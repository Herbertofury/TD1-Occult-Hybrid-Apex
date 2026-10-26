"""PRIVATE actual-AS product-grid prototype; no production capability grant."""
from pathlib import Path
import subprocess,sys,unittest
H=Path(__file__).resolve().parents[1];R=next(p for p in (H,*H.parents) if(p/'tools/dbpf_build.py').is_file());sys.path[:0]=[str(H/'tools'),str(R/'tools'),str(R/'tests')]
import cas_row_delta_stage as stage
import cas_grid_row_delta as contract
import test_cas_grid_presentation as f


def javascript():
    old=f.stage
    try:f.stage=contract;return f.javascript()
    finally:f.stage=old


BOOT='''
function uint(v){return v>>>0;}
function getQualifiedClassName(value){return Object.getPrototypeOf(value)===Selectability.prototype?'olympus.extensions::Selectability':'custom-extension';}
const realProductRow=item=>item!=null&&typeof item.GetVariationOrBaseId==='function';
function deltaRequest(g,scrollY=0,extra={}){g.lease.cell_type=g.mCellType;g.lease.panel_kind='clothing';return request(g,6,Object.assign({viewHeight:400,scrollY,
 rowDeltaReuseContract:1,rowDeltaFeedbackContract:'ea-complete-ready-before-resize-v1',
 rowDeltaRowValidate:realProductRow},extra));}
function ready(g){g.ApexGridBegin(deltaRequest(g));assert.equal(bounded(g).phase,'done');return g;}
function counters(g){return Object.assign({},g.ApexGridStatus().counts);}
function steps(g,n=10000){for(let i=0;i<n&&g.ApexGridStatus().phase!=='done'&&g.ApexGridStatus().phase!=='cancelled';i++)g.ApexGridStep(1,0);return g.ApexGridStatus();}
function snapshot(g){return {cells:g.mCells.slice(),ys:g.mCells.map(c=>c.y),visible:g.mCells.map(c=>c.visible),ids:rendered(g),map:g.mCellIndexToDataIndexMap.slice()};}
function same(g,old){assert.deepEqual(g.mCells.map(c=>c.id),old.cells.map(c=>c.id));assert.deepEqual(g.mCells.map(c=>c.y),old.ys);assert.deepEqual(g.mCells.map(c=>c.visible),old.visible);assert.deepEqual(rendered(g),old.ids);assert.deepEqual(g.mCellIndexToDataIndexMap,old.map);}
'''


