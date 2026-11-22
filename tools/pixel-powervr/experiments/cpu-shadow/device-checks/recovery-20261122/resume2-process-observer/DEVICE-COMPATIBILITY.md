# Observer compatibility on the Pixel

The original files in this directory are a preserved reviewed candidate. They
were **not installed or launched**. A physical self-only query found that
`/proc/4573/task/4573/children` did not exist while PID 4573 was running. The
candidate's readiness check correctly requires this surface, so it must not be
used for the current phone.

The separate `procstat1/` revision uses bounded numeric `/proc` discovery. A
physical compatibility probe at **2026-11-22 15:49:17.066099 UTC** read all 894
numeric process `stat` records in 53.212 milliseconds. There were no vanished,
denied or malformed reads. Its own PID/start identity was 6426/8758185; parent,
PID/TGID and pending-signal field checks passed. Only aggregate counts and the
query's own identity were printed. The query wrote no phone files and sent no
signals.

The [missing-surface screenshot](physical-observations/proc-children-unavailable.jpg)
and [replacement-probe screenshot](physical-observations/proc-stat-surface-ready-154917.jpg)
are preserved with selected metadata and exact query sources. These observations
establish compatibility only. They do not prove an inspection pass, explain the
earlier forced PID 13344, or release downstream disk changes.

Use only a separately reviewed `procstat1` installation and execution binding.
Keep this first candidate, the failed resume1 work, the accepted firstboot, and
the fresh resume2 preflight intact. Observer source installation is distinct
from monitor launch, and monitor launch is distinct from inspection execution.
