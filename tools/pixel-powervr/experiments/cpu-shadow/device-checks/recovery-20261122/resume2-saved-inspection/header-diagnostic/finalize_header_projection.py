"""Bind compact read-only pages to an actually observed diagnostic result."""
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
sha = lambda body: hashlib.sha256(body).hexdigest()


def write(name, body):
    body = body.encode() if isinstance(body, str) else body
    target = ROOT / name
    if target.exists():
        assert target.read_bytes() == body, 'preserve differing existing ' + name
    else:
        target.write_bytes(body)
    return body


assert len(sys.argv) == 2, 'actual reviewed result observation required'
path = Path(sys.argv[1]).resolve(strict=True)
observation = path.read_bytes()
v = json.loads(observation)
assert v.get('independently_reviewed') is True or v.get('independent_review_pending') is False
assert (path.parent / v['independent_review']).resolve(strict=True).is_file()
assert v['status'] == 'HFS_HEADER_RESULT_BINDING_READY' and v['readonly'] is True
assert v['diagnostic_status'] == 'READONLY_HFS_HEADERS_OBSERVED' and v['headers'] == 8
assert v['inspection_success_claimed'] is False and v['full_disk_hashes_recomputed'] is False
row = v['result']
assert row['path'] == '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-hfs-header-diagnostic-resume2/result.json'
assert type(row['bytes']) is int and 0 < row['bytes'] <= 65536
assert re.fullmatch('[a-f0-9]{64}', row['sha256'])
assert len(row['digest_bytes']) == 32 and all(type(n) is int and 0 <= n <= 255 for n in row['digest_bytes'])
assert bytes(row['digest_bytes']).hex() == row['sha256']
result_pin = {key: row[key] for key in ('bytes', 'sha256')}
source_pin = {'bytes': 22740, 'sha256': 'e79c0fbc472ae2a875164565802feffc4fad0a630571970f6e68d7251801bdcd'}
assert v['source'] == source_pin
installed = (ROOT / 'inspect_hfs_headers.py').read_bytes()
assert {'bytes': len(installed), 'sha256': sha(installed)} == source_pin
draft = (ROOT / 'observe_headers_UNRELEASED.py').read_bytes()
assert len(draft) == 6605 and sha(draft) == '75f6942c51e2bb5301f59331ab1b24de3e39e3d438a2aa66845a30c813d675d1'
source = draft.decode()
for name, pin in (('SOURCE_PIN', source_pin), ('RESULT_PIN', result_pin)):
    assert source.count(name + ' = None') == 1
    source = source.replace(name + ' = None', name + ' = ' + repr(pin))
old, new = ast.parse(draft), ast.parse(source)
for tree in (old, new):
    tree.body = [n for n in tree.body if not (isinstance(n, ast.Assign) and
        any(isinstance(t, ast.Name) and t.id in ('SOURCE_PIN', 'RESULT_PIN') for t in n.targets))]
assert ast.dump(old) == ast.dump(new)
body = write('observe_headers.py', source)
encoded = base64.b64encode(gzip.compress(body, mtime=0)).decode()
commands = []
for label, page in [('summary', None), *[('page' + str(n), n) for n in range(4)]]:
    loader = ('import base64,gzip,hashlib; b=gzip.decompress(base64.b64decode(' + repr(encoded) +
        ',validate=True)); assert len(b)==' + str(len(body)) + ' and hashlib.sha256(b).hexdigest()==' + repr(sha(body)) +
        '; exec(compile(b,"readonly-header-pages","exec"),{"__name__":"__main__","__page__":' + repr(page) + '})')
    command = '/data/data/com.termux/files/usr/bin/python -I -B -c ' + shlex.quote(loader) + '\n'
    assert len(command.encode()) <= 6000
    name = 'observe-headers-' + label + '.command.txt'
    write(name, command)
    commands.append({'path': name, 'page': page, 'bytes': len(command.encode()), 'sha256': sha(command.encode())})
record = {'schema': 1, 'status': 'FINALIZED_READONLY_HEADER_PAGES_PENDING_INDEPENDENT_REVIEW',
    'actual_observation': {'path': str(path), 'bytes': len(observation), 'sha256': sha(observation)},
    'diagnostic_source': source_pin, 'actual_result': result_pin,
    'observer': {'bytes': len(body), 'sha256': sha(body)}, 'commands': commands,
    'only_draft_delta': 'SOURCE_PIN and RESULT_PIN bound to reviewed actual source/result',
    'raw_header_bytes_exported': False, 'native_tool_or_guest_started': False}
write('header-projection-finalization.json', json.dumps(record, indent=2) + '\n')
print(json.dumps(record, indent=2))
