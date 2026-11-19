"""Actual-AS failure diagnostics; host quarantine stays unchanged."""
from pathlib import Path
import json,re,sys,unittest
HERE=Path(__file__).resolve().parents[1]
ROOT=Path(__file__).resolve().parents[3] if HERE.name.startswith('v350-') else HERE
sys.path[:0]=[str(HERE/'tools'),str(ROOT/'tools'),str(ROOT/'tests')]
import cas_catalog_workflow as workflow
import test_cas_keyboard_publication as keyboard
import test_cas_keyboard_postcondition as host

def converted(name,params):
    source=workflow.stage.fragment()
    source=re.sub(r'(?m)^private function ','      private function ',source)
    tail=source.split('private function '+name+'(',1)[1]
    tail=re.split(r'\n      private (?:function|var) ',tail,maxsplit=1)[0]
    body=tail.split('{',1)[1].rsplit('}',1)[0]
    body=re.sub(r'\b(var\s+\w+)\s*:\s*[\w.*]+',r'\1',body)
    body=re.sub(r'\s+as\s+[\w.]+','',body)
    body=re.sub(r'([\w.\[\]]+)\s+is\s+(int|String|Number|Boolean|Array)',r'isType(\1,"\2")',body)
    body=re.sub(r'catch\((\w+)\s*:\s*Error\)',r'catch(\1)',body)
    body=re.sub(r'for each\(([^)]+) in ([^)]+)\)',r'for(\1 of \2)',body)
    return 'function '+name+'('+params+'){'+body+'}\n'

