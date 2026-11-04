"""Execute actual merged Main/native source, without game/profile access."""
from pathlib import Path
import re,sys,subprocess,unittest,os,hashlib
H=Path(__file__).resolve().parents[1];R=next(p for p in(H,*H.parents)if(p/'tools/dbpf_build.py').is_file())
sys.path[:0]=[str(H/'tools'),str(R/'tools')]
import cas_list_insets_stage as stage,cas_grid_pool as pool
BODY=Path(os.environ['APEX_CAS_BODY_TYPE_TABS_AS'])if os.environ.get('APEX_CAS_BODY_TYPE_TABS_AS')else None
CATALOG=Path(os.environ['APEX_CAS_CATALOG_PANEL_AS'])if os.environ.get('APEX_CAS_CATALOG_PANEL_AS')else None

def method(source,name):
 source=source.replace('public static function','public function').replace('private static function','private function').replace('public final function','public function').replace('protected function','public function')
 a,b=pool.method_extent(source,name);return source[a:b]
def js(source,name,args=''):
 s=method(source,name);s=s[s.index('{')+1:-1]
 s=re.sub(r'\b(var\s+\w+)\s*:\s*[\w.<>]+',r'\1',s)
 s=re.sub(r'catch\((\w+):Error\)',r'catch(\1)',s)
 s=re.sub(r'\s+as\s+[\w.]+','',s)
 s=re.sub(r'\b([\w.]+) is Function',r'typeof \1==="function"',s)
 s=re.sub(r'\b([\w.]+) is Class',r'typeof \1==="function"',s)
 s=re.sub(r'\b([\w.]+) is int',r'Number.isInteger(\1)',s)
 s=re.sub(r'\bis\b','instanceof',s)
 s=re.sub(r'for each\((?:var )?(\w+) in ([^\n]+?)\)',r'for(var \1 of \2)',s)
 return 'function '+name+'('+args+'){'+('with(this){'+s+'}'if name in('RefreshLayout','ApexRawListBaseline','ApexRawListGeneration')else s)+'}\n'

BOOT=r'''
const assert=require('node:assert/strict');function int(v){return Math.trunc(v);}int.MAX_VALUE=2147483647;
const stage={};let writes=[],heightWrites=0,position=0,scroll=0,bridge=true,onY=null,onHeight=null;
const q=v=>Math.round(v*20)/20;
class NativeList {
 static qname='olympus.gui.lists::ScrollList';
 constructor(){this.stage=stage;this._y=17.3;this._height=1167.7;this.mcBackground={};this.mScrollerView={};this.mSlider={};this.grid={};}
 GetGridView(){return this.grid;}
 get y(){return this._y;}set y(v){writes.push(['y',v]);this._y=q(v);if(onY)onY(this);}
 get height(){return this._height;}set height(v){writes.push(['height',v]);heightWrites++;const old=this._height;this._height=q(v);if(old!==this._height)position++;scroll++;if(onHeight)onHeight(this);}
}
const flash={utils:{getQualifiedClassName(v){return typeof v==='function'?v.qname:v.qname||v.constructor.qname;}},display:{DisplayObject:class{}}};
function getDefinitionByName(n){if(n==='olympus.gui.lists.ScrollList')return NativeList;if(n==='dcc.catalog.BodyTypeTabs')return BodyTypeTabs;throw Error(n);}
let frameWidth=537.35;
const panel={stage,mcTileList:new NativeList(),mcPanelBackground:{height:1220,getBounds(){return {width:frameWidth,left:0};}},txtNoResults:null,
 mcHeader:null,mcFooter:null,mcFilterPane:{mcFilterBubble:{y:0,x:0,mcBackground:{width:507.35},parent:{}}},
 SetHeaderPosition(){},SetFooterPosition(){},UpdateFilterPaneOffsets(){},RefreshPanes(){},GetTileListYTopOffset(){return 17.3;},GetTileListYBottomOffset(){return 35;},
 apexRawListGeneration:0,apexRawListLayout:null};
const mcClothingPanel=panel,mcBodyModPanel={},mcFaceModPanel={},mcGenericCatalogPanel={},mcFeaturedFaceLookPanel={},mcSkinColorPanel={};
let apexSearch={root:{x:0,y:0},bubble:panel.mcFilterPane.mcFilterBubble,list:panel.mcTileList,geometry:null,width:507.35,message:{x:0,y:0,width:0},list_layouts:[null,null,null,null,null,null]};
function ApexSearchLabels(){}function ApexFormsText(){return {};}
const CommunicationManager={CallUIService(name,value){return bridge?ApexCatalogListGeometry(value):null;}};
const host=panel,rail={qname:'flash.display::Sprite',parent:panel,stage,scaleX:1,x:0,y:0};let layingOut=false,layoutList=null,baseY=0,baseHeight=0,hasLayout=false,appliedY=0,appliedHeight=0,apexListLayout=null;
let columns=9,rows=1,groups=[1,115],paged=false,capacity=8,offset=0,signature='ready',drawnWidth=517.35,drawnRows=1,drawnSelected=0,drawnOffset=0,drawnGroups='1,115',groupToken='1,115',selected=0;
function Draw(){drawnWidth=Math.max(156,frameWidth-20);drawnRows=rows;drawnSelected=selected;drawnOffset=offset;drawnGroups=groupToken;signature='ready';}
function Recover(){throw Error('Unexpected Recover');}
function once(){Layout(panel);ApexSearchAttach(panel);}
'''

