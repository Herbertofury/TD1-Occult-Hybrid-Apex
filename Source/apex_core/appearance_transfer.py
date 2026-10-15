"""Cross-Sim/form appearance clipboard and selective, detached paste.

No Sim identity, household, occult membership, progression or traits are in an
appearance clipboard. Outfits retain destination identities; typed row edits
preserve every parallel array and unselected part, including layered tattoos.
"""
import copy
import hashlib
import json
import uuid
import base64
import time
from collections import OrderedDict
from . import form_appearance as appearance
from .dresser_parts import read_rows, write_rows, uint

_CLIPS = OrderedDict()
_UPLOADS = {}
MAX_BYTES = 8 * 1024 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(',', ':')).encode('utf-8')


def capture(fields, source):
    appearance.payload(fields)
    if not isinstance(source, dict) or set(source) != {'kind', 'sim_id', 'form', 'label'}:
        raise ValueError('Exact appearance clipboard provenance required.')
    if (source['kind'] not in ('sim', 'tray') or not isinstance(source['sim_id'], str)
            or not source['sim_id'].isdigit() or str(int(source['sim_id'])) != source['sim_id']
            or not 0 < int(source['sim_id']) < 1 << 64 or type(source['form']) is not int
            or not 0 < source['form'] < 1 << 32 or not isinstance(source['label'], str)
            or len(source['label']) > 256 or any(ord(c) < 32 for c in source['label'])):
        raise ValueError('Appearance clipboard source identity is untyped or unbounded.')
    raw = canonical(fields)
    if len(raw) > MAX_BYTES: raise ValueError('Appearance clipboard exceeds its bound.')
    token = uuid.uuid4().hex
    row = {'id': token, 'sha256': hashlib.sha256(raw).hexdigest(), 'fields': copy.deepcopy(fields), 'source': copy.deepcopy(source)}
    while _CLIPS and (len(_CLIPS) >= 8 or sum(len(canonical(r['fields'])) for r in _CLIPS.values()) + len(raw) > 32 * 1024 * 1024):
        _CLIPS.popitem(last=False)
    _CLIPS[token] = row
    return copy.deepcopy(row)


def upload(operation, request):
    """Bounded staging; finish validates data before it becomes a clipboard."""
    now = time.monotonic()
    for key in list(_UPLOADS):
        if _UPLOADS[key]['expires'] < now: del _UPLOADS[key]
    if operation == 'begin':
        if (not isinstance(request, dict) or set(request) != {'sha256', 'bytes'}
                or type(request['bytes']) is not int or not 0 < request['bytes'] <= MAX_BYTES
                or not isinstance(request['sha256'], str) or len(request['sha256']) != 64
                or any(c not in '0123456789abcdef' for c in request['sha256']) or len(_UPLOADS) >= 2):
            raise ValueError('One bounded clipboard upload intent is required.')
        token = uuid.uuid4().hex
        _UPLOADS[token] = dict(request, raw=bytearray(), index=0, expires=now + 600)
        return {'upload_id': token, 'next_index': 0}
    expected = {'upload_id', 'index', 'data'} if operation == 'chunk' else {'upload_id'}
    if not isinstance(request, dict) or set(request) != expected or request['upload_id'] not in _UPLOADS:
        raise ValueError('Clipboard upload expired or its request fields differ.')
    row = _UPLOADS[request['upload_id']]
    if operation == 'chunk':
        if type(request['index']) is not int or request['index'] != row['index'] or not isinstance(request['data'], str) or not 0 < len(request['data']) <= 4096:
            raise ValueError('Clipboard chunk is unbounded, repeated or out of order.')
        part = base64.b64decode(request['data'], validate=True)
        if len(row['raw']) + len(part) > row['bytes']: raise ValueError('Clipboard upload exceeds its exact declared extent.')
        row['raw'].extend(part); row['index'] += 1
        return {'upload_id': request['upload_id'], 'next_index': row['index']}
    if operation != 'finish': raise ValueError('Unknown clipboard upload operation.')
    if len(row['raw']) != row['bytes'] or hashlib.sha256(row['raw']).hexdigest() != row['sha256']:
        raise ValueError('Clipboard upload is incomplete or differs from its declared hash.')
    data = json.loads(row['raw'].decode('utf-8'))
    if not isinstance(data, dict) or set(data) != {'fields', 'source'}: raise ValueError('Clipboard import fields differ.')
    result = capture(data['fields'], data['source'])
    del _UPLOADS[request['upload_id']]
    return result


def get(token, expected):
    if not isinstance(token, str) or token not in _CLIPS:
        raise ValueError('Appearance clipboard expired or belongs to a different game process; copy again.')
    row = _CLIPS[token]
    if expected != row['sha256'] or hashlib.sha256(canonical(row['fields'])).hexdigest() != expected:
        raise ValueError('Appearance clipboard identity changed.')
    return copy.deepcopy(row)


