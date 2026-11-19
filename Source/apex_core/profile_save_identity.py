"""Local appearance-save identity, independent of disposable test controls."""
import hashlib
import json
import os
from pathlib import Path
import uuid
from .overlay_loader import _unlinked


def player(backend):
    filename = os.path.abspath(str(backend.__file__))
    boundary = filename.casefold().find('.ts4script')
    if boundary < 0 or filename[boundary + 10:boundary + 11] not in ('/', '\\'):
        raise ValueError('Appearance saving requires the installed Apex script archive.')
    archive = _unlinked(filename[:boundary + 10])
    profile = _unlinked(archive.parent.parent.parent)
    data = _unlinked(Path(backend._data_directory()))
    if (archive.name != 'ApexOccultHybrid.ts4script' or archive.parent.name != 'Apex' or
            archive.parent.parent.name != 'Mods' or profile.name != 'The Sims 4' or
            data != profile / 'TD1_OccultHybridApexData'):
        raise ValueError('Appearance saving requires the actual installed profile and its own data directory.')
    if _unlinked(profile / '.apex-disposable-profile.json').exists():
        raise ValueError('A marked test profile must retain its exact disposable identity.')
    before = archive.stat()
    if not 0 < before.st_size <= 16 * 1024 * 1024:
        raise ValueError('Installed script archive exceeds its bound.')
    raw = archive.read_bytes()
    after = archive.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or len(raw) != after.st_size:
        raise ValueError('Installed script changed while identifying appearance saving.')
    path = _unlinked(data / 'profile_save_identity.json')
    if not path.exists():
        data.mkdir(exist_ok=True)
        # An exclusive create never replaces an existing installation identity.
        try:
            with path.open('x', encoding='ascii') as stream:
                json.dump(dict(schema=1, token=uuid.uuid4().hex), stream, sort_keys=True)
                stream.flush(); os.fsync(stream.fileno())
        except FileExistsError:
            pass
    if not 0 < path.stat().st_size <= 1024:
        raise ValueError('Local appearance-save identity exceeds its bound.')
    value = json.loads(path.read_text(encoding='ascii'))
    token = value.get('token') if isinstance(value, dict) else None
    if (not isinstance(value, dict) or set(value) != {'schema', 'token'} or type(value['schema']) is not int or value['schema'] != 1 or
            not isinstance(token, str) or len(token) != 32 or any(c not in '0123456789abcdef' for c in token)):
        raise ValueError('Local appearance-save identity is malformed; existing data was retained.')
    return dict(pid=os.getpid(), profile=str(profile), test_token=token,
                script_sha256=hashlib.sha256(raw).hexdigest(), identity_kind='player-appearance-save')
