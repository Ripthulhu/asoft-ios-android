# Downstream counter1 source integration

The independently reviewed downstream counter1 package has been copied into the
main checkout as a reversible source update. The six destination files matched
their expected baseline hashes before copying and now match the reviewed bytes.
The existing counter1 firstboot guard and inspector dependencies also matched
their reviewed hashes. No conflict was found.

This record supplies source and offline validation evidence only. There is no
new downstream VM run or physical pass. The two preserved failed firstboot
attempts remain unaccepted, and every upstream and downstream physical gate
still applies. This integration did not stage, commit, publish, or perform
device actions.

## Exact source changes

| Source | Purpose | SHA-256 |
| --- | --- | --- |
| `audit_ios26_apps.py` | Bind the new firstboot guard and saved inspector. | `6096521f41a8f2caf1c166495d09df28923135dde02295872b98c97a96378291` |
| `guard_ios26_wallpaper.py` | Bind the updated app auditor and require both post-stop block responses and their exact ordered trace. | `e563fcc7425187c9f0079ecbe206f01e5c4be69168a6937aaefd22283a98262f` |
| `inspect_ios26_wallpaper.py` | Bind the updated wallpaper guard. | `df7400ccbe03c3882cd3afcb2ecf892ffde635a2773480192354347320033c99` |
| `guard_ios26_coldboot.py` | Bind the updated wallpaper guard and inspector. | `1a965014ca1c437b97a076a7367e64f764d741162632badacf49f2a2d26993a1` |

The only test-source changes are `test_audit_ios26_apps.py` and
`test_guard_ios26_wallpaper.py`. The four frozen runner files, memfd adapter,
and guest audit/inspection implementations are unchanged. Original native,
GPU, frame, sync, app-copy, journal, filesystem, resource and final UI gates
remain enabled.

The wallpaper sequence is `stop` → `query-blockstats` → `query-block` → `quit`.
Each query has a five-second bound. Both responses are preserved, the shared
counter1 validator checks matching inventories and the narrowly qualified empty
floppy shape, and acceptance verifies the actual successful ordered QMP trace.
Missing or inconsistent evidence follows the existing cleanup/refusal path.

## Retained review and validation

The exact reviewed export is retained under [revision/](revision/README.md),
including the four production files, two test files,
[six-file patch](revision/0001-propagate-counter1-protocol-to-downstream-gates.patch),
[manifest](revision/manifest.json), [baseline identities](revision/baseline.json),
[test receipt](revision/focused-tests.json) and [full test log](revision/focused-tests.log).
The export's README describes its original isolated authoring boundary; the
current main-checkout copy is recorded separately in [integration.json](integration.json).

All **122 focused offline tests passed** in the app-audit, wallpaper-guard,
wallpaper-inspector and final-cold-guard suites. The retained receipt binds
their exact source/support bytes. No source changed between that passing run
and this copy; the suites were not rerun during integration. Independent review
found no blocking issue and checked the source-pin chain and receipt hashes.

| Evidence | SHA-256 |
| --- | --- |
| Six-file source/test patch | `68ba64e84d181ea97b3404ef3a55b7434bfe5ef33e71f82de290a650a23468d7` |
| 122-test log | `e5cf4de22cc06fd19528a43f1fc4785df635f632ce4ca13e4dde5ba95a2207d7` |

The [qualified QEMU policy report](policy-source/SOURCE-BASIS.md) and
[immutable source inventory](policy-source/source-basis.json) are retained
separately, together with their original firstboot-specific 57-test receipt.
They explain why an unattached default `floppy0` has `removable=true` and no
inserted medium, and why `account_failed=false` does not disable failed-I/O
counter increments. The complete QEMU source snapshots are retained in the
separate [firstboot counter evidence](../firstboot-counter/qemu-source-basis/).
The new `query-block` test data is synthetic source-grounded evidence; old
attempt `07-0002` did not collect that response and cannot pass retrospectively.

Only the directly affected app-audit, wallpaper-guard, wallpaper-inspection and
final-cold-guard workflow documents were updated to state these prerequisite
pins and the two-query protocol. No continuation index, recovery overview,
firstboot document or preserved prior failure was edited by this integration.
