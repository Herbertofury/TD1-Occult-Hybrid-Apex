"""Bounded, lossless collection of committed CAS appearance DTOs.

This only reads a native graph. It neither harvests the live model, writes a
bank, authorizes CAS acceptance nor loads a DTO as a gameplay Sim. Unknown
protobuf bytes remain intact. The receiver supplies the exact graph inventory.
"""
import copy
import hashlib
import json
import re

MAX_PAGE_BYTES = 512 * 1024
MAX_ARCHIVE_BYTES = 48 * 1024 * 1024
MAX_OWNERS = 2048
OWNER = re.compile(r'[a-z0-9_][a-z0-9_-]{0,63}/[a-z0-9_][a-z0-9_-]{0,63}\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')


def _integer(value, maximum):
    return type(value) is int and 0 < value <= maximum


def _id(value):
    return (isinstance(value, str) and 1 <= len(value) <= 20 and value.isascii() and value.isdecimal() and
            0 < int(value) < 2**64 and str(int(value)) == value)


def validate(page, pid):
    if (not isinstance(page, dict) or page.get('ok') is not True or
            type(page.get('schema')) is not int or page['schema'] != 1 or
            page.get('scope') != 'native-owner-export-page' or
            not _integer(page.get('pid'), 0xffffffff) or page['pid'] != pid or
            not isinstance(page.get('scope_id'), str) or re.fullmatch('[0-9a-f]{32}', page['scope_id']) is None or
            not _id(page.get('sim_id')) or not _integer(page.get('generation'), 2**64-1) or
            not _integer(page.get('owned_mask'),127) or not page['owned_mask'] & 1 or
            not isinstance(page.get('selected_owner_id'),str) or OWNER.fullmatch(page['selected_owner_id']) is None or
            not _integer(page.get('total_owners'), MAX_OWNERS) or
            type(page.get('start_index')) is not int or not 0 <= page['start_index'] <= page['total_owners'] or
            type(page.get('complete')) is not bool or
            any(page.get(name) is not False for name in ('appearance_written', 'model_harvested',
                'game_files_written', 'native_patch_qualified', 'production_ready')) or
            page.get('source') != 'committed-native-appearance'):
        raise ValueError('Owner export page has another runtime, scope or read-only contract.')
    after = page.get('after_owner_id')
    if not isinstance(after, str) or after and OWNER.fullmatch(after) is None or (not after) != (page['start_index'] == 0):
        raise ValueError('Owner export cursor is malformed or differs from its position.')
    rows = page.get('owners')
    if (not isinstance(rows, list) or len(rows) > 8 or
            page['start_index'] + len(rows) > page['total_owners'] or
            not rows and page['start_index'] != page['total_owners']):
        raise ValueError('Owner export page is empty, oversized or outside its inventory.')
    previous, total, wire = after, 0, 0
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {'owner_id', 'native_kind', 'native_hex', 'bytes', 'sha256', 'revision', 'linked_targets'} or
                not isinstance(row['owner_id'], str) or OWNER.fullmatch(row['owner_id']) is None or
                row['owner_id'] <= previous or type(row['native_kind']) is not int or
                row['native_kind'] not in (1, 2, 4, 8, 16, 32, 64) or
                not page['owned_mask'] & row['native_kind'] or
                type(row['revision']) is not int or not 0 <= row['revision'] < 2**64 or
                not _integer(row['bytes'], MAX_PAGE_BYTES) or not isinstance(row['native_hex'], str) or
                len(row['native_hex']) != row['bytes'] * 2 or re.fullmatch('[0-9a-f]+', row['native_hex']) is None or
                not isinstance(row['sha256'], str) or SHA.fullmatch(row['sha256']) is None):
            raise ValueError('Owner export has a duplicate identity or incomplete native bytes.')
        links=row['linked_targets']
        if (not isinstance(links,list) or len(links)>MAX_OWNERS or any(not isinstance(target,str) or
                OWNER.fullmatch(target) is None or target==row['owner_id'] for target in links) or
                links!=sorted(set(links))):
            raise ValueError('Owner export links are duplicated, malformed or self-referential.')
        if hashlib.sha256(bytes.fromhex(row['native_hex'])).hexdigest() != row['sha256']:
            raise ValueError('Owner export bytes differ from their digest.')
        previous = row['owner_id']; total += row['bytes']
        wire += len(json.dumps(row,separators=(',',':'),ensure_ascii=True).encode('ascii'))
    if total > MAX_PAGE_BYTES or wire > 1536*1024:
        raise ValueError('Owner export page exceeds its complete byte budget.')
    complete = page['start_index'] + len(rows) == page['total_owners']
    if (page['complete'] != complete or
            page.get('next_owner_id') != (None if complete else previous)):
        raise ValueError('Owner export continuation would skip or replay a page.')
    return page


