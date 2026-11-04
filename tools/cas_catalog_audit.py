"""Bounded raw catalog and semantic panel audit of an already open CAS session.

Only existing panel navigation and status reads are submitted. Getter support
does not establish panel-transition support: each requested transition requires
its own exact native acknowledgement. All 72 catalog records and future fields
are retained, including catalogs outside the deliberately small navigation set.
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
from cas_hair_audit import context_identity, encoded, inventory_signature
from cas_runtime_probe import OverlaySuppression, decimal_id, uuid_id
from source_manifest import sha256, write_json

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core.cas_ui import PANELS, panel, validate_client

# Explicit requested navigation scope, not a declaration that these transitions
# have runtime proof for every species, age or occult. Unsupported getters skip
# navigation; a failed actual transition stops the entire audit without cleanup.
DEFAULT_PANELS = ('clothing_hair', 'profile_hair_eyebrows', 'clothing_head_skin_details',
    'clothing_body_skin_details', 'profile_body_skincolor', 'profile_head_eyes',
    'profile_head_nose', 'profile_head_mouth', 'profile_head_ears',
    'clothing_face_makeup_eyes', 'clothing_face_makeup_lips',
    'clothing_accessories_earrings', 'clothing_accessories_necklaces',
    'clothing_accessories_rings', 'clothing_tops', 'clothing_bottoms')
MAX_STEPS = 24
MAX_RAW_BYTES = 8 * 1024 * 1024
MAX_PROOF_BYTES = 12 * 1024 * 1024


def canonical_panels(names):
    if names is None:
        return list(DEFAULT_PANELS)
    if (not isinstance(names, (list, tuple)) or not names or len(names) > MAX_STEPS - 3 or
            any(not isinstance(name, str) for name in names)):
        raise ValueError('Supply one to 21 explicit mapped panels, leaving steps for restoration.')
    states = {value: key for key, value in PANELS.items()}
    result = [states[panel(name)] for name in names]
    if len(result) != len(set(result)):
        raise ValueError('Panel aliases must not duplicate a requested native state.')
    return result


def catalog_coverage(client, requested):
    """Query classifications are limited to what the native producer exposes."""
    return [{'panel': row['panel'], 'menu_state': row['menu_state'],
             'catalog_supported': row['supported'],
             'catalog_query': 'returned-array' if row['supported'] else 'non-array-or-null',
             'catalog_state': ('items' if row['items'] else 'empty') if row['supported'] else 'unavailable',
             'catalog_item_count': len(row['items']) if row['supported'] else None,
             'preset_query': row['preset_query'],
             'navigation_requested': row['panel'] in requested,
             'transition_verified': False,
             'navigation_outcome': ('not-observed' if row['supported'] else 'skipped-getter-unsupported')
                 if row['panel'] in requested else 'outside-requested-navigation-scope'}
            for row in client['catalogs']]


def catalog_changes(before, after):
    baseline = {row['panel']: row for row in before['catalogs']}
    changes = []
    for row in after['catalogs']:
        prior = baseline[row['panel']]
        if row != prior:
            changes.append({'panel': row['panel'], 'supported_changed': row['supported'] != prior['supported'],
                'items_changed': row['items'] != prior['items'], 'preset_changed': row['preset'] != prior['preset'],
                'preset_query_changed': row['preset_query'] != prior['preset_query'],
                'raw_record_changed': True})
    return changes


def run(state, output, identity, request, sim_id, seconds=120, step_seconds=5,
        panels=None, step_budget=20, transport=None, alive=cas_transition.process_alive,
        monotonic=time.monotonic, pause=time.sleep):
    started = monotonic()
    for name, value, maximum in (('Audit', seconds, 120), ('Native step', step_seconds, 15)):
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= maximum:
            raise ValueError(name + ' wait must be positive, finite and bounded.')
    if type(step_budget) is not int or not 4 <= step_budget <= MAX_STEPS or not decimal_id(sim_id):
        raise ValueError('Use an exact Sim identity and a native step budget from 4 to 24.')
    requested = canonical_panels(panels)
    journal_path, journal, profile, original = reusable_profile.load(state)
    script = next((row['sha256'] for row in journal['artifacts'] if row['name'] == 'ApexOccultHybrid.ts4script'), None)
    if (not isinstance(identity, dict) or type(identity.get('pid')) is not int or not 0 < identity['pid'] <= 0xffffffff or
            identity.get('test_token') != journal['token'] or script is None or identity.get('script_sha256') != script):
        raise ValueError('Catalog audit identity differs from the exact disposable journal/script.')
    if identity.get('profile') is not None and Path(identity['profile']).resolve() != profile:
        raise ValueError('Catalog audit bridge belongs to a different disposable profile.')
    output = reusable_profile.writable(output)
    if (output.exists() or output.suffix.casefold() != '.json' or not output.parent.is_dir() or output == journal_path or
            any(output == root or root in output.parents for root in (profile, original))):
        raise ValueError('Use one new external JSON audit proof outside both profiles and the journal.')
    transport = apex_cli.get if transport is None else transport
    deadline = started + seconds
    cleanup_reserve = min(2 * step_seconds + 4, seconds / 3)
    crash_before, _ = cas_transition.read_crash(profile)
    proof = {'schema': 1, 'operation': 'native-cas-catalog-panel-audit', 'identity': identity,
        'journal': str(journal_path), 'inputs': journal['artifacts'], 'sim_id': sim_id,
        'ok': False, 'outcome': 'unresolved', 'steps': [], 'owner_requests': [], 'observations': [],
        'requested_panels': requested, 'catalog_coverage': [], 'overlay_suppression': {},
        'seconds': seconds, 'step_seconds': step_seconds, 'step_budget': step_budget,
        'initial_panel_restored': False, 'final_status_observed': False,
        'complete_catalog_inventory': False, 'all_requested_supported_panels_verified': False,
        'full_72_panel_transition_coverage': False, 'raw_bytes_retained': 0,
        'raw_bytes_limit': MAX_RAW_BYTES, 'proof_bytes_limit': MAX_PROOF_BYTES,
        'panel_navigation_submitted': False, 'appearance_mutation_submitted': False,
        'outfit_selection_submitted': False, 'outfit_creation_submitted': False,
        'history_submitted': False, 'accept_submitted': False, 'entry_submitted': False,
        'save_submitted': False, 'input_submitted': False, 'profile_read_only': True,
        'no_input_replay': True, 'crash_before': crash_before, 'process_exit_verified': False,
        'scope': 'Complete raw 72-catalog inventory on a bounded explicitly requested panel subset; transition proof is per observed panel.',
        'query_limitation': 'Unsupported item getters expose non-array/null without separate failure/null classification.',
        'finalized': False}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(proof, stream, indent=2, ensure_ascii=False, allow_nan=False)
    active_step = initial = last_client = expected_context = expected_inventory = None

    def record():
        if len(encoded(proof, pretty=True)) > MAX_PROOF_BYTES:
            raise ValueError('Catalog proof bound exceeded; retain identities without replay.')
        write_json(output, proof)

    def remaining(reserve=False):
        value = deadline - monotonic() - (cleanup_reserve if reserve else 0)
        if value <= 0:
            raise TimeoutError('Catalog audit deadline expired; no cleanup replay permitted.')
        return value

    def running():
        if not alive(identity['pid']):
            proof['process_exit_verified'] = True
            raise ProcessLookupError('Verified Sims process exited during the catalog audit.')

    def bounded_pause(value):
        pause(min(value, max(0, deadline - monotonic())))

    def pinned_transport(path, query=None, timeout=12):
        timeout = min(timeout, 2, remaining())
        if path in ('/api/command', '/api/native') and isinstance(query, dict):
            if len(proof['owner_requests']) >= 512:
                raise ValueError('Owner request inventory bound reached; no request submitted.')
            row = {'action': query.get('action'), 'request_id': query.get('request_id')}
            if not uuid_id(row['request_id']):
                raise ValueError('Retain a typed owner UUID before command submission.')
            proof['owner_requests'].append(row)
            if active_step is not None:
                active_step['owner_requests'].append(row)
            record()
        result = transport(path, query, timeout=timeout)
        if path == '/api/bridge' and (not isinstance(result, dict) or any(
                result.get(field) != identity.get(field) for field in ('pid', 'test_token', 'script_sha256'))):
            raise ValueError('Pinned CAS bridge changed PID/token/script; no further commands permitted.')
        return result

    def call(_state, action, sim_id=None, **kwargs):
        running()
        kwargs.update(seconds=min(kwargs.get('seconds', 2), 2, remaining()), transport=pinned_transport)
        result = request(_state, action, sim_id=sim_id, **kwargs)
        if not isinstance(result, dict):
            raise ValueError('Catalog audit requires a typed game-owned result.')
        if action == 'cas_ui_request' and active_step is not None and uuid_id(result.get('cas_request_id')):
            active_step.update(cas_request_id=result['cas_request_id'], state='submitted')
            record()
            if any(row is not active_step and row['cas_request_id'] == result['cas_request_id'] for row in proof['steps']):
                raise ValueError('New panel/status submission reused a prior native CAS UUID; no replay or cleanup.')
        if action == 'cas_ui_result' and active_step is not None:
            active_step['poll_count'] += 1
            if result.get('cas_request_id') != kwargs.get('value') or kwargs.get('value') != active_step['cas_request_id']:
                raise ValueError('Catalog receipt belongs to another CAS UUID.')
        if result.get('request_state') in ('pending', 'running', 'unknown') or result.get('outcome') == 'unresolved':
            raise RuntimeError('Owner completion is unresolved; retain its UUID without replay or cleanup.')
        return result

    def retain(client):
        raw = encoded(client)
        if len(raw) > 160 * 1024:
            raise ValueError('Native client exceeds its bounded frame contract.')
        row = {'operation': active_step['operation'], 'arguments': active_step['arguments'],
            'cas_request_id': active_step['cas_request_id'], 'validated': False,
            'raw_sha256': hashlib.sha256(raw).hexdigest(), 'native_client': client}
        cost = len(encoded(row, pretty=True)) + len(encoded(row, pretty=True).splitlines()) * 8
        if proof['raw_bytes_retained'] + cost > MAX_RAW_BYTES:
            raise ValueError('Catalog raw evidence budget reached; retain UUID without cleanup.')
        proof['raw_bytes_retained'] += cost
        proof['observations'].append(row)
        record()
        return row

    def step(operation, reserve=False, **arguments):
        nonlocal active_step, last_client
        running()
        if len(proof['steps']) >= step_budget:
            raise ValueError('Native step budget reached; no request submitted.')
        active_step = {'operation': operation, 'arguments': arguments, 'state': 'starting',
            'cas_request_id': None, 'owner_requests': [], 'poll_count': 0, 'verified': False}
        proof['steps'].append(active_step)
        if operation == 'panel':
            proof['panel_navigation_submitted'] = True
        record()
        args = SimpleNamespace(operation=operation, state=state, sim_id=sim_id, output=None,
            seconds=min(step_seconds, remaining(reserve)), **arguments)
        try:
            result = cas_client.execute(args, call, monotonic=monotonic, pause=bounded_pause)
            active_step['receipt'] = {key: result[key] for key in ('ok', 'operation', 'outcome', 'cas_request_id',
                'cas_request_state', 'ui_transition_verified', 'request_id', 'request_state', 'message') if key in result}
            client = result.get('client')
            raw_row = retain(client) if isinstance(client, dict) else None
            if (result.get('ok') is not True or result.get('ui_transition_verified') is not True or
                    not uuid_id(result.get('cas_request_id')) or result['cas_request_id'] != active_step['cas_request_id']):
                raise RuntimeError('Native panel/status outcome is failed or unresolved; restoration is blocked.')
            validate_client(client, sim_id, dict(arguments, operation=operation))
            context = context_identity(client, sim_id)
            if expected_context is not None and context != expected_context:
                raise ValueError('Native CAS exact Sim/household/form/edit context changed during audit.')
            if expected_inventory is not None and inventory_signature(client) != expected_inventory:
                raise ValueError('Native existing outfit inventory changed during panel navigation.')
            if initial is not None and client['outfit'] != initial['outfit']:
                raise ValueError('Selected native outfit changed during panel navigation.')
            raw_row.update(validated=True, catalog_count=len(client['catalogs']),
                logical_sim_identity_verified=True, catalog_inventory_complete=True,
                catalog_queries=catalog_coverage(client, requested),
                catalog_changes_from_initial=catalog_changes(initial, client) if initial is not None else [],
                raw_sim_record_changed=client['sim'] != initial['sim'] if initial is not None else False)
            last_client = client
            active_step.update(verified=True, state='completed')
            running()
            return client
        except (OSError, ValueError, RuntimeError) as error:
            active_step.update(state='unresolved', error=str(error))
            raise
        finally:
            record()

    overlay = OverlaySuppression(lambda action: call(state, action), proof['overlay_suppression'], record)
    try:
        running()
        overlay.suppress()
        diagnostic = overlay.wait_idle(seconds=min(3, remaining(reserve=True)), monotonic=monotonic, pause=bounded_pause)
        if not cas_transition.fresh_peer(diagnostic, sim_id):
            raise ValueError('Already open CAS has no fresh exact-Sim peer; no entry/fallback submitted.')
        initial = step('status', reserve=True)
        expected_context, expected_inventory = context_identity(initial, sim_id), inventory_signature(initial)
        initial_panel = next((name for name, value in PANELS.items() if value == initial['menu_state']), None)
        coverage = catalog_coverage(initial, requested)
        # The validated getter inventory is complete even when this initial
        # menu has no safe visible-panel restoration contract. Preserve that
        # distinction before refusing navigation; inventory is not transition
        # proof and cannot authorize a guessed restoring panel.
        proof.update(initial_panel={'panel': initial_panel, 'menu_state': initial['menu_state'],
                                    'visible': initial['panel_visible']},
                     context_identity=expected_context, catalog_coverage=coverage, complete_catalog_inventory=True)
        record()
        if initial_panel is None or initial['panel_visible'] is not True:
            raise ValueError('Initial panel has no exact visible mapped restoration contract; no navigation submitted.')
        supported = [name for name in requested if next(row for row in coverage if row['panel'] == name)['catalog_supported']]
        proof['requested_supported_panels'] = supported
        record()
        stopped = False
        for name in supported:
            if len(proof['steps']) >= step_budget - 2 or deadline - monotonic() <= cleanup_reserve:
                proof['stop_reason'] = 'audit-budget-reserved-for-panel-restoration'
                stopped = True
                break
            step('panel', reserve=True, panel=name)
            row = next(row for row in coverage if row['panel'] == name)
            row.update(transition_verified=True, navigation_outcome='verified-native-readback',
                       cas_request_id=active_step['cas_request_id'])
            record()
        # Another owner may have acquired the shared slot after our last ACK.
        # Never send the restoring panel while that request is unresolved.
        overlay.wait_idle(seconds=min(3, remaining()), monotonic=monotonic, pause=bounded_pause)
        if last_client['menu_state'] != initial['menu_state'] or last_client['panel_visible'] is not True:
            step('panel', panel=initial_panel)
        final = step('status')
        if final['menu_state'] != initial['menu_state'] or final['panel_visible'] is not True:
            raise ValueError('Initial native panel did not read back after the verified return.')
        verified = all(next(row for row in coverage if row['panel'] == name)['transition_verified'] for name in supported)
        full = verified and not stopped and len(supported) == len(PANELS)
        proof.update(initial_panel_restored=True, final_status_observed=True,
            all_requested_supported_panels_verified=verified and not stopped,
            full_72_panel_transition_coverage=full,
            ok=bool(supported) and verified and not stopped,
            outcome='completed' if full else 'completed-with-partial-coverage')
        record()
        overlay.restore(True)
    except (OSError, ValueError, RuntimeError) as error:
        proof.update(ok=False, outcome='unresolved', error=str(error))
        overlay.restore(False)
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
        'catalog_count': len(proof['catalog_coverage']),
        'verified_panels': [row['panel'] for row in proof['catalog_coverage'] if row['transition_verified']],
        'complete_catalog_inventory': proof['complete_catalog_inventory'],
        'all_requested_supported_panels_verified': proof['all_requested_supported_panels_verified'],
        'full_72_panel_transition_coverage': proof['full_72_panel_transition_coverage'],
        'initial_panel_restored': proof['initial_panel_restored'], 'elapsed_seconds': proof['elapsed_seconds'],
        'message': proof.get('error', 'Raw catalog inventory retained; panel proof covers only the observed supported subset.')}


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--state', required=True, type=Path)
    result.add_argument('--sim-id', required=True)
    result.add_argument('--output', required=True, type=Path)
    result.add_argument('--seconds', type=float, default=120)
    result.add_argument('--step-seconds', type=float, default=5)
    result.add_argument('--step-budget', type=int, default=20)
    result.add_argument('--panel', dest='panels', action='append')
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = run(args.state, args.output, apex_cli.verified_identity(args.state), apex_cli.owned_request,
            args.sim_id, seconds=args.seconds, step_seconds=args.step_seconds, panels=args.panels,
            step_budget=args.step_budget, transport=apex_cli.get)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result['ok'] else 1
    except (OSError, ValueError, RuntimeError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
