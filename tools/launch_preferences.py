"""Remember the successful, account-bound EA permission route.

This selects the existing one-shot helper through normal Windows elevation.
It never reuses a past PID, window, button coordinate or elevated process.
"""
import json
from pathlib import Path
import re

import reusable_profile
from source_manifest import write_json, sha256

NAME = 'ea-launch-permission-preference.json'


def bound(preference, account):
    return all(preference.get(name) == account.get(name) for name in ('offer_id','content_id','executable'))


def read(path):
    path = reusable_profile.writable(path)
    if not path.is_file() or not 0 < path.stat().st_size <= 4096:
        raise ValueError('Bounded launch preference/receipt required.')
    return json.loads(path.read_text(encoding='utf-8'))


def successful_receipt(work, name, expected=None):
    if not isinstance(name,str) or not re.fullmatch(r'ea-broker-[0-9a-f]{32}\.receipt\.json',name):
        raise ValueError('One verified EA permission receipt filename required.')
    receipt_path = work / name
    receipt = read(receipt_path)
    if expected is not None and sha256(receipt_path) != expected:
        raise ValueError('Remembered EA permission evidence changed.')
    request_path = receipt_path.with_name(name.replace('.receipt.json','.request.json'))
    request = read(request_path)
    from ea_permission_broker import validate_receipt
    validate_receipt(receipt,request,sha256(request_path))
    if receipt.get('ok') is not True or receipt.get('acknowledged') is not True:
        raise ValueError('Only an acknowledged, verified permission route can be remembered.')
    context = receipt['launch_context']
    return receipt_path, dict(offer_id=context['offer_id'],content_id=context['content_id'],executable=context['launcher'])


def remember(state, game_root, receipt_name):
    from game_launch import account_launch_identity
    work = Path(state).resolve().parent
    path, account = successful_receipt(work,receipt_name)
    if not bound(account,account_launch_identity(game_root)):
        raise ValueError('Permission receipt belongs to another account launch identity.')
    preference = dict(schema=1,mode='normal-uac-one-shot',receipt=path.name,
                      receipt_sha256=sha256(path),**account)
    write_json(reusable_profile.writable(work / NAME),preference)
    return dict(ok=True,preference=preference,windows_uac_automated=False)


def enabled(state, account):
    work = Path(state).resolve().parent
    path = work / NAME
    if not path.exists(): return False
    preference = read(path)
    if (not isinstance(preference,dict) or set(preference) !=
            {'schema','mode','receipt','receipt_sha256','offer_id','content_id','executable'} or
            preference['schema'] != 1 or preference['mode'] != 'normal-uac-one-shot' or
            not bound(preference,account)):
        raise ValueError('Remembered EA permission route differs from the verified account; inspect the preference.')
    _, historical = successful_receipt(work,preference['receipt'],preference['receipt_sha256'])
    if not bound(historical,account):
        raise ValueError('Remembered EA permission evidence belongs to another launch.')
    return True
