# Next diagnostic: compare the two iOSRoot Journal Information Blocks

## Why this is the next boundary

The completed resume4 guest refused `root_baseline_jib_changed`. In the [installed canonical guest](../../../inspect_ios26_firstboot_guest.py), that comparison covers the entire 4,096-byte JIB. It follows identical corresponding root headers, a clean primary header, each JIB's allowed flags and journal-range checks, matching JIB/journal locations and size, and both metadata-overlap checks. It precedes journal-header or all-zero journal validation.

The retained guest error has no attached JIB metadata. It does not identify a flag transition, a changed UUID, padding, journal emptiness, corruption or a safe initialization transition. None of those should be inferred.

The earlier [header diagnostic](../resume2-saved-inspection/header-diagnostic/README.md) read only eight 512-byte volume headers. Its retained files and existing projection cannot supply JIB bytes. Its occupied output directory must remain preserved.

## Implemented scope — awaiting a device observation

The [prepared diagnostic package](jib-diagnostic/README.md) implements this scope with fresh output paths and unchanged legacy extraction/owned-child helpers. The frozen 41,544-byte source has SHA-256 `cf31bf3489bed645dbd59f8e024f6759150f9262f1480e6d9d4ff53f855b9480`. All 28 focused diagnostic tests passed in both the author and independent runs. Transport, launch and future-reader verification are recorded separately in that package. No device installation or execution has occurred.

1. Bind the actual resume4 failure receipts, accepted preflight, exact installed owner/runtime/image-tool sources, completed header evidence, saved/baseline chain identities and existing ownership locks. Preserve the previous attempts and all nine newly verified receipt pins.
2. Derive each root JIB position from the pinned root-header metadata. The observed JIB block is 257; the fixed root base is 2,048 sectors, sectors are 512 bytes, and volume blocks are 4,096 bytes. The expected virtual byte offset is `2048 * 512 + 257 * 4096 = 2101248`. Validate every input, arithmetic result and range; do not silently replace inconsistent observations with this number.
3. Read only the two 4,096-byte root JIBs. The conservative implementation uses sixteen invocations of the already demonstrated 512-byte read primitive, eight per image, with `count = skip + 1`. Reuse the reviewed `run_tool()` ownership, timeout, output-size, exit and reap behavior. Write only new diagnostic evidence at fresh paths.
4. Keep raw JIB bytes on the phone. Export each JIB's length/hash, big-endian flags at byte 0, journal offset at byte 36, journal size at byte 44, total differing-byte count, and a bounded list of differing-byte ranges. Mark any omitted ranges explicitly. Do not export arbitrary bytes, raw device signatures, UUIDs, machine identifiers or private file inventories.
5. Preserve before/after checks for bound metadata, tooling and image identities. Distinguish those checks from newly recomputed full-disk hashes; do not claim a full rehash if none is performed.

This diagnostic must not follow the journal pointer, start a VM or fsck, mount, replay, repair, change the JIB equality predicate, or release inspection/application/APK acceptance. It is for classifying the difference.

## Focused validation required

Test exact-length refusal and field decoding; root/JIB arithmetic and bounds; reconstruction from the selected eight sectors; short or truncated extraction; stable before/after evidence handling; and difference-range reporting for identical blocks, isolated changes, adjacent changes and range-limit cases. Preserve the existing clean owned-child requirements.

A future policy change, if evidence supports one, is a separate code/test/review decision. The observation of a difference alone supplies no such justification.

## Current execution limit

The development workspace has been restored and the local diagnostic tests have run. The remaining access blocker is the originating connected browser session: the browser tool cannot reach the phone terminal from this chat context. The prior inspection and observer have already finished. Restore that browser connection, verify the prepared package's release records, stage the source without executing it, then use the separate reviewed launch. Collect and independently bind the actual result before releasing its detailed projection or deciding whether another inspection is warranted.

## Source review

The initial source-based scope was reviewed independently by `saved_inspection` and `retry_package`; root fetched the exact guest source from commit `77ec7b95012380659196358a578aad301f8bf8c1` and verified its 18,979-byte SHA-256 `f52e4d4ec78c08bf73ec37efac8aa6ecb99a5ab2baf174481fda8b286fb49d97`. The implementation's focused validation and independent reviews are additive files in the prepared package. This document describes the diagnostic scope and supplies no physical JIB result or filesystem acceptance.
