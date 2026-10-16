"""Complete a real local Library export from reviewed canonical appearances.

Only an external candidate is created. Native metadata, identities, portraits,
household fields and unknown wire fields outside the selected appearance
owners stay intact. Installing or loading it is a separate validation step.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import struct
import zipfile

from household_cli import blob, replace
from live_color_probe import chunks
from source_manifest import write_json
import tray_library
import reusable_profile

ACTIVE = ('flags', 'physique', 'facial_attr', 'skin_tone', 'skin_tone_val_shift',
          'pelt_layers', 'genetic_data', 'custom_texture', 'parts_custom_tattoos',
          'voice_pitch', 'voice_actor', 'voice_effect', 'outfits')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def wire_map(raw):
    result = {}
    for number, kind, value, wire in chunks(raw):
        result.setdefault(number, []).append((kind, value, wire))
    return result


def schema_fields(catalog, message):
    rows = catalog['field_schemas'][message]
    if (not isinstance(rows, list) or len(rows) > 4096 or
            len({r['number'] for r in rows}) != len(rows) or len({r['name'] for r in rows}) != len(rows)):
        raise ValueError('Native schema fields are duplicate or unbounded.')
    return {r['name']: r for r in rows}


def one(raw, field, kind):
    entries = wire_map(raw).get(field['number'], [])
    if len(entries) != 1 or entries[0][0] != kind or field.get('repeated') is not False:
        raise ValueError('Native singular field is absent, ambiguous or has changed wire type: ' + field['name'])
    value = entries[0][1]
    return int.from_bytes(entries[0][2][-(8 if kind == 1 else 4):], 'little') if kind in (1, 5) else value


def complete(template, records, mapping, catalog):
    """Use the current game's supplied descriptor catalog; never guess offsets."""
    old = tray_library.sims(template)
    if old['version'] != 2:
        raise ValueError('A real current v2 game-generated household is required.')
    root = schema_fields(catalog, catalog['native_message_type'])
    if not set(ACTIVE) | {'sim_id', 'attributes', 'first_name', 'last_name', 'age', 'gender'} <= set(root):
        raise ValueError('Current native appearance schema is incomplete; no fields omitted.')
    if root['sim_id']['type'] != 'fixed64' or root['attributes']['type'] != 'message':
        raise ValueError('Native identity/attributes descriptor contract changed.')
    attributes = schema_fields(catalog, root['attributes']['message_type'])
    if not {'occult_tracker', 'trait_tracker'} <= set(attributes):
        raise ValueError('Native occult and trait trackers are required.')
    for name in ('occult_tracker', 'trait_tracker'):
        if attributes[name]['type'] != 'message' or attributes[name]['repeated'] is not False:
            raise ValueError('Native tracker descriptor contract changed.')
    source = {}
    for row in records:
        raw = base64.b64decode(row['native_sim'], validate=True)
        sid = str(one(raw, root['sim_id'], 1))
        if row['sim_id'] != sid or row['native_sha256'] != digest(raw) or sid in source:
            raise ValueError('Canonical native identity/hash differs or repeats.')
        source[sid] = raw
    target = [base64.b64decode(raw, validate=True) for raw in old['sims']]
    target_ids = [str(one(raw, root['sim_id'], 1)) for raw in target]
    if (not 1 <= len(source) <= 8 or len(set(target_ids)) != len(target_ids) or
            set(mapping) != set(source) or set(mapping.values()) != set(target_ids) or
            len(mapping) != len(target_ids)):
        raise ValueError('Explicit complete bijection between canonical and Library members required.')
    inverse = {value: key for key, value in mapping.items()}
    completed, evidence = [], []
    for raw, tid in zip(target, target_ids):
        sid = inverse[tid]; canonical = source[sid]
        for name, kind in (('first_name', 2), ('last_name', 2), ('age', 0), ('gender', 0)):
            if one(raw, root[name], kind) != one(canonical, root[name], kind):
                raise ValueError('Explicit source mapping differs in native demographic identity: ' + name)
        active_numbers = {root[name]['number'] for name in ACTIVE}
        src = wire_map(canonical)
        changes = {number: [row[2] for row in src.get(number, [])] for number in active_numbers}
        src_attributes = one(canonical, root['attributes'], 2)
        dst_attributes = one(raw, root['attributes'], 2)
        tracker_fields = wire_map(src_attributes)
        replacements = {}
        for name in ('occult_tracker', 'trait_tracker'):
            number = attributes[name]['number']
            one(src_attributes, attributes[name], 2)
            replacements[number] = [entry[2] for entry in tracker_fields[number]]
        patched_attributes = replace(dst_attributes, replacements)
        changes[root['attributes']['number']] = [blob(root['attributes']['number'], patched_attributes)]
        patched = replace(raw, changes)
        actual = wire_map(patched)
        if any([e[2] for e in actual.get(n, [])] != wanted for n, wanted in changes.items()):
            raise ValueError('Completed native appearance failed complete wire readback.')
        # No other root field, including unknown future data, may change.
        untouched = lambda data: [(n, k, wire) for n, k, _v, wire in chunks(data) if n not in changes]
        if untouched(raw) != untouched(patched):
            raise ValueError('Completion changed an unselected native field.')
        completed.append(patched)
        evidence.append(dict(source_sim_id=sid, tray_sim_id=tid, source_native_sha256=digest(canonical),
            before_native_sha256=digest(raw), completed_native_sha256=digest(patched),
            copied_active_fields=list(ACTIVE), copied_attribute_owners=['occult_tracker', 'trait_tracker']))
    extent = struct.unpack_from('<I', template, 12)[0]
    payload, footer = template[16:16 + extent], template[16 + extent:]
    # The actual five-member export ends in 01 00 00 00 00. This is
    # opaque native data, not a member count. Keep the complete footer.
    if len(footer) != 5 or footer[-1:] != b'\0':
        raise ValueError('Native Library footer shape changed; no guessed envelope.')
    bodies = [v for n, k, v, _wire in chunks(payload) if n == 1 and k == 2]
    if len(bodies) != 1:
        raise ValueError('Native household container is ambiguous.')
    body = replace(bodies[0], {6: [blob(6, sim) for sim in completed]})
    payload = replace(payload, {1: [blob(1, body)]})
    result = struct.pack('<IIII', 2, 12 + len(payload) + len(footer), 0, len(payload)) + payload + footer
    if tray_library.sims(result)['sims'] != [base64.b64encode(r).decode('ascii') for r in completed]:
        raise ValueError('Completed native household failed exact readback.')
    return result, dict(members=evidence, native_metadata_regenerated=False, native_library_load_verified=False,
                        scope='Canonical active appearances, complete occult owners and trait tracker; other native Library data retained.')


