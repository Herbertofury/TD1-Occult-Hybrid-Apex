"""Execute the real inventory frame/read logic against re-entrant native doubles.

Only Flash's XML constant-name enumeration is replaced by an empty name table;
owner checks, service requests, response parsing and publication remain actual AS.
"""
from pathlib import Path
import json,re,shutil,subprocess,sys,unittest
HOME=Path(__file__).resolve().parents[1]
ROOT=next(parent for parent in Path(__file__).resolve().parents if (parent/'tools/cas_grid_transaction.py').is_file())
sys.path.insert(0,str(ROOT/'tests'))
from test_cas_card_geometry import javascript_function
SOURCE=HOME/'Source/CASUi/catalog_workspace_methods.as'


def methods():
    result=''
    for name,args in [('ApexCatalogFrame','event=null'),('ApexCatalogReadEquipped',''),('ApexCatalogInvalidate','value=null')]:
        code=javascript_function(name,args,source=SOURCE)
        code=re.sub(r'catch\((\w+):(?:Error|\*)\)',r'catch(\1)',code)
        code=code.replace('panel is ClothingPanel','panel instanceof ClothingPanel')
        code=re.sub(r'([a-zA-Z_]\w*\.\w+) is int',r'isInt(\1)',code)
        if name=='ApexCatalogReadEquipped':
            start=code.index('var names={};var definition=flash.utils.describeType(CASBodyType);')
            end=code.index('var rows=[];',start)
            assert 'constant.@name' in code[start:end]
            code=code[:start]+'var names={};\n'+code[end:]
        result+=code
    return result


