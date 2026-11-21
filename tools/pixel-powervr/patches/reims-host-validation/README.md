# Reims host validation and Vulkan alias patches

This optional six-patch increment follows the
[explicit reims producer API](../reims-producer/README.md). It repairs host
format/lint/fixture blockers, extends C ABI coverage, fixes an address-reuse
ambiguity in a lifetime test and supplies a supported Vulkan import/map alias
diagnostic. The [host checkpoint](../../ios26-build/reims-host-validation/README.md)
contains the complete evidence and remaining failures.

**The full gate is not green.** Formatting, both Clippy configurations and
compilation pass; nextest reports 3,001 passed, six failed and two skipped.
The new alias path passes on lavapipe with validation enabled. Raw POSIX
interpretation of the opaque FD remains unqualified and correctly refused.
No Android binary or guest boot was qualified with this source increment.

## Exact source

| Item | Value |
| --- | --- |
| Source repository | `https://github.com/alpersamur3/reims-vgpu` |
| Required producer base | `7bbcb042a71b57dba286d33638848c188e5d4799` |
| Base tree | `7ec29658bf455090d881b8ef055fdf00394e61b3` |
| Prepared host source | `c3551c742dfa826ea8e4aecf5affc22bf508822b` |
| Final source tree | `acf9ad9a46892d9833d851cd23cf8d2e357e90d6` |
| Unchanged prepared metal2vulkan | `7aaf60f105544b70b4cf25f9eb44ace4b00a61fd` |
| metal2vulkan tree | `1ee7add340efbe6da12d9e16e29dfe60ed5daff9` |

Reconstruct the parent patch series and its retained-backing dependency
first. In this directory, verify the patch hashes:

```sh
sha256sum -c SHA256SUMS
```

On a clean source checkout at the exact producer base, apply `0013` through
`0018` in the order given by [series.json](series.json), using `git am` with
the six patch paths. `git rev-parse 'HEAD^{tree}'` must report
`acf9ad9a46892d9833d851cd23cf8d2e357e90d6`. Commit metadata can produce different
commit IDs; the tree is the source-content check. A temporary Git index
reconstructed this complete tree from the six exported patches.

| Patch | Purpose |
| --- | --- |
| 0013 | Baseline Linux lint/format fixes; preserve awake-clock semantics |
| 0014 | Complete sleep callback fixtures and exercise all 50 C API functions |
| 0015 | Classify two unmeasured format semantics in strict audits |
| 0016 | Check SIMD flags against the actual host audit; assert idle constants |
| 0017 | Identify original file mappings in the surface lifetime test |
| 0018 | Import/map a producer FD through Vulkan; retain raw mmap negative mode |

Patch 0015 changes optional strict-audit behavior. Default behavior keeps its
existing logged relay. No new cold guest boot or behavior-lock suite result
qualifies that policy change; these patches are a preserved work branch,
not an upstream integration claim. The product's normal capability logic,
native requirement and producer-atomic restrictions are unchanged.

[provenance.json](provenance.json) matches the final test snapshot and each
changed file to its committed blob, records the clean prepared metal2vulkan
dependency, and records the patch-reconstructed tree. The local absolute
Cargo dependency override and lockfile are retained separately in the host
checkpoint. Existing dual licenses and notices in the parent `licenses/`
directory continue to apply.
