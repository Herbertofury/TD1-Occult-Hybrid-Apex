"""Lossless compressed native Sim records for every accepted history checkpoint.

Descriptor discovery is runtime-based; absent/new/extension fields remain in
catalogs and unknown wire fields remain in exact native bytes. Recorded native
state is evidence only: appearance Undo never reloads identity/gameplay data.
"""
import base64
import hashlib
import json
import zlib
from . import sim_data

MAX_RECORD = 7 * 1024 * 1024


def archive(record):
    raw = json.dumps(record, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(',', ':')).encode('utf-8')
    if len(raw) > MAX_RECORD:
        raise ValueError('Complete Sim record exceeds its bound; no fields omitted.')
    return {'encoding': 'zlib-base64', 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
            'native_sha256': record['native_sha256'],
            'value': base64.b64encode(zlib.compress(raw, 6)).decode('ascii')}


def restore(row):
    if row.get('encoding') != 'zlib-base64' or not 0 < row.get('bytes', 0) <= MAX_RECORD:
        raise ValueError('Invalid complete Sim record bound.')
    if not isinstance(row.get('value'), str) or len(row['value']) > MAX_RECORD * 2:
        raise ValueError('Compressed Sim record exceeds its bound.')
    stream = zlib.decompressobj()
    raw = stream.decompress(base64.b64decode(row['value'], validate=True), MAX_RECORD + 1)
    if not stream.eof or stream.unused_data or stream.unconsumed_tail or len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
        raise ValueError('Complete Sim record is corrupt/truncated; no partial read accepted.')
    result = json.loads(raw.decode('utf-8'))
    if result['native_sha256'] != row['native_sha256']:
        raise ValueError('Native Sim record identity differs.')
    return result


def capture(backend, sim):
    provider = getattr(backend, '_studio_native_record', None)
    return archive(provider(sim) if provider is not None else sim_data.snapshot(backend, sim))


def delta(before, after):
    left, right = restore(before), restore(after)
    fields = lambda data: {row['number']: row for row in data['data']['fields']}
    a, b = fields(left), fields(right)
    changes = [b.get(number, a.get(number))['name'] for number in sorted(set(a) | set(b)) if a.get(number) != b.get(number)]
    return {'changed_native_fields': changes, 'schema_changed': left['field_schemas'] != right['field_schemas'],
            'native_bytes_changed': left['native_sha256'] != right['native_sha256'],
            'unknown_wire_changes_possible': not changes and left['native_sha256'] != right['native_sha256']}
