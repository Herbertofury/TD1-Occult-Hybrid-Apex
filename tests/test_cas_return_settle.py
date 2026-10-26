import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from cas_return_settle import validate_prior,validate_current
from apex_cli import parser


class ReturnSettlementTests(unittest.TestCase):
    def prior(self):
        baseline=dict(sim_id='44',household_id='55',client_id='66',zone_id='77',save_guid='88',sim_time_source='services.time_service().sim_now',sim_now_ticks='100')
        paused=dict(baseline,ok=True,zone_running=True,in_build_buy=False,clock_speed=0,sim_now_ticks='866',
            sim=dict(id='44',instanced=True),runtime_queries={k:'returned-value' for k in ('client_id','zone_running','sim_now_ticks')})
        identity=dict(pid=123,test_token='a'*32,script_sha256='b'*64,profile='test-profile')
        prior=dict(operation='semantic-cas-return-to-live',ok=False,outcome='unresolved',identity=identity,sim_id='44',household_id='55',
            accept_submitted=True,accept_intent_observed=True,live_context_verified=True,final_paused=True,
            cas_bank_observe_attempted=False,form_bank_finish_attempted=False,return_metadata_completed=False,
            cas_request_id='c'*32,settle_ticks=30,producer_baseline=dict(ok=True,outcome='live-baseline',cas_request_id='c'*32,baseline=baseline),
            steps=[dict(action='test_pause',result=paused)])
        return prior,identity

    def test_retained_pause_proves_progress_without_playing_or_accepting_again(self):
        prior,identity=self.prior();original=copy.deepcopy(prior)
        sid,household,base,ticks,paused=validate_prior(prior,identity)
        self.assertEqual((sid,household,ticks),('44','55',30));self.assertEqual(int(paused['sim_now_ticks'])-int(base['sim_now_ticks']),766)
        self.assertEqual(prior,original)

    def test_prior_already_committed_unknown_identity_or_unpaused_is_not_authority(self):
        changes=({'ok':True},{'accept_submitted':False},{'accept_intent_observed':False},{'live_context_verified':False},
                 {'final_paused':False},{'cas_bank_observe_attempted':True},{'form_bank_finish_attempted':True},
                 {'return_metadata_completed':True},{'cas_request_id':'bad'},{'settle_ticks':True})
        for change in changes:
            prior,identity=self.prior();prior.update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):validate_prior(prior,identity)
        prior,identity=self.prior()
        with self.assertRaises(ValueError):validate_prior(prior,dict(identity,pid=124))

    def test_wrong_live_zone_timeline_or_insufficient_progress_refuses_metadata_completion(self):
        prior,identity=self.prior();sid,hh,base,ticks,paused=validate_prior(prior,identity)
        for change in ({'zone_id':'78'},{'save_guid':'89'},{'sim_time_source':'wall-clock'},
                       {'clock_speed':1},{'sim_now_ticks':'105'},{'zone_running':False}):
            with self.subTest(change=change),self.assertRaises(ValueError):validate_current(dict(paused,**change),sid,hh,base,ticks)

    def test_public_command_requires_exact_retained_proof_hash(self):
        args=parser().parse_args(['cas-return-settle','--state','state.json','--return-proof','return.json','--return-sha256','d'*64,'--output','settled.json'])
        self.assertEqual(args.command,'cas-return-settle');self.assertEqual(args.return_sha256,'d'*64)
