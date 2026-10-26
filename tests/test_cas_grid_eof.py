from pathlib import Path
from types import SimpleNamespace
import subprocess,sys,unittest,os
H=Path(__file__).resolve().parents[1];R=next(p for p in(H,*H.parents)if(p/'tools/dbpf_build.py').is_file())
FRAME=Path(os.environ.get('APEX_FRAME_STATUS_SOURCE_ROOT',R));LOGICAL=Path(os.environ.get('APEX_LOGICAL_BANK_SOURCE_ROOT',R))
sys.path[:0]=[str(H/'tools'),str(FRAME/'tools'),str(LOGICAL/'tools'),str(R/'tools'),str(R/'tests')]
import cas_grid_eof_stage as stage,test_cas_grid_presentation as fixture,test_cas_grid_spares as spares

def javascript(original=False):
 old=fixture.stage
 try:
  source=stage.previous.helpers()if original else stage.helpers()
  fixture.stage=SimpleNamespace(helpers=lambda:source.replace('public final function','public function'))
  return fixture.javascript()
 finally:fixture.stage=old

BOOT="""
NativeGrid.prototype.apexGridAuthority=null;
const rawDeltaRequest=deltaRequest;
deltaRequest=function(g,scrollY=0,extra={}){
 const defaults={sim_id:'1',household_id:'2',owner:'active/2',session:1,layer:0,native_kind:2,shell_kind:4,native_mask:127,native_generation:'42',outfit_type:9,outfit_index:0,state:7,phase:'bound'};
 for(const[k,v]of Object.entries(defaults))if(g.lease[k]===undefined)g.lease[k]=v;
 Object.assign(g.lease,{root:g,panel:g.panel,grid:g,view:g.mGridView,feed:g.mGridData});
 return rawDeltaRequest(g,scrollY,extra);
};
const geometry={columns:12,height:51.4446328,gapY:4,viewHeight:999.7,scale:.3499634885};
function eofGrid(){const g=new NativeGrid(260,0);g.ApexGridBegin(deltaRequest(g,0,geometry));assert.equal(bounded(g).phase,'done');assert.equal(g.mCells.length,240);return g;}
function padding(g){return g.mCellIndexToDataIndexMap.filter(i=>i<0).length;}
function emptyCorrect(g){const s=g.apexGridState;for(let i=0;i<g.mCells.length;i++)if(g.mCellIndexToDataIndexMap[i]<0){const c=g.mCells[i];assert.equal(c.visible,false);assert.equal(c.mouseEnabled,false);assert.equal(c.mouseChildren,false);assert.equal(c.ext.Selected,false);assert.equal(s.ready[c],-1);assert.ok(s.poolFlags[c]);assert.equal(s.presentation.committedExpected[c],undefined);}}
"""
class EofTests(unittest.TestCase):
 def case(self,body,original=False):
  native=fixture.NATIVE_MOCK.replace('const getTimer=()=>time;','const getTimer=()=>Math.trunc(time);').replace('this.item=null;this.mcHitArea=','Object.setPrototypeOf(this.ext,Selectability.prototype);this.item=null;this.mcHitArea=')
  code=native+javascript(original)+fixture.BOOT+spares.BOOT+BOOT+body
  r=subprocess.run(['node','-'],input=code,text=True,capture_output=True,timeout=30)
  if r.returncode:(H/'failed-probe.js').write_text(code,encoding='utf-8');(H/'failed-probe.log').write_text(r.stdout+r.stderr,encoding='utf-8')
  self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_exact_decimal_eof_enters_delta_and_only_new_real_items_draw(self):
  self.case("const g=eofGrid(),old=snapshot(g),before=counters(g);g.ApexGridBegin(deltaRequest(g,220,geometry));assert.equal(g.ApexGridStatus().phase,'row-delta');same(g,old);assert.equal(steps(g).phase,'done');assert.equal(g.apexGridState.job.plan.first,36);assert.equal(padding(g),16);assert.equal(counters(g).bind-before.bind,36);assert.equal(counters(g).draw-before.draw,20);assert.equal(counters(g).selection-before.selection,36);assert.deepEqual(g.mCells.slice(0,204),old.cells.slice(36));emptyCorrect(g);")
 def test_original_current_provider_reproduces_exact_full_window_fallback(self):
  self.case("const g=eofGrid(),before=counters(g);g.ApexGridBegin(deltaRequest(g,220,geometry));assert.notEqual(g.ApexGridStatus().phase,'row-delta');assert.equal(steps(g).phase,'done');assert.equal(counters(g).bind-before.bind,240);assert.equal(counters(g).draw-before.draw,224);assert.equal(padding(g),16);",True)
 def test_native_max_clamp_uses_the_same_verified_padding(self):
  self.case("const g=eofGrid(),before=counters(g);g.ApexGridBegin(deltaRequest(g,1e9,geometry));assert.equal(g.ApexGridStatus().phase,'row-delta');assert.equal(steps(g).phase,'done');assert.equal(g.apexGridState.job.plan.scrollY,g.apexGridState.job.plan.range);assert.equal(counters(g).bind-before.bind,36);assert.equal(counters(g).draw-before.draw,20);emptyCorrect(g);")
 def test_eof_to_one_row_up_borrows_hidden_empty_slots_then_returns_to_origin(self):
  self.case("const g=eofGrid();g.ApexGridBegin(deltaRequest(g,220,geometry));steps(g);const before=counters(g),old=snapshot(g);g.ApexGridBegin(deltaRequest(g,166,geometry));assert.equal(g.ApexGridStatus().phase,'row-delta');same(g,old);assert.equal(steps(g).phase,'done');assert.equal(g.apexGridState.job.plan.first,24);assert.equal(padding(g),4);assert.equal(counters(g).bind-before.bind,12);assert.equal(counters(g).draw-before.draw,12);assert.deepEqual(g.mCells.slice(12),old.cells.slice(0,228));emptyCorrect(g);g.ApexGridBegin(deltaRequest(g,0,geometry));assert.equal(steps(g).phase,'done');assert.equal(padding(g),0);assert.deepEqual(g.mCells.map(c=>c.item.data_id),Array.from({length:240},(_,i)=>'item-'+i));")
 def test_native_full_eof_bank_without_empty_records_can_enter_reverse_delta(self):
  self.case("const g=new NativeGrid(260,0);g.ApexGridBegin(deltaRequest(g,220,geometry));assert.equal(steps(g).phase,'done');assert.equal(padding(g),16);const empty=g.mCells[224];assert.equal(g.apexGridState.presentation.committedBindings[empty],undefined);const before=counters(g);g.ApexGridBegin(deltaRequest(g,166,geometry));assert.equal(g.ApexGridStatus().phase,'row-delta');assert.equal(steps(g).phase,'done');assert.equal(counters(g).draw-before.draw,12);assert.equal(padding(g),4);emptyCorrect(g);")
 def test_partial_initial_last_row_enters_only_native_empty_slots(self):
  self.case("const g=new NativeGrid(239,0);g.ApexGridBegin(deltaRequest(g,0,geometry));steps(g);assert.equal(padding(g),1);const before=counters(g);g.ApexGridBegin(deltaRequest(g,60,geometry));assert.equal(g.ApexGridStatus().phase,'row-delta');assert.equal(steps(g).phase,'done');assert.equal(counters(g).bind-before.bind,12);assert.equal(counters(g).draw-before.draw,0);assert.equal(counters(g).selection-before.selection,12);assert.equal(padding(g),13);emptyCorrect(g);")
 def test_pending_real_images_retain_old_bank_and_cancellation_restores_it(self):
  self.case("const g=eofGrid(),old=snapshot(g);g.delayImages=true;g.ApexGridBegin(deltaRequest(g,220,geometry));for(let i=0;i<3000&&g.apexGridState.delta?.phase!=='textures';i++)g.ApexGridStep(1,0);assert.equal(g.apexGridState.delta.phase,'textures');same(g,old);assert.equal(g.mGridView.mouseChildren,false);g.ApexGridCancel('context');for(let i=0;i<1000&&g.apexGridState.delta;i++)g.ApexGridStep(1,0);same(g,old);")
 def test_repeated_eof_reverse_and_subrow_scroll_keep_native_empty_slots_hidden(self):
  self.case("const g=eofGrid();let maximum=0;for(let n=0;n<16;n++){g.ApexGridBegin(deltaRequest(g,n%2?166:220,geometry));assert.equal(steps(g).phase,'done');emptyCorrect(g);maximum=Math.max(maximum,g.mGridView.children.length);assert.ok(g.mGridView.children.length<=480);const before=counters(g);g.ApexGridBegin(deltaRequest(g,n%2?165.5:219.5,geometry));assert.equal(steps(g).phase,'done');assert.equal(counters(g).draw-before.draw,0);assert.equal(counters(g).bind-before.bind,0);emptyCorrect(g);}assert.ok(maximum<=480);")
 def test_wrong_native_planner_or_eof_geometry_is_not_admitted(self):
  for change in ("p.range+=1;","p.rows++;","p.logicalRows++;","p.target--;","p.pitchY+=1;","p.feedCount=Infinity;"):
   self.case("const g=eofGrid(),s=g.apexGridState,p=s.job.plan;"+change+"assert.equal(g.ApexGridDeltaEofWindow(p,36,s.job.target),false);")
 def test_unknown_capability_or_featured_schema_keeps_the_original_full_path(self):
  for change in ("s.request.rowDeltaReuseContract=0;","s.request.featuredRowIdentity=()=>({});","s.owner.panel_kind='featured';"):
   self.case("const g=eofGrid(),s=g.apexGridState,r=deltaRequest(g,220,geometry);"+change+"assert.equal(g.ApexGridDeltaQueue(s.job,r),false);")
 def test_original_bind_ready_and_native_input_guards_are_source_identical(self):
  import cas_grid_pool
  before=stage.previous.helpers();after=stage.helpers()
  for name in ('ApexGridBind','ApexGridReady','ApexGridFreshInput','ApexGridDeltaCapture'):
   a,b=cas_grid_pool.method_extent(before,name);x,y=cas_grid_pool.method_extent(after,name);self.assertEqual(before[a:b],after[x:y],name)
 def test_foreign_visible_unregistered_selected_or_nonnegative_old_padding_is_refused(self):
  changes=("cell.visible=true;","cell.mouseEnabled=true;","cell.mouseChildren=true;","cell.ext.Selected=true;","s.ready[cell]=99;","delete s.poolFlags[cell];","delete s.intrinsics[cell];","g.mCellIndexToDataIndexMap[224]=260;","const foreign=new DisplayObject();foreign.addChild(cell);","class Foreign extends Cell{}Foreign.qname=Cell.qname;Object.setPrototypeOf(cell,Foreign.prototype);")
  for change in changes:
   self.case("const g=new NativeGrid(260,0);g.ApexGridBegin(deltaRequest(g,220,geometry));steps(g);const s=g.apexGridState,cell=g.mCells[224];"+change+"const parent=cell.parent,visible=cell.visible,old=snapshot(g);g.ApexGridBegin(deltaRequest(g,166,geometry));for(let i=0;i<2000&&s.delta;i++)g.ApexGridStep(1,0);assert.equal(s.delta,null);assert.equal(cell.parent,parent);assert.equal(cell.visible,visible);assert.deepEqual(g.mCells,old.cells);assert.deepEqual(g.mCellIndexToDataIndexMap,old.map);")
 def test_reentrant_null_lookup_cannot_adopt_changed_owner_ready_or_stage_arrays(self):
  changes=("g.lease.generation++;","s.ready={};","d.cells=d.cells.slice();","s.poolFlags[cell].mouse=!s.poolFlags[cell].mouse;","cell.ext={Selected:false};")
  for change in changes:
   # The extra out-of-range lookup was intentionally removed. Exercise the
   # real extension read after the EOF custody scalars were captured instead.
   self.case("const g=new NativeGrid(260,0);g.ApexGridBegin(deltaRequest(g,220,geometry));steps(g);const s=g.apexGridState,old=snapshot(g),cell=g.mCells[224];g.ApexGridBegin(deltaRequest(g,166,geometry));const read=cell.GetExtension;let once=true;cell.GetExtension=function(kind){const d=s.delta;if(once&&d!=null&&d.authority!=null&&d.authority.working===true){once=false;"+change+"}return read.call(this,kind);};for(let i=0;i<2000&&s.delta;i++)g.ApexGridStep(1,0);assert.equal(once,false);assert.equal(s.delta,null);assert.deepEqual(g.mCells,old.cells);assert.deepEqual(g.mCellIndexToDataIndexMap,old.map);")
 def test_nonnull_eof_lookup_never_turns_a_real_product_into_padding(self):
  # A real new product changes the fresh authoritative count; no synthetic
  # out-of-range product lookup is needed or permitted by the EOF reader.
  self.case("const g=new NativeGrid(260,0);g.ApexGridBegin(deltaRequest(g,220,geometry));steps(g);const s=g.apexGridState,old=snapshot(g),read=g.GetDataAtIndex,count=g.GetNumItems;let once=true,outOfRange=0;g.ApexGridBegin(deltaRequest(g,166,geometry));g.GetNumItems=function(){if(once&&s.delta!=null&&s.delta.phase==='publish'){once=false;g.mGridData.items.push(product('new-real-product'));}return count.call(this);};g.GetDataAtIndex=function(i){if(i>=260){outOfRange++;throw Error('unexpected EOF-only lookup');}return read.call(this,i);};for(let i=0;i<2000&&s.delta;i++)g.ApexGridStep(1,0);assert.equal(once,false);assert.equal(outOfRange,0);assert.deepEqual(g.mCells,old.cells);assert.deepEqual(g.mCellIndexToDataIndexMap,old.map);assert.equal(g.apexGridState.job.publishes,1);")
 def test_feedback_cancellation_or_throw_restores_original_product_and_empty_bank(self):
  for change in ("g.ApexGridCancel('context');","throw Error('native EOF feedback refused');"):
   self.case("const g=new NativeGrid(260,0);g.ApexGridBegin(deltaRequest(g,220,geometry));steps(g);const old=snapshot(g);g.ApexGridBegin(deltaRequest(g,166,geometry));g.hooks.resize=()=>{"+change+"};for(let i=0;i<3000&&g.apexGridState.delta;i++)g.ApexGridStep(1,0);same(g,old);emptyCorrect(g);")
 def test_rapid_newer_wheel_retarget_does_not_clear_or_click_wrong_old_cards(self):
  self.case("const g=eofGrid(),old=snapshot(g);g.delayImages=true;g.ApexGridBegin(deltaRequest(g,220,geometry));for(let i=0;i<80;i++)g.ApexGridStep(1,0);same(g,old);g.ApexGridBegin(deltaRequest(g,166,geometry));g.ApexGridBegin(deltaRequest(g,220,geometry));g.delayImages=false;for(let i=0;i<8000&&g.ApexGridStatus().phase!=='done';i++){const p=g.apexGridState.presentation;if(p.stageCells)for(const c of p.stageCells)if(c&&c.mcImage)c.mcImage.ready=true;g.ApexGridStep(1,0);}assert.equal(g.ApexGridStatus().phase,'done');assert.equal(g.apexGridState.job.plan.first,36);emptyCorrect(g);assert.equal(new Set(g.mCells).size,240);")
if __name__=='__main__':unittest.main()
