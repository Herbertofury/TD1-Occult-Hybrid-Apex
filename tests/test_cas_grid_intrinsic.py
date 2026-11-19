"""Execute production intrinsic helpers; no game, generated source or private fixture needed."""
from pathlib import Path
import os,re,sys,subprocess,unittest
ROOT=Path(os.environ.get('APEX_INTRINSIC_SOURCE_ROOT',Path(__file__).resolve().parents[1])).resolve()
REPO=next(p for p in Path(__file__).resolve().parents if(p/'tools/dbpf_build.py').is_file())
sys.path[:0]=[str(ROOT/'tools'),str(REPO/'tools')]
import cas_grid_intrinsic as contract
import cas_grid_pool as pool
stage=contract.stage

def main_predecessor():
 # Use the production native Main request producer and the complete real
 # preceding source transforms, rather than a copied or proposed AS method.
 names=('CASClothingPanelCellViewMain','CASClothingPanelCellViewCommon','CASClothingPanelCellViewSkinSpecularity','CASBodyPanelCellView','CASFacePanelCellView','CASGenericCatalogVariantCellView','CASBreedCatalogCellView')
 imports=''.join('   import widgets.CAS.controls.'+n+';\n'for n in names)
 source='package widgets.CAS.Customizer {\n'+imports+'   public class CASCustomizerMain {\n'+'\n'.join((ROOT/'Source/CASUi'/n).read_text(encoding='utf-8')for n in ('catalog_grid_transaction_methods.as','catalog_trace_methods.as'))+'\n   }\n}\n'
 return contract.main_previous.inject_main(source)

def javascript():
 source=stage.helpers();out=[]
 for name in (*stage.REPLACED,*stage.ADDED):
  a,b=pool.method_extent(source,name);text=source[a:b];m=re.search(r'function (\w+)\(([^)]*)\)\s*:\s*[\w.<>]+\s*\{',text);body=text[m.end():-1]
  body=re.sub(r'\b(var\s+\w+)\s*:\s*[\w.*<>]+',r'\1',body);body=re.sub(r'\s+as\s+\w+','',body);body=re.sub(r'\bis\b','instanceof',body)
  body=re.sub(r'for each\(var (\w+) in ([^\n]+)\)',r'for(var \1 of \2)',body);body=re.sub(r'catch\((\w+):(?:Error|\*)\)',r'catch(\1)',body)
  params=re.sub(r':\s*[\w.<>]+','',m.group(2));out.append('Grid.prototype.'+name+'=function('+params+'){with(this){'+body+'}};')
 return '\n'.join(out)

BOOT=r'''
const assert=require('node:assert/strict');const int=x=>Number(x)|0;int.MAX_VALUE=2147483647;
let serial=0,widthReads=0;function getQualifiedClassName(v){return typeof v==='function'?v.qname:v.constructor.qname;}
class Cell{static qname='widgets.CAS.controls::CASClothingPanelCellViewMain';constructor(scale=.35,natural=107){this.id=++serial;this.scaleX=this.scaleY=scale;this.nativeWidth=natural;this.mcHitArea={height:147};this.quantized=true;}
 toString(){return 'cell-'+this.id;}getChildByName(){return null;}getBounds(){return {height:this.mcHitArea?this.mcHitArea.height:147};}
 get width(){widthReads++;return this.quantized?Math.floor(this.nativeWidth*this.scaleX*20)/20:this.nativeWidth*this.scaleX;}}
class OtherNative extends Cell{static qname='widgets.CAS.controls::CASBodyPanelCellView';}
class Custom extends Cell{static qname='owner.custom::CustomCard';}
class ForeignDomain{static qname=Cell.qname;constructor(){this.id=++serial;this.scaleX=this.scaleY=.35;this.mcHitArea={height:147};}getChildByName(){return null;}get width(){widthReads++;return 200*.35;}toString(){return 'cell-'+this.id;}}
class Rectangle{}class Margin{}
class Grid{static qname='olympus.layout::SelectableRecyclingGridLayout';constructor(){this.mCellType=Cell;this.mGridData={};this.mGridView={};this.events=[];
 const owner={active:true,generation:1,cell_type:Cell,session:1,sim_id:'arbitrary-sim',household_id:'arbitrary-household',owner:'native/1',layer:0,native_kind:1,shell_kind:1,native_mask:127,native_generation:'arbitrary-generation',outfit_type:9,outfit_index:0,state:40};
 const panel={};this.apexGridState={armed:true,owner,ownerGeneration:1,feed:this.mGridData,view:this.mGridView,panel,intrinsics:{},revision:1,job:{phase:'done',generation:1,dirty:false},ready:{},deferredEvents:0};
 this.apexGridState.request={intrinsicGeometryContract:1,intrinsicGeometrySource:'exact-native-constructor-v1',intrinsicGeometryClass:Cell,owner,panel,scale:.35};}
 ApexTxnNotify(j,kind){this.events.push(kind);}ApexGridValid(){return true;}}
function capture(g,scale=.35,natural=107,C=Cell){const cell=new C(scale,natural);g.ApexGridCaptureNewCell(cell);return cell;}
'''

