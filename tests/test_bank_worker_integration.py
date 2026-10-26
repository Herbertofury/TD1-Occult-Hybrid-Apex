"""Production dispatcher/loader/queue integration for the gated prepare slice."""
from pathlib import Path
import json
import os
import sys
import tempfile
import threading
from types import SimpleNamespace as Object
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core import bank_worker, cas_bank_transaction as receiver, overlay_loader as loader, test_driver
from apex_core.command_queue import OwnerContinuation
from tests import test_owner_mailbox_integration as mailbox_tests
from tests.test_owner_mailbox import ID
functions,WORK,ROOT=mailbox_tests.functions,mailbox_tests.WORK,mailbox_tests.ROOT


class BankIntegration(unittest.TestCase):
    def fixture(self):
        module,native,adapter=mailbox_tests.Integration.fixture(self)
        module.services=Object(client_manager=lambda:Object(get_first_client=lambda:None))
        module.json=json;module.__file__='authenticated.ts4script/td1_occult_hybrid_apex.pyc'
        module._APEX_ASYNC_BANK_PREPARE_ENABLED=True
        module._get_sim_info_by_id=lambda _:Object(id=42)
        functions(WORK/'td1_occult_hybrid_apex.py',('run_action','_apex_cas_transaction_argument','_apex_zone_queue_ready'),module.__dict__)
        return module,native,adapter

    def test_real_dispatcher_retains_continuation_before_dict_metrics_and_publishes_terminal(self):
        module,native,adapter=self.fixture();admissions=[];resumes=[];metrics=[]
        module._record_perf=lambda name,*a,**k:metrics.append(name)
        class Prepare(OwnerContinuation):
            def __init__(self,backend,sim,argument,binding,rid):
                admissions.append((rid,argument,binding));self.count=0
            def resume(self):
                resumes.append(module._APEX_COMMANDS.current_request_id());self.count+=1
                return self if self.count==1 else dict(ok=True,async_prepare=True,complete='unchanged fields')
        native.add('/api/command?action=cas_bank_prepare&sim_id=42&value=%7B%7D')
        with patch.object(bank_worker,'PrepareAction',Prepare),patch.object(loader,'bank_worker_binding',return_value='frozen'),\
                patch.object(receiver,'prepare',side_effect=AssertionError('Async accepted action fell back to sync')):
            module._process_pending()
            row=module._APEX_COMMANDS.records[ID]
            self.assertEqual(row['state'],'running');self.assertIsNone(row['result']);self.assertFalse(row['event'].is_set())
            self.assertEqual(native.receipts[ID]['state'],'running')
            # Turning the feature off affects NEW admission, not this retained action.
            module._APEX_ASYNC_BANK_PREPARE_ENABLED=False
            module._process_pending();module._process_pending()
        self.assertEqual(len(admissions),1);self.assertEqual(admissions[0],(ID,{},'frozen'))
        self.assertEqual(resumes,[ID,ID]);self.assertEqual(metrics,['cas_bank_prepare:owner-admission'])
        self.assertEqual(native.receipts[ID]['state'],'completed');self.assertTrue(native.receipts[ID]['result']['async_prepare'])

    def test_enabled_route_requires_real_owned_uuid_and_disabled_route_stays_synchronous(self):
        module,native,adapter=self.fixture()
        queue=module._APEX_COMMANDS
        rid=queue.submit({'action':'cas_bank_prepare'},request_id=ID)['request_id']
        # Only an actual typed direct queue entry selects the async route.
        # Fault its UUID accessor while retaining that real outer action;
        # ordinary nonqueued calls intentionally remain synchronous.
        with patch.object(queue,'current_request_id',return_value=None),patch.object(bank_worker,'PrepareAction') as start:
            queue.drain(lambda payload:module.run_action(payload['action'],'42',value='{}'))
            result=queue.records[rid]['result']
            self.assertFalse(result['ok']);self.assertIn('canonical queue UUID',result['message']);start.assert_not_called()
        module._APEX_ASYNC_BANK_PREPARE_ENABLED=False
        with patch.object(receiver,'prepare',return_value={'ok':True,'synchronous':True}) as prepare:
            self.assertTrue(module.run_action('cas_bank_prepare','42',value='{}')['synchronous']);prepare.assert_called_once()

    def test_zone_change_keeps_running_uuid_and_later_fence_failure_does_not_replay_or_cancel_it(self):
        module,native,adapter=self.fixture();calls=[];valid=[True]
        class Prepare(OwnerContinuation):
            def __init__(self,*args):calls.append('admit')
            def resume(self):
                calls.append('resume')
                if not valid[0]:raise ValueError('Fresh zone/native before-image changed; durable WAL retained')
                return self
        native.add('/api/command?action=cas_bank_prepare&sim_id=42&value=%7B%7D')
        module._APEX_OWNER_MAILBOX.retire=lambda _:adapter.retire()
        module._ALARM_HANDLE=None;module._setup_alarm=lambda:True;module._apex_start_overlay=lambda **k:{'ok':True}
        with patch.object(bank_worker,'PrepareAction',Prepare),patch.object(loader,'bank_worker_binding',return_value='frozen'):
            module._process_pending();row=module._APEX_COMMANDS.records[ID];held=row['_continuation'];event=row['event']
            module._apex_zone_queue_ready(Object())
            self.assertEqual(row['state'],'running');self.assertIs(row['_continuation'],held);self.assertIs(row['event'],event)
            self.assertFalse(event.is_set());self.assertEqual(native.receipts[ID]['state'],'running')
            valid[0]=False;module._process_pending()
        self.assertEqual(calls,['admit','resume']);self.assertEqual(module._APEX_COMMANDS.status(ID)['state'],'failed')
        # The retired native runtime never receives a fabricated cancellation or
        # a different runtime's terminal result for its original UUID.
        self.assertEqual(native.receipts[ID]['state'],'running')

    def test_disposable_toggle_is_strict_boolean_guarded_and_changes_only_new_admission(self):
        module,native,adapter=self.fixture()
        with patch.object(test_driver,'guard',return_value=True),patch.object(loader,'bank_worker_binding',return_value=object()) as binding:
            result=test_driver.dispatch(module,'test_async_bank_prepare',None,'typed disposable envelope')
            self.assertTrue(result['enabled']);binding.assert_called_once_with(module.__file__)
        with patch.object(test_driver,'guard',return_value=False),patch.object(loader,'bank_worker_binding',side_effect=AssertionError('Disable must not rebind')):
            self.assertFalse(test_driver.dispatch(module,'test_async_bank_prepare',None,'typed')['enabled'])
        with patch.object(test_driver,'guard',return_value=1):
            with self.assertRaises(ValueError):test_driver.dispatch(module,'test_async_bank_prepare',None,'typed')
        with patch.object(test_driver,'guard',side_effect=ValueError('Wrong disposable token')):
            with self.assertRaises(ValueError):test_driver.dispatch(module,'test_async_bank_prepare',None,'foreign')


