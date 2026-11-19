"""Collect exact equipped CAS rows without activating forms or clicking menus.

Status may add an observation to CAS History. This command never applies an
appearance edit, invents missing presets, saves the game or switches a form.
"""
import copy
import json
from pathlib import Path
import re
import time
from concurrent.futures import ThreadPoolExecutor

import reusable_profile
from source_manifest import sha256, write_json


SHA = re.compile(r'[0-9a-f]{64}\Z')
MAX_ROWS = 16384


def _digest(value):
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def _inventory(status, identity, sim_id, form):
    if (not isinstance(status, dict) or status.get('ok') is not True or
            status.get('runtime_pid') != identity['pid'] or
            status.get('inspected_form_flags') != form or
            not _digest(status.get('appearance_sha256'))):
        raise ValueError('Fresh native equipped inventory identity is unavailable.')
    lane = status.get('history_lane')
    if (not isinstance(lane, str) or len(lane) > 256 or len(lane.split(':')) < 5 or
            lane.split(':')[2:4] != [sim_id, str(form)]):
        raise ValueError('Equipped inventory has a different Sim/form owner.')
    outfits = status.get('outfit_inventory')
    if not isinstance(outfits, list) or len(outfits) > 128:
        raise ValueError('Native outfit inventory is missing or exceeds its bound.')
    rows = []
    for index, outfit in enumerate(outfits):
        if (not isinstance(outfit, dict) or type(outfit.get('index')) is not int or
                outfit['index'] != index or not isinstance(outfit.get('parts'), list) or
                type(outfit.get('category')) is not int or type(outfit.get('ordinal')) is not int or
                not isinstance(outfit.get('outfit_id'), str)):
            raise ValueError('Native outfit indices are not exact and contiguous.')
        for part_index, row in enumerate(outfit['parts']):
            if (not isinstance(row, dict) or row.get('index') != part_index or
                    type(row.get('body_type')) is not int or
                    row.get('target') != '{}:{}:{}'.format(index, row['body_type'], part_index) or
                    not isinstance(row.get('cas_part_id'), str) or not row['cas_part_id'].isdecimal()):
                raise ValueError('Native equipped row is incomplete or ambiguously addressed.')
            rows.append(dict(row, outfit_index=index, category=outfit['category'],
                             ordinal=outfit['ordinal'], outfit_id=outfit['outfit_id']))
            if len(rows) > MAX_ROWS:
                raise ValueError('Native inventory exceeds its bound; no rows omitted.')
    return lane, rows


def _page(page, status, expected, cursor, form, sim_id, identity):
    if (not isinstance(page, dict) or page.get('ok') is not True or
            page.get('history_lane') != status['history_lane'] or
            page.get('appearance_sha256') != status['appearance_sha256'] or
            page.get('runtime_pid') != identity['pid'] or
            page.get('inspected_form_flags') != form or page.get('cursor') != cursor or
            page.get('total') != len(expected) or type(page.get('total')) is not int):
        raise ValueError('Equipped page is stale, cross-owner or has a different row count.')
    owner = page.get('owner')
    if (not isinstance(owner, dict) or owner.get('runtime_pid') != identity['pid'] or
            owner.get('sim_id') != sim_id or owner.get('form_flags') != form or
            str(owner.get('save_guid')) != status['history_lane'].split(':')[0] or
            str(owner.get('slot_id')) != status['history_lane'].split(':')[1]):
        raise ValueError('Equipped page native save/Sim/form binding differs.')
    items = page.get('items')
    count = min(8, len(expected) - cursor)
    if not isinstance(items, list) or len(items) != count:
        raise ValueError('Equipped page omitted or added a row.')
    for item, native in zip(items, expected[cursor:cursor + count]):
        if not isinstance(item, dict) or any(item.get(k) != native.get(k)
                for k in ('target', 'body_type', 'index', 'cas_part_id', 'layer_id',
                          'outfit_index', 'category', 'ordinal', 'outfit_id')):
            raise ValueError('Equipped metadata page differs from the exact native row.')
        obj, color = item.get('object_id'), item.get('color_shift')
        if (obj is not None and (type(obj) is not int or not 0 <= obj < 1 << 64) or
                (None if obj is None else str(obj)) != native.get('object_id') or
                color is not None and (type(color) is not int or not 0 <= color < 1 << 64) or
                (None if color is None else '{:016X}'.format(color)) != native.get('color_hex')):
            raise ValueError('Equipped metadata object/color arrays differ from the native row.')
    end = cursor + count
    next_cursor = end if end < len(expected) else None
    if page.get('next_cursor') != next_cursor or page.get('complete') is not (next_cursor is None):
        raise ValueError('Equipped paging cursor is missing, repeated or skips rows.')
    return items, next_cursor


