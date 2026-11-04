"""Execute the actual AS synthetic-input boundaries with adversarial grids."""
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


def method(file, name, parameters):
    source = (ROOT / 'Source/CASUi' / file).read_text(encoding='utf-8')
    tail = source.split('private function ' + name + '(', 1)[1]
    tail = re.split(r'\n      private (?:function|var) ', tail, maxsplit=1)[0]
    body = tail.split('{', 1)[1].rsplit('}', 1)[0]
    body = re.sub(r'\b(var\s+\w+)\s*:\s*[\w.]+', r'\1', body)
    body = re.sub(r'\s+as\s+flash\.[\w.]+', '', body)
    body = re.sub(r'catch\((\w+):Error\)', r'catch(\1)', body)
    return 'function ' + name + '(' + parameters + '){' + body + '}\n'


HARNESS = r'''
const assert=require('node:assert/strict');const int=x=>Number(x)|0;
let owned=true,pending=false,inputAllowed=true,typing=false,modal=false,inputReads=0,clicks=[],scrolls=[],legacyProbes=0,onInput=null;
const stage={},view={visible:true,addChild(c){c.parent=this;},dispatchEvent(e){clicks.push(e);}};
class Sprite{constructor(){this.graphics={clear(){},lineStyle(){},drawRoundRect(){}};this.visible=true;}}
const flash={display:{Sprite},utils:{getTimer:()=>1000}};
class GridEvent{constructor(type,rect,rects,data,selected,dataIndex,cellIndex){Object.assign(this,{type,mData:data,mDataIndex:dataIndex,mCellIndex:cellIndex});}static CELL_EVENT='cell';}
const PushButtonEvent={CLICK:'click'};
const items=[{data_id:'11',body_type:29},{data_id:'22',body_type:29},{data_id:'33',body_type:29}];
const feed={items,mapping:[2,0],get length(){return this.items.length;},RequestItemAt(i){return this.items[i]||null;},GetSelectedIndices(){return [0];}};
let generation=4,revision=7;
function cell(index){return {index,parent:view,stage,visible:true,getBounds(){return {x:0,y:index*80,top:index*80,bottom:index*80+70,width:50,height:70};}};}
let cells=[cell(1),cell(0)];
const grid={
 GetDataFeed:()=>feed,GetNumItems:()=>feed.mapping==null?feed.length:feed.mapping.length,
 GetDataAtIndex:i=>feed.RequestItemAt(feed.mapping==null?i:feed.mapping[i]),GetFilteredDataIndices:()=>feed.mapping,
 GetGridDimensions:()=>[2,1],Horizontal:true,GetViewAtIndex:i=>cells.find(c=>c.index===i)||null,
 GetGridIndexOfCell:c=>c.index,GetVisibleCells:()=>cells,get ApexGridCells(){return cells;},
 ApexGridStatus:()=>({phase:pending?'bind':'done',dirty:pending,cancelled:false,generation,revision}),
 GetPositionOfIndex(i){legacyProbes++;if(owned)throw Error('Unbudgeted native probe');return i*100;}
};
const list={visible:true,mGridLayout:grid,GetGridView:()=>view,ScrollerViewMargin:{mTop:4},
 mSlider:{SetCurrentValue(value){scrolls.push(value);}},mScrollerView:{GetScrollingRegion:()=>({top:0,bottom:200})}};
const panel={visible:true,mcTileList:list};
const lease={phase:'bound',active:true,generation:9,native_generation:'73'};
var apexCatalogGrid={lease},apexCardLayout={columns:2,pitch_y:80};
function ApexCatalogGridOwns(g){return owned&&g===grid;}
function ApexCatalogGridPending(g){return pending;}
function ApexCatalogGridInput(l){inputReads++;if(onInput)onInput();return l===apexCatalogGrid.lease&&inputAllowed;}
var mCurrentPanel=panel,mCurrSimInfo={simId:'101'},mCurrState=40,apexBoundSim='101',apexFormsSelectedId='human/first',apexEquippedActive=false;
var apexDisconnected=false,apexPendingFields=null,apexReceiving=false;
var apexKeyStage=stage,apexKeyIntent=0,apexKeyIndex=-1,apexKeyFeed=feed,apexKeyContext='',apexKeyBounds='',apexKeyItem=null,
 apexKeyFocus=null,apexKeyMessage='',apexKeyQueue=[],apexKeyReceipt=null,apexKeyInjecting=false,apexKeyReceived=0,apexKeyLastCode=0,apexKeyRejected='';
function ApexCatalogKeyboardInitialize(){}function ApexCatalogKeyboardTyping(){return typing;}
const CommunicationManager={CallUIService:()=>modal};
function event(code){return {keyCode:code,ctrlKey:false,altKey:false,shiftKey:false,prevented:false,stopped:false,
 preventDefault(){this.prevented=true;},stopImmediatePropagation(){this.stopped=true;}};}
function key(code){const e=event(code);ApexCatalogKeyDown(e);return e;}
function focus(index){apexKeyIndex=index;apexKeyItem=grid.GetDataAtIndex(index);apexKeyContext='101|human/first|40|false'+(owned?'|73|9':'');}
function ApexSearchContext(){return '101|human/first|73|40';}
var apexSearch={pending:false,feed,rows:items,panel,context:ApexSearchContext(),root:{parent:{}}};
var apexCompanion={donor:null,grid:view,root:{visible:true},stage,intent:null,context:ApexSearchContext(),feed,
 favorites:{'part/29/33':true},hidden:{},recent:[],dirty:false,persist:false,persist_catalog:false,resize:null,message:'',hide_mode:false};
function ApexCompanionAttach(){}function ApexCompanionSave(){}function ApexCompanionBadges(){}
function ApexCompanionChanged(){apexCompanion.dirty=true;}
function ApexCompanionReceipt(action,product){apexCompanion.receipt={action,product};}
function ApexSearchPublish(){}function ApexCatalogPersist(){}
'''