class BankBinding(unittest.TestCase):
    def test_actual_low_level_binding_has_u64_and_gil_held_submit_pollcopy(self):
        seen={}
        class Function:
            def __init__(self,symbol):seen[symbol[0]]=(self._flags_,self._restype_._type_,tuple(t._type_ for t in self._argtypes_))
        native=Object(_SimpleCData=object,CFuncPtr=Function,FUNCFLAG_STDCALL=0,FUNCFLAG_PYTHONAPI=4)
        self.assertIsNotNone(loader._bind_bank_exports(native,123))
        self.assertEqual(seen['ApexBankBind'],(0,'Q',('z','Q')))
        self.assertEqual(seen['ApexBankSubmit'],(4,'Q',('Q','z','Q','z','Q')))
        self.assertEqual(seen['ApexBankPollCopy'],(4,'z',('Q','z','Q','Q')))
        del native.FUNCFLAG_PYTHONAPI;self.assertIsNone(loader._bind_bank_exports(native,123))

    def test_root_matches_loaded_profile_and_active_binding_never_rehashes_or_rebinds(self):
        with tempfile.TemporaryDirectory() as temp:
            profile=Path(temp)/'The Sims 4';root=profile/'TD1_OccultHybridApexData';root.mkdir(parents=True)
            archive=profile/'Mods/Apex/ApexOccultHybrid.ts4script';source=str(archive/'td1_occult_hybrid_apex.pyc')
            calls=[]
            def bind(raw,length):calls.append(('bind',raw,length));return Object(value=2**48+33)
            def submit(cap,head,hsize,payload,psize):calls.append(('submit',cap,head,hsize,payload,psize));return Object(value=2**48+7)
            def poll(cap,head,hsize,ticket):calls.append(('poll',cap,head,hsize,ticket));return Object(value=b'{"ok":true,"state":"pending"}')
            with patch.multiple(loader,_HANDLE=object(),_STATUS={'ok':True},_LOADED_ARCHIVE=os.path.normcase(str(archive)),
                    _BANK_EXPORTS=(bind,submit,poll),_BANK_BINDING=None,_BANK_ROOT=None):
                with self.assertRaises(ValueError):loader._configure_bank_worker(source,Path(temp)/'The Sims 4 DO NOT TOUCH/TD1_OccultHybridApexData')
                self.assertEqual(calls,[])
                binding=loader._configure_bank_worker(source,root)
                self.assertEqual(str(binding.path),str(root/'form_bank.json'))
                with patch.object(loader,'_unlinked',side_effect=AssertionError('Active binding restatted root')),\
                        patch.object(loader,'sidecar_paths',side_effect=AssertionError('Active binding rehashed DLL')):
                    self.assertIs(loader.bank_worker_binding(source),binding)
                    self.assertIs(loader._configure_bank_worker(source,root),binding)
                    self.assertEqual(binding.submit({'request_id':'a'*32}),2**48+7)
                    self.assertEqual(binding.poll({'request_id':'a'*32},2**48+7)['state'],'pending')
                self.assertEqual(calls[1][1],2**48+33);self.assertEqual(calls[2][1],2**48+33)
                self.assertEqual(calls[2][-1],2**48+7)
                with self.assertRaises(ValueError):loader.bank_worker_binding(source.replace('The Sims 4','Foreign profile'))

    def test_three_rust_exports_are_force_linked_and_exported_from_actual_target(self):
        source=(ROOT/'NativeOverlay/Source/TD1ApexD3D11Proxy.cpp').read_text()
        for name in ('ApexBankBind','ApexBankSubmit','ApexBankPollCopy'):
            self.assertIn('"/INCLUDE:'+name+'"',source);self.assertIn('"/EXPORT:'+name+'"',source)


if __name__=='__main__':unittest.main()
