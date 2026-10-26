"""Execute the actual AS readback and reject adversarial thin host packets."""
import copy
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'Source'))
from apex_core import cas_ui


def source_method(name, parameters, stop=None):
    text = (ROOT/'Source/CASUi/semantic_methods.as').read_text(encoding='utf-8')
    tail = text.split('private function '+name+'(',1)[1]
    tail = re.split(r'\n      private (?:function|var) ',tail,maxsplit=1)[0]
    body = tail.split('{',1)[1].rsplit('}',1)[0]
    if stop: body = body.split(stop,1)[0]+'\nthrow Error("Unsupported fixture operation");'
    body = re.sub(r'\b(var\s+\w+)\s*:\s*[\w.*]+',r'\1',body)
    body = re.sub(r'\s+as\s+[\w.]+','',body)
    body = re.sub(r'([\w.\[\]]+)\s+is\s+(int|String|Number|Boolean|Array)',r'isType(\1,"\2")',body)
    body = re.sub(r'catch\((\w+)\s*:\s*Error\)',r'catch(\1)',body)
    body = re.sub(r'for each\(([^)]+) in ([^)]+)\)',r'for(\1 of \2)',body)
    return 'function '+name+'('+parameters+'){'+body+'}\n'


@unittest.skipUnless(shutil.which('node'), 'Node required for actual AS readback fixtures')
class SourceReadbackTests(unittest.TestCase):
    def run_source(self, test):
        source = r'''
const assert=require('node:assert/strict');const int=x=>Number(x)|0;
function isType(v,t){return t==='Array'?Array.isArray(v):t==='int'?Number.isInteger(v):typeof v===t.toLowerCase();}
var apexCatalogTrace=null;
var apexTicking=true,apexDisconnected=false,apexSocketActive=true,apexNativeChannel='7',apexNonce='a'.repeat(64),apexClaimNonce=apexNonce;
var apexBoundSim='12',mCurrSimInfo={simId:'12',householdId:'34',occultLayer:0,occultType:2,allOccultTypes:5};
var apexOwnerSession=3,apexFormsNativeState='bound',apexFormsSelectedId='alien/first',apexFormsDesiredId='',apexFormsNativeGeneration='91';
var apexFormsIntent=null,apexFormsNativeIntent=null,apexMoleculeIntent=null,apexPairIntent=null,apexFormsApplying=false;
var mCurrState=40,mCurrentPanel={visible:true},apexTimer={currentCount:10},apexReadbackTick=1,apexPendingPhase=1,apexAwaiting='';
var apexPendingFields=['b'.repeat(32),'12','catalog-state','0','0','0',''],apexPendingReply={ok:false},apexPendingContext={};
var nativeCalls=[],cursorCalls=0,statusCalls=0,fullCalls=0,completeCalls=0;
var fresh={simId:'12',householdId:'34',occultLayer:0,occultType:4,allOccultTypes:5};
var cursor='VIEWSTATE|12|alien/first|2|0|bound|91',outfit={outfit_type:0,outfit_index:0};
const CommunicationManager={CallGameService(name){nativeCalls.push(name);if(name==='CASGetSimInfo')return fresh;
 if(name==='CasGetCurrSimOutfitSlot')return outfit;throw Error('Unexpected full inventory '+name);}};
function ApexNativeExchange(value){assert.equal(value,'STATE|7');cursorCalls++;return cursor;}
function ApexEncode(v){return JSON.stringify(v);}
const workspace={search:{available:true,text:'',appearance_written:false},draw_trace:{enabled:false},layout_trace:{enabled:false},incremental_grid:{enabled:true,native:{phase:'bind'}}};
function ApexCatalogStatus(){statusCalls++;return workspace;}function ApexSnapshot(){fullCalls++;throw Error('Full native inventory');}
function ApexComplete(){completeCalls++;}const MenuState={CLOTHING_BODY_WINGS:114};
'''
        for name, params, stop in (
            ('ApexOwnerSimRow','raw',None),
            ('ApexCatalogReadbackOnly','operation',None),
            ('ApexCatalogReadbackContext','selected',None),
            ('ApexCatalogSnapshot','before,after',None),
            ('ApexControlResult','operation,state,category,index,value,context,client','if(operation=="form-owner-select")'),
            ('ApexReadback','',None),
        ): source += source_method(name,params,stop)
        source += 'apexPendingContext.catalog_before=ApexCatalogReadbackContext(ApexOwnerSimRow(fresh));nativeCalls=[];cursorCalls=0;\n'
        run = subprocess.run(['node','-'],input=source+test,text=True,capture_output=True,timeout=15)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)

    def test_thin_readback_uses_two_fresh_getters_one_cursor_and_one_workspace(self):
        self.run_source('''
ApexReadback.call({mCurrState,mCurrSimInfo,mCurrentPanel});
assert.equal(apexPendingReply.ok,true);assert.equal(completeCalls,1);assert.equal(fullCalls,0);
assert.deepEqual(nativeCalls,['CASGetSimInfo','CasGetCurrSimOutfitSlot']);assert.equal(cursorCalls,1);assert.equal(statusCalls,1);
const c=apexPendingReply.client;assert.equal(c.scope,'native-cas-catalog-client');assert.equal(c.appearance_written,false);
assert.equal(c.sim.occultType,4);assert.equal(c.catalog_identity.after.native_kind,2);
assert.equal(c.control.workspace,c.catalog_workspace);assert.equal(c.control.workspace,workspace);
assert.equal('catalogs' in c,false);assert.equal('hair_swatches' in c,false);
''')

    def test_foreign_same_kind_owner_generation_outfit_or_session_refuses(self):
        for mutation in ("cursor='VIEWSTATE|12|alien/second|2|0|bound|91';",
                         "cursor='VIEWSTATE|12|alien/first|2|0|bound|92';",
                         "outfit={outfit_type:1,outfit_index:0};",'apexOwnerSession=4;',
                         "fresh={...fresh,simId:'13'};",'apexFormsIntent={};'):
            with self.subTest(mutation=mutation):
                self.run_source(mutation+'''
ApexReadback.call({mCurrState,mCurrSimInfo,mCurrentPanel});assert.equal(apexPendingReply.ok,false);
assert.equal(statusCalls,0);assert.equal(fullCalls,0);assert.equal(completeCalls,1);
''')

    def test_allowlist_excludes_full_status_slider_and_all_appearance_paths(self):
        self.run_source('''
for(const op of ['status','catalog-open','catalog-view','catalog-slider','catalog-key','catalog-input','catalog-companion','select','swatch','undo','redo','accept','form-owner-select'])
 assert.equal(ApexCatalogReadbackOnly(op),false,op);
''')

    def test_catalog_navigation_menu_change_uses_full_readback_without_thin_rejection(self):
        for operation in ('catalog-open','catalog-view'):
            with self.subTest(operation=operation):
                self.run_source('apexPendingFields[2]='+json.dumps(operation)+''';
// The command intentionally changes menu after its original observation.
mCurrState=41;assert.notEqual(apexPendingContext.catalog_before.menu_state,mCurrState);
ApexSnapshot=function(){fullCalls++;return {scope:'native-cas-client',sim:fresh,
 menu_state:mCurrState,catalog_workspace:workspace};};
ApexReadback.call({mCurrState,mCurrSimInfo,mCurrentPanel});
assert.equal(apexPendingReply.ok,true);assert.equal(fullCalls,1);assert.equal(completeCalls,1);
assert.equal(cursorCalls,0);assert.deepEqual(nativeCalls,['CASGetSimInfo']);
assert.equal(apexPendingReply.client.scope,'native-cas-client');assert.equal(apexPendingReply.client.menu_state,41);
assert.equal(apexPendingReply.client.control.workspace,workspace);
''')

    def test_control_result_reuses_capture_including_existing_input_and_companion(self):
        self.run_source('''
for(const op of ['catalog-state','catalog-search','catalog-style','catalog-open','catalog-view','catalog-slider','catalog-cards','catalog-card-reset','panel-layout','catalog-key','catalog-input','catalog-companion']){
 const result=ApexControlResult(op,0,0,0,'enter,1',{}, {catalog_workspace:workspace});assert.equal(result.workspace,workspace);
}
assert.equal(ApexControlResult('catalog-trace',0,0,0,'',{}, {catalog_workspace:workspace}).trace,workspace.draw_trace);
assert.equal(ApexControlResult('catalog-layout-trace',0,0,0,'',{}, {catalog_workspace:workspace}).trace,workspace.layout_trace);
assert.equal(statusCalls,0);
''')

    def test_catalog_state_execute_has_no_calls_or_mutation_parameters(self):
        source = source_method('ApexControlExecute','operation,state,category,index,value,reply,context','if(operation=="catalog-layout-trace")')
        run = subprocess.run(['node','-'],input="const assert=require('node:assert/strict');\n"+source+'''
const reply={mutation_started:false},context={};ApexControlExecute('catalog-state',0,0,0,'',reply,context);
assert.deepEqual(reply,{mutation_started:false});assert.deepEqual(context,{});
assert.throws(()=>ApexControlExecute('catalog-state',0,0,1,'',reply,context));
assert.throws(()=>ApexControlExecute('catalog-state',0,0,0,'refresh',reply,context));
''',text=True,capture_output=True,timeout=10)
        self.assertEqual(run.returncode,0,run.stderr)


