"""Bounded explicit diagnostics: execute helper bodies and actual donor ABC."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'Source/CASUi/catalog_trace_methods.as'


def helper_js():
    source=SOURCE.read_text(encoding='utf-8')
    source=re.sub(r'public static var apexCatalogDrawTraceStep:Function;', '', source)
    source=re.sub(r'private var apexCatalogTrace:Object;', 'var apexCatalogTrace;', source)
    source=re.sub(r'private function (\w+)\(([^)]*)\)\s*:\s*\w+',
                  lambda m:'function '+m[1]+'('+re.sub(r':\w+', '', m[2])+')',source)
    source=re.sub(r'for each\(var (\w+):\w+ in ([^\n]+)\)',r'for(var \1 of \2)',source)
    source=re.sub(r'\bvar (\w+):\w+',r'var \1',source)
    source=re.sub(r'catch\((\w+):(?:Error|\*)\)',r'catch(\1)',source)
    return source


@unittest.skipUnless(shutil.which('node'),'Node required for scalar helper harness')
class DrawTraceHelperTests(unittest.TestCase):
    def run_js(self,test):
        boot='''let now=0,clocks=0,layoutDisposals=0;
const flash={utils:{getTimer:()=>{clocks++;return now;}}};
const CASCustomizerMain={apexCatalogDrawTraceStep:null};
const int=x=>x|0;
function check(v,m){if(!v)throw Error(m);}
function ApexLayoutTraceDispose(){layoutDisposals++;}
'''
        result=subprocess.run(['node','-e',boot+helper_js()+test],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_never_started_and_disabled_have_no_clock_or_callback(self):
        self.run_js('''check(ApexCatalogTraceStatus().requested_ms===0,"default");
check(ApexCatalogTraceStatus().records.length===0,"empty records");
ApexCatalogTraceStep("draw.enter",{data_id:"1"});
ApexCatalogTraceConfigure(0);check(clocks===0,"disabled timer");check(layoutDisposals===0,"disabled draw trace leaves layout diagnostics alone");
check(CASCustomizerMain.apexCatalogDrawTraceStep===null,"disabled callback");''')

    def test_other_main_disposal_cannot_clear_active_owner(self):
        second='(function(){'+helper_js()+';return {configure:ApexCatalogTraceConfigure,status:ApexCatalogTraceStatus,dispose:ApexCatalogTraceDispose};})()'
        self.run_js('''ApexCatalogTraceConfigure(100);let firstCallback=CASCustomizerMain.apexCatalogDrawTraceStep;
let second='''+second+''';second.dispose();check(CASCustomizerMain.apexCatalogDrawTraceStep===firstCallback,"uninitialized foreign dispose");
second.configure(100);let active=CASCustomizerMain.apexCatalogDrawTraceStep;
ApexCatalogTraceDispose();check(CASCustomizerMain.apexCatalogDrawTraceStep===active,"foreign old dispose");
check(second.status().enabled && second.status().callback_active,"owner active");
second.dispose();check(CASCustomizerMain.apexCatalogDrawTraceStep===null,"owner dispose");''')

    def test_exact_phases_and_scalar_records(self):
        self.run_js('''ApexCatalogTraceConfigure(1000);check(layoutDisposals===1,"positive draw trace retires the other diagnostic");
ApexCatalogTraceStep("draw.enter",{data_id:"18446744073709551615",body_type:114});
now=1;ApexCatalogTraceStep("thumbnail.enter");now=99;ApexCatalogTraceStep("thumbnail.leave");
now=100;ApexCatalogTraceStep("draw.leave");let s=ApexCatalogTraceStatus();
check(s.completed===1 && s.records[0].total_ms===100,"draw duration");
check(s.aggregates.thumbnail.total_ms===98 && s.aggregates.other.total_ms===2,"phase times");
check(s.records[0].id==="18446744073709551615","64 bit id");
check(JSON.stringify(s).indexOf("data_id")<0,"no product retained");''')

    def test_expiry_zero_stop_preserves_and_generation_resets(self):
        self.run_js('''ApexCatalogTraceConfigure(10);now=2;ApexCatalogTraceStep("draw.enter",{data_id:"2"});
now=3;ApexCatalogTraceStep("draw.leave");now=10;let s=ApexCatalogTraceStatus();
check(s.expired && !s.enabled && CASCustomizerMain.apexCatalogDrawTraceStep===null,"expire");
let old=clocks;s=ApexCatalogTraceConfigure(0);check(s.requested_ms===0 && s.records.length===1,"stop preserves");
check(clocks===old,"stop timer");s=ApexCatalogTraceConfigure(20);
check(s.generation===2 && s.completed===0 && s.requested_ms===20,"reset generation");''')

    def test_depth_overflow_record_cap_and_errors_are_bounded(self):
        self.run_js('''ApexCatalogTraceConfigure(30000);
for(let i=0;i<12;i++)ApexCatalogTraceStep("draw.enter",{data_id:String(i),body_type:2});
check(ApexCatalogTraceStatus().incomplete.length===8,"stack bound");
for(let i=0;i<12;i++){now++;ApexCatalogTraceStep("draw.leave");}
check(ApexCatalogTraceStatus().incomplete.length===0,"overflow unwinds");
for(let i=0;i<40;i++){ApexCatalogTraceStep("draw.enter",{data_id:String(i)});now+=i+1;ApexCatalogTraceStep("draw.leave");}
check(ApexCatalogTraceStatus().records.length===32,"record cap");
ApexCatalogTraceStep("draw.enter",{get data_id(){throw Error("bad product");}});
let s=ApexCatalogTraceStatus();check(!s.enabled && s.errors===1,"diagnostic error stops cleanly");''')

    def test_native_exception_is_reported_incomplete_without_catching_game(self):
        self.run_js('''ApexCatalogTraceConfigure(20);ApexCatalogTraceStep("draw.enter",{data_id:"9"});
now=2;ApexCatalogTraceStep("super.enter");now=20;let s=ApexCatalogTraceStatus();
check(s.completed===0 && s.incomplete[0].phase==="super","no fabricated completion");''')

    def test_non_error_diagnostic_throws_are_also_contained(self):
        self.run_js('''ApexCatalogTraceConfigure(100);
ApexCatalogTraceStep("draw.enter",{get data_id(){throw "arbitrary thrown value";}});
check(ApexCatalogTraceStatus().errors===1 && !ApexCatalogTraceStatus().enabled,"catch all");''')

    def test_bounds_and_source_has_no_services_or_io(self):
        self.run_js('''for(const n of [-1,30001]){let failed=false;try{ApexCatalogTraceConfigure(n);}catch(e){failed=true;}check(failed,"bound");}''')
        source=SOURCE.read_text(encoding='utf-8')
        for forbidden in ('CallGameService','CallUIService','ApexNativeExchange','new Timer','new Socket','FileReference'):
            self.assertNotIn(forbidden,source)


@unittest.skipUnless((ROOT/'.work/research/apex-companion-lazy-swatches-1.swf').exists() and shutil.which('javac'),
                     'Actual compiled donor helpers required')
class DrawTraceBytecodeTests(unittest.TestCase):
    def test_serialized_guards_retained_instructions_branches_returns_and_trait(self):
        info=json.loads((ROOT/'dist/candidate/ApexCASBridge.package.manifest.json').read_text())
        if info.get('native_bytecode_contract',{}).get('native_draw_trace_adapters')!=1:
            self.skipTest('Build with explicit Draw diagnostics first')
        jar=ROOT/'.work/research/ffdec/ffdec.jar'
        with tempfile.TemporaryDirectory(prefix='apex-draw-trace-') as directory:
            subprocess.run(['javac','-cp',str(jar),'-d',directory,str(ROOT/'tools/CasBytecodePatch.java'),
                            str(ROOT/'tests/CasDrawTraceBytecodeFixtures.java')],check=True,capture_output=True,timeout=60)
            for mode in ('valid','pin','trait','guard','retained','branch','locals','exceptions','flow-stale-jump','flow-stale-if','flow-null-receiver',
                         'helper-valid','helper-return','helper-catch','helper-service'):
                with self.subTest(mode=mode):
                    r=subprocess.run(['java','-cp',str(jar)+os.pathsep+directory,'CasDrawTraceBytecodeFixtures',
                        str(ROOT/'.work/research/maru-integrated/DynamicCASCustomizer.swf'),
                        str(ROOT/'.work/research/apex-companion-lazy-swatches-1.swf'),mode],capture_output=True,text=True,timeout=30)
                    self.assertEqual(r.returncode,0,r.stdout[-500:]+r.stderr[-1500:])
                    self.assertIn('PASS '+mode,r.stdout)


if __name__=='__main__':unittest.main()
