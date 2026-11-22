# Firstboot Python memfd recovery — memfd1

This staging directory contains a process-local compatibility adapter and a fresh, receipt-owned retry of the unchanged firstboot guard. The phone's existing Python exposes the kernel facility through libc but lacks three `os` attributes used by the frozen preparation source.

## Physical evidence reported by the root operator

The original guarded attempt `07-0001` finished before QEMU launch with `AttributeError: module 'os' has no attribute 'memfd_create'`. Its guard result remains INCOMPLETE, with bound inputs unchanged and no firstboot checkpoint. Its clean outer-owner exit and guard result are pinned separately:

| Retained artifact | SHA256 |
| --- | --- |
| Original guard result | `2a4b1ad20f478db58eb5ca7219789146b973f364cf4e7f079eb6acd4f5e7519d` |
| Original outer-owner exit | `c651a9fae9976e04eada79bc229604a9724ea4053723d6b05ee6c0df02ce28b1` |
| Frozen guard source | `8f98fafd603385b5d3aa20331acc7e536020b6ae136f8690bd190efbeb09845c` |

At 2026-11-22 12:13:07 UTC, the operator observed Python 3.14.8 without `os.memfd_create`, `os.MFD_CLOEXEC`, or `os.MFD_ALLOW_SEALING`; its Python `fcntl` seal constants and libc `memfd_create` symbol were present.

At 12:16:24 UTC, one invocation of the unchanged reviewed probe passed the exact relevant kernel sequence on one 4 KiB anonymous page: flags 3, CLOEXEC and non-inheritance, ftruncate, grow/shrink/seal seals 7, shared writable mapping and FD alias, EPERM for later growth/shrink, then mapping and FD closure. It launched no child or VM. The operator's exclusive metadata capture is:

`/data/local/tmp/pixel-gpu-transfer-sxtv33sh/python-memfd-smoke-memfd1.json`

Its SHA256 is `57d7239160422a858ed9882191c5012fd20a20d5b790f482be15013266f313bd`. The capture binds the exact reviewed 5,677-byte probe source SHA256 `069232bec27b8775499941bf52da9f4e076d8a8b3ee14171510691cbbf010225`. The retry consumes this receipt; it does not repeat the probe.

These observations establish the missing Python binding and the tested libc/kernel capability. They do not constitute a completed firstboot or GPU result.

## Adapter scope

`run_guard_memfd_adapter.py` requires the observed three attributes to be absent, then adds them only to its own Python process. The binding uses the exported libc symbol with the explicit ABI `int(const char *, unsigned int)` and errno preservation. It preserves the requested flags, rejects embedded NUL in the name before the call, and reproduces CPython's unsigned-int flag conversion. It has no raw-syscall or filesystem fallback.

The adapter reads and verifies the unchanged guard bytes, compiles those verified bytes with the original guard filename, and gives the guard its original-compatible `sys.argv`. The real outer command is independently recorded as Python `-I -B` executing the adapter. Actual interpreter flags are checked. The temporary attributes are removed in `finally`; separate adapter startup and exit receipts record the missing/installed names, source hashes, actual argv, accepted smoke, restoration and source equality.

The guard's existing session continues to describe its original two supervision hooks. The supplemental adapter receipts are therefore mandatory provenance for this retry. The original guard, runner, checkpoints, Python installation and failed attempt are not edited.

Primary sources used for the binding review:

