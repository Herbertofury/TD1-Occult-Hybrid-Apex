"""New donor recognition cannot weaken the historical merge gate."""
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import dbpf_build
import maru_companion
import maru_companion_versions as versions

SUPPLIED=Path(os.environ['APEX_PRIVATE_MARU_DONOR']) if os.environ.get('APEX_PRIVATE_MARU_DONOR') else None
BRIDGE=Path(os.environ['APEX_PRIVATE_CAS_BRIDGE']) if os.environ.get('APEX_PRIVATE_CAS_BRIDGE') else None
BRIDGE_SHA='c3f70eeef33114b705e8247c6af2bd1f23a51ba9b6e48b40ec95d9b6be6a5a3f'


class VersionTests(unittest.TestCase):
    def test_historical_gate_remains_exact_and_does_not_accept_new(self):
        self.assertEqual(maru_companion.PACKAGE_SHA256,'054ca6a189a587063290df004a42072c5381e59404d33e58ddb737ab821cf9c3')
        self.assertEqual(len(maru_companion.expected_resources()),66)
        if SUPPLIED is None or not SUPPLIED.is_file():self.skipTest('Set APEX_PRIVATE_MARU_DONOR to the private exact supplied donor')
        with self.assertRaisesRegex(ValueError,'differs'):maru_companion.read_package(SUPPLIED)

    def test_unknown_or_tampered_package_is_never_recognized(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'other.package';path.write_bytes(dbpf_build.build({(1,2,3):b'fixture'}))
            with self.assertRaisesRegex(ValueError,'Unknown donor'):versions.inspect_donor(path)

    def test_inventory_mismatch_refuses_even_when_outer_package_is_exact(self):
        if SUPPLIED is None or not SUPPLIED.is_file():self.skipTest('Set APEX_PRIVATE_MARU_DONOR to the private exact supplied donor')
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'inventory.json';path.write_text('{}',encoding='utf-8')
            with patch.object(versions,'INVENTORY',path),self.assertRaisesRegex(ValueError,'inventory'):
                versions.inspect_donor(SUPPLIED)

    def test_exact_supplied_donor_is_identified_but_not_approved(self):
        if SUPPLIED is None or not SUPPLIED.is_file():self.skipTest('Set APEX_PRIVATE_MARU_DONOR to the private exact supplied donor')
        result=versions.inspect_donor(SUPPLIED)
        self.assertEqual(result['package_sha256'],versions.SUPPLIED_SHA)
        self.assertEqual(result['resource_count'],88)
        self.assertEqual(len(result['resource_sha256']),88)
        self.assertFalse(result['merge_authorized']);self.assertFalse(result['actual_game_verified'])
        self.assertEqual(result['donor_version_string'],'unestablished')

    def test_real_collision_report_never_selects_precedence(self):
        if SUPPLIED is None or BRIDGE is None or not (SUPPLIED.is_file() and BRIDGE.is_file()):
            self.skipTest('Set APEX_PRIVATE_MARU_DONOR and APEX_PRIVATE_CAS_BRIDGE to private fixtures')
        report=versions.collision_report(SUPPLIED,BRIDGE,BRIDGE_SHA)
        self.assertFalse(report['precedence_selected']);self.assertFalse(report['merge_authorized'])
        rows={row['role']:row for row in report['collisions'] if row['role']!='other-resource'}
        self.assertEqual(set(rows),{'customizer-main','donor-grid-provider','plan-outfit-header'})
        for row in rows.values():
            self.assertFalse(row['same_bytes']);self.assertEqual(row['disposition'],'unresolved-proof-required')
        self.assertEqual(len(report['collisions']),67)
        with self.assertRaisesRegex(ValueError,'differs'):versions.collision_report(SUPPLIED,BRIDGE,'0'*64)

    def test_no_merge_api_accepts_approval_assertions(self):
        with self.assertRaises(TypeError):versions.collision_report(SUPPLIED,BRIDGE,BRIDGE_SHA,{'all_safe':True})

    def test_missing_apex_resources_are_reported_and_never_authorize_a_merge(self):
        if SUPPLIED is None or not SUPPLIED.is_file():self.skipTest('Set APEX_PRIVATE_MARU_DONOR to the private exact supplied donor')
        raw=dbpf_build.build({(1,2,3):b'fixture'})
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'sparse.package';path.write_bytes(raw)
            report=versions.collision_report(SUPPLIED,path,hashlib.sha256(raw).hexdigest())
            self.assertEqual(report['collisions'],[])
            self.assertEqual(len(report['role_status']),4)
            self.assertTrue(all(r['status']=='absent-in-apex' for r in report['role_status']))
            self.assertFalse(report['merge_authorized'])

    def test_duplicate_inventory_keys_refused(self):
        if SUPPLIED is None or not SUPPLIED.is_file():self.skipTest('Set APEX_PRIVATE_MARU_DONOR to the private exact supplied donor')
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'inventory.json';path.write_text('{"package_sha256":"x","package_sha256":"y"}',encoding='utf-8')
            with patch.object(versions,'INVENTORY',path),self.assertRaisesRegex(ValueError,'Duplicate donor inventory'):
                versions.inspect_donor(SUPPLIED)

    def test_report_never_overwrites_or_writes_outside_private_work(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);work=root/'work';work.mkdir();out=work/'report.json'
            with patch.object(versions,'WORK',work):
                versions.write_report(out,{'merge_authorized':False})
                with self.assertRaises(FileExistsError):versions.write_report(out,{'merge_authorized':True})
                with self.assertRaisesRegex(ValueError,'private'):versions.write_report(root/'escape.json',{})
            self.assertIn('false',out.read_text())

if __name__=='__main__':unittest.main()
