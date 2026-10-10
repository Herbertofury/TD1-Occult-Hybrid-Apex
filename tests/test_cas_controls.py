import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import cas_ui, cas_controls
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from cas_ui_build import verify_control_dispatch, verify_snapshot_ownership


class CasControlsTests(unittest.TestCase):
    def client(self, panel='skin_details'):
        return {'scope':'native-cas-client', 'sim':{'simId':'12','physiqueValues':[.4,.5]},
            'menu_state':cas_ui.panel(panel),'panel_visible':True,
            'outfit':{'outfit_type':0,'outfit_index':0}, 'selected':[],
            'catalogs':[{'panel':name,'menu_state':state,'supported':True,'items':[],
                         'preset':None,'preset_query':'returned-null'} for name,state in cas_ui.PANELS.items()]}

    def test_every_ordinary_item_panel_has_typed_selection(self):
        for name in cas_ui.PANELS:
            if name.startswith('profile_') or name in ('clothing_looks','clothing_head_tattoos','clothing_body_tattoos'):
                continue
            _, wire=cas_ui.envelope('12',{'operation':'select','panel':name,'data_id':'18446744073709551615'})
            self.assertEqual(wire.split('|')[3],str(cas_ui.PANELS[name]))
            self.assertEqual(wire.split('|')[6],'18446744073709551615')

    def test_every_panel_has_paged_discovery_without_total_catalog_cutoff(self):
        for name in cas_ui.PANELS:
            request={'operation':'catalog','panel':name,'offset':100000,'limit':32}
            _,wire=cas_ui.envelope('12',request)
            self.assertEqual(wire.split('|')[4:6],['100000','32'])
            client=self.client(name)
            client['control']={'operation':'catalog','offset':100000,'limit':32,'total':100003,
                               'items':[{'data_id':str(i),'future':{'raw':[1,'exact']}} for i in range(3)]}
            cas_ui.validate_client(client,'12',request)
            client['control']['items'].pop()
            with self.assertRaisesRegex(ValueError,'incomplete'):cas_ui.validate_client(client,'12',request)

    def test_layer_selection_requires_exact_body_part_index_and_identity(self):
        request={'operation':'select-layer','panel':'clothing_body_tattoos','data_id':'18446744073709551615',
                 'body_type':42,'layer_index':7,'layer_id':12}
        _,wire=cas_ui.envelope('12',request)
        self.assertEqual(wire.split('|')[4:],['42','7','18446744073709551615,12'])
        client=self.client(request['panel'])
        layers=[{'layerId':i+1,'partKey':'100','future':i} for i in range(8)]
        layers[7]={'layerId':12,'partKey':request['data_id'],'future':'kept'}
        client['control']={'operation':'select-layer','body_type':42,'layers':layers}
        cas_ui.validate_client(client,'12',request)
        for field,value in (('layerId',13),('partKey','99')):
            changed=copy.deepcopy(client); changed['control']['layers'][7][field]=value
            with self.assertRaisesRegex(ValueError,'exact part'):cas_ui.validate_client(changed,'12',request)

    def test_layer_move_and_remove_preserve_complete_other_rows(self):
        before=[{'layerId':i+1,'partKey':str(100+i),'future':{'v':i}} for i in range(4)]
        for operation in ('layer-move','layer-remove'):
            request={'operation':operation,'panel':'clothing_body_tattoos','body_type':42,'layer_index':1,'layer_id':2}
            expected=copy.deepcopy(before); moved=expected.pop(1)
            if operation=='layer-move':request['target_index']=3; expected.insert(3,moved)
            cas_ui.envelope('12',request)
            client=self.client(request['panel'])
            client['control']={'operation':operation,'body_type':42,'before':before,'layers':expected}
            cas_ui.validate_client(client,'12',request)
            changed=copy.deepcopy(client); changed['control']['layers'][0]['future']['v']=99
            with self.assertRaisesRegex(ValueError,'lost or changed'):cas_ui.validate_client(changed,'12',request)

    def test_skin_and_fur_swatch_readbacks_use_their_actual_native_shapes(self):
        for kind,selected,index in ((0,{'dataID':'123','value_range_modifier':.2,'future':True},0),
                                     (6,['111','123','222'],1),(3,'123',0)):
            request={'operation':'swatch','swatch_type':kind,'data_id':'123','color_index':index}
            cas_ui.envelope('12',request)
            client=self.client();client['control']={'operation':'swatch','selected':selected}
            cas_ui.validate_client(client,'12',request)
            client['control']['selected']=None
            with self.assertRaises(ValueError):cas_ui.validate_client(client,'12',request)

    def test_refusals_happen_before_any_transport(self):
        valid={'operation':'select-layer','panel':'clothing_body_tattoos','data_id':'123','body_type':42,'layer_index':0,'layer_id':1}
        malformed=[dict(valid,layer_index=-1),dict(valid,layer_id=True),dict(valid,body_type=None),dict(valid,data_id='123|undo'),
            {'operation':'catalog','panel':'hair','offset':True,'limit':8},
            {'operation':'physique','physique_type':0,'value':float('nan')},
            {'operation':'physique','physique_type':0,'value':1.1},
            {'operation':'swatch','swatch_type':5,'data_id':'12','color_index':0}]
        for request in malformed:
            with self.assertRaises(ValueError):cas_ui.submit('12',request,send=lambda _:self.fail('invalid transport'))

    def test_preset_and_physique_cannot_pass_on_only_navigation(self):
        request={'operation':'preset','panel':'nose','data_id':'123'}
        client=self.client('nose');client['control']={'operation':'preset','preset_query':'returned-value',
            'preset':{'index':2,'future':True},'selected_data_id':'122'}
        with self.assertRaisesRegex(ValueError,'exact catalog'):cas_ui.validate_client(client,'12',request)
        client['control']['selected_data_id']='123';cas_ui.validate_client(client,'12',request)
        request={'operation':'physique','physique_type':0,'value':.8}
        client['control']={'operation':'physique'}
        with self.assertRaisesRegex(ValueError,'slider'):cas_ui.validate_client(client,'12',request)
        client['sim']['physiqueValues'][0]=.8;cas_ui.validate_client(client,'12',request)

    def test_body_region_inventory_and_selection_require_actual_native_id(self):
        request={'operation':'body-types','panel':'clothing_body_tattoos'}
        client=self.client(request['panel'])
        client['control']={'operation':'body-types','body_types':[42,43,44],'body_type':42}
        cas_ui.validate_client(client,'12',request)
        request={'operation':'body-type','panel':'clothing_body_tattoos','body_type':44}
        client['control'].update(operation='body-type')
        with self.assertRaisesRegex(ValueError,'requested identity'):cas_ui.validate_client(client,'12',request)
        client['control']['body_type']=44;cas_ui.validate_client(client,'12',request)
        client['control']['body_types'].append(44)
        with self.assertRaisesRegex(ValueError,'complete eligible'):cas_ui.validate_client(client,'12',request)

    def test_eyebrows_and_whiskers_use_exact_part_selection_instead_of_preset_indices(self):
        for name in cas_controls.PART_PROFILE_PANELS:
            _,wire=cas_ui.envelope('12',{'operation':'select','panel':name,'data_id':'88163'})
            self.assertEqual(wire.split('|')[3],str(cas_ui.PANELS[name]))
        with self.assertRaises(ValueError):
            cas_ui.envelope('12',{'operation':'select','panel':'nose','data_id':'88163'})

    def test_color_slider_bounds_and_complete_unchanged_modifier_fields(self):
        request={'operation':'color-sliders','panel':'skin_details','data_id':'123','layer_index':-1,'layer_id':0,
                 'hue':.1,'opacity':.8,'saturation':-.1,'brightness':.2}
        _,wire=cas_ui.envelope('12',request)
        self.assertEqual(wire.split('|')[4:6],['0','-1'])
        before={'dataID':'123','future':{'v':'complete'},'hue_range_min':-.5,
                'hue_range_modifier':0,'opacity_range_modifier':1,'saturation_range_modifier':0,'value_range_modifier':0}
        selected=dict(copy.deepcopy(before),hue_range_modifier=.1,opacity_range_modifier=.8,saturation_range_modifier=-.1,value_range_modifier=.2)
        client=self.client('skin_details');client['control']={'operation':'color-sliders','before':before,'selected':selected}
        cas_ui.validate_client(client,'12',request)
        bad=copy.deepcopy(client);bad['control']['selected']['future']['v']='lost'
        with self.assertRaisesRegex(ValueError,'other modifier fields'):cas_ui.validate_client(bad,'12',request)
        bad=copy.deepcopy(client);bad['control']['selected']['hue_range_modifier']=.11
        with self.assertRaisesRegex(ValueError,'requested value'):cas_ui.validate_client(bad,'12',request)
        for changed in (dict(request,layer_id=127,layer_index=0),dict(request,layer_id=1),dict(request,hue=float('inf'))):
            with self.assertRaises(ValueError):cas_ui.envelope('12',changed)

    def test_native_hair_matching_mask_is_exact_and_not_outfit_isolation_proof(self):
        request={'operation':'hair-match','flags':0}
        cas_ui.envelope('12',request)
        client=self.client();client['control']={'operation':'hair-match','flags':0}
        cas_ui.validate_client(client,'12',request)
        client['control']['flags']=1
        with self.assertRaisesRegex(ValueError,'requested mask'):cas_ui.validate_client(client,'12',request)
        with self.assertRaises(ValueError):cas_ui.envelope('12',dict(request,flags=64))

    def test_complete_native_control_dispatch_rejects_the_observed_v21_omission(self):
        source=(Path(__file__).resolve().parents[1]/'Source/CASUi/semantic_methods.as').read_text()
        self.assertEqual(set(verify_control_dispatch(source)),cas_controls.OPERATIONS)
        for operation in cas_controls.OPERATIONS:
            start=source.index('private function ApexReadback()')
            changed=source[:start]+source[start:].replace('operation=="'+operation+'"','operation=="missing-control"',1)
            with self.assertRaisesRegex(ValueError,'dispatch'):
                verify_control_dispatch(changed)

    def test_every_native_inventory_getter_detaches_before_the_next_call(self):
        source=(Path(__file__).resolve().parents[1]/'Source/CASUi/semantic_methods.as').read_text()
        self.assertGreater(verify_snapshot_ownership(source),10)
        start=source.index('private function ApexSnapshot(')
        changed=source[:start]+source[start:].replace('ApexClone(CommunicationManager.CallGameService',
            'Identity(CommunicationManager.CallGameService',1)
        with self.assertRaisesRegex(ValueError,'immediate detachment'):verify_snapshot_ownership(changed)

    def test_voice_actor_uses_zero_based_index_but_one_based_native_readback(self):
        request={'operation':'voice-actor','actor_index':1}
        _,wire=cas_ui.envelope('12',request)
        self.assertEqual(wire.split('|')[5],'1')
        client=self.client();client['sim'].update(voiceActor=2,voicePitch=-.14)
        client['control']={'operation':'voice-actor','voices':[{'minPitch':-.5,'maxPitch':.5,'future':'kept'},
                                                           {'minPitch':-.3,'maxPitch':.3}]}
        cas_ui.validate_client(client,'12',request)
        client['sim']['voiceActor']=1
        with self.assertRaisesRegex(ValueError,'zero-based'):cas_ui.validate_client(client,'12',request)
        with self.assertRaises(ValueError):cas_ui.envelope('12',dict(request,actor_index=True))

    def test_voice_pitch_uses_native_ranges_and_allows_negative_pitch(self):
        request={'operation':'voice-pitch','value':-.14}
        cas_ui.envelope('12',request)
        client=self.client();client['sim'].update(voiceActor=1,voicePitch=-.14)
        client['control']={'operation':'voice-pitch','voices':[{'minPitch':-.2,'maxPitch':.2}]}
        cas_ui.validate_client(client,'12',request)
        client['control']['voices'][0]['minPitch']=-.1
        with self.assertRaisesRegex(ValueError,'native voice range'):cas_ui.validate_client(client,'12',request)
        with self.assertRaises(ValueError):cas_ui.envelope('12',dict(request,value=float('nan')))

    def test_walkstyle_and_detail_mode_require_actual_native_results(self):
        client=self.client();request={'operation':'walkstyle','data_id':'123'}
        cas_ui.envelope('12',request)
        client['control']={'operation':'walkstyle','walkstyles':[{'id':'123','equipped':True,'future':1},
                                                              {'id':'124','equipped':False}]}
        cas_ui.validate_client(client,'12',request)
        client['control']['walkstyles'][1]['equipped']=True
        with self.assertRaisesRegex(ValueError,'trait identity'):cas_ui.validate_client(client,'12',request)
        request={'operation':'detail-mode','enabled':False};cas_ui.envelope('12',request)
        client['control']={'operation':'detail-mode','active':False};cas_ui.validate_client(client,'12',request)
        client['control']['active']=True
        with self.assertRaisesRegex(ValueError,'requested state'):cas_ui.validate_client(client,'12',request)
        with self.assertRaises(ValueError):cas_ui.envelope('12',dict(request,enabled=0))

    def test_filters_keep_native_context_tags_but_verify_removable_selection_clear(self):
        request={'operation':'filter-clear','panel':'skin_details'};cas_ui.envelope('12',request)
        client=self.client();client['control']={'operation':'filter-clear','selected_bubble_empty':True,
            'filters':{'tags':[123],'excludeTags':[456],'packIds':[], 'filterByGameplayUnlocks':False,
                       'filterLocked':False,'filterPurchasedProducts':False,'filterModdedContent':False}}
        cas_ui.validate_client(client,'12',request)
        client['control']['selected_bubble_empty']=False
        with self.assertRaisesRegex(ValueError,'removable'):cas_ui.validate_client(client,'12',request)

    def test_rejected_native_success_retains_every_field_and_blocks_replay(self):
        cas_ui._RECORDS.clear();self.addCleanup(cas_ui._RECORDS.clear)
        rid=cas_ui.submit('12',{'operation':'hair-matching'},send=lambda _:None)['cas_request_id']
        reply={'protocol':1,'ok':True,'cas_request_id':rid,'client':self.client(),
               'future':{'full':['18446744073709551615']}}
        with self.assertRaisesRegex(ValueError,'exact typed result'):cas_ui.receive(rid,json.dumps(reply))
        result=cas_ui.result(rid)
        self.assertEqual(result['outcome'],'invalid-native-acknowledgement')
        self.assertEqual(result['native_acknowledgement'],reply)
        self.assertFalse(result['ok']);self.assertEqual(result['cas_request_state'],'pending')
        with self.assertRaisesRegex(ValueError,'unresolved'):
            cas_ui.submit('12',{'operation':'undo'},send=lambda _:self.fail('replayed'))


if __name__=='__main__':unittest.main()
