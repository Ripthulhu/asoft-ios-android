#!/usr/bin/env python3
"""Unreleased two-phase owner for the three native helpers through ios26-apps.

Every mode refuses before filesystem/process actions until the fourteen actual
accepted saved-inspection file identities are finalized. The pinned existing
app auditor validates the saved proof against its original firstboot prefix.
Only the unchanged frozen runner writes new preparation overlays/checkpoints.
No guest-boot permission, Python memfd adapter, or direct QEMU launch is used.
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time
import types

sys.dont_write_bytecode = True
BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
OWNER = BASE / 'ios26-apps-prep-resume1-owner'
PREP = Path('/data/local/tmp/pixel-prep-e9cc754')
RUNNER = Path('/data/local/tmp/pixel-prep-runner-f4d64db')
GUARD = Path('/data/local/tmp/pixel-boot-checks-counter1/firstboot/guard_ios26_firstboot.py')
GUARD_WORK = Path('/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1')
INSPECTOR = Path('/data/local/tmp/pixel-saved-checks-counter1')
INSPECTION = Path('/data/local/tmp/pixel-saved-audit-e9cc754-resume1')
INSPECTION_OWNER = BASE / 'ios26-saved-inspection-resume1-owner'
INSPECTION_SOURCE = BASE / 'run-ios26-saved-inspection-resume1.py'
APPS = Path('/data/local/tmp/pixel-app-checks-counter1-resume1')
APPS_INSTALL = BASE / 'resume1-apps-auditor-install.json'
APPS_WORK = Path('/data/local/tmp/pixel-app-audit-e9cc754-resume1')
PARTITION_GUEST = Path('/data/local/tmp/pixel-boot-checks-ebbc9c0/auditor/audit_ios26_partition_guest.py')
PYTHON = '/data/data/com.termux/files/usr/bin/python'
SESSION_DIGEST = '9ce5f5b8e4953ac54fddd854c5b4a606c2b9866814af6b1d520c2b590e987a6b'
INSPECTION_SUCCESS_PINS = None  # UNRELEASED: fourteen observed {path: {bytes, sha256}} entries.
FIRSTBOOT_STAGES = ['shared-fetch', 'shared-unpack', 'shared-build', 'ios26-fetch',
                    'ios26-decrypt', 'ios26-rootfs', 'ios26-partition', 'ios26-firstboot']
NEXT_STAGES = ['ios26-persona', 'ios26-activation', 'ios26-apps']
NEXT_ATTEMPTS = dict(zip(NEXT_STAGES, ('08-0001', '09-0001', '10-0001')))
OUTPUTS = {'ios26-persona': {'root26g.qcow2'},
           'ios26-activation': {'root26-activation.qcow2', 'root26-activation.tc'},
           'ios26-apps': {'root26-apps.qcow2', 'root26-apps.tc'}}
NO_BOOT = {'boot_complete': False, 'gpu_path_complete': False, 'app_gate_changed': False}
HELPER_SECONDS = 21600
PREFLIGHT_SECONDS = 1800
EXECUTION_SECONDS = len(NEXT_STAGES) * HELPER_SECONDS + 3600
MAX_METADATA = 4 << 20
COMMAND = [PYTHON, '-u', '-B', str(RUNNER / 'prepare_ios26.py'),
           '--package', str(BASE / 'pixel-cpu-shadow-ksceynt6/cpu-shadow-qualification'),
           '--qualification', str(BASE / 'qualification-e9cc754/qualification.json'),
           '--tooling', '/data/local/tmp/pixel-tools-1528a782',
           '--tooling-sha256', 'a5461ecf2e41d4966f783dfca620d3d700f9aa1bc76dd5fa745ec54666e764b2',
           '--work', str(PREP), '--timezone', 'Europe/Amsterdam', '--region', '', '--clock', '24',
           '--helper-ram-mib', '2048', '--helper-vcpus', '4', '--through', 'ios26-apps',
           '--helper-seconds', str(HELPER_SECONDS), '--max-log-mib', '64',
           '--min-free-mib', '1536', '--min-available-mib', '512']
INSPECTION_COMMAND = [PYTHON, '-I', '-B', str(INSPECTOR / 'inspect_ios26_firstboot.py'),
                      '--guard-work', str(GUARD_WORK), '--work', str(INSPECTION), '--execute']
FROZEN = {
    'prepare_ios26.py': 'c77bc990e56dcb47d651f9c054c41313a6671498a5b2494e96bb522ae868fb1a',
    'prepare_ios26_stages.py': '89e242b0c98dd994a04cabaeadc52f8d566ff3fd33fae37e1979ab81fd32b952',
    'cold_boot_ios26.py': '6a57ed164864eef20aeffd34b14b675a8ac597c20583c9f179414a36b4ccbdeb',
    'cold_boot_dt.py': '6931310e1318a6397ee2d7eead966bd0fcdeaae9c10038ca2f2aa01de1a45f7e',
}
APP_SOURCES = {
    'audit_ios26_apps.py': {'bytes': 34103, 'sha256': '6096521f41a8f2caf1c166495d09df28923135dde02295872b98c97a96378291'},
    'audit_ios26_apps_guest.py': {'bytes': 24987, 'sha256': 'aee8d203cc10fdc2a75d93bed9293d66588190e103cddb50720924c46a43c8c5'},
}
SOURCE_HASHES = {
    GUARD: 'ea40638312d6ac41607806ecb03c148fbd0677df6ab01480e13fd40536869674',
    INSPECTOR / 'inspect_ios26_firstboot.py': '2b127ecda390b199287358cdad7e6e7774f5b787148aea524e7b0247a2640cf3',
    INSPECTOR / 'inspect_ios26_firstboot_guest.py': 'ada26de8ababb11bb4af20e558708545eb64fd516481359fd5d0ccf6a7cbae2b',
    INSPECTION_SOURCE: '87526ee42417108f46a8ca03b3fece1cd154f2c439a9c6492f20c97fd6981bb9',
    PARTITION_GUEST: '6874b9b6b68c7fb50c3f9cf05c1b6a86a53f8fed75863c00a6ad9254b1640593',
    **{RUNNER / name: value for name, value in FROZEN.items()},
    **{APPS / name: value['sha256'] for name, value in APP_SOURCES.items()},
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def digest(value):
    return sha(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())


def canonical(path):
    require(path.is_absolute() and path.resolve(strict=True) == path, 'noncanonical path: ' + str(path))
    return path


def read_bytes(path, limit=MAX_METADATA):
    canonical(path)
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= limit,
                'not bounded ordinary metadata: ' + str(path))
        body = stream.read(limit + 1)
    require(len(body) <= limit, 'metadata exceeded bound: ' + str(path))
    return body


def read_json(path):
    return json.loads(read_bytes(path))


def create(name, value):
    canonical(OWNER)
    with os.fdopen(os.open(OWNER / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(OWNER, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def identity(pid):
    require(type(pid) is int and pid > 0, 'invalid process identity')
    try:
        with (Path('/proc') / str(pid) / 'stat').open('rb') as stream:
            raw = stream.read(4097)
    except (FileNotFoundError, ProcessLookupError):
        return None
    require(len(raw) <= 4096, 'process stat exceeded bound')
    return {'pid': pid, 'starttime': int(raw[raw.rfind(b')') + 2:].split()[19])}


def absent(record, label, start_key='starttime'):
    require(type(record) is dict and set(record) == {'pid', start_key} and type(record[start_key]) is int,
            'invalid process record: ' + label)
    require(identity(record['pid']) != {'pid': record['pid'], 'starttime': record[start_key]},
            'recorded process still present: ' + label)


def refuse_live_children():
    records = list((PREP / 'attempts').glob('*/*.child.json'))
    require(len(records) <= 256, 'too many preparation child records')
    for path in records:
        absent(read_json(path), str(path), 'start_ticks')
    absent(read_json(INSPECTION / 'a1/vm.child.json'), 'saved inspection VM', 'start_ticks')
    markers = ((str(PREP) + '/attempts/').encode(), (str(INSPECTION) + '/a1/').encode())
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            with (entry / 'cmdline').open('rb') as stream:
                command = stream.read(131073)
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        require(len(command) <= 131072, 'process cmdline exceeded bound')
        require(not (any(marker in command for marker in markers) and
                     (b'qemu-system-aarch64' in command or b'com.asoft.ios.PrepareInputs' in command)),
                'live previous preparation/inspection child: PID ' + entry.name)


def expected_success_paths():
    return {str(path) for path in (INSPECTION_SOURCE,
            *(INSPECTION_OWNER / name for name in ('command.json', 'owner.json', 'exit.json')),
            *(INSPECTION / name for name in ('inspection-session.json', 'result.json')),
            *(INSPECTION / 'a1' / name for name in ('inspection-result.json', 'expected-policy.json',
                                                   'launch.json', 'vm-result.json', 'vm.child.json')),
            *(INSPECTION / 'a1/files/inspection' / name for name in ('result.json', 'fsck-system.txt', 'fsck-data.txt')))}


def require_finalized():
    require(type(INSPECTION_SUCCESS_PINS) is dict and set(INSPECTION_SUCCESS_PINS) == expected_success_paths(),
            'unreleased owner: fourteen actual accepted saved-inspection pins must be finalized')
    for path, pin in INSPECTION_SUCCESS_PINS.items():
        require(type(pin) is dict and set(pin) == {'bytes', 'sha256'} and
                type(pin['bytes']) is int and 0 < pin['bytes'] <= MAX_METADATA and
                type(pin['sha256']) is str and re.fullmatch('[0-9a-f]{64}', pin['sha256']),
                'malformed saved-inspection pin: ' + path)


def inspection_owner_accepted(inputs):
    startup = read_json(INSPECTION_OWNER / 'owner.json')
    exited = read_json(INSPECTION_OWNER / 'exit.json')
    require(startup.get('schema') == exited.get('schema') == 1 and
            startup.get('command') == read_json(INSPECTION_OWNER / 'command.json') == INSPECTION_COMMAND and
            all(exited.get(key) == startup.get(key) for key in ('command', 'wrapper', 'runner', 'started_utc')) and
            exited.get('exit_code') == exited.get('owner_exit_code') == 0 and
            exited.get('accepted') is True and exited.get('runner_started') is True and
            exited.get('runner_reaped') is True and exited.get('forced_runner') is False and
            exited.get('wrapper_error') is None and exited.get('cleanup_errors') == [] and
            exited.get('finished_utc') and
            exited.get('inspection_result_sha256') == inputs[str(INSPECTION / 'result.json')],
            'saved-inspection owner has not accepted and cleanly reaped the bound result')
    absent(startup['wrapper'], 'saved-inspection wrapper')
    absent(startup['runner'], 'saved-inspection inspector')


def attempt_inventory(final):
    folder = canonical(PREP / 'attempts')
    entries = list(folder.iterdir())
    require(len(entries) <= 128, 'too many preparation attempts')
    names = []
    for path in entries:
        require(re.fullmatch(r'\d{2}-\d{4}', path.name) and path.is_dir() and canonical(path) == path,
                'unknown or noncanonical preparation attempt')
        names.append(path.name)
    require({name for name in names if name.startswith('07-')} == {'07-0001', '07-0002', '07-0003', '07-0004'},
            'preserved firstboot attempts differ')
    later = {name for name in names if int(name[:2]) >= 8}
    require(later == (set(NEXT_ATTEMPTS.values()) if final else set()),
            'unexpected later attempt: only fresh persona/activation/apps are permitted')
    return sorted(name for name in names if int(name[:2]) < 8)


def module_from(body, path):
    module = types.ModuleType('bound_apps_prep_' + path.stem)
    module.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module


def validate_plan(plan, session, inventory, final):
    completed = FIRSTBOOT_STAGES + (NEXT_STAGES if final else [])
    require(plan.get('schema') == 1 and plan.get('status') == 'PREFLIGHT_READY' and
            plan.get('work') == str(PREP) and plan.get('session') == session and
            plan.get('completed') == inventory['completed'] == completed and
            plan.get('artifacts') == inventory['artifacts'] and
            plan.get('remaining') == ([] if final else NEXT_STAGES) and
            plan.get('through') == 'ios26-apps' and plan.get('helper_smoke') is False and
            plan.get('network_stages') == [] and plan.get('guest_boot_stages') == [] and
            plan.get('execution_verified') is False and all(plan.get(k) is v for k, v in NO_BOOT.items()),
            'frozen preflight did not reproduce the exact native helper boundary')


def read_state(final=False):
    """Read-only full provenance validation; the existing saved proof stays at its own prefix."""
    require_finalized()  # Must precede reads, locks, module imports, directories or children.
    require(os.geteuid() == 0, 'root phone owner required')
    for folder in (BASE, PREP, RUNNER, INSPECTOR, INSPECTION, INSPECTION_OWNER, GUARD_WORK, APPS):
        canonical(folder)
    require(not os.path.lexists(APPS_WORK), 'apps audit output already exists; preserve it')
    inputs = {}

    def checked(path, expected=None, size=None):
        body = read_bytes(path)
        inputs[str(path)] = sha(body)
        require(expected is None or inputs[str(path)] == expected, 'changed bound input: ' + str(path))
        require(size is None or len(body) == size, 'changed bound input size: ' + str(path))
        return body

    for path, pin in INSPECTION_SUCCESS_PINS.items():
        checked(Path(path), pin['sha256'], pin['bytes'])
    for path, pin in SOURCE_HASHES.items():
        checked(path, pin)
    checked(Path(__file__).resolve(strict=True))
    install = json.loads(checked(APPS_INSTALL))
    require(install.get('schema') == 1 and install.get('kind') == 'resume1_apps_auditor_sources_install' and
            install.get('source_directory') == str(APPS) and install.get('execution_started') is False and
            install.get('files') == [{'path': name, **pin} for name, pin in APP_SOURCES.items()],
            'counter1 app-auditor installation receipt differs')
    for name, pin in APP_SOURCES.items():
        checked(APPS / name, pin['sha256'], pin['bytes'])
    inspection_owner_accepted(inputs)
    receipt = read_json(INSPECTION / 'inspection-session.json')
    result = read_json(INSPECTION / 'result.json')
    require(receipt.get('prep_work') == str(PREP) and receipt.get('runner_dir') == str(RUNNER) and
            receipt.get('source_directory') == str(INSPECTOR) and receipt.get('guard_source') == str(GUARD) and
            receipt.get('guard_work') == str(GUARD_WORK) and receipt.get('partition_guest_source') == str(PARTITION_GUEST),
            'saved inspection belongs to another source/preparation path')
    session = json.loads(checked(PREP / 'session.json'))
    require(digest(session) == SESSION_DIGEST and session.get('runner_sources') == FROZEN and
            session.get('helper_ram_mib') == 2048 and session.get('helper_vcpus') == 4 and
            session.get('guest_ram_gib') == 3 and session.get('native_required') is True and session.get('tcg_retry') is False,
            'frozen preparation session differs')
    fd = os.open(canonical(PREP / 'owner.lock'), os.O_RDONLY | os.O_NOFOLLOW)
    try:
        require(stat.S_ISREG(os.fstat(fd).st_mode), 'preparation lock is not ordinary')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        refuse_live_children()
        past_attempts = attempt_inventory(final)
        apps = module_from(checked(APPS / 'audit_ios26_apps.py', SOURCE_HASHES[APPS / 'audit_ios26_apps.py']),
                           APPS / 'audit_ios26_apps.py')
        inspector, _ = apps.approved_module(INSPECTOR / 'inspect_ios26_firstboot.py')
        guard, _ = apps.approved_module(GUARD)
        prep = guard.load_frozen(RUNNER, FROZEN)
        parsed = prep.parser().parse_args(COMMAND[4:])
        require(parsed.execute is False and parsed.allow_network is False and parsed.allow_guest_boots is False and
                parsed.helper_seconds == HELPER_SECONDS and parsed.helper_ram_mib == 2048 and parsed.helper_vcpus == 4 and
                parsed.max_log_mib == 64 and parsed.min_free_mib == 1536 and parsed.min_available_mib == 512,
                'preparation command changed helper bounds or permissions')
        plan = prep.preflight(parsed)
        inventory = (apps if final else inspector).checkpoint_inventory(prep, PREP, session)
        validate_plan(plan, session, inventory, final)
        require(inventory['rows']['ios26-firstboot'].get('attempt') == str(PREP / 'attempts/07-0004'),
                'accepted firstboot checkpoint does not belong to 07-0004')
        # Pure validator from the exact reviewed counter1 app auditor. It checks
        # raw journals/fsck/native receipts and full disk hashes without running
        # a helper, remounting, or applying its later eleven-checkpoint preflight.
        prior = apps.saved_inspection(inspector, guard, prep, INSPECTION, receipt, result, inventory, plan, session)
        for path, pin in prior['files'].items():
            checked(Path(path), pin)
        checkpoints = {str(PREP / 'checkpoints' / (stage + '.json')):
                       sha(checked(PREP / 'checkpoints' / (stage + '.json'))) for stage in FIRSTBOOT_STAGES}
        require(prior.get('firstboot_checkpoints') == checkpoints, 'saved proof firstboot prefix differs')
        state = {'inputs': inputs, 'firstboot_checkpoints': checkpoints, 'prior_evidence': prior,
                 'past_attempts': past_attempts, 'plan': plan}
        return state, {'apps': apps, 'prep': prep, 'inventory': inventory, 'session': session}
    finally:
        os.close(fd)


def prerequisites():
    return read_state(False)[0]


def validate_preflight(public, current):
    require(public == current['plan'], 'captured frozen preflight differs from the validated read-only plan')


def resources():
    match = re.search(rb'^MemAvailable:\s+(\d+) kB$', Path('/proc/meminfo').read_bytes(), re.M)
    require(match is not None and int(match[1]) * 1024 >= 2816 << 20, 'native helpers need 2816 MiB MemAvailable')
    free = os.statvfs(PREP)
    require(free.f_bavail * free.f_frsize >= 6_000_000_000, 'apps preparation needs 6000000000 free bytes')


def validate_helper(prep, stage, inventory):
    attempt = PREP / 'attempts' / NEXT_ATTEMPTS[stage]
    checkpoint = inventory['rows'][stage]
    require(checkpoint.get('attempt') == str(attempt) and read_json(attempt / 'stage-result.json') == checkpoint and
            set(checkpoint.get('artifacts', {})) == OUTPUTS[stage], 'new helper checkpoint/output boundary differs: ' + stage)
    predecessors = {}
    for earlier in FIRSTBOOT_STAGES + NEXT_STAGES:
        if earlier == stage:
            break
        predecessors.update(inventory['rows'][earlier]['artifacts'])
    expected_inputs = {name: prep.cold.readonly_identity(prep.contained(PREP, record['path']))
                       for name, record in predecessors.items()}
    require(read_json(attempt / 'stage-inputs.json') ==
            {'stage': stage, 'session_sha256': SESSION_DIGEST, 'inputs': expected_inputs},
            'new helper inputs differ from their own predecessor prefix: ' + stage)
    vm = read_json(attempt / 'vm-result.json')
    cleanup, witness = vm.get('cleanup', {}), vm.get('witnesses', {})
    require(vm.get('schema') == 1 and vm.get('stage') == stage and vm.get('status') == 'VM_OBSERVATION_COMPLETE' and
            prep.vm_success(vm, True) and vm.get('natural_exit') is True and vm.get('done_codes') == [0] and
            vm.get('error') is None and cleanup.get('exit_code') == 0 and cleanup.get('echild') is True and
            cleanup.get('forced_qemu') is False and cleanup.get('forced_descendants') == [] and cleanup.get('errors') == [] and
            witness.get('native_initialization') is True and witness.get('native_execution') is True and
            witness.get('fatal_markers') == [] and all(vm.get(k) is v for k, v in NO_BOOT.items()),
            'new helper lacks natural native completion and clean reap: ' + stage)
    launch = read_json(attempt / 'launch.json')
    argv, env = launch.get('command', []), launch.get('environment', {})
    require(launch.get('deadline_seconds') == HELPER_SECONDS and len(argv) >= 2 and
            argv[0] == str(Path(inventory['session']['package']) / 'qemu-system-aarch64') and
            argv.count('-m') == argv.count('-smp') == 1 and
            argv[argv.index('-m') + 1] == '2048M' and argv[argv.index('-smp') + 1] == '4' and
            env.get('ASOFT_NATIVE_EL0') == '1' and env.get('ASOFT_NATIVE_EL0_REQUIRED') == '1' and
            env.get('ASOFT_NATIVE_EL0_STUBS') == '8' and 'ASOFT_NATIVE_EL0_TPIDRRO' not in env,
            'new helper native launch contract differs: ' + stage)
    absent(read_json(attempt / 'vm.child.json'), stage + ' VM', 'start_ticks')
    for name, record in checkpoint['artifacts'].items():
        require(prep.verify_artifact(record, PREP) == attempt / 'files' / name,
                'new helper output escaped its fresh attempt: ' + stage)
    return {name: {'bytes': len(body), 'sha256': sha(body)} for name in
            ('stage-inputs.json', 'launch.json', 'vm-result.json', 'stage-result.json', 'vm.child.json')
            for body in [read_bytes(attempt / name)]}


def accept_result(current):
    actual, context = read_state(True)
    for name in ('inputs', 'firstboot_checkpoints', 'prior_evidence', 'past_attempts'):
        require(actual[name] == current[name], 'bound earlier evidence changed during helpers: ' + name)
    # Keep the original nonwriting lock through the final helper/chain checks.
    # Reproduce the boundary after reacquiring it; no later preparation may
    # advance the prefix while these complete disk hashes are being read.
    fd = os.open(canonical(PREP / 'owner.lock'), os.O_RDONLY | os.O_NOFOLLOW)
    try:
        require(stat.S_ISREG(os.fstat(fd).st_mode), 'preparation lock is not ordinary')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        refuse_live_children()
        require(attempt_inventory(True) == current['past_attempts'], 'attempt set changed before final acceptance')
        require(context['apps'].checkpoint_inventory(context['prep'], PREP, context['session']) == context['inventory'],
                'apps checkpoint boundary changed before final acceptance')
        inventory = dict(context['inventory'], session=context['session'])
        result_body = read_bytes(PREP / 'result.json')
        result = json.loads(result_body)
        require(result.get('schema') == 1 and result.get('status') == 'PREPARATION_CHECKPOINT' and
                result.get('completed') == FIRSTBOOT_STAGES + NEXT_STAGES and result.get('stage') == 'ios26-apps' and
                result.get('attempt') == str(PREP / 'attempts/10-0001') and not result.get('error') and
                result.get('finished_utc') and all(result.get(k) is v for k, v in NO_BOOT.items()),
                'frozen runner did not finish exactly through apps')
        helpers = {stage: validate_helper(context['prep'], stage, inventory) for stage in NEXT_STAGES}
        # The existing validator checks all five actual backing members plus the
        # original OS against complete stage artifact records. This grants no app
        # copy-audit result; that remains the next separately owned physical gate.
        chain = context['apps'].full_inputs(context['prep'], PREP, context['inventory'])
        require(len(chain) == 6, 'apps preparation does not have the five-member backing chain plus original OS')
        for path, pin in current['inputs'].items():
            require(sha(read_bytes(Path(path))) == pin, 'earlier evidence changed during final acceptance: ' + path)
        require(read_bytes(PREP / 'result.json') == result_body and
                context['apps'].checkpoint_inventory(context['prep'], PREP, context['session']) == context['inventory'],
                'preparation boundary changed during final acceptance')
        refuse_live_children()
        return {'result_sha256': sha(result_body),
                'checkpoints': context['inventory']['hashes'], 'attempts': NEXT_ATTEMPTS,
                'helper_files': helpers, 'input_chains': chain, 'app_copy_audit_passed': False, **NO_BOOT}
    finally:
        os.close(fd)


def wait_bounded(child, log, seconds, limit):
    deadline = time.monotonic() + seconds
    while True:
        require(log.stat().st_size <= limit, 'outer runner log exceeded bound')
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('outer preparation phase deadline')
        try:
            return child.wait(timeout=min(5, remaining))
        except subprocess.TimeoutExpired:
            pass


def run_phase(execute, current):
    prefix, output = ('', 'run.log') if execute else ('preflight-', 'preflight.json')
    command = COMMAND + (['--execute'] if execute else [])
    create(prefix + 'command.json', command)
    started, child, child_identity = utc(), None, None
    forced, error, returncode, accepted, acceptance = False, None, None, False, None
    cleanup_errors = []
    wrapper = identity(os.getpid())

    def interrupted(number, _frame):
        raise InterruptedError('outer owner signal ' + str(number))

    old = {number: signal.signal(number, interrupted) for number in (signal.SIGINT, signal.SIGTERM)}
    try:
        fd = os.open(OWNER / output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
            child_identity = identity(child.pid)
            require(child_identity is not None, 'spawned preparation runner has no process identity')
            create(prefix + 'owner.json', {'schema': 1, 'started_utc': started,
                   'wrapper': wrapper, 'runner': child_identity, 'command': command})
            returncode = wait_bounded(child, OWNER / output, EXECUTION_SECONDS if execute else PREFLIGHT_SECONDS,
                                      (64 << 20) if execute else MAX_METADATA)
            stream.flush()
            os.fsync(stream.fileno())
        require(returncode == 0, 'preparation runner exited ' + str(returncode))
        if execute:
            acceptance = accept_result(current)
        else:
            validate_preflight(read_json(OWNER / output), current)
            require(prerequisites() == current, 'prerequisites changed during read-only preflight')
        accepted = True
    except BaseException as exc:
        error = type(exc).__name__ + ': ' + str(exc)
        for number in old:
            signal.signal(number, signal.SIG_IGN)
        try:
            if child is not None and child.poll() is None:
                # Signal only this wrapper's unreaped direct child. The frozen
                # runner retains its own QMP shutdown, subreaping and PDEATHSIG.
                child.send_signal(signal.SIGTERM)
                try:
                    child.wait(timeout=180)
                except subprocess.TimeoutExpired:
                    forced = True
                    child.kill()
                    child.wait(timeout=30)
        except BaseException as exc:
            cleanup_errors.append(type(exc).__name__ + ': ' + str(exc))
        if child is not None:
            returncode = child.returncode
    finally:
        owner_exit_code = 0 if accepted and not error and not forced and not cleanup_errors and returncode == 0 else 2
        try:
            for number in old:
                signal.signal(number, signal.SIG_IGN)
            stdout_sha = None
            if not execute and (OWNER / output).exists():
                try:
                    stdout_sha = sha(read_bytes(OWNER / output))
                except Exception as exc:
                    cleanup_errors.append('preflight output hash: ' + str(exc))
                    owner_exit_code = 2
            create(prefix + 'exit.json', {'schema': 1, 'started_utc': started, 'finished_utc': utc(),
                   'wrapper': wrapper, 'runner': child_identity, 'exit_code': returncode, 'owner_exit_code': owner_exit_code,
                   'command': command, 'wrapper_error': error, 'forced_runner': forced, 'cleanup_errors': cleanup_errors,
                   'runner_started': child is not None, 'runner_reaped': child is not None and returncode is not None,
                   'accepted': accepted, 'stdout_sha256': stdout_sha, 'acceptance': acceptance,
                   'requires_owned_process_recheck': True})
        finally:
            for number, handler in old.items():
                signal.signal(number, handler)
    return owner_exit_code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--preflight', action='store_true')
    modes.add_argument('--execute', action='store_true')
    parser.add_argument('--preflight-sha256')
    parser.add_argument('--preflight-bytes', type=int)
    args = parser.parse_args(argv)
    try:
        require_finalized()
        current = prerequisites()
        if args.preflight:
            require(args.preflight_sha256 is None and args.preflight_bytes is None, 'preflight cannot consume execution pins')
            OWNER.mkdir(mode=0o700)
            create('prerequisites.json', current)
        else:
            require(type(args.preflight_sha256) is str and re.fullmatch('[0-9a-f]{64}', args.preflight_sha256) and
                    type(args.preflight_bytes) is int and 0 < args.preflight_bytes <= MAX_METADATA,
                    'actual observed preflight SHA-256 and bytes required')
            canonical(OWNER)
            require(read_json(OWNER / 'prerequisites.json') == current, 'accepted preflight inputs changed')
            exited = read_json(OWNER / 'preflight-exit.json')
            startup = read_json(OWNER / 'preflight-owner.json')
            body = read_bytes(OWNER / 'preflight.json')
            require(sha(body) == args.preflight_sha256 and len(body) == args.preflight_bytes, 'observed preflight pin differs')
            require(exited.get('schema') == 1 and exited.get('command') == COMMAND and
                    read_json(OWNER / 'preflight-command.json') == COMMAND and
                    exited.get('exit_code') == exited.get('owner_exit_code') == 0 and exited.get('accepted') is True and
                    exited.get('runner_started') is True and exited.get('runner_reaped') is True and
                    exited.get('forced_runner') is False and exited.get('wrapper_error') is None and
                    exited.get('cleanup_errors') == [] and exited.get('finished_utc') and
                    startup.get('command') == COMMAND and startup.get('started_utc') == exited.get('started_utc') and
                    all(startup.get(k) == exited.get(k) for k in ('wrapper', 'runner')) and sha(body) == exited.get('stdout_sha256'),
                    'missing, failed or mismatched read-only preflight receipt')
            absent(startup['wrapper'], 'preflight wrapper')
            absent(startup['runner'], 'preflight preparation runner')
            validate_preflight(json.loads(body), current)
            resources()
        return run_phase(args.execute, current)
    except Exception as exc:
        print(json.dumps({'schema': 1, 'status': 'APPS_PREP_OWNER_REFUSED',
                          'error': type(exc).__name__ + ': ' + str(exc), **NO_BOOT}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
