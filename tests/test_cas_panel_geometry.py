"""Execute production catalogue geometry against native widget/viewport fixtures.

These tests prove geometry and ownership contracts, not rendered FPS.
"""
import json
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
AS=ROOT/'Source/CASUi'


def js(name,args='',file='catalog_panel_geometry_methods.as',public=False):
    source=(AS/file).read_text(encoding='utf-8')
    match=re.search(r'(?:private|public) function '+name+r'\([^\n]*',source)
    if not match:raise AssertionError(name)
    start=source.index('{',match.end());depth=1;at=start+1
    # The staged methods do not contain braces in string literals.
    while depth:
        if source[at]=='{':depth+=1
        if source[at]=='}':depth-=1
        at+=1
    body=source[start+1:at-1]
    body=re.sub(r'\b(var\s+\w+)\s*:\s*[\w.]+',r'\1',body)
    body=re.sub(r'\s+as\s+flash\.[\w.]+','',body)
    body=re.sub(r'(\w+) is (flash\.[\w.]+)',r'\1 instanceof \2',body)
    # AS type casts retain identity; invoking the JS class would construct a
    # different object (or throw). The production instanceof gate stays intact.
    body=body.replace('flash.display.Sprite(display).hitArea','display.hitArea')
    # AS foreach locals have function scope. Retain var instead of accidentally
    # creating globals, which can also collide with a caller's lexical bindings.
    body=re.sub(r'for each\((?:var )?(\w+) in ([^\n]+?)\)\s*\{',r'for(var \1 of \2) {',body)
    body=body.replace('for(var saved of apexPanelGeometry)', 'for(var saved of Object.values(apexPanelGeometry))')
    return 'function '+name+'('+args+'){'+body+'}\n'


