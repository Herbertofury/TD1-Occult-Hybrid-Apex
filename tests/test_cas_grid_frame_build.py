"""Authenticate the Main-only shared-list continuation in the real build seams."""
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
import cas_grid_frame_status as insets


class FrameBuildIntegrationTests(unittest.TestCase):
    def builder(self):return ast.parse((ROOT/'tools/cas_ui_build.py').read_text())

    def assignments(self):
        names={'catalog_list_insets_main_contract','frame_status_main_contract'};found={}
        for node in ast.walk(self.builder()):
            if isinstance(node,ast.Assign)and len(node.targets)==1 and isinstance(node.targets[0],ast.Tuple)and isinstance(node.value,ast.Call):
                values=[value.id for value in node.targets[0].elts if isinstance(value,ast.Name)]
                if len(values)==2 and values[1]in names:found[values[1]]=node
        self.assertEqual(set(found),names)
        return found

    def test_four_exact_inputs_are_pinned_once(self):
        pins=next(ast.literal_eval(node.value)for node in self.builder().body if isinstance(node,ast.Assign)and
                  any(isinstance(target,ast.Name)and target.id=='PINNED_SOURCES'for target in node.targets))
        self.assertEqual(len(insets.SOURCES),4)
        for name in insets.SOURCES:
            with self.subTest(name=name):self.assertEqual(pins.count(name),1)

    def test_fresh_main_uses_exact_workflow_same_source_and_new_work_directory(self):
        calls=self.assignments();before=calls['catalog_list_insets_main_contract'];current=calls['frame_status_main_contract']
        self.assertLess(before.lineno,current.lineno)
        self.assertEqual(ast.dump(current.value.func),ast.dump(ast.parse('cas_grid_frame_status.adapt_main').body[0].value))
        self.assertEqual([ast.dump(arg)for arg in current.value.args[:4]],
                         [ast.dump(ast.Name(id=name,ctx=ast.Load()))for name in('catalog_list_insets_main_contract','payload','patched','ffdec')])
        self.assertEqual(ast.literal_eval(current.value.args[4].right),'grid-frame-status-main')

    def test_real_fresh_assignment_passes_the_returned_workflow_bytes_and_contract(self):
        calls=self.assignments();nodes=sorted(calls.values(),key=lambda node:node.lineno);observed=[]
        prior=object();source=object();ffdec=object();workflow_contract=object();inset_contract=object()
        def workflow(*args):
            observed.append(('workflow',args));return b'exact-workflow-resource',workflow_contract
        def current(*args):
            observed.append(('insets',args));return b'composed-main',inset_contract
        scope={'catalog_workflow_main_contract':prior,'payload':b'scheduler-resource','patched':source,'ffdec':ffdec,'work':Path('work'),
               'cas_list_insets':types.SimpleNamespace(adapt_main=workflow),'cas_grid_frame_status':types.SimpleNamespace(adapt_main=current)}
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),'fresh-main','exec'),scope)
        self.assertEqual([row[0]for row in observed],['workflow','insets'])
        self.assertEqual(observed[1][1],(workflow_contract,b'exact-workflow-resource',source,ffdec,Path('work/grid-frame-status-main')))
        self.assertEqual(scope['payload'],b'composed-main');self.assertIs(scope['frame_status_main_contract'],inset_contract)

    def test_refused_current_main_never_returns_a_predecessor_resource(self):
        current=self.assignments()['frame_status_main_contract'];before=object()
        def refuse(*args):raise ValueError('exact three-owner continuation refused')
        scope={'catalog_list_insets_main_contract':object(),'payload':before,'patched':object(),'ffdec':object(),'work':Path('work'),
               'cas_grid_frame_status':types.SimpleNamespace(adapt_main=refuse)}
        with self.assertRaisesRegex(ValueError,'exact three-owner continuation refused'):
            exec(compile(ast.fix_missing_locations(ast.Module(body=[current],type_ignores=[])),'fresh-main','exec'),scope)
        self.assertIs(scope['payload'],before);self.assertNotIn('frame_status_main_contract',scope)

    def test_manifest_exposes_the_exact_current_contract(self):
        matches=[]
        for node in ast.walk(self.builder()):
            if isinstance(node,ast.Dict):
                matches.extend(value for key,value in zip(node.keys,node.values)if isinstance(key,ast.Constant)and key.value==insets.MANIFEST)
        self.assertEqual(len(matches),1);self.assertIsInstance(matches[0],ast.Name)
        self.assertEqual(matches[0].id,'frame_status_main_contract')

    def verifier(self):
        path=ROOT/'tools/maru_companion.py'
        method=next(node for node in ast.parse(path.read_text()).body if isinstance(node,ast.FunctionDef)and node.name=='verify_merged')
        scope={};exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),str(path),'exec'),scope)
        return scope['verify_merged']

    def test_verifier_rolls_exact_current_main_before_workflow(self):
        class StopAfterExactPredecessor(Exception):pass
        calls=[];original_info={'raw':'unchanged'};original_resources={(1,2,3):b'original'}
        restored_info={'raw':'restored'};restored_resources={(1,2,3):b'restored'}
        current=types.ModuleType('cas_grid_frame_status');previous=types.ModuleType('cas_list_insets')
        def outer(info,resources):
            self.assertIs(info,original_info);self.assertIs(resources,original_resources)
            calls.append('insets');return restored_info,restored_resources
        def inner(info,resources):
            self.assertIs(info,restored_info);self.assertIs(resources,restored_resources)
            calls.append('workflow');raise StopAfterExactPredecessor()
        current.unwrap_manifest=outer;previous.unwrap_manifest=inner
        with patch.dict(sys.modules,{'cas_grid_frame_status':current,'cas_list_insets':previous}),self.assertRaises(StopAfterExactPredecessor):
            self.verifier()(original_info,original_resources)
        self.assertEqual(calls,['insets','workflow'])

    def test_refused_outer_proof_never_falls_through(self):
        calls=[];current=types.ModuleType('cas_grid_frame_status');previous=types.ModuleType('cas_list_insets')
        def refuse(info,resources):calls.append('insets');raise ValueError('exact list inset proof refused')
        def forbidden(info,resources):calls.append('workflow');raise AssertionError('refused outer proof fell through')
        current.unwrap_manifest=refuse;previous.unwrap_manifest=forbidden
        with patch.dict(sys.modules,{'cas_grid_frame_status':current,'cas_list_insets':previous}),self.assertRaisesRegex(ValueError,'exact list inset proof refused'):
            self.verifier()({}, {})
        self.assertEqual(calls,['insets'])

    def test_provider_finish_and_library_cache_never_compile_main(self):
        for node in self.builder().body:
            if isinstance(node,ast.FunctionDef)and(node.name.startswith('finish_grid_provider')or node.name.startswith('_finish_grid_provider')or node.name=='verified_library_cache'):
                with self.subTest(function=node.name):
                    calls=[child for child in ast.walk(node)if isinstance(child,ast.Call)and isinstance(child.func,ast.Attribute)and child.func.attr=='adapt_main']
                    self.assertEqual(calls,[])

    def test_all_eight_stage_sources_are_pinned_once(self):
        import cas_grid_logical_bank as bank
        pins=next(ast.literal_eval(node.value)for node in self.builder().body if isinstance(node,ast.Assign)and any(isinstance(target,ast.Name)and target.id=='PINNED_SOURCES'for target in node.targets))
        self.assertEqual(len(bank.SOURCES+insets.SOURCES),8)
        for name in bank.SOURCES+insets.SOURCES:self.assertEqual(pins.count(name),1)

    def test_actual_new_terminal_and_native_prefix_continue_without_fallback(self):
        from tests.test_cas_grid_budget_cache import CacheTests
        harness=CacheTests('runTest')
        result,calls,cache,prior,key=harness.cached('frame-status')
        self.assertEqual([name for name,args in calls],['cas_grid_frame_status.verify','cas_grid_eof.adapt']);self.assertEqual(result[0],b'cas_grid_eof');self.assertIs(result[1]['previous_stage_adapter'],prior);self.assertIn('continued',cache)
        result,calls,cache,prior,key=harness.cached('position')
        self.assertEqual([name for name,args in calls],['cas_grid_position.verify','cas_grid_logical_bank.adapt','cas_grid_frame_status.adapt','cas_grid_eof.adapt'])
        self.assertIs(result[1]['previous_stage_adapter']['previous_stage_adapter']['previous_stage_adapter'],prior);self.assertIn('continued',cache)


if __name__=='__main__':unittest.main()
