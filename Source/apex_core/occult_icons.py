"""Use installed occult trait artwork; never bundle or guess game resource IDs.

Phone rows use native resource keys. F11 receives bounded, hashed image bytes once
per game session; decoding and GPU allocation happen off the Sims thread.
Missing/unsupported images leave the control's text label available.
"""
import base64
import copy
import hashlib
import struct
import threading

NAMES = ('ALIEN', 'VAMPIRE', 'MERMAID', 'WITCH', 'WEREWOLF', 'FAIRY')
_CACHE = None
_LOCK = threading.Lock()


def key(backend, name):
    name = 'WITCH' if name == 'SPELLCASTER' else name
    if name not in NAMES:
        return None
    kind = backend._occult_by_name(name)
    if kind is None:
        return None
    tuning = backend._get_tuning(kind)
    return getattr(getattr(tuning, 'occult_trait', None), 'icon', None)


def choice_name(tag):
    """Resolve typed phone identities, never infer an occult from label text."""
    parts = tag.split(':')
    if len(parts) == 3 and parts[0] == 'occult' and parts[1] in ('add', 'switch'):
        return parts[2]
    if len(parts) >= 3 and parts[:2] == ['page', 'cas_form']:
        lane = parts[2]
    elif len(parts) >= 4 and parts[0] == 'cas' and parts[1] in ('decision', 'hair', 'hair-none', 'hair-page'):
        lane = parts[3]
    elif tag.startswith('action:werewolf_human_'):
        return 'WEREWOLF'
    elif tag.startswith('action:qol_sunlight_'):
        return 'VAMPIRE'
    else:
        return None
    # Native review lane identities are numeric flags, not UI labels.
    if lane.isascii() and lane.isdecimal():
        return {2: 'ALIEN', 4: 'VAMPIRE', 8: 'MERMAID',
                16: 'WITCH', 32: 'WEREWOLF', 64: 'FAIRY'}.get(int(lane))
    return lane if lane in NAMES else None


def png(raw):
    if (not isinstance(raw, bytes) or not 33 <= len(raw) <= 128 * 1024 or
            raw[:8] != b'\x89PNG\r\n\x1a\n' or raw[8:16] != b'\x00\x00\x00\rIHDR'):
        raise ValueError('The installed trait icon is not a bounded PNG.')
    width, height = struct.unpack('>II', raw[16:24])
    if not 0 < width <= 512 or not 0 < height <= 512:
        raise ValueError('The installed trait icon dimensions are unsupported.')
    return dict(width=width, height=height, sha256=hashlib.sha256(raw).hexdigest())


def image_metadata(raw):
    if raw.startswith(b'\x89PNG\r\n\x1a\n'):
        return dict(png(raw), format='png')
    # The six inspected installed icons are DST5 (shuffled BC3), one mip.
    # Reject other DDS layouts instead of giving the worker guessed offsets.
    if (len(raw) < 128 or len(raw) > 128 * 1024 or raw[:8] != b'DDS |\0\0\0' or
            raw[84:88] not in (b'DST5', b'DXT5') or struct.unpack_from('<I', raw, 76)[0] != 32 or
            struct.unpack_from('<I', raw, 28)[0] not in (0, 1)):
        raise ValueError('The installed icon is neither a bounded PNG nor verified DST5.')
    height, width = struct.unpack_from('<II', raw, 12)
    if (not 0 < width <= 512 or not 0 < height <= 512 or width % 4 or height % 4 or
            len(raw) != 128 + width * height):
        raise ValueError('The installed DST5 icon dimensions/payload are unsupported.')
    return dict(width=width, height=height, format=raw[84:88].decode('ascii').lower(), sha256=hashlib.sha256(raw).hexdigest())


