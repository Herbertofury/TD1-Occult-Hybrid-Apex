from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core.command_queue import CommandQueue


class QueueTests(unittest.TestCase):
    def test_expired_and_timed_out_mutations_never_execute(self):
        now = [0.0]
        queue = CommandQueue(clock=lambda: now[0])
        first = queue.submit({'action': 'mutate'}, ttl=1)['request_id']
        now[0] = 2.0
        calls = []
        queue.drain(lambda value: calls.append(value))
        self.assertEqual(queue.status(first)['state'], 'cancelled')
        second = queue.submit({'action': 'mutate'})['request_id']
        self.assertEqual(queue.wait(second, 0)['state'], 'cancelled')
        queue.drain(lambda value: calls.append(value))
        self.assertEqual(calls, [])

    def test_capacity_rejects_new_command_without_dropping_accepted_work(self):
        queue = CommandQueue(capacity=1)
        first = queue.submit({'action': 'first'})['request_id']
        self.assertEqual(queue.submit({'action': 'second'})['state'], 'rejected')
        calls = []
        queue.drain(lambda value: (calls.append(value) or {'ok': True}))
        self.assertEqual(calls, [{'action': 'first'}])
        self.assertEqual(queue.status(first)['state'], 'completed')

    def test_other_thread_cannot_execute_read_or_write(self):
        queue = CommandQueue()
        queue.submit({'action': 'status'})
        errors, calls = [], []
        def wrong_owner():
            try:
                queue.drain(lambda value: calls.append(value))
            except RuntimeError as error:
                errors.append(str(error))
        thread = threading.Thread(target=wrong_owner)
        thread.start()
        thread.join()
        self.assertEqual(len(errors), 1)
        self.assertEqual(calls, [])

    def test_started_timeout_has_queryable_outcome_and_is_not_requeued(self):
        queue = CommandQueue()
        request_id = queue.submit({'action': 'mutate'})['request_id']
        observations = []
        def execute(value):
            worker = threading.Thread(target=lambda: observations.append(queue.wait(request_id, 0)))
            worker.start()
            worker.join()
            return {'ok': True, 'value': 42}
        queue.drain(execute)
        self.assertEqual(observations[0]['state'], 'running')
        self.assertFalse(observations[0]['ok'])
        self.assertEqual(queue.status(request_id)['result']['value'], 42)

    def test_duplicate_identity_and_bounded_completed_records(self):
        queue = CommandQueue(completed_limit=2)
        for index in range(20):
            row = queue.submit({'action': 'status'}, request_id=str(index))
            self.assertEqual(queue.submit({'action': 'status'}, request_id=str(index))['request_id'], row['request_id'])
            with self.assertRaises(ValueError):
                queue.submit({'action': 'different'}, request_id=str(index))
            queue.drain(lambda value: {'ok': True})
        self.assertEqual(queue.metrics()['retained'], 2)

    def test_drain_budget_and_shutdown_preserve_explicit_outcomes(self):
        queue = CommandQueue()
        identifiers = [queue.submit({'action': str(index)})['request_id'] for index in range(8)]
        self.assertEqual(queue.drain(lambda value: {'ok': True}, max_commands=2), 2)
        queue.shutdown()
        self.assertEqual(queue.metrics()['pending'], 0)
        self.assertEqual(queue.status(identifiers[-1])['state'], 'cancelled')
        self.assertEqual(queue.submit({'action': 'new'})['state'], 'rejected')

    def test_one_millisecond_budget_yields_without_losing_or_replaying_work(self):
        now = [0.0]
        queue = CommandQueue(clock=lambda: now[0])
        ids = [queue.submit({'action': str(i)})['request_id'] for i in range(3)]
        calls = []
        def execute(value):
            calls.append(value['action'])
            now[0] += .0006
            return {'ok': True}
        self.assertEqual(queue.drain(execute), 2)
        self.assertEqual(calls, ['0', '1'])
        self.assertEqual(queue.status(ids[2])['state'], 'pending')
        self.assertEqual(queue.drain(execute), 1)
        self.assertEqual(calls, ['0', '1', '2'])
        self.assertEqual(queue.metrics()['over_budget'], 0)

    def test_nonpreemptible_overrun_is_measured_instead_of_reported_as_one_ms(self):
        now = [0.0]
        queue = CommandQueue(clock=lambda: now[0])
        ids = [queue.submit({'action': str(i)})['request_id'] for i in range(2)]
        def execute(value):
            now[0] += .025
            return {'ok': True}
        self.assertEqual(queue.drain(execute), 1)
        self.assertEqual(queue.status(ids[0])['state'], 'completed')
        self.assertEqual(queue.status(ids[1])['state'], 'pending')
        metrics = queue.metrics()
        self.assertEqual(metrics['executed'], 1)
        self.assertEqual(metrics['over_budget'], 1)
        self.assertEqual(metrics['command_max_ms'], 25)
        self.assertEqual(metrics['drain_max_ms'], 25)


if __name__ == '__main__':
    unittest.main()
