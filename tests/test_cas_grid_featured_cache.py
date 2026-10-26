"""Featured remains an authenticated prefix before Publication, Attach, Skin and RowDelta."""
from pathlib import Path
import ast,os,sys,unittest
ROOT=Path(__file__).resolve().parents[1]
PROJECT=next(parent for parent in(ROOT,*ROOT.parents)if(parent/'tools/cas_grid_budget.py').is_file())
sys.path[:0]=[str(ROOT/'tools'),str(PROJECT/'tools'),str(ROOT/'tests'),str(PROJECT/'tests')]
import cas_grid_featured as featured
import test_cas_grid_budget_cache as cache_harness
BUILD=Path(os.environ.get('APEX_CAS_GRID_FEATURED_BUILD_SOURCE',ROOT/'tools/cas_ui_build.py'))


class FeatureCacheTests(unittest.TestCase):
    def run_prefix(self,stage,refuse=None):
        original=cache_harness.BUILD;cache_harness.BUILD=BUILD
        try:return cache_harness.CacheTests('runTest').cached(stage,refuse)
        finally:cache_harness.BUILD=original

    def test_verified_slice_prefix_runs_each_missing_stage_in_exact_order(self):
        result,calls,cache,prior,key=self.run_prefix('slice')
        self.assertEqual([row[0]for row in calls],['cas_grid_slice.verify','cas_grid_budget.adapt',
            'cas_grid_featured.adapt','cas_grid_publication.adapt','cas_grid_staging_attach.adapt','cas_swatch_columns.adapt','cas_grid_row_delta.adapt','cas_grid_physical.adapt','cas_grid_intrinsic.adapt'])
        self.assertIs(calls[0][1][0],prior);self.assertEqual(calls[0][1][1],b'cached')
        self.assertEqual(calls[2][1][1],b'cas_grid_budget');self.assertEqual(result[0],b'cas_grid_intrinsic')

    def test_verified_budget_prefix_does_not_recompile_budget_or_earlier_stages(self):
        result,calls,*_=self.run_prefix('budget')
        self.assertEqual([row[0]for row in calls],['cas_grid_budget.verify','cas_grid_featured.adapt',
            'cas_grid_publication.adapt','cas_grid_staging_attach.adapt','cas_swatch_columns.adapt','cas_grid_row_delta.adapt','cas_grid_physical.adapt','cas_grid_intrinsic.adapt'])
        self.assertEqual(result[0],b'cas_grid_intrinsic')

    def test_featured_is_verified_before_newer_terminal_stages_and_cannot_return_early(self):
        result,calls,cache,prior,key=self.run_prefix('featured')
        self.assertEqual([row[0]for row in calls],['cas_grid_featured.verify','cas_grid_publication.adapt',
            'cas_grid_staging_attach.adapt','cas_swatch_columns.adapt','cas_grid_row_delta.adapt','cas_grid_physical.adapt','cas_grid_intrinsic.adapt'])
        self.assertIs(calls[0][1][0],prior);self.assertEqual(result[0],b'cas_grid_intrinsic')
        self.assertIn('continued',cache)

    def test_refused_featured_prefix_or_later_compiler_cannot_return_stale_bytes(self):
        for refusal in('cas_grid_featured.verify','cas_grid_publication.adapt',
                       'cas_grid_staging_attach.adapt','cas_swatch_columns.adapt','cas_grid_row_delta.adapt','cas_grid_physical.adapt','cas_grid_intrinsic.adapt'):
            with self.subTest(refusal=refusal):
                result,calls,*_=self.run_prefix('featured',refusal)
                self.assertIsNone(result);self.assertEqual(calls[-1][0],refusal)

    def test_shape_admission_keeps_featured_budget_and_publication_predecessors_exact(self):
        previous=cache_harness.BUILD;cache_harness.BUILD=BUILD
        try:gate=cache_harness.CacheTests('runTest').function('current_grid_stages',{})
        finally:cache_harness.BUILD=previous
        tail={}
        for key in reversed(('slice_contract','scroll_contract','swatch_provider_contract','progress_contract','product_rows_contract')):
            tail={key:{},'previous_stage_adapter':tail}
        budget={'budget_contract':{},'previous_stage_adapter':tail}
        final={'featured_contract':{},'previous_stage_adapter':budget}
        for valid in(tail,budget,final):self.assertTrue(gate(valid))
        for invalid in({},tail['previous_stage_adapter'],{'featured_contract':{},'previous_stage_adapter':tail},
                       {'budget_contract':None,'previous_stage_adapter':tail},
                       {'publication_trace_contract':{},'previous_stage_adapter':budget}):
            self.assertFalse(gate(invalid))

    def test_fresh_main_order_and_complete_owned_source_pins_remain_explicit(self):
        source=BUILD.read_text(encoding='utf-8');tree=ast.parse(source)
        assignment=next(node for node in tree.body if isinstance(node,ast.Assign)and
                        any(isinstance(target,ast.Name)and target.id=='PINNED_SOURCES'for target in node.targets))
        self.assertTrue(set(featured.SOURCES)<=set(ast.literal_eval(assignment.value)))
        steps=('payload, budget_main_contract = cas_grid_budget.adapt_main',
               'payload, featured_main_contract = cas_grid_featured.adapt_main',
               'payload, publication_main_contract = cas_grid_publication.adapt_main',
               'payload, swatch_columns_main_contract = cas_swatch_columns.adapt_main',
               'payload, row_delta_main_contract = cas_grid_row_delta.adapt_main')
        self.assertEqual([source.index(step)for step in steps],sorted(source.index(step)for step in steps))
        self.assertIn('return finish_grid_provider(adapter, grid_payload',source)


if __name__=='__main__':unittest.main()
