"""Explicit phone/F11 hair intent against the real receiver and native protobuf."""
import copy
import json
import unittest

import test_phone_cas as phone_fixture
from apex_core import phone_cas, outfit_hair, form_appearance as appearance
from apex_core.dresser_parts import read_rows


class PhoneCasHairTests(unittest.TestCase):
    setUp = phone_fixture.PhoneCasTests.setUp
    fire = phone_fixture.PhoneCasTests.fire
    observe = phone_fixture.PhoneCasTests.observe
    ui = phone_fixture.PhoneCasTests.ui

    def prepare_hair(self, lanes=(64,)):
        self.game.enable_hair()
        self.session.begin()
        def propagate(message):
            for index, outfit in enumerate(message.outfits):
                outfit.parts.ids[0] = (1 << 64) - 300 - index
                outfit.parts.ids[1] = 70000 + index
                outfit.part_shifts.color_shift[0] = (1 << 64) - 400 - index
                outfit.part_shifts.color_shift[1] = (1 << 63) + index
                outfit.parts.ids[2] = 95000 + index
        for lane in lanes:
            self.game.mutate_outfits(lane, propagate)
        self.observe()
        return self.ui('status')

    def choose_form(self, lane='64', action='accept-returned'):
        return phone_cas.select(self.backend, '10', 'cas:decision:{}:{}:{}'.format(self.session.nonce, lane, action))

    def picker(self, lane='64'):
        page = phone_cas.rows(self.backend, '10', 'cas_form:' + lane)
        tag = next(tag for tag, _label, _icon in page if tag.startswith('cas:hair-page:'))
        return phone_cas.select(self.backend, '10', tag)['page']

    def choose_slot(self, page, category, ordinal):
        tags = [tag for tag, _label, _icon in phone_cas.rows(self.backend, '10', page) if tag.startswith('cas:hair:')]
        tag = next(tag for tag in tags if tag.split(':')[5:7] == [str(category), str(ordinal)])
        return phone_cas.select(self.backend, '10', tag)

    def argument(self, status, targets):
        return {'expected_pending_sha256': status['expected_pending_sha256'],
            'expected_raw_return_sha256': status['raw_return_sha256'], 'review_nonce': status['review_nonce'],
            'dispositions': [{'lane': '64', 'action': 'accept-returned'}],
            'hair_targets': targets, 'hair_inventory_sha256': status['hair_inventory_sha256']}

    def test_phone_picker_keeps_only_explicit_numbered_outfit_hair_and_exact_colors(self):
        self.prepare_hair()
        held = copy.deepcopy(self.game.record()['cas_transaction']['hair_checkpoint']['forms'])
        returned = appearance.packed(self.backend, self.game.forms[64])
        self.choose_form()
        page = self.picker()
        self.choose_slot(page, 0, 1)
        self.choose_slot(page, 1, 0)
        self.assertEqual(self.game.native_writes, [])
        phone_cas.select(self.backend, '10', 'cas:prepare:' + self.session.nonce)
        phone_cas.select(self.backend, '10', 'cas:commit:' + self.session.nonce)
        final = self.game.record()['bank']['64']
        returned_hair = outfit_hair.capture(self.backend, returned)
        final_hair = outfit_hair.capture(self.backend, final)
        for before, changed, accepted in zip(held['64'], returned_hair, final_hair):
            selected = (before['category'], before['ordinal']) in {(0, 1), (1, 0)}
            self.assertEqual(accepted['hair'], changed['hair'] if selected else before['hair'])
        for lane in ('1', '2', '4', '8', '16', '32'):
            self.assertEqual(self.game.record()['bank'][lane], self.game.originals[lane])
        for old, new in zip(self.game.parse(appearance.decode(returned['__outfits__'])[1]).outfits,
                            self.game.parse(appearance.decode(final['__outfits__'])[1]).outfits):
            self.assertEqual(read_rows(old)[2], read_rows(new)[2])  # Clothing never follows hair repair.
        self.assertEqual(self.game.record()['cas_transaction']['journal']['plan']['hair_targets'], self.session.hair_targets)
        self.assertEqual(sum(action == 'cas_bank_prepare' for action, _ in self.actions), 1)
        self.assertEqual(sum(action == 'cas_bank_commit' for action, _ in self.actions), 1)

    def test_f11_inventory_contains_every_form_outfit_uid_and_no_inferred_selection(self):
        status = self.prepare_hair()
        self.assertTrue(status['hair_inventory_available'])
        inventory = status['hair_inventory']
        self.assertEqual(inventory['sim_id'], '10')
        self.assertEqual(inventory['review_nonce'], status['review_nonce'])
        self.assertEqual(len(inventory['forms']), 7)
        self.assertEqual(status['hair_targets'], {})
        for form in inventory['forms']:
            self.assertEqual(len(form['outfits']), 9)
            self.assertTrue(form['wardrobe_unchanged'])
            self.assertEqual(form['outfits'][0]['ordinal'], 0)
            self.assertEqual(form['outfits'][1]['ordinal'], 1)
            self.assertEqual(form['outfits'][0]['outfit_id'], str((1 << 64) - 20))
        self.assertNotIn('original-64', json.dumps(inventory))
        self.assertNotIn('hair', inventory['forms'][0]['outfits'][0])
        self.assertEqual(self.game.native_writes, [])

    def test_f11_supplied_exact_targets_roundtrip_through_receiver_ack_and_apply(self):
        status = self.prepare_hair()
        targets = self.game.targets(64, [(0, 1), (7, 0)])
        prepared = self.ui('prepare', self.argument(status, targets))
        self.assertEqual(prepared['hair_targets'], targets)
        self.assertEqual(prepared['hair_inventory_sha256'], status['hair_inventory_sha256'])
        self.assertTrue(prepared['hair_isolation_planned'])
        self.assertEqual(self.game.native_writes, [])
        committed = self.ui('commit', {'expected_pending_sha256': status['expected_pending_sha256'],
            'expected_plan_sha256': prepared['plan_sha256'], 'review_nonce': status['review_nonce']})
        self.assertTrue(committed['all_native_owners_verified'])
        held = self.game.record()['cas_transaction']['hair_checkpoint']['forms']['64']
        final = outfit_hair.capture(self.backend, self.game.record()['bank']['64'])
        for original, accepted in zip(held, final):
            if (accepted['category'], accepted['ordinal']) in {(0, 1), (7, 0)}:
                self.assertNotEqual(original['hair'], accepted['hair'])
            else:
                self.assertEqual(original['hair'], accepted['hair'])

    def test_stale_duplicate_foreign_uid_boolean_and_external_hair_intent_refuse_before_plan_attempt(self):
        status = self.prepare_hair()
        valid = self.game.targets(64, [(0, 1)])
        wrong_uid = copy.deepcopy(valid); wrong_uid['64'][0]['outfit_id'] = '11'
        duplicate = copy.deepcopy(valid); duplicate['64'].append(copy.deepcopy(duplicate['64'][0]))
        boolean = copy.deepcopy(valid); boolean['64'][0]['ordinal'] = True
        external = copy.deepcopy(valid); external['64'][0]['hair'] = 'forged appearance'
        invalids = [dict(self.argument(status, valid), hair_inventory_sha256='e' * 64),
            dict(self.argument(status, valid), review_nonce='f' * 32), self.argument(status, wrong_uid),
            self.argument(status, duplicate), self.argument(status, boolean), self.argument(status, external),
            self.argument(status, {'1': valid['64']}), self.argument(status, {'64': []})]
        for argument in invalids:
            with self.subTest(argument=argument), self.assertRaises(ValueError):
                self.ui('prepare', argument)
            self.assertEqual(self.session.decisions, {})
            self.assertFalse(self.session.prepare_attempted)
        self.assertFalse(any(action == 'cas_bank_prepare' for action, _ in self.actions))
        self.assertEqual(self.game.native_writes, [])

    def test_missing_target_does_not_consume_plan_and_phone_choice_then_succeeds(self):
        self.prepare_hair()
        self.choose_form()
        with self.assertRaisesRegex(ValueError, 'specific outfits'):
            self.session.prepare(self.session.nonce)
        self.assertFalse(self.session.prepare_attempted)
        self.assertEqual(self.session.phase, 'observed')
        self.choose_slot(self.picker(), 0, 1)
        self.assertTrue(self.session.prepare(self.session.nonce)['ok'])

    def test_every_outfit_is_reachable_across_phone_pages_without_silent_cap(self):
        message = self.game.parse(self.game.forms[64].blob)
        for index in range(35):
            outfit = message.outfits.add()
            outfit.CopyFrom(message.outfits[0])
            outfit.outfit_id = (1 << 63) + index
            outfit.category = 500 + index // 3
        self.game.edit(64, 'blob', message.SerializeToString())
        self.prepare_hair()
        self.choose_form()
        page, offered = self.picker(), []
        while True:
            rows = phone_cas.rows(self.backend, '10', page)
            offered.extend(tag.split(':')[7] for tag, _label, _icon in rows if tag.startswith('cas:hair:'))
            following = [tag for tag, label, _icon in rows if label == 'Next outfits']
            if not following:
                break
            page = phone_cas.select(self.backend, '10', following[0])['page']
        self.assertEqual(len(offered), 44)
        self.assertEqual(len(set(offered)), 44)
        self.assertEqual(set(offered), {str(outfit.outfit_id) for outfit in message.outfits})
        self.assertEqual(self.session.hair_targets, {})

    def test_restore_form_clears_old_hair_choice_and_stale_tags_cannot_restore_it(self):
        self.prepare_hair()
        self.choose_form()
        page = self.picker()
        tag = next(tag for tag, _label, _icon in phone_cas.rows(self.backend, '10', page) if tag.startswith('cas:hair:'))
        phone_cas.select(self.backend, '10', tag)
        self.assertIn('64', self.session.hair_targets)
        self.choose_form(action='restore-original')
        self.assertEqual(self.session.hair_targets, {})
        with self.assertRaisesRegex(ValueError, 'Keep returned edit'):
            phone_cas.select(self.backend, '10', tag)

    def test_added_and_removed_outfits_remain_visible_but_cannot_supply_guessed_hair_uid(self):
        self.game.enable_hair(); self.session.begin()
        def replace_wardrobe(message):
            del message.outfits[-1]
            added = message.outfits.add()
            added.CopyFrom(message.outfits[0])
            added.category, added.outfit_id = 500, 1234567
        self.game.mutate_outfits(64, replace_wardrobe)
        self.observe(); self.choose_form()
        status = self.ui('status')
        form = next(row for row in status['hair_inventory']['forms'] if row['lane'] == '64')
        self.assertFalse(form['wardrobe_unchanged'])
        self.assertEqual(len(form['outfits']), 10)
        self.assertTrue(any(row['original_outfit_id'] is None and row['returned_outfit_id'] == '1234567' for row in form['outfits']))
        self.assertTrue(any(row['original_outfit_id'] is not None and row['returned_outfit_id'] is None for row in form['outfits']))
        self.assertTrue(all(not row['selectable'] for row in form['outfits']))
        page = self.picker()
        self.assertFalse(any(tag.startswith('cas:hair:') for tag, _label, _icon in phone_cas.rows(self.backend, '10', page)))
        with self.assertRaisesRegex(ValueError, 'wardrobe'):
            self.session.prepare(self.session.nonce)
        self.assertFalse(self.session.prepare_attempted)
        self.assertEqual(self.game.native_writes, [])

    def test_replaced_native_owner_or_tampered_checkpoint_refuses_picker_without_rehydration(self):
        self.prepare_hair()
        self.choose_form()
        self.game.forms[64] = copy.deepcopy(self.game.forms[64])
        status = self.ui('status')
        self.assertFalse(status['hair_inventory_available'])
        self.assertIn('owner', status['hair_inventory_error'])
        with self.assertRaises(ValueError):
            self.session.hair_inventory()
        self.assertEqual(self.game.native_writes, [])

    def test_face_only_acceptance_does_not_invent_hair_target(self):
        self.game.enable_hair(); self.session.begin(); self.game.edit(64, 'facial_attributes', b'new face'); self.observe()
        self.choose_form()
        self.assertTrue(self.session.prepare(self.session.nonce)['ok'])
        self.assertEqual(self.session.receipts[-1]['argument']['hair_targets'], {})
        self.assertTrue(self.session.commit(self.session.nonce)['ok'])

    def test_unknown_plan_ack_is_never_replayed_and_retains_explicit_target_intent(self):
        self.prepare_hair(); self.choose_form(); self.choose_slot(self.picker(), 0, 1)
        def lost(action, result):
            if action == 'cas_bank_prepare':
                raise OSError('hair plan ACK lost')
        self.fault = lost
        with self.assertRaises(OSError):
            self.session.prepare(self.session.nonce)
        self.fault = None
        with self.assertRaises(ValueError):
            self.session.prepare(self.session.nonce)
        self.assertEqual(self.game.record()['cas_transaction']['journal']['plan']['hair_targets'], self.session.hair_targets)
        self.assertEqual(sum(action == 'cas_bank_prepare' for action, _ in self.actions), 1)
        self.assertEqual(self.game.native_writes, [])


if __name__ == '__main__':
    unittest.main()
