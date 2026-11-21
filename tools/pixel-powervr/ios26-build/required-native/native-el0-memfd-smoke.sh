#!/system/bin/sh
# Isolated native EL0 qualification using the existing el0bench guest.
# Package layout: qemu-system-aarch64, lib/, el0bench.elf, SHA256SUMS.
# No disk, network, iOS image, GPU allocation or installed-engine replacement.
set -eu
if [ "$#" -ne 1 ]; then
    printf 'usage: sh native-el0-memfd-smoke.sh /path/to/isolated/package\n' >&2
    exit 2
fi
bench_root=$(CDPATH= cd -- "$1" && pwd)
cd "$bench_root"
bench_results="$bench_root/results/native-$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir -p "$bench_results"
fail() {
    printf 'NATIVE_MEMFD_BENCH_PASS=0\nREASON=%s\nRESULTS=%s\n' "$1" "$bench_results"
    exit 1
}
check_benchmark_log() {
    bench_log=$1
    if grep -Eq 'MISMATCH|check=BAD|required initialization failed|staying on TCG|no stub factory' "$bench_log"; then
        fail 'guest mismatch or native failure diagnostic'
    fi
    # kprintf prefixes every guest line with the CPU number. CPU0 waits for
    # the other CPUs before its final exit; any CPU's nonzero exit is fatal.
    if grep -Eq '^\[cpu[0-9]+\] EXIT -?[1-9][0-9]* faults=' "$bench_log"; then
        fail 'guest CPU reported a nonzero exit'
    fi
    grep -q '^native-el0: required initialization ready mode=stubs;' "$bench_log" \
        || fail 'required stub initialization not reported'
    grep -Eq '^native-el0: enters [1-9][0-9]* svc [1-9][0-9]* ' "$bench_log" \
        || fail 'no positive native entry and native SVC counts'
    grep -Eq '^native-el0: time native [1-9][0-9]* ms,' "$bench_log" \
        || fail 'no positive native execution time'
    grep -Eq '^native-el0: stubs 2 spawned [1-9][0-9]* ' "$bench_log" \
        || fail 'no spawned native stub reported'
    grep -Eq '^\[cpu0\] EXIT 0 faults=' "$bench_log" \
        || fail 'guest CPU0 did not report successful completion'
    grep -q 'T6 OK calls=' "$bench_log" || fail 'floating-point state check did not pass'
    grep -Eq 'T10 memcpy16 .* check=ok' "$bench_log" || fail 'copy result check did not pass'
}
sha256sum -c SHA256SUMS > "$bench_results/hashes.txt" 2>&1 || fail 'package hash verification failed'

# Refuse to launch a guest if this is the old engine or the new gate is broken.
set +e
env -i PATH=/system/bin LD_LIBRARY_PATH="$bench_root/lib" \
    ASOFT_NATIVE_EL0=0 ASOFT_NATIVE_EL0_REQUIRED=1 \
    /system/bin/timeout -k 3 10 "$bench_root/qemu-system-aarch64" -version \
    > "$bench_results/disabled-native.txt" 2>&1
bench_disabled_status=$?
set -e
[ "$bench_disabled_status" -eq 1 ] || fail 'required-native negative check did not exit 1'
grep -q 'required initialization failed: ASOFT_NATIVE_EL0 is disabled' \
    "$bench_results/disabled-native.txt" || fail 'required-native diagnostic missing'

# Same memfd-backed virt guest and CPU settings as Android EngineService.java.
set +e
env -i PATH=/system/bin LD_LIBRARY_PATH="$bench_root/lib" \
    ASOFT_NATIVE_EL0=1 ASOFT_NATIVE_EL0_REQUIRED=1 \
    ASOFT_NATIVE_EL0_STATS=1 ASOFT_NATIVE_EL0_STUBS=2 \
    /system/bin/timeout -k 3 30 "$bench_root/qemu-system-aarch64" \
    -M virt,memory-backend=m0 \
    -object memory-backend-memfd,id=m0,size=512M,share=on \
    -cpu max,pauth-impdef=on -smp 2 -m 512 -accel tcg,thread=multi \
    -kernel "$bench_root/el0bench.elf" -nographic -monitor none \
    -serial stdio -nic none -no-reboot > "$bench_results/benchmark.txt" 2>&1
bench_status=$?
set -e
cat "$bench_results/benchmark.txt"
printf 'BENCHMARK_EXIT=%s\n' "$bench_status"
[ "$bench_status" -eq 0 ] || fail 'benchmark failed or reached its 30-second bound'
check_benchmark_log "$bench_results/benchmark.txt"
printf 'NATIVE_MEMFD_BENCH_PASS=1\nRESULTS=%s\n' "$bench_results"
