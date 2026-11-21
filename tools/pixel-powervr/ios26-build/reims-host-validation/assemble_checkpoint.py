import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile

SOURCE = Path('/workspace/scratch/4d73d97b75b7/reims-pixel-producer-runtime')
APP = Path('/workspace/scratch/4d73d97b75b7/asoft-ios-android-tests')
CHECKS = Path(__file__).resolve().parent
OUT = APP / 'tools/pixel-powervr/ios26-build/reims-host-validation'
PATCHES = APP / 'tools/pixel-powervr/patches/reims-host-validation'
BASE = '7bbcb042a71b57dba286d33638848c188e5d4799'
M2V = Path('/workspace/scratch/95f3cf369f81/metal2vulkan-producer-adoption')

def git(*args, cwd=SOURCE, env=None):
    return subprocess.check_output(['git', *args], cwd=cwd, env=env)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')

head = git('rev-parse', 'HEAD').decode().strip()
tree = git('rev-parse', 'HEAD^{tree}').decode().strip()
assert not git('diff', 'HEAD', '--', '.', ':!Cargo.toml')
assert not git('ls-files', '--others', '--exclude-standard')
assert not git('status', '--porcelain', cwd=M2V)
OUT.mkdir(parents=True, exist_ok=True)
PATCHES.mkdir(parents=True, exist_ok=True)

# Reproduce the exact source-content snapshot used by the final full gate, even
# though the same files have since been committed. The local Cargo override stays separate.
full = json.loads((CHECKS / 'workspace-check-final.json').read_text())
snap = full['source_after']
assert full['source_stable']
args = ['diff', '--binary', snap['head'], '--', '.']
args += [':!' + name for name in snap['untracked_sha256']]
assert digest(git(*args)) == snap['tracked_diff_sha256']
for name, sha in snap['untracked_sha256'].items():
    assert digest((SOURCE / name).read_bytes()) == sha
assert digest((SOURCE / 'Cargo.lock').read_bytes()) == snap['lock_sha256']

commits = git('rev-list', '--reverse', BASE + '..' + head).decode().splitlines()
names = git('format-patch', '--start-number=13', '--output-directory', str(PATCHES), BASE + '..' + head).decode().splitlines()
assert len(names) == len(commits)
series = []
for commit, name in zip(commits, names):
    path = Path(name)
    series.append({'path': path.name, 'sha256': digest(path.read_bytes()), 'bytes': path.stat().st_size,
                   'commit': commit, 'tree': git('rev-parse', commit + '^{tree}').decode().strip()})
with tempfile.TemporaryDirectory(prefix='host-patch-index-', dir=CHECKS) as temporary:
    env = dict(os.environ, GIT_INDEX_FILE=str(Path(temporary) / 'index'))
    git('read-tree', BASE, env=env)
    for name in names:
        git('apply', '--check', '--cached', name, env=env)
        git('apply', '--cached', name, env=env)
    reconstructed = git('write-tree', env=env).decode().strip()
    assert reconstructed == tree

paths = git('diff', '--name-only', BASE, head).decode().splitlines()
source_files = []
for name in paths:
    blob = git('show', head + ':' + name)
    assert blob == (SOURCE / name).read_bytes()
    source_files.append({'path': name, 'bytes': len(blob), 'sha256': digest(blob),
                         'git_blob': git('rev-parse', head + ':' + name).decode().strip()})
save_json(PATCHES / 'series.json', {'repository': 'https://github.com/alpersamur3/reims-vgpu',
    'base_commit': BASE, 'base_tree': git('rev-parse', BASE + '^{tree}').decode().strip(),
    'head_commit': head, 'head_tree': tree, 'patches': series})
(PATCHES / 'SHA256SUMS').write_text(''.join(row['sha256'] + '  ' + row['path'] + '\n' for row in series))
save_json(PATCHES / 'provenance.json', {'tested_content_matches_final_committed_source': True,
    'final_full_gate_source_snapshot': snap, 'patch_reconstruction_tree': reconstructed,
    'source_files': source_files, 'cargo_path_override_excluded': True,
    'metal2vulkan': {'commit': git('rev-parse', 'HEAD', cwd=M2V).decode().strip(),
                    'tree': git('rev-parse', 'HEAD^{tree}', cwd=M2V).decode().strip(), 'tracked_and_untracked_clean': True}})

labels = ['workspace-check-1', 'workspace-check-2', 'workspace-check-3', 'workspace-check-final',
          'focused-gate-repairs', 'focused-lifetime-repairs', 'alias-build-current',
          'alias-vulkan-final', 'alias-posix-final']
checks = {}
for label in labels:
    for ext in ['json', 'log']:
        shutil.copyfile(CHECKS / (label + '.' + ext), OUT / (label + '.' + ext))
    record = json.loads((CHECKS / (label + '.json')).read_text())
    assert digest((CHECKS / record['log']).read_bytes()) == record['log_sha256']
    checks[label] = {key: record[key] for key in ['command', 'exit', 'seconds', 'source_stable', 'log_sha256']}
for name in ['host-preflight.py', 'host-preflight.json', 'host-tools.json', 'sdl-sdk.json',
             'prepare_sdl_sdk.py', 'run_check.py']:
    shutil.copyfile(CHECKS / name, OUT / name)
shutil.copyfile(SOURCE / 'Cargo.lock', OUT / 'reims-Cargo.lock')
(OUT / 'reims-path-override.patch').write_bytes(git('diff', '--binary', 'HEAD', '--', 'Cargo.toml'))
positive = json.loads((CHECKS / 'alias-vulkan-final.json').read_text())
negative = json.loads((CHECKS / 'alias-posix-final.json').read_text())
build = json.loads((CHECKS / 'alias-build-current.json').read_text())
assert build['exit'] == 0 and build['source_stable']
assert positive['exit'] == 0 and positive['source_stable']
assert negative['exit'] == 1 and negative['source_stable']
assert positive['source_after'] == full['source_after'] == negative['source_after'] == build['source_after']
full_log = (CHECKS / 'workspace-check-final.log').read_text()
summary = next(line.strip() for line in full_log.splitlines() if line.lstrip().startswith('Summary ['))
positive_log = (CHECKS / 'alias-vulkan-final.log').read_text()
negative_log = (CHECKS / 'alias-posix-final.log').read_text()
assert 'ALIAS_PREFLIGHT=PASS provider=vulkan-import words_checked=8192 distinct_address=true' in positive_log
assert 'RESULT=REIMS_PRODUCER_RUNTIME_PASS' in positive_log
assert 'OPAQUE_FD_POSIX_ALIAS_UNQUALIFIED' in negative_log
assert 'VK_LAYER_KHRONOS_validation' in positive_log
validation_messages = {'vuid': len(re.findall(r'VUID-', positive_log)),
                       'synchronization_hazard': len(re.findall(r'SYNC-HAZARD', positive_log))}
assert validation_messages == {'vuid': 0, 'synchronization_hazard': 0}
save_json(OUT / 'validation.json', {'source_head': head, 'source_tree': tree,
    'nextest_summary': summary, 'validation_messages': validation_messages,
    'full_gate_passed': full['exit'] == 0, 'vulkan_import_alias_passed': True,
    'posix_mmap_alias_qualified': False, 'posix_negative_control_refused': True,
    'phone_tests_run_in_this_increment': False, 'producer_atomics_qualified': False,
    'checks': checks})
print(json.dumps({'source_head': head, 'source_tree': tree, 'patches': len(series),
                  'changed_source_files': len(paths), 'output': str(OUT)}, indent=2))