def _parse(backend, fields):
    raw = appearance.decode(fields['__outfits__'])
    if not isinstance(raw, tuple) or raw[0] != 'protobuf': raise ValueError('Typed complete outfit protobuf required.')
    provider = getattr(backend, '_studio_parse_snapshot', None)
    if provider is not None: return provider(raw[1])
    message = backend._V8_Outfits_pb2.OutfitList(); message.ParseFromString(raw[1]); return message


def _index(value, outfits):
    if type(value) is not int or not 0 <= value < len(outfits): raise ValueError('Select an exact existing numbered outfit.')
    return outfits[value]


def _identity_map(outfits):
    result, counts = {}, {}
    for outfit in outfits:
        category = int(outfit.category); ordinal = counts.get(category, 0); counts[category] = ordinal + 1
        result[(category, ordinal)] = outfit
    return result


def merge(backend, target, source, selection):
    appearance.payload(target); appearance.payload(source)
    required = {'fields', 'outfits', 'source_outfit', 'target_outfit', 'body_types'}
    if not isinstance(selection, dict) or set(selection) != required:
        raise ValueError('Paste must select fields, outfit scope and exact source/destination outfits/categories.')
    names = selection['fields']; bodies = selection['body_types']; scope = selection['outfits']
    if (not isinstance(names, list) or any(not isinstance(n, str) for n in names) or len(set(names)) != len(names) or any(n not in appearance.FIELDS for n in names)
            or not isinstance(bodies, list) or len(bodies) > 1024 or any(type(b) is not int or not 0 <= b < 1 << 32 for b in bodies)
            or len(set(bodies)) != len(bodies) or scope not in ('none', 'one', 'all')
            or bodies and scope != 'one' or not names and scope == 'none'):
        raise ValueError('Select supported appearance fields and an explicit outfit/category scope.')
    if any(name not in source or name not in target for name in names):
        raise ValueError('A selected field is unavailable on this source/destination; no missing value was fabricated.')
    after = copy.deepcopy(target)
    for name in names: after[name] = copy.deepcopy(source[name])
    if set(names) & {'genetic_data', 'voice_pitch', 'voice_actor'} and 'genetic_data' in after:
        genetics = appearance.decode(after['genetic_data'])
        protobuf = isinstance(genetics, tuple) and len(genetics) == 2 and genetics[0] == 'protobuf'
        raw = genetics[1] if protobuf else genetics
        if isinstance(raw, bytes):
            from .genetics_snapshot import mirror_voice
            pitch = appearance.decode(after['voice_pitch']) if 'voice_pitch' in after else None
            actor = appearance.decode(after['voice_actor']) if 'voice_actor' in after else None
            mirrored = mirror_voice(raw, pitch, actor)
            after['genetic_data'] = appearance.encode(('protobuf', mirrored) if protobuf else mirrored)
    if scope == 'none': return after
    src, dst = _parse(backend, source), _parse(backend, target)
    if scope == 'one':
        a, b = _index(selection['source_outfit'], src.outfits), _index(selection['target_outfit'], dst.outfits)
        if bodies:
            wanted = set(bodies)
            original = read_rows(b)
            replacements = {body: [r for r in read_rows(a) if r['body_type'] == body] for body in wanted}
            existing = {r['body_type'] for r in original}
            # Keep existing category positions. Missing categories enter their
            # native BodyType order, rather than being appended after eyes or
            # other later categories and then reordered by native load_outfits.
            missing = sorted(body for body in wanted if body not in existing)
            monotonic = [r['body_type'] for r in original] == sorted(r['body_type'] for r in original)
            rows, emitted = [], set()
            for row in original:
                if monotonic:
                    for body in missing:
                        if body < row['body_type'] and body not in emitted:
                            rows.extend(replacements[body]); emitted.add(body)
                body = row['body_type']
                if body in wanted:
                    if body not in emitted: rows.extend(replacements[body]); emitted.add(body)
                else: rows.append(row)
            for body in missing:
                if body not in emitted: rows.extend(replacements[body])
            # Requested empty source categories explicitly remove their target
            # slots; unselected categories and parallel metadata stay intact.
            write_rows(b, rows)
        else:
            identity, category = b.outfit_id, b.category
            b.CopyFrom(a); b.outfit_id, b.category = identity, category
    else:
        targets = _identity_map(dst.outfits); used = {int(r.outfit_id) for r in dst.outfits}
        for key, a in _identity_map(src.outfits).items():
            b = targets.get(key)
            if b is None:
                if len(dst.outfits) >= 1024: raise ValueError('Destination outfit bound reached.')
                allocator = getattr(backend, '_studio_alloc_outfit_id', None)
                if allocator is None:
                    import id_generator
                    allocator = id_generator.generate_object_id
                identity = uint(int(allocator()), 64)
                if not identity or identity in used: raise ValueError('Native outfit allocator returned a reserved/duplicate identity.')
                used.add(identity); b = dst.outfits.add()
            else: identity = b.outfit_id
            b.CopyFrom(a); b.outfit_id, b.category = identity, key[0]
        # Existing destination outfits absent from the source stay available.
        # A paste never silently removes a numbered outfit or its identity.
    after['__outfits__'] = appearance.encode(('protobuf', dst.SerializeToString()))
    appearance.payload(after)
    return after
