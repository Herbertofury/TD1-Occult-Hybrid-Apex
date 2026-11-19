"""Execute Main's actual explicit image-probe route without GFx or compilers."""
from pathlib import Path
import re
import shutil
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import cas_image_boundary_profile as image
import test_cas_communication_index as translate
import test_cas_layout_trace as layout


def actual_native_image_helpers():
    """Use the retained helper source, not an invented Enable/Stats response."""
    source = image.LOADER_HELPERS.replace(' final ', ' ').replace(
        'function get ApexImageTraceActive', 'function ApexImageTraceActive').replace(
        '__PROVIDER__', '62ECC59A:00000000:12272E1AC0C1F8E2')
    code = '''
let apexImageTraceState=null,apexImageTraceAccepting=false,apexImageTraceFault=false,apexImageTraceRequested=0;
function getTimer(){return flash.utils.getTimer();}function uint(n){return n>>>0;}
class Loader{
'''
    for name, (params, body) in translate.functions(source).items():
        text = translate.method(name, params, body)
        code += ('get ' + text if name == 'ApexImageTraceActive' else text)
    code += '}\nclass Resource{constructor(loader){this.mLoader=loader;}\n'
    for name, (params, body) in translate.functions(image.RESOURCE_HELPERS.replace(' final ', ' ')).items():
        code += translate.method(name, params, body)
    return code + '''}
let apiCalls=[];
function actualImage(){const loader=new Loader(),resource=new Resource(loader);
 for(const name of ['ApexImageTraceEnable','ApexImageTraceStats']){const original=resource[name];
  resource[name]=function(...args){assert.equal(this,resource);apiCalls.push([name,...args]);return original.apply(this,args);};}
 return {loader,resource};}
function primitiveTree(value){if(value===null)return;
 if(typeof value!=='object'){assert.ok(['string','number','boolean'].includes(typeof value));return;}
 assert.ok(Array.isArray(value)||Object.getPrototypeOf(value)===Object.prototype);
 for(const child of Object.values(value))primitiveTree(child);}
'''


