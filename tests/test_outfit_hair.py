import copy
import sys
from pathlib import Path
from types import SimpleNamespace as Obj
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import outfit_hair, studio, form_bank, form_appearance as appearance
import test_studio


class OutfitHairTests(unittest.TestCase):
    def setUp(self):
        test_studio.StudioTests.setUp(self)
        message = test_studio.Message(self.sim.raw)
        message.outfits[1].category = 0  # Everyday 2, a distinct numbered outfit.
        message.outfits[1].parts.ids[0] = 1200
        formal = copy.deepcopy(message.outfits[1]); formal.category=1; formal.outfit_id=3
        formal.parts.ids[0]=1500; formal.part_shifts.color_shift[0]=2**64-2
        message.outfits.append(formal); self.sim.raw=message.SerializeToString()
        self.sim.on_outfit_changed=[]
        self.sim.register_for_outfit_changed_callback=self.sim.on_outfit_changed.append
        self.sim.get_current_outfit=lambda: (0, 0)
        self.backend._APEX_GAME_THREAD_IDENT=threading.current_thread().ident
        self.backend._log=lambda *_: None
        self.backend._v8_resolve_body_type=lambda value: (7 if value=='HAIR' else None if value=='HAIRCOLOR_OVERRIDE' else int(value), {}, 'runtime')
        self.backend._studio_casp_bytes=lambda _: test_studio.casp(body=7)
        self.addCleanup(outfit_hair._BUSY.clear)
        self.addCleanup(outfit_hair._ERRORS.clear)

    def request(self, action, value=None):
        return studio.dispatch(self.backend, action, self.sim.id, value)

    def change_all_hair(self):
        message=test_studio.Message(self.sim.raw)
        for outfit in message.outfits:
            outfit.parts.ids[0]=9999; outfit.part_shifts.color_shift[0]=123456789
            outfit.parts.ids[1]=3333  # An unrelated legitimate clothing edit.
        self.sim.raw=message.SerializeToString()

    def test_event_restores_every_category_and_outfit_number_preserving_other_changes(self):
        original=outfit_hair.capture(self.backend,appearance.packed(self.backend,self.sim))
        policy=self.request('studio_hair_enable')['hair_policy']
        self.assertEqual(policy['outfit_count'],3)
        self.assertEqual(len(self.sim.on_outfit_changed),1)
        self.change_all_hair(); self.sim.skin_tone=999; self.sim.progression=77
        self.sim.on_outfit_changed[0](self.sim,(0,1),(0,0))
        self.assertEqual(outfit_hair.capture(self.backend,appearance.packed(self.backend,self.sim)),original)
        self.assertEqual([row.parts.ids[1] for row in test_studio.Message(self.sim.raw).outfits],[3333]*3)
        self.assertEqual((self.sim.skin_tone,self.sim.progression),(999,77))
        self.assertIn('Keep independent outfit hairstyle',self.request('studio_history')['history_nodes'][-1]['label'])

    def test_accepted_live_hair_edit_updates_only_selected_number_and_survives_propagation(self):
        self.request('studio_hair_enable'); before=self.request('studio_status')
        preview=self.request('studio_part_preview',__import__('json').dumps(dict(target='0:7:0',source='1:7:0',
            lane=before['history_lane'],appearance_sha256=before['appearance_sha256'])))
        self.request('studio_apply',preview['preview_id'])
        held=outfit_hair.capture(self.backend,appearance.packed(self.backend,self.sim))
        self.assertEqual([row['hair'][0]['row']['id'] for row in held],[1200,1200,1500])
        self.change_all_hair(); self.assertTrue(outfit_hair.enforce(self.backend,self.sim))
        self.assertEqual(outfit_hair.capture(self.backend,appearance.packed(self.backend,self.sim)),held)

    def test_cas_accepts_target_hair_but_reverses_propagation_to_other_numbers_and_categories(self):
        self.request('studio_hair_enable')
        path,key=form_bank.context(self.backend,self.sim);record=form_bank.load(path)['records'][key]
        original=outfit_hair.capture(self.backend,appearance.packed(self.backend,self.sim))
        self.change_all_hair();returned=appearance.packed(self.backend,self.sim)
        chosen=outfit_hair.accept_cas(self.backend,record,'32',returned,[0,1])
        rows=outfit_hair.capture(self.backend,chosen)
        self.assertEqual(rows[0],original[0]);self.assertEqual(rows[2],original[2])
        self.assertEqual(rows[1]['hair'][0]['row']['id'],9999)
        self.assertEqual(rows[1]['hair'][0]['row']['color_shift'],123456789)
        self.assertEqual([row.parts.ids[1] for row in test_studio.Message(appearance.decode(chosen['__outfits__'])[1]).outfits],[3333]*3)
        self.assertEqual(self.sim.raw,appearance.decode(returned['__outfits__'])[1]) # Preview/repair planning is pure.
        with self.assertRaisesRegex(ValueError,'explicit CAS hair target'):
            outfit_hair.accept_cas(self.backend,record,'32',returned,None)

    def test_disabled_policy_and_unknown_outfit_identity_do_not_overwrite_new_wardrobe(self):
        self.request('studio_hair_enable');self.request('studio_hair_disable');self.change_all_hair()
        before=self.sim.raw;self.assertFalse(outfit_hair.enforce(self.backend,self.sim));self.assertEqual(self.sim.raw,before)
        self.request('studio_hair_enable');message=test_studio.Message(self.sim.raw)
        message.outfits[0].outfit_id=9000;self.sim.raw=message.SerializeToString();before=self.sim.raw
        with self.assertRaisesRegex(ValueError,'Outfit identity changed'):
            outfit_hair.enforce(self.backend,self.sim)
        self.assertEqual(self.sim.raw,before)

    def test_pending_cas_or_studio_preview_blocks_event_repair_and_bank_failure_rolls_back(self):
        self.request('studio_hair_enable');self.change_all_hair();before=self.sim.raw
        with patch.object(form_bank,'save',side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError,'disk full'):outfit_hair.enforce(self.backend,self.sim)
        self.assertEqual(self.sim.raw,before)
        path,key=form_bank.context(self.backend,self.sim);data=form_bank.load(path)
        data['records'][key]['pending']={'state':'captured'};form_bank.save(path,data)
        self.assertFalse(outfit_hair.enforce(self.backend,self.sim));self.assertEqual(self.sim.raw,before)

    def test_restart_hook_chains_original_once_and_does_not_scan_on_ticks(self):
        self.request('studio_hair_enable');self.sim.on_outfit_changed.clear();self.change_all_hair()
        calls=[]
        class Wrapper:
            def set_current_outfit(info,value):
                calls.append(value)
                for callback in list(info.on_outfit_changed):callback(info,value,(0,0))
                return True
        outfit_hair.install(self.backend,Wrapper);wrapped=Wrapper.set_current_outfit
        outfit_hair.install(self.backend,Wrapper);self.assertIs(Wrapper.set_current_outfit,wrapped)
        self.assertTrue(Wrapper.set_current_outfit(self.sim,(0,1)))
        self.assertEqual(calls,[(0,1)]);self.assertEqual(len(self.sim.on_outfit_changed),1)
        self.assertEqual(test_studio.Message(self.sim.raw).outfits[2].parts.ids[0],1500)
