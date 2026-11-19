from pathlib import Path
import copy
import json
import sys
import unittest
from types import SimpleNamespace as Obj
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core import werewolf_defaults, form_appearance as appearance
import test_form_appearance as fixture


class WerewolfDefaultsTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.HumanWerewolfTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.backend,self.sim=self.f.backend,self.f.sim
        mapping={1:self.f.human,32:self.f.wolf};self.sim.occult_tracker._sim_info_map=mapping
        self.backend._get_occult_flags=lambda sim:sim.occult_types
        self.backend._set_flags=lambda sim,name,value:setattr(sim,name,value)
        for owner in [self.f.human,self.f.wolf,self.sim]:owner.pelt_layers=b'original-pelt'
        self.originals=[(o,appearance.packed(self.backend,o)) for o in [self.f.human,self.f.wolf,self.sim]]
        self.generated=Obj(**copy.deepcopy(self.f.wolf.__dict__));self.generated.physique='EA wolf';self.generated.skin_tone=555
        def generate(kind,generate_new):
            self.assertEqual((kind,generate_new),(32,True))
            self.f.human.pelt_layers=b'EA-generated-pelt';mapping[32]=self.generated
            return self.generated
        self.sim.occult_tracker._generate_sim_info=generate

    def check_originals(self):
        self.assertIs(self.sim.occult_tracker._sim_info_map[32],self.f.wolf)
        for owner,fields in self.originals:self.assertEqual(appearance.packed(self.backend,owner),fields)
        self.assertEqual((self.sim.occult_types,self.sim.current_occult_types,self.sim.fury,self.sim.perks),(33,32,75,(7,9)))

    def test_detached_ea_generation_restores_human_pelt_every_owner_and_map_identity(self):
        result=werewolf_defaults.prepare(self.backend,self.sim)
        self.assertEqual(appearance.decode(result['physique']),'EA wolf');self.check_originals()
        record=json.loads((Path(self.f.directory.name)/'werewolf_default_generation.json').read_text())
        self.assertEqual(record['stage'],'restored');self.assertTrue(record['accepted_preview'])

    def test_generator_error_restores_all_owners_before_raising(self):
        normal=self.sim.occult_tracker._generate_sim_info
        def fail(kind,generate_new):normal(kind,generate_new);self.sim.occult_types=99;raise RuntimeError('generation failed')
        self.sim.occult_tracker._generate_sim_info=fail
        with self.assertRaisesRegex(RuntimeError,'generation failed'):werewolf_defaults.prepare(self.backend,self.sim)
        self.check_originals()

    def test_aliasing_old_owner_is_refused_and_retains_originals(self):
        self.sim.occult_tracker._generate_sim_info=lambda kind,generate_new:self.f.wolf
        with self.assertRaisesRegex(ValueError,'distinct'):werewolf_defaults.prepare(self.backend,self.sim)
        self.check_originals()

    def test_interrupted_prior_generation_is_not_overwritten(self):
        path=Path(self.f.directory.name)/'werewolf_default_generation.json';path.write_text(json.dumps({'stage':'generating','original':'retained'}))
        with self.assertRaisesRegex(ValueError,'Interrupted'):werewolf_defaults.prepare(self.backend,self.sim)
        self.assertEqual(json.loads(path.read_text())['original'],'retained');self.check_originals()

    def test_recovery_preimage_is_written_before_native_generation(self):
        normal=self.sim.occult_tracker._generate_sim_info
        def generate(kind,generate_new):
            path=Path(self.f.directory.name)/'werewolf_default_generation.json'
            proof=json.loads(path.read_text());self.assertEqual(proof['stage'],'generating');self.assertEqual(len(proof['owners']),3)
            return normal(kind,generate_new)
        self.sim.occult_tracker._generate_sim_info=generate
        werewolf_defaults.prepare(self.backend,self.sim);self.check_originals()


if __name__=='__main__':unittest.main()
