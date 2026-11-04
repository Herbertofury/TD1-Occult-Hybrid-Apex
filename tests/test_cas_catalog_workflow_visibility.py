from pathlib import Path
from types import SimpleNamespace
import re,subprocess,sys,unittest
HERE=Path(__file__).resolve().parents[1]
ROOT=Path(__file__).resolve().parents[3] if HERE.name.startswith('v350-') else HERE
sys.path[:0]=[str(HERE/'tools'),str(ROOT/'tools'),str(ROOT/'tests')]
import cas_catalog_workflow as workflow
import test_cas_catalog_scheduling as old
import test_cas_card_geometry as card

def body(name,args,source=None):
    text=workflow.stage.fragment() if source is None else Path(source).read_text()
    text=re.sub(r'(?m)^private function ','      private function ',text)
    result=card.javascript_function(name,args,SimpleNamespace(read_text=lambda **kwargs:text))
    return re.sub(r'catch\((\w+):\w+\)',r'catch(\1)',result).replace(' is Function',' instanceof Function')

def harness(fixed=True):
    previous=old.scheduling_function
    try:
        old.scheduling_function=lambda name,parameters='': body(name,parameters) if fixed and name in workflow.stage.REPLACED else previous(name,parameters)
        code=old.ActiveGridSchedulingTests().harness()
    finally:old.scheduling_function=previous
    code+=(body('ApexCatalogGridInput','lease') if fixed else body('ApexCatalogGridInput','lease',ROOT/'Source/CASUi/catalog_grid_transaction_methods.as'))+'ApexCatalogGridInput=ApexCatalogGridInput.bind(root);\n'
    code+=r'''
var apexBoundSim='11',apexFormsSelectedId='active/2',apexFormsNativeGeneration='42',apexFormsNativeState='bound',apexFormsDesiredId='',
 apexFormsIntent=null,apexFormsNativeIntent=null,apexMoleculeIntent=null,apexPairIntent=null,apexFormsApplying=false;
function complete(){const lease=owned();Object.assign(lease,{view:gridView,panel_kind:'clothing',cell_type:cellType,feed,
 sim_id:'11',household_id:'22',layer:0,native_kind:2,shell_kind:4,native_mask:127,owner:'active/2',session:1,native_generation:'42',state:mCurrState,
 outfit_type:9,outfit_index:0});mCurrSimInfo={simId:'11',householdId:'22',occultLayer:0,occultType:2,allOccultTypes:127};return lease;}
'''
    return code

