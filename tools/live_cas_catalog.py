"""Host-side searchable CASP index, independent of CAS rooms and Sim wardrobes.

No game commands or writes to source packages. A catalog row is a container
candidate, never proof of effective game load order or Sim compatibility.
"""
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time

from cas_resource_catalog import (CASP, STBL, CACHE_ROOT, Package, canonical,
                                  casp_metadata, digest, file_hash, key,
                                  no_redirected_ancestors, sha, signature,
                                  stbl_strings, tgi)

INDEX_ROOT = CACHE_ROOT.parent / 'live-cas-catalog'
SCHEMA = 1
MAX_SOURCES = 100000
MAX_PARTS = 2000000


def index_path(value):
    path = Path(value).absolute()
    root = INDEX_ROOT.resolve()
    no_redirected_ancestors(path)
    path = path.resolve()
    if path == root or root not in path.parents or path.suffix != '.sqlite':
        raise ValueError('Use an external .work/live-cas-catalog/*.sqlite index.')
    return path


def _connect(index, expected):
    path = index_path(index)
    before = signature(path)
    if file_hash(path) != sha(expected) or signature(path) != before:
        raise ValueError('Catalog index changed; use its exact snapshot SHA256.')
    connection = sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        if connection.execute('PRAGMA user_version').fetchone()[0] != SCHEMA:
            raise ValueError('Unsupported Live CAS catalog schema.')
        connection.execute('PRAGMA query_only=ON')
        return connection
    except Exception:
        connection.close()
        raise


def _package_rows(package, locale):
    wanted = [item for item in package.entries if item[0] == CASP or
              (item[0] == STBL and item[2] >> 56 == locale)]
    resources = package.read_many(wanted)
    strings, string_errors = {}, []
    for item, raw in resources.items():
        if item[0] == STBL:
            try:
                for ident, name in stbl_strings(raw).items():
                    if name.strip():
                        strings.setdefault(ident, set()).add(name)
            except (ValueError, UnicodeError) as error:
                string_errors.append(str(error))
    for item in sorted(resources):
        if item[0] != CASP:
            continue
        raw = resources[item]
        identity = digest(canonical([str(package.path), package.source_sha256, tgi(item), digest(raw)]))
        row = {'part_id': identity, 'resource_tgi': tgi(item), 'resource_sha256': digest(raw),
               'package_path': str(package.path), 'package_name': package.path.name,
               'package_sha256': package.source_sha256, 'origin': package.origin,
               'preferred_name': package.path.name, 'name_status': 'package-filename',
               'code_name': None, 'body_type': None, 'metadata': None,
               'status': 'unclassified', 'reason': None,
               'effective_load_source_verified': False, 'equip_verified': False}
        try:
            meta = casp_metadata(raw)
            row.update(metadata=meta, body_type=meta['body_type'], code_name=meta['internal_name'], status='indexed')
            titles = strings.get(meta['title_key'], set())
            if len(titles) == 1 and not string_errors:
                row.update(preferred_name=next(iter(titles)), name_status='package-localized-title')
            elif package.origin == 'ea' and row['code_name']:
                row.update(preferred_name=row['code_name'], name_status='casp-internal-name')
        except (ValueError, UnicodeError) as error:
            row['reason'] = str(error)
        yield row


