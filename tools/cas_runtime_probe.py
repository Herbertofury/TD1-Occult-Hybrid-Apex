"""Repeatable exact-ID regression probe for an already open native CAS session.

No launch, CAS entry, acceptance, save, profile mutation or pointer input occurs.
The default sequence restores its hair swatch and selected outfit on success.
An unresolved operation stops the sequence; no mutation or cleanup is replayed.
"""
import argparse
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
from source_manifest import sha256, write_json

STANDARD_CATEGORIES = (0, 1, 2, 3, 4, 9, 10, 11)


class OverlaySuppression:
    """Hide F11 without starting a DLL; unresolved work stays hidden.

    The supplied call preserves the caller's pinned identity and deadlines.
    Native controls are submitted once using the existing deduplicated API.
    """
    def __init__(self, call, evidence=None, record=None):
        self.call, self.record = call, record or (lambda: None)
        self.evidence = {} if evidence is None else evidence
        self.evidence.update(initial_visibility=None, sidecar_started=None,
                             suppression_verified=False, hide_attempted=False,
                             restore_attempted=False, restored=False, controls=[],
                             blocking_native_requests=[], observed_native_requests=[], diagnostics_count=0,
                             outcome='not-observed')

    def _control(self, action):
        row = {'action': action, 'state': 'attempted', 'request_id': None}
        self.evidence['controls'].append(row)
        self.record()
        try:
            result = self.call(action)
            if not isinstance(result, dict):
                raise ValueError('F11 visibility control requires a typed game-owned result.')
            for key in ('ok', 'visible', 'request_id', 'request_state', 'message'):
                if isinstance(result.get(key), (str, bool)):
                    row[key] = result[key]
            row['state'] = 'observed'
            if result.get('request_state') in ('pending', 'running', 'unknown') or result.get('outcome') == 'unresolved':
                raise RuntimeError('F11 visibility outcome is unresolved; do not repeat its control.')
            return result
        except (OSError, ValueError, RuntimeError) as error:
            row.update(state='unresolved', error=str(error))
            raise
        finally:
            self.record()

    def suppress(self):
        if self.evidence['suppression_verified']:
            return self.evidence
        if self.evidence['hide_attempted']:
            raise RuntimeError('Prior F11 hide is unresolved; its control must not be repeated.')
        status = self._control('overlay_status')
        visible = status.get('visible')
        if type(visible) is not bool:
            # Missing visibility only proves absence for the exact existing
            # unloaded-loader contract, never for a generic failed response.
            if (status.get('ok') is False and status.get('message') == 'F11 sidecar has not been started.' and
                    'native_status' not in status and 'dll_sha256' not in status):
                self.evidence.update(sidecar_started=False, suppression_verified=True, outcome='not-started')
                self.record()
                return self.evidence
            raise ValueError('Initial F11 visibility is unknown; no CAS request may take its slot.')
        self.evidence.update(initial_visibility=visible, sidecar_started=True)
        self.record()
        if visible:
            self.evidence['hide_attempted'] = True
            self.record()
            hidden = self._control('overlay_hide')
            if hidden.get('ok') is not True or hidden.get('visible') is not False:
                raise RuntimeError('F11 hide was not verified; no CAS transaction submitted.')
        self.evidence.update(suppression_verified=True, outcome='hidden' if visible else 'already-hidden')
        self.record()
        return self.evidence

    def _diagnostic(self):
        diagnostic = self.call('cas_ui_diagnostics')
        self.evidence['diagnostics_count'] += 1
        if (not isinstance(diagnostic, dict) or diagnostic.get('ok') is not True or
                not isinstance(diagnostic.get('requests'), list) or len(diagnostic['requests']) > 512):
            raise ValueError('Native request inventory is unavailable; F11 must remain hidden.')
        blocked = []
        for row in diagnostic['requests']:
            if not isinstance(row, dict) or not isinstance(row.get('state'), str) or not uuid_id(row.get('cas_request_id')):
                raise ValueError('Native request identity/state is unknown; F11 must remain hidden.')
            retained = next((item for item in self.evidence['observed_native_requests']
                             if item['cas_request_id'] == row['cas_request_id']), None)
            if retained is None:
                retained = {'cas_request_id': row['cas_request_id'], 'initial_state': row['state']}
                self.evidence['observed_native_requests'].append(retained)
            retained['last_state'] = row['state']
            expired_status = row['state'] == 'superseded-read' and row.get('operation') == 'status'
            terminal = row['state'] in ('completed', 'failed') or expired_status
            if 'outcome' in row:
                terminal = terminal and (row['outcome'] in ('completed', 'failed', 'live-return', 'accept-rejected') or
                                         (expired_status and row['outcome'] == 'superseded-read'))
            if 'commit_outcome' in row:
                terminal = terminal and row['commit_outcome'] in ('accepted', 'rejected')
            if row.get('lifecycle_stage') in ('accept-intent', 'accept-unresolved'):
                terminal = False
            if not terminal:
                blocked.append({key: row.get(key) for key in ('cas_request_id', 'state', 'operation', 'outcome')
                                if isinstance(row.get(key), str)})
        self.evidence['blocking_native_requests'] = blocked
        self.record()
        return diagnostic, blocked

    def wait_idle(self, seconds=3, monotonic=time.monotonic, pause=time.sleep):
        if not self.evidence['suppression_verified']:
            raise ValueError('Verify F11 suppression before observing the shared CAS slot.')
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 5:
            raise ValueError('Native slot draining must be bounded to at most five seconds.')
        deadline = monotonic() + seconds
        while True:
            diagnostic, blocked = self._diagnostic()
            if not blocked:
                self.evidence['native_slot_idle_verified'] = True
                self.record()
                return diagnostic
            if any(row.get('state') != 'pending' or row.get('outcome') not in (None, 'pending-client') for row in blocked):
                raise RuntimeError('Native acceptance or unresolved request still owns the CAS slot; no new read submitted.')
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError('Existing native CAS request did not resolve after hiding F11; retain its UUID.')
            pause(min(.1, remaining))

    def restore(self, safe_terminal):
        if self.evidence['restore_attempted']:
            return self.evidence  # Preserve even an ambiguous show; never replay.
        if safe_terminal is not True or not self.evidence['suppression_verified']:
            self.evidence['outcome'] = 'left-hidden-unresolved'
            self.record()
            return self.evidence
        if self.evidence['initial_visibility'] is not True:
            self.evidence['outcome'] = 'not-started' if self.evidence['sidecar_started'] is False else 'kept-hidden'
            self.record()
            return self.evidence
        _diagnostic, blocked = self._diagnostic()
        if blocked:
            self.evidence['outcome'] = 'left-hidden-native-request-unresolved'
            self.record()
            return self.evidence
        self.evidence['restore_attempted'] = True
        self.record()
        shown = self._control('overlay_show')
        if shown.get('ok') is not True or shown.get('visible') is not True:
            raise RuntimeError('F11 visibility restoration was not verified; its control must not be replayed.')
        self.evidence.update(restored=True, outcome='restored')
        self.record()
        return self.evidence


