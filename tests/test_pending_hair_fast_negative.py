"""Actual hair callback regressions using detached temporary banks only."""
from pathlib import Path
import ast,copy,importlib.util,json,os,sys,threading,unittest
from types import SimpleNamespace as Obj
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'Source')]
from receiver_contract_fixtures import assert_contract,legacy_hair_helper
from apex_core import cas_save_boundary as boundary,cas_bank_transaction as bank,form_bank,outfit_hair,form_appearance as appearance,studio
import test_cas_bank_transaction as fixtures

class PendingHairTests(unittest.TestCase):
 def setUp(self):
  self.fx=fixtures.CasBankReceiverTests('runTest');self.fx.setUp();self.addCleanup(self.fx.doCleanups);self.fx.backend._log=lambda _:None;outfit_hair._BACKEND=self.fx.backend;outfit_hair._ERRORS.clear();self.addCleanup(setattr,outfit_hair,'_BACKEND',None)
  data=self.fx.data();record=data['records'][self.fx.key];record['runtime_pid']=os.getpid();record['hair_policy']={'enabled':True,'forms':{lane:outfit_hair.capture(self.fx.backend,fields)for lane,fields in self.fx.originals.items()}};form_bank.save(self.fx.path,data)
 def event(self):outfit_hair._event(self.fx.sim,(0,0),(0,1))
 def stable(self):
  form_bank.load(self.fx.path);self.assertEqual(boundary._READ_INDEX['path'],str(self.fx.path));self.assertEqual(boundary._READ_INDEX['stamp'],boundary._stamp(self.fx.path))
 def baseline_function(self):return legacy_hair_helper(boundary.__dict__)
 def test_actual_pending_callback_avoids_the_old_whole_bank_read_and_no_native_repair_runs(self):
  self.fx.begin();self.stable();load=form_bank.load
  with patch.object(form_bank,'load',wraps=load)as reads:
   self.event();self.assertEqual(reads.call_count,0)
  with patch.object(boundary,'hair_policy_enabled',self.baseline_function()),patch.object(form_bank,'load',wraps=load)as reads:
   self.event();self.assertEqual(reads.call_count,1)
  self.assertEqual(self.fx.native_writes,[]);self.assertIsNotNone(self.fx.record()['pending'])
 def test_stale_stamp_forces_real_read_and_cannot_suppress_current_completed_user_state(self):
  self.fx.begin();self.stable();stale=copy.deepcopy(boundary._READ_INDEX);data=self.fx.data();data['records'][self.fx.key]['pending']=None;data['records'][self.fx.key].pop('cas_transaction');form_bank.save(self.fx.path,data);boundary._READ_INDEX=stale;load=form_bank.load
  with patch.object(form_bank,'load',wraps=load)as reads,patch.object(outfit_hair,'enforce',return_value=False)as enforce:
   self.event();self.assertEqual(reads.call_count,1);enforce.assert_called_once_with(self.fx.backend,self.fx.sim)
 def test_stale_validator_or_untyped_pending_index_falls_back_to_real_permanent_guard(self):
  self.fx.begin();self.stable();source=copy.deepcopy(boundary._READ_INDEX);load=form_bank.load
  for case in('validator','untyped'):
   boundary._READ_INDEX=copy.deepcopy(source)
   if case=='validator':boundary._READ_INDEX['validator']=('old-validator',)
   else:boundary._READ_INDEX['by_save_guid']['30']=['10']
   with patch.object(form_bank,'load',wraps=load)as reads:
    self.event();self.assertEqual(reads.call_count,1,case)
   self.assertEqual(self.fx.native_writes,[])
 def test_foreign_path_index_forces_fresh_actual_index_before_deciding(self):
  self.fx.begin();self.stable();boundary._READ_INDEX=dict(boundary._READ_INDEX,path=str(self.fx.path)+'-foreign');load=form_bank.load
  with patch.object(form_bank,'load',wraps=load)as reads,patch.object(outfit_hair,'enforce',return_value=False)as enforce:
   self.event();self.assertEqual(reads.call_count,1);enforce.assert_not_called()
 def test_other_save_and_other_sim_pending_do_not_suppress_this_valid_opted_in_owner(self):
  data=self.fx.data();data['records']['31:10']={'pending':{'state':'captured'}};data['records']['30:99']['pending']={'state':'captured'};form_bank.save(self.fx.path,data);self.stable()
  with patch.object(form_bank,'load',side_effect=AssertionError('Known stable index needs no full read')),patch.object(outfit_hair,'enforce',return_value=False)as enforce:
   self.event();enforce.assert_called_once_with(self.fx.backend,self.fx.sim)
 def test_inactive_wrapper_with_same_sim_id_never_reaches_fast_negative_or_repair(self):
  inactive=copy.deepcopy(self.fx.sim)
  with patch.object(boundary,'hair_policy_enabled',side_effect=AssertionError('Non-manager wrapper cannot inspect policy')),patch.object(outfit_hair,'enforce')as enforce:
   outfit_hair._event(inactive,(0,0),(0,1));enforce.assert_not_called()
 def test_existing_writer_lease_still_defers_without_read_or_mutation_then_reenables(self):
  self.stable()
  with bank._writer_lease(self.fx.path):
   with patch.object(form_bank,'load',side_effect=AssertionError('Lease must not trigger full read')),patch.object(outfit_hair,'enforce')as enforce:
    self.event();enforce.assert_not_called()
  with patch.object(outfit_hair,'enforce',return_value=False)as enforce:self.event();enforce.assert_called_once_with(self.fx.backend,self.fx.sim)
 def test_actual_switch_finalization_fulfills_hair_and_completion_callback_is_not_suppressed(self):
  f=self.fx;outfit_hair._BACKEND=f.backend;events=[];loads=form_bank.load
  def native_switch():
   f.sim.current=2;f._assign(f.sim,appearance.packed(f.backend,f.forms[2]))
   with patch.object(form_bank,'load',wraps=loads)as reads,patch.object(outfit_hair,'enforce',side_effect=AssertionError('Pending native switch cannot repair')):
    self.event();events.append(reads.call_count)
   return {'ok':True,'message':'native fixture switched'}
  result=form_bank.switch(f.backend,f.sim,2,native_switch);self.assertTrue(result['all_stored_owners_verified']);self.assertTrue(result['active_owner_verified']);self.assertTrue(result['hair_policy_synchronized']);self.assertEqual(events,[0])
  row=f.record();self.assertIsNone(row['switch_pending']);held=row['hair_policy']['forms']['2'];fields=appearance.packed(f.backend,f.sim);desired=outfit_hair.reconcile(f.backend,fields,held);self.assertEqual(appearance.fingerprint(desired),appearance.fingerprint(fields))
  before=studio._state_from_fields(f.backend,fields);journal=Obj(data={'pending':None})
  with patch.object(studio,'_context',return_value=(f.sim,before,journal,'fixture')),patch.object(outfit_hair,'enforce',wraps=outfit_hair.enforce)as enforce,patch.object(studio,'dispatch',side_effect=AssertionError('Final hair already matches; no second mutation')):
   self.event();enforce.assert_called_once_with(f.backend,f.sim)
  self.assertEqual(appearance.fingerprint(appearance.packed(f.backend,f.sim)),appearance.fingerprint(fields))
 def test_actual_native_setter_wrapper_still_runs_and_registers_repair_after_durable_completion(self):
  class Wrapper:
   def register_for_outfit_changed_callback(self,callback):self.on_outfit_changed.append(callback)
   def set_current_outfit(self,new,old):
    self.native_calls+=1
    for callback in tuple(self.on_outfit_changed):callback(self,new,old)
  owner=Wrapper();owner.__dict__.update(self.fx.sim.__dict__);owner.on_outfit_changed=[];owner.native_calls=0;self.fx.sim=owner
  outfit_hair.install(self.fx.backend,wrapper_type=Wrapper);self.fx.begin();self.stable();load=form_bank.load
  with patch.object(form_bank,'load',wraps=load)as reads,patch.object(outfit_hair,'enforce')as enforce:
   owner.set_current_outfit((0,0),(0,1));self.assertEqual(reads.call_count,0);enforce.assert_not_called();self.assertEqual(owner.native_calls,1)
  self.fx.observe();self.fx.prepare([]);self.fx.commit()
  with patch.object(outfit_hair,'enforce',return_value=False)as enforce:
   owner.set_current_outfit((0,1),(0,0));enforce.assert_called_once_with(self.fx.backend,owner)
  self.assertEqual(owner.native_calls,2);self.assertIn(outfit_hair._event,owner.on_outfit_changed)
 def test_enforce_and_permanent_idle_guard_source_is_not_changed(self):
  assert_contract(self,outfit_hair,'outfit_hair');assert_contract(self,form_bank,'form_bank');assert_contract(self,boundary,'cas_save_boundary')

if __name__=='__main__':unittest.main()
