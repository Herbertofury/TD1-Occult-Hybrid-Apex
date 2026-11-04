"""Whole-roster appearance regression, with evidence before every mutation.

Uses the authenticated disposable game's bridge, never foreground input.
CAS coverage cells remain untested until actual native edits prove them.
Capture/verify/cycle preserve full packets and compare every readable field.
"""
import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import reusable_profile
from source_manifest import sha256, write_json
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core.cas_panels import PANELS
from apex_core import form_appearance as appearance, outfit_snapshot as outfit_wire

FORMS = (1, 2, 4, 8, 16, 32, 64)
CYCLE = (2, 4, 2, 8, 32, 64, 16, 1, 2)
NAMES = {2: 'alien', 4: 'vampire', 8: 'mermaid', 32: 'werewolf', 64: 'fairy', 16: 'witch'}


def roster(value):
    if (not isinstance(value, list) or not 1 <= len(value) <= 8 or len(set(value)) != len(value) or
            any(not isinstance(sid, str) or not sid.isascii() or not sid.isdecimal() or
                str(int(sid)) != sid or not 0 < int(sid) < 1 << 64 for sid in value)):
        raise ValueError('Use the entire unique existing household roster of canonical Sim IDs.')
    return value


def plan(ids):
    roster(ids)
    return {'schema': 1, 'ok': True, 'operation': 'household-stress-coverage-plan', 'sim_ids': ids,
            'forms': list(FORMS), 'panels': sorted(PANELS),
            'cells': [{'sim_id': sid, 'form': form, 'panel': panel, 'scope': scope, 'state': 'untested'}
                      for scope in ('single-member-edit', 'whole-household-edit')
                      for sid in ids for form in FORMS for panel in sorted(PANELS)],
            'lifecycle_gates': {name: 'untested' for name in
                ('alien-vampire-alien', 'all-form-cycles', 'full-cas-return', 'mccc-cas-return',
                 'household-exit-reentry', 'normal-save-cold-reload', 'tray-household-reload')},
            'outfit_scope': 'Every native returned category and ordinal; absent outfits must be reported.',
            'additional_controls': {name: 'untested' for name in
                ('presets', 'voice', 'walkstyle', 'body-face-modifiers', 'traits', 'gender',
                 'detail-mode', 'colors', 'tattoo-layers', 'hair-isolation', 'unknown-new-fields')},
            'acceptance_complete': False, 'native_edit_submitted': False}


def owners(snapshot):
    sim = snapshot['sim']; result = {}
    for row in sim['form_appearances']:
        key = str(row['flags'])
        if key in result:
            raise ValueError('Duplicate native stored appearance owner.')
        result[key] = row['appearance']
    result['active'] = sim['full_appearance']
    return result


def validate(snapshot, sid, ids, household, guid):
    if (snapshot.get('ok') is not True or snapshot.get('household_id') != household or
            snapshot.get('save_guid') != guid or snapshot.get('zone_running') is not True or
            snapshot.get('in_build_buy') is not False or snapshot.get('clock_speed') != 0 or
            snapshot.get('sim', {}).get('id') != sid or
            set(snapshot.get('persistence', {}).get('household_sim_ids', [])) != set(ids) or
            {row['flags'] for row in snapshot['sim']['membership']} != set(FORMS) - {1} or
            set(owners(snapshot)) != {str(kind) for kind in FORMS} | {'active'}):
        raise ValueError('Native paused household/Sim/membership/appearance inventory differs; no stress mutation.')
    for row in owners(snapshot).values():
        if (not isinstance(row.get('field_sha256'), dict) or
                set(row['field_sha256']) != set(row.get('typed_payload', {})) or
                '__outfits__' not in row['field_sha256']):
            raise ValueError('Every native returned field and its complete payload must be retained.')


def _outfit_rows(payload):
    raw = appearance.decode(payload['typed_payload']['__outfits__'])[1]
    offset, rows, other = 0, {}, []
    while offset < len(raw):
        start = offset
        number, kind, offset, value = outfit_wire.field(raw, offset)
        if number == 1:
            if kind != 2:
                raise ValueError('Outfit row wire differs.')
            rows.setdefault(outfit_wire.category(value), []).append(value)
        else:
            other.append(raw[start:offset])
    return rows, other


