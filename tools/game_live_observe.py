"""Observe a stable paused disposable household without any input or save.

This independent receipt preserves the prior Map Play result. A native scratch
or autosave slot remains distinct from the hash-bound indexed normal save.
"""
import hashlib
import json
from pathlib import Path
import re
import time

import cas_transition
import game_lifecycle
import reusable_profile
from game_load import _save_live_context
from game_map import AUTOSAVE_DRIFT_FILES, _native_click, save_delta
from save_household import read as read_household
from source_manifest import sha256, write_json


def paused_context(snapshot, target, metadata):
    """Native presence and singleton membership; never infer its save slot."""
    _save_live_context(snapshot, target)
    ticks = snapshot.get('sim_now_ticks')
    persistence = snapshot['persistence']
    if (type(snapshot.get('clock_speed')) is not int or snapshot['clock_speed'] != 0 or
            snapshot['zone_id'] != metadata['household']['home_zone_id'] or
            metadata['sim']['zone_id'] != metadata['household']['home_zone_id'] or
            metadata['household']['member_ids'] != [target['sim_id']] or
            persistence.get('household_sim_ids') != [target['sim_id']] or
            persistence.get('persisted_household_sim_ids') != [target['sim_id']] or
            snapshot['runtime_queries'].get('sim_now_ticks') != 'returned-value' or
            not isinstance(ticks, str) or re.fullmatch('(?:0|[1-9][0-9]{0,19})', ticks) is None or
            not 0 <= int(ticks) < 1 << 64):
        raise ValueError('Paused native household, home zone, singleton membership or simulation tick differs.')
    return {key: snapshot[key] for key in ('save_slot', 'save_guid', 'household_id',
        'zone_id', 'client_id', 'clock_speed', 'sim_now_ticks')}


