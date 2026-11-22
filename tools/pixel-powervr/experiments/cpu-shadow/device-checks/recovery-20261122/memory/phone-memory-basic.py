from pathlib import Path
import datetime
v={x.split(':',1)[0]:x.split(':',1)[1].strip() for x in Path('/proc/meminfo').read_text().splitlines()}
print('PHONE MEMORY '+datetime.datetime.now(datetime.timezone.utc).isoformat())
for k in ['MemTotal','MemAvailable','MemFree','Buffers','Cached','Shmem','AnonPages','Slab','SReclaimable','SUnreclaim','Unevictable','Mlocked','SwapTotal','SwapFree','SwapCached','Dirty','Writeback','PageTables','KernelStack']: print(k+'='+v.get(k,'absent'))
print('firstboot_floor_kib=3932160')
print('floor_met='+str(int(v['MemAvailable'].split()[0])>=3932160))