class HostReadbackTests(unittest.TestCase):
    def setUp(self):
        cas_ui._RECORDS.clear();cas_ui._PEERS.clear()
        self.token='a'*64;self.rid='b'*32
        self.context=dict(sim_id='12',household_id='34',owner_id='alien/first',native_kind=2,shell_kind=4,
            native_mask=5,native_generation='91',session=3,layer=0,outfit_type=0,outfit_index=0,menu_state=40)
        cas_ui._PEERS[self.token]={'sim_id':'12','observed_at':0,'owner_state_identity':('OWNERSTATE|alien/first|2|0|bound',91)}
        self.row={'state':'pending','sim_id':'12','request':{'operation':'catalog-state'},'transport':'loopback-socket',
                  'delivery':'queued','wire':self.rid+'|12|catalog-state|0|0|0|','result':None}
        cas_ui._RECORDS[self.rid]=self.row
        self.assertEqual(cas_ui.poll_client(self.token,clock=lambda:0),self.row['wire'])

    def packet(self):
        c=self.context;workspace={'incremental_grid':{'enabled':True,'native':{'phase':'bind'}}}
        return {'protocol':1,'ok':True,'scope':'native-cas-client','cas_request_id':self.rid,'operation':'catalog-state','mutation_started':False,
            'client':{'protocol':1,'scope':'native-cas-catalog-client','appearance_written':False,
                'sim':{'simId':c['sim_id'],'householdId':c['household_id'],'occultType':c['shell_kind'],
                       'allOccultTypes':c['native_mask'],'occultLayer':c['layer']},
                'menu_state':40,'panel_visible':True,'outfit':{'outfit_type':0,'outfit_index':0},
                'form_strip':{'sim_id':'12','selected_owner_id':c['owner_id'],'native_owner_state':'bound',
                    'desired_owner_id':'','gesture_pending':False,'native_generation':'91','session':3},
                'catalog_identity':{'request_id':self.rid,'peer_nonce':self.token,'before':copy.deepcopy(c),'after':copy.deepcopy(c)},
                'catalog_workspace':workspace,'control':{'operation':'catalog-state','appearance_written':False,'workspace':copy.deepcopy(workspace)}}}

    def test_pending_state_completes_without_full_inventory_or_producer_access(self):
        with (patch.object(cas_ui,'validate_client',side_effect=AssertionError('Full inventory validator')),
              patch.object(cas_ui,'owner_pair_diagnostic',side_effect=AssertionError('Producer inventory'))):
            cas_ui.receive_socket(self.token,self.rid,json.dumps(self.packet()),clock=lambda:1)
        self.assertEqual(self.row['state'],'completed')
        self.assertNotIn('cas_room',self.row);self.assertNotIn('owner_pair_diagnostic',self.row)

    def test_foreign_scope_operation_nonce_owner_generation_and_fields_refuse(self):
        mutations=[lambda p:p.update(operation='status'),lambda p:p.update(mutation_started=True),
            lambda p:p['client'].update(scope='native-cas-client'),lambda p:p['client'].update(appearance_written=True),
            lambda p:p['client'].update(catalogs=[]),lambda p:p['client']['catalog_identity'].update(peer_nonce='c'*64),
            lambda p:p['client']['catalog_identity'].update(request_id='c'*32),
            lambda p:p['client']['catalog_identity']['after'].update(owner_id='alien/second'),
            lambda p:p['client']['catalog_identity']['after'].update(native_generation='92'),
            lambda p:p['client']['catalog_identity']['after'].update(extra='foreign'),
            lambda p:p['client']['catalog_identity']['before'].update(outfit_index=False),
            lambda p:p['client']['sim'].update(simId='13'),lambda p:p['client']['sim'].update(occultType=True),
            lambda p:p['client']['form_strip'].update(desired_owner_id='alien/second'),
            lambda p:p['client']['control']['workspace'].update(foreign=True),
            lambda p:p['client'].pop('outfit')]
        for mutate in mutations:
            p=self.packet();mutate(p)
            with self.subTest(packet=p),self.assertRaises((ValueError,KeyError,TypeError)):
                cas_ui.receive_socket(self.token,self.rid,json.dumps(p),clock=lambda:1)
            self.assertEqual(self.row['state'],'pending')

    def test_consistently_forged_owner_and_generation_still_refuse_claimed_cursor(self):
        for key,value in [('owner_id','alien/second'),('native_generation','92')]:
            p=self.packet()
            for side in ('before','after'):p['client']['catalog_identity'][side][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'claimed native cursor'):
                cas_ui.receive_socket(self.token,self.rid,json.dumps(p),clock=lambda:1)

    def test_full_status_and_equipping_reject_thin_scope(self):
        for op in ('status','catalog-open','catalog-view','catalog-input','catalog-key','catalog-companion','catalog-slider','select','undo','accept'):
            self.row['request']={'operation':op};p=self.packet();p['operation']=op
            with self.subTest(op=op),self.assertRaises(ValueError):cas_ui.receive(self.rid,json.dumps(p))

    def test_thin_packet_never_seeds_cli_full_snapshot_preflight_cache(self):
        sys.path.insert(0,str(ROOT/'tools'))
        import cas_client
        args=SimpleNamespace(state=ROOT/'.work/private-readback-fixture.json',sim_id='12')
        with cas_client.observation_batch(args.state):
            cas_client._remember_observation(args,self.packet(),lambda:1)
            self.assertIsNone(cas_client._recent_observation(args,lambda:1))
            full=self.packet();full['client']['scope']='native-cas-client'
            cas_client._remember_observation(args,full,lambda:1)
            self.assertIsNotNone(cas_client._recent_observation(args,lambda:1))
            cas_client._remember_observation(args,self.packet(),lambda:1)
            self.assertIsNone(cas_client._recent_observation(args,lambda:1))

    def test_form_preflight_chooses_full_snapshot_before_newer_thin_record(self):
        self.row.update(state='completed',result=self.packet(),acknowledged_at=.5)
        full={'scope':'native-cas-client','sim':{'simId':'12'}}
        prior=dict(self.row,request={'operation':'status'},result={'ok':True,'client':full},acknowledged_at=.4)
        cas_ui._RECORDS.clear();cas_ui._RECORDS['c'*32]=prior;cas_ui._RECORDS[self.rid]=self.row
        request={'operation':'form-select','household_id':'34','expected_layer':0,'form_flags':2,'native_session':3}
        with (patch.object(cas_ui,'_form_select_original',return_value={'original':True}),
              patch.object(cas_ui,'form_selection_binding',return_value={'bound':True}) as binding):
            cas_ui.submit('12',request,clock=lambda:1,backend=object())
        self.assertEqual(binding.call_args.args[0],full)

    def test_catalog_state_wire_has_no_fields_and_cli_exposes_operation(self):
        _,wire=cas_ui.envelope('12',{'operation':'catalog-state'})
        self.assertEqual(wire.split('|')[2:],['catalog-state','0','0','0',''])
        with self.assertRaises(ValueError):cas_ui.envelope('12',{'operation':'catalog-state','refresh':True})
        sys.path.insert(0,str(ROOT/'tools'))
        import apex_cli
        args=apex_cli.parser().parse_args(['cas','catalog-state','--state','private.json','--sim-id','12'])
        self.assertEqual(args.operation,'catalog-state')
