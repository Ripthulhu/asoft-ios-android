#!/system/bin/sh
# Explicit one-shot control or GPU proof. All bytes must match the package.
set -u
umask 077
case "${1-}" in
  --memfd-control) expected=NATIVE_ONE_REGION_MEMFD_CONTROL_PASS ;;
  --gpu) expected=NATIVE_GPU_ONE_REGION_SCALAR_PASS ;;
  *) echo "Usage: $0 --memfd-control|--gpu" >&2; exit 2 ;;
esac
[ "$#" -eq 1 ] || exit 2
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
run="$root/results/one-region-$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir -p "$root/results" || exit 1
mkdir "$run" || exit 1
printf 'RESULT_DIRECTORY=%s\n' "$run"
if ! (cd "$root" && sha256sum -c SHA256SUMS) > "$run/integrity.txt" 2>&1; then
  cat "$run/integrity.txt"
  echo "PACKAGE_INTEGRITY=FAIL"
  exit 1
fi
{
  date -u +%Y-%m-%dT%H:%M:%SZ
  id
  id -Z
  getenforce
  uname -a
  printf 'mode=%s\npackage=%s\n' "$1" "$root"
} > "$run/context.txt" 2>&1
"$root/native-gpu-owner" "$1" "$root" < /dev/null > "$run/diagnostic.txt" 2>&1
status=$?
printf 'OWNER_EXIT=%s\n' "$status" > "$run/summary.txt"
grep -E '^(OWNER_|NATIVE_GPU_|NATIVE_MEMFD_|NATIVE_ONE_REGION_|RESULT=|native-gpu-one-region:)' \
  "$run/diagnostic.txt" >> "$run/summary.txt"
cat "$run/summary.txt"
if [ "$status" -ne 0 ] ||
   [ "$(grep -c '^OWNER_EVENT ' "$run/diagnostic.txt")" -ne 6 ] ||
   ! grep -qx "RESULT=$expected" "$run/diagnostic.txt" ||
   ! grep -qx 'NATIVE_GPU_GUEST_SVC_OK' "$run/diagnostic.txt" ||
   ! grep -q '^OWNER_TREE_CLOSED leader_reaped=1 .* ECHILD=1 group_signals=1$' "$run/diagnostic.txt"; then
  echo "ONE_REGION_RUNNER=FAIL"
  exit 1
fi
echo "ONE_REGION_RUNNER=PASS mode=$1"
