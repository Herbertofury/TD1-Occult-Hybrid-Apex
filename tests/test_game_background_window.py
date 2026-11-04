from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from game_background_window import restore
import game_background_window as background
import game_focus


class Adapter:
    def __init__(self):
        self.pid=42;self.is_minimized=True;self.front=500;self.calls=[];self.accept=True
        self.rows=[dict(hwnd=12,pid=42,class_name='Canvas-verified',visible=True,width=1278,height=1376)]
    def windows(self,pid):return self.rows
    def owner(self,hwnd):return self.pid
    def minimized(self,hwnd):return self.is_minimized
    def foreground(self):return self.front
    def restore_without_activation(self,hwnd):
        self.calls.append(hwnd)
        if self.accept:self.is_minimized=False
        return self.accept


class BackgroundWindowTests(unittest.TestCase):
    def test_restores_only_own_minimized_window_without_foreground_request(self):
        a=Adapter();p=restore(42,a)
        self.assertTrue(p['ok']);self.assertTrue(p['foreground_unchanged'])
        self.assertTrue(p['no_focus_request']);self.assertFalse(p['input_sent'])
        self.assertEqual(a.calls,[12]);self.assertEqual(a.front,500)
    def test_already_restored_window_is_not_changed(self):
        a=Adapter();a.is_minimized=False
        self.assertTrue(restore(42,a)['ok']);self.assertEqual(a.calls,[])
    def test_foreign_ambiguous_or_missing_canvas_gets_no_action(self):
        for rows in ([],[dict(hwnd=12,pid=43,class_name='Canvas-wrong',visible=True)],
                     [dict(hwnd=12,pid=42,class_name='Other',visible=True)]):
            a=Adapter();a.rows=rows
            with self.assertRaises(ValueError):restore(42,a)
            self.assertEqual(a.calls,[])
        a=Adapter();a.rows*=2
        with self.assertRaises(ValueError):restore(42,a)
        self.assertEqual(a.calls,[])
    def test_owner_race_or_refusal_has_no_foreground_fallback(self):
        a=Adapter();a.pid=43
        with self.assertRaises(ValueError):restore(42,a)
        self.assertEqual(a.calls,[])
        a=Adapter();a.accept=False
        self.assertFalse(restore(42,a)['ok']);self.assertEqual(a.calls,[12])
    def test_foreground_change_stops_subsequent_actions(self):
        a=Adapter();original=a.restore_without_activation
        def changed(hwnd):
            result=original(hwnd);a.front=501;return result
        a.restore_without_activation=changed
        value=restore(42,a)
        self.assertFalse(value['ok']);self.assertFalse(value['foreground_unchanged'])
        self.assertEqual(a.calls,[12])

    def test_only_positive_os_refusal_can_request_the_fixed_no_focus_helper(self):
        failure=dict(ok=False,foreground_unchanged=True,restore_attempted=True,input_sent=False,
            message='Windows refused the no-activation restore; no fallback input.')
        worker=dict(ok=True,no_focus_request=True,foreground_unchanged=True,input_sent=False)
        helper=dict(ok=True,input_sent=False,worker_receipt_verified=True,worker={'background_restore':worker})
        with patch.object(background,'restore',return_value=failure), \
             patch.object(game_focus,'requires_elevated_input',return_value=True), \
             patch.object(game_focus,'elevate_once',return_value=helper) as launch, \
             patch.object(game_focus,'digest',return_value='a'*64):
            self.assertTrue(background.restore_for_capture(Path('state.json'),42)['ok'])
            self.assertEqual(launch.call_args.kwargs,{'background_restore':True})
        for changed in (dict(failure,foreground_unchanged=False),dict(failure,restore_attempted=False),
                        dict(failure,message='The game stayed minimized; no activation fallback.')):
            with patch.object(background,'restore',return_value=changed), \
                 patch.object(game_focus,'requires_elevated_input',return_value=True), \
                 patch.object(game_focus,'elevate_once') as launch:
                self.assertFalse(background.restore_for_capture(Path('state.json'),42)['ok'])
                launch.assert_not_called()
