"""Execute the Main grid lease fragment with adversarial native doubles.

These fixtures exercise Main orchestration, not GFx rendering/performance or
native bytecode equivalence; those remain the native adapter's separate gate.
"""
import re
import shutil
import subprocess
import unittest
from pathlib import Path
from test_cas_panel_geometry import js as panel_javascript

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'Source/CASUi/catalog_grid_transaction_methods.as'


def translated():
    source = SOURCE.read_text(encoding='utf-8')
    methods = []
    for part in source.split('      private function ')[1:]:
        name, tail = part.split('(', 1)
        parameters, tail = tail.split(')', 1)
        body = tail.split('{', 1)[1].rsplit('}', 1)[0]
        parameters = re.sub(r':\s*[\w.]+', '', parameters)
        body = re.sub(r'\b(var\s+\w+)\s*:\s*[\w.]+', r'\1', body)
        body = re.sub(r'\b([\w.]+) is Function\b', r'(typeof \1==="function")', body)
        body = re.sub(r'\b([\w.]+) is int\b', r'Number.isInteger(\1)', body)
        body = body.replace('grid is SelectableRecyclingGridLayout', 'grid instanceof NativeGrid')
        body = body.replace('item is CASCatalogProduct', 'item instanceof CASCatalogProduct')
        body = re.sub(r'\s+as\s+Class\b', '', body)
        body = re.sub(r'catch\((\w+):Error\)', r'catch(\1)', body)
        methods.append('function '+name+'('+parameters+'){'+body+'}\n')
    return '\n'.join(methods)


