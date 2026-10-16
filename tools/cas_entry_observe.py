"""Read-only follow-up for an accepted CAS entry whose observer timed out."""
import json
from pathlib import Path
from types import SimpleNamespace

import cas_client
import cas_transition
import reusable_profile
from source_manifest import sha256, write_json


def entry_identity(entry, identity, sim_id):
    if (not isinstance(entry, dict) or entry.get('operation') != 'observe-native-cas-entry' or
            entry.get('entry_submitted') is not True or entry.get('entry_accepted') is not True or
            entry.get('requested_sim_id') != sim_id or
            any(entry.get('identity', {}).get(k) != identity.get(k)
                for k in ('pid', 'test_token', 'script_sha256')) or
            entry.get('crash', {}).get('outcome') not in ('absent', 'unchanged')):
        raise ValueError('Exact accepted entry and unchanged runtime/crash identity required; no entry replay.')


def observe(state, entry_path, entry_hash, sim_id, output, request, identity_provider):
    from cli_identity_cache import session
    _, _, profile, original = reusable_profile.load(state)
    entry_path, output = reusable_profile.writable(entry_path), reusable_profile.writable(output)
    if (output.exists() or any(path == root or root in path.parents
                             for path in (entry_path, output) for root in (profile, original)) or
            entry_path.stat().st_size > 16 * 1024 * 1024 or sha256(entry_path) != entry_hash):
        raise ValueError('Pinned external entry and new external observation proof required.')
    entry = json.loads(entry_path.read_text(encoding='utf-8'))
    with session(state):
        identity = identity_provider(state)
        entry_identity(entry, identity, sim_id)
        proof = {'ok': False, 'operation': 'observe-accepted-cas-entry-without-replay',
                 'entry_sha256': entry_hash, 'entry_request_id': entry['entry_request_id'],
                 'identity': identity, 'entry_submitted': False, 'input_submitted': False, 'steps': []}
        write_json(output, proof)
        def recorded(*args, **kwargs):
            row = {'action': args[1], 'request_id': None}; proof['steps'].append(row); write_json(output, proof)
            def intent(action, request_id): row['request_id'] = request_id; write_json(output, proof)
            result = request(*args, submission_observer=intent, **kwargs)
            row['result'] = result; write_json(output, proof)
            return result
        try:
            diagnostic = recorded(state, 'cas_ui_diagnostics', sim_id)
            if not cas_transition.fresh_peer(diagnostic, sim_id):
                raise ValueError('Original selected CAS peer is not fresh; no selection or entry submitted.')
            result = cas_client.execute(SimpleNamespace(operation='status', state=state, sim_id=sim_id,
                                                       output=None, seconds=15), recorded)
            if result.get('ok') is not True or result.get('ui_transition_verified') is not True:
                raise ValueError('Existing native CAS inventory remains unverified; retain its read request.')
            fresh = identity_provider(state)
            if any(fresh.get(k) != identity.get(k) for k in ('pid', 'test_token', 'script_sha256')):
                raise ValueError('Runtime changed during the read-only follow-up.')
            proof.update(ok=True, inventory=result, observation_scope='Existing native editor and complete typed inventory only; no edits or persistence claim.')
        except (ValueError, RuntimeError, OSError) as error:
            proof['error'] = str(error)
        write_json(output, proof)
        return {'ok': proof['ok'], 'proof': str(output), 'proof_sha256': sha256(output),
                'entry_submitted': False, 'input_submitted': False, 'error': proof.get('error')}
