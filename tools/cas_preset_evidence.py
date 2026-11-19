"""Read-only CPRE/sculpt footprint evidence from pinned packages and CAS proofs.

Supported resource contract: CPRE v12, as independently documented by
CmarNYC-Tools/TS4MorphMaker src/CPRE.cs. Other versions remain unsupported.
This tool never contacts the game or changes a package, profile or proof.
Presence of referenced sculpt IDs does not prove an entire preset applied:
native region replacement, modifiers, physique, partsets, effective resource
precedence and save/reload persistence are deliberately outside this scope.
"""
import argparse
import base64
import hashlib
import json
import math
from pathlib import Path
import re
import struct

from cas_resource_catalog import Package, no_redirected_ancestors, key, tgi

PRESET, SCULPT = 0xEAA32ADD, 0x9D1AB874
MAX_CPRE, MAX_FACIAL, MAX_PROOF = 1024 * 1024, 1024 * 1024, 48 * 1024 * 1024
MAX_SCULPTS, MAX_MODIFIERS, MAX_TAGS = 256, 1024, 1024
FORMS = ('1', '2', '4', '8', '16', '32', '64')
SHA = re.compile(r'[0-9a-f]{64}\Z')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _sha(value):
    if not isinstance(value, str) or SHA.fullmatch(value) is None:
        raise ValueError('Use an exact lowercase SHA-256.')
    return value


def _id(value):
    if (not isinstance(value, str) or not value.isascii() or
            not value.isdecimal() or not 0 < len(value) <= 20 or
            str(int(value)) != value or not 0 < int(value) < 1 << 64):
        raise ValueError('Use an exact nonzero canonical uint64 identity.')
    return value


class Reader:
    def __init__(self, raw):
        if not isinstance(raw, bytes) or not 4 <= len(raw) <= MAX_CPRE:
            raise ValueError('CPRE bytes are absent or exceed their bound.')
        self.raw, self.offset = raw, 0

    def read(self, fmt):
        size = struct.calcsize('<' + fmt)
        if self.offset + size > len(self.raw):
            raise ValueError('Truncated supported CPRE resource.')
        values = struct.unpack_from('<' + fmt, self.raw, self.offset)
        self.offset += size
        return values[0] if len(values) == 1 else values

    def count(self, bound):
        value = self.read('I')
        if value > bound:
            raise ValueError('CPRE repeated-field bound exceeded.')
        return value

    def boolean(self):
        value = self.read('B')
        if value not in (0, 1):
            raise ValueError('CPRE boolean has an unsupported representation.')
        return bool(value)

    def finite(self):
        value = self.read('f')
        if not math.isfinite(value):
            raise ValueError('CPRE contains a nonfinite float32.')
        return value


def parse_cpre(raw):
    """Parse precisely v12; do not infer fields in older/future layouts."""
    r = Reader(raw)
    version = r.read('I')
    result = {'status': 'unsupported', 'version': version,
              'resource_sha256': digest(raw), 'bytes': len(raw)}
    if version != 12:
        result['reason'] = 'Only the independently inspected CPRE v12 layout is supported.'
        return result
    metadata = dict(age_gender=r.read('I'), body_frame_gender=r.read('I'),
                    species=r.read('I'), region=r.read('I'), subregion=r.read('I'),
                    archetype=r.read('I'), display_index=r.finite(),
                    title_key=r.read('I'), description_key=r.read('I'))
    sculpts = [str(r.read('Q')) for _ in range(r.count(MAX_SCULPTS))]
    modifiers = [dict(instance=str(r.read('Q')), weight=r.finite())
                 for _ in range(r.count(MAX_MODIFIERS))]
    if ('0' in sculpts or len(set(sculpts)) != len(sculpts) or
            any(row['instance'] == '0' for row in modifiers) or
            len({row['instance'] for row in modifiers}) != len(modifiers)):
        raise ValueError('CPRE sculpt/modifier identities are zero or ambiguous.')
    physique = None
    if r.boolean():
        physique = {name: r.finite() for name in ('heavy', 'fit', 'lean', 'bony')}
    partset = None
    if r.boolean():
        partset = dict(instance=str(r.read('Q')), body_type=r.read('I'))
        _id(partset['instance'])
    chance = r.finite()
    tags = [dict(category=r.read('H'), value=r.read('I'))
            for _ in range(r.count(MAX_TAGS))]
    if r.offset != len(raw):
        raise ValueError('Unexplained bytes follow the supported CPRE v12 layout.')
    result.update(status='supported', metadata=metadata, expected_sculpt_ids=sculpts,
                  modifiers=modifiers, physique=physique, partset=partset,
                  chance_for_random=chance, tags=tags)
    return result