@unittest.skipUnless(shutil.which('node'), 'Node required for actual AS source execution')
class MainImageBoundaryProbeTests(unittest.TestCase):
    def run_body(self, checks):
        layout.LayoutTraceExecutionTests.run_body(self, actual_native_image_helpers() + checks)

    def test_default_null_and_disabled_status_dispose_do_no_pool_native_or_clock_work(self):
        self.run_body(r'''
const actual=actualImage();catalogCells([{mcImage:actual.resource}]);
for(let n=0;n<100;n++){const status=ApexLayoutTraceStatus();assert.equal(status.image_boundaries.reason,'not-requested');ApexLayoutTraceDispose();}
ApexLayoutTraceConfigure(0);ApexLayoutReset(grid);
assert.equal(poolReads,0);assert.equal(clockCalls,0);assert.deepEqual(apiCalls,[]);assert.equal(original,1);
assert.equal(apexImageTraceState,null);assert.equal(apexImageTraceAccepting,false);
''')

    def test_explicit_control_routes_to_real_resource_loader_and_retains_only_primitive_stats(self):
        self.run_body(r'''
const actual=actualImage(),cells=[null,{mcImage:null},{mcImage:actual.resource}];catalogCells(cells);
let status=ApexLayoutTraceConfigure(30000);
assert.deepEqual(apiCalls,[['ApexImageTraceEnable',4096],['ApexImageTraceStats']]);assert.equal(poolReads,2);
assert.equal(apexImageTraceRequested,4096);assert.equal(actual.loader.ApexImageTraceActive,true);
assert.equal(status.image_boundaries.provider_resource_tgi,'62ECC59A:00000000:12272E1AC0C1F8E2');
actual.loader.ApexImageTraceStamp(0,true);now=4;actual.loader.ApexImageTraceStamp(0,false);
status=ApexLayoutTraceStatus();assert.equal(status.image_boundaries.completed,1);
assert.equal(status.image_boundaries.phases[0].total_ms,4);assert.equal(apiCalls.length,3);
primitiveTree(status);primitiveTree(apexLayoutTrace);
assert.equal(status.appearance_written,false);assert.equal(status.image_boundaries.appearance_written,false);
const stopped=ApexLayoutTraceConfigure(0);assert.equal(stopped.enabled,false);assert.equal(stopped.requested_ms,0);
assert.deepEqual(apiCalls.at(-1),['ApexImageTraceEnable',0]);assert.equal(actual.loader.ApexImageTraceActive,false);
const reads=poolReads,clocks=clockCalls,calls=apiCalls.length;
for(let i=0;i<100;i++)ApexLayoutTraceStatus();ApexLayoutTraceDispose();
assert.equal(poolReads,reads);assert.equal(clockCalls,clocks);assert.equal(apiCalls.length,calls);
assert.equal(stopped.image_boundaries.completed,1);primitiveTree(stopped);
''')

    def test_probe_is_bounded_to_eight_actual_cells_and_never_uses_ninth_or_cached_image(self):
        self.run_body(r'''
const actual=actualImage();let indexes=[];
const cells=new Proxy(Array.from({length:9},(_,index)=>index===8?{mcImage:actual.resource}:null),{
 get(target,key,receiver){if(/^\d+$/.test(String(key)))indexes.push(Number(key));return Reflect.get(target,key,receiver);}});
catalogCells(cells);const unavailable=ApexImageBoundaryProbe(4096);
assert.equal(unavailable.reason,'actual-image-probe-unavailable');assert.deepEqual(indexes,[0,1,2,3,4,5,6,7]);
assert.deepEqual(apiCalls,[]);assert.equal(clockCalls,0);assert.equal(poolReads,1);
cells[7]={mcImage:actual.resource};indexes=[];assert.equal(ApexImageBoundaryProbe(4096).available,true);
assert.deepEqual(indexes,[0,1,2,3,4,5,6,7]);assert.deepEqual(apiCalls,[['ApexImageTraceEnable',4096]]);
catalogCells([]);assert.equal(ApexImageBoundaryProbe().available,false);assert.equal(apiCalls.length,1);
''')

    def test_unavailable_or_refused_probe_never_retries_or_calls_unqualified_methods(self):
        self.run_body(r'''
for(const panel of [null,{}, {mcTileList:{}},{mcTileList:{mGridLayout:null}}]){
 mcClothingPanel=panel;assert.equal(ApexImageBoundaryProbe(4096).reason,'catalog-unavailable');}
assert.equal(poolReads,0);assert.equal(clockCalls,0);
let badCalls=0;catalogCells([{mcImage:{ApexImageTraceEnable:12,ApexImageTraceStats(){badCalls++;}}},
 {mcImage:{ApexImageTraceEnable(){badCalls++;}}}]);
assert.equal(ApexImageBoundaryProbe(4096).reason,'actual-image-probe-unavailable');assert.equal(badCalls,0);
mcClothingPanel.mcTileList.mGridLayout.GetAllDisplayObjectCells=()=>{poolReads++;throw Error('pool refused');};
let status=ApexLayoutTraceConfigure(30000);assert.equal(status.image_boundaries.reason,'actual-image-probe-refused');
assert.equal(status.image_boundaries.message,'pool refused');assert.equal(apexLayoutTrace.image_enabled,false);
const before=poolReads;ApexLayoutTraceStatus();ApexLayoutTraceDispose();assert.equal(poolReads,before);
catalogCells([{mcImage:{ApexImageTraceEnable(){badCalls++;throw Error('provider refused');},ApexImageTraceStats(){badCalls++;}}}]);
const refused=ApexImageBoundaryProbe(4096);assert.equal(refused.reason,'actual-image-probe-refused');assert.equal(badCalls,1);
primitiveTree(refused);assert.equal(refused.appearance_written,false);
''')

    def test_status_and_native_reset_expiry_disable_image_before_any_further_layout_work(self):
        self.run_body(r'''
const actual=actualImage();catalogCells([{mcImage:actual.resource}]);ApexLayoutTraceConfigure(1);
now=2;const status=ApexLayoutTraceStatus();assert.equal(status.expired,true);assert.equal(status.enabled,false);
assert.equal(actual.loader.ApexImageTraceActive,false);assert.deepEqual(apiCalls.at(-1),['ApexImageTraceEnable',0]);
const stoppedCalls=apiCalls.length,stoppedReads=poolReads,stoppedClocks=clockCalls;ApexLayoutTraceStatus();ApexLayoutTraceDispose();
assert.equal(apiCalls.length,stoppedCalls);assert.equal(poolReads,stoppedReads);assert.equal(clockCalls,stoppedClocks);
now=3;ApexLayoutTraceConfigure(1);now=5;
grid.ResetAndPositionCells=function(){assert.equal(actual.loader.ApexImageTraceActive,false);original++;};
ApexLayoutReset(grid);assert.equal(original,1);assert.equal(profile,0);assert.equal(apexLayoutTrace.expired,true);
''')

    def test_native_exception_disables_actual_image_and_preserves_the_original_single_throw(self):
        self.run_body(r'''
const actual=actualImage();catalogCells([{mcImage:actual.resource}]);ApexLayoutTraceConfigure(30000);
const error=Error('native failed once');grid.ApexProfileResetAndPositionCells=function(){profile++;throw error;};
assert.throws(()=>ApexLayoutReset(grid),value=>value===error);assert.equal(profile,1);assert.equal(original,0);
assert.equal(apexLayoutTrace.errors,1);assert.equal(apexLayoutTrace.enabled,false);
assert.equal(actual.loader.ApexImageTraceActive,false);assert.deepEqual(apiCalls.at(-1),['ApexImageTraceEnable',0]);
''')

    def test_actual_catalog_dispose_disables_image_before_grid_teardown(self):
        source = (ROOT / 'Source/CASUi/catalog_workspace_methods.as').read_text()
        part = source.split('private function ApexCatalogDispose(', 1)[1]
        body = part.split('{', 1)[1].split('\n      private ', 1)[0].rsplit('}', 1)[0]
        self.run_body(r'''
var stage=null,apexCatalogRegistered=false,apexCatalogRefreshRegistered=false,apexCatalogBindingRegistered=false,apexCatalogUi=null;
function ApexPanelsDispose(){}function ApexColumnsDispose(){}function ApexEquippedDispose(){}function ApexCatalogKeyboardDispose(){}
function ApexCompanionDispose(){}function ApexSearchDispose(){}function removeEventListener(){}function ApexCatalogFrame(){}
function ApexCatalogClearEffects(){}function ApexCardForget(){}
flash.events={Event:{ENTER_FRAME:'frame'}};
const actual=actualImage();catalogCells([{mcImage:actual.resource}]);ApexLayoutTraceConfigure(30000);let teardown=0;
function ApexCatalogGridDispose(){assert.equal(actual.loader.ApexImageTraceActive,false);assert.deepEqual(apiCalls.at(-1),['ApexImageTraceEnable',0]);mcClothingPanel=null;teardown++;}
function ApexCatalogDispose(preserveGridBootstrap=false){
''' + body + r'''
}
ApexCatalogDispose();assert.equal(teardown,1);assert.equal(apexLayoutTrace.enabled,false);primitiveTree(ApexLayoutTraceStatus());
''')

    def test_actual_workspace_button_input_mode_preserves_nullable_boolean_and_omits_native_objects(self):
        source = (ROOT / 'Source/CASUi/catalog_workspace_methods.as').read_text()
        body = source.split('var buttonCommunicationIndex:Object=', 1)[1].split('var layout:Object=', 1)[0]
        body = 'var buttonCommunicationIndex=' + body
        body = re.sub(r'\b(var\s+\w+)\s*:\s*[\w.]+', r'\1', body)
        body = re.sub(r'([\w.]+(?:\["[^"]+"\])?) is Function', r'(typeof \1==="function")', body)
        body = body.replace('(localCommunication.using_mouse_keyboard is Boolean)', '(typeof localCommunication.using_mouse_keyboard==="boolean")')
        body = body.replace('catch(unavailableButtonIndex:Error)', 'catch(unavailableButtonIndex)')
        self.run_body('function buttonStatus(){' + body + 'return buttonCommunicationIndex;}\n' + r'''
for(const value of [true,false,null,undefined,0,1,'true']){
 const source={button_provider:'actual-provider',listener_membership:{count:1},using_mouse_keyboard:value,opaque:{}};
 catalogCells([{ApexCommButtonIndexStats(){return source;}}]);const status=buttonStatus();
 assert.equal(status.using_mouse_keyboard,typeof value==='boolean'?value:null);
 assert.equal('opaque' in status,false);assert.equal(status.appearance_written,false);primitiveTree(status);
}
''')


if __name__ == '__main__':
    unittest.main()
