#!/usr/bin/env python3
"""Read-only execution observation: compact by default; --json for selected metadata."""
import argparse
import base64
import gzip
import hashlib
import json

READER_SHA256 = 'a96e66cda4ebdba4a9b4508e5a019f50073971906132302882033baedd541078'
READER_BYTES = 11358
READER_SOURCE = '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'


def reader():
    source = gzip.decompress(base64.b64decode(READER_SOURCE, validate=True))
    if len(source) != READER_BYTES or hashlib.sha256(source).hexdigest() != READER_SHA256:
        raise ValueError('embedded read-only metadata reader differs')
    namespace = {'__name__': 'reviewed_readonly_status'}
    exec(compile(source, '<reviewed-readonly-status>', 'exec'), namespace)
    return namespace


def observe(namespace=None):
    namespace = reader() if namespace is None else namespace
    base = namespace['observe']()
    read, select, identity, dictionary = (namespace[k] for k in ('read_record', 'select', 'identity', 'dictionary'))
    root, work, transfer = (namespace[k] for k in ('OWNER', 'WORK', 'BASE'))
    command = namespace['AUDITOR_COMMAND'] + ['--execute']
    outer_command = [namespace['PYTHON'], '-I', '-B', str(namespace['SOURCE']), '--execute']
    output = {'schema': 1, 'observed_utc': base['observed_utc'], 'observation_only': True,
              'boot_complete_claimed': False, 'gpu_path_complete_claimed': False, 'app_gate_changed_claimed': False,
              'source': base['source'], 'resources': base['resources'], 'audit_work_exists': base['audit_work_exists'],
              'preflight': {'status': base['status'], 'saved_receipt_consistent': base['saved_preflight_receipt_consistent'],
                            'recorded_identities_absent': base['recorded_preflight_identities_absent'],
                            'stdout_sha256': base['preflight_output'].get('sha256')}}
    launch_meta, launched = read(transfer / 'ios26-partition-audit-ebbc9c0-execute-launch.json', 65536)
    launched = dictionary(launched)
    launch_meta['selected'] = select(launched, ('status', 'started_utc', 'finished_utc', 'source_sha256',
                     'install_receipt_sha256', 'start_new_session', 'preflight_accepted', 'audit_execution_requested', 'error'))
    launch_meta['exact_outer_command'] = launched.get('command') == outer_command
    launch_meta['wrapper'] = identity(launched.get('wrapper'))
    output['detached_launch'] = launch_meta
    owner_meta, owned = read(root / 'owner.json', 32768)
    owned = dictionary(owned)
    owner_meta['selected'] = select(owned, ('schema', 'started_utc'))
    owner_meta['exact_auditor_command'] = owned.get('command') == command
    owner_meta['wrapper'], owner_meta['auditor'] = identity(owned.get('wrapper')), identity(owned.get('runner'))
    output['owner'] = owner_meta
    exit_meta, exited = read(root / 'exit.json', 32768)
    exited = dictionary(exited)
    exit_meta['selected'] = select(exited, ('started_utc', 'finished_utc', 'exit_code', 'owner_exit_code',
                  'accepted', 'runner_started', 'runner_reaped', 'forced_runner', 'wrapper_error',
                  'audit_result_sha256', 'requires_owned_process_recheck'))
    exit_meta['cleanup_errors_empty'] = exited.get('cleanup_errors') == []
    exit_meta['exact_auditor_command'] = exited.get('command') == command
    output['exit'] = exit_meta
    command_meta, saved_command = read(root / 'command.json', 16384)
    output['command_receipt'] = dict(command_meta, exact_auditor_command=saved_command == command)
    child_meta, child = read(work / 'a1/vm.child.json', 16384)
    child = dictionary(child)
    child_meta['identity'] = identity({'pid': child.get('pid'), 'starttime': child.get('start_ticks')})
    output['helper_child'] = child_meta
    vm_meta, vm = read(work / 'a1/vm-result.json')
    vm = dictionary(vm)
    vm_meta['selected'] = select(vm, ('schema', 'stage', 'status', 'started_utc', 'finished_utc',
                                    'elapsed_seconds', 'natural_exit', 'error'))
    vm_meta['native'] = select(vm.get('witnesses'), ('native_initialization', 'native_execution', 'native_svc_final'))
    vm_meta['fatal_markers_empty'] = dictionary(vm.get('witnesses')).get('fatal_markers') == []
    vm_meta['cleanup'] = select(vm.get('cleanup'), ('exit_code', 'echild', 'forced_qemu'))
    vm_meta['cleanup_errors_empty'] = dictionary(vm.get('cleanup')).get('errors') == []
    vm_meta['no_forced_descendants'] = dictionary(vm.get('cleanup')).get('forced_descendants') == []
    vm_meta['done_codes_exact_zero'] = vm.get('done_codes') == [0]
    output['helper_result'] = vm_meta
    result_meta, result = read(work / 'result.json')
    result = dictionary(result)
    result_meta['selected'] = select(result, ('schema', 'status', 'started_utc', 'finished_utc', 'elapsed_seconds',
            'session_sha256', 'disk_unchanged', 'preparation_records_unchanged', 'natural_exit', 'error', 'identity_error',
            'boot_complete', 'gpu_path_complete', 'app_gate_changed'))
    result_meta['native'] = select(result.get('native_witnesses'), ('native_initialization', 'native_execution', 'native_svc_final'))
    result_meta['fatal_markers_empty'] = dictionary(result.get('native_witnesses')).get('fatal_markers') == []
    result_meta['cleanup'] = select(result.get('cleanup'), ('exit_code', 'echild', 'forced_qemu'))
    result_meta['cleanup_errors_empty'] = dictionary(result.get('cleanup')).get('errors') == []
    result_meta['no_forced_descendants'] = dictionary(result.get('cleanup')).get('forced_descendants') == []
    guest = dictionary(result.get('guest_result'))
    result_meta['guest'] = select(guest, ('status', 'readonly_attachment'))
    result_meta['guest_errors_empty'] = guest.get('errors') == [] and guest.get('cleanup_errors') == []
    result_meta['fsck_status'] = {name: select(dictionary(guest.get('fsck')).get(name), ('status', 'exit_code'))
                                  for name in ('iOSRoot', 'Data')}
    result_meta['sha_matches_owner_exit'] = (type(result_meta.get('sha256')) is str and
                                            result_meta.get('sha256') == exited.get('audit_result_sha256'))
    _, audit_session = read(work / 'audit-session.json')
    _, preflight = read(root / 'preflight.json')
    expected_session = dictionary(preflight).get('session')
    result_meta['session_matches_accepted_preflight'] = (type(expected_session) is dict and
            audit_session == expected_session and result.get('session_sha256') == hashlib.sha256(
            json.dumps(expected_session, sort_keys=True, separators=(',', ':')).encode()).hexdigest())
    output['audit_result'] = result_meta
    refusal_meta, refusal = read(transfer / 'ios26-partition-audit-ebbc9c0-execute-wrapper.log', 16384)
    output['wrapper_output'] = {k: v for k, v in refusal_meta.items() if k != 'read_error'}
    if dictionary(refusal).get('status') == 'OWNER_REFUSED':
        output['wrapper_output']['selected_refusal'] = select(refusal, ('status', 'error'))
    rows = (launch_meta['wrapper'], owner_meta['wrapper'], owner_meta['auditor'], child_meta['identity'])
    absent = all(row.get('identity_absent') is True for row in rows)
    running = any(row.get('identity_present') is True for row in rows)
    cleanup, witness = dictionary(result.get('cleanup')), dictionary(result.get('native_witnesses'))
    launched_identity = {k: dictionary(launched.get('wrapper')).get(k) for k in ('pid', 'starttime')}
    evidence = dictionary(launched.get('accepted_preflight_evidence'))
    consistent = bool(base['source']['matches_reviewed_source'] and
        launched.get('status') == 'AUDIT_EXECUTION_OWNER_LAUNCHED' and launch_meta['exact_outer_command'] and
        launched.get('preflight_accepted') is True and launched.get('audit_execution_requested') is True and
        evidence.get('preflight_stdout_sha256') == base['preflight_output'].get('sha256') and
        launched_identity == owned.get('wrapper') and saved_command == owned.get('command') == exited.get('command') == command and
        owned.get('started_utc') == exited.get('started_utc') and
        all(owned.get(k) == exited.get(k) for k in ('wrapper', 'runner')) and
        exited.get('exit_code') == exited.get('owner_exit_code') == 0 and exited.get('accepted') is True and
        exited.get('runner_started') is True and exited.get('runner_reaped') is True and
        exited.get('forced_runner') is False and exited.get('wrapper_error') is None and
        exited.get('cleanup_errors') == [] and exited.get('finished_utc') and
        result.get('status') == 'PARTITION_AUDIT_PASSED' and result.get('disk_unchanged') is True and
        result.get('preparation_records_unchanged') is True and result.get('natural_exit') is True and
        not result.get('error') and not result.get('identity_error') and
        result_meta['sha_matches_owner_exit'] and result_meta['session_matches_accepted_preflight'] and
        witness.get('native_initialization') is True and witness.get('native_execution') is True and
        witness.get('fatal_markers') == [] and cleanup.get('exit_code') == 0 and cleanup.get('echild') is True and
        cleanup.get('forced_qemu') is False and cleanup.get('forced_descendants') == [] and cleanup.get('errors') == [] and
        all(result.get(k) is False for k in ('boot_complete', 'gpu_path_complete', 'app_gate_changed')))
    output['accepted_audit_receipts_consistent'] = consistent
    output['recorded_execution_identities_absent'] = absent
    output['status'] = ('AUDIT_OWNER_RUNNING_OR_FINALIZING' if running else
                        'PARTITION_AUDIT_COMPLETE_ACCEPTED' if consistent and absent else
                        'AUDIT_EXIT_REQUIRES_REVIEW' if exit_meta['exists'] else
                        'AUDIT_OWNER_ABSENT_WITHOUT_COMPLETION' if launch_meta['wrapper'].get('identity_absent') else
                        'AUDIT_EXECUTION_NOT_OBSERVED')
    return output


