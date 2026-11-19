"""Exercise real merged resources; corruption must not pass the bundle gate."""
import copy
import json
from pathlib import Path
import sys
import unittest
import os
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import dbpf_build
import maru_companion

PACKAGE=ROOT/'dist/candidate/ApexCASBridge.package'
MANIFEST=Path(str(PACKAGE)+'.manifest.json')


class DonorIdentityTests(unittest.TestCase):
    def test_reviewed_inventory_includes_history_library_and_localization(self):
        rows=maru_companion.expected_resources()
        self.assertEqual(len(rows),66)
        self.assertIn('62ECC59A:00000000:FE7D7B3A973E3C5D',rows)
        self.assertEqual(sum(key.startswith('545AC67A:') for key in rows),4)


@unittest.skipUnless(PACKAGE.exists() and MANIFEST.exists(),'Private compiled CAS bridge required')
class LiteralMergeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.info=json.loads(MANIFEST.read_text(encoding='utf-8'))
        if cls.info.get('companion_code_merge') is None:
            raise unittest.SkipTest('Compile with the owner-supplied Dynamic CAS package')
        cls.resources=dbpf_build.read(PACKAGE.read_bytes())

    def test_complete_actual_donor_retention(self):
        self.assertTrue(maru_companion.verify_merged(self.info,self.resources))
        self.assertEqual(len(self.resources),72 + int(maru_companion.UNMODIFIED_OLYMPUS_LIBRARY in self.resources))
        self.assertEqual(set(self.info['grid_provider_adapters']),
                         {dbpf_build.tgi(maru_companion.GRID_LIBRARY),
                          dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY)})

    def test_missing_or_changed_history_and_art_are_rejected(self):
        for key in self.resources:
            if dbpf_build.tgi(key) not in maru_companion.expected_resources() or key==maru_companion.CUSTOMIZER:
                continue
            with self.subTest(tgi=dbpf_build.tgi(key)):
                changed=dict(self.resources);del changed[key]
                with self.assertRaises(ValueError):maru_companion.verify_merged(self.info,changed)
                changed[key]=self.resources[key]+b'changed'
                with self.assertRaises(ValueError):maru_companion.verify_merged(self.info,changed)

    def test_a_pattern_only_build_cannot_claim_the_full_code_merge(self):
        for field,value in [('package_sha256','0'*64),('method','interaction-patterns')]:
            changed=copy.deepcopy(self.info);changed['companion_code_merge'][field]=value
            with self.assertRaises(ValueError):maru_companion.verify_merged(changed,self.resources)
        changed=copy.deepcopy(self.info);changed['native_bytecode_contract']['native_method_count']=1787
        with self.assertRaises(ValueError):maru_companion.verify_merged(changed,self.resources)

    def test_palette_recovery_requires_the_reviewed_additional_native_adapter(self):
        for key,value in [('unchanged_native_methods',2632),('native_pelt_palette_reenable_verified',False),
                          ('native_current_outfit_refresh_queue_verified',False),('native_column_scheduler_adapters',7),
                          ('native_lazy_swatch_adapters',1),('native_favorite_lookup_map_verified',False),('native_outfit_consumers',2),
                          ('native_draw_trace_cfg_verified',False),('native_draw_trace_call_abi_verified',False)]:
            changed=copy.deepcopy(self.info);changed['native_bytecode_contract'][key]=value
            with self.subTest(field=key):
                with self.assertRaises(ValueError):maru_companion.verify_merged(changed,self.resources)


@unittest.skipUnless((ROOT/'.work/research/apex-companion-context-3.swf').exists() and shutil.which('javac'),
                     'Private compiled Companion adapters required')
class CompanionIdentityBytecodeTests(unittest.TestCase):
    def test_serialized_consumer_callbacks_fallbacks_and_exception_regions(self):
        jar=ROOT/'.work/research/ffdec/ffdec.jar'
        with tempfile.TemporaryDirectory(prefix='apex-consumer-fixtures-') as directory:
            subprocess.run(['javac','-cp',str(jar),'-d',directory,str(ROOT/'tools/CasBytecodePatch.java'),
                            str(ROOT/'tests/CasOutfitConsumerBytecodeFixtures.java')],check=True,capture_output=True,timeout=60)
            for case in ('valid','callback','fallback','exception','retained','sink-service','sink-fallback','shared-linkage'):
                with self.subTest(case=case):
                    result=subprocess.run(['java','-cp',str(jar)+os.pathsep+directory,'CasOutfitConsumerBytecodeFixtures',
                        str(ROOT/'.work/research/maru-integrated/DynamicCASCustomizer.swf'),
                        str(ROOT/'.work/research/apex-companion-context-3.swf'),case],capture_output=True,text=True,timeout=30)
                    self.assertEqual(result.returncode,0,result.stdout[-500:]+result.stderr[-1000:])
                    self.assertIn('PASS '+case,result.stdout)

    def test_serialized_frame_dispatch_preserves_original_body_and_refuses_corruption(self):
        jar=ROOT/'.work/research/ffdec/ffdec.jar'
        with tempfile.TemporaryDirectory(prefix='apex-outfit-fixtures-') as directory:
            subprocess.run(['javac','-cp',str(jar),'-d',directory,str(ROOT/'tools/CasBytecodePatch.java'),
                            str(ROOT/'tests/CasOutfitSchedulingBytecodeFixtures.java')],check=True,capture_output=True,timeout=60)
            for case in ('valid','service','fallback','retained-body'):
                with self.subTest(case=case):
                    result=subprocess.run(['java','-cp',str(jar)+os.pathsep+directory,'CasOutfitSchedulingBytecodeFixtures',
                        str(ROOT/'.work/research/maru-integrated/DynamicCASCustomizer.swf'),
                        str(ROOT/'.work/research/apex-companion-context-3.swf'),case],capture_output=True,text=True,timeout=30)
                    self.assertEqual(result.returncode,0,result.stdout[-500:]+result.stderr[-1000:])
                    self.assertIn('PASS '+case,result.stdout)

    def test_serialized_named_form_and_stale_timer_refusals(self):
        jar=ROOT/'.work/research/ffdec/ffdec.jar'
        with tempfile.TemporaryDirectory(prefix='apex-companion-fixtures-') as directory:
            subprocess.run(['javac','-cp',str(jar),'-d',directory,str(ROOT/'tools/CasBytecodePatch.java'),
                            str(ROOT/'tests/CasMergedCompanionBytecodeFixtures.java')],check=True,capture_output=True,timeout=60)
            for case in ('valid','service','cached-member','eye-lease','preview-recheck'):
                with self.subTest(case=case):
                    result=subprocess.run(['java','-cp',str(jar)+os.pathsep+directory,'CasMergedCompanionBytecodeFixtures',
                        str(ROOT/'.work/research/maru-integrated/DynamicCASCustomizer.swf'),
                        str(ROOT/'.work/research/apex-companion-context-3.swf'),case],capture_output=True,text=True,timeout=30)
                    self.assertEqual(result.returncode,0,result.stdout[-500:]+result.stderr[-1000:])
                    self.assertIn('PASS '+case,result.stdout)


if __name__=='__main__':unittest.main()
