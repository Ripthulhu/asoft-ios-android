#!/usr/bin/env python3
"""Preserve the completed reims native result and its earlier cache failure; run no test."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def fields(line):
    return dict(item.split('=', 1) for item in line.split()[1:] if '=' in item)


def collect(transfer, destination):
    install = json.loads((transfer / 'install.json').read_text())
    package = Path(install['package']).resolve()
    console = (transfer / 'runner-console.txt').read_text()
    matches = re.findall(r'^RESULT_DIRECTORY=(.+)$', console, re.M)
    assert len(matches) == 1
    run = Path(matches[0]).resolve()
    assert run.parent == package / 'results'
    destination.mkdir()
    for name in ['diagnostic.txt', 'summary.txt', 'context.txt', 'integrity.txt', 'engine-integrity.txt']:
        shutil.copyfile(run / name, destination / name)
    for name in ['install.json', 'runner-console.txt', 'runner-exit.txt']:
        shutil.copyfile(transfer / name, destination / name)
    text = (run / 'diagnostic.txt').read_text()
    events = [fields(line) for line in text.splitlines() if line.startswith('OWNER_EVENT ')]
    return {
        'package': str(package), 'result_directory': str(run),
        'runner_exit': int((transfer / 'runner-exit.txt').read_text()),
        'owner_exit': int(re.search(r'^OWNER_EXIT=(\d+)$', console, re.M)[1]),
        'install': install, 'context': (run / 'context.txt').read_text().splitlines(),
        'events': events,
        'selected_lines': [line for line in text.splitlines() if line.startswith((
            'REIMS_', 'OWNER_', 'NATIVE_GPU_', 'RESULT=', 'native-el0:'))],
        'files': {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in sorted(destination.iterdir())},
    }


def main():
    if len(sys.argv) != 4:
        raise SystemExit('usage: collect-device-evidence.py CURRENT_TRANSFER FIRST_TRANSFER OUTPUT_PARENT')
    out = Path(tempfile.mkdtemp(prefix='reims-native-gpu-', dir=sys.argv[3]))
    success = collect(Path(sys.argv[1]), out / 'cache-corrected')
    initial = collect(Path(sys.argv[2]), out / 'initial-cache-failure')
    assert success['runner_exit'] == success['owner_exit'] == 0
    assert [e['phase'] for e in success['events']] == [
        'READY', 'ENTRY', 'CODE_MAP', 'DATA_FAULT', 'DATA_MAP', 'COMPLETE']
    assert 'RESULT=REIMS_NATIVE_GPU_ONE_REGION_PASS' in success['selected_lines']
    assert initial['runner_exit'] == 1 and initial['owner_exit'] == 134
    assert not initial['events']
    record = {'status': 'REIMS_NATIVE_GPU_ONE_REGION_PASS', 'diagnostics_executed_by_collector': False,
              'success': success, 'initial_cache_failure': initial}
    (out / 'device-record.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    brief = {k: success[k] for k in ['package', 'result_directory', 'runner_exit', 'owner_exit']}
    brief.update({'evidence_directory': str(out), 'record_sha256': sha(out / 'device-record.json'),
        'diagnostic_sha256': success['files']['diagnostic.txt']['sha256'],
        'diagnostic_bytes': success['files']['diagnostic.txt']['bytes'],
        'initial_diagnostic_sha256': initial['files']['diagnostic.txt']['sha256'],
        'native_phases': len(success['events'])})
    print(json.dumps(brief, indent=2))
    for line in success['context']:
        print('CONTEXT ' + line)
    for line in success['selected_lines']:
        if line.startswith(('REIMS_ALLOCATION ', 'REIMS_NATIVE_GPU=', 'OWNER_TREE_CLOSED ', 'RESULT=')):
            print(line)


if __name__ == '__main__':
    main()
