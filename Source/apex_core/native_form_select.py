"""One explicit native Human selection without replaying appearance sidecars.

This disposable test operation retains current native evidence before any
switch, creates only an explicitly requested tuned Witch owner without random
generation, and preserves ambiguous ownership instead of retrying or restoring.
"""
import threading
from . import form_bank, form_bank_seal as seal, form_appearance as appearance


def select(backend, sim, sim_id, argument):
    fields = {'form_flags', 'expected_current_form_flags', 'save_guid', 'household_id', 'ensure_witch_owner'}
    from .test_driver import _save_id
    if (not isinstance(argument, dict) or set(argument) != fields or
            type(argument['form_flags']) is not int or argument['form_flags'] != 1 or
            type(argument['expected_current_form_flags']) is not int or argument['expected_current_form_flags'] not in seal.FORMS or
            type(argument['ensure_witch_owner']) is not bool or
            not all(_save_id(argument[name]) for name in ('save_guid', 'household_id')) or
            sim is None or str(sim.id) != str(sim_id) or not _save_id(str(sim_id))):
        raise ValueError('Use exact Sim/household/save identities, expected current native form, Human target and typed Witch-owner option.')
    if (type(getattr(backend, '_APEX_GAME_THREAD_IDENT', None)) is not int or
            backend._APEX_GAME_THREAD_IDENT != threading.current_thread().ident):
        raise ValueError('Native form selection requires the game owner thread.')
    identity, _profile, path, key, _seals = seal._identity(backend, sim)
    seal._idle(); form_bank.assert_idle(backend, sim)
    target = dict(argument, sim_id=str(sim.id))
    before_context = seal._live(backend, sim, target, paused=True)
    current = backend._get_current_flags(sim)
    if type(current) is not int or current != argument['expected_current_form_flags']:
        raise ValueError('Current native form changed; no selection submitted.')
    kinds = seal._members(backend, sim)
    tracker = sim.occult_tracker
    forms = backend._form_map(tracker)
    human_kind, witch_kind = backend._coerce_flags(1), kinds[16]
    human = forms.get(human_kind) if isinstance(forms, dict) else None
    if (human is None or not _save_id(str(human.id)) or not callable(getattr(tracker, 'switch_to_occult_type', None)) or
            not callable(getattr(tracker, 'set_pending_occult_type', None)) or not hasattr(tracker, '_pending_occult_type')):
        raise ValueError('An existing native Human owner and native switch contract are required.')
    create_witch = argument['ensure_witch_owner'] and witch_kind not in forms
    if create_witch and (witch_kind not in getattr(tracker, 'OCCULT_DATA', {}) or
                         not callable(getattr(tracker, '_generate_sim_info', None))):
        raise ValueError('Native Witch owner construction is unsupported by current tuning.')
    data = form_bank.load(path)
    record = data['records'].setdefault(key, {'bank': {}, 'history': []})
    if record.get('pending') or record.get('switch_pending') or not isinstance(record.get('native_selection_history', []), list):
        raise ValueError('Native selection ownership is retained or its bounded history is full.')
    pending = {'state': 'native-only-intent', 'runtime_pid': identity['pid'], 'argument': dict(argument),
               'native_before': seal._native(backend, sim), 'before_context': before_context,
               'bank_sha256': seal._hash(record['bank']), 'native_switch_attempted': False,
               'witch_creation_attempted': False, 'bank_appearance_restored': False}
    record['switch_pending'] = pending
    form_bank.save(path, data)  # Suppresses hair callbacks and precedes native writes.
    try:
        if current != 1:
            pending['native_switch_attempted'] = True
            form_bank.save(path, data)
            # No direct flag setter, scripted bank switch or fallback is used.
            tracker.switch_to_occult_type(human_kind)
        if backend._get_current_flags(sim) != 1:
            raise ValueError('Native Human selection has not converged; do not replay.')
        tracker.set_pending_occult_type(None)
        if tracker._pending_occult_type is not None or backend._get_current_flags(sim) != 1:
            raise ValueError('Immediate native Human selection left a deferred transform; do not replay.')
        pending['native_deferred_transform_cleared'] = True
        if create_witch:
            pending['witch_creation_attempted'] = True
            form_bank.save(path, data)
            owner = tracker._generate_sim_info(witch_kind, generate_new=False)
            fresh = backend._form_map(tracker)
            if owner is None or fresh.get(witch_kind) is not owner or not _save_id(str(owner.id)):
                raise ValueError('Native tuned Witch owner construction was not verified; do not replay.')
            appearance.evidence(backend, owner)  # Validate every readable appearance field/outfit.
        after_context = seal._live(backend, sim, target, paused=True)
        if any(after_context.get(name) != before_context.get(name) for name in ('client_id', 'zone_id', 'save_slot')):
            raise ValueError('Native client/zone/save context changed during selection.')
        seal._members(backend, sim)
        pending['native_after'] = seal._native(backend, sim)
        if pending['native_after']['active_form'] != 1 or seal._hash(record['bank']) != pending['bank_sha256']:
            raise ValueError('Human selection or historical bank preservation failed readback.')
        pending.update(state='native-only-completed', after_context=after_context,
                       witch_owner_created=bool(create_witch))
        record.setdefault('native_selection_history', []).append(pending)
        record['switch_pending'] = None
        form_bank.save(path, data)
    except Exception as error:
        pending.update(state='native-only-unresolved', error=str(error)[:2048], retry_safe=False)
        record['switch_pending'] = pending
        try:
            pending['native_after_failure'] = seal._native(backend, sim)
        except Exception as observation_error:
            pending['native_observation_error'] = str(observation_error)[:2048]
        try:
            form_bank.save(path, data)
        except Exception as evidence_error:
            tracker._apex_native_selection_evidence_error = str(evidence_error)[:2048]
        tracker._apex_native_selection_failure = pending
        raise
    return {'ok': True, 'outcome': 'native-human-selected', 'form_flags': 1,
            'native_switch_attempted': pending['native_switch_attempted'],
            'witch_owner_created': bool(create_witch), 'native_before': pending['native_before'],
            'native_after': pending['native_after'], 'before_context': before_context, 'after_context': after_context,
            'bank_sha256': pending['bank_sha256'], 'bank_appearances_changed': False,
            'bank_appearance_restored': False, 'save_file_written': False,
            'save_reload_verified': False, 'unpaused_visual_verification_required': True}
