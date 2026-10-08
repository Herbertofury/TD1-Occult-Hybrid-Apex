"""Observe one CAS entry and one native inventory read, without input replay.

The disposable profile is read-only here. Proof and a newly changed, bounded
crash report may only be written beside a new external evidence filename.
"""
import hashlib
import json
import math
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from xml.etree import ElementTree

import cas_client
import game_launch
import reusable_profile
from source_manifest import sha256, write_json

MAX_CRASH_BYTES = 1024 * 1024


def fresh_peer(diagnostics, sim_id):
    """A fresh peer for another Sim is not evidence for this CAS entry."""
    if not isinstance(diagnostics, dict) or diagnostics.get('ok') is not True:
        return False
    transport = diagnostics.get('socket_transport')
    if (not isinstance(transport, dict) or transport.get('bound') is not True or
            transport.get('host') != '127.0.0.1' or type(transport.get('port')) is not int or
            transport['port'] != 8021):
        return False
    peers = diagnostics.get('native_peers')
    return isinstance(peers, list) and any(
        isinstance(peer, dict) and peer.get('sim_id') == sim_id and
        type(peer.get('age_seconds')) in (int, float) and
        math.isfinite(peer['age_seconds']) and 0 <= peer['age_seconds'] <= 3
        for peer in peers)


def process_alive(pid):
    """Bounded, read-only Windows process observation, without shell polling."""
    return game_launch.observe_game_process(pid) is not None


def read_crash(profile):
    """Read at most one MiB; neither the active nor original profile is written."""
    path = reusable_profile.writable(profile / 'lastCrash.txt')
    if not path.exists():
        return {'state': 'absent'}, None
    try:
        with path.open('rb') as stream:
            stat = path.stat()
            raw = stream.read(MAX_CRASH_BYTES + 1)
        if len(raw) > MAX_CRASH_BYTES:
            return {'state': 'oversized', 'bytes': stat.st_size, 'mtime_ns': stat.st_mtime_ns}, None
        return {'state': 'read', 'bytes': len(raw), 'mtime_ns': stat.st_mtime_ns,
                'sha256': hashlib.sha256(raw).hexdigest()}, raw
    except OSError as error:
        return {'state': 'unreadable', 'error': str(error)}, None


def preserve_crash(profile, output, before):
    observed, raw = read_crash(profile)
    result = {'before': before, 'after': observed, 'preserved': False}
    if observed.get('sha256') == before.get('sha256') or raw is None:
        result['outcome'] = 'unchanged' if observed == before or observed.get('sha256') else observed['state']
        return result
    try:
        # Native lastCrash reports are UTF-8 XML. Reject alternate encodings,
        # declarations and entities before parsing or preserving a document.
        text = raw.decode('utf-8-sig', 'strict')
        if '\x00' in text or '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
            raise ValueError('Crash XML contains an unsupported declaration or encoding.')
        root = ElementTree.fromstring(text)
        metadata = {}
        fields = {'sessionid', 'type', 'createtime', 'buildsignature', 'categoryid'}
        for node in root.iter():
            name = node.tag.rsplit('}', 1)[-1] if isinstance(node.tag, str) else ''
            if name in fields and name not in metadata:
                metadata[name] = (node.text or '').strip()[:512]
        target = reusable_profile.writable(output.with_name(
            output.stem + '-crash-' + observed['sha256'] + '.xml'))
        if target.exists():
            if sha256(target) != observed['sha256']:
                raise ValueError('External content-addressed crash filename is already occupied.')
        else:
            with target.open('xb') as stream:
                stream.write(raw)
        result.update(preserved=True, outcome='preserved', path=str(target), metadata=metadata)
    except (OSError, ValueError, UnicodeError, ElementTree.ParseError) as error:
        result.update(outcome='refused', error=str(error))
    return result


