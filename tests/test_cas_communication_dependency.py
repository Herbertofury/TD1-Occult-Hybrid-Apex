"""Serialized native dependency proof; no game or profile access."""
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
import cas_communication_dependency as dependency

WORK=ROOT/'.work/v332-communication-dependency'


@unittest.skipUnless((WORK/'chained.json').exists() and shutil.which('javac'),'Private authenticated Olympus artifact and JDK required')
class CompiledCommunicationDependencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='apex-comm-dependency-');cls.addClassCleanup(cls.temp.cleanup)
        cls.jar=ROOT/'.work/research/ffdec/ffdec.jar'
        result=subprocess.run(['javac','-cp',str(cls.jar),'-d',cls.temp.name,
            str(ROOT/'tools/CasStructuralRolesPatch.java'),str(ROOT/'tools/CasCommunicationIndexPatch.java'),
            str(ROOT/'tools/CasCommunicationDependencyPatch.java'),
            str(ROOT/'tests/CasCommunicationIndexBytecodeFixtures.java'),
            str(ROOT/'tests/CasCommunicationDependencyBytecodeFixtures.java')],capture_output=True,text=True,timeout=60)
        if result.returncode:raise AssertionError(result.stdout+result.stderr)

    def test_exact_third_provider_preserves_native_listener_semantics_and_button_domain(self):
        raw=ROOT/'.work/research/native-library-v124-3FFE72432A703655.swf'
        command=['java','-cp',str(self.jar)+os.pathsep+self.temp.name]
        result=subprocess.run(command+['CasCommunicationDependencyBytecodeFixtures',str(raw),str(WORK/'compiled.swf'),str(WORK/'final.swf')],capture_output=True,text=True,timeout=90)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr[-3000:]);self.assertEqual(result.stdout.count('PASS '),12)
        # Exercise the already reviewed five native-hook corruption gates on
        # this third provider as well, using its pre-Button communication stage.
        result=subprocess.run(command+['CasCommunicationIndexBytecodeFixtures',str(raw),str(raw),str(WORK/'compiled.swf'),str(WORK/'communication.abc')],capture_output=True,text=True,timeout=90)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr[-3000:]);self.assertEqual(result.stdout.count('PASS '),14)

    def test_dependency_chain_cannot_claim_grid_history_or_unqualified_native_bytes(self):
        record=json.loads((WORK/'chained.json').read_text());final=(WORK/'final.swf').read_bytes()
        self.assertTrue(dependency.verify_adapter(record,final))
        self.assertNotIn('retained_transaction_adapter',record)
        for field,value in [('base_provider_sha256','0'*64),('baseline_swf_sha256','0'*64),('baseline_abc_sha256','0'*64),
                ('communication_abc_sha256','0'*64),('abc_sha256','0'*64),
                ('appended_methods',7),('appended_button_diagnostic_methods',0),('grid_stage_present',True),
                ('button_lexical_domain_read_verified',False),('button_whole_abc_rollback_verified',False),
                ('runtime_qualified',True),('hitch_free_claimed',True)]:
            altered=copy.deepcopy(record);altered['communication_dependency_contract'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):dependency.verify_adapter(altered,final)
        altered=copy.deepcopy(record);altered['communication_dependency_contract']['source_sha256']['tools/CasCommunicationDependencyPatch.java']='0'*64
        with self.assertRaises(ValueError):dependency.verify_adapter(altered,final)
        with self.assertRaises(ValueError):dependency.verify_adapter(record,(WORK/'baseline.swf').read_bytes())


if __name__=='__main__':unittest.main()
