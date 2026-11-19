"""Execute original and private frame APIs; no game/profile/process access."""
from pathlib import Path
from types import SimpleNamespace
import copy,hashlib,os,sys,unittest,re,subprocess
H=Path(__file__).resolve().parents[1];R=next(p for p in(H,*H.parents)if(p/'tools/dbpf_build.py').is_file())
PARENT=Path(os.environ.get('APEX_LOGICAL_BANK_SOURCE_ROOT',R))
sys.path[:0]=[str(H/'tools'),str(PARENT/'tools'),str(R/'tools'),str(R/'tests')]
import cas_frame_status_stage as stage,cas_grid_pool as pool,test_cas_grid_spares as fixture

BOOT='''
const projection=s=>({measurement_ready:s.measurement_ready,natural_width:s.natural_width,natural_height:s.natural_height,natural_aspect:s.natural_aspect,measured_scale:s.measured_scale,measured_height:s.measured_height});
const fields=['measuredHeight','measuredAspect','measuredGeneration','measuredScale','measuredRevision','measuredClass'];
const saved=s=>Object.fromEntries(fields.map(k=>[k,s[k]]));
const work=g=>{const s=g.apexGridState,j=s.job;return {phase:j.phase,generation:j.generation,revision:j.revision,target:j.target,index:j.index,dirty:j.dirty,cancelled:j.cancelled,coalesced:j.coalesced,desired:j.desired?.signature,reason:j.reason,pendingCell:j.pendingCell!=null,lease:j.lease,operations:j.operations,publishes:j.publishes,measurement:saved(s)};};
'''

