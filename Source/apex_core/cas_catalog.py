"""Bounded read-only CASP slider metadata from the effective game resource.

Format facts researched against SimRipper CASP and the installed v52 resource;
no third-party parser implementation or game resource bytes are bundled.
"""
import hashlib
import math
import struct

MAX_CASP = 1024 * 1024
MAX_CASP_KEYS = 250000
_INDEX_OWNER = None
_KEY_INDEX = None


def _key_values(key, resource_type, instance=None):
    values = (getattr(key, 'type', None), getattr(key, 'group', None), getattr(key, 'instance', None))
    if (any(type(value) is not int for value in values) or
            values[0] != resource_type or not 0 <= values[1] <= 0xffffffff or
            not 0 < values[2] <= 0xffffffffffffffff or
            instance is not None and values[2] != instance):
        raise ValueError('The native CASP resource key has an invalid type/group/instance identity.')
    return values


def _effective_key(resources, part_id):
    """Resolve the actual group from the game's resource manager, not a default.

    get_resource_key(integer, type) constructs a group-zero key. CC frequently
    uses other groups. The loaded resource index is fixed for this game session;
    build its bounded identity map once, while reading effective bytes fresh on
    every inspection. Conflicting groups for one part remain ambiguous.
    """
    global _INDEX_OWNER, _KEY_INDEX
    constructed = resources.get_resource_key(part_id, resources.Types.CASPART)
    _key_values(constructed, resources.Types.CASPART, part_id)
    enumerate_keys = getattr(resources, 'list', None)
    if not callable(enumerate_keys):
        # Older integrations without an index can only load their exact key.
        return constructed
    if _INDEX_OWNER is not resources or _KEY_INDEX is None:
        index = {}
        for count, key in enumerate(enumerate_keys(type=resources.Types.CASPART)):
            if count >= MAX_CASP_KEYS:
                raise ValueError('Native CASP resource index exceeds its inspection bound.')
            values = _key_values(key, resources.Types.CASPART)
            index.setdefault(values[2], {})[values] = key
        _INDEX_OWNER, _KEY_INDEX = resources, index
    matches = _KEY_INDEX.get(part_id, {})
    if len(matches) != 1:
        raise ValueError('Native CAS part resource is missing or has ambiguous resource groups.')
    return next(iter(matches.values()))


class Reader:
    def __init__(self, raw):
        if not isinstance(raw, bytes) or not 64 <= len(raw) <= MAX_CASP:
            raise ValueError('CASP is not bounded resource bytes.')
        self.raw, self.position, self.limit = raw, 0, len(raw)

    def take(self, count):
        if count < 0 or self.position + count > self.limit:
            raise ValueError('CASP header is truncated or overlaps its resource table.')
        result = self.raw[self.position:self.position + count]
        self.position += count
        return result

    def value(self, kind):
        return struct.unpack('<' + kind, self.take(struct.calcsize('<' + kind)))[0]

    def count(self, maximum):
        value = self.value('i')
        if not 0 <= value <= maximum:
            raise ValueError('CASP array count exceeds its bound.')
        return value

    def string(self):
        count = 0
        for index in range(5):
            byte = self.value('B')
            count |= (byte & 127) << (index * 7)
            if not byte & 128:
                if count > 4096 or count % 2:
                    raise ValueError('CASP UTF-16 string has an invalid byte length.')
                return self.take(count).decode('utf-16-be')
        raise ValueError('CASP string length is invalid.')


def slider_metadata(raw):
    reader = Reader(raw)
    version, table = reader.value('I'), reader.value('I') + 8
    if version not in range(44, 53):
        raise ValueError('CASP version {} is not a verified slider layout.'.format(version))
    if not 64 <= table < len(raw):
        raise ValueError('CASP resource table offset is invalid.')
    reader.limit = table
    if reader.value('i') != 0:
        raise ValueError('Unexpected CASP preset data; no slider write is permitted.')
    name = reader.string()
    reader.take(4 + 2 + 4 + 4 + 2)  # sort/swatch/outfit/material/parameter flags
    if version >= 50:
        reader.take(2)  # layer ID
    if version >= 51:
        reader.take(reader.count(512) * 8)
    else:
        reader.take(16)  # v41+ part exclusions
    reader.take(8)  # modifier region flags
    reader.take(reader.count(4096) * 6)  # uint16 tag type + uint32 tag value
    reader.take(16 + 1)  # price/title/description/v43 field + texture space
    body_type = reader.value('I')
    reader.take(4 + 4 + 4 + 12)  # subtype/age-gender/species/pack fields
    reader.take(reader.value('B') * 4)  # swatch colors
    reader.take(2 + 8)  # buff/swatch keys + voice hash
    if reader.value('B'):
        reader.take(12)  # material hashes, stored once when material count > 0
    reader.take(4)  # occult flags
    if version >= 46:
        reader.take(8)
    reader.take(16)  # opposite-gender and fallback part IDs
    opacity_min, opacity_step = reader.value('f'), reader.value('f')
    settings = {'opacity': {'min': opacity_min, 'max': 1.0, 'step': opacity_step}}
    for channel in ('hue', 'saturation', 'brightness'):
        settings[channel] = dict(zip(('min', 'max', 'step'), (reader.value('f') for _ in range(3))))
    for channel, bounds in settings.items():
        low, high, step = (bounds[key] for key in ('min', 'max', 'step'))
        if not all(math.isfinite(value) for value in (low, high, step)) or step < 0 or low > high:
            raise ValueError('CASP slider bounds are invalid.')
        bounds['enabled'] = step > 0 and high != 0 and low < high
        # Inspection preserves genuine metadata. Editing rejects values outside
        # Q14 separately; neither parser nor renderer silently clamps the Sim.
    return {'version': version, 'body_type': body_type, 'part_name': name,
            'resource_sha256': hashlib.sha256(raw).hexdigest(), 'ranges': settings}


def effective_metadata(backend, part_id):
    if type(part_id) is not int or not 0 < part_id <= 0xffffffffffffffff:
        raise ValueError('An exact nonzero CAS part instance is required.')
    resource_tgi = None
    provider = getattr(backend, '_studio_casp_bytes', None)
    if provider is not None:
        raw = provider(part_id)
    else:
        from sims4 import resources
        key = _effective_key(resources, part_id)
        values = _key_values(key, resources.Types.CASPART, part_id)
        resource_tgi = '{:08X}:{:08X}:{:016X}'.format(*values)
        value = resources.ResourceLoader(key).load_raw(silent_fail=True)
        if value is None:
            raise ValueError('The effective CAS part resource could not be read.')
        raw = bytes(value)
    metadata = slider_metadata(raw)
    metadata['resource_tgi'] = resource_tgi
    metadata['resource_key_query'] = 'native-key' if resource_tgi is not None else 'unavailable'
    return metadata
