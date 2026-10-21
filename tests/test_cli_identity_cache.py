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
    def test_each_enumerated_file_retains_real_device_and_file_identity(self):
        expected=self.part.lstat()
        rows={row[0]:row[1] for row in cache.stamp(self.state)}
        actual=rows[str(self.part.relative_to(self.profile))]
        self.assertEqual(actual[:2],(expected.st_dev,expected.st_ino))
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
    def test_rapid_large_file_rewrites_with_restored_mtime_always_invalidate(self):
        self.part.write_bytes(b'a' * (128 * 1024))
        for index in range(8):
            with self.subTest(index=index),cache.session(self.state):
                cache.validate(self.state,self.full);before=self.part.stat()
                self.part.write_bytes(bytes([index+1]) * before.st_size)
                os.utime(self.part,ns=(before.st_atime_ns,before.st_mtime_ns))
                with self.assertRaises(ValueError):cache.validate(self.state,self.full)
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
    def test_normal_profile_cache_and_save_writes_do_not_invalidate_mod_inventory(self):
        with cache.session(self.state):
            cache.validate(self.state,self.full)
            (self.profile/'clientDB.package').write_bytes(b'native user-data cache')
            (self.profile/'saves').mkdir()
            (self.profile/'saves'/'Slot_00000002.save').write_bytes(b'disposable save')
            cache.validate(self.state,self.full)
        self.assertEqual(self.calls,1)
    def test_replaced_profile_directory_still_invalidates_batch_even_with_same_mod_bytes(self):
        with cache.session(self.state):
            cache.validate(self.state,self.full)
            self.profile.rename(self.profile.with_name('retained-test-profile'))
            self.mods.mkdir(parents=True);self.part.write_bytes(b'valid')
            with self.assertRaises(ValueError):cache.validate(self.state,self.full)
    def test_known_mccc_log_creation_rotation_and_write_do_not_expire_artifacts(self):
        mccc=self.mods/'MCCC';mccc.mkdir()
        with cache.session(self.state):
            cache.validate(self.state,self.full)
            log=mccc/'mc_cmd_center.log';log.write_text('runtime entry')
            cache.validate(self.state,self.full)
            log.write_text('another native runtime entry')
            cache.validate(self.state,self.full)
            log.unlink();log.write_text('rotated diagnostic')
            (mccc/'mc_lastexception.html').write_text('diagnostic only')
            cache.validate(self.state,self.full)
        self.assertEqual(self.calls,1)
    def test_unknown_logs_settings_and_new_executables_still_invalidate(self):
        mccc=self.mods/'MCCC';mccc.mkdir()
        for filename in ('unknown.log','mc_settings.cfg','mc_cmd_center.log.ts4script'):
            with self.subTest(filename=filename),cache.session(self.state):
                cache.validate(self.state,self.full)
                (mccc/filename).write_text('changed')
                with self.assertRaises(ValueError):cache.validate(self.state,self.full)
    def test_runtime_log_name_cannot_hide_a_directory_or_reparse_point(self):
        mccc=self.mods/'MCCC';mccc.mkdir();log=mccc/'mc_cmd_center.log'
        log.mkdir()
        with self.assertRaisesRegex(ValueError,'not an ordinary file'):cache.stamp(self.state)
    def test_pinned_artifact_using_log_name_remains_content_checked(self):
        mccc=self.mods/'MCCC';mccc.mkdir();log=mccc/'mc_cmd_center.log';log.write_bytes(b'first')
        self.mock.stop()
        with patch.object(cache.reusable_profile,'load',return_value=(self.state,
                {'token':'token','artifacts':[{'relative':'MCCC/mc_cmd_center.log'}]},self.profile,self.profile.parent/'original')):
            with cache.session(self.state):
                cache.validate(self.state,self.full);log.write_bytes(b'other')
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
