from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
import td1_occult_hybrid_apex as backend
from apex_core import test_driver
from apex_core.command_queue import CommandQueue


class TestDriverTests(unittest.TestCase):
    def test_outfit_switch_uses_existing_number_and_requires_unpaused_visual_proof(self):
        current=[(0,0)]
        def switch(value):current[0]=value;return True
        sim=Obj(has_outfit=lambda value:value==(0,1),set_current_outfit=Mock(side_effect=switch),get_current_outfit=lambda:current[0])
        fake=Obj(_get_sim_info_by_id=lambda _:sim,_resend_all_visuals=Mock())
        modules={'sims':Obj(),'sims.outfits':Obj(),'sims.outfits.outfit_enums':Obj(OutfitCategory=lambda value:value)}
        with patch.object(test_driver,'guard',return_value={'category':0,'index':1}),patch.object(test_driver,'snapshot',return_value={}),patch.dict(sys.modules,modules):
            result=test_driver.dispatch(fake,'test_outfit','123','{}')
        self.assertTrue(result['ok']);self.assertTrue(result['unpaused_visual_verification_required']);self.assertEqual(current[0],(0,1))
        sim.set_current_outfit.reset_mock()
        with patch.object(test_driver,'guard',return_value={'category':0,'index':2}),patch.dict(sys.modules,modules):
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
        with patch.object(test_driver, 'guard', return_value=None), patch.object(test_driver, 'snapshot', return_value={}), patch.dict(sys.modules, modules):
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
        with patch.object(test_driver, 'guard', return_value='full'), patch.object(test_driver, 'snapshot', return_value={}), patch.dict(sys.modules, modules):
            self.assertTrue(test_driver.dispatch(fake, 'test_cas', '123', '{}')['ok'])
        self.assertEqual(calls, [('cheat', 'cas.fulleditmode', 987), ('cas', '123', {'_connection': 987})])
        calls.clear()
        with patch.object(test_driver, 'guard', return_value='unsupported'), patch.dict(sys.modules, modules):
            with self.assertRaisesRegex(ValueError, 'CAS mode'):
                test_driver.dispatch(fake, 'test_cas', '123', '{}')
        self.assertEqual(calls, [])

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
