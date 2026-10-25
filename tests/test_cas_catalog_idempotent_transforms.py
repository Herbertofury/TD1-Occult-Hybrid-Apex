"""Execute actual AS paths with native-style setter instrumentation."""
from pathlib import Path
import re
import shutil
import subprocess
import unittest

import test_cas_card_geometry as card

ROOT=card.ROOT
javascript_function=card.javascript_function

WORKSPACE=ROOT/'Source/CASUi/catalog_workspace_methods.as'


@unittest.skipUnless(shutil.which('node'),'Node required for actual-source transform execution')
class IdempotentCatalogTransformTests(unittest.TestCase):
    def execute(self,script):
        result=subprocess.run(['node'],input=script,capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_legacy_marker_unchanged_frames_do_not_write_and_changed_aspects_still_apply(self):
        self.execute(card.CardGeometryTests().harness()+r'''
let markerWrites=0;const values=new WeakMap();
Object.defineProperty(Sprite.prototype,'scaleY',{get(){return values.has(this)?values.get(this):1;},set(value){markerWrites++;values.set(this,value);}});
ApexCardScaleCells(grid,.5);const original=markerWrites;
for(let frame=0;frame<500;frame++){apexCatalogFrameCells=null;assert.equal(ApexCardScaleCells(grid,.5),false);}
assert.equal(markerWrites,original);
const first=grid.cells[0],marker=first.getChildByName('apexCatalogCardScale');
first.scaleY=.5*.7;assert.equal(ApexCardScaleCells(grid,.5),false);assert.equal(marker.scaleY,.7);assert.equal(markerWrites,original+1);
const changed=markerWrites;first.scaleY=.5*.9;ApexCardScaleCells(grid,.5,false);assert.equal(first.scaleY,.5*.7);assert.equal(markerWrites,changed);
first.scaleY=-.25;assert.throws(()=>ApexCardScaleCells(grid,.5),/Native card aspect unavailable/);assert.equal(markerWrites,changed);
first.scaleY=Infinity;assert.throws(()=>ApexCardScaleCells(grid,.5),/Native card aspect unavailable/);assert.equal(markerWrites,changed);
first.scaleY=NaN;assert.throws(()=>ApexCardScaleCells(grid,.5),/Native card aspect unavailable/);assert.equal(markerWrites,changed);
''')

    def test_static_flash_and_pulse_effects_write_only_when_actual_alpha_changes(self):
        code=javascript_function('ApexCatalogSelection','grid',WORKSPACE)
        self.execute(r'''
const assert=require('node:assert/strict');function int(n){return Math.trunc(n);}int.MAX_VALUE=2147483647;
let clock=0,writes=0,currentAlpha=1;const effect={parent:{removeChild(){}},get alpha(){return currentAlpha;},set alpha(value){writes++;currentAlpha=value;}};
const cell={visible:true,Selected:true,mcBottomFrame:null,getChildByName(name){assert.equal(name,'apexSelectedBorder');return effect;}};
let apexCatalogEffects=[{cell,effect,frame:null,transform:null}],apexCatalogSelectionFrames=0,apexCatalogSelectionMaxMs=0,apexCatalogSelectionOverBudget=0;
const apexCatalogPrefs={animation:'none',period:1.4,strength:1,color:0xff0088,border:3,glow:0};
const flash={utils:{getTimer(){return clock;}},display:{Sprite:Object}};
function ApexCatalogCells(grid){return grid.cells;}
'''+code+r'''
const grid={cells:[cell]};for(let frame=0;frame<500;frame++){clock=frame*16;ApexCatalogSelection(grid);}assert.equal(writes,0);assert.equal(currentAlpha,1);
apexCatalogPrefs.strength=.65;ApexCatalogSelection(grid);assert.equal(writes,1);assert.equal(currentAlpha,.65);
for(let frame=0;frame<100;frame++)ApexCatalogSelection(grid);assert.equal(writes,1);
apexCatalogPrefs.animation='flash';clock=0;ApexCatalogSelection(grid);assert.equal(writes,1);
clock=800;ApexCatalogSelection(grid);assert.equal(writes,2);assert.equal(currentAlpha,.65*.25);
clock=900;ApexCatalogSelection(grid);assert.equal(writes,2);
apexCatalogPrefs.animation='pulse';let prior=writes;
for(const time of[0,100,350,700,1100]){clock=time;ApexCatalogSelection(grid);const phase=(time%1400)/1400;
assert.ok(Math.abs(currentAlpha-.65*(.4+.6*(.5-.5*Math.cos(phase*Math.PI*2))))<1e-12);}
assert.ok(writes>prior);const same=writes;ApexCatalogSelection(grid);assert.equal(writes,same);
currentAlpha=.9;ApexCatalogSelection(grid);assert.equal(writes,same+1);assert.equal(apexCatalogEffects[0].effect,effect);
''')

    def test_actual_visible_frame_position_respects_changed_stage_panel_width_and_tabs(self):
        code=javascript_function('ApexCatalogFrame','event=null',WORKSPACE)
        code=re.sub(r'catch\((\w+):\w+\)',r'catch(\1)',code)
        code=code.replace('panel is ClothingPanel','panel instanceof ClothingPanel')
        self.execute(r'''
const assert=require('node:assert/strict');function int(n){return Math.trunc(n);}int.MAX_VALUE=2147483647;class ClothingPanel{}
const flash={utils:{getTimer(){return 0;}}};const stage={stageWidth:2560};
let x=12,y=75,xWrites=0,yWrites=0;
const apexCatalogUi={visible:true,width:320,get x(){return x;},set x(value){xWrites++;x=value;},get y(){return y;},set y(value){yWrites++;y=value;}};
let apexCatalogPrefs={},apexDisconnected=false,apexCatalogFrameCells=null,apexCatalogEffects=[],apexCatalogHeaderSignature='',apexCatalogTab='style';
let apexCatalogContext='',mCurrSimInfo=null,apexCatalogDirty=false,apexPendingFields=null,apexReceiving=false,apexCatalogIntent=null,apexCatalogGrid=null;
let apexCatalogError='',apexCatalogFrameTiming={samples:0,total_ms:0,max_ms:0,over_1ms:0};
const mCurrentPanel=null;
function ApexPanelsFrame(){}function ApexCatalogApplyBinding(){}function ApexColumnsFrame(){}function ApexEquippedFrame(){}
function ApexSearchFrame(){}function ApexCompanionFrame(){}function ApexCatalogKeyboardFrame(){}function ApexCatalogClearEffects(){}
function ApexCardRestore(){}function removeEventListener(){}const thisRoot={mCurrentPanel};
'''+code+r'''
for(let frame=0;frame<500;frame++)ApexCatalogFrame.call(thisRoot);assert.equal(xWrites,0);assert.equal(yWrites,0);assert.equal(apexCatalogError,'');
apexCatalogTab='items';ApexCatalogFrame.call(thisRoot);assert.equal(x,2220);assert.equal(xWrites,1);
for(let frame=0;frame<500;frame++)ApexCatalogFrame.call(thisRoot);assert.equal(xWrites,1);
stage.stageWidth=2048;ApexCatalogFrame.call(thisRoot);assert.equal(x,1708);assert.equal(xWrites,2);
apexCatalogUi.width=400;ApexCatalogFrame.call(thisRoot);assert.equal(x,1628);assert.equal(xWrites,3);
stage.stageWidth=300;ApexCatalogFrame.call(thisRoot);assert.equal(x,12);assert.equal(xWrites,4);
apexCatalogTab='style';ApexCatalogFrame.call(thisRoot);assert.equal(xWrites,4);
x=-37.25;y=-8.5;ApexCatalogFrame.call(thisRoot);assert.equal(x,12);assert.equal(y,75);assert.equal(xWrites,5);assert.equal(yWrites,1);
apexCatalogUi.visible=false;x=-10;y=-10;ApexCatalogFrame.call(thisRoot);assert.equal(x,-10);assert.equal(y,-10);assert.equal(xWrites,5);assert.equal(yWrites,1);
''')

    def test_ui_scale_and_requested_card_geometry_remain_the_actual_fitted_oracle(self):
        self.execute(card.CardGeometryTests().harness()+r'''
for(const scale of[.8,1,1.25,1.6]){uiScale=scale;stage.stageWidth=2560;stage.logicalWidth=2560/scale;apexCatalogFrameCells=null;
const width=ApexCardApply(panel,grid);assert.ok(Number.isFinite(width)&&width>0);assert.ok(width<=40+6*(111+4));
assert.equal(grid.columns,12);assert.equal(apexCardLayout.requested_columns,12);
for(const cell of grid.cells){assert.ok(Number.isFinite(cell.scaleX)&&cell.scaleX>0);assert.ok(Number.isFinite(cell.scaleY)&&cell.scaleY>0);}}
''')


if __name__=='__main__':unittest.main()
