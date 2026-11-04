"""Exact control values plus only native twip-sized thumb quantization."""
import copy,json,math
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core import cas_controls,cas_ui
RANGES={'columns':(2,32),'red':(0,255),'green':(0,255),'blue':(0,255),'glow':(0,12),'border':(1,8),
        'period':(.8,4),'strength':(.25,1),'card_scale':(.2,1.6),'gap_x':(0,32),'gap_y':(0,32)}
TWIP=(1/20)/300


def sample(name,fraction):
    low,high=RANGES[name];discrete=name in ('columns','red','green','blue')
    expected=low+(math.floor(fraction*(high-low)+.5) if discrete else fraction*(high-low))
    workspace=dict(visible=True,view='layout' if name in ('card_scale','gap_x','gap_y') else 'style',
        preferences={},card_preferences={},slider_thumbs={name:(expected-low)/(high-low)},
        slider_geometry={name:dict(x=(expected-low)/(high-low)*300,track_pixels=300,track_scale_x=1,attached=True)})
    if name in ('red','green','blue'):
        shift={'red':16,'green':8,'blue':0}[name];workspace['preferences']['color']=(0xaabbcc&~(255<<shift))|(expected<<shift)
    elif name in ('card_scale','gap_x','gap_y'):workspace['card_preferences']['scale' if name=='card_scale' else name]=expected
    else:workspace['preferences'][name]=expected
    request=dict(operation='catalog-slider',control=name,fraction=fraction);cas_ui.envelope('12',request)
    return request,{'control':dict(operation='catalog-slider',appearance_written=False,workspace=workspace)}


