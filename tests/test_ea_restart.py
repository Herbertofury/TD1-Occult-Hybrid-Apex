"""Independent closed-profile EA lifetime and registry fixtures; no real actions."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import ea_restart as restart
import apex_cli


class Layers:
    def __init__(self, value): self.value=value;self.writes=[]
    def read(self,_name):return self.value
    def write(self,name,value):self.writes.append((name,value));self.value=value


class RestartTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name).resolve();self.profile=self.root/'profile';self.original=self.root/'original'
        (self.profile/'saves').mkdir(parents=True);self.original.mkdir()
        for index in range(18):(self.profile/'saves'/('save-'+str(index)+'.bin')).write_bytes(bytes([index])*17)
        self.image=self.root/'install'/'EADesktop.exe';self.image.parent.mkdir();self.image.write_bytes(b'exact EA executable fixture')
        self.state=self.root/'state.json';self.state.write_text('{}');self.output=self.root/'operation.json'
        self.layers=Layers('~ RUNASADMIN WIN7RTM HIGHDPIAWARE');self.machine=None
        self.old={'pid':11,'creation_time':100,'image':str(self.image),'session_id':1,'elevated':True,'ui_access':False,'integrity':12288}
        self.new=dict(self.old,pid=12,creation_time=101,elevated=False,integrity=8192)
        self.host=dict(self.new,pid=os.getpid(),creation_time=50,image=str(Path(sys.executable).resolve()))
        self.live_rows={11:self.old};self.actions=[];self.now=0.;self.game_open=False;self.ready=True
        self.close_stays=False;self.close_denied=False;self.started_identity=self.new
        self.journal={'token':'a'*32}
        for manager in (
            patch.object(restart.reusable_profile,'load',return_value=(self.state,self.journal,self.profile,self.original)),
            patch.object(restart.test_profile,'require_closed',side_effect=self.closed),
            patch.object(restart.test_profile,'status',side_effect=lambda _s:{'ready_to_launch':self.ready})):
            manager.start();self.addCleanup(manager.stop)

    def closed(self):
        if self.game_open:raise ValueError('Game is open; no EA operation.')

    def diagnostic(self):
        return {'ok':len(self.live_rows)==1,'targets':list(self.live_rows.values()),'failures':[],'ignored_processes':[]}

    def probe(self,pid):return copy.deepcopy(self.host if pid==os.getpid() else self.live_rows[pid])
    def live(self,row):return self.live_rows.get(row['pid'])==row
    def pause(self,duration):self.now+=duration
    def close(self,target,force,guard,deadline):
        guard();self.actions.append(('normal-close',target['pid']))
        if self.close_denied:raise OSError(5,'Access denied at lower integrity.')
        if not self.close_stays:self.live_rows.pop(target['pid'])
        return {'ok':not self.close_stays,'closed':not self.close_stays,'forced':False}
    def elevated(self,state,journal,profile,target,image_hash,force,output,deadline,**kwargs):
        self.closed();self.actions.append(('elevated-close-only',target['pid']));self.live_rows.pop(target['pid'])
        return {'ok':True,'closed':True,'ea_started':False,'windows_uac_automated':False}
    def start(self,image):
        self.assertEqual(image,self.image);self.assertEqual(self.live_rows,{})
        self.assertEqual(json.loads(self.output.read_text())['ea_start_submitted'],True)
        self.actions.append(('normal-start',self.host['integrity']))
        if self.started_identity is not None:self.live_rows[self.started_identity['pid']]=copy.deepcopy(self.started_identity)
    def operate(self,operation='restart',**options):
        return restart.run(self.state,operation,self.output,image=self.image,layers=self.layers,
            machine=lambda _p:self.machine,manifest=lambda _p:'asInvoker',probe=self.probe,
            diagnostic=self.diagnostic,live=self.live,close=self.close,elevated_close=self.elevated,
            start=self.start,inventory=lambda:list(self.live_rows),clock=lambda:self.now,pause=self.pause,**options)

    def test_restart_removes_exact_hkcu_token_preserves_account_and_all18files_and_uses_medium_host(self):
        before={p.name:p.read_bytes() for p in (self.profile/'saves').iterdir()}
        result=self.operate(normal_permissions=True);self.assertTrue(result['ok'])
        self.assertEqual(self.layers.value,'~ WIN7RTM HIGHDPIAWARE')
        self.assertEqual(self.layers.writes,[(str(self.image),'~ WIN7RTM HIGHDPIAWARE')])
        self.assertEqual(self.actions,[('normal-close',11),('normal-start',8192)])
        proof=json.loads(self.output.read_text());self.assertEqual(len(proof['before_saves']),18)
        self.assertEqual(proof['before_saves'],proof['after_saves']);self.assertFalse(proof['account_files_written_by_tool'])
        self.assertEqual(before,{p.name:p.read_bytes() for p in (self.profile/'saves').iterdir()})
        self.assertEqual(self.image.read_bytes(),b'exact EA executable fixture')

    def test_verified_absence_starts_once_without_close_or_elevated_worker(self):
        self.live_rows.clear();result=self.operate(normal_permissions=True,elevate_close_once=True,force_if_tray=True)
        self.assertTrue(result['ok']);self.assertEqual(self.actions,[('normal-start',8192)])

    def test_status_is_passive_and_does_not_change_layers_close_or_start(self):
        result=self.operate(operation='status');self.assertTrue(result['ok'])
        self.assertEqual(self.actions,[]);self.assertEqual(self.layers.writes,[])

    def test_known_live_game_and_changed_profile_refuse_before_any_registry_or_process_action(self):
        self.game_open=True;result=self.operate(normal_permissions=True);self.assertFalse(result['ok'])
        self.assertEqual(self.actions,[]);self.assertEqual(self.layers.writes,[])
        self.output=self.root/'second.json';self.game_open=False;self.ready=False
        result=self.operate(normal_permissions=True);self.assertFalse(result['ok']);self.assertEqual(self.actions,[])

    def test_unknown_duplicate_wrong_install_or_wrong_session_ea_refuse(self):
        for name in ('unknown','duplicate','wrong-image','wrong-session'):
            if name=='unknown':self.diagnostic=lambda:{'ok':False,'targets':[],'failures':[{'error':'denied'}]}
            elif name=='duplicate':self.diagnostic=lambda:{'ok':False,'targets':[self.old,self.new],'failures':[]}
            else:
                row=dict(self.old,image=str(self.root/'other.exe')) if name=='wrong-image' else dict(self.old,session_id=2)
                self.diagnostic=lambda row=row:{'ok':True,'targets':[row],'failures':[]}
            self.output=self.root/(name+'.json');result=self.operate(normal_permissions=True)
            self.assertFalse(result['ok']);self.assertEqual(self.layers.writes,[]);self.assertEqual(self.actions,[])

    def test_host_elevation_and_machine_forced_admin_are_not_bypassed(self):
        self.host['elevated']=True;self.host['integrity']=12288
        result=self.operate(normal_permissions=True);self.assertFalse(result['ok']);self.assertEqual(self.actions,[])
        self.host.update(elevated=False,integrity=8192);self.output=self.root/'machine.json';self.machine='~ RUNASADMIN'
        result=self.operate(normal_permissions=True);self.assertFalse(result['ok']);self.assertEqual(self.layers.writes,[])

    def test_elevated_close_helper_never_launches_new_ea_and_host_alone_starts_medium(self):
        self.close_denied=True
        result=self.operate(normal_permissions=True,force_if_tray=True,elevate_close_once=True)
        self.assertTrue(result['ok']);self.assertEqual(self.actions,[('normal-close',11),('elevated-close-only',11),('normal-start',8192)])

    def test_no_implicit_elevation_or_force_after_denied_or_tray_close(self):
        self.close_denied=True;result=self.operate(normal_permissions=True);self.assertFalse(result['ok'])
        self.assertEqual(self.actions,[('normal-close',11)])
        self.output=self.root/'tray.json';self.actions=[];self.close_denied=False;self.close_stays=True
        result=self.operate();self.assertFalse(result['ok']);self.assertEqual(self.actions,[('normal-close',11)])

    def test_new_elevated_reused_pid_or_foreign_session_client_is_not_reported_normal(self):
        for field,value in [('elevated',True),('integrity',12288),('pid',11),('creation_time',100),('session_id',2)]:
            self.live_rows={11:self.old};self.started_identity=dict(self.new,**{field:value})
            self.output=self.root/('new-'+field+'.json');result=self.operate(normal_permissions=True)
            self.assertFalse(result['ok']);self.assertEqual(sum(action[0]=='normal-start' for action in self.actions),1)
            self.actions=[]

    def test_start_timeout_never_repeats_normal_start(self):
        self.started_identity=None;result=self.operate(normal_permissions=True,seconds=1)
        self.assertFalse(result['ok']);self.assertEqual(self.now,1)
        self.assertEqual(self.actions,[('normal-close',11),('normal-start',8192)])

    def test_exact_hash_restore_preserves_other_flags_and_never_changes_processes(self):
        result=self.operate(normal_permissions=True);self.assertTrue(result['ok'])
        recovery=self.output;digest=restart.sha256(recovery);immutable=recovery.read_bytes()
        self.output=self.root/'restore.json';self.actions=[]
        restored=self.operate(operation='restore',recovery=recovery,expected_recovery_sha256=digest)
        self.assertTrue(restored['ok']);self.assertEqual(self.layers.value,'~ RUNASADMIN WIN7RTM HIGHDPIAWARE')
        self.assertEqual(self.actions,[]);self.assertEqual(recovery.read_bytes(),immutable)

    def test_restore_refuses_external_user_edit_and_wrong_recovery_hash(self):
        self.assertTrue(self.operate(normal_permissions=True)['ok']);recovery=self.output;digest=restart.sha256(recovery)
        self.output=self.root/'restore.json';self.layers.value='~ WIN10RTM';self.actions=[];count=len(self.layers.writes)
        result=self.operate(operation='restore',recovery=recovery,expected_recovery_sha256=digest)
        self.assertFalse(result['ok']);self.assertEqual(len(self.layers.writes),count);self.assertEqual(self.actions,[])
        self.output=self.root/'wrong.json'
        result=self.operate(operation='restore',recovery=recovery,expected_recovery_sha256='f'*64)
        self.assertFalse(result['ok']);self.assertEqual(len(self.layers.writes),count)

    def test_existing_proof_and_profile_output_refuse_before_actions(self):
        self.output.write_text('immutable')
        with self.assertRaises(ValueError):self.operate(normal_permissions=True)
        self.assertEqual(self.output.read_text(),'immutable');self.assertEqual(self.actions,[])
        self.output=self.profile/'inside.json'
        with self.assertRaises(ValueError):self.operate()

    def test_public_cli_dispatch_is_typed_without_overlay_or_launch_commands(self):
        args=apex_cli.parser().parse_args(['ea-restart','restart','--state',str(self.state),'--output',str(self.output),
            '--normal-permissions','--force-if-tray','--elevate-close-once','--seconds','25'])
        with patch.object(restart,'run',return_value={'ok':True}) as call:
            self.assertTrue(apex_cli.execute(args)['ok'])
        self.assertEqual(call.call_args.kwargs['seconds'],25)
        self.assertTrue(call.call_args.kwargs['normal_permissions']);self.assertTrue(call.call_args.kwargs['force_if_tray'])

    def test_asynchronous_normal_exit_during_passive_wait_still_allows_one_medium_restart(self):
        checks=[0]
        def observed_live(target):
            checks[0]+=1
            answer=self.live(target)
            if checks[0]==3:self.live_rows.pop(target['pid'],None)
            return answer
        def request_close(target,action_guard):
            action_guard();self.actions.append(('normal-close',target['pid']));return {}
        self.close=lambda target,force,guard,deadline:restart.close_once(target,force,guard,deadline,
            live=observed_live,close=request_close,windows=lambda _p:[],clock=lambda:self.now,pause=self.pause)
        result=self.operate(normal_permissions=True)
        self.assertTrue(result['ok']);self.assertEqual(self.actions,[('normal-close',11),('normal-start',8192)])

    def test_changed_disposable_token_cannot_retarget_a_ready_profile(self):
        first=(self.state,copy.deepcopy(self.journal),self.profile,self.original)
        changed=(self.state,{'token':'b'*32},self.profile,self.original)
        with patch.object(restart.reusable_profile,'load',side_effect=[first,changed]):
            result=self.operate(normal_permissions=True)
        self.assertFalse(result['ok']);self.assertEqual(self.actions,[]);self.assertEqual(self.layers.writes,[])

    def test_legacy_default_ea_manifest_still_requires_actual_new_medium_token(self):
        with patch.object(restart,'ea_execution_level',return_value='legacy-default'):
            # Injectable resource-reader output is distinct from the game parser.
            result=restart.run(self.state,'restart',self.output,image=self.image,layers=self.layers,
                machine=lambda _p:None,manifest=lambda _p:'legacy-default',probe=self.probe,
                diagnostic=self.diagnostic,live=self.live,close=self.close,start=self.start,
                inventory=lambda:list(self.live_rows),clock=lambda:self.now,pause=self.pause,normal_permissions=True)
        self.assertTrue(result['ok']);self.assertEqual(json.loads(self.output.read_text())['execution_level'],'legacy-default')

    def make_worker_request(self):
        nonce='c'*32;path=self.root/('ea-restart-'+nonce+'.request.json')
        request={'schema':1,'nonce':nonce,'expires_at':time.time()+60,'state':str(self.state),
            'token':self.journal['token'],'profile':str(self.profile),'target':self.old,
            'image_sha256':restart.sha256(self.image),'force_if_tray':True,
            'source_sha256':{name:restart.sha256(restart.TOOLS/name) for name in restart.PINS}}
        path.write_text(json.dumps(request));return path,request

    def call_worker(self,path,action):
        helper=dict(self.host,elevated=True,integrity=12288)
        with patch.object(restart,'EA_IMAGE',self.image):
            return restart.worker(path,restart.sha256(restart.__file__),probe=lambda _p:helper,action=action)

    def test_close_only_worker_claim_before_write_and_duplicate_never_replays_after_lost_ack(self):
        path,request=self.make_worker_request();immutable=path.read_bytes();events=[]
        def action(target,force,guard,deadline):
            guard();self.assertTrue(path.with_name('ea-restart-'+request['nonce']+'.claim.json').exists())
            events.append(('close-only',target['pid']));return {'ok':True,'closed':True}
        result=self.call_worker(path,action)
        receipt=path.with_name('ea-restart-'+request['nonce']+'.receipt.json');ack=receipt.read_bytes()
        self.assertTrue(result['ok']);self.assertFalse(result['ea_started']);self.assertFalse(result['windows_uac_automated'])
        with self.assertRaises(FileExistsError):self.call_worker(path,action)
        self.assertEqual(events,[('close-only',11)]);self.assertEqual(receipt.read_bytes(),ack);self.assertEqual(path.read_bytes(),immutable)

    def test_worker_expired_wrong_source_wrong_identity_and_open_game_cannot_reach_original_action(self):
        path,original=self.make_worker_request();events=[]
        for mode in ('expired','source','identity','game','token'):
            request=copy.deepcopy(original);self.game_open=False
            if mode=='expired':request['expires_at']=time.time()-1
            elif mode=='source':request['source_sha256']['ea_restart.py']='f'*64
            elif mode=='identity':request['target']['image']=str(self.root/'other.exe')
            elif mode=='game':self.game_open=True
            else:request['token']='b'*32
            path.write_text(json.dumps(request))
            with self.assertRaises(ValueError):self.call_worker(path,lambda *a:events.append(a))
        self.assertEqual(events,[]);self.assertFalse(path.with_name('ea-restart-'+original['nonce']+'.claim.json').exists())


class CloseOnlyTests(unittest.TestCase):
    def test_lifetime_change_immediately_before_native_close_refuses_without_message(self):
        calls=[0];events=[]
        def live(_target):
            calls[0]+=1
            if calls[0]>1:raise ValueError('Exact EA creation time or token changed.')
            return True
        def close(target,guard):guard();events.append('WM_CLOSE');return {}
        with self.assertRaises(ValueError):restart.close_once({'pid':11},False,lambda:None,5,
            live=live,close=close,clock=lambda:0,windows=lambda _p:[])
        self.assertEqual(events,[])
    def test_close_tray_requires_explicit_force_and_checks_guard_before_terminate(self):
        for force in (False,True):
            now=[0.];alive=[True];events=[]
            def guard():events.append('guard')
            def terminate(target,current_guard):current_guard();events.append('terminate');alive[0]=False
            result=restart.close_once({'pid':11},force,guard,5,live=lambda _t:alive[0],
                close=lambda _t,g:(g() or {'normal_close_requested':True}),terminate=terminate,
                windows=lambda _p:[],clock=lambda:now[0],pause=lambda d:now.__setitem__(0,now[0]+d))
            self.assertEqual(result['closed'],force);self.assertEqual(events.count('terminate'),int(force))

    def test_visible_window_no_force_and_pid_change_never_terminate(self):
        now=[0.];terminated=[]
        with self.assertRaises(ValueError):
            restart.close_once({'pid':11},True,lambda:None,5,live=lambda _t:True,
                close=lambda _t,g:{},terminate=lambda *x:terminated.append(x),windows=lambda _p:[123],
                clock=lambda:now[0],pause=lambda d:now.__setitem__(0,now[0]+d))
        self.assertEqual(terminated,[])


class ManifestTests(unittest.TestCase):
    def test_actual_legacy_structure_and_utf16_are_explicit_default_not_game_manifest_relaxation(self):
        raw=b'<assembly xmlns="urn:schemas-microsoft-com:asm.v1"><compatibility xmlns="urn:schemas-microsoft-com:compatibility.v1"><application><supportedOS Id="{known}"/></application></compatibility></assembly>'
        self.assertEqual(restart._manifest_level(raw),'legacy-default')
        self.assertEqual(restart._manifest_level(raw.decode().encode('utf-16')),'legacy-default')
    def test_partial_privilege_duplicate_unknown_uiaccess_and_external_entities_refuse(self):
        for text in ('<not-assembly/>','<assembly xmlns="urn:unknown"/>','<assembly><trustInfo/></assembly>',
            '<assembly><requestedPrivileges/></assembly>',
            '<assembly><requestedExecutionLevel level="asInvoker"/><requestedExecutionLevel level="asInvoker"/></assembly>',
            '<assembly><requestedExecutionLevel level="unknown"/></assembly>',
            '<assembly><requestedExecutionLevel level="asInvoker" uiAccess="true"/></assembly>',
            '<!DOCTYPE assembly [<!ENTITY local SYSTEM "file:///private">]><assembly/>'):
            for raw in (text.encode(),text.encode('utf-16')):
                with self.assertRaises(ValueError):restart._manifest_level(raw)
        for level in ('asInvoker','highestAvailable','requireAdministrator'):
            self.assertEqual(restart._manifest_level(('<assembly><requestedExecutionLevel level="'+level+'"/></assembly>').encode()),level)


if __name__=='__main__':unittest.main()
