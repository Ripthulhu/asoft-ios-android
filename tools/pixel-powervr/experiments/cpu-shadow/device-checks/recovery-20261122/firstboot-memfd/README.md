# Python memfd compatibility recovery

Latest physical readback: **2026-11-22 12:36:31 UTC**. Retry **`07-0002`**
reached native execution and answered the guest shell-sync request, then its
post-stop counter validator rejected the backend identification. The guard and
outer owner exited **2**; QEMU exited **0**, and all three recorded process
identities are absent. The guard result remains **`INCOMPLETE`**, with no
accepted firstboot checkpoint. The [final observation](retry-counter-rejected-123046.json)
and [original screenshot](retry-counter-rejected-123046.jpg) preserve this boundary.

The first firstboot execution stopped before VM launch because the phone's
Python 3.14.8 lacks `os.memfd_create`, `os.MFD_CLOEXEC` and
`os.MFD_ALLOW_SEALING`. The original [failed owner and attempt](../firstboot-owner/README.md)
are preserved; their unchanged bound inputs and missing firstboot checkpoint
were verified. This is separate from RAM availability: the outer owner's
launch resource checks passed, and no memory reclamation was needed.

The exact [reviewed implementation package](package/README.md), including
all source, command transports, the original author README and its matching
manifest, is retained in `package/`. The physical observations below are
separate from that immutable authored package.

## Physical libc smoke test

At **2026-11-22 12:16:24 UTC**, the reviewed probe passed against the phone's
existing Bionic libc symbol. It created one **4,096-byte anonymous buffer**
with flags **3**, checked close-on-exec/noninheritability, installed and read
back seals **7**, checked a writable shared mapping and fd alias, verified
that sealed resize attempts returned EPERM, and closed the mapping and fd.
It started no child or VM, patched no Python module and changed no system
policy. The EPERM values here are the expected seal behavior of this probe's
own buffer, unrelated to the host integration check's self-read blocker.

[The observation](smoke-observation-121624.json) is a selected screenshot
transcription. The complete raw receipt is on the phone at:

```text
/data/local/tmp/pixel-gpu-transfer-sxtv33sh/python-memfd-smoke-memfd1.json
```

Its observed SHA-256 is
`57d7239160422a858ed9882191c5012fd20a20d5b790f482be15013266f313bd`.
The reviewed probe is 5,677 bytes, SHA-256
`069232bec27b8775499941bf52da9f4e076d8a8b3ee14171510691cbbf010225`.

The root agent executed [capture-memfd-smoke.command.txt](package/capture-memfd-smoke.command.txt),
whose source is [capture_memfd_smoke.py](package/capture_memfd_smoke.py).
It verifies and loads the exact reviewed probe under
a non-main module name, calls `probe(True)` once, and exclusively saves the
unaltered probe object with source/invocation metadata. The wrapper fsyncs the
receipt and parent directory and prints its readback SHA. The probe's
`persistent_files_created=false` describes the probe; the separate capture
correctly records `receipt_file_created=true`.

The three numbered probe transports are retained as reviewed alternatives;
they were not executed for this observation. No duplicate smoke is required.
Root's capture/source and exact transport round-trip were independently
reviewed after execution with no finding. The source-authoring/review agents
performed no phone actions.

## Adapter installation and accepted preflight

The root agent installed the reviewed process-local adapter at **12:19:39 UTC**.
The [installation transcription](adapter-installed-121939.json) records exactly
**9,097 bytes**, SHA-256
`e981d6d561b821641a6993b2aa96b84fa63776ccd1a7bc8cb314d1261ae899a8`.
Installation started no execution. The adapter supplies only the missing
`os.memfd_create`, `os.MFD_CLOEXEC=1` and `os.MFD_ALLOW_SEALING=2` in its own
process, calls the existing libc function, and restores those attributes on
exit. The staged guard, four frozen preparation files and system Python
installation remain unchanged.