@unittest.skipUnless(shutil.which('node'),'Node required for executing the actual AS inventory boundary')
class EquippedOwnerRefreshTests(unittest.TestCase):
    def execute(self,code):
        result=subprocess.run(['node','-'],input=BOOT+methods()+code,text=True,encoding='utf-8',
                              capture_output=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_changed_member_clears_old_rows_waits_for_binding_then_refreshes_once(self):
        self.execute('''
apexFormsDesiredId='native/2';ApexCatalogFrame();
assert.deepEqual(apexCatalogItems,[]);assert.equal(apexCatalogSlot,null);assert.equal(apexCatalogPage,0);
assert.equal(apexCatalogContext,'');assert.equal(apexCatalogDirty,true);assert.equal(nativeCalls.length,0);
assert.ok(apexCatalogError.startsWith('Updating equipped items'));
for(let i=0;i<50;i++)ApexCatalogFrame();assert.equal(nativeCalls.length,0);assert.equal(slotCalls,0);
apexFormsDesiredId='';ApexCatalogFrame();assert.equal(nativeCalls.length,1);assert.equal(slotCalls,2);
assert.equal(apexCatalogContext,'102|native/2');assert.equal(apexCatalogError,'');assert.equal(apexCatalogDirty,false);
assert.equal(apexCatalogItems.length,1);assert.equal(apexCatalogItems[0].part_key,'0x0000000000000123');
for(let i=0;i<200;i++)ApexCatalogFrame();assert.equal(nativeCalls.length,1);assert.equal(slotCalls,2);
assert.equal(nativeGrid.phase,'done');assert.equal(nativeGrid.published,180);assert.equal(removed,0);
''')

    def test_every_unsettled_owner_and_typed_command_gate_defers_all_game_reads(self):
        cases=[('apexPendingFields=["pending"]','apexPendingFields=null'),
               ('apexReceiving=true','apexReceiving=false'),('apexPendingPhase=9','apexPendingPhase=0'),
               ('mCurrSimInfo=null',"mCurrSimInfo={simId:'102'}"),
               ("apexBoundSim='foreign'","apexBoundSim='102'"),
               ("apexNativeChannel=''","apexNativeChannel='55'"),
               ('apexNativeConnected=false','apexNativeConnected=true'),
               ("apexFormsNativeState='waiting'","apexFormsNativeState='bound'"),
               ("apexFormsSelectedId=''","apexFormsSelectedId='native/2'"),
               ("apexFormsNativeGeneration=''","apexFormsNativeGeneration='43'"),
               ('apexOwnerSession=0','apexOwnerSession=7'),('apexFormsApplying=true','apexFormsApplying=false'),
               ("apexFormsDesiredId='native/4'","apexFormsDesiredId=''"),
               ('apexFormsNativeIntent={}','apexFormsNativeIntent=null'),
               ('apexFormsIntent={}','apexFormsIntent=null'),
               ('apexMoleculeIntent={}','apexMoleculeIntent=null'),
               ('apexPairIntent={}','apexPairIntent=null')]
        for blocked,ready in cases:
            with self.subTest(blocked=blocked):
                self.execute(blocked+''';for(let i=0;i<20;i++)ApexCatalogFrame();
assert.equal(nativeCalls.length,0);assert.equal(slotCalls,0);assert.deepEqual(apexCatalogItems,[]);
'''+ready+''';ApexCatalogFrame();assert.equal(nativeCalls.length,1);assert.equal(slotCalls,2);
for(let i=0;i<20;i++)ApexCatalogFrame();assert.equal(nativeCalls.length,1);
''')

    def test_closed_text_panel_does_not_read_or_scan_any_switched_member(self):
        self.execute('''
apexCatalogUi.visible=false;
for(let i=0;i<100;i++){mCurrSimInfo={simId:String(200+i)};apexBoundSim=String(200+i);apexNativeChannel=String(300+i);ApexCatalogFrame();}
assert.equal(nativeCalls.length,0);assert.equal(slotCalls,0);assert.equal(draws.length,0);
apexCatalogUi.visible=true;ApexCatalogFrame();assert.equal(nativeCalls.length,1);
assert.equal(apexCatalogContext,'299|native/2');assert.equal(apexCatalogError,'');
''')

    def test_one_failure_does_not_retry_on_every_frame_but_a_new_owner_gets_one_attempt(self):
        self.execute('''
nativeError='Native model is not available';ApexCatalogFrame();
assert.equal(nativeCalls.length,1);assert.equal(apexCatalogDirty,false);assert.equal(apexCatalogError,nativeError);
for(let i=0;i<100;i++)ApexCatalogFrame();assert.equal(nativeCalls.length,1);
mCurrSimInfo={simId:'103'};apexBoundSim='103';ApexCatalogFrame();assert.equal(nativeCalls.length,2);
for(let i=0;i<100;i++)ApexCatalogFrame();assert.equal(nativeCalls.length,2);
nativeError='';ApexCatalogInvalidate();ApexCatalogFrame();assert.equal(nativeCalls.length,3);
assert.equal(apexCatalogContext,'103|native/2');assert.equal(apexCatalogError,'');
''')

    def test_rapid_unbound_members_coalesce_to_the_final_exact_owner(self):
        self.execute('''
apexFormsNativeState='waiting';
for(let i=0;i<40;i++){mCurrSimInfo={simId:String(200+i)};apexBoundSim=String(200+i);ApexCatalogFrame();}
assert.equal(nativeCalls.length,0);assert.equal(slotCalls,0);assert.deepEqual(apexCatalogItems,[]);
apexFormsNativeState='bound';ApexCatalogFrame();assert.equal(nativeCalls.length,1);
assert.equal(apexCatalogContext,'239|native/2');
''')

    def test_header_cannot_adopt_another_member_form_outfit_or_generation(self):
        base=['EQUIPPED','102','native/2','0','1','43']
        for index,value in [(0,'WRONG'),(1,'103'),(2,'native/4'),(3,'1'),(4,'2'),(5,'44'),(5,'043')]:
            header=base[:];header[index]=value
            with self.subTest(index=index,value=value):
                self.execute('forcedResponse='+json.dumps('|'.join(header)+'\n0x0000000000000123|2|0|0')+''';
ApexCatalogFrame();assert.equal(nativeCalls.length,1);assert.equal(slotCalls,1);
assert.equal(apexCatalogContext,'');assert.deepEqual(apexCatalogItems,[]);assert.equal(apexCatalogDirty,false);
for(let i=0;i<100;i++)ApexCatalogFrame();assert.equal(nativeCalls.length,1);
''')

    def test_reentrant_mutations_at_each_native_boundary_never_publish_old_or_new_mixed_rows(self):
        changes=["mCurrSimInfo={simId:'103'}", "apexBoundSim='103'", "apexFormsSelectedId='native/4'",
                 "apexNativeChannel='other'", "apexFormsNativeGeneration='44'", 'apexOwnerSession++',
                 "apexFormsNativeState='waiting'", "apexFormsDesiredId='native/4'", 'apexFormsApplying=true',
                 'slot.outfit_index=2','apexFormsNativeIntent={}', 'apexFormsIntent={}',
                 'apexMoleculeIntent={}', 'apexPairIntent={}', 'apexPendingFields=["new-command"]',
                 'apexPendingPhase=9','apexReceiving=true','apexNativeConnected=false',
                 'apexFormsLocalCatalog=true','apexDisconnected=true']
        for boundary in ('firstSlot','native','lastSlot'):
            for change in changes:
                with self.subTest(boundary=boundary,change=change):
                    if boundary=='firstSlot' and change=='slot.outfit_index=2':
                        # The initial getter defines this requested read's outfit.
                        # A coherent new initial slot is valid; only later drift refuses.
                        self.execute('onfirstSlot=()=>{slot.outfit_index=2;};'+'''
ApexCatalogFrame();assert.equal(apexCatalogContext,'102|native/2');assert.equal(apexCatalogSlot.index,2);
assert.deepEqual(nativeCalls,['EQUIPPED|55|0|2']);assert.equal(slotCalls,2);
''')
                        continue
                    self.execute('on'+boundary+'=()=>{'+change+';};'+'''
ApexCatalogFrame();assert.equal(apexCatalogContext,'');assert.deepEqual(apexCatalogItems,[]);
assert.equal(apexCatalogDirty,false);assert.equal(removed,0);assert.equal(restored,0);
''')

    def test_same_owner_invalidation_during_read_refuses_without_an_idle_retry_loop(self):
        self.execute('''
onnative=()=>ApexCatalogInvalidate();ApexCatalogFrame();assert.equal(nativeCalls.length,1);
assert.deepEqual(apexCatalogItems,[]);assert.equal(apexCatalogDirty,false);assert.equal(apexEquippedDirty,true);
for(let i=0;i<100;i++)ApexCatalogFrame();assert.equal(nativeCalls.length,1);
onnative=null;ApexCatalogInvalidate();ApexCatalogFrame();assert.equal(nativeCalls.length,2);
assert.equal(apexCatalogContext,'102|native/2');assert.equal(apexCatalogError,'');
''')

    def test_complete_coherent_new_owner_is_not_blessed_during_an_old_read(self):
        self.execute('''
onnative=()=>{mCurrSimInfo={simId:'103'};apexBoundSim='103';apexFormsSelectedId='native/4';apexNativeChannel='66';apexOwnerSession=8;};
ApexCatalogFrame();assert.equal(nativeCalls.length,1);assert.deepEqual(apexCatalogItems,[]);assert.equal(apexCatalogContext,'');
onnative=null;ApexCatalogFrame();assert.equal(nativeCalls.length,2);assert.equal(apexCatalogContext,'103|native/4');
for(let i=0;i<100;i++)ApexCatalogFrame();assert.equal(nativeCalls.length,2);
''')

    def test_local_native_transport_and_empty_equipped_inventory_remain_supported(self):
        self.execute('''
apexNativeConnected=false;apexFormsLocalCatalog=true;responseRows='';ApexCatalogFrame();
assert.equal(nativeCalls.length,1);assert.equal(slotCalls,2);assert.equal(apexCatalogError,'');
assert.equal(apexCatalogContext,'102|native/2');assert.deepEqual(apexCatalogItems,[]);
for(let i=0;i<100;i++)ApexCatalogFrame();assert.equal(nativeCalls.length,1);
''')

    def test_explicit_typed_read_retains_its_original_command_phase_and_identity(self):
        self.execute('''
const original=['original-command','102','catalog-open'];apexPendingFields=original;apexPendingPhase=4;
ApexCatalogReadEquipped();assert.equal(nativeCalls.length,1);assert.equal(slotCalls,2);
assert.equal(apexPendingFields,original);assert.equal(apexPendingPhase,4);assert.equal(apexReceiving,false);
assert.equal(apexCatalogContext,'102|native/2');assert.equal(apexCatalogError,'');
''')

    def test_unknown_slot_and_part_types_remain_strict_and_no_appearance_write_is_added(self):
        for changed in ('slot=null','slot.outfit_type="0"','slot.outfit_index=1.5'):
            with self.subTest(changed=changed):
                self.execute(changed+''';ApexCatalogFrame();assert.equal(nativeCalls.length,0);
assert.equal(apexCatalogContext,'');assert.deepEqual(apexCatalogItems,[]);
''')
        for row in ('0x0000000000000123|bad|0|0','not-a-part|2|0|0'):
            self.execute('responseRows='+json.dumps('\n'+row)+''';ApexCatalogFrame();
assert.equal(apexCatalogContext,'');assert.deepEqual(apexCatalogItems,[]);assert.equal(removed,0);
''')

    def test_private_owned_state_is_initialized_and_disposed_and_no_per_frame_native_scan_exists(self):
        source=SOURCE.read_text(encoding='utf-8')
        self.assertEqual(source.count('private var apexCatalogObservedOwner:String'),1)
        initialize=source.split('private function ApexCatalogInitialize(',1)[1].split('private function ApexCatalogValidate(',1)[0]
        dispose=source.split('private function ApexCatalogDispose(',1)[1].split('private function ApexCatalogOpen(',1)[0]
        self.assertIn('apexCatalogObservedOwner="";',initialize)
        self.assertIn('apexCatalogObservedOwner="";',dispose)
        frame=source.split('private function ApexCatalogFrame(',1)[1].split('private function ApexCatalogClearEffects(',1)[0]
        self.assertNotIn('CallGameService(',frame)
        self.assertNotIn('ApexNativeExchange(',frame)
        self.assertNotIn('SetSimOccult',source)


BOOT=r'''
const assert=require('node:assert/strict');function int(n){return Math.trunc(n);}int.MAX_VALUE=2147483647;
function isInt(n){return typeof n==='number'&&Number.isInteger(n)&&n>=-2147483648&&n<=2147483647;}
class ClothingPanel{}const flash={utils:{getTimer(){return 0;}}},stage={stageWidth:2560};
var mCurrentPanel=null,mcClothingPanel={},mCurrState=0,mCurrSimInfo={simId:'102'};
var apexCatalogPrefs={},apexDisconnected=false,apexCatalogFrameCells=null,apexCatalogEffects=[],apexCatalogHeaderSignature='';
var apexCatalogUi={visible:true,width:320,x:2220,y:75},apexCatalogTab='items';
var apexCatalogContext='101|alien/alien',apexCatalogObservedOwner='101|alien/alien|54|6',apexCatalogItems=[{part_key:'OLD'}];
var apexCatalogSlot={category:1,index:0},apexCatalogPage=3,apexCatalogDirty=false,apexCatalogError='';
var apexPendingFields=null,apexReceiving=false,apexPendingPhase=0,apexCatalogIntent=null,apexCatalogGrid=null;
var apexCatalogDisplayFaults=null,apexCatalogStyleSignature='',apexEquippedDirty=false;
var apexCatalogFrameTiming={samples:0,total_ms:0,max_ms:0,over_1ms:0};
var apexBoundSim='102',apexNativeChannel='55',apexNativeConnected=true,apexFormsLocalCatalog=false;
var apexFormsNativeState='bound',apexFormsSelectedId='native/2',apexFormsNativeGeneration='43',apexOwnerSession=7;
var apexFormsApplying=false,apexFormsDesiredId='',apexFormsNativeIntent=null,apexFormsIntent=null,apexMoleculeIntent=null,apexPairIntent=null;
var nativeCalls=[],slotCalls=0,draws=[],removed=0,restored=0,nativeError='',forcedResponse=null;
var onfirstSlot=null,onlastSlot=null,onnative=null,slot={outfit_type:0,outfit_index:1};
var responseRows='\n0x0000000000000123|2|0|0';
var nativeGrid={phase:'done',published:180};
function ApexCatalogPanelKind(){return '';}
function ApexPanelsFrame(){}function ApexCatalogApplyBinding(){}function ApexColumnsFrame(){}function ApexEquippedFrame(){}
function ApexSearchFrame(){}function ApexCompanionFrame(){}function ApexCatalogKeyboardFrame(){}function ApexCatalogClearEffects(){}
function ApexCardRestore(){restored++;}function removeEventListener(){removed++;}
function ApexCatalogDraw(){draws.push(JSON.parse(JSON.stringify({items:apexCatalogItems,context:apexCatalogContext,error:apexCatalogError})));}
function ApexCatalogMenu(n){return n+100;}function ApexClone(o){return o===null?null:JSON.parse(JSON.stringify(o));}
const CommunicationManager={CallGameService(name){assert.equal(name,'CasGetCurrSimOutfitSlot');slotCalls++;
    const callback=slotCalls%2===1?onfirstSlot:onlastSlot;if(callback)callback();return slot;}};
function ApexNativeExchange(message){nativeCalls.push(message);assert.ok(message.startsWith('EQUIPPED|'));
    if(onnative)onnative();if(nativeError)throw Error(nativeError);if(forcedResponse!==null)return forcedResponse;
    return ['EQUIPPED',String(mCurrSimInfo.simId),apexFormsSelectedId,String(slot.outfit_type),String(slot.outfit_index),apexFormsNativeGeneration].join('|')+responseRows;}
'''

if __name__=='__main__':unittest.main()
