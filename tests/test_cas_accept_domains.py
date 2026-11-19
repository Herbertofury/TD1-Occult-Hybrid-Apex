from pathlib import Path
import ast,importlib.util,subprocess,sys,unittest
ROOT=Path.cwd();sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
import test_cas_accept_physical_kind as physical
existing=physical.existing
FIXTURE=ROOT/'tests/fixtures/cas_accept_domains_v348.json'
fixture=physical.fixture
needle='    if(nativeShell!==4)fresh.occultType=nativeShell;'
assert fixture.count(needle)==1
fixture=fixture.replace(needle,'    if(onPreparedPacket)onPreparedPacket();')
fixture+='\nvar onPreparedPacket=null;\n'

def run(body,baseline=False):
 text=(ROOT/'Source/CASUi/semantic_methods.as').read_text(encoding='utf-8')
 if baseline:
  from cas_grid_pool import method_extent
  import json
  old=json.loads(FIXTURE.read_text(encoding='utf-8'))
  assert old['source_sha256']=='72ce6e57307d58681ed5ebe2b0c12874913248642b18ef2a42335f2198c68303'
  for name,baseline_body in old['methods'].items():
   a,b=method_extent(text,name);text=text[:a]+baseline_body+text[b:]
 class TextSource:
  def read_text(self,**kwargs):return text
 original=existing.SOURCE
 try:
  existing.SOURCE=TextSource();method=existing.method()
 finally:existing.SOURCE=original
 p=subprocess.run(['node','-'],input=fixture+method+body,text=True,capture_output=True,timeout=10)
 if p.returncode:raise AssertionError(p.stdout+p.stderr)

