"""Exact profile-only marker projection and actual scalar trace behavior."""
import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import cas_draw_phase as phase
import cas_catalog_binding as binding
import cas_communication_index as comm


def helper_js():
    source=phase.trace_source().split('private function ApexLayoutTraceDispose',1)[0]
    source=re.sub(r'public static var apexCatalogDrawTraceStep:Function;','',source)
    source=source.replace('private var apexCatalogTrace:Object;','var apexCatalogTrace;')
    source=re.sub(r'private function (\w+)\(([^)]*)\)\s*:\s*\w+',lambda m:'function '+m[1]+'('+re.sub(r':\w+','',m[2])+')',source)
    source=re.sub(r'for each\(var (\w+):\w+ in ([^\n]+)\)',r'for(var \1 of \2)',source)
    source=re.sub(r'\bvar (\w+):\w+',r'var \1',source)
    source=re.sub(r'catch\((\w+):(?:Error|\*)\)',r'catch(\1)',source)
    return source


@unittest.skipUnless(shutil.which('node'),'Node required for actual production AS trace fixtures')
class GranularTraceExecutionTests(unittest.TestCase):
    def case(self,code):
        boot='''let now=0,clocks=0,layoutDisposals=0;
const flash={utils:{getTimer:()=>{clocks++;return now;}}};
const CASCustomizerMain={apexCatalogDrawTraceStep:null};const int=x=>x|0;
function check(v,m){if(!v)throw Error(m);}function ApexLayoutTraceDispose(){layoutDisposals++;}
'''
        r=subprocess.run(['node','-'],input=boot+helper_js()+code,capture_output=True,text=True,timeout=15)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)

    def test_default_disabled_null_callback_has_no_clocks_or_new_phase_work(self):
        self.case('''let s=ApexCatalogTraceStatus();check(s.requested_ms===0&&!s.callback_present,'default');
for(let i=0;i<500;i++){ApexCatalogTraceStep('overlay.enter');ApexCatalogTraceStep('overlay.leave');}
ApexCatalogTraceConfigure(0);check(clocks===0&&layoutDisposals===0,'disabled clock/work');''')

    def test_all_granular_phases_retain_exact_sums_and_only_copied_product_primitives(self):
        self.case('''ApexCatalogTraceConfigure(1000);const product={data_id:'18446744073709551615',body_type:114,private_object:{}};
ApexCatalogTraceStep('draw.enter',product);let elapsed=0;
for(const p of ['overlay','geometry','state','context','tooltip','favorite','super','thumbnail','decoration','swatches','icons']){
 now++;ApexCatalogTraceStep(p+'.enter');now+=3;ApexCatalogTraceStep(p+'.leave');elapsed+=4;
}
now++;ApexCatalogTraceStep('draw.leave');let s=ApexCatalogTraceStatus();check(s.completed===1&&s.errors===0,'completion');
check(s.records[0].total_ms===45&&Object.values(s.records[0].phases).reduce((a,b)=>a+b,0)===45,'sum');
for(const p of ['overlay','geometry','state','context','tooltip'])check(s.aggregates[p].calls===1&&s.aggregates[p].total_ms===3,'phase '+p);
check(s.records[0].id===product.data_id,'uint64 identity');check(!JSON.stringify(s).includes('private_object'),'no borrowed handle');''')

    def test_native_throw_remains_incomplete_until_expiry_no_fabricated_success(self):
        self.case('''ApexCatalogTraceConfigure(20);ApexCatalogTraceStep('draw.enter',{data_id:'arbitrary'});
now=1;ApexCatalogTraceStep('overlay.enter');now=20;let s=ApexCatalogTraceStatus();
check(s.expired&&!s.enabled&&s.completed===0&&s.incomplete[0].phase==='overlay','native exception incomplete');
check(CASCustomizerMain.apexCatalogDrawTraceStep===null,'expired callback released');''')

    def test_record_depth_bound_and_foreign_disposal_remain(self):
        self.case('''ApexCatalogTraceConfigure(30000);
for(let i=0;i<12;i++)ApexCatalogTraceStep('draw.enter',{data_id:String(i),body_type:2});
check(ApexCatalogTraceStatus().incomplete.length===8,'depth');for(let i=0;i<12;i++){now++;ApexCatalogTraceStep('draw.leave');}
for(let i=0;i<40;i++){ApexCatalogTraceStep('draw.enter',{data_id:String(i)});now++;ApexCatalogTraceStep('state.enter');now++;ApexCatalogTraceStep('state.leave');now++;ApexCatalogTraceStep('draw.leave');}
let s=ApexCatalogTraceStatus();check(s.records.length===32&&s.incomplete.length===0,'bounded records');
ApexCatalogTraceConfigure(0);check(CASCustomizerMain.apexCatalogDrawTraceStep===null,'stop callback');''')


