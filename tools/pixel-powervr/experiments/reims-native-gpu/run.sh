#!/system/bin/sh
# One serialized reims -> native EL0 -> reims GPU handoff, with retained logs.
set -u
umask 077
[ "$#" -eq 1 ] || { echo "Usage: $0 /absolute/verified/qemu-package" >&2; exit 2; }
case "$1" in /*) ;; *) exit 2 ;; esac
engine=$(CDPATH= cd -- "$1" && pwd) || exit 1
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
run="$root/results/reims-native-$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir -p "$root/results" || exit 1
mkdir "$run" || exit 1
cache="$run/runtime-cache"
mkdir "$cache" || exit 1
printf 'RESULT_DIRECTORY=%s\n' "$run"
if ! (cd "$root" && sha256sum -c SHA256SUMS) > "$run/integrity.txt" 2>&1; then
  cat "$run/integrity.txt"
  echo "PACKAGE_INTEGRITY=FAIL"
  exit 1
fi
if ! (cd "$engine" && sha256sum -c SHA256SUMS) > "$run/engine-integrity.txt" 2>&1; then
  cat "$run/engine-integrity.txt"
  echo "ENGINE_INTEGRITY=FAIL"
  exit 1
fi
actual=$(sha256sum "$engine/qemu-system-aarch64") || exit 1
[ "${actual%% *}" = a815e121d487c15cd9c1cec75ca6f43a48b2edf1ab42675bb9cde988b9679145 ] || exit 1
{
  date -u +%Y-%m-%dT%H:%M:%SZ
  id
  id -Z
  getenforce
  uname -a
  printf 'engine=%s\nproducer_package=%s\n' "$engine" "$root"
  printf 'runtime_cache_root=%s\ncache_selection=child HOME unset; runtime XDG_CACHE_HOME fallback\n' "$cache"
} > "$run/context.txt" 2>&1
# The root shell's default cache resolves into Android's read-only root. Leave
# the caller's environment intact; the runtime's documented no-HOME fallback
# uses a fresh XDG cache in this run. No prior shader-cache contents are reused.
/system/bin/env -u HOME XDG_CACHE_HOME="$cache" \
  "$root/reims-native-gpu-owner" "$engine" < /dev/null > "$run/diagnostic.txt" 2>&1
status=$?
printf 'OWNER_EXIT=%s\n' "$status" > "$run/summary.txt"
grep -E '^(REIMS_|OWNER_|NATIVE_GPU_|RESULT=|native-gpu-one-region:)' \
  "$run/diagnostic.txt" >> "$run/summary.txt"
cat "$run/summary.txt"
if [ "$status" -ne 0 ] ||
   [ "$(grep -c '^OWNER_EVENT ' "$run/diagnostic.txt")" -ne 6 ] ||
   ! grep -qx 'RESULT=REIMS_NATIVE_GPU_ONE_REGION_PASS' "$run/diagnostic.txt" ||
   ! grep -qx 'NATIVE_GPU_GUEST_SVC_OK' "$run/diagnostic.txt" ||
   ! grep -q '^OWNER_TREE_CLOSED leader_reaped=1 .* ECHILD=1 group_signals=1$' "$run/diagnostic.txt"; then
  echo "REIMS_NATIVE_RUNNER=FAIL"
  exit 1
fi
echo "REIMS_NATIVE_RUNNER=PASS"
