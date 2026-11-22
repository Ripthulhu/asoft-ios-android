# Final cold-boot guard staged on the Pixel

The separate final cold-boot guard was installed at
`/data/local/tmp/pixel-cold-check-fac6c40` at
`2026-11-22T06:38:11.845921+00:00`. This records source staging only. No final
cold boot has run, and `gpu_path_complete` remains false.

Author commit `698962240f6f002296dc8bb39ea744e54b01dd9a` was integrated as
`fac6c4025174a6c2fcdd0745efc96dc17cf957dd`. The installed
`guard_ios26_coldboot.py` is 43,824 bytes with SHA-256
`17ccc0dfd3b87738a536e93263cf6580cfd8448a6cd2715821a0ecb9214578c3`.

The phone verified the 12,152-byte transport ZIP against SHA-256
`f5e7add6954dd1955f6c75a08b8a8d623a3f838ba9b6d753840c5549b6799d83`,
then checked its exact single regular-file inventory, mode, length and source
hash. Installation used a fresh root-owned directory. The installed source
and all fourteen earlier frozen and audit/guard sources were rehashed.

[install.json](install.json) preserves the exact 2,633-byte phone receipt.
Its copy-back SHA-256 is
`b8a5ba0987a873bdd285b781adfe1162b6ac55be1675f743ca91a6488f144e69`.
The [retained host evidence](../../host-checks/final-cold-guard/README.md)
records all 37 passing tests and independent review of the exact source hash.

## Required boundary and invocation

First require the accepted saved-wallpaper inspection, then complete the
original locale and pack stages. At that exact through-pack boundary,
preflight the separate guard:

```sh
/data/data/com.termux/files/usr/bin/python -B \
  /data/local/tmp/pixel-cold-check-fac6c40/guard_ios26_coldboot.py \
  --wallpaper-inspection-work /data/local/tmp/pixel-wallpaper-check-e9cc754 \
  --work /data/local/tmp/pixel-final-cold-e9cc754
```

The work directory must still be fresh. Actual execution uses `--boot`, not
`--execute`, and repeatable `--expect-serial` values chosen from actual,
understood iOS milestones. No serial marker is invented in this staging
record. A run without explicit markers cannot receive a passing verdict.

The guard binds the original preparation session, all earlier proof prefixes,
nine packed assets, the complete locale/backing ancestry and original inputs.
It preserves the original cold owner and witness rules. The actual copied
launch tree must equal `expected_tree(original, 3, 3)`; qualified QEMU uses
that tree's DRAM size. Fresh available memory must be at least 3,840 MiB
immediately before launch. The original roughly ten-second supervision
reports and pre-shutdown sample require at least 512 MiB; missing, unreadable,
malformed or low observations remain failures after later recovery.

Acceptance requires the original `WITNESSES_OBSERVED` result, explicit serial
milestones, native/GPU/frame evidence, passing memory observations, complete
owned cleanup and unchanged bound inputs. Human frame inspection, app-UID
execution and broader product qualification remain separate requirements.
The [guard procedure](../../IOS26-COLD-BOOT-GUARD.md) documents the limits.
