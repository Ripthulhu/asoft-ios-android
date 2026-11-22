# Native preparation after whole-image acceptance

The recovered layer passed the [whole-image inspection](WHOLE-IMAGE.md).
Persona and activation then passed on separate copy-on-write descendants.
Both native helpers had natural exit, all three native witnesses, and
clean unforced cleanup. The frozen QCOW2 integrity checker passed each layer.

| Accepted stage | Phone attempt | Stage receipt SHA-256 |
| --- | --- | --- |
| Persona | `asoft-continue-02/attempts/08-0001` | `301156a4ce4e0408efa14313ac424dafc909555bffb1700d47097b9202112b65` |
| Activation | `asoft-continue-02/attempts/09-0001` | `01400863d5f1ca5520ed0d48ca834f7f493d17b3b4350361bf4c9fa66f44e3ac` |

The first persona job returned exit zero, but its immediate cleanup killed
an owned descendant. That attempt remains rejected and retained at
`asoft-continue-01/attempts/08-0001`, VM receipt SHA-256
`2b4e2c6c5fb34af8528621d124a1f94cd2987df7e1796263f1b8159c5d0c3640`.
The accepted retry allowed up to eight seconds for owned descendants to
exit naturally. The no-force gate remained in effect.

The new preparation owner operates under the existing nonwriting
preparation lease. Its work tree is separate from the original
preparation and recovered layers. The native app copy, app audit, and
guarded GPU boot are subsequent stages. No app or APK result is claimed
by this checkpoint.