class IntrinsicTests(unittest.TestCase):
 def case(self,code):
  p=subprocess.run(['node','-'],input=BOOT+javascript()+code,capture_output=True,text=True,timeout=15)
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
 def test_captured_scale_sequence_240_constructors_only_measure_once(self):
  self.case('''const g=new Grid(),a=.7371648096160528,b=.73748684866372;capture(g,a);const width=g.apexGridState.naturalWidth,fit=(537.3531192772556-40-24)/(6*width);
 for(let n=0;n<239;n++){const c=capture(g,n%2?b:a);assert.equal(g.apexGridState.intrinsics[c].width,width);assert.equal((537.3531192772556-40-24)/(6*g.apexGridState.naturalWidth),fit);}
 assert.equal(widthReads,1);assert.equal(g.apexGridState.intrinsicGeometryCaptures,1);assert.equal(g.apexGridState.intrinsicGeometryReuses,239);''')
 def test_recorded_normalized_measurement_drift_changes_only_legacy_path(self):
  self.case('''const legacy=new Grid();legacy.apexGridState.request.intrinsicGeometryContract=0;const guarded=new Grid();const samples=[[.7371648096160528,107.02109693394],[.73748684866372,106.9743639349732]];
 for(const [s,n]of samples)for(const g of [legacy,guarded]){const c=new Cell(s,n);c.quantized=false;g.ApexGridCaptureNewCell(c);}
 assert.equal(legacy.apexGridState.naturalWidth,samples[1][1]*samples[1][0]/samples[1][0]);assert.equal(guarded.apexGridState.naturalWidth,samples[0][1]*samples[0][0]/samples[0][0]);''')
 def test_columns_scale_spacing_panel_width_are_policy_and_keep_native_geometry(self):
  self.case('''const g=new Grid();capture(g);const original=g.apexGridState.naturalWidth;
 for(const columns of [2,12,32])for(const scale of [.2,1,1.6]){Object.assign(g.apexGridState.request,{columns,scale,gapX:32,gapY:0,width:40,viewWidth:1800});capture(g,scale);assert.equal(g.apexGridState.naturalWidth,original);}assert.equal(widthReads,1);''')
 def test_all_owner_category_outfit_primitive_fields_reseed_scope(self):
  for key in ['session','sim_id','household_id','owner','layer','native_kind','shell_kind','native_mask','native_generation','outfit_type','outfit_index','state']:
   self.case('const g=new Grid();capture(g);const s=g.apexGridState,old=s.intrinsicGeometry,o=s.owner;o.'+key+'=typeof o.'+key+"==='number'?o."+key+"+1:'new-value';capture(g,.73748684866372);assert.notEqual(s.intrinsicGeometry,old);assert.equal(widthReads,2);")
 def test_owner_feed_view_panel_and_lease_generation_reseed(self):
  for mutation in ['s.owner=Object.assign({},s.owner);s.request.owner=s.owner;','g.mGridData={};s.feed=g.mGridData;','g.mGridView={};s.view=g.mGridView;','s.panel={};s.request.panel=s.panel;','s.owner.generation++;s.ownerGeneration++;']:
   self.case('const g=new Grid();capture(g);const s=g.apexGridState,old=s.intrinsicGeometry;'+mutation+'capture(g,.73748684866372);assert.notEqual(s.intrinsicGeometry,old);assert.equal(widthReads,2);')
 def test_native_class_and_same_class_reset_keep_original_callback(self):
  for C in ['Cell','OtherNative']:
   self.case('const g=new Grid();capture(g);const s=g.apexGridState,old=s.intrinsicGeometry;assert.equal(g.ApexGridNativeSetCellView('+C+',null,false),true);s.request.intrinsicGeometryClass='+C+';s.owner.cell_type='+C+';capture(g,.73748684866372,200,'+C+");assert.notEqual(s.intrinsicGeometry,old);assert.equal(widthReads,2);assert.deepEqual(g.events,['update']);")
 def test_foreign_bounds_falls_back_until_native_geometry_reset(self):
  self.case('''const g=new Grid();capture(g);assert.equal(g.ApexGridNativeGuard('bounds',new Rectangle()),true);assert.equal(g.apexGridState.intrinsicGeometryForeign,true);capture(g,.73748684866372);capture(g,.2);assert.equal(widthReads,3);assert.deepEqual(g.events,['position']);g.ApexGridNativeSetCellView(Cell,null,false);capture(g);capture(g,.2);assert.equal(widthReads,4);''')
 def test_custom_subclass_foreign_asset_and_unknown_contract_keep_original(self):
  for mutation,cell in [('', 'new Custom()'),('','new ForeignDomain()'),('s.request.intrinsicGeometryContract=0;','new Cell()'),('s.request.intrinsicGeometrySource="unknown";','new Cell()'),('s.request.intrinsicGeometryClass=OtherNative;','new Cell()'),('s.owner.active=false;','new Cell()'),('s.ownerGeneration++;','new Cell()')]:
   self.case('const g=new Grid(),s=g.apexGridState;capture(g);const old=s.intrinsicGeometry;'+mutation+'g.ApexGridCaptureNewCell('+cell+');assert.equal(widthReads,2);assert.equal(s.intrinsicGeometry,old);')
 def test_height_aspect_change_declines_until_native_reset(self):
  for mutation in ['c.mcHitArea.height=148;','c.scaleY=c.scaleX*2;']:
   self.case('const g=new Grid();capture(g);const c=new Cell();'+mutation+'g.ApexGridCaptureNewCell(c);assert.equal(g.apexGridState.intrinsicGeometryForeign,true);assert.equal(widthReads,2);capture(g);assert.equal(widthReads,3);')
 def test_bad_first_measurement_does_not_latch_and_original_failure_survives(self):
  self.case('''const g=new Grid(),c=new Cell();c.nativeWidth=NaN;assert.throws(()=>g.ApexGridCaptureNewCell(c),/Native cell intrinsic metrics unavailable/);assert.equal(g.apexGridState.intrinsicGeometry,null);capture(g);assert.equal(g.apexGridState.intrinsicGeometryCaptures,1);''')
 def test_unarmed_and_custom_grid_preserve_original_path(self):
  self.case('''const g=new Grid();g.apexGridState.armed=false;capture(g);assert.equal(widthReads,0);g.apexGridState.armed=true;Object.setPrototypeOf(g,Object.assign(Object.create(Grid.prototype),{constructor:{qname:'custom-grid'}}));capture(g);assert.equal(widthReads,1);assert.equal(g.apexGridState.intrinsicGeometry,undefined);''')


