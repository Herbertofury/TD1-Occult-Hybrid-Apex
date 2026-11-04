import os
import shutil
import subprocess
import tempfile
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core.cas_controls import validate,PostconditionMismatch


class DonorFavoritesControlsTests(unittest.TestCase):
    def evidence(self,enabled=True):
        key='dynamic_cas_columns.favorite.shared.123456'
        request=dict(operation='catalog-companion',action='toggle-favorite',data_id='123456')
        receipt=dict(action='toggle-favorite',data_id='123456',key=key,enabled=enabled,sim_id='42',owner_id='fairy/alternate')
        companion=dict(available=True,pending=False,appearance_written=False,source='Dynamic CAS Companion actual code',
                       native_controls=True,favorites=[key] if enabled else [],receipt=receipt)
        client=dict(sim=dict(simId='42'),form_strip=dict(selected_owner_id='fairy/alternate'),
                    control=dict(operation='catalog-companion',appearance_write_possible=False,workspace=dict(companion=companion)))
        return client,request,companion,receipt

    def test_actual_donor_preference_key_and_membership_on_and_off(self):
        for enabled in (True,False):
            client,request,_,_=self.evidence(enabled);validate(client,request)

    def test_other_items_owners_and_stale_or_opposite_readbacks_are_rejected(self):
        for defect in ('item','owner','sim','key','inventory','enabled','pending','appearance'):
            with self.subTest(defect=defect):
                client,request,companion,receipt=self.evidence()
                if defect=='item':receipt['data_id']='654321'
                elif defect=='owner':receipt['owner_id']='native/1'
                elif defect=='sim':receipt['sim_id']='43'
                elif defect=='key':receipt['key']='dynamic_cas_columns.favorite.shared.654321'
                elif defect=='inventory':companion['favorites']=[]
                elif defect=='enabled':receipt['enabled']=False
                elif defect=='pending':companion['pending']=True
                elif defect=='appearance':companion['appearance_written']=True
                with self.assertRaises(PostconditionMismatch):validate(client,request)

    def test_unknown_implementations_cannot_claim_a_donor_key(self):
        client,request,companion,_=self.evidence();companion['source']='unknown'
        with self.assertRaises(PostconditionMismatch):validate(client,request)

ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless((ROOT/'.work/research/apex-cas-compiled.swf').exists() and shutil.which('javac'),'Private CAS compiler fixtures required')
class DonorGridBytecodeTests(unittest.TestCase):
    def test_compiled_command_and_status_reject_the_wrong_scrolling_container(self):
        jar=ROOT/'.work/research/ffdec/ffdec.jar'
        with tempfile.TemporaryDirectory(prefix='apex-donor-grid-') as folder:
            subprocess.run(['javac','-cp',str(jar),'-d',folder,str(ROOT/'tools/CasBytecodePatch.java'),
                            str(ROOT/'tests/CasCompanionGridFixtures.java')],check=True,capture_output=True,timeout=60)
            for case in ('valid','command','status','self-busy'):
                with self.subTest(case=case):
                    result=subprocess.run(['java','-cp',str(jar)+os.pathsep+folder,'CasCompanionGridFixtures',
                        str(ROOT/'.work/research/apex-cas-compiled.swf'),case],capture_output=True,text=True,timeout=30)
                    self.assertEqual(result.returncode,0,result.stdout[-500:]+result.stderr[-1000:])
                    self.assertIn('PASS '+case,result.stdout)

if __name__=='__main__':unittest.main()
