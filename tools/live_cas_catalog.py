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
import threading
from collections import OrderedDict
from copy import deepcopy
from cas_search import Vocabulary, aliases, terms as search_terms

from cas_resource_catalog import (CASP, STBL, CAS_THUMB, CACHE_ROOT, Package, canonical,
                                  casp_metadata, digest, file_hash, key,
                                  no_redirected_ancestors, sha, signature,
                                  stbl_strings, tgi)

INDEX_ROOT = CACHE_ROOT.parent / 'live-cas-catalog'
SCHEMA = 5
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
        if connection.execute('PRAGMA user_version').fetchone()[0] not in (1, 2, 3, 4, SCHEMA):
            raise ValueError('Unsupported Live CAS catalog schema.')
        connection.execute('PRAGMA query_only=ON')
        connection.create_function('creator_hint', 3, creator_hint, deterministic=True)
        return connection
    except Exception:
        connection.close()
        raise


def creator_hint(package_name, code_name, origin):
    """Filename tags are useful filters, not proof of authorship."""
    if origin == 'ea':
        return 'EA'
    match = re.match(r'^\s*\[([^\]\r\n]{1,80})\]', package_name or '')
    if match:
        return match.group(1).strip()
    # Only an explicit filename prefix is inferred. Never attribute a whole
    # untagged item title or a game's age/gender code to a creator.
    match = re.match(r'^([\w .-]{2,80})_', package_name or '')
    return match.group(1).strip() if match else ''


