import copy
import json
from pathlib import Path
import sys
import threading
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

from test_form_bank_seal import SealFixture, SIM, HH, GUID
from apex_core import cas_bank_transaction as receiver, form_bank
from apex_core.form_bank_seal import _hash
import cas_crash_archive
from source_manifest import sha256, write_json


class ClosedCrashArchiveTests(SealFixture):
    def setUp(self):
        super().setUp()
        receiver._CAPTURED.clear(); receiver._ACTIVE.clear()
        self.addCleanup(receiver._CAPTURED.clear); self.addCleanup(receiver._ACTIVE.clear)
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
