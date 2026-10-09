"""Independent synthetic map-Play fixtures; no game or owner profile access."""
import copy
import json
from pathlib import Path
import sys
import unittest

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import game_map_play
from source_manifest import sha256, write_json
from test_game_save import SaveFixture, SIM, HOUSEHOLD, GUID


def screen(size=(1278, 1376), household='Sim', caption='Bright Cliff Apartments', description=True):
    image = Image.new('RGB', size, (25, 35, 45))
    width, height = size
    if description:
        ImageDraw.Draw(image).rectangle((22, int(height * .78), int(width * .345), int(height * .938)),
                                       fill=(255, 255, 255))
    labels = [(caption, width * .38, 12, 300),
              (household, width * .175, height * .735, 35),
              ('Funds: $2,025', width * .14, height * .758, 125)]
    observation = {'ok': True, 'width': size[0], 'height': size[1],
                   'lines': [{'text': label, 'words': [{'text': label, 'x': x,
                       'y': y, 'width': span, 'height': 20}]}
                       for label, x, y, span in labels]}
    return image, observation


def play_icon(image, center=None, *, right=True, white=True):
    width, height = image.size
    x, y = center or (width - 67, height - 62)
    draw = ImageDraw.Draw(image)
    if white:
        draw.ellipse((x - 53, y - 53, x + 53, y + 53), fill=(250, 250, 250))
    if right:
        triangle = [(x - 18, y - 28), (x + 33, y), (x - 18, y + 28)]
    else:
        triangle = [(x + 18, y - 28), (x - 33, y), (x + 18, y + 28)]
    draw.polygon(triangle, fill=(15, 76, 175))


