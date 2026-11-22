"""Print a compact live recovery summary from existing receipts; no writes."""
import datetime
import json
from pathlib import Path

BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
PREP = Path('/data/local/tmp/pixel-prep-e9cc754')
FIRSTBOOT = Path('/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1')
INSPECTION = Path('/data/local/tmp/pixel-saved-audit-e9cc754-resume1')

def read(path):
    return json.loads(path.read_text())

def present(identity, key='starttime'):
    try:
        body = (Path('/proc') / str(identity['pid']) / 'stat').read_bytes()
    except FileNotFoundError:
        return False
    return int(body[body.rfind(b')') + 2:].split()[19]) == identity[key]

boot = read(FIRSTBOOT / 'result.json')
checkpoint = read(PREP / 'checkpoints/ios26-firstboot.json')
boot_owner = read(BASE / 'ios26-firstboot-owner-resume1/exit.json')
result = read(INSPECTION / 'result.json')
owner = read(BASE / 'ios26-saved-inspection-resume1-owner/exit.json')
start = read(BASE / 'ios26-saved-inspection-resume1-owner/owner.json')
vm = read(INSPECTION / 'a1/vm-result.json')
child = read(INSPECTION / 'a1/vm.child.json')

print('NATIVE IOS26 RECOVERY CHECKPOINT')
print('observed_utc=' + datetime.datetime.now(datetime.timezone.utc).isoformat())
print('firstboot_attempt=' + Path(checkpoint['attempt']).name)
print('firstboot=' + boot['status'])
print('firstboot_owner_accepted=' + str(boot_owner['accepted']))
print('saved_inspection=' + result['status'])
print('inspection_owner_accepted=' + str(owner['accepted']))
print('inspection_leader_exit=' + str(vm['cleanup']['exit_code']))
print('forced_descendants=' + str(vm['cleanup']['forced_descendants']))
print('disk_chain_unchanged=' + str(result['full_backing_chain_unchanged']))
print('prior_preparation_unchanged=' + str(result['preparation_and_guard_unchanged']))
print('inspection_owner_live=' + str(present(start['wrapper'])))
print('inspection_runner_live=' + str(present(start['runner'])))
print('inspection_qemu_live=' + str(present(child, 'start_ticks')))
print('gpu_path_complete=' + str(result['gpu_path_complete']))
print('Next gate: accepted saved-filesystem inspection.')
print('Failure evidence preserved; no downstream stage released.')
