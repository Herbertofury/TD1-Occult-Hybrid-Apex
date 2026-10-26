from pathlib import Path
from types import SimpleNamespace
import sys,subprocess,unittest
R=Path(__file__).resolve().parents[1];sys.path[:0]=[str(R/'tools'),str(R/'tests')]
import cas_grid_physical as stage
import test_cas_grid_presentation as f
import test_cas_grid_row_delta as fixture

def javascript(module):
 old=f.stage
 try:f.stage=module;return f.javascript()
 finally:f.stage=old

QUANT='''
// Models native display-property storage separately from EA's ideal layout
// vectors. Current actual V348 root positions (-108,4.4,116.8,229.2) agree
// with this test corpus; no runtime quantizer assumption enters the fix.
Object.defineProperty(DisplayObject.prototype,'y',{get(){return this._nativeY==null?0:this._nativeY;},set(v){this._nativeY=Math.floor(v*20)/20;}});
const actualPitch=112.4105667535669,actualRaw=1007.269043122038,actualUp=895.2845340285345;
function realRequest(g,raw){return deltaRequest(g,raw,{width:78.91,height:actualPitch-4,scale:.73748684866372,viewHeight:1016.700012207031});}
function realReady(raw=actualRaw){const g=new NativeGrid(436,0);g.ApexGridBegin(realRequest(g,raw));assert.equal(steps(g).phase,'done');return g;}
function settleDelta(g,n=2000){for(let i=0;i<n&&g.apexGridState.delta;i++)g.ApexGridStep(1,0);return g.ApexGridStatus();}
'''

