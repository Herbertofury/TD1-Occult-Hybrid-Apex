"""In-place package reads, memory-only scenes and a bounded loopback broker.

One persistent no-window assembler reuses the installed DBPF indexes. No saves
are opened. No Sim meshes, textures, or package copies are written to disk.
"""
import argparse
import os
import base64
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from loopback_server import LoopbackHTTPServer
import json
from pathlib import Path
import queue
import re
import subprocess
import threading
import time

from cas_resource_catalog import canonical, digest, sha, no_redirected_ancestors

ROOT = Path(__file__).resolve().parents[1]
PORT = 8024
MAX_REQUEST = 12 * 1024 * 1024
MAX_SCENE = 64 * 1024 * 1024
MEMORY_BUDGET = 128 * 1024 * 1024
WORKER = ROOT / '.work' / 'preview-worker' / 'bin' / 'ApexPreviewWorker.exe'


def snapshot(request):
    """Validate identity and all native bytes before starting expensive work."""
    required = {'ok', 'sim_id', 'form', 'fields', 'native_sim', 'native_sha256',
                'lane', 'appearance_sha256', 'outfit_index', 'outfit_id',
                'appearance_source', 'save_guid', 'runtime_pid', 'save_file_written', 'history_written',
                'render_sha256', 'preview_id'}
    if not isinstance(request, dict) or set(request) != required or request['ok'] is not True:
        raise ValueError('Exact owner-thread preview snapshot required.')
    for field in ('sim_id', 'outfit_id', 'save_guid'):
        expression = r'(?:0|[1-9][0-9]{0,19})' if field == 'outfit_id' else r'[1-9][0-9]{0,19}'
        if not isinstance(request[field], str) or not re.fullmatch(expression, request[field]) or int(request[field]) >= 1 << 64:
            raise ValueError('Invalid preview ' + field + '.')
    if (type(request['form']) is not int or request['form'] not in (1, 2, 4, 8, 16, 32, 64) or
            type(request['runtime_pid']) is not int or not 0 < request['runtime_pid'] < 1 << 32 or
            type(request['outfit_index']) is not int or not 0 <= request['outfit_index'] < 1024 or
            request['save_file_written'] is not False or request['history_written'] is not False):
        raise ValueError('Invalid preview owner or writable snapshot.')
    if not isinstance(request['lane'], str) or len(request['lane']) > 200 or not request['lane'].startswith(request['save_guid'] + ':'):
        raise ValueError('Save lane identity differs.')
    sha(request['appearance_sha256']); sha(request['native_sha256']); sha(request['render_sha256'])
    if request['preview_id'] is not None and (not isinstance(request['preview_id'], str) or not re.fullmatch(r'[0-9a-f]{32}', request['preview_id'])):
        raise ValueError('Exact prepared preview identity required.')
    raw = base64.b64decode(request['native_sim'], validate=True)
    if not raw or len(raw) > 7 * 1024 * 1024 or digest(raw) != request['native_sha256']:
        raise ValueError('Native Sim bytes differ from their hash.')
    # Sims SimData field 1 is required fixed64. Parse all wire extents so an
    # embedded second conflicting identity cannot be accepted accidentally.
    from live_color_probe import chunks
    identity = [(kind, chunk) for field, kind, _value, chunk in chunks(raw) if field == 1]
    if len(identity) != 1 or identity[0][0] != 1 or int.from_bytes(identity[0][1][-8:], 'little') != int(request['sim_id']):
        raise ValueError('Native preview Sim identity differs.')
    if not isinstance(request['fields'], dict) or '__outfits__' not in request['fields']:
        raise ValueError('Complete selected form fields are required.')
    if digest(json.dumps(request['fields'], sort_keys=True, ensure_ascii=True, allow_nan=False,
                         separators=(',', ':')).encode('utf-8')) != request['render_sha256']:
        raise ValueError('Selected appearance differs from its render hash.')
    if request['preview_id'] is None and request['render_sha256'] != request['appearance_sha256']:
        raise ValueError('Unprepared appearance cannot replace the inspected owner.')
    return digest(canonical(request))


