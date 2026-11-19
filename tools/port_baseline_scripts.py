"""Adapt authorized 1.13.7 bytecode into an Apex-owned package namespace.

Deserialize/transform/serialize with the pinned matching compiler. Baseline game
modules are never imported or executed by this tool. Exact instruction bytes,
integer tuning IDs and non-namespace constants remain intact outside the exact
documented persistence and legacy-entry adaptations. Decompiler output
is research only and is never silently shipped as recovered source.
"""
import base64
import io
import json
import os
from pathlib import Path
import subprocess
import zipfile
from dbpf_build import digest
from fetch_build_python import DEFAULT_OUTPUT

PATCHES = {
    'save': '''def save(original, self, *args, **kwargs):
    from apex_core.hybrid_persistence import save_with_retention
    return save_with_retention(original, self, occult_utils, *args, **kwargs)
''',
    'load': '''def load(original, self, data):
    from apex_core.hybrid_persistence import load_with_retention
    return load_with_retention(original, self, data, occult_cache, occult_utils, OccultType, SimInfoBaseWrapper)
'''}

# Keys are verified module/class paths, not broad method-name matches. Original
# guarded bodies retain their complete instruction stream beneath the gate.
LEGACY_ADAPTATIONS = {
    'apex_hybrid/IC_Hybrid/commands.py': {
        name: {'kind': 'retired', 'args': args, 'kwargs': False}
        for name, args in (
            ('edit_form_in_cas', ['occult_type', 'opt_sim', '_connection']),
            ('restore_occult', ['opt_sim', '_connection']),
            ('plan_batuu_outfit', ['opt_sim', '_connection']))},
    'apex_hybrid/IC_Hybrid/interactions.py': {},
    'apex_hybrid/CoreLib/TD1_OccultHybrid_Config.py': {
        'option_toggle': {'kind': 'settings-idle', 'args': ['config_key', 'to_set'], 'kwargs': False}}}
LEGACY_ADAPTATIONS['apex_hybrid/IC_Hybrid/commands.py']['remove_conflicting_traits'] = {
    'kind': 'sim-info-idle', 'args': ['sim_info', 'trait_to_check', 'output'], 'kwargs': False}
for _name, _args in (
        ('set_occult_type', ['occult_type', 'opt_sim', '_connection']),
        ('switch_to_occult', ['occult_type', 'opt_sim', '_connection']),
        ('remove_conflicting_traits_for_occult_type', ['occult_type', 'opt_sim', '_connection']),
        ('add_occult_type', ['occult_type', 'opt_sim', '_connection']),
        ('force_add_trait', ['trait_type', 'opt_sim', '_connection']),
        ('delete_form', ['occult_type', 'opt_sim', '_connection']),
        ('cmd_recalc_all', ['opt_sim', '_connection']),
        ('cmd_switch_occult', ['opt_sim', 'occult', '_connection'])):
    LEGACY_ADAPTATIONS['apex_hybrid/IC_Hybrid/commands.py'][_name] = {
        'kind': 'command-idle', 'args': _args, 'kwargs': False}
for _class, _args in (
        ('OccultTraitPickerSuperInteraction', ['self', 'choice_tag']),
        ('OccultTogglePickerSuperInteraction', ['self', 'choice_tag']),
        ('OccultFormDeletePickerSuperInteraction', ['self', 'choice_tag', 'show_again']),
        ('OccultTypePickerSuperInteraction', ['self', 'choice_tag']),
        ('OccultPerkResetPickerSuperInteraction', ['self', 'choice_tag', 'show_again']),
        ('OccultSecondaryFormPickerSuperInteraction', ['self', 'choice_tag'])):
    LEGACY_ADAPTATIONS['apex_hybrid/IC_Hybrid/interactions.py'][_class + '.on_choice_selected'] = {
        'kind': 'interaction-idle', 'args': _args, 'kwargs': True}

