"""Exact readable appearance evidence, separate from gameplay/occult flags.

No pickle, repr snapshots, arbitrary classes or executable deserialization.
The current installed game's SimInfoBaseWrapper defines these appearance fields.
"""
import base64
import hashlib
import json
import math

FIELDS = ('physique', 'facial_attributes', 'skin_tone', 'skin_tone_val_shift',
          'pelt_layers', 'genetic_data', 'custom_texture', 'parts_custom_tattoos',
          'voice_pitch', 'voice_actor', 'voice_effect')


def encode(value, depth=0):
    if depth > 8:
        raise ValueError('Appearance value nesting exceeds its bound.')
    if value is None or isinstance(value, (bool, str, int)):
        return {'kind': 'value', 'value': value}
    if isinstance(value, float) and math.isfinite(value):
        return {'kind': 'value', 'value': value}
    if isinstance(value, bytes):
        return {'kind': 'bytes', 'value': base64.b64encode(value).decode('ascii')}
    if isinstance(value, tuple) and len(value) == 2 and value[0] == 'protobuf' and isinstance(value[1], bytes):
        return {'kind': 'protobuf', 'value': base64.b64encode(value[1]).decode('ascii')}
    if hasattr(value, 'SerializeToString'):
        return {'kind': 'protobuf', 'value': base64.b64encode(value.SerializeToString()).decode('ascii')}
    if isinstance(value, (tuple, list)) and len(value) <= 1024:
        return {'kind': 'tuple' if isinstance(value, tuple) else 'list', 'value': [encode(item, depth + 1) for item in value]}
    if isinstance(value, dict) and len(value) <= 1024 and all(isinstance(key, (str, int)) for key in value):
        return {'kind': 'mapping', 'value': [[encode(key, depth + 1), encode(item, depth + 1)] for key, item in value.items()]}
    if all(hasattr(value, name) for name in ('type', 'group', 'instance')):
        return {'kind': 'resourcekey', 'value': [int(value.type), int(value.instance), int(value.group)]}
    raise ValueError('Unsupported native appearance value: ' + type(value).__name__)


def decode(row, depth=0):
    if not isinstance(row, dict) or set(row) != {'kind', 'value'} or depth > 8:
        raise ValueError('Invalid typed appearance value.')
    kind, value = row['kind'], row['value']
    if kind == 'value':
        if value is None or isinstance(value, (bool, str, int)) or isinstance(value, float) and math.isfinite(value):
            return value
    if kind in ('bytes', 'protobuf') and isinstance(value, str) and len(value) <= 12 * 1024 * 1024:
        raw = base64.b64decode(value, validate=True)
        return ('protobuf', raw) if kind == 'protobuf' else raw
    if kind in ('tuple', 'list') and isinstance(value, list) and len(value) <= 1024:
        decoded = [decode(item, depth + 1) for item in value]
        return tuple(decoded) if kind == 'tuple' else decoded
    if kind == 'dict' and isinstance(value, dict) and len(value) <= 1024:
        return {key: decode(item, depth + 1) for key, item in value.items()}
    if kind == 'mapping' and isinstance(value, list) and len(value) <= 1024:
        result = {}
        for pair in value:
            if not isinstance(pair, list) or len(pair) != 2:
                raise ValueError('Invalid native appearance mapping.')
            key, item = decode(pair[0], depth + 1), decode(pair[1], depth + 1)
            if not isinstance(key, (str, int)) or key in result:
                raise ValueError('Invalid/duplicate native appearance mapping key.')
            result[key] = item
        return result
    if kind == 'resourcekey' and isinstance(value, list) and len(value) == 3 and all(type(item) is int and 0 <= item < 1 << 64 for item in value):
        from sims4.resources import Key
        return Key(*value)
    raise ValueError('Unknown or malformed appearance value.')


def packed(backend, sim):
    fields = {}
    for name in FIELDS:
        try:
            value = getattr(sim, name)
        except AttributeError:
            continue
        fields[name] = encode(value)
    raw = backend._v8_read_outfit_blob(sim)
    if not isinstance(raw, bytes) or not raw:
        raise ValueError('A complete native outfit payload is required.')
    fields['__outfits__'] = encode(('protobuf', raw))
    return fields


def payload(fields):
    if not isinstance(fields, dict) or not fields or set(fields) - set(FIELDS + ('__outfits__',)):
        raise ValueError('Snapshot contains fields outside appearance ownership.')
    return {name: decode(value) for name, value in fields.items()}


def fingerprint(fields):
    payload(fields)  # Validate every value before accepting its identity.
    from .outfit_snapshot import normalize
    canonical = dict(fields)
    if '__outfits__' in canonical:
        raw = decode(canonical['__outfits__'])[1]
        canonical['__outfits__'] = encode(('protobuf', normalize(raw)))
    identities = {name: hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                  ensure_ascii=True, allow_nan=False).encode('utf-8')).hexdigest() for name, value in canonical.items()}
    digest = hashlib.sha256(json.dumps(identities, sort_keys=True, separators=(',', ':')).encode('ascii')).hexdigest()
    return {'appearance_sha256': digest, 'field_sha256': identities, 'readable_fields': sorted(fields),
            'scope': 'All readable native appearance fields plus every normalized outfit byte; gameplay excluded.'}


def evidence(backend, sim, export=False):
    fields = packed(backend, sim)
    result = fingerprint(fields)
    if export:
        result['typed_payload'] = fields
    return result
