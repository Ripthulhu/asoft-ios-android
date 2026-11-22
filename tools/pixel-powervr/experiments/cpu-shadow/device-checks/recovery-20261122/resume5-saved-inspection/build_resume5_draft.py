"""Create fresh, unreleased resume5 ownership drafts from exact reviewed evidence.

This builder only reads repository inputs and writes new local drafts. The new
inspector, released owner, preflight and observer bindings remain unset.
"""
from pathlib import Path
import ast
import hashlib
import json
import pprint
import re


OUT = Path(__file__).resolve().parent
REC = OUT.parent
PREVIOUS = REC / 'resume4-saved-inspection'
JIB = PREVIOUS / 'jib-diagnostic'
OWNER_PIN = {'bytes': 48469, 'sha256': 'c5cc01768be23c0a7e3ad1364cb89a3dd8562288ac3c51f5eaef35ce7c039f10'}
JIB_SOURCE_PIN = {'bytes': 41544, 'sha256': 'cf31bf3489bed645dbd59f8e024f6759150f9262f1480e6d9d4ff53f855b9480'}
JIB_OBSERVATION_PIN = {'bytes': 2243, 'sha256': 'f71b2365dec203d3803e72b20149fd6df5faec7aa3581589f42d43dde286c4e5'}
JIB_REVIEW_PIN = {'bytes': 4848, 'sha256': '86baf8276725514242b2a1ad06be4923a313fb41d479b750a94ff871560a7c14'}


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def read_bound(path, expected):
    body = path.read_bytes()
    assert pin(body) == expected, 'changed reviewed repository input: ' + str(path)
    return body


def write(name, body):
    body = body.encode() if isinstance(body, str) else body
    if name.endswith('.py'):
        ast.parse(body)
    path = OUT / name
    if path.exists():
        assert path.read_bytes() == body, 'preserve different existing draft: ' + name
    else:
        with path.open('xb') as stream:
            stream.write(body)
    return body


def assignment(source, name):
    rows = [node.value for node in ast.parse(source).body if isinstance(node, ast.Assign) and
            any(isinstance(target, ast.Name) and target.id == name for target in node.targets)]
    assert len(rows) == 1
    return ast.literal_eval(rows[0])


def replace_once(source, before, after):
    assert source.count(before) == 1, 'expected one source substitution: ' + before[:80]
    return source.replace(before, after)


def set_constant(source, name, value):
    pattern = re.compile(r'^' + re.escape(name) + r' = [^\n]*', re.M)
    source, count = pattern.subn(lambda _: name + ' = ' + repr(value), source)
    assert count == 1, name
    return source


def observed_pin(row):
    values = row['digest_bytes']
    assert type(values) is list and len(values) == 32
    assert all(type(value) is int and 0 <= value <= 255 for value in values)
    assert type(row['bytes']) is int and 0 < row['bytes'] <= 4 << 20
    assert bytes(values).hex() == row['sha256']
    return {key: row[key] for key in ('bytes', 'sha256')}


