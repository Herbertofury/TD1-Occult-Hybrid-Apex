from pathlib import Path
import importlib.util,sys,subprocess,unittest
HOME=Path(__file__).resolve().parents[1];ROOT=next(p for p in Path(__file__).resolve().parents if (p/'tools/cas_grid_transaction.py').is_file());sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests')]
import test_cas_grid_presentation as p
import cas_grid_product_rows as rows
spec=importlib.util.spec_from_file_location('progress_stage',HOME/'tools/cas_grid_progress.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
class ProgressTests(unittest.TestCase):
 def case(self,code,fixed=True):
  original_stage=p.stage
  p.stage=g if fixed else rows
  try:
   r=subprocess.run(['node','-'],input=p.NATIVE_MOCK+p.javascript()+p.BOOT+code,capture_output=True,text=True,timeout=15)
   self.assertEqual(r.returncode,0,r.stdout+r.stderr)
  finally:p.stage=original_stage
 def test_actual_previous_source_reproduces_495_selection_zero_progress_calls(self):
  self.case(SETUP+"const initial=g.ApexGridStatus();for(let i=0;i<495;i++)g.ApexGridStep(64,getTimer()+1);const after=g.ApexGridStatus();assert.equal(after.phase,'selection');assert.equal(after.index,0);assert.equal(after.counts.bind,1);assert.equal(after.counts.selection,0);assert.equal(after.operations,initial.operations);assert.equal(after.error,null);assert.equal(after.publishes,0);",False)
 def test_fixed_actual_source_advances_selection_with_same_slow_validations_and_one_atom(self):
  self.case(SETUP+"const before=g.ApexGridStatus();const after=g.ApexGridStep(64,getTimer()+1);assert.equal(after.phase,'bind');assert.equal(after.index,1);assert.equal(after.counts.selection,1);assert.equal(after.operations,before.operations+1);assert.equal(after.counts.data,before.counts.data+2);assert.equal(after.error,null);assert.equal(after.publishes,0);assert.equal(g.mGridView.mouseChildren,false);")
 def test_fixed_actual_source_converges_with_slow_validation_without_partial_publish(self):
  self.case(SETUP+"let status;for(let i=0;i<1200;i++){const before=g.ApexGridStatus().operations;status=g.ApexGridStep(64,getTimer()+1);assert.ok(status.operations-before<=1);if(status.phase==='done')break;assert.equal(status.publishes,0);}assert.equal(status.phase,'done');assert.equal(status.publishes,1);assert.equal(status.error,null);assert.equal(g.mGridView.mouseChildren,true);assert.ok(g.mCells.some(c=>c.ext.Selected));")
 def test_changed_owner_still_refuses_before_new_data_selection_or_draw(self):
  self.case(SETUP+"g.lease.active=false;const before=g.calls.length;const status=g.ApexGridStep(64,getTimer()+1);assert.equal(g.calls.length,before);assert.equal(status.phase,'cancelled');assert.equal(status.reason,'context');assert.equal(status.publishes,0);")
 def test_selection_reentry_retains_original_generation_and_revision_refusal(self):
  self.case(SETUP+"let once=true;g.hooks.selection=()=>{if(once){once=false;g.mGridData.items[0]=product('new-during-selection');g.ApexGridNativeGuard('update',{currentTarget:g.mGridData});}};const status=g.ApexGridStep(64,getTimer()+1);assert.equal(status.dirty,true);assert.equal(status.publishes,0);assert.equal(g.mGridView.mouseChildren,false);assert.equal(g.apexGridState.ready[g.ApexGridCells[0]],undefined);")
 def test_original_invalid_operation_budget_and_invariant_checks_remain(self):
  self.case(SETUP+"assert.throws(()=>g.ApexGridStep(0,getTimer()+1),/budget/);const before=g.calls.length;g.apexGridState.presentation.stageY.pop();assert.throws(()=>g.ApexGridStep(64,getTimer()+1),/arrays diverged/);assert.equal(g.calls.length,before);assert.equal(g.apexGridState.job.publishes,0);")
SETUP="""
const g=new NativeGrid(176,0);g.mGridData.selection.add(0);g.ApexGridBegin(request(g,12,{width:21.4,height:29.4,scale:.2,viewHeight:1213.7,scrollY:0}));
for(let i=0;i<1500&&g.ApexGridStatus().phase!=='selection';i++)g.ApexGridStep(1,0);
assert.equal(g.ApexGridStatus().phase,'selection');assert.equal(g.ApexGridStatus().index,0);assert.equal(g.ApexGridStatus().target,180);
const nativeValidate=g.apexGridState.validate;g.apexGridState.validate=function(owner){time+=2;return nativeValidate(owner);};
"""
if __name__=='__main__':unittest.main()
