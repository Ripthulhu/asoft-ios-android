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
At **10:57:29 UTC**, the [latest full owner observation](owner-observation-105729.json)
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

## Continuing

Use the existing installed observer from [CONTINUE-PIXEL.md](../../CONTINUE-PIXEL.md)
for a fresh owner/checkpoint check. The bounded observer here is deliberately
fixed to `05-0002`; do not use its old process identity to control a later
process. Let the current owner finish its rootfs and partition stages.
The separate partition auditor is the next gate after accepted natural
completion. Actual iOS boot and `gpu_path_complete` remain unproven.
