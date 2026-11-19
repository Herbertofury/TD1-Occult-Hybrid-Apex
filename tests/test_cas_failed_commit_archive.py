"""Closed archival preserves failed writes without permitting replay or recovery."""
import copy
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import cas_failed_commit_archive as archive
import test_cas_bank_transaction as fixtures


class FailedCommitArchiveTests(unittest.TestCase):
    def setUp(self):
        f=fixtures.CasBankReceiverTests(methodName='runTest');f.setUp()
        self.addCleanup(f.doCleanups)
        f.begin();f.edit(2);f.observe();f.prepare([(2,'restore-original')])
        f.backend._restore_siminfo_payload=lambda *a:None
        with self.assertRaises(ValueError):f.commit()
        self.record=f.record()
        self.identity=self.record['pending']['identity']
        self.failure={'ok':False,'request_state':'failed','request_id':'a'*32,'submitted_request_id':'a'*32,
            'message':'CAS native reconcile or bank commit failed; originals and returned state require inspection: '+
                self.record['cas_transaction']['journal']['error']}

    def test_exact_failed_readback_is_metadata_only_and_preserves_complete_raw_plan(self):
        before=copy.deepcopy(self.record)
        transaction=archive.validate_record(self.record,self.failure,self.identity)
        self.assertEqual(transaction['phase'],'recovery-required')
        self.assertTrue(transaction['journal']['native_write_attempted'])
        self.assertFalse(transaction['journal']['bank_committed'])
        self.assertEqual(self.record,before)

    def test_native_context_envelope_is_validated_and_preserved_for_closed_failure(self):
        transaction = self.record['cas_transaction']
        context = {kind: {'available': 127, 'current': int(kind)}
                   for kind in self.record['pending']['original_owners']['stored']}
        context['active'] = {'available': 127, 'current': 64}
        transaction['native_occult_context'] = context
        transaction['native_occult_context_sha256'] = fixtures.primitive.digest(context)
        envelope = {name: transaction[name] for name in ('transaction_id', 'identity',
            'checkpoint_sha256', 'record_guard_sha256', 'hair_checkpoint_sha256')}
        transaction['transaction_sha256'] = fixtures.primitive.digest(
            archive.receiver._native_context_envelope(transaction, envelope))
        before = copy.deepcopy(self.record)
        self.assertEqual(archive.validate_record(self.record, self.failure, self.identity), transaction)
        self.assertEqual(self.record, before)
        transaction['native_occult_context']['8']['available'] = 126
        with self.assertRaises(ValueError):
            archive.validate_record(self.record, self.failure, self.identity)

    def test_pending_unknown_committed_or_modified_history_never_authorizes_archival(self):
        for kind in ('pending','unknown-write','bank-commit','raw','plan','bank','identity','terminal','message'):
            record,failure=copy.deepcopy(self.record),copy.deepcopy(self.failure)
            j=record['cas_transaction']['journal']
            if kind=='pending':record['cas_transaction']['phase']='applying'
            elif kind=='unknown-write':j['native_write_attempted']=None
            elif kind=='bank-commit':j['bank_commit_attempted']=True
            elif kind=='raw':j['raw_return']['stored']['2']['physique']['value']='changed'
            elif kind=='plan':j['plan']['desired']['2']['physique']['value']='changed'
            elif kind=='bank':record['bank']['2']['physique']['value']='changed'
            elif kind=='identity':record['pending']['identity']=dict(self.identity,runtime_pid=os.getpid()+1)
            elif kind=='terminal':failure['request_state']='running'
            else:failure['message']='pretend success'
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                archive.validate_record(record,failure,self.identity)
