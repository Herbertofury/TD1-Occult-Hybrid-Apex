from pathlib import Path
import sys,importlib.util,subprocess,re,unittest
ROOT=Path(__file__).resolve().parents[1];PROJECT=next(p for p in (ROOT,*ROOT.parents) if (p/'tools/cas_grid_progress.py').is_file());sys.path[:0]=[str(ROOT/'tools'),str(PROJECT/'tests'),str(PROJECT/'tools')]
import cas_grid_scroll as scroll,cas_grid_pool as pool
SOURCE=ROOT/'Source/CASUi/catalog_grid_scroll_main_methods.as'

class MainOptinTests(unittest.TestCase):
 def code(self):
  text=SOURCE.read_text(encoding='utf-8-sig');a,b=pool.method_extent(text,'ApexCatalogGridRequest');fragment=text[a:b];body=fragment.split('{',1)[1].rsplit('}',1)[0]
  return 'function ApexCatalogGridRequest(lease){'+re.sub(r'\b(var\s+\w+)\s*:\s*[\w.]+',r'\1',body)+'}\n'
 def case(self,code):
  result=subprocess.run(['node','-'],input=BOOT+self.code()+code,text=True,capture_output=True,timeout=10);self.assertEqual(result.returncode,0,result.stdout+result.stderr)
 def test_only_exact_loaded_classes_get_contract_and_unknown_remains_zero(self):
  self.case("for(const c of cells){lease.cell_type=c;const r=ApexCatalogGridRequest(lease);assert.equal(r.scrollOnlyPositionContract,1);}lease.cell_type=function Custom(){ };assert.equal(ApexCatalogGridRequest(lease).scrollOnlyPositionContract,0);")
 def test_owner_and_geometry_refusals_still_happen_before_any_admission(self):
  self.case("current=false;assert.equal(ApexCatalogGridRequest(lease),null);current=true;lease.phase='bootstrap';assert.equal(ApexCatalogGridRequest(lease),null);lease.phase='bound';view.width=NaN;assert.equal(ApexCatalogGridRequest(lease),null);")
 def test_both_bootstrap_measurement_and_real_request_keep_same_callbacks_and_raw_origin(self):
  self.case("for(const bootstrap of [false,true]){if(bootstrap)retained=null;const r=ApexCatalogGridRequest(lease);assert.equal(r.scrollOnlyPositionContract,1);assert.equal(r.bootstrap,bootstrap);assert.equal(r.owner,lease);assert.equal(r.validate,ApexCatalogGridValidate);assert.equal(r.inputValidate,ApexCatalogGridInput);assert.equal(r.rowValidate,ApexCatalogGridProductRow);assert.equal(r.scrollY,bootstrap?0:3.125);} ")
 def test_clothing_null_row_predicate_remains_exact(self):
  self.case("lease.panel_kind='clothing';assert.equal(ApexCatalogGridRequest(lease).rowValidate,null);")
 def test_marker_removed_source_is_exact_original_no_other_main_edits(self):
  base=(PROJECT/'Source/CASUi/catalog_grid_transaction_methods.as').read_text();a,b=pool.method_extent(base,'ApexCatalogGridRequest');original=base[a:b];modified=SOURCE.read_text().strip()
  insertion='\n         var scrollContract:int=(lease.cell_type===CASClothingPanelCellViewMain ||\n            lease.cell_type===CASClothingPanelCellViewCommon || lease.cell_type===CASClothingPanelCellViewSkinSpecularity ||\n            lease.cell_type===CASBodyPanelCellView ||\n            lease.cell_type===CASFacePanelCellView || lease.cell_type===CASGenericCatalogVariantCellView ||\n            lease.cell_type===CASBreedCatalogCellView) ? 1 : 0;'
  self.assertEqual(modified.replace(insertion,'').replace(',scrollOnlyPositionContract:scrollContract',''),original)
BOOT="""
const assert=require('node:assert/strict');function int(v){return v|0;}
class CASClothingPanelCellViewMain{}class CASClothingPanelCellViewCommon{}class CASClothingPanelCellViewSkinSpecularity{}class CASBodyPanelCellView{}class CASFacePanelCellView{}class CASGenericCatalogVariantCellView{}class CASBreedCatalogCellView{}
const cells=[CASClothingPanelCellViewMain,CASClothingPanelCellViewCommon,CASClothingPanelCellViewSkinSpecularity,CASBodyPanelCellView,CASFacePanelCellView,CASGenericCatalogVariantCellView,CASBreedCatalogCellView];
let current=true;const view={width:600,height:770};const grid={GetCellPadding(){return {mLeft:0,mTop:0};}};const panel={mcTileList:{mScrollerView:view,mSlider:{Value:3.125}}};const lease={phase:'bound',cell_type:CASBodyPanelCellView,panel_kind:'body',grid,panel};
let retained={geometry:{grid,panel},layout:{scale:.5,card_width:53.5,card_height:73.5,columns:12,gap_x:4,gap_y:4}};
function ApexCatalogGridLeaseCurrent(){return current;}function ApexCardStateFor(){return retained;}
function ApexCatalogGridValidate(){}function ApexCatalogGridInput(){}function ApexCatalogGridProductRow(){}
"""
if __name__=='__main__':unittest.main()
