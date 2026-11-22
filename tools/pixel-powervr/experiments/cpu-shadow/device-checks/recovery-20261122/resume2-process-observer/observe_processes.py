#!/usr/bin/env python3
"""Bounded diagnostic observer outside the unchanged resume2 inspector tree.

Reads selected receipts and /proc metadata. Never launches, signals, reaps,
ptraces, stops or changes an observed process. Writes only its fresh own files.
Exit zero means observation finished, never that the inspection passed.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import time

BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
OUT = BASE / 'ios26-saved-inspection-resume2-observer'
OWNER = BASE / 'ios26-saved-inspection-resume2-owner'
WORK = Path('/data/local/tmp/pixel-saved-audit-e9cc754-resume2')
OWNER_SOURCE = BASE / 'run-ios26-saved-inspection-resume2.py'
OWNER_SOURCE_PIN = {'bytes': 35799, 'sha256': '445f16736ff3f0c4aca2f9d825f4b71b9264bc24b177fe3a8281ca9c6e0f1e0b'}
PYTHON = '/data/data/com.termux/files/usr/bin/python'
QEMU = str(BASE / 'pixel-cpu-shadow-ksceynt6/cpu-shadow-qualification/qemu-system-aarch64')
COMMAND = [PYTHON, '-I', '-B', '/data/local/tmp/pixel-saved-checks-counter1/inspect_ios26_firstboot.py',
           '--guard-work', '/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1', '--work', str(WORK)]
BOUNDS = {'total_seconds': 9000, 'launch_wait_seconds': 600, 'post_exit_seconds': 5,
          'process_identities': 128, 'tasks_per_process': 128, 'events': 10000,
          'event_bytes': 8 << 20, 'metadata_bytes': 4 << 20, 'summary_bytes': 256 << 10,
          'status_bytes': 64 << 10, 'total_output_bytes': 9 << 20,
          'steady_interval_ms': 200, 'burst_interval_ms': 20, 'burst_seconds': 2,
          'heartbeat_seconds': 1}
SCOPE = {'inspection_owner_directory': str(OWNER), 'inspection_work': str(WORK),
         'inspection_command': COMMAND + ['--execute'], 'qemu_child_record': str(WORK / 'a1/vm.child.json'),
         'qemu_executable': QEMU, 'native_factory_name': 'asoft-stubfac',
         'native_worker_name_pattern': '^asoft-stub[0-9]+$', 'metadata_only': True}
UID = 0


class BoundExceeded(ValueError):
    pass


class UnstableRead(ValueError):
    pass


class ReceiptPending(Exception):
    pass


def require(condition, message):
    if not condition:
        raise ValueError(message)


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def key(row):
    return row['pid'], row['start_ticks']


def small_identity(row):
    return {'pid': row['pid'], 'start_ticks': row['start_ticks']}


def from_owner(row):
    require(type(row) is dict and set(row) == {'pid', 'starttime'} and
            type(row['pid']) is int and row['pid'] > 0 and type(row['starttime']) is int and row['starttime'] > 0,
            'invalid owner process identity')
    return {'pid': row['pid'], 'start_ticks': row['starttime']}


def file_bytes(path, limit=4 << 20):
    require(path.is_absolute() and path.resolve(strict=True) == path, 'noncanonical receipt/source path')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        a = os.fstat(stream.fileno())
        require(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and a.st_uid == UID and a.st_size <= limit,
                'receipt/source is not bounded ordinary root-owned data')
        body = stream.read(limit + 1)
        b = os.fstat(stream.fileno())
    if not (len(body) == a.st_size <= limit and
            (a.st_dev, a.st_ino, a.st_size, a.st_mtime_ns, a.st_ctime_ns) ==
            (b.st_dev, b.st_ino, b.st_size, b.st_mtime_ns, b.st_ctime_ns)):
        raise UnstableRead('receipt/source changed while reading')
    c = path.stat()
    if (a.st_dev, a.st_ino, a.st_size, a.st_mtime_ns, a.st_ctime_ns) != (c.st_dev, c.st_ino, c.st_size, c.st_mtime_ns, c.st_ctime_ns):
        raise UnstableRead('receipt/source path changed while reading')
    return body


def read_json(path):
    body = file_bytes(path)
    return json.loads(body), {'path': str(path), 'bytes': len(body), 'sha256': sha(body)}


def poll_json(path, pending, now, emit):
    """Retry only initial publication, at most two seconds; bound receipts stay strict."""
    name = str(path)
    try:
        result = read_json(path)
    except FileNotFoundError:
        if name in pending and now - pending[name]['since'] > 2:
            raise ValueError('receipt disappeared during publication: ' + name)
        raise ReceiptPending(name)
    except (UnstableRead, json.JSONDecodeError) as error:
        if name not in pending:
            pending[name] = {'since': now, 'attempts': 0}
            emit('receipt_publication_gap', path=name, error=type(error).__name__)
        pending[name]['attempts'] += 1
        if now - pending[name]['since'] > 2:
            raise ValueError('receipt did not become stable valid JSON within two seconds: ' + name)
        raise ReceiptPending(name)
    if name in pending:
        emit('receipt_publication_recovered', path=name, **pending.pop(name))
    return result


def write_json(name, value, limit=256 << 10, replace=False):
    body = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
    if len(body) > limit:
        raise BoundExceeded('own metadata output bound: ' + name)
    target = OUT / name
    path = OUT / (name + '.next') if replace else target
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    if replace:
        os.replace(path, target)
    directory = os.open(OUT, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return {'path': str(target), 'bytes': len(body), 'sha256': sha(body)}


def parse_stat(body, pid):
    require(len(body) <= 4096 and body.find(b'(') > 0 and body.rfind(b')') > body.find(b'('), 'invalid bounded proc stat')
    left, right = body.find(b'('), body.rfind(b')')
    require(int(body[:left].strip()) == pid, 'proc stat PID differs')
    fields = body[right + 1:].split()
    require(len(fields) >= 20 and len(fields[0]) == 1, 'short proc stat')
    return {'pid': pid, 'start_ticks': int(fields[19]), 'ppid': int(fields[1]), 'pgrp': int(fields[2]),
            'session': int(fields[3]), 'state': fields[0].decode('ascii'),
            'comm': body[left + 1:right].decode('utf-8', errors='replace'), 'threads': int(fields[17])}


def parse_status(body, pid):
    require(len(body) <= 16384, 'proc status exceeded bound')
    fields = dict(line.split(b':', 1) for line in body.splitlines() if b':' in line)
    require(int(fields[b'Pid']) == int(fields[b'Tgid']) == pid, 'not a process leader status')
    pending = {}
    for name in (b'SigPnd', b'ShdPnd'):
        value = fields[name].strip()
        require(re.fullmatch(rb'[0-9a-fA-F]{1,32}', value) is not None, 'invalid pending signal mask')
        pending[name.decode()] = value.decode()
    return {'tgid': pid, 'status_ppid': int(fields[b'PPid']), 'pending': pending,
            'kill_pending': bool((int(pending['SigPnd'], 16) | int(pending['ShdPnd'], 16)) & (1 << 8))}


def parse_children(body):
    require(len(body) <= 8192, 'task children exceeded bound')
    values = body.split()
    require(len(values) <= 128 and all(re.fullmatch(rb'[0-9]+', value) for value in values), 'invalid task child inventory')
    result = {int(value) for value in values}
    require(all(pid > 0 for pid in result), 'invalid child PID')
    return sorted(result)


class Proc:
    def __init__(self, root=Path('/proc')):
        self.root = root

    def bounded(self, path, limit):
        with path.open('rb') as stream:
            body = stream.read(limit + 1)
        require(len(body) <= limit, 'proc read exceeded bound')
        return body

    def stat(self, pid):
        require(type(pid) is int and pid > 0, 'invalid proc PID')
        return parse_stat(self.bounded(self.root / str(pid) / 'stat', 4096), pid)

    def snapshot(self, pid):
        first = self.stat(pid)
        status = parse_status(self.bounded(self.root / str(pid) / 'status', 16384), pid)
        try:
            executable = os.readlink(self.root / str(pid) / 'exe')
            require(len(executable) <= 4096, 'proc exe exceeded bound')
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            executable = None
        last = self.stat(pid)
        require(key(first) == key(last), 'proc identity changed during snapshot')
        return dict(last, **status, executable=executable,
                    parent_changed_during_snapshot=first['ppid'] != last['ppid'] or status['status_ppid'] != last['ppid'])

    def children(self, parent):
        require(key(self.stat(parent['pid'])) == key(parent), 'parent identity changed before children read')
        tasks, children, lost_tasks = 0, set(), 0
        for entry in (self.root / str(parent['pid']) / 'task').iterdir():
            if not entry.name.isdigit():
                continue
            tasks += 1
            if tasks > BOUNDS['tasks_per_process']:
                raise BoundExceeded('task count bound')
            try:
                children.update(parse_children(self.bounded(entry / 'children', 8192)))
            except (FileNotFoundError, ProcessLookupError):
                lost_tasks += 1
                continue
            if len(children) > BOUNDS['process_identities']:
                raise BoundExceeded('direct child count bound')
        require(key(self.stat(parent['pid'])) == key(parent), 'parent identity changed after children read')
        return sorted(children), lost_tasks


class Events:
    def __init__(self):
        self.stream = os.fdopen(os.open(OUT / 'events.jsonl', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb')
        self.count, self.bytes, self.hash = 0, 0, hashlib.sha256()

    def emit(self, kind, **fields):
        body = (json.dumps({'event': kind, 'utc': utc(), 'monotonic_ns': time.monotonic_ns(), **fields},
                           sort_keys=True, separators=(',', ':')) + '\n').encode()
        if self.count >= BOUNDS['events'] or self.bytes + len(body) > BOUNDS['event_bytes']:
            raise BoundExceeded('event count/byte bound')
        self.stream.write(body)
        self.hash.update(body)
        self.count += 1
        self.bytes += len(body)

    def flush(self):
        self.stream.flush()
        os.fsync(self.stream.fileno())


class Graph:
    def __init__(self, proc, emit, self_identity):
        self.proc, self.emit, self.self_identity = proc, emit, self_identity
        self.rows, self.gaps, self.routine_state_changes = {}, 0, 0
        self.changed = False

    def gap(self, operation, identity, error):
        self.gaps += 1
        self.emit('read_gap', operation=operation, identity=identity, error=type(error).__name__ + ': ' + str(error)[:200])

    @staticmethod
    def native_role(snapshot, role):
        if role == 'descendant' and snapshot.get('executable') == QEMU:
            if snapshot['comm'] == 'asoft-stubfac':
                return 'native_factory'
            if re.fullmatch(r'asoft-stub[0-9]+', snapshot['comm']):
                return 'native_worker'
        return role

    def has_qemu_ancestor(self, parent):
        seen = set()
        while parent is not None and key(parent) in self.rows:
            identity = key(parent)
            require(identity not in seen, 'cyclic observed genealogy')
            seen.add(identity)
            row = self.rows[identity]
            if row['role'] == 'qemu':
                return True
            parent = row['first_observed_parent']
        return False

    def add(self, snapshot, role, parent=None):
        require(key(snapshot) != key(self.self_identity), 'observer entered the inspected descendant tree')
        if key(snapshot) in self.rows:
            row = self.rows[key(snapshot)]
            if role in ('inspection_owner', 'inspector', 'qemu') and row['role'] != role:
                row['role'] = role
                self.emit('receipt_anchor_bound', identity=small_identity(snapshot), role=role)
            return
        if len(self.rows) >= BOUNDS['process_identities']:
            raise BoundExceeded('process identity bound')
        if self.has_qemu_ancestor(parent):
            role = self.native_role(snapshot, role)
        self.rows[key(snapshot)] = {'identity': small_identity(snapshot), 'role': role,
            'first_observed_parent': parent, 'last': snapshot, 'present': True,
            'first_monotonic_ns': time.monotonic_ns(), 'last_monotonic_ns': time.monotonic_ns()}
        self.emit('identity_observed', identity=small_identity(snapshot), role=role, parent=parent, snapshot=snapshot)
        self.changed = True

    def anchor(self, identity, role, expected_parent=None, expected_executable=None):
        require(type(identity) is dict and set(identity) == {'pid', 'start_ticks'} and
                type(identity['pid']) is int and type(identity['start_ticks']) is int and
                identity['pid'] > 0 and identity['start_ticks'] > 0, 'invalid receipt anchor')
        try:
            snapshot = self.proc.snapshot(identity['pid'])
        except (FileNotFoundError, ProcessLookupError) as error:
            self.gap('receipt identity already absent', identity, error)
            if key(identity) in self.rows:
                old = self.rows[key(identity)]['last']
                if expected_executable is not None:
                    require(old['executable'] == expected_executable, 'earlier observed QEMU executable differs or unavailable')
                self.add(old, role, expected_parent)
                return True
            return False
        require(key(snapshot) == key(identity), 'receipt PID identity was reused')
        if expected_parent is not None:
            require(snapshot['ppid'] == expected_parent['pid'], 'receipt child is not under its recorded owner')
        if expected_executable is not None:
            require(snapshot['executable'] == expected_executable or
                    snapshot['state'] in 'ZXx' and snapshot['executable'] is None,
                    'live QEMU executable differs or is unavailable')
            self.emit('anchor_executable', identity=identity, expected=expected_executable,
                      verified=snapshot['executable'] == expected_executable, state=snapshot['state'])
        self.add(snapshot, role, expected_parent)
        return True

    def sample(self):
        self.changed = False
        queue = [identity for identity, row in self.rows.items() if row['present']]
        done = set()
        while queue:
            identity = queue.pop(0)
            if identity in done:
                continue
            done.add(identity)
            row = self.rows[identity]
            try:
                now = self.proc.snapshot(identity[0])
                if key(now) != identity:
                    row['present'] = False
                    self.emit('identity_reused', identity=row['identity'], replacement_start_ticks=now['start_ticks'])
                    self.changed = True
                    continue  # Never attach the replacement without a fresh owned-parent edge.
            except (FileNotFoundError, ProcessLookupError):
                row['present'] = False
                self.emit('identity_absent', identity=row['identity'])
                self.changed = True
                continue
            except (PermissionError, ValueError, OSError) as error:
                self.gap('snapshot', row['identity'], error)
                continue
            prior = row['last']
            if now['parent_changed_during_snapshot']:
                self.gap('parent changed during snapshot', row['identity'], ValueError('parent fields sampled at different times'))
            role = self.native_role(now, row['role']) if self.has_qemu_ancestor(row['first_observed_parent']) else row['role']
            if role != row['role']:
                row['role'] = role
                self.emit('native_role_observed', identity=row['identity'], role=role, snapshot=now)
                self.changed = True
            meaningful = (now['ppid'] != prior['ppid'] or now['comm'] != prior['comm'] or
                          now['kill_pending'] != prior['kill_pending'] or
                          now['state'] != prior['state'] and (now['state'] in 'ZDXTtx' or prior['state'] in 'ZDXTtx'))
            if meaningful:
                self.emit('process_change', identity=row['identity'], previous_parent_pid=prior['ppid'], snapshot=now)
                self.changed = True
            elif now['state'] != prior['state']:
                self.routine_state_changes += 1
            row['last'], row['last_monotonic_ns'] = now, time.monotonic_ns()
            if row['role'] == 'inspection_owner' or now['state'] in 'ZXx':
                continue  # The inspector subtree is the discovery boundary.
            try:
                children, lost_tasks = self.proc.children(now)
                if lost_tasks:
                    self.gap('task exited during child discovery', row['identity'], ValueError(str(lost_tasks) + ' task inventories unavailable'))
            except BoundExceeded:
                raise
            except (FileNotFoundError, ProcessLookupError, PermissionError, ValueError, OSError) as error:
                self.gap('children', row['identity'], error)
                continue
            for pid in children:
                try:
                    child = self.proc.snapshot(pid)
                    if child['ppid'] != now['pid']:
                        self.gap('child reparented before enrollment', {'pid': pid}, ValueError('child edge no longer matches'))
                        continue
                    require(key(self.proc.stat(now['pid'])) == identity, 'parent was reused during enrollment')
                    self.add(child, 'descendant', small_identity(now))
                    if key(child) not in done:
                        queue.append(key(child))
                except BoundExceeded:
                    raise
                except (FileNotFoundError, ProcessLookupError, PermissionError, ValueError, OSError) as error:
                    if 'observer entered' in str(error):
                        raise
                    self.gap('child enrollment', {'pid': pid}, error)

    def live(self):
        return [dict(row['last'], role=row['role']) for row in self.rows.values() if row['present']]


def prerequisites(preflight_sha, preflight_bytes, proc=None):
    proc = proc or Proc()
    require(os.geteuid() == UID and BASE.resolve(strict=True) == BASE, 'root and canonical transfer base required')
    require(re.fullmatch('[0-9a-f]{64}', preflight_sha or '') is not None and
            type(preflight_bytes) is int and 0 < preflight_bytes <= BOUNDS['metadata_bytes'], 'actual preflight identity required')
    source = file_bytes(OWNER_SOURCE)
    require({'bytes': len(source), 'sha256': sha(source)} == OWNER_SOURCE_PIN, 'retry owner source differs')
    public, pin = read_json(OWNER / 'preflight.json')
    startup, startup_pin = read_json(OWNER / 'preflight-owner.json')
    exited, exit_pin = read_json(OWNER / 'preflight-exit.json')
    command, command_pin = read_json(OWNER / 'preflight-command.json')
    require(pin['bytes'] == preflight_bytes and pin['sha256'] == preflight_sha and
            public.get('schema') == 1 and public.get('status') == 'PREFLIGHT_READY' and
            public.get('inspection_session', {}).get('guard_work') == '/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1' and
            command == startup.get('command') == exited.get('command') == COMMAND and
            exited.get('schema') == 1 and exited.get('accepted') is True and
            exited.get('exit_code') == exited.get('owner_exit_code') == 0 and
            exited.get('runner_started') is True and exited.get('runner_reaped') is True and
            exited.get('forced_runner') is False and exited.get('wrapper_error') is None and exited.get('cleanup_errors') == [] and
            exited.get('stdout_sha256') == preflight_sha and exited.get('finished_utc') and
            all(exited.get(name) == startup.get(name) for name in ('started_utc', 'wrapper', 'runner')),
            'retry preflight has not accepted/reaped the exact command and output')
    for name in ('wrapper', 'runner'):
        old = from_owner(startup[name])
        try:
            require(key(proc.stat(old['pid'])) != key(old), 'preflight process remains present')
        except (FileNotFoundError, ProcessLookupError):
            pass
    require(not os.path.lexists(WORK), 'retry inspection work already exists')
    for name in ('owner.json', 'command.json', 'exit.json'):
        require(not os.path.lexists(OWNER / name), 'retry execution already has receipts')
    return {'inspection_owner_source': {'path': str(OWNER_SOURCE), **OWNER_SOURCE_PIN},
            'preflight': dict(pin, exit_sha256=exit_pin['sha256']),
            'bound_inputs': [dict(path=str(OWNER_SOURCE), **OWNER_SOURCE_PIN), pin, startup_pin, exit_pin, command_pin]}


def outside_inspector(proc, self_identity, inspector):
    require(self_identity['start_ticks'] <= inspector['start_ticks'], 'observer was not ready before the inspector')
    current, seen = self_identity['pid'], set()
    for _ in range(64):
        if current <= 0:
            return True
        require(current not in seen, 'cyclic process ancestry')
        seen.add(current)
        row = proc.stat(current)
        require(key(row) != key(inspector), 'observer lies in inspector descendant subtree')
        current = row['ppid']
    raise BoundExceeded('observer ancestry depth bound')


def run(preflight_sha, preflight_bytes):
    proc = Proc()
    bound = prerequisites(preflight_sha, preflight_bytes, proc)
    self_row = proc.snapshot(os.getpid())
    require(self_row['session'] == self_row['pgrp'] == self_row['pid'], 'observer must have its own detached session')
    self_children, self_task_gaps = proc.children(self_row)
    require(not self_children and self_task_gaps == 0, 'observer self child-inventory probe failed')
    source_body = file_bytes(Path(__file__).resolve(strict=True))
    source = {'path': str(Path(__file__).resolve(strict=True)), 'bytes': len(source_body), 'sha256': sha(source_body)}
    OUT.mkdir(mode=0o700)
    events = Events()
    graph = Graph(proc, events.emit, small_identity(self_row))
    begin = time.monotonic()
    ready = {'schema': 1, 'kind': 'saved_inspection_process_observer_ready', 'status': 'READY',
             'ready_utc': utc(), 'ready_monotonic_ns': time.monotonic_ns(),
             'observer': small_identity(self_row), 'observer_process': self_row, 'source': source,
             'output_directory': str(OUT), 'scope': SCOPE, 'bounds': BOUNDS,
             'inspection_owner_source': bound['inspection_owner_source'], 'preflight': bound['preflight'],
             'child_inventory_probe': {'readable': True, 'children': [], 'task_read_gaps': 0},
             'independent_session': True, 'target_execution_absent_at_ready': True, 'diagnostic_only': True}
    write_json('session.json', dict(ready, bound_inputs=bound['bound_inputs']))
    ready_pin = write_json('ready.json', ready, 16 << 10)
    events.emit('ready', observer=ready['observer'], scope=SCOPE)
    owner, owner_pin, qemu, exit_value = None, None, None, None
    owner_ids, qemu_anchor_seen, errors, pending_receipts = {}, False, [], {}
    final_status, returncode, sample_count, sample_gaps = 'OBSERVER_INCOMPLETE', 2, 0, 0
    last_sample, last_heartbeat, burst_until, exit_seen = begin, 0, begin + 2, None

    def heartbeat(phase, status='RUNNING', compact=False):
        events.flush()
        live = graph.live()
        if compact:
            live = [{k: row[k] for k in ('pid', 'start_ticks', 'role', 'ppid', 'state', 'kill_pending')} for row in live]
        return write_json('status.json', {'schema': 1, 'kind': 'saved_inspection_process_observer_status',
            'status': status, 'phase': phase, 'heartbeat_utc': utc(), 'heartbeat_monotonic_ns': time.monotonic_ns(),
            'observer': ready['observer'], 'source_sha256': source['sha256'], 'ready_sha256': ready_pin['sha256'],
            'output_directory': str(OUT), 'scope': SCOPE, 'sample_count': sample_count,
            'sample_gaps': sample_gaps, 'read_gaps': graph.gaps, 'events': {'count': events.count, 'bytes': events.bytes},
            'tracked_identities': len(graph.rows), 'live': live, 'compact_final_status': compact,
            'diagnostic_only': True}, BOUNDS['status_bytes'], True)

    def interrupted(number, _frame):
        raise InterruptedError('observer received signal ' + str(number))

    previous_handlers = {s: signal.signal(s, interrupted) for s in (signal.SIGINT, signal.SIGTERM)}
    try:
        heartbeat('WAITING_FOR_EXECUTION_OWNER')
        while True:
            now = time.monotonic()
            if now - begin > BOUNDS['total_seconds']:
                raise BoundExceeded('total observation duration')
            if owner is None and now - begin > BOUNDS['launch_wait_seconds']:
                raise BoundExceeded('execution owner was not observed before launch-wait deadline')
            interval = BOUNDS['burst_interval_ms'] / 1000 if now < burst_until else BOUNDS['steady_interval_ms'] / 1000
            if now - last_sample > max(0.5, 3 * interval):
                sample_gaps += 1
                events.emit('sampling_gap', elapsed_ms=round((now - last_sample) * 1000, 3), intended_interval_ms=interval * 1000)
            last_sample, sample_count = now, sample_count + 1
            if owner is None:
                try:
                    candidate, candidate_pin = poll_json(OWNER / 'owner.json', pending_receipts, now, events.emit)
                    command, _ = poll_json(OWNER / 'command.json', pending_receipts, now, events.emit)
                except ReceiptPending:
                    candidate = None
                if candidate is not None:
                    require(candidate.get('schema') == 1 and candidate.get('command') == command == SCOPE['inspection_command'],
                            'execution owner command differs from fixed inspection scope')
                    owner_ids = {name: from_owner(candidate[name]) for name in ('wrapper', 'runner')}
                    require(key(owner_ids['wrapper']) != key(owner_ids['runner']), 'owner and inspector identities coincide')
                    outside_inspector(proc, ready['observer'], owner_ids['runner'])
                    graph.anchor(owner_ids['wrapper'], 'inspection_owner')
                    graph.anchor(owner_ids['runner'], 'inspector', owner_ids['wrapper'])
                    owner, owner_pin = candidate, candidate_pin
                    events.emit('execution_owner_bound', receipt=owner_pin, identities=owner_ids)
                    burst_until = now + BOUNDS['burst_seconds']
            if owner is not None and qemu is None:
                try:
                    candidate, candidate_pin = poll_json(WORK / 'a1/vm.child.json', pending_receipts, now, events.emit)
                    launch, launch_pin = poll_json(WORK / 'a1/launch.json', pending_receipts, now, events.emit)
                except ReceiptPending:
                    candidate = None
                if candidate is not None:
                    require(type(candidate) is dict and set(candidate) == {'pid', 'start_ticks'}, 'invalid QEMU identity receipt')
                    require(launch.get('command', [None])[0] == QEMU and
                            launch.get('environment', {}).get('ASOFT_NATIVE_EL0_REQUIRED') == '1', 'QEMU launch is outside native helper scope')
                    qemu_anchor_seen = graph.anchor(candidate, 'qemu', owner_ids['runner'], QEMU)
                    qemu = candidate
                    events.emit('qemu_receipt_bound', identity=qemu, receipt=candidate_pin, launch=launch_pin,
                                process_observed=qemu_anchor_seen)
            graph.sample()
            if graph.changed:
                burst_until = now + BOUNDS['burst_seconds']
            if owner is not None:
                current, pin = read_json(OWNER / 'owner.json')
                require(pin == owner_pin and current == owner, 'bound execution owner receipt changed')
                try:
                    value, pin = poll_json(OWNER / 'exit.json', pending_receipts, now, events.emit) if exit_value is None else read_json(OWNER / 'exit.json')
                except ReceiptPending:
                    value = None
                if value is not None:
                    require(value.get('schema') == 1 and value.get('command') == owner['command'] and
                            all(value.get(name) == owner.get(name) for name in ('started_utc', 'wrapper', 'runner')) and
                            value.get('finished_utc'), 'execution exit does not match the bound owner')
                    if exit_value is None:
                        exit_value, exit_seen = value, now
                        events.emit('inspection_outer_exit_observed', receipt=pin, exit_code=value.get('exit_code'),
                                    owner_exit_code=value.get('owner_exit_code'), accepted=value.get('accepted'))
                        burst_until = now + BOUNDS['burst_seconds']
                    else:
                        require(value == exit_value, 'bound execution exit changed')
            phase = 'AFTER_OUTER_EXIT' if exit_seen is not None else 'OBSERVING_HELPER' if qemu else 'WAITING_FOR_HELPER' if owner else 'WAITING_FOR_EXECUTION_OWNER'
            if now - last_heartbeat >= BOUNDS['heartbeat_seconds']:
                heartbeat(phase)
                last_heartbeat = now
            if exit_seen is not None and now - exit_seen >= BOUNDS['post_exit_seconds']:
                final_status, returncode = 'OBSERVATION_FINISHED', 0
                break
            time.sleep(interval)
        for pin in bound['bound_inputs'] + [source]:
            body = file_bytes(Path(pin['path']))
            require(len(body) == pin['bytes'] and sha(body) == pin['sha256'], 'bound source/preflight changed during observation')
    except BaseException as error:
        final_status, returncode = 'OBSERVER_INCOMPLETE', 2
        errors.append(type(error).__name__ + ': ' + str(error)[:500])
    finally:
        for s in previous_handlers:
            signal.signal(s, signal.SIG_IGN)
        events.flush()
        summary = {'schema': 1, 'status': final_status, 'diagnostic_only': True, 'finished_utc': utc(),
            'observer': ready['observer'], 'source': source, 'ready': ready_pin, 'scope': SCOPE, 'bounds': BOUNDS,
            'elapsed_seconds': time.monotonic() - begin, 'sample_count': sample_count,
            'sampling_gaps': sample_gaps, 'read_gaps': graph.gaps,
            'routine_state_changes_not_individually_logged': graph.routine_state_changes,
            'owner_receipt': owner_pin, 'qemu_receipt_identity': qemu,
            'qemu_identity_observed_alive_or_zombie': qemu_anchor_seen,
            'inspection_outer_exit': None if exit_value is None else {k: exit_value.get(k) for k in ('exit_code', 'owner_exit_code', 'accepted', 'finished_utc')},
            'processes': list(graph.rows.values()), 'remaining_observed_identities': [small_identity(row) for row in graph.live()],
            'events': {'path': str(OUT / 'events.jsonl'), 'count': events.count, 'bytes': events.bytes, 'sha256': events.hash.hexdigest()},
            'unresolved_receipt_publication_gaps': pending_receipts,
            'errors': errors, 'observer_signals_to_targets': False, 'observer_reaped_targets': False,
            'absence_is_not_an_exit_status': True, 'sampling_cannot_prove_counterfactual_grace': True}
        try:
            summary_pin = write_json('summary.json', summary, BOUNDS['summary_bytes'])
        except BoundExceeded:
            final_status, returncode = 'OBSERVER_INCOMPLETE', 2
            errors.append('BoundExceeded: full summary capacity; process details remain in bounded events')
            summary['status'] = final_status
            summary['full_process_summary_omitted_for_bound'] = True
            summary['processes'] = [{'identity': row['identity'], 'role': row['role'],
                'present': row['present'], 'first_observed_parent': row['first_observed_parent'],
                'last_parent_pid': row['last']['ppid'], 'last_state': row['last']['state']}
                for row in graph.rows.values()]
            summary_pin = write_json('summary.json', summary, BOUNDS['summary_bytes'])
        heartbeat('FINISHED', final_status, compact=True)
        write_json('exit.json', {'schema': 1, 'status': final_status, 'exit_code': returncode,
            'observer': ready['observer'], 'finished_utc': utc(), 'summary': summary_pin,
            'errors': errors, 'diagnostic_only': True}, 16 << 10)
        events.stream.close()
        for s, handler in previous_handlers.items():
            signal.signal(s, handler)
    print(json.dumps({'status': final_status, 'output_directory': str(OUT), 'diagnostic_only': True}), flush=True)
    return returncode


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight-sha256', required=True)
    parser.add_argument('--preflight-bytes', required=True, type=int)
    args = parser.parse_args(argv)
    try:
        return run(args.preflight_sha256, args.preflight_bytes)
    except Exception as error:
        print(json.dumps({'status': 'OBSERVER_REFUSED', 'error': type(error).__name__ + ': ' + str(error)[:500],
                          'diagnostic_only': True}), flush=True)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
