"""Exercise the actual display geometry and async stamp method bodies offline."""
from pathlib import Path
import re
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'Source/CASUi/panel_layout_methods.as'


def javascript_body(name, source_path=SOURCE):
    """Erase AS type annotations only; execute the checked-in method logic."""
    source = source_path.read_text(encoding='utf-8')
    part = source.split('private function ' + name + '(', 1)[1]
    part = re.split(r'\n      private (?:function|var) ', part, maxsplit=1)[0]
    body = part.split('{', 1)[1].rsplit('}', 1)[0]
    body = re.sub(r'\b(var\s+\w+)\s*:\s*[\w.]+', r'\1', body)
    body = re.sub(r'catch\((\w+):Error\)', r'catch(\1)', body)
    body = body.replace(' is flash.display.Sprite', ' instanceof flash.display.Sprite')
    body = body.replace(' is Function', ' instanceof Function')
    body = re.sub(r'([\w.]+) is int', r'Number.isInteger(\1)', body)
    body = re.sub(r'for each\(var (\w+) in (\[[^\]]*\])\)', r'for(var \1 of \2)', body)
    return re.sub(r'\s+as\s+flash\.[\w.]+', '', body)


@unittest.skipUnless(shutil.which('node'), 'Node is required for the AS method harness')
class PanelSchedulingTests(unittest.TestCase):
    def run_javascript(self, source):
        result = subprocess.run(['node', '-e', source], capture_output=True,
                                text=True, encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def stamp_harness(self):
        return '''
const assert=require('node:assert/strict');
var now=10,flash={utils:{getTimer:()=>now}},mCurrSimInfo={simId:'42'},apexFormsSelectedId='vampire',apexNativeChannel='lease';
var apexPanels, replies, calls;
function reset(){apexPanels={stamp_ticket:'',stamp_context:'',stamp_max_ms:0,stamp_wait:false,stamp_retry:0,
    key:'old',job:{phase:'verify'},requested:false,stale:0};replies=[];calls=[];}
function ApexNativeExchange(command){calls.push(command);assert.ok(replies.length,'Unexpected native request');return replies.shift();}
function ApexPanelsStamp(context){''' + javascript_body('ApexPanelsStamp') + '}\n'

    def test_one_ticket_is_polled_until_ready_then_fresh_verification_starts(self):
        self.run_javascript(self.stamp_harness() + '''
reset();replies=['STAMPJOB|42|vampire|18446744073709551615','STAMPPENDING|18446744073709551615',
    'EQUIPPEDSTAMP|42|vampire|'+ 'a'.repeat(64),'STAMPJOB|42|vampire|2'];
assert.equal(ApexPanelsStamp('outfit-A'),'');assert.equal(apexPanels.stamp_context,'outfit-A');
assert.equal(ApexPanelsStamp('outfit-A'),'');assert.equal(ApexPanelsStamp('outfit-A'),'a'.repeat(64));
assert.equal(apexPanels.stamp_ticket,'');assert.equal(ApexPanelsStamp('outfit-A'),'');
assert.deepEqual(calls,['EQUIPPEDSTAMPSTART|lease','EQUIPPEDSTAMPREAD|lease|18446744073709551615',
    'EQUIPPEDSTAMPREAD|lease|18446744073709551615','EQUIPPEDSTAMPSTART|lease']);
assert.equal(apexPanels.stamp_wait,true);
''')

    def test_busy_stale_and_foreign_receipts_never_publish_a_stamp(self):
        self.run_javascript(self.stamp_harness() + '''
reset();replies=['STAMPBUSY'];assert.equal(ApexPanelsStamp('outfit-A'),'');
assert.equal(apexPanels.stamp_ticket,'');assert.equal(apexPanels.stamp_retry,110);
reset();apexPanels.stamp_ticket='9';replies=['STAMPSTALE|9'];assert.equal(ApexPanelsStamp('outfit-A'),'');
assert.equal(apexPanels.job,null);assert.equal(apexPanels.key,'');assert.equal(apexPanels.requested,true);
assert.equal(apexPanels.stale,1);assert.equal(apexPanels.stamp_ticket,'');
for(const receipt of ['STAMPJOB|99|vampire|1','STAMPJOB|42|human|1','STAMPJOB|42|vampire|0',
    'STAMPJOB|42|vampire|0001','STAMPJOB|42|vampire|'+ '1'.repeat(21),'STAMPBUSY|1']){
    reset();replies=[receipt];assert.throws(()=>ApexPanelsStamp('outfit-A'));assert.equal(apexPanels.stamp_ticket,'');}
for(const receipt of ['STAMPPENDING|8','STAMPSTALE|8','EQUIPPEDSTAMP|42|human|'+ 'a'.repeat(64),
    'EQUIPPEDSTAMP|42|vampire|'+ 'A'.repeat(64),'EQUIPPEDSTAMP|42|vampire|abc']){
    reset();apexPanels.stamp_ticket='9';replies=[receipt];assert.throws(()=>ApexPanelsStamp('outfit-A'));}
''')

    def test_frame_polls_once_and_defers_busy_closed_panels_and_dragging(self):
        self.run_javascript(self.stamp_harness() + '''
flash.display={Sprite:class{getChildByName(){return body;}}};
var body={visible:true},stage={},drawer={0:new flash.display.Sprite(),40:{visible:true},5:2,6:1},apexColumns=null;
var apexFormsDesiredId='',apexFormsApplying=false,apexPendingFields=null,apexReceiving=false;
mCurrSimInfo.gender=1;mCurrSimInfo.age=32;mCurrSimInfo.speciesType=1;
function int(x){return Math.trunc(x);}
function ApexPanelsDrawer(){return drawer;}function ApexPanelsAdopt(){}function ApexPanelsApply(){}
function ApexPanelsPreview(){}function ApexPanelsContext(){return 'outfit-A';}
function ApexPanelsWork(){ApexPanelsStamp('outfit-A');}
function ApexPanelsFrame(){''' + javascript_body('ApexPanelsFrame') + '''}
reset();Object.assign(apexPanels,{stage,owner:'lease|42|vampire|1|32|1',drag:null,requested:true,
    slices:0,slice_max_ms:0,over_1ms:0,save:false});
replies=['STAMPJOB|42|vampire|1','STAMPPENDING|1'];
ApexPanelsFrame();assert.equal(calls.length,1);ApexPanelsFrame();assert.equal(calls.length,2);
body.visible=false;ApexPanelsFrame();assert.equal(calls.length,2);body.visible=true;
apexPanels.drag={};ApexPanelsFrame();assert.equal(calls.length,2);apexPanels.drag=null;
apexColumns={drag:false,scale_drag:true};ApexPanelsFrame();assert.equal(calls.length,2);apexColumns=null;
apexPanels.stamp_ticket='';replies=['STAMPBUSY'];ApexPanelsFrame();assert.equal(calls.length,3);
now=109;ApexPanelsFrame();assert.equal(calls.length,3);
now=110;replies=['STAMPJOB|42|vampire|2'];ApexPanelsFrame();assert.equal(calls.length,4);
''')

    def test_drag_release_and_scaled_parent_keep_full_drawer_and_toolbar_on_screen(self):
        self.run_javascript('''
const assert=require('node:assert/strict');
var flash={geom:{Point:class{constructor(x,y){this.x=x;this.y=y;}}}},stage,apexPanels;
function ApexPanelsApply(target=null){''' + javascript_body('ApexPanelsApply') + '''}
for(const [width,height] of [[800,600],[1280,720],[1920,1080],[3840,2160]]){
for(const parentScale of [.75,1,1.5]){for(const scale of [.35,1,1.5]){
    stage={stageWidth:width,stageHeight:height};
    const parent={globalToLocal:p=>({x:(p.x-73)/parentScale,y:(p.y-51)/parentScale}),
        localToGlobal:p=>({x:p.x*parentScale+73,y:p.y*parentScale+51})};
    const caption={text:''},lockCaption={text:''};
    const handle={getChildByName:()=>caption},lock={getChildByName:()=>lockCaption};
    const root={parent,x:0,y:0,scaleX:1,scaleY:1,visible:true,getChildByName:()=>({visible:true})};
    apexPanels={root,grip:{getChildByName:n=>n==='apexPanel_move'?handle:lock},x:-1,y:-1,scale,locked:false};
    for(const point of [new flash.geom.Point(-999,-999),new flash.geom.Point(99999,99999)]){
        ApexPanelsApply(point);const global=parent.localToGlobal(root),size=root.scaleX*parentScale;
        assert.ok(global.x>=8-1e-7);assert.ok(global.y-30*size>=8-1e-7);
        assert.ok(global.x+790*size<=width-8+1e-7);assert.ok(global.y+656*size<=height-112+1e-7);
        const old={x:root.x,y:root.y};ApexPanelsApply();
        assert.ok(Math.abs(root.x-old.x)<1e-7);assert.ok(Math.abs(root.y-old.y)<1e-7);
    }
    apexPanels.locked=true;ApexPanelsApply();assert.equal(lockCaption.text,'Unlock');assert.equal(handle.buttonMode,false);
}}}
''')

    def test_collapse_returns_geometry_to_native_layout_and_reopens_saved_placement(self):
        self.run_javascript('''
const assert=require('node:assert/strict');
var flash={geom:{Point:class{constructor(x,y){this.x=x;this.y=y;}}}},stage={stageWidth:1920,stageHeight:1080};
const parent={globalToLocal:p=>({x:p.x,y:p.y}),localToGlobal:p=>({x:p.x,y:p.y})};
const body={visible:true},caption={text:''},handle={getChildByName:()=>caption},lock={getChildByName:()=>({text:''})};
const root={parent,x:0,y:0,scaleX:1,scaleY:1,visible:true,getChildByName:()=>body};
var nativeLayouts=0;
var apexPanels={root,grip:{getChildByName:n=>n==='apexPanel_move'?handle:lock},x:.4,y:.3,scale:.8,locked:false,
    drag:null,viewport:'',host:{Layout:p=>{assert.equal(p,parent);nativeLayouts++;root.x=0;root.y=240;root.scaleX=.9;root.scaleY=.9;}}};
function ApexPanelsDragEnd(){apexPanels.drag=null;}
function ApexPanelsApply(target=null){''' + javascript_body('ApexPanelsApply') + '''}
ApexPanelsApply();const expanded={x:root.x,y:root.y,scale:root.scaleX};
assert.equal(nativeLayouts,0);assert.equal(apexPanels.grip.visible,true);assert.equal(apexPanels.opened,true);
body.visible=false;ApexPanelsApply();
assert.equal(nativeLayouts,1);assert.equal(root.x,0);assert.equal(root.y,240);assert.equal(root.scaleX,.9);
assert.equal(apexPanels.grip.visible,false);assert.equal(apexPanels.opened,false);assert.equal(apexPanels.bounds,null);
assert.equal(apexPanels.x,.4);assert.equal(apexPanels.y,.3);assert.equal(apexPanels.scale,.8);
ApexPanelsApply(new flash.geom.Point(9999,9999));assert.equal(nativeLayouts,1);assert.equal(apexPanels.x,.4);
body.visible=true;ApexPanelsApply();
assert.equal(apexPanels.grip.visible,true);assert.equal(root.x,expanded.x);assert.equal(root.y,expanded.y);
assert.equal(root.scaleX,expanded.scale);assert.equal(nativeLayouts,1);
body.visible=false;apexPanels.drag={};ApexPanelsApply();assert.equal(nativeLayouts,2);assert.equal(apexPanels.drag,null);
stage.stageHeight=900;ApexPanelsApply();assert.equal(nativeLayouts,3);assert.equal(apexPanels.grip.visible,false);
''')

    def test_phase_counters_use_actual_call_time_and_reset_only_the_new_job(self):
        self.run_javascript('''
const assert=require('node:assert/strict');
var now=0,flash={utils:{getTimer:()=>now},display:{Sprite:class{getChildByName(){return body;}}}};
var body={visible:true},stage={},drawer={0:new flash.display.Sprite(),40:{visible:true},5:2,6:1},apexColumns=null;
var mCurrSimInfo={simId:'42',gender:1,age:32,speciesType:1},apexNativeChannel='lease',apexFormsSelectedId='vampire';
var apexFormsDesiredId='',apexFormsApplying=false,apexPendingFields=null,apexReceiving=false;
function int(x){return Math.trunc(x);}
var CommunicationManager={CallGameService:()=>{now+=3;return {outfit_type:0,outfit_index:0};}};
var CASAPI={GetCatalogItemsSelected:()=>{now+=5;return ['part42'];}};
var CASCatalogProduct=class{constructor(raw){this.raw=raw;}};
var helpers={SavedOutfitNames:{AddEyeColor:()=>{now+=11;},CurrentCategoryPart:()=>{now+=7;return true;}},
    CurrentRemove:{Record:()=>{now+=2;}}};
for(const name of ['OutfitSwatchRoute','HairSwatches','OutfitRemoval','OutfitCategory'])helpers[name]={Register:()=>{now+=1;}};
drawer[0].parent={mcClothingPanel:{GetCatalogProduct:()=>{now+=13;return {};}}};
for(let group=0;group<4;group++){
    drawer[70+group]=group===0?[7]:[];
    drawer[47+group*3]={length:0,AddItem:function(){this.length++;now+=4;},ReplaceItemAt:()=>{now+=4;},RemoveItemAt:function(){this.length--;now+=3;}};
    drawer[49+group*3]={PositionCells:()=>{now+=19;}};
}
var apexPanels={stage,owner:'lease|42|vampire|1|32|1',drag:null,requested:true,stamp_retry:0,stamp_ticket:'',
    revision:0,job:null,job_metrics:null,last_job_metrics:null,key:'',helpers,metrics:{},slices:0,slice_max_ms:0,
    over_1ms:0,save:false,refreshes:0,refresh_max_ms:0,host:{LayoutCurrentOutfit:()=>{now+=23;}}};
for(const name of ['context','selected_ids','product','category_part','eye_color','feed_publish','position_cells','current_layout'])
    apexPanels.metrics[name]={calls:0,total_ms:0,max_ms:0,last_ms:0};
function ApexPanelsDrawer(){return drawer;}function ApexPanelsAdopt(){}function ApexPanelsApply(){}function ApexPanelsPreview(){}
var digest='a'.repeat(64);function ApexPanelsStamp(){return digest;}
function ApexPanelsContext(drawer){''' + javascript_body('ApexPanelsContext') + '''}
function ApexPanelsWork(drawer,context){''' + javascript_body('ApexPanelsWork') + '''}
function ApexPanelsFrame(){''' + javascript_body('ApexPanelsFrame') + '''}
function complete(){let limit=150;while((apexPanels.requested||apexPanels.job)&&limit-->0)ApexPanelsFrame();assert.ok(limit>0);}
complete();assert.equal(apexPanels.refreshes,1);
const first=apexPanels.last_job_metrics;assert.equal(first.completed,true);assert.equal(first.slice_max_ms,47);
assert.equal(first.last_phase,'current_layout');assert.equal(first.last_group,3);
for(const [name,calls,total,max,last] of [['selected_ids',1,5,5,5],['product',1,13,13,13],['category_part',1,7,7,7],
    ['eye_color',4,44,11,11],['feed_publish',5,12,4,2],['position_cells',4,76,19,19],['current_layout',1,23,23,23]]){
    assert.deepEqual(first.phases[name],{calls,total_ms:total,max_ms:max,last_ms:last});
    assert.deepEqual(apexPanels.metrics[name],first.phases[name]);
}
assert.equal(first.phases.context.total_ms,first.phases.context.calls*3);
assert.equal(apexPanels.metrics.context.calls,first.phases.context.calls+1);
digest='b'.repeat(64);apexPanels.requested=true;complete();
assert.equal(apexPanels.refreshes,2);assert.notEqual(apexPanels.last_job_metrics,first);
assert.equal(first.phases.product.calls,1);assert.equal(apexPanels.last_job_metrics.phases.product.calls,1);
assert.equal(apexPanels.metrics.product.calls,2);assert.equal(apexPanels.metrics.product.total_ms,26);
''')

    def test_history_density_changes_do_not_invalidate_appearance_data_or_query_the_game(self):
        self.run_javascript('''
const assert=require('node:assert/strict');var now=0,queries=0,work=0;
var flash={utils:{getTimer:()=>now},display:{Sprite:class{getChildByName(){return body;}}}};
var stage={},body={visible:true},drawer={0:new flash.display.Sprite(),40:{visible:true},5:2,6:1},apexColumns=null;
var mCurrSimInfo={simId:'arbitrary-sim-8888',gender:1,age:32,speciesType:1},apexNativeChannel='new-scope',apexFormsSelectedId='alien';
var apexFormsDesiredId='',apexFormsApplying=false,apexPendingFields=null,apexReceiving=false;
var apexPanels={stage,owner:'',drag:null,requested:false,job:null,consumer:null,stamp_retry:0,stamp_ticket:'',key:'',
    slices:0,slice_max_ms:0,over_1ms:0,save:false,job_metrics:null,stale:0,metrics:{context:{calls:0,total_ms:0,max_ms:0,last_ms:0}}};
var slot={outfit_type:2,outfit_index:3},CommunicationManager={CallGameService:()=>{queries++;return slot;}};
function int(v){return Math.trunc(v);}function ApexPanelsDrawer(){return drawer;}
function ApexPanelsAdopt(){}function ApexPanelsApply(){}function ApexPanelsPreview(){}
function ApexPanelsWork(){work++;apexPanels.requested=false;}
function ApexPanelsContext(drawer){''' + javascript_body('ApexPanelsContext') + '''}
function ApexPanelsFrame(){''' + javascript_body('ApexPanelsFrame') + '''}
ApexPanelsFrame();apexPanels.requested=false;apexPanels.key='qualified-data';queries=0;work=0;
for(var columns=2;columns<=12;columns++)for(var size of [.65,1,1.6]){drawer[5]=columns;drawer[6]=size;ApexPanelsFrame();}
assert.equal(queries,0);assert.equal(work,0);assert.equal(apexPanels.key,'qualified-data');
var context=ApexPanelsContext(drawer);drawer[5]=3;drawer[6]=.8;assert.equal(ApexPanelsContext(drawer),context);
slot={outfit_type:2,outfit_index:4};assert.notEqual(ApexPanelsContext(drawer),context);
queries=0;work=0;mCurrSimInfo.gender=2;ApexPanelsFrame();assert.equal(work,1);assert.equal(queries,1);
''')


if __name__ == '__main__':
    unittest.main()
