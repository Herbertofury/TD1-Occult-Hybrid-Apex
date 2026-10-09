"""Retain the real DX11 backbuffer captured by the running game sidecar."""
import json
from pathlib import Path
import time
import re
from source_manifest import sha256, write_json
import reusable_profile


def _renderer_status(value, minimum):
    """Accept current native evidence, never the cached startup message."""
    if (not isinstance(value, dict) or value.get('ok') is not True or
            type(value.get('native_status')) is not int or not minimum <= value['native_status'] <= 3 or
            type(value.get('visible')) is not bool or
            type(value.get('game_window_verified')) is not bool or
            value['game_window_verified'] != (value['native_status'] >= 2) or
            type(value.get('renderer_initialized')) is not bool or
            value['renderer_initialized'] != (value['native_status'] == 3) or
            type(value.get('rendered_frames')) is not int or not 0 <= value['rendered_frames'] <= 0x7fffffff or
            type(value.get('frame_submission_verified')) is not bool or
            value['frame_submission_verified'] != (value['rendered_frames'] > 0) or
            type(value.get('captures_completed')) is not int or not 0 <= value['captures_completed'] <= 0x7fffffff):
        raise ValueError('Capture requires typed, current native renderer and visibility evidence.')
    return value


def renderer_status(value):
    """A started hook alone is not a verified game window or renderer."""
    return _renderer_status(value, 2)


