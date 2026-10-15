import copy
import json
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch
from types import SimpleNamespace as Obj

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import lifestate_forms as forms, lifestates, form_bank, form_appearance as appearance, studio
import test_form_bank as bank_fixture
from test_outfit_snapshot import outfit
import test_studio as studio_fixture


class LifeStateFormsTests(unittest.TestCase):
    def setUp(self):
        bank_fixture.FormBankTests.setUp(self)
        self.backend._APEX_GAME_THREAD_IDENT = threading.current_thread().ident
        self.backend._get_sim_info_by_id = lambda value: self.sim if str(value) == str(self.sim.id) else None
        self.sim.occult_types = 5
        self.backend._get_occult_flags = lambda sim: sim.occult_types
        self.original = self.capture('human_original', 'HUMAN')

    def capture(self, identity, state='PLANTSIM', base=1):
        return forms.capture(self.backend, self.sim, dict(id=identity, lifestate=state,
            label=identity.replace('_', ' '), base_form=base))['form']

    def record(self):
        path, key = form_bank.context(self.backend, self.sim)
        return form_bank.load(path)['records'][key]

    def bind(self):
        return forms.bind(self.backend, self.sim, dict(id=self.original['id'],
            expected_sha256=self.original['appearance_sha256']))

    def modified(self, identity='plant', state='PLANTSIM', base=1):
        row = self.capture(identity, state, base)
        fields = dict(row['fields'], physique=appearance.encode('Independent ' + identity),
            facial_attributes=appearance.encode(b'face and unknown future morph bytes'),
            skin_tone=appearance.encode((1 << 64)-1), skin_tone_val_shift=appearance.encode(0.13),
            parts_custom_tattoos=appearance.encode((44, 55)), pelt_layers=appearance.encode(b'pelt'),
            custom_texture=appearance.encode(7788), genetic_data=appearance.encode(b'genetics'),
            voice_pitch=appearance.encode(0.8), voice_actor=appearance.encode(7), voice_effect=appearance.encode(2))
        # Switches require matching complete getter sets; actual game wrappers
        # expose these fields on both active and stored owners.
        for owner in (self.sim, self.human, self.vampire):
            for name in fields:
                if name != '__outfits__' and not hasattr(owner, name):
                    setattr(owner, name, appearance.decode(fields[name]))
        forms.update(self.backend, self.sim, identity, fields, row['appearance_sha256'])
        return forms.stored(self.backend, self.sim, identity)

    def test_all_registered_life_states_have_independent_capture_owners(self):
        before = form_bank.capture(self.backend, self.sim)
        for state in list(lifestates.NATIVE) + list(lifestates.SPECIAL):
            row = self.capture('look_' + state.lower(), state)
            self.assertEqual(row['lifestate'], state)
        self.assertEqual(form_bank.capture(self.backend, self.sim), before)
        rows = forms.list_forms(self.backend, self.sim)['forms']
        self.assertEqual(len(rows), len(lifestates.NATIVE) + len(lifestates.SPECIAL) + 1)
        self.assertEqual(len({forms.handle(row['id']) for row in rows}), len(rows))

    def test_inactive_tattoos_skin_voice_morphs_and_outfits_never_write_a_sim(self):
        before = form_bank.capture(self.backend, self.sim)
        row = self.capture('skeleton', 'SKELETON')
        fields = dict(row['fields'], physique=appearance.encode('shape'),
                      __outfits__=appearance.encode(('protobuf', outfit(0, 818))))
        with patch.object(self.backend, '_restore_siminfo_payload', side_effect=AssertionError('native write')):
            forms.update(self.backend, self.sim, row['id'], fields, row['appearance_sha256'])
        self.assertEqual(form_bank.capture(self.backend, self.sim), before)
        self.assertEqual(forms.stored(self.backend, self.sim, row['id'])['fields'], fields)

    def test_binding_never_replaces_an_existing_display_owner(self):
        self.bind()
        row = self.capture('second')
        with self.assertRaisesRegex(ValueError, 'already'):
            forms.bind(self.backend, self.sim, dict(id=row['id'], expected_sha256=row['appearance_sha256']))

    def test_switch_preserves_other_native_occults_and_returns_to_original(self):
        self.bind()
        row = self.capture('plant')
        edited = dict(row['fields'], physique=appearance.encode('plant-only body'),
                      __outfits__=appearance.encode(('protobuf', outfit(0, 77))))
        forms.update(self.backend, self.sim, row['id'], edited, row['appearance_sha256'])
        row = forms.stored(self.backend, self.sim, row['id'])
        vamp_before = appearance.packed(self.backend, self.vampire)
        reply = forms.select(self.backend, self.sim, dict(id=row['id'], expected_sha256=row['appearance_sha256']))
        self.assertTrue(reply['other_native_forms_verified'])
        self.assertFalse(reply['gameplay_modified'])
        self.assertEqual(self.sim.physique, 'plant-only body')
        self.assertEqual(self.human.physique, 'plant-only body')
        self.assertEqual(appearance.packed(self.backend, self.vampire), vamp_before)
        forms.select(self.backend, self.sim, dict(id=self.original['id'], expected_sha256=self.original['appearance_sha256']))
        self.assertEqual(self.sim.physique, 'Human original')
        self.assertEqual(forms.stored(self.backend, self.sim, row['id'])['fields'], edited)
        self.assertEqual(self.sim.occult_types, 5)

    def test_accepted_cas_and_live_edits_update_only_the_active_variant(self):
        self.bind()
        other = self.capture('ghost', 'GHOST')
        self.sim.physique = self.human.physique = 'CAS accepted body'
        fields = appearance.packed(self.backend, self.sim)
        form_bank.update(self.backend, self.sim, 1, fields)
        self.assertEqual(forms.stored(self.backend, self.sim, self.original['id'])['fields'], fields)
        self.assertEqual(forms.stored(self.backend, self.sim, other['id']), other)

    def test_stale_edit_and_switch_checksums_change_no_appearance_or_metadata(self):
        row = self.capture('plant')
        before = copy.deepcopy(self.record())
        for operation in ('select', 'update'):
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                if operation == 'select':
                    forms.select(self.backend, self.sim, dict(id=row['id'], expected_sha256='0'*64))
                else:
                    forms.update(self.backend, self.sim, row['id'], row['fields'], '0'*64)
        self.assertEqual(self.record(), before)

    def test_missing_native_base_is_never_generated_or_converted(self):
        with self.assertRaisesRegex(ValueError, 'existing native'):
            self.capture('new_alien', 'ALIEN', base=2)
        self.assertEqual(set(self.forms), {1, 4})

    def test_unknown_sim_and_wrong_thread_are_rejected_before_disk_or_native_write(self):
        for invalid in ('sim', 'thread'):
            with self.subTest(invalid=invalid):
                backend = copy.copy(self.backend)
                if invalid == 'sim': backend._get_sim_info_by_id = lambda _: None
                else: backend._APEX_GAME_THREAD_IDENT = -1
                with self.assertRaises(ValueError): forms.list_forms(backend, self.sim)

    def test_foreign_native_base_requires_explicit_native_selection_first(self):
        row = self.capture('vampire_reaper', 'REAPER', base=4)
        with self.assertRaisesRegex(ValueError, 'base form first'):
            forms.select(self.backend, self.sim, dict(id=row['id'], expected_sha256=row['appearance_sha256']))
        self.assertEqual(self.sim.current_occult_types, 1)

    def test_rejected_native_write_retains_intent_and_stops_further_edits(self):
        self.bind()
        row = self.capture('plant')
        fields = dict(row['fields'], physique=appearance.encode('rejected shape'))
        forms.update(self.backend, self.sim, row['id'], fields, row['appearance_sha256'])
        row = forms.stored(self.backend, self.sim, row['id'])
        with patch.object(self.backend, '_restore_siminfo_payload', return_value=None):
            with self.assertRaises(ValueError):
                forms.select(self.backend, self.sim, dict(id=row['id'], expected_sha256=row['appearance_sha256']))
        record = self.record()
        self.assertEqual(record['switch_pending']['state'], 'recovery-required')
        self.assertFalse(record['switch_pending']['retry_safe'])
        self.assertIn('1', record['switch_pending']['originals'])
        with self.assertRaises(ValueError): self.capture('must_not_replay')

    def test_checksums_and_aliases_do_not_turn_special_states_into_native_bits(self):
        for alias, canonical in lifestates.ALIASES.items():
            self.assertEqual(lifestates.name(alias), canonical)
        for state in lifestates.SPECIAL:
            self.assertNotIn(state, lifestates.NATIVE)
        data = forms.document(self.record())
        data['forms'][self.original['id']]['fields']['physique'] = appearance.encode('foreign')
        with self.assertRaisesRegex(ValueError, 'checksum'): forms.validate(data)

    def test_field_loss_and_unqualified_reload_never_apply_an_old_variant(self):
        row = self.capture('plant')
        with self.assertRaisesRegex(ValueError, 'every captured field'):
            forms.update(self.backend, self.sim, row['id'], {'__outfits__': row['fields']['__outfits__']}, row['appearance_sha256'])
        path,key=form_bank.context(self.backend,self.sim)
        bank=form_bank.load(path);bank['records'][key]['lifestate_runtime_pid']=os.getpid()+1;form_bank.save(path,bank)
        with self.assertRaisesRegex(ValueError, 'reload is not yet qualified'):
            forms.stored(self.backend,self.sim,row['id'])