class MainCapabilityTests(unittest.TestCase):
 def body(self):
  text=main_predecessor()
  text=stage.extend_main(text);a,b=pool.method_extent(text,'ApexCatalogGridRequest');text=text[a:b];m=re.search(r'function \w+\(([^)]*)\)\s*:\s*\w+\s*\{',text)
  return re.sub(r'\b(var\s+\w+)\s*:\s*[\w.*<>]+',r'\1',text[m.end():-1])
 def case(self,code):
  boot='''const assert=require('node:assert/strict'),int=x=>x|0;const CASCustomizerMain={};
const CASClothingPanelCellViewMain=class{},CASClothingPanelCellViewCommon=class{},CASClothingPanelCellViewSkinSpecularity=class{},CASBodyPanelCellView=class{},CASFacePanelCellView=class{},CASGenericCatalogVariantCellView=class{},CASBreedCatalogCellView=class{},CASFeaturedFacelookCellView=class{};
const classes=[CASClothingPanelCellViewMain,CASClothingPanelCellViewCommon,CASClothingPanelCellViewSkinSpecularity,CASBodyPanelCellView,CASFacePanelCellView,CASGenericCatalogVariantCellView,CASBreedCatalogCellView];
const callback=()=>{};let retained=null;const env={apexCatalogTrace:null,ApexCatalogGridLeaseCurrent:()=>true,ApexCardStateFor:()=>retained,ApexCatalogGridValidate:callback,ApexCatalogGridInput:callback,ApexCatalogGridProductRow:callback,ApexCatalogGridFeaturedIdentity:callback};
function lease(C){const panel={mcTileList:{mScrollerView:{width:700,height:1000},mSlider:{Value:0}}};return {phase:'bound',panel,grid:{GetCellPadding:()=>({mLeft:0,mTop:0})},cell_type:C,panel_kind:'clothing'};}
'''
  fn='const run=function(lease){with(env){'+self.body()+'}};'
  p=subprocess.run(['node','-'],input=boot+fn+code,capture_output=True,text=True,timeout=15);self.assertEqual(p.returncode,0,p.stdout+p.stderr)
 def test_both_real_producers_issue_independent_exact_native_class_capability(self):
  self.case('''for(const C of classes){const l=lease(C);retained=null;let r=run(l);assert.equal(r.intrinsicGeometryContract,1);assert.equal(r.intrinsicGeometryClass,C);assert.equal(r.intrinsicGeometrySource,'exact-native-constructor-v1');
retained={geometry:{grid:l.grid,panel:l.panel},layout:{scale:.35,card_width:40,card_height:50,columns:12,gap_x:4,gap_y:4}};r=run(l);assert.equal(r.intrinsicGeometryContract,1);assert.equal(r.intrinsicGeometryClass,C);assert.equal(r.bootstrap,false);}''')
 def test_custom_subclass_foreign_named_class_and_featured_do_not_inherit_permission(self):
  self.case('''for(const C of [class extends CASClothingPanelCellViewMain{},class{},CASFeaturedFacelookCellView]){const l=lease(C);l.panel_kind='featured';retained=null;const r=run(l);assert.equal(r.intrinsicGeometryContract,0);assert.equal(r.intrinsicGeometryClass,null);}''')
 def test_unbound_or_stale_scope_has_no_capability(self):
  self.case("const l=lease(classes[0]);l.phase='bootstrap';assert.equal(run(l),null);l.phase='bound';env.ApexCatalogGridLeaseCurrent=()=>false;assert.equal(run(l),null);")
 def test_all_preceding_main_tokens_survive_the_two_new_field_groups(self):
  before=main_predecessor();after=stage.extend_main(before)
  insert=',intrinsicGeometryContract:nativeCardContract,\n               intrinsicGeometryClass:nativeCardContract==1 ? lease.cell_type : null,\n               intrinsicGeometrySource:"exact-native-constructor-v1"'
  self.assertEqual(after.count(insert),2);self.assertEqual(after.replace(insert,''),before)

if __name__=='__main__':unittest.main()
