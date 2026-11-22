# Accepted second Linux embedding experiment

A fresh Linux VM run copied the same signed helper into a new ramdisk copy.
The Linux guest unmounted the image and passed the forced read-only HFS
check. The native host reached natural QEMU exit 0, all three native
witnesses and `ECHILD`, with zero forced descendants. The dedicated
supervisor waited up to three seconds for natural exit, reaping seven
descendants without sending a signal. The original cleanup fallback and
acceptance checks still apply if the bounded wait expires.

The builder's host return-tar call initially refused because the destination
directory had not been created. The preserved VM result had already reached
`VM_OBSERVATION_COMPLETE`. The additive finalizer pinned that VM result
and the original host receipt, used the same bounded tar checker in a fresh
destination, verified the returned guest receipt and bound the modified
image. The finalizer made no guest VM call.

| Retained item | SHA-256 |
| --- | --- |
| Executed embedding source | `04a94c59a2f674ac4fc5f6f83c9a09c84cefbdf7f4442a185093f53d5bd78879` |
| Clean VM result | `9c41d2cbfb77fe2a0834aff582e0e1f5f8d60fdd8ee5caf9f80eaa272594f087` |
| Original host result | `005fa24dc3f66d93ba8cf199e411381f49f58721e81f4662ce51535a011f494f` |
| Additive acceptance | `3756aa48c45325493cea326e63239a8c869cbf9181149d00cd140e5c165d323d` |
| Accepted 511,705,088-byte ramdisk | `648bdd2584050b45bab4ac865192940a12079f75f4b443379565af445c6fb18d` |

The accepted image and receipts are under `/data/local/tmp/asoft-rd-embed-02`.
The additive result was accepted at **22:25:03.847654 UTC** on November 22,
2026. The first embedding attempt and its unaccepted candidate are preserved.
The next use is a diskless Darwin boot of the accepted ramdisk as firmware,
with only the helper's read-only root query. Data recovery requires a
separate clean unmount experiment on a disposable HFS volume.
