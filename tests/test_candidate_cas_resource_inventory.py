"""Execute the real CAS bundle admission block without building any artifact."""
import ast
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_candidate
import dbpf_build
import maru_companion

PACKAGE = ROOT / 'dist/candidate/ApexCASBridge.package'
MANIFEST = Path(str(PACKAGE) + '.manifest.json')


@unittest.skipUnless(PACKAGE.is_file() and MANIFEST.is_file(), 'Private sealed CAS package required')
class CandidateCASInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = PACKAGE.read_bytes()
        cls.info = json.loads(MANIFEST.read_text())
        cls.resources = dbpf_build.read(cls.raw)
        if maru_companion.UNMODIFIED_OLYMPUS_LIBRARY not in cls.resources:
            raise unittest.SkipTest('Current 73-resource CAS package required')
        tree = ast.parse(Path(build_candidate.__file__).read_text())
        build = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'build')
        branch = next(node for node in build.body if isinstance(node, ast.If)
                      and ast.unparse(node.test) == 'cas_ui_package is not None')
        start = next(i for i, node in enumerate(branch.body) if isinstance(node, ast.Expr)
                     and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
                     and node.value.func.id == 'verify_source_pins')
        end = next(i for i, node in enumerate(branch.body) if isinstance(node, ast.If)
                   and any(isinstance(child, ast.Constant) and child.value ==
                           'CAS bridge resource inventory differs from its exact verified inputs.'
                           for child in ast.walk(node)))
        cls.block = compile(ast.Module(body=branch.body[start:end + 1], type_ignores=[]),
                            '<actual-candidate-CAS-admission>', 'exec')

    def execute(self, resources=None, info=None):
        # Decode once from the real package, then inject index mutations only.
        # Neither build_candidate.build nor a package/zip writer is called.
        resources = self.resources if resources is None else resources
        namespace = vars(build_candidate).copy()
        class Snapshot:
            def read_bytes(snapshot):
                return self.raw
        namespace.update(ui_info=copy.deepcopy(self.info if info is None else info),
                         ui_path=Snapshot(), read=lambda raw: resources)
        verified = []
        native_verify = maru_companion.verify_merged
        def verify_merge(evidence, decoded):
            verified.append(True)
            return native_verify(evidence, decoded)
        self.last_namespace = namespace
        with patch.object(maru_companion, 'verify_merged', side_effect=verify_merge):
            exec(self.block, namespace)
        self.assertEqual(verified, [True])
        return namespace

    def test_real_73_resource_package_passes_the_actual_bundle_inventory_gate(self):
        namespace = self.execute()
        self.assertEqual(len(self.resources), 73)
        self.assertEqual(len(namespace['expected_ui_resources']), 73)
        self.assertIn(dbpf_build.tgi(maru_companion.UNMODIFIED_OLYMPUS_LIBRARY), namespace['expected_ui_resources'])
        self.assertEqual(namespace['expected_ui_resources'], {dbpf_build.tgi(key) for key in self.resources})

    def test_an_extra_tgi_is_not_admitted_by_the_authenticated_dependency_allowance(self):
        resources = dict(self.resources)
        resources[(0x62ECC59A, 0, 0x1111222233334444)] = b'unreviewed extra resource'
        with self.assertRaisesRegex(ValueError, 'resource inventory differs'):
            self.execute(resources=resources)
        self.assertEqual(len(self.last_namespace['expected_ui_resources']), 73)

    def test_original_dependency_bytes_are_rejected_before_inventory_admission(self):
        resources = dict(self.resources)
        resources[maru_companion.UNMODIFIED_OLYMPUS_LIBRARY] = (ROOT / '.work/research/OlympusLibrary.swf').read_bytes()
        with self.assertRaises(ValueError):
            self.execute(resources=resources)
        self.assertNotIn('expected_ui_resources', self.last_namespace)

    def test_missing_dependency_proof_cannot_enable_the_extra_tgi(self):
        info = copy.deepcopy(self.info)
        del info['communication_dependency_adapters']
        with self.assertRaises(ValueError):
            self.execute(info=info)
        self.assertNotIn('expected_ui_resources', self.last_namespace)


if __name__ == '__main__':
    unittest.main()
