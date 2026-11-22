# Bounded host extraction for the Data journal diagnosis

This package is prepared for the exact saved firstboot image that resume5 inspected. The host source and pure parser have passed independent source review. [The exact source transfer and separate launch have also passed review](independent-transport-launch-review.json). No diagnostic installation, execution or result is claimed by this preparation record. Reconnecting to the browser does not require repeating these unchanged code reviews; actual installation and runtime output still need to be observed and verified.

The actual failure is preserved in [the reviewed guest boundary](../../physical-observations/guest-boundary-selected.json) and [the nine receipt bindings](../../physical-observations/receipt-pins-selected.json). iOSRoot passed its strict raw-journal classification. Data's checksum-valid journal header has `start=512`, `end=614400`, `size=8388608`; the unchanged inspector refused `nonempty_journal` before either filesystem check. This diagnostic does not turn that refusal into acceptance.

## Fixed reads and retained evidence

The Data partition begins at virtual byte 34,360,786,944 and is 17,179,869,184 bytes long. The scope derives from the exact recorded partition geometry and retained saved Data headers, linked to the currently inspected backing-chain records.

| Read | Virtual byte offset | Exact bytes |
| --- | ---: | ---: |
| Data primary header | 34,360,787,968 | 512 |
| Data alternate header | 51,540,655,104 | 512 |
| Data journal information block | 34,361,315,328 | 4,096 |
| Complete Data journal | 34,361,319,424 | 8,388,608 |

The host runs exactly four owned native `qemu-img dd` commands. The frozen executable is 2,356,032 bytes / `1bd2fd6b968c492d0263436c260af2a8c2ee807cf4afd4fd2abb3300446e2440`. The commands use the tool's physically demonstrated `count=skip+requested_blocks` behavior. They read through the recorded qcow2 backing chain and write fresh private diagnostic files. No image is attached writable, no guest VM starts and no mount, filesystem check, replay or repair runs.

Both fresh Data headers must equal their retained byte-pinned counterparts before the JIB is read. The JIB must still identify the same in-volume 8 MiB journal with flags 1. The unchanged pinned guest helper rejects a journal/JIB overlap with reserved areas or inline metadata extents before the journal is read. The journal's first sector must match the actual failed-inspection hash, `f9bd83c96acbaba80a2d24b09731ef6f39ae78cc922cbca9d65c774716c2a66f`, and reproduce the exact existing `nonempty_journal` metadata.

The source snapshots preserve all older inspection and diagnostic evidence through the reviewed resume5 owner. The new host separately binds the nine actual resume5 receipts, preflight, source pair, observed clean native VM and completed independent observer. The owner, inspector, QEMU and observer identities must be absent before and after the diagnosis. The existing preparation and resume5-work locks remain held throughout; no old attempt is relaunched and no checkpoint or acceptance file is changed.

## Bounds and process ownership

The unchanged resource floors are 2,816 MiB MemAvailable and 1,536 MiB free storage. They apply before the output directory exists and before each native read. The separate launcher follows the completed JIB launch pattern: it creates no launch log or execution receipt and executes the verified host in the same Python process. A resource refusal before `OUT` creation remains distinct from a started diagnosis. There is no retry loop.

Each native child has a 60-second wall bound, 30-second CPU bound and 8 MiB per-file hard size limit. Its stdout has a 64 KiB polling refusal threshold, checked at 50 ms intervals; it may exceed that threshold before the next poll, while the hard file limit remains 8 MiB. Any overflow, timeout, forced cleanup or failed reap makes the diagnostic incomplete. Only the host's exact unreaped child may be killed during cleanup. No inspection, observer or unrelated process is signalled. Partial task outputs remain preserved.

Before and after the reads, every backing-chain member must retain its complete recorded identity: canonical path, file identity, byte count, timestamps and first-64-KiB digest. The fresh descriptor read itself must be stable. The prior full-file digest records must remain bound and unchanged; this task does not hash every image byte again. Results explicitly report `whole_image_hashes_recomputed=false`. Bound receipt, source and tooling metadata are freshly hashed. This distinction must survive every result summary.

## Diagnostic and acceptance boundaries

The separately reviewed pure parser receives the retained 8 MiB byte string, the exact 16 GiB Data size and the exact observed header digest. It examines only the known active interval, 613,888 bytes, under explicit record and entry caps. The host allowlists the parser's selected output schema. It exports neither target block numbers nor entry-zero pointers, sequences, raw payloads, device signatures, UUIDs or file inventories.

