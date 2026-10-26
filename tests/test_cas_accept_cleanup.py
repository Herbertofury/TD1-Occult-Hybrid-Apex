"""Execute the production acceptance cleanup; never call the game/native process."""
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'Source/CASUi/semantic_methods.as'

def method():
    text=SOURCE.read_text(encoding='utf-8')
    body=text.split('private function ApexAccept() : void',1)[1].split('{',1)[1].rsplit('}',1)[0]
    body=re.sub(r'\b(var\s+\w+)\s*:\s*[\w.*]+',r'\1',body)
    body=re.sub(r'([\w.\[\]]+)\s+is\s+(int|String|Number|Boolean|Array)',r'isType(\1,"\2")',body)
    body=re.sub(r'catch\((\w+)\s*:\s*Error\)',r'catch(\1)',body)
    return 'function ApexAccept(){'+body+'}\n'

@unittest.skipUnless(shutil.which('node'),'Node required for actual ActionScript fixture')
class AcceptCleanup(unittest.TestCase):
    def run_as(self,body):
        fixture=r'''
const assert=require('node:assert/strict');const int=x=>Number(x)|0;
function isType(v,t){return t==='Array'?Array.isArray(v):t==='int'?Number.isInteger(v):typeof v===t.toLowerCase();}
var id='b'.repeat(32),nonce='a'.repeat(64),apexPendingFields=[id,'12','accept','0','0','0','34'];
var apexPendingReply={},apexPendingContext={household_id:'34'},apexPendingPhase=6,apexClaimNonce=nonce,apexNonce=nonce;
var apexSocketActive=true,apexDisconnected=false,apexTimer={currentCount:11},apexReadbackTick=10,apexLastReply='';
var apexFormsNativeState='bound',apexFormsSelectedId='alien/first',apexFormsDesiredId='',apexFormsNativeGeneration='91';
var apexFormsIntent=null,apexFormsNativeIntent=null,apexMoleculeIntent=null,apexPairIntent=null,apexFormsApplying=false,apexNativeChannel='7';
var MenuState={NONE:0},CASStateData={TattooMode:true},mCurrState=-2134374344;
var fresh={simId:'12',householdId:'34',occultLayer:0,occultType:4,allOccultTypes:127};
var rendered=2,mode=0,newFamily=false,fromLive=true,genetics=false,names=true,household={},adult=true,profanity=null,saveResult=true;
var cursor='VIEWSTATE|12|alien/first|2|0|bound|91',cursorCalls=0,saveCalls=0,acks=[],events=[],onCleanup=null,afterCleanup=false;
function ApexEncode(value){return JSON.stringify(value);}
function ApexSocketReply(rid,value){acks.push([rid,JSON.parse(value)]);}
function ApexNativeExchange(request){assert.equal(request,'STATE|7');cursorCalls++;return cursor;}
const CASTelemetryExtension={ReportHouseholdSimIDs(){events.push('telemetry');}};
class ExchangeData{constructor(value){assert.equal(value,household);}HouseholdContainsAdults(){return adult;}}
const CommunicationManager={
 CallUIService(name,value){events.push(name);if(name==='IsWidgetVisible'){assert.equal(value,'CASGeneticsPane');return genetics;}
  if(name==='CasApplyNameFields'){assert.equal(value,false);return names;}throw Error('Unexpected UI service '+name);},
 SendUIMessage(name,value){events.push(name);
  if(name==='ShowTransitionScreen'){assert.equal(value.mode,32);return;}
  assert.equal(apexPendingFields,null);assert.equal(apexPendingReply,null);assert.equal(apexPendingContext,null);
  assert.equal(apexPendingPhase,7);assert.equal(apexClaimNonce,'');assert.equal(saveCalls,0);
  if(name==='CASHideCustomizer'){mCurrState=0;CASStateData.TattooMode=false;}
  if(name==='CASResetWingToggle'){afterCleanup=true;if(onCleanup)onCleanup();}},
 CallGameService(name,value){events.push(name);
  if(name==='CASGetSimInfo')return {...fresh};
  if(name==='GetSimOccult')return rendered;
  if(name==='CasGetCASEditMode')return mode;
  if(name==='CasIsNewFamily')return newFamily;
  if(name==='CasIsEnteredFromPlayArea')return {result:fromLive};
  if(name==='CasGetHouseholdExchangeData'){assert.equal(value.bValidateExistingSimTraits,false);return household;}
  if(name==='CASCheckProfanityOnSimNames')return profanity;
  if(name==='SaveAndExitCAS'){saveCalls++;assert.equal(apexPendingFields,null);assert.equal(apexClaimNonce,'');assert.equal(value.bValidateExistingSimTraits,false);return saveResult;}
  throw Error('Unexpected native service '+name);
 }
};
function invoke(){ApexAccept.call({get mCurrState(){return mCurrState;}});}
'''
        result=subprocess.run(['node','-'],input=fixture+method()+body,text=True,capture_output=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_exact_normal_cleanup_order_after_consumption_and_before_validation_save(self):
        self.run_as('''
invoke();assert.equal(saveCalls,1);assert.equal(cursorCalls,2);assert.equal(acks.length,0);
const ordered=['CasApplyNameFields','CASHidePersonalityAndGeneticsPanels','CASHideCustomizer','CASResetGhostToggle','CASResetWingToggle','CasGetHouseholdExchangeData','CASCheckProfanityOnSimNames','SaveAndExitCAS','ShowTransitionScreen'];
for(let i=1;i<ordered.length;i++)assert(events.indexOf(ordered[i-1])<events.indexOf(ordered[i]),ordered[i]);
assert.equal(mCurrState,0);assert.equal(CASStateData.TattooMode,false);assert.equal(apexPendingPhase,7);
invoke();assert.equal(saveCalls,1); // Consumed intent is never replayed.
''')

    def test_native_false_is_original_uuid_terminal_refusal_without_replay(self):
        self.run_as('''
saveResult=false;invoke();assert.equal(saveCalls,1);assert.equal(acks.length,1);assert.equal(acks[0][0],id);
const r=acks[0][1];assert.equal(r.cas_request_id,id);assert.equal(r.commit_attempted,true);assert.equal(r.commit_accepted,false);
assert.equal(r.household_cleanup_attempted,true);assert.equal(r.household_cleanup_verified,true);assert.equal(r.household_finalization_verified,true);
assert.equal(r.ok,false);assert.equal(r.commit_submitted,false);assert.equal(r.ui_transition_verified,false);
invoke();assert.equal(saveCalls,1);assert.equal(acks.length,1);
''')

    def test_unknown_native_outcome_or_exception_is_unresolved_not_retryable(self):
        for setup in ("saveResult=null;", "const call=CommunicationManager.CallGameService;CommunicationManager.CallGameService=(name,value)=>{if(name==='SaveAndExitCAS'){saveCalls++;throw Error('native exception');}return call(name,value);};"):
            with self.subTest(setup=setup):self.run_as(setup+'''
invoke();assert.equal(saveCalls,1);assert.equal(acks.length,1);const r=acks[0][1];
assert.equal(r.commit_outcome,'unresolved');assert.equal(r.commit_accepted,null);assert.equal(apexPendingPhase,7);
invoke();assert.equal(saveCalls,1);
''')

    def test_cleanup_never_runs_before_genetics_and_name_finalization(self):
        for setup in ('genetics=true;','names=false;'):
            with self.subTest(setup=setup):self.run_as(setup+'''
invoke();assert.equal(saveCalls,0);assert.equal(afterCleanup,false);assert.equal(acks.length,1);
assert.equal(acks[0][1].commit_attempted,false);assert.equal(events.includes('CASHideCustomizer'),false);
''')

    def test_final_fresh_identity_and_editor_fences_after_cleanup(self):
        mutations=["fresh.simId='13';","fresh.householdId='35';",'fresh.occultLayer=1;',
            'fresh.occultType=2;','fresh.allOccultTypes=63;','rendered=4;','mode=7;','newFamily=true;',
            'fromLive=false;',"cursor='VIEWSTATE|12|alien/other|2|0|bound|91';",
            "cursor='VIEWSTATE|12|alien/first|2|0|bound|92';",'fresh.occultLayer=false;']
        for mutate in mutations:
            with self.subTest(mutate=mutate):self.run_as('onCleanup=()=>{'+mutate+'''};
invoke();assert.equal(saveCalls,0);assert.equal(acks.length,1);const r=acks[0][1];
assert.equal(r.cas_request_id,id);assert.equal(r.household_cleanup_attempted,true);assert.equal(r.commit_attempted,false);
assert.equal(r.household_cleanup_verified,undefined);assert.equal(r.ok,false);
''')

    def test_widget_retirement_nonce_or_channel_change_refuses_without_foreign_ack(self):
        for mutate,ack_count in (('apexDisconnected=true;',1),('apexSocketActive=false;',0),
                                 ("apexNonce='c'.repeat(64);",0),("apexNativeChannel='8';",1)):
            with self.subTest(mutate=mutate):self.run_as('onCleanup=()=>{'+mutate+'''};
invoke();assert.equal(saveCalls,0);assert.equal(acks.length,'''+str(ack_count)+''');
assert.equal(JSON.parse(apexLastReply).cas_request_id,id);assert.equal(JSON.parse(apexLastReply).commit_attempted,false);
''')

    def test_missing_actual_hide_handler_or_tattoo_exit_refuses(self):
        for mutate in ('mCurrState=-2134374344;','CASStateData.TattooMode=true;',
                       'CASStateData.TattooMode=undefined;','CASStateData.TattooMode=0;'):
            with self.subTest(mutate=mutate):self.run_as('onCleanup=()=>{'+mutate+'''};
invoke();assert.equal(saveCalls,0);assert.equal(acks.length,1);assert.equal(acks[0][1].commit_attempted,false);
''')

    def test_pending_form_identity_refuses_before_cleanup_or_save(self):
        for setup in ("apexFormsDesiredId='vampire/dark';",'apexFormsIntent={};','apexFormsApplying=true;',
                      "cursor='VIEWSTATE|12|alien/other|2|0|bound|91';",'fresh.allOccultTypes="127";'):
            with self.subTest(setup=setup):self.run_as(setup+'''
invoke();assert.equal(saveCalls,0);assert.equal(afterCleanup,false);assert.equal(acks.length,1);assert.equal(acks[0][1].commit_attempted,false);
''')

    def test_no_adult_or_profanity_warning_still_refuses_before_save(self):
        for setup in ('adult=false;',"profanity={simId:'12'};",'household=null;'):
            with self.subTest(setup=setup):self.run_as(setup+'''
invoke();assert.equal(saveCalls,0);assert.equal(afterCleanup,true);assert.equal(acks.length,1);assert.equal(acks[0][1].commit_attempted,false);
''')

    def test_plain_unbound_cas_keeps_authoritative_identity_without_invented_owner(self):
        self.run_as('''
apexFormsNativeState='unavailable';apexFormsSelectedId='';apexNativeChannel='';invoke();
assert.equal(saveCalls,1);assert.equal(cursorCalls,0);assert.equal(afterCleanup,true);
''')

    def test_single_sim_shortcut_remains_exactly_without_enter_game_cleanup(self):
        self.run_as('''
mode=7;delete fresh.occultType;delete fresh.allOccultTypes;invoke();assert.equal(saveCalls,1);assert.equal(cursorCalls,0);
assert.equal(afterCleanup,false);assert.equal(events.includes('GetSimOccult'),false);
assert.equal(events.includes('CasApplyNameFields'),false);assert.equal(events.includes('CasGetHouseholdExchangeData'),false);
assert.equal(events.includes('ShowTransitionScreen'),true);
''')


class BuildContract(unittest.TestCase):
    def test_existing_full_acceptance_contract_and_exact_cleanup_order(self):
        sys.path.insert(0,str(ROOT/'tools'))
        from cas_ui_build import verify_household_acceptance
        text=SOURCE.read_text(encoding='utf-8')
        self.assertTrue(verify_household_acceptance(text))
        body=text.split('private function ApexAccept()',1)[1]
        phases=['apexPendingFields=null; apexPendingReply=null; apexPendingContext=null;',
            'if(int(editMode)==0)', 'CallUIService("CasApplyNameFields",false)',
            'SendUIMessage("CASHidePersonalityAndGeneticsPanels",null)',
            'SendUIMessage("CASHideCustomizer",null)', 'SendUIMessage("CASResetGhostToggle",null)',
            'SendUIMessage("CASResetWingToggle",null)',
            'CallGameService("CasGetHouseholdExchangeData",{bValidateExistingSimTraits:false})',
            'reply.household_cleanup_verified=true;', 'reply.commit_attempted=true;',
            'CallGameService("SaveAndExitCAS",{bValidateExistingSimTraits:false})']
        positions=[body.index(phase) for phase in phases]
        self.assertEqual(positions,sorted(positions))
        self.assertEqual(body.count('CallGameService("SaveAndExitCAS",'),1)
        self.assertNotRegex(body,r'CASStateData\.TattooMode\s*=(?!=)')


if __name__=='__main__':unittest.main()
