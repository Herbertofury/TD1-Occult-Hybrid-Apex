"""Execute actual staged AS bodies; no game/collector/process operations."""
from pathlib import Path
import importlib.util,json,re,subprocess,sys,unittest
STAGE=Path(__file__).resolve().parents[1]
PROJECT=next(p for p in (STAGE,*STAGE.parents) if (p/'tests/test_cas_grid_presentation.py').is_file())
sys.path[:0]=[str(STAGE/'tools'),str(PROJECT/'tools'),str(PROJECT/'tests')]
import cas_publication_stage as stage
import test_cas_grid_presentation as fixture
import test_cas_draw_trace as draw
import test_cas_grid_featured as featured_fixture


def javascript(module):
    before=fixture.stage
    try:fixture.stage=module;return fixture.javascript().replace('{get:function','{configurable:true,get:function')
    finally:fixture.stage=before


def scalar(source):
    source=re.sub(r'private function (\w+)\(([^)]*)\)\s*:\s*\w+',lambda m:'function '+m[1]+'('+re.sub(r':\w+','',m[2])+')',source)
    source=re.sub(r'for each\(var (\w+):\w+ in ([^\n]+)\)',r'for(var \1 of \2)',source)
    source=re.sub(r'\bvar (\w+):\w+',r'var \1',source)
    source=re.sub(r'catch\((\w+):(?:Error|\*)\)',r'catch(\1)',source)
    source=re.sub(r'\s+as\s+[\w.]+','',source)
    return re.sub(r'\bis\b(?=\s+[\w.])','instanceof',source)


def main_source():
    source=featured_fixture.main_source()
    at=source.rfind('   }')
    return source[:at]+(PROJECT/'Source/CASUi/catalog_trace_methods.as').read_text()+'\n'+source[at:]


TRACE=scalar((STAGE/'Source/CASUi/catalog_publication_trace_methods.as').read_text())
TRACE_BOOT='''
const flash={utils:{getTimer:()=>{diagnosticClocks++;return int(time);}}};
let diagnosticClocks=0;
const CASCustomizerMain={apexCatalogDrawTraceStep:null};
function uint(n){return n>>>0;}
function ApexLayoutTraceDispose(){}
let apexPendingPhase=0,apexPendingFields=null,apexReceiving=false,apexWire='',apexFormsIntent=null;
function enable(g,ms=30000){ApexCatalogTraceConfigure(ms);return request(g,6,{viewHeight:400,
 publicationTraceStep:ApexCatalogPublicationTraceStep,publicationTraceGeneration:int(apexCatalogTrace.generation)});}
function seekPublish(g){
 const advance=g.ApexTxnAdvance;g.ApexTxnAdvance=function(j){return j.phase==='publish'?false:advance.call(this,j);};
 try{for(let i=0;i<3000&&g.ApexGridStatus().phase!=='publish';i++)g.ApexGridStep(1,0);assert.equal(g.ApexGridStatus().phase,'publish');}
 finally{g.ApexTxnAdvance=advance;}
}
'''