def document(path, expected):
    raw = tray_library.read(path, 16 * 1024 * 1024)
    if digest(raw) != expected:
        raise ValueError('Exact external input SHA-256 required.')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate external input key.')
            result[key] = value
        return result
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('folder', 'records', 'catalog', 'mapping', 'archive', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--item', required=True)
    for name in ('records', 'catalog', 'mapping'):
        parser.add_argument('--' + name + '-sha256', required=True)
    args = parser.parse_args(argv)
    # writable refuses protected originals and redirected ancestors. Existing
    # exports are read only; destination files must be new external artifacts.
    for path in (args.archive, args.output):
        reusable_profile.writable(path)
        if path.exists() or not path.parent.is_dir():
            raise ValueError('Use new external archive/evidence destinations.')
        if any(part.casefold() in ('the sims 4', 'the sims 4 do not touch') for part in path.parts):
            raise ValueError('This command never stages candidates into game profiles.')
    group = tray_library.groups(args.folder).get(args.item)
    if not group or len([p for p in group if p.suffix.lower() == '.householdbinary']) != 1:
        raise ValueError('Select one complete authentic native household group.')
    files = {p.name: tray_library.read(p) for p in group}
    if sum(map(len, files.values())) > tray_library.MAX_GROUP:
        raise ValueError('Complete native Library group exceeds its bound.')
    binary = next(n for n in files if n.endswith('.householdbinary'))
    records = document(args.records, args.records_sha256)
    if records.get('ok') is not True or records.get('game_appearance_written') is not False:
        raise ValueError('Use acknowledged read-only canonical native records.')
    result, proof = complete(files[binary], records['sims'], document(args.mapping, args.mapping_sha256),
                             document(args.catalog, args.catalog_sha256))
    proof.update(schema=1, status='unverified-apex-completed-native-library-candidate',
        original_files={n: digest(r) for n, r in files.items()},
        input_sha256={n: getattr(args, n + '_sha256') for n in ('records', 'catalog', 'mapping')},
        game_library_files_written=False, item=args.item)
    files[binary] = result
    proof['files'] = {n: digest(r) for n, r in files.items()}
    with args.archive.open('xb') as stream:
        with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as bundle:
            for name, raw in files.items():
                bundle.writestr(name, raw)
            bundle.writestr('ApexAppearanceCompletion.json', json.dumps(proof, sort_keys=True))
    proof.update(archive=str(args.archive.absolute()), archive_sha256=digest(args.archive.read_bytes()))
    write_json(args.output, proof)
    print(json.dumps(dict(ok=True, archive_sha256=proof['archive_sha256'], members=len(proof['members']),
                          native_library_load_verified=False)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
