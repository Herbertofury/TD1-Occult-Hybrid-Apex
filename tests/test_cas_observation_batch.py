import copy
from pathlib import Path
from types import SimpleNamespace as Obj
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from cas_client import observation_batch,_remember_observation,_recent_observation


class ObservationBatchTests(unittest.TestCase):
    def setUp(self):
        self.args=Obj(state=Path('disposable-fixture.json'),sim_id='123')
        self.row=dict(ok=True,cas_request_id='a'*32,client=dict(scope='native-cas-client',sim=dict(simId='123'),
            form_strip=dict(sim_id='123',selected_owner_id='native/2',native_owner_state='bound',
                desired_owner_id='',gesture_pending=False),future_field=[1,2]))

    def test_only_completed_same_member_subsecond_observations_can_be_reused(self):
        self.assertIsNone(_recent_observation(self.args,lambda:10))
        with observation_batch(self.args.state):
            before=copy.deepcopy(self.row)
            _remember_observation(self.args,self.row,lambda:10)
            cached=_recent_observation(self.args,lambda:10.5)
            self.assertEqual(cached['client'],self.row['client'])
            cached['client']['future_field'].append(3)
            self.assertEqual(_recent_observation(self.args,lambda:10.5)['client'],before['client'])
            self.assertIsNone(_recent_observation(self.args,lambda:11.01))
            self.assertIsNone(_recent_observation(self.args,lambda:9))
            self.assertIsNone(_recent_observation(Obj(state=self.args.state,sim_id='456'),lambda:10.5))
        self.assertIsNone(_recent_observation(self.args,lambda:10.5))

    def test_failed_or_unresolved_commands_invalidate_prior_ack(self):
        for failed in (dict(ok=False),dict(ok=False,outcome='pending-client'),dict(ok=True),dict(ok=True,client={})):
            with self.subTest(failed=failed),observation_batch(self.args.state):
                _remember_observation(self.args,self.row,lambda:10)
                _remember_observation(self.args,failed,lambda:10.1)
                self.assertIsNone(_recent_observation(self.args,lambda:10.2))

    def test_batch_cannot_change_profile_and_member_handoff_uses_destination_ack(self):
        with observation_batch(self.args.state):
            with self.assertRaises(ValueError):
                with observation_batch(Path('another-fixture.json')):pass
            target=copy.deepcopy(self.row);target['client']['sim']['simId']='456'
            target['client']['form_strip']['sim_id']='456'
            _remember_observation(self.args,dict(self.row,destination_status=target),lambda:10)
            self.assertIsNone(_recent_observation(self.args,lambda:10.1))
            self.assertEqual(_recent_observation(Obj(state=self.args.state,sim_id='456'),lambda:10.1)['client'],target['client'])

    def test_successful_peer_status_without_a_bound_form_is_not_reused(self):
        with observation_batch(self.args.state):
            _remember_observation(self.args,self.row,lambda:10)
            pending=copy.deepcopy(self.row)
            pending['client']['form_strip']={'sim_id':'123','selected_owner_id':'','native_owner_state':'','desired_owner_id':''}
            _remember_observation(self.args,pending,lambda:10.1)
            self.assertIsNone(_recent_observation(self.args,lambda:10.2))


if __name__=='__main__':unittest.main()
