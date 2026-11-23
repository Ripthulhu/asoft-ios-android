#!/usr/bin/env bash
# Reconstruct the Pixel core-run source, then add the linear XR renderer patches.
set -euo pipefail

patches=$(realpath "$1")
workspace=$(realpath "$2")
qemu="$workspace/qemu-pixel-android-build"
reims="$workspace/reims-pixel-android-link"
renderer="$workspace/metal2vulkan-tile-runtime"
recipe="$workspace/qemu26-build-reconstruction"

checkout() {
    local target="$1" repo="$2" revision="$3" tree="$4"
    git init --quiet "$target"
    git -C "$target" fetch --quiet --depth=1 "https://github.com/$repo.git" "$revision"
    git -C "$target" checkout --quiet --detach FETCH_HEAD
    require_tree "$target" "$tree"
}

require_tree() {
    local actual
    actual=$(git -C "$1" write-tree)
    if [[ "$actual" != "$2" ]]; then
        printf 'Expected tree %s, found %s in %s\n' "$2" "$actual" "$1" >&2
        return 1
    fi
}

apply_series() {
    local target="$1" manifest="$2" folder
    folder=$(dirname "$manifest")
    python3 - "$manifest" <<'PY' | while read -r hash file tree; do
import json
import sys

with open(sys.argv[1]) as manifest:
    for patch in json.load(manifest)["patches"]:
        print(patch["sha256"], patch["path"], patch.get("reconstructed_tree", patch.get("tree", "-")))
PY
        printf '%s  %s\n' "$hash" "$folder/$file" | sha256sum -c
        git -C "$target" apply --index "$folder/$file"
        if [[ "$tree" != "-" ]]; then
            require_tree "$target" "$tree"
        fi
    done
}

commit_tree() {
    git -C "$1" -c user.name='Pixel build' -c user.email='pixel-build@users.noreply.github.com' \
        commit --quiet -m "$2"
}

(cd "$patches/cpu-shadow" && sha256sum -c SHA256SUMS)
checkout "$renderer" alpersamur3/metal2vulkan 5951098336923a231a011578d8722449a3981034 6cba63e44790e0591eeab6c739fb313806a07dbe
apply_series "$renderer" "$patches/metal2vulkan-series.json"
require_tree "$renderer" 9fe786a921829ccdb51b2d977c0dbf30f7173962
(cd "$patches/producer-adoption" && sha256sum -c SHA256SUMS)
git -C "$renderer" apply --index "$patches/producer-adoption/0011-Retain-adopted-Vulkan-backing-with-explicit-address-placement.patch"
require_tree "$renderer" 1ee7add340efbe6da12d9e16e29dfe60ed5daff9
git -C "$renderer" apply --index "$patches/cpu-shadow/metal2vulkan/0001-canonical-paged-cpu-shadow-runtime.patch"
require_tree "$renderer" 1b8c0eff2356c3a05cc372b6ea25e74cbdeff8d0
git -C "$renderer" apply --index "$patches/pixel10-xr/0001-linear-xr-shadow-store.patch"
git -C "$renderer" apply --index "$patches/pixel10-xr/0002-use-xr-tile-shadow.patch"
git -C "$renderer" apply --index "$patches/pixel10-xr/0003-capture-tile-helper-refusal.patch"
git -C "$renderer" apply --index "$patches/pixel10-xr/0004-guard-tile-fetch-discards.patch"
commit_tree "$renderer" "Reconstruct the Pixel XR renderer"

checkout "$reims" alpersamur3/reims-vgpu 3e0467e64b4c21b6087ae3589388fec5154fb0cb b765da6439d7b080a580046871d94803a0c8f767
apply_series "$reims" "$patches/reims-series.json"
require_tree "$reims" f94e8a04f9e1c461e5db1aaa4c4935135edc4cbe
(cd "$patches/reims-producer" && sha256sum -c SHA256SUMS)
git -C "$reims" apply --index "$patches/reims-producer/0012-Add-explicit-cached-producer-memory-ownership.patch"
require_tree "$reims" 7ec29658bf455090d881b8ef055fdf00394e61b3
apply_series "$reims" "$patches/reims-host-validation/series.json"
require_tree "$reims" acf9ad9a46892d9833d851cd23cf8d2e357e90d6
git -C "$reims" apply --index "$patches/cpu-shadow/reims/0001-ordinary-file-cpu-shadow-integration.patch"
require_tree "$reims" 67f1860dc72f8cffff6bc6a79a9f5919be3bcc88
(cd "$patches/cpu-shadow-capabilities" && printf '%s  %s\n' \
    2ddf82636b8005bc8aa4cf96f8ff3251d359ef3f4a55208ce2d304643b9bc065 \
    reims/0001-enable-cpu-shadow-resource-capabilities.patch | sha256sum -c)
git -C "$reims" apply --index "$patches/cpu-shadow-capabilities/reims/0001-enable-cpu-shadow-resource-capabilities.patch"
require_tree "$reims" c191491d2ca8a1224d0f55bd14ecec4fcdf170da
commit_tree "$reims" "Reconstruct the Pixel core-run reims source"
git -C "$reims" apply "$recipe/provenance/reims-path-override.patch"

checkout "$qemu" alpersamur3/qemu-sptm 7a900afb62ddf94713e38ac5a4aafe1d42c9efa8 feb320cd8f7bc4846e6160981b6b85bf0c2f1c3b
git -C "$qemu" apply --index "$patches/cpu-shadow/qemu/0001-native-el0-and-cpu-shadow-integration.patch"
require_tree "$qemu" d1def5a49eaec302e46d8fa28aeaf5a227d02ecb
commit_tree "$qemu" "Reconstruct the Pixel core-run QEMU source"
git -C "$qemu" apply --reverse --check "$recipe/provenance/qemu-android-build.patch"
keycodes="$qemu/subprojects/keycodemapdb"
git init --quiet "$keycodes"
git -C "$keycodes" fetch --quiet --depth=1 https://github.com/qemu/keycodemapdb.git f5772a62ec52591ff6870b7e8ef32482371f22c6
git -C "$keycodes" checkout --quiet --detach FETCH_HEAD
