import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import launch_preferences as preferences


class RememberedLaunchTests(unittest.TestCase):
    def test_preference_never_rebinds_another_account_or_installation(self):
        original = dict(offer_id='OFB-ONE',content_id='1015806',executable='C:/Game/Launcher.exe')
        self.assertTrue(preferences.bound(original,dict(original)))
        for field in original:
            changed=dict(original);changed[field]='other'
            self.assertFalse(preferences.bound(original,changed))

    def test_missing_preference_retains_normal_launcher_route(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertFalse(preferences.enabled(Path(directory)/'state.json',{}))

    def test_modified_or_differently_owned_evidence_cannot_enable_route(self):
        account=dict(offer_id='OFB-ONE',content_id='1015806',executable='C:/Game/Launcher.exe')
        with tempfile.TemporaryDirectory() as directory:
            state=Path(directory)/'state.json'
            preference=dict(schema=1,mode='normal-uac-one-shot',receipt='ea-broker-'+'a'*32+'.receipt.json',
                            receipt_sha256='b'*64,**account)
            (state.parent/preferences.NAME).write_text(json.dumps(preference),encoding='utf-8')
            with patch.object(preferences,'successful_receipt',side_effect=ValueError('evidence changed')):
                with self.assertRaisesRegex(ValueError,'evidence changed'):preferences.enabled(state,account)
            with patch.object(preferences,'successful_receipt',return_value=(Path('receipt'),dict(account,content_id='other'))):
                with self.assertRaisesRegex(ValueError,'another launch'):preferences.enabled(state,account)
            with patch.object(preferences,'successful_receipt',return_value=(Path('receipt'),account)):
                self.assertTrue(preferences.enabled(state,account))
