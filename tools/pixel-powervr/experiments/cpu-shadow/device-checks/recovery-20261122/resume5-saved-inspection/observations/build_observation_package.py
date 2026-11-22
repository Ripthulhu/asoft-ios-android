#!/usr/bin/env python3
"""Build additive read-only queries; never run a phone reader or fill result pins."""
import ast
import base64
import gzip
import hashlib
import json
from pathlib import Path
import shlex

HERE = Path(__file__).resolve().parent
R5 = HERE.parent
RECOVERY = R5.parent
PYTHON = '/data/data/com.termux/files/usr/bin/python'


def sha(body):
    return hashlib.sha256(body).hexdigest()


def preserve(path, body):
    if path.exists():
        if path.read_bytes() != body:
            raise ValueError('preserve different existing file: ' + str(path))
    else:
        with path.open('xb') as stream:
            stream.write(body)


def record(path):
    body = path.read_bytes()
    return {'path': path.relative_to(HERE).as_posix(), 'bytes': len(body), 'sha256': sha(body)}


def command(source, arguments):
    body = source.read_bytes()
    payload = base64.b64encode(gzip.compress(body, mtime=0)).decode()
    loader = ('import base64,gzip,hashlib; b=gzip.decompress(base64.b64decode(' + repr(payload) + ')); '
              'assert len(b)==' + str(len(body)) + ' and hashlib.sha256(b).hexdigest()==' + repr(sha(body)) + '; '
              "exec(compile(b,'<reviewed-resume5-metadata-query>','exec'),{'__name__':'__main__'})")
    result = (shlex.join([PYTHON, '-I', '-B', '-c', loader, *arguments]) + '\n').encode()
    if len(result) > 6000:
        raise ValueError('query command exceeds 6000-byte transport bound: ' + source.name)
    return result


def actual_preflight():
    path = R5 / 'physical-observations/preflight-selected.json'
    value = json.loads(path.read_bytes())
    review = json.loads((R5 / 'independent-preflight-evidence-review.json').read_bytes())
    pin = value['preflight']
    if (value.get('independently_reviewed') is not True or value.get('independent_review_pending') is not False or
            review.get('status') != 'PASSED' or review['selected_reviewed']['sha256'] != sha(path.read_bytes()) or
            pin.get('path') != '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume5-owner/preflight.json' or
            len(pin['digest_bytes']) != 32 or any(type(x) is not int or not 0 <= x <= 255 for x in pin['digest_bytes']) or
            bytes(pin['digest_bytes']).hex() != pin['sha256'] or
            not all(value.get(k) is True for k in ('accepted', 'runner_reaped', 'wrapper_absent', 'runner_absent', 'inputs_unchanged', 'work_absent')) or
            value.get('exit_code') != 0 or value.get('owner_exit_code') != 0 or value.get('forced_runner') is not False or
            value.get('execution_started') is not False):
        raise ValueError('actual reviewed clean preflight required')
    return {k: pin[k] for k in ('bytes', 'sha256')}, path


def build_status():
    predecessor = RECOVERY / 'resume4-saved-inspection/observe_inspection_paged.py'
    text = predecessor.read_text().replace('resume4', 'resume5')
    owner_body = (R5 / 'run_saved_inspection_owner.py').read_bytes()
    if len(owner_body) != 60564 or sha(owner_body) != 'dbb570dc9b3354a5d7c4eb218883ab22f25afe24757c429e46cc7c04de1baa63':
        raise ValueError('released owner source differs')
    text = text.replace('SOURCE_BYTES = 48469', 'SOURCE_BYTES = 60564')
    text = text.replace('c5cc01768be23c0a7e3ad1364cb89a3dd8562288ac3c51f5eaef35ce7c039f10', sha(owner_body))
    pin, observation = actual_preflight()
    start = text.index('PREFLIGHT_PIN = ')
    end = text.index('\n', start)
    text = text[:start] + 'PREFLIGHT_PIN = ' + repr(pin) + '  # Actual independently reviewed fresh preflight.' + text[end:]
    before = "    recent = m['resume2_failure_inputs']()\n"
    after = before + "    latest = m['resume4_failure_inputs']()\n    require(all(current['inputs'].get(path) == expected for path, expected in latest.items()),\n            'resume4/JIB preservation was not bound by fresh preflight')\n"
    assert text.count(before) == 1
    text = text.replace(before, after)
    before = "            'resume2_diagnostic_pins_unchanged': len(m['RESUME2_PRESERVATION_PINS']),\n"
    assert text.count(before) == 1
    text = text.replace(before, before + "            'resume4_jib_pins_unchanged': len(m['RESUME4_PRESERVATION_PINS']),\n")
    before = "        print(json.dumps({'index': index, **row}, separators=(',', ':')), flush=True)"
    assert text.count(before) == 1
    text = text.replace(before, "        print(json.dumps({'index': index, 'path': row['path'], 'bytes': row['bytes']}, separators=(',', ':')))\n        print(row['sha256'])\n        print(json.dumps(row['digest_bytes'], separators=(',', ':')), flush=True)")
    path = HERE / 'observe_inspection.py'
    preserve(path, text.encode())
    return predecessor, observation


