"""Product-row validation plus the existing presentation preservation suite."""
from pathlib import Path
import shutil,subprocess,sys,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests')]
import cas_grid_product_rows
import test_cas_grid_presentation as fixture

@unittest.skipUnless(shutil.which('node'),'Node required for actual AS fixture')
class ProductRowTests(fixture.PresentationTests):
 def case(self,code):
  # Preserve the public fixture's global stage outside this one test call.
  with patch.object(fixture,'stage',cas_grid_product_rows):
   fixture.PresentationTests.case(self,code)
 def test_duck_typed_foreign_row_refused_before_identity_method_or_draw(self):
  self.case('''
class CASCatalogProduct{};
const g=new NativeGrid(100,0);g.ApexGridBegin(request(g,6,{viewHeight:400}));bounded(g);
const old=g.mCells.slice(),ids=rendered(g),before=g.calls.filter(x=>x==='draw').length;let accessed=0;
g.mGridData.items[10]={data_id:'fake',body_type:1,menu_state:2,GetVariationOrBaseId(){accessed++;throw Error('identity must not run');}};
g.ApexGridBegin(request(g,6,{viewHeight:400,rowValidate:x=>x instanceof CASCatalogProduct}));
g.ApexGridNativeGuard('update',{currentTarget:g.mGridData});for(let i=0;i<2000&&g.ApexGridStatus().phase!=='cancelled';i++)g.ApexGridStep(64,0);
assert.equal(g.ApexGridStatus().phase,'cancelled');assert.equal(accessed,0);assert.deepEqual(g.mCells,old);assert.deepEqual(rendered(g),ids);assert.equal(g.mGridView.mouseChildren,false);
''')
 def test_actual_product_and_subclass_rows_publish_through_original_draw(self):
  self.case('''
class CASCatalogProduct{};class ModdedProduct extends CASCatalogProduct{};
const g=new NativeGrid(20,0);g.mGridData.items=g.mGridData.items.map((p,i)=>Object.assign(new (i%2?ModdedProduct:CASCatalogProduct)(),p));
g.ApexGridBegin(request(g,6,{viewHeight:400,rowValidate:x=>x instanceof CASCatalogProduct}));assert.equal(bounded(g).phase,'done');
assert.equal(rendered(g).length,20);assert.equal(g.ApexGridPoolViews().length,20);
''')
 def test_type_guard_runs_again_after_selection_callback_replaces_row(self):
  self.case('''
class CASCatalogProduct{};const g=new NativeGrid(20,0);g.mGridData.items=g.mGridData.items.map(p=>Object.assign(new CASCatalogProduct(),p));
g.ApexGridBegin(request(g,6,{viewHeight:400,rowValidate:x=>x instanceof CASCatalogProduct}));bounded(g);
const ids=rendered(g),old=g.mCells.slice();g.mGridData.selection.add(0);let once=true,accessed=0;
g.hooks.selection=()=>{if(once){once=false;g.mGridData.items[0]={data_id:'foreign-after-selection',GetVariationOrBaseId(){accessed++;throw Error('identity must not run');}};}};
g.ApexGridNativeGuard('selection');g.ApexGridNativeGuard('update',{currentTarget:g.mGridData});for(let i=0;i<2000&&g.ApexGridStatus().phase!=='cancelled';i++)g.ApexGridStep(64,0);
assert.equal(g.ApexGridStatus().phase,'cancelled');assert.equal(accessed,0);assert.deepEqual(g.mCells,old);assert.deepEqual(rendered(g),ids);
''')
 def test_row_callback_cannot_bypass_fresh_owner_reentry_fence(self):
  self.case('''
const g=new NativeGrid(20,0);g.ApexGridBegin(request(g,6,{viewHeight:400}));bounded(g);const ids=rendered(g);let invoked=0;
g.ApexGridBegin(request(g,6,{viewHeight:400,rowValidate:x=>{invoked++;g.lease.generation++;return true;}}));
g.ApexGridNativeGuard('update',{currentTarget:g.mGridData});for(let i=0;i<2000&&g.ApexGridStatus().phase!=='cancelled';i++)g.ApexGridStep(64,0);
assert.equal(g.ApexGridStatus().phase,'cancelled');assert.ok(invoked>0);assert.deepEqual(rendered(g),ids);assert.equal(g.mGridView.mouseChildren,false);
''')
 def test_row_callback_throw_or_nonfunction_never_publishes_wrong_mapping(self):
  for callback in ("()=>{throw Error('predicate failure');}","{foreign:true}"):
   with self.subTest(callback=callback):self.case('''
const g=new NativeGrid(20,0);g.ApexGridBegin(request(g,6,{viewHeight:400}));bounded(g);const ids=rendered(g),old=g.mCells.slice();
g.ApexGridBegin(request(g,6,{viewHeight:400,rowValidate:'''+callback+'''}));
g.ApexGridNativeGuard('update',{currentTarget:g.mGridData});for(let i=0;i<2000&&g.ApexGridStatus().phase!=='cancelled';i++)g.ApexGridStep(64,0);
assert.equal(g.ApexGridStatus().phase,'cancelled');assert.deepEqual(rendered(g),ids);assert.deepEqual(g.mCells,old);
''')
if __name__=='__main__':unittest.main()