WORK=ROOT/'.work/v337-draw-phases'
@unittest.skipUnless((WORK/'chained.json').is_file(),'Frozen private granular Main required')
class GranularContinuationTests(unittest.TestCase):
    def fixture(self):return json.loads((WORK/'chained.json').read_text(encoding='utf-8')),(WORK/'final.swf').read_bytes()

    def refresh(self,r):
        r['previous_stage_sha256']=comm.contract_digest(r['previous_stage_contract']);r['draw_phase_contract']['previous_stage_sha256']=r['previous_stage_sha256'];r['postproof_sha256']=comm.contract_digest(r['draw_phase_contract'])

    def test_exact_profile_only_tail_reconstructs_complete_binding_stage(self):
        r,final=self.fixture();self.assertTrue(phase.verify_contract(r,final));baseline=(WORK/'baseline.swf').read_bytes()
        self.assertEqual(phase.reconstruct_previous(final,r['draw_phase_contract']),baseline)
        self.assertTrue(binding.verify_contract(r['previous_stage_contract'],baseline))
        a=binding._ABC(binding._abc_payload(final)[1]).parse();b=binding._ABC(binding._abc_payload(baseline)[1]).parse()
        self.assertEqual(a.methods['count'],b.methods['count']);self.assertEqual(a.bodies['count'],b.bodies['count'])
        before=phase._named(b,phase.CELL,'Draw')['value'];after=phase._named(a,phase.CELL,'Draw')['value'];code=b.instructions(before['code']);profile=code[6][1]+code[6][3][0]
        self.assertEqual(before['code'][:profile],after['code'][:profile]);self.assertEqual(profile,1590)
        self.assertEqual(r['draw_phase_contract']['phase_sites'],phase.COUNTS)

    def test_rehashed_counts_phase_fidelity_sources_and_history_corruption_refused(self):
        original,final=self.fixture()
        for name,value in [('ok',1),('disabled_added_instructions',False),('changed_draw_bodies',True),('granular_sites',46),('appended_methods',1),('appended_fields',False),
            ('native_throw_propagation_retained',False),('disabled_fast_tail_exact',False),('runtime_qualified',True),('performance_gain_claimed',True),('abc_sha256','0'*64)]:
            r=copy.deepcopy(original);r['draw_phase_contract'][name]=value;self.refresh(r)
            with self.subTest(field=name),self.assertRaises(ValueError):phase.verify_contract(r,final)
        r=copy.deepcopy(original);r['draw_phase_contract']['phase_sites']['overlay']=True;self.refresh(r)
        with self.assertRaises(ValueError):phase.verify_contract(r,final)
        r=copy.deepcopy(original);r['previous_stage_contract']['catalog_binding_contract']['other_four_binds_retained']=False;self.refresh(r)
        with self.assertRaises(ValueError):phase.verify_contract(r,final)
        for source in phase.SOURCES:
            r=copy.deepcopy(original);r['draw_phase_contract']['source_sha256'][source]='0'*64;self.refresh(r)
            with self.subTest(source=source),self.assertRaises(ValueError):phase.verify_contract(r,final)

    def test_unowned_and_owned_native_corruption_with_rehashed_abc_is_refused(self):
        import cas_ui_build as ui
        original,final=self.fixture();prefix,raw=binding._abc_payload(final);a=binding._ABC(raw).parse()
        for owner,name in ((phase.MAIN,'Initialize'),(phase.MAIN,'ApexCatalogTraceStep'),(phase.CELL,'Draw')):
            row=phase._named(a,owner,name);read=attach_reader=binding.attach._ABCReader(raw);read.at=row['start'];read.u30()
            for _ in range(4):read.u30()
            read.u30();at=read.at;bad=bytearray(raw);bad[at]=0xd1
            damaged=ui.replace_payload(final,prefix+bad);r=copy.deepcopy(original);r['draw_phase_contract']['abc_sha256']=phase.digest(bad);r['final_swf_sha256']=phase.digest(damaged);self.refresh(r)
            with self.subTest(method=name),self.assertRaises(ValueError):phase.verify_contract(r,damaged)

    @unittest.skipUnless(shutil.which('javac'),'JDK required for granular native bytecode fixtures')
    def test_compiled_projection_branch_metadata_and_native_corruptions(self):
        with tempfile.TemporaryDirectory(prefix='apex-draw-phase-') as work:
            jar=ROOT/'.work/research/ffdec/ffdec.jar'
            r=subprocess.run(['javac','-cp',str(jar),'-d',work,str(ROOT/'tools/CasStructuralRolesPatch.java'),str(ROOT/'tools/CasCommunicationIndexPatch.java'),str(ROOT/'tools/CasDrawPhasePatch.java'),str(ROOT/'tests/CasDrawPhaseBytecodeFixtures.java')],capture_output=True,text=True,timeout=45)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            r=subprocess.run(['java','-cp',str(jar)+os.pathsep+work,'CasDrawPhaseBytecodeFixtures',str(WORK/'baseline.swf'),str(WORK/'final.swf')],capture_output=True,text=True,timeout=45)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr[-2500:]);self.assertEqual(r.stdout.count('PASS '),11)


if __name__=='__main__':unittest.main()
