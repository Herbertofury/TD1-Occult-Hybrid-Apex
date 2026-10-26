from pathlib import Path
from types import SimpleNamespace
import sys,subprocess,unittest
H=Path(__file__).resolve().parents[1];R=next(p for p in (H,*H.parents) if(p/'tools/dbpf_build.py').is_file())
sys.path[:0]=[str(H/'tools'),str(R/'tools'),str(R/'tests')]
import cas_grid_width_stage as stage,test_cas_grid_presentation as fixture,test_cas_grid_spares as spares,test_cas_grid_eof as eof

def javascript(original=False):
 old=fixture.stage
 try:
  fixture.stage=SimpleNamespace(helpers=lambda:(stage.previous.helpers()if original else stage.helpers()).replace('public final function','public function'))
  return fixture.javascript()
 finally:fixture.stage=old

BOOT='''
DisplayObject.prototype.rotation=0;DisplayObject.prototype.alpha=1;
class CASCatalogProduct{}
class BodyCell extends Cell{}BodyCell.qname='widgets.CAS.controls::CASBodyPanelCellView';
function bodyRequest(g,w,extra={}){const r=deltaRequest(g,0,Object.assign({},bodyGeometry,{viewWidth:w,rowDeltaRowValidate:item=>item instanceof CASCatalogProduct},extra));g.lease.panel_kind='body';g.lease.state=-2134636525;return r;}
const bodyGeometry={columns:12,width:37.4499999786,height:51.44999997,gapX:4,gapY:4,viewHeight:1197.7,viewWidth:507.4,scale:.3499999998,viewWidthTransferContract:1};
function widthGrid(n=176){const g=new NativeGrid(n,0);g.mCellType=BodyCell;for(const item of g.mGridData.items)Object.setPrototypeOf(item,CASCatalogProduct.prototype);g.ApexGridBegin(bodyRequest(g,507.4));assert.equal(steps(g).phase,'done');assert.equal(g.lease.panel_kind,'body');assert.equal(g.lease.native_kind,2);assert.equal(g.lease.shell_kind,4);assert.equal(g.lease.state,-2134636525);assert.equal(g.mCells.length,180);assert.ok(g.mCells.every(c=>c.constructor===BodyCell));return g;}
function widthNative(g,w){g.mGridView.width=w;g.ApexGridNativeGuard('position');g.ApexGridNativeGuard('scroll',{mRect:{y:0}});}
function widthRequest(g,w,extra={}){return bodyRequest(g,w,extra);}
function stable(g){return{cells:g.mCells,ys:g.mCellsY,map:g.mCellIndexToDataIndexMap,ready:g.apexGridState.ready,bank:g.apexGridState.presentation.committedBindings,
 ids:g.mCells.map(c=>c.item?.data_id),xy:g.mCells.map(c=>[c.x,c.y,c.scaleX,c.scaleY,c.visible,c.mouseEnabled,c.mouseChildren,c.ext.Selected,c.mcImage.resourceId])};}
function unchanged(g,old){assert.equal(g.mCells,old.cells);assert.equal(g.mCellsY,old.ys);assert.equal(g.mCellIndexToDataIndexMap,old.map);assert.equal(g.apexGridState.ready,old.ready);assert.equal(g.apexGridState.presentation.committedBindings,old.bank);assert.deepEqual(g.mCells.map(c=>c.item?.data_id),old.ids);assert.deepEqual(g.mCells.map(c=>[c.x,c.y,c.scaleX,c.scaleY,c.visible,c.mouseEnabled,c.mouseChildren,c.ext.Selected,c.mcImage.resourceId]),old.xy);}
'''

