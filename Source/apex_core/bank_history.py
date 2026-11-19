"""Immutable, content-addressed raw history; no edit/count/total-size cutoff.

Only inactive history rows are externalized. Current originals, return journals
and native write-ahead records stay in the revision-checked active document.
An archive grants no native replay authority and is verified when opened.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
from .overlay_loader import _unlinked

FORMAT = 'apex-bank-history-v1'
HISTORIES = ('history', 'cas_transaction_history', 'switch_history', 'failed_history',
             'bank_rebase_history', 'native_selection_history',
             'human_werewolf_look_history', 'named_draft_history',
             'lifestate_revalidation_history')
# Completed native CAS exports are retained evidence. Current named looks and
# active transaction/WAL fields remain inline and keep their existing checks.
ARCHIVES = ('native_cas_owner_archive',)


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('Duplicate history key; original archive retained.')
        result[key] = value
    return result


def reference(row):
    if not isinstance(row, dict) or row.get('storage') != FORMAT:
        return False
    if (set(row) != {'storage', 'sha256', 'bytes'} or
            not isinstance(row['sha256'], str) or len(row['sha256']) != 64 or
            any(x not in '0123456789abcdef' for x in row['sha256']) or
            type(row['bytes']) is not int or row['bytes'] <= 0):
        raise ValueError('Malformed immutable history reference.')
    return True


def _path(bank, digest):
    bank = _unlinked(Path(bank))
    return _unlinked(bank.parent / 'form-bank-history' / (digest + '.json'))


class _ArchiveDirectory:
    """Validate the shared directory once per bounded archival operation.

    Hundreds of already archived rows share the same parents. Rewalking every
    parent for each SHA filename stalls the game thread. Retain the exact
    directory identity and check it and each leaf before every access instead.
    The filename is always a validated SHA, never caller-supplied path text.
    """
    def __init__(self, bank):
        self.root = _unlinked(_unlinked(Path(bank)).parent / 'form-bank-history')
        self.root.mkdir(parents=True, exist_ok=True)
        self.root = _unlinked(self.root)
        self.identity = self._identity(self.root.lstat())

    @staticmethod
    def _identity(info):
        if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or
                getattr(info, 'st_file_attributes', 0) & 0x400):
            raise ValueError('History directory is not an exact regular directory.')
        return info.st_dev, info.st_ino

    def leaf(self, digest):
        if (not isinstance(digest, str) or len(digest) != 64 or
                any(c not in '0123456789abcdef' for c in digest) or
                self._identity(self.root.lstat()) != self.identity):
            raise ValueError('History directory identity or SHA filename changed.')
        path = self.root / (digest + '.json')
        try:
            info = path.lstat()
        except FileNotFoundError:
            return path, None
        if (not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or
                getattr(info, 'st_file_attributes', 0) & 0x400):
            raise ValueError('History leaf is not an exact regular file.')
        return path, info


def resolve(bank, row, _directory=None):
    if not reference(row):
        return row
    path, info = (_directory.leaf(row['sha256']) if _directory is not None else
                  (_path(bank, row['sha256']), None))
    if _directory is None:
        info = path.stat() if path.is_file() else None
    if info is None or info.st_size != row['bytes']:
        raise ValueError('Raw history archive is missing or changed; no restore authorized.')
    raw = path.read_bytes()
    if len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
        raise ValueError('Raw history archive hash differs; no restore authorized.')
    value = json.loads(raw.decode('ascii'), object_pairs_hook=_pairs)
    if not isinstance(value, dict) or reference(value):
        raise ValueError('History archive must contain a complete original row.')
    return value


def store(bank, row, _directory=None):
    if reference(row):
        path, info = (_directory.leaf(row['sha256']) if _directory is not None else
                      (_path(bank, row['sha256']), None))
        if _directory is None:
            info = path.stat() if path.is_file() else None
        if info is None or info.st_size != row['bytes']:
            raise ValueError('Retained history reference is unavailable.')
        return row
    if not isinstance(row, dict):
        raise ValueError('History row must retain its complete typed mapping.')
    raw = json.dumps(row, sort_keys=True, ensure_ascii=True,
                     allow_nan=False, separators=(',', ':')).encode('ascii')
    digest = hashlib.sha256(raw).hexdigest()
    path = _directory.leaf(digest)[0] if _directory is not None else _path(bank, digest)
    path.parent.mkdir(parents=True, exist_ok=True)
    held = {'storage': FORMAT, 'sha256': digest, 'bytes': len(raw)}
    if path.exists():
        if resolve(bank, held, _directory) != row:
            raise ValueError('Existing archive does not match its complete source row.')
        return held
    try:
        with path.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        if resolve(bank, held, _directory) != row:
            raise ValueError('Concurrent immutable archive differs.')
    if resolve(bank, held, _directory) != row:
        raise ValueError('Archive complete readback differs; active originals retained.')
    return held


def externalize(bank, record):
    """Call on an owned clone at an idle boundary, before new guard hashes.

    Archives are durable before references enter the bank. A later bank CAS
    failure leaves complete extra archives, never an index to unwritten bytes.
    """
    directory = None
    def archive(row):
        nonlocal directory
        if directory is None:
            directory = _ArchiveDirectory(bank)
        return store(bank, row, directory)
    for name in HISTORIES:
        rows = record.get(name)
        if rows is None:
            continue
        if not isinstance(rows, list):
            raise ValueError('Raw history index must be a typed list.')
        # The latest legacy completion is still read directly by older seal
        # validators. Keep that one row inline; every earlier row is durable.
        held = rows[:-1] if name == 'history' else rows
        record[name] = [archive(row) for row in held] + (rows[-1:] if name == 'history' else [])
    for name in ARCHIVES:
        if name in record:
            record[name] = archive(record[name])
    return record