def family_identity(row):
    """Native OutfitID joins swatches, bounded by fitting and source namespace.

    A missing/zero OutfitID never joins unrelated resources. Exact repeated
    container copies share a variant identity; conflicting bytes remain distinct.
    Unknown CC creators stay within their package, avoiding OutfitID collisions.
    """
    meta = row.get('metadata') or {}
    variant = digest(canonical([row['origin'], row['resource_tgi'], row['resource_sha256']]))
    namespace = ('ea' if row['origin'] == 'ea' else
                 ['mod', (row.get('creator_hint') or row['package_name']).casefold()])
    native = meta.get('outfit_id', 0)
    group = ([namespace, native, meta['body_type'], meta['age_gender'], meta['species']]
             if native else ['ungrouped', variant])
    return digest(canonical(group)), variant, meta.get('swatch_order', 0)


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
        row['creator_hint'] = creator_hint(row['package_name'], row['code_name'], row['origin'])
        row['creator_source'] = 'EA resource' if row['origin'] == 'ea' else 'filename tag / unverified'
        row['creator_verified'] = row['origin'] == 'ea'
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
        if not isinstance(source['path'], str) or not source['path']:
            raise ValueError('Source path must be a nonempty string.')
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
            PRAGMA user_version=5;
            CREATE TABLE parts(part_id TEXT PRIMARY KEY, body_type INTEGER,
                origin TEXT, status TEXT, row_json TEXT NOT NULL,
                family_id TEXT NOT NULL, variant_key TEXT NOT NULL, swatch_order INTEGER NOT NULL);
            CREATE INDEX parts_filter ON parts(body_type, origin, status, part_id);
            CREATE INDEX parts_family ON parts(family_id,swatch_order,variant_key,part_id);
            CREATE VIRTUAL TABLE names USING fts5(preferred_name, package_name, code_name, search_aliases);
            CREATE TABLE snapshot(value TEXT NOT NULL);
            CREATE TABLE thumbnails(resource_tgi TEXT,package_path TEXT,package_sha256 TEXT,
                                    PRIMARY KEY(resource_tgi,package_path));
        ''')
        for source, path in zip(sources, paths):
            try:
                package = Package(path, source['origin'])
                signatures.append((path, package.before))
                connection.executemany('INSERT INTO thumbnails VALUES(?,?,?)',
                    ((tgi(item),str(path),package.source_sha256) for item in package.entries if item[0]==CAS_THUMB))
                for row in _package_rows(package, locale):
                    count += 1
                    if count > MAX_PARTS:
                        raise ValueError('Catalog part bound exceeded; no incomplete index published.')
                    family, variant, order = family_identity(row)
                    row.update(family_id=family, variant_key=variant)
                    cursor = connection.execute('INSERT INTO parts VALUES(?,?,?,?,?,?,?,?)',
                        (row['part_id'], row['body_type'], row['origin'], row['status'], canonical(row).decode('utf-8'), family, variant, order))
                    connection.execute('INSERT INTO names(rowid,preferred_name,package_name,code_name,search_aliases) VALUES(?,?,?,?,?)',
                        (cursor.lastrowid, row['preferred_name'], row['package_name'], row['code_name'] or '',
                         aliases(row['preferred_name'], row['package_name'], row['code_name'], row['creator_hint'])))
            except (OSError, ValueError, UnicodeError) as error:
                if count > MAX_PARTS:
                    raise
                errors.append({'package_name': path.name, 'reason': str(error)})
        if any(signature(path) != before for path, before in signatures):
            raise ValueError('A source changed during indexing; snapshot not published.')
        families, variants = connection.execute('SELECT count(DISTINCT family_id),count(DISTINCT variant_key) FROM parts').fetchone()
        snapshot = {'schema': SCHEMA, 'packages': len(sources), 'parts': count,
                    'families': families, 'variants': variants,
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


def _query(connection, expected, text='', body_type=None, origin=None, name_mode='preferred', offset=0, limit=60,
           part_ids=None, author='', sort='name', grouped=False, search_expression=None):
    if (not isinstance(text, str) or len(text) > 200 or name_mode not in ('preferred', 'package', 'code') or
            origin not in (None, 'mod', 'ea') or type(offset) is not int or not 0 <= offset <= MAX_PARTS or
            type(limit) is not int or not 1 <= limit <= 240 or
            (body_type is not None and (type(body_type) is not int or not 0 <= body_type <= 0xffffffff)) or
            not isinstance(author, str) or len(author) > 80 or sort not in ('name', 'package', 'creator', 'id') or type(grouped) is not bool):
        raise ValueError('Invalid catalog filter/page.')
    tokens = search_terms(text)
    if len(tokens) > 16 or (text.strip() and not tokens):
        raise ValueError('Search needs one to sixteen name terms.')
    clauses, parameters = [], []
    if tokens:
        clauses.append('rowid IN (SELECT rowid FROM names WHERE names MATCH ?)')
        parameters.append(search_expression if search_expression is not None else
                          ' AND '.join('"' + token + '"*' for token in tokens))
    for column, value in (('body_type', body_type), ('origin', origin)):
        if value is not None:
            clauses.append(column + '=?')
            parameters.append(value)
    creator = "coalesce(json_extract(row_json,'$.creator_hint'),creator_hint(json_extract(row_json,'$.package_name'),json_extract(row_json,'$.code_name'),origin))"
    if author:
        clauses.append(creator + '=? COLLATE NOCASE')
        parameters.append(author)
    if part_ids is not None:
        if not isinstance(part_ids, list) or len(part_ids) > 10000:
            raise ValueError('Invalid saved item list.')
        for ident in part_ids:
            sha(ident)
        clauses.append('part_id IN (SELECT value FROM json_each(?))')
        parameters.append(json.dumps(part_ids))
    where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
    started = time.perf_counter()
    snapshot = json.loads(connection.execute('SELECT value FROM snapshot').fetchone()[0])
    if grouped and snapshot['schema'] < 3:
        raise ValueError('Swatch grouping needs a new schema 3 catalog snapshot.')
    total = connection.execute('SELECT count(' + ('DISTINCT family_id' if grouped else '*') + ') FROM parts' + where, parameters).fetchone()[0]
    name_column = {'preferred': 'preferred_name', 'package': 'package_name', 'code': 'code_name'}[name_mode]
    ordering = {'id': 'part_id', 'name': "json_extract(row_json,'$." + name_column + "') COLLATE NOCASE,part_id",
                'package': "json_extract(row_json,'$.package_name') COLLATE NOCASE,part_id",
                'creator': creator + " COLLATE NOCASE,json_extract(row_json,'$.preferred_name') COLLATE NOCASE,part_id"}[sort]
    if grouped:
        # Filters choose a representative from matching candidates. Original
        # resources remain selectable, with all family swatches in inspection.
        sql = 'SELECT row_json FROM parts WHERE part_id IN (SELECT min(part_id) FROM parts' + where + ' GROUP BY family_id)'
    else:
        sql = 'SELECT row_json FROM parts' + where
    rows = [json.loads(row[0]) for row in connection.execute(sql + ' ORDER BY ' + ordering + ' LIMIT ? OFFSET ?', parameters + [limit, offset])]
    for row in rows:
        row['name'] = row[{'preferred': 'preferred_name', 'package': 'package_name', 'code': 'code_name'}[name_mode]]
        row.setdefault('creator_hint', creator_hint(row['package_name'], row['code_name'], row['origin']))
        row.setdefault('creator_source', 'EA resource' if row['origin'] == 'ea' else 'filename tag / unverified')
        row.setdefault('creator_verified', row['origin'] == 'ea')
        if grouped:
            row['swatch_count'], row['container_count'] = connection.execute(
                'SELECT count(DISTINCT variant_key),count(*) FROM parts WHERE family_id=?', (row['family_id'],)).fetchone()
    return {'ok': True, 'index_sha256': expected, 'snapshot': snapshot, 'total': total,
            'offset': offset, 'next_offset': offset + len(rows) if offset + len(rows) < total else None,
            'items': rows, 'elapsed_seconds': round(time.perf_counter() - started, 6),
            'game_contacted': False, 'grouped': grouped}


def query(index, expected, text='', body_type=None, origin=None, name_mode='preferred', offset=0, limit=60,
          author='', sort='name', grouped=False):
    connection = _connect(index, expected)
    try:
        return _query(connection, expected, text, body_type, origin, name_mode, offset, limit, author=author, sort=sort, grouped=grouped)
    finally:
        connection.close()


class PinnedIndex:
    """One startup hash scan; immutable SQLite pages never touch the game.

    The open read-only connection is serialized across HTTP workers. A changed
    path identity refuses every later page. Selection rehashes source packages.
    """
    def __init__(self, index, expected):
        self.path, self.expected = index_path(index), sha(expected)
        self.handle = None
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            create = self.kernel.CreateFileW
            create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                               wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
            create.restype = wintypes.HANDLE
            # Allow other readers, deny writes and replacement for the lifetime
            # of this browser. SQLite still opens a read-only handle normally.
            self.handle = create(str(self.path), 0x80000000, 1, None, 3, 0x80, None)
            if self.handle == ctypes.c_void_p(-1).value:
                self.handle = None
                raise OSError(ctypes.get_last_error(), 'Cannot retain a read-only catalog lease.')
        self.before = signature(self.path)
        try:
            connection = _connect(self.path, self.expected)
            connection.close()
            if signature(self.path) != self.before:
                raise ValueError('Index changed while opening browser.')
            self.connection = sqlite3.connect(self.path.as_uri() + '?mode=ro&immutable=1', uri=True,
                                             check_same_thread=False)
            # This is a TEMP virtual view of the existing FTS index. No source
            # package or immutable database is modified or reparsed. Build it
            # once on broker startup, never in a CAS click/render handler.
            self.connection.execute("CREATE VIRTUAL TABLE temp.apex_name_vocab USING fts5vocab(main,names,'row')")
            self.vocabulary = Vocabulary(row[0] for row in self.connection.execute('SELECT term FROM apex_name_vocab'))
            self.connection.execute('PRAGMA query_only=ON')
            self.connection.create_function('creator_hint', 3, creator_hint, deterministic=True)
            self.lock = threading.RLock()
            self.pages, self.page_bytes = OrderedDict(), 0
            grouped=self.connection.execute('PRAGMA user_version').fetchone()[0]>=3
            self.facets = [{'body_type': body, 'count': count} for body, count in self.connection.execute(
                'SELECT body_type,count('+('DISTINCT family_id' if grouped else '*')+') FROM parts GROUP BY body_type ORDER BY body_type')]
            self.creators = [{'name': name, 'count': count} for name, count in self.connection.execute(
                "SELECT coalesce(json_extract(row_json,'$.creator_hint'),creator_hint(json_extract(row_json,'$.package_name'),json_extract(row_json,'$.code_name'),origin)) AS creator,count(*) FROM parts GROUP BY creator ORDER BY creator COLLATE NOCASE LIMIT 1025") if name]
            self.creators_truncated = len(self.creators) > 1024
            self.creators = self.creators[:1024]
        except Exception:
            self._release()
            raise

    def _release(self):
        if self.handle is not None:
            import ctypes
            self.kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
            self.kernel.CloseHandle(self.handle)
            self.handle = None

    def __del__(self):
        if getattr(self, 'handle', None) is not None:
            self._release()

    def query(self, fuzzy=False, **filters):
        if type(fuzzy) is not bool:
            raise ValueError('Fuzzy search must be a boolean.')
        started = time.perf_counter()
        with self.lock:
            if (signature(self.path) != self.before or
                    os.name != 'nt' and file_hash(self.path) != self.expected):
                raise ValueError('Index path changed; restart with a verified snapshot.')
            # Cache keys include every filter, saved-item list and page. A
            # favorite change or different author cannot reuse an old result.
            cache_key = canonical(dict(filters, fuzzy=fuzzy))
            hit = cache_key in self.pages
            if hit:
                self.pages.move_to_end(cache_key)
                result = deepcopy(self.pages[cache_key][0])
            else:
                result = _query(self.connection, self.expected, **filters)
                result.update(search_mode='prefix', corrections=[])
                # Prefer exact/prefix matches. Never silently mix a different
                # creator into results that already satisfy the actual query.
                if fuzzy and not result['total'] and filters.get('text', '').strip():
                    expression, corrections = self.vocabulary.plan(filters['text'])
                    if corrections:
                        result = _query(self.connection, self.expected, **filters, search_expression=expression)
                        result.update(search_mode='fuzzy', corrections=corrections)
                size = len(canonical(result))
                if size <= 2 * 1024 * 1024:
                    self.pages[cache_key] = (deepcopy(result), size)
                    self.page_bytes += size
                    while len(self.pages) > 128 or self.page_bytes > 16 * 1024 * 1024:
                        _, (_, removed) = self.pages.popitem(last=False)
                        self.page_bytes -= removed
            return dict(result, categories=deepcopy(self.facets), creators=deepcopy(self.creators),
                        creator_facets_truncated=self.creators_truncated, cache_hit=hit,
                        worker_elapsed_seconds=round(time.perf_counter() - started, 6))

    def close(self):
        with self.lock:
            self.connection.close()
            self._release()

    def swatches(self, part_id, offset=0, limit=120):
        sha(part_id)
        if type(offset) is not int or not 0 <= offset <= MAX_PARTS or type(limit) is not int or not 1 <= limit <= 240:
            raise ValueError('Invalid swatch page.')
        with self.lock:
            if signature(self.path) != self.before:
                raise ValueError('Index path changed; restart with a verified snapshot.')
            version = self.connection.execute('PRAGMA user_version').fetchone()[0]
            if version < 3:
                return {'items': [], 'total': 0, 'offset': offset, 'next_offset': None, 'available': False}
            found = self.connection.execute('SELECT family_id FROM parts WHERE part_id=?', (part_id,)).fetchone()
            if not found: raise ValueError('Swatch family is absent from this snapshot.')
            family = found[0]
            total = self.connection.execute('SELECT count(DISTINCT variant_key) FROM parts WHERE family_id=?', (family,)).fetchone()[0]
            rows = self.connection.execute('SELECT row_json,count(*) FROM parts WHERE family_id=? GROUP BY variant_key '
                'HAVING part_id=min(part_id) ORDER BY swatch_order,variant_key LIMIT ? OFFSET ?', (family, limit, offset)).fetchall()
            items = []
            for raw, copies in rows:
                row = json.loads(raw); row.pop('package_path')
                row['container_count'] = copies
                items.append(row)
            return dict(items=items, total=total, offset=offset, next_offset=offset+len(items) if offset+len(items)<total else None,
                        family_id=family, available=True)

    def thumbnail_sources(self, items, gender):
        if not isinstance(items,list) or len(items)>24 or gender not in ('male','female'):
            raise ValueError('Bounded explicit thumbnail candidates required.')
        group=0x102 if gender=='male' else 2
        targets=[tgi((CAS_THUMB,group,key(row['resource_tgi'])[2])) for row in items]
        with self.lock:
            if signature(self.path)!=self.before: raise ValueError('Catalog snapshot changed.')
            if self.connection.execute('PRAGMA user_version').fetchone()[0]<4: return []
            providers=self.connection.execute('SELECT DISTINCT package_path,package_sha256 FROM thumbnails '
                'WHERE resource_tgi IN (SELECT value FROM json_each(?)) LIMIT 257',(json.dumps(targets),)).fetchall()
            if len(providers)>256: raise ValueError('Exact thumbnail provider bound exceeded.')
            return [dict(path=p,origin='thumbnail-cache',expected_sha256=h) for p,h in providers]


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
