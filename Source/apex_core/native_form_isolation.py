"""Prevent EA's shared-appearance copy between distinct existing hybrid forms.

The inspected game method copies physique and generates merged hidden outfits
before a form switch/save. Existing forms have independent appearances: only
the native gender-option trait copy is shared. Creation of a new wrapper and
ordinary one-occult pairs keep the original method. No bank, snapshot, timer,
appearance setter or post-mutation restoration is used by this patch.
"""
import inspect


def matches(tracker, destination, destination_kind, source, source_kind):
    forms = getattr(tracker, '_sim_info_map', None)
    sim = getattr(tracker, '_sim_info', None)
    if (not isinstance(forms, dict) or not 3 <= len(forms) <= 32 or sim is None or
            destination_kind == source_kind or destination_kind not in forms or source_kind not in forms or
            forms[destination_kind] is not destination or
            source is not sim and forms[source_kind] is not source):
        return False
    # Require the actual native, distinct wrapper owners. A generated wrapper
    # is not registered until AFTER EA's initialization copy, so stays native.
    owners = list(forms.values()) + [sim]
    bases = [getattr(owner, '_base', None) for owner in owners]
    try:
        valid_kinds = all(not isinstance(kind, bool) and 0 < int(kind) < 1 << 32 and
                          not int(kind) & (int(kind)-1) for kind in forms)
    except (TypeError, ValueError):
        return False
    return (all(base is not None for base in bases) and valid_kinds and
            len({id(base) for base in bases}) == len(bases))


def installed(method):
    seen = set()
    while callable(method) and id(method) not in seen:
        if getattr(method, '_apex_native_form_isolation', False):
            return True
        seen.add(id(method))
        method = getattr(method, '_apex_original', None)
    return False


def install(tracker):
    cls = type(tracker)
    original = getattr(cls, '_copy_shared_attributes', None)
    copy_traits = getattr(cls, '_copy_trait_ids', None)
    if not callable(original) or not callable(copy_traits):
        return False
    if installed(original):
        return True
    try:
        inspect.signature(original).bind(None, None, 2, None, 4)
        inspect.signature(copy_traits).bind(None, None)
    except (TypeError, ValueError):
        return False

    def isolated(self, destination, destination_kind, source, source_kind):
        if not matches(self, destination, destination_kind, source, source_kind):
            return original(self, destination, destination_kind, source, source_kind)
        copy_traits(destination, source)
        prior = getattr(self, '_apex_native_form_isolation_receipt', {})
        self._apex_native_form_isolation_receipt = {
            'source': int(source_kind), 'target': int(destination_kind),
            'count': min(int(prior.get('count', 0)) + 1, 1 << 31),
            'destructive_copy_skipped': True, 'native_trait_copy_called': True,
            'appearance_restore_performed': False, 'bank_read': False}
        return None

    isolated._apex_native_form_isolation = True
    isolated._apex_original = original
    cls._copy_shared_attributes = isolated
    return True