The new foreground read-only preflight started at **12:20:00 UTC**. By the
displayed **12:21:05 UTC** after-resource observation it reported
**`PREFLIGHT_READY`**, accepted, exit zero, reaped, no force and no cleanup
errors. The adapter completed and restored its attributes; the seven
checkpoints and preserved `07-0001` evidence were accepted, inputs were
unchanged, and the fresh guard work remained absent. Its output was
**21,952 bytes**, SHA-256
`eda974e4e726b0164f8c5bbcda232c972db53622e22b1736f1091717b2e4713b`.
The [preflight transcription](preflight-passed-122105.json) distinguishes the
displayed resource timestamp from the exact exit-receipt finish time, which
was not displayed.

## Retry installation, launch and native execution

The new outer owner was [installed at 12:24:11 UTC](retry-owner-installed-122411.json):
**24,980 bytes**, SHA-256
`771742c200d2d64c54cdd18db7bcd1cba4fc242999f16376531e0d9803f9a3d5`.
The [12:24:27 UTC conditions](retry-conditions-122427.json) reported
4,008,752 KiB available memory (**3,914.797 MiB**), charging battery capacity
74, raw battery temperature 311 and thermal status zero. No RAM reclamation
was performed.

The [12:24:54 UTC launch](retry-owner-launched-122454.json) consumed the accepted
preflight and real libc smoke receipt. Available memory was **4,137,132,032
bytes (3,945.477 MiB)**, above the unchanged **3,840 MiB** fresh-launch floor;
free space was 74,310,766,592 bytes. The wrapper ran in its own process group
and session. The [12:25:41 UTC observation](retry-input-check-122541.json) found
the owner and adapter/guard live during input validation, with matching
adapter source and smoke pins and no VM attempt recorded yet.

At **12:29:44 UTC**, the [native-running observation](retry-native-running-122944.json)
matched all three live identities and the new attempt **`07-0002`**:

| Process | PID | Start ticks | Observed state |
|---|---:|---:|---|
| Outer owner | 897 | 7531924 | Sleeping |
| Adapter and guard | 899 | 7531951 | Sleeping |
| Native QEMU | 2037 | 7545319 | Sleeping |

The VM sample at **150.88452436000807 seconds** had native initialization and
execution, with milestone and settled flags true. Sync and final cleanup
evidence were still pending. Available memory was **2,544,607,232 bytes
(2,426.727 MiB)**, above the unchanged **512 MiB** running floor. The fresh-launch
floor flag was false with this VM already allocated; the running floor remained
the applicable active-VM bound. This historical observation established
progress past the Python memfd failure, without accepting a firstboot result.

## Counter validation stopped acceptance

The [12:30:46 UTC observation](retry-counter-rejected-123046.json) found the
same owner, guard and QEMU identities absent. The final VM sample covered
**181.03553269000258 seconds** and had native initialization, execution and
svc-final witnesses, plus milestone, settled and guest-sync flags all true.
QEMU exited zero, `ECHILD` and quit acknowledgment were true, and no forced
QEMU or descendant cleanup was reported. The outer owner reaped its guard
with exit 2, without force or outer cleanup errors.

The retained counter event has `stop_acknowledged=true` and the error:

```text
ValueError: post-stop stats must identify exactly the root backend
```

The validator therefore did not establish the zero-failure counter condition.
`failed_io_counters_zero=false` is an unestablished predicate here; the compact
observation does not report a nonzero numeric I/O error count. The VM record
still has `stop_flushed=false` and nonempty cleanup errors, so its cleanup
contract and the guard checkpoint remain unaccepted. The guard reports
unchanged bound inputs and no firstboot checkpoint.

The adapter restored its Python attributes and reported unchanged sources.
Its `adapter_completed=false` accompanies the guard's exit 2. The separate
completion-dependent receipt and preserved-failure predicates remain false
because no accepted outer result exists. Both **`07-0001`** and **`07-0002`**
remain preserved. No accepted firstboot or saved-firstboot inspection is claimed.

## Saved counter response and receipt identities

