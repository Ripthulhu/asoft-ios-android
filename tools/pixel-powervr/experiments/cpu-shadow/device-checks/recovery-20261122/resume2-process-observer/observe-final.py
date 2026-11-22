import sys
sys.argv=['observe-final', '--final']
#!/usr/bin/env python3
"""Bounded read-only observer status/final projection; never reads guest logs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import time
import types

BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
SOURCE = BASE / 'run-ios26-saved-inspection-resume2-observer.py'
SOURCE_PIN = {'bytes': 33930, 'sha256': '26125291eebced96468511cc060a95623315aba14e2fd8b63cd6056fed27b192'}
OUT = BASE / 'ios26-saved-inspection-resume2-observer'


def load_observer():
    if os.geteuid() != 0 or SOURCE.resolve(strict=True) != SOURCE or BASE.resolve(strict=True) != BASE:
        raise ValueError('root and canonical source/base required')
    with os.fdopen(os.open(SOURCE, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1 or info.st_size != SOURCE_PIN['bytes']:
            raise ValueError('observer source metadata differs')
        body = stream.read(SOURCE_PIN['bytes'] + 1)
    if len(body) != SOURCE_PIN['bytes'] or hashlib.sha256(body).hexdigest() != SOURCE_PIN['sha256']:
        raise ValueError('observer source differs')
    module = types.ModuleType('verified_observer_status_reader')
    module.__file__ = str(SOURCE)
    exec(compile(body, str(SOURCE), 'exec'), module.__dict__)
    return module


def stable_json(m, path):
    for _ in range(3):
        try:
            return m.read_json(path)
        except m.UnstableRead:
            continue
    raise ValueError('metadata remained unstable across three bounded reads: ' + str(path))


def relation(row):
    return {k: row.get(k) for k in ('pid', 'start_ticks', 'role', 'ppid', 'state', 'kill_pending')}


def forced_projection(summary, forced, events):
    """A cleanup PID lacks start ticks; retain every matching observed identity."""
    result = []
    for pid in forced[:16]:
        matches = [row for row in summary['processes'] if row['identity']['pid'] == pid]
        identities = []
        for row in matches:
            identity = row['identity']
            last = row.get('last', {})
            points = []
            for event in events:
                if event.get('identity') != identity:
                    continue
                snapshot = event.get('snapshot', {})
                points.append({'event': event['event'], 'utc': event['utc'], 'monotonic_ns': event['monotonic_ns'],
                    'role': event.get('role'), 'parent_pid': snapshot.get('ppid'), 'state': snapshot.get('state'),
                    'kill_pending': snapshot.get('kill_pending'),
                    'previous_parent_pid': event.get('previous_parent_pid')})
            total = len(points)
            if total > 12:
                points = points[:3] + points[-9:]
            identities.append({'identity': identity, 'role': row['role'],
                'first_observed_parent': row.get('first_observed_parent'), 'present_at_final_sample': row.get('present'),
                'last_parent_pid': last.get('ppid', row.get('last_parent_pid')),
                'last_state': last.get('state', row.get('last_state')),
                'last_kill_pending': last.get('kill_pending'), 'last_pending_masks': last.get('pending'),
                'last_comm': last.get('comm', '')[:64], 'last_monotonic_ns': row.get('last_monotonic_ns'),
                'selected_event_count': len(points), 'total_identity_event_count': total,
                'events_omitted': max(0, total - len(points)), 'events': points})
        result.append({'cleanup_pid': pid, 'classification': 'unclassified' if not matches else
            'ambiguous_pid_reuse' if len(matches) > 1 else 'one_observed_identity_for_pid_number',
            'cleanup_receipt_does_not_supply_start_ticks': True, 'matching_observed_identities': identities})
    return {'total_forced_pid_count': len(forced), 'projected_forced_pid_count': len(result),
            'forced_pids_omitted': max(0, len(forced) - len(result)), 'mappings': result}


def collect(final=False):
    m = load_observer()
    ready, ready_pin = m.read_json(OUT / 'ready.json')
    status, status_pin = stable_json(m, OUT / 'status.json')
    source = {'path': str(SOURCE), **SOURCE_PIN}
    m.require(ready.get('schema') == 1 and ready.get('kind') == 'saved_inspection_process_observer_ready' and
              ready.get('source') == source and ready.get('scope') == m.SCOPE and ready.get('bounds') == m.BOUNDS and
              ready.get('output_directory') == str(OUT) and ready.get('diagnostic_only') is True,
              'observer ready/source/scope differs')
    identity = ready['observer']
    m.require(status.get('schema') == 1 and status.get('kind') == 'saved_inspection_process_observer_status' and
              status.get('observer') == identity and status.get('ready_sha256') == ready_pin['sha256'] and
              status.get('source_sha256') == SOURCE_PIN['sha256'] and status.get('scope') == m.SCOPE and
              status.get('output_directory') == str(OUT), 'observer status identity/scope differs')
    try:
        current = m.Proc().snapshot(identity['pid'])
        presence = {'same_identity_present': m.key(current) == m.key(identity),
                    'pid_reused': m.key(current) != m.key(identity)}
        if presence['same_identity_present']:
            presence['current'] = relation(current)
    except (FileNotFoundError, ProcessLookupError):
        presence = {'same_identity_present': False, 'pid_reused': False}
    projected = {'schema': 1, 'observed_utc': m.utc(), 'diagnostic_only': True, 'source': source,
        'observer': identity, 'observer_presence': presence, 'ready': ready_pin, 'status_file': status_pin,
        'status': status['status'], 'phase': status['phase'],
        'heartbeat_age_seconds': (time.monotonic_ns() - status['heartbeat_monotonic_ns']) / 1e9,
        'sample_count': status['sample_count'], 'sampling_gaps': status['sample_gaps'], 'read_gaps': status['read_gaps'],
        'tracked_identities': status['tracked_identities'], 'events': status['events'],
        'live_selected': [relation(row) for row in status['live'][:20]],
        'live_selected_omitted': max(0, len(status['live']) - 20),
        'observer_exit_receipt_present': os.path.lexists(OUT / 'exit.json')}
    try:
        vm, vm_pin = stable_json(m, m.WORK / 'a1/vm-result.json')
    except FileNotFoundError:
        vm, vm_pin = None, None
    if vm is not None:
        forced = vm.get('cleanup', {}).get('forced_descendants', [])
        m.require(type(forced) is list and len(forced) <= m.BOUNDS['process_identities'] and
                  all(type(pid) is int and pid > 0 for pid in forced), 'invalid bounded forced descendant list')
        projected['vm'] = {'receipt': vm_pin, 'status': vm.get('status'), 'natural_exit': vm.get('natural_exit'),
            'error': None if vm.get('error') is None else str(vm['error'])[:300],
            'cleanup': {k: vm.get('cleanup', {}).get(k) for k in ('exit_code', 'echild', 'forced_qemu', 'forced_descendants', 'errors')},
            'native_initialization': vm.get('witnesses', {}).get('native_initialization'),
            'native_execution': vm.get('witnesses', {}).get('native_execution')}
    if not final:
        return projected
    exited, exit_pin = m.read_json(OUT / 'exit.json')
    summary, summary_pin = m.read_json(OUT / 'summary.json')
    m.require(exited.get('schema') == 1 and exited.get('observer') == identity and exited.get('summary') == summary_pin and
              summary.get('schema') == 1 and summary.get('observer') == identity and summary.get('ready') == ready_pin and
              summary.get('source') == source and summary.get('scope') == m.SCOPE and summary.get('bounds') == m.BOUNDS and
              summary.get('status') == exited.get('status') == status['status'] and status['phase'] == 'FINISHED',
              'observer final receipts are not coherent')
    m.require(type(summary.get('processes')) is list and len(summary['processes']) <= m.BOUNDS['process_identities'],
              'observer process summary exceeds bound')
    event_pin = summary['events']
    m.require(event_pin['path'] == str(OUT / 'events.jsonl') and event_pin['bytes'] <= m.BOUNDS['event_bytes'] and
              event_pin['count'] <= m.BOUNDS['events'], 'observer event inventory exceeds scope/bounds')
    event_body = m.file_bytes(OUT / 'events.jsonl', m.BOUNDS['event_bytes'])
    m.require(len(event_body) == event_pin['bytes'] and m.sha(event_body) == event_pin['sha256'], 'observer event bytes differ')
    lines = event_body.splitlines()
    m.require(len(lines) == event_pin['count'], 'observer event count differs')
    events = [json.loads(line) for line in lines]
    if summary['owner_receipt'] is not None:
        owner, owner_pin = m.read_json(m.OWNER / 'owner.json')
        m.require(owner_pin == summary['owner_receipt'] and owner.get('command') == m.SCOPE['inspection_command'],
                  'bound inspection owner changed')
    if summary['qemu_receipt_identity'] is not None:
        qemu, _ = m.read_json(m.WORK / 'a1/vm.child.json')
        m.require(qemu == summary['qemu_receipt_identity'], 'bound QEMU identity changed')
    projected.update({'exit': exit_pin, 'exit_code': exited['exit_code'], 'summary': summary_pin,
        'events': event_pin, 'summary_errors': summary['errors'],
        'unresolved_receipt_publication_gaps': summary.get('unresolved_receipt_publication_gaps', {}),
        'remaining_observed_identities': summary['remaining_observed_identities'],
        'inspection_outer_exit': summary['inspection_outer_exit'],
        'qemu_receipt_identity': summary['qemu_receipt_identity'],
        'qemu_identity_observed_alive_or_zombie': summary['qemu_identity_observed_alive_or_zombie'],
        'absence_is_not_an_exit_status': True, 'sampling_cannot_prove_counterfactual_grace': True,
        'forced_pid_projection': None if vm is None else forced_projection(summary, forced, events)})
    return projected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--final', action='store_true')
    args = parser.parse_args()
    body = json.dumps(collect(args.final), indent=2)
    if len(body.encode()) > 128 << 10:
        raise ValueError('selected status/final projection exceeds 128 KiB output bound')
    print(body, flush=True)


if __name__ == '__main__':
    main()
