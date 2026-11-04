# SPDX-License-Identifier: GPL-3.0-or-later
import io
import random
import unittest
from atlas_visibility import compare_chunks, compare_streams, CHUNK_PIXELS

class VisibilityTests(unittest.TestCase):
    def test_opaque_layer_hides_change(self):
        r = compare_chunks(bytes([10,20,30,255]), bytes([0,0,0,255]), bytes([255,0,0,255]), [bytes([2,3,4,255])])
        self.assertEqual((r['initially_changed'], r['initial_changes_under_opaque_upper'], r['final_changed']), (1,1,0))
    def test_transparent_and_partial_layers(self):
        r = compare_chunks(bytes([10,20,30,255])*2, bytes([0,0,0,255])*2, bytes([255,0,0,255])*2, [bytes([255,255,255,0, 255,255,255,128])])
        self.assertEqual(r['changed_after_each_upper'], [2]); self.assertEqual(r['initial_changes_under_opaque_upper'], 0)
    def test_transparent_rgb_changes_do_not_count(self):
        r = compare_chunks(bytes([10,20,30,255]), bytes([1,2,3,0]), bytes([9,8,7,0]), [])
        self.assertEqual(r['initially_changed'], 0); self.assertEqual(r['final_changed'], 0)
    def test_upper_can_round_away_difference(self):
        r = compare_chunks(bytes([0,0,0,255]), bytes([0,0,0,255]), bytes([1,0,0,255]), [bytes([0,0,0,254])])
        self.assertEqual((r['initially_changed'], r['final_changed']), (1,0)); self.assertEqual(r['initial_changes_under_opaque_upper'],0)
    def test_matches_scalar_reference(self):
        rng = random.Random(614)
        def rgba(n, opaque=False):
            return bytes(channel for _ in range(n) for channel in (rng.randrange(256), rng.randrange(256), rng.randrange(256), 255 if opaque else rng.randrange(256)))
        n = 1000
        base, old, new, first, second = rgba(n, True), rgba(n), rgba(n), rgba(n), rgba(n)
        r = compare_chunks(base, old, new, [first, second])
        def over(dst, src):
            return [(src[k] * src[3] + dst[k] * (255 - src[3]) + 127) // 255 for k in range(3)]
        counts = [0, 0, 0]
        for i in range(n):
            j = i * 4
            a, b = over(base[j:j+3], old[j:j+4]), over(base[j:j+3], new[j:j+4])
            counts[0] += a != b
            for k, layer in enumerate((first, second)):
                a, b = over(a, layer[j:j+4]), over(b, layer[j:j+4])
                counts[k+1] += a != b
        self.assertEqual([r['initially_changed'], *r['changed_after_each_upper']], counts)
    def test_invalid_inputs_refused(self):
        for args in [(b'', b'', b'', []), (b'1234',b'123',b'1234',[]), (bytes([0,0,0,0]),bytes(4),bytes(4),[])]:
            with self.assertRaises(ValueError): compare_chunks(*args)
    def test_stream_multiple_chunks_and_mismatch(self):
        pixel=bytes([0,0,0,255]); changed=bytes([20,0,0,255]); n=CHUNK_PIXELS+1
        result=compare_streams([io.BytesIO(pixel*n),io.BytesIO(pixel*n),io.BytesIO(changed*n)])
        self.assertEqual(result['final_changed'], n)
        with self.assertRaises(ValueError): compare_streams([io.BytesIO(pixel),io.BytesIO(pixel),io.BytesIO(pixel*2)])

if __name__=='__main__': unittest.main()
