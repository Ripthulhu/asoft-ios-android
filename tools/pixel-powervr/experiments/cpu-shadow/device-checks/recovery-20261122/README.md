# Recovery after the November 22 chat limit

The new session recovered remote `eca3cb6c9f07e5a865ba255f23fca56bdfdc5511`
on `pixel10-gpu-integration`. The previous transient host checkout and
toolchains were absent. The phone's independent preparation owner survived.

## Physical observations

The installed status observer ran again at **10:11:59 UTC**. Wrapper
27799/start 5485624, runner 27801/start 5485639 and native QEMU 28210/start
5491577 still matched their saved identities. Five of seven preparation
checkpoints were present, through `ios26-decrypt`. Retry `05-0002` remained
active with its original 21,600-second bound; the owner had no exit receipt.
The latest VM record remained `INCOMPLETE`, with native initialization,
execution and sampler witnesses, no error field and no final witness or
cleanup. This is an observation of an unfinished run.

A later [owner observation](owner-observation.json) at **10:30:53 UTC** again
matched all three process identities, with five checkpoints, no exit receipt
and no fresh VM error or final witness. The container was 16,265,052,160 bytes.
The [next full owner observation](owner-observation-104648.json), at
**10:46:48 UTC**, again matched all three identities: five checkpoints, missing
exit receipt, no fresh VM error or final witness, and a 17,379,033,088-byte
container. Available memory was 2,077,093,888 bytes and work space had
93,358,809,088 free bytes. The separate top-level result still named the old
failed attempt; it was not interpreted as a new retry failure.
At **10:57:29 UTC**, the [next full owner observation](owner-observation-105729.json)
again matched all three identities, with five checkpoints, no exit receipt,
no fresh VM error and no final witness. The container was 18,316,001,280 bytes;
available memory was 2,141,052,928 bytes and free work space 92,422,381,568 bytes.

The bounded progress observations are in [observations.json](observations.json):

| Phone time (UTC) | Container bytes | Guest occupied space | Copy estimate | Latest native sample |
|---|---:|---:|---:|---|
| 10:16:39 | 15,795,552,256 | 14.7 GiB | 78% | 12,690 s; 17,789 ms native; 44,699 entries |
| 10:23:59 | 15,955,132,416 | 14.8 GiB | 78% | 13,140 s; 10,507 ms native; 21,216 entries |
| 10:39:06 | 17,186,226,176 | 16.0 GiB | 84% | 14,040 s; 15,047 ms native; 30,542 entries |
| 10:57:08 | 18,315,935,744 | 17.0 GiB | 90% | 15,120 s; 13,089 ms native; 32,904 entries |

Container size and process CPU counters advanced. Newer sampler windows
contained native execution. Together these show continued work during the
observed interval. Sample milliseconds and entry counts are window values,
not cumulative counters to subtract. The latest observed copy phase was
the main OS, after SystemOS and AppOS. None of these observations found the
trust-cache phase, output-size protocol, done protocol or final native
counters in its bounded tails.

The percentage comes from the pinned `copy_watch` wrapper: guest `df` used
space against an estimated 18 GiB target, clamped to 95%. Its displayed
"GB" values are GiB rounded to 0.1. Neither the percentage nor the Android
container length is an exact copied-byte count or a completion guarantee.

[observe_rootfs.py](observe_rootfs.py) is the exact authored source executed
through Python `-I -B -c` for those four observations. It was not installed on
the phone. It reads at most 256 KiB from each existing log, exports only
recognized numeric/protocol fields, verifies the recorded process start
ticks before reading counters, and performs no writes, signals, QMP calls
or VM launches. Its SHA-256 is
`4db3694b5ebd6c14d99c200ab28aeb4fdf7020f54b16bde0553e251984aff261`.

These selected values were transcribed from terminal screenshots. They are
not claimed as an exact-byte export of stdout or the changing phone files.
The complete serial and QEMU logs remain on the phone. An attempted metadata
download through Tango did not return an artifact to the agent, so it is
not used as evidence.

## Rootfs completion and partition start

The [11:10:34 UTC owner observation](owner-observation-111034.json) showed the
preparation checkpoint prefix advance to **6/7**, latest `ios26-rootfs`.
Attempt `05-0002` had `VM_OBSERVATION_COMPLETE`, all four native witness flags,
no VM error field and completed cleanup; its original QEMU process was absent.
Its final recorded VM timestamp was 11:05:37 UTC. These selected observations
establish that the existing runner accepted the rootfs checkpoint; they are
not an independent export or hash audit of the generated image.

