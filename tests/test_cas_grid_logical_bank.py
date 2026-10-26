"""Execute the exact current provider and narrowly staged full-publication seam."""
from pathlib import Path
from types import SimpleNamespace
import subprocess,sys,unittest
H=Path(__file__).resolve().parents[1];R=next(p for p in(H,*H.parents)if(p/'tools/dbpf_build.py').is_file())
sys.path[:0]=[str(H/'tools'),str(R/'tools'),str(R/'tests')]
import cas_grid_logical_bank_stage as stage
import test_cas_grid_presentation as fixture,test_cas_grid_spares as spares


def javascript(original=False):
 old=fixture.stage
 try:fixture.stage=SimpleNamespace(helpers=stage.previous.stage.helpers if original else stage.helpers);return fixture.javascript()
 finally:fixture.stage=old

BOOT='''
function largeThenSmall(g){
 g.ApexGridBegin(deltaRequest(g,0,{columns:12,viewHeight:1009.7}));assert.equal(bounded(g).phase,'done');assert.equal(g.mCells.length,240);
 g.ApexGridBegin(deltaRequest(g,0,{viewHeight:350}));assert.equal(bounded(g).phase,'done');assert.equal(g.ApexGridStatus().target,48);
 g.ApexGridBegin(deltaRequest(g,1100,{viewHeight:350}));assert.equal(bounded(g).phase,'done');return g;
}
function appendParked(g,n=5){
 const s=g.apexGridState,j=s.job;for(let i=0;i<n;i++){
  const cell=g.CreateCell();g.mGridView.addChild(cell);const slot=g.mCells.length;g.mCells.push(cell);g.mCellsY.push(0);g.mCellIndexToDataIndexMap.push(-1);g.ApexGridPoolPark(cell,slot);
 }
 j.phase='publish';g.ApexGridAcquire(j);j.lease=true;return g.mCells.slice(j.target);
}
function bankRefs(g){const p=g.apexGridState.presentation;return [g.mCells,g.mCellsY,g.mCellIndexToDataIndexMap,p.committedCells,p.committedY,p.committedMap,p.spareCells,p.spareY,p.spareMap];}
function refsSame(g,held){const got=bankRefs(g);for(let i=0;i<held.length;i++)assert.equal(got[i],held[i]);}
'''