class PhysicalTests(unittest.TestCase):
 def case(self,body,old=False):
  raw=f.NATIVE_MOCK.replace('const getTimer=()=>time;','const getTimer=()=>Math.trunc(time);').replace('this.item=null;this.mcHitArea=', 'Object.setPrototypeOf(this.ext,Selectability.prototype);this.item=null;this.mcHitArea=')
  text=raw+javascript(stage.previous if old else stage)+f.BOOT+fixture.BOOT+QUANT+body
  p=subprocess.run(['node','-'],input=text,capture_output=True,text=True,timeout=20);self.assertEqual(p.returncode,0,p.stdout+p.stderr)
 def test_exact_old_source_reproduces_six_draws_then_full_fallback_for_actual_fractional_geometry(self):
  self.case('''const g=realReady();const before=counters(g);assert.equal(g.mCells.length,66);assert.equal(g.mCells[0].y,-108);assert.notEqual(g.mCells[0].y,g.mCellsY[0]);g.ApexGridBegin(realRequest(g,actualUp));assert.equal(g.apexGridState.job.phase,'row-delta');settleDelta(g);assert.equal(counters(g).draw-before.draw,6);assert.equal(g.apexGridState.job.phase,'acquire');assert.equal(steps(g).phase,'done');assert.equal(counters(g).draw-before.draw,72);''',old=True)
 def test_native_physical_ledger_allows_only_six_entering_rows_without_an_epsilon(self):
  self.case('''const g=realReady(),old=snapshot(g),before=counters(g);g.ApexGridBegin(realRequest(g,actualUp));assert.equal(steps(g).phase,'done');assert.equal(counters(g).draw-before.draw,6);assert.equal(g.apexGridState.job.deltaPublishes,1);assert.deepEqual(g.mCells.slice(6),old.cells.slice(0,60));for(const cell of g.mCells){const binding=g.apexGridState.presentation.committedBindings[cell];assert.equal(binding.physicalY,cell.y);assert.equal(binding.logicalY,g.mCellsY[g.mCells.indexOf(cell)]);}''')
 def test_changed_committed_native_position_is_rejected_exactly_and_exposes_scalar_reason(self):
  self.case('''const g=realReady();g.mCells[0].y+=.5;const old=snapshot(g);g.ApexGridBegin(realRequest(g,actualUp));settleDelta(g);same(g,old);assert.equal(g.apexGridState.job.phase,'acquire');const state=g.ApexGridStatus();assert.equal(state.row_delta_last_refusal,'borrow-physical-y');assert.equal(state.row_delta_refusal.index,6);assert.notEqual(state.row_delta_refusal.expected,state.row_delta_refusal.actual);assert.equal(typeof state.row_delta_refusal.expected,'number');''')
 def test_resize_observer_displacement_is_refused_against_exact_postwrite_native_readback(self):
  self.case('''const g=realReady(),old=snapshot(g);let calls=0;g.hooks.resize=()=>{calls++;g.mCells[6].y+=.5;};g.ApexGridBegin(realRequest(g,actualUp));settleDelta(g);same(g,old);assert.equal(calls,1);assert.equal(g.ApexGridStatus().row_delta_last_refusal,'post-resize-physical-y');assert.equal(g.apexGridState.job.phase,'acquire');''')
 def test_logical_vector_corruption_is_not_adopted_as_a_new_physical_position(self):
  self.case('''const g=realReady();g.mCellsY[0]+=.001;const old=snapshot(g);g.ApexGridBegin(realRequest(g,actualUp));settleDelta(g);same(g,old);assert.equal(g.apexGridState.job.phase,'acquire');assert.equal(g.ApexGridStatus().row_delta_last_refusal,'borrow-physical-y');''')
 def test_owner_or_resource_change_in_feedback_still_restores_exact_prior_native_positions(self):
  for mutation in ("g.lease.active=false;","g.mCells[6].mcImage.resourceId='foreign';"):
   self.case('''const g=realReady(),old=snapshot(g);g.hooks.resize=()=>{'''+mutation+'''};g.ApexGridBegin(realRequest(g,actualUp));settleDelta(g);same(g,old);assert.equal(g.apexGridState.delta,null);''')
 def test_subrow_quantized_native_positions_keep_exact_ledger_then_cross_row_without_full_rebuild(self):
  self.case('''const g=realReady(),before=counters(g);const r=realRequest(g,actualRaw+1);r.scrollOnlyPositionContract=1;g.ApexGridBegin(r);assert.equal(g.ApexGridStatus().phase,'scroll-only');assert.equal(steps(g).phase,'done');assert.equal(counters(g).draw,before.draw);assert.equal(g.ApexGridStatus().scroll_only_commits,1);for(const cell of g.mCells){const record=g.apexGridState.presentation.committedBindings[cell];assert.equal(record.physicalY,cell.y);assert.equal(record.logicalY,g.mCellsY[g.mCells.indexOf(cell)]);}g.ApexGridBegin(realRequest(g,actualUp));assert.equal(steps(g).phase,'done');assert.equal(counters(g).draw-before.draw,6);''')
 def test_subrow_observer_displacement_rolls_back_exact_physical_and_logical_positions(self):
  self.case('''const g=realReady(),old=snapshot(g),logical=g.mCellsY.slice(),publishes=g.ApexGridStatus().publishes;g.hooks.resize=()=>{g.mCells[4].y+=.5;};const r=realRequest(g,actualRaw+1);r.scrollOnlyPositionContract=1;g.ApexGridBegin(r);for(let n=0;n<2000&&g.ApexGridStatus().phase==='scroll-only';n++)g.ApexGridStep(1,0);same(g,old);assert.deepEqual(g.mCellsY,logical);assert.equal(g.ApexGridStatus().row_delta_last_refusal,'scroll-post-resize-physical-y');assert.ok(['acquire','configure'].includes(g.ApexGridStatus().phase));assert.equal(g.ApexGridStatus().publishes,publishes);''')
 def test_fractional_native_feedback_echo_uses_existing_subrow_transaction_after_ready_row_commit(self):
  self.case('''const g=realReady(),before=counters(g);let callbacks=0;g.hooks.resize=()=>{if(callbacks++===0)g.ApexGridNativeGuard('scroll',{mRect:{y:-895.3}});};const r=realRequest(g,actualUp);r.scrollOnlyPositionContract=1;g.ApexGridBegin(r);assert.equal(steps(g).phase,'done');assert.equal(counters(g).draw-before.draw,6);assert.equal(g.apexGridState.job.deltaPublishes,1);assert.equal(g.ApexGridStatus().scroll_only_commits,1);assert.equal(g.apexGridState.job.plan.scrollY,895.3);assert.equal(callbacks,2);for(const cell of g.mCells)assert.equal(g.apexGridState.presentation.committedBindings[cell].physicalY,cell.y);''')

if __name__=='__main__':unittest.main()
