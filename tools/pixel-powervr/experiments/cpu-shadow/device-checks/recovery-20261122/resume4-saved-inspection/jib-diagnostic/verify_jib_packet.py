"""Read-only reconstruction of the generated JIB source/launch packet."""
from pathlib import Path
import ast
import base64
import gzip
import hashlib
import json
import shlex


ROOT = Path(__file__).resolve().parent
PYTHON = '/data/data/com.termux/files/usr/bin/python'


def sha(body):
    return hashlib.sha256(body).hexdigest()


def pin(body):
    return {'bytes': len(body), 'sha256': sha(body)}


def assignment(tree, name):
    matches = [node.value for node in tree.body if isinstance(node, ast.Assign) and
               any(isinstance(target, ast.Name) and target.id == name for target in node.targets)]
    assert len(matches) == 1, ('expected one top-level assignment', name)
    return matches[0]


def decode_command(path, expected):
    command = path.read_bytes()
    assert len(command) <= 6000 and command.endswith(b'\n')
    argv = shlex.split(command.decode())
    assert len(argv) == 5 and argv[:4] == [PYTHON, '-I', '-B', '-c']
    tree = ast.parse(argv[4])
    value = assignment(tree, 'b')
    assert isinstance(value, ast.Call) and ast.unparse(value.func) == 'gzip.decompress' and len(value.args) == 1
    decode = value.args[0]
    assert isinstance(decode, ast.Call) and ast.unparse(decode.func) == 'base64.b64decode'
    assert [(item.arg, ast.literal_eval(item.value)) for item in decode.keywords] == [('validate', True)]
    body = gzip.decompress(base64.b64decode(ast.literal_eval(decode.args[0]), validate=True))
    assert body == expected, ('command reconstruction differs', str(path))
    checks = [node for node in tree.body if isinstance(node, ast.Assert)]
    assert len(checks) == 1
    wanted = ast.parse('assert len(b)==' + str(len(body)) +
                       ' and hashlib.sha256(b).hexdigest()==' + repr(sha(body))).body[0]
    assert ast.dump(checks[0]) == ast.dump(wanted), 'command integrity assertion differs'
    ast.parse(body)
    return {'path': path.name, **pin(command), 'decoded_source': pin(body)}


def main():
    build = json.loads((ROOT / 'transport-build.json').read_bytes())
    source = (ROOT / 'inspect_root_jib.py').read_bytes()
    assert {key: build['source'][key] for key in ('bytes', 'sha256')} == pin(source)
    assert build['actual_result_binding'] is None and build['scalar_projection_released'] is False
    manifest_body = (ROOT / 'transfer-manifest.json').read_bytes()
    assert build['manifest'] == pin(manifest_body)
    manifest = json.loads(manifest_body)
    assert manifest['files'] == [{'path': 'run-ios26-root-jib-diagnostic-resume4.py', **pin(source)}]
    steps = json.loads((ROOT / 'transport-steps.json').read_bytes())
    assert len(steps) == len(manifest['chunks']) + 2 == build['steps']
    command_rows, parts = [], []
    for index, row in enumerate(steps):
        body = (ROOT / 'source-transfer' / (row['name'] + '.py')).read_bytes()
        command_path = ROOT / 'source-transfer' / (row['name'] + '.command.txt')
        checked = decode_command(command_path, body)
        assert row['source_bytes'] == len(body) and row['source_sha256'] == sha(body)
        assert row['command_bytes'] == checked['bytes'] and row['command_sha256'] == checked['sha256']
        command_rows.append(checked)
        if 0 < index < len(steps) - 1:
            chunk = ast.literal_eval(assignment(ast.parse(body), 'body'))
            expected = manifest['chunks'][index - 1]
            assert type(chunk) is bytes and pin(chunk) == {key: expected[key] for key in ('bytes', 'sha256')}
            parts.append(chunk)
    begin = ast.parse((ROOT / 'source-transfer' / (steps[0]['name'] + '.py')).read_bytes())
    manifest_call = assignment(begin, 'manifest')
    assert base64.b64decode(ast.literal_eval(manifest_call.args[0]), validate=True) == manifest_body
    encoded = b''.join(parts)
    assert len(encoded) == manifest['encoded_bytes'] and sha(encoded) == manifest['encoded_sha256']
    bundle_body = gzip.decompress(base64.b64decode(encoded, validate=True))
    assert len(bundle_body) == manifest['bundle_bytes'] and sha(bundle_body) == manifest['bundle_sha256']
    bundle = json.loads(bundle_body)
    assert bundle['schema'] == 1 and bundle['kind'] == 'root_jib_diagnostic_resume4_sources'
    assert len(bundle['files']) == 1
    assert [{key: row[key] for key in ('path', 'bytes', 'sha256')} for row in bundle['files']] == manifest['files']
    assert bundle['files'][0]['body'].encode() == source
    launcher = (ROOT / 'launch_jib_diagnostic.py').read_bytes()
    assert pin(launcher) == build['launcher']
    launch = decode_command(ROOT / 'run-jib-diagnostic.command.txt', launcher)
    assert {key: launch[key] for key in ('bytes', 'sha256')} == build['launch_command']
    reader = (ROOT / 'observe_jib_result_pin.py').read_bytes()
    assert pin(reader) == build['future_result_binding_reader']
    binding_command = decode_command(ROOT / 'observe-jib-result-pin.command.txt', reader)
    assert {key: binding_command[key] for key in ('bytes', 'sha256')} == build['future_result_binding_command']
    draft = (ROOT / 'observe_jib_result_pin_UNRELEASED.py').read_bytes()
    old, new = ast.parse(draft), ast.parse(reader)
    assert ast.literal_eval(assignment(old, 'SOURCE_PIN')) is None
    assert ast.literal_eval(assignment(new, 'SOURCE_PIN')) == pin(source)
    for tree in (old, new):
        tree.body = [node for node in tree.body if not (isinstance(node, ast.Assign) and
                     any(isinstance(target, ast.Name) and target.id == 'SOURCE_PIN' for target in node.targets))]
    assert ast.dump(old) == ast.dump(new)
    projection = (ROOT / 'observe_jibs_UNRELEASED.py').read_bytes()
    tree = ast.parse(projection)
    assert ast.literal_eval(assignment(tree, 'SOURCE_PIN')) is None
    assert ast.literal_eval(assignment(tree, 'RESULT_PIN')) is None
    assert not list(ROOT.glob('observe-jibs-*.command.txt')), 'no actual result exists for detailed projection release'
    report = {'schema': 1, 'status': 'EXACT_PACKET_RECONSTRUCTION_PASSED',
              'source': pin(source), 'manifest': pin(manifest_body), 'bundle': pin(bundle_body),
              'source_transfer_commands': command_rows, 'separate_launch_command': launch,
              'future_result_binding_command': binding_command,
              'future_detailed_projection_template': pin(projection),
              'detailed_projection_source_pin': None, 'actual_result_binding': None,
              'all_command_bytes_at_most_6000': True,
              'maximum_command_bytes': max([row['bytes'] for row in command_rows] + [launch['bytes'], binding_command['bytes']]),
              'device_files_accessed': False, 'diagnostic_executed': False}
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
