"""Actual receiver/primitive bodies + actual Rust C ABI, temporary bank only."""
import copy
import ctypes
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
import uuid as uuid_module
from unittest.mock import patch
from types import SimpleNamespace as Obj

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / '.work/v340-bank-async-stage'
sys.path.insert(0, str(ROOT / 'Source'))
sys.path.insert(1, str(ROOT / 'tests'))
from apex_core import bank_worker, cas_bank_transaction as bank, cas_commit_plan as primitive, form_bank
from apex_core.command_queue import CommandQueue, OwnerContinuation
import test_cas_bank_transaction as receiver_fixtures

DLL = STAGE / 'target/debug/apex_bank_prepare_stage.dll'


@unittest.skipUnless(DLL.is_file(), 'Private staged Rust C ABI build required')
class PrepareAsyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.TemporaryDirectory()
        cls.lib = ctypes.CDLL(str(DLL))
        cls.lib.ApexBankBind.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
        cls.lib.ApexBankBind.restype = ctypes.c_uint64
        cls.lib.ApexBankSubmit.argtypes = [ctypes.c_uint64, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t]
        cls.lib.ApexBankSubmit.restype = ctypes.c_uint64
        cls.lib.ApexBankPoll.argtypes = [ctypes.c_uint64, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_uint64]
        cls.lib.ApexBankPoll.restype = ctypes.c_void_p
        cls.lib.ApexBankFree.argtypes = [ctypes.c_void_p]
        cls.held_lib = ctypes.PyDLL(str(DLL))
        cls.held_lib.ApexBankSubmit.argtypes = cls.lib.ApexBankSubmit.argtypes
        cls.held_lib.ApexBankSubmit.restype = ctypes.c_uint64
        cls.held_lib.ApexBankPollCopy.argtypes = cls.lib.ApexBankPoll.argtypes
        cls.held_lib.ApexBankPollCopy.restype = ctypes.c_char_p
        encoded = cls.root.name.encode('utf-8')
        cls.handle = cls.lib.ApexBankBind(encoded, len(encoded))
        assert cls.handle

    @classmethod
    def tearDownClass(cls):
        cls.root.cleanup()

    def setUp(self):
        self.fixture = fx = receiver_fixtures.CasBankReceiverTests('runTest')
        fx.setUp()
        self.addCleanup(fx.doCleanups)
        fx.backend._data_directory = lambda: self.root.name
        fx.backend._household_sim_infos = lambda sim: (fx.sim,)
        self.zone = Obj(is_zone_running=True, is_in_build_buy=False)
        self.household = Obj(id=fx.sim.household_id, sim_info_gen=lambda: iter((fx.sim,)))
        fx.backend.services.current_zone = lambda: self.zone
        fx.backend.services.active_household = lambda: self.household
        fx.path, fx.key = form_bank.context(fx.backend, fx.sim)
        # Every test starts a new disposable bank; worker receipts keep their
        # original UUIDs and cannot adopt these new transactions' input.
        for name in ('form_bank.json', 'form_bank.pending', '.form_bank.json.cas-writer.lock'):
            path = Path(self.root.name) / name
            if path.exists():
                path.unlink()
        form_bank.save(fx.path, fx.initial)
        self.generation = [1]
        self.operations = []
        self.binding = bank_worker.NativeBinding(self.root.name, self.submit, self.poll)

    def submit(self, header, payload):
        self.operations.append(json.loads(header)['operation'])
        return int(self.lib.ApexBankSubmit(self.handle, header, len(header), payload, len(payload)))

    def poll(self, header, ticket):
        result = self.lib.ApexBankPoll(self.handle, header, len(header), ticket)
        self.assertTrue(result)
        try:
            return ctypes.string_at(result)
        finally:
            self.lib.ApexBankFree(result)

    def observed(self, changed=False, hair=False):
        fx = self.fixture
        if hair:
            fx.enable_hair()
        fx.begin()
        if changed:
            fx.edit(2)
        fx.observe()
        return dict(expected_pending_sha256=fx.epoch,
                    expected_raw_return_sha256=fx.observation['raw_return_sha256'],
                    dispositions=[dict(lane='2', action='accept-returned')] if changed else [])

    def start(self, argument, uuid=None):
        fx = self.fixture
        return bank_worker.PrepareAction(fx.backend, fx.sim, argument, self.binding, uuid or uuid_module.uuid4().hex,
                                        native_probe=lambda backend: self.generation[0])

    def observed_named(self, hair=False):
        from apex_core import native_cas_engine
        fx = self.fixture
        if hair:
            fx.enable_hair()
        returned = fx.named_native_return()
        active = copy.deepcopy(next(row for row in returned['owners'] if row['owner_id'] == 'native/64'))
        active['owner_id'] = 'active/64'
        returned['owners'].append(active)
        fx.begin()
        returned['checkpoint_epoch'] = fx.epoch
        self.native_current = copy.deepcopy(returned)
        self.enterContext(patch.object(native_cas_engine, 'owns_return', return_value=True))
        self.enterContext(patch.object(native_cas_engine, 'returned_owners',
                                      side_effect=lambda *args: copy.deepcopy(self.native_current)))
        fx.observe()
        return dict(expected_pending_sha256=fx.epoch,
            expected_raw_return_sha256=fx.observation['raw_return_sha256'], dispositions=[],
            named_dispositions=[dict(owner_id=row['owner_id'], action='accept-returned')
                for row in returned['owners'] if row['owner_id'].startswith('ghost/')])

    def finish(self, action, forbidden_io=True):
        # No owner storage path may run after the async route is entered.
        paths = [patch.object(bank, name, side_effect=AssertionError('Owner full-bank I/O: ' + name))
                 for name in ('_read', '_mutate', 'atomic_save')]
        for item in paths:
            item.start()
            self.addCleanup(item.stop)
        deadline = time.perf_counter() + 5
        result = action
        while isinstance(result, OwnerContinuation) and time.perf_counter() < deadline:
            result = result.resume()
            if isinstance(result, OwnerContinuation):
                time.sleep(.001)  # test caller only; no production wait/join
        for item in paths:
            item.stop()
        self.assertNotIsInstance(result, OwnerContinuation)
        return result

    def parity(self, changed=False, hair=False, named=False):
        fx = self.fixture
        if named:
            argument = self.observed_named(hair=hair)
        else:
            argument = self.observed(changed=changed, hair=hair)
        before = fx.path.read_bytes()
        key = next(iter(bank._ACTIVE))
        instance = bank._ACTIVE[key]
        state = {name: copy.deepcopy(getattr(instance, name)) for name in
                 ('state', 'document', 'journal_sha256', 'retained_document', 'plan')}
        expected = bank.prepare(fx.backend, fx.sim, argument)
        planned = copy.deepcopy(instance.document)
        for name, value in state.items():
            setattr(instance, name, value)
        fx.path.write_bytes(before)
        result = self.finish(self.start(argument))
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['plan_sha256'], expected['plan_sha256'])
        self.assertEqual(instance.document, planned)
        self.assertEqual(fx.record()['cas_transaction']['journal'], planned)
        self.assertEqual(fx.data()['records']['30:99'], fx.foreign)
        self.assertEqual(fx.native_writes, [])
        self.assertEqual(self.operations, ['read-selected', 'plan-base'] +
                         (['plan-hair'] if hair else []) + (['plan-named'] if named else []))
        self.assertTrue(all(value >= 0 for value in result['owner_phase_costs'].values()))
        return result

    def test_actual_no_edit_prepare_matches_synchronous_result_and_never_uses_owner_bank_io(self):
        self.parity()

    def test_actual_changed_prepare_matches_every_complete_field_and_plan_hash(self):
        self.parity(changed=True)

    def test_unknown_journal_noncanonical_numeric_spelling_retains_exact_bytes_and_python_digest(self):
        fx = self.fixture
        argument = self.observed()
        instance = next(iter(bank._ACTIVE.values()))
        document = copy.deepcopy(instance.document)
        document['future_numeric_metadata'] = [1000.0, 0, -0.0, 1e-5, 1e16, 5e-324]
        data = json.loads(fx.path.read_bytes())
        data['records'][fx.key]['cas_transaction']['journal'] = document
        original = b'"future_numeric_metadata":[1000.0,0,-0.0,1e-05,1e+16,5e-324]'
        retained = b'"future_numeric_metadata":[1e+03,-0,-0.000,0.0000100,1.000E+0016,4.9406564584124654e-324]'
        raw = json.dumps(data, sort_keys=True, separators=(',', ':')).encode('ascii')
        self.assertIn(original, raw)
        fx.path.write_bytes(raw.replace(original, retained))
        instance.document = copy.deepcopy(document)
        instance.retained_document = copy.deepcopy(document)
        instance.journal_sha256 = primitive.digest(document)
        result = self.finish(self.start(argument))
        self.assertTrue(result['ok'], result)
        self.assertIn(retained, fx.path.read_bytes())
        self.assertEqual(primitive.digest(fx.record()['cas_transaction']['journal']), instance.journal_sha256)

    def test_cas_native_peer_refuses_before_any_worker_ticket(self):
        from apex_core import cas_ui
        argument = self.observed()
        before = self.fixture.path.read_bytes()
        with patch.object(cas_ui, 'diagnostics', return_value={'native_peers': ['actual-CAS-peer-fixture']}):
            with self.assertRaisesRegex(ValueError, 'CAS still owns'):
                self.start(argument)
        self.assertEqual(self.operations, [])
        self.assertEqual(self.fixture.path.read_bytes(), before)

    def test_ready_receipt_cannot_plan_after_leaving_running_live(self):
        action = self.start(self.observed())
        self.zone.is_in_build_buy = True
        result = self.finish(action)
        self.assertFalse(result['ok'])
        self.assertEqual(self.operations, ['read-selected'])
        self.assertEqual(self.fixture.native_writes, [])

    def test_same_generation_native_canonical_active_named_unknown_changes_before_prepare_refuse(self):
        argument = self.observed_named()
        original = copy.deepcopy(self.native_current)
        for owner_id in ('native/2', 'active/64', 'ghost/ghost_ghost'):
            self.native_current = copy.deepcopy(original)
            row = next(row for row in self.native_current['owners'] if row['owner_id'] == owner_id)
            row['future_native_unknown_field'] = {'opaque': ['same generation', 184467440737095516160]}
            with self.subTest(owner_id=owner_id), self.assertRaisesRegex(ValueError, 'changed after observation'):
                self.start(argument)
        self.assertEqual(self.generation, [1])
        self.assertEqual(self.operations, [])
        self.assertEqual(self.fixture.native_writes, [])

    def test_same_generation_named_change_while_waiting_does_not_adopt_fresh_baseline(self):
        action = self.start(self.observed_named())
        row = next(row for row in self.native_current['owners'] if row['owner_id'] == 'ghost/ghost_ghost')
        row['future_native_unknown_field'] = {'opaque': 'changed while read was pending'}
        result = self.finish(action)
        self.assertFalse(result['ok'])
        self.assertIn('changed after observation', result['message'])
        self.assertEqual(self.operations, ['read-selected'])
        self.assertEqual(self.generation, [1])
        self.assertEqual(self.fixture.native_writes, [])

    def test_entering_editor_during_complete_native_export_refuses_before_ticket(self):
        from apex_core import native_cas_engine, cas_ui
        argument = self.observed_named()
        peers = []
        def export(*args):
            peers.append('editor-entered-during-multi-page-export')
            return copy.deepcopy(self.native_current)
        with patch.object(native_cas_engine, 'returned_owners', side_effect=export), \
                patch.object(cas_ui, 'diagnostics', side_effect=lambda: {'native_peers': list(peers)}):
            with self.assertRaisesRegex(ValueError, 'CAS still owns'):
                self.start(argument)
        self.assertEqual(self.operations, [])

    def test_same_generation_named_change_after_plan_submission_refuses_durable_ack_without_replay(self):
        argument = self.observed_named()
        submit = self.binding.submit_call
        def mutate_after_submit(header, payload):
            ticket = submit(header, payload)
            if json.loads(header)['operation'] == 'plan-base':
                row = next(row for row in self.native_current['owners'] if row['owner_id'] == 'ghost/ghost_ghost')
                row['future_native_unknown_field'] = {'opaque': 'edited after plan submission'}
            return ticket
        self.binding.submit_call = mutate_after_submit
        result = self.finish(self.start(argument))
        self.assertFalse(result['ok'])
        self.assertIn('changed after observation', result['message'])
        self.assertEqual(self.operations, ['read-selected', 'plan-base'])
        self.assertEqual(self.fixture.native_writes, [])
        self.assertFalse(result['automatic_replay_allowed'])

    def test_async_alien_plan_is_consumed_by_existing_commit_without_touching_vampire_or_other_forms(self):
        from apex_core import form_appearance as appearance
        fx = self.fixture
        result = self.finish(self.start(self.observed(changed=True)))
        self.assertTrue(result['ok'], result)
        instance = next(iter(bank._ACTIVE.values()))
        expected = copy.deepcopy(instance.plan['desired'])
        committed = bank.commit(fx.backend, fx.sim,
            dict(expected_pending_sha256=fx.epoch, expected_plan_sha256=result['plan_sha256']))
        self.assertTrue(committed['ok'], committed)
        self.assertEqual(fx.record()['bank'], expected)
        for lane, fields in expected.items():
            self.assertEqual(appearance.fingerprint(appearance.packed(fx.backend, fx.forms[int(lane)])),
                             appearance.fingerprint(fields))
        self.assertEqual(fx.forms[2].physique, 'accepted-2')
        self.assertEqual(fx.forms[4].physique, 'original-4')
        self.assertEqual(fx.data()['records']['30:99'], fx.foreign)

    def test_actual_enabled_hair_keeps_its_separate_durable_plan_transition(self):
        self.parity(hair=True)

    def test_actual_named_same_genus_variants_keep_their_separate_durable_plan_transition(self):
        self.parity(named=True)

    def test_actual_hair_and_named_prepare_preserves_all_three_ordered_journal_barriers(self):
        self.parity(hair=True, named=True)

    def test_loaded_copy_string_abi_with_gil_retained_completes_actual_prepare(self):
        def submit(header, payload):
            self.operations.append(json.loads(header)['operation'])
            return int(self.held_lib.ApexBankSubmit(self.handle, header, len(header), payload, len(payload)))
        def poll(header, ticket):
            return self.held_lib.ApexBankPollCopy(self.handle, header, len(header), ticket)
        self.binding = bank_worker.NativeBinding(self.root.name, submit, poll)
        self.parity()

    def test_actual_prepare_runs_end_to_end_in_canonical_queue_and_allows_unrelated_actions(self):
        argument = self.observed(changed=True)
        queue = CommandQueue()
        identifier = queue.submit({'action': 'cas_bank_prepare'}, request_id=uuid_module.uuid4().hex)['request_id']
        calls, gate = [], [False]
        actual_poll = self.binding.poll_call
        self.binding.poll_call = lambda header, ticket: (actual_poll(header, ticket) if gate[0] else
                                                        b'{"ok":true,"state":"pending"}')
        def execute(payload):
            calls.append(payload['action'])
            return self.start(argument, uuid=identifier) if payload['action'] == 'cas_bank_prepare' else {'ok': True}
        queue.drain(execute, max_commands=1)
        self.assertFalse(queue.records[identifier]['event'].is_set())
        other = queue.submit({'action': 'unrelated_interaction'})['request_id']
        queue.drain(execute, max_commands=2, budget_seconds=1)
        self.assertEqual(queue.status(other)['state'], 'completed')
        self.assertEqual(queue.status(identifier)['state'], 'running')
        gate[0] = True
        deadline = time.perf_counter() + 5
        while queue.status(identifier)['state'] == 'running' and time.perf_counter() < deadline:
            queue.drain(execute, max_commands=1)
            time.sleep(.001)
        self.assertEqual(queue.status(identifier)['state'], 'completed', queue.status(identifier))
        self.assertTrue(queue.status(identifier)['result']['async_prepare'])
        self.assertEqual(calls.count('cas_bank_prepare'), 1)

    def test_complete_native_edit_during_worker_wait_is_not_overwritten(self):
        argument = self.observed()
        action = self.start(argument)
        self.fixture.edit(2, value='newer-live-edit')
        result = self.finish(action)
        self.assertFalse(result['ok'])
        self.assertIn('before-image', result['message'])
        self.assertEqual(self.fixture.forms[2].physique, 'newer-live-edit')
        self.assertEqual(self.fixture.native_writes, [])

    def test_generation_change_during_wait_retains_durable_originals_and_no_replay(self):
        action = self.start(self.observed())
        self.generation[0] += 1
        result = self.finish(action)
        self.assertFalse(result['ok'])
        self.assertIn('generation', result['message'])
        with self.assertRaisesRegex(ValueError, 'already issued|not observed'):
            self.start(self.observed() if False else action.argument, uuid='b' * 32)

    def test_active_profile_root_change_is_refused_without_touching_either_path(self):
        action = self.start(self.observed())
        self.fixture.backend._data_directory = lambda: self.root.name + '-different-profile'
        result = self.finish(action)
        self.assertFalse(result['ok'])
        self.assertEqual(self.fixture.native_writes, [])
        self.assertFalse(Path(self.root.name + '-different-profile').exists())

    def test_replaced_stored_wrapper_is_not_rebound_or_reconstructed(self):
        action = self.start(self.observed())
        self.fixture.forms[2] = copy.deepcopy(self.fixture.forms[2])
        result = self.finish(action)
        self.assertFalse(result['ok'])
        self.assertEqual(self.fixture.native_writes, [])

    def test_missing_previously_captured_appearance_field_refuses_the_complete_before_image(self):
        action = self.start(self.observed())
        del self.fixture.forms[2].facial_attributes
        result = self.finish(action)
        self.assertFalse(result['ok'])
        self.assertEqual(self.fixture.native_writes, [])

    def test_wrong_owner_thread_cannot_resume_even_the_native_poll(self):
        action = self.start(self.observed())
        results = []
        def wrong_owner():
            try:
                action.resume()
            except ValueError as error:
                results.append(str(error))
        thread = threading.Thread(target=wrong_owner)
        thread.start()
        thread.join()
        self.assertEqual(len(results), 1)
        self.assertIn('game thread', results[0])
        self.assertTrue(self.finish(action)['ok'])

    def test_pending_native_work_never_holds_receiver_lock_or_private_selected_view(self):
        action = self.start(self.observed())
        self.assertIsNone(bank._BANK_ASYNC_VIEW)
        acquired = []
        def probe_lock():
            held = bank._LOCK.acquire(False)
            acquired.append(held)
            if held:
                bank._LOCK.release()
        thread = threading.Thread(target=probe_lock)
        thread.start()
        thread.join()
        self.assertEqual(acquired, [True])
        self.assertTrue(self.finish(action)['ok'])

    def test_zone_same_owner_rebind_preserves_uuid_then_stale_manager_fails_fences(self):
        argument = self.observed()
        queue = CommandQueue()
        rid = uuid_module.uuid4().hex
        queue.submit({'action': 'cas_bank_prepare'}, request_id=rid)
        queue.drain(lambda payload: self.start(argument, uuid=rid), max_commands=1)
        continuation = queue.records[rid]['_continuation']
        queue.bind_owner()  # actual zone-ready same-thread behavior
        self.assertIs(queue.records[rid]['_continuation'], continuation)
        self.assertEqual(queue.status(rid)['state'], 'running')
        self.assertFalse(queue.records[rid]['event'].is_set())
        self.fixture.backend._get_sim_info_by_id = lambda sid: None
        deadline = time.perf_counter() + 5
        while queue.status(rid)['state'] == 'running' and time.perf_counter() < deadline:
            queue.drain(lambda payload: self.fail('Initial CAS action was replayed'), max_commands=1)
            time.sleep(.001)
        self.assertEqual(queue.status(rid)['state'], 'failed')
        self.assertFalse(queue.status(rid)['result']['automatic_replay_allowed'])
        self.assertTrue(self.fixture.path.is_file())
        self.assertEqual(self.fixture.native_writes, [])

    def test_external_bank_revision_change_is_not_replaced(self):
        argument = self.observed()
        original_submit, changed = self.binding.submit_call, []
        def external_write(header, payload):
            if json.loads(header)['operation'] == 'plan-base':
                value = self.fixture.path.read_bytes() + b' '
                self.fixture.path.write_bytes(value)
                changed.append(value)
            return original_submit(header, payload)
        self.binding.submit_call = external_write
        action = self.start(argument)
        result = self.finish(action)
        self.assertFalse(result['ok'])
        self.assertIn('revision', result['message'])
        self.assertEqual(self.fixture.path.read_bytes(), changed[0])


