# Fresh phone memory after the firstboot preflight

The user requested safe RAM reclamation and confirmed the Pixel has 16 GB RAM.
At **2026-11-22 11:54:20 UTC**, a read-only `/proc/meminfo` snapshot reported
**4,623,605,760 bytes (4,409.41 MiB)** MemAvailable, exceeding the unchanged
**4,026,531,840-byte (3,840 MiB)** firstboot launch floor by **597,073,920 bytes
(569.41 MiB)**. No reclaim command, app trim, process termination, cache drop,
policy change or firstboot launch was performed by this snapshot.

The kernel reported MemTotal **15,925,732 KiB (15.19 GiB)**. This is usable
kernel-managed RAM, distinct from installed hardware capacity. The earlier
11:47:11 UTC snapshot was below the floor; this fresh observation supersedes
that resource decision only. It does not supersede any audit or boot gate.

The exact source and shell command are retained beside the original screenshot.
The JSON is a selected screenshot transcription; it is not represented as a raw
phone-exported receipt. Firstboot still requires a fresh launch-time resource
check and the unchanged successful guard/audit/checkpoint boundary.

The new request authorizes safe, measured reclamation if needed. No unrelated
application is to be killed, and no RAM threshold or system protection is to
be changed. Since available RAM already exceeded the floor, no reclamation was
needed at this boundary.

## Memory interpretation

Linux defines MemAvailable as an estimate of allocation headroom without swap,
including a portion of reclaimable file pages and slab. Dropping clean caches
can increase MemFree substantially without a corresponding increase in
MemAvailable. That is why a cache drop was not performed just to inflate free
RAM when the actual gate was already met.

Primary references:

- https://docs.kernel.org/filesystems/proc.html#meminfo
- https://docs.kernel.org/admin-guide/sysctl/vm.html#drop-caches
- https://developer.android.com/topic/performance/memory-management

## Follow-up conditions at 11:58:19 UTC

The separate read-only conditions command reported **4,340,744 KiB
(4,239.01 MiB)** MemAvailable, still above the 3,840 MiB launch floor;
74,344,148,992 bytes were free. Battery status was `Not charging`, capacity
74, raw temperature 285 and health `Good`; USB online was 1. Android's thermal
service exited zero and reported `Thermal Status: 0`. Memory PSI averaged
0.00 for both `some` and `full` over 10 and 60 seconds (300-second averages
0.01). The guard work remained absent. These are the selected physical
conditions, not a claim of future thermal or resource behavior. No memory
reclamation or firstboot execution was performed by this command.