def read_preset(path, expected_package_sha256, resource_tgi):
    """Pin one package and CPRE TGI; report local sculpt provenance, not load order."""
    expected_package_sha256 = _sha(expected_package_sha256)
    ident = key(resource_tgi)
    if ident[0] != PRESET or ident[2] == 0:
        raise ValueError('An exact nonzero CPRE resource TGI is required.')
    path = Path(path)
    no_redirected_ancestors(path)
    package = Package(path, 'mod')
    if package.source_sha256 != expected_package_sha256:
        raise ValueError('Package bytes differ from the pinned SHA-256.')
    if ident not in package.entries:
        raise ValueError('Pinned package does not contain the exact CPRE TGI.')
    parsed = parse_cpre(package.read(ident))
    result = {'schema': 1, 'scope': 'package-cpre-and-local-sculpt-provenance',
              'package_path': str(package.path), 'package_sha256': package.source_sha256,
              'resource_tgi': tgi(ident), 'cpre': parsed, 'sculpts': [],
              'effective_loaded_resources_verified': False,
              'game_contacted': False, 'source_files_written': False}
    if parsed['status'] == 'supported':
        for instance in parsed['expected_sculpt_ids']:
            # CPRE v12 stores scalar sculpt instances; its sculpt resource
            # contract uses type 9D1AB874, group 00000000. No ID conversion.
            sculpt = (SCULPT, 0, int(instance))
            row = {'instance': instance, 'resource_tgi': tgi(sculpt),
                   'present_in_pinned_package': sculpt in package.entries}
            if row['present_in_pinned_package']:
                raw = package.read(sculpt)
                row.update(resource_sha256=digest(raw), bytes=len(raw),
                           package_sha256=package.source_sha256)
            else:
                row['reason'] = 'Reference is external or absent; its effective definition is unverified.'
            result['sculpts'].append(row)
    return result


def _pairs(items):
    result = {}
    for name, value in items:
        if name in result:
            raise ValueError('Duplicate retained proof JSON key.')
        result[name] = value
    return result


def _nonfinite(_value):
    raise ValueError('Nonfinite JSON value in retained proof.')


def read_proof(path, expected_sha256):
    """Read a complete pinned JSON proof without opening game/profile writers."""
    expected_sha256 = _sha(expected_sha256)
    path = Path(path)
    no_redirected_ancestors(path)
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_PROOF:
        raise ValueError('Retained proof is absent or exceeds its bound.')
    with path.open('rb') as stream:
        raw = stream.read(MAX_PROOF + 1)
    if len(raw) > MAX_PROOF or digest(raw) != expected_sha256:
        raise ValueError('Retained proof bytes differ from the pinned SHA-256.')
    try:
        document = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=_pairs,
                              parse_constant=_nonfinite)
    except (UnicodeError, RecursionError) as error:
        raise ValueError('Retained proof has an unsupported JSON layout.') from error
    if not isinstance(document, dict):
        raise ValueError('Retained proof must be a JSON object.')
    return document


