# Final cold guard: retained authored host validation

These are byte-identical copies of the retained validation receipt and raw
unittest output for authored commit
`698962240f6f002296dc8bb39ea744e54b01dd9a`, integrated in the main checkout as
`fac6c4025174a6c2fcdd0745efc96dc17cf957dd`. No tests were rerun while preserving
this evidence.

The recorded invocation was:

```sh
python3 -B -m unittest -v test_guard_ios26_coldboot
```

It ran from the source directory recorded in `host-check.json` on
2026-11-22 at 06:24:44 UTC: **37 tests passed, exit 0**. Source hashes before and
after that run matched. The three source files are described in
[`IOS26-COLD-BOOT-GUARD.md`](../../IOS26-COLD-BOOT-GUARD.md).

| Exact retained file | Bytes | SHA-256 |
| --- | ---: | --- |
| `host-check.json` | 1,475 | `317e9a5e377ff8d6b488d1e240446f420bc14ab2a2b5aa4c69878863f8405ad3` |
| `host-unittest.log` | 6,674 | `ce8177e8f21cceda4c37f2e0d095871da2894807d5ccd08b4a3a3b17f7d86681` |

The independent `harness_review` agent completed a source-only review of
wrapper SHA-256
`17ccc0dfd3b87738a536e93263cf6580cfd8448a6cd2715821a0ecb9214578c3`
and found no concrete production blocker. Its review covered process-handle
ownership, memory latching, cleanup, actual 3 GiB device-tree verification,
historical proof prefixes, complete backing hashes, read-only saved-inspection
launch binding, preparation locking and the final witness verdict. The reviewer
did not rerun tests.

**Physical final cold execution remains pending.** The authored tests use fake
process/native observations where needed and execute no QEMU, guest, mount,
phone or GPU operation. This evidence does not establish a successful physical
iOS boot, usable UI or complete GPU/product qualification. All completion flags
remain false. The retained files contain test metadata and authored fixture
output, with no Apple images, plist bodies or certificates.
