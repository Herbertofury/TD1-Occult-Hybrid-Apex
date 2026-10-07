"""Bounded read-only CASP slider metadata from the effective game resource.

Format facts researched against SimRipper CASP and the installed v52 resource;
no third-party parser implementation or game resource bytes are bundled.
"""
import hashlib
import math
import struct

MAX_CASP = 1024 * 1024


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
    provider = getattr(backend, '_studio_casp_bytes', None)
    if provider is not None:
        raw = provider(part_id)
    else:
        from sims4 import resources
        key = resources.get_resource_key(part_id, resources.Types.CASPART)
        value = resources.ResourceLoader(key).load_raw(silent_fail=True)
        if value is None:
            raise ValueError('The effective CAS part resource could not be read.')
        raw = bytes(value)
    return slider_metadata(raw)
