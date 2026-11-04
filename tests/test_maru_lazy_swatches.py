"""Execute the complete patched donor methods, not a reimplemented scheduler."""
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import maru_companion_performance as patch

DONOR = ROOT / '.work/research/maru-integrated/customizer/scripts'


def body(name):
    source = (DONOR / (name.replace('.', '/') + '.as')).read_text(encoding='utf-8')
    changed = patch.inject(name, source)
    # The only source edit is the early visibility guard. The entire retained
    # continuation is the actual donor's method, including its open-grid route.
    index = changed.index('public static function Decorate(')
    begin = changed.index('{', index)
    depth = 1
    end = begin + 1
    while depth:
        depth += (changed[end] == '{') - (changed[end] == '}')
        end += 1
    result = changed[begin + 1:end - 1]
    result = re.sub(r'\b(var\s+\w+)\s*:\s*[\w.]+', r'\1', result)
    result = re.sub(r'for each\(var (\w+) in ([\w.]+)\)', r'for(var \1 of \2)', result)
    return re.sub(r'\s+as\s+Array', '', result)


class PatchBoundaryTests(unittest.TestCase):
    def test_unknown_or_changed_boundary_is_refused(self):
        for name in patch.ROUTES:
            with self.assertRaises(ValueError):
                patch.inject(name, 'changed source')
        with self.assertRaises(ValueError):
            patch.inject('unreviewed.Class', '')


@unittest.skipUnless(DONOR.exists() and shutil.which('node'), 'Private donor and Node required')
class LiteralDonorLazySwatchTests(unittest.TestCase):
    def run_js(self, code):
        result = subprocess.run(['node', '-e', code], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_actual_favorite_lookup_keeps_false_legacy_and_extra_type_semantics(self):
        source = (DONOR / (patch.PREFERENCES.replace('.', '/') + '.as')).read_text(encoding='utf-8')
        changed = patch.preferences(source)
        before = source[source.index('      public static function Has('):source.index('      public static function Toggle(')]
        after = changed[changed.index('      public static function Has('):changed.index('      public static function Toggle(')]
        def js(text):
            value = text.split('{', 1)[1].rsplit('}', 1)[0]
            return re.sub(r'\b(var\s+\w+)\s*:\s*(?:\*|[\w.]+)', r'\1', value)
        self.run_js('''
const assert=require('node:assert/strict');var values={},reads=0;
var UISettings={get AccountSettings(){reads++;return {GetValue:k=>values[k]};}};
function Key(type,id){return type<0||!id||id==='0'||id.length>128||id.includes('#')?null:'dynamic_cas_columns.favorite.shared.'+id;}
function Before(param1,param2){''' + js(before) + '''}
function After(param1,param2){''' + js(after) + '''}
for(var type of [-1,0,1,13,14,999])for(var shared of [undefined,false,true])for(var legacy of [-1,0,13,14,999]){
 values={};if(shared!==undefined)values['dynamic_cas_columns.favorite.shared.42']=shared;
 if(legacy>=0)values['dynamic_cas_columns.favorite.'+legacy+'.42']=true;
 var expected=Before(type,'42');reads=0;assert.equal(After(type,'42'),expected);
 assert.ok(reads<=1);if(type>=0)assert.equal(reads,1);
}
for(var id of [null,'','0','bad#key','x'.repeat(129)]){reads=0;assert.equal(After(0,id),false);assert.equal(reads,0);}
values={};reads=0;Before(0,'42');assert.equal(reads,15);reads=0;After(0,'42');assert.equal(reads,1);
''')

    def test_actual_hair_method_defers_closed_but_preserves_hover_open_and_cache(self):
        self.run_js('''
const assert=require('node:assert/strict');
var queries=0,created=0,layouts=0,shown=0,selected=0,origin=null,panel=null;
var states=new Map(),feeds=new Map();
// AS Dictionary indexing semantics used by the literal method.
states={};feeds={};
var product={toString:()=> 'hair-A'},cell={current:true,btnVariationStackContainer:{visible:true,Selected:true,mcArrow:{alpha:1},
 VariationStack:{SetDataFeed:()=>{},ShowGrid:()=>shown++},RefreshLayout:()=>layouts++}};
states[product]=4;
var CurrentOutfitUI={IsCurrent:c=>c.current},CASSwatchType={NONE:0};
function Type(s){return s;}function int(x){return Math.trunc(x);}
var CommunicationManager={CallGameService:(name)=>{queries++;if(name==='CasGetSwatchColorList')return [{dataID:'1',color:2},{dataID:'2',color:3}];selected++;return '1';}};
function SelectableArrayDataFeed(){created++;this.length=0;this.AddItem=()=>this.length++;}
function ColorSwatchData(x){Object.assign(this,x);}
function Decorate(cell,product,over){''' + body(patch.ROUTES[0]) + '''}
for(var i=0;i<10000;i++)Decorate(cell,product,false);
assert.equal(queries,0);assert.equal(created,0);assert.equal(shown,0);assert.equal(cell.btnVariationStackContainer.visible,false);
assert.equal(cell.btnVariationStackContainer.mcArrow.alpha,0);
Decorate(cell,product,true);assert.equal(queries,2);assert.equal(created,1);assert.equal(shown,1);
assert.equal(cell.btnVariationStackContainer.visible,true);
Decorate(cell,product,true);assert.equal(queries,3);assert.equal(created,1);
origin=cell;panel={};Decorate(cell,product,false);assert.equal(queries,4);assert.equal(shown,3);
assert.equal(cell.btnVariationStackContainer.Selected, true);
origin=null;Decorate(cell,product,false);assert.equal(queries,4);assert.equal(cell.btnVariationStackContainer.visible,false);
cell.current=false;cell.btnVariationStackContainer.visible=true;Decorate(cell,product,false);
assert.equal(cell.btnVariationStackContainer.visible,true);assert.equal(queries,4);
''')

    def test_actual_nonhair_method_keeps_open_swatches_and_never_builds_hidden_grid(self):
        self.run_js('''
const assert=require('node:assert/strict');
var calls=0,shown=0,openBase=null,items={},button={visible:true,Selected:true,mcArrow:{alpha:1},
 VariationStack:{SetDataFeed:()=>{},ShowGrid:()=>shown++},RefreshLayout:()=>{}};
var p={toString:()=> 'lipstick',GetColorSwatchDataFeed:()=>{calls++;return {length:1000};},AllowsCreatingColorShiftVariations:()=>false};
items[p]={state:9,id:'42'};
var cell={current:true,btnVariationStackContainer:button},CurrentOutfitUI={IsCurrent:c=>c.current},MenuState={IsHair:()=>false};
function int(x){return Math.trunc(x);}function Base(){return openBase;}
function Decorate(cell,p,over){''' + body(patch.ROUTES[1]) + '''}
for(var i=0;i<10000;i++)Decorate(cell,p,false);
assert.equal(calls,0);assert.equal(shown,0);assert.equal(button.visible,false);
Decorate(cell,p,true);assert.equal(calls,1);assert.equal(shown,1);assert.equal(button.visible,true);
openBase=p;Decorate(cell,p,false);assert.equal(calls,2);assert.equal(shown,2);assert.equal(button.Selected,true);
assert.equal(button.mcArrow.alpha,1);
openBase=null;Decorate(cell,p,false);assert.equal(calls,2);assert.equal(button.visible,false);
cell.current=false;button.visible=true;Decorate(cell,p,false);assert.equal(button.visible,true);
''')


if __name__ == '__main__':
    unittest.main()
