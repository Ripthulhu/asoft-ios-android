# Resume4 saved-filesystem inspection result

## Actual outcome

The inspection completed with **acceptance false** and owner/inspector exit code **2**. Its native helper completed normally with all three required native witnesses, VM exit code **0**, ECHILD true, no forced QEMU or descendant cleanup, and no cleanup errors. All recorded wrapper, inspector and QEMU identities were absent at the final read.

The guest stopped at **`root_baseline_jib_changed` for iOSRoot**. Its current and baseline 4,096-byte Journal Information Blocks differ. The difference has not been classified as expected or safe. Neither filesystem check ran, so this attempt supplies no fsck verdict and no proof of filesystem health.

This run has finished. Do not replay its execution launcher or the already accepted guarded first boot.

## Evidence

| Boundary | Actual observation |
| --- | --- |
| Final owner/VM status | 2026-11-22 17:35:46.404468 UTC |
| Guest-specific refusal | 2026-11-22 17:40:22.371830 UTC |
| Owner and inspector | Exit 2, accepted false, runner reaped, no forced outer cleanup |
| Wrapper identity | 20063 / 9342623, absent |
| Inspector identity | 20064 / 9342659, absent |
| QEMU identity | 21484 / 9363754, absent |
| VM | Natural exit 0, ECHILD true, forced descendants empty, errors empty |
| Native witnesses | Initialization, execution and final SVC all true |
| Guest | INCOMPLETE; iOSRoot journal code root_baseline_jib_changed |
| GPT and policy | GPT passed; baseline GPT, policy nonce and policy digest matched |
| Guest filesystem actions | Read-only attachments; no mount, replay or repair |
| Filesystem checks | No fsck results; both known fsck diagnostic files absent |
| Preservation | Full backing chain and preparation/guard unchanged; 19 prior failure pins and 16 resume2/diagnostic pins unchanged |
| GPU and application gates | GPU path incomplete; application gate unchanged; no APK authorized by this result |

The [final selected status](physical-observations/inspection-finished-173546.json), its [independent pixel review](independent-final-status-evidence-review.json), the [guest projection](physical-observations/guest-boundary-174022.json) and its [independent review](independent-guest-boundary-evidence-review.json) are backed by retained screenshots. Reported elapsed-time fields are preserved as displayed; they are not replaced with wall-clock differences.

The five inspection metadata receipts and four observer receipts were also read in two bounded pages. Each page checked all nine exact regular files for stable metadata and checked all four recorded process identities absent before and after. The selected receipt record contains all **288 decimal SHA-256 bytes**, with each digest reconstructed into its displayed hexadecimal value. These are corroborating preservation records, not an acceptance override.

## What the new refusal establishes

In the installed guest classifier, this error is reached only after the corresponding saved/baseline root headers match byte for byte, the primary clean-unmount condition passes, both Journal Information Blocks pass their flags/range/alignment checks, their journal locations and lengths agree, and metadata-overlap checks pass. The next comparison requires the complete 4,096-byte JIB bodies to match. That comparison failed.

The failure occurs before initialized-journal-header or all-zero journal validation. The failure path retains only the bounded error code for this volume. It does not retain the JIB payload, the particular differing bytes, or enough scalar JIB metadata to explain the difference. The earlier eight-header diagnostic explicitly did not follow the JIB pointer. No conclusion about corruption, a legitimate initialization transition, or harmless padding follows from this inequality alone.

The root-only header exception remains constrained by the same JIB, journal, filesystem-check, native, cleanup, resource and preservation requirements. This checkpoint changes no acceptance policy.

## Independent process observer

The observer itself finished with exit code 0 and no reported summary errors or remaining observed identities. It recorded 1,761 samples and 10 tracked identities. Its final report is preserved separately from the inspection result.

Coverage was incomplete: **21 sampling gaps**, **119 selected-process read gaps**, and a **135,694.42625 ms maximum discovery interval** were reported. Zero unavailable reads in completed global discovery scans does not cancel these gaps. The observer's final absence and the VM's cleanup receipt support the recorded clean ending; they do not establish continuous observation or explain the old failed worker PID 13344. No cleanup fix was implemented or claimed.

See the [observer evidence](../resume4-process-observer/procstat1/physical-observations/observer-finished-173736.json) and [review](../resume4-process-observer/procstat1/independent-final-evidence-review.json).

## Next diagnostic boundary

A new, separately reviewed read-only JIB comparison is needed. It should bind the completed resume4 failure and the existing saved/baseline image chain, read only the two corresponding root JIB blocks through the already qualified image tool, retain raw bytes on the phone, and expose bounded field comparisons, byte-difference ranges/counts and hashes. It must preserve both input images and all previous receipts, retain clean owned-child accounting, and leave inspection acceptance unchanged.

The existing header-only reader cannot supply this comparison. New extraction and classification logic needs focused tests and independent review before a device run. No new helper launch, image repair, journal replay, application-gate change or APK build follows from this checkpoint.

## Workspace interruption and recovery

The development executor disconnected after publication of the live checkpoint `77ec7b95012380659196358a578aad301f8bf8c1`. The phone job continued independently. Its completed outcome and the metadata above were collected through the surviving browser connection without relaunching it. Publication of this result uses the GitHub connector and a guarded fast-forward.

The development workspace remains unavailable. No new diagnostic test run or local Git alignment is claimed. On recovery, inspect local HEAD, refs and uncommitted work before aligning to the latest remote branch. The prior local checkpoint was `0ededd092cf32d697464abc3210d082c2503b284`; an attempted alignment after the disconnect did not start. Use [CURRENT_STATE.md](../CURRENT_STATE.md) as the continuation entry point.
