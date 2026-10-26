"""Actual production panel navigation: AS execution, owner receipts and CLI routing."""
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

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Source'))
sys.path.insert(0,str(ROOT/'tools'))
from apex_core import cas_controls

from apex_core import cas_ui as host

def source_method(name,parameters):
    text=(ROOT/'Source/CASUi/semantic_methods.as').read_text(encoding='utf-8')
    tail=text.split('private function '+name+'(',1)[1]
    tail=re.split(r'\n      private (?:function|var) ',tail,maxsplit=1)[0]
    body=tail.split('{',1)[1].rsplit('}',1)[0]
    body=re.sub(r'\b(var\s+\w+)\s*:\s*[\w.*]+',r'\1',body)
    body=re.sub(r'\s+as\s+[\w.]+','',body)
    body=re.sub(r'([\w.\[\]]+)\s+is\s+(int|String|Number|Boolean|Array|ClothingPanel|FaceModPanel)',r'isType(\1,"\2")',body)
    body=re.sub(r'catch\((\w+)\s*:\s*Error\)',r'catch(\1)',body)
    body=re.sub(r'for each\(([^)]+) in ([^)]+)\)',r'for(\1 of \2)',body)
    return 'function '+name+'('+parameters+'){'+body+'}\n'


@unittest.skipUnless(shutil.which('node'),'Node required for actual AS readback proof')
class ASReadback(unittest.TestCase):
    def run_as(self,body):
        source=r'''
const assert=require('node:assert/strict');const int=x=>Number(x)|0;
function isType(v,t){return t==='Array'?Array.isArray(v):t==='int'?Number.isInteger(v):typeof v===t.toLowerCase();}
var apexTicking=true,apexDisconnected=false,apexSocketActive=true,apexNativeChannel='7',apexNonce='a'.repeat(64),apexClaimNonce=apexNonce;
var apexBoundSim='12',mCurrSimInfo={simId:'12',householdId:'34',occultLayer:0,occultType:2,allOccultTypes:5};
var apexOwnerSession=3,apexFormsNativeState='bound',apexFormsSelectedId='alien/first',apexFormsDesiredId='',apexFormsNativeGeneration='91';
var apexFormsIntent=null,apexFormsNativeIntent=null,apexMoleculeIntent=null,apexPairIntent=null,apexFormsApplying=false;
var mCurrState=40,mCurrentPanel={visible:true},apexTimer={currentCount:10},apexReadbackTick=1,apexPendingPhase=1,apexAwaiting='';
var apexPendingFields=['b'.repeat(32),'12','panel-navigation','41','0','0',''],apexPendingReply={ok:false,mutation_started:true},apexPendingContext={};
var nativeCalls=[],cursorCalls=0,statusCalls=0,fullCalls=0,completeCalls=0;
var apexCatalogTrace=null;function ApexCatalogTimerStep(){throw Error('Disabled trace must not do timing work');}
var fresh={simId:'12',householdId:'34',occultLayer:0,occultType:4,allOccultTypes:5};
var cursor='VIEWSTATE|12|alien/first|2|0|bound|91',outfit={outfit_type:0,outfit_index:0};
var apexCardGeometry={panel:mCurrentPanel},apexCardLayout={columns:12,scale:.5,width:600,card_width:40,card_height:60,gap_x:2,gap_y:4};
const CommunicationManager={CallGameService(name){nativeCalls.push(name);if(name==='CASGetSimInfo')return fresh;
 if(name==='CasGetCurrSimOutfitSlot')return outfit;throw Error('Unexpected inventory getter '+name);}};
function ApexNativeExchange(value){assert.equal(value,'STATE|7');cursorCalls++;return cursor;}
function ApexEncode(v){return JSON.stringify(v);}
function ApexCatalogStatus(){statusCalls++;throw Error('Unexpected catalogue diagnostic');}
function ApexSnapshot(){fullCalls++;throw Error('Unexpected full diagnostic');}
function ApexComplete(){completeCalls++;}const MenuState={CLOTHING_BODY_WINGS:114};
'''
        for name,params in (('ApexOwnerSimRow','raw'),('ApexCatalogReadbackOnly','operation'),
            ('ApexCatalogReadbackContext','selected'),('ApexCatalogSnapshot','before,after'),
            ('ApexPanelNavigationSnapshot','before,after,requested'),('ApexExecute','message'),('ApexReadback','')):
            source+=source_method(name,params)
        source+='apexPendingContext.navigation_before=ApexCatalogReadbackContext(ApexOwnerSimRow(fresh));mCurrState=41;nativeCalls=[];cursorCalls=0;\n'
        completed=subprocess.run(['node','-'],input=source+body,text=True,capture_output=True,timeout=15)
        self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)

    def test_next_tick_readback_has_exact_identity_without_full_or_card_diagnostics(self):
        self.run_as('''
ApexReadback.call({mCurrState,mCurrSimInfo,mCurrentPanel});
assert.equal(apexPendingReply.ok,true);assert.equal(completeCalls,1);assert.equal(fullCalls,0);assert.equal(statusCalls,0);
assert.deepEqual(nativeCalls,['CASGetSimInfo','CasGetCurrSimOutfitSlot']);assert.equal(cursorCalls,1);
const c=apexPendingReply.client;assert.equal(c.scope,'native-cas-navigation-client');assert.equal(c.appearance_written,false);
assert.equal(c.requested_menu_state,41);assert.equal(c.menu_state,41);assert.equal(c.navigation_identity.before.menu_state,40);
assert.equal(c.navigation_identity.after.menu_state,41);assert.equal(c.navigation_identity.after.native_kind,2);
assert.equal(c.sim.occultType,4);assert.equal(c.card_layout.columns,12);
for(const name of ['catalogs','selected','hair_swatches','catalog_workspace','native_context','owner_pair_observation'])assert.equal(name in c,false,name);
''')

    def test_before_readback_tick_it_does_nothing(self):
        self.run_as('''
apexReadbackTick=11;ApexReadback.call({mCurrState,mCurrSimInfo,mCurrentPanel});
assert.equal(completeCalls,0);assert.deepEqual(nativeCalls,[]);assert.equal(cursorCalls,0);
''')

    def test_actual_execute_retains_normal_calls_exact_uuid_and_delayed_readback(self):
        self.run_as('''
var apexReceiving=true,apexWire='b'.repeat(32)+'|12|panel-navigation|41|0|0|';
var apexLastId='',apexLastReply='',apexSocketError='';
var sent=[],handled=[];mCurrState=40;apexPendingFields=null;apexPendingReply=null;apexPendingContext=null;
function HandleContextMenuSetMenuState(value){handled.push(value);mCurrState=value.menuState;}
CommunicationManager.SendUIMessage=(name,value)=>sent.push([name,value]);
function ApexSocketReply(){throw Error('No early or duplicate ACK');}
ApexExecute();
assert.equal(apexLastId,'b'.repeat(32));assert.equal(apexClaimNonce,apexNonce);assert.equal(apexPendingPhase,1);
assert.equal(apexReadbackTick,11);assert.equal(apexPendingContext.navigation_before.menu_state,40);
assert.deepEqual(nativeCalls,['CASGetSimInfo','CasGetCurrSimOutfitSlot']);assert.equal(cursorCalls,1);
assert.deepEqual(handled,[{menuState:41,skipAnim:true,setZoomState:true}]);assert.deepEqual(sent,[['CASChangeMenuState',41]]);
assert.equal(apexPendingReply.mutation_started,true);assert.equal(completeCalls,0);assert.equal(fullCalls,0);
apexReceiving=true;nativeCalls=[];ApexExecute();
assert.deepEqual(nativeCalls,[]);assert.equal(handled.length,1);assert.equal(sent.length,1);
assert.equal(apexSocketError,'Duplicate CAS claim is still unresolved');
''')

    def test_context_drift_and_wrong_panel_fail_without_diagnostic_fallback(self):
        for mutate in ("cursor='VIEWSTATE|12|alien/second|2|0|bound|91';",
                       "cursor='VIEWSTATE|12|alien/first|2|0|bound|92';",
                       "cursor='VIEWSTATE|12|alien/first|4|0|bound|91';",
                       "cursor='VIEWSTATE|12|alien/first|2|1|bound|91';",
                       'outfit={outfit_type:1,outfit_index:0};',
                       'outfit={outfit_type:0,outfit_index:1};','apexOwnerSession=4;',
                       "fresh={...fresh,simId:'13'};","fresh={...fresh,householdId:'35'};",
                       'apexFormsIntent={};','mCurrState=42;','mCurrentPanel.visible=false;'):
            with self.subTest(mutate=mutate):
                self.run_as(mutate+'''
ApexReadback.call({mCurrState,mCurrSimInfo,mCurrentPanel});
assert.equal(apexPendingReply.ok,false);assert.equal(completeCalls,1);assert.equal(fullCalls,0);assert.equal(statusCalls,0);
''')

    def test_no_physical_card_queries_or_stale_panel_layout_claim(self):
        self.run_as('''
apexCardGeometry={panel:{visible:true},grid:new Proxy({},{get(){throw Error('Grid must not be read');}})};
ApexReadback.call({mCurrState,mCurrSimInfo,mCurrentPanel});
assert.equal(apexPendingReply.ok,true);
assert.deepEqual(apexPendingReply.client.card_layout,{query:'not-available-current-panel',available:false});
''')

    def test_cached_metrics_are_fixed_and_finite(self):
        for mutate in ('apexCardLayout.scale=NaN;','apexCardLayout.columns=1;','apexCardLayout.width=9000;',
                       'apexCardLayout.gap_y="4";'):
            with self.subTest(mutate=mutate):
                self.run_as(mutate+'''
ApexReadback.call({mCurrState,mCurrSimInfo,mCurrentPanel});assert.equal(apexPendingReply.ok,false);assert.equal(fullCalls,0);
''')


