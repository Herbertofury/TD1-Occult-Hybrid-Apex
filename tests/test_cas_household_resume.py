"""Resume only certified unsent household steps; never replay completed work."""
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from source_manifest import sha256
import test_cas_household_commit as fixture


class HouseholdResumeTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.HouseholdCommitTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.phases={'100':'captured','200':'captured'}
        self.hashes={'100':'e'*64,'200':'e'*64};self.stop=('cas_bank_prepare','200')
        self.uncertain=False;self.round=0
        original=self.f.request
        def request(state,action,sim_id,value,seconds,submission_observer):
            if self.stop==(action,sim_id):
                self.stop=None
                raise ValueError('Test artifacts or journal changed during this CLI batch; no request sent.')
            result=original(state,action,sim_id,value,seconds,submission_observer)
            if action=='cas_bank_status':
                phase=self.phases[sim_id]
                result.update(phase=phase,raw_return_sha256='d'*64 if phase!='captured' else None,
                    plan_sha256=self.hashes[sim_id] if phase in ('planned','completed') else None,
                    completed_receipt=phase=='completed',native_availability_restore_verified=phase=='completed',
                    native_write_possible=phase in ('completed','committing'),
                    native_write_attempted=phase in ('completed','committing'),
                    metadata_commit_persisted=phase=='completed')
            elif action=='cas_bank_observe':self.phases[sim_id]='observed'
            elif action=='cas_bank_prepare':self.phases[sim_id]='planned'
            elif action=='cas_bank_commit':
                self.phases[sim_id]='completed';result['all_native_owners_verified']=True
            return result
        self.f.request=request

    def resume(self):
        prior=self.f.args.output
        self.round+=1
        self.f.args.resume_proof=prior;self.f.args.resume_sha256=sha256(prior)
        self.f.args.output=self.f.root/('resume-'+str(self.round)+'.json')

    def count(self,action,sid):
        return sum(a==action and s==sid for s,a,_ in self.f.calls)

    def test_partial_plan_then_partial_commit_resume_retains_every_ack_and_never_repeats_mutations(self):
        self.assertFalse(self.f.run_tool()['ok'])
        self.resume();self.stop=('cas_bank_commit','200')
        self.assertFalse(self.f.run_tool()['ok'])
        self.resume();self.assertTrue(self.f.run_tool()['ok'])
        for sid in ('100','200'):
            for action in ('cas_bank_observe','cas_bank_prepare','cas_bank_commit'):
                self.assertEqual(self.count(action,sid),1,(action,sid))
        proof=json.loads(self.f.args.output.read_text())
        self.assertTrue(proof['certified_unsent_resume']);self.assertFalse(proof['automatic_replay_allowed'])
        self.assertTrue(proof['retained_owner_steps'])

    def test_unresolved_final_uuid_is_refused_before_any_new_owner_request(self):
        self.f.run_tool();prior=self.f.args.output
        data=json.loads(prior.read_text());data['steps'][-1]['request_id']='f'*32
        prior.write_text(json.dumps(data));self.resume();before=len(self.f.calls)
        with self.assertRaisesRegex(ValueError,'unresolved UUIDs'):self.f.run_tool()
        self.assertEqual(len(self.f.calls),before)

    def test_changed_explicit_form_decisions_refuse_before_any_new_request(self):
        self.f.run_tool();self.resume();self.f.args.accept=['100:4'];before=len(self.f.calls)
        with self.assertRaisesRegex(ValueError,'edit decisions'):self.f.run_tool()
        self.assertEqual(len(self.f.calls),before)

    def test_changed_native_plan_cannot_be_recreated_or_committed(self):
        self.f.run_tool();self.resume();self.hashes['100']='f'*64
        self.assertFalse(self.f.run_tool()['ok'])
        self.assertEqual(self.count('cas_bank_prepare','100'),1)
        self.assertEqual(self.count('cas_bank_commit','100'),0)

    def test_partial_native_write_cannot_be_treated_as_planned_or_completed(self):
        self.f.run_tool();self.resume();self.phases['100']='committing'
        self.assertFalse(self.f.run_tool()['ok'])
        self.assertFalse(any(action=='cas_bank_commit' for _sid,action,_value in self.f.calls))

    def test_wrong_hash_or_runtime_cannot_resume_a_retained_receiver(self):
        self.f.run_tool();self.resume();self.f.args.resume_sha256='0'*64;before=len(self.f.calls)
        with self.assertRaises(ValueError):self.f.run_tool()
        self.assertEqual(len(self.f.calls),before)
        self.f.args.resume_sha256=sha256(self.f.args.resume_proof)
        self.f.identity=dict(self.f.identity,pid=999)
        with self.assertRaisesRegex(ValueError,'runtime'):self.f.run_tool()
        self.assertEqual(len(self.f.calls),before)


if __name__=='__main__':unittest.main()
