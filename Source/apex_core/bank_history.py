"""Immutable, content-addressed raw history; no edit/count/total-size cutoff.

Only inactive history rows are externalized. Current originals, return journals
and native write-ahead records stay in the revision-checked active document.
An archive grants no native replay authority and is verified when opened.
"""
import hashlib
import json
import os
from pathlib import Path
from .overlay_loader import _unlinked

FORMAT = 'apex-bank-history-v1'
HISTORIES = ('history', 'cas_transaction_history', 'switch_history', 'failed_history',
             'bank_rebase_history', 'native_selection_history')


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


def resolve(bank, row):
    if not reference(row):
        return row
    path = _path(bank, row['sha256'])
    if not path.is_file() or path.stat().st_size != row['bytes']:
        raise ValueError('Raw history archive is missing or changed; no restore authorized.')
    raw = path.read_bytes()
    if len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
        raise ValueError('Raw history archive hash differs; no restore authorized.')
    value = json.loads(raw.decode('ascii'), object_pairs_hook=_pairs)
    if not isinstance(value, dict) or reference(value):
        raise ValueError('History archive must contain a complete original row.')
    return value


def store(bank, row):
    if reference(row):
        path = _path(bank, row['sha256'])
        if not path.is_file() or path.stat().st_size != row['bytes']:
            raise ValueError('Retained history reference is unavailable.')
        return row
    if not isinstance(row, dict):
        raise ValueError('History row must retain its complete typed mapping.')
    raw = json.dumps(row, sort_keys=True, ensure_ascii=True,
                     allow_nan=False, separators=(',', ':')).encode('ascii')
    digest = hashlib.sha256(raw).hexdigest()
    path = _path(bank, digest)
    path.parent.mkdir(parents=True, exist_ok=True)
    held = {'storage': FORMAT, 'sha256': digest, 'bytes': len(raw)}
    if path.exists():
        if resolve(bank, held) != row:
            raise ValueError('Existing archive does not match its complete source row.')
        return held
    try:
        with path.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        if resolve(bank, held) != row:
            raise ValueError('Concurrent immutable archive differs.')
    if resolve(bank, held) != row:
        raise ValueError('Archive complete readback differs; active originals retained.')
    return held


def externalize(bank, record):
    """Call on an owned clone at an idle boundary, before new guard hashes.

    Archives are durable before references enter the bank. A later bank CAS
    failure leaves complete extra archives, never an index to unwritten bytes.
    """
    for name in HISTORIES:
        rows = record.get(name)
        if rows is None:
            continue
        if not isinstance(rows, list):
            raise ValueError('Raw history index must be a typed list.')
        # The latest legacy completion is still read directly by older seal
        # validators. Keep that one row inline; every earlier row is durable.
        held = rows[:-1] if name == 'history' else rows
        record[name] = [store(bank, row) for row in held] + (rows[-1:] if name == 'history' else [])
    return record