class MapPlayImageTests(unittest.TestCase):
    def test_click_is_measured_from_unique_filled_triangle(self):
        image, observed = screen()
        play_icon(image)
        result = game_map_play.play_target(image, observed, 'Sim')
        self.assertEqual(result['command'], 1)
        self.assertEqual((result['width'], result['height']), image.size)
        self.assertTrue(1193 <= result['x'] <= 1244)
        self.assertTrue(1286 <= result['y'] <= 1342)
        self.assertIs(type(result['x']), int)
        self.assertIs(type(result['y']), int)

    def test_measurement_follows_the_icon_instead_of_fixed_coordinates(self):
        image, observed = screen()
        play_icon(image, center=(1160, 1260))
        result = game_map_play.play_target(image, observed, 'Sim')
        self.assertTrue(1142 <= result['x'] <= 1193)
        self.assertTrue(1232 <= result['y'] <= 1288)

    def test_exact_household_and_complete_detail_labels_required(self):
        for missing in ('Sim', 'Funds: $2,025', 'Bright Cliff Apartments'):
            image, observed = screen(); play_icon(image)
            observed['lines'] = [row for row in observed['lines'] if row['text'] != missing]
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                game_map_play.play_target(image, observed, 'Sim')
        image, observed = screen(household='Another Sim'); play_icon(image)
        with self.assertRaises(ValueError):
            game_map_play.play_target(image, observed, 'Sim')
        image, observed = screen(description=False); play_icon(image)
        with self.assertRaises(ValueError):
            game_map_play.play_target(image, observed, 'Sim')

    def test_wrong_caption_and_blocking_dialog_refuse_existing_icon(self):
        for label in ('Another Apartment', 'SAVE GAME?', 'BUY NOW'):
            image, observed = screen(); play_icon(image)
            if label == 'Another Apartment':
                observed['lines'][0]['text'] = label
            else:
                observed['lines'].append({'text': label, 'words': []})
            with self.subTest(label=label), self.assertRaises(ValueError):
                game_map_play.play_target(image, observed, 'Sim')

    def test_multiple_right_triangles_are_ambiguous(self):
        image, observed = screen(); play_icon(image)
        play_icon(image, center=(1060, 1250))
        with self.assertRaises(ValueError):
            game_map_play.play_target(image, observed, 'Sim')

    def test_left_triangle_or_no_white_margin_is_not_play(self):
        for options in ({'right': False}, {'white': False}):
            image, observed = screen(); play_icon(image, **options)
            with self.subTest(options=options), self.assertRaises(ValueError):
                game_map_play.play_target(image, observed, 'Sim')

    def test_clipped_or_elsewhere_icon_is_not_safe_lower_right_play(self):
        for center in ((1270, 1350), (70, 100), (1200, 1370)):
            image, observed = screen(); play_icon(image, center=center)
            with self.subTest(center=center), self.assertRaises(ValueError):
                game_map_play.play_target(image, observed, 'Sim')

    def test_ocr_success_and_dimensions_match_the_actual_image(self):
        image, observed = screen(); play_icon(image)
        for change in ({'ok': False}, {'width': 1277}, {'height': True}, {'width': 9000}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                game_map_play.play_target(image, dict(observed, **change), 'Sim')

    def test_native_currency_alias_is_bounded_to_complete_funds_label(self):
        image, observed = screen(); play_icon(image)
        observed['lines'][2]['text'] = 'Funds: S 2,025'
        self.assertEqual(game_map_play.play_target(image, observed, 'Sim')['command'], 1)
        for text in ('Refunds: $2,025', 'Funds:', 'Funds: S', 'Funds: unlimited'):
            observed['lines'][2]['text'] = text
            with self.subTest(text=text), self.assertRaises(ValueError):
                game_map_play.play_target(image, observed, 'Sim')


class MapPlayTransactionTests(SaveFixture):
    def setUp(self):
        super().setUp()
        journal = json.loads(self.state.read_bytes())
        for index in range(13):
            path = self.profile / 'Mods/ApexTest' / ('Fixture{:02d}.package'.format(index))
            path.parent.mkdir(exist_ok=True); path.write_bytes(b'fixture artifact')
            journal['artifacts'].append({'name': path.name, 'sha256': sha256(path)})
        write_json(self.state, journal)
        self.artifacts = journal['artifacts']
        for stem in ('Slot_00000002.save', 'Slot_ffffffff.save'):
            for tail in ['.ver{}'.format(index) for index in range(5)] + ['.day.ver0', '.day.ver1', '.week.ver0']:
                (self.profile / 'saves' / (stem + tail)).write_bytes(b'unchanged fixture')
        (self.profile / 'saves/Slot_ffffffff.save').write_bytes(b'unchanged fixture')
        self.before = game_map_play.game_lifecycle.all_save_files(self.profile)
        self.metadata = {'slot_id': 2, 'slot_name': 'Synthetic indexed save',
                         'save_guid': GUID, 'active_household_id': HOUSEHOLD,
                         'file_sha256': self.digest, 'preferred_manual_slot_id': 2,
                         'household': {'id': HOUSEHOLD, 'name': 'Sim', 'member_ids': [SIM],
                                       'home_zone_id': '42', 'last_played_sim_id': SIM},
                         'sim': {'id': SIM, 'household_id': HOUSEHOLD, 'zone_id': '42'},
                         'selected_membership_verified': True, 'selected_household_is_active': True,
                         'save_file_written': False, 'game_modules_executed': False}
        self.receipt = {'ok': True, 'native_code': 0, 'input_state': 4, 'input_version': 2,
                        'input_submitted': True, 'pointer_verified': True,
                        'execution': 'fixed-native-control', 'request_state': 'completed',
                        'request_id': 'b' * 32, 'cursor_client': {'x': 100, 'y': 100},
                        'window_metrics': {'available': True, 'root_match': True,
                            'foreground_pid': 42, 'overlay_pid': 42, 'width': 1278, 'height': 1376}}
        image, observed = screen(); play_icon(image)
        self.prior_image = self.root / 'selected-household.bmp'; image.save(self.prior_image)
        self.prior_capture = {'ok': True, 'capture_completed_verified': True,
            'width': 1278, 'height': 1376, 'test_token': self.token, 'inputs': self.artifacts,
            'sha256': sha256(self.prior_image), 'output': str(self.prior_image)}
        self.capture_path = self.root / 'selected-capture.json'; write_json(self.capture_path, self.prior_capture)
        native_inputs = []
        for index in range(3):
            receipt = dict(self.receipt, request_id=str(index + 1) * 32)
            path = self.root / ('selection-input-{}.json'.format(index)); write_json(path, receipt)
            native_inputs.append({'proof': str(path), 'sha256': sha256(path), 'result': receipt,
                                  'target_provenance': 'Synthetic measured selection fixture.'})
        indexed = {key: value for key, value in self.metadata.items() if key not in
                   ('household', 'sim', 'selected_membership_verified', 'selected_household_is_active',
                    'game_modules_executed')}
        self.prior = {'schema': 1, 'ok': True, 'operation': 'select-existing-disposable-household-unit',
            'identity': self.identity, 'inputs': self.artifacts,
            'target': {'sim_id': SIM, 'household_id': HOUSEHOLD, 'save_guid': GUID,
                       'slot_id': 2, 'file_sha256': self.digest, 'world': 'ONDARION'},
            'indexed_save_metadata': indexed, 'indexed_household': self.metadata,
            'native_inputs': native_inputs, 'capture': {'proof': str(self.capture_path),
                'proof_sha256': sha256(self.capture_path), 'result': self.prior_capture},
            'selected_household_observation': observed, 'before_saves': self.before, 'after_saves': self.before,
            'save_files_unchanged': True, 'save_requested': False, 'save_file_written': False,
            'input_replay_attempted': False, 'native_live_verified': False, 'native_slot_verified': False}
        self.prior_path = self.root / 'selection.json'
        self.output = self.root / 'play-proof.json'

    def run_play(self, *, slot=2, changed_identity=False, active_cas=False, lost_input=False,
                 changed_after_capture=False, tampered_capture=False, changed_saves=False,
                 wrong_household=False, bad_persistence=False, running_clock=False,
                 changed_pre_input_save=False, transitional_snapshot=False,
                 transition_instanced=False, pause_failed=False):
        write_json(self.prior_path, self.prior)
        clock, calls, current = [0.0], [], dict(self.identity)
        if changed_identity: current['pid'] = 43
        diagnostic = {'ok': True, 'native_initializer_observed': False, 'native_peers': [], 'requests': [],
            'socket_transport': {'bound': True, 'host': '127.0.0.1', 'port': 8021,
                                'startup_error': None, 'native_connection_verified': False}}
        if active_cas: diagnostic['native_peers'] = [{'sim_id': SIM, 'age_seconds': 0}]
        live = {'ok': True, 'save_slot': slot, 'save_guid': GUID, 'household_id': HOUSEHOLD,
            'in_build_buy': False, 'zone_running': True, 'zone_id': '42', 'client_id': '7',
            'clock_speed': 1 if running_clock else 0, 'sim': {'id': SIM, 'instanced': True},
            'runtime_queries': {'client_id': 'returned-value', 'zone_running': 'returned-value'},
            'persistence': {'persistence_verified_before_save': True, 'checks': {key: True for key in
                ('active_household_membership', 'runtime_household_identity', 'manager_identity',
                 'account_save_eligible', 'sim_proto_exists', 'sim_proto_identity',
                 'sim_proto_household_identity', 'household_proto_exists', 'household_proto_identity',
                 'household_proto_membership')}}}
        if wrong_household: live['household_id'] = '123'
        if bad_persistence: live['persistence']['checks']['sim_proto_identity'] = False
        snapshots = [{'ok': False, 'zone_running': False, 'sim': None}] if transitional_snapshot else []
        if transition_instanced:
            snapshots = [{'ok': True, 'zone_running': False, 'sim': {'id': SIM, 'instanced': True}}]
        def request(_state, action, **kwargs):
            calls.append(action)
            if action == 'cas_ui_diagnostics': return copy.deepcopy(diagnostic)
            if action == 'overlay_hide': return {'ok': True, 'visible': False}
            if action == 'test_input':
                durable = json.loads(self.output.read_bytes())
                self.assertEqual(durable['steps'][-1]['action'], 'input-play-intent')
                value = json.loads(kwargs['value'])['value']
                self.assertEqual(value['command'], 1)
                if changed_saves: self.slot.write_bytes(b'changed by native fixture')
                if lost_input: return {'ok': False, 'outcome': 'unresolved', 'input_submitted': None}
                return dict(self.receipt, cursor_client={key: value[key] for key in ('x', 'y')})
            if action == 'test_snapshot': return snapshots.pop(0) if snapshots else copy.deepcopy(live)
            if action == 'test_pause':
                if not pause_failed: live['clock_speed'] = 0
                return copy.deepcopy(live)
            self.fail('Unexpected native action ' + action)
        def capture(_state, path, _request):
            image, _ = screen(); play_icon(image); image.save(path)
            if changed_after_capture: current['pid'] = 43
            if changed_pre_input_save: self.slot.write_bytes(b'changed before input')
            return dict(self.prior_capture, output=str(path),
                        sha256='0' * 64 if tampered_capture else sha256(path))
        result = game_map_play.observe(self.state, self.output, self.identity, request,
            SIM, HOUSEHOLD, GUID, 2, self.digest, self.prior_path, sha256(self.prior_path),
            seconds=1, capture=capture, ocr=lambda _path: screen()[1],
            identity_provider=lambda _state: current, alive=lambda _pid: True,
            metadata_reader=lambda _path, _hash, _household, _sim: copy.deepcopy(self.metadata),
            monotonic=lambda: clock[0], pause=lambda value: clock.__setitem__(0, clock[0] + value))
        self.assertEqual(self.original_save.read_bytes(), b'owner save must never change')
        return result, json.loads(self.output.read_bytes()), calls

    def test_one_durable_play_then_exact_paused_live_without_save_or_replay(self):
        result, proof, calls = self.run_play(running_clock=True)
        self.assertTrue(result['ok']); self.assertEqual(calls.count('test_input'), 1)
        self.assertIn('test_pause', calls)
        self.assertTrue(proof['native_slot_verified']); self.assertTrue(proof['native_live_verified'])
        self.assertFalse(proof['input_replay_attempted']); self.assertFalse(proof['save_requested'])
        self.assertTrue(proof['save_files_unchanged'])
        with self.assertRaisesRegex(ValueError, 'new external'):
            self.run_play()

    def test_autosave_sentinel_keeps_household_and_pause_proof_but_not_slot_success(self):
        result, proof, calls = self.run_play(slot=0xffffffff, running_clock=True)
        self.assertFalse(result['ok']); self.assertTrue(proof['household_verified'])
        self.assertFalse(proof['native_slot_verified'])
        self.assertIn('test_pause', calls); self.assertEqual(calls.count('test_input'), 1)
        self.assertFalse(proof['input_replay_attempted'])

    def test_unknown_input_is_retained_without_replay_or_live_claim(self):
        result, proof, calls = self.run_play(lost_input=True)
        self.assertFalse(result['ok']); self.assertEqual(calls.count('test_input'), 1)
        self.assertFalse(proof['native_live_verified']); self.assertFalse(proof['input_replay_attempted'])

    def test_changed_identity_active_cas_or_tampered_capture_blocks_input(self):
        for flag in ('changed_identity', 'active_cas', 'changed_after_capture', 'tampered_capture'):
            if self.output.exists(): self.output.unlink()
            with self.subTest(flag=flag):
                result, proof, calls = self.run_play(**{flag: True})
                self.assertFalse(result['ok']); self.assertNotIn('test_input', calls)
                self.assertFalse(proof['input_replay_attempted'])

    def test_wrong_household_or_incomplete_persistence_cannot_verify_live(self):
        for flag in ('wrong_household', 'bad_persistence'):
            if self.output.exists(): self.output.unlink()
            with self.subTest(flag=flag):
                result, proof, calls = self.run_play(**{flag: True})
                self.assertFalse(result['ok']); self.assertFalse(proof['native_live_verified'])
                self.assertEqual(calls.count('test_input'), 1)

    def test_normal_save_drift_fails_after_one_click(self):
        result, proof, calls = self.run_play(changed_saves=True)
        self.assertFalse(result['ok']); self.assertFalse(proof['save_files_unchanged'])
        self.assertEqual(calls.count('test_input'), 1)

    def test_normal_save_drift_before_submission_blocks_input(self):
        result, proof, calls = self.run_play(changed_pre_input_save=True)
        self.assertFalse(result['ok']); self.assertFalse(proof['save_files_unchanged'])
        self.assertNotIn('test_input', calls)

    def test_unavailable_transition_snapshot_is_observed_without_input_replay(self):
        result, proof, calls = self.run_play(transitional_snapshot=True)
        self.assertTrue(result['ok']); self.assertEqual(calls.count('test_input'), 1)
        self.assertTrue(proof['native_live_verified']); self.assertFalse(proof['input_replay_attempted'])

    def test_instanced_sim_during_nonrunning_zone_waits_for_actual_live(self):
        result, proof, calls = self.run_play(transition_instanced=True)
        self.assertTrue(result['ok']); self.assertEqual(calls.count('test_input'), 1)
        self.assertGreaterEqual(calls.count('test_snapshot'), 3)
        self.assertTrue(proof['native_live_verified']); self.assertFalse(proof['input_replay_attempted'])

    def test_failed_pause_preserves_observation_but_no_safe_live_verification(self):
        result, proof, calls = self.run_play(running_clock=True, pause_failed=True)
        self.assertFalse(result['ok']); self.assertFalse(proof['household_verified'])
        self.assertFalse(proof['native_live_verified']); self.assertFalse(proof['native_slot_verified'])
        self.assertEqual(proof['loaded_before_pause']['household_id'], HOUSEHOLD)
        self.assertEqual(proof['loaded_before_pause']['clock_speed'], 1)
        self.assertEqual(calls.count('test_input'), 1); self.assertEqual(calls.count('test_pause'), 1)
        self.assertFalse(proof['input_replay_attempted'])

    def test_wrong_prior_target_and_changed_native_input_proof_refuse_before_any_actions(self):
        self.prior['target']['household_id'] = '123'
        with self.assertRaises(ValueError): self.run_play()
        self.assertFalse(self.output.exists())
        self.prior['target']['household_id'] = HOUSEHOLD
        Path(self.prior['native_inputs'][0]['proof']).write_bytes(b'changed input evidence')
        with self.assertRaises(ValueError): self.run_play()
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
