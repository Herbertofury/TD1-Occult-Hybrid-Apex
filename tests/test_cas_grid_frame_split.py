from pathlib import Path
import sys,re,subprocess,unittest,hashlib,json
HOME=Path(__file__).resolve().parents[1];ROOT=next(p for p in Path(__file__).resolve().parents if (p/'tools/cas_grid_transaction.py').is_file());sys.path.insert(0,str(ROOT/'tests'))
from test_cas_card_geometry import javascript_function
SOURCE=ROOT/'Source/CASUi/catalog_grid_transaction_methods.as'
class SplitTests(unittest.TestCase):
 def case(self,code):
  body=javascript_function('ApexCatalogGridFrame','event=null',source=SOURCE);body=re.sub(r'catch\((\w+):Error\)',r'catch(\1)',body)
  script=BOOT+body+code;r=subprocess.run(['node','-'],input=script,capture_output=True,text=True,timeout=10);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_existing_three_clocks_and_original_deadline_argument_order_are_retained(self):
  text=SOURCE.read_text();frame=text.split('private function ApexCatalogGridFrame(',1)[1].split('private function ApexCatalogGridInvalidate(',1)[0]
  self.assertEqual(frame.count('flash.utils.getTimer()'),3)
  self.assertIn('ApexGridStep(64,(stepStarted=flash.utils.getTimer())+1)',frame)
  self.assertNotIn('CallGameService(',frame);self.assertNotIn('ApexNativeExchange(',frame)
 def test_exact_existing_clocks_split_pre_step_and_step_with_original_deadline(self):
  self.case("preDelay=17;stepDelay=5;ApexCatalogGridFrame();assert.equal(clocks,3);assert.equal(stepCalls,1);assert.equal(lastDeadline,18);assert.equal(apexCatalogGrid.frame_max_ms,22);assert.equal(apexCatalogGrid.frame_pre_step_max_ms,17);assert.equal(apexCatalogGrid.frame_step_max_ms,5);assert.equal(apexCatalogGrid.frame_max_pre_step_ms+apexCatalogGrid.frame_max_step_ms,22);")
 def test_early_observation_wait_is_all_pre_step_and_no_extra_clock(self):
  self.case("preDelay=9;wait=true;ApexCatalogGridFrame();assert.equal(clocks,2);assert.equal(stepCalls,0);assert.equal(apexCatalogGrid.frame_max_ms,9);assert.equal(apexCatalogGrid.frame_pre_step_max_ms,9);assert.equal(apexCatalogGrid.frame_step_max_ms,0);")
 def test_native_step_throw_preserves_original_error_path_and_finally_cleanup(self):
  self.case("preDelay=3;stepDelay=40;throwStep=true;ApexCatalogGridFrame();assert.equal(clocks,3);assert.equal(apexCatalogGrid.error,'Incremental catalogue paused: original step refused');assert.equal(invalidated,'error-abandon');assert.equal(apexCatalogGrid.running,false);assert.equal(apexCatalogGrid.lease.frame_validated,false);assert.equal(apexCatalogGrid.frame_step_max_ms,40);assert.equal(apexCatalogGrid.frame_max_ms,43);")
 def test_coherent_idle_grid_still_performs_zero_clocks_and_zero_step(self):
  self.case("idle=true;ApexCatalogGridFrame();assert.equal(clocks,0);assert.equal(stepCalls,0);assert.equal(time,0);assert.equal(apexCatalogGrid.frame,0);")
 def test_reentrant_frame_and_hidden_panels_remain_inert(self):
  self.case("apexCatalogGrid.running=true;ApexCatalogGridFrame();assert.equal(clocks,0);apexCatalogGrid.running=false;mCurrentPanel.visible=false;ApexCatalogGridFrame();assert.equal(clocks,0);assert.equal(stepCalls,0);")
 def test_max_frame_pair_is_from_same_frame_not_independent_component_maxima(self):
  self.case("preDelay=30;stepDelay=1;ApexCatalogGridFrame();preDelay=1;stepDelay=12;ApexCatalogGridFrame();assert.equal(apexCatalogGrid.frame_pre_step_max_ms,30);assert.equal(apexCatalogGrid.frame_step_max_ms,12);assert.equal(apexCatalogGrid.frame_max_ms,31);assert.equal(apexCatalogGrid.frame_max_pre_step_ms,30);assert.equal(apexCatalogGrid.frame_max_step_ms,1);")
BOOT="""
const assert=require('node:assert/strict');function int(v){return v|0;}int.MAX_VALUE=2147483647;
let clocks=0,time=0,preDelay=0,stepDelay=0,stepCalls=0,lastDeadline=0,idle=false,wait=false,throwStep=false,invalidated='';
const flash={utils:{getTimer(){clocks++;return time;}}};const stage={};let mCurrentPanel={visible:true};
const lease={panel:mCurrentPanel,active:true,phase:'bound',geometry_signature:'sig',frame_validated:false};const grid={ApexGridNeedsWork(){return !idle;},ApexGridBegin(){return {operations:0};},ApexGridStep(count,deadline){assert.equal(count,64);lastDeadline=deadline;stepCalls++;time+=stepDelay;if(throwStep)throw Error('original step refused');return {operations:1,error:null};}};
let apexCatalogGrid={enabled:true,disposed:false,error:'',running:false,grid,lease,frame:0};
const retained={geometry:{grid,panel:mCurrentPanel},signature:'sig',layout:{}};
function ApexCatalogGridProductPanel(){return 'body';}function ApexCardStateFor(){return retained;}function ApexCatalogGridLeaseCurrent(){return true;}
function ApexCatalogGridPrepare(){return true;}function ApexCatalogGridFrameObserve(){time+=preDelay;return wait?null:{};}function ApexCatalogGridObserve(){return ApexCatalogGridFrameObserve();}function ApexCatalogGridMatches(){return true;}
function ApexCatalogGridRequest(){return {};}function ApexCatalogGridInvalidate(reason){invalidated=reason;}
"""
if __name__=='__main__':unittest.main()
