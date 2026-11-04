from pathlib import Path
import sys,ast,subprocess,unittest
ROOT=Path(__file__).resolve().parents[1];PROJECT=next(p for p in(ROOT,*ROOT.parents)if(p/'tools/cas_grid_slice.py').is_file());sys.path[:0]=[str(ROOT/'tools'),str(PROJECT/'tools'),str(PROJECT/'tests')]
import cas_grid_budget as stage,test_cas_grid_presentation as p
SETUP="\nconst g=new NativeGrid(1000,0);\nfunction small(y){return request(g,12,{width:21.4,height:29.4,scale:.2,viewHeight:450,scrollY:y});}\ng.ApexGridBegin(small(0));assert.equal(bounded(g).phase,'done');g.ApexGridBegin(small(1));assert.equal(bounded(g).phase,'done');\nassert.equal(g.mCells.length,180);assert.equal(g.apexGridState.presentation.spareCells.length,180);\ng.ApexGridBegin(request(g,6,{width:107,height:147,scale:1,viewHeight:1213.7,scrollY:0}));\nfunction seek(phase,index){for(let i=0;i<2000;i++){const s=g.ApexGridStatus();if(s.phase===phase&&s.index===index)break;g.ApexGridStep(1,0);}const s=g.ApexGridStatus();assert.equal(s.phase,phase);assert.equal(s.index,index);assert.equal(s.target,60);assert.equal(g.ApexGridCells.length,180);}\nfunction slow(){const validate=g.apexGridState.validate;g.apexGridState.validate=o=>{time+=2;return validate(o);};}\n"

