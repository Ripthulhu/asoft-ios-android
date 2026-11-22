# Recovered iOS 26 Data copy on the Pixel

The offline ARM64 recovery tool replayed the retained Resume5 Data state on a
detached raw export. The export matched the previously retained primary and
alternate volume headers, journal information block, and journal bytes. The
tool validated the recovered filesystem graph and set the primary unmounted
bit. The journal moved from `512..614400` to `614400..614400`.

A separate native Linux check opened the recovered volume read-only, ran
`fsck.hfsplus -f -n`, exited zero, and reverified the image SHA-256. The
recovery procedure confines partition changes to a fresh descendant of
`attempts/07-0004/files/root26g.qcow2`.

| Data proof | SHA-256 |
| --- | --- |
| Original guarded firstboot QCOW2 | `36a910108a8e1d462ffaf96e4f76dd8dceda439d5c24330695ed085538651250` |
| Original 06-0001 backing QCOW2 | `49a453b3a3c6b6b2a204a80e10381480972d5484789595756dea2118d7004f99` |
| Detached pending raw Data export | `e840a0395825eb25bbafe6865d2e0cf6179aa235ea28abb49da2137f6129bd03` |
| Recovered raw Data | `0b9c6f5e4cb0fb6b81a272b8b399c28480b75e54be1d936bb5a662ff172046d5` |
| Detached recovery receipt | `73b235605cedc8331160ed159b41b45e1f3c63b8e49aa23cdb307280bd701573` |
| Recovered Data fsck receipt | `994d3b54669bd0bff1ede3c3856e5189d11395b065c68efb113d5812982beae4` |
| Published device overlay | `edd1213461f0cf5b83b8e4e3e1c6b299ec56b20746f68c4b394c93bcbbac8735` |
| Final device recovery manifest | `1379e1e3cdd4b3180c1efe20757fc3afc366e01d426d705d806cd07ae8d33729` |

The recovered layer is
`/data/local/tmp/asoft-data-copy-recovery-01/recovered.qcow2`.
It is **917,504 bytes** and retains the guarded firstboot image as its backing
file. Exactly one 1 MiB region of Data was applied. The new layer's allocation
map contains zero allocations outside Data. Both original QCOW2 files matched
their pinned hashes before and after validation.

The initial `qemu-img compare` on the nested raw subrange reported a mismatch
at 1 MiB. Direct spot reads matched, including at that boundary. The final
verifier then read all **17,179,869,184 bytes** through the QCOW2 chain using
bounded direct reads and compared every byte with the independently checked
raw Data copy. The final verification made no writes to the layer. Its
manifest reports `RECOVERED_DATA_COPY_VERIFIED`.

The prior raw-device-denied probe and its results remain preserved. The
recovered descendant is available for the next guarded whole-image
inspection. An iOS boot, GPU validation, and APK remain pending.
