"""Execute actual donor width/reflow excerpts and current owned swatch methods."""
from pathlib import Path
import json,re,subprocess,unittest
ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/'Source/CASUi/swatch_columns_methods.as').read_text()
FIXTURE=json.loads((ROOT/'tests/fixtures/cas_skin_custom_width_native.json').read_text())
DONOR='\n'.join(FIXTURE['native_methods'].values())
RECEIPT=FIXTURE['workspace']

def method(source,name):
 m=re.search(r'(?:private|public|protected) function '+name+r'\(([^\n]*)\)\s*:\s*[\w.]+\s*\{',source);start=m.end();at=start;depth=1
 while depth:depth+=(source[at]=='{')-(source[at]=='}');at+=1
 body=source[start:at-1];body=re.sub(r'\b(var\s+\w+)\s*:\s*[\w.*]+',r'\1',body);params=re.sub(r':\s*[\w.]+','',m[1])
 return params,body

def setup(patched=True):
 result='''const assert=require('node:assert/strict');function int(x){return x|0;}
class Rectangle{constructor(x,y,width,height){Object.assign(this,{x,y,width,height});}}
class Margin{constructor(top,right,bottom,left){this.Horizontal=left+right;this.Vertical=top+bottom;}}
const flash={geom:{Rectangle}},olympus={core:{widget:{Margin}}};
const CASSwatchType={SKINTONE:2},CASTunables={SWATCH_PANEL_BACKGROUND_PADDING:6,SWATCH_PANEL_SCROLLING_LIST_MARGINS:{Vertical:0}};
function makePanel(count=9){const first=count?{width:22,scaleX:1,height:22,scaleY:1}:null;
 const feed={length:count,selection:new Set([2])};let positions=0;
 const grid={columns:9,Horizontal:true,FirstCell:first,bounds:{width:22,height:22},padding:{Horizontal:0,Vertical:0},
 GetGridDimensions(){return [this.columns,Math.ceil(feed.length/this.columns)];},GetCellBounds(){return this.bounds;},GetCellPadding(){return this.padding;},
 set NumLines(n){this.columns=n;},SetCellPadding(p){this.padding=p;this.PositionCells();},SetCellBounds(b){this.bounds=b;if(first){first.width=b.width;first.height=b.height;}this.PositionCells();},
 PositionCells(){positions++;},GetAllCells(){throw Error('No swatch enumeration needed');},GetAllDisplayObjectCells(){throw Error('No swatch enumeration needed');}};
 const owner={mGrid:grid,mDataFeed:feed,mSwatchType:CASSwatchType.SKINTONE,mMaxCols:9,mCenterX:0,mbPreserveBackgroundWidth:true,
  apexSwatchGeometry:null,mcScrollList:{},mcSelectionGrid:{mGridLayout:grid},mcSelectionGridBackground:{width:200},get positions(){return positions;}};
'''
 for name in('ApexSwatchGeometry','ApexSwatchColumns'):
  args,body=method(SOURCE,name);result+='owner.'+name+'=function('+args+'){with(this){'+body+'}};\n'
 args,body=method(DONOR,'DCCReflowSkinSwatches')
 needle='var _loc7_ = Math.max(1,Math.floor(_loc3_ / _loc6_));'
 if body.count(needle)!=1:raise AssertionError('Exact native donor count expression absent')
 if patched:body=body.replace(needle,needle+'\n _loc7_=this.ApexSwatchColumns(_loc7_);')
 result+='owner.DCCReflowSkinSwatches=function('+args+'){with(this){'+body+'}};\n'
 for name in('SetWidth','ResetLayout'):
  args,body=method(DONOR,name);result+='owner.'+name+'=function('+args+'){with(this){'+body+'}};\n'
 return result+'''return owner;}
'''