def observe(state, output, identity, request, sim_id, household_id, save_guid,
            slot_id, expected_save_sha256, map_play_proof, map_play_proof_sha256,
            identity_provider=None, alive=cas_transition.process_alive,
            pause=time.sleep, metadata_reader=read_household):
    state_path, journal, profile, original = reusable_profile.load(state)
    if (type(slot_id) is not int or not 0 < slot_id < 0xffffffff or
            any(not isinstance(value, str) or re.fullmatch('[1-9][0-9]{0,19}', value) is None or
                not 0 < int(value) < 1 << 64 for value in (sim_id, household_id, save_guid)) or
            any(not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None
                for value in (expected_save_sha256, map_play_proof_sha256))):
        raise ValueError('Live observation requires exact normal save, household and prerequisite identities.')
    output = reusable_profile.writable(output)
    prior_path = reusable_profile.writable(map_play_proof)
    for path in (output, prior_path):
        if (path == state_path or path.suffix.lower() != '.json' or
                any(path == base or base in path.parents for base in (profile, original))):
            raise ValueError('Use external Live JSON evidence outside both profiles and the journal.')
    if (output.exists() or not output.parent.is_dir() or not prior_path.is_file() or
            prior_path.stat().st_size > 8 * 1024 * 1024):
        raise ValueError('Use a new Live output and one bounded existing prerequisite proof.')
    raw = prior_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != map_play_proof_sha256 or sha256(prior_path) != map_play_proof_sha256:
        raise ValueError('Prior Map Play proof differs from its immutable hash.')
    prior = json.loads(raw.decode('utf-8'), parse_constant=lambda _value:
        (_ for _ in ()).throw(ValueError('Nonfinite Map Play evidence.')))
    keys = ('pid', 'test_token', 'script_sha256')
    target = {'sim_id': sim_id, 'household_id': household_id, 'save_guid': save_guid,
              'slot_id': slot_id, 'file_sha256': expected_save_sha256}
    expected_script = next((row['sha256'] for row in journal['artifacts'] if row['name'] == 'ApexOccultHybrid.ts4script'), None)
    if (not isinstance(identity, dict) or type(identity.get('pid')) is not int or not 0 < identity['pid'] <= 0xffffffff or
            identity.get('test_token') != journal['token'] or identity.get('script_sha256') != expected_script or
            len(journal['artifacts']) != 14 or not isinstance(prior, dict) or
            type(prior.get('schema')) is not int or prior['schema'] != 1 or
            prior.get('operation') != 'play-existing-selected-disposable-household' or
            not isinstance(prior.get('identity'), dict) or any(prior['identity'].get(key) != identity.get(key) for key in keys) or
            prior.get('inputs') != journal['artifacts'] or prior.get('target') != target or
            prior.get('play_input_accepted') is not True or prior.get('input_replay_attempted') is not False or
            prior.get('save_requested') is not False or prior.get('save_file_written') is not False):
        raise ValueError('Map Play prerequisite differs from the exact current runtime, target or no-save scope.')
    baseline = prior.get('after_saves')
    previous = prior.get('before_saves')
    if (not isinstance(baseline, dict) or not isinstance(previous, dict) or
            len(baseline) != 18 or set(previous) != set(baseline) or
            any(row['name'] not in AUTOSAVE_DRIFT_FILES for row in save_delta(previous, baseline))):
        raise ValueError('Prior Map Play save family changed outside the retained disposable autosaves.')
    before = game_lifecycle.all_save_files(profile)
    filename = 'Slot_{:08x}.save'.format(slot_id)
    if before != baseline or before.get(filename, {}).get('sha256') != expected_save_sha256:
        raise ValueError('Current eighteen-file family differs from the retained Map Play baseline.')
    metadata = metadata_reader(profile / 'saves' / filename, expected_save_sha256, household_id, sim_id)
    if (not isinstance(metadata, dict) or metadata != prior.get('indexed_household') or
            metadata.get('slot_id') != slot_id or metadata.get('save_guid') != save_guid or
            metadata.get('file_sha256') != expected_save_sha256 or metadata.get('active_household_id') != household_id or
            metadata.get('selected_membership_verified') is not True or metadata.get('selected_household_is_active') is not True or
            not isinstance(metadata.get('household'), dict) or not isinstance(metadata.get('sim'), dict) or
            metadata['household'].get('id') != household_id or metadata['sim'].get('id') != sim_id or
            metadata['sim'].get('household_id') != household_id or metadata['household'].get('member_ids') != [sim_id] or
            not isinstance(metadata['household'].get('home_zone_id'), str) or
            metadata['sim'].get('zone_id') != metadata['household']['home_zone_id']):
        raise ValueError('Indexed original household/Sim singleton metadata changed.')
    prior_live = prior.get('loaded_before_pause', prior.get('last_live_readback'))
    paused_context(prior_live, target, metadata)
    clicks = [row.get('result') for row in prior.get('steps', [])
              if isinstance(row, dict) and row.get('action') == 'test_input']
    if len(clicks) != 1 or not _native_click(clicks[0], identity['pid']):
        raise ValueError('Prior Map Play lacks its one retained completed native input.')
    if identity_provider is None:
        from apex_cli import verified_identity
        identity_provider = verified_identity
    state_digest = sha256(state_path)
    proof = {'schema': 1, 'operation': 'observe-stable-paused-disposable-live', 'ok': False,
        'identity': identity, 'inputs': journal['artifacts'], 'target': target,
        'map_play_proof': str(prior_path), 'map_play_proof_sha256': map_play_proof_sha256,
        'map_play_result_preserved': {'ok': prior.get('ok'), 'outcome': prior.get('outcome'),
                                    'save_files_unchanged': prior.get('save_files_unchanged')},
        'indexed_household': metadata, 'before_saves': before, 'steps': [],
        'paused_live_verified': False, 'household_verified': False, 'native_slot_verified': False,
        'native_observed_slot': None, 'input_requested': False, 'input_submitted': False,
        'gameplay_mutation_requested': False, 'save_requested': False, 'save_file_written': False,
        'input_replay_attempted': False, 'source_epoch_changed': False, 'outcome': 'unresolved',
        'scope': 'Two fresh paused Live reads and unchanged current saves; no input, play/pause, save, normal-slot inference or appearance restoration.'}
    write_json(output, proof)
    def record(action, result):
        proof['steps'].append({'action': action, 'result': result}); write_json(output, proof)
        return result
    def bound():
        current = identity_provider(state)
        if (not isinstance(current, dict) or any(current.get(key) != identity.get(key) for key in keys) or
                sha256(state_path) != state_digest or sha256(prior_path) != map_play_proof_sha256 or not alive(identity['pid'])):
            raise ValueError('Exact runtime, journal or immutable Map Play prerequisite changed; observations stopped.')
    def call(action):
        if action not in ('test_snapshot', 'cas_ui_diagnostics'):
            raise ValueError('Paused Live observer permits only fixed read-only actions.')
        bound()
        return record(action, request(state, action, sim_id=sim_id,
            value=json.dumps({'test_token': journal['token'], 'value': None}), seconds=2))
    def idle():
        if game_lifecycle.shutdown_cas_state(call('cas_ui_diagnostics')).get('safe') is not True:
            raise ValueError('Active or unresolved CAS ownership blocks paused Live observation.')
    try:
        contexts, request_ids = [], []
        for index in range(2):
            bound(); idle()
            snapshot = call('test_snapshot')
            proof.setdefault('snapshots', []).append(snapshot); write_json(output, proof)
            context = paused_context(snapshot, target, metadata)
            rid = snapshot.get('request_id')
            if (not isinstance(rid, str) or re.fullmatch('[0-9a-f]{32}', rid) is None or
                    rid in request_ids or snapshot.get('request_state') != 'completed'):
                raise ValueError('Live observations require two distinct completed game-owned request identities.')
            contexts.append(context); request_ids.append(rid)
            idle(); bound()
            if index == 0: pause(.1)
        if contexts[0] != contexts[1]:
            raise ValueError('Paused native presence, save slot or simulation ticks changed between fresh observations.')
        proof.update(paused_live_verified=True, household_verified=True,
            native_observed_slot=contexts[1]['save_slot'], native_slot_verified=contexts[1]['save_slot'] == slot_id,
            loaded=proof['snapshots'][1], stable_paused_context=contexts[1], outcome='stable-paused-original-household-observed')
    except (OSError, ValueError, RuntimeError) as error:
        proof['error'] = str(error)
    proof['after_saves'] = game_lifecycle.all_save_files(profile)
    proof['save_files_unchanged'] = proof['after_saves'] == before
    proof['save_delta'] = save_delta(before, proof['after_saves'])
    try:
        proof['prerequisite_unchanged'] = sha256(prior_path) == map_play_proof_sha256
    except OSError as error:
        proof['prerequisite_unchanged'] = False
        proof['prerequisite_error'] = str(error)
    proof['ok'] = proof['paused_live_verified'] and proof['save_files_unchanged'] and proof['prerequisite_unchanged']
    if not proof['save_files_unchanged']: proof['outcome'] = 'save-files-changed-during-read-only-observation'
    if not proof['prerequisite_unchanged']: proof['outcome'] = 'immutable-map-play-proof-changed'
    write_json(output, proof)
    return {'ok': proof['ok'], 'proof': str(output), 'proof_sha256': sha256(output),
        'paused_live_verified': proof['paused_live_verified'], 'household_verified': proof['household_verified'],
        'native_slot_verified': proof['native_slot_verified'], 'native_observed_slot': proof['native_observed_slot'],
        'save_files_unchanged': proof['save_files_unchanged'], 'outcome': proof['outcome'],
        'message': proof.get('error')}
