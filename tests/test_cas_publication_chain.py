"""Actual compiled artifacts: complete raw rollback and adversarial refusals."""
from pathlib import Path
import copy,json,os,sys,unittest
H=Path(__file__).resolve().parents[1];R=next(p for p in (H,*H.parents) if(p/'tools/cas_grid_featured.py').is_file())
sys.path[:0]=[str(H/'tools'),str(R/'tools')]
import cas_grid_publication as c
import cas_ui_build as build


class CompiledTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows={}
        fixture=os.environ.get('APEX_CAS_PUBLICATION_FIXTURE_ROOT')
        if fixture is None:raise unittest.SkipTest('Explicit independently compiled publication fixtures not supplied')
        fixture=Path(fixture).resolve()
        if not fixture.is_dir():raise ValueError('Supplied publication fixture directory is unavailable')
        for name,owner in(('12272E1AC0C1F8E2',c.GRID),('89D13757C58C2E05',c.GRID),('main',c.MAIN)):
            root=fixture/name
            cls.rows[name]=(owner,json.loads((root/'contract.json').read_text()),(root/'final.swf').read_bytes(),(root/'baseline.swf').read_bytes())
    def row(self):return self.rows['12272E1AC0C1F8E2']
    def test_both_providers_and_main_restore_exact_verified_featured_bytes(self):
        for name,(owner,contract,final,base)in self.rows.items():
            with self.subTest(name=name):
                self.assertTrue(c.verify(contract,final,owner))
                self.assertEqual(c.reconstruct(final,contract['publication_trace_contract']['rollback'],owner),base)
    def test_missing_partial_stale_source_pins_refuse(self):
        owner,contract,final,_=self.row()
        for mode in('missing','partial','stale'):
            altered=copy.deepcopy(contract);proof=altered['publication_trace_contract']
            if mode=='missing':proof.pop('source_sha256')
            elif mode=='partial':proof['source_sha256'].pop(c.SOURCES[-1])
            else:proof['source_sha256'][c.SOURCES[0]]='0'*64
            altered['postproof_sha256']=c.comm.contract_digest(proof)
            with self.assertRaises(ValueError,msg=mode):c.verify(altered,final,owner)
    def test_missing_and_downgraded_complete_prior_refuse_even_rehashed(self):
        owner,contract,final,_=self.row()
        for mode in('missing','downgraded'):
            altered=copy.deepcopy(contract)
            prior={}if mode=='missing'else altered['previous_stage_adapter']['previous_stage_adapter']
            altered['previous_stage_adapter']=prior;altered['previous_stage_sha256']=c.comm.contract_digest(prior)
            proof=altered['publication_trace_contract'];proof['previous_stage_sha256']=altered['previous_stage_sha256']
            altered['postproof_sha256']=c.comm.contract_digest(proof)
            with self.assertRaises(ValueError,msg=mode):c.verify(altered,final,owner)
    def test_scope_guarantees_are_exact_typed_values_not_truthiness(self):
        owner,contract,final,_=self.row()
        for key,value in(('appended_fields',True),('replaced_owned_bodies',1),('appended_methods',0),
                          ('native_clock_QName_verified',False),('runtime_qualified',True),('performance_gain_claimed',True)):
            altered=copy.deepcopy(contract);proof=altered['publication_trace_contract'];proof[key]=value
            altered['postproof_sha256']=c.comm.contract_digest(proof)
            with self.assertRaises(ValueError,msg=key):c.verify(altered,final,owner)
    def mutate(self,final,owner,name):
        prefix,raw=c.binding._abc_payload(final);a=c.mechanics.ABC(raw).parse();row=c.presentation.named(a,owner,name)[1]
        old=raw[row['start']:row['end']];code=row['value']['code'];at=old.index(code)
        self.assertIn(code[-1],(0x47,0x48));changed=old[:at]+code[:-1]+bytes([0x48 if code[-1]==0x47 else 0x47])+old[at+len(code):]
        return build.replace_payload(final,prefix+raw[:row['start']]+changed+raw[row['end']:])
    def rehash(self,contract,final,owner):
        altered=copy.deepcopy(contract);proof=altered['publication_trace_contract'];proof['final_swf_sha256']=c.sha(final);proof['abc_sha256']=c.sha(c.binding._abc_payload(final)[1]);altered['patched_resource_sha256'if owner==c.GRID else'final_swf_sha256']=c.sha(final);altered['postproof_sha256']=c.comm.contract_digest(proof);return altered
    def test_rehashed_new_emitter_cfg_change_refuses(self):
        owner,contract,final,_=self.row();changed=self.mutate(final,owner,'ApexGridPublicationTrace')
        with self.assertRaises(ValueError):c.verify(self.rehash(contract,changed,owner),changed,owner)
    def test_rehashed_existing_default_loop_change_refuses(self):
        owner,contract,final,_=self.row();changed=self.mutate(final,owner,'ApexTxnStep')
        with self.assertRaises(ValueError):c.verify(self.rehash(contract,changed,owner),changed,owner)
    def test_rehashed_main_callback_and_original_draw_changes_refuse(self):
        owner,contract,final,_=self.rows['main']
        for target,name in((owner,'ApexCatalogPublicationTraceStep'),('widgets.CAS.controls.CASClothingPanelCellViewMain','Draw')):
            changed=self.mutate(final,target,name)
            with self.assertRaises(ValueError,msg=name):c.verify(self.rehash(contract,changed,owner),changed,owner)
    def test_final_swf_and_abc_hashes_cannot_be_omitted(self):
        owner,contract,final,_=self.row()
        for key in('final_swf_sha256','abc_sha256'):
            altered=copy.deepcopy(contract);altered['publication_trace_contract'].pop(key)
            altered['postproof_sha256']=c.comm.contract_digest(altered['publication_trace_contract'])
            with self.assertRaises(ValueError,msg=key):c.verify(altered,final,owner)
    def test_partial_rollback_or_malformed_constant_prefix_refuses(self):
        owner,contract,final,_=self.rows['main']
        for mode in('body','constant'):
            altered=copy.deepcopy(contract);proof=altered['publication_trace_contract']
            if mode=='body':proof['rollback']['bodies'].pop(c.stage.MAIN_REPLACED[0])
            else:proof['rollback']['pool_counts'][0]=False
            altered['postproof_sha256']=c.comm.contract_digest(proof)
            with self.assertRaises(ValueError,msg=mode):c.verify(altered,final,owner)
    def test_native_clock_namespace_cannot_change_even_with_outer_hashes_recomputed(self):
        owner,contract,final,_=self.rows['main'];prefix,raw=c.binding._abc_payload(final)
        self.assertIn(b'flash.utils',raw)
        changed=build.replace_payload(final,prefix+raw.replace(b'flash.utils',b'flash.utilx'))
        with self.assertRaises(ValueError):c.verify(self.rehash(contract,changed,owner),changed,owner)


if __name__=='__main__':unittest.main()
