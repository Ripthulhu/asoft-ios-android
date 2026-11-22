# Additive runtime finalization

The source-only checkpoint and its review remain frozen. Its `None` preflight
constants describe that checkpoint and will not be rewritten.

After the parent reports the actual accepted resume4 preflight byte count,
SHA-256 and observation time, `finalize_runtime.py` produces a fresh
`runtime-binding/` directory. It copies the observed binding, substitutes only
the two preflight constants into the retained readiness template, and creates
the exact compressed launch and readiness commands. The installed observer,
installed launcher, seven installation commands and three final projections
remain byte-identical to their reviewed versions.

The builder itself performs no phone action. Its emitted commands require
independent review; the phone launcher still validates the actual new
preflight receipts, accepted clean reap, source hashes and unused execution
paths. The separate inspection launcher will bind the subsequent actual live
observer readiness receipt.