class WorkVisibilityTests(unittest.TestCase):
    def execute(self,text,fixed=True):
        result=subprocess.run(['node'],input=harness(fixed)+text,text=True,capture_output=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_original_source_reproduces_lease_retirement_for_view_self_mask(self):
        self.execute(r'''
const lease=complete();gridView.visible=false;assert.equal(ApexCatalogPanelVisible(panel),false);
ApexCatalogGridFrame();assert.equal(cancels,1);assert.equal(lease.active,false);assert.equal(apexCatalogGrid.retiring.lease,lease);
''',fixed=False)

    def test_exact_masked_live_pending_lease_remains_current_but_input_stays_blocked(self):
        self.execute(r'''
const lease=complete();gridView.visible=false;
assert.equal(ApexCatalogPanelVisible(panel),false);assert.equal(ApexCatalogGridLeaseCurrent(lease),true);
assert.equal(ApexCatalogGridInput(lease),false);assert.equal(queries,0);assert.equal(steps,0);assert.equal(cancels,0);
''')

    def test_pending_work_advances_and_can_restore_view_without_retiring_original_lease(self):
        self.execute(r'''
const lease=complete();gridView.visible=false;
ApexCatalogGridFrameObserve=()=>({sim_id:'11',household_id:'22',owner:'active/2',session:1,layer:0,native_kind:2,shell_kind:4,
 native_mask:127,native_generation:'42',outfit_type:9,outfit_index:0,state:mCurrState});
ApexCatalogGridMatches=(l,c)=>l===lease&&c.native_kind===2&&c.shell_kind===4;
ApexCatalogGridRequest=()=>({columns:6});
grid.ApexGridStep=(ops,deadline)=>{steps++;assert.equal(ops,64);assert.equal(deadline,1);assert.equal(lease.active,true);
 gridView.visible=true;native.phase='done';return {...native};};
ApexCatalogGridFrame();assert.equal(steps,1);assert.equal(cancels,0);assert.equal(apexCatalogGrid.lease,lease);
assert.equal(lease.active,true);assert.equal(apexCatalogGrid.retiring,null);assert.equal(gridView.visible,true);
assert.equal(ApexCatalogPanelVisible(panel),true);
''')

    def test_every_real_ancestor_hidden_still_refuses_work_and_retires(self):
        for target in ('view','list','panel','layer','root'):
            self.execute(r'''
const lease=complete();gridView.visible=false;'''+target+r'''.visible=false;
assert.equal(ApexCatalogGridLeaseCurrent(lease),false);assert.equal(ApexCatalogGridInput(lease),false);
ApexCatalogGridFrame();assert.equal(cancels,1);assert.equal(lease.active,false);assert.equal(steps,0);
''')

    def test_original_view_identity_is_required(self):
        self.execute(r'''
const lease=complete();gridView.visible=false;lease.view={...gridView};
assert.equal(ApexCatalogGridLeaseCurrent(lease),false);ApexCatalogGridFrame();assert.equal(cancels,1);
''')

    def test_missing_legacy_view_receipt_cannot_claim_masked_work(self):
        self.execute(r'''
const lease=complete();gridView.visible=false;delete lease.view;
assert.equal(ApexCatalogGridLeaseCurrent(lease),false);
''')

    def test_replaced_grid_or_feed_refuses_even_if_view_and_ancestors_match(self):
        for change in ('list.mGridLayout={};','lease.feed={};','lease.cell_type=function(){};'):
            self.execute('const lease=complete();gridView.visible=false;'+change+
                         'assert.equal(ApexCatalogGridLeaseCurrent(lease),false);')

    def test_inactive_error_cancelled_or_done_without_work_do_not_gain_work_permission(self):
        for change in ('lease.active=false;','apexCatalogGrid.error="failed";',
                       'grid.ApexGridNeedsWork=()=>false;','grid.ApexGridNeedsWork=()=>1;'):
            self.execute('const lease=complete();gridView.visible=false;'+change+
                         'assert.equal(ApexCatalogGridLeaseCurrent(lease),false);')

    def test_masked_view_cannot_bypass_the_actual_list_scroller_chain(self):
        self.execute(r'''
const lease=complete();gridView.visible=false;gridView.parent=panel;
assert.equal(ApexCatalogGridLeaseCurrent(lease),false);
''')

    def test_ancestry_cycle_does_not_spin_or_enable_work(self):
        self.execute(r'''
const lease=complete();gridView.visible=false;layer.parent=layer;
assert.equal(ApexCatalogGridLeaseCurrent(lease),false);
''')

    def test_hiding_another_current_panel_never_grants_old_hidden_panel_work(self):
        self.execute(r'''
const lease=complete();gridView.visible=false;mCurrentPanel={};
assert.equal(ApexCatalogGridLeaseCurrent(lease),false);
''')

    def test_bootstrap_hidden_scope_remains_structural_not_stepped(self):
        self.execute(r'''
const lease=complete();lease.phase='bootstrap';gridView.visible=false;panel.visible=false;
ApexCatalogGridFrame();assert.equal(steps,0);assert.equal(begins,0);assert.equal(cancels,0);
''')

    def test_visible_fast_path_does_not_call_new_work_probe(self):
        self.execute(r'''
const lease=complete();grid.ApexGridNeedsWork=()=>{throw Error('must not probe when fully visible');};
assert.equal(ApexCatalogGridLeaseCurrent(lease),true);assert.equal(ApexCatalogPanelVisible(panel),true);
''')

if __name__=='__main__':unittest.main()
