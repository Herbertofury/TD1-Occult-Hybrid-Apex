"""Native keyboard receipts must prove movement, ownership and no equip."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core import cas_controls


class CatalogKeyboardTests(unittest.TestCase):
    def client(self,key,before,after,count=20,columns=6,page=12):
        codes={'left':37,'right':39,'up':38,'down':40,'home':36,'end':35,'pageup':33,'pagedown':34}
        receipt=dict(key=codes[key],sim_id='123',owner_id='native/2',menu_state=99,
            index_before=before,index_after=after,count=count,columns=columns,page_step=page,click_dispatched=False)
        return dict(sim=dict(simId='123'),menu_state=99,form_strip=dict(selected_owner_id='native/2',native_owner_state='bound'),
            control=dict(operation='catalog-key',appearance_written=False,
                workspace=dict(keyboard=dict(index=after,pending=0,queued=0,receipt=receipt))))

    def test_full_rows_partial_last_row_edges_and_native_columns(self):
        for key,before,after in [('right',5,6),('left',0,0),('down',5,11),('down',17,19),
                                 ('up',11,5),('up',2,0),('home',19,0),('end',3,19),
                                 ('pagedown',0,12),('pageup',13,1)]:
            request=dict(operation='catalog-key',key=key)
            self.assertEqual(cas_controls.wire(request,None),(0,0,0,key))
            cas_controls.validate(self.client(key,before,after),request)
        # The native Face grid has two columns even when clothing uses six.
        cas_controls.validate(self.client('down',1,3,columns=2),dict(operation='catalog-key',key='down'))

    def test_foreign_stale_incomplete_or_equip_results_are_refused(self):
        good=self.client('down',1,7);request=dict(operation='catalog-key',key='down')
        for field,value in [('sim_id','456'),('owner_id','native/4'),('key',39),('menu_state',100),
                            ('count',0),('columns',True),('index_after',8),('index_before',20),('click_dispatched',True)]:
            with self.subTest(field=field):
                client=deepcopy(good);client['control']['workspace']['keyboard']['receipt'][field]=value
                with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(client,request)
        for field,value in [('queued',1),('pending',40),('index',8)]:
            client=deepcopy(good);client['control']['workspace']['keyboard'][field]=value
            with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(client,request)
        for key in ['enter','a','UP',None]:
            with self.assertRaises(ValueError):cas_controls.wire(dict(operation='catalog-key',key=key),None)


if __name__=='__main__':unittest.main()