class SwatchColumnTests(unittest.TestCase):
 def case(self,code,patched=True):
  result=subprocess.run(['node','-'],input=setup(patched)+code,text=True,capture_output=True,encoding='utf-8',timeout=15)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
 def test_actual_custom_width_receipt_reproduces_legacy_41_columns(self):
  width=RECEIPT['card_layout']['width']-40;scale=RECEIPT['card_preferences']['scale']
  self.assertEqual(RECEIPT['grid_metrics']['swatch_families'][-1]['dimensions'],[41,1])
  self.case('const p=makePanel();p.dccSkinLayoutWidth='+repr(width)+';p.ApexSwatchGeometry(12,'+repr(scale)+',4,4,'+repr(width)+');assert.equal(p.mGrid.columns,41);',False)
 def test_same_receipt_fixed_without_changing_requested_custom_width_or_feed(self):
  width=RECEIPT['card_layout']['width']-40
  self.case('''const p=makePanel(),feed=p.mDataFeed,selected=feed.selection;p.dccSkinLayoutWidth='''+repr(width)+''';
const result=p.ApexSwatchGeometry(12,.35,4,4,p.dccSkinLayoutWidth);
assert.equal(p.mGrid.columns,12);assert.equal(p.mMaxCols,12);assert.equal(result.columns,12);
assert.equal(p.mcSelectionGridBackground.width,p.dccSkinLayoutWidth);assert.equal(p.mcScrollList.width,p.dccSkinLayoutWidth-12);
assert.equal(p.mGrid.padding.Horizontal,4);assert.equal(p.mGrid.padding.Vertical,4);assert.ok(Math.abs(p.mGrid.bounds.width-7.7)<1e-7);
assert.equal(p.mDataFeed,feed);assert.equal(feed.selection,selected);assert.equal(feed.length,9);''')
 def test_later_real_native_width_resizes_keep_user_columns_and_recompute_native_scroll_geometry(self):
  self.case('''const p=makePanel(29);p.SetWidth(497);p.ApexSwatchGeometry(12,.35,4,4,497);
for(const width of[620,400,537.3775390625]){p.SetWidth(width);assert.equal(p.mGrid.columns,12);assert.equal(p.mMaxCols,12);
assert.equal(p.mcSelectionGridBackground.width,width);assert.equal(p.mcScrollList.width,width-12);
assert.ok(Math.abs(p.mcScrollList.height-3*(7.7+4))<1e-6);}
p.ApexSwatchGeometry(32,.2,4,4,537.3775390625);p.SetWidth(600);assert.equal(p.mGrid.columns,32);''')
 def test_all_four_families_keep_their_rows_and_empty_families_are_also_explicit(self):
  self.case('''const families=[makePanel(0),makePanel(0),makePanel(0),makePanel(9)],outer=families.slice();
for(const p of families){p.SetWidth(497);p.ApexSwatchGeometry(12,.35,4,4,497);p.SetWidth(537);
assert.equal(p.mGrid.GetGridDimensions()[0],12);}
assert.deepEqual(families,outer);assert.deepEqual(families.map(p=>p.mDataFeed.length),[0,0,0,9]);''')
 def test_inactive_wrong_grid_wrong_type_and_invalid_policy_preserve_exact_legacy_count(self):
  self.case('''const p=makePanel();p.SetWidth(497);const legacy=p.mGrid.columns;assert.equal(legacy,Math.floor((497-12)/22));
for(const state of[null,{policy:1,grid:{},columns:12},{policy:0,grid:p.mGrid,columns:12},{policy:1,grid:p.mGrid,columns:33},
{policy:1,grid:p.mGrid,columns:1},{policy:1,grid:p.mGrid,columns:NaN},{policy:1,grid:p.mGrid,columns:'12'}]){
p.apexSwatchGeometry=state;assert.equal(p.ApexSwatchColumns(legacy),legacy);}
p.apexSwatchGeometry={policy:1,grid:p.mGrid,columns:12};p.mSwatchType=-1;assert.equal(p.ApexSwatchColumns(legacy),legacy);''')
 def test_unchanged_repeat_reuses_intrinsics_and_performs_no_second_layout(self):
  self.case('''const p=makePanel();p.SetWidth(497);const first=p.ApexSwatchGeometry(12,.35,4,4,497),positioned=p.positions;
const again=p.ApexSwatchGeometry(12,.35,4,4,497);assert.equal(again.changed,false);assert.equal(p.positions,positioned);
assert.equal(first.natural_width,again.natural_width);assert.equal(first.natural_height,again.natural_height);''')

if __name__=='__main__':unittest.main()
