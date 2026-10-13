from pathlib import Path
import sys,json,copy,tempfile,hashlib
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import switch_archive as api


class SwitchArchiveTests(unittest.TestCase):
    def setUp(self):
        self.fields={'__outfits__':{'kind':'protobuf','value':'CgQIARAA'},'physique':{'kind':'value','value':'native shape'}}
        self.pending=dict(schema=2,state='native-did-not-converge',runtime_pid=55,sim_id={'query':'returned-value','value':'11'},request_id='a'*32,
            native_operation_attempted=True,manager_identity_verified=True,source='16',target='1',
            stored_originals={'1':self.fields,'16':self.fields},desired_stored={'1':self.fields,'16':self.fields},
            active_original=self.fields,desired_active=self.fields,future_native_diagnostic={'opaque':'keep'})
        self.record=dict(bank={'1':self.fields,'16':self.fields},history=[],runtime_pid=55,switch_pending=self.pending)
        self.proof=dict(identity={'pid':55},operation='normal-exit-without-saving',save_requested=False,
            game_exit_verified=True,final_process_alive=False,save_files_unchanged_verified=True,
            requested_sim_id='11',requested_household_id='77',requested_save_guid='88',
            before_all_saves={'file':{'sha256':'unchanged'}},after_all_saves={'file':{'sha256':'unchanged'}})

    def test_live_save_unknown_pid_or_altered_preimage_never_retires_metadata(self):
        changes=[dict(final_process_alive=True),dict(save_requested=True),dict(requested_save_guid='89'),
            dict(after_all_saves={'file':{'sha256':'changed'}}),dict(identity={'pid':True})]
        for change in changes:
            with self.assertRaises(ValueError):api.validate(self.record,dict(self.proof,**change),'11','77','88')
        broken=copy.deepcopy(self.record);broken['switch_pending']['stored_originals']['1']['unexpected']={'kind':'value','value':0}
        with self.assertRaises(ValueError):api.validate(broken,self.proof,'11','77','88')

    def test_cas_intent_or_wrong_switch_epoch_cannot_be_cleared(self):
        for record in (dict(self.record,pending={'state':'captured'}),dict(self.record,cas_transaction={'phase':'recovery-required'}),
            dict(self.record,switch_pending=dict(self.pending,runtime_pid=56))):
            with self.assertRaises(ValueError):api.validate(record,self.proof,'11','77','88')

    def test_closed_archive_preserves_every_byte_without_certifying_or_replaying_bank(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);active=root/'active';original=root/'original';active.mkdir();original.mkdir()
            saves=active/'saves';saves.mkdir();save=saves/'Slot_00000002.save';save.write_bytes(b'native save')
            bank=active/'form_bank.json';bank.write_text(json.dumps(dict(schema=1,records={'88:11':self.record},future_bank_field='keep')))
            raw=bank.read_bytes();save_sha=hashlib.sha256(save.read_bytes()).hexdigest();bank_sha=hashlib.sha256(raw).hexdigest()
            state=root/'state.json';state.write_text('{}');output=root/'result.json'
            proof=dict(self.proof,identity={'pid':55,'test_token':'a'*32,'profile':str(active)},
                before_all_saves=api.all_save_files(active),after_all_saves=api.all_save_files(active))
            closure=root/'exit.json';closure.write_text(json.dumps(proof));closure_sha=hashlib.sha256(closure.read_bytes()).hexdigest()
            with patch.object(api.reusable_profile.legacy,'require_closed'),patch.object(api.reusable_profile,'load',return_value=(state,{'token':'a'*32},active,original)):
                result=api.archive(state,bank,bank_sha,closure,closure_sha,'11','77','88',2,save_sha,output)
            self.assertTrue(result['ok']);self.assertEqual(Path(result['preimage']).read_bytes(),raw)
            after=json.loads(bank.read_text());record=after['records']['88:11']
            self.assertIsNone(record['switch_pending']);self.assertEqual(record['runtime_pid'],55)
            self.assertEqual(record['bank'],self.record['bank']);self.assertEqual(after['future_bank_field'],'keep')
            retained=api.bank_history.resolve(bank,record['switch_history'][-1])
            self.assertEqual(retained['future_native_diagnostic'],{'opaque':'keep'})
            self.assertFalse(result['cas_completion_certified']);self.assertFalse(result['old_bank_replay_authorized'])
            self.assertEqual(save.read_bytes(),b'native save')
