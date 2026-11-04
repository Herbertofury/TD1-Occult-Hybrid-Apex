import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import cas_abandon
import apex_cli
from cas_return import live_snapshot, SIM_TIME_SOURCE
from test_game_discard import diagnostic, live


class AbandonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.profile, self.original = self.root / 'The Sims 4', self.root / 'protected'
        self.profile.mkdir(); self.original.mkdir()
        self.output = self.root / 'out.json'
        self.identity = {'pid': 9, 'test_token': 'b' * 32, 'script_sha256': 'c' * 64, 'profile': str(self.profile)}
        old = dict(self.identity, pid=8, script_sha256='d' * 64)
        failed = {'schema': 1, 'operation': 'semantic-cas-return-to-live', 'ok': False,
            'outcome': 'unresolved', 'accept_submitted': True, 'accept_intent_observed': True,
            'cas_peer_disappearance_verified': True, 'process_exit_verified': False,
            'input_submitted': False, 'sim_id': '11', 'household_id': '22', 'cas_request_id': 'a' * 32,
            'identity': old, 'crash': {'outcome': 'unchanged'},
            'steps': [{'action': 'test_snapshot', 'result': live()}]}
        self.failed = self.root / 'failed.json'
        self.failed.write_text(json.dumps(failed), encoding='utf-8')
        self.failed_hash = hashlib.sha256(self.failed.read_bytes()).hexdigest()
        self.save = self.profile / 'saves' / 'Slot_00000002.save'
        self.save.parent.mkdir(); self.save.write_bytes(b'untouched existing save')
        self.save_hash = hashlib.sha256(self.save.read_bytes()).hexdigest()
        self.bank = self.profile / 'TD1_OccultHybridApexData' / 'form_bank.json'
        self.bank.parent.mkdir()
        self.pending = {'state': 'captured', 'lane': '64', 'originals': {'64': {'future_field': 'retained'}}}
        self.data = {'schema': 1, 'records': {'33:11': {'pending': copy.deepcopy(self.pending),
            'bank': {'64': {'future_field': 'do not restore'}}, 'history': [], 'switch_pending': None},
            'other:sim': {'bank': {'x': 123}}}}
        self.bank.write_text(json.dumps(self.data), encoding='utf-8')
        self.journal = {'token': 'b' * 32, 'artifacts': [{'name': 'ApexOccultHybrid.ts4script', 'sha256': 'c' * 64}]}
        self.actions, self.old_alive, self.lose_response, self.change_lane = [], False, False, False
        self.native_slot, self.archive_values = 2, []

    def request(self, _state, action, **kwargs):
        self.actions.append(action)
        request_id = uuid.uuid4().hex
        kwargs['transport']('/api/command', {'action': action, 'request_id': request_id})
        if action == 'test_snapshot':
            return dict(live(), sim={'id': '11', 'instanced': True}, save_slot=self.native_slot,
                        sim_time_source=SIM_TIME_SOURCE)
        if action == 'cas_ui_diagnostics':
            value = diagnostic(); value['requests'] = []; return value
        if action != 'test_cas_abandon_unsaved': raise AssertionError(action)
        argument = json.loads(kwargs['value'])['value']
        self.archive_values.append(argument)
        data = json.loads(self.bank.read_text(encoding='utf-8'))
        row = data['records']['33:11']
        row.setdefault('failed_history', []).append({'pending_sha256': argument['expected_pending_sha256'],
            'failed_return_proof_sha256': argument['failed_return_proof_sha256'], 'pending': row['pending']})
        row['pending'] = None
        if self.change_lane: row['bank']['64']['future_field'] = 'unexpected overwrite'
        self.bank.write_text(json.dumps(data), encoding='utf-8')
        if self.lose_response: raise OSError('Response lost after metadata archive')
        return {'ok': True, 'abandoned': True, 'appearance_mutated': False, 'save_written': False}

    def transport(self, _path, query, **_kwargs):
        proof = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertEqual(proof['owner_requests'][-1]['request_id'], query['request_id'])
        return {'ok': True}

    def run_observer(self, **options):
        with patch.object(cas_abandon.reusable_profile, 'load', return_value=(self.root / 'state.json', self.journal, self.profile, self.original)):
            return cas_abandon.observe(self.root / 'state.json', self.output, self.identity, self.request,
                self.failed, self.failed_hash, self.save_hash, '11', '22', '33', 2,
                alive=lambda pid: self.old_alive if pid == 8 else True, transport=self.transport, **options)

    def test_autosave_sentinel_requires_explicit_metadata_only_option(self):
        self.native_slot = 0xffffffff
        result = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertNotIn('test_cas_abandon_unsaved', self.actions)
        self.assertEqual(json.loads(self.bank.read_text())['records']['33:11']['pending'], self.pending)

    def test_opted_in_autosave_archive_preserves_all_originals_without_disk_reload_claim(self):
        self.native_slot = 0xffffffff
        result = self.run_observer(allow_auto_save_slot_metadata_only=True)
        self.assertTrue(result['ok'])
        self.assertFalse(result['disk_slot_verified']); self.assertFalse(result['save_reload_verified'])
        self.assertTrue(self.archive_values[0]['allow_auto_save_slot_metadata_only'])
        proof = json.loads(self.output.read_text())
        self.assertEqual(proof['native_save_slot'], 0xffffffff)
        self.assertEqual(self.save.read_bytes(), b'untouched existing save')

    def test_metadata_option_does_not_authorize_other_native_slot(self):
        self.native_slot = 3
        result = self.run_observer(allow_auto_save_slot_metadata_only=True)
        self.assertFalse(result['ok'])
        self.assertNotIn('test_cas_abandon_unsaved', self.actions)

    def test_archive_retains_exact_failed_originals_without_native_or_save_writes(self):
        result = self.run_observer()
        self.assertTrue(result['ok'])
        after = json.loads(self.bank.read_text(encoding='utf-8'))
        self.assertEqual(after['records']['33:11']['failed_history'][0]['pending'], self.pending)
        self.assertIsNone(after['records']['33:11']['pending'])
        self.assertEqual(after['records']['33:11']['bank'], self.data['records']['33:11']['bank'])
        self.assertEqual(self.save.read_bytes(), b'untouched existing save')
        self.assertEqual(self.actions.count('test_cas_abandon_unsaved'), 1)
        self.assertNotIn('test_save', self.actions)

    def test_old_process_alive_or_unknown_refuses_before_transport(self):
        for alive in (True, None):
            self.old_alive = alive
            with self.subTest(alive=alive), self.assertRaises(ValueError): self.run_observer()
        self.assertEqual(self.actions, [])

    def test_changed_save_refuses_before_transport(self):
        self.save.write_bytes(b'new user save')
        with self.assertRaises(ValueError): self.run_observer()
        self.assertEqual(self.actions, [])

    def test_changed_proof_refuses_before_transport(self):
        self.failed.write_text('{}', encoding='utf-8')
        with self.assertRaises(ValueError): self.run_observer()
        self.assertEqual(self.actions, [])

    def test_different_pending_switch_is_not_discarded(self):
        self.data['records']['33:11']['switch_pending'] = {'target': '1'}
        self.bank.write_text(json.dumps(self.data), encoding='utf-8')
        with self.assertRaises(ValueError): self.run_observer()
        self.assertEqual(self.actions, [])

    def test_response_loss_retains_owner_identity_without_repeating_archive(self):
        self.lose_response = True
        result = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertEqual(self.actions.count('test_cas_abandon_unsaved'), 1)
        proof = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertTrue(proof['archive_submitted'])
        self.assertEqual(proof['owner_requests'][-1]['action'], 'test_cas_abandon_unsaved')

    def test_unexpected_bank_write_is_not_reported_as_success(self):
        self.change_lane = True
        result = self.run_observer()
        self.assertFalse(result['ok'])
        proof = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertTrue(proof['bank_lanes_changed'])

    def test_reloaded_exact_sim_is_required_before_archiving(self):
        base = self.request
        def changed(state, action, **kwargs):
            result = base(state, action, **kwargs)
            if action == 'test_snapshot': result.pop('sim')
            return result
        self.request = changed
        result = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertNotIn('test_cas_abandon_unsaved', self.actions)

    def entry_crash(self):
        old = dict(self.identity, pid=8, script_sha256='d' * 64)
        crash = self.root / 'preserved-crash.xml'
        crash.write_bytes(b'<report><type>crash</type></report>')
        before = dict(live(), sim={'id': '11', 'instanced': True}, save_slot=2)
        failed = {'schema': 1, 'operation': 'observe-native-cas-entry', 'ok': False, 'outcome': 'crash',
            'entry_submitted': True, 'entry_accepted': True, 'handshake_verified': True,
            'inventory_verified': False, 'no_input_replay': True, 'requested_sim_id': '11', 'identity': old,
            'crash': {'outcome': 'preserved', 'preserved': True, 'path': str(crash), 'before': {'state': 'absent'},
                      'after': {'sha256': hashlib.sha256(crash.read_bytes()).hexdigest()}},
            'steps': [{'action': 'test_cas', 'result': {'ok': True, 'before': before}}]}
        return failed, crash

    def publish_failed(self, failed):
        self.failed.write_text(json.dumps(failed), encoding='utf-8')
        self.failed_hash = hashlib.sha256(self.failed.read_bytes()).hexdigest()

    def test_entry_crash_archives_only_original_metadata_after_distinct_runtime(self):
        failed, _ = self.entry_crash(); self.publish_failed(failed)
        result = self.run_observer()
        self.assertTrue(result['ok'])
        self.assertEqual(self.actions.count('test_cas_abandon_unsaved'), 1)
        self.assertEqual(json.loads(self.bank.read_text())['records']['33:11']['failed_history'][0]['pending'], self.pending)
        self.assertEqual(self.save.read_bytes(), b'untouched existing save')

    def test_historical_entry_game_clock_origin_stays_immutable_and_is_never_new_progress_proof(self):
        failed, _ = self.entry_crash()
        before = failed['steps'][0]['result']['before']
        before['sim_time_source'] = 'services.game_clock_service().now()'
        self.publish_failed(failed)
        immutable = self.failed.read_bytes()
        self.assertFalse(live_snapshot(before, '11', '22'))
        result = self.run_observer()
        self.assertTrue(result['ok'])
        self.assertFalse(result['save_reload_verified'])
        self.assertEqual(self.failed.read_bytes(), immutable)
        self.assertEqual(self.save.read_bytes(), b'untouched existing save')

    def test_current_game_clock_snapshot_only_authorizes_archive_metadata_without_progress_or_save_claim(self):
        base = self.request
        def legacy(state, action, **kwargs):
            result = base(state, action, **kwargs)
            if action == 'test_snapshot':
                result['sim_time_source'] = 'services.game_clock_service().now()'
            return result
        self.request = legacy
        result = self.run_observer()
        self.assertTrue(result['ok'])
        proof = json.loads(self.output.read_text())
        snapshot = next(row['result'] for row in proof['steps'] if row['action'] == 'test_snapshot')
        self.assertFalse(live_snapshot(snapshot, '11', '22'))
        self.assertIs(proof['clock_progress_verified'], False)
        self.assertIs(proof['simulation_progress_verified'], False)
        self.assertFalse(result['save_reload_verified'])
        self.assertEqual(self.actions, ['test_snapshot', 'cas_ui_diagnostics', 'test_cas_abandon_unsaved'])
        self.assertEqual(json.loads(self.bank.read_text())['records']['33:11']['failed_history'][0]['pending'], self.pending)
        self.assertEqual(self.save.read_bytes(), b'untouched existing save')

    def test_entry_crash_requires_changed_preserved_file_and_exact_entry_context(self):
        for mutation in ('changed-file', 'successful-inventory', 'other-sim', 'other-slot', 'no-entry', 'unchanged-crash'):
            with self.subTest(mutation=mutation):
                failed, crash = self.entry_crash()
                if mutation == 'changed-file': crash.write_bytes(b'changed crash')
                elif mutation == 'successful-inventory': failed['inventory_verified'] = True
                elif mutation == 'other-sim': failed['requested_sim_id'] = '99'
                elif mutation == 'other-slot': failed['steps'][0]['result']['before']['save_slot'] = 3
                elif mutation == 'no-entry': failed['steps'][0]['result']['ok'] = False
                elif mutation == 'unchanged-crash': failed['crash']['before'] = dict(failed['crash']['after'])
                self.publish_failed(failed)
                with self.assertRaises(ValueError): self.run_observer()
                self.assertEqual(self.actions, [])


