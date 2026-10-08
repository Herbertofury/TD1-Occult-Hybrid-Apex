"""Closed-game-only overlay autostart override for the pinned test profile."""
import configparser
import copy
import hashlib
import json
from pathlib import Path
import re

import reusable_profile as profiles
import test_profile
from source_manifest import sha256

RELATIVE = 'Apex/Native/ApexOverlay.ini'
MAX_BYTES = 16384
AUTOSTART_LINE = re.compile(r'^([ \t]*AutoStart[ \t]*=[ \t]*)([01])([ \t]*\r?)$', re.MULTILINE)


def edited_ini(raw, enabled):
    """Change only one canonical 0/1 value, preserving all other bytes."""
    if type(enabled) is not bool:
        raise ValueError('Overlay autostart must be on or off.')
    if len(raw) > MAX_BYTES:
        raise ValueError('Overlay configuration exceeds its bound.')
    try:
        text = raw.decode('utf-8', 'strict')
        parser = configparser.ConfigParser(interpolation=None, strict=True)
        parser.optionxform = str
        parser.read_string(text)
    except (UnicodeError, configparser.Error) as error:
        raise ValueError('Overlay configuration is not an unambiguous UTF-8 INI.') from error
    if (parser.sections() != ['Overlay'] or parser.defaults() or
            set(parser['Overlay']) != {'AutoStart', 'ToggleKey'}):
        raise ValueError('Expected only canonical Overlay.AutoStart and Overlay.ToggleKey settings.')
    matches = list(AUTOSTART_LINE.finditer(text))
    if len(matches) != 1 or parser.get('Overlay', 'AutoStart') != matches[0].group(2):
        raise ValueError('Expected exactly one canonical AutoStart=0 or AutoStart=1 line.')
    if not re.fullmatch(r'F(?:[1-9]|1[0-9]|2[0-4])', parser.get('Overlay', 'ToggleKey')):
        raise ValueError('Overlay ToggleKey must retain a supported canonical function key.')
    match = matches[0]
    replacement = '1' if enabled else '0'
    result = (text[:match.start(2)] + replacement + text[match.end(2):]).encode('utf-8')
    if len(result) != len(raw):
        raise ValueError('Overlay override unexpectedly changes configuration length.')
    return result, match.group(2) == '1'


def blob(path, raw, digest):
    path = profiles.writable(path)
    if not path.exists():
        with path.open('xb') as stream:
            stream.write(raw)
    if path.stat().st_size != len(raw) or sha256(path) != digest:
        raise ValueError('Content-addressed overlay configuration recovery verification failed.')
    return path


@profiles.serialized
def configure(state, enabled, guard=test_profile.require_closed):
    """Install the complete unchanged inventory with just one INI row replaced."""
    guard()
    state, data, profile, _original = profiles.load(state)
    before_status = profiles.status(state)
    if not before_status['ready_to_launch']:
        raise ValueError('Exact pinned test artifacts are required before changing overlay configuration.')
    candidates = [row for row in data['artifacts'] if profiles.artifact_relative(row) == RELATIVE]
    if len(candidates) != 1:
        raise ValueError('The journal must pin exactly one native overlay INI artifact.')
    prior = candidates[0]
    target = profiles.writable(profile / 'Mods' / RELATIVE)
    with target.open('rb') as stream:
        original = stream.read(MAX_BYTES + 1)
    if hashlib.sha256(original).hexdigest() != prior['sha256']:
        raise ValueError('Overlay INI differs from its exact journal hash; no configuration changed.')
    updated, was_enabled = edited_ini(original, enabled)
    base = {'overlay_autostart_enabled': enabled, 'setting': 'Overlay.AutoStart', 'original_written': False,
            'saves_written': False, 'complete_bundle_verified': False,
            'bundle_receipt_scope': 'Original candidate ZIP identity; configuration override is tracked separately.'}
    if updated == original:
        return dict(before_status, **base, changed=False, configuration_override=prior.get('configuration_override'))

    digest = hashlib.sha256(updated).hexdigest()
    row = copy.deepcopy(prior)
    row.update(sha256=digest, bytes=len(updated))
    recovery = profiles.writable(state.parent / 'artifact-recovery')
    guard()
    recovery.mkdir(exist_ok=True)
    source = blob(profiles.recovery_path(state, row, incoming=True), updated, digest)
    row['source'] = str(source)
    receipt = {'schema': 1, 'operation': 'overlay-autostart', 'test_token': data['token'],
               'journal': str(state), 'journal_generation_before': data['generation'], 'relative': RELATIVE,
               'setting': 'Overlay.AutoStart', 'before_enabled': was_enabled, 'enabled': enabled,
               'before_sha256': prior['sha256'], 'expected_installed_sha256': digest,
               'configuration_blob': str(source), 'baseline_bundle': copy.deepcopy(data.get('bundle')),
               'previous_override': copy.deepcopy(prior.get('configuration_override')),
               'scope': 'One INI setting only; full candidate ZIP equivalence is not asserted.'}
    receipt_raw = (json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + '\n').encode('utf-8')
    receipt_digest = hashlib.sha256(receipt_raw).hexdigest()
    receipt_path = blob(recovery / ('overlay-autostart-' + receipt_digest + '.json'), receipt_raw, receipt_digest)
    row['configuration_override'] = {'operation': 'overlay-autostart', 'enabled': enabled,
                                     'receipt': str(receipt_path), 'receipt_sha256': receipt_digest,
                                     'baseline_bundle_sha256': (data.get('bundle') or {}).get('sha256')}
    # install_rows retires omitted artifacts. Retain every other row, including
    # MCCC, optional packages, future row metadata and their exact source/hash.
    incoming = [row if existing is prior else copy.deepcopy(existing) for existing in data['artifacts']]
    result = profiles.install_rows(state, incoming, guard)
    if not result['ready_to_launch'] or sha256(target) != digest:
        raise RuntimeError('Overlay configuration did not verify after the pinned installation.')
    return dict(result, **base, changed=True, configuration_sha256=digest,
                configuration_override=row['configuration_override'])
