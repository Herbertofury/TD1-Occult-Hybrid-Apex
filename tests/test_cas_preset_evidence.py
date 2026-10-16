"""Synthetic CPRE and independent protobuf fixtures; no game/profile actions."""
import base64
import copy
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import cas_preset_evidence as evidence
import dbpf_build

SCULPT_ID = (1 << 64) - 9
PRESET_ID = (1 << 63) + 171
PRESET_KEY = (evidence.PRESET, 0, PRESET_ID)
SCULPT_KEY = (evidence.SCULPT, 0, SCULPT_ID)


def cpre(sculpts=(SCULPT_ID,), modifiers=(), physique=None, partset=None):
    # Independent byte layout copied from CPRE v12's public field contract.
    raw = struct.pack('<7IfII', 12, 8312, 8192, 1, 1, 0, 0, -5028., 11, 12)
    raw += struct.pack('<I', len(sculpts)) + b''.join(struct.pack('<Q', v) for v in sculpts)
    raw += struct.pack('<I', len(modifiers)) + b''.join(struct.pack('<Qf', k, v) for k, v in modifiers)
    raw += bytes([physique is not None])
    if physique is not None:
        raw += struct.pack('<4f', *physique)
    raw += bytes([partset is not None])
    if partset is not None:
        raw += struct.pack('<QI', *partset)
    return raw + struct.pack('<fIHIHI', 0., 2, 109, 0x8A0, 65000, 0xffffffff)


def facial(sculpts, *, packed=True, unknown='future untouched field'):
    file = descriptor_pb2.FileDescriptorProto(name='footprint.proto', syntax='proto2')
    message = file.message_type.add(name='Face')
    field = message.field.add(name='sculpts', number=1, type=4, label=3)
    field.options.packed = packed
    message.field.add(name='future', number=99, type=9, label=1)
    pool = descriptor_pool.DescriptorPool()
    pool.Add(file)
    cls = message_factory.GetMessageClass(pool.FindMessageTypeByName('Face'))
    raw = cls(sculpts=sculpts, future=unknown).SerializeToString()
    return {'kind': 'bytes', 'value': base64.b64encode(raw).decode('ascii')}


def snapshot(sculpts, *, sim='100', household='200', guid='300'):
    return {'ok': True, 'household_id': household, 'save_guid': guid,
            'sim': {'id': sim, 'form_appearances': [
                {'flags': 1, 'appearance': {'typed_payload': {'facial_attributes': facial([900])}}},
                {'flags': 8, 'appearance': {'typed_payload': {'facial_attributes': facial(sculpts)}}}],
                'full_appearance': {'typed_payload': {'facial_attributes': facial([777])}}}}


class PresetEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.package = self.root / 'Author Nose.package'
        self.package.write_bytes(dbpf_build.build({PRESET_KEY: cpre(), SCULPT_KEY: b'synthetic sculpt'}))
        self.sha = evidence.digest(self.package.read_bytes())
        self.preset = evidence.read_preset(self.package, self.sha, evidence.tgi(PRESET_KEY))
        self.before, self.returned = snapshot([900]), snapshot([SCULPT_ID])

    def compare(self, **options):
        return evidence.compare_footprint(self.preset, self.before, self.returned,
            sim_id='100', form='8', household_id='200', save_guid='300', **options)

    def test_v12_metadata_exact_uint64_float_tags_and_all_controlled_fields(self):
        row = evidence.parse_cpre(cpre(modifiers=((SCULPT_ID - 1, -.25),),
                                      physique=(.1, .2, .3, .4), partset=(PRESET_ID, 35)))
        self.assertEqual(row['status'], 'supported')
        self.assertEqual(row['expected_sculpt_ids'], [str(SCULPT_ID)])
        self.assertEqual(row['metadata']['display_index'], -5028.)
        self.assertEqual(row['metadata']['region'], 1)
        self.assertEqual(row['modifiers'], [{'instance': str(SCULPT_ID - 1), 'weight': -.25}])
        self.assertEqual(row['partset'], {'instance': str(PRESET_ID), 'body_type': 35})
        self.assertEqual(set(row['physique']), {'heavy', 'fit', 'lean', 'bony'})
        self.assertEqual(row['tags'][-1], {'category': 65000, 'value': 0xffffffff})

    def test_future_and_older_layouts_report_unsupported_without_fabricated_fields(self):
        for version in (0, 8, 11, 13, 0xffffffff):
            row = evidence.parse_cpre(struct.pack('<I', version) + b'opaque unknown future bytes')
            self.assertEqual(row['status'], 'unsupported')
            self.assertNotIn('expected_sculpt_ids', row)
            self.assertEqual(row['resource_sha256'], evidence.digest(struct.pack('<I', version) + b'opaque unknown future bytes'))

    def test_supported_truncations_and_unexplained_tail_refuse(self):
        raw = cpre(modifiers=((17, .4),), physique=(.1, .2, .3, .4), partset=(12, 35))
        for end in range(4, len(raw)):
            with self.assertRaises(ValueError, msg=str(end)):
                evidence.parse_cpre(raw[:end])
        with self.assertRaisesRegex(ValueError, 'Unexplained'):
            evidence.parse_cpre(raw + b'future extension')

    def test_invalid_boolean_nonfinite_counts_and_ambiguous_ids_refuse(self):
        empty = cpre(sculpts=())
        for bad in (cpre(sculpts=(0,)), cpre(sculpts=(7, 7)),
                    cpre(modifiers=((8, .1), (8, .2))), cpre(modifiers=((8, float('nan')),)),
                    empty[:48] + b'\x02' + empty[49:]):
            with self.assertRaises(ValueError):
                evidence.parse_cpre(bad)
        raw = bytearray(cpre())
        struct.pack_into('<I', raw, 40, evidence.MAX_SCULPTS + 1)
        with self.assertRaises(ValueError):
            evidence.parse_cpre(bytes(raw))

    def test_package_pin_exact_tgi_and_sculpt_hash_without_effective_load_claim(self):
        row = self.preset
        self.assertEqual(row['package_sha256'], self.sha)
        self.assertEqual(row['sculpts'][0]['resource_sha256'], evidence.digest(b'synthetic sculpt'))
        self.assertFalse(row['effective_loaded_resources_verified'])
        self.assertFalse(row['source_files_written'])
        with self.assertRaises(ValueError):
            evidence.read_preset(self.package, '0' * 64, evidence.tgi(PRESET_KEY))
        with self.assertRaises(ValueError):
            evidence.read_preset(self.package, self.sha, evidence.tgi(SCULPT_KEY))
        with self.assertRaises(ValueError):
            evidence.read_preset(self.package, self.sha, evidence.tgi((evidence.PRESET, 1, PRESET_ID)))

    def test_external_missing_sculpt_reference_is_reported_without_guessing_a_provider(self):
        path = self.root / 'external.package'
        path.write_bytes(dbpf_build.build({PRESET_KEY: cpre()}))
        row = evidence.read_preset(path, evidence.digest(path.read_bytes()), evidence.tgi(PRESET_KEY))
        self.assertFalse(row['sculpts'][0]['present_in_pinned_package'])
        self.assertNotIn('resource_sha256', row['sculpts'][0])
        self.assertFalse(row['effective_loaded_resources_verified'])

    def test_facial_parser_uses_independent_packed_and_unpacked_protobuf_uint64(self):
        for packed in (True, False):
            row = evidence.facial_sculpts(facial([SCULPT_ID, 123], packed=packed))
            self.assertEqual(row['sculpt_ids'], [str(SCULPT_ID), '123'])
        self.assertEqual(evidence.facial_sculpts(facial([]))['sculpt_ids'], [])

    def test_facial_unknown_wire_extents_and_ambiguous_sculpts_refuse(self):
        for raw in (b'\x0a\x02\x80', b'\x0a\x01\x80\x01', b'\x09' + b'\x00' * 8,
                    b'\x08\x00', b'\x08\x81\x00', b'\x00', b'\x13',
                    b'\x08' + b'\xff' * 9 + b'\x02'):
            typed = {'kind': 'bytes', 'value': base64.b64encode(raw).decode('ascii')}
            with self.assertRaises(ValueError, msg=raw.hex()):
                evidence.facial_sculpts(typed)
        with self.assertRaises(ValueError):
            evidence.facial_sculpts(facial([1, 1]))
        with self.assertRaises(ValueError):
            evidence.facial_sculpts(facial(range(1, evidence.MAX_SCULPTS + 2)))
        with self.assertRaises(ValueError):
            evidence.facial_sculpts({'kind': 'value', 'value': ''})

    def test_exact_selected_form_footprint_does_not_use_active_or_another_form(self):
        self.assertTrue(self.compare()['expected_sculpt_footprint_present'])
        self.returned['sim']['form_appearances'][1]['appearance']['typed_payload']['facial_attributes'] = facial([17])
        self.returned['sim']['full_appearance']['typed_payload']['facial_attributes'] = facial([SCULPT_ID])
        result = self.compare()
        self.assertFalse(result['ok'])
        self.assertEqual(result['missing_expected_sculpt_ids'], [str(SCULPT_ID)])

    def test_pure_comparison_preserves_inputs_and_never_labels_full_preset_applied(self):
        original = copy.deepcopy((self.preset, self.before, self.returned))
        result = self.compare()
        self.assertTrue(result['new_expected_sculpt_footprint_observed'])
        self.assertEqual(result['new_expected_sculpt_ids'], [str(SCULPT_ID)])
        for name in ('preset_applied_verified', 'all_controlled_fields_verified',
                     'effective_loaded_resources_verified', 'native_selection_verified',
                     'save_reload_verified', 'game_contacted', 'source_files_written'):
            self.assertFalse(result[name])
        self.assertEqual((self.preset, self.before, self.returned), original)

    def test_preexisting_sculpt_is_presence_only_and_empty_footprint_is_not_vacuous_success(self):
        self.before = snapshot([SCULPT_ID])
        result = self.compare()
        self.assertTrue(result['ok'])
        self.assertFalse(result['new_expected_sculpt_footprint_observed'])
        self.assertEqual(result['new_expected_sculpt_ids'], [])
        self.preset['cpre'] = evidence.parse_cpre(cpre(sculpts=(), modifiers=((7, .5),)))
        result = self.compare()
        self.assertFalse(result['ok'])
        self.assertFalse(result['preset_applied_verified'])

    def test_mismatched_sim_household_guid_form_and_parent_identity_refuse(self):
        for name, value in (('household_id', '201'), ('save_guid', '301')):
            old = self.returned[name]
            self.returned[name] = value
            with self.assertRaises(ValueError):
                self.compare()
            self.returned[name] = old
        self.returned['sim']['id'] = '101'
        with self.assertRaises(ValueError):
            self.compare()
        self.returned['sim']['id'] = '100'
        self.returned['sim']['form_appearances'][1]['flags'] = 4
        with self.assertRaises(ValueError):
            self.compare()
        self.returned = {'household_id': '999', 'snapshots': {'100': snapshot([SCULPT_ID])}}
        with self.assertRaisesRegex(ValueError, 'Contradictory'):
            self.compare()

    def test_missing_optional_identity_is_reported_without_becoming_verified(self):
        for document in (self.before, self.returned):
            document.pop('household_id')
            document.pop('save_guid')
        result = self.compare()
        self.assertTrue(result['ok'])
        self.assertFalse(result['identity']['household_id_verified_in_both_proofs'])
        self.assertFalse(result['identity']['save_guid_verified_in_both_proofs'])

    def test_duplicate_forms_unknown_layout_and_wrong_recorded_facial_hash_refuse(self):
        self.returned['sim']['form_appearances'].append(copy.deepcopy(self.returned['sim']['form_appearances'][1]))
        with self.assertRaises(ValueError):
            self.compare()
        self.returned['sim']['form_appearances'].pop()
        self.returned['sim']['form_appearances'][1]['appearance']['field_sha256'] = {'facial_attributes': '0' * 64}
        with self.assertRaisesRegex(ValueError, 'recorded field hash'):
            self.compare()
        with self.assertRaises(ValueError):
            evidence.compare_footprint(self.preset, {'appearance': {}}, self.returned, sim_id='100', form='8')

    def test_explicit_sections_support_raw_owner_receipts_without_guessing_active_lane(self):
        def owners(sculpts):
            return {'identity': {'runtime_pid': 333, 'sim_id': '100', 'household_id': '200', 'save_guid': '300'},
                    'stored': {'8': {'facial_attributes': facial(sculpts)}},
                    'active': {'lane': '1', 'fields': {'facial_attributes': facial([777])}}}
        journal = {'original_owners': owners([900]), 'raw_return': owners([SCULPT_ID])}
        result = evidence.compare_footprint(self.preset, journal, journal, sim_id='100', form='8',
            before_section=('original_owners',), returned_section=('raw_return',))
        self.assertTrue(result['ok'])
        with self.assertRaises(ValueError):
            evidence.compare_footprint(self.preset, journal, journal, sim_id='100', form='8')

    def test_unsupported_cpre_does_not_infer_footprint(self):
        self.preset['cpre'] = evidence.parse_cpre(struct.pack('<I', 99))
        result = self.compare()
        self.assertFalse(result['assessment_completed'])
        self.assertFalse(result['preset_applied_verified'])

    def test_retained_proof_pin_duplicate_keys_nonfinite_json_and_byte_changes_refuse(self):
        path = self.root / 'proof.json'
        raw = json.dumps({'snapshots': {'100': self.before}}).encode('utf-8')
        path.write_bytes(raw)
        self.assertEqual(evidence.read_proof(path, evidence.digest(raw))['snapshots']['100'], self.before)
        path.write_bytes(raw + b' ')
        with self.assertRaises(ValueError):
            evidence.read_proof(path, evidence.digest(raw))
        for bad in (b'{"x":1,"x":2}', b'{"x":NaN}', b'[]'):
            path.write_bytes(bad)
            with self.assertRaises(ValueError):
                evidence.read_proof(path, evidence.digest(bad))


if __name__ == '__main__':
    unittest.main()
