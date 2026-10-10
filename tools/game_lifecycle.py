"""Bounded Resume and normal Save and Exit through game-owned menu buttons."""
import json
import math
from pathlib import Path
import re
import sys
import time

import game_capture
import game_launch
import cas_transition
import reusable_profile
from source_manifest import sha256, write_json
from windows_ocr import recognize


def button(observation, phase):
    lines = observation.get('lines', [])
    normalized = lambda text: ' '.join(str(text).split()).casefold()
    text = [normalized(row.get('text')) for row in lines]
    if phase == 'menu':
        if 'menu' not in text or 'save' not in text or not any(label in text for label in ('save as', 'save as...', 'save as…')) or 'save game?' in text:
            raise ValueError('Native main menu is not recognized; no Exit click submitted.')
        label = 'exit game'
    elif phase in ('confirmation', 'confirmation-discard'):
        if not all(item in text for item in ('save game?', 'are you sure you want to exit the game?', 'cancel', 'exit game')):
            raise ValueError('Native Save Game confirmation is not recognized; no Save and Exit click submitted.')
        if phase == 'confirmation-discard' and 'save and exit' not in text:
            raise ValueError('Complete native exit confirmation is not recognized; no discard click submitted.')
        label = 'exit game' if phase == 'confirmation-discard' else 'save and exit'
    elif phase == 'resume':
        required = ('home', 'marketplace', 'load game', 'new game', 'gallery')
        forbidden = ('save game?', 'buy now', 'expansion pack', 'game pack', 'stuff pack',
                     'this game requires permissions', 'you don’t have access',
                     "you don't have access", 'cancel')
        if observation.get('ok') is not True or not all(text.count(item) == 1 for item in required) or any(item in text for item in forbidden):
            raise ValueError('Complete Sims 4 Home menu is not recognized; no Resume click submitted.')
        labels = [item for item in ('resume game', 'resume') if item in text]
        if len(labels) != 1:
            raise ValueError('Native Resume button is absent or ambiguous.')
        label = labels[0]
    else:
        raise ValueError('Unknown lifecycle phase.')
    matches = [row for row in lines if normalized(row.get('text')) == label]
    if len(matches) != 1 or not matches[0].get('words'):
        raise ValueError('Native lifecycle button is absent or ambiguous.')
    words = matches[0]['words']
    left, top = min(row['x'] for row in words), min(row['y'] for row in words)
    right = max(row['x'] + row['width'] for row in words)
    bottom = max(row['y'] + row['height'] for row in words)
    x, y = round((left + right) / 2), round((top + bottom) / 2)
    if not 0 <= left < right <= observation['width'] or not 0 <= top < bottom <= observation['height']:
        raise ValueError('Lifecycle button is outside the observed game viewport.')
    return {'command': 1, 'x': x, 'y': y, 'width': observation['width'], 'height': observation['height']}


def loaded_household(snapshot, prior_saves, sim_id=None):
    """Require a real saved Live household; no menu/loading submission is proof."""
    if not snapshot.get('ok') or snapshot.get('in_build_buy') is not False:
        return False
    try:
        slot = snapshot['save_slot']
        if type(slot) is not int or not 0 < slot < 0xffffffff:
            return False
        if 'Slot_{:08x}.save'.format(slot) not in prior_saves:
            return False
        if any(not 0 < int(str(snapshot[field]), 10) < 1 << 64
               for field in ('zone_id', 'save_guid', 'household_id')):
            return False
        sim = snapshot['sim']
        if sim.get('instanced') is not True or not 0 < int(sim['id'], 10) < 1 << 64:
            return False
        return sim_id is None or sim['id'] == sim_id
    except (KeyError, TypeError, ValueError):
        return False


