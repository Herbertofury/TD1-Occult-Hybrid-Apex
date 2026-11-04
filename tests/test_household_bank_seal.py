import copy
import hashlib
import json
import threading
from types import SimpleNamespace as Obj
from unittest.mock import patch

from test_form_bank_seal import SealFixture, SIM, HH, GUID
from apex_core import form_bank_seal as seal, form_appearance as appearance
from apex_core import lifestate_forms as forms


class HouseholdBankSealTests(SealFixture):
    def setUp(self):
        super().setUp()
        self.sims=[self.sim]
        template=copy.deepcopy(self.bank['records'][self.key])
        for index in (1,2):
            member=copy.deepcopy(self.sim);member.id=int(SIM)+index
            for kind,owner in member.occult_tracker._sim_info_map.items():
                owner.id+=10000*index;owner.physique='member-'+str(index)+'-form-'+str(kind)
            member.physique=member.occult_tracker._sim_info_map[64].physique
            member.occult_tracker.sim_info=member;member.occult_tracker._sim_info=member
            row=copy.deepcopy(template)
            row['bank']={str(kind):appearance.packed(self.backend,owner)
                for kind,owner in member.occult_tracker._sim_info_map.items()}
            self.bank['records'][GUID+':'+str(member.id)]=row;self.sims.append(member)
        self.bank_path.write_text(json.dumps(self.bank))
        self.backend.services.active_household=lambda:Obj(id=int(HH),sim_info_gen=lambda:iter(self.sims))
        self.backend._ensure_human_form=lambda tracker:tracker._sim_info_map.get(1)
        self.backend._ensure_form=lambda tracker,kind,**kwargs:tracker._sim_info_map.get(kind)
        def snapshot(_backend,member,*args,**kwargs):
            row=self.live();row['sim']['id']=str(member.id);return row
        self.enterContext(patch('apex_core.test_driver.snapshot',side_effect=snapshot))

    def finish(self,receipt):
        seal.submitted(self.backend,self.sim,receipt,True)
        self.slot.write_bytes(b'one native household save')
        digest=hashlib.sha256(self.slot.read_bytes()).hexdigest()
        return seal.complete_save(self.backend,self.sim,dict(intent_id=receipt['intent_id'],expected_save_sha256=digest))

    def test_one_save_seals_three_distinct_members_with_one_atomic_write_per_phase(self):
        bank_before=self.bank_path.read_bytes()
        with patch.object(seal,'_write',wraps=seal._write) as write:
            receipt=self.begin()
            self.assertEqual(receipt['household_member_count'],3)
            self.assertEqual(receipt['appearance_bank_count'],3)
            self.assertEqual(write.call_count,1)
            result=self.finish(receipt)
            self.assertEqual(write.call_count,3)
        rows=seal._store(self.path)['records']
        self.assertEqual(set(result['household_seals']),set(self.bank['records']))
        self.assertEqual({row['state'] for row in rows.values()},{'sealed'})
        self.assertEqual(len({row['seal_sha256'] for row in rows.values()}),3)
        self.assertEqual(len({row['file_sha256'] for row in rows.values()}),1)
        self.assertEqual(self.bank_path.read_bytes(),bank_before)
        self.assertEqual(self.writes,[])

    def test_bad_third_member_does_not_leave_first_two_save_intents(self):
        self.sims[-1].occult_tracker._sim_info_map[2].physique='unreviewed native edit'
        bank_before=self.bank_path.read_bytes()
        with self.assertRaisesRegex(ValueError,'differs from bank'):
            self.begin()
        self.assertFalse(self.path.exists())
        self.assertEqual(self.bank_path.read_bytes(),bank_before)
        self.assertEqual(self.writes,[])

    def test_changed_member_or_roster_cannot_partially_seal_a_completed_file(self):
        for damage in ('bank','roster'):
            with self.subTest(damage=damage):
                if self.path.exists():self.path.unlink()
                self.bank_path.write_text(json.dumps(self.bank))
                self.backend.services.active_household=lambda:Obj(id=int(HH),sim_info_gen=lambda:iter(self.sims))
                receipt=self.begin();seal.submitted(self.backend,self.sim,receipt,True)
                self.slot.write_bytes(('native save '+damage).encode())
                if damage=='bank':
                    data=json.loads(self.bank_path.read_text())
                    data['records'][GUID+':'+str(self.sims[-1].id)]['bank']['2']['physique']=appearance.encode('later edit')
                    self.bank_path.write_text(json.dumps(data))
                else:
                    self.backend.services.active_household=lambda:Obj(id=int(HH),sim_info_gen=lambda:iter(self.sims[:-1]))
                before=self.path.read_bytes()
                with self.assertRaises(ValueError):
                    seal.complete_save(self.backend,self.sim,dict(intent_id=receipt['intent_id'],
                        expected_save_sha256=hashlib.sha256(self.slot.read_bytes()).hexdigest()))
                self.assertEqual(self.path.read_bytes(),before)
                self.assertEqual({row['state'] for row in seal._store(self.path)['records'].values()},{'save-submitted'})
                self.assertEqual(self.writes,[])

    def test_selected_sim_without_a_bank_does_not_skip_other_household_banks(self):
        del self.bank['records'][self.key];self.bank_path.write_text(json.dumps(self.bank))
        receipt=self.begin();self.assertNotEqual(receipt['primary_key'],self.key)
        self.assertEqual(receipt['household_member_count'],3)
        self.assertEqual(receipt['appearance_bank_count'],2)
        result=self.finish(receipt)
        self.assertEqual(set(result['household_seals']),set(self.bank['records']))
        self.assertEqual(self.writes,[])

    def test_each_saved_member_can_reconcile_after_reload_without_invalidating_the_others(self):
        certified=self.finish(self.begin());bank_before=self.bank_path.read_bytes()
        self.identity['pid']+=1
        for member in self.sims:seal.note_loaded(member.occult_tracker)
        for member in (self.sims[2],self.sims[0],self.sims[1]):
            key=GUID+':'+str(member.id)
            result=seal.reconcile(self.backend,member,dict(seal_sha256=certified['household_seals'][key]))
            self.assertEqual(result['state'],'reconciled')
            row=json.loads(self.bank_path.read_text())['records'][key]
            self.assertTrue(seal.current_runtime_bank_verified(self.backend,member,row))
        self.assertEqual(self.bank_path.read_bytes(),bank_before)
        self.assertEqual(self.writes,[])
        self.assertEqual({row['state'] for row in seal._store(self.path)['records'].values()},{'reconciled'})

    def test_saved_named_ghosts_reopen_independently_for_every_member(self):
        self.backend._APEX_GAME_THREAD_IDENT=threading.current_thread().ident
        self.backend._get_sim_info_by_id=lambda sid:next((member for member in self.sims if str(member.id)==sid),None)
        saved={}
        for member in self.sims:
            key=GUID+':'+str(member.id);record=self.bank['records'][key]
            fields=copy.deepcopy(record['bank']['1']);fields['physique']=appearance.encode('Ghost-'+str(member.id))
            ghost=dict(id='ghost_ghost',label='Ghost',lifestate='GHOST',base_form=1,
                fields=fields,appearance_sha256=appearance.fingerprint(fields)['appearance_sha256'])
            saved[key]=dict(schema=1,forms={'ghost_ghost':ghost},active={})
            record.update(lifestate_forms=copy.deepcopy(saved[key]),lifestate_runtime_pid=self.identity['pid'])
            forms._bind_runtime(record,member)
        self.bank_path.write_text(json.dumps(self.bank));self.finish(self.begin())
        seals_before=self.path.read_bytes();self.identity['pid']+=1
        for member in self.sims:seal.note_loaded(member.occult_tracker)
        with patch('apex_core.form_bank._old_process_absent',return_value=True):
            for member in (self.sims[2],self.sims[0],self.sims[1]):forms.list_forms(self.backend,member)
        records=json.loads(self.bank_path.read_text())['records']
        for key,expected in saved.items():
            self.assertEqual(records[key]['lifestate_forms'],expected)
            self.assertEqual(records[key]['lifestate_runtime_pid'],self.identity['pid'])
        self.assertEqual(self.path.read_bytes(),seals_before);self.assertEqual(self.writes,[])