class LogicalBankTests(unittest.TestCase):
 def case(self,body,original=False):
  native=fixture.NATIVE_MOCK.replace('const getTimer=()=>time;','const getTimer=()=>Math.trunc(time);').replace('this.item=null;this.mcHitArea=','Object.setPrototypeOf(this.ext,Selectability.prototype);this.item=null;this.mcHitArea=')
  result=subprocess.run(['node','-'],input=native+javascript(original)+fixture.BOOT+spares.BOOT+BOOT+body,text=True,capture_output=True,timeout=25)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)

 def test_original_exact_provider_reproduces_oversized_bank_and_full_window_row_redraw(self):
  self.case("const g=largeThenSmall(new NativeGrid(1000,0));assert.equal(g.mCells.length,240);const before=counters(g);g.ApexGridBegin(deltaRequest(g,1045,{viewHeight:350}));assert.notEqual(g.ApexGridStatus().phase,'row-delta');steps(g);assert.equal(counters(g).draw-before.draw,48);",True)

 def test_240_stock_to_48_window_preserves_hidden_stock_and_binds_only_six_entering(self):
  self.case("const g=largeThenSmall(new NativeGrid(1000,0));assert.equal(g.mCells.length,48);assert.equal(g.apexGridState.presentation.spareCells.length,240);const old=snapshot(g),before=counters(g),at=g.calls.length;g.ApexGridBegin(deltaRequest(g,1045,{viewHeight:350}));assert.equal(g.ApexGridStatus().phase,'row-delta');assert.equal(steps(g).phase,'done');assert.equal(counters(g).draw-before.draw,6);assert.equal(counters(g).bind-before.bind,6);assert.equal(counters(g).selection-before.selection,6);assert.equal(g.calls.slice(at).filter(x=>x==='construct'||x==='attach'||x==='detach').length,0);assert.deepEqual(g.mCells.slice(6),old.cells.slice(0,42));assert.equal(new Set(g.mCells).size,48);")

 def test_53_physical_cells_normalize_to_48_without_any_widget_or_ready_mutation(self):
  self.case("const g=new NativeGrid(1000,0);g.ApexGridBegin(deltaRequest(g,0,{viewHeight:350}));bounded(g);const tail=appendParked(g),heldReady=g.apexGridState.ready,old=g.mCells.slice(),before=g.calls.length;assert.equal(g.mCells.length,53);assert.equal(g.ApexGridCommitLogicalBank(g.apexGridState.job),true);assert.equal(g.calls.length,before);assert.equal(g.mCells.length,48);assert.deepEqual(g.mCells,old.slice(0,48));assert.equal(g.apexGridState.ready,heldReady);assert.ok(tail.every(c=>c.parent===g.mGridView&&!c.visible&&g.apexGridState.presentation.spareCells.includes(c)));")

 def test_unknown_or_unready_tail_is_never_normalized_or_touched(self):
  for change in("tail[0].visible=true;","delete g.apexGridState.intrinsics[tail[0]];","g.apexGridState.ready[tail[0]]=999;","g.mCellIndexToDataIndexMap[48]=0;","delete g.apexGridState.poolFlags[tail[0]];","g.mCells[49]=g.mCells[48];"):
   self.case("const g=new NativeGrid(1000,0);g.ApexGridBegin(deltaRequest(g,0,{viewHeight:350}));bounded(g);const tail=appendParked(g);"+change+"const held=bankRefs(g),before=g.calls.length,vis=tail.map(c=>c.visible);assert.equal(g.ApexGridCommitLogicalBank(g.apexGridState.job),false);refsSame(g,held);assert.equal(g.calls.length,before);assert.deepEqual(tail.map(c=>c.visible),vis);")

 def test_foreign_tail_parent_same_qname_and_ready_generation_never_gains_stock_custody(self):
  for change in("const external=new DisplayObject();external.addChild(tail[0]);","class OtherDomain extends Cell{}OtherDomain.qname=Cell.qname='same::Native';Object.setPrototypeOf(tail[0],OtherDomain.prototype);","g.apexGridState.intrinsics[tail[0]]={type:OtherCell,width:1,height:1};"):
   self.case("const g=new NativeGrid(1000,0);g.ApexGridBegin(deltaRequest(g,0,{viewHeight:350}));bounded(g);const tail=appendParked(g);"+change+"const parent=tail[0].parent,held=bankRefs(g),before=g.calls.length;assert.equal(g.ApexGridCommitLogicalBank(g.apexGridState.job),false);refsSame(g,held);assert.equal(tail[0].parent,parent);assert.equal(g.calls.length,before);")

 def test_frame_lease_owner_feed_and_binding_reentry_refuse_without_adopting_replacement(self):
  for change in("g.lease.generation++;","s.ownerGeneration++;g.lease.generation++;","s.ready={};","s.presentation.committedBindings={};","s.feed=new SelectableArrayDataFeed(1000);g.mGridData=s.feed;","s.externalSuppression=true;"):
   self.case("const g=new NativeGrid(1000,0);g.ApexGridBegin(deltaRequest(g,0,{viewHeight:350}));bounded(g);const tail=appendParked(g),s=g.apexGridState,held=bankRefs(g),before=g.calls.length;const original=s.validate;s.validate=o=>{"+change+"return true;};assert.equal(g.ApexGridCommitLogicalBank(s.job),false);refsSame(g,held);assert.equal(g.calls.length,before);")

 def test_full_publication_cancel_and_same_view_replan_keep_old_ready_bank(self):
  self.case("const g=largeThenSmall(new NativeGrid(1000,0)),old=snapshot(g);g.delayImages=true;g.ApexGridBegin(deltaRequest(g,0,{viewHeight:350}));for(let i=0;i<5000&&g.ApexGridStatus().phase!=='textures';i++)g.ApexGridStep(1,0);same(g,old);g.ApexGridCancel('context');same(g,old);g.delayImages=false;g.lease.generation++;g.ApexGridBegin(deltaRequest(g,0,{viewHeight:350}));assert.equal(steps(g).phase,'done');assert.equal(g.mCells.length,48);assert.ok(g.apexGridState.presentation.spareCells.every(c=>!g.mCells.includes(c)&&!c.visible));")

 def test_ready_texture_or_logical_physical_ledger_changes_do_not_enable_normalization(self):
  for change in("g.mCells[0].mcImage.resourceId='changed';","g.apexGridState.presentation.committedBindings[g.mCells[0]].generation--;","g.mCellsY[0]+=1;","g.mCells[0].y+=1;"):
   self.case("const g=new NativeGrid(1000,0);g.ApexGridBegin(deltaRequest(g,0,{viewHeight:350}));bounded(g);appendParked(g);"+change+"const held=bankRefs(g),before=g.calls.length;assert.equal(g.ApexGridCommitLogicalBank(g.apexGridState.job),false);refsSame(g,held);assert.equal(g.calls.length,before);")

 def test_no_full_publication_phase_or_unknown_capability_never_normalizes(self):
  for change in("g.apexGridState.job.phase='done';","g.apexGridState.request.rowDeltaReuseContract=0;","g.apexGridState.request.rowDeltaFeedbackContract='unknown';","g.apexGridState.owner.panel_kind='featured';"):
   self.case("const g=new NativeGrid(1000,0);g.ApexGridBegin(deltaRequest(g,0,{viewHeight:350}));bounded(g);appendParked(g);"+change+"const held=bankRefs(g),before=g.calls.length;assert.equal(g.ApexGridCommitLogicalBank(g.apexGridState.job),false);refsSame(g,held);assert.equal(g.calls.length,before);")

 def test_repeated_large_small_replans_keep_all_stock_bounded_and_scope_isolated(self):
  self.case("const g=largeThenSmall(new NativeGrid(1000,0));const max=g.mGridView.children.length;for(let n=0;n<20;n++){const wide=n%2;g.ApexGridBegin(deltaRequest(g,0,wide?{columns:12,viewHeight:1009.7}:{columns:6,viewHeight:350}));assert.equal(bounded(g).phase,'done');assert.equal(g.mCells.length,wide?240:48);assert.ok(g.mGridView.children.length<=max);assert.equal(new Set(g.mCells).size,g.mCells.length);assert.ok(g.apexGridState.presentation.spareCells.every(c=>!g.mCells.includes(c)&&!c.visible));}")

if __name__=='__main__':unittest.main()
