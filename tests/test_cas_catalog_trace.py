"""Bound diagnostic windows and exact acknowledgements through the public CLI."""
import copy
from pathlib import Path
import sys
import unittest
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parents[1]/'Source')]
from apex_core import cas_controls
from apex_cli import parser

class CatalogTraceTests(unittest.TestCase):
    def test_public_cli_and_wire_preserve_exact_duration(self):
        for ms in (0,1,30000):
            args=parser().parse_args(['cas','catalog-trace','--state','test.json','--milliseconds',str(ms)])
            self.assertEqual(args.milliseconds,ms)
            self.assertEqual(cas_controls.wire(dict(operation='catalog-trace',milliseconds=ms),lambda _:self.fail('Diagnostic must not navigate panels')),(0,0,0,str(ms)))
        for ms in (-1,30001,True,False,1.5,None,'1000'):
            with self.subTest(ms=ms),self.assertRaises(ValueError):
                cas_controls.wire(dict(operation='catalog-trace',milliseconds=ms),lambda _:None)
        with self.assertRaises(ValueError):cas_controls.wire(dict(operation='catalog-trace',milliseconds=1,other=1),lambda _:None)

    def test_acknowledgement_is_bounded_and_never_authorizes_an_appearance_write(self):
        request=dict(operation='catalog-trace',milliseconds=1)
        client=dict(control=dict(operation='catalog-trace',appearance_written=False,trace=dict(requested_ms=1,enabled=False,callback_active=False,appearance_written=False,record_limit=32,records=[],aggregates={})))
        cas_controls.validate(client,request) # A tiny window can expire before the next-tick ACK.
        for key,value in [('requested_ms',2),('requested_ms',True),('enabled',0),('callback_active',None),('callback_active',True),('enabled',True),('appearance_written',True),('record_limit',33),('records',[{}]*33),('aggregates',[])]:
            bad=copy.deepcopy(client);bad['control']['trace'][key]=value
            with self.subTest(key=key,value=str(value)[:32]),self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(bad,request)
        stopped=copy.deepcopy(client);stopped['control']['trace'].update(requested_ms=0,enabled=True)
        with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(stopped,dict(operation='catalog-trace',milliseconds=0))

if __name__=='__main__':unittest.main()
