# Downstream counter1 compatibility candidate

This separate source candidate propagates the reviewed firstboot counter1 protocol through the existing app audit, wallpaper execution/inspection, and final cold-boot prerequisite chain. It depends on the separately reviewed firstboot guard `ea40638312d6ac41607806ecb03c148fbd0677df6ab01480e13fd40536869674` and saved-firstboot inspector `2b127ecda390b199287358cdad7e6e7774f5b787148aea524e7b0247a2640cf3`.

There is no physical acceptance in this export. Firstboot and saved-firstboot inspection must pass first, followed by each original preparation, audit, wallpaper, saved-disk, locale/pack, and final cold-boot gate. Neither failed firstboot attempt can acquire acceptance from updated source pins. Old staged sources and failed evidence remain separate.

## Changes

| Source | Necessary compatibility change | SHA-256 |
| --- | --- | --- |
| `audit_ios26_apps.py` | Pins the new firstboot guard and saved inspector; all app/journal/copy validation is unchanged. | `6096521f41a8f2caf1c166495d09df28923135dde02295872b98c97a96378291` |
| `guard_ios26_wallpaper.py` | Pins the updated app auditor; collects bounded post-stop `query-block` evidence after statistics; calls the shared two-response validator; revalidates both responses and the exact four-command QMP trace. | `e563fcc7425187c9f0079ecbe206f01e5c4be69168a6937aaefd22283a98262f` |
| `inspect_ios26_wallpaper.py` | Pins the updated wallpaper guard; guest/raw-journal/fsck logic is unchanged. | `df7400ccbe03c3882cd3afcb2ecf892ffde635a2773480192354347320033c99` |
| `guard_ios26_coldboot.py` | Pins the updated wallpaper guard and inspector; independent cold owner, native/UI/GPU/memory and final verdict logic is unchanged. | `1a965014ca1c437b97a076a7367e64f764d741162632badacf49f2a2d26993a1` |

The wallpaper stop protocol now matches firstboot: `stop` → `query-blockstats` → `query-block` → `quit`. The added query is bounded to five seconds. Its response is preserved as `post_stop_blocks`, while `post_stop_blockstats` retains the existing statistics. The same reviewed predicate admits only root or root plus the precisely qualified empty default floppy, checks matching root identity and writable media, and requires typed zero failure counters throughout the returned graph. Query or validation failures retain the event and follow the original cleanup and checkpoint-refusal path.

No guest auditor/inspector source changed. No frozen runner source or memfd adapter changed. No additional source is trusted implicitly: pins are updated in dependency order, and existing exact-source/receipt checks continue to enforce them. The four production files and two directly affected test files are the complete patch.

## Validation

All **122 focused offline tests** passed in the app-audit, wallpaper-guard, wallpaper-inspector and final-cold-guard suites. `focused-tests.json` records the exact command, local support hashes, unchanged-source check, log hash and exit code. The test log is retained in full. The fixtures are authored metadata and mocked owners/I/O; no VM, GPU, phone, mount, package or network execution occurred.

Independent source review found no blocking issue in the six-file patch or the dependency, patch, receipt and log identities. The reviewer confirmed that the source-pin chain is consistent and that the original native, GPU, frame, sync, journal, filesystem and resource logic is unchanged. The review ran no additional tests or device actions.

Added regression cases cover matching two-query empty-floppy evidence, no-medium enforcement, failure counters on the empty backend, inventory mismatch, query timeout with statistics preserved and cleanup performed, missing new evidence in a success-shaped receipt, reply/order/duplication/error tampering after metadata hashes are recomputed, and old saved-inspector receipt rejection before any source is loaded. Existing native/GPU/frame/settling/sync, immutable ancestry, app-copy, raw-journal/fsck, memory and final verdict tests remain enabled.

The receipt uses the current copied preparation support source identified in `baseline.json`; it is not a physical run of the byte-frozen phone preparation environment. The firstboot counter1 source and test dependencies are listed separately from the downstream baseline. `manifest.json` and the six-file unified patch make this candidate independently reviewable and reproducible.

## Delivery boundary

The candidate lives only in the isolated `downstream-fix` directory. The parent owns main-repository integration, new staging directories, immutable source receipts, fresh physical preflights and any later device execution. A passing offline suite does not satisfy any of those physical gates or confer boot, GPU-path or application-launch completion.
