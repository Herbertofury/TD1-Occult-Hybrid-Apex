from pathlib import Path
import ast
import importlib.util
import json
import sys
import threading
import time
from types import ModuleType,SimpleNamespace as Object
import unittest
from unittest.mock import patch
from apex_core import owner_mailbox as adapter_module
from tests.test_owner_mailbox import Native, ID
from apex_core.command_queue import CommandQueue,OwnerContinuation
from apex_core.overlay_display_status import dispatch as display

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'Source'


def functions(path,names,namespace):
    tree=ast.parse(path.read_text(encoding='utf-8'))
    chosen={node.name:node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names}
    assert len(chosen)==len(names)
    exec(compile(ast.Module(body=list(chosen.values()),type_ignores=[]),str(path),'exec'),namespace)


class Integration(unittest.TestCase):
    def fixture(self):
        native=Native();queue=CommandQueue();module=ModuleType('apex_mailbox_source_fixture')
        ns=module.__dict__;ns.update(threading=threading,time=time,OwnerContinuation=OwnerContinuation,_APEX_GAME_THREAD_IDENT=threading.current_thread().ident,
            _APEX_COMMANDS=queue,_APEX_CORE_TICK_READY=True,_APEX_CORE_TICKS=0,_APEX_PROFILE_PULSE=None,
            _SERVER_START_RETRY=Object(take_due=lambda _:False),_AUTO_REPAIR=False,_MCCC_CAS_SHIELD_ENABLED=False,
            _ALARM_READY=True,_log=lambda _:None,_record_perf=lambda *a,**k:None)
        functions(WORK/'td1_occult_hybrid_apex.py',('_apex_owner_action_ready','_execute_owned_command','_process_pending','_apex_install_core_tick'),ns)
        adapter=adapter_module.OwnerIngress(queue,native,native.pending,ns['_APEX_GAME_THREAD_IDENT'],'a'*32,100,ns['_apex_owner_action_ready'])
        ns['_APEX_OWNER_MAILBOX']=Object(ingress=lambda _:adapter.ingress(),completions=lambda _:adapter.completions(),
            before_execute=lambda _,payload:adapter.before_execute(payload))
        sys.modules[module.__name__]=module;self.addCleanup(sys.modules.pop,module.__name__,None)
        return module,native,adapter

    def test_actual_core_tick_drains_once_and_preserves_previous_return(self):
        module,native,adapter=self.fixture();calls=[]
        module.run_action=lambda *args: (calls.append(args) or dict(ok=True,exact='actual result'))
        package=ModuleType('sims4');package.__path__=[];core=ModuleType('sims4.core_services');previous=[]
        core.on_tick=lambda *a,**k:(previous.append((a,k)) or 'EA return')
        package.core_services=core
        with patch.dict(sys.modules,{'sims4':package,'sims4.core_services':core}):
            self.assertTrue(module._apex_install_core_tick())
            native.add('/api/command?action=switch&sim_id=42&occult=ALIEN')
            with patch.object(module._APEX_COMMANDS,'wait',side_effect=AssertionError('Owner must not wait')):
                self.assertEqual(core.on_tick(1,test=2),'EA return')
            self.assertEqual(len(calls),1);self.assertEqual(calls[0],('switch','42','ALIEN',None))
            self.assertEqual(native.receipts[ID],module._APEX_COMMANDS.status(ID))
            self.assertEqual(previous,[((1,),{'test':2})]);self.assertEqual(module._APEX_CORE_TICKS,1)

    def test_actual_alarm_handler_checks_selection_at_execution(self):
        module,native,adapter=self.fixture();module.run_action=lambda *a:self.fail('Stale selection reached run_action')
        native.add('/api/command?action=switch&sim_id=42');adapter.ingress();native.generation=8
        self.assertTrue(module._process_pending());self.assertEqual(native.receipts[ID]['state'],'failed')

    def test_actual_readiness_is_shared_without_broadening_ea_owner_actions(self):
        module,native,adapter=self.fixture()
        module._ALARM_READY=False;module._APEX_CORE_TICK_READY=False
        self.assertFalse(module._apex_owner_action_ready('overlay_display_status'))
        module._APEX_CORE_TICK_READY=True
        self.assertTrue(module._apex_owner_action_ready('overlay_display_status'))
        self.assertFalse(module._apex_owner_action_ready('switch'))
        module._ALARM_READY=True;self.assertTrue(module._apex_owner_action_ready('switch'))

    def test_display_dispatch_observes_fresh_arbitrary_metadata_each_time(self):
        from enum import IntEnum
        class Kind(IntEnum):HUMAN=1;ALIEN=2
        sim=Object(id=2**64-1,household_id=42,full_name='Before',occult_types=2,current_occult_types=2)
        sim.occult_tracker=Object(_sim_info_map={Kind.HUMAN:object(),Kind.ALIEN:object()},_occult_form_available=True)
        sim.household=Object(sim_info_gen=lambda:iter((sim,)))
        fixture=Object(services=Object(sim_info_manager=lambda:Object(get=lambda sid:sim if sid==sim.id else None),
            get_persistence_service=lambda:Object(get_save_slot_proto_guid=lambda:55)),
            _APEX_GAME_THREAD_IDENT=threading.current_thread().ident,_get_active_sim_info=lambda:sim,
            _sim_label=lambda value:value.full_name,_get_occult_flags=lambda value:value.occult_types,
            _get_current_flags=lambda value:value.current_occult_types,_form_map=lambda tracker:tracker._sim_info_map,
            _all_occults=lambda include_human=False:(Kind.ALIEN,),_has_occult=lambda tracker,kind:True,
            _safe_name=lambda kind:kind.name,_APEX7_WARNINGS={},_LOCK=threading.RLock(),_HISTORY=[],
            _BUILD_VERSION='arbitrary',_ALARM_READY=True,_SERVER_RUNNING=True,_AUTO_REPAIR=False,_NATIVE_STATUS='available')
        module,native,adapter=self.fixture()
        module.run_action=lambda action,sid,occult,value:display(fixture,sid,value)
        for index,label in enumerate(('Before','After')):
            sim.full_name=label;rid=format(index+1,'032x')
            native.add('/api/overlay/display?count=0&sim_id='+str(sim.id),rid)
            module._process_pending();result=native.receipts[rid]['result']
            self.assertEqual(result['status']['sim'],label)
            self.assertTrue(result['display_metadata_only']);self.assertFalse(result['appearance_read'])
            self.assertFalse(result['mutation_authority'])

    def test_loaded_binding_never_rehashes_or_takes_loader_lock_on_tick(self):
        ns={'_OWNER_MAILBOX_BINDING':None}
        functions(WORK/'apex_core/overlay_loader.py',('owner_mailbox_binding',),ns)
        self.assertIsNone(ns['owner_mailbox_binding']('unused'))
        import os
        binding=(object(),object());ns.update(_OWNER_MAILBOX_BINDING=binding,os=os,_LOADED_ARCHIVE='archive',_archive_name=lambda _:'archive')
        self.assertIs(ns['owner_mailbox_binding']('exact loaded owner'),binding)
        ns['_archive_name']=lambda _:'foreign'
        with self.assertRaises(ValueError):ns['owner_mailbox_binding']('foreign')
    def test_idle_peek_retains_gil_while_control_keeps_standard_native_call_semantics(self):
        calls={}
        class Function:
            def __init__(self,symbol):calls[symbol[0]]=self._flags_
            def __call__(self,*args):return 0
        native=Object(_SimpleCData=object,CFuncPtr=Function,FUNCFLAG_STDCALL=0,FUNCFLAG_PYTHONAPI=4)
        ns={'json':json,'_integer':lambda call:call()}
        functions(WORK/'apex_core/overlay_loader.py',('_bind_owner_mailbox',),ns)
        self.assertIsNotNone(ns['_bind_owner_mailbox'](native,123))
        self.assertEqual(calls['ApexOwnerMailboxPending'],4)
        self.assertEqual(calls['ApexOwnerMailboxControl'],0)
        del native.FUNCFLAG_PYTHONAPI
        self.assertIsNone(ns['_bind_owner_mailbox'](native,123))

    def test_accepted_native_worker_has_no_http_fallback_or_sleep(self):
        cpp=(ROOT/'NativeOverlay/Source/TD1ApexD3D11Proxy.cpp').read_text()
        start=cpp.index('static bool NativeOwnedCommand(');end=cpp.index('static bool HttpGet(',start)
        native=cpp[start:end]
        self.assertEqual(native.count('return false;'),2)
        self.assertNotIn('HttpGet(',native);self.assertNotIn('Sleep(',native)
        self.assertIn('Admission::Unready)return false;',native)
        self.assertIn('mailbox->Wait(',native)
        self.assertIn('generation!=g_selectionGeneration',native)
        self.assertIn('return true;',native)
        owned=cpp[cpp.index('static bool HttpOwnedCommand('):cpp.index('static std::string ResourceKey(')]
        self.assertLess(owned.index('if(NativeOwnedCommand('),owned.index('bool received=HttpGet('))
        self.assertIn('review?60000:8000,expectedGeneration',owned)
    def test_display_ui_publication_rejects_newer_selection_without_cancelling_receipt(self):
        cpp=(ROOT/'NativeOverlay/Source/TD1ApexD3D11Proxy.cpp').read_text()
        start=cpp.index('static void WorkerLoop()');end=cpp.index('static void EnsureWorker()',start)
        worker=cpp[start:end];start=worker.index('if (g_visible.load() && !g_nativeCasPaneVisible.load()')
        display=worker[start:]
        capture=display.index('sim = g_selectedSim; generation = g_selectionGeneration;')
        receive=display.index('bool ok = HttpGet(path, body);',capture)
        lock=display.index('std::lock_guard<std::mutex> lock(g_dataMutex);',receive)
        reject=display.index('if (generation != g_selectionGeneration) continue;',lock)
        publish=display.index('g_json = body;',reject)
        self.assertLess(capture,receive);self.assertLess(receive,lock);self.assertLess(reject,publish)
        self.assertNotIn('cancel(',display)

if __name__=='__main__':unittest.main()
