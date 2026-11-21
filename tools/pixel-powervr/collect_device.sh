#!/system/bin/sh
# Read-only diagnostics. This script does not change SELinux, permissions,
# properties, kernel parameters, modules, or the installed iOS application.
set -u

section() { printf '\n=== %s ===\n' "$1"; }
section 'Execution context'
id
cat /proc/self/attr/current 2>/dev/null
getenforce 2>/dev/null

section 'Phone and build'
for property in ro.product.manufacturer ro.product.model ro.product.device \
    ro.soc.manufacturer ro.soc.model ro.build.version.release \
    ro.build.version.sdk ro.build.version.security_patch ro.build.id \
    ro.hardware.vulkan; do
    printf '%s: %s\n' "$property" "$(getprop "$property")"
done
printf 'kernel: '; uname -r
printf 'architecture: '; uname -m
printf 'host_page_size: '; getconf PAGE_SIZE 2>/dev/null

section 'Memory exporter nodes'
for node in /dev/udmabuf /sys/class/misc/udmabuf/dev; do
    if [ -e "$node" ]; then
        ls -lZ "$node" 2>/dev/null || ls -l "$node"
    else
        printf 'absent: %s\n' "$node"
    fi
done
if [ -r /sys/class/misc/udmabuf/dev ]; then
    printf 'registered_udmabuf_device: '
    cat /sys/class/misc/udmabuf/dev
fi
if [ -d /dev/dma_heap ]; then
    ls -lZ /dev/dma_heap 2>/dev/null || ls -l /dev/dma_heap
fi
for parameter in /sys/module/udmabuf/parameters/*; do
    [ -r "$parameter" ] || continue
    printf '%s: ' "$parameter"
    cat "$parameter"
done

section 'Running kernel configuration'
if [ -r /proc/config.gz ]; then
    zcat /proc/config.gz 2>/dev/null | grep -E \
        '^(CONFIG_(UDMABUF|DMA_SHARED_BUFFER|DMABUF_HEAPS.*|MEMFD_CREATE|SHMEM|TMPFS|MODULES|MODULE_SIG.*|SECURITY_SELINUX|KSU.*)=|# CONFIG_(UDMABUF|DMABUF_HEAPS.*|MEMFD_CREATE|MODULES|MODULE_SIG_FORCE) is not set)'
else
    printf 'unavailable: /proc/config.gz is absent or unreadable in this context\n'
fi

if [ "${1:-}" = '--gpu' ]; then
    section 'Android Vulkan driver report'
    cmd gpu vkjson 2>&1
fi
exit 0