class WorkflowDiagnosticTests(unittest.TestCase):
    def execute(self,test):
        prior_keyboard=keyboard.keyboard_method;prior_source=keyboard.source_method
        try:
            keyboard.keyboard_method=lambda name,params: converted(name,params) if name=='ApexCatalogKeyboardPublicationReady' else prior_keyboard(name,params)
            keyboard.source_method=lambda name,params,stop=None: (converted(name,params)+converted('ApexCatalogKeyboardFailureDiagnostic','error,held')) if name=='ApexReadback' else prior_source(name,params,stop)
            keyboard.KeyboardPublicationTests().execute('apexCatalogGrid.grid=grid;lease.view=view;\n'+test,injected=True)
        finally:
            keyboard.keyboard_method=prior_keyboard;keyboard.source_method=prior_source

    def test_failed_ack_contains_original_error_and_copied_grid_keyboard_evidence(self):
        self.execute(r'''
grid.ApexGridStatus=()=>({phase:'cancelled',error:'boom'});
apexCatalogGrid.error='Main stopped';apexCatalogGrid.waiting='publication';
apexKeyReceipt={...apexKeyReceipt};readback();assert.equal(acks.length,1);const a=acks[0];
assert.equal(a.ok,false);assert.match(a.message,/guard=receipt/);assert.equal(a.navigation_diagnostic.diagnostic_only,true);
assert.equal(a.navigation_diagnostic.main.error,'Main stopped');assert.equal(a.navigation_diagnostic.main.waiting,'publication');
assert.equal(a.navigation_diagnostic.grid.error,'boom');assert.equal(a.navigation_diagnostic.main.panel_visible,true);
assert.equal(a.navigation_diagnostic.keyboard.receipt_same,false);assert.equal(a.navigation_diagnostic.keyboard.target,149);
assert.equal(scrolls,1);assert.equal(dispatches,0);assert.equal('client'in a,false);
''')

    def test_diagnostic_getter_failure_never_replaces_original_failure_or_replays_key(self):
        self.execute(r'''
grid.ApexGridStatus=()=>{throw Error('status unavailable');};
apexKeyReceipt={...apexKeyReceipt};readback();const a=acks[0];
assert.match(a.message,/guard=receipt/);assert.equal(a.navigation_diagnostic.grid,null);
assert.equal(a.navigation_diagnostic.status_error,'status unavailable');assert.equal(scrolls,1);assert.equal(dispatches,0);
''')

    def test_large_status_and_stack_are_bounded_after_failure_only(self):
        self.execute(r'''
const oldStatus=grid.ApexGridStatus;grid.ApexGridStatus=()=>({...oldStatus(),thumbnail_failures:Array.from({length:2000},()=>({resource:'x'.repeat(20000)})),
 error:'E'.repeat(50000),row_delta_last_error:'D'.repeat(50000),counts:{draw:20},row_delta_refusal:{reason:'R'.repeat(30000),phase:'borrow',index:6,generation:9,expected:4.4,actual:4.35}});
Error.prototype.getStackTrace=()=> 'S'.repeat(5000);apexKeyReceipt={...apexKeyReceipt};readback();const d=acks[0].navigation_diagnostic;
assert.equal(d.error.stack.length,2048);assert.equal(d.grid.error.length,512);assert.equal(d.grid.row_delta_last_error.length,512);
assert.equal(d.grid.row_delta_refusal.reason.length,512);assert.equal(d.grid.row_delta_refusal.index,6);
assert.equal('thumbnail_failures'in d.grid,false);assert.ok(Buffer.byteLength(JSON.stringify(acks[0]),'utf8')<32768);
assert.equal(scrolls,1);assert.equal(dispatches,0);
''')

    def test_huge_unicode_original_error_and_stack_stay_inside_source_frame_budget(self):
        self.execute(r'''
CommunicationManager.CallGameService=()=>{const e=Error('\u{1f984}'.repeat(100000));e.errorID=123;e.getStackTrace=()=> '\u{1f984}'.repeat(100000);throw e;};
readback();const a=acks[0];assert.equal(a.ok,false);assert.ok(a.message.length<=512);assert.equal(a.navigation_diagnostic.error.id,123);
assert.ok(a.navigation_diagnostic.error.message.length<=512);assert.ok(a.navigation_diagnostic.error.stack.length<=2048);
assert.ok(Buffer.byteLength(JSON.stringify(a),'utf8')<32768);assert.equal(scrolls,1);assert.equal(dispatches,0);
''')

    def test_success_has_no_diagnostic_getter_call(self):
        self.execute(r'''
function ApexCatalogGridStatus(){throw Error('success must not call diagnostics');}
pending=false;readback();assert.equal(acks[0].ok,true);assert.equal('navigation_diagnostic'in acks[0],false);
assert.equal(scrolls,1);assert.equal(dispatches,0);
''')

    def test_complete_typed_visibility_timeout_retains_old_exact_host_schema(self):
        self.execute(r'''
function ApexCatalogGridStatus(){throw Error('typed timeout must keep old envelope');}
now+=10000;readback();assert.equal(acks[0].ok,false);assert.equal('navigation_diagnostic'in acks[0],false);
assert.equal(acks[0].navigation_publication.elapsed_ms,10000);assert.equal(scrolls,1);assert.equal(dispatches,0);
''')

    def test_partial_diagnostic_envelope_is_retained_by_unchanged_source_quarantine(self):
        case=host.NavigationPostconditionTests();case.setUp()
        try:
            packet=case.timeout_packet();packet.pop('client');packet['message']='Navigation publication changed its original request, target or catalog [guard=receipt]'
            packet['navigation_publication']['elapsed_ms']=498
            packet['navigation_diagnostic']={'protocol':1,'diagnostic_only':True,'main':{'error':'boom'}}
            with self.assertRaisesRegex(ValueError,'complete same-peer'):
                host.cas_ui.receive_socket(case.peer,case.rid,json.dumps(packet),clock=lambda:1)
            self.assertEqual(host.cas_ui._RECORDS[case.rid]['state'],'pending')
            self.assertEqual(host.cas_ui.result(case.rid)['native_acknowledgement'],packet)
            with self.assertRaisesRegex(ValueError,'unresolved'):
                host.cas_ui.submit('12',{'operation':'status'},clock=lambda:2)
        finally:case.doCleanups()


class ExistingKeyboardCompatibilityTests(keyboard.KeyboardPublicationTests):
    def setUp(self):
        self.prior_keyboard=keyboard.keyboard_method;self.prior_source=keyboard.source_method
        keyboard.keyboard_method=lambda name,params: converted(name,params) if name=='ApexCatalogKeyboardPublicationReady' else self.prior_keyboard(name,params)
        keyboard.source_method=lambda name,params,stop=None: (converted(name,params)+converted('ApexCatalogKeyboardFailureDiagnostic','error,held')) if name=='ApexReadback' else self.prior_source(name,params,stop)
    def tearDown(self):
        keyboard.keyboard_method=self.prior_keyboard;keyboard.source_method=self.prior_source

if __name__=='__main__':unittest.main()
