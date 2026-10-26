import copy
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'Source')]
from cas_catalog_workspace import viewport_layout,native_catalog_clamp,equipped_menus,inject_context,inject_plan,card_layout
from apex_core import cas_ui,cas_controls


class CatalogWorkspaceTests(unittest.TestCase):
    def style(self):
        return dict(operation='catalog-style',columns=6,color=0x00c9eb,glow=0,
            animation='none',strength=1,period=1.4,border=3)

    def test_requested_columns_fit_using_smaller_native_tiles(self):
        for width in (640,1024,1280,1920,2560,3840):
            for requested in range(2,33):
                layout=viewport_layout(requested,width)
                self.assertLessEqual(layout['columns'],requested)
                self.assertGreaterEqual(layout['columns'],2)
                self.assertLessEqual(layout['width'],max(80,width*.40-12)+1e-8)
        for requested in (12,20,32):self.assertEqual(viewport_layout(requested,1278)['columns'],requested)
        self.assertEqual(viewport_layout(6,1920)['width'],706)

    def test_native_attachment_clamp_reserves_the_complete_catalog(self):
        for width in (640,1278,1920,2560):
            for columns in range(2,33):
                x=native_catalog_clamp(columns,width,418)
                self.assertGreaterEqual(x,0)
                self.assertLessEqual(x+viewport_layout(columns,width)['width'],width-12)
        self.assertAlmostEqual(native_catalog_clamp(6,1278,418),766.8)

    def test_invalid_slider_values_never_reach_transport(self):
        request=self.style()
        for field,values in {'columns':[True,0,33,2.5],'color':[True,-1,0x1000000],
                'glow':[float('nan'),13],'period':[0,.79,4.1],
                'border':[0,9],'strength':[False,.2,2],'animation':['strobe','unknown']}.items():
            for value in values:
                with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                    cas_ui.envelope('12',dict(request,**{field:value}))

    def test_extended_column_and_card_bounds_reach_the_same_typed_contract(self):
        for count in (2,12,20,32):
            request=dict(self.style(),columns=count);cas_ui.envelope('12',request)
            self.assertEqual(cas_controls.wire(request,None)[3].split(',')[0],str(count))
        for size in (.2,.4,1,1.6):
            request=dict(operation='catalog-cards',card_scale=size,gap_x=4,gap_y=4);cas_ui.envelope('12',request)
            self.assertEqual(float(cas_controls.wire(request,None)[3].split(',')[0]),size)

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

    def test_native_category_ack_is_distinct_from_optional_text_list(self):
        request=dict(operation='catalog-view',view='category');cas_ui.envelope('12',request)
        workspace=dict(visible=False,error='',context='12|native/2',outfit=dict(category=0,index=1),
            equipped_category=dict(active=True,pending=False,resolved=20,published=20),clothing_grid_item_count=20)
        client=dict(sim=dict(simId='12'),form_strip=dict(selected_owner_id='native/2'),outfit=dict(outfit_type=0,outfit_index=1),
            control=dict(operation='catalog-view',appearance_written=False,workspace=workspace))
        cas_controls.validate(client,request)
        for field,value in [('context','13|native/2'),('outfit',dict(category=0,index=0)),('equipped_category',dict(active=False))]:
            bad=copy.deepcopy(client);bad['control']['workspace'][field]=value
            with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(bad,request)
        text=copy.deepcopy(client);text['control']['workspace'].update(visible=True,view='items')
        cas_controls.validate(text,dict(operation='catalog-view',view='items'))

    def test_partial_publication_cannot_claim_a_complete_thumbnail_grid(self):
        request=dict(operation='catalog-view',view='category')
        workspace=dict(visible=False,error='',context='12|native/2',outfit=dict(category=0,index=1),
            equipped_category=dict(active=True,pending=True,resolved=20,published=3),clothing_grid_item_count=3)
        client=dict(sim=dict(simId='12'),form_strip=dict(selected_owner_id='native/2'),outfit=dict(outfit_type=0,outfit_index=1),
            control=dict(operation='catalog-view',appearance_written=False,workspace=workspace))
        cas_controls.validate(client,request)
        for changes in (dict(pending=False),dict(published=21),dict(published=True),dict(resolved=257),dict(pending=None)):
            bad=copy.deepcopy(client);bad['control']['workspace']['equipped_category'].update(changes)
            with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(bad,request)
        workspace['equipped_category'].update(pending=False,published=20)
        with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(client,request)

    def test_different_ui_contract_is_rejected_before_patching(self):
        with self.assertRaises(ValueError):inject_context('native UI changed')
        with self.assertRaises(ValueError):inject_plan('native UI changed')

    def test_outfit_header_clamp_changes_only_inspected_anchors(self):
        native='"clampX":{"max":LayoutAPI.StageWidth - param4}\n         if(_loc2_ == this.mAnimExtension.IsVisible())'
        made=inject_plan(native)
        self.assertIn('Math.max(param4,this.mWidth + 12)',made)
        self.assertIn('typeof param1.apex_view_x_offset=="number"',made)
        self.assertIn('isFinite(param1.apex_screen_x_max)',made)
        self.assertIn('this.mWidth>=262 && this.mWidth<=LayoutAPI.StageWidth-12',made)
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
        cards=(ROOT/'Source/CASUi/catalog_cards_methods.as').read_text(encoding='utf-8')
        signature=cards.split('var signature:String=',1)[1].split(';',1)[0]
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
                value={'columns':14,'color':0x666666,'glow':4.8,'border':3.8,'period':2.08,'strength':.55}
                workspace=dict(visible=True,view='style',preferences=value,slider_thumbs={name:.4})
                client={'control':dict(operation='catalog-slider',appearance_written=False,workspace=workspace)}
                cas_controls.validate(client,request)
                workspace['slider_thumbs'][name]=.5
                with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(client,request)
        for fraction in (True,-.1,1.1,float('nan')):
            with self.assertRaises(ValueError):cas_ui.envelope('12',dict(operation='catalog-slider',control='red',fraction=fraction))

    def test_catalog_view_acknowledges_the_exact_tab(self):
        for view in ('items','style','layout','closed'):
            request=dict(operation='catalog-view',view=view);cas_ui.envelope('12',request)
            workspace=dict(visible=view!='closed',view=view)
            client={'control':dict(operation='catalog-view',appearance_written=False,workspace=workspace)}
            cas_controls.validate(client,request)
            workspace['visible']=not workspace['visible']
            with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(client,request)

    def test_card_geometry_keeps_proportions_gaps_and_viewport_fit(self):
        for viewport in (640,1024,1278,1920,2560,3840):
            for size in (.2,.4,.65,1,1.6):
                for gap_x,gap_y in ((0,32),(32,0),(4,4),(32,32)):
                    for columns in (2,6,12,20,32):
                        made=card_layout(columns,viewport,size,gap_x,gap_y)
                        self.assertLessEqual(made['columns'],columns)
                        self.assertLessEqual(made['width'],max(80,viewport*.40-12)+1e-8)
                        self.assertEqual(made['columns'],columns)
                        self.assertAlmostEqual(made['card_width']/made['card_height'],107/148)
                        self.assertAlmostEqual(made['pitch_x']-made['card_width'],made['gap_x'])
                        self.assertLessEqual(made['gap_x'],gap_x)
                        self.assertEqual(made['requested_gap_x'],gap_x)
                        self.assertAlmostEqual(made['pitch_y']-made['card_height'],gap_y)
        self.assertEqual(card_layout(6,1920,1,4,4)['width'],706)

    def test_card_commands_reject_nonfinite_bool_missing_and_foreign_fields(self):
        request=dict(operation='catalog-cards',card_scale=1,gap_x=4,gap_y=4)
        cas_ui.envelope('12',request)
        for name,values in {'card_scale':[True,float('nan'),.19,1.61],
                'gap_x':[False,-1,33,float('inf')],'gap_y':[-1,33,float('nan')]}.items():
            for value in values:
                with self.subTest(field=name,value=value),self.assertRaises(ValueError):
                    cas_ui.envelope('12',dict(request,**{name:value}))
        for altered in (dict(request,unknown=1),{k:v for k,v in request.items() if k!='gap_y'}):
            with self.assertRaises(ValueError):cas_ui.envelope('12',altered)

    def test_card_readback_requires_all_preferences_and_ui_only_receipt(self):
        request=dict(operation='catalog-cards',card_scale=.8,gap_x=0,gap_y=32)
        prefs=dict(scale=.8,gap_x=0,gap_y=32)
        client={'control':dict(operation='catalog-cards',appearance_written=False,workspace={'card_preferences':prefs})}
        cas_controls.validate(client,request)
        for name in prefs:
            altered=copy.deepcopy(client);altered['control']['workspace']['card_preferences'][name]=None
            with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(altered,request)
        client['control']['appearance_written']=True
        with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(client,request)

    def test_card_sliders_acknowledge_exact_thumb_and_independent_values(self):
        for name,key,n in (('card_scale','scale',.76),('gap_x','gap_x',12.8),('gap_y','gap_y',12.8)):
            request=dict(operation='catalog-slider',control=name,fraction=.4);cas_ui.envelope('12',request)
            workspace=dict(visible=True,view='layout',card_preferences={key:n},slider_thumbs={name:.4})
            client={'control':dict(operation='catalog-slider',appearance_written=False,workspace=workspace)}
            cas_controls.validate(client,request)
            workspace['card_preferences'][key]=n+.1
            with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(client,request)

    def test_selection_outline_stays_inside_real_thumbnail(self):
        source=(ROOT/'Source/CASUi/catalog_workspace_methods.as').read_text(encoding='utf-8')
        selected=source.split('private function ApexCatalogSelection(',1)[1].split('private function ApexCatalogReadEquipped(',1)[0]
        self.assertIn('cell.mcIconAndMask',selected)
        self.assertIn('stroke*0.5+1',selected)
        self.assertIn('bounds.width-inset*2',selected)
        self.assertIn('bounds.height-inset*2',selected)
        self.assertNotIn('effect.graphics.drawRoundRect(',selected)
        self.assertIn('effect.graphics.lineTo(right,bottom-radius)',selected)
        self.assertIn('effect.graphics.lineTo(left,top+radius)',selected)
        self.assertIn('effect.graphics.curveTo(left,top,left+radius,top)',selected)

    def test_card_adapter_does_not_read_native_write_only_num_lines(self):
        source=(ROOT/'Source/CASUi/catalog_cards_methods.as').read_text(encoding='utf-8')
        self.assertIn('grid.GetGridDimensions()',source)
        self.assertIn('grid.Horizontal ? 0 : 1',source)
        self.assertNotIn('columns:grid.NumLines',source)
        self.assertIn('Number(nativeCell.width)/Number(nativeCell.scaleX)',source)
        self.assertIn('naturalWidth*scale+Number(fitted.gap_x)',source)
        self.assertIn('new flash.geom.Rectangle(base.x,base.y,naturalWidth*scale,0)',source)
        self.assertIn('CalculateCellViewHeight(cell as flash.display.DisplayObject)',source)

    def test_layout_resets_the_stock_recycling_cache_instead_of_preserving_nan(self):
        source=(ROOT/'Source/CASUi/catalog_cards_methods.as').read_text(encoding='utf-8')
        self.assertIn('ApexLayoutReset(grid)',source)
        self.assertNotIn('grid.PositionCells()',source)
        self.assertNotIn('ApexCatalogGridPlaced',source)

    def test_semantic_panel_navigation_notifies_the_native_radial_binding(self):
        source=(ROOT/'Source/CASUi/semantic_methods.as').read_text(encoding='utf-8')
        branch=source.split('} else if(operation=="panel" || operation=="panel-navigation") {',1)[1].split('} else if(operation=="outfit"',1)[0]
        self.assertLess(branch.index('HandleContextMenuSetMenuState('),branch.index('SendUIMessage("CASChangeMenuState",state)'))


if __name__=='__main__':unittest.main()
