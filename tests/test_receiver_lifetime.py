"""Receiver lifetime/capability regressions using detached fixtures only."""
from pathlib import Path
import ast,gc,importlib.util,os,sys,threading,types,unittest,weakref
from types import SimpleNamespace as Obj
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'Source')]
from receiver_contract_fixtures import assert_contract
from apex_core.receiver_lifetime import ReceiverLifetime,Completion
from apex_core import cas_bank_transaction as bank,native_cas_engine as native,cas_ui,overlay_loader,bank_worker
from apex_core.command_queue import CommandQueue,OwnerContinuation
import json
import test_cas_bank_transaction as fixtures

ActualReceiverLifetime=ReceiverLifetime
def make_registry(*args,**kwargs):
    value=ActualReceiverLifetime(*args,**kwargs);value.bind_owner(threading.current_thread().ident);return value

class Owner:pass
class NoScan(dict):
 def __iter__(self):raise AssertionError('No receiver enumeration allowed')
 def items(self):raise AssertionError('No receiver enumeration allowed')
 def values(self):raise AssertionError('No receiver enumeration allowed')

class LifetimeTests(unittest.TestCase):
 def make(self,registry,sid=1,scope=None,epoch='e'*64,token=None,path='/checked'):
  owner=Owner();instance=Owner();instance.state='completed';instance.journal_sha256='a'*64;instance.heavy=bytearray(1024)
  captured={'sim':owner,'native_return_required':scope is not None};key=registry.install(registry.preflight(path, '30:'+str(sid)),token or format(sid,'032x'),captured);registry.active[key]=instance
  certificate=registry.certify(key,captured,instance,(os.getpid(),'30','20',str(sid)),epoch,'a'*64,'b'*64,scope,3 if scope else None,'c'*64 if scope else None)
  return key,captured,instance,certificate
 def scope(self,sids,scope='d'*32,epoch='e'*64):
  value=dict(pid=os.getpid(),scope_id=scope,epochs={str(s):epoch for s in sids},load_identity=dict(save_guid='30',household_id='20'),completions={str(s):dict(epoch=epoch,generation=3,native_return_sha256='c'*64)for s in sids})
  receipt=dict(ok=True,pid=os.getpid(),scope_id=scope,armed=True,selection_enabled=False,members=[dict(sim_id=str(s),imported_mask=0)for s in sids]);return value,receipt
 def test_thousand_distinct_completed_sims_do_not_accumulate_native_receivers(self):
  registry=make_registry({}, {},capacity=256,completed_limit=32);refs=[]
  for sid in range(1,1026):
   key,captured,instance,_=self.make(registry,sid);refs.extend((weakref.ref(captured['sim']),weakref.ref(instance)));registry.retire_unbound(key);del captured,instance
   self.assertEqual(len(registry.captured),0);self.assertEqual(len(registry.active),0)
  gc.collect();self.assertTrue(all(r()is None for r in refs));self.assertEqual(len(registry.finished),32);self.assertEqual(len(registry.current),0)
 def test_256_unresolved_receivers_remain_bounded_and_257th_refuses_without_eviction(self):
  registry=make_registry({},{});held=[]
  for sid in range(1,257):
   cap={};key=registry.install(registry.preflight('/checked','30:'+str(sid)),format(sid,'032x'),cap);held.append((key,cap))
  with self.assertRaises(ValueError):registry.preflight('/checked','30:257')
  with self.assertRaises(ValueError):registry.preflight('/checked','30:1')
  self.assertEqual(len(registry.captured),256);self.assertTrue(all(registry.captured[k]is c for k,c in held))
 def test_certified_same_sim_replacement_at_capacity_keeps_all_other_unresolved_rows(self):
  registry=make_registry({},{});key,cap,instance,_=self.make(registry)
  for sid in range(2,257):registry.install(registry.preflight('/checked','30:'+str(sid)),format(sid,'032x'),{})
  others={k:id(v)for k,v in registry.captured.items()if k!=key};new=registry.install(registry.preflight('/checked','30:1'),'f'*32,{'new':True})
  self.assertNotEqual(new,key);self.assertEqual(len(registry.captured),256);self.assertNotIn(key,registry.active);self.assertIsNotNone(registry.diagnostic_receipt(key));self.assertEqual(others,{k:id(v)for k,v in registry.captured.items()if k!=new})
 def test_reused_token_or_changed_reservation_cannot_drop_old_completed_row(self):
  registry=make_registry({},{});key,cap,instance,_=self.make(registry);reservation=registry.preflight('/checked','30:1')
  with self.assertRaises(ValueError):registry.install(reservation,key[2],{})
  self.assertIs(registry.captured[key],cap);self.assertIs(registry.active[key],instance)
  registry.current[key[:2]]=('/checked','30:1','f'*32)
  with self.assertRaises(ValueError):registry.install(reservation,'a'*32,{})
  self.assertIs(registry.captured[key],cap)
 def test_scope_retirement_requires_every_exact_completed_member_before_dropping_any(self):
  registry=make_registry({},{});a=self.make(registry,1,scope='d'*32);b=self.make(registry,2,scope='d'*32);scope,receipt=self.scope([1,2]);b[2].state='recovery-required'
  with self.assertRaises(ValueError):registry.retire_scope('/checked',scope,receipt)
  self.assertEqual(len(registry.captured),2);b[2].state='completed';result=registry.retire_scope('/checked',scope,receipt);self.assertEqual(result['retired'],2);self.assertEqual(registry.captured,{})
 def test_false_unknown_lost_ack_foreign_scope_epoch_and_generation_retain_all(self):
  for case in('false','missing','scope','epoch','generation','member','mask'):
   registry=make_registry({},{});key,cap,instance,_=self.make(registry,1,scope='d'*32);scope,receipt=self.scope([1])
   if case=='false':receipt['ok']=False
   elif case=='missing':receipt.pop('ok')
   elif case=='scope':receipt['scope_id']='f'*32
   elif case=='epoch':scope['epochs']['1']='f'*64
   elif case=='generation':scope['completions']['1']['generation']=4
   elif case=='member':receipt['members']=[]
   else:receipt['members'][0]['imported_mask']=1
   with self.assertRaises(ValueError,msg=case):registry.retire_scope('/checked',scope,receipt)
   self.assertIs(registry.captured[key],cap);self.assertIs(registry.active[key],instance)
 def test_old_scope_receipt_cannot_retire_newer_same_sim_receiver(self):
  registry=make_registry({},{});old=self.make(registry,1,scope='d'*32);scope,receipt=self.scope([1]);registry.retire_scope('/checked',scope,receipt)
  new=self.make(registry,1,scope='f'*32,epoch='9'*64,token='f'*32)
  with self.assertRaises(ValueError):registry.retire_scope('/checked',scope,receipt)
  self.assertIs(registry.captured[new[0]],new[1]);self.assertTrue(registry.diagnostic_receipt(old[0])['historical']);self.assertFalse(registry.diagnostic_receipt(old[0])['appearance_replay_authorized'])
 def test_running_prepare_is_pinned_across_scope_change_and_never_retired(self):
  registry=make_registry({},{});key,cap,instance,_=self.make(registry,1,scope='d'*32);registry.pin_prepare(key,cap,'7'*32);scope,receipt=self.scope([1])
  with self.assertRaises(ValueError):registry.retire_scope('/checked',scope,receipt)
  with self.assertRaises(ValueError):registry.finish_prepare(key,cap,'8'*32)
  self.assertEqual(cap['prepare_async_inflight'],'7'*32);registry.finish_prepare(key,cap,'7'*32);instance.state='recovery-required'
  with self.assertRaises(ValueError):registry.retire_scope('/checked',scope,receipt)
  self.assertIs(registry.captured[key],cap)
 def test_keyed_lookup_works_with_no_iterable_receiver_maps_and_rejects_tampering(self):
  registry=make_registry(NoScan(),NoScan());key,cap,instance,_=self.make(registry)
  self.assertEqual(registry.lookup('/checked','30:1',True),(key,cap));registry.captured[('/checked','30:2','f'*32)]={}
  with self.assertRaises(ValueError):registry.lookup('/checked','30:1',True)
 def test_import_thread_is_not_authority_and_binding_retains_active_work(self):
  values=[]
  t=threading.Thread(target=lambda:values.append(ActualReceiverLifetime({},{})));t.start();t.join();registry=values[0]
  self.assertIsNone(registry.owner)
  with self.assertRaises(ValueError):registry.preflight('/checked','30:1')
  registry.bind_owner(threading.current_thread().ident);key,cap,active,_=self.make(registry);registry.bind_owner(threading.current_thread().ident)
  errors=[]
  def transfer():
   try:registry.bind_owner(threading.current_thread().ident)
   except Exception as error:errors.append(error)
  t=threading.Thread(target=transfer);t.start();t.join();self.assertEqual(len(errors),1);self.assertIs(registry.captured[key],cap)
 def test_json_like_forged_certificate_and_cross_thread_calls_have_no_authority(self):
  with self.assertRaises(ValueError):Completion({},('/checked','30:1','a'*32),(os.getpid(),'30','20','1'),'e'*64,'a'*64,'b'*64,None,None,None)
  registry=make_registry({},{});errors=[]
  def wrong():
   try:registry.preflight('/checked','30:1')
   except Exception as error:errors.append(error)
  t=threading.Thread(target=wrong);t.start();t.join();self.assertEqual(len(errors),1);self.assertEqual(registry.captured,{})

