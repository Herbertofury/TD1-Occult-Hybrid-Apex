"""Retain the real DX11 backbuffer captured by the running game sidecar."""
import json
from pathlib import Path
import time
from source_manifest import sha256, write_json
import reusable_profile


def capture(state, output, request, monotonic=time.monotonic, pause=time.sleep, overlay=False):
    _, journal, profile, original = reusable_profile.load(state)
    output = reusable_profile.writable(output)
    if any(output == root or root in output.parents for root in (profile, original)):
        raise ValueError('Capture evidence must remain outside both profiles.')
    if output.suffix.lower() != '.bmp' or output.exists() or output.with_suffix('.json').exists():
        raise ValueError('Use a new external BMP evidence filename; previous evidence is retained.')
    directory = reusable_profile.writable(profile / 'TD1ApexScreenshots')
    pattern = 'TD1Apex_overlay_*.bmp' if overlay else 'TD1Apex_full_*.bmp'
    prior = {str(path): (path.stat().st_mtime_ns, path.stat().st_size) for path in directory.glob(pattern)} if directory.exists() else {}
    requested = request(state, 'test_capture', value=json.dumps({'test_token': journal['token'], 'value': 'overlay' if overlay else None}))
    if not requested.get('ok'):
        return requested
    deadline, previous = monotonic() + 5, None
    while monotonic() < deadline:
        after = request(state, 'overlay_status')
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
                output.parent.mkdir(parents=True, exist_ok=True)
                with output.open('xb') as stream:
                    stream.write(raw)
                proof = {'ok': True, 'capture_completed_verified': True, 'source': str(source),
                    'output': str(output), 'sha256': sha256(output), 'width': width, 'height': height,
                    'requested': requested, 'after': after,
                    'scope': 'Actual DX11 game backbuffer after Apex UI rendering.' if overlay else 'Actual DX11 game backbuffer before overlay; UI semantics require inspecting the image.'}
                write_json(output.with_suffix('.json'), proof)
                return proof
            previous = observed
        pause(0.1)
    return dict(requested, ok=False, outcome='unresolved', capture_completed_verified=False,
                message='One capture was submitted but a unique completed image was not observed; do not blindly repeat.')