@unittest.skipUnless(shutil.which('node'), 'Node is required for the lease harness')
class MainGridLeaseTests(unittest.TestCase):
    def test_hidden_or_other_panel_never_polls_or_builds_the_clothing_pool(self):
        self.run_js(r'''
ApexCatalogGridBootstrap();mcClothingPanel.visible=false;
const before=grid.calls.length,clock=frameClock;
for(let n=0;n<200;n++)ApexCatalogGridFrame();
assert.equal(reads.length,0);assert.equal(stateReads,0);assert.equal(gridStateReads,0);assert.equal(grid.steps,0);
assert.equal(grid.calls.length,before);assert.equal(frameClock,clock);
mcClothingPanel.visible=true;mCurrentPanel={visible:true};ApexCatalogGridFrame();
assert.equal(reads.length,0);assert.equal(grid.steps,0);
mCurrentPanel=mcClothingPanel;pump();assert.equal(grid.click(),true);
''')
    def test_bound_alien_uses_verified_renderer_while_ea_shell_stays_vampire(self):
        self.run_js(r'''
nativeSim.occultType=4;assert.equal(mCurrSimInfo.occultType,2);
ApexCatalogGridBootstrap();pump();
assert.equal(apexCatalogGrid.lease.phase,'bound');
assert.equal(apexCatalogGrid.lease.native_kind,2);assert.equal(apexCatalogGrid.lease.shell_kind,4);
assert.equal(grid.click(),true);assert.equal(writes,1);
var previous=apexCatalogGrid.lease;nativeSim.occultType=8;
assert.equal(grid.click(),false);assert.equal(writes,1);assert.equal(previous.active,false);
pump();assert.equal(apexCatalogGrid.lease.shell_kind,8);assert.equal(grid.click(),true);
mCurrSimInfo.occultType=4;assert.equal(grid.click(),false);assert.equal(writes,2);
''')

    def test_native_initializer_preserves_only_its_unstepped_bootstrap(self):
        from test_cas_card_geometry import javascript_function
        semantic = ROOT / 'Source/CASUi/semantic_methods.as'
        workspace = ROOT / 'Source/CASUi/catalog_workspace_methods.as'
        declared = re.findall(r'private var (\w+)\s*:', ''.join(
            path.read_text(encoding='utf-8') for path in (ROOT / 'Source/CASUi').glob('*.as')))
        functions = (javascript_function('ApexInitialize', source=semantic) +
                     javascript_function('ApexDisconnect', 'preserveGridBootstrap=false', source=semantic) +
                     javascript_function('ApexCatalogDispose', 'preserveGridBootstrap=false', source=workspace))
        functions = re.sub(r'catch\((\w+):Error\)', r'catch(\1)', functions)
        stubs = ('ApexMoleculeChooseOccult ApexMoleculeReadSelection ApexPairPanel ApexObserveOwnerFeed '
                 'ApexInvalidateOwnerFeed ApexPresentationNotify ApexCatalogFrame ApexCatalogSlide ApexCatalogSlideEnd '
                 'ApexCatalogOpen ApexCatalogInvalidate ApexCatalogObserveBinding ApexCatalogInitialize ApexTick '
                 'ApexPresentationSchedule ApexPresentationStop ApexMoleculeListen ApexResetSocket '
                 'ApexCatalogTraceDispose ApexLayoutTraceDispose ApexPanelsDispose ApexColumnsDispose '
                 'ApexEquippedDispose ApexCatalogKeyboardDispose ApexCompanionDispose ApexSearchDispose '
                 'UnregisterServiceHandler ApexCatalogClearEffects ApexCardForget').split()
        suffix = ('\nvar ' + ','.join(dict.fromkeys(declared)) + ';\n' +
                  ''.join('function '+name+'(){}\n' for name in stubs) + functions + r'''
function RegisterServiceHandler(){return true;}
function AddMessageListener(name,fn){if(!messages[name])messages[name]=new Set();messages[name].add(fn);}
function RemoveMessageListener(name,fn){if(messages[name])messages[name].delete(fn);}
stage.removeEventListener=function(){};
flash.events.MouseEvent={MOUSE_MOVE:'move',MOUSE_UP:'up'};
flash.events.TimerEvent={TIMER:'timer'};
flash.utils.Timer=class{addEventListener(){}start(){}stop(){}removeEventListener(){}};
ApexCatalogGridBootstrap();var early=apexCatalogGrid;assert.equal(early.enabled,true);
assert.equal(early.frame,0);assert.equal(early.lease.phase,'bootstrap');
ApexInitialize();assert.equal(apexSocketError,'');assert.equal(apexCatalogGrid,early);assert.equal(early.disposed,false);
assert.equal(early.grid.steps,0);assert.equal(apexDisconnected,false);
assert.equal(messages.CASSetSimInfo.has(ApexCatalogGridChanged),true);
ApexDisconnect();assert.equal(apexCatalogGrid,null);assert.equal(early.disposed,true);
ApexCatalogGridBootstrap();var consumed=apexCatalogGrid;consumed.frame=1;
ApexInitialize();assert.equal(apexCatalogGrid,null);assert.equal(consumed.disposed,true);
''')
        self.run_js(suffix)

    def run_js(self, suffix):
        result = subprocess.run(['node'], input=self.harness()+suffix,
            capture_output=True, text=True, encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)

    def harness(self):
        return r'''
const assert=require('node:assert/strict');
function int(n){return Math.trunc(n)||0;}int.MAX_VALUE=2147483647;
var frameClock=1000,flash={events:{Event:{ENTER_FRAME:'frame'}},utils:{getTimer(){return frameClock++;}}};
var added=[],removed=[],messages={},reads=[],writes=0,apexCatalogError='';
var permitAvailable=true,permitCalls=0,stateReads=0,gridStateReads=0,fullInfoReads=0,nativeExchanges=[],apexNativeChannel='77';
// Count full getter dispatches, not NativeSync cache writes or actual harvest work.
var gridStateOverride=null,simRowOverride=null,onOutfitRead=null;
function freshGridWire(){if(nativeModelContext!==expectedModelContext)return 'WAIT';
 return ['GRIDSTATE',nativeSim.simId,nativeSim.householdId,nativeOwner,nativeRendererKind,nativeSim.occultLayer,nativeViewMask,nativeModelMask,nativeGeneration].join('|');}
function ApexNativeExchange(command){nativeExchanges.push(command);if(command==='GRIDPERMIT|1'){permitCalls++;return permitAvailable?'GRIDPERMIT|'+'a'.repeat(32)+'|101|73':'GRIDPERMIT|0';}
 if(command==='GRIDSTATE|77'){gridStateReads++;return gridStateOverride===null?freshGridWire():(typeof gridStateOverride==='function'?gridStateOverride():gridStateOverride);}
 if(command==='STATE|77'){stateReads++;throw Error('Legacy STATE cannot attest native household and both masks');}throw Error('Unexpected native exchange '+command);}

function addEventListener(...args){added.push(args);}function removeEventListener(...args){removed.push(args);}
function AddMessageListener(name,fn){messages[name]=fn;}function RemoveMessageListener(name,fn){if(messages[name]===fn)delete messages[name];}
var apexCatalogSignature='fit-1';
var stage={},apexCatalogGrid=null,apexCatalogDisplayFaults=null,apexOwnerSession=3,apexDisconnected=false,apexBoundSim='101';
var mCurrState=40,mCurrSimInfo={simId:'101',householdId:'909',occultLayer:1,occultType:2,allOccultTypes:127};
var nativeSim={...mCurrSimInfo},nativeSlot={outfit_type:0,outfit_index:0};
var nativeRendererKind=2,nativeViewMask=127,nativeModelMask=127,nativeModelContext={id:'bound-model'},expectedModelContext=nativeModelContext;
var apexFormsNativeState='bound',apexFormsSelectedId='alien/alien',apexFormsNativeGeneration='73',apexFormsDesiredId='';
var nativeOwner=apexFormsSelectedId,nativeGeneration=apexFormsNativeGeneration;
var apexFormsIntent=null,apexFormsNativeIntent=null,apexMoleculeIntent=null,apexPairIntent=null,apexFormsApplying=false;
var apexPendingFields=null,apexReceiving=false;
var CommunicationManager={CallGameService(name,args,nativeArg3){reads.push(name);assert.equal(nativeArg3,true);
    if(name==='CASGetSimInfo'){fullInfoReads++;return {...(simRowOverride===null?nativeSim:simRowOverride)};}if(name==='CasGetCurrSimOutfitSlot'){if(onOutfitRead)onOutfitRead();return nativeSlot===null?null:{...nativeSlot};}throw Error('Unexpected engine call '+name);}};
function ApexOwnerSimRow(raw){if(!raw||typeof raw.simId!=='string'||typeof raw.householdId!=='string')return null;
    return {sim_id:raw.simId,household_id:raw.householdId,occult_type:raw.occultType,all_occult_types:raw.allOccultTypes,occult_layer:raw.occultLayer};}
class NativeGrid{
 constructor(){this.feed={id:1};this.phase='unarmed';this.request=null;this.next=null;this.calls=[];this.steps=0;this.dirty=false;this.onStep=null;}
 GetDataFeed(){return this.feed;}GetCellPadding(){return {mLeft:4,mTop:0};}
 ApexGridNeedsWork(){return this.phase!=='done'||this.dirty;}
 ApexGridBegin(r){assert.equal(r.validate(r.owner),true);assert.equal(typeof r.inputValidate,'function');
   this.calls.push(['begin',r.owner.phase]);
   if(this.request&&this.phase!=='cancelled'&&(this.request.owner!==r.owner||this.ownerGeneration!==r.owner.generation||this.feedAtBegin!==this.feed)){
      this.next=r;this.phase='cancel';return this.ApexGridStatus();}
   if(!this.request||this.phase==='cancelled'){this.request=r;this.ownerGeneration=r.owner.generation;this.feedAtBegin=this.feed;this.phase='acquire';}
   else {if(this.request.bootstrap!==r.bootstrap)this.phase='acquire';this.request=r;}
   return this.ApexGridStatus();}
 ApexGridCancel(reason){this.calls.push(['cancel',reason]);if(reason==='bootstrap-failed'){this.phase='unarmed';this.request=null;this.next=null;}else if(reason==='dispose'){this.phase='cancelled';this.next=null;}else this.phase='cancel';return this.ApexGridStatus();}
 ApexGridStatus(){return {phase:this.phase,active:this.phase!=='unarmed'&&this.phase!=='cancelled',dirty:this.dirty,cancelled:this.phase==='cancelled',error:null,measurement_ready:!!this.measurementReady,natural_width:this.measurementReady?111:0,natural_height:this.measurementReady?148:0,natural_aspect:1};}
 ApexGridStep(maxOps,deadline){this.calls.push(['step',maxOps,deadline]);this.steps++;assert.equal(maxOps,64);assert.ok(deadline>0);
   if(this.onStep)this.onStep();
   if(this.phase==='cancel'){this.phase='cancelled';if(this.next){const r=this.next;this.next=null;this.ApexGridBegin(r);}return this.ApexGridStatus();}
   assert.equal(this.request.validate(this.request.owner),true);
   if(this.request.bootstrap===true){if(!this.measurementReady){this.measurements=(this.measurements||0)+1;this.measuredCell={id:'retained-real-cell'};this.measurementReady=true;}this.phase='measured';return this.ApexGridStatus();}
   if(this.phase==='acquire')this.phase='bind';else if(this.phase==='bind'){this.phase='done';this.dirty=false;}return this.ApexGridStatus();}
 click(){const r=this.request;if(!r||this.phase!=='done'||this.dirty||!r.owner.active||this.ownerGeneration!==r.owner.generation||this.feedAtBegin!==this.feed)return false;
   if(r.inputValidate(r.owner)!==true)return false;writes++;return true;}
}
var grid=new NativeGrid(),mcClothingPanel={stage,visible:true,mcTileList:{mGridLayout:grid,mScrollerView:{width:670,height:950},mSlider:{Value:23}}};
var mCurrentPanel=mcClothingPanel;
var apexCardGeometry={grid,panel:mcClothingPanel},apexCardLayout={columns:12,scale:.46,card_width:51.06,card_height:68.08,gap_x:4,gap_y:4};
var apexPanelGeometry=null,apexCardReflowAttempts=0,mcBodyModPanel=null,mcFaceModPanel=null,
    mcGenericCatalogPanel=null,mcFeaturedFaceLookPanel=null,mcSkinColorPanel=null;
function pump(){for(let i=0;i<8&&grid.phase!=='done';i++)ApexCatalogGridFrame();assert.equal(grid.phase,'done');}
'''+panel_javascript('ApexCatalogPanelKey','panel')+panel_javascript('ApexCardStateFor','grid')+translated()

    def test_default_off_is_inert_and_early_bootstrap_never_draws_or_queries(self):
        self.run_js(r'''
mcClothingPanel.visible=false;
ApexCatalogGridInitialize();assert.equal(grid.calls.length,0);assert.equal(reads.length,0);assert.equal(added.length,0);
ApexCatalogGridFrame();assert.equal(grid.steps,0);
ApexCatalogGridInitialize(true);assert.equal(grid.calls.length,1);assert.equal(grid.calls[0][1],'bootstrap');
assert.equal(reads.length,0);assert.equal(grid.steps,0);assert.equal(mcClothingPanel.visible,false);
const same=apexCatalogGrid;ApexCatalogGridInitialize(true);assert.equal(apexCatalogGrid,same);assert.equal(grid.calls.length,1);
assert.equal(ApexCatalogGridPending(grid),true);assert.equal(grid.click(),false);assert.equal(writes,0);
// Structural bootstrap never steps. A fresh bound owner may measure a real
// cell while fitted geometry is unavailable, but it cannot publish/click.
apexCardLayout=null;mcClothingPanel.visible=true;ApexCatalogGridFrame();assert.equal(grid.steps,1);
assert.equal(grid.request.bootstrap,true);assert.equal(grid.click(),false);
''')

    def test_native_no_argument_bootstrap_precedes_semantic_context_and_late_init_is_idempotent(self):
        self.run_js(r'''
mCurrSimInfo=null;apexOwnerSession=0;apexDisconnected=true;
ApexCatalogGridBootstrap();assert.equal(reads.length,0);assert.equal(grid.steps,0);
assert.equal(grid.calls.length,1);assert.equal(apexCatalogGrid.lease.phase,'bootstrap');
const same=apexCatalogGrid;ApexCatalogGridInitialize();assert.equal(apexCatalogGrid,same);
assert.equal(grid.calls.length,1);assert.equal(reads.length,0);assert.equal(grid.click(),false);
''')

    def test_missing_geometry_measures_one_retained_real_cell_under_fresh_owner(self):
        self.run_js(r'''
apexCardGeometry=null;apexCardLayout=null;ApexCatalogGridBootstrap();
assert.equal(reads.length,0);assert.equal(grid.steps,0);
for(let i=0;i<4;i++)ApexCatalogGridFrame();
assert.equal(grid.phase,'measured');assert.equal(grid.measurements,1);assert.equal(grid.click(),false);
assert.equal(grid.request.owner.phase,'bound');assert.equal(grid.request.bootstrap,true);
const retained=grid.measuredCell;
apexCardGeometry={grid,panel:mcClothingPanel};apexCardLayout={columns:12,scale:.46,card_width:51.06,card_height:68.08,gap_x:4,gap_y:4};
apexCatalogSignature='measured-fit';pump();
assert.equal(grid.request.bootstrap,false);assert.equal(grid.measurements,1);assert.equal(grid.measuredCell,retained);
assert.equal(grid.click(),true);assert.equal(writes,1);
''')

    def test_clean_idle_grid_has_no_engine_reads_clocks_or_begin_step_work(self):
        self.run_js(r'''
ApexCatalogGridBootstrap();pump();const beforeReads=reads.length,beforeCalls=grid.calls.length,beforeClock=frameClock;
for(let i=0;i<30;i++)ApexCatalogGridFrame();
assert.equal(reads.length,beforeReads);assert.equal(grid.calls.length,beforeCalls);assert.equal(frameClock,beforeClock);
apexCatalogSignature='changed-fit';ApexCatalogGridFrame();
assert.equal(reads.length,beforeReads+1);assert.equal(reads[reads.length-1],'CasGetCurrSimOutfitSlot');assert.ok(grid.calls.length>beforeCalls);
grid.dirty=true;const n=reads.length,full=fullInfoReads;ApexCatalogGridFrame();assert.equal(reads.length,n+1);assert.equal(fullInfoReads,full);
''')

    def test_unarmed_new_or_unsupported_cas_keeps_native_controls_unintercepted(self):
        self.run_js(r'''
permitAvailable=false;ApexCatalogGridBootstrap();
assert.equal(permitCalls,1);assert.equal(apexCatalogGrid,null);assert.equal(grid.calls.length,0);
assert.equal(grid.steps,0);assert.equal(added.length,0);assert.equal(reads.length,0);
ApexNativeExchange=()=>{throw Error('native DLL unavailable');};ApexCatalogGridBootstrap();
assert.equal(apexCatalogGrid,null);assert.equal(grid.calls.length,0);
ApexNativeExchange=()=>'GRIDPERMIT|'+'a'.repeat(32)+'|0|73';ApexCatalogGridBootstrap();
assert.equal(apexCatalogGrid,null);assert.equal(grid.calls.length,0);
''')

    def test_same_kind_authoritative_owner_or_generation_change_rejects_old_card(self):
        self.run_js(r'''
ApexCatalogGridBootstrap();pump();const original=apexCatalogGrid.lease;
nativeOwner='ghost/manifested';assert.equal(grid.click(),false);assert.equal(writes,0);assert.equal(original.active,false);
// Physical Sim/kind/layer and every cached Main owner field stayed unchanged.
assert.equal(apexFormsSelectedId,'alien/alien');assert.equal(mCurrSimInfo.occultType,2);
nativeOwner='alien/alien';pump();const current=apexCatalogGrid.lease;
nativeGeneration='74';assert.equal(grid.click(),false);assert.equal(writes,0);assert.equal(current.active,false);
''')

    def test_partial_bootstrap_failure_fast_disarms_without_aborting_ea_initializer(self):
        self.run_js(r'''
const original=grid.ApexGridBegin;grid.ApexGridBegin=function(r){original.call(this,r);throw Error('unsupported future adapter');};
assert.doesNotThrow(()=>ApexCatalogGridBootstrap());assert.equal(grid.steps,0);assert.equal(grid.phase,'unarmed');
assert.equal(apexCatalogGrid.enabled,false);assert.equal(apexCatalogGrid.lease,null);
assert.equal(Object.keys(messages).length,0);assert.match(ApexCatalogGridStatus().error,/unsupported future adapter/);
const calls=grid.calls.length;ApexCatalogGridFrame();ApexCatalogGridFrame();assert.equal(grid.calls.length,calls);
''')

    def test_uncertain_native_step_failure_is_terminal_and_never_replayed_on_next_frames(self):
        self.run_js(r'''
ApexCatalogGridInitialize(true);grid.onStep=function(){throw Error('native draw uncertain');};
ApexCatalogGridFrame();assert.equal(grid.steps,1);assert.match(apexCatalogGrid.error,/native draw uncertain/);
const calls=grid.calls.length;ApexCatalogGridFrame();ApexCatalogGridFrame();assert.equal(grid.steps,1);
assert.equal(grid.calls.length,calls);assert.equal(ApexCatalogGridPrepare(),false);assert.equal(grid.click(),false);assert.equal(writes,0);
''')

    def test_owned_frame_reads_once_and_native_validator_is_pure(self):
        self.run_js(r'''
ApexCatalogGridInitialize(true);ApexCatalogGridFrame();
assert.deepEqual(reads,['CASGetSimInfo','CasGetCurrSimOutfitSlot']);
const lease=apexCatalogGrid.lease;assert.equal(lease.phase,'bound');assert.equal(lease.frame_validated,false);
const before=reads.length;assert.equal(ApexCatalogGridValidate(lease),false);assert.equal(reads.length,before);
pump();assert.equal(ApexCatalogGridPending(grid),false);assert.equal(grid.click(),true);assert.equal(writes,1);
assert.deepEqual(reads.slice(-2),['CASGetSimInfo','CasGetCurrSimOutfitSlot']);
''')

    def test_between_frame_other_sim_or_household_cannot_receive_old_card(self):
        for change in ("nativeSim.simId='202';", "nativeSim.householdId='808';"):
            with self.subTest(change=change):
                self.run_js(r'''
ApexCatalogGridInitialize(true);pump();const before=reads.length;
'''+change+r'''
assert.equal(grid.click(),false);assert.equal(writes,0);assert.equal(apexCatalogGrid.lease.active,false);
assert.equal(reads.length,before+2);assert.equal(ApexCatalogGridPending(grid),true);
''')

    def test_between_frame_outfit_change_cannot_receive_old_card_and_fresh_frame_recovers(self):
        self.run_js(r'''
ApexCatalogGridInitialize(true);pump();nativeSlot.outfit_type=3;nativeSlot.outfit_index=2;
assert.equal(grid.click(),false);assert.equal(writes,0);assert.equal(apexCatalogGrid.lease.active,false);
pump();assert.equal(apexCatalogGrid.lease.outfit_type,3);assert.equal(apexCatalogGrid.lease.outfit_index,2);
assert.equal(grid.click(),true);assert.equal(writes,1);
''')

    def test_pending_form_or_member_intent_blocks_input_and_step_but_metadata_control_does_not(self):
        for name in ('apexFormsIntent','apexFormsNativeIntent','apexMoleculeIntent','apexPairIntent'):
            with self.subTest(intent=name):
                self.run_js(r'''
ApexCatalogGridInitialize(true);pump();const before=reads.length;
'''+name+r'''={requested:'other'};
assert.equal(grid.click(),false);assert.equal(reads.length,before);assert.equal(writes,0);
const steps=grid.steps;ApexCatalogGridFrame();assert.equal(grid.steps,steps);
''')
        self.run_js(r'''
ApexCatalogGridInitialize(true);apexPendingFields=['catalog-slider'];apexReceiving=true;pump();
assert.equal(grid.click(),true);assert.equal(writes,1);
''')

    def test_notifications_and_named_owner_change_invalidate_before_any_read_or_write(self):
        self.run_js(r'''
ApexCatalogGridInitialize(true);pump();const old=apexCatalogGrid.lease,before=reads.length;
messages.CASPlannedOutfitTypeChanged({});assert.equal(old.active,false);assert.equal(reads.length,before);
assert.equal(grid.click(),false);pump();const afterFreshRecovery=reads.length;apexFormsSelectedId='vampire/dark';
assert.equal(grid.click(),false);assert.equal(writes,0);assert.equal(reads.length,afterFreshRecovery);
''')

    def test_live_feed_replacement_blocks_old_cells_and_restarts_exact_new_feed(self):
        self.run_js(r'''
ApexCatalogGridInitialize(true);pump();const old=apexCatalogGrid.lease;grid.feed={id:2};
assert.equal(grid.click(),false);ApexCatalogGridFrame();pump();
assert.equal(old.active,false);assert.equal(apexCatalogGrid.lease.feed,grid.feed);
assert.equal(grid.click(),true);assert.equal(writes,1);
''')

    def test_stage_and_panel_reference_replacement_cannot_strand_old_lease(self):
        self.run_js(r'''
ApexCatalogGridInitialize(true);pump();const old=apexCatalogGrid.lease;
stage={};mcClothingPanel.stage=stage;ApexCatalogGridFrame();pump();
assert.equal(old.active,false);assert.equal(apexCatalogGrid.lease.stage,stage);
const second=apexCatalogGrid.lease;mcClothingPanel={...mcClothingPanel};
assert.equal(grid.click(),false);mCurrentPanel=mcClothingPanel;ApexCatalogGridFrame();
assert.equal(grid.click(),false); // The replaced widget requires its own fitted geometry.
apexCardGeometry={grid,panel:mcClothingPanel};pump();
assert.equal(second.active,false);assert.equal(apexCatalogGrid.lease.panel,mcClothingPanel);
assert.equal(grid.click(),true);assert.equal(writes,1);assert.equal(ApexCatalogGridOwns(grid),true);
''')

    def test_reentrant_frame_does_not_double_step_and_dispose_abandons_without_bulk_reset(self):
        self.run_js(r'''
ApexCatalogGridInitialize(true);grid.onStep=function(){const before=grid.steps;ApexCatalogGridFrame();assert.equal(grid.steps,before);};
ApexCatalogGridFrame();assert.equal(grid.steps,1);grid.onStep=null;pump();
const before=grid.steps;grid.onStep=function(){ApexCatalogGridDispose();};
// Native dirty change starts another bounded pass; disposal happens within it.
grid.phase='acquire';ApexCatalogGridFrame();assert.equal(apexCatalogGrid,null);assert.equal(grid.steps,before+1);
assert.equal(grid.phase,'cancelled');assert.equal(grid.click(),false);assert.equal(writes,0);
assert.equal(Object.keys(messages).length,0);assert.equal(removed.length,1);
''')

    def test_status_serializes_no_opaque_lease_and_input_read_error_refuses_write(self):
        self.run_js(r'''
ApexCatalogGridInitialize(true);pump();const status=ApexCatalogGridStatus();assert.equal(status.appearance_written,false);
assert.equal(status.context.owner,'alien/alien');assert.ok(JSON.stringify(status));
for(const name of ['root','stage','panel','grid','feed','validate','inputValidate'])assert.equal(name in status.context,false);
CommunicationManager.CallGameService=function(){throw Error('native read refused');};
assert.equal(grid.click(),false);assert.equal(writes,0);assert.equal(apexCatalogGrid.lease.active,false);
assert.match(apexCatalogGrid.error,/native read refused/);
''')


if __name__ == '__main__':
    unittest.main()
