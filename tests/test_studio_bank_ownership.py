"""A previous process's bank cannot become the editor's native baseline."""
import copy
import json
import os
import unittest
from unittest.mock import patch

import test_studio
from apex_core import form_bank, form_appearance as appearance, studio, form_bank_seal


class StudioBankOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_studio.StudioTests('runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.stored_form()
        form_bank.update(self.fixture.backend, self.fixture.sim, 4,
                         appearance.packed(self.fixture.backend, self.fixture.vampire), create=True)
        self.path, self.key = form_bank.context(self.fixture.backend, self.fixture.sim)

    def prior_bank(self):
        data = form_bank.load(self.path)
        record = data['records'][self.key]
        record['runtime_pid'] = os.getpid() + 10000
        record['bank']['4']['physique']['value'] = 'Stale prior-runtime Vampire'
        record['bank']['4']['skin_tone']['value'] = 1
        record['bank']['16'] = copy.deepcopy(record['bank']['4'])
        form_bank.save(self.path, data)
        self.fixture.vampire.physique = 'Fresh actual native Vampire'
        self.fixture.vampire.skin_tone = 987654
        return self.path.read_bytes()

    def test_status_and_inventory_ignore_stale_bank_and_missing_phantom_owner(self):
        before = self.prior_bank()
        result = self.fixture.stored_request('studio_status')
        self.assertEqual(result['appearance_source'], 'Native stored form')
        forms = {row['flags']: row for row in result['form_inventory']}
        self.assertEqual(set(forms), {4, 32})
        self.assertEqual(forms[4]['source'], 'Native stored form')
        fields = {row['name']: row['value'] for row in forms[4]['appearance_fields']}
        self.assertEqual(fields['physique'], 'Fresh actual native Vampire')
        self.assertEqual(fields['skin_tone'], 987654)
        self.assertEqual(self.path.read_bytes(), before)

    def test_explicit_part_edit_uses_fresh_native_baseline_and_preserves_other_fields(self):
        self.prior_bank()
        fresh = self.fixture.vampire.raw
        active = appearance.packed(self.fixture.backend, self.fixture.sim)
        status = self.fixture.stored_request('studio_status')
        preview = self.fixture.stored_preview(status)
        self.fixture.stored_request('studio_apply', preview['preview_id'])
        self.assertEqual(self.fixture.vampire.physique, 'Fresh actual native Vampire')
        self.assertEqual(self.fixture.vampire.skin_tone, 987654)
        self.assertNotEqual(self.fixture.vampire.raw, fresh)
        self.assertEqual(appearance.packed(self.fixture.backend, self.fixture.sim), active)
        record = form_bank.load(self.path)['records'][self.key]
        self.assertEqual(record['runtime_pid'], os.getpid())
        self.assertNotIn('16', record['bank'])
        self.assertEqual(record['bank']['4']['physique']['value'], 'Fresh actual native Vampire')

    def test_stale_bank_without_native_owner_cannot_stage_or_generate_a_form(self):
        self.prior_bank()
        with self.assertRaisesRegex(ValueError, 'No existing appearance owner'):
            self.fixture.stored_request('studio_status', form=16)
        self.assertEqual(self.fixture.sim.flags, 32)
        self.assertEqual(set(self.fixture.backend._form_map(self.fixture.sim.occult_tracker)), {4, 32})

    def test_current_runtime_accepted_bank_remains_available_when_native_owner_missing(self):
        self.fixture.backend._form_map = lambda _: {32: self.fixture.sim}
        result = self.fixture.stored_request('studio_status')
        self.assertEqual(result['appearance_source'], 'Accepted independent appearance bank')
        forms = {row['flags']: row for row in result['form_inventory']}
        self.assertEqual(forms[4]['source'], 'Accepted independent appearance bank')
        self.assertEqual(set(forms), {4, 32})

    def test_consumed_exact_reload_receipt_can_authorize_retained_bank(self):
        self.prior_bank()
        with patch.object(form_bank_seal, 'current_runtime_bank_verified', return_value=True) as verified:
            result = self.fixture.stored_request('studio_status')
        self.assertEqual(result['appearance_source'], 'Accepted independent appearance bank')
        self.assertGreaterEqual(verified.call_count, 2)

    def test_unavailable_or_rejected_reload_receipt_never_substitutes_stale_fields(self):
        self.prior_bank()
        for outcome in (False, ValueError('No certified owner receipt')):
            with self.subTest(outcome=str(outcome)):
                options = {'side_effect': outcome} if isinstance(outcome, Exception) else {'return_value': outcome}
                with patch.object(form_bank_seal, 'current_runtime_bank_verified', **options):
                    result = self.fixture.stored_request('studio_status')
                self.assertEqual(result['appearance_source'], 'Native stored form')


if __name__ == '__main__':
    unittest.main()
