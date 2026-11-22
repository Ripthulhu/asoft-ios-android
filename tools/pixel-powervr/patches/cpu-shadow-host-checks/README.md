# CPU-shadow probe clock correction

The first increment fixes the five direct `Instant::now` calls that stopped the
previous all-feature Clippy check. It uses the existing `OsClock::now_awake`
service and subtracts elapsed awake time from the original per-command budget.
The submission callback, shared-event poll and command-completion wait share
one budget; the second command starts its own budget at the same point as
before. The Linux/Android probe keeps its suspend behavior because both the old
`Instant` path and the existing awake clock use `CLOCK_MONOTONIC`. The guest's
sleep-inclusive monotonic clock is not used.

The next full check exposed four more direct clock calls in the alias and
lifetime examples. The second increment makes the existing awake-time API
publicly reachable from those separate example crates and uses it there. It
retains their timestamp locations and wait durations. Clock arithmetic, device
capability answers, GPU operations and the already qualified phone package are
unchanged; the Rust clock API gains public access to the existing service.
The third increment expresses the tile diagnostic's four-byte comparisons
with fixed-size array chunks, as required by the pinned Clippy version.
The fourth groups the heap mapping, file and expected-byte references into a
borrowed backing value and documents the heap and rebind public entry points;
all commands and comparisons remain the same.

## Apply

Reconstruct the Reims source through the CPU-shadow capability patch and the
saved `approved-formatting.patch` from
`experiments/cpu-shadow/host-checks/xtask-bda933b-clippy-clock-stop`. The complete
base tree must be `c603324e4e499668f5ae4133cfe14b39f4491275`, the saved
`bda933b9592262dd85d8723e5c47cfe6886b6c25` checkpoint.

Verify `SHA256SUMS`, then apply the four raw Git patches in `series.json` order
with `git apply --index`. The first tree must be
`963542a2d364df5cb975c0cb0aae600995777f97`; the second must be
`6bfcb3a42e85970b2a32e405ed9150728bea49d7`. The final tree must be
`bc5c683847cd8f9065e31b7970659553d36bf096`.
Local Cargo dependency paths are configured separately and are excluded from
the patches. The source manifests record their local commit identities;
those commit IDs differ from the saved originals, while the source trees match.

## Evidence

Every restored Reims and metal2vulkan intermediate tree matched its saved
manifest. Forward application in a separate Git index reproduced the candidate
tree, reverse application checked, and the exact diff passed independent source
review. The full host check runs separately and its outcome must be read from
the new check receipt. Source reconstruction and review alone are not a host
check pass, an iOS boot or GPU-path completion.
