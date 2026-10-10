"""Synthetic map-marker validation; no game capture or native input."""
import copy
import json
from pathlib import Path
import sys
import unittest

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from game_map import marker_target
import game_map
from source_manifest import sha256, write_json
from test_game_save import SaveFixture, SIM, HOUSEHOLD, GUID


GREEN = (30, 180, 50)


def frame(size=(640, 480), labels=('ONDARION',)):
    image = Image.new('RGB', size, (25, 35, 45))
    observation = {'ok': True, 'width': size[0], 'height': size[1],
                   'lines': [{'text': label, 'words': [
                       {'text': label, 'x': 40, 'y': 20 + 30 * index,
                        'width': 180, 'height': 20}]} for index, label in enumerate(labels)]}
    return image, observation


def pair(image, origin=(300, 200), width=9, height=22, gap=1, color=GREEN):
    x, y = origin
    draw = ImageDraw.Draw(image)
    for start in (x, x + width + gap):
        draw.rectangle((start, y, start + width - 1, y + height - 1), fill=color)


class GameMapMarkerTests(unittest.TestCase):
    def assert_refused(self, image, observation, expected='ONDARION'):
        with self.assertRaises(ValueError):
            marker_target(image, observation, expected)

    def test_measured_geometry_returns_one_viewport_bound_click(self):
        image, observation = frame((1278, 1376))
        # Synthetic reproduction of measured bounds, not a runtime screenshot.
        pair(image, origin=(738, 723), width=7, height=20, gap=5)
        result = marker_target(image, observation, 'ONDARION')
        self.assertEqual({key: result[key] for key in ('command', 'x', 'y', 'width', 'height')},
                         {'command': 1, 'x': 748, 'y': 733, 'width': 1278, 'height': 1376})
        self.assertIs(type(result['x']), int)
        self.assertIs(type(result['y']), int)

    def test_center_uses_measured_half_open_pixel_bounds(self):
        image, observation = frame()
        pair(image)
        result = marker_target(image, observation, 'ONDARION')
        self.assertEqual((result['x'], result['y']), (310, 211))

    def test_two_valid_pairs_are_ambiguous(self):
        image, observation = frame()
        pair(image, origin=(100, 150))
        pair(image, origin=(400, 150))
        self.assert_refused(image, observation)

    def test_exact_unique_world_normalizes_case_and_whitespace_only(self):
        image, observation = frame(labels=('  oNdArIoN  ',))
        pair(image)
        self.assertEqual(marker_target(image, observation, '  ondarion  ')['command'], 1)
        for labels in (('WILLOW CREEK',), ('ONDARION HEIGHTS',), ('MY ONDARION',),
                       ('ONDARION', '  ondarion  ')):
            image, observation = frame(labels=labels)
            pair(image)
            with self.subTest(labels=labels):
                self.assert_refused(image, observation)
        image, observation = frame()
        pair(image)
        self.assert_refused(image, observation, 'WILLOW CREEK')

    def test_modal_labels_refuse_an_otherwise_valid_marker(self):
        for modal in ('SAVE GAME?', 'LEAVING SO SOON?'):
            image, observation = frame(labels=('ONDARION', modal))
            pair(image)
            with self.subTest(modal=modal):
                self.assert_refused(image, observation)

    def test_component_and_pair_size_limits_are_required(self):
        for dimensions in ({'width': 6}, {'height': 14}, {'height': 31},
                           {'width': 14}, {'gap': 0}, {'gap': 9}):
            image, observation = frame()
            pair(image, **dimensions)
            with self.subTest(dimensions=dimensions):
                self.assert_refused(image, observation)

    def test_components_require_exact_y_and_height(self):
        for offset, height in ((1, 22), (0, 21)):
            image, observation = frame()
            draw = ImageDraw.Draw(image)
            draw.rectangle((300, 200, 308, 221), fill=GREEN)
            draw.rectangle((310, 200 + offset, 318, 200 + offset + height - 1), fill=GREEN)
            with self.subTest(offset=offset, height=height):
                self.assert_refused(image, observation)

    def test_matching_bounds_alone_do_not_replace_minimum_area(self):
        image, observation = frame()
        # Each connected component spans 7x15 but contains only 24 pixels.
        for x in (300, 308):
            draw = ImageDraw.Draw(image)
            draw.line((x, 200, x, 214), fill=GREEN)
            draw.line((x, 200, x + 6, 200), fill=GREEN)
            draw.line((x, 214, x + 3, 214), fill=GREEN)
        self.assert_refused(image, observation)

    def test_area_ratio_boundary_accepts_half_and_refuses_less(self):
        for area, allowed in ((80, True), (79, False)):
            image, observation = frame()
            draw = ImageDraw.Draw(image)
            draw.rectangle((300, 200, 309, 215), fill=GREEN)  # 160 pixels.
            draw.rectangle((311, 200, 314, 215), fill=GREEN)
            draw.rectangle((315, 200, 320, 200), fill=GREEN)
            draw.rectangle((315, 215, 320, 215), fill=GREEN)
            draw.rectangle((315, 201, 314 + area - 76, 201), fill=GREEN)
            with self.subTest(area=area):
                if allowed:
                    self.assertEqual(marker_target(image, observation, 'ONDARION')['command'], 1)
                else:
                    self.assert_refused(image, observation)

    def test_edge_clipped_markers_are_not_click_targets(self):
        for origin in ((0, 200), (300, 0), (621, 200), (300, 458), (-1, 200)):
            image, observation = frame()
            pair(image, origin=origin)
            with self.subTest(origin=origin):
                self.assert_refused(image, observation)

    def test_ocr_dimensions_and_success_are_bound_to_image(self):
        image, observation = frame()
        pair(image)
        for change in ({'width': 639}, {'height': 481}, {'width': True},
                       {'height': 0}, {'ok': False}):
            with self.subTest(change=change):
                self.assert_refused(image, dict(observation, **change))
        untouched = copy.deepcopy(observation)
        marker_target(image, observation, 'ONDARION')
        self.assertEqual(observation, untouched)

    def test_green_thresholds_are_inclusive_and_each_rejection_matters(self):
        image, observation = frame()
        pair(image, color=(65, 165, 100))
        self.assertEqual(marker_target(image, observation, 'ONDARION')['command'], 1)
        for color in ((66, 200, 0), (0, 134, 0), (0, 200, 101), (65, 135, 71)):
            image, observation = frame()
            pair(image, color=color)
            with self.subTest(color=color):
                self.assert_refused(image, observation)

    def test_unrelated_green_pixels_do_not_create_or_move_target(self):
        image, observation = frame()
        draw = ImageDraw.Draw(image)
        draw.rectangle((40, 100, 100, 105), fill=GREEN)
        for x in range(450, 550, 3):
            draw.point((x, 350), fill=GREEN)
        self.assert_refused(image, observation)
        pair(image)
        result = marker_target(image, observation, 'ONDARION')
        self.assertEqual((result['x'], result['y']), (310, 211))

    def test_diagonal_noise_cannot_join_the_pair_under_four_connectivity(self):
        image, observation = frame()
        pair(image)
        # This pixel touches both lower corners diagonally, but neither by an edge.
        image.putpixel((309, 222), GREEN)
        result = marker_target(image, observation, 'ONDARION')
        self.assertEqual((result['x'], result['y']), (310, 211))


