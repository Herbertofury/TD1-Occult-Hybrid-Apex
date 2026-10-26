"""Finalize an existing hybrid's Live presentation after native trait updates.

EA refreshes the actor inside its internal switch, before current-form trait
cleanup. A Fairy's inertial back-carry owner can also outlive that switch.
Keep native gameplay and the permanent appearance guard; finish only this
reviewed EA wing owner, then resend the final selected form through native APIs.
No bank access, polling, actor reset, appearance copy or generic part removal.
"""
import functools
import threading

_SCOPES = threading.local()


def _eligible(tracker, target):
    forms = getattr(tracker, '_sim_info_map', None)
    sim = getattr(tracker, '_sim_info', None)
    if (not isinstance(forms, dict) or not 3 <= len(forms) <= 32 or sim is None or
            target not in forms or sim.current_occult_types not in forms):
        return None
    owners = list(forms.values()) + [sim]
    bases = [getattr(owner, '_base', None) for owner in owners]
    if any(base is None for base in bases) or len({id(base) for base in bases}) != len(bases):
        return None
    return sim, forms, dict(forms)


def finalize(sim, target, completed_interaction=None):
    actor = sim.get_sim_instance()
    if actor is None:
        return {'actor_present': False, 'appearance_written': False}
    if actor.sim_info is not sim:
        raise ValueError('Live presentation actor belongs to a different SimInfo.')
    running = tuple(actor.si_state.sis_actor_gen()) if actor.si_state is not None else ()
    if len(running) > 64:
        raise ValueError('Live presentation interaction inventory exceeds its bound.')
    # Conceal Fairy Form already owns EA's animated exit-carry sequence. Let it
    # finish. Other transformations never run that sequence themselves.
    native_exit = any(int(si.get_interaction_type().guid64) == 425311 and not si.is_finishing for si in running)
    # A form trait is applied from an animation event before the rest of its
    # native loot list/outcome has finished. Cancelling carry here can interrupt
    # that sequence (including Vampire's manual-Dark-Form trait). Finalize the
    # carry at the real completed-interaction boundary instead.
    transforming = any(si is not completed_interaction and int(si.get_interaction_type().guid64) in
                       (425308, 425311, 152200, 152201) for si in running)
    posture = actor.posture_state
    back = None if posture is None else posture.back
    proxy = None if back is None else back.target
    cancelled = []
    if int(target) != 64 and not native_exit and not transforming and proxy is not None and int(proxy.definition.id) == 460952:
        holders = [si for si in running if int(si.get_interaction_type().guid64) == 426489 and
                   si.target is proxy and not si.is_finishing]
        if len(holders) > 1:
            raise ValueError('EA Fairy wing owner is ambiguous; no generic carry cancellation.')
        if holders:
            from interactions.interaction_finisher import FinishingType
            if holders[0].cancel(FinishingType.CONDITIONAL_EXIT,
                                 cancel_reason_msg='Apex: selected form no longer owns the EA Fairy wing proxy'):
                cancelled.append(426489)
    # This is the normal modifier evaluation, after the native public switch
    # finishes trait changes and the permanent internal guard retains owners.
    # Keep legitimate appearance modifiers; never clear their state wholesale.
    sim.appearance_tracker.evaluate_appearance_modifiers()
    sim.resend_current_occult_types()
    sim.resend_physical_attributes()
    sim.resend_current_outfit()
    sim.force_resend_suntan_data()
    return {'actor_present': True, 'target': int(target), 'native_wing_exit_in_progress': native_exit,
            'native_transform_in_progress': transforming,
            'cancelled_ea_wing_owners': cancelled, 'appearance_written': False,
            'gameplay_switch_repeated': False, 'native_animation_cleanup_preserved': True,
            'pixels_verified': False}


def install_completion(interaction_class=None):
    if interaction_class is None:
        from interactions.base.super_interaction import SuperInteraction
        interaction_class = SuperInteraction
    original = interaction_class._exited_pipeline
    if getattr(original, '_apex_live_form_completion', False):
        return True

    @functools.wraps(original)
    def exited(self, *args, **kwargs):
        kind = int(self.get_interaction_type().guid64)
        actor = self.sim if kind in (425308, 425311, 152200, 152201) else None
        result = original(self, *args, **kwargs)  # All native loot/liability/transition cleanup first.
        if actor is not None:
            tracker = None
            try:
                # Native cleanup or another mod can retire this actor. That
                # completed lifecycle must not fail on a later visual refresh.
                sim = actor.sim_info
                tracker = None if sim is None else sim.occult_tracker
                if tracker is not None and _eligible(tracker, sim.current_occult_types) is not None:
                    receipt = finalize(sim, sim.current_occult_types, completed_interaction=self)
                    receipt['completed_native_interaction'] = kind
                    tracker._apex_live_form_presentation = receipt
            except Exception as error:
                if tracker is not None:
                    tracker._apex_live_form_presentation = {'error': str(error)[:2048],
                        'completed_native_interaction': kind, 'retry_safe': False, 'pixels_verified': False}
        return result

    exited._apex_live_form_completion = True
    exited._apex_original = original
    interaction_class._exited_pipeline = exited
    return True


def install(tracker):
    cls = type(tracker)
    original = getattr(cls, 'switch_to_occult_type', None)
    if not callable(original):
        return False
    try:
        install_completion()
    except ImportError:
        pass  # Offline tracker fixtures have no installed game interaction class.
    method, seen = original, set()
    while callable(method) and id(method) not in seen:
        if getattr(method, '_apex_live_form_presentation', False):
            return True
        seen.add(id(method));method = getattr(method, '_apex_original', None)

    @functools.wraps(original)
    def switched(self, target, *args, **kwargs):
        outer = getattr(_SCOPES, 'trackers', ())
        scope = None if self in outer else _eligible(self, target)
        source = None if scope is None else scope[0].current_occult_types
        trace = None
        if getattr(self, '_apex_trace_live_forms', False) is True:
            import traceback
            sim = getattr(self, '_sim_info', None)
            trace = {'source': int(sim.current_occult_types), 'requested': int(target),
                     'callers': [{'function': row.name, 'file': row.filename, 'line': row.lineno}
                                 for row in traceback.extract_stack(limit=12)[:-1]]}
            rows = getattr(self, '_apex_live_form_trace', [])
            rows = list(rows[-63:]) + [trace]
            self._apex_live_form_trace = rows
        _SCOPES.trackers = outer + (self,)
        try:
            result = original(self, target, *args, **kwargs)  # One native call, including its original exceptions.
            if scope is not None and source != target:
                sim, forms, owners = scope
                if (self._sim_info is sim and self._sim_info_map is forms and
                        set(forms) == set(owners) and all(forms[k] is o for k, o in owners.items()) and
                        sim.current_occult_types == target):
                    try:
                        self._apex_live_form_presentation = finalize(sim, target)
                    except Exception as error:
                        # A visual finalization fault must not discard an otherwise
                        # valid Sim or replay its completed native transformation.
                        self._apex_live_form_presentation = {'target': int(target), 'error': str(error)[:2048],
                            'appearance_written': False, 'retry_safe': False, 'pixels_verified': False}
            return result
        finally:
            if trace is not None:
                try:
                    trace['observed_after'] = int(self._sim_info.current_occult_types)
                except Exception as error:
                    trace['observation_error'] = str(error)[:2048]
            _SCOPES.trackers = outer

    switched._apex_live_form_presentation = True
    switched._apex_original = original
    cls.switch_to_occult_type = switched
    return True
