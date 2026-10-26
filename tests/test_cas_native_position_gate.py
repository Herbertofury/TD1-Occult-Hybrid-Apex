"""Execute the actual native override bodies with current provider helpers."""
from pathlib import Path
import importlib.util,re,sys,unittest
from types import SimpleNamespace
H=Path(__file__).resolve().parents[1];R=next(p for p in(H,*H.parents)if(p/'tools/dbpf_build.py').is_file())
sys.path[:0]=[str(H/'tools'),str(R/'tools'),str(R/'tests')]
import cas_grid_position_stage as stage,cas_grid_pool as pool
import test_cas_grid_spares as fixture
ORIGINAL='''override public function PositionCells() : void
      {
         super.PositionCells();
         this.UpdateSelectionInCells();
      }'''

def override_js(source):
    start,end=pool.method_extent(source,'PositionCells');body=source[start:end]
    body=body.replace('if(ApexGridNativeGuard(', 'if(this.ApexGridNativeGuard(').replace('public function PositionCells() : void','function PositionCells()').replace('super.PositionCells();','nativeParentPosition.call(this);')
    return body

BOOT='''
function nativeParentPosition(){if(this.ApexGridNativeGuard('position'))return;this.nativeParentCalls++;}
function nativeSelection(){if(this.ApexGridNativeGuard('selection'))return;this.nativeSelectionCalls++;}
function install(g,fn){g.nativeParentCalls=0;g.nativeSelectionCalls=0;g.UpdateSelectionInCells=nativeSelection;g.PositionCells=fn;return g;}
'''

class NativePositionTests(unittest.TestCase):
 def case(self,body,fixed=True):
    source=stage.fragment()if fixed else ORIGINAL
    old=fixture.stage
    try:
        fixture.stage=SimpleNamespace(helpers=stage.helpers,previous=stage.previous)
        fixture.SpareTests.case(self,BOOT+override_js(source)+'\n'+body)
    finally:fixture.stage=old
 def test_original_parent_guard_does_not_stop_override_tail_and_increments_revision_twice(self):
    self.case("const g=install(ready(new NativeGrid(1000,0)),PositionCells),s=g.apexGridState,rev=s.revision;g.PositionCells();g.PositionCells();assert.equal(s.revision,rev+2);assert.equal(g.nativeParentCalls,0);assert.equal(g.nativeSelectionCalls,0);assert.equal(s.job.dirty,true);",False)
 def test_new_override_geometry_coalesces_without_spurious_selection_revision(self):
    self.case("const g=install(ready(new NativeGrid(1000,0)),PositionCells),s=g.apexGridState,rev=s.revision;g.PositionCells();g.PositionCells();assert.equal(s.revision,rev);assert.equal(g.nativeParentCalls,0);assert.equal(g.nativeSelectionCalls,0);assert.equal(s.job.dirty,true);assert.equal(steps(g).phase,'done');")
 def test_direct_selection_refresh_still_invalidates_and_republishes(self):
    self.case("const g=install(ready(new NativeGrid(1000,0)),PositionCells),s=g.apexGridState,rev=s.revision;g.UpdateSelectionInCells();assert.equal(s.revision,rev+1);assert.equal(s.job.dirty,true);assert.equal(steps(g).phase,'done');")
 def test_real_feed_update_then_native_selection_tail_retains_both_invalidations(self):
    self.case("const g=install(ready(new NativeGrid(1000,0)),PositionCells),s=g.apexGridState,rev=s.revision;g.ApexGridNativeGuard('update',{currentTarget:g.mGridData});g.UpdateSelectionInCells();assert.equal(s.revision,rev+2);assert.equal(s.job.dirty,true);assert.equal(steps(g).phase,'done');")
 def test_unarmed_native_position_and_selection_bodies_both_run(self):
    self.case("const g=install(new NativeGrid(10,0),PositionCells);g.PositionCells();assert.equal(g.nativeParentCalls,1);assert.equal(g.nativeSelectionCalls,1);")
 def test_guard_error_is_propagated_once_without_executing_original_tail(self):
    self.case("const g=install(new NativeGrid(10,0),PositionCells),sentinel={exact:'error'};let calls=0;g.ApexGridNativeGuard=function(){calls++;throw sentinel;};let caught;try{g.PositionCells();}catch(e){caught=e;}assert.equal(calls,1);assert.equal(caught,sentinel);assert.equal(g.nativeParentCalls,0);assert.equal(g.nativeSelectionCalls,0);")
 def test_source_admission_rejects_changed_native_body_instead_of_erasing_it(self):
    source='package olympus.layout {public class SelectableRecyclingGridLayout {'+ORIGINAL+'}}'
    self.assertIn('ApexGridNativeGuard("position",null)',stage.inject(source))
    with self.assertRaisesRegex(ValueError,'Exact original'):stage.inject(source.replace('this.UpdateSelectionInCells();','this.UpdateSelectionInCells();sideEffect();'))
 def test_fixed_kind_counts_distinguish_geometry_feed_and_selection(self):
    self.case("const g=install(ready(new NativeGrid(1000,0)),PositionCells),before=g.ApexGridStatus().native_event_kinds;g.PositionCells();g.PositionCells();g.ApexGridNativeGuard('update',{currentTarget:g.mGridData});g.UpdateSelectionInCells();const k=g.ApexGridStatus().native_event_kinds;assert.equal(k.position-before.position,2);assert.equal(k.update-before.update,1);assert.equal(k.selection-before.selection,1);assert.equal(k.last_kind,'selection');assert.equal(Object.keys(k).length,17);assert.ok(Object.entries(k).every(([n,v])=>n==='last_kind'?typeof v==='string':Number.isInteger(v)));assert.ok(JSON.stringify(k).length<1024);")
 def test_saturated_and_unknown_counter_diagnostics_are_bounded_without_changing_error(self):
    self.case("const g=install(ready(new NativeGrid(1000,0)),PositionCells),s=g.apexGridState;s.nativeEvent_position=2147483647;g.PositionCells();assert.equal(s.nativeEvent_position,2147483647);let caught;try{g.ApexGridNativeGuard('x'.repeat(1000000));}catch(e){caught=e;}assert.match(String(caught),/Unknown native grid guard/);const k=g.ApexGridStatus().native_event_kinds;assert.equal(k.unknown,1);assert.equal(k.last_kind,'unknown');assert.ok(JSON.stringify(k).length<1024);")
 def test_unarmed_counter_path_does_no_state_work(self):
    self.case("const g=install(new NativeGrid(10,0),PositionCells);g.PositionCells();assert.equal(g.apexGridState,null);assert.equal(g.nativeParentCalls,1);assert.equal(g.nativeSelectionCalls,1);")
 def test_counter_insert_is_fixed_scalars_only_and_metrics_is_not_a_mutable_alias(self):
    s=stage.helpers();a,b=pool.method_extent(s,'ApexGridNativeGuard');guard=s[a:b]
    begin=guard.index('         switch(kind)');end=guard.index('         if(j==null)',begin);counter=guard[begin:end]
    self.assertNotIn('new ',counter);self.assertNotIn('getTimer',counter);self.assertNotIn('CallGameService',counter);self.assertNotIn('push(',counter)
    self.assertEqual(counter.count('case "'),15);self.assertEqual(counter.count('<int.MAX_VALUE'),16)
    self.case("const g=install(ready(new NativeGrid(1000,0)),PositionCells);g.PositionCells();const old=g.ApexGridStatus().native_event_kinds;old.position=999;assert.equal(g.ApexGridStatus().native_event_kinds.position,1);")

if __name__=='__main__':unittest.main()
