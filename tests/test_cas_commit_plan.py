"""Constructed owners and independent protobuf bytes; no game imports/run."""
import base64
import copy
import hashlib
from enum import IntEnum
import os
from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import cas_commit_plan as plan, form_appearance as appearance


def _varint(value):
    result = bytearray()
    while value > 127:
        result.append(128 | value & 127)
        value >>= 7
    result.append(value)
    return bytes(result)


def _outfit(uid, category=0, suffix=b'unknown outfit'):
    # UID/category plus unknown fixed64, bytes and group: all must survive.
    raw = b'\x08' + _varint(uid) + b'\x10' + _varint(category)
    raw += b'\x61' + ((1 << 64) - 9).to_bytes(8, 'little')
    raw += b'\xea\x04' + _varint(len(suffix)) + suffix
    raw += b'\xa3\x01\x08\x07\xa4\x01'
    return b'\x0a' + _varint(len(raw)) + raw


def _owner(lane):
    return Obj(physique='original-' + str(lane), facial_attributes=b'face unknown',
               skin_tone=(1 << 64) - lane, skin_tone_val_shift=0.31,
               pelt_layers=b'unknown pelt', genetic_data=b'unknown genetic',
               custom_texture=b'texture', parts_custom_tattoos=(55, 66),
               voice_pitch=0.42, voice_actor=3, voice_effect=7,
               blob=_outfit(lane * 10 + 1) + b'\x42\x03top')


def _serialized(raw=b'\x08\x0a\xa2\x06\x03new'):
    return {'schema': 1, 'native_message_type': 'Fixture.SimData',
            'native_sha256': hashlib.sha256(raw).hexdigest(), 'native_bytes': len(raw),
            'native_base64': base64.b64encode(raw).decode('ascii'),
            'sim_id': '10', 'save_guid': '30',
            'data': {'message_type': 'Fixture.SimData', 'fields': []},
            'field_schemas': {'Fixture.SimData': []},
            'unknown_fields_retained_in_native_bytes': True,
            'native_serializer_called': True, 'save_file_written': False}


