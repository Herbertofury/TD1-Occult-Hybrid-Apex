"""Native removal equivalence, source-auth predicate and serialized error ABI."""
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
import cas_communication_removal_miss as miss
import test_cas_communication_index as old


@unittest.skipUnless(old.SOURCE.exists()and shutil.which('node'),'Private native listener source and Node required')
class RemovalMissSemanticsTests(unittest.TestCase):
    def execute(self,body):
        harness=old.CommunicationIndexSemanticsTests().harness()
        params,source=old.functions(miss.HELPER)['ApexCommRemovalMissing'];source=source.replace('mbDispatching','this.mbDispatching')
        method=old.method('ApexCommRemovalMissing',params,source)
        harness+='\nIndexed.prototype.ApexCommRemovalMissing=function'+method[len('ApexCommRemovalMissing'):]+';\n'
        harness+='''const retainedRemove=Indexed.prototype.RemoveFunction;
Indexed.prototype.RemoveFunction=function(name,fn){let negative=false;try{negative=this.ApexCommRemovalMissing(fn);}catch(error){}
return negative?false:retainedRemove.call(this,name,fn);};\n'''
        result=subprocess.run(['node'],input=harness+body,capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_proven_misses_do_not_scan_or_allocate_and_positive_wrong_widget_and_null_match(self):
        self.execute(r'''
const first=()=>0,missing=()=>-1;const n=new Native('first',first),i=new Indexed('first',first);const fn=[];
for(let j=0;j<1200;j++){fn.push(()=>j);n.AddFunction('b'+j,fn[j]);i.AddFunction('b'+j,fn[j]);}
let nativeSlots=0,indexSlots=0;
n.mFunctions=new Proxy(n.mFunctions,{get(t,key,r){if(/^\d+$/.test(String(key)))nativeSlots++;return Reflect.get(t,key,r);}});
i.mFunctions=new Proxy(i.mFunctions,{get(t,key,r){if(/^\d+$/.test(String(key)))indexSlots++;return Reflect.get(t,key,r);}});
assert.equal(n.RemoveFunction('missing',missing),false);assert.ok(nativeSlots>=1200);
const before=dictionaries;for(let j=0;j<2000;j++)assert.equal(i.RemoveFunction('missing',missing),false);
assert.equal(indexSlots,0);assert.equal(dictionaries,before);assert.deepEqual(rows(n),rows(i));
for(const args of [['wrong-widget',fn[10]],['b10',fn[10]],['b10',fn[10]],['first',first],['none',null]]){
assert.equal(n.RemoveFunction(...args),i.RemoveFunction(...args));assert.deepEqual(rows(n),rows(i));}
''')

    def test_deferred_absent_present_duplicate_queue_nested_dispatch_and_callback_throw_match(self):
        self.execute(r'''
const missing=()=>{};
function a(p){p.log.push('a'+p.depth);if(!p.depth){p.log.push(p.o.RemoveFunction('absent',missing));p.log.push(p.o.mPendingRemoval.length);
p.o.RemoveFunction('b',b);p.o.RemoveFunction('b',b);p.o.AddFunction('c',c);p.o.Dispatch({o:p.o,log:p.log,depth:1});}}
function b(p){p.log.push('b'+p.depth);}function c(p){p.log.push('c'+p.depth);}
function run(Type){const o=new Type('a',a);o.AddFunction('b',b);const log=[];o.Dispatch({o,log,depth:0});return{log,rows:rows(o),pending:o.mPendingRemoval,dispatch:o.mbDispatching};}
assert.deepEqual(run(Native),run(Indexed));
function bad(){throw Error('native callback');}for(const Type of[Native,Indexed]){const o=new Type('bad',bad);o.HasFunction(bad);assert.throws(()=>o.Dispatch({}),/native callback/);
assert.equal(o.RemoveFunction('absent',missing),true);assert.equal(o.mPendingRemoval.length,1);assert.equal(o.mbDispatching,true);}
''')

    def test_alias_duplicates_mutable_rows_null_and_bound_closure_ineligibility_stay_native(self):
        self.execute(r'''
const a=()=>1,b=()=>2;for(const Type of[Native,Indexed]){const o=new Type('a',a);o.AddFunction('b',b);const array=o.GetFunctions();
array.push(new WidgetFunction('dup',a));array[0].mFunction=b;assert.equal(o.RemoveFunction('dup',a),true);
assert.equal(o.RemoveFunction('a',a),false);assert.equal(o.RemoveFunction('a',b),true);assert.deepEqual(rows(o),[['b',b]]);}
for(const Type of[Native,Indexed]){const o=new Type('null',null);o.AddFunction('b',b);assert.equal(o.RemoveFunction('null',null),true);assert.equal(o.RemoveFunction('none',null),false);}
const o=new Indexed('a',a);const inherited=Indexed.prototype.HasFunction;Object.defineProperty(o,'HasFunction',{get(){return inherited.bind(o);}});
assert.equal(o.HasFunction(a),true);assert.equal(o.apexCommAliased,true);assert.equal(o.RemoveFunction('a',a),true);
''')

    def test_unbuilt_failed_lookup_allocation_and_eligibility_paths_do_not_change_native_behavior(self):
        self.execute(r'''
const a=()=>1,b=()=>2,missing=()=>-1;const unbuilt=new Indexed('a',a);const before=dictionaries;
assert.equal(unbuilt.RemoveFunction('absent',missing),false);assert.equal(dictionaries,before);assert.equal(unbuilt.apexCommIndex,null);
const o=new Indexed('a',a);o.AddFunction('b',b);const map=o.apexCommIndex;assert.ok(map);
map.get=()=>{throw Error('Dictionary lookup uncertainty');};assert.equal(o.RemoveFunction('absent',missing),false);
assert.equal(o.RemoveFunction('a',a),true);assert.deepEqual(rows(o),[['b',b]]);
for(const fault of['allocation','eligibility']){failAllocate=fault==='allocation';brokenEligibility=fault==='eligibility';const p=new Indexed('a',a);
assert.equal(p.HasFunction(a),true);assert.equal(p.apexCommAliased,true);assert.equal(p.RemoveFunction('absent',missing),false);assert.equal(p.RemoveFunction('a',a),true);
failAllocate=false;brokenEligibility=false;}
''')


class PredicateVM:
    def __init__(self,body):self.body=body
    def run(self,owner,fn):
        stack=[];scopes=[];pc=0;peak=0;code=self.body['code'];handler=self.body['catch']
        while pc<len(code):
            at=pc;i=code[pc];pc+=1;op=i['op']
            try:
                if op==0xd0:stack.append(owner)
                elif op==0xd1:stack.append(fn)
                elif op==0x30:scopes.append(stack.pop())
                elif op==0xef:pass
                elif op==0x20:stack.append(None)
                elif op==0x26:stack.append(True)
                elif op==0x27:stack.append(False)
                elif op==0x29:stack.pop()
                elif op==0x2a:stack.append(stack[-1])
                elif op in(0x11,0x12):
                    truth=bool(stack.pop())
                    if truth==(op==0x11):pc=i['target']
                elif op==0x60:stack.append(owner[i['name']])
                elif op==0x66:
                    key=stack.pop();dictionary=stack.pop();stack.append(dictionary.get(key))
                elif op in(0xab,0xac):
                    right,left=stack.pop(),stack.pop();stack.append(left is right if right is None else type(left)is type(right)and left==right)
                elif op==0x96:stack.append(not stack.pop())
                elif op==0x48:
                    value=stack.pop();assert not stack;assert len(scopes)==1;assert self.body['flags']==0;return value
                else:raise AssertionError(('unexpected opcode',op))
            except RuntimeError as error:
                if not handler['from']<=at<handler['to']:raise
                stack=[error];scopes=[];pc=handler['target']
            peak=max(peak,len(stack));assert peak<=self.body['max_stack'];assert len(scopes)<=self.body['max_scope']
        raise AssertionError('Missing return')


class ManagerReasonVM:
    def __init__(self,body,singleton):self.body=body;self.singleton=singleton;self.calls=0
    def run(self):
        # Deliberately WRONG static receiver: the corrected native lexical
        # getter must still read self.singleton, never local0.instance.
        locals_=[{'instance':None},None,None,None];stack=[];pc=0
        while pc<len(self.body['code']):
            i=self.body['code'][pc];pc+=1;op=i['op']
            if op in(0xd0,0xd1,0xd2,0xd3):stack.append(locals_[op-0xd0])
            elif op in(0xd5,0xd6,0xd7):locals_[op-0xd4]=stack.pop()
            elif op==0x30:stack.pop()
            elif op==0x60:
                assert i['name']=='instance';assert i['qname']==self.body['native_singleton_qname'];stack.append(self.singleton)
            elif op==0x2c:stack.append(i['value'])
            elif op in(0x26,0x27):stack.append(op==0x26)
            elif op==0x11:
                value=stack.pop();truth=True if isinstance(value,(dict,list))else bool(value)
                if truth:pc=i['target']
            elif op==0x66:
                if i['name']is None:
                    assert i['qname']==self.body['native_map_qname'];key=stack.pop();obj=stack.pop();stack.append(obj.get(key))
                else:stack.append(stack.pop().get(i['name']))
            elif op==0xb4:obj,key=stack.pop(),stack.pop();stack.append(key in obj)
            elif op==0xb2:assert i['name']=='Function';stack.append(callable(stack.pop()))
            elif op==0x46:
                assert i['name']=='ApexCommObjectIndexStats';obj=stack.pop();self.calls+=1;stack.append(obj[i['name']]())
            elif op==0x61:value,obj=stack.pop(),stack.pop();obj[i['name']]=value
            elif op==0x55:
                values=stack[-i['count']*2:];del stack[-i['count']*2:];stack.append(dict(zip(values[::2],values[1::2])))
            elif op==0x48:return stack.pop()
            else:raise AssertionError(('Unexpected Manager opcode',op))
        raise AssertionError('Missing Manager return')


@unittest.skipUnless((ROOT/'.work/v333-removal-miss-dependency/chained.json').exists()and shutil.which('javac'),'Private three-provider removal artifacts/JDK required')
class CompiledRemovalMissTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='apex-removal-miss-');cls.addClassCleanup(cls.temp.cleanup);cls.jar=ROOT/'.work/research/ffdec/ffdec.jar'
        result=subprocess.run(['javac','-cp',str(cls.jar),'-d',cls.temp.name,str(ROOT/'tools/CasStructuralRolesPatch.java'),
            str(ROOT/'tools/CasCommunicationIndexPatch.java'),str(ROOT/'tools/CasCommunicationRemovalMissPatch.java'),
            str(ROOT/'tests/CasCommunicationRemovalMissBytecodeFixtures.java')],capture_output=True,text=True,timeout=60)
        if result.returncode:raise AssertionError(result.stdout+result.stderr)
        cls.command=['java','-cp',str(cls.jar)+os.pathsep+cls.temp.name,'CasCommunicationRemovalMissBytecodeFixtures']

    def invoke(self,kind,*extra):
        return subprocess.run(self.command+[str(ROOT/('.work/v332-domain-probe-'+kind)/'final.swf'),str(ROOT/('.work/v333-removal-miss-'+kind)/'final.swf'),*extra],capture_output=True,text=True,timeout=60)

    def test_three_real_bytecode_projection_and_corruption_gates(self):
        for kind in('canonical','donor','dependency'):
            r=self.invoke(kind)
            with self.subTest(kind=kind):self.assertEqual(r.returncode,0,r.stdout+r.stderr[-3000:]);self.assertEqual(r.stdout.count('PASS '),22)

    def test_actual_compiled_zero_allocation_predicate_and_exception_handler_execute(self):
        class ThrowingMap(dict):
            def get(self,key):raise RuntimeError('native Dictionary lookup fault')
        a=object();b=object()
        for kind in('canonical','donor','dependency'):
            r=self.invoke(kind,'--dump');self.assertEqual(r.returncode,0,r.stderr);body=json.loads(r.stdout);vm=PredicateVM(body)
            owner={'mbDispatching':False,'apexCommAliased':False,'apexCommIndex':{a:True}}
            self.assertTrue(vm.run(owner,b));self.assertFalse(vm.run(owner,a));self.assertFalse(vm.run(owner,None))
            for field,value in [('mbDispatching',True),('apexCommAliased',True),('apexCommIndex',None),('apexCommIndex',ThrowingMap())]:
                changed=dict(owner);changed[field]=value;self.assertFalse(vm.run(changed,b))
            self.assertEqual(owner,{'mbDispatching':False,'apexCommAliased':False,'apexCommIndex':{a:True}})

    def test_owned_manager_uses_original_native_lexical_static_and_dynamic_lookup_oracles(self):
        for kind in('canonical','donor','dependency'):
            r=self.invoke(kind,'--manager');self.assertEqual(r.returncode,0,r.stderr);body=json.loads(r.stdout)
            for singleton,reason,present in [(None,'singleton-missing',False),({'mMessageListeners':None},'listener-map-missing',True),
                    ({'mMessageListeners':{}},'listener-missing',True),({'mMessageListeners':{'UsingControllerToggled':{}}},'listener-probe-unavailable',True),
                    ({'mMessageListeners':{'UsingControllerToggled':{'ApexCommObjectIndexStats':None}}},'listener-probe-unavailable',True)]:
                vm=ManagerReasonVM(body,singleton);value=vm.run();self.assertEqual(value['reason'],reason);self.assertEqual(value['singleton_present'],present);self.assertEqual(vm.calls,0)
            original={'index_active':True,'alias_escaped':False,'listener_count':513,'indexed_calls':9876,'appearance_written':False}
            listener={'ApexCommObjectIndexStats':lambda:dict(original)};singleton={'mMessageListeners':{'UsingControllerToggled':listener}}
            vm=ManagerReasonVM(body,singleton);value=vm.run();self.assertEqual(vm.calls,1);self.assertTrue(value['singleton_present']);self.assertTrue(value['listener_present']);self.assertEqual(value['reason'],'ready')
            self.assertEqual(value['indexed_calls'],9876);self.assertEqual(value['listener_count'],513);self.assertTrue(value['index_active'])
            self.assertNotIn('reason',original);self.assertEqual(list(singleton['mMessageListeners']),['UsingControllerToggled']);self.assertNotIn('reason',listener)

    def test_prior_stage_and_source_corruption_cannot_enter_final_manifest(self):
        for kind in('canonical','donor','dependency'):
            work=ROOT/('.work/v333-removal-miss-'+kind);record=json.loads((work/'chained.json').read_text());final=(work/'final.swf').read_bytes()
            self.assertTrue(miss.verify_adapter(record,final))
            for field,value in [('baseline_abc_sha256','0'*64),('appended_fields',1),('negative_only_predicate_verified',False),('deferred_removal_original_path_verified',False),('no_lazy_index_build_or_allocation',False),('runtime_qualified',True)]:
                changed=copy.deepcopy(record);changed['communication_removal_miss_contract'][field]=value
                with self.subTest(kind=kind,field=field),self.assertRaises(ValueError):miss.verify_adapter(changed,final)
            changed=copy.deepcopy(record);changed['previous_stage_adapter']['base_resource_sha256']='0'*64
            with self.assertRaises(ValueError):miss.verify_adapter(changed,final)
            with self.assertRaises(ValueError):miss.verify_adapter(record,(ROOT/('.work/v332-domain-probe-'+kind)/'final.swf').read_bytes())


if __name__=='__main__':unittest.main()
