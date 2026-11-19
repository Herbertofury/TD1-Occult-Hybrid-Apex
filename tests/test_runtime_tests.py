import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from runtime_tests import RuntimeTest


class RuntimeSequenceTests(unittest.TestCase):
    def test_actual_actions_are_single_submit_and_settled_then_finally_paused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = {'token': 'a' * 32, 'artifacts': []}
            current, cursor, calls, pauses = ['original'], ['root'], [], []
            def request(state, action, sim_id, occult=None, value=None):
                calls.append(action)
                if action == 'studio_apply':
                    current[0], cursor[0] = ('edited', 'child') if value in ('preview', 'redo') else ('original', 'root')
                if action == 'test_snapshot':
                    return {'ok': True, 'sim': {'linked_forms': [{'flags': 4, 'outfit_sha256': 'other'}], 'current_form': 1}}
                if action == 'studio_status':
                    return {'ok': True, 'pending_preview': None, 'appearance_sha256': current[0], 'history_cursor': cursor[0]}
                if action == 'studio_color_inspect':
                    return {'ok': True, 'history_lane': 'lane', 'color_editor': {
                        'target': '0:HAIR', 'cas_part_id': '1', 'color_hex': '4000000000000000',
                        'appearance_sha256': 'original', 'resource_sha256': 'resource',
                        'channels': {key: {'enabled': True, 'value': 0, 'min': -0.5, 'max': 0.5, 'step': 0.05}
                                     for key in ('hue', 'saturation', 'brightness', 'opacity')}}}
                return {'ok': True, 'preview_id': {'studio_undo': 'undo', 'studio_redo': 'redo'}.get(action, 'preview')}
            with patch('runtime_tests.reusable_profile.load', return_value=(None, data, root / 'active', root / 'original')):
                test = RuntimeTest(root / 'state', '42', root / 'proof.json', request, pause=pauses.append)
                result = test.run('color-cycle')
            self.assertTrue(result['ok'], result)
            self.assertEqual(pauses, [3, 3, 3, 3])
            self.assertEqual(current[0], 'original')
            self.assertEqual(calls[-1], 'test_pause')
            self.assertEqual(calls.count('studio_apply'), 4)
            self.assertTrue(all(row['passed'] for row in result['assertions']))
            with patch('runtime_tests.reusable_profile.load', return_value=(None, data, root / 'active', root / 'original')):
                with self.assertRaisesRegex(ValueError, 'previous proof'):
                    RuntimeTest(root / 'state', '42', root / 'proof.json', request)

    def test_failed_mutation_stops_without_retry_and_leaves_explicit_pause_attempt(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            calls = []
            def request(state, action, *args, **kwargs):
                calls.append(action)
                if action == 'test_snapshot':
                    return {'ok': True, 'sim': {'membership': []}}
                return {'ok': action != 'add', 'outcome': 'unresolved' if action == 'add' else None}
            with patch('runtime_tests.reusable_profile.load', return_value=(None, {'token': 'a' * 32, 'artifacts': []}, root / 'active', root / 'original')):
                result = RuntimeTest(root / 'state', '42', root / 'proof.json', request).run('hybrid-cycle')
            self.assertFalse(result['ok'])
            self.assertEqual(calls.count('add'), 1)
            self.assertEqual(calls[-1], 'test_pause')
            self.assertFalse(json.loads((root / 'proof.json').read_text())['ok'])
