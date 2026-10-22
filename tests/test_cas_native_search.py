"""Native search transport and truthful asynchronous acknowledgements."""
import copy
from pathlib import Path
import sys
import unittest
import os
import shutil
import subprocess
import tempfile
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'Source'),str(ROOT/'tools')]
from apex_core import cas_controls,cas_ui
from cas_ui_build import source_pins,verify_control_dispatch

JAR=ROOT/'.work/research/ffdec/ffdec.jar'
COMPILED=ROOT/'.work/research/apex-cas-compiled.swf'


class NativeSearchTests(unittest.TestCase):
    def test_query_is_lossless_and_cannot_inject_an_envelope_field(self):
        for text in ('','Magic Hand','author:"Magic Hand" origin:cc type:29','a|b%20"','café','头发'):
            with self.subTest(text=text):
                request={'operation':'catalog-search','text':text}
                _,frame=cas_ui.envelope('12',request)
                fields=frame.split('|')
                self.assertEqual(len(fields),7)
                self.assertEqual(unquote(fields[-1]),text)
                self.assertTrue(frame.isascii())

    def test_unbounded_or_control_input_is_rejected_before_native_dispatch(self):
        for text in (None,False,[], 'a'*161,'a\nb','a\tb','\x7f', '头'*160):
            with self.subTest(text=text),self.assertRaises(ValueError):
                cas_ui.envelope('12',{'operation':'catalog-search','text':text})

    def test_acknowledgement_is_only_for_the_exact_field_not_finished_results(self):
        request={'operation':'catalog-search','text':'lipstik'}
        search=dict(available=True,text='lipstik',pending=True,ready=False,appearance_written=False)
        client={'control':dict(operation='catalog-search',appearance_written=False,workspace={'search':search})}
        cas_controls.validate(client,request)
        for field,value in [('text','lipstick'),('available',False),('appearance_written',True)]:
            changed=copy.deepcopy(client);changed['control']['workspace']['search'][field]=value
            with self.subTest(field=field),self.assertRaises(cas_controls.PostconditionMismatch):
                cas_controls.validate(changed,request)
        changed=copy.deepcopy(client);changed['control']['appearance_written']=True
        with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(changed,request)

    def test_search_is_in_the_immutable_ui_source_and_public_dispatch_contract(self):
        self.assertIn('Source/CASUi/catalog_search_methods.as',source_pins())
        self.assertIn('catalog-search',verify_control_dispatch((ROOT/'Source/CASUi/semantic_methods.as').read_text()))


@unittest.skipUnless(JAR.exists() and COMPILED.exists() and shutil.which('javac'),'Local compiled CAS and JDK required')
class NativeSearchBytecodeTests(unittest.TestCase):
    def test_serialized_search_gates_reject_native_input_work_and_stale_publication(self):
        with tempfile.TemporaryDirectory(prefix='apex-search-bytecode-') as work:
            subprocess.run(['javac','-cp',str(JAR),'-d',work,str(ROOT/'tools/CasBytecodePatch.java'),
                str(ROOT/'tests/java/CasSearchBytecodeFixtures.java')],check=True,capture_output=True,timeout=60)
            for case in ('valid','input-native-work','publish-no-context','publish-no-membership','publish-stale-key','adopt-wrong-owner','publish-rebuilds-unchanged','search-sim-instead-of-channel','search-runtime-json','swatch-no-membership','swatch-no-family-cache'):
                with self.subTest(case=case):
                    result=subprocess.run(['java','-cp',str(JAR)+os.pathsep+work,'CasSearchBytecodeFixtures',str(COMPILED),case],
                        capture_output=True,text=True,timeout=30)
                    self.assertEqual(result.returncode,0,result.stdout[-500:]+result.stderr[-1200:])
                    self.assertIn('PASS '+case,result.stdout)


if __name__=='__main__':unittest.main()
