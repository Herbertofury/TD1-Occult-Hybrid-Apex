from pathlib import Path
import re,sys,subprocess,unittest
ROOT=Path(__file__).resolve().parents[1]
PROJECT=next(p for p in(ROOT,*ROOT.parents)if(p/'tools/cas_grid_budget.py').is_file())
sys.path[:0]=[str(ROOT/'tools'),str(PROJECT/'tests'),str(PROJECT/'tools')]
import cas_grid_featured as featured
import test_cas_grid_presentation as fixture
import json
NATIVE=json.loads((ROOT/'tests/fixtures/native_featured_asset_contract.json').read_text(encoding='utf-8'))

def main_source():
 fragment=(PROJECT/'Source/CASUi/catalog_grid_transaction_methods.as').read_text(encoding='utf-8')
 request=(PROJECT/'Source/CASUi/catalog_grid_budget_main_request.as').read_text(encoding='utf-8')
 cells=set(re.findall(r'lease.cell_type===(\w+)',request))
 imports=''.join('   import widgets.CAS.controls.'+name+';\n' for name in sorted(cells))
 return featured.inject_main('package widgets.CAS.Customizer {\n'+imports+'   public class CASCustomizerMain {\n'+fragment+'\n   }\n}\n')

def method(text,name):
 hit=re.search(r'(?:public|private)(?: static)? function '+name+r'\(([^\n]*)\)\s*:\s*[\w.]+\s*\{',text)
 if hit is None:raise AssertionError(name)
 at=hit.end();start=at;depth=1
 while depth:
  depth+=(text[at]=='{')-(text[at]=='}');at+=1
 body=text[start:at-1]
 body=re.sub(r'\b(var\s+\w+)\s*:\s*[\w.*<>]+',r'\1',body)
 body=re.sub(r'\s+as\s+[\w.]+','',body)
 body=re.sub(r'\bis\b','instanceof',body)
 params=re.sub(r':\s*[\w.]+','',hit.group(1))
 return params,body

def boot():
 old=fixture.stage
 try:fixture.stage=featured;helpers=fixture.javascript()
 finally:fixture.stage=old
 actual=NATIVE['cell_source']
 args,draw=method(actual,'Draw');draw=draw.replace('super.Draw(param1,param2);','nativeButtonDraw.call(this,param1,param2);')
 _,native_width=method(actual,'get width')
 tunables=NATIVE['tunables_source']
 width=re.search(r'FEATURED_FACE_LOOK_CELL_VIEW_WIDTH:Number = ([0-9.]+);',tunables).group(1)
 args0,load=method(NATIVE['image_utils_source'],'LoadSimThumbnail')
 args1,identity=method((ROOT/'Source/CASUi/catalog_featured_main_identity.as').read_text(),'ApexCatalogGridFeaturedIdentity')
 return fixture.NATIVE_MOCK.replace('const getTimer=()=>time;','const getTimer=()=>Math.trunc(time);')+helpers+fixture.BOOT+'''
function uint(v){return Number(v)>>>0;}
class CASFeaturedLook{constructor(id,packId=0){this.data_id=id;this.packId=packId;}}
const CASCustomizerTunables={FEATURED_FACE_LOOK_CELL_VIEW_WIDTH:'''+width+'''};
class FeaturedCell extends Cell{
 constructor(){super();this.scaleX=this.scaleY=1;this.mcIconAndMask=null;this.mcPackIcon={LoadImage(){},visible:false};}
 get width(){'''+native_width+'''}
 set width(value){super.width=value;}
}
function nativeButtonDraw(item){this.item=item;this.owner.atom('draw');if(this.owner.hooks.draw)this.owner.hooks.draw(this);}
const ImageUtils={SIM_THUMBNAIL_TYPE_FEATURED_LOOK:'l_',THUMBNAIL_SIZE_XLARGE:'x',SIM_THUMBNAIL_OUTFIT_DEFAULT:'_outfit',
 CreateSimImageUrl(type,id,size,index){return type+id+'_'+size+'_'+index;}};
ImageUtils.LoadSimThumbnail=function('''+args0+'''){with(ImageUtils){'''+load+'''}};
FeaturedCell.prototype.Draw=function('''+args+'''){'''+draw+'''};
function ApexCatalogGridFeaturedIdentity('''+args1+'''){'''+identity+'''}
function feature(id,look='41',pack=0){return {product:new CASFeaturedLook(look,pack),outfit:{data_id:String(id)}};}
function makeFeatured(n=40){const g=new NativeGrid(n,0);g.mCellType=FeaturedCell;g.donorMarker=false;
 g.mGridData.items=Array.from({length:n},(_,i)=>feature(1000+i));g.lease.panel_kind='featured';g.lease.cell_type=FeaturedCell;return g;}
function featureRequest(g,y=0,extra={}){return request(g,4,{viewHeight:100,scrollY:y,rowValidate:null,featuredRowIdentity:ApexCatalogGridFeaturedIdentity,stepBudgetClockContract:1,stepBudgetMilliseconds:1,...extra});}
const featureRendered=g=>g.mGridView.children.filter(c=>c.visible&&c.item).map(c=>c.item.product.data_id+':'+c.item.outfit.data_id);
function toPhase(g,phase){for(let i=0;i<2000&&g.ApexGridStatus().phase!==phase;i++)g.ApexGridStep(1,0);assert.equal(g.ApexGridStatus().phase,phase);}
'''