def program(original=False):
 main=(R/'Source/CASUi/catalog_search_methods.as').read_text();body=BODY.read_text();catalog=CATALOG.read_text();extra='';helper=''
 if not original:
  main=stage.main(main);body,helper=stage.body(body);catalog,catalog_extra=stage.catalog(catalog);extra=catalog_extra
 funcs=''
 if not original:
  for n,args in [('ApexCatalogListSlot','panel'),('ApexCatalogListCurrent','r'),('ApexCatalogListRecord','panel,list'),('ApexCatalogListApply','r'),('ApexCatalogListRail','r,height,rail=null'),('ApexCatalogListGeometry','value'),('ApexCatalogSearchListApply','panel,list,g'),('ApexCatalogSearchListRestore','g')]:funcs+=js(main,n,args)
  funcs+=js(helper,'ApexListLayoutRecord','panel,list')+js(helper,'ApexNativeRailReceipt','panel,list')+'function BodyTypeTabs(){}BodyTypeTabs.ApexNativeRailReceipt=ApexNativeRailReceipt;\n'
 else:funcs+='function ApexCatalogListGeometry(){return null;}\n'
 funcs+=js(main,'ApexSearchAttach','panel')+js(main,'ApexSearchRestore')+js(body,'Layout','panel')+js(body,'NativeLayout','panel')+js(body,'RestoreList')+js(catalog,'RefreshLayout')
 if not original:funcs+=js(extra,'ApexRawListBaseline')+js(extra,'ApexRawListGeneration')+'panel.ApexRawListBaseline=ApexRawListBaseline;panel.ApexRawListGeneration=ApexRawListGeneration;\n'
 # Original native bodies use this, as in their real receiver.
 funcs+='panel.RefreshLayout=RefreshLayout;\n'
 return BOOT+funcs

def public_program():
 source=(H/'Source/CASUi/catalog_list_inset_methods.as').read_text()
 funcs=''.join(js(source,n,args)for n,args in [('ApexCatalogListSlot','panel'),('ApexCatalogListCurrent','r'),('ApexCatalogListRecord','panel,list'),('ApexCatalogListApply','r'),('ApexCatalogListRail','r,height,rail=null'),('ApexCatalogListGeometry','value'),('ApexCatalogSearchListApply','panel,list,g'),('ApexCatalogSearchListRestore','g'),('ApexCatalogListRect','display,target,space'),('ApexCatalogListStatus','')])
 return BOOT+'''function BodyTypeTabs(){};const mCurrentPanel=panel;
panel.ApexRawListGeneration=()=>panel.apexRawListGeneration;
panel.ApexRawListBaseline=()=>panel.apexRawListLayout==null?null:{...panel.apexRawListLayout};
function raw(y=17.3,h=1167.7){panel.mcTileList._y=q(y);panel.mcTileList._height=q(h);panel.apexRawListGeneration++;panel.apexRawListLayout={protocol:1,panel,list:panel.mcTileList,stage,generation:panel.apexRawListGeneration,y:q(y),height:q(h)};return ApexCatalogListGeometry({operation:'native-base',panel,list:panel.mcTileList,generation:panel.apexRawListGeneration});}
'''+funcs

