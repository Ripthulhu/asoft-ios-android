# Fourth physical probe: volatile root remount refused

The fourth diskless run started at **22:21:25.948499 UTC** and finished at
**22:22:16.193210 UTC** on November 22, 2026. It observed the HFS root
`root_device` at `/`, UID and EUID zero, and the Darwin `md0` boot witness.
Both QMP block inventories were empty before boot and again after observation.

After those checks the guest ran one normal `/sbin/mount -uw /` against
the firmware-backed RAM root. The nonce-bound status was exit 1 with
`Operation not permitted`. The helper transfer never started. No iOS
disk, overlay or backing image was attached. QEMU stopped and quit with exit
zero, all three native witnesses and unforced owned cleanup. Bound inputs
were reverified.

The source SHA-256 was `891dce3d722c091b4c56e9a2bcba61be22b91d91acd6f8a805d956960bc46b63`.
The phone receipt is `/data/local/tmp/asoft-rd-probe-04/run/result.json`,
4,333 bytes, SHA-256
`07a7ec7e0c38aafef571fac2125ff4f60a3b3e88510e8a5384e9a2b7137f54ea`.
The attempt remains `INCOMPLETE` and the remount is closed.
