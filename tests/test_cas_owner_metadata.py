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
        rows = [dict(owner_id='ghost/look_'+str(i), native_kind=1, ui_token=0x20000000+i) for i in range(33)]
        status = dict(owner_view_adapter_available=True, members=[dict(sim_id=fixture.SIM, separate_owners=rows)])
        selected = dict(available=True, sim_id=fixture.SIM, owner_id='ghost/look_1', native_kind=1, layer=1, state='bound')
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
        self.assertTrue(first.startswith('OWNERS|0|33|'))
        self.assertEqual(len(first.split('|')[3].split(';')),32)
        self.assertTrue(second.startswith('OWNERS|32|33|'))
        self.assertEqual(third,'OWNERSTATE|ghost/look_1|1|1|bound')
        self.assertEqual(calls,['status','view-status'])
        self.assertFalse(cas_ui._RECORDS)

    def test_no_loaded_native_adapter_keeps_the_ordinary_cas_transport_available(self):
        with patch.object(overlay_loader,'_CALLS',None):
            self.assertIsNone(cas_ui.owner_metadata(self.peer,self.backend))
