"""One semantic existing-Sim CAS acceptance, followed by observed Live proof.

All-lane checkpoints retain raw edits for explicit decisions; actual older CAS
checkpoints keep their guarded legacy finish. No pointer input, save, relaunch
or request replay occurs. Native acceptance and Live proof remain separate.
"""
import json
import hashlib
import math
from pathlib import Path
import sys
import time

import cas_transition
import reusable_profile
from source_manifest import sha256, write_json

SIM_TIME_SOURCE = 'services.time_service().sim_now'
ZONE_CANCELLED_BEFORE_EXECUTION = 'Zone changed before execution; submit against the new zone explicitly.'
WAIT_CANCELLED_BEFORE_EXECUTION = 'Wait expired; command cancelled before execution.'
READINESS_ACTIONS = ('cas_ui_diagnostics', 'cas_ui_result', 'test_snapshot')


def decimal_id(value, zero=False):
    return (isinstance(value, str) and value.isascii() and value.isdecimal() and
            (0 if zero else 1) <= int(value) < 1 << 64 and str(int(value)) == value)


def uuid_id(value):
    return isinstance(value, str) and len(value) == 32 and all(char in '0123456789abcdef' for char in value)


def hash_id(value):
    return isinstance(value, str) and len(value) == 64 and all(char in '0123456789abcdef' for char in value)


def primary_navigation(client, sim_id, household_id, test_token=None, native_view=None, process_id=None):
    """Select the actual base owner of this independently bound portrait pair.

    The legacy UI feed can be incomplete or describe another rendering genus.
    The fresh native pair identifies its real base: shared Human for ordinary
    pairs, Alien for its Human disguise. Legacy layer-select is kept only for
    editors without an independently bound owner controller.
    """
    session = client.get('owner_pair_observation', {}).get('session')
    if type(session) is not int or session <= 0:
        raise ValueError('Alternate-layer return lacks its native session; no layer or accept submitted.')
    navigation = dict(operation='layer-select',household_id=household_id,
                      expected_layer=1,target_layer=0,native_session=session)
    strip = client.get('form_strip')
    if isinstance(strip,dict) and strip.get('native_owner_state') == 'bound':
        if not uuid_id(test_token):
            raise ValueError('Bound hybrid navigation requires the exact disposable token; no request submitted.')
        mask=client.get('sim',{}).get('allOccultTypes')
        groups=strip.get('life_states')
        if (strip.get('sim_id')!=sim_id or strip.get('cross_kind_navigation') is not True or
                type(mask) is not int or not 0<mask<=127 or not mask&1 or strip.get('owned_mask')!=mask or not isinstance(groups,list)):
            raise ValueError('Bound hybrid return lacks its exact current owner graph; no navigation or accept submitted.')
        human=[row for row in groups if isinstance(row,dict) and row.get('family')=='human']
        variants=human[0].get('variants') if len(human)==1 else None
        if (not isinstance(variants,list) or len(variants)!=1 or not isinstance(variants[0],dict) or
                variants[0].get('owner_id') not in ('native/1','active/1')):
            raise ValueError('Bound hybrid return requires its one shared Human owner; no navigation or accept submitted.')
        human=variants[0]['owner_id']
        rendered=client.get('native_context',{}).get('rendered_form',{})
        if (not isinstance(native_view,dict) or native_view.get('ok') is not True or
                native_view.get('scope')!='native-form-view-status' or native_view.get('available') is not True or
                native_view.get('state')!='bound' or type(process_id) is not int or process_id<=0 or
                type(native_view.get('pid')) is not int or native_view.get('pid')!=process_id or native_view.get('sim_id')!=sim_id or
                native_view.get('owner_id')!=strip.get('selected_owner_id') or
                native_view.get('human_owner_id')!=human or type(native_view.get('generation')) is not int or
                native_view['generation']<=0 or type(native_view.get('layer')) is not int or native_view['layer']!=1 or
                type(client.get('sim',{}).get('occultLayer')) is not int or client['sim']['occultLayer']!=1 or
                rendered.get('query')!='returned-value' or type(rendered.get('value')) is not int or
                type(native_view.get('native_kind')) is not int or native_view.get('native_kind')!=rendered['value']):
            raise ValueError('Bound hybrid return requires its fresh native portrait pair; no navigation or accept submitted.')
        pair=native_view.get('portrait_pair')
        if (not isinstance(pair,dict) or pair.get('alternate_owner_id')!=strip['selected_owner_id'] or
                type(pair.get('alternate_kind')) is not int or pair['alternate_kind']!=rendered['value']):
            raise ValueError('Native alternate owner differs from this editor; no navigation or accept submitted.')
        base,kind=pair.get('base_owner_id'),pair.get('base_kind')
        if base==human and type(kind) is int and kind==1 and pair['alternate_owner_id']!=human:
            pass
        elif (pair['alternate_owner_id']==human and pair['alternate_kind']==1 and
                type(kind) is int and kind==2 and mask&2):
            aliens=[row for row in groups if isinstance(row,dict) and row.get('family')=='alien']
            choices=aliens[0].get('variants') if len(aliens)==1 else None
            if (not isinstance(choices,list) or len(choices)!=1 or not isinstance(choices[0],dict) or
                    choices[0].get('owner_id')!=base or base not in ('native/2','active/2')):
                raise ValueError('Alien disguise return lacks its exact Alien base owner; no navigation or accept submitted.')
        else:
            raise ValueError('Native portrait orientation is not qualified; no navigation or accept submitted.')
        navigation=dict(operation='form-owner-select',owner_id=base,native_kind=kind,
                        owned_mask=mask,household_id=household_id,expected_layer=1,native_session=session,test_token=test_token)
    return navigation


def cancelled_read(result):
    return (isinstance(result, dict) and
            set(result) == {'ok', 'request_state', 'message', 'request_id'} and
            result.get('ok') is False and result.get('request_state') == 'cancelled' and
            result.get('message') in (ZONE_CANCELLED_BEFORE_EXECUTION, WAIT_CANCELLED_BEFORE_EXECUTION) and
            uuid_id(result.get('request_id')))


def cancelled_snapshot(result):
    return cancelled_read(result) and result['message'] == ZONE_CANCELLED_BEFORE_EXECUTION


