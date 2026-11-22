#!/usr/bin/env python3
"""Bounded read-only firstboot metadata; compact by default or --json."""
import argparse
import datetime
import hashlib
import itertools
import json
import os
from pathlib import Path
import re
import stat

BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
OWNER = BASE / 'ios26-firstboot-owner-memfd1'
SOURCE = BASE / 'run-ios26-firstboot-owner-memfd1.py'
SOURCE_SHA = '771742c200d2d64c54cdd18db7bcd1cba4fc242999f16376531e0d9803f9a3d5'
PREP = Path('/data/local/tmp/pixel-prep-e9cc754')
WORK = Path('/data/local/tmp/pixel-firstboot-guard-e9cc754-memfd1')
GUARD = Path('/data/local/tmp/pixel-boot-checks-ebbc9c0/firstboot/guard_ios26_firstboot.py')
GUARD_SHA = '8f98fafd603385b5d3aa20331acc7e536020b6ae136f8690bd190efbeb09845c'
PYTHON = '/data/data/com.termux/files/usr/bin/python'
ADAPTER = BASE / 'run-ios26-firstboot-memfd-adapter-memfd1.py'
ADAPTER_SHA = 'e981d6d561b821641a6993b2aa96b84fa63776ccd1a7bc8cb314d1261ae899a8'
SMOKE = BASE / 'python-memfd-smoke-memfd1.json'
SMOKE_SHA = '57d7239160422a858ed9882191c5012fd20a20d5b790f482be15013266f313bd'
FAILED_RESULT = Path('/data/local/tmp/pixel-firstboot-guard-e9cc754/result.json')
FAILED_EXIT = BASE / 'ios26-firstboot-owner-ebbc9c0/exit.json'
FAILED_RESULT_SHA = '2a4b1ad20f478db58eb5ca7219789146b973f364cf4e7f079eb6acd4f5e7519d'
FAILED_EXIT_SHA = 'c651a9fae9976e04eada79bc229604a9724ea4053723d6b05ee6c0df02ce28b1'
COMMAND = [PYTHON, '-I', '-B', str(ADAPTER), '--execute']
GUARD_ARGV = [str(GUARD), '--audit-work', '/data/local/tmp/pixel-audit-e9cc754',
              '--auditor-dir', '/data/local/tmp/pixel-boot-checks-ebbc9c0/auditor',
              '--runner-dir', '/data/local/tmp/pixel-prep-runner-f4d64db', '--work', str(WORK), '--execute']


def dictionary(value): return value if type(value) is dict else {}


def selected(value, keys):
    value = dictionary(value)
    return {k: (value[k][:240] if type(value[k]) is str else value[k] if value[k] is None or type(value[k]) in (bool, int, float) else '<non-scalar>') for k in keys if k in value}


def read(path, parse=True, limit=4 << 20):
    meta = {'exists': os.path.lexists(path)}
    if not meta['exists']: return meta, {}
    try:
        if path.resolve(strict=True) != path: raise ValueError('noncanonical metadata')
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit: raise ValueError('nonordinary/oversized metadata')
            body = stream.read(limit + 1)
        if len(body) > limit: raise ValueError('metadata grew beyond bound')
        meta.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        return meta, json.loads(body) if parse else {}
    except Exception as exc:
        meta['error'] = (type(exc).__name__ + ': ' + str(exc))[:240]
        return meta, {}


def process(value, key='starttime'):
    value = dictionary(value); pid, ticks = value.get('pid'), value.get(key)
    if type(pid) is not int or not 0 < pid < 1 << 31 or type(ticks) is not int: return {'recorded': False, 'absent': False}
    output = {'recorded': True, 'expected': {'pid': pid, 'starttime': ticks}}
    try:
        with Path('/proc/{}/stat'.format(pid)).open('rb') as stream: raw = stream.read(4097)
        if len(raw) > 4096: raise ValueError('oversized process stat')
        fields = raw[raw.rfind(b')') + 2:].split(); current = int(fields[19])
        output.update(present=current == ticks, absent=current != ticks, reused=current != ticks, state=fields[0].decode('ascii'))
    except FileNotFoundError: output.update(present=False, absent=True, reused=False)
    except Exception as exc: output.update(absent=False, error=(type(exc).__name__ + ': ' + str(exc))[:160])
    return output


