"""Exercise the production restorer against native outfit-loading side effects."""
import ast
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / 'Source' / 'td1_occult_hybrid_apex.py'
tree = ast.parse(SOURCE.read_text(encoding='utf-8-sig'))
definition = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                  and node.name == '_restore_siminfo_payload')
scope = {'_copy_value': copy.deepcopy}
exec(compile(ast.Module(body=[definition], type_ignores=[]), str(SOURCE), 'exec'), scope)
restore = scope['_restore_siminfo_payload']


class RestoreGeneticsTests(unittest.TestCase):
    def owner(self, genetics):
        owner = SimpleNamespace(genetic_data=genetics, physique='before', outfits=None, sent=[])
        def load_outfits(outfits):
            owner.outfits = outfits
            owner.genetic_data = b'native outfit rebuild drops extra genetics'
        owner.load_outfits = load_outfits
        owner.resend_outfits = lambda: owner.sent.append(owner.genetic_data)
        return owner

    def test_exact_opaque_genetics_restored_after_native_outfits_rebuild(self):
        original = b'\x0a\x04genes\x2a\x07unknown'
        owner = self.owner(b'mutated')
        self.assertTrue(restore(owner, {'genetic_data': original, '__outfits__': b'outfits', 'physique': 'captured'}))
        self.assertEqual(owner.genetic_data, original)
        self.assertEqual(owner.outfits, b'outfits')
        self.assertEqual(owner.physique, 'captured')
        self.assertEqual(owner.sent, [original])

    def test_message_genetics_replace_instead_of_appending(self):
        class Message:
            def __init__(self): self.raw = b'existing'
            def Clear(self): self.raw = b''
            def MergeFromString(self, raw): self.raw += raw
        owner = self.owner(Message())
        message = owner.genetic_data
        def load_outfits(value): owner.genetic_data.raw += b'regenerated'; owner.outfits = value
        owner.load_outfits = load_outfits
        restore(owner, {'genetic_data': ('protobuf', b'captured-opaque'), '__outfits__': b'outfits'})
        self.assertIs(owner.genetic_data, message)
        self.assertEqual(message.raw, b'captured-opaque')

    def test_native_outfit_proto_is_loaded_before_final_genetics_assignment(self):
        class OutfitList:
            def ParseFromString(self, raw): self.raw = raw
        owner = self.owner(b'after serialization')
        protocolbuffers = SimpleNamespace(Outfits_pb2=SimpleNamespace(OutfitList=OutfitList))
        with patch.dict('sys.modules', {'protocolbuffers': protocolbuffers}):
            restore(owner, {'__outfits__': ('protobuf', b'captured outfit message'), 'genetic_data': b'exact genes'})
        self.assertEqual(owner.outfits.raw, b'captured outfit message')
        self.assertEqual(owner.genetic_data, b'exact genes')

    def test_missing_or_none_genetics_does_not_fabricate_a_value(self):
        owner = self.owner(b'existing')
        restore(owner, {'physique': 'changed', 'genetic_data': None})
        self.assertEqual(owner.genetic_data, b'existing')
