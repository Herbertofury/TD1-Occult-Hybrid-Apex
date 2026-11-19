"""Executing newest-only wheel queue and bounded fresh-lease cleanup fixtures."""
from pathlib import Path
import sys,unittest
H=Path(__file__).resolve().parents[1];sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_cas_grid_row_delta as base

class CoalescingTests(unittest.TestCase):
    case=base.DeltaTests.case
    def test_hundred_pending_wheel_events_only_replace_primitive_request_no_native_callbacks_or_display_writes(self):
        self.case('''const g=ready(new NativeGrid(1000,0)),old=snapshot(g);g.delayImages=true;g.ApexGridBegin(deltaRequest(g,55));
for(let i=0;i<3000&&g.apexGridState.delta.phase!=='textures';i++)g.ApexGridStep(1,0);
let wheel=false,reads=0;const count=g.GetNumItems,lookup=g.GetDataAtIndex,valid=g.apexGridState.validate;
g.GetNumItems=function(){assert.equal(wheel,false,'no provider count in pending callback');reads++;return count.call(g);};
g.GetDataAtIndex=function(i){assert.equal(wheel,false);return lookup.call(g,i);};g.apexGridState.validate=o=>{assert.equal(wheel,false);return valid(o);};
const draft=g.apexGridState.delta,cells=draft.cells,spares=draft.oldSpare,calls=g.calls.length;
for(let i=0;i<100;i++){wheel=true;g.ApexGridNativeGuard('scroll',{mRect:{y:-(60+i*.5)}});wheel=false;assert.equal(g.apexGridState.delta,draft);assert.equal(draft.cells,cells);assert.equal(draft.oldSpare,spares);assert.equal(g.apexGridState.job.dirty,false);}
assert.equal(reads,0);assert.equal(g.calls.length,calls);same(g,old);assert.equal(draft.latest.scrollY,109.5);
g.delayImages=false;assert.equal(steps(g).phase,'done');assert.equal(g.apexGridState.job.plan.scrollY,109.5);assert.equal(g.mCellIndexToDataIndexMap[0],6);''')
    def test_continuous_newer_rows_replan_from_committed_bank_without_full_redraw(self):
        self.case('''const g=ready(new NativeGrid(1000,0)),old=snapshot(g),before=counters(g);g.delayImages=true;g.ApexGridBegin(deltaRequest(g,55));
for(let i=0;i<3000&&g.apexGridState.delta.phase!=='textures';i++)g.ApexGridStep(1,0);
for(const raw of[110,115.25,120.5,165.75]){g.ApexGridNativeGuard('scroll',{mRect:{y:-raw}});for(let i=0;i<3;i++){g.ApexGridStep(1,0);same(g,old);}}
g.delayImages=false;assert.equal(steps(g).phase,'done');assert.equal(g.apexGridState.job.plan.scrollY,165.75);assert.equal(g.mCellIndexToDataIndexMap[0],18);
assert.ok(counters(g).draw-before.draw<54,'no repeated full-bank Draw');assert.ok(g.apexGridState.job.deltaRetargets>=1);assert.deepEqual(g.mCells.slice(0,36),old.cells.slice(18));''')
    def test_cleanup_reuses_attached_hidden_widgets_and_one_step_per_used_spare_or_created_widget(self):
        self.case('''const g=ready(new NativeGrid(1000,0)),old=snapshot(g);g.delayImages=true;g.ApexGridBegin(deltaRequest(g,55));
for(let i=0;i<3000&&g.apexGridState.delta.phase!=='textures';i++)g.ApexGridStep(1,0);const discarded=g.apexGridState.delta,newEpoch=discarded.newGeneration;
g.ApexGridNativeGuard('scroll',{mRect:{y:-110}});let stepsTaken=0;
while(g.apexGridState.delta===discarded){const calls=g.calls.length;g.ApexGridStep(1,0);same(g,old);assert.equal(g.calls.length,calls,'cleanup does not Draw/attach/lookup');assert.ok(++stepsTaken<100);}
assert.ok(stepsTaken>=discarded.created.length);assert.equal(g.apexGridState.delta.oldCells,old.cells.length?discarded.oldCells:null);assert.ok(g.apexGridState.delta.newGeneration>newEpoch);
const construct=g.calls.filter(c=>c==='construct').length;g.delayImages=false;assert.equal(steps(g).phase,'done');assert.equal(g.calls.filter(c=>c==='construct').length-construct,6);
assert.equal(new Set(g.mCells).size,54);assert.ok(g.apexGridState.presentation.spareCells.every(c=>!g.mCells.includes(c)&&!c.visible));''')
    def test_new_request_during_original_resize_queues_next_ready_delta_instead_of_rolling_back_current_commit(self):
        self.case('''const g=ready(new NativeGrid(1000,0)),before=counters(g);let calls=0;g.hooks.resize=()=>{calls++;if(calls===1){const n=g.calls.length;g.ApexGridNativeGuard('scroll',{mRect:{y:-110.125}});assert.equal(g.calls.length,n);assert.equal(g.apexGridState.job.dirty,false);}};
g.ApexGridBegin(deltaRequest(g,55));assert.equal(steps(g).phase,'done');assert.equal(calls,2);assert.equal(g.apexGridState.job.plan.scrollY,110.125);assert.equal(g.mCellIndexToDataIndexMap[0],12);assert.equal(counters(g).draw-before.draw,12);assert.equal(g.mGridView.mouseChildren,true);''')
    def test_retarget_back_to_same_committed_row_moves_only_after_ready_no_full_draw(self):
        self.case('''const g=ready(new NativeGrid(1000,0)),old=snapshot(g),before=counters(g);g.delayImages=true;g.ApexGridBegin(deltaRequest(g,55));
for(let i=0;i<3000&&g.apexGridState.delta.phase!=='textures';i++)g.ApexGridStep(1,0);g.ApexGridNativeGuard('scroll',{mRect:{y:-1.25}});g.delayImages=false;assert.equal(steps(g).phase,'done');
assert.deepEqual(g.mCells,old.cells);assert.equal(g.apexGridState.job.plan.scrollY,1.25);assert.equal(counters(g).draw-before.draw,6,'only the abandoned entering row was drawn');assert.deepEqual(g.mCells.map(c=>c.y),old.ys.map(y=>y-1.25));''')
    def test_return_to_exact_committed_raw_origin_is_not_lost_by_old_plan_scroll_echo_check(self):
        self.case('''const g=ready(new NativeGrid(1000,0)),old=snapshot(g),before=counters(g);g.delayImages=true;g.ApexGridBegin(deltaRequest(g,55));
for(let i=0;i<3000&&g.apexGridState.delta.phase!=='textures';i++)g.ApexGridStep(1,0);g.ApexGridNativeGuard('scroll',{mRect:{y:0}});assert.ok(g.apexGridState.delta.latest.scrollY===0);
g.delayImages=false;assert.equal(steps(g).phase,'done');same(g,old);assert.equal(g.apexGridState.job.plan.scrollY,0);assert.equal(counters(g).draw-before.draw,6);''')
    def test_newest_input_while_cleanup_runs_wins_without_second_cleanup_or_stale_publish(self):
        self.case('''const g=ready(new NativeGrid(1000,0)),old=snapshot(g);g.delayImages=true;g.ApexGridBegin(deltaRequest(g,55));
for(let i=0;i<3000&&g.apexGridState.delta.phase!=='textures';i++)g.ApexGridStep(1,0);g.ApexGridNativeGuard('scroll',{mRect:{y:-110}});g.ApexGridStep(1,0);
assert.equal(g.apexGridState.delta.cleaning,true);g.ApexGridNativeGuard('scroll',{mRect:{y:-165.5}});g.ApexGridNativeGuard('scroll',{mRect:{y:-220.75}});same(g,old);g.delayImages=false;assert.equal(steps(g).phase,'done');assert.equal(g.apexGridState.job.plan.scrollY,220.75);assert.equal(g.mCellIndexToDataIndexMap[0],24);''')
    def test_same_target_after_a_newer_request_cancels_only_the_pending_retarget(self):
        self.case('''const g=ready(new NativeGrid(1000,0));g.delayImages=true;g.ApexGridBegin(deltaRequest(g,55));g.ApexGridStep(1,0);const draft=g.apexGridState.delta;
g.ApexGridNativeGuard('scroll',{mRect:{y:-110}});assert.ok(draft.latest);g.ApexGridNativeGuard('scroll',{mRect:{y:-55}});assert.equal(draft.latest,null);g.delayImages=false;assert.equal(steps(g).phase,'done');assert.equal(g.apexGridState.job.plan.scrollY,55);assert.equal(g.apexGridState.job.deltaRetargets,undefined);''')
    def test_source_revision_during_cleanup_uses_original_full_fallback_without_duplicate_spares(self):
        self.case('''const g=ready(new NativeGrid(1000,0)),old=snapshot(g);g.delayImages=true;g.ApexGridBegin(deltaRequest(g,55));
for(let i=0;i<3000&&g.apexGridState.delta.phase!=='textures';i++)g.ApexGridStep(1,0);g.ApexGridNativeGuard('scroll',{mRect:{y:-110}});
for(let i=0;i<5;i++)g.ApexGridStep(1,0);g.ApexGridNativeGuard('update',{currentTarget:g.mGridData});g.ApexGridStep(1,0);same(g,old);
assert.equal(new Set(g.apexGridState.presentation.spareCells).size,g.apexGridState.presentation.spareCells.length);g.delayImages=false;assert.equal(steps(g).phase,'done');assert.equal(g.mCellIndexToDataIndexMap[0],12);''')
    def test_pending_unattached_factory_widget_is_discarded_once_before_retarget(self):
        self.case('''const g=ready(new NativeGrid(1000,0)),old=snapshot(g);g.ApexGridBegin(deltaRequest(g,55));
for(let i=0;i<3000&&g.apexGridState.delta.phase!=='attach';i++)g.ApexGridStep(1,0);const pending=g.apexGridState.job.pendingCell;assert.equal(pending.parent,null);
g.ApexGridNativeGuard('scroll',{mRect:{y:-110}});assert.equal(steps(g).phase,'done');assert.equal(pending.parent,null);assert.equal(g.apexGridState.intrinsics[pending],undefined);assert.equal(g.apexGridState.job.pendingCell,null);assert.equal(g.mCellIndexToDataIndexMap[0],12);''')
    def test_owner_loss_during_cleanup_refuses_and_never_publishes_the_new_request(self):
        self.case('''const g=ready(new NativeGrid(1000,0)),old=snapshot(g),published=g.apexGridState.job.publishes;g.delayImages=true;g.ApexGridBegin(deltaRequest(g,55));
for(let i=0;i<3000&&g.apexGridState.delta.phase!=='textures';i++)g.ApexGridStep(1,0);g.ApexGridNativeGuard('scroll',{mRect:{y:-110}});g.ApexGridStep(1,0);g.lease.active=false;g.ApexGridStep(1,0);same(g,old);assert.equal(g.apexGridState.job.publishes,published);assert.equal(g.mGridView.mouseChildren,false);''')

if __name__=='__main__':unittest.main()