The same wrapper and runner were still alive and had launched the fresh
partition attempt **`06-0001`** at **11:05:58 UTC**. Its QEMU identity was
26348/start 7058379, with the original 2,048 MiB, four vCPUs and its own
21,600-second limit. Its 11:10:30 UTC VM sample showed initialization,
execution and sampler witnesses, no error field, and no final witness or
cleanup yet. The owner had no exit receipt. Available memory was
1,922,732,032 bytes and work space had 74,324,398,080 free bytes.

The old `05-0001` RuntimeError in the top-level result remained stale. It was
not attributed to either the completed rootfs retry or the current partition
helper. No partition completion, physical audit or actual iOS boot is claimed.

## Preparation completion

The [11:22:26 UTC observation](owner-observation-112226.json) found **all seven
preparation checkpoints**, ending at `ios26-partition`. The original owner
recorded exit zero at **11:18:02 UTC**, with the runner reaped, no forced runner,
no wrapper error and no cleanup errors. Its wrapper and runner identities,
and both helper QEMU identities, were absent.

Partition attempt `06-0001` had `VM_OBSERVATION_COMPLETE`, all four native
witness flags, no error field and completed cleanup; its final VM timestamp
was **11:17:42 UTC**. The partition container was 18,330,943,488 bytes, with
18,348,912,640 allocated filesystem bytes. The preparation result now read
`PREPARATION_CHECKPOINT`, selected `ios26-partition`, named `06-0001` and had
no error. Available memory was 3,876,208,640 bytes and work space had
74,050,465,792 free bytes. These are selected screenshot transcriptions; the
subsequent audit preflight must still validate full metadata and disk hashes.

## Accepted audit preflight

A fresh reviewed receipt owner was installed after preparation exited. Its
separate read-only preflight completed successfully, observed at **11:30:18 UTC**:
`PREFLIGHT_READY`, all seven checkpoint names, accepted zero exits, clean reap,
matching output hash and absent wrapper/auditor identities. The audit work
directory was still absent. The [audit owner record](audit-owner/README.md)
retains exact source/transport identities and selected physical observations.
No audit VM or iOS boot had run at that preflight boundary.

## Audit execution started

The separate execution launcher consumed the accepted preflight and finished
at **11:35:34 UTC**. The [11:36:12 UTC observation](audit-owner/execution-observation-113612.json)
matched wrapper 8032/start 7235994, auditor 8034/start 7236028 and QEMU
8247/start 7238076. The new audit work directory exists. Its first ten-second
VM sample had initialization, with no native execution/final witness or audit
verdict yet. The [audit owner record](audit-owner/README.md) contains the
process recovery procedure and exact reviewed sources.

## Audit completed

At **11:38:42 UTC**, the [audit observation](audit-owner/execution-observation-113842.json)
reported `PARTITION_AUDIT_COMPLETE_ACCEPTED`. Both unfiltered filesystem
checks returned `PASSED:0`, the disk and preparation records remained
unchanged, native initialization/execution/final witnesses were present, and
the helper exited naturally with clean reap. Owner and auditor exited zero,
accepted result and session hashes matched, and all recorded process
identities were absent. This completes the separate partition audit. It does
not establish an iOS setup boot or final native GPU/UI qualification.

## Firstboot preflight and resource boundary

The [firstboot guard preflight](firstboot-preflight/README.md) subsequently
returned `PREFLIGHT_READY`, accepted with exit zero, clean reap and unchanged
guard/audit-result identities. The guard work directory remained absent.
At **11:47:11 UTC**, MemAvailable was 3,940,978,688 bytes (3,758.41 MiB),
85,553,152 bytes below the unchanged 3,840 MiB firstboot floor. Disk space
met its separate requirement. No firstboot was requested or launched.

## Fresh memory and physical conditions

After the user requested safe RAM reclamation and confirmed the phone's 16 GB
configuration, fresh read-only observations found **4,409.41 MiB** available
at 11:54:20 UTC and **4,239.01 MiB** at 11:58:19 UTC. Both exceeded the unchanged
3,840 MiB firstboot launch floor. No memory reclamation, app trim or process
termination was needed or performed. The follow-up retained battery, thermal,
pressure and space observations and found the guard work absent. See the
[memory record](memory/README.md) for exact source, commands and screenshots.

## Detached firstboot execution started

