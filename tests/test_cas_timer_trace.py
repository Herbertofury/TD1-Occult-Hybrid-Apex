"""Execute the production Timer diagnostics with deterministic scalar inputs.

The existing Draw trace fixture supplies the AS-to-JS scalar translation. These
tests need no staged files, AVM2 compiler, parser package, or running game.
"""
import importlib.util
from pathlib import Path
import re
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Source/CASUi/catalog_trace_methods.as"
SEMANTIC = ROOT / "Source/CASUi/semantic_methods.as"
_spec = importlib.util.spec_from_file_location(
    "cas_timer_draw_fixture", ROOT / "tests/test_cas_draw_trace.py"
)
_draw_fixture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_draw_fixture)


def method(source, name):
    start = source.index("      private function " + name + "(")
    end = source.find("\n      private function ", start + 1)
    return source[start:] if end < 0 else source[start:end]


class TimerTraceSourceTests(unittest.TestCase):
    def test_helpers_do_not_call_domain_services_or_retain_game_objects(self):
        source = SOURCE.read_text(encoding="utf-8")
        helper = method(source, "ApexCatalogTimerStep") + method(source, "ApexCatalogTimerStatus")
        for forbidden in (
            "CallGameService", "CallUIService", "ApexNativeExchange", "new Timer",
            "new Socket", "FileReference", "ApexClone", "getChildAt",
        ):
            self.assertNotIn(forbidden, helper)
        self.assertIn('operation:String(root.operation)', helper)
        self.assertIn('phase:int(root.phase)', helper)
        self.assertIn('operation.substr(0,64)', helper)
        self.assertIn('record_limit:16,depth_limit:8', helper)
        self.assertIn('interrupted phases are separate upper bounds; no CPU attribution', helper)

    def test_default_callsite_checks_and_original_tick_finally(self):
        source = SEMANTIC.read_text(encoding="utf-8")
        markers = re.findall(
            r'(?m)^[ \t]*// APEX_TIMER_TRACE_BEGIN ([^\n]+)\n(.*?)'
            r'^[ \t]*// APEX_TIMER_TRACE_END \1\n', source, re.S
        )
        self.assertGreaterEqual(len(markers), 20)
        for name, body in markers:
            if name == "tick-end":
                self.assertIn('if(apexTimerTraceGeneration!=0)', body)
            elif name == "tick-begin":
                self.assertIn('apexCatalogTrace!=null && apexCatalogTrace.enabled===true', body)
            else:
                self.assertIn('apexCatalogTrace!=null && apexCatalogTrace.enabled===true && apexCatalogTrace.timer_profile!=null', body, name)
            for forbidden in ('new ', 'getTimer(', 'ApexSnapshot(', 'CallGameService', 'CallUIService'):
                self.assertNotIn(forbidden, body, name)
        tick = method(source, "ApexTick")
        self.assertLess(tick.rindex('finally {'), tick.index('// APEX_TIMER_TRACE_BEGIN tick-end'))
        self.assertLess(tick.index('"tick.leave"'), tick.index('apexTicking=false;'))
        readback = method(source, "ApexReadback")
        self.assertLess(readback.index('"snapshot.enter"'), readback.index('if(operation=="panel-navigation") reply.client='))
        self.assertLess(readback.index('"snapshot.leave"'), readback.index('catalogAfter=null;'))


