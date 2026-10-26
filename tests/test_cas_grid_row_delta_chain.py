"""Private compiled exact-predecessor and adverse identity gates."""
from pathlib import Path
import copy,json,os,sys,unittest
H=Path(__file__).resolve().parents[1];R=next(p for p in (H,*H.parents) if(p/'tools/dbpf_build.py').is_file())
sys.path[:0]=[str(H/'tools'),str(R/'tools')]
import cas_grid_row_delta as c
import cas_ui_build as ui
import cas_catalog_binding as binding
import cas_grid_presentation as presentation
import cas_communication_index as comm

FIXTURE=Path(os.environ['APEX_CAS_ROW_DELTA_FIXTURE'])if os.environ.get('APEX_CAS_ROW_DELTA_FIXTURE')else None

@unittest.skipUnless(FIXTURE is not None,'Set APEX_CAS_ROW_DELTA_FIXTURE for authenticated native fixtures')
class ChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=[]
        for name,owner in [('12272E1AC0C1F8E2',c.GRID),('89D13757C58C2E05',c.GRID),('main',c.MAIN)]:
            p=FIXTURE/name
            cls.rows.append((owner,json.loads((p/'contract.json').read_text()),(p/'final.swf').read_bytes(),(p/'baseline.swf').read_bytes()))
    def verify(self,a,raw,owner):return c.verify_adapter(a,raw)if owner==c.GRID else c.verify_main(a,raw)
    def test_all_three_exact_skin_terminal_continuations_and_whole_raw_rollback(self):
        for owner,a,raw,base in self.rows:
            self.assertTrue(self.verify(a,raw,owner))
            self.assertEqual(c.historical(a,raw,owner)[1],base)
    def test_missing_partial_stale_source_pins_refused(self):
        for owner,a,raw,_ in self.rows:
            for mode in ('missing','partial','stale'):
                bad=copy.deepcopy(a);p=bad['row_delta_contract']
                if mode=='missing':p.pop('source_sha256')
                elif mode=='partial':p['source_sha256'].pop(next(iter(p['source_sha256'])))
                else:p['source_sha256'][next(iter(p['source_sha256']))]='0'*64
                with self.assertRaises(ValueError):self.verify(bad,raw,owner)
    def test_no_runtime_claim_method_count_or_rollback_guarantee_downgrade(self):
        for owner,a,raw,_ in self.rows:
            for k,v in [('runtime_qualified',True),('performance_gain_claimed',True),('whole_abc_rollback_verified',False),('appended_methods',99),('changed_original_native_bodies',1)]:
                bad=copy.deepcopy(a);bad['row_delta_contract'][k]=v
                with self.assertRaises(ValueError):self.verify(bad,raw,owner)
    def test_wrong_or_missing_complete_current_predecessor_rejected_even_with_rehashed_outer_proof(self):
        for owner,a,raw,_ in self.rows:
            bad=copy.deepcopy(a);key='previous_stage_adapter'if owner==c.GRID else'previous_stage_contract'
            prior=bad[key];prior.pop('swatch_columns_contract'if owner==c.GRID else'swatch_columns_main_contract')
            bad['row_delta_contract']['previous_stage_sha256']=comm.contract_digest(prior)
            bad['previous_stage_sha256']=comm.contract_digest(prior)
            bad['postproof_sha256']=comm.contract_digest(bad['row_delta_contract'])
            with self.assertRaisesRegex(ValueError,'Skin predecessor'):self.verify(bad,raw,owner)
    def test_final_owned_instruction_semantics_cannot_be_forged_by_rehashing(self):
        for owner,a,raw,_ in self.rows:
            prefix,abc=binding._abc_payload(raw);parsed=c.mechanics.ABC(abc).parse()
            name='ApexGridDeltaCapable'if owner==c.GRID else'ApexCatalogGridRequest'
            body=presentation.named(parsed,owner,name)[1]['value'];code=body['code'];at=abc.find(code)
            self.assertGreater(at,0)
            # Replace a pushnull/true/false instruction only, never alter length.
            i=next(i for i,_,op,_ in parsed.instructions(code)if op in(0x20,0x26,0x27))
            modified=abc[:at+i]+bytes([0x27 if code[i]!=0x27 else 0x26])+abc[at+i+1:]
            changed=ui.replace_payload(raw,prefix+modified);bad=copy.deepcopy(a)
            bad['row_delta_contract']['final_swf_sha256']=c.sha(changed);bad['row_delta_contract']['abc_sha256']=c.sha(modified)
            bad['patched_resource_sha256'if owner==c.GRID else'final_swf_sha256']=c.sha(changed)
            bad['postproof_sha256']=comm.contract_digest(bad['row_delta_contract'])
            with self.assertRaisesRegex(ValueError,'semantic'):self.verify(bad,changed,owner)
    def test_native_unowned_body_tamper_survives_owned_undo_and_is_refused(self):
        owner,a,raw,_=self.rows[0];prefix,abc=binding._abc_payload(raw);parsed=c.mechanics.ABC(abc).parse()
        code=presentation.named(parsed,owner,'CycleCells')[1]['value']['code'];at=abc.find(code)
        i=next(i for i,_,op,_ in parsed.instructions(code)if op in(0x26,0x27))
        changed_abc=abc[:at+i]+bytes([0x27 if code[i]==0x26 else 0x26])+abc[at+i+1:]
        changed=ui.replace_payload(raw,prefix+changed_abc);bad=copy.deepcopy(a)
        bad['row_delta_contract']['final_swf_sha256']=c.sha(changed);bad['row_delta_contract']['abc_sha256']=c.sha(changed_abc)
        bad['patched_resource_sha256']=c.sha(changed);bad['postproof_sha256']=comm.contract_digest(bad['row_delta_contract'])
        with self.assertRaisesRegex(ValueError,'predecessor bytes'):self.verify(bad,changed,owner)

if __name__=='__main__':unittest.main()
