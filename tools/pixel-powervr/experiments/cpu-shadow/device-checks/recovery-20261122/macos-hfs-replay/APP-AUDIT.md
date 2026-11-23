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

## Accepted audit and GPU inputs

The one-vCPU retry completed naturally in 574 seconds with all three
native witnesses and unforced cleanup. Both read-only fsck checks passed.
GPT and journal metadata were unchanged. The audit checked 10,523 files
and 1,599,952,366 logical bytes. Of 50 source bundles, 48 were copied
and two were explicitly skipped by the preparation policy. The comparison
included 5,925 newly copied files and reported zero errors. The comparison
digest is `ed32c62a5fad8629a9a4818729fb49c0d2907ad4941bee04c8c741c37055eccb`.

The native GPU installer then ran on its own QCOW2 descendant. It exited
naturally with all three native witnesses and unforced cleanup. The host
checked the output image and verified its backing chain before starting
the guarded physical GPU boot.

| Accepted phone artifact | SHA-256 |
| --- | --- |
| App audit guest result | `8f3b3756031cbeccdc408cf91fa5ae20e9adedd97865fc875dd07f5f75a9779c` |
| App audit VM result | `0ba603093a294088ea6465d1e4491576f4e28ff8e94ba85b207ada7a49877052` |
| GPU installer VM result | `0ecec2584749f861d9799521ccb5b16e3209c2faf049284f2311ead6181f6802` |
| GPU installer stage receipt | `313f938735deb0e07db618e4be6092afd2caeb3b9cac3fc97a80c778864fcee7` |
| GPU QCOW2 layer | `90a8b4b99cc496aabf9ba071c5764a006076fe56494ea40bbe243c4cd8305db6` |
| GPU trust cache | `abb25bab6f03ddc89dec014d398bb8035b2b2be61bbaf16f8bab3d85c0666368` |
| Complete preparation handoff | `2941c4ad1e6aed4d1bd2ed3a05bc996f2624247d72eeece444bd452a94cdf97b` |

These receipts cover the prepared app copy and installation of the GPU driver.
Physical iOS GPU rendering and a usable interactive boot require their own
evidence.
