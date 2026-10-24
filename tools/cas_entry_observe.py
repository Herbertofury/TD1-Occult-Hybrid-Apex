"""Read-only follow-up for an accepted CAS entry whose observer timed out."""
import json
import time
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


def observed_member(entry, diagnostic, requested):
    """Read an initial full-editor member without replaying member selection.

    EA may initially select another captured household member. Reuse the same
    complete checkpoint/roster checks as the entry observer; a fresh unrelated
    peer or a single-Sim editor never qualifies this handoff.
    """
    if cas_transition.fresh_peer(diagnostic, requested):
        return requested, None
    rid=entry.get('entry_request_id')
    steps=entry.get('steps')
    if (not isinstance(steps,list) or len(steps)>1024 or not isinstance(rid,str) or len(rid)!=32 or
            any(char not in '0123456789abcdef' for char in rid)):
        raise ValueError('Initial member observation lacks the exact retained entry acknowledgement.')
    receipts=[step.get('result') for step in steps
        if isinstance(step,dict) and step.get('action') in ('test_cas','test_cas_completion') and
        isinstance(step.get('result'),dict) and step['result'].get('ok') is True and
        isinstance(rid,str) and step['result'].get('request_id')==rid and
        step['result'].get('request_state')=='completed']
    if len(receipts)==1:
        handoff=cas_transition.protected_initial_member(receipts[0],diagnostic,requested)
        if handoff is not None:
            return handoff['source'], handoff['household']
    raise ValueError('Original selected CAS peer is not fresh; no selection or entry submitted.')


def observe(state, entry_path, entry_hash, sim_id, output, request, identity_provider,
            monotonic=time.monotonic,pause=time.sleep):
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
            deadline=monotonic()+15
            while True:
                diagnostic = recorded(state, 'cas_ui_diagnostics', sim_id)
                # A terminal read may see the previous heartbeat between UI
                # ticks. Observe a later heartbeat, never repeat an unresolved
                # owner UUID or submit a navigation/entry action.
                if diagnostic.get('ok') is not True or diagnostic.get('request_state')!='completed':
                    raise ValueError('CAS diagnostic read is unresolved; retain its UUID without replay.')
                try:
                    actual,household=observed_member(entry,diagnostic,sim_id)
                    break
                except ValueError:
                    if monotonic()>=deadline:raise
                    pause(min(.25,max(0,deadline-monotonic())))
            proof.update(requested_sim_id=sim_id,observed_sim_id=actual,
                         initial_member_observed=actual!=sim_id,member_selection_submitted=False)
            write_json(output,proof)
            result = cas_client.execute(SimpleNamespace(operation='status', state=state, sim_id=actual,
                                                       output=None, seconds=15), recorded)
            if result.get('ok') is not True or result.get('ui_transition_verified') is not True:
                raise ValueError('Existing native CAS inventory remains unverified; retain its read request.')
            if household is not None and result.get('client',{}).get('sim',{}).get('householdId')!=household:
                raise ValueError('Initial native CAS member belongs to a different captured household.')
            if isinstance(entry.get('ui_exception_before'), dict):
                proof['ui_health'] = cas_transition.ui_health(profile, entry['ui_exception_before'], output)
                if proof['ui_health']['ok'] is not True:
                    raise ValueError('A new native CAS UI exception prevents readiness; the accepted entry is not replayed.')
            fresh = identity_provider(state)
            if any(fresh.get(k) != identity.get(k) for k in ('pid', 'test_token', 'script_sha256')):
                raise ValueError('Runtime changed during the read-only follow-up.')
            proof.update(ok=True, inventory=result, observation_scope='Existing native editor and complete typed inventory only; no edits or persistence claim.')
        except (ValueError, RuntimeError, OSError) as error:
            proof['error'] = str(error)
        write_json(output, proof)
        return {'ok': proof['ok'], 'proof': str(output), 'proof_sha256': sha256(output),
                'entry_submitted': False, 'input_submitted': False, 'error': proof.get('error')}
