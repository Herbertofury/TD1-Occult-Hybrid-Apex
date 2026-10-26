from pathlib import Path
import sys,subprocess,unittest
ROOT=Path(__file__).resolve().parents[1];PROJECT=next(p for p in(ROOT,*ROOT.parents)if(p/'tools/cas_grid_slice.py').is_file());sys.path[:0]=[str(PROJECT/'tests')]
from test_cas_card_geometry import javascript_function
from test_cas_grid_scroll_main import BOOT
class ProducerTests(unittest.TestCase):
 def test_exact_known_class_capabilities_are_separate_and_unknown_classes_keep_legacy(self):
  source=ROOT/'Source/CASUi/catalog_grid_budget_main_request.as';body=javascript_function('ApexCatalogGridRequest','lease',source=source)
  code="for(const c of cells){lease.cell_type=c;const r=ApexCatalogGridRequest(lease);assert.equal(r.stepBudgetClockContract,1);assert.equal(r.stepBudgetMilliseconds,1);assert.equal(r.scrollOnlyPositionContract,1);}lease.cell_type=function Unknown(){};const unknown=ApexCatalogGridRequest(lease);assert.equal(unknown.stepBudgetClockContract,0);assert.equal(unknown.scrollOnlyPositionContract,0);assert.equal(unknown.stepBudgetMilliseconds,1);"
  result=subprocess.run(['node','-'],input=BOOT+body+code,capture_output=True,text=True,timeout=10);self.assertEqual(result.returncode,0,result.stdout+result.stderr)
if __name__=='__main__':unittest.main()
