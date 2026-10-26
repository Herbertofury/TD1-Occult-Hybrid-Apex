"""Synthetic guarded-journal integration; never touches the actual game profiles."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import cas_resource_catalog as catalog
import reusable_profile as profiles
import test_cc_addons as addons
import test_profile
from source_manifest import sha256, write_json


class CCAddonTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.original = self.root / profiles.PROTECTED_NAME
        (self.original / 'saves').mkdir(parents=True)
        (self.original / 'saves' / 'precious.save').write_bytes(b'protected fixture')
        self.original_before = test_profile.inventory(self.original)
        self.profile = self.root / 'The Sims 4'
        (self.profile / 'Mods' / 'Apex').mkdir(parents=True)
        (self.profile / 'Mods' / 'ApexTest').mkdir()
        (self.profile / 'saves').mkdir()
        (self.profile / 'Tray').mkdir()
        (self.profile / 'saves' / 'Slot_00000002.save').write_bytes(b'certified disposable save')
        (self.profile / 'saves' / 'Slot_00000002.save.ver0').write_bytes(b'disposable backup')
        self.state = self.root / 'work' / 'state.json'
        self.state.parent.mkdir()
        core = self.state.parent / 'core.ts4script'
        core.write_bytes(b'PK\x03\x04 synthetic A0 core')
        old = self.state.parent / 'existing.package'
        old.write_bytes(b'DBPF pre-existing artifact')
        (self.profile / 'Mods' / 'Apex' / 'ApexOccultHybrid.ts4script').write_bytes(core.read_bytes())
        (self.profile / 'Mods' / 'ApexTest' / 'existing.package').write_bytes(old.read_bytes())
        self.artifacts = [
            {'name': 'ApexOccultHybrid.ts4script', 'relative': 'Apex/ApexOccultHybrid.ts4script',
             'sha256': sha256(core), 'source': str(core), 'custom_seal_field': 'preserve'},
            {'name': 'existing.package', 'sha256': sha256(old), 'source': str(old)},
        ]
        self.data = {'schema': 2, 'mode': 'reusable-test-only', 'phase': 'active',
                     'token': 'a' * 32, 'profile': str(self.profile),
                     'protected_original': str(self.original), 'artifacts': self.artifacts,
                     'generation': 7, 'bundle': {'sha256': 'b' * 64, 'identity': 'keep'}}
        write_json(self.state, self.data)
        write_json(self.profile / test_profile.MARKER, {'token': 'a' * 32, 'disposable': True})
        self.cache = self.state.parent / 'cas-resource-cache'
        (self.cache / 'packages').mkdir(parents=True)
        items, assets = [], {}
        for name in ['[Creator] Original Arm.package', 'Freckles Exact.package', 'Jewelry — Original.package']:
            raw = ('DBPF fixture CC ' + name).encode('utf-8')
            digest = catalog.digest(raw)
            copy = self.cache / 'packages' / (digest + '.package')
            copy.write_bytes(raw)
            assets[name] = digest
            items.append({'original_filename': name, 'sha256': digest,
                          'sealed_copy': str(copy), 'bytes': len(raw)})
        inventory = {'schema': 1, 'operation': 'read-only-cc-candidate-inventory', 'items': items}
        self.inventory = self.cache / 'cc-candidate-inventory.json'
        write_json(self.inventory, inventory)
        for owner, field, value in [(catalog, 'CACHE_ROOT', self.cache), (addons, 'ASSETS', assets),
                                     (addons, 'INVENTORY_SHA256', sha256(self.inventory)),
                                     (addons, 'SCRIPT_SHA256', sha256(core))]:
            patcher = patch.object(owner, field, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.before_saves = addons.save_hashes(self.profile)
        self.guard = lambda: None

    def assert_original_unchanged(self):
        self.assertEqual(test_profile.inventory(self.original), self.original_before)

    def test_plan_is_read_only_and_preserves_original_asset_basenames(self):
        before = test_profile.inventory(self.profile)
        journal = self.state.read_bytes()
        result = addons.plan(self.state)
        self.assertEqual(result['profile_writes'], 0)
        self.assertEqual(len(result['additions']), 3)
        for row in result['additions']:
            self.assertEqual(row['relative'], 'ApexTest/' + row['name'])
            self.assertEqual(Path(row['source']).parent, self.cache / 'packages')
        self.assertEqual(self.state.read_bytes(), journal)
        self.assertEqual(test_profile.inventory(self.profile), before)
        self.assert_original_unchanged()

    def test_cli_proof_output_cannot_overwrite_its_reusable_journal(self):
        before = self.state.read_bytes()
        with self.assertRaisesRegex(ValueError, 'replace the reusable profile journal'):
            addons.main(['--state', str(self.state), '--output', str(self.state)])
        self.assertEqual(self.state.read_bytes(), before)
        self.assert_original_unchanged()

    def test_install_merges_all_records_and_preserves_bundle_token_script_and_saves(self):
        result = addons.install(self.state, self.guard)
        self.assertTrue(result['ready_to_launch'])
        self.assertTrue(result['existing_artifacts_preserved_verified'])
        self.assertTrue(result['candidate_seal_preserved_verified'])
        self.assertTrue(result['save_files_unchanged_verified'])
        self.assertFalse(result['save_requested'])
        after = json.loads(self.state.read_text())
        self.assertEqual(after['artifacts'][:2], self.artifacts)
        self.assertEqual(after['bundle'], self.data['bundle'])
        self.assertEqual(after['token'], self.data['token'])
        self.assertEqual(after['generation'], 8)
        self.assertEqual(len(after['artifacts']), 5)
        self.assertEqual(addons.save_hashes(self.profile), self.before_saves)
        for row in result['additions']:
            self.assertEqual(sha256(self.profile / 'Mods' / row['relative']), row['sha256'])
        self.assert_original_unchanged()

    def test_repeat_install_is_idempotent_without_rewriting_generation_or_save(self):
        addons.install(self.state, self.guard)
        state = self.state.read_bytes()
        profile = test_profile.inventory(self.profile)
        result = addons.install(self.state, self.guard)
        self.assertTrue(result['already_installed'])
        self.assertEqual(result['additions'], [])
        self.assertEqual(self.state.read_bytes(), state)
        self.assertEqual(test_profile.inventory(self.profile), profile)
        self.assert_original_unchanged()

    def test_running_game_guard_refuses_before_any_profile_or_journal_write(self):
        def running():
            raise RuntimeError('game running')
        state, before = self.state.read_bytes(), test_profile.inventory(self.profile)
        with self.assertRaisesRegex(RuntimeError, 'game running'):
            addons.install(self.state, running)
        self.assertEqual(self.state.read_bytes(), state)
        self.assertEqual(test_profile.inventory(self.profile), before)
        self.assertFalse((self.state.parent / 'artifact-recovery').exists())
        self.assert_original_unchanged()

    def test_unknown_or_changed_existing_mod_and_wrong_script_are_refused(self):
        unknown = self.profile / 'Mods' / 'unexpected.package'
        unknown.write_bytes(b'DBPF unknown')
        with self.assertRaisesRegex(ValueError, 'unchanged marked'):
            addons.plan(self.state)
        unknown.unlink()
        with patch.object(addons, 'SCRIPT_SHA256', 'c' * 64):
            with self.assertRaisesRegex(ValueError, 'sealed A0'):
                addons.plan(self.state)
        self.assertEqual(addons.save_hashes(self.profile), self.before_saves)
        self.assert_original_unchanged()

    def test_changed_inventory_or_sealed_asset_is_refused_without_install(self):
        original = self.inventory.read_bytes()
        self.inventory.write_bytes(original + b' ')
        with self.assertRaisesRegex(ValueError, 'inventory hash'):
            addons.plan(self.state)
        self.inventory.write_bytes(original)
        item = json.loads(original)['items'][0]
        Path(item['sealed_copy']).write_bytes(b'DBPF changed CC')
        with self.assertRaisesRegex(ValueError, 'copy hash/size'):
            addons.plan(self.state)
        self.assertEqual(addons.save_hashes(self.profile), self.before_saves)
        self.assert_original_unchanged()

    def test_even_repinned_inventory_cannot_redirect_copy_into_protected_original(self):
        payload = json.loads(self.inventory.read_text())
        payload['items'][0]['sealed_copy'] = str(self.original / 'saves' / 'precious.save')
        write_json(self.inventory, payload)
        with patch.object(addons, 'INVENTORY_SHA256', sha256(self.inventory)):
            with self.assertRaisesRegex(ValueError, 'independent sealed'):
                addons.plan(self.state)
        self.assert_original_unchanged()

    def test_owned_target_collision_cannot_replace_an_existing_unrelated_artifact(self):
        name = next(iter(addons.ASSETS))
        path = self.profile / 'Mods' / 'ApexTest' / name
        path.write_bytes(b'DBPF unrelated owned artifact')
        self.data['artifacts'].append({'name': name, 'sha256': sha256(path), 'source': str(path)})
        write_json(self.state, self.data)
        before = self.state.read_bytes()
        with self.assertRaisesRegex(ValueError, 'collides'):
            addons.install(self.state, self.guard)
        self.assertEqual(self.state.read_bytes(), before)
        self.assertEqual(path.read_bytes(), b'DBPF unrelated owned artifact')
        self.assert_original_unchanged()


if __name__ == '__main__':
    unittest.main()
