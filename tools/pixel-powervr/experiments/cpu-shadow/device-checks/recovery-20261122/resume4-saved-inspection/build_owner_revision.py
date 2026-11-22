"""Create a fresh owner with only the independently observed digest correction.

The installed resume3 source is preserved. Digests in the selected observation
are reconstructed from all 32 decimal bytes before any new binding is written.
"""
from pathlib import Path
import ast
import hashlib
import json

OUT = Path(__file__).resolve().parent
PREVIOUS = OUT.parent / 'resume3-saved-inspection'
SOURCE_PIN = {'bytes': 48469, 'sha256': '91ac3ba2ba8c3e40b2a99dfffdc4a53ae49b8e441245755f33ef761846d61e14'}
EVIDENCE_PIN = {'bytes': 4580, 'sha256': '83210b43b5df51e01d0de70648f4d42dd0dd771924c1d875df55031058f2cb1b'}
REVIEW_PIN = {'bytes': 5143, 'sha256': '3458bc9390c6a35bd0d9fb85b0bb6a428aaca62ac473319cf76ef4b56498862c'}
OLD_EXIT_SHA256 = '4af8f8a2feeb3e8103bfaf61c8393aa58f94c9ea61e32f06e51bbaee3cdbb920'


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def read_bound(path, expected):
    body = path.read_bytes()
    if pin(body) != expected:
        raise ValueError('local reviewed input differs: ' + str(path))
    return body


def digest_from_decimal(row):
    values = row.get('digest_bytes')
    if not (type(values) is list and len(values) == 32 and
            all(type(value) is int and 0 <= value <= 255 for value in values)):
        raise ValueError('all 32 decimal digest bytes are required')
    derived = bytes(values).hex()
    if row.get('sha256') != derived:
        raise ValueError('displayed digest differs from decimal bytes')
    if type(row.get('bytes')) is not int or row['bytes'] < 1:
        raise ValueError('positive observed file length required')
    return {'bytes': row['bytes'], 'sha256': derived}


def write_preserved(name, body):
    body = body.encode() if isinstance(body, str) else body
    path = OUT / name
    if path.exists():
        if path.read_bytes() != body:
            raise ValueError('preserve different existing artifact: ' + name)
    else:
        path.write_bytes(body)


def main():
    old = read_bound(PREVIOUS / 'run_saved_inspection_owner.py', SOURCE_PIN)
    evidence_path = PREVIOUS / 'physical-observations/prior-observer-pins-170717.json'
    selected = json.loads(read_bound(evidence_path, EVIDENCE_PIN))
    read_bound(PREVIOUS / 'independent-observer-exit-pin-correction-review.json', REVIEW_PIN)
    if not (selected.get('independently_reviewed') is True and
            selected.get('independent_review_pending') is False and
            selected.get('independent_review') == '../independent-observer-exit-pin-correction-review.json'):
        raise ValueError('actual independent evidence review required')
    observed = {name: digest_from_decimal(row) for name, row in selected['files'].items()}
    if set(observed) != {'exit.json', 'summary.json', 'events.jsonl', 'ready.json'}:
        raise ValueError('exact four observed prior receipts required')
    module = {'__name__': 'reviewed_previous_owner'}
    exec(compile(old, 'reviewed_previous_owner.py', 'exec'), module)
    previous_pins = module['RESUME2_PRESERVATION_PINS']
    for name, row in selected['files'].items():
        expected = previous_pins[row['path']]
        if name == 'exit.json':
            if expected != {'bytes': 478, 'sha256': OLD_EXIT_SHA256} or observed[name]['bytes'] != 478:
                raise ValueError('expected historical exit transcription mismatch required')
        elif observed[name] != expected:
            raise ValueError('unexpected additional prior receipt difference: ' + name)
    text = old.decode()
    substitutions = {
        'fresh resume3 saved-firstboot inspection': 'fresh resume4 saved-firstboot inspection',
        "OWNER = BASE / 'ios26-saved-inspection-resume3-owner'": "OWNER = BASE / 'ios26-saved-inspection-resume4-owner'",
        "WORK = Path('/data/local/tmp/pixel-saved-audit-e9cc754-resume3')": "WORK = Path('/data/local/tmp/pixel-saved-audit-e9cc754-resume4')",
        OLD_EXIT_SHA256: observed['exit.json']['sha256'],
    }
    for before, after in substitutions.items():
        if text.count(before) != 1:
            raise ValueError('expected sole substitution absent: ' + before)
        text = text.replace(before, after)
    source = text.encode()
    ast.parse(source)
    write_preserved('run_saved_inspection_owner.py', source)
    record = {
        'schema': 1, 'kind': 'fresh_resume4_owner_digest_correction',
        'previous_source': {'path': '../resume3-saved-inspection/run_saved_inspection_owner.py', **SOURCE_PIN},
        'actual_observation': {'path': '../resume3-saved-inspection/physical-observations/prior-observer-pins-170717.json', **EVIDENCE_PIN},
        'independent_evidence_review': {'path': '../resume3-saved-inspection/independent-observer-exit-pin-correction-review.json', **REVIEW_PIN},
        'observed_utc': selected['observed_utc'],
        'digest_derivation': 'All four hashes reconstructed from all 32 observed decimal bytes; displayed hex must match.',
        'corrected_receipt': {'path': selected['files']['exit.json']['path'], **observed['exit.json']},
        'old_selected_sha256': OLD_EXIT_SHA256,
        'other_three_receipts_unchanged': True,
        'source': {'local_path': 'run_saved_inspection_owner.py',
                   'phone_path': '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-saved-inspection-resume4.py', **pin(source)},
        'inspector_directory_reused': '/data/local/tmp/pixel-saved-checks-resume3',
        'source_delta': ['heading resume4', 'fresh OWNER path', 'fresh WORK path', 'one observed prior exit digest nibble'],
        'all_function_bodies_unchanged': True,
        'native_runtime_resource_cleanup_and_acceptance_unchanged': True,
        'previous_installed_sources_and_evidence_preserved': True,
        'fresh_preflight_pin': None, 'execution_released': False,
    }
    write_preserved('owner-preparation.json', json.dumps(record, indent=2) + '\n')
    print(json.dumps(record['source']))


if __name__ == '__main__':
    main()
