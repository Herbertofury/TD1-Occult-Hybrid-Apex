"""The real planner statements survive the async storage split unchanged."""
import ast
import copy
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / '.work/v340-bank-async-stage'


def method(path, owner, name):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    body = tree.body if owner is None else next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == owner).body
    return copy.deepcopy(next(n for n in body if isinstance(n, ast.FunctionDef) and n.name == name))


class NormalizeAsync(ast.NodeTransformer):
    def visit_FunctionDef(self, node):
        node.name = {'prepare_steps': 'prepare', '_write_steps': '_write'}.get(node.name, node.name)
        return self.generic_visit(node)
    def visit_YieldFrom(self, node):
        return self.visit(node.value)
    def visit_Attribute(self, node):
        node.attr = {'prepare_steps': 'prepare', '_write_steps': '_write',
                     'journal_writer_steps': 'journal_writer', '_prepare_failure': '_failure'}.get(node.attr, node.attr)
        return self.generic_visit(node)


class ActualPrepareSourceParityTests(unittest.TestCase):
    def test_complete_current_primitive_and_hair_planner_statements_are_retained(self):
        cases = [('cas_commit_plan.py', 'CasCommitTransaction', 'prepare'),
                 ('cas_commit_plan.py', 'CasCommitTransaction', '_write'),
                 ('cas_bank_transaction.py', '_HairTransaction', 'prepare')]
        for file, owner, name in cases:
            actual = method(ROOT / 'Source/apex_core' / file, owner, name)
            staged = method(STAGE / 'Source/apex_core' / file, owner, name + '_steps')
            staged = NormalizeAsync().visit(staged)
            with self.subTest(file=file, owner=owner, method=name):
                self.assertEqual(ast.dump(actual), ast.dump(staged))

    def test_complete_receiver_prepare_statements_retained_without_lock_held_across_yield(self):
        actual = method(ROOT / 'Source/apex_core/cas_bank_transaction.py', None, 'prepare')
        self.assertEqual(len(actual.body), 1)
        self.assertIsInstance(actual.body[0], ast.With)
        actual.body = actual.body[0].body
        staged = method(STAGE / 'Source/apex_core/cas_bank_transaction.py', None, 'prepare_steps')
        self.assertEqual(ast.dump(actual), ast.dump(NormalizeAsync().visit(staged)))


if __name__ == '__main__':
    unittest.main()