- [AOSP bionic memfd prototype and API availability](https://android.googlesource.com/platform/bionic/+/417c3a197becc23316cb8db06229b010e8438009/libc/include/sys/mman.h).
- [AOSP Linux UAPI memfd flag definitions](https://android.googlesource.com/platform/bionic/+/refs/heads/main/libc/kernel/uapi/linux/memfd.h).
- [AOSP Linux UAPI seal definitions](https://android.googlesource.com/platform/bionic/+/0c56cbad119e167803bea4d6c0671517c9b7fb9c/libc/kernel/uapi/linux/fcntl.h).
- [CPython 3.14.8 memfd implementation](https://github.com/python/cpython/blob/v3.14.8/Modules/posixmodule.c) and [generated argument conversion](https://github.com/python/cpython/blob/v3.14.8/Modules/clinic/posixmodule.c.h).
- [Python ctypes ABI and errno documentation](https://docs.python.org/3/library/ctypes.html).

## Fresh paths and sequence

All transfer receipts are under `/data/local/tmp/pixel-gpu-transfer-sxtv33sh`. All writes reserve fresh names exclusively. An existing or interrupted artifact is retained and causes refusal; no helper overwrites it or automatically retries.

1. `04-install-memfd-adapter.command.txt` installs only the reviewed adapter source at `run-ios26-firstboot-memfd-adapter-memfd1.py`, with `ios26-firstboot-memfd-adapter-memfd1-install.json`.
2. `05-capture-memfd-preflight.command.txt` owns one foreground adapter child without `--execute`, captures the unchanged guard's read-only preflight, waits and reaps that direct child, and writes `ios26-firstboot-guard-preflight-memfd1.*` plus the adapter's `ios26-firstboot-memfd1-adapter-preflight.*` receipts. It leaves the fresh guard work absent. It verifies the old clean failure, exact retained stage-input metadata, absent old VM metadata and absent recorded owner/guard identities before and after capture.
3. The root operator observed the new adapter-bound preflight pass at 12:21:05 UTC: exit 0, reaped, no force/cleanup errors, adapter completed and restored, old 07-0001 preserved, seven checkpoints and fresh guard work absent. Its stdout is exactly 21,952 bytes with SHA256 `eda974e4e726b0164f8c5bbcda232c972db53622e22b1736f1091717b2e4713b`; the final retry-owner pin is grounded in this capture. A semantic preflight pass does not establish the current resource floors.
4. `06-install-firstboot-memfd-owner.command.txt` installs only the exact reviewed retry owner. `07-launch-firstboot-memfd-owner.command.txt` requests the authorized retry after its fresh gates. The fresh outer owner uses `ios26-firstboot-owner-memfd1`; the fresh guard work is `/data/local/tmp/pixel-firstboot-guard-e9cc754-memfd1`. It requires exactly the retained `07-0001`, then accepts only one new `07-0002`. The frozen runner selects and creates that attempt itself.
5. The detached launcher starts one reviewed owner with `start_new_session=True`, DEVNULL stdin, an exclusive wrapper log and a startup receipt containing PID/starttime/PGID/SID. It never waits for or signals a possibly launched owner after a receipt error. The owner is the adapter/guard's direct parent and owns its wait/cleanup.
6. `08-status-firstboot-memfd-owner.command.txt` provides the compact observation; `09-status-firstboot-memfd-owner-json.command.txt` provides full selected metadata. `status_firstboot_memfd_owner.py` reads bounded source/receipt/process metadata only. It never reads guest or serial logs. Completion requires the original accepted guard/checkpoint/session/observations evidence, all four current attempt metadata hashes, clean ownership receipts and absent recorded identities, plus the adapter/smoke/preserved-failure bindings.

The exact unchanged guard arguments inside the adapter are:

```text
--audit-work /data/local/tmp/pixel-audit-e9cc754
--auditor-dir /data/local/tmp/pixel-boot-checks-ebbc9c0/auditor
--runner-dir /data/local/tmp/pixel-prep-runner-f4d64db
--work /data/local/tmp/pixel-firstboot-guard-e9cc754-memfd1
```

Only the explicit execution invocation adds `--execute`.

## Ownership, resources and acceptance

Fresh execution still requires 3,840 MiB available RAM and 4,500,000,000 free bytes. The native VM deadline remains 3,600 seconds, with the original running memory, disk and log limits. The outer owner's 5,400-second envelope includes preflight and post-run evidence work; its direct-child TERM grace is 180 seconds, followed only if needed by killing and reaping that still-owned direct child. Any forced cleanup is INCOMPLETE and needs exact recorded-identity review.

Firstboot uses the original controlled QMP stop/quit sequence. Acceptance does not import the partition helper's natural-exit or done-code conditions. It retains native initialization/execution, milestone/settling, shell-sync, clean QEMU cleanup, the guard's failed-I/O counter checks and the original checkpoint chain. The old seven checkpoints and failed attempt remain preserved.

Even an accepted guarded firstboot keeps `boot_complete`, `gpu_path_complete` and `app_gate_changed` false. The separate saved-filesystem/journal inspection remains the mandatory next gate before Linux disk mutation.

## Local review and validation

The original 069232be probe and its first three transports remain unchanged. The adapter and capture received independent source review. A focused fake-libc check verified default/explicit flag handling, unsigned conversion, NUL rejection, ABI declarations and errno propagation without making a real libc call, allocating an FD or launching a VM; see `adapter-local-validation.json`. Transport validation is limited to syntax, exact payload roundtrips and argv integrity. Core owner changes are reviewable in `owner-vs-original.diff`.

No phone/browser action, source installation, real probe, VM job or main-repository edit was performed by this helper author. Physical observations and execution belong to the root operator.
