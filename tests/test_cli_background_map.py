"""Public map CLI transport wiring; no game, profile or real capture calls."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import apex_cli
import game_capture
import game_map
import game_map_play


class BackgroundMapCliTests(unittest.TestCase):
    def invoke(self, operation, background):
        argv = ['game', operation, '--state', 'fixture-state', '--output', 'fixture-output.json',
                '--sim-id', '12', '--household-id', '20', '--save-guid', '30', '--slot-id', '2',
                '--expected-save-sha256', 'a' * 64]
        if operation == 'map-select':
            argv += ['--world', 'Ondarion', '--load-proof', 'load.json', '--load-proof-sha256', 'b' * 64,
                     '--recovered-input-proof', 'recovered.json', '--recovered-input-sha256', 'c' * 64,
                     '--allow-autosave-drift']
            target, method = game_map, 'select_marker'
        else:
            argv += ['--selection-proof', 'selection.json', '--selection-proof-sha256', 'd' * 64,
                     '--seconds', '45']
            target, method = game_map_play, 'observe'
        if background:
            argv += ['--background']
        args = apex_cli.parser().parse_args(argv)
        native, capture = Mock(return_value={'ok': True}), Mock(return_value={'ok': True})
        identity = {'pid': 42}
        with patch.object(apex_cli, 'require_isolated', return_value=Path('fixture-profile')), \
                patch.object(apex_cli, 'verified_identity', return_value=identity) as identity_provider, \
                patch.object(apex_cli, 'owned_request', native), \
                patch.object(game_capture, 'capture', capture), \
                patch.object(target, method, return_value={'ok': True}) as observed:
            self.assertTrue(apex_cli.execute(args)['ok'])
        call = observed.call_args
        self.assertEqual(call.args[:3], (args.state, args.output, identity))
        self.assertEqual(call.args[4:9], ('12', '20', '30', 2, 'a' * 64))
        self.assertIs(call.kwargs['identity_provider'], identity_provider)
        if operation == 'map-select':
            self.assertEqual(call.args[9:], ('Ondarion', Path('load.json'), 'b' * 64,
                                            Path('recovered.json'), 'c' * 64))
            self.assertTrue(call.kwargs['allow_autosave_drift'])
        else:
            self.assertEqual(call.args[9:], (Path('selection.json'), 'd' * 64))
            self.assertEqual(call.kwargs['seconds'], 45)
        envelope = {'test_token': 'fixture-token', 'value':
                    {'command': 1, 'x': 10, 'y': 20, 'width': 100, 'height': 100}}
        encoded = json.dumps(envelope)
        request = call.args[3]
        observer = Mock()
        request(args.state, 'test_input', value=encoded, sim_id='12', seconds=7,
                submission_observer=observer)
        actual = native.call_args
        self.assertEqual(actual.args, (args.state, 'test_input'))
        self.assertEqual(actual.kwargs['sim_id'], '12')
        self.assertEqual(actual.kwargs['seconds'], 7)
        self.assertIs(actual.kwargs['submission_observer'], observer)
        routed = json.loads(actual.kwargs['value'])
        self.assertEqual(routed, dict(envelope, value=dict(envelope['value'], command=4 if background else 1)))
        self.assertEqual(json.loads(encoded)['value']['command'], 1)
        if background:
            self.assertIn('capture', call.kwargs)
            call.kwargs['capture'](args.state, Path('fixture.bmp'), request)
            self.assertEqual(capture.call_args.args, (args.state, Path('fixture.bmp'), request))
            self.assertEqual(capture.call_args.kwargs, {'background': True})
        else:
            self.assertIs(request, native)
            self.assertNotIn('capture', call.kwargs)
            capture.assert_not_called()
        request(args.state, 'test_snapshot', sim_id='12')
        self.assertEqual(native.call_args.args, (args.state, 'test_snapshot'))
        self.assertEqual(native.call_args.kwargs, {'sim_id': '12'})

    def test_background_map_select_maps_click_to_command4_and_capture_without_focus(self):
        self.invoke('map-select', True)

    def test_background_map_play_maps_click_to_command4_and_capture_without_focus(self):
        self.invoke('map-play', True)

    def test_normal_map_select_preserves_original_request_and_default_capture(self):
        self.invoke('map-select', False)

    def test_normal_map_play_preserves_original_request_and_default_capture(self):
        self.invoke('map-play', False)


if __name__ == '__main__':
    unittest.main()
