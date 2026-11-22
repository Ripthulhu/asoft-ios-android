# Diskless Darwin ramdisk capability probe

Two physical attempts observed a root Darwin shell. The
[second attempt](RESULT-02.md) identified the HFS root source as
`root_device` and obtained empty QMP block inventories before and after
guest observation. Four checked unmount paths failed the executable-file
test. The [first attempt](RESULT.md) is retained as historical evidence.

## First preparation on the phone

| Item | Value |
| --- | --- |
| Source | `/data/local/tmp/asoft-rd-source-01/probe_ios26_ramdisk.py` |
| Source SHA-256 | `1d979fd7a0fbba85d672131ebe0812cbb903840137765442f747c6a6c7d70a8c` |
| Work directory | `/data/local/tmp/asoft-rd-probe-01` |
| Trust cache | `ramdisk.tc`, 10,386 bytes |
| Trust cache SHA-256 | `d35c51f0a91f5a02b417dd037f435dd79a3fe1457b93499f8a7fecaaceffa78b` |
| Preparation receipt | `cache-result.json`, 437 bytes |

The shared-build checkpoint retained the shell ramdisk and the original
Apple ramdisk trust cache. The probe reconstructs the combined cache using
the pinned sysroot archive and the app's existing signing tool with the same
identifiers as the shell ramdisk builder. The result contains 360 Apple
entries and 111 added sysroot entries. A separate reconstruction on the Pixel
used the pinned `mktc.py` CLI and produced byte-identical output. The archive,
the cache and the temporary signed binaries are kept on the phone.

The phone passed five Bash mount-output fixtures, eight guest-observation
acceptance and refusal cases, and three simulated QMP block-state cases. The
launch arguments were checked against the actual frozen runner and qualified
runtime. The installed QEMU reports version 11.1.0 and advertises `-S`,
`-nodefaults` and `-nic none`. The first live observation and QMP replies are summarized in the physical result.

## Probe contract

The probe uses the original research kernel, SPTM, TXM, 38.4 MHz device tree
and native EL0 + kernel TCG runtime. It starts QEMU paused and requires empty
block devices and named block nodes before starting the guest. It checks them
again after the shell observation. QEMU receives the HFS shell ramdisk as
firmware input and no iOS disk image, overlay or backing chain.

The verified ramdisk builder starts interactive Bash on the console. The
probe uses the frozen console's one-time markers to collect real and effective
UID, executable-file checks for fixed utility paths, and the root row from
`/sbin/mount` invoked without arguments. The root row must identify the HFS
ramdisk at `/`. Utility presence is tested with executable-file predicates.
Mount and unmount functionality on Data require a separate later experiment.

The result requires native initialization, execution and final SVC evidence,
plus an acknowledged QMP stop and quit, exit zero and unforced child cleanup.
A memory refusal before creation of the run directory leaves this prepared
cache eligible for a fresh launch check. Preserve any created run directory.
Guest and QEMU logs stay on the phone.

## Continue from the physical results

Use a fresh work directory for any new probe and retain the completed runs,
sources, and cache receipts. Qualify the [unmount helper](helper/README.md)
on a disposable HFS volume before attaching a recovery image. Data still
needs journal replay and a new filesystem inspection. GPU completion and
APK readiness remain open.
