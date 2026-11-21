#!/system/bin/sh
# Manual-upload runner for the frozen cached-memory BASIC mode only.
# The diagnostic's stdout must remain a regular file: do not pipe it through tee.
set -eu
umask 077
PATH=/system/bin
export PATH

if [ "$#" -ne 0 ]; then
    printf 'usage: sh run-cached-memory.sh\nThis runner accepts no options.\n' >&2
    exit 64
fi

if [ ! -x /system/bin/timeout ] || [ ! -x /system/bin/sha256sum ]; then
    printf 'This runner requires Android /system/bin/timeout and sha256sum.\n' >&2
    exit 65
fi
if [ "$(uname -m)" != aarch64 ]; then
    printf 'This package requires an AArch64 Android device.\n' >&2
    exit 65
fi

package_dir=$(CDPATH= cd -P "$(dirname "$0")" && pwd -P)
cd "$package_dir"
mkdir -p results
run_dir="$package_dir/results/cached-$(date -u +%Y%m%dT%H%M%SZ)-$$"
# A collision is an error; an earlier diagnostic log is never overwritten.
mkdir "$run_dir"
printf 'RESULTS=%s\n' "$run_dir"
printf 'RUNNER_STATE=VERIFYING\n' > "$run_dir/status.txt"

if ! sha256sum -c SHA256SUMS > "$run_dir/checksums.txt" 2>&1; then
    cat "$run_dir/checksums.txt" >&2
    printf 'RUNNER_RESULT=PACKAGE_CHECKSUM_FAILURE\n' >> "$run_dir/status.txt"
    exit 66
fi
expected_binary=f69664840ba2e7588e196849ea4ce9ff598a8c0081c22e8ac249830fb43f2b9c
actual_binary=$(sha256sum cached_memory_diagnostic)
if [ "$actual_binary" != "$expected_binary  cached_memory_diagnostic" ]; then
    printf 'Frozen binary identity mismatch.\n' >&2
    printf 'RUNNER_RESULT=FROZEN_BINARY_MISMATCH\n' >> "$run_dir/status.txt"
    exit 66
fi

{
    printf 'PACKAGE=pixel-cached-memory-device\n'
    printf 'BINARY_SHA256=%s\n' "$expected_binary"
    printf 'START_UTC=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'MODE=--cached-memory\nPRODUCER_CPU_ATOMICS_REQUESTED=0\n'
    printf 'OUTER_TIMEOUT_SECONDS=65\nOUTER_TIMEOUT_SIGNAL=KILL\n'
    printf 'KERNEL_PANIC_CONTAINED=no\n'
    id
    id -Z 2>/dev/null || true
    uname -a
    if command -v getenforce >/dev/null 2>&1; then getenforce; fi
} > "$run_dir/environment.txt" 2>&1

chmod 700 cached_memory_diagnostic
printf 'RUNNER_STATE=RUNNING\n' >> "$run_dir/status.txt"
printf 'Running the frozen default mode; output: %s/diagnostic.txt\n' "$run_dir"
set +e
/system/bin/timeout -s KILL 65 ./cached_memory_diagnostic --cached-memory \
    > "$run_dir/diagnostic.txt" 2>&1
diagnostic_status=$?
set -e
printf 'DIAGNOSTIC_EXIT=%s\nEND_UTC=%s\n' "$diagnostic_status" \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$run_dir/status.txt"

if [ "$diagnostic_status" -ne 0 ]; then
    printf 'RUNNER_RESULT=DIAGNOSTIC_DID_NOT_PASS\n' >> "$run_dir/status.txt"
    tail -n 40 "$run_dir/diagnostic.txt"
    cat "$run_dir/status.txt"
    printf 'RESULTS=%s\nPreserve this directory before any further test.\n' "$run_dir"
    exit "$diagnostic_status"
fi

if ! grep -q '^RESULT=CACHED_MEMORY_BASIC_PASS_ATOMICS_NOT_TESTED$' "$run_dir/diagnostic.txt" ||
   ! grep -q '^cached-memory-diagnostic .* producer_cpu_atomics=0$' "$run_dir/diagnostic.txt" ||
   ! grep -q '^CACHED_MEMORY_CHECKPOINT phase=final_result role=parent .* cpu_atomics=0 .* regular_log=1 ' "$run_dir/diagnostic.txt"; then
    printf 'RUNNER_RESULT=EXPECTED_DEFAULT_RESULT_MISSING\n' >> "$run_dir/status.txt"
    tail -n 40 "$run_dir/diagnostic.txt"
    cat "$run_dir/status.txt"
    printf 'RESULTS=%s\nPreserve this directory before any further test.\n' "$run_dir"
    exit 1
fi

printf 'RUNNER_RESULT=CACHED_MEMORY_BASIC_PASS_ATOMICS_NOT_TESTED\n' >> "$run_dir/status.txt"
tail -n 40 "$run_dir/diagnostic.txt"
cat "$run_dir/status.txt"
printf 'RESULTS=%s\n' "$run_dir"
