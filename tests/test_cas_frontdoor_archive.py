import copy,json,sys,threading
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from test_form_bank_seal import SealFixture,SIM,HH,GUID
from test_cas_bank_transaction import reset_receiver_process
from apex_core import cas_bank_transaction as receiver
from apex_core.form_bank_seal import _hash
import cas_frontdoor_archive as tool
from source_manifest import write_json,sha256


class FrontdoorArchiveTests(SealFixture):
    def setUp(self):
        super().setUp();reset_receiver_process()
        self.addCleanup(reset_receiver_process)
        self.backend._APEX_GAME_THREAD_IDENT=threading.current_thread().ident
        self.backend._get_sim_info_by_id=lambda _:self.sim
        self.prior=self.identity['pid']-1;intent='c'*32
        with patch.object(receiver.os,'getpid',return_value=self.prior):
            checkpoint=receiver.begin(self.backend,self.sim)
            receiver.mark_entry_submitted(self.backend,self.sim,checkpoint['expected_pending_sha256'],intent)
        self.data=json.loads(self.bank_path.read_text(encoding='utf-8'))
        raw=self.data['records'][self.key]['pending']['original_owners']
        snap=dict(self.live(),sim={'id':SIM,'form_appearances':[
            {'flags':int(lane),'appearance':{'typed_payload':fields}} for lane,fields in raw['stored'].items()],
            'full_appearance':{'typed_payload':raw['active']['fields']}})
        self.cold=dict(ok=True,save_submitted=False,identity=self.identity,snapshots={SIM:copy.deepcopy(snap)})
        self.entry=dict(schema=1,stage='native-command-returned',full_household=True,native_appearance_written=False,
            id=intent,household_id=HH,roster_sim_ids=[SIM],members=[dict(sim_id=SIM,checkpoint=checkpoint,
                owner_observation={'original_owner':dict(complete=True,original_sim_id=SIM,household_id=HH,
                    runtime_pid=self.prior,save_guid=GUID)})])

    def test_preparation_is_read_only_and_checks_complete_independent_owners(self):
        before=copy.deepcopy(self.data)
        planned,held,pid,guid=tool.prepare(self.entry,self.data,self.cold)
        self.assertEqual(self.data,before);self.assertEqual(planned,before)
        self.assertEqual(set(held),{self.key});self.assertEqual((pid,guid),(self.prior,GUID))
        self.cold['snapshots'][SIM]['sim']['full_appearance']['typed_payload']['physique']='wrong'
        with self.assertRaisesRegex(ValueError,'appearances differ'):tool.prepare(self.entry,self.data,self.cold)
        self.assertEqual(self.data,before)

    def test_missing_member_changed_checkpoint_or_wrong_runtime_refuses(self):
        variants=[]
        value=copy.deepcopy(self.entry);value['roster_sim_ids'].append('999');variants.append(value)
        value=copy.deepcopy(self.entry);value['members'][0]['checkpoint']['checkpoint_sha256']='f'*64;variants.append(value)
        value=copy.deepcopy(self.entry);value['stage']='native-submit-intent';variants.append(value)
        value=copy.deepcopy(self.entry);value['members'][0]['owner_observation']['original_owner']['runtime_pid']=self.identity['pid'];variants.append(value)
        for value in variants:
            with self.subTest(value=value['stage']),self.assertRaises(ValueError):tool.prepare(value,self.data,self.cold)

    def test_observed_or_native_write_transaction_cannot_be_archived(self):
        for name,value in (('phase','observed'),('native_write_attempted',True)):
            data=copy.deepcopy(self.data);data['records'][self.key]['cas_transaction'][name]=value
            with self.subTest(name=name),self.assertRaises(ValueError):tool.prepare(self.entry,data,self.cold)

    def test_atomic_archival_preserves_bank_originals_save_and_all_other_records(self):
        entry=self.root/'source-entry.json';cold=self.root/'cold.json';out=self.root/'archive.json'
        write_json(entry,self.entry);write_json(cold,self.cold)
        before=self.bank_path.read_bytes();save=self.slot.read_bytes()
        with patch.object(tool.reusable_profile,'load',return_value=(self.root/'state.json',
                {'token':self.identity['test_token']},self.profile,self.protected)),\
                patch.object(tool.reusable_profile.legacy,'require_closed') as closed,\
                patch.object(tool,'process_alive',return_value=False):
            result=tool.archive(self.root/'state.json',entry,sha256(entry),cold,sha256(cold),2,
                self.target['expected_save_sha256'],out)
        self.assertTrue(result['ok']);self.assertTrue(result['bank_lanes_unchanged'])
        self.assertFalse(result['appearance_mutated']);self.assertFalse(result['save_written'])
        self.assertGreaterEqual(closed.call_count,2)
        self.assertEqual((self.root/'archive-bank-before.json').read_bytes(),before)
        after=json.loads(self.bank_path.read_text(encoding='utf-8'))['records'][self.key]
        self.assertIsNone(after['pending']);self.assertIsNone(after['cas_transaction'])
        self.assertEqual(after['failed_history'][-1]['pending'],self.data['records'][self.key]['pending'])
        self.assertEqual(self.slot.read_bytes(),save)