def _catalog(manifest, expected_hash):
    if manifest is None:
        if expected_hash is not None:
            raise ValueError('A catalog hash requires its exact manifest.')
        return None
    from cas_resource_catalog import Broker, CACHE_ROOT
    path = reusable_profile.writable(manifest)
    root = CACHE_ROOT.resolve()
    if root not in path.parents or not _digest(expected_hash):
        raise ValueError('Use one hash-bound manifest in the external CAS resource cache.')
    return Broker(path, expected_hash)


def enrich(item, native, catalog):
    """Keep code, package and preferred names distinct; never guess provenance."""
    row = copy.deepcopy(item)
    row['label'] = native.get('label')
    row['color_hex'] = native.get('color_hex')
    row['color_values'] = native.get('color_values')
    row['target_supported'] = native.get('target_supported')
    row['target_reason'] = native.get('target_reason')
    code = row.get('display_name')
    row['names'] = {'code': code, 'package': None, 'preferred': code,
                    'preferred_source': row.get('name_status', 'unresolved')}
    row['catalog_match_verified'] = False
    if catalog is None:
        return row
    editor = row.get('part_editor') or {}
    matches = [record for record in catalog.records.values()
        if record['row'].get('resource_tgi') == editor.get('resource_tgi') and
        record['row'].get('effective_resource_sha256') == editor.get('resource_sha256') and
        record['row'].get('body_type') == row.get('body_type') and
        record['row'].get('status') == 'resolved']
    if len(matches) != 1:
        row['catalog_match_reason'] = 'No unique catalog entry matches exact native CASP bytes and BodyType.'
        return row
    entry = matches[0]['row']
    provenance = entry.get('provenance') or {}
    package = provenance.get('package_filename')
    preferred = entry.get('preferred_name') or entry.get('display_name') or code
    source = entry.get('preferred_name_status') or entry.get('name_status')
    if provenance.get('origin') in ('cc', 'mod') and package and source != 'localized-title':
        preferred, source = package, 'cc-package-filename'
    row['names'] = {'code': code, 'package': package, 'preferred': preferred,
                    'preferred_source': source}
    row['catalog_match_verified'] = True
    row['provenance'] = copy.deepcopy(provenance)
    row['resource_id'] = entry['resource_id']
    row['cache_proof'] = entry['cache_proof']
    row['studio_open'] = copy.deepcopy(entry.get('studio_open'))
    row['thumbnail'] = copy.deepcopy(entry.get('thumbnail'))
    if row['thumbnail'] and row['thumbnail'].get('status') == 'resolved':
        catalog.thumbnail(entry['resource_id'])  # Verify actual cached image bytes.
        row['thumbnail']['cache_bytes_verified'] = True
    return row


