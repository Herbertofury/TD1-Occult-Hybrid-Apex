from pathlib import Path
import sys,importlib.util,subprocess,unittest,json
ROOT=Path(__file__).resolve().parents[1];PROJECT=next(p for p in (ROOT,*ROOT.parents) if (p/'tools/cas_grid_progress.py').is_file());sys.path[:0]=[str(ROOT/'tools'),str(PROJECT/'tests'),str(PROJECT/'tools')]
import test_cas_grid_presentation as base
import cas_grid_scroll as proto

EXTRA=r'''
const initImage=Object.getOwnPropertyDescriptor(Cell.prototype,'mcImage').get;
Object.defineProperty(Cell.prototype,'pixelImage',{get(){const image=initImage.call(this);if(!image._counted){const ready=image.ApexImageReadyFor;image.ApexImageReadyFor=function(resource){imageCalls++;return ready.call(this,resource);};image._counted=true;}return image;}});
let imageCalls=0;
const createCell=NativeGrid.prototype.CreateCell;
NativeGrid.prototype.CreateCell=function(){const c=createCell.call(this);c.pixelImage;return c;};
function fresh(options={}){const g=new NativeGrid(1000,0);g.lease.panel_kind='clothing';g.lease.cell_type=Cell;
 if(options.failPrimary)g.failPrimary=true;if(options.failWarning)g.failWarning=true;
 g.ApexGridBegin(pixelRequest(g,0));assert.equal(bounded(g).phase,'done');return g;}
function pixelRequest(g,y,extra={}){return request(g,12,{width:53.5,height:73.5,scale:.5,viewHeight:770,scrollY:y,scrollOnlyPositionContract:1,...extra});}
function delta(before,after){const out={};for(const k of Object.keys(before.counts))out[k]=after.counts[k]-before.counts[k];return out;}
function queue(g,y){assert.equal(g.ApexGridNativeGuard('scroll',{mRect:{y:-y}}),true);}
function ys(g){return g.mCells.map(c=>c.y);}
'''
class PixelTests(unittest.TestCase):
 def case(self,code):
  original=base.stage
  try:
   base.stage=proto
   js=base.javascript().replace('this.mCellType','this.mCellType')
   r=subprocess.run(['node','-'],input=base.NATIVE_MOCK+js+base.BOOT+EXTRA+code,capture_output=True,text=True,timeout=15);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
  finally:base.stage=original
 def test_queued_pixel_requests_are_work_for_the_unchanged_main_idle_gate(self):
  controller=(PROJECT/'Source/CASUi/catalog_grid_transaction_methods.as').read_text()
  self.assertIn('s.grid.ApexGridNeedsWork()===false)return;',controller)
  self.case("const g=fresh();assert.equal(g.ApexGridNeedsWork(),false);queue(g,1);assert.equal(g.apexGridState.job.dirty,false);assert.equal(g.ApexGridNeedsWork(),true);g.ApexGridStep(1,0);assert.equal(g.ApexGridNeedsWork(),false);queue(g,2);g.lease.active=false;assert.equal(g.ApexGridNeedsWork(),true);g.ApexGridStep(1,0);assert.equal(g.ApexGridNeedsWork(),false);")
 def test_one_pixel_updates_132_positions_without_draw_data_selection_or_texture_work(self):
  self.case("const g=fresh();const before=g.ApexGridStatus(),cells=g.mCells.slice(),map=g.mCellIndexToDataIndexMap.slice(),old=ys(g),images=imageCalls;queue(g,1);assert.equal(g.ApexGridStatus().phase,'scroll-only');assert.deepEqual(ys(g),old);const after=g.ApexGridStep(1,0),d=delta(before,after);assert.equal(after.phase,'done');assert.equal(after.scroll_only_commits,1);assert.equal(d.position,132);for(const k of ['draw','bind','data','selection','selected_setter','construct','attach','retire'])assert.equal(d[k],0,k);assert.equal(imageCalls,images);assert.deepEqual(g.mCells,cells);assert.deepEqual(g.mCellIndexToDataIndexMap,map);assert.deepEqual(ys(g),old.map(y=>y-1));assert.equal(g.mPrevRectangleUpdate.y,-1);assert.equal(g.apexGridState.job.plan.scrollY,1);assert.equal(g.mGridView.visible,true);")
 def test_newest_raw_echo_is_coalesced_and_scroll_back_is_exact(self):
  self.case("const g=fresh(),old=ys(g);queue(g,1);queue(g,2);queue(g,3.5);assert.equal(g.ApexGridStep(1,0).phase,'done');assert.deepEqual(ys(g),old.map(y=>y-3.5));assert.equal(g.apexGridState.job.desired.scrollY,3.5);queue(g,0);assert.equal(g.ApexGridStep(1,0).phase,'done');assert.deepEqual(ys(g),old);assert.equal(g.mPrevRectangleUpdate.y,-0);")
 def test_pending_pixel_queue_never_mutates_before_fresh_frame_lease(self):
  self.case("const g=fresh(),old=ys(g);g.lease.frame_validated=false;const original=g.apexGridState.validate;g.apexGridState.validate=o=>o.frame_validated===true&&original(o);queue(g,1);assert.deepEqual(ys(g),old);assert.equal(g.ApexGridNativeGuard('input',{currentTarget:g.mCells[0]}),true);g.lease.frame_validated=true;assert.equal(g.ApexGridStep(1,0).phase,'done');assert.deepEqual(ys(g),old.map(y=>y-1));")
 def test_wrong_or_stale_owner_refuses_without_any_coordinate_mutation(self):
  self.case("const g=fresh(),old=ys(g),before=g.ApexGridStatus();queue(g,1);g.lease.active=false;g.ApexGridStep(1,0);assert.deepEqual(ys(g),old);assert.equal(g.ApexGridStatus().publishes,before.publishes);assert.equal(g.apexGridState.job.scrollCommits,undefined);")
 def test_unknown_default_requests_keep_full_native_binding_path(self):
  self.case("const g=fresh();const before=g.ApexGridStatus();g.ApexGridBegin(pixelRequest(g,1,{scrollOnlyPositionContract:0}));assert.equal(bounded(g).phase,'done');const d=delta(before,g.ApexGridStatus());assert.equal(d.draw,132);assert.equal(d.data,396);assert.equal(g.ApexGridStatus().scroll_only_commits,0);")
 def test_row_boundary_then_return_and_new_geometry_use_existing_full_transaction(self):
  self.case("const g=fresh();queue(g,1);g.ApexGridStep(1,0);const before=g.ApexGridStatus();g.ApexGridBegin(pixelRequest(g,77.5));assert.equal(bounded(g).phase,'done');assert.equal(delta(before,g.ApexGridStatus()).draw,132);assert.equal(g.mCellIndexToDataIndexMap[0],12);g.ApexGridBegin(pixelRequest(g,0));assert.equal(bounded(g).phase,'done');assert.equal(g.mCellIndexToDataIndexMap[0],0);const d=g.ApexGridStatus();g.ApexGridBegin(pixelRequest(g,1,{height:70}));assert.equal(bounded(g).phase,'done');assert.ok(delta(d,g.ApexGridStatus()).draw>0);")
 def test_new_feed_revision_and_category_owner_disable_pixel_fastpath(self):
  self.case("const g=fresh();const before=g.ApexGridStatus();queue(g,1);g.mGridData.items[0]=product('changed');g.ApexGridNativeGuard('update',{currentTarget:g.mGridData});assert.equal(bounded(g).phase,'done');assert.equal(g.mCells[0].item.data_id,'changed');assert.ok(delta(before,g.ApexGridStatus()).draw>0);const old=ys(g);queue(g,2);g.lease.active=false;g.ApexGridStep(1,0);assert.deepEqual(ys(g),old);")
 def test_dispose_pending_and_completed_scroll_keeps_exact_owned_coordinates(self):
  self.case("for(const completed of [false,true]){const g=fresh(),old=ys(g);queue(g,1);if(completed)g.ApexGridStep(1,0);const now=ys(g);g.lease.active=false;g.ApexGridCancel('dispose');assert.deepEqual(ys(g),now);assert.equal(g.ApexGridStatus().lease,false);assert.equal(g.mGridView.visible,true);assert.equal(g.ApexGridNativeGuard('input',{currentTarget:g.mCells[0]}),true);assert.deepEqual(now,completed?old.map(y=>y-1):old);}")
 def test_native_feedback_revision_reentry_rolls_back_without_pixel_publication(self):
  self.case("const g=fresh(),old=ys(g),before=g.ApexGridStatus();let once=true;g.hooks.resize=()=>{if(once){once=false;g.mGridData.items[0]=product('reentrant');g.ApexGridNativeGuard('update',{currentTarget:g.mGridData});}};queue(g,1);g.ApexGridStep(1,0);assert.deepEqual(ys(g),old);assert.equal(g.mPrevRectangleUpdate.y,-0);assert.equal(g.ApexGridStatus().publishes,before.publishes);assert.equal(g.ApexGridStatus().scroll_only_commits,0);assert.equal(g.ApexGridNativeGuard('input',{currentTarget:g.mCells[0]}),true);")
 def test_native_feedback_throw_rolls_back_and_does_not_replay_or_publish(self):
  self.case("const g=fresh(),old=ys(g),before=g.ApexGridStatus();let calls=0;g.hooks.resize=()=>{calls++;throw Error('original feedback failed');};queue(g,1);const after=g.ApexGridStep(1,0);assert.deepEqual(ys(g),old);assert.equal(g.mPrevRectangleUpdate.y,-0);assert.equal(after.publishes,before.publishes);assert.equal(calls,1);assert.ok(after.error.includes('original feedback failed'));")
 def test_pending_native_redraw_invalidates_pixel_only_work(self):
  self.case("const g=fresh();const before=g.ApexGridStatus();queue(g,1);g.ApexGridNativeGuard('redraw',{currentTarget:g.mCells[0]});assert.equal(g.apexGridState.job.dirty,true);assert.equal(bounded(g).phase,'done');assert.ok(delta(before,g.ApexGridStatus()).draw>0);assert.equal(g.ApexGridStatus().scroll_only_commits,0);")
 def test_existing_warning_and_failure_diagnostic_resources_are_preserved_without_reloading(self):
  self.case("for(const failWarning of [false,true]){const g=fresh({failPrimary:true,failWarning}),resources=g.mCells.map(c=>c.mcImage.resourceId),images=imageCalls;queue(g,1);assert.equal(g.ApexGridStep(1,0).phase,'done');assert.deepEqual(g.mCells.map(c=>c.mcImage.resourceId),resources);assert.equal(imageCalls,images);if(failWarning)assert.ok(g.mCells.every(c=>c.getChildByName('apexThumbnailFailure').visible));}")
 def test_raw_scroll_reentry_during_resize_coalesces_without_dirty_oscillation(self):
  self.case("const g=fresh(),old=ys(g),before=g.ApexGridStatus();let once=true;g.hooks.resize=()=>{if(once){once=false;queue(g,2.25);}};queue(g,1);assert.equal(g.ApexGridStep(1,0).phase,'scroll-only');assert.equal(g.apexGridState.job.dirty,false);assert.equal(g.apexGridState.job.plan.scrollY,1);assert.equal(g.apexGridState.job.desired.scrollY,2.25);assert.equal(g.ApexGridStep(1,0).phase,'done');assert.deepEqual(ys(g),old.map(y=>y-2.25));assert.equal(delta(before,g.ApexGridStatus()).draw,0);assert.equal(g.ApexGridStatus().scroll_only_commits,2);")
 def test_partial_end_padding_and_clamping_do_not_move_or_expose_parked_widgets(self):
  self.case("const g=new NativeGrid(176,0);g.lease.panel_kind='body';g.lease.cell_type=Cell;g.ApexGridBegin(pixelRequest(g,0));assert.equal(bounded(g).phase,'done');const before=g.ApexGridStatus(),old=ys(g);assert.equal(g.mCells.length,132);queue(g,1);assert.equal(g.ApexGridStep(1,0).phase,'done');assert.equal(delta(before,g.ApexGridStatus()).draw,0);g.ApexGridBegin(pixelRequest(g,100000));assert.equal(bounded(g).phase,'done');const max=g.apexGridState.job.plan.range,done=g.ApexGridStatus();queue(g,max+1);assert.equal(g.ApexGridStatus().phase,'done');assert.equal(g.apexGridState.job.plan.scrollY,max);assert.equal(g.ApexGridStatus().publishes,done.publishes);const padding=g.mCells.map((c,i)=>g.mCellIndexToDataIndexMap[i]<0?c.y:null),beforePixel=g.ApexGridStatus();queue(g,max-1);assert.equal(g.ApexGridStep(1,0).phase,'done');assert.equal(delta(beforePixel,g.ApexGridStatus()).draw,0);for(let i=0;i<g.mCells.length;i++)if(g.mCellIndexToDataIndexMap[i]<0){assert.equal(g.mCells[i].visible,false);assert.equal(g.mCells[i].y,padding[i]);}")
 def test_mismatched_coordinate_ledger_and_unsupported_owner_take_full_fallback(self):
  self.case("for(const unsupported of [false,true]){const g=fresh(),before=g.ApexGridStatus();if(unsupported)g.lease.panel_kind='featured';else g.mCells[0].y+=.5;queue(g,1);assert.equal(bounded(g).phase,'done');assert.equal(g.ApexGridStatus().scroll_only_commits,0);assert.equal(delta(before,g.ApexGridStatus()).draw,132);}")
if __name__=='__main__':unittest.main()