def decimal_id(value):
    return (isinstance(value, str) and value.isascii() and value.isdecimal() and
            0 < int(value) < 1 << 64 and str(int(value)) == value)


def uuid_id(value):
    return isinstance(value, str) and len(value) == 32 and all(char in '0123456789abcdef' for char in value)


def planned_inventory(client):
    """Derive only explicit slot identities; null/failed discovery stays unknown."""
    source = client.get('planned_outfits')
    if not isinstance(source, list) or len(source) > 256:
        source = []
    inventory = {}
    for row in source:
        if not isinstance(row, dict) or type(row.get('category')) is not int or not 0 <= row['category'] <= 255:
            raise ValueError('Native planned outfit category is not a typed identity.')
        category = row['category']
        if category in inventory:
            raise ValueError('Native planned outfit category is duplicated; no slot may be guessed.')
        record = {'category': category, 'state': 'unavailable', 'slots': [], 'max_outfits': None,
                  'query': row.get('query') if isinstance(row.get('query'), str) else 'unknown'}
        data = row.get('data')
        if row.get('supported') is True and row.get('query') == 'returned-value' and isinstance(data, dict):
            slots = data.get('outfit_list')
            if isinstance(slots, list) and len(slots) <= 5:
                identities = []
                for slot in slots:
                    if (not isinstance(slot, dict) or type(slot.get('outfit_type')) is not int or
                            slot['outfit_type'] != category or type(slot.get('outfit_index')) is not int or
                            not 0 <= slot['outfit_index'] < 5 or slot['outfit_index'] in identities):
                        raise ValueError('Native planned outfit slot is invalid or duplicated; no outfit invented.')
                    identities.append(slot['outfit_index'])
                record.update(state='present' if identities else 'missing', slots=sorted(identities))
                if type(data.get('max_outfits')) is int and 0 < data['max_outfits'] <= 5:
                    record['max_outfits'] = data['max_outfits']
        inventory[category] = record
    return inventory