def build(sources, index, locale=0):
    target = index_path(index)
    if target.exists():
        raise ValueError('Use a new index filename; prior snapshots are preserved.')
    if (not isinstance(sources, list) or not 0 < len(sources) <= MAX_SOURCES or
            type(locale) is not int or not 0 <= locale <= 255):
        raise ValueError('Use explicit bounded source packages and a numeric locale.')
    paths = []
    for source in sources:
        if not isinstance(source, dict) or set(source) != {'path', 'origin'} or source['origin'] not in ('mod', 'ea'):
            raise ValueError('Every source needs exactly path and mod/ea origin.')
        path = Path(source['path']).resolve(strict=True)
        if not path.is_file() or path.suffix.lower() != '.package':
            raise ValueError('Source must be an existing package file.')
        paths.append(path)
    if len(set(paths)) != len(paths):
        raise ValueError('Duplicate source path.')
    target.parent.mkdir(parents=True, exist_ok=True)
    no_redirected_ancestors(target)
    handle, temporary_name = tempfile.mkstemp(prefix='building-', suffix='.sqlite', dir=target.parent)
    os.close(handle)
    temporary = Path(temporary_name)
    connection = sqlite3.connect(temporary)
    started, count, errors, signatures = time.perf_counter(), 0, [], []
    try:
        connection.executescript('''
            PRAGMA user_version=1;
            CREATE TABLE parts(part_id TEXT PRIMARY KEY, body_type INTEGER,
                origin TEXT, status TEXT, row_json TEXT NOT NULL);
            CREATE INDEX parts_filter ON parts(body_type, origin, status, part_id);
            CREATE VIRTUAL TABLE names USING fts5(preferred_name, package_name, code_name);
            CREATE TABLE snapshot(value TEXT NOT NULL);
        ''')
        for source, path in zip(sources, paths):
            try:
                package = Package(path, source['origin'])
                signatures.append((path, package.before))
                for row in _package_rows(package, locale):
                    count += 1
                    if count > MAX_PARTS:
                        raise ValueError('Catalog part bound exceeded; no incomplete index published.')
                    cursor = connection.execute('INSERT INTO parts VALUES(?,?,?,?,?)',
                        (row['part_id'], row['body_type'], row['origin'], row['status'], canonical(row).decode('utf-8')))
                    connection.execute('INSERT INTO names(rowid,preferred_name,package_name,code_name) VALUES(?,?,?,?)',
                        (cursor.lastrowid, row['preferred_name'], row['package_name'], row['code_name'] or ''))
            except (OSError, ValueError, UnicodeError) as error:
                if count > MAX_PARTS:
                    raise
                errors.append({'package_name': path.name, 'reason': str(error)})
        if any(signature(path) != before for path, before in signatures):
            raise ValueError('A source changed during indexing; snapshot not published.')
        snapshot = {'schema': SCHEMA, 'packages': len(sources), 'parts': count,
                    'locale': locale, 'source_errors': errors, 'complete': not errors,
                    'effective_load_source_verified': False, 'equip_verified': False}
        connection.execute('INSERT INTO snapshot VALUES(?)', (canonical(snapshot).decode('utf-8'),))
        connection.commit()
        connection.close()
        # A concurrent build must never replace a prior completed snapshot.
        os.link(temporary, target)
        return dict(snapshot, ok=not errors, index=str(target), index_sha256=file_hash(target),
                    elapsed_seconds=round(time.perf_counter() - started, 3), game_contacted=False)
    finally:
        connection.close()
        temporary.unlink(missing_ok=True)


def query(index, expected, text='', body_type=None, origin=None, name_mode='preferred', offset=0, limit=60):
    if (not isinstance(text, str) or len(text) > 200 or name_mode not in ('preferred', 'package', 'code') or
            origin not in (None, 'mod', 'ea') or type(offset) is not int or not 0 <= offset <= MAX_PARTS or
            type(limit) is not int or not 1 <= limit <= 240 or
            (body_type is not None and (type(body_type) is not int or not 0 <= body_type <= 0xffffffff))):
        raise ValueError('Invalid catalog filter/page.')
    tokens = re.findall(r'\w+', text, flags=re.UNICODE)
    if len(tokens) > 16 or (text.strip() and not tokens):
        raise ValueError('Search needs one to sixteen name terms.')
    clauses, parameters = [], []
    if tokens:
        clauses.append('rowid IN (SELECT rowid FROM names WHERE names MATCH ?)')
        parameters.append(' AND '.join('"' + token + '"*' for token in tokens))
    for column, value in (('body_type', body_type), ('origin', origin)):
        if value is not None:
            clauses.append(column + '=?')
            parameters.append(value)
    where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
    started = time.perf_counter()
    connection = _connect(index, expected)
    try:
        snapshot = json.loads(connection.execute('SELECT value FROM snapshot').fetchone()[0])
        total = connection.execute('SELECT count(*) FROM parts' + where, parameters).fetchone()[0]
        rows = [json.loads(row[0]) for row in connection.execute(
            'SELECT row_json FROM parts' + where + ' ORDER BY part_id LIMIT ? OFFSET ?', parameters + [limit, offset])]
        for row in rows:
            row['name'] = row[{'preferred': 'preferred_name', 'package': 'package_name', 'code': 'code_name'}[name_mode]]
        return {'ok': True, 'index_sha256': expected, 'snapshot': snapshot, 'total': total,
                'offset': offset, 'next_offset': offset + len(rows) if offset + len(rows) < total else None,
                'items': rows, 'elapsed_seconds': round(time.perf_counter() - started, 6),
                'game_contacted': False}
    finally:
        connection.close()


def resolve(index, expected, part_id):
    sha(part_id)
    connection = _connect(index, expected)
    try:
        found = connection.execute('SELECT row_json FROM parts WHERE part_id=?', (part_id,)).fetchone()
        if found is None:
            raise ValueError('Part identity is absent from this exact snapshot.')
        row = json.loads(found[0])
    finally:
        connection.close()
    if row['status'] != 'indexed':
        raise ValueError('Unclassified CASP cannot be selected.')
    package = Package(row['package_path'], row['origin'])
    if package.source_sha256 != row['package_sha256']:
        raise ValueError('Package changed since indexing; rebuild before selecting.')
    raw = package.read(key(row['resource_tgi']))
    if digest(raw) != row['resource_sha256']:
        raise ValueError('CASP changed since indexing.')
    return {'ok': True, 'item': row, 'source': {'path': str(package.path), 'origin': package.origin},
            'request': {'resource_tgi': row['resource_tgi'], 'effective_resource_sha256': digest(raw),
                        'body_type': row['body_type']}, 'game_contacted': False,
            'effective_load_source_verified': False, 'equip_verified': False}
