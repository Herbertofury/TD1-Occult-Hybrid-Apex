"""Behavioral equivalence + actual compiled gates for native listener indexing."""
import json
import copy
import tempfile
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import cas_communication_index as comm
SOURCE=ROOT/'.work/research/maru-dynamic/62ECC59A-00000000-89D13757C58C2E05/scripts/olympus/io/CommunicationObject.as'


def functions(source):
    out={}
    for m in re.finditer(r'(?:public|private|protected)(?: static)? function (\w+)\(([^)]*)\)(?:\s*:\s*[\w.*]+)?\s*\{',source):
        at=m.end();depth=1;end=at
        while depth:
            depth+=(source[end]=='{')-(source[end]=='}');end+=1
        out[m.group(1)]=(m.group(2),source[at:end-1])
    return out


def method(name,params,body):
    params=re.sub(r':\s*[\w.*]+','',params)
    body=re.sub(r'\b(var\s+\w+)\s*:\s*[\w.*]+',r'\1',body)
    body=re.sub(r'catch\((\w+):[\w.*]+\)',r'catch(\1)',body)
    body=re.sub(r'for each\((var )?(\w+) in ([^\n)]+)\)',r'for(var \2 of \3)',body)
    for field in ('apexCommIndex','apexCommAliased','mFunctions'):
        body=re.sub(r'(?<![\w.])'+field+r'\b','this.'+field,body)
    for fn in comm.HELPERS.split('private function ')[1:]:
        fn=fn.split('(',1)[0];body=re.sub(r'(?<![\w.])'+fn+r'\(', 'this.'+fn+'(',body)
    body=re.sub(r'(?<![\w.])HasFunction\(','this.HasFunction(',body)
    # Explicit model of AS Dictionary object keys. JS bracket access would
    # stringify Function keys, so use native Map methods instead.
    body=re.sub(r'(made|this\.apexCommIndex)\[([^\]]+)\]=true;',r'\1.set(\2,true);',body)
    body=re.sub(r'delete (made|this\.apexCommIndex)\[([^\]]+)\];',r'\1.delete(\2);',body)
    body=re.sub(r'(made|this\.apexCommIndex)\[([^\]]+)\]',r'\1.get(\2)',body)
    return name+'('+params+'){'+body+'}\n'