class AcceptanceDomains(unittest.TestCase):
 def test_actual_packet4_physical2_reproduces_v348_pre_save_refusal(self):
  run(r"nativeShell=2;invoke();assert.equal(prepareCalls,1);assert.equal(readyCalls,0);assert.equal(saveCalls,0);assert.match(acks[0][1].message,/changed Sim\/household\/layer\/editor mode/);",baseline=True)
 def test_actual_packet_remains4_with_prepared_native_view2_and_saves_once(self):
  run("nativeShell=2;nativeBusy=true;invoke();assert.equal(prepareCalls,1);assert.equal(apexAcceptWait.shell,4);assert.equal(apexAcceptWait.nativeViewKind,2);assert.equal(apexAcceptWait.preparedPacketShell,4);assert.equal(saveCalls,0);const original=preparedRequest;nativeBusy=false;frame();assert.equal(saveCalls,1);assert.equal(preparedRequest,original);invoke();frame();assert.equal(saveCalls,1);")
 def test_real_one_time_packet_normalization_to_exact_prepared_view_is_supported(self):
  run("nativeShell=2;nativeBusy=true;onPreparedPacket=()=>{fresh.occultType=2;};invoke();assert.equal(apexAcceptWait.shell,4);assert.equal(apexAcceptWait.nativeViewKind,2);assert.equal(apexAcceptWait.preparedPacketShell,2);assert.equal(saveCalls,0);nativeBusy=false;frame();assert.equal(saveCalls,1);")
 def test_post_bound_packet_flip_is_not_adopted_in_either_direction(self):
  for initial,changed in ((4,2),(2,4)):
   with self.subTest(initial=initial):
    run("nativeShell=2;nativeBusy=true;onPreparedPacket=()=>{fresh.occultType="+str(initial)+";};invoke();assert.equal(apexAcceptWait.preparedPacketShell,"+str(initial)+");fresh.occultType="+str(changed)+";nativeBusy=false;frame();assert.equal(saveCalls,0);assert.equal(prepareCalls,1);assert.equal(cancelCalls,1);invoke();frame();assert.equal(saveCalls,0);")
 def test_unrelated_or_untyped_packet_is_never_adopted(self):
  for value in ('1','8','16','32','64','3','0','"4"','true','null'):
   with self.subTest(value=value):
    run("nativeShell=2;onPreparedPacket=()=>{fresh.occultType="+value+";};invoke();assert.equal(saveCalls,0);assert.equal(readyCalls,0);assert.equal(cancelCalls,1);")
 def test_all_fresh_identity_mode_nonce_owner_and_mask_fences_survive_prepare(self):
  for mutation in ("fresh.simId='13';","fresh.householdId='35';",'fresh.occultLayer=1;','fresh.allOccultTypes=63;',
                   'mode=7;','newFamily=true;','fromLive=false;',"apexNonce='c'.repeat(64);", "apexNativeChannel='8';",
                   "cursor='VIEWSTATE|12|alien/other|2|0|bound|92';", "cursor='VIEWSTATE|12|alien/first|2|0|bound|93';"):
   with self.subTest(mutation=mutation):
    run('nativeShell=2;onPreparedPacket=()=>{'+mutation+'};invoke();assert.equal(saveCalls,0);assert.equal(prepareCalls,1);assert.equal(cancelCalls,1);')
 def test_native_prepared_physical_stamp_change_still_refuses(self):
  run("nativeShell=2;nativeBusy=true;invoke();nativeShell=4;nativeBusy=false;frame();assert.equal(saveCalls,0);assert.equal(cancelCalls,1);")
 def test_cached_generation_change_after_prepared_adoption_still_refuses(self):
  run("nativeShell=2;nativeBusy=true;invoke();assert.equal(apexFormsNativeGeneration,'92');apexFormsNativeGeneration='93';nativeBusy=false;frame();assert.equal(saveCalls,0);assert.equal(cancelCalls,1);")
 def test_packet_change_during_pre_prepare_cleanup_remains_forbidden(self):
  run("nativeShell=2;onCleanup=()=>{fresh.occultType=2;};invoke();assert.equal(saveCalls,0);assert.equal(prepareCalls,0);")
 def test_plain_unbound_and_mode7_keep_original_native_contract(self):
  run("apexFormsNativeState='unavailable';apexFormsSelectedId='';apexNativeChannel='';nativePhysicalView=4;invoke();assert.equal(saveCalls,1);assert(preparedRequest.includes('|0|0|4|2|127|-|0'));")
  run("mode=7;apexFormsNativeState='unavailable';apexFormsSelectedId='';apexNativeChannel='';nativePhysicalView=4;invoke();assert.equal(saveCalls,1);assert(preparedRequest.includes('|0|0|-|-|-|-|0'));")
 def test_known_prior_domain_error_and_existing_native_guards_remain_explicit(self):
  from cas_grid_pool import method_extent
  import json
  old=json.loads(FIXTURE.read_text(encoding='utf-8'))
  self.assertEqual(set(old['methods']),{'ApexAcceptNative','ApexAcceptReady'})
  self.assertEqual(old['source_sha256'],'72ce6e57307d58681ed5ebe2b0c12874913248642b18ef2a42335f2198c68303')
  self.assertIn('held.shell=int(fields[5])',old['methods']['ApexAcceptNative'])
  import cas_ui_build
  final=(ROOT/'Source/CASUi/semantic_methods.as').read_text(encoding='utf-8')
  self.assertTrue(cas_ui_build.verify_household_acceptance(final))
  native=(ROOT/'NativeOverlay/Source/ApexNativeCasEngineWin.h').read_text(encoding='utf-8')
  for guard in ('intent.viewKind!=std::to_string(current.viewKind)',
                'intent.modelKind!=std::to_string(current.modelKind)',
                'intent.viewMask!=std::to_string(current.viewMask)',
                'Read<std::uint32_t>(view,0xd8)!=cursor.kind',
                'Read<std::uint32_t>(model,0x178)!=cursor.kind'):
   self.assertIn(guard,native)


if __name__=='__main__':unittest.main()
