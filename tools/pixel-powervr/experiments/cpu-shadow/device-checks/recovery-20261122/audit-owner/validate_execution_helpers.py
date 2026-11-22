"""Narrow synthetic checks of the new preflight-consumption gate; no child starts."""
import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location('fixture_' + name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def refuse(call):
    try:
        call()
    except ValueError:
        return
    raise AssertionError('invalid preflight was accepted')


def check():
    launcher = load('launch_audit_execution')
    original = (HERE / 'run_partition_audit.py').read_bytes()
    assert hashlib.sha256(original).hexdigest() == launcher.SOURCE_SHA256
    assert launcher.COMMAND == [launcher.PYTHON, '-I', '-B', str(launcher.SOURCE), '--execute']
    tree = ast.parse((HERE / 'launch_audit_execution.py').read_text())
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
    assert len([n for n in calls if n.func.attr == 'Popen']) == 1
    assert not any(n.func.attr in ('wait', 'poll', 'kill', 'send_signal', 'mkdir') for n in calls)
    fixture = load('test_owner').OwnerTests()
    checks = []
    with mock.patch('subprocess.Popen', side_effect=AssertionError('no subprocess permitted')):
        try:
            fixture.setUp()  # Fixture setup writes synthetic metadata only.
            owner = fixture.m
            current = owner.prerequisites()
            owner.OWNER.mkdir()
            save(owner.OWNER / 'prerequisites.json', current)
            save(owner.OWNER / 'preflight.json', fixture.public)
            save(owner.OWNER / 'preflight-command.json', owner.COMMAND)
            startup = {'schema': 1, 'started_utc': '2026-11-22T11:30:00+00:00', 'command': owner.COMMAND,
                       'wrapper': {'pid': 999999993, 'starttime': 3}, 'runner': {'pid': 999999994, 'starttime': 4}}
            save(owner.OWNER / 'preflight-owner.json', startup)
            exited = dict(startup, finished_utc='2026-11-22T11:31:00+00:00', exit_code=0, owner_exit_code=0,
                          accepted=True, runner_started=True, runner_reaped=True, forced_runner=False,
                          wrapper_error=None, cleanup_errors=[], stdout_sha256=hashlib.sha256(
                          (owner.OWNER / 'preflight.json').read_bytes()).hexdigest())
            save(owner.OWNER / 'preflight-exit.json', exited)
            launcher.PREFLIGHT_LAUNCH = fixture.root / 'detached.json'
            detached = {'schema': 1, 'status': 'PREFLIGHT_OWNER_LAUNCHED',
                        'kind': 'detached_partition_audit_preflight_owner',
                        'command': [launcher.PYTHON, '-I', '-B', str(launcher.SOURCE), '--preflight'],
                        'start_new_session': True, 'audit_execution_requested': False,
                        'source_sha256': launcher.SOURCE_SHA256, 'install_receipt_sha256': launcher.INSTALL_SHA256,
                        'wrapper': dict(startup['wrapper'], process_group=999999993, session=999999993)}
            save(launcher.PREFLIGHT_LAUNCH, detached)
            call = lambda: launcher.preflight_receipts(owner.__dict__, current, launcher.INSTALL_SHA256)
            accepted = call()
            assert accepted['preflight_stdout_sha256'] == exited['stdout_sha256']
            checks.append('accepted preflight metadata and detached owner identities bind correctly')
            path = owner.OWNER / 'preflight.json'
            kept = path.read_bytes()
            path.write_bytes(kept + b'\n')
            refuse(call)
            path.write_bytes(kept)
            checks.append('changed preflight output bytes refuse before spawn')
            live = owner.identity(os.getpid())
            save(owner.OWNER / 'preflight-owner.json', dict(startup, wrapper=live))
            save(owner.OWNER / 'preflight-exit.json', dict(exited, wrapper=live))
            refuse(call)
            save(owner.OWNER / 'preflight-owner.json', startup)
            save(owner.OWNER / 'preflight-exit.json', exited)
            checks.append('present preflight PID/start identity refuses before spawn')
            save(owner.OWNER / 'preflight-exit.json', dict(exited, command=owner.COMMAND + ['--execute']))
            refuse(call)
            save(owner.OWNER / 'preflight-exit.json', exited)
            checks.append('wrong-phase command receipt refuses before spawn')
            refuse(lambda: launcher.preflight_receipts(owner.__dict__, current, '0' * 64))
            checks.append('different physical installation receipt hash refuses before spawn')
            status = load('status_audit_execution')
            reader = status.reader()
            reader['BASE'] = fixture.root / 'missing-transfer'
            reader['SOURCE'] = fixture.root / 'missing-source.py'
            reader['INSTALL'] = fixture.root / 'missing-install.json'
            reader['LAUNCH'] = fixture.root / 'missing-launch.json'
            reader['WRAPPER_LOG'] = fixture.root / 'missing-wrapper.log'
            reader['OWNER'] = fixture.root / 'missing-owner'
            reader['WORK'] = fixture.root / 'missing-work'
            observed = status.observe(reader)
            assert observed['status'] == 'AUDIT_EXECUTION_NOT_OBSERVED'
            assert observed['accepted_audit_receipts_consistent'] is False
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                status.display(observed)
            assert len(out.getvalue().splitlines()) == 19
            checks.append('missing execution evidence stays unaccepted; compact observation has 19 lines')
        finally:
            fixture.doCleanups()
    report = {'schema': 1, 'status': 'PASS', 'checks': checks, 'real_subprocesses_started': 0,
              'phone_operations': False, 'owner_wrapper_sha256': hashlib.sha256(original).hexdigest(),
              'scope': 'new receipt-consumption gate and compact missing-evidence observation only'}
    save(HERE / 'execution-helper-validation.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    check()
