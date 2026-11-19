"""Execute production Main product leases with adversarial native doubles."""
from pathlib import Path
import sys,re,shutil,subprocess,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
import test_cas_main_grid_transaction as original

BOOT='''
class CASCatalogProduct{}
class CASBodyPanelCellView{};class CASFacePanelCellView{};class CASGenericCatalogVariantCellView{};class CASBreedCatalogCellView{};
var mcBodyModPanel=null,mcFaceModPanel=null,mcGenericCatalogPanel=null,mcFeaturedFaceLookPanel=null,mcSkinColorPanel=null;
Object.defineProperty(NativeGrid.prototype,'GetCellView',{get(){return this.cellType||null;}});
const states=new Map();
function panelState(panel,g){return {geometry:{grid:g,panel},layout:{...apexCardLayout},signature:'fit-'+Math.random(),reflow:0};}
function ApexCardStateFor(g){if(g===grid&&!states.has(g))return {geometry:{grid:g,panel:mcClothingPanel},layout:apexCardLayout,signature:apexCatalogSignature};return states.get(g)||null;}
function openProduct(kind,cell){
 let g=new NativeGrid(),panel={stage,visible:true,mcTileList:{mGridLayout:g,mScrollerView:{width:670,height:950},mSlider:{Value:23}}};g.cellType=cell;
 if(kind==='body')mcBodyModPanel=panel;else if(kind==='face')mcFaceModPanel=panel;else if(kind==='generic')mcGenericCatalogPanel=panel;
 states.set(g,panelState(panel,g));mCurrentPanel=panel;return {g,panel};
}
function pumpGrid(g){ApexCatalogGridFrame();for(let i=0;i<12&&g.phase!=='done';i++)ApexCatalogGridFrame();assert.equal(g.phase,'done');}
'''
@unittest.skipUnless(shutil.which('node'),'Node required for actual AS fixture')
class ProductLeaseTests(unittest.TestCase):
 def run_case(self,suffix):
  h=original.MainGridLeaseTests.harness(self);h=h.replace('return item is CASCatalogProduct;','return item instanceof CASCatalogProduct;').replace('grid is SelectableRecyclingGridLayout','grid instanceof NativeGrid');h=re.sub(r'\s+as\s+Class\b','',h)
  at=h.index('function ApexCatalogGridPermit(');h=h[:at]+BOOT+h[at:]
  r=subprocess.run(['node','-'],input=h+suffix,capture_output=True,text=True,timeout=20);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_exact_body_face_and_all_three_generic_cell_classes_bind(self):
  self.run_case('''
ApexCatalogGridBootstrap();pump();
for(const [kind,cell] of [['body',CASBodyPanelCellView],['face',CASFacePanelCellView],['generic',CASGenericCatalogVariantCellView],['generic',CASFacePanelCellView],['generic',CASBreedCatalogCellView]]){
 const {g,panel}=openProduct(kind,cell);pumpGrid(g);assert.equal(apexCatalogGrid.lease.panel,panel);assert.equal(apexCatalogGrid.lease.panel_kind,kind);
 assert.equal(g.request.rowValidate(new CASCatalogProduct()),true);assert.equal(g.request.rowValidate({data_id:'fake',GetVariationOrBaseId(){return 'fake';}}),false);
 assert.equal(g.click(),true);
}
''')
 def test_featured_skin_foreign_and_wrong_cell_classes_never_gain_product_lease(self):
  self.run_case('''
ApexCatalogGridBootstrap();pump();const steps=grid.steps,readsBefore=reads.length;
for(const kind of ['featured','skin','foreign']){
 const p={stage,visible:true,mcTileList:{mGridLayout:new NativeGrid()}};
 if(kind==='featured')mcFeaturedFaceLookPanel=p;if(kind==='skin')mcSkinColorPanel=p;mCurrentPanel=p;
 assert.equal(ApexCatalogGridProductPanel(p),'');ApexCatalogGridFrame();assert.equal(grid.steps,steps);
}
const foreign={stage,visible:true,mcTileList:{mGridLayout:{get GetCellView(){throw Error('foreign getter must not run');}}}};assert.equal(ApexCatalogGridProductPanel(foreign),'');
const bad=openProduct('body',CASFacePanelCellView);assert.equal(ApexCatalogGridProductPanel(bad.panel),'');ApexCatalogGridFrame();assert.equal(bad.g.steps,0);
assert.equal(reads.length,readsBefore);assert.equal(writes,0);
''')
 def test_hidden_known_product_panel_never_polls_or_builds(self):
  self.run_case('''
ApexCatalogGridBootstrap();pump();const {g,panel}=openProduct('body',CASBodyPanelCellView);panel.visible=false;
const before=reads.length;for(let i=0;i<30;i++)ApexCatalogGridFrame();assert.equal(g.steps,0);assert.equal(reads.length,before);
''')
 def test_same_native_grid_cell_class_replacement_invalidates_click_before_rebind(self):
  self.run_case('''
ApexCatalogGridBootstrap();const {g}=openProduct('generic',CASGenericCatalogVariantCellView);pumpGrid(g);assert.equal(g.click(),true);
const before=writes;g.cellType=CASBreedCatalogCellView;assert.equal(g.click(),false);assert.equal(writes,before);pumpGrid(g);assert.equal(g.click(),true);
''')
 def test_selected_member_form_household_and_outfit_staleness_keep_existing_fences(self):
  for change in ["nativeSim.simId='202';","nativeSim.householdId='808';","nativeOwner='ghost/ghost';","nativeGeneration='74';","nativeSlot={outfit_type:3,outfit_index:2};"]:
   with self.subTest(change=change):self.run_case("ApexCatalogGridBootstrap();const {g}=openProduct('body',CASBodyPanelCellView);pumpGrid(g);assert.equal(g.click(),true);const before=writes;"+change+"assert.equal(g.click(),false);assert.equal(writes,before);")
 def test_generic_new_grid_does_not_reuse_retiring_grid_or_feed(self):
  self.run_case('''
ApexCatalogGridBootstrap();let first=openProduct('generic',CASGenericCatalogVariantCellView);pumpGrid(first.g);
let second=openProduct('generic',CASBreedCatalogCellView);pumpGrid(second.g);assert.notEqual(second.g,first.g);assert.equal(apexCatalogGrid.lease.panel,second.panel);assert.equal(first.g.click(),false);
''')
 def test_unknown_cell_and_feed_replacement_refuse_pending_owner(self):
  self.run_case('''
ApexCatalogGridBootstrap();const {g}=openProduct('face',CASFacePanelCellView);pumpGrid(g);g.feed={replaced:true};assert.equal(g.click(),false);pumpGrid(g);assert.equal(g.click(),true);
g.cellType=class ForeignCell{};assert.equal(g.click(),false);const before=g.steps;ApexCatalogGridFrame();assert.equal(g.steps,before);
''')
 def test_product_row_predicate_has_no_side_effects_or_duck_typing(self):
  self.run_case('''
const before=[reads.length,writes,grid.calls.length,nativeExchanges.length];assert.equal(ApexCatalogGridProductRow(new CASCatalogProduct()),true);
assert.equal(ApexCatalogGridProductRow({product:{data_id:'look'},outfit:{data_id:'outfit'}}),false);assert.equal(ApexCatalogGridProductRow({dataID:'color',color:123}),false);assert.equal(ApexCatalogGridProductRow(null),false);
assert.deepEqual([reads.length,writes,grid.calls.length,nativeExchanges.length],before);
''')
if __name__=='__main__':unittest.main()
