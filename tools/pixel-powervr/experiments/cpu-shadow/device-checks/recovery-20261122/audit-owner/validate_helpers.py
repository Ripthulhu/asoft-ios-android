"""Local synthetic validation; no subprocess or phone operation is launched."""
import base64
import contextlib
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
from unittest import mock

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location('fixture_' + name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def check():
    source = (HERE / 'run_partition_audit.py').read_bytes()
    installer = load('install_audit_owner')
    assert gzip.decompress(base64.b64decode(installer.PAYLOAD, validate=True)) == source
    assert len(source) == installer.EXPECTED_BYTES == 18144
    assert hashlib.sha256(source).hexdigest() == installer.EXPECTED_SHA256
    checks = ['embedded owner matches the unchanged reviewed bytes']
    with tempfile.TemporaryDirectory(prefix='helper-fixture-', dir=HERE) as temporary:
        base = Path(temporary)
        installer.BASE = base
        installer.TARGET = base / 'run-ios26-partition-audit-ebbc9c0.py'
        installer.RECEIPT = base / 'ios26-partition-audit-ebbc9c0-install.json'
        actual_fstat = os.fstat

        def fixture_root_fstat(fd):
            fields = list(actual_fstat(fd))
            fields[4] = 0  # Only model Android root ownership; host uid is 1000.
            return os.stat_result(fields)

        with mock.patch.object(installer.os, 'geteuid', return_value=0), \
                mock.patch.object(installer.os, 'fstat', side_effect=fixture_root_fstat):
            installed = installer.install()
            assert installed['execution_started'] is False
            assert installer.TARGET.read_bytes() == source
            before = installer.TARGET.read_bytes(), installer.RECEIPT.read_bytes()
            try:
                installer.install()
                raise AssertionError('duplicate install unexpectedly accepted')
            except FileExistsError:
                pass
            assert before == (installer.TARGET.read_bytes(), installer.RECEIPT.read_bytes())
        checks.append('exclusive source/receipt installation and duplicate preservation on synthetic paths')
        launcher = load('launch_audit_preflight')
        launcher.BASE, launcher.SOURCE, launcher.INSTALL = base, installer.TARGET, installer.RECEIPT
        launcher.LAUNCH, launcher.LOG = base / 'launch.json', base / 'wrapper.log'
        launcher.OWNER, launcher.WORK = base / 'owner', base / 'work'
        launcher.COMMAND = [launcher.PYTHON, '-I', '-B', str(launcher.SOURCE), '--preflight']

        class Child:
            pid = 999999991

            def wait(self, *args, **kwargs):
                raise AssertionError('launcher attempted wait')

            def poll(self, *args, **kwargs):
                raise AssertionError('launcher attempted poll')

            def send_signal(self, *args, **kwargs):
                raise AssertionError('launcher attempted signalling')

            def kill(self, *args, **kwargs):
                raise AssertionError('launcher attempted killing')

        def fake_process(pid):
            return {'pid': pid, 'starttime': 1, 'state': 'R', 'parent_pid': os.getpid(),
                    'process_group': pid, 'session': pid}

        def fake_spawn(command, **kwargs):
            assert command == launcher.COMMAND
            assert kwargs['stdin'] == launcher.subprocess.DEVNULL
            assert kwargs['stderr'] == launcher.subprocess.STDOUT
            assert kwargs['start_new_session'] is True and kwargs['close_fds'] is True
            assert stat.S_IMODE(os.fstat(kwargs['stdout'].fileno()).st_mode) == 0o600
            return Child()

        with mock.patch.object(launcher.os, 'geteuid', return_value=0), \
                mock.patch.object(launcher, 'process', side_effect=fake_process), \
                mock.patch.object(launcher.subprocess, 'Popen', side_effect=fake_spawn) as popen:
            launched = launcher.launch()
            assert launched['status'] == 'PREFLIGHT_OWNER_LAUNCHED'
            assert launched['wrapper']['session'] == Child.pid
            before = launcher.LAUNCH.read_bytes(), launcher.LOG.read_bytes()
            try:
                launcher.launch()
                raise AssertionError('duplicate launch unexpectedly accepted')
            except FileExistsError:
                pass
            assert popen.call_count == 1
            assert before == (launcher.LAUNCH.read_bytes(), launcher.LOG.read_bytes())
        checks.append('mocked detached argv/session/stdin/output contract, no wait/poll/signal, duplicate refusal')
        status = load('status_audit_preflight')
        status.BASE, status.SOURCE, status.INSTALL = base, installer.TARGET, installer.RECEIPT
        status.LAUNCH, status.WRAPPER_LOG = launcher.LAUNCH, launcher.LOG
        status.OWNER, status.WORK = launcher.OWNER, launcher.WORK
        status.OUTER_COMMAND = launcher.COMMAND
        status.OWNER.mkdir()
        startup = {'schema': 1, 'started_utc': '2026-11-22T11:30:00+00:00',
                   'command': status.AUDITOR_COMMAND, 'wrapper': {'pid': Child.pid, 'starttime': 1},
                   'runner': {'pid': Child.pid + 1, 'starttime': 2}}
        save(status.OWNER / 'preflight-owner.json', startup)
        save(status.OWNER / 'preflight-command.json', status.AUDITOR_COMMAND)
        public = {'schema': 1, 'status': 'PREFLIGHT_READY', 'work': str(status.WORK),
                  'execution_verified': False, 'boot_complete': False, 'gpu_path_complete': False,
                  'app_gate_changed': False, 'session': {'readonly': True, 'native_required': True,
                  'tcg_retry': False, 'checkpoints': {str(status.PREP / 'checkpoints' / (s + '.json')):
                  '0' * 64 for s in status.STAGES}}}
        save(status.OWNER / 'preflight.json', public)
        exited = dict(startup, finished_utc='2026-11-22T11:31:00+00:00', exit_code=0, owner_exit_code=0,
                      accepted=True, runner_started=True, runner_reaped=True, forced_runner=False,
                      wrapper_error=None, cleanup_errors=[], stdout_sha256=hashlib.sha256(
                      (status.OWNER / 'preflight.json').read_bytes()).hexdigest())
        save(status.OWNER / 'preflight-exit.json', exited)
        before = {str(p): p.read_bytes() for p in base.rglob('*') if p.is_file()}
        observation = status.observe()
        assert observation['status'] == 'PREFLIGHT_COMPLETE_ACCEPTED'
        assert observation['observation_only'] is True and observation['audit_pass_claimed'] is False
        assert before == {str(p): p.read_bytes() for p in base.rglob('*') if p.is_file()}
        checks.append('read-only selected status from synthetic completed receipts; no artifact changes')
        compact = load('status_audit_preflight_compact')
        embedded = gzip.decompress(base64.b64decode(compact.STATUS_SOURCE, validate=True))
        assert embedded == (HERE / 'status_audit_preflight.py').read_bytes()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            compact.display(observation)
        assert len(out.getvalue().splitlines()) == 15
        (HERE / 'compact-status-synthetic-example.txt').write_text(out.getvalue())
        checks.append('compact projection embeds exact full reader and emits 15 lines')
    result = {'schema': 1, 'status': 'PASS', 'checks': checks,
              'phone_operations': False, 'real_subprocesses_started': 0,
              'note': 'Installer root identity and detached child are simulated; this is not phone execution evidence.'}
    save(HERE / 'helper-validation.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    check()