class Worker:
    def __init__(self, game, mods):
        if not WORKER.is_file():
            raise ValueError('Build the pinned preview worker first.')
        for path in (game, mods):
            no_redirected_ancestors(path)
            if not Path(path).is_dir(): raise ValueError('Explicit installed game and Mods directories required.')
        self.game, self.mods = str(Path(game).resolve()), str(Path(mods).resolve())
        # The independent assembler shares the user's RAM with the game. A
        # machine-wide default GC threshold can retain several GiB between
        # requests on high-memory PCs. Bound its managed heap to 2 GiB.
        environment = dict(os.environ, DOTNET_GCHeapHardLimit='80000000')
        self.process = subprocess.Popen([str(WORKER), str(game), str(mods)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding='utf-8',
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), cwd=WORKER.parent, env=environment)
        self.responses = queue.Queue(maxsize=2)
        self.lock = threading.Lock()
        self.reader = threading.Thread(target=self._read, daemon=True); self.reader.start()
        ready = self.responses.get(timeout=90)
        if ready.get('ready') is not True or ready.get('window_shown') is not False:
            self.close(); raise ValueError('Preview worker did not become ready: ' + str(ready.get('error', ''))[:1000])

    def _read(self):
        try:
            while True:
                line = self.process.stdout.readline(96 * 1024 * 1024 + 1)
                if not line: break
                if len(line) > 96 * 1024 * 1024:
                    raise ValueError('Worker response exceeds memory transport budget.')
                try: reply = json.loads(line)
                except ValueError: continue  # upstream DDS diagnostics are not protocol replies
                self.responses.put(reply, timeout=5)
        except Exception as error:
            self.responses.put({'ok': False, 'error': str(error)})
        finally:
            try: self.responses.put_nowait({'ok': False, 'error': 'Worker exited.'})
            except queue.Full: pass

    def assemble(self, request):
        with self.lock:
            if self.process.poll() is not None: raise ValueError('Preview worker exited; restart the preview service.')
            self.process.stdin.write(json.dumps(request, separators=(',', ':')) + '\n'); self.process.stdin.flush()
            try: result = self.responses.get(timeout=90)
            except queue.Empty:
                self.close(); raise ValueError('Preview assembly exceeded its deadline; no retry was submitted.')
            if result.get('ok') is not True or result.get('disk_assets_written') is not False:
                raise ValueError(result.get('error', 'Worker returned a writable/invalid scene.'))
            return result

    def close(self):
        if self.process.poll() is None:
            try: self.process.stdin.close(); self.process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired): self.process.kill(); self.process.wait(timeout=5)


class Broker:
    def __init__(self, worker, budget=MEMORY_BUDGET):
        if type(budget) is not int or not MAX_SCENE <= budget <= MEMORY_BUDGET:
            raise ValueError('Preview memory budget must be between 64 and 128 MiB.')
        self.worker, self.budget = worker, budget
        self.lock = threading.RLock()
        self.jobs = OrderedDict(); self.scenes = OrderedDict(); self.bytes = 0
        self.active = False

    def prepare(self, request):
        key = snapshot(request)
        with self.lock:
            if key in self.jobs:
                retained = self.jobs[key]
                if retained.get('state') == 'ready' and retained['scene_id'] not in self.scenes:
                    del self.jobs[key]
                else:
                    self.jobs.move_to_end(key)
                    return dict(retained, request_id=key)
            if self.active:
                raise ValueError('A scene is assembling; wait for its exact request ID before selecting another.')
            self.active = True
            self.jobs[key] = {'ok': True, 'state': 'assembling'}
            while len(self.jobs) > 32: self.jobs.popitem(last=False)
        threading.Thread(target=self._build, args=(key, request), daemon=True).start()
        return {'ok': True, 'request_id': key, 'state': 'assembling'}

    def _build(self, key, request):
        started = time.monotonic()
        try:
            result = self.worker.assemble(request)
            manifest = result['manifest_json'].encode('utf-8')
            ident = sha(result['manifest_sha256'])
            if digest(manifest) != ident or len(manifest) > 8 * 1024 * 1024: raise ValueError('Scene manifest changed.')
            scene = json.loads(manifest)
            if any(str(scene.get(field)) != str(request[field]) for field in ('sim_id', 'form', 'outfit_id', 'outfit_index')):
                raise ValueError('Assembled scene owner differs.')
            assets, expected = {}, {}
            for surface in scene['surfaces']:
                expected[surface['image']] = sha(surface['image_sha256'])
                if surface.get('specular'):
                    expected[surface['specular']] = sha(surface['specular_sha256'])
                for part in surface['parts']: expected[part['file']] = sha(part['sha256'])
            if set(result['assets']) != set(expected): raise ValueError('Scene asset inventory differs.')
            for name, value in result['assets'].items():
                if len(name) > 80 or not re.fullmatch(r'[a-z0-9-]+\.(mesh|png)', name): raise ValueError('Invalid scene asset name.')
                assets[name] = base64.b64decode(value, validate=True)
                if digest(assets[name]) != expected[name]: raise ValueError('Scene asset hash differs.')
            assets['scene.json'] = manifest
            size = sum(map(len, assets.values()))
            if size > MAX_SCENE: raise ValueError('Scene exceeds the cache budget.')
            with self.lock:
                if ident in self.scenes:
                    self.bytes -= self.scenes.pop(ident)['bytes']
                while self.scenes and self.bytes + size > self.budget:
                    _old, old = self.scenes.popitem(last=False); self.bytes -= old['bytes']
                self.scenes[ident] = {'assets': assets, 'bytes': size}; self.bytes += size
                self.jobs[key] = {'ok': True, 'state': 'ready', 'scene_id': ident,
                    'sim_id': request['sim_id'], 'form': request['form'], 'outfit_id': request['outfit_id'], 'outfit_index': request['outfit_index'],
                    'appearance_sha256': request['appearance_sha256'], 'lane': request['lane'],
                    'preview_id': request['preview_id'], 'render_sha256': request['render_sha256'],
                    'runtime_pid': request['runtime_pid'],
                    'seconds': time.monotonic()-started, 'bytes': size, 'disk_assets_written': False}
        except Exception as error:
            with self.lock: self.jobs[key] = {'ok': False, 'state': 'failed', 'reason': str(error)[:2000]}
        finally:
            with self.lock: self.active = False

    def status(self, key):
        with self.lock:
            result = self.jobs[sha(key)]
            if result.get('state') == 'ready' and result['scene_id'] not in self.scenes:
                return {'ok': False, 'state': 'evicted', 'reason': 'Memory cache evicted this scene; inspect the current owner again.'}
            return dict(result, request_id=key)

    def asset(self, ident, name):
        with self.lock:
            scene = self.scenes[sha(ident)]; self.scenes.move_to_end(ident)
            return scene['assets'][name]


