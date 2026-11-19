import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core import runtime_profile as p


class FakeProfiler:
    def __init__(self):self.enabled=False;self.stops=0
    def enable(self):self.enabled=True
    def disable(self):self.enabled=False;self.stops+=1
    def getstats(self):
        return [SimpleNamespace(code='menu_test',callcount=4,reccallcount=0,inlinetime=.002,totaltime=.004)]


class ProfilingTests(unittest.TestCase):
    def setUp(self):
        p._ACTIVE=p._LAST=None
        self.backend=SimpleNamespace(_APEX_PROFILE_PULSE=None)
        self.now=10.;self.profiler=FakeProfiler()
    def clock(self):return self.now
    def start(self,**changes):
        argument=dict(operation='start',seconds=2,label='Live pie menu');argument.update(changes)
        return p.control(self.backend,argument,self.clock,lambda:self.profiler)
    def test_deadline_disables_without_second_command(self):
        self.start();self.assertTrue(self.profiler.enabled)
        self.now=11.;self.backend._APEX_PROFILE_PULSE();self.assertTrue(self.profiler.enabled)
        self.now=12.;self.backend._APEX_PROFILE_PULSE()
        self.assertFalse(self.profiler.enabled);self.assertIsNone(self.backend._APEX_PROFILE_PULSE)
        result=p.control(self.backend,dict(operation='status'),self.clock)
        self.assertEqual(result['top_self'][0]['self_ms'],2.);self.assertEqual(result['state'],'completed')
        self.assertFalse(result['appearance_written']);self.assertEqual(self.profiler.stops,1)
    def test_manual_stop_and_repeated_stop_do_not_replay(self):
        self.start();p.control(self.backend,dict(operation='stop'),self.clock)
        p.control(self.backend,dict(operation='stop'),self.clock);self.assertEqual(self.profiler.stops,1)
    def test_active_sample_cannot_be_restarted(self):
        self.start()
        with self.assertRaises(ValueError):self.start()
    def test_bad_duration_label_or_extra_field_refused(self):
        for changes in (dict(seconds=True),dict(seconds=0),dict(seconds=31),dict(label='\n'),dict(label='x'*81),dict(extra=True)):
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.start(**changes)
        self.assertIsNone(self.backend._APEX_PROFILE_PULSE)
    def test_failure_to_enable_leaves_no_tick_work(self):
        with patch.object(self.profiler,'enable',side_effect=RuntimeError('missing native profiler')):
            with self.assertRaises(RuntimeError):self.start()
        self.assertIsNone(p._ACTIVE);self.assertIsNone(self.backend._APEX_PROFILE_PULSE)
    def test_foreign_thread_cannot_stop_profile(self):
        self.start()
        with patch.object(p.threading,'get_ident',return_value=-1):
            with self.assertRaises(ValueError):p.control(self.backend,dict(operation='stop'),self.clock)
        self.assertTrue(self.profiler.enabled)
        p.control(self.backend,dict(operation='stop'),self.clock)
    def test_deadline_report_failure_does_not_escape_game_tick(self):
        self.start();self.now=12.
        with patch.object(self.profiler,'getstats',side_effect=RuntimeError('unavailable stats')):
            self.backend._APEX_PROFILE_PULSE()
        self.assertFalse(self.profiler.enabled);self.assertIsNone(self.backend._APEX_PROFILE_PULSE)
        result=p.control(self.backend,dict(operation='status'),self.clock)
        self.assertFalse(result['ok']);self.assertEqual(result['state'],'failed')
        self.assertEqual(result['error'],'unavailable stats')
    def test_foreign_deadline_pulse_retains_owned_stop_authority(self):
        self.start();self.now=12.
        with patch.object(p.threading,'get_ident',return_value=-1):
            self.backend._APEX_PROFILE_PULSE()
        self.assertTrue(self.profiler.enabled);self.assertIsNotNone(p._ACTIVE)
        self.backend._APEX_PROFILE_PULSE();self.assertFalse(self.profiler.enabled)
    def test_idle_does_not_import_or_construct_profiler(self):
        self.assertEqual(p.control(self.backend,dict(operation='status'),self.clock)['state'],'idle')
        self.assertIsNone(self.backend._APEX_PROFILE_PULSE)


if __name__=='__main__':unittest.main()
