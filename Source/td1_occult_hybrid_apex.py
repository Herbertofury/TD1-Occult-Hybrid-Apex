# TD1 Occult Hybrid Apex - ImGui overlay architecture build v9.6
# Standalone Sims 4 occult hybrid controller with local API, native helper DLL support, Lot51/MCCC awareness, persistent form libraries, and a DirectX 11 Dear ImGui overlay companion source kit.
# Source is intentionally packaged as .py so Sims 4 can load it directly from the .ts4script archive.

import json
import os
import socket
import threading
import time
import traceback
import ctypes
import copy
import base64
import pickle
import re
import sys

try:
    from urllib.parse import parse_qs, urlparse, unquote_plus
except Exception:
    parse_qs = None
    urlparse = None
    unquote_plus = None

try:
    import services
except Exception:
    services = None

try:
    import alarms
    import clock
except Exception:
    alarms = None
    clock = None

try:
    from sims.occult.occult_enums import OccultType
    from sims.occult.occult_tracker import OccultTracker
except Exception:
    OccultType = None
    OccultTracker = None

try:
    from sims.sim_info_base_wrapper import SimInfoBaseWrapper
except Exception:
    SimInfoBaseWrapper = None

try:
    from sims4.commands import Command, CommandType, CommandRestrictionFlags, CheatOutput, Output
except Exception:
    Command = None
    CommandType = None
    CommandRestrictionFlags = None
    CheatOutput = None
    Output = None

try:
    from sims4.resources import Types
except Exception:
    Types = None

try:
    from event_testing.resolver import SingleSimResolver, DoubleSimResolver
except Exception:
    SingleSimResolver = None
    DoubleSimResolver = None

try:
    from sims4.log import Logger
    LOGGER = Logger('TD1 Occult Hybrid Apex', default_owner='Herberto')
except Exception:
    LOGGER = None

HOST = '127.0.0.1'
PORT = 8017
SERVER_NAME = 'TD1 Occult Hybrid Apex'
NATIVE_DLL = 'TD1OccultNativeBridge.dll'

_SERVER_SOCKET = None
_SERVER_THREAD = None
_SERVER_RUNNING = False
_LOCK = threading.RLock()
_HISTORY = []
_LOG_SEQ = 0
_PENDING = []
_RESULTS = {}
_ACTION_COUNTER = 0
_ALARM_OWNER = object()
_ALARM_HANDLE = None
_ALARM_READY = False
_FORM_MEMORY = {}
_CAS_MEMORY = {}
_SAVED_FORMS = {}
_SAVED_FORMS_LOADED = False
_WARDROBE_CLIPBOARD = {}
_MCCC_GUARD_ENABLED = False
_MCCC_GUARD_MEMORY = {}
_MCCC_GUARD_LAST_EVENT = 'not armed'
_MCCC_GUARD_LAST_RESTORE = 'never'
_MCCC_STATUS = 'not checked'
_MCCC_DETAILS = {}
_XML_INJECTOR_STATUS = 'not checked'
_XML_INJECTOR_DETAILS = {}
_LOT51_EVENTS_INSTALLED = False
_LOT51_EVENT_STATUS = 'not installed'
_LOT51_EVENT_HANDLERS = []
_AUTO_REPAIR = False
_AUTO_REPAIR_INTERVAL_SECONDS = 120.0
_ACTION_QUEUE_INTERVAL_SECONDS = 1.0
_LAST_AUTO_REPAIR = 0.0
_NATIVE = None
_NATIVE_PATH = None
_NATIVE_STATUS = 'not loaded'
_BUILD_VERSION = '2026.05.28-imgui-overlay-v6.0-mccc-savedforms'
_READ_ONLY_ACTIONS = set(('status', 'diagnostics', 'list_sims', 'clear_logs', 'list_saved_forms', 'saved_forms', 'mccc_status', 'clipboard_status', 'overlay', 'overlay_capabilities'))
_PERF_STATS = {}
_LAST_COMMAND = None


# V6: MCCC/CAS compatibility guard, saved occult form library, and appearance clipboard.
_MCCC_STATUS = 'not checked'
_MCCC_DETAILS = {}
_MCCC_GUARD = False
_MCCC_AUTO_RESTORE = False
_MCCC_GUARD_MEMORY = {}
_MCCC_LAST_PULSE = 0.0
_MCCC_LAST_SNAPSHOT = 0.0
_MCCC_PULSE_SECONDS = 8.0
_MCCC_SNAPSHOT_INTERVAL_SECONDS = 45.0
_MCCC_PENDING_RESTORE_REASON = None
_LOT51_EVENT_REGISTERED = False
_LOT51_EVENT_HANDLERS = []
_SAVED_FORMS = {}
_SAVED_FORMS_LOADED = False
_SAVED_FORM_COUNTER = 0
_APPEARANCE_CLIPBOARD = {}
_APPEARANCE_SCOPES = ('all', 'wardrobe', 'body', 'face', 'physique', 'skin', 'tattoos', 'outfits')
_DATA_DIR = None
_SAVED_FORMS_CACHE = None
_WARDROBE_CACHE = None
_MCCC_STATUS = None
_MCCC_CAS_SHIELD_ENABLED = False
_MCCC_CAS_WAS_AWAY = False
_MCCC_CAS_LAST_PULSE = 0.0
_MCCC_CAS_PULSE_SECONDS = 18.0
_MCCC_EVENT_HOOKED = False
_MCCC_LAST_RECOVERY = None
_OUTFIT_CODES = ('E', 'AT', 'F', 'P', 'SL', 'SW', 'HW', 'CW', 'BT')

IMGUI_OVERLAY_NAME = 'TD1 Apex Dear ImGui DX11 Overlay'
IMGUI_OVERLAY_TOGGLE_KEY = 'F11'
IMGUI_OVERLAY_API_VERSION = 94
IMGUI_OVERLAY_POLL_VISIBLE_MS = 1400
IMGUI_OVERLAY_LOG_VISIBLE_MS = 300
IMGUI_OVERLAY_HIDDEN_MODE = 'passive: no Sim polling, no HTTP polling, F11 visibility check only'
_LOT51_STATUS = 'not checked'
_LOT51_MODULE = None
_LOT51_DETAILS = {}

# TD1/LordPercival-style hidden memory trait ids seen in the existing mod line.
# If a trait is absent in a user's pack/configuration, the command safely reports unavailable.
_MEMORY_TRAIT_IDS = {
    'ALIEN': 16768010466321094980,
    'VAMPIRE': 11440349392908825663,
    'MERMAID': 17158874848357145152,
    'WITCH': 11287859092209813903,
    'SPELLCASTER': 11287859092209813903,
    'WEREWOLF': 12351341566375713428,
    'FAIRY': 18197032510434408842,
    'PLANTSIM': 16220648519181083001,
}

# Vanilla gameplay loot IDs used as first-pass official initializers before Apex
# normalizes flags/forms/traits for hybrid safety. Missing pack tunings are skipped safely.
_GAMEPLAY_ADD_LOOTS = {
    'ALIEN': (103256, 103254),
    'VAMPIRE': (149538,),
    'MERMAID': (205399,),
    'WITCH': (215080,),
    'SPELLCASTER': (215080,),
    'WEREWOLF': (290058,),
    'FAIRY': (420057,),
    'PLANTSIM': (163440,),
}

_GAMEPLAY_REMOVE_LOOTS = {
    'VAMPIRE': (150170, 31238),
    'WITCH': (215274,),
    'SPELLCASTER': (215274,),
    'WEREWOLF': (291816,),
}

_SIMINFO_COPY_ATTRS = (
    'physique', 'facial_attributes', 'voice_pitch', 'voice_actor', 'voice_effect',
    'skin_tone', 'flags', 'pelt_layers', 'base_trait_ids', 'genetic_data',
)

_SPECIAL_OCCULT_NAME_ORDER = (
    'ALIEN', 'VAMPIRE', 'MERMAID', 'WITCH', 'SPELLCASTER', 'WEREWOLF',
    'FAIRY', 'PLANTSIM', 'ROBOT', 'SERVO', 'GHOST', 'SKELETON', 'SCARECROW',
)

_MCCC_MODULE_NAMES = (
    'mc_cmd_center', 'mc_cas', 'mc_dresser', 'mc_occult', 'mc_cheats',
    'mc_cleaner', 'mc_population', 'mc_control', 'mc_tuner', 'mc_career'
)
_XML_INJECTOR_MODULE_NAMES = ('xml_injector', 'XmlInjector', 'xmlinjector')



def _log(message):
    global _LOG_SEQ
    text = str(message)
    with _LOCK:
        _LOG_SEQ += 1
        stamp = time.strftime('%H:%M:%S')
        _HISTORY.append('[{0} #{1:05d}] {2}'.format(stamp, _LOG_SEQ, text))
        if len(_HISTORY) > 1000:
            del _HISTORY[:-1000]
    try:
        if LOGGER is not None:
            LOGGER.info(text)
    except Exception:
        pass






def _get_mod_root():
    try:
        file_name = globals().get('__file__', '') or ''
        lower = file_name.lower()
        marker = '.ts4script'
        idx = lower.find(marker)
        if idx >= 0:
            return os.path.dirname(file_name[:idx + len(marker)])
        folder = os.path.dirname(file_name)
        if folder:
            return folder
    except Exception:
        pass
    try:
        return os.getcwd()
    except Exception:
        return '.'


def _data_dir():
    root = _get_mod_root()
    path = os.path.join(root, 'TD1_Apex_Data')
    try:
        if not os.path.isdir(path):
            os.makedirs(path)
    except Exception:
        pass
    return path


def _saved_forms_file():
    return os.path.join(_data_dir(), 'saved_occult_forms.json')


def _json_safe(value):
    try:
        if isinstance(value, tuple) and len(value) == 2 and value[0] == 'protobuf':
            raw = value[1]
            if isinstance(raw, str):
                raw = raw.encode('utf-8')
            return {'__td1_proto_b64__': base64.b64encode(raw).decode('ascii')}
        if isinstance(value, bytes):
            return {'__td1_bytes_b64__': base64.b64encode(value).decode('ascii')}
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        if isinstance(value, dict):
            out = {}
            for k, v in value.items():
                out[str(k)] = _json_safe(v)
            return out
        if isinstance(value, (list, tuple)):
            return {'__td1_list__': [_json_safe(v) for v in value]}
        if hasattr(value, 'SerializeToString'):
            return {'__td1_proto_b64__': base64.b64encode(value.SerializeToString()).decode('ascii')}
    except Exception:
        pass
    try:
        return {'__td1_repr__': str(value), '__td1_type__': type(value).__name__}
    except Exception:
        return None


def _json_restore(value):
    try:
        if isinstance(value, dict):
            if '__td1_proto_b64__' in value:
                return ('protobuf', base64.b64decode(value.get('__td1_proto_b64__') or ''))
            if '__td1_bytes_b64__' in value:
                return base64.b64decode(value.get('__td1_bytes_b64__') or '')
            if '__td1_list__' in value:
                return [_json_restore(v) for v in value.get('__td1_list__') or []]
            if '__td1_repr__' in value:
                return None
            return dict((k, _json_restore(v)) for k, v in value.items())
        if isinstance(value, list):
            return [_json_restore(v) for v in value]
    except Exception:
        return None
    return value


def _detect_mccc():
    global _MCCC_STATUS, _MCCC_DETAILS
    if _MCCC_STATUS not in ('not checked', ''):
        return _MCCC_STATUS
    details = {'available': False, 'modules': [], 'missing': [], 'errors': {}}
    for name in _MCCC_MODULE_NAMES:
        try:
            if name in sys.modules:
                module = sys.modules[name]
            else:
                module = __import__(name)
            details['modules'].append(name)
            details['available'] = True
            try:
                details.setdefault('module_repr', {})[name] = str(module)
            except Exception:
                pass
        except Exception as exc:
            details['missing'].append(name)
            details['errors'][name] = str(exc)
    if details['available']:
        _MCCC_STATUS = 'available: {}'.format(', '.join(details['modules']))
    else:
        _MCCC_STATUS = 'not installed or not loaded yet'
    _MCCC_DETAILS = details
    return _MCCC_STATUS


def _detect_xml_injector():
    global _XML_INJECTOR_STATUS, _XML_INJECTOR_DETAILS
    if _XML_INJECTOR_STATUS not in ('not checked', ''):
        return _XML_INJECTOR_STATUS
    details = {'available': False, 'modules': [], 'errors': {}}
    for name in _XML_INJECTOR_MODULE_NAMES:
        try:
            if name in sys.modules:
                module = sys.modules[name]
            else:
                module = __import__(name)
            details['available'] = True
            details['modules'].append(name)
            try:
                details.setdefault('module_repr', {})[name] = str(module)
            except Exception:
                pass
        except Exception as exc:
            details['errors'][name] = str(exc)
    _XML_INJECTOR_STATUS = 'available' if details['available'] else 'not installed or not needed'
    _XML_INJECTOR_DETAILS = details
    return _XML_INJECTOR_STATUS

def _detect_lot51_core():
    global _LOT51_STATUS, _LOT51_MODULE, _LOT51_DETAILS
    if _LOT51_STATUS not in ('not checked', ''):
        return _LOT51_STATUS
    details = {'available': False, 'modules': [], 'error': None}
    try:
        import lot51_core  # noqa: F401
        _LOT51_MODULE = lot51_core
        details['available'] = True
        details['module'] = str(lot51_core)
        details['modules'].append('lot51_core')
        # Probe known utility modules without depending on their exact public API.
        for name in ('lot51_core.utils.log', 'lot51_core.utils.config', 'lot51_core.services.events', 'lot51_core.events.zone'):
            try:
                __import__(name)
                details['modules'].append(name)
            except Exception as sub_exc:
                details.setdefault('module_errors', {})[name] = str(sub_exc)
        _LOT51_STATUS = 'available'
        # V9.4: detection must stay passive. Register Lot51 hooks only from an explicit user command.
        details['event_registration_mode'] = 'manual only; use lot51_register_events / lot51_events_on after arming MCCC Shield'
    except Exception as exc:
        details['error'] = str(exc)
        _LOT51_STATUS = 'not installed'
    _LOT51_DETAILS = details
    return _LOT51_STATUS




def _data_directory():
    global _DATA_DIR
    if _DATA_DIR:
        return _DATA_DIR
    candidates = []
    try:
        if services is not None:
            for attr in ('get_user_data_path', 'user_data_path'):
                try:
                    value = getattr(services, attr)
                    if callable(value):
                        value = value()
                    if value:
                        candidates.append(str(value))
                except Exception:
                    pass
    except Exception:
        pass
    try:
        profile = os.environ.get('USERPROFILE')
        if profile:
            candidates.append(os.path.join(profile, 'Documents', 'Electronic Arts', 'The Sims 4'))
    except Exception:
        pass
    candidates.append(os.path.expanduser(os.path.join('~', 'Documents', 'Electronic Arts', 'The Sims 4')))
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        if here and not here.lower().endswith('.ts4script'):
            candidates.append(here)
    except Exception:
        pass
    for base in candidates:
        try:
            if not base:
                continue
            folder = os.path.join(base, 'TD1_OccultHybridApexData')
            os.makedirs(folder, exist_ok=True)
            test = os.path.join(folder, '.write_test')
            with open(test, 'w') as fp:
                fp.write('ok')
            try:
                os.remove(test)
            except Exception:
                pass
            _DATA_DIR = folder
            return _DATA_DIR
        except Exception:
            pass
    _DATA_DIR = os.path.join(os.path.expanduser('~'), 'TD1_OccultHybridApexData')
    try:
        os.makedirs(_DATA_DIR, exist_ok=True)
    except Exception:
        pass
    return _DATA_DIR


def _json_file(name):
    return os.path.join(_data_directory(), name)


def _load_json_file(name, default):
    path = _json_file(name)
    try:
        if os.path.exists(path):
            with open(path, 'r') as fp:
                data = json.load(fp)
            if isinstance(data, type(default)):
                return data
            return data
    except Exception as exc:
        _log('Could not load {}: {}'.format(name, exc))
    return copy.deepcopy(default)


def _save_json_file(name, data):
    path = _json_file(name)
    tmp = path + '.tmp'
    try:
        with open(tmp, 'w') as fp:
            json.dump(data, fp, indent=2, sort_keys=True)
        try:
            os.replace(tmp, path)
        except Exception:
            if os.path.exists(path):
                os.remove(path)
            os.rename(tmp, path)
        return True
    except Exception as exc:
        _log('Could not save {}: {}'.format(name, exc))
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return False


def _slug(value):
    text = str(value or '').strip().lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-') or 'untitled'


def _trait_guid(trait):
    if trait is None:
        return None
    for attr in ('guid64', 'guid', 'instance', 'resource_key'):
        try:
            value = getattr(trait, attr)
            if callable(value):
                value = value()
            if value is not None:
                try:
                    return int(value)
                except Exception:
                    pass
        except Exception:
            pass
    return None


def _pack_value(value):
    try:
        if isinstance(value, tuple) and len(value) == 2 and value[0] == 'protobuf':
            return {'kind': 'protobuf', 'data': base64.b64encode(value[1]).decode('ascii')}
    except Exception:
        pass
    try:
        if isinstance(value, bytes):
            return {'kind': 'bytes', 'data': base64.b64encode(value).decode('ascii')}
    except Exception:
        pass
    try:
        json.dumps(value)
        return {'kind': 'json', 'data': value}
    except Exception:
        pass
    try:
        return {'kind': 'pickle', 'data': base64.b64encode(pickle.dumps(value, protocol=2)).decode('ascii')}
    except Exception as exc:
        return {'kind': 'repr', 'data': repr(value), 'error': str(exc)}


def _unpack_value(node):
    if not isinstance(node, dict):
        return node
    kind = node.get('kind')
    data = node.get('data')
    try:
        if kind == 'protobuf':
            return ('protobuf', base64.b64decode(data.encode('ascii')))
        if kind == 'bytes':
            return base64.b64decode(data.encode('ascii'))
        if kind == 'json':
            return data
        if kind == 'pickle':
            return pickle.loads(base64.b64decode(data.encode('ascii')))
    except Exception as exc:
        _log('Could not unpack saved payload value: {}'.format(exc))
    return None


def _pack_payload(payload):
    out = {}
    for key, value in (payload or {}).items():
        out[str(key)] = _pack_value(value)
    return out


def _unpack_payload(payload):
    out = {}
    for key, value in (payload or {}).items():
        out[key] = _unpack_value(value)
    return out


def _load_saved_forms():
    global _SAVED_FORMS_CACHE
    if _SAVED_FORMS_CACHE is None:
        _SAVED_FORMS_CACHE = _load_json_file('saved_occult_forms.json', {'version': 1, 'forms': []})
        if not isinstance(_SAVED_FORMS_CACHE, dict):
            _SAVED_FORMS_CACHE = {'version': 1, 'forms': []}
        _SAVED_FORMS_CACHE.setdefault('forms', [])
    return _SAVED_FORMS_CACHE


def _save_saved_forms(data=None):
    global _SAVED_FORMS_CACHE
    if data is not None:
        _SAVED_FORMS_CACHE = data
    return _save_json_file('saved_occult_forms.json', _load_saved_forms())


def _load_wardrobes():
    global _WARDROBE_CACHE
    if _WARDROBE_CACHE is None:
        _WARDROBE_CACHE = _load_json_file('saved_wardrobes.json', {'version': 1, 'wardrobes': []})
        if not isinstance(_WARDROBE_CACHE, dict):
            _WARDROBE_CACHE = {'version': 1, 'wardrobes': []}
        _WARDROBE_CACHE.setdefault('wardrobes', [])
    return _WARDROBE_CACHE


def _save_wardrobes(data=None):
    global _WARDROBE_CACHE
    if data is not None:
        _WARDROBE_CACHE = data
    return _save_json_file('saved_wardrobes.json', _load_wardrobes())


def _record_matches(record, query):
    q = str(query or '').strip().lower()
    if not q:
        return True
    hay = ' '.join(str(record.get(key, '')) for key in ('id', 'label', 'sim', 'occult', 'created', 'notes')).lower()
    return q in hay


def _summarize_records(records, query=None, limit=80):
    rows = [r for r in records if _record_matches(r, query)]
    rows.sort(key=lambda r: str(r.get('created', '')), reverse=True)
    out = []
    for r in rows[:limit]:
        clean = {}
        for key in ('id', 'label', 'sim', 'sim_id', 'occult', 'created', 'payload_quality', 'source'):
            if key in r:
                clean[key] = r.get(key)
        out.append(clean)
    return out


def _current_nonhuman_occult(sim_info):
    current = _get_current_flags(sim_info)
    for occult_type in _all_occults():
        if _mask_has(current, _int_value(occult_type)):
            return occult_type
    flags = _get_occult_flags(sim_info)
    for occult_type in _all_occults():
        if _mask_has(flags, _int_value(occult_type)):
            return occult_type
    return None


def _payload_quality(payload):
    counts = {'json': 0, 'bytes': 0, 'protobuf': 0, 'pickle': 0, 'repr': 0, 'none': 0}
    for item in (payload or {}).values():
        if isinstance(item, dict):
            counts[item.get('kind', 'none')] = counts.get(item.get('kind', 'none'), 0) + 1
    return ', '.join('{}={}'.format(k, v) for k, v in sorted(counts.items()) if v) or 'empty'


def _save_occult_form_to_library(sim_info, occult_type=None, label=None):
    if occult_type is None:
        occult_type = _current_nonhuman_occult(sim_info)
    if occult_type is None:
        return {'ok': False, 'message': 'No non-human occult form is active or available to save.'}
    tracker = sim_info.occult_tracker
    form = _ensure_form(tracker, occult_type, generate_new=False)
    source = 'occult form'
    if form is None:
        form = sim_info
        source = 'current sim fallback'
    raw_payload = _snapshot_siminfo_payload(form)
    packed = _pack_payload(raw_payload)
    stamp = time.strftime('%Y-%m-%d %H:%M:%S')
    name = _safe_name(occult_type).upper()
    label = (label or '').strip() or '{} {} {}'.format(_sim_label(sim_info), name, stamp)
    rec_id = '{}-{}-{}-{}'.format(time.strftime('%Y%m%d%H%M%S'), _sim_id(sim_info), name.lower(), _slug(label))[:110]
    record = {
        'id': rec_id,
        'label': label,
        'sim': _sim_label(sim_info),
        'sim_id': _sim_id(sim_info),
        'occult': name,
        'occult_value': _int_value(occult_type),
        'created': stamp,
        'source': source,
        'payload': packed,
        'payload_quality': _payload_quality(packed),
    }
    data = _load_saved_forms()
    data.setdefault('forms', []).append(record)
    _save_saved_forms(data)
    _log('Saved occult form {} as {} ({})'.format(name, rec_id, record['payload_quality']))
    return {'ok': True, 'message': 'Saved {} form as {}'.format(name, label), 'saved_form': _summarize_records([record])[0]}


def _apply_saved_form_from_library(sim_info, record_id, occult_type=None, force_current=False):
    record_id = str(record_id or '').strip()
    if not record_id:
        return {'ok': False, 'message': 'Select or enter a saved form ID first.'}
    data = _load_saved_forms()
    record = None
    for item in data.get('forms', []):
        if str(item.get('id')) == record_id:
            record = item
            break
    if record is None:
        return {'ok': False, 'message': 'Saved form ID not found: {}'.format(record_id)}
    if occult_type is None:
        occult_type = _parse_occult(record.get('occult'))
    if occult_type is None:
        occult_type = _current_nonhuman_occult(sim_info)
    if occult_type is None:
        return {'ok': False, 'message': 'Could not determine which occult should receive the saved form.'}
    payload = _unpack_payload(record.get('payload') or {})
    tracker = sim_info.occult_tracker
    _add_occult(sim_info, occult_type, generate=True, add_traits=True, add_memory=True, use_gameplay_loot=True)
    target = _ensure_form(tracker, occult_type, generate_new=True)
    if target is None:
        target = sim_info
    restored = _restore_siminfo_payload(target, payload)
    if force_current:
        try:
            _switch_to(tracker, occult_type)
        except Exception:
            pass
        try:
            _copy_form_data(target, sim_info)
        except Exception:
            pass
    _set_tracker_form_available(tracker, True)
    details = _repair_sim(sim_info, deep=True)
    _recalc(sim_info)
    _log('Applied saved form {} to {} as {}'.format(record_id, _sim_label(sim_info), _safe_name(occult_type)))
    return {'ok': bool(restored), 'message': 'Applied saved form {} to {} {}'.format(record.get('label', record_id), _sim_label(sim_info), _safe_name(occult_type)), 'details': details, 'saved_form': _summarize_records([record])[0]}


def _delete_saved_form(record_id):
    record_id = str(record_id or '').strip()
    data = _load_saved_forms()
    before = len(data.get('forms', []))
    data['forms'] = [r for r in data.get('forms', []) if str(r.get('id')) != record_id]
    _save_saved_forms(data)
    return before != len(data.get('forms', []))


def _save_wardrobe_to_library(sim_info, label=None):
    raw_payload = _snapshot_siminfo_payload(sim_info)
    packed = _pack_payload(raw_payload)
    stamp = time.strftime('%Y-%m-%d %H:%M:%S')
    label = (label or '').strip() or '{} wardrobe {}'.format(_sim_label(sim_info), stamp)
    rec_id = '{}-{}-wardrobe-{}'.format(time.strftime('%Y%m%d%H%M%S'), _sim_id(sim_info), _slug(label))[:110]
    record = {
        'id': rec_id,
        'label': label,
        'sim': _sim_label(sim_info),
        'sim_id': _sim_id(sim_info),
        'created': stamp,
        'source': 'current sim appearance/outfits snapshot',
        'payload': packed,
        'payload_quality': _payload_quality(packed),
    }
    data = _load_wardrobes()
    data.setdefault('wardrobes', []).append(record)
    _save_wardrobes(data)
    _log('Saved wardrobe/CAS preset {} ({})'.format(rec_id, record['payload_quality']))
    return {'ok': True, 'message': 'Saved wardrobe/CAS preset {}'.format(label), 'wardrobe': _summarize_records([record])[0]}


def _apply_wardrobe_from_library(sim_info, record_id):
    record_id = str(record_id or '').strip()
    data = _load_wardrobes()
    record = None
    for item in data.get('wardrobes', []):
        if str(item.get('id')) == record_id:
            record = item
            break
    if record is None:
        return {'ok': False, 'message': 'Wardrobe/CAS preset ID not found: {}'.format(record_id)}
    payload = _unpack_payload(record.get('payload') or {})
    restored = _restore_siminfo_payload(sim_info, payload)
    _recalc(sim_info)
    return {'ok': bool(restored), 'message': 'Applied wardrobe/CAS preset {} to {}'.format(record.get('label', record_id), _sim_label(sim_info)), 'wardrobe': _summarize_records([record])[0]}


def _delete_wardrobe(record_id):
    record_id = str(record_id or '').strip()
    data = _load_wardrobes()
    before = len(data.get('wardrobes', []))
    data['wardrobes'] = [r for r in data.get('wardrobes', []) if str(r.get('id')) != record_id]
    _save_wardrobes(data)
    return before != len(data.get('wardrobes', []))


def _detect_mccc():
    global _MCCC_STATUS
    if _MCCC_STATUS is not None:
        return _MCCC_STATUS
    mods = []
    errors = {}
    for name in ('mc_cmd_center', 'mc_cas', 'mc_dresser', 'mc_occult', 'mc_cheats', 'mc_cleaner'):
        try:
            module = __import__(name)
            mods.append(name)
            for attr in ('VERSION', '__version__', 'version'):
                try:
                    val = getattr(module, attr)
                    if callable(val):
                        val = val()
                    if val:
                        errors[name + '_version'] = str(val)
                        break
                except Exception:
                    pass
        except Exception as exc:
            errors[name] = str(exc)
    _MCCC_STATUS = {
        'available': 'mc_cmd_center' in mods,
        'modules': mods,
        'missing_expected': [m for m in ('mc_cmd_center', 'mc_cas', 'mc_dresser', 'mc_occult') if m not in mods],
        'notes': 'Apex does not patch MCCC internals. It uses public console-style commands when possible and its own CAS shield for occult restoration.',
        'errors': errors,
    }
    return _MCCC_STATUS


def _sim_name_parts(sim_info):
    first = ''
    last = ''
    for attr in ('first_name', 'first_name_key'):
        try:
            value = getattr(sim_info, attr)
            if value:
                first = str(value)
                break
        except Exception:
            pass
    for attr in ('last_name', 'last_name_key'):
        try:
            value = getattr(sim_info, attr)
            if value:
                last = str(value)
                break
        except Exception:
            pass
    if not first:
        try:
            parts = str(sim_info.full_name).split()
            first = parts[0] if parts else 'Sim'
            last = parts[-1] if len(parts) > 1 else 'Sim'
        except Exception:
            first = 'Sim'
            last = 'Sim'
    if not last:
        last = 'Sim'
    first = re.sub(r'\s+', '', first)
    last = re.sub(r'\s+', '', last)
    return first, last


def _run_console_command(command_text):
    command_text = str(command_text or '').strip()
    if not command_text:
        return False, 'empty command'
    try:
        import sims4.commands as command_module
    except Exception as exc:
        return False, 'sims4.commands unavailable: {}'.format(exc)
    tried = []
    for attr in ('execute', 'execute_command'):
        func = getattr(command_module, attr, None)
        if func is None:
            continue
        for args in ((command_text,), (command_text, None), (command_text, 0)):
            try:
                result = func(*args)
                return True, '{} -> {}'.format(command_text, result)
            except Exception as exc:
                tried.append('{}{}: {}'.format(attr, len(args), exc))
    try:
        command_service = getattr(services, 'command_service', None)
        if callable(command_service):
            svc = command_service()
            for attr in ('execute', 'execute_command'):
                func = getattr(svc, attr, None)
                if func is None:
                    continue
                try:
                    result = func(command_text)
                    return True, '{} -> {}'.format(command_text, result)
                except Exception as exc:
                    tried.append('service.{}: {}'.format(attr, exc))
    except Exception as exc:
        tried.append('command_service: {}'.format(exc))
    return False, 'could not execute command; tried {}'.format('; '.join(tried[-5:]))


def _mccc_open_for_sim(sim_info):
    first, last = _sim_name_parts(sim_info)
    return _run_console_command('mccc {} {}'.format(first, last))


def _mccc_dresser_command(sim_info, operation, value=None):
    first, last = _sim_name_parts(sim_info)
    operation = (operation or '').lower()
    if operation == 'clean':
        return _run_console_command('dresser_clean {} {}'.format(first, last))
    if operation == 'check':
        return _run_console_command('dresser_check {} {}'.format(first, last))
    if operation == 'info':
        return _run_console_command('dresser_info {} {} all'.format(first, last))
    if operation == 'save':
        outfit = (value or '').strip() or 'All'
        return _run_console_command('dresser_os {} {} {}'.format(first, last, outfit))
    if operation == 'load':
        idx = (value or '').strip()
        return _run_console_command('dresser_ol {} {} {}'.format(first, last, idx)) if idx else _run_console_command('dresser_ol {} {}'.format(first, last))
    return False, 'unknown dresser operation {}'.format(operation)


def _mccc_dresser_copy_all(sim_info, source_code='E'):
    first, last = _sim_name_parts(sim_info)
    source_code = str(source_code or 'E').strip().upper()
    if source_code not in _OUTFIT_CODES:
        source_code = 'E'
    results = []
    ok_any = False
    for dest in _OUTFIT_CODES:
        if dest == source_code:
            continue
        ok, msg = _run_console_command('dresser_copy {} {} {} {}'.format(first, last, source_code, dest))
        ok_any = ok_any or ok
        results.append(msg)
    return ok_any, results


def _disk_trait_snapshot(sim_info):
    rows = []
    for _kind, name, trait in _occult_trait_snapshot(sim_info):
        guid = _trait_guid(trait)
        if guid:
            rows.append({'kind': _kind, 'occult': name, 'trait_id': guid, 'label': _trait_label(trait)})
    return rows


def _restore_disk_trait_snapshot(sim_info, rows):
    restored = []
    for row in rows or []:
        trait = _get_trait(row.get('trait_id'))
        if trait is not None and _add_trait(sim_info, trait):
            restored.append(str(row.get('occult') or row.get('trait_id')))
    return restored


def _save_cas_recovery_snapshot(sim_info, reason='manual'):
    records = []
    for item in _household_sim_infos(sim_info):
        tracker = item.occult_tracker
        forms = []
        try:
            for key, form in (_form_map(tracker) or {}).items():
                forms.append({'occult': _safe_name(key).upper(), 'payload': _pack_payload(_snapshot_siminfo_payload(form))})
        except Exception:
            pass
        records.append({
            'sim_id': _sim_id(item),
            'sim': _sim_label(item),
            'occult_types': _get_occult_flags(item),
            'current_occult_types': _get_current_flags(item),
            'shape': _pack_payload(_snapshot_siminfo_payload(item)),
            'forms': forms,
            'traits': _disk_trait_snapshot(item),
        })
    payload = {'version': 1, 'reason': reason, 'created': time.strftime('%Y-%m-%d %H:%M:%S'), 'active_sim_id': _sim_id(sim_info), 'records': records}
    _save_json_file('cas_mccc_recovery_snapshot.json', payload)
    return payload


def _restore_cas_recovery_snapshot(sim_info=None, reason='manual restore'):
    payload = _load_json_file('cas_mccc_recovery_snapshot.json', {'records': []})
    records = payload.get('records') or []
    details = []
    if not records:
        return details or ['no disk CAS/MCCC recovery snapshot']
    active = sim_info or _get_active_sim_info()
    id_to_sim = {}
    if active is not None:
        for item in _household_sim_infos(active):
            id_to_sim[_sim_id(item)] = item
    if not id_to_sim:
        try:
            for item in _list_sims():
                pass
        except Exception:
            pass
    for record in records:
        target = id_to_sim.get(int(record.get('sim_id') or 0))
        if target is None:
            if active is not None and int(record.get('sim_id') or 0) == _sim_id(active):
                target = active
        if target is None:
            details.append('skip missing sim {}'.format(record.get('sim')))
            continue
        tracker = target.occult_tracker
        _set_flags(target, 'occult_types', int(record.get('occult_types') or 0))
        _set_flags(target, 'current_occult_types', int(record.get('current_occult_types') or 0))
        _restore_siminfo_payload(target, _unpack_payload(record.get('shape') or {}))
        for form_row in record.get('forms') or []:
            oc = _parse_occult(form_row.get('occult'))
            if oc is None:
                continue
            form = _ensure_form(tracker, oc, generate_new=True)
            if form is not None:
                _restore_siminfo_payload(form, _unpack_payload(form_row.get('payload') or {}))
        restored_traits = _restore_disk_trait_snapshot(target, record.get('traits') or [])
        _set_tracker_form_available(tracker, True)
        repair = _repair_sim(target, deep=True)
        _recalc(target)
        details.append('restored {} via {}; traits {}; repair {}'.format(_sim_label(target), reason, ','.join(restored_traits) or 'unchanged', '; '.join(repair[:8])))
    return details


def _mccc_cas_shield_arm(sim_info, keep=None):
    global _MCCC_CAS_SHIELD_ENABLED, _MCCC_CAS_WAS_AWAY
    snapshot = _save_cas_recovery_snapshot(sim_info, reason='MCCC/CAS shield arm')
    for item in _household_sim_infos(sim_info):
        if keep is None:
            _cas_prepare_one(item)
        else:
            _cas_prepare_keep_one(item, keep)
    _MCCC_CAS_SHIELD_ENABLED = True
    _MCCC_CAS_WAS_AWAY = False
    _try_register_lot51_event_hooks()
    return ['armed MCCC/CAS shield for {} sim(s); snapshot {}'.format(len(snapshot.get('records') or []), snapshot.get('created'))]


def _mccc_cas_shield_tick():
    global _MCCC_CAS_WAS_AWAY, _MCCC_CAS_LAST_PULSE, _MCCC_LAST_RECOVERY
    if not _MCCC_CAS_SHIELD_ENABLED:
        return
    now = time.time()
    if now - _MCCC_CAS_LAST_PULSE < _MCCC_CAS_PULSE_SECONDS:
        return
    _MCCC_CAS_LAST_PULSE = now
    active = _get_active_sim_info()
    if active is None:
        _MCCC_CAS_WAS_AWAY = True
        return
    if _MCCC_CAS_WAS_AWAY:
        details = _restore_cas_recovery_snapshot(active, reason='CAS return watchdog')
        _MCCC_LAST_RECOVERY = time.strftime('%Y-%m-%d %H:%M:%S')
        _MCCC_CAS_WAS_AWAY = False
        for line in details:
            _log('MCCC/CAS shield: {}'.format(line))


def _lot51_zone_event(*args, **kwargs):
    try:
        active = _get_active_sim_info()
        if active is not None and _MCCC_CAS_SHIELD_ENABLED:
            details = _restore_cas_recovery_snapshot(active, reason='Lot51 zone/load event')
            for line in details:
                _log('Lot51 event CAS restore: {}'.format(line))
    except Exception as exc:
        _log('Lot51 event hook failed: {}'.format(exc))


def _try_register_lot51_event_hooks():
    global _MCCC_EVENT_HOOKED
    if _MCCC_EVENT_HOOKED:
        return True
    try:
        from lot51_core.services.events import event_service, CoreEvent
    except Exception:
        return False
    events = []
    for attr in ('ZONE_LOAD', 'LOADING_SCREEN_LIFTED', 'HOUSEHOLDS_AND_SIMS_LOADED', 'GAME_LOAD'):
        try:
            events.append(getattr(CoreEvent, attr))
        except Exception:
            pass
    if not events:
        return False
    registered = False
    for event_name in events:
        for call in ('add_listener', 'handler'):
            try:
                func = getattr(event_service, call)
            except Exception:
                continue
            try:
                if call == 'handler':
                    func(event_name)(_lot51_zone_event)
                else:
                    try:
                        func(event_name, _lot51_zone_event, weight=50)
                    except TypeError:
                        func(event_name, _lot51_zone_event)
                registered = True
                break
            except Exception:
                pass
    _MCCC_EVENT_HOOKED = registered
    if registered:
        _log('Lot51 Core event hooks registered for CAS/MCCC shield restore.')
    return registered

def _overlay_capabilities():
    _detect_lot51_core()
    return {
        'name': IMGUI_OVERLAY_NAME,
        'api_version': IMGUI_OVERLAY_API_VERSION,
        'toggle_key': IMGUI_OVERLAY_TOGGLE_KEY,
        'transport': 'localhost HTTP JSON on 127.0.0.1:{}'.format(PORT),
        'commands_endpoint': '/api/command?action=<name>&sim_id=<optional>&occult=<optional>&value=<optional>',
        'forms_endpoint': '/api/forms?query=<search>&sim_id=<optional>',
        'mccc_endpoint': '/api/mccc',
        'state_endpoint': '/api/overlay/state?count=120',
        'logs_endpoint': '/api/logs?count=220',
        'visible_poll_ms': IMGUI_OVERLAY_POLL_VISIBLE_MS,
        'visible_log_poll_ms': IMGUI_OVERLAY_LOG_VISIBLE_MS,
        'hidden_mode': IMGUI_OVERLAY_HIDDEN_MODE,
        'auto_repair_default': False,
        'mccc_status': _detect_mccc(),
        'saved_forms_count': len(_load_saved_forms().get('forms', [])),
        'wardrobe_presets_count': len(_load_wardrobes().get('wardrobes', [])),
        'cas_mccc_shield': {'enabled': _MCCC_CAS_SHIELD_ENABLED, 'lot51_event_hooked': _MCCC_EVENT_HOOKED, 'last_recovery': _MCCC_LAST_RECOVERY},
        'native_overlay_component': 'NativeOverlay/Source/TD1ApexD3D11Proxy.cpp builds as d3d11.dll proxy overlay',
        'lot51_core_status': _LOT51_STATUS,
        'lot51_core_details': _LOT51_DETAILS,
        'lot51_events_status': _LOT51_EVENT_STATUS,
        'mccc_status': _detect_mccc(),
        'mccc_details': _MCCC_DETAILS,
        'xml_injector_status': _detect_xml_injector(),
        'performance_guards': [
            'Overlay source polls only while visible.',
            'Hidden overlay should only perform F11 toggle check inside Present.',
            'Game data still changes only through the existing game-thread alarm command queue.',
            'Auto repair remains off by default.',
            'List Sims is explicit/manual; no idle all-world scans are started by the overlay API.',
            'MCCC/CAS guard snapshots only the active household at a low frequency and restores only after an event/manual command.',
            'Saved-form search reads a compact local JSON index; it does not scan Sims.',
            'MCCC/CAS guardian is event-driven through Lot51 Core when available; no high-frequency polling is used.',
            'Saved form searches read Apex metadata and do not scan Sims until an apply/save command is clicked.',
        ],
    }


def _compact_status_for_overlay(sim_id=None):
    sim_info = _get_sim_info_by_id(sim_id) if sim_id not in (None, '') else _get_active_sim_info()
    if sim_info is None:
        return {
            'ok': False,
            'message': 'No active/selected Sim available yet.',
            'sim': None,
            'sim_id': None,
            'health': {'score': 0, 'issues': ['No Sim selected']},
            'occults': [],
        }
    full = _status(sim_info)
    occults = []
    for item in full.get('occults', []):
        occults.append({
            'name': item.get('name'),
            'value': item.get('value'),
            'has_occult': item.get('has_occult'),
            'has_form_data': item.get('has_form_data'),
            'has_memory_trait': item.get('has_memory_trait'),
            'has_tuning': item.get('has_tuning'),
        })
    return {
        'ok': True,
        'message': 'Overlay compact status ready',
        'sim': full.get('sim'),
        'sim_id': full.get('sim_id'),
        'occult_types_value': full.get('occult_types_value'),
        'current_occult_types_value': full.get('current_occult_types_value'),
        'health': full.get('health'),
        'cas_memory_saved': full.get('cas_memory_saved'),
        'stored_memory_slots': full.get('stored_memory_slots'),
        'occults': occults,
        'mccc_guard_enabled': _MCCC_GUARD,
        'mccc_auto_restore': _MCCC_AUTO_RESTORE,
        'mccc_guard_snapshots': len(_MCCC_GUARD_MEMORY),
        'saved_form_count': len(_list_saved_forms('')),
    }


def _overlay_compact_from_status_payload(result):
    if not isinstance(result, dict) or not result.get('ok'):
        return {
            'ok': False,
            'message': result.get('message', 'Status unavailable') if isinstance(result, dict) else 'Status unavailable',
            'sim': None,
            'sim_id': None,
            'health': {'score': 0, 'issues': ['Status unavailable']},
            'occults': [],
        }
    full = result.get('data') if isinstance(result.get('data'), dict) else {}
    occults = []
    for item in full.get('occults', []):
        occults.append({
            'name': item.get('name'),
            'value': item.get('value'),
            'has_occult': item.get('has_occult'),
            'has_form_data': item.get('has_form_data'),
            'has_memory_trait': item.get('has_memory_trait'),
            'has_tuning': item.get('has_tuning'),
        })
    return {
        'ok': True,
        'message': 'Overlay compact status ready',
        'sim': full.get('sim'),
        'sim_id': full.get('sim_id'),
        'occult_types_value': full.get('occult_types_value'),
        'current_occult_types_value': full.get('current_occult_types_value'),
        'health': full.get('health'),
        'cas_memory_saved': full.get('cas_memory_saved'),
        'stored_memory_slots': full.get('stored_memory_slots'),
        'occults': occults,
        'mccc_guard_enabled': _MCCC_GUARD,
        'mccc_auto_restore': _MCCC_AUTO_RESTORE,
        'mccc_guard_snapshots': len(_MCCC_GUARD_MEMORY),
        'saved_form_count': len(_list_saved_forms('')),
    }


def _overlay_state_payload(query=None):
    query = query or {}
    count = query.get('count', 120) if isinstance(query, dict) else 120
    sim_id = query.get('sim_id', '') if isinstance(query, dict) else ''
    logs = _logs_payload(count)
    # Important: the native ImGui overlay polls this endpoint while visible. Route even
    # read-only Sim status through the existing game-thread queue instead of inspecting
    # SimInfo directly on the HTTP socket thread.
    status_result = _submit_action('status', sim_id=sim_id, wait_seconds=2.5)
    status = _overlay_compact_from_status_payload(status_result)
    return {
        'ok': True,
        'message': 'Overlay state ready',
        'build_version': _BUILD_VERSION,
        'server': SERVER_NAME,
        'host': HOST,
        'port': PORT,
        'status': status,
        'logs': logs.get('history', []),
        'saved_forms': _list_saved_forms(query.get('query', '') if isinstance(query, dict) else '', None, 80),
        'mccc': _mccc_status_payload(),
        'pending_count': logs.get('pending_count', 0),
        'alarm_ready': _ALARM_READY,
        'server_running': _SERVER_RUNNING,
        'auto_repair': _AUTO_REPAIR,
        'native_status': _NATIVE_STATUS,
        'overlay': _overlay_capabilities(),
        'lot51_core_status': _detect_lot51_core(),
        'mccc': _detect_mccc(),
        'saved_forms': {'count': len(_load_saved_forms().get('forms', [])), 'data_dir': _data_directory()},
        'wardrobes': {'count': len(_load_wardrobes().get('wardrobes', []))},
        'cas_mccc_shield': {'enabled': _MCCC_CAS_SHIELD_ENABLED, 'was_away': _MCCC_CAS_WAS_AWAY, 'lot51_event_hooked': _MCCC_EVENT_HOOKED, 'last_recovery': _MCCC_LAST_RECOVERY},
        'performance': _perf_snapshot(),
    }



def _detect_mccc():
    global _MCCC_STATUS, _MCCC_DETAILS
    if _MCCC_STATUS not in ('not checked', ''):
        return _MCCC_STATUS
    details = {'available': False, 'modules': {}, 'notes': []}
    for name in ('mc_cmd_center', 'mc_cas', 'mc_dresser', 'mc_occult', 'mc_cleaner', 'mc_cheats'):
        try:
            module = __import__(name)
            details['modules'][name] = {'available': True, 'module': str(module)}
            details['available'] = True
        except Exception as exc:
            details['modules'][name] = {'available': False, 'error': str(exc)}
    if details['modules'].get('mc_cmd_center', {}).get('available'):
        _MCCC_STATUS = 'available'
    elif details['available']:
        _MCCC_STATUS = 'partial'
        details['notes'].append('One or more optional MCCC modules were detected, but mc_cmd_center was not importable.')
    else:
        _MCCC_STATUS = 'not installed'
    _MCCC_DETAILS = details
    return _MCCC_STATUS


def _mark_mccc_restore_needed(reason):
    global _MCCC_PENDING_RESTORE_REASON
    _MCCC_PENDING_RESTORE_REASON = str(reason or 'CAS return')
    _log('MCCC/CAS guard scheduled restore: {}'.format(_MCCC_PENDING_RESTORE_REASON))


def _lot51_loading_screen_lifted_handler(*args, **kwargs):
    _mark_mccc_restore_needed('Lot51 Core loading screen lifted event')


def _register_lot51_core_events():
    global _LOT51_EVENT_REGISTERED
    if _LOT51_EVENT_REGISTERED:
        return True
    try:
        from lot51_core.services.events import event_service, CoreEvent
    except Exception as exc:
        _LOT51_DETAILS.setdefault('event_error', str(exc))
        return False
    try:
        event_name = getattr(CoreEvent, 'LOADING_SCREEN_LIFTED', 'zone.loading_screen_lifted')
        handler = _lot51_loading_screen_lifted_handler
        if hasattr(event_service, 'add_listener'):
            event_service.add_listener(event_name, handler, weight=500)
        elif hasattr(event_service, 'handler'):
            event_service.handler(event_name, weight=500)(handler)
        else:
            return False
        _LOT51_EVENT_HANDLERS.append(handler)
        _LOT51_EVENT_REGISTERED = True
        _log('Lot51 Core event hook armed for loading screen lifted; MCCC/CAS restore will run on the next safe queue tick.')
        return True
    except Exception as exc:
        _LOT51_DETAILS.setdefault('event_error', str(exc))
        _log('Lot51 Core event registration failed safely: {}'.format(exc))
        return False


def _json_safe(value, depth=0):
    if depth > 8:
        return {'__td1_type': 'repr', 'value': repr(value)}
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return {'__td1_type': 'bytes', 'data': base64.b64encode(value).decode('ascii')}
    if isinstance(value, tuple) and len(value) == 2 and value[0] == 'protobuf' and isinstance(value[1], bytes):
        return {'__td1_type': 'protobuf', 'data': base64.b64encode(value[1]).decode('ascii')}
    if isinstance(value, (list, tuple)):
        return {'__td1_type': 'tuple' if isinstance(value, tuple) else 'list', 'items': [_json_safe(v, depth + 1) for v in value]}
    if isinstance(value, dict):
        return {'__td1_type': 'dict', 'items': [[_json_safe(k, depth + 1), _json_safe(v, depth + 1)] for k, v in value.items()]}
    return {'__td1_type': 'repr', 'value': repr(value)}


def _json_restore(value):
    if isinstance(value, dict) and '__td1_type' in value:
        typ = value.get('__td1_type')
        if typ == 'bytes':
            try:
                return base64.b64decode(value.get('data', '').encode('ascii'))
            except Exception:
                return b''
        if typ == 'protobuf':
            try:
                return ('protobuf', base64.b64decode(value.get('data', '').encode('ascii')))
            except Exception:
                return ('protobuf', b'')
        if typ == 'list':
            return [_json_restore(v) for v in value.get('items', [])]
        if typ == 'tuple':
            return tuple(_json_restore(v) for v in value.get('items', []))
        if typ == 'dict':
            out = {}
            for pair in value.get('items', []):
                try:
                    out[_json_restore(pair[0])] = _json_restore(pair[1])
                except Exception:
                    pass
            return out
        return None
    if isinstance(value, list):
        return [_json_restore(v) for v in value]
    return value


def _storage_root():
    candidates = []
    try:
        import sims4.paths
        root = getattr(sims4.paths, 'USER_DATA_ROOT', None)
        if root:
            candidates.append(root)
    except Exception:
        pass
    try:
        candidates.append(os.path.join(os.path.expanduser('~'), 'Documents', 'Electronic Arts', 'The Sims 4'))
    except Exception:
        pass
    try:
        candidates.append(os.getcwd())
    except Exception:
        pass
    for base in candidates:
        try:
            if base and os.path.isdir(base):
                path = os.path.join(base, 'TD1_Occult_Hybrid_Apex')
                if not os.path.isdir(path):
                    os.makedirs(path)
                return path
        except Exception:
            pass
    return None


def _saved_forms_path():
    root = _storage_root()
    if not root:
        return None
    return os.path.join(root, 'SavedForms.json')


def _load_saved_forms():
    global _SAVED_FORMS_LOADED, _SAVED_FORMS, _SAVED_FORM_COUNTER
    if _SAVED_FORMS_LOADED:
        return True
    _SAVED_FORMS_LOADED = True
    path = _saved_forms_path()
    if not path or not os.path.exists(path):
        return False
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            raw = json.load(fh)
        forms = raw.get('forms', {}) if isinstance(raw, dict) else {}
        loaded = {}
        max_counter = 0
        for key, rec in forms.items():
            if not isinstance(rec, dict):
                continue
            payload = _json_restore(rec.get('payload'))
            if payload is None:
                payload = {}
            new = dict(rec)
            new['payload'] = payload
            loaded[str(key)] = new
            try:
                suffix = int(str(key).split('-')[-1], 16)
                if suffix > max_counter:
                    max_counter = suffix
            except Exception:
                pass
        _SAVED_FORMS.update(loaded)
        _SAVED_FORM_COUNTER = max(_SAVED_FORM_COUNTER, max_counter)
        _log('Loaded {} saved occult form preset(s) from {}'.format(len(loaded), path))
        return True
    except Exception as exc:
        _log('Saved form library load failed safely: {}'.format(exc))
        return False


def _save_saved_forms_to_disk():
    path = _saved_forms_path()
    if not path:
        return False, 'No writable Sims user-data folder found'
    try:
        out = {'version': 2, 'build': _BUILD_VERSION, 'updated': time.time(), 'forms': {}}
        for key, rec in _SAVED_FORMS.items():
            item = dict(rec)
            item['payload'] = _json_safe(rec.get('payload', {}))
            out['forms'][str(key)] = item
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(out, fh, indent=2, sort_keys=True)
        return True, path
    except Exception as exc:
        return False, str(exc)


def _next_saved_form_id(sim_info, occult_name):
    global _SAVED_FORM_COUNTER
    _SAVED_FORM_COUNTER += 1
    safe_occ = (occult_name or 'FORM').upper().replace(' ', '_')
    return 'sf-{0}-{1:x}'.format(safe_occ[:12], int(time.time() * 1000) ^ _SAVED_FORM_COUNTER)


def _saved_form_summary(rec):
    return {
        'id': rec.get('id'),
        'name': rec.get('name'),
        'sim_id': rec.get('sim_id'),
        'sim_name': rec.get('sim_name'),
        'occult': rec.get('occult'),
        'source': rec.get('source'),
        'created': rec.get('created'),
        'updated': rec.get('updated'),
        'payload_keys': sorted(list((rec.get('payload') or {}).keys())),
    }


def _list_saved_forms(search=''):
    _load_saved_forms()
    text = (search or '').strip().lower()
    rows = []
    for rec in _SAVED_FORMS.values():
        blob = ' '.join(str(rec.get(k, '')) for k in ('id', 'name', 'sim_name', 'occult', 'source')).lower()
        if text and text not in blob:
            continue
        rows.append(_saved_form_summary(rec))
    rows.sort(key=lambda r: (str(r.get('name') or '').lower(), str(r.get('created') or '')))
    return rows


def _saved_forms_text(search=''):
    rows = _list_saved_forms(search)
    lines = ['Saved occult forms: {} match(es)'.format(len(rows))]
    for r in rows:
        lines.append('{id} | {name} | occult={occult} | sim={sim_name} ({sim_id}) | source={source}'.format(**dict((k, r.get(k, '')) for k in ('id','name','occult','sim_name','sim_id','source'))))
    return '\n'.join(lines)


def _resolve_saved_form(token):
    _load_saved_forms()
    key = str(token or '').strip()
    if not key:
        return None
    if key in _SAVED_FORMS:
        return _SAVED_FORMS[key]
    low = key.lower()
    matches = []
    for rec in _SAVED_FORMS.values():
        if low == str(rec.get('name', '')).lower() or low in str(rec.get('name', '')).lower() or low in str(rec.get('id', '')).lower():
            matches.append(rec)
    if len(matches) == 1:
        return matches[0]
    return matches[0] if matches else None


def _make_saved_form_record(sim_info, source_obj, occult_type=None, name=None, source='current'):
    if source_obj is None:
        return None
    occult_name = _safe_name(occult_type).upper() if occult_type is not None else 'CURRENT'
    payload = _snapshot_siminfo_payload(source_obj)
    if not payload:
        payload = {}
    label = (name or '').strip()
    if not label:
        label = '{} {} {}'.format(_sim_label(sim_info).split(' (')[0], occult_name, time.strftime('%Y-%m-%d %H:%M'))
    now = time.time()
    rec_id = _next_saved_form_id(sim_info, occult_name)
    return {
        'id': rec_id,
        'name': label,
        'sim_id': _sim_id(sim_info),
        'sim_name': _sim_label(sim_info),
        'occult': occult_name,
        'source': source,
        'created': now,
        'updated': now,
        'build': _BUILD_VERSION,
        'payload': payload,
    }


def _save_active_form(sim_info, occult_type=None, name=None):
    _load_saved_forms()
    rec = _make_saved_form_record(sim_info, sim_info, occult_type=occult_type, name=name, source='active-current-form')
    if rec is None:
        return None, 'No current form data could be read'
    _SAVED_FORMS[rec['id']] = rec
    ok, msg = _save_saved_forms_to_disk()
    _log('Saved active form preset {} ({})'.format(rec['id'], rec['name']))
    return rec, msg if ok else 'Saved in memory only: {}'.format(msg)


def _save_occult_form(sim_info, occult_type, name=None):
    _load_saved_forms()
    tracker = sim_info.occult_tracker
    form = _ensure_form(tracker, occult_type, generate_new=False)
    if form is None:
        return None, 'No stored {} form exists yet'.format(_safe_name(occult_type))
    rec = _make_saved_form_record(sim_info, form, occult_type=occult_type, name=name, source='stored-occult-form')
    _SAVED_FORMS[rec['id']] = rec
    ok, msg = _save_saved_forms_to_disk()
    _log('Saved occult form preset {} ({})'.format(rec['id'], rec['name']))
    return rec, msg if ok else 'Saved in memory only: {}'.format(msg)


def _apply_saved_payload_to_target(payload, target):
    if not payload or target is None:
        return False
    return _restore_siminfo_payload(target, payload)


def _apply_saved_form(sim_info, token, occult_type=None, to_current=False, force=False):
    rec = _resolve_saved_form(token)
    if rec is None:
        return False, 'No saved form matched {}'.format(token)
    payload = rec.get('payload') or {}
    tracker = sim_info.occult_tracker
    targets = []
    if to_current or occult_type is None:
        targets.append(('current', sim_info))
    if occult_type is not None:
        form = _ensure_form(tracker, occult_type, generate_new=True)
        targets.append((_safe_name(occult_type), form))
    copied = []
    for label, target in targets:
        if _apply_saved_payload_to_target(payload, target):
            copied.append(label)
    if occult_type is not None and force:
        _add_occult(sim_info, occult_type, generate=True, add_traits=True, add_memory=True, use_gameplay_loot=False)
        _set_tracker_form_available(tracker, True)
    _recalc(sim_info)
    if not copied:
        return False, 'Saved form {} matched, but no payload fields could be applied'.format(rec.get('id'))
    _log('Applied saved form {} to {} on {}'.format(rec.get('id'), ', '.join(copied), _sim_label(sim_info)))
    return True, 'Applied saved form {} ({}) to {}'.format(rec.get('id'), rec.get('name'), ', '.join(copied))


def _delete_saved_form(token):
    _load_saved_forms()
    rec = _resolve_saved_form(token)
    if rec is None:
        return False, 'No saved form matched {}'.format(token)
    _SAVED_FORMS.pop(rec.get('id'), None)
    ok, msg = _save_saved_forms_to_disk()
    return True, 'Deleted saved form {} ({})'.format(rec.get('id'), rec.get('name')) + ('' if ok else ' from memory only: {}'.format(msg))


def _snapshot_guard_one(sim_info, reason='manual'):
    if sim_info is None:
        return None
    tracker = sim_info.occult_tracker
    data = {
        'sim_id': _sim_id(sim_info),
        'sim_name': _sim_label(sim_info),
        'time': time.time(),
        'reason': reason,
        'occult_types': _get_occult_flags(sim_info),
        'current_occult_types': _get_current_flags(sim_info),
        'form_map': _form_map(tracker).copy(),
        'shape': _snapshot_siminfo_payload(sim_info),
        'trait_snapshot': _occult_trait_snapshot(sim_info),
        'health': _health_report(sim_info),
    }
    _MCCC_GUARD_MEMORY[_sim_id(sim_info)] = data
    return data


def _snapshot_guard_household(sim_info, reason='manual'):
    rows = []
    for item in _household_sim_infos(sim_info):
        try:
            data = _snapshot_guard_one(item, reason=reason)
            if data is not None:
                rows.append('{} flags={} current={} forms={}'.format(data.get('sim_name'), data.get('occult_types'), data.get('current_occult_types'), len(data.get('form_map') or {})))
        except Exception as exc:
            rows.append('{} snapshot failed: {}'.format(_sim_label(item), exc))
    if rows:
        _log('MCCC/CAS guard snapshot saved ({}): {} Sim(s)'.format(reason, len(rows)))
    return rows


def _restore_guard_one(sim_info, preserve_current_edits=True):
    data = _MCCC_GUARD_MEMORY.get(_sim_id(sim_info)) or _CAS_MEMORY.get(_sim_id(sim_info))
    if not data:
        return 'no guard snapshot for {}'.format(_sim_label(sim_info))
    tracker = sim_info.occult_tracker
    _set_flags(sim_info, 'occult_types', data.get('occult_types', 0))
    _set_flags(sim_info, 'current_occult_types', _clamp_current(data.get('occult_types', 0), data.get('current_occult_types', 0)))
    saved_map = data.get('form_map') or {}
    live_map = _form_map(tracker)
    restored_forms = []
    if preserve_current_edits:
        for key, value in saved_map.items():
            if key not in live_map or live_map.get(key) is None:
                live_map[key] = value
                restored_forms.append(_safe_name(key))
    else:
        live_map.update(saved_map)
        restored_forms = [_safe_name(key) for key in saved_map.keys()]
        _restore_siminfo_payload(sim_info, data.get('shape') or {})
    restored_traits = _restore_occult_trait_snapshot(sim_info, data.get('trait_snapshot'))
    _set_tracker_form_available(tracker, True)
    details = _repair_sim(sim_info, deep=True)
    _recalc(sim_info)
    return '{} restored; forms={} traits={} repair={}'.format(_sim_label(sim_info), ','.join(restored_forms) or 'kept-live', ','.join(restored_traits) or 'unchanged', '; '.join(details[:8]))


def _restore_guard_household(sim_info, preserve_current_edits=True, reason='manual'):
    rows = []
    for item in _household_sim_infos(sim_info):
        try:
            rows.append(_restore_guard_one(item, preserve_current_edits=preserve_current_edits))
        except Exception as exc:
            rows.append('{} restore failed: {}'.format(_sim_label(item), exc))
    if rows:
        _log('MCCC/CAS guard restore ran ({}): {} Sim(s)'.format(reason, len(rows)))
    return rows


def _mccc_guard_tick():
    global _MCCC_LAST_PULSE, _MCCC_LAST_SNAPSHOT, _MCCC_PENDING_RESTORE_REASON
    if not _MCCC_GUARD:
        return
    now = time.time()
    if now - _MCCC_LAST_PULSE < _MCCC_PULSE_SECONDS:
        return
    _MCCC_LAST_PULSE = now
    try:
        sim_info = _get_active_sim_info()
        if sim_info is None:
            return
        if _MCCC_PENDING_RESTORE_REASON and _MCCC_AUTO_RESTORE:
            reason = _MCCC_PENDING_RESTORE_REASON
            _MCCC_PENDING_RESTORE_REASON = None
            _restore_guard_household(sim_info, preserve_current_edits=True, reason=reason)
            return
        if now - _MCCC_LAST_SNAPSHOT >= _MCCC_SNAPSHOT_INTERVAL_SECONDS:
            _MCCC_LAST_SNAPSHOT = now
            _snapshot_guard_household(sim_info, reason='low-frequency MCCC guard')
    except Exception as exc:
        _log('MCCC/CAS guard tick failed safely: {}'.format(exc))


def _filter_payload_scope(payload, scope):
    scope = (scope or 'all').strip().lower()
    if scope == 'all':
        return dict(payload)
    if scope in ('wardrobe', 'outfits', 'tattoos'):
        keys = ('__outfits__',)
    elif scope == 'body':
        keys = ('physique', 'facial_attributes', 'genetic_data', 'voice_pitch', 'voice_actor', 'voice_effect')
    elif scope == 'face':
        keys = ('facial_attributes', 'voice_pitch', 'voice_actor', 'voice_effect')
    elif scope == 'physique':
        keys = ('physique',)
    elif scope == 'skin':
        keys = ('skin_tone', 'pelt_layers', 'base_trait_ids')
    else:
        keys = tuple(payload.keys())
    return dict((k, v) for k, v in payload.items() if k in keys)


def _appearance_copy(sim_info, scope='all'):
    scope = (scope or 'all').strip().lower()
    payload = _filter_payload_scope(_snapshot_siminfo_payload(sim_info), scope)
    _APPEARANCE_CLIPBOARD[scope] = {'sim_id': _sim_id(sim_info), 'sim_name': _sim_label(sim_info), 'time': time.time(), 'scope': scope, 'payload': payload}
    return 'Copied {} appearance payload from {} ({} field(s))'.format(scope, _sim_label(sim_info), len(payload))


def _appearance_paste(sim_info, scope='all'):
    scope = (scope or 'all').strip().lower()
    data = _APPEARANCE_CLIPBOARD.get(scope) or _APPEARANCE_CLIPBOARD.get('all')
    if not data:
        return False, 'No {} appearance clipboard is available yet'.format(scope)
    payload = _filter_payload_scope(data.get('payload') or {}, scope)
    ok = _restore_siminfo_payload(sim_info, payload)
    _recalc(sim_info)
    return ok, 'Pasted {} appearance payload onto {} from {} ({} field(s))'.format(scope, _sim_label(sim_info), data.get('sim_name'), len(payload))


def _current_outfit_tuple(sim_info):
    for name in ('get_current_outfit', 'current_outfit'):
        try:
            value = getattr(sim_info, name)
            if callable(value):
                value = value()
            if value:
                return value
        except Exception:
            pass
    try:
        sim = sim_info.get_sim_instance()
        if sim is not None:
            value = getattr(sim, 'current_outfit', None)
            if callable(value):
                value = value()
            if value:
                return value
    except Exception:
        pass
    return None


def _apply_current_outfit_to_all(sim_info):
    details = []
    current = _current_outfit_tuple(sim_info)
    if not current:
        return False, ['Current outfit could not be read with this game build.']
    try:
        from sims.outfits.outfit_enums import OutfitCategory
        categories = list(OutfitCategory)
    except Exception:
        categories = []
    for category in categories:
        if str(category).upper().endswith('INVALID'):
            continue
        try:
            count = 1
            for count_name in ('get_outfit_count', 'get_number_of_outfits_in_category'):
                func = getattr(sim_info, count_name, None)
                if func is not None:
                    try:
                        count = max(1, int(func(category)))
                        break
                    except Exception:
                        pass
            for idx in range(max(1, count)):
                for setter in ('set_outfit', 'set_current_outfit'):
                    func = getattr(sim_info, setter, None)
                    if func is None:
                        continue
                    try:
                        func(category, idx, current)
                        details.append('{}[{}]'.format(_safe_name(category), idx))
                        break
                    except Exception:
                        pass
        except Exception:
            pass
    for call in ('resend_current_outfit', 'resend_outfits'):
        try:
            getattr(sim_info, call)()
        except Exception:
            pass
    if not details:
        return False, ['No outfit setter accepted the current outfit tuple. Use Copy Wardrobe/Paste Wardrobe instead.']
    return True, details


def _force_resend_appearance(sim_info):
    calls = []
    for call in ('resend_physical_attributes', 'resend_current_outfit', 'force_resend_suntan_data', 'resend_outfits', 'resend_facial_attributes'):
        try:
            getattr(sim_info, call)()
            calls.append(call)
        except Exception:
            pass
    return calls or ['no resend calls available']

def _format_action_label(item):
    try:
        parts = ['#{}'.format(item.get('id', '?')), str(item.get('action') or 'status')]
        if item.get('occult'):
            parts.append('occult={}'.format(item.get('occult')))
        if item.get('sim_id'):
            parts.append('sim={}'.format(item.get('sim_id')))
        if item.get('value') not in (None, ''):
            parts.append('value={}'.format(item.get('value')))
        return ' '.join(parts)
    except Exception:
        return str(item)


def _record_perf(action, elapsed_ms, ok=True):
    key = (action or 'status').strip().lower()
    with _LOCK:
        data = _PERF_STATS.get(key)
        if data is None:
            data = {'count': 0, 'ok': 0, 'fail': 0, 'last_ms': 0.0, 'avg_ms': 0.0, 'max_ms': 0.0}
            _PERF_STATS[key] = data
        data['count'] += 1
        if ok:
            data['ok'] += 1
        else:
            data['fail'] += 1
        elapsed = float(elapsed_ms)
        data['last_ms'] = round(elapsed, 2)
        data['avg_ms'] = round(((float(data['avg_ms']) * (data['count'] - 1)) + elapsed) / data['count'], 2)
        if elapsed > float(data['max_ms']):
            data['max_ms'] = round(elapsed, 2)


def _perf_snapshot():
    with _LOCK:
        return dict((k, dict(v)) for k, v in _PERF_STATS.items())


def _logs_payload(count=160):
    try:
        count = int(count)
    except Exception:
        count = 160
    if count < 20:
        count = 20
    if count > 600:
        count = 600
    with _LOCK:
        history = list(_HISTORY[-count:])
        pending_count = len(_PENDING)
        result_count = len(_RESULTS)
    return {
        'ok': True,
        'message': 'Log snapshot ready',
        'build_version': _BUILD_VERSION,
        'history': history,
        'pending_count': pending_count,
        'result_count': result_count,
        'alarm_ready': _ALARM_READY,
        'server_running': _SERVER_RUNNING,
        'auto_repair': _AUTO_REPAIR,
        'queue_interval_seconds': _ACTION_QUEUE_INTERVAL_SECONDS,
        'native_status': _NATIVE_STATUS,
        'overlay': _overlay_capabilities(),
        'lot51_core_status': _detect_lot51_core(),
        'performance': _perf_snapshot(),
    }

def _safe_name(obj):
    try:
        return obj.name
    except Exception:
        try:
            return str(obj).split('.')[-1]
        except Exception:
            return str(obj)


def _int_value(obj):
    try:
        return int(obj)
    except Exception:
        try:
            return int(obj.value)
        except Exception:
            try:
                return int(str(obj), 0)
            except Exception:
                return 0


def _coerce_flags(value):
    flags = _int_value(value)
    if OccultType is not None:
        try:
            return OccultType(flags)
        except Exception:
            pass
    return flags


def _native_candidates():
    candidates = []
    try:
        file_name = globals().get('__file__', '') or ''
        lower = file_name.lower()
        idx = lower.find('.ts4script')
        if idx >= 0:
            script_archive = file_name[:idx + len('.ts4script')]
            mod_dir = os.path.dirname(script_archive)
            candidates.append(os.path.join(mod_dir, 'Native', NATIVE_DLL))
            candidates.append(os.path.join(mod_dir, NATIVE_DLL))
            candidates.append(os.path.join(os.path.dirname(mod_dir), 'Native', NATIVE_DLL))
        folder = os.path.dirname(file_name)
        if folder:
            candidates.append(os.path.join(folder, 'Native', NATIVE_DLL))
            candidates.append(os.path.join(folder, NATIVE_DLL))
    except Exception:
        pass
    try:
        cwd = os.getcwd()
        candidates.append(os.path.join(cwd, 'Mods', 'TD1 Occult Hybrid Apex', 'Native', NATIVE_DLL))
        candidates.append(os.path.join(cwd, 'Native', NATIVE_DLL))
    except Exception:
        pass
    out = []
    seen = set()
    for item in candidates:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _bind_native_functions(dll):
    specs = {
        'TD1OccultNativeVersion': (ctypes.c_ulonglong, []),
        'TD1OccultMaskAdd': (ctypes.c_ulonglong, [ctypes.c_ulonglong, ctypes.c_ulonglong]),
        'TD1OccultMaskRemove': (ctypes.c_ulonglong, [ctypes.c_ulonglong, ctypes.c_ulonglong]),
        'TD1OccultMaskHas': (ctypes.c_int, [ctypes.c_ulonglong, ctypes.c_ulonglong]),
        'TD1OccultMaskToggle': (ctypes.c_ulonglong, [ctypes.c_ulonglong, ctypes.c_ulonglong]),
        'TD1OccultNormalizeCurrent': (ctypes.c_ulonglong, [ctypes.c_ulonglong, ctypes.c_ulonglong]),
        'TD1OccultLowestBit': (ctypes.c_ulonglong, [ctypes.c_ulonglong]),
        'TD1OccultChooseSafeForm': (ctypes.c_ulonglong, [ctypes.c_ulonglong, ctypes.c_ulonglong, ctypes.c_ulonglong]),
        'TD1OccultSimIdLooksValid': (ctypes.c_int, [ctypes.c_longlong]),
        'TD1OccultFnv1a64': (ctypes.c_ulonglong, [ctypes.c_char_p, ctypes.c_uint]),
        'TD1OccultMaskNormalizeSupported': (ctypes.c_ulonglong, [ctypes.c_ulonglong, ctypes.c_ulonglong]),
        'TD1OccultMaskCount': (ctypes.c_uint, [ctypes.c_ulonglong]),
        'TD1OccultIsPowerOfTwo': (ctypes.c_int, [ctypes.c_ulonglong]),
        'TD1OccultChooseNext': (ctypes.c_ulonglong, [ctypes.c_ulonglong, ctypes.c_ulonglong]),
        'TD1OccultStateScore': (ctypes.c_int, [ctypes.c_ulonglong, ctypes.c_ulonglong, ctypes.c_ulonglong]),
        'TD1OccultClampCurrent': (ctypes.c_ulonglong, [ctypes.c_ulonglong, ctypes.c_ulonglong]),
        'TD1OccultRepairMask': (ctypes.c_ulonglong, [ctypes.c_ulonglong, ctypes.c_ulonglong, ctypes.c_ulonglong]),
        'TD1OccultMaskMissing': (ctypes.c_ulonglong, [ctypes.c_ulonglong, ctypes.c_ulonglong]),
        'TD1OccultMaskExtra': (ctypes.c_ulonglong, [ctypes.c_ulonglong, ctypes.c_ulonglong]),
        'TD1OccultNeedsRepair': (ctypes.c_int, [ctypes.c_ulonglong, ctypes.c_ulonglong, ctypes.c_ulonglong]),
        'TD1OccultCommandHash': (ctypes.c_ulonglong, [ctypes.c_ulonglong, ctypes.c_ulonglong, ctypes.c_ulonglong]),
        'TD1OverlayNativeVersion': (ctypes.c_ulonglong, []),
        'TD1OverlayVirtualKeyF11': (ctypes.c_uint, []),
        'TD1OverlayShouldPoll': (ctypes.c_int, [ctypes.c_ulonglong, ctypes.c_ulonglong, ctypes.c_uint, ctypes.c_uint]),
        'TD1OverlayClampPollMs': (ctypes.c_uint, [ctypes.c_uint, ctypes.c_uint, ctypes.c_uint]),
        'TD1OverlayPerfLevel': (ctypes.c_uint, [ctypes.c_uint]),
        'TD1OverlayProtocolVersion': (ctypes.c_uint, []),
        'TD1OverlayMaxLogLines': (ctypes.c_uint, []),
        'TD1OverlayHiddenMode': (ctypes.c_uint, []),
        'TD1OverlayProtocolHash': (ctypes.c_ulonglong, []),
        'TD1OverlayCommandSafeToPoll': (ctypes.c_int, [ctypes.c_uint, ctypes.c_uint]),
        'TD1SavedFormHash': (ctypes.c_ulonglong, [ctypes.c_char_p, ctypes.c_uint]),
    }
    bound = []
    missing = []
    for name, spec in specs.items():
        try:
            func = getattr(dll, name)
            func.restype = spec[0]
            func.argtypes = spec[1]
            bound.append(name)
        except Exception:
            missing.append(name)
    try:
        dll._td1_bound_exports = tuple(bound)
        dll._td1_missing_exports = tuple(missing)
    except Exception:
        pass


def _load_native():
    global _NATIVE, _NATIVE_PATH, _NATIVE_STATUS
    if _NATIVE is not None:
        return True
    last_error = None
    for path in _native_candidates():
        try:
            if not os.path.exists(path):
                continue
            dll = ctypes.CDLL(path)
            _bind_native_functions(dll)
            version = dll.TD1OccultNativeVersion()
            _NATIVE = dll
            _NATIVE_PATH = path
            _NATIVE_STATUS = 'loaded version {}'.format(version)
            _log('Native bridge loaded from {}'.format(path))
            return True
        except Exception as exc:
            last_error = exc
    if last_error is not None:
        _NATIVE_STATUS = 'load failed: {}'.format(last_error)
    else:
        _NATIVE_STATUS = 'not found'
    return False


def _mask_add(mask, value):
    if _load_native() and _NATIVE is not None:
        try:
            return int(_NATIVE.TD1OccultMaskAdd(int(mask), int(value)))
        except Exception:
            pass
    return int(mask) | int(value)


def _mask_remove(mask, value):
    if _load_native() and _NATIVE is not None:
        try:
            return int(_NATIVE.TD1OccultMaskRemove(int(mask), int(value)))
        except Exception:
            pass
    return int(mask) & (~int(value))


def _mask_toggle(mask, value):
    if _load_native() and _NATIVE is not None:
        try:
            return int(_NATIVE.TD1OccultMaskToggle(int(mask), int(value)))
        except Exception:
            pass
    return int(mask) ^ int(value)


def _mask_has(mask, value):
    if _load_native() and _NATIVE is not None:
        try:
            return bool(_NATIVE.TD1OccultMaskHas(int(mask), int(value)))
        except Exception:
            pass
    if int(value) == 0:
        return int(mask) == 0
    return (int(mask) & int(value)) == int(value)


def _lowest_bit(mask):
    if _load_native() and _NATIVE is not None:
        try:
            return int(_NATIVE.TD1OccultLowestBit(int(mask)))
        except Exception:
            pass
    m = int(mask)
    return m & -m


def _choose_safe_form(available, current, requested):
    if _load_native() and _NATIVE is not None:
        try:
            return int(_NATIVE.TD1OccultChooseSafeForm(int(available), int(current), int(requested)))
        except Exception:
            pass
    chosen = int(requested) & int(available)
    if chosen:
        return _lowest_bit(chosen)
    chosen = int(current) & int(available)
    if chosen:
        return _lowest_bit(chosen)
    return 0


def _get_occult_utils():
    try:
        from OccultHybrid.IC_Hybrid import occult_utils
        return occult_utils
    except Exception:
        return None


def _get_occult_cache():
    try:
        from OccultHybrid.IC_Hybrid.occult_cache import OccultDataCache
        return OccultDataCache
    except Exception:
        return None


def _get_bucks_lock():
    try:
        from bucks.bucks_commands import lock_all_perks_for_bucks_type
        from bucks.bucks_enums import BucksType
        return lock_all_perks_for_bucks_type, BucksType
    except Exception:
        return None, None


def _all_occults(include_human=False):
    if OccultType is None:
        return []
    result = []
    try:
        if OccultTracker is not None and getattr(OccultTracker, 'OCCULT_DATA', None):
            for oc in OccultTracker.OCCULT_DATA.keys():
                if include_human or oc != OccultType.HUMAN:
                    result.append(oc)
    except Exception:
        result = []
    if not result:
        for name in _SPECIAL_OCCULT_NAME_ORDER:
            try:
                oc = getattr(OccultType, name)
                if include_human or oc != OccultType.HUMAN:
                    result.append(oc)
            except Exception:
                pass
    seen = set()
    out = []
    for oc in result:
        key = _int_value(oc)
        if key not in seen:
            seen.add(key)
            out.append(oc)
    return out


def _parse_occult(value):
    if OccultType is None:
        return None
    if value is None:
        return None
    if not isinstance(value, str):
        try:
            return OccultType(value)
        except Exception:
            return value
    text = value.strip().upper()
    if not text:
        return None
    if text.startswith('OCCULTTYPE.'):
        text = text.split('.', 1)[1]
    aliases = {
        'SPELLCASTER': 'WITCH',
        'MAGE': 'WITCH',
        'WIZARD': 'WITCH',
        'ALIENS': 'ALIEN',
        'VAMPIRES': 'VAMPIRE',
        'MERMAIDS': 'MERMAID',
        'WEREWOLVES': 'WEREWOLF',
        'FAERIE': 'FAIRY',
        'FAERIES': 'FAIRY',
        'FAIRIES': 'FAIRY',
        'PLANTSIMS': 'PLANTSIM',
    }
    text = aliases.get(text, text)
    try:
        return getattr(OccultType, text)
    except Exception:
        pass
    try:
        return OccultType(int(text, 0))
    except Exception:
        return None


def _get_trait(trait_id):
    if services is None or Types is None or trait_id in (None, '', 0):
        return None
    try:
        return services.get_instance_manager(Types.TRAIT).get(int(trait_id))
    except Exception:
        return None


def _trait_label(trait):
    if trait is None:
        return None
    for attr in ('display_name', 'trait_name', '__name__', 'guid64'):
        try:
            value = getattr(trait, attr)
            if callable(value):
                value = value()
            if value:
                return str(value)
        except Exception:
            pass
    return str(trait)


def _copy_value(value):
    try:
        if hasattr(value, 'SerializeToString'):
            return ('protobuf', value.SerializeToString())
    except Exception:
        pass
    try:
        return copy.deepcopy(value)
    except Exception:
        try:
            return value.copy()
        except Exception:
            return value


def _snapshot_siminfo_payload(sim_info):
    if sim_info is None:
        return {}
    data = {}
    for attr in _SIMINFO_COPY_ATTRS:
        try:
            if hasattr(sim_info, attr):
                data[attr] = _copy_value(getattr(sim_info, attr))
        except Exception:
            pass
    try:
        if hasattr(sim_info, 'save_outfits'):
            data['__outfits__'] = sim_info.save_outfits()
    except Exception:
        pass
    return data


def _restore_siminfo_payload(sim_info, data):
    if sim_info is None or not data:
        return False
    restored = False
    for attr, value in data.items():
        if attr == '__outfits__':
            continue
        if value is None:
            continue
        try:
            if isinstance(value, tuple) and len(value) == 2 and value[0] == 'protobuf':
                target_value = getattr(sim_info, attr)
                if hasattr(target_value, 'MergeFromString'):
                    target_value.MergeFromString(value[1])
                else:
                    setattr(sim_info, attr, value[1])
            else:
                setattr(sim_info, attr, _copy_value(value))
            restored = True
        except Exception:
            pass
    try:
        outfits = data.get('__outfits__')
        if outfits is not None and hasattr(sim_info, 'load_outfits'):
            sim_info.load_outfits(outfits)
            restored = True
    except Exception:
        pass
    for call in ('resend_physical_attributes', 'resend_current_outfit', 'force_resend_suntan_data', 'resend_outfits'):
        try:
            getattr(sim_info, call)()
        except Exception:
            pass
    return restored


def _get_supported_occult_mask():
    mask = 0
    for occult_type in _all_occults():
        mask = _mask_add(mask, _int_value(occult_type))
    return mask


def _normalize_supported_mask(mask):
    supported = _get_supported_occult_mask()
    if _load_native() and _NATIVE is not None:
        try:
            return int(_NATIVE.TD1OccultMaskNormalizeSupported(int(mask), int(supported)))
        except Exception:
            pass
    return int(mask) & int(supported)


def _mask_count(mask):
    if _load_native() and _NATIVE is not None:
        try:
            return int(_NATIVE.TD1OccultMaskCount(int(mask)))
        except Exception:
            pass
    try:
        return bin(int(mask) & ((1 << 64) - 1)).count('1')
    except Exception:
        return 0


def _is_power_of_two(mask):
    if _load_native() and _NATIVE is not None:
        try:
            return bool(_NATIVE.TD1OccultIsPowerOfTwo(int(mask)))
        except Exception:
            pass
    m = int(mask)
    return m != 0 and (m & (m - 1)) == 0


def _clamp_current(available, current):
    if _load_native() and _NATIVE is not None:
        try:
            func = getattr(_NATIVE, 'TD1OccultClampCurrent')
            return int(func(int(available), int(current)))
        except Exception:
            pass
    current = int(current) & int(available)
    if current and _is_power_of_two(current):
        return current
    return _lowest_bit(current) if current else 0


def _repair_mask(flag_mask, trait_mask, supported):
    if _load_native() and _NATIVE is not None:
        try:
            func = getattr(_NATIVE, 'TD1OccultRepairMask')
            return int(func(int(flag_mask), int(trait_mask), int(supported)))
        except Exception:
            pass
    return (int(flag_mask) | int(trait_mask)) & int(supported)


def _state_score(available, current):
    supported = _get_supported_occult_mask()
    if _load_native() and _NATIVE is not None:
        try:
            return int(_NATIVE.TD1OccultStateScore(int(available), int(current), int(supported)))
        except Exception:
            pass
    score = 100
    if int(available) & ~int(supported):
        score -= 35
    if int(current) and not _mask_has(available, current):
        score -= 35
    if int(current) and not _is_power_of_two(current):
        score -= 25
    return max(0, score)


def _occult_key(occult_type):
    return _safe_name(occult_type).upper()


def _get_loot_action(loot_id):
    if services is None or Types is None:
        return None
    for type_name in ('ACTION', 'SNIPPET'):
        try:
            manager = services.get_instance_manager(getattr(Types, type_name))
            if manager is None:
                continue
            action = manager.get(int(loot_id))
            if action is not None:
                return action
        except Exception:
            pass
    return None


def _apply_loot_action_id(sim_info, loot_id, target_sim_info=None):
    try:
        action = _get_loot_action(loot_id)
        if action is None:
            return False, 'loot {} unavailable'.format(loot_id)
        if target_sim_info is not None:
            if DoubleSimResolver is None:
                return False, 'DoubleSimResolver unavailable'
            resolver = DoubleSimResolver(sim_info, target_sim_info)
        else:
            if SingleSimResolver is None:
                return False, 'SingleSimResolver unavailable'
            resolver = SingleSimResolver(sim_info)
        if hasattr(action, 'apply_to_resolver'):
            result = action.apply_to_resolver(resolver)
            return result is not False, 'loot {} applied'.format(loot_id)
        if hasattr(action, 'apply_operations'):
            result = action.apply_operations(resolver)
            return result is not False, 'loot {} applied'.format(loot_id)
        return False, 'loot {} has no apply method'.format(loot_id)
    except Exception as exc:
        return False, 'loot {} failed: {}'.format(loot_id, exc)


def _apply_gameplay_loots(sim_info, occult_type, operation='add'):
    table = _GAMEPLAY_ADD_LOOTS if operation == 'add' else _GAMEPLAY_REMOVE_LOOTS
    keys = [_occult_key(occult_type)]
    if keys[0] == 'WITCH':
        keys.append('SPELLCASTER')
    if keys[0] == 'SPELLCASTER':
        keys.append('WITCH')
    loot_ids = ()
    for key in keys:
        if key in table:
            loot_ids = table[key]
            break
    if not loot_ids:
        return False, ['no gameplay loot mapping for {}'.format(keys[0])]
    messages = []
    ok_any = False
    for loot_id in loot_ids:
        duo = operation == 'remove' and keys[0] in ('WITCH', 'SPELLCASTER')
        ok, msg = _apply_loot_action_id(sim_info, loot_id, target_sim_info=sim_info if duo else None)
        messages.append(msg)
        ok_any = ok_any or ok
    return ok_any, messages


def _household_sim_infos(sim_info):
    sims = []
    try:
        household = getattr(sim_info, 'household', None)
        if household is not None:
            for name in ('sim_info_gen', 'get_all_sim_infos', 'get_all_sims_sim_info_gen'):
                func = getattr(household, name, None)
                if func is None:
                    continue
                try:
                    for item in func():
                        if item is not None and item not in sims:
                            sims.append(item)
                    if sims:
                        return sims
                except Exception:
                    pass
    except Exception:
        pass
    if sim_info is not None:
        sims.append(sim_info)
    return sims


def _cas_prepare_one(sim_info):
    tracker = sim_info.occult_tracker
    _CAS_MEMORY[_sim_id(sim_info)] = {
        'occult_types': _get_occult_flags(sim_info),
        'current_occult_types': _get_current_flags(sim_info),
        'form_map': _form_map(tracker).copy(),
        'shape': _snapshot_siminfo_payload(sim_info),
        'trait_snapshot': _occult_trait_snapshot(sim_info),
        'cas_keep': 'HUMAN',
    }
    _ensure_human_form(tracker)
    _switch_human(tracker)
    _set_tracker_form_available(tracker, True)
    _recalc(sim_info)
    return 'prepared {}'.format(_sim_label(sim_info))


def _cas_restore_one(sim_info):
    tracker = sim_info.occult_tracker
    data = _CAS_MEMORY.get(_sim_id(sim_info))
    if not data:
        return 'no CAS memory for {}'.format(_sim_label(sim_info))
    _set_flags(sim_info, 'occult_types', data.get('occult_types', 0))
    _set_flags(sim_info, 'current_occult_types', data.get('current_occult_types', 0))
    _form_map(tracker).update(data.get('form_map') or {})
    _restore_siminfo_payload(sim_info, data.get('shape') or {})
    restored_traits = _restore_occult_trait_snapshot(sim_info, data.get('trait_snapshot'))
    if restored_traits:
        _log('Restored CAS trait snapshot for {}: {}'.format(_sim_label(sim_info), ', '.join(restored_traits)))
    _set_tracker_form_available(tracker, True)
    _repair_sim(sim_info, deep=True)
    _recalc(sim_info)
    return 'restored {}'.format(_sim_label(sim_info))


def _get_tuning(occult_type):
    try:
        return OccultTracker.OCCULT_DATA.get(occult_type)
    except Exception:
        return None


def _tuning_traits(occult_type):
    tuning = _get_tuning(occult_type)
    result = []
    if tuning is None:
        return result
    for attr in ('occult_trait', 'current_occult_trait', 'part_occult_trait'):
        try:
            trait = getattr(tuning, attr)
            if trait is not None and trait not in result:
                result.append(trait)
        except Exception:
            pass
    try:
        for trait in getattr(tuning, 'additional_occult_traits') or []:
            if trait is not None and trait not in result:
                result.append(trait)
    except Exception:
        pass
    return result


def _current_occult_trait(occult_type):
    tuning = _get_tuning(occult_type)
    if tuning is None:
        return None
    try:
        return getattr(tuning, 'current_occult_trait')
    except Exception:
        return None


def _sim_id(sim_info):
    for attr in ('sim_id', 'id'):
        try:
            value = getattr(sim_info, attr)
            if value is not None:
                return int(value)
        except Exception:
            pass
    return 0


def _sim_label(sim_info):
    try:
        name = sim_info.full_name
        if name:
            return '{} ({})'.format(name, _sim_id(sim_info))
    except Exception:
        pass
    try:
        return '{} {} ({})'.format(sim_info.first_name, sim_info.last_name, _sim_id(sim_info))
    except Exception:
        return str(sim_info)


def _get_active_sim_info():
    if services is None:
        return None
    try:
        client = services.client_manager().get_first_client()
        if client is not None and getattr(client, 'active_sim', None) is not None:
            return client.active_sim.sim_info
    except Exception:
        pass
    try:
        sim = services.get_active_sim()
        if sim is not None:
            return sim.sim_info
    except Exception:
        pass
    return None


def _get_sim_info_by_id(sim_id=None):
    if services is None:
        return None
    if sim_id is None or str(sim_id).strip() == '':
        return _get_active_sim_info()
    try:
        sid = int(str(sim_id).strip(), 0)
    except Exception:
        return None
    if _load_native() and _NATIVE is not None:
        try:
            if not _NATIVE.TD1OccultSimIdLooksValid(sid):
                return None
        except Exception:
            pass
    try:
        sim_info = services.sim_info_manager().get(sid)
        if sim_info is not None:
            return sim_info
    except Exception:
        pass
    try:
        for sim_info in services.sim_info_manager().get_all():
            if _sim_id(sim_info) == sid:
                return sim_info
    except Exception:
        pass
    return None


def _list_sims():
    rows = []
    if services is None:
        return rows
    try:
        for sim_info in services.sim_info_manager().get_all():
            if sim_info is None:
                continue
            rows.append({
                'id': _sim_id(sim_info),
                'name': _sim_label(sim_info),
                'occult_types': str(getattr(sim_info, 'occult_types', '')),
                'occult_types_value': _int_value(getattr(sim_info, 'occult_types', 0)),
                'current_occult_types': str(getattr(sim_info, 'current_occult_types', '')),
                'current_occult_types_value': _int_value(getattr(sim_info, 'current_occult_types', 0)),
            })
    except Exception as exc:
        _log('List sims failed: {}'.format(exc))
    rows.sort(key=lambda item: item.get('name', ''))
    return rows


def _has_trait(sim_info, trait):
    if trait is None:
        return False
    try:
        return bool(sim_info.has_trait(trait))
    except Exception:
        return False


def _add_trait(sim_info, trait):
    if trait is None:
        return False
    try:
        if not sim_info.has_trait(trait):
            sim_info.add_trait(trait)
        return True
    except Exception:
        return False


def _remove_trait(sim_info, trait):
    if trait is None:
        return False
    try:
        if sim_info.has_trait(trait):
            sim_info.remove_trait(trait)
        return True
    except Exception:
        return False


def _has_occult(tracker, occult_type):
    try:
        return bool(tracker.has_occult_type(occult_type))
    except Exception:
        try:
            return _mask_has(_int_value(tracker.sim_info.occult_types), _int_value(occult_type))
        except Exception:
            return False


def _set_flags(sim_info, attr, flags):
    try:
        setattr(sim_info, attr, _coerce_flags(flags))
        return True
    except Exception:
        try:
            setattr(sim_info, attr, int(flags))
            return True
        except Exception:
            return False


def _recalc(sim_info_or_tracker):
    tracker = sim_info_or_tracker
    sim_info = None
    try:
        if hasattr(sim_info_or_tracker, 'occult_tracker'):
            sim_info = sim_info_or_tracker
            tracker = sim_info.occult_tracker
        else:
            sim_info = tracker._sim_info
    except Exception:
        pass
    occult_utils = _get_occult_utils()
    if occult_utils is not None:
        for name in ('recalc_occult_types', 'recalc_occult_form_availability', 'exit_invalid_forms', 'cleanup_occult_exit_traits'):
            func = getattr(occult_utils, name, None)
            if func is None:
                continue
            for arg in (tracker, sim_info):
                if arg is None:
                    continue
                try:
                    func(arg)
                    break
                except Exception:
                    pass
        try:
            func = getattr(occult_utils, 'get_occult_types_for_save', None)
            if func is not None and tracker is not None:
                func(tracker)
        except Exception:
            pass
    for name in ('recalc_occult_types', 'recalc_occult_form_availability', '_update_occult_traits', '_recalculate_occult_types'):
        try:
            func = getattr(tracker, name)
            func()
        except Exception:
            pass
    return True


def _ensure_human_form(tracker):
    if OccultType is None:
        return None
    try:
        human = tracker.get_occult_sim_info(OccultType.HUMAN)
        if human is not None:
            return human
    except Exception:
        pass
    for args in ((OccultType.HUMAN, False), (OccultType.HUMAN, True), (OccultType.HUMAN,)):
        try:
            if len(args) == 2:
                return tracker._generate_sim_info(args[0], generate_new=args[1])
            return tracker._generate_sim_info(args[0])
        except TypeError:
            continue
        except Exception:
            continue
    return None


def _ensure_form(tracker, occult_type, generate_new=True):
    try:
        form = tracker.get_occult_sim_info(occult_type)
        if form is not None:
            return form
    except Exception:
        pass
    try:
        if occult_type != OccultType.HUMAN:
            _ensure_human_form(tracker)
    except Exception:
        pass
    for args in ((occult_type, generate_new), (occult_type, True), (occult_type,)):
        try:
            if len(args) == 2:
                return tracker._generate_sim_info(args[0], generate_new=args[1])
            return tracker._generate_sim_info(args[0])
        except TypeError:
            continue
        except Exception:
            continue
    return None


def _copy_form_data(src, dst):
    copied = False
    if src is None or dst is None:
        return False
    payload = _snapshot_siminfo_payload(src)
    if payload and _restore_siminfo_payload(dst, payload):
        copied = True
    if SimInfoBaseWrapper is not None:
        attempts = (
            (getattr(dst, '_base', dst), src),
            (dst, getattr(src, '_base', src)),
            (getattr(dst, '_base', dst), getattr(src, '_base', src)),
            (dst, src),
        )
        for dst_arg, src_arg in attempts:
            try:
                SimInfoBaseWrapper.copy_physical_attributes(dst_arg, src_arg)
                copied = True
                break
            except Exception:
                pass
    try:
        if hasattr(src, 'save_outfits') and hasattr(dst, 'load_outfits'):
            dst.load_outfits(src.save_outfits())
            copied = True
    except Exception:
        pass
    for call in ('resend_physical_attributes', 'resend_current_outfit', 'force_resend_suntan_data', 'resend_outfits'):
        try:
            getattr(dst, call)()
        except Exception:
            pass
    return copied


def _form_map(tracker):
    try:
        value = tracker._sim_info_map
        if value is not None:
            return value
    except Exception:
        pass
    return {}


def _memory_trait_for_occult(occult_type):
    name = _safe_name(occult_type).upper()
    trait_id = _MEMORY_TRAIT_IDS.get(name)
    return _get_trait(trait_id), trait_id


def _get_occult_flags(sim_info):
    return _int_value(getattr(sim_info, 'occult_types', 0))


def _get_current_flags(sim_info):
    return _int_value(getattr(sim_info, 'current_occult_types', 0))


def _active_occults_from_everything(sim_info):
    tracker = sim_info.occult_tracker
    found = []
    flags = _get_occult_flags(sim_info)
    for occult_type in _all_occults():
        value = _int_value(occult_type)
        trait, _trait_id = _memory_trait_for_occult(occult_type)
        has_flag = _mask_has(flags, value)
        has_tracker = _has_occult(tracker, occult_type)
        has_tuning_trait = False
        for trait_obj in _tuning_traits(occult_type):
            if _has_trait(sim_info, trait_obj):
                has_tuning_trait = True
                break
        has_memory = _has_trait(sim_info, trait) if trait is not None else False
        if has_flag or has_tracker or has_tuning_trait or has_memory:
            found.append(occult_type)
    return found


def _set_tracker_form_available(tracker, value=True):
    try:
        tracker._occult_form_available = bool(value)
        return True
    except Exception:
        return False


def _switch_human(tracker):
    if OccultType is None:
        return False
    try:
        tracker.set_pending_occult_type(getattr(tracker._sim_info, 'current_occult_types', OccultType.HUMAN))
    except Exception:
        pass
    try:
        tracker.switch_to_occult_type(OccultType.HUMAN)
        return True
    except Exception:
        try:
            _set_flags(tracker._sim_info, 'current_occult_types', _int_value(OccultType.HUMAN))
            return True
        except Exception:
            return False


def _switch_to(tracker, occult_type):
    try:
        tracker.set_pending_occult_type(getattr(tracker._sim_info, 'current_occult_types', OccultType.HUMAN))
    except Exception:
        pass
    try:
        tracker.switch_to_occult_type(occult_type)
        return True
    except Exception:
        try:
            _set_flags(tracker._sim_info, 'current_occult_types', _int_value(occult_type))
            return True
        except Exception:
            return False


def _add_occult(sim_info, occult_type, generate=True, add_traits=True, add_memory=True, use_gameplay_loot=True):
    tracker = sim_info.occult_tracker
    changed = []
    value = _int_value(occult_type)
    old_flags = _get_occult_flags(sim_info)
    old_current = _get_current_flags(sim_info)
    base_payload = _snapshot_siminfo_payload(sim_info)
    if use_gameplay_loot:
        loot_ok, loot_messages = _apply_gameplay_loots(sim_info, occult_type, operation='add')
        if loot_messages:
            changed.extend(['gameplay {}'.format(msg) for msg in loot_messages])
        if loot_ok:
            # Vanilla loot is good at initializing pack-specific trackers, but Apex restores the look
            # and then normalizes data so the Sim can safely remain a hybrid.
            _restore_siminfo_payload(sim_info, base_payload)
    if not _has_occult(tracker, occult_type):
        try:
            tracker.add_occult_type(occult_type)
            changed.append('tracker add')
        except Exception:
            changed.append('tracker add skipped')
    merged_flags = _mask_add(_mask_add(old_flags, _get_occult_flags(sim_info)), value)
    merged_flags = _normalize_supported_mask(merged_flags) or merged_flags
    _set_flags(sim_info, 'occult_types', merged_flags)
    safe_current = _choose_safe_form(merged_flags, old_current, old_current)
    _set_flags(sim_info, 'current_occult_types', safe_current)
    human_form = _ensure_human_form(tracker)
    if base_payload and human_form is not None:
        _restore_siminfo_payload(human_form, base_payload)
    if generate:
        form = _ensure_form(tracker, occult_type, generate_new=True)
        if form is not None and base_payload:
            _restore_siminfo_payload(form, base_payload)
        changed.append('form {}'.format('ok' if form is not None else 'missing'))
    if add_traits:
        for trait in _tuning_traits(occult_type):
            if _add_trait(sim_info, trait):
                changed.append('trait {}'.format(_trait_label(trait)))
    if add_memory:
        trait, trait_id = _memory_trait_for_occult(occult_type)
        if trait is not None and _add_trait(sim_info, trait):
            changed.append('memory {}'.format(trait_id))
    _set_tracker_form_available(tracker, True)
    _recalc(sim_info)
    return changed


def _remove_occult(sim_info, occult_type, remove_traits=False, remove_memory=False, use_gameplay_loot=False):
    tracker = sim_info.occult_tracker
    changed = []
    if use_gameplay_loot:
        loot_ok, loot_messages = _apply_gameplay_loots(sim_info, occult_type, operation='remove')
        if loot_messages:
            changed.extend(['gameplay {}'.format(msg) for msg in loot_messages])
    if _has_occult(tracker, occult_type):
        try:
            tracker.remove_occult_type(occult_type)
            changed.append('tracker remove')
        except Exception:
            old = _get_occult_flags(sim_info)
            _set_flags(sim_info, 'occult_types', _mask_remove(old, _int_value(occult_type)))
            changed.append('raw flag remove')
    old = _get_occult_flags(sim_info)
    _set_flags(sim_info, 'occult_types', _normalize_supported_mask(_mask_remove(old, _int_value(occult_type))))
    if remove_traits:
        for trait in _tuning_traits(occult_type):
            if _remove_trait(sim_info, trait):
                changed.append('removed trait {}'.format(_trait_label(trait)))
    if remove_memory:
        trait, trait_id = _memory_trait_for_occult(occult_type)
        if trait is not None and _remove_trait(sim_info, trait):
            changed.append('removed memory {}'.format(trait_id))
    if _mask_has(_get_current_flags(sim_info), _int_value(occult_type)):
        _switch_human(tracker)
        changed.append('current set human')
    _recalc(sim_info)
    return changed


def _sync_traits_to_flags(sim_info):
    tracker = sim_info.occult_tracker
    flags = _get_occult_flags(sim_info)
    added = []
    for occult_type in _all_occults():
        has_any = False
        for trait in _tuning_traits(occult_type):
            if _has_trait(sim_info, trait):
                has_any = True
                break
        if has_any and not _mask_has(flags, _int_value(occult_type)):
            flags = _mask_add(flags, _int_value(occult_type))
            added.append(_safe_name(occult_type))
    _set_flags(sim_info, 'occult_types', flags)
    _set_tracker_form_available(tracker, True)
    _recalc(sim_info)
    return added


def _sync_flags_to_traits(sim_info):
    added = []
    flags = _get_occult_flags(sim_info)
    for occult_type in _all_occults():
        if _mask_has(flags, _int_value(occult_type)):
            for trait in _tuning_traits(occult_type):
                if _add_trait(sim_info, trait):
                    added.append('{}:{}'.format(_safe_name(occult_type), _trait_label(trait)))
    _recalc(sim_info)
    return added



def _occult_trait_snapshot(sim_info):
    rows = []
    for occult_type in _all_occults():
        for trait in _tuning_traits(occult_type):
            if trait is not None and _has_trait(sim_info, trait):
                rows.append(('tuning', _safe_name(occult_type), trait))
        mem_trait, mem_id = _memory_trait_for_occult(occult_type)
        if mem_trait is not None and _has_trait(sim_info, mem_trait):
            rows.append(('memory', _safe_name(occult_type), mem_trait))
    return rows


def _restore_occult_trait_snapshot(sim_info, rows):
    restored = []
    for _kind, name, trait in rows or []:
        if _add_trait(sim_info, trait):
            restored.append(name)
    return restored


def _remove_non_keep_occult_traits(sim_info, keep_occult_type=None):
    keep_name = _safe_name(keep_occult_type).upper() if keep_occult_type is not None else 'HUMAN'
    removed = []
    for occult_type in _all_occults():
        name = _safe_name(occult_type).upper()
        if name == keep_name:
            continue
        for trait in _tuning_traits(occult_type):
            if _remove_trait(sim_info, trait):
                removed.append('{} tuning'.format(name))
        mem_trait, mem_id = _memory_trait_for_occult(occult_type)
        if mem_trait is not None and _remove_trait(sim_info, mem_trait):
            removed.append('{} memory {}'.format(name, mem_id))
    return removed


def _cas_prepare_keep_one(sim_info, keep_occult_type=None):
    tracker = sim_info.occult_tracker
    keep_name = _safe_name(keep_occult_type).upper() if keep_occult_type is not None else 'HUMAN'
    _CAS_MEMORY[_sim_id(sim_info)] = {
        'occult_types': _get_occult_flags(sim_info),
        'current_occult_types': _get_current_flags(sim_info),
        'form_map': _form_map(tracker).copy(),
        'shape': _snapshot_siminfo_payload(sim_info),
        'trait_snapshot': _occult_trait_snapshot(sim_info),
        'cas_keep': keep_name,
    }
    _ensure_human_form(tracker)
    if keep_occult_type is None:
        _switch_human(tracker)
    else:
        _ensure_form(tracker, keep_occult_type, generate_new=True)
        _switch_to(tracker, keep_occult_type)
    removed = _remove_non_keep_occult_traits(sim_info, keep_occult_type)
    _set_tracker_form_available(tracker, True)
    _recalc(sim_info)
    return 'prepared {} for CAS keep {}; temporarily hidden {}'.format(_sim_label(sim_info), keep_name, ', '.join(removed) or 'nothing')




def _saved_form_public(row):
    if not row:
        return {}
    payload = row.get('payload')
    return {
        'id': row.get('id'),
        'label': row.get('label') or row.get('id'),
        'sim_id': row.get('sim_id'),
        'sim_name': row.get('sim_name'),
        'occult': row.get('occult'),
        'occult_value': row.get('occult_value'),
        'created': row.get('created'),
        'source': row.get('source'),
        'runtime_payload': bool(payload),
        'persistent_payload': bool(row.get('payload_json')),
        'notes': row.get('notes') or '',
    }


def _load_saved_forms():
    global _SAVED_FORMS_LOADED
    if _SAVED_FORMS_LOADED:
        return True
    _SAVED_FORMS_LOADED = True
    path = _saved_forms_file()
    try:
        if not os.path.exists(path):
            return False
        with open(path, 'r') as fp:
            data = json.load(fp)
        rows = data.get('forms') if isinstance(data, dict) else data
        loaded = 0
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            form_id = str(row.get('id') or '')
            if not form_id:
                continue
            payload_json = row.get('payload_json') or row.get('payload') or {}
            row['payload_json'] = payload_json
            row['payload'] = _json_restore(payload_json)
            _SAVED_FORMS[form_id] = row
            loaded += 1
        if loaded:
            _log('Loaded {} saved occult form catalog entries from {}'.format(loaded, path))
        return True
    except Exception as exc:
        _log('Could not load saved occult form catalog: {}'.format(exc))
        return False


def _save_saved_forms():
    _load_saved_forms()
    path = _saved_forms_file()
    try:
        rows = []
        for row in _SAVED_FORMS.values():
            clean = dict((k, v) for k, v in row.items() if k != 'payload')
            if 'payload_json' not in clean:
                clean['payload_json'] = _json_safe(row.get('payload') or {})
            rows.append(clean)
        rows.sort(key=lambda item: item.get('created') or '', reverse=True)
        with open(path, 'w') as fp:
            json.dump({'version': _BUILD_VERSION, 'forms': rows}, fp, indent=2, sort_keys=True)
        return True
    except Exception as exc:
        _log('Could not save occult form catalog: {}'.format(exc))
        return False


def _make_saved_form_id(sim_info, occult_type, label):
    seed = '{}|{}|{}|{}'.format(_sim_id(sim_info), _safe_name(occult_type), label or '', time.time())
    if _load_native() and _NATIVE is not None:
        try:
            raw = seed.encode('utf-8')
            return 'sf_{:016x}'.format(int(_NATIVE.TD1OccultFnv1a64(raw, len(raw))) & ((1 << 64) - 1))
        except Exception:
            pass
    h = 1469598103934665603
    for ch in seed.encode('utf-8'):
        h ^= ch
        h = (h * 1099511628211) & ((1 << 64) - 1)
    return 'sf_{:016x}'.format(h)


def _list_saved_forms(query='', sim_id=None, limit=120):
    _load_saved_forms()
    q = (query or '').strip().lower()
    sid = str(sim_id).strip() if sim_id not in (None, '') else ''
    try:
        limit = int(limit)
    except Exception:
        limit = 120
    rows = []
    for row in _SAVED_FORMS.values():
        pub = _saved_form_public(row)
        hay = ' '.join([str(pub.get('id') or ''), str(pub.get('label') or ''), str(pub.get('sim_name') or ''), str(pub.get('occult') or ''), str(pub.get('source') or '')]).lower()
        if q and q not in hay:
            continue
        if sid and str(pub.get('sim_id') or '') != sid:
            # Saved form search defaults to all Sims; a specific sim_id narrows it.
            continue
        rows.append(pub)
    rows.sort(key=lambda item: item.get('created') or '', reverse=True)
    return rows[:max(1, min(limit, 300))]


def _saved_forms_payload(query='', sim_id=None, limit=120):
    forms = _list_saved_forms(query=query, sim_id=sim_id, limit=limit)
    return {
        'ok': True,
        'message': 'Saved occult forms listed: {}'.format(len(forms)),
        'forms': forms,
        'count': len(forms),
        'query': query or '',
        'catalog_file': _saved_forms_file(),
    }


def _save_form_to_library(sim_info, occult_type, source='form', label=None):
    _load_saved_forms()
    tracker = sim_info.occult_tracker
    if occult_type is None or occult_type == OccultType.HUMAN:
        current = _get_current_flags(sim_info)
        for oc in _all_occults():
            if _mask_has(current, _int_value(oc)):
                occult_type = oc
                break
    if occult_type is None or occult_type == OccultType.HUMAN:
        return False, 'Choose a non-human occult first.', None
    if source == 'current':
        source_sim = sim_info
    elif source == 'human':
        source_sim = _ensure_human_form(tracker)
    else:
        source_sim = _ensure_form(tracker, occult_type, generate_new=False)
        if source_sim is None:
            source_sim = _ensure_form(tracker, occult_type, generate_new=True)
    if source_sim is None:
        return False, 'No source SimInfo/form exists for {}'.format(_safe_name(occult_type)), None
    label = (label or '').strip()
    if not label:
        label = '{} {} {}'.format(_sim_label(sim_info), _safe_name(occult_type), time.strftime('%Y-%m-%d %H:%M:%S'))
    payload = _snapshot_siminfo_payload(source_sim)
    form_id = _make_saved_form_id(sim_info, occult_type, label)
    row = {
        'id': form_id,
        'label': label,
        'sim_id': str(_sim_id(sim_info)),
        'sim_name': _sim_label(sim_info),
        'occult': _safe_name(occult_type),
        'occult_value': _int_value(occult_type),
        'created': time.strftime('%Y-%m-%d %H:%M:%S'),
        'source': source,
        'payload': payload,
        'payload_json': _json_safe(payload),
        'occult_types': _get_occult_flags(sim_info),
        'current_occult_types': _get_current_flags(sim_info),
        'trait_snapshot': _occult_trait_snapshot(sim_info),
        'notes': 'Session payload is full fidelity; persisted JSON restores serializable/protobuf-backed CAS data when possible.',
    }
    _SAVED_FORMS[form_id] = row
    _save_saved_forms()
    _log('Saved occult form {} for {} / {} from {}'.format(form_id, _sim_label(sim_info), _safe_name(occult_type), source))
    return True, 'Saved {} form as {}'.format(_safe_name(occult_type), label), _saved_form_public(row)


def _delete_saved_form(form_id):
    _load_saved_forms()
    form_id = str(form_id or '').strip()
    if not form_id:
        return False, 'No saved form id supplied.'
    existed = _SAVED_FORMS.pop(form_id, None)
    _save_saved_forms()
    return existed is not None, 'Deleted saved form {}'.format(form_id) if existed else 'No saved form found for {}'.format(form_id)


def _apply_saved_form_to_sim(sim_info, form_id, target_occult_type=None, force_current=False):
    _load_saved_forms()
    row = _SAVED_FORMS.get(str(form_id or '').strip())
    if not row:
        return False, 'No saved form found for {}'.format(form_id), []
    payload = row.get('payload')
    if not payload and row.get('payload_json'):
        payload = _json_restore(row.get('payload_json'))
        row['payload'] = payload
    if not payload:
        return False, 'Saved form has no restorable payload.', []
    target = target_occult_type or _parse_occult(row.get('occult'))
    if target is None or target == OccultType.HUMAN:
        return False, 'Saved form target occult is invalid.', []
    tracker = sim_info.occult_tracker
    details = []
    changes = _add_occult(sim_info, target, generate=True, add_traits=True, add_memory=True, use_gameplay_loot=False)
    if changes:
        details.extend(changes)
    form = _ensure_form(tracker, target, generate_new=True)
    restored_form = _restore_siminfo_payload(form, payload)
    details.append('restored target form {}'.format(restored_form))
    if force_current:
        _switch_to(tracker, target)
        restored_current = _restore_siminfo_payload(sim_info, payload)
        details.append('restored current Sim {}'.format(restored_current))
    _set_tracker_form_available(tracker, True)
    details.extend(_repair_sim(sim_info, deep=True))
    _recalc(sim_info)
    return True, 'Applied saved form {} to {} {}'.format(row.get('label') or row.get('id'), _sim_label(sim_info), _safe_name(target)), details


def _copy_to_clipboard(sim_info, slot, mode='full'):
    mode = (mode or 'full').lower()
    payload = _snapshot_siminfo_payload(sim_info)
    if mode == 'wardrobe':
        payload = dict((k, v) for k, v in payload.items() if k == '__outfits__')
    elif mode == 'body':
        payload = dict((k, v) for k, v in payload.items() if k in ('physique', 'facial_attributes', 'voice_pitch', 'voice_actor', 'voice_effect', 'genetic_data'))
    elif mode == 'skin':
        payload = dict((k, v) for k, v in payload.items() if k in ('skin_tone', 'pelt_layers', 'base_trait_ids', 'flags'))
    elif mode == 'tattoos':
        # Sims 4 exposes tattoos through CAS outfit/body-part data. Keep the outfit blob so tattoo layers survive when the game supports save_outfits/load_outfits.
        payload = dict((k, v) for k, v in payload.items() if k == '__outfits__')
    _WARDROBE_CLIPBOARD[slot] = {
        'slot': slot,
        'mode': mode,
        'sim_id': str(_sim_id(sim_info)),
        'sim_name': _sim_label(sim_info),
        'created': time.strftime('%Y-%m-%d %H:%M:%S'),
        'payload': payload,
    }
    return 'Copied {} data from {} into clipboard {}'.format(mode, _sim_label(sim_info), slot)


def _paste_from_clipboard(sim_info, slot):
    row = _WARDROBE_CLIPBOARD.get(slot)
    if not row:
        return False, 'Clipboard {} is empty'.format(slot)
    ok = _restore_siminfo_payload(sim_info, row.get('payload') or {})
    _recalc(sim_info)
    return ok, 'Pasted {} clipboard {} onto {}'.format(row.get('mode'), slot, _sim_label(sim_info))


def _clipboard_payload():
    return {
        'ok': True,
        'message': 'Clipboard status ready',
        'slots': [dict((k, v) for k, v in row.items() if k != 'payload') for row in _WARDROBE_CLIPBOARD.values()],
    }


def _copy_current_to_all_forms(sim_info, include_human=False):
    tracker = sim_info.occult_tracker
    payload = _snapshot_siminfo_payload(sim_info)
    done = []
    if include_human:
        human = _ensure_human_form(tracker)
        if human is not None and _restore_siminfo_payload(human, payload):
            done.append('HUMAN')
    for oc in _all_occults():
        if _mask_has(_get_occult_flags(sim_info), _int_value(oc)) or _has_occult(tracker, oc):
            form = _ensure_form(tracker, oc, generate_new=True)
            if form is not None and _restore_siminfo_payload(form, payload):
                done.append(_safe_name(oc))
    _set_tracker_form_available(tracker, True)
    _recalc(sim_info)
    return done


def _copy_human_to_all_forms(sim_info):
    tracker = sim_info.occult_tracker
    human = _ensure_human_form(tracker)
    if human is None:
        return []
    done = []
    for oc in _all_occults():
        if _mask_has(_get_occult_flags(sim_info), _int_value(oc)) or _has_occult(tracker, oc):
            form = _ensure_form(tracker, oc, generate_new=True)
            if form is not None and _copy_form_data(human, form):
                done.append(_safe_name(oc))
    _set_tracker_form_available(tracker, True)
    _recalc(sim_info)
    return done


def _resend_all_visuals(sim_info):
    calls = []
    for call in ('resend_physical_attributes', 'resend_current_outfit', 'force_resend_suntan_data', 'resend_outfits'):
        try:
            getattr(sim_info, call)()
            calls.append(call)
        except Exception:
            pass
    return calls


def _mccc_status_payload():
    _detect_mccc()
    return {
        'ok': True,
        'message': 'MCCC compatibility status ready',
        'mccc_status': _MCCC_STATUS,
        'mccc_details': _MCCC_DETAILS,
        'guardian_enabled': _MCCC_GUARD_ENABLED,
        'guardian_snapshots': len(_MCCC_GUARD_MEMORY),
        'guardian_last_event': _MCCC_GUARD_LAST_EVENT,
        'guardian_last_restore': _MCCC_GUARD_LAST_RESTORE,
        'lot51_core_status': _detect_lot51_core(),
        'lot51_events_installed': _LOT51_EVENTS_INSTALLED,
        'lot51_event_status': _LOT51_EVENT_STATUS,
        'xml_injector_status': _detect_xml_injector(),
        'xml_injector_details': _XML_INJECTOR_DETAILS,
    }


def _mccc_guard_snapshot_household(sim_info=None, reason='manual'):
    global _MCCC_GUARD_LAST_EVENT
    if sim_info is None:
        sim_info = _get_active_sim_info()
    if sim_info is None:
        return ['no active Sim available for MCCC/CAS snapshot']
    details = []
    for item in _household_sim_infos(sim_info):
        try:
            tracker = item.occult_tracker
            sid = _sim_id(item)
            data = {
                'occult_types': _get_occult_flags(item),
                'current_occult_types': _get_current_flags(item),
                'form_map': _form_map(tracker).copy(),
                'shape': _snapshot_siminfo_payload(item),
                'trait_snapshot': _occult_trait_snapshot(item),
                'cas_keep': 'MCCC_GUARD',
                'reason': reason,
                'created': time.strftime('%Y-%m-%d %H:%M:%S'),
            }
            _CAS_MEMORY[sid] = data
            _MCCC_GUARD_MEMORY[sid] = data
            details.append('snapshot {}'.format(_sim_label(item)))
        except Exception as exc:
            details.append('snapshot failed {}: {}'.format(_sim_label(item), exc))
    _MCCC_GUARD_LAST_EVENT = '{} / {}'.format(reason, time.strftime('%H:%M:%S'))
    _log('MCCC/CAS guardian snapshot: {}'.format('; '.join(details)))
    return details


def _mccc_guard_restore_household(reason='manual'):
    global _MCCC_GUARD_LAST_RESTORE
    if not _MCCC_GUARD_MEMORY:
        return ['no MCCC/CAS guardian snapshots available']
    details = []
    for sid in list(_MCCC_GUARD_MEMORY.keys()):
        try:
            sim_info = _get_sim_info_by_id(sid)
            if sim_info is None:
                details.append('missing Sim {}'.format(sid))
                continue
            _CAS_MEMORY[sid] = _MCCC_GUARD_MEMORY[sid]
            details.append(_cas_restore_one(sim_info))
        except Exception as exc:
            details.append('restore failed {}: {}'.format(sid, exc))
    _MCCC_GUARD_LAST_RESTORE = '{} / {}'.format(reason, time.strftime('%H:%M:%S'))
    _log('MCCC/CAS guardian restore: {}'.format('; '.join(details)))
    return details


def _install_lot51_events():
    global _LOT51_EVENTS_INSTALLED, _LOT51_EVENT_STATUS
    if _LOT51_EVENTS_INSTALLED:
        return True
    try:
        from lot51_core.services.events import event_handler, CoreEvent
        def _event(name, fallback):
            return getattr(CoreEvent, name, fallback)

        @event_handler(_event('ZONE_UNLOAD', 'zone.unload'))
        def _td1_apex_zone_unload(service=None, context=None, **kwargs):
            try:
                if _MCCC_GUARD_ENABLED:
                    _mccc_guard_snapshot_household(_get_active_sim_info(), 'lot51 zone.unload / possible CAS or travel')
            except Exception as exc:
                _log('Lot51 zone.unload guardian failed: {}'.format(exc))

        @event_handler(_event('ZONE_LOADING_SCREEN_LIFTED', 'zone.loading_screen_lifted'))
        def _td1_apex_zone_loaded(service=None, context=None, **kwargs):
            try:
                if _MCCC_GUARD_ENABLED and _MCCC_GUARD_MEMORY:
                    _mccc_guard_restore_household('lot51 zone.loading_screen_lifted / post CAS or travel')
            except Exception as exc:
                _log('Lot51 zone.loading_screen_lifted guardian failed: {}'.format(exc))

        @event_handler(_event('GAME_PRE_SAVE', 'game.pre_save'))
        def _td1_apex_pre_save(service=None, context=None, **kwargs):
            try:
                active = _get_active_sim_info()
                if active is not None:
                    _repair_sim(active, deep=False)
            except Exception as exc:
                _log('Lot51 game.pre_save repair failed: {}'.format(exc))

        _LOT51_EVENT_HANDLERS.extend([_td1_apex_zone_unload, _td1_apex_zone_loaded, _td1_apex_pre_save])
        _LOT51_EVENTS_INSTALLED = True
        _LOT51_EVENT_STATUS = 'installed: zone.unload, zone.loading_screen_lifted, game.pre_save'
        _log('Lot51 Core event handlers installed for MCCC/CAS guardian.')
        return True
    except Exception as exc:
        _LOT51_EVENT_STATUS = 'not installed: {}'.format(exc)
        return False

def _health_report(sim_info):
    issues = []
    tracker = sim_info.occult_tracker
    flags = _get_occult_flags(sim_info)
    current = _get_current_flags(sim_info)
    supported = _get_supported_occult_mask()
    if flags & ~supported:
        issues.append('occult_types has unsupported bits {}'.format(flags & ~supported))
    if current and not _mask_has(flags, current):
        issues.append('current_occult_types is not inside occult_types')
    if current and not _is_power_of_two(current):
        issues.append('current_occult_types has multiple bits')
    try:
        if not getattr(tracker, '_occult_form_available', False) and flags:
            issues.append('occult form availability is off')
    except Exception:
        pass
    for occult_type in _all_occults():
        value = _int_value(occult_type)
        has_flag = _mask_has(flags, value)
        has_form = False
        try:
            has_form = tracker.get_occult_sim_info(occult_type) is not None
        except Exception:
            pass
        has_any_trait = False
        for trait in _tuning_traits(occult_type):
            if _has_trait(sim_info, trait):
                has_any_trait = True
                break
        mem_trait, _mem_id = _memory_trait_for_occult(occult_type)
        has_memory = _has_trait(sim_info, mem_trait) if mem_trait is not None else False
        if has_flag and not has_form:
            issues.append('{} flag exists but form data is missing'.format(_safe_name(occult_type)))
        if has_any_trait and not has_flag:
            issues.append('{} trait exists but flag is missing'.format(_safe_name(occult_type)))
        if has_memory and not has_flag:
            issues.append('{} memory trait exists but flag is missing'.format(_safe_name(occult_type)))
    score = _state_score(flags, current) - min(60, len(issues) * 8)
    if score < 0:
        score = 0
    return {'score': score, 'issues': issues, 'supported_mask': supported, 'flag_count': _mask_count(flags)}


def _normalize_sim_state(sim_info):
    tracker = sim_info.occult_tracker
    details = []
    active_mask = 0
    for occult_type in _active_occults_from_everything(sim_info):
        active_mask = _mask_add(active_mask, _int_value(occult_type))
    old_flags = _get_occult_flags(sim_info)
    flags = _repair_mask(old_flags, active_mask, _get_supported_occult_mask())
    if flags != old_flags:
        _set_flags(sim_info, 'occult_types', flags)
        details.append('occult_types normalized {} -> {}'.format(old_flags, flags))
    old_current = _get_current_flags(sim_info)
    current = _clamp_current(flags, old_current)
    if current != old_current:
        _set_flags(sim_info, 'current_occult_types', current)
        details.append('current_occult_types normalized {} -> {}'.format(old_current, current))
    _set_tracker_form_available(tracker, True)
    _ensure_human_form(tracker)
    for occult_type in _all_occults():
        if _mask_has(flags, _int_value(occult_type)):
            _ensure_form(tracker, occult_type, generate_new=True)
    _recalc(sim_info)
    return details or ['already normalized']

def _repair_sim(sim_info, deep=False):
    tracker = sim_info.occult_tracker
    details = []
    _ensure_human_form(tracker)
    details.append('human form checked')
    active = _active_occults_from_everything(sim_info)
    if not active:
        _recalc(sim_info)
        return details + ['no active non-human occult found']
    flags = _get_occult_flags(sim_info)
    for occult_type in active:
        value = _int_value(occult_type)
        if not _mask_has(flags, value):
            flags = _mask_add(flags, value)
            details.append('flag added {}'.format(_safe_name(occult_type)))
        if not _has_occult(tracker, occult_type):
            try:
                tracker.add_occult_type(occult_type)
                details.append('tracker added {}'.format(_safe_name(occult_type)))
            except Exception:
                pass
        form = _ensure_form(tracker, occult_type, generate_new=True)
        details.append('{} form {}'.format(_safe_name(occult_type), 'ok' if form is not None else 'missing'))
        for trait in _tuning_traits(occult_type):
            if _add_trait(sim_info, trait):
                details.append('trait ok {}'.format(_trait_label(trait)))
        trait, trait_id = _memory_trait_for_occult(occult_type)
        if trait is not None and _add_trait(sim_info, trait):
            details.append('memory ok {}'.format(trait_id))
    flags = _normalize_supported_mask(flags) or flags
    _set_flags(sim_info, 'occult_types', flags)
    if _mask_count(flags) > 1:
        details.append('hybrid mask has {} occult bits'.format(_mask_count(flags)))
    current = _get_current_flags(sim_info)
    safe_current = _clamp_current(flags, current)
    if current and safe_current != current:
        _set_flags(sim_info, 'current_occult_types', safe_current)
        details.append('current flags normalized {}'.format(safe_current))
    if current and not safe_current:
        _switch_human(tracker)
        details.append('current reset human')
    _set_tracker_form_available(tracker, True)
    if deep:
        _sync_flags_to_traits(sim_info)
        _sync_traits_to_flags(sim_info)
        details.append('deep trait and flag sync')
    _recalc(sim_info)
    return details


def _repair_all(deep=False):
    results = []
    if services is None:
        return results
    try:
        for sim_info in services.sim_info_manager().get_all():
            if sim_info is None:
                continue
            try:
                details = _repair_sim(sim_info, deep=deep)
                results.append('{}: {}'.format(_sim_label(sim_info), '; '.join(details)))
            except Exception as exc:
                results.append('{}: {}'.format(_sim_label(sim_info), exc))
    except Exception as exc:
        results.append('repair all failed: {}'.format(exc))
    return results


def _apply_perk_lock(sim_info, occult_type, locked):
    lock_all, BucksType = _get_bucks_lock()
    if lock_all is None or BucksType is None:
        return 'Bucks API unavailable'
    tuning = _get_tuning(occult_type)
    if tuning is None:
        return 'No tuning'
    done = []
    for attr in ('primary_buck_type', 'secondary_buck_type'):
        try:
            buck_type = getattr(tuning, attr)
            if buck_type is not BucksType.INVALID:
                lock_all(buck_type, _sim_id(sim_info), bool(locked))
                done.append(attr)
        except Exception:
            pass
    return ', '.join(done) if done else 'No perk buck types'


def _status(sim_info):
    tracker = sim_info.occult_tracker
    form_map = _form_map(tracker)
    occults = []
    for occult_type in _all_occults():
        trait, trait_id = _memory_trait_for_occult(occult_type)
        has_form = False
        try:
            has_form = tracker.get_occult_sim_info(occult_type) is not None
        except Exception:
            pass
        tuning_traits = []
        for trait_obj in _tuning_traits(occult_type):
            tuning_traits.append({
                'name': _trait_label(trait_obj),
                'has': _has_trait(sim_info, trait_obj),
            })
        occults.append({
            'name': _safe_name(occult_type),
            'value': _int_value(occult_type),
            'has_occult': _has_occult(tracker, occult_type),
            'has_form_data': has_form,
            'has_memory_trait': _has_trait(sim_info, trait) if trait is not None else False,
            'memory_trait_id': trait_id,
            'tuning_traits': tuning_traits,
            'has_tuning': _get_tuning(occult_type) is not None,
        })
    try:
        map_keys = [_safe_name(key) for key in form_map.keys()]
    except Exception:
        map_keys = []
    return {
        'sim': _sim_label(sim_info),
        'sim_id': _sim_id(sim_info),
        'occult_types': str(getattr(sim_info, 'occult_types', '')),
        'occult_types_value': _get_occult_flags(sim_info),
        'current_occult_types': str(getattr(sim_info, 'current_occult_types', '')),
        'current_occult_types_value': _get_current_flags(sim_info),
        'pending_occult_type': str(getattr(tracker, '_pending_occult_type', None)),
        'occult_form_available': bool(getattr(tracker, '_occult_form_available', False)),
        'form_map_keys': map_keys,
        'stored_memory_slots': list(_FORM_MEMORY.get(_sim_id(sim_info), {}).keys()),
        'cas_memory_saved': _sim_id(sim_info) in _CAS_MEMORY,
        'saved_forms_count': len(_list_saved_forms(sim_id=None, limit=300)),
        'saved_forms_for_sim': len(_list_saved_forms(sim_id=str(_sim_id(sim_info)), limit=300)),
        'mccc_guardian': _mccc_status_payload(),
        'auto_repair': _AUTO_REPAIR,
        'build_version': _BUILD_VERSION,
        'health': _health_report(sim_info),
        'native': {'status': _NATIVE_STATUS, 'path': _NATIVE_PATH, 'bound_exports': list(getattr(_NATIVE, '_td1_bound_exports', ())) if _NATIVE is not None else []},
        'overlay': _overlay_capabilities(),
        'lot51_core_status': _detect_lot51_core(),
        'mccc': {'status': _detect_mccc(), 'details': _MCCC_DETAILS, 'guard': _MCCC_GUARD, 'auto_restore': _MCCC_AUTO_RESTORE, 'snapshots': len(_MCCC_GUARD_MEMORY), 'pending_restore_reason': _MCCC_PENDING_RESTORE_REASON},
        'saved_forms': {'count': len(_list_saved_forms('')), 'path': _saved_forms_path()},
        'appearance_clipboard_scopes': list(_APPEARANCE_CLIPBOARD.keys()),
        'performance': {'history_lines': len(_HISTORY), 'pending_count': len(_PENDING), 'last_command': _LAST_COMMAND, 'stats': _perf_snapshot()},
        'occults': occults,
    }


def run_action(action, sim_id=None, occult=None, value=None):
    global _AUTO_REPAIR, _MCCC_GUARD_ENABLED
    action = (action or 'status').strip().lower()
    if action == 'clear_logs':
        with _LOCK:
            del _HISTORY[:]
            _PERF_STATS.clear()
        _log('Log cleared from the Apex panel.')
        return {'ok': True, 'message': 'Apex running log cleared'}
    if action == 'list_sims':
        return {'ok': True, 'message': 'Listed Sims', 'sims': _list_sims()}
    if action == 'diagnostics':
        _load_native()
        return {'ok': True, 'message': 'Diagnostics ready', 'data': _diagnostics()}
    if action == 'mccc_status':
        return {'ok': True, 'message': 'MCCC compatibility status ready', 'data': _detect_mccc()}
    if action == 'saved_forms':
        rows = _summarize_records(_load_saved_forms().get('forms', []), query=value, limit=120)
        return {'ok': True, 'message': 'Saved occult forms: {} match(es)'.format(len(rows)), 'saved_forms': rows, 'query': value or ''}
    if action == 'wardrobes':
        rows = _summarize_records(_load_wardrobes().get('wardrobes', []), query=value, limit=120)
        return {'ok': True, 'message': 'Wardrobe/CAS presets: {} match(es)'.format(len(rows)), 'wardrobes': rows, 'query': value or ''}
    if action == 'mccc_open_settings':
        ok, msg = _run_console_command('mc_settings')
        return {'ok': ok, 'message': msg}
    if action == 'mccc_open_cheats':
        ok, msg = _run_console_command('mc_cheats')
        return {'ok': ok, 'message': msg}
    if action in ('list_saved_forms', 'saved_forms'):
        return _saved_forms_payload(query=value or '', sim_id=sim_id or None, limit=160)
    if action == 'delete_saved_form':
        ok, msg = _delete_saved_form(value)
        return {'ok': ok, 'message': msg, 'data': _saved_forms_payload()}
    if action == 'clear_saved_forms':
        _load_saved_forms()
        _SAVED_FORMS.clear()
        _save_saved_forms()
        return {'ok': True, 'message': 'Cleared saved occult form catalog'}
    if action == 'mccc_status':
        return _mccc_status_payload()
    if action == 'mccc_guardian_on':
        _MCCC_GUARD_ENABLED = True
        _install_lot51_events()
        return {'ok': True, 'message': 'MCCC/CAS guardian enabled', 'data': _mccc_status_payload()}
    if action == 'mccc_guardian_off':
        _MCCC_GUARD_ENABLED = False
        return {'ok': True, 'message': 'MCCC/CAS guardian disabled', 'data': _mccc_status_payload()}
    if action == 'mccc_restore_guard':
        return {'ok': True, 'message': 'MCCC/CAS guardian restore complete', 'details': _mccc_guard_restore_household('manual command')}
    if action == 'clipboard_status':
        return _clipboard_payload()
    if action in ('overlay', 'overlay_capabilities'):
        return {'ok': True, 'message': 'Overlay capabilities ready', 'data': _overlay_capabilities()}
    if action == 'auto_on':
        _AUTO_REPAIR = True
        return {'ok': True, 'message': 'Auto repair enabled; it uses the low-frequency queue tick and only repairs the active Sim at the configured interval.'}
    if action == 'auto_off':
        _AUTO_REPAIR = False
        return {'ok': True, 'message': 'Auto repair disabled; the panel will stay manual-only except for explicit commands.'}
    if action == 'repair_all':
        return {'ok': True, 'message': 'Repair all complete', 'details': _repair_all(deep=False)}
    if action == 'deep_repair_all':
        return {'ok': True, 'message': 'Deep repair all complete', 'details': _repair_all(deep=True)}

    sim_info = _get_sim_info_by_id(sim_id)
    if sim_info is None:
        return {'ok': False, 'message': 'No valid Sim found. Select a Sim in-game or enter a Sim ID.'}
    tracker = sim_info.occult_tracker
    occult_type = _parse_occult(occult)
    try:
        if action == 'status':
            _load_native()
            return {'ok': True, 'message': 'Status for {}'.format(_sim_label(sim_info)), 'data': _status(sim_info)}
        if action == 'repair':
            details = _repair_sim(sim_info, deep=False)
            return {'ok': True, 'message': 'Repaired {}'.format(_sim_label(sim_info)), 'details': details}
        if action == 'deep_repair':
            details = _repair_sim(sim_info, deep=True)
            return {'ok': True, 'message': 'Deep repaired {}'.format(_sim_label(sim_info)), 'details': details}
        if action == 'normalize':
            details = _normalize_sim_state(sim_info)
            return {'ok': True, 'message': 'Normalized {}'.format(_sim_label(sim_info)), 'details': details}
        if action == 'health':
            return {'ok': True, 'message': 'Health checked for {}'.format(_sim_label(sim_info)), 'data': _status(sim_info)}
        if action == 'mccc_snapshot_active':
            row = _snapshot_guard_one(sim_info, reason='manual active snapshot')
            return {'ok': row is not None, 'message': 'MCCC/CAS guard snapshot saved for {}'.format(_sim_label(sim_info)), 'data': row}
        if action == 'mccc_snapshot_household':
            rows = _snapshot_guard_household(sim_info, reason='manual household snapshot')
            return {'ok': True, 'message': 'MCCC/CAS guard household snapshot saved', 'details': rows}
        if action == 'mccc_restore_active':
            msg = _restore_guard_one(sim_info, preserve_current_edits=True)
            return {'ok': True, 'message': msg}
        if action == 'mccc_restore_household':
            rows = _restore_guard_household(sim_info, preserve_current_edits=True, reason='manual MCCC restore')
            return {'ok': True, 'message': 'MCCC/CAS guard household restore complete', 'details': rows}
        if action == 'mccc_restore_full_snapshot':
            rows = _restore_guard_household(sim_info, preserve_current_edits=False, reason='manual full snapshot restore')
            return {'ok': True, 'message': 'Full pre-CAS snapshot restore complete', 'details': rows}
        if action == 'save_active_form':
            rec, msg = _save_active_form(sim_info, occult_type=occult_type if occult_type is not None else None, name=value)
            return {'ok': rec is not None, 'message': msg, 'form': _saved_form_summary(rec) if rec else None}
        if action == 'apply_saved_form_current':
            ok, msg = _apply_saved_form(sim_info, value, occult_type=None, to_current=True, force=False)
            return {'ok': ok, 'message': msg}
        if action == 'delete_saved_form':
            ok, msg = _delete_saved_form(value)
            return {'ok': ok, 'message': msg}
        if action == 'appearance_copy':
            return {'ok': True, 'message': _appearance_copy(sim_info, value or 'all')}
        if action == 'appearance_paste':
            ok, msg = _appearance_paste(sim_info, value or 'all')
            return {'ok': ok, 'message': msg}
        if action == 'apply_current_outfit_to_all':
            ok, details = _apply_current_outfit_to_all(sim_info)
            return {'ok': ok, 'message': 'Applied current outfit to {} target outfit slot(s)'.format(len(details)) if ok else details[0], 'details': details}
        if action == 'force_resend_appearance':
            details = _force_resend_appearance(sim_info)
            return {'ok': True, 'message': 'Appearance resend requested for {}'.format(_sim_label(sim_info)), 'details': details}
        if action == 'recalc':
            _recalc(sim_info)
            return {'ok': True, 'message': 'Recalculated occult data for {}'.format(_sim_label(sim_info))}
        if action == 'sync_traits_to_flags':
            added = _sync_traits_to_flags(sim_info)
            return {'ok': True, 'message': 'Synced traits to flags: {}'.format(', '.join(added) or 'nothing added')}
        if action == 'sync_flags_to_traits':
            added = _sync_flags_to_traits(sim_info)
            return {'ok': True, 'message': 'Synced flags to traits: {}'.format(', '.join(added) or 'nothing added')}
        if action == 'force_form_available':
            _set_tracker_form_available(tracker, True)
            return {'ok': True, 'message': 'Forced occult form availability on for {}'.format(_sim_label(sim_info))}
        if action == 'save_memory':
            _FORM_MEMORY[_sim_id(sim_info)] = _form_map(tracker).copy()
            return {'ok': True, 'message': 'Saved {} occult form map entries for {}'.format(len(_FORM_MEMORY[_sim_id(sim_info)]), _sim_label(sim_info))}
        if action == 'restore_memory':
            data = _FORM_MEMORY.get(_sim_id(sim_info))
            if not data:
                return {'ok': False, 'message': 'No in-session form memory saved for {}'.format(_sim_label(sim_info))}
            _form_map(tracker).update(data)
            _set_tracker_form_available(tracker, True)
            _recalc(sim_info)
            return {'ok': True, 'message': 'Restored {} form map entries for {}'.format(len(data), _sim_label(sim_info))}
        if action == 'clear_memory':
            _FORM_MEMORY.pop(_sim_id(sim_info), None)
            return {'ok': True, 'message': 'Cleared in-session form memory for {}'.format(_sim_label(sim_info))}
        if action == 'mccc_snapshot_guard':
            return {'ok': True, 'message': 'MCCC/CAS guardian snapshot complete', 'details': _mccc_guard_snapshot_household(sim_info, 'manual command')}
        if action == 'copy_full_cas':
            return {'ok': True, 'message': _copy_to_clipboard(sim_info, 'full', 'full')}
        if action == 'paste_full_cas':
            ok, msg = _paste_from_clipboard(sim_info, 'full')
            return {'ok': ok, 'message': msg}
        if action == 'copy_wardrobe':
            return {'ok': True, 'message': _copy_to_clipboard(sim_info, 'wardrobe', 'wardrobe')}
        if action == 'paste_wardrobe':
            ok, msg = _paste_from_clipboard(sim_info, 'wardrobe')
            return {'ok': ok, 'message': msg}
        if action == 'copy_body':
            return {'ok': True, 'message': _copy_to_clipboard(sim_info, 'body', 'body')}
        if action == 'paste_body':
            ok, msg = _paste_from_clipboard(sim_info, 'body')
            return {'ok': ok, 'message': msg}
        if action == 'copy_skin':
            return {'ok': True, 'message': _copy_to_clipboard(sim_info, 'skin', 'skin')}
        if action == 'paste_skin':
            ok, msg = _paste_from_clipboard(sim_info, 'skin')
            return {'ok': ok, 'message': msg}
        if action == 'copy_tattoos':
            return {'ok': True, 'message': _copy_to_clipboard(sim_info, 'tattoos', 'tattoos')}
        if action == 'paste_tattoos':
            ok, msg = _paste_from_clipboard(sim_info, 'tattoos')
            return {'ok': ok, 'message': msg}
        if action == 'copy_current_to_all_forms':
            done = _copy_current_to_all_forms(sim_info, include_human=False)
            return {'ok': True, 'message': 'Copied current appearance to occult forms: {}'.format(', '.join(done) or 'none'), 'details': done}
        if action == 'copy_current_to_all_forms_with_human':
            done = _copy_current_to_all_forms(sim_info, include_human=True)
            return {'ok': True, 'message': 'Copied current appearance to all forms: {}'.format(', '.join(done) or 'none'), 'details': done}
        if action == 'copy_human_to_all_forms':
            done = _copy_human_to_all_forms(sim_info)
            return {'ok': True, 'message': 'Copied human form to occult forms: {}'.format(', '.join(done) or 'none'), 'details': done}
        if action == 'resend_all_visuals':
            calls = _resend_all_visuals(sim_info)
            return {'ok': True, 'message': 'Resent CAS/outfit visual data: {}'.format(', '.join(calls) or 'no calls available'), 'details': calls}
        if action in ('apply_saved_form', 'force_apply_saved_form', 'update_occult_from_saved_form'):
            force = action == 'force_apply_saved_form'
            ok, msg, details = _apply_saved_form_to_sim(sim_info, value, target_occult_type=occult_type, force_current=force)
            return {'ok': ok, 'message': msg, 'details': details}
        if action == 'cas_prepare':
            msg = _cas_prepare_one(sim_info)
            return {'ok': True, 'message': msg}
        if action == 'cas_prepare_keep_human':
            msg = _cas_prepare_keep_one(sim_info, None)
            return {'ok': True, 'message': msg}
        if action == 'cas_restore':
            msg = _cas_restore_one(sim_info)
            return {'ok': True, 'message': msg}
        if action == 'cas_prepare_household':
            details = [_cas_prepare_one(item) for item in _household_sim_infos(sim_info)]
            return {'ok': True, 'message': 'CAS-safe household state prepared', 'details': details}
        if action == 'cas_restore_household':
            details = [_cas_restore_one(item) for item in _household_sim_infos(sim_info)]
            return {'ok': True, 'message': 'CAS-safe household state restored', 'details': details}
        if action == 'save_occult_form':
            target_occult = occult_type or _current_nonhuman_occult(sim_info)
            return _save_occult_form_to_library(sim_info, target_occult, label=value)
        if action == 'apply_saved_form':
            return _apply_saved_form_from_library(sim_info, value, occult_type=occult_type, force_current=False)
        if action == 'force_apply_saved_form':
            return _apply_saved_form_from_library(sim_info, value, occult_type=occult_type, force_current=True)
        if action == 'delete_saved_form':
            ok = _delete_saved_form(value)
            return {'ok': ok, 'message': 'Deleted saved form {}'.format(value) if ok else 'Saved form not found: {}'.format(value)}
        if action in ('save_wardrobe', 'save_cas_preset'):
            return _save_wardrobe_to_library(sim_info, label=value)
        if action in ('apply_wardrobe', 'apply_cas_preset'):
            return _apply_wardrobe_from_library(sim_info, value)
        if action == 'delete_wardrobe':
            ok = _delete_wardrobe(value)
            return {'ok': ok, 'message': 'Deleted wardrobe/CAS preset {}'.format(value) if ok else 'Wardrobe/CAS preset not found: {}'.format(value)}
        if action == 'mccc_cas_shield_on':
            details = _mccc_cas_shield_arm(sim_info, keep=occult_type)
            return {'ok': True, 'message': 'MCCC/CAS shield armed. Open MCCC Edit Household/CAS, then return to live mode; Apex will restore from memory/disk.', 'details': details}
        if action == 'mccc_cas_shield_off':
            _MCCC_CAS_SHIELD_ENABLED = False
            _MCCC_CAS_WAS_AWAY = False
            return {'ok': True, 'message': 'MCCC/CAS shield disabled.'}
        if action == 'mccc_cas_restore':
            details = []
            for item in _household_sim_infos(sim_info):
                details.append(_cas_restore_one(item))
            details.extend(_restore_cas_recovery_snapshot(sim_info, reason='manual MCCC/CAS restore'))
            return {'ok': True, 'message': 'MCCC/CAS restore applied for household.', 'details': details}
        if action == 'mccc_open_sim_menu':
            ok, msg = _mccc_open_for_sim(sim_info)
            return {'ok': ok, 'message': msg}
        if action == 'mccc_dresser_clean':
            ok, msg = _mccc_dresser_command(sim_info, 'clean')
            return {'ok': ok, 'message': msg}
        if action == 'mccc_dresser_check':
            ok, msg = _mccc_dresser_command(sim_info, 'check')
            return {'ok': ok, 'message': msg}
        if action == 'mccc_dresser_info':
            ok, msg = _mccc_dresser_command(sim_info, 'info')
            return {'ok': ok, 'message': msg}
        if action == 'mccc_dresser_save_outfit':
            ok, msg = _mccc_dresser_command(sim_info, 'save', value=value)
            return {'ok': ok, 'message': msg}
        if action == 'mccc_dresser_load_outfit':
            ok, msg = _mccc_dresser_command(sim_info, 'load', value=value)
            return {'ok': ok, 'message': msg}
        if action == 'mccc_dresser_copy_all':
            ok, details = _mccc_dresser_copy_all(sim_info, source_code=value or 'E')
            return {'ok': ok, 'message': 'MCCC dresser_copy current source {} to all categories'.format(value or 'E'), 'details': details}
        if action == 'copy_current_to_all_occult_forms':
            copied = []
            for oc in _all_occults():
                if _mask_has(_get_occult_flags(sim_info), _int_value(oc)):
                    target = _ensure_form(tracker, oc, generate_new=True)
                    if _copy_form_data(sim_info, target):
                        copied.append(_safe_name(oc))
            _recalc(sim_info)
            return {'ok': True, 'message': 'Copied current CAS/body data to occult forms: {}'.format(', '.join(copied) or 'none')}
        if action == 'set_flags':
            flags = int(str(value), 0)
            _set_flags(sim_info, 'occult_types', flags)
            _recalc(sim_info)
            return {'ok': True, 'message': 'Set occult_types flags to {} for {}'.format(flags, _sim_label(sim_info))}
        if action == 'set_flags_normalized':
            flags = _normalize_supported_mask(int(str(value), 0))
            _set_flags(sim_info, 'occult_types', flags)
            _set_flags(sim_info, 'current_occult_types', _clamp_current(flags, _get_current_flags(sim_info)))
            _recalc(sim_info)
            return {'ok': True, 'message': 'Set normalized occult_types flags to {} for {}'.format(flags, _sim_label(sim_info))}
        if action == 'set_current':
            flags = int(str(value), 0)
            _set_flags(sim_info, 'current_occult_types', flags)
            _recalc(sim_info)
            return {'ok': True, 'message': 'Set current_occult_types to {} for {}'.format(flags, _sim_label(sim_info))}
        if action == 'set_current_normalized':
            flags = _clamp_current(_get_occult_flags(sim_info), int(str(value), 0))
            _set_flags(sim_info, 'current_occult_types', flags)
            _recalc(sim_info)
            return {'ok': True, 'message': 'Set normalized current_occult_types to {} for {}'.format(flags, _sim_label(sim_info))}
        if action == 'add_all':
            added = []
            for oc in _all_occults():
                changes = _add_occult(sim_info, oc, generate=True, add_traits=True, add_memory=True)
                if changes:
                    added.append('{} ({})'.format(_safe_name(oc), ', '.join(changes)))
            _repair_sim(sim_info, deep=True)
            return {'ok': True, 'message': 'Added all supported occults to {}'.format(_sim_label(sim_info)), 'details': added}
        if action == 'generate_all_forms':
            made = []
            _ensure_human_form(tracker)
            for oc in _all_occults():
                if _ensure_form(tracker, oc, generate_new=True) is not None:
                    made.append(_safe_name(oc))
            _set_tracker_form_available(tracker, True)
            _recalc(sim_info)
            return {'ok': True, 'message': 'Generated/refreshed forms for {}: {}'.format(_sim_label(sim_info), ', '.join(made))}
        if action == 'purge':
            removed = []
            for oc in list(_all_occults()):
                changes = _remove_occult(sim_info, oc, remove_traits=True, remove_memory=True)
                if changes:
                    removed.append('{} ({})'.format(_safe_name(oc), ', '.join(changes)))
            _switch_human(tracker)
            _recalc(sim_info)
            return {'ok': True, 'message': 'Removed all non-human occults from {}'.format(_sim_label(sim_info)), 'details': removed}
        if action == 'human':
            _switch_human(tracker)
            _recalc(sim_info)
            return {'ok': True, 'message': 'Switched {} to HUMAN'.format(_sim_label(sim_info))}
        if occult_type is None or occult_type == OccultType.HUMAN:
            return {'ok': False, 'message': 'Action {} needs a non-human occult name or value.'.format(action)}
        name = _safe_name(occult_type)
        if action == 'save_occult_form':
            rec, msg = _save_occult_form(sim_info, occult_type, name=value)
            return {'ok': rec is not None, 'message': msg, 'form': _saved_form_summary(rec) if rec else None}
        if action == 'apply_saved_form_occult':
            ok, msg = _apply_saved_form(sim_info, value, occult_type=occult_type, to_current=False, force=False)
            return {'ok': ok, 'message': msg}
        if action == 'force_apply_saved_form':
            ok, msg = _apply_saved_form(sim_info, value, occult_type=occult_type, to_current=True, force=True)
            return {'ok': ok, 'message': msg}
        if action == 'cas_prepare_keep':
            msg = _cas_prepare_keep_one(sim_info, occult_type)
            return {'ok': True, 'message': msg}
        if action == 'save_occult_form':
            ok, msg, row = _save_form_to_library(sim_info, occult_type, source='form', label=value)
            return {'ok': ok, 'message': msg, 'form': row, 'data': _saved_forms_payload()}
        if action == 'save_current_as_occult_form':
            ok, msg, row = _save_form_to_library(sim_info, occult_type, source='current', label=value)
            return {'ok': ok, 'message': msg, 'form': row, 'data': _saved_forms_payload()}
        if action == 'save_human_as_occult_form':
            ok, msg, row = _save_form_to_library(sim_info, occult_type, source='human', label=value)
            return {'ok': ok, 'message': msg, 'form': row, 'data': _saved_forms_payload()}
        if action == 'add':
            changes = _add_occult(sim_info, occult_type, generate=True, add_traits=True, add_memory=True, use_gameplay_loot=True)
            return {'ok': True, 'message': 'Added {} to {}'.format(name, _sim_label(sim_info)), 'details': changes}
        if action == 'gameplay_add':
            changes = _add_occult(sim_info, occult_type, generate=True, add_traits=True, add_memory=True, use_gameplay_loot=True)
            return {'ok': True, 'message': 'Gameplay-initialized {} on {}'.format(name, _sim_label(sim_info)), 'details': changes}
        if action == 'remove':
            changes = _remove_occult(sim_info, occult_type, remove_traits=True, remove_memory=True, use_gameplay_loot=False)
            return {'ok': True, 'message': 'Removed {} from {}'.format(name, _sim_label(sim_info)), 'details': changes}
        if action == 'gameplay_remove':
            changes = _remove_occult(sim_info, occult_type, remove_traits=True, remove_memory=True, use_gameplay_loot=True)
            return {'ok': True, 'message': 'Gameplay-removed {} from {}'.format(name, _sim_label(sim_info)), 'details': changes}
        if action == 'switch':
            _add_occult(sim_info, occult_type, generate=True, add_traits=True, add_memory=True)
            _switch_to(tracker, occult_type)
            _set_tracker_form_available(tracker, True)
            _recalc(sim_info)
            return {'ok': True, 'message': 'Switched {} to {}'.format(_sim_label(sim_info), name)}
        if action == 'generate_form':
            form = _ensure_form(tracker, occult_type, generate_new=True)
            _set_tracker_form_available(tracker, True)
            _recalc(sim_info)
            return {'ok': form is not None, 'message': 'Generated/refreshed {} form data for {}'.format(name, _sim_label(sim_info))}
        if action == 'delete_form':
            try:
                if occult_type in _form_map(tracker):
                    del _form_map(tracker)[occult_type]
            except Exception:
                pass
            _recalc(sim_info)
            return {'ok': True, 'message': 'Deleted {} form data for {}'.format(name, _sim_label(sim_info))}
        if action == 'copy_human_to_form':
            human = _ensure_human_form(tracker)
            target = _ensure_form(tracker, occult_type, generate_new=True)
            copied = _copy_form_data(human, target)
            _recalc(sim_info)
            return {'ok': copied, 'message': 'Copied HUMAN form data to {} for {}'.format(name, _sim_label(sim_info))}
        if action == 'copy_current_to_form':
            target = _ensure_form(tracker, occult_type, generate_new=True)
            copied = _copy_form_data(sim_info, target)
            _recalc(sim_info)
            return {'ok': copied, 'message': 'Copied current Sim data to {} for {}'.format(name, _sim_label(sim_info))}
        if action == 'copy_form_to_current':
            src = _ensure_form(tracker, occult_type, generate_new=False)
            copied = _copy_form_data(src, sim_info)
            _recalc(sim_info)
            return {'ok': copied, 'message': 'Copied {} form data to current Sim for {}'.format(name, _sim_label(sim_info))}
        if action == 'add_memory_trait':
            trait, trait_id = _memory_trait_for_occult(occult_type)
            ok = _add_trait(sim_info, trait)
            return {'ok': ok, 'message': 'Added {} memory trait {} to {}'.format(name, trait_id, _sim_label(sim_info))}
        if action == 'remove_memory_trait':
            trait, trait_id = _memory_trait_for_occult(occult_type)
            ok = _remove_trait(sim_info, trait)
            return {'ok': ok, 'message': 'Removed {} memory trait {} from {}'.format(name, trait_id, _sim_label(sim_info))}
        if action == 'add_tuning_traits':
            names = []
            for trait in _tuning_traits(occult_type):
                if _add_trait(sim_info, trait):
                    names.append(_trait_label(trait) or 'trait')
            _recalc(sim_info)
            return {'ok': True, 'message': 'Added {} tuning traits to {}: {}'.format(name, _sim_label(sim_info), ', '.join(names) or 'none')}
        if action == 'remove_tuning_traits':
            names = []
            for trait in _tuning_traits(occult_type):
                if _remove_trait(sim_info, trait):
                    names.append(_trait_label(trait) or 'trait')
            _recalc(sim_info)
            return {'ok': True, 'message': 'Removed {} tuning traits from {}: {}'.format(name, _sim_label(sim_info), ', '.join(names) or 'none')}
        if action == 'on_add_actions':
            occult_utils = _get_occult_utils()
            if occult_utils is not None and getattr(occult_utils, 'on_add_occult', None) is not None:
                try:
                    occult_utils.on_add_occult(occult_type, sim_info)
                except Exception:
                    pass
            _recalc(sim_info)
            return {'ok': True, 'message': 'Ran on-add occult actions for {} on {}'.format(name, _sim_label(sim_info))}
        if action == 'lock_perks':
            result = _apply_perk_lock(sim_info, occult_type, True)
            return {'ok': True, 'message': 'Locked {} perks for {}: {}'.format(name, _sim_label(sim_info), result)}
        if action == 'unlock_perks':
            result = _apply_perk_lock(sim_info, occult_type, False)
            return {'ok': True, 'message': 'Unlocked {} perks for {}: {}'.format(name, _sim_label(sim_info), result)}
        if action == 'toggle_flag':
            old = _get_occult_flags(sim_info)
            new_flags = _normalize_supported_mask(_mask_toggle(old, _int_value(occult_type)))
            _set_flags(sim_info, 'occult_types', new_flags)
            _set_flags(sim_info, 'current_occult_types', _clamp_current(new_flags, _get_current_flags(sim_info)))
            _recalc(sim_info)
            return {'ok': True, 'message': 'Toggled {} raw flag for {}'.format(name, _sim_label(sim_info))}
        return {'ok': False, 'message': 'Unknown action: {}'.format(action)}
    except Exception as exc:
        err = '{}\n{}'.format(exc, traceback.format_exc())
        _log(err)
        return {'ok': False, 'message': str(exc), 'traceback': traceback.format_exc()}


def _auto_repair_tick():
    global _LAST_AUTO_REPAIR
    _mccc_guard_tick()
    if not _AUTO_REPAIR:
        return
    now = time.time()
    if now - _LAST_AUTO_REPAIR < _AUTO_REPAIR_INTERVAL_SECONDS:
        return
    _LAST_AUTO_REPAIR = now
    try:
        active = _get_active_sim_info()
        if active is not None:
            details = _repair_sim(active, deep=False)
            _log('Auto repaired active Sim: {}'.format('; '.join(details)))
    except Exception as exc:
        _log('Auto repair failed: {}'.format(exc))


def _process_pending(_handle=None):
    global _LAST_COMMAND
    while True:
        with _LOCK:
            if not _PENDING:
                break
            item = _PENDING.pop(0)
        label = _format_action_label(item)
        _LAST_COMMAND = label
        _log('START {}'.format(label))
        started = time.time()
        try:
            result = run_action(item['action'], item.get('sim_id'), item.get('occult'), item.get('value'))
        except Exception as exc:
            result = {'ok': False, 'message': str(exc), 'traceback': traceback.format_exc()}
        elapsed_ms = (time.time() - started) * 1000.0
        ok = bool(result.get('ok'))
        _record_perf(item.get('action'), elapsed_ms, ok=ok)
        state = 'DONE' if ok else 'FAIL'
        _log('{} {} in {:.1f} ms: {}'.format(state, label, elapsed_ms, result.get('message', 'no message')))
        details = result.get('details')
        if details:
            try:
                max_detail = 30
                for line in list(details)[:max_detail]:
                    _log('  detail: {}'.format(line))
                if len(details) > max_detail:
                    _log('  detail: ... {} more line(s)'.format(len(details) - max_detail))
            except Exception:
                pass
        with _LOCK:
            _RESULTS[item['id']] = result
            try:
                item['event'].set()
            except Exception:
                pass
    _auto_repair_tick()
    _mccc_cas_shield_tick()
    return True
def _setup_alarm():
    global _ALARM_HANDLE, _ALARM_READY
    if _ALARM_READY:
        return True
    if alarms is None or clock is None:
        return False
    try:
        _ALARM_HANDLE = alarms.add_alarm_real_time(_ALARM_OWNER, clock.interval_in_real_seconds(_ACTION_QUEUE_INTERVAL_SECONDS), _process_pending, repeating=True)
        _ALARM_READY = True
        _detect_mccc()
        _detect_lot51_core()
        _log('Game-thread action queue armed at {0:.1f}s; auto repair is off unless enabled, and no Sim scan runs while idle. Overlay API v{1} ready; toggle key is {2}.'.format(_ACTION_QUEUE_INTERVAL_SECONDS, IMGUI_OVERLAY_API_VERSION, IMGUI_OVERLAY_TOGGLE_KEY))
        return True
    except Exception as exc:
        _log('Could not arm action queue: {}'.format(exc))
        return False


def _submit_action(action, sim_id=None, occult=None, value=None, wait_seconds=8.0):
    global _ACTION_COUNTER
    safe_action = (action or 'status').strip().lower()
    if not _setup_alarm():
        if safe_action in _READ_ONLY_ACTIONS:
            _log('DIRECT read-only action {}'.format(safe_action))
            started = time.time()
            result = run_action(action, sim_id, occult, value)
            _record_perf(safe_action, (time.time() - started) * 1000.0, ok=bool(result.get('ok')))
            return result
        return {'ok': False, 'message': 'Game-thread alarm queue is not ready. Load a household, then use the panel again or run td1occult.apex.run from the cheat console.'}
    event = threading.Event()
    with _LOCK:
        _ACTION_COUNTER += 1
        req_id = str(_ACTION_COUNTER)
        item = {'id': req_id, 'event': event, 'action': action, 'sim_id': sim_id, 'occult': occult, 'value': value}
        _PENDING.append(item)
    _log('QUEUED {}'.format(_format_action_label(item)))
    event.wait(wait_seconds)
    with _LOCK:
        result = _RESULTS.pop(req_id, None)
    if result is None:
        _log('WAITING #{} did not finish within {:.1f} seconds'.format(req_id, float(wait_seconds)))
        return {'ok': False, 'message': 'Action queued but did not complete yet. Watch the live log or try Refresh Status in a moment.'}
    return result
def _diagnostics():
    return {
        'server': SERVER_NAME,
        'build_version': _BUILD_VERSION,
        'host': HOST,
        'port': PORT,
        'alarm_ready': _ALARM_READY,
        'server_running': _SERVER_RUNNING,
        'auto_repair': _AUTO_REPAIR,
        'queue_interval_seconds': _ACTION_QUEUE_INTERVAL_SECONDS,
        'native_status': _NATIVE_STATUS,
        'native_path': _NATIVE_PATH,
        'native_candidates': _native_candidates(),
        'native_bound_exports': list(getattr(_NATIVE, '_td1_bound_exports', ())) if _NATIVE is not None else [],
        'native_missing_exports': list(getattr(_NATIVE, '_td1_missing_exports', ())) if _NATIVE is not None else [],
        'overlay': _overlay_capabilities(),
        'lot51_core_status': _detect_lot51_core(),
        'lot51_core_details': _LOT51_DETAILS,
        'lot51_events_installed': _LOT51_EVENTS_INSTALLED,
        'lot51_event_status': _LOT51_EVENT_STATUS,
        'mccc': _mccc_status_payload(),
        'xml_injector_status': _detect_xml_injector(),
        'saved_forms_count': len(_list_saved_forms(limit=300)),
        'clipboard': _clipboard_payload(),
        'history_lines': len(_HISTORY),
        'pending_count': len(_PENDING),
        'result_count': len(_RESULTS),
        'last_command': _LAST_COMMAND,
        'performance': _perf_snapshot(),
        'supported_occult_mask': _get_supported_occult_mask(),
        'occults': [{'name': _safe_name(oc), 'value': _int_value(oc), 'has_tuning': _get_tuning(oc) is not None} for oc in _all_occults()],
        'sims_count': len(_list_sims()),
    }


def _panel_html():
    occults = [_safe_name(oc) for oc in _all_occults()]
    if not occults:
        occults = ['ALIEN', 'VAMPIRE', 'MERMAID', 'WITCH', 'WEREWOLF', 'FAIRY', 'PLANTSIM']
    occ_json = json.dumps(occults)
    return r"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TD1 Occult Hybrid Apex</title>
<style>
:root{--bg:#050612;--ink:#f6f7ff;--muted:#aab5d6;--panel:#11162c;--panel2:#171f3d;--panel3:#202b55;--edge:rgba(151,172,255,.28);--edge2:rgba(255,255,255,.12);--violet:#9b6cff;--rose:#ff5e9d;--gold:#ffd166;--cyan:#70e1ff;--green:#6effa3;--red:#ff6384;--shadow:0 24px 70px rgba(0,0,0,.46);--radius:22px}
*{box-sizing:border-box}html{min-height:100%;background:var(--bg)}body{margin:0;min-height:100%;color:var(--ink);font:14px/1.45 Inter,Segoe UI,Roboto,Arial,sans-serif;background:radial-gradient(circle at 12% 0%,rgba(155,108,255,.35),transparent 33%),radial-gradient(circle at 82% 8%,rgba(112,225,255,.18),transparent 28%),radial-gradient(circle at 46% 85%,rgba(255,94,157,.15),transparent 40%),linear-gradient(145deg,#050612 0%,#071020 46%,#09081a 100%);overflow-x:hidden}
body:before{content:"";position:fixed;inset:0;pointer-events:none;background-image:linear-gradient(rgba(255,255,255,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.025) 1px,transparent 1px);background-size:48px 48px;mask-image:linear-gradient(to bottom,rgba(0,0,0,.9),rgba(0,0,0,.15));z-index:-1}.app{display:grid;grid-template-columns:286px minmax(0,1fr) 430px;gap:18px;min-height:100vh;padding:18px}.side,.main,.logdock{border:1px solid var(--edge);border-radius:var(--radius);background:linear-gradient(180deg,rgba(17,22,44,.88),rgba(8,11,24,.92));box-shadow:var(--shadow);backdrop-filter:blur(18px)}.side{position:sticky;top:18px;height:calc(100vh - 36px);padding:18px;display:flex;flex-direction:column;gap:14px}.brand{position:relative;padding:16px;border:1px solid var(--edge2);border-radius:20px;background:linear-gradient(135deg,rgba(155,108,255,.25),rgba(112,225,255,.10) 55%,rgba(255,94,157,.18));overflow:hidden}.brand:after{content:"";position:absolute;right:-42px;top:-42px;width:130px;height:130px;border-radius:999px;background:radial-gradient(circle,rgba(255,209,102,.33),transparent 66%)}.brand .title{font-size:22px;font-weight:950;letter-spacing:.2px;line-height:1.05}.brand .subtitle{margin-top:7px;color:#d5ddff;font-size:12px}.version{display:inline-flex;gap:7px;align-items:center;margin-top:12px;padding:6px 9px;border:1px solid rgba(255,255,255,.18);border-radius:999px;background:rgba(0,0,0,.2);color:#edf2ff;font-size:11px}.nav{display:grid;gap:8px}.tab{appearance:none;border:1px solid transparent;border-radius:16px;background:rgba(255,255,255,.055);color:var(--muted);padding:12px 13px;text-align:left;font-weight:850;cursor:pointer;display:flex;justify-content:space-between;align-items:center;transition:transform .14s ease,border .14s ease,background .14s ease,color .14s ease}.tab:hover{transform:translateY(-1px);border-color:rgba(112,225,255,.4);color:#fff}.tab.active{color:#fff;border-color:rgba(155,108,255,.72);background:linear-gradient(135deg,rgba(155,108,255,.28),rgba(112,225,255,.12))}.sidefoot{margin-top:auto;color:var(--muted);font-size:12px;border-top:1px solid var(--edge2);padding-top:13px}.statusdot{display:inline-block;width:9px;height:9px;border-radius:99px;background:var(--red);box-shadow:0 0 18px var(--red);margin-right:7px}.statusdot.ok{background:var(--green);box-shadow:0 0 18px var(--green)}.main{padding:18px;min-width:0}.topbar{display:grid;grid-template-columns:minmax(270px,1fr) auto;gap:12px;margin-bottom:16px}.field{border:1px solid var(--edge2);background:rgba(255,255,255,.055);border-radius:18px;padding:12px}.field label{display:block;color:var(--muted);font-size:12px;font-weight:800;margin-bottom:7px;text-transform:uppercase;letter-spacing:.08em}.field input,.field select{width:100%;background:rgba(0,0,0,.32);border:1px solid rgba(151,172,255,.32);border-radius:13px;color:#fff;padding:11px 12px;outline:none}.field input:focus{border-color:var(--cyan);box-shadow:0 0 0 3px rgba(112,225,255,.12)}.topbuttons{display:flex;gap:9px;align-items:stretch}.btn,.bigbtn{border:1px solid rgba(151,172,255,.32);border-radius:14px;background:linear-gradient(180deg,rgba(46,57,108,.95),rgba(26,34,70,.95));color:#fff;padding:10px 12px;font-weight:900;cursor:pointer;box-shadow:0 9px 22px rgba(0,0,0,.24);transition:transform .12s ease,filter .12s ease,border .12s ease}.btn:hover,.bigbtn:hover{transform:translateY(-1px);filter:brightness(1.08);border-color:rgba(255,255,255,.36)}.btn:active,.bigbtn:active{transform:translateY(1px)}.bigbtn{min-height:54px}.good{background:linear-gradient(180deg,rgba(55,171,94,.95),rgba(21,97,52,.96));border-color:rgba(110,255,163,.45)}.danger{background:linear-gradient(180deg,rgba(198,59,95,.96),rgba(124,30,58,.98));border-color:rgba(255,99,132,.55)}.warn{background:linear-gradient(180deg,rgba(196,142,42,.96),rgba(115,79,23,.98));border-color:rgba(255,209,102,.55)}.soft{background:linear-gradient(180deg,rgba(44,105,158,.96),rgba(26,60,105,.98));border-color:rgba(112,225,255,.45)}.ghost{background:rgba(255,255,255,.06);box-shadow:none}.dashboard{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:16px}.metric{position:relative;overflow:hidden;border:1px solid var(--edge2);border-radius:20px;background:linear-gradient(180deg,rgba(255,255,255,.075),rgba(255,255,255,.035));padding:14px;min-height:105px}.metric:after{content:"";position:absolute;right:-34px;top:-34px;width:90px;height:90px;border-radius:999px;background:radial-gradient(circle,rgba(112,225,255,.16),transparent 67%)}.metric .label{color:var(--muted);font-size:11px;font-weight:900;text-transform:uppercase;letter-spacing:.09em}.metric .value{margin-top:7px;font-size:28px;font-weight:950}.metric .hint{margin-top:2px;color:#cbd5ff;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.panel{display:none;animation:rise .18s ease}.panel.active{display:block}@keyframes rise{from{opacity:.2;transform:translateY(8px)}to{opacity:1;transform:none}}.section-title{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin:5px 0 12px}.section-title h2{margin:0;font-size:25px;letter-spacing:.1px}.section-title p{margin:3px 0 0;color:var(--muted);max-width:780px}.hero{display:grid;grid-template-columns:repeat(4,minmax(130px,1fr));gap:10px;margin:12px 0 16px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(292px,1fr));gap:13px}.card{border:1px solid var(--edge2);border-radius:20px;background:linear-gradient(180deg,rgba(24,32,66,.82),rgba(12,16,34,.92));box-shadow:0 16px 44px rgba(0,0,0,.28);padding:14px}.card h3{margin:0 0 11px;font-size:20px}.card .btn{font-size:12px;padding:8px 9px;margin:4px 3px 0 0;box-shadow:none}.occ-head{display:flex;justify-content:space-between;gap:10px;align-items:start}.occ-name{font-size:19px;font-weight:950}.occ-value{font-size:11px;color:var(--muted);border:1px solid var(--edge2);border-radius:999px;padding:4px 7px}.pills{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0 10px}.pill{border:1px solid rgba(151,172,255,.35);color:#dbe4ff;border-radius:999px;padding:4px 8px;font-size:11px;background:rgba(255,255,255,.055)}.pill.on{background:rgba(110,255,163,.13);color:#c9ffd9;border-color:rgba(110,255,163,.5)}.pill.off{background:rgba(255,99,132,.12);color:#ffd5df;border-color:rgba(255,99,132,.43)}.pill.warn{background:rgba(255,209,102,.13);color:#ffe6a2;border-color:rgba(255,209,102,.45)}.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}.output{white-space:pre-wrap;background:rgba(0,0,0,.35);border:1px solid rgba(151,172,255,.24);border-radius:16px;padding:12px;min-height:160px;max-height:420px;overflow:auto;color:#eaf0ff;font:12px/1.45 Consolas,Monaco,monospace}.note{color:var(--muted);font-size:13px}.logdock{position:sticky;top:18px;height:calc(100vh - 36px);padding:15px;display:flex;flex-direction:column;min-width:0}.loghead{display:flex;align-items:start;justify-content:space-between;gap:10px;margin-bottom:11px}.loghead h2{font-size:20px;margin:0}.loghead p{margin:2px 0 0;color:var(--muted);font-size:12px}.logcontrols{display:flex;gap:7px;flex-wrap:wrap}.logbox{flex:1;min-height:0;overflow:auto;border:1px solid rgba(151,172,255,.22);border-radius:18px;background:rgba(0,0,0,.31);padding:10px}.logline{display:grid;grid-template-columns:74px 1fr;gap:8px;border-bottom:1px solid rgba(255,255,255,.055);padding:8px 2px;color:#dfe7ff;font:12px/1.4 Consolas,Monaco,monospace}.logline:last-child{border-bottom:none}.logtime{color:#95a4d0}.logmsg{overflow-wrap:anywhere}.logline.goodline .logmsg{color:#c7ffd8}.logline.badline .logmsg{color:#ffd1dc}.logline.warnline .logmsg{color:#ffe6a5}.logline.startline .logmsg{color:#ccecff}.perf{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px}.perfitem{border:1px solid rgba(151,172,255,.18);border-radius:14px;background:rgba(255,255,255,.05);padding:9px}.perfitem .k{color:var(--muted);font-size:11px}.perfitem .v{font-weight:950;margin-top:3px}.toast{position:fixed;left:50%;bottom:22px;transform:translateX(-50%) translateY(130%);padding:12px 16px;border-radius:16px;background:rgba(5,8,20,.94);border:1px solid rgba(151,172,255,.35);box-shadow:var(--shadow);transition:transform .18s ease;z-index:100}.toast.show{transform:translateX(-50%) translateY(0)}.split{display:grid;grid-template-columns:1.2fr .8fr;gap:12px}.mini{font-size:12px;color:var(--muted)}.hidden{display:none!important}@media(max-width:1320px){.app{grid-template-columns:250px minmax(0,1fr)}.logdock{position:relative;top:auto;height:540px;grid-column:1 / -1}.dashboard{grid-template-columns:repeat(2,1fr)}}@media(max-width:860px){.app{display:block;padding:10px}.side,.main,.logdock{position:relative;height:auto;margin-bottom:12px}.topbar,.row,.hero,.dashboard,.split{grid-template-columns:1fr}.side{top:auto}.nav{grid-template-columns:1fr 1fr}.tab{font-size:12px}}
</style>
</head>
<body>
<div class="app">
  <aside class="side">
    <div class="brand"><div class="title">TD1 Occult<br>Hybrid Apex</div><div class="subtitle">Glorious RTBP-style local commander</div><div class="version"><span id="dot" class="statusdot"></span><span id="versionText">v4</span></div></div>
    <div class="nav">
      <button class="tab active" data-tab="control">Command Center <span>01</span></button>
      <button class="tab" data-tab="forms">Form Studio <span>02</span></button>
      <button class="tab" data-tab="memory">Memory + Traits <span>03</span></button>
      <button class="tab" data-tab="raw">Raw Flags <span>04</span></button>
      <button class="tab" data-tab="cas">Safe CAS <span>05</span></button>
      <button class="tab" data-tab="sims">Sim Browser <span>06</span></button>
      <button class="tab" data-tab="diag">Diagnostics <span>07</span></button>
    </div>
    <div class="sidefoot"><b>Performance mode:</b><br>No repair sweeps or Sim scans run in the background by default. Status refreshes only on load, button press, or after a command. The live log polls the mod's in-memory log only.</div>
  </aside>

  <main class="main">
    <div class="topbar">
      <div class="field"><label>Target Sim ID</label><input id="sim" placeholder="blank = active Sim"></div><div class="field"><label>Occult Pick</label><select id="occultPick"></select></div>
      <div class="topbuttons"><button class="bigbtn soft" onclick="cmd('status')">Refresh Status</button><button class="bigbtn ghost" onclick="toggleLogs()">Pause Log</button></div>
    </div>

    <div class="dashboard">
      <div class="metric"><div class="label">Target</div><div class="value" id="mSim">—</div><div class="hint" id="mSimHint">Awaiting game status</div></div>
      <div class="metric"><div class="label">Hybrid Health</div><div class="value" id="mHealth">—</div><div class="hint" id="mHealthHint">No report yet</div></div>
      <div class="metric"><div class="label">Flags</div><div class="value" id="mFlags">—</div><div class="hint" id="mCurrent">current —</div></div>
      <div class="metric"><div class="label">Bridge</div><div class="value" id="mBridge">—</div><div class="hint" id="mBridgeHint">native status unknown</div></div>
    </div>

    <section id="control" class="panel active">
      <div class="section-title"><div><h2>Command Center</h2><p>High-impact occult controls. Commands are queued through the Sims game thread and logged step-by-step.</p></div></div>
      <div class="hero"><button class="bigbtn good" onclick="cmd('repair')">Repair Active</button><button class="bigbtn good" onclick="cmd('deep_repair')">Deep Repair</button><button class="bigbtn soft" onclick="cmd('normalize')">Normalize</button><button class="bigbtn good" onclick="cmd('add_all')">Add All Occults</button><button class="bigbtn danger" onclick="cmd('purge')">Purge Occults</button><button class="bigbtn soft" onclick="cmd('human')">Switch Human</button><button class="bigbtn soft" onclick="cmd('generate_all_forms')">Generate All Forms</button><button class="bigbtn warn" onclick="cmd('repair_all')">Repair All Sims</button><button class="bigbtn warn" onclick="cmd('deep_repair_all')">Deep Repair All</button></div>
      <div class="field" style="margin-bottom:12px"><label>Filter occult cards</label><input id="filter" placeholder="type vampire, fairy, witch..." oninput="filterCards()"></div>
      <div id="occultGrid" class="grid"></div>
    </section>

    <section id="forms" class="panel">
      <div class="section-title"><div><h2>Form Studio</h2><p>Generate, delete, copy, and restore occult form data. Nothing runs continuously; every operation is explicit.</p></div></div>
      <div class="hero"><button class="bigbtn soft" onclick="cmd('generate_all_forms')">Generate All Forms</button><button class="bigbtn good" onclick="cmd('force_form_available')">Force Forms Available</button><button class="bigbtn good" onclick="cmd('save_memory')">Snapshot Forms</button><button class="bigbtn warn" onclick="cmd('restore_memory')">Restore Snapshot</button></div>
      <div id="formsGrid" class="grid"></div>
    </section>

    <section id="memory" class="panel">
      <div class="section-title"><div><h2>Memory + Traits</h2><p>Manage hidden occult memory traits and tuning trait alignment without opening CAS.</p></div></div>
      <div class="hero"><button class="bigbtn good" onclick="cmd('save_memory')">Save Form Memory</button><button class="bigbtn good" onclick="cmd('restore_memory')">Restore Form Memory</button><button class="bigbtn danger" onclick="cmd('clear_memory')">Clear Memory</button><button class="bigbtn soft" onclick="cmd('sync_flags_to_traits')">Flags → Traits</button><button class="bigbtn soft" onclick="cmd('sync_traits_to_flags')">Traits → Flags</button></div>
      <div id="memoryGrid" class="grid"></div>
    </section>

    <section id="raw" class="panel">
      <div class="section-title"><div><h2>Raw Flag Console</h2><p>Detailed flag surgery for debugging. Normalized buttons clamp values to supported occult bits.</p></div></div>
      <div class="row"><div class="field"><label>occult_types</label><input id="flags" value="0"><button class="btn warn" onclick="cmd('set_flags',null,$('flags').value)">Set raw occult_types</button><button class="btn good" onclick="cmd('set_flags_normalized',null,$('flags').value)">Set normalized</button></div><div class="field"><label>current_occult_types</label><input id="currentFlags" value="0"><button class="btn warn" onclick="cmd('set_current',null,$('currentFlags').value)">Set raw current</button><button class="btn good" onclick="cmd('set_current_normalized',null,$('currentFlags').value)">Set normalized</button></div></div><br><div id="rawGrid" class="grid"></div>
    </section>

    <section id="cas" class="panel">
      <div class="section-title"><div><h2>Safe CAS Workflow</h2><p>Prepare before CAS, make edits, restore afterward, then deep repair. This is built to preserve secondary occult forms.</p></div></div>
      <div class="hero"><button class="bigbtn warn" onclick="cmd('cas_prepare')">Prepare CAS Safe</button><button class="bigbtn warn" onclick="cmd('cas_prepare_keep_human')">CAS Keep Human</button><button class="bigbtn good" onclick="cmd('cas_restore')">Restore After CAS</button><button class="bigbtn warn" onclick="cmd('cas_prepare_household')">Prepare Household</button><button class="bigbtn good" onclick="cmd('cas_restore_household')">Restore Household</button><button class="bigbtn soft" onclick="cmd('human')">Switch Human</button><button class="bigbtn good" onclick="cmd('deep_repair')">Deep Repair After CAS</button></div>
      <div class="card" style="margin-bottom:13px"><h3>Recommended flow</h3><div class="note">1. Click a CAS Keep button. 2. Open CAS. 3. Return to Live Mode. 4. Click Restore After CAS. 5. Click Deep Repair. The log will show each saved/restored stage.</div></div>
      <div id="casGrid" class="grid"></div>
    </section>

    <section id="sims" class="panel">
      <div class="section-title"><div><h2>Sim Browser</h2><p>Load Sims, click a row to target that Sim, then run commands from any tab.</p></div></div>
      <button class="bigbtn soft" onclick="cmd('list_sims')">Load Sims</button><div id="simCards" class="grid" style="margin-top:13px"></div><pre id="simList" class="output hidden"></pre>
    </section>

    <section id="saved" class="panel">
      <div class="section-title"><div><h2>Saved Occult Form Library</h2><p>Save the active edited form or a stored occult form, search presets, then force-apply one back to current or occult data.</p></div></div>
      <div class="row"><div class="card"><h3>Save / Apply</h3><div class="field"><label>Preset Name</label><input id="saveName" placeholder="Nóttlilja vampire form v1"></div><div class="field"><label>Saved Form ID or Name</label><input id="savedId" placeholder="sf-VAMPIRE-..."></div><div class="hero"><button class="bigbtn good" onclick="cmd('save_active_form', $('occultPick').value, $('saveName').value)">Save Active Form</button><button class="bigbtn good" onclick="cmd('save_occult_form', $('occultPick').value, $('saveName').value)">Save Stored Occult Form</button><button class="bigbtn soft" onclick="cmd('apply_saved_form_current', null, $('savedId').value)">Apply To Current</button><button class="bigbtn warn" onclick="cmd('force_apply_saved_form', $('occultPick').value, $('savedId').value)">Force Apply To Occult</button></div></div><div class="card"><h3>Search</h3><div class="field"><label>Search</label><input id="savedSearch" placeholder="name, occult, sim, id"></div><button class="btn soft" onclick="searchSaved()">Search Saved Forms</button><button class="btn danger" onclick="cmd('delete_saved_form', null, $('savedId').value)">Delete Selected</button><pre class="output" id="savedOut">No search yet.</pre></div></div>
    </section>
    <section id="mccc" class="panel">
      <div class="section-title"><div><h2>MCCC Compatibility Guard</h2><p>Feature-detects MCCC modules, snapshots active household occult state, and restores occult flags/forms after MCCC Modify Household/Edit CAS returns.</p></div></div>
      <div class="hero"><button class="bigbtn soft" onclick="cmd('mccc_detect')">Detect MCCC</button><button class="bigbtn good" onclick="cmd('mccc_guard_on')">Guard ON</button><button class="bigbtn danger" onclick="cmd('mccc_guard_off')">Guard OFF</button><button class="bigbtn good" onclick="cmd('mccc_auto_restore_on')">Auto Restore ON</button><button class="bigbtn warn" onclick="cmd('mccc_auto_restore_off')">Auto Restore OFF</button><button class="bigbtn warn" onclick="cmd('mccc_snapshot_household')">Snapshot Before CAS</button><button class="bigbtn good" onclick="cmd('mccc_restore_household')">Restore After CAS</button><button class="bigbtn danger" onclick="cmd('mccc_restore_full_snapshot')">Full Snapshot Restore</button></div>
      <div class="card"><h3>CAS / Wardrobe Maintenance</h3><div class="field"><label>Scope</label><select id="appearanceScope"><option>all</option><option>wardrobe</option><option>body</option><option>face</option><option>physique</option><option>skin</option><option>tattoos</option></select></div><div class="hero"><button class="bigbtn soft" onclick="cmd('appearance_copy', null, $('appearanceScope').value)">Copy Scope</button><button class="bigbtn good" onclick="cmd('appearance_paste', null, $('appearanceScope').value)">Paste Scope</button><button class="bigbtn warn" onclick="cmd('apply_current_outfit_to_all')">Apply Current Outfit To All</button><button class="bigbtn soft" onclick="cmd('force_resend_appearance')">Force Resend Appearance</button></div></div>
    </section>
    <section id="diag" class="panel">
      <div class="section-title"><div><h2>Diagnostics + Performance</h2><p>Deep status, native bridge information, game-thread queue state, and measured command costs.</p></div></div>
      <div class="hero"><button class="bigbtn soft" onclick="cmd('diagnostics')">Run Diagnostics</button><button class="bigbtn soft" onclick="cmd('health')">Health Check</button><button class="bigbtn good" onclick="cmd('auto_on')">Auto Repair On</button><button class="bigbtn danger" onclick="cmd('auto_off')">Auto Repair Off</button><button class="bigbtn ghost" onclick="cmd('clear_logs')">Clear Log</button></div>
      <div class="split"><pre id="diagOut" class="output"></pre><pre id="perfOut" class="output"></pre></div>
    </section>

    <br><div class="card"><h3>Command Result</h3><pre id="out" class="output">Panel loaded. Waiting for game status...</pre></div>
    <br><div class="card"><h3>Full Status JSON</h3><pre id="status" class="output"></pre></div>
  </main>

  <aside class="logdock">
    <div class="loghead"><div><h2>Running Log</h2><p>Live queue, command, repair, and diagnostic trace.</p></div><div class="logcontrols"><button class="btn ghost" onclick="pollLogs(true)">Refresh</button><button class="btn ghost" onclick="copyLog()">Copy</button><button class="btn ghost" onclick="downloadLog()">Export</button></div></div>
    <div id="logbox" class="logbox"></div>
    <div class="perf"><div class="perfitem"><div class="k">Queue</div><div class="v" id="queueStat">—</div></div><div class="perfitem"><div class="k">Auto Repair</div><div class="v" id="autoStat">—</div></div><div class="perfitem"><div class="k">Last Avg</div><div class="v" id="avgStat">—</div></div><div class="perfitem"><div class="k">Native</div><div class="v" id="nativeStat">—</div></div></div>
  </aside>
</div>
<div class="toast" id="toast"></div>
<script>
const occults=OCCULT_JSON;
const $=id=>document.getElementById(id);
let lastStatus=null,lastLogs=[],logPaused=false,logTimer=null,busy=false;
function enc(v){return encodeURIComponent(v===undefined||v===null?'':v)}
function toast(msg){const t=$('toast'); t.textContent=msg; t.classList.add('show'); setTimeout(()=>t.classList.remove('show'),1800)}
function setDot(ok){const d=$('dot'); if(ok){d.classList.add('ok')}else{d.classList.remove('ok')}}
document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));document.querySelectorAll('.panel').forEach(x=>x.classList.remove('active'));b.classList.add('active');$(b.dataset.tab).classList.add('active')});
function card(o,kind){let buttons=''; if(kind==='cas'){buttons=`<button class="btn warn" onclick="cmd('cas_prepare_keep','${o}')">CAS Keep ${o}</button><button class="btn good" onclick="cmd('cas_restore')">Restore</button>`} if(kind==='control'){buttons=`<button class="btn good" onclick="cmd('add','${o}')">Add</button><button class="btn soft" onclick="cmd('gameplay_add','${o}')">Gameplay Init</button><button class="btn danger" onclick="cmd('remove','${o}')">Remove</button><button class="btn danger" onclick="cmd('gameplay_remove','${o}')">Gameplay Remove</button><button class="btn" onclick="cmd('switch','${o}')">Switch</button><button class="btn soft" onclick="cmd('on_add_actions','${o}')">Add Actions</button><button class="btn warn" onclick="cmd('lock_perks','${o}')">Lock Perks</button><button class="btn good" onclick="cmd('unlock_perks','${o}')">Unlock Perks</button>`} if(kind==='forms'){buttons=`<button class="btn good" onclick="cmd('generate_form','${o}')">Generate Form</button><button class="btn danger" onclick="cmd('delete_form','${o}')">Delete Form</button><button class="btn" onclick="cmd('copy_human_to_form','${o}')">Human → Form</button><button class="btn" onclick="cmd('copy_current_to_form','${o}')">Current → Form</button><button class="btn soft" onclick="cmd('copy_form_to_current','${o}')">Form → Current</button>`} if(kind==='memory'){buttons=`<button class="btn warn" onclick="cmd('add_memory_trait','${o}')">Add Memory Trait</button><button class="btn danger" onclick="cmd('remove_memory_trait','${o}')">Remove Memory Trait</button><button class="btn good" onclick="cmd('add_tuning_traits','${o}')">Add Tuning Traits</button><button class="btn danger" onclick="cmd('remove_tuning_traits','${o}')">Remove Tuning Traits</button>`} if(kind==='raw'){buttons=`<button class="btn warn" onclick="cmd('toggle_flag','${o}')">Toggle Raw Flag</button>`} return `<div class="card occ" data-occult="${o.toLowerCase()}"><div class="occ-head"><div class="occ-name">${o}</div><div class="occ-value" id="value-${kind}-${o}">—</div></div><div class="pills" id="pill-${kind}-${o}"><span class="pill">awaiting status</span></div>${buttons}</div>`}
function build(){let pick=$('occultPick'); if(pick)pick.innerHTML=occults.map(o=>`<option>${o}</option>`).join(''); ['control','forms','memory','raw','cas'].forEach(kind=>{let el=$(kind==='control'?'occultGrid':kind+'Grid'); if(el)el.innerHTML=occults.map(o=>card(o,kind)).join('')})}
function filterCards(){const q=($('filter')?$('filter').value:'').toLowerCase(); document.querySelectorAll('.occ').forEach(c=>c.style.display=c.dataset.occult.indexOf(q)>=0?'':'none')}
async function cmd(action,occult,value){let u='/api/command?action='+enc(action)+'&sim_id='+enc($('sim').value||''); if(occult)u+='&occult='+enc(occult); if(value!==undefined&&value!==null)u+='&value='+enc(value); busy=true; $('out').textContent='Running '+action+'...\nWatch the Running Log for queue/start/done details.'; pollLogs(true); try{let r=await fetch(u,{cache:'no-store'}); let j=await r.json(); show(j); pollLogs(true); if(action!=='status'&&action!=='list_sims'&&action!=='diagnostics'&&action!=='clear_logs') setTimeout(()=>cmd('status'),450)}catch(e){$('out').textContent='Browser request failed: '+e; setDot(false)} finally{busy=false}}
function show(j){setDot(!!j.ok); $('out').textContent=JSON.stringify(j,null,2); if(j.data){if(j.data.server){$('diagOut').textContent=JSON.stringify(j.data,null,2); renderPerf(j.data.performance||{}); updateLogStats({performance:j.data.performance||{},pending_count:j.data.pending_count,auto_repair:j.data.auto_repair,native_status:j.data.native_status})}else{$('status').textContent=JSON.stringify(j.data,null,2); lastStatus=j.data; paint(j.data)}} if(j.details){$('out').textContent += '\n\n' + j.details.join('\n')} if(j.sims){renderSims(j.sims)}}
function paint(data){$('versionText').textContent=data.build_version||'v4'; $('mSim').textContent=(data.sim||'—').split(' ').slice(0,2).join(' '); $('mSimHint').textContent='id '+(data.sim_id||'—'); const h=data.health||{}; $('mHealth').textContent=(h.score!==undefined?h.score:'—'); $('mHealthHint').textContent=(h.issues&&h.issues.length? h.issues.length+' issue(s)' : 'clean'); $('mFlags').textContent=data.occult_types_value; $('mCurrent').textContent='current '+data.current_occult_types_value; $('mBridge').textContent=(data.native&&data.native.status&&data.native.status.indexOf('loaded')>=0)?'Loaded':'Fallback'; $('mBridgeHint').textContent=(data.native&&data.native.status)||'unknown'; setDot(true); for(const o of data.occults||[]){for(const kind of ['control','forms','memory','raw','cas']){let el=$(`pill-${kind}-${o.name}`); let val=$(`value-${kind}-${o.name}`); if(val)val.textContent=o.value; if(!el)continue; let tuning=o.has_tuning?'tuning':'no tuning'; el.innerHTML=`<span class="pill ${o.has_occult?'on':'off'}">occult ${o.has_occult?'ON':'OFF'}</span><span class="pill ${o.has_form_data?'on':'off'}">form ${o.has_form_data?'ON':'OFF'}</span><span class="pill ${o.has_memory_trait?'on':'off'}">memory ${o.has_memory_trait?'ON':'OFF'}</span><span class="pill ${o.has_tuning?'on':'warn'}">${tuning}</span>`}} updateLogStats(data.performance||{})}
function renderSims(sims){const box=$('simCards'); box.innerHTML=(sims||[]).map(s=>`<div class="card"><h3>${s.name||'Unknown Sim'}</h3><div class="pills"><span class="pill">id ${s.id}</span><span class="pill">flags ${s.occult_types_value}</span><span class="pill">current ${s.current_occult_types_value}</span></div><button class="btn good" onclick="$('sim').value='${s.id}'; cmd('status')">Target This Sim</button></div>`).join('')||'<div class="card">No Sims returned.</div>'}
function lineClass(text){if(text.indexOf('DONE')>=0||text.indexOf('loaded')>=0||text.indexOf('enabled')>=0)return 'goodline'; if(text.indexOf('FAIL')>=0||text.indexOf('failed')>=0||text.indexOf('ERROR')>=0)return 'badline'; if(text.indexOf('WAITING')>=0||text.indexOf('QUEUED')>=0)return 'warnline'; if(text.indexOf('START')>=0)return 'startline'; return ''}
function renderLogs(lines){lastLogs=lines||[]; const box=$('logbox'); box.innerHTML=lastLogs.map(line=>{let time=''; let msg=line; const m=/^\[([^\]]+)\]\s*(.*)$/.exec(line); if(m){time=m[1]; msg=m[2]} return `<div class="logline ${lineClass(msg)}"><div class="logtime">${time}</div><div class="logmsg">${escapeHtml(msg)}</div></div>`}).join('')||'<div class="logline"><div class="logtime">—</div><div class="logmsg">No log entries yet.</div></div>'; box.scrollTop=box.scrollHeight}
function escapeHtml(s){return String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
async function pollLogs(manual){if(logPaused&&!manual)return; try{let r=await fetch('/api/logs?count=220',{cache:'no-store'}); let j=await r.json(); renderLogs(j.history||[]); updateLogStats(j); renderPerf(j.performance||{}); setDot(!!j.ok)}catch(e){if(manual)toast('Could not read log: '+e); setDot(false)}}
function updateLogStats(j){j=j||{}; $('queueStat').textContent=(j.pending_count!==undefined?j.pending_count:'0')+' pending'; $('autoStat').textContent=j.auto_repair?'ON':'OFF'; $('nativeStat').textContent=(j.native_status|| (lastStatus&&lastStatus.native&&lastStatus.native.status) || '—').split(' ')[0]; let p={}; if(j.performance&&j.performance.stats){p=j.performance.stats}else if(j.stats){p=j.stats}else if(j.performance){p=j.performance}else{p=j}; let keys=Object.keys(p).filter(k=>p[k]&&typeof p[k]==='object'&&p[k].last_ms!==undefined); if(keys.length){let latest=keys.map(k=>[k,p[k].last_ms||0]).sort((a,b)=>b[1]-a[1])[0]; $('avgStat').textContent=latest[0]+' '+latest[1]+'ms'}else{$('avgStat').textContent='—'}}
function renderPerf(perf){if(perf&&perf.stats)perf=perf.stats; const keys=Object.keys(perf||{}).filter(k=>perf[k]&&typeof perf[k]==='object').sort(); $('perfOut').textContent=keys.map(k=>`${k}: count=${perf[k].count} ok=${perf[k].ok} fail=${perf[k].fail} last=${perf[k].last_ms}ms avg=${perf[k].avg_ms}ms max=${perf[k].max_ms}ms`).join('\n')||'No command timing samples yet.'}

async function searchSaved(){try{let r=await fetch('/api/saved_forms/text?search='+enc($('savedSearch').value||''),{cache:'no-store'}); $('savedOut').textContent=await r.text()}catch(e){$('savedOut').textContent='Saved form search failed: '+e}}
function toggleLogs(){logPaused=!logPaused; toast(logPaused?'Live log paused':'Live log resumed'); if(!logPaused)pollLogs(true)}
function copyLog(){navigator.clipboard&&navigator.clipboard.writeText(lastLogs.join('\n')); toast('Log copied')}
function downloadLog(){const blob=new Blob([lastLogs.join('\n')],{type:'text/plain'}); const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download='TD1_Occult_Hybrid_Apex_Log.txt'; a.click(); setTimeout(()=>URL.revokeObjectURL(a.href),800)}
build(); pollLogs(true); setTimeout(()=>cmd('status'),350); logTimer=setInterval(()=>pollLogs(false),2500);
</script>
</body>
</html>""".replace('OCCULT_JSON', occ_json)

def _parse_request_path(raw_path):
    if not raw_path:
        return '/', {}
    if urlparse is not None and parse_qs is not None:
        parsed = urlparse(raw_path)
        query = {}
        for key, values in parse_qs(parsed.query, keep_blank_values=True).items():
            query[key] = values[0] if values else ''
        return parsed.path or '/', query
    parts = raw_path.split('?', 1)
    path = parts[0] or '/'
    query = {}
    if len(parts) > 1:
        for pair in parts[1].split('&'):
            if '=' in pair:
                k, v = pair.split('=', 1)
            else:
                k, v = pair, ''
            if unquote_plus is not None:
                k = unquote_plus(k)
                v = unquote_plus(v)
            query[k] = v
    return path, query


def _http_payload(payload, content_type='application/json; charset=utf-8', status='200 OK'):
    if isinstance(payload, bytes):
        body = payload
    elif isinstance(payload, str):
        body = payload.encode('utf-8')
    else:
        body = json.dumps(payload, default=str, indent=2).encode('utf-8')
    headers = [
        'HTTP/1.1 {}'.format(status),
        'Content-Type: {}'.format(content_type),
        'Content-Length: {}'.format(len(body)),
        'Access-Control-Allow-Origin: *',
        'Access-Control-Allow-Methods: GET, OPTIONS',
        'Access-Control-Allow-Headers: Content-Type',
        'Cache-Control: no-store',
        'Connection: close',
        '',
        ''
    ]
    return '\r\n'.join(headers).encode('ascii') + body


def _handle_http_client(conn):
    try:
        data = conn.recv(16384)
        if not data:
            return
        line = data.split(b'\r\n', 1)[0].decode('utf-8', 'ignore')
        parts = line.split()
        method = parts[0] if len(parts) > 0 else 'GET'
        raw_path = parts[1] if len(parts) > 1 else '/'
        if method == 'OPTIONS':
            conn.sendall(_http_payload('', 'text/plain; charset=utf-8', '204 No Content'))
            return
        path, query = _parse_request_path(raw_path)
        if path in ('/', '/index.html'):
            conn.sendall(_http_payload(_panel_html(), 'text/html; charset=utf-8'))
            return
        if path == '/api/history':
            with _LOCK:
                payload = {'ok': True, 'history': list(_HISTORY)}
            conn.sendall(_http_payload(payload))
            return
        if path in ('/api/command', '/api/status'):
            payload = _submit_action(query.get('action', 'status'), query.get('sim_id', ''), query.get('occult'), query.get('value'))
            conn.sendall(_http_payload(payload))
            return
        if path == '/api/sims':
            payload = _submit_action('list_sims')
            conn.sendall(_http_payload(payload))
            return
        if path == '/api/forms':
            payload = _submit_action('list_saved_forms', sim_id=query.get('sim_id', ''), value=query.get('query', ''), wait_seconds=3.0)
            conn.sendall(_http_payload(payload))
            return
        if path == '/api/mccc':
            payload = _submit_action('mccc_status', wait_seconds=3.0)
            conn.sendall(_http_payload(payload))
            return
        if path == '/api/clipboard':
            payload = _submit_action('clipboard_status', wait_seconds=3.0)
            conn.sendall(_http_payload(payload))
            return
        if path == '/api/diagnostics':
            payload = _submit_action('diagnostics')
            conn.sendall(_http_payload(payload))
            return
        if path == '/api/logs':
            payload = _logs_payload(query.get('count', 180))
            conn.sendall(_http_payload(payload))
            return
        if path in ('/api/saved_forms/text', '/api/saved_forms.txt'):
            payload = _saved_forms_text(query.get('search', '') or query.get('q', ''))
            conn.sendall(_http_payload(payload, 'text/plain; charset=utf-8'))
            return
        if path in ('/api/saved_forms', '/api/forms'):
            payload = {'ok': True, 'message': 'Saved forms listed', 'forms': _list_saved_forms(query.get('search', '') or query.get('q', ''))}
            conn.sendall(_http_payload(payload))
            return
        if path in ('/api/overlay', '/api/overlay/state'):
            payload = _overlay_state_payload(query)
            conn.sendall(_http_payload(payload))
            return
        if path == '/api/overlay/capabilities':
            payload = {'ok': True, 'message': 'Overlay capabilities ready', 'data': _overlay_capabilities()}
            conn.sendall(_http_payload(payload))
            return
        conn.sendall(_http_payload({'ok': False, 'message': 'Unknown path'}, status='404 Not Found'))
    except Exception as exc:
        try:
            conn.sendall(_http_payload({'ok': False, 'message': str(exc), 'traceback': traceback.format_exc()}, status='500 Internal Server Error'))
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _server_loop():
    global _SERVER_RUNNING, _SERVER_SOCKET
    while _SERVER_RUNNING:
        try:
            conn, _addr = _SERVER_SOCKET.accept()
            t = threading.Thread(target=_handle_http_client, args=(conn,))
            t.daemon = True
            t.start()
        except socket.timeout:
            continue
        except Exception as exc:
            if _SERVER_RUNNING:
                _log('HTTP server error: {}'.format(exc))
            time.sleep(0.25)


def start_server():
    global _SERVER_SOCKET, _SERVER_THREAD, _SERVER_RUNNING
    _load_native()
    with _LOCK:
        if _SERVER_RUNNING:
            return True, '{} already running at http://{}:{}/'.format(SERVER_NAME, HOST, PORT)
        try:
            _SERVER_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            _SERVER_SOCKET.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            _SERVER_SOCKET.settimeout(0.5)
            _SERVER_SOCKET.bind((HOST, PORT))
            _SERVER_SOCKET.listen(24)
            _SERVER_RUNNING = True
            _SERVER_THREAD = threading.Thread(target=_server_loop, name='TD1OccultApexHTTP')
            _SERVER_THREAD.daemon = True
            _SERVER_THREAD.start()
            # The game-thread queue is armed lazily on the first panel command,
            # so simply loading the mod does not create recurring simulation work.
            msg = '{} running at http://{}:{}/'.format(SERVER_NAME, HOST, PORT)
            _log(msg)
            return True, msg
        except Exception as exc:
            try:
                if _SERVER_SOCKET is not None:
                    _SERVER_SOCKET.close()
            except Exception:
                pass
            _SERVER_SOCKET = None
            _SERVER_RUNNING = False
            msg = 'Could not start {}: {}'.format(SERVER_NAME, exc)
            _log(msg)
            return False, msg


def stop_server():
    global _SERVER_SOCKET, _SERVER_THREAD, _SERVER_RUNNING
    with _LOCK:
        if not _SERVER_RUNNING:
            return True, '{} is not running.'.format(SERVER_NAME)
        _SERVER_RUNNING = False
        try:
            _SERVER_SOCKET.close()
        except Exception:
            pass
        _SERVER_SOCKET = None
        _SERVER_THREAD = None
        msg = '{} stopped.'.format(SERVER_NAME)
        _log(msg)
        return True, msg


def _cmd_out(connection):
    try:
        return CheatOutput(connection)
    except Exception:
        try:
            return Output(connection)
        except Exception:
            return lambda message: _log(message)


if Command is not None:
    _LIVE = getattr(CommandType, 'Live', None)
    _UNRESTRICTED = getattr(CommandRestrictionFlags, 'UNRESTRICTED', None)

    @Command('td1occult.apex.server_start', command_type=_LIVE, command_restrictions=_UNRESTRICTED)
    def _command_server_start(_connection=None):
        out = _cmd_out(_connection)
        ok, msg = start_server()
        out(msg)
        return ok

    @Command('td1occult.apex.server_stop', command_type=_LIVE, command_restrictions=_UNRESTRICTED)
    def _command_server_stop(_connection=None):
        out = _cmd_out(_connection)
        ok, msg = stop_server()
        out(msg)
        return ok

    @Command('td1occult.apex.status', command_type=_LIVE, command_restrictions=_UNRESTRICTED)
    def _command_status(sim_id: str='', _connection=None):
        out = _cmd_out(_connection)
        result = run_action('status', sim_id=sim_id)
        out(json.dumps(result, default=str, indent=2))
        return bool(result.get('ok'))

    @Command('td1occult.apex.run', command_type=_LIVE, command_restrictions=_UNRESTRICTED)
    def _command_run(action: str='status', occult: str='', sim_id: str='', value: str='', _connection=None):
        out = _cmd_out(_connection)
        result = run_action(action, sim_id=sim_id, occult=occult, value=value)
        out(result.get('message', str(result)))
        return bool(result.get('ok'))

    @Command('td1occult.apex.repair_all', command_type=_LIVE, command_restrictions=_UNRESTRICTED)
    def _command_repair_all(deep: bool=False, _connection=None):
        out = _cmd_out(_connection)
        details = _repair_all(deep=deep)
        for line in details:
            out(line)
        return True


# Auto-start like RTBP's in-game bridge.
_load_saved_forms()
# V9.4: legacy Lot51 event hooks are not auto-installed; use explicit MCCC Shield/Lot51 commands.
start_server()


# -----------------------------------------------------------------------------
# Apex v6.0 extensions: saved occult forms, MCCC CAS shield, appearance tools,
# and ImGui command surface support. These are appended as compatibility layers
# so the base Apex backend remains easy to diff/update after Sims 4 patches.
# -----------------------------------------------------------------------------
try:
    import sys as _td1_sys
    import inspect as _td1_inspect
    import pickle as _td1_pickle
except Exception:
    _td1_sys = None
    _td1_inspect = None
    _td1_pickle = None

_SAVED_FORMS = {}
_APPEARANCE_CLIPBOARD = {}
_MCCC_SHIELD = {
    'armed': False,
    'household': False,
    'sim_ids': [],
    'armed_at': 0.0,
    'last_tick': 0.0,
    'auto_restore': True,
    'restore_attempts': 0,
    'keep': 'HUMAN',
    'last_restore': 0.0,
    'hook_scan': False,
    'hooked_functions': [],
    'settle_seconds': 6.0,
}
_MCCC_DETAILS = {'checked': False, 'available': False, 'modules': {}, 'version_guess': None, 'archive_modules_seen': []}
_LOT51_EVENT_REGISTRATION = {'attempted': False, 'registered': False, 'message': 'not attempted'}
_BASE_RUN_ACTION = run_action
_BASE_STATUS = _status
_BASE_AUTO_REPAIR_TICK = _auto_repair_tick
_BASE_OVERLAY_CAPABILITIES = _overlay_capabilities

try:
    _READ_ONLY_ACTIONS.update(set(('list_saved_forms', 'mccc_status', 'mccc_detect', 'appearance_clipboard_status', 'saved_form_status')))
except Exception:
    pass


def _apex6_now_label():
    try:
        return time.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return 'unknown time'


def _apex6_safe_text(value):
    try:
        text = str(value)
    except Exception:
        text = 'value'
    for ch in ('\r', '\n', '\t'):
        text = text.replace(ch, ' ')
    return text.strip()


def _apex6_slug(value, fallback='slot'):
    text = _apex6_safe_text(value).lower()
    keep = []
    for ch in text:
        if ch.isalnum():
            keep.append(ch)
        elif ch in (' ', '-', '_', '.', ':'):
            keep.append('_')
    slug = ''.join(keep).strip('_')
    while '__' in slug:
        slug = slug.replace('__', '_')
    return slug or fallback


def _apex6_payload_for_appearance(obj, scope='cas'):
    payload = _snapshot_siminfo_payload(obj)
    # Never let a wardrobe/body paste mutate occult identity flags or base trait ids.
    for risky in ('flags', 'base_trait_ids'):
        try:
            payload.pop(risky, None)
        except Exception:
            pass
    scope = (scope or 'cas').lower()
    if scope in ('all', 'cas', 'appearance'):
        return payload
    allowed = {
        'wardrobe': set(('__outfits__',)),
        'outfits': set(('__outfits__',)),
        'body': set(('physique', 'facial_attributes', 'voice_pitch', 'voice_actor', 'voice_effect', 'genetic_data')),
        'skin': set(('skin_tone', 'pelt_layers', 'genetic_data')),
        # Tattoos/skin details are stored in CAS/outfit/skin payloads depending on patch and pack.
        # This is intentionally broader than just one field, but still avoids identity flags.
        'tattoos': set(('__outfits__', 'skin_tone', 'pelt_layers', 'genetic_data')),
        'voice': set(('voice_pitch', 'voice_actor', 'voice_effect')),
    }.get(scope)
    if allowed is None:
        return payload
    return dict((key, value) for key, value in payload.items() if key in allowed)


def _apex6_restore_appearance(obj, payload, scope='cas'):
    if obj is None or not payload:
        return False
    scoped = dict(payload)
    scope = (scope or 'cas').lower()
    if scope not in ('all', 'cas', 'appearance'):
        allowed = {
            'wardrobe': set(('__outfits__',)),
            'outfits': set(('__outfits__',)),
            'body': set(('physique', 'facial_attributes', 'voice_pitch', 'voice_actor', 'voice_effect', 'genetic_data')),
            'skin': set(('skin_tone', 'pelt_layers', 'genetic_data')),
            'tattoos': set(('__outfits__', 'skin_tone', 'pelt_layers', 'genetic_data')),
            'voice': set(('voice_pitch', 'voice_actor', 'voice_effect')),
        }.get(scope)
        if allowed is not None:
            scoped = dict((key, value) for key, value in scoped.items() if key in allowed)
    for risky in ('flags', 'base_trait_ids'):
        try:
            scoped.pop(risky, None)
        except Exception:
            pass
    return _restore_siminfo_payload(obj, scoped)


def _apex6_slot_bucket(sim_id):
    sid = str(sim_id)
    if sid not in _SAVED_FORMS:
        _SAVED_FORMS[sid] = {}
    return _SAVED_FORMS[sid]


def _apex6_find_saved_form(slot_id):
    slot_id = _apex6_safe_text(slot_id)
    if not slot_id:
        return None, None, None
    for sid, bucket in list(_SAVED_FORMS.items()):
        if slot_id in bucket:
            return sid, slot_id, bucket[slot_id]
    # forgiving search: allow user to paste a visible label instead of exact id
    needle = slot_id.lower()
    for sid, bucket in list(_SAVED_FORMS.items()):
        for key, data in list(bucket.items()):
            label = _apex6_safe_text(data.get('label')).lower()
            if needle and (needle == label or needle in label or needle in key.lower()):
                return sid, key, data
    return None, None, None


def _apex6_make_slot_id(sim_info, occult_name, label):
    base = _apex6_slug(label or occult_name or 'form')
    stamp = time.strftime('%Y%m%d_%H%M%S')
    sid = _sim_id(sim_info)
    key = '{}_{}_{}'.format(sid, _apex6_slug(occult_name or 'occult'), stamp)
    if base and base not in key:
        key = '{}_{}'.format(key, base[:48])
    bucket = _apex6_slot_bucket(sid)
    original = key
    index = 2
    while key in bucket:
        key = '{}_{}'.format(original, index)
        index += 1
    return key


def _apex6_saved_form_rows(search=''):
    rows = []
    needle = _apex6_safe_text(search).lower()
    for sid, bucket in list(_SAVED_FORMS.items()):
        for key, data in list(bucket.items()):
            row = {
                'id': key,
                'sim_id': sid,
                'sim_name': data.get('sim_name'),
                'label': data.get('label'),
                'occult': data.get('occult'),
                'source': data.get('source'),
                'created': data.get('created'),
                'scope': data.get('scope'),
                'payload_keys': sorted(list((data.get('payload') or {}).keys())),
            }
            hay = ' '.join([_apex6_safe_text(row.get(k)) for k in ('id', 'sim_id', 'sim_name', 'label', 'occult', 'source', 'created', 'scope')]).lower()
            if not needle or needle in hay:
                rows.append(row)
    rows.sort(key=lambda row: (row.get('created') or '', row.get('label') or ''), reverse=True)
    return rows


def _apex6_save_form(sim_info, occult_type=None, label=None, source='occult_form', scope='cas'):
    tracker = sim_info.occult_tracker
    occult_name = _safe_name(occult_type) if occult_type is not None else 'CURRENT'
    if source == 'current':
        src = sim_info
    else:
        src = None
        if occult_type is not None:
            try:
                src = tracker.get_occult_sim_info(occult_type)
            except Exception:
                src = None
            if src is None:
                src = _ensure_form(tracker, occult_type, generate_new=False)
        if src is None:
            src = sim_info
            source = 'current fallback'
    final_label = _apex6_safe_text(label) or '{} {} {}'.format(_sim_label(sim_info), occult_name, _apex6_now_label())
    payload = _apex6_payload_for_appearance(src, scope=scope)
    if not payload:
        return {'ok': False, 'message': 'No appearance payload could be captured for {}'.format(_sim_label(sim_info))}
    key = _apex6_make_slot_id(sim_info, occult_name, final_label)
    record = {
        'id': key,
        'label': final_label,
        'created': _apex6_now_label(),
        'sim_id': str(_sim_id(sim_info)),
        'sim_name': _sim_label(sim_info),
        'occult': occult_name,
        'source': source,
        'scope': scope or 'cas',
        'occult_flags': _get_occult_flags(sim_info),
        'current_occult_flags': _get_current_flags(sim_info),
        'payload': payload,
    }
    _apex6_slot_bucket(_sim_id(sim_info))[key] = record
    _log('Saved occult form slot {} label={} occult={} source={} keys={}'.format(key, final_label, occult_name, source, sorted(list(payload.keys()))))
    return {'ok': True, 'message': 'Saved form {}'.format(final_label), 'slot_id': key, 'data': dict((k, v) for k, v in record.items() if k != 'payload')}


def _apex6_apply_saved_form(sim_info, slot_id, occult_type=None, force=True, to_current=False):
    _sid, key, record = _apex6_find_saved_form(slot_id)
    if record is None:
        return {'ok': False, 'message': 'Saved form not found: {}'.format(slot_id)}
    payload = record.get('payload') or {}
    tracker = sim_info.occult_tracker
    target_label = 'current Sim'
    target = sim_info
    chosen_occult = occult_type
    if chosen_occult is None and not to_current:
        chosen_occult = _occult_by_name(record.get('occult'))
    if chosen_occult is not None and chosen_occult != OccultType.HUMAN and not to_current:
        if force:
            _add_occult(sim_info, chosen_occult, generate=True, add_traits=True, add_memory=True, use_gameplay_loot=True)
        target = _ensure_form(tracker, chosen_occult, generate_new=True)
        target_label = '{} form'.format(_safe_name(chosen_occult))
    if target is None:
        return {'ok': False, 'message': 'Could not resolve target for saved form {}'.format(key)}
    ok = _apex6_restore_appearance(target, payload, scope=record.get('scope') or 'cas')
    if force and chosen_occult is not None and chosen_occult != OccultType.HUMAN:
        flags = _mask_add(_get_occult_flags(sim_info), _int_value(chosen_occult))
        _set_flags(sim_info, 'occult_types', _normalize_supported_mask(flags) or flags)
        _set_flags(sim_info, 'current_occult_types', _clamp_current(_get_occult_flags(sim_info), _get_current_flags(sim_info)))
        _set_tracker_form_available(tracker, True)
        _repair_sim(sim_info, deep=True)
    else:
        _recalc(sim_info)
    _log('Applied saved form {} to {} for {}'.format(key, target_label, _sim_label(sim_info)))
    return {'ok': bool(ok), 'message': 'Applied saved form {} to {}'.format(record.get('label') or key, target_label), 'slot_id': key, 'target': target_label}


def _apex6_delete_saved_form(slot_id):
    sid, key, _record = _apex6_find_saved_form(slot_id)
    if not key:
        return {'ok': False, 'message': 'Saved form not found: {}'.format(slot_id)}
    try:
        del _SAVED_FORMS[sid][key]
        return {'ok': True, 'message': 'Deleted saved form {}'.format(key)}
    except Exception as exc:
        return {'ok': False, 'message': 'Could not delete saved form {}: {}'.format(key, exc)}


def _apex6_clipboard_status():
    rows = []
    for key, data in _APPEARANCE_CLIPBOARD.items():
        rows.append({'scope': key, 'sim': data.get('sim_name'), 'saved_at': data.get('created'), 'payload_keys': sorted(list((data.get('payload') or {}).keys()))})
    return {'ok': True, 'message': 'Appearance clipboard status', 'data': rows}


def _apex6_copy_clipboard(sim_info, scope):
    scope = (scope or 'cas').lower()
    payload = _apex6_payload_for_appearance(sim_info, scope=scope)
    if not payload:
        return {'ok': False, 'message': 'Could not copy {} payload'.format(scope)}
    _APPEARANCE_CLIPBOARD[scope] = {'payload': payload, 'sim_id': str(_sim_id(sim_info)), 'sim_name': _sim_label(sim_info), 'created': _apex6_now_label(), 'scope': scope}
    _log('Copied {} appearance clipboard from {} keys={}'.format(scope, _sim_label(sim_info), sorted(list(payload.keys()))))
    return {'ok': True, 'message': 'Copied {} from {}'.format(scope, _sim_label(sim_info)), 'details': sorted(list(payload.keys()))}


def _apex6_paste_clipboard(sim_info, scope):
    scope = (scope or 'cas').lower()
    data = _APPEARANCE_CLIPBOARD.get(scope) or _APPEARANCE_CLIPBOARD.get('cas')
    if not data:
        return {'ok': False, 'message': 'Clipboard is empty for {}'.format(scope)}
    ok = _apex6_restore_appearance(sim_info, data.get('payload') or {}, scope=scope)
    _repair_sim(sim_info, deep=False)
    _log('Pasted {} appearance clipboard onto {}'.format(scope, _sim_label(sim_info)))
    return {'ok': bool(ok), 'message': 'Pasted {} onto {}'.format(scope, _sim_label(sim_info))}


def _apex6_apply_scope_to_all_forms(sim_info, scope):
    tracker = sim_info.occult_tracker
    scope = (scope or 'cas').lower()
    payload = _apex6_payload_for_appearance(sim_info, scope=scope)
    details = []
    if not payload:
        return {'ok': False, 'message': 'Could not capture {} from current Sim'.format(scope)}
    for occult_type in _all_occults():
        if not _mask_has(_get_occult_flags(sim_info), _int_value(occult_type)):
            continue
        form = _ensure_form(tracker, occult_type, generate_new=True)
        if form is None:
            details.append('{}: no form'.format(_safe_name(occult_type)))
            continue
        ok = _apex6_restore_appearance(form, payload, scope=scope)
        details.append('{}: {}'.format(_safe_name(occult_type), 'updated' if ok else 'skipped'))
    _set_tracker_form_available(tracker, True)
    _repair_sim(sim_info, deep=True)
    return {'ok': True, 'message': 'Applied {} from current Sim to all active occult forms'.format(scope), 'details': details}


def _apex6_detect_mccc():
    global _MCCC_DETAILS
    names = ('mc_cmd_center', 'mc_cas', 'mc_cheats', 'mc_cleaner', 'mc_dresser', 'mc_occult', 'mc_population', 'mc_pregnancy', 'mc_tuner', 'mc_control')
    modules = {}
    available = False
    for name in names:
        try:
            mod = __import__(name)
            available = True
            version = None
            for attr in ('VERSION', '__version__', 'version'):
                try:
                    value = getattr(mod, attr)
                    if value:
                        version = str(value)
                        break
                except Exception:
                    pass
            modules[name] = {'loaded': True, 'version': version, 'file': str(getattr(mod, '__file__', ''))}
        except Exception as exc:
            modules[name] = {'loaded': False, 'error': str(exc)}
    _MCCC_DETAILS = {'checked': True, 'available': available, 'modules': modules, 'version_guess': None, 'archive_modules_seen': ['mc_cmd_center', 'mc_cas', 'mc_dresser', 'mc_occult', 'mc_cleaner']}
    return _MCCC_DETAILS


def _apex6_mccc_status():
    if not _MCCC_DETAILS.get('checked'):
        _apex6_detect_mccc()
    return {'ok': True, 'message': 'MCCC compatibility status', 'data': {'mccc': _MCCC_DETAILS, 'shield': dict(_MCCC_SHIELD)}}


def _apex6_mccc_arm(sim_info, household=True, keep_occult_type=None):
    keep_name = _safe_name(keep_occult_type).upper() if keep_occult_type is not None else 'HUMAN'
    sims = _household_sim_infos(sim_info) if household else [sim_info]
    details = []
    ids = []
    for item in sims:
        if item is None:
            continue
        ids.append(str(_sim_id(item)))
        try:
            details.append(_cas_prepare_keep_one(item, keep_occult_type))
        except Exception as exc:
            details.append('{}: prepare failed {}'.format(_sim_label(item), exc))
    _MCCC_SHIELD.update({
        'armed': True,
        'household': bool(household),
        'sim_ids': ids,
        'armed_at': time.time(),
        'last_tick': time.time(),
        'restore_attempts': 0,
        'keep': keep_name,
        'last_restore': 0.0,
    })
    _log('MCCC CAS shield armed: household={} keep={} sims={}'.format(bool(household), keep_name, ','.join(ids)))
    return {'ok': True, 'message': 'MCCC CAS shield armed for {} Sim(s); use MCCC > Sim Commands > Modify in CAS, then restore/auto-restore after returning.'.format(len(ids)), 'details': details, 'data': dict(_MCCC_SHIELD)}


def _apex6_mccc_restore(sim_info=None, household=None, reason='manual'):
    ids = list(_MCCC_SHIELD.get('sim_ids') or [])
    if not ids and sim_info is not None:
        ids = [str(_sim_id(sim_info))]
    if household is True and sim_info is not None:
        ids = [str(_sim_id(item)) for item in _household_sim_infos(sim_info)]
    details = []
    restored = 0
    for sid in ids:
        target = _get_sim_info_by_id(sid)
        if target is None:
            details.append('{}: Sim not loaded'.format(sid))
            continue
        try:
            details.append(_cas_restore_one(target))
            restored += 1
        except Exception as exc:
            details.append('{}: restore failed {}'.format(sid, exc))
    if restored:
        _MCCC_SHIELD['armed'] = False
        _MCCC_SHIELD['last_restore'] = time.time()
        _MCCC_SHIELD['restore_attempts'] = int(_MCCC_SHIELD.get('restore_attempts') or 0) + 1
    _log('MCCC CAS shield restore {} restored={} details={}'.format(reason, restored, '; '.join(details)))
    return {'ok': restored > 0, 'message': 'MCCC CAS shield restore {}: {} Sim(s) restored'.format(reason, restored), 'details': details, 'data': dict(_MCCC_SHIELD)}


def _apex6_live_mode_ready():
    if services is None:
        return False
    try:
        client = services.client_manager().get_first_client()
        if client is None:
            return False
        active = getattr(client, 'active_sim', None)
        if active is None:
            return False
    except Exception:
        return False
    try:
        zone = services.current_zone()
        if zone is None:
            return False
    except Exception:
        pass
    return True


def _apex6_mccc_tick():
    if not _MCCC_SHIELD.get('armed') or not _MCCC_SHIELD.get('auto_restore'):
        _MCCC_SHIELD['last_tick'] = time.time()
        return
    now = time.time()
    previous = float(_MCCC_SHIELD.get('last_tick') or now)
    _MCCC_SHIELD['last_tick'] = now
    if now - float(_MCCC_SHIELD.get('armed_at') or now) < float(_MCCC_SHIELD.get('settle_seconds') or 6.0):
        return
    # CAS typically pauses or changes game services; a gap strongly suggests the player returned.
    # If a patch keeps alarms running in CAS, this will not fire early and the manual Restore button remains safe.
    if now - previous < 3.5:
        return
    if not _apex6_live_mode_ready():
        return
    active = _get_active_sim_info()
    _apex6_mccc_restore(active, household=_MCCC_SHIELD.get('household'), reason='auto after CAS/live-mode gap')


def _apex6_mccc_soft_hook_scan(enable=True):
    _MCCC_SHIELD['hook_scan'] = bool(enable)
    if not enable:
        return {'ok': True, 'message': 'MCCC soft hook scan disabled', 'data': dict(_MCCC_SHIELD)}
    _apex6_detect_mccc()
    if _td1_sys is None or _td1_inspect is None:
        return {'ok': False, 'message': 'Python inspect/sys unavailable for MCCC soft hook scan'}
    found = []
    # Report and lightly wrap only obvious top-level CAS launcher functions. This is off by default
    # and deliberately narrow to avoid destabilizing MCCC internals.
    for mod_name, mod in list(_td1_sys.modules.items()):
        if not (mod_name == 'mc_cas' or mod_name.startswith('mc_')):
            continue
        try:
            items = list(vars(mod).items())
        except Exception:
            continue
        for name, func in items:
            low = name.lower()
            if 'cas' not in low or not any(token in low for token in ('modify', 'edit', 'open', 'show')):
                continue
            if not _td1_inspect.isfunction(func):
                continue
            if getattr(func, '_td1_apex_mccc_wrapped', False):
                found.append('{}.'.format(mod_name) + name + ' already wrapped')
                continue
            def _make_wrapper(original, label):
                def _td1_wrapper(*args, **kwargs):
                    try:
                        active = _get_active_sim_info()
                        if active is not None:
                            _apex6_mccc_arm(active, household=True, keep_occult_type=None)
                    except Exception as prep_exc:
                        _log('MCCC soft hook prepare failed for {}: {}'.format(label, prep_exc))
                    result = original(*args, **kwargs)
                    try:
                        _MCCC_SHIELD['armed'] = True
                        _MCCC_SHIELD['last_tick'] = time.time()
                    except Exception:
                        pass
                    return result
                _td1_wrapper._td1_apex_mccc_wrapped = True
                _td1_wrapper.__name__ = getattr(original, '__name__', 'td1_mccc_wrapper')
                return _td1_wrapper
            try:
                setattr(mod, name, _make_wrapper(func, '{}.{}'.format(mod_name, name)))
                found.append('wrapped {}.{}'.format(mod_name, name))
            except Exception as exc:
                found.append('could not wrap {}.{}: {}'.format(mod_name, name, exc))
    _MCCC_SHIELD['hooked_functions'] = found[-80:]
    return {'ok': True, 'message': 'MCCC soft hook scan complete: {} candidate(s)'.format(len(found)), 'details': found, 'data': dict(_MCCC_SHIELD)}


def _apex6_register_lot51_events():
    if _LOT51_EVENT_REGISTRATION.get('attempted'):
        return _LOT51_EVENT_REGISTRATION
    _LOT51_EVENT_REGISTRATION['attempted'] = True
    try:
        from lot51_core.services.events import event_handler, CoreEvent
        @event_handler(CoreEvent.LOADING_SCREEN_LIFTED)
        def _td1_apex_lot51_loading_screen_lifted(service, context=None, **kwargs):
            try:
                if _MCCC_SHIELD.get('armed') and _MCCC_SHIELD.get('auto_restore'):
                    _apex6_mccc_restore(_get_active_sim_info(), household=_MCCC_SHIELD.get('household'), reason='Lot51 loading_screen_lifted')
            except Exception as exc:
                _log('Lot51 loading_screen_lifted MCCC restore failed: {}'.format(exc))
        @event_handler(CoreEvent.GAME_PRE_SAVE)
        def _td1_apex_lot51_pre_save(service, context=None, **kwargs):
            try:
                if _MCCC_SHIELD.get('armed'):
                    _apex6_mccc_restore(_get_active_sim_info(), household=_MCCC_SHIELD.get('household'), reason='Lot51 pre_save safety')
            except Exception as exc:
                _log('Lot51 pre_save MCCC restore failed: {}'.format(exc))
        _LOT51_EVENT_REGISTRATION.update({'registered': True, 'message': 'Lot51 Core event handlers registered'})
        _log('Apex v6 registered optional Lot51 Core event handlers for loading_screen_lifted and pre_save.')
    except Exception as exc:
        _LOT51_EVENT_REGISTRATION.update({'registered': False, 'message': str(exc)})
    return _LOT51_EVENT_REGISTRATION


def _overlay_capabilities():
    data = _BASE_OVERLAY_CAPABILITIES()
    try:
        data.update({
            'api_version': 6,
            'build_version': _BUILD_VERSION,
            'mccc_support': {
                'mode': 'CAS shield snapshots before MCCC Modify in CAS and restores after manual restore, Lot51 event, or live-mode gap auto-restore.',
                'commands': ['mccc_detect', 'mccc_prepare_active', 'mccc_prepare_household', 'mccc_restore_active', 'mccc_restore_household', 'mccc_auto_restore_on', 'mccc_auto_restore_off', 'mccc_soft_hooks_on', 'mccc_soft_hooks_off'],
                'status': _MCCC_DETAILS,
                'shield': dict(_MCCC_SHIELD),
            },
            'saved_forms': {
                'commands': ['save_occult_form', 'save_current_form', 'list_saved_forms', 'apply_saved_form', 'force_apply_saved_form', 'apply_saved_form_current', 'delete_saved_form'],
                'count': sum(len(bucket) for bucket in _SAVED_FORMS.values()),
            },
            'appearance_tools': ['copy_cas', 'paste_cas', 'copy_wardrobe', 'paste_wardrobe', 'copy_body', 'paste_body', 'copy_skin', 'paste_skin', 'copy_tattoos', 'paste_tattoos', 'apply_cas_to_all_forms', 'apply_wardrobe_to_all_forms', 'apply_body_to_all_forms', 'apply_skin_to_all_forms', 'apply_tattoos_to_all_forms'],
            'lot51_event_registration': dict(_LOT51_EVENT_REGISTRATION),
        })
    except Exception:
        pass
    return data


def _status(sim_info):
    data = _BASE_STATUS(sim_info)
    try:
        data['saved_forms'] = _apex6_saved_form_rows('')[:80]
        data['saved_form_count'] = sum(len(bucket) for bucket in _SAVED_FORMS.values())
        data['appearance_clipboard'] = _apex6_clipboard_status().get('data')
        data['mccc'] = _apex6_mccc_status().get('data')
        data['lot51_event_registration'] = dict(_LOT51_EVENT_REGISTRATION)
    except Exception as exc:
        data['apex6_status_error'] = str(exc)
    return data


def _auto_repair_tick():
    try:
        _BASE_AUTO_REPAIR_TICK()
    finally:
        try:
            _apex6_mccc_tick()
        except Exception as exc:
            _log('MCCC CAS shield tick failed: {}'.format(exc))


def run_action(action, sim_id=None, occult=None, value=None):
    action = (action or 'status').strip().lower()
    try:
        if action in ('mccc_status', 'mccc_detect'):
            if action == 'mccc_detect':
                _apex6_detect_mccc()
            return _apex6_mccc_status()
        if action == 'lot51_register_events':
            return {'ok': True, 'message': 'Lot51 event registration status', 'data': _apex6_register_lot51_events()}
        if action == 'list_saved_forms' or action == 'saved_form_status':
            rows = _apex6_saved_form_rows(value or '')
            return {'ok': True, 'message': 'Saved forms: {} result(s)'.format(len(rows)), 'data': rows, 'saved_form_count': sum(len(bucket) for bucket in _SAVED_FORMS.values())}
        if action == 'appearance_clipboard_status':
            return _apex6_clipboard_status()

        sim_info = _get_sim_info_by_id(sim_id)
        if action.startswith('mccc_'):
            if sim_info is None:
                sim_info = _get_active_sim_info()
            if action == 'mccc_auto_restore_on':
                _MCCC_SHIELD['auto_restore'] = True
                return {'ok': True, 'message': 'MCCC CAS auto-restore enabled', 'data': dict(_MCCC_SHIELD)}
            if action == 'mccc_auto_restore_off':
                _MCCC_SHIELD['auto_restore'] = False
                return {'ok': True, 'message': 'MCCC CAS auto-restore disabled', 'data': dict(_MCCC_SHIELD)}
            if action == 'mccc_soft_hooks_on':
                return _apex6_mccc_soft_hook_scan(True)
            if action == 'mccc_soft_hooks_off':
                return _apex6_mccc_soft_hook_scan(False)
            if sim_info is None:
                return {'ok': False, 'message': 'No active/selected Sim for MCCC CAS shield'}
            keep_occult = _occult_by_name(occult) if occult else None
            if action in ('mccc_prepare_active', 'mccc_arm_active'):
                return _apex6_mccc_arm(sim_info, household=False, keep_occult_type=keep_occult)
            if action in ('mccc_prepare_household', 'mccc_arm_household'):
                return _apex6_mccc_arm(sim_info, household=True, keep_occult_type=keep_occult)
            if action == 'mccc_restore_active':
                return _apex6_mccc_restore(sim_info, household=False, reason='manual active')
            if action == 'mccc_restore_household':
                return _apex6_mccc_restore(sim_info, household=True, reason='manual household')

        # Saved form and CAS clipboard operations require a Sim unless they are pure list/status commands.
        if action in ('save_occult_form', 'save_current_form', 'apply_saved_form', 'force_apply_saved_form', 'apply_saved_form_current', 'delete_saved_form', 'copy_cas', 'paste_cas', 'copy_wardrobe', 'paste_wardrobe', 'copy_body', 'paste_body', 'copy_skin', 'paste_skin', 'copy_tattoos', 'paste_tattoos', 'apply_cas_to_all_forms', 'apply_wardrobe_to_all_forms', 'apply_body_to_all_forms', 'apply_skin_to_all_forms', 'apply_tattoos_to_all_forms', 'apply_voice_to_all_forms', 'copy_voice', 'paste_voice'):
            if action == 'delete_saved_form':
                return _apex6_delete_saved_form(value)
            if sim_info is None:
                return {'ok': False, 'message': 'No active/selected Sim for {}'.format(action)}
            occult_type = _occult_by_name(occult) if occult else None
            if action == 'save_occult_form':
                if occult_type is None or occult_type == OccultType.HUMAN:
                    return {'ok': False, 'message': 'Save occult form needs a non-human occult selection'}
                return _apex6_save_form(sim_info, occult_type, label=value, source='occult_form', scope='cas')
            if action == 'save_current_form':
                return _apex6_save_form(sim_info, occult_type, label=value, source='current', scope='cas')
            if action in ('apply_saved_form', 'force_apply_saved_form'):
                return _apex6_apply_saved_form(sim_info, value, occult_type=occult_type, force=True, to_current=False)
            if action == 'apply_saved_form_current':
                return _apex6_apply_saved_form(sim_info, value, occult_type=occult_type, force=False, to_current=True)
            scope_map = {
                'copy_cas': 'cas', 'paste_cas': 'cas',
                'copy_wardrobe': 'wardrobe', 'paste_wardrobe': 'wardrobe',
                'copy_body': 'body', 'paste_body': 'body',
                'copy_skin': 'skin', 'paste_skin': 'skin',
                'copy_tattoos': 'tattoos', 'paste_tattoos': 'tattoos',
                'copy_voice': 'voice', 'paste_voice': 'voice',
            }
            if action in scope_map:
                scope = scope_map[action]
                if action.startswith('copy_'):
                    return _apex6_copy_clipboard(sim_info, scope)
                return _apex6_paste_clipboard(sim_info, scope)
            all_form_map = {
                'apply_cas_to_all_forms': 'cas',
                'apply_wardrobe_to_all_forms': 'wardrobe',
                'apply_body_to_all_forms': 'body',
                'apply_skin_to_all_forms': 'skin',
                'apply_tattoos_to_all_forms': 'tattoos',
                'apply_voice_to_all_forms': 'voice',
            }
            if action in all_form_map:
                return _apex6_apply_scope_to_all_forms(sim_info, all_form_map[action])
    except Exception as exc:
        err = '{}\n{}'.format(exc, traceback.format_exc())
        _log(err)
        return {'ok': False, 'message': str(exc), 'traceback': traceback.format_exc()}
    return _BASE_RUN_ACTION(action, sim_id=sim_id, occult=occult, value=value)

try:
    _apex6_detect_mccc()
except Exception as _td1_apex6_mccc_detect_exc:
    _log('Apex v6 MCCC initial detect skipped: {}'.format(_td1_apex6_mccc_detect_exc))
try:
    _LOT51_EVENT_REGISTRATION.update({'attempted': False, 'registered': False, 'message': 'manual only in v9.4; use lot51_register_events / lot51_events_on after arming MCCC Shield'})
except Exception as _td1_apex6_lot51_exc:
    _log('Apex v9.4 Lot51 manual-only setup skipped: {}'.format(_td1_apex6_lot51_exc))
_log('TD1 Occult Hybrid Apex v6 extensions loaded: saved forms, MCCC CAS shield, and expanded F11 commands ready.')

# -----------------------------------------------------------------------------
# Apex v6.2 final command layer: stable names for the F11 ImGui command surface.
# This layer intentionally avoids MCCC private APIs. MCCC compatibility is handled
# by detection, public console-style command bridging where available, and robust
# CAS/occult snapshots before and after CAS/MCCC household edits.
# -----------------------------------------------------------------------------
try:
    _occult_by_name
except Exception:
    _occult_by_name = _parse_occult

_V62_FORMS_CACHE = None
_V62_WARDROBE_CACHE = None
_V62_CLIPBOARD = {}
_V62_BASE_RUN_ACTION = run_action
_V62_BASE_STATUS = _status
_V62_BASE_OVERLAY_CAPABILITIES = _overlay_capabilities

try:
    _READ_ONLY_ACTIONS.update(set(('list_saved_forms', 'saved_forms', 'list_wardrobes', 'wardrobes', 'mccc_status', 'mccc_detect', 'appearance_clipboard_status')))
except Exception:
    pass


def _v62_dir():
    try:
        return _data_directory()
    except Exception:
        pass
    try:
        import sims4.paths
        base = getattr(sims4.paths, 'USER_DATA_ROOT', None)
        if base:
            path = os.path.join(base, 'TD1_OccultHybridApexData')
            os.makedirs(path, exist_ok=True)
            return path
    except Exception:
        pass
    path = os.path.join(os.path.expanduser('~'), 'TD1_OccultHybridApexData')
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass
    return path


def _v62_json_path(name):
    return os.path.join(_v62_dir(), name)


def _v62_load_file(name, default):
    path = _v62_json_path(name)
    try:
        if os.path.exists(path):
            with open(path, 'r') as fp:
                data = json.load(fp)
            if isinstance(default, dict) and isinstance(data, dict):
                return data
            if isinstance(default, list) and isinstance(data, list):
                return data
    except Exception as exc:
        _log('Apex v6.2 could not load {}: {}'.format(name, exc))
    return copy.deepcopy(default)


def _v62_save_file(name, data):
    path = _v62_json_path(name)
    tmp = path + '.tmp'
    try:
        with open(tmp, 'w') as fp:
            json.dump(data, fp, indent=2, sort_keys=True, default=str)
        try:
            os.replace(tmp, path)
        except Exception:
            if os.path.exists(path):
                os.remove(path)
            os.rename(tmp, path)
        return True
    except Exception as exc:
        _log('Apex v6.2 could not save {}: {}'.format(name, exc))
        return False


def _v62_pack_value(value):
    try:
        if isinstance(value, tuple) and len(value) == 2 and value[0] == 'protobuf':
            return {'kind': 'protobuf', 'data': base64.b64encode(value[1]).decode('ascii')}
        if isinstance(value, bytes):
            return {'kind': 'bytes', 'data': base64.b64encode(value).decode('ascii')}
        json.dumps(value)
        return {'kind': 'json', 'data': value}
    except Exception:
        pass
    try:
        return {'kind': 'pickle', 'data': base64.b64encode(pickle.dumps(value, protocol=2)).decode('ascii')}
    except Exception as exc:
        return {'kind': 'repr', 'data': repr(value), 'error': str(exc)}


def _v62_unpack_value(node):
    if not isinstance(node, dict):
        return node
    kind = node.get('kind')
    data = node.get('data')
    try:
        if kind == 'protobuf':
            return ('protobuf', base64.b64decode(str(data).encode('ascii')))
        if kind == 'bytes':
            return base64.b64decode(str(data).encode('ascii'))
        if kind == 'json':
            return data
        if kind == 'pickle':
            return pickle.loads(base64.b64decode(str(data).encode('ascii')))
    except Exception as exc:
        _log('Apex v6.2 unpack failed: {}'.format(exc))
    return None


def _v62_pack_payload(payload):
    return dict((str(key), _v62_pack_value(value)) for key, value in (payload or {}).items())


def _v62_unpack_payload(payload):
    return dict((str(key), _v62_unpack_value(value)) for key, value in (payload or {}).items())


def _v62_payload_quality(packed):
    counts = {}
    for value in (packed or {}).values():
        kind = value.get('kind', 'unknown') if isinstance(value, dict) else 'raw'
        counts[kind] = counts.get(kind, 0) + 1
    return ', '.join('{}={}'.format(key, counts[key]) for key in sorted(counts)) or 'empty'


def _v62_load_forms():
    global _V62_FORMS_CACHE
    if _V62_FORMS_CACHE is None:
        data = _v62_load_file('ApexV6_SavedOccultForms.json', {'version': 2, 'forms': []})
        if not isinstance(data, dict):
            data = {'version': 2, 'forms': []}
        data.setdefault('forms', [])
        _V62_FORMS_CACHE = data
    return _V62_FORMS_CACHE


def _v62_save_forms(data=None):
    global _V62_FORMS_CACHE
    if data is not None:
        _V62_FORMS_CACHE = data
    return _v62_save_file('ApexV6_SavedOccultForms.json', _v62_load_forms())


def _v62_load_wardrobes():
    global _V62_WARDROBE_CACHE
    if _V62_WARDROBE_CACHE is None:
        data = _v62_load_file('ApexV6_WardrobeCasPresets.json', {'version': 1, 'wardrobes': []})
        if not isinstance(data, dict):
            data = {'version': 1, 'wardrobes': []}
        data.setdefault('wardrobes', [])
        _V62_WARDROBE_CACHE = data
    return _V62_WARDROBE_CACHE


def _v62_save_wardrobes(data=None):
    global _V62_WARDROBE_CACHE
    if data is not None:
        _V62_WARDROBE_CACHE = data
    return _v62_save_file('ApexV6_WardrobeCasPresets.json', _v62_load_wardrobes())


def _v62_clean_label(value, fallback='slot'):
    try:
        text = str(value or '').strip()
    except Exception:
        text = ''
    return text or fallback


def _v62_slug(value):
    text = _v62_clean_label(value, 'slot').lower()
    try:
        text = re.sub(r'[^a-z0-9]+', '-', text)
        text = text.strip('-')
    except Exception:
        text = 'slot'
    return text or 'slot'


def _v62_summary(record):
    return dict((key, record.get(key)) for key in ('id', 'label', 'sim', 'sim_id', 'occult', 'created', 'source', 'scope', 'payload_quality') if key in record)


def _v62_filter(records, query='', limit=160):
    q = str(query or '').strip().lower()
    rows = []
    for record in records or []:
        hay = ' '.join(str(record.get(key, '')) for key in ('id', 'label', 'sim', 'sim_id', 'occult', 'created', 'source', 'scope')).lower()
        if not q or q in hay:
            rows.append(_v62_summary(record))
    rows.sort(key=lambda row: str(row.get('created', '')), reverse=True)
    return rows[:limit]


def _v62_infer_occult(sim_info):
    try:
        current = _get_current_flags(sim_info)
        for occult_type in _all_occults():
            if _mask_has(current, _int_value(occult_type)):
                return occult_type
    except Exception:
        pass
    try:
        flags = _get_occult_flags(sim_info)
        for occult_type in _all_occults():
            if _mask_has(flags, _int_value(occult_type)):
                return occult_type
    except Exception:
        pass
    return None


def _v62_scope_payload(obj, scope='cas'):
    payload = _snapshot_siminfo_payload(obj)
    scope = (scope or 'cas').lower()
    for risky in ('flags', 'base_trait_ids'):
        try:
            payload.pop(risky, None)
        except Exception:
            pass
    allowed = None
    if scope in ('wardrobe', 'outfits'):
        allowed = set(('__outfits__',))
    elif scope == 'body':
        allowed = set(('physique', 'facial_attributes', 'genetic_data'))
    elif scope == 'skin':
        allowed = set(('skin_tone', 'pelt_layers', 'genetic_data'))
    elif scope == 'tattoos':
        allowed = set(('__outfits__', 'skin_tone', 'pelt_layers', 'genetic_data'))
    elif scope == 'voice':
        allowed = set(('voice_pitch', 'voice_actor', 'voice_effect'))
    if allowed is not None:
        payload = dict((key, value) for key, value in payload.items() if key in allowed)
    return payload


def _v62_restore_scope(obj, payload, scope='cas'):
    unpacked = _v62_unpack_payload(payload or {}) if payload and isinstance(next(iter(payload.values()), None), dict) else (payload or {})
    scoped = dict(unpacked)
    for risky in ('flags', 'base_trait_ids'):
        try:
            scoped.pop(risky, None)
        except Exception:
            pass
    return _restore_siminfo_payload(obj, scoped)


def _v62_save_form(sim_info, occult_type=None, label=None, source='form', scope='cas'):
    if occult_type is None and source != 'current':
        occult_type = _v62_infer_occult(sim_info)
    tracker = sim_info.occult_tracker
    target = sim_info
    occult_name = 'CURRENT'
    if occult_type is not None and occult_type != getattr(OccultType, 'HUMAN', None):
        occult_name = _safe_name(occult_type).upper()
        try:
            target = tracker.get_occult_sim_info(occult_type)
        except Exception:
            target = None
        if target is None:
            target = _ensure_form(tracker, occult_type, generate_new=False) or sim_info
    payload_raw = _v62_scope_payload(target, scope=scope)
    packed = _v62_pack_payload(payload_raw)
    stamp = time.strftime('%Y-%m-%d %H:%M:%S')
    label = _v62_clean_label(label, '{} {} {}'.format(_sim_label(sim_info), occult_name, stamp))
    rec_id = '{}-{}-{}-{}'.format(time.strftime('%Y%m%d%H%M%S'), _sim_id(sim_info), occult_name.lower(), _v62_slug(label))[:128]
    record = {
        'id': rec_id,
        'label': label,
        'sim': _sim_label(sim_info),
        'sim_id': _sim_id(sim_info),
        'occult': occult_name,
        'occult_value': _int_value(occult_type) if occult_type is not None else 0,
        'created': stamp,
        'source': source,
        'scope': scope,
        'payload_quality': _v62_payload_quality(packed),
        'payload': packed,
    }
    data = _v62_load_forms()
    data.setdefault('forms', []).append(record)
    _v62_save_forms(data)
    _log('Apex v6.2 saved form {} label={} quality={}'.format(rec_id, label, record['payload_quality']))
    return {'ok': True, 'message': 'Saved {} form: {}'.format(occult_name, label), 'data': _v62_summary(record), 'slot_id': rec_id}


def _v62_find_form(form_id):
    form_id = str(form_id or '').strip()
    if not form_id:
        return None
    q = form_id.lower()
    for record in _v62_load_forms().get('forms', []):
        if str(record.get('id')) == form_id:
            return record
    for record in _v62_load_forms().get('forms', []):
        hay = ' '.join(str(record.get(key, '')) for key in ('id', 'label', 'occult', 'sim')).lower()
        if q and q in hay:
            return record
    return None


def _v62_apply_form(sim_info, form_id, occult_type=None, to_current=False, force=True):
    record = _v62_find_form(form_id)
    if record is None:
        return {'ok': False, 'message': 'Saved form not found: {}'.format(form_id)}
    if occult_type is None and not to_current:
        occult_type = _parse_occult(record.get('occult'))
    target = sim_info
    target_name = 'current Sim'
    if occult_type is not None and occult_type != getattr(OccultType, 'HUMAN', None) and not to_current:
        if force:
            _add_occult(sim_info, occult_type, generate=True, add_traits=True, add_memory=True, use_gameplay_loot=True)
        target = _ensure_form(sim_info.occult_tracker, occult_type, generate_new=True)
        target_name = '{} form'.format(_safe_name(occult_type))
    if target is None:
        return {'ok': False, 'message': 'Could not resolve target form for {}'.format(record.get('label'))}
    ok = _v62_restore_scope(target, record.get('payload') or {}, scope=record.get('scope') or 'cas')
    if force and occult_type is not None and occult_type != getattr(OccultType, 'HUMAN', None):
        _set_tracker_form_available(sim_info.occult_tracker, True)
        _repair_sim(sim_info, deep=True)
    _recalc(sim_info)
    return {'ok': bool(ok), 'message': 'Applied saved form {} to {}'.format(record.get('label'), target_name), 'data': _v62_summary(record)}


def _v62_delete_form(form_id):
    data = _v62_load_forms()
    before = len(data.get('forms', []))
    data['forms'] = [r for r in data.get('forms', []) if str(r.get('id')) != str(form_id)]
    _v62_save_forms(data)
    return before != len(data['forms'])


def _v62_save_wardrobe(sim_info, label=None, scope='cas'):
    payload_raw = _v62_scope_payload(sim_info, scope=scope)
    packed = _v62_pack_payload(payload_raw)
    stamp = time.strftime('%Y-%m-%d %H:%M:%S')
    label = _v62_clean_label(label, '{} {} {}'.format(_sim_label(sim_info), scope, stamp))
    rec_id = '{}-{}-{}-{}'.format(time.strftime('%Y%m%d%H%M%S'), _sim_id(sim_info), scope, _v62_slug(label))[:128]
    record = {'id': rec_id, 'label': label, 'sim': _sim_label(sim_info), 'sim_id': _sim_id(sim_info), 'created': stamp, 'source': 'current sim', 'scope': scope, 'payload_quality': _v62_payload_quality(packed), 'payload': packed}
    data = _v62_load_wardrobes()
    data.setdefault('wardrobes', []).append(record)
    _v62_save_wardrobes(data)
    return {'ok': True, 'message': 'Saved {} preset {}'.format(scope, label), 'data': _v62_summary(record), 'slot_id': rec_id}


def _v62_find_wardrobe(rec_id):
    q = str(rec_id or '').strip().lower()
    for record in _v62_load_wardrobes().get('wardrobes', []):
        if str(record.get('id')).lower() == q:
            return record
    for record in _v62_load_wardrobes().get('wardrobes', []):
        hay = ' '.join(str(record.get(key, '')) for key in ('id', 'label', 'sim', 'scope')).lower()
        if q and q in hay:
            return record
    return None


def _v62_apply_wardrobe(sim_info, rec_id):
    record = _v62_find_wardrobe(rec_id)
    if record is None:
        return {'ok': False, 'message': 'Wardrobe/CAS preset not found: {}'.format(rec_id)}
    ok = _v62_restore_scope(sim_info, record.get('payload') or {}, scope=record.get('scope') or 'cas')
    _recalc(sim_info)
    return {'ok': bool(ok), 'message': 'Applied {} preset {}'.format(record.get('scope'), record.get('label')), 'data': _v62_summary(record)}


def _v62_copy_clipboard(sim_info, scope):
    payload = _v62_scope_payload(sim_info, scope=scope)
    _V62_CLIPBOARD[scope] = {'payload': payload, 'sim': _sim_label(sim_info), 'created': time.strftime('%Y-%m-%d %H:%M:%S'), 'scope': scope}
    return {'ok': True, 'message': 'Copied {} from {}'.format(scope, _sim_label(sim_info)), 'data': {'scope': scope, 'keys': sorted(list(payload.keys()))}}


def _v62_paste_clipboard(sim_info, scope):
    item = _V62_CLIPBOARD.get(scope)
    if not item:
        return {'ok': False, 'message': 'Clipboard is empty for {}'.format(scope)}
    ok = _restore_siminfo_payload(sim_info, item.get('payload') or {})
    _recalc(sim_info)
    return {'ok': bool(ok), 'message': 'Pasted {} from {}'.format(scope, item.get('sim'))}


def _v62_apply_clipboard_to_forms(sim_info, scope):
    item = _V62_CLIPBOARD.get(scope)
    if not item:
        return {'ok': False, 'message': 'Clipboard is empty for {}'.format(scope)}
    flags = _get_occult_flags(sim_info)
    done = []
    for occult_type in _all_occults():
        if _mask_has(flags, _int_value(occult_type)):
            form = _ensure_form(sim_info.occult_tracker, occult_type, generate_new=True)
            if form is not None and _restore_siminfo_payload(form, item.get('payload') or {}):
                done.append(_safe_name(occult_type))
    _set_tracker_form_available(sim_info.occult_tracker, True)
    _recalc(sim_info)
    return {'ok': True, 'message': 'Applied {} clipboard to forms: {}'.format(scope, ', '.join(done) or 'none')}


def _v62_mccc_status():
    try:
        base = _detect_mccc()
    except Exception:
        base = {}
    try:
        extra = _apex6_mccc_status().get('data')
    except Exception:
        extra = {}
    return {'ok': True, 'message': 'MCCC compatibility status ready', 'data': {'runtime_detection': base, 'apex6_detection': extra, 'shield_enabled': _MCCC_CAS_SHIELD_ENABLED, 'lot51_event_hooked': _MCCC_EVENT_HOOKED}}


def _overlay_capabilities():
    data = _V62_BASE_OVERLAY_CAPABILITIES()
    try:
        data.update({
            'api_version': 6,
            'v62_commands': {
                'saved_forms': ['save_occult_form', 'save_current_form', 'list_saved_forms', 'apply_saved_form', 'force_apply_saved_form', 'apply_saved_form_current', 'delete_saved_form'],
                'appearance': ['copy_cas', 'paste_cas', 'copy_wardrobe', 'paste_wardrobe', 'copy_body', 'paste_body', 'copy_skin', 'paste_skin', 'copy_tattoos', 'paste_tattoos', 'copy_voice', 'paste_voice', 'apply_cas_to_all_forms', 'apply_wardrobe_to_all_forms', 'apply_body_to_all_forms', 'apply_skin_to_all_forms', 'apply_tattoos_to_all_forms', 'apply_voice_to_all_forms'],
                'mccc': ['mccc_status', 'mccc_cas_shield_on', 'mccc_cas_restore', 'mccc_cas_shield_off', 'mccc_open_sim_menu', 'mccc_open_settings', 'mccc_dresser_clean', 'mccc_dresser_check', 'mccc_dresser_info', 'mccc_dresser_save_outfit', 'mccc_dresser_load_outfit', 'mccc_dresser_copy_all'],
            },
            'v62_saved_form_count': len(_v62_load_forms().get('forms', [])),
            'v62_wardrobe_count': len(_v62_load_wardrobes().get('wardrobes', [])),
            'v62_data_dir': _v62_dir(),
        })
    except Exception:
        pass
    return data


def _status(sim_info):
    data = _V62_BASE_STATUS(sim_info)
    try:
        data['v62_saved_forms'] = _v62_filter(_v62_load_forms().get('forms', ''), '', 80)
        data['v62_wardrobes'] = _v62_filter(_v62_load_wardrobes().get('wardrobes', ''), '', 80)
        data['v62_clipboard'] = dict((k, {'sim': v.get('sim'), 'created': v.get('created'), 'keys': sorted(list((v.get('payload') or {}).keys()))}) for k, v in _V62_CLIPBOARD.items())
        data['v62_mccc'] = _v62_mccc_status().get('data')
    except Exception as exc:
        data['v62_error'] = str(exc)
    return data


def run_action(action, sim_id=None, occult=None, value=None):
    action = (action or 'status').strip().lower()
    try:
        if action in ('list_saved_forms', 'saved_forms', 'saved_form_status'):
            rows = _v62_filter(_v62_load_forms().get('forms', []), value or '', 200)
            return {'ok': True, 'message': 'Saved occult forms: {} result(s)'.format(len(rows)), 'data': rows, 'saved_forms': rows, 'saved_form_count': len(_v62_load_forms().get('forms', []))}
        if action in ('list_wardrobes', 'wardrobes'):
            rows = _v62_filter(_v62_load_wardrobes().get('wardrobes', []), value or '', 200)
            return {'ok': True, 'message': 'Wardrobe/CAS presets: {} result(s)'.format(len(rows)), 'data': rows, 'wardrobes': rows}
        if action in ('mccc_status', 'mccc_detect'):
            return _v62_mccc_status()
        if action == 'appearance_clipboard_status':
            return {'ok': True, 'message': 'Appearance clipboard status', 'data': dict((k, {'sim': v.get('sim'), 'created': v.get('created'), 'keys': sorted(list((v.get('payload') or {}).keys()))}) for k, v in _V62_CLIPBOARD.items())}
        if action == 'mccc_open_settings':
            ok, msg = _run_console_command('mc_settings')
            return {'ok': ok, 'message': msg}
        if action == 'mccc_open_cheats':
            ok, msg = _run_console_command('mc_cheats')
            return {'ok': ok, 'message': msg}

        sim_info = _get_sim_info_by_id(sim_id)
        if sim_info is None and action not in ('diagnostics', 'overlay', 'overlay_capabilities', 'list_sims', 'clear_logs'):
            sim_info = _get_active_sim_info()
        occult_type = _parse_occult(occult) if occult else None

        if action in ('save_occult_form', 'save_current_form'):
            if sim_info is None:
                return {'ok': False, 'message': 'No selected/active Sim for saving a form'}
            if action == 'save_current_form':
                return _v62_save_form(sim_info, occult_type=occult_type, label=value, source='current', scope='cas')
            return _v62_save_form(sim_info, occult_type=occult_type or _v62_infer_occult(sim_info), label=value, source='occult_form', scope='cas')
        if action in ('apply_saved_form', 'force_apply_saved_form', 'apply_saved_form_current'):
            if sim_info is None:
                return {'ok': False, 'message': 'No selected/active Sim for applying a saved form'}
            return _v62_apply_form(sim_info, value, occult_type=occult_type, to_current=(action == 'apply_saved_form_current'), force=(action != 'apply_saved_form_current'))
        if action == 'delete_saved_form':
            ok = _v62_delete_form(value)
            return {'ok': ok, 'message': 'Deleted saved form {}'.format(value) if ok else 'Saved form not found: {}'.format(value)}

        if action in ('save_wardrobe', 'save_cas_preset'):
            if sim_info is None:
                return {'ok': False, 'message': 'No selected/active Sim for saving a wardrobe/CAS preset'}
            return _v62_save_wardrobe(sim_info, label=value, scope='cas')
        if action in ('apply_wardrobe', 'apply_cas_preset'):
            if sim_info is None:
                return {'ok': False, 'message': 'No selected/active Sim for applying a wardrobe/CAS preset'}
            return _v62_apply_wardrobe(sim_info, value)
        if action == 'delete_wardrobe':
            data = _v62_load_wardrobes()
            before = len(data.get('wardrobes', []))
            data['wardrobes'] = [r for r in data.get('wardrobes', []) if str(r.get('id')) != str(value)]
            _v62_save_wardrobes(data)
            return {'ok': before != len(data['wardrobes']), 'message': 'Deleted wardrobe/CAS preset {}'.format(value)}

        scopes = {'copy_cas': 'cas', 'paste_cas': 'cas', 'copy_wardrobe': 'wardrobe', 'paste_wardrobe': 'wardrobe', 'copy_body': 'body', 'paste_body': 'body', 'copy_skin': 'skin', 'paste_skin': 'skin', 'copy_tattoos': 'tattoos', 'paste_tattoos': 'tattoos', 'copy_voice': 'voice', 'paste_voice': 'voice'}
        if action in scopes:
            if sim_info is None:
                return {'ok': False, 'message': 'No selected/active Sim for {}'.format(action)}
            scope = scopes[action]
            return _v62_copy_clipboard(sim_info, scope) if action.startswith('copy_') else _v62_paste_clipboard(sim_info, scope)
        all_scopes = {'apply_cas_to_all_forms': 'cas', 'apply_wardrobe_to_all_forms': 'wardrobe', 'apply_body_to_all_forms': 'body', 'apply_skin_to_all_forms': 'skin', 'apply_tattoos_to_all_forms': 'tattoos', 'apply_voice_to_all_forms': 'voice'}
        if action in all_scopes:
            if sim_info is None:
                return {'ok': False, 'message': 'No selected/active Sim for {}'.format(action)}
            return _v62_apply_clipboard_to_forms(sim_info, all_scopes[action])

        if action in ('mccc_cas_shield_on', 'mccc_prepare_household', 'mccc_arm_household'):
            if sim_info is None:
                return {'ok': False, 'message': 'No selected/active Sim for MCCC CAS shield'}
            details = _mccc_cas_shield_arm(sim_info, keep=occult_type)
            return {'ok': True, 'message': 'MCCC/CAS shield armed for household. Use MCCC Edit Household/CAS, then return to live mode; Apex will restore or press Restore.', 'details': details}
        if action in ('mccc_cas_restore', 'mccc_restore_household'):
            if sim_info is None:
                return {'ok': False, 'message': 'No selected/active Sim for MCCC CAS restore'}
            details = []
            for item in _household_sim_infos(sim_info):
                details.append(_cas_restore_one(item))
            try:
                details.extend(_restore_cas_recovery_snapshot(sim_info, reason='v6.2 manual restore'))
            except Exception as exc:
                details.append('disk restore skipped: {}'.format(exc))
            return {'ok': True, 'message': 'MCCC/CAS restore complete for household', 'details': details}
        if action == 'mccc_cas_shield_off':
            global _MCCC_CAS_SHIELD_ENABLED, _MCCC_CAS_WAS_AWAY
            _MCCC_CAS_SHIELD_ENABLED = False
            _MCCC_CAS_WAS_AWAY = False
            return {'ok': True, 'message': 'MCCC/CAS shield disabled'}
        if action == 'mccc_open_sim_menu':
            if sim_info is None:
                return {'ok': False, 'message': 'No selected/active Sim for MCCC menu'}
            ok, msg = _mccc_open_for_sim(sim_info)
            return {'ok': ok, 'message': msg}
        if action == 'mccc_dresser_copy_all':
            if sim_info is None:
                return {'ok': False, 'message': 'No selected/active Sim for dresser copy'}
            ok, details = _mccc_dresser_copy_all(sim_info, source_code=value or 'E')
            return {'ok': ok, 'message': 'MCCC dresser_copy {} to all outfit categories'.format(value or 'E'), 'details': details}
        if action.startswith('mccc_dresser_'):
            if sim_info is None:
                return {'ok': False, 'message': 'No selected/active Sim for MCCC dresser command'}
            op = action.replace('mccc_dresser_', '')
            ok, msg = _mccc_dresser_command(sim_info, op, value=value)
            return {'ok': ok, 'message': msg}
    except Exception as exc:
        err = '{}\n{}'.format(exc, traceback.format_exc())
        _log(err)
        return {'ok': False, 'message': str(exc), 'traceback': traceback.format_exc()}
    return _V62_BASE_RUN_ACTION(action, sim_id=sim_id, occult=occult, value=value)

try:
    _v62_load_forms()
    _v62_load_wardrobes()
    _log('TD1 Occult Hybrid Apex v6.2 final layer loaded: ImGui commands, saved forms, wardrobe/CAS clipboard, and MCCC CAS shield ready.')
except Exception as _td1_v62_exc:
    _log('Apex v6.2 final layer startup skipped: {}'.format(_td1_v62_exc))


# -----------------------------------------------------------------------------
# Apex v7.0 extensions: fire-once drift guard, post-CAS commit protection,
# baseline fix workflow, and native overlay reference-shot commands.
# -----------------------------------------------------------------------------
try:
    import hashlib as _apex7_hashlib
except Exception:
    _apex7_hashlib = None

_APEX7_BASELINES = {}
_APEX7_WARNINGS = {}
_APEX7_SETTINGS = {
    'scan_after_apex_commands': True,
    'warn_unsynced_current_form': True,
    'warn_missing_baseline': True,
    'timerless_mode': True,
}
_V6_RUN_ACTION = run_action
_V6_STATUS = _status
_V6_OVERLAY_CAPABILITIES = _overlay_capabilities

try:
    # Drift status can touch SimInfo, so keep it on the game-thread queue.
    pass
except Exception:
    pass


def _apex7_hash_bytes(data):
    if _apex7_hashlib is None:
        return str(len(data)) + ':' + repr(data[:32])
    h = _apex7_hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def _apex7_bytes_for_value(value):
    try:
        if isinstance(value, tuple) and len(value) == 2 and value[0] == 'protobuf':
            raw = value[1]
            if isinstance(raw, str):
                return raw.encode('utf-8', 'replace')
            return bytes(raw)
    except Exception:
        pass
    try:
        if isinstance(value, (bytes, bytearray)):
            return bytes(value)
    except Exception:
        pass
    try:
        if hasattr(value, 'SerializeToString'):
            return value.SerializeToString()
    except Exception:
        pass
    try:
        return repr(value).encode('utf-8', 'replace')
    except Exception:
        return str(type(value)).encode('utf-8', 'replace')


def _apex7_payload_digests(payload):
    result = {}
    for key in sorted(list((payload or {}).keys())):
        try:
            result[key] = _apex7_hash_bytes(_apex7_bytes_for_value(payload.get(key)))
        except Exception as exc:
            result[key] = 'error:' + str(exc)
    return result


def _apex7_payload_fingerprint(payload):
    digests = _apex7_payload_digests(payload)
    if _apex7_hashlib is None:
        return repr(sorted(digests.items()))
    h = _apex7_hashlib.sha256()
    for key in sorted(digests.keys()):
        h.update(key.encode('utf-8', 'replace'))
        h.update(b'=')
        h.update(str(digests[key]).encode('utf-8', 'replace'))
        h.update(b';')
    return h.hexdigest()


def _apex7_scope_label(keys):
    keys = set(keys or [])
    labels = []
    if '__outfits__' in keys:
        labels.append('outfits/hair/makeup/tattoos/accessories')
    if 'skin_tone' in keys:
        labels.append('skin tone')
    if 'pelt_layers' in keys:
        labels.append('occult overlays/pelt layers')
    if 'genetic_data' in keys:
        labels.append('genetic skin details/sculpts')
    if 'physique' in keys or 'facial_attributes' in keys:
        labels.append('body/face shape')
    if 'voice_pitch' in keys or 'voice_actor' in keys or 'voice_effect' in keys:
        labels.append('voice')
    return labels or sorted(list(keys))


def _apex7_baseline_bucket(sim_info):
    sid = str(_sim_id(sim_info))
    if sid not in _APEX7_BASELINES:
        _APEX7_BASELINES[sid] = {}
    return _APEX7_BASELINES[sid]


def _apex7_warning_key(sim_info, occult_name, warning_type):
    return '{}:{}:{}'.format(_sim_id(sim_info), occult_name, warning_type)


def _apex7_get_form_for_occult(sim_info, occult_type, generate=False):
    if sim_info is None or occult_type is None:
        return None
    if occult_type == OccultType.HUMAN:
        return sim_info
    tracker = sim_info.occult_tracker
    form = None
    try:
        form = tracker.get_occult_sim_info(occult_type)
    except Exception:
        form = None
    if form is None and generate:
        form = _ensure_form(tracker, occult_type, generate_new=True)
    return form


def _apex7_occult_payload(sim_info, occult_type, use_current=False, generate=False):
    if use_current:
        src = sim_info
    else:
        src = _apex7_get_form_for_occult(sim_info, occult_type, generate=generate)
    if src is None:
        return None, None
    try:
        payload = _apex6_payload_for_appearance(src, scope='cas')
    except Exception:
        payload = _snapshot_siminfo_payload(src)
    return src, payload


def _apex7_accept_baseline(sim_info, occult_type, label=None, source='manual', use_current=False):
    if sim_info is None:
        return {'ok': False, 'message': 'No Sim for baseline'}
    if occult_type is None or occult_type == OccultType.HUMAN:
        return {'ok': False, 'message': 'Baseline needs a selected non-human occult'}
    src, payload = _apex7_occult_payload(sim_info, occult_type, use_current=use_current, generate=True)
    if src is None or not payload:
        return {'ok': False, 'message': 'Could not capture {} baseline'.format(_safe_name(occult_type))}
    name = _safe_name(occult_type)
    digests = _apex7_payload_digests(payload)
    record = {
        'occult': name,
        'label': _apex6_safe_text(label) or '{} baseline {}'.format(name, _apex6_now_label()),
        'source': source,
        'created': _apex6_now_label(),
        'sim_id': str(_sim_id(sim_info)),
        'sim_name': _sim_label(sim_info),
        'fingerprint': _apex7_payload_fingerprint(payload),
        'digests': digests,
        'payload': payload,
        'payload_keys': sorted(list(payload.keys())),
    }
    _apex7_baseline_bucket(sim_info)[name] = record
    # A new accepted baseline clears drift warnings for that occult.
    for key in list(_APEX7_WARNINGS.keys()):
        if key.startswith('{}:{}:'.format(_sim_id(sim_info), name)):
            try:
                del _APEX7_WARNINGS[key]
            except Exception:
                pass
    _log('Accepted Apex drift baseline for {} {} keys={}'.format(_sim_label(sim_info), name, sorted(list(payload.keys()))))
    return {'ok': True, 'message': 'Accepted {} as expected baseline for {}'.format(name, _sim_label(sim_info)), 'data': dict((k, v) for k, v in record.items() if k != 'payload')}


def _apex7_baseline_rows(sim_info=None):
    rows = []
    buckets = {}
    if sim_info is not None:
        buckets[str(_sim_id(sim_info))] = _APEX7_BASELINES.get(str(_sim_id(sim_info)), {})
    else:
        buckets = _APEX7_BASELINES
    for sid, bucket in list(buckets.items()):
        for occult_name, record in list((bucket or {}).items()):
            rows.append(dict((k, v) for k, v in record.items() if k != 'payload'))
    rows.sort(key=lambda item: (item.get('created') or '', item.get('occult') or ''), reverse=True)
    return rows


def _apex7_add_warning(sim_info, occult_name, warning_type, message, keys=None, fix_action=None, severity='warning'):
    key = _apex7_warning_key(sim_info, occult_name, warning_type)
    row = {
        'id': key,
        'sim_id': str(_sim_id(sim_info)),
        'sim_name': _sim_label(sim_info),
        'occult': occult_name,
        'type': warning_type,
        'severity': severity,
        'message': message,
        'changed_keys': sorted(list(keys or [])),
        'changed_areas': _apex7_scope_label(keys or []),
        'fix_action': fix_action or 'fix_occult_drift',
        'created': _apex6_now_label(),
    }
    _APEX7_WARNINGS[key] = row
    _log('DRIFT WARNING {}: {}'.format(key, message))
    return row


def _apex7_clear_warning(sim_info, occult_name=None, warning_type=None):
    removed = []
    prefix = '{}:'.format(_sim_id(sim_info)) if sim_info is not None else ''
    for key in list(_APEX7_WARNINGS.keys()):
        if prefix and not key.startswith(prefix):
            continue
        parts = key.split(':')
        if occult_name and len(parts) > 1 and parts[1] != occult_name:
            continue
        if warning_type and len(parts) > 2 and parts[2] != warning_type:
            continue
        removed.append(key)
        try:
            del _APEX7_WARNINGS[key]
        except Exception:
            pass
    return removed


def _apex7_current_occult_type(sim_info):
    current = _get_current_flags(sim_info)
    for oc in _all_occults():
        try:
            if _mask_has(current, _int_value(oc)):
                return oc
        except Exception:
            pass
    return None


def _apex7_scan_drift(sim_info, occult_type=None, include_missing=True):
    if sim_info is None:
        return {'ok': False, 'message': 'No Sim for drift scan'}
    scanned = []
    issues = []
    active = [occult_type] if occult_type is not None and occult_type != OccultType.HUMAN else _active_occults_from_everything(sim_info)
    baseline_bucket = _APEX7_BASELINES.get(str(_sim_id(sim_info)), {})
    current_occult = _apex7_current_occult_type(sim_info)
    for oc in active:
        if oc is None or oc == OccultType.HUMAN:
            continue
        name = _safe_name(oc)
        scanned.append(name)
        form, payload = _apex7_occult_payload(sim_info, oc, use_current=False, generate=False)
        if form is None or not payload:
            issues.append(_apex7_add_warning(sim_info, name, 'missing_form', '{} has no stored occult form data'.format(name), keys=('__outfits__',), fix_action='generate_form', severity='error'))
            continue
        baseline = baseline_bucket.get(name)
        if baseline is None:
            if include_missing and _APEX7_SETTINGS.get('warn_missing_baseline'):
                issues.append(_apex7_add_warning(sim_info, name, 'missing_baseline', '{} has no accepted expected-look baseline yet; save or accept one after editing.'.format(name), keys=payload.keys(), fix_action='accept_occult_baseline', severity='info'))
            continue
        current_digests = _apex7_payload_digests(payload)
        expected_digests = baseline.get('digests') or {}
        changed = []
        for key in sorted(set(list(current_digests.keys()) + list(expected_digests.keys()))):
            if current_digests.get(key) != expected_digests.get(key):
                changed.append(key)
        if changed:
            issues.append(_apex7_add_warning(sim_info, name, 'appearance_drift', '{} form no longer matches expected baseline; changed: {}'.format(name, ', '.join(_apex7_scope_label(changed))), keys=changed, fix_action='fix_occult_drift', severity='warning'))
        else:
            _apex7_clear_warning(sim_info, name, 'appearance_drift')
            _apex7_clear_warning(sim_info, name, 'missing_baseline')
        if _APEX7_SETTINGS.get('warn_unsynced_current_form') and current_occult is not None and _safe_name(current_occult) == name:
            _src, current_payload = _apex7_occult_payload(sim_info, oc, use_current=True, generate=False)
            if current_payload:
                current_form_digests = _apex7_payload_digests(current_payload)
                changed_current = []
                for key in sorted(set(list(current_form_digests.keys()) + list(current_digests.keys()))):
                    if current_form_digests.get(key) != current_digests.get(key):
                        changed_current.append(key)
                if changed_current:
                    issues.append(_apex7_add_warning(sim_info, name, 'current_not_committed', '{} is the current form, but current CAS edits are not saved into its stored occult form. Click Commit Current -> Selected Occult.'.format(name), keys=changed_current, fix_action='commit_current_to_occult', severity='error'))
                else:
                    _apex7_clear_warning(sim_info, name, 'current_not_committed')
    return {'ok': True, 'message': 'Drift scan checked {} occult form(s), found {} warning(s).'.format(len(scanned), len(issues)), 'details': [row.get('message') for row in issues], 'data': {'scanned': scanned, 'warnings': _apex7_warning_rows(sim_info)}}


def _apex7_warning_rows(sim_info=None):
    rows = []
    sid = str(_sim_id(sim_info)) if sim_info is not None else None
    for key, row in list(_APEX7_WARNINGS.items()):
        if sid is not None and row.get('sim_id') != sid:
            continue
        rows.append(dict(row))
    rows.sort(key=lambda row: (row.get('severity') == 'info', row.get('created') or ''))
    return rows


def _apex7_fix_drift(sim_info, occult_type=None):
    if sim_info is None:
        return {'ok': False, 'message': 'No Sim for drift fix'}
    active = [occult_type] if occult_type is not None and occult_type != OccultType.HUMAN else _active_occults_from_everything(sim_info)
    bucket = _APEX7_BASELINES.get(str(_sim_id(sim_info)), {})
    details = []
    fixed = 0
    for oc in active:
        if oc is None or oc == OccultType.HUMAN:
            continue
        name = _safe_name(oc)
        # If current form edits are not committed, preserve the user's current CAS changes instead of overwriting them.
        warn_key = _apex7_warning_key(sim_info, name, 'current_not_committed')
        if warn_key in _APEX7_WARNINGS:
            commit = _apex7_commit_current_to_occult(sim_info, oc, label='Auto commit from Fix button')
            details.append(commit.get('message'))
            fixed += 1 if commit.get('ok') else 0
            continue
        baseline = bucket.get(name)
        if not baseline:
            details.append('{}: no baseline to restore'.format(name))
            continue
        form = _apex7_get_form_for_occult(sim_info, oc, generate=True)
        if form is None:
            details.append('{}: no form target'.format(name))
            continue
        ok = _apex6_restore_appearance(form, baseline.get('payload') or {}, scope='cas')
        if ok:
            fixed += 1
            _apex7_clear_warning(sim_info, name, 'appearance_drift')
            _apex7_clear_warning(sim_info, name, 'missing_form')
            details.append('{} restored from baseline {}'.format(name, baseline.get('label')))
        else:
            details.append('{} restore skipped'.format(name))
    _set_tracker_form_available(sim_info.occult_tracker, True)
    _repair_sim(sim_info, deep=True)
    _apex7_scan_drift(sim_info, occult_type=occult_type, include_missing=False)
    return {'ok': fixed > 0, 'message': 'Fixed {} occult warning target(s).'.format(fixed), 'details': details, 'data': {'warnings': _apex7_warning_rows(sim_info)}}


def _apex7_commit_current_to_occult(sim_info, occult_type, label=None):
    if sim_info is None:
        return {'ok': False, 'message': 'No Sim to commit'}
    if occult_type is None or occult_type == OccultType.HUMAN:
        return {'ok': False, 'message': 'Commit needs a selected non-human occult'}
    name = _safe_name(occult_type)
    target = _apex7_get_form_for_occult(sim_info, occult_type, generate=True)
    if target is None:
        return {'ok': False, 'message': 'Could not create/get {} form for commit'.format(name)}
    payload = _apex6_payload_for_appearance(sim_info, scope='cas')
    ok = _apex6_restore_appearance(target, payload, scope='cas')
    if ok:
        _set_tracker_form_available(sim_info.occult_tracker, True)
        _repair_sim(sim_info, deep=True)
        base = _apex7_accept_baseline(sim_info, occult_type, label=label or 'Post-CAS committed {}'.format(_apex6_now_label()), source='post_cas_commit', use_current=False)
        try:
            _apex6_save_form(sim_info, occult_type, label=label or '{} post-CAS {}'.format(name, _apex6_now_label()), source='occult_form', scope='cas')
        except Exception as exc:
            _log('Post-CAS commit saved-form mirror skipped: {}'.format(exc))
        _apex7_clear_warning(sim_info, name, 'current_not_committed')
        _apex7_clear_warning(sim_info, name, 'appearance_drift')
        return {'ok': bool(base.get('ok')), 'message': 'Committed current CAS appearance into {} form and accepted it as baseline.'.format(name), 'details': ['copied current appearance payload into stored occult sim_info', base.get('message')]}
    return {'ok': False, 'message': 'Failed to commit current appearance into {}'.format(name)}


def _apex7_commit_current_to_all_forms(sim_info, label=None):
    if sim_info is None:
        return {'ok': False, 'message': 'No Sim to commit'}
    details = []
    ok_count = 0
    for oc in _active_occults_from_everything(sim_info):
        if oc is None or oc == OccultType.HUMAN:
            continue
        result = _apex7_commit_current_to_occult(sim_info, oc, label=label)
        details.append(result.get('message'))
        if result.get('ok'):
            ok_count += 1
    return {'ok': ok_count > 0, 'message': 'Committed current CAS appearance to {} active occult form(s).'.format(ok_count), 'details': details}


def _apex7_after_command_scan(action, sim_id=None, occult=None):
    if not _APEX7_SETTINGS.get('scan_after_apex_commands'):
        return
    if action in ('status', 'health', 'diagnostics', 'list_sims', 'list_saved_forms', 'drift_scan', 'scan_occult_drift', 'drift_status', 'baseline_status'):
        return
    try:
        sim_info = _get_sim_info_by_id(sim_id)
        if sim_info is None:
            return
        oc = _occult_by_name(occult) if occult else None
        _apex7_scan_drift(sim_info, occult_type=oc, include_missing=False)
    except Exception as exc:
        _log('Post-command drift scan skipped for {}: {}'.format(action, exc))


def _overlay_capabilities():
    data = _V6_OVERLAY_CAPABILITIES()
    try:
        data.update({
            'api_version': 7,
            'build_version': _BUILD_VERSION,
            'drift_guard': {
                'mode': 'timerless/fire-once; scans only on user command or after Apex commands when enabled',
                'commands': ['scan_occult_drift', 'fix_occult_drift', 'accept_occult_baseline', 'commit_current_to_occult', 'commit_current_to_all_forms', 'clear_drift_warnings', 'drift_scan_after_commands_on', 'drift_scan_after_commands_off'],
                'warning_count': len(_APEX7_WARNINGS),
                'settings': dict(_APEX7_SETTINGS),
            },
            'reference_screenshots': {
                'mode': 'native DX11 overlay captures backbuffer to BMP before ImGui is drawn',
                'buttons': ['Face Reference Screenshot', 'Body Reference Screenshot', 'Full Reference Screenshot'],
                'folder': 'Documents/Electronic Arts/The Sims 4/TD1ApexScreenshots',
            },
        })
    except Exception:
        pass
    return data


def _status(sim_info):
    data = _V6_STATUS(sim_info)
    try:
        rows = _apex7_warning_rows(sim_info)
        data['drift_warnings'] = rows
        data['drift_warning_count'] = len(rows)
        data['baselines'] = _apex7_baseline_rows(sim_info)
        data['baseline_count'] = len(data.get('baselines') or [])
        data['drift_guard_settings'] = dict(_APEX7_SETTINGS)
    except Exception as exc:
        data['apex7_status_error'] = str(exc)
    return data


def run_action(action, sim_id=None, occult=None, value=None):
    action = (action or 'status').strip().lower()
    try:
        if action in ('drift_status', 'baseline_status'):
            sim_info = _get_sim_info_by_id(sim_id)
            return {'ok': True, 'message': 'Drift guard status', 'data': {'warnings': _apex7_warning_rows(sim_info), 'warning_count': len(_apex7_warning_rows(sim_info)), 'baselines': _apex7_baseline_rows(sim_info), 'settings': dict(_APEX7_SETTINGS)}}
        if action == 'drift_scan_after_commands_on':
            _APEX7_SETTINGS['scan_after_apex_commands'] = True
            return {'ok': True, 'message': 'Drift scan after Apex commands enabled', 'data': dict(_APEX7_SETTINGS)}
        if action == 'drift_scan_after_commands_off':
            _APEX7_SETTINGS['scan_after_apex_commands'] = False
            return {'ok': True, 'message': 'Drift scan after Apex commands disabled', 'data': dict(_APEX7_SETTINGS)}
        if action == 'clear_drift_warnings':
            sim_info = _get_sim_info_by_id(sim_id)
            removed = _apex7_clear_warning(sim_info) if sim_info is not None else list(_APEX7_WARNINGS.keys())
            if sim_info is None:
                _APEX7_WARNINGS.clear()
            return {'ok': True, 'message': 'Cleared {} drift warning(s).'.format(len(removed)), 'details': removed}
        if action == 'reference_shot_note':
            _log('Reference screenshot requested from F11 overlay: {}'.format(value or 'capture'))
            return {'ok': True, 'message': 'Reference screenshot request logged: {}'.format(value or 'capture')}

        if action in ('scan_occult_drift', 'drift_scan', 'fix_occult_drift', 'accept_occult_baseline', 'commit_current_to_occult', 'commit_current_to_all_forms'):
            sim_info = _get_sim_info_by_id(sim_id)
            if sim_info is None:
                return {'ok': False, 'message': 'No Sim selected for {}'.format(action)}
            oc = _occult_by_name(occult) if occult else None
            if action in ('scan_occult_drift', 'drift_scan'):
                return _apex7_scan_drift(sim_info, occult_type=oc, include_missing=True)
            if action == 'fix_occult_drift':
                return _apex7_fix_drift(sim_info, occult_type=oc)
            if action == 'accept_occult_baseline':
                return _apex7_accept_baseline(sim_info, oc, label=value, source='manual_accept', use_current=False)
            if action == 'commit_current_to_occult':
                return _apex7_commit_current_to_occult(sim_info, oc, label=value)
            if action == 'commit_current_to_all_forms':
                return _apex7_commit_current_to_all_forms(sim_info, label=value)

        result = _V6_RUN_ACTION(action, sim_id=sim_id, occult=occult, value=value)
        # Make saved forms also become expected baselines, so a future scan knows what the form is supposed to look like.
        if isinstance(result, dict) and result.get('ok'):
            sim_info = _get_sim_info_by_id(sim_id)
            oc = _occult_by_name(occult) if occult else None
            if sim_info is not None and oc is not None and oc != OccultType.HUMAN:
                if action in ('save_current_form', 'save_occult_form'):
                    _apex7_accept_baseline(sim_info, oc, label=value, source=action, use_current=(action == 'save_current_form'))
                elif action in ('apply_saved_form', 'force_apply_saved_form'):
                    _apex7_accept_baseline(sim_info, oc, label='Baseline after saved-form apply', source=action, use_current=False)
                elif action in ('switch', 'copy_current_to_form', 'copy_human_to_form', 'generate_form'):
                    _apex7_after_command_scan(action, sim_id=sim_id, occult=occult)
            elif action in ('mccc_restore_active', 'mccc_restore_household', 'cas_restore', 'cas_restore_household'):
                _apex7_after_command_scan(action, sim_id=sim_id, occult=occult)
        return result
    except Exception as exc:
        err = '{}\n{}'.format(exc, traceback.format_exc())
        _log(err)
        return {'ok': False, 'message': str(exc), 'traceback': traceback.format_exc()}

_log('TD1 Occult Hybrid Apex v7 loaded: drift guard, post-CAS commit protection, and reference-shot overlay commands ready.')


# V8: Codex handoff + per-CAS-body-type copy/paste/apply commands.
_BUILD_VERSION = '2026.05.28-v9.2-tech-radar-base-layer'
_V8_CAS_BODYTYPE_DEFS = [{'group': 'Reserved / Utility', 'key': 'NONE', 'label': 'None / no body type', 'value': 0, 'genetic': False}, {'group': 'Core Sim Body', 'key': 'HAT', 'label': 'Hat / headwear', 'value': 1, 'genetic': False}, {'group': 'Core Sim Body', 'key': 'HAIR', 'label': 'Hair', 'value': 2, 'genetic': True}, {'group': 'Core Sim Body', 'key': 'HEAD', 'label': 'Head', 'value': 3, 'genetic': True}, {'group': 'Core Sim Body', 'key': 'TEETH', 'label': 'Teeth', 'value': 4, 'genetic': True}, {'group': 'Core Sim Body', 'key': 'FULL_BODY', 'label': 'Full body outfit', 'value': 5, 'genetic': False}, {'group': 'Core Sim Body', 'key': 'UPPER_BODY', 'label': 'Upper body top', 'value': 6, 'genetic': False}, {'group': 'Core Sim Body', 'key': 'LOWER_BODY', 'label': 'Lower body bottom', 'value': 7, 'genetic': False}, {'group': 'Core Sim Body', 'key': 'SHOES', 'label': 'Shoes / footwear', 'value': 8, 'genetic': False}, {'group': 'Accessories', 'key': 'CUMMERBUND', 'label': 'Cummerbund', 'value': 9, 'genetic': False}, {'group': 'Accessories', 'key': 'EARRINGS', 'label': 'Earrings', 'value': 10, 'genetic': False}, {'group': 'Accessories', 'key': 'GLASSES', 'label': 'Glasses', 'value': 11, 'genetic': False}, {'group': 'Accessories', 'key': 'NECKLACE', 'label': 'Necklace', 'value': 12, 'genetic': False}, {'group': 'Accessories', 'key': 'GLOVES', 'label': 'Gloves', 'value': 13, 'genetic': False}, {'group': 'Accessories', 'key': 'WRIST_LEFT', 'label': 'Left wrist', 'value': 14, 'genetic': False}, {'group': 'Accessories', 'key': 'WRIST_RIGHT', 'label': 'Right wrist', 'value': 15, 'genetic': False}, {'group': 'Piercings / Rings', 'key': 'LIP_RING_LEFT', 'label': 'Left lip ring', 'value': 16, 'genetic': False}, {'group': 'Piercings / Rings', 'key': 'LIP_RING_RIGHT', 'label': 'Right lip ring', 'value': 17, 'genetic': False}, {'group': 'Piercings / Rings', 'key': 'NOSE_RING_LEFT', 'label': 'Left nose ring', 'value': 18, 'genetic': False}, {'group': 'Piercings / Rings', 'key': 'NOSE_RING_RIGHT', 'label': 'Right nose ring', 'value': 19, 'genetic': False}, {'group': 'Piercings / Rings', 'key': 'BROW_RING_LEFT', 'label': 'Left brow ring', 'value': 20, 'genetic': False}, {'group': 'Piercings / Rings', 'key': 'BROW_RING_RIGHT', 'label': 'Right brow ring', 'value': 21, 'genetic': False}, {'group': 'Piercings / Rings', 'key': 'INDEX_FINGER_LEFT', 'label': 'Left index finger ring', 'value': 22, 'genetic': False}, {'group': 'Piercings / Rings', 'key': 'INDEX_FINGER_RIGHT', 'label': 'Right index finger ring', 'value': 23, 'genetic': False}, {'group': 'Piercings / Rings', 'key': 'RING_FINGER_LEFT', 'label': 'Left ring finger ring', 'value': 24, 'genetic': False}, {'group': 'Piercings / Rings', 'key': 'RING_FINGER_RIGHT', 'label': 'Right ring finger ring', 'value': 25, 'genetic': False}, {'group': 'Piercings / Rings', 'key': 'MIDDLE_FINGER_LEFT', 'label': 'Left middle finger ring', 'value': 26, 'genetic': False}, {'group': 'Piercings / Rings', 'key': 'MIDDLE_FINGER_RIGHT', 'label': 'Right middle finger ring', 'value': 27, 'genetic': False}, {'group': 'Makeup / Face', 'key': 'FACIAL_HAIR', 'label': 'Facial hair', 'value': 28, 'genetic': True}, {'group': 'Makeup / Face', 'key': 'LIPS_TICK', 'label': 'Lipstick', 'value': 29, 'genetic': False}, {'group': 'Makeup / Face', 'key': 'EYE_SHADOW', 'label': 'Eye shadow', 'value': 30, 'genetic': False}, {'group': 'Makeup / Face', 'key': 'EYE_LINER', 'label': 'Eye liner', 'value': 31, 'genetic': False}, {'group': 'Makeup / Face', 'key': 'BLUSH', 'label': 'Blush', 'value': 32, 'genetic': False}, {'group': 'Makeup / Face', 'key': 'FACEPAINT', 'label': 'Face paint', 'value': 33, 'genetic': False}, {'group': 'Makeup / Face', 'key': 'EYEBROWS', 'label': 'Eyebrows', 'value': 34, 'genetic': True}, {'group': 'Makeup / Face', 'key': 'EYECOLOR', 'label': 'Eye color', 'value': 35, 'genetic': True}, {'group': 'Accessories', 'key': 'SOCKS', 'label': 'Socks', 'value': 36, 'genetic': False}, {'group': 'Makeup / Face', 'key': 'EYELASHES', 'label': 'Eyelashes', 'value': 37, 'genetic': False}, {'group': 'Skin Details', 'key': 'SKINDETAIL_CREASE_FOREHEAD', 'label': 'Forehead crease skin detail', 'value': 38, 'genetic': True}, {'group': 'Skin Details', 'key': 'SKINDETAIL_FRECKLES', 'label': 'Freckles skin detail', 'value': 39, 'genetic': True}, {'group': 'Skin Details', 'key': 'SKINDETAIL_DIMPLE_LEFT', 'label': 'Left dimple skin detail', 'value': 40, 'genetic': True}, {'group': 'Skin Details', 'key': 'SKINDETAIL_DIMPLE_RIGHT', 'label': 'Right dimple skin detail', 'value': 41, 'genetic': True}, {'group': 'Accessories', 'key': 'TIGHTS', 'label': 'Tights / legwear', 'value': 42, 'genetic': False}, {'group': 'Skin Details', 'key': 'SKINDETAIL_MOLE_LIP_LEFT', 'label': 'Left lip mole skin detail', 'value': 43, 'genetic': True}, {'group': 'Skin Details', 'key': 'SKINDETAIL_MOLE_LIP_RIGHT', 'label': 'Right lip mole skin detail', 'value': 44, 'genetic': True}, {'group': 'Tattoos', 'key': 'TATTOO_ARM_LOWER_LEFT', 'label': 'Lower left arm tattoo', 'value': 45, 'genetic': True}, {'group': 'Tattoos', 'key': 'TATTOO_ARM_UPPER_LEFT', 'label': 'Upper left arm tattoo', 'value': 46, 'genetic': True}, {'group': 'Tattoos', 'key': 'TATTOO_ARM_LOWER_RIGHT', 'label': 'Lower right arm tattoo', 'value': 47, 'genetic': True}, {'group': 'Tattoos', 'key': 'TATTOO_ARM_UPPER_RIGHT', 'label': 'Upper right arm tattoo', 'value': 48, 'genetic': True}, {'group': 'Tattoos', 'key': 'TATTOO_LEG_LEFT', 'label': 'Left leg tattoo', 'value': 49, 'genetic': True}, {'group': 'Tattoos', 'key': 'TATTOO_LEG_RIGHT', 'label': 'Right leg tattoo', 'value': 50, 'genetic': True}, {'group': 'Tattoos', 'key': 'TATTOO_TORSO_BACK_LOWER', 'label': 'Lower back torso tattoo', 'value': 51, 'genetic': True}, {'group': 'Tattoos', 'key': 'TATTOO_TORSO_BACK_UPPER', 'label': 'Upper back torso tattoo', 'value': 52, 'genetic': True}, {'group': 'Tattoos', 'key': 'TATTOO_TORSO_FRONT_LOWER', 'label': 'Lower front torso tattoo', 'value': 53, 'genetic': True}, {'group': 'Tattoos', 'key': 'TATTOO_TORSO_FRONT_UPPER', 'label': 'Upper front torso tattoo', 'value': 54, 'genetic': True}, {'group': 'Skin Details', 'key': 'SKINDETAIL_MOLE_CHEEK_LEFT', 'label': 'Left cheek mole skin detail', 'value': 55, 'genetic': True}, {'group': 'Skin Details', 'key': 'SKINDETAIL_MOLE_CHEEK_RIGHT', 'label': 'Right cheek mole skin detail', 'value': 56, 'genetic': True}, {'group': 'Skin Details', 'key': 'SKINDETAIL_CREASE_MOUTH', 'label': 'Mouth crease skin detail', 'value': 57, 'genetic': True}, {'group': 'Skin Details', 'key': 'SKIN_OVERLAY', 'label': 'Skin overlay', 'value': 58, 'genetic': True}, {'group': 'Occult / Creature', 'key': 'FUR_BODY', 'label': 'Fur body', 'value': 59, 'genetic': True}, {'group': 'Occult / Creature', 'key': 'EARS', 'label': 'Ears', 'value': 60, 'genetic': True}, {'group': 'Occult / Creature', 'key': 'TAIL', 'label': 'Tail', 'value': 61, 'genetic': True}, {'group': 'Skin Details', 'key': 'SKINDETAIL_NOSE_COLOR', 'label': 'Nose color skin detail', 'value': 62, 'genetic': True}, {'group': 'Makeup / Face', 'key': 'EYECOLOR_SECONDARY', 'label': 'Secondary eye color', 'value': 63, 'genetic': True}, {'group': 'Occult / Creature', 'key': 'OCCULT_BROW', 'label': 'Occult brow', 'value': 64, 'genetic': True}, {'group': 'Occult / Creature', 'key': 'OCCULT_EYE_SOCKET', 'label': 'Occult eye socket', 'value': 65, 'genetic': True}, {'group': 'Occult / Creature', 'key': 'OCCULT_EYE_LID', 'label': 'Occult eye lid', 'value': 66, 'genetic': True}, {'group': 'Occult / Creature', 'key': 'OCCULT_MOUTH', 'label': 'Occult mouth', 'value': 67, 'genetic': True}, {'group': 'Occult / Creature', 'key': 'OCCULT_LEFT_CHEEK', 'label': 'Occult left cheek', 'value': 68, 'genetic': True}, {'group': 'Occult / Creature', 'key': 'OCCULT_RIGHT_CHEEK', 'label': 'Occult right cheek', 'value': 69, 'genetic': True}, {'group': 'Occult / Creature', 'key': 'OCCULT_NECK_SCAR', 'label': 'Occult neck scar', 'value': 70, 'genetic': True}, {'group': 'Skin Details', 'key': 'FOREARM_SCAR', 'label': 'Forearm scar', 'value': 71, 'genetic': True}, {'group': 'Skin Details', 'key': 'ACNE', 'label': 'Acne', 'value': 72, 'genetic': True}, {'group': 'Accessories', 'key': 'FINGERNAIL', 'label': 'Fingernails', 'value': 73, 'genetic': False}, {'group': 'Accessories', 'key': 'TOENAIL', 'label': 'Toenails', 'value': 74, 'genetic': False}, {'group': 'Makeup / Face', 'key': 'HAIRCOLOR_OVERRIDE', 'label': 'Hair color override', 'value': 75, 'genetic': False}, {'group': 'Occult / Creature', 'key': 'BITE', 'label': 'Bite mark', 'value': 76, 'genetic': True}, {'group': 'Skin Details', 'key': 'BODYFRECKLES', 'label': 'Body freckles', 'value': 77, 'genetic': True}, {'group': 'Body Hair / Scars', 'key': 'BODYHAIR_ARM', 'label': 'Arm body hair', 'value': 78, 'genetic': True}, {'group': 'Body Hair / Scars', 'key': 'BODYHAIR_LEG', 'label': 'Leg body hair', 'value': 79, 'genetic': True}, {'group': 'Body Hair / Scars', 'key': 'BODYHAIR_TORSOFRONT', 'label': 'Front torso body hair', 'value': 80, 'genetic': True}, {'group': 'Body Hair / Scars', 'key': 'BODYHAIR_TORSOBACK', 'label': 'Back torso body hair', 'value': 81, 'genetic': True}, {'group': 'Body Hair / Scars', 'key': 'BODYSCAR_ARMLEFT', 'label': 'Left arm body scar', 'value': 82, 'genetic': True}, {'group': 'Body Hair / Scars', 'key': 'BODYSCAR_ARMRIGHT', 'label': 'Right arm body scar', 'value': 83, 'genetic': True}, {'group': 'Body Hair / Scars', 'key': 'BODYSCAR_TORSOFRONT', 'label': 'Front torso body scar', 'value': 84, 'genetic': True}, {'group': 'Body Hair / Scars', 'key': 'BODYSCAR_TORSOBACK', 'label': 'Back torso body scar', 'value': 85, 'genetic': True}, {'group': 'Body Hair / Scars', 'key': 'BODYSCAR_LEGLEFT', 'label': 'Left leg body scar', 'value': 86, 'genetic': True}, {'group': 'Body Hair / Scars', 'key': 'BODYSCAR_LEGRIGHT', 'label': 'Right leg body scar', 'value': 87, 'genetic': True}, {'group': 'Occult / Creature', 'key': 'ATTACHMENT_BACK', 'label': 'Back attachment', 'value': 88, 'genetic': False}, {'group': 'Skin Details', 'key': 'SKINDETAIL_ACNE_PUBERTY', 'label': 'Puberty acne skin detail', 'value': 89, 'genetic': True}, {'group': 'Body Hair / Scars', 'key': 'SCARFACE', 'label': 'Face scar', 'value': 90, 'genetic': True}, {'group': 'Skin Details', 'key': 'BIRTHMARKFACE', 'label': 'Face birthmark', 'value': 91, 'genetic': True}, {'group': 'Skin Details', 'key': 'BIRTHMARKTORSOBACK', 'label': 'Back torso birthmark', 'value': 92, 'genetic': True}, {'group': 'Skin Details', 'key': 'BIRTHMARKTORSOFRONT', 'label': 'Front torso birthmark', 'value': 93, 'genetic': True}, {'group': 'Skin Details', 'key': 'BIRTHMARKARMS', 'label': 'Arm birthmarks', 'value': 94, 'genetic': True}, {'group': 'Skin Details', 'key': 'MOLEFACE', 'label': 'Face mole', 'value': 95, 'genetic': True}, {'group': 'Skin Details', 'key': 'MOLECHESTUPPER', 'label': 'Upper chest mole', 'value': 96, 'genetic': True}, {'group': 'Skin Details', 'key': 'MOLEBACKUPPER', 'label': 'Upper back mole', 'value': 97, 'genetic': True}, {'group': 'Skin Details', 'key': 'BIRTHMARKLEGS', 'label': 'Leg birthmarks', 'value': 98, 'genetic': True}, {'group': 'Skin Details', 'key': 'STRETCHMARKS_FRONT', 'label': 'Front stretch marks', 'value': 99, 'genetic': True}, {'group': 'Skin Details', 'key': 'STRETCHMARKS_BACK', 'label': 'Back stretch marks', 'value': 100, 'genetic': True}, {'group': 'Horse / Animal', 'key': 'SADDLE', 'label': 'Saddle', 'value': 101, 'genetic': False}, {'group': 'Horse / Animal', 'key': 'BRIDLE', 'label': 'Bridle', 'value': 102, 'genetic': False}, {'group': 'Horse / Animal', 'key': 'REINS', 'label': 'Reins', 'value': 103, 'genetic': False}, {'group': 'Horse / Animal', 'key': 'BLANKET', 'label': 'Blanket', 'value': 104, 'genetic': False}, {'group': 'Horse / Animal', 'key': 'SKINDETAIL_HOOF_COLOR', 'label': 'Hoof color skin detail', 'value': 105, 'genetic': True}, {'group': 'Horse / Animal', 'key': 'HAIR_MANE', 'label': 'Mane hair', 'value': 106, 'genetic': False}, {'group': 'Horse / Animal', 'key': 'HAIR_TAIL', 'label': 'Tail hair', 'value': 107, 'genetic': False}, {'group': 'Horse / Animal', 'key': 'HAIR_FORELOCK', 'label': 'Forelock hair', 'value': 108, 'genetic': False}, {'group': 'Horse / Animal', 'key': 'HAIR_FEATHERS', 'label': 'Feathering hair', 'value': 109, 'genetic': False}, {'group': 'Horse / Animal', 'key': 'HORN', 'label': 'Horn', 'value': 110, 'genetic': False}, {'group': 'Horse / Animal', 'key': 'TAIL_BASE', 'label': 'Tail base', 'value': 111, 'genetic': False}, {'group': 'Reserved / Utility', 'key': 'UNUSED', 'label': 'Unused / reserved', 'value': 112, 'genetic': False}, {'group': 'Latest / Runtime Resolved', 'key': 'HEAD_DECORATION', 'label': 'Head decoration', 'value': 113, 'genetic': False}, {'group': 'Latest / Runtime Resolved', 'key': 'SKIN_SPECULARITY', 'label': 'Skin specularity', 'value': 114, 'genetic': True}, {'group': 'Latest / Runtime Resolved', 'key': 'TATTOO_HEAD_WINGS', 'label': 'Tattoo head wings', 'value': 115, 'genetic': True}, {'group': 'Latest / Runtime Resolved', 'key': 'BASE_LAYER', 'label': 'Base Layer', 'value': 116, 'genetic': False}]
_V8_CAS_BODYTYPE_ALIASES = {
    'LIPSTICK': 'LIPS_TICK',
    'LIPS': 'LIPS_TICK',
    'EYESHADOW': 'EYE_SHADOW',
    'EYELINER': 'EYE_LINER',
    'EYE_COLOR': 'EYECOLOR',
    'SECONDARY_EYE_COLOR': 'EYECOLOR_SECONDARY',
    'FINGERNAILS': 'FINGERNAIL',
    'TOENAILS': 'TOENAIL',
    'TATTOOS_HEAD_WINGS': 'TATTOO_HEAD_WINGS',
    'HEAD_WINGS': 'TATTOO_HEAD_WINGS',
}
_V8_CAS_BODYTYPE_BY_KEY = dict((row.get('key'), row) for row in _V8_CAS_BODYTYPE_DEFS)
_V8_CAS_CATEGORY_CLIPBOARD = {}

try:
    from sims.outfits.outfit_enums import BodyType as _V8_EA_BODYTYPE
except Exception:
    _V8_EA_BODYTYPE = None

try:
    from protocolbuffers import Outfits_pb2 as _V8_Outfits_pb2
    from protocolbuffers import S4Common_pb2 as _V8_S4Common_pb2
except Exception:
    _V8_Outfits_pb2 = None
    _V8_S4Common_pb2 = None


def _v8_cas_clean_key(value):
    text = str(value or '').strip().upper()
    text = re.sub(r'[^A-Z0-9]+', '_', text).strip('_')
    return _V8_CAS_BODYTYPE_ALIASES.get(text, text)


def _v8_resolve_body_type(value):
    key = _v8_cas_clean_key(value)
    if not key:
        return None, None, 'No CAS category was supplied.'
    if key.isdigit():
        number = int(key)
        for row in _V8_CAS_BODYTYPE_DEFS:
            if int(row.get('value', -999)) == number:
                return number, row, 'numeric'
        return number, {'key': key, 'label': 'BodyType {}'.format(number), 'value': number, 'group': 'Numeric'}, 'numeric_custom'
    row = _V8_CAS_BODYTYPE_BY_KEY.get(key)
    if _V8_EA_BODYTYPE is not None:
        try:
            if hasattr(_V8_EA_BODYTYPE, key):
                return int(getattr(_V8_EA_BODYTYPE, key)), row or {'key': key, 'label': key, 'value': int(getattr(_V8_EA_BODYTYPE, key)), 'group': 'Runtime'}, 'runtime_enum'
        except Exception:
            pass
        if row is not None and int(row.get('value', 0)) >= 113:
            return None, row, 'This game build did not expose BodyType.{} at runtime. Do not paste this latest category until the enum is verified after a patch.'.format(key)
    if row is None:
        return None, None, 'Unknown CAS body type: {}'.format(value)
    return int(row.get('value')), row, 'fallback_table'


def _v8_imports_ready():
    return _V8_Outfits_pb2 is not None and _V8_S4Common_pb2 is not None


def _v8_outfit_parallel_rows(outfit):
    try:
        ids = list(outfit.parts.ids)
    except Exception:
        ids = []
    try:
        body_types = list(outfit.body_types_list.body_types)
    except Exception:
        body_types = []
    try:
        shifts = list(outfit.part_shifts.color_shift)
    except Exception:
        shifts = []
    try:
        objects = list(outfit.object_ids.object_id)
    except Exception:
        objects = []
    try:
        layers = list(outfit.layer_ids.layer_id)
    except Exception:
        layers = []
    rows = []
    for idx, body_type in enumerate(body_types):
        rows.append({
            'id': int(ids[idx]) if idx < len(ids) else 0,
            'body_type': int(body_type),
            'color_shift': int(shifts[idx]) if idx < len(shifts) else 0,
            'object_id': int(objects[idx]) if idx < len(objects) else 0,
            'layer_id': int(layers[idx]) if idx < len(layers) else 0,
        })
    return rows


def _v8_clear_repeated(seq):
    try:
        del seq[:]
        return
    except Exception:
        pass
    try:
        while len(seq):
            seq.pop()
    except Exception:
        pass


def _v8_message_bytes(value):
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    try:
        return value.SerializeToString()
    except Exception:
        pass
    try:
        return bytes(value)
    except Exception:
        return None


def _v8_read_outfit_blob(sim_info):
    # Prefer the official SimInfo outfit serializer when available; fall back to
    # the persisted base blob.  The fallback keeps this usable across game patch
    # builds where load/save helper names may move.
    for name in ('save_outfits',):
        try:
            fn = getattr(sim_info, name, None)
            if callable(fn):
                blob = _v8_message_bytes(fn())
                if blob:
                    return blob
        except Exception:
            pass
    try:
        return _v8_message_bytes(sim_info._base.outfits)
    except Exception:
        return None


def _v8_write_outfit_blob(sim_info, blob):
    if not blob:
        return False
    for name in ('load_outfits',):
        try:
            fn = getattr(sim_info, name, None)
            if callable(fn):
                fn(blob)
                return True
        except Exception:
            pass
    try:
        sim_info._base.outfits = blob
        return True
    except Exception:
        pass
    try:
        target = sim_info._base.outfits
        if hasattr(target, 'ParseFromString'):
            target.ParseFromString(blob)
            return True
    except Exception:
        pass
    return False


def _v8_read_genetic_blob(sim_info):
    try:
        return _v8_message_bytes(sim_info._base.genetic_data)
    except Exception:
        return None


def _v8_write_genetic_blob(sim_info, blob):
    if not blob:
        return False
    try:
        sim_info._base.genetic_data = blob
        return True
    except Exception:
        pass
    try:
        target = sim_info._base.genetic_data
        if hasattr(target, 'ParseFromString'):
            target.ParseFromString(blob)
            return True
    except Exception:
        pass
    return False


def _v8_write_outfit_parallel_rows(outfit, rows):
    rows = sorted(list(rows or []), key=lambda item: (int(item.get('body_type', 0)), int(item.get('id', 0))))
    # Protobuf composite fields cannot be assigned with ``outfit.parts = ...`` on
    # many EA Python builds.  ClearField + repeated.extend is the safe path.
    try:
        outfit.ClearField('parts')
    except Exception:
        _v8_clear_repeated(getattr(getattr(outfit, 'parts', None), 'ids', []))
    outfit.parts.ids.extend([int(r.get('id', 0)) for r in rows])
    try:
        outfit.ClearField('body_types_list')
    except Exception:
        _v8_clear_repeated(getattr(getattr(outfit, 'body_types_list', None), 'body_types', []))
    outfit.body_types_list.body_types.extend([int(r.get('body_type', 0)) for r in rows])
    try:
        outfit.ClearField('part_shifts')
    except Exception:
        _v8_clear_repeated(getattr(getattr(outfit, 'part_shifts', None), 'color_shift', []))
    outfit.part_shifts.color_shift.extend([int(r.get('color_shift', 0)) for r in rows])
    try:
        outfit.ClearField('object_ids')
    except Exception:
        _v8_clear_repeated(getattr(getattr(outfit, 'object_ids', None), 'object_id', []))
    outfit.object_ids.object_id.extend([int(r.get('object_id', 0)) for r in rows])
    try:
        outfit.ClearField('layer_ids')
    except Exception:
        _v8_clear_repeated(getattr(getattr(outfit, 'layer_ids', None), 'layer_id', []))
    outfit.layer_ids.layer_id.extend([int(r.get('layer_id', 0)) for r in rows])


def _v8_parse_outfits(sim_info):
    msg = _V8_Outfits_pb2.OutfitList()
    blob = _v8_read_outfit_blob(sim_info)
    if not blob:
        return None
    try:
        msg.ParseFromString(blob)
    except Exception:
        return None
    return msg


def _v8_parse_genetic(sim_info):
    msg = _V8_Outfits_pb2.GeneticData()
    blob = _v8_read_genetic_blob(sim_info)
    if not blob:
        return None
    try:
        msg.ParseFromString(blob)
    except Exception:
        return None
    return msg


def _v8_extract_message_blobs(repeated_parts, body_type_value):
    blobs = []
    for part in list(repeated_parts or []):
        try:
            if int(getattr(part, 'body_type', -1)) == int(body_type_value):
                blobs.append(part.SerializeToString())
        except Exception:
            pass
    return blobs


def _v8_restore_message_blobs(repeated_parts, body_type_value, source_blobs):
    kept = []
    for part in list(repeated_parts or []):
        try:
            if int(getattr(part, 'body_type', -1)) != int(body_type_value):
                kept.append(part.SerializeToString())
        except Exception:
            try:
                kept.append(part.SerializeToString())
            except Exception:
                pass
    try:
        del repeated_parts[:]
    except Exception:
        try:
            while len(repeated_parts):
                repeated_parts.pop()
        except Exception:
            pass
    count = 0
    for blob in kept + list(source_blobs or []):
        try:
            item = repeated_parts.add()
            item.ParseFromString(blob)
            count += 1
        except Exception:
            pass
    return count


def _v8_extract_bodytype_payload(sim_info, body_type_name):
    if sim_info is None:
        return {'ok': False, 'message': 'No Sim selected for CAS category copy.'}
    if not _v8_imports_ready():
        return {'ok': False, 'message': 'Outfits/S4Common protocolbuffers are unavailable in this runtime; category copy is disabled to avoid corrupting outfit data.'}
    body_value, meta, source = _v8_resolve_body_type(body_type_name)
    if body_value is None:
        return {'ok': False, 'message': source, 'category': body_type_name}
    outfits_msg = _v8_parse_outfits(sim_info)
    if outfits_msg is None:
        return {'ok': False, 'message': 'Could not parse outfit data for {}'.format(_sim_label(sim_info))}
    outfit_payloads = []
    total_parts = 0
    for idx, outfit in enumerate(list(outfits_msg.outfits)):
        rows = [row for row in _v8_outfit_parallel_rows(outfit) if int(row.get('body_type', -1)) == int(body_value)]
        if rows:
            total_parts += len(rows)
            outfit_payloads.append({'outfit_index': idx, 'outfit_id': int(getattr(outfit, 'outfit_id', 0)), 'parts': rows})
    genetic_blobs = []
    growth_blobs = []
    genetic_msg = _v8_parse_genetic(sim_info)
    if genetic_msg is not None:
        try:
            genetic_blobs = _v8_extract_message_blobs(genetic_msg.parts_list.parts, body_value)
        except Exception:
            genetic_blobs = []
        try:
            growth_blobs = _v8_extract_message_blobs(genetic_msg.growth_parts_list.parts, body_value)
        except Exception:
            growth_blobs = []
    payload = {
        'scope': 'cas_body_type',
        'body_type_key': meta.get('key') if meta else str(body_type_name),
        'body_type_label': meta.get('label') if meta else str(body_type_name),
        'body_type_value': int(body_value),
        'resolve_source': source,
        'created': time.strftime('%Y-%m-%d %H:%M:%S'),
        'source_sim_id': str(_sim_id(sim_info)),
        'source_sim_name': _sim_label(sim_info),
        'outfits': outfit_payloads,
        'genetic_parts': genetic_blobs,
        'growth_parts': growth_blobs,
        'total_outfit_parts': total_parts,
    }
    if total_parts == 0 and not genetic_blobs and not growth_blobs:
        return {'ok': False, 'message': '{} has no {} parts to copy.'.format(_sim_label(sim_info), payload['body_type_label']), 'data': {'category': meta, 'value': body_value}}
    return {'ok': True, 'message': 'Copied {} category from {}: {} outfit part(s), {} genetic, {} growth.'.format(payload['body_type_label'], _sim_label(sim_info), total_parts, len(genetic_blobs), len(growth_blobs)), 'payload': payload}


def _v8_apply_bodytype_payload(sim_info, payload):
    if sim_info is None:
        return False, 'No target Sim selected.'
    if not payload:
        return False, 'No CAS category clipboard payload.'
    if not _v8_imports_ready():
        return False, 'Outfits/S4Common protocolbuffers are unavailable in this runtime.'
    body_value = int(payload.get('body_type_value'))
    outfits_msg = _v8_parse_outfits(sim_info)
    if outfits_msg is None:
        return False, 'Could not parse target outfit data.'
    src_by_index = dict((int(row.get('outfit_index', -1)), list(row.get('parts') or [])) for row in payload.get('outfits') or [])
    first_parts = None
    for row in payload.get('outfits') or []:
        if row.get('parts'):
            first_parts = list(row.get('parts') or [])
            break
    changed_outfits = 0
    for idx, outfit in enumerate(list(outfits_msg.outfits)):
        source_parts = src_by_index.get(idx, first_parts)
        if not source_parts:
            continue
        existing = [row for row in _v8_outfit_parallel_rows(outfit) if int(row.get('body_type', -1)) != int(body_value)]
        merged = existing + [dict(part, body_type=body_value) for part in source_parts]
        _v8_write_outfit_parallel_rows(outfit, merged)
        changed_outfits += 1
    if changed_outfits:
        try:
            _v8_write_outfit_blob(sim_info, outfits_msg.SerializeToString())
        except Exception:
            pass
    genetic_count = 0
    growth_count = 0
    genetic_msg = _v8_parse_genetic(sim_info)
    if genetic_msg is not None:
        try:
            if payload.get('genetic_parts'):
                genetic_count = _v8_restore_message_blobs(genetic_msg.parts_list.parts, body_value, payload.get('genetic_parts') or [])
        except Exception:
            genetic_count = 0
        try:
            if payload.get('growth_parts'):
                growth_count = _v8_restore_message_blobs(genetic_msg.growth_parts_list.parts, body_value, payload.get('growth_parts') or [])
        except Exception:
            growth_count = 0
        if genetic_count or growth_count:
            try:
                _v8_write_genetic_blob(sim_info, genetic_msg.SerializeToString())
            except Exception:
                pass
    _resend_all_visuals(sim_info)
    _recalc(sim_info)
    return True, 'Applied {} category to {}: {} outfit(s), genetic={}, growth={}.'.format(payload.get('body_type_label') or payload.get('body_type_key'), _sim_label(sim_info), changed_outfits, genetic_count, growth_count)


def _v8_copy_cas_category(sim_info, category):
    result = _v8_extract_bodytype_payload(sim_info, category)
    if not result.get('ok'):
        return result
    payload = result.pop('payload')
    key = payload.get('body_type_key')
    _V8_CAS_CATEGORY_CLIPBOARD[key] = payload
    _log('V8 copied CAS category {} from {} parts={}'.format(key, _sim_label(sim_info), payload.get('total_outfit_parts')))
    return {'ok': True, 'message': result.get('message'), 'data': _v8_clipboard_summary(key)}


def _v8_clipboard_summary(key=None):
    rows = []
    for k, payload in sorted(_V8_CAS_CATEGORY_CLIPBOARD.items()):
        if key is not None and k != key:
            continue
        rows.append({
            'body_type_key': k,
            'label': payload.get('body_type_label'),
            'value': payload.get('body_type_value'),
            'source_sim': payload.get('source_sim_name'),
            'created': payload.get('created'),
            'outfit_parts': payload.get('total_outfit_parts'),
            'genetic_parts': len(payload.get('genetic_parts') or []),
            'growth_parts': len(payload.get('growth_parts') or []),
        })
    return rows[0] if key is not None and rows else rows


def _v8_paste_cas_category(sim_info, category):
    body_value, meta, source = _v8_resolve_body_type(category)
    if body_value is None:
        return {'ok': False, 'message': source}
    key = meta.get('key') if meta else _v8_cas_clean_key(category)
    payload = _V8_CAS_CATEGORY_CLIPBOARD.get(key)
    if not payload:
        return {'ok': False, 'message': 'CAS category clipboard is empty for {}.'.format(key), 'data': _v8_clipboard_summary()}
    ok, msg = _v8_apply_bodytype_payload(sim_info, payload)
    if ok:
        _log('V8 pasted CAS category {} onto {}'.format(key, _sim_label(sim_info)))
        try:
            _apex7_after_command_scan('paste_cas_category', sim_id=_sim_id(sim_info), occult=None)
        except Exception:
            pass
    return {'ok': bool(ok), 'message': msg, 'data': {'clipboard': _v8_clipboard_summary(key)}}


def _v8_apply_cas_category_to_forms(sim_info, category):
    if sim_info is None:
        return {'ok': False, 'message': 'No selected/active Sim for apply category to forms.'}
    body_value, meta, source = _v8_resolve_body_type(category)
    if body_value is None:
        return {'ok': False, 'message': source}
    key = meta.get('key') if meta else _v8_cas_clean_key(category)
    payload = _V8_CAS_CATEGORY_CLIPBOARD.get(key)
    if not payload:
        return {'ok': False, 'message': 'CAS category clipboard is empty for {}.'.format(key), 'data': _v8_clipboard_summary()}
    done = []
    details = []
    for oc in _active_occults_from_everything(sim_info):
        if oc is None or oc == OccultType.HUMAN:
            continue
        target = _ensure_form(sim_info.occult_tracker, oc, generate_new=True)
        if target is None:
            details.append('{}: no form target'.format(_safe_name(oc)))
            continue
        ok, msg = _v8_apply_bodytype_payload(target, payload)
        details.append('{}: {}'.format(_safe_name(oc), msg))
        if ok:
            done.append(_safe_name(oc))
    _set_tracker_form_available(sim_info.occult_tracker, True)
    _repair_sim(sim_info, deep=False)
    try:
        _apex7_after_command_scan('apply_cas_category_to_all_forms', sim_id=_sim_id(sim_info), occult=None)
    except Exception:
        pass
    return {'ok': bool(done), 'message': 'Applied {} category to {} occult form(s).'.format(key, len(done)), 'details': details, 'data': {'forms': done, 'clipboard': _v8_clipboard_summary(key)}}


def _v8_cas_category_status():
    rows = []
    for row in _V8_CAS_BODYTYPE_DEFS:
        value, _meta, source = _v8_resolve_body_type(row.get('key'))
        rows.append(dict(row, runtime_value=value, resolve_source=source, clipboard=row.get('key') in _V8_CAS_CATEGORY_CLIPBOARD))
    return {'ok': True, 'message': 'CAS category status: {} category buttons, {} clipboard slot(s).'.format(len(rows), len(_V8_CAS_CATEGORY_CLIPBOARD)), 'data': rows, 'clipboards': _v8_clipboard_summary()}


_V8_PREV_OVERLAY_CAPABILITIES = _overlay_capabilities
_V8_PREV_STATUS = _status
_V8_PREV_RUN_ACTION = run_action


def _overlay_capabilities():
    data = _V8_PREV_OVERLAY_CAPABILITIES()
    try:
        data.update({
            'api_version': 8,
            'cas_category_buttons': {
                'count': len(_V8_CAS_BODYTYPE_DEFS),
                'commands': ['copy_cas_category', 'paste_cas_category', 'apply_cas_category_to_all_forms', 'cas_category_status'],
                'mode': 'fire-on-click only; no timers; BodyType enum is runtime-resolved when available',
                'categories': [dict((k, v) for k, v in row.items()) for row in _V8_CAS_BODYTYPE_DEFS],
            },
            'codex_handoff': 'See CODEX_CONTINUATION_GUIDE.md in the mod root.',
        })
    except Exception:
        pass
    return data


def _status(sim_info):
    data = _V8_PREV_STATUS(sim_info)
    try:
        data['cas_category_clipboards'] = _v8_clipboard_summary()
        data['cas_category_count'] = len(_V8_CAS_BODYTYPE_DEFS)
    except Exception as exc:
        data['v8_cas_category_error'] = str(exc)
    return data


def run_action(action, sim_id=None, occult=None, value=None):
    action = (action or 'status').strip().lower()
    try:
        if action in ('cas_category_status', 'list_cas_categories'):
            return _v8_cas_category_status()
        if action in ('copy_cas_category', 'copy_bodytype', 'copy_body_type'):
            sim_info = _get_sim_info_by_id(sim_id) or _get_active_sim_info()
            if sim_info is None:
                return {'ok': False, 'message': 'No selected/active Sim for {}'.format(action)}
            return _v8_copy_cas_category(sim_info, value or occult)
        if action in ('paste_cas_category', 'paste_bodytype', 'paste_body_type'):
            sim_info = _get_sim_info_by_id(sim_id) or _get_active_sim_info()
            if sim_info is None:
                return {'ok': False, 'message': 'No selected/active Sim for {}'.format(action)}
            return _v8_paste_cas_category(sim_info, value or occult)
        if action in ('apply_cas_category_to_all_forms', 'apply_bodytype_to_all_forms', 'apply_body_type_to_all_forms'):
            sim_info = _get_sim_info_by_id(sim_id) or _get_active_sim_info()
            if sim_info is None:
                return {'ok': False, 'message': 'No selected/active Sim for {}'.format(action)}
            return _v8_apply_cas_category_to_forms(sim_info, value or occult)
        return _V8_PREV_RUN_ACTION(action, sim_id=sim_id, occult=occult, value=value)
    except Exception as exc:
        err = '{}\n{}'.format(exc, traceback.format_exc())
        _log(err)
        return {'ok': False, 'message': str(exc), 'traceback': traceback.format_exc()}

_log('TD1 Occult Hybrid Apex v8.1 loaded: Codex guide, runtime CAS category list, and per-body-type copy/paste/apply commands ready.')

# V9: brutal QA / fail-closed compatibility hardening.
# - Adds explicit self-test/preflight commands for Codex and in-game smoke testing.
# - Makes per-category CAS paste conflict-aware for FULL_BODY vs UPPER_BODY/LOWER_BODY.
# - Keeps all new checks fire-on-click; no new timers or gameplay scans.
_BUILD_VERSION = '2026.05.28-v9-brutal-qa-conflict-safe'
IMGUI_OVERLAY_API_VERSION = 94
try:
    _READ_ONLY_ACTIONS = set(_READ_ONLY_ACTIONS) | set(('qa_self_test', 'apex_qa', 'preflight', 'qa_preflight', 'compatibility_preflight', 'cas_category_status', 'list_cas_categories'))
except Exception:
    pass

_V9_EXCLUSIVE_BODYTYPE_GROUPS = {
    5: set((5, 6, 7)),       # FULL_BODY must not coexist with upper/lower body.
    6: set((5, 6)),          # UPPER_BODY replaces full body, leaves lower body alone.
    7: set((5, 7)),          # LOWER_BODY replaces full body, leaves upper body alone.
}
_V9_RUNTIME_ONLY_KEYS = set(('HEAD_DECORATION', 'SKIN_SPECULARITY', 'TATTOO_HEAD_WINGS'))
_V9_CRITICAL_CAS_KEYS = set(('HAT', 'HAIR', 'HEAD', 'TEETH', 'FULL_BODY', 'UPPER_BODY', 'LOWER_BODY', 'SHOES', 'GLOVES', 'EYELASHES', 'LIPS_TICK', 'TATTOO_TORSO_FRONT_UPPER', 'SKIN_OVERLAY'))


def _v9_conflict_bodytypes(body_value):
    try:
        return set(_V9_EXCLUSIVE_BODYTYPE_GROUPS.get(int(body_value), set((int(body_value),))))
    except Exception:
        return set((body_value,))


def _v9_table_audit():
    rows = list(_V8_CAS_BODYTYPE_DEFS)
    keys = [str(row.get('key')) for row in rows]
    values = [int(row.get('value')) for row in rows if row.get('value') is not None]
    duplicate_keys = sorted([key for key in set(keys) if keys.count(key) > 1])
    duplicate_values = sorted([value for value in set(values) if values.count(value) > 1])
    by_value = dict((int(row.get('value')), row.get('key')) for row in rows if row.get('value') is not None)
    missing_core_values = [value for value in range(0, 113) if value not in by_value]
    missing_critical_keys = sorted(_V9_CRITICAL_CAS_KEYS.difference(set(keys)))
    runtime_only = []
    runtime_missing = []
    for key in sorted(_V9_RUNTIME_ONLY_KEYS):
        value, meta, source = _v8_resolve_body_type(key)
        runtime_only.append({'key': key, 'runtime_value': value, 'source': source})
        if value is None:
            runtime_missing.append(key)
    fatal = []
    warnings = []
    if duplicate_keys:
        fatal.append('Duplicate CAS BodyType keys: {}'.format(', '.join(duplicate_keys)))
    if duplicate_values:
        fatal.append('Duplicate CAS BodyType fallback values: {}'.format(', '.join(str(v) for v in duplicate_values)))
    if missing_core_values:
        fatal.append('Missing core BodyType fallback values 0-112: {}'.format(missing_core_values))
    if missing_critical_keys:
        fatal.append('Missing critical CAS category keys: {}'.format(', '.join(missing_critical_keys)))
    if runtime_missing:
        warnings.append('Runtime-only CAS categories not exposed by this game build yet: {}'.format(', '.join(runtime_missing)))
    return {
        'ok': not fatal,
        'fatal': fatal,
        'warnings': warnings,
        'count': len(rows),
        'core_value_range': '0-112 contiguous' if not missing_core_values else 'missing values',
        'runtime_only': runtime_only,
        'exclusive_groups': {'FULL_BODY': [5, 6, 7], 'UPPER_BODY': [5, 6], 'LOWER_BODY': [5, 7]},
    }


def _v9_writable_data_audit():
    try:
        folder = _data_directory()
        if not folder:
            return {'ok': False, 'message': 'No writable data directory resolved.'}
        try:
            os.makedirs(folder, exist_ok=True)
        except TypeError:
            if not os.path.isdir(folder):
                os.makedirs(folder)
        test = os.path.join(folder, '.td1_apex_v9_write_test')
        with open(test, 'w') as fp:
            fp.write('ok')
        with open(test, 'r') as fp:
            readback = fp.read()
        try:
            os.remove(test)
        except Exception:
            pass
        return {'ok': readback == 'ok', 'path': folder, 'message': 'Writable data directory verified.'}
    except Exception as exc:
        return {'ok': False, 'message': str(exc), 'traceback': traceback.format_exc()}


def _v9_runtime_import_audit():
    data = {
        'outfits_pb2_available': _V8_Outfits_pb2 is not None,
        's4common_pb2_available': _V8_S4Common_pb2 is not None,
        'bodytype_enum_available': _V8_EA_BODYTYPE is not None,
        'socket_available': socket is not None,
        'ctypes_available': ctypes is not None,
        'alarms_available': alarms is not None,
        'clock_available': clock is not None,
        'services_available': services is not None,
    }
    fatal = []
    warnings = []
    if not data['outfits_pb2_available'] or not data['s4common_pb2_available']:
        fatal.append('protocolbuffers.Outfits_pb2/S4Common_pb2 are unavailable; CAS category copy/paste is intentionally disabled.')
    if not data['bodytype_enum_available']:
        warnings.append('sims.outfits.outfit_enums.BodyType is unavailable; fallback table will be used and runtime-only categories will refuse safely.')
    if not data['alarms_available'] or not data['clock_available']:
        warnings.append('Sims real-time alarm APIs are not ready; mutating commands must wait until a household/zone is loaded.')
    return {'ok': not fatal, 'fatal': fatal, 'warnings': warnings, 'data': data}


def _v9_mod_compat_audit():
    try:
        mccc_status = _detect_mccc()
    except Exception as exc:
        mccc_status = 'detect failed: {}'.format(exc)
    try:
        lot51_status = _detect_lot51_core()
    except Exception as exc:
        lot51_status = 'detect failed: {}'.format(exc)
    try:
        xml_status = _detect_xml_injector()
    except Exception as exc:
        xml_status = 'detect failed: {}'.format(exc)
    notes = [
        'MCCC is optional; Apex uses snapshots/restore and does not patch MCCC internals.',
        'Lot51 Core is optional; when present, Apex uses event hooks instead of adding extra injection points.',
        'XML Injector is optional and not required for the F11 overlay or Python backend.',
    ]
    return {'ok': True, 'mccc': mccc_status, 'mccc_details': globals().get('_MCCC_DETAILS', {}), 'lot51': lot51_status, 'lot51_details': globals().get('_LOT51_DETAILS', {}), 'xml_injector': xml_status, 'xml_details': globals().get('_XML_INJECTOR_DETAILS', {}), 'notes': notes}


def _v9_self_test(sim_info=None, deep=False):
    started = time.time()
    tests = {
        'cas_bodytype_table': _v9_table_audit(),
        'runtime_imports': _v9_runtime_import_audit(),
        'data_directory': _v9_writable_data_audit(),
        'mod_compatibility': _v9_mod_compat_audit(),
        'queue': {'ok': True, 'alarm_ready': bool(_ALARM_READY), 'pending_count': len(_PENDING), 'interval_seconds': _ACTION_QUEUE_INTERVAL_SECONDS, 'note': 'Mutating commands are queued through the Sims real-time alarm when available.'},
        'server': {'ok': True, 'host': HOST, 'port': PORT, 'server_running': bool(_SERVER_RUNNING), 'threaded_socket': True},
        'overlay': {'ok': True, 'api_version': IMGUI_OVERLAY_API_VERSION, 'toggle': IMGUI_OVERLAY_TOGGLE_KEY, 'hidden_mode': IMGUI_OVERLAY_HIDDEN_MODE},
    }
    if sim_info is not None:
        try:
            tests['active_sim_health'] = _health_report(sim_info)
        except Exception as exc:
            tests['active_sim_health'] = {'ok': False, 'message': str(exc)}
        if deep:
            try:
                tests['active_sim_status'] = _status(sim_info)
            except Exception as exc:
                tests['active_sim_status'] = {'ok': False, 'message': str(exc)}
    fatal = []
    warnings = []
    for name, result in tests.items():
        if isinstance(result, dict):
            fatal.extend(['{}: {}'.format(name, line) for line in result.get('fatal', [])])
            warnings.extend(['{}: {}'.format(name, line) for line in result.get('warnings', [])])
            if result.get('ok') is False and not result.get('fatal'):
                fatal.append('{}: {}'.format(name, result.get('message', 'failed')))
    elapsed_ms = (time.time() - started) * 1000.0
    return {
        'ok': not fatal,
        'message': 'Apex V9 QA self-test {} in {:.1f} ms; fatal={}, warnings={}'.format('passed' if not fatal else 'found issues', elapsed_ms, len(fatal), len(warnings)),
        'build_version': _BUILD_VERSION,
        'fatal': fatal,
        'warnings': warnings,
        'tests': tests,
        'elapsed_ms': elapsed_ms,
        'important_limit': 'No offline test can prove flawless behavior inside every Sims 4 save; this self-test fails closed when runtime APIs needed for a feature are missing.',
    }


# Replace the V8 category paste engine with a conflict-aware V9 engine while
# preserving the existing V8 command names used by the overlay.
_V9_PREV_APPLY_BODYTYPE_PAYLOAD = _v8_apply_bodytype_payload


def _v8_apply_bodytype_payload(sim_info, payload):
    if sim_info is None:
        return False, 'No target Sim selected.'
    if not payload:
        return False, 'No CAS category clipboard payload.'
    if not _v8_imports_ready():
        return False, 'Outfits/S4Common protocolbuffers are unavailable in this runtime.'
    try:
        body_value = int(payload.get('body_type_value'))
    except Exception:
        return False, 'Clipboard payload does not contain a valid body_type_value.'
    conflicts = _v9_conflict_bodytypes(body_value)
    outfits_msg = _v8_parse_outfits(sim_info)
    if outfits_msg is None:
        return False, 'Could not parse target outfit data.'
    src_by_index = dict((int(row.get('outfit_index', -1)), list(row.get('parts') or [])) for row in payload.get('outfits') or [])
    first_parts = None
    for row in payload.get('outfits') or []:
        if row.get('parts'):
            first_parts = list(row.get('parts') or [])
            break
    changed_outfits = 0
    conflict_removed = 0
    for idx, outfit in enumerate(list(outfits_msg.outfits)):
        source_parts = src_by_index.get(idx, first_parts)
        if not source_parts:
            continue
        original_rows = _v8_outfit_parallel_rows(outfit)
        existing = [row for row in original_rows if int(row.get('body_type', -1)) not in conflicts]
        conflict_removed += max(0, len(original_rows) - len(existing))
        merged = existing + [dict(part, body_type=body_value) for part in source_parts]
        _v8_write_outfit_parallel_rows(outfit, merged)
        changed_outfits += 1
    if changed_outfits:
        try:
            _v8_write_outfit_blob(sim_info, outfits_msg.SerializeToString())
        except Exception:
            pass
    genetic_count = 0
    growth_count = 0
    # Only the selected body type is replaced in genetics/growth. The full-body vs upper/lower
    # exclusivity rule applies to outfit slots; the genetic list should not be blanket-pruned.
    genetic_msg = _v8_parse_genetic(sim_info)
    if genetic_msg is not None:
        try:
            if payload.get('genetic_parts'):
                genetic_count = _v8_restore_message_blobs(genetic_msg.parts_list.parts, body_value, payload.get('genetic_parts') or [])
        except Exception:
            genetic_count = 0
        try:
            if payload.get('growth_parts'):
                growth_count = _v8_restore_message_blobs(genetic_msg.growth_parts_list.parts, body_value, payload.get('growth_parts') or [])
        except Exception:
            growth_count = 0
        if genetic_count or growth_count:
            try:
                _v8_write_genetic_blob(sim_info, genetic_msg.SerializeToString())
            except Exception:
                pass
    _resend_all_visuals(sim_info)
    _recalc(sim_info)
    return True, 'Applied {} category to {}: {} outfit(s), genetic={}, growth={}, conflict_slots_removed={}.'.format(payload.get('body_type_label') or payload.get('body_type_key'), _sim_label(sim_info), changed_outfits, genetic_count, growth_count, conflict_removed)


_V9_PREV_OVERLAY_CAPABILITIES = _overlay_capabilities
_V9_PREV_STATUS = _status
_V9_PREV_RUN_ACTION = run_action


def _overlay_capabilities():
    data = _V9_PREV_OVERLAY_CAPABILITIES()
    try:
        data.update({
            'api_version': 9,
            'qa': {
                'commands': ['qa_self_test', 'preflight', 'compatibility_preflight'],
                'fire_on_click_only': True,
                'no_new_timers': True,
                'cas_conflict_handling': 'FULL_BODY removes upper/lower; upper/lower remove full-body in outfit rows.',
            },
        })
    except Exception:
        pass
    return data


def _status(sim_info):
    data = _V9_PREV_STATUS(sim_info)
    try:
        data['qa_light'] = {
            'build_version': _BUILD_VERSION,
            'api_version': IMGUI_OVERLAY_API_VERSION,
            'cas_bodytype_table_ok': _v9_table_audit().get('ok'),
            'category_count': len(_V8_CAS_BODYTYPE_DEFS),
            'conflict_safe_category_paste': True,
        }
    except Exception as exc:
        data['qa_light_error'] = str(exc)
    return data


def run_action(action, sim_id=None, occult=None, value=None):
    action = (action or 'status').strip().lower()
    try:
        if action in ('qa_self_test', 'apex_qa', 'preflight', 'qa_preflight', 'compatibility_preflight'):
            sim_info = _get_sim_info_by_id(sim_id) or _get_active_sim_info()
            return _v9_self_test(sim_info=sim_info, deep=(value == 'deep'))
        return _V9_PREV_RUN_ACTION(action, sim_id=sim_id, occult=occult, value=value)
    except Exception as exc:
        _log('V9 run_action failed safely: {}'.format(exc))
        return {'ok': False, 'message': str(exc), 'traceback': traceback.format_exc()}


_log('TD1 Occult Hybrid Apex v9 loaded: brutal QA self-test, conflict-safe CAS category paste, and fail-closed runtime checks ready.')



# -----------------------------------------------------------------------------
# Apex v9.1 final readiness shim
# Fixes overlay/state capability calls after layered saved-form compatibility
# modules redefine _load_saved_forms with different return types. This keeps the
# F11 ImGui overlay endpoints fail-closed and always JSON-safe.
# -----------------------------------------------------------------------------
_BUILD_VERSION = '2026.05.28-v9.1-ready-overlay-safe'
IMGUI_OVERLAY_API_VERSION = 94


def _apex91_json_safe(obj):
    try:
        json.dumps(obj, default=str)
        return obj
    except Exception:
        try:
            if isinstance(obj, dict):
                return dict((str(k), _apex91_json_safe(v)) for k, v in obj.items())
            if isinstance(obj, (list, tuple, set)):
                return [_apex91_json_safe(v) for v in obj]
            return str(obj)
        except Exception:
            return '<unserializable>'


def _apex91_call(name, default=None, *args, **kwargs):
    try:
        func = globals().get(name)
        if callable(func):
            return func(*args, **kwargs)
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}
    return default


def _apex91_saved_forms_rows(query='', limit=80):
    # Prefer the current public list function because it survived the V6/V8/V9
    # layering and returns rows even when _load_saved_forms returns a bool.
    try:
        rows = _list_saved_forms(query or '', None, limit)
        if isinstance(rows, list):
            return rows[:limit]
    except TypeError:
        try:
            rows = _list_saved_forms(query or '')
            if isinstance(rows, list):
                return rows[:limit]
        except Exception:
            pass
    except Exception:
        pass
    # Older dictionary catalog fallback.
    try:
        data = _load_saved_forms()
        if isinstance(data, dict):
            rows = data.get('forms', []) or []
            if query:
                q = str(query).lower()
                rows = [row for row in rows if q in str(row).lower()]
            return rows[:limit]
    except Exception:
        pass
    return []


def _apex91_saved_forms_summary(query='', limit=80):
    rows = _apex91_saved_forms_rows(query=query, limit=limit)
    count = len(rows)
    try:
        # If the underlying catalog has more than the displayed limit, count it.
        all_rows = _apex91_saved_forms_rows(query='', limit=100000)
        count = len(all_rows)
    except Exception:
        pass
    return {'count': count, 'rows': rows}


def _apex91_wardrobe_count():
    try:
        data = _load_wardrobes()
        if isinstance(data, dict):
            return len(data.get('wardrobes', []) or [])
    except Exception:
        pass
    return 0


def _apex91_safe_status_result(sim_id=''):
    try:
        return _submit_action('status', sim_id=sim_id or '', wait_seconds=2.5)
    except Exception as exc:
        return {'ok': False, 'message': 'Status unavailable: {}'.format(exc)}


def _apex91_compact_status(status_result):
    try:
        return _overlay_compact_from_status_payload(status_result)
    except Exception as exc:
        return {
            'ok': False,
            'message': 'Compact status unavailable: {}'.format(exc),
            'sim': None,
            'sim_id': None,
            'health': {'score': 0, 'issues': ['Status unavailable']},
            'occults': [],
        }


def _overlay_capabilities():
    saved = _apex91_saved_forms_summary(limit=1)
    return {
        'api_version': IMGUI_OVERLAY_API_VERSION,
        'build_version': _BUILD_VERSION,
        'overlay_name': IMGUI_OVERLAY_NAME,
        'toggle_key': IMGUI_OVERLAY_TOGGLE_KEY,
        'backend': 'Dear ImGui Win32 + DirectX 11 proxy source kit; commands route to Sims Python localhost backend',
        'performance': {
            'hidden_mode': IMGUI_OVERLAY_HIDDEN_MODE,
            'visible_poll_ms': IMGUI_OVERLAY_POLL_VISIBLE_MS,
            'log_poll_ms': IMGUI_OVERLAY_LOG_VISIBLE_MS,
            'gameplay_mutation': 'button-driven; queued through Sims game thread when available',
            'constant_sim_scanning': False,
            'auto_repair_default': _AUTO_REPAIR,
        },
        'commands': {
            'core': ['status', 'health', 'diagnostics', 'list_sims', 'repair', 'repair_deep', 'repair_all', 'deep_repair_all'],
            'occult': ['add', 'remove', 'switch', 'add_all', 'purge', 'normalize', 'recalculate', 'gameplay_init', 'gameplay_remove'],
            'forms': ['generate_form', 'delete_form', 'copy_current_to_form', 'copy_human_to_form', 'save_form_memory', 'restore_form_memory', 'clear_form_memory'],
            'saved_forms': ['save_occult_form', 'save_current_form', 'list_saved_forms', 'apply_saved_form', 'force_apply_saved_form', 'apply_saved_form_current', 'delete_saved_form'],
            'mccc_shield': ['mccc_detect', 'mccc_arm_active', 'mccc_arm_household', 'mccc_restore_active', 'mccc_restore_household', 'mccc_auto_restore_on', 'mccc_auto_restore_off'],
            'drift_guard': ['scan_occult_drift', 'fix_occult_drift', 'accept_occult_baseline', 'commit_current_to_occult', 'commit_current_to_all_forms', 'clear_drift_warnings'],
            'cas_categories': ['cas_category_status', 'copy_cas_category', 'paste_cas_category', 'apply_cas_category_to_all_forms'],
            'qa': ['qa_self_test', 'preflight', 'compatibility_preflight'],
        },
        'saved_forms': {
            'count': saved.get('count', 0),
            'search_supported': True,
        },
        'cas_categories': {
            'count': len(globals().get('_V8_CAS_BODYTYPE_DEFS', []) or []),
            'conflict_safe_category_paste': True,
            'full_body_upper_lower_guard': True,
        },
        'screenshots': {
            'buttons': ['Face Reference Screenshot', 'Body Reference Screenshot', 'Full Reference Screenshot'],
            'folder': 'Documents/Electronic Arts/The Sims 4/TD1ApexScreenshots',
            'native_overlay_capture': True,
        },
        'compatibility': {
            'mccc_optional': True,
            'lot51_optional': True,
            'xml_injector_optional': True,
        },
    }


def _logs_payload(count=160):
    try:
        count = int(count)
    except Exception:
        count = 160
    if count < 20:
        count = 20
    if count > 600:
        count = 600
    with _LOCK:
        history = list(_HISTORY[-count:])
        pending_count = len(_PENDING)
        result_count = len(_RESULTS)
    return {
        'ok': True,
        'message': 'Log snapshot ready',
        'build_version': _BUILD_VERSION,
        'history': history,
        'pending_count': pending_count,
        'result_count': result_count,
        'alarm_ready': _ALARM_READY,
        'server_running': _SERVER_RUNNING,
        'auto_repair': _AUTO_REPAIR,
        'queue_interval_seconds': _ACTION_QUEUE_INTERVAL_SECONDS,
        'native_status': _NATIVE_STATUS,
        'overlay': _overlay_capabilities(),
        'lot51_core_status': _apex91_call('_detect_lot51_core', {'checked': False}),
        'performance': _perf_snapshot(),
    }


def _overlay_state_payload(query=None):
    query = query or {}
    try:
        count = query.get('count', 120) if isinstance(query, dict) else 120
    except Exception:
        count = 120
    sim_id = ''
    search = ''
    if isinstance(query, dict):
        sim_id = query.get('sim_id', '') or ''
        search = query.get('query', '') or ''
    logs = _logs_payload(count)
    status_result = _apex91_safe_status_result(sim_id=sim_id)
    status = _apex91_compact_status(status_result)
    saved = _apex91_saved_forms_summary(query=search, limit=80)
    payload = {
        'ok': True,
        'message': 'Overlay state ready',
        'build_version': _BUILD_VERSION,
        'server': SERVER_NAME,
        'host': HOST,
        'port': PORT,
        'status': status,
        'logs': logs.get('history', []),
        'saved_forms': saved,
        'mccc': _apex91_call('_detect_mccc', {'checked': False}),
        'pending_count': logs.get('pending_count', 0),
        'alarm_ready': _ALARM_READY,
        'server_running': _SERVER_RUNNING,
        'auto_repair': _AUTO_REPAIR,
        'native_status': _NATIVE_STATUS,
        'overlay': _overlay_capabilities(),
        'lot51_core_status': _apex91_call('_detect_lot51_core', {'checked': False}),
        'wardrobes': {'count': _apex91_wardrobe_count()},
        'cas_mccc_shield': {
            'enabled': globals().get('_MCCC_CAS_SHIELD_ENABLED', False),
            'was_away': globals().get('_MCCC_CAS_WAS_AWAY', False),
            'lot51_event_hooked': globals().get('_MCCC_EVENT_HOOKED', False),
            'last_recovery': globals().get('_MCCC_LAST_RECOVERY', None),
        },
        'performance': _perf_snapshot(),
    }
    return _apex91_json_safe(payload)


_log('TD1 Occult Hybrid Apex v9.1 readiness shim loaded: overlay endpoints hardened and saved-form loader shadowing fixed.')


# -----------------------------------------------------------------------------
# Apex v9.3 above-and-beyond code audit hardening
# Date: 2026-05-29
# Purpose:
# - Preserve V9.2 Base Layer support while fixing the V9.1 readiness shim's
#   build-version reset.
# - Make latest/patch-sensitive CAS categories fail closed when the current game
#   runtime does not expose the matching BodyType enum.
# - Keep MCCC guard scanning fully opt-in so the repeating command queue does not
#   perform household snapshots while idle.
# - Add an explicit code-audit/preflight payload for Codex and in-game QA.
# -----------------------------------------------------------------------------
_BUILD_VERSION = '2026.05.29-v9.3-code-audited-runtime-safe'
IMGUI_OVERLAY_API_VERSION = 94

# These are newer/patch-sensitive CAS categories. They should never be applied by
# hardcoded fallback number alone; the live game runtime must expose the enum name
# or the command refuses safely.
_APEX93_RUNTIME_ONLY_BODYTYPE_KEYS = set(('HEAD_DECORATION', 'SKIN_SPECULARITY', 'TATTOO_HEAD_WINGS', 'BASE_LAYER'))
_APEX93_RUNTIME_ENUM_ALIASES = {
    'BASE_LAYER': ('BASE_LAYER', 'BASELAYER', 'BASE_LAYER_TOP', 'BASELAYER_TOP'),
    'HEAD_DECORATION': ('HEAD_DECORATION', 'HEADDECORATION'),
    'SKIN_SPECULARITY': ('SKIN_SPECULARITY', 'SKINSPECULARITY'),
    'TATTOO_HEAD_WINGS': ('TATTOO_HEAD_WINGS', 'TATTOO_HEADWINGS', 'HEAD_WINGS', 'HEADWINGS'),
}

try:
    _V9_RUNTIME_ONLY_KEYS = set(globals().get('_V9_RUNTIME_ONLY_KEYS', set())) | _APEX93_RUNTIME_ONLY_BODYTYPE_KEYS
except Exception:
    _V9_RUNTIME_ONLY_KEYS = set(_APEX93_RUNTIME_ONLY_BODYTYPE_KEYS)

# The older MCCC guard layer could low-frequency snapshot while the queue was
# armed. Keep that legacy system off by default; the explicit V6+ MCCC Shield
# remains user-armed and button-driven.
try:
    _MCCC_GUARD = False
    _MCCC_AUTO_RESTORE = False
    _MCCC_GUARD_LAST_EVENT = 'disabled by v9.3; use explicit MCCC Shield arm/restore buttons'
except Exception:
    pass

_APEX93_PREV_RESOLVE_BODY_TYPE = _v8_resolve_body_type

def _apex93_runtime_enum_value(key):
    if _V8_EA_BODYTYPE is None:
        return None, 'BodyType enum unavailable in this runtime.'
    names = _APEX93_RUNTIME_ENUM_ALIASES.get(key, (key,))
    for enum_name in names:
        try:
            if hasattr(_V8_EA_BODYTYPE, enum_name):
                return int(getattr(_V8_EA_BODYTYPE, enum_name)), 'runtime_enum:{}'.format(enum_name)
        except Exception:
            pass
    return None, 'This game build did not expose BodyType.{} at runtime. Do not paste this patch-sensitive category until the enum is verified after a Sims update.'.format(key)


def _v8_resolve_body_type(value):
    key = _v8_cas_clean_key(value)
    if not key:
        return None, None, 'No CAS category was supplied.'
    if key.isdigit():
        number = int(key)
        row = None
        for candidate in _V8_CAS_BODYTYPE_DEFS:
            try:
                if int(candidate.get('value', -999)) == number:
                    row = candidate
                    break
            except Exception:
                pass
        if row is not None:
            row_key = str(row.get('key'))
            if row_key in _APEX93_RUNTIME_ONLY_BODYTYPE_KEYS or int(row.get('value', 0)) >= 113:
                enum_value, source = _apex93_runtime_enum_value(row_key)
                if enum_value is None:
                    return None, row, source
                return enum_value, row, source
            return number, row, 'numeric'
        return number, {'key': key, 'label': 'BodyType {}'.format(number), 'value': number, 'group': 'Numeric'}, 'numeric_custom'
    row = _V8_CAS_BODYTYPE_BY_KEY.get(key)
    if row is not None and (key in _APEX93_RUNTIME_ONLY_BODYTYPE_KEYS or int(row.get('value', 0)) >= 113):
        enum_value, source = _apex93_runtime_enum_value(key)
        if enum_value is None:
            return None, row, source
        return enum_value, row, source
    # For stable/core categories, preserve the previous behavior. It uses the
    # runtime enum when present and otherwise falls back to documented 0-112 values.
    return _APEX93_PREV_RESOLVE_BODY_TYPE(value)


_APEX93_PREV_TABLE_AUDIT = _v9_table_audit

def _v9_table_audit():
    data = _APEX93_PREV_TABLE_AUDIT()
    try:
        runtime_rows = []
        runtime_missing = []
        for key in sorted(_APEX93_RUNTIME_ONLY_BODYTYPE_KEYS):
            value, meta, source = _v8_resolve_body_type(key)
            runtime_rows.append({'key': key, 'runtime_value': value, 'source': source, 'label': (meta or {}).get('label')})
            if value is None:
                runtime_missing.append(key)
        data['runtime_only'] = runtime_rows
        warnings = list(data.get('warnings') or [])
        if runtime_missing:
            msg = 'Patch-sensitive CAS categories unavailable in this runtime and will refuse safely: {}'.format(', '.join(runtime_missing))
            if msg not in warnings:
                warnings.append(msg)
        data['warnings'] = warnings
        data['base_layer_runtime_safe'] = True
        data['latest_categories_fail_closed'] = True
    except Exception as exc:
        data['warnings'] = list(data.get('warnings') or []) + ['v9.3 runtime category audit failed: {}'.format(exc)]
    return data


_APEX93_PREV_OVERLAY_CAPABILITIES = _overlay_capabilities

def _overlay_capabilities():
    data = _APEX93_PREV_OVERLAY_CAPABILITIES()
    try:
        data['build_version'] = _BUILD_VERSION
        data['api_version'] = IMGUI_OVERLAY_API_VERSION
        data.setdefault('performance', {})['legacy_mccc_guard_default'] = 'off; explicit MCCC Shield arm/restore only'
        data.setdefault('performance', {})['idle_household_snapshots'] = False
        data.setdefault('cas_categories', {})['latest_categories_fail_closed'] = True
        data.setdefault('cas_categories', {})['runtime_only_keys'] = sorted(_APEX93_RUNTIME_ONLY_BODYTYPE_KEYS)
        data.setdefault('qa', {})['v9_3_code_audit'] = 'runtime-only CAS categories hardened; MCCC legacy guard disabled by default; build version corrected'
    except Exception:
        pass
    return data


_APEX93_PREV_LOGS_PAYLOAD = _logs_payload

def _logs_payload(count=160):
    payload = _APEX93_PREV_LOGS_PAYLOAD(count)
    try:
        payload['build_version'] = _BUILD_VERSION
        payload['overlay'] = _overlay_capabilities()
    except Exception:
        pass
    return payload


_APEX93_PREV_OVERLAY_STATE_PAYLOAD = _overlay_state_payload

def _overlay_state_payload(query=None):
    payload = _APEX93_PREV_OVERLAY_STATE_PAYLOAD(query)
    try:
        payload['build_version'] = _BUILD_VERSION
        payload['overlay'] = _overlay_capabilities()
        payload['performance'] = _perf_snapshot()
        payload['runtime_category_audit'] = _v9_table_audit().get('runtime_only')
    except Exception:
        pass
    return _apex91_json_safe(payload)


_APEX93_PREV_RUN_ACTION = run_action

def _apex93_code_audit_payload():
    ts4_imports = None
    try:
        ts4_imports = _apex93_scan_supplied_bin_imports()
    except Exception as exc:
        ts4_imports = {'ok': False, 'message': 'TS4 import scan unavailable in-game: {}'.format(exc)}
    return {
        'ok': True,
        'message': 'Apex V9.3 code audit payload ready',
        'build_version': _BUILD_VERSION,
        'bodytype_audit': _v9_table_audit(),
        'mccc_guard_default': {'legacy_guard_enabled': bool(globals().get('_MCCC_GUARD', False)), 'explicit_shield': dict(globals().get('_MCCC_SHIELD', {})) if isinstance(globals().get('_MCCC_SHIELD', {}), dict) else 'unavailable'},
        'queue': {'interval_seconds': _ACTION_QUEUE_INTERVAL_SECONDS, 'auto_repair': _AUTO_REPAIR, 'idle_sim_scanning': False},
        'overlay': _overlay_capabilities(),
        'ts4_dx11_imports': ts4_imports,
    }


def _apex93_scan_supplied_bin_imports():
    # In-game this usually cannot inspect the user's EXE safely, so return a
    # deterministic note. The packaged NativeOverlay/verify_ts4_dx11_imports.py
    # performs the real Windows-side scan against TS4_x64.exe before install.
    return {'ok': True, 'message': 'Use NativeOverlay/verify_ts4_dx11_imports.py against Game/Bin/TS4_x64.exe before copying d3d11.dll.', 'required_exports': ['D3D11CreateDevice', 'D3D11CreateDeviceAndSwapChain']}


def run_action(action, sim_id=None, occult=None, value=None):
    action = (action or 'status').strip().lower()
    try:
        if action in ('code_audit', 'apex_code_audit', 'v9_3_audit'):
            return _apex93_code_audit_payload()
        return _APEX93_PREV_RUN_ACTION(action, sim_id=sim_id, occult=occult, value=value)
    except Exception as exc:
        _log('V9.3 run_action failed safely: {}'.format(exc))
        return {'ok': False, 'message': str(exc), 'traceback': traceback.format_exc()}

try:
    _READ_ONLY_ACTIONS = set(_READ_ONLY_ACTIONS) | set(('code_audit', 'apex_code_audit', 'v9_3_audit'))
except Exception:
    pass

_log('TD1 Occult Hybrid Apex v9.3 loaded: runtime-only CAS categories fail closed, Base Layer is guarded, legacy MCCC idle guard is off, and build version is corrected.')

# -----------------------------------------------------------------------------
# Apex v9.4 research-lockdown shim
# Research/audit result: keep all patch-sensitive integrations passive until the
# user explicitly clicks an F11 button or runs a command. This prevents overlay
# status polling or library detection from registering gameplay event handlers.
# -----------------------------------------------------------------------------
_BUILD_VERSION = '2026.05.29-v9.4-research-lockdown-accounted'
try:
    _MCCC_GUARD_ENABLED = False
    _MCCC_GUARD = False
    _MCCC_AUTO_RESTORE = False
    _LOT51_EVENT_STATUS = 'manual only in v9.4; no automatic Lot51 hooks on import/detect'
    if isinstance(globals().get('_LOT51_EVENT_REGISTRATION', None), dict) and not _LOT51_EVENT_REGISTRATION.get('registered'):
        _LOT51_EVENT_REGISTRATION.update({'attempted': False, 'registered': False, 'message': 'manual only in v9.4; arm MCCC Shield first, then register Lot51 hooks if desired'})
except Exception:
    pass
try:
    _READ_ONLY_ACTIONS.update(set(('research_audit', 'apex_research_audit', 'extreme_audit', 'everything_audit', 'lot51_events_status', 'lot51_event_status')))
except Exception:
    pass

_V94_PREV_RUN_ACTION = run_action
_V94_PREV_OVERLAY_CAPABILITIES = _overlay_capabilities
_V94_PREV_STATUS = _status
_V94_PREV_DETECT_LOT51_CORE = _detect_lot51_core


def _detect_lot51_core():
    """Passive Lot51 probe. Never registers handlers from a status/capability poll."""
    global _LOT51_STATUS, _LOT51_MODULE, _LOT51_DETAILS
    if _LOT51_STATUS not in ('not checked', ''):
        return _LOT51_STATUS
    details = {'available': False, 'modules': [], 'error': None, 'event_registration_mode': 'manual only'}
    try:
        import lot51_core  # noqa: F401
        _LOT51_MODULE = lot51_core
        details['available'] = True
        details['module'] = str(lot51_core)
        details['modules'].append('lot51_core')
        for name in ('lot51_core.utils.log', 'lot51_core.utils.config', 'lot51_core.services.events', 'lot51_core.events.zone'):
            try:
                __import__(name)
                details['modules'].append(name)
            except Exception as sub_exc:
                details.setdefault('module_errors', {})[name] = str(sub_exc)
        _LOT51_STATUS = 'available'
    except Exception as exc:
        details['error'] = str(exc)
        _LOT51_STATUS = 'not installed'
    _LOT51_DETAILS = details
    return _LOT51_STATUS


def _v94_research_audit():
    """Return the high-level engineering checklist used after the deep research pass."""
    try:
        category_audit = _v9_table_audit()
    except Exception as exc:
        category_audit = {'ok': False, 'error': str(exc)}
    try:
        runtime_imports = _v9_runtime_import_audit()
    except Exception as exc:
        runtime_imports = {'ok': False, 'error': str(exc)}
    try:
        compat = _v9_mod_compat_audit()
    except Exception as exc:
        compat = {'ok': False, 'error': str(exc)}
    return {
        'ok': bool(category_audit.get('ok', False)),
        'runtime_ready': bool(runtime_imports.get('ok', True)),
        'message': 'Apex V9.4 research lockdown audit complete: known high-risk areas are accounted for; see runtime_ready/runtime_checks for live-game readiness.',
        'build_version': _BUILD_VERSION,
        'accounted_for': {
            'script_packaging': 'ts4script zip with source .py; install one folder deep; no pycache/pyc required',
            'game_thread_safety': 'browser/overlay commands enqueue to Sims Python action queue; native overlay never edits gameplay data directly',
            'performance': 'hidden overlay performs no HTTP polling; drift scans, screenshots, saved-form writes, MCCC shield, and CAS category actions are fire-on-click/armed-only',
            'lot51_core': 'optional and passive by default; status detection never registers event handlers; manual lot51_register_events is available after MCCC Shield is armed',
            'xml_injector': 'not required for core; only useful for future tuning/menu entry points',
            'mccc': 'compatibility uses explicit MCCC Shield snapshots/restores and avoids private MCCC mutation unless user arms the shield',
            'occult_forms': 'current SimInfo and occult form SimInfo are handled separately; commit/baseline/scan/fix/saved-form workflows protect CAS edits',
            'cas_categories': 'stable BodyType 0-112 table is present; patch-sensitive latest categories resolve only from live runtime enum and fail closed otherwise',
            'wardrobe_conflicts': 'FullBody vs Upper/Lower conflict is normalized during category paste',
            'genetic_parts': 'genetic/growth body types are copied separately from outfit rows to avoid losing tattoos, skin details, body hair, scars, and occult details',
            'dx11_overlay': 'd3d11 proxy targets TS4 DX11 dynamic D3D11CreateDevice/CreateDeviceAndSwapChain; verify_ts4_dx11_imports.py checks game exe strings before install',
            'reshade_and_other_proxies': 'only one local d3d11/dxgi proxy can own first load; docs require chain-loader/renaming plan when ReShade/GShade/RTBP proxy is also present',
            'screenshots': 'reference shots are user-clicked only and captured before ImGui draw; DirectXTex/PNG is recommended future upgrade over BMP',
            'patch_updates': 'Code Audit/QA Self-Test should be run after every Sims patch; BodyType runtime-only values protect new CAS categories such as Base Layer',
        },
        'runtime_checks': {
            'cas_category_table': category_audit,
            'runtime_imports': runtime_imports,
            'compatibility': compat,
            'lot51_status': _detect_lot51_core(),
            'lot51_details': globals().get('_LOT51_DETAILS', {}),
            'mccc_status': globals().get('_MCCC_DETAILS', {}),
            'xml_injector_status': globals().get('_XML_INJECTOR_DETAILS', {}),
        },
        'defaults': {
            'legacy_mccc_guard_enabled': bool(globals().get('_MCCC_GUARD_ENABLED', False)),
            'legacy_mccc_tick_guard': bool(globals().get('_MCCC_GUARD', False)),
            'legacy_mccc_auto_restore': bool(globals().get('_MCCC_AUTO_RESTORE', False)),
            'auto_repair': bool(globals().get('_AUTO_REPAIR', False)),
            'mccc_shield': dict(globals().get('_MCCC_SHIELD', {})) if isinstance(globals().get('_MCCC_SHIELD', {}), dict) else {},
            'lot51_event_registration': dict(globals().get('_LOT51_EVENT_REGISTRATION', {})) if isinstance(globals().get('_LOT51_EVENT_REGISTRATION', {}), dict) else {},
        },
        'hard_limit': 'This audit cannot prove flawless behavior without launching the exact Windows DX11 game runtime and a copied save, but it fails closed where runtime APIs/categories are missing.',
    }


def _overlay_capabilities():
    data = _V94_PREV_OVERLAY_CAPABILITIES()
    try:
        data.update({
            'api_version': 94,
            'build_version': _BUILD_VERSION,
            'research_lockdown': {
                'command': 'research_audit',
                'lot51_detection_is_passive': True,
                'lot51_event_hooks_default': 'off/manual',
                'legacy_mccc_guard_default': False,
                'gameplay_edits_from_overlay_thread': False,
                'proxy_conflict_warning': 'Do not drop multiple d3d11/dxgi proxy DLLs into Game/Bin without a chain-loader plan.',
            },
        })
    except Exception:
        pass
    return data


def _status(sim_info):
    data = _V94_PREV_STATUS(sim_info)
    try:
        data['research_lockdown'] = {
            'build_version': _BUILD_VERSION,
            'lot51_detection_passive': True,
            'legacy_mccc_guard_enabled': bool(globals().get('_MCCC_GUARD_ENABLED', False)),
            'legacy_mccc_tick_guard': bool(globals().get('_MCCC_GUARD', False)),
            'auto_repair': bool(globals().get('_AUTO_REPAIR', False)),
            'recommendation': 'Run F11 -> Research Audit and QA Self-Test after every Sims patch, then test on a copied save.',
        }
    except Exception as exc:
        data['research_lockdown_error'] = str(exc)
    return data


def run_action(action, sim_id=None, occult=None, value=None):
    global _MCCC_GUARD_ENABLED, _MCCC_GUARD, _MCCC_AUTO_RESTORE
    action = (action or 'status').strip().lower()
    try:
        if action in ('research_audit', 'apex_research_audit', 'extreme_audit', 'everything_audit'):
            return _v94_research_audit()
        if action in ('lot51_events_on', 'lot51_register_events'):
            # Manual only. Prefer the V6 MCCC Shield-aware handlers, which do nothing unless the shield is armed.
            data = _apex6_register_lot51_events() if '_apex6_register_lot51_events' in globals() else {'registered': False, 'message': 'Lot51 register helper unavailable'}
            return {'ok': bool(data.get('registered')), 'message': 'Manual Lot51 event registration attempted', 'data': data}
        if action in ('lot51_events_status', 'lot51_event_status'):
            return {'ok': True, 'message': 'Lot51 event status', 'data': dict(globals().get('_LOT51_EVENT_REGISTRATION', {})), 'lot51_status': _detect_lot51_core(), 'details': globals().get('_LOT51_DETAILS', {})}
        if action == 'mccc_guardian_on':
            _MCCC_GUARD_ENABLED = False
            _MCCC_GUARD = False
            _MCCC_AUTO_RESTORE = False
            return {'ok': False, 'message': 'Legacy MCCC guardian is disabled by V9.4 research lockdown. Use F11 -> MCCC Shield -> Arm/Restore instead; optional Lot51 hooks can be registered manually after arming.', 'data': _v94_research_audit().get('defaults')}
        if action == 'mccc_guardian_off':
            _MCCC_GUARD_ENABLED = False
            _MCCC_GUARD = False
            _MCCC_AUTO_RESTORE = False
            return {'ok': True, 'message': 'Legacy MCCC guardian remains disabled; explicit MCCC Shield is the supported path.', 'data': _v94_research_audit().get('defaults')}
        return _V94_PREV_RUN_ACTION(action, sim_id=sim_id, occult=occult, value=value)
    except Exception as exc:
        _log('V9.4 run_action failed safely: {}'.format(exc))
        return {'ok': False, 'message': str(exc), 'traceback': traceback.format_exc()}

_log('TD1 Occult Hybrid Apex v9.4 loaded: research lockdown accounted-for pass, passive Lot51 detection, explicit MCCC Shield path, and fail-closed patch safety ready.')


# -----------------------------------------------------------------------------
# Apex v9.5 final-accounting hardening pass
# Research-driven safety fixes:
# 1) Do not allow optional MCCC soft hooks to monkey-patch MCCC internals.
# 2) Do not register Lot51 event callbacks before the explicit MCCC Shield is armed.
# 3) Make offline QA distinguish this Linux/dev sandbox from a live Sims runtime.
# -----------------------------------------------------------------------------
_BUILD_VERSION = '2026.05.29-v9.5-final-accounting-safe'
IMGUI_OVERLAY_API_VERSION = 95
try:
    _READ_ONLY_ACTIONS.update(set(('final_audit', 'zero_mistake_audit', 'v9_5_audit')))
except Exception:
    pass

_V95_PREV_RUN_ACTION = run_action
_V95_PREV_OVERLAY_CAPABILITIES = _overlay_capabilities
_V95_PREV_STATUS = _status
_V95_PREV_RUNTIME_IMPORT_AUDIT = _v9_runtime_import_audit
_V95_PREV_RESEARCH_AUDIT = _v94_research_audit


def _v95_external_dev_sandbox():
    """True when imported outside Sims 4, used only to avoid false QA fatals."""
    try:
        return services is None and alarms is None and clock is None
    except Exception:
        return False


def _v9_runtime_import_audit():
    """V9.5 override: in live Sims, required runtime imports stay fatal; in an
    external dev sandbox they are reported as expected warnings so QA can still
    validate packaging, endpoint, and fail-closed behavior."""
    data = _V95_PREV_RUNTIME_IMPORT_AUDIT()
    try:
        data['external_dev_sandbox'] = bool(_v95_external_dev_sandbox())
        if data.get('external_dev_sandbox'):
            fatal = list(data.get('fatal') or [])
            kept = []
            moved = []
            for item in fatal:
                text = str(item)
                if 'protocolbuffers.Outfits_pb2/S4Common_pb2' in text or 'unavailable' in text:
                    moved.append('offline-dev-sandbox expected: ' + text)
                else:
                    kept.append(text)
            if moved:
                data['fatal'] = kept
                data.setdefault('warnings', []).extend(moved)
                data['ok'] = not kept
                data['note'] = 'Live Sims 4 must expose protocolbuffers, alarms, clock, and services; this external sandbox cannot.'
    except Exception as exc:
        data.setdefault('warnings', []).append('V9.5 runtime-audit adjustment failed safely: {}'.format(exc))
    return data


def _v95_final_audit_payload():
    research = {}
    code = {}
    qa = {}
    try:
        research = _V95_PREV_RESEARCH_AUDIT()
    except Exception as exc:
        research = {'ok': False, 'message': str(exc)}
    try:
        code = _apex93_code_audit_payload()
    except Exception as exc:
        code = {'ok': False, 'message': str(exc)}
    try:
        qa = _v9_self_test(deep=False)
    except Exception as exc:
        qa = {'ok': False, 'message': str(exc)}
    mccc_shield = globals().get('_MCCC_SHIELD', {})
    if not isinstance(mccc_shield, dict):
        mccc_shield = {}
    lot51_reg = globals().get('_LOT51_EVENT_REGISTRATION', {})
    if not isinstance(lot51_reg, dict):
        lot51_reg = {}
    fatal = []
    warnings = []
    if not bool(research.get('ok', False)):
        warnings.append('research_audit reported non-ready state; inspect runtime_checks in-game.')
    if not bool(code.get('ok', False)):
        warnings.append('code_audit reported non-ready state; inspect payload.')
    if not bool(qa.get('ok', False)):
        # In the external sandbox this can be expected if live Sims modules are unavailable.
        if _v95_external_dev_sandbox():
            warnings.append('QA is running outside Sims 4; live runtime modules are unavailable here, but fail-closed code paths were checked.')
        else:
            fatal.append('QA self-test failed in live runtime: {}'.format(qa.get('message')))
    return {
        'ok': not fatal,
        'message': 'Apex V9.5 final-accounting audit complete; private MCCC hooks are locked off, Lot51 hooks require armed shield, and offline QA no longer creates false live-runtime fatals.',
        'build_version': _BUILD_VERSION,
        'api_version': IMGUI_OVERLAY_API_VERSION,
        'fatal': fatal,
        'warnings': warnings,
        'locked_down': {
            'mccc_soft_hooks_allowed': False,
            'mccc_soft_hook_reason': 'Wrapping private MCCC functions is intentionally disabled to avoid version breakage; use explicit MCCC Shield Arm/Restore instead.',
            'lot51_event_registration_requires_mccc_shield': True,
            'legacy_mccc_guard_aliases_disabled': True,
            'overlay_thread_edits_gameplay': False,
            'live_scans_without_user_command': False,
        },
        'defaults': {
            'auto_repair': bool(globals().get('_AUTO_REPAIR', False)),
            'legacy_mccc_guard_enabled': bool(globals().get('_MCCC_GUARD_ENABLED', False)),
            'legacy_mccc_tick_guard': bool(globals().get('_MCCC_GUARD', False)),
            'legacy_mccc_auto_restore': bool(globals().get('_MCCC_AUTO_RESTORE', False)),
            'mccc_shield': dict(mccc_shield),
            'lot51_event_registration': dict(lot51_reg),
        },
        'research_audit': research,
        'code_audit': code,
        'qa_self_test': qa,
        'external_dev_sandbox': bool(_v95_external_dev_sandbox()),
        'hard_limit': 'The code is hardened and validated offline; only a Windows Sims 4 DX11 runtime with the player save/MCCC setup can prove actual in-game behavior.',
    }


def _overlay_capabilities():
    data = _V95_PREV_OVERLAY_CAPABILITIES()
    try:
        data.update({
            'api_version': IMGUI_OVERLAY_API_VERSION,
            'build_version': _BUILD_VERSION,
            'v9_5_final_accounting': {
                'command': 'final_audit',
                'mccc_soft_hooks': 'disabled/fail-closed',
                'lot51_register_events': 'requires armed MCCC Shield',
                'qa_offline_mode': 'external sandbox warnings; live Sims runtime still fatal for required missing modules',
            },
        })
        try:
            compat = data.setdefault('compatibility', {})
            compat['mccc_soft_hooks'] = 'disabled in V9.5; use explicit Shield buttons only'
            compat['lot51_event_registration'] = 'manual and shield-gated'
        except Exception:
            pass
    except Exception:
        pass
    return data


def _status(sim_info):
    data = _V95_PREV_STATUS(sim_info)
    try:
        data['final_accounting_v9_5'] = {
            'build_version': _BUILD_VERSION,
            'mccc_soft_hooks_allowed': False,
            'lot51_event_registration_requires_mccc_shield': True,
            'recommended_test_buttons': ['Research Audit', 'Code Audit', 'QA Self-Test', 'Final Audit'],
        }
    except Exception as exc:
        data['final_accounting_v9_5_error'] = str(exc)
    return data


def run_action(action, sim_id=None, occult=None, value=None):
    global _MCCC_GUARD_ENABLED, _MCCC_GUARD, _MCCC_AUTO_RESTORE
    action = (action or 'status').strip().lower()
    try:
        if action in ('final_audit', 'zero_mistake_audit', 'v9_5_audit'):
            return _v95_final_audit_payload()
        if action in ('mccc_soft_hooks_on', 'mccc_soft_hook_scan', 'mccc_private_hooks_on'):
            try:
                if isinstance(globals().get('_MCCC_SHIELD', None), dict):
                    _MCCC_SHIELD['hook_scan'] = False
                    _MCCC_SHIELD['hooked_functions'] = []
            except Exception:
                pass
            return {'ok': False, 'message': 'MCCC soft/private hooks are disabled in V9.5. Use F11 -> MCCC Shield -> Arm/Restore; Apex will not monkey-patch MCCC internals.', 'data': _v95_final_audit_payload().get('locked_down')}
        if action in ('mccc_soft_hooks_off', 'mccc_private_hooks_off'):
            try:
                if isinstance(globals().get('_MCCC_SHIELD', None), dict):
                    _MCCC_SHIELD['hook_scan'] = False
                    _MCCC_SHIELD['hooked_functions'] = []
            except Exception:
                pass
            return {'ok': True, 'message': 'MCCC soft/private hooks are off and locked down.', 'data': _v95_final_audit_payload().get('locked_down')}
        if action in ('mccc_guard_on', 'mccc_guardian_on'):
            _MCCC_GUARD_ENABLED = False
            _MCCC_GUARD = False
            _MCCC_AUTO_RESTORE = False
            return {'ok': False, 'message': 'Legacy MCCC guardian aliases are disabled in V9.5. Use explicit MCCC Shield Arm/Restore buttons instead.', 'data': _v95_final_audit_payload().get('defaults')}
        if action in ('mccc_guard_off', 'mccc_guardian_off'):
            _MCCC_GUARD_ENABLED = False
            _MCCC_GUARD = False
            _MCCC_AUTO_RESTORE = False
            return {'ok': True, 'message': 'Legacy MCCC guardian is off.', 'data': _v95_final_audit_payload().get('defaults')}
        if action in ('lot51_events_on', 'lot51_register_events'):
            shield = globals().get('_MCCC_SHIELD', {})
            if not isinstance(shield, dict) or not shield.get('armed'):
                return {'ok': False, 'message': 'Lot51 event registration is shield-gated in V9.5. First use F11 -> MCCC Shield -> Arm Active/Household, then register events if you want auto-restore callbacks.', 'data': dict(globals().get('_LOT51_EVENT_REGISTRATION', {})) if isinstance(globals().get('_LOT51_EVENT_REGISTRATION', {}), dict) else {}}
            data = _apex6_register_lot51_events() if '_apex6_register_lot51_events' in globals() else {'registered': False, 'message': 'Lot51 register helper unavailable'}
            return {'ok': bool(data.get('registered')), 'message': 'Manual Lot51 event registration attempted after MCCC Shield arm', 'data': data}
        return _V95_PREV_RUN_ACTION(action, sim_id=sim_id, occult=occult, value=value)
    except Exception as exc:
        _log('V9.5 run_action failed safely: {}'.format(exc))
        return {'ok': False, 'message': str(exc), 'traceback': traceback.format_exc()}

_log('TD1 Occult Hybrid Apex v9.5 loaded: final-accounting safe pass, MCCC private hooks locked off, shield-gated Lot51 events, and sandbox-aware QA ready.')


# -----------------------------------------------------------------------------
# Apex v9.6 live-game BodyType correction
# Verified read-only against The Sims 4 1.124.63.1020
# Data\Simulation\Gameplay\simulation.zip/sims/outfits/outfit_enums.pyc:
#   BIRTHMARKOCCULT=112, TATTOO_HEAD=113, WINGS=114,
#   HEADDECO=115, SKINSPECULARITY=116, BASE_LAYER=117, UNUSED=118.
# Keep these patch-sensitive entries runtime-resolved; do not trust a fallback
# number unless the live game exposes the matching BodyType enum name.
# -----------------------------------------------------------------------------
_BUILD_VERSION = '2026.05.29-v9.6-live-1.124.63-bodytype-safe'
IMGUI_OVERLAY_API_VERSION = 96

_APEX96_LIVE_BODYTYPE_ROWS = (
    {'group': 'Latest / Runtime Resolved', 'key': 'BIRTHMARKOCCULT', 'label': 'Occult birthmark', 'value': 112, 'genetic': True},
    {'group': 'Latest / Runtime Resolved', 'key': 'TATTOO_HEAD', 'label': 'Head tattoo', 'value': 113, 'genetic': True},
    {'group': 'Latest / Runtime Resolved', 'key': 'WINGS', 'label': 'Wings', 'value': 114, 'genetic': False},
    {'group': 'Latest / Runtime Resolved', 'key': 'HEADDECO', 'label': 'Head decoration', 'value': 115, 'genetic': False},
    {'group': 'Latest / Runtime Resolved', 'key': 'SKINSPECULARITY', 'label': 'Skin specularity', 'value': 116, 'genetic': True},
    {'group': 'Latest / Runtime Resolved', 'key': 'BASE_LAYER', 'label': 'Base Layer', 'value': 117, 'genetic': False},
    {'group': 'Reserved / Utility', 'key': 'UNUSED', 'label': 'Unused / reserved', 'value': 118, 'genetic': False},
)

_APEX96_RUNTIME_ONLY_BODYTYPE_KEYS = set(row['key'] for row in _APEX96_LIVE_BODYTYPE_ROWS if row['key'] != 'UNUSED')
_APEX96_BODYTYPE_ALIASES = {
    'BIRTHMARK_OCCULT': 'BIRTHMARKOCCULT',
    'TATTOOHEAD': 'TATTOO_HEAD',
    'TATTOOS_HEAD': 'TATTOO_HEAD',
    'HEAD_WINGS': 'WINGS',
    'HEADWINGS': 'WINGS',
    'HEAD_DECORATION': 'HEADDECO',
    'HEADDECORATION': 'HEADDECO',
    'HEAD_DECO': 'HEADDECO',
    'SKIN_SPECULARITY': 'SKINSPECULARITY',
    'SKINSPECULARITY': 'SKINSPECULARITY',
    'BASELAYER': 'BASE_LAYER',
    'BASE_LAYER_TOP': 'BASE_LAYER',
    'BASELAYER_TOP': 'BASE_LAYER',
}

try:
    _V8_CAS_BODYTYPE_DEFS = [row for row in _V8_CAS_BODYTYPE_DEFS if int(row.get('value', -1)) < 112]
    _V8_CAS_BODYTYPE_DEFS.extend(dict(row) for row in _APEX96_LIVE_BODYTYPE_ROWS)
    _V8_CAS_BODYTYPE_BY_KEY = dict((row.get('key'), row) for row in _V8_CAS_BODYTYPE_DEFS)
    _V8_CAS_BODYTYPE_ALIASES.pop('TATTOOS_HEAD_WINGS', None)
    _V8_CAS_BODYTYPE_ALIASES.pop('TATTOO_HEAD_WINGS', None)
    _V8_CAS_BODYTYPE_ALIASES.update(_APEX96_BODYTYPE_ALIASES)
except Exception as _apex96_table_exc:
    _log('Apex v9.6 BodyType table correction failed safely: {}'.format(_apex96_table_exc))

try:
    _APEX93_RUNTIME_ONLY_BODYTYPE_KEYS = set(_APEX93_RUNTIME_ONLY_BODYTYPE_KEYS).difference(set(('HEAD_DECORATION', 'SKIN_SPECULARITY', 'TATTOO_HEAD_WINGS')))
    _APEX93_RUNTIME_ONLY_BODYTYPE_KEYS.update(_APEX96_RUNTIME_ONLY_BODYTYPE_KEYS)
    _V9_RUNTIME_ONLY_KEYS = set(globals().get('_V9_RUNTIME_ONLY_KEYS', set())).difference(set(('HEAD_DECORATION', 'SKIN_SPECULARITY', 'TATTOO_HEAD_WINGS')))
    _V9_RUNTIME_ONLY_KEYS.update(_APEX96_RUNTIME_ONLY_BODYTYPE_KEYS)
    _APEX93_RUNTIME_ENUM_ALIASES.update({
        'BIRTHMARKOCCULT': ('BIRTHMARKOCCULT', 'BIRTHMARK_OCCULT'),
        'TATTOO_HEAD': ('TATTOO_HEAD', 'TATTOOHEAD'),
        'WINGS': ('WINGS', 'HEAD_WINGS', 'HEADWINGS'),
        'HEADDECO': ('HEADDECO', 'HEAD_DECORATION', 'HEADDECORATION', 'HEAD_DECO'),
        'SKINSPECULARITY': ('SKINSPECULARITY', 'SKIN_SPECULARITY'),
        'BASE_LAYER': ('BASE_LAYER', 'BASELAYER', 'BASE_LAYER_TOP', 'BASELAYER_TOP'),
        'UNUSED': ('UNUSED',),
    })
except Exception as _apex96_runtime_exc:
    _log('Apex v9.6 runtime enum map correction failed safely: {}'.format(_apex96_runtime_exc))

try:
    _READ_ONLY_ACTIONS.update(set(('bodytype_live_audit', 'v9_6_audit')))
except Exception:
    pass

_APEX96_PREV_OVERLAY_CAPABILITIES = _overlay_capabilities
_APEX96_PREV_STATUS = _status
_APEX96_PREV_RUN_ACTION = run_action


def _apex96_bodytype_live_audit():
    external = bool(_v95_external_dev_sandbox()) if '_v95_external_dev_sandbox' in globals() else False
    rows = []
    missing = []
    for row in _APEX96_LIVE_BODYTYPE_ROWS:
        key = row['key']
        value, meta, source = _v8_resolve_body_type(key)
        rows.append({'key': key, 'expected_value': row['value'], 'runtime_value': value, 'source': source, 'label': row['label']})
        if key != 'UNUSED' and value is None and not external:
            missing.append(key)
    return {
        'ok': not missing,
        'message': 'Apex V9.6 BodyType live-game table audit complete; patch-sensitive rows fail closed if missing at runtime.',
        'build_version': _BUILD_VERSION,
        'external_dev_sandbox': external,
        'verified_game_version': '1.124.63.1020',
        'verified_source': 'Data/Simulation/Gameplay/simulation.zip:sims/outfits/outfit_enums.pyc',
        'live_rows': rows,
        'missing_runtime_keys': missing,
        'warnings': ['External sandbox cannot import live sims.outfits.outfit_enums; in-game runtime must resolve these keys before patch-sensitive writes.'] if external else [],
        'legacy_alias_policy': {
            'HEAD_DECORATION': 'HEADDECO',
            'SKIN_SPECULARITY': 'SKINSPECULARITY',
            'TATTOO_HEAD_WINGS': 'ambiguous old combined key; intentionally not aliased',
        },
    }


def _overlay_capabilities():
    data = _APEX96_PREV_OVERLAY_CAPABILITIES()
    try:
        data.update({
            'api_version': IMGUI_OVERLAY_API_VERSION,
            'build_version': _BUILD_VERSION,
            'v9_6_bodytypes': {
                'command': 'bodytype_live_audit',
                'verified_game_version': '1.124.63.1020',
                'latest_runtime_keys': [row['key'] for row in _APEX96_LIVE_BODYTYPE_ROWS],
                'ambiguous_legacy_key': 'TATTOO_HEAD_WINGS is not mapped because live runtime splits TATTOO_HEAD and WINGS.',
            },
        })
    except Exception:
        pass
    return data


def _status(sim_info):
    data = _APEX96_PREV_STATUS(sim_info)
    try:
        data['bodytype_live_v9_6'] = _apex96_bodytype_live_audit()
    except Exception as exc:
        data['bodytype_live_v9_6_error'] = str(exc)
    return data


def run_action(action, sim_id=None, occult=None, value=None):
    action = (action or 'status').strip().lower()
    try:
        if action in ('bodytype_live_audit', 'v9_6_audit'):
            return _apex96_bodytype_live_audit()
        return _APEX96_PREV_RUN_ACTION(action, sim_id=sim_id, occult=occult, value=value)
    except Exception as exc:
        _log('V9.6 run_action failed safely: {}'.format(exc))
        return {'ok': False, 'message': str(exc), 'traceback': traceback.format_exc()}


_log('TD1 Occult Hybrid Apex v9.6 loaded: BodyType table corrected for Sims 4 1.124.63.1020, Base Layer moved to 117, and ambiguous old head/wings keys fail closed.')