def appended_outfits(before, after):
    """Allow only exact existing rows plus bounded native append-only rows."""
    a, old_other = _outfit_rows(before); b, new_other = _outfit_rows(after)
    if old_other != new_other or any(b.get(category, [])[:len(rows)] != rows for category, rows in a.items()):
        raise ValueError('Existing outfit/index or unknown root bytes changed.')
    added = [{'category': category, 'index': i, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
             for category, rows in b.items() for i, raw in enumerate(rows) if i >= len(a.get(category, []))]
    if not 0 < len(added) <= 32:
        raise ValueError('Outfit delta is not a bounded nonempty native append.')
    return added


def initialized_empty_outfits(before, after):
    """Recognize EA filling a zero-ID, part-free placeholder, never an edit."""
    def fields(raw):
        offset, rows = 0, []
        while offset < len(raw):
            start = offset
            n, wire, offset, value = outfit_wire.field(raw, offset)
            rows.append((n, wire, value, raw[start:offset]))
        return rows
    a, old_other = _outfit_rows(before); b, new_other = _outfit_rows(after)
    if old_other != new_other:
        raise ValueError('Unknown outfit root bytes changed.')
    generated, initialized = [], 0
    for category, old_rows in a.items():
        new_rows = b.get(category, [])
        if len(new_rows) < len(old_rows):
            raise ValueError('An existing outfit index was removed.')
        for index, old in enumerate(old_rows):
            new = new_rows[index]
            if old == new:
                continue
            x, y = fields(old), fields(new)
            uid_before = [r for r in x if r[0] == 1]
            uid_after = [r for r in y if r[0] == 1]
            parts_before = [r for r in x if r[0] == 5]
            parts_after = [r for r in y if r[0] == 5]
            if (len(uid_before) != 1 or uid_before[0][1:3] != (0, 0) or
                    len(uid_after) != 1 or uid_after[0][1] != 0 or not 0 < uid_after[0][2] < 1 << 64 or
                    any(r[1] != 2 or r[2] != b'' for r in parts_before) or len(parts_before) > 1 or
                    len(parts_after) != 1 or parts_after[0][1] != 2 or not parts_after[0][2]):
                raise ValueError('Existing outfit is not an empty native zero-ID placeholder.')
            # Preserve every other existing field's complete bytes and order.
            # Only the inspected OutfitData generation fields may be added.
            old_numbers = {r[0] for r in x}
            existing_x = [r[3] for r in x if r[0] not in (1, 5)]
            existing_y = [r[3] for r in y if r[0] in old_numbers and r[0] not in (1, 5)]
            added = [r for r in y if r[0] not in old_numbers]
            if (existing_x != existing_y or
                    len({r[0] for r in added}) != len(added) or
                    any(n not in (5, 6, 7, 12, 14, 15) or wire != (0 if n == 6 else 2)
                        for n, wire, _v, _raw in added)):
                raise ValueError('Generation replaced existing metadata or added unknown fields.')
            generated.append({'category': category, 'index': index, 'kind': 'initialized-empty-native-outfit',
                'before_sha256': hashlib.sha256(old).hexdigest(), 'after_sha256': hashlib.sha256(new).hexdigest(),
                'native_outfit_id': str(uid_after[0][2]), 'existing_fields_and_unknown_bytes_preserved': True})
            initialized += 1
    generated.extend({'category': c, 'index': i, 'kind': 'appended-native-outfit',
                      'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
                     for c, rows in b.items() for i, raw in enumerate(rows) if i >= len(a.get(c, [])))
    if not initialized or len(generated) > 32:
        raise ValueError('No bounded native placeholder initialization was proved.')
    return generated


def differences(left, right, include_active=True, native_appends=None):
    result = []
    for sid in sorted(set(left) | set(right)):
        if sid not in left or sid not in right:
            result.append({'sim_id': sid, 'roster_changed': True}); continue
        a, b = owners(left[sid]), owners(right[sid])
        for lane in sorted(set(a) | set(b)):
            if lane == 'active' and not include_active:
                continue
            if lane not in a or lane not in b:
                result.append({'sim_id': sid, 'lane': lane, 'owner_inventory_changed': True}); continue
            old, new = a[lane]['field_sha256'], b[lane]['field_sha256']
            changed = {name: {'before': old.get(name), 'after': new.get(name)}
                       for name in sorted(set(old) | set(new)) if old.get(name) != new.get(name)}
            if native_appends is not None and lane == 'active' and set(changed) == {'__outfits__'}:
                try:
                    added = appended_outfits(a[lane], b[lane])
                except ValueError:
                    try:
                        added = initialized_empty_outfits(a[lane], b[lane])
                    except ValueError:
                        added = None  # Destructive/unknown changes remain failures.
                if added is not None:
                    native_appends.append({'sim_id': sid, 'lane': lane, 'rows': added})
                    changed = {}
            if changed:
                result.append({'sim_id': sid, 'lane': lane, 'fields': changed})
        for name in ('membership', 'current_form'):
            if left[sid]['sim'][name] != right[sid]['sim'][name]:
                result.append({'sim_id': sid, 'context': name,
                               'before': left[sid]['sim'][name], 'after': right[sid]['sim'][name]})
    return result


def retained_companion_transitions(before, after, selected):
    """Accept only complete observed source/target retention, never a waiver."""
    expected, transitions = copy.deepcopy(before), []
    for sid in before:
        if sid == selected or sid not in after:
            continue
        source = before[sid]['sim']['current_form']
        target = after[sid]['sim']['current_form']
        if source == target:
            continue
        if source not in FORMS or target not in FORMS:
            raise ValueError('Unselected Sim changed to an unknown/composite form.')
        row = copy.deepcopy(before[sid])
        for owner in row['sim']['form_appearances']:
            if owner['flags'] == source:
                owner['appearance'] = copy.deepcopy(before[sid]['sim']['full_appearance'])
        row['sim']['current_form'] = target
        row['sim']['full_appearance'] = copy.deepcopy(owners(before[sid])[str(target)])
        generated = []
        changed = differences({sid: row}, {sid: after[sid]}, native_appends=generated)
        if changed:
            raise ValueError('Unselected form transition lost source edits, target identity or another owner.')
        expected[sid] = row
        transitions.append({'sim_id': sid, 'source_form': source, 'target_form': target,
            'complete_source_target_retention_verified': True, 'all_other_stored_fields_verified': True,
            'native_generated_outfits': generated, 'cli_switch_submitted_for_this_sim': False,
            'transition_trigger_proved': False})
    return expected, transitions


def run(args, request=None, identity_provider=None, pause=time.sleep):
    from apex_cli import owned_request, verified_identity
    request = request or owned_request; identity_provider = identity_provider or verified_identity
    _, journal, active, original = reusable_profile.load(args.state)
    dest = reusable_profile.writable(args.output)
    if (dest.exists() or dest.suffix.lower() != '.json' or
            any(dest == p or p in dest.parents for p in (active, original))):
        raise ValueError('Use one new external stress receipt in the existing evidence directory.')
    ids = roster(args.sim_ids)
    if args.operation == 'plan':
        proof = plan(ids); write_json(dest, proof); return dict(proof, output=str(dest))
    identity = identity_provider(args.state)
    proof = {'schema': 1, 'ok': False, 'operation': args.operation, 'identity': identity,
             'sim_ids': ids, 'household_id': args.household_id, 'save_guid': args.save_guid,
             'before': {}, 'steps': [], 'differences': [], 'save_submitted': False,
             'cas_edit_submitted': False, 'automatic_replay_allowed': False,
             'all_categories_edited_verified': False}
    write_json(dest, proof)
    envelope = lambda value: json.dumps({'test_token': journal['token'], 'value': value})
    def snapshot_all():
        rows = {}
        for sid in ids:
            row = request(args.state, 'test_snapshot', sid, value=envelope('forms'))
            validate(row, sid, ids, args.household_id, args.save_guid); rows[sid] = row
        return rows
    def current_process():
        current = identity_provider(args.state)
        if any(current.get(key) != identity.get(key) for key in ('pid', 'script_sha256', 'test_token')):
            raise ValueError('Stress test lost its exact runtime/profile/script; no further mutation.')
    try:
        proof['before'] = snapshot_all(); write_json(dest, proof)
        if args.operation == 'capture':
            proof['ok'] = True
        elif args.operation == 'verify':
            if args.baseline is None or sha256(args.baseline) != args.baseline_sha256:
                raise ValueError('Use the exact immutable prior whole-household capture and hash.')
            raw = args.baseline.read_bytes()
            if len(raw) > 64 * 1024 * 1024:
                raise ValueError('Baseline exceeds the complete-record bound.')
            baseline = json.loads(raw.decode('utf-8'))
            if (baseline.get('ok') is not True or set(baseline.get('before', {})) != set(ids) or
                    baseline.get('household_id') != args.household_id or baseline.get('save_guid') != args.save_guid):
                raise ValueError('Baseline roster/household/GUID differs; no partial verification.')
            proof['baseline_sha256'] = args.baseline_sha256
            proof['differences'] = differences(baseline['before'], proof['before'])
            proof['ok'] = not proof['differences']
        elif args.operation == 'cycle':
            if (type(args.settle_seconds) not in (int, float) or not math.isfinite(args.settle_seconds) or
                    not .1 <= args.settle_seconds <= 30):
                raise ValueError('Use bounded real simulation settling time.')
            for sid in ids:
                for target in CYCLE:
                    current_process()
                    before = snapshot_all()
                    step = {'sim_id': sid, 'target_form': target, 'before': before,
                            'mutation_request_id': None, 'mutation_submitted': None, 'ok': False}
                    proof['steps'].append(step); write_json(dest, proof)
                    def intent(action, rid):
                        step.update(action=action, mutation_request_id=rid); write_json(dest, proof)
                    step['reply'] = request(args.state, 'human' if target == 1 else 'switch', sid,
                        occult=NAMES.get(target), submission_observer=intent)
                    step['mutation_submitted'] = True; write_json(dest, proof)
                    if step['reply'].get('ok') is not True:
                        raise ValueError('Native switch failed or is unresolved; no retry submitted.')
                    try:
                        played = request(args.state, 'test_play', ids[0], value=envelope(None))
                        if played.get('ok') is not True:
                            raise ValueError('Native simulation did not start.')
                        pause(args.settle_seconds)
                    finally:
                        paused = request(args.state, 'test_pause', ids[0], value=envelope(None))
                        step['final_paused'] = paused.get('ok') is True; write_json(dest, proof)
                    after = snapshot_all(); step['after'] = after
                    step['sim_ticks_advanced'] = int(after[sid]['sim_now_ticks']) - int(before[sid]['sim_now_ticks'])
                    # The departing form owns its fresh active edits. Every
                    # other stored owner and every unselected Sim stay exact.
                    expected = copy.deepcopy(before)
                    expected, step['unselected_retained_transitions'] = retained_companion_transitions(before, after, sid)
                    departing = before[sid]['sim']['current_form']
                    for row in expected[sid]['sim']['form_appearances']:
                        if row['flags'] == departing:
                            row['appearance'] = copy.deepcopy(before[sid]['sim']['full_appearance'])
                    expected[sid]['sim']['current_form'] = target
                    expected[sid]['sim']['full_appearance'] = copy.deepcopy(owners(before[sid])[str(target)])
                    step['native_outfits_appended'] = []
                    step['differences'] = differences(expected, after,
                        native_appends=step['native_outfits_appended'] if step['sim_ticks_advanced'] > 0 else None)
                    step['ok'] = (not step['differences'] and step['sim_ticks_advanced'] > 0 and step['final_paused'])
                    write_json(dest, proof)
                    if not step['ok']:
                        raise ValueError('Whole-household appearance or simulation postcondition failed; originals retained.')
            proof['ok'] = True
        else:
            raise ValueError('Unknown whole-household stress operation.')
    except (ValueError, RuntimeError, OSError, KeyError, TypeError) as error:
        proof['error'] = str(error)
    write_json(dest, proof)
    return {'ok': proof['ok'], 'operation': args.operation, 'steps': len(proof['steps']),
            'differences': proof['differences'], 'error': proof.get('error'),
            'output': str(dest), 'proof_sha256': sha256(dest), 'all_categories_edited_verified': False}