@unittest.skipUnless(shutil.which('node'), 'Node required for actual AS input fixtures')
class IncrementalInputTests(unittest.TestCase):
    def run_source(self, test):
        source = HARNESS
        for file, name, params in (
            ('catalog_keyboard_methods.as', 'ApexCatalogKeyDown', 'event'),
            ('catalog_keyboard_methods.as', 'ApexCatalogKeyboardFrame', 'controlled=false'),
            ('catalog_keyboard_methods.as', 'ApexCatalogKeyboardCommand', 'value'),
            ('catalog_companion_methods.as', 'ApexCompanionKey', 'product'),
            ('catalog_companion_methods.as', 'ApexCompanionIntent', 'action,product=null'),
            ('catalog_companion_methods.as', 'ApexCompanionApply', 'action,product=null'),
            ('catalog_companion_methods.as', 'ApexCompanionFrame', ''),
        ):
            source += method(file, name, params)
        result = subprocess.run(['node', '-'], input=source + test,
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_pending_catalog_key_is_consumed_and_never_queued_or_applied(self):
        self.run_source('''
pending=true;focus(0);const e=key(13);
assert.equal(e.prevented,true);assert.equal(e.stopped,true);assert.equal(apexKeyQueue.length,0);
ApexCatalogKeyboardFrame();assert.equal(clicks.length,0);assert.equal(inputReads,0);
assert.equal(apexKeyIndex,0);assert.match(apexKeyRejected,/loading/);
typing=true;const text=key(13);assert.equal(text.prevented,false);
''')

    def test_key_queued_before_partial_rebind_is_dropped_without_replay(self):
        self.run_source('''
focus(0);key(13);pending=true;ApexCatalogKeyboardFrame();pending=false;ApexCatalogKeyboardFrame();
assert.equal(clicks.length,0);assert.equal(inputReads,0);assert.equal(apexKeyQueue.length,0);assert.equal(apexKeyIndex,0);
''')

    def test_exact_sorted_item_and_physical_cell_index_are_dispatched(self):
        self.run_source('''
focus(0);key(13);ApexCatalogKeyboardFrame();
assert.equal(inputReads,1);assert.equal(clicks.length,1);assert.equal(clicks[0].mData,items[2]);
assert.equal(clicks[0].mDataIndex,0);assert.equal(clicks[0].mCellIndex,1);
assert.equal(apexKeyReceipt.click_dispatched,true);assert.equal(apexKeyReceipt.count,2);
// The selected feed index0 maps to virtual sorted index1, physical cell0.
clicks=[];apexKeyIndex=-1;apexKeyItem=null;key(13);ApexCatalogKeyboardFrame();
assert.equal(clicks[0].mData,items[0]);assert.equal(clicks[0].mDataIndex,1);assert.equal(clicks[0].mCellIndex,0);
''')

    def test_unbound_hidden_or_detached_enter_target_never_dispatches(self):
        for mutation in ('cells=[];', 'cells[1].visible=false;', 'cells[1].stage={};', 'cells[1].parent={};'):
            with self.subTest(mutation=mutation):
                self.run_source('focus(0);key(13);' + mutation + '''
ApexCatalogKeyboardFrame();assert.equal(clicks.length,0);assert.equal(apexKeyReceipt,null);
''')

    def test_stale_lease_generations_revision_and_focused_item_are_rejected(self):
        for mutation in ('apexCatalogGrid.lease={...lease};', 'lease.generation++;',
                         "lease.native_generation='74';", 'generation++;', 'revision++;',
                         "items[2]={data_id:'99',body_type:29};"):
            with self.subTest(mutation=mutation):
                self.run_source('focus(0);key(13);' + mutation + '''
ApexCatalogKeyboardFrame();assert.equal(clicks.length,0);assert.equal(apexKeyQueue.length,0);
''')

    def test_fresh_native_owner_failure_or_reentrant_results_change_refuses_equip(self):
        for mutation in ('inputAllowed=false;', 'onInput=()=>{revision++;};',
                         'onInput=()=>{pending=true;};', 'onInput=()=>{apexCatalogGrid.lease={...lease};};'):
            with self.subTest(mutation=mutation):
                self.run_source('focus(0);key(13);' + mutation + '''
ApexCatalogKeyboardFrame();assert.equal(inputReads,1);assert.equal(clicks.length,0);
''')

    def test_idle_focus_has_no_fresh_reads_and_owned_scroll_uses_confirmed_pitch(self):
        self.run_source('''
focus(0);for(let i=0;i<30;i++)ApexCatalogKeyboardFrame();assert.equal(inputReads,0);
feed.items=Array.from({length:60},(_,i)=>({data_id:String(i+100),body_type:29}));feed.mapping=null;
focus(0);key(35);ApexCatalogKeyboardFrame();assert.equal(apexKeyIndex,59);
assert.deepEqual(scrolls,[29*80+4]);assert.equal(legacyProbes,0);assert.equal(inputReads,1);
pending=true;ApexCatalogKeyboardFrame();assert.equal(apexKeyIndex,59);assert.equal(inputReads,1);
''')

    def test_unowned_catalog_keeps_native_keyboard_route_and_positioning(self):
        self.run_source('''
owned=false;pending=true;inputAllowed=false;focus(0);key(13);ApexCatalogKeyboardFrame();
assert.equal(clicks.length,1);assert.equal(inputReads,0);assert.equal(clicks[0].mData,items[0]);
cells=[];key(35);ApexCatalogKeyboardFrame();assert.equal(legacyProbes,1);
''')

    def test_random_favorite_requires_ready_grid_and_fresh_current_owner(self):
        for mutation in ('pending=true;', 'view.visible=false;', 'inputAllowed=false;'):
            with self.subTest(mutation=mutation):
                self.run_source(mutation + '''
assert.throws(()=>ApexCompanionApply('random-favorite'));
assert.equal(clicks.length,0);
''')
        self.run_source('''
ApexCompanionApply('random-favorite');assert.equal(inputReads,1);assert.equal(clicks.length,1);
assert.equal(clicks[0].mData,items[2]);assert.equal(clicks[0].mDataIndex,0);
''')

    def test_queued_random_favorite_cannot_cross_rebound_lease_or_revision(self):
        for mutation in ('pending=true;', 'apexCatalogGrid.lease={...lease};',
                         'lease.generation++;', "lease.native_generation='74';", 'generation++;', 'revision++;'):
            with self.subTest(mutation=mutation):
                self.run_source("ApexCompanionIntent('random-favorite');" + mutation + '''
ApexCompanionFrame();assert.equal(clicks.length,0);assert.equal(apexCompanion.intent,null);
assert.match(apexCompanion.message,/catalog changed/);
''')

    def test_random_candidate_scan_is_rechecked_after_fresh_owner_read(self):
        for mutation in ('revision++;', 'pending=true;', "items[2]={data_id:'99',body_type:29};"):
            with self.subTest(mutation=mutation):
                self.run_source('onInput=()=>{' + mutation + '''};
assert.throws(()=>ApexCompanionApply('random-favorite'));assert.equal(inputReads,1);assert.equal(clicks.length,0);
''')

    def test_preference_actions_and_unowned_random_favorite_remain_available(self):
        self.run_source('''
pending=true;inputAllowed=false;ApexCompanionIntent('favorites');ApexCompanionFrame();
assert.equal(apexCompanion.mode,'favorites');assert.equal(inputReads,0);
owned=false;ApexCompanionApply('random-favorite');assert.equal(clicks.length,1);assert.equal(inputReads,0);
''')


if __name__ == '__main__':
    unittest.main()
