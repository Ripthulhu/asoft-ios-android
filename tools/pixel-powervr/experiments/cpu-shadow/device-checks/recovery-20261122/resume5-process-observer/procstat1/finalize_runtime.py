#!/usr/bin/env python3
"""Build additive local wrappers from an actual new preflight observation."""
import ast
import importlib.util
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
OUT = HERE / 'runtime-binding'
spec = importlib.util.spec_from_file_location('source_only_builder', HERE / 'build_transport.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def build(binding_path):
    binding_body = Path(binding_path).read_bytes()
    if len(binding_body) > 65536:
        raise ValueError('oversized preflight observation')
    binding = json.loads(binding_body)
    pin = binding.get('stdout', {})
    if (set(pin) != {'bytes', 'sha256'} or type(pin['bytes']) is not int or not 0 < pin['bytes'] <= 4 << 20 or
            type(pin['sha256']) is not str or re.fullmatch('[0-9a-f]{64}', pin['sha256']) is None or
            type(binding.get('observed_utc')) is not str or not binding['observed_utc'] or
            binding.get('status') != 'ACTUAL_RESUME5_PREFLIGHT_ACCEPTED' or binding.get('accepted') is not True):
        raise ValueError('actual accepted resume5 preflight observation required')
    manifest_body = (HERE / 'transfer-manifest.json').read_bytes()
    manifest = json.loads(manifest_body)
    if [r['path'] for r in manifest['files']] != [row[1] for row in builder.FILES]:
        raise ValueError('source-only manifest inventory differs')
    for row, (local, _) in zip(manifest['files'], builder.FILES):
        body = (HERE / local).read_bytes()
        if {'bytes': len(body), 'sha256': builder.sha(body)} != {k: row[k] for k in ('bytes', 'sha256')}:
            raise ValueError('reviewed source bytes changed')
    template = (HERE / 'observe_ready.py').read_text()
    values = {'PREFLIGHT_SHA256': pin['sha256'], 'PREFLIGHT_BYTES': pin['bytes']}
    before = ast.parse(template)
    for name, value in values.items():
        assignment = name + ' = None'
        if template.count(assignment) != 1:
            raise ValueError('unbound ready template differs')
        template = template.replace(assignment, name + ' = ' + repr(value))
    after = ast.parse(template)
    for node in after.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in values for t in node.targets):
            node.value = ast.Constant(value=None)
    if ast.dump(before, include_attributes=False) != ast.dump(after, include_attributes=False):
        raise ValueError('ready collector changed beyond its actual preflight pins')
    launcher = manifest['files'][1]
    launch = builder.COMMON + f"p=BASE/{launcher['path']!r}\nb=read(p,{launcher['bytes']})\nif len(b)!={launcher['bytes']} or hashlib.sha256(b).hexdigest()!={launcher['sha256']!r}: raise ValueError('launcher source differs')\nimport sys\nsys.argv=[str(p),'--preflight-sha256',{pin['sha256']!r},'--preflight-bytes',{str(pin['bytes'])!r}]\nexec(compile(b,str(p),'exec'),{{'__name__':'__main__','__file__':str(p)}})\n"
    OUT.mkdir(mode=0o700)
    (OUT / 'preflight-binding.json').write_bytes(binding_body)
    (OUT / 'observe_ready.py').write_text(template)
    commands = [builder.command(OUT, 'launch-observer', launch), builder.command(OUT, 'observe-ready', template)]
    result = {'schema': 1, 'status': 'BOUND_TO_ACTUAL_PREFLIGHT_PENDING_INDEPENDENT_REVIEW',
              'preflight': pin, 'observed_utc': binding['observed_utc'],
              'binding_sha256': builder.sha(binding_body), 'source_manifest_sha256': builder.sha(manifest_body),
              'source_files': manifest['files'], 'commands': commands, 'phone_execution': False,
              'unbound_source_only_files_preserved': True}
    (OUT / 'runtime-transport.json').write_bytes(builder.json_bytes(result))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: finalize_runtime.py ACTUAL_PREFLIGHT_BINDING.json')
    build(sys.argv[1])