def collect(state, output, identity, request, sim_id, form=None, all_forms=False,
            catalog_manifest=None, catalog_manifest_sha256=None, identity_provider=None, jobs=4):
    if (not isinstance(sim_id, str) or not sim_id.isdecimal() or
            not 0 < int(sim_id) < 1 << 64 or form is not None and
            (type(form) is not int or not 0 < form < 1 << 32) or all_forms and form is not None):
        raise ValueError('Choose one exact Sim and either a form or all observed forms.')
    if type(jobs) is not int or not 1 <= jobs <= 4:
        raise ValueError('Read-only page concurrency must be between one and four.')
    started = time.monotonic()
    state_path, journal, profile, original = reusable_profile.load(state)
    output = reusable_profile.writable(output)
    if (output.exists() or output.suffix.casefold() != '.json' or
            any(output == root or root in output.parents for root in (profile, original))):
        raise ValueError('Inventory needs one new external JSON evidence filename.')
    journal_hash = sha256(state_path)
    catalog = _catalog(catalog_manifest, catalog_manifest_sha256)
    proof = {'schema': 1, 'operation': 'collect-equipped-cas-inventory', 'ok': False,
             'identity': identity, 'inputs': journal['artifacts'], 'forms': [],
             'appearance_writes': False, 'form_activation_requested': False,
             'read_only_page_jobs': jobs,
             'save_requested': False, 'history_observation_possible': True,
             'all_sim_fields_editable': False, 'native_manual_slot_verified': False,
             'scope': 'Every serialized equipped part row for each selected existing appearance owner; opaque preset/genetic data has no invented CASP row.'}
    def bound():
        _, current, _, _ = reusable_profile.load(state)
        if sha256(state_path) != journal_hash or current['artifacts'] != journal['artifacts']:
            raise ValueError('Installed profile/journal changed during inventory.')
        fresh = identity_provider(state) if identity_provider else identity
        if any(fresh.get(k) != identity.get(k) for k in ('pid', 'test_token', 'script_sha256')):
            raise ValueError('Running inventory owner changed; no pages combined across runtimes.')
    def call(action, flags=None, value=None):
        bound()
        if flags is not None:
            value = json.dumps({'form': flags, 'value': value})
        result = request(state, action, sim_id, value=value)
        bound()
        return result
    write_json(output, proof)
    try:
        initial = call('studio_status', form)
        flags = initial.get('inspected_form_flags')
        _inventory(initial, identity, sim_id, flags)
        forms = [flags]
        if all_forms:
            inventory = initial.get('form_inventory')
            if not isinstance(inventory, list) or not 1 <= len(inventory) <= 32:
                raise ValueError('Existing native form inventory is unavailable or unbounded.')
            forms = [row.get('flags') for row in inventory if isinstance(row, dict)]
            if (len(forms) != len(inventory) or len(set(forms)) != len(forms) or
                    any(type(flag) is not int or not 0 < flag < 1 << 32 for flag in forms)):
                raise ValueError('Native form inventory is duplicated or untyped.')
        for flag in forms:
            status = initial if flag == flags else call('studio_status', flag)
            lane, expected = _inventory(status, identity, sim_id, flag)
            collected = []
            cursors = list(range(0, len(expected), 8)) or [0]
            def read_page(cursor):
                value = json.dumps({'lane': lane, 'appearance_sha256': status['appearance_sha256'],
                    'runtime_pid': identity['pid'], 'cursor': cursor, 'limit': 8, 'outfit_index': None})
                return call('studio_items', flag, value)
            # Only fixed read-only pages overlap. The native game-thread bridge
            # still owns serialization. Form/appearance writes never use this.
            with ThreadPoolExecutor(max_workers=jobs) as pool:
                pending = {cursor: pool.submit(read_page, cursor) for cursor in cursors}
                for cursor in cursors:
                    page = pending[cursor].result()
                    items, _ = _page(page, status, expected, cursor, flag, sim_id, identity)
                    collected.extend(enrich(item, native, catalog)
                                     for item, native in zip(items, expected[cursor:cursor + len(items)]))
            after = call('studio_status', flag)
            _inventory(after, identity, sim_id, flag)
            if any(after.get(k) != status.get(k) for k in ('history_lane', 'appearance_sha256', 'outfit_inventory')):
                raise ValueError('Appearance changed during inventory; partial rows are not certified.')
            proof['forms'].append({'flags': flag, 'history_lane': lane,
                'appearance_sha256': status['appearance_sha256'], 'appearance_source': status.get('appearance_source'),
                'stable_save_slot_verified': status.get('stable_save_slot_verified'),
                'readable_appearance_fields': status.get('readable_appearance_fields'),
                'outfit_inventory': status['outfit_inventory'], 'category_catalog': status.get('category_catalog'),
                'total': len(expected), 'items': collected, 'complete': True})
            write_json(output, proof)
        # Reading another form's complete history can invoke the guarded native
        # serializer. Verify every collected owner again after the whole scan.
        for row in proof['forms']:
            final = call('studio_status', row['flags'])
            _inventory(final, identity, sim_id, row['flags'])
            if any(final.get(key) != row.get(key) for key in
                   ('appearance_sha256', 'history_lane', 'outfit_inventory')) or \
                    final.get('current_form_flags') != initial.get('current_form_flags'):
                raise ValueError('A collected appearance owner changed during another form read; scan is not certified.')
        bound()
        if catalog_manifest is not None and sha256(catalog_manifest) != catalog_manifest_sha256:
            raise ValueError('Resource catalog changed during inventory.')
        proof['ok'] = True
    except (OSError, ValueError, RuntimeError) as error:
        proof['error'] = str(error)
    proof['elapsed_seconds'] = round(time.monotonic() - started, 6)
    write_json(output, proof)
    return {'ok': proof['ok'], 'proof': str(output), 'proof_sha256': sha256(output),
            'forms': len(proof['forms']), 'equipped_rows': sum(row['total'] for row in proof['forms']),
            'elapsed_seconds': proof['elapsed_seconds'],
            'message': proof.get('error', 'Complete equipped inventory retained without activating or editing forms.')}
