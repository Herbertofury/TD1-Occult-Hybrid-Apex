"""Inventory layered Python owners without importing or starting the recovered backend."""
import argparse
import ast
import collections
import hashlib
from pathlib import Path
from source_manifest import write_json


def inventory(path):
    raw = Path(path).read_bytes()
    tree = ast.parse(raw.decode('utf-8-sig'), filename=str(path), feature_version=(3, 7))
    definitions = collections.defaultdict(list)
    bindings = {}
    captures = []
    startup = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            row = {'name': node.name, 'line': node.lineno,
                   'kind': type(node).__name__, 'captured_by': [], 'startup_calls': [],
                   'references': sorted({child.id for child in ast.walk(node)
                                         if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)})}
            definitions[node.name].append(row)
            bindings[node.name] = row
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Name):
            previous = bindings.get(node.value.id)
            if previous:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        captures.append({'alias': target.id, 'line': node.lineno,
                                         'owner': previous['name'], 'owner_line': previous['line']})
                        previous['captured_by'].append(target.id)
                        bindings[target.id] = previous
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            name = call.func.id if isinstance(call.func, ast.Name) else ast.unparse(call.func)
            startup.append({'line': node.lineno, 'call': name})
            if name in bindings:
                bindings[name]['startup_calls'].append(node.lineno)
    rows = []
    for name in sorted(definitions):
        for row in definitions[name]:
            row['final_global_owner'] = row is definitions[name][-1]
            if row['final_global_owner']:
                row['reachability'] = 'final-global-owner'
            elif row['captured_by']:
                row['reachability'] = 'retained-through-alias'
            elif row['startup_calls']:
                row['reachability'] = 'import-time-only-before-redefinition'
            else:
                row['reachability'] = 'superseded-global-definition-review-registrations'
            rows.append(row)
    return {'schema': 1, 'source_sha256': hashlib.sha256(raw).hexdigest(),
            'python_syntax_target': '3.7', 'definition_count': len(rows),
            'duplicate_names': {name: [row['line'] for row in values]
                                for name, values in sorted(definitions.items()) if len(values) > 1},
            'definitions': rows, 'alias_captures': captures, 'top_level_calls': startup,
            'limitations': ['Static namespace/capture inventory; runtime coverage is still required.',
                           'Nested registrations, dynamic globals and callbacks can retain earlier definitions.',
                           'Do not delete superseded definitions without inspecting those owners.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = inventory(args.source)
    write_json(args.output, data)
    print('Definitions: {}; duplicated names: {}'.format(data['definition_count'], len(data['duplicate_names'])))
