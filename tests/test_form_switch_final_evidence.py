"""Compare complete switch behavior while removing duplicate final evidence work."""
import copy
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'Source'),str(ROOT/'tests')]
from apex_core import form_bank, form_appearance as appearance
import test_form_switch_all_owners as owner_fixtures


def baseline():
    """Reconstruct only the previous duplicate evidence calls for comparison."""
    source=(ROOT/'Source/apex_core/form_bank.py').read_text(encoding='utf-8')
    replacements=[
        ("        # These newly encoded captures are detached invocation-local values.\n"
         "        # Reuse their evidence only; every native read and expected comparison\n"
         "        # remains at its original transaction boundary.\n"
         "        final_stored_hashes = _switch_hashes(final_stored)\n"
         "        if final_stored_hashes != _switch_hashes(expected):",
         "        if _switch_hashes(final_stored) != _switch_hashes(expected):"),
        ("        final_active_evidence = appearance.fingerprint(final_active)\n"
         "        if final_active_evidence != appearance.fingerprint(desired_active):",
         "        if appearance.fingerprint(final_active) != appearance.fingerprint(desired_active):"),
        ("pending['verified_stored_hashes'] = dict(final_stored_hashes)",
         "pending['verified_stored_hashes'] = _switch_hashes(final_stored)"),
        ("pending['verified_active_hash'] = final_active_evidence['appearance_sha256']",
         "pending['verified_active_hash'] = appearance.fingerprint(final_active)['appearance_sha256']"),
        ("stored_owner_hashes=dict(final_stored_hashes)","stored_owner_hashes=_switch_hashes(final_stored)"),
        ("appearance=final_active_evidence)","appearance=appearance.fingerprint(final_active))")]
    for before,after in replacements:
        if source.count(before)!=1:raise AssertionError('Evidence fixture boundary changed')
        source=source.replace(before,after,1)
    module=types.ModuleType('apex_core.final_evidence_baseline')
    module.__package__='apex_core'
    exec(compile(source,'<duplicate-evidence-baseline>','exec'),module.__dict__)
    return module


def scrub(value):
    if isinstance(value,dict):return {key:scrub(item) for key,item in value.items() if key!='request_id' and key!='switch_request_id'}
    if isinstance(value,list):return [scrub(item) for item in value]
    return value


def mutable_ids(value):
    out=set()
    if isinstance(value,(dict,list)):
        out.add(id(value))
        for item in value.values() if isinstance(value,dict) else value:out.update(mutable_ids(item))
    return out