class ComposerPublicTests(unittest.TestCase):
 def case(self,code):
  r=subprocess.run(['node','-'],input=public_program()+code,text=True,capture_output=True,timeout=15)
  self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_steady_combined_geometry_has_no_additional_native_setters(self):
  self.case("const r=raw();assert.equal(r.set_rail(r,68,rail),true);const g={};ApexCatalogSearchListApply(panel,panel.mcTileList,g);const n=writes.length;for(let i=0;i<30;i++){r.set_rail(r,68,rail);ApexCatalogSearchListApply(panel,panel.mcTileList,g);}assert.equal(writes.length,n);assert.equal(panel.mcTileList.y,137.3);assert.equal(panel.mcTileList.height,1047.7);assert.equal(rail.y,69.3);")
 def test_each_contributor_can_leave_without_removing_the_other(self):
  self.case("const r=raw(),g={};r.set_rail(r,68,rail);ApexCatalogSearchListApply(panel,panel.mcTileList,g);ApexCatalogSearchListRestore(g);assert.equal(panel.mcTileList.y,85.3);assert.equal(r.rail,68);r.set_rail(r,0);assert.equal(panel.mcTileList.y,17.3);assert.equal(r.raw_height,1167.7);")
 def test_bridge_does_not_accept_fabricated_native_generation_or_inset_pixels(self):
  self.case("const r=raw(),g={};ApexCatalogSearchListApply(panel,panel.mcTileList,g);const n=writes.length;assert.equal(ApexCatalogListGeometry({operation:'native-base',panel,list:panel.mcTileList,generation:2,y:69.3,height:1115.7}),null);assert.equal(r.raw_y,17.3);assert.equal(writes.length,n);")
 def test_foreign_native_widget_replacement_cannot_use_old_cleanup_authority(self):
  self.case("const r=raw(),g={};ApexCatalogSearchListApply(panel,panel.mcTileList,g);const old=panel.mcTileList;panel.mcTileList=new NativeList();const n=writes.length;assert.equal(ApexCatalogListCurrent(r),false);assert.equal(ApexCatalogSearchListRestore(g),false);assert.equal(writes.length,n);assert.equal(old.y,69.3);")
 def test_explicit_rectangles_are_copied_labelled_finite_and_bounded(self):
  self.case("const d={stage,visible:true,mouseEnabled:true,mouseChildren:false,getBounds(){return {x:2,y:3,width:4,height:5,foreign:panel};}};const rect=ApexCatalogListRect(d,panel,'panel-local');assert.deepEqual(rect,{available:true,space:'panel-local',source:'native-getBounds',x:2,y:3,width:4,height:5,visible:true,mouse_enabled:true,mouse_children:false});d.getBounds=()=>({x:NaN,y:0,width:1,height:1});assert.equal(ApexCatalogListRect(d,panel,'panel-local').available,false);d.getBounds=()=>{throw Error('x'.repeat(10000));};assert.equal(ApexCatalogListRect(d,panel,'panel-local').error.length,160);")
 def test_explicit_status_serializes_no_control_or_callable_handles(self):
  self.case("const r=raw(),g={};ApexCatalogSearchListApply(panel,panel.mcTileList,g);const value=ApexCatalogListStatus();const text=JSON.stringify(value);assert.equal(text.includes('GetGridView'),false);assert.equal(text.includes('current'),true);assert.equal(value.raw.native_generation,1);assert.equal(value.insets.search,52);assert.equal(value.local_space,'panel-local');assert.equal(value.stage_space,'stage');assert.equal(value.appearance_written,false);assert.equal(value.record_present,true);")
 def test_status_rect_helpers_are_not_added_to_frame_or_input_paths(self):
  before=(R/'Source/CASUi/catalog_search_methods.as').read_text();after=stage.main(before)
  for name in ('ApexSearchFrame','ApexSearchSource'):
   self.assertEqual(method(before,name),method(after,name))
  self.assertIn('list_geometry:ApexCatalogListStatus()',method(after,'ApexSearchStatus'))

