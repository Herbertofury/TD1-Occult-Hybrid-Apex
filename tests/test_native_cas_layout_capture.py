import base64
import copy
import hashlib
import os
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import patch
from apex_core import native_cas_engine as engine,overlay_loader,sim_data,form_appearance as appearance,lifestate_forms,cas_owner_payload,cas_bank_transaction


class NativeLayoutCaptureTests(unittest.TestCase):
    def seed(self,fail=None):
        sim=Obj(id=123,tag='current edited shape',occult_tracker=object())
        owners={1:Obj(tag='human original'),2:Obj(tag='alien original')}
        backend=Obj(__file__='fixture',services=Obj(active_household=lambda:Obj(sim_info_gen=lambda:iter([sim]))),
                    _form_map=lambda tracker:owners,_get_current_flags=lambda selected:2)
        def fields(owner):
            return dict(physique=appearance.encode(owner.tag),__outfits__=appearance.encode(('protobuf',b'\xa0\x06\x01')))
        named=dict(owner_id='ghost/manifested',native_kind=1,fields=fields(Obj(tag='ghost original')),appearance_sha256='a'*64)
        raw=b'\x01\x02';capture=dict(native_base64=base64.b64encode(raw).decode('ascii'),
            native_sha256=hashlib.sha256(raw).hexdigest(),native_message_type='EA.Sims4.Persistence.SimData')
        calls=[]
        def call(module,dll,value):
            op=value['operation'];calls.append(op)
            if op=='status':return dict(ok=True,armed=True,scope_id='a'*32,members=[dict(sim_id='123',owned_mask=3)])
            if op=='activate':return dict(ok=fail!='activate',selection_enabled=fail!='activate')
            imported=dict(sim_id='123',imported_mask=3,kinds=[1,2],active_entry_source_seeded=True,canonical_source_seeded_mask=3,separate_owners=[
                dict(owner_id='ghost/manifested',native_kind=2 if fail=='named-kind' else 1)])
            return dict(ok=True,members=[imported])
        prior=dict(pid=1,scope_id='b'*32,owners={})
        with patch.object(engine,'_verify_imported_owners',return_value=dict(ok=True,owners=[])), \
                patch.object(cas_bank_transaction,'status',return_value=dict(phase='captured',expected_pending_sha256='c'*64)), \
                patch.object(engine,'_LAYOUT_SCOPE',prior),patch.object(overlay_loader,'_CALLS',{'ready':True}), \
                patch.object(overlay_loader,'native_cas_engine_control',side_effect=call), \
                patch.object(appearance,'packed',side_effect=lambda backend,owner:fields(owner)), \
                patch.object(sim_data,'snapshot',return_value=capture), \
                patch.object(lifestate_forms,'native_cas_owners',return_value=[named]), \
                patch.object(cas_owner_payload,'project_record',return_value=dict(native_hex=raw.hex(),sha256=capture['native_sha256'])), \
                patch.dict(sys.modules,{'paths':Obj(DLL_PATH='fixture')}):
            if fail:
                with self.assertRaises(ValueError):engine.seed_members(backend)
                self.assertIs(engine._LAYOUT_SCOPE,prior)
                return calls,None
            result=engine.seed_members(backend);scope=copy.deepcopy(engine._LAYOUT_SCOPE)
            self.assertTrue(result['enabled'])
        return calls,scope

    def test_fresh_native_active_and_named_owners_publish_only_representations(self):
        calls,scope=self.seed()
        self.assertEqual(calls,['status','seed','seed-canonical','seed-canonical','seed-active','seed-appearance','activate'])
        self.assertEqual(scope['pid'],os.getpid());self.assertEqual(scope['scope_id'],'a'*32)
        self.assertEqual(set(scope['owners']),{('123','native/1'),('123','native/2'),('123','active/2'),('123','ghost/manifested')})
        self.assertEqual(scope['owners'][('123','active/2')]['native_kind'],2)
        for captured in scope['owners'].values():
            self.assertEqual(captured['layout']['physique'],appearance.encode(''))
            self.assertEqual(captured['layout']['__outfits__'],appearance.encode(('protobuf',b'')))
        self.assertNotIn('original',str(scope));self.assertNotIn('current edited shape',str(scope))

    def test_failed_named_import_keeps_prior_scope_without_partial_publication(self):
        calls,_=self.seed('named-kind');self.assertNotIn('activate',calls)

    def test_failed_activation_cannot_publish_layouts_for_new_scope(self):
        calls,_=self.seed('activate');self.assertEqual(calls[-1],'activate')


if __name__=='__main__':unittest.main()