def prepare_window(state, request, evidence, record, identity=None, identity_provider=None,
                   focus=None, monotonic=time.monotonic, pause=time.sleep):
    """Start once only on exact not-started evidence; focus and observe selection.

    Native status 1 remains transitional. No capture, visibility change or input
    is performed by this bootstrap. An explicit default-focus refusal may use
    one authenticated focus-only helper; a lost start/focus is never repeated.
    """
    evidence.update(start_attempted=False, focus_attempted=False, focus_fallback_attempted=False,
                    game_window_verified=False, steps=[])
    def call(action):
        row = {'action': action, 'state': 'attempted'}
        evidence['steps'].append(row); record()
        try:
            value = request(state, action, seconds=1)
            row.update(state='observed', result=value); record()
            if (not isinstance(value, dict) or value.get('request_state') in ('pending', 'running', 'unknown') or
                    value.get('outcome') == 'unresolved'):
                raise ValueError('Renderer bootstrap request is unresolved; no control is replayed.')
            return value
        except (OSError, ValueError, RuntimeError) as error:
            row.update(state='unresolved', error=str(error)); record(); raise
    current = call('overlay_status')
    not_started = (current.get('ok') is False and current.get('message') == 'F11 sidecar has not been started.' and
                   set(current) <= {'ok', 'message', 'request_id', 'request_state', 'execution', 'sim_data_read'})
    if not not_started:
        current = _renderer_status(current, 1)
        if current['native_status'] >= 2:
            evidence['game_window_verified'] = True; record()
            return renderer_status(current)
    # Authenticate the current bridge and its exact installed script before any
    # startup or OS focus action, not just the caller's cached integer PID.
    if identity_provider is None:
        from apex_cli import verified_identity
        identity_provider = verified_identity
    default_focus = focus is None
    if default_focus:
        from game_window import focus
    _, journal, _, _ = reusable_profile.load(state)
    expected_script = next((row['sha256'] for row in journal['artifacts'] if row['name'] == 'ApexOccultHybrid.ts4script'), None)
    expected_dll = next((row['sha256'] for row in journal['artifacts'] if row['name'] == 'ApexOverlay.dll'), None)
    observed = identity_provider(state)
    def bound(value):
        if (not isinstance(value, dict) or type(value.get('pid')) is not int or not 0 < value['pid'] <= 0xffffffff or
                value.get('test_token') != journal['token'] or expected_script is None or
                value.get('script_sha256') != expected_script):
            raise ValueError('Renderer bootstrap bridge differs from the exact installed disposable script.')
        return {key: value[key] for key in ('pid', 'test_token', 'script_sha256')}
    binding = bound(observed)
    if identity is not None and bound(identity) != binding:
        raise ValueError('Renderer bootstrap process changed from the verified lifecycle identity.')
    if not isinstance(expected_dll, str) or re.fullmatch(r'[0-9a-f]{64}', expected_dll) is None:
        raise ValueError('Renderer bootstrap requires the exact installed sidecar artifact hash.')
    evidence['identity'] = binding; evidence['dll_sha256'] = expected_dll; record()
    if not_started:
        evidence['start_attempted'] = True; record()
        started = call('overlay_start')
        if (started.get('ok') is not True or type(started.get('native_code')) is not int or started['native_code'] != 0 or
                type(started.get('protocol')) is not int or started['protocol'] != 1 or
                started.get('dll_sha256') != expected_dll):
            raise ValueError('The one matching sidecar start was refused or unverified; no replay.')
        current = _renderer_status(call('overlay_status'), 1)
    if current.get('dll_sha256') != expected_dll:
        raise ValueError('Started sidecar identity differs from the disposable artifact.')
    if bound(identity_provider(state)) != binding:
        raise ValueError('Renderer bootstrap bridge changed before focus; no focus submitted.')
    def exact_window(value):
        window = value.get('window') if isinstance(value, dict) else None
        return (isinstance(window, dict) and type(window.get('pid')) is int and window['pid'] == binding['pid'] and
                window.get('visible') is True and isinstance(window.get('class'), str) and
                window['class'].startswith('Canvas-') and
                all(type(window.get(key)) is int and window[key] > 0 for key in ('hwnd', 'width', 'height')))

    evidence['focus_attempted'] = True; record()
    try:
        focused = focus(binding['pid'])
        evidence['focus'] = focused; record()
        if (default_focus and isinstance(focused, dict) and focused.get('ok') is False and
                focused.get('foreground_verified') is False and exact_window(focused) and
                type(focused.get('foreground_pid')) is int and focused['foreground_pid'] >= 0 and
                focused.get('foreground_alt_unlock') is None and
                all(name not in focused or focused[name] is False for name in ('input_submitted', 'input_sent')) and
                focused.get('request_state') not in ('pending', 'running', 'unknown') and
                focused.get('outcome') != 'unresolved'):
            # The default focus implementation sends no game input. Recheck
            # this runtime before one fixed source-pinned focus-only lease.
            if bound(identity_provider(state)) != binding:
                raise ValueError('Renderer bootstrap bridge changed after normal focus refusal; no helper submitted.')
            from game_focus import LEASE, focus_for_input
            helper_deadline = monotonic() + LEASE
            evidence['focus_fallback_attempted'] = True; record()
            focused = focus_for_input(state, binding['pid'], dict(focused, input_submitted=False))
            evidence['focus_fallback'] = focused; record()
            if monotonic() >= helper_deadline:
                raise TimeoutError('Authenticated focus receipt arrived after its helper lease; no further action.')
            # A deadline-aware caller also refuses here if its own observation
            # budget expired while the one helper was being observed.
            if bound(identity_provider(state)) != binding:
                raise ValueError('Renderer bootstrap bridge changed during focus fallback; no further action.')
            if (not isinstance(focused, dict) or focused.get('automatic_pre_input_focus') is not True or
                    not isinstance(focused.get('focus_helper_proof'), str) or
                    re.fullmatch(r'[0-9a-f]{64}', focused['focus_helper_proof']) is None or
                    focused.get('request_state') in ('pending', 'running', 'unknown') or
                    focused.get('outcome') == 'unresolved' or
                    any(name in focused and focused[name] is not False for name in ('input_submitted', 'input_sent'))):
                raise ValueError('The one authenticated focus fallback was refused or unresolved; no replay.')
        if (not isinstance(focused, dict) or focused.get('ok') is not True or focused.get('foreground_verified') is not True or
                type(focused.get('foreground_pid')) is not int or focused['foreground_pid'] != binding['pid'] or
                not exact_window(focused)):
            raise ValueError('The one exact game-window focus was not verified; no input or focus replay.')
    except (OSError, ValueError, RuntimeError) as error:
        evidence['focus_error'] = str(error); record(); raise
    deadline = monotonic() + 3
    # Hold the same foreground handoff briefly so the real game's next Present
    # can select its chain; status reads are the only repeated operations.
    while True:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError('The real game swapchain was not observed after bounded focus; no control replay.')
        pause(min(.1, remaining))
        current = _renderer_status(call('overlay_status'), 1)
        if current.get('dll_sha256') != expected_dll:
            raise ValueError('Sidecar identity changed during bounded selection observation.')
        if monotonic() >= deadline:
            raise TimeoutError('Native renderer selection was observed after its deadline; no control replay.')
        if current['native_status'] >= 2:
            if bound(identity_provider(state)) != binding:
                raise ValueError('Renderer bootstrap bridge changed during selection observation.')
            evidence['game_window_verified'] = True; record()
            return renderer_status(current)


