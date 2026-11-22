"""Local-only source binding and later actual-result finalization.

Preparation writes the compact pin collector. Detailed projections are created
only from the original independently reviewed physical pin observation. No
phone operation, source installation or diagnostic launch occurs here.
"""
import ast
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import sys

ROOT = Path(__file__).resolve().parent
BASE = '/data/local/tmp/pixel-gpu-transfer-sxtv33sh'
SOURCE = BASE + '/run-ios26-data-journal-diagnostic-resume5.py'
RESULT = BASE + '/ios26-data-journal-diagnostic-resume5/result.json'
PYTHON = '/data/data/com.termux/files/usr/bin/python'
HOST_PIN = {'bytes': 51923, 'sha256': '85194af9e14f68e16d1990e79603060644a892c772adafc51dc52777055c77c9'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def read(path, limit=1 << 20):
    require(path.resolve(strict=True) == path, 'canonical local binding input required')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        a = os.fstat(stream.fileno())
        require(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and 0 <= a.st_size <= limit,
                'ordinary bounded local input required')
        body = stream.read(limit + 1)
        b = os.fstat(stream.fileno())
    require(len(body) == a.st_size <= limit and
            (a.st_dev, a.st_ino, a.st_size, a.st_mtime_ns, a.st_ctime_ns) ==
            (b.st_dev, b.st_ino, b.st_size, b.st_mtime_ns, b.st_ctime_ns), 'local binding input changed')
    return body


def bind(template, values):
    tree = ast.parse(template)
    found = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in values:
                require(isinstance(node.value, ast.Constant) and node.value.value is None,
                        'preserved template constant was already bound')
                node.value = ast.parse(repr(values[name]), mode='eval').body
                found.add(name)
    require(found == set(values), 'binding constant missing')
    body = (ast.unparse(ast.fix_missing_locations(tree)) + '\n').encode()
    def without_pins(raw):
        parsed = ast.parse(raw)
        parsed.body = [node for node in parsed.body if not (
            isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in values
                                                for target in node.targets))]
        return ast.dump(parsed, include_attributes=False)
    require(without_pins(template) == without_pins(body), 'binding changed executable logic')
    return body


def command(body, mode, page=0):
    encoded = base64.b64encode(gzip.compress(body, mtime=0)).decode()
    loader = ('import base64,gzip,hashlib;b=gzip.decompress(base64.b64decode(' + repr(encoded) +
              ',validate=True));assert len(b)==' + str(len(body)) +
              ' and hashlib.sha256(b).hexdigest()==' + repr(pin(body)['sha256']) +
              ';exec(compile(b,"readonly-data-journal-projection","exec"),{"__name__":"__main__",' +
              '"__mode__":' + repr(mode) + ',"__page__":' + repr(page) + '})')
    output = (PYTHON + ' -I -B -c ' + shlex.quote(loader) + '\n').encode()
    require(len(output) <= 6000, 'terminal command exceeds6000bytes')
    return output


def save_fresh(directory, outputs):
    directory.mkdir(mode=0o700)
    for name, body in outputs.items():
        with (directory / name).open('xb') as stream:
            stream.write(body)


def reviewed_source():
    body = read(ROOT.parent / 'host/inspect_data_journal.py', HOST_PIN['bytes'])
    require(pin(body) == HOST_PIN, 'reviewed host source differs')
    review_path = ROOT.parent / 'host/independent-host-source-review.json'
    review_body = read(review_path)
    review = json.loads(review_body)
    require(review.get('host_source_released') is True and review.get('findings') == [] and
            {key: review['source'][key] for key in ('bytes', 'sha256')} == HOST_PIN,
            'host source lacks its actual independent release')
    return review_path, review_body


def prepare():
    review_path, review_body = reviewed_source()
    template = read(ROOT / 'observe_result_pin_UNRELEASED.py')
    body = bind(template, {'SOURCE_PIN': HOST_PIN})
    cmd = command(body, 'pin')
    record = {'schema': 1, 'status': 'SOURCE_BOUND_RESULT_COLLECTOR_PENDING_INDEPENDENT_REVIEW',
              'host_source': {'path': SOURCE, **HOST_PIN},
              'host_source_review': {'path': str(review_path), **pin(review_body)},
              'template': pin(template), 'reader': pin(body), 'command': pin(cmd),
              'only_executable_delta': 'SOURCE_PIN; AST unparse changes formatting only',
              'actual_result_pin': None, 'native_tool_or_guest_started': False}
    save_fresh(ROOT / 'source-binding', {'observe_result_pin.py': body,
               'observe-result-pin.command.txt': cmd,
               'source-binding.json': (json.dumps(record, sort_keys=True, indent=2) + '\n').encode()})
    return record