class BudgetTests(unittest.TestCase):
 def case(self,code):
  original=p.stage
  try:p.stage=stage;js=p.NATIVE_MOCK+p.javascript()+p.BOOT+'\nfunction uint(n){return n>>>0;}\n'+SETUP+'\ng.ApexGridNow=()=>int(getTimer());\n'+code
  finally:p.stage=original
  result=subprocess.run(['node','-'],input=js,capture_output=True,text=True,timeout=15);self.assertEqual(result.returncode,0,result.stdout+result.stderr)
 def test_independent_main_and_provider_origins_all_execute_only_one_tail_atom(self):
  for offset in(-1000000,-1000,0,1000,1000000):
   self.case("seek('position',114);slow();time=5000;g.apexGridState.request.stepBudgetClockContract=1;g.apexGridState.request.stepBudgetMilliseconds=1;g.ApexGridNow=()=>int(getTimer()+("+str(offset)+"));const before=g.ApexGridStatus(),start=time;const after=g.ApexGridStep(64,getTimer()+1);assert.equal(after.operations-before.operations,1);assert.equal(after.index,115);assert.equal(time-start,6);")
 def test_negative_signed_clock_and_rollover_use_modular_elapsed_duration(self):
  for now in(-2147483648,-1000,2147483646,2147483647,4294967295):
   self.case("seek('position',114);slow();time="+str(now)+";g.apexGridState.request.stepBudgetClockContract=1;g.apexGridState.request.stepBudgetMilliseconds=1;g.ApexGridNow=()=>int(getTimer());const before=g.ApexGridStatus();const after=g.ApexGridStep(64,1);assert.equal(after.operations-before.operations,1);assert.equal(after.index,115);")
 def test_missing_string_or_boolean_capability_preserves_legacy_absolute_behavior(self):
  for cap in('undefined',"'1'",'true','0','2'):
   self.case("seek('position',114);slow();time=5000;g.apexGridState.request.stepBudgetClockContract="+cap+";g.apexGridState.request.stepBudgetMilliseconds=1;g.ApexGridNow=()=>getTimer()-1000;const before=g.ApexGridStatus(),after=g.ApexGridStep(64,getTimer()+1);assert.equal(after.operations-before.operations,64);assert.equal(after.index,178);")
 def test_recognized_capability_rejects_unsupported_duration_before_any_atom(self):
  for duration in('0','2',"'1'",'true','NaN','undefined'):
   self.case("seek('position',114);g.apexGridState.request.stepBudgetClockContract=1;g.apexGridState.request.stepBudgetMilliseconds="+duration+";const before=g.ApexGridStatus();assert.throws(()=>g.ApexGridStep(64,1),/Unsupported/);assert.equal(g.ApexGridStatus().operations,before.operations);assert.equal(g.ApexGridStatus().index,114);")
 def test_invalid_max_operations_remains_invalid_under_exact_capability(self):
  self.case("seek('position',114);g.apexGridState.request.stepBudgetClockContract=1;g.apexGridState.request.stepBudgetMilliseconds=1;for(const n of [0,-1,65])assert.throws(()=>g.ApexGridStep(n,1),/budget/);")
 def test_nonfinite_provider_clock_is_refused_without_position_mutation(self):
  self.case("seek('position',114);g.apexGridState.request.stepBudgetClockContract=1;g.apexGridState.request.stepBudgetMilliseconds=1;g.ApexGridNow=()=>NaN;const before=g.ApexGridStatus();assert.throws(()=>g.ApexGridStep(64,1),/finite native integer/);assert.equal(g.ApexGridStatus().index,before.index);")
 def test_selection_reentry_keeps_revision_and_no_partial_publication(self):
  self.case("seek('selection',0);g.mGridData.selection.add(0);g.apexGridState.request.stepBudgetClockContract=1;g.apexGridState.request.stepBudgetMilliseconds=1;slow();let once=true;g.hooks.selection=()=>{if(once){once=false;g.mGridData.items[0]=product('reentered');g.ApexGridNativeGuard('update',{currentTarget:g.mGridData});}};const before=g.ApexGridStatus(),after=g.ApexGridStep(64,0);assert.equal(after.dirty,true);assert.equal(after.publishes,before.publishes);assert.equal(g.mGridView.mouseChildren,false);")
 def test_expired_capacity_transition_still_yields_after_logical_progress(self):
  self.case("seek('capacity',0);g.apexGridState.request.stepBudgetClockContract=1;g.apexGridState.request.stepBudgetMilliseconds=1;slow();const before=g.ApexGridStatus(),after=g.ApexGridStep(64,0);assert.equal(after.operations,before.operations);assert.equal(after.phase,'position');assert.equal(after.index,0);")
 def test_all_original_owner_and_invariant_guards_remain(self):
  self.case("seek('position',114);g.apexGridState.request.stepBudgetClockContract=1;g.apexGridState.request.stepBudgetMilliseconds=1;g.lease.active=false;const before=g.calls.length;const s=g.ApexGridStep(64,0);assert.equal(s.phase,'cancelled');assert.equal(s.reason,'context');assert.equal(g.calls.length,before);")
 def test_recognized_bootstrap_is_one_existing_atom_per_call_even_with_foreign_deadline(self):
  self.case("const q=new NativeGrid(2,0);q.ApexGridBegin(request(q,6,{bootstrap:true,stepBudgetClockContract:1,stepBudgetMilliseconds:1}));let s=q.ApexGridStep(64,-2147483648);assert.equal(s.operations,1);assert.equal(s.pendingCell,false);s=q.ApexGridStep(64,2147483647);assert.equal(s.operations,2);assert.equal(s.phase,'measured');assert.equal(s.counts.construct,1);")
 def test_bootstrap_invalid_budgets_remain_invalid_and_legacy_deadline_is_unchanged(self):
  self.case("const q=new NativeGrid(2,0);q.ApexGridBegin(request(q,6,{bootstrap:true,stepBudgetClockContract:1,stepBudgetMilliseconds:1}));for(const n of[0,65])assert.throws(()=>q.ApexGridStep(n,1),/bootstrap budget/);delete q.apexGridState.request.stepBudgetClockContract;time=5000;assert.equal(q.ApexGridStep(64,1).operations,0);")
if __name__=='__main__':unittest.main()