def resume(state, output, identity, request, sim_id=None, seconds=60,
           capture=game_capture.capture, ocr=recognize,
           processes=game_launch.running_game_processes, monotonic=time.monotonic, pause=time.sleep,
           household_id=None, save_guid=None, identity_provider=None, focus=None):
    """Recognize Resume once, then observe a saved household through the owned bridge."""
    _, journal, profile, original = reusable_profile.load(state)
    if sim_id is not None:
        if not isinstance(sim_id, str) or not sim_id.isascii() or not sim_id.isdecimal() or not 0 < int(sim_id) < 1 << 64:
            raise ValueError('Use an exact decimal existing Sim ID.')
        sim_id = str(int(sim_id))
    if household_id is not None or save_guid is not None:
        if sim_id is None or any(not isinstance(value, str) or re.fullmatch(r'[1-9][0-9]{0,19}', value) is None or
                not 0 < int(value) < 1 << 64 for value in (household_id, save_guid)):
            raise ValueError('Already-Live Resume preflight requires exact canonical Sim, household and save GUID identities.')
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 60:
        raise ValueError('Resume completion wait must be between 0 and 60 seconds.')
    output = reusable_profile.writable(output)
    if output.exists() or output.suffix.lower() != '.json' or any(output == root or root in output.parents for root in (profile, original)):
        raise ValueError('Use one new external JSON lifecycle proof filename.')
    if not output.parent.is_dir():
        raise ValueError('Use an existing evidence directory.')
    proof = {'schema': 1, 'ok': False, 'operation': 'resume-existing-disposable-household',
             'identity': identity, 'inputs': journal['artifacts'], 'requested_sim_id': sim_id,
             'before_saves': save_files(profile), 'steps': [], 'resume_input_accepted': False,
             'household_loaded_verified': False, 'native_live_verified': False, 'save_reload_verified': False,
             'outcome': 'unresolved', 'requested_household_id': household_id, 'requested_save_guid': save_guid,
             'pause_submission_attempted': False}
    write_json(output, proof)
    deadline = monotonic() + seconds
    supplied_request = request
    def request(*args, **kwargs):
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError('Resume deadline expired; no further request or input submitted.')
        kwargs['seconds'] = min(kwargs.get('seconds', 30), remaining)
        return supplied_request(*args, **kwargs)
    if identity_provider is None:
        from apex_cli import get, verified_identity
        def identity_provider(current_state):
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError('Resume bridge observation deadline expired.')
            def bounded_transport(path, query=None):
                budget = deadline - monotonic()
                if budget <= 0:
                    raise TimeoutError('Resume bridge observation deadline expired.')
                return get(path, query, timeout=min(2, budget))
            return verified_identity(current_state, transport=bounded_transport)
    def record(action, result):
        proof['steps'].append({'action': action, 'result': result})
        write_json(output, proof)
        return result
    def still_running():
        return any(row['Id'] == identity['pid'] for row in processes())
    envelope = lambda value: json.dumps({'test_token': journal['token'], 'value': value})
    def await_owner_ready():
        # /api/bridge reads bootstrap metadata without queuing a game-thread
        # command. The Home menu may have a core owner tick before a Live alarm.
        # Never submit CAS diagnostics, captures or input while both are absent.
        expected_script = next((row['sha256'] for row in journal['artifacts']
                                if row['name'] == 'ApexOccultHybrid.ts4script'), None)
        provider = identity_provider
        if provider is None:
            from apex_cli import verified_identity
            provider = verified_identity
        readiness = {'ready': False, 'observations': 0, 'wait_seconds': 0,
                     'owner_source': None}
        proof['bridge_readiness'] = readiness
        started = monotonic()
        current = identity
        while True:
            readiness['wait_seconds'] = max(0, monotonic() - started)
            if monotonic() >= deadline:
                proof['outcome'] = 'bridge-startup-unresolved'
                raise TimeoutError('The exact game-thread owner did not become ready within the Resume deadline; no game-thread request or input submitted.')
            if not still_running():
                proof['outcome'] = 'verified-game-exited'
                raise ValueError('Verified game process exited while awaiting its game-thread owner; no input submitted.')
            if (not isinstance(current, dict) or type(current.get('pid')) is not int or
                    not 0 < current['pid'] <= 0xffffffff or current['pid'] != identity.get('pid') or
                    current.get('test_token') != journal['token'] or expected_script is None or
                    current.get('script_sha256') != expected_script):
                proof['outcome'] = 'bridge-identity-refused'
                raise ValueError('Resume bridge changed from the exact process/profile/script; no game-thread request or input submitted.')
            if any(type(current.get(name)) is not bool for name in ('core_tick_ready', 'alarm_ready')):
                proof['outcome'] = 'bridge-readiness-unknown'
                raise ValueError('Game-thread bootstrap readiness is missing or untyped; no game-thread request or input submitted.')
            readiness.update(observations=readiness['observations'] + 1,
                last_bridge=current, wait_seconds=max(0, monotonic() - started))
            if current['core_tick_ready'] or current['alarm_ready']:
                readiness.update(ready=True, owner_source='core-owner-tick' if current['core_tick_ready'] else 'live-alarm')
                write_json(output, proof)
                return
            write_json(output, proof)
            pause(min(.25, max(0, deadline - monotonic())))
            if monotonic() >= deadline:
                continue  # No late provider read can authorize an expired intent.
            try:
                current = record('resume-readiness-bridge', provider(state))
            except OSError as error:
                readiness['last_observation_error'] = str(error)
                write_json(output, proof)
                # A read-only transport failure permits another observation,
                # never a game-thread request or a new runtime identity.
    def finish():
        write_json(output, proof)
        return {'ok': proof['ok'], 'proof': str(output), 'proof_sha256': sha256(output),
                'outcome': proof['outcome'], 'native_live_verified': proof['native_live_verified'],
                'resume_input_accepted': proof['resume_input_accepted'],
                'household_loaded_verified': proof['household_loaded_verified'], 'save_reload_verified': False,
                'message': proof.get('message', proof.get('error'))}
    def settle_live(existing, already_loaded):
        from game_save import _save_live_context
        target = {'sim_id': sim_id, 'household_id': household_id, 'save_guid': save_guid}
        _save_live_context(existing, target)
        if type(existing.get('clock_speed')) is not int or not 0 <= existing['clock_speed'] <= 3:
            raise ValueError('Native Live clock is untyped; no pause or further Resume input submitted.')
        prefix = 'existing' if already_loaded else 'resumed'
        diagnostic = record(prefix + '-live-cas-preflight', request(state, 'cas_ui_diagnostics'))
        guard = shutdown_cas_state(diagnostic)
        proof[prefix + '_live_cas_guard'] = guard; write_json(output, proof)
        if guard['safe'] is not True:
            raise ValueError('Native Live preflight has active or unknown CAS ownership; no pause or further input submitted.')
        if existing['clock_speed'] != 0:
            proof['pause_submission_attempted'] = True; write_json(output, proof)
            paused = record('pause-' + prefix + '-live', request(state, 'test_pause', sim_id=sim_id,
                value=envelope(None), seconds=2))
            if (not isinstance(paused, dict) or paused.get('ok') is not True or
                    paused.get('request_state') in ('pending', 'running', 'unknown') or paused.get('outcome') == 'unresolved'):
                raise ValueError('Native Live pause is rejected or unresolved; no replay or further Resume input submitted.')
        after = record('verify-' + prefix + '-live', request(state, 'test_snapshot', sim_id=sim_id,
            value=envelope(None), seconds=2))
        _save_live_context(after, target)
        if (type(after.get('clock_speed')) is not int or after['clock_speed'] != 0 or
                any(after.get(name) != existing.get(name) for name in ('zone_id', 'client_id')) or not still_running()):
            raise ValueError('Native paused Live context did not remain exact; no further input submitted.')
        # Recheck after settling, rather than assuming no native CAS ownership
        # appeared while the first pause/readback was pending.
        final_guard = shutdown_cas_state(record(prefix + '-live-cas-settled', request(state, 'cas_ui_diagnostics')))
        proof[prefix + '_live_cas_settled_guard'] = final_guard; write_json(output, proof)
        if final_guard['safe'] is not True:
            raise ValueError('Settled Live context has active or unknown CAS ownership; no further input submitted.')
        proof.update(ok=True, outcome='existing-household-already-loaded' if already_loaded else 'existing-household-resumed-live',
            native_live_verified=True, loaded_household=after,
            household_loaded_verified=loaded_household(after, proof['before_saves'], sim_id),
            message='Exact native household is in Live mode and paused. Disk-slot and save/reload proof remain separate.')
        return finish()
    def recheck_existing_live(action):
        # Readiness can arrive while the native renderer/Home observation is
        # pending. Reauthenticate before a bounded native read; images alone
        # cannot establish the expected Live household or authorize a pause.
        if household_id is None:
            return None
        provider = identity_provider
        if provider is None:
            from apex_cli import verified_identity
            provider = verified_identity
        current = record(action + '-bridge', provider(state))
        expected_script = next((row['sha256'] for row in journal['artifacts']
                                if row['name'] == 'ApexOccultHybrid.ts4script'), None)
        if (not isinstance(current, dict) or type(current.get('pid')) is not int or
                current.get('pid') != identity['pid'] or current.get('test_token') != journal['token'] or
                expected_script is None or current.get('script_sha256') != expected_script):
            raise ValueError('Resume bridge changed from the exact process/profile/script; no Home input submitted.')
        if current.get('core_tick_ready') is not True or current.get('alarm_ready') is not True:
            return None
        try:
            existing = request(state, 'test_snapshot', sim_id=sim_id, value=envelope(None), seconds=2)
        except (OSError, ValueError, RuntimeError) as error:
            existing = {'ok': False, 'error': str(error)}
        record(action + '-snapshot', existing)
        if (isinstance(existing, dict) and existing.get('ok') is True and
                (existing.get('zone_running') is True or isinstance(existing.get('sim'), dict) and
                 existing['sim'].get('instanced') is True)):
            return settle_live(existing, True)
        return None
    try:
        if not proof['before_saves']:
            raise ValueError('No existing normal disposable save was found; Resume was not submitted.')
        if not still_running():
            raise ValueError('Verified game process exited before Resume.')
        await_owner_ready()
        if household_id is not None:
            try:
                existing = request(state, 'test_snapshot', sim_id=sim_id, value=envelope(None), seconds=2)
            except (OSError, ValueError, RuntimeError) as error:
                existing = {'ok': False, 'error': str(error)}
            record('existing-live-preflight', existing)
            if (isinstance(existing, dict) and existing.get('ok') is True and
                    (existing.get('zone_running') is True or isinstance(existing.get('sim'), dict) and
                     existing['sim'].get('instanced') is True)):
                return settle_live(existing, True)
        bootstrap = {}
        proof['renderer_bootstrap'] = bootstrap; write_json(output, proof)
        game_capture.prepare_window(state, request, bootstrap, lambda: write_json(output, proof),
            identity=identity, identity_provider=identity_provider, focus=focus, monotonic=monotonic, pause=pause)
        loaded = recheck_existing_live('post-renderer-existing-live')
        if loaded is not None:
            return loaded
        diagnostic = record('resume-cas-preflight', request(state, 'cas_ui_diagnostics'))
        guard = shutdown_cas_state(diagnostic)
        proof['resume_cas_guard'] = guard; write_json(output, proof)
        if guard['safe'] is not True:
            raise ValueError('Resume has active or unknown CAS ownership; no visibility change or Resume input submitted.')
        hidden = record('overlay_hide', request(state, 'overlay_hide'))
        if hidden.get('request_state') in ('pending', 'running', 'unknown') or hidden.get('outcome') == 'unresolved':
            raise ValueError('Resume overlay-hide outcome is unresolved; no visibility or input replay submitted.')
        if game_capture.renderer_status(hidden)['visible'] is not False:
            raise ValueError('Could not hide Apex overlay before recognizing native Resume.')
        for attempt in range(3):
            if monotonic() >= deadline:
                raise TimeoutError('Resume deadline expired before native Home observation; no input submitted.')
            if not still_running():
                raise ValueError('Verified game process changed before Resume.')
            loaded = recheck_existing_live('pre-capture-existing-live-' + str(attempt + 1))
            if loaded is not None:
                return loaded
            image = output.with_name(output.stem + '-resume-' + str(attempt + 1) + '.bmp')
            frame = record('capture-resume', capture(state, image, request))
            if not frame.get('ok'):
                raise ValueError('Native Resume capture was unresolved; no input submitted.')
            loaded = recheck_existing_live('post-capture-existing-live-' + str(attempt + 1))
            if loaded is not None:
                return loaded
            observed = ocr(image)
            try:
                selected = button(observed, 'resume')
            except ValueError as error:
                record('recognize-resume', {'observation': observed, 'error': str(error)})
                # Only observations repeat: never dismiss a card or choose a different menu action.
                pause(0.5)
                continue
            if (selected['width'], selected['height']) != (frame['width'], frame['height']):
                raise ValueError('OCR/capture viewport differs; no Resume click submitted.')
            record('recognize-resume', {'observation': observed, 'selected': selected})
            if not still_running():
                raise ValueError('Verified game process changed before Resume input.')
            loaded = recheck_existing_live('pre-input-existing-live-' + str(attempt + 1))
            if loaded is not None:
                return loaded
            if monotonic() >= deadline:
                raise TimeoutError('Resume deadline expired before native input; no input submitted.')
            result = record('click-resume', request(state, 'test_input', value=envelope(selected)))
            if not result.get('ok'):
                if refused_before_input(result):
                    pause(0.5)
                    continue  # Explicit pre-input refusal; reobserve all menu labels and dimensions.
                raise ValueError('Resume input unresolved; no successful or ambiguous press is repeated.')
            proof['resume_input_accepted'] = True
            write_json(output, proof)
            break
        if not proof['resume_input_accepted']:
            raise ValueError('Native Resume surface did not converge; no Resume completion claimed.')
        while monotonic() < deadline and still_running():
            try:
                snapshot = record('test_snapshot', request(state, 'test_snapshot', sim_id=sim_id,
                                                           value=envelope(None), seconds=2))
            except (OSError, ValueError, RuntimeError) as error:
                snapshot = record('test_snapshot', {'ok': False, 'error': str(error)})
            if (household_id is not None and isinstance(snapshot, dict) and snapshot.get('ok') is True and
                    (snapshot.get('zone_running') is True or isinstance(snapshot.get('sim'), dict) and
                     snapshot['sim'].get('instanced') is True)):
                return settle_live(snapshot, False)
            if loaded_household(snapshot, proof['before_saves'], sim_id):
                proof['household_loaded_verified'] = True
                proof['loaded_household'] = snapshot
                break
            pause(min(0.5, max(0, deadline - monotonic())))
        proof['ok'] = proof['household_loaded_verified']
        proof['outcome'] = 'existing-household-resumed' if proof['ok'] else 'resume-submitted-unresolved'
        proof['message'] = ('Existing disposable household loaded; native saved slot, Live Sim and optional requested Sim identity verified.'
                            if proof['ok'] else 'Resume was submitted once; the saved household was not verified. Inspect retained proof before another action.')
    except (OSError, ValueError, RuntimeError) as error:
        proof['error'] = str(error)
    return finish()


