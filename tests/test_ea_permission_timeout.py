from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import ea_permission


class EaPermissionTimeoutTests(unittest.TestCase):
    def test_certified_observation_only_timeout_can_use_one_native_fallback(self):
        error = subprocess.TimeoutExpired('uia', 15, output=b'{"phase":"observation-started"}\n')
        with patch.object(ea_permission.subprocess,'CREATE_NO_WINDOW',0,create=True), \
                patch.object(ea_permission.subprocess,'run',side_effect=error), \
                patch('ea_native_permission.acknowledge',return_value={'ok':True,'acknowledged':True}) as fallback:
            result=ea_permission.acknowledge(Path('evidence'))
        self.assertTrue(result['acknowledged']);fallback.assert_called_once()

    def test_invoke_intent_timeout_remains_unresolved_and_never_uses_fallback(self):
        error = subprocess.TimeoutExpired('uia', 15, output=b'{"phase":"observation-started"}\n{"phase":"invoke-intent"}\n')
        with patch.object(ea_permission.subprocess,'CREATE_NO_WINDOW',0,create=True), \
                patch.object(ea_permission.subprocess,'run',side_effect=error), \
                patch('ea_native_permission.acknowledge') as fallback:
            result=ea_permission.acknowledge(Path('evidence'))
        self.assertTrue(result['acknowledgement_unresolved']);fallback.assert_not_called()

    def test_completed_phase_markers_do_not_hide_successful_ack(self):
        completed=subprocess.CompletedProcess('uia',0,'{"phase":"observation-started"}\n{"phase":"invoke-intent"}\n{"ok":true,"acknowledged":true}\n')
        with patch.object(ea_permission.subprocess,'CREATE_NO_WINDOW',0,create=True), \
                patch.object(ea_permission.subprocess,'run',return_value=completed), \
                patch('ea_native_permission.acknowledge') as fallback:
            result=ea_permission.acknowledge(Path('evidence'))
        self.assertTrue(result['acknowledged']);fallback.assert_not_called()

    def test_ambiguous_uia_timeout_does_not_replay_via_native_fallback(self):
        with patch.object(ea_permission.subprocess,'CREATE_NO_WINDOW',0,create=True), \
                patch.object(ea_permission.subprocess,'run',side_effect=subprocess.TimeoutExpired('uia',15)) as run, \
                patch('ea_native_permission.acknowledge') as fallback:
            result=ea_permission.acknowledge(Path('evidence'))
        self.assertTrue(result['acknowledgement_unresolved'])
        self.assertFalse(result['acknowledged'])
        self.assertFalse(result['retry_safe'])
        self.assertFalse(result['windows_uac_approved'])
        run.assert_called_once()
        fallback.assert_not_called()
