#!/usr/bin/env python3
"""Bounded host tests of the production TPIDRRO option and mapping policy.

The actual C functions are extracted at run time. Header/type glue, cache scan
results and storage are simulated; no AArch64 guest or target syscall is run.
The cache fixture executes production cc_fill/cc_same, including the n=0 path.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import tempfile

SOURCE = Path(__file__).resolve().parents[2] / "target/arm/tcg/native-el0.c"


def function(source, name):
    match = re.search(r"(?m)^static\s+[^;{}]*?\b" + re.escape(name) +
                      r"\s*\([^;{}]*?\)\s*\{", source)
    if not match:
        raise RuntimeError("Missing production function: " + name)
    depth = 1
    end = match.end()
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[match.start():end]


def main():
    source = SOURCE.read_text()
    names = (
        "native_el0_required_mode", "native_el0_required_fail",
        "native_el0_tpidrro_trap_fail", "native_el0_tpidrro_trap_requested",
        "native_el0_required_check_enabled", "native_el0_tpidrro_trap_check_config",
        "tpidrro_trap_require_ro_exec", "tpidrro_trap_require_cache",
        "tpidrro_trap_fill_valid", "tpidrro_trap_require_cached",
        "is_tpidrro_read", "tpidrro_trap_word")
    defines = "\n".join(re.search(r"(?m)^#define " + name + r"\s+[^\n]+", source).group()
                        for name in ("STUB_MAX", "CC_PAGE", "CC_WORDS", "CC_SLOTS",
                                     "CC_MAXP", "CC_FRAMES", "FD_INDEX_CC", "TPIDRRO_TRAP_UDF"))
    ctor = function(source, "native_el0_setup")
    prefix = ctor[ctor.index("{") + 1:ctor.index("\n    {\n        uint64_t f;")]
    cache_type_end = source.index("} CcMeta;") + len("} CcMeta;")
    cache_type_start = source.rfind("typedef struct {", 0, cache_type_end)
    prelude = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <errno.h>
#include <inttypes.h>
#include <pthread.h>
#include <sys/mman.h>
#define G_GNUC_PRINTF(a,b) __attribute__((format(printf,a,b)))
#define PAGE_READ 1
#define PAGE_WRITE 2
#define PAGE_EXEC 4
#define qatomic_inc(p) (++*(p))
enum { CC_CLEAN, CC_CACHED, CC_NONE };
static bool tpidrro_trap_mode, tpidrro_mode, patch_xo, stub_mode;
static char *cc_base;
typedef struct {
    uint64_t va, len, off;
    int fd_index, prot, patch;
} StubFill;
'''
    cache_glue = r'''
static uint32_t *cc_of_frame, cc_next;
static CcMeta *cc_meta;
static uint64_t cc_clean, cc_hits, cc_misses, cc_stale, cc_none, cc_trap_copies;
static uint64_t tpro_pairs, tpro_lone, ssbs_guest_words;
static bool ssbs_native;
static int tpro_log_left, scan_count;
static pthread_mutex_t cc_lock = PTHREAD_MUTEX_INITIALIZER;
static int cc_scan(const uint32_t *w, uint16_t *idx)
{
    for (int k = 0; k < scan_count; k++) { idx[k] = k; }
    return scan_count;
}
static uint32_t patched_in(const uint32_t *w, uint64_t i, uint64_t n)
{
    return tpidrro_trap_mode ? tpidrro_trap_word(w[i]) : w[i];
}
static bool is_tpro_mrs(uint32_t w) { return false; }
static bool is_ssbs_msr(uint32_t w) { return false; }
static bool is_ssbs_mrs(uint32_t w) { return false; }
'''
    driver = r'''
static pthread_mutex_t held_lock = PTHREAD_MUTEX_INITIALIZER;
static void cleanup(void)
{
    pthread_mutex_lock(&held_lock);
    puts("CLEANUP_REACHED");
    pthread_mutex_unlock(&held_lock);
}
static bool enabled(const char *name)
{
    const char *v = getenv(name);
    return v && *v && *v != '0';
}
static uint64_t number(const char *s) { return strtoull(s, NULL, 0); }
int main(int argc, char **argv)
{
    int status = 0;
    assert(argc >= 2);
    atexit(cleanup);
    pthread_mutex_lock(&held_lock);
    if (!strcmp(argv[1], "config")) {
        fixture_initial_options();
        tpidrro_mode = enabled("ASOFT_NATIVE_EL0_TPIDRRO");
        patch_xo = enabled("ASOFT_NATIVE_EL0_PATCH_XO");
        native_el0_tpidrro_trap_check_config();
        printf("MODE=%d\n", tpidrro_trap_mode);
    } else if (!strcmp(argv[1], "map")) {
        assert(argc == 11);
        tpidrro_trap_mode = atoi(argv[2]);
        stub_mode = atoi(argv[8]);
        cc_base = atoi(argv[9]) ? (char *)1 : NULL;
        patch_xo = atoi(argv[10]);
        tpidrro_trap_require_cache(atoi(argv[3]), number(argv[4]), number(argv[5]),
                                  number(argv[6]), atoi(argv[7]));
    } else if (!strcmp(argv[1], "fill")) {
        assert(argc == 9);
        tpidrro_trap_mode = atoi(argv[2]);
        StubFill f = {.prot = atoi(argv[3]), .patch = atoi(argv[4]),
                      .fd_index = atoi(argv[5]), .va = number(argv[6]),
                      .len = number(argv[7]), .off = number(argv[8])};
        status = tpidrro_trap_fill_valid(&f) ? 0 : 2;
    } else if (!strcmp(argv[1], "cache-policy")) {
        tpidrro_trap_mode = atoi(argv[2]);
        tpidrro_trap_require_cached(atoi(argv[3]));
    } else if (!strcmp(argv[1], "cache-behavior")) {
        uint32_t *words = calloc(CC_WORDS, sizeof(uint32_t));
        cc_base = calloc(2, CC_PAGE);
        cc_of_frame = calloc(CC_FRAMES, sizeof(uint32_t));
        cc_meta = calloc(CC_SLOTS, sizeof(CcMeta));
        assert(words && cc_base && cc_of_frame && cc_meta);
        words[0] = 0xd503201f; /* NOP, with no RO-register read initially. */
        uint64_t off = UINT64_MAX;
        scan_count = 0;
        tpidrro_trap_mode = false;
        assert(cc_fill(words, 0, &off) == CC_CLEAN && cc_next == 0);
        tpidrro_trap_mode = true;
        assert(cc_fill(words, 0, &off) == CC_CACHED && off == 0);
        assert(cc_next == 1 && cc_trap_copies == 1);
        assert(!memcmp(words, cc_base, CC_PAGE));
        assert(cc_fill(words, 0, &off) == CC_CACHED && cc_hits == 1);
        assert(cc_trap_copies == 1);
        words[0] = 0xd53bd061; /* A replacement frame now contains MRS x1,RO. */
        scan_count = 1;
        assert(cc_fill(words, 0, &off) == CC_CACHED && cc_stale == 1);
        assert(((uint32_t *)cc_base)[0] == 0x00006001 && cc_trap_copies == 2);
        scan_count = -1;
        assert(cc_fill(words, CC_PAGE, &off) == CC_NONE);
        scan_count = 1;
        assert(cc_fill(words, (uint64_t)CC_FRAMES * CC_PAGE, &off) == CC_NONE);
        cc_next = CC_SLOTS;
        assert(cc_fill(words, CC_PAGE, &off) == CC_NONE);
        puts("CACHE_COPY_REUSE_REWRITE_LIMITS_PASSED");
    } else {
        return 3;
    }
    pthread_mutex_unlock(&held_lock);
    return status;
}
'''
    unit = (prelude + defines + "\n" + source[cache_type_start:cache_type_end] + "\n" +
            "\n".join(function(source, name) for name in names) +
            "\nstatic void fixture_initial_options(void) {\n" + prefix + "\n}\n" +
            cache_glue + function(source, "cc_same") + "\n" +
            function(source, "cc_fill") + "\n" + driver)
    results = []
    with tempfile.TemporaryDirectory(prefix="native-tpidrro-policy-") as tmp:
        root = Path(tmp)
        (root / "fixture.c").write_text(unit)
        exe = root / "fixture"
        subprocess.run([os.environ.get("CC", "cc"), "-std=gnu11", "-O2", "-Wall", "-Werror",
                        "-pthread", str(root / "fixture.c"), "-o", str(exe)], check=True)
        clean = {k: v for k, v in os.environ.items() if not k.startswith("ASOFT_")}

        def run(name, args, expected, env=None):
            result = subprocess.run([str(exe), *map(str, args)], env=clean | (env or {}),
                                    capture_output=True, text=True, timeout=2)
            assert result.returncode == expected, (name, result)
            assert ("CLEANUP_REACHED" in result.stdout) == (expected != 1), (name, result)
            results.append({"name": name, "exit_code": result.returncode, "pass": True})

        for value in (None, "", "0"):
            env = {} if value is None else {"ASOFT_NATIVE_EL0_TPIDRRO_TRAP": value}
            run("mode-disabled-" + repr(value), ["config"], 0, env)
        for value in ("true", "2", "01", "-1"):
            run("invalid-mode-" + value, ["config"], 1,
                {"ASOFT_NATIVE_EL0_TPIDRRO_TRAP": value})
        good = {"ASOFT_NATIVE_EL0_TPIDRRO_TRAP": "1", "ASOFT_NATIVE_EL0_REQUIRED": "1",
                "ASOFT_NATIVE_EL0": "1", "ASOFT_NATIVE_EL0_STUBS": "2"}
        run("valid-mode", ["config"], 0, good)
        for name, changes in (
            ("missing-required", {"ASOFT_NATIVE_EL0_REQUIRED": "0"}),
            ("native-disabled", {"ASOFT_NATIVE_EL0": "0"}),
            ("ios-swap-conflict", {"ASOFT_NATIVE_EL0_TPIDRRO": "1"}),
            ("codecache-disabled", {"ASOFT_NATIVE_EL0_CODECACHE": "0"}),
            ("patch-xo-conflict", {"ASOFT_NATIVE_EL0_PATCH_XO": "1"})):
            run(name, ["config"], 1, good | changes)
        for value in ("", "0", "-1", "33", "2x", "two", "999999999999999999999999"):
            run("invalid-stubs-" + value, ["config"], 1, good | {"ASOFT_NATIVE_EL0_STUBS": value})
        for value in ("1", "32"):
            run("valid-stubs-" + value, ["config"], 0, good | {"ASOFT_NATIVE_EL0_STUBS": value})
        run("legacy-options-not-rejected", ["config"], 0,
            {"ASOFT_NATIVE_EL0_TPIDRRO": "1", "ASOFT_NATIVE_EL0_CODECACHE": "0",
             "ASOFT_NATIVE_EL0_PATCH_XO": "1"})
        # mode, permissions, guest VA, length, RAM offset, fd index, stub, cache, XO
        base = [1, 5, 0x100000000, 0x4000, 0, 0, 1, 1, 0]
        run("aligned-ro-exec", ["map", *base], 0)
        for name, index, value in (
            ("writable-exec", 1, 7), ("short-exec-page", 3, 0x1000),
            ("unaligned-exec-va", 2, 0x100001000), ("unaligned-ram-offset", 4, 0x1000),
            ("other-ram-fd", 5, 1), ("missing-ram-fd", 5, -1),
            ("in-process", 6, 0), ("cache-unavailable", 7, 0), ("xo-copy", 8, 1)):
            args = base.copy()
            args[index] = value
            run(name, ["map", *args], 1)
        run("nonexec-data-does-not-request-code-cache", ["map", 1, 3, 3, 3, 3, -1, 0, 0, 1], 0)
        run("legacy-map-policy-unchanged", ["map", 0, 7, 3, 3, 3, -1, 0, 0, 1], 0)
        # mode, host permissions, private patch, fd index, VA, length, cache offset
        base = [1, 5, 0, -2, 0x100000000, 0x4000, 0]
        run("worker-cached-ro-exec", ["fill", *base], 0)
        for name, index, value in (
            ("worker-rwx", 1, 7), ("worker-private-copy", 2, 1),
            ("worker-direct-ram", 3, 0), ("worker-short-page", 5, 0x1000),
            ("worker-unaligned-va", 4, 0x100001000), ("worker-unaligned-offset", 6, 0x1000)):
            args = base.copy()
            args[index] = value
            run(name, ["fill", *args], 2)
        run("worker-data-unchanged", ["fill", 1, 3, 0, 0, 0x100004000, 0x4000, 0], 0)
        run("legacy-worker-unchanged", ["fill", 0, 7, 1, 0, 3, 3, 3], 0)
        for mode in (0, 1):
            for result in (0, 1, 2):
                run(f"cache-result-mode{mode}-result{result}", ["cache-policy", mode, result],
                    1 if mode and result != 1 else 0)
        run("production-cache-copy-reuse-rewrite-limits", ["cache-behavior"], 0)
    print(json.dumps({"scope": "production option/mapping/cache policy with simulated storage and scan",
                      "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                      "cases": results}, indent=2))


if __name__ == "__main__":
    main()
