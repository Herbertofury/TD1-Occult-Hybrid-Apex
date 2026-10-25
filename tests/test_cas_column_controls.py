"""The actual slider methods must not chase a catalog that resizes beneath them."""
from pathlib import Path
import re
import shutil
import subprocess
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'Source/CASUi/catalog_columns_methods.as'


def javascript_function(name, parameters=''):
    source = SOURCE.read_text(encoding='utf-8')
    part = source.split('private function ' + name + '(', 1)[1]
    part = re.split(r'\n      private (?:function|var) ', part, maxsplit=1)[0]
    body = part.split('{', 1)[1].rsplit('}', 1)[0]
    body = re.sub(r'\b(var\s+\w+)\s*:\s*[\w.]+', r'\1', body)
    body = re.sub(r'\s+as\s+flash\.[\w.]+', '', body)
    body = re.sub(r'(\w+) is (flash\.[\w.]+|ClothingPanel)', r'\1 instanceof \2', body)
    return 'function ' + name + '(' + parameters + '){' + body + '}\n'


@unittest.skipUnless(shutil.which('node'), 'Node is required for the AS method harness')
class ColumnControlTests(unittest.TestCase):
    def harness(self):
        setup = '''
const assert=require('node:assert/strict');
class Point{constructor(x,y){this.x=x;this.y=y;}}
class Event{constructor(type){this.type=type;}}Event.DEACTIVATE='deactivate';Event.MOUSE_LEAVE='mouseLeave';Event.ENTER_FRAME='frame';
class MouseEvent extends Event{}MouseEvent.MOUSE_MOVE='move';MouseEvent.MOUSE_UP='up';MouseEvent.MOUSE_DOWN='down';
class Sprite{
    constructor(name=''){this.name=name;this.parent=null;this.x=0;this.y=0;this.scaleX=1;this.scaleY=1;this.visible=true;this.children={};}
    addChild(child){this.children[child.name]=child;child.parent=this;}
    getChildByName(name){return this.children[name]||null;}
    localToGlobal(p){const value={x:p.x*this.scaleX+this.x,y:p.y*this.scaleY+this.y};return this.parent?this.parent.localToGlobal(value):value;}
    globalToLocal(p){const value=this.parent?this.parent.globalToLocal(p):p;return {x:(value.x-this.x)/this.scaleX,y:(value.y-this.y)/this.scaleY};}
    get mouseX(){return this.globalToLocal({x:stage.mouseX,y:stage.mouseY}).x;}
}
class ClothingPanel extends Sprite{}
var flash={geom:{Point},display:{Sprite},events:{Event,MouseEvent},utils:{getTimer:()=>10}};
var stage={stageWidth:1278,stageHeight:1376,mouseX:0,mouseY:0,addEventListener(){},removeEventListener(){}};
function int(x){return Math.trunc(x);}function HandleThumbnailScaleMove(){}function HandleThumbnailScaleUp(){}function HandleThumbnailScaleFrame(){}
var mcClothingPanel=new ClothingPanel(),mCurrentPanel=mcClothingPanel;
mcClothingPanel.x=978;mcClothingPanel.mcTileList={x:20,y:100,height:600};mcClothingPanel.mcPanelBackground={width:300};
const root=new Sprite('ApexColumnsSlider'),track=new Sprite('dccThumbnailScaleTrack');
for(const name of ['thumb','caption','apexColumnsLayout'])root.addChild(new Sprite(name));
for(const name of ['dccThumbnailScaleThumb','apexThumbnailScaleCaption'])track.addChild(new Sprite(name));
mcClothingPanel.addChild(root);mcClothingPanel.addChild(track);
var apexColumns={root,track,bounds:null,anchor:null,resize:null,tooltips:[],track_tip:null,drag:false,scale_drag:false,
    scale_stage:null,stage:null,persist:false,due:0},apexCatalogPrefs={columns:2},apexCardPrefs={scale:1},apexCardLayout={columns:2,scale:1};
var apexPanels={drag:null},apexPendingFields=null,apexReceiving=false;
function ApexCatalogPersist(){throw new Error('Persistence on an active input frame');}
function event(){return {target:root,stopImmediatePropagation(){},preventDefault(){}};}
'''
        for name, parameters in [('ApexColumnsTakeover', 'value=null'), ('ApexColumnsSave', ''),
                                 ('ApexColumnsSet', 'value=null'), ('ApexColumnsScale', 'value=null'),
                                 ('ApexColumnsScaleEnd', 'value=null'), ('ApexColumnsDown', 'event'),
                                 ('ApexColumnsMove', 'event'), ('ApexColumnsUp', 'event=null'),
                                 ('ApexColumnsResize', 'value=null'), ('ApexColumnsResizeEnd', 'value=null'),
                                 ('ApexColumnsFrame', '')]:
            setup += javascript_function(name, parameters)
        return setup

    def run_case(self, case):
        result = subprocess.run(['node', '-e', self.harness() + case], capture_output=True,
                                text=True, encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_column_drag_keeps_track_and_value_stable_through_reflow(self):
        self.run_case('''
ApexColumnsFrame();const origin=root.localToGlobal(new Point(0,0)),scale=root.scaleX;
stage.mouseX=origin.x+80*scale;stage.mouseY=origin.y+26;
ApexColumnsDown(event());assert.equal(apexCatalogPrefs.columns,14);
mcClothingPanel.x=578;mcClothingPanel.mcPanelBackground.width=700;ApexColumnsFrame();
assert.deepEqual(root.localToGlobal(new Point(0,0)),origin);assert.equal(root.scaleX,scale);
for(let i=0;i<4;i++){ApexColumnsMove(event());ApexColumnsFrame();assert.equal(apexCatalogPrefs.columns,14);}
ApexColumnsUp();ApexColumnsFrame();assert.equal(apexColumns.anchor,null);
assert.equal(apexCatalogPrefs.columns,14);assert.notEqual(root.localToGlobal(new Point(0,0)).x,origin.x);
''')

    def test_thumbnail_drag_keeps_native_track_under_pointer_until_release(self):
        self.run_case('''
ApexColumnsFrame();const origin=track.localToGlobal(new Point(0,0)),scale=track.scaleX;
stage.mouseX=origin.x+160*scale;stage.mouseY=origin.y+14;
ApexColumnsScale();const size=apexCardPrefs.scale;assert.equal(size,1.23);
mcClothingPanel.x=578;mcClothingPanel.mcPanelBackground.width=700;ApexColumnsFrame();
assert.deepEqual(track.localToGlobal(new Point(0,0)),origin);assert.equal(track.scaleX,scale);
for(let i=0;i<4;i++){ApexColumnsScale();ApexColumnsFrame();assert.equal(apexCardPrefs.scale,size);}
ApexColumnsScaleEnd();ApexColumnsFrame();assert.equal(apexColumns.anchor,null);assert.equal(apexColumns.scale_drag,false);
assert.equal(apexCardPrefs.scale,size);assert.notEqual(track.localToGlobal(new Point(0,0)).x,origin.x);
''')

    def test_viewport_change_ends_drag_without_applying_a_new_pointer_value(self):
        self.run_case('''
ApexColumnsFrame();const origin=track.localToGlobal(new Point(0,0));
stage.mouseX=origin.x+120*track.scaleX;stage.mouseY=origin.y+14;ApexColumnsScale();const size=apexCardPrefs.scale;
stage.stageWidth=1440;stage.mouseX=0;ApexColumnsFrame();
assert.equal(apexColumns.scale_drag,false);assert.equal(apexColumns.drag,false);assert.equal(apexColumns.anchor,null);
assert.equal(apexCardPrefs.scale,size);
''')

    def test_complete_slider_ranges_and_native_resize_hold_one_pitch(self):
        self.run_case('''
function HandleDynamicResizeMoveRight(){}function HandleDynamicResizeUpRight(){}
var mDynamicResizeStartX=100,mDynamicResizeStartCols=6,mDynamicResizeHandle={alpha:1};
apexCardLayout.pitch_x=100;ApexColumnsResize({stageX:300});assert.equal(apexCatalogPrefs.columns,8);
assert.equal(apexColumns.drag,true);apexCardLayout.pitch_x=25;
ApexColumnsResize({stageX:300});assert.equal(apexCatalogPrefs.columns,8);
const last=apexCatalogPrefs.columns;ApexColumnsResizeEnd(new Event(Event.DEACTIVATE));
assert.equal(apexColumns.resize,null);assert.equal(apexColumns.drag,false);assert.equal(apexCatalogPrefs.columns,last);
ApexColumnsSet(32);assert.equal(apexCatalogPrefs.columns,32);ApexColumnsSet(33);assert.equal(apexCatalogPrefs.columns,32);
ApexColumnsFrame();const at=track.localToGlobal(new Point(0,0));stage.mouseX=at.x+20*track.scaleX;ApexColumnsScale();
assert.equal(apexCardPrefs.scale,.2);stage.mouseX=at.x+210*track.scaleX;ApexColumnsScale();assert.equal(apexCardPrefs.scale,1.6);
''')

    def test_native_resize_retires_on_context_change_without_native_fallback(self):
        self.run_case('''
function HandleDynamicResizeMoveRight(){}function HandleDynamicResizeUpRight(){}
var mDynamicResizeStartX=100,mDynamicResizeStartCols=6,mDynamicResizeHandle={alpha:1};
apexCardLayout.pitch_x=100;ApexColumnsResize({stageX:300});const count=apexCatalogPrefs.columns;
mCurrentPanel=new Sprite('body');ApexColumnsFrame();
assert.equal(apexColumns.resize,null);assert.equal(apexColumns.drag,false);assert.equal(apexCatalogPrefs.columns,count);
assert.equal(mDynamicResizeHandle.alpha,.78);assert.equal(root.visible,false);assert.equal(track.visible,false);
''')


if __name__ == '__main__':
    unittest.main()
