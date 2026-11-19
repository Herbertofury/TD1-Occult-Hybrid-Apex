import json
from pathlib import Path
import sys,unittest
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from game_lifecycle import background_request

class BackgroundLifecycleTests(unittest.TestCase):
    def test_typed_click_preserves_owner_envelope_and_converts_once(self):
        transport=Mock(return_value={'ok':True})
        original={'test_token':'f'*32,'value':{'command':1,'x':20,'y':30,'width':1278,'height':1376}}
        raw=json.dumps(original)
        background_request(transport)('state','test_input',value=raw,seconds=2)
        transported=json.loads(transport.call_args.kwargs['value'])
        self.assertEqual(transported,dict(original,value=dict(original['value'],command=4)))
        self.assertEqual(transport.call_args.kwargs['seconds'],2)
        self.assertEqual(json.loads(raw)['value']['command'],1)

    def test_ordinary_game_thread_actions_are_forwarded_unchanged(self):
        transport=Mock();background_request(transport)('state','test_snapshot',sim_id='12',value='null')
        transport.assert_called_once_with('state','test_snapshot',sim_id='12',value='null')

    def test_unrecognized_keyboard_or_unbounded_pointer_never_reaches_transport(self):
        original={'command':1,'x':20,'y':30,'width':1278,'height':1376}
        for changes in ({'command':2},{'command':True},{'x':-1},{'x':1278},{'height':8193},{'y':30.5},{'extra':'field'}):
            with self.subTest(changes=changes):
                transport=Mock()
                with self.assertRaises(ValueError):
                    background_request(transport)('state','test_input',value=json.dumps({'test_token':'f'*32,'value':dict(original,**changes)}))
                transport.assert_not_called()

if __name__=='__main__':unittest.main()
