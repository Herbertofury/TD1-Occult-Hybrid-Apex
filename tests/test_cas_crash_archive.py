import copy
import json
from pathlib import Path
import sys
import threading
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

from test_form_bank_seal import SealFixture, SIM, HH, GUID
from test_cas_bank_transaction import reset_receiver_process
from apex_core import cas_bank_transaction as receiver, form_bank
from apex_core.form_bank_seal import _hash
import cas_crash_archive
from source_manifest import sha256, write_json


class ClosedCrashArchiveTests(SealFixture):
    def setUp(self):
        super().setUp()
        reset_receiver_process()
        self.addCleanup(reset_receiver_process)
        self.backend._APEX_GAME_THREAD_IDENT = threading.current_thread().ident
        self.backend._get_sim_info_by_id = lambda _id: self.sim
        self.old = dict(self.identity, pid=self.identity['pid'] - 1)
        with patch.object(receiver.os, 'getpid', return_value=self.old['pid']):
            receiver.begin(self.backend, self.sim)
        self.original = json.loads(self.bank_path.read_text())
        record = self.original['records'][self.key]
        before = dict(self.live(), sim_now_ticks='123', save_slot=0xffffffff)
        before['runtime_queries'] = dict(before['runtime_queries'], sim_now_ticks='returned-value')
        self.entry_path = self.root / 'entry.json'
        checkpoint = dict(ok=True, native_appearance_written=False,
            checkpoint_sha256=_hash(record['pending']),
            expected_pending_sha256=record['cas_transaction']['transaction_sha256'])
        self.entry = dict(schema=1, operation='observe-native-cas-entry', ok=True, outcome='inventory',
            entry_submitted=True, entry_accepted=True, handshake_verified=True, inventory_verified=True,
            no_input_replay=True, requested_sim_id=SIM, identity=self.old, crash_before={'state':'absent'},
            steps=[{'action':'test_cas','result':dict(ok=True,before=before,form_checkpoint=checkpoint)}])
        write_json(self.entry_path, self.entry)
        self.crash = self.root / 'crash.xml'; self.crash.write_bytes(b'<type>crash</type>')
        self.proof_path = self.root / 'proof.json'
        self.proof = dict(schema=1, operation='observe-native-cas-post-entry-crash', ok=False,
            outcome='native-crash', process_absent_observed=True, identity=self.old,
            entry_proof=str(self.entry_path), entry_proof_sha256=sha256(self.entry_path),
            sim_id=SIM, household_id=HH, save_guid=GUID, slot_id=0xffffffff,
            crash=dict(outcome='preserved', preserved=True, before={'state':'absent'},
                after={'sha256':sha256(self.crash)},path=str(self.crash)))
        self.publish()
        self.output = self.root / 'archive.json'
        self.journal = dict(token=self.identity['test_token'])
        self.enterContext(patch.object(cas_crash_archive.reusable_profile, 'load',
            return_value=(self.root/'state.json',self.journal,self.profile,self.protected)))
        self.guard = self.enterContext(patch.object(cas_crash_archive.reusable_profile.legacy,'require_closed'))
        self.enterContext(patch.object(cas_crash_archive.cas_crash.cas_transition,'process_alive',return_value=False))

    def publish(self):
        write_json(self.proof_path,self.proof)
        self.proof_hash = sha256(self.proof_path)

    def invoke(self):
        return cas_crash_archive.archive(self.root/'state.json',self.proof_path,self.proof_hash,
            2,self.target['expected_save_sha256'],self.output)

    def test_exact_closed_crash_archives_metadata_with_originals_and_all_banks_intact(self):
        before = self.bank_path.read_bytes(); saved = self.slot.read_bytes()
        result = self.invoke()
        self.assertTrue(result['ok']); self.assertTrue(result['bank_lanes_unchanged'])
        self.assertEqual((self.root/'archive-bank-before.json').read_bytes(),before)
        after = json.loads(self.bank_path.read_text())
        record = after['records'][self.key]
        self.assertIsNone(record['pending']); self.assertIsNone(record['cas_transaction'])
        self.assertEqual(record['failed_history'][-1]['pending'],self.original['records'][self.key]['pending'])
        self.assertEqual(self.slot.read_bytes(),saved); self.assertEqual(self.writes,[])
        self.assertFalse(result['loaded_file_verified']); self.assertFalse(result['save_reload_verified'])

    def test_closed_accepted_entry_timeout_can_archive_captured_metadata_without_claiming_inventory(self):
        self.entry.update(ok=False,outcome='unresolved',inventory_verified=False,handshake_verified=False)
        write_json(self.entry_path,self.entry); original_entry=self.entry_path.read_bytes()
        result=cas_crash_archive.archive(self.root/'state.json',self.entry_path,sha256(self.entry_path),
            2,self.target['expected_save_sha256'],self.output,entry_only=True)
        self.assertTrue(result['ok']);self.assertFalse(result['entry_inventory_verified'])
        self.assertTrue(result['bank_lanes_unchanged']);self.assertTrue(result['save_files_unchanged'])
        self.assertEqual(self.entry_path.read_bytes(),original_entry)

    def test_incomplete_inventory_does_not_qualify_native_crash_or_rejected_entry(self):
        self.entry.update(ok=False,outcome='unresolved',inventory_verified=False)
        write_json(self.entry_path,self.entry)
        self.proof['entry_proof_sha256']=sha256(self.entry_path);self.publish()
        before=self.bank_path.read_bytes()
        with self.assertRaises(ValueError):self.invoke()
        self.entry['entry_accepted']=False;write_json(self.entry_path,self.entry)
        with self.assertRaises(ValueError):
            cas_crash_archive.archive(self.root/'state.json',self.entry_path,sha256(self.entry_path),
                2,self.target['expected_save_sha256'],self.output,entry_only=True)
        self.assertEqual(self.bank_path.read_bytes(),before);self.assertFalse(self.output.exists())

    def early_crash_entry(self):
        self.entry.update(ok=False, outcome='crash', inventory_verified=False,
            handshake_verified=False, process_exit_verified=True,
            crash=copy.deepcopy(self.proof['crash']))
        self.entry['crash']['after'].update(state='read', bytes=self.crash.stat().st_size)
        write_json(self.entry_path, self.entry)

    def archive_entry(self):
        return cas_crash_archive.archive(self.root/'state.json', self.entry_path, sha256(self.entry_path),
            2, self.target['expected_save_sha256'], self.output, entry_only=True)

    def test_early_entry_crash_archives_only_captured_metadata_with_exact_preserved_report(self):
        self.early_crash_entry(); original_entry=self.entry_path.read_bytes(); original_bank=self.bank_path.read_bytes()
        result=self.archive_entry()
        self.assertTrue(result['ok']); self.assertTrue(result['early_entry_crash_report_verified'])
        self.assertFalse(result['entry_inventory_verified']); self.assertFalse(result['crash_verified'])
        self.assertFalse(result['normal_exit_verified']); self.assertFalse(result['save_reload_verified'])
        self.assertFalse(result['appearance_mutated']); self.assertFalse(result['causality_verified'])
        self.assertEqual(self.entry_path.read_bytes(),original_entry)
        self.assertEqual((self.root/'archive-bank-before.json').read_bytes(),original_bank)
        self.assertEqual(self.writes,[])

    def test_early_entry_crash_rejects_unverified_exit_replay_or_report_before_metadata_write(self):
        self.early_crash_entry(); good=copy.deepcopy(self.entry); held=self.bank_path.read_bytes()
        for mutation in ('exit','accepted','replay','missing','changed','unchanged','size','protected'):
            altered=copy.deepcopy(good)
            if mutation=='exit': altered['process_exit_verified']=False
            elif mutation=='accepted': altered['entry_accepted']=False
            elif mutation=='replay': altered['no_input_replay']=False
            elif mutation=='missing': altered['crash']['path']=str(self.root/'absent.xml')
            elif mutation=='changed': altered['crash']['after']['sha256']='a'*64
            elif mutation=='unchanged': altered['crash_before']=altered['crash']['before']=copy.deepcopy(altered['crash']['after'])
            elif mutation=='size': altered['crash']['after']['bytes']+=1
            else:
                target=self.protected/'crash.xml'; target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(self.crash.read_bytes()); altered['crash']['path']=str(target)
            write_json(self.entry_path,altered)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.archive_entry()
            self.assertEqual(self.bank_path.read_bytes(),held);self.assertFalse(self.output.exists())
            self.assertFalse((self.root/'archive-bank-before.json').exists())

    def test_early_entry_crash_report_change_during_archival_blocks_final_bank_write(self):
        self.early_crash_entry(); held=self.bank_path.read_bytes(); count=[0]
        def closure():
            count[0]+=1
            if count[0]==2:self.crash.write_bytes(b'changed during archive')
        self.guard.side_effect=closure
        with self.assertRaisesRegex(ValueError,'crash bytes'):self.archive_entry()
        self.assertEqual(self.bank_path.read_bytes(),held)
        self.assertFalse(json.loads(self.output.read_text())['metadata_write_submitted'])

    def scoped_entry(self, additional=()):
        row=self.entry['steps'][0]['result']
        members=[{'sim_id':SIM,'form_checkpoint':row['form_checkpoint']}] + list(additional)
        row['household_form_checkpoints']={'ok':True,'household_id':HH,
            'roster_sim_ids':[item['sim_id'] for item in members],'members':members}
        write_json(self.entry_path,self.entry)
        self.proof['entry_proof_sha256']=sha256(self.entry_path);self.publish()

    def test_scoped_entry_keeps_each_exact_capture_and_reports_its_member_ids(self):
        self.scoped_entry()
        result=self.invoke()
        self.assertTrue(result['ok']);self.assertEqual(result['archived_member_sim_ids'],[SIM])
        self.assertTrue(result['bank_lanes_unchanged']);self.assertEqual(self.writes,[])

    def test_missing_companion_receiver_blocks_entire_scope_before_any_archive_write(self):
        self.scoped_entry([{'sim_id':'200','form_checkpoint':dict(ok=True,native_appearance_written=False,
            checkpoint_sha256='a'*64,expected_pending_sha256='b'*64)}])
        before=self.bank_path.read_bytes()
        with self.assertRaisesRegex(ValueError,'captured CAS metadata'):self.invoke()
        self.assertEqual(self.bank_path.read_bytes(),before);self.assertFalse(self.output.exists())
        self.assertFalse((self.root/'archive-bank-before.json').exists())

    def test_foreign_household_scope_cannot_archive_selected_original(self):
        self.scoped_entry()
        self.entry['steps'][0]['result']['household_form_checkpoints']['household_id']='999'
        write_json(self.entry_path,self.entry);self.proof['entry_proof_sha256']=sha256(self.entry_path);self.publish()
        before=self.bank_path.read_bytes()
        with self.assertRaisesRegex(ValueError,'household scope'):self.invoke()
        self.assertEqual(self.bank_path.read_bytes(),before)

    def native_context_entry(self):
        data=json.loads(self.bank_path.read_text());record=data['records'][self.key]
        transaction=record['cas_transaction'];pending=record['pending']
        context={lane:{'available':65,'current':int(lane)} for lane in pending['original_owners']['stored']}
        context['active']={'available':65,'current':int(pending['lane'])}
        transaction['native_occult_context']=context
        transaction['native_occult_context_sha256']=_hash(context)
        envelope={name:transaction[name] for name in ('transaction_id','identity','checkpoint_sha256',
            'record_guard_sha256','hair_checkpoint_sha256')}
        transaction['transaction_sha256']=_hash(receiver._native_context_envelope(transaction,envelope))
        write_json(self.bank_path,data)
        self.entry['steps'][0]['result']['form_checkpoint']['expected_pending_sha256']=transaction['transaction_sha256']
        write_json(self.entry_path,self.entry);self.proof['entry_proof_sha256']=sha256(self.entry_path);self.publish()
        return data

    def test_fresh_native_availability_extension_is_archived_without_restoration(self):
        before=self.native_context_entry()
        self.assertTrue(self.invoke()['ok'])
        row=json.loads(self.bank_path.read_text())['records'][self.key]
        self.assertEqual(row['failed_history'][-1]['cas_transaction']['native_occult_context'],
                         before['records'][self.key]['cas_transaction']['native_occult_context'])
        self.assertEqual(self.writes,[])

    def test_changed_native_context_extension_hash_blocks_archival_before_any_write(self):
        data=self.native_context_entry()
        data['records'][self.key]['cas_transaction']['native_occult_context_sha256']='a'*64
        write_json(self.bank_path,data);before=self.bank_path.read_bytes()
        with self.assertRaisesRegex(ValueError,'context hash'):self.invoke()
        self.assertEqual(self.bank_path.read_bytes(),before);self.assertFalse(self.output.exists())

    def test_running_game_refuses_before_read_or_write(self):
        self.guard.side_effect = RuntimeError('game running')
        before = self.bank_path.read_bytes()
        with self.assertRaises(RuntimeError): self.invoke()
        self.assertEqual(self.bank_path.read_bytes(),before); self.assertFalse(self.output.exists())

    def test_changed_disk_save_refuses_without_metadata_write(self):
        self.slot.write_bytes(b'new save'); before = self.bank_path.read_bytes()
        with self.assertRaisesRegex(ValueError,'save changed'): self.invoke()
        self.assertEqual(self.bank_path.read_bytes(),before)

    def test_mismatched_checkpoint_and_observed_transaction_refuse(self):
        for mutation in ('checkpoint','phase','owner','bank'):
            data=copy.deepcopy(self.original); record=data['records'][self.key]
            if mutation=='checkpoint':record['pending']['original_owners']['stored']['64']['physique']['value']='other'
            elif mutation=='phase':record['cas_transaction']['phase']='observed'
            elif mutation=='owner':record['pending']['runtime_pid']+=1
            else:record['bank']['64']['physique']['value']='new bank'
            write_json(self.bank_path,data); before=self.bank_path.read_bytes()
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.invoke()
            self.assertEqual(self.bank_path.read_bytes(),before);self.assertFalse(self.output.exists())

    def test_existing_evidence_and_wrong_profile_token_refuse(self):
        self.journal['token']='f'*32
        with self.assertRaises(ValueError):self.invoke()
        self.journal['token']=self.identity['test_token'];self.output.write_text('{}')
        before=self.bank_path.read_bytes()
        with self.assertRaisesRegex(ValueError,'new external'):self.invoke()
        self.assertEqual(self.bank_path.read_bytes(),before)

    def test_closed_captured_entry_archives_without_inventing_crash_or_normal_return(self):
        result=cas_crash_archive.archive(self.root/'state.json',self.entry_path,sha256(self.entry_path),
            2,self.target['expected_save_sha256'],self.output,entry_only=True)
        self.assertTrue(result['ok']);self.assertFalse(result['crash_verified'])
        self.assertFalse(result['normal_exit_verified']);self.assertFalse(result['save_reload_verified'])
        self.assertEqual(self.writes,[])
        row=json.loads(self.bank_path.read_text())['records'][self.key]
        self.assertEqual(row['failed_history'][-1]['closure_kind'],'captured-entry')

    def test_captured_entry_unknown_inventory_and_foreign_checkpoint_refuse(self):
        for field in ('inventory_verified','entry_accepted','no_input_replay'):
            value=copy.deepcopy(self.entry);value[field]=False;write_json(self.entry_path,value)
            before=self.bank_path.read_bytes()
            with self.subTest(field=field),self.assertRaises(ValueError):
                cas_crash_archive.archive(self.root/'state.json',self.entry_path,sha256(self.entry_path),
                    2,self.target['expected_save_sha256'],self.output,entry_only=True)
            self.assertEqual(self.bank_path.read_bytes(),before);self.assertFalse(self.output.exists())

    def mccc_before(self):
        self.scoped_entry()
        result = self.entry['steps'][0]['result']
        before = result.pop('before')
        pending = self.original['records'][self.key]['pending']['original_owners']
        before['sim']['form_appearances'] = [dict(flags=int(lane), appearance={'typed_payload': fields})
            for lane, fields in pending['stored'].items()]
        before['sim']['full_appearance'] = {'typed_payload': pending['active']['fields']}
        result['mccc_callback'] = dict(actual_callback_invoked=True, method='SimMenuNavigation._modify_household_in_cas')
        result['native_frontdoor'] = dict(stage='native-command-returned', full_household=True, sim_id=SIM, household_id=HH)
        write_json(self.entry_path, self.entry)
        packet = dict(ok=True, save_submitted=False, identity=self.old, snapshots={SIM: before})
        path = self.root / 'native-before.json'; write_json(path, packet)
        return path, packet

    def test_older_mccc_entry_can_archive_only_with_exact_same_runtime_native_originals(self):
        path, _packet = self.mccc_before()
        result = cas_crash_archive.archive(self.root/'state.json', self.entry_path, sha256(self.entry_path),
            2, self.target['expected_save_sha256'], self.output, entry_only=True,
            before_proof=path, expected_before_sha256=sha256(path))
        self.assertTrue(result['ok'])
        self.assertTrue(result['supplemental_appearances_equal_entry_originals'])
        self.assertFalse(result['normal_exit_verified'])
        self.assertFalse(result['save_written'])

    def test_supplemental_changed_appearance_runtime_or_roster_cannot_archive(self):
        path, packet = self.mccc_before()
        held = self.bank_path.read_bytes()
        for mutation in ('runtime', 'roster', 'appearance'):
            changed = copy.deepcopy(packet)
            if mutation == 'runtime': changed['identity']['pid'] += 1
            elif mutation == 'roster': changed['snapshots']['999'] = copy.deepcopy(changed['snapshots'][SIM])
            else: changed['snapshots'][SIM]['sim']['full_appearance']['typed_payload'] = {}
            write_json(path, changed)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                cas_crash_archive.archive(self.root/'state.json', self.entry_path, sha256(self.entry_path),
                    2, self.target['expected_save_sha256'], self.output, entry_only=True,
                    before_proof=path, expected_before_sha256=sha256(path))
            self.assertEqual(self.bank_path.read_bytes(), held)

    def bind_supplemental_frontdoor(self):
        intent='d'*32
        data=json.loads(self.bank_path.read_text())
        data['records'][self.key]['cas_transaction']['native_entry_intent']=intent
        self.bank_path.write_text(json.dumps(data))
        checkpoint=self.entry['steps'][0]['result']['form_checkpoint']
        source=dict(schema=1,stage='native-command-returned',native_appearance_written=False,
            id=intent,household_id=HH,sim_id=SIM,members=[dict(sim_id=SIM,checkpoint=checkpoint,
                owner_observation={'original_owner':dict(complete=True,runtime_pid=self.old['pid'],
                    original_sim_id=SIM,household_id=HH,save_guid=GUID)})])
        path=self.root/'source-frontdoor.json';write_json(path,source)
        return path,source

    def test_source_frontdoor_binds_old_cli_receipt_missing_its_native_intent(self):
        path,_source=self.bind_supplemental_frontdoor()
        before=self.bank_path.read_bytes()
        result=cas_crash_archive.archive(self.root/'state.json',self.proof_path,self.proof_hash,
            2,self.target['expected_save_sha256'],self.output,
            frontdoor_proof=path,expected_frontdoor_sha256=sha256(path))
        self.assertTrue(result['ok']);self.assertTrue(result['bank_lanes_unchanged'])
        self.assertEqual(result['native_entry_intent'],'d'*32)
        self.assertEqual((self.root/'archive-bank-before.json').read_bytes(),before)
        self.assertFalse(result['save_written'])

    def test_closed_timeout_uses_exact_source_frontdoor_without_inventing_inventory_success(self):
        path,source=self.bind_supplemental_frontdoor()
        self.entry.update(ok=False,outcome='unresolved',inventory_verified=False)
        write_json(self.entry_path,self.entry);entry_bytes=self.entry_path.read_bytes()
        before=self.bank_path.read_bytes()
        result=cas_crash_archive.archive(self.root/'state.json',self.entry_path,sha256(self.entry_path),
            2,self.target['expected_save_sha256'],self.output,entry_only=True,
            frontdoor_proof=path,expected_frontdoor_sha256=sha256(path))
        self.assertTrue(result['ok']);self.assertFalse(result['entry_inventory_verified'])
        self.assertFalse(result['normal_exit_verified']);self.assertFalse(result['save_reload_verified'])
        self.assertEqual(self.entry_path.read_bytes(),entry_bytes)
        self.assertEqual((self.root/'archive-bank-before.json').read_bytes(),before)
        self.assertEqual(result['native_entry_intent'],source['id'])

    def test_source_frontdoor_cannot_authorize_another_runtime_or_missing_member(self):
        path,source=self.bind_supplemental_frontdoor();before=self.bank_path.read_bytes()
        for change in ('runtime','roster','checkpoint'):
            altered=copy.deepcopy(source)
            if change=='runtime':altered['members'][0]['owner_observation']['original_owner']['runtime_pid']+=1
            elif change=='roster':altered['members']=[]
            else:altered['members'][0]['checkpoint']['checkpoint_sha256']='f'*64
            write_json(path,altered)
            with self.subTest(change=change),self.assertRaises(ValueError):
                cas_crash_archive.archive(self.root/'state.json',self.proof_path,self.proof_hash,
                    2,self.target['expected_save_sha256'],self.output,
                    frontdoor_proof=path,expected_frontdoor_sha256=sha256(path))
            self.assertEqual(self.bank_path.read_bytes(),before)
            self.assertFalse(self.output.exists())