The reviewed [firstboot outer owner](firstboot-owner/README.md) was installed
at **12:06:06 UTC** and launched at **12:06:51 UTC** after fresh resource and physical checks.
Wrapper 26052/start 7423681 and guard 26054/start 7423704 were live in the
12:07:17 and 12:08:38 UTC observations. The later sample found the guard session
equal to the accepted preflight; no VM attempt was yet observed. This is an
active input-validation boundary, not an accepted iOS setup boot. Source and
transfer pins, original screenshots and selected metadata are retained.

At **12:10:21 UTC**, the next observation found the wrapper and guard absent,
cleanly exited with status 2. The firstboot guard had stopped at **12:09:06 UTC**
because Python lacked `os.memfd_create`, before any QEMU launch. Bound inputs
were unchanged; no firstboot checkpoint exists. Attempt 07-0001 and its fresh
overlay/boot-input copies remain preserved. The following [compatibility
check](firstboot-memfd/README.md) passed at **12:16:24 UTC** against the existing
libc symbol, using one anonymous page, exact flags/seals and complete cleanup.
No RAM reclamation or threshold change was required.

## Adapter retry reached native execution and stopped at counter validation

The reviewed process-local adapter was installed at **12:19:39 UTC** and its
new read-only preflight was accepted by the **12:21:05 UTC** observation:
exit zero, clean reap, restored Python attributes, seven checkpoints,
unchanged inputs and fresh guard work still absent. The new outer owner was
installed at **12:24:11 UTC** and launched at **12:24:54 UTC** with sufficient
fresh memory and space. The [memfd recovery record](firstboot-memfd/README.md)
retains the exact immutable package, actual installation/preflight/launch
observations and original screenshots. The original failed attempt `07-0001`
was preserved.

At **12:29:44 UTC**, the [native-running observation](firstboot-memfd/retry-native-running-122944.json)
found attempt **`07-0002`** running with wrapper **897/start 7531924**, guard
**899/start 7531951** and QEMU **2037/start 7545319**. Its 150.8845-second VM
sample showed native initialization/execution and milestone/settled witnesses.
Available memory was 2,544,607,232 bytes, above the unchanged 512 MiB running
floor. Completion receipts were still pending.

The [12:30:46 UTC observation](firstboot-memfd/retry-counter-rejected-123046.json)
then found all three recorded identities absent. Native initialization,
execution, final, milestone, settled and guest-sync witnesses were present.
QEMU exited zero with owned reap, quit acknowledgment and no forced cleanup;
the guard and outer owner exited 2, with the guard reaped and outer cleanup
errors empty. Acceptance stopped on **`ValueError: post-stop stats must
identify exactly the root backend`**. The counter event acknowledged stop,
but the zero-failure predicate was not established. Its false flag does not
report a measured nonzero I/O error count. VM cleanup remained unaccepted,
the guard result was `INCOMPLETE`, and no firstboot checkpoint was created.
The adapter restored its attributes and reported unchanged sources. Both
firstboot attempts remain preserved; saved-firstboot inspection has not run.

The [12:34:28 UTC saved counter projection](firstboot-memfd/saved-counter-projection-123428.json)
found `root` and `floppy0` top-level rows plus three parent/backing nodes,
all with exact integer-zero failed write and flush counters. The saved event
lacks the post-stop `query-block` reply needed to establish that the extra
backend had no inserted medium; `07-0002` remains unaccepted. The
[12:36:31 UTC read-only receipt pins](firstboot-memfd/retry-receipt-pins-123631.json)
identify seven retained metadata files and confirm the exact guard-result
digest. These observations export selected metadata, not guest logs or
complete raw phone receipts.

## Continuing

Read [CONTINUE-PIXEL.md](../../CONTINUE-PIXEL.md) and use the current
[retry status command](firstboot-memfd/package/08-status-firstboot-memfd-owner.command.txt)
for a fresh process/evidence check. The older bounded progress observer here
is fixed to `05-0002`; its process identity must not control a later process.
Rootfs/partition preparation and the separate partition audit are complete.
The Python compatibility retry reached native execution and shell sync, then
stopped at the post-stop counter validator. Preserve both failed attempts.
Any correction requires a separately reviewed guard version, a fresh attempt
and explicit post-stop backend/medium evidence. The staged guard and frozen
runner remain unchanged. An accepted firstboot checkpoint, saved-firstboot
inspection and `gpu_path_complete` remain outstanding.