@unittest.skipUnless(SOURCE.exists() and shutil.which('node'),'Private native source and Node required')
class CommunicationIndexSemanticsTests(unittest.TestCase):
    def harness(self):
        native=functions(SOURCE.read_text())
        patched=dict(native)
        p,b=patched['GetFunctions'];patched['GetFunctions']=(p,'this.ApexCommExpose();'+b)
        p,b=patched['HasFunction'];patched['HasFunction']=(p,'if(this.ApexCommCanIndex(param1))return this.ApexCommIndexedHas(param1);'+b)
        p,b=patched['AddFunction'];a='this.mFunctions.push(new WidgetFunction(param1,param2));';assert b.count(a)==1
        patched['AddFunction']=(p,b.replace(a,a+'this.ApexCommAdded(param2);'))
        p,b=patched['RemoveFunction'];a='this.mFunctions.splice(_loc3_,1);';assert b.count(a)==1
        patched['RemoveFunction']=(p,b.replace(a,a+'this.ApexCommRemoved(param2);'))
        p,b=patched['RemoveWidgetsFunctions'];a='this.mFunctions.splice(_loc2_,1);';assert b.count(a)==1
        patched['RemoveWidgetsFunctions']=(p,b.replace(a,a+'this.ApexCommRemoved(_loc3_.mFunction);'))
        patched.update(functions(comm.HELPERS))
        pre=r'''
const assert=require('node:assert/strict');
function int(n){return Math.trunc(n);}
var reads=0,dictionaries=0,brokenEligibility=false,failAllocate=false,failWrite=false,failDelete=false;
var apexCommBuilt=0,apexCommCalls=0,apexCommAlias=0,apexCommEligibility=0,apexCommErrors=0;
class WidgetFunction{constructor(name,fn){this.mWidgetName=name;this.fn=fn;}get mFunction(){reads++;return this.fn;}set mFunction(v){this.fn=v;}}
class Dictionary extends Map{constructor(weak){if(failAllocate)throw Error('allocation refused');super();assert.equal(weak,true);dictionaries++;}
 set(k,v){if(failWrite)throw Error('write refused');return super.set(k,v);}get(k){return brokenEligibility?undefined:super.get(k);}delete(k){if(failDelete)throw Error('delete refused');return super.delete(k);}}
function rows(o){return o.mFunctions.map(r=>r==null?r:[r.mWidgetName,r.mFunction]);}
'''
        for kind,items in [('Native',native),('Indexed',patched)]:
            pre+='class '+kind+'{\nconstructor(name,fn){this.mbDispatching=false;this.mPendingRemoval=null;this.apexCommIndex=null;this.apexCommAliased=false;this.mFunctions=[new WidgetFunction(name,fn)];}\n'
            for name,(params,body) in items.items():
                if name!='CommunicationObject':pre+=('static ' if name=='ApexCommIndexStats' else '')+method(name,params,body)
            pre+='}\n'
        return pre

    def execute(self,body):
        r=subprocess.run(['node'],input=self.harness()+body,capture_output=True,text=True,timeout=20)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)

    def test_add_has_remove_preserves_reference_identity_widget_match_and_order(self):
        self.execute(r'''
const a=()=>1,b=()=>1,c=()=>3,missing=()=>0;const n=new Native('a',a),i=new Indexed('a',a);
for(const [method,args] of [['HasFunction',[a]],['HasFunction',[b]],['AddFunction',['b',b]],['AddFunction',['other',a]],
 ['AddFunction',['c',c]],['RemoveFunction',['wrong',b]],['RemoveFunction',['b',b]],['HasFunction',[b]],
 ['AddFunction',['b',b]],['RemoveWidgetsFunctions',['c']],['HasFunction',[missing]]]){
 assert.deepEqual(n[method](...args),i[method](...args),method);assert.deepEqual(rows(n),rows(i),method);}
assert.deepEqual(rows(i).map(r=>r[0]),['a','b']);
''')

    def test_dispatch_order_deferred_removal_nested_dispatch_and_additions_match_native(self):
        self.execute(r'''
function a(p){p.log.push('a'+p.depth);if(!p.depth){p.obj.RemoveFunction('b',b);p.obj.AddFunction('c',c);p.obj.Dispatch({obj:p.obj,log:p.log,depth:1});}}
function b(p){p.log.push('b'+p.depth);}function c(p){p.log.push('c'+p.depth);}
function run(Type){const o=new Type('a',a);o.AddFunction('b',b);const log=[];o.Dispatch({obj:o,log,depth:0});return{log,rows:rows(o),dispatching:o.mbDispatching,pending:o.mPendingRemoval};}
assert.deepEqual(run(Native),run(Indexed));
''')

    def test_queued_widget_removal_does_not_delete_membership_before_native_drain(self):
        self.execute(r'''
function a(p){p.log.push('a');p.obj.RemoveWidgetsFunctions('b');p.log.push(p.obj.HasFunction(b));p.log.push(p.obj.AddFunction('b',b));}
function b(p){p.log.push('b');}
for(const Type of [Native,Indexed]){const o=new Type('a',a);o.AddFunction('b',b);const log=[];o.Dispatch({obj:o,log});
 assert.deepEqual(log,['a',true,false,'b']);assert.equal(o.HasFunction(b),false);assert.deepEqual(rows(o),[['a',a]]);}
''')

    def test_live_array_and_mutable_row_aliases_permanently_use_original_scan(self):
        self.execute(r'''
const a=()=>1,b=()=>2,c=()=>3;for(const Type of [Native,Indexed]){const o=new Type('a',a);o.HasFunction(a);
 const exposed=o.GetFunctions();assert.equal(exposed,o.mFunctions);exposed[0].mFunction=b;exposed.push(new WidgetFunction('c',c));
 assert.equal(o.HasFunction(a),false);assert.equal(o.HasFunction(b),true);assert.equal(o.HasFunction(c),true);
 exposed.splice(0,1);assert.equal(o.HasFunction(b),false);exposed.fixed=true;assert.equal(o.AddFunction('a',a),false);
 if(Type===Indexed){assert.equal(o.apexCommAliased,true);assert.equal(o.apexCommIndex,null);}}
''')

    def test_null_functions_and_callback_exception_behavior_match_original(self):
        self.execute(r'''
for(const Type of [Native,Indexed]){const o=new Type('null',null);assert.equal(o.HasFunction(null),true);const a=()=>{};
 assert.equal(o.AddFunction('again',null),false);assert.equal(o.AddFunction('a',a),true);assert.equal(o.RemoveFunction('null',null),true);assert.equal(o.HasFunction(null),false);}
function bad(p){p.log.push('bad');throw Error('callback error');}
for(const Type of [Native,Indexed]){const o=new Type('bad',bad);const log=[];assert.throws(()=>o.Dispatch({log}),/callback error/);
 assert.equal(o.mbDispatching,true);assert.equal(o.RemoveFunction('bad',bad),true);assert.equal(o.HasFunction(bad),true);}
''')

    def test_eligibility_failure_and_allocation_or_mutation_failure_fall_back_once(self):
        self.execute(r'''
for(const fault of ['eligibility','allocate','write']){brokenEligibility=fault==='eligibility';failAllocate=fault==='allocate';
 const a=()=>1,b=()=>2;const o=new Indexed('a',a);assert.equal(o.HasFunction(a),true);
 if(fault==='write'){failWrite=true;assert.equal(o.AddFunction('b',b),true);failWrite=false;assert.equal(o.HasFunction(b),true);}
 assert.equal(o.apexCommAliased,true);assert.equal(o.apexCommIndex,null);const prior=dictionaries;
 for(let j=0;j<100;j++)assert.equal(o.HasFunction(a),true);assert.equal(dictionaries,prior);
 brokenEligibility=false;failAllocate=false;failWrite=false;}
''')

    def test_different_bound_closure_eligibility_and_remove_failure_preserve_native_results(self):
        self.execute(r'''
const a=()=>1,b=()=>2;const o=new Indexed('a',a);const inherited=Indexed.prototype.HasFunction;
Object.defineProperty(o,'HasFunction',{get(){return inherited.bind(o);}});
assert.equal(o.HasFunction(a),true);assert.equal(o.apexCommAliased,true);assert.equal(o.apexCommIndex,null);
const p=new Indexed('a',a);p.AddFunction('b',b);failDelete=true;
assert.equal(p.RemoveFunction('b',b),true);failDelete=false;assert.equal(p.HasFunction(b),false);
assert.equal(p.apexCommAliased,true);assert.equal(p.apexCommIndex,null);
''')

    def test_explicit_stats_are_primitive_and_distinguish_live_indexing_from_fallback(self):
        self.execute(r'''
const a=()=>{};const o=new Indexed('a',a);o.HasFunction(a);const ready=Indexed.ApexCommIndexStats();
assert.ok(ready.indexes_built>0);assert.ok(ready.indexed_calls>0);assert.equal(ready.appearance_written,false);
o.GetFunctions();assert.equal(Indexed.ApexCommIndexStats().alias_fallbacks,ready.alias_fallbacks+1);
const after=Indexed.ApexCommIndexStats();for(let j=0;j<10;j++)o.HasFunction(a);
assert.equal(Indexed.ApexCommIndexStats().indexed_calls,after.indexed_calls);
for(const value of Object.values(after))assert.ok(['string','number','boolean'].includes(typeof value));
''')

    def test_no_per_add_original_linear_miss_restores_quadratic_registration(self):
        self.execute(r'''
function add(Type){reads=0;const o=new Type('first',()=>{});for(let j=0;j<1500;j++)assert.equal(o.AddFunction('b'+j,()=>{}),true);return reads;}
const nativeReads=add(Native),indexReads=add(Indexed);
assert.ok(nativeReads>1000000,nativeReads);assert.ok(indexReads<20,indexReads);
const before=dictionaries;const a=()=>{};const o=new Indexed('a',a);o.HasFunction(a);const ready=dictionaries;
for(let j=0;j<1000;j++)assert.equal(o.HasFunction(()=>{}),false);assert.equal(dictionaries,ready);assert.ok(ready>before);
''')


