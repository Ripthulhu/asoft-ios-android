# Resume5 result: root journal classification passed; Data journal is nonempty

The single resume5 inspection completed with `INCOMPLETE`. The supervising
owner and inspector exited 2 because **Data failed `nonempty_journal`**. The
native VM completed normally, and every recorded owner, inspector, QEMU and
observer identity is absent. This is a filesystem acceptance refusal, not an
observed native-execution or process-cleanup failure.

The result-bound, read-only failure projection was observed at
**2026-11-22T21:11:04.460470+00:00**. Its actual host result is **7,269 bytes**,
SHA-256 `08ab06ea5b0e1d46a168935df1dbaabeda0daa7ab569b1e001f61e17d7cfc828`.
All nine retained receipt sizes/hashes and all 288 displayed digest bytes were
independently checked. See [the selected receipt bindings](physical-observations/receipt-pins-selected.json),
[their independent review](physical-observations/independent-receipt-pins-review.json),
and [the actual failure projection](physical-observations/guest-boundary.jpg).

## What the inspection established

| Check | Actual result |
| --- | --- |
| Read-only disk attachments | Confirmed |
| GPT verification and saved/baseline equality | Passed |
| iOSRoot raw journal gate | Passed `ROOT_AUTHORED_NEEDINIT_TO_INITIALIZED_EMPTY` |
| iOSRoot journal cursors | `start = end = 512` |
| Data raw journal gate | Refused `nonempty_journal` |
| Data journal cursors | `start = 512`, `end = 614400` |
| Data journal size | 8,388,608 bytes |
| Data header / block-list header sizes | 512 / 49,152 bytes |
| Data header checksum | Stored and independently computed values both 195,764,962 |
| Forced read-only filesystem checks | Neither ran; both expected log files are absent |
| Mount / replay / repair | None performed |
| Native initialization / execution / final SVC | All three witnesses present |
| Native VM exit and cleanup | Exit 0, natural completion, clean and unforced |
| Full backing chain, preparation and guard | Unchanged |
| Boot, GPU and application gates | Remain incomplete / closed |

The root result exercises the exact new classification on the physical saved
image. It requires the complete authored baseline JIB, its complete zero
baseline journal, the sole NeedInit flag transition, unchanged corresponding
root volume headers and a valid initialized-empty current journal. The proof
correctly reports `baseline_jib_identical=false` and
`baseline_journal_metadata_identical=false`; the transition is explicitly
classified rather than reported as byte equality. This raw result does not
replace the root filesystem check, which was never reached.

Data's cursors identify a 613,888-byte active interval without wraparound.
The matching header checksum does not validate its transaction contents or
prove that replay would succeed. [Apple TN1150](https://developer.apple.com/library/archive/technotes/tn/tn1150.html)
defines unequal start/end cursors as a nonempty journal and requires replay
before relying on the volume's consistency. The current inspector therefore
correctly stops before either filesystem check. No corruption conclusion or
acceptance-policy relaxation follows from this result.

## One actual inspection, preceded by one memory refusal

The first execution-command submission refused on the unchanged 2,816 MiB
MemAvailable floor before creating any execution artifact. A subsequent
read-only probe at **20:55:19.691688 UTC** found all seven execution paths
absent, 3,491,127,296 bytes MemAvailable and the same live, fresh observer.
The second submission started the only actual inspection at
**20:55:38.023625 UTC**. No memory compaction, cache drop, process termination,
manual thaw or policy change was performed during resume5.

| Recorded process | PID / start ticks | Final state |
| --- | --- | --- |
| Supervising owner | 3218 / 10596300 | Absent |
| Inspector | 3219 / 10596334 | Absent; reaped by owner |
| Native QEMU helper | 4784 / 10606734 | Absent; exit 0, unforced |
| Independent observer | 31097 / 10563710 | Absent; exit 0 |

The VM reports `VM_OBSERVATION_COMPLETE`, started
**20:57:22.061220 UTC**, and finished **20:57:46.561855 UTC**. Its reported
elapsed field is 20.092154703001142 seconds. This is retained as reported,
without substituting a duration calculated from its wall-clock timestamps.
The inspection finished **20:58:05.315390 UTC**. Its host error was:

> ValueError: guest inspection incomplete; retained metadata classifies the boundary

The final status observations at **20:58:46.670734 UTC** and
**21:00:02.936994 UTC** both show all three inspection identities absent.
The nine-receipt reads at **21:04:36.721478 UTC** and **21:07:50.117013 UTC**
also checked all four recorded identities absent before and after stable
metadata reads. They are distinct observations, not an atomic cross-page
snapshot. The failure projection rechecked the owner/inspector/QEMU absence,
the actual host result, source bindings and preservation inputs.

## Observer evidence and limits

The observer's final full projection at **21:08:12.050075 UTC** reports exit 0,
no summary errors, no unresolved receipt-publication gaps and no remaining
observed identities. It recorded 2,727 samples, 44 events and 10 identities.
It also reports three read gaps, zero sampling gaps, 133 discovery scans and
a maximum discovery scan interval of 326,163.110562 ms. These facts do not
establish uninterrupted descendant discovery. See [the selected full final
observation](../resume5-process-observer/procstat1/physical-observations/observer-final-json-selected.json)
and [its independent review](../resume5-process-observer/procstat1/physical-observations/independent-observer-final-json-evidence-review.json).

## Preserved corrections

Original evidence remains unchanged; the following interpretation and
transcription corrections are additive:

- Two final-status screenshot filenames say `wrapper-present`, but their
  pixels show the wrapper absent. The [interpretation correction](physical-observations/wrapper-presence-interpretation-correction.json)
  and both corrected selected final records document the actual state.
- The original early refusal/running selections placed `native` inside `vm`.
  The released query emits `native` at the top level. The new `*-selected-pin1`
  records and [schema correction review](physical-observations/independent-observation-schema-correction-review.json)
  preserve that distinction; the scalar null values were unchanged.
- An earlier chat transcription duplicated one hex character in the observer
  events digest. The complete 32-byte verification establishes the actual
  18,872-byte receipt as
  `5190b81b28170fc749b4caa2b40938213b597280746067dab2eaf318fc5aea0d`.
  No phone receipt changed.

## Continue from here

**Do not relaunch the accepted firstboot, any completed saved inspection,
the JIB diagnostic, resume5 preflight or a completed observer.** Preserve all
current images, receipts, installed sources and prior failure evidence.

The next technical work concerns Data's active journal transactions. A bounded
read-only diagnostic can validate their structure and target ranges without
altering the saved image or exporting raw payloads. Any later recovery must
use a separately reviewed fresh copy-on-write descendant, preserve and bind
the complete original chain, and earn a new clean filesystem result. The
current inspection's no-replay policy and rejection of a nonempty journal
remain unchanged. No journal replay or recovery has been implemented or run
at this result checkpoint.

Native EL0 plus kernel TCG remains the required execution design. The GPU path
is incomplete, and no APK is released by any result in this directory. Public
evidence contains reviewed source and selected metadata only; raw Apple images,
raw journal payloads, private file inventories and raw guest logs remain off
the repository.