class FeaturedTests(unittest.TestCase):
 def case(self,source):
  result=subprocess.run(['node','-'],input=boot()+source,text=True,capture_output=True,encoding='utf-8',timeout=15)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
 def test_actual_native_draw_preserves_forced_same_uri_reload(self):
  self.case('''const g=makeFeatured();g.ApexGridBegin(featureRequest(g));assert.equal(bounded(g).phase,'done');
const c=g.mCells[0],resource=c.mcImage.resourceId;c.mcImage.ready=true;g.delayImages=true;c.Draw(c.item);
assert.equal(c.mcImage.resourceId,resource);assert.equal(c.mcImage.ready,false);''')
 def test_same_look_different_outfits_have_distinct_primitive_identity(self):
  self.case('''const g=makeFeatured();g.ApexGridBegin(featureRequest(g));assert.equal(bounded(g).phase,'done');
const ids=featureRendered(g);assert.ok(ids.includes('41:1000'));assert.ok(ids.includes('41:1001'));
const item=g.mGridData.items[0],snapshot=g.ApexGridFeaturedIdentity(item);
assert.deepEqual(Object.keys(snapshot).sort(),['look_id','outfit_id','pack_id','schema']);
assert.equal(snapshot.look_id,'41');assert.equal(snapshot.outfit_id,'1000');item.outfit.data_id='999';
assert.equal(snapshot.outfit_id,'1000');assert.equal(g.ApexGridFeaturedSame(snapshot,g.ApexGridFeaturedIdentity(item)),false);''')
 def test_delayed_forced_textures_do_not_blank_or_remap_current_bank(self):
  self.case('''const g=makeFeatured();g.ApexGridBegin(featureRequest(g));assert.equal(bounded(g).phase,'done');
const old=g.mCells.slice(),ids=featureRendered(g);g.delayImages=true;g.ApexGridBegin(featureRequest(g,150));toPhase(g,'textures');
assert.deepEqual(g.mCells,old);assert.deepEqual(featureRendered(g),ids);assert.equal(g.mGridView.mouseChildren,false);
for(const c of old)assert.equal(g.ApexGridNativeGuard('input',{currentTarget:c}),true);
assert.ok(g.apexGridState.presentation.stageCells.every(c=>!c.visible));g.ApexGridStep(64,0);assert.deepEqual(featureRendered(g),ids);
stagedReady(g);assert.equal(bounded(g).phase,'done');assert.notDeepEqual(g.mCells,old);assert.notDeepEqual(featureRendered(g),ids);''')
 def test_changed_look_outfit_or_pack_after_native_selection_cannot_publish_wrong_row(self):
  for field in ('look','outfit','pack'):
   self.case('''const g=makeFeatured();g.mGridData.selection.add(0);let changed=false;
g.hooks.selection=()=>{if(changed)return;changed=true;const item=g.mGridData.items[0];'''+{
    'look':"item.product.data_id='99';",'outfit':"item.outfit.data_id='999';",'pack':"item.product.packId=4;"}[field]+'''};
g.ApexGridBegin(featureRequest(g));for(let i=0;i<2000&&!changed;i++)g.ApexGridStep(1,0);assert.equal(changed,true);
const job=g.apexGridState.job;assert.equal(job.dirty,true);assert.equal(job.publishes,0);''')
 def test_featured_never_reads_product_only_fields(self):
  self.case('''const g=makeFeatured();for(const item of g.mGridData.items){
 for(const field of ['data_id','GetVariationOrBaseId','body_type','menu_state'])Object.defineProperty(item,field,{get(){throw Error('wrong schema field '+field);}});}
g.ApexGridBegin(featureRequest(g));assert.equal(bounded(g).phase,'done');assert.ok(featureRendered(g).length>0);''')
 def test_changed_schema_callback_or_unknown_rows_fail_without_publication(self):
  self.case('''const g=makeFeatured();g.mGridData.items[0]={product:{data_id:'41'},outfit:{data_id:'1000'}};
g.ApexGridBegin(featureRequest(g));const result=bounded(g);assert.ok(result.error.includes('schema differs'));assert.equal(result.publishes,0);''')
  self.case('''const g=makeFeatured();g.ApexGridBegin(featureRequest(g));let j=g.apexGridState.job;
for(let i=0;i<2000&&j.phase!=='selection';i++)g.ApexGridStep(1,0);assert.equal(j.phase,'selection');
g.apexGridState.request.featuredRowIdentity=null;g.ApexGridStep(1,0);assert.equal(j.dirty,true);assert.equal(j.publishes,0);''')
 def test_late_foreign_texture_callback_does_not_publish(self):
  self.case('''const g=makeFeatured();g.ApexGridBegin(featureRequest(g));bounded(g);const ids=featureRendered(g);
g.delayImages=true;g.ApexGridBegin(featureRequest(g,150));toPhase(g,'textures');stagedReady(g);
const cell=g.apexGridState.presentation.stageCells[0];cell.mcImage.resourceId='older-outfit';
g.ApexGridStep(64,0);assert.notEqual(g.ApexGridStatus().phase,'done');assert.deepEqual(featureRendered(g),ids);
cell.mcImage.resourceId=g.apexGridState.presentation.expected[cell].display;assert.equal(bounded(g).phase,'done');''')
 def test_native_redraw_preserves_same_uri_refresh_on_hidden_staging_bank(self):
  self.case('''const g=makeFeatured();g.ApexGridBegin(featureRequest(g));bounded(g);
for(let pass=0;pass<3;pass++){
 const old=g.mCells.slice(),ids=featureRendered(g);g.delayImages=true;
 assert.equal(g.ApexGridNativeGuard('redraw',{currentTarget:g.mCells[0]}),true);toPhase(g,'textures');
 assert.deepEqual(g.mCells,old);assert.deepEqual(featureRendered(g),ids);
 assert.ok(g.apexGridState.presentation.stageCells.filter(c=>c.item).every(c=>c.mcImage.ready===false));
 stagedReady(g);assert.equal(bounded(g).phase,'done');assert.deepEqual(featureRendered(g),ids);
}''')
 def test_owner_retirement_during_featured_image_wait_preserves_only_preceding_bank(self):
  self.case('''const g=makeFeatured();g.ApexGridBegin(featureRequest(g));bounded(g);
const old=g.mCells.slice(),ids=featureRendered(g);g.delayImages=true;g.ApexGridBegin(featureRequest(g,150));toPhase(g,'textures');
g.lease.active=false;stagedReady(g);for(let i=0;i<100&&g.ApexGridStatus().phase!=='cancelled';i++)g.ApexGridStep(64,0);
assert.equal(g.ApexGridStatus().phase,'cancelled');assert.deepEqual(g.mCells,old);assert.deepEqual(featureRendered(g),ids);
assert.equal(g.mGridView.mouseChildren,false);assert.equal(g.ApexGridNativeGuard('input',{currentTarget:old[0]}),true);''')
 def test_current_product_path_keeps_existing_variant_and_favorite_fences(self):
  self.case('''const g=new NativeGrid(40,0);g.ApexGridFeaturedIdentity=function(){throw Error('product path must not invoke Featured helper');};
g.ApexGridBegin(request(g,4,{viewHeight:100}));assert.equal(bounded(g).phase,'done');
assert.equal(g.mCells[0].item.data_id,'item-0');g.mGridData.selection.add(0);let changed=false;
g.hooks.selection=c=>{if(!changed){changed=true;c.dccFavoriteProductId='foreign';}};
g.ApexGridNativeGuard('selection');for(let i=0;i<2000&&!changed;i++)g.ApexGridStep(1,0);
assert.equal(changed,true);assert.equal(g.apexGridState.job.dirty,true);''')

