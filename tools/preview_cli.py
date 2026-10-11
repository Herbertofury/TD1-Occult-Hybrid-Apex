"""Focus-free F11 preview control and a single reusable memory-only helper."""
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import urllib.error

import reusable_profile
from sim_preview_service import PORT, ROOT
from source_manifest import write_json


def http(path, value=None):
    data = None if value is None else json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(',', ':')).encode('utf-8')
    if data is not None and len(data) > 12 * 1024 * 1024: raise ValueError('Preview payload exceeds bound.')
    request = urllib.request.Request('http://127.0.0.1:' + str(PORT) + path, data=data,
        headers={} if data is None else {'Content-Type': 'application/json'})
    from apex_cli import LocalRedirectGuard
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), LocalRedirectGuard())
    try:
        response = opener.open(request, timeout=10)
    except urllib.error.HTTPError as error:
        raw = error.read(4097)
        try: reason = json.loads(raw).get('reason', str(error))
        except ValueError: reason = str(error)
        raise ValueError('Preview helper refused the request: ' + str(reason)[:2000]) from error
    with response:
        raw = response.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024: raise ValueError('Preview response exceeds bound.')
        return json.loads(raw)


def start(state, game):
    from apex_cli import require_isolated
    require_isolated(state)
    _, _, active, _ = reusable_profile.load(state)
    mods = active / 'Mods'
    game = Path(game).resolve(strict=True)
    try: health = http('/v1/preview/health')
    except OSError: health = None
    if health is not None:
        if health.get('game_root') != str(game) or health.get('mods_root') != str(mods):
            raise ValueError('A different preview profile owns the helper; no second helper started.')
        return dict(health, reused=True)
    log = ROOT / '.work' / 'preview-service.log'
    with log.open('ab') as stream:
        process = subprocess.Popen([sys.executable, '-B', str(ROOT / 'tools' / 'sim_preview_service.py'),
            '--game-root', str(game), '--mods-root', str(mods)], stdin=subprocess.DEVNULL,
            stdout=stream, stderr=stream, cwd=ROOT,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    deadline = time.monotonic() + 55
    while time.monotonic() < deadline:
        if process.poll() is not None: raise ValueError('Preview helper exited; inspect .work/preview-service.log.')
        try: return dict(http('/v1/preview/health'), reused=False, service_pid=process.pid)
        except OSError: time.sleep(.2)
    raise ValueError('Preview helper did not become ready; no second helper started.')


def native(state, value):
    from apex_cli import owned_request
    _, journal, _, _ = reusable_profile.load(state)
    return owned_request(state, 'test_preview', value=json.dumps({'test_token': journal['token'], 'value': value},
        ensure_ascii=True, allow_nan=False, separators=(',', ':')))


def render(args):
    from apex_cli import owned_request, verified_identity
    identity = verified_identity(args.state)
    start(args.state, args.game_root)
    deadline = time.monotonic() + 95
    while http('/v1/preview/health').get('active'):
        if time.monotonic() > deadline:
            raise ValueError('Another preview is still assembling; no new request submitted.')
        time.sleep(.2)
    if args.sim_id is None or args.form is None or args.outfit_index is None:
        raise ValueError('Render requires an exact Sim, stored form and outfit index.')
    wrap = lambda value: json.dumps({'form': args.form, 'value': value})
    selection = owned_request(args.state, 'studio_status', args.sim_id, value=wrap(None))
    if not selection.get('ok') or selection.get('runtime_pid') != identity['pid'] or selection.get('inspected_form_flags') != args.form:
        raise ValueError('Fresh selected appearance inventory was refused.')
    if args.preview_id is not None and args.preview_id != selection.get('pending_preview'):
        raise ValueError('Prepared appearance identity differs; no preview requested.')
    outfits = selection.get('preview_outfit_inventory') if args.preview_id is not None else selection['outfit_inventory']
    if outfits is None: outfits=selection['outfit_inventory']
    if not 0 <= args.outfit_index < len(outfits): raise ValueError('Exact existing outfit index required.')
    outfit = outfits[args.outfit_index]
    value = dict(lane=selection['history_lane'], appearance_sha256=selection['appearance_sha256'],
                 outfit_index=args.outfit_index, outfit_id=outfit['outfit_id'])
    if args.preview_id is not None: value['preview_id'] = args.preview_id
    elif selection.get('pending_preview') is not None:
        raise ValueError('A prepared appearance is pending; name its --preview-id or cancel it before rendering.')
    snapshot = owned_request(args.state, 'studio_preview_snapshot', args.sim_id, value=wrap(json.dumps(value)))
    if not snapshot.get('ok'): raise ValueError(snapshot.get('message', 'Exact preview snapshot refused.'))
    fields = ('ok', 'sim_id', 'form', 'fields', 'native_sim', 'native_sha256', 'lane', 'appearance_sha256',
              'outfit_index', 'outfit_id', 'appearance_source', 'save_guid', 'runtime_pid', 'save_file_written',
              'history_written', 'render_sha256', 'preview_id')
    payload = {name: snapshot[name] for name in fields}
    if 'visual_form' in snapshot: payload['visual_form'] = snapshot['visual_form']
    job = http('/v1/preview/prepare', payload)
    request_id = job['request_id']; deadline = time.monotonic() + 95
    while job['state'] == 'assembling':
        if time.monotonic() > deadline: raise ValueError('Exact preview job exceeded deadline; no replay submitted: ' + request_id)
        time.sleep(.2); job = http('/v1/preview/status/' + request_id)
    if not job.get('ok') or job['state'] != 'ready': raise ValueError(job.get('reason', 'Preview job failed.'))
    if any(job[name] != snapshot[name] for name in ('sim_id', 'form', 'outfit_id', 'outfit_index', 'lane', 'appearance_sha256', 'render_sha256', 'preview_id', 'runtime_pid')):
        raise ValueError('Completed job differs from its exact selected appearance.')
    fresh = verified_identity(args.state)
    if any(fresh[name] != identity[name] for name in ('pid', 'test_token', 'script_sha256')):
        raise ValueError('Game restarted while assembling; no stale scene displayed.')
    current = owned_request(args.state, 'studio_status', args.sim_id, value=wrap(None))
    verify_selection(selection, current, snapshot)
    selection = current
    reply = native(args.state, dict(operation='load', job=job, selection=selection, automatic=True))
    if not reply.get('ok'): raise ValueError(reply.get('reason', 'Native preview selection refused.'))
    deadline = time.monotonic() + 20
    while reply.get('busy') or not reply.get('ready'):
        if time.monotonic() > deadline: raise ValueError('Native preview has not rendered; read preview status without resubmitting load.')
        time.sleep(.2); reply = native(args.state, {'operation': 'status'})
        if not reply.get('ok'): raise ValueError(reply.get('reason', 'Native scene failed.'))
        if not reply.get('busy') and not reply.get('ready') and reply.get('staged') is False:
            raise ValueError(reply.get('status', 'Native scene failed.'))
    if reply.get('scene_id') != job['scene_id'] or reply.get('sim_id') != args.sim_id or reply.get('form') != args.form:
        raise ValueError('Rendered native preview owner differs.')
    if reply.get('outfit_id') != snapshot['outfit_id'] or ('outfit_index' in reply and reply['outfit_index'] != snapshot['outfit_index']):
        raise ValueError('Rendered native preview outfit differs.')
    # Loading a new owner invalidates an in-flight read-only library page.
    # Re-arm its exact filters once; rendering must not strand the selected
    # library with an abandoned earlier-generation query. No item is applied.
    workspace=reply.get('workspace',{})
    if isinstance(workspace.get('query'),dict) and workspace.get('catalog_ready') is False:
        refreshed=native(args.state,dict(operation='workspace',values=dict(query=workspace['query'])))
        if not refreshed.get('ok'): raise ValueError(refreshed.get('reason','Read-only library refresh was refused.'))
    return dict(ok=True, job=job, native=reply, headless_asset_assembly=True,
                headless_game_runtime=False, game_appearance_written=False, disk_assets_written=False)


def verify_selection(before, current, snapshot):
    """Refuse a scene if the selected owner changed during expensive assembly."""
    keys = ('runtime_pid', 'history_lane', 'appearance_sha256', 'inspected_form_flags', 'pending_preview')
    if not current.get('ok') or any(current.get(key) != before.get(key) for key in keys):
        raise ValueError('Appearance or prepared preview changed while assembling; no stale scene displayed.')
    if snapshot.get('preview_id') is not None and snapshot['preview_id'] != current.get('pending_preview'):
        raise ValueError('Prepared appearance identity changed; no stale scene displayed.')
    outfits = current.get('preview_outfit_inventory') if snapshot.get('preview_id') is not None else current.get('outfit_inventory', [])
    if outfits is None: outfits=current.get('outfit_inventory', [])
    index = snapshot['outfit_index']
    if not 0 <= index < len(outfits) or outfits[index].get('outfit_id') != snapshot['outfit_id']:
        raise ValueError('Selected outfit changed while assembling; no stale scene displayed.')


def execute(args):
    output = None
    if args.output is not None:
        _, _, active, original = reusable_profile.load(args.state)
        output = reusable_profile.writable(args.output)
        if output.exists() or output.suffix.lower() != '.json' or any(output == root or root in output.parents for root in (active, original)):
            raise ValueError('Preview evidence needs one new external JSON filename.')
    if args.operation == 'start': result = start(args.state, args.game_root)
    elif args.operation == 'render': result = render(args)
    elif args.operation == 'health': result = http('/v1/preview/health')
    elif args.operation == 'mode':
        if args.apply_mode is None: raise ValueError('Select --apply-mode live or preview explicitly.')
        result = native(args.state, dict(operation='mode', apply_mode=args.apply_mode))
    elif args.operation in ('library-select', 'thumbnail','gallery-query','gallery-select','gallery-view'):
        if args.values is None or args.values.stat().st_size>4096: raise ValueError('Provide bounded explicit thumbnail/gallery JSON values.')
        value=json.loads(args.values.read_text(encoding='utf-8'))
        if not isinstance(value,dict) or 'operation' in value: raise ValueError('Named typed operation and JSON values required.')
        result=native(args.state,dict(value,operation=args.operation))
    elif args.operation == 'workspace':
        if args.values is None or args.values.stat().st_size > 4096: raise ValueError('Provide bounded JSON workspace values.')
        result = native(args.state, dict(operation='workspace', values=json.loads(args.values.read_text(encoding='utf-8'))))
    elif args.operation == 'view':
        if args.values is None or args.values.stat().st_size > 4096: raise ValueError('Provide a bounded JSON view-controls file.')
        status = native(args.state, {'operation': 'status'})
        if not status.get('ok') or not status.get('ready'): raise ValueError('No ready independent preview.')
        result = native(args.state, dict(operation='view', scene_id=args.scene_id or status['scene_id'],
                        values=json.loads(args.values.read_text(encoding='utf-8'))))
    else: result = native(args.state, {'operation': args.operation})
    if output is not None: write_json(output, result)
    return result