TRANSFORM = r'''
import base64, hashlib, importlib.util, json, marshal, sys, types
if sys.version_info[:2] != (3, 7) or importlib.util.MAGIC_NUMBER != b'\x42\x0d\x0d\x0a':
    raise RuntimeError('Matching private Python 3.7 compiler required.')
def rename(value):
    if isinstance(value, str):
        if value == 'OccultHybrid' or value.startswith('OccultHybrid.') or value.startswith('OccultHybrid/'):
            return 'apex_hybrid' + value[len('OccultHybrid'):]
    return value
def constant(value, filename, parent):
    if isinstance(value, types.CodeType):
        return transform(value, filename, parent)
    if isinstance(value, tuple):
        return tuple(constant(item, filename, parent) for item in value)
    if isinstance(value, frozenset):
        return frozenset(constant(item, filename, parent) for item in value)
    return rename(value)
def transplant_constants(code, values):
    return types.CodeType(code.co_argcount, code.co_kwonlyargcount, code.co_nlocals,
        code.co_stacksize, code.co_flags, code.co_code, tuple(values), code.co_names,
        code.co_varnames, code.co_filename, code.co_name, code.co_firstlineno,
        code.co_lnotab, code.co_freevars, code.co_cellvars)
def legacy_boundary(code, filename, qualified, original):
    rule = adaptations.get(filename, {}).get(qualified)
    if rule is None:
        return original
    key = (filename, qualified)
    if key in seen:
        raise RuntimeError('Duplicate legacy mutation boundary: ' + qualified)
    if (list(code.co_varnames[:code.co_argcount]) != rule['args'] or code.co_kwonlyargcount or
            code.co_freevars or bool(code.co_flags & 8) != rule['kwargs'] or code.co_flags & (4 | 32 | 128 | 512)):
        raise RuntimeError('Legacy mutation callable contract changed: ' + qualified)
    signature = ', '.join(rule['args'] + (['**kwargs'] if rule['kwargs'] else []))
    if rule['kind'] == 'retired':
        body = '    from apex_core.legacy_phone_guard import retired\n    return retired(_connection)\n'
    else:
        guards = {
            'command-idle': '    from apex_core.legacy_phone_guard import command_idle\n    command_idle(opt_sim, _connection)\n',
            'sim-info-idle': '    from apex_core.legacy_phone_guard import sim_info_idle\n    sim_info_idle(sim_info)\n',
            'settings-idle': '    from apex_core.legacy_phone_guard import settings_idle\n    settings_idle()\n',
            'interaction-idle': '    if choice_tag is not None:\n        from apex_core.legacy_phone_guard import interaction_idle\n        interaction_idle(self)\n'}
        guard = guards[rule['kind']]
        body = guard + '    def _apex_guarded_original(' + signature + '):\n        return None\n'
        body += '    return _apex_guarded_original(' + signature + ')\n'
    compiled = compile('def ' + code.co_name + '(' + signature + '):\n' + body, filename, 'exec', dont_inherit=True)
    wrapper = next(value for value in compiled.co_consts if isinstance(value, types.CodeType))
    if rule['kind'] != 'retired':
        values, replaced = [], 0
        for value in wrapper.co_consts:
            if isinstance(value, types.CodeType) and value.co_name == '_apex_guarded_original':
                values.append(original)
                replaced += 1
            else:
                values.append(value)
        if replaced != 1:
            raise RuntimeError('Legacy guard must retain exactly one complete original body.')
        wrapper = transplant_constants(wrapper, values)
    if (wrapper.co_argcount != code.co_argcount or wrapper.co_kwonlyargcount != code.co_kwonlyargcount or
            wrapper.co_freevars or bool(wrapper.co_flags & 8) != bool(code.co_flags & 8)):
        raise RuntimeError('Legacy guard changed the native callable signature.')
    seen.add(key)
    audit.append({'function': qualified, 'kind': rule['kind'],
        'original_instruction_sha256': hashlib.sha256(code.co_code).hexdigest(),
        'guarded_original_instruction_sha256': hashlib.sha256(original.co_code).hexdigest()
             if rule['kind'] != 'retired' else None,
        'replacement_instruction_sha256': hashlib.sha256(wrapper.co_code).hexdigest()})
    return wrapper
def transform(code, filename, parent=''):
    qualified = parent + code.co_name
    if filename.endswith('/IC_Hybrid/_occult_tracker.py') and code.co_name in patches:
        replacement = compile(patches[code.co_name], filename, 'exec', dont_inherit=True)
        updated = next(item for item in replacement.co_consts if isinstance(item, types.CodeType))
        if code.co_freevars or updated.co_freevars:
            raise RuntimeError('Persistence port cannot replace closure-backed functions.')
        return updated
    updated = types.CodeType(code.co_argcount, code.co_kwonlyargcount, code.co_nlocals,
        code.co_stacksize, code.co_flags, code.co_code,
        tuple(constant(value, filename, qualified + '.') for value in code.co_consts),
        tuple(rename(value) for value in code.co_names), code.co_varnames,
        filename, code.co_name, code.co_firstlineno, code.co_lnotab,
        code.co_freevars, code.co_cellvars)
    if updated.co_code != code.co_code:
        raise RuntimeError('Baseline instructions changed unexpectedly.')
    logical = qualified[len('<module>.'):] if qualified.startswith('<module>.') else qualified
    return legacy_boundary(code, filename, logical, updated)
request = json.load(sys.stdin)
patches = request['patches']
adaptations = request['legacy_adaptations']
rows = []
for item in request['modules']:
    seen, audit = set(), []
    raw = base64.b64decode(item['payload'], validate=True)
    name = item['name']
    if name.endswith('.pyc'):
        if raw[:4] != importlib.util.MAGIC_NUMBER or len(raw) <= 16:
            raise RuntimeError('Incompatible baseline bytecode.')
        code = marshal.loads(raw[16:])
        if not isinstance(code, types.CodeType):
            raise RuntimeError('Baseline contains a non-code bytecode payload.')
        code = transform(code, name[:-1])
        payload = importlib.util.MAGIC_NUMBER + b'\0' * 12 + marshal.dumps(code)
    else:
        source = raw.decode('utf-8-sig').replace('from OccultHybrid.', 'from apex_hybrid.').replace('import OccultHybrid.', 'import apex_hybrid.')
        if name.endswith('/Modules/TD1_OccultHybrid_StabilizeFix.py'):
            source = source.replace('        global RAN_FIX\n', '')
            source = source.replace('    result = original(self, *args, **kwargs)', '    global RAN_FIX\n    result = original(self, *args, **kwargs)')
            source = source.replace('        return\n', '        return result\n')
            source = source.replace('\ndef get_current_occult_trait', '    return result\n\ndef get_current_occult_trait')
        code = transform(compile(source, name, 'exec', dont_inherit=True, optimize=0), name)
        payload = importlib.util.MAGIC_NUMBER + b'\0' * 12 + marshal.dumps(code)
        name += 'c'
    expected = set(adaptations.get(name[:-1], {}))
    if {qualified for filename, qualified in seen} != expected:
        raise RuntimeError('Legacy mutation boundary inventory changed: ' + name)
    marshal.loads(payload[16:])
    rows.append({'name': name, 'payload': base64.b64encode(payload).decode('ascii'),
                 'legacy_adaptations': audit, 'legacy_adaptation_count': len(audit)})
print(json.dumps(rows))
'''


