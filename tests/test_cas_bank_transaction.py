"""Real atomic form-bank receiver with constructed native owners/proto fixtures."""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import cas_bank_transaction as receiver, cas_commit_plan as primitive
from apex_core import form_bank, form_appearance as appearance, outfit_hair, sim_data
from apex_core.dresser_parts import read_rows
from test_outfit_hair import native_outfit_parser, native_outfit_fields


def _native_snapshot(sim, raw=b'\x08\x0a\xa2\x06\x03new'):
    return {'schema': 1, 'native_message_type': 'Fixture.SimData',
            'native_sha256': hashlib.sha256(raw).hexdigest(), 'native_bytes': len(raw),
            'native_base64': base64.b64encode(raw).decode('ascii'),
            'sim_id': str(sim.id), 'save_guid': '30',
            'data': {'message_type': 'Fixture.SimData', 'fields': []},
            'field_schemas': {'Fixture.SimData': []},
            'unknown_fields_retained_in_native_bytes': True,
            'native_serializer_called': True, 'save_file_written': False}


class CasBankReceiverTests(unittest.TestCase):
    def setUp(self):
        receiver._ACTIVE.clear()
        receiver._CAPTURED.clear()
        receiver._WRITER_LEASES.clear()
        self.addCleanup(receiver._ACTIVE.clear)
        self.addCleanup(receiver._CAPTURED.clear)
        self.addCleanup(receiver._WRITER_LEASES.clear)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parse = native_outfit_parser()
        self.forms = {}
        for lane in (1, 2, 4, 8, 16, 32, 64):
            fields = native_outfit_fields(self.parse)
            fields['physique'] = appearance.encode('original-' + str(lane))
            fields['facial_attributes'] = appearance.encode(b'face unknown\x00\xff')
            message = self.parse(appearance.decode(fields['__outfits__'])[1])
            for index, item in enumerate(message.outfits):
                item.parts.ids.append(90000 + lane + index)
                item.body_types_list.body_types.append(9)
                item.part_shifts.color_shift.append((1 << 64) - 1000 - index)
                item.object_ids.object_id.append(80000 + index)
                item.layer_ids.layer_id.append(19)
            fields['__outfits__'] = appearance.encode(('protobuf', message.SerializeToString()))
            owner = Obj(id=10, owner_lane=str(lane))
            self._assign(owner, fields)
            self.forms[lane] = owner
        self.sim = copy.deepcopy(self.forms[64])
        self.sim.id, self.sim.household_id, self.sim.current = 10, 20, 64
        self.sim.owner_lane = 'active'
        self.sim.occult_tracker = Obj()
        self.native_writes, self.visual_resends, self.ensure_calls = [], [], []
        self.backend = Obj(_data_directory=lambda: self.temp.name,
            _APEX_GAME_THREAD_IDENT=threading.current_thread().ident,
            _get_sim_info_by_id=lambda _: self.sim,
            _get_current_flags=lambda sim: sim.current, _all_occults=lambda: (2, 4, 8, 16, 32, 64),
            _form_map=lambda _: self.forms, _v8_read_outfit_blob=lambda sim: sim.blob,
            _studio_parse_snapshot=self.parse,
            _v8_resolve_body_type=lambda name: (2 if name == 'HAIR' else 75, {}, 'native-fixture'),
            _coerce_flags=lambda flags: flags,
            _ensure_human_form=lambda _: self.forms.get(1), _ensure_form=self.ensure_form,
            _restore_siminfo_payload=self.restore,
            _resend_all_visuals=lambda sim: self.visual_resends.append(sim.owner_lane),
            _add_occult=lambda *_a, **_k: self.fail('CAS receiver must never generate membership'),
            _restore_disk_trait_snapshot=lambda *_a, **_k: self.fail('CAS receiver must never rewrite traits'),
            services=Obj(get_persistence_service=lambda: Obj(get_save_slot_proto_guid=lambda: 30)))
        self.snapshot_calls = []
        def snapshot(backend, sim):
            self.snapshot_calls.append(sim.id)
            return _native_snapshot(sim)
        self.enterContext(patch.object(sim_data, 'snapshot', side_effect=snapshot))
        self.path, self.key = form_bank.context(self.backend, self.sim)
        self.foreign = {'bank': {'1': {'note': 'another Sim is immutable'}}, 'history': [], 'unknown': [7, 8]}
        self.originals = {str(lane): appearance.packed(self.backend, owner) for lane, owner in self.forms.items()}
        self.initial = {'schema': 1, 'unknown_top_level': {'future': 'preserved'},
            'records': {self.key: {'bank': copy.deepcopy(self.originals), 'history': [],
                        'runtime_pid': 1234, 'unknown_record_field': {'future': [1, 2, 3]}},
                        '30:99': copy.deepcopy(self.foreign)}}
        form_bank.save(self.path, self.initial)

    def _assign(self, owner, fields):
        for name, value in appearance.payload(fields).items():
            if name == '__outfits__':
                owner.blob = value[1]
            else:
                setattr(owner, name, value)

    def ensure_form(self, tracker, kind, generate_new):
        self.ensure_calls.append((kind, generate_new))
        self.assertFalse(generate_new)
        return self.forms.get(kind)

    def restore(self, owner, fields):
        row = self.record()
        self.assertIn('cas_transaction', row)
        self.assertEqual(row['cas_transaction']['journal']['state'], 'applying')
        self.assertTrue(row['cas_transaction']['journal']['native_write_possible'])
        self.assertIsNone(row['cas_transaction']['journal']['native_write_attempted'])
        self.native_writes.append(owner.owner_lane)
        encoded = {name: appearance.encode(value) for name, value in fields.items()}
        self._assign(owner, encoded)

    def data(self):
        return form_bank.load(self.path)

    def record(self):
        return self.data()['records'][self.key]

    def edit(self, lane, name='physique', value=None):
        if value is None:
            value = 'accepted-' + str(lane)
        setattr(self.forms[lane], name, value)
        if self.sim.current == lane:
            setattr(self.sim, name, value)

    def enable_hair(self):
        data = self.data()
        # Intentionally stale prior policy: receiver must capture current native
        # originals, not let these rows substitute for them.
        data['records'][self.key]['hair_policy'] = {'enabled': True, 'future_setting': 'preserved',
            'forms': {'64': [{'category': 0, 'ordinal': 0, 'outfit_id': '7', 'hair': []}]}}
        form_bank.save(self.path, data)

    def begin(self, **kwargs):
        self.begin_receipt = receiver.begin(self.backend, self.sim, **kwargs)
        self.epoch = self.begin_receipt['expected_pending_sha256']
        return self.begin_receipt

    def observe(self):
        self.observation = receiver.observe(self.backend, self.sim, {'expected_pending_sha256': self.epoch})
        return self.observation

    def prepare(self, decisions, hair_targets=None):
        argument = {'expected_pending_sha256': self.epoch,
            'expected_raw_return_sha256': self.observation['raw_return_sha256'],
            'dispositions': [{'lane': str(lane), 'action': action} for lane, action in decisions]}
        if hair_targets is not None:
            argument['hair_targets'] = hair_targets
        self.plan_receipt = receiver.prepare(self.backend, self.sim, argument)
        self.commit_argument = {'expected_pending_sha256': self.epoch,
                               'expected_plan_sha256': self.plan_receipt['plan_sha256']}
        return self.plan_receipt

    def commit(self):
        return receiver.commit(self.backend, self.sim, self.commit_argument)

    def mutate_outfits(self, lane, mutate):
        message = self.parse(self.forms[lane].blob)
        mutate(message)
        self.edit(lane, 'blob', message.SerializeToString())

    def targets(self, lane, slots):
        held = self.record()['cas_transaction']['hair_checkpoint']['forms'][str(lane)]
        index = {(row['category'], row['ordinal']): row for row in held}
        return {str(lane): [{'category': category, 'ordinal': ordinal,
            'outfit_id': index[(category, ordinal)]['outfit_id']} for category, ordinal in slots]}

    def test_fairy_and_human_edits_commit_to_real_json_and_preserve_every_other_record(self):
        self.begin()
        self.edit(64)
        self.edit(1, 'facial_attributes', b'accepted human face\x00\xff')
        self.observe()
        self.prepare([(64, 'accept-returned'), (1, 'accept-returned')])
        result = self.commit()
        row = self.record()
        self.assertTrue(result['all_native_owners_verified'])
        self.assertIsNone(row['pending'])
        self.assertEqual(row['bank']['64']['physique']['value'], 'accepted-64')
        self.assertEqual(appearance.decode(row['bank']['1']['facial_attributes']), b'accepted human face\x00\xff')
        for lane in ('2', '4', '8', '16', '32'):
            self.assertEqual(row['bank'][lane], self.originals[lane])
        self.assertEqual(self.data()['records']['30:99'], self.foreign)
        self.assertEqual(self.data()['unknown_top_level'], self.initial['unknown_top_level'])
        self.assertEqual(row['unknown_record_field'], self.initial['records'][self.key]['unknown_record_field'])
        self.assertEqual(row['cas_transaction']['journal']['state'], 'completed')
        self.assertTrue(receiver.assert_idle(self.backend, self.sim))

    def test_raw_original_checkpoint_is_durable_before_optional_begin_serializer(self):
        def serializer():
            row = self.record()
            self.assertEqual(row['pending']['schema'], 2)
            self.assertEqual(row['pending']['original_owners']['stored'], self.originals)
            self.assertEqual(row['cas_transaction']['phase'], 'captured')
            self.assertEqual(self.native_writes, [])
            return _native_snapshot(self.sim)
        result = self.begin(snapshot_reader=serializer)
        self.assertTrue(result['full_native_original_appended'])
        self.assertIn('native_original_append', self.record()['cas_transaction'])
        self.assertEqual(self.record()['pending']['original_owners']['stored'], self.originals)

    def test_default_begin_performs_no_serializer_or_native_write(self):
        result = self.begin()
        self.assertFalse(result['full_native_original_appended'])
        self.assertEqual(self.snapshot_calls, [])
        self.assertEqual(self.native_writes, [])
        self.assertEqual(self.record()['bank'], self.originals)

    def test_observe_and_status_expose_bounded_hashes_and_field_names_without_payloads(self):
        self.begin()
        captured = receiver.status(self.backend, self.sim)
        self.assertFalse(captured['lane_change_evidence_available'])
        self.assertIsNone(captured['changed_lanes'])
        self.edit(64)
        self.edit(1, 'facial_attributes', b'private accepted face\x00\xff')
        self.mutate_outfits(1, lambda message: message.outfits[0].parts.ids.append(987654321))
        self.observe()
        observed = self.observation
        public = receiver.status(self.backend, self.sim)
        self.assertTrue(observed['lane_change_evidence_available'])
        self.assertEqual(observed['changed_lanes'], ['1', '64'])
        self.assertEqual(public['lane_change_evidence'], observed['lane_change_evidence'])
        rows = {row['lane']: row for row in public['lane_change_evidence']}
        self.assertEqual(rows['64']['changed_fields'], ['physique'])
        self.assertEqual(rows['1']['changed_fields'], ['__outfits__', 'facial_attributes'])
        self.assertEqual(rows['1']['changed_field_labels'], ['outfits', 'facial attributes'])
        self.assertFalse(rows['2']['changed'])
        self.assertEqual(rows['1']['before_fingerprint'], appearance.fingerprint(self.originals['1']))
        self.assertEqual(rows['1']['returned_fingerprint'], appearance.fingerprint(
            self.record()['cas_transaction']['journal']['raw_return']['stored']['1']))
        self.assertFalse(public['evidence_establishes_edit_intent'])
        encoded = json.dumps(public)
        self.assertLess(len(encoded.encode('utf-8')), 32 * 1024)
        for private in ('private accepted face', 'accepted-64', 'native_base64', 'typed_payload', '987654321'):
            self.assertNotIn(private, encoded)
        self.assertEqual(self.native_writes, [])

    def test_changed_owner_evidence_refuses_a_mutated_raw_receipt(self):
        self.begin()
        self.observe()
        self.assertTrue(self.observation['lane_change_evidence_available'])
        self.assertEqual(self.observation['changed_lanes'], [])
        current = self.data()
        current['records'][self.key]['cas_transaction']['journal']['raw_return']['stored']['1']['physique']['value'] = 'foreign raw'
        form_bank.save(self.path, current)
        public = receiver.status(self.backend, self.sim)
        self.assertFalse(public['lane_change_evidence_available'])
        self.assertIsNone(public['changed_lanes'])
        self.assertEqual(public['lane_change_evidence'], [])
        self.assertTrue(public['blocked'])

    def test_returned_raw_is_durable_before_observe_serializer(self):
        self.begin()
        self.edit(64)
        def serializer(backend, sim):
            journal = self.record()['cas_transaction']['journal']
            self.assertEqual(journal['state'], 'raw-observed')
            self.assertEqual(journal['raw_return']['stored']['64']['physique']['value'], 'accepted-64')
            return _native_snapshot(sim)
        with patch.object(sim_data, 'snapshot', side_effect=serializer):
            self.observe()
        self.assertIn('native_serialized_append', self.record()['cas_transaction']['journal'])

    def test_legacy_and_unknown_pending_are_never_relabelled_or_written(self):
        for pending in ({'state': 'captured', 'originals': self.originals}, {'schema': 99}, 'unknown'):
            data = self.data()
            data['records'][self.key]['pending'] = pending
            form_bank.save(self.path, data)
            before = self.path.read_bytes()
            with self.subTest(pending=pending), self.assertRaises(ValueError):
                self.begin()
            self.assertEqual(self.path.read_bytes(), before)
            self.assertTrue(receiver.status(self.backend, self.sim)['legacy_pending_not_converted'])
        self.assertEqual(self.native_writes, [])

    def test_unresolved_separate_journal_blocks_mutations_without_pending(self):
        data = self.data()
        data['records'][self.key]['pending'] = None
        data['records'][self.key]['cas_transaction'] = {'schema': 1, 'journal': {'state': 'verified'}}
        form_bank.save(self.path, data)
        self.assertTrue(receiver.status(self.backend, self.sim)['blocked'])
        with self.assertRaisesRegex(ValueError, 'checkpoint/journal is unresolved'):
            receiver.assert_idle(self.backend, self.sim)
        with self.assertRaises(ValueError):
            self.begin()

    def test_hash_only_bridge_rejects_external_fields_and_unknown_actions(self):
        self.begin()
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'external fields'):
            receiver.observe(self.backend, self.sim, {'expected_pending_sha256': self.epoch, 'fields': self.originals})
        self.assertEqual(self.path.read_bytes(), before)
        self.edit(64)
        self.observe()
        with self.assertRaises(ValueError):
            self.prepare([(64, 'accept-returned'), (1, 'whatever')])
        self.assertEqual(self.native_writes, [])

    def test_duplicate_commit_acknowledges_history_without_replaying_native_writes(self):
        self.begin()
        self.edit(64)
        self.observe()
        self.prepare([(64, 'accept-returned')])
        self.commit()
        native_count = len(self.native_writes)
        bytes_before = self.path.read_bytes()
        replay = self.commit()
        self.assertTrue(replay['already_completed'])
        self.assertTrue(replay['receipt_historical'])
        self.assertFalse(replay['replayed'])
        self.assertEqual(len(self.native_writes), native_count)
        self.assertEqual(self.path.read_bytes(), bytes_before)

    def test_new_identical_checkpoint_has_new_epoch_and_rejects_old_request(self):
        self.begin()
        self.observe()
        self.prepare([])
        self.commit()
        old_argument = copy.deepcopy(self.commit_argument)
        old_checkpoint = self.record()['cas_transaction']['checkpoint_sha256']
        old_epoch = self.epoch
        self.begin()
        self.assertEqual(old_checkpoint, self.record()['cas_transaction']['checkpoint_sha256'])
        self.assertNotEqual(self.epoch, old_epoch)
        with self.assertRaisesRegex(ValueError, 'stale/different transaction epoch'):
            receiver.commit(self.backend, self.sim, old_argument)
        self.assertEqual(len(self.record()['cas_transaction_history']), 1)

    def test_old_bank_cannot_generate_or_supply_missing_native_lane(self):
        del self.forms[16]
        old = copy.deepcopy(self.originals['16'])
        self.begin()
        self.observe()
        self.prepare([])
        self.commit()
        self.assertNotIn('16', self.record()['bank'])
        self.assertEqual(self.record()['cas_transaction']['prior_bank']['16'], old)
        self.assertNotIn(16, [kind for kind, generate in self.ensure_calls])
        self.assertTrue(all(generate is False for kind, generate in self.ensure_calls))

    def test_changed_stored_and_active_lanes_can_return_as_human(self):
        self.begin()
        for name, value in vars(self.forms[1]).items():
            if name not in ('id', 'owner_lane'):
                setattr(self.sim, name, copy.deepcopy(value))
        self.sim.current = 1
        self.edit(64)
        self.edit(1)
        self.observe()
        self.prepare([(1, 'accept-returned'), (64, 'accept-returned')])
        self.commit()
        self.assertEqual(self.record()['active_lane'], '1')
        self.assertEqual(self.sim.physique, 'accepted-1')
        self.assertEqual(self.forms[64].physique, 'accepted-64')

    def test_hair_policy_uses_fresh_wardrobes_and_keeps_only_explicit_outfit_edits(self):
        self.enable_hair()
        self.begin()
        held = copy.deepcopy(self.record()['cas_transaction']['hair_checkpoint']['forms'])
        def propagate(message):
            for index, item in enumerate(message.outfits):
                item.parts.ids[0] = (1 << 64) - 300 - index
                item.parts.ids[1] = 70000 + index
                item.part_shifts.color_shift[0] = (1 << 64) - 400 - index
                item.part_shifts.color_shift[1] = (1 << 63) + index
                item.parts.ids[2] = 95000 + index  # Legitimate clothing edits.
                item.title = 'Accepted clothing/title ' + str(index)
        self.mutate_outfits(64, propagate)
        self.edit(64, 'skin_tone', 111111)
        returned = appearance.packed(self.backend, self.forms[64])
        self.observe()
        targets = self.targets(64, [(0, 0), (0, 1), (1, 0)])
        result = self.prepare([(64, 'accept-returned')], targets)
        self.assertTrue(result['hair_isolation_planned'])
        self.assertFalse(result['native_cas_propagation_verified'])
        self.commit()
        chosen = self.record()['bank']['64']
        final_hair = outfit_hair.capture(self.backend, chosen)
        returned_hair = outfit_hair.capture(self.backend, returned)
        keep = {(0, 0), (0, 1), (1, 0)}
        for old, edit, accepted in zip(held['64'], returned_hair, final_hair):
            key = (old['category'], old['ordinal'])
            self.assertEqual(accepted['hair'], edit['hair'] if key in keep else old['hair'])
            self.assertEqual(accepted['outfit_id'], old['outfit_id'])
        self.assertEqual(chosen['skin_tone'], returned['skin_tone'])
        self.assertEqual(chosen['genetic_data'], returned['genetic_data'])
        self.assertEqual(self.record()['hair_policy']['future_setting'], 'preserved')
        self.assertEqual(self.record()['hair_policy']['forms']['64'], final_hair)
        returned_message = self.parse(appearance.decode(returned['__outfits__'])[1])
        accepted_message = self.parse(appearance.decode(chosen['__outfits__'])[1])
        for left, right in zip(returned_message.outfits, accepted_message.outfits):
            self.assertEqual(read_rows(left)[2], read_rows(right)[2])
            for item in (left, right):
                del item.parts.ids[:]; del item.body_types_list.body_types[:]
                del item.part_shifts.color_shift[:]; del item.object_ids.object_id[:]; del item.layer_ids.layer_id[:]
            self.assertEqual(left.SerializeToString(), right.SerializeToString())
        del returned_message.outfits[:]; del accepted_message.outfits[:]
        self.assertEqual(returned_message.SerializeToString(), accepted_message.SerializeToString())

    def test_hair_changes_without_explicit_targets_are_refused_not_silently_blessed(self):
        self.enable_hair()
        self.begin()
        def edit(message):
            message.outfits[0].parts.ids[0] = 333333
        self.mutate_outfits(64, edit)
        self.observe()
        with self.assertRaisesRegex(ValueError, 'Changed hair requires explicit'):
            self.prepare([(64, 'accept-returned')])
        self.assertEqual(self.record()['cas_transaction']['journal']['state'], 'observed')
        self.assertEqual(self.native_writes, [])
        self.assertIsNotNone(self.record()['pending'])

    def test_face_only_edits_with_hair_enabled_need_no_invented_hair_target(self):
        self.enable_hair()
        self.begin()
        self.edit(64, 'facial_attributes', b'face edit without hair propagation')
        self.observe()
        self.prepare([(64, 'accept-returned')])
        self.commit()
        self.assertEqual(appearance.decode(self.record()['bank']['64']['facial_attributes']), b'face edit without hair propagation')

    def test_multiple_occult_hair_intents_are_reconciled_independently(self):
        self.enable_hair()
        self.begin()
        def edit(message):
            for item in message.outfits:
                item.parts.ids[0] = 333333
        self.mutate_outfits(64, edit)
        self.mutate_outfits(1, edit)
        held = self.record()['cas_transaction']['hair_checkpoint']['forms']
        self.observe()
        targets = self.targets(64, [(0, 1)])
        targets.update(self.targets(1, [(7, 0)]))
        self.prepare([(64, 'accept-returned'), (1, 'accept-returned')], targets)
        self.commit()
        for lane, selected in [('64', (0, 1)), ('1', (7, 0))]:
            accepted = outfit_hair.capture(self.backend, self.record()['bank'][lane])
            for original, actual in zip(held[lane], accepted):
                slot = (actual['category'], actual['ordinal'])
                if slot == selected:
                    self.assertEqual(actual['hair'][0]['row']['id'], 333333)
                else:
                    self.assertEqual(actual['hair'], original['hair'])

    def test_hair_wardrobe_replacement_reorder_or_addition_refuses_before_any_setter(self):
        for change in ('replacement', 'reorder', 'addition'):
            with self.subTest(change=change):
                receiver._ACTIVE.clear()
                reset = self.data()
                reset.clear()
                reset.update(copy.deepcopy(self.initial))
                form_bank.save(self.path, reset)
                self._assign(self.forms[64], self.originals['64'])
                self._assign(self.sim, self.originals['64'])
                self.enable_hair()
                self.begin()
                def change_message(message):
                    if change == 'replacement':
                        message.outfits[0].outfit_id = 7
                    elif change == 'reorder':
                        first, second = copy.deepcopy(message.outfits[0]), copy.deepcopy(message.outfits[1])
                        message.outfits[0].CopyFrom(second); message.outfits[1].CopyFrom(first)
                    else:
                        message.outfits.add(outfit_id=7, category=0)
                self.mutate_outfits(64, change_message)
                self.observe()
                with self.assertRaises(ValueError):
                    self.prepare([(64, 'accept-returned')])
                self.assertEqual(self.native_writes, [])

    def test_partial_native_failure_keeps_originals_return_and_plan_no_bank_commit(self):
        self.begin()
        self.edit(1)
        self.edit(64)
        self.observe()
        self.prepare([(1, 'restore-original'), (64, 'accept-returned')])
        native_restore = self.backend._restore_siminfo_payload
        def failing_restore(owner, fields):
            if owner.owner_lane == '1':
                raise ValueError('constructed native partial failure')
            native_restore(owner, fields)
        self.backend._restore_siminfo_payload = failing_restore
        with self.assertRaises(primitive.RecoveryRequired):
            self.commit()
        row = self.record()
        self.assertEqual(row['bank'], self.originals)
        self.assertIsNotNone(row['pending'])
        self.assertEqual(row['cas_transaction']['journal']['state'], 'recovery-required')
        self.assertIn('raw_return', row['cas_transaction']['journal'])
        self.assertIn('plan', row['cas_transaction']['journal'])
        self.assertTrue(receiver.status(self.backend, self.sim)['blocked'])

    def test_completion_journal_failure_after_pending_consumed_remains_blocked(self):
        self.begin()
        self.edit(64)
        self.observe()
        self.prepare([(64, 'accept-returned')])
        native_save = receiver.atomic_save
        def refuse_completion(path, data, **kwargs):
            journal = data['records'][self.key]['cas_transaction'].get('journal')
            if journal and journal.get('state') == 'completed':
                raise OSError('constructed completion journal failure')
            return native_save(path, data, **kwargs)
        with patch.object(receiver, 'atomic_save', side_effect=refuse_completion), self.assertRaises(primitive.RecoveryRequired):
            self.commit()
        row = self.record()
        self.assertIsNone(row['pending'])
        self.assertTrue(row['cas_transaction']['metadata_commit']['committed'])
        self.assertEqual(row['cas_transaction']['journal']['state'], 'recovery-required')
        self.assertTrue(receiver.status(self.backend, self.sim)['blocked'])
        with self.assertRaises(ValueError):
            receiver.assert_idle(self.backend, self.sim)
        writes = len(self.native_writes)
        with self.assertRaises(ValueError):
            self.commit()
        self.assertEqual(len(self.native_writes), writes)

    def test_atomic_metadata_persists_then_loses_ack_reports_unresolved_and_never_replays(self):
        self.begin()
        self.edit(64)
        self.observe()
        self.prepare([(64, 'accept-returned')])
        native_save = receiver.atomic_save
        lost = [False]
        def lose_metadata_ack(path, data, **kwargs):
            row = data['records'][self.key]
            result = native_save(path, data, **kwargs)
            if row.get('pending') is None and row['cas_transaction'].get('metadata_commit') and not lost[0]:
                lost[0] = True
                raise OSError('constructed lost atomic metadata ACK')
            return result
        with patch.object(receiver, 'atomic_save', side_effect=lose_metadata_ack), self.assertRaises(primitive.RecoveryRequired):
            self.commit()
        status = receiver.status(self.backend, self.sim)
        self.assertTrue(status['metadata_commit_persisted'])
        self.assertEqual(status['bank_commit_outcome'], 'unresolved')
        self.assertTrue(status['blocked'])
        self.assertIsNone(self.record()['pending'])
        with self.assertRaises(ValueError):
            self.commit()

    def test_source_receiver_cache_loss_cannot_rehydrate_observed_journal(self):
        self.begin()
        self.observe()
        receiver._ACTIVE.clear()
        with self.assertRaisesRegex(ValueError, 'rehydration/replay is blocked'):
            self.prepare([])
        self.assertEqual(self.native_writes, [])

    def test_selected_policy_or_bank_changed_during_pending_refuses_exact_receiver(self):
        self.begin()
        self.edit(64)
        self.observe()
        self.prepare([(64, 'accept-returned')])
        data = self.data()
        data['records'][self.key]['bank']['1']['physique']['value'] = 'foreign modification'
        form_bank.save(self.path, data)
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'metadata changed during CAS'):
            self.commit()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.native_writes, [])

    def test_missing_returned_owner_retains_raw_before_refusal(self):
        self.begin()
        del self.forms[4]
        with self.assertRaises(primitive.RecoveryRequired):
            self.observe()
        journal = self.record()['cas_transaction']['journal']
        self.assertIn('raw_return', journal)
        self.assertNotIn('4', journal['raw_return']['stored'])
        self.assertIn('4', journal['original_owners']['stored'])
        self.assertEqual(self.snapshot_calls, [])
        self.assertEqual(self.native_writes, [])

    def test_failed_original_serializer_retains_raw_checkpoint_and_persistent_gate(self):
        def failed():
            self.assertEqual(self.record()['pending']['original_owners']['stored'], self.originals)
            raise ValueError('constructed original serializer failure')
        with self.assertRaises(primitive.RecoveryRequired):
            self.begin(snapshot_reader=failed)
        row = self.record()
        self.assertIsNotNone(row['pending'])
        self.assertEqual(row['cas_transaction']['journal']['state'], 'recovery-required')
        self.assertEqual(row['cas_transaction']['journal']['original_owners']['stored'], self.originals)
        self.assertTrue(receiver.status(self.backend, self.sim)['blocked'])
        self.assertEqual(self.native_writes, [])

    def test_failed_returned_serializer_retains_all_raw_edits_and_native_originals(self):
        self.begin()
        self.edit(64)
        with patch.object(sim_data, 'snapshot', side_effect=ValueError('constructed returned serializer failure')):
            with self.assertRaises(primitive.RecoveryRequired):
                self.observe()
        journal = self.record()['cas_transaction']['journal']
        self.assertEqual(journal['state'], 'recovery-required')
        self.assertEqual(journal['raw_return']['stored']['64']['physique']['value'], 'accepted-64')
        self.assertEqual(journal['original_owners']['stored'], self.originals)
        self.assertEqual(self.record()['bank'], self.originals)
        self.assertEqual(self.native_writes, [])

    def test_returned_serializer_mutation_is_repaired_from_raw_choices_after_journaling(self):
        self.begin()
        self.edit(64)
        raw_before = self.forms[64].blob
        def serializer(backend, sim):
            def shared(message):
                message.outfits[0].parts.ids[2] = 123456
            self.mutate_outfits(64, shared)
            return _native_snapshot(sim)
        with patch.object(sim_data, 'snapshot', side_effect=serializer):
            self.observe()
        self.prepare([(64, 'accept-returned')])
        self.commit()
        self.assertEqual(self.forms[64].blob, raw_before)
        self.assertEqual(self.sim.blob, raw_before)
        self.assertEqual(self.record()['bank']['64']['physique']['value'], 'accepted-64')

    def test_wrong_thread_wrong_sim_and_protected_path_are_refused_without_writes(self):
        self.backend._APEX_GAME_THREAD_IDENT += 1
        with self.assertRaisesRegex(ValueError, 'actual game thread'):
            self.begin()
        self.backend._APEX_GAME_THREAD_IDENT = threading.current_thread().ident
        self.backend._get_sim_info_by_id = lambda _: copy.deepcopy(self.sim)
        with self.assertRaisesRegex(ValueError, 'manager-owned'):
            self.begin()
        self.backend._get_sim_info_by_id = lambda _: self.sim
        forbidden = Path(self.temp.name) / 'The Sims 4 DO NOT FUCKING TOUCH!!!'
        self.backend._data_directory = lambda: str(forbidden)
        with self.assertRaisesRegex(ValueError, 'protected original'):
            self.begin()
        self.assertFalse(forbidden.exists())
        self.assertEqual(self.native_writes, [])

    def test_duplicate_form_bank_json_keys_are_refused_read_only(self):
        self.path.write_text('{"schema":1,"records":{},"records":{}}', encoding='utf-8')
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Duplicate form-bank JSON key'):
            self.begin()
        self.assertEqual(self.path.read_bytes(), before)

    def test_normal_cas_return_can_recreate_stored_wrappers_before_observation(self):
        self.begin()
        self.assertEqual(receiver._ACTIVE, {})
        self.forms = {lane: copy.deepcopy(owner) for lane, owner in self.forms.items()}
        self.sim.occult_tracker = Obj()
        self.edit(1)
        self.edit(64)
        self.observe()
        self.prepare([(1, 'accept-returned'), (64, 'accept-returned')])
        self.commit()
        self.assertEqual(self.forms[1].physique, 'accepted-1')
        self.assertEqual(self.forms[64].physique, 'accepted-64')
        self.assertEqual(self.sim.physique, 'accepted-64')

    def test_owner_replacement_after_observation_refuses_before_native_writes(self):
        self.begin()
        self.edit(64)
        self.observe()
        self.prepare([(64, 'accept-returned')])
        self.forms[4] = copy.deepcopy(self.forms[4])
        with self.assertRaisesRegex(ValueError, 'owner was replaced'):
            self.commit()
        self.assertEqual(self.native_writes, [])

    def test_initial_native_cas_return_recreates_primary_and_all_wrappers_without_losing_seven_owner_originals(self):
        self.sim.current = 1
        self._assign(self.sim, self.originals['1'])
        original_sim = self.sim
        self.begin()
        pending_before = copy.deepcopy(self.record()['pending'])
        self.sim = copy.deepcopy(self.sim)
        self.sim.occult_tracker = Obj()
        self.forms = {lane: copy.deepcopy(owner) for lane, owner in self.forms.items()}
        self.edit(1, value='Explicit returned Human appearance')
        self.edit(2, value='Native unwanted Alien appearance change')
        raw_returned = {str(lane): appearance.packed(self.backend, owner) for lane, owner in self.forms.items()}
        def serialize_after_raw(backend, sim):
            self.assertIs(sim, self.sim)
            row = self.record()
            self.assertEqual(row['pending'], pending_before)
            journal = row['cas_transaction']['journal']
            self.assertEqual(journal['state'], 'raw-observed')
            self.assertEqual(journal['raw_return']['stored'], raw_returned)
            self.assertEqual(journal['original_owners']['stored'], self.originals)
            self.assertEqual(len(journal['raw_return']['stored']), 7)
            self.assertEqual(self.native_writes, [])
            return _native_snapshot(sim)
        with patch.object(sim_data, 'snapshot', side_effect=serialize_after_raw):
            observed = self.observe()
        self.assertTrue(observed['primary_sim_recreated'])
        binding = self.record()['cas_transaction']['primary_receiver_binding']
        self.assertTrue(binding['begin_capability_retained'])
        self.assertTrue(binding['manager_owned_verified'])
        self.assertFalse(binding['native_appearance_written'])
        held = next(iter(receiver._CAPTURED.values()))
        self.assertIs(held['begin_sim'], original_sim)
        self.assertIs(held['sim'], self.sim)
        self.assertTrue(held['receiver_bound'])
        self.prepare([(1, 'accept-returned'), (2, 'restore-original')])
        result = self.commit()
        self.assertTrue(result['all_native_owners_verified'])
        self.assertFalse(result['save_reload_verified'])
        self.assertEqual(self.sim.physique, 'Explicit returned Human appearance')
        self.assertEqual(self.record()['bank']['1'], raw_returned['1'])
        for lane in ('2', '4', '8', '16', '32', '64'):
            self.assertEqual(appearance.packed(self.backend, self.forms[int(lane)]), self.originals[lane])
            self.assertEqual(self.record()['bank'][lane], self.originals[lane])
        self.assertEqual(self.data()['records']['30:99'], self.foreign)
        self.assertEqual(self.data()['unknown_top_level'], self.initial['unknown_top_level'])
        self.assertIsNone(self.record()['pending'])

    def test_primary_replacement_after_observation_cannot_transfer_receiver_or_reobserve(self):
        self.begin()
        self.edit(64)
        self.observe()
        self.prepare([(64, 'accept-returned')])
        self.sim = copy.deepcopy(self.sim)
        before, serializers = self.path.read_bytes(), list(self.snapshot_calls)
        for operation in (self.observe, lambda: self.prepare([(64, 'accept-returned')]), self.commit):
            with self.assertRaisesRegex(ValueError, 'receiver object differs'):
                operation()
            self.assertEqual(self.path.read_bytes(), before)
            self.assertEqual(self.snapshot_calls, serializers)
        self.assertEqual(self.native_writes, [])

    def test_prepare_and_commit_cannot_establish_initial_primary_transfer(self):
        self.begin()
        self.sim = copy.deepcopy(self.sim)
        before = self.path.read_bytes()
        requests = ((receiver.prepare, {'expected_pending_sha256': self.epoch,
                    'expected_raw_return_sha256': 'a' * 64, 'dispositions': []}),
                    (receiver.commit, {'expected_pending_sha256': self.epoch,
                    'expected_plan_sha256': 'a' * 64}))
        for operation, argument in requests:
            with self.assertRaisesRegex(ValueError, 'outside its initial observation'):
                operation(self.backend, self.sim, argument)
            self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(receiver._ACTIVE, {})
        self.assertEqual(self.snapshot_calls, [])
        self.assertEqual(self.native_writes, [])

    def test_recreated_primary_wrong_identity_backend_or_resolver_never_transfers_capability(self):
        self.begin()
        original_sim, original_backend = self.sim, self.backend
        before = self.path.read_bytes()
        for change in ('sim-id', 'household', 'save-guid', 'backend', 'wrong-resolver'):
            self.sim, self.backend = copy.deepcopy(original_sim), original_backend
            self.backend.services = Obj(get_persistence_service=lambda: Obj(get_save_slot_proto_guid=lambda: 30))
            self.backend._get_sim_info_by_id = lambda _: self.sim
            if change == 'sim-id': self.sim.id = 11
            elif change == 'household': self.sim.household_id = 21
            elif change == 'save-guid':
                self.backend.services = Obj(get_persistence_service=lambda: Obj(get_save_slot_proto_guid=lambda: 31))
            elif change == 'backend': self.backend = copy.copy(self.backend)
            else: self.backend._get_sim_info_by_id = lambda _: original_sim
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.observe()
            self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(receiver._ACTIVE, {})
        self.assertEqual(self.snapshot_calls, [])
        self.assertEqual(self.native_writes, [])

    def test_prior_pid_and_unknown_transaction_phase_cannot_bind_a_recreated_primary(self):
        self.begin()
        self.sim = copy.deepcopy(self.sim)
        before = self.path.read_bytes()
        with patch.object(receiver.os, 'getpid', return_value=os.getpid() + 1234):
            with self.assertRaises(ValueError): self.observe()
        self.assertEqual(self.path.read_bytes(), before)
        current = self.data()
        current['records'][self.key]['cas_transaction']['phase'] = 'unknown'
        form_bank.save(self.path, current)
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'outside its initial observation'):
            self.observe()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(receiver._ACTIVE, {})
        self.assertEqual(self.snapshot_calls, [])
        self.assertEqual(self.native_writes, [])

    def test_original_capability_cache_loss_and_prior_bound_receiver_cannot_rebind_primary(self):
        for lost in ('captured', 'active'):
            with self.subTest(lost=lost):
                receiver._ACTIVE.clear(); receiver._CAPTURED.clear()
                self.path.unlink()
                form_bank.save(self.path, self.initial)
                self.begin()
                if lost == 'captured': receiver._CAPTURED.clear()
                else:
                    receiver._instance(self.backend, self.sim)
                    receiver._ACTIVE.clear()
                self.sim = copy.deepcopy(self.sim)
                before = self.path.read_bytes()
                with self.assertRaises(ValueError): self.observe()
                self.assertEqual(self.path.read_bytes(), before)
                self.assertEqual(self.snapshot_calls, [])
                self.assertEqual(self.native_writes, [])

    def test_primary_transfer_is_once_even_if_receiver_construction_fails_before_raw_observation(self):
        self.begin()
        original_sim = self.sim
        self.sim = copy.deepcopy(self.sim)
        with patch.object(receiver, '_HairTransaction', side_effect=ValueError('constructed pre-observation failure')):
            with self.assertRaisesRegex(ValueError, 'pre-observation failure'):
                self.observe()
        held = next(iter(receiver._CAPTURED.values()))
        self.assertIs(held['begin_sim'], original_sim)
        self.assertTrue(held['primary_sim_recreated'])
        self.assertFalse(held['receiver_bound'])
        self.assertIsNone(self.record()['cas_transaction']['journal'])
        self.sim = copy.deepcopy(self.sim)
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'outside its initial observation'):
            self.observe()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.snapshot_calls, [])
        self.assertEqual(self.native_writes, [])

    def test_injected_competing_source_writer_cannot_enter_the_final_save_window(self):
        original_atomic_save = receiver.atomic_save
        inject_once = [True]
        before = self.path.read_bytes()
        def inject_competing_writer(path, data, **kwargs):
            if inject_once[0]:
                inject_once[0] = False
                concurrent = form_bank.load(path)
                concurrent['records']['30:100'] = {'bank': {}, 'history': [], 'note': 'new other Sim'}
                # Models the REQUIRED next-epoch form_bank.save delegation.
                # The old frozen implementation does not honor this protocol.
                form_bank.save(path, concurrent)
            return original_atomic_save(path, data, **kwargs)
        with patch.object(form_bank, 'save', side_effect=original_atomic_save):
            with patch.object(receiver, 'atomic_save', side_effect=inject_competing_writer):
                with self.assertRaisesRegex(ValueError, 'writer lease is already held'):
                    self.begin()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertNotIn('30:100', self.data()['records'])
        self.assertEqual(self.native_writes, [])
        self.assertFalse(receiver._lease_path(self.path).exists())

    def test_unknown_interrupted_writer_lease_is_never_stolen_or_deleted(self):
        held = receiver._lease_path(self.path)
        raw = b'{"schema":1,"pid":1234,"token":"unknown-external-lock"}'
        held.write_bytes(raw)
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.begin()
        self.assertEqual(held.read_bytes(), raw)
        self.assertEqual(self.path.read_bytes(), before)
        status = receiver.status(self.backend, self.sim)
        self.assertTrue(status['blocked'])
        self.assertTrue(status['writer_lease_present'])
        self.assertFalse(status['uncooperating_external_writer_atomic_cas_supported'])

    def test_atomic_file_compare_hash_is_checked_under_the_owned_lease(self):
        before = self.path.read_bytes()
        changed = copy.deepcopy(self.initial)
        changed['records']['30:99']['note'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'file hash differs'):
            receiver.atomic_save(self.path, changed, expected_file_sha256='0' * 64)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(receiver._lease_path(self.path).exists())

    def test_caller_cannot_supply_a_forged_writer_lease_capability(self):
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'receiver-owned bank writer lease'):
            receiver.atomic_save(self.path, self.initial,
                _lease={'path': str(self.path), 'thread': threading.current_thread().ident})
        self.assertEqual(self.path.read_bytes(), before)

    def test_typed_dispatch_runs_hash_only_observation_and_exposes_no_callback_input(self):
        initial = receiver.dispatch(self.backend, self.sim, 'cas_bank_begin')
        argument = json.dumps({'expected_pending_sha256': initial['expected_pending_sha256']})
        observed = receiver.dispatch(self.backend, self.sim, 'cas_bank_observe', argument)
        self.assertTrue(observed['ok'])
        with self.assertRaisesRegex(ValueError, 'no external payload'):
            receiver.dispatch(self.backend, self.sim, 'cas_bank_begin', '{"snapshot_reader":"anything"}')
        self.assertEqual(self.native_writes, [])

    def test_typed_dispatch_rejects_duplicate_nonfinite_and_unsupported_input_read_only(self):
        self.begin()
        before = self.path.read_bytes()
        for value in ('{"expected_pending_sha256":"' + self.epoch + '","expected_pending_sha256":"' + self.epoch + '"}',
                      '{"expected_pending_sha256":NaN}', '[]'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                receiver.dispatch(self.backend, self.sim, 'cas_bank_observe', value)
        with self.assertRaisesRegex(ValueError, 'Unknown typed CAS bank action'):
            receiver.dispatch(self.backend, self.sim, 'cas_bank_execute', '{}')
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.native_writes, [])

    def test_stale_cooperating_writer_cannot_erase_the_new_cas_checkpoint(self):
        stale = receiver.load_for_write(self.path)
        old_hash = stale._bank_file_sha256
        self.begin()
        before = self.path.read_bytes()
        stale['records']['30:100'] = {'bank': {}, 'history': [], 'note': 'stale other-Sim update'}
        with self.assertRaisesRegex(ValueError, 'file hash differs'):
            receiver.save_from_read(self.path, stale)
        self.assertEqual(stale._bank_file_sha256, old_hash)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertIsNotNone(self.record()['pending'])
        self.assertEqual(self.native_writes, [])

    def test_unspecified_or_plain_unpinned_existing_bank_write_is_forbidden(self):
        stale = dict(self.data())
        self.begin()
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'read-bound file SHA'):
            receiver.atomic_save(self.path, stale)
        with self.assertRaisesRegex(ValueError, 'Plain unpinned data'):
            receiver.save_from_read(self.path, stale)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertIsNotNone(self.record()['pending'])

    def test_read_revision_attributes_survive_deepcopy_but_never_enter_json(self):
        document = receiver.load_for_write(self.path)
        clone = copy.deepcopy(document)
        self.assertIsInstance(clone, receiver.AtomicBankDocument)
        self.assertEqual(clone._bank_file_sha256, document._bank_file_sha256)
        self.assertEqual(clone._bank_path, document._bank_path)
        self.assertEqual(json.loads(json.dumps(clone)), self.data())
        clone['records']['30:99']['first_change'] = True
        first = receiver.save_from_read(self.path, clone)
        self.assertEqual(clone._bank_file_sha256, first['file_sha256'])
        clone['records']['30:99']['second_change'] = True
        second = receiver.save_from_read(self.path, clone)
        self.assertEqual(clone._bank_file_sha256, second['file_sha256'])
        self.assertTrue(self.data()['records']['30:99']['first_change'])
        self.assertTrue(self.data()['records']['30:99']['second_change'])

    def test_new_plain_bank_requires_expected_absence_and_cannot_borrow_another_path(self):
        other = Path(self.temp.name) / 'another-bank.json'
        fresh = {'schema': 1, 'records': {}}
        receiver.save_from_read(other, fresh)
        self.assertEqual(form_bank.load(other), fresh)
        document = receiver.load_for_write(self.path)
        with self.assertRaisesRegex(ValueError, 'another read path'):
            receiver.save_from_read(other, document)
        with self.assertRaisesRegex(ValueError, 'file hash differs'):
            receiver.atomic_save(other, fresh, expected_file_sha256=None)

    def test_envelope_less_malformed_completed_receipt_cannot_open_the_mutation_gate(self):
        data = self.data()
        fake_plan = {}
        fake_hash = primitive.digest(fake_plan)
        data['records'][self.key]['pending'] = None
        data['records'][self.key]['cas_transaction'] = {
            'journal': {'state': 'completed', 'bank_committed': True, 'save_reload_verified': False,
                        'plan': fake_plan, 'plan_sha256': fake_hash,
                        'final_native_appearance': {'verified': True}},
            'metadata_commit': {'committed': True, 'plan_sha256': fake_hash}}
        form_bank.save(self.path, data)
        self.assertTrue(receiver.status(self.backend, self.sim)['blocked'])
        with self.assertRaises(ValueError):
            receiver.assert_idle(self.backend, self.sim)
        with self.assertRaises(ValueError):
            self.begin()

    def test_truncated_ack_and_mutated_complete_receipt_are_not_historical_authority(self):
        self.begin()
        self.observe()
        self.prepare([])
        self.commit()
        completed = self.data()
        variants = []
        truncated = copy.deepcopy(completed)
        del truncated['records'][self.key]['cas_transaction']['metadata_commit']['native_verified_receipt_sha256']
        variants.append(truncated)
        wrong_owner = copy.deepcopy(completed)
        wrong_owner['records'][self.key]['cas_transaction']['owner_key'] = '30:99'
        variants.append(wrong_owner)
        changed_original = copy.deepcopy(completed)
        changed_original['records'][self.key]['cas_transaction']['journal']['original_owners']['stored']['1']['physique']['value'] = 'foreign original'
        variants.append(changed_original)
        for value in variants:
            current = self.data()
            current.clear()
            current.update(value)
            form_bank.save(self.path, current)
            with self.subTest(value=value['records'][self.key]['cas_transaction']['metadata_commit']):
                self.assertTrue(receiver.status(self.backend, self.sim)['blocked'])
                with self.assertRaises(ValueError):
                    receiver.assert_idle(self.backend, self.sim)

    def test_valid_historical_completion_stays_idle_after_a_legitimate_later_bank_edit(self):
        self.begin()
        self.observe()
        self.prepare([])
        self.commit()
        data = self.data()
        data['records'][self.key]['bank']['64']['physique']['value'] = 'later accepted Live edit'
        form_bank.save(self.path, data)
        self.assertTrue(receiver.assert_idle(self.backend, self.sim))
        self.assertFalse(receiver.status(self.backend, self.sim)['blocked'])
        # A fresh raw begin uses CURRENT native owners and archives history;
        # the changed bank never supplies those new originals.
        self.begin()
        self.assertEqual(self.record()['pending']['original_owners']['stored'], self.originals)


if __name__ == '__main__':
    unittest.main()
