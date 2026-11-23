# Read-only system app audit on Pixel 10

The [prepared app layer](PREPARATION.md) was reused for each audit attempt.
Both forced read-only filesystem checks passed with the pinned iOSRoot
alternate header. The subsequent APFS check initially rejected the source
string reported by FUSE. Its guest receipt was
`9212363ca8efe970ffe1ca146f0543e08fb3ced44fd87577a8683afe5129a1ba`.

The independent native mount probe confirmed that the read-only FUSE source
is the guest path passed to `apfs-fuse`. That path is a symlink to the
attached source block device. The probe returned type `fuse`, mount root
`/`, and options `ro,nosuid,nodev,noexec,relatime`. The adapter verifies
that exact path and its resolved block-device identity in the guest and
checks the returned mount record again on the host.

| Phone evidence | SHA-256 |
| --- | --- |
| APFS mount identity probe result | `597409bf6c88cf49e7a4e5e8aa1542da1e2673e721a12e276d148511002371c9` |
| Probe native VM result | `ebde0d60f139c80fb4e45ca1a6fb74d4d761142ef55ba4cce6dc447d4225c415` |
| Four-vCPU audit result | `4a79e599d45064a4065f49dd2820f260b710d0661d94099c5a0cd5eb444bfcb8` |
| Four-vCPU native VM result | `756acbe7bc77a1770aee3fe5f2f0a937c9f8817292a29c31116a2161d9766735` |
| Four-vCPU QEMU stderr | `9c0f8b63c624696e3402b8b1f57b30cb4d16c82d2b8c0956312ba80670f0c0be` |

The four-vCPU helper ran for 824 seconds. QEMU reported an alternate
signal-stack violation in one native stub and exited with SIGABRT before
a comparison receipt was returned. The three audited disks were attached
read-only. The retry uses one guest vCPU and two native stubs for this audit
only, with native EL0 required and the same filesystem and content checks.
The GPU preparation and guarded boot depend on an accepted comparison.