def adapter_status(owner, exited, inputs):
    source, _ = read(ADAPTER, False); smoke, _ = read(SMOKE)
    prefix = BASE / 'ios26-firstboot-memfd1-adapter-execute'
    startup_meta, startup = read(Path(str(prefix) + '.owner.json'))
    exit_meta, ended = read(Path(str(prefix) + '.exit.json'))
    startup, ended = dictionary(startup), dictionary(ended)
    acceptance = dictionary(dictionary(exited.get('acceptance')).get('adapter'))
    failure_meta, failure = read(FAILED_RESULT); failed_exit_meta, failed_exit = read(FAILED_EXIT)
    stage_meta, _ = read(PREP / 'attempts/07-0001/stage-inputs.json')
    stage_expected = dictionary(dictionary(dictionary(dictionary(failure).get('actual_attempt')).get('files')).get('stage-inputs.json'))
    preserved = {'guard_result_sha256': FAILED_RESULT_SHA, 'owner_exit_sha256': FAILED_EXIT_SHA, 'attempt': '07-0001'}
    prior_absent = all(process(dictionary(failed_exit).get(k)).get('absent') is True for k in ('wrapper', 'guard'))
    failure_match = (failure_meta.get('sha256') == FAILED_RESULT_SHA and failed_exit_meta.get('sha256') == FAILED_EXIT_SHA and
                     type(stage_meta.get('sha256')) is str and stage_meta.get('sha256') == stage_expected.get('sha256') and
                     stage_meta.get('bytes') == stage_expected.get('bytes') and prior_absent and
                     all(not os.path.lexists(PREP / 'attempts/07-0001' / name) for name in ('launch.json', 'vm-result.json', 'vm.child.json')) and
                     dictionary(exited.get('acceptance')).get('preserved_failure') == inputs.get('preserved_failure') == preserved)
    names = ['memfd_create', 'MFD_CLOEXEC', 'MFD_ALLOW_SEALING']
    out = selected(ended if ended else startup, ('phase', 'started_utc', 'finished_utc', 'exit_code', 'error', 'adapter_completed', 'attributes_restored', 'sources_unchanged'))
    out.update(source_matches=source.get('sha256') == ADAPTER_SHA, smoke_matches=smoke.get('sha256') == SMOKE_SHA,
               preserved_failure_matches=bool(failure_match), receipt_owner_sha256=startup_meta.get('sha256'), receipt_exit_sha256=exit_meta.get('sha256'))
    out['receipts_match'] = bool(out['source_matches'] and out['smoke_matches'] and failure_match and
        inputs.get('adapter_source_sha256') == ADAPTER_SHA and inputs.get('accepted_smoke_receipt_sha256') == SMOKE_SHA and
        type(startup_meta.get('sha256')) is str and startup_meta.get('sha256') == acceptance.get('owner_sha256') and
        type(exit_meta.get('sha256')) is str and exit_meta.get('sha256') == acceptance.get('exit_sha256') and
        startup.get('schema') == 1 and startup.get('phase') == 'execute' and startup.get('process') == owner.get('guard') and
        startup.get('command') == COMMAND and startup.get('guard_argv') == GUARD_ARGV and
        startup.get('adapter_source_sha256') == acceptance.get('adapter_source_sha256') == ADAPTER_SHA and
        startup.get('guard_source_sha256') == GUARD_SHA and startup.get('missing_attributes') == startup.get('installed_attributes') == names and
        startup.get('constants') == {'MFD_CLOEXEC': 1, 'MFD_ALLOW_SEALING': 2} and
        dictionary(startup.get('accepted_libc_smoke')).get('receipt_sha256') == acceptance.get('smoke_receipt_sha256') == SMOKE_SHA and
        startup.get('boot_execution_requested') is True and all(ended.get(k) == v for k, v in startup.items()) and
        ended.get('exit_code') == 0 and ended.get('error') is None and ended.get('adapter_completed') is True and
        ended.get('attributes_restored') is True and ended.get('sources_unchanged') is True)
    return out