def proof_sources(shared, template):
    """Split only the displayed views; completed proof validation stays identical."""
    combined = shared + '\n' + template
    for journal_view in (True, False):
        tree = ast.parse(combined)
        excluded = {'optional', 'process'} | ({'codes'} if journal_view else {'volume', 'journal_projection'})
        tree.body = [n for n in tree.body if not (isinstance(n, ast.FunctionDef) and n.name in excluded) and
                     not (not journal_view and isinstance(n, ast.Assign) and
                          any(isinstance(t, ast.Name) and t.id == 'JOURNAL_FIELDS' for t in n.targets))]
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name == 'render':
                boundary = next(i for i, n in enumerate(node.body) if isinstance(n, ast.Assign) and
                                any(isinstance(t, ast.Name) and t.id == 'nonce_matches' for t in n.targets))
                if journal_view:
                    node.body = node.body[:boundary]
                else:
                    node.body = [n for i, n in enumerate(node.body) if not (i < boundary and isinstance(n, ast.If))]
            elif node.name == 'main':
                for call in (n for n in ast.walk(node) if isinstance(n, ast.Call)):
                    for key in call.keywords:
                        if key.arg == 'choices':
                            key.value = ast.Tuple(elts=[ast.Constant(v) for v in (('root', 'data') if journal_view else ('fsck',))], ctx=ast.Load())
        name = 'observe_journals.py' if journal_view else 'observe_fsck.py'
        preserve(HERE / name, (ast.unparse(ast.fix_missing_locations(tree)) + '\n').encode())


def main():
    predecessor, observation = build_status()
    template = HERE / 'proof_projection_template.py'
    if template.exists():
        shared = (HERE / 'observe_inspection.py').read_text().split('\ndef status(m):', 1)[0]
        proof_sources(shared, template.read_text())
    rows = []
    queries = [('observe-inspection.command.txt', 'observe_inspection.py', [])]
    queries += [('observe-success-pins-' + str(page) + '.command.txt', 'observe_inspection.py', ['--pins', '--page', str(page)]) for page in range(3)]
    if template.exists():
        queries += [('observe-proof-' + view + '.command.txt', 'observe_journals.py' if view in ('root', 'data') else 'observe_fsck.py', ['--view', view]) for view in ('root', 'data', 'fsck')]
    for name, source_name, arguments in queries:
        source, target = HERE / source_name, HERE / name
        ast.parse(source.read_bytes())
        preserve(target, command(source, arguments))
        rows.append({'source': record(source), 'command': record(target), 'arguments': arguments})
    report = {'schema': 1, 'kind': 'resume5_readonly_metadata_queries',
              'predecessor': str(predecessor.relative_to(RECOVERY)),
              'actual_preflight_observation': str(observation.relative_to(RECOVERY)),
              'queries': rows, 'phone_action_performed': False,
              'actual_inspection_result_pin': None, 'inspection_success_claimed': False}
    preserve(HERE / 'query-manifest.json', (json.dumps(report, indent=2) + '\n').encode())
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
