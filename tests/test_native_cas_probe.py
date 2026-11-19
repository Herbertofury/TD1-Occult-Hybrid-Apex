import copy,json,os,sys
from pathlib import Path
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core import overlay_loader,test_driver
import test_overlay_loader as overlay_fixture


class NativeProbeLoaderTests(unittest.TestCase):
    setUp = overlay_fixture.OverlayLoaderTests.setUp
    def test_probe_has_zero_arguments_exact_loaded_sidecar_and_no_write_claim(self):
        seen=[]
        value=dict(ok=True,pid=os.getpid(),exe_sha256='916b852b187b9c41b9c2d77af55e0d5ed6aaf06909661397d7aa98f2e4db78ab',
            own_process_only=True,read_only=True,game_memory_written=False,game_files_written=False,
            memory_dump_written=False,native_patch_qualified=False,disk_text_sha256='a'*64,
            runtime_text_sha256='b'*64,runtime_text_matches_disk=False)
        class Function:
            def __init__(self,symbol):seen.append(symbol[0])
            def __call__(self):return json.dumps(value).encode('utf-8')
        native=Obj(_SimpleCData=object,CFuncPtr=Function,FUNCFLAG_STDCALL=0)
        manifest=json.loads(self.manifest.read_text())
        with patch.object(overlay_loader,'_CALLS',object()),patch.object(overlay_loader,'_LOADED_SHA',manifest['sha256']),\
                patch.object(overlay_loader,'_LOADED_PATH',str(self.dll)),patch.object(overlay_loader,'_HANDLE',object()),\
                patch.object(overlay_loader,'_game_ctypes',return_value=native):
            self.assertEqual(overlay_loader.native_cas_probe(self.module,'unused'),value)
            for change in (dict(game_memory_written=True),dict(game_files_written=True),dict(read_only=False),
                    dict(native_patch_qualified=True),dict(own_process_only=False),dict(pid=os.getpid()+1),
                    dict(exe_sha256='f'*64),dict(disk_text_sha256='bad'),dict(runtime_text_matches_disk=True)):
                old=copy.deepcopy(value);value.update(change)
                with self.subTest(change=change),self.assertRaises(ValueError):
                    overlay_loader.native_cas_probe(self.module,'unused')
                value.clear();value.update(old)
        self.assertEqual(set(seen),{'ApexNativeCasProbe'})

    def test_unloaded_or_replaced_sidecar_never_binds_a_native_probe(self):
        with patch.object(overlay_loader,'_CALLS',None),patch.object(overlay_loader,'_game_ctypes') as bind:
            with self.assertRaisesRegex(ValueError,'not loaded'):
                overlay_loader.native_cas_probe(self.module,'unused')
            bind.assert_not_called()
        with patch.object(overlay_loader,'_CALLS',object()),patch.object(overlay_loader,'_LOADED_SHA','f'*64),\
                patch.object(overlay_loader,'_game_ctypes') as bind:
            with self.assertRaisesRegex(ValueError,'changed'):
                overlay_loader.native_cas_probe(self.module,'unused')
            bind.assert_not_called()


class NativeProbeDispatchTests(unittest.TestCase):
    def test_exact_disposable_guard_precedes_read_only_native_call_without_sim_mutation(self):
        backend=Obj(__file__='owned/ApexOccultHybrid.ts4script/main.pyc')
        reply=dict(ok=True,read_only=True)
        with patch.object(test_driver,'guard',return_value=None) as guard,\
                patch.dict(sys.modules,{'paths':Obj(DLL_PATH='game-dlls')}),\
                patch.object(overlay_loader,'native_cas_probe',return_value=reply) as probe:
            self.assertEqual(test_driver.dispatch(backend,'test_native_cas_probe',None,'bounded-token'),reply)
            guard.assert_called_once_with(backend,'bounded-token')
            probe.assert_called_once_with(backend.__file__,'game-dlls')

    def test_addresses_operations_and_bad_token_cannot_reach_native_reader(self):
        for argument in ('0x140000000',{'address':123},{'operation':'patch'},False):
            with self.subTest(argument=argument),patch.object(test_driver,'guard',return_value=argument),\
                    patch.object(overlay_loader,'native_cas_probe') as probe:
                with self.assertRaisesRegex(ValueError,'no addresses'):
                    test_driver.dispatch(Obj(),'test_native_cas_probe',None,'request')
                probe.assert_not_called()
        with patch.object(test_driver,'guard',side_effect=ValueError('wrong disposable token')),\
                patch.object(overlay_loader,'native_cas_probe') as probe:
            with self.assertRaisesRegex(ValueError,'token'):
                test_driver.dispatch(Obj(),'test_native_cas_probe',None,'wrong')
            probe.assert_not_called()
