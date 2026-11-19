"""Read selected household/Sim metadata from one hash-bound indexed save.

This projects a small installed wire contract without loading game descriptors,
executing game modules, rebuilding protobuf messages or writing the save.
Unknown fields remain opaque input bytes and contribute to the resource hash.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from cas_resource_catalog import Package, signature
from save_metadata import fields, project as save_identity
from source_manifest import sha256
from test_profile import unlinked


def identity(value):
    if (not isinstance(value, str) or not value.isascii() or not value.isdecimal() or
            not 0 < int(value) < 1 << 64 or str(int(value)) != value):
        raise ValueError('An exact canonical positive uint64 identity is required.')
    return value


def record_id(raw, number):
    values = [(wire, value) for field, wire, value in fields(raw) if field == number]
    if len(values) != 1 or values[0][0] != 1 or not 0 < values[0][1] < 1 << 64:
        raise ValueError('Native household/Sim identity is missing, duplicated or untyped.')
    return str(values[0][1])


def name(value):
    if len(value) > 1024:
        raise ValueError('Native household/Sim name exceeds its UTF-8 bound.')
    value = value.decode('utf-8')
    if len(value) > 256 or any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError('Native household/Sim name is unbounded or contains controls.')
    return value


def members(raw):
    result = []
    for number, wire, value in fields(raw):
        if number != 1:
            continue
        if wire != 2 or len(value) % 8:
            raise ValueError('Household member IDs require packed fixed64 bytes.')
        if len(result) + len(value) // 8 > 1024:
            raise ValueError('Household member list exceeds its bound.')
        result.extend(str(item[0]) for item in struct.iter_unpack('<Q', value))
    if not result or len(set(result)) != len(result) or any(item == '0' for item in result):
        raise ValueError('Household member IDs are empty, zero or duplicated.')
    return result


def selected(raw, expected):
    result = {}
    for number, wire, value in fields(raw):
        if number not in expected:
            continue
        label, required_wire, convert = expected[number]
        if wire != required_wire or label in result:
            raise ValueError('Selected native household/Sim field is duplicated or untyped.')
        result[label] = convert(value)
    return result


def project(raw, household_id, sim_id):
    household_id, sim_id = identity(household_id), identity(sim_id)
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 32 * 1024 * 1024:
        raise ValueError('Native save resource exceeds its bound.')
    metadata = save_identity(raw)
    households, sims = [], []
    count = 0
    for number, wire, value in fields(raw):
        if number not in (5, 6):
            continue
        if wire != 2:
            raise ValueError('Native household/Sim records must be length-delimited.')
        count += 1
        if count > 200000:
            raise ValueError('Native household/Sim record inventory exceeds its bound.')
        actual = record_id(value, 2 if number == 5 else 1)
        if actual == (household_id if number == 5 else sim_id):
            (households if number == 5 else sims).append(value)
    if len(households) != 1 or len(sims) != 1:
        raise ValueError('Selected household/Sim is missing or duplicated in the indexed save.')
    household = selected(households[0], {
        2: ('id', 1, str), 3: ('name', 2, name), 4: ('home_zone_id', 1, str),
        9: ('last_played_sim_id', 1, str), 11: ('member_ids', 2, members)})
    sim = selected(sims[0], {
        1: ('id', 1, str), 2: ('zone_id', 1, str), 4: ('household_id', 1, str),
        5: ('first_name', 2, name), 6: ('last_name', 2, name), 22: ('household_name', 2, name)})
    if (household.get('id') != household_id or sim.get('id') != sim_id or
            sim.get('household_id') != household_id or sim_id not in household.get('member_ids', [])):
        raise ValueError('Selected Sim/household identity and exact list membership disagree.')
    if 'home_zone_id' not in household or 'zone_id' not in sim:
        raise ValueError('Selected Sim/household has no typed zone metadata.')
    return dict(metadata, household=household, sim=sim, selected_membership_verified=True,
                selected_household_is_active=metadata['active_household_id'] == household_id,
                unknown_fields_skipped_read_only=True)


def read(path, expected_sha256, household_id, sim_id):
    household_id, sim_id = identity(household_id), identity(sim_id)
    if (not isinstance(expected_sha256, str) or len(expected_sha256) != 64 or
            any(character not in '0123456789abcdef' for character in expected_sha256)):
        raise ValueError('An exact lowercase file SHA-256 is required.')
    path = unlinked(path)
    before_signature, before = signature(path), sha256(path)
    if before != expected_sha256 or signature(path) != before_signature:
        raise ValueError('Native save differs from the explicit file hash or changed during hashing.')
    package = Package(path, 'mod')
    keys = [key for key in package.entries if key[0] == 13 and key[1] == 0]
    if len(keys) != 1:
        raise ValueError('Native save data resource is absent or ambiguous.')
    raw = package.read(keys[0])
    metadata = project(raw, household_id, sim_id)
    if (metadata['save_guid'] != str(keys[0][2]) or sha256(path) != before or
            signature(path) != before_signature):
        raise ValueError('Native save resource GUID differs or the file changed.')
    return dict(metadata, file_sha256=before, resource_key=list(keys[0]),
                resource_sha256=hashlib.sha256(raw).hexdigest(),
                household_record_sha256=hashlib.sha256(next(value for number, _wire, value in fields(raw)
                    if number == 5 and record_id(value, 2) == household_id)).hexdigest(),
                sim_record_sha256=hashlib.sha256(next(value for number, _wire, value in fields(raw)
                    if number == 6 and record_id(value, 1) == sim_id)).hexdigest(),
                save_file_written=False, game_modules_executed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--household-id', required=True)
    parser.add_argument('--sim-id', required=True)
    args = parser.parse_args()
    print(json.dumps(read(args.file, args.expected_sha256, args.household_id, args.sim_id), indent=2))
