# Recorded memory operations before resume1 execution

These are the exact sources and bounded commands used during this recovery,
preserved for review. They are not the next continuation commands. Resume1 now
has a live or completed owner and must be inspected through its read-only
status command before any further action.

`compact_one_cached.py` binds a specific previously observed frozen cached
process identity. Its physical invocation returned
`COMPACTION_NOT_REQUESTED_LOW_FREE_SWAP`; no compaction was requested and no
action receipt was created. The process identity is historical, not a current
target selection.

`reclaim_clean_caches.py` took the existing preparation lock, checked that new
boot state was absent, reserved an exclusive receipt, called `sync`, and issued
one `drop_caches=3` request. It completed at 14:39:24 UTC with unchanged original
input stat metadata and unchanged global OOM-kill counter. MemAvailable rose
from 3,848,491,008 to 4,000,583,680 bytes at the two samples. These system-wide
measurements do not isolate all concurrent memory changes. No process kill,
manual thaw, threshold reduction or persistent policy change was requested.

The cache request's receipt is
`/data/local/tmp/pixel-gpu-transfer-sxtv33sh/kernel-clean-cache-reclaim-resume1-01.jsonl`.
Preserve it; do not replay this operation. A later, independent launcher check
observed enough memory and started the firstboot owner.

See the independent review JSON files in the parent directory and
`../physical-observations/memory-and-launch.json` for selected observations and
screenshots. Clean cache reclamation follows the kernel's documented one-time
debugging mechanism: [drop_caches](https://docs.kernel.org/admin-guide/sysctl/vm.html#drop-caches).
It can cause additional I/O and CPU work as caches rebuild.
