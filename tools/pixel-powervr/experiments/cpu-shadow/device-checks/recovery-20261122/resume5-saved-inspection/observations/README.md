# Resume5 read-only inspection observations

These additive readers consume the actual resume5 owner, the released inspector
pair, and the independently reviewed fresh preflight. They do not install
sources, launch a process, run a VM or native tool, mount a filesystem, replay a
journal, repair anything, change the memory gate, or advance preparation.

The fresh preflight was observed at `2026-11-22T20:44:38.734136+00:00`: 9,069
bytes, SHA-256 `4630b5dc921d3bee52d4805cc829e3624144b763d27b53937443e43c69db44f6`.
Its selected metadata and independent review are in the parent package. The
owner source is 60,564 bytes,
`dbb570dc9b3354a5d7c4eb218883ab22f25afe24757c429e46cc7c04de1baa63`.
No future inspection result hash, process identity or success is assumed here.

## Released status and accepted-result pins

`independent-status-reader-review.json` releases the exact
`observe_inspection.py` source and its four commands. The source is 11,676
bytes, SHA-256
`8af888afaf98bf154dd332f0247b19ae95053ee0e26543edc2ee278bf3b881de`.

| Command | Bytes | Purpose |
| --- | ---: | --- |
| `observe-inspection.command.txt` | 5,247 | Running or final lifecycle, native VM, host result and input-preservation metadata |
| `observe-success-pins-0.command.txt` | 5,263 | Accepted-success receipt pins 0–4 |
| `observe-success-pins-1.command.txt` | 5,263 | Accepted-success receipt pins 5–9 |
| `observe-success-pins-2.command.txt` | 5,263 | Accepted-success receipt pins 10–13 |

The port retains the reviewed resume4 status, source loader, process-identity
logic, success acceptance, and all fourteen reads. The additional preservation
check calls the exact new owner's `resume4_failure_inputs()` and verifies every
returned binding was included in the fresh preflight. It reports the eleven
resume4/JIB pins along with the older preserved evidence. Successful pin rows
print path/length, full hexadecimal digest, and all 32 decimal digest bytes on
separate lines for the narrow terminal.

Status is observation only. A reported live child or absent result does not
grant success. The pin modes require accepted outer exit zero, clean unforced
reaping, absent recorded wrapper/inspector identities, exact launch/preflight
links, unchanged firstboot and historical evidence, and the released owner's
complete `accept_result()` validation.

## Released canonical proof projections

The two richer source files are frozen after thirteen focused tests and are
released by `independent-proof-reader-review.json` (4,266 bytes,
`73e02869264ce2c17c7686b407b26a46747297a47139582501850be1c333e1ba`).
`proof-validation.json` and `focused-tests.log` record the authored fixtures
and exact file hashes. Source release is not a physical inspection pass.

| Command | Bytes | Selected output |
| --- | ---: | --- |
| `observe-proof-root.command.txt` | 5,835 | Root header hashes/attributes/geometry, journal metadata, and the exact root classification including the NeedInit transition proof |
| `observe-proof-data.command.txt` | 5,835 | Data header and journal metadata and its own unchanged classification |
| `observe-proof-fsck.command.txt` | 5,791 | Both fsck verdicts/log hashes and lengths, read-only/no-mount/no-replay/no-repair fields, policy/GPT linkage and host/current input preservation |

`observe_journals.py` is 12,144 bytes,
`7d3afc1ab7c69e28fabef081735273ac03186d11e70be519c793c3201c0c80de`.
`observe_fsck.py` is 11,846 bytes,
`f97f7878a4d81f9d371ee78b16bf23fb642b9012ebb4d86f2b390762896c5fde`.

Every view performs identical completed-result validation. It requires an
actually accepted, cleanly reaped outer result and absent recorded processes;
binds host result copies, expected policy, session, VM, launch and raw outputs;
calls the released owner acceptance function; and loads the exact hash-bound
canonical inspector and partition auditor to call `guest_pass()` over the raw
guest JSON and both complete fsck logs. The canonical inspector checks the
strict root proof and the actual fsck verdicts. The projection does not
substitute selected output fields for those validators.