`READONLY_DATA_JOURNAL_DIAGNOSTIC_OBSERVED` means extraction, parser invocation and preservation completed. The parser may still report `INCOMPLETE`; that outcome is retained explicitly. Even `STRUCTURE_DIAGNOSIS_COMPLETE` establishes only the supported structure checks. It does not establish filesystem consistency, a safe replay implementation, transaction coalescing semantics or inspection acceptance. The complete selected records remain in the private result; terminal output uses bounded aggregates. The [separate observations package](../observations/) owns result-pin acquisition and later actual-result-bound pages.

The prior firstboot sent guest shell `sync`, then used the guarded QMP stop/quit path. It did not prove a guest filesystem unmount. The repository also records that the pinned Linux hfsprogs `journal_replay()` is a no-op; the older application comment claiming helper replay is not a qualified recovery procedure. See [the saved-inspection gate](../../../../../IOS26-SAVED-FIRSTBOOT-INSPECTION.md), [firstboot guard rationale](../../../../../IOS26-FIRSTBOOT-GUARD.md) and [partition audit source analysis](../../../../../IOS26-PARTITION-AUDIT.md). Apple [TN1150's Journal section](https://developer.apple.com/library/archive/technotes/tn/tn1150.html#Journal) explains why active journal transactions require refusal or replay by a compatible implementation before filesystem consistency is assumed. The [pinned format review](../independent-format-semantics-review.json) distinguishes the modern format from older prose and does not identify the actual guest kernel source.

A future replay experiment would need its own explicit scope, qualified replay implementation and fresh copy-on-write descendant. It must preserve the accepted firstboot and every existing image, retain native EL0 plus kernel TCG, and earn a new strict empty-journal and filesystem inspection. No such experiment is implemented here. Clearing cursors, skipping the raw gate or treating the current fsck utility as replay would not establish that result.

## Exact source and transport

- `inspect_data_journal.py`: 51,923 bytes / `85194af9e14f68e16d1990e79603060644a892c772adafc51dc52777055c77c9`.
- Pure parser: 14,617 bytes / `4036055b490f5fd93a74e6d12de12f511de45e8e0f62dfa81419151fc2dcc852`.
- Source manifest: 1,692 bytes / `fb21a4782fa6f5bf04edac463df6cf6a2a6767102d969135085d53128d45d65d`.
- Separate launch command: 1,961 bytes / `49844f2967f3e90da6c15d002374a961ee6e5d364404f2f2dc55e2d71d69143e`.

[transport-steps.json](transport-steps.json) gives the exact ordered nine installation commands: begin, seven chunks, assembly. Every command is at most 5,218 bytes. Installation only reserves fresh paths, writes the exact two reviewed sources, verifies them and writes an installation receipt. It never imports or executes either source. The launch is separate and rechecks the manifest, installation receipt and both complete installed sources before invoking the host.

Fresh phone paths are:

- Source: `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-data-journal-diagnostic-resume5.py`.
- Parser: `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/parse-ios26-data-journal-resume5.py`.
- Output: `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-data-journal-diagnostic-resume5`.
- Transfer: `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/data-journal-diagnostic-resume5-transfer`.
- Installation receipt: `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/data-journal-diagnostic-resume5-install.json`.

## Validation

[The independent host review](independent-host-source-review.json) binds the frozen source and repeats all 31 focused host tests. The preserved unbound draft differs from the executable source only in `PARSER_SOURCE_PIN`. The parser's independent review covers its separate 29-test suite.

The unbound `host/observe_data_journal_UNRELEASED.py` is an unreviewed precursor retained for provenance. It is not a released command or a source installed by this packet. Use only the separately reviewed [observations package](../observations/) for physical status, result binding and selected pages. Likewise, the historical pending state in `transport-build.json` is the generator's original record; [preparation-status.json](preparation-status.json) adds the completed source and transport reviews without changing those generated bytes.

The host tests exercise observed evidence pins, fixed range arithmetic, refusal on changed headers/JIBs, exact nonempty-header binding, typed selected-output limits, owned-child timeout and stdout overflow cleanup, preservation failures, resource refusal before output creation and lock release even if result writing fails. [The 14 focused transport tests](transport-validation.json) use sources that raise if executed. [Exact packet reconstruction](packet-validation.json) verifies all ten command bodies, all seven chunks and the complete 68,396-byte two-source bundle, and installs those exact bytes only into a fresh temporary directory. No native tool or device run was part of these tests.
