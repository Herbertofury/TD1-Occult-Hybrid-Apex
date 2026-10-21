import copy
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'Source')]
from cas_catalog_workspace import viewport_layout,native_catalog_clamp,equipped_menus,inject_context,inject_plan
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

    def test_native_attachment_clamp_reserves_the_complete_catalog(self):
        for width in (640,1278,1920,2560):
            for columns in range(2,13):
                x=native_catalog_clamp(columns,width,418)
                self.assertGreaterEqual(x,0)
                self.assertLessEqual(x+viewport_layout(columns,width)['width'],width-12)
        self.assertEqual(native_catalog_clamp(6,1278,418),671)

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
        workspace=dict(visible=True,error='',context='12|native/2',items=[],outfit={'category':0,'index':1})
        client={'sim':{'simId':'12'},'form_strip':{'selected_owner_id':'native/2'},
            'outfit':{'outfit_type':0,'outfit_index':1},
            'control':dict(operation='catalog-open',appearance_written=False,workspace=workspace)}
        cas_controls.validate(client,request)
        for context in ('13|native/2','12|native/4',''):
            workspace['context']=context
            with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(client,request)
        workspace['context']='12|native/2';workspace['outfit']['index']=0
        with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(client,request)

    def test_category_routes_include_jewelry_skin_details_and_tattoos(self):
        menus=equipped_menus()
        for body in (2,8,10,16,22,34,35,38,39,45,54,58):self.assertIn(str(body),menus)
        self.assertNotEqual(menus['39'],menus['45'])
        self.assertNotIn('10000',menus)  # Unknown future types are shown, not misrouted.

    def test_different_ui_contract_is_rejected_before_patching(self):
        with self.assertRaises(ValueError):inject_context('native UI changed')
        with self.assertRaises(ValueError):inject_plan('native UI changed')

    def test_outfit_header_clamp_changes_only_inspected_anchors(self):
        native='"clampX":{"max":LayoutAPI.StageWidth - param4}\n         if(_loc2_ == this.mAnimExtension.IsVisible())'
        made=inject_plan(native)
        self.assertIn('Math.max(param4,this.mWidth + 12)',made)
        self.assertIn('typeof param1.apex_view_x_offset=="number"',made)
        self.assertIn('isFinite(param1.apex_screen_x_max)',made)
        self.assertIn('this.mWidth>=262 && this.mWidth<=1372',made)
        self.assertNotIn('CasSelectPlannedOutfit',made)
        self.assertTrue(made.endswith('if(_loc2_ == this.mAnimExtension.IsVisible())'))
        with self.assertRaises(ValueError):inject_plan(made)

    def test_radial_click_queues_without_waiting_for_transport_poll(self):
        source=(ROOT/'Source/CASUi/catalog_workspace_methods.as').read_text(encoding='utf-8')
        click=source.split('private function ApexCatalogOpen(',1)[1].split('private function ApexCatalogFrame(',1)[0]
        self.assertNotIn('CallGameService',click)
        self.assertNotIn('ApexNativeExchange',click)
        frame=source.split('private function ApexCatalogFrame(',1)[1].split('private function ApexCatalogClearEffects(',1)[0]
        self.assertIn('apexPendingFields==null && !apexReceiving',frame)
        self.assertNotIn('apexAwaiting',frame)

    def test_selection_styling_keeps_native_layout_and_thumb_motion_separate(self):
        source=(ROOT/'Source/CASUi/catalog_workspace_methods.as').read_text(encoding='utf-8')
        signature=source.split('var signature:String=',1)[1].split(';',1)[0]
        self.assertNotIn('color',signature)
        self.assertNotIn('glow',signature)
        self.assertNotIn('border',signature)
        slide=source.split('private function ApexCatalogSlide(',1)[1].split('private function ApexCatalogSlideEnd(',1)[0]
        self.assertIn('thumb.x=300*ratio',slide)
        self.assertNotIn('apexCatalogSignature=',slide)
        self.assertNotIn('ApexCatalogDraw(',slide)

    def test_slider_acknowledges_thumb_and_value_without_pointer_input(self):
        for name in ('columns','red','green','blue','glow','border','period','strength'):
            with self.subTest(control=name):
                request=dict(operation='catalog-slider',control=name,fraction=.4)
                cas_ui.envelope('12',request)
                value={'columns':6,'color':0x666666,'glow':4.8,'border':3.8,'period':2.08,'strength':.55}
                workspace=dict(visible=True,view='style',preferences=value,slider_thumbs={name:.4})
                client={'control':dict(operation='catalog-slider',appearance_written=False,workspace=workspace)}
                cas_controls.validate(client,request)
                workspace['slider_thumbs'][name]=.5
                with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(client,request)
        for fraction in (True,-.1,1.1,float('nan')):
            with self.assertRaises(ValueError):cas_ui.envelope('12',dict(operation='catalog-slider',control='red',fraction=fraction))

    def test_catalog_view_acknowledges_the_exact_tab(self):
        for view in ('items','style','closed'):
            request=dict(operation='catalog-view',view=view);cas_ui.envelope('12',request)
            workspace=dict(visible=view!='closed',view=view)
            client={'control':dict(operation='catalog-view',appearance_written=False,workspace=workspace)}
            cas_controls.validate(client,request)
            workspace['visible']=not workspace['visible']
            with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(client,request)


if __name__=='__main__':unittest.main()
