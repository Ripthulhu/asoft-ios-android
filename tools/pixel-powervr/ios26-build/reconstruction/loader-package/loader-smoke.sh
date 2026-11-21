#!/system/bin/sh
# Loader and registration checks only. No guest images or GPU allocations.
set -eu
smoke_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$smoke_root"
sha256sum -c SHA256SUMS
smoke_results="$smoke_root/results/$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir -p "$smoke_results"
run_info() {
    smoke_name=$1
    shift
    # A clean environment prevents inherited ASOFT settings spawning stubs.
    set +e
    env -i PATH=/system/bin LD_LIBRARY_PATH="$smoke_root/lib" \
        /system/bin/timeout -k 2 10 "$smoke_root/bin/qemu-system-aarch64" "$@" \
        > "$smoke_results/$smoke_name.txt" 2>&1
    smoke_status=$?
    set -e
    cat "$smoke_results/$smoke_name.txt"
    printf '%s_EXIT=%s\n' "$smoke_name" "$smoke_status"
    if [ "$smoke_status" -ne 0 ]; then
        printf 'QEMU_LOADER_SMOKE_PASS=0\nRESULTS=%s\n' "$smoke_results"
        exit "$smoke_status"
    fi
}
run_info version -version
run_info machines -machine help
run_info accelerators -accel help
grep -q '^vresearch ' "$smoke_results/machines.txt"
printf 'QEMU_LOADER_SMOKE_PASS=1\nRESULTS=%s\n' "$smoke_results"