class GameMapTransactionTests(SaveFixture):
    def setUp(self):
        super().setUp()
        journal = json.loads(self.state.read_bytes())
        for index in range(13):
            path = self.profile / 'Mods/ApexTest' / ('Fixture{:02d}.package'.format(index))
            path.parent.mkdir(exist_ok=True); path.write_bytes(b'fixture artifact')
            journal['artifacts'].append({'name': path.name, 'sha256': sha256(path)})
        write_json(self.state, journal)
        extra = []
        for stem in ('Slot_00000002.save', 'Slot_ffffffff.save'):
            extra.extend([stem + '.ver{}'.format(index) for index in range(5)])
            extra.extend([stem + '.day.ver0', stem + '.day.ver1', stem + '.week.ver0'])
        extra.append('Slot_ffffffff.save')
        for name in extra:
            (self.profile / 'saves' / name).write_bytes(b'unchanged fixture')
        self.artifacts = journal['artifacts']
        self.before = game_map.game_lifecycle.all_save_files(self.profile)
        self.metadata = {'slot_id': 2, 'slot_name': 'Synthetic indexed save',
                         'save_guid': GUID, 'active_household_id': HOUSEHOLD}
        self.receipt = {'ok': True, 'native_code': 0, 'input_state': 4, 'input_version': 2,
                        'input_submitted': True, 'pointer_verified': True,
                        'execution': 'fixed-native-control', 'request_state': 'completed',
                        'request_id': 'b' * 32, 'cursor_client': {'x': 500, 'y': 200}, 'window_metrics': {'available': True,
                            'root_match': True, 'foreground_pid': 42, 'overlay_pid': 42,
                            'width': 640, 'height': 480}}
        self.prior_path = self.root / 'indexed-load.json'
        self.prior = {'operation': 'load-exact-existing-disposable-save', 'identity': self.identity,
                      'initial_surface': 'native-load-menu', 'inputs': self.artifacts,
                      'before_saves': self.before, 'after_saves': self.before,
                      'save_files_unchanged': True, 'input_replay_attempted': False,
                      'indexed_save_metadata': self.metadata,
                      'target': {'sim_id': SIM, 'household_id': HOUSEHOLD, 'save_guid': GUID,
                                 'slot_id': 2, 'file_sha256': self.digest},
                      'steps': [{'action': 'recognize-play', 'result': {'target': {
                          'command': 1, 'x': 500, 'y': 200, 'width': 640, 'height': 480}}},
                          {'action': 'input-play-intent', 'result': {'submission_attempted': True}},
                          {'action': 'test_input', 'result': {'request_id': 'b' * 32}}]}
        self.recovered_path = self.root / 'recovered-original-input.json'
        self.recovered = {'original_request_id': 'b' * 32, 'same_request_identity': True,
                          'result': self.receipt}
        self.output = self.root / 'map-proof.json'

    def run_marker(self, *, wrong_world=False, rejected_input=False, active_cas=False,
                   changed_identity=False, changed_after_capture=False, tampered_frame=False,
                   changed_saves=False, allow_autosave_drift=False, prior_autosave_drift=False,
                   input_autosave_drift=False, wrong_autosave_metadata=False):
        if prior_autosave_drift:
            for name in game_map.AUTOSAVE_DRIFT_FILES:
                (self.profile / 'saves' / name).write_bytes(b'observed autosave before marker')
        write_json(self.prior_path, self.prior); write_json(self.recovered_path, self.recovered)
        calls, current = [], dict(self.identity)
        if changed_identity: current['pid'] = 43
        diagnostics = {'ok': True, 'native_initializer_observed': False, 'native_peers': [],
                       'requests': [], 'socket_transport': {'bound': True, 'host': '127.0.0.1',
                           'port': 8021, 'startup_error': None, 'native_connection_verified': False}}
        if active_cas: diagnostics['native_peers'] = [{'sim_id': SIM, 'age_seconds': 0}]
        def request(_state, action, **kwargs):
            calls.append(action)
            if action == 'cas_ui_diagnostics': return diagnostics
            if action == 'overlay_hide': return {'ok': True, 'visible': False}
            if action == 'test_input':
                durable = json.loads(self.output.read_bytes())
                self.assertEqual([row['action'] for row in durable['steps']][-1], 'input-marker-intent')
                self.assertTrue(any(row['action'] == 'measured-played-lot-marker' for row in durable['steps']))
                self.assertEqual(json.loads(kwargs['value'])['value']['command'], 1)
                if changed_saves: self.slot.write_bytes(b'changed during native input')
                if input_autosave_drift:
                    (self.profile / 'saves/Slot_ffffffff.save').write_bytes(b'observed autosave after marker')
                delivered = copy.deepcopy(self.receipt)
                delivered['cursor_client'] = {key: json.loads(kwargs['value'])['value'][key] for key in ('x', 'y')}
                return {'ok': False, 'input_submitted': None} if rejected_input else delivered
            self.fail('Unexpected native action ' + action)
        def capture(_state, image_path, _request):
            image, _ = frame(); pair(image); image.save(image_path)
            if changed_after_capture: current['pid'] = 43
            return {'ok': True, 'capture_completed_verified': True, 'width': 640, 'height': 480,
                    'test_token': self.token, 'inputs': self.artifacts,
                    'sha256': '0' * 64 if tampered_frame else sha256(image_path)}
        def ocr(_path):
            return frame(labels=('WRONG WORLD',) if wrong_world else ('ONDARION',))[1]
        def metadata(path, expected):
            if path.name == 'Slot_ffffffff.save':
                return {'slot_id': 0xffffffff, 'save_guid': '1' if wrong_autosave_metadata else GUID,
                        'active_household_id': HOUSEHOLD, 'preferred_manual_slot_id': 2, 'file_sha256': expected}
            return self.metadata
        result = game_map.select_marker(self.state, self.output, self.identity, request,
            SIM, HOUSEHOLD, GUID, 2, self.digest, 'ONDARION', self.prior_path, sha256(self.prior_path),
            self.recovered_path, sha256(self.recovered_path), capture=capture, ocr=ocr,
            identity_provider=lambda _state: current, alive=lambda _pid: True,
            pause=lambda _seconds: None, metadata_reader=metadata,
            allow_autosave_drift=allow_autosave_drift)
        return result, json.loads(self.output.read_bytes()), calls

    def test_one_durable_marker_intent_then_capture_without_play_or_live_claim(self):
        result, proof, calls = self.run_marker()
        self.assertTrue(result['ok']); self.assertEqual(calls.count('test_input'), 1)
        self.assertTrue(proof['post_click_capture_verified']); self.assertTrue(proof['save_files_unchanged'])
        self.assertFalse(proof['play_input_accepted']); self.assertFalse(proof['native_live_verified'])
        self.assertFalse(proof['native_slot_verified']); self.assertFalse(proof['input_replay_attempted'])
        self.assertEqual(self.original_save.read_bytes(), b'owner save must never change')
        with self.assertRaisesRegex(ValueError, 'new external'):
            self.run_marker()

    def test_wrong_world_active_cas_changed_identity_or_capture_hash_submit_no_input(self):
        for flag in ('wrong_world', 'active_cas', 'changed_identity', 'changed_after_capture', 'tampered_frame'):
            if self.output.exists(): self.output.unlink()
            with self.subTest(flag=flag):
                result, proof, calls = self.run_marker(**{flag: True})
                self.assertFalse(result['ok']); self.assertNotIn('test_input', calls)
                self.assertFalse(proof['input_replay_attempted'])

    def test_unknown_input_result_is_not_replayed(self):
        result, proof, calls = self.run_marker(rejected_input=True)
        self.assertFalse(result['ok']); self.assertEqual(calls.count('test_input'), 1)
        self.assertFalse(proof['input_replay_attempted'])
        self.assertNotIn('post_click_capture_verified', proof)

    def test_changed_saves_fail_overall_after_single_click(self):
        result, proof, calls = self.run_marker(changed_saves=True)
        self.assertFalse(result['ok']); self.assertEqual(calls.count('test_input'), 1)
        self.assertFalse(proof['save_files_unchanged'])
        self.assertEqual(proof['outcome'], 'save-files-changed-unexpectedly')

    def test_explicit_autosave_drift_allows_marker_but_keeps_unchanged_gate_false(self):
        result, proof, calls = self.run_marker(allow_autosave_drift=True, prior_autosave_drift=True)
        self.assertTrue(result['ok']); self.assertEqual(calls.count('test_input'), 1)
        self.assertFalse(proof['save_files_unchanged']); self.assertTrue(proof['save_files_changed'])
        self.assertTrue(proof['operation_save_files_unchanged'])
        self.assertEqual({row['name'] for row in proof['save_delta']}, game_map.AUTOSAVE_DRIFT_FILES)
        self.assertFalse(proof['native_slot_verified']); self.assertFalse(proof['native_live_verified'])
        self.assertTrue(proof['final_save_boundary']['non_autosave_files_unchanged'])

    def test_explicit_autosave_change_after_marker_is_recorded_without_replay(self):
        result, proof, calls = self.run_marker(allow_autosave_drift=True, input_autosave_drift=True)
        self.assertTrue(result['ok']); self.assertEqual(calls.count('test_input'), 1)
        self.assertFalse(proof['save_files_unchanged']); self.assertFalse(proof['operation_save_files_unchanged'])
        self.assertEqual([row['name'] for row in proof['save_delta']], ['Slot_ffffffff.save'])

    def test_autosave_drift_requires_explicit_option_and_exact_indexed_metadata(self):
        with self.assertRaisesRegex(ValueError, 'explicitly permitted'):
            self.run_marker(prior_autosave_drift=True)
        with self.assertRaisesRegex(ValueError, 'autosave metadata differs'):
            self.run_marker(allow_autosave_drift=True, prior_autosave_drift=True, wrong_autosave_metadata=True)
        self.assertFalse(self.output.exists())

    def test_autosave_option_never_allows_normal_day_week_deleted_or_added_files(self):
        before = copy.deepcopy(self.before)
        for name in ('Slot_00000002.save', 'Slot_00000002.save.ver0', 'Slot_00000002.save.day.ver0',
                     'Slot_00000002.save.week.ver0', 'Slot_ffffffff.save.day.ver0', 'Slot_ffffffff.save.week.ver0'):
            after = copy.deepcopy(before); after[name]['sha256'] = '0' * 64
            with self.subTest(name=name), self.assertRaises(ValueError):
                game_map._save_boundary(before, after, True, self.profile, lambda *_args: {}, self.target)

        for mutation in ('deleted', 'added'):
            after = copy.deepcopy(before)
            if mutation == 'deleted': after.pop('Slot_ffffffff.save.ver0')
            else: after['another.save'] = after['Slot_ffffffff.save.ver0']
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'inventory names'):
                game_map._save_boundary(before, after, True, self.profile, lambda *_args: {}, self.target)

    def test_indexed_autosave_requires_typed_exact_preferred_manual_slot(self):
        for value in (True, '2', 3, None):
            metadata = {'slot_id': 0xffffffff, 'save_guid': GUID, 'active_household_id': HOUSEHOLD,
                        'preferred_manual_slot_id': value,
                        'file_sha256': self.before['Slot_ffffffff.save']['sha256']}
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'preferred slot'):
                game_map._save_boundary(self.before, self.before, True, self.profile,
                                        lambda *_args: metadata, self.target)

    def test_recovered_original_id_and_native_input_state_must_match(self):
        for change in ('different-request', 'noncompleted-input', 'wrong-cursor'):
            self.recovered = {'original_request_id': 'b' * 32, 'same_request_identity': True,
                              'result': copy.deepcopy(self.receipt)}
            if change == 'different-request': self.recovered['original_request_id'] = 'c' * 32
            elif change == 'noncompleted-input': self.recovered['result']['input_state'] = 3
            else: self.recovered['result']['cursor_client']['x'] += 1
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'Recovered original'):
                self.run_marker()
            self.assertFalse(self.output.exists())

    def test_changed_inventory_or_wrong_prior_operation_refuse_before_game_calls(self):
        for change in ('wrong-operation', 'wrong-inventory', 'not-indexed-play', 'extra-target',
                       'untyped-dimension', 'outside-target'):
            original = copy.deepcopy(self.prior)
            if change == 'wrong-operation': self.prior['operation'] = 'another-operation'
            elif change == 'wrong-inventory': self.prior['after_saves'] = {}
            elif change == 'not-indexed-play': self.prior['steps'][0]['action'] = 'recognize-home'
            elif change == 'extra-target': self.prior['steps'][0]['result']['target']['other'] = 1
            elif change == 'untyped-dimension': self.prior['steps'][0]['result']['target']['width'] = True
            else: self.prior['steps'][0]['result']['target']['x'] = 640
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.run_marker()
            self.assertFalse(self.output.exists()); self.prior = original


if __name__ == '__main__':
    unittest.main()
