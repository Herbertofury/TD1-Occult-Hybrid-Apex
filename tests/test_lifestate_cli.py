from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import lifestate_cli
import apex_cli


class LifeStateCliTests(unittest.TestCase):
    def args(self, operation, **values):
        return Obj(operation=operation,sim_id='18446744073709551615',**values)

    def test_inventory_never_accepts_a_hidden_edit(self):
        for op in ('catalog','list'):
            self.assertIsNone(lifestate_cli.argument(self.args(op))[1])
            with self.assertRaises(ValueError):lifestate_cli.argument(self.args(op,id='hidden'))

    def test_capture_is_named_full_appearance_without_external_payload(self):
        route,value=lifestate_cli.argument(self.args('capture',id='plant_form',lifestate='PLANTSIM',label='Plant details',base_form=1))
        self.assertEqual(route,'lifestate_form_capture')
        self.assertEqual(set(value),{'id','lifestate','label','base_form'})

    def test_bind_and_select_require_exact_inspected_identity(self):
        for op in ('bind','select'):
            self.assertEqual(lifestate_cli.argument(self.args(op,id='original',expected_sha256='a'*64))[0],'lifestate_form_'+op)
            for digest in (None,'','a'*63,'A'*64):
                with self.assertRaises(ValueError):lifestate_cli.argument(self.args(op,id='original',expected_sha256=digest))

    def test_invalid_native_ids_boolean_flags_or_whole_sim_payloads_are_refused(self):
        for sid in ('0','01','-1',str(1<<64)):
            args=self.args('list');args.sim_id=sid
            with self.assertRaises(ValueError):lifestate_cli.argument(args)
        with self.assertRaises(ValueError):lifestate_cli.argument(self.args('capture',id='x',lifestate='GHOST',label='Ghost',base_form=True))
        with self.assertRaises(ValueError):lifestate_cli.argument(self.args('select',id='x',expected_sha256='a'*64,label='replace'))

    def test_parser_exposes_cli_without_clicks_and_requires_evidence_output(self):
        parser=apex_cli.parser()
        args=parser.parse_args(['lifestate','capture','--state','state.json','--sim-id','123','--output','proof.json',
            '--id','reaper','--lifestate','REAPER','--label','My Reaper','--base-form','1'])
        self.assertEqual(lifestate_cli.argument(args)[0],'lifestate_form_capture')

    def test_revalidation_cannot_smuggle_an_edit_or_skip_document_identity(self):
        values=dict(expected_document_sha256='a'*64,prior_pid=456,household_id='7',save_guid='99')
        self.assertEqual(lifestate_cli.argument(self.args('revalidate',**values))[0],'lifestate_form_revalidate')
        for changed in (dict(id='replace'),dict(prior_pid=True),dict(household_id='0'),dict(expected_document_sha256='b')):
            with self.subTest(changed=changed),self.assertRaises(ValueError):
                lifestate_cli.argument(self.args('revalidate',**dict(values,**changed)))
        with self.assertRaises(ValueError):lifestate_cli.argument(self.args('list',**values))
