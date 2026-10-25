"""Display-only controls cannot smuggle engine edits or false acknowledgements."""
import copy
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core import cas_controls


class PanelLayoutTests(unittest.TestCase):
    def setUp(self):
        self.request=dict(operation='panel-layout',x=.2,y=.4,scale=.65,locked=False)
        self.client=dict(control=dict(operation='panel-layout',appearance_written=False,workspace=dict(panels=dict(
            x=.2,y=.4,scale=.65,locked=False,appearance_written=False))))

    def test_complete_bounded_display_request_and_automatic_placement(self):
        self.assertEqual(cas_controls.wire(self.request,lambda _:self.fail('Not a CAS category')),(0,0,0,'0.2,0.4,0.65,0'))
        automatic=dict(self.request,x=-1,y=-1,scale=.35,locked=True)
        self.assertEqual(cas_controls.wire(automatic,None),(0,0,0,'-1,-1,0.35,1'))
        cas_controls.validate(self.client,self.request)

    def test_invalid_preferences_do_not_reach_ui(self):
        for field,values in [('x',[-.5,1.1,True,math.nan]),('y',[-2,math.inf,'0']),
                             ('scale',[.34,1.51,False]),('locked',[0,'false',None])]:
            for value in values:
                with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                    cas_controls.wire(dict(self.request,**{field:value}),None)
        with self.assertRaises(ValueError):cas_controls.wire(dict(self.request,service='SaveAndExitCAS'),None)

    def test_postcondition_requires_exact_preferences_and_no_appearance_write(self):
        for field,value in [('x',.3),('y',None),('scale',.7),('locked',0),('appearance_written',True)]:
            changed=copy.deepcopy(self.client);changed['control']['workspace']['panels'][field]=value
            with self.subTest(field=field),self.assertRaises(cas_controls.PostconditionMismatch):
                cas_controls.validate(changed,self.request)
        changed=copy.deepcopy(self.client);changed['control']['appearance_written']=True
        with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(changed,self.request)


if __name__=='__main__':unittest.main()
