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
preparation and recovered layers. The native app-copy stage also completed on this chain. The guest counted
255 bundles in `/Applications`. The host accepted the native, cleanup, and
QCOW2 checks.

| App preparation evidence | SHA-256 |
| --- | --- |
| `asoft-continue-02/attempts/10-0001/stage-result.json` | `65e9e6071f62d6f4f369a9baca22913dcff85cec428748964d4a17cb1ef605c0` |
| App QCOW2 layer | `16eb0586bed0f4314c97ad56f51fa54e1f652ce9ce7e9ab16d3626d5325f35b3` |
| App trust cache | `5b545a74f29247c9ec95d0132dc650df25acce4f360c252ca74ffd97bf42abdd` |

The first independent copy audit rejected the old iOSRoot alternate header
at the activation attachment. Its guest record SHA-256 is
`437add73905d8636a13a20119fde2987f74338faa24cba40320b2825ed06eae4`.
A direct read of the activation layer found the exact alternate header
previously accepted during whole-image inspection and a clean primary header.

The revised read-only audit binds that exact alternate hash at the iOSRoot
partition geometry. Scope tests accepted the exact activation header and
rejected a changed alternate, an unclean primary, and use at a different
partition offset. The original app-copy comparison and fsck gates still
apply. The [independent app audit and native GPU preparation](APP-AUDIT.md)
passed on the recovered chain. Physical iOS GPU boot is the next boundary.
