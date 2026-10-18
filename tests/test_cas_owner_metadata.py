from pathlib import Path
import sys
from types import SimpleNamespace as Obj
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import cas_ui, overlay_loader
from test_cas_occult_view import OccultViewTests
import test_cas_form_select as fixture


class OwnerMetadataTests(OccultViewTests):
    def test_complete_named_catalog_is_paged_without_commands_or_game_owner_reads(self):
        self.backend.__file__ = 'fixture-script'
        rows = [dict(owner_id='native/1',native_kind=1,ui_token=0x20010000)]
        rows += [dict(owner_id='ghost/look_'+str(i), native_kind=1, ui_token=0x20000000+i) for i in range(33)]
        status = dict(owner_view_adapter_available=True, members=[dict(sim_id=fixture.SIM, separate_owners=rows,
            human_owner_id='native/1',graph_selected_owner_id='ghost/look_1')])
        selected = dict(available=True, sim_id=fixture.SIM, owner_id='ghost/look_1', native_kind=1, layer=1, state='bound',generation=1)
        calls = []
        def native(_module, _path, value):
            calls.append(value['operation'])
            return status if value['operation']=='status' else selected
        with patch.object(overlay_loader,'_CALLS',{'ready':True}), \
                patch.object(overlay_loader,'native_cas_engine_control',side_effect=native), \
                patch.object(cas_ui,'client_owned_mask',return_value=69), \
                patch.dict(sys.modules,{'paths':Obj(DLL_PATH='fixture')}):
            first=cas_ui.owner_metadata(self.peer,self.backend)
            second=cas_ui.owner_metadata(self.peer,self.backend)
            third=cas_ui.owner_metadata(self.peer,self.backend)
            self.assertIsNone(cas_ui.owner_metadata(self.peer,self.backend))
            selected.update(layer=0, state='unbound')
            changed=cas_ui.owner_metadata(self.peer,self.backend)
            self.assertIsNone(cas_ui.owner_metadata(self.peer,self.backend))
            selected['generation']=2
            rebound=cas_ui.owner_metadata(self.peer,self.backend)
            self.assertIsNone(cas_ui.owner_metadata(self.peer,self.backend))
        self.assertTrue(first.startswith('OWNERS|0|34|'))
        self.assertEqual(len(first.split('|')[3].split(';')),32)
        self.assertTrue(second.startswith('OWNERS|32|34|'))
        self.assertEqual(third,'OWNERSTATE|ghost/look_1|1|1|bound')
        self.assertEqual(changed,'OWNERSTATE|ghost/look_1|1|0|unbound')
        self.assertEqual(rebound,changed)
        self.assertEqual(calls,['status']+['view-status']*6)
        self.assertFalse(cas_ui._RECORDS)

    def test_reconnected_peer_gets_catalog_and_state_even_when_the_appearance_is_unchanged(self):
        self.backend.__file__='fixture-script'
        selected=dict(available=True,sim_id=fixture.SIM,owner_id='native/1',native_kind=1,layer=0,state='bound',generation=1)
        status=dict(owner_view_adapter_available=True,members=[dict(sim_id=fixture.SIM,
            separate_owners=[dict(owner_id='native/1',native_kind=1,ui_token=0x20000000)],
            human_owner_id='native/1',graph_selected_owner_id='native/1')])
        def native(_module,_path,value):
            return status if value['operation']=='status' else selected
        with patch.object(overlay_loader,'_CALLS',{'ready':True}), \
                patch.object(overlay_loader,'native_cas_engine_control',side_effect=native), \
                patch.object(cas_ui,'client_owned_mask',return_value=69), \
                patch.dict(sys.modules,{'paths':Obj(DLL_PATH='fixture')}):
            for peer in (self.peer,cas_ui.attach_client(fixture.SIM,clock=lambda:11)):
                self.assertTrue(cas_ui.owner_metadata(peer,self.backend).startswith('OWNERS|0|1|'))
                self.assertEqual(cas_ui.owner_metadata(peer,self.backend),'OWNERSTATE|native/1|1|0|bound')
                self.assertIsNone(cas_ui.owner_metadata(peer,self.backend))
        self.assertFalse(cas_ui._RECORDS)

    def test_departed_peer_cannot_publish_a_late_state(self):
        self.backend.__file__='fixture-script'
        cas_ui._PEERS[self.peer].update(owner_catalog=[],owner_catalog_offset=0)
        def native(_module,_path,_value):
            cas_ui.detach_client(self.peer)
            return dict(available=True,sim_id=fixture.SIM,owner_id='native/1',native_kind=1,layer=0,state='bound',generation=1)
        with patch.object(overlay_loader,'_CALLS',{'ready':True}), \
                patch.object(overlay_loader,'native_cas_engine_control',side_effect=native), \
                patch.object(cas_ui,'client_owned_mask',return_value=69), \
                patch.dict(sys.modules,{'paths':Obj(DLL_PATH='fixture')}):
            self.assertIsNone(cas_ui.owner_metadata(self.peer,self.backend))
        self.assertNotIn(self.peer,cas_ui._PEERS)

    def test_no_loaded_native_adapter_keeps_the_ordinary_cas_transport_available(self):
        with patch.object(overlay_loader,'_CALLS',None):
            self.assertIsNone(cas_ui.owner_metadata(self.peer,self.backend))