class LifeStateStudioTests(unittest.TestCase):
    def setUp(self):
        studio_fixture.StudioTests.setUp(self)
        self.sim.physique = '0.1,0.2,0.3,'
        self.backend._APEX_GAME_THREAD_IDENT = threading.current_thread().ident
        self.row = forms.capture(self.backend, self.sim, dict(id='wolf_cc', lifestate='WEREWOLF',
            label='CC werewolf', base_form=32))['form']

    def request(self, action, value=None):
        return studio.dispatch(self.backend, action, str(self.sim.id),
            json.dumps({'form': forms.handle(self.row['id']), 'value': value}))

    def test_studio_lists_all_existing_native_and_custom_owners_without_activation(self):
        result = self.request('studio_status')
        self.assertEqual(result['inspected_form_flags'], forms.handle(self.row['id']))
        self.assertEqual(result['visual_form'], 32)
        inventory = result['form_inventory']
        self.assertEqual({row['flags'] for row in inventory}, {32, forms.handle(self.row['id'])})

    def test_studio_preview_apply_and_undo_change_only_stored_variant(self):
        original = self.sim.raw
        inspected = self.request('studio_shape_inspect')
        control = next(row for row in inspected['shape_editor'] if row['field'] == 'physique' and row['index'] == 1)
        request = {key: control[key] for key in ('field', 'group', 'index', 'key')}
        request.update(before=control['value'], value=.57, lane=inspected['history_lane'], appearance_sha256=inspected['appearance_sha256'])
        preview = self.request('studio_shape_preview', json.dumps(request))
        self.request('studio_apply', preview['preview_id'])
        self.assertEqual(self.sim.raw, original)
        stored = forms.stored(self.backend, self.sim, self.row['id'])
        self.assertNotEqual(stored['fields']['physique'], self.row['fields']['physique'])
        undo = self.request('studio_undo')
        self.request('studio_apply', undo['preview_id'])
        self.assertEqual(forms.stored(self.backend, self.sim, self.row['id'])['fields'], self.row['fields'])
        self.assertEqual(self.sim.raw, original)

    def test_active_variant_edits_use_the_real_base_and_sync_accepted_history(self):
        forms.bind(self.backend,self.sim,dict(id=self.row['id'],expected_sha256=self.row['appearance_sha256']))
        inspected=self.request('studio_shape_inspect')
        control=next(row for row in inspected['shape_editor'] if row['field']=='physique' and row['index']==1)
        request={key:control[key] for key in ('field','group','index','key')}
        request.update(before=control['value'],value=.61,lane=inspected['history_lane'],appearance_sha256=inspected['appearance_sha256'])
        self.request('studio_shape_live',json.dumps(request))
        self.assertEqual([float(x) for x in self.sim.physique.rstrip(',').split(',')],[.1,.61,.3])
        self.assertEqual(forms.stored(self.backend,self.sim,self.row['id'])['fields'],appearance.packed(self.backend,self.sim))