Bound historical inputs are checked before and after the projection, and every
captured current receipt/log is compared again before any output. Shared loader
and preservation functions have identical ASTs to the released status source;
the two views also share identical complete acceptance functions.

Only allowlisted scalar metadata and hashes are printed. Raw fsck text, raw
headers/JIB/journal payloads, UUIDs and private file inventories stay on the
phone. Missing metadata is unavailable rather than positive evidence. The root
transition's `baseline_jib_identical=false` and
`baseline_journal_metadata_identical=false` are preserved exactly. The query
does not recompute full disk hashes: it validates and labels the trusted host's
recorded full-chain preservation separately from the query's current metadata
checks.

These richer views require accepted success. A failed inspection remains a
failure, and its specific diagnostic boundary must be handled with a separate
bounded query after the actual result is known.

## Released failure projection and preserved template

`failure/observe_guest_boundary_UNRELEASED.py` is a separate failure-only
projection based on the reviewed resume4 boundary query. It is 12,702 bytes,
`7e868aa3d5ee6ac245828a4dd472cfb19e814573be740e4344a19a92067f9ce1`.
The expected wrapper identity, exact host error and failed host result
length/hash are all `None`; the template refuses before loading the owner.
The preserved template remains unbound. The separate finalized source below
uses the actual independently reviewed failed outcome.

It retains exit 2, accepted false, clean native VM, unchanged backing/guard
and absent recorded process requirements. Its output contains bounded error
codes, root/Data classification and transition fields, volume attributes and
geometry, journal scalars, fsck verdicts and known diagnostic sizes. Native
cleanup is explicit. It exports no raw logs, headers, JIBs or private inventory,
and it grants no inspection success. Additional resume2/resume4/JIB bindings
and final metadata/input/absence checks preserve the fresh scope.

`failure/observe_guest_boundary.py` is 12,903 bytes,
`a6097497b9df8282a41a740125ab197bcba56df5386a8e7bf35803fd05577acd`.
Its only changes from the reviewed template are the actual wrapper identity
`3218/10596300`, the actual generic guest-inspection host error, and the actual
7,269-byte host result hash
`08ab06ea5b0e1d46a168935df1dbaabeda0daa7ab569b1e001f61e17d7cfc828`.
All 32 digest bytes came from the independently reviewed normal receipt
collector. `actual-result-selected.json` and
`independent-failure-binding-review.json` preserve that evidence linkage.

The released `failure/observe-guest-boundary.command.txt` is 5,998 bytes,
`ed1aef6064ca220737283d6625f6694bd2a60aa7e789af22304337ad66a77954`.
It uses a fixed zlib transport payload to remain within 6,000 bytes, with exact
source length/hash validation before compilation. Its failure-only and
recorded-process absence gates remain unchanged. Source release does not claim
that the phone query has run or that any inspection passed.

## Additional corroborating receipt reader remains unbound

`observe_nine_receipt_pins_UNRELEASED.py` ports the earlier nine-receipt reader
to fresh resume5 paths. `IDENTITIES=None` makes it refuse before receipt reads.
It needs the actual independently reviewed completed wrapper, inspector, QEMU
and observer PID/start-tick pairs. No runnable command was generated.

Once those identities exist, a separate finalized source and review can collect
the outer exit, host result, VM result, guest result, policy and the observer's
ready/exit/summary/events pins. Those pins are corroborating metadata, not an
inspection pass. The original template and all historical readers are retained.

## Reproduction and focused verification

`build_observation_package.py` builds commands only, using the reviewed actual
preflight and exact owner source. It refuses different existing outputs and
commands exceeding 6,000 bytes. `query-manifest.json` binds all seven command
payloads and their explicit view arguments. It splits presentation branches
without changing the common completed-result validators.

The focused test module covers the real canonical authored-root proof and both
fsck logs, forged/missing proof, missing/altered fsck diagnostics, forced or live
recorded processes, wrong source pins, before/after input and metadata changes,
allowlist privacy, null/unavailable semantics, shared validator ASTs, and exact
transport reconstruction. It uses authored sparse fixtures and temporary
metadata only; no phone or image payload was accessed by the tests.

```sh
python -B -m unittest -v test_observations.MetadataFixture test_observations.ScopeAndTransport
```
