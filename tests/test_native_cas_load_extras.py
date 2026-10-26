"""CAS loader completes absent fields from final, exactly owned appearances."""
import copy
import os
from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import native_cas_engine as engine, hybrid_persistence as p
from apex_core import form_appearance as a, occult_appearance_extension as ext
from apex_core import overlay_loader
from test_native_witch_persistence import NativeRecord
from test_outfit_snapshot import outfit


class LoadCapabilityTests(unittest.TestCase):
    def setUp(self):
        self.sim = Obj(id=123, household_id=99)
        self.backend = Obj(services=Obj(get_persistence_service=lambda: Obj(get_save_slot_proto_guid=lambda:77)))
        self.scope = dict(pid=os.getpid(), scope_id='b'*32, epochs={'123':'a'*64},
            load_identity=dict(household_id='99', save_guid='77'))
        self.enterContext(patch.object(engine, '_accepted_load_generation', return_value=17))

    def test_only_fresh_session_member_gets_complete_readback(self):
        doc = {'fresh':True, 'identity':dict(generation=17)}
        with patch.object(engine, '_LAYOUT_SCOPE', self.scope), patch.object(engine, 'returned_owners', return_value=doc) as read:
            self.assertIs(engine.load_owners(self.backend, self.sim), doc)
            read.assert_called_once_with(self.backend, self.sim, 'a'*64)

    def test_ordinary_and_other_sim_loads_do_not_query_native_graph(self):
        for scope in (None, dict(self.scope, epochs={'456':'b'*64})):
            with patch.object(engine, '_LAYOUT_SCOPE', scope), patch.object(engine, 'returned_owners') as read:
                self.assertIsNone(engine.load_owners(self.backend, self.sim)); read.assert_not_called()

    def test_foreign_save_household_process_completed_or_retiring_refuses(self):
        for changes in (dict(pid=os.getpid()+1), dict(load_identity=dict(household_id='88', save_guid='77')),
                        dict(load_identity=dict(household_id='99', save_guid='66')),
                        dict(completions={'123':{}}), dict(retirement_attempted=True), dict(load_identity=None)):
            with self.subTest(changes=changes), patch.object(engine, '_LAYOUT_SCOPE', dict(self.scope, **changes)), \
                    patch.object(engine, 'returned_owners') as read:
                with self.assertRaises(ValueError): engine.load_owners(self.backend, self.sim)
                read.assert_not_called()

    def test_changed_capability_during_read_refuses(self):
        def changed(*args):
            engine._LAYOUT_SCOPE = copy.deepcopy(self.scope)
            return {'fresh': True}
        with patch.object(engine, '_LAYOUT_SCOPE', self.scope), patch.object(engine, 'returned_owners', side_effect=changed):
            with self.assertRaises(ValueError): engine.load_owners(self.backend, self.sim)

    def test_cancel_or_unverified_acceptance_cannot_apply_new_paint(self):
        with patch.object(engine, '_LAYOUT_SCOPE', self.scope), \
                patch.object(engine, '_accepted_load_generation', return_value=None), \
                patch.object(engine, 'returned_owners') as read:
            self.assertIsNone(engine.load_owners(self.backend, self.sim));read.assert_not_called()

    def test_graph_changed_after_native_acceptance_is_not_loaded(self):
        with patch.object(engine, '_LAYOUT_SCOPE', self.scope), \
                patch.object(engine, 'returned_owners',return_value=dict(identity=dict(generation=18))):
            with self.assertRaisesRegex(ValueError,'changed after'):engine.load_owners(self.backend,self.sim)


class NativeAcceptanceProofTests(unittest.TestCase):
    def setUp(self):
        self.scope=dict(pid=os.getpid(),scope_id='b'*32,epochs={'123':'a'*64,'456':'c'*64})
        self.backend=Obj(__file__='matching-script')
        self.value=dict(ok=True,pid=os.getpid(),scope_id='b'*32,selection_enabled=True,
            household_acceptance=dict(verified=True,native_accepted=True,scope_id='b'*32,generations={'123':17,'456':23}))
        self.enterContext(patch.dict(sys.modules,{'paths':Obj(DLL_PATH='game-dlls')}))
    def call(self,value):
        with patch.object(overlay_loader,'native_cas_engine_control',return_value=value):
            return engine._accepted_load_generation(self.backend,self.scope,'123')
    def test_complete_real_native_acceptance_selects_exact_member_generation(self):
        self.assertEqual(self.call(self.value),17)
    def test_missing_unverified_cancelled_or_just_handled_results_grant_nothing(self):
        for proof in (None,{},dict(verified=False),dict(verified=False,cancelled=True),dict(handler_returned=True)):
            with self.subTest(proof=proof):self.assertIsNone(self.call(dict(self.value,household_acceptance=proof)))
    def test_verified_but_incomplete_stale_or_untyped_proof_refuses(self):
        for change in (dict(native_accepted=False),dict(scope_id='c'*32),dict(generations={'123':17}),
                       dict(generations={'123':True,'456':23}),dict(generations={'123':0,'456':23}),
                       dict(generations={'123':17,'456':23,'789':1})):
            value=copy.deepcopy(self.value);value['household_acceptance'].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):self.call(value)
        for change in (dict(pid=os.getpid()+1),dict(scope_id='c'*32),dict(selection_enabled=False)):
            with self.subTest(change=change),self.assertRaises(ValueError):self.call(dict(self.value,**change))