class FinalEvidenceReuseTests(unittest.TestCase):
    def run_switch(self, proposed, scenario='success'):
        test=owner_fixtures.FormSwitchAllOwnerTests('test_all_seven_and_distinct_latest_source_survive_intermediate_human')
        test.setUp();self.addCleanup(test.doCleanups)
        module=form_bank if proposed else baseline()
        switch=module.switch;real_save=module.save
        real_packed=appearance.packed;real_fingerprint=appearance.fingerprint
        real_restore=test.backend._restore_siminfo_payload
        real_snapshots=module._switch_snapshots
        events=[];fingerprints=[];captured=[];snapshot_calls=[0];native_calls=[0];commit_failed=[False]

        def packed(backend, owner):
            events.append(('native-read',owner.id))
            value=real_packed(backend,owner);captured.append(value);return value

        def fingerprint(fields):
            fingerprints.append(fields)  # Hold exact objects; no object-ID reuse.
            return real_fingerprint(fields)

        def restore(owner, fields):
            events.append(('native-write',owner.id,tuple(sorted(fields))))
            value=real_restore(owner,fields)
            if scenario=='collateral' and owner is test.sim:test.forms[1].physique='later active write damaged earlier Human'
            if scenario=='rejected' and owner is test.forms[1]:owner.physique='setter ignored intended physique'
            return value

        def save(path, data):
            row=data['records'][test.key];pending=row.get('switch_pending')
            state=pending['state'] if pending else 'completed'
            events.append(('durable-save',state))
            if scenario=='issued-storage-error' and state=='native-operation-issued':raise OSError('fixture issued write failed')
            if scenario=='commit-storage-error' and state=='completed' and not commit_failed[0]:
                commit_failed[0]=True
                test.forms[2].custom_texture=b'fresh failure-capture texture'
                raise OSError('fixture final commit failed')
            return real_save(path,data)

        def snapshots(backend, owners):
            snapshot_calls[0]+=1
            value=real_snapshots(backend,owners)
            if snapshot_calls[0]==3 and scenario=='malformed-final':
                value['1']['voice_pitch']={'kind':'value','value':float('nan')}
            return value

        def native():
            native_calls[0]+=1;events.append(('native-operation',))
            if scenario=='raised':return test.operation(raises=True)
            if scenario=='refused':return test.operation(refused=True)
            if scenario=='replacement':
                test.forms[64]=copy.deepcopy(test.forms[64]);test.forms[64].id+=10
                test.sim.current_occult_types=64
                return {'ok':True}
            return test.operation(corrupt_source=True)

        with patch.object(appearance,'packed',side_effect=packed),patch.object(appearance,'fingerprint',side_effect=fingerprint),\
                patch.object(module,'save',side_effect=save),patch.object(module,'_switch_snapshots',side_effect=snapshots),\
                patch.object(test.backend,'_restore_siminfo_payload',side_effect=restore),\
                patch.object(test.backend,'_resend_all_visuals',side_effect=lambda _:events.append(('resend',))):
            try:result=switch(test.backend,test.sim,64,native);error=None
            except Exception as failure:result=None;error=(type(failure).__name__,str(failure))
        record=test.record()
        return dict(result=scrub(result),error=error,events=events,record=scrub(record),
            native_calls=native_calls[0],fingerprints=len(fingerprints),test=test,
            captured=captured, module=module)

    def assert_equivalent(self, scenario):
        before=self.run_switch(False,scenario);after=self.run_switch(True,scenario)
        for key in ('result','error','events','record','native_calls'):
            self.assertEqual(before[key],after[key],(scenario,key))
        return before,after

    def test_success_removes_exactly_two_fingerprints_per_final_owner(self):
        before,after=self.assert_equivalent('success')
        self.assertEqual(before['fingerprints']-after['fingerprints'],16) # 7 stored + distinct Live, twice each.
        self.assertEqual(before['native_calls'],1)
        self.assertEqual([e for e in after['events'] if e[0]=='durable-save'],
            [('durable-save','captured'),('durable-save','native-operation-issued'),('durable-save','completed')])

    def test_failure_paths_preserve_every_native_read_write_save_and_original_error(self):
        for scenario in ('collateral','rejected','raised','refused','replacement','issued-storage-error','malformed-final'):
            with self.subTest(scenario=scenario):self.assert_equivalent(scenario)

    def test_failed_commit_still_captures_fresh_native_failure_state(self):
        before,after=self.assert_equivalent('commit-storage-error')
        self.assertEqual(after['error'],('OSError','fixture final commit failed'))
        pending=after['record']['switch_pending']
        self.assertEqual(appearance.decode(pending['returned_stored']['2']['custom_texture']),b'fresh failure-capture texture')
        self.assertEqual(after['native_calls'],1)
        self.assertIsNotNone(pending)

    def test_returned_receipt_mutation_does_not_mutate_durable_evidence(self):
        after=self.run_switch(True)
        result=after['result'];expected=copy.deepcopy(after['record']['switch_history'][-1]['verified_stored_hashes'])
        result['stored_owner_hashes']['1']='0'*64
        result['appearance']['field_sha256']['physique']='0'*64
        self.assertEqual(after['test'].record()['switch_history'][-1]['verified_stored_hashes'],expected)
        self.assertNotEqual(appearance.evidence(after['test'].backend,after['test'].sim)['field_sha256']['physique'],'0'*64)

    def test_packed_trees_detach_nested_native_mutables_and_every_capture(self):
        after=self.run_switch(True);owner=after['test'].forms[2]
        owner.parts_custom_tattoos=[{'layers':[1,2,{'key':3}]}]
        packed=appearance.packed(after['test'].backend,owner)
        native_mutables=mutable_ids(owner.parts_custom_tattoos)
        self.assertTrue(native_mutables.isdisjoint(mutable_ids(packed)))
        other=appearance.packed(after['test'].backend,owner)
        self.assertTrue(mutable_ids(packed).isdisjoint(mutable_ids(other)))
        before=copy.deepcopy(packed);owner.parts_custom_tattoos[0]['layers'][2]['key']=99
        self.assertEqual(packed,before)

    def test_no_cross_request_evidence_reuse_on_same_sim_owner_or_slot(self):
        after=self.run_switch(True);test=after['test'];module=after['module']
        test.forms[2].physique='new second-request inactive Alien edit'
        test.forms[2].custom_texture=b'new second-request opaque texture'
        expected=appearance.packed(test.backend,test.forms[2])
        calls=[]
        def native():
            calls.append(2);test.sim.current_occult_types=2
            test.backend._restore_siminfo_payload(test.sim,appearance.payload(expected));return {'ok':True}
        result=module.switch(test.backend,test.sim,2,native)
        self.assertEqual(calls,[2])
        self.assertEqual(result['appearance'],appearance.fingerprint(expected))
        self.assertEqual(appearance.packed(test.backend,test.sim),expected)
        self.assertFalse(any('final_stored_hashes' in key or 'final_active_evidence' in key for key in module.__dict__))



if __name__=='__main__':unittest.main(verbosity=2)
