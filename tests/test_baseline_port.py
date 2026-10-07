import io
from pathlib import Path
import sys
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from build_script import compile_payloads
from fetch_build_python import DEFAULT_OUTPUT
from inspect_script_code import inspect
from port_baseline_scripts import port


class NamespacePortTests(unittest.TestCase):
    def test_nested_namespaces_change_without_changing_instructions_or_tuning_ids(self):
        source = b'import OccultHybrid.IC_Hybrid\ndef nested():\n    return ("OccultHybrid.IC_Hybrid", 18197032510434408842)\n'
        compiled, _ = compile_payloads([('OccultHybrid/example.py', source)], DEFAULT_OUTPUT / 'python.exe')
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            for name, raw in compiled:
                archive.writestr(name, raw)
        adapted, records = port(stream.getvalue())
        second = io.BytesIO()
        with zipfile.ZipFile(second, 'w') as archive:
            for name, raw in adapted:
                archive.writestr(name, raw)
        original = inspect(stream.getvalue(), 'OccultHybrid/example.pyc')
        migrated = inspect(second.getvalue(), 'apex_hybrid/example.pyc')
        self.assertEqual([row['instruction_sha256'] for row in original], [row['instruction_sha256'] for row in migrated])
        self.assertIn('apex_hybrid.IC_Hybrid', migrated[0]['names'])
        self.assertIn(18197032510434408842, migrated[1]['constants'])
        self.assertEqual(migrated[1]['filename'], 'apex_hybrid/example.py')
        self.assertEqual(len(records), 1)

    def test_unexpected_outside_module_is_rejected(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('../outside.py', 'raise RuntimeError("must never execute")')
        with self.assertRaises(ValueError):
            port(stream.getvalue())
