"""Execute the actual proposed AS bodies; no game/profile/process access."""
from pathlib import Path
import re,sys,subprocess,unittest,os
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'tools/dbpf_build.py').is_file())
HERE=Path(os.environ.get('APEX_CATALOG_AUTHORITY_SOURCE_ROOT',ROOT))
FIXTURE=Path(os.environ['APEX_CATALOG_AUTHORITY_FIXTURE_ROOT']) if 'APEX_CATALOG_AUTHORITY_FIXTURE_ROOT' in os.environ else None
sys.path[:0]=[str(HERE/'tools'),str(ROOT/'tools')]
import cas_catalog_authority_stage as stage,cas_grid_pool as pool

def translate(raw):
    raw=re.sub(r'(?:private|public) function (\w+)\(([^)]*)\)\s*:\s*[\w.]+',
               lambda m:'function '+m[1]+'('+re.sub(r':\s*[\w.]+','',m[2])+')',raw)
    raw=re.sub(r'\bvar (\w+):[\w.]+',r'var \1',raw)
    raw=re.sub(r'catch\((\w+):[\w.]+\)',r'catch(\1)',raw)
    raw=re.sub(r'for each\(var (\w+) in ([^)]*)\)',r'for(var \1 of Object.values(\2))',raw)
    raw=re.sub(r'([\w.]+) is (String|Boolean|Function|int)',lambda m:'is'+m[2]+'('+m[1]+')',raw)
    raw=re.sub(r'\s+as [\w.]+','',raw).replace('grid is SelectableRecyclingGridLayout','grid instanceof SelectableRecyclingGridLayout')
    return raw

