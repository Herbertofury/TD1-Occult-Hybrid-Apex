"""The actual slider methods must not chase a catalog that resizes beneath them."""
from pathlib import Path
import re
import shutil
import subprocess
import unittest
import test_cas_panel_geometry as geometry


SOURCE = Path(__file__).resolve().parents[1] / 'Source/CASUi/catalog_columns_methods.as'


def javascript_function(name, parameters=''):
    source = SOURCE.read_text(encoding='utf-8')
    part = source.split('private function ' + name + '(', 1)[1]
    part = re.split(r'\n      private (?:function|var) ', part, maxsplit=1)[0]
    body = part.split('{', 1)[1].rsplit('}', 1)[0]
    body = re.sub(r'\b(var\s+\w+)\s*:\s*[\w.]+', r'\1', body)
    body = re.sub(r'\s+as\s+flash\.[\w.]+', '', body)
    body = re.sub(r'(\w+) is (flash\.[\w.]+|ClothingPanel)', r'\1 instanceof \2', body)
    return 'function ' + name + '(' + parameters + '){' + body + '}\n'


@unittest.skipUnless(shutil.which('node'), 'Node is required for the AS method harness')
class ColumnControlTests(unittest.TestCase):
    def harness(self):
        # Share the real native-panel/mask/viewport fixture with the six-panel
        # geometry tests; execute the complete current column helper family.
        setup = geometry.BASE + geometry.GeometryTests().common() + '''
stage.stageWidth=1278;stage.stageHeight=1376;mcClothingPanel.x=978;
mcClothingPanel.mcTileList.y=100;mcClothingPanel.mcTileList.height=600;
const root=new Sprite('ApexColumnsSlider'),track=new Sprite('dccThumbnailScaleTrack');
for(const name of ['thumb','caption','apexColumnsLayout'])root.addChild(new Sprite(name));
for(const name of ['dccThumbnailScaleThumb','apexThumbnailScaleCaption'])track.addChild(new Sprite(name));
mcClothingPanel.addChild(root);mcClothingPanel.addChild(track);
apexColumns={root,track,bounds:null,anchor:null,resize:null,tooltips:[],track_tip:null,drag:false,scale_drag:false,
    scale_stage:null,stage:null,persist:false,due:0},apexCatalogPrefs={columns:2},apexCardPrefs={scale:1},apexCardLayout={columns:2,scale:1};
var apexPanels={drag:null},apexPendingFields=null,apexReceiving=false;
function ApexCatalogPersist(){throw new Error('Persistence on an active input frame');}
function event(){return {target:root,currentTarget:root,stopImmediatePropagation(){},preventDefault(){}};}
'''
        for name, parameters in [('ApexColumnsTakeover', 'value=null'), ('ApexColumnsSave', ''),
                                 ('ApexColumnsSet', 'value=null'), ('ApexColumnsScale', 'value=null'),
                                 ('ApexColumnsScaleEnd', 'value=null'), ('ApexColumnsDown', 'event'),
                                 ('ApexColumnsMove', 'event'), ('ApexColumnsUp', 'event=null'),
                                 ('ApexColumnsResize', 'value=null'), ('ApexColumnsResizeEnd', 'value=null'),
                                 ('ApexColumnsTrack', 'panel'), ('ApexColumnsScaleDown', 'event'),
                                 ('ApexColumnsScaleMove', 'event'), ('ApexColumnsScaleUp', 'event'),
                                 ('ApexColumnsWidthDown', 'event'), ('ApexColumnsWidthMove', 'event'),
                                 ('ApexColumnsWidthUp', 'event=null'), ('ApexColumnsWidthHandle', 'panel'),
                                 ('ApexColumnsFrame', '')]:
            setup += javascript_function(name, parameters)
        return setup

    def run_case(self, case):
        result = subprocess.run(['node', '-'], input=self.harness() + case, capture_output=True,
                                text=True, encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_column_drag_keeps_track_and_value_stable_through_reflow(self):
        self.run_case('''
ApexColumnsFrame();const origin=root.localToGlobal(new Point(0,0)),scale=root.scaleX;
stage.mouseX=origin.x+80*scale;stage.mouseY=origin.y+26;
ApexColumnsDown(event());assert.equal(apexCatalogPrefs.columns,14);
mcClothingPanel.x=578;mcClothingPanel.mcPanelBackground.width=700;ApexColumnsFrame();
assert.deepEqual(root.localToGlobal(new Point(0,0)),origin);assert.equal(root.scaleX,scale);
for(let i=0;i<4;i++){ApexColumnsMove(event());ApexColumnsFrame();assert.equal(apexCatalogPrefs.columns,14);}
ApexColumnsUp();ApexColumnsFrame();assert.equal(apexColumns.anchor,null);
assert.equal(apexCatalogPrefs.columns,14);assert.notEqual(root.localToGlobal(new Point(0,0)).x,origin.x);
''')

    def test_thumbnail_drag_keeps_native_track_under_pointer_until_release(self):
        self.run_case('''
ApexColumnsFrame();const origin=track.localToGlobal(new Point(0,0)),scale=track.scaleX;
stage.mouseX=origin.x+160*scale;stage.mouseY=origin.y+14;
ApexColumnsScale();const size=apexCardPrefs.scale;assert.equal(size,1.23);
mcClothingPanel.x=578;mcClothingPanel.mcPanelBackground.width=700;ApexColumnsFrame();
assert.deepEqual(track.localToGlobal(new Point(0,0)),origin);assert.equal(track.scaleX,scale);
for(let i=0;i<4;i++){ApexColumnsScale();ApexColumnsFrame();assert.equal(apexCardPrefs.scale,size);}
ApexColumnsScaleEnd();ApexColumnsFrame();assert.equal(apexColumns.anchor,null);assert.equal(apexColumns.scale_drag,false);
assert.equal(apexCardPrefs.scale,size);assert.notEqual(track.localToGlobal(new Point(0,0)).x,origin.x);
''')

    def test_viewport_change_ends_drag_without_applying_a_new_pointer_value(self):
        self.run_case('''
ApexColumnsFrame();const origin=track.localToGlobal(new Point(0,0));
stage.mouseX=origin.x+120*track.scaleX;stage.mouseY=origin.y+14;ApexColumnsScale();const size=apexCardPrefs.scale;
stage.stageWidth=1440;stage.mouseX=0;ApexColumnsFrame();
assert.equal(apexColumns.scale_drag,false);assert.equal(apexColumns.drag,false);assert.equal(apexColumns.anchor,null);
assert.equal(apexCardPrefs.scale,size);
''')

    def test_complete_slider_ranges_and_native_width_handle_keep_count_and_size_independent(self):
        self.run_case('''
ApexColumnsFrame();const beforeCount=apexCatalogPrefs.columns,beforeSize=apexCardPrefs.scale;
// A plain object cannot invent a native mouse gesture.
ApexColumnsResize({stageX:300});assert.equal(apexColumns.resize,null);
const down=new MouseEvent(1100);ApexColumnsResize(down);assert.notEqual(apexColumns.resize,null);
assert.equal(apexCatalogPrefs.columns,beforeCount);assert.equal(apexCardPrefs.scale,beforeSize);
ApexColumnsResize(new MouseEvent(1170));assert.equal(apexCatalogPrefs.columns,beforeCount);assert.equal(apexCardPrefs.scale,beforeSize);
ApexColumnsResizeEnd(new Event(Event.DEACTIVATE));
assert.equal(apexColumns.resize,null);assert.equal(apexColumns.drag,false);assert.equal(apexCatalogPrefs.columns,beforeCount);
ApexColumnsSet(32);assert.equal(apexCatalogPrefs.columns,32);ApexColumnsSet(33);assert.equal(apexCatalogPrefs.columns,32);
ApexColumnsFrame();const at=track.localToGlobal(new Point(0,0));stage.mouseX=at.x+20*track.scaleX;ApexColumnsScale();
assert.equal(apexCardPrefs.scale,.2);stage.mouseX=at.x+210*track.scaleX;ApexColumnsScale();assert.equal(apexCardPrefs.scale,1.6);
''')

    def test_native_resize_retires_on_context_change_without_native_fallback(self):
        self.run_case('''
ApexColumnsFrame();ApexColumnsResize(new MouseEvent(1100));assert.notEqual(apexColumns.resize,null);
const count=apexCatalogPrefs.columns;mCurrentPanel=new Sprite('unknown');ApexColumnsFrame();
assert.equal(apexColumns.resize,null);assert.equal(apexColumns.drag,false);assert.equal(apexCatalogPrefs.columns,count);
assert.equal(mDynamicResizeHandle.alpha,.78);assert.equal(root.visible,false);assert.equal(track.visible,false);
''')


if __name__ == '__main__':
    unittest.main()
