from pathlib import Path
import sys,re,subprocess,unittest
HOME=Path(__file__).resolve().parents[1];ROOT=next(p for p in Path(__file__).resolve().parents if (p/'tools/cas_grid_transaction.py').is_file());sys.path.insert(0,str(ROOT/'tests'))
from test_cas_card_geometry import javascript_function
SOURCE=ROOT/'Source/CASUi/catalog_workspace_methods.as'
def functions():
 out=''
 for name,args in [('ApexCatalogFrame','event=null'),('ApexCatalogDisplayFaulted','panel,grid'),('ApexCatalogDisplayFault','panel,grid,error'),('ApexCatalogDisplayFaultStatus','')]:
  body=javascript_function(name,args,source=SOURCE);body=re.sub(r'catch\((\w+):(?:Error|\*)\)',r'catch(\1)',body);body=re.sub(r'for each\(var (\w+) in ([^)]+)\)',r'for(var \1 of Object.values(\2))',body);body=body.replace('of apexCatalogDisplayFaults)','of Object.values(apexCatalogDisplayFaults))');out+=body
 return out
class FaultTests(unittest.TestCase):
 def case(self,code):
  r=subprocess.run(['node','-'],input=BOOT+functions()+code,capture_output=True,text=True,timeout=10);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_skin_missing_nested_helper_does_not_poison_other_retained_provider(self):
  self.case("ApexCatalogFrame();assert.equal(layoutCalls.skin,1);assert.equal(apexCatalogGrid.error,'');assert.equal(invalidations.length,0);assert.equal(removed,0);assert.equal(hairGrid.visible,true);mCurrentPanel=hair;ApexCatalogFrame();assert.equal(layoutCalls.hair,1);assert.equal(apexCatalogGrid.error,'');assert.equal(removed,0);")
 def test_failed_exact_grid_never_retries_on_later_frames_context_or_preference_changes(self):
  self.case("ApexCatalogFrame();for(let i=0;i<50;i++){mCurrSimInfo.simId=String(100+i);apexFormsSelectedId='changed/'+i;apexOwnerSession++;mCurrState++;ApexCatalogFrame();}assert.equal(layoutCalls.skin,1);assert.equal(removed,0);assert.equal(columns,51);assert.equal(Object.keys(apexCatalogDisplayFaults).length,1);")
 def test_fault_status_copies_primitive_evidence_and_no_ui_handles(self):
  self.case("ApexCatalogFrame();const result=ApexCatalogDisplayFaultStatus();assert.equal(result.limit,6);assert.equal(result.faults.length,1);const row=result.faults[0];for(const key of ['grid','root','stage','validate'])assert.equal(key in row,false);assert.equal(row.panel,'skin');assert.equal(row.sim_id,'101');assert.equal(row.owner_id,'alien/alien');assert.equal(row.native_generation,'73');assert.ok(JSON.stringify(result));row.message='tampered';assert.notEqual(apexCatalogDisplayFaults.skin.message,'tampered');")
 def test_only_exact_failed_incremental_grid_retires_without_hiding_ready_cells(self):
  self.case("mCurrentPanel=body;failBody=true;apexCatalogGrid.grid=bodyGrid;apexCatalogGrid.lease.panel=body;ApexCatalogFrame();assert.deepEqual(invalidations,['dispose']);assert.equal(bodyGrid.visible,true);assert.equal(bodyGrid.input,false);assert.equal(apexCatalogGrid.error,'');assert.equal(apexCatalogDisplayFaults.body.incremental_retired,true);assert.equal(removed,0);")
 def test_cleanup_failure_retains_fault_evidence_without_global_latch_or_retry(self):
  self.case("throwCleanup=true;ApexCatalogFrame();assert.equal(apexCatalogDisplayFaults.skin.cleanup_error,'Owned display cleanup refused');assert.equal(apexCatalogGrid.error,'');ApexCatalogFrame();assert.equal(layoutCalls.skin,1);assert.equal(removed,0);")
 def test_fresh_native_widget_can_qualify_but_same_widget_not_retried(self):
  self.case("ApexCatalogFrame();ApexCatalogFrame();assert.equal(layoutCalls.skin,1);skin.mcTileList.mGridLayout={visible:true,input:true};failSkin=false;ApexCatalogFrame();assert.equal(layoutCalls.skin,2);assert.equal(Object.keys(apexCatalogDisplayFaults).length,1);assert.equal(removed,0);")
 def test_reentrant_panel_change_during_failure_never_retires_or_restores_new_panel(self):
  self.case("changePanelDuringFailure=true;ApexCatalogFrame();assert.equal(mCurrentPanel,hair);assert.equal(invalidations.length,0);assert.equal(restored,0);assert.equal(hairGrid.visible,true);ApexCatalogFrame();assert.equal(layoutCalls.hair,1);assert.equal(removed,0);")
 def test_fault_inventory_is_bounded_to_six_exact_known_panels(self):
  self.case("for(const p of panels)ApexCatalogDisplayFault(p,p.mcTileList.mGridLayout,Error('bad '+p.key));assert.equal(Object.keys(apexCatalogDisplayFaults).length,6);for(let i=0;i<100;i++)ApexCatalogDisplayFault({key:'foreign'+i},{},Error('foreign'));assert.equal(Object.keys(apexCatalogDisplayFaults).length,6);assert.equal(ApexCatalogDisplayFaultStatus().faults.length,6);")
 def test_actual_native_provider_retirement_retains_committed_bank_and_refuses_stale_input(self):
  sys.path.insert(0,str(ROOT/'tools'))
  import test_cas_grid_presentation as native
  import cas_grid_progress
  original_stage=native.stage
  native.stage=cas_grid_progress
  extra="""
const g=new NativeGrid(176,0);g.ApexGridBegin(request(g,12,{viewHeight:400}));assert.equal(bounded(g).phase,'done');const old=g.mCells.slice(),ids=rendered(g);
var apexCatalogDisplayFaults=null,apexCatalogError='',apexCardGeometry=null;
var apexCatalogGrid={error:'',grid:g,lease:{panel:g.panel}},mCurrState=40,mCurrSimInfo={simId:'101'},apexFormsSelectedId='alien/alien',apexOwnerSession=3,apexFormsNativeGeneration='73';
function ApexCatalogPanelKey(panel){return panel===g.panel?'body':'';}function ApexCatalogClearEffects(){}function ApexCardRestore(){throw Error('No geometry owned');}
function ApexCatalogGridInvalidate(reason){g.lease.active=false;g.ApexGridCancel(reason);}
ApexCatalogDisplayFault(g.panel,g,Error('Exact failed display provider'));
assert.deepEqual(g.mCells,old);assert.deepEqual(rendered(g),ids);assert.equal(g.mGridView.visible,true);
assert.equal(g.ApexGridStatus().phase,'cancelled');assert.equal(g.ApexGridStatus().reason,'dispose');assert.equal(g.ApexGridStatus().lease,false);
assert.equal(g.ApexGridNativeGuard('input',{currentTarget:old[0]}),true);assert.equal(apexCatalogGrid.error,'');assert.equal(apexCatalogDisplayFaults.body.incremental_retired,true);
"""
  try:
   r=subprocess.run(['node','-'],input=native.NATIVE_MOCK+native.javascript()+native.BOOT+functions()+extra,capture_output=True,text=True,timeout=15);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
  finally:native.stage=original_stage
 def test_only_owned_fault_summary_clears_after_successful_other_panel_apply(self):
  self.case("ApexCatalogFrame();assert.ok(apexCatalogError.startsWith('Catalogue display unavailable for skin:'));const evidence=apexCatalogDisplayFaults.skin;mCurrentPanel=hair;ApexCatalogFrame();assert.equal(apexCatalogError,'');assert.equal(apexCatalogDisplayFaults.skin,evidence);apexCatalogError='Different genuine edit error';ApexCatalogFrame();assert.equal(apexCatalogError,'Different genuine edit error');")
 def test_controller_rejects_quarantined_provider_without_hiding_others(self):
  source=(ROOT/'Source/CASUi/catalog_grid_transaction_methods.as').read_text();body=source.split('private function ApexCatalogGridProductPanel(',1)[1].split('private function ApexCatalogGridProductRow(',1)[0]
  self.assertIn('if(apexCatalogDisplayFaults!=null && ApexCatalogDisplayFaulted(panel,panel.mcTileList.mGridLayout))return "";',body)
 def test_original_global_outer_catch_is_not_used_for_known_display_apply_failures(self):
  source=SOURCE.read_text();frame=source.split('private function ApexCatalogFrame(',1)[1].split('private function ApexCatalogClearEffects(',1)[0]
  self.assertIn('catch(displayError:Error) {ApexCatalogDisplayFault(panel,grid,displayError);}',frame)
  self.assertLess(frame.index('catch(displayError:Error)'),frame.index('catch(frameError:Error)'))