def port(script, python37=None):
    compiler = Path(python37 or DEFAULT_OUTPUT / 'python.exe').resolve(strict=True)
    rows, records = [], []
    with zipfile.ZipFile(io.BytesIO(script)) as archive:
        names = set()
        for info in sorted(archive.infolist(), key=lambda row: row.filename):
            if info.is_dir():
                continue
            old = info.filename
            if not old.startswith('OccultHybrid/') or not old.endswith(('.py', '.pyc')) or '..' in Path(old).parts or info.file_size > 4 * 1024 * 1024:
                raise ValueError('Unexpected baseline module: ' + old)
            name = 'apex_hybrid/' + old[len('OccultHybrid/'):]
            compiled_name = name + 'c' if name.endswith('.py') else name
            if compiled_name in names:
                raise ValueError('Duplicate migrated module.')
            names.add(compiled_name)
            raw = archive.read(info)
            if name.endswith('/Modules/occult_cas_restore.pyc'):
                name = name[:-1]
                effective = b'"""Legacy automatic CAS restoration retired; use the explicit Apex shield."""\n'
                adaptation = 'Retired stale whole-library auto-restore callback; canonical Apex shield owns restoration.'
            else:
                effective = raw
                adaptation = 'Apex namespace and portable filenames; compiled instruction stream preserved.'
            if name.endswith('/IC_Hybrid/_occult_tracker.pyc'):
                adaptation = 'Apex namespace; load/save port retains unresolved forms and restores transient flags in finally.'
            if name.endswith('/Modules/TD1_OccultHybrid_StabilizeFix.py'):
                adaptation = 'Apex namespace; valid global declaration and original callback return preserved.'
            rows.append({'name': name, 'payload': base64.b64encode(effective).decode('ascii')})
            records.append({'source_module': old, 'apex_module': compiled_name, 'source_sha256': digest(raw),
                            'adaptation': adaptation})
    environment = os.environ.copy()
    environment.pop('PYTHONPATH', None)
    environment['PYTHONHOME'] = str(compiler.parent)
    environment['PYTHONHASHSEED'] = '0'
    if (compiler.parent / 'python37._pth').exists():
        raise ValueError('Unconfigured compiler isolation; use fetch_build_python.py.')
    result = subprocess.run([str(compiler), '-B', '-S', '-s', '-c', TRANSFORM], input=json.dumps({
                            'modules': rows, 'patches': PATCHES, 'legacy_adaptations': LEGACY_ADAPTATIONS}),
                            text=True, capture_output=True, env=environment, cwd=str(compiler.parent), timeout=60)
    if result.returncode:
        raise ValueError('Authorized bytecode adaptation failed: ' + result.stderr[-2000:])
    transformed = json.loads(result.stdout)
    payloads = [(row['name'], base64.b64decode(row['payload'], validate=True)) for row in transformed]
    guarded_modules = {name[:-1] for name, _payload in payloads if name[:-1] in LEGACY_ADAPTATIONS}
    if guarded_modules and guarded_modules != set(LEGACY_ADAPTATIONS):
        raise ValueError('Authorized legacy mutation module inventory is incomplete.')
    if {name for name, _ in payloads} != names:
        raise ValueError('Migrated module inventory mismatch.')
    for record, (name, payload), adapted in zip(records, payloads, transformed):
        if record['apex_module'] != name:
            raise ValueError('Migrated module order mismatch.')
        record['sha256'] = digest(payload)
        record['legacy_adaptations'] = adapted['legacy_adaptations']
        record['legacy_adaptation_count'] = adapted['legacy_adaptation_count']
        if adapted['legacy_adaptation_count']:
            record['adaptation'] += '; exact legacy mutation guards and unsafe CAS/cache command retirement.'
    return payloads, records
