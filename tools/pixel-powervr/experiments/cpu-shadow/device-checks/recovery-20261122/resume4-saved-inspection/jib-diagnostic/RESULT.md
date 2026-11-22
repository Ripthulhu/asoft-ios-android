# Root JIB diagnostic result

## Observed outcome

**The bounded read-only diagnostic completed successfully. The saved root JIB differs from its baseline in exactly one byte: the flags value changed from `0x00000005` to `0x00000001`.** The only differing interval is `[3, 4)` within the 4,096-byte JIB. There are no omitted or truncated difference ranges.

The diagnostic completion was observed at **2026-11-22 20:16:40.213734 UTC**. The completed result was bound at **20:17:28.126172 UTC**, and the separately reviewed result-bound readers confirmed the summary at **20:21:20.762494 UTC** and its single difference range at **20:21:32.934758 UTC**.

| Field | Saved root | Baseline root |
|---|---:|---:|
| JIB bytes | 4,096 | 4,096 |
| JIB virtual offset | 2,101,248 | 2,101,248 |
| Volume JIB block | 257 | 257 |
| Flags | `0x00000001` | `0x00000005` |
| Journal offset within the volume | 1,056,768 | 1,056,768 |
| Journal bytes | 8,388,608 | 8,388,608 |

The complete baseline JIB hash is `65f57e6fad390f4a87dafbc97c23ded9a66a416d6600350dd5eeb34ebc2632eb`. The saved JIB hash is `e50b1697e64b81794bc984642dc652d40bd7041818f7299f71a118300f8289a9`. These also match the existing guest inspector's locally generated authored root JIB and that same complete structure with only the big-endian flags changed from 5 to 1. This local structural cross-check is separate from the actual phone reads.

## Receipt and preservation

The actual phone result is **14,246 bytes**, SHA-256 **`5d39c9a0fb16c794577abaf4ab7155ee5f352d46cb7027e03b571055f10d5061`**. All 32 displayed decimal digest bytes reconstruct this exact hash. The diagnostic source remained the reviewed **41,544-byte** file with SHA-256 `cf31bf3489bed645dbd59f8e024f6759150f9262f1480e6d9d4ff53f855b9480`.

All sixteen bounded native image-tool commands completed and were reaped without forced cleanup. The result recorded unchanged image identities, bound metadata and bound tooling; the four recorded prior inspection/observer identities were absent. Both error fields were null. The later readers rechecked the bound result, source, sixteen sectors and assembled blocks, and verified that the diagnostic owner was absent.

Raw sectors and the two assembled JIBs remain on the phone. Only selected scalar metadata, hashes, difference ranges and task screenshots are published. This diagnostic neither followed the journal pointer nor started a guest, filesystem checker, mount, replay or repair. It did not recompute full-disk hashes or claim saved-inspection acceptance.

## Interpretation and next inspection

[Apple TN1150, Journal Info Block and Journal Header](https://developer.apple.com/library/archive/technotes/tn/tn1150.html) defines flag `0x4` as `kJIJournalNeedInitMask`. A newly allocated journal normally has this bit cleared when its journal header is initialized. Apple HFS source at [the pinned create-and-clear path](https://github.com/apple-oss-distributions/hfs/blob/d1bac2f062e6e9c0dfcce302d9aacb10173d0eea/core/hfs_vfsutils.c#L2599-L2618) implements that sequence. These sources explain why the observed one-bit transition is a candidate for classification; they do not establish the exact guest-kernel implementation or the saved journal's validity.

**The saved journal header has not been evaluated by this diagnostic. Its emptiness and the filesystem verdict remain unknown.** The completed resume4 inspection remains rejected at its earlier full-JIB equality predicate.

The next revision must recognize only a separate root-only authored-NeedInit-to-initialized-empty case: identical corresponding volume headers and geometry, a clean primary header, the exact authored baseline JIB, only the NeedInit bit cleared in the saved JIB, the full baseline journal still zero, and the saved journal passing the existing endian, magic, checksum, range and empty-cursor checks. Both complete forced read-only filesystem checks, post-check revalidation, native lifecycle checks and image-chain preservation must still pass in a fresh inspection. No revised inspector has been installed or executed at this result checkpoint.

## Evidence

- [Installation screenshot](physical-observations/source-installation.jpg) and [independent installation review](physical-observations/independent-source-installation-review.json).
- [Completed diagnostic screenshot](physical-observations/diagnostic-completion.jpg).
- [Selected actual result receipt](physical-observations/result-pin-selected.json), [receipt screenshot](physical-observations/result-pin.jpg), and [independent receipt review](independent-result-pin-review.json).
- [Actual reader binding](result-binding/projection-binding.json) and [independent finalized-reader review](result-binding/independent-finalized-projection-review.json).
- [Selected JIB metadata](physical-observations/metadata-selected.json), [bound summary](physical-observations/bound-summary.jpg), [single range page](physical-observations/bound-ranges0.jpg), and [independent projection evidence review](physical-observations/independent-projection-evidence-review.json).
