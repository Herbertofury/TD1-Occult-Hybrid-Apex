"""Bounded, read-only transition tracing for the marked disposable profile.

Only known Python method boundaries are observed around one explicit native
selection, never in production profiles or the frame loop. Native values are
not read from a profiler callback: native setters can still hold their locks
at those callbacks. No trait, appearance, selection or pending value is written.
"""
import os
import sys
import time
import uuid


def state(tracker):
    sim = tracker._sim_info
    row = {'current': int(sim.current_occult_types), 'available': int(sim.occult_types),
           'pending': None if tracker._pending_occult_type is None else int(tracker._pending_occult_type),
           'form_available': bool(getattr(tracker, '_occult_form_available', False))}
    base = getattr(sim, '_base', None)
    if base is not None:
        row['native_current'] = int(base.current_occult_types)
        row['native_available'] = int(base.occult_types)
    return row


class Selection:
    def __init__(self, tracker, target):
        self.tracker = tracker
        self.wrappers = []
        self.last = None
        self.sequence = 0
        self.events = []
        self.started = time.perf_counter()
        self.record = {'id': uuid.uuid4().hex, 'target': int(target),
                       'sim_id': str(tracker._sim_info.id), 'events': self.events,
                       'read_only': True, 'native_calls_repeated': False}

    def observe(self, event, frame=None):
        try:
            observed = state(self.tracker)
            name = None if frame is None else frame.f_code.co_name
            relevant = name in ('switch_to_occult_type', '_switch_to_occult_type_internal',
                               '_update_occult_traits', 'add_trait', 'remove_trait',
                               'on_trait_added', 'on_trait_removed', 'set_pending_occult_type')
            if frame is not None and not relevant and observed == self.last:
                return
            self.sequence += 1
            row = {'sequence': self.sequence, 'event': event, 'state': observed}
            if frame is not None:
                row.update(function=name, file=os.path.basename(frame.f_code.co_filename),
                           line=frame.f_lineno)
                trait = frame.f_locals.get('trait')
                trait_id = getattr(trait, 'guid64', None)
                if isinstance(trait_id, int) and not isinstance(trait_id, bool):
                    row['trait_id'] = str(trait_id)
            self.last = observed
            self.events.append(row)
            if len(self.events) > 256:
                del self.events[128]  # Retain the beginning and newest tail.
                self.record['truncated'] = True
        except Exception as error:
            self.record['observation_error'] = str(error)[:512]

    def wrap(self, owner, name):
        cls = type(owner)
        original = getattr(cls, name, None)
        if not callable(original) or not hasattr(original, '__code__'):
            self.record.setdefault('untraced_methods', []).append(name)
            return
        local = cls.__dict__.get(name)
        trace = self
        def boundary(receiver, *args, **kwargs):
            selected = receiver is owner
            if selected:
                trace.observe('before-' + name)
                if name in ('add_trait', 'remove_trait') and args:
                    trait_id = getattr(args[0], 'guid64', None)
                    if isinstance(trait_id, int) and trace.events:
                        trace.events[-1]['trait_id'] = str(trait_id)
            try:
                return original(receiver, *args, **kwargs)
            finally:
                if selected:
                    trace.observe('after-' + name)
        setattr(cls, name, boundary)
        self.wrappers.append((cls, name, local, boundary))

    def __enter__(self):
        self.observe('before-public-switch')
        self.record['profiler_preserved'] = sys.getprofile() is not None
        try:
            for name in ('_switch_to_occult_type_internal', '_update_occult_traits', 'set_pending_occult_type'):
                self.wrap(self.tracker, name)
            for name in ('add_trait', 'remove_trait'):
                self.wrap(self.tracker._sim_info, name)
        except Exception:
            self.release()
            raise
        self.tracker._apex_explicit_switch_trace = self.record
        return self

    def release(self):
        for cls, name, local, boundary in reversed(self.wrappers):
            if cls.__dict__.get(name) is not boundary:
                self.record['wrapper_changed'] = name
                continue  # Never overwrite a concurrent mod's replacement.
            if local is None:
                delattr(cls, name)
            else:
                setattr(cls, name, local)
        self.wrappers = []

    def __exit__(self, kind, error, traceback):
        self.release()
        self.observe('after-public-switch')
        self.record['elapsed_ms'] = round((time.perf_counter() - self.started) * 1000, 3)
        self.record['observed_events'] = self.sequence
        if error is not None:
            self.record['error'] = str(error)[:2048]
        return False
