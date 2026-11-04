"""Execute the actual toolbar capture bodies before a retained donor capture hook."""
from pathlib import Path
import re
import shutil
import subprocess
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'Source/CASUi/panel_input_methods.as'


def javascript_function(name, parameters):
    part = SOURCE.read_text(encoding='utf-8').split('private function ' + name + '(', 1)[1]
    part = re.split(r'\n      private function ', part, maxsplit=1)[0]
    body = part.split('{', 1)[1].rsplit('}', 1)[0]
    body = re.sub(r'\b(var\s+\w+)\s*:\s*[\w.]+', r'\1', body)
    body = re.sub(r'\s+as\s+flash\.[\w.]+', '', body)
    return 'function ' + name + '(' + parameters + '){' + body + '}\n'


@unittest.skipUnless(shutil.which('node'), 'Node is required for the AS input harness')
class PanelInputTests(unittest.TestCase):
    def run_case(self, case):
        harness = '''
const assert=require('node:assert/strict');
class Sprite{
    constructor(name=''){this.name=name;this.parent=null;this.visible=true;this.children={};}
    add(child){this.children[child.name]=child;child.parent=this;return child;}
    getChildByName(name){return this.children[name]||null;}
    get stage(){let node=this;while(node.parent)node=node.parent;return node===stage?stage:null;}
}
var flash={display:{Sprite},events:{MouseEvent:{MOUSE_DOWN:'mouseDown',CLICK:'click'}}};
var stage,owner,root,grip,body,tab,card,apexPanels,log,actions,dragStarts;
function reset(){
    log=[];actions=[];dragStarts=0;stage=new Sprite('stage');owner=stage.add(new Sprite('owner'));
    root=owner.add(new Sprite('drawer'));body=root.add(new Sprite('body'));tab=root.add(new Sprite('tab'));
    card=body.add(new Sprite('card'));grip=root.add(new Sprite('ApexPanelMoveAndScale'));
    for(const name of ['move','smaller','larger','lock','reset'])grip.add(new Sprite('apexPanel_'+name)).add(new Sprite('caption'));
    apexPanels={stage,root,grip,host:{dccHistoryRuntimeDrawer:[root]},scale:1,locked:false,x:.2,y:.4,drag:null};
}
function ApexPanelsDragStart(){dragStarts++;if(!apexPanels.locked){apexPanels.drag={};log.push('drag');}}
function ApexPanelsDragEnd(){apexPanels.drag=null;actions.push('drag-end');}
function ApexPanelsScale(value){actions.push('scale:'+value);apexPanels.scale=value;}
function ApexPanelsApply(){actions.push('apply');}
function ApexPanelsChanged(){actions.push('changed');}
''' + javascript_function('ApexPanelsCapture', 'event') + javascript_function('ApexPanelsAction', 'name') + '''
function dispatch(target,type='mouseDown',sender=stage){
    const event={target,type,currentTarget:sender,stopped:false,prevented:false,
        stopImmediatePropagation(){this.stopped=true;log.push('owned-stop');},
        preventDefault(){this.prevented=true;}};
    // The real stage capture phase precedes the retained drawer capture phase.
    ApexPanelsCapture.call(owner,event);
    if(!event.stopped){log.push('donor-capture');log.push('native-target');}
    // Mirrors the existing target click callback delegated to the shared action.
    if(!event.stopped && type==='click' && target.parent===grip)ApexPanelsAction(target.name);
    return event;
}
reset();
'''
        result = subprocess.run(['node', '-e', harness + case], capture_output=True,
                                text=True, encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_button_down_isolated_and_click_runs_exactly_one_action_before_donor(self):
        self.run_case('''
const button=grip.getChildByName('apexPanel_larger');
let event=dispatch(button);assert.equal(event.stopped,true);assert.equal(event.prevented,true);assert.deepEqual(actions,[]);
event=dispatch(button,'click');assert.equal(apexPanels.scale,1.05);assert.deepEqual(actions,['scale:1.05']);
assert.ok(!log.includes('donor-capture'));assert.ok(!log.includes('native-target'));
reset();dispatch(grip.getChildByName('apexPanel_smaller').getChildByName('caption'),'click');
assert.deepEqual(actions,['scale:0.95']);assert.ok(!log.includes('donor-capture'));
''')

    def test_move_down_isolated_for_unlocked_and_locked_panels_without_click_action(self):
        self.run_case('''
let target=grip.getChildByName('apexPanel_move');dispatch(target);
assert.equal(dragStarts,1);assert.ok(apexPanels.drag);assert.deepEqual(log,['owned-stop','drag']);
dispatch(target,'click');assert.deepEqual(actions,[]);assert.ok(!log.includes('donor-capture'));
reset();apexPanels.locked=true;target=grip.getChildByName('apexPanel_move');
const event=dispatch(target);assert.equal(event.stopped,true);assert.equal(dragStarts,1);assert.equal(apexPanels.drag,null);
assert.deepEqual(log,['owned-stop']);
''')

    def test_native_body_tabs_cards_and_unowned_or_stale_targets_pass_unchanged(self):
        self.run_case('''
for(const change of [()=>body,()=>tab,()=>card,()=>grip,
    ()=>body.add(new Sprite('apexPanel_larger')),
    ()=>grip.add(new Sprite('not-an-owned-control')),
    ()=>{const old=root.add(new Sprite('oldGrip'));return old.add(new Sprite('apexPanel_reset'));}]){
    reset();const target=change(),event=dispatch(target,'click');
    assert.equal(event.stopped,false);assert.equal(event.prevented,false);assert.deepEqual(actions,[]);
    assert.deepEqual(log,['donor-capture','native-target']);
}
''')

    def test_hidden_detached_replaced_and_wrong_stage_controls_are_not_captured(self):
        self.run_case('''
for(const change of [()=>{root.visible=false;},()=>{grip.visible=false;},()=>{body.visible=false;},
    ()=>{owner.visible=false;},()=>{root.parent=null;},()=>{grip.parent=body;},
    ()=>{apexPanels.host.dccHistoryRuntimeDrawer=[new Sprite('replacement')];},
    ()=>{apexPanels.stage=new Sprite('old-stage');}]){
    reset();const target=grip.getChildByName('apexPanel_larger');change();const event=dispatch(target);
    assert.equal(event.stopped,false);assert.equal(event.prevented,false);assert.equal(dragStarts,0);
    assert.deepEqual(actions,[]);assert.deepEqual(log,['donor-capture','native-target']);
}
reset();let event=dispatch(grip.getChildByName('apexPanel_move'),'mouseDown',new Sprite('other-sender'));
assert.equal(event.stopped,false);assert.equal(dragStarts,0);
reset();event=dispatch(grip.getChildByName('apexPanel_move'),'mouseUp');assert.equal(event.stopped,false);
''')

    def test_shared_action_retains_lock_reset_and_unknown_name_semantics(self):
        self.run_case('''
apexPanels.drag={};dispatch(grip.getChildByName('apexPanel_lock'),'click');
assert.equal(apexPanels.locked,true);assert.equal(apexPanels.drag,null);assert.deepEqual(actions,['drag-end','apply','changed']);
actions=[];dispatch(grip.getChildByName('apexPanel_reset'),'click');
assert.equal(apexPanels.x,-1);assert.equal(apexPanels.y,-1);assert.equal(apexPanels.scale,1);assert.equal(apexPanels.locked,false);
assert.deepEqual(actions,['apply','changed']);actions=[];ApexPanelsAction('unknown');assert.deepEqual(actions,[]);
''')


if __name__ == '__main__':
    unittest.main()
