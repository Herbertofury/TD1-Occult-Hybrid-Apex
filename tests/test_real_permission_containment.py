"""Opt-in real broker containment check. Never invokes EA, game, UI or input.

This touches actual filesystem metadata, including ancestor checks. Do not run
without the relevant exact owner approval; never retry after a denial.
"""
import os,sys,tempfile,unittest,uuid
from pathlib import Path
ROOT=Path(os.environ.get('APEX_CHECKOUT',str(Path(__file__).absolute().parent.parent)))
sys.path.insert(0,str(ROOT/'tools'))
import ea_permission_broker as broker

@unittest.skipUnless(os.environ.get('APEX_PERMISSION_REAL_FS')=='1','Real filesystem check requires explicit owner approval')
class RealContainment(unittest.TestCase):
 def test_existing_work_is_accepted_and_external_directory_is_rejected(self):
  # Retain both fresh empty directories as evidence. On any permission error,
  # let the exception stop this single test; do not retry or use an alternate path.
  work=ROOT/'.work'/('permission-containment-'+uuid.uuid4().hex)
  work.mkdir(exist_ok=False)
  external=Path(tempfile.mkdtemp(prefix='apex-permission-containment-'))
  print('Fresh test directories:',work,external,flush=True)
  accepted=broker.evidence_directory(work)
  self.assertEqual(accepted,work.resolve())
  with self.assertRaisesRegex(ValueError,'existing external repository .work evidence directory'):
   broker.evidence_directory(external)
if __name__=='__main__':unittest.main(verbosity=2)
