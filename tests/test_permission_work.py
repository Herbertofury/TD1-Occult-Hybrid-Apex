"""Mocked EA launch integration. No game, process, UAC, real journal or real lstat."""
import os,sys,tempfile,unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
# In a checkout's tests directory, import sibling tools by default. For an
# external review copy, APEX_CHECKOUT points at the actual checkout root.
ROOT=Path(os.environ.get('APEX_CHECKOUT',str(Path(__file__).absolute().parent.parent)))
sys.path.insert(0,str(ROOT/'tools'))
import game_launch as launch, apex_cli as cli
import ea_permission,ea_permission_broker as broker,launch_preferences
real_evidence=broker.evidence_directory
class FakeKey:
 def __enter__(self):return self
 def __exit__(self,*a):pass
class Cases(unittest.TestCase):
 def run_launch(self,root,*,work=None,explicit=True,remembered=False,permission=None,context_error=None,session_under_work=False,broker_error=None):
  session=(root/'repo'/'.work'/'session') if session_under_work else (root/'sessions'/'s1');session.mkdir(parents=True,exist_ok=True)
  workroot=root/'repo'/'.work';workroot.mkdir(parents=True,exist_ok=True)
  okwork=workroot/'broker';okwork.mkdir(exist_ok=True)
  log=root/'fake-log';log.write_text('old synthetic lines')
  state=session/'state.json';plan={'ok':True,'url':'origin2://fake','account_launch_identity':{'log':str(log)}}
  reg=SimpleNamespace(HKEY_CLASSES_ROOT=object(),OpenKey=lambda *a:FakeKey(),QueryValueEx=lambda *a:('EALauncher.exe %1',0))
  os_api=SimpleNamespace(name='nt',startfile=Mock())
  validation=lambda p:real_evidence(p,root=workroot)
  default_permission={'acknowledged':False} if permission is None else permission
  with ExitStack() as stack:
   for fixture in [patch.object(Path,'resolve',lambda self:self.absolute()),
       patch.object(broker,'writable',lambda p:Path(p).absolute()),
       patch.object(launch,'launch_plan',return_value=plan),patch.object(launch_preferences,'enabled',return_value=remembered),
       patch.object(launch.test_profile,'require_closed'),patch.object(launch.test_profile,'status',return_value={'ready_to_launch':True}),
       patch.object(launch.test_profile,'unlinked',side_effect=lambda p:Path(p)),patch.object(launch,'running_game_processes',return_value=[]),
       patch.object(launch,'observe_start',return_value={'process_started':False}),patch.object(launch,'os',os_api),patch.dict(sys.modules,{'winreg':reg}),
       patch.object(launch.time,'sleep'),patch.object(launch.time,'time',return_value=12345.0),
       patch.object(broker,'diagnose',return_value={'ok':True,'compatible_integrity':True})]:stack.enter_context(fixture)
   validator=stack.enter_context(patch.object(broker,'evidence_directory',side_effect=validation))
   uia=stack.enter_context(patch.object(ea_permission,'acknowledge',return_value=default_permission))
   context=stack.enter_context(patch.object(broker,'wait_launch_context',return_value={'fresh':'synthetic'},side_effect=context_error))
   elevate=stack.enter_context(patch.object(broker,'elevate_once',return_value={'ok':True,'acknowledged':True,'game_start_verified':False},side_effect=broker_error))
   error=None;result=None
   try:result=launch.launch(root/'game',state,execute=True,elevate_permission_once=explicit,permission_work=(okwork if work=='good' else work))
   except (ValueError,RuntimeError,OSError) as e:error=e
  return SimpleNamespace(result=result,error=error,os=os_api,context=context,elevate=elevate,uia=uia,validator=validator,work=okwork,session=session)
 def test_external_journal_explicit_valid_work_reaches_bound_broker_once(self):
  with tempfile.TemporaryDirectory(dir=str(Path(os.environ.get('TEMP', '.'))) ) as tmp:
   x=self.run_launch(Path(tmp),work='good');self.assertIsNone(x.error);x.os.startfile.assert_called_once();x.context.assert_called_once();x.elevate.assert_called_once()
   self.assertEqual(x.elevate.call_args[0][0],x.work);self.assertEqual(x.elevate.call_args[1],{'launch_context':{'fresh':'synthetic'}})
   self.assertEqual(x.context.call_args[0][1],12345.0);self.assertEqual(x.result['handoff_evidence']['timestamp'],12345.0)
   self.assertEqual(x.uia.call_args[0][0],x.session);self.assertFalse(x.result['launched'])
 def test_explicit_outside_work_refuses_before_handoff(self):
  with tempfile.TemporaryDirectory(dir=str(Path(os.environ.get('TEMP', '.')))) as tmp:
   root=Path(tmp);outside=root/'outside';outside.mkdir()
   x=self.run_launch(root,work=outside);self.assertIsInstance(x.error,ValueError);x.os.startfile.assert_not_called();x.elevate.assert_not_called()
 def test_legacy_external_default_uia_success_never_checks_broker_directory(self):
  with tempfile.TemporaryDirectory(dir=str(Path(os.environ.get('TEMP', '.')))) as tmp:
   x=self.run_launch(Path(tmp),permission={'acknowledged':True})
   self.assertIsNone(x.error);x.os.startfile.assert_called_once();x.uia.assert_called_once();x.validator.assert_not_called();x.elevate.assert_not_called()
   self.assertNotIn('ea_permission_broker',x.result)
 def test_legacy_external_default_broker_refusal_remains_post_handoff(self):
  with tempfile.TemporaryDirectory(dir=str(Path(os.environ.get('TEMP', '.')))) as tmp:
   x=self.run_launch(Path(tmp),broker_error=ValueError('legacy invalid broker directory'))
   self.assertIsNone(x.error);x.os.startfile.assert_called_once();x.validator.assert_not_called();x.elevate.assert_called_once()
   self.assertEqual(x.elevate.call_args[0][0],x.session)
   self.assertIn('legacy invalid broker directory',x.result['ea_permission_broker']['message']);self.assertFalse(x.result['ea_permission_broker']['acknowledged'])
 def test_no_one_shot_never_elevates_and_explicit_work_refuses(self):
  with tempfile.TemporaryDirectory(dir=str(Path(os.environ.get('TEMP', '.'))) ) as tmp:
   root=Path(tmp);x=self.run_launch(root,explicit=False);self.assertIsNone(x.error);x.os.startfile.assert_called_once();x.elevate.assert_not_called()
  with tempfile.TemporaryDirectory(dir=str(Path(os.environ.get('TEMP', '.'))) ) as tmp:
   x=self.run_launch(Path(tmp),work='good',explicit=False);self.assertIsInstance(x.error,ValueError);x.os.startfile.assert_not_called();x.elevate.assert_not_called()
 def test_uncertain_ack_or_context_error_never_elevates(self):
  for perm,error in (({'acknowledgement_unresolved':True},None),({'acknowledged':False},ValueError('synthetic expired'))):
   with self.subTest(permission=perm),tempfile.TemporaryDirectory(dir=str(Path(os.environ.get('TEMP', '.'))) ) as tmp:
    x=self.run_launch(Path(tmp),work='good',permission=perm,context_error=error);self.assertIsNone(x.error);x.os.startfile.assert_called_once();x.elevate.assert_not_called()
 def test_remembered_permission_uses_explicit_directory(self):
  with tempfile.TemporaryDirectory(dir=str(Path(os.environ.get('TEMP', '.'))) ) as tmp:
   x=self.run_launch(Path(tmp),work='good',explicit=False,remembered=True);self.assertIsNone(x.error);x.elevate.assert_called_once();self.assertEqual(x.elevate.call_args[0][0],x.work)
 def test_legacy_journal_inside_work_retains_default(self):
  with tempfile.TemporaryDirectory(dir=str(Path(os.environ.get('TEMP', '.'))) ) as tmp:
   x=self.run_launch(Path(tmp),session_under_work=True);self.assertIsNone(x.error);x.os.startfile.assert_called_once();x.elevate.assert_called_once()
   self.assertEqual(x.elevate.call_args[0][0],x.session)
 def test_cli_forwards_only_explicit_permission_work(self):
  for extra,expected in (([],None),(['--permission-work','synthetic-work'],Path('synthetic-work'))):
   args=cli.parser().parse_args(['launch','--game-root','fake','--state','fake','--elevate-permission-once']+extra)
   with patch.object(cli.game_launch,'launch',return_value={'ok':True}) as invoked:cli.execute(args)
   self.assertEqual(invoked.call_args[1].get('permission_work'),expected)
if __name__=='__main__':unittest.main(verbosity=2)
