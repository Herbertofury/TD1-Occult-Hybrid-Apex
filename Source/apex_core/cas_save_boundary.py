"""Protect actual saves without using a bank transaction as a global UI lock.

The inspected game's _save_game_gen first calls get_save_lock_tooltip and
returns FAILED_SAVE_LOCKED before starting any serialization when non-None.
Use that existing failure path and the matching UI predicate. Internal CAS
Sim serialization stays native; no appearance is restored or edit inferred.
The one inspected native save generator also captures household sidecars at
save time. No timer, periodic scan or swallowed native exception is added.
"""
import hashlib
import json
import os
from pathlib import Path
import threading

from . import cas_bank_transaction as bank
from .overlay_loader import _unlinked

MAX_BANK = 48 * 1024 * 1024
_READ_INDEX = None
_CONTRACT = {
    'is_save_locked': ('8bd090ba573ef92a49809650864640cc7e39ff3282a4a6a1440cfdc98c88e45e',
                       'a862376bc569a4afdce54a66d474d1f3c1085b843f845b0e760334b36f257a8b'),
    'get_save_lock_tooltip': ('7d64177cbaa5d29a752b6bfb02d148d1042e545a852457f84dbb6013b3e4e077',
                              '53b375308425465b60a9a351aa4bdfc6a18f3f412fd52d2add1030af55f52c9d'),
    '_save_game_gen': ('48d92df75480e21299b4660faa9709ebc3abe1a7b47bc564ef3bba6e840c4093',
                       '7be0a3eb40ca9a888ae7f0aa44d7babf6543a5faecd3fb29ed2c61fa4be5d8ee'),
    '_send_lock_save_message': ('1e2503ec7773f47981ab14d41e1ab09cfb3d337dd44079b7608f3ac64f532e5a',
                                '5b08ff8db9dda7d4d1ca7aa9ba6ebfc66a3b6e443b24bf87eb27c9016eea024f'),
    '_send_unlock_save_message': ('f79c77363b2e0b8c58b4b3f6339aa47a26c0d119d033b0f34d040bbd6f3c3357',
                                  'd4ec64e73f522f73a996453c6c4be14387fc6b722914a4454790fb356e0f1f03')}
_TEXT = ('Apex could not finish automatic appearance preservation for this save. '
         'Originals and edited forms remain retained; the save was not started.')


def _shape(function):
    code = getattr(function, '__code__', None)
    if code is None:
        raise ValueError('Native save admission method has no inspectable Python contract.')
    metadata = dict(args=code.co_argcount, kwonly=code.co_kwonlyargcount,
        flags=code.co_flags, varnames=code.co_varnames, names=code.co_names,
        constants=code.co_consts, freevars=code.co_freevars, cellvars=code.co_cellvars,
        posonly=getattr(code, 'co_posonlyargcount', 0))
    raw = json.dumps(metadata, ensure_ascii=True, allow_nan=False,
                     sort_keys=True, separators=(',', ':')).encode('ascii')
    return hashlib.sha256(code.co_code).hexdigest(), hashlib.sha256(raw).hexdigest()


def _id(value):
    return (isinstance(value, str) and value.isascii() and value.isdecimal() and
            0 < len(value) <= 20 and str(int(value)) == value and 0 < int(value) < 1 << 64)


def _nonfinite(_value):
    raise ValueError('Nonfinite retained form-bank JSON.')


def _stamp(path):
    stat = path.stat()
    return (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino)


