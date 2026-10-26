"""Run current width helpers against the recorded EA widget contract.

All coordinates below are adverse synthetic fixtures. Actual V345 width dragging
and native hit rectangles require separate game qualification.
"""
import json
from pathlib import Path
import re
import shutil
import subprocess
import unittest

import test_cas_panel_geometry as fixture

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / 'tests/fixtures/native_cas_width_contract.json').read_text(encoding='utf-8'))


@unittest.skipUnless(shutil.which('node'), 'Node required')
class NativeWidthBoundsTests(unittest.TestCase):
    def run_js(self, body):
        source = fixture.BASE
        for name, args in [
            ('ApexCatalogPanelKey', 'panel'), ('ApexCatalogPanelKind', 'panel'),
            ('ApexCatalogOptional', 'owner,name'), ('ApexCatalogVisibleRect', 'display'),
            ('ApexCatalogSafeRight', 'left,top,bottom,viewport,minimum,regions'),
            ('ApexCatalogNavigationRects', 'probe=null'),
            ('ApexCatalogWidthEnvelope', 'panel,probe=null'),
        ]:
            source += fixture.js(name, args)
        result = subprocess.run(['node'], input=source + body, capture_output=True,
                                text=True, encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_native_button_uses_configured_hit_area_and_conservative_fallback(self):
        # EA's GetBoundsOverride is a separate interface, not an override of
        # Flash getBounds. Its ConfigUI deliberately hides the real hit Sprite.
        self.assertFalse(CONTRACT['button']['overrides_flash_get_bounds'])
        self.assertEqual(CONTRACT['button']['bounds_override'], 'GetBoundsOverride')
        self.assertIn('hitArea = this.mcHitArea;', CONTRACT['component']['config_ui_statements'])
        helper = fixture.js('ApexCatalogVisibleRect', 'display')
        self.assertIn('display instanceof flash.display.Sprite', helper)
        self.assertIn('display.hitArea', helper)
        self.assertNotIn('GetBoundsOverride(', helper)
        self.run_js('''
const button=new Sprite('nativeButton');button.stage=stage;button.x=950;button.y=300;
button.naturalWidth=1800;button.naturalHeight=1200;
const hit=new Sprite('nativeHit');hit.stage=stage;hit.x=1700;hit.y=1100;hit.naturalWidth=50;hit.naturalHeight=40;hit.visible=false;
button.hitArea=hit;
const rect=ApexCatalogVisibleRect(button);
assert.equal(rect.x,1700);assert.equal(rect.y,1100);assert.equal(rect.width,50);assert.equal(rect.height,40);
assert.equal(rect.bounds_source,'native-sprite-hit-area');
button.hitArea=null;const fallback=ApexCatalogVisibleRect(button);
assert.equal(fallback.bounds_source,'conservative-artwork');assert.equal(fallback.x,950);assert.equal(fallback.width,1800);
''')

    def test_navigation_reads_only_recorded_native_root_fields_and_fences_identity(self):
        navigation = fixture.js('ApexCatalogNavigationRects', 'probe=null')
        native_fields = set(CONTRACT['navigation']['public_fields'])
        direct = set(re.findall(r'navigation\.(\w+)', navigation)) - {'stage', 'WidgetName'}
        optional = set(re.findall(r'ApexCatalogOptional\(navigation,"(\w+)"\)', navigation))
        self.assertTrue((direct | optional) <= native_fields, (direct | optional) - native_fields)
        self.assertEqual(CONTRACT['navigation']['widget_name'], 'CASNavigation')
        self.assertEqual(CONTRACT['layout_api']['lookup_delegate'],
                         'return mLayoutMgr.GetLoadedWidgetByName(param1);')
        self.run_js('''
const probe={};const native=ApexCatalogNavigationRects(probe);
assert.ok(Array.isArray(native));assert.equal(probe.navigation_widget_name,'CASNavigation');
assert.equal(probe.navigation_same_stage,true);
navigation.WidgetName='unknown-widget';assert.equal(ApexCatalogNavigationRects({}),null);
navigation.WidgetName='CASNavigation';navigation.stage={};assert.equal(ApexCatalogNavigationRects({}),null);
navigation.stage=stage;delete navigation.btnCancel;assert.equal(ApexCatalogNavigationRects({}),null);
''')

    def test_explicit_probe_names_early_refusals_and_contains_only_bounded_primitives(self):
        self.run_js('''
let probe={};LayoutAPI.mLayoutMgr=null;assert.equal(ApexCatalogWidthEnvelope(mCurrentPanel,probe),null);
assert.equal(probe.reason,'native-navigation-unavailable');assert.equal(probe.navigation.reason,'layout-manager-unavailable');
LayoutAPI.mLayoutMgr={};const mask=mCurrentPanel.mcTileList.mScrollerView.mcMask;
mask.stage={};probe={};assert.equal(ApexCatalogWidthEnvelope(mCurrentPanel,probe),null);
assert.equal(probe.reason,'native-scroll-mask-unavailable');assert.equal(probe.mask_same_stage,false);
mask.stage=stage;probe={};const envelope=ApexCatalogWidthEnvelope(mCurrentPanel,probe);
assert.ok(envelope.available>=80);assert.equal(probe.reason,'available');assert.equal(probe.ok,true);
assert.ok(probe.regions.length>=3&&probe.regions.length<=64);
const fields=['bounds_source','height','kind','width','x','y'].sort();
for(const rect of probe.regions){assert.deepEqual(Object.keys(rect).sort(),fields);
 for(const key of ['x','y','width','height'])assert.ok(Number.isFinite(rect[key]));}
assert.doesNotThrow(()=>JSON.stringify(probe));
''')

    def test_native_hit_rect_releases_inflated_artwork_but_unknown_controls_block(self):
        self.run_js('''
const button=new Sprite('nativePlay');button.stage=stage;button.x=950;button.y=300;button.naturalWidth=1800;button.naturalHeight=1200;
navigation.btnPlay=button;
let probe={};assert.equal(ApexCatalogWidthEnvelope(mCurrentPanel,probe).available,0);
assert.equal(probe.reason,'native-protected-region-blocks-width');
const hit=new Sprite('nativePlayHit');hit.stage=stage;hit.x=1700;hit.y=1100;hit.naturalWidth=50;hit.naturalHeight=40;hit.visible=false;button.hitArea=hit;
probe={};const safe=ApexCatalogWidthEnvelope(mCurrentPanel,probe);assert.ok(safe.available>500);
assert.ok(probe.regions.some(r=>r.kind==='native-navigation-button'&&r.bounds_source==='native-sprite-hit-area'));
mcWingToggle=new Sprite('unknownVisibleControl');mcWingToggle.stage=stage;mcWingToggle.x=890;mcWingToggle.y=400;
probe={};assert.equal(ApexCatalogWidthEnvelope(mCurrentPanel,probe).available,0);
assert.equal(probe.reason,'native-protected-region-blocks-width');
''')

    def test_visible_foreign_hit_area_refuses_and_hidden_widgets_are_not_obstacles(self):
        self.run_js('''
const button=new Sprite();button.stage=stage;const hit=new Sprite();hit.stage={};button.hitArea=hit;
assert.throws(()=>ApexCatalogVisibleRect(button),/detached/);
button.visible=false;assert.equal(ApexCatalogVisibleRect(button),null);
button.visible=true;button.parent=new Sprite();button.parent.visible=false;
assert.equal(ApexCatalogVisibleRect(button),null);
''')

    def test_bounds_diagnostic_executes_only_on_explicit_readback(self):
        geometry = (fixture.AS / 'catalog_panel_geometry_methods.as').read_text(encoding='utf-8')
        for forbidden in ('CallGameService', 'SendUIMessage', 'RequestData', 'PostServerCommand'):
            self.assertNotIn(forbidden, geometry)
        status = fixture.js('ApexCatalogStatus', '', 'catalog_workspace_methods.as')
        self.assertEqual(status.count('ApexCatalogWidthEnvelope('), 1)
        self.assertIn('width_diagnostics:widthProbe', status)
        self.assertIn('apexPendingFields[2]=="catalog-state" || apexPendingFields[2]=="catalog-width-drag"', status)
        # Execute the unmodified actual diagnostic block, not a proposed patch.
        start = status.index('var widthProbe=null;')
        end = status.index('return {preferences:', start)
        block = status[start:end]
        self.run_js('''
let boundsCalls=0;const originalBounds=ApexCatalogWidthEnvelope;
ApexCatalogWidthEnvelope=function(panel,probe){boundsCalls++;return originalBounds(panel,probe);};
var apexPendingFields=null;
function diagnostic(fields){apexPendingFields=fields;
''' + block + '''
return widthProbe;}
for(const fields of [null,[],['','','catalog-input'],['','','catalog-slider'],['','','metadata']]){
 assert.equal(diagnostic(fields),null);assert.equal(boundsCalls,0);}
for(const operation of ['catalog-state','catalog-width-drag']){
 const result=diagnostic(['','',operation]);assert.equal(result.protocol,1);
 assert.equal(result.scope,'native-catalog-width-bounds');assert.equal(result.appearance_written,false);assert.equal(result.ok,true);}
assert.equal(boundsCalls,2);
ApexCatalogWidthEnvelope=function(){throw Error('native-failure');};
const refused=diagnostic(['','','catalog-state']);assert.equal(refused.ok,false);
assert.equal(refused.reason,'native-bounds-error');assert.equal(refused.error,'native-failure');
''')


if __name__ == '__main__':
    unittest.main()