class RendererPreparation:
    """Borrow visibility once only when typed CAS diagnostics allow it."""
    def __init__(self, state, request, evidence, record, monotonic, pause, identity=None, identity_provider=None, focus=None):
        self.state, self.request, self.evidence, self.record = state, request, evidence, record
        self.monotonic, self.pause = monotonic, pause
        self.identity, self.identity_provider, self.focus = identity, identity_provider, focus
        evidence.update(initial_visibility=None, show_attempted=False, hide_attempted=False,
                        ready_verified=False, original_visibility_verified=False, steps=[])

    def call(self, action):
        row = {'action': action, 'state': 'attempted'}
        self.evidence['steps'].append(row)
        self.record()
        try:
            result = self.request(self.state, action, seconds=1)
            row.update(state='observed', result=result)
            self.record()
            if (isinstance(result, dict) and
                    (result.get('request_state') in ('pending', 'running', 'unknown') or result.get('outcome') == 'unresolved')):
                raise RuntimeError('Renderer control remains unresolved; it must not be repeated.')
            return result
        except (OSError, ValueError, RuntimeError) as error:
            row.update(state='unresolved', error=str(error))
            self.record()
            raise

    def cas_idle(self):
        # Use the same fail-closed, typed peer/slot validator as normal shutdown.
        # Import at call time because lifecycle uses this capture module too.
        from game_lifecycle import shutdown_cas_state
        diagnostic = self.call('cas_ui_diagnostics')
        guard = shutdown_cas_state(diagnostic)
        self.evidence['visibility_cas_guard'] = guard
        self.record()
        if guard['safe'] is not True:
            raise ValueError('Renderer preparation would expose a hidden CAS view with active or unresolved native requests; '
                             'no further visibility show or capture submitted. Initialize F11 in verified Live mode first.')

    def restore(self):
        if not self.evidence['show_attempted'] or self.evidence['hide_attempted']:
            return
        self.evidence['hide_attempted'] = True
        self.record()
        hidden = renderer_status(self.call('overlay_hide'))
        if hidden['visible'] is not False:
            raise RuntimeError('Original hidden F11 visibility was not restored; do not repeat the visibility control.')
        self.evidence['original_visibility_verified'] = True
        self.record()

    def prepare(self, overlay):
        bootstrap = {}
        self.evidence['bootstrap'] = bootstrap; self.record()
        current = prepare_window(self.state, self.request, bootstrap, self.record, self.identity,
                                 self.identity_provider, self.focus, self.monotonic, self.pause)
        self.evidence['initial_visibility'] = current['visible']
        self.record()
        ready = lambda status: status['renderer_initialized'] and status['frame_submission_verified']
        if not current['visible'] and (not ready(current) or overlay):
            self.cas_idle()
            self.evidence['show_attempted'] = True
            self.record()
            current = renderer_status(self.call('overlay_show'))
            if current['visible'] is not True:
                raise RuntimeError('One F11 show request was not observed; no visibility control is replayed.')
        deadline = self.monotonic() + 3
        while not ready(current):
            remaining = deadline - self.monotonic()
            if remaining <= 0:
                raise TimeoutError('The F11 renderer did not initialize after bounded status observation; no show or capture is replayed.')
            if current['visible'] is not True:
                raise ValueError('F11 visibility changed during initialization; no replacement show submitted.')
            self.pause(min(.1, remaining))
            current = renderer_status(self.call('overlay_status'))
        if overlay and current['visible'] is not True:
            raise ValueError('An overlay image requires current visible F11 evidence.')
        self.evidence['ready_verified'] = True
        if self.evidence['show_attempted']:
            if not overlay:
                self.restore()  # Plain backbuffer capture starts with prior visibility restored.
            self.cas_idle()  # Do not capture if CAS appeared while initialization was pending.
        else:
            self.evidence['original_visibility_verified'] = True
        self.record()