def swatch_choice(client):
    current = client.get('hair_selected_swatch_id')
    source = client.get('hair_swatches')
    if not decimal_id(current) or client.get('hair_swatch_query') != 'returned-value' or not isinstance(source, list) or len(source) > 1024:
        raise ValueError('Exact native hair swatch identities are unavailable; no hair change submitted.')
    ids = []
    for item in source:
        value = item.get('dataID') if isinstance(item, dict) else None
        if not decimal_id(value) or value in ids:
            raise ValueError('Native hair swatch identity is ambiguous; no hair change submitted.')
        ids.append(value)
    if current not in ids:
        raise ValueError('Original selected hair swatch is absent from the returned list; no change submitted.')
    alternate = next((value for value in ids if value != current), None)
    if alternate is None:
        raise ValueError('No exact alternate hair swatch is available; no change submitted.')
    return current, alternate


def summary(client):
    """Targeted primitive evidence rather than raw native object records."""
    inventory = planned_inventory(client)
    return {'sim_id': client['sim']['simId'], 'menu_state': client['menu_state'],
            'panel_visible': client['panel_visible'], 'outfit_type': client['outfit']['outfit_type'],
            'outfit_index': client['outfit']['outfit_index'],
            'hair_selected_swatch_id': client.get('hair_selected_swatch_id') if decimal_id(client.get('hair_selected_swatch_id')) else None,
            'hair_identity_known': decimal_id(client.get('hair_selected_swatch_id')),
            'hair_swatch_query': client.get('hair_swatch_query') if isinstance(client.get('hair_swatch_query'), str) else 'unknown',
            'catalog_count': len(client['catalogs']),
            'planned_outfits': [inventory[key] for key in sorted(inventory)]}


