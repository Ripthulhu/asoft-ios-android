"""Read-only bounded projection of the failed capability probe's built-in help."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat

BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
WORK = BASE / 'ios26-hfs-header-capability-resume3'
SOURCE_SHA = '7029bc14ad7ae5a056caadfd1932d8f4b4eec738ad68fef2bdac67e961c607e8'
RESULT_PIN = {'bytes': 1481, 'sha256': 'fd9f444caae344caf9bf6b3058e3d377c28c60c4b486132bac96323fa35dd1e0'}
TOOL = {'path': '/data/local/tmp/pixel-tools-1528a782/tools/qemu-img', 'bytes': 2356032,
        'sha256': '1bd2fd6b968c492d0263436c260af2a8c2ee807cf4afd4fd2abb3300446e2440'}


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path, limit):
    require(path.resolve(strict=True) == path, 'noncanonical metadata path')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        s = os.fstat(stream.fileno())
        require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and s.st_size <= limit, 'nonordinary or oversized metadata')
        body = stream.read(limit + 1)
    require(len(body) <= limit, 'metadata exceeded bound')
    return body


def pin(path, body):
    digest = hashlib.sha256(body)
    return {'path': str(path), 'bytes': len(body), 'sha256': digest.hexdigest(), 'digest_bytes': list(digest.digest())}


def main():
    require(os.geteuid() == 0, 'root metadata reader required')
    body = read(WORK / 'result.json', 64 << 10)
    require({'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()} == RESULT_PIN, 'actual failed capability result changed')
    result = json.loads(body)
    rows = result.get('tool_commands', [])
    require(result.get('kind') == 'native_qemu_img_read_capability_probe' and result.get('status') == 'INCOMPLETE' and
            result.get('source_sha256') == SOURCE_SHA and result.get('tool') == TOOL and
            result.get('existing_disk_images_opened') is False and result.get('guest_vm_started') is False and
            result.get('bound_tooling_and_session_unchanged') is True and
            result.get('error') == 'ValueError: required dd options not advertised' and len(rows) == 1,
            'actual failed capability boundary differs')
    row = rows[0]
    require(row.get('label') == 'help' and row.get('command') == [TOOL['path'], 'dd', '--help'] and
            row.get('exit_code') == 0 and row.get('reaped') is True and row.get('forced') is False and
            not row.get('cleanup_error'), 'help command was not cleanly owned/reaped')
    exit_body = read(WORK / 'help.exit.json', 64 << 10)
    require(json.loads(exit_body) == row, 'retained help exit differs')
    help_body = read(WORK / 'help.stdout', 64 << 10)
    require(len(help_body) == row.get('output_bytes') and hashlib.sha256(help_body).hexdigest() == row.get('output_sha256'),
            'retained help output differs')
    for name in ('sample.input', 'sample.output', 'sample.command.json', 'sample.exit.json'):
        require(not os.path.lexists(WORK / name), 'synthetic phase unexpectedly started')
    lines = help_body.decode('utf-8').splitlines()
    matches = [i for i, line in enumerate(lines) if re.search(r'(?i)\bdd\b|bs=|count=|skip=|if=|of=', line)]
    selected = sorted({j for i in matches for j in range(max(0, i - 4), min(len(lines), i + 5))}) if matches else list(range(min(len(lines), 60)))
    require(len(selected) <= 80 and all(len(lines[i]) <= 2048 for i in selected), 'selected help context exceeds display bound')
    print(json.dumps({'schema': 1, 'status': 'QEMU_IMG_HELP_PROJECTION', 'readonly': True,
          'failed_capability_result': pin(WORK / 'result.json', body), 'help_stdout': pin(WORK / 'help.stdout', help_body),
          'help_exit': {'pid': row.get('pid'), 'exit_code': 0, 'reaped': True, 'forced': False,
                        'bytes': len(exit_body), 'sha256': hashlib.sha256(exit_body).hexdigest()},
          'total_lines': len(lines), 'match_indices_zero_based': matches, 'selected_lines': len(selected),
          'other_lines_omitted': len(selected) != len(lines), 'synthetic_phase_started': False,
          'existing_disk_images_opened': False}, separators=(',', ':')), flush=True)
    for i in selected:
        print(json.dumps({'line_zero_based': i, 'characters': len(lines[i]), 'text': lines[i]}, separators=(',', ':')), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status': 'CAPABILITY_HELP_PROJECTION_REFUSED', 'readonly': True,
                          'error': type(error).__name__ + ': ' + str(error)}, separators=(',', ':')), flush=True)
        raise SystemExit(2)
