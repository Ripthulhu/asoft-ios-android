"""Bind only the independently reviewed resume5 inspector source pair."""
from pathlib import Path
import ast
import hashlib
import json
import re


ROOT = Path(__file__).resolve().parent
REVISION = ROOT.parent / 'resume5-inspector-revision'
INSPECTOR_PINS = {
    'inspect_ios26_firstboot.py': {'bytes': 37444, 'sha256': '30eaaffc42aa73bf95488f3ca504d7c56344fbada0aaed746904ed1f4f78fd3e'},
    'inspect_ios26_firstboot_guest.py': {'bytes': 20929, 'sha256': '96c559bac19a3c36a4e26c2cf57b75cbafdfd5879de6e4fceb582b2c07a9b51a'},
}
REVIEW_PIN = {'bytes': 3729, 'sha256': 'ae4d3f14781bb20ca9eb69f320d6560bb42989ab1fb15012ec30e15ce8ef6493'}


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def read_bound(path, expected):
    body = path.read_bytes()
    assert pin(body) == expected, 'source/review differs: ' + str(path)
    return body


def write(name, body):
    body = body.encode() if isinstance(body, str) else body
    if name.endswith('.py'):
        ast.parse(body)
    target = ROOT / name
    if target.exists():
        assert target.read_bytes() == body, 'preserve different existing ' + name
    else:
        with target.open('xb') as stream:
            stream.write(body)
    return body


def bind(source, name, value):
    source, count = re.subn(r'^' + re.escape(name) + r' = None[^\n]*',
                            lambda _: name + ' = ' + repr(value), source, flags=re.M)
    assert count == 1
    return source


def same_except(before, after, names, module_doc=False):
    trees = [ast.parse(before), ast.parse(after)]
    for tree in trees:
        tree.body = [node for node in tree.body if not (isinstance(node, ast.Assign) and
                     any(isinstance(target, ast.Name) and target.id in names for target in node.targets))]
        if module_doc:
            assert isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant)
            tree.body = tree.body[1:]
    assert ast.dump(trees[0]) == ast.dump(trees[1])


def main():
    review = read_bound(REVISION / 'independent-inspector-review.json', REVIEW_PIN)
    for name, expected in INSPECTOR_PINS.items():
        read_bound(REVISION / 'sources' / name, expected)
    draft = read_bound(ROOT / 'run_saved_inspection_owner_UNRELEASED.py', {
        'bytes': 60304, 'sha256': '1a150bd473b1a5c28425b80a6fdaa0fb2c0ffe4d1b3d6e756bb45e8fcf0f5cae'})
    owner_source = bind(draft.decode(), 'INSPECTOR_SOURCE_PINS', INSPECTOR_PINS)
    old_doc = 'Revised inspector source pins are deliberately unbound in this draft.'
    assert owner_source.count(old_doc) == 1
    owner_source = owner_source.replace(old_doc, 'Revised inspector source pins bind the independently reviewed resume5 pair.')
    same_except(draft, owner_source, {'INSPECTOR_SOURCE_PINS'}, module_doc=True)
    owner = write('run_saved_inspection_owner.py', owner_source)
    owner_pin = pin(owner)
    preflight_draft = read_bound(ROOT / 'launch_saved_inspection_preflight_UNRELEASED.py', {
        'bytes': 6170, 'sha256': 'a779bf719a49597b9400107e29e4f5ed30b25f2790214ed8b9288fd904dda578'})
    launcher = bind(preflight_draft.decode(), 'SOURCE_BYTES', owner_pin['bytes'])
    launcher = bind(launcher, 'SOURCE_SHA256', owner_pin['sha256'])
    same_except(preflight_draft, launcher, {'SOURCE_BYTES', 'SOURCE_SHA256'})
    launcher_body = write('launch_saved_inspection_preflight.py', launcher)
    old_observer = (ROOT.parent / 'resume4-saved-inspection/observe_preflight.py').read_bytes()
    observer = old_observer.decode().replace('resume4', 'resume5')
    observer, count = re.subn(r'^SOURCE_BYTES = [^\n]*', 'SOURCE_BYTES = ' + repr(owner_pin['bytes']), observer, flags=re.M)
    assert count == 1
    observer, count = re.subn(r'^SOURCE_SHA256 = [^\n]*', 'SOURCE_SHA256 = ' + repr(owner_pin['sha256']), observer, flags=re.M)
    assert count == 1
    observer_body = write('observe_preflight.py', observer)
    record = {'schema': 1, 'state': 'REVISED_SOURCE_BOUND_OWNER_PENDING_INDEPENDENT_PACKAGE_REVIEW',
        'inspector_directory': '/data/local/tmp/pixel-saved-checks-resume5',
        'inspector_sources': INSPECTOR_PINS,
        'independent_inspector_review': {'path': '../resume5-inspector-revision/independent-inspector-review.json', **pin(review)},
        'preserved_owner_draft': pin(draft),
        'owner': {'path': 'run_saved_inspection_owner.py', 'phone_path': '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-saved-inspection-resume5.py', **owner_pin},
        'preflight_launcher': {'path': 'launch_saved_inspection_preflight.py', **pin(launcher_body)},
        'preflight_observer': {'path': 'observe_preflight.py', **pin(observer_body)},
        'previous_preflight_observer': {'path': '../resume4-saved-inspection/observe_preflight.py', **pin(old_observer)},
        'owner_executable_delta': 'INSPECTOR_SOURCE_PINS only; module description now records the completed binding',
        'preflight_launcher_delta': 'SOURCE_BYTES and SOURCE_SHA256 only',
        'fresh_preflight_pin': None, 'fresh_observer_source_pin': None, 'fresh_observer_ready_pin': None,
        'inspection_execution_released': False, 'phone_or_browser_actions': False}
    write('source-binding.json', json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
