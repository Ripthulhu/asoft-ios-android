# TPIDRRO candidate transfer provenance

This folder preserves the reviewed local delta installer and manifests for the
frozen [generic TPIDRRO candidate](../tpidrro-trap/README.md). It does not change
that candidate, its source, or its checkpoint index.

**Completed on 2026-11-21:** host reconstruction and negative checks passed.
All 18 parts and the complete archive SHA-256 then verified on the phone. The
installer reconstructed and verified all 22 frozen files in a new private
directory and rechecked the unchanged base. The subsequent
[root-shell native benchmark passed](../../results/2026-11-21/qemu-tpidrro-trap-root.json).
The `phone_executed: false` field in `update-package.json` preserves the state
when the transfer archive was created; it is not the later device result.

## Pinned artifacts

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| Existing QEMU binary used as the delta base | 58,513,456 | `02fd3b92e1f7747596df8688326af2802a261bf59fdf09222b2a4d7dbb94be74` |
| New QEMU binary | 58,516,208 | `78e6174366fa3522fdcef0e1eca3f606ea3601823148bb69a31e4ecd18c42a35` |
| Frozen full candidate ZIP, `qemu26-tpidrro-trap-smoke.zip` | 20,184,858 | `2ca2bc06c689126d37ea1fc1e8836ab21862c8b98f0186330ea65e96b8dc17d1` |
| Zstandard delta, `qemu-delta.zst` inside the update ZIP | 1,915,841 | `0f4b4d461b2be4e7507ad0df337a4e07b2a6c8d581c52ede9531bd3f2d3b6648` |
| Update ZIP, `qemu26-tpidrro-trap-update.zip` | 1,973,809 | `b75c8adb284db81cd7c8c499a626e6f9ebb2980baa86aa50b1d7302b1be74578` |
| Reviewed installer, `install-update.py` | 8,216 | `5ce83eaabce5911967b5888268b04b4f4d1fbdf44f28a74f5b1f699b1a1afd38` |
| Pinned update manifest, `update.json` | 4,950 | `48121a15a80c133da911c8ee7d136285b64aa757b4efef7f80d696ae83a765a8` |

This folder's `SHA256SUMS` verifies the preserved source and documentation
bytes; the installer and update-manifest hashes identify the reviewed copies.
`update-package.json` preserves archive and base64 metadata and the original
scratch paths. ZIPs, executable binaries, libraries, and base64 payloads are not
included in this repository folder.

The original base package on the phone was
`/data/local/tmp/pixel-native-test.JeLCD7/qemu26-native-required-smoke`.
All full binaries, the unchanged guest, and dependencies must come from the
existing verified packages. The update reuses exactly 13 matching old-package
files: 12 libraries and `el0bench.elf`. Its eight non-ELF payload files are exact
copies from the frozen new package. Reconstructed contents comprise all 22
files of that package, including its unchanged `SHA256SUMS`.

## Delta creation and reconstruction

The encoder used the local **Zstandard CLI 1.5.7**, with one compression thread,
ultra level 22 and window log 27. Given the two verified binaries, the command
used was:

```sh
zstd --single-thread --ultra -22 --long=27 \
  --patch-from=/path/to/verified-old/qemu-system-aarch64 \
  /path/to/verified-new/qemu-system-aarch64 \
  -o /path/to/fresh-staging/qemu-delta.zst
```

The tested decoder command is:

```sh
zstd -d -q \
  --patch-from=/path/to/verified-old/qemu-system-aarch64 \
  --memory=128MB \
  /path/to/verified-update/qemu-delta.zst \
  -o /path/to/fresh-output/qemu-system-aarch64
```

Use explicit memory units. The initially tried unitless `-M128` was insufficient;
`--memory=128MB` passed. The phone's installed Zstandard version was also
reported as 1.5.7, and its existing Termux Python was reported as 3.14.8.

The supplied installer performs the complete package reconstruction rather
than only decoding the binary. Its staging layout is `install-update.py`,
`update.json`, `qemu-delta.zst`, and `payload/` containing the eight files marked
`"source": "payload"` in the pinned manifest. Those payload bytes must come
from the verified frozen full candidate package. The original update ZIP
already contains that layout.

After verifying the **complete update ZIP SHA-256 before extraction**, invoke:

```sh
/data/data/com.termux/files/usr/bin/python3 \
  /path/to/verified-update/install-update.py \
  /data/local/tmp/pixel-native-test.JeLCD7/qemu26-native-required-smoke \
  /data/local/tmp \
  /data/data/com.termux/files/usr/bin/zstd
```

The installer checks every input before creating output, creates a new private
directory under the selected parent, and never overwrites the base package.
The decoder runs with a 30-second bound and without `--force`. The installer
then verifies the complete new binary and every frozen package file, including
full `SHA256SUMS` coverage, rechecks the old binary, and only then applies the
candidate's recorded file permissions. It prints the new package path with
`UPDATE_PACKAGE_VERIFIED_NOT_EXECUTED`. It never invokes QEMU or the runner.

The direct Tango transfer uses terminal input and already installed local
tools. It requires no requests to blocked download hosts, no network fetch on
the phone, and no change to host-access policy.

## Verification and reproducibility boundary

`installer-validation.json` records successful local reconstruction and three
negative checks:

- A wrong base hash is rejected before creating an output directory.
- A corrupted delta is rejected before creating an output directory.
- A forced decoder failure removes only that invocation's freshly created
  directory and leaves the existing output parent and base unchanged.

The reconstructed binary matched the pinned new SHA-256, and all 22 output
files matched the frozen candidate. A second reviewer independently checked
the installer, all file mappings, the 13 reused inputs, and the eight metadata
payload files. No reconstructed executable ran during host validation.

The transfer ZIP was assembled by a one-off inline Python command with sorted
members, fixed ZIP timestamps, stored Zstandard bytes and deflated metadata.
Its original members and outer hash were verified. A reusable archive generator
was not retained, and bit-identical archive regeneration was not separately
tested; none is claimed here. The encoder and decoder commands above preserve
the actual delta procedure, and the installer preserves the verified package
reconstruction procedure. Any regenerated archive needs its own measured
outer SHA-256 before use.