def _installed_worker(root, pending, rows):
    # Only immutable keys/rows cross this boundary. No game API is called here.
    from . import installed_icon_resources
    try:
        found = installed_icon_resources.read(root, [identity for _, identity in pending])
        for index, identity in pending:
            row = rows[index]
            record = found.get(identity)
            if record is None:
                row['reason'] = 'The exact installed client texture is absent.'
            elif record.get('conflict'):
                row['reason'] = 'Conflicting installed client textures; no image was guessed.'
            else:
                raw = record['raw']
                try:
                    row.update(image_metadata(raw), image_base64=base64.b64encode(raw).decode('ascii'),
                               status='resolved', sources=record['sources'])
                    row.pop('reason', None)
                except ValueError as error:
                    row['reason'] = str(error)
            if row['status'] != 'resolved':
                row['status'] = 'unavailable'
    except (ValueError, TypeError, AttributeError, OSError, ImportError) as error:
        for index, _ in pending:
            rows[index].update(status='unavailable', reason=str(error))
    global _CACHE
    with _LOCK:
        _CACHE = dict(schema=1, origin='installed-occult-trait-tuning', loading=False, items=rows)


def catalog(backend):
    global _CACHE
    if _CACHE is None:
        from sims4 import resources
        rows, pending = [], []
        for name in NAMES:
            row = dict(name=name, status='unavailable')
            raw = b''
            try:
                identity = key(backend, name)
                if identity is None:
                    raise ValueError('This installed occult has no trait icon.')
                values = tuple(getattr(identity, field) for field in ('type', 'group', 'instance'))
                if (any(type(value) is not int for value in values) or
                        not 0 < values[0] <= 0xffffffff or not 0 <= values[1] <= 0xffffffff or
                        not 0 < values[2] <= 0xffffffffffffffff):
                    raise ValueError('The native trait icon resource key is invalid.')
                row['reference_tgi'] = '{:08X}:{:08X}:{:016X}'.format(*values)
                loaded = resources.ResourceLoader(identity).load_raw(silent_fail=True)
                if loaded is None and values[0] == 0x2f7d0004:
                    # EA's UI PNG references alias the same installed DST image
                    # instance/group. All six aliases were verified against the
                    # installed DBPF resources; do not search by a nearby ID.
                    identity = resources.Key(0x00b2d882, values[2], values[1])
                    loaded = resources.ResourceLoader(identity).load_raw(silent_fail=True)
                    values = (0x00b2d882, values[1], values[2])
                row['resource_tgi'] = '{:08X}:{:08X}:{:016X}'.format(*values)
                raw = bytes(loaded) if loaded is not None else b''
                if loaded is None:
                    row.update(status='loading', reason='Reading the exact installed client texture in the artwork worker.')
                    pending.append((len(rows), values))
                    rows.append(row)
                    continue
                row.update(image_metadata(raw), image_base64=base64.b64encode(raw).decode('ascii'), status='resolved')
            except (ValueError, TypeError, AttributeError, OSError) as error:
                row['reason'] = str(error)
                row['raw_bytes'] = len(raw)
                row['raw_prefix'] = raw[:16].hex()
                row['raw_fourcc'] = raw[84:88].hex() if len(raw) >= 88 else None
            rows.append(row)
        _CACHE = dict(schema=1, origin='installed-occult-trait-tuning', loading=bool(pending), items=rows)
        if pending:
            try:
                import paths
                from .installed_icon_resources import game_root
                root = game_root(paths.DLL_PATH)
                worker = threading.Thread(target=_installed_worker, args=(root, tuple(pending), [dict(row) for row in rows]),
                                          name='ApexInstalledArtwork', daemon=True)
                worker.start()
            except (ValueError, TypeError, AttributeError, OSError, ImportError, RuntimeError) as error:
                for index, _ in pending:
                    rows[index].update(status='unavailable', reason=str(error))
                _CACHE = dict(_CACHE, loading=False)
    # The caller must not be able to corrupt the shared session cache.
    with _LOCK:
        return copy.deepcopy(_CACHE)
