from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tests'), str(ROOT / 'tools')]

import cas_catalog_schedule as schedule
import test_cas_card_geometry as card
SCHEDULE = schedule.ROOT
from test_cas_card_geometry import javascript_function


from types import SimpleNamespace
import re
def scheduling_function(name,parameters=''):
    # Execute the exact fragment through the existing public AS converter. Only
    # declaration indentation is normalized for that converter's delimiter.
    text=re.sub(r'(?m)^private function ', '      private function ', schedule.stage.fragment())
    return card.javascript_function(name,parameters,SimpleNamespace(read_text=lambda **kwargs:text))

class ActiveGridSchedulingTests(unittest.TestCase):
    def harness(self):
        script = r'''
const assert=require('node:assert/strict');function int(x){return Math.trunc(x);}int.MAX_VALUE=2147483647;
const stage={stageWidth:2560,visible:true};const root={visible:true,stage};
const layer={parent:root,visible:true,stage},panel={parent:layer,visible:true,stage},list={parent:panel,visible:true,stage},
 view={parent:list,visible:true,stage},gridView={parent:view,visible:true,stage};
list.mScrollerView=view;list.GetGridView=()=>gridView;panel.mcTileList=list;
let mCurrentPanel=panel,mcClothingPanel=panel,mCurrState=-2138044416,mCurrSimInfo=null;
let apexCatalogGrid=null,apexCardGeometry=null,apexCardLayout=null,apexDisconnected=false,prepares=0,queries=0,steps=0,cancels=0,begins=0,draws=0;
const flash={utils:{getTimer(){return 0;}},events:{Event:{ENTER_FRAME:'frame'}}};
const cellType=function(){};const feed={length:81};
const native={phase:'selection',cancelled:false,pendingCell:true,lease:true,error:null,committedVisible:true};
const grid={GetCellView:cellType,GetDataFeed(){return feed;},ApexGridBegin(request){begins++;return {...native};},
 ApexGridCancel(reason){cancels++;native.cancelled=true;native.phase=reason==='dispose'?'cancelled':'cancel';
  if(reason==='dispose'){native.pendingCell=false;native.lease=false;}return {...native};},
 ApexGridStep(ops,deadline){steps++;assert.equal(ops,1);assert.equal(deadline,0);assert.equal(native.phase,'cancel');
  if(native.pendingCell)native.pendingCell=false;else{native.lease=false;native.phase='cancelled';}return {...native};},
 ApexGridStatus(){return {...native};},ApexGridNeedsWork(){return true;}};
list.mGridLayout=grid;let apexOwnerSession=1;
function ApexCatalogGridProductPanel(p){return p===mcClothingPanel?'clothing':'';}
function ApexCatalogGridObserve(){queries++;throw Error('unexpected owner query');}
function ApexCatalogGridFrameObserve(){queries++;throw Error('unexpected owner query');}
function ApexCardStateFor(){return null;}function ApexCatalogGridMatches(){throw Error('unexpected bind');}
function ApexCatalogGridRequest(){throw Error('unexpected new request');}function ApexCatalogGridValidate(){return true;}
function ApexCatalogGridInput(){return false;}function ApexCatalogGridProductRow(){return true;}
function owned(){const lease={active:true,frame_validated:false,root,stage,panel,grid,phase:'bound',generation:7};
 apexCatalogGrid={enabled:true,disposed:false,running:false,input_reading:false,generation:7,frame:0,lease,grid,last:null,error:'',invalidations:0,retiring:null};return lease;}
'''
        for name, args, source in (
            ('ApexCatalogPanelVisible', 'panel', 'catalog_panel_geometry_methods.as'),
            ('ApexCatalogGridPrepare', '', 'catalog_grid_transaction_methods.as'),
            ('ApexCatalogGridLeaseCurrent', 'lease', 'catalog_grid_transaction_methods.as'),
            ('ApexCatalogGridStatus', '', 'catalog_grid_transaction_methods.as'),
            ('ApexCatalogGridFrame', 'event=null', 'catalog_grid_transaction_methods.as'),
            ('ApexCatalogGridRetireInactive', 's', 'catalog_grid_transaction_methods.as'),
            ('ApexCatalogGridInvalidate', 'reason', 'catalog_grid_transaction_methods.as'),
        ):
            body = (javascript_function(name,args,ROOT/'Source/CASUi'/source) if name=='ApexCatalogGridInvalidate' else scheduling_function(name,args))
            body = re.sub(r'catch\((\w+):\w+\)', r'catch(\1)', body).replace(' is Function',' instanceof Function')
            script += body + name + '=' + name + '.bind(root);\n'
        return script

    def run_js(self, body):
        result = subprocess.run(['node'], input=self.harness() + body, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_requested_diagnostic_reports_exact_route_and_visibility_without_native_owner_work(self):
        self.run_js(r'''
const lease=owned();panel.mcPanelBackground={width:537.35};
mCurrSimInfo={simId:'11',householdId:'22',occultLayer:0,occultType:2,allOccultTypes:127};
Object.assign(lease,{panel_kind:'clothing',cell_type:cellType,feed,sim_id:'11',household_id:'22',layer:0,native_kind:2,native_mask:127,owner:'active/2',session:1,native_generation:'42',state:mCurrState});
var apexBoundSim='11',apexFormsSelectedId='active/2',apexFormsNativeGeneration='42',apexFormsNativeState='bound',apexFormsDesiredId='',
 apexFormsIntent=null,apexFormsNativeIntent=null,apexMoleculeIntent=null,apexPairIntent=null,apexFormsApplying=false;
apexCatalogGrid.last_repair_path='legacy';apexCatalogGrid.last_repair_grid=grid;apexCatalogGrid.last_repair_panel=panel;
function ApexCatalogGridOwns(value){return value===apexCatalogGrid.grid;}
const before=JSON.stringify(native),result=ApexCatalogGridStatus().scheduling;
assert.equal(result.current_grid_matches,true);assert.equal(result.current_grid_owned,true);assert.equal(result.lease_current,true);
assert.equal(result.reached_root,true);assert.equal(result.contains_panel,true);assert.equal(result.actual_repair_path,'legacy');
assert.equal(result.width_receipt_present,false);assert.equal(result.desired_width,null);assert.equal(result.native_panel_width,537.35);
assert.equal(result.ancestors.length,6);assert.equal(queries,0);assert.equal(steps,0);assert.equal(begins,0);assert.equal(JSON.stringify(native),before);
list.visible=false;const hidden=ApexCatalogGridStatus().scheduling;assert.equal(hidden.lease_current,false);assert.equal(hidden.current_panel_visible,false);
assert.equal(queries,0);assert.equal(steps,0);
''')

    def test_true_active_native_aggregate_submenu_and_empty_leaf_remain_admitted(self):
        self.run_js(r'''
assert.equal(ApexCatalogPanelVisible(panel),true);owned();
ApexCatalogGridPrepare=()=>{prepares++;return false;};ApexCatalogGridFrame();assert.equal(prepares,1);assert.equal(cancels,0);
feed.length=0;mCurrState=12345;ApexCatalogGridFrame();assert.equal(prepares,2);assert.equal(cancels,0);assert.equal(queries,0);
''')

    def test_each_hidden_ancestor_blocks_normal_work_and_cleans_only_owned_pending_atoms(self):
        self.run_js(r'''
for(const node of[gridView,view,list,panel,layer,root]){
 native.phase='selection';native.cancelled=false;native.pendingCell=true;native.lease=true;owned();node.visible=false;
 const baseSteps=steps,baseCancel=cancels;ApexCatalogGridFrame();assert.equal(cancels,baseCancel+1);assert.equal(steps,baseSteps);
 assert.equal(apexCatalogGrid.lease.active,false);assert.equal(apexCatalogGrid.retiring.grid,grid);
 ApexCatalogGridFrame();assert.equal(steps,baseSteps+1);assert.equal(native.pendingCell,false);assert.equal(native.lease,true);
 ApexCatalogGridFrame();assert.equal(steps,baseSteps+2);assert.equal(native.lease,false);assert.equal(apexCatalogGrid.retiring,null);assert.equal(apexCatalogGrid.lease,null);
 for(let n=0;n<20;n++)ApexCatalogGridFrame();assert.equal(steps,baseSteps+2);assert.equal(cancels,baseCancel+1);
 assert.equal(native.committedVisible,true);node.visible=true;
}assert.equal(queries,0);assert.equal(begins,0);assert.equal(draws,0);
''')

    def test_early_hidden_bootstrap_stays_intercepting_without_steps_or_queries(self):
        self.run_js(r'''
apexCatalogGrid={enabled:true,disposed:false,running:false,error:'',generation:0,lease:null,grid:null,retiring:null};
mCurrentPanel=null;panel.visible=false;assert.equal(ApexCatalogGridPrepare(),true);assert.equal(apexCatalogGrid.lease.phase,'bootstrap');
const held=apexCatalogGrid.lease;for(let n=0;n<100;n++)ApexCatalogGridFrame();
assert.equal(apexCatalogGrid.lease,held);assert.equal(held.active,true);assert.equal(begins,1);assert.equal(steps,0);assert.equal(cancels,0);assert.equal(queries,0);
''')

    def test_already_invalidated_bound_owner_is_drained_without_rebinding_a_new_owner(self):
        self.run_js(r'''
const held=owned();held.active=false;native.phase='cancel';native.cancelled=true;list.visible=false;
ApexCatalogGridFrame();ApexCatalogGridFrame();ApexCatalogGridFrame();
assert.equal(native.lease,false);assert.equal(apexCatalogGrid.lease,null);assert.equal(begins,0);assert.equal(queries,0);
''')

    def test_widget_replacement_uses_existing_dispose_release_without_touching_replacement(self):
        self.run_js(r'''
owned();list.visible=false;ApexCatalogGridFrame();const replacement={};list.mGridLayout=replacement;
ApexCatalogGridFrame();assert.equal(native.phase,'cancelled');assert.equal(native.lease,false);assert.equal(steps,0);
assert.equal(list.mGridLayout,replacement);assert.equal(apexCatalogGrid.retiring,null);assert.equal(native.committedVisible,true);
''')

    def test_widget_removal_before_cleanup_capture_uses_owned_dispose_release(self):
        self.run_js(r'''
owned();panel.mcTileList=null;ApexCatalogGridFrame();assert.equal(cancels,1);
ApexCatalogGridFrame();assert.equal(native.phase,'cancelled');assert.equal(native.lease,false);
assert.equal(steps,0);assert.equal(apexCatalogGrid.lease,null);assert.equal(apexCatalogGrid.retiring,null);
assert.equal(apexCatalogGrid.error,'');assert.equal(panel.mcTileList,null);
''')

    def test_widget_replacement_before_cleanup_capture_never_drives_the_replacement(self):
        self.run_js(r'''
owned();const replacement={mGridLayout:{},GetGridView(){return {};}};panel.mcTileList=replacement;
ApexCatalogGridFrame();assert.equal(cancels,1);ApexCatalogGridFrame();
assert.equal(native.phase,'cancelled');assert.equal(native.lease,false);assert.equal(steps,0);
assert.equal(apexCatalogGrid.retiring,null);assert.equal(apexCatalogGrid.error,'');
assert.equal(panel.mcTileList,replacement);assert.equal(native.committedVisible,true);
''')

    def test_active_panel_replacement_finishes_old_owned_cleanup_before_new_begin(self):
        self.run_js(r'''
owned();const nextPanel={visible:true,stage,parent:layer},nextList={visible:true,stage,parent:nextPanel},nextView={visible:true,stage,parent:nextList},
 nextGridView={visible:true,stage,parent:nextView},nextGrid={...grid};
nextPanel.mcTileList=nextList;nextList.mGridLayout=nextGrid;nextList.mScrollerView=nextView;nextList.GetGridView=()=>nextGridView;
mCurrentPanel=mcClothingPanel=nextPanel;assert.equal(ApexCatalogPanelVisible(nextPanel),true);
assert.equal(ApexCatalogGridPrepare(),false);assert.equal(begins,0);assert.equal(cancels,1);
ApexCatalogGridRetireInactive(apexCatalogGrid);assert.equal(native.pendingCell,false);assert.equal(begins,0);
ApexCatalogGridRetireInactive(apexCatalogGrid);assert.equal(native.lease,false);assert.equal(apexCatalogGrid.retiring,null);
assert.equal(ApexCatalogGridPrepare(),true);assert.equal(begins,1);assert.equal(apexCatalogGrid.grid,nextGrid);assert.equal(apexCatalogGrid.lease.phase,'bootstrap');
assert.equal(queries,0);assert.equal(native.committedVisible,true);
''')

    def test_reentrant_prepare_cannot_start_foreign_work_during_retirement(self):
        self.run_js(r'''
owned();list.visible=false;ApexCatalogGridFrame();assert.equal(ApexCatalogGridPrepare(),false);
assert.equal(begins,0);assert.equal(queries,0);assert.equal(apexCatalogGrid.retiring.grid,grid);
''')

    def test_foreign_display_tree_and_reparented_view_cannot_claim_active_native_scope(self):
        self.run_js(r'''
const stranger={visible:true,stage,parent:root};gridView.parent=stranger;assert.equal(ApexCatalogPanelVisible(panel),false);
gridView.parent=view;const old=panel.mcTileList;panel.mcTileList={...old,GetGridView(){return stranger;}};
assert.equal(ApexCatalogPanelVisible(panel),false);panel.mcTileList=old;
layer.parent=layer;assert.equal(ApexCatalogPanelVisible(panel),false);
''')

    def test_noncard_drawer_is_not_armed_and_does_not_globally_disable_visible_native_catalog(self):
        self.run_js(r'''
owned();const drawer={visible:true,stage,parent:root,mcTileList:{mGridLayout:{}}};
assert.equal(ApexCatalogGridProductPanel(drawer),'');assert.equal(ApexCatalogPanelVisible(panel),true);
ApexCatalogGridPrepare=()=>{prepares++;return false;};ApexCatalogGridFrame();assert.equal(prepares,1);assert.equal(cancels,0);
''')

if __name__ == '__main__':
    unittest.main(verbosity=2)
