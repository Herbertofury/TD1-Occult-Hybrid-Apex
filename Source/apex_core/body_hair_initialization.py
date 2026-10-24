"""Keep a native growth refresh from reapplying an unchanged hair level.

EA's refresh sets each growth statistic to the active base's current level.
Its callback queues change_bodytype_level even at that same level, which can
replace a chosen CAS swatch with the preferred growth swatch after loading.
Only that synchronous refresh or a checkpointed native-load request can be
suppressed. Fresh appearance edits, later growth, shaving and nonhybrid Sims
stay native. No prior bank or saved-profile metadata supplies authority.
"""
import inspect
import math
import threading

_REFRESHES = threading.local()
BODY_TYPES = (78, 79, 80, 81)


def _requests(value):
    if not isinstance(value, dict) or len(value) > 32:
        return None
    if any(not isinstance(k, int) or isinstance(k, bool) or not 0 <= int(k) < 256 or
           not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)
           for k, v in value.items()):
        return None
    return dict(value)


def checkpoint_load(tracker):
    """Hold only requests already queued before native load readiness."""
    if getattr(tracker, '_apex_body_hair_load_requests', None) is not None:
        return
    saved = getattr(tracker, '_apex_native_load_owners', None)
    if not isinstance(saved, tuple) or len(saved) != 3:
        return
    forms, sim, expected = saved
    native = getattr(sim, 'body_type_level_tracker', None)
    queued = _requests(getattr(native, '_pending_requests', None))
    kind = getattr(sim, 'current_occult_types', None)
    if (native is None or getattr(native, '_sim_info', None) is not sim or not queued or
            tracker._sim_info_map is not forms or tracker._sim_info is not sim or kind not in expected):
        return
    initial = {k: v for k, v in queued.items() if k in BODY_TYPES}
    if initial:
        versions = getattr(native, '_apex_body_hair_request_versions', {})
        tracker._apex_body_hair_load_requests = (native, forms, sim, int(kind), dict(initial),
                                                {k: versions.get(k, 0) for k in initial})


def _dispatch(original, self):
    sim = getattr(self, '_sim_info', None)
    tracker = getattr(sim, 'occult_tracker', None)
    held = getattr(tracker, '_apex_body_hair_load_requests', None)
    if not isinstance(held, tuple) or len(held) != 6 or held[0] is not self:
        return original(self)
    # Consume before calling native code. A failed dispatch is never repeated.
    tracker._apex_body_hair_load_requests = False
    native, forms, sim, kind, initial, initial_versions = held
    queued = _requests(getattr(self, '_pending_requests', None))
    proof = {'form_flags': kind, 'initial_requests': {str(k): v for k, v in initial.items()},
             'queued_requests': None if queued is None else {str(k): v for k, v in queued.items()},
             'suppressed': [], 'native_call_count': 0, 'load_appearance_verified': False,
             'native_owner_verified': False, 'bank_read': False, 'save_written': False}
    tracker._apex_body_hair_load_dispatch = proof
    if queued is None:
        proof['native_call_count'] = 1
        return original(self)
    try:
        from . import form_appearance as appearance
        from .hybrid_persistence import _appearance_backend
        backend = _appearance_backend()
        saved_forms, saved_sim, expected = tracker._apex_native_load_owners
        bound = (self._sim_info is sim and tracker._sim_info is sim and tracker._sim_info_map is forms and
                 saved_forms is forms and saved_sim is sim and int(sim.current_occult_types) == kind and
                 set(forms) == set(expected) and all(forms[k] is owner for k, (owner, _) in expected.items()))
        proof['native_owner_verified'] = bool(bound and backend is not None)
        proof['load_appearance_verified'] = bool(bound and backend is not None and
            appearance.evidence(backend, sim) == appearance.fingerprint(expected[kind][1]))
        if proof['native_owner_verified']:
            proof['before'] = appearance.fingerprint(appearance.packed(backend, sim))
            retained = dict(queued)
            versions = getattr(self, '_apex_body_hair_request_versions', {})
            for body_type, level in initial.items():
                if (body_type in retained and retained[body_type] == level and
                        versions.get(body_type, 0) == initial_versions[body_type]):
                    # These exact requests predate restoration of the immutable
                    # saved owner. The saved CAS appearance is newer than that
                    # provisional native-load projection, regardless of level.
                    del retained[body_type]
                    proof['suppressed'].append(int(body_type))
            if proof['suppressed']:
                self._pending_requests = retained
    except Exception as error:
        proof['authority_error'] = str(error)[:1024]
        self._pending_requests = queued  # An unreadable authority keeps native behavior.
        proof['suppressed'] = []
    proof['native_call_count'] = 1
    result = original(self)
    if proof['native_owner_verified']:
        proof['after'] = appearance.evidence(backend, sim)
        proof['appearance_unchanged'] = proof['before'] == proof['after']
    return result