BASE=r'''
const assert=require('node:assert/strict');
class Point {constructor(x=0,y=0){this.x=x;this.y=y;}}
class Rectangle {constructor(x=0,y=0,width=0,height=0){Object.assign(this,{x,y,width,height});}clone(){return new Rectangle(this.x,this.y,this.width,this.height);}}
class Event {constructor(type){this.type=type;}stopImmediatePropagation(){}preventDefault(){}}
Object.assign(Event,{DEACTIVATE:'deactivate',MOUSE_LEAVE:'leave',ENTER_FRAME:'frame'});
class MouseEvent extends Event {constructor(stageX=0){super('move');this.stageX=stageX;}}
Object.assign(MouseEvent,{MOUSE_MOVE:'move',MOUSE_UP:'up',MOUSE_DOWN:'down'});
class Sprite {
 constructor(name=''){Object.assign(this,{name,parent:null,x:0,y:0,scaleX:1,scaleY:1,visible:true,hitArea:null,children:{},naturalWidth:100,naturalHeight:100});
 this.graphics={beginFill(){},drawRoundRect(){},drawRect(){},endFill(){},lineStyle(){},moveTo(){},lineTo(){},drawCircle(){}};}
 get stage(){return this._stage||(this.parent?this.parent.stage:null);}set stage(v){this._stage=v;}
 get width(){return this.naturalWidth*this.scaleX;}set width(v){this.scaleX=v/this.naturalWidth;}
 get height(){return this.naturalHeight*this.scaleY;}set height(v){this.scaleY=v/this.naturalHeight;}
 addChild(c){if(c.parent)c.parent.removeChild(c);this.children[c.name]=c;c.parent=this;return c;}
 removeChild(c){delete this.children[c.name];c.parent=null;}
 getChildByName(n){return this.children[n]||null;}
 localToGlobal(p){let v=new Point(p.x*this.scaleX+this.x,p.y*this.scaleY+this.y);return this.parent?this.parent.localToGlobal(v):v;}
 globalToLocal(p){let v=this.parent?this.parent.globalToLocal(p):p;return new Point((v.x-this.x)/this.scaleX,(v.y-this.y)/this.scaleY);}
 getBounds(target){let a=this.localToGlobal(new Point(0,0));let b=this.localToGlobal(new Point(this.naturalWidth,this.naturalHeight));return new Rectangle(a.x,a.y,b.x-a.x,b.y-a.y);}
 get mouseX(){return this.globalToLocal(new Point(stage.mouseX,stage.mouseY)).x;}
 addEventListener(){}removeEventListener(){}
}
class Dictionary {constructor(){return {};}}
class Margin {constructor(top,right,bottom,left){Object.assign(this,{mTop:top,mRight:right,mBot:bottom,mLeft:left});}get Horizontal(){return this.mLeft+this.mRight;}get Vertical(){return this.mTop+this.mBot;}}
class TooltipObject {Initialize(){}Shutdown(){}}
var flash={geom:{Point,Rectangle},display:{Sprite,DisplayObject:Sprite},events:{Event,MouseEvent},utils:{Dictionary,getTimer:()=>10}};
var olympus={core:{widget:{Margin}}};
function int(v){return Math.trunc(v);}int.MAX_VALUE=2147483647;
var stage={stageWidth:1800,stageHeight:1200,mouseX:0,mouseY:0,addEventListener(){},removeEventListener(){}};
var navigation=null;var LayoutAPI={mLayoutMgr:{},get StageWidth(){return stage.stageWidth;},GetLoadedWidgetByName(name){return name==='CASNavigation'?navigation:null;}};
let seq=0;
function panel(name){let p=new Sprite(name);p.stage=stage;p.x=900;p.y=40;p.grid={toString:()=>name};
 let mask=new Sprite('mask');mask.stage=stage;mask.x=900;mask.y=200;mask.naturalWidth=300;mask.naturalHeight=700;
 p.mcTileList={x:20,y:160,height:700,mGridLayout:p.grid,mScrollerView:{mcMask:mask},
 mSlider:{getBounds(){return new Rectangle(p.mcPanelBackground.width-11.5,160,13,700);}}};p.mcPanelBackground={width:300};return p;}
var mcClothingPanel=panel('clothing'),mcBodyModPanel=panel('body'),mcFaceModPanel=panel('face'),
 mcGenericCatalogPanel=panel('generic'),mcFeaturedFaceLookPanel=panel('featured'),mcSkinColorPanel=panel('skin');
var mCurrentPanel=mcClothingPanel,mcGhostToggle=null,mcWingToggle=null,mcBodyModSliderPanel=null,mcDetailedEditModePanel=null;
var apexPanels=null,apexCatalogUi=null,apexCompanion=null;
var apexPanelGeometry=null,apexCardGeometry=null,apexCardLayout={columns:12,scale:1,width:300},apexCatalogSignature='',apexCardReflowAttempts=0,apexCatalogFrameCells=null;
var apexColumns={root:null,track:null,fallback_track:null,width_handle:null,preferred_width:0,width_anchor:NaN,resize:null,tooltips:[],scale_drag:false,drag:false,stage:null,scale_stage:null};
var apexCatalogPrefs={columns:12},apexCardPrefs={scale:1,gap_x:4,gap_y:4};
var mCurrSimInfo={simId:"fixture-owned-sim"};
navigation=new Sprite('nav');navigation.stage=stage;navigation.WidgetName='CASNavigation';navigation.btnPlay=null;navigation.btnCancel=null;
var apexCatalogBinding={maximum:262},mDynamicResizeHandle={visible:true,alpha:.78};
function HandleDynamicResizeMoveRight(){}function HandleDynamicResizeUpRight(){}
function HandleThumbnailScaleMove(){}function HandleThumbnailScaleUp(){}function HandleThumbnailScaleFrame(){}
function ApexColumnsUp(){apexColumns.drag=false;}function ApexColumnsScaleEnd(){apexColumns.scale_drag=false;}
function ApexColumnsSave(){apexColumns.persist=true;}
'''