@unittest.skipUnless(shutil.which("node"), "Node required for scalar helper harness")
class TimerTraceHelperTests(unittest.TestCase):
    def run_js(self, code):
        boot = '''let now=0,clocks=0;
const flash={utils:{getTimer:()=>{clocks++;return now;}}};
const CASCustomizerMain={apexCatalogDrawTraceStep:null};
const int=x=>x|0;
let apexPendingPhase=0,apexPendingFields=null,apexReceiving=false,apexWire="",apexFormsIntent=null;
function ApexLayoutTraceDispose(){};
function check(v,m){if(!v)throw Error(m);}
'''
        result = subprocess.run(
            ["node", "-e", boot + _draw_fixture.helper_js() + code],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_disabled_has_no_clocks_or_profile_allocation(self):
        self.run_js('''let initial=clocks;
check(ApexCatalogTimerStep('tick.enter')===0,'default');
check(ApexCatalogTimerStep('receive.enter')===0,'default inner');
check(clocks===initial,'default clocks');
ApexCatalogTraceConfigure(0);
check(ApexCatalogTraceStatus().timer_profile.completed===0,'empty');
check(clocks===initial,'disabled clocks');
ApexCatalogTraceConfigure(100);ApexCatalogTraceConfigure(0);initial=clocks;
ApexCatalogTimerStep('tick.enter');ApexCatalogTimerStep('execute.enter');
check(clocks===initial && apexCatalogTrace.timer_profile===undefined,'stopped never allocated');''')

    def test_nested_inclusive_phases_and_copied_operation(self):
        self.run_js('''ApexCatalogTraceConfigure(1000);
let token=ApexCatalogTimerStep('tick.enter');
apexReceiving=true;apexWire='id|sim|panel|3|0|0|';now=1;
ApexCatalogTimerStep('execute.enter');now=3;ApexCatalogTimerStep('native-info.enter');
now=7;ApexCatalogTimerStep('native-info.leave');now=11;ApexCatalogTimerStep('execute.leave');
now=12;ApexCatalogTimerStep('tick.leave',token);
let s=ApexCatalogTimerStatus();
check(s.completed===1 && s.records[0].operation==='panel','operation copy');
check(s.aggregates.tick.total_ms===12 && s.aggregates.execute.total_ms===10,'inclusive outer');
check(s.aggregates['native-info'].total_ms===4,'native getter separate');
check(s.incomplete.length===0 && s.errors===0,'balanced');
check(JSON.stringify(s).indexOf('id|sim')<0,'no request or Sim retained');''')

    def test_missing_inner_leave_is_interrupted_and_original_error_propagates(self):
        self.run_js('''ApexCatalogTraceConfigure(1000);
let token=ApexCatalogTimerStep('tick.enter'),original={native:'error'},caught;
try{now=1;ApexCatalogTimerStep('execute.enter');now=2;ApexCatalogTimerStep('native-info.enter');throw original;}
catch(e){caught=e;}finally{now=8;ApexCatalogTimerStep('tick.leave',token);}
let s=ApexCatalogTimerStatus();check(caught===original,'exception identity retained');
check(s.aggregates['native-info'].completed===0 && s.aggregates['native-info'].interrupted===1,'no native completion forged');
check(s.aggregates.execute.interrupted===1 && s.records[0].interrupted===2,'interrupted parent');
check(s.incomplete.length===0 && s.completed===1,'existing finally closed tick only');''')

    def test_stop_and_reconfigure_cannot_mix_generations(self):
        self.run_js('''ApexCatalogTraceConfigure(1000);let token=ApexCatalogTimerStep('tick.enter');
now=1;ApexCatalogTimerStep('execute.enter');ApexCatalogTraceConfigure(0);
now=3;ApexCatalogTimerStep('tick.leave',token);let s=ApexCatalogTimerStatus();
check(s.completed===1 && s.aggregates.execute.interrupted===1,'stop closes original pending tick');
ApexCatalogTraceConfigure(1000);let next=ApexCatalogTimerStep('tick.enter');
ApexCatalogTimerStep('tick.leave',token);
check(ApexCatalogTimerStatus().incomplete.length===1,'stale generation cannot close');
now=4;ApexCatalogTimerStep('tick.leave',next);
check(ApexCatalogTimerStatus().completed===1,'new generation closes');''')

    def test_expiry_does_not_start_tick_but_existing_finally_can_finish(self):
        self.run_js('''ApexCatalogTraceConfigure(10);now=11;
check(ApexCatalogTimerStep('tick.enter')===0,'expired admission');
check(!apexCatalogTrace.enabled && apexCatalogTrace.expired,'expired stopped');
now=20;ApexCatalogTraceConfigure(10);let token=ApexCatalogTimerStep('tick.enter');now=31;
ApexCatalogTraceStatus();ApexCatalogTimerStep('tick.leave',token);
check(ApexCatalogTimerStatus().completed===1,'inflight duration remains observable');''')

    def test_bounds_faults_and_default_path_after_stop(self):
        self.run_js('''ApexCatalogTraceConfigure(30000);
for(let i=0;i<40;i++){let token=ApexCatalogTimerStep('tick.enter');now+=i+1;ApexCatalogTimerStep('tick.leave',token);}
check(ApexCatalogTimerStatus().records.length===16,'slow record bound');
let token=ApexCatalogTimerStep('tick.enter');
for(let i=0;i<20;i++)ApexCatalogTimerStep('execute.enter');
check(ApexCatalogTimerStatus().incomplete.length===8,'depth bound');
for(let i=0;i<20;i++)ApexCatalogTimerStep('execute.leave');ApexCatalogTimerStep('tick.leave',token);
check(ApexCatalogTimerStatus().dropped===13,'overflow counted');
ApexCatalogTraceConfigure(0);let last=clocks;
ApexCatalogTimerStep('tick.enter');ApexCatalogTimerStep('execute.enter');
check(clocks===last,'disabled reused state no clocks');
Object.defineProperty(apexCatalogTrace,'timer_profile',{get(){throw 'arbitrary diagnostic throw';}});
check(ApexCatalogTimerStep('tick.leave',token)===0,'diagnostic failure contained');''')

    def test_all_phase_metrics_and_primitive_operation_snapshot(self):
        self.run_js('''ApexCatalogTraceConfigure(1000);apexPendingPhase=7;
let token=ApexCatalogTimerStep('tick.enter');
apexPendingFields=['request','sim','x'.repeat(100)];
for(const name of ['receive','native-info','clone','execute','readback','snapshot','ack-encode','ack-send','forms']){
  now++;ApexCatalogTimerStep(name+'.enter');now+=2;ApexCatalogTimerStep(name+'.leave');
}
apexPendingPhase=999;apexPendingFields[2]='changed';now++;ApexCatalogTimerStep('tick.leave',token);
let s=ApexCatalogTraceStatus().timer_profile;
check(s.records[0].phase===7 && s.records[0].operation==='x'.repeat(64),'copied bounded primitives');
check(Object.keys(s.aggregates).length===10,'fixed phase inventory');
for(const name of Object.keys(s.aggregates)){
  check(s.aggregates[name].started===1 && s.aggregates[name].completed===1,'each scope completed');
  check(s.aggregates[name].interrupted===0,'no interrupted scope');
  if(name!=='tick')check(s.aggregates[name].total_ms===2,'exact inner duration');
}
check(s.errors===0 && s.incomplete.length===0,'clean completion');''')

    def test_unknown_or_mismatched_phase_cannot_forge_a_completion(self):
        self.run_js('''ApexCatalogTraceConfigure(1000);
let token=ApexCatalogTimerStep('tick.enter');now=1;ApexCatalogTimerStep('execute.enter');
ApexCatalogTimerStep('readback.leave');ApexCatalogTimerStep('unknown.enter');
ApexCatalogTimerStep('execute.other');
let pending=ApexCatalogTimerStatus();
check(pending.errors===3 && pending.incomplete.length===2,'invalid phase rejected');
check(pending.aggregates.execute.completed===0,'no completion fabricated');
now=3;ApexCatalogTimerStep('execute.leave');now=4;ApexCatalogTimerStep('tick.leave',token);
let done=ApexCatalogTimerStatus();
check(done.aggregates.execute.completed===1 && done.aggregates.execute.total_ms===2,'valid close retained');
check(done.completed===1 && done.incomplete.length===0,'root closes normally');''')


if __name__ == "__main__":
    unittest.main()
