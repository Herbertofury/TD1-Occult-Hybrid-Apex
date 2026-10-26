"""Two-pass raw hair observations in verified existing CAS clothing outfits.

Only status reads and existing-outfit UI selection are submitted. This does not
edit hair, add outfits, accept CAS, save, launch or assert outfit independence.
The complete native client records preserve future fields without interpreting
UI swatches as serialized 64-bit outfit color values. All returned category
metadata is retained; hidden/internal categories lack verified selector proof.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time
from types import SimpleNamespace

import apex_cli
import cas_client
import cas_transition
import reusable_profile
from cas_runtime_probe import OverlaySuppression, STANDARD_CATEGORIES, decimal_id, planned_inventory, uuid_id
from source_manifest import sha256, write_json

NATIVE_CATEGORIES = tuple(range(14))
MAX_RAW_BYTES = 20 * 1024 * 1024
MAX_PROOF_BYTES = 24 * 1024 * 1024
MAX_OWNER_REQUESTS = 2048


def encoded(value, pretty=False):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                      indent=2 if pretty else None,
                      separators=None if pretty else (',', ':')).encode('utf-8')


def category_coverage(client):
    """Unknown and unsupported categories remain visible, never invented slots."""
    inventory = planned_inventory(client)
    coverage = []
    for category in sorted(set(NATIVE_CATEGORIES) | set(inventory)):
        row = dict(inventory.get(category, {'category': category, 'state': 'not-returned',
                   'slots': [], 'max_outfits': None, 'query': 'not-returned'}))
        # Only the eight inspected clothing categories have runtime selector
        # proof. A broad integer accepted by a handler does not establish that
        # hidden/internal categories can be navigated safely.
        row['selector_verified'] = category in STANDARD_CATEGORIES
        row['selectable_slots'] = [index for index in row['slots']
                                   if row['selector_verified'] and index < len(row['slots'])]
        row['selector_unverified_slots'] = list(row['slots']) if not row['selector_verified'] else []
        row['selector_unsupported_slots'] = [index for index in row['slots']
                                             if row['selector_verified'] and index not in row['selectable_slots']]
        row['first_pass_slots'], row['repeat_pass_slots'] = [], []
        coverage.append(row)
    return coverage


def inventory_signature(client):
    return [(row['category'], row['state'], row['slots'], row['query'], row['max_outfits'])
            for row in category_coverage(client)]


def context_identity(client, sim_id):
    sim = client.get('sim')
    if not isinstance(sim, dict) or sim.get('simId') != sim_id or not decimal_id(sim.get('householdId')):
        raise ValueError('Native CAS Sim/household is not an exact decimal-string identity.')
    form = {}
    for name in ('speciesType', 'occultType', 'occultLayer'):
        if type(sim.get(name)) is not int or not 0 <= sim[name] < 1 << 32:
            raise ValueError('Native CAS form identity is unavailable: ' + name)
        form[name] = sim[name]
    # Keep native query values in their actual shapes, including future fields.
    native_context = client.get('native_context')
    if not isinstance(native_context, dict):
        raise ValueError('Native CAS edit context is unavailable.')
    return {'sim_id': sim_id, 'household_id': sim['householdId'], 'form': form,
            'native_context': native_context}


def hair_observation(client):
    """Exact resource observations, explicitly separate from unknown style/color."""
    catalogs = [row for row in client.get('catalogs', [])
                if isinstance(row, dict) and row.get('panel') == 'clothing_hair']
    catalog = catalogs[0] if len(catalogs) == 1 else None
    items = catalog.get('items') if catalog and catalog.get('supported') is True else None
    ids = [row.get('dataID') for row in items] if isinstance(items, list) else None
    resource_known = (ids is not None and all(decimal_id(value) for value in ids) and len(set(ids)) == len(ids))
    modifiers = None
    if resource_known:
        modifiers = [{'dataID': row['dataID'], 'values': {name: value for name, value in row.items()
                       if name.endswith('_modifier')}} for row in items]
    swatch_id, swatches = client.get('hair_selected_swatch_id'), client.get('hair_swatches')
    swatch_known = (client.get('hair_swatch_query') == 'returned-value' and decimal_id(swatch_id) and
                    isinstance(swatches, list))
    matching = [row for row in swatches if isinstance(row, dict) and row.get('dataID') == swatch_id] if swatch_known else []
    swatch_known = swatch_known and len(matching) == 1
    return {'style': {'selected_part_resource_ids_known': resource_known,
                     'selected_part_resource_ids': sorted(ids) if resource_known else None,
                     'hairstyle_family_known': False, 'hairstyle_family_id': None,
                     'limitation': 'Selected dataID is a variant resource; no verified hairstyle-family getter is captured.'},
            'color': {'ui_swatch_resource_known': swatch_known,
                      'ui_swatch_resource_id': swatch_id if swatch_known else None,
                      'ui_swatch_color_raw_known': swatch_known and 'color' in matching[0],
                      'ui_swatch_color_raw': matching[0].get('color') if swatch_known else None,
                      'packed_uint64_outfit_color_known': False, 'packed_uint64_outfit_color': None,
                      'limitation': 'The returned UI swatch/color does not prove a serialized 64-bit part-shift color.'},
            'modifiers': {'selected_record_known': resource_known, 'values': modifiers},
            'unknown_native_fields_preserved': True}


def compare_observations(first, repeat):
    """Compare observed resource identities without inventing semantic equivalence."""
    def changed(section, known, value):
        left, right = first['observed'][section], repeat['observed'][section]
        return left[value] != right[value] if left[known] is True and right[known] is True else None
    modifier_changed = None
    if first['observed']['modifiers']['selected_record_known'] and repeat['observed']['modifiers']['selected_record_known']:
        # Resource IDs and modifier values are different observations. Changing
        # just a variant resource must not itself become a modifier-value edit.
        left = sorted(encoded(row['values']) for row in first['observed']['modifiers']['values'])
        right = sorted(encoded(row['values']) for row in repeat['observed']['modifiers']['values'])
        modifier_changed = left != right
    return {'category': first['category'], 'index': first['index'],
            'first_cas_request_id': first['cas_request_id'], 'repeat_cas_request_id': repeat['cas_request_id'],
            'style': {'selected_part_resource_ids_changed': changed('style', 'selected_part_resource_ids_known', 'selected_part_resource_ids'),
                      'hairstyle_family_changed': None},
            'color': {'ui_swatch_resource_changed': changed('color', 'ui_swatch_resource_known', 'ui_swatch_resource_id'),
                      'ui_swatch_color_raw_changed': changed('color', 'ui_swatch_color_raw_known', 'ui_swatch_color_raw'),
                      'packed_uint64_outfit_color_changed': None},
            'modifiers_changed': modifier_changed,
            'native_sim_record_changed': first['native_client']['sim'] != repeat['native_client']['sim'],
            'raw_native_client_changed': first['raw_sha256'] != repeat['raw_sha256'],
            'outfit_independence_verified': False}


def run(state, output, identity, request, sim_id, seconds=120, step_seconds=15,
        transport=None, alive=cas_transition.process_alive, monotonic=time.monotonic, pause=time.sleep,
        max_raw_bytes=MAX_RAW_BYTES):
    started = monotonic()
    for name, value, maximum in (('Audit', seconds, 300), ('Native step', step_seconds, 60)):
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= maximum:
            raise ValueError(name + ' wait must be positive, finite and bounded.')
    if not decimal_id(sim_id) or type(max_raw_bytes) is not int or not 0 < max_raw_bytes <= MAX_RAW_BYTES:
        raise ValueError('Use an exact Sim identity and a bounded raw evidence budget.')
    deadline = started + seconds
    cleanup_reserve = min(2 * step_seconds + 6, seconds / 3)
    journal_path, journal, profile, original = reusable_profile.load(state)
    script = next((row['sha256'] for row in journal['artifacts'] if row['name'] == 'ApexOccultHybrid.ts4script'), None)
    if (not isinstance(identity, dict) or type(identity.get('pid')) is not int or not 0 < identity['pid'] <= 0xffffffff or
            identity.get('test_token') != journal['token'] or script is None or identity.get('script_sha256') != script):
        raise ValueError('Hair audit identity differs from the exact disposable journal/script.')
    if identity.get('profile') is not None and Path(identity['profile']).resolve() != profile:
        raise ValueError('Hair audit bridge belongs to a different disposable profile.')
    output = reusable_profile.writable(output)
    if (output.exists() or output.suffix.casefold() != '.json' or not output.parent.is_dir() or output == journal_path or
            any(output == root or root in output.parents for root in (profile, original))):
        raise ValueError('Use one new external JSON audit proof outside both profiles and the journal.')
    if transport is None:
        transport = apex_cli.get
    crash_before, _ = cas_transition.read_crash(profile)
    proof = {'schema': 1, 'operation': 'native-cas-existing-outfit-hair-audit', 'ok': False,
             'outcome': 'unresolved', 'identity': identity, 'journal': str(journal_path),
             'inputs': journal['artifacts'], 'sim_id': sim_id, 'seconds': seconds, 'step_seconds': step_seconds,
             'steps': [], 'owner_requests': [], 'observations': [], 'category_coverage': [], 'comparisons': [],
             'within_pass_variation': [],
             'overlay_suppression': {}, 'raw_bytes_retained': 0, 'raw_bytes_limit': max_raw_bytes,
             'proof_bytes_limit': MAX_PROOF_BYTES, 'initial_selection_restored': False,
             'final_status_observed': False, 'returned_slots_twice_observed': False,
             'verified_selector_slots_twice_observed': False, 'complete_returned_slot_coverage': False,
             'all_native_categories_queried': False, 'resource_observations_complete': False,
             'appearance_mutation_submitted': False, 'outfit_creation_submitted': False,
             'outfit_selection_submitted': False,
             'accept_submitted': False, 'save_submitted': False, 'input_submitted': False,
             'packed_uint64_color_verified': False, 'hairstyle_family_verified': False,
             'outfit_independence_verified': False, 'profile_read_only': True, 'no_input_replay': True,
             'crash_before': crash_before, 'process_exit_verified': False, 'finalized': False,
             'verified_selector_categories': list(STANDARD_CATEGORIES),
             'scope': 'Full raw native client at existing slots in verified clothing categories, two passes; other returned slots explicitly unverified.'}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(proof, stream, indent=2, ensure_ascii=False, allow_nan=False)
    active_step = last_client = expected_context = expected_inventory = None

    def record():
        # Leave room for final error/UUID metadata even if a native record is big.
        if len(encoded(proof, pretty=True)) > MAX_PROOF_BYTES:
            raise ValueError('Audit proof bound exceeded; no native request may be repeated.')
        write_json(output, proof)

    def remaining(reserve=False):
        value = deadline - monotonic() - (cleanup_reserve if reserve else 0)
        if value <= 0:
            raise TimeoutError('Hair audit deadline expired; retain request identities and do not replay.')
        return value

    def running():
        if not alive(identity['pid']):
            proof['process_exit_verified'] = True
            raise ProcessLookupError('Verified Sims process exited during hair audit.')

    def bounded_pause(value):
        pause(min(value, max(0, deadline - monotonic())))

    def pinned_transport(path, query=None, timeout=12):
        timeout = min(timeout, 2, remaining())
        if path in ('/api/command', '/api/native') and isinstance(query, dict):
            if len(proof['owner_requests']) >= MAX_OWNER_REQUESTS:
                raise ValueError('Owner request inventory bound reached; no request submitted.')
            row = {'action': query.get('action'), 'request_id': query.get('request_id')}
            proof['owner_requests'].append(row)
            if active_step is not None:
                active_step['owner_requests'].append(row)
            record()  # Durable before network submission, including response loss.
        result = transport(path, query, timeout=timeout)
        if path == '/api/bridge' and (not isinstance(result, dict) or any(
                result.get(field) != identity.get(field) for field in ('pid', 'test_token', 'script_sha256'))):
            raise ValueError('Pinned CAS bridge changed PID/token/script; no further commands permitted.')
        return result

    def call(_state, action, sim_id=None, **kwargs):
        running()
        kwargs['seconds'] = min(kwargs.get('seconds', 2), 2, remaining())
        kwargs['transport'] = pinned_transport
        result = request(_state, action, sim_id=sim_id, **kwargs)
        if not isinstance(result, dict):
            raise ValueError('Hair audit requires a typed game-owned result.')
        if action == 'cas_ui_request' and active_step is not None:
            rid = result.get('cas_request_id')
            if uuid_id(rid):
                active_step.update(cas_request_id=rid, state='submitted')
                record()
        if action == 'cas_ui_result' and active_step is not None:
            active_step['poll_count'] += 1
            if result.get('cas_request_id') != kwargs.get('value') or kwargs.get('value') != active_step['cas_request_id']:
                raise ValueError('Native hair-audit receipt belongs to another CAS UUID.')
        if result.get('request_state') in ('pending', 'running', 'unknown') or result.get('outcome') == 'unresolved':
            raise RuntimeError('Owner completion is unresolved; retain its UUID without replay or cleanup.')
        return result

    def step(operation, reserve=False, **arguments):
        nonlocal active_step, last_client
        running()
        active_step = {'operation': operation, 'arguments': arguments, 'state': 'starting',
                       'cas_request_id': None, 'verified': False, 'owner_requests': [], 'poll_count': 0,
                       'started_seconds': max(0, monotonic() - started)}
        proof['steps'].append(active_step)
        if operation == 'outfit':
            proof['outfit_selection_submitted'] = True
        record()
        args = SimpleNamespace(operation=operation, state=state, sim_id=sim_id, output=None,
                               seconds=min(step_seconds, remaining(reserve)), **arguments)
        try:
            result = cas_client.execute(args, call, monotonic=monotonic, pause=bounded_pause)
            active_step['receipt'] = {key: result[key] for key in ('ok', 'operation', 'outcome', 'cas_request_id',
                  'cas_request_state', 'ui_transition_verified', 'request_id', 'request_state', 'message') if key in result}
            if (result.get('ok') is not True or result.get('ui_transition_verified') is not True or
                    not uuid_id(result.get('cas_request_id')) or result['cas_request_id'] != active_step['cas_request_id']):
                raise RuntimeError('Native outfit selection/status is failed or unresolved; no cleanup replay permitted.')
            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
            from apex_core.cas_ui import validate_client
            client = result.get('client')
            validate_client(client, sim_id, dict(arguments, operation=operation))
            context = context_identity(client, sim_id)
            if expected_context is not None and context != expected_context:
                raise ValueError('Native CAS Sim/household/form/edit context changed during audit.')
            if expected_inventory is not None and inventory_signature(client) != expected_inventory:
                raise ValueError('Native existing outfit identity inventory changed during audit.')
            last_client = client
            active_step.update(verified=True, state='completed')
            running()
            return client
        except (OSError, ValueError, RuntimeError) as error:
            active_step.update(state='unresolved', error=str(error))
            raise
        finally:
            active_step['elapsed_seconds'] = max(0, monotonic() - started - active_step['started_seconds'])
            record()

    def capture(client, pass_number, category, index):
        raw = encoded(client)
        # The native wire itself is limited to 131072 UTF-8 bytes. A host JSON
        # reserialization can spell equivalent floats slightly differently.
        if len(raw) > 160 * 1024:
            raise ValueError('Native client evidence exceeds its bounded frame contract.')
        row = {'pass': pass_number, 'category': category, 'index': index,
               'cas_request_id': active_step['cas_request_id'], 'raw_sha256': hashlib.sha256(raw).hexdigest(),
               'observed': hair_observation(client), 'native_client': client}
        cost = len(encoded(row, pretty=True)) + len(encoded(row, pretty=True).splitlines()) * 8
        if proof['raw_bytes_retained'] + cost > max_raw_bytes:
            proof['stop_reason'] = 'raw-evidence-budget'; proof['raw_record_not_retained'] = {
                'category': category, 'index': index, 'pass': pass_number, 'cas_request_id': active_step['cas_request_id']}
            record()
            return False
        proof['raw_bytes_retained'] += cost
        proof['observations'].append(row)
        record()
        return True

    overlay = OverlaySuppression(lambda action: call(state, action), proof['overlay_suppression'], record)
    try:
        running()
        overlay.suppress()
        diagnostic = overlay.wait_idle(seconds=min(3, remaining(reserve=True)), monotonic=monotonic, pause=bounded_pause)
        if not cas_transition.fresh_peer(diagnostic, sim_id):
            raise ValueError('Already open CAS has no fresh exact-Sim peer; no entry/fallback submitted.')
        initial = step('status', reserve=True)
        expected_context, expected_inventory = context_identity(initial, sim_id), inventory_signature(initial)
        initial_slot = (initial['outfit']['outfit_type'], initial['outfit']['outfit_index'])
        coverage = category_coverage(initial)
        proof.update(context_identity=expected_context, initial_selection={'category': initial_slot[0], 'index': initial_slot[1]},
                     initial_planned_outfits=initial.get('planned_outfits'), category_coverage=coverage,
                     all_native_categories_queried=all(row['state'] not in ('not-returned', 'unavailable')
                                                      for row in coverage if row['category'] in NATIVE_CATEGORIES))
        slots = [(row['category'], index) for row in coverage for index in row['selectable_slots']]
        if initial_slot not in slots:
            raise ValueError('Initial selected slot has no existing native selector contract; no series submitted.')
        proof['explicit_existing_slot_count'] = sum(len(row['slots']) for row in coverage)
        proof['selectable_slot_count'] = len(slots)
        record()
        stop = False
        for pass_number, field in ((1, 'first_pass_slots'), (2, 'repeat_pass_slots')):
            for category, index in slots:
                if deadline - monotonic() <= cleanup_reserve:
                    proof['stop_reason'] = 'audit-budget-reserved-for-selection-restoration'
                    stop = True
                    break
                current = (last_client['outfit']['outfit_type'], last_client['outfit']['outfit_index'])
                if pass_number == 1 and not proof['observations'] and current == (category, index):
                    observed = initial  # One complete initial read, retained without duplication.
                elif current == (category, index):
                    observed = step('status', reserve=True)
                else:
                    observed = step('outfit', reserve=True, category=category, index=index)
                if not capture(observed, pass_number, category, index):
                    stop = True
                    break
                next(row for row in coverage if row['category'] == category)[field].append(index)
                record()
            if stop:
                break
        by_slot = {}
        for row in proof['observations']:
            by_slot.setdefault((row['category'], row['index']), {})[row['pass']] = row
        proof['comparisons'] = [compare_observations(rows[1], rows[2]) for _, rows in sorted(by_slot.items())
                                if 1 in rows and 2 in rows]
        # Expose first-pass outfit differences as well as repeated observations;
        # neither comparison establishes that an intentional future hair edit
        # will stay local to an outfit.
        for pass_number in (1, 2):
            anchor = next((row for row in proof['observations'] if row['pass'] == pass_number and
                           (row['category'], row['index']) == initial_slot), None)
            variation = {'pass': pass_number, 'anchor_selection': {'category': initial_slot[0], 'index': initial_slot[1]},
                         'anchor_observed': anchor is not None, 'comparisons': []}
            if anchor is not None:
                for observed in proof['observations']:
                    if observed['pass'] == pass_number and observed is not anchor:
                        comparison = compare_observations(anchor, observed)
                        comparison.update(category=observed['category'], index=observed['index'],
                                          comparison_scope='same-pass-different-slot')
                        variation['comparisons'].append(comparison)
            proof['within_pass_variation'].append(variation)
        proof['verified_selector_slots_twice_observed'] = all(len(rows) == 2 for rows in by_slot.values()) and len(by_slot) == len(slots)
        proof['returned_slots_twice_observed'] = (proof['verified_selector_slots_twice_observed'] and
                                                   len(by_slot) == proof['explicit_existing_slot_count'])
        if (last_client['outfit']['outfit_type'], last_client['outfit']['outfit_index']) != initial_slot:
            step('outfit', category=initial_slot[0], index=initial_slot[1])
        final = step('status')
        if (final['outfit']['outfit_type'], final['outfit']['outfit_index']) != initial_slot:
            raise ValueError('Initial outfit selection did not read back after the verified return.')
        proof.update(initial_selection_restored=True, final_status_observed=True,
                     final_planned_outfits=final.get('planned_outfits'))
        resource_complete = all(row['observed']['style']['selected_part_resource_ids_known'] and
                                row['observed']['color']['ui_swatch_resource_known'] for row in proof['observations'])
        proof['resource_observations_complete'] = proof['verified_selector_slots_twice_observed'] and resource_complete
        complete = (proof['returned_slots_twice_observed'] and proof['all_native_categories_queried'] and
                    not any(row['selector_unsupported_slots'] or row['selector_unverified_slots'] for row in coverage) and resource_complete)
        proof.update(ok=proof['verified_selector_slots_twice_observed'] and not stop,
                     complete_returned_slot_coverage=complete,
                     outcome='completed' if complete else 'completed-with-partial-coverage',
                     available_observations_verified=proof['verified_selector_slots_twice_observed'] and not stop)
        record()
        overlay.restore(True)
    except (OSError, ValueError, RuntimeError) as error:
        proof.update(ok=False, outcome='unresolved', error=str(error))
        overlay.restore(False)  # No native or outfit cleanup after ambiguous outcomes.
        try:
            running()
        except ProcessLookupError:
            proof['outcome'] = 'process-exited'
        except (OSError, ValueError) as observation_error:
            proof['process_observation_error'] = str(observation_error)
        try:
            proof['crash'] = cas_transition.preserve_crash(profile, output, crash_before)
        except (OSError, ValueError) as crash_error:
            proof['crash'] = {'preserved': False, 'outcome': 'refused', 'error': str(crash_error)}
        if proof['crash'].get('preserved'):
            proof['outcome'] = 'crash'
    proof.update(elapsed_seconds=max(0, monotonic() - started), finalized=True)
    record()
    return {'ok': proof['ok'], 'outcome': proof['outcome'], 'proof': str(output), 'proof_sha256': sha256(output),
            'observed_slots': len({(row['category'], row['index']) for row in proof['observations']}),
            'compared_slots': len(proof['comparisons']), 'initial_selection_restored': proof['initial_selection_restored'],
            'returned_slots_twice_observed': proof['returned_slots_twice_observed'],
            'verified_selector_slots_twice_observed': proof['verified_selector_slots_twice_observed'],
            'complete_returned_slot_coverage': proof['complete_returned_slot_coverage'],
            'packed_uint64_color_verified': False, 'hairstyle_family_verified': False,
            'outfit_independence_verified': False, 'elapsed_seconds': proof['elapsed_seconds'],
            'message': proof.get('error', 'Native resource observations recorded; style-family/packed-color independence remains unverified.')}


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--state', required=True, type=Path)
    result.add_argument('--sim-id', required=True)
    result.add_argument('--output', required=True, type=Path)
    result.add_argument('--seconds', type=float, default=120)
    result.add_argument('--step-seconds', type=float, default=15)
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = run(args.state, args.output, apex_cli.verified_identity(args.state), apex_cli.owned_request,
                     args.sim_id, seconds=args.seconds, step_seconds=args.step_seconds, transport=apex_cli.get)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result['ok'] else 1
    except (OSError, ValueError, RuntimeError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
