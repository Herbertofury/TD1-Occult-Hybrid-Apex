"""Read the indexed native save identity without touching the save file.

DBPF kind 13 contains SaveGameData; the installed descriptor establishes guid#1
and save_slot#2, with slot_id#1/fixed64, slot_name#9 and household#11/uint64.
Unreferenced append-only DBPF bytes and arbitrary string searches are excluded.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from cas_resource_catalog import Package
from source_manifest import sha256
from test_profile import unlinked


def fields(raw):
    position = 0
    def take(count):
        nonlocal position
        if not 0 <= count <= len(raw) - position:
            raise ValueError('Truncated native save protobuf.')
        value = raw[position:position + count]; position += count
        return value
    def varint():
        value = 0
        for shift in range(0, 70, 7):
            byte = take(1)[0]; value |= (byte & 127) << shift
            if not byte & 128:
                if value >= 1 << 64:
                    raise ValueError('Native save varint overflow.')
                return value
        raise ValueError('Overlong native save varint.')
    while position < len(raw):
        key = varint(); number, wire = key >> 3, key & 7
        if not 0 < number < 1 << 29:
            raise ValueError('Invalid native save field number.')
        if wire == 0: value = varint()
        elif wire == 1: value = struct.unpack('<Q', take(8))[0]
        elif wire == 2: value = take(varint())
        elif wire == 5: value = struct.unpack('<I', take(4))[0]
        else: raise ValueError('Unsupported native save wire type.')
        yield number, wire, value


def project(raw):
    root = [(number, wire, value) for number, wire, value in fields(raw) if number in (1, 2)]
    if sorted((number, wire) for number, wire, _ in root) != [(1, 0), (2, 2)]:
        raise ValueError('Native save root identity is absent, duplicated or untyped.')
    guid = next(value for number, _, value in root if number == 1)
    slot = next(value for number, _, value in root if number == 2)
    expected = {1: ('slot_id', 1), 9: ('slot_name', 2), 11: ('active_household_id', 0),
                20: ('preferred_manual_slot_id', 0), 21: ('preferred_manual_slot_name', 2)}
    result = {'save_guid': str(guid)}
    for number, wire, value in fields(slot):
        if number not in expected: continue
        name, required_wire = expected[number]
        if wire != required_wire or name in result:
            raise ValueError('Native save slot identity is duplicated or untyped.')
        if required_wire == 2:
            value = value.decode('utf-8')
            if not 0 < len(value) <= 128 or any(ord(character) < 32 for character in value):
                raise ValueError('Native save slot name exceeds its bound.')
        result[name] = str(value) if name == 'active_household_id' else value
    if (not 0 < guid < 1 << 32 or not {'slot_id', 'slot_name', 'active_household_id'} <= set(result) or
            not 0 < result['slot_id'] <= 0xffffffff or not 0 < int(result['active_household_id']) < 1 << 64):
        raise ValueError('Native save metadata has no complete bounded identity.')
    return result


def read(path, expected_sha256):
    path = unlinked(path)
    before = sha256(path)
    if before != expected_sha256:
        raise ValueError('Native save differs from the explicit file hash.')
    package = Package(path, 'mod')  # Read-only indexed container; never opened by Studio.
    keys = [key for key in package.entries if key[0] == 13 and key[1] == 0]
    if len(keys) != 1:
        raise ValueError('Native save data resource is absent or ambiguous.')
    raw = package.read(keys[0]); metadata = project(raw)
    if metadata['save_guid'] != str(keys[0][2]) or sha256(path) != before:
        raise ValueError('Native save resource GUID differs or the file changed.')
    return dict(metadata, file_sha256=before, resource_key=list(keys[0]),
                resource_sha256=hashlib.sha256(raw).hexdigest(), save_file_written=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    parser.add_argument('--expected-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(read(args.file, args.expected_sha256), indent=2))
