"""Explicit compiled artifact qualification; absent fixtures are honest skips."""
from pathlib import Path
import copy,json,os,sys,unittest
HERE=Path(__file__).resolve().parents[1]
ROOT=Path(__file__).resolve().parents[3] if HERE.name.startswith('v350-') else HERE
sys.path[:0]=[str(HERE/'tools'),str(ROOT/'tools')]
import cas_catalog_workflow as module
FIXTURE=os.environ.get('APEX_CATALOG_WORKFLOW_FIXTURE')

@unittest.skipUnless(FIXTURE,'Set APEX_CATALOG_WORKFLOW_FIXTURE to an explicit compiled/current-terminal fixture')
class WorkflowChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path=Path(FIXTURE);cls.final=(cls.path/'final.swf').read_bytes()
        cls.contract=json.loads((cls.path/'contract.json').read_bytes())
    def bad(self,change):
        made=copy.deepcopy(self.contract);change(made)
        with self.assertRaises(ValueError):module.verify_main(made,self.final)
    def test_exact_compiled_terminal_and_recursive_current_scheduler_pass(self):
        self.assertTrue(module.verify_main(self.contract,self.final))
    def test_full_raw_rollback_equals_exact_actual349_main(self):
        prior,base=module.historical(self.contract,self.final)
        self.assertEqual(base,(self.path/'baseline.swf').read_bytes())
        self.assertEqual(prior['final_swf_sha256'],module.sha(base))
        self.assertTrue(module.previous.verify_main(prior,base))
    def test_partial_new_source_pins_refuse(self):
        self.bad(lambda c:c[module.CONTRACT]['source_sha256'].pop(module.SOURCES[0]))
    def test_stale_new_source_pin_refuses(self):
        self.bad(lambda c:c[module.CONTRACT]['source_sha256'].__setitem__(module.SOURCES[0],'0'*64))
    def test_missing_private_failure_helper_inventory_refuses(self):
        self.bad(lambda c:c[module.CONTRACT].__setitem__('appended_methods',0))
    def test_native_body_change_claim_refuses(self):
        self.bad(lambda c:c[module.CONTRACT].__setitem__('changed_original_native_bodies',1))
    def test_predecessor_or_previous_stage_digest_refuses(self):
        self.bad(lambda c:c.__setitem__('previous_stage_sha256','0'*64))
        self.bad(lambda c:c['previous_stage_contract'].__setitem__('postproof_sha256','0'*64))
    def test_final_hash_or_raw_abc_tamper_refuses(self):
        self.bad(lambda c:c.__setitem__('final_swf_sha256','0'*64))
        with self.assertRaises(ValueError):module.verify_main(self.contract,self.final[:-1]+bytes([self.final[-1]^1]))
    def test_incomplete_rollback_body_inventory_refuses(self):
        self.bad(lambda c:c[module.CONTRACT]['rollback']['bodies'].pop(module.stage.REPLACED[0]))
    def test_wrong_rollback_callable_body_refuses(self):
        self.bad(lambda c:c[module.CONTRACT]['rollback']['bodies'].__setitem__(module.stage.REPLACED[0],'00'))

if __name__=='__main__':unittest.main()
