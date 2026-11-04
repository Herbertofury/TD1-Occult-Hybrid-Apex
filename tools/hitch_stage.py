"""Strict identities for cumulative, separately prepared hitch experiments.

These are observed-state declarations, not an installer or proof that a package
was actually loaded. No game, profile, save, or runtime code is changed here.
"""
import hashlib
import json
from pathlib import PurePosixPath
import re

FLAGS = ('apex_script_loaded', 'apex_cas_package_loaded', 'apex_overlay_loaded')
ID = re.compile(r'[a-z][a-z0-9-]{0,63}\Z')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=True, allow_nan=False).encode('ascii')).hexdigest()


def validate_definition(value):
    if not isinstance(value, dict) or set(value) != {'id', 'features', 'artifacts', 'loaded'}:
        raise ValueError('Stage needs exact id, features, artifacts and loaded fields.')
    if not isinstance(value['id'], str) or not ID.fullmatch(value['id']):
        raise ValueError('Invalid stage id.')
    features = value['features']
    if (not isinstance(features, list) or len(features) > 100 or
            any(not isinstance(x, str) or not ID.fullmatch(x) for x in features) or
            features != sorted(set(features))):
        raise ValueError('Feature ids must be sorted and unique.')
    loaded = value['loaded']
    if (not isinstance(loaded, dict) or set(loaded) != set(FLAGS) or
            any(type(loaded[k]) is not bool for k in FLAGS)):
        raise ValueError('Each loaded component needs an exact Boolean.')
    artifacts = value['artifacts']
    if not isinstance(artifacts, list) or len(artifacts) > 1000:
        raise ValueError('Bounded exact artifact inventory required.')
    names = []
    for row in artifacts:
        if not isinstance(row, dict) or set(row) != {'path', 'sha256'}:
            raise ValueError('Each artifact needs only path and SHA-256.')
        name = row['path']
        if (not isinstance(name, str) or not name or '\\' in name or ':' in name or
                any(c in name for c in '<>"|?*') or
                name.startswith('/') or any(p in ('', '.', '..') for p in name.split('/')) or
                any(p.rstrip(' .') != p for p in name.split('/')) or
                PurePosixPath(name).as_posix() != name):
            raise ValueError('Artifact paths must be canonical relative paths.')
        if not isinstance(row['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', row['sha256']):
            raise ValueError('Artifact SHA-256 required.')
        names.append(name.casefold())
    if names != sorted(set(names)):
        raise ValueError('Artifact paths must be sorted and unique, including Windows case aliases.')
    if not features:
        if artifacts or any(loaded.values()):
            raise ValueError('The no-mod control must have no Apex artifacts or loaded components.')
    elif not artifacts or not any(loaded.values()):
        raise ValueError('A feature stage needs its artifact identity and an observed loaded component.')
    return value


def validate_mod_state(value, pid, creation):
    if (not isinstance(value, dict) or type(value.get('schema')) is not int or value['schema'] != 2 or
            type(value.get('target_pid')) is not int or value['target_pid'] != pid or
            type(value.get('process_creation_filetime')) is not int or value['process_creation_filetime'] != creation or
            value.get('inventory_and_loaded_modules_observed') is not True or
            not isinstance(value.get('observation_method'), str) or not value['observation_method'].strip() or
            not isinstance(value.get('other_mods_sha256'), str) or
            not re.fullmatch('[0-9a-f]{64}', value['other_mods_sha256'])):
        raise ValueError('Stage state needs PID/creation-bound observed mod evidence.')
    stage = validate_definition(value.get('stage'))
    if any(value.get(k) is not stage['loaded'][k] for k in FLAGS):
        raise ValueError('Observed components differ from the pinned stage.')
    if value.get('stage_sha256') != digest(stage):
        raise ValueError('Stage identity differs from its exact feature/artifact inventory.')
    if stage['loaded']['apex_overlay_loaded']:
        service = value.get('native_service_profile')
        gfx = value.get('native_gfx_snapshot_profile')
        if (not isinstance(service, dict) or service.get('enabled') is not False or
                service.get('installed') is not False or type(service.get('inflight')) is not int or service['inflight'] != 0 or
                not isinstance(gfx, dict) or gfx.get('enabled') is not False or gfx.get('prepared') is not False or
                gfx.get('active_heap_hooks') is not False or type(gfx.get('inflight')) is not int or gfx['inflight'] != 0):
            raise ValueError('Stage diagnostic profilers must be inactive and uninstalled.')
    return stage


def validate_ladder(stages):
    if not isinstance(stages, list) or not 2 <= len(stages) <= 40:
        raise ValueError('Require a bounded no-mod control and incremental feature stages.')
    for stage in stages:
        validate_definition(stage)
    if stages[0]['features'] or len({s['id'] for s in stages}) != len(stages):
        raise ValueError('Start with a no-mod control and use distinct stage ids.')
    for previous, current in zip(stages, stages[1:]):
        old, new = set(previous['features']), set(current['features'])
        if not old < new or len(new - old) != 1:
            raise ValueError('Add exactly one feature group without removing earlier functionality.')
    return stages
