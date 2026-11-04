from pathlib import Path
import sys,re,subprocess,unittest
HOME=Path(__file__).resolve().parents[1];ROOT=next(p for p in Path(__file__).resolve().parents if (p/'tools/cas_grid_transaction.py').is_file());sys.path.insert(0,str(ROOT/'tests'))
from test_cas_card_geometry import javascript_function
OLD=ROOT/'Source/CASUi/catalog_grid_transaction_methods.as';NEW=OLD
def functions():
 new=javascript_function('ApexCatalogGridLeaseCurrent','lease',source=NEW).replace('function ApexCatalogGridLeaseCurrent(','function fast(')
 pattern=r'stage==null\)return false;\s*(?://[^\n]*\n\s*)*var panelKind=ApexCatalogGridProductPanel\(lease.panel\);\s*if\(panelKind=="" \|\| lease.panel_kind!==panelKind \|\|'
 replacement='stage==null ||\n            ApexCatalogGridProductPanel(lease.panel)=="" || lease.panel_kind!==ApexCatalogGridProductPanel(lease.panel) ||'
 old,count=re.subn(pattern,lambda match:replacement,new);assert count==1,'Actual Main is missing the reviewed one-classification boundary'
 old=old.replace('function fast(','function slow(')
 product=javascript_function('ApexCatalogGridProductPanel','panel',source=OLD).replace('grid is SelectableRecyclingGridLayout','grid instanceof NativeGrid');product=re.sub(r'\s+as\s+Class','',product);product=re.sub(r'\b([\w.]+) is Function\b',r'(typeof \1==="function")',product)
 product=product.replace('function ApexCatalogGridProductPanel(panel){','function ApexCatalogGridProductPanel(panel){classifications++;')
 return product+old+new
class LeaseTests(unittest.TestCase):
 def case(self,code):
  r=subprocess.run(['node','-'],input=BOOT+functions()+code,capture_output=True,text=True,timeout=10);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_same_valid_body_context_halves_classifier_calls_without_omitting_final_accessors(self):
  self.case("fresh();assert.equal(slow(lease),true);assert.equal(classifications,2);assert.equal(feedReads,3);assert.equal(cellReads,3);classifications=feedReads=cellReads=0;assert.equal(fast(lease),true);assert.equal(classifications,1);assert.equal(feedReads,2);assert.equal(cellReads,2);")
 def test_all_original_scalar_and_structural_refusals_are_preserved(self):
  mutations=["apexCatalogGrid.enabled=false","apexCatalogGrid.disposed=true","lease.active=false","lease.generation++","lease.root={}","lease.stage={}","stage=null","panel.stage={}","panel.mcTileList=null","panel.mcTileList.mGridLayout={}","lease.grid={}","apexCatalogGrid.grid={}","grid.feed=null","grid.feed={}","grid.cell=CASBreedCatalogCellView","lease.panel_kind='face'","lease.phase='unknown'","mCurrentPanel={}","panel.visible=false","mCurrSimInfo=null","mCurrSimInfo.simId='202'","mCurrSimInfo.householdId='808'","mCurrSimInfo.occultLayer=0","mCurrSimInfo.occultType=4","mCurrSimInfo.allOccultTypes=3","apexBoundSim='202'","apexFormsSelectedId='vampire/dark'","apexOwnerSession++","apexFormsNativeGeneration='74'","apexFormsNativeState='waiting'","apexFormsDesiredId='vampire/dark'","apexFormsIntent={}","apexFormsNativeIntent={}","apexMoleculeIntent={}","apexPairIntent={}","apexFormsApplying=true","mCurrState++","apexCatalogDisplayFaults={};quarantined=true"]
  for mutation in mutations:
   with self.subTest(mutation=mutation):self.case("fresh();"+mutation+";assert.equal(slow(lease),false);assert.equal(fast(lease),false);")
 def test_every_existing_admitted_product_panel_and_generic_cell_schema_is_preserved(self):
  setups=["", "mcBodyModPanel={};mcFaceModPanel=panel;grid.cell=lease.cell_type=CASFacePanelCellView;lease.panel_kind='face'", "mcBodyModPanel={};mcClothingPanel=panel;lease.panel_kind='clothing'"]
  setups += ["mcBodyModPanel={};mcGenericCatalogPanel=panel;lease.panel_kind='generic';grid.cell=lease.cell_type="+name for name in ['CASGenericCatalogVariantCellView','CASFacePanelCellView','CASBreedCatalogCellView']]
  for setup in setups:
   with self.subTest(setup=setup):self.case("fresh();"+setup+";assert.equal(slow(lease),true);assert.equal(fast(lease),true);")
 def test_null_or_foreign_lease_never_classifies_a_panel(self):
  self.case("fresh();assert.equal(fast(null),false);assert.equal(fast({...lease}),false);assert.equal(classifications,0);")
 def test_bootstrap_remains_structural_only_and_new_function_never_invokes_game_or_clock(self):
  self.case("fresh();lease.phase='bootstrap';mCurrSimInfo=null;apexFormsNativeState='waiting';assert.equal(slow(lease),true);assert.equal(fast(lease),true);")
  body=NEW.read_text().split('private function ApexCatalogGridLeaseCurrent(',1)[1].split('private function ApexCatalogGridValidate(',1)[0]
  for forbidden in ['CallGameService','ApexNativeExchange','getTimer','new ','ApexGridStep','Draw(']:self.assertNotIn(forbidden,body)
 def test_lease_is_rechecked_after_context_changes_without_cross_call_reuse(self):
  self.case("fresh();assert.equal(fast(lease),true);mCurrSimInfo.simId='202';assert.equal(fast(lease),false);mCurrSimInfo.simId='101';assert.equal(fast(lease),true);grid.feed={};assert.equal(fast(lease),false);")