def handler(broker):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)
        def log_message(self, *args): pass
        def allowed(self):
            host = '127.0.0.1:' + str(self.server.server_port)
            return self.headers.get('Host') == host and self.headers.get('Origin') in (None, 'http://' + host)
        def reply(self, status, value):
            raw = value if isinstance(value, bytes) else canonical(value)
            self.send_response(status); self.send_header('Content-Length', str(len(raw)))
            self.send_header('Content-Type', 'application/octet-stream' if isinstance(value, bytes) else 'application/json')
            self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(raw)
        def do_POST(self):
            try:
                if not self.allowed() or self.path != '/v1/preview/prepare' or self.headers.get('Content-Type') != 'application/json' or self.headers.get('Transfer-Encoding'):
                    raise ValueError('Bounded loopback preview protocol required.')
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= MAX_REQUEST: raise ValueError('Preview request exceeds bound.')
                raw = self.rfile.read(size)
                if len(raw) != size: raise ValueError('Truncated preview request.')
                self.reply(200, broker.prepare(json.loads(raw)))
            except (KeyError, ValueError, TypeError, OSError) as e: self.reply(409, {'ok': False, 'reason': str(e)})
        def do_GET(self):
            try:
                if not self.allowed(): raise ValueError('Loopback origin required.')
                status = re.fullmatch(r'/v1/preview/status/([0-9a-f]{64})', self.path)
                asset = re.fullmatch(r'/v1/scenes/([0-9a-f]{64})/([a-z0-9-]+\.(?:mesh|png)|scene\.json)', self.path)
                if status: self.reply(200, broker.status(status.group(1)))
                elif asset: self.reply(200, broker.asset(*asset.groups()))
                elif self.path == '/v1/preview/health':
                    with broker.lock: self.reply(200, dict(ok=True, scenes=len(broker.scenes), bytes=broker.bytes, budget=broker.budget,
                        active=broker.active, disk_assets_written=False, game_root=broker.worker.game, mods_root=broker.worker.mods))
                else: raise ValueError('Unknown typed preview route.')
            except (KeyError, ValueError, TypeError, OSError) as e: self.reply(409, {'ok': False, 'reason': str(e)})
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-root', required=True, type=Path)
    parser.add_argument('--mods-root', required=True, type=Path)
    args = parser.parse_args()
    worker = Worker(args.game_root, args.mods_root)
    try:
        with LoopbackHTTPServer(('127.0.0.1', PORT), handler(Broker(worker))) as server:
            server.daemon_threads = True
            print(json.dumps(dict(ok=True, endpoint='http://127.0.0.1:'+str(PORT), disk_assets_written=False)), flush=True)
            server.serve_forever()
    finally: worker.close()


if __name__ == '__main__': main()
