"""Exercise the real AS wrapper and reject incomplete layout timing receipts."""
import copy
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'Source'), str(ROOT / 'tools')]
from apex_core import cas_controls
from apex_cli import parser

PHASES = ('setup_ms', 'position_ms', 'bind_ms', 'resize_ms', 'total_ms')


class LayoutTraceProtocolTests(unittest.TestCase):
    def receipt(self):
        return dict(control=dict(operation='catalog-layout-trace', appearance_written=False, trace=dict(
            requested_ms=30000, enabled=True, available=True, appearance_written=False, generation=1,
            record_limit=16, records=[], completed=0, suppressed=0, errors=0,
            aggregates={key: dict(calls=0, total_ms=0, max_ms=0) for key in PHASES})))

    def test_public_duration_bounds_and_no_panel_navigation(self):
        for duration in (0, 1, 30000):
            self.assertEqual(parser().parse_args(['cas', 'catalog-layout-trace', '--state', 'test.json', '--milliseconds', str(duration)]).milliseconds, duration)
            self.assertEqual(cas_controls.wire(dict(operation='catalog-layout-trace', milliseconds=duration),
                                             lambda _: self.fail('Diagnostic cannot navigate')), (0, 0, 0, str(duration)))
        for duration in (-1, 30001, True, False, 1.2, None, '1'):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                cas_controls.wire(dict(operation='catalog-layout-trace', milliseconds=duration), None)

    def test_complete_phase_counts_and_primitive_receipts(self):
        request = dict(operation='catalog-layout-trace', milliseconds=30000)
        client = self.receipt()
        cas_controls.validate(client, request)
        trace = client['control']['trace']
        trace['completed'] = 1
        trace['records'] = [dict(provider='62ECC59A:00000000:12272E1AC0C1F8E2', before_count=48, after_count=640,
                                 setup_ms=10, position_ms=2, bind_ms=20, resize_ms=3, total_ms=35)]
        for phase in PHASES:
            trace['aggregates'][phase] = dict(calls=1, total_ms=trace['records'][0][phase], max_ms=trace['records'][0][phase])
        cas_controls.validate(client, request)
        for key, value in [('completed', True), ('errors', -1), ('record_limit', True), ('appearance_written', True),
                           ('requested_ms', 2), ('records', [{}] * 17), ('aggregates', {}), ('enabled', 1)]:
            bad = copy.deepcopy(client); bad['control']['trace'][key] = value
            with self.subTest(key=key), self.assertRaises(cas_controls.PostconditionMismatch):
                cas_controls.validate(bad, request)
        for key, value in [('provider', 'foreign'), ('before_count', -1), ('after_count', True), ('bind_ms', 36), ('setup_ms', float('nan'))]:
            bad = copy.deepcopy(client); bad['control']['trace']['records'][0][key] = value
            with self.subTest(key=key), self.assertRaises(cas_controls.PostconditionMismatch):
                cas_controls.validate(bad, request)
        bad = copy.deepcopy(client); bad['control']['trace']['aggregates']['bind_ms']['calls'] = 0
        with self.assertRaises(cas_controls.PostconditionMismatch): cas_controls.validate(bad, request)


@unittest.skipUnless(shutil.which('node'), 'Node is required for actual AS execution')
class LayoutTraceExecutionTests(unittest.TestCase):
    def run_body(self, checks):
        source = (ROOT / 'Source/CASUi/catalog_layout_trace_methods.as').read_text(encoding='utf-8')
        code = '''const assert=require('node:assert/strict');
var apexLayoutTrace=null,now=0,clockCalls=0,drawDisposed=0;
var flash={utils:{getTimer(){clockCalls++;return now;}}};
const int=Math.trunc,Boolean=global.Boolean;
function ApexCatalogTraceDispose(){drawDisposed++;}
'''
        for name, parameters in [('ApexLayoutTraceConfigure', 'milliseconds'), ('ApexLayoutTraceDispose', ''),
                                 ('ApexLayoutTraceStatus', ''), ('ApexLayoutReset', 'grid')]:
            part = source.split('private function ' + name + '(', 1)[1]
            part = re.split(r'\n      private (?:function|var) ', part, maxsplit=1)[0]
            body = part.split('{', 1)[1].rsplit('}', 1)[0]
            body = re.sub(r'\b(var\s+\w+)\s*:\s*[\w.]+', r'\1', body)
            body = re.sub(r'for each\((?:var )?(\w+) in ([^\n]+?)\)', r'for(var \1 of \2)', body)
            body = body.replace('catch(nativeError:*)', 'catch(nativeError)')
            code += 'function ' + name + '(' + parameters + '){' + body + '}\n'
        code += '''let original=0,profile=0;
const grid={ResetAndPositionCells(){original++;},ApexProfileResetAndPositionCells(){profile++;return {suppressed:false,before_count:48,after_count:640,setup_ms:10,position_ms:2,bind_ms:20,resize_ms:3,total_ms:35};},
    ApexGridProviderIdentity(){return '62ECC59A:00000000:12272E1AC0C1F8E2';}};
'''+checks
        result = subprocess.run(['node'], input=code, text=True, encoding='utf-8', capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_disabled_expired_and_suppressed_do_not_duplicate_native_work(self):
        self.run_body('''ApexLayoutReset(grid);assert.equal(original,1);assert.equal(clockCalls,0);
ApexLayoutTraceConfigure(1);assert.equal(drawDisposed,1);now=2;ApexLayoutReset(grid);
assert.equal(original,2);assert.equal(profile,0);assert.equal(apexLayoutTrace.enabled,false);
ApexLayoutTraceConfigure(30000);grid.ApexProfileResetAndPositionCells=()=>{profile++;return {suppressed:true};};
ApexLayoutReset(grid);assert.equal(profile,1);assert.equal(original,2);assert.equal(apexLayoutTrace.suppressed,1);assert.equal(apexLayoutTrace.completed,0);
''')

    def test_completed_aggregates_are_bounded_and_store_no_grid_objects(self):
        self.run_body('''ApexLayoutTraceConfigure(30000);for(let i=0;i<40;i++)ApexLayoutReset(grid);
assert.equal(original,0);assert.equal(profile,40);assert.equal(apexLayoutTrace.records.length,16);
const status=ApexLayoutTraceStatus();assert.equal(status.completed,40);assert.equal(status.aggregates.bind_ms.total_ms,800);
assert.equal(status.aggregates.total_ms.max_ms,35);assert.equal(status.appearance_written,false);
assert.ok(!JSON.stringify(status).includes('ResetAndPositionCells'));
ApexLayoutTraceConfigure(0);const clocks=clockCalls;ApexLayoutReset(grid);assert.equal(clockCalls,clocks);assert.equal(original,1);
''')

    def test_native_exception_propagates_once_and_disables_diagnostics(self):
        self.run_body('''ApexLayoutTraceConfigure(30000);const failure=new Error('native failed');
grid.ApexProfileResetAndPositionCells=()=>{profile++;throw failure;};
assert.throws(()=>ApexLayoutReset(grid),error=>error===failure);assert.equal(profile,1);assert.equal(original,0);
assert.equal(apexLayoutTrace.errors,1);assert.equal(apexLayoutTrace.enabled,false);assert.equal(apexLayoutTrace.completed,0);
''')


if __name__ == '__main__': unittest.main()