class PrebindingArchiveTests(unittest.TestCase):
    """Independent native-return/terminal-owner/normal-exit wire receipts."""
    run_observer = AbandonTests.run_observer
    transport = AbandonTests.transport

    def setUp(self):
        from test_schema2_metadata_abandon import Schema2HostArchiveTests
        self.fixture=Schema2HostArchiveTests
        self.write_exit=lambda:self.fixture.write_exit(self)
        self.fixture.setUp(self)
        self.request=lambda state,action,**kwargs:self.fixture.request(self,state,action,**kwargs)
        old=json.loads(self.failed.read_text())['identity']
        checks={name:True for name in cas_abandon.PERSISTENCE_CHECKS}
        self.paused=dict(live(),sim={'id':'11','instanced':True},save_slot=0,
            sim_now_ticks='554',sim_time_source=SIM_TIME_SOURCE,
            persistence={'checks':checks,'errors':[],'persistence_verified_before_save':True,
                'save_reload_verified':False,'household_sim_ids':['11'],'persisted_household_sim_ids':['11']})
        final={name:self.paused[name] for name in ('client_id','zone_id','sim_now_ticks','sim_time_source')}
        final.update(sim_id='11',household_id='22',save_guid='33',minimum_ticks=30)
        baseline=dict(final,sim_now_ticks='100')
        self.receipt={'ok':False,'message':cas_abandon.PREBINDING_REFUSAL,'request_id':'e'*32,
            'request_state':'failed','save_reload_verified':False}
        self.failed_value={'schema':1,'operation':'semantic-cas-return-to-live','ok':False,
            'outcome':'live-return-cas-observation-unresolved','identity':old,'sim_id':'11','household_id':'22',
            'cas_request_id':'a'*32,'cas_bank_observe_request_id':'e'*32,'settle_ticks':30,
            'cas_bank_observation_receipt':copy.deepcopy(self.receipt),
            'cas_bank_observation_receipt_sha256':cas_abandon.digest(self.receipt),
            'checkpoint_sha256':self.transaction['checkpoint_sha256'],
            'expected_pending_sha256':self.transaction['transaction_sha256'],'cas_transaction_phase':'captured',
            'crash':{'outcome':'unchanged'},'owner_requests':[{'action':'cas_bank_observe','request_id':'e'*32}],
            'settled_snapshot':dict(copy.deepcopy(self.paused),clock_speed=1,sim_now_ticks='300'),
            'return_observation':{'ok':True,'live_return_verified':True,'cas_request_id':'a'*32,
                'appearance_persistence_verified':False,'commit_submission_verified':False,
                'baseline':baseline,'final':final,'advanced_ticks':454},
            'steps':[{'action':'test_pause','result':copy.deepcopy(self.paused)}],
            'form_bank_status':{'pending_schema':2,'pending_state':'captured','captured':True,'switch_pending':False,
                'cas_transaction':{'ok':True,'phase':'captured','expected_pending_sha256':self.transaction['transaction_sha256'],
                    'checkpoint_sha256':self.transaction['checkpoint_sha256'],'raw_return_sha256':None,'plan_sha256':None,
                    **{name:False for name in ('native_write_attempted','native_write_possible',
                        'metadata_commit_persisted','membership_or_traits_modified','writer_lease_present')}}}}
        self.failed_value.update({name:True for name in ('accept_submitted','accept_intent_observed',
            'cas_peer_disappearance_verified','clock_progress_verified','final_paused','live_context_verified',
            'return_metadata_completed','no_input_replay','cas_bank_observe_attempted')})
        self.failed_value.update({name:False for name in ('process_exit_verified','input_submitted',
            'form_bank_finish_attempted','form_bank_completion_verified','cas_bank_observation_verified',
            'appearance_persistence_verified','save_reload_verified')})
        self.observer_path=self.root/'original-observer-result.json'
        self.observer={'schema':1,'identity':copy.deepcopy(old),'original_request_id':'e'*32,
            'request_resubmitted':False,'result':copy.deepcopy(self.receipt),'source_proof_sha256':None}
        self.publish_failures()
        for index in range(17):(self.save.parent/('retained-backup-'+str(index)+'.bin')).write_bytes(bytes([index])*9)
        saves=cas_abandon.game_lifecycle.all_save_files(self.profile)
        self.assertEqual(len(saves),18)
        self.exit={'schema':1,'operation':'normal-exit-without-saving','outcome':'normal-exit-without-saving',
            'identity':copy.deepcopy(old),'requested_sim_id':'11','requested_household_id':'22','requested_save_guid':'33',
            'rewritten_normal_slots':{},'cas_shutdown_guard':{'safe':True,'blocking_native_requests':[]},
            'crash':{'outcome':'unchanged'},'before_all_saves':saves,'after_all_saves':copy.deepcopy(saves),
            'unsaved_exit_native_before':copy.deepcopy(self.paused),
            **{name:True for name in ('ok','normal_exit_verified','game_exit_verified',
                'save_files_unchanged_verified','exit_without_save_input_accepted')},
            **{name:False for name in ('final_process_alive','save_requested','save_and_exit_input_accepted',
                'save_completed_file_verified','save_reload_verified')}}
        self.write_exit()

    def publish_failures(self):
        self.failed.write_text(json.dumps(self.failed_value),encoding='utf-8');self.failed_hash=cas_abandon.sha256(self.failed)
        self.observer['source_proof_sha256']=self.failed_hash
        self.publish_observer()

    def publish_observer(self):
        self.observer_path.write_text(json.dumps(self.observer),encoding='utf-8')
        self.observer_sha=cas_abandon.sha256(self.observer_path)

    def invoke(self,**options):
        args={'allow_auto_save_slot_metadata_only':True,'unsaved_exit_proof':self.exit_path,
            'expected_unsaved_exit_proof_sha256':self.exit_sha,'observer_failure_proof':self.observer_path,
            'expected_observer_failure_sha256':self.observer_sha}
        args.update(options);return self.run_observer(**args)

    def test_certified_prebinding_refusal_archives_exact_seven_raw_originals_with_no_replay_or_appearance_save_writes(self):
        raw_hash=hashlib.sha256(json.dumps(self.pending,sort_keys=True,ensure_ascii=True,
            allow_nan=False,separators=(',',':')).encode('ascii')).hexdigest()
        envelope_hash=self.transaction['transaction_sha256']
        self.assertNotEqual(raw_hash,envelope_hash)
        self.assertNotEqual(raw_hash,cas_abandon.digest(self.pending))  # Real Unicode raw fields.
        self.assertEqual(raw_hash,self.failed_value['checkpoint_sha256'])
        self.assertEqual(envelope_hash,self.failed_value['expected_pending_sha256'])
        immutable={p:p.read_bytes() for p in (self.failed,self.observer_path,self.exit_path)}
        result=self.invoke();self.assertTrue(result['ok'])
        after=json.loads(self.bank.read_text());row=after['records']['33:11']
        retained=row['failed_history'][-1]
        self.assertEqual(retained['pending'],self.pending);self.assertEqual(retained['cas_transaction'],self.transaction)
        self.assertEqual(len(retained['pending']['original_owners']['stored']),7)
        self.assertEqual(row['bank'],self.data['records']['33:11']['bank'])
        self.assertEqual(after['records']['other:sim'],self.data['records']['other:sim'])
        self.assertEqual(self.actions,['test_snapshot','cas_ui_diagnostics','test_cas_abandon_unsaved'])
        for p,raw in immutable.items():self.assertEqual(p.read_bytes(),raw)
        proof=json.loads(self.output.read_text());self.assertTrue(proof['prebinding_refusal_recovery'])
        self.assertEqual(proof['pending_sha256'],cas_abandon.digest(self.pending))
        self.assertEqual(self.archive_values[0]['expected_pending_sha256'],cas_abandon.digest(self.pending))
        self.assertEqual(proof['observer_failure_proof_sha256'],self.observer_sha)
        for name in ('disk_slot_verified','save_reload_verified','clock_progress_verified','simulation_progress_verified'):
            self.assertIs(proof[name],False)

    def test_distinct_checkpoint_and_envelope_mismatches_refuse_before_any_native_request(self):
        original_failed=copy.deepcopy(self.failed_value)
        original_data=copy.deepcopy(self.data)
        for mode in ('failed-raw','failed-envelope','stored-raw','stored-checkpoint','stored-envelope','swapped'):
            self.failed_value=copy.deepcopy(original_failed)
            data=copy.deepcopy(original_data)
            transaction=data['records']['33:11']['cas_transaction']
            status=self.failed_value['form_bank_status']['cas_transaction']
            if mode=='failed-raw':
                self.failed_value['checkpoint_sha256']=status['checkpoint_sha256']='f'*64
            elif mode=='failed-envelope':
                self.failed_value['expected_pending_sha256']=status['expected_pending_sha256']='f'*64
            elif mode=='stored-raw':
                data['records']['33:11']['pending']['unknown_future_field']={'retained':7}
            elif mode=='stored-checkpoint':transaction['checkpoint_sha256']='f'*64
            elif mode=='stored-envelope':transaction['transaction_sha256']='f'*64
            else:
                self.failed_value['checkpoint_sha256']=status['checkpoint_sha256']=original_failed['expected_pending_sha256']
                self.failed_value['expected_pending_sha256']=status['expected_pending_sha256']=original_failed['checkpoint_sha256']
            self.publish_failures()
            self.bank.write_text(json.dumps(data),encoding='utf-8')
            before=self.bank.read_bytes()
            immutable={p:p.read_bytes() for p in (self.failed,self.observer_path,self.exit_path)}
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'exact retained checkpoint'):
                self.invoke()
            self.assertEqual(self.actions,[])
            self.assertEqual(self.bank.read_bytes(),before)
            for path,raw in immutable.items():self.assertEqual(path.read_bytes(),raw)

    def test_observer_proof_pairs_and_explicit_native_zero_optin_are_required(self):
        for args in ({'observer_failure_proof':None},{'expected_observer_failure_sha256':None},
            {'expected_observer_failure_sha256':'f'*64},{'unsaved_exit_proof':None},
            {'expected_unsaved_exit_proof_sha256':None},
            {'observer_failure_proof':None,'expected_observer_failure_sha256':None}):
            with self.subTest(args=args),self.assertRaises(ValueError):self.invoke(**args)
            self.assertEqual(self.actions,[])
        result=self.invoke(allow_auto_save_slot_metadata_only=False)
        self.assertFalse(result['ok']);self.assertNotIn('test_cas_abandon_unsaved',self.actions)

    def test_rehashed_wrong_uuid_ambiguity_replay_identity_source_or_nonprebinding_failure_refuse(self):
        original=copy.deepcopy(self.observer)
        for mode in ('uuid','unknown','running','completed','cancelled','resubmitted','pid','token','script','profile','source','reason'):
            self.observer=copy.deepcopy(original)
            if mode=='uuid':self.observer['original_request_id']='f'*32
            elif mode in ('unknown','running','completed','cancelled'):self.observer['result']['request_state']=mode
            elif mode=='resubmitted':self.observer['request_resubmitted']=True
            elif mode=='pid':self.observer['identity']['pid']=7
            elif mode=='token':self.observer['identity']['test_token']='f'*32
            elif mode=='script':self.observer['identity']['script_sha256']='f'*64
            elif mode=='profile':self.observer['identity']['profile']=str(self.original)
            elif mode=='source':self.observer['source_proof_sha256']='f'*64
            else:self.observer['result']['message']='Failed after native setter; unknown write outcome.'
            self.publish_observer()
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.invoke()
            self.assertEqual(self.actions,[])

    def test_native_live_pause_tenchecks_real_unpaused_progress_and_unwritten_status_cannot_be_forged(self):
        original=copy.deepcopy(self.failed_value)
        for mode in ('missing-sim','persistence','clock-origin','not-paused','not-playing','no-progress',
            'finish','raw-return','native-write','checkpoint','duplicate-observe'):
            self.failed_value=copy.deepcopy(original)
            if mode=='missing-sim':self.failed_value['steps'][0]['result'].pop('sim')
            elif mode=='persistence':self.failed_value['steps'][0]['result']['persistence']['checks']['manager_identity']=False
            elif mode=='clock-origin':self.failed_value['return_observation']['final']['sim_time_source']='services.game_clock_service().now()'
            elif mode=='not-paused':self.failed_value['steps'][0]['result']['clock_speed']=1
            elif mode=='not-playing':self.failed_value['settled_snapshot']['clock_speed']=0
            elif mode=='no-progress':self.failed_value['return_observation']['advanced_ticks']=0
            elif mode=='finish':self.failed_value['form_bank_finish_attempted']=True
            elif mode=='raw-return':self.failed_value['form_bank_status']['cas_transaction']['raw_return_sha256']='f'*64
            elif mode=='native-write':self.failed_value['form_bank_status']['cas_transaction']['native_write_possible']=True
            elif mode=='checkpoint':self.failed_value['checkpoint_sha256']='f'*64
            else:self.failed_value['owner_requests'].append(copy.deepcopy(self.failed_value['owner_requests'][0]))
            self.publish_failures()
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.invoke()
            self.assertEqual(self.actions,[])

    def test_normal_exit_saved_unknown_identity_cas_ambiguity_all18_changes_or_wrong_normal_slot_refuse(self):
        original=copy.deepcopy(self.exit)
        for mode in ('saved','save-button','alive','pid','guid','cas','after','count','normal-slot','native-sim'):
            self.exit=copy.deepcopy(original)
            if mode=='saved':self.exit['save_requested']=True
            elif mode=='save-button':self.exit['save_and_exit_input_accepted']=True
            elif mode=='alive':self.exit['final_process_alive']=None
            elif mode=='pid':self.exit['identity']['pid']=7
            elif mode=='guid':self.exit['requested_save_guid']='99'
            elif mode=='cas':self.exit['cas_shutdown_guard']['blocking_native_requests']=[{'state':'running'}]
            elif mode=='after':self.exit['after_all_saves']['Slot_00000002.save']['sha256']='f'*64
            elif mode=='count':self.exit['before_all_saves'].pop('retained-backup-0.bin');self.exit['after_all_saves']=copy.deepcopy(self.exit['before_all_saves'])
            elif mode=='normal-slot':
                self.exit['before_all_saves']['Slot_00000002.save']['sha256']='f'*64
                self.exit['after_all_saves']=copy.deepcopy(self.exit['before_all_saves'])
            else:self.exit['unsaved_exit_native_before']['sim']['id']='99'
            self.write_exit()
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.invoke()
            self.assertEqual(self.actions,[])

    def test_observed_journal_or_changed_slot_during_preflight_keeps_all_original_metadata(self):
        for journal in ({'state':'applying'},{'state':'raw-observed'}):
            data=copy.deepcopy(self.data);data['records']['33:11']['cas_transaction']['journal']=journal
            self.bank.write_text(json.dumps(data));before=self.bank.read_bytes()
            with self.assertRaises(ValueError):self.invoke()
            self.assertEqual(self.actions,[]);self.assertEqual(self.bank.read_bytes(),before)
        self.bank.write_text(json.dumps(self.data));base=self.request
        def changed(state,action,**kwargs):
            value=base(state,action,**kwargs)
            if action=='test_snapshot':self.save.write_bytes(b'new normal user save')
            return value
        self.request=changed;result=self.invoke()
        self.assertFalse(result['ok']);self.assertNotIn('test_cas_abandon_unsaved',self.actions)
        self.assertEqual(json.loads(self.bank.read_text())['records']['33:11']['pending'],self.pending)

    def test_pinned_observer_changed_after_initial_read_refuses_before_archive(self):
        base=self.request
        def changed(state,action,**kwargs):
            value=base(state,action,**kwargs)
            if action=='cas_ui_diagnostics':self.observer_path.write_text('{}')
            return value
        self.request=changed;result=self.invoke()
        self.assertFalse(result['ok']);self.assertNotIn('test_cas_abandon_unsaved',self.actions)

    def test_public_cli_requires_pair_and_normal_exit_before_identity_or_dispatch(self):
        base=['cas-abandon','--state','state.json','--sim-id','11','--household-id','22','--save-guid','33',
            '--slot-id','2','--failed-return-proof','failed.json','--expected-proof-sha256','d'*64,
            '--expected-save-sha256','e'*64,'--output','new.json']
        for extra in (['--observer-failure-proof','observer.json'],
            ['--expected-observer-failure-sha256','f'*64],
            ['--observer-failure-proof','observer.json','--expected-observer-failure-sha256','f'*64]):
            args=apex_cli.parser().parse_args(base+extra)
            with patch.object(apex_cli,'require_isolated'),patch.object(apex_cli,'verified_identity') as identity,patch.object(cas_abandon,'observe') as observe:
                with self.assertRaises(ValueError):apex_cli.execute(args)
                identity.assert_not_called();observe.assert_not_called()
        args=apex_cli.parser().parse_args(base+['--observer-failure-proof','observer.json',
            '--expected-observer-failure-sha256','f'*64,'--unsaved-exit-proof','exit.json',
            '--expected-unsaved-exit-proof-sha256','a'*64])
        with patch.object(apex_cli,'require_isolated'),patch.object(apex_cli,'verified_identity',return_value=self.identity),patch.object(cas_abandon,'observe',return_value={'ok':True}) as observe:
            self.assertTrue(apex_cli.execute(args)['ok'])
            self.assertEqual(observe.call_args.kwargs['observer_failure_proof'],Path('observer.json'))
            self.assertEqual(observe.call_args.kwargs['expected_observer_failure_sha256'],'f'*64)


if __name__ == '__main__': unittest.main()