def finalize(observation_path):
    reviewed_source()
    path = Path(observation_path).resolve(strict=True)
    require(path.is_relative_to(ROOT.parent), 'physical observation is outside this diagnostic package')
    observation_body = read(path)
    observed = json.loads(observation_body)
    require(observed.get('independently_reviewed') is True,
            'actual original physical observation requires independent review')
    review_path = (path.parent / observed['independent_review']).resolve(strict=True)
    require(review_path.is_relative_to(ROOT.parent), 'evidence review is outside this diagnostic package')
    review_body = read(review_path)
    require(type(json.loads(review_body)) is dict, 'evidence review is not an object')
    require(observed.get('status') == 'DATA_JOURNAL_RESULT_BINDING_READY' and
            observed.get('diagnostic_status') == 'READONLY_DATA_JOURNAL_DIAGNOSTIC_OBSERVED' and
            observed.get('readonly') is True and
            observed.get('source') == {'path': SOURCE, **HOST_PIN}, 'actual result collector scope differs')
    require(all(observed.get(key) is True for key in
                ('owner_absent', 'owned_child_pids_absent', 'all_own_tool_children_reaped',
                 'recorded_inspection_processes_absent', 'disk_identities_unchanged', 'bound_metadata_unchanged',
                 'bound_tooling_unchanged', 'owned_child_exit_receipts_verified')) and
            observed.get('forced_tool_children') == [] and observed.get('tool_commands') == 4 and
            observed.get('retained_read_count') == 4, 'actual clean metadata completion is missing')
    require(all(observed.get(key) is False for key in
                ('whole_image_hashes_recomputed', 'raw_bytes_exported', 'private_file_inventories_exported',
                 'inspection_success_claimed', 'filesystem_consistency_claimed', 'replay_safety_claimed',
                 'native_tool_or_guest_started', 'actual_result_bound_before_query',
                 'retained_payloads_reverified', 'pure_parser_recomputed')),
            'actual collector diagnostic-only scope differs')
    row = observed['result']
    require(row.get('path') == RESULT and type(row.get('bytes')) is int and 0 < row['bytes'] <= 128 << 10 and
            type(row.get('sha256')) is str and re.fullmatch('[0-9a-f]{64}', row['sha256']),
            'actual result pin is malformed')
    digest = row.get('digest_bytes')
    require(type(digest) is list and len(digest) == 32 and
            all(type(value) is int and 0 <= value <= 255 for value in digest) and
            bytes(digest).hex() == row['sha256'], 'all32 observed digest bytes must match hex')
    result_pin = {key: row[key] for key in ('bytes', 'sha256')}
    template = read(ROOT / 'observe_data_journal_UNRELEASED.py')
    body = bind(template, {'SOURCE_PIN': HOST_PIN, 'RESULT_PIN': result_pin})
    outputs = {'observe_data_journal.py': body}
    commands = []
    for label, mode, page in [('summary', 'summary', 0)] + [('lists' + str(i), 'records', i) for i in range(4)]:
        name = 'observe-data-journal-' + label + '.command.txt'
        outputs[name] = command(body, mode, page)
        commands.append({'path': name, 'mode': mode, 'page': page, **pin(outputs[name])})
    record = {'schema': 1, 'status': 'ACTUAL_RESULT_BOUND_PROJECTIONS_PENDING_INDEPENDENT_REVIEW',
              'actual_observation': {'path': str(path), **pin(observation_body)},
              'actual_evidence_review': {'path': str(review_path), **pin(review_body)},
              'source': {'path': SOURCE, **HOST_PIN}, 'actual_result': result_pin,
              'template': pin(template), 'reader': pin(body), 'commands': commands,
              'only_executable_delta': 'SOURCE_PIN and RESULT_PIN; AST unparse changes formatting only',
              'native_tool_or_guest_started': False, 'inspection_success_claimed': False}
    outputs['projection-binding.json'] = (json.dumps(record, sort_keys=True, indent=2) + '\n').encode()
    save_fresh(ROOT / 'result-binding', outputs)
    return record


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'prepare':
        print(json.dumps(prepare(), indent=2))
    elif len(sys.argv) == 3 and sys.argv[1] == 'finalize':
        print(json.dumps(finalize(sys.argv[2]), indent=2))
    else:
        raise SystemExit('Usage: build_projection.py prepare | finalize ACTUAL_REVIEWED_OBSERVATION_JSON')
