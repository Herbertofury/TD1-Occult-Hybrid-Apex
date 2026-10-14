"""CAS availability projection must preserve appearances, traits and identity."""
from pathlib import Path
import json
import sys
import tempfile
from types import SimpleNamespace as Obj
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import cas_entry_context as entry, form_appearance as appearance
from test_native_witch_persistence import Owner


class CasEntryContextTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.path = Path(temp.name); self.sims = []
        for identity, current in ((100, 2), (200, 4)):
            sim = Owner(identity, 'active', identity)
            sim.household_id = 55; sim.current_occult_types = current; sim.occult_types = 65
            forms = {kind: Owner(identity + kind, 'form-' + str(kind), identity + kind) for kind in (1, 2, 4, 8, 16, 32, 64)}
            for kind, owner in forms.items(): owner.current_occult_types = kind; owner.occult_types = 65
            sim.occult_tracker = Obj(_sim_info_map=forms, has_occult_type=lambda kind: True)
            self.sims.append(sim)
        self.household = Obj(id=55, sim_info_gen=lambda: iter(self.sims)); self.writes = []
        self.backend = Obj(_data_directory=lambda: str(self.path), _form_map=lambda tracker: tracker._sim_info_map,
            _get_current_flags=lambda sim: sim.current_occult_types, _coerce_flags=int,
            _get_sim_info_by_id=lambda identity: next((sim for sim in self.sims if str(sim.id) == identity), None),
            _disk_trait_snapshot=lambda sim: {'traits': [11, 22, 33]}, _set_flags=self.set_flags,
            _v8_read_outfit_blob=lambda owner: owner.blob,
            services=Obj(active_household=lambda: self.household,
                         get_persistence_service=lambda: Obj(get_save_slot_proto_guid=lambda: 77)))
        self.before = {sim.id: {str(kind): appearance.packed(self.backend, owner)
                               for kind, owner in dict(sim.occult_tracker._sim_info_map, active=sim).items()}
                       for sim in self.sims}

    def set_flags(self, sim, name, value):
        self.assertEqual(name, 'occult_types')
        held = json.loads((self.path / 'household_cas_entry.json').read_text())
        self.assertEqual(held['stage'], 'native-write-intent')
        row = next(row for row in held['members'] if row['sim_id'] == str(sim.id))
        self.assertTrue(row['write_attempted']); self.assertEqual(row['original_appearances'], self.before[sim.id])
        self.writes.append((sim.id, value))
        # Native Vampire normalizes 5 to 4; all wrappers share availability.
        value = 4 if value == 5 else value
        for owner in [sim] + list(sim.occult_tracker._sim_info_map.values()): owner.occult_types = value

    def test_household_projects_existing_pairs_without_changing_traits_or_appearance(self):
        proof = entry.prepare(self.backend, self.sims[1], True)
        self.assertEqual(self.writes, [(100, 3), (200, 5)])
        self.assertEqual(proof['prepared_members'], [{'sim_id': '100', 'available': 3, 'current': 2},
                                                    {'sim_id': '200', 'available': 4, 'current': 4}])
        self.assertTrue(proof['all_appearances_and_traits_unchanged'])
        self.assertFalse(proof['crash_fix_verified'])

    def test_single_selected_scope_does_not_change_other_household_member(self):
        entry.prepare(self.backend, self.sims[0], False)
        self.assertEqual(self.writes, [(100, 3)]); self.assertEqual(self.sims[1].occult_types, 65)

    def test_membership_absence_refuses_before_any_write(self):
        self.sims[1].occult_tracker.has_occult_type = lambda kind: False
        with self.assertRaisesRegex(ValueError, 'membership'): entry.prepare(self.backend, self.sims[0], True)
        self.assertEqual(self.writes, []); self.assertFalse((self.path / 'household_cas_entry.json').exists())

    def test_native_setter_refusal_retains_preimages_and_blocks_replay(self):
        self.backend._set_flags = lambda *args: False
        with self.assertRaisesRegex(ValueError, 'availability'): entry.prepare(self.backend, self.sims[0], True)
        raw = (self.path / 'household_cas_entry.json').read_bytes()
        self.assertEqual(json.loads(raw)['stage'], 'unresolved')
        with self.assertRaisesRegex(ValueError, 'unresolved'): entry.prepare(self.backend, self.sims[0], True)
        self.assertEqual((self.path / 'household_cas_entry.json').read_bytes(), raw)

    def test_appearance_side_effect_is_retained_as_failure_never_replayed(self):
        def bad(sim, name, value):
            self.set_flags(sim, name, value); sim.physique = 'changed by native setter'
        self.backend._set_flags = bad
        with self.assertRaisesRegex(ValueError, 'appearance'): entry.prepare(self.backend, self.sims[0], True)
        self.assertEqual(len(self.writes), 1)
        proof = json.loads((self.path / 'household_cas_entry.json').read_text())
        self.assertEqual(proof['members'][0]['original_appearances'], self.before[100])
        self.assertFalse(proof['retry_safe'])

    def test_changed_native_current_kind_cannot_be_accepted(self):
        def bad(sim, name, value):
            self.set_flags(sim, name, value); sim.current_occult_types = 1
        self.backend._set_flags = bad
        with self.assertRaisesRegex(ValueError, 'current kind'): entry.prepare(self.backend, self.sims[0], True)
        self.assertEqual(len(self.writes), 1)


if __name__ == '__main__': unittest.main()
