from pathlib import Path
import sys,subprocess,unittest,re
ROOT=Path(__file__).resolve().parents[1];PROJECT=next(p for p in(ROOT,*ROOT.parents)if(p/'tools/cas_grid_slice.py').is_file());sys.path.insert(0,str(PROJECT/'tests'));from test_cas_card_geometry import javascript_function

class ProbeTests(unittest.TestCase):
 def case(self,code):
  js=javascript_function('ApexCatalogGridStatus',source=ROOT/'Source/CASUi/catalog_grid_budget_main_status.as');result=subprocess.run(['node','-'],input=BOOT+js+code,capture_output=True,text=True,timeout=10);self.assertEqual(result.returncode,0,result.stdout+result.stderr)
 def test_default_status_and_all_other_operations_invoke_zero_probe_clocks(self):
  self.case("for(const op of [null,'status','catalog-search','catalog-input']){apexPendingFields=op===null?null:['id','sim',op];const r=ApexCatalogGridStatus();assert.equal('clock_probe'in r,false);}assert.equal(clocks,0);assert.equal(providers,0);")
 def test_explicit_catalog_state_captures_a_bracket_once_per_uuid(self):
  self.case("apexPendingFields=['id','sim','catalog-state'];const first=ApexCatalogGridStatus();assert.equal(first.clock_probe.main_before_ms,5000);assert.equal(first.clock_probe.main_after_ms,5001);assert.equal(first.clock_probe.provider_ms,4000);assert.equal(first.clock_probe.provider_inside_main_bracket,false);const second=ApexCatalogGridStatus();assert.deepEqual(second.clock_probe,first.clock_probe);assert.notEqual(second.clock_probe,first.clock_probe);assert.equal(clocks,2);assert.equal(providers,1);apexPendingFields[0]='next';ApexCatalogGridStatus();assert.equal(clocks,4);assert.equal(providers,2);")
 def test_nonce_and_disconnect_refusals_are_clock_free(self):
  self.case("apexPendingFields=['id','sim','catalog-state'];apexClaimNonce='wrong';assert.equal('clock_probe'in ApexCatalogGridStatus(),false);apexClaimNonce=apexNonce;apexDisconnected=true;assert.equal('clock_probe'in ApexCatalogGridStatus(),false);assert.equal(clocks,0);assert.equal(providers,0);")
 def test_unowned_or_unbound_grid_is_an_explicit_unavailable_result(self):
  self.case("apexPendingFields=['id','sim','catalog-state'];current=false;const r=ApexCatalogGridStatus();assert.equal(r.clock_probe.available,false);assert.equal(clocks,0);assert.equal(providers,0);")
 def test_native_clock_scope_reentry_is_refused_without_caching(self):
  self.case("apexPendingFields=['id','sim','catalog-state'];hook=()=>{apexClaimNonce='changed';};assert.throws(()=>ApexCatalogGridStatus(),/exact native owner lease/);assert.equal(apexCatalogGrid.clockProbeRequest,undefined);")
 def test_nonfinite_clock_is_refused_before_serialization(self):
  self.case("apexPendingFields=['id','sim','catalog-state'];providerValue=NaN;assert.throws(()=>ApexCatalogGridStatus(),/finite native integer/);assert.equal(apexCatalogGrid.clockProbeRequest,undefined);")
 def test_cached_sample_cannot_move_to_another_lease_generation(self):
  self.case("apexPendingFields=['id','sim','catalog-state'];ApexCatalogGridStatus();lease.generation++;assert.throws(()=>ApexCatalogGridStatus(),/sampled owner lease/);assert.equal(providers,1);")
 def test_signed_main_rollover_is_explicit_not_misclassified_as_alignment(self):
  self.case("times=[2147483647,-2147483648];providerValue=2147483647;apexPendingFields=['id','sim','catalog-state'];const r=ApexCatalogGridStatus();assert.equal(r.clock_probe.main_wrap,true);assert.equal(r.clock_probe.provider_inside_main_bracket,false);")
BOOT="""
const assert=require('node:assert/strict');function int(n){return n|0;}let clocks=0,providers=0,times=[5000,5001,5002,5003],providerValue=4000,hook=null,current=true;
const flash={utils:{getTimer(){return times[clocks++];}}};const lease={phase:'bound',generation:7,active:true};const grid={ApexGridNow(){providers++;if(hook)hook();return providerValue;},ApexGridStatus(){return {phase:'done'};}};
let apexCatalogGrid={enabled:true,lease,grid,generation:7},apexPendingFields=null,apexClaimNonce='nonce',apexNonce='nonce',apexDisconnected=false,apexSocketActive=true;
function ApexCatalogGridLeaseCurrent(l){return current&&l===lease&&l.active;}function ApexClone(x){return JSON.parse(JSON.stringify(x));}
"""
if __name__=='__main__':unittest.main()
