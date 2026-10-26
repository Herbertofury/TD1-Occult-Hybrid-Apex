"""Actual-AS bodies, visible-empty-card oracle and reentry ownership guards."""
from pathlib import Path
import subprocess,sys,unittest
H=Path(__file__).resolve().parents[1];R=next(p for p in(H,*H.parents)if(p/'tools/cas_grid_featured.py').is_file());sys.path[:0]=[str(H/'tools'),str(R/'tools'),str(R/'tests')]
import cas_grid_staging_attach as stage
import test_cas_grid_presentation as f
from types import SimpleNamespace
FIXTURE_STAGE=SimpleNamespace(helpers=lambda:stage.helpers(kind='featured-fixture'))


def js(module):
    old=f.stage
    try:f.stage=module;return f.javascript().replace('{get:function','{configurable:true,get:function')
    finally:f.stage=old


class AttachTests(unittest.TestCase):
    def case(self,code,original=False):
        text=f.NATIVE_MOCK+js(stage.featured if original else FIXTURE_STAGE)+f.BOOT+'\nfunction uint(v){return v>>>0;}\n'+code
        p=subprocess.run(['node','-'],input=text,text=True,capture_output=True,timeout=15);self.assertEqual(p.returncode,0,p.stdout+p.stderr)
    def test_prior_actual_code_admits_a_visible_empty_staging_widget_before_draw(self):
        self.case('''const g=new NativeGrid(100,0);g.ApexGridBegin(request(g,6,{viewHeight:400}));
let blank=0;for(let i=0;i<300&&!blank;i++){g.ApexGridStep(1,0);blank=g.mGridView.children.filter(c=>c.visible&&!c.item).length;}
assert.ok(blank>0,'prior native-default-visible attachment must reproduce blank overlay');''',original=True)
    def test_every_new_attachment_stays_hidden_until_ready_publication(self):
        self.case('''const g=new NativeGrid(100,0);g.ApexGridBegin(request(g,6,{viewHeight:400}));let observed=0;
g.hooks.attach=c=>{observed++;assert.equal(c.visible,false,'hidden BEFORE native stage callback');};
for(let i=0;i<4000&&g.ApexGridStatus().phase!=='done';i++){g.ApexGridStep(1,0);if(g.ApexGridStatus().phase!=='done')for(const c of g.mGridView.children)assert.equal(c.visible,false);}
assert.ok(observed>0);assert.equal(g.ApexGridStatus().phase,'done');assert.ok(rendered(g).length>0);''')
    def test_retained_bank_is_never_covered_by_a_visible_empty_replacement(self):
        self.case('''const g=new NativeGrid(100,0);g.ApexGridBegin(request(g,6,{viewHeight:400}));bounded(g);const old=g.mCells.slice(),ids=rendered(g);
g.delayImages=true;g.ApexGridBegin(request(g,12,{viewHeight:400,width:53.5,height:73.5,scale:.5}));
for(let i=0;i<2000&&g.ApexGridStatus().phase!=='textures';i++){g.ApexGridStep(1,0);assert.deepEqual(rendered(g),ids);for(const c of g.mGridView.children)if(!old.includes(c))assert.equal(c.visible,false,'all replacement roots hidden including empty ones');}
assert.equal(g.ApexGridStatus().phase,'textures');stagedReady(g);bounded(g);assert.ok(rendered(g).length>0);''')
    def test_native_configui_that_unhides_pending_cell_is_rehidden_before_yield(self):
        self.case('''const g=new NativeGrid(100,0);g.hooks.attach=c=>{assert.equal(c.visible,false);c.visible=true;};g.ApexGridBegin(request(g,6,{viewHeight:400}));
for(let i=0;i<1000&&g.ApexGridStatus().phase!=='bind';i++){g.ApexGridStep(1,0);for(const c of g.mGridView.children)assert.equal(c.visible,false);}
assert.equal(g.ApexGridStatus().phase,'bind');''')
    def test_replaced_authoritative_state_adopting_cell_is_not_overwritten(self):
        self.case('''const g=new NativeGrid(100,0);g.ApexGridBegin(request(g,6,{viewHeight:400}));let adopted=null;
g.hooks.attach=c=>{c.visible=true;adopted=c;g.apexGridState={replacement:true};};
let stopped=false;for(let i=0;i<100&&!adopted;i++){try{g.ApexGridStep(1,0);}catch(e){stopped=true;}}
assert.ok(adopted);assert.equal(adopted.visible,true);assert.equal(g.apexGridState.replacement,true);''')
    def test_native_attach_arbitrary_throw_value_propagates_unchanged(self):
        self.case('''const g=new NativeGrid(100,0);g.ApexGridBegin(request(g,6,{viewHeight:400}));
const s=g.apexGridState,j=s.job;j.lease=true;s.lease=j;s.presentation={working:true};const cell=new Cell();cell.owner=g;j.pendingCell=cell;j.pendingAttached=true;
const sentinel={native:'same'};g.hooks.attach=()=>{throw sentinel;};let caught=null;try{g.ApexGridAttach(cell);}catch(e){caught=e;}
assert.equal(caught,sentinel);assert.equal(cell.visible,false);assert.equal(g.calls.filter(x=>x==='attach').length,1);''')
    def test_nonpending_committed_or_unarmed_call_keeps_original_visibility(self):
        self.case('''const g=new NativeGrid(100,0);const c=new Cell();c.owner=g;g.ApexGridAttach(c);assert.equal(c.visible,true);
g.ApexGridBegin(request(g,6,{viewHeight:400}));const s=g.apexGridState;s.presentation={working:true};s.job.pendingCell=null;const other=new Cell();other.owner=g;
g.ApexGridAttach(other);assert.equal(other.visible,true);assert.equal(other.parent,g.mGridView);''')
    def test_rollback_keeps_ready_old_art_and_hides_all_new_empty_roots(self):
        self.case('''const g=new NativeGrid(100,0);g.ApexGridBegin(request(g,6,{viewHeight:400}));bounded(g);const old=g.mCells.slice(),ids=rendered(g);
g.ApexGridBegin(request(g,12,{viewHeight:400,width:53.5,height:73.5,scale:.5}));for(let i=0;i<2000&&g.ApexGridStatus().phase!=='position';i++)g.ApexGridStep(1,0);
g.ApexGridPresentationRollback();assert.deepEqual(rendered(g),ids);for(const c of g.mGridView.children)if(!old.includes(c))assert.equal(c.visible,false);''')


if __name__=='__main__':unittest.main()
