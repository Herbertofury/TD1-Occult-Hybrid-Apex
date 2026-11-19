"""Reject real phenotype loss and exercise isolated native CASP staging."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from types import SimpleNamespace as Obj
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import growth_parts, form_appearance as appearance
from test_genetics_snapshot import genetic, part, message


class MissingGrowthPartsTests(unittest.TestCase):
    def setUp(self):
        self.hair = part(100, 2)
        self.current = [part(200 + n, 78 + n) for n in range(4)]
        self.preferred = [part(300 + n, 78 + n) for n in range(4)]
        self.expected = genetic([self.hair] + self.current, self.preferred, message(98, b'unknown'), message(99, b'future'))
        self.filtered = genetic([self.hair], self.preferred, message(98, b'unknown'), message(99, b'future'))

    def test_missing_distinct_swatches_keep_complete_genetics_identity(self):
        rows = growth_parts.missing_growth_parts(self.expected, self.filtered)
        self.assertEqual([(r['part_id'], r['body_type']) for r in rows], [(200+n, 78+n) for n in range(4)])
        self.assertNotEqual(appearance.fingerprint({'genetic_data': appearance.encode(self.expected)}),
                            appearance.fingerprint({'genetic_data': appearance.encode(self.filtered)}))

    def test_identical_growth_projection_needs_no_native_casp_call(self):
        duplicate = genetic([self.hair] + self.preferred, self.preferred)
        filtered = genetic([self.hair], self.preferred)
        self.assertEqual(growth_parts.missing_growth_parts(duplicate, filtered), [])

    def test_unknown_bytes_or_non_growth_parts_never_authorize_restoration(self):
        for changed in (genetic([self.hair], self.preferred, b'', message(99, b'future')),
                        genetic([], self.preferred, message(98, b'unknown'), message(99, b'future')),
                        genetic([self.hair], [], message(98, b'unknown'), message(99, b'future')),
                        genetic([part(999, 2)], self.preferred, message(98, b'unknown'), message(99, b'future'))):
            with self.assertRaises(ValueError):growth_parts.missing_growth_parts(self.expected, changed)

    def test_reorder_or_two_current_parts_in_one_slot_are_ambiguous(self):
        reordered = genetic(self.current + [self.hair], self.preferred, message(98, b'unknown'), message(99, b'future'))
        with self.assertRaises(ValueError):growth_parts.missing_growth_parts(self.expected, reordered)
        duplicate = genetic([self.hair, part(201, 78), part(202, 78)], self.preferred)
        with self.assertRaises(ValueError):growth_parts.missing_growth_parts(duplicate, genetic([self.hair], self.preferred))


class NativeGrowthPreparationTests(unittest.TestCase):
    def setUp(self):MissingGrowthPartsTests.setUp(self)
    def run_probe(self, behavior=None):
        with tempfile.TemporaryDirectory() as directory:
            def owner(identity):
                return Obj(id=identity, flags=63, genetic_data=self.expected, _base=Obj(
                    current_occult_types=2, occult_types=3, base_trait_ids=[10],outfits=b'\x0a\x04\x08\x01\x10\x00'),
                    gender=8192, age=16, species=1, first_name='Apex', last_name='Test',
                    breed_name='', full_name_key=0, breed_name_key=0, household_id=77)
            sim, stored = owner(11), owner(12)
            detached = []
            def construct(**kwargs):
                value=owner(13+len(detached));detached.append(value);return value
            sim.occult_tracker = Obj()
            mapping = {2:stored}
            before = dict(genetic_data=appearance.encode(self.expected), __outfits__=appearance.encode(('protobuf', b'\x0a\x04\x08\x01\x10\x00')))
            def packed(backend, target):
                return dict(before, genetic_data=appearance.encode(target.genetic_data),__outfits__=appearance.encode(('protobuf',target._base.outfits)))
            backend = Obj(_form_map=lambda tracker:mapping, _coerce_flags=int,
                _data_directory=lambda:directory, _restore_siminfo_payload=lambda target, values:setattr(target,'genetic_data',self.filtered))
            def native(source, destination, identity, toggle, random, update_genetics, seed, conflict):
                src=next(o for o in detached+[stored] if o._base is source)
                dst=next(o for o in detached if o._base is destination)
                self.assertIsNot(src,dst)
                self.assertIsNot(destination,stored._base)
                self.assertEqual((toggle, random, update_genetics, seed, conflict), (False, False, True, 0, True))
                if behavior:return behavior(sim,stored,dst)
                # Model EA's source-copy semantics: a fixed original source
                # loses earlier slot edits even if the destination kept them.
                raw=next(v for n,w,v,c in growth_parts.genetics._fields(src.genetic_data) if n==5)
                ids={next(v for n,w,v,c in growth_parts.genetics._fields(row) if n==1)
                     for n,w,row,c in growth_parts.genetics._parts(raw) if n==1}
                ids.add(identity)
                dst.genetic_data=genetic([self.hair]+[row for n,row in enumerate(self.current) if 200+n in ids],
                    self.preferred,message(98,b'unknown'),message(99,b'future'))
                dst._base.outfits=b'\x0a\x04\x08\x02\x10\x00'
                return True
            function = Mock(side_effect=native)
            modules={'sims':Obj(), 'sims.sim_info_base_wrapper':Obj(SimInfoBaseWrapper=construct),
                     'cas':Obj(), 'cas.cas':Obj(set_caspart=function,get_caspart_bodytype=lambda p:78+p-200)}
            with patch.dict(sys.modules,modules), patch.object(growth_parts.appearance,'packed',side_effect=packed), \
                 patch('apex_core.household_io.context'), patch('apex_core.native_occult_context.read',return_value={'context':'unchanged'}):
                try:result=growth_parts.prepare(backend,sim,dict(household_id='77',save_guid='88',form_flags=2))
                except ValueError as error:result=error
            journal=json.loads(next(Path(directory).glob('growth-probe-*.json')).read_text())
            return result,journal,function.call_count

    def test_native_staging_preserves_original_owners_and_never_applies_to_real_sim(self):
        result,journal,calls=self.run_probe()
        self.assertTrue(result['prepared_genetics_verified']);self.assertFalse(result['real_sim_apply_attempted'])
        self.assertTrue(journal['all_real_owners_unchanged']);self.assertEqual(calls,1)
        self.assertEqual(journal['complete_native_source_id'],'12')
        self.assertEqual(journal['stage'],'verified')
        self.assertTrue(journal['prepared_appearance_verified'])
        self.assertEqual(journal['staged_fields'],journal['fields'])

    def test_native_rejection_has_one_attempt_and_retains_complete_source(self):
        result,journal,calls=self.run_probe(lambda *a:False)
        self.assertIsInstance(result,ValueError);self.assertEqual(calls,1)
        self.assertEqual(journal['fields']['genetic_data'],appearance.encode(self.expected))
        self.assertTrue(journal['all_real_owners_unchanged']);self.assertEqual(journal['stage'],'rejected')

    def test_native_source_mutation_is_not_reported_as_a_read_only_success(self):
        def mutate(sim,stored,staged):stored.genetic_data=self.filtered;return False
        result,journal,calls=self.run_probe(mutate)
        self.assertIn('existing owner',str(result));self.assertFalse(journal['all_real_owners_unchanged'])
        self.assertFalse(journal['real_sim_apply_attempted']);self.assertEqual(calls,1)

    def test_detached_outfit_write_losing_genetics_refuses_before_real_apply(self):
        with patch.object(growth_parts,'_restore_outfits',side_effect=lambda target,fields:setattr(target,'genetic_data',self.filtered)):
            result,journal,calls=self.run_probe()
        self.assertIn('Detached outfit restoration',str(result));self.assertEqual(calls,1)
        self.assertFalse(journal['real_sim_apply_attempted']);self.assertTrue(journal['all_real_owners_unchanged'])
        self.assertFalse(journal['prepared_appearance_verified'])


class NativeGrowthRestoreTests(unittest.TestCase):
    def setUp(self):MissingGrowthPartsTests.setUp(self)

    def run_restore(self, behavior=None, source_matches=True, source_kind=2, source_outfits_match=True, resend_corrupts=False,
                    outfit_side_effect=False, outfit_restore_corrupts=False):
        with tempfile.TemporaryDirectory() as directory:
            live = Obj(id=11, flags=63, genetic_data=self.expected if source_matches else self.filtered,
                       _base=Obj(current_occult_types=source_kind), occult_tracker=Obj())
            owner = Obj(id=12, flags=63, genetic_data=self.filtered, _base=Obj(current_occult_types=2))
            staged = Obj(_base=Obj())
            mapping = {2:owner}
            fields = dict(genetic_data=appearance.encode(self.expected), __outfits__=appearance.encode(('protobuf',b'\x0a\x04\x08\x01\x10\x00')))
            live._base.outfits=b'\x0a\x04\x08\x01\x10\x00' if source_outfits_match else b'\x0a\x04\x08\x02\x10\x00'
            owner._base.outfits=b'\x0a\x04\x08\x01\x10\x00'
            if resend_corrupts:
                owner.resend_outfits=lambda:setattr(owner,'genetic_data',self.filtered)
            def packed(backend, target):return dict(fields, genetic_data=appearance.encode(target.genetic_data),__outfits__=appearance.encode(('protobuf',target._base.outfits)))
            backend = Obj(_form_map=lambda tracker:mapping, _data_directory=lambda:directory)
            def native(source, destination, identity, toggle, random, genetics, seed, conflict):
                self.assertIs(source,live._base);self.assertIs(destination,owner._base)
                self.assertEqual((identity,toggle,random,genetics,seed,conflict),(200,False,False,True,0,True))
                if behavior:return behavior(live,owner)
                owner.genetic_data=self.expected
                if outfit_side_effect:owner._base.outfits=b'\x0a\x04\x08\x02\x10\x00'
                return True
            function=Mock(side_effect=native)
            modules={'cas':Obj(), 'cas.cas':Obj(set_caspart=function)}
            def stage(*args):
                args[4]['complete_native_source_id']='11'
                args[4]['prepared_appearance_verified']=True
                return staged,[dict(part_id=200,body_type=78)]
            original_restore=growth_parts._restore_outfits
            def restore_outfits(target,desired):
                original_restore(target,desired)
                if outfit_restore_corrupts:target.genetic_data=self.filtered
            with patch.dict(sys.modules,modules), patch.object(appearance,'packed',side_effect=packed), \
                 patch('apex_core.native_occult_context.read',return_value={'context':'unchanged'}), \
                 patch.object(growth_parts,'_stage',side_effect=stage), \
                 patch.object(growth_parts,'_restore_outfits',side_effect=restore_outfits):
                try:result=growth_parts.restore(backend,live,owner,fields)
                except ValueError as error:result=error
            journal=json.loads(next(Path(directory).glob('growth-restore-*.json')).read_text())
            return result,journal,function.call_count

    def test_exact_native_casp_transfer_preserves_the_other_owner_and_requires_full_readback(self):
        result,journal,calls=self.run_restore()
        self.assertIs(result,True);self.assertEqual(calls,1)
        self.assertEqual(journal['stage'],'verified');self.assertTrue(journal['all_unselected_owners_unchanged'])
        self.assertTrue(journal['real_sim_apply_attempted'])
        self.assertEqual(journal['apply_method'],'set_caspart')

    def test_incomplete_or_different_kind_source_never_authorizes_real_apply(self):
        for values in ({'source_matches':False},{'source_kind':4},{'source_outfits_match':False}):
            with self.subTest(values=values):
                result,journal,calls=self.run_restore(**values)
                self.assertIn('source is unavailable',str(result));self.assertEqual(calls,0)
                self.assertFalse(journal['real_sim_apply_attempted'])

    def test_distributor_resend_side_effect_cannot_report_complete_success(self):
        result,journal,calls=self.run_restore(resend_corrupts=True)
        self.assertIn('readback',str(result));self.assertEqual(calls,1)
        self.assertEqual(journal['observed_fields']['genetic_data'],appearance.encode(self.filtered))

    def test_casp_outfit_side_effect_is_repaired_without_reassigning_genetics(self):
        result,journal,calls=self.run_restore(outfit_side_effect=True)
        self.assertIs(result,True);self.assertEqual(calls,1)
        self.assertEqual(journal['fields_before_outfit_restore']['genetic_data'],journal['expected_fields']['genetic_data'])

    def test_outfit_repair_losing_genetics_never_reports_success(self):
        result,journal,calls=self.run_restore(outfit_side_effect=True,outfit_restore_corrupts=True)
        self.assertIn('readback',str(result));self.assertEqual(calls,1)
        self.assertEqual(journal['observed_fields']['genetic_data'],appearance.encode(self.filtered))

    def test_native_readback_rejection_is_not_replayed_and_retains_observed_bytes(self):
        result,journal,calls=self.run_restore(lambda *a:True)
        self.assertIn('readback',str(result));self.assertEqual(calls,1)
        self.assertEqual(journal['stage'],'rejected')
        self.assertEqual(journal['observed_fields']['genetic_data'],appearance.encode(self.filtered))
        self.assertEqual(journal['expected_fields']['genetic_data'],appearance.encode(self.expected))

    def test_native_error_keeps_intent_and_original_preimages_with_one_attempt(self):
        def fail(*a):raise ValueError('Native CASP error')
        result,journal,calls=self.run_restore(fail)
        self.assertIn('Native CASP error',str(result));self.assertEqual(calls,1)
        self.assertTrue(journal['real_sim_apply_attempted']);self.assertEqual(journal['stage'],'rejected')
        self.assertEqual(len(journal['original_owners']),2)

    def test_an_unselected_owner_mutation_cannot_report_success(self):
        def mutate(live,owner):owner.genetic_data=self.expected;live.genetic_data=self.filtered;return True
        result,journal,calls=self.run_restore(mutate)
        self.assertIn('another owner',str(result));self.assertEqual(calls,1)
        self.assertEqual(journal['stage'],'rejected')


if __name__=='__main__':unittest.main()
