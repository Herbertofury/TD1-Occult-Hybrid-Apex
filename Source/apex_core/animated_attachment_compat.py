"""Allow tagged animated wings/tails to share EA's persistent attachment path.

No polling, object creation, form conversion, resource extraction or animation
replacement. The game's original parent/animation/components run once. Only
its single-head reservation is scoped for the reviewed attachment tags.
"""
import functools
import hashlib
import json
import weakref

TAGS = frozenset((1298798044, 4119383130))
# Exact installed 1.128.90 Python contracts, populated from the reviewed code.
PINS = {
    'apply': '97428bb368ee9819c437852ed12d2b404da1de880d4a7bc2868fe1c4dc98cfc8',
    'setter': '8ba64a72930a24acaf9612aad99874ab16b180f61834c3d7befc091d724013e4',
    'unset': '0ec5c50bb9bbffcad92f146c21ec87be70c43e3ca400d528d21b7c96f5853066',
    'head': '393b6d4ce61350ce86e04dead3936a98c2e27df93bcb3ee90e9b0e300d577375',
    'reparent': '80cbad2515045b6456e904643d9c2a980cb5e98643f77397bee52a536a5f8fd7',
}
_STATUS = {'installed': False, 'background_tasks': False}


def status():
    return dict(_STATUS)


def code_hash(code):
    def constant(value):
        if hasattr(value, 'co_code'):
            return {'code': code_hash(value)}
        if isinstance(value, bytes):
            return {'bytes': value.hex()}
        if isinstance(value, tuple):
            return [constant(x) for x in value]
        if value is None or type(value) in (str, int, float, bool):
            return value
        raise ValueError('Unreviewed attachment code constant.')
    data = dict(code=code.co_code.hex(), names=list(code.co_names), variables=list(code.co_varnames),
                args=code.co_argcount, kwonly=code.co_kwonlyargcount, flags=code.co_flags,
                freevars=list(code.co_freevars), cellvars=list(code.co_cellvars),
                constants=[constant(x) for x in code.co_consts])
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True).encode('ascii')).hexdigest()


def _reviewed(function, expected):
    seen = set()
    for _ in range(16):
        if not callable(function) or id(function) in seen:
            return False
        seen.add(id(function))
        code = getattr(function, '__code__', None)
        if code is not None and code_hash(code) == expected:
            return True
        function = getattr(function, '__wrapped__', None)
    return False


def _tagged(obj):
    getter = getattr(obj, 'get_tags', None)
    if not callable(getter):
        return False
    try:
        return bool(TAGS.intersection(getter()))
    except (AttributeError, TypeError, RuntimeError):
        return False  # Unknown tag providers retain their original operation.


def _points(reference, obj):
    return isinstance(reference, weakref.ReferenceType) and reference() is obj


def _restore(parent, obj, previous):
    current = parent.current_object_set_as_head
    if current is not None and not _points(current, obj):
        return  # A different mod's explicit new head must not be overwritten.
    if _points(previous, obj) and getattr(obj, 'parent', None) is not parent:
        previous = None  # Never restore a reference to the just-removed object.
    parent.current_object_set_as_head = previous