class LoadRecordTests(unittest.TestCase):
    def setUp(self):
        self.tracker = Obj(sim_info=Obj(id=123, household_id=99))
        self.backend = Obj()
        self.enterContext(patch.object(p, '_appearance_backend', return_value=self.backend))
        self.records = {}; self.doc = dict(identity=dict(scope_id='b'*32, generation=17), logical_owner_ids={}, owners=[])
        for kind in (1, 2, 4, 8, 16, 32, 64):
            record = NativeRecord(occult_type=kind, physique='shape-'+str(kind), skin_tone=kind,
                facial_attributes=b'unknown face', flags=0)
            record.outfits.ParseFromString(outfit(0, kind+5))
            record.MergeFromString(b'\xa0\x06\x7b')
            fields = p._record_payload(record, {})
            fields.update(pelt_layers=a.encode(b'Human paint' if kind==1 else bytes([kind])*7),
                          custom_texture=a.encode(2**64-kind))
            oid = ('active/' if kind==32 else 'native/')+str(kind)
            self.records[kind]=record; self.doc['logical_owner_ids'][str(kind)]=oid
            self.doc['owners'].append(dict(owner_id=oid,native_kind=kind,fields=fields))
        self.before = {kind: record.SerializeToString() for kind,record in self.records.items()}

    def call(self, doc=None):
        with patch.object(engine, 'load_owners', return_value=self.doc if doc is None else doc):
            return p._cas_load_records(self.tracker, self.records)

    def test_complete_human_paint_is_independent_and_all_native_bytes_retained(self):
        result = self.call()
        self.assertIsNot(result, self.records)
        for kind,record in result.items():
            self.assertEqual(ext._parts(record)[0], self.before[kind])
            self.assertEqual(self.records[kind].SerializeToString(), self.before[kind])
            extra=ext.read(record)
            self.assertEqual(a.decode(extra['pelt_layers']), b'Human paint' if kind==1 else bytes([kind])*7)
            self.assertEqual(a.decode(extra['custom_texture']), 2**64-kind)
        self.assertTrue(self.tracker._apex_native_cas_load_extras['verified'])
        self.assertFalse(self.tracker._apex_native_cas_load_extras['bank_read'])

    def test_any_core_edit_missing_owner_or_wrong_genus_refuses_the_whole_projection(self):
        for damage in ('skin','outfit','face','missing','duplicate','genus','extras'):
            doc=copy.deepcopy(self.doc)
            row=doc['owners'][-1]
            if damage=='skin':row['fields']['skin_tone']=a.encode(999)
            if damage=='outfit':row['fields']['__outfits__']=a.encode(('protobuf',outfit(1,999)))
            if damage=='face':row['fields']['facial_attributes']=a.encode(b'another face')
            if damage=='missing':del doc['logical_owner_ids']['1']
            if damage=='duplicate':doc['owners'].append(copy.deepcopy(row))
            if damage=='genus':row['native_kind']=1
            if damage=='extras':del row['fields']['pelt_layers']
            with self.subTest(damage=damage):
                self.assertIs(self.call(doc),self.records)
                self.assertFalse(self.tracker._apex_native_cas_load_extras['verified'])
                self.assertEqual({k:r.SerializeToString() for k,r in self.records.items()},self.before)

    def test_foreign_extension_is_not_overwritten_even_when_core_matches(self):
        self.records[64].MergeFromString(ext._varint(ext.FIELD<<3|2)+b'\x07foreign')
        original=self.records[64].SerializeToString()
        self.assertIs(self.call(),self.records)
        self.assertEqual(self.records[64].SerializeToString(),original)

    def test_no_native_capability_does_not_modify_existing_saved_carrier(self):
        ext.write(self.records[1],dict(pelt_layers=a.encode(b'saved actual paint')))
        original=self.records[1].SerializeToString()
        with patch.object(engine,'load_owners',return_value=None):
            self.assertIs(p._cas_load_records(self.tracker,self.records),self.records)
        self.assertEqual(self.records[1].SerializeToString(),original)

    def test_decoder_sets_only_omitted_fields_without_waiting_for_a_guard(self):
        record=self.call()[1]
        owner=Obj(pelt_layers=b'wrong beast template',custom_texture=0,skin_tone=91,
                  outfit=b'unrelated outfit',gameplay_progress=12345)
        p._load_record_extras(self.tracker,owner,record)
        self.assertEqual(vars(owner),dict(pelt_layers=b'Human paint',custom_texture=2**64-1,
            skin_tone=91,outfit=b'unrelated outfit',gameplay_progress=12345))

    def test_invalid_carrier_is_observable_without_discarding_a_sim(self):
        record=self.records[1]
        record.MergeFromString(ext._varint(ext.FIELD<<3|2)+b'\x07foreign')
        owner=Obj(pelt_layers=b'previous',custom_texture=3)
        p._load_record_extras(self.tracker,owner,record)
        self.assertEqual(vars(owner),dict(pelt_layers=b'previous',custom_texture=3))
        self.assertFalse(self.tracker._apex_native_load_extension_failure['extension_applied'])


if __name__ == '__main__': unittest.main()