BOOT=r'''
const assert=require('assert/strict'),vm=require('vm');
const events=[];const fail=(name)=>()=>{throw Error('forbidden '+name)};
class SelectableRecyclingGridLayout {}
const c={console,Math,Number,String,Boolean,Object,Array,Error,isFinite,
  isString:v=>typeof v==='string',isBoolean:v=>typeof v==='boolean',isFunction:v=>typeof v==='function',isint:Number.isInteger,
  int:Object.assign(v=>v|0,{MAX_VALUE:2147483647}),
  SelectableRecyclingGridLayout,flash:{utils:{getQualifiedClassName:g=>g.qname,getTimer:()=>0},events:{Event:{ENTER_FRAME:'frame'}}}};
vm.createContext(c);vm.runInContext(SOURCE,c);
const root=vm.runInContext('this',c);for(const name of Object.keys(c))if(name.startsWith('Apex'))c[name]=c[name].bind(root);
const clone=x=>JSON.parse(JSON.stringify(x));
function setup(){
 events.length=0;c.stage={};c.apexDisconnected=false;c.apexOwnerSession=3;c.apexFormsSelectedId='native/1';
 c.apexFormsNativeGeneration='42';c.apexFormsNativeState='bound';c.apexFormsDesiredId='';c.apexBoundSim='11';
 c.apexFormsIntent=null;c.apexFormsNativeIntent=null;c.apexMoleculeIntent=null;c.apexPairIntent=null;c.apexFormsApplying=false;
 c.mCurrState=101;c.mCurrSimInfo={simId:'11',householdId:'22',occultLayer:0,occultType:1,allOccultTypes:127};
 const view={stage:c.stage,visible:true},feed={};function Cell(){}
 const g=Object.assign(new SelectableRecyclingGridLayout(),{qname:'olympus.layout::SelectableRecyclingGridLayout',GetCellView:Cell,GetDataFeed:()=>feed,
  ApexGridAuthorityStatus:()=>g.terminal??null,ApexGridCancel:fail('cancel'),ApexGridStatus:fail('status'),
  ApexGridNeedsWork:()=>false,ApexGridStep:fail('step'),ApexGridBeginFrame:fail('frame begin')});
 const p={key:'clothing',stage:c.stage,visible:true,mcPanelBackground:{width:500},mcTileList:{mGridLayout:g,GetGridView:()=>view}};
 c.mCurrentPanel=p;c.mcClothingPanel=p;c.apexCatalogDisplayFaults=null;
 c.apexCardGeometry=null;c.apexCardLayout=null;c.apexPanelGeometry=null;c.apexCatalogEffects=null;
 c.ApexCatalogSlide=()=>{};c.ApexCatalogSlideEnd=()=>{};
 c.apexCatalogGrid={enabled:true,disposed:false,running:false,input_reading:false,error:'',generation:8,frame:0,grid:g,lease:null,last:null};
 const s=c.apexCatalogGrid;
 const scope={sim_id:'11',household_id:'22',owner:'native/1',session:3,layer:0,native_kind:1,shell_kind:4,native_mask:127,
  native_generation:'42',outfit_type:0,outfit_index:0,state:101};
 const lease={...scope,root:vm.runInContext('this',c),active:true,generation:8,grid:g,panel:p,view,feed,stage:c.stage,
  cell_type:Cell,panel_kind:'clothing',phase:'bound',frame_validated:true};s.lease=lease;
 c.ApexCatalogPanelKey=p=>p?.key??'';c.ApexCatalogGridProductPanel=p=>p===c.mCurrentPanel?'clothing':'';
 c.ApexCatalogPanelVisible=p=>p===c.mCurrentPanel&&p.visible===true;
 c.ApexCatalogGridObserve=()=>{events.push('observe');return clone(c.observed??scope)};
 c.ApexCatalogGridRequest=lease=>({owner:lease,bootstrap:true,width:1,height:1,validate:c.ApexCatalogGridValidate});
 c.ApexCatalogFrameStatusAvailable=()=>true;c.ApexCardStateFor=()=>null;
 c.ApexCatalogGridFrameObserve=c.ApexCatalogGridObserve;
 c.ApexCatalogAuthorityRemember(lease);
 const terminal={protocol:1,phase:'authority-lost',authority_lost:true,terminal_blocked:true,error:null,reason:'callback replaced native grid state',
  generation:7,revision:4,lease_released:false,input_released:true,release_refused:'foreign lease',lifecycle_changed:true,scope:clone(scope)};
 g.ApexGridBegin=request=>{events.push('begin');assert.equal(request.owner.phase,'bound');assert.equal(request.bootstrap,true);
  assert.equal(request.validate(request.owner),true);if(g.onBegin)g.onBegin(request);else g.terminal=null;return {phase:'measure',error:null};};
 return {g,p,s,scope,lease,terminal,feed,view};
}
'''

class MainAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=(HERE/'Source/CASUi/catalog_authority_consumer_methods.as').read_text()+'\n'+(HERE/'Source/CASUi/catalog_authority_methods.as').read_text()
        for name,file in [('ApexCatalogGridLeaseCurrent','catalog_workflow_methods.as'),('ApexCatalogGridValidate','catalog_grid_transaction_methods.as'),('ApexCatalogGridMatches','catalog_grid_transaction_methods.as'),('ApexCatalogDispose','catalog_workspace_methods.as')]:
            raw=(ROOT/'Source/CASUi'/file).read_text();a,b=pool.method_extent(raw,name);cls.source+='\n'+raw[a:b]
        names=stage.ADDED+stage.REPLACED+('ApexCatalogGridLeaseCurrent','ApexCatalogGridValidate','ApexCatalogGridMatches','ApexCatalogDispose')
        cls.js='\n'.join(translate(cls.source[s:e]) for n in names for s,e in [pool.method_extent(cls.source,n)])
    def case(self,body):
        import json
        script=BOOT.replace('SOURCE',json.dumps(self.js))+'\n'+body
        p=subprocess.run(['node','-'],input=script,text=True,capture_output=True,timeout=15)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
    def test_healthy_and_foreign_class_keep_existing_path(self):
        self.case("const x=setup();assert.equal(c.ApexCatalogAuthorityHold(x.g),false);x.g.qname='custom::Grid';x.g.ApexGridAuthorityStatus=fail('foreign getter');assert.equal(c.ApexCatalogAuthorityHold(x.g),false);assert.deepEqual(events,[]);")
    def test_terminal_is_detached_and_release_refusal_is_not_a_generic_error(self):
        self.case("const x=setup();x.g.terminal=x.terminal;assert.equal(c.ApexCatalogAuthorityHold(x.g),true);const h=c.ApexCatalogAuthorityHeld(x.g);assert.equal(h.receipt.verified,true);assert.equal(h.receipt.lease_released,false);x.terminal.scope.owner='foreign';assert.equal(h.receipt.scope.owner,'native/1');assert.equal(x.s.error,'');assert.equal(x.lease.active,true);assert.equal(x.lease.generation,8);")
    def test_inflight_terminal_survives_complete_provider_state_replacement(self):
        self.case("const x=setup();x.s.last=x.terminal;x.g.ApexGridAuthorityStatus=()=>null;assert.equal(c.ApexCatalogAuthorityHold(x.g),true);assert.equal(c.ApexCatalogGridPending(x.g),true);c.ApexCatalogGridInvalidate('notification');assert.equal(x.s.generation,8);assert.equal(x.lease.active,true);")
    def test_all_unchanged_frame_geometry_input_and_status_lanes_quiesce(self):
        self.case("const x=setup();x.g.terminal=x.terminal;assert.equal(c.ApexCatalogAuthorityHold(x.g),true);for(let i=0;i<5;i++){c.ApexCatalogGridFrame();assert.equal(c.ApexCatalogGridPrepare(),false);assert.equal(c.ApexCardApply(x.p,x.g),500);assert.equal(c.ApexCardIncrementalApply(x.p,x.g),500);assert.equal(c.ApexCatalogGridInput(x.lease),false);assert.equal(c.ApexCatalogGridPending(x.g),true);const status=c.ApexCatalogGridStatus();assert.equal(status.native.phase,'authority-lost');assert.equal(status.authority.verified,true);}assert.deepEqual(events,[]);assert.equal(x.s.generation,8);assert.equal(x.lease.frame_validated,true);")
    def test_ui_generation_size_and_idle_cannot_recover(self):
        self.case("const x=setup();x.g.terminal=x.terminal;c.ApexCatalogAuthorityHold(x.g);x.s.generation++;x.p.mcPanelBackground.width=999;x.s.running=true;assert.equal(c.ApexCatalogAuthorityRecover(x.p,x.g),false);assert.deepEqual(events,[]);")
    def test_notification_is_only_a_probe_and_same_scope_does_not_begin(self):
        self.case("const x=setup();x.g.terminal=x.terminal;c.ApexCatalogAuthorityHold(x.g);c.ApexCatalogGridChanged({});x.s.running=true;assert.equal(c.ApexCatalogAuthorityRecover(x.p,x.g),false);assert.deepEqual(events,['observe']);assert.equal(c.ApexCatalogAuthorityRecover(x.p,x.g),false);assert.deepEqual(events,['observe']);assert.equal(x.s.generation,8);")
    def test_changed_named_owner_or_generation_requires_fresh_bound_validation(self):
        self.case("for(const change of ['owner','generation','outfit','menu']){const x=setup();x.g.terminal=x.terminal;c.ApexCatalogAuthorityHold(x.g);c.observed=clone(x.scope);if(change==='owner'){c.apexFormsSelectedId='named/custom';c.observed.owner='named/custom';}if(change==='generation'){c.apexFormsNativeGeneration='43';c.observed.native_generation='43';}if(change==='outfit'){c.observed.outfit_index=1;c.ApexCatalogGridChanged({});}if(change==='menu'){c.mCurrState=102;c.observed.state=102;}x.s.running=true;assert.equal(c.ApexCatalogAuthorityRecover(x.p,x.g),true,change);assert.deepEqual(events,['observe','begin','observe']);assert.equal(c.ApexCatalogAuthorityHeld(x.g),null);assert.equal(x.lease.active,true);assert.equal(x.lease.generation,8);delete c.observed;}")
    def test_genuine_feed_replacement_can_recover_without_appearance_change(self):
        self.case("const x=setup();x.g.terminal=x.terminal;c.ApexCatalogAuthorityHold(x.g);const feed={};x.g.GetDataFeed=()=>feed;x.s.running=true;assert.equal(c.ApexCatalogAuthorityRecover(x.p,x.g),true);assert.equal(x.s.lease.feed,feed);assert.deepEqual(events,['observe','begin','observe']);")
    def test_failed_same_tuple_never_replays_begin_even_after_notification(self):
        self.case("const x=setup();x.g.terminal=x.terminal;c.ApexCatalogAuthorityHold(x.g);c.apexFormsNativeGeneration='43';c.observed={...x.scope,native_generation:'43'};x.g.onBegin=()=>{};x.s.running=true;assert.equal(c.ApexCatalogAuthorityRecover(x.p,x.g),false);assert.equal(events.filter(x=>x==='begin').length,1);c.ApexCatalogGridChanged({});assert.equal(c.ApexCatalogAuthorityRecover(x.p,x.g),false);assert.equal(events.filter(x=>x==='begin').length,1);assert.equal(x.s.lease,x.lease);")
    def test_malformed_receipt_fails_closed_without_recovery_or_touching_old_lease(self):
        self.case("for(const mutate of [t=>t.scope.owner='other',t=>t.protocol=true,t=>t.input_released='true',t=>t.release_refused='x'.repeat(161),t=>t.generation='7']){const x=setup();x.g.terminal=clone(x.terminal);mutate(x.g.terminal);assert.equal(c.ApexCatalogAuthorityHold(x.g),true);assert.equal(c.ApexCatalogAuthorityHeld(x.g).receipt.verified,false);c.apexFormsNativeGeneration='43';x.s.running=true;assert.equal(c.ApexCatalogAuthorityRecover(x.p,x.g),false);assert.deepEqual(events,[]);assert.equal(x.lease.active,true);}")
    def test_scope_change_during_observation_or_native_begin_keeps_latch_and_old_lease(self):
        self.case("const x=setup();x.g.terminal=x.terminal;c.ApexCatalogAuthorityHold(x.g);c.apexFormsNativeGeneration='43';c.observed={...x.scope,native_generation:'43'};x.g.onBegin=()=>{x.g.terminal=null;c.apexFormsNativeGeneration='44';};x.s.running=true;assert.equal(c.ApexCatalogAuthorityRecover(x.p,x.g),false);assert.equal(x.s.lease,x.lease);assert.equal(c.ApexCatalogAuthorityHold(x.g),true);assert.equal(x.lease.active,true);")
    def test_other_panel_retires_only_main_references_no_foreign_cancel(self):
        self.case("const x=setup();x.g.terminal=x.terminal;c.ApexCatalogAuthorityHold(x.g);c.ApexCatalogGridRetireInactive(x.s);assert.equal(x.s.grid,null);assert.equal(x.s.lease,null);assert.equal(x.lease.active,true);assert.equal(c.ApexCatalogGridOwns(x.g),true);assert.equal(c.ApexCardApply(x.p,x.g),500);assert.deepEqual(events,[]);")
    def test_terminal_dispose_does_not_write_shared_lease_or_native_widget(self):
        self.case("const x=setup();x.g.terminal=x.terminal;c.ApexCatalogAuthorityHold(x.g);c.removeEventListener=()=>{};c.RemoveMessageListener=()=>{};c.ApexCatalogGridDispose();assert.equal(c.apexCatalogGrid,null);assert.equal(x.lease.active,true);assert.equal(x.lease.frame_validated,true);assert.deepEqual(events,[]);")
    def test_actual_view_is_captured_without_optional_lease_view_and_no_spurious_recovery(self):
        self.case("const x=setup();delete x.s.authority_owners;delete x.lease.view;c.ApexCatalogAuthorityRemember(x.lease);x.g.terminal=x.terminal;assert.equal(c.ApexCatalogAuthorityHold(x.g),true);const h=c.ApexCatalogAuthorityHeld(x.g);assert.equal(h.view,x.view);assert.equal(h.receipt.verified,true);x.s.running=true;assert.equal(c.ApexCatalogAuthorityRecover(x.p,x.g),false);assert.deepEqual(events,[]);")
    def test_legacy_restore_forgets_only_main_references_on_terminal_grid(self):
        self.case("const x=setup();x.g.terminal=x.terminal;c.ApexCatalogAuthorityHold(x.g);const geometry={grid:x.g,panel:x.p};c.apexCardGeometry=geometry;c.apexCardLayout={};c.ApexCardForget=()=>{events.push('forget');c.apexCardGeometry=null;c.apexCardLayout=null;};c.ApexCardRestore();assert.equal(c.apexCardGeometry,null);assert.equal(geometry.incremental,undefined);assert.equal(geometry.applying,undefined);assert.equal(x.lease.active,true);assert.deepEqual(events,['forget']);")
    def test_foreign_same_qname_and_custom_subclass_never_call_diagnostic_getter(self):
        self.case("setup();class Child extends SelectableRecyclingGridLayout{};for(const g of [{},new Child()]){g.qname='olympus.layout::SelectableRecyclingGridLayout';g.ApexGridAuthorityStatus=fail('foreign diagnostic');assert.equal(c.ApexCatalogAuthorityHold(g),false);}")
    def test_dispose_forgets_held_saved_geometry_before_erasing_authority_evidence(self):
        self.case("const x=setup();x.g.terminal=x.terminal;c.ApexCatalogAuthorityHold(x.g);const geometry={grid:x.g,panel:x.p},other={grid:{}};c.apexCardGeometry=geometry;c.apexPanelGeometry={clothing:{geometry},body:{geometry:other}};c.ApexCardForget=()=>{events.push('forget');c.apexCardGeometry=null;c.apexCardLayout=null;};c.removeEventListener=()=>{};c.RemoveMessageListener=()=>{};c.ApexCatalogGridDispose();assert.equal(c.apexCatalogGrid,null);assert.equal(c.apexCardGeometry,null);assert.equal(c.apexPanelGeometry.clothing,undefined);assert.equal(c.apexPanelGeometry.body.geometry,other);assert.equal(x.lease.active,true);assert.deepEqual(events,['forget']);")
    def test_recovery_always_clears_new_owned_frame_flag_even_after_native_scope_change(self):
        self.case("const x=setup();x.g.terminal=x.terminal;c.ApexCatalogAuthorityHold(x.g);c.apexFormsNativeGeneration='43';c.observed={...x.scope,native_generation:'43'};let owned;x.g.onBegin=r=>{owned=r.owner;x.g.terminal=null;c.apexFormsNativeGeneration='44';};x.s.running=true;assert.equal(c.ApexCatalogAuthorityRecover(x.p,x.g),false);assert.equal(owned.frame_validated,false);assert.equal(x.lease.frame_validated,true);assert.equal(x.s.lease,x.lease);")
    def test_actual_view_capture_refuses_reentry_that_replaces_lease(self):
        self.case("const x=setup();delete x.s.authority_owners;const foreign={active:true};x.p.mcTileList.GetGridView=()=>{x.s.lease=foreign;return x.view;};c.ApexCatalogAuthorityRemember(x.lease);assert.equal(x.s.authority_owners,undefined);assert.equal(foreign.active,true);")
    def test_outer_catalog_dispose_never_writes_held_legacy_widgets_but_cleans_known_other_effects(self):
        self.case("const x=setup();x.g.terminal=x.terminal;c.ApexCatalogAuthorityHold(x.g);const held={grid:x.g,cell:{parent:x.view},effect:{parent:{removeChild:fail('held child')}},frame:{transform:{set colorTransform(v){throw Error('held transform')}}}};let cleaned=0;const other={grid:{},cell:{},effect:{parent:{removeChild(){cleaned++}}},frame:{transform:{set colorTransform(v){cleaned++}}},transform:{original:true}};c.apexCatalogEffects=[held,other];c.apexCardGeometry={grid:x.g};c.apexPanelGeometry={clothing:{geometry:c.apexCardGeometry}};c.ApexCardForget=()=>{c.apexCardGeometry=null;c.apexCardLayout=null;};for(const n of ['ApexCatalogTraceDispose','ApexLayoutTraceDispose','ApexPanelsDispose','ApexColumnsDispose','ApexEquippedDispose','ApexCatalogKeyboardDispose','ApexCompanionDispose','ApexSearchDispose'])c[n]=()=>{};c.removeEventListener=()=>{};c.RemoveMessageListener=()=>{};c.stage.removeEventListener=()=>{};c.flash.events.MouseEvent={MOUSE_MOVE:'move',MOUSE_UP:'up'};c.apexCatalogRegistered=false;c.apexCatalogRefreshRegistered=false;c.apexCatalogBindingRegistered=false;c.apexCatalogUi=null;c.ApexCatalogDispose();assert.equal(cleaned,2);assert.equal(held.authority_forget,true);assert.equal(c.apexCatalogGrid,null);assert.equal(c.apexCardGeometry,null);assert.equal(c.apexPanelGeometry,null);assert.equal(c.apexCatalogEffects.length,0);assert.equal(x.lease.active,true);")
    def test_unattributed_legacy_effect_is_reported_and_never_restored_while_known_owned_still_cleans(self):
        self.case("const x=setup();x.g.terminal=x.terminal;c.ApexCatalogAuthorityHold(x.g);const old={cell:{parent:{}},effect:{parent:{removeChild:fail('unattributed child')}},frame:{transform:{set colorTransform(v){throw Error('unattributed transform')}}}};let n=0;const own={grid:{},effect:{parent:{removeChild(){n++}}},frame:null};c.apexCatalogEffects=[old,own];c.ApexCatalogClearEffects();assert.equal(n,1);assert.equal(old.authority_forget,true);assert.equal(old.authority_forget_reason,'unattributed-effect-after-authority-loss');assert.equal(x.s.authority_unattributed_effects,1);assert.equal(c.ApexCatalogGridStatus().unattributed_effects,1);assert.equal(c.apexCatalogEffects.length,0);")
    def test_unheld_legacy_effect_cleanup_is_unchanged(self):
        self.case("setup();let n=0;c.apexCatalogEffects=[{cell:{parent:{}},effect:{parent:{removeChild(){n++}}},frame:{transform:{set colorTransform(v){n++}}},transform:{}}];c.ApexCatalogClearEffects();assert.equal(n,2);assert.equal(c.apexCatalogEffects.length,0);")
    def test_selecting_healthy_other_grid_does_not_retire_held_prior_effect(self):
        self.case("const x=setup();x.g.terminal=x.terminal;c.ApexCatalogAuthorityHold(x.g);c.apexCatalogEffects=[{grid:x.g,cell:{parent:x.view},effect:{parent:{removeChild:fail('held child')}},frame:{transform:{set colorTransform(v){throw Error('held transform')}}}}];c.ApexCatalogCells=()=>[];c.apexCatalogSelectionFrames=0;c.apexCatalogSelectionMaxMs=0;c.apexCatalogSelectionOverBudget=0;c.ApexCatalogSelection({});assert.equal(c.apexCatalogEffects.length,0);assert.equal(x.lease.active,true);")
    def test_stage_changes_only_declared_owned_bodies_and_appends_private_helpers(self):
        if FIXTURE is None:self.skipTest('Explicit compiled Main fixture not supplied')
        before=(FIXTURE/'baseline.as').read_text();after=stage.inject_main(before)
        for name in stage.REPLACED:
            a,b=pool.method_extent(before,name);x,y=pool.method_extent(after,name);self.assertNotEqual(before[a:b],after[x:y],name)
        for name in ('ApexTick','ApexCatalogGridLeaseCurrent','ApexCatalogGridValidate','ApexCatalogGridRequest','ApexCatalogKeyboardPublicationReady'):
            a,b=pool.method_extent(before,name);x,y=pool.method_extent(after,name);self.assertEqual(before[a:b],after[x:y],name)

if __name__=='__main__':unittest.main()
