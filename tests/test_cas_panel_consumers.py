"""Exercise actual asynchronous leases around the retained native consumers."""
from pathlib import Path
import shutil
import subprocess
import unittest
from test_cas_panel_scheduling import javascript_body

SOURCE = Path(__file__).resolve().parents[1] / 'Source/CASUi/panel_consumer_methods.as'


@unittest.skipUnless(shutil.which('node'), 'Node required')
class ConsumerTests(unittest.TestCase):
    def harness(self):
        return '''
const assert=require('node:assert/strict');
var stage={},context='sim-123/alien/outfit-4',apexFormsDesiredId='',apexFormsApplying=false,apexFormsNativeState='bound';
var mCurrSimInfo={simId:'123'},drawer={0:{stage,visible:true,parent:stage},40:{visible:true},108:{}},saved=0,planned=0,stops=0;
var dialog={dialog:{stage,visible:true,parent:drawer[0]},input:{text:'New look',stage},busy:false,sourceId:'123',error:{text:''}};
var helpers={SavedOutfitNames:{SavedManageDialogState:()=>dialog},SavedManage:{IsRenaming:()=>false}};
var apexPanels={helpers,owner:'owner-123-alien',consumer:null,consumer_running:null,key:'old',requested:false,revision:0,job:null,stamp_ticket:'',message:''};
function getDefinitionByName(){throw Error('unexpected class discovery');}
function ApexPanelsDrawer(){return drawer;}function ApexPanelsContext(){return context;}
function ApexPanelRefreshGate(){''' + javascript_body('ApexPanelRefreshGate') + '''}
function ApexPanelConsumer(value){''' + javascript_body('ApexPanelConsumer', SOURCE) + '''}
function ApexPanelPersistGate(event){''' + javascript_body('ApexPanelPersistGate', SOURCE) + '''}
function ApexPanelsConsumerCancel(request,message){''' + javascript_body('ApexPanelsConsumerCancel', SOURCE) + '''}
var flash={events:{MouseEvent:function(type){this.type=type;this.stopImmediatePropagation=()=>stops++;}}};flash.events.MouseEvent.CLICK='click';
flash.utils={getTimer:()=>0};
function ApexPanelsConsume(drawer,context,check_only=false){''' + javascript_body('ApexPanelsConsume', SOURCE) + '''}
function Save(e){if(ApexPanelConsumer({kind:'save',callback:Save,event:e}))return;
    assert.equal(apexPanels.consumer,null);var revision=apexPanels.revision;
    ApexPanelRefreshGate();assert.equal(apexPanels.revision,revision);assert.equal(apexPanels.requested,false);
    assert.equal(ApexPanelPersistGate({currentTarget:drawer[108]}),false);saved++;}
var target={stage,visible:true,parent:drawer[0],dispatchEvent:function(e){e.currentTarget=this;Remove(e);}};
function Remove(e){if(ApexPanelConsumer({kind:'remove',callback:Remove,event:e}))return;planned++;ApexPanelRefreshGate();}
function finish(){apexPanels.job=null;apexPanels.requested=false;apexPanels.stamp_ticket='';apexPanels.key=context+'|fresh-hash';
    if(apexPanels.consumer&&apexPanels.consumer.stamp==='')apexPanels.consumer.stamp='fresh-hash';}
'''

    def run_js(self, source):
        result = subprocess.run(['node', '-e', self.harness() + source], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_save_waits_for_full_view_then_invokes_original_once_without_nested_refresh(self):
        self.run_js('''
Save(null);assert.equal(saved,0);assert.equal(apexPanels.consumer.kind,'save');assert.equal(apexPanels.requested,true);
apexPanels.job={group:1};ApexPanelsConsume(drawer,context);assert.equal(saved,0);
finish();ApexPanelsConsume(drawer,context);assert.equal(saved,1);assert.equal(apexPanels.consumer_running,null);
ApexPanelsConsume(drawer,context);assert.equal(saved,1);assert.equal(apexPanels.consumer,null);
''')

    def test_each_changed_identity_dialog_or_name_cancels_without_writing(self):
        for change in ["apexPanels.owner='different-form'", "context='sim-123/vampire/outfit-4'",
                       "context='sim-123/alien/outfit-5'", "dialog.input.text='changed'",
                       "dialog.input.stage=null", "dialog.dialog={}", "dialog.sourceId='456'"]:
            with self.subTest(change=change):
                self.run_js("Save(null);" + change + ";finish();ApexPanelsConsume(drawer,context);assert.equal(saved,0);assert.equal(apexPanels.consumer,null);")

    def test_remove_dispatches_exact_target_only_after_all_groups_complete(self):
        self.run_js('''
Remove({currentTarget:target,stopImmediatePropagation:()=>stops++});assert.equal(planned,0);assert.equal(stops,1);
apexPanels.job={group:3};ApexPanelsConsume(drawer,context);assert.equal(planned,0);
finish();ApexPanelsConsume(drawer,context);assert.equal(planned,1);assert.equal(apexPanels.requested,false);
ApexPanelsConsume(drawer,context);assert.equal(planned,1);
''')

    def test_closed_hidden_dialog_cancels_before_worker_or_tab_can_finish(self):
        self.run_js('''
Save(null);assert.equal(dialog.error.text,'Updating the current outfit…');
apexPanels.job={group:1};dialog.dialog.parent={visible:false,parent:stage};
ApexPanelsConsume(drawer,'',true);assert.equal(saved,0);assert.equal(apexPanels.consumer,null);
assert.match(dialog.error.text,/panel closed/);
''')

    def test_changed_appearance_stamp_is_not_replaced_by_later_fresh_data(self):
        self.run_js('''
Save(null);apexPanels.consumer.stamp='the-look-at-first-capture';finish();ApexPanelsConsume(drawer,context);
assert.equal(saved,0);assert.equal(apexPanels.consumer,null);assert.match(dialog.error.text,/appearance changed/);
''')

    def test_first_fresh_capture_freezes_intent_and_mid_refresh_edit_cancels(self):
        self.run_js('''
drawer[0].getChildByName=()=>({visible:true});drawer[40]={visible:false};
for(const n of ['OutfitSwatchRoute','HairSwatches','OutfitRemoval','OutfitCategory','CurrentRemove'])helpers[n]={};
apexPanels.job_metrics=null;apexPanels.metrics={};var hash='first-fresh-hash';
function ApexPanelsStamp(){return hash;}
function int(v){return Math.trunc(v);}
function ApexPanelsWork(drawer,context){''' + javascript_body('ApexPanelsWork') + '''}
Save(null);ApexPanelsWork(drawer,context);assert.equal(apexPanels.consumer.stamp,'first-fresh-hash');
apexPanels.job.phase='verify';hash='appearance-edited-during-refresh';ApexPanelsWork(drawer,context);
assert.equal(apexPanels.consumer,null);assert.equal(apexPanels.job,null);assert.equal(saved,0);
assert.match(dialog.error.text,/appearance changed/);
''')

    def test_destroyed_native_dialog_accessor_cannot_leave_an_intent_pending(self):
        self.run_js('''
Save(null);helpers.SavedOutfitNames.SavedManageDialogState=()=>{throw Error('dialog retired');};
ApexPanelsConsume(drawer,'',true);assert.equal(apexPanels.consumer,null);assert.equal(saved,0);
assert.equal(apexPanels.message,'dialog retired');
''')

    def test_other_sim_or_detached_panel_cannot_queue_an_action(self):
        self.run_js('''
dialog.sourceId='another-sim';Save(null);assert.equal(apexPanels.consumer,null);assert.equal(saved,0);
assert.match(dialog.error.text,/different Sim/);
dialog.sourceId='123';dialog.dialog.parent=stage;Save(null);assert.equal(apexPanels.consumer,null);assert.equal(saved,0);
assert.match(dialog.error.text,/different CAS panel/);
target.parent=stage;Remove({currentTarget:target,stopImmediatePropagation:()=>stops++});
assert.equal(apexPanels.consumer,null);assert.equal(planned,0);
''')

    def test_remove_all_outside_content_mask_cancels_when_its_tab_closes(self):
        self.run_js('''
Remove({currentTarget:target,stopImmediatePropagation:()=>stops++});assert.ok(apexPanels.consumer);
drawer[40].visible=false;ApexPanelsConsume(drawer,'',true);assert.equal(apexPanels.consumer,null);assert.equal(planned,0);
''')

    def test_stale_first_capture_does_not_recapture_and_execute_a_later_look(self):
        self.run_js('''
var apexNativeChannel='native-channel',apexFormsSelectedId='alien';
function ApexNativeExchange(){return 'STAMPSTALE|7';}
function ApexPanelsStamp(context){''' + javascript_body('ApexPanelsStamp') + '''}
Save(null);apexPanels.stamp_ticket='7';apexPanels.stamp_max_ms=0;apexPanels.stale=0;
assert.equal(ApexPanelsStamp(context),'');assert.equal(apexPanels.consumer,null);assert.equal(saved,0);
assert.match(dialog.error.text,/captured appearance became stale/);
''')

    def test_pending_intent_is_not_overwritten_and_standalone_save_sinks_are_blocked(self):
        self.run_js('''
Save(null);var first=apexPanels.consumer;
Remove({currentTarget:target,stopImmediatePropagation:()=>stops++});assert.equal(apexPanels.consumer,first);
assert.equal(ApexPanelPersistGate({currentTarget:drawer[108],stopImmediatePropagation:()=>stops++}),true);
assert.equal(ApexPanelPersistGate({currentTarget:{}}),false);assert.equal(saved,0);assert.equal(planned,0);
''')

    def test_rename_empty_input_and_unavailable_bridge_keep_original_fallback(self):
        self.run_js('''
helpers.SavedManage.IsRenaming=()=>true;assert.equal(ApexPanelConsumer({kind:'save',callback:Save,event:null}),false);
helpers.SavedManage.IsRenaming=()=>false;dialog.input.text='   ';assert.equal(ApexPanelConsumer({kind:'save',callback:Save,event:null}),false);
assert.equal(apexPanels.consumer,null);apexPanels=null;assert.equal(ApexPanelConsumer({}),false);assert.equal(ApexPanelPersistGate({}),false);
''')


if __name__ == '__main__':
    unittest.main()
