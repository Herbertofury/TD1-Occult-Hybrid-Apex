import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import test_candidate_install as candidate_tests
import candidate_install
import reusable_profile as profiles
import test_addons
import test_profile
from source_manifest import sha256


class AddonTests(unittest.TestCase):
    setUp = candidate_tests.CandidateTests.setUp
    make_bundle = candidate_tests.CandidateTests.make_bundle
    assert_preserved = candidate_tests.CandidateTests.assert_preserved
    def fixture_archive(self):
        archive = self.root / 'mccc.zip'
        with zipfile.ZipFile(archive, 'w') as container:
            for name in test_addons.MEMBERS:
                container.writestr(name, b'DBPF addon' if name.endswith('.package') else b'PK addon')
        return archive

    def test_exact_recipe_survives_candidate_update_and_explicit_removal_preserves_settings(self):
        archive = self.fixture_archive()
        with patch.object(test_addons, 'MCCC_SHA256', sha256(archive)):
            result = test_addons.configure(self.state, archive, guard=lambda: None)
        self.assertTrue(result['ready_to_launch'])
        config = self.profile / 'Mods' / 'MCCC' / 'mc_settings.cfg'
        config.write_text('{"preserve":true}')
        result = candidate_install.install(self.state, self.bundle, guard=lambda: None)
        self.assertEqual(len(result['artifacts']), 10)
        self.assertEqual(config.read_text(), '{"preserve":true}')
        result = test_addons.configure(self.state, remove=True, guard=lambda: None)
        self.assertEqual(len(result['artifacts']), 6)
        self.assertTrue(result['ready_to_launch'])
        self.assertFalse(config.exists())
        recovery = json.loads((self.state.parent / 'artifact-recovery' / 'mccc-generated-data-latest.json').read_text())
        recovered = Path(recovery['files'][0]['recovery'])
        self.assertEqual(recovered.read_text(), '{"preserve":true}')
        self.assert_preserved()

    def test_wrong_archive_refuses_before_mod_writes(self):
        archive = self.fixture_archive()
        before = test_profile.inventory(self.profile)
        with self.assertRaisesRegex(ValueError, 'differs'):
            test_addons.configure(self.state, archive, guard=lambda: None)
        self.assertEqual(test_profile.inventory(self.profile), before)
        self.assert_preserved()

    def test_addon_install_interruption_recovers_full_exact_recipe(self):
        archive = self.fixture_archive()
        replace = profiles.os.replace
        def fail(source, target):
            if Path(target).name == 'mc_cas.ts4script':
                raise OSError('interrupted add-on install')
            return replace(source, target)
        with patch.object(test_addons, 'MCCC_SHA256', sha256(archive)), patch.object(profiles.os, 'replace', side_effect=fail):
            with self.assertRaises(OSError):
                test_addons.configure(self.state, archive, guard=lambda: None)
        self.assertFalse(profiles.status(self.state)['ready_to_launch'])
        self.assertTrue(profiles.recover(self.state, guard=lambda: None)['ready_to_launch'])
        self.assertEqual(len(profiles.load(self.state)[1]['artifacts']), 5)
        self.assert_preserved()
