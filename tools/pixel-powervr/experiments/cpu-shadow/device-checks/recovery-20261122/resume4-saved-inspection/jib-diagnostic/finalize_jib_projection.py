"""Bind the future scalar reader to independently reviewed physical result evidence.

No result is available at preparation time.  This local-only finalizer must not
be run against a guessed, synthetic or failed physical result.  It writes a new
result-binding directory and never changes the unbound reader or phone sources.
"""
from pathlib import Path
import ast
import base64
import gzip
import hashlib
import json
import re
import shlex
import sys


ROOT = Path(__file__).resolve().parent
BASE = '/data/local/tmp/pixel-gpu-transfer-sxtv33sh'
PYTHON = '/data/data/com.termux/files/usr/bin/python'


def sha(body):
    return hashlib.sha256(body).hexdigest()


def pin(body):
    return {'bytes': len(body), 'sha256': sha(body)}


def finalize(observation_path):
    path = Path(observation_path).resolve(strict=True)
    observation_body = path.read_bytes()
    observed = json.loads(observation_body)
    assert observed.get('kind') == 'selected_physical_root_jib_diagnostic_observation'
    assert observed.get('independently_reviewed') is True
    review_path = (path.parent / observed['independent_review']).resolve(strict=True)
    review_body = review_path.read_bytes()
    assert review_body and type(json.loads(review_body)) is dict
    assert observed.get('status') == 'ROOT_JIB_RESULT_BINDING_READY'
    assert observed.get('diagnostic_status') == 'READONLY_ROOT_JIB_COMPARISON_OBSERVED'
    assert observed.get('readonly') is True
    assert observed.get('jibs') == 2 and observed.get('tool_commands') == 16
    assert observed.get('all_own_tool_children_reaped') is True and observed.get('forced_tool_children') == []
    assert all(observed.get(key) is True for key in
               ('disk_identities_unchanged', 'bound_metadata_unchanged', 'bound_tooling_unchanged',
                'recorded_inspection_processes_absent'))
    assert all(observed.get(key) is False for key in
               ('inspection_success_claimed', 'full_disk_hashes_recomputed', 'journal_pointer_followed',
                'difference_classified_as_safe', 'raw_bytes_exported', 'raw_jib_bytes_exported'))
    assert observed.get('error') is None and observed.get('preservation_error') is None
    row = observed['result']
    assert row['path'] == BASE + '/ios26-root-jib-diagnostic-resume4/result.json'
    assert type(row['bytes']) is int and 0 < row['bytes'] <= 65536
    assert type(row['sha256']) is str and re.fullmatch('[a-f0-9]{64}', row['sha256'])
    assert type(row['digest_bytes']) is list and len(row['digest_bytes']) == 32
    assert all(type(value) is int and 0 <= value <= 255 for value in row['digest_bytes'])
    assert bytes(row['digest_bytes']).hex() == row['sha256'], 'observed hexadecimal and decimal digest differ'
    result_pin = {key: row[key] for key in ('bytes', 'sha256')}
    build_body = (ROOT / 'transport-build.json').read_bytes()
    build = json.loads(build_body)
    source = (ROOT / 'inspect_root_jib.py').read_bytes()
    source_pin = pin(source)
    assert build['source'] == {'path': BASE + '/run-ios26-root-jib-diagnostic-resume4.py', **source_pin}
    assert observed.get('source') == build['source'], 'actual diagnostic source differs from the prepared source'
    draft = (ROOT / 'observe_jibs_UNRELEASED.py').read_bytes()
    finalized = draft.decode()
    for name, value in (('SOURCE_PIN', source_pin), ('RESULT_PIN', result_pin)):
        assert finalized.count(name + ' = None') == 1
        finalized = finalized.replace(name + ' = None', name + ' = ' + repr(value))
    before, after = ast.parse(draft), ast.parse(finalized)
    for tree in (before, after):
        tree.body = [node for node in tree.body if not (isinstance(node, ast.Assign) and
                     any(isinstance(target, ast.Name) and target.id in ('SOURCE_PIN', 'RESULT_PIN')
                         for target in node.targets))]
    assert ast.dump(before) == ast.dump(after), 'reader delta exceeded two actual pins'
    body = finalized.encode()
    encoded = base64.b64encode(gzip.compress(body, mtime=0)).decode()
    outputs = {'observe_jibs.py': body}
    commands = []
    for label, page in [('summary', None), *[('ranges' + str(index), index) for index in range(4)]]:
        loader = ('import base64,gzip,hashlib; b=gzip.decompress(base64.b64decode(' + repr(encoded) +
                  ',validate=True)); assert len(b)==' + str(len(body)) +
                  ' and hashlib.sha256(b).hexdigest()==' + repr(sha(body)) +
                  '; exec(compile(b,"readonly-root-jib-projection","exec"),{"__name__":"__main__","__page__":' +
                  repr(page) + '})')
        command = (PYTHON + ' -I -B -c ' + shlex.quote(loader) + '\n').encode()
        assert len(command) <= 6000, 'bounded terminal command exceeded 6000 bytes'
        name = 'observe-jibs-' + label + '.command.txt'
        outputs[name] = command
        commands.append({'path': name, 'page': page, **pin(command)})
    record = {'schema': 1, 'status': 'ACTUAL_RESULT_BOUND_PROJECTION_PENDING_INDEPENDENT_REVIEW',
              'actual_observation': {'path': str(path), **pin(observation_body)},
              'actual_evidence_review': {'path': str(review_path), **pin(review_body)},
              'prepared_transport_record': pin(build_body), 'diagnostic_source': source_pin,
              'actual_result': result_pin, 'unbound_template': pin(draft), 'finalized_reader': pin(body),
              'commands': commands, 'only_executable_delta': 'SOURCE_PIN and RESULT_PIN',
              'raw_jib_bytes_exported': False, 'device_signatures_exported': False, 'uuid_values_exported': False,
              'native_tool_or_guest_started': False, 'inspection_success_claimed': False}
    outputs['projection-binding.json'] = (json.dumps(record, indent=2) + '\n').encode()
    target = ROOT / 'result-binding'
    target.mkdir(mode=0o700)
    for name, value in outputs.items():
        with (target / name).open('xb') as stream:
            stream.write(value)
    return record


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: finalize_jib_projection.py ACTUAL_REVIEWED_RESULT_OBSERVATION_JSON')
    print(json.dumps(finalize(sys.argv[1]), indent=2))
