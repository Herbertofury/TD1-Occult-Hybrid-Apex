"""Bounded local Windows OCR for captured native game/EA windows."""
import json
import os
from pathlib import Path
import subprocess
from test_profile import unlinked


def recognize(path):
    if os.name != 'nt':
        raise RuntimeError('Native image OCR requires Windows.')
    path = unlinked(path)
    if not path.is_file() or not 0 < path.stat().st_size <= 32 * 1024 * 1024:
        raise ValueError('Use one bounded local capture.')
    script = Path(__file__).with_suffix('.ps1')
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-File', str(script)],
        input=json.dumps({'path': str(path)}), capture_output=True, text=True,
        encoding='utf-8', timeout=35, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise ValueError('Windows OCR failed: ' + result.stderr[-1500:])
    return json.loads(result.stdout)
