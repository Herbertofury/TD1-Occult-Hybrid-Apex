"""Execute actual serialized probe bytecode with foreign reflected domains."""
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
sys.path.insert(0,str(ROOT/'tools'))
import cas_communication_domain_probe as probe

KINDS={'canonical':'.work/v331-comm-index-stage-canonical','donor':'.work/v331-comm-index-stage-donor','dependency':'.work/v332-communication-dependency'}


class ProbeVM:
    """Restricted AVM2 operations from verified diagnostic bodies, not a mock API."""
    def __init__(self,bodies,manager,comm):self.bodies=bodies;self.manager=manager;self.comm=comm;self.calls=[]

    def run(self,kind,receiver):
        stack=[];locals_=[receiver,None,None];pc=0;code=self.bodies[kind]
        while pc<len(code):
            i=code[pc];pc+=1;op=i['op']
            if op in (0xd0,0xd1,0xd2):stack.append(locals_[op-0xd0])
            elif op in (0xd5,0xd6):locals_[op-0xd4]=stack.pop()
            elif op==0x30:stack.pop()
            elif op==0x2c:stack.append(i['value'])
            elif op==0x20:stack.append(None)
            elif op==0x27:stack.append(False)
            elif op==0x60:stack.append(self.comm if i['value']=='CommunicationObject' else self.manager)
            elif op==0x66:
                obj=stack.pop();stack.append(len(obj)if i['value']=='length'else obj.get(i['value']))
            elif op==0xac:
                right,left=stack.pop(),stack.pop();stack.append(left is right if right is None else type(left)is type(right)and left==right)
            elif op==0x96:stack.append(not stack.pop())
            elif op==0x11:
                if stack.pop():pc=i['target']
            elif op==0x46:
                assert i['argc']==0;obj=stack.pop();self.calls.append((i['value'],obj))
                stack.append(self.run('manager',obj)if i['value']=='ApexCommTargetIndexStats'else self.run('object',obj))
            elif op==0x55:
                values=stack[-i['count']*2:];del stack[-i['count']*2:];stack.append(dict(zip(values[::2],values[1::2])))
            elif op==0x48:return stack.pop()
            else:raise AssertionError(('unreviewed opcode',op))
        raise AssertionError('Missing native return')


