import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import cli_identity_cache as cache


class IdentityBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name);self.state=root/'state.json';self.state.write_text('{}')
        self.profile=root/'test';self.mods=self.profile/'Mods';self.mods.mkdir(parents=True)
        self.part=self.mods/'item.package';self.part.write_bytes(b'valid')
        self.mock=patch.object(cache.reusable_profile,'load',return_value=(self.state,{'token':'token'},self.profile,root/'original'))
        self.mock.start();self.addCleanup(self.mock.stop);self.calls=0
    def full(self):
        self.calls+=1;return {'ready_to_launch':True}
    def test_cache_is_only_alive_within_one_batch(self):
        with cache.session(self.state):
            for _ in range(3):self.assertTrue(cache.validate(self.state,self.full)['ready_to_launch'])
        self.assertEqual(self.calls,1)
        with cache.session(self.state):cache.validate(self.state,self.full)
        self.assertEqual(self.calls,2)
        cache.validate(self.state,self.full);self.assertEqual(self.calls,3)
    def test_nested_native_status_and_submit_share_batch(self):
        with cache.session(self.state):
            cache.validate(self.state,self.full)
            with cache.session(self.state):cache.validate(self.state,self.full)
        self.assertEqual(self.calls,1)
    def test_same_size_edit_even_with_restored_mtime_invalidates_batch(self):
        with cache.session(self.state):
            cache.validate(self.state,self.full);before=self.part.stat()
            self.part.write_bytes(b'other');os.utime(self.part,ns=(before.st_atime_ns,before.st_mtime_ns))
            with self.assertRaises(ValueError):cache.validate(self.state,self.full)
        self.assertEqual(self.calls,1)
    def test_added_unknown_mod_and_removed_mod_are_both_rejected(self):
        for action in ('add','remove'):
            with self.subTest(action=action),cache.session(self.state):
                cache.validate(self.state,self.full)
                if action=='add':(self.mods/'unknown.package').write_bytes(b'new')
                else:self.part.unlink()
                with self.assertRaises(ValueError):cache.validate(self.state,self.full)
    def test_journal_change_invalidates_cached_artifacts(self):
        with cache.session(self.state):
            cache.validate(self.state,self.full);self.state.write_text('{"changed":true}')
            with self.assertRaises(ValueError):cache.validate(self.state,self.full)
    def test_profile_switch_and_failed_full_check_never_create_lease(self):
        with cache.session(self.state):
            with self.assertRaises(ValueError):
                with cache.session(self.state.with_name('another.json')):pass
            def fail():raise ValueError('Full content hash differs')
            with self.assertRaises(ValueError):cache.validate(self.state,fail)
            cache.validate(self.state,self.full)
        self.assertEqual(self.calls,1)
    def test_file_change_during_initial_full_hash_is_refused(self):
        with cache.session(self.state):
            def racing_check():self.part.write_bytes(b'changed');return self.full()
            with self.assertRaises(ValueError):cache.validate(self.state,racing_check)
