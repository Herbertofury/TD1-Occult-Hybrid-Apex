from pathlib import Path
import json
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tests'), str(ROOT / 'tools')]

import cas_catalog_schedule as schedule
import test_cas_card_geometry as card
SCHEDULE = schedule.ROOT


from types import SimpleNamespace
import re
def scheduling_function(name,parameters=''):
    # Execute the exact fragment through the existing public AS converter. Only
    # declaration indentation is normalized for that converter's delimiter.
    text=re.sub(r'(?m)^private function ', '      private function ', schedule.stage.fragment())
    return card.javascript_function(name,parameters,SimpleNamespace(read_text=lambda **kwargs:text))

class NativeControlFeedbackTests(unittest.TestCase):
    def run_js(self, extra, patched=True):
        script = card.CardGeometryTests().harness()
        script = script.replace('function ApexCatalogGridOwns(grid){return false;}', 'var ownedRoute=false;function ApexCatalogGridOwns(grid){return ownedRoute;}')
        if patched:
            script += 'var apexCatalogGrid=null;\n'
            script += scheduling_function('ApexCardRepairControls', 'panel,width,reflow')
            script += scheduling_function('ApexCardApply', 'panel,grid')
        script += card.javascript_function('ApexCardIncrementalApply', 'panel,grid', ROOT / 'Source/CASUi/catalog_grid_geometry_methods.as')
        script += r'''
let wanted=537.3531192772556,resetCalls=0,panelWrites=0,proxyEvents=0;
const q=value=>Math.round(value*20)/20;
function pixel(owner,key,value){let actual=q(value);Object.defineProperty(owner,key,{configurable:true,get(){return actual;},set(value){actual=q(value);}});}
pixel(panel.mcPanelBackground,'width',262);pixel(panel.mcFilterPane.mcFilterBubble.mcBackground,'width',232);
pixel(panel.txtTitle,'x',110);pixel(panel.btnRandomize,'x',220);pixel(slider,'x',251);
let proxyWidth=232;Object.defineProperty(gridView,'width',{configurable:true,get(){return proxyWidth;},set(value){if(value!==proxyWidth){proxyEvents++;proxyWidth=value;}}});
Object.defineProperty(list,'width',{configurable:true,get(){return this._width;},set(value){
 this._width=q(value);widthUpdates++;view.x=18;view.width=this.width-30;mask.width=this.width-30;
 gridView.width=this.width-30;slider.x=this.width-6-slider.width*.5;
}});
Object.defineProperty(panel,'width',{configurable:true,set(value){panelWrites++;this.mcPanelBackground.width=value;list.width=value;}});
grid.ResetAndPositionCells=function(){resetCalls++;this.PositionCells();};
function ApexCatalogWidthRequest(){return wanted;}
stage.stageWidth=2560;stage.logicalWidth=2560;apexCardPrefs.scale=.35;
grid.ApexGridStatus=()=>({measurement_ready:true,natural_width:107.0558278546344,natural_height:147,natural_aspect:1,
 columns:12,measured_scale:.34978098832649,measured_height:51.417805283994});
function frame(){apexCatalogFrameCells=null;return ApexCardApply(panel,grid);}
'''
        result = subprocess.run(['node'], input=script + extra, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_original_legacy_constant_request_repeats_reset_despite_unchanged_layout_signature(self):
        self.run_js(r'''
frame();const changes=apexCatalogLayoutChanges,initial=resetCalls,initialWidths=widthUpdates;
for(let i=0;i<500;i++)frame();
assert.equal(apexCatalogLayoutChanges,changes);assert.equal(resetCalls-initial,500);assert.ok(widthUpdates-initialWidths>=1000);
''', patched=False)

    def test_original_owned_route_repeats_width_setters_but_never_enters_legacy_reset(self):
        self.run_js(r'''
ownedRoute=true;frame();const initial=widthUpdates;
for(let i=0;i<500;i++)frame();assert.equal(resetCalls,0);assert.ok(widthUpdates-initial>=1000);
''', patched=False)

    def test_both_routes_settle_exact_native_readback_without_rewriting_user_request(self):
        self.run_js(r'''
for(const route of[false,true]){ownedRoute=route;apexCardGeometry=null;apexCardLayout=null;apexCatalogSignature='';
 frame();frame();const widthCount=widthUpdates,resets=resetCalls,changes=apexCatalogLayoutChanges;
 for(let i=0;i<500;i++)frame();
 assert.equal(widthUpdates,widthCount);assert.equal(resetCalls,resets);assert.equal(apexCatalogLayoutChanges,changes);
 assert.equal(apexCardLayout.width,wanted);assert.equal(apexCardGeometry.controls_width_receipt.request,wanted);
 assert.equal(list.width,537.35);assert.equal(panel.mcPanelBackground.width,537.35);
}
''')

    def test_external_sub_twip_proxy_drift_and_replaced_native_view_are_repaired(self):
        self.run_js(r'''
ownedRoute=true;frame();const before=widthUpdates;view.width+=.001;frame();assert.ok(widthUpdates>before);assert.equal(view.width,list.width-30);
const saved=widthUpdates;gridView={width:123};frame();assert.ok(widthUpdates>saved);assert.equal(gridView.width,list.width-30);
const stable=widthUpdates;for(let i=0;i<100;i++)frame();assert.equal(widthUpdates,stable);
''')

    def test_sub_twip_request_change_is_not_merged_and_reflow_still_runs(self):
        self.run_js(r'''
ownedRoute=true;frame();const before=widthUpdates;wanted+=.001;frame();assert.ok(widthUpdates>before);
assert.equal(apexCardLayout.width,wanted);assert.equal(apexCardGeometry.controls_width_receipt.request,wanted);
const widths=widthUpdates,ranges=rangeUpdates;ApexCardRepairControls(panel,wanted,true);
assert.equal(widthUpdates,widths);assert.equal(rangeUpdates,ranges+1);
''')

    def test_refused_native_geometry_is_not_adopted_as_an_acknowledged_target(self):
        self.run_js(r'''
ownedRoute=true;Object.defineProperty(panel.mcPanelBackground,'width',{configurable:true,get(){return 999;},set(){}});
frame();assert.equal(apexCardGeometry.controls_width_receipt,null);const before=widthUpdates;
frame();assert.ok(widthUpdates>before);assert.equal(apexCardGeometry.controls_width_receipt,null);
''')

    def test_coherent_nearby_refusal_cannot_gain_a_receipt_from_the_old_tolerance(self):
        self.run_js(r'''
ownedRoute=true;wanted=537.36;const wrong=537.4;
Object.defineProperty(panel.mcPanelBackground,'width',{configurable:true,get(){return wrong;},set(){}});
Object.defineProperty(list,'width',{configurable:true,get(){return wrong;},set(){
 widthUpdates++;view.x=18;view.width=wrong-30;mask.width=wrong-30;
 gridView.width=wrong-30;slider.x=wrong-6-slider.width*.5;
}});
frame();assert.equal(apexCardGeometry.controls_width_receipt,null);const before=widthUpdates;
frame();assert.ok(widthUpdates>before);assert.equal(apexCardGeometry.controls_width_receipt,null);
assert.equal(wanted,537.36);
''')

    def test_nonmatching_truncation_model_keeps_normal_repair_instead_of_being_blessed(self):
        self.run_js(r'''
ownedRoute=true;wanted=537.38;const truncated=537.35;
Object.defineProperty(panel.mcPanelBackground,'width',{configurable:true,get(){return truncated;},set(){}});
Object.defineProperty(list,'width',{configurable:true,get(){return truncated;},set(){
 widthUpdates++;view.x=18;view.width=truncated-30;mask.width=truncated-30;
 gridView.width=truncated-30;slider.x=q(truncated-6-slider.width*.5);
}});
frame();assert.equal(apexCardGeometry.controls_width_receipt,null);const before=widthUpdates;
frame();assert.ok(widthUpdates>before);assert.equal(apexCardGeometry.controls_width_receipt,null);
assert.equal(wanted,537.38);
''')

if __name__ == '__main__':
    unittest.main(verbosity=2)
