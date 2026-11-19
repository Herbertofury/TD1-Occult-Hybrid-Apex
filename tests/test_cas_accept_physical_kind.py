"""Actual-AS fixture for V347 packet shell4 / physical owner2 admission.

No game calls. The new native guard in the host fixture deliberately models
the UNCHANGED strict EngineWin PREPARE equality, not a permissive mock.
"""
from pathlib import Path
import ast
import importlib.util
import json
import re
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('existing_accept',ROOT/'tests/test_cas_accept_cleanup.py')
existing=importlib.util.module_from_spec(spec);spec.loader.exec_module(existing)
tree=ast.parse((ROOT/'tests/test_cas_accept_cleanup.py').read_text(encoding='utf-8'))
run_as=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='run_as')
fixture=next(ast.literal_eval(n.value) for n in run_as.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='fixture' for t in n.targets))
needle="if(verb==='PREPARE'){\n"
assert fixture.count(needle)==1
STRICT=r'''
    if(f[7]!==String(nativePhysicalLayer) ||
       (f[8]!=='-' && f[8]!==String(nativePhysicalView)) ||
       (f[9]!=='-' && f[9]!==String(nativePhysicalModel)) ||
       (f[10]!=='-' && f[10]!==String(nativePhysicalMask)))
      return 'REFUSED|Acceptance original pre-harvest form identity changed.';
    if(f[6]!=='0' && (f[11]!==nativePhysicalOwner || f[12]!==nativePhysicalGeneration))
      return 'REFUSED|Acceptance original pre-harvest owner/generation changed.';
'''
fixture=fixture.replace(needle,needle+STRICT)
fixture+='\nvar nativePhysicalLayer=0,nativePhysicalView=2,nativePhysicalModel=2,nativePhysicalMask=127,nativePhysicalOwner="alien/first",nativePhysicalGeneration="91";\n'


OLD='(editMode===0 ? String(observedShell)+"|"+String(observedRendered)+"|"+String(observedMask) : "-|-|-")'
NEW='(editMode===0 ? String(acceptanceChannel!="" ? observedRendered : observedShell)+"|"+String(observedRendered)+"|"+String(observedMask) : "-|-|-")'


def run(body,staged=True):
    text=(ROOT/'Source/CASUi/semantic_methods.as').read_text(encoding='utf-8')
    assert text.count(NEW)==1 and OLD not in text
    if not staged:text=text.replace(NEW,OLD)
    class TextSource:
        def read_text(self,**kwargs):return text
    original=existing.SOURCE
    try:
        existing.SOURCE=TextSource()
        method=existing.method()
    finally:existing.SOURCE=original
    result=subprocess.run(['node','-'],input=fixture+method+body,text=True,capture_output=True,timeout=10)
    if result.returncode:raise AssertionError(result.stdout+result.stderr)


class PhysicalKind(unittest.TestCase):
    def test_actual_recorded_case_reproduces_old_refusal(self):
        # Reproduce the recorded V347 packet4/rendered2 owner-bound case.
        # The original native strict equality must reject the old operand.
        run("nativeShell=2;invoke();assert.equal(saveCalls,0);assert.equal(prepareCalls,0);assert.equal(acks.length,1);assert.match(acks[0][1].message,/original pre-harvest form identity changed/);invoke();frame();assert.equal(saveCalls,0);",staged=False)

    def test_attested_physical_tuple_passes_original_native_equality_once(self):
        run('''
nativeShell=2;nativeBusy=true;
onCleanup=()=>{assert.equal(fresh.occultType,4);assert.equal(rendered,2);};
invoke();assert.equal(saveCalls,0);assert.equal(prepareCalls,1);
assert(preparedRequest.includes('|7|0|2|2|127|alien/first|91'));
assert.equal(apexAcceptWait.shell,4);assert.equal(apexAcceptWait.nativeViewKind,2); // Existing R2 post-harvest native attestation.
const original=preparedRequest;frame();assert.equal(prepareCalls,1);
assert.equal(apexAcceptWait.request,original);nativeBusy=false;frame();
assert.equal(saveCalls,1);frame();invoke();assert.equal(saveCalls,1);
''')

    def test_true_physical_staleness_still_refuses_without_harvest(self):
        for mutation in ('nativePhysicalView=4;','nativePhysicalModel=4;','nativePhysicalMask=63;',
                         'nativePhysicalLayer=1;',"nativePhysicalOwner='alien/other';","nativePhysicalGeneration='92';"):
            with self.subTest(mutation=mutation):
                run("nativeShell=2;"+mutation+"invoke();assert.equal(saveCalls,0);assert.equal(prepareCalls,0);assert.equal(acks[0][1].commit_attempted,false);invoke();frame();assert.equal(saveCalls,0);")

    def test_packet_shell_and_original_context_checks_survive_cleanup(self):
        for mutation in ('fresh.occultType=2;','fresh.allOccultTypes=63;',"fresh.simId='13';",'fresh.occultLayer=1;',
                         "cursor='VIEWSTATE|12|alien/other|2|0|bound|91';", "cursor='VIEWSTATE|12|alien/first|2|0|bound|92';",
                         "apexNativeChannel='8';","apexNonce='c'.repeat(64);",'apexDisconnected=true;'):
            with self.subTest(mutation=mutation):
                run("nativeShell=2;onCleanup=()=>{"+mutation+"};invoke();assert.equal(saveCalls,0);assert.equal(prepareCalls,0);assert.equal(JSON.parse(apexLastReply).commit_attempted,false);invoke();frame();assert.equal(saveCalls,0);")

    def test_plain_unbound_original_tuple_and_mode7_remain_unchanged(self):
        run("apexFormsNativeState='unavailable';apexFormsSelectedId='';apexNativeChannel='';nativePhysicalView=4;invoke();assert(preparedRequest.includes('|0|0|4|2|127|-|0'));assert.equal(saveCalls,1);invoke();assert.equal(saveCalls,1);")
        run("mode=7;apexFormsNativeState='unavailable';apexFormsSelectedId='';apexNativeChannel='';invoke();assert(preparedRequest.includes('|0|0|-|-|-|-|0'));assert.equal(saveCalls,1);assert(!events.includes('CASHideCustomizer'));")

    def test_single_field_change_preserves_all_native_source_and_household_gates(self):
        final=(ROOT/'Source/CASUi/semantic_methods.as').read_text(encoding='utf-8')
        self.assertEqual(final.count(NEW),1)
        self.assertNotIn(OLD,final)
        sys.path.insert(0,str(ROOT/'tools'));from cas_ui_build import verify_household_acceptance
        self.assertTrue(verify_household_acceptance(final))
        native=(ROOT/'NativeOverlay/Source/ApexNativeCasEngineWin.h').read_text(encoding='utf-8')
        for fragment in ('intent.viewKind!=std::to_string(current.viewKind)',
                         'intent.modelKind!=std::to_string(current.modelKind)',
                         'intent.viewMask!=std::to_string(current.viewMask)',
                         'intent.owner!=cursor.owner || intent.generation!=std::to_string(cursor.generation)',
                         'Read<std::uint32_t>(view,0xd8)!=cursor.kind',
                         'Read<std::uint32_t>(model,0x178)!=cursor.kind'):
            self.assertIn(fragment,native)


if __name__=='__main__':unittest.main()