def remember_read(path, data, file_hash, stamp):
    """Retain only lock decisions from a complete, stable bank-reader result.

    The bank reader/writer already paid for full JSON validation and hashing.
    Never repeat that work for the first interaction-menu save-lock test. This
    compact index owns no mutable bank records and grants no appearance writes.
    Admission still checks the path, current save, writer lease and file stamp.
    """
    global _READ_INDEX
    previous = _READ_INDEX
    _READ_INDEX = None
    try:
        if (not isinstance(file_hash, str) or len(file_hash) != 64 or
                any(c not in '0123456789abcdef' for c in file_hash) or
                not isinstance(data, dict) or type(data.get('schema')) is not int or data['schema'] != 1 or
                not isinstance(data.get('records'), dict) or len(data['records']) > 20000 or
                not isinstance(stamp, tuple) or len(stamp) != 4 or not 0 < stamp[0] <= MAX_BANK):
            return False
        # This SHA comes from the bank reader's complete, strictly parsed bytes,
        # not from mtime or a caller's modified mapping. Identical whole-file
        # content has identical lock decisions; refresh only its observed stamp.
        # Validator replacement invalidates reuse, including diagnostic patches.
        validator = (bank._blocked, bank._completed, bank._completed_uncached,
                     bank.appearance.fingerprint, bank.primitive.digest,
                     bank._native_context_envelope, bank._verify_context_final)
        if (isinstance(previous, dict) and previous.get('path') == str(path) and
                previous.get('bank_sha256') == file_hash and previous.get('validator') == validator):
            _READ_INDEX = dict(previous, stamp=stamp)
            return True
        decisions = {}
        hair_enabled = set()
        for owner_key, record in data['records'].items():
            parts = owner_key.split(':') if isinstance(owner_key, str) else []
            if len(parts) != 2 or not all(_id(value) for value in parts) or not isinstance(record, dict):
                return False
            pending = decisions.setdefault(parts[0], [])
            if bank._blocked(record, owner_key):
                pending.append(parts[1])
            policy = record.get('hair_policy', {})
            if isinstance(policy, dict) and policy.get('enabled') is True:
                hair_enabled.add(owner_key)
        _READ_INDEX = dict(path=str(path), stamp=stamp, bank_sha256=file_hash, validator=validator,
            hair_enabled=frozenset(hair_enabled),
            by_save_guid={guid: tuple(sorted(pending, key=int)) for guid, pending in decisions.items()})
        return True
    except Exception:
        # This optimization is optional. A malformed/unindexable document
        # follows admission's existing full read and fail-closed validation.
        _READ_INDEX = None
        return False


def hair_policy_enabled(backend, sim):
    """Read only the opted-in bit from the current stable bank-read index.

    This grants no repair authority. The enabled path still performs its fresh
    idle, runtime and full wardrobe checks. No bank payload is cached here.
    """
    from . import form_bank
    path, key = form_bank.context(backend, sim)
    path = _unlinked(path)
    with bank._LOCK:
        if bank._lease_path(path).exists() or not path.exists():
            return False
        before = _stamp(path)
        index = _READ_INDEX
        if not (isinstance(index, dict) and index['path'] == str(path) and index['stamp'] == before):
            form_bank.load(path)  # Its validated stable read publishes a fresh compact index.
            index = _READ_INDEX
        if (not isinstance(index, dict) or index['path'] != str(path) or
                index['stamp'] != before or _stamp(path) != before):
            return False
        return key in index.get('hair_enabled', ())


