"""Execute consumed navigation and publication waits from the actual AS source."""
from pathlib import Path
import re
import shutil
import subprocess
import unittest

from test_cas_catalog_readback import source_method

ROOT = Path(__file__).resolve().parents[1]


def keyboard_method(name, parameters):
    text = (ROOT/'Source/CASUi/catalog_keyboard_methods.as').read_text(encoding='utf-8')
    tail = text.split('private function '+name+'(', 1)[1]
    tail = re.split(r'\n      private (?:function|var) ', tail, maxsplit=1)[0]
    body = tail.split('{', 1)[1].rsplit('}', 1)[0]
    body = re.sub(r'\b(var\s+\w+)\s*:\s*[\w.*]+', r'\1', body)
    body = re.sub(r'\s+as\s+[\w.]+', '', body)
    body = re.sub(r'catch\((\w+)\s*:\s*Error\)', r'catch(\1)', body)
    return 'function '+name+'('+parameters+'){'+body+'}\n'


@unittest.skipUnless(shutil.which('node'), 'Node is required for actual-AS publication tests')
class KeyboardPublicationTests(unittest.TestCase):
    def execute(self, test, injected=False):
        code = r'''
const assert=require('node:assert/strict');const int=x=>Number(x)|0;
function isType(v,t){return t==='Array'?Array.isArray(v):t==='int'?Number.isInteger(v):typeof v===t.toLowerCase();}
class Rectangle {
 constructor(x=0,y=0,width=100,height=100){Object.assign(this,{x,y,width,height});}
 get top(){return this.y;} get bottom(){return this.y+this.height;}
 clone(){return new Rectangle(this.x,this.y,this.width,this.height);}
 inflate(x,y){this.x-=x;this.y-=y;this.width+=x*2;this.height+=y*2;}
 containsRect(r){return r.x>=this.x&&r.y>=this.y&&r.x+r.width<=this.x+this.width&&r.bottom<=this.bottom;}
}
class Sprite {
 constructor(){this.visible=true;this.parent=null;this.graphics={clear(){},lineStyle(){},drawRoundRect(){}};}
 get stage(){return this.parent?this.parent.stage:null;}
}
class KeyboardEvent{constructor(){}preventDefault(){}stopImmediatePropagation(){}}
KeyboardEvent.KEY_DOWN='keydown';
var now=100,stage={focus:null},flash={display:{Sprite},geom:{Rectangle},utils:{getTimer:()=>now},events:{KeyboardEvent}};
var apexCatalogTrace=null,apexTicking=true,apexDisconnected=false,apexSocketActive=true,apexNativeChannel='7';
var apexNonce='a'.repeat(64),apexClaimNonce=apexNonce,apexBoundSim='12';
// Native family shell and displayed owner kind intentionally differ.
var mCurrSimInfo={simId:'12',householdId:'34',occultLayer:0,occultType:2,allOccultTypes:127};
var fresh={...mCurrSimInfo,occultType:4};
var apexOwnerSession=3,apexFormsNativeState='bound',apexFormsSelectedId='active/2',apexFormsDesiredId='',apexFormsNativeGeneration='91';
var apexFormsIntent=null,apexFormsNativeIntent=null,apexMoleculeIntent=null,apexPairIntent=null,apexFormsApplying=false;
var mCurrState=40,apexTimer={currentCount:10},apexReadbackTick=1,apexPendingPhase=1,apexAwaiting='';
var apexPendingFields=['b'.repeat(32),'12','catalog-key','0','0','0','pagedown'];
var apexPendingReply={protocol:1,ok:false,cas_request_id:apexPendingFields[0],operation:'catalog-key',scope:'native-cas-client',mutation_started:false};
var apexPendingContext={},apexKeyStage=stage,apexKeyFeed=null,apexKeyContext='',apexKeyIndex=-1,apexKeyItem=null;
var apexKeyBounds='',apexKeyFocus=null,apexKeyQueue=[],apexKeyIntent=0,apexKeyReceipt=null,apexKeyMessage='',apexKeyRejected='';
var apexKeyInjecting=false,apexKeyReceived=0,apexKeyLastCode=0;
var apexReceiving=false,apexEquippedActive=false,apexCardLayout={columns:6,pitch_y:140};
var pending=false,generation=3,revision=3,scrolls=0,dispatches=0,snapshots=0,acks=[],nativeCalls=[];
var items=Array.from({length:176},(_,i)=>({dataID:String(i)}));
var feed={length:176,GetSelectedIndices:()=>[101],RequestItemAt:i=>items[i]};
var view={visible:true,stage,addChild(c){c.parent=this;},dispatchEvent(){dispatches++;}};
var cell={visible:true,stage,parent:view,getBounds:()=>new Rectangle(4,4,92,92)};
var scroller={GetScrollingRegion:()=>new Rectangle(0,0,100,100)};
var grid={Horizontal:true,GetDataFeed:()=>feed,GetDataAtIndex:i=>items[i],GetNumItems:()=>176,
 GetGridDimensions:()=>[6,30],GetFilteredDataIndices:()=>items.map((_,i)=>i),
 GetVisibleCells:()=>new Array(54),GetViewAtIndex:i=>!pending&&i===apexKeyIndex?cell:null,
 GetGridIndexOfCell:c=>c===cell?apexKeyIndex:-1,ApexGridStatus:()=>({generation,revision})};
var list={visible:true,mGridLayout:grid,mScrollerView:scroller,ScrollerViewMargin:{mTop:0},
 GetGridView:()=>view,mSlider:{SetCurrentValue(v){scrolls++;pending=true;generation++;}}};
var mCurrentPanel={visible:true,stage,mcTileList:list};
var lease={generation:30,native_generation:'91',phase:'bound',active:true};
var apexCatalogGrid={lease};
function ApexCatalogGridOwns(g){return g===grid;}function ApexCatalogGridPending(g){return pending;}
function ApexCatalogGridLeaseCurrent(l){return l===lease&&l.active&&l.phase==='bound';}
function ApexCatalogGridInput(l){return ApexCatalogGridLeaseCurrent(l);}
function ApexCatalogKeyboardInitialize(){apexKeyStage=stage;}
function ApexCatalogKeyboardTyping(){return false;}
function ApexEncode(v){return JSON.stringify(v);}function ApexClone(v){return JSON.parse(JSON.stringify(v));}
var cursor='VIEWSTATE|12|active/2|2|0|bound|91',outfit={outfit_type:9,outfit_index:0};
const CommunicationManager={CallGameService(name){nativeCalls.push(name);if(name==='CASGetSimInfo')return fresh;
 if(name==='CasGetCurrSimOutfitSlot')return outfit;throw Error('Unexpected mutation '+name);},CallUIService(){return false;}};
function ApexNativeExchange(v){assert.equal(v,'STATE|7');return cursor;}
function ApexCatalogStatus(){return {error:'',context:'12|active/2',outfit:{category:9,index:0},
 keyboard:{index:apexKeyIndex,pending:apexKeyIntent,queued:apexKeyQueue.length,receipt:apexKeyReceipt,visibility:ApexCatalogKeyboardVisibility()}};}
var snapshotHook=null;
function ApexSnapshot(){snapshots++;if(snapshotHook)snapshotHook();return {scope:'native-cas-client',sim:{...fresh},
 menu_state:mCurrState,panel_visible:true,outfit:{...outfit},catalog_workspace:ApexCatalogStatus()};}
function ApexComplete(){acks.push(ApexClone(apexPendingReply));apexPendingFields=null;}
const MenuState={CLOTHING_BODY_WINGS:114};
'''
        for name, params in (
            ('ApexCatalogKeyboardFrame', 'controlled=false'),
            ('ApexCatalogKeyboardCommand', 'value'),
            ('ApexCatalogKeyDown', 'event'),
            ('ApexCatalogKeyboardInput', 'value'),
            ('ApexCatalogKeyboardVisibility', ''),
            ('ApexCatalogKeyboardScopeEqual', 'left,right'),
            ('ApexCatalogKeyboardPublication', 'before'),
            ('ApexCatalogKeyboardPublicationReady', 'held'),
        ):
            code += keyboard_method(name, params)
        for name, params, stop in (
            ('ApexOwnerSimRow', 'raw', None), ('ApexCatalogReadbackOnly', 'operation', None),
            ('ApexCatalogReadbackContext', 'selected', None),
            ('ApexControlResult', 'operation,state,category,index,value,context,client', 'if(operation=="form-owner-select")'),
            ('ApexReadback', '', None),
        ):
            code += source_method(name, params, stop)
        code += r'''
function readback(){apexTimer.currentCount++;ApexReadback.call({mCurrState,mCurrSimInfo,mCurrentPanel});}
apexPendingContext.keyboard_before=ApexCatalogReadbackContext(ApexOwnerSimRow(fresh));
'''
        if injected:
            code += "apexPendingFields[2]='catalog-input';apexPendingFields[6]='pagedown,1';apexPendingReply.operation='catalog-input';ApexCatalogKeyboardInput('pagedown,1');\n"
        else:
            code += "ApexCatalogKeyboardCommand('pagedown');\n"
        code += r'''
assert.equal(scrolls,1);assert.equal(apexKeyIndex,149);assert.equal(apexKeyReceipt.index_before,101);
apexPendingContext.keyboard_publication=ApexCatalogKeyboardPublication(apexPendingContext.keyboard_before);
assert.equal(pending,true);assert.equal(generation,4);
'''
        run = subprocess.run(['node', '-'], input=code+test, text=True, capture_output=True, timeout=15)
        self.assertEqual(run.returncode, 0, run.stdout+run.stderr)

    def test_waits_for_native_publication_then_acknowledges_original_once_without_input_replay(self):
        self.execute(r'''
for(let i=0;i<15;i++){now+=100;readback();assert.equal(acks.length,0);assert.equal(snapshots,0);}
assert.equal(apexKeyIndex,149);assert.equal(scrolls,1);assert.equal(dispatches,0);
pending=false;readback();assert.equal(acks.length,1);assert.equal(acks[0].ok,true);
assert.equal(acks[0].cas_request_id,'b'.repeat(32));assert.equal(snapshots,1);
assert.equal(acks[0].client.control.workspace.keyboard.visibility.focus_visible,true);
for(let i=0;i<3;i++)readback();assert.equal(acks.length,1);assert.equal(scrolls,1);assert.equal(dispatches,0);
assert.equal(nativeCalls.every(n=>n==='CASGetSimInfo'||n==='CasGetCurrSimOutfitSlot'),true);
''')

    def test_actual_shared_keyboard_event_consumes_once_and_waits_for_its_own_publication(self):
        self.execute(r'''
assert.equal(apexKeyReceived,1);assert.equal(apexKeyReceipt.source_route,'shared-keyboard-handler');
assert.equal(stage.focus,view);readback();assert.equal(acks.length,0);assert.equal(snapshots,0);
pending=false;readback();assert.equal(acks.length,1);assert.equal(acks[0].ok,true);
assert.equal(acks[0].client.control.handler_invoked,true);assert.equal(acks[0].client.control.focus_requested,true);
assert.equal(acks[0].client.control.appearance_write_possible,false);
assert.equal(apexKeyReceived,1);assert.equal(scrolls,1);assert.equal(dispatches,0);
''', injected=True)

    def test_generation_advance_is_allowed_but_feed_revision_or_original_lease_changes_refuse(self):
        for mutation in ('revision++;', 'lease.generation++;', 'lease.active=false;',
                         'apexCatalogGrid.lease={...lease};', 'feed={...feed};',
                         'grid={...grid};', "apexKeyReceipt={...apexKeyReceipt};"):
            with self.subTest(mutation=mutation):
                self.execute(mutation+r'''
readback();assert.equal(acks.length,1);assert.equal(acks[0].ok,false);
const after=acks[0].navigation_publication.after;assert.ok(after===null || Object.keys(after).length===12);
assert.notEqual(acks[0].message,'Native catalog navigation did not publish its focused card before the bounded deadline');
assert.equal(scrolls,1);assert.equal(dispatches,0);
''')

    def test_original_owner_room_nonce_outfit_and_target_are_never_adopted(self):
        for mutation in ("fresh={...fresh,simId:'13'};", "fresh={...fresh,householdId:'35'};",
                         "apexFormsNativeGeneration='92';", 'apexOwnerSession++;',
                         "apexNonce='f'.repeat(64);", 'stage={};', 'mCurrState++;',
                         'outfit={outfit_type:0,outfit_index:0};',
                         "items[149]={dataID:'149'};pending=false;", 'apexKeyQueue=[{key:34}];'):
            with self.subTest(mutation=mutation):
                self.execute(mutation+r'''
readback();assert.equal(acks.length,1);assert.equal(acks[0].ok,false);
const after=acks[0].navigation_publication.after;assert.ok(after===null || Object.keys(after).length===12);
assert.notEqual(acks[0].message,'Native catalog navigation did not publish its focused card before the bounded deadline');
assert.equal(scrolls,1);assert.equal(dispatches,0);
''')

    def test_timeout_exports_complete_original_navigation_scope_without_false_success(self):
        self.execute(r'''
now+=10000;readback();assert.equal(acks.length,1);const ack=acks[0];assert.equal(ack.ok,false);
assert.equal(snapshots,1);assert.equal(ack.mutation_started,false);assert.equal(scrolls,1);assert.equal(dispatches,0);
const proof=ack.navigation_publication;assert.equal(proof.published,false);assert.equal(proof.appearance_written,false);
assert.equal(proof.elapsed_ms,10000);assert.deepEqual(proof.before,proof.after);
assert.equal(proof.before.shell_kind,4);assert.equal(proof.before.native_kind,2);
assert.equal(proof.request_id,'b'.repeat(32));assert.equal(proof.peer_nonce,'a'.repeat(64));
assert.equal(proof.key,34);assert.equal(proof.target_index,149);
assert.equal(ack.client.control.workspace.keyboard.visibility.available,false);
''')

    def test_reentrant_snapshot_publication_change_yields_again_instead_of_acknowledging(self):
        self.execute(r'''
pending=false;snapshotHook=()=>{pending=true;};readback();assert.equal(acks.length,0);
assert.equal(apexPendingReply.client,null);assert.equal(snapshots,1);assert.equal(scrolls,1);
snapshotHook=null;pending=false;readback();assert.equal(acks.length,1);assert.equal(acks[0].ok,true);
assert.equal(scrolls,1);assert.equal(dispatches,0);
''')

    def test_visible_cell_still_requires_exact_grid_mapping_attached_focus_and_scroller_visibility(self):
        for mutation in ('grid.GetGridIndexOfCell=()=>148;', 'cell.parent={};', 'cell.visible=false;',
                         'cell.getBounds=()=>new Rectangle(4,110,92,92);', 'view.visible=false;'):
            with self.subTest(mutation=mutation):
                self.execute('pending=false;'+mutation+r'''
readback();assert.equal(acks.length,0);assert.equal(scrolls,1);assert.equal(dispatches,0);
now+=10000;readback();assert.equal(acks.length,1);assert.equal(acks[0].ok,false);
assert.equal(acks[0].navigation_publication.published,false);
''')

    def test_enter_is_not_a_navigation_publication_and_is_not_replayed(self):
        self.execute(r'''
assert.throws(()=>ApexCatalogKeyboardPublication(null));
apexKeyReceipt={...apexKeyReceipt,key:13,click_dispatched:true};
assert.throws(()=>ApexCatalogKeyboardPublication(apexPendingContext.keyboard_before));
assert.equal(scrolls,1);assert.equal(dispatches,0);
''')

    def test_first_native_getter_exception_is_unknown_scope_not_a_typed_timeout(self):
        self.execute(r'''
CommunicationManager.CallGameService=()=>{throw Error('Native getter failed');};
readback();assert.equal(acks.length,1);assert.equal(acks[0].ok,false);assert.equal(snapshots,0);
assert.equal(acks[0].navigation_publication.after,null);
assert.equal(acks[0].message,'Native getter failed');assert.equal(scrolls,1);assert.equal(dispatches,0);
''')

    def test_capture_exception_before_held_publication_keeps_unknown_scope_and_original_error(self):
        self.execute(r'''
apexPendingContext.keyboard_publication=null;apexPendingReply.message='Capture changed after input';
readback();assert.equal(acks.length,1);assert.equal(acks[0].ok,false);assert.equal(snapshots,0);
assert.equal(acks[0].navigation_publication.after,null);assert.equal(acks[0].navigation_publication.key,-1);
assert.equal(acks[0].message,'Capture changed after input');assert.equal(scrolls,1);assert.equal(dispatches,0);
''')

    def test_enter_execute_failure_does_not_gain_navigation_failure_classification(self):
        self.execute(r'''
apexPendingFields[2]='catalog-input';apexPendingFields[6]='enter,1';
apexPendingContext.keyboard_publication=null;apexPendingReply.message='Native Enter refused';
readback();assert.equal(acks.length,1);assert.equal(acks[0].ok,false);
assert.equal('navigation_publication' in acks[0],false);assert.equal(scrolls,1);assert.equal(dispatches,0);
''')



    def test_dynamic_property_order_cannot_masquerade_as_an_owner_scope_change(self):
        self.execute(r"""
const original=apexPendingContext.keyboard_publication.before;
const reordered=Object.fromEntries(Object.entries(original).reverse());
assert.deepEqual(reordered,original);assert.notEqual(ApexEncode(reordered),ApexEncode(original));
assert.equal(ApexCatalogKeyboardScopeEqual(original,reordered),true);
apexPendingContext.keyboard_publication.before=reordered;pending=false;readback();
assert.equal(acks.length,1);assert.equal(acks[0].ok,true);assert.equal(scrolls,1);assert.equal(dispatches,0);
""")

    def test_complete_scope_requires_every_exact_scalar_and_no_added_field(self):
        self.execute(r"""
const original=apexPendingContext.keyboard_publication.before;
for(const name of Object.keys(original)){
 const changed={...original,[name]:typeof original[name]==='string'?original[name]+'x':original[name]+1};
 assert.equal(ApexCatalogKeyboardScopeEqual(original,changed),false,name);
 const missing={...original};delete missing[name];assert.equal(ApexCatalogKeyboardScopeEqual(original,missing),false,name);
}
assert.equal(ApexCatalogKeyboardScopeEqual(original,{...original,unknown:'future'}),false);
assert.equal(ApexCatalogKeyboardScopeEqual(null,original),false);
assert.equal(ApexCatalogKeyboardScopeEqual(original,{...original,session:true}),false);
assert.equal(ApexCatalogKeyboardScopeEqual(original,{...original,session:'3'}),false);
""")

    def test_changed_scope_returns_fresh_diagnostic_after_without_adopting_it(self):
        self.execute(r"""
fresh={...fresh,occultType:8};readback();assert.equal(acks.length,1);const a=acks[0];
assert.equal(a.ok,false);assert.equal(a.navigation_publication.before.shell_kind,4);
assert.equal(a.navigation_publication.after.shell_kind,8);assert.equal(scrolls,1);assert.equal(dispatches,0);
""")

if __name__ == '__main__': unittest.main()