def save_files(profile):
    files = {}
    for path in (profile / 'saves').glob('Slot_*.save'):
        matched = re.fullmatch(r'Slot_([0-9a-fA-F]{8})\.save', path.name)
        if matched and 0 < int(matched[1], 16) < 0xffffffff:
            path = reusable_profile.writable(path)
            files[path.name] = {'bytes': path.stat().st_size, 'mtime_ns': path.stat().st_mtime_ns, 'sha256': sha256(path)}
    return files


def all_save_files(profile):
    """Passive complete top-level save/backup inventory for no-save exit proof."""
    directory = reusable_profile.writable(profile / 'saves')
    entries = sorted(directory.iterdir())
    if len(entries) > 1024:
        raise ValueError('Disposable save inventory exceeds the unchanged-file bound.')
    files = {}
    for path in entries:
        path = reusable_profile.writable(path)
        if not path.is_file():
            raise ValueError('Disposable saves contain a non-file; unchanged inventory cannot be complete.')
        before = path.stat()
        if not 0 <= before.st_size <= 512 * 1024 * 1024:
            raise ValueError('Disposable save file exceeds its unchanged-file bound.')
        digest = sha256(path); after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError('Disposable save file changed during passive inventory.')
        files[path.name] = {'bytes': after.st_size, 'mtime_ns': after.st_mtime_ns, 'sha256': digest}
    return files


