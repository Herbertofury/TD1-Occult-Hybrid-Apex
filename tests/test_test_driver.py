from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
import td1_occult_hybrid_apex as backend
from apex_core import test_driver, form_bank, cas_bank_transaction
from apex_core.command_queue import CommandQueue


class TestDriverTests(unittest.TestCase):
    @staticmethod
    def timeline_fixture(timeline, game_ticks):
        class NativeTime:
            def __init__(self, ticks, label):
                self.ticks, self.label = ticks, label
            def absolute_ticks(self):
                return self.ticks
            def __str__(self):
                return self.label
        game = Obj(clock_speed=1, now=lambda: NativeTime(game_ticks[0], 'game ' + str(game_ticks[0])))
        persistence = Obj(get_save_slot_proto_buff=lambda: Obj(slot_id=2),
                          get_save_slot_proto_guid=lambda: 333)
        service = Obj(sim_now=NativeTime(timeline, 'simulation ' + str(timeline)))
        services = Obj(get_persistence_service=lambda: persistence, game_clock_service=lambda: game,
            active_household=lambda: Obj(id=222), current_zone=lambda: Obj(id=444, is_in_build_buy=False, is_zone_running=True),
            client_manager=lambda: Obj(get_first_client=lambda: Obj(id=555)), time_service=lambda: service)
        return Obj(services=services), service

    def test_frozen_simulation_does_not_inherit_advancing_game_clock(self):
        game_ticks = [100]
        fake, _timeline = self.timeline_fixture((1 << 63) + 7, game_ticks)
        before = test_driver.snapshot(fake, None)
        game_ticks[0] += 1000
        after = test_driver.snapshot(fake, None)
        self.assertEqual(before['sim_now_ticks'], str((1 << 63) + 7))
        self.assertEqual(after['sim_now_ticks'], before['sim_now_ticks'])
        self.assertEqual(after['sim_now'], before['sim_now'])
        self.assertEqual(before['game_now_ticks'], '100')
        self.assertEqual(after['game_now_ticks'], '1100')
        self.assertNotEqual(after['game_now'], before['game_now'])
        self.assertEqual(after['sim_time_source'], 'services.time_service().sim_now')
        self.assertEqual(after['runtime_queries']['sim_now_ticks'], 'returned-value')

    def test_simulation_timeline_advances_independently_from_game_clock(self):
        fake, timeline = self.timeline_fixture(20, [100])
        before = test_driver.snapshot(fake, None)
        timeline.sim_now.ticks = 35
        after = test_driver.snapshot(fake, None)
        self.assertEqual((before['sim_now_ticks'], after['sim_now_ticks']), ('20', '35'))
        self.assertEqual(before['game_now_ticks'], after['game_now_ticks'])

    def test_missing_failed_or_null_timeline_never_falls_back_to_game_clock(self):
        for unavailable in ('missing-service', 'null-service', 'failed-service', 'missing-timeline', 'null-timeline'):
            with self.subTest(unavailable=unavailable):
                fake, timeline = self.timeline_fixture(20, [100])
                if unavailable == 'missing-service':
                    del fake.services.time_service
                elif unavailable == 'null-service':
                    fake.services.time_service = lambda: None
                elif unavailable == 'failed-service':
                    fake.services.time_service = Mock(side_effect=RuntimeError('timeline unavailable'))
                elif unavailable == 'missing-timeline':
                    del timeline.sim_now
                else:
                    timeline.sim_now = None
                result = test_driver.snapshot(fake, None)
                self.assertIsNone(result['sim_now'])
                self.assertIsNone(result['sim_now_ticks'])
                state = 'returned-null' if unavailable.startswith('null-') else 'failed'
                self.assertEqual(result['runtime_queries']['sim_now'], state)
                self.assertEqual(result['runtime_queries']['sim_now_ticks'], state)
                self.assertEqual(result['game_now_ticks'], '100')
                if state == 'failed':
                    self.assertIn('sim_now_ticks', result['runtime_errors'])

    def test_malformed_native_timeline_ticks_are_explicit_without_clock_fallback(self):
        for malformed in (True, -1, 1 << 64, 1.25, '123'):
            with self.subTest(malformed=malformed):
                fake, timeline = self.timeline_fixture(malformed, [100])
                result = test_driver.snapshot(fake, None)
                self.assertIsNone(result['sim_now_ticks'])
                self.assertIsNone(result['sim_now'])
                self.assertEqual(result['runtime_queries']['sim_now_ticks'], 'failed')
                self.assertEqual(result['game_now_ticks'], '100')
        fake, timeline = self.timeline_fixture(20, [100])
        timeline.sim_now = Obj()
        result = test_driver.snapshot(fake, None)
        self.assertIsNone(result['sim_now_ticks'])
        self.assertEqual(result['runtime_queries']['sim_now_ticks'], 'failed')

    def test_unavailable_game_clock_time_does_not_erase_valid_simulation_timeline(self):
        fake, _timeline = self.timeline_fixture(20, [100])
        fake.services.game_clock_service().now = Mock(side_effect=RuntimeError('game now unavailable'))
        result = test_driver.snapshot(fake, None)
        self.assertEqual(result['sim_now_ticks'], '20')
        self.assertIsNone(result['game_now_ticks'])
        self.assertEqual(result['runtime_queries']['game_now_ticks'], 'failed')

    def test_outfit_switch_uses_existing_number_and_requires_unpaused_visual_proof(self):
        current=[(0,0)]
        def switch(value):current[0]=value;return True
        sim=Obj(has_outfit=lambda value:value==(0,1),set_current_outfit=Mock(side_effect=switch),get_current_outfit=lambda:current[0])
        fake=Obj(_get_sim_info_by_id=lambda _:sim,_resend_all_visuals=Mock())
        modules={'sims':Obj(),'sims.outfits':Obj(),'sims.outfits.outfit_enums':Obj(OutfitCategory=lambda value:value)}
        with patch.object(test_driver,'guard',return_value={'category':0,'index':1}),patch.object(test_driver,'snapshot',return_value={}),patch.object(form_bank, 'assert_idle'),patch.dict(sys.modules,modules):
            result=test_driver.dispatch(fake,'test_outfit','123','{}')
        self.assertTrue(result['ok']);self.assertTrue(result['unpaused_visual_verification_required']);self.assertEqual(current[0],(0,1))
        sim.set_current_outfit.reset_mock()
        with patch.object(test_driver,'guard',return_value={'category':0,'index':2}),patch.object(form_bank, 'assert_idle'),patch.dict(sys.modules,modules):
            with self.assertRaisesRegex(ValueError,'does not exist'):test_driver.dispatch(fake,'test_outfit','123','{}')
        sim.set_current_outfit.assert_not_called()
    def test_new_occult_initializes_new_form_without_overwriting_existing_human(self):
        human, new_form = Obj(id=1), Obj(id=2)
        tracker = Obj(get_occult_sim_info=lambda kind: human if kind == 1 else None)
        sim = Obj(id=3, occult_tracker=tracker, occult_types=1, current_occult_types=1)
        with patch.object(backend, 'OccultType', Obj(HUMAN=1)), patch.object(backend, '_snapshot_siminfo_payload', return_value={'look': 'current'}), \
             patch.object(backend, '_has_occult', side_effect=[False, True]), patch.object(backend, '_apply_gameplay_loots', return_value=(False, [])), \
             patch.object(backend, '_restore_siminfo_payload') as restore, patch.object(backend, '_ensure_human_form', return_value=human), \
             patch.object(backend, '_ensure_form', return_value=new_form), patch.object(backend, '_recalc'), \
             patch.object(backend, '_set_tracker_form_available'):
            backend._add_occult(sim, 4, add_traits=False, add_memory=False)
        restore.assert_called_once_with(new_form, {'look': 'current'})
    def test_readding_existing_occult_preserves_independent_human_and_occult_edits(self):
        human, vampire = Obj(id=1), Obj(id=2)
        tracker = Obj(get_occult_sim_info=lambda kind: {1: human, 4: vampire}.get(kind))
        sim = Obj(id=3, occult_tracker=tracker, occult_types=4, current_occult_types=1)
        with patch.object(backend, 'OccultType', Obj(HUMAN=1)), patch.object(backend, '_snapshot_siminfo_payload', return_value={'look': 'current'}), \
             patch.object(backend, '_has_occult', return_value=True), patch.object(backend, '_apply_gameplay_loots') as loot, \
             patch.object(backend, '_restore_siminfo_payload') as restore, patch.object(backend, '_ensure_human_form', return_value=human), \
             patch.object(backend, '_ensure_form', return_value=vampire), patch.object(backend, '_recalc'), \
             patch.object(backend, '_set_tracker_form_available'):
            backend._add_occult(sim, 4, add_traits=False, add_memory=False)
        loot.assert_not_called()
        restore.assert_not_called()

    def test_guard_rejects_before_any_sim_inspection(self):
        fake = Obj(_get_sim_info_by_id=Mock(side_effect=AssertionError('Sim read')))
        with patch.object(test_driver, 'guard', side_effect=ValueError('wrong token')):
            with self.assertRaisesRegex(ValueError, 'wrong token'):
                test_driver.dispatch(fake, 'test_create_sim', '1', '{}')
        fake._get_sim_info_by_id.assert_not_called()

    def creation_fixture(self, *, missing_proto=False, missing_membership=False,
                         wrong_manager=False, wrong_household=False, no_account=False,
                         created_count=1):
        # Use IDs above IEEE-754's exact range to catch accidental numeric coercion.
        household_id = (1 << 63) + 9
        sim_id = (1 << 63) + 7
        existing = Obj(id=20)
        created = [Obj(id=sim_id + number, household_id=household_id,
                       account_id=None if no_account else 5) for number in range(created_count)]
        members = [existing]
        household = Obj(id=household_id, sim_info_gen=lambda: iter(members))
        sim_proto = Obj(sim_id=sim_id, household_id=household_id + int(wrong_household))
        native_household = Obj(household_id=household_id,
                               sims=Obj(ids=[existing.id] if missing_membership else [existing.id, sim_id]))
        persistence = Obj(get_sim_proto_buff=Mock(return_value=None if missing_proto else sim_proto),
                          get_household_proto_buff=Mock(return_value=native_household))
        manager = Obj(get=lambda identity: object() if wrong_manager else
                      next((item for item in members if item.id == identity), None))
        spawn = Mock(side_effect=lambda **_kwargs: members.extend(created))
        fake = Obj(_get_sim_info_by_id=lambda _: None, services=Obj(
            active_household=lambda: household,
            client_manager=lambda: Obj(get_first_client=lambda: Obj(id=987)),
            sim_info_manager=lambda: manager, get_persistence_service=lambda: persistence))
        modules = {'server_commands': Obj(),
                   'server_commands.sim_commands': Obj(spawn_client_sims_simple=spawn),
                   'sims': Obj(), 'sims.sim_info_types': Obj(
                       Age=Obj(YOUNGADULT=2), Gender=Obj(FEMALE=1), Species=Obj(HUMAN=1))}
        return fake, modules, spawn, sim_id, persistence

    def create_with_fixture(self, **failures):
        fake, modules, spawn, sim_id, persistence = self.creation_fixture(**failures)
        with patch.object(test_driver, 'guard', return_value=None), \
             patch.object(test_driver, 'snapshot', return_value={}), patch.dict(sys.modules, modules):
            result = test_driver.dispatch(fake, 'test_create_sim', '0', '{}')
        spawn.assert_called_once()
        return result, sim_id, persistence

    def test_creation_native_buffers_are_distinct_from_disk_save_reload_proof(self):
        result, sim_id, persistence = self.create_with_fixture()
        self.assertTrue(result['ok'])
        self.assertTrue(result['persistence_verified_before_save'])
        self.assertFalse(result['save_reload_verified'])
        self.assertFalse(result['retry_safe'])
        self.assertEqual(result['created_sim_id'], str(sim_id))
        self.assertIn(str(sim_id), result['persistence']['persisted_household_sim_ids'])
        persistence.get_sim_proto_buff.assert_called_once_with(sim_id)

    def test_creation_retains_identity_if_native_sim_or_household_would_not_save(self):
        for failure in ('missing_proto', 'missing_membership', 'wrong_manager',
                        'wrong_household', 'no_account'):
            with self.subTest(failure=failure):
                result, sim_id, _ = self.create_with_fixture(**{failure: True})
                self.assertFalse(result['ok'])
                self.assertFalse(result['persistence_verified_before_save'])
                self.assertFalse(result['save_reload_verified'])
                self.assertFalse(result['retry_safe'])
                self.assertEqual(result['outcome'], 'persistence-unresolved')
                self.assertEqual(result['created_sim_id'], str(sim_id))

    def test_ambiguous_creation_reports_every_observed_identity_without_retry(self):
        for count in (0, 2):
            with self.subTest(count=count):
                result, sim_id, persistence = self.create_with_fixture(created_count=count)
                self.assertFalse(result['ok'])
                self.assertFalse(result['retry_safe'])
                self.assertFalse(result['save_reload_verified'])
                self.assertEqual(result['created_sim_ids'], [str(sim_id + n) for n in range(count)])
                persistence.get_sim_proto_buff.assert_not_called()

    def test_unavailable_native_persistence_is_explicit_and_does_not_write(self):
        fake, _modules, _spawn, sim_id, persistence = self.creation_fixture()
        household = fake.services.active_household()
        sim = Obj(id=sim_id, household_id=household.id, account_id=5)
        persistence.get_sim_proto_buff.side_effect = RuntimeError('native buffer unavailable')
        result = test_driver.persistence_evidence(fake, sim, household)
        self.assertFalse(result['persistence_verified_before_save'])
        self.assertFalse(result['save_reload_verified'])
        self.assertEqual(result['errors'], ['native buffer unavailable'])
        persistence.get_household_proto_buff.assert_not_called()

    def test_cas_uses_actual_string_target_contract_not_integer(self):
        sim = Obj(id=(1 << 63) + 7, get_sim_instance=lambda: object())
        fake = Obj(_get_sim_info_by_id=lambda _: sim,
            services=Obj(client_manager=lambda: Obj(get_first_client=lambda: Obj(id=5))))
        calls = []
        def target(value):
            calls.append(value)
            return int(value, 0)  # Actual game helper contract which failed live.
        modules = {'server_commands': Obj(),
            'server_commands.cas_commands': Obj(modify_in_cas=lambda *_a, **_k: True),
            'server_commands.argument_helpers': Obj(OptionalTargetParam=target)}
        with patch.object(test_driver, 'guard', return_value=None), patch.object(test_driver, 'snapshot', return_value={}), \
                patch.object(cas_bank_transaction, 'begin', return_value={'ok': True, 'lane': '1'}), patch.dict(sys.modules, modules):
            result = test_driver.dispatch(fake, 'test_cas', str(sim.id), '{}')
        self.assertTrue(result['ok'])
        self.assertEqual(calls, [str(sim.id)])
        self.assertFalse(result['cas_visible_verified'])

    def test_native_protobuf_outfits_are_saved_as_bytes_and_restored_as_message(self):
        class Message:
            def SerializeToString(self):
                return b'full native bytes\x00\xff'
            def ParseFromString(self, raw):
                self.raw = raw
        sim = Obj(save_outfits=lambda: Message(), load_outfits=Mock())
        snapshot = backend._snapshot_siminfo_payload(sim)
        self.assertEqual(snapshot['__outfits__'], ('protobuf', b'full native bytes\x00\xff'))
        packed = backend._pack_value(Message())
        self.assertEqual(packed['kind'], 'protobuf')
        data = {'__outfits__': backend._unpack_value(packed)}
        with patch.dict(sys.modules, {'protocolbuffers': Obj(Outfits_pb2=Obj(OutfitList=Message))}):
            self.assertTrue(backend._restore_siminfo_payload(sim, data))
        self.assertEqual(sim.load_outfits.call_args[0][0].raw, b'full native bytes\x00\xff')

    def test_full_cas_enables_native_full_edit_on_observed_client_before_entry(self):
        sim = Obj(id=123, get_sim_instance=lambda: object())
        fake = Obj(_get_sim_info_by_id=lambda _: sim,
            services=Obj(client_manager=lambda: Obj(get_first_client=lambda: Obj(id=987))))
        calls = []
        modules = {'server_commands': Obj(),
            'server_commands.cas_commands': Obj(modify_in_cas=lambda target, **kwargs: calls.append(('cas', target, kwargs)) or True),
            'server_commands.argument_helpers': Obj(OptionalTargetParam=lambda text: text),
            'sims4.commands': Obj(client_cheat=lambda *args: calls.append(('cheat',) + args))}
        with patch.object(test_driver, 'guard', return_value='full'), patch.object(test_driver, 'snapshot', side_effect=lambda *_a: calls.append(('snapshot-after-checkpoint',)) or {}), \
                patch.object(cas_bank_transaction, 'begin', side_effect=lambda *_a: calls.append(('checkpoint',)) or {'ok': True, 'lane': '1'}), patch.dict(sys.modules, modules):
            self.assertTrue(test_driver.dispatch(fake, 'test_cas', '123', '{}')['ok'])
        self.assertEqual(calls, [('checkpoint',), ('snapshot-after-checkpoint',), ('cheat', 'cas.fulleditmode', 987), ('cas', '123', {'_connection': 987})])
        calls.clear()
        with patch.object(test_driver, 'guard', return_value='unsupported'), patch.dict(sys.modules, modules):
            with self.assertRaisesRegex(ValueError, 'CAS mode'):
                test_driver.dispatch(fake, 'test_cas', '123', '{}')
        self.assertEqual(calls, [])

    def test_cas_checkpoint_failure_or_pending_transaction_prevents_native_entry(self):
        sim = Obj(id=123, get_sim_instance=lambda: object())
        fake = Obj(_get_sim_info_by_id=lambda _: sim,
            services=Obj(client_manager=lambda: Obj(get_first_client=lambda: Obj(id=987))))
        entry, cheat = Mock(return_value=True), Mock()
        modules = {'server_commands': Obj(),
            'server_commands.cas_commands': Obj(modify_in_cas=entry),
            'server_commands.argument_helpers': Obj(OptionalTargetParam=lambda text: text),
            'sims4.commands': Obj(client_cheat=cheat)}
        for options in ({'side_effect': ValueError('CAS transaction retained')},
                        {'return_value': {'ok': False}}, {'return_value': None}):
            with self.subTest(options=options), patch.object(test_driver, 'guard', return_value='full'), \
                    patch.object(test_driver, 'snapshot', return_value={}), \
                    patch.object(cas_bank_transaction, 'begin', **options), patch.dict(sys.modules, modules):
                with self.assertRaises(ValueError):
                    test_driver.dispatch(fake, 'test_cas', '123', '{}')
        entry.assert_not_called()
        cheat.assert_not_called()

    def test_rejected_native_cas_entry_keeps_form_checkpoint_for_recovery(self):
        sim = Obj(id=123, get_sim_instance=lambda: object())
        fake = Obj(_get_sim_info_by_id=lambda _: sim,
            services=Obj(client_manager=lambda: Obj(get_first_client=lambda: Obj(id=987))))
        saved = []
        modules = {'server_commands': Obj(),
            'server_commands.cas_commands': Obj(modify_in_cas=lambda *_a, **_k: False),
            'server_commands.argument_helpers': Obj(OptionalTargetParam=lambda text: text)}
        with patch.object(test_driver, 'guard', return_value=None), patch.object(test_driver, 'snapshot', return_value={}), \
                patch.object(cas_bank_transaction, 'begin', side_effect=lambda *_a: saved.append('originals') or {'ok': True, 'lane': '32'}), \
                patch.dict(sys.modules, modules):
            result = test_driver.dispatch(fake, 'test_cas', '123', '{}')
        self.assertFalse(result['ok'])
        self.assertEqual(saved, ['originals'])
        self.assertEqual(result['form_checkpoint'], {'ok': True, 'lane': '32'})

    def test_mccc_uses_observed_client_and_cannot_fall_back_to_anonymous_execution(self):
        execute = Mock(return_value=None)
        command_module = Obj(execute=execute)
        modules = {'sims4': Obj(commands=command_module), 'sims4.commands': command_module}
        with patch.dict(sys.modules, modules), patch.object(backend, 'services',
                Obj(client_manager=lambda: Obj(get_first_client=lambda: Obj(id=987)))):
            self.assertTrue(backend._run_console_command('mccc Apex Test')[0])
        execute.assert_called_once_with('mccc Apex Test', 987)
        execute.reset_mock()
        with patch.dict(sys.modules, modules), patch.object(backend, 'services',
                Obj(client_manager=lambda: Obj(get_first_client=lambda: None))):
            self.assertFalse(backend._run_console_command('mccc Apex Test')[0])
        execute.assert_not_called()

    def test_core_tick_preserves_original_and_only_owner_drains_accepted_work(self):
        import threading
        queue = CommandQueue()
        core = Obj(on_tick=Mock(return_value='original return'))
        core.on_tick._apex_core_tick = False
        executed = []
        with patch.dict(sys.modules, {'sims4': Obj(core_services=core), 'sims4.core_services': core}), \
             patch.object(backend, '_APEX_COMMANDS', queue), patch.object(backend, '_APEX_GAME_THREAD_IDENT', threading.get_ident()), \
             patch.object(backend, '_APEX_CORE_TICK_READY', False), patch.object(backend, '_APEX_CORE_TICKS', 0), \
             patch.object(backend, '_execute_owned_command', side_effect=lambda row: executed.append(row) or {'ok': True}):
            self.assertTrue(backend._apex_install_core_tick())
            self.assertEqual(core.on_tick(), 'original return')
            self.assertEqual(executed, [])
            queue.submit({'action': 'test_quit'})
            worker = threading.Thread(target=core.on_tick)
            worker.start(); worker.join()
            self.assertEqual(executed, [])
            core.on_tick()
            self.assertEqual(executed, [{'action': 'test_quit'}])