def run(state, output, identity, request, sim_id, seconds=60, everyday_second=False, step_seconds=30,
        transport=None, alive=cas_transition.process_alive, monotonic=time.monotonic, pause=time.sleep):
    started = monotonic()
    for label, value, maximum in (('Probe', seconds, 300), ('Native step', step_seconds, 60)):
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= maximum:
            raise ValueError(label + ' wait must be finite, positive and within its bound.')
    if type(everyday_second) is not bool or not decimal_id(sim_id):
        raise ValueError('Use an exact canonical Sim ID and an explicit optional second-outfit flag.')
    deadline = started + seconds
    journal_path, journal, profile, original = reusable_profile.load(state)
    script = next((row['sha256'] for row in journal['artifacts'] if row['name'] == 'ApexOccultHybrid.ts4script'), None)
    if (not isinstance(identity, dict) or type(identity.get('pid')) is not int or not 0 < identity['pid'] <= 0xffffffff or
            identity.get('test_token') != journal['token'] or script is None or identity.get('script_sha256') != script):
        raise ValueError('CAS probe identity does not match the exact disposable journal and script.')
    output = reusable_profile.writable(output)
    if (output.exists() or output.suffix.casefold() != '.json' or not output.parent.is_dir() or output == journal_path or
            any(output == root or root in output.parents for root in (profile, original))):
        raise ValueError('Use one new external JSON proof outside both profiles and the journal.')
    crash_before, _ = cas_transition.read_crash(profile)
    proof = {'schema': 1, 'operation': 'already-open-native-cas-regression', 'ok': False, 'outcome': 'unresolved',
             'identity': identity, 'journal': str(journal_path), 'inputs': journal['artifacts'], 'sim_id': sim_id,
             'seconds': seconds, 'step_seconds': step_seconds, 'steps': [], 'owner_control_requests': [],
             'overlay_suppression': {}, 'standard_categories': list(STANDARD_CATEGORIES),
             'category_coverage': [], 'hair_cycle_verified': False, 'baseline_hair_restored': False,
             'baseline_outfit_restored': False, 'final_status_observed': False, 'final_status': None,
             'everyday_second': {'requested': everyday_second, 'outcome': 'not-requested'},
             'outfit_add_submitted': False, 'cas_changes_accepted': False, 'profile_read_only': True,
             'broad_cas_validation': False, 'available_steps_verified': False, 'complete_probe_verified': False,
             'no_input_replay': True, 'crash_before': crash_before, 'process_exit_verified': False, 'finalized': False,
             'scope': 'Exact swatch/history IDs and existing standard outfit selection; no whole-Sim or headless parity claim.'}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(proof, stream, indent=2, ensure_ascii=False)
    active_step = None
    last_client = None

    def record():
        write_json(output, proof)

    def remaining():
        value = deadline - monotonic()
        if value <= 0:
            raise TimeoutError('CAS runtime probe deadline expired; no operation will be repeated.')
        return value

    def running():
        if not alive(identity['pid']):
            proof['process_exit_verified'] = True
            raise ProcessLookupError('Verified Sims process exited during the native CAS probe.')

    def bounded_pause(value):
        pause(min(value, max(0, deadline - monotonic())))

    def bounded_transport(path, query=None, timeout=12):
        timeout = min(timeout, 2, remaining())
        if path == '/api/native' and isinstance(query, dict):
            proof['owner_control_requests'].append({'action': query.get('action'), 'request_id': query.get('request_id')})
            record()  # Preserve control identity even when hide/show loses its response.
        if path == '/api/command' and isinstance(query, dict) and active_step is not None:
            active_step['owner_requests'].append({'action': query.get('action'), 'request_id': query.get('request_id')})
            record()  # Retain the owner UUID even if the HTTP response never arrives.
        result = transport(path, query, timeout=timeout)
        if path == '/api/bridge' and (not isinstance(result, dict) or any(result.get(field) != identity.get(field)
                for field in ('pid', 'test_token', 'script_sha256'))):
            raise ValueError('Running bridge changed PID/token/script during the pinned CAS probe.')
        return result

    def call(_state, action, sim_id=None, **kwargs):
        running()
        kwargs['seconds'] = min(kwargs.get('seconds', 2), 2, remaining())
        if transport is not None:
            kwargs['transport'] = bounded_transport
        result = request(_state, action, sim_id=sim_id, **kwargs)
        if not isinstance(result, dict):
            raise ValueError('Use a typed game-owned CAS result.')
        if action == 'cas_ui_request' and active_step is not None:
            rid = result.get('cas_request_id')
            if uuid_id(rid):
                active_step.update(cas_request_id=rid, state='submitted')
                record()  # Native UUID is durable before the first result poll.
        if action == 'cas_ui_result' and active_step is not None:
            active_step['poll_count'] += 1
            if result.get('cas_request_id') != kwargs.get('value') or kwargs.get('value') != active_step['cas_request_id']:
                raise ValueError('Native CAS response belongs to a different request UUID.')
        return result

    def step(operation, expected_hair=None, expected_slot=None, **arguments):
        nonlocal active_step, last_client
        running()
        remaining()
        active_step = {'operation': operation, 'arguments': arguments, 'state': 'starting', 'verified': False,
                       'started_seconds': max(0, monotonic() - started), 'cas_request_id': None,
                       'owner_requests': [], 'poll_count': 0}
        proof['steps'].append(active_step)
        if operation == 'outfit-add':
            proof['outfit_add_submitted'] = True
        record()
        args = SimpleNamespace(operation=operation, state=state, sim_id=sim_id, output=None,
                               seconds=min(step_seconds, remaining()), **arguments)
        try:
            result = cas_client.execute(args, call, monotonic=monotonic, pause=bounded_pause)
            active_step['result'] = {key: result[key] for key in
                ('ok', 'outcome', 'cas_request_state', 'message', 'ui_transition_verified', 'request_id', 'request_state') if key in result}
            if (result.get('ok') is not True or result.get('ui_transition_verified') is not True or
                    not uuid_id(result.get('cas_request_id')) or result['cas_request_id'] != active_step['cas_request_id']):
                raise RuntimeError('Native CAS step failed or is unresolved; retain its UUID and do not replay it.')
            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
            from apex_core.cas_ui import validate_client
            contract = dict(arguments, operation=operation)
            client = result.get('client')
            validate_client(client, sim_id, contract)
            if client['sim'].get('simId') != sim_id:
                raise ValueError('Native selected Sim identity is not the exact requested decimal string.')
            observed = summary(client)
            active_step['observed'] = observed
            if expected_hair is not None:
                active_step['expected_hair_swatch_id'] = expected_hair
                if client.get('hair_selected_swatch_id') != expected_hair:
                    raise ValueError('Native history/swatch readback did not match the exact expected hair ID.')
            if expected_slot is not None:
                active_step['expected_outfit'] = {'outfit_type': expected_slot[0], 'outfit_index': expected_slot[1]}
                if (client['outfit']['outfit_type'], client['outfit']['outfit_index']) != expected_slot:
                    raise ValueError('Native step changed the exact selected outfit unexpectedly.')
            running()
            remaining()
            last_client = client
            active_step.update(verified=True, state='completed')
            return client
        except (OSError, ValueError, RuntimeError) as error:
            active_step.update(state='unresolved', error=str(error))
            raise
        finally:
            active_step['elapsed_seconds'] = max(0, monotonic() - started - active_step['started_seconds'])
            record()

    overlay = OverlaySuppression(lambda action: call(state, action), proof['overlay_suppression'], record)
    try:
        running()
        overlay.suppress()
        diagnostic = overlay.wait_idle(seconds=min(3, remaining()), monotonic=monotonic, pause=bounded_pause)
        proof['fresh_exact_sim_peer'] = cas_transition.fresh_peer(diagnostic, sim_id)
        record()
        if not proof['fresh_exact_sim_peer']:
            raise ValueError('Already open CAS has no fresh exact-Sim peer; no CAS entry or fallback submitted.')
        initial = step('status')
        inventory = planned_inventory(initial)
        baseline_slot = (initial['outfit']['outfit_type'], initial['outfit']['outfit_index'])
        baseline = inventory.get(baseline_slot[0])
        if not baseline or baseline['state'] != 'present' or baseline_slot[1] not in baseline['slots'] or baseline_slot[0] > 13:
            raise ValueError('Initial outfit slot lacks exact native planned evidence; no reversible series submitted.')
        original_hair, alternate = swatch_choice(initial)
        proof['original_hair_swatch_id'], proof['alternate_hair_swatch_id'] = original_hair, alternate
        proof['initial_status'] = summary(initial)
        proof['category_coverage'] = [dict(inventory.get(category, {'category': category, 'state': 'unavailable',
            'slots': [], 'max_outfits': None, 'query': None}), verified_slots=[]) for category in STANDARD_CATEGORIES]
        record()
        for operation, expected, arguments in (
                ('hair-swatch', alternate, {'data_id': alternate}), ('undo', original_hair, {}),
                ('redo', alternate, {}), ('undo', original_hair, {})):
            step(operation, expected_hair=expected, expected_slot=baseline_slot, **arguments)
        proof['hair_cycle_verified'] = proof['baseline_hair_restored'] = True
        for coverage in proof['category_coverage']:
            for index in coverage['slots']:
                step('outfit', category=coverage['category'], index=index)
                coverage['verified_slots'].append(index)
                record()
        if everyday_second:
            everyday = planned_inventory(last_client).get(0)
            if everyday and everyday['state'] == 'present' and 1 in everyday['slots']:
                step('outfit', category=0, index=1)
                proof['everyday_second']['outcome'] = 'verified-existing-second'
            elif (everyday and everyday['state'] == 'present' and everyday['slots'] == [0] and
                  everyday['max_outfits'] is not None and 2 <= everyday['max_outfits'] <= 5):
                step('outfit', category=0, index=0)
                created = step('outfit-add', category=0, expected_slot=(0, 1))
                after = planned_inventory(created).get(0)
                if not after or after['slots'] != [0, 1]:
                    raise ValueError('Native creation did not verify exactly the requested Everyday second slot.')
                proof['everyday_second']['outcome'] = 'verified-created-second'
            else:
                proof['everyday_second'].update(outcome='skipped-unavailable',
                    reason='No exact existing second slot or supported one-slot append capacity was returned.')
        if (last_client['outfit']['outfit_type'], last_client['outfit']['outfit_index']) != baseline_slot:
            step('outfit', category=baseline_slot[0], index=baseline_slot[1])
        final = step('status', expected_hair=original_hair, expected_slot=baseline_slot)
        proof.update(baseline_hair_restored=True, baseline_outfit_restored=True,
                     final_status_observed=True, final_status=summary(final), available_steps_verified=True)
        proof['all_standard_categories_tested'] = all(row['verified_slots'] for row in proof['category_coverage'])
        complete = proof['all_standard_categories_tested'] and (not everyday_second or
                   proof['everyday_second']['outcome'] in ('verified-existing-second', 'verified-created-second'))
        proof['ok'] = proof['complete_probe_verified'] = complete
        proof['outcome'] = 'completed' if complete else 'completed-with-skips'
        overlay.restore(True)
    except (OSError, ValueError, RuntimeError) as error:
        proof['ok'] = False
        proof['complete_probe_verified'] = False
        if proof['outcome'] in ('completed', 'completed-with-skips'):
            proof['outcome'] = 'unresolved'
        overlay.restore(False)
        proof['error'] = str(error)
        if last_client is not None:
            proof['last_acknowledged_status'] = summary(last_client)
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
        if proof['crash']['preserved']:
            proof['outcome'] = 'crash'
    proof['elapsed_seconds'] = max(0, monotonic() - started)
    proof['finalized'] = True
    record()
    return {'ok': proof['ok'], 'outcome': proof['outcome'], 'proof': str(output), 'proof_sha256': sha256(output),
            'hair_cycle_verified': proof['hair_cycle_verified'], 'final_status_observed': proof['final_status_observed'],
            'all_standard_categories_tested': proof.get('all_standard_categories_tested', False),
            'available_steps_verified': proof['available_steps_verified'], 'broad_cas_validation': False,
            'outfit_add_submitted': proof['outfit_add_submitted'], 'elapsed_seconds': proof['elapsed_seconds'],
            'message': proof.get('error', 'Native swatch/history IDs and returned existing outfit slots verified.')}


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--state', required=True, type=Path)
    result.add_argument('--sim-id', required=True)
    result.add_argument('--output', required=True, type=Path)
    result.add_argument('--seconds', type=float, default=60)
    result.add_argument('--step-seconds', type=float, default=30)
    result.add_argument('--outfit-add', '--everyday-second', dest='everyday_second', action='store_true',
                        help='Explicitly allow an Everyday second-outfit probe; may append one disposable CAS slot.')
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        identity = apex_cli.verified_identity(args.state)
        result = run(args.state, args.output, identity, apex_cli.owned_request, args.sim_id,
                     seconds=args.seconds, step_seconds=args.step_seconds, everyday_second=args.everyday_second,
                     transport=apex_cli.get)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result['ok'] else 1
    except (OSError, ValueError, RuntimeError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
