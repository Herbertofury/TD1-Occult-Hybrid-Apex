from pathlib import Path
import json
import sys
import tempfile
import unittest
from types import SimpleNamespace as Obj
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
import td1_occult_hybrid_apex as backend
from apex_core import occult_add_guard as guard


def outfit(label,category=0):
    child=b'\x08\x01\x10'+bytes([category])+b'\x1a'+bytes([len(label)])+label
    return b'\x0a'+bytes([len(child)])+child


class OccultAddGuardTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.human=Obj(id=10,skin_tone=100,blob=outfit(b'human'))
        self.alien=Obj(id=11,skin_tone=200,blob=outfit(b'alien'))
        self.sim=Obj(id=12,skin_tone=300,blob=outfit(b'active-alien'),occult_types=3,current_occult_types=2)
        self.mapping={1:self.human,2:self.alien};self.sim.occult_tracker=Obj(_sim_info_map=self.mapping)
        self.fake=Obj(_form_map=lambda tracker:tracker._sim_info_map,
            _snapshot_siminfo_payload=lambda owner:dict(skin_tone=owner.skin_tone,__outfits__=('protobuf',owner.blob)),
            _get_occult_flags=lambda sim:sim.occult_types,_get_current_flags=lambda sim:sim.current_occult_types,
            _all_occults=lambda:[2,4,8,16,32,64],_has_occult=lambda tracker,kind:bool(self.sim.occult_types&kind),
            _coerce_flags=lambda flag:flag,
            _set_flags=lambda sim,name,value:setattr(sim,name,value),
            _data_directory=lambda:self.temporary.name,
            services=Obj(get_persistence_service=lambda:Obj(get_save_slot_proto_guid=lambda:99)))
        def restore(owner,rows):
            if 'skin_tone' in rows:owner.skin_tone=rows['skin_tone']
            if '__outfits__' in rows:owner.blob=rows['__outfits__'][1]
            if 'flags' in rows:owner.flags=rows['flags']
        self.fake._restore_siminfo_payload=restore
        self.originals={id(o):guard.fields(self.fake,o) for o in [self.human,self.alien,self.sim]}

    def mutate_native(self):
        self.generated=Obj(id=13,skin_tone=800,blob=outfit(b'EA-mermaid'))
        self.mapping[8]=self.generated;self.mapping[2]=Obj(id=14,skin_tone=700,blob=outfit(b'replaced-alien'))
        self.alien.skin_tone=900;self.sim.skin_tone=600;self.sim.blob=outfit(b'mermaid-active')
        self.sim.current_occult_types=8;self.sim.occult_types=3

    def assert_originals(self):
        self.assertIs(self.mapping[2],self.alien)
        for o in [self.human,self.alien,self.sim]:self.assertEqual(guard.fields(self.fake,o),self.originals[id(o)])

    def test_new_membership_restores_every_previous_wrapper_and_active_look(self):
        preservation=guard.Preservation(self.fake,self.sim,8)
        self.mutate_native();preservation.restore(11,accepted=True)
        self.assert_originals();self.assertIs(self.mapping[8],self.generated)
        self.assertEqual((self.sim.occult_types,self.sim.current_occult_types),(11,2))
        self.assertEqual(self.generated.blob,outfit(b'EA-mermaid'))
        self.assertEqual(json.loads(preservation.path.read_text())['stage'],'restored')

    def test_unrestorable_owner_keeps_exact_durable_expected_and_observed_values(self):
        preservation=guard.Preservation(self.fake,self.sim,8);self.mutate_native()
        self.fake._restore_siminfo_payload=lambda *_:None
        with self.assertRaisesRegex(ValueError,'preimages retained'):preservation.restore(11,accepted=True)
        proof=json.loads(preservation.path.read_text());self.assertEqual(proof['stage'],'recovery-required')
        self.assertTrue(proof['differences']);self.assertEqual(proof['owners'][1]['fields'],self.originals[id(self.alien)])
        with self.assertRaisesRegex(ValueError,'Interrupted occult add'):guard.Preservation(self.fake,self.sim,8)

    def test_guard_records_preimages_before_native_code_and_restores_on_native_exception(self):
        def failed_native(*args):
            p=Path(self.temporary.name)/'OccultAdd/99-12-8.json'
            self.assertEqual(json.loads(p.read_text())['stage'],'adding')
            self.mutate_native();raise RuntimeError('native loot failed')
        patches={name:getattr(self.fake,name) for name in ('_form_map','_snapshot_siminfo_payload','_get_occult_flags',
            '_get_current_flags','_set_flags','_data_directory','_restore_siminfo_payload','services','_all_occults','_has_occult','_coerce_flags')}
        with patch.multiple(backend,**patches),patch.object(backend,'_add_occult_native',side_effect=failed_native):
            with self.assertRaisesRegex(RuntimeError,'native loot failed'):backend._add_occult(self.sim,8)
        self.assert_originals();self.assertEqual((self.sim.occult_types,self.sim.current_occult_types),(3,2))

    def test_mementos_are_separate_for_two_sims_in_one_save(self):
        a=guard.Preservation(self.fake,self.sim,8)
        other=Obj(id=22,skin_tone=400,blob=outfit(b'other'),occult_types=1,current_occult_types=1,occult_tracker=Obj(_sim_info_map={}))
        b=guard.Preservation(self.fake,other,8)
        self.assertNotEqual(a.path,b.path);self.assertEqual(json.loads(a.path.read_text())['sim_id'],'12')
        self.assertEqual(json.loads(b.path.read_text())['sim_id'],'22')

    def test_native_category_reordering_retains_every_outfit_byte_and_records_projection(self):
        first,second=outfit(b'unknown clothing',1),outfit(b'unknown accessory',2)
        self.sim.blob=second+first
        preservation=guard.Preservation(self.fake,self.sim,8)
        self.sim.blob=first+second
        self.fake._restore_siminfo_payload=lambda owner,rows:None
        preservation.restore(3,accepted=True)
        proof=json.loads(preservation.path.read_text())
        self.assertEqual(proof['stage'],'restored')
        self.assertEqual(proof['representation_changes'][0]['fields'],['__outfits__'])
        self.assertEqual(self.sim.blob,first+second)

    def test_native_appearance_flags_are_restored_separately_from_membership(self):
        for i,owner in enumerate([self.human,self.alien,self.sim]):owner.flags=i+1
        preservation=guard.Preservation(self.fake,self.sim,8)
        for owner in [self.human,self.alien,self.sim]:owner.flags=99
        preservation.restore(11,accepted=True)
        self.assertEqual([o.flags for o in [self.human,self.alien,self.sim]],[1,2,3])
        self.assertEqual(self.sim.occult_types,11)
        self.assertEqual([r['appearance_flags'] for r in json.loads(preservation.path.read_text())['owners']],[1,2,3])

    def test_membership_is_published_after_physical_setter_recalculates_native_mask(self):
        self.sim.flags=1
        preservation=guard.Preservation(self.fake,self.sim,16)
        restore=self.fake._restore_siminfo_payload
        def native_restore(owner,rows):
            restore(owner,rows)
            if 'flags' in rows:self.sim.occult_types=18
        self.fake._restore_siminfo_payload=native_restore
        self.sim.flags=9
        preservation.restore(19,accepted=True)
        self.assertEqual(self.sim.occult_types,19);self.assertEqual(self.sim.flags,1)

    def test_spellcaster_default_human_bit_normalization_requires_all_real_members(self):
        self.sim.occult_types=107
        preservation=guard.Preservation(self.fake,self.sim,16)
        def setter(sim,name,value):setattr(sim,name,value&~1 if name=='occult_types' and value&16 else value)
        self.fake._set_flags=setter
        preservation.restore(123,accepted=True)
        self.assertEqual(self.sim.occult_types,122)
        self.assertTrue(json.loads(preservation.path.read_text())['native_human_default_normalization'])

    def test_missing_actual_occult_does_not_pass_default_human_projection(self):
        self.sim.occult_types=107
        preservation=guard.Preservation(self.fake,self.sim,16)
        self.fake._has_occult=lambda tracker,kind:kind!=16
        self.fake._set_flags=lambda sim,name,value:setattr(sim,name,value&~1 if name=='occult_types' else value)
        with self.assertRaisesRegex(ValueError,'preimages retained'):preservation.restore(123,accepted=True)