class FrameStatusTests(unittest.TestCase):
 def case(self,body):
  original=fixture.stage
  try:
   fixture.stage=SimpleNamespace(helpers=lambda:stage.helpers().replace('public final function','public function'),previous=original.previous)
   fixture.SpareTests.case(self,BOOT+body)
  finally:fixture.stage=original
 def test_existing_public_begin_status_step_and_input_are_source_exact(self):
  before=stage.previous.stage.helpers();after=stage.helpers()
  for name in('ApexGridBegin','ApexGridStatus','ApexGridStep','ApexGridNativeGuard','ApexGridFreshInput','ApexGridBind','ApexGridReady'):
   x,y=pool.method_extent(before,name);a,b=pool.method_extent(after,name);self.assertEqual(after[a:b],before[x:y],name)
 def test_measurement_expiry_condition_and_mutations_are_factored_without_change(self):
  before=stage.previous.stage.helpers();x,y=pool.method_extent(before,'ApexGridMetrics');m=before[x:y];start=m.index('         if(s.owner==null');end=m.index('         result.measured_height',start)
  after=stage.helpers();a,b=pool.method_extent(after,'ApexGridExpireMeasurement');self.assertIn(m[start:end],after[a:b])
  a,b=pool.method_extent(after,'ApexGridMetrics');self.assertEqual(after[a:b].replace('         ApexGridExpireMeasurement(s);\n',m[start:end]),m)
 def test_valid_geometry_projection_and_every_expiry_fence_match_full_status(self):
  mutations=['','s.owner=null;','s.owner.active=false;','s.owner.generation++;','s.feed={};','s.view={};','s.measuredRevision--;','s.measuredClass=class Other{};','s.request.scale+=.01;']
  for mutation in mutations:
   self.case("const g=ready(new NativeGrid(1000,0)),s=g.apexGridState;"+mutation+"const before=saved(s),full=g.ApexGridStatus(),expected=saved(s);Object.assign(s,before);const scalar=g.ApexGridGeometryFrame();assert.deepEqual(scalar,projection(full));assert.deepEqual(saved(s),expected);")
 def test_pending_boolean_matches_fresh_original_status_for_all_phases_and_exact_booleans(self):
  self.case("const g=ready(new NativeGrid(1000,0)),j=g.apexGridState.job;for(const phase of['done','acquire','configure','capacity','position','bind','selection','textures','publish','cancel','cancelled'])for(const dirty of[false,true,'true'])for(const cancelled of[false,true]){j.phase=phase;j.dirty=dirty;j.cancelled=cancelled;const full=g.ApexGridStatus();assert.equal(g.ApexGridPendingFrame(),full==null||full.phase!=='done'||full.dirty===true||full.cancelled===true);}g.apexGridState.job=null;assert.equal(g.ApexGridPendingFrame(),true);assert.equal(g.ApexGridGeometryFrame(),null);g.apexGridState=null;assert.equal(g.ApexGridPendingFrame(),true);assert.equal(g.ApexGridGeometryFrame(),null);")
 def test_frame_pending_and_geometry_preserve_original_vector_invariant_failure(self):
  self.case("const g=ready(new NativeGrid(1000,0));g.mCellsY.pop();for(const method of['ApexGridStatus','ApexGridPendingFrame','ApexGridGeometryFrame']){let e;try{g[method]();}catch(value){e=value;}assert.match(String(e),/Native grid arrays diverged/);}")
 def test_no_readback_begin_repeats_full_work_and_effects_for_initial_and_existing_owner(self):
  for initial in (True,False):
   self.case("const a="+("new NativeGrid(1000,0)"if initial else"ready(new NativeGrid(1000,0))")+",b="+("new NativeGrid(1000,0)"if initial else"ready(new NativeGrid(1000,0))")+";a.ApexGridBegin(deltaRequest(a,0,{width:41}));b.ApexGridBeginFrame(deltaRequest(b,0,{width:41}));assert.deepEqual(work(a),work(b));assert.equal(steps(a).phase,'done');assert.equal(steps(b).phase,'done');assert.deepEqual(rendered(a),rendered(b));assert.deepEqual(counters(a),counters(b));")
 def test_begin_frame_does_not_bypass_validation_or_change_thrown_value(self):
  self.case("for(const method of['ApexGridBegin','ApexGridBeginFrame']){const g=new NativeGrid(100,0),r=deltaRequest(g),sentinel={exact:'validator'};let calls=0;r.validate=()=>{calls++;throw sentinel;};let caught;try{g[method](r);}catch(e){caught=e;}assert.equal(caught,sentinel);assert.equal(calls,1);assert.equal(g.apexGridState,null);}")
 def test_unchanged_owner_fast_return_preserves_coalescing_and_status_expiry_without_graph(self):
  self.case("const a=ready(new NativeGrid(1000,0)),b=ready(new NativeGrid(1000,0));a.ApexGridBegin(deltaRequest(a));b.ApexGridBeginFrame(deltaRequest(b));assert.deepEqual(work(a),work(b));")
 def test_real_frame_four_full_graphs_become_one_graph_and_one_six_scalar_projection(self):
  self.case("const a=ready(new NativeGrid(1000,0)),b=ready(new NativeGrid(1000,0));for(const g of[a,b]){g.graphs=0;const original=g.ApexTxnStatus;g.ApexTxnStatus=function(...args){this.graphs++;return original.apply(this,args);};}const ra=deltaRequest(a,0,{width:41}),rb=deltaRequest(b,0,{width:41});a.ApexGridStatus();a.ApexGridStatus();a.ApexGridBegin(ra);a.ApexGridStep(1,0);const geometry=b.ApexGridGeometryFrame();b.ApexGridPendingFrame();b.ApexGridBeginFrame(rb);b.ApexGridStep(1,0);assert.equal(a.graphs,4);assert.equal(b.graphs,1);assert.equal(Object.keys(geometry).length,6);assert.deepEqual(work(a),work(b));")
 def test_metrics_and_public_status_still_return_detached_full_schema(self):
  self.case("const g=ready(new NativeGrid(1000,0)),a=g.ApexGridStatus(),b=g.ApexGridStatus();assert.notEqual(a,b);assert.notEqual(a.counts,b.counts);assert.notEqual(a.maxMS,b.maxMS);assert.notEqual(a.native_event_kinds,b.native_event_kinds);a.counts.draw=-1;assert.notEqual(g.ApexGridStatus().counts.draw,-1);")
 def test_idle_two_full_graphs_become_only_six_scalar_projection(self):
  self.case("const g=ready(new NativeGrid(1000,0));let calls=0;const original=g.ApexTxnStatus;g.ApexTxnStatus=function(...args){calls++;return original.apply(this,args);};g.ApexGridStatus();g.ApexGridStatus();assert.equal(calls,2);calls=0;g.ApexGridGeometryFrame();g.ApexGridPendingFrame();assert.equal(calls,0);")
 def test_native_runtime_gate_rejects_unknown_classes_and_partial_api(self):
  raw=stage.extend_main('\n'.join((R/'Source/CASUi'/name).read_text()for name in('catalog_workflow_methods.as','catalog_grid_geometry_methods.as'))+'\n'+self.pending())
  a,b=pool.method_extent(raw,'ApexCatalogFrameStatusAvailable');fn=raw[a:b]
  fn=re.sub(r'private function ApexCatalogFrameStatusAvailable\(grid:Object\)\s*:\s*Boolean','function available(grid)',fn)
  fn=re.sub(r'var (\w+):String',r'var \1',fn).replace(' is Function',' instanceof Function')
  script="const assert=require('assert/strict');const flash={utils:{getQualifiedClassName:g=>g.class_name}};"+fn+";const g={class_name:'olympus.layout::SelectableRecyclingGridLayout',ApexGridBeginFrame(){},ApexGridPendingFrame(){},ApexGridGeometryFrame(){}};assert.equal(available(g),true);g.class_name='custom::SameAPIs';assert.equal(available(g),false);g.class_name='olympus.layout::RecyclingGridLayout';delete g.ApexGridGeometryFrame;assert.equal(available(g),false);assert.equal(available(null),false);"
  r=subprocess.run(['node','-'],input=script,text=True,capture_output=True,timeout=10);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def pending(self):
  raw=(R/'Source/CASUi/catalog_grid_transaction_methods.as').read_text();a,b=pool.method_extent(raw,'ApexCatalogGridPending');return raw[a:b]
 def test_main_transform_retains_all_original_error_finally_and_unknown_fallbacks(self):
  source='\n'.join((R/name).read_text()for name in('Source/CASUi/catalog_workflow_methods.as','Source/CASUi/catalog_grid_transaction_methods.as','Source/CASUi/catalog_grid_geometry_methods.as'))
  # Select each actual current implementation once, avoiding older frozen copies
  # of Frame inside the shared source fragments.
  pieces=[]
  for name,file in(('ApexCatalogGridFrame','catalog_workflow_methods.as'),('ApexCatalogGridPending','catalog_grid_transaction_methods.as'),('ApexCardIncrementalApply','catalog_grid_geometry_methods.as')):
   raw=(R/'Source/CASUi'/file).read_text();a,b=pool.method_extent(raw,name);pieces.append(raw[a:b])
  source='\n'.join(pieces);changed=stage.extend_main(source)
  a,b=pool.method_extent(changed,'ApexCatalogGridFrame');x,y=pool.method_extent(source,'ApexCatalogGridFrame')
  old=source[x:y];new=changed[a:b];self.assertEqual(new[new.index('} catch(error:Error)'):],old[old.index('} catch(error:Error)'):])
  self.assertIn('else s.last=s.grid.ApexGridBegin(request);',new);self.assertIn(': grid.ApexGridStatus();',changed)
  a,b=pool.method_extent(changed,'ApexCatalogGridPending');self.assertIn('var status:Object=grid.ApexGridStatus();',changed[a:b])

if __name__=='__main__':unittest.main()
