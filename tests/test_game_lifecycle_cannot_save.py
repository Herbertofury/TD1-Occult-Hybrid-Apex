"""Retained EA warning pixels plus synthetic transport; never operates the game."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import game_lifecycle
import test_game_lifecycle as fixture
FIXTURES=Path(__file__).resolve().parent/'fixtures'


class CannotSaveDiscardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.native=json.loads((FIXTURES/'cannot-save-exit-anyway.json').read_text(encoding='utf-8'))
        self.source=FIXTURES/'cannot-save-exit-anyway.png'

    def surface(self,scale=1,offset=(0,0),size=None):
        value=copy.deepcopy(self.native);image=Image.open(self.source).convert('RGB')
        image=image.resize((round(image.width*scale),round(image.height*scale)),Image.Resampling.NEAREST)
        if size is None:size=(image.width+offset[0],image.height+offset[1])
        canvas=Image.new('RGB',size,(32,35,75));canvas.paste(image,offset)
        for row in value['lines']:
            for word in row['words']:
                for key in ('x','width'):word[key]=word[key]*scale+(offset[0] if key=='x' else 0)
                for key in ('y','height'):word[key]=word[key]*scale+(offset[1] if key=='y' else 0)
        value.update(width=size[0],height=size[1]);path=self.root/'warning.png';canvas.save(path)
        return value,path,canvas

    def test_retained_native_warning_identifies_measured_check_only_for_discard(self):
        value,path,_=self.surface()
        self.assertEqual(game_lifecycle.button(value,'confirmation-discard',path),
            {'command':1,'x':334,'y':170,'width':390,'height':210})
        self.assertEqual([r['kind'] for r in value['lifecycle_icon_recognition']['icons']],['cancel-x','discard-check'])
        for phase in ('confirmation','menu','menu-discard','resume'):
            with self.subTest(phase=phase),self.assertRaises(ValueError):game_lifecycle.button(value,phase,path)
        with self.assertRaises(ValueError):game_lifecycle.button(value,'confirmation-discard')
        behind=fixture.observed(['MENU','Save','Save As...','Exit Game'])
        behind['lines']+=copy.deepcopy(value['lines'])
        for phase in ('menu','menu-discard'):
            with self.subTest(phase=phase),self.assertRaises(ValueError):game_lifecycle.button(behind,phase,path)

    def test_measured_footer_is_independent_of_resolution_scale_and_dialog_position(self):
        for scale,offset,size in ((.75,(83,75),(640,480)),(1,(435,510),(1278,1376)),(2,(1000,600),(2560,1385))):
            with self.subTest(scale=scale):
                value,path,_=self.surface(scale,offset,size)
                selected=game_lifecycle.button(value,'confirmation-discard',path)
                self.assertAlmostEqual(selected['x'],334.5*scale+offset[0],delta=1)
                self.assertAlmostEqual(selected['y'],170.5*scale+offset[1],delta=1)
                self.assertEqual((selected['width'],selected['height']),size)

    def test_incomplete_foreign_or_duplicate_warning_never_authorizes_an_icon(self):
        value,path,_=self.surface()
        for damage in ('body','question','duplicate','different-title','conflicting-save','geometry','viewport','nan'):
            with self.subTest(damage=damage):
                changed=copy.deepcopy(value)
                if damage=='body':changed['lines'].pop(1)
                elif damage=='question':changed['lines'][-1]['text']='or save?'
                elif damage=='duplicate':changed['lines'].append(copy.deepcopy(changed['lines'][0]))
                elif damage=='different-title':changed['lines'][0]['text']='Cannot load'
                elif damage=='conflicting-save':changed['lines'].append({'text':'Save and Exit','words':[]})
                elif damage=='geometry':changed['lines'][0]['words'][0]['x']=-10
                elif damage=='viewport':changed['width']+=1
                else:changed['lines'][0]['words'][0]['width']=float('nan')
                with self.assertRaises(ValueError):game_lifecycle.button(changed,'confirmation-discard',path)

    def test_missing_reversed_duplicate_or_unbacked_icons_refuse(self):
        for damage in ('missing','reversed','duplicate','no-white-buttons'):
            with self.subTest(damage=damage):
                value,path,canvas=self.surface();pixels=canvas.load()
                if damage=='missing':canvas.paste((185,185,192),(27,134,390,210))
                elif damage=='reversed':canvas.paste(canvas.crop((27,134,390,210)).transpose(Image.Transpose.FLIP_LEFT_RIGHT),(27,134))
                elif damage=='duplicate':canvas.paste(canvas.crop((312,147,357,195)),(200,147))
                else:
                    for y in range(134,210):
                        for x in range(27,390):
                            r,g,b=pixels[x,y]
                            if not (r<100 and 25<g<180 and b>110 and b-g>20):pixels[x,y]=(155,155,160)
                canvas.save(path)
                with self.assertRaises(ValueError):game_lifecycle.button(value,'confirmation-discard',path)

    def session(self,initial_warning=False,uncertain=False,save=False,incomplete=False):
        host=fixture.ShutdownGuardTests();host.setUp();self.addCleanup(host.doCleanups)
        native,options=host.unsaved_exit()
        warning,path,canvas=self.surface(1,(435,510),(1278,1376))
        if incomplete:warning['lines'].pop()
        host.frames=[warning] if initial_warning else [fixture.observed(['MENU','Save','Save As...','Exit Game']),warning]
        def capture(_state,image,_request):
            host.calls.append(('capture',{}));canvas.save(image)
            return {'ok':True,'width':1278,'height':1376}
        host.capture=capture;presses=[0]
        def handler(action,kwargs):
            if action=='test_snapshot':return native
            if action=='test_input':
                presses[0]+=1
                if uncertain:return {'ok':False,'input_submitted':True,'input_state':-4}
                if presses[0]==(1 if initial_warning else 2):host.alive=False
        host.handler=handler
        result,proof=host.run_shutdown(**({'save':True} if save else options))
        return result,proof,host.calls

    def test_normal_unsaved_shutdown_uses_single_measured_confirmation_and_never_saves(self):
        for initial in (False,True):
            with self.subTest(initial=initial):
                result,proof,calls=self.session(initial_warning=initial)
                self.assertTrue(result['ok'],proof.get('error'));self.assertTrue(result['save_files_unchanged_verified'])
                self.assertFalse(proof['save_and_exit_input_accepted'])
                clicks=[json.loads(k['value'])['value'] for action,k in calls if action=='test_input']
                self.assertEqual(len(clicks),1 if initial else 2)
                self.assertEqual(clicks[-1]['x'],770);self.assertEqual(clicks[-1]['y'],680)
                self.assertFalse(any(action in ('test_save','test_pause','test_play') for action,_ in calls))

    def test_lost_click_ack_is_never_replayed_and_unrecognized_modal_submits_no_input(self):
        result,proof,calls=self.session(initial_warning=True,uncertain=True)
        self.assertFalse(result['ok']);self.assertEqual(sum(a=='test_input' for a,_ in calls),1)
        self.assertFalse(any(a=='test_quit' for a,_ in calls))
        for options in ({'initial_warning':True,'incomplete':True},{'initial_warning':True,'save':True}):
            result,proof,calls=self.session(**options)
            self.assertFalse(result['ok']);self.assertFalse(any(a in ('test_input','test_quit') for a,_ in calls))


if __name__=='__main__':unittest.main()
