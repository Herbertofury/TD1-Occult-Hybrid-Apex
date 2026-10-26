"""Run the established committed/staging regression suite through this layer."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];PROJECT=next(p for p in(ROOT,*ROOT.parents)if(p/'tools/cas_grid_budget.py').is_file())
sys.path[:0]=[str(ROOT/'tools'),str(PROJECT/'tests'),str(PROJECT/'tools')]
import cas_grid_featured as featured
import test_cas_grid_presentation as base

class ExistingPresentationTests(base.PresentationTests):
    def case(self,source):
        old=base.stage
        try:
            base.stage=featured
            return super().case(source)
        finally:
            base.stage=old