def observe(state, output, identity, request, sim_id, value=None, seconds=60,
            processes=None, monotonic=time.monotonic, pause=time.sleep, transport=None):
    """Submit entry once, then observe an exact-Sim peer and one status ACK.

With the CLI's transport supplied, each HTTP operation shares this deadline.
Lost or failed requests are retained and never resubmitted by this observer.
"""
    started = monotonic()
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 60:
        raise ValueError('CAS entry observation must be between 0 and 60 seconds.')
    deadline = started + seconds
    journal_path, journal, profile, original = reusable_profile.load(state)
    if (not isinstance(sim_id, str) or not sim_id.isascii() or not sim_id.isdecimal() or
            not 0 < int(sim_id) < 1 << 64 or str(int(sim_id)) != sim_id):
        raise ValueError('CAS entry requires an exact canonical decimal Sim ID.')
    expected = next((row['sha256'] for row in journal['artifacts']
                     if row['name'] == 'ApexOccultHybrid.ts4script'), None)
    if (not isinstance(identity, dict) or type(identity.get('pid')) is not int or not 0 < identity['pid'] <= 0xffffffff or
            identity.get('test_token') != journal['token'] or expected is None or
            identity.get('script_sha256') != expected):
        raise ValueError('CAS observer identity differs from the disposable journal and installed script.')
    output = reusable_profile.writable(output)
    if (output.exists() or output.suffix.casefold() != '.json' or not output.parent.is_dir() or
            any(output == root or root in output.parents for root in (profile, original)) or
            output == journal_path):
        raise ValueError('Use one new external JSON CAS proof filename outside both profiles and the journal.')
    before, _ = read_crash(profile)
    proof = {'schema': 1, 'ok': False, 'operation': 'observe-native-cas-entry',
             'outcome': 'unresolved', 'last_verified_stage': None, 'identity': identity,
             'journal': str(journal_path), 'inputs': journal['artifacts'], 'requested_sim_id': sim_id,
             'seconds': seconds, 'steps': [], 'entry_submitted': False, 'entry_accepted': False,
             'handshake_verified': False, 'inventory_verified': False, 'process_exit_verified': False,
             'owner_requests': [], 'cas_request_id': None,
             'crash_before': before, 'profile_read_only': True, 'no_input_replay': True}
    # Reserve this evidence filename exclusively before any game command.
    with output.open('x', encoding='utf-8') as stream:
        json.dump(proof, stream, ensure_ascii=False, indent=2)

    def remaining():
        available = deadline - monotonic()
        if available <= 0:
            raise TimeoutError('CAS entry observation deadline expired.')
        return available

    def running():
        live = (process_alive(identity['pid']) if processes is None else
                any(row['Id'] == identity['pid'] for row in processes()))
        if not live:
            proof['process_exit_verified'] = True
            raise ProcessLookupError('Verified Sims process exited during CAS entry observation.')

    def record(action, result):
        proof['steps'].append({'action': action, 'elapsed_seconds': max(0, monotonic() - started),
                               'result': result})
        write_json(output, proof)
        return result

    def bounded_transport(path, query=None, timeout=12):
        timeout = min(timeout, 2, remaining())
        if path == '/api/command' and isinstance(query, dict):
            # Record the predetermined owner ID before transport: response loss
            # during its completion poll must not discard the recovery identity.
            proof['owner_requests'].append({'action': query.get('action'),
                                            'request_id': query.get('request_id')})
            write_json(output, proof)
        return transport(path, query, timeout=timeout)

    def bounded_pause(seconds):
        pause(min(seconds, max(0, deadline - monotonic())))

    def call(_state, action, sim_id=None, **kwargs):
        # Read-only CAS result polling uses this same process/deadline guard.
        running()
        kwargs['seconds'] = min(kwargs.get('seconds', 2), 2, remaining())
        if transport is not None:
            kwargs['transport'] = bounded_transport
        try:
            result = request(_state, action, sim_id=sim_id, **kwargs)
        except (OSError, ValueError, RuntimeError) as error:
            record(action, {'ok': False, 'error': str(error), 'response_lost_or_failed': True})
            raise
        record(action, result)
        if not isinstance(result, dict):
            raise ValueError('CAS entry observer requires a typed owner result.')
        if action == 'cas_ui_request':
            proof['cas_request_id'] = result.get('cas_request_id')
        if action == 'cas_ui_result' and result.get('cas_request_id') != kwargs.get('value'):
            raise ValueError('Native CAS acknowledgement belongs to a different request identity.')
        return result

    try:
        running()
        remaining()
        proof['entry_submitted'] = True
        proof['outcome'] = 'entry-submitted'
        write_json(output, proof)
        entry = call(state, 'test_cas', sim_id=sim_id,
                     value=json.dumps({'test_token': journal['token'], 'value': value}))
        proof['entry_accepted'] = entry.get('ok') is True
        if not proof['entry_accepted']:
            proof['outcome'] = 'unresolved' if entry.get('outcome') == 'unresolved' else 'entry-rejected'
            raise RuntimeError('CAS entry was not acknowledged; its request must not be repeated blindly.')
        proof['last_verified_stage'] = 'entry-submitted'
        running()
        while remaining() > 0:
            diagnostic = call(state, 'cas_ui_diagnostics')
            if fresh_peer(diagnostic, sim_id):
                proof['handshake_verified'] = True
                proof['outcome'] = proof['last_verified_stage'] = 'handshake'
                write_json(output, proof)
                break
            pause(min(.25, remaining()))
        # Exactly one native status submission. cas_client only polls its ID.
        args = SimpleNamespace(operation='status', state=state, sim_id=sim_id,
                               seconds=remaining(), output=None)
        inventory = cas_client.execute(args, call, monotonic=monotonic, pause=bounded_pause)
        proof['inventory_result'] = inventory
        if inventory.get('ok') is not True or inventory.get('ui_transition_verified') is not True:
            raise RuntimeError('Native CAS inventory read remains unresolved or failed; retain its request identity.')
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
        from apex_core.cas_ui import validate_client
        validate_client(inventory.get('client'), sim_id, {'operation': 'status'})
        running()
        remaining()
        proof.update(ok=True, inventory_verified=True, outcome='inventory', last_verified_stage='inventory',
                     inventory_scope='Every mapped native CAS catalog, including empty and unsupported records.')
    except (OSError, ValueError, RuntimeError) as error:
        proof['error'] = str(error)
        known_id = proof['cas_request_id']
        if ('inventory_result' not in proof and isinstance(known_id, str) and len(known_id) == 32 and
                all(char in '0123456789abcdef' for char in known_id)):
            proof['inventory_result'] = {'ok': False, 'outcome': 'unresolved', 'cas_request_id': known_id,
                                         'ui_transition_verified': False, 'input_submitted': False,
                                         'message': 'Observer stopped before a validated native acknowledgement; poll this ID.'}
        if proof['outcome'] not in ('entry-rejected',):
            proof['outcome'] = 'unresolved'
        try:
            running()
        except ProcessLookupError:
            proof['outcome'] = 'process-exited'
        except (OSError, ValueError) as observation_error:
            proof['process_observation_error'] = str(observation_error)
        try:
            proof['crash'] = preserve_crash(profile, output, before)
        except (OSError, ValueError) as crash_error:
            proof['crash'] = {'preserved': False, 'outcome': 'refused', 'error': str(crash_error)}
        if proof['crash']['preserved']:
            proof['outcome'] = 'crash'
    proof['elapsed_seconds'] = max(0, monotonic() - started)
    write_json(output, proof)
    return {'ok': proof['ok'], 'outcome': proof['outcome'], 'proof': str(output), 'proof_sha256': sha256(output),
            'entry_submitted': proof['entry_submitted'], 'entry_accepted': proof['entry_accepted'],
            'handshake_verified': proof['handshake_verified'], 'inventory_verified': proof['inventory_verified'],
            'process_exit_verified': proof['process_exit_verified'], 'elapsed_seconds': proof['elapsed_seconds'],
            'message': proof.get('error', 'Exact selected native CAS Sim and complete mapped catalog inventory verified.')}
