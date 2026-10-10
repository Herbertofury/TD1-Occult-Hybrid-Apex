"""Exercise native CAS panels without pointer input, acceptance or saving.

The complete registry is the default scope. Each response is retained in one
append-only, fsynced JSONL file. Catalog pages remain available without a total
item limit. An edit is attempted only for a returned exact native identity.
An unresolved request or uncertain mutation stops the run without cleanup.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

import cas_client
import reusable_profile
from cas_runtime_probe import OverlaySuppression, decimal_id
from source_manifest import sha256, write_json

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import cas_ui, cas_controls


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                       separators=(',', ':')) + '\n').encode('utf-8')


def panel_names(names):
    if names is None:
        return list(cas_ui.PANELS)
    if not isinstance(names, (list, tuple)) or not names:
        raise ValueError('Use mapped panels, or omit them for the complete registry.')
    reverse = {value: name for name, value in cas_ui.PANELS.items()}
    result = [reverse[cas_ui.panel(name)] for name in names]
    if len(set(result)) != len(result):
        raise ValueError('Do not repeat native panels through aliases.')
    return result


def context(client, sim_id):
    cas_ui.validate_client(client, sim_id, {'operation': 'status'})
    native = client.get('native_context', {})
    for field in ('edit_mode', 'new_family', 'entered_from_play_area'):
        if not isinstance(native.get(field), dict) or native[field].get('query') != 'returned-value':
            raise ValueError('Full CAS context query is unavailable: ' + field)
    if (type(native['edit_mode'].get('value')) is not int or native['edit_mode']['value'] not in (0, 7) or
            native['new_family'].get('value') is not False or
            not isinstance(native['entered_from_play_area'].get('value'), dict) or
            native['entered_from_play_area']['value'].get('result') is not True):
        raise ValueError('Workbench requires the existing-Sim full editor entered from Live.')
    full = client['native_context'].get('forced_full_edit')
    if not isinstance(full, dict) or full.get('query') != 'returned-value' or full.get('value') is not True:
        raise ValueError('The workbench requires actual native full-edit CAS.')
    sim = client['sim']
    keys = ('simId', 'householdId', 'speciesType', 'age', 'occultType', 'allOccultTypes', 'occultLayer')
    result = {key: sim.get(key) for key in keys}
    if not decimal_id(result['householdId']) or type(result['occultLayer']) is not int or result['occultLayer'] not in (0, 1):
        raise ValueError('Native CAS household identity is unavailable.')
    return result


def run(state, output, identity, request, sim_id, edit=False, panels=None, step_seconds=12):
    if not decimal_id(sim_id) or type(edit) is not bool:
        raise ValueError('Use an explicit existing Sim identity and typed edit option.')
    if type(step_seconds) not in (int, float) or not math.isfinite(step_seconds) or not 0 < step_seconds <= 60:
        raise ValueError('Each native acknowledgment needs a finite 0-60 second wait.')
    names = panel_names(panels)
    journal_path, journal, profile, original = reusable_profile.load(state)
    script = next((row['sha256'] for row in journal['artifacts'] if row['name'] == 'ApexOccultHybrid.ts4script'), None)
    if (identity.get('test_token') != journal['token'] or identity.get('script_sha256') != script or
            type(identity.get('pid')) is not int or identity['pid'] <= 0):
        raise ValueError('Workbench identity must match the installed disposable candidate.')
    output = reusable_profile.writable(output)
    raw_path = output.with_suffix('.jsonl')
    if (output.suffix != '.json' or not output.parent.is_dir() or output == journal_path or
            output.exists() or raw_path.exists() or any(output == p or p in output.parents for p in (profile, original))):
        raise ValueError('Use a new external JSON proof and adjacent JSONL file.')
    proof = {'schema': 1, 'operation': 'native-full-cas-workbench', 'ok': False,
        'identity': identity, 'sim_id': sim_id, 'edit_requested': edit, 'requested_panels': names,
        'native_panel_count': len(cas_ui.PANELS), 'raw_path': str(raw_path), 'steps': [],
        'panels': [], 'overlay_suppression': {}, 'input_submitted': False,
        'entry_submitted': False, 'accept_submitted': False, 'save_submitted': False,
        'no_request_replay': True, 'full_catalog_inventory': False,
        'live_retention_verified': False, 'all_edit_paths_complete': False,
        'scope': 'Native panel discovery and exact-item edits only; separate return, owner decisions, Live ticks, switches and reload are required.'}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(proof, stream)
    raw_stream = raw_path.open('xb')
    expected = None
    started = time.monotonic()

    def record():
        write_json(output, proof)

    def retain(operation, arguments, result):
        data = encoded({'operation': operation, 'arguments': arguments, 'result': result})
        offset = raw_stream.tell()
        raw_stream.write(data); raw_stream.flush(); os.fsync(raw_stream.fileno())
        with raw_path.open('rb') as checked:
            checked.seek(offset)
            if checked.read(len(data)) != data:
                raise OSError('Complete native response archive did not verify.')
        row = proof['steps'][-1]
        row.update(offset=offset, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), ok=result.get('ok'),
                   cas_request_id=result.get('cas_request_id'), request_id=result.get('request_id'),
                   message=result.get('message', result.get('error')), state='response-retained')
        record()
        return result

    def control(operation, allow_refusal=False, **arguments):
        step = {'operation': operation, 'arguments': arguments, 'state': 'intent-recorded', 'owner_requests': []}
        proof['steps'].append(step); record()
        def observed_request(current_state, action, *values, **options):
            def submitted(_action, request_id):
                step['owner_requests'].append({'action': _action, 'request_id': request_id, 'submitted_once': True})
                record()
            return request(current_state, action, *values, **options, submission_observer=submitted)
        options = SimpleNamespace(operation=operation, state=state, sim_id=sim_id,
                                  seconds=step_seconds, output=None, **arguments)
        result = cas_client.execute(options, observed_request)
        if not isinstance(result, dict):
            raise ValueError('Native response is not a complete record.')
        retain(operation, arguments, result)
        if result.get('ok') is not True:
            # A terminal, explicitly non-mutating query refusal can be recorded
            # as unavailable. Never continue after an ambiguous mutation/ACK.
            safe = operation in ('catalog', 'variants', 'swatches', 'layers', 'body-types', 'panel')
            if (allow_refusal and safe and result.get('cas_request_state') == 'failed' and
                    result.get('mutation_started') is False):
                return result
            raise RuntimeError('Native command failed or is unresolved; retain its original UUID: ' +
                               str(result.get('message', result.get('error', result.get('outcome')))))
        cas_ui.validate_client(result['client'], sim_id, dict(arguments, operation=operation))
        current = context(result['client'], sim_id)
        if expected is not None and current != expected:
            raise ValueError('Original Sim/household/form context changed; no further native commands.')
        return result

    overlay = OverlaySuppression(lambda action: request(state, action), proof['overlay_suppression'], record)
    try:
        overlay.suppress()
        initial = control('status')
        expected = context(initial['client'], sim_id)
        proof['original_context'] = expected; record()
        for name in names:
            item = {'panel': name, 'menu_state': cas_ui.PANELS[name], 'discovered': False,
                    'edit_verified_in_cas': False, 'outcome': 'not-observed'}
            proof['panels'].append(item); record()
            if name == 'profile_body_skincolor':
                opened = control('panel', panel=name)
                found = control('swatches', swatch_type=0, offset=0, limit=8)
            else:
                found = control('catalog', allow_refusal=True, panel=name, offset=0, limit=8)
            if found.get('ok') is not True:
                item.update(outcome='native-query-unavailable', message=proof['steps'][-1]['message']); record(); continue
            client, data = found['client'], found['client']['control']
            item.update(discovered=True, catalog_total=data['total'], outcome='catalog-discovered',
                        first_page_items=len(data['items']))
            record()
            if not edit:
                continue
            if name == 'clothing_looks':
                item['outcome'] = 'featured-look-edit-contract-pending'; record(); continue
            if name in ('clothing_head_tattoos', 'clothing_body_tattoos'):
                item['outcome'] = 'use-explicit-region-and-layer-controls'; record(); continue
            rows, offset = data['items'], 0
            equipped = {str(row.get('dataID')) for row in client.get('selected') or []}
            preset = next(row for row in client['catalogs'] if row['panel'] == name)['preset']
            preset_index = preset.get('index') if isinstance(preset, dict) else None
            palette_selected = data.get('selected')
            if isinstance(palette_selected, dict): palette_selected = palette_selected.get('dataID')
            chosen = None
            while True:
                for at, row in enumerate(rows):
                    key = 'dataID' if name == 'profile_body_skincolor' else 'data_id'
                    native_id = row.get(key)
                    if (isinstance(native_id, str) and decimal_id(native_id) and native_id not in equipped and
                            native_id != palette_selected and (not name.startswith('profile_') or offset+at != preset_index)):
                        chosen = native_id; break
                if chosen is not None or offset+len(rows) >= data['total']:
                    break
                offset += len(rows)
                if not rows:
                    raise ValueError('Native catalog page stopped before its advertised total.')
                page = control('swatches', swatch_type=0, offset=offset, limit=8) if name == 'profile_body_skincolor' else control('catalog', panel=name, offset=offset, limit=8)
                data = page['client']['control']; rows = data['items']
            if chosen is None:
                item['outcome'] = 'no-different-native-item'; record(); continue
            if name == 'profile_body_skincolor':
                applied = control('swatch', swatch_type=0, data_id=chosen, color_index=0)
            elif name.startswith('profile_') and name not in cas_controls.PART_PROFILE_PANELS:
                applied = control('preset', panel=name, data_id=chosen)
            else:
                family = control('variants', panel=name, data_id=chosen)['client']['control']['family']
                variants = family.get('mItems')
                if not isinstance(variants, list):
                    raise ValueError('Native color family does not have its complete returned variant array.')
                identities = [row['dataID'] for row in variants if isinstance(row, dict) and
                              isinstance(row.get('dataID'), str) and decimal_id(row['dataID']) and row['dataID'] not in equipped]
                if not identities:
                    item['outcome'] = 'no-different-native-variant'; record(); continue
                chosen = identities[0]
                applied = control('select', panel=name, data_id=chosen)
            item.update(edit_verified_in_cas=True, selected_data_id=chosen, outcome='native-edit-acknowledged',
                        cas_request_id=applied['cas_request_id']); record()
        proof.update(ok=True, outcome='completed-discovery-and-scoped-edits',
                     all_requested_panels_observed=len(proof['panels']) == len(names),
                     edited_panels=[row['panel'] for row in proof['panels'] if row['edit_verified_in_cas']])
    except (OSError, ValueError, RuntimeError) as error:
        proof.update(ok=False, outcome='stopped-with-retained-evidence', error=str(error))
    finally:
        raw_stream.close()
        proof.update(elapsed_seconds=round(time.monotonic()-started, 3), raw_sha256=sha256(raw_path))
        record()
    return {key: proof.get(key) for key in ('ok', 'outcome', 'error', 'elapsed_seconds', 'edited_panels',
                 'all_requested_panels_observed')} | {'proof': str(output), 'proof_sha256': sha256(output),
                    'raw_sha256': proof['raw_sha256'], 'panel_count': len(proof['panels'])}
