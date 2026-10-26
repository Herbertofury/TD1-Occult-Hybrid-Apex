"""Native masks must unlock exact genetics without merging or creating owners."""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import native_occult_context as context, cas_bank_transaction as receiver
import test_cas_bank_transaction as fixtures


class FilteredMermaid(Obj):
    @property
    def genetic_data(self):
        return self._genetics if self._base.occult_types & 8 else b'filtered-without-tail'

    @genetic_data.setter
    def genetic_data(self, value):
        if self._base.occult_types & 8:
            self._genetics = value


class AssignmentFilteredMermaid(FilteredMermaid):
    @property
    def genetic_data(self):
        return self._genetics

    @genetic_data.setter
    def genetic_data(self, value):
        if self._base.occult_types & 8:
            self._genetics = value


class NativeOccultContextTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.CasBankReceiverTests(methodName='runTest')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        for lane, owner in self.f.forms.items():
            owner._base = Obj(occult_types=127, current_occult_types=lane)
        self.f.sim._base = Obj(occult_types=127, current_occult_types=64)
        old = self.f.forms[8]
        values = dict(old.__dict__)
        values.pop('genetic_data', None)
        self.f.forms[8] = FilteredMermaid(**values)
        self.f.forms[8]._genetics = b'exact-tail-and-unknown-future-fields\x00\xff'

    def returned_vampire(self):
        f = self.f
        f.sim.current = 4
        f.sim._base.current_occult_types = 4
        f._assign(f.sim, fixtures.appearance.packed(f.backend, f.forms[4]))
        for owner in list(f.forms.values()) + [f.sim]:
            owner._base.occult_types = 4
        f.forms[8]._genetics = b'filtered-without-tail'
        f.edit(4, 'physique', 'edited-vampire-only')

    def planned(self):
        f = self.f
        f.begin()
        self.captured = copy.deepcopy(f.record()['cas_transaction']['native_occult_context'])
        self.returned_vampire()
        f.observe()
        f.prepare([(4, 'accept-returned'), (8, 'restore-original')])

    def assignment_filtered(self):
        f = self.f
        old = f.forms[8]
        f.forms[8] = AssignmentFilteredMermaid(**old.__dict__)
        for owner in list(f.forms.values()) + [f.sim]:
            owner._base.occult_types = 4
        return f

    def test_already_narrowed_checkpoint_restores_tail_using_only_existing_owner_kind(self):
        f = self.assignment_filtered()
        f.begin()
        self.returned_vampire()
        f.observe()
        f.prepare([(4, 'accept-returned'), (8, 'restore-original')])
        native_restore = f.backend._restore_siminfo_payload
        seen = []
        def restore(owner, fields):
            seen.append((owner, owner._base.occult_types))
            if owner is f.forms[8]:
                self.assertEqual(owner._base.occult_types, 8)
                self.assertTrue(all(row._base.occult_types == 4 for row in list(f.forms.values()) + [f.sim] if row is not owner))
                self.assertEqual(f.record()['cas_transaction']['journal']['state'], 'applying')
            return native_restore(owner, fields)
        f.backend._restore_siminfo_payload = restore
        self.assertTrue(f.commit()['all_native_owners_verified'])
        self.assertEqual(f.forms[8].genetic_data, b'exact-tail-and-unknown-future-fields\x00\xff')
        self.assertEqual(f.forms[4].physique, 'edited-vampire-only')
        self.assertTrue(all(row._base.occult_types == 4 for row in list(f.forms.values()) + [f.sim]))
        self.assertEqual(f.record()['cas_transaction']['native_occult_restore']['restored_owners'], [])
        self.assertTrue(receiver._completed(f.record()['cas_transaction']))
        self.assertTrue(seen)

    def test_temporary_owner_context_is_restored_after_failed_appearance_setter_once(self):
        f = self.assignment_filtered()
        before = context.capture(f.backend, f.sim)
        calls = []
        def refused():
            calls.append(True)
            self.assertEqual(f.forms[8]._base.occult_types, 8)
            raise ValueError('Native setter refused exact payload')
        with self.assertRaisesRegex(ValueError, 'Native setter refused'):
            context.appearance_write(f.backend, f.sim, f.forms[8], refused)
        self.assertEqual(context.read(f.backend, f.sim), before)
        self.assertEqual(calls, [True])

    def test_native_human_appearance_does_not_require_an_invented_human_capability_bit(self):
        f = self.assignment_filtered()
        before = context.capture(f.backend, f.sim)
        writes = []
        class HumanBase:
            current_occult_types = 1
            @property
            def occult_types(self): return 4
            @occult_types.setter
            def occult_types(self, value): writes.append(value)
        f.forms[1]._base = HumanBase()
        calls = []
        def restore():
            calls.append(True)
            f.forms[1].physique = 'exact-retained-human'
        context.appearance_write(f.backend, f.sim, f.forms[1], restore)
        self.assertEqual(writes, [])
        self.assertEqual(calls, [True])
        self.assertEqual(f.forms[1].physique, 'exact-retained-human')
        self.assertEqual(context.read(f.backend, f.sim), before)
        diagnostic = f.backend._APEX_NATIVE_OCCULT_WRITE_DIAGNOSTICS[str(f.forms[1].id)]
        self.assertEqual(diagnostic['temporary_available'], 4)
        self.assertEqual(diagnostic['scope'], 'unchanged')
        self.assertTrue(diagnostic['verified'])

    def test_missing_kind_uses_its_own_context_and_restores_preceding_vampire_context(self):
        f = self.assignment_filtered()
        old = f.forms[8]
        class ExclusiveMermaid(AssignmentFilteredMermaid):
            @AssignmentFilteredMermaid.genetic_data.setter
            def genetic_data(self, value):
                if self._base.occult_types == 8:
                    self._genetics = value
        f.forms[8] = ExclusiveMermaid(**old.__dict__)
        f.begin(); self.returned_vampire(); f.observe()
        f.prepare([(4, 'accept-returned'), (8, 'restore-original')])
        self.assertTrue(f.commit()['all_native_owners_verified'])
        self.assertEqual(f.forms[8].genetic_data, b'exact-tail-and-unknown-future-fields\x00\xff')
        self.assertEqual(f.forms[4].physique, 'edited-vampire-only')
        diagnostic = f.backend._APEX_NATIVE_OCCULT_WRITE_DIAGNOSTICS[str(f.forms[8].id)]
        self.assertEqual(diagnostic['temporary_available'], 8)
        self.assertEqual(diagnostic['scope'], 'selected-owner')
        self.assertTrue(diagnostic['payload_completed'] and diagnostic['verified'])
        self.assertTrue(all(row._base.occult_types == 4 for row in list(f.forms.values()) + [f.sim]))
        self.assertTrue(receiver._completed(f.record()['cas_transaction']))

    def test_temporary_owner_context_refuses_cross_owner_effect_before_payload(self):
        f = self.assignment_filtered()
        primary = f.sim._base
        class CrossOwnerBase:
            current_occult_types = 8
            _available = 4
            @property
            def occult_types(self): return self._available
            @occult_types.setter
            def occult_types(self, value):
                self._available = value
                if value != 4:
                    primary.occult_types = 12
        f.forms[8]._base = CrossOwnerBase()
        calls = []
        with self.assertRaisesRegex(ValueError, 'another owner'):
            context.appearance_write(f.backend, f.sim, f.forms[8], lambda: calls.append(True))
        self.assertEqual(calls, [])
        self.assertEqual(f.forms[8]._base.occult_types, 4)
        self.assertEqual(primary.occult_types, 12)

    def test_temporary_context_cannot_hide_genetics_filtered_again_after_reset(self):
        f = self.f
        for owner in list(f.forms.values()) + [f.sim]: owner._base.occult_types = 4
        desired = fixtures.appearance.packed(f.backend, f.forms[8])
        desired['genetic_data'] = fixtures.appearance.encode(b'exact-tail-and-unknown-future-fields\x00\xff')
        def assign(owner, fields):
            for name, value in fields.items(): setattr(owner, name, value)
        f.backend._restore_siminfo_payload = assign
        with self.assertRaisesRegex(ValueError, 'exact appearance readback'):
            fixtures.form_bank.restore(f.backend, f.sim, '8', desired)
        self.assertTrue(all(row._base.occult_types == 4 for row in list(f.forms.values()) + [f.sim]))

    def shared_bases(self, available=4):
        f = self.assignment_filtered()
        shared = Obj(available=available)
        class SharedBase:
            def __init__(self, current): self.current_occult_types = current
            @property
            def occult_types(self): return shared.available
            @occult_types.setter
            def occult_types(self, value): shared.available = value
        for lane, owner in f.forms.items(): owner._base = SharedBase(lane)
        f.sim._base = SharedBase(f.sim.current)
        return f

    def test_complete_shared_availability_restores_exact_tail_and_original_context(self):
        f = self.shared_bases()
        f.begin(); self.returned_vampire(); f.observe()
        f.prepare([(4,'accept-returned'),(8,'restore-original')])
        self.assertTrue(f.commit()['all_native_owners_verified'])
        self.assertEqual(f.forms[8].genetic_data, b'exact-tail-and-unknown-future-fields\x00\xff')
        diagnostic = f.backend._APEX_NATIVE_OCCULT_WRITE_DIAGNOSTICS[str(getattr(f.forms[8],'id','8'))]
        self.assertEqual(diagnostic['scope'], 'complete-shared-availability')
        self.assertTrue(diagnostic['payload_completed'] and diagnostic['verified'])
        self.assertTrue(all(row._base.occult_types == 4 for row in list(f.forms.values()) + [f.sim]))
        self.assertTrue(receiver._completed(f.record()['cas_transaction']))

    def test_captured_mask_restore_admits_only_complete_shared_readback(self):
        f = self.shared_bases(127)
        self.planned()
        self.assertTrue(f.commit()['all_native_owners_verified'])
        restored = f.record()['cas_transaction']['native_occult_restore']
        self.assertEqual(restored['restored_owners'], ['1','2','4','8','16','32','64','active'])
        self.assertTrue(all(row['available'] == 127 for row in restored['after'].values()))
        self.assertTrue(receiver._completed(f.record()['cas_transaction']))

    def test_shared_mask_never_admits_changed_current_kind(self):
        f = self.shared_bases()
        native_restore = f.backend._restore_siminfo_payload
        def refused(owner, fields):
            native_restore(owner, fields)
            f.forms[2]._base.current_occult_types = 1
        f.backend._restore_siminfo_payload = refused
        f.begin(); self.returned_vampire(); f.observe()
        f.prepare([(4,'accept-returned'),(8,'restore-original')])
        with self.assertRaisesRegex(ValueError,'native context'):
            f.commit()
        self.assertTrue(all(row._base.occult_types == 4 for row in list(f.forms.values()) + [f.sim]))
        self.assertFalse(receiver._completed(f.record()['cas_transaction']))
        self.assertEqual(f.record()['cas_transaction']['journal']['bank_commit_outcome'],'not-attempted')

    def test_filtered_tail_restores_only_after_captured_masks_and_retains_vampire_edits(self):
        f = self.f
        self.planned()
        native_restore = f.backend._restore_siminfo_payload
        def restore(owner, fields):
            self.assertTrue(all(row._base.occult_types == 127 for row in list(f.forms.values()) + [f.sim]))
            self.assertIsNotNone(f.record()['cas_transaction']['native_occult_restore'])
            native_restore(owner, fields)
        f.backend._restore_siminfo_payload = restore
        result = f.commit()
        self.assertTrue(result['all_native_owners_verified'])
        self.assertEqual(f.forms[8].genetic_data, b'exact-tail-and-unknown-future-fields\x00\xff')
        self.assertEqual(f.forms[4].physique, 'edited-vampire-only')
        transaction = f.record()['cas_transaction']
        self.assertEqual(transaction['native_occult_restore']['restored_owners'], ['1','2','4','8','16','32','64','active'])
        self.assertEqual(transaction['journal']['final_native_appearance']['native_occult_context']['observed']['active']['current'], 4)
        self.assertEqual(f.sim._base.current_occult_types, 4)
        self.assertTrue(receiver._completed(transaction))
        self.assertTrue(receiver.assert_idle(f.backend, f.sim))
        self.assertEqual(f.data()['records']['30:99'], f.foreign)
        historical = copy.deepcopy(transaction)
        historical['native_occult_restore']['restored_owners'].pop()
        self.assertFalse(receiver._completed(historical))

    def test_corrupted_or_partial_native_begin_refuses_before_metadata_or_setters(self):
        f = self.f
        before = f.path.read_bytes()
        f.sim._base.occult_types = 4
        with self.assertRaisesRegex(ValueError, 'differs between'):
            f.begin()
        self.assertEqual(f.path.read_bytes(), before)
        self.assertEqual(f.native_writes, [])
        f.sim._base.occult_types = 127
        del f.forms[2]._base
        with self.assertRaisesRegex(ValueError, 'missing or aliased'):
            f.begin()
        self.assertEqual(f.path.read_bytes(), before)

    def test_replaced_primary_and_wrappers_use_fresh_current_bases_without_replay(self):
        f = self.f
        f.begin()
        old_primary, old_forms = f.sim, f.forms
        f.sim, f.forms = copy.deepcopy(f.sim), copy.deepcopy(f.forms)
        self.returned_vampire()
        f.observe()
        f.prepare([(4,'accept-returned'),(8,'restore-original')])
        self.assertTrue(f.commit()['ok'])
        self.assertEqual(old_primary._base.current_occult_types, 64)
        self.assertEqual(old_forms[8]._genetics, b'exact-tail-and-unknown-future-fields\x00\xff')
        self.assertEqual(f.sim._base.current_occult_types, 4)

    def test_availability_tamper_invalidates_envelope_before_native_write(self):
        f = self.f
        self.planned()
        data = json.loads(f.path.read_text())
        data['records'][f.key]['cas_transaction']['native_occult_context']['8']['available'] = 126
        f.path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            f.commit()
        self.assertEqual(f.native_writes, [])
        self.assertEqual(f.sim._base.occult_types, 4)

    def test_cross_owner_setter_side_effect_keeps_failed_wal_and_does_not_commit_bank(self):
        f = self.f
        self.planned()
        primary = f.sim._base
        class CrossOwnerBase:
            current_occult_types = 1
            value = 4
            @property
            def occult_types(self):
                return self.value
            @occult_types.setter
            def occult_types(self, value):
                self.value = value
                primary.current_occult_types = 2
        f.forms[1]._base = CrossOwnerBase()
        with self.assertRaisesRegex(ValueError, 'another owner/current'):
            f.commit()
        transaction = f.record()['cas_transaction']
        self.assertEqual(transaction['journal']['state'], 'recovery-required')
        self.assertTrue(transaction['journal']['native_write_possible'])
        self.assertFalse(transaction['journal']['bank_commit_attempted'])
        self.assertIsNotNone(f.record()['pending'])
        self.assertEqual(f.record()['bank'], f.initial['records'][f.key]['bank'])
        self.assertEqual(f.native_writes, [])
        with self.assertRaises(ValueError):
            f.commit()

    def test_later_appearance_setter_cannot_silently_renarrow_native_masks(self):
        f = self.f
        self.planned()
        native_restore = f.backend._restore_siminfo_payload
        def restore(owner, fields):
            native_restore(owner, fields)
            if owner.owner_lane == '8':
                f.sim._base.occult_types = 4
        f.backend._restore_siminfo_payload = restore
        with self.assertRaisesRegex(ValueError, 'availability|context'):
            f.commit()
        transaction = f.record()['cas_transaction']
        self.assertEqual(transaction['journal']['state'], 'recovery-required')
        self.assertFalse(transaction['journal']['bank_commit_attempted'])
        self.assertIsNotNone(f.record()['pending'])

    def test_metadata_callback_mask_drift_cannot_open_completed_gate(self):
        f = self.f
        self.planned()
        original = receiver.atomic_save
        def save(path, data, *args, **kwargs):
            result = original(path, data, *args, **kwargs)
            if data['records'][f.key].get('cas_transaction', {}).get('metadata_commit', {}).get('committed') is True:
                f.sim._base.occult_types = 4
            return result
        with patch.object(receiver, 'atomic_save', side_effect=save):
            with self.assertRaisesRegex(ValueError, 'availability|context'):
                f.commit()
        transaction = f.record()['cas_transaction']
        self.assertFalse(receiver._completed(transaction))
        self.assertEqual(transaction['journal']['state'], 'recovery-required')
        self.assertEqual(transaction['journal']['bank_commit_outcome'], 'unresolved')
        with self.assertRaises(ValueError):
            receiver.assert_idle(f.backend, f.sim)

    def test_human_bit_is_not_invented_when_native_checkpoint_excludes_it(self):
        f = self.f
        for owner in list(f.forms.values()) + [f.sim]:
            owner._base.occult_types = 126
        captured = context.capture(f.backend, f.sim)
        self.assertEqual(captured['1']['available'], 126)
        receipt = context.restore(f.backend, f.sim, captured)
        self.assertEqual(receipt['restored_owners'], [])
        self.assertEqual(f.sim._base.occult_types, 126)

    def test_native_availability_is_not_synthesized_from_trait_membership_or_stored_keys(self):
        f = self.f
        for owner in list(f.forms.values()) + [f.sim]:
            owner._base.occult_types = 65
        captured = context.capture(f.backend, f.sim)
        for owner in list(f.forms.values()) + [f.sim]:
            owner._base.occult_types = 4
        result = context.restore(f.backend, f.sim, captured)
        self.assertTrue(result['verified'])
        self.assertTrue(all(row['available'] == 65 for row in result['after'].values()))
        self.assertEqual(f.sim._base.current_occult_types, 64)


if __name__ == '__main__':
    unittest.main()
