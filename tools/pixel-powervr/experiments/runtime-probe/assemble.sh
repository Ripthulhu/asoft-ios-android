#!/system/bin/sh
# Local-only reconstruction; run from Android sh or from a Linux shell.
set -eu
cd "$(dirname "$0")"
sha256sum -c PARTS-SHA256SUMS
if [ -e pixel_runtime_probe ] || [ -e pixel_runtime_probe.gz ]; then
    sha256sum -c OUTPUT-SHA256SUMS
    printf '%s\n' 'Existing reconstructed outputs verified.'
    exit 0
fi
assembly_tmp=$(mktemp -d ./runtime-assemble-XXXXXX)
trap 'rm -rf "$assembly_tmp"' EXIT HUP INT TERM
cat payload/pixel_runtime_probe.gz.part000 \
    payload/pixel_runtime_probe.gz.part001 \
    payload/pixel_runtime_probe.gz.part002 \
    payload/pixel_runtime_probe.gz.part003 \
    payload/pixel_runtime_probe.gz.part004 \
    payload/pixel_runtime_probe.gz.part005 \
    payload/pixel_runtime_probe.gz.part006 \
    payload/pixel_runtime_probe.gz.part007 \
    payload/pixel_runtime_probe.gz.part008 \
    payload/pixel_runtime_probe.gz.part009 \
    payload/pixel_runtime_probe.gz.part010 \
    payload/pixel_runtime_probe.gz.part011 \
    payload/pixel_runtime_probe.gz.part012 \
    payload/pixel_runtime_probe.gz.part013 \
    payload/pixel_runtime_probe.gz.part014 \
    payload/pixel_runtime_probe.gz.part015 > "$assembly_tmp/pixel_runtime_probe.gz"
gzip -dc "$assembly_tmp/pixel_runtime_probe.gz" > "$assembly_tmp/pixel_runtime_probe"
cp OUTPUT-SHA256SUMS "$assembly_tmp/OUTPUT-SHA256SUMS"
(cd "$assembly_tmp" && sha256sum -c OUTPUT-SHA256SUMS)
chmod 755 "$assembly_tmp/pixel_runtime_probe"
mv "$assembly_tmp/pixel_runtime_probe.gz" ./pixel_runtime_probe.gz
mv "$assembly_tmp/pixel_runtime_probe" ./pixel_runtime_probe
printf '%s\n' 'Runtime probe reconstructed and verified; no probe was executed.'