@unittest.skipUnless((ROOT/'.work/v332-domain-probe-dependency/chained.json').exists()and shutil.which('javac'),'Private three-provider diagnostic artifacts and JDK required')
class CompiledDomainProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='apex-domain-probe-');cls.addClassCleanup(cls.temp.cleanup)
        cls.jar=ROOT/'.work/research/ffdec/ffdec.jar'
        result=subprocess.run(['javac','-cp',str(cls.jar),'-d',cls.temp.name,str(ROOT/'tools/CasStructuralRolesPatch.java'),
            str(ROOT/'tools/CasCommunicationDomainProbePatch.java'),str(ROOT/'tests/CasCommunicationDomainProbeBytecodeFixtures.java')],capture_output=True,text=True,timeout=60)
        if result.returncode:raise AssertionError(result.stdout+result.stderr)
        cls.command=['java','-cp',str(cls.jar)+os.pathsep+cls.temp.name,'CasCommunicationDomainProbeBytecodeFixtures']

    def invoke(self,kind,*extra):
        return subprocess.run(self.command+[str(ROOT/KINDS[kind]/'final.swf'),str(ROOT/('.work/v332-domain-probe-'+kind)/'final.swf'),*extra],capture_output=True,text=True,timeout=60)

    def test_all_three_serialized_original_methods_and_actual_object_route_reject_corruption(self):
        for kind in KINDS:
            result=self.invoke(kind)
            with self.subTest(kind=kind):self.assertEqual(result.returncode,0,result.stdout+result.stderr[-3000:]);self.assertEqual(result.stdout.count('PASS '),18)

    def test_extracted_native_probe_reads_actual_listener_not_unrelated_reflected_class_or_array(self):
        for kind in KINDS:
            result=self.invoke(kind,'--dump');self.assertEqual(result.returncode,0,result.stderr[-3000:]);bodies=json.loads(result.stdout)
            foreign_reflected={'apexCommBuilt':151,'apexCommCalls':935}
            actual_class={'apexCommBuilt':17,'apexCommCalls':9876,'apexCommAlias':0,'apexCommEligibility':0,'apexCommErrors':0}
            native_array=[object()for _ in range(513)];index=object()
            actual={'apexCommIndex':index,'apexCommAliased':False,'mFunctions':native_array}
            manager={'instance':{'mMessageListeners':{'UsingControllerToggled':actual,'OtherMessage':{'mFunctions':[]}}}}
            vm=ProbeVM(bodies,manager,actual_class);value=vm.run('button',{'unused_cell':True})
            info=value['listener_membership'];self.assertTrue(info['index_active']);self.assertFalse(info['alias_escaped']);self.assertEqual(info['listener_count'],513)
            self.assertEqual(info['indexed_calls'],9876);self.assertNotEqual(info['indexed_calls'],foreign_reflected['apexCommCalls'])
            self.assertEqual(vm.calls[0][0],'ApexCommTargetIndexStats');self.assertIs(vm.calls[0][1],manager)
            self.assertEqual(vm.calls[1][0],'ApexCommObjectIndexStats');self.assertIs(vm.calls[1][1],actual)
            for item in info.values():self.assertIsInstance(item,(str,bool,int));self.assertIsNot(item,native_array);self.assertIsNot(item,index)
            self.assertIs(actual['mFunctions'],native_array);self.assertIs(actual['apexCommIndex'],index)
            actual['apexCommIndex']=None;actual['apexCommAliased']=True
            info=vm.run('button',{})['listener_membership'];self.assertFalse(info['index_active']);self.assertTrue(info['alias_escaped'])

    def test_native_null_singleton_and_absent_listener_return_without_dispatch_or_construction(self):
        result=self.invoke('dependency','--dump');self.assertEqual(result.returncode,0,result.stderr);bodies=json.loads(result.stdout)
        for manager in ({'instance':None},{'instance':{'mMessageListeners':{}}}):
            vm=ProbeVM(bodies,manager,{})
            self.assertIsNone(vm.run('button',{})['listener_membership']);self.assertEqual([x[0]for x in vm.calls],['ApexCommTargetIndexStats'])

    def test_separate_frozen_stage_chain_rejects_history_source_and_proof_corruption(self):
        for kind in KINDS:
            work=ROOT/('.work/v332-domain-probe-'+kind);record=json.loads((work/'chained.json').read_text());final=(work/'final.swf').read_bytes()
            self.assertTrue(probe.verify_adapter(record,final))
            for field,value in [('baseline_swf_sha256','0'*64),('baseline_abc_sha256','0'*64),('abc_sha256','0'*64),
                    ('changed_native_bodies',1),('actual_listener_instance_read_verified',False),('no_dispatch_write_or_services',False),('runtime_qualified',True)]:
                altered=copy.deepcopy(record);altered['communication_domain_probe_contract'][field]=value
                with self.subTest(kind=kind,field=field),self.assertRaises(ValueError):probe.verify_adapter(altered,final)
            altered=copy.deepcopy(record);altered['previous_stage_adapter']['base_resource_sha256']='0'*64
            with self.assertRaises(ValueError):probe.verify_adapter(altered,final)
            altered=copy.deepcopy(record);altered['communication_domain_probe_contract']['source_sha256']['tools/CasCommunicationDomainProbePatch.java']='0'*64
            with self.assertRaises(ValueError):probe.verify_adapter(altered,final)
            with self.assertRaises(ValueError):probe.verify_adapter(record,(ROOT/KINDS[kind]/'final.swf').read_bytes())


if __name__=='__main__':unittest.main()