@unittest.skipUnless(shutil.which('node'),'Node required')
class GeometryTests(unittest.TestCase):
    def execute(self,source):
        result=subprocess.run(['node'],input=BASE+source,capture_output=True,text=True,encoding='utf-8',timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def common(self):
        out=''
        for name,args in [('ApexCatalogPanelKey','panel'),('ApexCatalogPanelKind','panel'),('ApexCatalogOptional','owner,name'),
                          ('ApexCardStateFor','grid'),('ApexCardActivate','panel,grid'),
                          ('ApexCatalogVisibleRect','display'),('ApexCatalogSafeRight','left,top,bottom,viewport,minimum,regions'),
                          ('ApexCatalogNavigationRects','probe=null'),('ApexCatalogWidthEnvelope','panel,probe=null'),('ApexCatalogWidthRequest','panel'),('ApexCatalogWidthMode','')]:
            out+=js(name,args)
        return out

    def test_all_six_actual_native_catalogues_and_no_unknown_panel(self):
        self.execute(self.common()+'''
for(const p of [mcClothingPanel,mcBodyModPanel,mcFaceModPanel,mcGenericCatalogPanel,mcFeaturedFaceLookPanel]){
 mCurrentPanel=p;assert.equal(ApexCatalogPanelKind(p),'cards');p.visible=false;assert.equal(ApexCatalogPanelKind(p),'');p.visible=true;}
mCurrentPanel=mcSkinColorPanel;assert.equal(ApexCatalogPanelKind(mCurrentPanel),'swatches');
let unknown=panel('unknown');mCurrentPanel=unknown;assert.equal(ApexCatalogPanelKind(unknown),'');
mCurrentPanel=mcBodyModPanel;assert.equal(ApexCatalogPanelKind(mcClothingPanel),'');
mcBodyModPanel.stage={};assert.equal(ApexCatalogPanelKind(mcBodyModPanel),'');
assert.equal(ApexCatalogOptional(mcGenericCatalogPanel,'btnRandomize'),null);
''')

    def test_retained_grid_state_avoids_hidden_pool_restore_and_midtransaction_theft(self):
        self.execute(self.common()+'''
apexCardGeometry={panel:mcClothingPanel,grid:mcClothingPanel.grid,applying:false};
const clothing=apexCardGeometry;apexCardLayout={columns:12,scale:.4};apexCatalogSignature='original-clothing';
mCurrentPanel=mcBodyModPanel;assert.equal(ApexCardActivate(mCurrentPanel,mCurrentPanel.grid),true);
assert.equal(apexCardGeometry,null);assert.equal(ApexCardStateFor(mcClothingPanel.grid).geometry,clothing);
assert.equal(ApexCardStateFor(mcClothingPanel.grid).signature,'original-clothing');
apexCardGeometry={panel:mCurrentPanel,grid:mCurrentPanel.grid,applying:true};
mCurrentPanel=mcClothingPanel;assert.equal(ApexCardActivate(mCurrentPanel,mCurrentPanel.grid),false);
apexCardGeometry.applying=false;assert.equal(ApexCardActivate(mCurrentPanel,mCurrentPanel.grid),true);
assert.equal(apexCardGeometry,clothing);assert.equal(apexCatalogSignature,'original-clothing');
assert.equal(apexCardLayout.columns,12);assert.equal(apexCardLayout.scale,.4);
''')

    def test_retained_geometry_is_bounded_by_native_panels_and_idle_reads_reuse_same_state_object(self):
        self.execute(self.common()+'''
mCurrentPanel=mcBodyModPanel;
for(let i=0;i<100;i++){
 const grid={id:i};mCurrentPanel.mcTileList.mGridLayout=grid;
 assert.equal(ApexCardActivate(mCurrentPanel,grid),true);
 apexCardGeometry={panel:mCurrentPanel,grid};apexCardLayout={columns:12};
 const first=ApexCardStateFor(grid);for(let j=0;j<8;j++)assert.equal(ApexCardStateFor(grid),first);
 assert.equal(Object.keys(apexPanelGeometry).length,1);
}
''')

    def test_safe_right_stops_at_obstacles_and_never_uses_space_left_of_avatar_anchor(self):
        self.execute(self.common()+'''
let regions=[{x:0,y:0,width:900,height:1200},{x:1470,y:200,width:90,height:400},
 {x:1200,y:0,width:300,height:100},{x:0,y:1128,width:1800,height:72}];
assert.equal(ApexCatalogSafeRight(900,200,1000,1800,80,regions),562);
assert.equal(ApexCatalogSafeRight(900,200,1000,1800,80,[]),888);
assert.equal(ApexCatalogSafeRight(900,200,1000,1800,80,[{x:890,y:300,width:50,height:50}]),0);
assert.equal(ApexCatalogSafeRight(NaN,200,1000,1800,80,regions),0);
assert.equal(ApexCatalogSafeRight(900,1000,200,1800,80,regions),0);
''')

    def test_envelope_protects_native_left_footer_and_other_visible_controls(self):
        self.execute(self.common()+'''
const envelope=ApexCatalogWidthEnvelope(mCurrentPanel);assert.equal(envelope.available,866.5);
assert.deepEqual(envelope.regions.slice(0,3).map(r=>r.kind),['avatar-native-attachment','traits-native-left','radial-native-left']);
const before=mCurrentPanel.localToGlobal(new Point(0,0));
mcWingToggle=new Sprite();mcWingToggle.stage=stage;mcWingToggle.x=1400;mcWingToggle.y=300;
assert.equal(ApexCatalogWidthEnvelope(mCurrentPanel).available,492);
mcWingToggle.visible=false;assert.equal(ApexCatalogWidthEnvelope(mCurrentPanel).available,866.5);
mcWingToggle=null;navigation.btnPlay=new Sprite();navigation.btnPlay.stage=stage;navigation.btnPlay.x=950;navigation.btnPlay.y=300;
assert.equal(ApexCatalogWidthEnvelope(mCurrentPanel).available,42);navigation.btnPlay=null;LayoutAPI.mLayoutMgr=null;assert.equal(ApexCatalogWidthEnvelope(mCurrentPanel),null);
assert.deepEqual(mCurrentPanel.localToGlobal(new Point(0,0)),before);
''')

    def test_recorded_2560_1385_native_mask_allows_rightward_space_without_covering_navigation_buttons(self):
        fixture=json.loads((ROOT/'tests/fixtures/cas_geometry_2560x1385.json').read_text(encoding='utf-8'))
        self.execute(self.common()+'const recorded='+json.dumps(fixture)+''';
const bounds=recorded.catalog_bounds,metrics=recorded.grid_metrics;
stage.stageWidth=bounds.stage_width;stage.stageHeight=bounds.stage_height;
mCurrentPanel.x=bounds.x;mCurrentPanel.y=bounds.y;mCurrentPanel.mcPanelBackground.width=bounds.width;
const mask=mCurrentPanel.mcTileList.mScrollerView.mcMask;
mask.x=metrics.scroll_mask.x;mask.y=metrics.scroll_mask.y;mask.naturalWidth=metrics.scroll_mask.width;mask.naturalHeight=metrics.scroll_mask.height;
mCurrentPanel.mcTileList.height=metrics.scroll_list_height;
mCurrentPanel.mcTileList.mSlider.getBounds=()=>new Rectangle(metrics.scrollbar.x-bounds.x,metrics.scrollbar.y-bounds.y,metrics.scrollbar.width,metrics.scrollbar.height);
mCurrentPanel.mcTileList.y=recorded.catalog_controls.columns.y-bounds.y-metrics.scroll_list_height-3;
// Button positions below are guard fixtures, not claimed captured hit bounds.
navigation.btnPlay=new Sprite();navigation.btnPlay.stage=stage;navigation.btnPlay.x=2476;navigation.btnPlay.y=1330;
navigation.btnPlay.naturalWidth=64;navigation.btnPlay.naturalHeight=48;
const free=ApexCatalogWidthEnvelope(mCurrentPanel);
assert.equal(free.bottom,1310.9999542236328);assert.ok(free.available>bounds.width);assert.ok(free.available>900);
assert.ok(free.available<=stage.stageWidth-bounds.x-12);
navigation.btnPlay.x=2300;const clipped=ApexCatalogWidthEnvelope(mCurrentPanel);
assert.ok(clipped.available<free.available);const half=Math.max(90,(clipped.available-30)*.5);
const thumbnailRight=bounds.x+mCurrentPanel.mcTileList.x+half+7+Math.min(230,half);
assert.ok(thumbnailRight<=navigation.btnPlay.x-8+.001);
navigation.btnPlay.y=1200;assert.ok(ApexCatalogWidthEnvelope(mCurrentPanel).available<=navigation.btnPlay.x-8-bounds.x);
navigation.btnPlay.parent=navigation;navigation.visible=false;
assert.ok(ApexCatalogNavigationRects().length===0);
assert.equal(mCurrentPanel.x,bounds.x);assert.equal(mCurrentPanel.y,bounds.y);
''')

    def test_width_grip_stays_outside_native_scrollbar_and_reserves_its_real_overhang(self):
        self.execute(self.common()+js('ApexColumnsWidthHandle','panel','catalog_columns_methods.as')+'''
function ApexColumnsWidthDown(){}
const p=mCurrentPanel;p.mcTileList.mSlider.getBounds=()=>new Rectangle(280,160,60,700);
ApexColumnsWidthHandle(p);
assert.equal(apexColumns.width_handle.parent,p);assert.ok(apexColumns.width_handle.x-3>=348);
assert.equal(mDynamicResizeHandle.visible,false);
const envelope=ApexCatalogWidthEnvelope(p);assert.equal(envelope.available,828);
p.scaleX=1.5;p.scaleY=1.5;p.mcTileList.height=500;
const scaled=ApexCatalogWidthEnvelope(p);assert.ok(scaled.available<=((1800-900)/1.5)-72);
''')

    def test_fit_keeps_count_and_requested_size_independent_of_explicit_width(self):
        self.execute(js('ApexCardFit','columns,stageWidth,scale,gapX,gapY,naturalWidth,naturalHeight,availableOverride=NaN','catalog_cards_methods.as')+'''
for(const n of [2,12,20,32])for(const requested of [.2,1,1.6])for(const free of [80,262,650,1200]){
 const f=ApexCardFit(n,1800,requested,4,4,111,148,free);
 assert.equal(f.columns,n);assert.equal(f.requested_scale,requested);assert.equal(f.width,free);
 assert.ok(f.scale>0&&f.scale<=requested);assert.ok(f.columns*f.pitch_x+40<=f.width+1e-7);assert.equal(f.right_growth,true);}
const compact=ApexCardFit(12,1800,1,4,4,111,148);assert.equal(compact.right_growth,false);
assert.ok(compact.width<=730);const wider=ApexCardFit(12,1800,1,4,4,111,148,1200);assert.ok(wider.scale>compact.scale);
''')

    def test_actual_legacy_apply_works_on_body_and_generic_without_clothing_members(self):
        import importlib.util
        repo=ROOT
        spec=importlib.util.spec_from_file_location('actual_geometry_fixture',repo/'tests/test_cas_card_geometry.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        setup=mod.CardGeometryTests().harness().split('function ApexCatalogCells(',1)[0]
        setup+='''
flash.utils={Dictionary:class Dictionary{constructor(){return {};}}};
var apexPanelGeometry=null,apexColumns={preferred_width:0},mCurrentPanel=panel;
var mcClothingPanel=null,mcBodyModPanel=panel,mcFaceModPanel=null,mcGenericCatalogPanel=null,mcFeaturedFaceLookPanel=null,mcSkinColorPanel=null;
panel.stage=stage;panel.visible=true;panel.mcTileList.mGridLayout=grid;
'''
        for name,args in [('ApexCatalogPanelKey','panel'),('ApexCatalogPanelKind','panel'),('ApexCatalogOptional','owner,name'),('ApexCardStateFor','grid'),
                          ('ApexCardActivate','panel,grid'),('ApexCatalogWidthRequest','panel')]:setup+=js(name,args)
        for name,args in [('ApexCatalogCells','grid'),('ApexCardRowsAligned','grid,columns,pitch,pitchX=0'),
                          ('ApexCardRestore',''),('ApexCardForget',''),('ApexCardScaleCells','grid,scale,preserveAspect=true'),
                          ('ApexCardFit','columns,stageWidth,scale,gapX,gapY,naturalWidth,naturalHeight,availableOverride=NaN'),
                          ('ApexCardRepairControls','panel,width,reflow'),('ApexCardApply','panel,grid')]:setup+=js(name,args,'catalog_cards_methods.as')
        setup+='''
// Actual Body uses the same native recycling API, with its own preset cells.
for(const c of grid.cells)delete c.mcHitArea;
ApexCardApply(panel,grid);assert.equal(grid.columns,12);assert.equal(apexCardLayout.columns,12);
const bindings=gridBinds;apexCatalogFrameCells=null;ApexCardApply(panel,grid);assert.equal(gridBinds,bindings);
mcBodyModPanel=null;mcGenericCatalogPanel=panel;delete panel.btnRandomize;panel.mcFilterPane=null;
apexCatalogPrefs.columns=32;apexCardPrefs.scale=.2;apexCatalogFrameCells=null;ApexCardApply(panel,grid);
assert.equal(grid.columns,32);assert.equal(apexCardLayout.requested_scale,.2);assert.ok(apexCardLayout.scale<=.2);
'''
        result=subprocess.run(['node'],input=setup,capture_output=True,text=True,encoding='utf-8',timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_nested_skin_swatch_adapter_preserves_feed_selection_callbacks_and_outer_family_count(self):
        source=js('ApexSwatchGeometry','columns,scale,gapX,gapY,width','swatch_geometry_adapter_methods.as')
        source='''
function makeSwatches(){
 let mMaxCols=6,mCenterX=100,mbPreserveBackgroundWidth=true,apexSwatchGeometry=null,resets=0;
 const feed={selection:2,items:[1,2,3,4,5,6,7,8,9]},callback=()=>17;
 const cells=Array.from({length:9},()=>{let c=new Sprite();c.naturalWidth=24;c.naturalHeight=24;return c;});
 const mGrid={columns:6,Horizontal:true,padding:new Margin(0,0,4,4),bounds:new Rectangle(0,0,24,24),
 get FirstCell(){return cells[0]||null;},GetAllDisplayObjectCells(){throw Error("Idle swatch enumeration");},GetGridDimensions(){return [this.columns,Math.ceil(cells.length/this.columns)];},
 GetCellBounds(){return this.bounds;},GetCellPadding(){return this.padding;},set NumLines(v){this.columns=v;},
 SetCellPadding(p){this.padding=p;},SetCellBounds(b){this.bounds=b;for(const c of cells){c.width=b.width;c.height=b.height;}}};
 const mcSelectionGrid={mGridLayout:mGrid};const mcSelectionGridBackground={width:200};
 function ResetLayout(){resets++;}
'''+source+'''
 return {ApexSwatchGeometry,feed,callback,mGrid,mcSelectionGrid,get resets(){return resets;},get max(){return mMaxCols;}};
}
const swatches=makeSwatches(),feed=swatches.feed,callback=swatches.callback;
const first=swatches.ApexSwatchGeometry(12,.5,3,5,400);
assert.equal(first.columns,12);assert.equal(first.card_width,12);assert.equal(swatches.max,12);
assert.equal(swatches.feed,feed);assert.equal(swatches.feed.selection,2);assert.equal(swatches.callback,callback);assert.equal(callback(),17);
assert.equal(swatches.resets,1);swatches.ApexSwatchGeometry(12,.5,3,5,400);assert.equal(swatches.resets,1);
swatches.ApexSwatchGeometry(32,.2,0,0,200);assert.equal(swatches.max,32);assert.equal(swatches.resets,2);
assert.equal(swatches.feed,feed);assert.equal(swatches.feed.selection,2);
// Native SetType may reset only its column count; the next real geometry pass repairs it once.
swatches.mGrid.NumLines=6;swatches.ApexSwatchGeometry(32,.2,0,0,200);assert.equal(swatches.mGrid.columns,32);assert.equal(swatches.resets,3);
assert.throws(()=>swatches.ApexSwatchGeometry(33,1,0,0,200));
'''
        self.execute(source)

    def drag(self):
        out=self.common()
        for name,args in [('ApexColumnsTakeover','value=null'),('ApexColumnsResizeEnd','value=null'),
                          ('ApexColumnsWidthDown','event'),('ApexColumnsWidthMove','event'),('ApexColumnsWidthUp','event=null')]:
            out+=js(name,args,'catalog_columns_methods.as')
        return out

    def test_right_width_drag_expands_and_shrinks_without_changing_columns_scale_or_avatar(self):
        self.execute(self.drag()+'''
const p=mCurrentPanel,origin=p.localToGlobal(new Point(0,0));
ApexColumnsWidthDown(new MouseEvent(1200));assert.equal(apexColumns.width_anchor,312);
ApexColumnsWidthMove(new MouseEvent(1600));assert.equal(apexColumns.preferred_width,700);
assert.equal(apexCatalogPrefs.columns,12);assert.equal(apexCardPrefs.scale,1);
ApexColumnsWidthMove(new MouseEvent(900));assert.equal(apexColumns.preferred_width,80);
ApexColumnsWidthMove(new MouseEvent(9000));assert.equal(apexColumns.preferred_width,866.5);
assert.deepEqual(p.localToGlobal(new Point(0,0)),origin);
ApexColumnsWidthUp(new MouseEvent(1400));assert.equal(apexColumns.resize,null);assert.equal(apexColumns.preferred_width,500);
''')

    def test_width_drag_refuses_stale_panel_grid_viewport_and_handles_ui_scaling(self):
        self.execute(self.drag()+'''
mCurrentPanel.scaleX=1.25;mCurrentPanel.scaleY=1.25;mCurrentPanel.mcTileList.height=600;
ApexColumnsWidthDown(new MouseEvent(1200));ApexColumnsWidthMove(new MouseEvent(1450));assert.equal(apexColumns.preferred_width,500);
const last=apexColumns.preferred_width;stage.stageWidth=1700;ApexColumnsWidthMove(new MouseEvent(1700));
assert.equal(apexColumns.resize,null);assert.equal(apexColumns.preferred_width,last);
ApexColumnsWidthDown(new MouseEvent(1200));mCurrentPanel=mcBodyModPanel;ApexColumnsWidthMove(new MouseEvent(1600));
assert.equal(apexColumns.resize,null);assert.equal(apexColumns.preferred_width,300);
ApexColumnsWidthDown(new MouseEvent(1200));mCurrentPanel.mcTileList.mGridLayout={};ApexColumnsWidthMove(new MouseEvent(1600));assert.equal(apexColumns.resize,null);
''')

    def test_generic_track_reuses_visual_without_reparenting_donor_control(self):
        self.execute(self.common()+js('ApexColumnsTrack','panel','catalog_columns_methods.as')+'''
function ApexColumnsScaleDown(){}
const donor=new Sprite('dccThumbnailScaleTrack');mcClothingPanel.addChild(donor);
assert.equal(ApexColumnsTrack(mcClothingPanel),donor);
const shared=ApexColumnsTrack(mcBodyModPanel);assert.notEqual(shared,donor);
assert.equal(shared.parent,mcBodyModPanel);assert.equal(ApexColumnsTrack(mcFaceModPanel),shared);
assert.equal(shared.parent,mcFaceModPanel);assert.equal(donor.parent,mcClothingPanel);
assert.equal(ApexColumnsTrack(mcClothingPanel),donor);
''')

    def test_skin_family_caller_preflights_all_groups_and_never_recolumns_outer_rows(self):
        self.execute(self.common()+js('ApexSkinToneApply','panel,grid')+
                     js('ApexCardFit','columns,stageWidth,scale,gapX,gapY,naturalWidth,naturalHeight,availableOverride=NaN','catalog_cards_methods.as')+'''
mCurrentPanel=mcSkinColorPanel;let calls=0,positions=0,ranges=0;
const groups=Array.from({length:4},()=>{
 const c=new Sprite();c.naturalWidth=24;c.naturalHeight=24;
 const nested={FirstCell:c,GetAllDisplayObjectCells(){throw Error("Idle nested swatch enumeration");}},selection={mGridLayout:nested};
 return {mcColorSwatchPanel:{mcSelectionGrid:selection},last:'',
 ApexSwatchGroupGeometry(columns,scale,gapX,gapY,width){calls++;let next=[columns,scale,gapX,gapY,width].join(':');
 let changed=next!==this.last;this.last=next;return {changed,ready:true};}};
});
const outer={GetAllDisplayObjectCells:()=>groups,PositionCells(){positions++;},
 set NumLines(v){throw Error('Color family rows must remain one column');},toString:()=> 'skin-grid'};
mcSkinColorPanel.mcTileList.mGridLayout=outer;
let height=700;Object.defineProperty(mcSkinColorPanel.mcTileList,'height',{get(){return height;},set(v){height=v;ranges++;}});
function ApexCardRepairControls(panel,width,reflow){assert.equal(reflow,false);panel.mcPanelBackground.width=width;return false;}
ApexSkinToneApply(mcSkinColorPanel,outer);assert.equal(calls,4);assert.equal(positions,1);assert.equal(ranges,1);
assert.equal(apexCardLayout.requested_columns,12);assert.equal(apexCardGeometry.specialized,true);
ApexSkinToneApply(mcSkinColorPanel,outer);assert.equal(calls,8);assert.equal(positions,1);assert.equal(ranges,1);
delete groups[3].ApexSwatchGroupGeometry;const before=calls;
assert.throws(()=>ApexSkinToneApply(mcSkinColorPanel,outer),/adapters unavailable/);assert.equal(calls,before);
''')

    def test_reloaded_width_reconstructs_original_native_anchor_and_is_fenced_to_current_sim_panel(self):
        self.execute(self.common()+'''
apexColumns.preferred_width=650;assert.equal(ApexCatalogWidthMode(),false);
const width=ApexCatalogWidthRequest(mcClothingPanel);assert.equal(width,650);assert.equal(apexColumns.width_anchor,312);
assert.equal(ApexCatalogWidthMode(),true);const anchor=apexColumns.width_anchor;
mcClothingPanel.mcPanelBackground.width=650;assert.equal(ApexCatalogWidthRequest(mcClothingPanel),650);assert.equal(apexColumns.width_anchor,anchor);
mCurrentPanel=mcBodyModPanel;assert.equal(ApexCatalogWidthMode(),false);ApexCatalogWidthRequest(mCurrentPanel);
assert.equal(apexColumns.width_panel,mcBodyModPanel);assert.equal(ApexCatalogWidthMode(),true);
mCurrSimInfo={simId:'another-fixture-owner'};assert.equal(ApexCatalogWidthMode(),false);ApexCatalogWidthRequest(mCurrentPanel);
assert.equal(apexColumns.width_sim,'another-fixture-owner');assert.equal(ApexCatalogWidthMode(),true);
''')


class IntegrationContracts(unittest.TestCase):
    def test_explicit_six_native_panels_and_no_game_mutation(self):
        source=(AS/'catalog_panel_geometry_methods.as').read_text(encoding='utf-8')
        for name in ['mcClothingPanel','mcBodyModPanel','mcFaceModPanel','mcGenericCatalogPanel','mcFeaturedFaceLookPanel','mcSkinColorPanel']:
            self.assertIn('panel==='+name,source)
        # Geometry only changes owned UI layout. It never equips a part,
        # selects a Sim/form, submits a cheat, or changes the avatar camera.
        for forbidden in ('CallGameService','CallUIService','PostServerCommand','RequestData','SetCatalogSlotSelected',
                          'CasSetSimOccult','LoadNextSimModel','LoadPrevSimModel','CasSetZoomState'):
            self.assertNotIn(forbidden,source)

    def test_native_handler_and_incremental_lease_boundaries_are_retained(self):
        workspace=(AS/'catalog_workspace_methods.as').read_text(encoding='utf-8')
        self.assertIn('ApexSkinToneApply(panel,grid) : ApexCardApply(panel,grid)',workspace)
        self.assertIn('if(panel===mcClothingPanel && !ApexCatalogGridPending(grid))',workspace)
        controller=(AS/'catalog_grid_transaction_methods.as').read_text(encoding='utf-8')
        self.assertIn('var retained:Object=ApexCardStateFor(lease.grid)',controller)
        self.assertIn('var retained:Object=ApexCardStateFor(s.grid)',controller)
        # The product extension intentionally adds exact Body/Face/Generic
        # leases; the current panel/cell classifier replaces clothing-only.
        self.assertIn('var panelKind:String=ApexCatalogGridProductPanel(lease.panel);',controller)
        self.assertIn('panelKind=="" || lease.panel_kind!==panelKind',controller)
        self.assertIn('lease.panel===mCurrentPanel && lease.panel.visible===true',controller)
        self.assertIn('lease.cell_type!==lease.grid.GetCellView',controller)
        self.assertIn('native_generation:context.native_generation',controller)
        helper=(AS/'catalog_panel_geometry_methods.as').read_text(encoding='utf-8')
        skin=helper.split('private function ApexSkinToneApply',1)[1]
        self.assertNotIn('grid.NumLines=',skin)
        self.assertNotIn('CallGameService',helper)
        self.assertNotIn('RequestData',helper)
        self.assertNotIn('SetCatalogSlotSelected',helper)

    def test_matching_native_binding_seam_cannot_shift_left_for_width_growth(self):
        source=(ROOT/'tools/cas_catalog_binding.py').read_text(encoding='utf-8')
        self.assertIn('panel!==mcBodyModPanel && panel!==mcFaceModPanel',source)
        self.assertIn('if(fitted && apexColumns!=null',source)
        self.assertIn('clamp=Math.max(maximum,Number(apexColumns.width_anchor))',source)
        workspace=(AS/'catalog_workspace_methods.as').read_text(encoding='utf-8')
        self.assertIn('Math.max(apexCatalogBinding.maximum,Number(apexColumns.width_anchor))',workspace)
        # No direct screen-coordinate or avatar/camera mutation is introduced.
        helper=(AS/'catalog_panel_geometry_methods.as').read_text(encoding='utf-8')
        self.assertNotRegex(helper,r'(panel|mLayerPanels)\.x\s*=')
        self.assertNotIn('CasSetZoomState',helper)


if __name__=='__main__':unittest.main()