@unittest.skipUnless(BODY and CATALOG,'Set APEX_CAS_BODY_TYPE_TABS_AS + APEX_CAS_CATALOG_PANEL_AS for exact private native-source qualification')
class ListInsetTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  if hashlib.sha256(BODY.read_bytes()).hexdigest()!='5e6e4a48e495c7f5ba36957d5ad79eba75b04c5064e8f5d813d3f65d52d911e6':raise ValueError('Exact pinned donor BodyTypeTabs source required')
  if hashlib.sha256(CATALOG.read_bytes()).hexdigest()!='6fabb1891b00fbe47ca7235078508ea7084363d6fd4c37fed1c8990dfcace9a6':raise ValueError('Exact pinned donor CatalogPanel source required')
 def case(self,code,original=False):
  r=subprocess.run(['node','-'],input=program(original)+code,text=True,capture_output=True,timeout=15)
  self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_original_rail_and_search_reproduce_repeated_dimension_setters(self):
  self.case("panel.RefreshLayout();for(let i=0;i<30;i++)once();assert.ok(heightWrites>=59);assert.equal(panel.mcTileList.height,1047.7);",True)
 def test_shared_actual_two_group_rail_search_settle_without_thirty_frame_writes(self):
  self.case("panel.RefreshLayout();once();const old=writes.length,events=scroll,r=apexSearch.geometry.list_layout;for(let i=0;i<30;i++)once();assert.equal(writes.length,old);assert.equal(scroll,events);assert.equal(r.raw_y,17.3);assert.equal(r.raw_height,1167.7);assert.equal(panel.mcTileList.y,137.3);assert.equal(panel.mcTileList.height,1047.7);assert.equal(rail.y,69.3);")
 def test_search_off_preserves_rail_then_rail_off_restores_native(self):
  self.case("panel.RefreshLayout();once();ApexSearchRestore();assert.equal(panel.mcTileList.y,85.3);assert.equal(panel.mcTileList.height,1099.7);Layout(panel);assert.equal(panel.mcTileList.y,85.3);RestoreList();assert.equal(panel.mcTileList.y,17.3);assert.equal(panel.mcTileList.height,1167.7);")
 def test_rail_off_preserves_search_then_search_off_restores_native(self):
  self.case("panel.RefreshLayout();once();RestoreList();assert.equal(panel.mcTileList.y,69.3);assert.equal(panel.mcTileList.height,1115.7);ApexSearchRestore();assert.equal(panel.mcTileList.y,17.3);assert.equal(panel.mcTileList.height,1167.7);")
 def test_native_base_then_derived_consumes_raw_generation_without_double_inset(self):
  self.case("panel.RefreshLayout();once();panel.mcPanelBackground.height=1100;panel.RefreshLayout();NativeLayout(panel);ApexSearchAttach(panel);const r=apexSearch.geometry.list_layout;assert.equal(r.raw_height,1047.7);assert.equal(r.native_generation,2);assert.equal(panel.mcTileList.height,927.7);const n=writes.length;for(let i=0;i<30;i++)once();assert.equal(writes.length,n);")
 def test_width_group_count_and_selection_change_preserve_baseline(self):
  self.case("panel.RefreshLayout();once();groups=Array.from({length:15},(_,i)=>i);groupToken=groups.join(',');Layout(panel);ApexSearchAttach(panel);assert.equal(panel.mcTileList.y,197.3);assert.equal(panel.mcTileList.height,987.7);const r=apexSearch.geometry.list_layout;assert.equal(r.raw_height,1167.7);groups=[1,115];groupToken=groups.join(',');Layout(panel);ApexSearchAttach(panel);assert.equal(panel.mcTileList.height,1047.7);assert.equal(r.raw_height,1167.7);")
 def test_repeated_public_bridge_cannot_bless_composed_pixels_as_native_raw(self):
  self.case("panel.RefreshLayout();once();const r=apexSearch.geometry.list_layout,n=writes.length;for(let i=0;i<30;i++)ApexCatalogListGeometry({operation:'native-base',panel,list:panel.mcTileList,generation:1,y:panel.mcTileList.y,height:panel.mcTileList.height});assert.equal(r.raw_y,17.3);assert.equal(r.raw_height,1167.7);assert.equal(writes.length,n);")
 def test_external_edit_requires_new_native_baseline_without_repeated_repairs(self):
  self.case("panel.RefreshLayout();once();const r=apexSearch.geometry.list_layout;panel.mcTileList._height=900;const n=writes.length;for(let i=0;i<30;i++)once();assert.equal(writes.length,n);assert.equal(r.blocked,true);panel.RefreshLayout();NativeLayout(panel);ApexSearchAttach(panel);assert.equal(r.blocked,false);assert.equal(panel.mcTileList.height,1047.7);")
 def test_reentrant_raw_mutation_cannot_receive_old_receipt_or_overwrite_height(self):
  self.case("panel.RefreshLayout();Layout(panel);const r=apexSearch.list_layouts[0];onY=()=>{r.raw_height=777;};ApexSearchAttach(panel);onY=null;assert.equal(r.blocked,true);assert.notEqual(r.receipt?.y,137.3);assert.equal(panel.mcTileList.height,1099.7);")
 def test_unknown_bridge_keeps_original_donor_layout(self):
  self.case("bridge=false;panel.RefreshLayout();Layout(panel);assert.equal(panel.mcTileList.y,85.3);assert.equal(panel.mcTileList.height,1099.7);assert.equal(apexListLayout,null);")
 def test_rail_before_main_registration_uses_exact_private_native_predecessor_receipt(self):
  self.case("bridge=false;panel.RefreshLayout();Layout(panel);bridge=true;ApexSearchAttach(panel);Layout(panel);const r=apexSearch.geometry.list_layout;assert.equal(r.blocked,false);assert.equal(r.raw_y,17.3);assert.equal(r.raw_height,1167.7);assert.equal(panel.mcTileList.y,137.3);assert.equal(panel.mcTileList.height,1047.7);const n=writes.length;for(let i=0;i<30;i++)once();assert.equal(writes.length,n);")
 def test_native_no_results_follows_both_cleanup_orders(self):
  for order in('ApexSearchRestore();RestoreList();','RestoreList();ApexSearchRestore();'):
   self.case("panel.txtNoResults={y:17.3,visible:true};panel.RefreshLayout();once();once();"+order+"assert.equal(panel.txtNoResults.y,17.3);assert.equal(panel.mcTileList.y,17.3);")
 def test_real_native_refresh_during_each_setter_preserves_new_raw_then_applies_next_frame(self):
  for setter in('onY','onHeight'):
   self.case("panel.RefreshLayout();Layout(panel);let hit=0;"+setter+"=()=>{if(hit++)return;"+setter+"=null;panel.mcPanelBackground.height=1100;panel.RefreshLayout();NativeLayout(panel);};ApexSearchAttach(panel);"+setter+"=null;const r=apexSearch.geometry.list_layout;assert.equal(r.native_generation,2);assert.equal(r.raw_height,1047.7);assert.equal(panel.mcTileList.height,1047.7);once();assert.equal(panel.mcTileList.height,927.7);assert.equal(r.blocked,false);")
 def test_refused_height_blocks_without_retry_or_same_generation_reset(self):
  self.case("panel.RefreshLayout();Layout(panel);const r=apexSearch.list_layouts[0];onHeight=l=>{l._height=1099.7;};ApexSearchAttach(panel);onHeight=null;assert.equal(r.blocked,true);const n=writes.length;for(let i=0;i<30;i++){ApexCatalogListGeometry({operation:'native-base',panel,list:panel.mcTileList,generation:1});once();}assert.equal(writes.length,n);assert.equal(r.blocked,true);")
 def test_all_six_exact_panel_slots_preserve_raw_native_resize_without_clothing_assumptions(self):
  self.case("for(const p of[mcBodyModPanel,mcFaceModPanel,mcGenericCatalogPanel,mcFeaturedFaceLookPanel,mcSkinColorPanel]){Object.assign(p,{stage,mcTileList:new NativeList(),mcPanelBackground:{height:1220},txtNoResults:null,mcHeader:null,mcFooter:null,apexRawListGeneration:0,apexRawListLayout:null,ApexRawListBaseline,ApexRawListGeneration,RefreshLayout,SetHeaderPosition(){},SetFooterPosition(){},UpdateFilterPaneOffsets(){},RefreshPanes(){},GetTileListYTopOffset(){return 17.3;},GetTileListYBottomOffset(){return 35;}});p.RefreshLayout();const g={};assert.equal(ApexCatalogSearchListApply(p,p.mcTileList,g),true);const n=writes.length;for(let i=0;i<30;i++)ApexCatalogSearchListApply(p,p.mcTileList,g);assert.equal(writes.length,n);assert.equal(p.mcTileList.y,69.3);assert.equal(p.mcTileList.height,1115.7);p.mcPanelBackground.height=1100;p.RefreshLayout();assert.equal(g.list_layout.raw_height,1047.7);assert.equal(p.mcTileList.height,995.7);assert.equal(ApexCatalogSearchListRestore(g),true);assert.equal(p.mcTileList.height,1047.7);}")
 def test_scaled_native_rectangles_separate_search_filters_rail_and_cards_across_preferences(self):
  self.case("panel.RefreshLayout();groups=Array.from({length:15},(_,i)=>i);groupToken=groups.join(',');for(const width of[180,537.35,1200])for(const columns of[2,12,32])for(const size of[.2,.35,1,1.6]){frameWidth=width;once();const r=apexSearch.geometry.list_layout;const search={top:apexSearch.root.y,bottom:apexSearch.root.y+24},filter={top:panel.mcFilterPane.mcFilterBubble.y,bottom:panel.mcFilterPane.mcFilterBubble.y+17.3},tabs={top:rail.y,bottom:rail.y+rows*60},cards={top:panel.mcTileList.y,bottom:panel.mcTileList.y+panel.mcTileList.height};for(const scale of[.5,.75,1,1.25,1.6]){const toY=v=>106+v*scale;assert.ok(toY(search.bottom)<=toY(filter.top));assert.ok(toY(filter.bottom)<=toY(tabs.top));assert.ok(toY(tabs.bottom)<=toY(cards.top));assert.ok(toY(cards.bottom)<=toY(r.raw_y+r.raw_height));}const n=writes.length;for(let i=0;i<30;i++)once();assert.equal(writes.length,n);}")
 def test_subpixel_native_projection_is_exact_receipted_without_epsilon_or_drift(self):
  self.case("panel.GetTileListYTopOffset=()=>17.31;panel.mcPanelBackground.height=1220.021;panel.RefreshLayout();once();const r=apexSearch.geometry.list_layout;assert.equal(r.raw_y,17.3);assert.equal(r.applied_y,q(r.raw_y+r.search+r.rail));const n=writes.length;for(let i=0;i<30;i++)once();assert.equal(writes.length,n);assert.equal(r.raw_y,17.3);")
 def test_foreign_replacement_is_not_repaired_or_cleaned_through_old_record(self):
  self.case("panel.RefreshLayout();once();const r=apexSearch.geometry.list_layout,old=panel.mcTileList;panel.mcTileList=new NativeList();const n=writes.length;assert.equal(ApexCatalogListCurrent(r),false);assert.equal(ApexCatalogSearchListRestore(apexSearch.geometry),false);assert.equal(writes.length,n);assert.equal(old.y,137.3);assert.equal(panel.mcTileList.y,17.3);")

if __name__=='__main__':unittest.main()