def admission(backend):
    """Read all current-save records, including unloaded/old-runtime owners."""
    result = {'locked': True, 'pending_sim_ids': [], 'appearance_written': False,
              'save_file_written': False, 'automatic_restore_performed': False}
    cache_key = None
    try:
        if threading.current_thread().ident != backend._APEX_GAME_THREAD_IDENT:
            raise ValueError('Save admission must be observed on the canonical game thread.')
        guid = str(backend.services.get_persistence_service().get_save_slot_proto_guid())
        if not _id(guid):raise ValueError('The current native save identity is unavailable.')
        unresolved=getattr(backend,'_APEX_CAS_AUTO_SETTLEMENT',{})
        if (isinstance(unresolved,dict) and unresolved.get('unresolved') is True and unresolved.get('save_guid')==guid):
            result.update(reason='automatic-household-preservation-unresolved',save_guid=guid,
                pending_sim_ids=list(unresolved.get('members',[])))
            return result
        path = _unlinked(Path(backend._data_directory()) / 'form_bank.json')
        with bank._LOCK:
            if bank._lease_path(path).exists():
                raise ValueError('A retained form-bank writer is unresolved.')
            if not path.exists():
                from . import native_cas_engine
                scope=native_cas_engine._LAYOUT_SCOPE
                if (isinstance(scope,dict) and scope.get('pid')==os.getpid() and
                        scope.get('load_identity',{}).get('save_guid')==guid and scope.get('epochs')):
                    result.update(reason='captured-cas-bank-missing',save_guid=guid,pending_sim_ids=sorted(scope['epochs'],key=int))
                    return result
                result.update(locked=False, reason='no-retained-form-bank')
                return result
            if not path.is_file() or not 0 < path.stat().st_size <= MAX_BANK:
                raise ValueError('Retained form bank is absent, empty or exceeds its bound.')
            before = _stamp(path)
            cache_key = (str(path), guid, before)
            cached = getattr(backend, '_APEX_CAS_SAVE_ADMISSION_CACHE', None)
            if isinstance(cached, dict) and cached.get('key') == cache_key:
                result = dict(cached['result'])
                result['pending_sim_ids'] = list(result['pending_sim_ids'])
                return result
            index = _READ_INDEX
            if isinstance(index, dict) and index['path'] == str(path) and index['stamp'] == before:
                pending = list(index['by_save_guid'].get(guid, ()))
                result.update(pending_sim_ids=pending, bank_sha256=index['bank_sha256'], save_guid=guid,
                    locked=bool(pending), reason='retained-cas-review-required' if pending else 'retained-owners-idle')
                return result
            with path.open('rb') as stream:
                raw = stream.read(MAX_BANK + 1)
            if len(raw) > MAX_BANK or before != _stamp(path):
                raise ValueError('Retained form bank changed during its complete read or exceeds its bound.')
            data = json.loads(raw.decode('utf-8'), object_pairs_hook=bank._pairs, parse_constant=_nonfinite)
            if (not isinstance(data, dict) or type(data.get('schema')) is not int or data['schema'] != 1 or
                    not isinstance(data.get('records'), dict) or len(data['records']) > 20000):
                raise ValueError('Retained form-bank ownership schema is unsupported.')
            result['bank_sha256'] = hashlib.sha256(raw).hexdigest()
            if not data['records']:
                result.update(locked=False, reason='no-retained-owner-records')
                return result
            result['save_guid'] = guid
            for owner_key, record in data['records'].items():
                parts = owner_key.split(':') if isinstance(owner_key, str) else []
                if len(parts) != 2 or not all(_id(value) for value in parts) or not isinstance(record, dict):
                    raise ValueError('Retained owner identity or record is malformed.')
                if parts[0] == guid and bank._blocked(record, owner_key):
                    result['pending_sim_ids'].append(parts[1])
            result['pending_sim_ids'].sort(key=int)
            result.update(locked=bool(result['pending_sim_ids']),
                          reason='retained-cas-review-required' if result['pending_sim_ids'] else 'retained-owners-idle')
            return result
    except Exception as error:
        result.update(locked=True, reason='retained-cas-authority-unavailable', error=str(error)[:2048])
        return result
    finally:
        backend._APEX_CAS_SAVE_ADMISSION = result
        if cache_key is not None and result.get('reason') != 'retained-cas-authority-unavailable':
            cached_result = dict(result)
            cached_result['pending_sim_ids'] = list(result['pending_sim_ids'])
            backend._APEX_CAS_SAVE_ADMISSION_CACHE = {'key': cache_key, 'result': cached_result}


