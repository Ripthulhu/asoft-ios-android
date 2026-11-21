# Frozen producer probe v1

This directory preserves the exact source, Android executable and build-time
metadata for the first successful opaque-FD CPU/GPU experiment on the Pixel.
The binary SHA-256 is
`0daa83ea361129d70cc586cbca58401b2614e907f55383fbdf64ee7258a183d7`.

The metadata's statement that phone execution was not performed by the build
is historical provenance. The subsequent actual device result is recorded in
the [parent test report](../README.md#vulkan-owned-shared-allocation-pass).
The current maintained v2 source and its more extensive, phase-specific
experiment are described in [OPAQUE-FD.md](../../../OPAQUE-FD.md).

This snapshot is MIT-licensed, like the original diagnostic kit. It is not
selected by the original ADB runner or by the diagnostic APK.
