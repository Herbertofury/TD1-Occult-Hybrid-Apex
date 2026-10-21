import copy
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'Source')]
from cas_catalog_workspace import viewport_layout,equipped_menus,inject_context
from apex_core import cas_ui,cas_controls


class CatalogWorkspaceTests(unittest.TestCase):
    def style(self):
        return dict(operation='catalog-style',columns=6,color=0x00c9eb,glow=0,
            animation='none',strength=1,period=1.4,border=3)

    def test_columns_fit_without_scaling_native_tiles(self):
        for width in (640,1024,1280,1920,2560,3840):
            for requested in range(2,13):
                layout=viewport_layout(requested,width)
                self.assertLessEqual(layout['columns'],requested)
                self.assertEqual(layout['width'],262+(layout['columns']-2)*111)
                self.assertLessEqual(layout['width'],max(262,width*.53))
        self.assertEqual(viewport_layout(6,1920)['width'],706)

    def test_invalid_slider_values_never_reach_transport(self):
        request=self.style()
        for field,values in {'columns':[True,0,13,2.5],'color':[True,-1,0x1000000],
                'glow':[float('nan'),13],'period':[0,.79,4.1],
                'border':[0,9],'strength':[False,.2,2],'animation':['strobe','unknown']}.items():
            for value in values:
                with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                    cas_ui.envelope('12',dict(request,**{field:value}))

    def test_acknowledgement_must_match_every_preference(self):
        request=self.style();cas_ui.envelope('12',request)
        prefs={k:v for k,v in request.items() if k!='operation'}
        client={'control':dict(operation='catalog-style',appearance_written=False,workspace={'preferences':prefs})}
        cas_controls.validate(client,request)
        for name in prefs:
            altered=copy.deepcopy(client);altered['control']['workspace']['preferences'][name]=None
            with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(altered,request)
        client['control']['appearance_written']=True
        with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(client,request)

    def test_equipped_inventory_cannot_acknowledge_another_owner(self):
        request={'operation':'catalog-open'};cas_ui.envelope('12',request)
        workspace=dict(visible=True,error='',context='12|native/2',items=[])
        client={'sim':{'simId':'12'},'form_strip':{'selected_owner_id':'native/2'},
            'control':dict(operation='catalog-open',appearance_written=False,workspace=workspace)}
        cas_controls.validate(client,request)
        for context in ('13|native/2','12|native/4',''):
            workspace['context']=context
            with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(client,request)

    def test_category_routes_include_jewelry_skin_details_and_tattoos(self):
        menus=equipped_menus()
        for body in (2,8,10,16,22,34,35,38,39,45,54,58):self.assertIn(str(body),menus)
        self.assertNotEqual(menus['39'],menus['45'])
        self.assertNotIn('10000',menus)  # Unknown future types are shown, not misrouted.

    def test_different_ui_contract_is_rejected_before_patching(self):
        with self.assertRaises(ValueError):inject_context('native UI changed')

    def test_radial_click_queues_without_waiting_for_transport_poll(self):
        source=(ROOT/'Source/CASUi/catalog_workspace_methods.as').read_text(encoding='utf-8')
        click=source.split('private function ApexCatalogOpen(',1)[1].split('private function ApexCatalogFrame(',1)[0]
        self.assertNotIn('CallGameService',click)
        self.assertNotIn('ApexNativeExchange',click)
        frame=source.split('private function ApexCatalogFrame(',1)[1].split('private function ApexCatalogClearEffects(',1)[0]
        self.assertIn('apexPendingFields==null && !apexReceiving',frame)
        self.assertNotIn('apexAwaiting',frame)


if __name__=='__main__':unittest.main()