@unittest.skipUnless((ROOT/'.work/v331-comm-index-stage-donor/chained.json').exists() and shutil.which('javac'),
                     'Private staged provider artifacts and FFDec required')
class CompiledCommunicationIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='apex-comm-index-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.jar=ROOT/'.work/research/ffdec/ffdec.jar'
        subprocess.run(['javac','-cp',str(cls.jar),'-d',cls.temp.name,
            str(ROOT/'tools/CasStructuralRolesPatch.java'),str(ROOT/'tools/CasCommunicationIndexPatch.java'),
            str(ROOT/'tests/CasCommunicationIndexBytecodeFixtures.java')],check=True,capture_output=True,timeout=60)

    def test_both_actual_provider_bytecode_corruption_gates_and_prior_stage_rollback(self):
        raw={'donor':'.work/research/maru-dynamic/62ECC59A-00000000-89D13757C58C2E05.swf',
             'canonical':'.work/research/native-library-v124-12272E1AC0C1F8E2.swf'}
        for kind,path in raw.items():
            with self.subTest(provider=kind):
                work=ROOT/('.work/v331-comm-index-stage-'+kind)
                result=subprocess.run(['java','-cp',str(self.jar)+os.pathsep+self.temp.name,
                    'CasCommunicationIndexBytecodeFixtures',str(ROOT/path),
                    str(ROOT/('.work/v331-grid-selection-final/'+kind+'.swf')),
                    str(work/'compiled.swf'),str(work/'retained.abc')],capture_output=True,text=True,timeout=60)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr[-2000:])
                self.assertEqual(result.stdout.count('PASS '),14)

    def test_historical_proof_is_separate_and_chain_rejects_current_bytes_or_metadata_corruption(self):
        for kind in ('donor','canonical'):
            work=ROOT/('.work/v331-comm-index-stage-'+kind)
            record=json.loads((work/'chained.json').read_text());final=(work/'final.swf').read_bytes()
            self.assertTrue(comm.verify_adapter(record,final))
            self.assertNotEqual(record['patched_resource_sha256'],record['retained_transaction_adapter']['patched_resource_sha256'])
            self.assertNotEqual(record['communication_index_contract']['abc_sha256'],
                record['retained_transaction_adapter']['native_bytecode_contract']['abc_sha256'])
            for field,value in [('baseline_swf_sha256','0'*64),('baseline_abc_sha256','0'*64),('abc_sha256','0'*64),
                    ('appended_methods',6),('appended_static_fields',0),('runtime_qualified',True),
                    ('bound_closure_runtime_eligibility_probe',False),('public_alias_falls_back_to_original',False)]:
                changed=copy.deepcopy(record);changed['communication_index_contract'][field]=value
                with self.subTest(kind=kind,field=field),self.assertRaises(ValueError):comm.verify_adapter(changed,final)
            changed=copy.deepcopy(record);changed['retained_transaction_adapter']['native_bytecode_contract']['unchanged_baseline_bodies']=-1
            with self.assertRaises(ValueError):comm.verify_adapter(changed,final)
            with self.assertRaises(ValueError):comm.verify_adapter(record,(ROOT/('.work/v331-grid-selection-final/'+kind+'.swf')).read_bytes())
            changed=copy.deepcopy(record);changed['communication_index_contract']['source_sha256']['tools/cas_communication_index.py']='0'*64
            with self.assertRaises(ValueError):comm.verify_adapter(changed,final)


if __name__=='__main__':unittest.main()
