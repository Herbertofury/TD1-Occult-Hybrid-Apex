"""Synthetic disposable migration fixtures; no actual game/profile operations."""
import copy
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import subprocess
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from test_form_bank_seal import SealFixture
from apex_core import form_bank_seal as seal, form_bank
import build_script
import reusable_profile as profiles
import test_profile
import test_script_upgrade as upgrade
from source_manifest import sha256, write_json


def archive_of(members, compiler):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(members.items()): archive.writestr(name, raw)
    raw = stream.getvalue()
    rows = [{'module': name, 'bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()}
            for name, value in sorted(members.items())]
    return raw, {'schema': 1, 'artifact': 'ApexOccultHybrid.ts4script', 'compiler': compiler,
        'sha256': hashlib.sha256(raw).hexdigest(), 'modules': [row for row in rows if row['module'].endswith('.py')],
        'compiled_modules': [row for row in rows if row['module'].endswith('.pyc')]}


class TargetFixture:
    @classmethod
    def setUpClass(cls):
        sources = [(name, (ROOT / 'Source' / name).read_bytes())
                   for name in sorted(set(seal.UPGRADE_MODULE_PINS) | {'apex_core/form_bank_seal.py'})]
        compiled, cls.compiler = build_script.compile_payloads(sources, build_script.DEFAULT_OUTPUT / 'python.exe')
        cls.members = dict(sources + compiled)
        cls.target_raw, cls.manifest = archive_of(cls.members, cls.compiler)
        cls.target_sha = hashlib.sha256(cls.target_raw).hexdigest()


class ArchiveTests(TargetFixture, unittest.TestCase):
    def test_known_predecessor_remains_the_exact_reviewed_a0(self):
        self.assertEqual(seal.UPGRADE_PREDECESSOR, 'a0dff198bd8bf778c440883baf58d83e695b0a26e3d2b7a491e315fcbabf34ce')

    def test_actual_pinned_sources_and_private_python37_compile_are_accepted(self):
        self.assertEqual(upgrade.validate_target(self.target_raw, self.manifest), self.target_sha)

    def test_full_source_batch_preserves_python37_marshal_interning_order(self):
        source = ROOT / 'Source'
        paths = ([source / 'td1_occult_hybrid_apex.py'] +
                 sorted((source / 'apex_core').rglob('*.py')) +
                 sorted((source / 'apex_hybrid').rglob('*.py')))
        sources = [(path.relative_to(source).as_posix(), path.read_bytes()) for path in paths]
        compiled, compiler = build_script.compile_payloads(sources, build_script.DEFAULT_OUTPUT / 'python.exe')
        members = dict(sources + compiled)
        audited = {name[:-3] + '.pyc' for name in seal.UPGRADE_MODULE_PINS} | {'apex_core/form_bank_seal.pyc'}
        # Compiling the same audited sources alone produces different marshal
        # interned-string flags. That must not reject a genuine complete build.
        self.assertTrue(any(members[name] != self.members[name] for name in audited))
        raw, manifest = archive_of(members, compiler)
        rows = {row['module']: row for row in manifest['modules']}
        manifest['modules'] = [rows[name] for name, _raw in sources]
        self.assertEqual(upgrade.validate_target(raw, manifest), hashlib.sha256(raw).hexdigest())
        # The source order is build evidence: changing it without recompiling
        # cannot substitute a new bytecode batch for the certified target.
        manifest['modules'].sort(key=lambda row: row['module'])
        with self.assertRaisesRegex(ValueError, 'fresh audited-source compilation'):
            upgrade.validate_target(raw, manifest)

    def test_source_contract_text_cannot_substitute_for_exact_reviewed_source(self):
        changed = dict(self.members)
        changed['apex_core/hybrid_persistence.py'] += b'\n# another implementation\n'
        raw, manifest = archive_of(changed, self.compiler)
        with self.assertRaisesRegex(ValueError, 'audited epoch'):
            upgrade.validate_target(raw, manifest)

    def test_rehashed_manifest_cannot_authorize_bytecode_from_other_source(self):
        changed = dict(self.members)
        item = bytearray(changed['apex_core/hybrid_persistence.pyc']); item[-1] ^= 1
        changed['apex_core/hybrid_persistence.pyc'] = bytes(item)
        raw, manifest = archive_of(changed, self.compiler)
        with self.assertRaisesRegex(ValueError, 'fresh audited-source compilation'):
            upgrade.validate_target(raw, manifest)

    def test_wrong_magic_inventory_and_receiver_body_are_refused(self):
        for kind in ('compiler', 'inventory', 'receiver'):
            with self.subTest(kind=kind):
                raw, manifest = self.target_raw, copy.deepcopy(self.manifest)
                if kind == 'compiler': manifest['compiler']['magic'] = '00000000'
                elif kind == 'inventory': manifest['compiled_modules'].append(manifest['compiled_modules'][0])
                else:
                    changed = dict(self.members); changed['apex_core/form_bank_seal.py'] += b'\n# altered receiver\n'
                    raw, manifest = archive_of(changed, self.compiler)
                with self.assertRaises(ValueError): seal.upgrade_archive(raw, manifest)

    def test_canonical_receiver_self_pin_cannot_hide_an_appended_statement(self):
        raw = self.members['apex_core/form_bank_seal.py']
        declaration = ("UPGRADE_SELF_BODY_SHA = '" + seal.UPGRADE_SELF_BODY_SHA + "'").encode()
        changed = raw.replace(declaration, declaration + b'; injected_operation()')
        with self.assertRaisesRegex(ValueError, 'no appended code'):
            seal.upgrade_source_hash('apex_core/form_bank_seal.py', changed)


class LoadedCodeTests(TargetFixture, unittest.TestCase):
    def test_python37_checks_real_code_graphs_classes_source_hash_and_archive_binding(self):
        source = b'def fn(value):\n    return value\nclass C:\n    def method(self):\n        return 1\n'
        inputs = [('probe.py', source)]
        compiled, _compiler = build_script.compile_payloads(inputs, build_script.DEFAULT_OUTPUT / 'python.exe')
        values = {name: base64.b64encode(raw).decode() for name, raw in dict(self.members, **dict(inputs + compiled)).items()}
        program = r'''
import ast, base64, importlib, json, marshal, sys, types
sys.path.insert(0, sys.argv[1])
from apex_core import form_bank_seal as seal
members = {name: base64.b64decode(raw) for name, raw in json.load(sys.stdin).items()}
for name, raw in members.items():
    if name.endswith('.pyc'):
        actual = marshal.loads(raw[16:])
        source = compile(members[name[:-4]+'.py'], name[:-4]+'.py', 'exec', dont_inherit=True, optimize=0)
        assert seal._code_identity(actual) == seal._code_identity(source)
archive = 'C:/fixture/ApexOccultHybrid.ts4script'
def code_named(code, name):
    if code.co_name == name: return code
    for item in code.co_consts:
        if isinstance(item, types.CodeType):
            found = code_named(item, name)
            if found is not None: return found
def function(code, module):
    value = types.FunctionType(code, vars(module), code.co_name)
    value.__module__ = module.__name__
    return value
probe_code = marshal.loads(members['probe.pyc'][16:])
seal_code = marshal.loads(members['apex_core/form_bank_seal.pyc'][16:])
seal._code_identity(probe_code); seal._code_identity(seal_code)
probe = types.SimpleNamespace(__name__='probe', __file__=archive+'/probe.pyc')
good = function(code_named(probe_code, 'fn'), probe)
method = function(code_named(probe_code, 'method'), probe)
owner = type('C', (), {'__module__': 'probe', 'method': method})
probe.fn = good; probe.C = owner
receiver = types.SimpleNamespace(__name__='apex_core.form_bank_seal',
    __file__=archive+'/apex_core/form_bank_seal.pyc')
for node in ast.parse(members['apex_core/form_bank_seal.py']).body:
    if isinstance(node, ast.FunctionDef):
        setattr(receiver, node.name, function(code_named(seal_code, node.name), receiver))
modules = {'probe': probe, 'apex_core.form_bank_seal': receiver}
importlib.import_module = lambda name: modules[name]
seal.UPGRADE_MODULE_PINS = {'probe.py': 'fixture'}
seal._verify_loaded_upgrade(members, archive)
def refused(action):
    try: action()
    except ValueError: return True
    raise AssertionError('altered loaded code was accepted')
bad = function(code_named(compile('def fn(value): return 999', 'probe.py', 'exec'), 'fn'), probe)
probe.fn = bad
refused(lambda: seal._verify_loaded_upgrade(members, archive)); probe.fn = good
del probe.fn
refused(lambda: seal._verify_loaded_upgrade(members, archive)); probe.fn = good
owner.method = bad
refused(lambda: seal._verify_loaded_upgrade(members, archive)); owner.method = method
probe.__file__ = 'C:/another/probe.pyc'
refused(lambda: seal._verify_loaded_upgrade(members, archive)); probe.__file__ = archive+'/probe.pyc'
raw = members['probe.pyc']; changed = bytearray(raw); changed[8] ^= 1; members['probe.pyc'] = bytes(changed)
refused(lambda: seal._verify_loaded_upgrade(members, archive)); members['probe.pyc'] = raw
changed = compile('def fn(value): return 999', 'probe.py', 'exec')
members['probe.pyc'] = raw[:16] + marshal.dumps(changed)
refused(lambda: seal._verify_loaded_upgrade(members, archive))
members['probe.pyc'] = raw + b'other data'
refused(lambda: seal._verify_loaded_upgrade(members, archive))
print('loaded-code guards passed')
'''
        compiler = build_script.DEFAULT_OUTPUT / 'python.exe'
        env = os.environ.copy(); env.pop('PYTHONPATH', None)
        env['PYTHONHOME'] = str(compiler.parent); env['PYTHONHASHSEED'] = '0'
        result = subprocess.run([str(compiler), '-B', '-S', '-s', '-c', program, str(ROOT / 'Source')],
            input=json.dumps(values), text=True, capture_output=True, env=env, cwd=compiler.parent, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'loaded-code guards passed')


class UpgradeFixture(TargetFixture, SealFixture):
    def setUp(self):
        super().setUp()
        self.old_raw = b'PK synthetic exact prior archive'
        self.old_sha = hashlib.sha256(self.old_raw).hexdigest()
        self.enterContext(patch.object(seal, 'UPGRADE_PREDECESSOR', self.old_sha))
        self.identity['script_sha256'] = self.old_sha
        self.certified = self.certify()
        self.original_seal = self.path.read_bytes()
        self.original_bank = self.bank_path.read_bytes()
        self.before_saves = upgrade.save_hashes(self.profile)
        self.original_before = test_profile.inventory(self.protected)
        self.artifacts = []
        names = [upgrade.SCRIPT, upgrade.NATIVE, 'Apex/Native/ApexOverlay.dll', 'Apex/Native/ApexOverlay.ini',
            'Apex/ApexOccultHybrid.package', 'Apex/ApexCASUnlocks.package', 'Apex/ApexCASBridge.package',
            'MCCC/mc_cmd_center.package', 'MCCC/mc_cmd_center.ts4script', 'MCCC/mc_cas.ts4script', 'MCCC/mc_dresser.ts4script']
        for name in names + ['ApexTest/Original Name.package', 'ApexTest/Unicode — Original.package', 'ApexTest/Lashes.package']:
            raw = self.old_raw if name == upgrade.SCRIPT else ('retained exact fixture ' + name).encode()
            path = self.profile / 'Mods' / name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            row = {'name': path.name, 'relative': name, 'sha256': sha256(path), 'source': str(path), 'fixture_metadata': 'keep'}
            if name.startswith('ApexTest/'): row.pop('relative')
            if name.startswith('MCCC/'): row['test_addon'] = 'mccc-2026.5.0'
            self.artifacts.append(row)
        self.native = self.profile / 'Mods' / upgrade.NATIVE
        write_json(self.native, {'schema': 1, 'protocol': 1, 'file': 'ApexOverlay.dll',
            'sha256': sha256(self.native.with_name('ApexOverlay.dll')), 'verified_script_sha256': self.old_sha,
            'custom_retained_field': 'unchanged'})
        next(row for row in self.artifacts if row.get('relative') == upgrade.NATIVE)['sha256'] = sha256(self.native)
        self.state = self.root / 'work' / 'state.json'; self.state.parent.mkdir()
        self.data = {'schema': 2, 'mode': 'reusable-test-only', 'phase': 'active', 'profile': str(self.profile),
            'protected_original': str(self.protected), 'token': self.identity['test_token'], 'generation': 7,
            'artifacts': self.artifacts, 'bundle': {'sha256': 'b' * 64, 'retain': 'prior bundle'}}
        write_json(self.state, self.data)
        self.payloads = {'Mods/' + upgrade.SCRIPT: self.target_raw,
            'Manifests/ApexOccultHybrid.ts4script.manifest.json': json.dumps(self.manifest).encode()}
        self.bundle = self.root / 'target.zip'
        self.enterContext(patch.object(upgrade.candidate_install, 'read_bundle',
            return_value=(self.bundle, 'c' * 64, {}, self.payloads)))
        # The host interpreter is 3.13. The separately tested verifier requires
        # Sims Python 3.7 and exact loaded modules; this fixture exercises every
        # real archive/source/inventory/bank/save guard around that one boundary.
        self.loaded_verifier = self.enterContext(patch.object(seal, '_verify_loaded_upgrade'))
        self.guard_calls = 0

    def guard(self):
        self.guard_calls += 1

    def install(self):
        return upgrade.install(self.state, self.bundle, self.certified['seal_sha256'], self.guard)

    def migrate_reload(self):
        self.install()
        self.identity['script_sha256'] = self.target_sha
        self.reload()

    def reconcile(self):
        return seal.reconcile(self.backend, self.sim, {'seal_sha256': self.certified['seal_sha256']})

    def unchanged(self):
        self.assertEqual(self.path.read_bytes(), self.original_seal)
        self.assertEqual(self.bank_path.read_bytes(), self.original_bank)
        self.assertEqual(upgrade.save_hashes(self.profile), self.before_saves)
        self.assertEqual(test_profile.inventory(self.protected), self.original_before)

    def archive_metadata(self):
        utf8 = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
            allow_nan=False, separators=(',', ':')).encode()).hexdigest()
        old = seal._store(self.path)['records'][self.key]
        prior = dict(self.identity, pid=self.identity['pid'] + 10)
        current = dict(self.identity, pid=self.identity['pid'] + 20)
        pending = {'state': 'captured', 'runtime_pid': prior['pid'], 'native_original': {
            'sim_id': self.target['sim_id'], 'save_guid': self.target['save_guid'], 'data': {'fields': [
                {'name': 'household_id', 'present': True, 'value': self.target['household_id']}]}}}
        pending_hash = utf8(pending)
        leaf = {'state': 'abandoned-unsaved-exit', 'pending': pending, 'pending_sha256': pending_hash,
            'prior_pid': prior['pid'], 'new_pid': current['pid'], 'failed_return_proof_sha256': 'e' * 64,
            'reloaded_file': {'sha256': old['file_sha256']}, 'appearance_restored': False, 'seal_created': False,
            'metadata_archive_only': True, 'disk_slot_verified': False, 'actual_native_slot_id': 0xffffffff,
            **{name: self.target[name] for name in ('sim_id', 'household_id', 'save_guid')}}
        bank = form_bank.load(self.bank_path)
        record = bank['records'][self.key]
        record.update(runtime_pid=prior['pid'], active_lane='64', failed_history=[leaf])
        record['history'].append({'state': 'completed', 'operation': 'unsaved-switch'})
        write_json(self.bank_path, bank); self.original_bank = self.bank_path.read_bytes()
        proof = {'schema': 1, 'operation': 'archive-unsaved-failed-cas-metadata',
            'outcome': 'failed-transaction-archived-without-appearance-writes', 'identity': current, 'prior_identity': prior,
            'expected_save_sha256': old['file_sha256'], 'slot_id': self.target['slot_id'],
            'pending_sha256': pending_hash, 'failed_return_proof_sha256': 'e' * 64,
            'native_save_slot': 0xffffffff, 'disk_slot_verified': False, 'allow_auto_save_slot_metadata_only': True,
            'bank_lanes_sha256': utf8(record['bank']),
            **{name: self.target[name] for name in ('sim_id', 'household_id', 'save_guid')},
            **{name: True for name in ('ok', 'finalized', 'archive_submitted', 'failed_history_retained_verified',
                'save_file_unchanged_verified', 'other_records_unchanged_verified', 'native_live_identity_verified')},
            **{name: False for name in ('appearance_mutated', 'bank_lanes_changed', 'save_submitted')}}
        self.archive_path = self.root / 'archive-proof.json'; write_json(self.archive_path, proof)
        self.archive_sha = sha256(self.archive_path)
        return {'metadata_archive_proof': self.archive_path, 'metadata_archive_sha256': self.archive_sha}


