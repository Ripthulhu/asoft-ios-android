#!/usr/bin/env python3
"""Compile and exercise the actual native TPIDRRO rewrite/state helpers on host.

This checks instruction selection and register/state semantics. It does not run
AArch64 code or qualify Android signal delivery, executable mappings, or QEMU.
The source functions are extracted unchanged; the harness supplies small CPU
and signal-frame models plus inert unrelated FP/counter helpers. No repository
source is modified. Run with --source target/arm/tcg/native-el0.c when this file
is outside tests/unit in a QEMU source tree.
"""

import argparse
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile


def function(source, name):
    """Find a static definition, then balance braces outside C comments/strings."""
    match = re.search(
        r"^static[^\n]*\b" + re.escape(name) + r"\s*\([^;]*?\)\s*\{",
        source,
        re.MULTILINE,
    )
    if not match:
        raise AssertionError(f"missing static definition: {name}")
    start = source.index("{", match.start())
    depth, state, i = 0, "code", start
    while i < len(source):
        char, pair = source[i], source[i : i + 2]
        if state == "line":
            if char == "\n":
                state = "code"
        elif state == "block":
            if pair == "*/":
                state = "code"
                i += 1
        elif state in ("'", '"'):
            if char == "\\":
                i += 1
            elif char == state:
                state = "code"
        elif pair in ("//", "/*"):
            state = "line" if pair == "//" else "block"
            i += 1
        elif char in ("'", '"'):
            state = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[match.start() : i + 1]
        i += 1
    raise AssertionError(f"unclosed static definition: {name}")


def macro(source, name):
    match = re.search(r"^#define\s+" + re.escape(name) + r"\s+[^\n]+", source, re.MULTILINE)
    if not match:
        raise AssertionError(f"missing macro: {name}")
    return match.group(0)


PREFIX = r"""
#include <assert.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <signal.h>

#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define unlikely(a) (a)
#define qatomic_inc(p) (++*(p))
#define qatomic_xchg(p, v) exchange_int((p), (v))
#define PSTATE_NZCV UINT32_C(0xf0000000)
#define PSTATE_DIT (UINT32_C(1) << 24)
#define PSTATE_SSBS (UINT32_C(1) << 12)
static int exchange_int(int *p, int v) { int old = *p; *p = v; return old; }

typedef struct {
    uint64_t regs[31];
    uint64_t register_guard, sp, pc, pstate;
} TestMContext;
typedef struct {
    TestMContext uc_mcontext;
    sigset_t uc_sigmask;
} TestUContext;
#define ucontext_t TestUContext

typedef struct CPUARMState {
    uint64_t xregs[32], pc, sprr_uperm_el0;
    uint32_t pstate, fpsr, fpcr;
    struct { uint64_t tpidrro_el[1], tpidr_el[1]; } cp15;
    struct { struct { uint64_t d[2]; } zregs[32]; } vfp;
} CPUARMState;
typedef struct { CPUARMState *env; } TestCPU;
typedef struct {
    TestCPU *cs;
    uint64_t guest_tpidr, emul_mrs, tpidrro_traps, tpidrro_trap_last_pc;
} NativeCtx;
struct fpsimd_context { unsigned char vregs[32][16]; uint32_t fpsr, fpcr; };

static bool tpidrro_trap_mode, tpidrro_mode, tpro_carry, ssbs_native;
static bool test_tpro_pair, test_host_counter, test_tpro_const, pac_off, patch_log;
static uint64_t tpidrro_patched;
static int sig_kick = SIGUSR1, sig_enter = SIGUSR2, sig_inval = SIGWINCH;
enum { MK_TPRO_W, MK_TPRO_R, MK_TPIDRRO, MK_CNT, MK_ACNT, MK_N };
static uint64_t mrs_kind[MK_N];
static CPUARMState *cpu_env(TestCPU *cpu) { return cpu->env; }
static uint32_t pstate_read(CPUARMState *env) { return env->pstate; }
static void pstate_write(CPUARMState *env, uint32_t value) { env->pstate = value; }
static struct fpsimd_context *find_fpsimd(TestUContext *uc) { (void)uc; return NULL; }
static uint32_t vfp_get_fpsr(CPUARMState *env) { return env->fpsr; }
static uint32_t vfp_get_fpcr(CPUARMState *env) { return env->fpcr; }
static void vfp_set_fpsr(CPUARMState *env, uint32_t value) { env->fpsr = value; }
static void vfp_set_fpcr(CPUARMState *env, uint32_t value) { env->fpcr = value; }
static void arm_rebuild_hflags(CPUARMState *env) { (void)env; }
static void tpro_value_seen(uint64_t value, uint64_t pc) { (void)value; (void)pc; }
static void tpro_site_hit(uint64_t pc) { (void)pc; }
static uint64_t gt_get_countervalue(CPUARMState *env) { (void)env; return 123; }
static bool tpro_pair_on(void) { return test_tpro_pair; }
static bool host_counter_on(void) { return test_host_counter; }
static bool tpro_const_on(void) { return test_tpro_const; }
static inline bool is_patch_word(uint32_t w);
static inline uint32_t patched_word(uint32_t w);
"""

