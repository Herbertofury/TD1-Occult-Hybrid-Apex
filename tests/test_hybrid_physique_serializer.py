from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import sim_data


class HybridPhysiqueSerializerTests(unittest.TestCase):
    def setUp(self):
        test = self; self.calls = []; self.stats = []
        class NativeSim:
            def _set_fit_fat(self):
                test.stats.append(self)
                self.physique = 'shared fitness physique'
            def save_sim(self, for_cloning=False, full_service=True):
                test.calls.append((self, for_cloning, full_service))
                self._set_fit_fat()
                if getattr(self, 'fail', False):raise RuntimeError('native failed')
                if getattr(self, 'other', None) is not None:self.other._set_fit_fat()
                return Obj(physique=self.physique, opaque=b'complete unknown save data')
        self.cls = NativeSim
        self.sim = NativeSim(); self.sim._base = Obj(); self.sim.current_occult_types = 2
        self.sim.physique = 'independent edited alien body'
        self.sim.occult_tracker = Obj(_sim_info=self.sim,
            _sim_info_map={k:Obj(_base=Obj()) for k in (1,2,4)})
        self.assertTrue(sim_data.install_hybrid_serializer(self.sim))

    def test_normal_save_preserves_edited_form_in_runtime_and_root_native_record(self):
        record = self.sim.save_sim(for_cloning=False, full_service=True)
        self.assertEqual(record.physique, 'independent edited alien body')
        self.assertEqual(self.sim.physique, record.physique)
        self.assertEqual(record.opaque, b'complete unknown save data')
        self.assertEqual(self.stats, [])
        self.assertEqual(self.calls, [(self.sim,False,True)])
        self.assertEqual(sim_data._APPEARANCE_READS.owners, ())

    def test_gameplay_fitness_and_another_sim_stay_native(self):
        self.sim._set_fit_fat()
        self.assertEqual(self.sim.physique, 'shared fitness physique')
        other = self.cls(); other.physique = 'ordinary physique'
        self.sim.other = other; self.sim.physique = 'new edited alien body'
        self.sim.save_sim()
        self.assertEqual(self.sim.physique, 'new edited alien body')
        self.assertEqual(other.physique, 'shared fitness physique')
        self.assertEqual(self.stats, [self.sim,other])

    def test_single_native_pair_and_aliased_or_missing_ownership_keep_native_serialization(self):
        for setup in ('pair','alias','owner'):
            with self.subTest(setup=setup):
                if setup=='pair':self.sim.occult_tracker._sim_info_map={1:Obj(_base=Obj()),2:Obj(_base=Obj())}
                elif setup=='alias':self.sim.occult_tracker._sim_info_map={1:Obj(_base=Obj()),2:Obj(_base=self.sim._base),4:Obj(_base=Obj())}
                else:self.sim.occult_tracker._sim_info=Obj()
                self.sim.physique='new body'
                self.assertEqual(self.sim.save_sim().physique,'shared fitness physique')

    def test_native_exception_releases_scope_before_later_gameplay_update(self):
        self.sim.fail=True
        with self.assertRaisesRegex(RuntimeError,'native failed'):self.sim.save_sim()
        self.assertEqual(sim_data._APPEARANCE_READS.owners, ())
        self.sim._set_fit_fat()
        self.assertEqual(self.sim.physique,'shared fitness physique')
        self.assertEqual(len(self.calls),1)

    def test_install_idempotent_and_clone_contract_preserved(self):
        wrapped=self.cls.save_sim
        self.assertTrue(sim_data.install_hybrid_serializer(self.sim))
        self.assertIs(self.cls.save_sim,wrapped)
        record=self.sim.save_sim(for_cloning=True,full_service=False)
        self.assertEqual(record.physique,'independent edited alien body')
        self.assertEqual(self.calls,[(self.sim,True,False)])


if __name__=='__main__':unittest.main()
