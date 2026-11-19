"""Execute the exact staged native-input/readback/helper bodies, never the game."""
from pathlib import Path
import ast,re,sys,subprocess,unittest,os
ROOT=next(p for p in Path(__file__).resolve().parents if(p/'tools/dbpf_build.py').is_file())
HERE=Path(os.environ.get('APEX_UNCONSUMED_SOURCE_ROOT',ROOT))
sys.path[:0]=[str(ROOT/'tools')]
import cas_grid_pool as pool

def method(source,name,parameters):
 a,b=pool.method_extent(source,name);raw=source[a:b];body=raw.split('{',1)[1].rsplit('}',1)[0]
 body=re.sub(r'\b(var\s+\w+)\s*:\s*[\w.*]+',r'\1',body)
 body=re.sub(r'\s+as\s+[\w.]+','',body)
 body=re.sub(r'([\w.\[\]]+)\s+is\s+(int|String|Number|Boolean|Array)',r'isType(\1,"\2")',body)
 body=re.sub(r'catch\((\w+)\s*:\s*Error\)',r'catch(\1)',body)
 body=re.sub(r'for each\(([^)]+) in ([^)]+)\)',r'for(\1 of \2)',body)
 return 'function '+name+'('+parameters+'){'+body+'}\n'

class UnconsumedAsTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  tree=ast.parse((ROOT/'tests/test_cas_keyboard_publication.py').read_text(encoding='utf-8'))
  execute=next(n for n in ast.walk(tree)if isinstance(n,ast.FunctionDef)and n.name=='execute')
  cls.boot=next(ast.literal_eval(n.value) for n in execute.body if isinstance(n,ast.Assign)and isinstance(n.value,(ast.Str,ast.Constant)))
  cls.source=(HERE/'Source/CASUi/catalog_unconsumed_consumer_methods.as').read_text(encoding='utf-8')+'\n'+(HERE/'Source/CASUi/catalog_unconsumed_methods.as').read_text(encoding='utf-8')
  for name,file in [('ApexCatalogKeyboardInput','catalog_keyboard_methods.as'),('ApexCatalogKeyboardVisibility','catalog_keyboard_methods.as'),('ApexCatalogKeyboardScopeEqual','catalog_keyboard_methods.as'),('ApexCatalogKeyboardPublication','catalog_keyboard_methods.as'),('ApexCatalogKeyboardPublicationReady','catalog_keyboard_methods.as'),('ApexOwnerSimRow','semantic_methods.as'),('ApexCatalogReadbackOnly','semantic_methods.as'),('ApexCatalogReadbackContext','semantic_methods.as')]:
   raw=(ROOT/'Source/CASUi'/file).read_text(encoding='utf-8');a,b=pool.method_extent(raw,name);cls.source+='\n'+raw[a:b]
  cls.code=cls.boot+'\napexCatalogGrid.grid=grid;\n'
  functions=[('ApexCatalogKeyboardFrame','controlled=false'),('ApexCatalogKeyboardCommand','value'),('ApexCatalogKeyDown','event'),
    ('ApexCatalogKeyboardInput','value'),('ApexCatalogKeyboardVisibility',''),('ApexCatalogKeyboardScopeEqual','left,right'),
    ('ApexCatalogKeyboardPublication','before'),('ApexCatalogKeyboardPublicationReady','held'),
    ('ApexOwnerSimRow','raw'),('ApexCatalogReadbackOnly','operation'),('ApexCatalogReadbackContext','selected'),
    ('ApexReadback',''),('ApexCatalogUnconsumedMark','code,panel,grid,lease,route'),
    ('ApexCatalogUnconsumedBound','held,fields,context,reply'),('ApexCatalogUnconsumedCurrent','held,fields,context,reply'),('ApexCatalogUnconsumedReply','fields,context,reply')]
  cls.code+='\n'.join(method(cls.source,n,p)for n,p in functions)
  cls.code+="\nfunction readback(){apexTimer.currentCount++;ApexReadback();}\napexPendingContext.keyboard_before=ApexCatalogReadbackContext(ApexOwnerSimRow(fresh));\n"
 def case(self,body):
  proc=subprocess.run(['node','-'],input=self.code+body,text=True,capture_output=True,timeout=15)
  self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
 def start(self):
  return "apexPendingFields[2]='catalog-input';apexPendingFields[6]='home,1';apexPendingReply.operation='catalog-input';pending=true;let original;try{ApexCatalogKeyboardInput('home,1');}catch(e){original=e;}assert.match(String(original),/CAS key not consumed/);assert.ok(apexPendingContext.keyboard_unconsumed);assert.equal(scrolls,0);assert.equal(dispatches,0);"
 def test_actual_loading_rejection_emits_complete_distinct_failure_once_without_full_snapshot(self):
  self.case(self.start()+"readback();assert.equal(acks.length,1);const ack=acks[0],p=ack.navigation_unconsumed;assert.equal(ack.ok,false);assert.equal(ack.message,'CAS catalog navigation rejected before consumption: catalog is still loading');assert.equal(p.emitter,'apex-keyboard-loading-before-queue-v1');assert.deepEqual(p.before,p.after);assert.equal(p.before.native_kind,2);assert.equal(p.before.shell_kind,4);assert.equal(p.key_listener_invoked,true);assert.equal(p.navigation_dispatched,false);assert.equal(p.appearance_written,false);assert.equal(p.receipt_present,false);assert.equal(p.key_code,36);assert.equal(p.requested_key,'home');assert.equal(ack.navigation_publication,undefined);assert.equal(ack.client,undefined);assert.equal(snapshots,0);readback();assert.equal(acks.length,1);assert.equal(scrolls,0);assert.equal(dispatches,0);")
 def test_every_request_peer_native_owner_outfit_ui_identity_change_refuses_typed_settlement(self):
  changes=["apexNonce='f'.repeat(64);","apexClaimNonce='f'.repeat(64);","stage={};","apexNativeChannel='8';",
   "fresh={...fresh,simId:'13'};","fresh={...fresh,householdId:'35'};","apexFormsNativeGeneration='92';",
   'apexOwnerSession++;','mCurrState++;','outfit={outfit_type:0,outfit_index:1};',"apexFormsSelectedId='named/other';",
   'lease.generation++;','apexCatalogGrid.lease={...lease};','feed={...feed};','list.mGridLayout={...grid};grid=list.mGridLayout;',
   'apexKeyReceived++;','apexKeyQueue=[{key:36}];','apexKeyReceipt={key:36};','apexKeyInjecting=true;']
  for change in changes:
   with self.subTest(change=change):self.case(self.start()+change+"readback();assert.equal(acks.length,1);assert.equal(acks[0].navigation_unconsumed,undefined);assert.equal(scrolls,0);assert.equal(dispatches,0);")
 def test_consuming_phase_invalidates_witness_before_any_native_navigation_callback(self):
  self.case(self.start()+"pending=false;apexKeyQueue=[{key:36,sim:'12',owner:'active/2',panel:mCurrentPanel,state:mCurrState,feed,grid,lease,lease_generation:lease.generation,native_generation:lease.native_generation,grid_generation:generation,grid_revision:revision,focused_index:-1,focused_item:null,route:'shared-keyboard-handler'}];apexKeyIntent=36;grid.GetDataAtIndex=()=>{assert.equal(apexPendingContext.keyboard_unconsumed,null);throw Error('native callback failed after consumption began');};ApexCatalogKeyboardFrame(true);assert.equal(apexPendingContext.keyboard_unconsumed,null);readback();assert.equal(acks[0].navigation_unconsumed,undefined);")
 def test_readback_scope_service_reentry_is_checked_again_before_failure_packet(self):
  self.case(self.start()+"const call=CommunicationManager.CallGameService;CommunicationManager.CallGameService=function(name){const r=call(name);if(name==='CasGetCurrSimOutfitSlot')apexCatalogGrid.lease={...lease};return r;};readback();assert.equal(acks.length,1);assert.equal(acks[0].navigation_unconsumed,undefined);assert.equal(scrolls,0);")
 def test_no_generic_or_real_player_rejection_can_mint_prequeue_witness(self):
  self.case("pending=true;apexPendingFields[2]='catalog-input';apexPendingFields[6]='home,1';apexPendingReply.operation='catalog-input';const e=new flash.events.KeyboardEvent();e.keyCode=36;ApexCatalogKeyDown(e);assert.equal(apexPendingContext.keyboard_unconsumed,undefined);assert.equal(apexKeyRejected,'command busy');assert.equal(scrolls,0);")
 def test_enter_and_unknown_route_never_create_unconsumed_witness(self):
  self.case("for(const [code,route,value]of[[13,'shared-keyboard-handler-before-queue','enter,1'],[36,'guessed','home,1']]){apexPendingFields[2]='catalog-input';apexPendingFields[6]=value;apexPendingReply.operation='catalog-input';apexKeyInjecting=true;ApexCatalogUnconsumedMark(code,mCurrentPanel,grid,lease,route);assert.equal(apexPendingContext.keyboard_unconsumed,undefined);}assert.equal(scrolls,0);")
 def test_semantic_loading_before_queue_uses_false_listener_provenance(self):
  self.case("apexPendingFields[6]='home';pending=true;try{ApexCatalogKeyboardCommand('home');}catch(e){}assert.ok(apexPendingContext.keyboard_unconsumed);readback();assert.equal(acks.length,1);const p=acks[0].navigation_unconsumed;assert.equal(p.key_listener_invoked,false);assert.equal(p.focus_requested,false);assert.equal(p.source_route,'semantic-navigation-before-queue');assert.equal(scrolls,0);assert.equal(dispatches,0);")
 def test_actual_getter_detach_or_grid_replacement_is_refused_in_same_scope(self):
  for change in ["grid.GetDataFeed=()=>{mCurrentPanel.stage=null;return feed;};",
                 "list.GetGridView=()=>{list.mGridLayout={...grid};return view;};"]:
   with self.subTest(change=change):self.case(self.start()+change+"assert.equal(ApexCatalogUnconsumedCurrent(apexPendingContext.keyboard_unconsumed,apexPendingFields,apexPendingContext,apexPendingReply),false);readback();assert.equal(acks[0].navigation_unconsumed,undefined);assert.equal(scrolls,0);assert.equal(dispatches,0);")
 def test_marker_getter_reentry_never_writes_a_replacement_request_context(self):
  self.case("apexPendingFields[2]='catalog-input';apexPendingFields[6]='home,1';apexPendingReply.operation='catalog-input';pending=true;const original=apexPendingContext,foreign={};let calls=0;const get=list.GetGridView;list.GetGridView=()=>{calls++;if(calls===2)apexPendingContext=foreign;return get();};try{ApexCatalogKeyboardInput('home,1');}catch(e){}assert.equal(foreign.keyboard_unconsumed,undefined);assert.equal(original.keyboard_unconsumed,undefined);assert.equal(scrolls,0);")

if __name__=='__main__':unittest.main()
