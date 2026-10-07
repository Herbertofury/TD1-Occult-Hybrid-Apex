"""EA launch handoff using installed metadata and the registered origin2 handler.

Only an exact isolated test session may launch. This cannot silently approve an
EA/Windows administrator prompt and does not implement a headless game engine.
"""
import os
from pathlib import Path
import re
import urllib.parse
from xml.etree import ElementTree
from source_manifest import sha256
import test_profile


def launch_plan(game_root, state):
    isolation = test_profile.status(state)
    if not isolation['ready_to_launch']:
        raise ValueError('Launch requires an exact isolated test profile.')
    root = test_profile.unlinked(game_root)
    launcher = test_profile.unlinked(root / 'Game' / 'Bin' / 'TS4_Launcher_x64.exe')
    executable = test_profile.unlinked(root / 'Game' / 'Bin' / 'TS4_x64.exe')
    manifest = test_profile.unlinked(root / '__Installer' / 'installerdata.xml')
    if not all(path.is_file() for path in (launcher, executable, manifest)):
        raise ValueError('The selected installation lacks the Sims 4 launcher/executable/EA manifest.')
    raw = manifest.read_bytes()
    if len(raw) > 1024 * 1024 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('Unsupported EA installation manifest.')
    metadata = ElementTree.fromstring(raw)
    version = metadata.find('./buildMetaData/gameVersion')
    ids = [node.text for node in metadata.findall('./contentIDs/contentID')]
    if not ids or len(ids) > 64 or any(not re.fullmatch(r'[0-9]{1,10}', value or '') for value in ids):
        raise ValueError('EA manifest content IDs are missing or unsafe; no launch URL will be guessed.')
    url = 'origin2://game/launch?' + urllib.parse.urlencode({'offerIds': ','.join(ids), 'autoDownload': '0'})
    return {'ok': True, 'launched': False, 'mode': 'ea-client-handoff',
            'url': url, 'game_version': version.get('version') if version is not None else None,
            'executable_sha256': sha256(executable), 'installer_manifest_sha256': sha256(manifest),
            'isolation': isolation, 'headless_game_runtime': False,
            'permission_prompts': 'EA/Windows may still require the owner to approve an administrator prompt.',
            'proof_scope': 'Validated launch plan only; success requires observed process and packaged bridge readiness.'}


def launch(game_root, state, execute=False, headless=False):
    if headless:
        raise ValueError('A headless Sims 4 runtime is not implemented. Use the real-game bridge for CLI testing.')
    plan = launch_plan(game_root, state)
    if execute:
        test_profile.require_closed()
        # Recheck immediately before handoff so no launch can use a restored/live profile.
        if not test_profile.status(state)['ready_to_launch']:
            raise ValueError('Test profile changed before launch.')
        if os.name != 'nt':
            raise RuntimeError('EA registered-protocol launch is supported only on Windows.')
        import winreg
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r'origin2\shell\open\command') as key:
            registered = winreg.QueryValueEx(key, None)[0]
        if not registered or 'EALauncher.exe' not in registered or '%1' not in registered:
            raise ValueError('The origin2 handler is not the expected installed EA launcher.')
        os.startfile(plan['url'])
        plan['launched'] = True
        plan['proof_scope'] = 'Launch handed to installed EA client; game/bridge readiness has not yet been proven.'
    return plan
