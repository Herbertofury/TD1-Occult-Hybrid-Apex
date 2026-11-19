"""Execute original EA layout bodies as the completed-state observation oracle.

This proves active item/map/geometry/resource observation, not widget identity or
the count/order of hidden pooled display children. The native small-scroll body
does not emit RESIZE; its completed projection is compared to our RESIZE view.
"""
from pathlib import Path
from types import SimpleNamespace
import os,re,sys,unittest
H=Path(__file__).resolve().parents[1];R=next(p for p in (H,*H.parents) if(p/'tools/dbpf_build.py').is_file())
sys.path[:0]=[str(H/'tools'),str(H/'tests'),str(R/'tests'),str(R/'tools')]
import test_cas_grid_row_delta as delta
import test_cas_grid_presentation as fixture
import cas_grid_pool as pool

FIXTURE=Path(os.environ['APEX_CAS_ROW_DELTA_FIXTURE'])if os.environ.get('APEX_CAS_ROW_DELTA_FIXTURE')else None

def original_native():
    source=(FIXTURE/'12272E1AC0C1F8E2/native-source/scripts/olympus/layout/RecyclingGridLayout.as').read_text()
    names=('CycleCells','ExitCells','PositionCells','PositionCellsInternal','InitializeCellData','SetupCells')
    bodies=[]
    for name in names:
        text=source.replace('protected function','public function').replace('override public function','public function')
        a,b=pool.method_extent(text,name);bodies.append(text[a:b])
    source='\n'.join(bodies)
    for name in names:source=re.sub(r'\b'+name+r'\b','Ea'+name,source)
    source=re.sub(r'for each\((\w+) in ([^\n]+)\)',r'for(\1 of \2)',source)
    old=fixture.stage
    try:fixture.stage=SimpleNamespace(helpers=lambda:source);return fixture.javascript()
    finally:fixture.stage=old

BOOT='''
NativeGrid.prototype.CalculateCellViewHeight=function(){return this.apexGridState.job.plan.height;};
NativeGrid.prototype.CalculateCellViewWidth=function(){return this.apexGridState.job.plan.width;};
NativeGrid.prototype.DetermineCellCount=function(){return this.apexGridState.job.target;};
Rectangle.prototype.intersects=function(b){return b.x<this.x+this.width&&b.x+b.width>this.x&&b.y<this.y+this.height&&b.y+b.height>this.y;};
DisplayObject.prototype.getBounds=function(){return{x:this.x||0,y:this.y||0,width:38,height:51};};
function observation(g){const viewport=new Rectangle(0,0,1400,400);
 return{map:g.mCellIndexToDataIndexMap.slice(),cells:g.mCells.map(c=>({data:c.item.data_id,x:c.x,y:c.y,visible:c.visible,
  selected:c.ext.Selected,resource:c.mcImage.resourceId,ready:c.mcImage.ApexImageReadyFor('thumb:'+c.item.data_id)})),
 visible:g.mCells.filter(c=>c.visible&&viewport.intersects(c.getBounds(g.mGridView))).map(c=>c.item.data_id)};
}
const sevenNames=['CASClothingPanelCellViewMain','CASClothingPanelCellViewCommon','CASClothingPanelCellViewSkinSpecularity','CASBodyPanelCellView',
 'CASFacePanelCellView','CASGenericCatalogVariantCellView','CASBreedCatalogCellView'];
function family(name){const types={[name]:class extends Cell{}};return types[name];}
function familyReady(name){const g=new NativeGrid(1000,0);g.mCellType=family(name);return ready(g);}
'''

@unittest.skipUnless(FIXTURE is not None,'Set APEX_CAS_ROW_DELTA_FIXTURE for original native layout bodies')
class NativeReferenceTests(unittest.TestCase):
    def case(self,code):delta.DeltaTests.case(self,original_native()+BOOT+code)
    def test_completed_original_ea_one_row_scroll_projection_equals_delta_feedback_for_all_seven_admitted_families(self):
        self.case('''for(const name of sevenNames){const native=familyReady(name),g=familyReady(name);
const before=counters(g);native.EaCycleCells({mRect:{y:-55}});const expected=observation(native);let transcript=null;
g.hooks.resize=()=>{assert.equal(transcript,null,'one original feedback');transcript=observation(g);assert.equal(g.ApexGridPoolViews().length,54);};
g.ApexGridBegin(deltaRequest(g,55));assert.equal(steps(g).phase,'done');assert.deepEqual(transcript,expected,name);assert.deepEqual(observation(g),expected,name);
assert.equal(counters(g).draw-before.draw,6,name);assert.equal(native.calls.filter(c=>c==='resize').length,1,'native small-scroll itself emits no RESIZE');}''')
    def test_original_ea_completed_reflow_resize_observes_the_same_complete_ready_logical_state_before_callback(self):
        self.case('''for(const raw of[55,58.125,110]){const native=ready(new NativeGrid(1000,0)),g=ready(new NativeGrid(1000,0));
const first=Math.floor(raw/55)*6,origin=-(raw%55);native.mCellIndexToDataIndexMap[0]=first;native.mCellsY[0]=origin;native.mPrevRectangleUpdate.y=-raw;
let ea=null,ours=null;native.resize=()=>{ea=observation(native);};native.EaPositionCells();assert.ok(ea);
g.hooks.resize=()=>{ours=observation(g);};g.ApexGridBegin(deltaRequest(g,raw));assert.equal(steps(g).phase,'done');assert.deepEqual(ours,ea);assert.deepEqual(observation(g),ea);}''')

if __name__=='__main__':unittest.main()
