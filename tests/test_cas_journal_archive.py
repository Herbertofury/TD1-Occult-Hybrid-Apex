import copy
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import cas_journal_archive
import test_cas_bank_transaction as fixtures
from apex_core import cas_commit_plan as primitive


class ObservedArchiveValidationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.CasBankReceiverTests(methodName='runTest')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        f=self.fixture;f.begin();f.edit(2);f.observe()
        self.record=f.record()
        transaction=self.record['cas_transaction'];journal=transaction['journal']
        keys={'schema','state','identity','pending_sha256','original_owners','raw_return','raw_return_sha256',
              'native_write_attempted','bank_committed','automatic_replay_allowed'}
        journal={name:journal[name] for name in keys};journal['state']='raw-observed'
        transaction['journal']=journal;transaction['phase']='raw-observed'
        self.proof={'ok':False,'operation':'semantic-cas-return-to-live','live_context_verified':True,'final_paused':True,
            'identity':{'pid':os.getpid()},'sim_id':'10','household_id':'20','live_snapshot':{'save_guid':'30'},
            'expected_pending_sha256':transaction['transaction_sha256'],'cas_bank_observe_request_id':'a'*32,
            'cas_bank_observation_receipt':{'ok':False,'request_state':'failed','request_id':'a'*32,
              'message':'CAS raw observation or serializer append failed; originals and returned state require inspection: Form bank capacity reached; prior originals retained.'}}

    def test_exact_originals_and_raw_return_are_accepted_for_metadata_only(self):
        before=copy.deepcopy(self.record)
        result=cas_journal_archive.validate_record(self.record,self.proof)
        self.assertEqual(result,self.record['pending']['identity'])
        self.assertEqual(before,self.record)
        self.assertEqual(self.fixture.native_writes,[])

    def test_closed_archival_never_spoofs_or_requires_old_pid_as_current_runtime(self):
        old=os.getpid()+100
        record=copy.deepcopy(self.record);proof=copy.deepcopy(self.proof)
        old_identity=dict(record['pending']['identity'],runtime_pid=old)
        record['pending']['identity']=old_identity;record['pending']['runtime_pid']=old
        record['pending']['original_owners']['identity']=old_identity
        transaction=record['cas_transaction'];transaction['identity']=old_identity
        transaction['journal']['identity']=old_identity
        transaction['journal']['original_owners']=copy.deepcopy(record['pending']['original_owners'])
        transaction['journal']['raw_return']['identity']=old_identity
        transaction['journal']['raw_return_sha256']=primitive.digest(transaction['journal']['raw_return'])
        transaction['checkpoint_sha256']=primitive.digest(record['pending'])
        transaction['journal']['pending_sha256']=transaction['checkpoint_sha256']
        transaction['transaction_sha256']=primitive.digest({name:transaction[name] for name in
            ('transaction_id','identity','checkpoint_sha256','record_guard_sha256','hair_checkpoint_sha256')})
        proof['identity']['pid']=old;proof['expected_pending_sha256']=transaction['transaction_sha256']
        self.assertEqual(cas_journal_archive.validate_record(record,proof),old_identity)
        with self.assertRaisesRegex(ValueError,'this runtime'):primitive._identity(old_identity)

    def test_no_planned_attempted_or_partial_native_write_can_be_archived(self):
        mutations=[lambda t:t['journal'].update(native_write_attempted=True),
            lambda t:t['journal'].update(native_write_possible=True),
            lambda t:t['journal'].update(plan={'desired':'anything'}),
            lambda t:t.update(phase='applying'),lambda t:t.update(metadata_commit={'committed':True}),
            lambda t:t['journal'].update(bank_committed=True),lambda t:t['journal'].update(automatic_replay_allowed=True)]
        for mutate in mutations:
            record=copy.deepcopy(self.record);mutate(record['cas_transaction'])
            with self.assertRaises(ValueError):cas_journal_archive.validate_record(record,self.proof)

    def test_changed_owner_bank_checkpoint_raw_return_or_terminal_receipt_refuse(self):
        for kind in ('bank','original','return','identity','terminal'):
            record=copy.deepcopy(self.record);proof=copy.deepcopy(self.proof)
            if kind=='bank':record['bank']['2']['physique']['value']='new edit'
            elif kind=='original':record['pending']['original_owners']['stored']['2']['physique']['value']='changed'
            elif kind=='return':record['cas_transaction']['journal']['raw_return']['stored']['2']['physique']['value']='changed'
            elif kind=='identity':proof['identity']['pid']+=1
            else:proof['cas_bank_observation_receipt']['request_state']='running'
            with self.subTest(kind=kind),self.assertRaises(ValueError):cas_journal_archive.validate_record(record,proof)


if __name__=='__main__':unittest.main()
