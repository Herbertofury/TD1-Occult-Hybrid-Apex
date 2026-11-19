"""Fresh-process archive fixtures reset their whole test-only receiver registry."""
import threading
import unittest
import test_cas_bank_transaction as receiver_fixtures
import test_cas_crash_archive as crash
import test_cas_frontdoor_archive as frontdoor
import test_schema2_metadata_abandon as schema2
from apex_core import cas_bank_transaction as receiver


class ArchiveReceiverFixtureIsolationTests(unittest.TestCase):
    def test_each_fresh_process_fixture_cleans_the_index_and_runtime_loss_still_refuses(self):
        cases=(
            (crash.ClosedCrashArchiveTests,'test_exact_closed_crash_archives_metadata_with_originals_and_all_banks_intact'),
            (frontdoor.FrontdoorArchiveTests,'test_atomic_archival_preserves_bank_originals_save_and_all_other_records'),
            (schema2.Schema2SourceArchiveTests,'test_captured_no_serializer_seven_owner_archive_retains_exact_full_records_and_unknown_wire_bytes'),
        )
        self.addCleanup(receiver_fixtures.reset_receiver_process)
        for kind,name in cases:
            with self.subTest(fixture=kind.__name__):
                prior=receiver_fixtures.CasBankReceiverTests('runTest')
                prior.setUp()
                try:
                    prior.begin()
                    self.assertEqual(len(receiver._RECEIVERS.current),1)
                    receiver._CAPTURED.clear();receiver._ACTIVE.clear()
                    # This is a deliberately broken runtime capability, not a
                    # fresh-process fixture. The permanent guard must refuse.
                    with self.assertRaisesRegex(ValueError,'Receiver index changed'):
                        receiver._RECEIVERS.bind_owner(threading.current_thread().ident)
                    result=unittest.TestResult()
                    kind(name).run(result)
                    self.assertTrue(result.wasSuccessful(),str(result.errors)+str(result.failures))
                    self.assertEqual(result.testsRun,1)
                    self.assertEqual(receiver._CAPTURED,{})
                    self.assertEqual(receiver._ACTIVE,{})
                    self.assertEqual(receiver._RECEIVERS.current,{})
                    self.assertEqual(receiver._RECEIVERS.capacity,256)
                finally:
                    prior.doCleanups()
