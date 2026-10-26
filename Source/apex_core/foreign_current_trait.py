"""Keep another occult's current-trait cleanup from changing the active form.

EA's SimInfoWithOccultTracker.remove_trait requests Human for every removed
current-occult trait, even if a different form is active. Native trait removal
and trait-effect updates still execute once. Only that unrelated synchronous
Human request is suppressed; explicit switches and membership removals remain
native. No appearance, availability, pending value or bank is written here.
"""
import threading

_SCOPES = threading.local()


def _foreign(tracker, sim, trait):
    forms = getattr(tracker, '_sim_info_map', None)
    current = getattr(sim, 'current_occult_types', None)
    if (not isinstance(forms, dict) or len(forms) < 3 or current not in forms or
            getattr(tracker, '_sim_info', None) is not sim or any(owner is sim for owner in forms.values())):
        return None
    tuning = getattr(tracker, 'OCCULT_DATA', {})
    if any(getattr(data, 'occult_trait', None) is trait for data in tuning.values()):
        return None  # A membership removal always retains its native behavior.
    matched = [kind for kind, data in tuning.items()
               if trait is not None and getattr(data, 'current_occult_trait', None) is trait]
    if len(matched) != 1 or matched[0] == current or matched[0] not in forms:
        return None
    return (tracker, sim, current, matched[0], forms, forms[current], forms[matched[0]])


def install(tracker):
    """Install idempotently on actual Python tracker/Sim methods."""
    sim = getattr(tracker, '_sim_info', None)
    tracker_class, sim_class = type(tracker), type(sim)
    switch = getattr(tracker_class, 'switch_to_occult_type', None)
    remove = getattr(sim_class, 'remove_trait', None)
    if not callable(switch) or not callable(remove):
        return False
    if not getattr(switch, '_apex_foreign_current_trait_guard', False):
        def guarded_switch(self, target, *args, **kwargs):
            scopes = getattr(_SCOPES, 'stack', ())
            if scopes and int(target) == 1:
                selected, owner, current, foreign, forms, active_owner, foreign_owner = scopes[-1]
                if (self is selected and self._sim_info is owner and owner.current_occult_types == current and
                        self._sim_info_map is forms and forms.get(current) is active_owner and
                        forms.get(foreign) is foreign_owner):
                    previous = getattr(self, '_apex_foreign_current_trait_cleanup', {})
                    self._apex_foreign_current_trait_cleanup = {
                        'active_form': int(current), 'removed_current_trait_form': int(foreign),
                        'unrelated_human_switch_suppressed': True,
                        'count': min(int(previous.get('count', 0)) + 1, 1 << 31),
                        'native_trait_removal_preserved': True, 'appearance_written': False}
                    return None  # The native public switch's return contract.
            return switch(self, target, *args, **kwargs)
        guarded_switch._apex_foreign_current_trait_guard = True
        guarded_switch._apex_original = switch
        tracker_class.switch_to_occult_type = guarded_switch
    if not getattr(remove, '_apex_foreign_current_trait_guard', False):
        def guarded_remove(self, trait, *args, **kwargs):
            selected = getattr(self, 'occult_tracker', None)
            context = None if selected is None else _foreign(selected, self, trait)
            if context is None:
                return remove(self, trait, *args, **kwargs)
            scopes = getattr(_SCOPES, 'stack', None)
            if scopes is None:
                scopes = _SCOPES.stack = []
            scopes.append(context)
            try:
                return remove(self, trait, *args, **kwargs)  # Exactly once.
            finally:
                if not scopes or scopes[-1] is not context:
                    raise ValueError('Foreign current-trait removal scope changed; no replay authorized.')
                scopes.pop()
        guarded_remove._apex_foreign_current_trait_guard = True
        guarded_remove._apex_original = remove
        sim_class.remove_trait = guarded_remove
    return True
