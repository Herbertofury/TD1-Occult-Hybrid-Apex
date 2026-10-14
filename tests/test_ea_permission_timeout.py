from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import ea_permission


class EaPermissionTimeoutTests(unittest.TestCase):
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
