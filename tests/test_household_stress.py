from pathlib import Path
import copy
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import household_stress as stress
from test_outfit_snapshot import outfit, varint
from apex_core.form_appearance import encode


def sample(ids=('1', '2')):
    def owner(label):
        return {'field_sha256': {'__outfits__': label, 'future_new_cas_field': label},
                'typed_payload': {'__outfits__': {}, 'future_new_cas_field': {}}}
    return {sid: {'ok': True, 'household_id': '3', 'save_guid': '4', 'zone_running': True,
        'in_build_buy': False, 'clock_speed': 0, 'persistence': {'household_sim_ids': list(ids)},
        'sim': {'id': sid, 'current_form': 2, 'membership': [{'flags': f} for f in stress.FORMS if f != 1],
                'form_appearances': [{'flags': f, 'appearance': owner(sid + ':' + str(f))} for f in stress.FORMS],
                'full_appearance': owner(sid + ':active')}} for sid in ids}


class HouseholdStressTests(unittest.TestCase):
    def test_companion_transition_must_retain_latest_source_and_exact_target_and_every_other_field(self):
        before = sample(); after = copy.deepcopy(before)
        sim = after['2']['sim']; sim['current_form'] = 8
        for row in sim['form_appearances']:
            if row['flags'] == 2: row['appearance'] = copy.deepcopy(before['2']['sim']['full_appearance'])
        sim['full_appearance'] = copy.deepcopy(stress.owners(before['2'])['8'])
        expected, retained = stress.retained_companion_transitions(before, after, '1')
        self.assertEqual(stress.differences(expected, after), [])
        self.assertTrue(retained[0]['complete_source_target_retention_verified'])
        for location in ('source', 'target', 'another'):
            broken = copy.deepcopy(after)
            row = broken['2']['sim']['full_appearance'] if location == 'target' else next(
                r['appearance'] for r in broken['2']['sim']['form_appearances']
                if r['flags'] == (2 if location == 'source' else 4))
            row['field_sha256']['future_new_cas_field'] = 'lost'
            with self.subTest(location=location), self.assertRaises(ValueError):
                stress.retained_companion_transitions(before, broken, '1')

    def test_only_part_free_zero_id_native_placeholder_can_initialize(self):
        metadata = b'\x48\x01\x6a\x00\xa3\x01\x08\x07\xa4\x01'
        def row(uid, parts=b'', extra=b''):
            raw = b'\x08' + varint(uid) + b'\x10\x00' + parts + metadata + extra
            return b'\x0a' + varint(len(raw)) + raw
        def payload(raw):
            return {'typed_payload': {'__outfits__': encode(('protobuf', raw))}}
        before = payload(row(0) + b'\x10\x03')
        after = payload(row(999, b'\x2a\x03\x08\x91\x01') + outfit(5, 44) + b'\x10\x03')
        generated = stress.initialized_empty_outfits(before, after)
        self.assertEqual(generated[0]['native_outfit_id'], '999')
        self.assertEqual(generated[1]['category'], 5)
        for old, new in ((row(4), row(999, b'\x2a\x03\x08\x91\x01')),
                         (row(0, b'\x2a\x03\x08\x91\x01'), row(999, b'\x2a\x03\x08\x92\x01')),
                         (row(0), row(999, b'\x2a\x03\x08\x91\x01', b'\xb8\x01\x01')),
                         (row(0), row(999, b'\x2a\x03\x08\x91\x01').replace(b'\x48\x01', b'\x48\x00')),
                         (row(0), row(999))):
            with self.subTest(old=old, new=new), self.assertRaises(ValueError):
                stress.initialized_empty_outfits(payload(old), payload(new))

    def test_only_bounded_appends_preserve_existing_outfit_and_unknown_bytes(self):
        a = {'typed_payload': {'__outfits__': encode(('protobuf', outfit(0, 1) + b'\x10\x03'))}}
        b = {'typed_payload': {'__outfits__': encode(('protobuf', outfit(0, 1) + outfit(7, 2) + b'\x10\x03'))}}
        self.assertEqual(stress.appended_outfits(a, b)[0]['category'], 7)
        for raw in (outfit(0, 3) + outfit(7, 2) + b'\x10\x03', outfit(0, 1) + outfit(7, 2) + b'\x10\x04', outfit(0, 1) + b'\x10\x03'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                stress.appended_outfits(a, {'typed_payload': {'__outfits__': encode(('protobuf', raw))}})
    def test_each_member_each_form_each_panel_and_both_edit_scopes_are_untested(self):
        plan = stress.plan(['1', '2'])
        cells = {(r['sim_id'], r['form'], r['panel'], r['scope']) for r in plan['cells']}
        self.assertEqual(len(cells), 2 * 7 * len(stress.PANELS) * 2)
        self.assertEqual({r['state'] for r in plan['cells']}, {'untested'})
        self.assertFalse(plan['acceptance_complete'])
        self.assertIn(('2', 2, 'clothing_head_skin_details', 'whole-household-edit'), cells)
        self.assertIn(('1', 32, 'clothing_body_tattoos', 'single-member-edit'), cells)
        self.assertEqual(stress.CYCLE[:3], (2, 4, 2))

    def test_unselected_member_and_new_native_field_changes_are_detected(self):
        before = sample(); after = copy.deepcopy(before)
        after['2']['sim']['form_appearances'][4]['appearance']['field_sha256']['future_new_cas_field'] = 'changed'
        self.assertEqual(stress.differences(before, after), [{'sim_id': '2', 'lane': '16',
            'fields': {'future_new_cas_field': {'before': '2:16', 'after': 'changed'}}}])
        after['1']['sim']['full_appearance']['field_sha256']['next_patch_field'] = 'new'
        self.assertEqual(stress.differences(before, after)[0]['fields']['next_patch_field']['before'], None)

    def test_roster_changes_and_removed_owners_are_never_partial_success(self):
        before = sample(); after = copy.deepcopy(before); del after['2']
        self.assertTrue(stress.differences(before, after)[0]['roster_changed'])
        after = copy.deepcopy(before); after['1']['sim']['form_appearances'].pop()
        self.assertTrue(stress.differences(before, after)[0]['owner_inventory_changed'])

    def test_all_memberships_and_every_payload_are_required_before_testing(self):
        snapshot = sample()['1']; stress.validate(snapshot, '1', ['1', '2'], '3', '4')
        for change in ('roster', 'membership', 'fields', 'unpaused'):
            bad = copy.deepcopy(snapshot)
            if change == 'roster': bad['persistence']['household_sim_ids'] = ['1']
            if change == 'membership': bad['sim']['membership'].pop()
            if change == 'fields': bad['sim']['full_appearance']['typed_payload'].pop('future_new_cas_field')
            if change == 'unpaused': bad['clock_speed'] = 1
            with self.subTest(change=change), self.assertRaises(ValueError):
                stress.validate(bad, '1', ['1', '2'], '3', '4')

    def test_active_appearance_and_membership_cannot_be_silently_ignored(self):
        a = sample(); b = copy.deepcopy(a)
        b['1']['sim']['full_appearance']['field_sha256']['__outfits__'] = 'changed'
        b['2']['sim']['membership'].pop()
        changes = stress.differences(a, b)
        self.assertEqual(changes[0]['lane'], 'active')
        self.assertEqual(changes[1]['context'], 'membership')


if __name__ == '__main__':
    unittest.main()
