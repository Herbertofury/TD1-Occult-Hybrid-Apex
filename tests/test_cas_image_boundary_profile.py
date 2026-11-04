"""Behavior and serialized native-flow gates for explicit image diagnostics."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'tests'))
import cas_image_boundary_profile as image
import test_cas_communication_index as old


@unittest.skipUnless(shutil.which('node'),'Node required for extracted AS behavior')
class ImageTraceSemanticsTests(unittest.TestCase):
    def execute(self,test):
        source=image.LOADER_HELPERS.replace(' final ',' ').replace('function get ApexImageTraceActive','function ApexImageTraceActive')
        methods=old.functions(source);script='''const assert=require('node:assert/strict');
let apexImageTraceState=null,apexImageTraceAccepting=false,apexImageTraceFault=false,apexImageTraceRequested=0;
let clock=1000,clockCalls=0;function getTimer(){clockCalls++;return clock;}function int(n){return Math.trunc(n);}function uint(n){return n>>>0;}
class Loader{\n'''
        for name,(params,body)in methods.items():
            if name=='ApexImageTraceStamp':body='try{'+body+'}catch(error){apexImageTraceAccepting=false;apexImageTraceFault=true;}'
            text=old.method(name,params,body)
            if name=='ApexImageTraceActive':text='get '+text
            script+=text
        script+='}\n'
        wrappers=old.functions(image.RESOURCE_HELPERS.replace(' final ',' '));script+='class Resource{constructor(loader){this.mLoader=loader;}\n'
        for name,(params,body)in wrappers.items():script+=old.method(name,params,body)
        script+='}\n'+test
        r=subprocess.run(['node'],input=script,capture_output=True,text=True,timeout=20)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)

    def test_default_disabled_and_status_do_not_clock_or_mutate_trace(self):
        self.execute(r'''
const loader=new Loader(),resource=new Resource(loader);
for(let j=0;j<2000;j++)assert.equal(loader.ApexImageTraceActive,false);
const s=resource.ApexImageTraceStats();assert.equal(s.available,true);assert.equal(s.enabled,false);assert.equal(s.requested_budget,0);
assert.equal(s.phases.length,5);assert.equal(s.record_limit,0);assert.equal(clockCalls,0);assert.equal(apexImageTraceState,null);
for(const row of s.phases)assert.deepEqual([row.count,row.total_ms,row.max_ms],[0,0,0]);
''')

    def test_budget_nested_spans_and_draining_ignored_markers_are_bounded(self):
        self.execute(r'''
const l=new Loader();let s=l.ApexImageTraceEnable(3);assert.equal(s.generation,1);assert.equal(s.enabled,true);assert.equal(clockCalls,0);
l.ApexImageTraceStamp(0,true);clock+=2;l.ApexImageTraceStamp(1,true);clock+=5;l.ApexImageTraceStamp(1,false);clock+=3;l.ApexImageTraceStamp(0,false);
s=l.ApexImageTraceStats();assert.deepEqual([s.started,s.completed,s.open_depth],[2,2,0]);assert.equal(s.phases[0].total_ms,10);assert.equal(s.phases[1].total_ms,5);
l.ApexImageTraceStamp(2,true);assert.equal(l.ApexImageTraceActive,false);clock+=4;const before=clockCalls;
l.ApexImageTraceStamp(3,true);clock+=9;l.ApexImageTraceStamp(3,false);assert.equal(clockCalls,before);clock+=1;l.ApexImageTraceStamp(2,false);
s=l.ApexImageTraceStats();assert.deepEqual([s.started,s.completed,s.open_depth],[3,3,0]);assert.equal(s.phases[2].total_ms,14);assert.equal(s.phases[3].count,0);assert.equal(s.diagnostic_error,false);
const completed=JSON.stringify(s.phases);l.ApexImageTraceEnable(0);assert.equal(JSON.stringify(l.ApexImageTraceStats().phases),completed);
l.ApexImageTraceEnable(4);assert.equal(l.ApexImageTraceStats().generation,2);assert.equal(l.ApexImageTraceStats().completed,0);
''')

    def test_depth_fault_counter_wrap_and_status_aliases_cannot_change_native_objects(self):
        self.execute(r'''
const l=new Loader();l.ApexImageTraceEnable(40);for(let j=0;j<33;j++)l.ApexImageTraceStamp(0,true);
let s=l.ApexImageTraceStats();assert.equal(s.open_depth,32);assert.equal(s.max_depth,32);assert.equal(s.diagnostic_error,true);assert.equal(l.ApexImageTraceActive,false);
const before=clockCalls;l.ApexImageTraceStamp(0,false);assert.equal(clockCalls,before);assert.equal(l.ApexImageTraceStats().open_depth,32);
l.ApexImageTraceEnable(2);clock=0xfffffffe;l.ApexImageTraceStamp(4,true);clock=3;l.ApexImageTraceStamp(4,false);
s=l.ApexImageTraceStats();assert.equal(s.phases[4].total_ms,5);s.phases[4].total_ms=99999;assert.equal(l.ApexImageTraceStats().phases[4].total_ms,5);
assert.equal(new Resource(null).ApexImageTraceStats().reason,'loader-probe-unavailable');
assert.equal(new Resource({}).ApexImageTraceEnable(1).reason,'loader-probe-unavailable');
''')

    def test_original_throw_stays_original_and_own_diagnostic_fault_stops_trace(self):
        self.execute(r'''
const l=new Loader();l.ApexImageTraceEnable(10);const nativeError=Error('native image failure');
function native(){l.ApexImageTraceStamp(0,true);throw nativeError;}
let seen;try{native();}catch(error){seen=error;}assert.equal(seen,nativeError);
let s=l.ApexImageTraceStats();assert.equal(s.open_depth,1);assert.equal(s.completed,0);assert.equal(s.phases[0].total_ms,0);
l.ApexImageTraceEnable(10);apexImageTraceState.times=new Proxy([],{set(){throw Error('diagnostic allocation failure');}});
assert.doesNotThrow(()=>l.ApexImageTraceStamp(0,true));assert.equal(l.ApexImageTraceActive,false);assert.equal(l.ApexImageTraceStats().diagnostic_error,true);
''')


@unittest.skipUnless((ROOT/'.work/v334-image-profile-dependency/chained.json').exists()and shutil.which('javac'),'Private three-provider profiler artifacts/JDK required')
class CompiledImageTraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='apex-image-trace-');cls.addClassCleanup(cls.temp.cleanup);cls.jar=ROOT/'.work/research/ffdec/ffdec.jar'
        r=subprocess.run(['javac','-cp',str(cls.jar),'-d',cls.temp.name,str(ROOT/'tools/CasStructuralRolesPatch.java'),
            str(ROOT/'tools/CasCommunicationIndexPatch.java'),str(ROOT/'tools/CasImageBoundaryProfilePatch.java'),
            str(ROOT/'tests/CasImageBoundaryProfileBytecodeFixtures.java')],capture_output=True,text=True,timeout=60)
        if r.returncode:raise AssertionError(r.stdout+r.stderr)
        cls.command=['java','-cp',str(cls.jar)+os.pathsep+cls.temp.name,'CasImageBoundaryProfileBytecodeFixtures']

    def test_all_three_disabled_enabled_native_projections_and_corruption_gates(self):
        for kind in('canonical','donor','dependency'):
            r=subprocess.run(self.command+[str(ROOT/('.work/v333-removal-miss-'+kind)/'final.swf'),str(ROOT/('.work/v334-image-profile-'+kind)/'final.swf')],capture_output=True,text=True,timeout=90)
            with self.subTest(kind=kind):self.assertEqual(r.returncode,0,r.stdout+r.stderr[-3000:]);self.assertEqual(r.stdout.count('PASS '),17)

    def test_separate_profile_stage_cannot_relabel_native_history_or_optimization(self):
        for kind in('canonical','donor','dependency'):
            work=ROOT/('.work/v334-image-profile-'+kind);record=json.loads((work/'chained.json').read_text());final=(work/'final.swf').read_bytes();self.assertTrue(image.verify_adapter(record,final))
            for field,value in [('native_disabled_projection_verified',False),('native_enabled_projection_verified',False),('native_exceptions_not_intercepted',False),
                    ('disabled_no_allocation_clock_counter',False),('native_input_mode_oracle_verified',False),('budget_limit',5000),('runtime_qualified',True),('optimization_claimed',True)]:
                changed=copy.deepcopy(record);changed['image_boundary_profile_contract'][field]=value
                with self.subTest(kind=kind,field=field),self.assertRaises(ValueError):image.verify_adapter(changed,final)
            changed=copy.deepcopy(record);changed['previous_stage_adapter']['base_resource_sha256']='0'*64
            with self.assertRaises(ValueError):image.verify_adapter(changed,final)
            with self.assertRaises(ValueError):image.verify_adapter(record,(ROOT/('.work/v333-removal-miss-'+kind)/'final.swf').read_bytes())


if __name__=='__main__':unittest.main()
