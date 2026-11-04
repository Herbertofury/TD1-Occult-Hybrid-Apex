"""One exact donor dead write, preserving independent Main/Draw history."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import cas_cell_attach as attach

WORK=ROOT/'.work/v335-cell-attach'


@unittest.skipUnless((WORK/'chained.json').exists()and shutil.which('javac'),'Private current final-Main fixture and JDK required')
class CellAttachTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='apex-cell-attach-');cls.addClassCleanup(cls.temp.cleanup);cls.jar=ROOT/'.work/research/ffdec/ffdec.jar'
        r=subprocess.run(['javac','-cp',str(cls.jar),'-d',cls.temp.name,str(ROOT/'tools/CasStructuralRolesPatch.java'),str(ROOT/'tools/CasCellAttachPatch.java'),str(ROOT/'tests/CasCellAttachBytecodeFixtures.java')],capture_output=True,text=True,timeout=60)
        if r.returncode:raise AssertionError(r.stdout+r.stderr)

    def test_actual_compiled_deletion_retains_arbitrary_user_scale_all_native_and_donor_features(self):
        r=subprocess.run(['java','-cp',str(self.jar)+os.pathsep+self.temp.name,'CasCellAttachBytecodeFixtures',
            str(ROOT/'.work/research/maru-integrated/DynamicCASCustomizer.swf'),str(WORK/'baseline.swf'),str(WORK/'final.swf')],capture_output=True,text=True,timeout=90)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr[-3000:]);self.assertEqual(r.stdout.count('PASS '),15)

    def test_final_chain_keeps_three_prior_proofs_and_refuses_relabelled_bytes_or_fidelity_claim(self):
        record=json.loads((WORK/'chained.json').read_text());final=(WORK/'final.swf').read_bytes();self.assertTrue(attach.verify_contract(record,final))
        for field,value in [('removed_instructions',4),('appended_traits',1),('native_cfg_projection_verified',False),('final_xy_writes_retained',False),
                ('authoritative_static_slot_verified',False),('rightclick_favorite_body_retained',False),('runtime_qualified',True),('performance_gain_claimed',True),('abc_sha256','0'*64)]:
            changed=copy.deepcopy(record);changed['cell_attach_contract'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):attach.verify_contract(changed,final)
        for stage in('native_bytecode_contract','structural_roles_native_bytecode_contract','draw_fast_path_native_bytecode_contract'):
            changed=copy.deepcopy(record);changed['previous_chain'][stage]['ok']=False
            with self.subTest(stage=stage),self.assertRaises(ValueError):attach.verify_contract(changed,final)
        with self.assertRaises(ValueError):attach.verify_contract(record,(WORK/'baseline.swf').read_bytes())
        changed=copy.deepcopy(record);changed['cell_attach_contract']['source_sha256']['tools/CasCellAttachPatch.java']='0'*64
        with self.assertRaises(ValueError):attach.verify_contract(changed,final)

    def test_pure_byte_rollback_reconstructs_exact_previous_swf_and_rejects_forged_outer_fields(self):
        import cas_draw_fast_path as draw
        import cas_ui_build as ui
        import cas_communication_index as comm
        record=json.loads((WORK/'chained.json').read_text());final=(WORK/'final.swf').read_bytes()
        self.assertEqual(attach.reconstruct_previous(final),(WORK/'baseline.swf').read_bytes())
        payload=[t[3]for t in ui.tags(ui.unpack(final)[1])if t[0]==82][0];boundary=payload.index(b'\0',4)+1;abc=payload[boundary:]
        rows=attach._ABCReader(abc).code_vectors();row=next(r for r in rows if len(r['code'])>30 and attach.digest(r['code'])!=attach.EDITED_CONFIG_UI_SHA256)
        damaged=bytearray(abc);damaged[row['code_at']+3]^=1
        bad=ui.replace_payload(final,payload[:boundary]+damaged)
        forged=copy.deepcopy(record);forged['cell_attach_contract']['abc_sha256']=attach.digest(bytes(damaged));forged['postproof_sha256']=comm.contract_digest(forged['cell_attach_contract']);forged['final_swf_sha256']=attach.digest(bad)
        with self.assertRaisesRegex(ValueError,'reconstruct'):attach.verify_contract(forged,bad)
        edited=next(r for r in rows if attach.digest(r['code'])==attach.EDITED_CONFIG_UI_SHA256)
        damaged=bytearray(abc);damaged[edited['code_at']+3]^=1
        bad=ui.replace_payload(final,payload[:boundary]+damaged)
        with self.assertRaisesRegex(ValueError,'ConfigUI'):attach.reconstruct_previous(bad)
        with self.assertRaises(ValueError):attach._ABCReader(abc[:-1]).code_vectors()
        with self.assertRaises(ValueError):attach._ABCReader(abc+b'\0').code_vectors()


if __name__=='__main__':unittest.main()