class CasCommitPlanTests(unittest.TestCase):
    def setUp(self):
        self.forms = {lane: _owner(lane) for lane in (1, 2, 4, 8, 16, 32, 64)}
        self.sim = copy.deepcopy(self.forms[64])
        self.sim.id, self.sim.current = 10, 64
        self.sim.occult_tracker = Obj()
        self.backend = Obj(_all_occults=lambda: (2, 4, 8, 16, 32, 64),
                           _get_current_flags=lambda sim: sim.current,
                           _form_map=lambda _: self.forms,
                           _v8_read_outfit_blob=lambda owner: owner.blob)
        self.identity = {'runtime_pid': os.getpid(), 'sim_id': '10',
                         'household_id': '20', 'save_guid': '30'}
        self.pending = plan.checkpoint(self.backend, self.sim, self.read_identity)
        self.original = copy.deepcopy(self.pending)
        self.persisted, self.events, self.writes = None, [], []
        self.bank_receipts, self.bank = [], None
        self.writer_failure_state, self.restore_failure_lane = None, None
        self.ignore_restore_lane, self.bad_bank_ack = None, False
        self.tx = self.make_transaction()

    def read_identity(self):
        return copy.deepcopy(self.identity)

    def write_journal(self, document, expected_previous_sha256):
        self.events.append(('journal', document['state']))
        current = None if self.persisted is None else plan.digest(self.persisted)
        if current != expected_previous_sha256:
            raise ValueError('constructed journal compare-and-swap failed')
        if document['state'] == self.writer_failure_state:
            raise OSError('constructed durable journal failure')
        self.persisted = copy.deepcopy(document)
        return {'durable': True, 'sha256': plan.digest(document)}

    def restore_lane(self, lane, fields):
        self.assertTrue(self.persisted['native_write_possible'])
        self.assertIsNone(self.persisted['native_write_attempted'])
        self.assertIn('raw_return', self.persisted)
        self.assertIn('original_owners', self.persisted)
        self.assertIn('plan', self.persisted)
        self.events.append(('restore', lane))
        self.writes.append(lane)
        if lane == self.restore_failure_lane:
            raise ValueError('constructed native restore failure')
        if lane == self.ignore_restore_lane:
            return
        for owner in [self.forms[int(lane)]] + ([self.sim] if int(lane) == self.sim.current else []):
            for name, value in appearance.payload(fields).items():
                if name == '__outfits__':
                    owner.blob = value[1]
                else:
                    setattr(owner, name, value)

    def commit_bank(self, receipt):
        self.events.append(('bank', receipt['plan_sha256']))
        self.bank_receipts.append(copy.deepcopy(receipt))
        if self.bad_bank_ack:
            raise OSError('constructed atomic metadata failure')
        self.bank = copy.deepcopy(receipt['bank'])
        self.pending = None  # Atomic checkpoint consumption by the embedder.
        return {'committed': True, 'plan_sha256': receipt['plan_sha256']}

    def make_transaction(self):
        return plan.CasCommitTransaction(self.backend, self.sim, lambda: self.pending,
                                        self.read_identity, lambda: self.persisted,
                                        self.write_journal, self.restore_lane, self.commit_bank)

    def edit(self, lane, name='physique', value=None):
        if value is None:
            value = 'accepted edit-' + str(lane)
        setattr(self.forms[lane], name, value)
        if self.sim.current == lane:
            setattr(self.sim, name, value)

    def observe(self, serializer=None):
        return self.tx.observe_return(snapshot_reader=serializer)

    def prepare(self, actions, hair_targets=None):
        dispositions = [{'lane': str(lane), 'action': action} for lane, action in actions]
        return self.tx.prepare(self.tx.pending_sha256, self.tx.raw_return_sha256,
                               dispositions, hair_targets=hair_targets)

    def test_simultaneous_fairy_and_human_edits_survive_all_owner_commit(self):
        self.edit(64)
        self.edit(1)
        self.observe()
        receipt = self.prepare([(64, 'accept-returned'), (1, 'accept-returned')])
        result = self.tx.commit(receipt['plan_sha256'])
        self.assertEqual(result['accepted_lanes'], ['1', '64'])
        self.assertEqual(self.forms[64].physique, 'accepted edit-64')
        self.assertEqual(self.sim.physique, 'accepted edit-64')
        self.assertEqual(self.forms[1].physique, 'accepted edit-1')
        self.assertEqual(set(self.bank), {'1', '2', '4', '8', '16', '32', '64'})
        for lane in (2, 4, 8, 16, 32):
            self.assertEqual(self.bank[str(lane)], self.original['original_owners']['stored'][str(lane)])
        self.assertFalse(result['save_reload_verified'])
        self.assertEqual(self.persisted['state'], 'completed')
        applying = self.events.index(('journal', 'applying'))
        self.assertLess(applying, self.events.index(('restore', '1')))
        self.assertLess(self.events.index(('journal', 'verified')), next(index for index, event in enumerate(self.events) if event[0] == 'bank'))

    def test_changed_inactive_form_can_be_accepted_without_becoming_active(self):
        self.edit(4, 'facial_attributes', b'new inactive face')
        self.observe()
        receipt = self.prepare([(4, 'accept-returned')])
        self.tx.commit(receipt['plan_sha256'])
        self.assertEqual(self.forms[4].facial_attributes, b'new inactive face')
        self.assertEqual(self.sim.current, 64)
        self.assertEqual(self.sim.physique, 'original-64')

    def test_explicit_restore_original_retains_raw_return_as_history(self):
        self.edit(64)
        self.edit(1)
        raw = self.observe()
        receipt = self.prepare([(64, 'accept-returned'), (1, 'restore-original')])
        self.tx.commit(receipt['plan_sha256'])
        self.assertEqual(self.forms[1].physique, 'original-1')
        self.assertEqual(self.persisted['raw_return']['stored']['1']['physique']['value'], 'accepted edit-1')
        self.assertEqual(raw['raw_return_sha256'], self.persisted['raw_return_sha256'])

    def test_every_unknown_outfit_and_appearance_byte_is_retained(self):
        blob = _outfit(641, suffix=b'future opaque\x00\xffbytes') + b'\x42\x05novel'
        self.edit(64, 'blob', blob)
        self.edit(64, 'genetic_data', b'unknown genetics\x00\xff')
        self.edit(1, 'pelt_layers', b'unknown independent\x00\xfe')
        self.observe()
        receipt = self.prepare([(64, 'accept-returned'), (1, 'accept-returned')])
        self.tx.commit(receipt['plan_sha256'])
        self.assertEqual(self.sim.blob, blob)
        self.assertEqual(self.forms[64].blob, blob)
        self.assertEqual(appearance.decode(self.bank['64']['__outfits__']), ('protobuf', blob))
        self.assertEqual(appearance.decode(self.bank['64']['genetic_data']), b'unknown genetics\x00\xff')
        self.assertEqual(appearance.decode(self.bank['1']['pelt_layers']), b'unknown independent\x00\xfe')

    def test_all_changed_lanes_require_dispositions_even_if_not_entry_lane(self):
        self.edit(64)
        self.edit(1)
        self.observe()
        with self.assertRaisesRegex(ValueError, 'Every changed'):
            self.prepare([(64, 'accept-returned')])
        self.assertEqual(self.writes, [])
        self.assertIsNone(self.bank)

    def test_external_payload_or_navigation_receipt_is_not_intent(self):
        self.edit(64)
        self.observe()
        for row in ({'lane': '64', 'action': 'accept-returned', 'fields': {}},
                    {'lane': '64', 'action': 'accept-returned', 'mapping_verified': True}):
            with self.subTest(row=row), self.assertRaisesRegex(ValueError, 'external appearance bytes'):
                self.tx.prepare(self.tx.pending_sha256, self.tx.raw_return_sha256, [row])
        with self.assertRaises(ValueError):
            self.prepare([(64, {'not': 'a decision'})])
        self.assertEqual(self.writes, [])

    def test_duplicate_unknown_and_unchanged_dispositions_are_refused(self):
        self.edit(64)
        self.edit(1)
        self.observe()
        for actions in ([(64, 'accept-returned'), (64, 'restore-original')],
                        [(64, 'accept-returned'), (128, 'accept-returned')],
                        [(64, 'accept-returned'), (4, 'accept-returned')]):
            with self.subTest(actions=actions), self.assertRaises(ValueError):
                self.prepare(actions)
        self.assertEqual(self.writes, [])

    def test_stale_raw_pending_or_plan_hash_never_writes(self):
        self.edit(64)
        self.observe()
        with self.assertRaisesRegex(ValueError, 'hashes are stale'):
            self.tx.prepare(self.tx.pending_sha256, '0' * 64, [{'lane': '64', 'action': 'accept-returned'}])
        receipt = self.prepare([(64, 'accept-returned')])
        with self.assertRaisesRegex(ValueError, 'plan hash differs'):
            self.tx.commit('0' * 64)
        self.pending['lane'] = '1'
        with self.assertRaisesRegex(ValueError, 'pending checkpoint changed'):
            self.tx.commit(receipt['plan_sha256'])
        self.assertEqual(self.writes, [])

    def test_external_journal_change_and_native_change_after_observation_refuse(self):
        self.edit(64)
        self.observe()
        receipt = self.prepare([(64, 'accept-returned')])
        saved = copy.deepcopy(self.persisted)
        self.persisted['extra'] = 'foreign journal mutation'
        with self.assertRaisesRegex(ValueError, 'journal changed'):
            self.tx.commit(receipt['plan_sha256'])
        self.persisted = saved
        self.edit(1)
        with self.assertRaisesRegex(ValueError, 'return changed after observation'):
            self.tx.commit(receipt['plan_sha256'])
        self.assertEqual(self.writes, [])

    def test_runtime_identity_change_refuses_before_native_write(self):
        self.edit(64)
        self.observe()
        receipt = self.prepare([(64, 'accept-returned')])
        self.identity['household_id'] = '21'
        with self.assertRaisesRegex(ValueError, 'runtime ownership changed'):
            self.tx.commit(receipt['plan_sha256'])
        self.assertEqual(self.writes, [])

    def test_replaced_native_wrapper_is_not_certified_by_matching_bytes(self):
        self.edit(64)
        self.observe()
        receipt = self.prepare([(64, 'accept-returned')])
        self.forms[4] = copy.deepcopy(self.forms[4])
        with self.assertRaisesRegex(ValueError, 'owner was replaced'):
            self.tx.commit(receipt['plan_sha256'])
        self.assertEqual(self.writes, [])

    def test_missing_unknown_duplicate_and_aliased_stored_owner_maps_refuse(self):
        original_forms = self.forms
        examples = [dict(self.forms, **{'128': _owner(128)}),
                    {lane: owner for lane, owner in self.forms.items() if lane != 4},
                    dict(self.forms, **{'1': copy.deepcopy(self.forms[1])})]
        alias = dict(self.forms)
        alias[4] = alias[1]
        examples.append(alias)
        for owners in examples:
            self.forms = owners
            self.persisted = None
            self.tx = self.make_transaction()
            with self.subTest(keys=list(owners)), self.assertRaises(plan.RecoveryRequired):
                self.tx.observe_return()
            self.assertEqual(self.writes, [])
            self.assertEqual(self.persisted['state'], 'recovery-required')
            self.assertTrue('raw_return' in self.persisted or 'rejected_owner_observation' in self.persisted)
        self.forms = original_forms

    def test_active_stored_ambiguity_is_preserved_and_cannot_be_planned(self):
        self.sim.physique = 'active edit with stale stored wrapper'
        result = self.observe()
        self.assertTrue(result['ok'])
        self.assertEqual(self.persisted['raw_return']['active']['fields']['physique']['value'], self.sim.physique)
        self.assertEqual(self.persisted['raw_return']['stored']['64']['physique']['value'], 'original-64')
        with self.assertRaisesRegex(ValueError, 'Active and stored CAS appearances disagree'):
            self.prepare([])
        self.assertEqual(self.writes, [])

    def test_raw_return_is_durable_before_serializer_runs_or_raises(self):
        self.edit(64, 'blob', _outfit(641, suffix=b'raw before serializer'))
        def broken_serializer():
            self.events.append(('serializer', 'called'))
            self.assertEqual(self.persisted['state'], 'raw-observed')
            self.assertEqual(appearance.decode(self.persisted['raw_return']['stored']['64']['__outfits__'])[1], self.forms[64].blob)
            raise ValueError('constructed serializer failure')
        with self.assertRaises(plan.RecoveryRequired):
            self.observe(broken_serializer)
        self.assertEqual(self.events[:2], [('journal', 'raw-observed'), ('serializer', 'called')])
        self.assertEqual(self.persisted['state'], 'recovery-required')
        self.assertIn('raw_return', self.persisted)
        self.assertEqual(self.writes, [])
        with self.assertRaises(ValueError):
            self.tx.observe_return()

    def test_serializer_side_effects_cannot_replace_the_raw_accepted_edits(self):
        self.edit(64)
        self.edit(1)
        before = self.forms[64].blob
        def serializer():
            self.edit(64, 'blob', _outfit(641, suffix=b'serializer regenerates hidden outfit'))
            return _serialized(b'complete unknown sim\x00\xff')
        self.observe(serializer)
        self.assertNotEqual(self.persisted['pre_write_owners_sha256'], self.persisted['raw_return_sha256'])
        receipt = self.prepare([(64, 'accept-returned'), (1, 'accept-returned')])
        self.tx.commit(receipt['plan_sha256'])
        self.assertEqual(self.sim.blob, before)
        self.assertIn('native_serialized_append', self.persisted)
        self.assertEqual(self.forms[1].physique, 'accepted edit-1')

    def test_serializer_that_leaves_active_stored_ambiguous_cannot_commit(self):
        self.edit(64)
        def serializer():
            self.sim.physique = 'only active serializer side effect'
            return _serialized()
        self.observe(serializer)
        receipt = self.prepare([(64, 'accept-returned')])
        with self.assertRaisesRegex(ValueError, 'Active and stored CAS appearances disagree'):
            self.tx.commit(receipt['plan_sha256'])
        self.assertEqual(self.writes, [])

    def test_initial_write_ahead_failure_prevents_serializer_and_native_calls(self):
        self.writer_failure_state = 'raw-observed'
        with self.assertRaises(plan.RecoveryRequired):
            self.observe(lambda: self.fail('serializer must follow a durable raw receipt'))
        self.assertEqual(self.persisted['state'], 'recovery-required')
        self.assertIn('raw_return', self.persisted)
        self.assertFalse(self.tx.native_write_attempted)
        self.assertEqual(self.writes, [])

    def test_apply_write_ahead_failure_prevents_every_native_and_bank_call(self):
        self.edit(64)
        self.observe()
        receipt = self.prepare([(64, 'accept-returned')])
        self.writer_failure_state = 'applying'
        with self.assertRaises(plan.RecoveryRequired):
            self.tx.commit(receipt['plan_sha256'])
        self.assertEqual(self.writes, [])
        self.assertEqual(self.bank_receipts, [])
        self.assertIn('plan', self.persisted)
        self.assertFalse(self.persisted['native_write_attempted'])
        with self.assertRaisesRegex(ValueError, 'replay refused'):
            self.tx.commit(receipt['plan_sha256'])

    def test_partial_native_restore_failure_preserves_all_states_and_no_bank_commit(self):
        self.edit(1)
        self.edit(64)
        self.observe()
        receipt = self.prepare([(64, 'accept-returned'), (1, 'accept-returned')])
        self.restore_failure_lane = '4'
        with self.assertRaises(plan.RecoveryRequired):
            self.tx.commit(receipt['plan_sha256'])
        self.assertEqual(self.writes, ['1', '2', '4'])
        self.assertEqual(self.bank_receipts, [])
        self.assertTrue(self.persisted['native_write_attempted'])
        self.assertFalse(self.persisted['bank_commit_attempted'])
        self.assertFalse(self.persisted['automatic_replay_allowed'])
        self.assertEqual(set(self.persisted['plan']['desired']), set(self.original['original_owners']['stored']))
        with self.assertRaises(ValueError):
            self.tx.commit(receipt['plan_sha256'])

    def test_stored_verify_failure_never_updates_bank_or_hair_policy(self):
        self.edit(1)
        self.observe()
        receipt = self.prepare([(1, 'restore-original')])
        self.ignore_restore_lane = '1'
        with self.assertRaisesRegex(plan.RecoveryRequired, 'lane 1'):
            self.tx.commit(receipt['plan_sha256'])
        self.assertEqual(self.bank_receipts, [])
        self.assertIsNone(self.bank)

    def test_active_verify_failure_is_not_hidden_by_matching_stored_wrapper(self):
        self.edit(64)
        self.observe()
        receipt = self.prepare([(64, 'restore-original')])
        native_restore = self.tx.restore_lane
        def stored_only(lane, fields):
            native_restore(lane, fields)
            if lane == '64':
                self.sim.physique = 'stale active sim'
        self.tx.restore_lane = stored_only
        with self.assertRaisesRegex(plan.RecoveryRequired, 'Final active CAS appearance differs'):
            self.tx.commit(receipt['plan_sha256'])
        self.assertEqual(self.bank_receipts, [])

    def test_hair_intent_is_bound_to_accepted_lane_original_and_returned_uid(self):
        self.edit(64)
        self.observe()
        targets = {'64': [{'category': 0, 'ordinal': 0, 'outfit_id': '641'}]}
        receipt = self.prepare([(64, 'accept-returned')], targets)
        self.tx.commit(receipt['plan_sha256'])
        self.assertEqual(self.bank_receipts[0]['hair_targets'], targets)
        self.assertTrue(self.bank_receipts[0]['final_native_appearance']['verified'])
        self.assertEqual(self.bank_receipts[0]['bank']['64'], self.persisted['raw_return']['stored']['64'])

    def test_hair_replaced_reordered_duplicate_unknown_or_external_target_refused(self):
        self.edit(64)
        self.observe()
        bad = [
            {'64': [{'category': 0, 'ordinal': 0, 'outfit_id': '642'}]},
            {'64': [{'category': 0, 'ordinal': 0, 'outfit_id': '641'}, {'category': 0, 'ordinal': 0, 'outfit_id': '641'}]},
            {'1': [{'category': 0, 'ordinal': 0, 'outfit_id': '11'}]},
            {'64': [{'category': 0, 'ordinal': 0, 'outfit_id': '641', 'fields': {}}]},
        ]
        for targets in bad:
            with self.subTest(targets=targets), self.assertRaises(ValueError):
                self.prepare([(64, 'accept-returned')], targets)
        self.assertEqual(self.writes, [])

    def test_returned_outfit_replacement_refuses_even_with_original_uid_target(self):
        self.edit(64, 'blob', _outfit(649))
        self.observe()
        with self.assertRaisesRegex(ValueError, 'replaced'):
            self.prepare([(64, 'accept-returned')], {'64': [{'category': 0, 'ordinal': 0, 'outfit_id': '641'}]})
        self.assertEqual(self.writes, [])

    def test_no_changed_lane_requires_no_invented_intent(self):
        self.observe()
        receipt = self.prepare([])
        result = self.tx.commit(receipt['plan_sha256'])
        self.assertEqual(result['accepted_lanes'], [])
        self.assertEqual(self.bank, self.original['original_owners']['stored'])

    def test_atomic_metadata_failure_is_recovery_required_and_not_replayed(self):
        self.edit(64)
        self.observe()
        receipt = self.prepare([(64, 'accept-returned')])
        self.bad_bank_ack = True
        with self.assertRaises(plan.RecoveryRequired):
            self.tx.commit(receipt['plan_sha256'])
        self.assertTrue(self.persisted['bank_commit_attempted'])
        self.assertIsNone(self.persisted['bank_committed'])
        self.assertEqual(self.persisted['bank_commit_outcome'], 'unresolved')
        self.assertIsNone(self.bank)
        count = len(self.writes)
        with self.assertRaises(ValueError):
            self.tx.commit(receipt['plan_sha256'])
        self.assertEqual(len(self.writes), count)

    def test_completed_transaction_is_one_use_and_requires_no_live_save(self):
        self.observe()
        receipt = self.prepare([])
        self.tx.commit(receipt['plan_sha256'])
        count = len(self.writes)
        with self.assertRaisesRegex(ValueError, 'replay refused'):
            self.tx.commit(receipt['plan_sha256'])
        self.assertEqual(len(self.writes), count)
        self.assertFalse(self.persisted['save_reload_verified'])

    def test_old_checkpoint_or_an_existing_recovery_journal_cannot_be_rehydrated(self):
        pending = self.pending
        self.pending = {'state': 'captured', 'runtime_pid': os.getpid(), 'lane': '64',
                        'originals': pending['original_owners']['stored']}
        with self.assertRaisesRegex(ValueError, 'schema-2'):
            self.make_transaction()
        self.pending = pending
        self.persisted = {'state': 'recovery-required'}
        with self.assertRaisesRegex(ValueError, 'automatic replay is blocked'):
            self.make_transaction()

    def test_wrong_runtime_and_ambiguous_original_checkpoint_are_refused(self):
        self.pending['runtime_pid'] = os.getpid() + 1
        with self.assertRaises(ValueError):
            self.make_transaction()
        self.pending = copy.deepcopy(self.original)
        self.pending['original_owners']['active']['fields']['physique']['value'] = 'ambiguous original'
        with self.assertRaisesRegex(ValueError, 'Active and stored'):
            self.make_transaction()

    def test_invalid_complete_serializer_byte_identity_is_rejected_after_raw_retention(self):
        self.edit(64)
        invalid = _serialized()
        invalid['native_sha256'] = '0' * 64
        with self.assertRaisesRegex(plan.RecoveryRequired, 'exact byte/catalog readback'):
            self.observe(lambda: invalid)
        self.assertIn('raw_return', self.persisted)
        self.assertNotIn('native_serialized_append', self.persisted)
        self.assertEqual(self.writes, [])

    def test_writer_that_persists_then_returns_bad_ack_does_not_lose_raw_state(self):
        self.edit(64)
        good_writer = self.tx.journal_writer
        def bad_ack(document, expected_previous_sha256):
            receipt = good_writer(document, expected_previous_sha256)
            if document['state'] == 'raw-observed':
                receipt['sha256'] = '0' * 64
            return receipt
        self.tx.journal_writer = bad_ack
        with self.assertRaises(plan.RecoveryRequired):
            self.observe(lambda: self.fail('bad raw journal ACK cannot authorize serializer'))
        self.assertEqual(self.persisted['state'], 'recovery-required')
        self.assertEqual(self.persisted['raw_return']['stored']['64']['physique']['value'], 'accepted edit-64')
        self.assertEqual(self.writes, [])

    def test_bank_that_consumes_pending_then_returns_bad_ack_is_unresolved_no_replay(self):
        self.observe()
        receipt = self.prepare([])
        good_bank = self.tx.commit_bank
        def bad_ack(document):
            acknowledgment = good_bank(document)
            acknowledgment['plan_sha256'] = '0' * 64
            return acknowledgment
        self.tx.commit_bank = bad_ack
        with self.assertRaises(plan.RecoveryRequired):
            self.tx.commit(receipt['plan_sha256'])
        self.assertIsNone(self.pending)
        self.assertIsNotNone(self.bank)
        self.assertIsNone(self.persisted['bank_committed'])
        self.assertEqual(self.persisted['bank_commit_outcome'], 'unresolved')
        self.assertTrue(self.persisted['bank_commit_attempted'])
        with self.assertRaises(ValueError):
            self.tx.commit(receipt['plan_sha256'])

    def test_final_journal_failure_after_bank_consumption_remains_persistently_blocked(self):
        self.observe()
        receipt = self.prepare([])
        self.writer_failure_state = 'completed'
        with self.assertRaises(plan.RecoveryRequired):
            self.tx.commit(receipt['plan_sha256'])
        self.assertIsNone(self.pending)
        self.assertTrue(self.persisted['bank_committed'])
        self.assertEqual(self.persisted['bank_commit_outcome'], 'acknowledged')
        self.assertEqual(self.persisted['state'], 'recovery-required')
        self.assertIn('plan', self.persisted)
        self.pending = copy.deepcopy(self.original)
        with self.assertRaisesRegex(ValueError, 'automatic replay is blocked'):
            self.make_transaction()

    def test_unknown_native_owner_rows_are_preserved_without_becoming_plans(self):
        self.forms[128] = _owner(128)
        self.tx = self.make_transaction()
        with self.assertRaises(plan.RecoveryRequired):
            self.observe(lambda: self.fail('invalid owners cannot reach serialization'))
        rows = self.persisted['rejected_owner_observation']['stored_rows']
        unknown = [row for row in rows if row['native_lane'] == '128']
        self.assertEqual(len(unknown), 1)
        self.assertEqual(appearance.decode(unknown[0]['fields']['__outfits__'])[1], self.forms[128].blob)
        self.assertFalse(self.persisted['rejected_owner_observation']['usable_as_plan'])
        self.assertEqual(self.writes, [])

    def test_missing_returned_owner_retains_remaining_raw_before_refusal(self):
        del self.forms[4]
        self.tx = self.make_transaction()
        with self.assertRaises(plan.RecoveryRequired):
            self.observe(lambda: self.fail('missing owners cannot reach serialization'))
        self.assertEqual(set(self.persisted['raw_return']['stored']), {'1', '2', '8', '16', '32', '64'})
        self.assertIn('4', self.persisted['original_owners']['stored'])
        self.assertEqual(self.writes, [])

    def test_entry_fairy_can_return_as_human_and_accept_both_explicit_edits(self):
        for name, value in vars(self.forms[1]).items():
            setattr(self.sim, name, copy.deepcopy(value))
        self.sim.current = 1
        self.edit(1)
        self.edit(64)
        self.observe()
        receipt = self.prepare([(1, 'accept-returned'), (64, 'accept-returned')])
        self.tx.commit(receipt['plan_sha256'])
        self.assertEqual(self.persisted['plan']['active_lane'], '1')
        self.assertEqual(self.sim.physique, 'accepted edit-1')
        self.assertEqual(self.forms[64].physique, 'accepted edit-64')
        self.assertEqual(self.bank_receipts[0]['active_lane'], '1')

    def test_native_integer_enum_lanes_are_canonicalized_without_losing_owner_binding(self):
        class NativeLane(IntEnum):
            HUMAN = 1
            FAIRY = 64
        self.forms = {NativeLane.HUMAN: self.forms[1], NativeLane.FAIRY: self.forms[64]}
        self.pending = plan.checkpoint(self.backend, self.sim, self.read_identity)
        self.tx = self.make_transaction()
        self.edit(1)
        self.edit(64)
        self.observe()
        receipt = self.prepare([(1, 'accept-returned'), (64, 'accept-returned')])
        self.tx.commit(receipt['plan_sha256'])
        self.assertEqual(set(self.bank), {'1', '64'})

    def test_multiple_hair_targets_bind_each_category_ordinal_and_uid(self):
        wardrobe = _outfit(641) + _outfit(642) + _outfit(643, 7)
        self.edit(64, 'blob', wardrobe)
        self.pending = plan.checkpoint(self.backend, self.sim, self.read_identity)
        self.tx = self.make_transaction()
        self.edit(64, 'blob', _outfit(641, suffix=b'accepted hair1') + _outfit(642, suffix=b'accepted hair2') + _outfit(643, 7))
        self.observe()
        targets = {'64': [{'category': 0, 'ordinal': 0, 'outfit_id': '641'},
                          {'category': 0, 'ordinal': 1, 'outfit_id': '642'}]}
        receipt = self.prepare([(64, 'accept-returned')], targets)
        self.tx.commit(receipt['plan_sha256'])
        self.assertEqual(self.bank_receipts[0]['hair_targets'], targets)
        self.assertEqual(self.forms[64].blob, self.sim.blob)

    def test_mutating_an_internal_plan_cannot_authorize_external_payload_bytes(self):
        self.edit(64)
        self.observe()
        self.prepare([(64, 'accept-returned')])
        self.tx.plan['desired']['1']['physique']['value'] = 'externally supplied bytes'
        with self.assertRaisesRegex(ValueError, 'plan hash differs'):
            self.tx.commit(plan.digest(self.tx.plan))
        self.assertEqual(self.writes, [])

    def test_replacement_sim_with_same_ids_is_not_the_authenticated_manager_owner(self):
        self.backend._get_sim_info_by_id = lambda _: self.sim
        self.observe()
        receipt = self.prepare([])
        replacement = copy.deepcopy(self.sim)
        self.backend._get_sim_info_by_id = lambda _: replacement
        with self.assertRaisesRegex(ValueError, 'manager-owned object'):
            self.tx.commit(receipt['plan_sha256'])
        self.assertEqual(self.writes, [])


if __name__ == '__main__':
    unittest.main()
