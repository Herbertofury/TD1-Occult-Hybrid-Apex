"""Actual production queue and unmodified final dispatcher direct-entry isolation."""
import ast
import json
from pathlib import Path
import sys
import threading
from types import ModuleType, SimpleNamespace as Obj
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Source'))
from apex_core import bank_worker, cas_bank_transaction as bank, overlay_loader, phone_cas
from apex_core.command_queue import CommandQueue as Queue, OwnerContinuation as Continuation


class QueueActionTests(unittest.TestCase):
    def test_initial_resume_and_exception_preserve_exact_action_context(self):
        queue, seen = Queue(), []
        class Work(Continuation):
            def resume(self):
                seen.append((queue.current_action(), queue.current_request_id()))
                raise ValueError('terminal fixture')
        rid = queue.submit({'action': 'cas_bank_prepare'}, request_id='same')['request_id']
        def execute(payload):
            seen.append((queue.current_action(), queue.current_request_id()))
            return Work()
        queue.drain(execute)
        self.assertIsNone(queue.current_action())
        self.assertIsNone(queue.current_request_id())
        queue.drain(execute)
        self.assertEqual(seen, [('cas_bank_prepare', rid), ('cas_bank_prepare', rid)])
        self.assertEqual(queue.status(rid)['state'], 'failed')
        self.assertIsNone(queue.current_action())
        self.assertIsNone(queue.current_request_id())

    def test_nested_owner_execution_restores_outer_context_and_wrong_thread_refuses(self):
        queue, seen = Queue(), []
        queue.submit({'action': 'cas_bank_ui_prepare'}, request_id='outer')
        def inner(payload):
            seen.append((queue.current_action(), queue.current_request_id()))
            return {'ok': True}
        def outer(payload):
            queue.submit({'action': 'unrelated'}, request_id='inner')
            queue.drain(inner)
            seen.append((queue.current_action(), queue.current_request_id()))
            return {'ok': True}
        queue.drain(outer, budget_seconds=1)
        self.assertEqual(seen, [('unrelated', 'inner'), ('cas_bank_ui_prepare', 'outer')])
        errors = []
        def wrong():
            try: queue.current_action()
            except RuntimeError as error: errors.append(str(error))
        thread = threading.Thread(target=wrong)
        thread.start(); thread.join()
        self.assertEqual(len(errors), 1)


class DirectDispatcherTests(unittest.TestCase):
    def setUp(self):
        self.module = module = ModuleType('private_direct_dispatch_fixture')
        module.__file__ = 'authenticated.ts4script/td1_occult_hybrid_apex.pyc'
        self.addCleanup(sys.modules.pop, module.__name__, None)
        sys.modules[module.__name__] = module
        module.__dict__.update(services=Obj(), threading=threading, json=json,
            _APEX_GAME_THREAD_IDENT=threading.current_thread().ident,
            _APEX_ASYNC_BANK_PREPARE_ENABLED=True, _APEX_COMMANDS=Queue(),
            _get_sim_info_by_id=lambda sid: Obj(id=int(sid)),
            _apex_cas_transaction_argument=json.loads)
        tree = ast.parse((ROOT / 'Source/td1_occult_hybrid_apex.py').read_text(encoding='utf-8'))
        node = next(n for n in reversed(tree.body) if isinstance(n, ast.FunctionDef) and n.name == 'run_action')
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(ROOT / 'Source/td1_occult_hybrid_apex.py'), 'exec'), module.__dict__)

    def test_direct_phone_call_stays_dictionary_and_sync_once_with_flag_enabled(self):
        with patch.object(bank, 'prepare', return_value={'ok': True, 'plan_sha256': 'a'*64}) as sync, \
                patch.object(bank_worker, 'PrepareAction', side_effect=AssertionError('Phone must not admit orphan continuation')) as start:
            result = phone_cas._call(self.module, '42', 'cas_bank_prepare', {})
        self.assertIsInstance(result, dict)
        sync.assert_called_once()
        start.assert_not_called()
        self.assertEqual(self.module._APEX_COMMANDS.metrics()['retained'], 0)

    def test_nested_queued_ui_prepare_stays_dictionary_and_never_admits_worker(self):
        module = self.module
        def ui(backend, sid, action, argument):
            return phone_cas._call(backend, sid, 'cas_bank_prepare', argument)
        rid = module._APEX_COMMANDS.submit({'action': 'cas_bank_ui_prepare'})['request_id']
        with patch.object(phone_cas, 'ui_dispatch', side_effect=ui), \
                patch.object(bank, 'prepare', return_value={'ok': True, 'plan_sha256': 'b'*64}) as sync, \
                patch.object(bank_worker, 'PrepareAction', side_effect=AssertionError('Nested UI orphan')) as start:
            module._APEX_COMMANDS.drain(lambda payload: module.run_action(payload['action'], '42', value='{}'))
        sync.assert_called_once(); start.assert_not_called()
        row = module._APEX_COMMANDS.records[rid]
        self.assertEqual(row['state'], 'completed')
        self.assertIsInstance(row['result'], dict)
        self.assertNotIn('_continuation', row)
        self.assertTrue(row['event'].is_set())

    def test_exact_queued_prepare_retains_original_uuid_and_resumes_once(self):
        module = self.module
        seen = []
        class Work(Continuation):
            def __init__(self, backend, sim, argument, binding, rid): seen.append(('admit', rid))
            def resume(self):
                seen.append(('resume', module._APEX_COMMANDS.current_request_id()))
                return {'ok': True, 'plan_sha256': 'c'*64}
        rid = module._APEX_COMMANDS.submit({'action': 'cas_bank_prepare'}, request_id='original')['request_id']
        with patch.object(bank_worker, 'PrepareAction', Work), patch.object(overlay_loader, 'bank_worker_binding', return_value='frozen'), \
                patch.object(bank, 'prepare', side_effect=AssertionError('Accepted direct route fell back')):
            module._APEX_COMMANDS.drain(lambda payload: module.run_action(payload['action'], '42', value='{}'))
            self.assertEqual(module._APEX_COMMANDS.status(rid)['state'], 'running')
            module._APEX_COMMANDS.drain(lambda payload: self.fail('Direct action replayed'))
        self.assertEqual(seen, [('admit', rid), ('resume', rid)])
        self.assertEqual(module._APEX_COMMANDS.status(rid)['state'], 'completed')


if __name__ == '__main__': unittest.main()