def refused_before_input(result):
    # These version-2 paths return before button-down. All other failures,
    # timeouts and response loss can have submitted input and must not repeat.
    return (result.get('input_version') == 2 and result.get('input_submitted') is False and
            (result.get('input_state') == -7 or result.get('native_code') == -2))


def shutdown_cas_state(diagnostic):
    """Only a typed, idle CAS transport permits the normal Live quit path."""
    unknown = {'safe': False, 'outcome': 'cas-state-unknown',
               'reason': 'Native CAS state is unavailable or not fully typed.'}
    if (not isinstance(diagnostic, dict) or diagnostic.get('ok') is not True or
            type(diagnostic.get('native_initializer_observed')) is not bool):
        return unknown
    transport = diagnostic.get('socket_transport')
    if (not isinstance(transport, dict) or transport.get('bound') is not True or
            transport.get('host') != '127.0.0.1' or type(transport.get('port')) is not int or
            transport['port'] != 8021 or type(transport.get('native_connection_verified')) is not bool or
            'startup_error' not in transport or transport['startup_error'] is not None):
        return unknown
    peers, rows = diagnostic.get('native_peers'), diagnostic.get('requests')
    if (not isinstance(peers, list) or len(peers) > 4 or
            not isinstance(rows, list) or len(rows) > 512):
        return unknown
    age_valid = lambda age: type(age) in (int, float) and 0 <= age <= 1e12 and math.isfinite(age)
    for peer in peers:
        sim = peer.get('sim_id') if isinstance(peer, dict) else None
        if (not isinstance(sim, str) or re.fullmatch(r'[1-9][0-9]{0,19}', sim) is None or
                not 0 < int(sim) < 1 << 64 or not age_valid(peer.get('age_seconds'))):
            return unknown
    # The same public typed registry supplies request validation and shutdown.
    # Completed catalog/filter/preset reads must not look like an unknown CAS
    # protocol; pending writes still block the normal quit path below.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
    from apex_core import cas_controls
    operations = {'status', 'panel', 'select', 'hair-swatch', 'outfit', 'outfit-add', 'undo', 'redo', 'accept', 'form-select', 'layer-select'} | set(cas_controls.OPERATIONS)
    blocked, ids = [], set()
    for row in rows:
        if not isinstance(row, dict):
            return unknown
        request_id = row.get('cas_request_id')
        if (not isinstance(request_id, str) or re.fullmatch(r'[0-9a-f]{32}', request_id) is None or
                request_id in ids or not isinstance(row.get('operation'), str) or row['operation'] not in operations or
                not isinstance(row.get('state'), str) or not age_valid(row.get('age_seconds'))):
            return unknown
        ids.add(request_id)
        expired_status = row['state'] == 'superseded-read' and row['operation'] == 'status'
        terminal = row['state'] in ('completed', 'failed') or expired_status
        if 'outcome' in row:
            terminal = terminal and (row['outcome'] in ('completed', 'failed', 'live-return', 'accept-rejected') or
                                     (expired_status and row['outcome'] == 'superseded-read'))
        if 'commit_outcome' in row:
            terminal = terminal and row['commit_outcome'] in ('accepted', 'rejected')
        if row.get('lifecycle_stage') in ('accept-intent', 'accept-unresolved'):
            terminal = False
        if not terminal:
            blocked.append({key: row[key] for key in ('cas_request_id', 'state', 'operation')})
    if peers:
        return {'safe': False, 'outcome': 'cas-active-refused',
                'reason': 'A native CAS peer is still attached.', 'native_peers': peers,
                'blocking_native_requests': blocked}
    if transport['native_connection_verified']:
        return unknown  # A reported connection without its exact peer is contradictory.
    if blocked:
        return {'safe': False, 'outcome': 'cas-unresolved-refused',
                'reason': 'A native CAS request still owns its slot.', 'blocking_native_requests': blocked}
    return {'safe': True, 'outcome': 'cas-idle-verified', 'blocking_native_requests': []}


