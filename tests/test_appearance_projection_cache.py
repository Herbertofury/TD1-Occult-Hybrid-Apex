from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import outfit_snapshot as outfits, genetics_snapshot as genetics
from test_outfit_snapshot import outfit


class AppearanceProjectionCacheTests(unittest.TestCase):
    def setUp(self):
        outfits._small_normalize.cache_clear()
        genetics._small_normalize.cache_clear()

    def test_identical_bytes_parse_once_and_changed_unknown_fields_are_revalidated(self):
        for module, raw in ((outfits, outfit(0, 17)), (genetics, b'\x38\x01')):
            with self.subTest(module=module.__name__), patch.object(module, '_normalize', wraps=module._normalize) as parse:
                self.assertEqual(module.normalize(raw), module.normalize(bytes(bytearray(raw))))
                self.assertEqual(parse.call_count, 1)
                changed = raw + b'\xc0\x0c\x01'  # Unknown root varint remains exact.
                self.assertTrue(module.normalize(changed).endswith(b'\xc0\x0c\x01'))
                self.assertEqual(parse.call_count, 2)

    def test_large_inputs_do_not_enter_the_bounded_hot_cache(self):
        for module in (outfits, genetics):
            raw = b'x' * (module.NORMALIZE_CACHE_BYTES + 1)
            with self.subTest(module=module.__name__), patch.object(module, '_normalize', return_value=raw) as parse:
                module.normalize(raw);module.normalize(raw)
                self.assertEqual(parse.call_count, 2)
                self.assertEqual(module._small_normalize.cache_info().currsize, 0)

    def test_eviction_is_bounded_and_never_grants_appearance_write_authority(self):
        for module in (outfits, genetics):
            with self.subTest(module=module.__name__):
                for n in range(100):module.normalize(b'\x38' + bytes((n,)))
                self.assertEqual(module._small_normalize.cache_info().currsize, 32)
                self.assertEqual(module.normalize(b'\x38\x00'), b'\x38\x00')

    def test_invalid_values_and_failed_parses_are_never_cached_as_valid(self):
        for module in (outfits, genetics):
            with self.subTest(module=module.__name__):
                for raw in (bytearray(b'abc'), 'abc', None):
                    with self.assertRaises(ValueError):module.normalize(raw)
        for _ in range(2):
            with self.assertRaises(ValueError):outfits.normalize(b'\x0a\x10bad')
        self.assertEqual(outfits._small_normalize.cache_info().currsize, 0)


if __name__ == '__main__':unittest.main()