def main():
    old_body = read_bound(PREVIOUS / 'run_saved_inspection_owner.py', OWNER_PIN)
    jib_source = read_bound(JIB / 'inspect_root_jib.py', JIB_SOURCE_PIN)
    observation_body = read_bound(JIB / 'physical-observations/result-pin-selected.json', JIB_OBSERVATION_PIN)
    review_body = read_bound(JIB / 'independent-result-pin-review.json', JIB_REVIEW_PIN)
    observed = json.loads(observation_body)
    assert observed['independently_reviewed'] is True and observed['independent_review'] == '../independent-result-pin-review.json'
    assert json.loads(review_body)['decision'] == 'ACTUAL_RESULT_PIN_EVIDENCE_PASSED'
    assert observed['status'] == 'ROOT_JIB_RESULT_BINDING_READY'
    assert observed['diagnostic_status'] == 'READONLY_ROOT_JIB_COMPARISON_OBSERVED'
    actual_jib_pin = observed_pin(observed['result'])
    assert actual_jib_pin == {'bytes': 14246, 'sha256': '5d39c9a0fb16c794577abaf4ab7155ee5f352d46cb7027e03b571055f10d5061'}
    nine_path = PREVIOUS / 'physical-observations/receipt-pins-selected.json'
    nine_body = nine_path.read_bytes()
    nine = json.loads(nine_body)
    assert nine['independently_reviewed'] is True and nine['independent_pixel_review_pending'] is False
    assert nine['status'] == 'RESUME4_RECEIPT_PINS_OBSERVED' and nine['files'] == len(nine['rows']) == 9
    assert nine['recorded_identities_absent'] is True and nine['receipt_metadata_stable'] is True
    preserved = {row['path']: observed_pin(row) for row in nine['rows']}
    assert len(preserved) == 9 and preserved == assignment(jib_source, 'RECEIPT_PINS')
    base = '/data/local/tmp/pixel-gpu-transfer-sxtv33sh'
    assert observed['source'] == {'path': base + '/run-ios26-root-jib-diagnostic-resume4.py', **JIB_SOURCE_PIN}
    preserved[observed['source']['path']] = JIB_SOURCE_PIN
    preserved[observed['result']['path']] = actual_jib_pin
    constants = "\nRESUME4_OWNER = BASE / 'ios26-saved-inspection-resume4-owner'\n" + \
        "RESUME4_WORK = Path('/data/local/tmp/pixel-saved-audit-e9cc754-resume4')\n" + \
        "RESUME4_MONITOR = BASE / 'ios26-saved-inspection-resume4-observer-procstat1'\n" + \
        "JIB_SOURCE = BASE / 'run-ios26-root-jib-diagnostic-resume4.py'\n" + \
        "JIB_WORK = BASE / 'ios26-root-jib-diagnostic-resume4'\n" + \
        'RESUME4_PRESERVATION_PINS = ' + pprint.pformat(preserved, width=110, sort_dicts=True) + '\n\n'
    source = old_body.decode()
    for before, after in (
        ('fresh resume4 saved-firstboot inspection', 'fresh resume5 saved-firstboot inspection'),
        ("OWNER = BASE / 'ios26-saved-inspection-resume4-owner'", "OWNER = BASE / 'ios26-saved-inspection-resume5-owner'"),
        ("WORK = Path('/data/local/tmp/pixel-saved-audit-e9cc754-resume4')", "WORK = Path('/data/local/tmp/pixel-saved-audit-e9cc754-resume5')"),
        ("INSPECTOR = Path('/data/local/tmp/pixel-saved-checks-resume3')", "INSPECTOR = Path('/data/local/tmp/pixel-saved-checks-resume5')"),
        ('remain unchanged; the reviewed inspector classifies the preexisting alternate flag.',
         'remain unchanged. Revised inspector source pins are deliberately unbound in this draft.')):
        source = replace_once(source, before, after)
    source = set_constant(source, 'INSPECTOR_SOURCE_PINS', None)
    source = replace_once(source, "PYTHON = '/data/data/com.termux/files/usr/bin/python'",
                          constants + "PYTHON = '/data/data/com.termux/files/usr/bin/python'")
    fragment = (OUT / 'resume4_preservation_fragment.py').read_bytes()
    source = replace_once(source, 'def prerequisites():', fragment.decode() + '\ndef prerequisites():')
    anchor = "    for name, pin in resume2_failure_inputs().items():\n        require(name not in inputs or inputs[name] == pin, 'preserved predecessor bindings disagree')\n        inputs[name] = pin\n"
    source = replace_once(source, anchor, anchor + "    for name, pin in resume4_failure_inputs().items():\n        require(name not in inputs or inputs[name] == pin, 'preserved resume4/JIB bindings disagree')\n        inputs[name] = pin\n")
    old_functions = {node.name: ast.dump(node) for node in ast.parse(old_body).body if isinstance(node, ast.FunctionDef)}
    new_functions = {node.name: ast.dump(node) for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)}
    assert all(new_functions[name] == body for name, body in old_functions.items() if name != 'prerequisites')
    for name in ('PREVIOUS_FAILURE_PINS', 'RESUME2_PRESERVATION_PINS', 'FIRSTBOOT_SUCCESS_PINS'):
        assert assignment(source, name) == assignment(old_body, name)
    owner = write('run_saved_inspection_owner_UNRELEASED.py', source)

    preflight = (PREVIOUS / 'launch_saved_inspection_preflight.py').read_text().replace('resume4', 'resume5')
    preflight = set_constant(preflight, 'SOURCE_BYTES', None)
    preflight = set_constant(preflight, 'SOURCE_SHA256', None)
    release_guard = "    if not (type(SOURCE_BYTES) is int and 0 < SOURCE_BYTES <= 256 << 10 and\n            type(SOURCE_SHA256) is str and len(SOURCE_SHA256) == 64 and\n            all(value in '0123456789abcdef' for value in SOURCE_SHA256)):\n        raise ValueError('UNRELEASED: exact reviewed resume5 owner source required')\n"
    preflight = replace_once(preflight, 'def launch():\n', 'def launch():\n' + release_guard)
    preflight_body = write('launch_saved_inspection_preflight_UNRELEASED.py', preflight)
    execution = (PREVIOUS / 'launch_saved_inspection_execution_UNRELEASED.py').read_text().replace('resume4', 'resume5')
    for name in ('SOURCE_BYTES', 'SOURCE_SHA256', 'TRANSFER_MANIFEST_SHA256', 'INSTALLED_FILES',
                 'PREFLIGHT_SHA256', 'PREFLIGHT_BYTES', 'MONITOR_PIN'):
        execution = set_constant(execution, name, None)
    release = "    require(type(SOURCE_BYTES) is int and 0 < SOURCE_BYTES <= 256 << 10 and\n            type(SOURCE_SHA256) is str and re.fullmatch('[0-9a-f]{64}', SOURCE_SHA256) is not None and\n            type(TRANSFER_MANIFEST_SHA256) is str and re.fullmatch('[0-9a-f]{64}', TRANSFER_MANIFEST_SHA256) is not None and\n            type(INSTALLED_FILES) is list and len(INSTALLED_FILES) == 2,\n            'UNRELEASED: exact reviewed owner and source installation bindings required')\n"
    execution = replace_once(execution, 'def require_release():\n', 'def require_release():\n' + release)
    execution_body = write('launch_saved_inspection_execution_UNRELEASED.py', execution)
    record = {'schema': 1, 'state': 'UNRELEASED_RESUME5_DRAFT_AWAITING_REVISED_INSPECTOR_SOURCES',
        'previous_owner': {'path': '../resume4-saved-inspection/run_saved_inspection_owner.py', **OWNER_PIN},
        'actual_jib_observation': {'path': '../resume4-saved-inspection/jib-diagnostic/physical-observations/result-pin-selected.json', **JIB_OBSERVATION_PIN},
        'actual_jib_evidence_review': {'path': '../resume4-saved-inspection/jib-diagnostic/independent-result-pin-review.json', **JIB_REVIEW_PIN},
        'actual_jib_result': {'path': observed['result']['path'], **actual_jib_pin},
        'nine_receipt_observation': {'path': '../resume4-saved-inspection/physical-observations/receipt-pins-selected.json', **pin(nine_body)},
        'all_nine_receipts_derived_from_288_decimal_bytes': True,
        'preserved_older_pin_sets_unchanged': True, 'unchanged_owner_functions_except_prerequisites': True,
        'preservation_fragment': {'path': 'resume4_preservation_fragment.py', **pin(fragment)},
        'draft_owner': {'path': 'run_saved_inspection_owner_UNRELEASED.py', **pin(owner)},
        'draft_preflight_launcher': {'path': 'launch_saved_inspection_preflight_UNRELEASED.py', **pin(preflight_body)},
        'draft_execution_launcher': {'path': 'launch_saved_inspection_execution_UNRELEASED.py', **pin(execution_body)},
        'new_inspector_directory': '/data/local/tmp/pixel-saved-checks-resume5',
        'new_owner_directory': base + '/ios26-saved-inspection-resume5-owner',
        'new_work': '/data/local/tmp/pixel-saved-audit-e9cc754-resume5',
        'inspector_source_pins': None, 'released_owner_pin': None, 'fresh_preflight_pin': None,
        'observer_source_pin': None, 'actual_observer_ready_pin': None,
        'source_installation_generated': False, 'preflight_released': False, 'execution_released': False,
        'phone_or_browser_actions': False, 'diagnostic_or_inspection_executed': False}
    write('owner-draft-preparation.json', json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