class ContinuationQueueTests(unittest.TestCase):
    def test_waiting_stays_running_event_unset_and_unrelated_action_executes(self):
        class Waiting(OwnerContinuation):
            def __init__(self): self.ready = False; self.calls = 0
            def resume(self):
                self.calls += 1
                return {'ok': True, 'verified': True} if self.ready else self
        queue = CommandQueue()
        wait = Waiting()
        first = queue.submit({'action': 'prepare'}, request_id='first')['request_id']
        calls = []
        def execute(value):
            calls.append(value['action'])
            return wait if value['action'] == 'prepare' else {'ok': True}
        queue.drain(execute, max_commands=1)
        self.assertEqual(queue.status(first)['state'], 'running')
        self.assertIsNone(queue.status(first)['result'])
        self.assertFalse(queue.records[first]['event'].is_set())
        self.assertFalse(queue.cancel(first))
        self.assertEqual(queue.wait(first, 0)['state'], 'running')
        second = queue.submit({'action': 'interaction'})['request_id']
        queue.drain(execute, max_commands=2)
        self.assertEqual(queue.status(second)['state'], 'completed')
        self.assertEqual(calls, ['prepare', 'interaction'])
        wait.ready = True
        queue.drain(execute)
        self.assertEqual(queue.status(first)['state'], 'completed')
        self.assertTrue(queue.records[first]['event'].is_set())
        self.assertEqual(calls.count('prepare'), 1)

    def test_original_uuid_pending_capacity_and_pruning_do_not_drop_waiting_action(self):
        class Waiting(OwnerContinuation):
            def resume(self): return self
        queue = CommandQueue(capacity=1, completed_limit=0)
        first = queue.submit({'action': 'prepare'}, request_id='same')
        queue.drain(lambda _: Waiting())
        self.assertEqual(queue.submit({'action': 'prepare'}, request_id='same')['state'], 'running')
        self.assertEqual(queue.submit({'action': 'other'})['state'], 'rejected')
        queue.shutdown()
        self.assertEqual(queue.status(first['request_id'])['state'], 'running')
        queue.bind_owner()
        self.assertEqual(queue.status(first['request_id'])['state'], 'running')
        self.assertFalse(queue.records[first['request_id']]['event'].is_set())
        errors = []
        def transfer():
            try:
                queue.bind_owner()
            except RuntimeError as error:
                errors.append(str(error))
        thread = threading.Thread(target=transfer)
        thread.start()
        thread.join()
        self.assertEqual(len(errors), 1)


if __name__ == '__main__':
    unittest.main()
