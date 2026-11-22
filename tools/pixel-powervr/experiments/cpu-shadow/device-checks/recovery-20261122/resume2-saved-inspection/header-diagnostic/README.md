# Read-only HFS header diagnosis

## Current state

The bounded eight-header diagnostic completed at **16:39:46.597544 UTC**. All owned tool children exited and were reaped without force; existing image identities and bound metadata remained unchanged. Its actual **14,542-byte** result is SHA-256 `d768516e7cc9846e35aefa5f7583797b4cc0c129402a16994965501c69882ba6`. The [selected physical observation](physical-observations/headers-observed-163946.json) and [independent review](independent-header-result-evidence-review.json) record all 32 digest bytes, all eight flag rows, and corresponding iOSRoot header-hash equality.

**All eight headers are journaled.** The rejected predicate is the legacy boot-inconsistent bit 11 in the **iOSRoot alternate header**, and that same alternate-header state already exists in the baseline. The modern runtime-inconsistent bit 14 is clear in every observed header.

| Volume and copy | Saved attributes | Baseline attributes | Observed distinction |
| --- | --- | --- | --- |
| iOSRoot primary | `0x80002100` | `0x80002100` | Clean-unmount bit 8 set; bit 11 clear |
| iOSRoot alternate | `0x80002800` | `0x80002800` | Bit 11 set; clean-unmount bit 8 clear |
| Data primary | `0x80002000` | `0x80002100` | Saved clean-unmount bit 8 clear |
| Data alternate | `0x80002100` | `0x80002100` | Clean-unmount bit 8 set; bit 11 clear |

The corresponding saved/baseline iOSRoot **512-byte header hashes** match. This does not establish whole-root partition equality or filesystem health. No JIB payload, journal state, or fsck verdict was obtained by this header-only diagnostic. The saved inspection remains **INCOMPLETE**, and its acceptance code is unchanged.

`observe_headers.py` binds the exact completed result and installed diagnostic source, rechecks the retained header bytes and fixed commands, and emits two scalar rows per page. Page 0 is saved iOSRoot, page 1 saved Data, page 2 baseline iOSRoot, and page 3 baseline Data. These queries run no native tool and export no raw header bytes.

`inspect_hfs_headers.py` is **22,740 bytes**, SHA-256 `e79c0fbc472ae2a875164565802feffc4fad0a630571970f6e68d7251801bdcd`. Its [final release review](independent-final-header-release-review.json) binds the source, five source-only transfer commands, and separate bounded invocation. Earlier drafts, probe failures and their receipts remain preserved.

## The boundary being diagnosed

The saved inspection returned `volume_not_journaled_or_inconsistent` for iOSRoot after clean native VM completion. Its metadata confirms read-only attachments, matching passed GPT results and no mount, replay or repair. No fsck result or known fsck file was produced. The frozen guest check tests volume-header attributes before journal details and does not attach the failing attributes to that error. The raw-header follow-up above has now classified which flag caused the rejection.

Five actual failed-result metadata files were independently verified from all 160 decimal digest bytes. The reader binds those records, the frozen owner/source/input checks, the exact two-image saved/baseline chain and existing ownership locks. It reads only primary and alternate 512-byte HFS headers for iOSRoot and Data: eight fixed reads. Raw bytes stay on the phone; only scalar fields and hashes are exported. Inconsistency bits 11 and 14 are labelled separately from journal bit 13 and clean-unmount bit 8. No JIB pointer is followed, and whole-header differences are not classified as corruption.

## Tooling and interpretation limits

The bound Android tool is qemu-img 11.1.0 (ASoftware-android), 2,356,032 bytes, SHA-256 `1bd2fd6b968c492d0263436c260af2a8c2ee807cf4afd4fd2abb3300446e2440`. The frozen preparation validator checks its complete manifest and dependencies before and after. The [official QEMU image-tool manual](https://www.qemu.org/docs/master/tools/qemu-img.html) documents the dd input/output operation. [Pinned upstream source analysis](../../hfs-qemu-img-source-analysis.md) establishes ordinary read-only input flags and the count-before-skip implementation; exact native-source reproduction for this custom binary is not established. The upstream input-open behavior remains an inference for the qualified binary. No writable-input defect has been observed.

Existing inspection acceptance, memory/storage floors and runtime source remain unchanged. Existing image identities and bound metadata are checked before and after; this diagnostic does **not** claim newly recomputed full-disk hashes. Three focused offline tests cover partial-header refusal, distinct attribute-bit decoding and retention of an unreapable owned-child identity.

## Preserved capability attempts

The first probe (`probe_qemu_img.py`, phone work `capability-resume2`) refused its option-advertisement check because top-level help contained command summaries. Its 1,467-byte failed receipt and retained help projection remain preserved. `capability-resume3` then used command-specific help and refused the same advertisement criterion before creating a synthetic input; its 1,481-byte receipt remains preserved. Upstream help can omit an implemented skip option, so `capability-resume4` retained help as evidence and made the exact bounded synthetic output decisive. Both failed probes opened no existing image.

All earlier header drafts remain preserved with their success pin unset. The original page-projection draft is also preserved; its finalized form changes only the actual source and result pins. The passed capability4 result is 2,659 bytes, SHA-256 `897cb1faaab342ff576fcc8a3e8d958282f0d44fd0162c445457853cf1d8c11c`; its [physical evidence](physical-observations/capability4-passed-163539.json) and [independent review](capability-resume4/independent-passed-capability-evidence-review.json) establish count3/skip2/512-byte behavior with unchanged synthetic input.