class FeaturedMainTests(unittest.TestCase):
 def case(self,boot,source):
  result=subprocess.run(['node','-'],input=boot+source,text=True,capture_output=True,encoding='utf-8',timeout=15)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
 def test_exact_featured_panel_grid_feed_and_cell_classes_are_required(self):
  source=main_source();args,body=method(source,'ApexCatalogGridProductPanel')
  body=body.replace(' as Class','')
  setup='''const assert=require('node:assert/strict');
const stage={};let apexCatalogDisplayFaults=null;
class SelectableRecyclingGridLayout{constructor(){this.cell=CASFeaturedFacelookCellView;this.feed=new FeaturedFaceLookDataFeed();}get GetCellView(){return this.cell;}GetDataFeed(){return this.feed;}}
class FeaturedFaceLookDataFeed{}class CASFeaturedFacelookCellView{}
class CASBodyPanelCellView{}class CASFacePanelCellView{}class CASGenericCatalogVariantCellView{}class CASBreedCatalogCellView{}
const mcClothingPanel={},mcBodyModPanel={},mcFaceModPanel={},mcGenericCatalogPanel={};
const grid=new SelectableRecyclingGridLayout(),mcFeaturedFaceLookPanel={stage,mcTileList:{mGridLayout:grid}};
function ApexCatalogDisplayFaulted(){return true;}
function ApexCatalogGridProductPanel('''+args+'''){'''+body+'''}
'''
  self.case(setup,'''assert.equal(ApexCatalogGridProductPanel(mcFeaturedFaceLookPanel),'featured');
grid.feed={};assert.equal(ApexCatalogGridProductPanel(mcFeaturedFaceLookPanel),'');grid.feed=new FeaturedFaceLookDataFeed();
grid.cell=class ForeignCell{};assert.equal(ApexCatalogGridProductPanel(mcFeaturedFaceLookPanel),'');grid.cell=CASFeaturedFacelookCellView;
mcFeaturedFaceLookPanel.stage={};assert.equal(ApexCatalogGridProductPanel(mcFeaturedFaceLookPanel),'');mcFeaturedFaceLookPanel.stage=stage;
apexCatalogDisplayFaults={};assert.equal(ApexCatalogGridProductPanel(mcFeaturedFaceLookPanel),'');apexCatalogDisplayFaults=null;
assert.equal(ApexCatalogGridProductPanel({stage,mcTileList:{mGridLayout:grid}}),'');''')
 def test_measurement_and_normal_requests_keep_own_identity_callback_and_guards(self):
  import test_cas_grid_scroll_main as main
  source=main_source();args,body=method(source,'ApexCatalogGridRequest')
  setup=main.BOOT+'''class CASFeaturedFacelookCellView{}function ApexCatalogGridFeaturedIdentity(){}
function ApexCatalogGridRequest('''+args+'''){'''+body+'''}
'''
  self.case(setup,'''lease.panel_kind='featured';lease.cell_type=CASFeaturedFacelookCellView;
for(const bootstrap of [false,true]){if(bootstrap)retained=null;const r=ApexCatalogGridRequest(lease);
assert.equal(r.bootstrap,bootstrap);assert.equal(r.owner,lease);assert.equal(r.validate,ApexCatalogGridValidate);
assert.equal(r.inputValidate,ApexCatalogGridInput);assert.equal(r.rowValidate,null);
assert.equal(r.featuredRowIdentity,ApexCatalogGridFeaturedIdentity);assert.equal(r.scrollOnlyPositionContract,0);assert.equal(r.stepBudgetClockContract,1);assert.equal(r.stepBudgetMilliseconds,1);}
current=false;assert.equal(ApexCatalogGridRequest(lease),null);''')

if __name__=='__main__':unittest.main()