class PublicationTests(unittest.TestCase):
    def case(self,code):
        mock=fixture.NATIVE_MOCK.replace('const getTimer=()=>time;','let allClocks=0;const getTimer=()=>{allClocks++;return Math.trunc(time);};')
        text=mock+javascript(stage)+fixture.BOOT+TRACE_BOOT+draw.helper_js()+TRACE+code
        result=subprocess.run(['node','-'],input=text,text=True,capture_output=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    def test_marker_stripped_complete_helpers_match_without_relaxed_calls(self):
        self.assertEqual(stage.compact(stage.strip(stage.helpers())),stage.compact(stage.previous.helpers()))
        source=stage.helpers()
        for marker in ('pretexture','resize','posttexture','visibility','diagnostics','tail','publication'):
            self.assertIn('"'+marker+'.enter"',source)
        emit=(STAGE/'Source/CASUi/catalog_grid_publication_trace_emit.as').read_text()
        self.assertIn('catch(diagnosticError:*)',emit)
        self.assertNotIn('getTimer(',emit)
    def test_actual_four_recovered_methods_have_identical_acorn_ast(self):
        provider=stage.helpers();original=stage.previous.helpers();baseline=main_source();main=stage.main(baseline)
        pairs=[]
        for before,after,names in ((original,provider,stage.GRID_REPLACED),(baseline,main,stage.MAIN_REPLACED)):
            for name in names:
                a,b=stage.pool.method_extent(before,name);old=before[a:b]
                a,b=stage.pool.method_extent(after,name);actual=after[a:b]
                pairs.append([name,scalar(old),scalar(actual),scalar(stage.strip(actual))])
        code='''const vm=require('vm'),moduleCopy={exports:{}};
vm.runInNewContext(process.binding('natives')['internal/deps/acorn/acorn/dist/acorn'],{module:moduleCopy,exports:moduleCopy.exports});
const acorn=moduleCopy.exports,pairs=JSON.parse(require('fs').readFileSync(0,'utf8'));
const clean=(k,v)=>['start','end','raw'].includes(k)?undefined:v;
for(const [name,before,actual,recovered] of pairs){
 const old=JSON.stringify(acorn.parse(before,{ecmaVersion:2022}),clean);
 acorn.parse(actual,{ecmaVersion:2022});
 if(old!==JSON.stringify(acorn.parse(recovered,{ecmaVersion:2022}),clean))throw Error(name+' original AST differs');
}console.log('PASS4 recovered ASTs');'''
        result=subprocess.run(['node','-e',code],input=json.dumps(pairs),text=True,capture_output=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr);self.assertIn('PASS4',result.stdout)
        self.assertEqual(stage.compact(stage.strip(main)),stage.compact(baseline))
    def test_disabled_native_work_and_clock_counts_equal_original(self):
        base=javascript(stage.previous)
        private=javascript(stage)
        # The same actual-AS fixture runs with each precise predecessor/helper
        # set; only scalar snapshots are compared, never implementation mirrors.
        self.case('''
'''+base+'''
const a=new NativeGrid(100,0);allClocks=0;a.ApexGridBegin(request(a,6,{viewHeight:400}));bounded(a);
const expected={calls:a.calls.slice(),clock:allClocks,time:time,status:a.ApexGridStatus().counts,ids:rendered(a)};
'''+private+'''
time=0;allClocks=0;const b=new NativeGrid(100,0);b.ApexGridBegin(request(b,6,{viewHeight:400}));bounded(b);
assert.deepEqual(b.calls,expected.calls);assert.equal(allClocks,expected.clock);assert.equal(time,expected.time);
assert.deepEqual(b.ApexGridStatus().counts,expected.status);assert.deepEqual(rendered(b),expected.ids);
assert.equal(diagnosticClocks,0);assert.equal(apexCatalogTrace,undefined);
''')
    def test_resize_inclusive_duration_identifies_injected177ms_callback(self):
        self.case('''
const g=new NativeGrid(100,0);g.ApexGridBegin(enable(g));g.hooks.resize=()=>{time+=177;};assert.equal(bounded(g).phase,'done');
const p=apexCatalogTrace.publication_profile;
assert.equal(p.errors,0);assert.equal(p.aggregates.publication.completed,1);
assert.ok(p.aggregates.resize.max_ms>=177);assert.ok(p.aggregates.publication.max_ms>=177);
for(const n of ['pretexture','resize','posttexture','visibility','diagnostics','tail'])assert.equal(p.aggregates[n].completed,1,n);
assert.equal(p.records[0].target,g.mCells.length);assert.equal(p.records[0].old_count,0);
assert.ok(!p.records[0].interrupted);assert.ok(g.mGridView.mouseChildren);
''')
    def test_arbitrary_diagnostic_throw_changes_no_publication_outcome(self):
        self.case('''
const g=new NativeGrid(100,0),seen=[];const r=request(g,6,{viewHeight:400,publicationTraceStep:(...a)=>{seen.push(a);throw 'diagnostic-only';},publicationTraceGeneration:9});
g.ApexGridBegin(r);assert.equal(bounded(g).phase,'done');assert.equal(g.apexGridState.job.publishes,1);assert.ok(g.mGridView.mouseChildren);
assert.ok(seen.length>=14);assert.ok(seen.every(a=>a.length===4&&typeof a[0]==='string'&&a.slice(1).every(x=>typeof x==='number')));
''')
    def test_actual_native_throw_keeps_same_value_rolls_back_and_records_interrupted(self):
        self.case('''
const g=new NativeGrid(100,0);g.ApexGridBegin(enable(g));seekPublish(g);const old=g.mCells.slice(),sentinel={native:'unchanged'};
g.hooks.resize=()=>{time+=9;throw sentinel;};let thrown=null;try{g.ApexTxnAdvance(g.apexGridState.job);}catch(e){thrown=e;}
assert.equal(thrown,sentinel);assert.deepEqual(g.mCells,old);assert.equal(g.apexGridState.job.publishing,false);
const p=apexCatalogTrace.publication_profile;assert.equal(p.aggregates.publication.completed,0);assert.equal(p.aggregates.publication.interrupted,1);
assert.equal(p.aggregates.resize.interrupted,1);assert.equal(p.stack.length,0);
''')
    def test_reentrant_resize_owner_change_cannot_publish_stale_data(self):
        self.case('''
const g=new NativeGrid(100,0);g.ApexGridBegin(enable(g));seekPublish(g);const old=g.mCells.slice();g.hooks.resize=()=>{g.lease.active=false;};
g.ApexTxnAdvance(g.apexGridState.job);assert.deepEqual(g.mCells,old);assert.ok(g.apexGridState.job.cancelled);
const p=apexCatalogTrace.publication_profile;assert.equal(p.aggregates.publication.completed,0);assert.equal(p.aggregates.publication.interrupted,1);
''')
    def test_postcallback_resource_change_keeps_original_texture_fence(self):
        self.case('''
const g=new NativeGrid(100,0);g.ApexGridBegin(enable(g));seekPublish(g);const old=g.mCells.slice();
g.hooks.resize=()=>{g.apexGridState.presentation.stageCells[0].mcImage.resourceId='wrong-resource';};g.apexGridState.job.running=true;
try{g.ApexTxnAdvance(g.apexGridState.job);}finally{g.apexGridState.job.running=false;}
assert.deepEqual(g.mCells,old);assert.ok(g.apexGridState.job.dirty);
const p=apexCatalogTrace.publication_profile;assert.equal(p.aggregates.posttexture.interrupted,1);assert.equal(p.aggregates.publication.completed,0);
''')
    def test_missing_prepublication_texture_still_throws_before_native_resize(self):
        self.case('''
const g=new NativeGrid(100,0);g.ApexGridBegin(enable(g));seekPublish(g);g.apexGridState.presentation.stageCells[0].mcImage.ready=false;
const before=g.calls.filter(x=>x==='resize').length;assert.throws(()=>g.ApexTxnAdvance(g.apexGridState.job),/not ready/);
assert.equal(g.calls.filter(x=>x==='resize').length,before);assert.equal(apexCatalogTrace.publication_profile.aggregates.pretexture.interrupted,1);
''')
    def test_old_generation_cannot_allocate_profile_or_read_clock(self):
        self.case('''
ApexCatalogTraceConfigure(30000);const old=apexCatalogTrace.generation;ApexCatalogTraceConfigure(30000);const before=diagnosticClocks;
ApexCatalogPublicationTraceStep('publication.enter',old,240,240);assert.equal(diagnosticClocks,before);assert.equal(apexCatalogTrace.publication_profile,undefined);
''')
    def test_expiry_midspan_records_interruption_then_zero_stale_session_clocks(self):
        self.case('''
ApexCatalogTraceConfigure(10);let gen=apexCatalogTrace.generation;ApexCatalogPublicationTraceStep('publication.enter',gen,240,0);
time=2;ApexCatalogPublicationTraceStep('resize.enter',gen,240,0);time=12;ApexCatalogPublicationTraceStep('resize.leave',gen,240,0);
assert.ok(!apexCatalogTrace.enabled);ApexCatalogPublicationTraceStep('publication.leave',gen,240,0);
assert.equal(apexCatalogTrace.publication_profile.aggregates.publication.interrupted,1);
assert.equal(apexCatalogTrace.publication_profile.aggregates.resize.completed,0);
const before=diagnosticClocks;for(let i=0;i<30;i++)for(const e of ['publication.enter','resize.enter','resize.leave','publication.leave'])ApexCatalogPublicationTraceStep(e,gen,240,0);
assert.equal(diagnosticClocks,before);
''')
    def test_depth_and_record_limits_hold_only_primitives(self):
        self.case('''
ApexCatalogTraceConfigure(30000);const gen=apexCatalogTrace.generation;
for(let i=0;i<12;i++)ApexCatalogPublicationTraceStep('publication.enter',gen,240,100);
assert.equal(apexCatalogTrace.publication_profile.stack.length,8);assert.equal(apexCatalogTrace.publication_profile.overflow,4);
for(let i=0;i<12;i++){time++;ApexCatalogPublicationTraceStep('publication.leave',gen,240,100);}
for(let i=0;i<40;i++){ApexCatalogPublicationTraceStep('publication.enter',gen,240,0);time+=i+1;ApexCatalogPublicationTraceStep('publication.leave',gen,240,0);}
const p=apexCatalogTrace.publication_profile;assert.equal(p.stack.length,0);assert.equal(p.records.length,16);assert.equal(p.overflow,0);
function primitive(v){if(v===null||typeof v!=='object')return ['string','number','boolean'].includes(typeof v)||v===null;return Object.values(v).every(primitive);}
assert.ok(primitive(p));assert.ok(!JSON.stringify(p).includes('data_id'));
''')
    def test_signed_rollover_preserves_short_elapsed_durations(self):
        self.case('''
time=2147483646;ApexCatalogTraceConfigure(100);const gen=apexCatalogTrace.generation;ApexCatalogPublicationTraceStep('publication.enter',gen,240,0);
time+=2;ApexCatalogPublicationTraceStep('resize.enter',gen,240,0);time+=7;ApexCatalogPublicationTraceStep('resize.leave',gen,240,0);
ApexCatalogPublicationTraceStep('publication.leave',gen,240,0);assert.equal(apexCatalogTrace.publication_profile.aggregates.resize.max_ms,7);
assert.equal(apexCatalogTrace.publication_profile.aggregates.publication.max_ms,9);
''')
    def test_diagnostic_helper_has_no_services_catalog_or_handle_capture(self):
        source=(STAGE/'Source/CASUi/catalog_publication_trace_methods.as').read_text()
        for forbidden in ('CallGameService','CallUIService','ApexNativeExchange','new Timer','new Socket','FileReference','GetDataAtIndex','getChildAt'):
            self.assertNotIn(forbidden,source)
        self.assertIn('record_limit:16,depth_limit:8',source)
        self.assertIn('no CPU or GC attribution',source)


if __name__=='__main__':unittest.main()
