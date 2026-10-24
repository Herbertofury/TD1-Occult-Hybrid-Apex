import base64
import io
import json
import os
from pathlib import Path
import sys
import subprocess
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from build_script import compile_payloads
from fetch_build_python import DEFAULT_OUTPUT
from inspect_script_code import inspect
from port_baseline_scripts import port, LEGACY_ADAPTATIONS


class NamespacePortTests(unittest.TestCase):
    def fixtures(self):
        result = []
        for module, rules in LEGACY_ADAPTATIONS.items():
            source = ['EVENTS = []']
            for name, rule in rules.items():
                args = list(rule['args'])
                if rule['kwargs']:
                    args = [arg + '=True' if arg == 'show_again' else arg for arg in args] + ['**kwargs']
                prefix = ''
                if '.' in name:
                    cls, function = name.split('.')
                    source.append('class ' + cls + ':')
                    source.append('    picker_target = "target"')
                    prefix = '    '
                else:
                    function = name
                source.append(prefix + 'def ' + function + '(' + ', '.join(args) + '):')
                source.append(prefix + '    EVENTS.append(' + repr(name) + ')')
                source.append(prefix + '    return "original-result"')
            if module.endswith('TD1_OccultHybrid_Config.py'):
                source += ['def config_set_option(option):', '    def on_response():',
                    '        return option_toggle(option, True)', '    return on_response']
            result.append((module.replace('apex_hybrid/', 'OccultHybrid/'), ('\n'.join(source) + '\n').encode()))
        return result

    def compiled_port(self, fixtures):
        compiled, _ = compile_payloads(fixtures, DEFAULT_OUTPUT / 'python.exe')
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            for name, raw in compiled:
                archive.writestr(name, raw)
        return port(stream.getvalue())

    def test_exact_legacy_guards_run_before_owned_fixture_mutations_preserve_defaults_and_retire_cas(self):
        payloads, records = self.compiled_port(self.fixtures())
        self.assertEqual(sum(record['legacy_adaptation_count'] for record in records), 19)
        for record in records:
            for rule in record['legacy_adaptations']:
                if rule['kind'] != 'retired':
                    self.assertEqual(rule['original_instruction_sha256'], rule['guarded_original_instruction_sha256'])
        # Only OUR tiny fixture modules execute here. Installed/baseline modules
        # are inspected passively in the separate test below, never imported.
        program = r'''
import base64, json, marshal, sys, types
data = json.load(sys.stdin)
pending, checks = [False], []
def gate(*args):
    checks.append('gate')
    if pending[0]: raise ValueError('pending')
def retired(*args):
    checks.append('retired')
    return False
helper = types.ModuleType('apex_core.legacy_phone_guard')
helper.command_idle = helper.interaction_idle = helper.sim_info_idle = helper.settings_idle = gate
helper.retired = retired
sys.modules['apex_core'] = types.ModuleType('apex_core')
sys.modules['apex_core.legacy_phone_guard'] = helper
modules = {}
for name, payload in data['modules']:
    scope = {'__name__': name}
    exec(marshal.loads(base64.b64decode(payload)[16:]), scope)
    modules[name[:-1]] = scope
assert checks == [], 'function-entry gates must not run during imports'
for name, rules in data['rules'].items():
    scope = modules[name]
    for qualified, rule in rules.items():
        if '.' in qualified:
            cls, method = qualified.split('.')
            subject = scope[cls]()
            function = getattr(subject, method)
            arguments = ['choice'] if 'show_again' not in rule['args'] else ['choice']
        else:
            function = scope[qualified]
            arguments = [object() for _ in rule['args']]
        pending[0] = True
        before = list(scope['EVENTS'])
        if rule['kind'] == 'retired':
            assert function(*arguments) is False
        else:
            try: function(*arguments)
            except ValueError: pass
            else: raise AssertionError('guard did not refuse pending')
        assert scope['EVENTS'] == before, qualified + ' mutated before its gate'
        pending[0] = False
        if rule['kind'] != 'retired':
            assert function(*arguments) == 'original-result'
            assert scope['EVENTS'][-1] == qualified
config = modules['apex_hybrid/CoreLib/TD1_OccultHybrid_Config.py']
pending[0] = False
callback = config['config_set_option']('occult_form_memory')
before = list(config['EVENTS'])
pending[0] = True
try: callback()
except ValueError: pass
else: raise AssertionError('old settings dialog bypassed the final execution gate')
assert config['EVENTS'] == before
print(json.dumps({'ok': True, 'boundaries': sum(len(r) for r in data['rules'].values())}))
'''
        compiler = DEFAULT_OUTPUT / 'python.exe'
        environment = os.environ.copy()
        environment.pop('PYTHONPATH', None)
        environment['PYTHONHOME'] = str(compiler.parent)
        result = subprocess.run([str(compiler), '-B', '-S', '-s', '-c', program],
            input=json.dumps({'modules': [(name, base64.b64encode(raw).decode()) for name, raw in payloads],
                              'rules': LEGACY_ADAPTATIONS}), text=True, capture_output=True,
            cwd=str(compiler.parent), env=environment, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'ok': True, 'boundaries': 19})

    def test_missing_duplicate_or_signature_changed_legacy_boundary_refuses_port(self):
        fixtures = self.fixtures()
        first_name, first = fixtures[0]
        mutations = [first.replace(b'def restore_occult(', b'def unexpected_restore('),
            first.replace(b'def delete_form(occult_type,', b'def delete_form(unverified_type,'),
            first + b'\ndef restore_occult(opt_sim, _connection):\n    return True\n']
        for source in mutations:
            with self.subTest(source=source[-100:]), self.assertRaisesRegex(ValueError, 'adaptation failed'):
                self.compiled_port([(first_name, source)] + fixtures[1:])

    def test_actual_authorized_baseline_is_only_passively_ported_with_exact_19_boundary_provenance(self):
        baseline = Path(__file__).resolve().parents[1] / '.work/baselines/LordPercivalXII.Occult.Hybrid.Unlocker.Stabilizer.Version.1.13.7.zip'
        if not baseline.is_file():
            self.skipTest('Private authorized baseline is not present; owned fixtures still enforce the same contract.')
        with zipfile.ZipFile(baseline) as archive:
            raw = archive.read(next(name for name in archive.namelist() if name.endswith('.ts4script')))
        _payloads, records = port(raw)
        counts = {record['apex_module']: record['legacy_adaptation_count'] for record in records
                  if record['legacy_adaptation_count']}
        self.assertEqual(counts, {'apex_hybrid/IC_Hybrid/commands.pyc': 12,
            'apex_hybrid/IC_Hybrid/interactions.pyc': 6, 'apex_hybrid/CoreLib/TD1_OccultHybrid_Config.pyc': 1})
        for record in records:
            for rule in record['legacy_adaptations']:
                if rule['kind'] != 'retired':
                    self.assertEqual(rule['original_instruction_sha256'], rule['guarded_original_instruction_sha256'])

    def test_nested_namespaces_change_without_changing_instructions_or_tuning_ids(self):
        source = b'import OccultHybrid.IC_Hybrid\ndef nested():\n    return ("OccultHybrid.IC_Hybrid", 18197032510434408842)\n'
        compiled, _ = compile_payloads([('OccultHybrid/example.py', source)], DEFAULT_OUTPUT / 'python.exe')
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            for name, raw in compiled:
                archive.writestr(name, raw)
        adapted, records = port(stream.getvalue())
        second = io.BytesIO()
        with zipfile.ZipFile(second, 'w') as archive:
            for name, raw in adapted:
                archive.writestr(name, raw)
        original = inspect(stream.getvalue(), 'OccultHybrid/example.pyc')
        migrated = inspect(second.getvalue(), 'apex_hybrid/example.pyc')
        self.assertEqual([row['instruction_sha256'] for row in original], [row['instruction_sha256'] for row in migrated])
        self.assertIn('apex_hybrid.IC_Hybrid', migrated[0]['names'])
        self.assertIn(18197032510434408842, migrated[1]['constants'])
        self.assertEqual(migrated[1]['filename'], 'apex_hybrid/example.py')
        self.assertEqual(len(records), 1)

    def test_unexpected_outside_module_is_rejected(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('../outside.py', 'raise RuntimeError("must never execute")')
        with self.assertRaises(ValueError):
            port(stream.getvalue())