MAIN = r"""
static void test_rewrite(void)
{
    /* Independently assembled AArch64 encodings: MRS RO has low five Rt bits;
     * UDF #imm16 stores its immediate in the low 16 instruction bits.
     */
    tpidrro_trap_mode = true;
    for (unsigned rt = 0; rt < 32; rt++) {
        uint32_t original = UINT32_C(0xd53bd060) | rt;
        assert(is_tpidrro_read(original));
        assert(tpidrro_trap_word(original) == (UINT32_C(0x00006000) | rt));
        for (unsigned bit = 5; bit < 32; bit++) {
            uint32_t neighbour = original ^ (UINT32_C(1) << bit);
            assert(!is_tpidrro_read(neighbour));
            assert(tpidrro_trap_word(neighbour) == neighbour);
        }
    }

    /* Generic mode must win over every legacy rewrite knob. These include
     * both TPIDR accesses, counters, PACGA, TPRO and its adjacent branch,
     * SSBS reads/writes, an ordinary UDF, and an ordinary arithmetic word.
     */
    const uint32_t untouched[] = {
        0xd53bd041, 0xd51bd041, 0xd51bd061, 0xd53be040, 0xd53be0c0,
        0xd53be020, 0xd53be0a0, 0x9ac03000, 0xd53ef1a0, 0xb6200000,
        0xd53b42c0, 0xd503403f, 0x00001234, 0x91000400,
    };
    for (unsigned knobs = 0; knobs < 16; knobs++) {
        test_tpro_pair = knobs & 1;
        ssbs_native = knobs & 2;
        pac_off = knobs & 4;
        test_tpro_const = knobs & 8;
        for (unsigned i = 0; i < ARRAY_SIZE(untouched); i++) {
            uint32_t w = untouched[i];
            assert(patched_at(0xd53ef1a0, w, 0xb6200000, 1) == w);
        }
        uint32_t page[] = { 0xd53bd060, 0xd53bd07f, 0xd53bd041,
                            0xd51bd041, 0xd53ef1a0, 0xb6200000 };
        uint32_t original[ARRAY_SIZE(page)];
        memcpy(original, page, sizeof(page));
        assert(patch_code_words(page, ARRAY_SIZE(page), UINT64_C(0x100000000)) == 2);
        assert(page[0] == 0x00006000 && page[1] == 0x0000601f);
        assert(!memcmp(page + 2, original + 2, sizeof(page) - 2 * sizeof(page[0])));
    }

    /* Opt-in disabled: preserve the existing iOS swap exactly. */
    tpidrro_trap_mode = false;
    test_tpro_pair = false;
    ssbs_native = true;
    pac_off = false;
    test_tpro_const = false;
    for (unsigned rt = 0; rt < 32; rt++) {
        assert(patched_at(0, 0xd53bd060 | rt, 0, 0) == (0xd53bd040 | rt));
        assert(patched_at(0, 0xd53bd040 | rt, 0, 0) == (0xd53bd060 | rt));
        assert(patched_at(0, 0xd51bd040 | rt, 0, 0) == (0xd51bd040 | rt));
    }
}

static void test_emulation(void)
{
    const uint64_t values[] = { 0, 0xabcd0000, 0xabcd0001, UINT64_MAX,
                               UINT64_C(0x9a5b3c7d01234567) };
    tpidrro_trap_mode = true;
    tpidrro_mode = false;
    tpro_carry = false;
    for (unsigned vi = 0; vi < ARRAY_SIZE(values); vi++) {
        for (unsigned rt = 0; rt < 32; rt++) {
            CPUARMState env = {0};
            TestCPU cpu = { &env };
            NativeCtx nc = { .cs = &cpu };
            TestUContext uc = {0};
            env.cp15.tpidrro_el[0] = values[vi];
            env.cp15.tpidr_el[0] = UINT64_C(0x1234);
            for (unsigned r = 0; r < 31; r++) {
                uc.uc_mcontext.regs[r] = UINT64_C(0xfedcba0000000000) + r;
            }
            uc.uc_mcontext.register_guard = UINT64_C(0x7b4d3a291d263e5f);
            uc.uc_mcontext.sp = UINT64_C(0x110010000);
            uc.uc_mcontext.pc = UINT64_C(0x100000768);
            uc.uc_mcontext.pstate = UINT64_C(0xa1001000);
            TestUContext before = uc;
            assert(emulate_mrs(&nc, &uc, UINT32_C(0xd53bd060) | rt));
            for (unsigned r = 0; r < 31; r++) {
                assert(uc.uc_mcontext.regs[r] ==
                       (r == rt ? values[vi] : before.uc_mcontext.regs[r]));
            }
            assert(uc.uc_mcontext.register_guard == before.uc_mcontext.register_guard);
            assert(uc.uc_mcontext.sp == before.uc_mcontext.sp);
            assert(uc.uc_mcontext.pstate == before.uc_mcontext.pstate);
            assert(uc.uc_mcontext.pc == before.uc_mcontext.pc + 4);
            assert(env.cp15.tpidrro_el[0] == values[vi]);
            assert(env.cp15.tpidr_el[0] == 0x1234);
            assert(nc.tpidrro_traps == 1 && nc.emul_mrs == 1);
            assert(nc.tpidrro_trap_last_pc == before.uc_mcontext.pc);
        }
    }

    const uint32_t rejected[] = { 0x00006000, 0x0000601f, 0xd53bd041,
                                 0xd51bd041, 0xd51bd061, 0x91000400 };
    for (unsigned i = 0; i < ARRAY_SIZE(rejected); i++) {
        CPUARMState env = {0};
        TestCPU cpu = { &env };
        NativeCtx nc = { .cs = &cpu };
        TestUContext uc = {0};
        uc.uc_mcontext.pc = 0x100000768;
        TestUContext before = uc;
        assert(!emulate_mrs(&nc, &uc, rejected[i]));
        assert(!memcmp(&uc, &before, sizeof(uc)));
        assert(nc.tpidrro_traps == 0 && nc.emul_mrs == 0);
    }
    assert(mrs_kind[MK_TPIDRRO] == 32 * ARRAY_SIZE(values));
}

static void test_state_roundtrip(void)
{
    for (unsigned legacy = 0; legacy < 2; legacy++) {
        CPUARMState env = {0};
        TestCPU cpu = { &env };
        NativeCtx nc = { .cs = &cpu };
        TestUContext uc = {0};
        tpidrro_mode = legacy;
        tpidrro_trap_mode = !legacy;
        ssbs_native = false;
        tpro_carry = false;
        env.cp15.tpidr_el[0] = 0x1234;
        env.cp15.tpidrro_el[0] = 0xabcd0001;
        env.xregs[31] = 0x110010000;
        env.pc = 0x100000154;
        sigfillset(&uc.uc_sigmask);
        state_to_frame(&nc, &uc);
        assert(nc.guest_tpidr == (legacy ? 0xabcd0001 : 0x1234));
        /* Model a native writable-TPIDR update returned by the stub. */
        frame_to_state(&nc, &uc, 0x5678);
        assert(env.cp15.tpidr_el[0] == (legacy ? 0x1234 : 0x5678));
        assert(env.cp15.tpidrro_el[0] == 0xabcd0001);
        state_to_frame(&nc, &uc);
        assert(nc.guest_tpidr == (legacy ? 0xabcd0001 : 0x5678));
    }
}

int main(void)
{
    test_rewrite();
    test_emulation();
    test_state_roundtrip();
    puts("PASS: exact rewrite, Rt0..31, 5 read-only values, original-word emulation, PC+4, preserved writable TPIDR, and legacy swap/state semantics");
    return 0;
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path,
        default=Path(__file__).resolve().parents[2] / "target/arm/tcg/native-el0.c",
    )
    parser.add_argument("--cc", default=os.environ.get("CC", "cc"))
    args = parser.parse_args()
    source = args.source.read_text()
    definitions = [macro(source, name) for name in (
        "PACGA_UDF", "TPIDRRO_TRAP_UDF", "TPRO_W_BIT", "PSTATE_COPY",
    )]
    definitions.extend(function(source, name) for name in (
        "is_pacga", "is_tpro_mrs", "is_tb_bit36", "is_ssbs_msr", "is_ssbs_mrs",
        "is_tpidrro_read", "tpidrro_trap_word", "is_patch_word", "patched_word",
        "patched_at", "patch_code_words", "emulate_mrs", "state_to_frame", "frame_to_state",
    ))
    harness = PREFIX + "\n\n".join(definitions) + MAIN
    with tempfile.TemporaryDirectory(prefix="native-tpidrro-rewrite-test-") as temporary:
        root = Path(temporary)
        c_path, executable = root / "test.c", root / "test"
        c_path.write_text(harness)
        subprocess.run(
            shlex.split(args.cc) + ["-std=gnu11", "-O1", "-g", "-Wall", "-Wextra",
                                   "-Werror", "-fsanitize=undefined",
                                   "-fno-sanitize-recover=all", str(c_path), "-o", str(executable)],
            check=True, timeout=30,
        )
        subprocess.run([str(executable)], check=True, timeout=5)


if __name__ == "__main__":
    main()
