import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import game_lifecycle
import windows_ocr


def observation(scale=2):
    labels = ['MENU', 'Save', 'Save As...', 'Exit Game']
    return {'ok': True, 'width': 1278, 'height': 1376, 'future_diagnostic': {'preserved': True},
            'preprocessing': {'requested_scale': 2, 'scale': scale, 'ocr_width': 1278 * scale,
                              'ocr_height': 1376 * scale, 'interpolation': 'cubic', 'coordinates': 'scaled-bitmap'},
            'lines': [{'text': label, 'future_line': index,
                       'words': [{'text': label, 'x': 200 * scale, 'y': (100 + index * 40) * scale,
                                  'width': 100 * scale, 'height': 20 * scale, 'future_word': {'raw': 'kept'}}]}
                      for index, label in enumerate(labels)]}


def home_observation(home=False):
    result = observation()
    labels = ['MARKETPLACE', 'LOAD GAME', 'NEW GAME', 'GALLERY', 'RESUME GAME']
    if home: labels.insert(0, 'HOME')
    result['lines'] = [{'text': text, 'words': [{'text': text, 'x': 200, 'y': 100 + index * 80,
        'width': 300, 'height': 40}]} for index, text in enumerate(labels)]
    return result


class CoordinateTests(unittest.TestCase):
    def test_two_times_coordinates_return_to_original_viewport_without_losing_fields(self):
        source = observation()
        unchanged = copy.deepcopy(source)
        result = windows_ocr.original_viewport(source, 2)
        self.assertEqual(source, unchanged)
        self.assertEqual((result['width'], result['height']), (1278, 1376))
        self.assertEqual(result['preprocessing']['coordinates'], 'original-viewport')
        self.assertEqual(result['future_diagnostic'], source['future_diagnostic'])
        self.assertEqual(result['lines'][3]['future_line'], 3)
        word = result['lines'][3]['words'][0]
        self.assertEqual({key: word[key] for key in ('x', 'y', 'width', 'height')},
                         {'x': 200, 'y': 220, 'width': 100, 'height': 20})
        self.assertEqual(word['future_word'], {'raw': 'kept'})
        self.assertEqual(game_lifecycle.button(result, 'menu'),
                         {'command': 1, 'x': 250, 'y': 230, 'width': 1278, 'height': 1376})

    def test_bounded_one_times_fallback_keeps_original_positions(self):
        source = observation(scale=1)
        result = windows_ocr.original_viewport(source, 2)
        self.assertEqual(result['lines'], source['lines'])
        self.assertEqual(result['preprocessing']['scale'], 1)

    def test_fractional_rectangles_map_exactly_without_rounded_or_fixed_click_positions(self):
        source = observation()
        word = source['lines'][3]['words'][0]
        word.update(x=400.5, y=440.25, width=200.5, height=40.5)
        result = windows_ocr.original_viewport(source, 2)
        actual = result['lines'][3]['words'][0]
        self.assertEqual((actual['x'], actual['y'], actual['width'], actual['height']),
                         (200.25, 220.125, 100.25, 20.25))

    def test_scaling_does_not_weaken_complete_menu_or_ambiguity_validation(self):
        source = observation()
        source['lines'].pop(1)  # Missing Save remains a refusal.
        with self.assertRaisesRegex(ValueError, 'not recognized'):
            game_lifecycle.button(windows_ocr.original_viewport(source, 2), 'menu')
        source = observation()
        source['lines'].append(copy.deepcopy(source['lines'][3]))
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            game_lifecycle.button(windows_ocr.original_viewport(source, 2), 'menu')

    def test_boolean_nonfinite_negative_or_outside_word_rectangles_refuse_geometry(self):
        for change in ({'x': True}, {'x': -0.5}, {'width': 0}, {'height': -1},
                       {'x': float('nan')}, {'y': float('inf')}, {'x': 10 ** 1000},
                       {'width': 3000}, {'y': 2700, 'height': 60}):
            source = observation()
            source['lines'][0]['words'][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                windows_ocr.original_viewport(source, 2)

    def test_unknown_scaling_original_dimensions_and_failed_or_double_mapped_observations_refuse(self):
        changes = [{'scale': True}, {'scale': 3}, {'ocr_width': 1278}, {'ocr_height': True},
                   {'requested_scale': 1}, {'coordinates': 'original-viewport'}]
        for change in changes:
            source = observation()
            source['preprocessing'].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                windows_ocr.original_viewport(source, 2)
        for change in ({'ok': False}, {'width': True}, {'height': 0}, {'preprocessing': None}, {'lines': None}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                windows_ocr.original_viewport(dict(observation(), **change), 2)

    def test_scaled_pixel_and_word_inventory_bounds_are_enforced(self):
        source = observation()
        source.update(width=4096, height=4096)
        source['preprocessing'].update(ocr_width=8192, ocr_height=8192)
        with self.assertRaisesRegex(ValueError, 'dimensions'):
            windows_ocr.original_viewport(source, 2)
        source = observation()
        source['lines'] = [source['lines'][0]] * 8193
        with self.assertRaisesRegex(ValueError, 'line inventory'):
            windows_ocr.original_viewport(source, 2)
        source = observation()
        source['lines'][0]['words'] = [source['lines'][0]['words'][0]] * 32769
        with self.assertRaisesRegex(ValueError, 'word inventory'):
            windows_ocr.original_viewport(source, 2)


@unittest.skipUnless(os.name == 'nt', 'Windows native OCR launcher')
class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.image = Path(self.temporary.name) / 'image.bmp'
        self.image.write_bytes(b'bounded capture fixture')

    def test_default_scale_two_is_sent_only_over_stdin_and_source_is_read_only(self):
        original = self.image.read_bytes()
        result = SimpleNamespace(returncode=0, stdout=json.dumps(observation()), stderr='')
        with patch.object(windows_ocr.subprocess, 'run', return_value=result) as run:
            observed = windows_ocr.recognize(self.image)
        args, kwargs = run.call_args
        self.assertEqual(json.loads(kwargs['input']), {'path': str(self.image.resolve()), 'scale': 2})
        self.assertEqual(kwargs['timeout'], 35)
        self.assertNotIn(str(self.image), args[0])
        self.assertEqual(self.image.read_bytes(), original)
        self.assertEqual(observed['preprocessing']['coordinates'], 'original-viewport')
        self.assertEqual(list(self.image.parent.iterdir()), [self.image])

    def test_invalid_scale_missing_input_and_native_failure_refuse_without_inventing_labels(self):
        with patch.object(windows_ocr.subprocess, 'run') as run:
            for scale in (True, 0, 3, 2.0):
                with self.subTest(scale=scale), self.assertRaises(ValueError):
                    windows_ocr.recognize(self.image, scale=scale)
            with self.assertRaises(ValueError):
                windows_ocr.recognize(self.image.with_name('absent.bmp'))
            run.assert_not_called()
        result = SimpleNamespace(returncode=1, stdout='', stderr='native decoder refused')
        with patch.object(windows_ocr.subprocess, 'run', return_value=result), self.assertRaisesRegex(ValueError, 'decoder refused'):
            windows_ocr.recognize(self.image)

    def test_empty_scaled_inventory_uses_independent_native_size_read_of_same_frame(self):
        empty = observation(); empty['lines'] = []
        native = observation(scale=1); native['preprocessing']['requested_scale'] = 1
        replies = [SimpleNamespace(returncode=0, stdout=json.dumps(row), stderr='') for row in (empty, native)]
        with patch.object(windows_ocr.subprocess, 'run', side_effect=replies) as run:
            observed = windows_ocr.recognize(self.image)
        self.assertEqual([json.loads(call.kwargs['input'])['scale'] for call in run.call_args_list], [2, 1])
        self.assertTrue(observed['scaling_fallback']['accepted'])
        self.assertEqual(observed['raw_observation']['lines'], [])
        self.assertEqual(observed['lines'][0]['words'][0]['x'], 200)
        self.assertEqual(self.image.read_bytes(), b'bounded capture fixture')

    def test_capture_change_during_native_size_read_blocks_geometry(self):
        empty = observation(); empty['lines'] = []
        native = observation(scale=1); native['preprocessing']['requested_scale'] = 1
        replies = iter((empty, native))
        def reply(*_args, **_kwargs):
            row = next(replies)
            if row is native: self.image.write_bytes(b'changed native frame')
            return SimpleNamespace(returncode=0, stdout=json.dumps(row), stderr='')
        with patch.object(windows_ocr.subprocess, 'run', side_effect=reply), self.assertRaisesRegex(ValueError, 'changed'):
            windows_ocr.recognize(self.image)


@unittest.skipUnless(os.name == 'nt', 'Windows native OCR launcher')
class ContrastTests(unittest.TestCase):
    def setUp(self):
        from PIL import Image
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.image = Path(self.temporary.name) / 'capture.bmp'
        image = Image.new('RGB', (1278, 1376), (110, 255, 100))
        image.putpixel((0, 0), (0, 0, 0)); image.putpixel((1, 0), (255, 255, 255))
        image.save(self.image)
        self.original = self.image.read_bytes()

    def reply(self, value):
        return SimpleNamespace(returncode=0, stdout=json.dumps(value), stderr='')

    def test_full_frame_grayscale_keeps_real_pixels_geometry_and_source_read_only(self):
        from PIL import Image, ImageOps
        paths = []
        def run(_args, **kwargs):
            request = json.loads(kwargs['input']); path = Path(request['path']); paths.append(path)
            if len(paths) == 1:
                self.assertEqual(path, self.image.resolve())
                return self.reply(home_observation())
            self.assertNotEqual(path, self.image)
            with Image.open(path) as derived, Image.open(self.image) as source:
                self.assertEqual(derived.size, source.size)
                self.assertEqual(derived.mode, 'L')
                self.assertEqual(derived.tobytes(), ImageOps.autocontrast(ImageOps.grayscale(source)).tobytes())
            self.assertGreater(kwargs['timeout'], 0); self.assertLessEqual(kwargs['timeout'], 35)
            return self.reply(home_observation(home=True))
        with patch.object(windows_ocr.subprocess, 'run', side_effect=run):
            result = windows_ocr.recognize(self.image)
        self.assertEqual(len(paths), 2); self.assertFalse(paths[1].exists())
        self.assertEqual(self.image.read_bytes(), self.original)
        self.assertEqual(list(self.image.parent.iterdir()), [self.image])
        self.assertEqual(result['preprocessing']['source_sha256'], hashlib.sha256(self.original).hexdigest())
        self.assertEqual(result['preprocessing']['color_transform'], 'full-frame-grayscale-autocontrast')
        self.assertEqual(result['preprocessing']['coordinates'], 'original-viewport')
        self.assertNotIn('HOME', [line['text'] for line in result['raw_observation']['lines']])
        self.assertEqual(game_lifecycle.button(result, 'resume'),
                         {'command': 1, 'x': 175, 'y': 260, 'width': 1278, 'height': 1376})

    def test_existing_home_other_surface_duplicates_and_dialogs_never_trigger_fallback(self):
        samples = [home_observation(home=True), observation()]
        for label in ('MARKETPLACE', 'RESUME GAME', 'Cancel', 'Buy Now', 'Save Game?'):
            sample = home_observation()
            sample['lines'].append({'text': label, 'words': [{'text': label, 'x': 100, 'y': 100, 'width': 80, 'height': 30}]})
            samples.append(sample)
        for sample in samples:
            with self.subTest(sample=sample), patch.object(windows_ocr.subprocess, 'run', return_value=self.reply(sample)) as run:
                result = windows_ocr.recognize(self.image)
                self.assertEqual(run.call_count, 1)
                self.assertNotIn('raw_observation', result)

    def test_failed_contrast_labels_do_not_synthesize_home_or_hide_ambiguity(self):
        samples = [home_observation(), home_observation(home=True), home_observation(home=True)]
        samples[1]['lines'].append(copy.deepcopy(samples[1]['lines'][0]))
        samples[2]['lines'].append({'text': 'Cancel', 'words': [{'text': 'Cancel', 'x': 100, 'y': 100, 'width': 80, 'height': 30}]})
        for sample in samples:
            with self.subTest(sample=sample), patch.object(windows_ocr.subprocess, 'run',
                    side_effect=[self.reply(home_observation()), self.reply(sample)]) as run:
                result = windows_ocr.recognize(self.image)
                self.assertEqual(run.call_count, 2)
                self.assertFalse(result['contrast_fallback']['accepted'])
                with self.assertRaisesRegex(ValueError, 'Home menu'):
                    game_lifecycle.button(result, 'resume')

    def test_dimension_change_and_source_change_fail_closed(self):
        changed = home_observation(home=True); changed['width'] = 1279
        changed['preprocessing']['ocr_width'] = 2558
        with patch.object(windows_ocr.subprocess, 'run', side_effect=[self.reply(home_observation()), self.reply(changed)]):
            with self.assertRaisesRegex(ValueError, 'viewport changed'):
                windows_ocr.recognize(self.image)
        def run(_args, **_kwargs):
            self.image.write_bytes(b'changed capture')
            return self.reply(home_observation())
        with patch.object(windows_ocr.subprocess, 'run', side_effect=run):
            with self.assertRaisesRegex(ValueError, 'Capture changed'):
                windows_ocr.recognize(self.image)

    def test_total_fallback_deadline_is_bounded(self):
        with patch.object(windows_ocr.subprocess, 'run', return_value=self.reply(home_observation())) as run:
            with patch.object(windows_ocr.time, 'monotonic', side_effect=[10, 46]):
                with self.assertRaisesRegex(ValueError, 'total deadline'):
                    windows_ocr.recognize(self.image)
        self.assertEqual(run.call_count, 1)


if __name__ == '__main__':
    unittest.main()
