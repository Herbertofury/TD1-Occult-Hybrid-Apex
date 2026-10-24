"""Bind one native save submission to all prepared household sidecars.

Pure validation and preparation only. The game-thread save receiver supplies
the complete roster and native-verified member intents before writing once.
No appearance, native object, save file or runtime authority is restored here.
"""
import copy
import re

_UUID = re.compile(r'^[0-9a-f]{32}$')


def _id(value):
    return (isinstance(value, str) and value.isascii() and value.isdecimal() and
            0 < len(value) <= 20 and str(int(value)) == value and 0 < int(value) < 1 << 64)


def _key(value):
    parts = value.split(':') if isinstance(value, str) else []
    return len(parts) == 2 and all(_id(part) for part in parts)


def prepare(primary_key, roster, prepared):
    """Finish validation before any member intent is persisted.

    A Sim without an appearance bank needs no sidecar, but remains in the
    complete roster. Every prepared member belongs to this one native save.
    """
    if (not _key(primary_key) or not isinstance(roster, list) or not 1 <= len(roster) <= 8 or
            any(not _id(sid) for sid in roster) or len(set(roster)) != len(roster) or
            not isinstance(prepared, dict) or not 1 <= len(prepared) <= len(roster) or primary_key not in prepared):
        raise ValueError('A save group requires the exact primary, complete roster and prepared bank members.')
    primary = prepared[primary_key]
    if not isinstance(primary, dict) or not isinstance(primary.get('target'), dict):
        raise ValueError('A save group has no prepared native target.')
    target, identity = primary['target'], primary.get('identity')
    if (not isinstance(identity, dict) or not _id(target.get('save_guid')) or
            not _id(target.get('household_id')) or primary_key != target['save_guid'] + ':' + target.get('sim_id', '')):
        raise ValueError('The primary save-group identity differs from its native target.')
    ids, intents = set(), set()
    for key, row in prepared.items():
        if (not _key(key) or not isinstance(row, dict) or not isinstance(row.get('target'), dict) or
                row.get('state') != 'save-intent' or row.get('sealed') is not False or
                not isinstance(row.get('intent_id'), str) or _UUID.fullmatch(row['intent_id']) is None or
                row['intent_id'] in intents or row.get('identity') != identity or
                row.get('contract_sha256') != primary.get('contract_sha256') or
                row.get('before_file') != primary.get('before_file') or 'save_group' in row):
            raise ValueError('A prepared save-group member is foreign, duplicated or unresolved.')
        member = row['target']
        sid = member.get('sim_id')
        if (not _id(sid) or sid not in roster or sid in ids or key != target['save_guid'] + ':' + sid or
                set(member) != set(target) or
                any(member[name] != value for name, value in target.items() if name != 'sim_id')):
            raise ValueError('Prepared members must share the exact slot, file, save and household target.')
        ids.add(sid); intents.add(row['intent_id'])
    group = dict(schema=1, primary_key=primary_key, roster_sim_ids=sorted(roster, key=int),
                 member_intents={key: row['intent_id'] for key, row in sorted(prepared.items())})
    result = copy.deepcopy(prepared)
    for row in result.values():
        row['save_group'] = copy.deepcopy(group)
    return result


def members(records, primary_key, intent_id, states):
    """Return one exact retained group; never partially update its members."""
    primary = records.get(primary_key) if isinstance(records, dict) else None
    if (not isinstance(primary, dict) or primary.get('intent_id') != intent_id or
            not isinstance(states, (tuple, list, set)) or not states):
        raise ValueError('The retained save-group primary or allowed state is unavailable.')
    group = primary.get('save_group')
    if group is None:
        if primary.get('state') not in states:
            raise ValueError('The legacy save intent is not in the expected state.')
        return {primary_key: primary}
    if (not isinstance(group, dict) or set(group) != {'schema', 'primary_key', 'roster_sim_ids', 'member_intents'} or
            type(group.get('schema')) is not int or group['schema'] != 1 or group['primary_key'] != primary_key or
            not isinstance(group.get('member_intents'), dict) or primary_key not in group['member_intents']):
        raise ValueError('The retained household save group is malformed.')
    rows = {}
    for key, expected in group['member_intents'].items():
        row = records.get(key)
        if (not isinstance(row, dict) or row.get('intent_id') != expected or row.get('state') not in states or
                row.get('save_group') != group):
            raise ValueError('A retained household save member changed; no partial result is authorized.')
        rows[key] = row
    # Reuse the full native-target validation without accepting mutable state
    # differences as a reason to weaken the original group identity.
    candidate = copy.deepcopy(rows)
    for row in candidate.values():
        del row['save_group']; row['state'] = 'save-intent'; row['sealed'] = False
    checked = prepare(primary_key, group['roster_sim_ids'], candidate)
    if checked[primary_key]['save_group'] != group:
        raise ValueError('The retained household save group differs from its complete prepared identity.')
    return rows
