from pathlib import Path
import datetime,json,os,subprocess
m={x.split(':',1)[0]:x.split(':',1)[1].strip() for x in Path('/proc/meminfo').read_text().splitlines()}
print('FIRSTBOOT CONDITIONS '+datetime.datetime.now(datetime.timezone.utc).isoformat())
print('MemTotal_kib='+m['MemTotal'].split()[0]+' MemAvailable_kib='+m['MemAvailable'].split()[0]+' floor_kib=3932160')
s=os.statvfs('/data/local/tmp')
print('free_bytes='+str(s.f_bavail*s.f_frsize)+' floor_bytes=4500000000')
for name in ['status','capacity','temp','health']:
 p=Path('/sys/class/power_supply/battery')/name
 print('battery_'+name+'='+(p.read_text().strip() if p.exists() else 'absent'))
for name in ['usb','ac','wireless']:
 p=Path('/sys/class/power_supply')/name/'online'
 print(name+'_online='+(p.read_text().strip() if p.exists() else 'absent'))
print('memory_PSI='+Path('/proc/pressure/memory').read_text().strip().replace('\n','; '))
try:
 r=subprocess.run(['/system/bin/dumpsys','thermalservice'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
 lines=r.stdout.decode(errors='replace').splitlines()
 chosen=[x.strip() for x in lines if 'Thermal Status:' in x or 'Thermal Status Override:' in x]
 print('thermal_service_exit='+str(r.returncode)+' selected='+json.dumps(chosen))
except Exception as e: print('thermal_service_error='+type(e).__name__)
print('guard_work_exists='+str(Path('/data/local/tmp/pixel-firstboot-guard-e9cc754').exists()))
