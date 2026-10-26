"""Execute the leased geometry path and forbid a legacy whole-pool rebind."""
import unittest
from pathlib import Path
import test_cas_card_geometry as legacy
ROOT=legacy.ROOT
javascript_function=legacy.javascript_function

SOURCE = ROOT / 'Source/CASUi/catalog_grid_geometry_methods.as'


class IncrementalGeometryTests(unittest.TestCase):
    def execute(self, script):
        return legacy.CardGeometryTests.execute(self, script)

    def harness(self):
        code = legacy.CardGeometryTests.harness(self)
        code += javascript_function('ApexCardForget')
        code += javascript_function('ApexCardIncrementalApply', 'panel,grid', SOURCE)
        return code + '''
ApexCatalogGridOwns=()=>true;
var nativeStatus={measurement_ready:true,natural_width:111,natural_height:148,natural_aspect:1,columns:2};
var reads=0,positions=0;
grid.ApexGridStatus=()=>{reads++;return {...nativeStatus};};
grid.GetAllDisplayObjectCells=()=>{throw Error('Incremental Main enumerated the pool');};
grid.GetCellBounds=()=>{throw Error('Incremental Main constructed a native probe');};
grid.ResetAndPositionCells=()=>{throw Error('Incremental Main reset the pool');};
grid.PositionCells=()=>{positions++;}; // Native adapter coalesces these events.
grid.SetCellBounds=()=>{throw Error('Incremental Main sized every cell');};
grid.SetCellPadding=()=>{throw Error('Incremental Main changed the provider lease');};
Object.defineProperty(grid,'SuppressUpdates',{get(){throw Error('Main read the provider lease');},set(){throw Error('Main changed the provider lease');}});
'''

    def test_leased_apply_never_enumerates_binds_scales_or_releases_provider(self):
        self.execute(self.harness()+'''
const width=ApexCardApply(panel,grid);assert.equal(apexCardGeometry.incremental,true);
assert.equal(apexCardLayout.columns,12);assert.ok(width<=stage.stageWidth*.4-12+1e-7);assert.ok(apexCardLayout.scale<.6);
const writes=positions,changes=apexCatalogLayoutChanges;
for(let i=0;i<20;i++)ApexCardApply(panel,grid);
assert.equal(positions,writes);assert.equal(apexCatalogLayoutChanges,changes);
apexCatalogPrefs.columns=32;ApexCardApply(panel,grid);
assert.equal(apexCardLayout.columns,32);assert.equal(apexCardLayout.width,width);assert.ok(apexCardLayout.scale<.2);
ApexCardRestore();assert.equal(apexCardGeometry,null);assert.equal(positions,writes);
''')

    def test_measurement_wait_has_no_size_guess_and_invalid_values_do_not_commit(self):
        self.execute(self.harness()+'''
nativeStatus.measurement_ready=false;
assert.equal(ApexCardApply(panel,grid),262);assert.equal(apexCardGeometry,null);assert.equal(apexCardLayout,null);assert.equal(positions,0);
nativeStatus.measurement_ready=true;nativeStatus.natural_width=NaN;
assert.throws(()=>ApexCardApply(panel,grid),/measurement unavailable/);assert.equal(apexCardGeometry,null);assert.equal(positions,0);
''')

    def test_native_post_draw_height_is_bound_to_the_exact_effective_scale(self):
        self.execute(self.harness()+'''
ApexCardApply(panel,grid);const size=apexCardLayout.scale;
nativeStatus.measured_scale=size;nativeStatus.measured_height=71;
ApexCardApply(panel,grid);assert.equal(apexCardLayout.card_height,71);assert.equal(apexCardLayout.pitch_y,75);
nativeStatus.measured_scale=size/2;ApexCardApply(panel,grid);
assert.ok(Math.abs(apexCardLayout.card_height-148*size)<1e-8);
''')

    def test_geometry_failure_releases_only_main_reentry_and_is_not_a_native_reset(self):
        self.execute(self.harness()+'''
Object.defineProperty(list,'width',{get(){return this._width;},set(){throw Error('native control failed');}});
assert.throws(()=>ApexCardApply(panel,grid),/native control failed/);
assert.equal(apexCardGeometry.applying,false);assert.equal(apexCatalogSignature,'');
''')


if __name__ == '__main__': unittest.main()