def install(cls=None):
    if cls is None:
        from sims.body_type_level.body_type_level_tracker import BodyTypeLevelTracker
        cls = BodyTypeLevelTracker
    refresh = getattr(cls, 'refresh_hair_growth_commodities', None)
    request = getattr(cls, 'request_client_level_change', None)
    if not callable(refresh) or not callable(request):
        return False
    if getattr(refresh, '_apex_body_hair_refresh_guard', False):
        return True
    try:
        inspect.signature(refresh).bind(None, None)
        inspect.signature(request).bind(None, 78, 0)
    except (TypeError, ValueError):
        return False

    def guarded_refresh(self, *args, **kwargs):
        sim = getattr(self, '_sim_info', None)
        tracker = getattr(sim, 'occult_tracker', None)
        forms = getattr(tracker, '_sim_info_map', None)
        kind = getattr(sim, 'current_occult_types', None)
        if (not isinstance(forms, dict) or len(forms) < 3 or kind not in forms or
                getattr(tracker, '_sim_info', None) is not sim):
            return refresh(self, *args, **kwargs)
        prior = getattr(_REFRESHES, 'owners', ())
        if len(prior) >= 32:
            return refresh(self, *args, **kwargs)
        _REFRESHES.owners = prior + ((self, sim, tracker, forms, kind),)
        try:
            return refresh(self, *args, **kwargs)
        finally:
            _REFRESHES.owners = prior

    def guarded_request(self, body_type, new_level):
        rows = getattr(_REFRESHES, 'owners', ())
        held = rows[-1] if rows else None
        if held is not None and held[0] is self and body_type in BODY_TYPES:
            _, sim, tracker, forms, kind = held
            if (self._sim_info is sim and tracker._sim_info is sim and
                    tracker._sim_info_map is forms and sim.current_occult_types == kind and kind in forms):
                try:
                    current = sim._base.get_current_growth_level(body_type)
                except Exception:
                    current = None  # An unreadable level never authorizes suppression.
                if current is not None and new_level == current:
                    events = list(getattr(tracker, '_apex_body_hair_refresh_retention', ()))
                    events.append({'form_flags': int(kind), 'body_type': int(body_type),
                                   'same_native_level': True, 'native_caspart_write_skipped': True})
                    tracker._apex_body_hair_refresh_retention = tuple(events[-32:])
                    return None
        # A later genuine request must stay native even if it uses the same
        # numeric level as the old load queue. Preserve per-slot provenance.
        if body_type in BODY_TYPES:
            versions = dict(getattr(self, '_apex_body_hair_request_versions', {}))
            versions[body_type] = versions.get(body_type, 0) + 1
            self._apex_body_hair_request_versions = versions
        return request(self, body_type, new_level)

    guarded_refresh._apex_body_hair_refresh_guard = True
    guarded_refresh._apex_original = refresh
    guarded_request._apex_original = request
    cls.refresh_hair_growth_commodities = guarded_refresh
    cls.request_client_level_change = guarded_request
    dispatch = getattr(cls, '_send_body_type_level_update', None)
    if callable(dispatch):
        try:
            inspect.signature(dispatch).bind(None)
        except (TypeError, ValueError):
            pass
        else:
            def guarded_dispatch(self):
                return _dispatch(dispatch, self)
            guarded_dispatch._apex_original = dispatch
            guarded_dispatch._apex_body_hair_load_dispatch_guard = True
            cls._send_body_type_level_update = guarded_dispatch
    return True