class SourceContractTests(unittest.TestCase):
 def test_all_fresh_owner_fences_and_byte_worker_receipt_checks_are_unchanged(self):assert_contract(self,bank_worker,'bank_worker')
 def test_permanent_completed_validation_and_all_atomic_storage_barriers_are_unchanged(self):assert_contract(self,bank,'cas_bank_transaction')
 def test_every_other_native_engine_function_is_unchanged(self):assert_contract(self,native,'native_cas_engine')

class SourceIntegrationTests(unittest.TestCase):
 def setUp(self):
  bank._CAPTURED={};bank._ACTIVE={}
  self.addCleanup(lambda:bank._CAPTURED.clear());self.addCleanup(lambda:bank._ACTIVE.clear());self.addCleanup(setattr,native,'_LAYOUT_SCOPE',None)
  self.fx=fixtures.CasBankReceiverTests('runTest');self.fx.setUp();self.addCleanup(self.fx.doCleanups);bank._RECEIVERS=make_registry(bank._CAPTURED,bank._ACTIVE);native._LAYOUT_SCOPE=None
 def completed(self):
  f=self.fx;f.begin();f.observe();f.prepare([]);return f.commit()
 def test_real_receiver_commit_retires_heavy_objects_and_duplicate_commit_uses_durable_receipt(self):
  f=self.fx;f.begin();f.observe();f.prepare([]);instance=next(iter(bank._ACTIVE.values()));ref=weakref.ref(instance);del instance;result=f.commit();gc.collect();self.assertIsNone(ref());self.assertEqual(result['receiver_lifetime']['retired'],1);self.assertEqual(bank._CAPTURED,{});self.assertEqual(bank._ACTIVE,{})
  before=f.path.read_bytes();writes=list(f.native_writes);second=f.commit();self.assertTrue(second['already_completed']);self.assertFalse(second['replayed']);self.assertEqual(before,f.path.read_bytes());self.assertEqual(writes,f.native_writes);self.assertTrue(bank._completed(f.record()['cas_transaction']))
 def test_real_receiver_same_sim_can_begin_again_after_completion_without_rehydration(self):
  self.completed();old=self.fx.epoch;self.fx.begin();self.assertNotEqual(self.fx.epoch,old);self.assertEqual(len(bank._CAPTURED),1);self.assertEqual(bank._ACTIVE,{})
 def test_actual_native_verified_scope_retirement_releases_only_the_completed_matching_receivers(self):
  registry=bank._RECEIVERS;test=LifetimeTests();path=str(Path(self.fx.temp.name)/'form_bank.json')
  held=[test.make(registry,sid,scope='d'*32,path=path)for sid in(1,2)];scope,receipt=test.scope([1,2]);native._LAYOUT_SCOPE=scope
  backend=Obj(_APEX_GAME_THREAD_IDENT=threading.current_thread().ident,_data_directory=lambda:self.fx.temp.name,__file__='fixture',_get_sim_info_by_id=lambda *_:self.fail('Lifetime release must not read game Sims'))
  with patch.object(cas_ui,'diagnostics',return_value={'native_peers':[]}),patch.object(overlay_loader,'native_cas_engine_control',return_value=receipt)as call,patch.dict(sys.modules,{'paths':Obj(DLL_PATH='fixture')}):
   result=native._retire_completed_scope(backend,scope)
   self.assertTrue(result['retired']);self.assertEqual(result['receiver_lifetime']['retired'],2);self.assertEqual(registry.captured,{});self.assertEqual(registry.active,{});self.assertIsNone(native._LAYOUT_SCOPE);self.assertEqual(call.call_count,1)
   with self.assertRaises(ValueError):native._retire_completed_scope(backend,scope)
   self.assertEqual(call.call_count,1)
 def test_planned_or_uncommitted_real_receiver_cannot_be_certified(self):
  f=self.fx;f.begin();f.observe();f.prepare([]);path,key,record,transaction=bank._selected(f.backend,f.sim)
  instance=next(iter(bank._ACTIVE.values()));instance.state='completed'
  with self.assertRaises(ValueError):bank._mark_receiver_completed(f.backend,f.sim,path,key,record,transaction)
  self.assertEqual(len(bank._CAPTURED),1);self.assertIsNotNone(f.record()['pending'])
 def test_actual_prepare_constructor_uses_exact_key_and_running_job_survives_cancel_shutdown_and_scope_change(self):
  f=self.fx;f.backend.services.current_zone=lambda:Obj(is_zone_running=True,is_in_build_buy=False)
  household=Obj(id=f.sim.household_id,sim_info_gen=lambda:iter((f.sim,)))
  f.backend.services.active_household=lambda:household;f.backend._household_sim_infos=lambda sim:(f.sim,)
  f.begin();f.observe();argument=dict(expected_pending_sha256=f.epoch,expected_raw_return_sha256=f.observation['raw_return_sha256'],dispositions=[])
  bank._CAPTURED=NoScan(bank._CAPTURED);bank._ACTIVE=NoScan(bank._ACTIVE);bank._RECEIVERS.captured=bank._CAPTURED;bank._RECEIVERS.active=bank._ACTIVE
  rid='6'*32;submissions=[];polls=[]
  def submit(header,payload):submissions.append((header,payload));return 19
  def poll(header,ticket):polls.append((header,ticket));return b'{"state":"pending"}'
  binding=bank_worker.NativeBinding(f.temp.name,submit,poll)
  with patch.object(cas_ui,'diagnostics',return_value={'native_peers':[]}):
   action=bank_worker.PrepareAction(f.backend,f.sim,argument,binding,rid,native_probe=lambda backend:1)
   self.assertIsInstance(action,OwnerContinuation);key,cap=bank._RECEIVERS.lookup(f.path,f.key,True)
   self.assertEqual(cap['prepare_async_inflight'],rid);self.assertEqual(len(submissions),1)
   q=CommandQueue();q.submit({'action':'cas_bank_prepare'},request_id=rid);q.drain(lambda _:action,max_commands=1)
   self.assertEqual(q.status(rid)['state'],'running');self.assertFalse(q.cancel(rid));q.bind_owner();q.shutdown()
   self.assertEqual(q.status(rid)['state'],'running');self.assertFalse(q.records[rid]['event'].is_set())
   native._LAYOUT_SCOPE={'foreign_scope':'newer'}
   with self.assertRaises(ValueError):bank._RECEIVERS.preflight(f.path,f.key)
   self.assertEqual(cap['prepare_async_inflight'],rid)
   binding.poll_call=lambda header,ticket:b'{"state":"failed","ok":false,"message":"uncertain original ACK"}'
   q.drain(lambda _:self.fail('Initial prepare must never replay'),max_commands=1)
   terminal=q.status(rid);self.assertEqual(terminal['state'],'failed');self.assertFalse(terminal['result']['automatic_replay_allowed']);self.assertIsNone(cap['prepare_async_inflight']);self.assertEqual(bank._ACTIVE[key].state,'recovery-required');self.assertIs(bank._CAPTURED[key],cap);self.assertEqual(len(submissions),1)
   before=len(polls);self.assertIs(action.resume(),action.terminal);self.assertEqual(len(polls),before)
   with self.assertRaises(ValueError):bank._RECEIVERS.preflight(f.path,f.key)
  native._LAYOUT_SCOPE=None
 def test_refused_native_retirement_keeps_source_receivers_and_no_native_retry(self):
  registry=bank._RECEIVERS;test=LifetimeTests();a=test.make(registry,1,scope='d'*32);scope,receipt=test.scope([1]);native._LAYOUT_SCOPE=scope;backend=Obj(_APEX_GAME_THREAD_IDENT=threading.current_thread().ident,_data_directory=lambda:'/checked-parent',__file__='fixture')
  with patch.object(cas_ui,'diagnostics',return_value={'native_peers':[]}),patch.object(overlay_loader,'native_cas_engine_control',return_value=dict(receipt,selection_enabled=True))as call,patch.dict(sys.modules,{'paths':Obj(DLL_PATH='fixture')}):
   with self.assertRaises(ValueError):native._retire_completed_scope(backend,scope)
   self.assertIs(registry.captured[a[0]],a[1]);self.assertTrue(scope['retirement_attempted'])
   with self.assertRaises(ValueError):native._retire_completed_scope(backend,scope)
   self.assertEqual(call.call_count,1)
 def test_actual_native_verified_retirement_keeps_ack_even_if_source_cleanup_refuses(self):
  registry=bank._RECEIVERS;test=LifetimeTests();a=test.make(registry,1,scope='d'*32);scope,receipt=test.scope([1]);native._LAYOUT_SCOPE=scope;backend=Obj(_APEX_GAME_THREAD_IDENT=threading.current_thread().ident,_data_directory=lambda:'/different-root',__file__='fixture')
  with patch.object(cas_ui,'diagnostics',return_value={'native_peers':[]}),patch.object(overlay_loader,'native_cas_engine_control',return_value=receipt)as call,patch.dict(sys.modules,{'paths':Obj(DLL_PATH='fixture')}):
   result=native._retire_completed_scope(backend,scope)
   self.assertTrue(result['retired']);self.assertTrue(result['receiver_lifetime']['retained']);self.assertIs(registry.captured[a[0]],a[1]);self.assertIsNone(native._LAYOUT_SCOPE);self.assertEqual(call.call_count,1)

if __name__=='__main__':unittest.main()