def capture(state, output, request, monotonic=time.monotonic, pause=time.sleep, overlay=False,
            identity=None, identity_provider=None, focus=None):
    _, journal, profile, original = reusable_profile.load(state)
    output = reusable_profile.writable(output)
    if any(output == root or root in output.parents for root in (profile, original)):
        raise ValueError('Capture evidence must remain outside both profiles.')
    if output.suffix.lower() != '.bmp' or output.exists() or output.with_suffix('.json').exists():
        raise ValueError('Use a new external BMP evidence filename; previous evidence is retained.')
    output.parent.mkdir(parents=True, exist_ok=True)
    preparation = {}
    proof = {'schema': 1, 'operation': 'capture-overlay' if overlay else 'capture-game',
             'ok': False, 'capture_completed_verified': False, 'output': str(output),
             'renderer_preparation': preparation, 'capture_attempted': False, 'capture_submitted': False, 'outcome': 'unresolved',
             'test_token': journal['token'], 'inputs': journal['artifacts']}
    record = lambda: write_json(output.with_suffix('.json'), proof)
    prepared = RendererPreparation(state, request, preparation, record, monotonic, pause, identity, identity_provider, focus)
    record()
    try:
        prepared.prepare(overlay)
        result = _capture_ready(state, output, request, journal, profile, monotonic, pause, overlay, proof, record)
        proof.update(result)
    except (OSError, ValueError, RuntimeError) as error:
        proof.update(ok=False, outcome='unresolved', error=str(error),
                     message='Capture preparation or observation failed; inspect retained evidence before another action.')
    finally:
        try:
            prepared.restore()
        except (OSError, ValueError, RuntimeError) as error:
            proof.update(ok=False, outcome='visibility-unresolved', visibility_restore_error=str(error),
                         message='Capture visibility restoration is unresolved; no control was repeated.')
        if preparation['show_attempted'] and not preparation['original_visibility_verified']:
            proof.update(ok=False, outcome='visibility-unresolved')
        record()
    return proof


def _capture_ready(state, output, request, journal, profile, monotonic, pause, overlay, proof, record):
    directory = reusable_profile.writable(profile / 'TD1ApexScreenshots')
    pattern = 'TD1Apex_overlay_*.bmp' if overlay else 'TD1Apex_full_*.bmp'
    prior = {str(path): (path.stat().st_mtime_ns, path.stat().st_size) for path in directory.glob(pattern)} if directory.exists() else {}
    proof['capture_attempted'] = True  # Intent survives response loss; submission then remains unknown.
    proof['capture_submitted'] = None
    record()
    requested = request(state, 'test_capture', value=json.dumps({'test_token': journal['token'], 'value': 'overlay' if overlay else None}))
    proof['requested'] = requested
    record()
    if not isinstance(requested, dict):
        raise ValueError('Capture request outcome is untyped; no capture request is replayed.')
    if requested.get('ok') is not True:
        if (requested.get('capture_requested') is False and type(requested.get('native_code')) is int and
                requested['native_code'] < 0):
            proof['capture_submitted'] = False
        return requested
    renderer_status(requested)
    if (requested.get('capture_requested') is not True or type(requested.get('native_code')) is not int or
            requested['native_code'] != 0 or requested.get('request_state') in ('pending', 'running', 'unknown')):
        raise ValueError('Capture request lacks a typed native acceptance; no capture request is replayed.')
    proof['capture_submitted'] = True
    record()
    deadline, previous = monotonic() + 5, None
    while monotonic() < deadline:
        after = renderer_status(request(state, 'overlay_status', seconds=1))
        new = [reusable_profile.writable(path) for path in directory.glob(pattern)
               if str(path) not in prior]
        if after.get('captures_completed', 0) > requested.get('captures_completed', 0) and len(new) == 1:
            source = new[0]
            observed = (source.stat().st_mtime_ns, source.stat().st_size)
            if observed == previous:
                raw = source.read_bytes()
                if raw[:2] != b'BM' or len(raw) < 54 or len(raw) > 256 * 1024 * 1024:
                    raise ValueError('The game capture is not a bounded BMP.')
                width = int.from_bytes(raw[18:22], 'little', signed=True)
                height = abs(int.from_bytes(raw[22:26], 'little', signed=True))
                if not 1 <= width <= 8192 or not 1 <= height <= 8192:
                    raise ValueError('The captured dimensions are invalid.')
                with output.open('xb') as stream:
                    stream.write(raw)
                result = {'ok': True, 'outcome': 'captured', 'capture_completed_verified': True, 'source': str(source),
                    'output': str(output), 'sha256': sha256(output), 'width': width, 'height': height,
                    'requested': requested, 'after': after,
                    'scope': 'Actual DX11 game backbuffer after Apex UI rendering.' if overlay else 'Actual DX11 game backbuffer before overlay; UI semantics require inspecting the image.'}
                return result
            previous = observed
        pause(0.1)
    return dict(requested, ok=False, outcome='unresolved', capture_completed_verified=False,
                message='One capture was submitted but a unique completed image was not observed; do not blindly repeat.')
