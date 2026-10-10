"""Independent real-receiver schema2 metadata archival fixtures; no game code."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import cas_bank_transaction as receiver, cas_commit_plan as primitive
from apex_core import form_bank, sim_data, test_driver
from test_form_bank_seal import SealFixture, SIM, HH, GUID, outfit
import test_cas_abandon as host_fixtures
import cas_abandon
from apex_core import form_appearance as appearance
import uuid


def pending_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        allow_nan=False, separators=(',', ':')).encode('utf-8')).hexdigest()


class Schema2SourceArchiveTests(SealFixture):
    def setUp(self):
        super().setUp()
        receiver._ACTIVE.clear(); receiver._CAPTURED.clear(); receiver._WRITER_LEASES.clear()
        self.addCleanup(receiver._ACTIVE.clear); self.addCleanup(receiver._CAPTURED.clear)
        self.addCleanup(receiver._WRITER_LEASES.clear)
        self.backend._APEX_GAME_THREAD_IDENT = threading.current_thread().ident
        self.backend._get_sim_info_by_id = lambda _id: self.sim
        self.prior_pid = self.identity['pid'] - 1
        for owner in self.forms.values():
            owner.physique += ' — Jéwélry'
            owner.blob += b'\xaa\x06\x07future!'
        self.sim.physique, self.sim.blob = self.forms[64].physique, self.forms[64].blob
        data = form_bank.load(self.bank_path)
        data['future_top_level'] = {'keep': ['unknown', 999]}
        data['records']['other:sim'] = {'unknown': 'keep another record'}
        data['records'][self.key]['hair_policy'] = {'enabled': False, 'future_setting': 'retain'}
        form_bank.save(self.bank_path, data)
        with patch.object(receiver.os, 'getpid', return_value=self.prior_pid), \
                patch.object(sim_data, 'snapshot', side_effect=AssertionError('full Sim serializer forbidden')):
            receiver.begin(self.backend, self.sim)
        self.original = copy.deepcopy(form_bank.load(self.bank_path))
        self.record = self.original['records'][self.key]
        self.argument = dict(expected_pending_sha256=pending_digest(self.record['pending']),
            expected_cas_transaction_sha256=primitive.digest(self.record['cas_transaction']),
            unsaved_exit_proof_sha256='f' * 64, failed_return_proof_sha256='e' * 64,
            prior_pid=self.prior_pid, slot_id=2, save_guid=GUID, household_id=HH,
            expected_save_sha256=self.target['expected_save_sha256'],
            allow_auto_save_slot_metadata_only=True)

    def invoke(self, argument=None):
        live = self.live(); live['save_slot'] = 0
        with patch.object(test_driver, 'snapshot', return_value=live), \
                patch.object(form_bank, '_old_process_absent', return_value=True), \
                patch.object(sim_data, 'snapshot', side_effect=AssertionError('full Sim serializer forbidden')):
            return form_bank.abandon_unsaved(self.backend, self.sim, argument or self.argument)

    def test_captured_no_serializer_seven_owner_archive_retains_exact_full_records_and_unknown_wire_bytes(self):
        saves, before_file = self.slot.read_bytes(), self.bank_path.read_bytes()
        result = self.invoke()
        self.assertTrue(result['abandoned']); self.assertTrue(result['cas_transaction_archived'])
        self.assertFalse(result['disk_slot_verified']); self.assertFalse(result['save_reload_verified'])
        self.assertFalse(result['native_write_attempted']); self.assertFalse(result['native_serializer_called'])
        after = form_bank.load(self.bank_path); row = after['records'][self.key]
        self.assertIsNone(row['pending']); self.assertIsNone(row['cas_transaction'])
        archived = row['failed_history'][-1]
        self.assertEqual(archived['pending'], self.record['pending'])
        self.assertEqual(archived['cas_transaction'], self.record['cas_transaction'])
        self.assertEqual(set(archived['pending']['original_owners']['stored']), {'1','2','4','8','16','32','64'})
        self.assertEqual(archived['unsaved_exit_proof_sha256'], 'f' * 64)
        self.assertEqual(archived['cas_transaction_sha256'], primitive.digest(self.record['cas_transaction']))
        stripped = copy.deepcopy(after); selected = stripped['records'][self.key]
        selected.pop('failed_history'); selected['pending'] = self.record['pending']
        selected['cas_transaction'] = self.record['cas_transaction']
        self.assertEqual(stripped, self.original)
        self.assertEqual(self.slot.read_bytes(), saves); self.assertEqual(self.writes, [])
        self.assertNotEqual(self.bank_path.read_bytes(), before_file); self.assertFalse(self.path.exists())
        # Same arguments cannot archive again or borrow the retained old bank.
        stable = self.bank_path.read_bytes()
        with self.assertRaises(ValueError): self.invoke()
        self.assertEqual(self.bank_path.read_bytes(), stable)

    def test_zero_slot_requires_explicit_boolean_optin_and_both_hash_boundaries(self):
        before = self.bank_path.read_bytes()
        for mutation in ('no-optin', 'false-optin', 'typed-optin', 'no-exit', 'no-transaction', 'bad-transaction'):
            arg = dict(self.argument)
            if mutation == 'no-optin': arg.pop('allow_auto_save_slot_metadata_only')
            elif mutation == 'false-optin': arg['allow_auto_save_slot_metadata_only'] = False
            elif mutation == 'typed-optin': arg['allow_auto_save_slot_metadata_only'] = 1
            elif mutation == 'no-exit': arg.pop('unsaved_exit_proof_sha256')
            elif mutation == 'no-transaction': arg.pop('expected_cas_transaction_sha256')
            else: arg['expected_cas_transaction_sha256'] = '0' * 64
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): self.invoke(arg)
            self.assertEqual(self.bank_path.read_bytes(), before)

    def test_any_journal_serializer_native_or_bank_commit_boundary_refuses_even_with_new_external_hash(self):
        for name, value in (('phase','observed'), ('journal',{'state':'applying','native_write_possible':True}),
                ('full_native_original_appended',True), ('metadata_commit',{'committed':True}),
                ('native_write_attempted',False)):
            data = copy.deepcopy(self.original); trans = data['records'][self.key]['cas_transaction']
            trans[name] = value
            self.bank_path.write_text(json.dumps(data), encoding='utf-8')
            arg = dict(self.argument, expected_cas_transaction_sha256=primitive.digest(trans))
            before = self.bank_path.read_bytes()
            with self.subTest(name=name), self.assertRaises(ValueError): self.invoke(arg)
            self.assertEqual(self.bank_path.read_bytes(), before); self.assertEqual(self.writes, [])

    def test_changed_record_or_hair_checkpoint_and_foreign_original_identity_remain_gated(self):
        for mutate in ('record','hair','household','checkpoint'):
            data = copy.deepcopy(self.original); row = data['records'][self.key]
            if mutate == 'record': row['new_unknown_value'] = 'retain refusal'
            elif mutate == 'hair': row['cas_transaction']['hair_checkpoint']['enabled'] = True
            elif mutate == 'household': row['pending']['original_owners']['identity']['household_id'] = '999'
            else: row['pending']['original_owners']['stored']['64']['physique']['value'] = 'altered'
            self.bank_path.write_text(json.dumps(data), encoding='utf-8'); before = self.bank_path.read_bytes()
            arg = dict(self.argument, expected_pending_sha256=pending_digest(row['pending']),
                expected_cas_transaction_sha256=primitive.digest(row['cas_transaction']))
            with self.subTest(mutation=mutate), self.assertRaises(ValueError): self.invoke(arg)
            self.assertEqual(self.bank_path.read_bytes(), before)

    def test_wrong_thread_or_manager_identity_and_interrupted_lease_never_archive(self):
        before = self.bank_path.read_bytes()
        self.backend._get_sim_info_by_id = lambda _id: copy.copy(self.sim)
        with self.assertRaises(ValueError): self.invoke()
        self.assertEqual(self.bank_path.read_bytes(), before)
        self.backend._get_sim_info_by_id = lambda _id: self.sim
        self.backend._APEX_GAME_THREAD_IDENT += 1
        with self.assertRaises(ValueError): self.invoke()
        self.assertEqual(self.bank_path.read_bytes(), before)
        self.backend._APEX_GAME_THREAD_IDENT = threading.current_thread().ident
        lease = receiver._lease_path(self.bank_path); lease.write_bytes(b'uncertain writer')
        with self.assertRaises(ValueError): self.invoke()
        self.assertEqual(lease.read_bytes(), b'uncertain writer'); self.assertEqual(self.bank_path.read_bytes(), before)

    def test_fresh_receiver_household_identity_cannot_be_replaced_by_patched_snapshot_labels(self):
        before = self.bank_path.read_bytes()
        self.sim.household_id = int(HH) + 1
        with self.assertRaises(ValueError): self.invoke()
        self.assertEqual(self.bank_path.read_bytes(), before); self.assertEqual(self.writes, [])

    def test_native_context_changes_at_atomic_metadata_boundary_and_stale_bank_are_refused(self):
        before = self.bank_path.read_bytes(); original_live = self.live(); original_live['save_slot'] = 0
        changed = dict(original_live, zone_id='999')
        with patch.object(test_driver, 'snapshot', side_effect=[original_live, changed]), \
                patch.object(form_bank, '_old_process_absent', return_value=True), self.assertRaises(ValueError):
            form_bank.abandon_unsaved(self.backend, self.sim, self.argument)
        self.assertEqual(self.bank_path.read_bytes(), before); self.assertEqual(self.writes, [])
        mutation = receiver._mutate
        def competing(backend, sim, transform):
            data = form_bank.load(self.bank_path); data['records']['other:sim']['new'] = 'preserve competing write'
            form_bank.save(self.bank_path, data)
            # A foreign record alone may coexist: expected whole-file version is
            # captured under receiver lease, preserving its new fields.
            return mutation(backend, sim, transform)
        with patch.object(receiver, '_mutate', side_effect=competing): result = self.invoke()
        self.assertTrue(result['abandoned'])
        self.assertEqual(form_bank.load(self.bank_path)['records']['other:sim']['new'], 'preserve competing write')


class Schema2HostArchiveTests(unittest.TestCase):
    transport = host_fixtures.AbandonTests.transport
    run_observer = host_fixtures.AbandonTests.run_observer

    def setUp(self):
        host_fixtures.AbandonTests.setUp(self)
        old = json.loads(self.failed.read_text(encoding='utf-8'))['identity']
        identity = {'runtime_pid': 8, 'sim_id': '11', 'household_id': '22', 'save_guid': '33'}
        stored = {str(lane): {'physique': appearance.encode('original Jéwélry ' + str(lane)),
            '__outfits__': appearance.encode(('protobuf', outfit(0, lane) + b'\xaa\x06\x07future!'))}
            for lane in (1,2,4,8,16,32,64)}
        self.pending = {'schema':2,'state':'captured','runtime_pid':8,'lane':'64','identity':identity,
            'original_owners':{'identity':copy.deepcopy(identity),'stored':stored,
                              'active':{'lane':'64','fields':copy.deepcopy(stored['64'])}}}
        row = self.data['records']['33:11']; row['pending'] = copy.deepcopy(self.pending)
        hair = {'enabled':False,'forms':{}}
        envelope = {'transaction_id':'9'*32,'identity':identity,'checkpoint_sha256':primitive.digest(self.pending),
                    'record_guard_sha256':receiver._record_guard(row),'hair_checkpoint_sha256':primitive.digest(hair)}
        self.transaction = dict(envelope,schema=1,owner_key='33:11',transaction_sha256=primitive.digest(envelope),
            hair_checkpoint=hair,prior_bank=copy.deepcopy(row['bank']),prior_hair_policy=None,
            phase='captured',journal=None,full_native_original_appended=False)
        row['cas_transaction'] = copy.deepcopy(self.transaction)
        self.bank.write_text(json.dumps(self.data),encoding='utf-8')
        self.native_slot = 0
        saves = {'Slot_00000002.save':{'sha256':self.save_hash,'bytes':len(self.save.read_bytes()),'mtime_ns':7}}
        self.exit = {'schema':1,'operation':'normal-discard-failed-cas-session','ok':True,
            'outcome':'normal-exit-without-saving','normal_exit_verified':True,'game_exit_verified':True,
            'save_files_unchanged_verified':True,'finalized':True,'discard_input_accepted':True,
            'save_submitted':False,'appearance_mutated':False,'cas_accept_repeated':False,'final_process_alive':False,
            'identity':old,'sim_id':'11','household_id':'22','save_guid':'33','retained_cas_request_id':'a'*32,
            'failed_return_proof':{'path':str(self.failed.resolve()),'sha256':self.failed_hash},
            'before_saves':saves,'after_saves':copy.deepcopy(saves)}
        self.exit_path = self.root/'normal-unsaved-exit.json'; self.write_exit()

    def write_exit(self):
        self.exit_path.write_text(json.dumps(self.exit),encoding='utf-8')
        self.exit_sha = hashlib.sha256(self.exit_path.read_bytes()).hexdigest()

    def invoke(self, **options):
        params = dict(allow_auto_save_slot_metadata_only=True,unsaved_exit_proof=self.exit_path,
                      expected_unsaved_exit_proof_sha256=self.exit_sha)
        params.update(options)
        return self.run_observer(**params)

    def request(self, _state, action, **kwargs):
        self.actions.append(action)
        request_id = uuid.uuid4().hex
        kwargs['transport']('/api/command',{'action':action,'request_id':request_id})
        if action == 'test_snapshot':
            from test_game_discard import live
            return dict(live(),sim={'id':'11','instanced':True},save_slot=self.native_slot)
        if action == 'cas_ui_diagnostics':
            from test_game_discard import diagnostic
            value = diagnostic();value['requests']=[];return value
        self.assertEqual(action,'test_cas_abandon_unsaved')
        argument = json.loads(kwargs['value'])['value'];self.archive_values.append(argument)
        rowdata=json.loads(self.bank.read_text(encoding='utf-8'));row=rowdata['records']['33:11']
        row.setdefault('failed_history',[]).append({'pending':row['pending'],'pending_sha256':argument['expected_pending_sha256'],
            'cas_transaction':row['cas_transaction'],'cas_transaction_sha256':argument['expected_cas_transaction_sha256'],
            'unsaved_exit_proof_sha256':argument['unsaved_exit_proof_sha256'],
            'failed_return_proof_sha256':argument['failed_return_proof_sha256']})
        row['pending']=None;row['cas_transaction']=None
        self.bank.write_text(json.dumps(rowdata),encoding='utf-8')
        if self.lose_response: raise OSError('ACK lost after archive')
        return {'ok':True,'abandoned':True,'appearance_mutated':False,'save_written':False,'cas_transaction_archived':True}

    def test_schema2_native_zero_full_history_retention_with_exact_exit_binding_and_no_slot_or_progress_claim(self):
        failed_bytes, exit_bytes = self.failed.read_bytes(), self.exit_path.read_bytes()
        result=self.invoke();self.assertTrue(result['ok'])
        for name in ('disk_slot_verified','save_reload_verified','clock_progress_verified','simulation_progress_verified'):
            self.assertIs(result[name],False)
        archived=json.loads(self.bank.read_text())['records']['33:11']['failed_history'][-1]
        self.assertEqual(archived['pending'],self.pending);self.assertEqual(archived['cas_transaction'],self.transaction)
        self.assertEqual(self.archive_values[0]['expected_cas_transaction_sha256'],primitive.digest(self.transaction))
        self.assertEqual(self.archive_values[0]['unsaved_exit_proof_sha256'],self.exit_sha)
        self.assertEqual(self.actions,['test_snapshot','cas_ui_diagnostics','test_cas_abandon_unsaved'])
        self.assertEqual(self.failed.read_bytes(),failed_bytes);self.assertEqual(self.exit_path.read_bytes(),exit_bytes)
        self.assertEqual(self.save.read_bytes(),b'untouched existing save')

    def test_schema2_zero_requires_explicit_optin_and_separate_pinned_exit(self):
        before=self.bank.read_bytes()
        for args in ({'unsaved_exit_proof':None},{'expected_unsaved_exit_proof_sha256':None},
                     {'expected_unsaved_exit_proof_sha256':'0'*64}):
            with self.subTest(args=args),self.assertRaises(ValueError):self.invoke(**args)
            self.assertEqual(self.actions,[]);self.assertEqual(self.bank.read_bytes(),before)
        result=self.invoke(allow_auto_save_slot_metadata_only=False)
        self.assertFalse(result['ok']);self.assertNotIn('test_cas_abandon_unsaved',self.actions)
        self.assertEqual(self.bank.read_bytes(),before)

    def test_rehashed_exit_wrong_pid_save_accept_replay_failed_receipt_and_file_identity_refuse_before_transport(self):
        original=copy.deepcopy(self.exit)
        for mutate in ('pid','save','accept','changed-after','failed-proof','request','file','unfinished'):
            self.exit=copy.deepcopy(original)
            if mutate=='pid':self.exit['identity']['pid']=7
            elif mutate=='save':self.exit['save_submitted']=True
            elif mutate=='accept':self.exit['cas_accept_repeated']=True
            elif mutate=='changed-after':self.exit['after_saves']['Slot_00000002.save']['sha256']='f'*64
            elif mutate=='failed-proof':self.exit['failed_return_proof']['sha256']='f'*64
            elif mutate=='request':self.exit['retained_cas_request_id']='f'*32
            elif mutate=='file':
                self.exit['before_saves']['Slot_00000002.save']['sha256']='f'*64
                self.exit['after_saves']=copy.deepcopy(self.exit['before_saves'])
            else:self.exit['final_process_alive']=None
            self.write_exit()
            with self.subTest(mutation=mutate),self.assertRaises(ValueError):self.invoke()
            self.assertEqual(self.actions,[])

    def test_observed_serializer_and_write_uncertainty_cannot_clear_modern_journal(self):
        for name,value in (('phase','observed'),('journal',{'state':'applying'}),
                           ('full_native_original_appended',True),('metadata_commit',{'committed':True})):
            data=copy.deepcopy(self.data);data['records']['33:11']['cas_transaction'][name]=value
            self.bank.write_text(json.dumps(data),encoding='utf-8');before=self.bank.read_bytes()
            with self.subTest(name=name),self.assertRaises(ValueError):self.invoke()
            self.assertEqual(self.actions,[]);self.assertEqual(self.bank.read_bytes(),before)

    def test_journal_change_during_native_preflight_is_retained_without_archive_submission(self):
        original=self.request
        def changed(state,action,**kwargs):
            result=original(state,action,**kwargs)
            if action=='cas_ui_diagnostics':
                data=json.loads(self.bank.read_text());data['records']['33:11']['cas_transaction']['phase']='observed'
                self.bank.write_text(json.dumps(data),encoding='utf-8')
            return result
        self.request=changed
        result=self.invoke();self.assertFalse(result['ok']);self.assertNotIn('test_cas_abandon_unsaved',self.actions)
        self.assertEqual(json.loads(self.bank.read_text())['records']['33:11']['cas_transaction']['phase'],'observed')

    def test_lost_archive_ack_retains_original_owner_uuid_and_full_history_without_replay(self):
        self.lose_response=True;result=self.invoke();self.assertFalse(result['ok'])
        proof=json.loads(self.output.read_text());self.assertTrue(proof['archive_submitted'])
        self.assertEqual(proof['owner_requests'][-1]['action'],'test_cas_abandon_unsaved')
        self.assertEqual(self.actions.count('test_cas_abandon_unsaved'),1)
        archived=json.loads(self.bank.read_text())['records']['33:11']['failed_history'][-1]
        self.assertEqual(archived['cas_transaction'],self.transaction)
        self.output=self.root/'fresh-attempt.json'
        with self.assertRaises(ValueError):self.invoke()
        self.assertEqual(self.actions.count('test_cas_abandon_unsaved'),1)


class ArchiveCompletionTests(unittest.TestCase):
    """An independent delayed server with a real temp-file metadata write.

    Run the actual owned_request transport, including its initial two-second
    wait. The server loses that response, keeps one UUID and publishes the
    completion later; no mock manufactures success in the archive observer.
    """
    write_exit = Schema2HostArchiveTests.write_exit

    def setUp(self):
        Schema2HostArchiveTests.setUp(self)
        self.now = 0.0
        self.completed_at = 5.5
        self.commands = []
        self.status_ids = []
        self.observed_timeouts = []
        self.archive_id = None
        self.terminal_state = 'completed'
        self.status_fault = None
        self.identity_fault = None
        self.temporary_loss = False
        self.status_loss_used = False
        self.unknown_forever = False
        self.failed_bytes = self.failed.read_bytes()
        self.exit_bytes = self.exit_path.read_bytes()
        self.original_poll = cas_abandon.apex_cli.poll_request

    def pause(self, duration):
        self.assertGreaterEqual(duration, 0)
        self.now += duration

    def server(self, path, query=None, timeout=12):
        self.observed_timeouts.append(timeout)
        if path == '/api/bridge':
            result = dict(self.identity, alarm_ready=True, core_tick_ready=True)
            if self.identity_fault is not None and self.now >= 1:
                result[self.identity_fault] = {'pid': 99, 'test_token': 'f' * 32,
                    'script_sha256': 'f' * 64}[self.identity_fault]
            return result
        if path == '/api/command':
            action, owner = query['action'], query['request_id']
            self.commands.append((action, owner))
            # The journal must already own this UUID before server acceptance.
            retained = json.loads(self.output.read_text(encoding='utf-8'))
            self.assertEqual(retained['owner_requests'][-1], {'action': action, 'request_id': owner})
            if action == 'test_snapshot':
                from test_game_discard import live
                return dict(live(), sim={'id': '11', 'instanced': True}, save_slot=0,
                            request_id=owner, request_state='completed')
            if action == 'cas_ui_diagnostics':
                from test_game_discard import diagnostic
                result = diagnostic(); result['requests'] = []
                return dict(result, request_id=owner, request_state='completed')
            self.assertEqual(action, 'test_cas_abandon_unsaved')
            self.assertIsNone(self.archive_id)
            self.archive_id = owner
            argument = json.loads(query['value'])['value']
            self.assertEqual(argument['expected_pending_sha256'], pending_digest(self.pending))
            self.assertEqual(argument['expected_cas_transaction_sha256'], primitive.digest(self.transaction))
            data = json.loads(self.bank.read_text(encoding='utf-8')); row = data['records']['33:11']
            row.setdefault('failed_history', []).append({'pending': row['pending'],
                'cas_transaction': row['cas_transaction'],
                'pending_sha256': argument['expected_pending_sha256'],
                'cas_transaction_sha256': argument['expected_cas_transaction_sha256'],
                'failed_return_proof_sha256': argument['failed_return_proof_sha256'],
                'unsaved_exit_proof_sha256': argument['unsaved_exit_proof_sha256']})
            row['pending'] = None; row['cas_transaction'] = None
            self.bank.write_text(json.dumps(data), encoding='utf-8')
            raise OSError('Actual metadata archived; initial response lost.')
        self.assertEqual(path, '/api/requests/status')
        owner = query['request_id']; self.status_ids.append(owner)
        self.assertEqual(owner, self.archive_id)
        if self.temporary_loss and self.now >= 2.25 and not self.status_loss_used:
            self.status_loss_used = True
            raise OSError('A read-only status response was lost.')
        state = 'unknown' if self.unknown_forever else 'running' if self.now < self.completed_at else self.terminal_state
        row = {'request_id': owner, 'state': state}
        if self.status_fault == 'wrong-row-uuid': row['request_id'] = 'f' * 32
        elif self.status_fault == 'untyped-state': row['state'] = ['completed']
        if state in ('completed', 'failed', 'cancelled'):
            # Even a lying success body cannot make failed/cancelled terminal
            # states succeed. This result acknowledges only metadata archival.
            row['result'] = {'ok': True, 'abandoned': True, 'appearance_mutated': False,
                'save_written': False, 'cas_transaction_archived': True}
            if self.status_fault == 'wrong-result-uuid': row['result']['request_id'] = 'f' * 32
            elif self.status_fault == 'untyped-ok': row['result']['ok'] = 1
        return row

    def observe(self, seconds=30, alive=None, request=None):
        def initial_poll(owner, duration, transport=None):
            return self.original_poll(owner, duration, transport=transport,
                monotonic=lambda: self.now, pause=self.pause)
        def verified(_state, transport):
            return transport('/api/bridge')
        with patch.object(cas_abandon.reusable_profile, 'load', return_value=(self.root / 'state.json',
                self.journal, self.profile, self.original)), \
                patch.object(cas_abandon.apex_cli, 'verified_identity', side_effect=verified), \
                patch.object(cas_abandon.apex_cli, 'poll_request', side_effect=initial_poll):
            return cas_abandon.observe(self.root / 'state.json', self.output, self.identity,
                request or cas_abandon.apex_cli.owned_request, self.failed, self.failed_hash,
                self.save_hash, '11', '22', '33', 2, seconds=seconds,
                alive=alive or (lambda pid: pid != 8), transport=self.server,
                monotonic=lambda: self.now, pause=self.pause,
                allow_auto_save_slot_metadata_only=True, unsaved_exit_proof=self.exit_path,
                expected_unsaved_exit_proof_sha256=self.exit_sha)

    def preserved_without_replay(self):
        self.assertEqual([action for action, _id in self.commands],
                         ['test_snapshot', 'cas_ui_diagnostics', 'test_cas_abandon_unsaved'])
        self.assertEqual(set(self.status_ids), {self.archive_id})
        self.assertEqual(self.failed.read_bytes(), self.failed_bytes)
        self.assertEqual(self.exit_path.read_bytes(), self.exit_bytes)
        self.assertEqual(self.save.read_bytes(), b'untouched existing save')
        data = json.loads(self.bank.read_text(encoding='utf-8')); row = data['records']['33:11']
        self.assertEqual(row['failed_history'][-1]['pending'], self.pending)
        self.assertEqual(row['failed_history'][-1]['cas_transaction'], self.transaction)
        self.assertEqual(row['bank'], self.data['records']['33:11']['bank'])
        self.assertIsNone(row['pending']); self.assertIsNone(row['cas_transaction'])
        return json.loads(self.output.read_text(encoding='utf-8'))

    def test_response_lost_after_metadata_write_completes_same_uuid_beyond_initial_wait_and_preserves_proofs(self):
        result = self.observe()
        self.assertTrue(result['ok']); self.assertGreaterEqual(self.now, 5.5)
        self.assertLess(self.now, 30)
        proof = self.preserved_without_replay()
        self.assertEqual(proof['archive_request_id'], self.archive_id)
        self.assertGreater(proof['request_status_poll_count'], 8)
        self.assertTrue(proof['failed_history_retained_verified'])
        initial = next(x['result'] for x in proof['steps'] if x['action'] == 'test_cas_abandon_unsaved')
        self.assertEqual(initial['outcome'], 'unresolved')
        completed = [x['result'] for x in proof['steps'] if x['action'] == 'completed-owner:test_cas_abandon_unsaved']
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0]['request_id'], self.archive_id)

    def test_unknown_status_uses_whole_deadline_then_retains_uuid_without_replaying_consumed_pending(self):
        self.unknown_forever = True
        result = self.observe(seconds=4)
        self.assertFalse(result['ok']); self.assertEqual(self.now, 4)
        self.assertTrue(all(0 < value <= 2 for value in self.observed_timeouts))
        proof = self.preserved_without_replay()
        self.assertEqual(proof['archive_request_id'], self.archive_id)
        historical = self.output
        immutable = historical.read_bytes(); self.output = self.root / 'do-not-replay.json'
        with self.assertRaises(ValueError): self.observe(seconds=4)
        self.assertEqual(len(self.commands), 3)
        self.assertEqual(historical.read_bytes(), immutable)

    def test_wrong_status_uuid_refuses_already_written_archive_without_resubmission(self):
        self.status_fault = 'wrong-row-uuid'
        result = self.observe(); self.assertFalse(result['ok'])
        proof = self.preserved_without_replay()
        self.assertIn('another owner UUID', proof['error'])

    def test_wrong_terminal_body_uuid_refuses_success_and_retains_archive_identity(self):
        self.status_fault = 'wrong-result-uuid'
        result = self.observe(); self.assertFalse(result['ok'])
        proof = self.preserved_without_replay()
        self.assertIn('another owner UUID', proof['error'])

    def test_typed_failed_and_cancelled_states_never_borrow_success_body(self):
        self.terminal_state = 'failed'
        result = self.observe(); self.assertFalse(result['ok'])
        self.preserved_without_replay()
        self.setUp()
        self.terminal_state = 'cancelled'
        result = self.observe(); self.assertFalse(result['ok'])
        self.preserved_without_replay()

    def test_nonboolean_terminal_success_is_refused(self):
        self.status_fault = 'untyped-ok'
        result = self.observe(); self.assertFalse(result['ok'])
        self.preserved_without_replay()

    def test_any_pinned_pid_token_or_script_change_during_poll_refuses_without_replay(self):
        for field in ('pid', 'test_token', 'script_sha256'):
            if field != 'pid': self.setUp()
            self.identity_fault = field
            result = self.observe(); self.assertFalse(result['ok'])
            proof = self.preserved_without_replay()
            self.assertIn('identity changed', proof['error'])
            self.assertLess(self.now, self.completed_at)

    def test_prior_pid_reappearance_and_unknown_current_process_refuse_status_reads(self):
        result = self.observe(alive=lambda pid: self.now >= 1 if pid == 8 else True)
        self.assertFalse(result['ok']); self.preserved_without_replay()
        self.setUp()
        result = self.observe(alive=lambda pid: False if pid == 8 else None if self.now >= 1 else True)
        self.assertFalse(result['ok']); self.preserved_without_replay()

    def test_temporary_read_only_status_loss_is_polled_same_uuid_until_completion(self):
        self.temporary_loss = True
        result = self.observe(); self.assertTrue(result['ok']); self.assertTrue(self.status_loss_used)
        self.preserved_without_replay()

    def test_runtime_change_during_terminal_status_read_refuses_stale_completed_ack(self):
        original = self.server
        def changed(path, query=None, timeout=12):
            result = original(path, query, timeout=timeout)
            if path == '/api/requests/status' and result.get('state') == 'completed':
                self.identity_fault = 'script_sha256'
            return result
        self.server = changed
        result = self.observe(); self.assertFalse(result['ok'])
        proof = self.preserved_without_replay()
        self.assertIn('identity changed', proof['error'])

    def test_transport_cannot_resubmit_original_uuid_even_when_its_response_is_lost(self):
        def repeated(state, action, **kwargs):
            if action != 'test_cas_abandon_unsaved':
                return cas_abandon.apex_cli.owned_request(state, action, **kwargs)
            owner = 'b' * 32
            query = dict(action=action, request_id=owner, value=kwargs['value'])
            try:
                kwargs['transport']('/api/command', query)
            except OSError:
                kwargs['transport']('/api/command', query)
            raise AssertionError('Second submission must be refused before transport.')
        result = self.observe(request=repeated); self.assertFalse(result['ok'])
        proof = json.loads(self.output.read_text())
        self.assertIn('no replay', proof['error'])
        self.assertEqual(self.commands.count(('test_cas_abandon_unsaved', 'b' * 32)), 1)
        self.assertEqual(self.archive_id, 'b' * 32)
        self.assertEqual(self.failed.read_bytes(), self.failed_bytes)
        self.assertEqual(self.exit_path.read_bytes(), self.exit_bytes)


if __name__ == '__main__': unittest.main()
