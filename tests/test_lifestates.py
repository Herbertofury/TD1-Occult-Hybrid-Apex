from pathlib import Path
import sys
import threading
from types import SimpleNamespace as Obj
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import lifestates


class LifeStateCatalogTests(unittest.TestCase):
    def setUp(self):
        self.owned_traits = set()
        self.owned_buffs = set()
        self.sim = Obj(id=123, occult_tracker=Obj(), is_ghost=False,
            trait_tracker=Obj(has_trait=lambda t: t in self.owned_traits),
            has_buff=lambda b: b in self.owned_buffs)
        self.service = Obj(is_imaginary_friend=lambda _: False)
        self.backend = Obj(_APEX_GAME_THREAD_IDENT=threading.current_thread().ident,
            _get_sim_info_by_id=lambda sid: self.sim if str(sid)=='123' else None,
            _get_trait=lambda i: 'trait:'+str(i), _coerce_flags=lambda f: f,
            _form_map=lambda _: {1: Obj(), 2: Obj(), 4: Obj()},
            _has_occult=lambda _t,k: k in (2,4), _get_current_flags=lambda _: 2,
            sims4=Obj(resources=Obj(Types=Obj(BUFF=1))),
            services=Obj(get_instance_manager=lambda _: Obj(get=lambda i: 'buff:'+str(i)),
                         get_imaginary_friend_service=lambda: self.service))

    def row(self, state):
        result = lifestates.catalog(self.backend, self.sim)
        return next(row for row in result['rows'] if row['id']==state)

    def test_catalog_preserves_each_native_membership_instead_of_selecting_one(self):
        result = lifestates.catalog(self.backend,self.sim)
        self.assertEqual({r['id'] for r in result['rows'] if r['member']}, {'HUMAN','ALIEN','VAMPIRE'})
        self.assertFalse(result['appearance_modified'])
        self.assertFalse(result['gameplay_modified'])

    def test_native_service_owns_imaginary_identity_not_a_costume_trait(self):
        self.owned_traits.add('trait:453528')
        row = self.row('IMAGINARY_FRIEND')
        self.assertFalse(row['member'])
        self.assertEqual(row['observed']['trait_ids'], ['453528'])

    def test_native_friend_child_doll_and_real_status_are_retained_separately(self):
        self.service = Obj(is_imaginary_friend=lambda _: True,
            get_imaginary_friend_status=lambda _: 'REAL', get_child_sim=lambda _: 7788,
            get_imaginary_friend_doll=lambda _: 554433)
        row = self.row('IMAGINARY_FRIEND')
        self.assertTrue(row['member'])
        self.assertEqual(row['observed']['service'],dict(supported=True,member=True,status='REAL',child_sim_id='7788',doll_object_id='554433'))
        self.assertIn('real',row['variants'])

    def test_unavailable_service_is_unknown_and_never_fabricates_a_sim(self):
        self.backend.services.get_imaginary_friend_service = lambda: None
        row=self.row('IMAGINARY_FRIEND')
        self.assertIsNone(row['member'])
        self.assertFalse(row['observed']['service']['supported'])

    def test_ghost_uses_the_actual_death_tracker_projection(self):
        self.sim.is_ghost=True
        self.assertTrue(self.row('GHOST')['member'])

    def test_native_servo_and_cloned_robot_have_distinct_evidence(self):
        for trait in ('trait:218444','trait:17914856899346771710'):
            self.owned_traits={trait}
            row=self.row('SERVO')
            self.assertTrue(row['member'])
            self.assertIsNone(row['native_flags'])
            self.assertEqual(row['observed']['trait_ids'],[trait.split(':')[1]])

    def test_buffs_resolve_the_real_tuning_object_before_membership_queries(self):
        self.owned_buffs.add('buff:162844')
        row=self.row('PLANTSIM')
        self.assertTrue(row['member'])
        self.assertEqual(row['observed']['buff_ids'],['162844'])

    def test_all_named_special_states_have_variants_without_claiming_ea_enum_support(self):
        for state in lifestates.SPECIAL:
            row=self.row(state)
            self.assertGreaterEqual(len(row['variants']),2)
            self.assertFalse(row['native_membership_switch_supported'])
        for invalid in (True,1,'not_a_lifestate','../Ghost'):
            with self.assertRaises(ValueError):lifestates.name(invalid)
