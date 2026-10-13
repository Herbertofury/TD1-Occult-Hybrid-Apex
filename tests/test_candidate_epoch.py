from pathlib import Path
import sys
import tempfile
import unittest
import hashlib
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_candidate


class CandidateEpochTests(unittest.TestCase):
    def source_fixture(self,root):
        source=root/'Source';core=source/'apex_core';core.mkdir(parents=True)
        module=core/'example.py';module.write_bytes(b'raise RuntimeError("never execute source")\n')
        pin=hashlib.sha256(module.read_bytes()).hexdigest()
        raw=("UPGRADE_EPOCH = '2026-10-12-source-fixture'\nUPGRADE_SELF_BODY_SHA = '<pinned>'\n"
             "UPGRADE_MODULE_PINS = {'apex_core/example.py': '"+pin+"'}\n").encode()
        self_hash=hashlib.sha256(raw).hexdigest()
        seal=core/'form_bank_seal.py';seal.write_bytes(raw.replace(b'<pinned>',self_hash.encode()))
        return source,module,seal

    def test_recovery_source_reads_literals_without_executing_modules(self):
        with tempfile.TemporaryDirectory() as folder:
            source,module,seal=self.source_fixture(Path(folder))
            proof=build_candidate.verify_recovery_source(source,'2026-10-12-source-fixture')
            self.assertEqual(proof['module_pins']['apex_core/example.py'],hashlib.sha256(module.read_bytes()).hexdigest())

    def test_main_module_is_allowed_but_arbitrary_root_files_are_rejected(self):
        for name in ('td1_occult_hybrid_apex.py', 'unrelated.py', '../escape.py'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                source,module,seal=self.source_fixture(Path(folder))
                target=source/name
                target.write_bytes(module.read_bytes())
                pin=hashlib.sha256(target.read_bytes()).hexdigest()
                raw=("UPGRADE_EPOCH = '2026-10-12-source-fixture'\nUPGRADE_SELF_BODY_SHA = '<pinned>'\n"
                     "UPGRADE_MODULE_PINS = {"+repr(name)+": '"+pin+"'}\n").encode()
                seal.write_bytes(raw.replace(b'<pinned>',hashlib.sha256(raw).hexdigest().encode()))
                if name == 'td1_occult_hybrid_apex.py':
                    self.assertIn(name, build_candidate.verify_recovery_source(source,'2026-10-12-source-fixture')['module_pins'])
                else:
                    with self.assertRaises(ValueError):
                        build_candidate.verify_recovery_source(source,'2026-10-12-source-fixture')

    def test_wrong_epoch_stale_module_and_stale_self_pin_fail_before_package_mutation(self):
        for failure in ('epoch','module','seal'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);source,module,seal=self.source_fixture(root)
                output=root/'dist'/'candidate';output.mkdir(parents=True)
                if failure=='module':module.write_bytes(b'changed source')
                if failure=='seal':seal.write_bytes(seal.read_bytes()+b'# changed receiver\n')
                epoch='2026-10-12-wrong-source' if failure=='epoch' else '2026-10-12-source-fixture'
                with patch.object(build_candidate,'ROOT',root),patch.object(build_candidate,'build_packages') as build:
                    with self.assertRaises(ValueError):build_candidate.build(output,epoch=epoch)
                    build.assert_not_called()
                self.assertEqual(list(output.iterdir()),[])
    def test_prior_epoch_is_refused_before_any_build_or_artifact_change(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve(); output = root/'dist'/'candidate'; output.mkdir(parents=True)
            prior = output/build_candidate.candidate_filename(None)
            prior.write_bytes(b'immutable prior bundle')
            with patch.object(build_candidate, 'ROOT', root), patch.object(build_candidate, 'build_packages') as build:
                with self.assertRaisesRegex(ValueError, 'already exists'):
                    build_candidate.build(output)
            build.assert_not_called(); self.assertEqual(prior.read_bytes(), b'immutable prior bundle')

    def test_epoch_cannot_traverse_or_inject_a_new_path(self):
        for value in ('../escape', 'new/name', 'NEW', 'x', 'a'*81, 'new:epoch', None):
            if value is None:
                self.assertEqual(build_candidate.candidate_filename(value), 'Apex_Development_Candidate_2026-10-07.zip')
            else:
                with self.subTest(value=value), self.assertRaises(ValueError):
                    build_candidate.candidate_filename(value)
        self.assertEqual(build_candidate.candidate_filename('2026-10-08-all-owner-cas-v1'),
            'Apex_Development_Candidate_2026-10-08-all-owner-cas-v1.zip')


if __name__ == '__main__':
    unittest.main()