def display(value):
    def shown(item):
        return json.dumps(item, separators=(',', ':'))

    def process(item):
        if not item.get('recorded'):
            return 'unrecorded'
        row = item['expected']
        return (str(row['pid']) + '/' + str(row['starttime']) + ' present=' + shown(item.get('identity_present')) +
                ' absent=' + shown(item.get('identity_absent')) + ' reused=' + shown(item.get('pid_occupied_by_other_identity')))

    launch, owner, exited = value['detached_launch'], value['owner'], value['exit']
    vm, final = value['helper_result'], value['audit_result']
    vm_row, final_row, exit_row = vm['selected'], final['selected'], exited['selected']
    print('AUDIT EXECUTION ' + value['observed_utc'] + ' (observation only)')
    print('status=' + value['status'] + ' audit_work_exists=' + shown(value['audit_work_exists']))
    print('source_match=' + shown(value['source']['matches_reviewed_source']) + ' sha256=' + str(value['source'].get('sha256')))
    print('launched_wrapper=' + process(launch['wrapper']))
    print('owner_wrapper=' + process(owner['wrapper']))
    print('auditor=' + process(owner['auditor']))
    print('QEMU=' + process(value['helper_child']['identity']))
    print('exact_commands outer/owner/exit/saved=' + '/'.join(shown(v) for v in
          (launch['exact_outer_command'], owner['exact_auditor_command'], exited['exact_auditor_command'], value['command_receipt']['exact_auditor_command'])))
    print('exit child/owner=' + shown(exit_row.get('exit_code')) + '/' + shown(exit_row.get('owner_exit_code')) +
          ' accepted=' + shown(exit_row.get('accepted')) + ' reaped=' + shown(exit_row.get('runner_reaped')) + ' forced=' + shown(exit_row.get('forced_runner')))
    print('wrapper_error=' + shown(str(exit_row.get('wrapper_error'))[:96] if exit_row.get('wrapper_error') is not None else None) +
          ' cleanup_errors_empty=' + shown(exited['cleanup_errors_empty']))
    print('VM=' + str(vm_row.get('status')) + ' seconds=' + str(vm_row.get('elapsed_seconds')) +
          ' native_init/exec/final=' + '/'.join(shown(vm['native'].get(k)) for k in ('native_initialization', 'native_execution', 'native_svc_final')))
    print('VM natural=' + shown(vm_row.get('natural_exit')) + ' done0=' + shown(vm['done_codes_exact_zero']) +
          ' cleanup_exit/reaped=' + shown(vm['cleanup'].get('exit_code')) + '/' + shown(vm['cleanup'].get('echild')) +
          ' no_force/errors=' + shown(vm['no_forced_descendants'] and vm['cleanup'].get('forced_qemu') is False) + '/' + shown(vm['cleanup_errors_empty']))
    print('audit=' + str(final_row.get('status')) + ' disk/prep_unchanged=' + shown(final_row.get('disk_unchanged')) + '/' + shown(final_row.get('preparation_records_unchanged')))
    print('audit_error=' + shown(str(final_row.get('error'))[:120] if final_row.get('error') is not None else None) +
          ' identity_error=' + shown(str(final_row.get('identity_error'))[:120] if final_row.get('identity_error') is not None else None))
    print('result_sha256=' + str(final.get('sha256')) + ' owner_match=' + shown(final['sha_matches_owner_exit']) +
          ' accepted_session_match=' + shown(final['session_matches_accepted_preflight']))
    print('fsck iOSRoot/Data=' + '/'.join(str(final['fsck_status'][n].get('status')) + ':' +
          str(final['fsck_status'][n].get('exit_code')) for n in ('iOSRoot', 'Data')))
    print('boot/GPU/app=' + '/'.join(shown(final_row.get(k)) for k in ('boot_complete', 'gpu_path_complete', 'app_gate_changed')))
    print('resources MemAvailable=' + str(value['resources'].get('mem_available_bytes')) + ' free=' +
          str(value['resources'].get('free_bytes')) + ' fresh_2816MiB_floor_met=' + shown(value['resources'].get('fresh_helper_memory_floor_met_at_observation')))
    print('accepted_receipts_consistent=' + shown(value['accepted_audit_receipts_consistent']) +
          ' recorded_identities_absent=' + shown(value['recorded_execution_identities_absent']))
    refusal = value.get('wrapper_output', {}).get('selected_refusal')
    if refusal:
        print('outer_refusal=' + str(refusal.get('error'))[:160])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    observation = observe()
    if args.json:
        print(json.dumps(observation, indent=2), flush=True)
    else:
        display(observation)