BOOT="""
const assert=require('node:assert/strict');function int(v){return v|0;}int.MAX_VALUE=2147483647;
let ticks=0,removed=0,columns=0,restored=0,throwCleanup=false,changePanelDuringFailure=false;
const flash={events:{Event:{ENTER_FRAME:'frame'}},utils:{getTimer(){return ticks++;}}};const stage={stageWidth:2560};
const hairGrid={visible:true,input:true},skinGrid={visible:true,input:true},bodyGrid={visible:true,input:true};
const hair={key:'hair',visible:true,mcTileList:{mGridLayout:hairGrid}},skin={key:'skin',visible:true,mcTileList:{mGridLayout:skinGrid}},body={key:'body',visible:true,mcTileList:{mGridLayout:bodyGrid}};
const panels=[hair,skin,body,...['face','generic','featured'].map(key=>({key,visible:true,mcTileList:{mGridLayout:{visible:true,input:true}}}))];
var mCurrentPanel=skin,mcClothingPanel=hair,mCurrState=40,mCurrSimInfo={simId:'101'},apexFormsSelectedId='alien/alien',apexOwnerSession=3,apexFormsNativeGeneration='73';
let apexCatalogPrefs={color:0,glow:0,border:3},apexDisconnected=false,apexCatalogFrameCells=null,apexCatalogDisplayFaults=null,apexCatalogError='',apexCatalogStyleSignature='';
let apexCardGeometry={grid:skinGrid,panel:skin},apexCatalogGrid={error:'',grid:hairGrid,lease:{panel:hair}},apexCatalogEffects=[],apexCatalogHeaderSignature='',apexCatalogUi=null,apexCatalogIntent=null,apexPendingFields=null,apexReceiving=false;
let apexCatalogFrameTiming={layout_max_ms:0,binding_max_ms:0,samples:0,total_ms:0,max_ms:0,over_1ms:0};
let failSkin=true,failBody=false,layoutCalls={skin:0,hair:0,body:0};const invalidations=[];
function ApexCatalogPanelKey(panel){return panels.includes(panel)?panel.key:'';}function ApexCatalogPanelKind(panel){return panel===skin?'swatches':panel?'cards':'';}
function ApexPanelsFrame(){}function ApexSkinToneApply(panel,grid){layoutCalls.skin++;if(changePanelDuringFailure){mCurrentPanel=hair;apexCardGeometry={panel:hair,grid:hairGrid};}if(failSkin)throw Error('Native nested swatch adapter unavailable');return 400;}
function ApexCardApply(panel,grid){layoutCalls[panel.key]++;if(failBody)throw Error('Body display failed');return 400;}function ApexCatalogApplyBinding(){}function ApexCatalogClearEffects(){if(throwCleanup)throw 'cleanup';}function ApexCatalogGridPending(){return false;}function ApexCatalogSelection(){}function ApexColumnsFrame(){columns++;}
function ApexEquippedFrame(){}function ApexSearchFrame(){}function ApexCompanionFrame(){}function ApexCatalogKeyboardFrame(){}function ApexCatalogGridInvalidate(reason){invalidations.push(reason);apexCatalogGrid.grid.input=false;}
function ApexCardRestore(){restored++;apexCardGeometry=null;}function removeEventListener(){removed++;}
"""
if __name__=='__main__':unittest.main()
