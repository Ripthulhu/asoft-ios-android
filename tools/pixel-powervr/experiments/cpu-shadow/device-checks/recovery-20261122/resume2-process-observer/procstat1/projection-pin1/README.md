# Corrected read-only status and final projection

This separate reader revision preserves the previously reviewed candidate and
all installed observer/launcher bytes. The independent reviewer identified
that using `cleanup.get('forced_descendants', [])` could turn an unavailable
field into an apparent observed empty list.

The corrected reader reports `forced_descendants_available=false` for a missing
or null field, and leaves `forced_pid_projection=null`. An actual empty list
sets availability true and produces an empty mapping. Invalid non-list values
or invalid PID entries are rejected. The compact terminal view includes the
availability flag. No inspection or cleanup acceptance rule changes.

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `observe_status.py` | 14,099 | `67b7df76b6c15f16fe76275131cfe37045fed68ab2411544523d5d7ed9f611a5` |
| `observe-status.command.txt` | 5,951 | `8f294a22e1e53095ecd26947a1a325949301d5663abc9600ffa46177ac6ab7af` |
| `observe-final.command.txt` | 5,958 | `c9e733f50cb8ed4f81bc3096be3534555da623c1bd1a5c7c203f4d66312841df` |
| `observe-final-json.command.txt` | 5,963 | `144e75387b861176cd15b80009fd163b48ae067de1ab8f50ed365214667648eb` |

All commands verify the installed procstat1 observer source and read only its
own receipts/events plus the new inspection's selected metadata. No native
stderr, guest serial, raw guest output, unrelated command lines, or app
inventory is read. The final query checks exact event bytes/count/SHA-256 and
the coherent source/ready/summary/exit chain before classifying any cleanup PID.

Default terminal output has at most 69 logical lines. The full JSON query has
an explicit 128-KiB output bound and reports omissions from bounded selected
event points. A cleanup PID supplies no start ticks: unmatched numbers remain
unclassified, and multiple observed identities for the same number remain
ambiguous. Observation completion is independent of inspection acceptance.

Twelve focused checks passed, including actual final-collector fixtures for
missing/null, present-empty, and invalid forced-descendant schema; ambiguous
PID reuse; selected event omissions; line bounds; and exact compressed command
reconstruction. See [projection-validation.json](projection-validation.json)
and [projection-tests.log](projection-tests.log). The generated commands use
AST-equivalent formatting of the reviewed source to stay below 6,000 bytes;
the AST equality is checked by the builder and tests.

The [independent projection review](independent-projection-review.json) passed
for the exact source, all three decoded commands, and the twelve-test record.
The review receipt is 3,596 bytes, SHA-256
`074f8823e23cad006b74983ea0afadc9f7e9e8f76609742aad1f00ee0b2a141d`.