The bounded [12:34:28 UTC readback](saved-counter-projection-123428.json)
reported two top-level `query-blockstats` rows, **`root`** and **`floppy0`**,
plus three parent/backing nodes. Every one of the five nodes reported exact
integer-zero `failed_wr_operations` and `failed_flush_operations` values.
The literal `account_failed` flags were true for the two top-level rows and
false for the three nested nodes; those flag values are retained without
interpreting them as disabling failed-operation counters.

The original validator rejected the two-row inventory before establishing
its acceptance predicate. The saved event contains no post-stop `query-block`
reply that would prove `floppy0` had no inserted medium. The zero-valued
counters therefore do not retroactively accept `07-0002`, complete its
cleanup contract or create a firstboot checkpoint.

The split readback also resolved the digest that was visually ambiguous in
the earlier final screenshot. The guard result is **24,006 bytes**, SHA-256
`f618a29bc550d6155e78ed3757e3ce715b6c75b1fcf1745c6d6b55944b6a345a`.
The failure transcription links this later confirmation explicitly.
The [12:36:31 UTC receipt readback](retry-receipt-pins-123631.json) independently
confirmed this digest and pinned seven retained files: owner exit, guard
result and observations, adapter owner and exit, and attempt launch and VM
result. The outer exit receipt is **805 bytes**, SHA-256
`701461a97e794ae669cadda23cbb8a475adb974556d0c4e5cf6c552876a629f5`.

Exact [counter reader](diagnostics/read_saved_counter_events.py),
[compact projection](diagnostics/read_saved_counter_events_projected.py) and
[receipt-pins reader](diagnostics/read_retry_receipt_pins.py) sources, command
transports and manifests are retained under `diagnostics/`. They read bounded
saved metadata only, print no guest log, and issue no live QMP or process
operation. The immutable authored adapter package remains separate.

## Recovery from this boundary

The physical JSON records are selected screenshot transcriptions, not raw
phone receipt exports. The [transcription review](physical-transcriptions-review.json)
binds each record to its original screenshot. Complete guard, owner and
attempt receipts remain on the phone; guest serial logs and Apple binaries
have not been exported.

Use the retained [compact status command](package/08-status-firstboot-memfd-owner.command.txt)
or [selected JSON status command](package/09-status-firstboot-memfd-owner-json.command.txt)
to recheck the recorded boundary. The relevant phone paths are:

| Evidence | Phone path |
|---|---|
| Retry outer owner | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-firstboot-owner-memfd1` |
| Retry guard work | `/data/local/tmp/pixel-firstboot-guard-e9cc754-memfd1` |
| Preserved native attempt | `/data/local/tmp/pixel-prep-e9cc754/attempts/07-0002` |

Preserve the existing source, installation, preflight, launch and attempt
artifacts; do not rerun their exclusive installers or launchers. Any future
correction must use a separately reviewed guard version and a fresh attempt,
with explicit post-stop backend and medium evidence. The existing staged
guard and both failed attempts remain unchanged. Keep the 3 GiB guest, both
memory floors, native cleanup and checkpoint requirements. The [saved-firstboot inspector](../../../IOS26-SAVED-FIRSTBOOT-INSPECTION.md)
remains a required later gate and has not run at this boundary.

## Primary source basis

Bionic declares `memfd_create(const char *, unsigned)` from API 30 and
implements it as a libc syscall stub. Android's Linux UAPI declares
`MFD_CLOEXEC=1` and `MFD_ALLOW_SEALING=2`. CPython exposes platform-dependent
bindings conditionally; a missing Python attribute alone is not a kernel-call
failure. The reason this exact Python build omitted it has not been proved.

- https://android.googlesource.com/platform/bionic/+/master/libc/include/sys/mman.h
- https://android.googlesource.com/platform/bionic/+/master/libc/SYSCALLS.TXT
- https://android.googlesource.com/platform/bionic/+/refs/heads/main/libc/kernel/uapi/linux/memfd.h
- https://docs.python.org/3/library/os.html#os.memfd_create