def resume_intent(path, digest, profile, original, identity, journal, sim_id, household_id, settle_ticks):
    """Resume observation of an acknowledged intent, never its native action."""
    if path is None and digest is None:
        return None
    from cas_bank_cli import _intent_file
    prior = _intent_file(path, digest, profile, original, limit=16 * 1024 * 1024)
    if (not isinstance(prior, dict) or prior.get('operation') != 'semantic-cas-return-to-live' or
            prior.get('ok') is not False or prior.get('outcome') != 'unresolved' or
            not isinstance(prior.get('identity'), dict) or
            any(prior['identity'].get(key) != identity.get(key)
                for key in ('pid', 'test_token', 'script_sha256', 'profile', 'build_version')) or
            prior.get('inputs') != journal['artifacts'] or
            prior.get('sim_id') != sim_id or prior.get('household_id') != household_id or
            prior.get('settle_ticks') != settle_ticks or prior.get('accept_submitted') is not True or
            prior.get('accept_submission_attempted') is not True or prior.get('accept_intent_observed') is not True or
            not uuid_id(prior.get('cas_request_id')) or
            prior.get('native_commit_outcome') not in ('unobserved', 'unresolved') or
            any(prior.get(key) for key in ('play_attempted', 'form_bank_finish_attempted', 'cas_bank_observe_attempted',
                'return_metadata_completed', 'return_metadata_observations', 'pause_observations',
                'process_exit_verified', 'clock_progress_verified', 'live_context_verified'))):
        raise ValueError('Resume requires the exact acknowledged CAS intent before any Live settling or bank action.')
    intent = prior.get('accept_intent')
    if (not isinstance(intent, dict) or intent.get('ok') is not True or
            intent.get('cas_request_id') != prior['cas_request_id'] or
            intent.get('lifecycle_stage') != 'accept-intent' or intent.get('commit_submitted') is not False or
            intent.get('ui_transition_verified', False) is not False):
        raise ValueError('Retained CAS proof lacks its exact acknowledged native accept intent.')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
    from apex_core.cas_ui import validate_client
    validate_client(intent.get('client'), sim_id, {'operation': 'accept', 'household_id': household_id})
    if intent['client']['sim']['householdId'] != household_id:
        raise ValueError('Retained CAS intent belongs to another household.')
    return prior


def native_live_context(snapshot, sim_id, household_id):
    """Exact native presence, including historical identity evidence only.

    This does not establish the tick origin or simulation progress. Historical
    crash/archive receipts may retain it without certifying a fresh CAS return.
    """
    if not isinstance(snapshot, dict):
        return False
    sim, queries = snapshot.get('sim'), snapshot.get('runtime_queries')
    return (snapshot.get('ok') is True and snapshot.get('in_build_buy') is False and
            snapshot.get('zone_running') is True and snapshot.get('household_id') == household_id and
            isinstance(sim, dict) and sim.get('id') == sim_id and sim.get('instanced') is True and
            isinstance(queries, dict) and all(queries.get(field) == 'returned-value'
                for field in ('client_id', 'zone_running', 'sim_now_ticks')) and
            all(decimal_id(snapshot.get(field)) for field in ('client_id', 'zone_id', 'save_guid')) and
            decimal_id(snapshot.get('sim_now_ticks'), zero=True) and
            type(snapshot.get('clock_speed')) is int and snapshot['clock_speed'] in (0, 1, 2, 3))


def live_snapshot(snapshot, sim_id, household_id):
    """Current Live proof additionally requires actual simulation-time origin."""
    return (native_live_context(snapshot, sim_id, household_id) and
            snapshot.get('sim_time_source') == SIM_TIME_SOURCE)


def observe(state, output, identity, request, sim_id, household_id, seconds=60, settle_ticks=30,
            transport=None, alive=cas_transition.process_alive, monotonic=time.monotonic, pause=time.sleep,
            resume_proof=None, resume_sha256=None):
    from cli_identity_cache import session
    with session(state):
        return _observe(state, output, identity, request, sim_id, household_id, seconds, settle_ticks,
                        transport, alive, monotonic, pause, resume_proof, resume_sha256)


