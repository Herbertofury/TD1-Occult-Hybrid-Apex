from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'NativeOverlay'))
from verify_ts4_dx11_imports import PEError, verify


def image(symbol='D3D11CreateDevice', ordinal=False, delayed=False):
    data = bytearray(0x1000)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 0x3c, 0x80)
    data[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<HH', data, 0x84, 0x8664, 1)
    struct.pack_into('<H', data, 0x94, 240)
    optional = 0x98
    struct.pack_into('<H', data, optional, 0x20b)
    struct.pack_into('<Q', data, optional + 24, 0x140000000)
    struct.pack_into('<I', data, optional + 60, 0x200)
    struct.pack_into('<I', data, optional + 108, 16)
    entry, size = (13, 64) if delayed else (1, 40)
    struct.pack_into('<II', data, optional + 112 + entry * 8, 0x1000, size)
    section = optional + 240
    struct.pack_into('<IIII', data, section + 8, 0xe00, 0x1000, 0xe00, 0x200)
    if delayed:
        struct.pack_into('<8I', data, 0x200, 1, 0x1100, 0, 0x1200, 0x1200, 0, 0, 0)
    else:
        struct.pack_into('<5I', data, 0x200, 0x1200, 0, 0, 0x1100, 0x1200)
    data[0x300:0x30b] = b'd3d11.dll\0\0'
    struct.pack_into('<Q', data, 0x400, ((1 << 63) | 7) if ordinal else 0x1300)
    encoded = symbol.encode('ascii') + b'\0'
    data[0x502:0x502 + len(encoded)] = encoded
    return data


class ImportTests(unittest.TestCase):
    def test_valid_named_normal_and_delay_imports(self):
        for delayed in (False, True):
            result = verify(image(delayed=delayed))
            self.assertTrue(result['ok'])
            self.assertEqual(result['d3d11_imports'][0]['delay_load'], delayed)

    def test_extra_export_fails(self):
        with self.assertRaises(PEError):
            verify(image('D3D11On12CreateDevice'))

    def test_ordinal_is_not_assumed_supported(self):
        with self.assertRaises(PEError):
            verify(image(ordinal=True))

    def test_unrelated_ascii_strings_do_not_pass(self):
        data = image()
        struct.pack_into('<II', data, 0x98 + 112 + 8, 0, 0)
        with self.assertRaises(PEError):
            verify(data)

    def test_unmapped_import_rva_and_truncation_fail(self):
        data = image()
        struct.pack_into('<I', data, 0x200 + 12, 0x80000000)
        with self.assertRaises(PEError):
            verify(data)
        with self.assertRaises(PEError):
            verify(image()[:0x205])


if __name__ == '__main__':
    unittest.main()
