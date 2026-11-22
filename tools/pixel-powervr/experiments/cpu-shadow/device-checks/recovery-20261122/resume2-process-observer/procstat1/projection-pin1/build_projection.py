#!/usr/bin/env python3
"""Build three bounded read-only query commands without changing installed code."""
import ast
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('observer_transport_builder', HERE.parent / 'build_transport.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
source = (HERE / 'observe_status.py').read_text()
compact_source = ast.unparse(ast.parse(source)) + '\n'
assert ast.dump(ast.parse(source), include_attributes=False) == ast.dump(ast.parse(compact_source), include_attributes=False)
steps = []
for name, arguments in [('observe-status', []), ('observe-final', ['--final']),
                        ('observe-final-json', ['--final', '--json'])]:
    code = 'import sys\nsys.argv=' + repr(['query'] + arguments) + '\n' + compact_source
    steps.append(builder.command(HERE, name, code))
report = {'schema': 1, 'status': 'READY_FOR_INDEPENDENT_READ_ONLY_REVIEW',
          'source_bytes': len(source.encode()), 'source_sha256': builder.sha(source.encode()),
          'ast_equivalent_formatting_only': True, 'terminal_output_lines_at_most': 69,
          'full_json_output_bytes_at_most': 128 << 10, 'commands': steps}
(HERE / 'projection-transport.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