def _observe(state, output, identity, request, sim_id, household_id, seconds=60, settle_ticks=30,
             transport=None, alive=cas_transition.process_alive, monotonic=time.monotonic, pause=time.sleep,
             resume_proof=None, resume_sha256=None):
    started = monotonic()
    if (type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 120 or
            type(settle_ticks) is not int or not 1 <= settle_ticks <= 6000 or
            not decimal_id(sim_id) or not decimal_id(household_id)):
        raise ValueError('Use exact Sim/household identities, a bounded timeout and positive native settle ticks.')
    deadline = started + seconds
    cleanup_reserve = min(4, seconds / 3)
    journal_path, journal, profile, original = reusable_profile.load(state)
    script = next((row['sha256'] for row in journal['artifacts'] if row['name'] == 'ApexOccultHybrid.ts4script'), None)
    if (not isinstance(identity, dict) or type(identity.get('pid')) is not int or not 0 < identity['pid'] <= 0xffffffff or
            identity.get('test_token') != journal['token'] or script is None or identity.get('script_sha256') != script):
        raise ValueError('CAS return identity differs from the exact disposable journal and installed script.')
    if identity.get('profile') is not None and Path(identity['profile']).resolve() != profile:
        raise ValueError('CAS return bridge belongs to a different disposable profile.')
    resumed = resume_intent(resume_proof, resume_sha256, profile, original, identity, journal,
                            sim_id, household_id, settle_ticks)
    output = reusable_profile.writable(output)
    if (output.exists() or output.suffix.casefold() != '.json' or not output.parent.is_dir() or output == journal_path or
            any(output == root or root in output.parents for root in (profile, original))):
        raise ValueError('Use one new external JSON CAS return proof outside both profiles and the journal.')
    if transport is None:
        from apex_cli import get
        transport = get
    crash_before, _ = cas_transition.read_crash(profile)
    proof = {'schema': 1, 'operation': 'semantic-cas-return-to-live', 'ok': False, 'outcome': 'unresolved',
             'identity': identity, 'journal': str(journal_path), 'inputs': journal['artifacts'],
             'sim_id': sim_id, 'household_id': household_id, 'seconds': seconds, 'settle_ticks': settle_ticks,
             'steps': [], 'owner_requests': [], 'cas_request_id': None, 'accept_submitted': False,
             'accept_submission_attempted': False,
             'preflight_request_id': None,
             'accept_intent_observed': False, 'cas_peer_disappearance_verified': False,
             'live_context_verified': False, 'clock_progress_verified': False, 'final_paused': False,
             'return_metadata_completed': False, 'ui_transition_verified': False,
             'return_metadata_observations': [], 'return_metadata_rebound_attempted': False,
             'return_metadata_rebound_verified': False,
             'pause_observations': [], 'pause_rebound_attempted': False,
             'pause_rebound_verified': False,
             'form_bank_finish_attempted': False, 'form_bank_completion_verified': False,
             'cas_bank_observe_attempted': False, 'cas_bank_observe_request_id': None,
             'cas_bank_observe_status_poll_count': 0,
             'cas_bank_observation_verified': False, 'cas_explicit_decisions_required': False,
             'cas_transaction_phase': None,
             'native_commit_submission_verified': False, 'appearance_persistence_verified': False,
             'native_commit_outcome': 'unobserved',
             'save_reload_verified': False, 'process_exit_verified': False, 'profile_read_only': True,
             'input_submitted': False, 'no_input_replay': True, 'crash_before': crash_before}
    proof['overlay_suppression'] = {}
    if resumed is not None:
        proof.update(cas_request_id=resumed['cas_request_id'], accept_submitted=True,
                     accept_submission_attempted=True, accept_intent_observed=True,
                     accept_intent=resumed['accept_intent'], accept_replayed=False,
                     resumed_from={'proof': str(Path(resume_proof).resolve()), 'sha256': resume_sha256,
                                   'owner_requests': resumed.get('owner_requests', [])})
    with output.open('x', encoding='utf-8') as stream:
        json.dump(proof, stream, ensure_ascii=False, indent=2)
    play_attempted = pause_attempted = False
    baseline = None
    active_metadata_intent = None
    active_pause_intent = None

    def save():
        write_json(output, proof)

    def remaining(reserve=False):
        value = deadline - monotonic() - (cleanup_reserve if reserve else 0)
        if value <= 0:
            raise TimeoutError('CAS return observation deadline expired; retain all request identities.')
        return value

    def running():
        if not alive(identity['pid']):
            proof['process_exit_verified'] = True
            raise ProcessLookupError('Verified Sims process exited during CAS return.')

    def record(action, result):
        retained = result
        if action == 'cas_ui_result' and proof['accept_intent_observed'] and isinstance(result, dict):
            # Retain the complete first intent once. Repeated read-only checks
            # keep its exact identity/outcome and content digest, rather than
            # multiplying every full CAS catalog in the bounded wait journal.
            retained = {key: result.get(key) for key in ('ok', 'outcome', 'cas_request_id',
                        'lifecycle_stage', 'commit_submitted', 'commit_attempted', 'commit_accepted', 'commit_outcome',
                        'ui_transition_verified', 'cas_request_state', 'message')}
            retained['receipt_sha256'] = hashlib.sha256(json.dumps(result, sort_keys=True,
                        ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()
        proof['steps'].append({'action': action, 'elapsed_seconds': max(0, monotonic() - started), 'result': retained})
        save()
        return result

    def pinned_transport(path, query=None, timeout=12):
        # Native visibility/status controls can wait for a renderer-owned
        # boundary. Keep their normal bounded call budget; a two-second owner
        # polling interval is not a native completion deadline.
        timeout = min(timeout, 12 if path == '/api/native' else 2, remaining())
        if path in ('/api/command', '/api/native') and isinstance(query, dict):
            proof['owner_requests'].append({'action': query.get('action'), 'request_id': query.get('request_id')})
            if query.get('action') == 'test_cas_return_observed':
                if (active_metadata_intent is None or active_metadata_intent['owner_request_id'] is not None or
                        not uuid_id(query.get('request_id'))):
                    raise ValueError('CAS return metadata requires one retained owner UUID before transport.')
                active_metadata_intent['owner_request_id'] = query['request_id']
            if query.get('action') == 'test_pause':
                if (active_pause_intent is None or active_pause_intent['owner_request_id'] is not None or
                        not uuid_id(query.get('request_id'))):
                    raise ValueError('CAS pause requires one retained owner UUID before transport.')
                active_pause_intent['owner_request_id'] = query['request_id']
            if query.get('action') == 'cas_bank_observe':
                if proof['cas_bank_observe_request_id'] is not None:
                    raise RuntimeError('CAS raw observation already has a submitted UUID; replay is forbidden.')
                if not uuid_id(query.get('request_id')):
                    raise ValueError('CAS raw observation requires its exact original owner UUID before transport.')
                proof['cas_bank_observe_request_id'] = query['request_id']
            save()  # Persist the owner UUID before the first network write.
        try:
            result = transport(path, query, timeout=timeout)
        except OSError as error:
            if active_metadata_intent is not None:
                active_metadata_intent['transport_error'] = str(error)
                save()
            raise
        if path == '/api/bridge' and (not isinstance(result, dict) or any(
                result.get(field) != identity.get(field) for field in ('pid', 'test_token', 'script_sha256'))):
            raise ValueError('CAS return bridge changed PID/token/script; no further action permitted.')
        return result

    def observe_bank_owner(result):
        """Observe the retained raw-capture UUID through the whole deadline."""
        request_id = proof['cas_bank_observe_request_id']
        if (not uuid_id(request_id) or result.get('request_id') != request_id):
            raise ValueError('CAS raw observation lacks its exact retained original owner UUID; no replay allowed.')
        while True:
            running()
            remaining()
            try:
                # Each status read remains bound to this runtime. This is an
                # observational bridge read, never another owner command.
                pinned_transport('/api/bridge')
                running()
                remaining()
                row = pinned_transport('/api/requests/status', {'request_id': request_id})
            except OSError as error:
                record('observe-owner:cas_bank_observe', {'ok': False, 'request_id': request_id,
                    'response_lost_or_failed': True, 'error': str(error)})
                pause(min(.25, remaining()))
                continue
            proof['cas_bank_observe_status_poll_count'] += 1
            record('observe-owner:cas_bank_observe', row)
            remaining()  # A late receipt cannot authorize an expired intent.
            running()
            if (not isinstance(row, dict) or row.get('request_id') != request_id or
                    row.get('state') not in ('pending', 'running', 'unknown', 'completed', 'failed', 'cancelled')):
                raise ValueError('CAS raw observation status is untyped or belongs to another owner UUID.')
            if row['state'] in ('completed', 'failed', 'cancelled'):
                terminal = row.get('result')
                if (not isinstance(terminal, dict) or type(terminal.get('ok')) is not bool or
                        'request_id' in terminal and terminal['request_id'] != request_id):
                    raise ValueError('CAS raw observation terminal result is untyped or has a different owner UUID.')
                return dict(terminal, request_id=request_id, request_state=row['state'],
                            ok=terminal['ok'] if row['state'] == 'completed' else False)
            pause(min(.25, remaining()))

    def call(action, value=None, metadata_intent=None):
        nonlocal active_metadata_intent
        running()
        try:
            active_metadata_intent = metadata_intent
            result = request(state, action, sim_id=sim_id, value=value,
                             seconds=min(2, remaining()), transport=pinned_transport)
        except (OSError, ValueError, RuntimeError) as error:
            record(action, {'ok': False, 'response_lost_or_failed': True, 'error': str(error)})
            if (action != 'cas_bank_observe' or not isinstance(error, OSError) or
                    not uuid_id(proof['cas_bank_observe_request_id'])):
                raise
            # The command UUID was persisted before transport. Response loss
            # permits only read-only observation of that existing identity.
            result = {'ok': False, 'outcome': 'unresolved', 'request_state': 'unknown',
                      'request_id': proof['cas_bank_observe_request_id'], 'transport_error': str(error)}
        finally:
            active_metadata_intent = None
        record(action, result)
        if not isinstance(result, dict):
            raise ValueError('CAS return requires a typed game-owned result.')
        if (action == 'cas_bank_observe' and
                (result.get('request_state') in ('pending', 'running', 'unknown') or
                 result.get('outcome') == 'unresolved') and
                result.get('request_state') not in ('completed', 'failed', 'cancelled')):
            result = observe_bank_owner(result)
            record('completed-owner:cas_bank_observe', result)
        while action in READINESS_ACTIONS:
            # The exact read UUID remains owned until terminal. A zone change
            # can certify that it never executed; only then submit a fresh read.
            from apex_cli import poll_request
            while (result.get('outcome') == 'unresolved' or
                   result.get('request_state') in ('pending', 'running', 'unknown')):
                request_id = result.get('request_id')
                if not uuid_id(request_id):
                    raise ValueError('Readiness observation lacks its retained owner UUID.')
                running(); pinned_transport('/api/bridge')
                result = poll_request(request_id, seconds=min(2, remaining()),
                                      transport=pinned_transport, monotonic=monotonic,
                                      pause=lambda value: pause(min(value, remaining())))
                if result.get('request_id') != request_id:
                    raise ValueError('Readiness observation returned a different owner UUID.')
                record('observe-owner:' + action, result)
            if not cancelled_read(result):
                break
            remaining(); running(); pinned_transport('/api/bridge')
            result = request(state, action, sim_id=sim_id, value=value,
                             seconds=min(2, remaining()), transport=pinned_transport)
            record('reobserve-cancelled-live-snapshot' if action == 'test_snapshot' else
                   'reobserve-cancelled:' + action, result)
            if not isinstance(result, dict):
                raise ValueError('Readiness reobservation requires a typed game-owned result.')
        return result

    def wait():
        pause(min(.2, remaining(reserve=True)))

    def guard_value(value=None):
        return json.dumps({'test_token': journal['token'], 'value': value})

    def observation_value(phase):
        return guard_value({'cas_request_id': proof['cas_request_id'], 'phase': phase,
                            'household_id': household_id, 'minimum_ticks': settle_ticks})

    def same_live(snapshot):
        if not live_snapshot(snapshot, sim_id, household_id):
            raise ValueError('Exact native Sim/household/client/running-zone context and simulation timeline origin are unavailable.')
        if baseline is not None and any(snapshot.get(key) != baseline[key]
                for key in ('client_id', 'zone_id', 'save_guid', 'household_id', 'sim_time_source')):
            raise ValueError('Native Live identity changed during CAS return settling.')

    def metadata_observation(phase, rebound_of=None):
        """One metadata command; a certified unexecuted completion may rebind once."""
        remaining()
        intent = {'cas_request_id': proof['cas_request_id'], 'phase': phase,
                  'household_id': household_id, 'minimum_ticks': settle_ticks,
                  'owner_request_id': None, 'rebound_of': rebound_of,
                  'submission_attempted': True}
        proof['return_metadata_observations'].append(intent)
        save()  # Preserve this intent before any network write.
        result = call('test_cas_return_observed', observation_value(phase), metadata_intent=intent)
        intent['result'] = result
        save()
        remaining()  # A late receipt cannot authorize an expired rebound.
        if (rebound_of is not None and (not uuid_id(intent['owner_request_id']) or
                result.get('request_id') != intent['owner_request_id'] or
                result.get('request_state') != 'completed' or result.get('ok') is not True)):
            raise RuntimeError('The explicitly rebound metadata observation has no exact completed owner receipt; do not repeat it.')
        if (phase != 'complete' or rebound_of is not None or
                set(result) != {'ok', 'request_state', 'message', 'request_id'} or
                'transport_error' in intent or
                result.get('ok') is not False or result.get('request_state') != 'cancelled' or
                result.get('message') != ZONE_CANCELLED_BEFORE_EXECUTION or
                not uuid_id(intent['owner_request_id']) or result.get('request_id') != intent['owner_request_id']):
            return result
        if (proof['return_metadata_rebound_attempted'] or baseline is None or
                proof['clock_progress_verified'] is not True or proof['final_paused'] is not True):
            raise ValueError('Cancelled CAS metadata completion has no verified retained baseline/progress/Pause authority.')
        running()
        remaining()
        bridge = record('metadata-rebound:fresh-bridge', pinned_transport('/api/bridge'))
        if (bridge.get('ok') is not True or bridge.get('alarm_ready') is not True or
                bridge.get('core_tick_ready') is not True):
            raise ValueError('Cancelled CAS metadata completion requires a fresh ready pinned bridge.')
        snapshot = call('test_snapshot', guard_value())
        same_live(snapshot)
        if (snapshot.get('request_state') in ('pending', 'running', 'unknown', 'failed', 'cancelled', 'rejected') or
                snapshot.get('outcome') == 'unresolved' or snapshot.get('clock_speed') != 0 or
                int(snapshot['sim_now_ticks']) - int(baseline['sim_now_ticks']) < settle_ticks):
            raise ValueError('Cancelled CAS metadata completion requires fresh native Pause and simulation progress.')
        running()
        remaining()
        final_bridge = record('metadata-rebound:confirmed-bridge', pinned_transport('/api/bridge'))
        if (final_bridge.get('ok') is not True or final_bridge.get('alarm_ready') is not True or
                final_bridge.get('core_tick_ready') is not True):
            raise ValueError('Cancelled CAS metadata completion bridge readiness changed before the rebound.')
        remaining()
        proof['return_metadata_rebound_preflight'] = {'cancelled_owner_request_id': intent['owner_request_id'],
            'cancellation': result, 'bridge': bridge, 'confirmed_bridge': final_bridge, 'snapshot': snapshot}
        proof['return_metadata_rebound_attempted'] = True
        save()  # Cancellation, fresh context and one-shot decision precede the new UUID.
        return metadata_observation(phase, rebound_of=intent['owner_request_id'])

    def reject_native(receipt):
        proof['outcome'] = 'accept-rejected'
        proof['native_failure_receipt'] = receipt
        native_error = receipt.get('message') if isinstance(receipt.get('message'), str) else 'No native error message returned.'
        if receipt.get('commit_attempted') is False:
            proof['native_commit_outcome'] = 'not-attempted'
            raise RuntimeError('Native CAS precommit failed before SaveAndExitCAS: ' + native_error)
        if receipt.get('commit_attempted') is True and receipt.get('commit_accepted') is False:
            proof['native_commit_outcome'] = 'rejected'
            raise RuntimeError('Native SaveAndExitCAS returned false on its one attempt: ' + native_error)
        raise RuntimeError('Native CAS acceptance failed without a verified commit-attempt classification: ' + native_error)

    def pause_once():
        nonlocal pause_attempted, active_pause_intent
        pause_attempted = True
        proof['pause_attempted'] = True
        save()
        def submit(rebound_of=None):
            nonlocal active_pause_intent
            intent = {'owner_request_id': None, 'rebound_of': rebound_of,
                      'submission_attempted': True}
            proof['pause_observations'].append(intent)
            active_pause_intent = intent
            save()
            try:
                result = call('test_pause', guard_value())
            finally:
                active_pause_intent = None
            intent['result'] = result
            save()
            return result, intent
        paused, intent = submit()
        if (set(paused) == {'ok', 'request_state', 'message', 'request_id'} and
                paused.get('ok') is False and paused.get('request_state') == 'cancelled' and
                paused.get('message') == ZONE_CANCELLED_BEFORE_EXECUTION and
                uuid_id(intent['owner_request_id']) and paused.get('request_id') == intent['owner_request_id']):
            # The native queue certifies that the original command never ran.
            # A fresh exact Live read may authorize ONE new-zone submission;
            # ambiguous, lost, failed or second cancellations remain retained.
            remaining(); running(); pinned_transport('/api/bridge')
            fresh = call('test_snapshot', guard_value())
            same_live(fresh)
            if (baseline is None or proof['clock_progress_verified'] is not True or
                    int(fresh['sim_now_ticks']) - int(baseline['sim_now_ticks']) < settle_ticks):
                raise ValueError('Cancelled pause lacks exact retained Live progress authority.')
            pinned_transport('/api/bridge'); running(); remaining()
            proof['pause_rebound_preflight'] = {'cancellation': paused, 'snapshot': fresh}
            save()
            if fresh['clock_speed'] == 0:
                paused = fresh  # Independently observed Pause needs no mutation.
            else:
                proof['pause_rebound_attempted'] = True
                save()
                paused, rebound = submit(intent['owner_request_id'])
                remaining()
                if (paused.get('ok') is not True or paused.get('request_state') != 'completed' or
                        not uuid_id(rebound['owner_request_id']) or
                        paused.get('request_id') != rebound['owner_request_id']):
                    raise RuntimeError('Explicitly rebound pause is unresolved; no third submission permitted.')
                proof['pause_rebound_verified'] = True
        same_live(paused)
        if paused.get('ok') is not True or paused.get('clock_speed') != 0:
            raise RuntimeError('Native paused readback was not verified; no pause replay submitted.')
        proof['final_paused'] = True
        save()
        return paused

    def explicit_bank_return(bank):
        """Retain raw returns once; never classify or commit the user's edits."""
        transaction = bank.get('cas_transaction')
        proof['form_bank_status'] = bank
        proof['outcome'] = 'live-return-bank-unresolved'
        save()
        if (not isinstance(transaction, dict) or transaction.get('ok') is not True or
                transaction.get('current_runtime') is not True or
                not hash_id(transaction.get('expected_pending_sha256')) or
                not hash_id(transaction.get('checkpoint_sha256')) or
                transaction.get('writer_lease_present') is not False):
            raise ValueError('Live returned but the exact current-runtime CAS checkpoint is unavailable; retained states were not replayed.')
        phase = transaction.get('phase')
        proof['cas_transaction_phase'] = phase
        proof['expected_pending_sha256'] = transaction['expected_pending_sha256']
        proof['checkpoint_sha256'] = transaction['checkpoint_sha256']
        save()
        if phase == 'captured':
            if (bank.get('pending_schema') != 2 or bank.get('pending_state') != 'captured' or
                    transaction.get('native_write_possible') is not False or
                    transaction.get('native_write_attempted') is not False or
                    transaction.get('metadata_commit_persisted') is not False):
                raise ValueError('Captured CAS checkpoint has an ambiguous write/commit state; raw observation was not repeated.')
            proof.update(cas_bank_observe_attempted=True,
                         outcome='live-return-cas-observation-unresolved')
            save()
            observed = call('cas_bank_observe', json.dumps({
                'expected_pending_sha256': transaction['expected_pending_sha256']}))
            proof['cas_bank_observation_receipt'] = observed
            proof['cas_bank_observation_receipt_sha256'] = hashlib.sha256(json.dumps(observed,
                sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')).hexdigest()
            save()
            if (observed.get('ok') is not True or
                    observed.get('request_id') != proof['cas_bank_observe_request_id'] or
                    observed.get('expected_pending_sha256') != transaction['expected_pending_sha256'] or
                    observed.get('checkpoint_sha256') != transaction['checkpoint_sha256'] or
                    not hash_id(observed.get('raw_return_sha256')) or not hash_id(observed.get('journal_sha256')) or
                    observed.get('native_write_attempted') is not False or observed.get('bank_committed') is True or
                    observed.get('request_state') in ('pending', 'running', 'unknown') or
                    observed.get('outcome') == 'unresolved'):
                raise RuntimeError('The one raw CAS return observation is unresolved; retain its original UUID without replay.')
            checked = call('cas_session_status')
            current = checked.get('cas_transaction')
            proof['form_bank_status'] = checked
            save()
            if (checked.get('ok') is not True or checked.get('request_state') in ('pending', 'running', 'unknown') or
                    checked.get('outcome') == 'unresolved' or not isinstance(current, dict) or current.get('ok') is not True or
                    current.get('phase') != 'observed' or current.get('current_runtime') is not True or
                    current.get('writer_lease_present') is not False or
                    current.get('expected_pending_sha256') != transaction['expected_pending_sha256'] or
                    current.get('checkpoint_sha256') != transaction['checkpoint_sha256'] or
                    current.get('raw_return_sha256') != observed['raw_return_sha256'] or
                    current.get('native_write_possible') is not False or current.get('native_write_attempted') is not False or
                    current.get('metadata_commit_persisted') is not False):
                raise RuntimeError('Raw CAS observation was returned but its exact retained journal status did not verify; no observer replay.')
            transaction = current
            proof.update(cas_bank_observation_verified=True, cas_transaction_phase='observed',
                         raw_return_sha256=observed['raw_return_sha256'], journal_sha256=observed['journal_sha256'])
        elif phase in ('observed', 'planned'):
            if (not hash_id(transaction.get('raw_return_sha256')) or
                    transaction.get('native_write_possible') is not False or transaction.get('native_write_attempted') is not False or
                    transaction.get('metadata_commit_persisted') is not False or
                    phase == 'planned' and not hash_id(transaction.get('plan_sha256'))):
                raise ValueError('Retained CAS plan/observation lacks exact idle evidence; it was not replayed.')
            proof['raw_return_sha256'] = transaction['raw_return_sha256']
            if phase == 'planned':
                proof['plan_sha256'] = transaction['plan_sha256']
        else:
            raise RuntimeError('Retained CAS transaction is ' + str(phase) + '; inspect its recovery evidence, without observation or finish replay.')
        for name in ('changed_lanes', 'changed_lane_summary', 'native_owner_lanes',
                     'lane_change_evidence', 'lane_change_evidence_available', 'evidence_establishes_edit_intent',
                     'original_active_lane', 'returned_active_lane'):
            if name in transaction:
                proof[name] = transaction[name]
        proof.update(ok=False, outcome='live-return-explicit-cas-decisions-required',
                     cas_explicit_decisions_required=True, form_bank_completion_verified=False)
        proof['message'] = ('Exact Sim returned to Live, advanced native ticks and remains paused. '
                            'Raw CAS edits are retained; explicit per-form accept/restore decisions and commit remain required.')
        save()

    from cas_runtime_probe import OverlaySuppression
    overlay = OverlaySuppression(call, evidence=proof['overlay_suppression'], record=save)
    try:
        running()
        remaining(reserve=True)
        if resumed is None:
            overlay.suppress()
            diagnostic = overlay.wait_idle(seconds=min(3, remaining(reserve=True)), monotonic=monotonic,
                                           pause=lambda value: pause(min(value, remaining(reserve=True))))
            if not cas_transition.fresh_peer(diagnostic, sim_id):
                raise ValueError('No fresh exact-Sim native CAS peer; acceptance was not submitted.')
            # One read-only native inventory proves the requested household/context
            # before any commit intent is queued. Its own UUID is also never replayed.
            preflight = call('cas_ui_request', json.dumps({'operation': 'status'}))
            preflight_id = preflight.get('cas_request_id')
            if not uuid_id(preflight_id):
                raise RuntimeError('Native preflight UUID was not observed; no accept intent submitted.')
            proof['preflight_request_id'] = preflight_id
            save()
            while True:
                remaining(reserve=True)
                preflight = call('cas_ui_result', preflight_id)
                if preflight.get('cas_request_id') != preflight_id:
                    raise ValueError('Native preflight receipt belongs to another request UUID.')
                if preflight.get('outcome') != 'pending-client':
                    break
                wait()
            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
            from apex_core.cas_ui import validate_client, validate_accept_context
            if preflight.get('ok') is not True or preflight.get('ui_transition_verified') is not True:
                raise RuntimeError('Complete native preflight was not acknowledged; no accept intent submitted.')
            validate_client(preflight.get('client'), sim_id, {'operation': 'status'})
            if preflight['client']['sim']['householdId'] != household_id:
                raise ValueError('Requested household differs from native CAS; no accept intent submitted.')
            if preflight['client']['sim'].get('occultLayer') == 1:
                native = preflight['client']
                view = None
                if native.get('form_strip',{}).get('native_owner_state')=='bound':
                    view=call('test_native_cas_engine',json.dumps(dict(test_token=journal['token'],
                        value={'operation':'view-status'})))
                    # A native read can outlast the socket's three-second
                    # preflight lease. Refresh only status before the one
                    # navigation submission; never relax or extend that lease.
                    from cas_client import _submit_status
                    from types import SimpleNamespace
                    def refresh_read(_state,action,*values,**options):
                        if action not in ('cas_ui_request','cas_ui_diagnostics'):
                            raise ValueError('Portrait refresh may only observe the native socket.')
                        return call(action,options.get('value'))
                    refreshed=_submit_status(SimpleNamespace(state=state,sim_id=sim_id,
                        seconds=min(12,remaining(reserve=True))),refresh_read,monotonic,
                        lambda value:pause(min(value,remaining(reserve=True))))
                    refreshed_id=refreshed.get('cas_request_id')
                    if not uuid_id(refreshed_id):
                        raise RuntimeError('Portrait-pair status UUID was not observed; no navigation or accept submitted.')
                    proof['primary_pair_preflight_request_id']=refreshed_id;save()
                    while True:
                        remaining(reserve=True)
                        refreshed=call('cas_ui_result',refreshed_id)
                        if refreshed.get('cas_request_id')!=refreshed_id:
                            raise ValueError('Portrait-pair status has a different UUID; no navigation or accept submitted.')
                        if refreshed.get('outcome')!='pending-client':break
                        wait()
                    if refreshed.get('ok') is not True or refreshed.get('ui_transition_verified') is not True:
                        raise RuntimeError('Portrait-pair status remains unacknowledged; no navigation or accept submitted.')
                    validate_client(refreshed.get('client'),sim_id,{'operation':'status'})
                    native=refreshed['client']
                    if native['sim']['householdId']!=household_id:
                        raise ValueError('Portrait-pair refresh changed households; no navigation or accept submitted.')
                navigation = primary_navigation(native,sim_id,household_id,journal['token'],view,identity['pid'])
                from apex_core.cas_ui import envelope
                envelope(sim_id, navigation)
                selected = call('cas_ui_request', json.dumps(navigation))
                selected_id = selected.get('cas_request_id')
                proof['primary_layer_navigation'] = {'cas_request_id': selected_id, 'request': navigation}
                save()
                if not uuid_id(selected_id):
                    raise RuntimeError('Primary-layer navigation UUID was not observed; no accept submitted.')
                while True:
                    remaining(reserve=True)
                    selected = call('cas_ui_result', selected_id)
                    if selected.get('cas_request_id') != selected_id:
                        raise ValueError('Primary-layer reply has a different UUID; no accept submitted.')
                    if selected.get('outcome') != 'pending-client': break
                    wait()
                proof['primary_layer_navigation']['result'] = selected; save()
                if selected.get('ok') is not True or selected.get('ui_transition_verified') is not True:
                    raise RuntimeError('Primary-layer navigation remains unresolved; no accept submitted or layer replayed.')
                validate_client(selected.get('client'), sim_id, {'operation': 'status'})
                preflight = selected
            validate_accept_context(preflight['client'])
            proof['preflight'] = preflight
            save()
            proof['accept_submission_attempted'] = True
            save()
            submitted = call('cas_ui_request', json.dumps({'operation': 'accept', 'household_id': household_id}))
            rid = submitted.get('cas_request_id')
            if not uuid_id(rid):
                raise RuntimeError('CAS acceptance UUID was not observed; retain its owner request and do not repeat.')
            proof['cas_request_id'] = rid
            proof['accept_submitted'] = True
            save()
            while True:
                remaining(reserve=True)
                result = call('cas_ui_result', rid)
                if result.get('cas_request_id') != rid:
                    raise ValueError('CAS acceptance receipt belongs to another request UUID.')
                if result.get('outcome') == 'pending-client':
                    wait()
                    continue
                if result.get('outcome') == 'accept-rejected':
                    reject_native(result)
                intent = result
                if result.get('outcome') == 'accept-unresolved':
                    intent = result.get('accept_intent')
                    proof['native_commit_outcome'] = 'unresolved'
                if (result.get('outcome') not in ('accept-intent', 'accept-unresolved') or
                        result.get('ui_transition_verified') is not False or
                        not isinstance(intent, dict) or intent.get('ok') is not True or
                        intent.get('lifecycle_stage') != 'accept-intent' or intent.get('commit_submitted') is not False or
                        intent.get('cas_request_id') != rid or intent.get('ui_transition_verified', False) is not False):
                    proof['outcome'] = 'accept-rejected' if result.get('outcome') == 'accept-rejected' else 'unresolved'
                    raise RuntimeError('A guarded native precommit accept intent was not observed.')
                validate_client(intent.get('client'), sim_id, {'operation': 'accept', 'household_id': household_id})
                if intent['client']['sim']['householdId'] != household_id:
                    raise ValueError('Native CAS household changed after the read-only preflight.')
                proof['accept_intent'] = intent
                proof['accept_intent_observed'] = True
                save()
                break
        else:
            rid = proof['cas_request_id']
            pinned_transport('/api/bridge')
            retained = call('cas_ui_result', rid)
            if retained.get('cas_request_id') != rid:
                raise ValueError('Retained CAS intent no longer has its exact native UUID.')
            if retained.get('outcome') == 'accept-rejected':
                reject_native(retained)
            if retained.get('outcome') not in ('accept-intent', 'accept-unresolved'):
                raise ValueError('Retained CAS intent changed lifecycle; inspect its receipt without replay.')
            proof['resumed_receipt'] = retained
            save()
        while True:
            remaining(reserve=True)
            diagnostic = call('cas_ui_diagnostics')
            peers = diagnostic.get('native_peers')
            if diagnostic.get('ok') is True and isinstance(peers, list) and not peers:
                proof['cas_peer_disappearance_verified'] = True
                save()
                break
            # Read only the original ID. A later explicit native service refusal
            # must stop this observer while that native peer is still attached.
            receipt = call('cas_ui_result', rid)
            if receipt.get('cas_request_id') != rid:
                raise ValueError('CAS acceptance receipt UUID changed after its intent.')
            if receipt.get('outcome') == 'accept-rejected':
                reject_native(receipt)
            if receipt.get('outcome') == 'accept-unresolved':
                proof['native_commit_outcome'] = 'unresolved'
                save()
            wait()
        while True:
            remaining(reserve=True)
            running()
            bridge = record('fresh-bridge-readiness', pinned_transport('/api/bridge'))
            if bridge.get('ok') is True and bridge.get('alarm_ready') is True and bridge.get('core_tick_ready') is True:
                snapshot = call('test_snapshot', guard_value())
                if live_snapshot(snapshot, sim_id, household_id):
                    proof['live_snapshot'] = snapshot
                    proof['live_context_verified'] = True
                    save()
                    break
            wait()
        observed = metadata_observation('baseline')
        baseline = observed.get('baseline')
        if (observed.get('ok') is not True or observed.get('outcome') != 'live-baseline' or
                observed.get('cas_request_id') != rid or not isinstance(baseline, dict) or
                baseline.get('sim_id') != sim_id or baseline.get('household_id') != household_id or
                baseline.get('minimum_ticks') != settle_ticks or baseline.get('sim_time_source') != SIM_TIME_SOURCE or
                not decimal_id(baseline.get('sim_now_ticks'), zero=True)):
            raise ValueError('Game-owned CAS return baseline and simulation timeline origin were not verified.')
        same_live(snapshot)
        proof['producer_baseline'] = observed
        play_attempted = True
        proof['play_attempted'] = True
        save()
        played = call('test_play', guard_value())
        same_live(played)
        if played.get('clock_speed') != 1:
            raise RuntimeError('Native unpaused speed was not verified; no play replay submitted.')
        while True:
            remaining(reserve=True)
            settled = call('test_snapshot', guard_value())
            same_live(settled)
            advanced = int(settled['sim_now_ticks']) - int(baseline['sim_now_ticks'])
            if advanced >= settle_ticks and settled.get('clock_speed') in (0, 1):
                proof['clock_progress_verified'] = True
                proof['native_pause_after_required_ticks'] = settled.get('clock_speed') == 0
                proof['settled_snapshot'] = settled
                save()
                break
            if settled.get('clock_speed') != 1:
                raise ValueError('Game ceased native normal-speed play before required CAS settling ticks.')
            wait()
        paused = pause_once()
        if int(paused['sim_now_ticks']) - int(baseline['sim_now_ticks']) < settle_ticks:
            raise ValueError('Native simulation timeline regressed before final paused readback.')
        complete = metadata_observation('complete')
        if (complete.get('ok') is not True or complete.get('outcome') != 'live-return' or
                complete.get('cas_request_id') != rid or complete.get('live_return_verified') is not True or
                complete.get('ui_transition_verified') is not True or
                not isinstance(complete.get('baseline'), dict) or not isinstance(complete.get('final'), dict) or
                complete['baseline'].get('sim_time_source') != SIM_TIME_SOURCE or
                complete['final'].get('sim_time_source') != SIM_TIME_SOURCE):
            raise RuntimeError('Live was observed but lifecycle metadata completion remains unresolved; retain its owner UUID.')
        if proof['return_metadata_rebound_attempted']:
            proof['return_metadata_rebound_verified'] = True
        proof.update(ok=True, outcome='live-return', return_metadata_completed=True,
                     ui_transition_verified=True, return_observation=complete)
        running()
        bank = call('cas_session_status')
        proof['form_bank_status_preflight'] = bank
        proof['ok'] = False
        save()
        if bank.get('ok') is not True or bank.get('request_state') in ('pending', 'running', 'unknown') or bank.get('outcome') == 'unresolved':
            proof['outcome'] = 'live-return-bank-unresolved'
            raise RuntimeError('Live returned but retained form-bank status is unresolved; no finish submitted.')
        if bank.get('cas_transaction') is not None or bank.get('pending_schema') == 2:
            explicit_bank_return(bank)
        else:
            # Actual legacy checkpoints retain their existing one-finish path.
            # Schema-2 checkpoints must never fall through to entry-lane inference.
            legacy_schema = bank.get('pending_schema')
            if (bank.get('captured') is not True or bank.get('pending_state') != 'captured' or
                    bank.get('switch_pending') is not False or
                    legacy_schema is not None and (type(legacy_schema) is not int or legacy_schema != 1)):
                proof['outcome'] = 'live-return-bank-unresolved'
                raise ValueError('No actual captured legacy CAS checkpoint was verified; no finish submitted.')
            proof['form_bank_finish_attempted'] = True
            save()
            finished = call('cas_session_finish')
            proof['form_bank_finish_receipt'] = finished
            save()
            if (finished.get('ok') is not True or str(finished.get('lane')) not in ('1', '2', '4', '8', '16', '32', '64')
                    or finished.get('request_state') in ('pending', 'running', 'unknown')):
                raise RuntimeError('Native Live returned, but the one form-bank finish is unresolved; retain its UUID without replay.')
            bank = call('cas_session_status')
            lanes = bank.get('bank_lanes')
            if (bank.get('ok') is not True or bank.get('captured') is not True
                    or bank.get('pending_state') is not None or bank.get('switch_pending') is not False
                    or not isinstance(lanes, list) or not lanes or len(lanes) != len(set(lanes))
                    or any(lane not in ('1', '2', '4', '8', '16', '32', '64') for lane in lanes)
                    or str(finished['lane']) not in lanes or str(bank.get('active_lane')) not in lanes):
                raise RuntimeError('Hybrid bank completion did not verify idle appearance ownership after CAS.')
            proof.update(ok=True, form_bank_completion_verified=True, form_bank_status=bank)
            save()
        try:
            overlay.restore(True)
        except (OSError, ValueError, RuntimeError) as restore_error:
            # Live completion is already independently verified. An ambiguous
            # visibility control is retained separately and never replayed.
            proof['overlay_restore_error'] = str(restore_error)
    except (OSError, ValueError, RuntimeError) as error:
        proof['ok'] = False
        if not proof['return_metadata_completed']:
            proof['ui_transition_verified'] = False
        elif proof['form_bank_finish_attempted'] and not proof['form_bank_completion_verified']:
            proof['outcome'] = 'live-return-bank-unresolved'
        proof['error'] = str(error)
        overlay.restore(False)
        if play_attempted and not pause_attempted:
            try:
                pause_once()
            except (OSError, ValueError, RuntimeError) as pause_error:
                proof['pause_error'] = str(pause_error)
        try:
            running()
        except ProcessLookupError:
            proof['outcome'] = 'process-exited'
        except (OSError, ValueError) as observation_error:
            proof['process_observation_error'] = str(observation_error)
        proof['crash'] = cas_transition.preserve_crash(profile, output, crash_before)
        if proof['crash']['preserved']:
            proof['outcome'] = 'crash'
    proof['elapsed_seconds'] = max(0, monotonic() - started)
    save()
    result = {key: proof[key] for key in ('ok', 'outcome', 'cas_request_id', 'accept_submitted', 'accept_submission_attempted',
                'accept_intent_observed', 'live_context_verified', 'clock_progress_verified', 'final_paused',
                'return_metadata_completed', 'ui_transition_verified', 'process_exit_verified',
                'return_metadata_rebound_attempted', 'return_metadata_rebound_verified',
                'pause_rebound_attempted', 'pause_rebound_verified',
                'form_bank_finish_attempted', 'form_bank_completion_verified',
                'cas_bank_observe_attempted', 'cas_bank_observe_request_id', 'cas_bank_observation_verified',
                'cas_explicit_decisions_required', 'cas_transaction_phase',
            'native_commit_submission_verified', 'native_commit_outcome', 'appearance_persistence_verified', 'save_reload_verified')} | {
                'proof': str(output), 'proof_sha256': sha256(output), 'elapsed_seconds': proof['elapsed_seconds'],
                'message': proof.get('error', proof.get('message', 'Exact Sim returned to running Live, advanced native game ticks and was left paused.'))}
    result.update({key: proof[key] for key in ('expected_pending_sha256', 'checkpoint_sha256',
        'raw_return_sha256', 'journal_sha256', 'plan_sha256', 'changed_lanes',
        'lane_change_evidence_available', 'evidence_establishes_edit_intent') if key in proof})
    return result
