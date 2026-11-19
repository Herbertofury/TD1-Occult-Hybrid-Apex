"""Execute the exact verifier seam and authenticate the normal fresh Main path."""
from pathlib import Path
import ast
import sys
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import cas_grid_frame_status  # Load current dependency definitions before scoped legacy gate doubles.
import cas_grid_eof,cas_catalog_authority
import cas_grid_width,cas_catalog_unconsumed
import cas_catalog_workflow as workflow


class WorkflowBuildIntegrationTests(unittest.TestCase):
    def builder(self):return ast.parse((ROOT/'tools/cas_ui_build.py').read_text())

    def test_all_four_owned_inputs_are_pinned_exactly_once(self):
        pins=next(ast.literal_eval(n.value)for n in self.builder().body if isinstance(n,ast.Assign)and
                  any(isinstance(t,ast.Name)and t.id=='PINNED_SOURCES'for t in n.targets))
        for name in workflow.SOURCES:
            with self.subTest(name=name):self.assertEqual(pins.count(name),1)

    def test_normal_fresh_main_compiles_workflow_from_exact_scheduler_and_same_source(self):
        calls={}
        for node in ast.walk(self.builder()):
            if isinstance(node,ast.Assign)and len(node.targets)==1 and isinstance(node.targets[0],ast.Tuple)and isinstance(node.value,ast.Call):
                names=[item.id for item in node.targets[0].elts if isinstance(item,ast.Name)]
                if len(names)==2 and names[1]in('catalog_schedule_main_contract','catalog_workflow_main_contract'):calls[names[1]]=node
        self.assertEqual(set(calls),{'catalog_schedule_main_contract','catalog_workflow_main_contract'})
        before=calls['catalog_schedule_main_contract'];current=calls['catalog_workflow_main_contract']
        self.assertLess(before.lineno,current.lineno)
        self.assertEqual(ast.dump(current.value.func),ast.dump(ast.parse('cas_catalog_workflow.adapt_main').body[0].value))
        self.assertEqual([ast.dump(arg)for arg in current.value.args[:4]],
                         [ast.dump(ast.Name(id=name,ctx=ast.Load()))for name in('catalog_schedule_main_contract','payload','patched','ffdec')])
        self.assertEqual(ast.literal_eval(current.value.args[4].right),'catalog-workflow-main')

    def test_manifest_exposes_the_exact_fresh_workflow_contract(self):
        matches=[]
        for node in ast.walk(self.builder()):
            if isinstance(node,ast.Dict):
                matches.extend(value for key,value in zip(node.keys,node.values)if isinstance(key,ast.Constant)and key.value==workflow.MANIFEST)
        self.assertEqual(len(matches),1)
        self.assertIsInstance(matches[0],ast.Name)
        self.assertEqual(matches[0].id,'catalog_workflow_main_contract')

    def verifier(self):
        path=ROOT/'tools/maru_companion.py'
        method=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='verify_merged')
        scope={}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),str(path),'exec'),scope)
        return scope['verify_merged']

    def test_verifier_authenticates_and_rolls_workflow_before_scheduler(self):
        class StopAfterExactPredecessor(Exception):pass
        calls=[];original_info={'raw':'unchanged'};original_resources={(1,2,3):b'original'}
        restored_info={'raw':'restored'};restored_resources={(1,2,3):b'restored'}
        current=types.ModuleType('cas_catalog_workflow');previous=types.ModuleType('cas_catalog_schedule')
        def outer(info,resources):
            self.assertIs(info,original_info);self.assertIs(resources,original_resources)
            calls.append('workflow');return restored_info,restored_resources
        def inner(info,resources):
            self.assertIs(info,restored_info);self.assertIs(resources,restored_resources)
            calls.append('scheduler');raise StopAfterExactPredecessor()
        current.unwrap_manifest=outer;previous.unwrap_manifest=inner
        with patch.dict(sys.modules,{'cas_catalog_workflow':current,'cas_catalog_schedule':previous}),self.assertRaises(StopAfterExactPredecessor):
            self.verifier()(original_info,original_resources)
        self.assertEqual(calls,['workflow','scheduler'])

    def test_refused_workflow_proof_never_falls_through_to_the_older_gate(self):
        calls=[];current=types.ModuleType('cas_catalog_workflow');previous=types.ModuleType('cas_catalog_schedule')
        def refuse(info,resources):calls.append('workflow');raise ValueError('exact workflow proof refused')
        def forbidden(info,resources):calls.append('scheduler');raise AssertionError('refused outer proof fell through')
        current.unwrap_manifest=refuse;previous.unwrap_manifest=forbidden
        with patch.dict(sys.modules,{'cas_catalog_workflow':current,'cas_catalog_schedule':previous}),self.assertRaisesRegex(ValueError,'exact workflow proof refused'):
            self.verifier()({}, {})
        self.assertEqual(calls,['workflow'])


if __name__=='__main__':unittest.main()