class WidthTests(unittest.TestCase):
 def case(self,body,original=False):
  native=fixture.NATIVE_MOCK.replace('const getTimer=()=>time;','const getTimer=()=>Math.trunc(time);').replace('this.item=null;this.mcHitArea=','Object.setPrototypeOf(this.ext,Selectability.prototype);this.item=null;this.mcHitArea=')
  code=native+javascript(original)+fixture.BOOT+spares.BOOT+eof.BOOT+BOOT+'{'+body+'}'
  r=subprocess.run(['node','-'],input=code,text=True,capture_output=True,timeout=30)
  if r.returncode:(H/'failed-width.js').write_text(code,encoding='utf-8');(H/'failed-width.log').write_text(r.stdout+r.stderr,encoding='utf-8')
  self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_actual180_slot_width_growth_has_zero_draw_bind_construct_or_position(self):
  self.case("const g=widthGrid(),old=stable(g),before=counters(g),s=g.apexGridState,gen=s.job.generation;widthNative(g,707.4);assert.equal(s.job.dirty,false);assert.equal(g.ApexGridNeedsWork(),true);g.ApexGridBegin(widthRequest(g,707.4));assert.equal(s.job.phase,'done');assert.equal(s.job.generation,gen);assert.equal(g.ApexGridNeedsWork(),false);assert.equal(s.widthOnlyCommits,1);assert.equal(s.job.plan.viewWidth,707.4);unchanged(g,old);const after=counters(g);for(const name of['draw','bind','construct','attach','selection','position','publish'])assert.equal(after[name],before[name],name);assert.equal(g.mbSuppressUpdates,false);assert.equal(g.apexGridAuthority,null);")
 def test_current_original_reproduces_full_rebuild_for_the_same_native_sequence(self):
  self.case("const g=widthGrid(),before=counters(g),gen=g.apexGridState.job.generation;widthNative(g,707.4);assert.equal(g.apexGridState.job.dirty,true);g.ApexGridBegin(widthRequest(g,707.4));steps(g);assert.equal(counters(g).draw-before.draw,176);assert.ok(g.apexGridState.job.generation>gen);",True)
 def test_unknown_capability_keeps_done_position_invalidation_and_full_path(self):
  self.case("const g=widthGrid(),s=g.apexGridState;s.request.viewWidthTransferContract=0;widthNative(g,707.4);assert.equal(s.job.dirty,true);assert.equal(s.widthWake,undefined);")
 def test_height_columns_scale_spacing_and_scroll_changes_do_not_transfer(self):
  for change in ({'columns':13},{'height':52},{'width':38},{'gapX':5},{'gapY':5},{'viewHeight':1100},{'marginX':1},{'marginY':1},{'scale':.4}):
   import json
   self.case("const g=widthGrid(),s=g.apexGridState;widthNative(g,707.4);g.ApexGridBegin(widthRequest(g,707.4,"+json.dumps(change)+"));assert.equal(s.widthOnlyCommits,undefined);assert.equal(s.job.dirty,true);")
 def test_actual_native_height_change_keeps_original_invalidation(self):
  self.case("const g=widthGrid(),s=g.apexGridState;g.mGridView.height-=1;widthNative(g,707.4);assert.equal(s.job.dirty,true);assert.equal(s.widthWake,undefined);")
 def test_repeated_width_growth_shrink_and_idle_keep_same_correct_ready_widgets(self):
  self.case("const g=widthGrid(),old=stable(g),before=counters(g);for(const w of[707.4,607.4,507.4,800,507.4]){widthNative(g,w);g.ApexGridBegin(widthRequest(g,w));assert.equal(g.ApexGridStatus().phase,'done');unchanged(g,old);}assert.equal(g.apexGridState.widthOnlyCommits,5);for(let n=0;n<30;n++)g.ApexGridBegin(widthRequest(g,507.4));assert.deepEqual(counters(g),before);unchanged(g,old);")
 def test_native_feed_selection_profile_reset_or_redraw_never_consumed_as_width(self):
  for kind in ('update','selection','sort','profile','reset','redraw','padding','bounds'):
   event="{currentTarget:g.mGridData,mIndicesArray:Array.from({length:176},(_,i)=>i)}"if kind in('sort','update')else'null'
   self.case("const g=widthGrid(),s=g.apexGridState;widthNative(g,707.4);g.ApexGridNativeGuard('"+kind+"',"+event+");g.ApexGridBegin(widthRequest(g,707.4));assert.equal(s.widthOnlyCommits,undefined);assert.equal(s.job.dirty,true);")
 def test_stolen_suppression_and_external_lease_never_admit_width_wake(self):
  for change in ('g.mbSuppressUpdates=true;','s.lease={foreign:true};','s.externalSuppression=true;'):
   self.case("const g=widthGrid(),s=g.apexGridState;"+change+"widthNative(g,707.4);assert.equal(s.widthWake,undefined);assert.equal(s.job.dirty,true);")
 def test_changed_resource_or_selection_keeps_original_full_bank_route(self):
  for change in ("g.mCells[0].mcImage.resourceId='new-foreign-uri';","g.mCells[0].ext.Selected=true;","g.mGridData.items[0].data_id='new-foreign-product';"):
   self.case("const g=widthGrid(),s=g.apexGridState,old=g.mCells;"+change+"widthNative(g,707.4);g.ApexGridBegin(widthRequest(g,707.4));assert.equal(s.widthOnlyCommits,undefined);assert.equal(s.job.dirty,true);assert.equal(g.mCells,old);assert.equal(g.mGridView.visible,true);")
 def test_registry_or_physical_cell_adoption_during_row_read_is_typed_loss(self):
  for change in ("s.ready={adopted:true};","s.ready[g.mCells[0]]=999;g.mCells[0].y=777;","g.mCells[0].x=777;"):
   self.case("const g=widthGrid(),s=g.apexGridState,old=g.mCells;const read=g.GetDataAtIndex;let once=true;g.GetDataAtIndex=function(i){const item=read.call(this,i);if(once){once=false;"+change+"}return item;};widthNative(g,707.4);g.ApexGridBegin(widthRequest(g,707.4));assert.equal(once,false);assert.equal(s.widthOnlyCommits,undefined);assert.equal(g.ApexGridAuthorityStatus().phase,'authority-lost');assert.equal(g.mCells,old);assert.equal(g.mGridView.visible,true);")
 def test_complete_state_replacement_in_row_read_remains_untouched(self):
  self.case("const g=widthGrid(),s=g.apexGridState,old=g.mCells,foreign={job:null,marker:'foreign'};const read=g.GetDataAtIndex;let once=true;g.GetDataAtIndex=function(i){const item=read.call(this,i);if(once){once=false;g.apexGridState=foreign;}return item;};widthNative(g,707.4);g.ApexGridBegin(widthRequest(g,707.4));assert.equal(g.apexGridState,foreign);assert.deepEqual(foreign,{job:null,marker:'foreign'});assert.equal(g.ApexGridAuthorityStatus().phase,'authority-lost');assert.equal(g.mCells,old);assert.equal(g.mGridView.visible,true);")
 def test_cancellation_and_native_throw_do_not_rewrite_any_ready_card(self):
  for action in ("g.ApexGridCancel('context');","throw Error('original native read failed');"):
   self.case("const g=widthGrid(),old=stable(g);const read=g.GetDataAtIndex;let once=true;g.GetDataAtIndex=function(i){if(once){once=false;"+action+"}return read.call(this,i);};widthNative(g,707.4);try{g.ApexGridBegin(widthRequest(g,707.4));}catch(e){assert.equal(e.message,'original native read failed');}unchanged(g,old);assert.equal(g.mGridView.visible,true);assert.equal(g.apexGridState.delta,null);assert.equal(g.apexGridAuthority,null);assert.equal(g.mbSuppressUpdates,false);assert.equal(g.mGridView.mouseEnabled,true);assert.equal(g.mGridView.mouseChildren,true);")

if __name__=='__main__':unittest.main()
