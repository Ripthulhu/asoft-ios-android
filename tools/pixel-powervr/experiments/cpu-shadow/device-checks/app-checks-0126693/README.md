# App-copy audit sources staged on the Pixel

The separate app-copy auditor was staged at
`/data/local/tmp/pixel-app-checks-0126693` at
`2026-11-22T06:02:55.422909+00:00`. This records source transfer and installation,
not a physical audit outcome. No VM or preparation stage was started by this
installation.

The implementation is author commit `fe0a649ab7b5135f8b9b6729802c3418e336e347`,
integrated as `0126693664c21d44e0adc1db5d92513a5ebfce22`. It passed 41 authored host tests and
independent source review; [the host record](../../host-checks/apps-audit.json)
distinguishes the reported result from a retained raw test log.

| Installed file | Bytes | SHA-256 |
|---|---:|---|
| `audit_ios26_apps.py` | 34,103 | `948478f244ea96c40df5693f66bef7c28d4da59dee0db7cc56badac1377232e6` |
| `audit_ios26_apps_guest.py` | 24,987 | `aee8d203cc10fdc2a75d93bed9293d66588190e103cddb50720924c46a43c8c5` |

The ZIP contains only these two regular source files. Its 17,512 bytes have
SHA-256 `87b4bc0608af171df4096d89fdb10877b3c0bbcc72ee33d2b9c65dfe7261a2a5`.
The phone verified the complete transport, exact archive inventory, modes,
lengths and hashes before installing to the fresh root-owned directory.
The installer then rehashed both installed files and all nine earlier frozen,
partition-audit, firstboot-guard and saved-inspector sources.

[install.json](install.json) is the exact 2,074-byte phone receipt, copied back
and verified against SHA-256
`7afd1cbd8b77689ca3f025bd770778e8f8f4b8c39c088a831888b948b5bcd5a6`.
It contains `physical_app_copy_audit_run=false`.

## Required boundary and invocation

First finish the partition audit, guarded firstboot, and saved-firstboot
inspection. After that accepted inspection, run only the frozen preparation
helpers through `ios26-apps`. Stop there before GPU installation.

```sh
/data/data/com.termux/files/usr/bin/python -B \
  /data/local/tmp/pixel-app-checks-0126693/audit_ios26_apps.py \
  --inspection-work /data/local/tmp/pixel-saved-audit-e9cc754 \
  --work /data/local/tmp/pixel-app-audit-e9cc754
```

This command is read-only preflight. Add `--execute` only after the preceding
physical gates and concrete preflight pass. Require
`APP_COPY_AUDIT_PASSED` before proceeding to the GPU helper. The
[procedure](../../IOS26-APPS-AUDIT.md) defines exact source/predecessor
comparison, original-prefix provenance, read-only journals/filesystems and
native cleanup requirements. Application launchability, migration freshness,
UI and final GPU completion remain separate checks.
