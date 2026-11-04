from pathlib import Path
import json
import sys
import threading
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core.command_queue import CommandQueue
from apex_core import owner_mailbox as module

ID='1'*32

class Native:
    def __init__(self):
        self.runtime=dict(nonce='a'*32,pid=100,owner=200,epoch=1)
        self.jobs=[];self.receipts={};self.calls=[];self.generation=7;self.fail=False;self.valid=True;self.pending_calls=0
    def add(self,path,rid=ID):
        self.jobs.append(dict(ticket=len(self.receipts)+len(self.jobs)+1,request_id=rid,selection=7,request=path))
    def pending(self):
        self.pending_calls+=1;return bool(self.jobs)
    def __call__(self,request):
        self.calls.append(request);op=request['operation']
        if op=='bind':return dict(ok=True,runtime=self.runtime)
        if request['runtime']!=self.runtime:return dict(ok=False)
        if op=='take':return dict(ok=True,job=self.jobs.pop(0) if self.jobs else None)
        if op=='publish':
            if self.fail:return dict(ok=False)
            row=json.loads(request['receipt']);assert row['request_id']==request['request_id'];self.receipts[row['request_id']]=row;return dict(ok=True)
        if op=='authorize':return dict(ok=self.valid and self.generation==7)
        if op=='retire':self.valid=False;return dict(ok=True)
        raise AssertionError(op)

