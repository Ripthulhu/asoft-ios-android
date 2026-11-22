# Recovered historical counter1 owner sources

The user supplied the installed pin1 owner after the development workspace restarted without its previous checkout. Its complete bytes match the source identity recorded before the interruption. This directory preserves that file and the exact preceding v1 source.

These files are **historical evidence, not a new execution package**. Pin1 already ran attempt `07-0003`, which stopped before QEMU at the unchanged memory gate. Its owner/work paths contain preserved failure evidence. Neither source should be replayed, and no firstboot success or memory1 release is claimed here.

## Exact source recovery

| File | Bytes | SHA-256 | Recovery method |
| --- | ---: | --- | --- |
| [Corrected pin1 owner](run-ios26-firstboot-owner-counter1-pin1.py) | 35,614 | `b7337a992b5c9c651aae1085c358a27c5d2c8b41998398afd5a4f5ba40c6e2e7` | Unchanged user-supplied copy, matched to the previously observed installed source |
| [Rejected v1 owner](run-ios26-firstboot-owner-counter1.py) | 35,614 | `e78766a3ea3d71064a2866e8e8bf2a7060af85f5384f05d0d61699b1a398ba6d` | Reversed the documented single-byte correction and verified the complete original hash |

The only differing byte is at zero-based offset **1,837** in `PREFLIGHT_SHA`: v1 has ASCII `d` (100), while pin1 has ASCII `b` (98). The full-file hashes establish that this recovers the original v1 bytes, rather than merely producing a similar script. The corrected preflight digest is:

`42a0fefd327fd8be51eebb9be6fac4def61a18f5cf8bb274af23d6c093cbe222`

Both source files were parsed with Python's AST parser. They were not executed during recovery. No new phone owner, preflight, VM, memory action or guest-disk mutation was requested while preparing this commit. Exact metadata is in [sources.json](sources.json).

## What remains to recover

This source recovery does not recreate the original local installer/transport packages, all selected screenshots and transcriptions, or the unstaged memory1 author files. Their known identities and review limits remain in the [workspace-disconnect checkpoint](../workspace-disconnect/README.md). The eight selected `07-0003` receipt pins and memory-compaction observation are already published there.

The new local checkout was reconstructed from the published `ccc23b203cae857c6f1a2b3b49d02bc3a789362c` checkpoint. It is a **partial, shallow checkout**: 380 verified blob objects materialize 416 tracked paths. The other 1,341 tracked paths retain their exact remote index entries with `skip-worktree`; they are not deletions. This recovered published content does not restore lost unpublished files.

Future publication must preserve those unmaterialized paths. Use the current remote head as the expected-SHA lease and compare the resulting tree. The next possible physical attempt remains `07-0004`, after recovering or rebuilding its separately reviewed memory1 package, observing its fresh preflight and verifying current resources. The fresh firstboot floor remains 3,840 MiB.
