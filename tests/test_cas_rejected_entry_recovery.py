import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / name) for name in ('tools', 'Source')]
import cas_rejected_entry_recovery as recovery
from apex_core import form_appearance as appearance


class RejectedEntryRecoveryTests(unittest.TestCase):
    def setUp(self):
        fields = {'physique': appearance.encode('independent native appearance')}
        self.fields = fields
        self.identity = dict(pid=42, script_sha256='a'*64, test_token='b'*32, profile='disposable')
        self.entry = dict(identity=self.identity, outcome='entry-rejected', entry_accepted=False,
            handshake_verified=False, entry_submitted=True, steps=[dict(action='test_cas', result=dict(
                ok=False, request_state='failed', request_id='c'*32,
                message='A prior CAS pair preparation is unresolved; no replay authorized.'))])
        self.native = dict(ok=True, differences=[], identity=self.identity, snapshots={'3': dict(
            clock_speed=0, zone_running=True, household_id='7', save_guid='99',
            _owners={lane:dict(typed_payload=copy.deepcopy(fields)) for lane in ('1', 'active')})})
        self.status = dict(ok=True, pid=42, selection_enabled=False, selected_native=dict(available=False),
            members=[dict(sim_id='3', imported_mask=0, native_view_bound=False)])
        self.diag = dict(ok=True, native_peers=[], requests=[], queued_operations=0,
            socket_transport=dict(native_connection_verified=False))
        self.prep = dict(stage='unresolved', runtime_pid=41, save_guid='99', household_id='7',
            members=[dict(sim_id='3', original_appearances={lane:copy.deepcopy(fields) for lane in ('1','active')})],
            **{key:False for key in ('appearance_written','current_kind_written','trait_written','forms_created','save_written')})
        self.bank = dict(records={'99:3':dict(bank={'1':copy.deepcopy(fields)}, pending=dict(original_owners=dict(
            stored={'1':copy.deepcopy(fields)}, active=dict(fields=copy.deepcopy(fields)))), cas_transaction={})})
        self.enterContext(patch.object(recovery, 'owners', side_effect=lambda row:row['_owners']))
        self.validator = self.enterContext(patch.object(recovery.form_bank, '_captured_schema2_archive'))

    def plan(self):
        return recovery.plan(self.entry,self.native,self.status,self.diag,self.bank,self.prep)

    def test_valid_recovery_changes_only_metadata_and_retains_both_originals(self):
        before=copy.deepcopy(self.bank);result=self.plan()
        self.assertEqual(self.bank,before)
        row=result['records']['99:3'];self.assertIsNone(row['pending']);self.assertIsNone(row['cas_transaction'])
        self.assertEqual(row['bank'],before['records']['99:3']['bank'])
        self.assertEqual(row['failed_history'][0]['pending'],before['records']['99:3']['pending'])
        self.validator.assert_called_once()

    def test_actual_entry_partial_import_native_peer_or_native_intent_refuse(self):
        for variant in ('entered','imported','peer','intent','appearance-write'):
            with self.subTest(variant=variant):
                saved=copy.deepcopy((self.entry,self.status,self.diag,self.bank,self.prep))
                if variant=='entered':self.entry['entry_accepted']=True
                elif variant=='imported':self.status['members'][0]['imported_mask']=3
                elif variant=='peer':self.diag['native_peers']=[dict(sim_id='3')]
                elif variant=='intent':self.bank['records']['99:3']['cas_transaction']['native_entry_intent']='d'*32
                else:self.prep['appearance_written']=True
                before=copy.deepcopy(self.bank)
                with self.assertRaises(ValueError):self.plan()
                self.assertEqual(self.bank,before)
                self.entry,self.status,self.diag,self.bank,self.prep=saved

    def test_a_new_native_edit_or_missing_owner_is_never_cleared(self):
        for change in ('edited','missing'):
            with self.subTest(change=change):
                saved=copy.deepcopy(self.native)
                if change=='edited':self.native['snapshots']['3']['_owners']['active']['typed_payload']['physique']=appearance.encode('new intentional edit')
                else:self.native['snapshots']['3']['_owners'].pop('1')
                before=copy.deepcopy(self.bank)
                with self.assertRaises(ValueError):self.plan()
                self.assertEqual(self.bank,before);self.native=saved
