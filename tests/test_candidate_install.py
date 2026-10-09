import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import candidate_install as installer
import reusable_profile as profiles
import test_profile
from source_manifest import sha256, write_json


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.profile = self.root / 'The Sims 4'
        self.original = self.root / profiles.PROTECTED_NAME
        self.original.mkdir()
        (self.original / 'precious.txt').write_bytes(b'preserve original')
        (self.profile / 'Mods' / 'ApexTest').mkdir(parents=True)
        (self.profile / 'saves').mkdir()
        (self.profile / 'saves' / 'test.save').write_bytes(b'preserve test save')
        self.token = 'a' * 32
        write_json(self.profile / test_profile.MARKER, {'disposable': True, 'token': self.token})
        old = self.profile / 'Mods' / 'ApexTest' / 'old.package'
        old.write_bytes(b'DBPF old')
        self.state = self.root / 'work' / 'state.json'
        write_json(self.state, {'schema': 2, 'mode': 'reusable-test-only', 'phase': 'active', 'generation': 0,
            'token': self.token, 'profile': str(self.profile), 'protected_original': str(self.original),
            'artifacts': [{'name': old.name, 'sha256': sha256(old), 'source': str(old)}]})
        self.bundle = self.root / 'candidate.zip'
        self.make_bundle()
        self.before = test_profile.inventory(self.original)

    def make_bundle(self, corrupt=False, mismatch=False, unsafe=False):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('td1_occult_hybrid_apex.pyc', b'\x42\x0d\x0d\x0a' + b'fixture')
        script = stream.getvalue()
        dll = b'MZ' + b'fixture' * 1000
        native = {'schema': 1, 'file': 'ApexOverlay.dll', 'protocol': 1,
                  'sha256': hashlib.sha256(dll).hexdigest(), 'verified_script_sha256': '0' * 64 if mismatch else hashlib.sha256(script).hexdigest()}
        prefix = 'Mods/Apex/'
        payloads = {prefix + 'ApexOccultHybrid.package': b'DBPF hybrid', prefix + 'ApexCASUnlocks.package': b'DBPF unlocks',
            prefix + 'ApexOccultHybrid.ts4script': script, prefix + 'Native/ApexOverlay.dll': dll,
            prefix + 'Native/ApexOverlay.ini': b'[Apex]\nAutoStart=1\n', prefix + 'Native/overlay-manifest.json': json.dumps(native).encode()}
        if unsafe:
            payloads['../outside.txt'] = b'bad'
        manifest = {'schema': 1, 'target_game': 'fixture', 'files': [
            {'file': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()} for name, raw in payloads.items()]}
        if corrupt:
            payloads[prefix + 'Native/ApexOverlay.dll'] += b'tamper'
        with zipfile.ZipFile(self.bundle, 'w') as archive:
            for name, raw in payloads.items():
                archive.writestr(name, raw)
            archive.writestr('Manifests/candidate-manifest.json', json.dumps(manifest))

    def assert_preserved(self):
        self.assertEqual(test_profile.inventory(self.original), self.before)
        self.assertEqual((self.profile / 'saves' / 'test.save').read_bytes(), b'preserve test save')

    def test_full_bundle_installs_native_pair_and_preserves_both_saves(self):
        result = installer.install(self.state, self.bundle, guard=lambda: None)
        self.assertTrue(result['ready_to_launch'])
        self.assertEqual(len(result['artifacts']), 6)
        self.assertTrue((self.profile / 'Mods' / 'Apex' / 'Native' / 'ApexOverlay.dll').is_file())
        self.assertFalse((self.profile / 'Mods' / 'ApexTest' / 'old.package').exists())
        self.assert_preserved()

    def test_tampered_manifest_wrong_native_pair_and_zip_traversal_refuse_before_writes(self):
        for kwargs in ({'corrupt': True}, {'mismatch': True}, {'unsafe': True}):
            self.make_bundle(**kwargs)
            before = test_profile.inventory(self.profile)
            with self.assertRaises(ValueError):
                installer.install(self.state, self.bundle, guard=lambda: None)
            self.assertEqual(test_profile.inventory(self.profile), before)
            self.assert_preserved()

    def test_interrupted_native_install_recovers_with_matching_script(self):
        settings = self.profile / 'Mods' / 'Apex' / 'TD1_OccultHybrid_Settings.json'
        settings.parent.mkdir(exist_ok=True)
        settings.write_text('{"occult_form_memory":true}')
        replace = profiles.os.replace
        def fail_dll(source, target):
            if Path(target).suffix == '.dll':
                raise OSError('interrupted DLL copy')
            return replace(source, target)
        with patch.object(profiles.os, 'replace', side_effect=fail_dll):
            with self.assertRaises(OSError):
                installer.install(self.state, self.bundle, guard=lambda: None)
        self.assertFalse(profiles.status(self.state)['ready_to_launch'])
        self.assertTrue(profiles.recover(self.state, guard=lambda: None)['ready_to_launch'])
        self.assertEqual(settings.read_text(), '{"occult_form_memory":true}')
        self.assert_preserved()

    def test_running_game_cannot_replace_a_loaded_dll(self):
        before = test_profile.inventory(self.profile)
        with self.assertRaises(RuntimeError):
            installer.install(self.state, self.bundle, guard=lambda: (_ for _ in ()).throw(RuntimeError('game running')))
        self.assertEqual(test_profile.inventory(self.profile), before)
        self.assert_preserved()

    def test_candidate_replacement_preserves_exact_installed_cc_recipe(self):
        import test_cc_addons
        name = next(iter(test_cc_addons.ASSETS))
        cc = self.profile/'Mods'/'ApexTest'/name; cc.write_bytes(b'DBPF verified CC fixture')
        digest = sha256(cc)
        journal = json.loads(self.state.read_bytes())
        journal['artifacts'].append({'name': name, 'sha256': digest, 'source': str(cc),
                                    'test_addon': test_cc_addons.ADDON})
        write_json(self.state, journal)
        with patch.dict(test_cc_addons.ASSETS, {name: digest}):
            result = installer.install(self.state, self.bundle, guard=lambda: None)
        self.assertTrue(result['ready_to_launch']); self.assertEqual(cc.read_bytes(), b'DBPF verified CC fixture')
        self.assertTrue(any(row.get('test_addon') == test_cc_addons.ADDON
            for row in json.loads(self.state.read_bytes())['artifacts']))
        self.assert_preserved()

    def test_changed_cc_recipe_cannot_be_accepted_by_candidate_replacement(self):
        import test_cc_addons
        name = next(iter(test_cc_addons.ASSETS))
        cc = self.profile/'Mods'/'ApexTest'/name; cc.write_bytes(b'DBPF mismatched CC fixture')
        journal = json.loads(self.state.read_bytes())
        journal['artifacts'].append({'name': name, 'sha256': sha256(cc), 'source': str(cc),
                                    'test_addon': test_cc_addons.ADDON})
        write_json(self.state, journal)
        before = test_profile.inventory(self.profile)
        with self.assertRaisesRegex(ValueError, 'CC add-on recipe'):
            installer.install(self.state, self.bundle, guard=lambda: None)
        self.assertEqual(test_profile.inventory(self.profile), before); self.assert_preserved()


if __name__ == '__main__':
    unittest.main()
