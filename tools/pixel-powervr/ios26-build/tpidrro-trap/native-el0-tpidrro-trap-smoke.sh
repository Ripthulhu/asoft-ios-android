#!/system/bin/sh
# Qualify the opt-in generic TPIDRRO trap on the unchanged pinned el0bench ELF.
# Package layout: qemu-system-aarch64, lib/, el0bench.elf, SHA256SUMS.
# This is ordinary memfd RAM and copied code; no GPU or installed-engine change.
set -eu
if [ "$#" -ne 1 ]; then
    printf 'usage: sh native-el0-tpidrro-trap-smoke.sh /path/to/isolated/package\n' >&2
    exit 2
fi
bench_root=$(CDPATH= cd -- "$1" && pwd)
cd "$bench_root"
bench_results="$bench_root/results/tpidrro-trap-$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir -p "$bench_results"
fail() {
    printf 'NATIVE_TPIDRRO_TRAP_BENCH_PASS=0\nREASON=%s\nRESULTS=%s\n' "$1" "$bench_results"
    exit 1
}
check_benchmark_log() {
    bench_log=$1
    if grep -Eq 'MISMATCH|check=BAD|required initialization failed|TPIDRRO trap mode failed|staying on TCG|no stub factory' "$bench_log"; then
        fail 'guest mismatch or native failure diagnostic'
    fi
    if grep -Eq '^\[cpu[0-9]+\] EXIT -?[1-9][0-9]* faults=' "$bench_log"; then
        fail 'guest CPU reported a nonzero exit'
    fi
    grep -q '^native-el0: required initialization ready mode=stubs;' "$bench_log" \
        || fail 'required stub initialization not reported'
    grep -q '^native-el0: tpidrro-trap ready mode=stubs code=memfd$' "$bench_log" \
        || fail 'generic TPIDRRO trap initialization not reported'
    grep -Eq '^native-el0: enters [1-9][0-9]* svc [1-9][0-9]* ' "$bench_log" \
        || fail 'no positive native entry and native SVC counts'
    grep -Eq '^native-el0: time native [1-9][0-9]* ms,' "$bench_log" \
        || fail 'no positive native execution time'
    grep -Eq '^native-el0: stubs 2 spawned [1-9][0-9]* ' "$bench_log" \
        || fail 'no spawned native stub reported'
    grep -Eq '^native-el0: tpidrro-trap code-copies [1-9][0-9]* code-map-requests [1-9][0-9]*$' "$bench_log" \
        || fail 'no copied-code cache activity reported'
    # The pinned payload reads TPIDRRO at T0 (+0x154) and T7 (+0x768).
    # Requiring two reads and the last PC excludes a T0-only native witness.
    for bench_cpu in 0 1; do
        grep -Eq "^native-el0: tpidrro-trap cpu$bench_cpu reads ([2-9]|[1-9][0-9]+) last-pc 0x100000768$" "$bench_log" \
            || fail "CPU$bench_cpu did not report native T7 TPIDRRO emulation"
        grep -Eq "^\[cpu$bench_cpu\] T7 tpidr=0x1234 tpidrro=0xabcd000$bench_cpu OK[[:space:]]*$" "$bench_log" \
            || fail "CPU$bench_cpu thread-register correctness check did not pass"
        grep -Eq "^\[cpu$bench_cpu\] T6 OK calls=" "$bench_log" \
            || fail "CPU$bench_cpu floating-point state check did not pass"
        grep -Eq "^\[cpu$bench_cpu\] T10 memcpy16 .* check=ok" "$bench_log" \
            || fail "CPU$bench_cpu copy result check did not pass"
        grep -Eq "^\[cpu$bench_cpu\] EXIT 0 faults=" "$bench_log" \
            || fail "CPU$bench_cpu did not report successful completion"
    done
}
sha256sum -c SHA256SUMS > "$bench_results/hashes.txt" 2>&1 || fail 'package hash verification failed'

set +e
env -i PATH=/system/bin LD_LIBRARY_PATH="$bench_root/lib" \
    ASOFT_NATIVE_EL0=0 ASOFT_NATIVE_EL0_REQUIRED=1 \
    /system/bin/timeout -k 3 10 "$bench_root/qemu-system-aarch64" -version \
    < /dev/null > "$bench_results/disabled-native.txt" 2>&1
bench_disabled_status=$?
set -e
[ "$bench_disabled_status" -eq 1 ] || fail 'required-native negative check did not exit 1'
grep -q 'required initialization failed: ASOFT_NATIVE_EL0 is disabled' \
    "$bench_results/disabled-native.txt" || fail 'required-native diagnostic missing'

# An older required-native binary ignores the new flag and must not run a guest.
set +e
env -i PATH=/system/bin LD_LIBRARY_PATH="$bench_root/lib" \
    ASOFT_NATIVE_EL0=1 ASOFT_NATIVE_EL0_REQUIRED=1 ASOFT_NATIVE_EL0_STUBS=2 \
    ASOFT_NATIVE_EL0_TPIDRRO=1 ASOFT_NATIVE_EL0_TPIDRRO_TRAP=1 \
    /system/bin/timeout -k 3 10 "$bench_root/qemu-system-aarch64" -version \
    < /dev/null > "$bench_results/conflicting-modes.txt" 2>&1
bench_conflict_status=$?
set -e
[ "$bench_conflict_status" -eq 1 ] || fail 'TPIDRRO mode-conflict check did not exit 1'
grep -q 'TPIDRRO trap mode failed: ASOFT_NATIVE_EL0_TPIDRRO_TRAP and ASOFT_NATIVE_EL0_TPIDRRO are mutually exclusive' \
    "$bench_results/conflicting-modes.txt" || fail 'new TPIDRRO mode diagnostic missing'

# Match EngineService's /dev/null stdin. This changed no guest code or checks.
set +e
env -i PATH=/system/bin LD_LIBRARY_PATH="$bench_root/lib" \
    ASOFT_NATIVE_EL0=1 ASOFT_NATIVE_EL0_REQUIRED=1 \
    ASOFT_NATIVE_EL0_STATS=1 ASOFT_NATIVE_EL0_STUBS=2 \
    ASOFT_NATIVE_EL0_TPIDRRO_TRAP=1 \
    /system/bin/timeout -k 3 30 "$bench_root/qemu-system-aarch64" \
    -M virt,memory-backend=m0 \
    -object memory-backend-memfd,id=m0,size=512M,share=on \
    -cpu max,pauth-impdef=on -smp 2 -m 512 -accel tcg,thread=multi \
    -kernel "$bench_root/el0bench.elf" -nographic -monitor none \
    -serial stdio -nic none -no-reboot \
    < /dev/null > "$bench_results/benchmark.txt" 2>&1
bench_status=$?
set -e
cat "$bench_results/benchmark.txt"
printf 'BENCHMARK_EXIT=%s\n' "$bench_status"
[ "$bench_status" -eq 0 ] || fail 'benchmark failed or reached its 30-second bound'
check_benchmark_log "$bench_results/benchmark.txt"
printf 'NATIVE_TPIDRRO_TRAP_BENCH_PASS=1\nRESULTS=%s\n' "$bench_results"