BOOT="""
const assert=require('node:assert/strict');function int(v){return v|0;}
class CASBodyPanelCellView{}class CASFacePanelCellView{}class CASGenericCatalogVariantCellView{}class CASBreedCatalogCellView{}
class NativeGrid{GetDataFeed(){feedReads++;return this.feed;}get GetCellView(){cellReads++;return this.cell;}}
let classifications=0,feedReads=0,cellReads=0,quarantined=false,stage,grid,feed,panel,lease,apexCatalogGrid,mCurrentPanel,mCurrSimInfo;
let mcClothingPanel,mcBodyModPanel,mcFaceModPanel,mcGenericCatalogPanel;
let apexBoundSim,apexFormsSelectedId,apexOwnerSession,apexFormsNativeGeneration,apexFormsNativeState,apexFormsDesiredId,apexFormsIntent,apexFormsNativeIntent,apexMoleculeIntent,apexPairIntent,apexFormsApplying,mCurrState,apexCatalogDisplayFaults;
function ApexCatalogDisplayFaulted(){return quarantined;}
function fresh(){classifications=feedReads=cellReads=0;quarantined=false;stage={};feed={};grid=new NativeGrid();grid.feed=feed;grid.cell=CASBodyPanelCellView;
panel={stage,visible:true,mcTileList:{mGridLayout:grid}};mcClothingPanel={};mcBodyModPanel=panel;mcFaceModPanel={};mcGenericCatalogPanel={};mCurrentPanel=panel;
mCurrSimInfo={simId:'101',householdId:'909',occultLayer:1,occultType:2,allOccultTypes:127};apexBoundSim='101';apexFormsSelectedId='alien/alien';apexOwnerSession=3;apexFormsNativeGeneration='73';apexFormsNativeState='bound';apexFormsDesiredId='';apexFormsIntent=apexFormsNativeIntent=apexMoleculeIntent=apexPairIntent=null;apexFormsApplying=false;mCurrState=40;apexCatalogDisplayFaults=null;
lease={active:true,generation:2,root:globalThis,stage,panel,grid,feed,cell_type:CASBodyPanelCellView,panel_kind:'body',phase:'bound',sim_id:'101',household_id:'909',layer:1,native_kind:2,native_mask:127,owner:'alien/alien',session:3,native_generation:'73',state:40};apexCatalogGrid={enabled:true,disposed:false,lease,grid,generation:2};}
"""
if __name__=='__main__':unittest.main()