def shutdown(state, output, identity, request, capture=game_capture.capture, ocr=recognize,
             processes=game_launch.running_game_processes, monotonic=time.monotonic, pause=time.sleep,
             save=True, sim_id=None, household_id=None, save_guid=None):
    if type(save) is not bool:
        raise ValueError('Shutdown save selection must be an explicit boolean.')
    if not save and any(not isinstance(value, str) or re.fullmatch(r'[1-9][0-9]{0,19}', value) is None or
            not 0 < int(value) < 1 << 64 for value in (sim_id, household_id, save_guid)):
        raise ValueError('Exit without saving requires exact canonical Sim, household and save GUID identities.')
    _, journal, profile, original = reusable_profile.load(state)
    output = reusable_profile.writable(output)
    if output.exists() or output.suffix.lower() != '.json' or any(output == root or root in output.parents for root in (profile, original)):
        raise ValueError('Use one new external JSON lifecycle proof filename.')
    if not output.parent.is_dir():
        raise ValueError('Use an existing evidence directory.')
    proof = {'schema': 1, 'ok': False, 'operation': 'normal-save-and-exit' if save else 'normal-exit-without-saving',
             'identity': identity, 'inputs': journal['artifacts'], 'steps': [],
             'before_saves': save_files(profile), 'game_exit_verified': False,
             'normal_exit_verified': False, 'save_and_exit_input_accepted': False,
             'save_completed_file_verified': False, 'save_reload_verified': False,
             'exit_without_save_input_accepted': False, 'save_files_unchanged_verified': False,
             'save_requested': save, 'requested_sim_id': sim_id, 'requested_household_id': household_id,
             'requested_save_guid': save_guid,
             'final_process_alive': None, 'outcome': 'unresolved'}
    write_json(output, proof)
    def record(action, result, require_ok=True):
        proof['steps'].append({'action': action, 'result': result})
        write_json(output, proof)
        if require_ok and (not isinstance(result, dict) or result.get('ok') is not True):
            raise ValueError('Lifecycle step failed; retained proof: ' + action)
        return result
    def guard_cas():
        try:
            diagnostic = request(state, 'cas_ui_diagnostics')
        except (OSError, ValueError, RuntimeError) as error:
            diagnostic = {'ok': False, 'error': str(error)}
        record('cas-shutdown-preflight', diagnostic, require_ok=False)
        guard = shutdown_cas_state(diagnostic)
        proof['cas_shutdown_guard'] = guard
        write_json(output, proof)
        if guard['safe'] is not True:
            proof['outcome'] = guard['outcome']
            raise ValueError(guard['reason'] + ' No quit or further input was submitted. '
                             'Use semantic cas return to finish CAS and verify Live mode first; '
                             'retain unresolved request UUIDs instead of repeating shutdown.')
    def process_alive():
        pid = identity.get('pid') if isinstance(identity, dict) else None
        if type(pid) is not int or not 0 < pid <= 0xffffffff:
            raise ValueError('Final process observation requires the exact integer verified PID.')
        rows = processes()
        if (not isinstance(rows, list) or len(rows) > 16384 or any(
                not isinstance(row, dict) or type(row.get('Id')) is not int or
                not 0 < row['Id'] <= 0xffffffff for row in rows)):
            raise ValueError('Game process inventory is not fully typed; exit is unknown.')
        matches = [row for row in rows if row['Id'] == pid]
        if len(matches) > 1:
            raise ValueError('Game process inventory has duplicate PID observations; exit is unknown.')
        return bool(matches)
    before_crash = None
    envelope = lambda value: json.dumps({'test_token': journal['token'], 'value': value})
    def guard_unsaved_live():
        if save:
            return
        if not process_alive():
            raise ValueError('Verified game process ended before unsaved exit; no input submitted.')
        from game_save import _save_live_context
        native = record('unsaved-exit-live-preflight', request(state, 'test_snapshot', sim_id=sim_id,
            value=envelope(None), seconds=2))
        _save_live_context(native, {'sim_id': sim_id, 'household_id': household_id, 'save_guid': save_guid})
        if type(native.get('clock_speed')) is not int or native['clock_speed'] != 0:
            raise ValueError('Exit without saving requires the exact native Live household paused first.')
        previous = proof.get('unsaved_exit_native_before')
        if previous is not None and any(native.get(name) != previous.get(name) for name in ('zone_id', 'client_id')):
            raise ValueError('Native Live client/zone changed during unsaved exit; no further input submitted.')
        if previous is None:
            proof['unsaved_exit_native_before'] = native; write_json(output, proof)
    try:
        before_crash, _ = cas_transition.read_crash(profile)
        proof['before_crash'] = before_crash
        write_json(output, proof)
        if before_crash['state'] not in ('absent', 'read'):
            raise ValueError('Existing crash report cannot be observed safely; no shutdown action submitted.')
        if not save:
            proof['before_all_saves'] = all_save_files(profile); write_json(output, proof)
        guard_cas()
        guard_unsaved_live()
        record('overlay_hide', request(state, 'overlay_hide'))
        image = output.with_name(output.stem + '-initial.bmp')
        frame = record('capture-initial', capture(state, image, request)); observed = ocr(image)
        initial = None
        confirmation = 'confirmation' if save else 'confirmation-discard'
        for phase in (confirmation, 'menu'):
            try:
                button(observed, phase); initial = (phase, frame, observed); break
            except ValueError: pass
        if initial is None:
            guard_cas()
            guard_unsaved_live()
            record('quit-menu-request', request(state, 'test_quit', value=envelope(None)))
        phases = (confirmation,) if initial and initial[0] == confirmation else ('menu', confirmation)
        for phase in phases:
            selected, clicked = None, False
            for attempt in range(3):
                if attempt == 0 and initial and initial[0] == phase:
                    _, frame, observed = initial
                else:
                    image = output.with_name(output.stem + '-' + phase + '-' + str(attempt + 1) + '.bmp')
                    frame = record('capture-' + phase, capture(state, image, request)); observed = ocr(image)
                try: selected = button(observed, phase)
                except ValueError as error:
                    proof['steps'].append({'action': 'recognize-' + phase, 'observation': observed, 'error': str(error)})
                    write_json(output, proof)
                    pause(0.5)
                    continue
                if (selected['width'], selected['height']) != (frame['width'], frame['height']):
                    raise ValueError('OCR/capture viewport identity differs; no click submitted.')
                # The accepted label, pixels and native dimensions are recorded
                # before the single identity-protected click is submitted.
                proof['steps'].append({'action': 'recognize-' + phase, 'observation': observed, 'selected': selected})
                write_json(output, proof)
                guard_cas()
                guard_unsaved_live()
                result = record('click-' + phase, request(state, 'test_input', value=envelope(selected)), require_ok=False)
                if not isinstance(result, dict) or result.get('ok') is not True:
                    if isinstance(result, dict) and refused_before_input(result):
                        pause(0.5); continue  # Reobserve the complete native surface before another attempt.
                    raise ValueError('Unresolved lifecycle input; no button press repeated: ' + phase)
                clicked = True
                if phase == confirmation:
                    proof['save_and_exit_input_accepted' if save else 'exit_without_save_input_accepted'] = True
                    write_json(output, proof)
                pause(0.5)
                break
            if not clicked:
                raise ValueError('Native lifecycle surface did not converge; do not repeat quit blindly.')
        deadline = monotonic() + 30
        while monotonic() < deadline:
            if not process_alive():
                proof['game_exit_verified'] = True
                break
            pause(0.5)
    except (OSError, ValueError, RuntimeError) as error:
        proof['error'] = str(error)
    # Always preserve final evidence, including after a menu, transport or input
    # failure. Process disappearance alone does not prove a normal game exit.
    try:
        proof['final_process_alive'] = process_alive()
        proof['game_exit_verified'] = proof['final_process_alive'] is False
    except (OSError, ValueError, RuntimeError) as error:
        proof['game_exit_verified'] = False
        proof['process_observation_error'] = str(error)
    try:
        if before_crash is None:
            proof['crash'] = {'preserved': False, 'outcome': 'baseline-unavailable'}
        else:
            proof['crash'] = cas_transition.preserve_crash(profile, output, before_crash)
    except (OSError, ValueError, RuntimeError) as error:
        proof['crash'] = {'preserved': False, 'outcome': 'observation-failed', 'error': str(error)}
    crash = proof['crash']
    after_crash = crash.get('after', {})
    changed_crash = (isinstance(after_crash, dict) and before_crash is not None and
                     before_crash.get('state') in ('absent', 'read') and
                     ((after_crash.get('state') == 'read' and
                       after_crash.get('sha256') != before_crash.get('sha256')) or
                      after_crash.get('state') == 'oversized'))
    crash_clear = (before_crash is not None and before_crash.get('state') in ('absent', 'read') and
                   crash.get('outcome') in ('absent', 'unchanged') and not changed_crash)
    if proof['game_exit_verified']:
        try:
            proof['after_saves'] = save_files(profile)
            changed = {name: row for name, row in proof['after_saves'].items() if row != proof['before_saves'].get(name)}
            proof['rewritten_normal_slots'] = changed
            proof['save_completed_file_verified'] = bool(changed) and proof['save_and_exit_input_accepted']
        except (OSError, ValueError, RuntimeError) as error:
            proof['save_observation_error'] = str(error)
    if not save and 'before_all_saves' in proof:
        try:
            proof['after_all_saves'] = all_save_files(profile)
            proof['save_files_unchanged_verified'] = proof['after_all_saves'] == proof['before_all_saves']
        except (OSError, ValueError, RuntimeError) as error:
            proof['save_observation_error'] = str(error)
    accepted = proof['save_and_exit_input_accepted'] if save else proof['exit_without_save_input_accepted']
    proof['normal_exit_verified'] = (proof['game_exit_verified'] and accepted and
                                     crash_clear and 'error' not in proof)
    proof['ok'] = proof['normal_exit_verified'] and (proof['save_completed_file_verified'] if save else proof['save_files_unchanged_verified'])
    if changed_crash:
        proof['ok'] = proof['normal_exit_verified'] = False
        proof['outcome'] = 'crash' if crash.get('preserved') is True else 'changed-crash-report-refused'
        proof['message'] = 'A changed crash report was observed; this is not a verified normal exit. Inspect retained crash evidence before any retry.'
    elif proof['ok']:
        proof['outcome'] = 'normal-save-and-exit' if save else 'normal-exit-without-saving'
        proof['message'] = ('Normal Save and Exit completed; disposable save rewrite and game-process exit verified. Reload verification remains separate.' if save else
            'Normal Exit Game completed without a Save selection; all disposable save/backup files remained unchanged and process exit was observed without a new crash.')
    elif proof['outcome'].startswith('cas-'):
        proof['message'] = proof['error']
    else:
        proof['outcome'] = 'process-exited-unverified' if proof['game_exit_verified'] else 'unresolved'
        proof['message'] = proof.get('error', 'Save and Exit was submitted once; save rewrite/process exit were not both verified. Retained proof must be inspected before retrying.' if save else
            'Exit without saving is unresolved or disposable save files changed. Inspect retained proof; no confirmation is replayed.')
    write_json(output, proof)
    return {'ok': proof['ok'], 'proof': str(output), 'proof_sha256': sha256(output),
            'game_exit_verified': proof['game_exit_verified'], 'save_completed_file_verified': proof['save_completed_file_verified'],
            'normal_exit_verified': proof['normal_exit_verified'], 'final_process_alive': proof['final_process_alive'],
            'outcome': proof['outcome'], 'crash': proof['crash'],
            'exit_without_save_input_accepted': proof['exit_without_save_input_accepted'],
            'save_files_unchanged_verified': proof['save_files_unchanged_verified'],
            'save_reload_verified': False, 'message': proof.get('message', proof.get('error'))}
