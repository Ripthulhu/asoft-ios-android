# Pixel HFSX replay-only probe

The Linux preparation VM embedded the fixture-only iPhoneOS helper in a fresh
shell ramdisk and passed its read-only HFS check. The Pixel booted the Darwin
ramdisk from `md0`, ran the original read-only root helper and passed the three
native execution witnesses. QMP verified the single writable disk was the
disposable HFSX copy.

The new helper launched. Darwin System Policy denied its raw device open with
`deny(1) file-read-data /dev/rdisk0`. It exited before invoking
`HFS_REPLAY_JOURNAL`. Both the source fixture and the writable attempt
retained the same 96 MiB SHA-256. The journal remained at start 512 and end
12800, and the test catalog value remained unchanged. QEMU acknowledged
the stop and quit, exited zero, and all children were reaped without force.

| Retained evidence | SHA-256 |
| --- | --- |
| `asoft-rd-probe-replay1/run/result.json` | `5e52da56a86ace3373ffa0f3368528f7c197c2f2967ce26681c92848bad31ef9` |
| `asoft-rd-probe-replay1/verification.json` | `9ffa897d927903587f24d1c9dc98d845b216b2bdf52f2870500ee913998e3a11` |
| Both fixture images | `4f3c23d42d26fd0de77da4271a2e3f1b50d869793d2876594e772411fea53456` |
| Pixel replay probe launcher | `1644dc916290a025d51a2f6515f03db62fa2a9efc5452ec5449af4ffb12d390c` |

The [fixture-only build and transport](https://github.com/Ripthulhu/asoft-ios-android/actions/runs/45081850509)
used an image made on hosted macOS. The saved Data image stayed detached.

A read-only check of the retained Resume5 extract shows six writes covering
the primary Data volume header and none covering the alternate header. The
last primary header payload leaves the unmounted flag clear. A working Data
recovery path needs both durable replay and a separate clean-state verification.
