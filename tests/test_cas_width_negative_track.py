"""Actual V345 coordinates reproduce the controls-band refusal in source.

The native rectangle reader is replayed; actual corrected dragging remains a
separate runtime check. Unknown visible controls retain their exclusion.
"""
import json,sys,unittest,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests')]
import test_cas_panel_geometry as base
FIXTURE=ROOT/'tests/fixtures/catalog-width-v345-negative-track.json'
class ActualWidthBand(unittest.TestCase):
 def test_actual_negative_native_track_offset_and_foreign_controls(self):
  f=json.loads(FIXTURE.read_text(encoding='utf-8'));p=f['probe'];self.assertEqual(p['reason'],'native-protected-region-blocks-width');self.assertLess(p['controls_origin']['x'],p['origin']['x']);self.assertEqual(p['available'],0)
  source=base.BASE
  for n,a in [('ApexCatalogPanelKey','panel'),('ApexCatalogPanelKind','panel'),('ApexCatalogOptional','owner,name'),('ApexCatalogVisibleRect','display'),('ApexCatalogSafeRight','left,top,bottom,viewport,minimum,regions'),('ApexCatalogNavigationRects','probe=null'),('ApexCatalogWidthEnvelope','panel,probe=null')]:source+=base.js(n,a)
  source+='const recorded='+json.dumps(f)+';\n'+'''
const p=recorded.probe;stage.stageWidth=recorded.catalog_bounds.stage_width;stage.stageHeight=recorded.catalog_bounds.stage_height;
mCurrentPanel.x=p.origin.x;mCurrentPanel.y=p.origin.y;mCurrentPanel.scaleX=p.coordinate_scale;mCurrentPanel.scaleY=p.vertical.y-p.origin.y;
const list=mCurrentPanel.mcTileList;list.height=p.content.height;
list.x=(p.controls_origin.x-p.origin.x)/mCurrentPanel.scaleX;
list.y=(p.controls_origin.y-p.origin.y)/mCurrentPanel.scaleY-list.height-3;
mCurrentPanel.mcPanelBackground.width=recorded.card_width;
list.mSlider.getBounds=()=>p.scrollbar;
const mask=list.mScrollerView.mcMask;Object.assign(mask,{x:p.content.x,y:p.content.y,naturalWidth:p.content.width,naturalHeight:p.content.height});
// Replay the recorded native rectangle-reader output; widget contracts are
// independently exercised by the six existing actual-source tests.
ApexCatalogNavigationRects=()=>p.regions.filter(r=>r.kind==='native-navigation-button');
let probe={};let result=ApexCatalogWidthEnvelope(mCurrentPanel,probe);
assert.equal(probe.ok,true);assert.equal(probe.reason,'available');
assert.ok(Math.abs(probe.content_available-p.content_available)<.051);
assert.ok(Math.abs(result.available-p.content_available)<.051);
assert.ok(result.available>recorded.card_width+200);
assert.ok(probe.controls_available>800);
assert.equal(probe.controls_left_boundary,p.controls_origin.x);
const before={x:mCurrentPanel.x,y:mCurrentPanel.y,list_x:list.x,list_y:list.y};
const other=new Sprite('unknown-real-control');other.stage=stage;other.x=p.controls_origin.x-5;other.y=p.controls_origin.y+1;other.naturalWidth=40;other.naturalHeight=20;mcWingToggle=other;
probe={};result=ApexCatalogWidthEnvelope(mCurrentPanel,probe);assert.equal(result.available,0);assert.equal(probe.ok,false);
assert.equal(probe.reason,'native-protected-region-blocks-width');
assert.deepEqual(before,{x:mCurrentPanel.x,y:mCurrentPanel.y,list_x:list.x,list_y:list.y});
'''
  r=subprocess.run(['node'],input=source,text=True,encoding='utf-8',capture_output=True,timeout=15);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
if __name__=='__main__':unittest.main()
