import copy
import json
import threading
from unittest.mock import patch

from test_form_bank_seal import SealFixture
from apex_core import form_bank_seal as seal, form_appearance as appearance, lifestate_forms as forms


class SavedNamedFormsTests(SealFixture):
    def setUp(self):
        super().setUp()
        self.backend._APEX_GAME_THREAD_IDENT=threading.current_thread().ident
        self.backend._get_sim_info_by_id=lambda sid:self.sim if sid==str(self.sim.id) else None
        fields=copy.deepcopy(self.bank['records'][self.key]['bank']['1'])
        fields['physique']=appearance.encode('distinct saved Ghost appearance')
        ghost=dict(id='ghost_ghost',label='Ghost',lifestate='GHOST',base_form=1,
            fields=fields,appearance_sha256=appearance.fingerprint(fields)['appearance_sha256'])
        record=self.bank['records'][self.key]
        record.update(lifestate_runtime_pid=self.identity['pid'],
            lifestate_forms=dict(schema=1,forms={'ghost_ghost':ghost},active={}))
        forms._bind_runtime(record,self.sim)
        self.saved_named=copy.deepcopy(record['lifestate_forms'])
        self.bank_path.write_text(json.dumps(self.bank))
        self.enterContext(patch('apex_core.form_bank._old_process_absent',return_value=True))

    def loaded(self):
        self.identity['pid']+=1
        seal.note_loaded(self.tracker)

    def record(self):
        return json.loads(self.bank_path.read_text())['records'][self.key]

    def test_captured_human_ghost_bank_does_not_require_six_unowned_occults_or_fake_cas_history(self):
        record = self.bank['records'][self.key]
        record['bank'] = {'1': record['bank']['1']}; record['history'] = []
        self.forms.clear(); self.forms[1] = self.tracker.sim_info
        for name, field in appearance.payload(record['bank']['1']).items():
            if name == '__outfits__': self.sim.blob = field[1]
            else: setattr(self.sim, name, field)
        self.sim.current_occult_types = 1
        self.tracker.has_occult_type = lambda kind: False
        self.bank_path.write_text(json.dumps(self.bank))
        certified = self.certify(); self.loaded()
        listed = forms.list_forms(self.backend, self.sim)
        self.assertEqual(listed['forms'][0]['id'], 'ghost_ghost')
        self.assertEqual(set(self.record()['bank']), {'1'})
        self.assertEqual(self.writes, [])

    def test_saved_ghost_reopens_without_native_restore_and_respects_later_live_human_edits(self):
        self.certify();self.loaded()
        self.forms[1].physique='new Human edit after loading'
        before_save=self.slot.read_bytes()
        listed=forms.list_forms(self.backend,self.sim)
        self.assertEqual([row['id'] for row in listed['forms']],['ghost_ghost'])
        record=self.record()
        self.assertEqual(record['lifestate_forms'],self.saved_named)
        self.assertEqual(record['runtime_pid'],self.identity['pid'])
        self.assertEqual(record['lifestate_runtime_pid'],self.identity['pid'])
        self.assertEqual(appearance.decode(record['bank']['1']['physique']),'new Human edit after loading')
        self.assertEqual(self.forms[1].physique,'new Human edit after loading')
        self.assertEqual(self.writes,[]);self.assertEqual(self.slot.read_bytes(),before_save)
        first=self.bank_path.read_bytes();forms.list_forms(self.backend,self.sim)
        self.assertEqual(self.bank_path.read_bytes(),first)

    def test_exit_without_saving_reopens_saved_names_and_preserves_the_unsaved_look_in_history(self):
        self.certify()
        data=json.loads(self.bank_path.read_text());row=data['records'][self.key]['lifestate_forms']['forms']['ghost_ghost']
        row['fields']['physique']=appearance.encode('unsaved later Ghost edit')
        row['appearance_sha256']=appearance.fingerprint(row['fields'])['appearance_sha256']
        self.bank_path.write_text(json.dumps(data));self.loaded()
        forms.list_forms(self.backend,self.sim);record=self.record()
        self.assertEqual(record['lifestate_forms'],self.saved_named)
        archive=record['named_load_history'][-1]['archived_unsaved']
        preserved=seal._read(archive['path'])
        self.assertEqual(seal._hash(preserved),archive['sha256'])
        self.assertEqual(appearance.decode(preserved['named_forms']['forms']['ghost_ghost']['fields']['physique']),
            'unsaved later Ghost edit')
        self.assertEqual(self.writes,[])

    def test_load_loss_or_new_save_does_not_blindly_admit_a_named_document(self):
        for damage in ('load-loss','file','named-snapshot'):
            with self.subTest(damage=damage):
                self.identity['pid']=self.bank['records'][self.key]['runtime_pid'];seal._LOADED.clear()
                self.slot.write_bytes(b'prior native save')
                self.bank_path.write_text(json.dumps(self.bank))
                if self.path.exists():self.path.unlink()
                self.forms[1].physique='independent-1'
                self.certify()
                if damage=='load-loss':self.forms[1].physique='native lost saved Human'
                elif damage=='file':self.slot.write_bytes(b'another valid user save')
                else:
                    seals=seal._store(self.path);seals['records'][self.key]['named_forms']['forms']['ghost_ghost']['label']='tampered'
                    seal._write(self.path,seals)
                self.loaded();before=self.bank_path.read_bytes()
                self.assertFalse(seal.admit_saved_named(self.backend,self.sim))
                self.assertEqual(self.bank_path.read_bytes(),before);self.assertEqual(self.writes,[])

    def test_legacy_certificate_cannot_authorize_names_it_did_not_capture(self):
        del self.bank['records'][self.key]['lifestate_forms'];self.bank_path.write_text(json.dumps(self.bank))
        self.certify()
        self.bank['records'][self.key]['lifestate_forms']=copy.deepcopy(self.saved_named)
        self.bank_path.write_text(json.dumps(self.bank));self.loaded();before=self.bank_path.read_bytes()
        self.assertFalse(seal.admit_saved_named(self.backend,self.sim))
        self.assertEqual(self.bank_path.read_bytes(),before);self.assertEqual(self.writes,[])

    def test_metadata_admission_does_not_require_resaving_after_each_restart(self):
        self.certify()
        for count in (1,2):
            self.loaded();forms.list_forms(self.backend,self.sim)
            record=self.record();self.assertEqual(record['lifestate_forms'],self.saved_named)
            self.assertEqual(record['lifestate_runtime_pid'],self.identity['pid'])
            self.assertEqual(len(record['named_load_history']),count)
        self.assertEqual(self.writes,[])

    def test_deferred_native_load_completion_can_match_saved_state_after_an_early_partial_sample(self):
        self.certify(); self.loaded()
        seal._LOADED[self.key]['native']['stored'].pop('16')
        forms.list_forms(self.backend,self.sim)
        self.assertEqual(self.record()['lifestate_forms'],self.saved_named)
        self.assertTrue(forms._owns_runtime(self.record(),self.sim));self.assertEqual(self.writes,[])

    def test_partial_load_sample_cannot_certify_a_current_native_loss_or_unproved_live_edit(self):
        self.certify();self.loaded()
        seal._LOADED[self.key]['native']['stored'].pop('16')
        self.forms[1].physique='a differing current Native Human'
        original=self.bank_path.read_bytes()
        self.assertFalse(seal.admit_saved_named(self.backend,self.sim))
        self.assertEqual(self.bank_path.read_bytes(),original);self.assertEqual(self.writes,[])
        self.assertIn('match-save',self.backend._APEX_NAMED_LOAD_DIAGNOSTICS[str(self.sim.id)]['reason'])

    def test_known_metadata_predecessor_does_not_gain_native_restore_authority(self):
        certified=self.certify();old_source=self.identity['script_sha256'];self.identity['script_sha256']='c'*64
        with patch.object(seal,'NAMED_METADATA_PREDECESSORS',(old_source,)):
            self.loaded();forms.list_forms(self.backend,self.sim)
            self.assertEqual(self.record()['lifestate_forms'],self.saved_named)
            self.assertEqual(self.backend._APEX_NAMED_LOAD_DIAGNOSTICS[str(self.sim.id)]['metadata_source_authority'],
                'named-metadata-only:'+old_source)
            with self.assertRaisesRegex(ValueError,'another source'):
                seal.reconcile(self.backend,self.sim,dict(seal_sha256=certified['seal_sha256']))
        self.assertEqual(self.writes,[])

    def test_unknown_source_still_cannot_admit_saved_names_or_mutate_native_data(self):
        self.certify();self.identity['script_sha256']='c'*64;self.loaded();original=self.bank_path.read_bytes()
        self.assertFalse(seal.admit_saved_named(self.backend,self.sim))
        self.assertEqual(self.bank_path.read_bytes(),original);self.assertEqual(self.writes,[])

    def test_audited_v192_menu_upgrade_reopens_metadata_without_native_restore_authority(self):
        old_source='cfef084203d44910520917a2922a034bb6c996cb68bac436782460a94712b0cd'
        self.assertIn(old_source,seal.NAMED_METADATA_PREDECESSORS)
        self.identity['script_sha256']=old_source
        certified=self.certify();self.identity['script_sha256']='c'*64
        self.loaded();forms.list_forms(self.backend,self.sim)
        self.assertEqual(self.record()['lifestate_forms'],self.saved_named)
        with self.assertRaisesRegex(ValueError,'another source'):
            seal.reconcile(self.backend,self.sim,dict(seal_sha256=certified['seal_sha256']))
        self.assertEqual(self.writes,[])

    def test_audited_v198_fairy_save_reopens_metadata_without_native_restore_authority(self):
        old_source='aa2b7e955890d44c6d0c66225777fa10cfeff68900c7650d860910e07d0a3770'
        self.assertIn(old_source,seal.NAMED_METADATA_PREDECESSORS)
        self.identity['script_sha256']=old_source
        certified=self.certify();self.identity['script_sha256']='c'*64
        self.loaded();forms.list_forms(self.backend,self.sim)
        self.assertEqual(self.record()['lifestate_forms'],self.saved_named)
        self.assertEqual(self.backend._APEX_NAMED_LOAD_DIAGNOSTICS[str(self.sim.id)]['metadata_source_authority'],
            'named-metadata-only:'+old_source)

        with self.assertRaisesRegex(ValueError,'another source'):
            seal.reconcile(self.backend,self.sim,dict(seal_sha256=certified['seal_sha256']))
        self.assertEqual(self.writes,[])

    def test_v261_edited_household_save_reopens_after_code_upgrade_without_native_restore(self):
        old_source='30b38b03923e8d32cf191feec719f621a0e4b62bd1516209759ca007417995b4'
        self.assertIn(old_source,seal.NAMED_METADATA_PREDECESSORS)
        self.identity['script_sha256']=old_source
        certified=self.certify();self.identity['script_sha256']='c'*64
        sealed_bytes=self.path.read_bytes()
        self.loaded();forms.list_forms(self.backend,self.sim)
        self.assertEqual(self.record()['lifestate_forms'],self.saved_named)
        self.assertEqual(self.path.read_bytes(),sealed_bytes)
        self.assertEqual(self.backend._APEX_NAMED_LOAD_DIAGNOSTICS[str(self.sim.id)]['metadata_source_authority'],
            'named-metadata-only:'+old_source)
        with self.assertRaisesRegex(ValueError,'another source'):
            seal.reconcile(self.backend,self.sim,dict(seal_sha256=certified['seal_sha256']))
        self.assertEqual(self.writes,[])

    def test_v295_edited_household_save_admits_only_saved_metadata_after_upgrade(self):
        old_source='1eb9997146db3e2426e0acc4f847fc729f732baaf3ec1bc1f2f26dec68e39fbe'
        self.assertIn(old_source,seal.NAMED_METADATA_PREDECESSORS)
        self.identity['script_sha256']=old_source
        certified=self.certify();self.identity['script_sha256']='c'*64
        sealed_bytes=self.path.read_bytes()
        self.loaded();forms.list_forms(self.backend,self.sim)
        self.assertEqual(self.record()['lifestate_forms'],self.saved_named)
        self.assertEqual(self.path.read_bytes(),sealed_bytes)
        self.assertEqual(self.backend._APEX_NAMED_LOAD_DIAGNOSTICS[str(self.sim.id)]['metadata_source_authority'],
            'named-metadata-only:'+old_source)
        with self.assertRaisesRegex(ValueError,'another source'):
            seal.reconcile(self.backend,self.sim,dict(seal_sha256=certified['seal_sha256']))
        self.assertEqual(self.writes,[])

    def test_same_process_save_reload_uses_the_saved_names_and_not_the_unsaved_old_tracker(self):
        self.certify()
        data=json.loads(self.bank_path.read_text());ghost=data['records'][self.key]['lifestate_forms']['forms']['ghost_ghost']
        ghost['fields']['physique']=appearance.encode('unsaved look before loading again')
        ghost['appearance_sha256']=appearance.fingerprint(ghost['fields'])['appearance_sha256']
        self.bank_path.write_text(json.dumps(data))
        old_tracker=self.tracker;self.tracker=copy.deepcopy(old_tracker)
        del self.tracker._apex_named_runtime_epoch
        self.tracker.sim_info=self.sim;self.tracker._sim_info=self.sim;self.tracker._sim_info_map=self.forms
        self.sim.occult_tracker=self.tracker;seal.note_loaded(self.tracker)
        forms.list_forms(self.backend,self.sim)
        self.assertEqual(self.record()['lifestate_forms'],self.saved_named)
        self.assertTrue(forms._owns_runtime(self.record(),self.sim))
        self.assertIsNot(self.tracker,old_tracker);self.assertEqual(self.writes,[])
