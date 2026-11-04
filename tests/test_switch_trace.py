"""Observe the native callback that changes a form without changing behavior."""
from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core.switch_trace import Selection


class SwitchTraceTests(unittest.TestCase):
    def tracker(self):
        class Tracker:
            def __init__(self):
                self._sim_info = Obj(id=42, current_occult_types=1, occult_types=3)
                self._pending_occult_type = 4
                self._occult_form_available = True
                self.calls = []
            def _switch_to_occult_type_internal(self, target):
                self.calls.append('internal')
                self._sim_info.current_occult_types = target
            def _update_occult_traits(self):
                self.calls.append('traits')
                self._sim_info.current_occult_types = 1
            def switch_to_occult_type(self, target):
                self._switch_to_occult_type_internal(target)
                self._update_occult_traits()
        return Tracker()

    def test_identifies_trait_reversion_without_replaying_or_changing_pending(self):
        tracker = self.tracker()
        with Selection(tracker, 2) as trace:
            tracker.switch_to_occult_type(2)
        self.assertEqual(tracker.calls, ['internal', 'traits'])
        self.assertEqual(tracker._pending_occult_type, 4)
        self.assertEqual(tracker._sim_info.current_occult_types, 1)
        returns = {row['event']: row['state']['current'] for row in trace.events}
        self.assertEqual(returns['after-_switch_to_occult_type_internal'], 2)
        self.assertEqual(returns['after-_update_occult_traits'], 1)
        self.assertIsNone(sys.getprofile())

    def test_native_exception_survives_and_profiler_is_released(self):
        tracker = self.tracker()
        with self.assertRaisesRegex(ValueError, 'native failure'):
            with Selection(tracker, 2) as trace:
                raise ValueError('native failure')
        self.assertEqual(trace.record['error'], 'native failure')
        self.assertIsNone(sys.getprofile())

    def test_existing_profiler_remains_installed(self):
        tracker = self.tracker()
        prior = sys.getprofile()
        def existing(*args): pass
        try:
            sys.setprofile(existing)
            with Selection(tracker, 2) as trace:
                tracker.switch_to_occult_type(2)
            self.assertIs(sys.getprofile(), existing)
            self.assertTrue(trace.record['profiler_preserved'])
        finally:
            sys.setprofile(prior)

    def test_trace_is_bounded_but_retains_final_state(self):
        tracker = self.tracker()
        with Selection(tracker, 2) as trace:
            for i in range(400):
                tracker._sim_info.current_occult_types = 1 if i % 2 else 2
                trace.observe('probe')
        self.assertEqual(len(trace.events), 256)
        self.assertTrue(trace.record['truncated'])
        self.assertEqual(trace.events[-1]['event'], 'after-public-switch')


if __name__ == '__main__': unittest.main()
