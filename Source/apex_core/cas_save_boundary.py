"""Block native file-save admission while retained CAS owners need review.

The inspected game's _save_game_gen first calls get_save_lock_tooltip and
returns FAILED_SAVE_LOCKED before starting any serialization when non-None.
Use that existing failure path and the matching UI predicate. Internal CAS
Sim serialization stays native; no appearance is restored or edit inferred.
No timer, periodic scan, native serializer exception, or disk write is added.
"""
import hashlib
import json
from pathlib import Path
import threading

from . import cas_bank_transaction as bank
from .overlay_loader import _unlinked

MAX_BANK = 48 * 1024 * 1024
_CONTRACT = {
    'is_save_locked': ('8bd090ba573ef92a49809650864640cc7e39ff3282a4a6a1440cfdc98c88e45e',
                       'a862376bc569a4afdce54a66d474d1f3c1085b843f845b0e760334b36f257a8b'),
    'get_save_lock_tooltip': ('7d64177cbaa5d29a752b6bfb02d148d1042e545a852457f84dbb6013b3e4e077',
                              '53b375308425465b60a9a351aa4bdfc6a18f3f412fd52d2add1030af55f52c9d'),
    '_save_game_gen': ('48d92df75480e21299b4660faa9709ebc3abe1a7b47bc564ef3bba6e840c4093',
                       '7be0a3eb40ca9a888ae7f0aa44d7babf6543a5faecd3fb29ed2c61fa4be5d8ee')}
_TEXT = ('Apex: finish CAS review for every captured Sim before saving. '
         'Keep or restore each changed form, then commit every captured member. '
         'Originals and returned edits remain retained.')


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


def admission(backend):
    """Read all current-save records, including unloaded/old-runtime owners."""
    result = {'locked': True, 'pending_sim_ids': [], 'appearance_written': False,
              'save_file_written': False, 'automatic_restore_performed': False}
    try:
        if threading.current_thread().ident != backend._APEX_GAME_THREAD_IDENT:
            raise ValueError('Save admission must be observed on the canonical game thread.')
        path = _unlinked(Path(backend._data_directory()) / 'form_bank.json')
        with bank._LOCK:
            if bank._lease_path(path).exists():
                raise ValueError('A retained form-bank writer is unresolved.')
            if not path.exists():
                result.update(locked=False, reason='no-retained-form-bank')
                return result
            if not path.is_file() or not 0 < path.stat().st_size <= MAX_BANK:
                raise ValueError('Retained form bank is absent, empty or exceeds its bound.')
            with path.open('rb') as stream:
                raw = stream.read(MAX_BANK + 1)
            if len(raw) > MAX_BANK:
                raise ValueError('Retained form bank exceeds its complete read bound.')
            data = json.loads(raw.decode('utf-8'), object_pairs_hook=bank._pairs, parse_constant=_nonfinite)
            if (not isinstance(data, dict) or type(data.get('schema')) is not int or data['schema'] != 1 or
                    not isinstance(data.get('records'), dict) or len(data['records']) > 20000):
                raise ValueError('Retained form-bank ownership schema is unsupported.')
            result['bank_sha256'] = hashlib.sha256(raw).hexdigest()
            if not data['records']:
                result.update(locked=False, reason='no-retained-owner-records')
                return result
            guid = str(backend.services.get_persistence_service().get_save_slot_proto_guid())
            if not _id(guid):
                raise ValueError('The current native save identity is unavailable.')
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


def install(backend, service_type=None, reason_factory=None):
    """Install only the inspected native admission contract, before future saves."""
    if threading.current_thread().ident != backend._APEX_GAME_THREAD_IDENT:
        raise ValueError('Save admission installation requires the canonical game thread.')
    service = backend.services.get_persistence_service()
    cls = type(service) if service_type is None else service_type
    locked, tooltip = getattr(cls, 'is_save_locked', None), getattr(cls, 'get_save_lock_tooltip', None)
    installed = (getattr(locked, '_apex_cas_save_boundary', None) is backend and
                 getattr(tooltip, '_apex_cas_save_boundary', None) is backend)
    candidates = {'is_save_locked': getattr(locked, '_apex_original', locked) if installed else locked,
                  'get_save_lock_tooltip': getattr(tooltip, '_apex_original', tooltip) if installed else tooltip,
                  '_save_game_gen': getattr(cls, '_save_game_gen', None)}
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
        native = locked(self)
        if native or self is not backend.services.get_persistence_service():
            return native
        return admission(backend)['locked']
    def get_save_lock_tooltip(self):
        native = tooltip(self)
        if native is not None or self is not backend.services.get_persistence_service():
            return native
        return reason if admission(backend)['locked'] else None
    for method, original in ((is_save_locked, locked), (get_save_lock_tooltip, tooltip)):
        method._apex_cas_save_boundary = backend
        method._apex_original = original
    cls.is_save_locked, cls.get_save_lock_tooltip = is_save_locked, get_save_lock_tooltip
    backend._APEX_CAS_SAVE_BOUNDARY_READY = True
    return True


def require_installed(backend):
    """Unsupported save protection must refuse a new native CAS entry."""
    return install(backend)


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
    if state['locked'] is not True or not state['pending_sim_ids'] or reason is None:
        raise ValueError('The native generator probe requires actual pending CAS owners and a current native lock reason; no save submitted.')
    original = type(service)._save_game_gen
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
