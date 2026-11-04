"""Execute the actual provider helpers; no game/profile/native process access."""
from pathlib import Path
from types import SimpleNamespace
import subprocess,sys,unittest
HERE=Path(__file__).resolve().parents[1]
ROOT=next(p for p in (HERE,*HERE.parents)if(p/'tools/dbpf_build.py').is_file())
sys.path[:0]=[str(HERE/'tools'),str(ROOT/'tools'),str(ROOT/'tests')]
import cas_grid_spares_stage as stage
import test_cas_grid_presentation as fixture
import test_cas_grid_row_delta as delta

def javascript(old=False):
 previous=fixture.stage
 try:fixture.stage=SimpleNamespace(helpers=stage.previous.helpers if old else stage.helpers);return fixture.javascript()
 finally:fixture.stage=previous

BOOT=delta.BOOT.replace("function getQualifiedClassName(value){return Object.getPrototypeOf(value)===Selectability.prototype?'olympus.extensions::Selectability':'custom-extension';}",
"function getQualifiedClassName(value){return typeof value==='function'?(value.qname||value.name):(Object.getPrototypeOf(value)===Selectability.prototype?'olympus.extensions::Selectability':value.constructor.qname||value.constructor.name);}")

class SpareTests(unittest.TestCase):
 def case(self,code,old=False):
  raw=fixture.NATIVE_MOCK.replace('const getTimer=()=>time;','const getTimer=()=>Math.trunc(time);')
  raw=raw.replace('this.item=null;this.mcHitArea=','Object.setPrototypeOf(this.ext,Selectability.prototype);this.item=null;this.mcHitArea=')
  result=subprocess.run(['node','-'],input=raw+javascript(old)+fixture.BOOT+BOOT+code,text=True,capture_output=True,timeout=25)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)

 def test_old_exact_source_reproduces_unknown_initial_bank_spare_failure(self):
  self.case('''const g=ready(new NativeGrid(1000,0));const bad=new Cell(g);bad.visible=false;g.mGridView.addChild(bad);delete g.apexGridState.intrinsics[bad];
g.apexGridState.presentation.spareCells.push(bad);g.ApexGridBegin(deltaRequest(g,55));let failed=false;
for(let i=0;i<1000&&!failed;i++){g.ApexGridStep(1,0);failed=String(g.ApexGridStatus().error).includes('Delta spare ownership/class changed');}
assert.equal(failed,true);''',old=True)

 def test_unregistered_spare_does_not_blank_old_bank_or_block_entering_rows(self):
  self.case('''const g=ready(new NativeGrid(1000,0)),old=snapshot(g),before=counters(g);const bad=new Cell(g);bad.visible=false;g.mGridView.addChild(bad);
delete g.apexGridState.intrinsics[bad];g.apexGridState.presentation.spareCells.push(bad);const parent=bad.parent;
g.ApexGridBegin(deltaRequest(g,55));assert.equal(steps(g).phase,'done');assert.equal(counters(g).draw-before.draw,6);
assert.equal(g.apexGridState.job.deltaPublishes,1);assert.equal(g.mGridView.visible,true);assert.equal(bad.parent,parent);assert.equal(bad.visible,false);
assert.equal(g.apexGridState.presentation.spareCells.includes(bad),false);assert.equal(g.apexGridState.deferredSpare.some(r=>r.cell===bad),false);
assert.deepEqual(g.mCells.slice(0,48),old.cells.slice(6));assert.match(g.ApexGridStatus().row_delta_last_refusal,/unregistered/);''')

 def test_mixed_bad_stock_is_never_adopted_hidden_redrawn_or_queued_for_retirement(self):
  self.case('''const g=ready(new NativeGrid(1000,0)),before=counters(g);const p=g.apexGridState.presentation;
const foreign=new Cell(g),visible=new Cell(g),unknown=new Cell(g);g.ApexGridCaptureNewCell(foreign);g.ApexGridCaptureNewCell(visible);
const external=new DisplayObject();external.addChild(foreign);foreign.visible=false;g.mGridView.addChild(visible);visible.visible=true;g.mGridView.addChild(unknown);unknown.visible=false;
p.spareCells.push(null,foreign,visible,unknown,g.mCells[0]);const fields=[foreign,visible,unknown].map(c=>({c,parent:c.parent,visible:c.visible,item:c.item}));
g.ApexGridBegin(deltaRequest(g,55));assert.equal(steps(g).phase,'done');assert.equal(counters(g).draw-before.draw,6);
for(const r of fields){assert.equal(r.c.parent,r.parent);assert.equal(r.c.visible,r.visible);assert.equal(r.c.item,r.item);}
assert.ok(g.apexGridState.presentation.spareCells.every(c=>!g.mCells.includes(c)));assert.equal(g.apexGridState.deferredSpare.length,0);''')

 def test_valid_spare_is_used_once_even_with_duplicate_and_committed_aliases(self):
  self.case('''const g=ready(new NativeGrid(1000,0));g.ApexGridBegin(deltaRequest(g,55));steps(g);const p=g.apexGridState.presentation;
const valid=p.spareCells[0];p.spareCells.push(valid,g.mCells[0]);const before=counters(g);
g.ApexGridBegin(deltaRequest(g,0));assert.equal(steps(g).phase,'done');assert.equal(counters(g).draw-before.draw,6);
assert.equal(new Set(g.mCells).size,g.mCells.length);assert.ok(p.spareCells.every(c=>!g.mCells.includes(c)));assert.equal(new Set(p.spareCells).size,p.spareCells.length);''')

 def test_same_qname_foreign_domain_class_is_not_registered_or_retired(self):
  self.case('''const g=ready(new NativeGrid(1000,0));Cell.qname='same::Native';class DomainOther extends DisplayObject{static qname=Cell.qname;}
const bad=new DomainOther();bad.visible=false;g.mGridView.addChild(bad);g.apexGridState.intrinsics[bad]={type:Cell,width:40,height:50,aspect:1};
g.apexGridState.presentation.spareCells.push(bad);g.ApexGridBegin(deltaRequest(g,55));assert.equal(steps(g).phase,'done');
assert.equal(bad.parent,g.mGridView);assert.equal(bad.visible,false);assert.equal(g.apexGridState.deferredSpare.length,0);''')

 def test_hidden_registered_old_class_is_deferred_then_native_full_replan_retires_once(self):
  self.case('''const g=ready(new NativeGrid(1000,0));class OldCell extends Cell{}const bad=new OldCell(g);bad.visible=false;g.mGridView.addChild(bad);
g.apexGridState.intrinsics[bad]={type:OldCell,width:40,height:50,aspect:1};g.apexGridState.presentation.spareCells.push(bad);
g.ApexGridBegin(deltaRequest(g,55));assert.equal(steps(g).phase,'done');assert.equal(g.apexGridState.deferredSpare.length,1);
g.ApexGridBegin(deltaRequest(g,55,{width:41}));assert.equal(steps(g).phase,'done');assert.equal(g.apexGridState.deferredSpare.length,0);
assert.equal(bad.parent,null);assert.equal(g.apexGridState.intrinsics[bad],undefined);''')

 def test_deferred_cell_becoming_foreign_or_visible_is_not_retired(self):
  for mode in ('foreign','visible','committed'):
   self.case('''const g=ready(new NativeGrid(1000,0));class OldCell extends Cell{}const bad=new OldCell(g);bad.visible=false;g.mGridView.addChild(bad);
g.apexGridState.intrinsics[bad]={type:OldCell,width:40,height:50,aspect:1};g.apexGridState.presentation.spareCells.push(bad);
g.ApexGridBegin(deltaRequest(g,55));steps(g);const external=new DisplayObject();'''+
    ("g.mGridView.removeChild(bad);external.addChild(bad);"if mode=='foreign'else"bad.visible=true;"if mode=='visible'else"g.apexGridState.presentation.committedCells.push(bad);g.mCellsY.push(0);g.mCellIndexToDataIndexMap.push(0);")+'''
const parent=bad.parent,visibility=bad.visible;g.ApexGridBegin(deltaRequest(g,55,{width:41}));steps(g);
assert.equal(bad.parent,parent);assert.equal(bad.visible,visibility);assert.ok(g.apexGridState.intrinsics[bad]);''')

 def test_guarded_detach_preserves_callback_new_ready_and_pool_values(self):
  self.case('''const g=ready(new NativeGrid(1000,0));const spare=new Cell(g);spare.visible=false;g.mGridView.addChild(spare);g.ApexGridCaptureNewCell(spare);
const s=g.apexGridState,record=s.intrinsics[spare];s.spareCustody[spare]={view:g.mGridView,intrinsic:record};
const remove=g.mGridView.removeChild;g.mGridView.removeChild=function(c){remove.call(this,c);s.ready[c]=999;s.poolFlags[c]={owner:'new'};};
g.ApexGridDetach(spare);assert.equal(s.ready[spare],999);assert.equal(s.poolFlags[spare].owner,'new');assert.equal(s.intrinsics[spare],record);
assert.equal(s.spareCustody[spare].abandoned,true);g.ApexGridDetach(spare);assert.equal(s.ready[spare],999);assert.equal(s.intrinsics[spare],record);''')

 def test_retarget_after_rejected_candidates_cleans_only_verified_used_stock(self):
  self.case('''const g=ready(new NativeGrid(1000,0));g.ApexGridBegin(deltaRequest(g,55));steps(g);const p=g.apexGridState.presentation;
const foreign=new Cell(g),external=new DisplayObject();external.addChild(foreign);foreign.visible=true;p.spareCells.unshift(foreign);
g.delayImages=true;g.ApexGridBegin(deltaRequest(g,0));for(let i=0;i<1000&&g.apexGridState.delta.phase!=='selection';i++)g.ApexGridStep(1,0);
g.ApexGridNativeGuard('scroll',{mRect:{y:-110}});for(let i=0;i<1000&&g.apexGridState.delta&&g.apexGridState.delta.cleaning;i++)g.ApexGridStep(1,0);
assert.equal(foreign.parent,external);assert.equal(foreign.visible,true);g.ApexGridCancel('dispose');assert.equal(foreign.parent,external);assert.equal(foreign.visible,true);''')

 def test_stock_changed_after_start_before_retire_or_rollback_is_not_touched(self):
  for mode in ('foreign','visible','committed','new-ready'):
   self.case('''const g=ready(new NativeGrid(1000,0));class OldCell extends Cell{}const bad=new OldCell(g);bad.visible=false;g.mGridView.addChild(bad);
g.apexGridState.intrinsics[bad]={type:OldCell,width:40,height:50,aspect:1};g.apexGridState.presentation.spareCells.push(bad);
g.ApexGridBegin(deltaRequest(g,55,{width:41}));for(let i=0;i<1000&&(!g.apexGridState.presentation.working||!g.apexGridState.spareCustody[bad]);i++)g.ApexGridStep(1,0);
assert.ok(g.apexGridState.spareCustody[bad]);const external=new DisplayObject();'''+
    ("g.mGridView.removeChild(bad);external.addChild(bad);"if mode=='foreign'else"bad.visible=true;"if mode=='visible'else"g.apexGridState.presentation.committedCells.push(bad);g.mCellsY.push(0);g.mCellIndexToDataIndexMap.push(0);"if mode=='committed'else"g.apexGridState.ready[bad]=999;")+'''
const parent=bad.parent,visible=bad.visible,intrinsic=g.apexGridState.intrinsics[bad];
g.ApexGridDetach(bad);g.ApexGridPresentationRollback();
assert.equal(bad.parent,parent);assert.equal(bad.visible,visible);assert.equal(g.apexGridState.intrinsics[bad],intrinsic);''')

 def test_detach_callback_adoption_and_replaced_dictionary_identity_preserve_new_metadata(self):
  for mutation in ("s.ready={};s.ready[c]=999;", "s.poolFlags={};s.poolFlags[c]={newOwner:true};", "external.addChild(c);", "s.presentation.committedCells.push(c);s.ready[c]=999;"):
   self.case('''const g=ready(new NativeGrid(1000,0));const bad=new Cell(g);bad.visible=false;g.mGridView.addChild(bad);g.ApexGridCaptureNewCell(bad);
const s=g.apexGridState,record=s.intrinsics[bad],external=new DisplayObject();s.spareCustody[bad]={view:g.mGridView,intrinsic:record};
const remove=g.mGridView.removeChild;g.mGridView.removeChild=function(c){remove.call(this,c);'''+mutation+'''};
g.ApexGridDetach(bad);assert.equal(s.intrinsics[bad],record);assert.equal(s.spareCustody[bad].abandoned,true);
g.ApexGridDetach(bad);assert.equal(s.intrinsics[bad],record);''')

 def test_unknown_old_initial_bank_is_filtered_at_first_publication_not_repeated_each_wheel(self):
  self.case('''const g=new NativeGrid(1000,12);const initial=g.mCells.slice();g.ApexGridBegin(deltaRequest(g));assert.equal(steps(g).phase,'done');
assert.ok(initial.every(c=>c.parent===g.mGridView&&!c.visible));assert.ok(g.apexGridState.presentation.spareCells.every(c=>!initial.includes(c)));
const rejected=g.ApexGridStatus().spare_diagnostic.rejected;
for(let n=1;n<=8;n++){g.ApexGridBegin(deltaRequest(g,n*55));assert.equal(steps(g).phase,'done');}
assert.equal(g.ApexGridStatus().spare_diagnostic.rejected,rejected);assert.equal(g.apexGridState.deferredSpare.length,0);''')

 def test_repeated_full_replans_bound_children_to_native_initial_plus_two_owned_banks(self):
  self.case('''const g=new NativeGrid(1000,12);const initial=g.mCells.slice();g.ApexGridBegin(deltaRequest(g));steps(g);
const bound=initial.length+2*g.mCells.length;
for(let n=0;n<30;n++){g.ApexGridBegin(deltaRequest(g,(n%6)*55,{width:n%2?40:41}));assert.equal(steps(g).phase,'done');
assert.ok(g.mGridView.children.length<=bound);assert.equal(g.apexGridState.deferredSpare.length,0);}
assert.ok(initial.every(c=>c.parent===g.mGridView&&!c.visible));''')

 def test_abandoned_stock_custody_survives_cancel_and_same_view_new_owner_state(self):
  self.case('''const g=ready(new NativeGrid(1000,0)),bad=new Cell(g);bad.visible=false;g.mGridView.addChild(bad);g.ApexGridCaptureNewCell(bad);
const s=g.apexGridState,record=s.intrinsics[bad];s.spareCustody[bad]={view:g.mGridView,intrinsic:record,abandoned:true};
s.presentation.spareCells.push(bad);const next=deltaRequest(g,0);g.ApexGridCancel('dispose');next.owner.generation++;next.owner.active=true;
g.ApexGridBegin(next);assert.equal(steps(g).phase,'done');assert.equal(g.apexGridState.spareCustody[bad].abandoned,true);
assert.equal(bad.parent,g.mGridView);assert.equal(g.apexGridState.presentation.spareCells.includes(bad),false);''')

class ExistingDeltaRegression(delta.DeltaTests):
 def case(self,code):SpareTests.case(self,code)

if __name__=='__main__':unittest.main()