class DeltaTests(unittest.TestCase):
    def case(self,code):
        raw=f.NATIVE_MOCK.replace('const getTimer=()=>time;','const getTimer=()=>Math.trunc(time);')
        raw=raw.replace('this.item=null;this.mcHitArea=', 'Object.setPrototypeOf(this.ext,Selectability.prototype);this.item=null;this.mcHitArea=')
        p=subprocess.run(['node','-'],input=raw+javascript()+f.BOOT+BOOT+code,capture_output=True,text=True,timeout=15)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
    def test_one_row_only_entering_native_bind_draw_selection_and_factory_calls(self):
        self.case('''const g=ready(new NativeGrid(1000,0));const old=snapshot(g),before=counters(g),calls=g.calls.length;
g.ApexGridBegin(deltaRequest(g,55));assert.equal(g.ApexGridStatus().phase,'row-delta');assert.equal(steps(g).phase,'done');
const after=counters(g);assert.equal(after.draw-before.draw,6);assert.equal(after.bind-before.bind,6);assert.equal(after.selection-before.selection,6);
assert.equal(g.calls.slice(calls).filter(x=>x==='construct').length,6);assert.equal(g.calls.slice(calls).filter(x=>x==='attach').length,6);
assert.deepEqual(g.mCells.slice(0,48),old.cells.slice(6));assert.deepEqual(rendered(g),Array.from({length:54},(_,i)=>'item-'+(6+i)));
assert.ok(g.mGridView.mouseChildren);assert.equal(new Set(g.mCells).size,54);assert.ok(g.apexGridState.presentation.spareCells.every(c=>!g.mCells.includes(c)&&!c.visible));''')
    def test_borrowed_widgets_are_never_moved_hidden_or_redrawn_while_loading(self):
        self.case('''const g=ready(new NativeGrid(1000,0)),old=snapshot(g);g.delayImages=true;g.ApexGridBegin(deltaRequest(g,55));
for(let i=0;i<3000&&(!g.apexGridState.delta||g.apexGridState.delta.phase!=='textures');i++){g.ApexGridStep(1,0);same(g,old);}
assert.equal(g.apexGridState.delta.phase,'textures');for(let i=0;i<20;i++){g.ApexGridStep(1,0);same(g,old);}
for(const c of g.apexGridState.delta.cells)if(g.apexGridState.delta.entering[c])c.mcImage.ready=true;
assert.equal(steps(g).phase,'done');assert.deepEqual(g.mCells.slice(0,48),old.cells.slice(6));''')
    def test_backwards_reuses_overlap_and_hidden_spares_without_new_widgets(self):
        self.case('''const g=ready(new NativeGrid(1000,0));g.ApexGridBegin(deltaRequest(g,55));steps(g);const before=counters(g),calls=g.calls.length,old=snapshot(g);
g.ApexGridBegin(deltaRequest(g,0));assert.equal(steps(g).phase,'done');const after=counters(g);
assert.equal(after.draw-before.draw,6);assert.equal(g.calls.slice(calls).filter(x=>x==='construct').length,0);
assert.deepEqual(g.mCells.slice(6),old.cells.slice(0,48));assert.deepEqual(rendered(g),Array.from({length:54},(_,i)=>'item-'+i));''')
    def test_unknown_feedback_or_selection_contract_stays_on_original_full_pipeline(self):
        for key,value in [('rowDeltaReuseContract',0),('rowDeltaFeedbackContract','unknown'),('rowDeltaRowValidate',None)]:
            literal='null'if value is None else repr(value)
            self.case("const g=ready(new NativeGrid(1000,0)),before=counters(g);const r=deltaRequest(g,55);r["+repr(key)+"]="+literal+";g.ApexGridBegin(r);assert.notEqual(g.ApexGridStatus().phase,'row-delta');assert.equal(steps(g).phase,'done');assert.equal(counters(g).draw-before.draw,54);")
    def test_precommit_source_revision_change_restores_exact_old_presentation(self):
        self.case('''const g=ready(new NativeGrid(1000,0)),old=snapshot(g);g.delayImages=true;g.ApexGridBegin(deltaRequest(g,55));
for(let i=0;i<3000&&g.apexGridState.delta.phase!=='textures';i++)g.ApexGridStep(1,0);
g.ApexGridNativeGuard('update',{currentTarget:g.mGridData});g.ApexGridStep(1,0);same(g,old);assert.equal(g.apexGridState.delta,null);assert.equal(g.ApexGridStatus().phase,'acquire');''')
    def test_committed_native_redraw_invalidates_delta_instead_of_losing_genuine_repaint(self):
        self.case('''const g=ready(new NativeGrid(1000,0)),old=snapshot(g);g.delayImages=true;g.ApexGridBegin(deltaRequest(g,55));
for(let i=0;i<3000&&g.apexGridState.delta.phase!=='textures';i++)g.ApexGridStep(1,0);
const before=g.apexGridState.revision;g.ApexGridNativeGuard('redraw',{currentTarget:old.cells[6]});assert.equal(g.apexGridState.revision,before+1);
g.ApexGridStep(1,0);same(g,old);assert.equal(g.apexGridState.delta,null);assert.equal(g.ApexGridStatus().phase,'acquire');''')
    def test_original_resize_route_observes_correct_map_and_cannot_publish_hidden_borrowed_card(self):
        self.case('''const g=ready(new NativeGrid(1000,0)),old=snapshot(g);let seen=0;
g.hooks.resize=()=>{seen++;const d=g.apexGridState.delta;assert.ok(d);assert.equal(g.apexGridState.job.publishing,true);
 assert.equal(g.mCellIndexToDataIndexMap[0],6);assert.equal(g.ApexGridPoolViews().length,54,'complete ready callback projection');
 for(let i=0;i<g.mCells.length;i++){assert.equal(g.mCells[i].visible,true);assert.equal(g.mCells[i].y,d.ys[i]);assert.equal(g.mCells[i].mcImage.ready,true);}
 for(const c of old.cells.slice(0,6))assert.equal(c.visible,false,'leaving art is already retired during native callback');
 assert.equal(g.ApexGridNativeGuard('input',{currentTarget:g.mCells[0]}),true,'input remains blocked during callback');
 d.oldCells[6].visible=false;
};g.ApexGridBegin(deltaRequest(g,55));for(let i=0;i<3000&&g.apexGridState.delta;i++)g.ApexGridStep(1,0);
same(g,old);assert.equal(g.ApexGridStatus().phase,'acquire');assert.equal(seen,1);assert.equal(g.apexGridState.delta,null);''')
    def test_resize_resource_or_owner_reentry_restores_held_coordinates_without_overwriting_external_edits(self):
        for mutation in ["g.lease.active=false;", "g.apexGridState.delta.oldCells[6].mcImage.resourceId='foreign';"]:
            self.case('''const g=ready(new NativeGrid(1000,0)),old=snapshot(g);g.hooks.resize=()=>{'''+mutation+'''};
g.ApexGridBegin(deltaRequest(g,55));for(let i=0;i<3000&&g.apexGridState.delta;i++)g.ApexGridStep(1,0);same(g,old);assert.equal(g.apexGridState.delta,null);''')
    def test_custom_selection_extension_falls_back_to_original_full_path(self):
        self.case('''const g=ready(new NativeGrid(1000,0)),old=snapshot(g);class CustomSelection extends Selectability{}
Object.setPrototypeOf(g.mCells[6].ext,CustomSelection.prototype);g.ApexGridBegin(deltaRequest(g,55));
for(let i=0;i<3000&&g.apexGridState.delta;i++)g.ApexGridStep(1,0);same(g,old);assert.equal(g.ApexGridStatus().phase,'acquire');
assert.match(g.apexGridState.deltaLastRefusal,/extension/);assert.equal(steps(g).phase,'done');''')
    def test_replaced_authoritative_state_and_view_are_not_overwritten_by_old_rollback(self):
        self.case('''const g=ready(new NativeGrid(1000,0));let fresh=null,view=null,cells=null;
g.hooks.resize=()=>{fresh={armed:false,job:null,replacement:true};view=new DisplayObject();cells=[];g.apexGridState=fresh;g.mGridView=view;g.mCells=cells;g.mCellsY=[];g.mCellIndexToDataIndexMap=[];};
g.ApexGridBegin(deltaRequest(g,55));for(let i=0;i<3000&&!fresh;i++)g.ApexGridStep(1,0);
assert.equal(g.apexGridState,fresh);assert.equal(g.mGridView,view);assert.equal(g.mCells,cells);assert.equal(g.apexGridState.replacement,true);''')
    def test_arbitrary_native_draw_throw_is_unchanged_after_cleanup(self):
        self.case('''const g=ready(new NativeGrid(1000,0)),old=snapshot(g),sentinel={native:'exact thrown value'};
g.hooks.draw=()=>{throw sentinel;};g.ApexGridBegin(deltaRequest(g,55));let caught=null;
for(let i=0;i<3000&&!caught;i++){try{g.ApexGridStep(1,0);}catch(e){caught=e;}}
assert.equal(caught,sentinel);same(g,old);assert.equal(g.apexGridState.delta,null);''')
    def test_no_borrowed_product_or_mutable_identity_alias_survives_a_yield(self):
        self.case('''const g=ready(new NativeGrid(1000,0));g.ApexGridBegin(deltaRequest(g,55));
for(let i=0;i<25;i++)g.ApexGridStep(1,0);const d=g.apexGridState.delta;assert.ok(d);
for(const c of d.cells){if(!c)continue;const record=d.bindings[c];if(!record)continue;
 assert.ok(Object.values(record).every(v=>['string','number','boolean'].includes(typeof v)));assert.notEqual(record,d.oldBindings[c]);
 for(const item of g.mGridData.items)assert.notEqual(record,item);
}assert.equal('item' in d,false);assert.equal('product' in d,false);''')
    def test_fractional_origin_preserves_native_scroll_echo_and_correct_texture_identity(self):
        self.case('''const g=ready(new NativeGrid(1000,0)),old=snapshot(g),before=counters(g);g.ApexGridBegin(deltaRequest(g,58.125));assert.equal(steps(g).phase,'done');
assert.equal(g.mPrevRectangleUpdate.y,-58.125);assert.equal(g.scroll,58.125);assert.equal(g.apexGridState.job.plan.first,6);
assert.equal(g.apexGridState.job.plan.originY,-3.125);assert.equal(counters(g).draw-before.draw,6);
assert.deepEqual(g.mCells.slice(0,48).map(c=>c.mcImage.resourceId),old.cells.slice(6).map(c=>c.mcImage.resourceId));''')
    def test_eof_no_overlap_geometry_or_surplus_capacity_refuse_delta_without_blank_or_schema_merge(self):
        self.case('''const g=ready(new NativeGrid(60,0));g.ApexGridBegin(deltaRequest(g,10000));assert.notEqual(g.ApexGridStatus().phase,'row-delta');assert.equal(steps(g).phase,'done');
const q=ready(new NativeGrid(1000,0));const altered=deltaRequest(q,55,{width:39});q.ApexGridBegin(altered);assert.notEqual(q.ApexGridStatus().phase,'row-delta');assert.equal(steps(q).phase,'done');
const z=ready(new NativeGrid(1000,0));z.apexGridState.request.featuredRowIdentity=()=>null;assert.equal(z.ApexGridDeltaCapable(),false);''')
    def test_cancel_each_delta_phase_restores_committed_bank_and_disjoint_spares(self):
        for phase in ['plan','attach','position','bind','selection','textures','publish']:
            self.case("const g=ready(new NativeGrid(1000,0)),old=snapshot(g);g.delayImages="+('false'if phase=='publish'else'true')+";g.ApexGridBegin(deltaRequest(g,55));for(let i=0;i<3000&&g.apexGridState.delta.phase!=="+repr(phase)+";i++)g.ApexGridStep(1,0);assert.equal(g.apexGridState.delta.phase,"+repr(phase)+");g.ApexGridCancel('context');same(g,old);const p=g.apexGridState.presentation;assert.equal(new Set(p.spareCells).size,p.spareCells.length);assert.ok(p.spareCells.every(c=>!g.mCells.includes(c)&&!c.visible));")
    def test_ordinary_native_scroll_notification_reaches_real_delta_without_a_new_host_request(self):
        self.case('''const g=ready(new NativeGrid(1000,0)),before=counters(g);assert.equal(g.ApexGridNativeGuard('scroll',{mRect:{y:-55}}),true);
assert.equal(g.ApexGridStatus().phase,'row-delta');assert.equal(g.ApexGridNeedsWork(),true);assert.equal(steps(g).phase,'done');
assert.equal(counters(g).draw-before.draw,6);assert.equal(g.mCellIndexToDataIndexMap[0],6);assert.equal(g.ApexGridNeedsWork(),false);''')
    def test_between_frame_native_scroll_queues_without_a_fresh_frame_but_mutates_only_after_full_fresh_lease(self):
        self.case('''const g=ready(new NativeGrid(1000,0)),old=snapshot(g),before=counters(g),calls=g.calls.length;const validate=g.apexGridState.validate;
g.apexGridState.validate=o=>o.frame_validated===true&&validate(o);g.lease.frame_validated=false;
assert.equal(g.ApexGridNativeGuard('scroll',{mRect:{y:-55}}),true);assert.equal(g.ApexGridStatus().phase,'row-delta');same(g,old);
assert.equal(g.calls.length,calls,'queue has no native lookups/Draw/display work');assert.equal(g.ApexGridNativeGuard('input',{currentTarget:g.mCells[0]}),true);
g.lease.frame_validated=true;assert.equal(steps(g).phase,'done');assert.equal(counters(g).draw-before.draw,6);assert.equal(g.mCellIndexToDataIndexMap[0],6);''')
    def test_240_cards_bind_draw_and_load_only_twelve_entering_cards(self):
        self.case('''const g=new NativeGrid(10000,0);g.ApexGridBegin(deltaRequest(g,0,{columns:12,viewHeight:1009.7}));assert.equal(bounded(g).phase,'done');
assert.equal(g.mCells.length,240);const old=snapshot(g),before=counters(g),calls=g.calls.length;g.ApexGridBegin(deltaRequest(g,55,{columns:12,viewHeight:1009.7}));
assert.equal(steps(g).phase,'done');assert.equal(counters(g).draw-before.draw,12);assert.equal(counters(g).bind-before.bind,12);assert.equal(counters(g).selection-before.selection,12);
assert.equal(g.calls.slice(calls).filter(c=>c==='construct').length,12);assert.deepEqual(g.mCells.slice(0,228),old.cells.slice(12));assert.equal(new Set(g.mCells).size,240);''')
    def test_newer_pending_raw_scroll_never_publishes_stale_candidate_and_keeps_original_ready_art(self):
        self.case('''const g=ready(new NativeGrid(1000,0)),old=snapshot(g);g.delayImages=true;g.ApexGridBegin(deltaRequest(g,55));
for(let i=0;i<3000&&g.apexGridState.delta.phase!=='textures';i++)g.ApexGridStep(1,0);
g.ApexGridNativeGuard('scroll',{mRect:{y:-110.25}});g.ApexGridStep(1,0);same(g,old);assert.ok(g.apexGridState.delta);
g.delayImages=false;assert.equal(steps(g).phase,'done');assert.equal(g.apexGridState.job.plan.scrollY,110.25);assert.equal(g.mCellIndexToDataIndexMap[0],12);''')
    def test_sorted_filtered_native_mapping_remains_authoritative_for_overlap(self):
        self.case('''const g=ready(new NativeGrid(1000,0));const indices=Array.from({length:300},(_,i)=>999-i*2);
g.ApexGridNativeGuard('sort',{currentTarget:g.mGridData,mIndicesArray:indices});assert.equal(steps(g).phase,'done');
const before=counters(g),old=snapshot(g);g.ApexGridBegin(deltaRequest(g,55));assert.equal(steps(g).phase,'done');assert.equal(counters(g).draw-before.draw,6);
assert.deepEqual(g.mCells.slice(0,48),old.cells.slice(6));assert.deepEqual(g.mCells.map(c=>c.item.data_id),indices.slice(6,60).map(i=>'item-'+i));''')
    def test_real_selection_feed_update_while_waiting_forces_full_ready_selection_not_stale_reuse(self):
        self.case('''const g=ready(new NativeGrid(1000,0)),old=snapshot(g);g.delayImages=true;g.ApexGridBegin(deltaRequest(g,55));
for(let i=0;i<3000&&g.apexGridState.delta.phase!=='textures';i++)g.ApexGridStep(1,0);
g.mGridData.selection.add(7);g.ApexGridNativeGuard('selection');g.ApexGridStep(1,0);same(g,old);g.delayImages=false;assert.equal(steps(g).phase,'done');
assert.equal(g.mCells.find(c=>c.item.data_id==='item-7').ext.Selected,true);''')
    def test_owner_class_or_validator_change_is_refused_without_mutating_held_presentation(self):
        for mutation in ["g.lease.cell_type=OtherCell;", "g.lease.panel_kind='featured';", "g.apexGridState.request.rowDeltaRowValidate=()=>true;", "g.apexGridState.request.rowDeltaReuseContract=0;"]:
            self.case('''const g=ready(new NativeGrid(1000,0)),old=snapshot(g);g.ApexGridBegin(deltaRequest(g,55));g.ApexGridStep(1,0);'''+mutation+'''
g.ApexGridStep(1,0);same(g,old);assert.equal(g.apexGridState.delta,null);assert.equal(g.ApexGridStatus().phase,'acquire');''')
    def test_existing_ea_warning_and_text_failure_resources_remain_valid_for_delta_overlap(self):
        self.case('''for(const failWarning of[false,true]){const g=new NativeGrid(1000,0);g.failPrimary=true;g.failWarning=failWarning;ready(g);const old=snapshot(g),before=counters(g);
g.ApexGridBegin(deltaRequest(g,55));assert.equal(steps(g).phase,'done');assert.equal(counters(g).draw-before.draw,6);assert.deepEqual(g.mCells.slice(0,48),old.cells.slice(6));
for(const c of g.mCells){if(failWarning){assert.ok(c.getChildByName('apexThumbnailFailure').visible);assert.ok(c.getChildByName('apexThumbnailFailure').text.length>0);}else assert.ok(c.mcImage.ApexImageReadyFor(SharedIcons.ICON_WARNING));}}''')
    def test_entering_native_attach_stays_hidden_and_callback_reentry_restores_all_committed_art(self):
        self.case('''const g=ready(new NativeGrid(1000,0)),old=snapshot(g);let calls=0;g.hooks.attach=cell=>{calls++;assert.equal(cell.visible,false);assert.equal(cell.parent,g.mGridView);same(g,old);g.ApexGridNativeGuard('update',{currentTarget:g.mGridData});};
g.ApexGridBegin(deltaRequest(g,55));for(let i=0;i<3000&&g.apexGridState.delta;i++)g.ApexGridStep(1,0);same(g,old);assert.equal(calls,1);assert.equal(g.apexGridState.delta,null);''')
    def test_entering_native_selection_callback_cannot_publish_to_a_changed_owner(self):
        self.case('''const g=ready(new NativeGrid(1000,0)),old=snapshot(g);g.mGridData.selection.add(54);let calls=0;
g.hooks.selection=()=>{calls++;g.lease.generation++;};g.ApexGridBegin(deltaRequest(g,55));for(let i=0;i<3000&&g.apexGridState.delta;i++)g.ApexGridStep(1,0);
same(g,old);assert.equal(calls,1);assert.equal(g.apexGridState.delta,null);assert.equal(g.mGridView.mouseChildren,false);''')
    def test_native_resize_throw_is_never_replayed_and_restores_full_held_coordinates(self):
        self.case('''const g=ready(new NativeGrid(1000,0)),old=snapshot(g),sentinel={original:'resize throw'};let calls=0;g.hooks.resize=()=>{calls++;throw sentinel;};
g.ApexGridBegin(deltaRequest(g,55));let caught=null;for(let i=0;i<3000&&!caught;i++){try{g.ApexGridStep(1,0);}catch(e){caught=e;}}
assert.equal(caught,sentinel);assert.equal(calls,1);same(g,old);assert.equal(g.apexGridState.delta,null);''')


if __name__=='__main__':unittest.main()
