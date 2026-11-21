#!/system/bin/sh
set -eu
cd "$(dirname "$0")"
sha256sum -c PARTS-SHA256SUMS
if [ -e pixel-powervr-runtime-probe.apk ]; then
    sha256sum -c APK-SHA256SUMS
    exit 0
fi
assembly_tmp=$(mktemp -d ./runtime-app-assemble-XXXXXX)
trap 'rm -rf "$assembly_tmp"' EXIT HUP INT TERM
cat payload/runtime-probe.apk.part000 payload/runtime-probe.apk.part001 payload/runtime-probe.apk.part002 payload/runtime-probe.apk.part003 payload/runtime-probe.apk.part004 payload/runtime-probe.apk.part005 payload/runtime-probe.apk.part006 payload/runtime-probe.apk.part007 payload/runtime-probe.apk.part008 payload/runtime-probe.apk.part009 payload/runtime-probe.apk.part010 payload/runtime-probe.apk.part011 payload/runtime-probe.apk.part012 payload/runtime-probe.apk.part013 payload/runtime-probe.apk.part014 payload/runtime-probe.apk.part015 > "$assembly_tmp/pixel-powervr-runtime-probe.apk"
cp APK-SHA256SUMS "$assembly_tmp/APK-SHA256SUMS"
(cd "$assembly_tmp" && sha256sum -c APK-SHA256SUMS)
mv "$assembly_tmp/pixel-powervr-runtime-probe.apk" ./pixel-powervr-runtime-probe.apk
printf '%s\n' 'Verified APK reconstructed; no package was installed or launched.'
