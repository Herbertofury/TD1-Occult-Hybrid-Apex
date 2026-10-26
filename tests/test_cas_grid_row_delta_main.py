"""Execute the actual compiled-source Main capability producer."""
from pathlib import Path
import os,re,subprocess,sys,unittest
H=Path(__file__).resolve().parents[1];R=next(p for p in (H,*H.parents) if(p/'tools/dbpf_build.py').is_file())
sys.path[:0]=[str(H/'tools'),str(R/'tools')]
import cas_row_delta_stage as stage
import cas_grid_row_delta as portable
def base_source():
    prefix=portable.presentation.ROOT
    imports='\n'.join('   import widgets.CAS.controls.'+n+';'for n in('CASClothingPanelCellViewMain','CASClothingPanelCellViewCommon','CASClothingPanelCellViewSkinSpecularity','CASBodyPanelCellView','CASFacePanelCellView','CASGenericCatalogVariantCellView','CASBreedCatalogCellView'))
    return 'package widgets.CAS.Customizer {\n'+imports+'\n   public class CASCustomizerMain {\n'+(prefix/'Source/CASUi/catalog_grid_transaction_methods.as').read_text()+'\n'+(prefix/'Source/CASUi/catalog_trace_methods.as').read_text()+'\n   }\n}\n'
def request_source():
    text=portable.inject_main(base_source());a,b=stage.pool.method_extent(text,'ApexCatalogGridRequest');text=text[a:b]
    text=re.sub(r'private function ApexCatalogGridRequest\(lease:Object\)\s*:\s*Object','function request(lease)',text)
    return re.sub(r'\b(var\s+\w+)\s*:\s*[\w.*<>]+',r'\1',text)
BOOT='''const assert=require('node:assert/strict');const int=n=>n|0;
const CASClothingPanelCellViewMain=class{},CASClothingPanelCellViewCommon=class{},CASClothingPanelCellViewSkinSpecularity=class{},
CASBodyPanelCellView=class{},CASFacePanelCellView=class{},CASGenericCatalogVariantCellView=class{},CASBreedCatalogCellView=class{},CASFeaturedFacelookCellView=class{};
let apexCatalogTrace=null,CASCustomizerMain={};const ApexCatalogGridProductRow=()=>true,ApexCatalogGridFeaturedIdentity=()=>null;
const ApexCatalogGridValidate=()=>true,ApexCatalogGridInput=()=>true;
let retained=null,current=null;
function ApexCatalogGridLeaseCurrent(lease){return lease===current&&lease.active===true;}
function ApexCardStateFor(){return retained;}
function fixture(type=CASClothingPanelCellViewCommon,kind='clothing',bootstrap=false){
 const grid={GetCellPadding(){return{mTop:3,mLeft:2};}},panel={mcTileList:{mScrollerView:{width:500,height:400},mSlider:{Value:55.125}}};
 current={phase:'bound',active:true,cell_type:type,panel_kind:kind,grid,panel};
 retained=bootstrap?null:{geometry:{grid,panel},layout:{scale:.35,card_width:38,card_height:51,columns:6,gap_x:4,gap_y:4}};
 return current;
}
'''
class MainTests(unittest.TestCase):
    def case(self,code):
        p=subprocess.run(['node','-'],input=BOOT+request_source()+code,capture_output=True,text=True,timeout=15)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
    def test_every_exact_native_product_class_has_a_real_enabled_main_producer(self):
        self.case('''for(const [type,kind]of[[CASClothingPanelCellViewMain,'clothing'],[CASClothingPanelCellViewCommon,'clothing'],[CASClothingPanelCellViewSkinSpecularity,'clothing'],[CASBodyPanelCellView,'body'],[CASFacePanelCellView,'face'],[CASGenericCatalogVariantCellView,'generic'],[CASBreedCatalogCellView,'generic']]){
for(const bootstrap of[false,true]){const lease=fixture(type,kind,bootstrap),r=request(lease);assert.equal(r.rowDeltaReuseContract,1);assert.equal(r.rowDeltaFeedbackContract,'ea-complete-ready-before-resize-v1');assert.equal(r.rowDeltaRowValidate,ApexCatalogGridProductRow);assert.equal(r.bootstrap,bootstrap);}}''')
    def test_unknown_subclass_featured_skin_foreign_and_unbound_are_never_admitted(self):
        self.case('''for(const [type,kind]of[[class extends CASBodyPanelCellView{},'body'],[CASFeaturedFacelookCellView,'featured'],[CASBodyPanelCellView,'skin'],[class{},'clothing']]){
const lease=fixture(type,kind),r=request(lease);assert.equal(r.rowDeltaReuseContract,0);assert.equal(r.rowDeltaRowValidate,null);}
let lease=fixture();lease.active=false;assert.equal(request(lease),null);lease=fixture();lease.phase='bootstrap';assert.equal(request(lease),null);assert.equal(request({...lease}),null);''')
    def test_existing_geometry_native_lease_and_callbacks_are_retained(self):
        self.case('''const lease=fixture(),r=request(lease);assert.equal(r.width,38);assert.equal(r.height,51);assert.equal(r.columns,6);assert.equal(r.scrollY,55.125);assert.equal(r.owner,lease);assert.equal(r.panel,lease.panel);assert.equal(r.validate,ApexCatalogGridValidate);assert.equal(r.inputValidate,ApexCatalogGridInput);assert.equal(r.scrollOnlyPositionContract,1);assert.equal(r.stepBudgetClockContract,1);assert.equal(r.stepBudgetMilliseconds,1);assert.equal(r.publicationTraceStep,null);
lease.panel.mcTileList.mScrollerView.width=NaN;assert.equal(request(lease),null);''')
    def test_main_changes_only_the_exact_owned_capability_producer(self):
        base=portable.publication.inject_main(base_source());made=stage.extend_main(base)
        a,b=stage.pool.method_extent(base,'ApexCatalogGridRequest');x,y=stage.pool.method_extent(made,'ApexCatalogGridRequest')
        self.assertEqual(base[:a],made[:x]);self.assertEqual(base[b:],made[y:])
        if os.environ.get('APEX_CAS_ROW_DELTA_FIXTURE'):
            text=(Path(os.environ['APEX_CAS_ROW_DELTA_FIXTURE'])/'main/CASCustomizerMain.as').read_text();i,j=stage.pool.method_extent(text,'ApexCatalogGridRequest')
            self.assertEqual(text[i:j],made[x:y])

if __name__=='__main__':unittest.main()
