#!/usr/bin/env python3
"""Compact projection of the exact bounded read-only status reader."""
import base64
import gzip
import hashlib
import json

STATUS_SHA256 = 'a96e66cda4ebdba4a9b4508e5a019f50073971906132302882033baedd541078'
STATUS_BYTES = 11358
STATUS_SOURCE = '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'


def display(value):
    def shown(item):
        return json.dumps(item, separators=(',', ':'))

    def process(item):
        if not item.get('recorded'):
            return 'unrecorded'
        expected = item['expected']
        current = item.get('current') or {}
        return (str(expected['pid']) + '/' + str(expected['starttime']) +
                ' present=' + shown(item.get('identity_present')) +
                ' absent=' + shown(item.get('identity_absent')) +
                ' reused=' + shown(item.get('pid_occupied_by_other_identity')) +
                ' state=' + str(current.get('state', '-')))

    launch, owner = value['detached_launch'], value['preflight_owner']
    exit_row, public = value['preflight_exit'], value['preflight_output']
    exited, selected, session = exit_row['selected'], public['selected'], public['session_selected']
    print('AUDIT PREFLIGHT ' + value['observed_utc'] + ' (observation only; no audit pass)')
    print('status=' + value['status'])
    print('source_match=' + shown(value['source']['matches_reviewed_source']) + ' sha256=' + str(value['source'].get('sha256')))
    print('launched_wrapper=' + process(launch['wrapper']))
    print('owner_wrapper=' + process(owner['wrapper']))
    print('auditor=' + process(owner['auditor']))
    print('exact_commands outer/owner/exit/saved=' + '/'.join(shown(v) for v in
          (launch['exact_outer_command'], owner['exact_auditor_command'], exit_row['exact_auditor_command'], value['command_receipt']['exact_auditor_command'])))
    print('exit child/owner=' + shown(exited.get('exit_code')) + '/' + shown(exited.get('owner_exit_code')) +
          ' accepted=' + shown(exited.get('accepted')) + ' reaped=' + shown(exited.get('runner_reaped')) + ' forced=' + shown(exited.get('forced_runner')))
    print('wrapper_error=' + shown(str(exited.get('wrapper_error'))[:96] if exited.get('wrapper_error') is not None else None) +
          ' cleanup_errors_empty=' + shown(exit_row['cleanup_errors_empty']))
    print('stdout_sha256=' + str(public.get('sha256')) + ' receipt_match=' + shown(public['stdout_hash_matches_exit_receipt']) + ' bytes=' + str(public.get('bytes')))
    print('preflight=' + str(selected.get('status')) + ' checkpoints=' + str(public['checkpoint_count']) +
          ' exact_seven=' + shown(public['exact_seven_checkpoint_names']))
    print('readonly=' + shown(session.get('readonly')) + ' native_required=' + shown(session.get('native_required')) +
          ' tcg_retry=' + shown(session.get('tcg_retry')) + ' audit_work_exists=' + shown(value['audit_work_exists']))
    print('execution_verified=' + shown(selected.get('execution_verified')) + ' boot/GPU/app=' +
          '/'.join(shown(selected.get(k)) for k in ('boot_complete', 'gpu_path_complete', 'app_gate_changed')))
    print('resources MemAvailable=' + str(value['resources'].get('mem_available_bytes')) + ' free=' +
          str(value['resources'].get('free_bytes')) + ' fresh_2816MiB_floor_met=' + shown(value['resources'].get('fresh_helper_memory_floor_met_at_observation')))
    print('saved_receipt_consistent=' + shown(value['saved_preflight_receipt_consistent']) +
          ' recorded_identities_absent=' + shown(value['recorded_preflight_identities_absent']))
    refusal = value.get('wrapper_output', {}).get('selected_refusal')
    if refusal:
        print('outer_refusal=' + str(refusal.get('error'))[:160])


def main():
    source = gzip.decompress(base64.b64decode(STATUS_SOURCE, validate=True))
    if len(source) != STATUS_BYTES or hashlib.sha256(source).hexdigest() != STATUS_SHA256:
        raise ValueError('embedded status source differs')
    namespace = {'__name__': 'observed_status'}
    exec(compile(source, '<reviewed-audit-preflight-status>', 'exec'), namespace)
    display(namespace['observe']())


if __name__ == '__main__':
    main()
