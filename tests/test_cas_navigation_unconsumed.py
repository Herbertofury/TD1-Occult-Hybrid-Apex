"""Actual receiver and pure validator, offline and Python 3.7 compatible."""
from pathlib import Path
import ast,copy,hashlib,importlib,json,os,sys,types,unittest
ROOT=next(p for p in Path(__file__).resolve().parents if(p/'tools/dbpf_build.py').is_file())
HERE=Path(os.environ.get('APEX_UNCONSUMED_SOURCE_ROOT',ROOT))
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'Source')]
PACKAGE='_apex_unconsumed_private'
pkg=types.ModuleType(PACKAGE);pkg.__path__=[str(HERE/'Source/apex_core'),str(ROOT/'Source/apex_core')];sys.modules[PACKAGE]=pkg
cas_ui=importlib.import_module(PACKAGE+'.cas_ui')
validator=importlib.import_module(PACKAGE+'.cas_navigation_unconsumed')
from test_cas_slider_postcondition import producer_client

class UnconsumedReceiverTests(unittest.TestCase):
 def setUp(self):
  cas_ui._RECORDS.clear();cas_ui._PEERS.clear()
  self.addCleanup(cas_ui._RECORDS.clear);self.addCleanup(cas_ui._PEERS.clear)
  self.peer=cas_ui.attach_client('12',clock=lambda:0)
  rid=cas_ui.submit('12',{'operation':'status'},clock=lambda:0)['cas_request_id'];cas_ui.poll_client(self.peer,clock=lambda:0)
  client=producer_client();client['sim'].update(allOccultTypes=127,occultType=4);client['form_strip'].update(native_generation='91',session=7)
  cas_ui.receive_socket(self.peer,rid,json.dumps(dict(protocol=1,ok=True,cas_request_id=rid,client=client)),clock=lambda:0)
  self.rid=cas_ui.submit('12',dict(operation='catalog-input',key='home',focus_catalog=True),clock=lambda:0)['cas_request_id']
  cas_ui.poll_client(self.peer,clock=lambda:0);self.row=cas_ui._RECORDS[self.rid]
  scope=copy.deepcopy(self.row['navigation_owner_lease']['context'])
  self.packet=dict(protocol=1,ok=False,cas_request_id=self.rid,operation='catalog-input',scope='native-cas-client',
   mutation_started=False,message=validator.MESSAGE,navigation_unconsumed=dict(protocol=1,emitter=validator.EMITTER,request_id=self.rid,
    peer_nonce=self.peer,before=scope,after=copy.deepcopy(scope),requested_key='home',key_code=36,
    source_route='shared-keyboard-handler-before-queue',rejection='catalog-loading-before-consumption',key_listener_invoked=True,
    navigation_dispatched=False,appearance_written=False,intent=0,queued=0,receipt_present=False,focus_requested=True))
 def test_exact_failure_releases_only_original_slot_without_claiming_input_or_success(self):
  original=copy.deepcopy(self.packet);result=cas_ui.receive_socket(self.peer,self.rid,json.dumps(self.packet),clock=lambda:1)
  self.assertTrue(result['acknowledgement_accepted']);failed=cas_ui.result(self.rid)
  self.assertEqual(failed['cas_request_state'],'failed');self.assertEqual(failed['outcome'],'native-navigation-unconsumed')
  for key in ('ok','mutation_started','input_consumed','retry_submitted','postcondition_verified','ui_transition_verified'):
   self.assertIs(failed[key],False,key)
  self.assertEqual(failed['native_acknowledgement'],original);self.assertEqual(self.packet,original)
  self.assertEqual(failed['native_acknowledgement_sha256'],cas_ui._baseline_hash(original))
  fresh=cas_ui.submit('12',{'operation':'status'},clock=lambda:1);self.assertNotEqual(fresh['cas_request_id'],self.rid)
 def test_same_uuid_packet_is_idempotent_and_changed_duplicate_never_replaces_original_evidence(self):
  raw=json.dumps(self.packet);cas_ui.receive_socket(self.peer,self.rid,raw,clock=lambda:1);before=cas_ui.result(self.rid)
  cas_ui.receive_socket(self.peer,self.rid,raw,clock=lambda:1);self.assertEqual(before,cas_ui.result(self.rid))
  changed=copy.deepcopy(self.packet);changed['navigation_unconsumed']['key_code']=34
  with self.assertRaises(ValueError):cas_ui.receive_socket(self.peer,self.rid,json.dumps(changed),clock=lambda:1)
  self.assertEqual(before,cas_ui.result(self.rid));self.assertEqual(self.row['rejected_acknowledgement'],self.packet)
 def test_every_original_scope_field_before_or_after_mismatch_stays_pending(self):
  for side in ('before','after'):
   for key,value in self.packet['navigation_unconsumed'][side].items():
    original=copy.deepcopy(self.packet);bad=copy.deepcopy(original)
    bad['navigation_unconsumed'][side][key]=value+'x' if isinstance(value,str) else value+1
    with self.subTest(side=side,key=key),self.assertRaises(ValueError):cas_ui.receive_socket(self.peer,self.rid,json.dumps(bad),clock=lambda:1)
    self.assertEqual(self.row['state'],'pending');self.assertEqual(self.row.get('rejected_acknowledgement'),bad)
 def test_unknown_partial_dispatched_or_fake_timeout_packets_never_release_slot(self):
  changes=[lambda p:p.__setitem__('ok',True),lambda p:p.__setitem__('mutation_started',True),lambda p:p.__setitem__('extra',0),
   lambda p:p.__setitem__('message','Native catalog navigation did not publish its focused card before the bounded deadline'),
   lambda p:p.__setitem__('client',{}),lambda p:p.__setitem__('navigation_publication',{}),
   lambda p:p['navigation_unconsumed'].__setitem__('navigation_dispatched',True),
   lambda p:p['navigation_unconsumed'].__setitem__('receipt_present',True),lambda p:p['navigation_unconsumed'].__setitem__('queued',1),
   lambda p:p['navigation_unconsumed'].__setitem__('intent',36),lambda p:p['navigation_unconsumed'].__setitem__('appearance_written',True),
   lambda p:p['navigation_unconsumed'].__setitem__('emitter','guessed'),lambda p:p['navigation_unconsumed'].__setitem__('key_listener_invoked',False),
   lambda p:p['navigation_unconsumed'].__setitem__('focus_requested',False),lambda p:p['navigation_unconsumed'].__setitem__('source_route','semantic-navigation'),
   lambda p:p['navigation_unconsumed'].__setitem__('peer_nonce','f'*64),lambda p:p['navigation_unconsumed'].__setitem__('request_id','0'*32),
   lambda p:p['navigation_unconsumed'].__setitem__('protocol',True),lambda p:p['navigation_unconsumed'].__setitem__('key_code',True),
   lambda p:p['navigation_unconsumed'].__setitem__('queued',False),lambda p:p['navigation_unconsumed'].__setitem__('intent',False),
   lambda p:p['navigation_unconsumed']['after'].__setitem__('session',True),lambda p:p['navigation_unconsumed'].__setitem__('after',None)]
  for i,change in enumerate(changes):
   bad=copy.deepcopy(self.packet);change(bad)
   with self.subTest(index=i),self.assertRaises(ValueError):cas_ui.receive_socket(self.peer,self.rid,json.dumps(bad),clock=lambda:1)
   self.assertEqual(self.row['state'],'pending')
 def test_foreign_transport_lease_delivery_peer_or_missing_context_cannot_settle(self):
  old=copy.deepcopy(self.row)
  for change in [lambda r:r.__setitem__('transport','game-ui-message'),lambda r:r.__setitem__('delivery','queued'),
    lambda r:r.__setitem__('peer','f'*64),lambda r:r.pop('navigation_owner_lease'),
    lambda r:r['navigation_owner_lease'].__setitem__('peer','f'*64),lambda r:r['navigation_owner_lease']['context'].__setitem__('owner_id','native/4')]:
   self.row.clear();self.row.update(copy.deepcopy(old));change(self.row)
   with self.assertRaises(ValueError):cas_ui.receive(self.rid,json.dumps(self.packet))
   self.assertEqual(self.row['state'],'pending')
 def test_enter_and_appearance_mutations_cannot_use_the_failure_type(self):
  old=copy.deepcopy(self.row['request'])
  for request in [dict(operation='catalog-input',key='enter',focus_catalog=True),dict(operation='select',data_id='42')]:
   self.row['request']=request
   with self.assertRaises(ValueError):cas_ui.receive_socket(self.peer,self.rid,json.dumps(self.packet),clock=lambda:1)
   self.assertEqual(self.row['state'],'pending')
  self.row['request']=old
 def test_semantic_command_has_distinct_no_listener_route_and_false_focus(self):
  self.row['request']=dict(operation='catalog-key',key='home');self.packet['operation']='catalog-key';p=self.packet['navigation_unconsumed']
  p.update(source_route='semantic-navigation-before-queue',key_listener_invoked=False,focus_requested=False)
  cas_ui.receive_socket(self.peer,self.rid,json.dumps(self.packet),clock=lambda:1)
  self.assertEqual(cas_ui.result(self.rid)['outcome'],'native-navigation-unconsumed')
 def test_incomplete_new_failure_keeps_permanent_pending_guard_and_submits_no_following_read(self):
  bad=copy.deepcopy(self.packet);bad['navigation_unconsumed']['after']=None
  with self.assertRaises(ValueError):cas_ui.receive_socket(self.peer,self.rid,json.dumps(bad),clock=lambda:1)
  before=list(cas_ui._RECORDS)
  with self.assertRaisesRegex(ValueError,'unresolved'):cas_ui.submit('12',{'operation':'status'},clock=lambda:1)
  self.assertEqual(list(cas_ui._RECORDS),before);self.assertEqual(self.row['state'],'pending')
 def test_existing_consumed_timeout_and_mismatch_classifier_is_byte_exact(self):
  before=(ROOT/'Source/apex_core/cas_ui.py').read_text(encoding='utf-8');after=(HERE/'Source/apex_core/cas_ui.py').read_text(encoding='utf-8')
  def method(s,name):
   a=s.index('def '+name+'(');b=s.index('\ndef ',a+1);return s[a:b]
  for name in ('_complete_navigation_mismatch','_navigation_owner_context','_complete_slider_mismatch','validate_client'):
   self.assertEqual(hashlib.sha256(method(after,name).encode()).hexdigest(),{'_complete_navigation_mismatch': '188f892e02962ee216ac358538715e5f0aba552bc3a8265c656e0118f0b94be3', '_navigation_owner_context': 'ad4312ad449ea7a0af8c6f697c430b67c969514908be9080c393b076a5eb44c6', '_complete_slider_mismatch': '26c1ac480a580200ae954a581f145dfd309ca36de745343f4f9417320ef5b489', 'validate_client': '12fed0feff9241a175cd018ba65268dad6e40d4b5eb722658130fe97d3309895'}[name],name)
 def test_actual_as_loading_payload_passes_actual_socket_receiver_without_a_fake_client(self):
  import subprocess
  sys.path.insert(0,str(HERE/'tests'))
  from test_cas_unconsumed_as import UnconsumedAsTests
  UnconsumedAsTests.setUpClass();test=UnconsumedAsTests()
  code=test.code+test.start()+"readback();assert.equal(acks.length,1);console.log(JSON.stringify(acks[0]));"
  proc=subprocess.run(['node','-'],input=code,text=True,capture_output=True,timeout=15)
  self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr);packet=json.loads(proc.stdout.strip())
  proof=packet['navigation_unconsumed'];rid=packet['cas_request_id'];peer=proof['peer_nonce'];scope=proof['before']
  cas_ui._RECORDS.clear();cas_ui._PEERS.clear();cas_ui._PEERS[peer]={'sim_id':scope['sim_id']}
  cas_ui._RECORDS[rid]=dict(state='pending',sim_id=scope['sim_id'],request=dict(operation='catalog-input',key='home',focus_catalog=True),
   wire=rid+'|'+scope['sim_id']+'|catalog-input|0|0|0|home,1',peer=peer,transport='loopback-socket',delivery='claimed',
   navigation_owner_lease=dict(peer=peer,context=copy.deepcopy(scope)),result=None)
  ack=cas_ui.receive_socket(peer,rid,json.dumps(packet),clock=lambda:1);self.assertTrue(ack['acknowledgement_accepted'])
  result=cas_ui.result(rid);self.assertEqual(result['outcome'],'native-navigation-unconsumed');self.assertEqual(result['cas_request_state'],'failed')
  self.assertNotIn('client',result['native_acknowledgement']);self.assertFalse(result['input_consumed'])
 def test_recorded354_invalid_ack_remains_pending_and_is_not_reinterpreted(self):
  path=Path(__file__).parent/'fixtures/cas_unconsumed_rejected354.json';original=json.loads(path.read_text(encoding='utf-8'))
  proof=original['navigation_publication'];rid=original['cas_request_id'];peer=proof['peer_nonce'];sid=proof['before']['sim_id']
  cas_ui._RECORDS.clear();cas_ui._PEERS.clear();cas_ui._PEERS[peer]={'sim_id':sid}
  row=dict(state='pending',sim_id=sid,request=dict(operation='catalog-input',key='home',focus_catalog=True),wire=rid+'|'+sid+'|catalog-input|0|0|0|home,1',
   peer=peer,transport='loopback-socket',delivery='claimed',navigation_owner_lease=dict(peer=peer,context=copy.deepcopy(proof['before'])),result=None)
  cas_ui._RECORDS[rid]=row
  with self.assertRaises(ValueError):cas_ui.receive(rid,json.dumps(original))
  self.assertEqual(row['state'],'pending');self.assertEqual(row['rejected_acknowledgement'],original)
  self.assertEqual(cas_ui.result(rid)['cas_request_state'],'pending')

if __name__=='__main__':unittest.main()
