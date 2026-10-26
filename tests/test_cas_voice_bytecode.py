"""Actual native widget patch preserves user interaction and other methods."""
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
from cas_ui_build import PINNED_SOURCES,VOICE_KEY,VOICE_PIN


class VoicePatchContractTests(unittest.TestCase):
    def test_voice_patch_is_a_pinned_build_input_and_real_widget_resource(self):
        self.assertIn('tools/CasVoiceBytecodePatch.java',PINNED_SOURCES)
        self.assertEqual(VOICE_KEY,(0x62ECC59A,0,0xE36BA403351FFE60))
        self.assertEqual(len(VOICE_PIN),64)


class SerializedVoicePatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jar=ROOT/'.work/research/ffdec/ffdec.jar';cls.widget=ROOT/'.work/research/cas-hair-casagegenderpane-current.swf';cls.library=ROOT/'.work/research/OlympusLibrary.swf'
        if not all(p.is_file() for p in (cls.jar,cls.widget,cls.library)) or not shutil.which('javac'):
            raise unittest.SkipTest('Requires the exact local game UI resources and JDK.')
        cls.temp=tempfile.TemporaryDirectory(prefix='apex-voice-patch-');cls.addClassCleanup(cls.temp.cleanup);cls.classes=Path(cls.temp.name)
        proc=subprocess.run(['javac','-cp',str(cls.jar),'-d',str(cls.classes),str(ROOT/'tools/CasBytecodePatch.java'),str(ROOT/'tools/CasVoiceBytecodePatch.java')],capture_output=True,timeout=60)
        if proc.returncode:raise AssertionError(proc.stderr.decode('utf-8')[-2000:])
    def call(self,widget,output):
        return subprocess.run(['java','-cp',os.pathsep.join((str(self.jar),str(self.classes))),'CasVoiceBytecodePatch',str(widget),str(self.library),str(output)],capture_output=True,text=True,encoding='utf-8',timeout=30)
    def test_exact_silent_refresh_serializes_without_changing_other_native_handlers(self):
        output=self.classes/'patched.abc';proc=self.call(self.widget,output)
        self.assertEqual(proc.returncode,0,proc.stderr[-2000:]);receipt=json.loads(proc.stdout)
        self.assertTrue(receipt['unrelated_native_methods_preserved']);self.assertTrue(receipt['user_voice_handler_preserved'])
        self.assertEqual(receipt['base_method_sha256'],'ee8407e704f69ad134e98afc0e701cd402de990996fd0ab85643cb61d2cff015')
        self.assertEqual(receipt['patched_method_sha256'],'3a1300de02412b157086aa3a8240b30d7a9f1319dfe1f7bb5dbb641d6a41c0b2')
        self.assertGreater(output.stat().st_size,1000)
    def test_changed_widget_refuses_without_producing_an_output(self):
        wrong=self.classes/'unknown-version.swf';wrong.write_bytes(self.widget.read_bytes()+b'changed')
        output=self.classes/'should-not-exist.abc';proc=self.call(wrong,output)
        self.assertNotEqual(proc.returncode,0);self.assertIn('differs from inspected game version',proc.stderr)
        self.assertFalse(output.exists())
