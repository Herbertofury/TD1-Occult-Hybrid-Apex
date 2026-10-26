import copy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Source'))
from apex_core import native_pelt_copy as pelt


class NativePeltPolicyTests(unittest.TestCase):
    def objects(self,mask):
        human=types.SimpleNamespace(pelt_layers=b'authored Human paint')
        tracker=types.SimpleNamespace(_sim_info=types.SimpleNamespace(id=44,occult_types=mask),_sim_info_map={1:human})
        generated=types.SimpleNamespace(pelt_layers=b'independent generated paint')
        enums=types.SimpleNamespace(HUMAN=1,WEREWOLF=32,FAIRY=64)
        return tracker,human,generated,pelt._policy({'OccultType':enums})

    def test_hybrid_generation_keeps_nonempty_human_paint_and_generated_paint_independent(self):
        for mask in (35,67,96,97,126,127):
            tracker,human,generated,policy=self.objects(mask)
            policy(tracker,generated)
            self.assertEqual(human.pelt_layers,b'authored Human paint')
            self.assertEqual(generated.pelt_layers,b'independent generated paint')
            self.assertTrue(tracker._apex_native_pelt_policy['human_write_suppressed'])
            self.assertFalse(tracker._apex_native_pelt_policy['bank_read'])
            self.assertFalse(tracker._apex_native_pelt_policy['appearance_restored'])

    def test_uncaptured_single_occult_keeps_the_native_copy(self):
        with patch.dict(sys.modules,{'apex_core.native_cas_engine':types.SimpleNamespace(_LAYOUT_SCOPE=None)}):
            for mask in (33,65):
                tracker,human,generated,policy=self.objects(mask);policy(tracker,generated)
                self.assertEqual(human.pelt_layers,generated.pelt_layers)
                self.assertTrue(tracker._apex_native_pelt_policy['native_default_copy_called'])

    def test_single_occult_requires_current_process_and_exact_shared_human_scope(self):
        scope=dict(pid=os.getpid(),logical_owners={'44':dict(human_owner_id='native/1',logical_owner_ids={'1':'native/1'})},
                   owners={('44','native/1'):object()})
        for damage in (None,'pid','sim','binding','owner'):
            selected=copy.deepcopy(scope)
            if damage=='pid':selected['pid']+=1
            elif damage=='sim':selected['logical_owners']['45']=selected['logical_owners'].pop('44')
            elif damage=='binding':selected['logical_owners']['44']['logical_owner_ids']['1']='active/1'
            elif damage=='owner':selected['owners']={}
            with patch.dict(sys.modules,{'apex_core.native_cas_engine':types.SimpleNamespace(_LAYOUT_SCOPE=selected)}):
                tracker,human,generated,policy=self.objects(65);policy(tracker,generated)
                self.assertEqual(tracker._apex_native_pelt_policy['human_write_suppressed'],damage is None)
                self.assertEqual(human.pelt_layers,b'authored Human paint' if damage is None else generated.pelt_layers)

    def test_changed_enum_contract_keeps_the_original_assignment(self):
        tracker,human,generated,_=self.objects(127)
        policy=pelt._policy({'OccultType':types.SimpleNamespace(HUMAN=1,WEREWOLF=32)})
        policy(tracker,generated);self.assertEqual(human.pelt_layers,generated.pelt_layers)

    def test_wrong_runtime_refuses_without_replacing_a_method(self):
        class Tracker:
            def _generate_sim_info(self,kind,generate_new=False):return kind
        before=Tracker._generate_sim_info
        self.assertFalse(pelt.install(Tracker)['installed']);self.assertIs(Tracker._generate_sim_info,before)

    def test_real_wordcode_replacement_preserves_wrappers_and_vanilla_behavior(self):
        compiler=ROOT/'.work/build-python37/python.exe'
        if not compiler.is_file():self.skipTest('Requires the pinned private Python 3.7 compiler.')
        fixture=ROOT/'tests/fixtures/native_pelt_wordcode.py'
        result=subprocess.run([str(compiler),str(fixture),str(ROOT/'Source')],text=True,capture_output=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
        self.assertIn('wordcode preservation and scoped generation passed',result.stdout)