class HostPacket(unittest.TestCase):
    def setUp(self):
        host._RECORDS.clear();host._PEERS.clear()
        self.token='a'*64;self.rid='b'*32
        self.request={'operation':'panel-navigation','panel':'hair','test_token':'fixture'}
        self.state=host.panel(self.request['panel'])
        self.context=dict(sim_id='12',household_id='34',owner_id='alien/first',native_kind=2,shell_kind=4,
            native_mask=5,native_generation='91',session=3,layer=0,outfit_type=0,outfit_index=0,menu_state=999)
        host._PEERS[self.token]={'sim_id':'12','observed_at':0,'owner_state_identity':('OWNERSTATE|alien/first|2|0|bound',91)}
        self.row={'state':'pending','sim_id':'12','request':copy.deepcopy(self.request),'transport':'loopback-socket',
            'delivery':'queued','wire':self.rid+'|12|panel-navigation|'+str(self.state)+'|0|0|','result':None}
        host._RECORDS[self.rid]=self.row
        self.assertEqual(host.poll_client(self.token,clock=lambda:0),self.row['wire'])

    def packet(self):
        before=copy.deepcopy(self.context);after=dict(before,menu_state=self.state)
        return dict(protocol=1,ok=True,scope='native-cas-client',cas_request_id=self.rid,
            operation='panel-navigation',mutation_started=True,client=dict(protocol=1,
                scope='native-cas-navigation-client',appearance_written=False,
                sim={'simId':'12','householdId':'34','occultType':4,'allOccultTypes':5,'occultLayer':0},
                menu_state=self.state,panel_visible=True,requested_menu_state=self.state,
                outfit={'outfit_type':0,'outfit_index':0},
                form_strip=dict(sim_id='12',selected_owner_id='alien/first',native_owner_state='bound',
                    desired_owner_id='',gesture_pending=False,native_generation='91',session=3),
                navigation_identity=dict(request_id=self.rid,peer_nonce=self.token,before=before,after=after),
                card_layout=dict(query='cached-current-panel-only',available=True,columns=12,scale=.5,
                    width=600,card_width=40,card_height=60,gap_x=2,gap_y=4)))

    def receive(self,p):
        return host.receive_socket(self.token,self.rid,json.dumps(p),clock=lambda:1)

    def test_actual_receiver_completes_without_inventory_producer_or_full_preflight(self):
        p=self.packet()
        with (patch.object(host,'validate_client',side_effect=AssertionError('full snapshot')),
              patch.object(host,'owner_pair_diagnostic',side_effect=AssertionError('producer'))):
            self.receive(p)
        self.assertEqual(self.row['state'],'completed');self.assertEqual(self.row['result'],p)
        self.assertNotIn('cas_room',self.row);self.assertNotIn('owner_pair_diagnostic',self.row)
        result=host.result(self.rid)
        self.assertTrue(result['ui_transition_verified']);self.assertFalse(result['input_submitted'])
        self.receive(p) # Exact same ACK is idempotent; no dispatch is replayed.
        self.assertEqual(self.row['result'],p)

    def test_foreign_uuid_nonce_scope_header_and_layout_reject_and_retain(self):
        mutations=[lambda p:p.update(operation='panel'),lambda p:p.update(mutation_started=False),
            lambda p:p.update(cas_request_id='c'*32),lambda p:p['client'].update(scope='native-cas-client'),
            lambda p:p['client'].update(appearance_written=True),lambda p:p['client'].update(catalogs=[]),
            lambda p:p['client']['navigation_identity'].update(peer_nonce='c'*64),
            lambda p:p['client']['navigation_identity'].update(request_id='c'*32),
            lambda p:p['client'].update(menu_state=999),lambda p:p['client'].update(requested_menu_state=999),
            lambda p:p['client'].update(panel_visible=False),lambda p:p['client']['sim'].update(simId='13'),
            lambda p:p['client']['sim'].update(occultType=True),lambda p:p['client']['form_strip'].update(gesture_pending=True),
            lambda p:p['client']['outfit'].update(outfit_index=False),lambda p:p['client']['card_layout'].update(scale=float('nan')),
            lambda p:p['client']['card_layout'].update(available=1),lambda p:p['client']['card_layout'].update(columns=33),
            lambda p:p['client']['card_layout'].update(extra='foreign')]
        for mutate in mutations:
            p=self.packet();mutate(p)
            with self.subTest(packet=p),self.assertRaises((ValueError,KeyError,TypeError)):
                self.receive(p)
            self.assertEqual(self.row['state'],'pending')

    def test_all_context_drifts_fail_even_when_header_is_consistently_rewritten(self):
        values={'sim_id':'13','household_id':'35','owner_id':'alien/second','native_kind':4,'shell_kind':2,
            'native_mask':7,'native_generation':'92','session':4,'layer':1,'outfit_type':1,'outfit_index':1}
        for key,value in values.items():
            p=self.packet();p['client']['navigation_identity']['after'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.receive(p)
            self.assertEqual(self.row['state'],'pending')
        for key,value in (('owner_id','alien/second'),('native_generation','92')):
            p=self.packet()
            for side in ('before','after'):p['client']['navigation_identity'][side][key]=value
            with self.subTest(forged=key),self.assertRaisesRegex(ValueError,'claimed native cursor'):self.receive(p)

    def test_wrong_scope_never_seeds_full_status_or_appearance_paths(self):
        for operation in ('status','panel','select','undo','accept','form-owner-select','catalog-state'):
            p=self.packet();self.row['request']={'operation':operation};p['operation']=operation
            with self.subTest(operation=operation),self.assertRaises((ValueError,KeyError)):
                self.receive(p)

    def test_admission_requires_disposable_guard_and_fresh_exact_sim_peer(self):
        host._RECORDS.clear()
        with patch('apex_core.test_driver.guard',return_value=None) as guard:
            result=host.submit('12',self.request,clock=lambda:0,backend=object())
        self.assertEqual(guard.call_count,1)
        wire=next(iter(host._RECORDS.values()))['wire']
        self.assertEqual(wire.split('|')[2:],[self.request['operation'],str(self.state),'0','0',''])
        self.assertNotIn('fixture',wire)
        host._RECORDS.clear()
        with patch('apex_core.test_driver.guard',side_effect=ValueError('not disposable')):
            with self.assertRaisesRegex(ValueError,'not disposable'):host.submit('12',self.request,clock=lambda:0,backend=object())
        self.assertEqual(len(host._RECORDS),0)
        with patch('apex_core.test_driver.guard',return_value=None):
            with self.assertRaisesRegex(ValueError,'fresh exact-Sim'):host.submit('12',self.request,clock=lambda:4,backend=object())
        self.assertEqual(len(host._RECORDS),0)

    def test_original_uuid_uncertainty_blocks_a_second_navigation(self):
        with patch('apex_core.test_driver.guard',return_value=None):
            with self.assertRaisesRegex(ValueError,'unresolved'):host.submit('12',self.request,clock=lambda:0,backend=object())
        self.assertEqual(list(host._RECORDS),[self.rid]);self.assertEqual(host.result(self.rid)['outcome'],'pending-client')

    def test_existing_full_panel_wire_unchanged_and_opt_in_schema_is_exact(self):
        _,wire=host.envelope('12',{'operation':'panel','panel':'hair'})
        self.assertEqual(wire.split('|')[2:],['panel',str(self.state),'0','0',''])
        for extra in ('delay','eval','data_id','full_diagnostics'):
            with self.subTest(extra=extra),self.assertRaises(ValueError):host.envelope('12',dict(self.request,**{extra:True}))

    def test_unavailable_layout_is_explicit_and_bounded(self):
        p=self.packet();p['client']['card_layout']={'query':'not-available-current-panel','available':False}
        self.receive(p);self.assertEqual(self.row['state'],'completed')


class SourceIntegration(unittest.TestCase):
    def test_exact_native_panel_calls_and_500ms_order_preserved(self):
        source=(ROOT/'Source/CASUi/semantic_methods.as').read_text(encoding='utf-8')
        block=source.split('} else if(operation=="panel" || operation=="panel-navigation") {',1)[1].split('} else if',1)[0]
        block=re.sub(r'//[^\n]*','',block)
        self.assertEqual(re.sub(r'\s+','',block),re.sub(r'\s+','','''
            reply.mutation_started=true;
            HandleContextMenuSetMenuState({menuState:state,skipAnim:true,setZoomState:true});
            CommunicationManager.SendUIMessage("CASChangeMenuState",state);
        '''))
        self.assertIn('apexTimer=new flash.utils.Timer(500);',source)
        self.assertIn('apexReadbackTick=int(apexTimer.currentCount)+1;',source)
        self.assertIn('if(operation!="panel-navigation" && reply.mutation_started',source)

    def test_navigation_scope_does_not_enter_thin_metadata_equal_menu_allowlist(self):
        self.assertNotIn('panel-navigation',host._CATALOG_READBACK_OPERATIONS)
        snapshot=source_method('ApexPanelNavigationSnapshot','before,after,requested')
        for banned in ('GetAllDisplayObjectCells','getBounds','GetDataFeed','ApexSnapshot','ApexCatalogStatus'):
            self.assertNotIn(banned+'(',snapshot)


class CLIIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import cas_client
        import apex_cli
        cls.client=cas_client;cls.cli=apex_cli

    def args(self,*extra):
        args=self.cli.parser().parse_args(['cas','panel','--state','private.json','--sim-id','12','--panel','hair',*extra])
        args.seconds=2
        return args

    def test_opt_in_transmits_exact_schema_and_observes_same_uuid_once(self):
        args=self.args('--minimal-navigation');calls=[]
        def request(state,action,sim_id=None,value=None):
            calls.append((action,value))
            if action=='cas_ui_request':return {'cas_request_id':'b'*32}
            self.assertEqual(action,'cas_ui_result');self.assertEqual(value,'b'*32)
            return {'ok':True,'client':{'scope':'native-cas-navigation-client'}}
        with patch.dict(sys.modules,{'apex_core.cas_ui':host}),patch('reusable_profile.load',return_value=(None,{'token':'fixture'},None,None)):
            result=self.client._execute(args,request)
        self.assertTrue(result['ok']);self.assertEqual(len(calls),2)
        self.assertEqual(json.loads(calls[0][1]),{'operation':'panel-navigation','panel':'hair','test_token':'fixture'})

    def test_full_default_and_explicit_non_panel_rejection(self):
        args=self.args();calls=[]
        def request(state,action,sim_id=None,value=None):
            calls.append((action,value))
            return {'cas_request_id':'b'*32} if action=='cas_ui_request' else {'ok':True}
        with patch.dict(sys.modules,{'apex_core.cas_ui':host}):self.client._execute(args,request)
        self.assertEqual(json.loads(calls[0][1]),{'operation':'panel','panel':'hair'})
        for operation in ('status','result','panels','select'):
            args=self.args('--minimal-navigation');args.operation=operation
            with self.subTest(operation=operation),self.assertRaisesRegex(ValueError,'panel-only'):
                self.client._execute(args,lambda *a,**k:self.fail('No request may be made'))


if __name__=='__main__':unittest.main()