def install(backend, service_type=None, reason_factory=None):
    """Install only the inspected native admission contract, before future saves."""
    if threading.current_thread().ident != backend._APEX_GAME_THREAD_IDENT:
        raise ValueError('Save admission installation requires the canonical game thread.')
    service = backend.services.get_persistence_service()
    cls = type(service) if service_type is None else service_type
    locked, tooltip = getattr(cls, 'is_save_locked', None), getattr(cls, 'get_save_lock_tooltip', None)
    generator = getattr(cls, '_save_game_gen', None)
    installed = (getattr(locked, '_apex_cas_save_boundary', None) is backend and
                 getattr(tooltip, '_apex_cas_save_boundary', None) is backend and
                 getattr(generator, '_apex_cas_save_boundary', None) is backend)
    candidates = {'is_save_locked': getattr(locked, '_apex_original', locked) if installed else locked,
                  'get_save_lock_tooltip': getattr(tooltip, '_apex_original', tooltip) if installed else tooltip,
                  '_save_game_gen': getattr(generator, '_apex_original', generator) if installed else generator,
                  '_send_lock_save_message': getattr(cls, '_send_lock_save_message', None),
                  '_send_unlock_save_message': getattr(cls, '_send_unlock_save_message', None)}
    for name, method in candidates.items():
        if not callable(method) or _shape(method) != _CONTRACT[name]:
            backend._APEX_CAS_SAVE_BOUNDARY_READY = False
            raise ValueError('Native save admission contract changed; protected CAS entry is unavailable: ' + name)
    if installed:
        backend._APEX_CAS_SAVE_BOUNDARY_READY = True
        return True
    if reason_factory is None:
        from sims4.localization import LocalizationHelperTuning
        reason_factory = LocalizationHelperTuning.get_raw_text
    reason = reason_factory(_TEXT)
    if reason is None:
        raise ValueError('Native localized CAS save-lock reason is unavailable.')
    def is_save_locked(self):
        # EA also asks this for harmless navigation such as Gallery browsing.
        # The actual save generator performs Apex's preservation admission.
        return locked(self)
    def get_save_lock_tooltip(self):
        return tooltip(self)
    for method, original in ((is_save_locked, locked), (get_save_lock_tooltip, tooltip)):
        method._apex_cas_save_boundary = backend
        method._apex_original = original
    from . import named_save_boundary
    wrapped_generator = named_save_boundary.wrap(backend, candidates['_save_game_gen'], reason)
    cls.is_save_locked, cls.get_save_lock_tooltip, cls._save_game_gen = is_save_locked, get_save_lock_tooltip, wrapped_generator
    backend._APEX_CAS_SAVE_BOUNDARY_READY = True
    # This hook is installed during zone initialization, before player menus
    # need its predicate. A fresh process has no bank-reader index yet: pay
    # the one complete read here, not inside the first interaction test.
    # Unavailable/corrupt authority remains locked; later revisions still
    # invalidate both caches and retain the ordinary full validation path.
    admission(backend)
    return True


def require_installed(backend):
    """Unsupported save protection must refuse a new native CAS entry."""
    return install(backend)


def refresh_ui(backend):
    """Publish EA's own lock state after appearance preservation.

    Existing EA locks win. No lock holder is removed, no save is requested and
    native appearance completion must never be replayed if UI delivery fails.
    """
    require_installed(backend)
    service = backend.services.get_persistence_service()
    locked = bool(service.is_save_locked())
    if locked:
        service._send_lock_save_message(service.get_save_lock_tooltip)
    else:
        service._send_unlock_save_message()
    return {'ok': True, 'native_save_ui_locked': locked, 'save_requested': False}


def probe(backend, exercise_locked_generator=False):
    """Observe the real native early refusal; never attempt an unlocked save."""
    require_installed(backend)
    state = admission(backend)
    service = backend.services.get_persistence_service()
    reason = service.get_save_lock_tooltip()
    result = dict(ok=True, installed=True, admission=state,
        native_is_save_locked=bool(service.is_save_locked()), native_tooltip_present=reason is not None,
        generator_exercised=False, native_locked_generator_verified=False,
        appearance_written=False, save_file_written=False)
    if not exercise_locked_generator:
        return result
    from . import native_cas_engine
    if native_cas_engine._LAYOUT_SCOPE is not None:
        raise ValueError('A retained native CAS scope may settle automatically; a diagnostic must not submit its save.')
    if reason is None:reason=getattr(type(service)._save_game_gen,'_apex_preservation_reason',None)
    if state['locked'] is not True or not state['pending_sim_ids'] or reason is None:
        raise ValueError('The native generator probe requires actual pending CAS owners and a current native lock reason; no save submitted.')
    original = getattr(type(service)._save_game_gen, '_apex_original', type(service)._save_game_gen)
    if _shape(original) != _CONTRACT['_save_game_gen']:
        raise ValueError('Native save generator contract changed; no probe submitted.')
    # This exact inspected function returns its lock tuple before examining
    # timeline/save data. No target file, save buffer or serialization exists.
    expected = original.__globals__['SaveGameResult'].FAILED_SAVE_LOCKED
    generator = service._save_game_gen(None, None, False)
    result['generator_exercised'] = True
    try:
        try:
            next(generator)
        except StopIteration as stopped:
            returned = stopped.value
        else:
            raise ValueError('Locked native generator unexpectedly yielded; no further generator work is permitted.')
    finally:
        generator.close()
    if not isinstance(returned, tuple) or len(returned) != 2 or returned[0] != expected or returned[1] is not reason:
        raise ValueError('Native locked-save result did not match its exact expected code and reason.')
    result.update(native_locked_generator_verified=True, native_result_code=str(returned[0]))
    return result
