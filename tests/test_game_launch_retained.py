"""A successful observed launch survives EA log rotation without guessed IDs."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import game_launch
from source_manifest import sha256
import test_game_launch as fixture


class RetainedLaunchTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        fixture.LaunchPlanTests.fixture(self, self.root,
            '<contentID>1011164</contentID><contentID>1015806</contentID>')
        self.state = self.root / 'state.json'
        self.proof = self.root / 'successful-launch.json'
        self.prior = dict(ok=True, launched=True, mode='ea-client-handoff',
            url='origin2://game/launch?offerIds=1011164&autoDownload=0',
            account_launch_identity=dict(offer_id='OFB-EAST:fixture',content_id='1011164',
                executable=str(self.root/'Game/Bin/TS4_Launcher_x64.exe'),
                evidence='Successful EA Client Play request for this exact installation',
                record_sha256='a'*64,log='current-EA.log'),
            observation=dict(process_started=True,pid=44,executable=str(self.root/'Game/Bin/TS4_x64.exe')),
            executable_sha256=sha256(self.root/'Game/Bin/TS4_x64.exe'),
            installer_manifest_sha256=sha256(self.root/'__Installer/installerdata.xml'))
        self.write()

    def write(self):
        self.proof.write_text(json.dumps(self.prior),encoding='utf-8')

    def remember(self):
        return game_launch.retained_account_identity(self.root,self.state,self.proof,sha256(self.proof))

    def test_exact_account_identity_is_retained_and_used_after_log_rotation(self):
        self.assertEqual(self.remember()['content_id'],'1011164')
        with patch.object(game_launch.test_profile,'status',return_value={'ready_to_launch':True}), \
                patch.object(game_launch,'account_launch_identity',side_effect=ValueError('rotated')):
            plan=game_launch.launch_plan(self.root,self.state)
        self.assertIn('offerIds=1011164&',plan['url'])
        self.assertFalse(plan['launched'])
        self.assertEqual(plan['account_launch_identity']['retained_proof_sha256'],sha256(self.proof))

    def test_current_successful_client_play_takes_precedence_over_history(self):
        self.remember()
        fresh=dict(self.prior['account_launch_identity'],content_id='1015806')
        with patch.object(game_launch.test_profile,'status',return_value={'ready_to_launch':True}), \
                patch.object(game_launch,'account_launch_identity',return_value=fresh):
            plan=game_launch.launch_plan(self.root,self.state)
        self.assertIn('offerIds=1015806&',plan['url'])

    def test_changed_executable_manifest_or_evidence_refuses_cached_identity(self):
        for kind in ('executable','manifest','proof'):
            with self.subTest(kind=kind):
                self.write(); self.remember()
                target={'executable':self.root/'Game/Bin/TS4_x64.exe',
                        'manifest':self.root/'__Installer/installerdata.xml','proof':self.proof}[kind]
                saved=target.read_bytes();target.write_bytes(saved+b'changed')
                with self.assertRaises(ValueError):
                    game_launch.retained_account_identity(self.root,self.state)
                target.write_bytes(saved)

    def test_unobserved_foreign_installation_and_truthy_receipts_never_establish_identity(self):
        original=copy.deepcopy(self.prior)
        for kind in ('ok','launched','started','pid','path','content','record','url'):
            self.prior=copy.deepcopy(original)
            if kind in ('ok','launched'):self.prior[kind]=1
            elif kind=='started':self.prior['observation']['process_started']=False
            elif kind=='pid':self.prior['observation']['pid']=True
            elif kind=='path':self.prior['observation']['executable']='other/TS4_x64.exe'
            elif kind=='content':self.prior['account_launch_identity']['content_id']='invalid'
            elif kind=='record':self.prior['account_launch_identity']['record_sha256']='unverified'
            else:self.prior['url']='origin2://game/launch?offerIds=guessed'
            self.write()
            with self.subTest(kind=kind),self.assertRaises(ValueError):self.remember()

    def test_unknown_historical_sku_still_fails_current_installer_check(self):
        self.prior['account_launch_identity']['content_id']='99999'
        self.prior['url']='origin2://game/launch?offerIds=99999&autoDownload=0';self.write();self.remember()
        with patch.object(game_launch.test_profile,'status',return_value={'ready_to_launch':True}), \
                patch.object(game_launch,'account_launch_identity',side_effect=ValueError('rotated')), \
                self.assertRaisesRegex(ValueError,'not in'):
            game_launch.launch_plan(self.root,self.state)

    def test_requested_other_offer_is_not_substituted_after_rotation(self):
        self.remember()
        with patch.object(game_launch.test_profile,'status',return_value={'ready_to_launch':True}), \
                patch.object(game_launch,'account_launch_identity',side_effect=ValueError('rotated')), \
                self.assertRaisesRegex(ValueError,'differs'):
            game_launch.launch_plan(self.root,self.state,'OFB-EAST:other')

if __name__=='__main__':unittest.main()
