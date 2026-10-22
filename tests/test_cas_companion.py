"""Preferences must not acknowledge another item, form or native input route."""
import copy
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'Source')]
from apex_core import cas_controls,cas_ui


class CompanionContractTests(unittest.TestCase):
    def test_right_click_preference_intent_cannot_supply_appearance_fields(self):
        good=dict(operation='catalog-companion',action='toggle-favorite',data_id='18446744073709551615')
        cas_ui.envelope('12',good)
        for extra in ({'appearance':{}},{'owner_id':'foreign'},{'part_id':'1'}):
            with self.assertRaises(ValueError):cas_ui.envelope('12',dict(good,**extra))
        for identity in (None,False,0,'0','-1','18446744073709551616','1|equip','0x12'):
            with self.subTest(identity=identity),self.assertRaises(ValueError):cas_ui.envelope('12',dict(good,data_id=identity))

    def test_preference_ack_requires_exact_action_item_member_form_and_inventory(self):
        request=dict(operation='catalog-companion',action='toggle-favorite',data_id='19')
        companion=dict(available=True,pending=False,appearance_written=False,favorites=['part/29/19'],
            receipt=dict(action='toggle-favorite',data_id='19',key='part/29/19',enabled=True,sim_id='12',owner_id='alien'))
        client=dict(sim={'simId':'12'},form_strip={'selected_owner_id':'alien'},
            control=dict(operation='catalog-companion',appearance_write_possible=False,workspace={'companion':companion}))
        cas_controls.validate(client,request)
        for field,value in [('action','toggle-hidden'),('data_id','20'),('key','part/29/20'),('enabled',False),('sim_id','13'),('owner_id','vampire')]:
            changed=copy.deepcopy(client);changed['control']['workspace']['companion']['receipt'][field]=value
            with self.subTest(field=field),self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(changed,request)
        changed=copy.deepcopy(client);changed['control']['appearance_write_possible']=True
        with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(changed,request)

    def test_non_item_actions_never_accept_a_borrowed_item(self):
        for action in ('all','favorites','hidden','recent','hide-mode','pause','play','columns-reset','refresh-search'):
            cas_ui.envelope('12',dict(operation='catalog-companion',action=action,data_id=None))
            with self.assertRaises(ValueError):cas_ui.envelope('12',dict(operation='catalog-companion',action=action,data_id='19'))


JAR=ROOT/'.work/research/ffdec/ffdec.jar'
COMPILED=ROOT/'.work/research/apex-cas-compiled.swf'
@unittest.skipUnless(JAR.exists() and COMPILED.exists() and shutil.which('javac'),'Local compiled CAS and JDK required')
class CompanionBytecodeTests(unittest.TestCase):
    def test_serialized_input_and_cleanup_gates_reject_mutations(self):
        with tempfile.TemporaryDirectory(prefix='apex-companion-bytecode-') as work:
            subprocess.run(['javac','-cp',str(JAR),'-d',work,str(ROOT/'tools/CasBytecodePatch.java'),str(ROOT/'tests/java/CasCompanionBytecodeFixtures.java')],check=True,capture_output=True,timeout=60)
            for case in ('valid','rightclick-native-work','rightclick-propagates','intent-no-context','badges-native-work','dispose-no-tooltip-cleanup'):
                with self.subTest(case=case):
                    r=subprocess.run(['java','-cp',str(JAR)+os.pathsep+work,'CasCompanionBytecodeFixtures',str(COMPILED),case],capture_output=True,text=True,timeout=30)
                    self.assertEqual(r.returncode,0,r.stdout[-500:]+r.stderr[-1200:])

if __name__=='__main__':unittest.main()
