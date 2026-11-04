"""Execute the actual fitted-card and control-repair methods with native UI doubles."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'Source/CASUi/catalog_cards_methods.as'
sys.path.insert(0, str(ROOT / 'tools'))
from cas_catalog_workspace import card_layout
from test_cas_panel_geometry import js as panel_javascript


def javascript_function(name, parameters='', source=SOURCE):
    part = source.read_text(encoding='utf-8').split('private function ' + name + '(', 1)[1]
    part = re.split(r'\n      private (?:function|var) ', part, maxsplit=1)[0]
    body = part.split('{', 1)[1].rsplit('}', 1)[0]
    body = re.sub(r'\b(var\s+\w+)\s*:\s*[\w.]+', r'\1', body)
    body = re.sub(r'\s+as\s+flash\.[\w.]+', '', body)
    body = re.sub(r'for each\((?:var )?(\w+) in ([^\n]+?)\)\s*\{', r'for(var \1 of \2) {', body)
    return 'function ' + name + '(' + parameters + '){' + body + '}\n'


@unittest.skipUnless(shutil.which('node'), 'Node is required for the AS geometry harness')
class CardGeometryTests(unittest.TestCase):
    def execute(self, script):
        result = subprocess.run(['node'], input=script, capture_output=True,
                                text=True, encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def harness(self):
        code = '''
const assert=require('node:assert/strict');
class Rectangle{constructor(x=0,y=0,width=0,height=0){Object.assign(this,{x,y,width,height});}clone(){return new Rectangle(this.x,this.y,this.width,this.height);}}
class Point{constructor(x,y){this.x=x;this.y=y;}}
class Sprite{constructor(){this.children={};}getChildByName(name){return this.children[name]||null;}
    addChild(child){this.children[child.name]=child;child.parent=this;}removeChild(child){delete this.children[child.name];child.parent=null;}}
class Cell extends Sprite{constructor(){super();this.naturalWidth=111;this.naturalHeight=148;this.mcHitArea={height:148};this.scaleX=1;this.scaleY=1;this.x=0;this.y=0;}
    get width(){return this.naturalWidth*this.scaleX;}set width(value){this.scaleX=value/this.naturalWidth;}}
class Margin{constructor(top,right,bottom,left){Object.assign(this,{mTop:top,mRight:right,mBot:bottom,mLeft:left});}
    get Horizontal(){return this.mLeft+this.mRight;}get Vertical(){return this.mTop+this.mBot;}}
function int(value){return Math.trunc(value);}int.MAX_VALUE=2147483647;
var flash={geom:{Rectangle,Point},display:{Sprite}},stage={stageWidth:1278},uiScale=1;
var olympus={gamepad:{LayoutAPI:{get StageWidth(){return stage.logicalWidth||stage.stageWidth;}}}};
var LayoutAPI=olympus.gamepad.LayoutAPI;
var apexCardGeometry=null,apexCardLayout=null,apexCardReflowAttempts=0,apexCatalogFrameCells=null;
var apexCatalogPrefs={columns:12},apexCardPrefs={scale:1,gap_x:4,gap_y:4},apexCatalogSignature='',apexCatalogLayoutChanges=0;
var popupOpen=false,popupCloses=0,favoriteLayouts=0,rangeUpdates=0,widthUpdates=0,gridBinds=0;
var apexCompanion={layout_owner:{},donor:{PositionButton(){favoriteLayouts++;}}};
function ApexCatalogClearEffects(){}
function ApexCatalogGridOwns(grid){return false;}
function ApexCardIncrementalApply(){throw Error("Unexpected incremental mode");}
function ApexLayoutReset(grid){grid.ResetAndPositionCells();}
class Grid{
    constructor(){this.SuppressUpdates=false;this.columns=2;this.Horizontal=true;this.bounds=new Rectangle(0,0,107,148);this.padding=new Margin(0,0,4,4);this.cells=Array.from({length:64},()=>new Cell());}
    GetAllDisplayObjectCells(){return this.cells;}GetCellBounds(){const bounds=this.bounds.clone();if(!bounds.height)bounds.height=148;return bounds;}GetCellPadding(){return this.padding;}
    GetGridDimensions(){const rows=Math.ceil(this.cells.length/this.columns);return this.Horizontal?[this.columns,rows]:[rows,this.columns];}
    set NumLines(value){this.columns=value;}SetCellPadding(value){this.padding=value;this.PositionCells();}
    SetCellBounds(value){this.bounds=value;for(const cell of this.cells)cell.width=value.width;this.PositionCells();}
    PositionCells(){if(this.SuppressUpdates)return;gridBinds++;for(let i=0;i<this.cells.length;i++){const cell=this.cells[i];cell.x=(i%this.columns)*(cell.width+this.padding.Horizontal);
        cell.y=Math.floor(i/this.columns)*(this.cells[0].naturalHeight*this.cells[0].scaleY+this.padding.Vertical);}}
    ResetAndPositionCells(){this.PositionCells();}
}
var grid=new Grid(),gridView={width:232},mask={width:232},view={x:18,width:232,mcMask:mask};
var slider={x:251,width:10,Value:123,MinValue:0,MaxValue:1000};
var list={ScrollerViewMargin:new Margin(-4,12,0,18),mScrollerView:view,mSlider:slider,ScrollerAmount:111,
    _width:262,_height:1000,GetGridView(){return gridView;},
    get width(){return this._width;},set width(value){this._width=value;widthUpdates++;view.x=18;view.width=value-30;mask.width=value-30;gridView.width=value-30;slider.x=value-6-slider.width*.5;grid.PositionCells();},
    get height(){return this._height;},set height(value){this._height=value;rangeUpdates++;slider.MaxValue=Math.max(0,Math.ceil(grid.cells.length/grid.columns)*(148*grid.cells[0].scaleY+grid.padding.Vertical)-value);
        slider.Value=Math.min(slider.Value,slider.MaxValue);if(popupOpen){popupOpen=false;popupCloses++;}}};
var panel={localToGlobal(p){return new Point(p.x*uiScale+400,p.y*uiScale+20);},mcTileList:list,mcPanelBackground:{width:262},mcFilterPane:{mcFilterBubble:{mcBackground:{width:232}}},txtTitle:{x:110},btnRandomize:{x:220},
    set width(value){this.mcPanelBackground.width=value;list.width=value;}};
// Exercise the real shared six-panel ownership helpers. Width preferences
// remain unset here; their measured-envelope behavior has its own fixtures.
var apexPanelGeometry=null,apexColumns={preferred_width:0},mCurrentPanel=panel;
var mcClothingPanel=panel,mcBodyModPanel=null,mcFaceModPanel=null,
    mcGenericCatalogPanel=null,mcFeaturedFaceLookPanel=null,mcSkinColorPanel=null;
panel.stage=stage;panel.visible=true;list.mGridLayout=grid;
'''
        for name, parameters in [('ApexCatalogPanelKey', 'panel'), ('ApexCatalogPanelKind', 'panel'),
                                 ('ApexCatalogOptional', 'owner,name'), ('ApexCardStateFor', 'grid'),
                                 ('ApexCardActivate', 'panel,grid'), ('ApexCatalogWidthRequest', 'panel')]:
            code += panel_javascript(name, parameters)
        for name, parameters in [('ApexCatalogCells', 'grid'), ('ApexCardRowsAligned', 'grid,columns,pitch,pitchX=0'),
                                 ('ApexCardRestore', ''), ('ApexCardScaleCells', 'grid,scale,preserveAspect=true'),
                                 ('ApexCardFit', 'columns,stageWidth,scale,gapX,gapY,naturalWidth,naturalHeight,availableOverride=-1'),
                                 ('ApexCardRepairControls', 'panel,width,reflow'), ('ApexCardApply', 'panel,grid')]:
            code += javascript_function(name, parameters)
        return code

    def test_actual_fit_matches_oracle_and_keeps_twelve_plus_at_1278(self):
        cases = []
        for viewport in (640, 1024, 1278, 1920, 3840):
            for columns in (2, 6, 12, 20, 32):
                for scale in (.2, .4, 1, 1.6):
                    for gap_x, gap_y in ((0, 32), (4, 4), (32, 0)):
                        args = [columns, viewport, scale, gap_x, gap_y, 111, 148]
                        cases.append([args, card_layout(*args[:5], base_width=111)])
        self.execute(self.harness() + 'const cases=' + json.dumps(cases) + ''';
for(const [args,expected] of cases){const actual=ApexCardFit(...args);
    for(const [key,value] of Object.entries(expected))if(typeof value==='number')assert.ok(Math.abs(actual[key]-value)<1e-7,key+JSON.stringify(args));else assert.equal(actual[key],value);
    assert.ok(actual.width<=actual.available_width+1e-7);assert.ok(actual.available_width<=40+6*(111+4));assert.ok(actual.scale>0&&actual.scale<=args[2]+1e-7);
    assert.ok(actual.gap_x<=args[3]);assert.equal(actual.requested_gap_x,args[3]);assert.equal(actual.gap_y,args[4]);}
for(const columns of [12,20,32]){const actual=ApexCardFit(columns,1278,1,4,4,111,148);assert.equal(actual.columns,columns);}
assert.ok(ApexCardFit(32,1278,1,4,4,111,148).scale<.2);
''')

    def test_actual_apply_renders_requested_columns_and_repairs_native_scroll_geometry(self):
        self.execute(self.harness() + '''
popupOpen=true;const width=ApexCardApply(panel,grid);
assert.equal(grid.columns,12);assert.equal(apexCardLayout.columns,12);assert.equal(apexCardLayout.requested_columns,12);
assert.ok(apexCardLayout.scale<.5);assert.equal(list.width,width);assert.equal(mask.width,width-30);
assert.equal(slider.x,width-6-slider.width*.5);assert.equal(popupOpen,false);assert.equal(popupCloses,1);
assert.equal(panel.mcFilterPane.mcFilterBubble.mcBackground.width,width-30);assert.ok(favoriteLayouts>0);
const updates=rangeUpdates;popupOpen=true;slider.x=60;view.width=50;gridView.width=50;
apexCatalogFrameCells=null;ApexCardApply(panel,grid);
assert.equal(slider.x,width-6-slider.width*.5);assert.equal(view.width,width-30);assert.equal(gridView.width,width-30);
assert.equal(rangeUpdates,updates);assert.equal(popupOpen,true);
slider.x=NaN;apexCatalogFrameCells=null;ApexCardApply(panel,grid);assert.equal(slider.x,width-6-slider.width*.5);
apexCatalogPrefs.columns=32;apexCatalogFrameCells=null;ApexCardApply(panel,grid);
assert.equal(grid.columns,32);assert.equal(apexCardLayout.columns,32);assert.ok(apexCardLayout.scale<.2);
assert.equal(popupOpen,false);assert.equal(popupCloses,2);
for(const cell of grid.cells){assert.ok(Math.abs(cell.scaleX-apexCardLayout.scale)<1e-7);assert.ok(Math.abs(cell.scaleY-apexCardLayout.scale)<1e-7);assert.ok(cell.x+cell.width<=view.width+1e-7);}
const expectedScroll=Math.max(16,apexCardLayout.pitch_y*.75);assert.equal(list.ScrollerAmount,expectedScroll);
''')

    def test_native_dimension_reset_cannot_leave_five_columns_under_twelve_preference(self):
        self.execute(self.harness() + '''
ApexCardApply(panel,grid);const before=apexCatalogLayoutChanges;
grid.NumLines=5;apexCatalogFrameCells=null;ApexCardApply(panel,grid);
assert.equal(grid.columns,12);assert.equal(apexCardLayout.columns,12);assert.equal(apexCatalogLayoutChanges,before+1);
const retained=apexCatalogLayoutChanges;apexCatalogFrameCells=null;ApexCardApply(panel,grid);assert.equal(apexCatalogLayoutChanges,retained);
''')

    def test_restoring_native_geometry_restores_only_owned_header_offsets(self):
        self.execute(self.harness() + '''
ApexCardApply(panel,grid);assert.notEqual(panel.txtTitle.x,110);assert.notEqual(panel.btnRandomize.x,220);
ApexCardRestore();assert.equal(panel.mcPanelBackground.width,262);assert.equal(panel.txtTitle.x,110);
assert.equal(panel.btnRandomize.x,220);assert.equal(panel.mcFilterPane.mcFilterBubble.mcBackground.width,232);
assert.equal(list.ScrollerAmount,111);assert.equal(apexCardGeometry,null);
apexCatalogFrameCells=null;ApexCardApply(panel,grid);panel.txtTitle.x=777;panel.btnRandomize.x=888;
panel.mcFilterPane.mcFilterBubble.mcBackground.width=999;ApexCardRestore();
assert.equal(panel.txtTitle.x,777);assert.equal(panel.btnRandomize.x,888);assert.equal(panel.mcFilterPane.mcFilterBubble.mcBackground.width,999);
''')

    def test_geometry_setters_commit_one_native_bind_and_idle_does_no_work(self):
        self.execute(self.harness() + '''
ApexCardApply(panel,grid);assert.equal(gridBinds,1);assert.equal(grid.SuppressUpdates,false);
const before=gridBinds;apexCatalogFrameCells=null;ApexCardApply(panel,grid);assert.equal(gridBinds,before);
apexCatalogPrefs.columns=32;apexCatalogFrameCells=null;ApexCardApply(panel,grid);
assert.equal(gridBinds,before+1);assert.equal(grid.SuppressUpdates,false);
ApexCardRestore();assert.equal(gridBinds,before+2);assert.equal(grid.SuppressUpdates,false);
''')

    def test_foreign_suppression_lease_is_never_released_or_partially_mutated(self):
        self.execute(self.harness() + '''
grid.SuppressUpdates=true;const width=ApexCardApply(panel,grid);
assert.equal(width,262);assert.equal(apexCardGeometry,null);assert.equal(grid.columns,2);assert.equal(gridBinds,0);
assert.equal(grid.SuppressUpdates,true);grid.SuppressUpdates=false;ApexCardApply(panel,grid);
const retained=apexCardGeometry;grid.SuppressUpdates=true;ApexCardRestore();
assert.equal(apexCardGeometry,retained);assert.equal(grid.SuppressUpdates,true);assert.equal(grid.columns,12);
''')

    def test_setter_exception_releases_owned_lease_without_committing_signature(self):
        self.execute(self.harness() + '''
const native=grid.SetCellPadding;grid.SetCellPadding=function(){throw new Error('setter failed');};
assert.throws(()=>ApexCardApply(panel,grid),/setter failed/);assert.equal(grid.SuppressUpdates,false);
assert.equal(apexCatalogSignature,'');assert.equal(gridBinds,0);
grid.SetCellPadding=native;ApexCardApply(panel,grid);assert.equal(gridBinds,1);
''')


    def test_legitimate_donor_aspect_and_card_flags_do_not_trigger_whole_pool_reset(self):
        self.execute(self.harness() + '''
ApexCardApply(panel,grid);const before=gridBinds;
const card=grid.cells[7];card.Selected=true;card.favorite=true;card.hidden=false;
const s=apexCardLayout.scale;card.scaleY=s*103/147;
apexCatalogFrameCells=null;ApexCardApply(panel,grid);
assert.equal(gridBinds,before);assert.ok(Math.abs(card.scaleY/card.scaleX-103/147)<1e-10);
assert.equal(card.Selected,true);assert.equal(card.favorite,true);assert.equal(card.hidden,false);
// A native draw can reset X/Y to its own aspect. Repair just these transforms.
card.scaleX=1;card.scaleY=103/147;apexCatalogFrameCells=null;ApexCardApply(panel,grid);
assert.equal(gridBinds,before);assert.ok(Math.abs(card.scaleX-s)<1e-10);
assert.ok(Math.abs(card.scaleY-s*103/147)<1e-10);
// Ending Apex geometry must restore native X without flattening the donor Y.
ApexCardRestore();assert.equal(card.scaleX,1);assert.ok(Math.abs(card.scaleY-103/147)<1e-10);
assert.equal(card.getChildByName('apexCatalogCardScale'),null);
''')

    def test_first_cell_aspect_changes_row_pitch_once_and_width_setter_keeps_aspect(self):
        self.execute(self.harness() + '''
for(const cell of grid.cells)cell.scaleY=103/147;
ApexCardApply(panel,grid);const expected=148*apexCardLayout.scale*103/147;
assert.equal(gridBinds,1);assert.ok(Math.abs(apexCardLayout.card_height-expected)<1e-8);
assert.ok(Math.abs(grid.CellViewSizeFallback.y-expected)<1e-8);
for(const cell of grid.cells)assert.ok(Math.abs(cell.scaleY/cell.scaleX-103/147)<1e-8);
assert.ok(ApexCardRowsAligned(grid,12,expected+4,apexCardLayout.pitch_x));
const before=gridBinds;apexCatalogFrameCells=null;ApexCardApply(panel,grid);assert.equal(gridBinds,before);
// Switching back to a native square-aspect category is a real geometry change.
for(const cell of grid.cells)cell.scaleY=cell.scaleX;
apexCatalogFrameCells=null;ApexCardApply(panel,grid);assert.equal(gridBinds,before+1);
assert.ok(Math.abs(apexCardLayout.card_height-148*apexCardLayout.scale)<1e-8);
''')

    def test_native_resize_callback_cannot_recursively_apply_or_restore_geometry(self):
        self.execute(self.harness() + '''
const native=grid.ResetAndPositionCells;let nested=0;
grid.ResetAndPositionCells=function(){nested++;assert.equal(grid.SuppressUpdates,false);
    const same=apexCardGeometry;assert.equal(same.applying,true);
    ApexCardApply(panel,grid);ApexCardRestore();assert.equal(apexCardGeometry,same);
    assert.equal(gridBinds,0);native.call(this);};
ApexCardApply(panel,grid);assert.equal(nested,1);assert.equal(gridBinds,1);
assert.equal(grid.SuppressUpdates,false);assert.equal(apexCardGeometry.applying,false);
grid.ResetAndPositionCells=native;ApexCardRestore();assert.equal(gridBinds,2);
''')

    def test_native_reset_exception_releases_busy_flag_without_hiding_failed_commit(self):
        self.execute(self.harness() + '''
const native=grid.ResetAndPositionCells;grid.ResetAndPositionCells=function(){throw new Error('native resize failed');};
assert.throws(()=>ApexCardApply(panel,grid),/native resize failed/);
assert.equal(grid.SuppressUpdates,false);assert.equal(apexCardGeometry.applying,false);
assert.equal(apexCatalogSignature,'');grid.ResetAndPositionCells=native;
apexCatalogFrameCells=null;ApexCardApply(panel,grid);assert.equal(gridBinds,1);
assert.notEqual(apexCatalogSignature,'');
''')

    def test_scale_pass_count_and_new_pool_cells_are_not_stale_cached(self):
        self.execute(self.harness() + '''
const original=ApexCardScaleCells;let passes=0;
ApexCardScaleCells=function(...args){passes++;return original(...args);};
ApexCardApply(panel,grid);assert.equal(passes,3);
const native=grid.ResetAndPositionCells;
grid.ResetAndPositionCells=function(){const newCell=new Cell();newCell.scaleX=apexCardLayout.scale;newCell.scaleY=apexCardLayout.scale;
    this.cells=this.cells.concat([newCell]);native.call(this);};
passes=0;apexCatalogPrefs.columns=20;apexCatalogFrameCells=null;ApexCardApply(panel,grid);
assert.equal(passes,3);assert.equal(grid.cells.length,65);
assert.ok(grid.cells[64].getChildByName('apexCatalogCardScale'));
assert.ok(Math.abs(grid.cells[64].scaleX-apexCardLayout.scale)<1e-8);
const before=gridBinds;passes=0;apexCatalogFrameCells=null;ApexCardApply(panel,grid);
assert.equal(passes,1);assert.equal(gridBinds,before);
''')

    def test_coordinate_checks_reject_nan_and_wrong_column_before_bounded_repair(self):
        self.execute(self.harness() + '''
ApexCardApply(panel,grid);const before=gridBinds;
grid.cells[2].x=NaN;assert.equal(ApexCardRowsAligned(grid,12,apexCardLayout.pitch_y,apexCardLayout.pitch_x),false);
apexCatalogFrameCells=null;ApexCardApply(panel,grid);assert.equal(gridBinds,before+1);
grid.cells[2].x+=10;assert.equal(ApexCardRowsAligned(grid,12,apexCardLayout.pitch_y,apexCardLayout.pitch_x),false);
grid.cells[2].y=NaN;assert.equal(ApexCardRowsAligned(grid,12,apexCardLayout.pitch_y,apexCardLayout.pitch_x),false);
''')

    def test_logical_viewport_and_panel_transform_keep_all_columns_outside_sim_region(self):
        for ui_scale in (.8,1,1.25):
            for native_width in (1920,2560):
                expected=card_layout(32,2560,1,32,4,base_width=111,
                    ui_scale=ui_scale,native_stage_width=native_width)
                self.execute(self.harness() + 'uiScale='+str(ui_scale)+';stage.stageWidth=2560;stage.logicalWidth='+str(native_width)+';'+ '''
apexCatalogPrefs.columns=32;apexCardPrefs.gap_x=32;ApexCardApply(panel,grid);
assert.equal(grid.columns,32);assert.ok(Math.abs(apexCardLayout.width-'''+str(expected['width'])+''')<1e-7);
assert.ok(panel.mcPanelBackground.width*uiScale<=stage.stageWidth*.4-12*uiScale+1e-7);
for(const cell of grid.cells)assert.ok(cell.x+cell.width<=view.width+1e-7);
// Changing UI scale at unchanged physical resolution still invalidates geometry.
const before=gridBinds;uiScale*=1.25;apexCatalogFrameCells=null;ApexCardApply(panel,grid);
assert.ok(panel.mcPanelBackground.width*uiScale<=stage.stageWidth*.4-12*uiScale+1e-7);
''')


if __name__ == '__main__':
    unittest.main()
