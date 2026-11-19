import copy
import os
from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core import native_cas_engine as engine,cas_bank_transaction as receiver,cas_commit_plan as primitive,cas_ui,overlay_loader


class RetirementTests(unittest.TestCase):
    def setUp(self):
        self.scope=dict(pid=os.getpid(),scope_id='a'*32,epochs={'123':'b'*64,'456':'c'*64},
            owners={('123','native/1'):{},('456','native/1'):{}},logical_owners={})
        self.enterContext(patch.object(engine,'_LAYOUT_SCOPE',self.scope))
        self.valid=self.enterContext(patch.object(receiver,'_completed',return_value=True))
        self.peers=self.enterContext(patch.object(cas_ui,'diagnostics',return_value={'native_peers':[]}))
        self.enterContext(patch.dict(sys.modules,{'paths':Obj(DLL_PATH='fixture')}))
        self.backend=Obj(__file__='matching-installed-script')
        self.original_control=overlay_loader.native_cas_engine_control
        self.native=self.enterContext(patch.object(overlay_loader,'native_cas_engine_control',return_value=dict(
            ok=True,pid=os.getpid(),scope_id='a'*32,armed=True,selection_enabled=False,
            members=[dict(sim_id=sid,imported_mask=0) for sid in ('123','456')])))

    def transaction(self,sid):
        returned=dict(identity=dict(pid=os.getpid(),scope_id='a'*32,sim_id=sid,generation=7 if sid=='123' else 8))
        return dict(transaction_sha256=self.scope['epochs'][sid],native_owner_return=returned,
            native_owner_return_sha256=primitive.digest(returned))

    def complete(self,sid):return engine.complete_return(self.backend,Obj(id=int(sid)),self.transaction(sid))

    def test_only_complete_household_retires_exact_generations_and_keeps_no_replay_authority(self):
        first=self.complete('123');self.assertFalse(first['retired']);self.native.assert_not_called()
        self.assertIs(engine._LAYOUT_SCOPE,self.scope)
        result=self.complete('456');self.assertTrue(result['retired']);self.assertIsNone(engine._LAYOUT_SCOPE)
        request=self.native.call_args.args[2]
        self.assertEqual(request,dict(operation='retire-committed-session',scope_id='a'*32,
            members=[dict(sim_id='123',generation=7),dict(sim_id='456',generation=8)]))
        self.assertFalse(result['appearance_written']);self.assertFalse(result['native_write_replay_authorized'])

    def test_unfinished_receiver_foreign_scope_or_changed_archive_never_disposes_graph(self):
        for damage in ('unfinished','epoch','archive','scope'):
            with self.subTest(damage=damage):
                transaction=self.transaction('123');self.valid.return_value=damage!='unfinished'
                if damage=='epoch':transaction['transaction_sha256']='d'*64
                elif damage=='archive':transaction['native_owner_return']['identity']['generation']+=1
                elif damage=='scope':
                    transaction['native_owner_return']['identity']['scope_id']='d'*32
                    transaction['native_owner_return_sha256']=primitive.digest(transaction['native_owner_return'])
                with self.assertRaises(ValueError):engine.complete_return(self.backend,Obj(id=123),transaction)
                self.native.assert_not_called();self.assertNotIn('retirement_attempted',self.scope)

    def test_attached_peer_defers_retirement_until_next_owned_boundary_without_replaying_commits(self):
        self.complete('123');self.peers.return_value={'native_peers':[dict(sim_id='456')]}
        with self.assertRaisesRegex(ValueError,'peer still owns'):self.complete('456')
        self.native.assert_not_called();self.assertNotIn('retirement_attempted',self.scope)
        self.peers.return_value={'native_peers':[]}
        result=engine._retire_completed_scope(self.backend,self.scope)
        self.assertTrue(result['retired']);self.native.assert_called_once()

    def test_ambiguous_native_retirement_retains_attempt_and_cannot_replay(self):
        self.complete('123');self.native.side_effect=OSError('Native reply lost')
        with self.assertRaises(OSError):self.complete('456')
        self.assertTrue(self.scope['retirement_attempted']);self.assertIs(engine._LAYOUT_SCOPE,self.scope)
        with self.assertRaisesRegex(ValueError,'no automatic replay'):engine._retire_completed_scope(self.backend,self.scope)
        self.native.assert_called_once()

    def test_retirement_is_not_a_public_research_control(self):
        with self.assertRaises(ValueError):engine.argument(dict(operation='retire-committed-session',scope_id='a'*32,members=[]))

    def test_real_loader_validation_accepts_only_the_held_completed_capability(self):
        self.complete('123')
        # Complete the second receiver but retain the attempted scope instead
        # of letting the mocked native success consume it.
        self.native.side_effect=OSError('Retain the exact attempted scope')
        with self.assertRaises(OSError):self.complete('456')
        value=dict(operation='retire-committed-session',scope_id='a'*32,
            members=[dict(sim_id='123',generation=7),dict(sim_id='456',generation=8)])
        # Exercise the real loader wrapper, not a mock that bypasses its public
        # argument validator. The ABI-only leaf remains isolated from the host.
        with patch.object(overlay_loader,'native_cas_engine_control',self.original_control), \
                patch.object(overlay_loader,'_native_cas_engine_call',return_value={'ok':True}) as abi:
            with self.assertRaises(ValueError):overlay_loader.native_cas_engine_control('module','dll',value)
            with self.assertRaises(ValueError):overlay_loader.native_cas_engine_control('module','dll',value,
                _retirement_capability=copy.deepcopy(self.scope))
            abi.assert_not_called()
            self.assertTrue(overlay_loader.native_cas_engine_control('module','dll',value,
                _retirement_capability=self.scope)['ok'])
            abi.assert_called_once_with('module','dll',value)


if __name__=='__main__':unittest.main()