def _varint(raw, position):
    value, start = 0, position
    for shift in range(0, 70, 7):
        if position >= len(raw):
            raise ValueError('Truncated facial protobuf varint.')
        byte = raw[position]
        position += 1
        if shift == 63 and byte > 1:
            raise ValueError('Facial protobuf varint exceeds uint64.')
        value |= (byte & 127) << shift
        if byte < 128:
            if position - start > 1 and byte == 0:
                raise ValueError('Noncanonical facial protobuf varint.')
            return value, position
    raise ValueError('Facial protobuf varint exceeds its bound.')


def facial_sculpts(typed):
    """Read exact uint64 scalar/packed field1; validate unrelated wire extents."""
    if (not isinstance(typed, dict) or set(typed) != {'kind', 'value'} or
            typed['kind'] not in ('bytes', 'protobuf') or not isinstance(typed['value'], str) or
            len(typed['value']) > 4 * ((MAX_FACIAL + 2) // 3)):
        raise ValueError('Use the retained bounded typed facial protobuf bytes.')
    try:
        raw = base64.b64decode(typed['value'], validate=True)
    except (ValueError, TypeError) as error:
        raise ValueError('Facial payload is not exact base64.') from error
    if len(raw) > MAX_FACIAL or base64.b64encode(raw).decode('ascii') != typed['value']:
        raise ValueError('Facial payload bytes are oversized or noncanonical.')
    position, count, sculpts = 0, 0, []
    while position < len(raw):
        tag, position = _varint(raw, position)
        number, wire = tag >> 3, tag & 7
        count += 1
        if not 0 < number < 1 << 29 or count > 16384:
            raise ValueError('Facial protobuf field number/count exceeds its bound.')
        if wire == 0:
            value, position = _varint(raw, position)
            if number == 1:
                sculpts.append(value)
        elif wire in (1, 5):
            if number == 1:
                raise ValueError('Sculpt uint64 uses an unsupported wire type.')
            position += 8 if wire == 1 else 4
        elif wire == 2:
            length, position = _varint(raw, position)
            end = position + length
            if end > len(raw):
                raise ValueError('Truncated facial protobuf child.')
            if number == 1:
                while position < end:
                    value, position = _varint(raw[:end], position)
                    sculpts.append(value)
                    if len(sculpts) > MAX_SCULPTS:
                        raise ValueError('Facial protobuf sculpt bound exceeded.')
            position = end
        else:
            raise ValueError('Unsupported facial protobuf group/wire type.')
        if position > len(raw) or len(sculpts) > MAX_SCULPTS:
            raise ValueError('Facial protobuf extent/sculpt bound exceeded.')
    if any(value == 0 for value in sculpts) or len(set(sculpts)) != len(sculpts):
        raise ValueError('Retained facial sculpt identities are zero or ambiguous.')
    return {'sha256': digest(raw), 'bytes': len(raw),
            'sculpt_ids': [str(value) for value in sculpts]}


def _section(document, section):
    if not isinstance(section, (tuple, list)) or len(section) > 4:
        raise ValueError('Use a bounded explicit retained proof section.')
    for name in section:
        if not isinstance(name, str) or not name or not isinstance(document, dict) or name not in document:
            raise ValueError('Explicit retained proof section is absent.')
        document = document[name]
    if not isinstance(document, dict):
        raise ValueError('Retained proof section must be an object.')
    return document


def _form(document, sim_id, form, section):
    """Known snapshot/raw-owner layouts only; never substitute active appearance."""
    claims = {'household_id': [], 'save_guid': []}
    def observe(node):
        if isinstance(node, dict):
            for container in (node, node.get('identity')):
                if isinstance(container, dict):
                    for name in claims:
                        if name in container:
                            claims[name].append(_id(container[name]))
    observe(document)
    # Identity claims on the explicit parent path remain binding even when
    # the caller selects a nested native snapshot/raw-owner section.
    selected = document
    _section(document, section)
    for name in section:
        selected = selected[name]
        observe(selected)
    document = selected
    if 'snapshots' in document:
        document = _section(document, ('snapshots',))
        observe(document)
    if sim_id in document:
        document = _section(document, (sim_id,))
        observe(document)
    if 'sim' in document:
        sim = document['sim']
        if not isinstance(sim, dict) or sim.get('id') != sim_id or document.get('ok') is not True:
            raise ValueError('Retained snapshot does not acknowledge the exact requested Sim.')
        rows = sim.get('form_appearances')
        if not isinstance(rows, list) or not 1 <= len(rows) <= 128:
            raise ValueError('Retained snapshot has no bounded native stored-form inventory.')
        matches, seen = [], set()
        for row in rows:
            if not isinstance(row, dict) or type(row.get('flags')) is not int:
                raise ValueError('Retained native form identity has an unsupported layout.')
            flags = str(row['flags'])
            if flags not in FORMS or flags in seen:
                raise ValueError('Retained native form identities are unsupported or duplicate.')
            seen.add(flags)
            if flags == form:
                matches.append(row.get('appearance'))
        if len(matches) != 1 or not isinstance(matches[0], dict):
            raise ValueError('Retained snapshot lacks the exact requested stored form.')
        fields = matches[0].get('typed_payload')
        hashes = matches[0].get('field_sha256')
        if hashes is not None:
            if not isinstance(hashes, dict) or 'facial_attributes' not in hashes:
                raise ValueError('Retained facial field hash is missing or malformed.')
            actual = digest(json.dumps(fields.get('facial_attributes') if isinstance(fields, dict) else None,
                sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('utf-8'))
            if _sha(hashes['facial_attributes']) != actual:
                raise ValueError('Retained facial payload differs from its recorded field hash.')
    elif 'stored' in document and 'identity' in document:
        identity = document['identity']
        if not isinstance(identity, dict) or identity.get('sim_id') != sim_id:
            raise ValueError('Raw retained owner identity differs from the requested Sim.')
        stored = document['stored']
        if (not isinstance(stored, dict) or not stored or set(stored) - set(FORMS) or
                form not in stored):
            raise ValueError('Raw retained owners lack the exact requested stored form.')
        fields = stored[form]
        observe(document)
    else:
        raise ValueError('Unsupported retained appearance layout; select its explicit native section.')
    if not isinstance(fields, dict) or 'facial_attributes' not in fields:
        raise ValueError('Selected native form has no retained facial attributes.')
    identity = {}
    for name, values in claims.items():
        if len(set(values)) > 1:
            raise ValueError('Contradictory retained ' + name + ' identity claims.')
        identity[name] = values[0] if values else None
    return fields['facial_attributes'], identity


def compare_footprint(preset, before, returned, *, sim_id, form,
                      household_id=None, save_guid=None,
                      before_section=(), returned_section=()):
    """Pure comparison: qualify only the referenced sculpt footprint, never a preset."""
    sim_id = _id(sim_id)
    if not isinstance(form, str) or form not in FORMS:
        raise ValueError('Use one exact supported stored occult form identity.')
    if (not isinstance(preset, dict) or preset.get('schema') != 1 or
            preset.get('scope') != 'package-cpre-and-local-sculpt-provenance' or
            key(preset.get('resource_tgi'))[0] != PRESET):
        raise ValueError('Use the exact parsed package CPRE provenance.')
    _sha(preset.get('package_sha256'))
    cpre = preset.get('cpre')
    if not isinstance(cpre, dict) or cpre.get('status') != 'supported' or cpre.get('version') != 12:
        return {'ok': False, 'assessment_completed': False, 'scope': 'expected-cpre-sculpt-footprint-only',
                'reason': 'Unsupported CPRE contract; no expected footprint inferred.',
                'preset_applied_verified': False, 'game_contacted': False, 'source_files_written': False}
    expected = cpre.get('expected_sculpt_ids')
    if (not isinstance(expected, list) or len(expected) > MAX_SCULPTS or
            any(not isinstance(value, str) for value in expected) or len(set(expected)) != len(expected)):
        raise ValueError('Parsed expected sculpt footprint is malformed.')
    for instance in expected:
        _id(instance)
    a, before_identity = _form(before, sim_id, form, before_section)
    b, returned_identity = _form(returned, sim_id, form, returned_section)
    identities = {'sim_id': sim_id, 'form': form}
    for name, requested in (('household_id', household_id), ('save_guid', save_guid)):
        if requested is not None:
            _id(requested)
        values = [v[name] for v in (before_identity, returned_identity) if v[name] is not None]
        if requested is not None:
            values.append(requested)
        if len(set(values)) > 1:
            raise ValueError('Retained ' + name + ' differs between requested/before/returned identities.')
        identities[name] = values[0] if values else None
        identities[name + '_verified_in_both_proofs'] = all(
            v[name] is not None for v in (before_identity, returned_identity))
    old, new = facial_sculpts(a), facial_sculpts(b)
    missing = [v for v in expected if v not in new['sculpt_ids']]
    preexisting = [v for v in expected if v in old['sculpt_ids']]
    added = [v for v in expected if v in new['sculpt_ids'] and v not in old['sculpt_ids']]
    present = bool(expected) and not missing
    return {'schema': 1, 'ok': present, 'assessment_completed': True,
            'scope': 'expected-cpre-sculpt-footprint-only', 'identity': identities,
            'package_sha256': preset['package_sha256'], 'resource_tgi': preset['resource_tgi'],
            'cpre_resource_sha256': _sha(cpre.get('resource_sha256')),
            'expected_sculpt_ids': list(expected), 'missing_expected_sculpt_ids': missing,
            'preexisting_expected_sculpt_ids': preexisting, 'new_expected_sculpt_ids': added,
            'expected_sculpt_footprint_present': present,
            'new_expected_sculpt_footprint_observed': present and bool(added),
            'before': old, 'returned': new, 'facial_payload_changed': old['sha256'] != new['sha256'],
            'preset_applied_verified': False, 'all_controlled_fields_verified': False,
            'effective_loaded_resources_verified': False, 'native_selection_verified': False,
            'save_reload_verified': False,
            'unverified': ['sculpt-region-replacement-and-other-region-preservation',
                           'direct-modifier-values', 'physique-and-partset-effects',
                           'effective-loaded-resource-precedence', 'native-catalog-selection',
                           'save-and-reload-persistence'],
            'game_contacted': False, 'source_files_written': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', required=True, type=Path)
    parser.add_argument('--package-sha256', required=True)
    parser.add_argument('--preset-tgi', required=True)
    parser.add_argument('--before', required=True, type=Path)
    parser.add_argument('--before-sha256', required=True)
    parser.add_argument('--returned', required=True, type=Path)
    parser.add_argument('--returned-sha256', required=True)
    parser.add_argument('--before-section', default='', help='Explicit dot-separated JSON object keys, at most four.')
    parser.add_argument('--returned-section', default='')
    parser.add_argument('--sim-id', required=True)
    parser.add_argument('--form', required=True, choices=FORMS)
    parser.add_argument('--household-id')
    parser.add_argument('--save-guid')
    args = parser.parse_args()
    preset = read_preset(args.package, args.package_sha256, args.preset_tgi)
    before = read_proof(args.before, args.before_sha256)
    returned = read_proof(args.returned, args.returned_sha256)
    result = compare_footprint(preset, before, returned, sim_id=args.sim_id, form=args.form,
        household_id=args.household_id, save_guid=args.save_guid,
        before_section=args.before_section.split('.') if args.before_section else (),
        returned_section=args.returned_section.split('.') if args.returned_section else ())
    result.update(preset_provenance=preset, before_proof_sha256=args.before_sha256,
                  returned_proof_sha256=args.returned_sha256)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
