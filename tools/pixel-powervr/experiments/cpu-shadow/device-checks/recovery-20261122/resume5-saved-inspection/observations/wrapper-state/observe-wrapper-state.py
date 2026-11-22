#!/usr/bin/env python3
"""Read only selected proc metadata for the exact recorded resume5 wrapper."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import stat

PID = 3218
TICKS = 10596300
SOURCE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-saved-inspection-resume5.py')
SOURCE_PIN = {'bytes': 60564, 'sha256': 'dbb570dc9b3354a5d7c4eb218883ab22f25afe24757c429e46cc7c04de1baa63'}


def bounded(path, limit):
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        body = stream.read(limit + 1)
    if len(body) > limit:
        raise ValueError('bounded proc/source read exceeded')
    return body


def parse(raw):
    left, right = raw.find(b'('), raw.rfind(b')')
    if not 0 < left < right or int(raw[:left].strip()) != PID:
        raise ValueError('invalid selected wrapper stat')
    fields = raw[right + 1:].split()
    if len(fields) < 20:
        raise ValueError('short selected wrapper stat')
    return {'pid': PID, 'start_ticks': int(fields[19]), 'state': fields[0].decode('ascii'),
            'parent_pid': int(fields[1]), 'process_group': int(fields[2]), 'session': int(fields[3]),
            'comm': raw[left + 1:right].decode('utf-8', 'replace')[:64]}


def main():
    if os.geteuid() != 0 or SOURCE.resolve(strict=True) != SOURCE:
        raise ValueError('root canonical owner source required')
    with os.fdopen(os.open(SOURCE, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1 or info.st_size != SOURCE_PIN['bytes']:
            raise ValueError('released owner source metadata differs')
        body = stream.read(SOURCE_PIN['bytes'] + 1)
    if len(body) != SOURCE_PIN['bytes'] or hashlib.sha256(body).hexdigest() != SOURCE_PIN['sha256']:
        raise ValueError('released owner source differs')
    result = {'schema': 1, 'status': 'READONLY_RECORDED_WRAPPER_STATE',
              'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'expected': {'pid': PID, 'start_ticks': TICKS}, 'recorded_identity_present': False,
              'same_identity_through_read': False, 'stat': None, 'status_selected': None,
              'exe': None, 'read_errors': [], 'readonly': True, 'signal_or_reap_requested': False}
    folder = Path('/proc') / str(PID)
    try:
        first = parse(bounded(folder / 'stat', 4096))
    except (FileNotFoundError, ProcessLookupError):
        result['identity_observation'] = 'ABSENT_AT_FIRST_READ'
        print(json.dumps(result, indent=2), flush=True)
        return
    if first['start_ticks'] != TICKS:
        result['identity_observation'] = 'PID_REUSED_SELECTED_METADATA_NOT_EXPORTED'
        print(json.dumps(result, indent=2), flush=True)
        return
    result['recorded_identity_present'] = True
    result['stat'] = first
    result['identity_observation'] = 'RECORDED_IDENTITY_PRESENT_AT_FIRST_READ'
    selected = None
    executable = None
    try:
        raw = bounded(folder / 'status', 65536).decode('ascii', 'replace')
        values = dict(line.split(':', 1) for line in raw.splitlines() if ':' in line)
        keys = ('State', 'Tgid', 'Pid', 'PPid', 'TracerPid', 'Threads', 'SigPnd', 'ShdPnd', 'SigBlk', 'SigIgn', 'SigCgt')
        selected = {key: values.get(key, '').strip() or None for key in keys}
        if selected['Pid'] != str(PID) or selected['Tgid'] != str(PID):
            raise ValueError('selected wrapper status identity differs')
    except Exception as error:
        selected = None
        result['read_errors'].append('status: ' + type(error).__name__ + ': ' + str(error)[:160])
    try:
        executable = os.readlink(folder / 'exe')
        if len(executable) > 4096:
            raise ValueError('selected wrapper exe link exceeds bound')
    except Exception as error:
        executable = None
        result['read_errors'].append('exe: ' + type(error).__name__ + ': ' + str(error)[:160])
    try:
        last = parse(bounded(folder / 'stat', 4096))
        same = last['start_ticks'] == TICKS
        result['same_identity_through_read'] = same
        result['recorded_identity_present_at_last_read'] = same
        if same:
            result['status_selected'] = selected
            result['exe'] = executable
            result['stat_after'] = last
        else:
            result['identity_observation'] = 'PID_REUSED_DURING_READ_STATUS_AND_EXE_SUPPRESSED'
    except (FileNotFoundError, ProcessLookupError):
        result['recorded_identity_present_at_last_read'] = False
        result['identity_observation'] = 'RECORDED_IDENTITY_DISAPPEARED_DURING_READ_STATUS_AND_EXE_SUPPRESSED'
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