class Tests(unittest.TestCase):
    def setUp(self):
        self.queue=CommandQueue();self.native=Native();self.calls=[]
        self.adapter=module.OwnerIngress(self.queue,self.native,self.native.pending,threading.current_thread().ident,'a'*32,100,lambda _:True)
    def drain(self,result=None):
        def execute(payload):
            self.adapter.before_execute(payload);self.calls.append(payload)
            return result or dict(ok=True)
        self.queue.drain(execute,max_commands=1)
        self.adapter.completions()
    def test_real_queue_executes_once_with_original_uuid_without_wait(self):
        self.assertNotEqual(self.adapter.owner_ident,self.adapter.runtime['owner'])
        self.native.add('/api/command?action=switch&sim_id=42&occult=ALIEN')
        with patch.object(self.queue,'wait',side_effect=AssertionError('Owner blocked in wait')):
            self.adapter.ingress();self.assertEqual(self.queue.status(ID)['state'],'pending');self.drain()
        self.assertEqual(len(self.calls),1);self.assertEqual(self.calls[0]['sim_id'],'42')
        self.assertEqual(self.native.receipts[ID],self.queue.status(ID));self.assertFalse(self.adapter.active)
    def test_foreign_thread_cannot_ingress(self):
        self.native.add('/api/command?action=status');errors=[]
        def run():
            try:self.adapter.ingress()
            except ValueError as error:errors.append(str(error))
        thread=threading.Thread(target=run);thread.start();thread.join()
        self.assertEqual(len(errors),1);self.assertFalse(self.queue.pending)
    def test_invalid_or_duplicate_typed_fields_never_reach_action(self):
        for index,path in enumerate(('/api/command?action=switch&action=remove','/api/command?action=status&request_id='+ID,
                'https://foreign.invalid/api/command?action=status','/api/command?action=status&value=%xy',
                '/api/command?action=status&value=%FF','/api/foreign?action=status','/api/command?action=exec%28code%29')):
            rid=format(index+1,'032x');self.native.add(path,rid);self.adapter.ingress();self.drain()
            self.assertFalse(self.native.receipts[rid]['result']['owner_queue_accepted'])
        self.assertEqual(self.calls,[])
    def test_unready_canonical_action_is_explicitly_cancelled(self):
        self.adapter.ready=lambda _:False;self.native.add('/api/command?action=switch');self.adapter.ingress();self.drain()
        self.assertEqual(self.native.receipts[ID]['state'],'cancelled');self.assertEqual(self.calls,[])
    def test_uuid_collision_never_claims_foreign_action_was_cancelled(self):
        self.queue.submit({'action':'existing'},request_id=ID)
        self.native.add('/api/command?action=switch');self.adapter.ingress()
        self.assertEqual(self.native.receipts[ID]['state'],'unknown')
        self.assertEqual(self.queue.records[ID]['payload'],{'action':'existing'})
        self.assertEqual(len(self.queue.pending),1)
        self.adapter.retire();self.assertEqual(self.queue.status(ID)['state'],'pending')
    def test_selection_change_blocks_action_immediately_before_execute(self):
        self.native.add('/api/command?action=switch');self.adapter.ingress();self.native.generation=8;self.drain()
        self.assertEqual(self.calls,[]);self.assertEqual(self.native.receipts[ID]['state'],'failed')
    def test_completed_write_keeps_original_target_when_selection_changes_during_action(self):
        self.native.add('/api/command?action=switch&sim_id=42');self.adapter.ingress()
        def execute(payload):
            self.adapter.before_execute(payload)
            self.calls.append(payload['sim_id']);self.native.generation=8
            return dict(ok=True,original_target=payload['sim_id'],write_completed=True)
        self.queue.drain(execute,max_commands=1);self.adapter.completions()
        self.assertEqual(self.calls,['42']);self.assertEqual(self.native.receipts[ID]['state'],'completed')
        self.assertEqual(self.native.receipts[ID]['result']['original_target'],'42')
        self.assertTrue(self.native.receipts[ID]['result']['write_completed'])
    def test_foreign_runtime_blocks_action(self):
        self.native.add('/api/command?action=switch');self.adapter.ingress();self.native.valid=False;self.drain()
        self.assertEqual(self.calls,[]);self.assertEqual(self.queue.status(ID)['state'],'failed')
    def test_payload_change_after_admission_does_not_execute(self):
        self.native.add('/api/command?action=switch');self.adapter.ingress()
        self.queue.records[ID]['payload']['action']='remove';self.drain()
        self.assertEqual(self.calls,[]);self.assertEqual(self.native.receipts[ID]['state'],'failed')
    def test_lost_completion_publish_retries_bytes_without_resubmission(self):
        self.native.add('/api/command?action=switch');self.adapter.ingress()
        def execute(payload):
            self.adapter.before_execute(payload);self.calls.append(payload);return dict(ok=True,unique='actual')
        self.queue.drain(execute,max_commands=1);self.native.fail=True;self.adapter.completions()
        frozen=self.adapter.active[ID]['outbound'];self.native.fail=False;self.adapter.completions()
        self.assertEqual(self.queue.executed,1);self.assertEqual(len(self.calls),1)
        self.assertEqual(self.native.receipts[ID],json.loads(frozen));self.assertFalse(self.adapter.active)
    def test_lost_submission_receipt_is_not_requeued(self):
        self.native.add('/api/command?action=status');self.native.fail=True;self.adapter.ingress()
        self.native.fail=False;self.adapter.completions();self.assertEqual(len(self.queue.pending),1)
        self.drain();self.assertEqual(self.queue.executed,1)
    def test_retire_cancels_pending_with_real_queue_receipt(self):
        self.native.add('/api/command?action=switch');self.adapter.ingress();self.assertTrue(self.adapter.retire())
        self.assertEqual(self.queue.status(ID)['state'],'cancelled');self.assertEqual(self.native.receipts[ID],self.queue.status(ID))
        self.queue.drain(lambda _:self.fail('Retired action executed'));self.assertEqual(self.calls,[])
    def test_display_runs_fresh_each_time_on_owner(self):
        name=['Before'];returned=[]
        for index in range(2):
            rid=format(index+1,'032x');self.native.add('/api/overlay/display?count=0&sim_id=42',rid);self.adapter.ingress()
            def execute(payload):
                self.adapter.before_execute(payload);self.assertEqual(payload['action'],'overlay_display_status')
                self.assertEqual(json.loads(payload['value']),{'count':0});returned.append(name[0]);return dict(ok=True,name=name[0])
            self.queue.drain(execute,max_commands=1);self.adapter.completions();name[0]='After'
        self.assertEqual(returned,['Before','After'])
    def test_idle_uses_one_cheap_pending_check_and_no_serialization(self):
        before=len(self.native.calls)
        with patch.object(module,'_wire',side_effect=AssertionError('Idle serialization')):
            self.assertEqual(self.adapter.ingress(),0);self.assertEqual(self.adapter.completions(),0)
        self.assertEqual(len(self.native.calls),before);self.assertEqual(self.native.pending_calls,1)

if __name__=='__main__':unittest.main()