def observe():
    out = {'schema': 1, 'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'observation_only': True}
    source, _ = read(SOURCE, False); guard_source, _ = read(GUARD, False)
    out['source_matches'] = source.get('sha256') == SOURCE_SHA
    out['guard_source_matches'] = guard_source.get('sha256') == GUARD_SHA
    _, launched = read(BASE / 'ios26-firstboot-owner-memfd1-launch.json')
    _, owner = read(OWNER / 'owner.json'); exit_meta, exited = read(OWNER / 'exit.json')
    _, inputs = read(OWNER / 'inputs.json'); _, command = read(OWNER / 'command.json')
    result_meta, result = read(WORK / 'result.json'); session_meta, session = read(WORK / 'guard-session.json')
    observations_meta, observations = read(WORK / 'guard-observations.json')
    launched, owner, exited, inputs, result = map(dictionary, (launched, owner, exited, inputs, result))
    out['adapter'] = adapter_status(owner, exited, inputs)
    out['launch'] = selected(launched, ('status', 'started_utc', 'finished_utc', 'firstboot_execution_requested', 'error'))
    out['exit'] = selected(exited, ('started_utc', 'finished_utc', 'exit_code', 'owner_exit_code', 'accepted', 'guard_started', 'guard_reaped', 'forced_guard', 'wrapper_error'))
    out['exit']['cleanup_errors_empty'] = exited.get('cleanup_errors') == []
    out['processes'] = {'launched_wrapper': process(launched.get('wrapper')), 'wrapper': process(owner.get('wrapper')), 'guard': process(owner.get('guard'))}
    out['exact_commands'] = {'launcher': launched.get('command') == [PYTHON, '-I', '-B', str(SOURCE), '--execute'],
                             'owner': owner.get('command') == COMMAND, 'exit': exited.get('command') == COMMAND, 'saved': command == COMMAND}
    before = inputs.get('attempts_before')
    candidates = []; truncated = False
    if type(before) is list and (PREP / 'attempts').is_dir():
        entries = list(itertools.islice((PREP / 'attempts').iterdir(), 1025)); truncated = len(entries) > 1024
        candidates = [p for p in entries[:1024] if re.fullmatch(r'07-\d{4}', p.name) and p.name not in before]
    attempt = candidates[0] if len(candidates) == 1 and not truncated else None
    out['attempt_inventory_truncated'] = truncated
    out['attempt'] = str(attempt) if attempt else None; out['attempt_candidate_count'] = len(candidates)
    vm_meta, vm = read(attempt / 'vm-result.json') if attempt else ({}, {})
    _, child = read(attempt / 'vm.child.json') if attempt else ({}, {})
    out['processes']['qemu'] = process(child, 'start_ticks')
    vm = dictionary(vm); cleanup = dictionary(vm.get('cleanup'))
    out['vm'] = selected(vm, ('stage', 'status', 'started_utc', 'finished_utc', 'elapsed_seconds', 'milestone', 'settled', 'guest_sync_answered', 'error'))
    out['vm']['native'] = selected(vm.get('witnesses'), ('native_initialization', 'native_execution', 'native_svc_final'))
    out['vm']['cleanup'] = selected(cleanup, ('exit_code', 'echild', 'forced_qemu', 'stop_flushed', 'quit_acknowledged'))
    out['vm']['cleanup_errors_empty'] = cleanup.get('errors') == []; out['vm']['no_forced_descendants'] = cleanup.get('forced_descendants') == []
    out['result'] = selected(result, ('status', 'finished_utc', 'checkpoint_accepted_by_guard', 'bound_inputs_unchanged',
                           'original_firstboot_checkpoint_present', 'error', 'identity_error', 'attempt_error', 'boot_complete', 'gpu_path_complete', 'app_gate_changed'))
    counters = result.get('post_stop_blockstats', dictionary(observations).get('post_stop_blockstats', []))
    supervision = result.get('supervision', dictionary(observations).get('supervision', []))
    out['counter_events'] = [selected(row, ('status', 'stop_acknowledged', 'failed_io_counters_zero', 'stop_internal_flush_return_observed', 'error')) for row in counters[:2]] if type(counters) is list else []
    out['supervision'] = [selected(row, ('stage', 'status', 'guest_sync_answered', 'original_supervision_status', 'error')) for row in supervision[:2]] if type(supervision) is list else []
    checkpoint_meta, checkpoint = read(PREP / 'checkpoints/ios26-firstboot.json')
    acceptance = dictionary(exited.get('acceptance'))
    actual_attempt = dictionary(result.get('actual_attempt')); recorded_files = dictionary(actual_attempt.get('files'))
    recorded_vm = dictionary(recorded_files.get('vm-result.json'))
    attempt_metadata_match = attempt is not None and set(recorded_files) == {'stage-inputs.json', 'launch.json', 'vm-result.json', 'stage-result.json'}
    for name in ('stage-inputs.json', 'launch.json', 'vm-result.json', 'stage-result.json'):
        meta, body = (vm_meta, vm) if name == 'vm-result.json' else read(attempt / name) if attempt else ({}, {})
        expected = dictionary(recorded_files.get(name))
        attempt_metadata_match = bool(attempt_metadata_match and type(meta.get('sha256')) is str and meta.get('sha256') == expected.get('sha256') and meta.get('bytes') == expected.get('bytes'))
        if name in ('vm-result.json', 'launch.json'): attempt_metadata_match = attempt_metadata_match and body == actual_attempt.get(name)
    out['hashes'] = {'result_sha256': result_meta.get('sha256'), 'checkpoint_sha256': checkpoint_meta.get('sha256'),
                    'attempt_metadata_match': attempt_metadata_match,
                    'vm_metadata_match': type(vm_meta.get('sha256')) is str and vm_meta.get('sha256') == recorded_vm.get('sha256') and vm_meta.get('bytes') == recorded_vm.get('bytes'),
                    'result_match': type(result_meta.get('sha256')) is str and result_meta.get('sha256') == acceptance.get('result_sha256'),
                    'checkpoint_match': type(checkpoint_meta.get('sha256')) is str and checkpoint_meta.get('sha256') == acceptance.get('checkpoint_sha256'),
                    'session_match': type(session_meta.get('sha256')) is str and session_meta.get('sha256') == acceptance.get('guard_session_file_sha256'),
                    'observations_match': type(observations_meta.get('sha256')) is str and observations_meta.get('sha256') == acceptance.get('guard_observations_sha256')}
    out['session_equals_accepted_preflight'] = type(session) is dict and session == inputs.get('accepted_guard_session')
    out['resources'] = {}
    try:
        with Path('/proc/meminfo').open('rb') as stream: memory = stream.read(65537)
        match = re.search(rb'^MemAvailable:\s+(\d+) kB$', memory, re.M)
        if len(memory) > 65536 or match is None: raise ValueError('memory metric unavailable')
        available = int(match[1]) * 1024; disk = os.statvfs(PREP)
        out['resources'] = {'mem_available_bytes': available, 'free_bytes': disk.f_bavail * disk.f_frsize,
                            'fresh_3840MiB_floor_met': available >= 3840 << 20, 'running_512MiB_floor_met': available >= 512 << 20}
    except Exception as exc: out['resources']['error'] = (type(exc).__name__ + ': ' + str(exc))[:160]
    _, refusal = read(BASE / 'ios26-firstboot-owner-memfd1-wrapper.log', limit=16384)
    if dictionary(refusal).get('status') == 'FIRSTBOOT_OWNER_REFUSED': out['outer_refusal'] = selected(refusal, ('status', 'error'))
    absent = all(row.get('absent') is True for row in out['processes'].values())
    running = any(row.get('present') is True for row in out['processes'].values())
    out['all_recorded_identities_absent'] = absent
    launch_process = dictionary(launched.get('wrapper'))
    out['accepted_receipts_consistent'] = bool(out['source_matches'] and out['guard_source_matches'] and out['adapter']['receipts_match'] and all(out['exact_commands'].values()) and
        launched.get('status') == 'FIRSTBOOT_OWNER_LAUNCHED' and launched.get('start_new_session') is True and
        launched.get('source_sha256') == SOURCE_SHA and launched.get('firstboot_execution_requested') is True and
        launched.get('adapter_source_sha256') == ADAPTER_SHA and launched.get('accepted_smoke_receipt_sha256') == SMOKE_SHA and
        launch_process.get('process_group') == launch_process.get('session') == launch_process.get('pid') and
        inputs.get('outer_source_sha256') == SOURCE_SHA and out['session_equals_accepted_preflight'] and
        all(out['hashes'][k] for k in ('result_match', 'checkpoint_match', 'session_match', 'observations_match', 'vm_metadata_match', 'attempt_metadata_match')) and
        {k: dictionary(launched.get('wrapper')).get(k) for k in ('pid', 'starttime')} == owner.get('wrapper') and
        all(owner.get(k) == exited.get(k) for k in ('wrapper', 'guard', 'started_utc')) and
        exited.get('accepted') is True and exited.get('exit_code') == exited.get('owner_exit_code') == 0 and
        exited.get('guard_reaped') is True and exited.get('forced_guard') is False and exited.get('wrapper_error') is None and exited.get('cleanup_errors') == [] and
        result.get('status') == 'GUARDED_FIRSTBOOT_COMPLETE' and result.get('checkpoint_accepted_by_guard') is True and result.get('bound_inputs_unchanged') is True and
        acceptance.get('attempt') == out['attempt'] == dictionary(result.get('actual_attempt')).get('attempt') == dictionary(checkpoint).get('attempt') == str(PREP / 'attempts/07-0002'))
    out['status'] = ('FIRSTBOOT_RUNNING_OR_FINALIZING' if running else 'GUARDED_FIRSTBOOT_COMPLETE_ACCEPTED' if out['accepted_receipts_consistent'] and absent else
                     'FIRSTBOOT_EXIT_REQUIRES_REVIEW' if exit_meta['exists'] else 'FIRSTBOOT_OWNER_ABSENT_WITHOUT_COMPLETION' if out['processes']['launched_wrapper'].get('absent') else 'FIRSTBOOT_NOT_OBSERVED')
    return out


def compact(value):
    print('FIRSTBOOT STATUS', value['observed_utc'], '(memfd1 retry; observation only)')
    print('status=', value['status'], 'owner_source_match=', value['source_matches'], 'guard_source_match=', value['guard_source_matches'])
    for name, row in value['processes'].items(): print(name, json.dumps(row, separators=(',', ':')))
    print('adapter=', json.dumps({k:v for k,v in value['adapter'].items() if k not in ('receipt_owner_sha256','receipt_exit_sha256')}, separators=(',', ':')))
    print('exact_commands=', json.dumps(value['exact_commands'], separators=(',', ':')))
    print('exit=', json.dumps(value['exit'], separators=(',', ':')))
    print('attempt=', value['attempt'], 'candidates=', value['attempt_candidate_count'], 'inventory_truncated=', value['attempt_inventory_truncated'])
    vm = value['vm']; print('VM=', vm.get('status'), 'seconds=', vm.get('elapsed_seconds'), 'native=', json.dumps(vm['native'], separators=(',', ':')))
    print('milestone/settled/sync=', vm.get('milestone'), vm.get('settled'), vm.get('guest_sync_answered'), 'VMerror=', vm.get('error'))
    print('cleanup=', json.dumps(vm['cleanup'], separators=(',', ':')), 'errors_empty=', vm['cleanup_errors_empty'], 'no_forced_descendants=', vm['no_forced_descendants'])
    print('guard_result=', json.dumps(value['result'], separators=(',', ':')))
    print('counter_events=', json.dumps(value['counter_events'], separators=(',', ':')))
    print('supervision=', json.dumps(value['supervision'], separators=(',', ':')))
    print('result_sha256=', value['hashes']['result_sha256'], 'match=', value['hashes']['result_match'])
    print('checkpoint_sha256=', value['hashes']['checkpoint_sha256'], 'match=', value['hashes']['checkpoint_match'])
    print('session/observations/attempt_hash_match=', value['hashes']['session_match'], value['hashes']['observations_match'], value['hashes']['attempt_metadata_match'], 'accepted_session_equal=', value['session_equals_accepted_preflight'])
    print('resources=', json.dumps(value['resources'], separators=(',', ':')))
    print('accepted_receipts_consistent=', value['accepted_receipts_consistent'], 'all_identities_absent=', value['all_recorded_identities_absent'])
    if value.get('outer_refusal'): print('outer_refusal=', json.dumps(value['outer_refusal'], separators=(',', ':')))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--json', action='store_true')
    args = parser.parse_args(); snapshot = observe()
    print(json.dumps(snapshot, indent=2), flush=True) if args.json else compact(snapshot)
