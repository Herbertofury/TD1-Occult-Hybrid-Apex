"""Complete Studio data must fit the wire without dropping appearance fields."""
import ast
import json
from pathlib import Path
import unittest


class BridgePayloadTests(unittest.TestCase):
    def payload(self, value):
        source = Path(__file__).resolve().parents[1] / 'Source/td1_occult_hybrid_apex.py'
        tree = ast.parse(source.read_text(encoding='utf-8-sig'))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_http_payload')
        namespace = {'json': json}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
        return namespace['_http_payload'](value)

    def test_large_complete_hybrid_inventory_avoids_whitespace_overflow(self):
        # Many independent forms, outfits and parts, including future fields.
        part = dict(target='SKINDETAIL', cas_part_id='18446744073709551615',
                    label='Cr\u00e9ateur \u5934\u53d1', future={'unknown': [1, None, True]})
        value = dict(ok=True, form_inventory=[dict(flags=i, outfit_inventory=[
            dict(index=j, parts=[part] * 40) for j in range(14)]) for i in range(36)])
        self.assertGreater(len(json.dumps(value, indent=2).encode()), 4 * 1024 * 1024)
        wire = self.payload(value)
        headers, body = wire.split(b'\r\n\r\n', 1)
        self.assertLess(len(body), 4 * 1024 * 1024)
        self.assertIn(('Content-Length: ' + str(len(body))).encode(), headers)
        self.assertEqual(json.loads(body), value)

    def test_utf8_text_and_binary_responses_keep_exact_content_length(self):
        for value, expected in [('café', 'café'.encode()), (b'\x00\xff', b'\x00\xff')]:
            with self.subTest(value=value):
                headers, body = self.payload(value).split(b'\r\n\r\n', 1)
                self.assertEqual(body, expected)
                self.assertIn(('Content-Length: ' + str(len(expected))).encode(), headers)