class HostUpgradeTests(UpgradeFixture):
    def test_default_plan_writes_no_profile_journal_receipt_or_staging(self):
        before = test_profile.inventory(self.profile); journal = self.state.read_bytes()
        result = upgrade.plan(self.state, self.bundle, self.certified['seal_sha256'])
        self.assertEqual(result['profile_writes'], 0); self.assertEqual(result['existing_artifacts_retained'], 14)
        self.assertEqual(self.state.read_bytes(), journal); self.assertEqual(test_profile.inventory(self.profile), before)
        self.assertFalse((self.state.parent / 'artifact-recovery').exists()); self.unchanged()

    def test_closed_journal_install_preserves_full_inputs_saves_bank_and_immutable_seal(self):
        result = self.install()
        self.assertTrue(result['ok']); self.assertGreater(self.guard_calls, 5)
        data = profiles.load(self.state)[1]
        self.assertEqual(len(data['artifacts']), 14); self.assertEqual(data['generation'], 8)
        self.assertEqual(data['bundle'], self.data['bundle']); self.assertEqual(data['token'], self.data['token'])
        for before in self.artifacts:
            relative = profiles.artifact_relative(before)
            after = next(row for row in data['artifacts'] if profiles.artifact_relative(row) == relative)
            self.assertEqual(after['fixture_metadata'], 'keep')
            if relative not in (upgrade.SCRIPT, upgrade.NATIVE): self.assertEqual(before['sha256'], after['sha256'])
        native = json.loads(self.native.read_text())
        self.assertEqual(native['verified_script_sha256'], self.target_sha)
        self.assertEqual(native['custom_retained_field'], 'unchanged')
        self.assertTrue(profiles.status(self.state)['ready_to_launch']); self.unchanged()
        receipt = self.data_dir / upgrade.RECEIPT; receipt_before = receipt.read_bytes()
        repeated = self.install()
        self.assertTrue(repeated['already_installed']); self.assertEqual(receipt.read_bytes(), receipt_before)
        self.assertEqual(profiles.load(self.state)[1]['generation'], 8); self.unchanged()

    def test_open_game_guard_blocks_before_any_profile_or_journal_mutation(self):
        before = test_profile.inventory(self.profile); journal = self.state.read_bytes()
        def running(): raise RuntimeError('native game still running')
        with self.assertRaisesRegex(RuntimeError, 'still running'):
            upgrade.install(self.state, self.bundle, self.certified['seal_sha256'], running)
        self.assertEqual(test_profile.inventory(self.profile), before); self.assertEqual(self.state.read_bytes(), journal)
        self.assertFalse(self.state.with_name(self.state.name + '.operation-lock').exists()); self.unchanged()

    def test_new_save_or_bank_refuses_without_installing_or_repinning(self):
        for kind in ('save', 'bank'):
            with self.subTest(kind=kind):
                self.slot.write_bytes(b'actual changed native save'); self.bank_path.write_bytes(self.original_bank)
                if kind == 'save': self.slot.write_bytes(b'legitimate newer save')
                else:
                    data = form_bank.load(self.bank_path); data['records'][self.key]['history'].append({'state': 'completed', 'new_edit': True})
                    write_json(self.bank_path, data)
                journal = self.state.read_bytes()
                with self.assertRaisesRegex(ValueError, 'newer'):
                    self.install()
                self.assertEqual(self.state.read_bytes(), journal); self.assertEqual(self.path.read_bytes(), self.original_seal)
                self.assertFalse((self.data_dir / upgrade.RECEIPT).exists())

    def test_ordinary_profile_marker_and_fourteen_input_inventory_are_mandatory(self):
        marker = self.profile / test_profile.MARKER
        write_json(marker, {'token': self.identity['test_token'], 'disposable': False})
        with self.assertRaisesRegex(ValueError, 'disposable profile marker'):
            upgrade.plan(self.state, self.bundle, self.certified['seal_sha256'])
        write_json(marker, {'token': self.identity['test_token'], 'disposable': True})
        data = copy.deepcopy(self.data); dropped = data['artifacts'].pop()
        (self.profile / 'Mods' / profiles.artifact_relative(dropped)).unlink(); write_json(self.state, data)
        with self.assertRaisesRegex(ValueError, 'fourteen'):
            upgrade.plan(self.state, self.bundle, self.certified['seal_sha256'])

    def test_interrupted_install_retains_receipt_and_journal_recovery_can_finish_exact_transition(self):
        def fail_when_journaled():
            self.guard()
            if json.loads(self.state.read_text())['phase'] == 'installing': raise RuntimeError('late closed guard refusal')
        with self.assertRaisesRegex(RuntimeError, 'late closed guard'):
            upgrade.install(self.state, self.bundle, self.certified['seal_sha256'], fail_when_journaled)
        receipt = (self.data_dir / upgrade.RECEIPT).read_bytes()
        self.assertEqual(json.loads(self.state.read_text())['phase'], 'installing'); self.unchanged()
        profiles.recover(self.state, self.guard)
        result = self.install()
        self.assertTrue(result['already_installed']); self.assertEqual((self.data_dir / upgrade.RECEIPT).read_bytes(), receipt)
        self.unchanged()

    def test_altered_receipt_or_newer_generation_cannot_be_overwritten_or_replayed(self):
        self.install(); path = self.data_dir / upgrade.RECEIPT; original = path.read_bytes()
        path.write_bytes(original.replace(seal.UPGRADE_EPOCH.encode('ascii'), b'invalid-unreviewed-epoch'))
        with self.assertRaisesRegex(ValueError, 'receipt is altered'): self.install()
        self.assertNotEqual(path.read_bytes(), original)
        path.write_bytes(original); data = profiles.load(self.state)[1]; data['generation'] += 1; write_json(self.state, data)
        with self.assertRaisesRegex(ValueError, 'newer artifacts/generation'): self.install()
        self.assertEqual(path.read_bytes(), original); self.unchanged()

    def test_output_cannot_replace_journal_or_any_profile_file(self):
        for path in (self.state, self.slot, self.protected / 'owner-save'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                upgrade.main(['--state', str(self.state), '--bundle', str(self.bundle), '--seal-sha256',
                    self.certified['seal_sha256'], '--output', str(path)])
        self.unchanged()


class ReceiverUpgradeTests(UpgradeFixture):
    def test_explicit_audited_transition_reconciles_once_without_rewriting_old_seal_bank_or_save(self):
        self.migrate_reload(); self.assertIn(self.key, seal._LOADED); self.assertEqual(self.writes, [])
        result = self.reconcile()
        self.assertTrue(result['ok']); self.assertEqual(result['stored_forms_verified'], list(seal.FORMS))
        self.assertEqual(result['upgrade_receipt_sha256'], seal._read(self.data_dir / upgrade.RECEIPT)['receipt_sha256'])
        self.assertTrue(seal.current_runtime_bank_verified(self.backend, self.sim, form_bank.load(self.bank_path)['records'][self.key]))
        self.unchanged()
        self.sim.physique = 'newer unsaved edit'; self.writes.clear(); seal.note_loaded(self.tracker)
        with self.assertRaisesRegex(ValueError, 'already reconciled'): self.reconcile()
        self.assertEqual(self.sim.physique, 'newer unsaved edit'); self.assertEqual(self.writes, []); self.unchanged()

    def test_no_receipt_wrong_predecessor_or_target_never_crosses_exact_source_guard(self):
        self.identity['script_sha256'] = self.target_sha; self.reload()
        self.assertNotIn(self.key, seal._LOADED)
        with self.assertRaisesRegex(ValueError, 'upgrade receipt'): self.reconcile()
        self.assertEqual(self.writes, []); self.unchanged()

    def test_changed_save_bank_archive_addon_or_loaded_code_refuses_before_native_writes(self):
        self.migrate_reload()
        for kind in ('save', 'bank', 'archive', 'addon', 'loaded'):
            with self.subTest(kind=kind):
                path = self.slot if kind == 'save' else self.bank_path if kind == 'bank' else self.profile / 'Mods' / (
                    upgrade.SCRIPT if kind == 'archive' else 'ApexTest/Lashes.package')
                original = path.read_bytes()
                if kind == 'loaded': self.loaded_verifier.side_effect = ValueError('loaded code changed')
                elif kind == 'bank':
                    value = json.loads(original); value['records'][self.key]['history'].append({'state': 'completed', 'newer': True})
                    write_json(path, value)
                else: path.write_bytes(original + b'new legitimate state')
                self.writes.clear()
                with self.assertRaises(ValueError): self.reconcile()
                self.assertEqual(self.writes, []); self.assertEqual(self.path.read_bytes(), self.original_seal)
                path.write_bytes(original); self.loaded_verifier.side_effect = None

    def test_new_native_edit_owner_tracker_or_unknown_owner_is_preserved(self):
        self.migrate_reload()
        original = self.forms[1].physique
        for kind in ('edit', 'tracker', 'unknown'):
            with self.subTest(kind=kind):
                self.forms[1].physique = original; seal._LOADED[self.key]['tracker'] = self.tracker
                if kind == 'edit': self.forms[1].physique = 'legitimate newer native edit'
                elif kind == 'tracker': seal._LOADED[self.key]['tracker'] = object()
                else:
                    self.forms[128] = copy.copy(self.forms[2])
                    seal._LOADED[self.key]['native'] = seal._native(self.backend, self.sim)
                with self.assertRaises(ValueError): self.reconcile()
                self.assertEqual(self.writes, []); self.unchanged()
                self.forms.pop(128, None)

    def test_partial_restore_failure_retains_separate_recovery_and_blocks_automatic_replay(self):
        self.migrate_reload()
        original = self.backend._restore_siminfo_payload; failed = [False]
        def fail_once(owner, fields):
            if not failed[0]: failed[0] = True; raise RuntimeError('native setter failed')
            original(owner, fields)
        self.backend._restore_siminfo_payload = fail_once
        with self.assertRaisesRegex(RuntimeError, 'native setter failed'): self.reconcile()
        runtime = seal._store(self.data_dir / 'form_bank_upgrade_runtime.json')['records'][self.key]
        self.assertEqual(runtime['state'], 'recovery-required'); self.assertFalse(runtime['reconciliation']['ok'])
        self.unchanged(); self.writes.clear(); seal._LOADED.clear(); seal.note_loaded(self.tracker)
        self.assertTrue(self.tracker._apex_seal_recovery_required); self.assertNotIn(self.key, seal._LOADED)
        with self.assertRaisesRegex(ValueError, 'recovery is unresolved'): self.reconcile()
        self.assertEqual(self.writes, []); self.unchanged()

    def test_receipt_rehash_cannot_change_epoch_token_seal_or_compiler_authority(self):
        self.migrate_reload(); path = self.data_dir / upgrade.RECEIPT; original = path.read_bytes()
        for field in ('epoch', 'test_token', 'old_seal_sha256', 'target_sha256', 'build_manifest'):
            with self.subTest(field=field):
                value = json.loads(original)
                if field == 'build_manifest':
                    value['receipt'][field]['compiler']['magic'] = '00000000'
                    value['receipt']['build_manifest_sha256'] = seal._hash(value['receipt'][field])
                else: value['receipt'][field] = 'd' * 64
                value['receipt_sha256'] = seal._hash(value['receipt']); write_json(path, value)
                with self.assertRaises(ValueError): self.reconcile()
                self.assertEqual(self.writes, []); self.assertEqual(self.path.read_bytes(), self.original_seal)
        path.write_bytes(original); self.unchanged()


class ArchivedMetadataTests(UpgradeFixture):
    def test_exact_archive_and_unchanged_seven_appearances_migrate_without_rebasing_metadata(self):
        args = self.archive_metadata()
        planned = upgrade.plan(self.state, self.bundle, self.certified['seal_sha256'], **args)
        self.assertNotEqual(planned['old_bank_record_sha256'], planned['current_bank_record_sha256'])
        self.assertTrue(seal._sha(planned['failed_history_leaf_sha256']))
        upgrade.install(self.state, self.bundle, self.certified['seal_sha256'], self.guard, **args)
        self.identity['script_sha256'] = self.target_sha; self.reload()
        result = self.reconcile(); self.assertTrue(result['ok']); self.unchanged()
        current = form_bank.load(self.bank_path)['records'][self.key]
        self.assertTrue(seal.current_runtime_bank_verified(self.backend, self.sim, current))
        self.assertEqual(current['failed_history'][0]['state'], 'abandoned-unsaved-exit')
        self.assertEqual(current['history'][-1]['operation'], 'unsaved-switch')

    def test_new_appearance_field_outfit_or_dye_cannot_borrow_archive_authority(self):
        args = self.archive_metadata(); original = self.bank_path.read_bytes()
        for kind in ('physique', 'outfit', 'dye'):
            with self.subTest(kind=kind):
                bank = json.loads(original); fields = bank['records'][self.key]['bank']['16']
                if kind == 'physique': fields['physique']['value'] = 'new accepted appearance'
                elif kind == 'outfit': fields['__outfits__']['value'] = fields['__outfits__']['value'] + 'AAAA'
                else: fields['new_dye_field'] = {'type': 'str', 'value': 'new dye'}
                write_json(self.bank_path, bank)
                with self.assertRaises(ValueError):
                    upgrade.plan(self.state, self.bundle, self.certified['seal_sha256'], **args)
                self.assertFalse((self.data_dir / upgrade.RECEIPT).exists())
        self.bank_path.write_bytes(original); self.unchanged()

    def test_cleared_changed_or_unrelated_failed_history_is_refused_by_host_and_receiver(self):
        args = self.archive_metadata(); original = self.bank_path.read_bytes()
        for kind in ('clear', 'pending', 'household', 'prior', 'proof'):
            with self.subTest(kind=kind):
                bank = json.loads(original); history = bank['records'][self.key]['failed_history']
                if kind == 'clear': history.clear()
                elif kind == 'pending': history[-1]['pending']['state'] = 'accepted'
                elif kind == 'household': history[-1]['household_id'] = '999'
                elif kind == 'prior': history[-1]['prior_pid'] += 1
                else: history[-1]['failed_return_proof_sha256'] = 'f' * 64
                write_json(self.bank_path, bank)
                with self.assertRaises(ValueError): upgrade.plan(self.state, self.bundle, self.certified['seal_sha256'], **args)
        self.bank_path.write_bytes(original)
        upgrade.install(self.state, self.bundle, self.certified['seal_sha256'], self.guard, **args)
        self.identity['script_sha256'] = self.target_sha; self.reload()
        bank = json.loads(original); bank['records'][self.key]['failed_history'].clear(); write_json(self.bank_path, bank)
        with self.assertRaises(ValueError): self.reconcile()
        self.assertEqual(self.writes, []); self.assertEqual(self.path.read_bytes(), self.original_seal)
        self.bank_path.write_bytes(original); self.unchanged()

    def test_changed_bank_requires_explicit_hash_bound_external_proof(self):
        self.archive_metadata()
        with self.assertRaisesRegex(ValueError, 'metadata-archive evidence'):
            upgrade.plan(self.state, self.bundle, self.certified['seal_sha256'])
        with self.assertRaisesRegex(ValueError, 'both the exact'):
            upgrade.plan(self.state, self.bundle, self.certified['seal_sha256'], self.archive_path)
        with self.assertRaisesRegex(ValueError, 'proof changed'):
            upgrade.plan(self.state, self.bundle, self.certified['seal_sha256'], self.archive_path, 'd' * 64)
        self.unchanged()


if __name__ == '__main__':
    unittest.main()
