# Read-only Data diagnostic observations

These readers use the exact reviewed host source and its pinned pure parser.
They never invoke the host's main/extraction functions, start a native tool or
guest, or change filesystem/inspection acceptance. The host author retains
source staging and the separate diagnostic launch under `../host/`.

## First status and actual-result binding

`source-binding/observe-result-pin.command.txt` is the compact first query.
Its prepared command is 5,455 bytes; independent review is recorded separately.
The source-only binding is to the exact 51,923-byte host source with SHA-256
`85194af9e14f68e16d1990e79603060644a892c772adafc51dc52777055c77c9`.

If `result.json` does not yet exist, the reader reports only output/session
presence and explicitly leaves owner state and completion unknown. A completed
binding requires fixed scope, clean four-child exit receipts, current absence
of the diagnostic owner and recorded child PIDs, all old inspection identities
absent, and unchanged metadata, tooling and backing-chain identities. The
historical tool records lack start ticks; any current reuse of a child PID
causes a refusal instead of an invented process identity.

The first query validates recorded parser fields through the host's allowlist
but does not reread the retained8MiB payload. Its output explicitly says
`retained_payloads_reverified=false` and `pure_parser_recomputed=false`.
It prints the result path/length, full hexadecimal digest and all32 decimal
digest bytes on separate lines for screenshot verification.

## Detailed projection after actual evidence

Keep `observe_data_journal_UNRELEASED.py` unchanged with both pins unset until
the actual source/result observation is independently reviewed. Save that
selected observation within this diagnostic directory, using the exact output
fields plus a `result` object containing `path`, `bytes`, `sha256` and
`digest_bytes`. Add `independently_reviewed=true` and an `independent_review`
relative path only after the visual evidence review.

Then run locally:

```sh
python -B observations/build_projection.py finalize PATH_TO_REVIEWED_OBSERVATION_JSON
```

The finalizer writes a fresh `result-binding/` directory with one summary and
four bounded list-page commands. It checks all32 observed digest bytes and
changes only the two source/result bindings. AST unparse changes formatting
to keep each command below6,000 bytes; exact generated sources and commands
still require independent review before phone use. No actual-result commands
exist at preparation time. Synthetic command-size tests create no production
result-binding directory.

Every detailed query validates the four exact extraction commands and retained
command/exit/stdout receipts, rereads the two headers/JIB/journal, reruns the
pinned parser and requires identical analysis. It rereads retained hashes and
metadata after validation. Summary and page modes project only the allowlisted
scalars; no payloads, targets, pointers, sequence numbers or private inventories
are printed. Native extraction completion and nested parser `INCOMPLETE` remain
separate; neither status is a filesystem or replay-safety verdict.

See `projection-validation.json` for the eleven narrow synthetic reader tests
and exact file/command pins. Both unbound templates and the host author's
original unreviewed draft are preserved.
