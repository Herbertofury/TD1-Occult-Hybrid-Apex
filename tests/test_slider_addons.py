import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import owner_slider_addons as sliders
import test_reusable_profile as fixtures
from source_manifest import sha256


class SliderAddonTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.ReusableTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.adopt();self.source=self.f.original/'Mods'/'Sliders And Presets';self.source.mkdir()
        self.asset=self.source/'[Author] slider.package';self.asset.write_bytes(b'DBPF source test fixture')
    def test_copies_only_to_existing_profile_preserves_original_and_save(self):
        before=sha256(self.asset);save=sha256(self.f.profile/'saves'/'test.save')
        result=sliders.install(self.f.state,self.f.guard)
        self.assertTrue(result['ok']);self.assertEqual(result['added'],1)
        self.assertEqual(sha256(self.asset),before);self.assertEqual(sha256(self.f.profile/'saves'/'test.save'),save)
        target=self.f.profile/'Mods'/'ApexTest'/self.asset.name
        self.assertEqual(sha256(target),before)
        self.assertEqual(sliders.install(self.f.state,self.f.guard)['added'],0)
    def test_identical_existing_other_recipe_is_reused(self):
        import reusable_profile as profiles
        profiles.install(self.f.state,[self.f.artifact,self.asset],self.f.guard)
        self.assertEqual(sliders.install(self.f.state,self.f.guard)['added'],0)
    def test_different_target_hash_or_duplicate_filename_refuses_before_copying(self):
        nested=self.source/'other';nested.mkdir();(nested/self.asset.name).write_bytes(b'DBPF different')
        with self.assertRaisesRegex(ValueError,'Duplicate'):sliders.plan(self.f.state)
        self.assertFalse((self.f.profile/'Mods'/'ApexTest'/self.asset.name).exists())
    def test_non_package_and_changed_source_refuse_without_original_writes(self):
        (self.source/'other.txt').write_text('untouched',encoding='utf-8')
        with self.assertRaises(ValueError):sliders.install(self.f.state,self.f.guard)
        self.assertEqual(self.asset.read_bytes(),b'DBPF source test fixture')
    def test_running_game_guard_prevents_even_a_pending_install(self):
        def running():raise RuntimeError('running')
        before=self.f.state.read_bytes()
        with self.assertRaises(RuntimeError):sliders.install(self.f.state,running)
        self.assertEqual(self.f.state.read_bytes(),before)


if __name__=='__main__':unittest.main()