class Collector:
    """Receiver-owned inventory; a partial/stale graph never becomes complete."""
    def __init__(self, identity, owner_kinds):
        if (not isinstance(identity, dict) or set(identity) != {'pid', 'scope_id', 'sim_id', 'generation', 'owned_mask', 'selected_owner_id'} or
                not _integer(identity['pid'], 0xffffffff) or not _id(identity['sim_id']) or
                not isinstance(identity['scope_id'], str) or re.fullmatch('[0-9a-f]{32}', identity['scope_id']) is None or
                not _integer(identity['generation'], 2**64-1) or not _integer(identity['owned_mask'],127) or
                not identity['owned_mask'] & 1 or not isinstance(owner_kinds, dict) or
                not 1 <= len(owner_kinds) <= MAX_OWNERS or any(not isinstance(owner, str) or OWNER.fullmatch(owner) is None or
                    type(kind) is not int or kind not in (1, 2, 4, 8, 16, 32, 64) for owner, kind in owner_kinds.items())):
            raise ValueError('Complete owner collection requires an exact receiver inventory.')
        observed=0
        for kind in owner_kinds.values():observed |= kind
        if (not isinstance(identity['selected_owner_id'],str) or identity['selected_owner_id'] not in owner_kinds or
                observed!=identity['owned_mask']):
            raise ValueError('Complete owner inventory omits its selected form or a native membership.')
        self.identity = copy.deepcopy(identity)
        self.kinds = copy.deepcopy(owner_kinds)
        self.ids = sorted(owner_kinds)
        self.rows = []
        self.bytes = 0
        self.complete = False

    def append(self, page):
        validate(page, self.identity['pid'])
        if (self.complete or any(page.get(key) != value for key, value in self.identity.items()) or
                page['total_owners'] != len(self.ids) or page['start_index'] != len(self.rows) or
                page['after_owner_id'] != (self.rows[-1]['owner_id'] if self.rows else '')):
            raise ValueError('Owner export page is stale, replayed or belongs to another graph.')
        rows = page['owners']
        expected = self.ids[len(self.rows):len(self.rows)+len(rows)]
        if ([row['owner_id'] for row in rows] != expected or
                any(row['native_kind'] != self.kinds[row['owner_id']] or
                    any(target not in self.kinds for target in row['linked_targets']) for row in rows)):
            raise ValueError('Owner export omitted, replaced or relabeled a captured form.')
        size = self.bytes + sum(row['bytes'] for row in rows)
        if size > MAX_ARCHIVE_BYTES:
            raise ValueError('Complete owner collection exceeds its byte budget.')
        # Commit the detached page only after every check. No partial mutation
        # of the collector, native graph, appearance bank or Sim occurs on error.
        self.rows.extend(copy.deepcopy(rows)); self.bytes = size
        self.complete = page['complete']
        return dict(complete=self.complete, owners=len(self.rows), bytes=self.bytes,
                    next_owner_id=page['next_owner_id'])

    def document(self):
        if not self.complete or len(self.rows) != len(self.ids):
            raise ValueError('Partial owner exports cannot become a complete document.')
        return dict(schema=1, identity=copy.deepcopy(self.identity), owners=copy.deepcopy(self.rows),
                    appearance_written=False, model_harvested=False, production_ready=False)