def bind(set_class, unset_class, object_class, component_class, component_type, parent_lookup, pins=None):
    """Prepare every hook before publishing; wrap other known wrappers once."""
    pins = PINS if pins is None else pins
    apply = set_class.apply
    if getattr(apply, '_apex_animated_attachment', False):
        return True
    setter_descriptor = vars(set_class).get('set_head_object')
    head_property = vars(object_class).get('is_set_as_head')
    if not isinstance(setter_descriptor, classmethod) or not isinstance(head_property, property):
        return False
    setter, unset, reparent = setter_descriptor.__func__, unset_class.apply, component_class._reparent_object
    functions = dict(apply=apply, setter=setter, unset=unset, head=head_property.fget, reparent=reparent)
    if set(pins) != set(functions) or any(not _reviewed(fn, pins[key]) for key, fn in functions.items()):
        return False

    def eligible(obj, parent):
        return parent is not None and getattr(parent, 'is_sim', False) is True and _tagged(obj)

    @functools.wraps(apply)
    def apply_tagged(self, obj, parent):
        if not eligible(obj, parent):
            return apply(self, obj, parent)
        previous = parent.current_object_set_as_head
        parent.current_object_set_as_head = None
        try:
            return apply(self, obj, parent)
        finally:
            _restore(parent, obj, previous)

    @functools.wraps(setter)
    def set_tagged(cls, parent, obj, bone_hash):
        if not eligible(obj, parent):
            return setter(cls, parent, obj, bone_hash)
        previous = parent.current_object_set_as_head
        try:
            return setter(cls, parent, obj, bone_hash)
        finally:
            _restore(parent, obj, previous)

    @functools.wraps(unset)
    def unset_tagged(self, obj, parent):
        if not eligible(obj, parent) or getattr(obj, 'parent', None) is not parent:
            return unset(self, obj, parent)
        previous = parent.current_object_set_as_head
        parent.current_object_set_as_head = weakref.ref(obj)
        try:
            return unset(self, obj, parent)
        finally:
            _restore(parent, obj, previous)

    @functools.wraps(head_property.fget)
    def is_tagged_head(obj):
        native = head_property.fget(obj)
        if native or not _tagged(obj):
            return native
        parent = getattr(obj, 'parent', None)
        if not eligible(obj, parent) or not obj.has_component(component_type):
            return native
        component = obj.get_component(component_type)
        return getattr(component, '_parent_sim_info_id', None) == parent.sim_info.id

    @functools.wraps(reparent)
    def reparent_tagged(self):
        obj = self.owner
        if not _tagged(obj):
            return reparent(self)
        parent = parent_lookup(self)
        previous = parent.current_object_set_as_head if parent is not None else None
        try:
            return reparent(self)
        finally:
            # EA's failed reparent cleanup clears the single global reference.
            # Preserve a still-attached unrelated head through that cleanup.
            if (parent is not None and isinstance(previous, weakref.ReferenceType) and
                    previous() is not None and previous() is not obj and
                    getattr(previous(), 'parent', None) is parent and
                    parent.current_object_set_as_head is None):
                parent.current_object_set_as_head = previous

    apply_tagged._apex_animated_attachment = True
    changes = ((set_class, 'apply', apply_tagged),
               (set_class, 'set_head_object', classmethod(set_tagged)),
               (unset_class, 'apply', unset_tagged),
               (object_class, 'is_set_as_head', property(is_tagged_head, head_property.fset, head_property.fdel, head_property.__doc__)),
               (component_class, '_reparent_object', reparent_tagged))
    installed = []
    try:
        for owner, name, value in changes:
            previous = vars(owner)[name]
            setattr(owner, name, value)
            installed.append((owner, name, previous))
    except Exception:
        for owner, name, previous in reversed(installed):
            setattr(owner, name, previous)
        raise
    return True


def install():
    """Explicit bootstrap only; importing this module changes nothing."""
    from objects.parenting_utils import SetAsHead, UnsetAsHead
    from objects.game_object import GameObject
    from objects.components.parent_to_sim_head_component import ParentToSimHeadComponent
    from objects.components.types import PARENT_TO_SIM_HEAD_COMPONENT
    from objects import ALL_HIDDEN_REASONS
    import services

    def parent_lookup(component):
        sim = services.sim_info_manager().get(component._parent_sim_info_id)
        return None if sim is None else sim.get_sim_instance(allow_hidden_flags=ALL_HIDDEN_REASONS)

    installed = bind(SetAsHead, UnsetAsHead, GameObject, ParentToSimHeadComponent,
                     PARENT_TO_SIM_HEAD_COMPONENT, parent_lookup)
    _STATUS.update(installed=installed, background_tasks=False, native_animation_preserved=True,
                   resource_files_modified=False, appearance_fields_written=False)
    return dict(_STATUS)