class SliderAcknowledgmentTests(unittest.TestCase):
    def native_fixture(self):
        return json.loads((Path(__file__).parent/'fixtures/catalog-slider-v344-pixel-ack.json').read_text(encoding='utf-8'))

    def test_actual_full_v344_ack_has_correct_pixels_and_inconsistent_fraction_without_replay(self):
        fixture=self.native_fixture();ack=fixture['native_acknowledgement'];client=ack['client'];request=fixture['request']
        self.assertEqual(cas_ui._baseline_hash(ack),fixture['native_acknowledgement_sha256'])
        w=client['control']['workspace'];pixel=w['slider_geometry']['card_scale']['x'];fraction=w['slider_thumbs']['card_scale']
        self.assertEqual(pixel,32.1);self.assertEqual(fraction,.1)
        self.assertGreater(abs(pixel/300-fraction),TWIP)
        expected=request['fraction']*300;self.assertLessEqual(abs(pixel-expected),.05)
        # This unchanged V344 capture predates the installed Featured Face
        # alias. Its historical full envelope must not pass today's complete
        # registry gate. Qualify only the attested slider primitives here.
        self.assertEqual(len(client['catalogs']),77)
        self.assertEqual({row['panel'] for row in client['catalogs']},
                         set(cas_ui.PANELS)-{'featured_face_presets'})
        with self.assertRaisesRegex(ValueError,'every mapped panel'):
            cas_ui.validate_client(client,client['sim']['simId'],request)
        cas_controls.validate(client,request)
        self.assertEqual(cas_ui._baseline_hash(ack),fixture['native_acknowledgement_sha256'])
        self.assertEqual(fixture['original_terminal_outcome'],'native-postcondition-failed')

    def test_actual_pixel_bound_is_one_twip_and_fraction_cannot_authorize_a_wrong_thumb(self):
        fixture=self.native_fixture();request=fixture['request'];client=fixture['native_acknowledgement']['client']
        w=client['control']['workspace'];expected=request['fraction']*300
        for delta in(-.05,.05):
            w['slider_geometry']['card_scale']['x']=expected+delta;cas_controls.validate(client,request)
        w['slider_thumbs']['card_scale']=request['fraction']
        for pixel in(expected-.050001,expected+.050001,30):
            w['slider_geometry']['card_scale']['x']=pixel
            with self.subTest(pixel=pixel),self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(client,request)

    def test_missing_detached_scaled_or_forged_pixel_geometry_is_not_a_complete_ack(self):
        fixture=self.native_fixture();request=fixture['request'];original=fixture['native_acknowledgement']['client']
        changes=[lambda w:w.pop('slider_geometry'),lambda w:w['slider_geometry'].pop('card_scale'),
            lambda w:w['slider_geometry']['card_scale'].update(attached=False),
            lambda w:w['slider_geometry']['card_scale'].update(track_pixels=299),
            lambda w:w['slider_geometry']['card_scale'].update(track_scale_x=.5),
            lambda w:w['slider_geometry']['card_scale'].update(x=True),
            lambda w:w['slider_geometry']['card_scale'].update(x=float('nan')),
            lambda w:w['slider_geometry']['card_scale'].update(extra='foreign')]
        for change in changes:
            client=copy.deepcopy(original);change(client['control']['workspace'])
            with self.subTest(client=client['control']['workspace']['slider_geometry']if 'slider_geometry'in client['control']['workspace']else None):
                with self.assertRaises(ValueError)as raised:cas_controls.validate(client,request)
                self.assertNotIsInstance(raised.exception,cas_controls.PostconditionMismatch)
        client=copy.deepcopy(original);client['control']['workspace']['card_preferences']['scale']=.36
        with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(client,request)

    def test_historical_fraction_only_packet_cannot_authorize_current_pixel_ack(self):
        fixture=json.loads((Path(__file__).parent/'fixtures/catalog-slider-native-twip.json').read_text(encoding='utf-8'))
        with self.assertRaisesRegex(ValueError,'pixel geometry'):cas_controls.validate(fixture['client'],fixture['request'])
        workspace=fixture['client']['control']['workspace']
        self.assertEqual(workspace['preferences']['columns'],12)
        self.assertAlmostEqual((1/3-workspace['slider_thumbs']['columns'])*300,.05)

    def test_discrete_controls_use_exact_rounded_value_position_not_raw_fraction(self):
        for name in ('columns','red','green','blue'):
            for fraction in (.34,.35,.5,.0166,.0167,1/3):
                with self.subTest(name=name,fraction=fraction):
                    request,client=sample(name,fraction);cas_controls.validate(client,request)
                    actual=client['control']['workspace']['slider_thumbs'][name]
                    if abs(actual-fraction)>TWIP+1e-9:
                        client['control']['workspace']['slider_geometry'][name]['x']=fraction*300
                        with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(client,request)

    def test_continuous_values_remain_exact_independent_of_thumb_quantization(self):
        for name in RANGES:
            for fraction in (.12345,.4,1/3):
                with self.subTest(name=name,fraction=fraction):
                    request,client=sample(name,fraction);workspace=client['control']['workspace']
                    expected=workspace['slider_thumbs'][name]
                    for offset in (-TWIP,TWIP):
                        workspace['slider_geometry'][name]['x']=(expected+offset)*300;cas_controls.validate(client,request)
                    workspace['slider_geometry'][name]['x']=(expected+2*TWIP)*300
                    with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(client,request)

    def test_endpoints_are_in_range_and_true_wrong_thumb_or_untyped_coordinates_refuse(self):
        for name in RANGES:
            for fraction in (0,1):
                request,client=sample(name,fraction);cas_controls.validate(client,request)
                for wrong in (-TWIP,1+TWIP,float('nan'),float('inf'),True,None):
                    with self.subTest(name=name,fraction=fraction,wrong=wrong):
                        changed=copy.deepcopy(client);changed['control']['workspace']['slider_geometry'][name]['x']=wrong*300 if type(wrong)in(int,float)else wrong
                        with self.assertRaises(ValueError):cas_controls.validate(changed,request)

    def test_correct_thumb_cannot_authorize_wrong_preference_or_rounding_bin(self):
        for name in RANGES:
            request,client=sample(name,.34);workspace=client['control']['workspace']
            if name in ('red','green','blue'):workspace['preferences']['color']^=1<<{'red':16,'green':8,'blue':0}[name]
            elif name in ('card_scale','gap_x','gap_y'):workspace['card_preferences']['scale' if name=='card_scale' else name]+=.01
            else:workspace['preferences'][name]+=.01
            with self.subTest(name=name),self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(client,request)
        for bad in (float('nan'),float('inf'),True):
            request,client=sample('glow',.4);client['control']['workspace']['preferences']['glow']=bad
            with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(client,request)

    def test_value_precision_is_not_relaxed_by_visual_twip_tolerance(self):
        request,client=sample('columns',1/3);workspace=client['control']['workspace']
        workspace['slider_thumbs']['columns']-=TWIP
        workspace['preferences']['columns']=12.0000001
        with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(client,request)
        request,client=sample('glow',1/3);client['control']['workspace']['preferences']['glow']+=.00001
        with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(client,request)


if __name__=='__main__':unittest.main()
