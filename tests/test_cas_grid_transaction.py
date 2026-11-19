"""Execute production native-adapter AS, plus opt-in private FFDec proof."""
from pathlib import Path
import os
import json
import re
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import cas_grid_transaction as grid


def native_javascript():
    source = grid.ADAPTER_METHODS + '\n' + grid.CORE_METHODS
    functions = []
    for m in re.finditer(r'(?:public|private) function (?:(get) )?(\w+)\(([^)]*)\)\s*:\s*\w+\s*\{', source):
        end, depth = m.end(), 1
        while depth:
            depth += (source[end] == '{') - (source[end] == '}')
            end += 1
        body = source[m.end():end - 1]
        body = re.sub(r'\b(var\s+\w+)\s*:\s*[\w.*]+', r'\1', body)
        body = re.sub(r'catch\((\w+):(?:Error|\*)\)', r'catch(\1)', body)
        body = re.sub(r'\s+as\s+\w+', '', body)
        body = re.sub(r'\bis\b', 'instanceof', body)
        body = re.sub(r'new Vector\.<(?:Number|int)>\(([^)]*)\)', r'makeVector(\1)', body)
        params = re.sub(r':\s*\w+', '', m.group(3))
        fn = 'function(' + params + '){with(this){' + body + '}}'
        if m.group(1):
            functions.append("Object.defineProperty(NativeGrid.prototype,'" + m.group(2) + "',{get:" + fn + '});')
        else:
            functions.append('NativeGrid.prototype.' + m.group(2) + '=' + fn + ';')
    if len(functions) < 35:
        raise ValueError('Incomplete actual AS method extraction')
    return '\n'.join(functions)


NATIVE_MOCK = r'''
const assert=require('node:assert/strict');const int=x=>Number(x)|0;
let time=0,serial=0;const getTimer=()=>time;const makeVector=n=>Array(n).fill(0);
function Dictionary(){return Object.create(null);}
class Margin{
 constructor(top=0,right=NaN,bottom=NaN,left=NaN){
  if(isNaN(right)){this.mTop=this.mBot=this.mLeft=this.mRight=top;}
  else if(isNaN(bottom)){this.mTop=this.mBot=top;this.mLeft=this.mRight=right;}
  else if(isNaN(left)){this.mTop=top;this.mBot=bottom;this.mLeft=this.mRight=right;}
  else{this.mTop=top;this.mRight=right;this.mBot=bottom;this.mLeft=left;}
 }
 get Horizontal(){return this.mLeft+this.mRight;}
 get Vertical(){return this.mTop+this.mBot;}
}
class Rectangle{constructor(x,y,width,height){Object.assign(this,{x,y,width,height});}}
class Point{constructor(x,y){Object.assign(this,{x,y});}}
class DisplayObject{
 constructor(){this.parent=null;this.children=[];this.visible=true;this.mouseEnabled=true;this.mouseChildren=true;this.scaleX=this.scaleY=1;this.id=++serial;}
 toString(){return '#'+this.id;}
 addChild(child){if(child.parent)child.parent.removeChild(child);child.parent=this;this.children.push(child);if(this.owner&&this===this.owner.mGridView){this.owner.atom('attach');if(this.owner.hooks.attach)this.owner.hooks.attach(child);}return child;}
 removeChild(child){assert.equal(child.parent,this);child.parent=null;this.children.splice(this.children.indexOf(child),1);if(this.owner&&this===this.owner.mGridView)this.owner.atom('detach');return child;}
 getChildByName(name){return this.children.find(c=>c.name===name)||null;}
 dispatchEvent(event){if(this.owner)this.owner.resize(event);}
}
class Sprite extends DisplayObject{}
const IView=DisplayObject,IExtendable=DisplayObject;
class Selectability{}
function product(id,extra={}){return Object.assign({id,data_id:id,body_type:1,menu_state:2,GetVariationOrBaseId(){return this.variation_id||this.data_id;}},extra);}
class SelectableArrayDataFeed{
 constructor(n){this.items=Array.from({length:n},(_,i)=>product('item-'+i));this.selection=new Set();}
 get length(){return this.items.length;}
 GetSelectionState(index){return this.selection.has(index);}
 SetSelectionState(index,value){if(value)this.selection.add(index);else this.selection.delete(index);if(this.owner)this.owner.ApexGridNativeGuard('update',{currentTarget:this,mIndicesArray:[index],mDataArray:[this.items[index]],mUserDataArray:[{isSelected:value}]});}
}
class GridEvent{constructor(type,a=null,b=null){this.type=type;this.mRectArray=b;}static RESIZE='resize';}
class Cell extends DisplayObject{
 constructor(){super();this.ext={_selected:false};Object.defineProperty(this.ext,'Selected',{get:()=>this.ext._selected,set:value=>{if(this.ext._selected===value)return;this.ext._selected=value;this.owner.atom('selection');if(this.owner.hooks.selection)this.owner.hooks.selection(this);}});this.item=null;this.mcHitArea={height:147};this.intrinsicWidth=107;this.scaleX=this.scaleY=.35;}
 get width(){return this.intrinsicWidth*this.scaleX;}
 set width(value){this.scaleX=value/this.intrinsicWidth;}
 Draw(item){this.item=item;if(this.owner.donorMarker!==false)this.dccFavoriteProductId=item.data_id;this.scaleX=.35;this.scaleY=item.aspect==null?.35:.35*item.aspect;this.owner.atom('draw');if(this.owner.hooks.draw)this.owner.hooks.draw(this);}
 GetExtension(){return this.ext;}
}
class OtherCell extends Cell{}
class NativeGrid{
 constructor(n=436,initial=48){
  this.apexGridState=null;this.mCells=[];this.mCellsY=[];this.mCellIndexToDataIndexMap=[];
  this.mGridData=new SelectableArrayDataFeed(n);this.mGridData.owner=this;this.mGridView=new DisplayObject();this.mGridView.owner=this;
  this.mCellType=Cell;this.mCellMargin=new Margin();this.mCellBounds=null;this.mCellViewSizeFallback=null;
  this.mNumLines=6;this.mbSuppressUpdates=false;this.mbUseRedrawListener=false;this.mSortedIndexToDataIndex=null;
  this.mPrevRectangleUpdate={y:0};this.hooks={};this.calls=[];this.range=0;this.scroll=0;this.validations=0;this.inputValidations=0;
  this.panel={stage:{},mcTileList:{mGridLayout:this}};this.lease={active:true,generation:1,frame_validated:true};
  for(let i=0;i<initial;i++){const c=new Cell();c.owner=this;c.parent=this.mGridView;this.mGridView.children.push(c);this.mCells.push(c);this.mCellsY.push(0);this.mCellIndexToDataIndexMap.push(i);}
 }
 atom(name){this.calls.push(name);time+=.05;this.invariant();}
 invariant(){assert.equal(this.mCells.length,this.mCellsY.length);assert.equal(this.mCells.length,this.mCellIndexToDataIndexMap.length);}
 CreateCell(){this.atom('construct');const c=new this.mCellType();c.owner=this;c.redraw=this.mbUseRedrawListener;if(this.hooks.construct)this.hooks.construct(c);if(this.ApexGridCaptureNewCell)this.ApexGridCaptureNewCell(c);if(this.mCellBounds&&this.mCellBounds.width)c.width=this.mCellBounds.width;return c;}
 GetNumItems(){return this.mSortedIndexToDataIndex?this.mSortedIndexToDataIndex.length:this.mGridData.length;}
 GetDataIndexOfSortedIndex(index){return this.mSortedIndexToDataIndex?this.mSortedIndexToDataIndex[index]:index;}
 GetDataAtIndex(index){this.atom('lookup');return this.mGridData.items[this.GetDataIndexOfSortedIndex(index)]||null;}
 AddSortedData(e){this.calls.push('logical.add');if(this.mSortedIndexToDataIndex)this.mSortedIndexToDataIndex.push(...e.mIndicesArray);}
 AddSortedDataToFront(e){this.calls.push('logical.front');}
 RemoveSortedData(e){this.calls.push('logical.remove');if(this.mSortedIndexToDataIndex){const gone=e.mIndicesArray[0];this.mSortedIndexToDataIndex=this.mSortedIndexToDataIndex.filter(i=>i!==gone).map(i=>i>gone?i-1:i);}}
 GetSortedIndexOfDataIndex(index){return this.mSortedIndexToDataIndex?this.mSortedIndexToDataIndex.indexOf(index):index;}
 resize(event){
  this.atom('resize');this.range=Math.max(0,Math.ceil(this.GetNumItems()/this.mNumLines)*(this.mCellViewSizeFallback.y+this.mCellMargin.Vertical)-this.mGridView.height);
  this.scroll=Math.max(0,Math.min(this.range,-this.mPrevRectangleUpdate.y));
  assert.equal(this.ApexGridNativeGuard('scroll',{mRect:{y:-this.scroll}}),true);
  assert.equal(this.ApexGridNativeGuard('selection'),true);
  if(this.hooks.resize)this.hooks.resize();
 }
}
function request(g,columns=32,extra={}){
 return Object.assign({columns,width:38,height:51,scale:.35,gapX:4,gapY:4,viewWidth:1400,viewHeight:1009.7,scrollY:0,marginX:0,marginY:0,
  panel:g.panel,owner:g.lease,validate:owner=>{g.validations++;return owner===g.lease&&owner.active===true;},
  inputValidate:owner=>{g.inputValidations++;return owner===g.lease&&owner.active===true;}},extra);
}
function drive(g,limit=12000,budget=1){for(let i=0;i<limit;i++){const s=g.ApexGridStep(budget,0);g.invariant();if(s.error)throw Error(s.error);if(s.phase==='done'||s.phase==='cancelled')return s;}throw Error('no convergence '+JSON.stringify(g.ApexGridStatus()));}
'''


@unittest.skipUnless(shutil.which('node'), 'Node required for actual native AS bodies')
class NativeAdapterExecutionTests(unittest.TestCase):
    def case(self, text):
        result = subprocess.run(['node', '-'], input=NATIVE_MOCK + native_javascript() + text,
                                capture_output=True, text=True, encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_actual_native_adapter_constructs_attaches_and_binds_bounded_target(self):
        self.case('''
const g=new NativeGrid();g.mGridData.selection.add(435);g.ApexGridBegin(request(g));let steps=0;
while(g.ApexGridStatus().phase!=='done'){const before=g.calls.length;g.ApexGridStep(1,0);g.invariant();assert.ok(g.calls.length-before<=3);assert.ok(++steps<3000);}
assert.equal(g.mCells.length,448);assert.equal(g.calls.filter(x=>x==='construct').length,400);
assert.equal(g.calls.filter(x=>x==='attach').length,400);assert.equal(g.calls.filter(x=>x==='draw').length,436);
assert.equal(g.calls.filter(x=>x==='resize').length,1);assert.equal(g.mCells[435].ext.Selected,true);
assert.equal(g.mGridView.visible,true);assert.equal(g.mGridView.mouseChildren,true);assert.equal(g.mbSuppressUpdates,false);
assert.equal(g.ApexGridStatus().counts.construct,400);assert.ok(steps>1600);
assert.equal(g.ApexGridNativeGuard('input',{currentTarget:g.mCells[447]}),true);
''')

    def test_native_input_and_redraw_never_validate_or_apply_an_unready_or_retired_cell(self):
        self.case('''
const g=new NativeGrid(8,0);assert.equal(g.ApexGridNativeGuard('input',{}),false);g.ApexGridBegin(request(g,4,{viewHeight:100}));
const before=g.validations;assert.equal(g.ApexGridNativeGuard('input',{currentTarget:new Cell()}),true);assert.equal(g.validations,before);
drive(g);const active=g.mCells[0],retired=new Cell();let n=g.validations;
assert.equal(g.ApexGridNativeGuard('input',{currentTarget:active}),false);assert.equal(g.ApexGridNativeGuard('input',{currentTarget:retired}),true);
assert.equal(g.ApexGridNativeGuard('redraw',{currentTarget:retired}),true);assert.equal(g.validations,n);
assert.equal(g.inputValidations,1);
g.lease.active=false;assert.equal(g.ApexGridNativeGuard('input',{currentTarget:active}),true);assert.equal(g.validations,n);
assert.equal(g.inputValidations,1);
''')

    def test_native_sorted_feed_bookkeeping_and_selection_are_preserved_without_bulk_selection(self):
        self.case('''
const g=new NativeGrid(8,0);g.ApexGridBegin(request(g,4,{viewHeight:100}));drive(g);
g.ApexGridNativeGuard('sort',{currentTarget:g.mGridData,mIndicesArray:[7,6,5,4,3,2,1,0]});drive(g);assert.equal(g.mCells[0].item.id,'item-7');
g.mGridData.items.push(product('added'));g.ApexGridNativeGuard('add',{currentTarget:g.mGridData,mIndicesArray:[8]});assert.ok(g.calls.includes('logical.add'));drive(g);
g.mGridData.items.splice(1,1);g.ApexGridNativeGuard('remove',{currentTarget:g.mGridData,mIndicesArray:[1]});assert.ok(g.calls.includes('logical.remove'));drive(g);
g.mGridData.selection.add(6);assert.equal(g.ApexGridNativeGuard('selection'),true);drive(g);assert.ok(g.mCells.some(c=>c.item&&c.item.id==='item-7'&&c.ext.Selected));
g.mGridData.items=[];g.ApexGridNativeGuard('removeAll',{currentTarget:g.mGridData});drive(g);assert.equal(g.mCells.length,0);
g.mGridData.items.push(product('after-empty'));g.ApexGridNativeGuard('add',{currentTarget:g.mGridData,mIndicesArray:[0]});drive(g);assert.equal(g.mCells[0].item.id,'after-empty');
''')

    def test_class_change_retires_old_cells_incrementally_without_validation_only_constructor(self):
        self.case('''
const g=new NativeGrid(8,8);g.ApexGridBegin(request(g,4,{viewHeight:100}));drive(g);const before=g.calls.filter(x=>x==='construct').length;
assert.equal(g.ApexGridNativeSetCellView(OtherCell,new Margin(),true),true);drive(g);
assert.ok(g.mCells.every(c=>c instanceof OtherCell));assert.equal(g.calls.filter(x=>x==='construct').length-before,8);
assert.equal(g.calls.filter(x=>x==='detach').length,8);assert.equal(g.mbUseRedrawListener,true);g.invariant();
''')

    def test_dispose_is_constant_work_and_needs_no_retired_main_frame(self):
        self.case('''
for(const stop of ['construct','attach','draw']){
 const g=new NativeGrid(8,0);g.ApexGridBegin(request(g,4,{viewHeight:100}));let disposed=false;
 g.hooks[stop]=()=>{if(!disposed){disposed=true;const before=g.calls.length;g.lease.active=false;g.ApexGridCancel('dispose');assert.equal(g.calls.length,before);}};
 for(let i=0;!disposed;i++){g.ApexGridStep(1,0);assert.ok(i<100);}
 const s=g.ApexGridStatus();assert.equal(s.phase,'cancelled');assert.equal(s.pendingCell,false);assert.equal(s.lease,false);assert.equal(g.mbSuppressUpdates,false);
 assert.equal(g.ApexGridNativeGuard('input',{currentTarget:new Cell()}),true);g.invariant();
}
''')

    def test_external_suppression_write_is_never_released_by_owned_cleanup(self):
        self.case('''
const g=new NativeGrid(8,0);g.ApexGridBegin(request(g,4));g.ApexGridStep(1,0);
g.ApexGridSuppressionChanged(true);g.mbSuppressUpdates=true;drive(g);
assert.equal(g.mbSuppressUpdates,true);assert.equal(g.ApexGridStatus().reason,'lease');
''')

    def test_feed_replacement_requires_current_main_lease_and_fresh_bind(self):
        self.case('''
const g=new NativeGrid(8,0);g.ApexGridBegin(request(g,4));g.ApexGridStep(1,0);
g.lease.active=false;g.mGridData=new SelectableArrayDataFeed(4);g.lease={active:true,generation:2};
g.ApexGridBegin(request(g,2,{viewHeight:100}));drive(g);if(g.ApexGridStatus().phase!=='done')drive(g);
assert.equal(g.ApexGridStatus().phase,'done');assert.equal(g.mCells.filter(c=>c.visible).length,4);assert.equal(g.mGridView.mouseEnabled,true);
''')

    def test_error_abandon_releases_only_owned_lease_without_replay_or_queued_resume(self):
        self.case('''
for(const stop of ['construct','attach','draw']){
 const g=new NativeGrid(8,0);g.ApexGridBegin(request(g,4,{viewHeight:100}));
 g.hooks[stop]=()=>{throw Error('failed '+stop);};let s;
 for(let i=0;i<100;i++){s=g.ApexGridStep(1,0);if(s.error)break;}
 assert.ok(s.error);g.apexGridState.nextRequest=request(g,2);const before=g.calls.length;
 s=g.ApexGridCancel('error-abandon');assert.equal(g.calls.length,before);
 assert.equal(s.reason,'error-abandon');assert.equal(s.phase,'cancelled');assert.equal(s.pendingCell,false);assert.equal(s.lease,false);
 assert.equal(g.mbSuppressUpdates,false);assert.equal(g.lease.active,false);assert.equal(g.apexGridState.nextRequest,null);
 assert.equal(g.mGridView.visible,false);assert.equal(g.mGridView.mouseChildren,false);
 for(let i=0;i<3;i++)assert.equal(g.ApexGridStep(64,0).phase,'cancelled');
 assert.equal(g.calls.length,before);assert.equal(g.ApexGridNeedsWork(),false);assert.equal(g.ApexGridNativeGuard('input',{}),true);g.invariant();
}
const foreign=new NativeGrid(4,0);foreign.ApexGridBegin(request(foreign,2));foreign.ApexGridStep(1,0);
foreign.ApexGridSuppressionChanged(true);foreign.mbSuppressUpdates=true;const before=foreign.calls.length;
foreign.ApexGridCancel('error-abandon');assert.equal(foreign.calls.length,before);assert.equal(foreign.mbSuppressUpdates,true);
const broken=new NativeGrid(0,0);broken.ApexTxnBegin=()=>{throw Error('before job');};assert.throws(()=>broken.ApexGridBegin(request(broken)));
assert.equal(broken.ApexGridCancel('error-abandon').phase,'cancelled');assert.equal(broken.ApexGridNativeGuard('input',{}),true);assert.equal(broken.calls.length,0);
''')

    def test_failed_begin_terminal_null_job_consumes_native_events_without_replay(self):
        self.case('''
const g=new NativeGrid(8,0);assert.throws(()=>g.ApexGridBegin(request(g,2,{width:0})));
assert.equal(g.apexGridState.job,null);const before=g.calls.length;const oldType=g.mCellType;
const terminal=g.ApexGridCancel('error-abandon');assert.equal(terminal.phase,'cancelled');
assert.equal(terminal.armed,true);assert.equal(terminal.abandoned,true);assert.equal(terminal.terminal_blocked,true);
assert.equal(terminal.lease,false);assert.equal(terminal.pendingCell,false);
for(const kind of ['selection','redraw','add','front','remove','removeAll','sort','update','scroll','bounds','padding','position','reset','profile','input'])
 assert.equal(g.ApexGridNativeGuard(kind,{currentTarget:g.mGridData,mIndicesArray:[0],mRect:{y:0}}),true);
assert.equal(g.ApexGridNativeSetCellView(OtherCell,null,false),true);assert.equal(g.mCellType,oldType);
assert.equal(g.ApexGridStep(64,0).phase,'cancelled');assert.equal(g.ApexGridStatus().terminal_blocked,true);
assert.equal(g.ApexGridNeedsWork(),false);assert.equal(g.calls.length,before);assert.equal(g.validations,1);
assert.equal(g.inputValidations,0);assert.equal(g.mGridView.visible,false);assert.equal(g.mbSuppressUpdates,false);g.invariant();
''')

    def test_draw_and_selection_yield_separately_with_attributed_timing(self):
        self.case('''
const g=new NativeGrid(4,0);g.mGridData.selection.add(0);
g.hooks.draw=()=>{time+=7;};g.hooks.selection=()=>{time+=53;};g.ApexGridBegin(request(g,2));
let s;for(let i=0;i<100;i++){s=g.ApexGridStep(1,0);if(s.phase==='selection')break;}
assert.equal(s.phase,'selection');assert.equal(s.counts.draw,1);assert.equal(s.counts.selection,0);
const c=g.mCells[0];assert.equal(c.ext.Selected,false);assert.equal(g.apexGridState.ready[c],undefined);
assert.equal(g.mGridView.visible,false);assert.equal(g.ApexGridNativeGuard('input',{currentTarget:c}),true);
for(const item of g.mGridData.items)assert.ok(!Object.values(g.apexGridState.job).includes(item));
const draws=g.calls.filter(x=>x==='draw').length;s=g.ApexGridStep(64,getTimer()+1);
assert.equal(g.calls.filter(x=>x==='draw').length,draws);assert.equal(c.ext.Selected,true);assert.equal(s.counts.selection,1);
assert.equal(s.counts.selected_setter,1);assert.equal(s.counts.data,3);assert.ok(s.maxMS.draw>=7);assert.ok(s.maxMS.selected_setter>=53);
assert.ok(s.maxMS.selection>=53);assert.ok(s.maxMS.bind<10);assert.equal(s.phase,'bind');
assert.equal(g.apexGridState.ready[c],s.generation);assert.equal(g.mGridView.visible,false);
drive(g);assert.equal(g.ApexGridStatus().phase,'done');assert.equal(g.mGridView.visible,true);
''')

    def test_selection_rechecks_all_primitive_and_structural_targets_before_setter(self):
        self.case('''
for(const kind of ['id','variation','body','menu','map','cell','generation','owner','feed','view','marker']){
 const g=new NativeGrid(4,0);g.mGridData.selection.add(0);g.ApexGridBegin(request(g,2));
 for(let i=0;g.ApexGridStatus().phase!=='selection';i++){g.ApexGridStep(1,0);assert.ok(i<100);}
 const c=g.mCells[0],j=g.apexGridState.job,oldGeneration=j.generation;
 if(kind==='id')g.mGridData.items[0].data_id='different';
 else if(kind==='variation')g.mGridData.items[0].variation_id='different';
 else if(kind==='body')g.mGridData.items[0].body_type=9;
 else if(kind==='menu')g.mGridData.items[0].menu_state=19;
 else if(kind==='map')g.mCellIndexToDataIndexMap[0]=1;
 else if(kind==='cell'){const other=new Cell();other.owner=g;other.parent=g.mGridView;g.mCells[0]=other;}
 else if(kind==='generation')j.generation++;
 else if(kind==='owner')g.lease.generation++;
 else if(kind==='feed')g.mGridData=new SelectableArrayDataFeed(4);
 else if(kind==='view'){g.mGridView=new DisplayObject();g.mGridView.owner=g;}
 else c.dccFavoriteProductId='stale-donor-base';
 g.ApexGridStep(1,0);assert.equal(c.ext.Selected,false,kind);assert.equal(int(j.phaseCounts.selected_setter),0,kind);
 assert.notEqual(g.apexGridState.ready[c],oldGeneration,kind);assert.equal(g.ApexGridNativeGuard('input',{currentTarget:c}),true,kind);g.invariant();
}
''')

    def test_optional_donor_marker_absent_is_supported_and_present_marker_is_base_id(self):
        self.case('''
const plain=new NativeGrid(4,0);plain.donorMarker=false;plain.mGridData.selection.add(0);plain.ApexGridBegin(request(plain,2));drive(plain);
assert.equal('dccFavoriteProductId' in plain.mCells[0],false);assert.equal(plain.mCells[0].ext.Selected,true);
const donor=new NativeGrid(4,0);donor.mGridData.items[0].variation_id='chosen-swatch';donor.mGridData.selection.add(0);
donor.ApexGridBegin(request(donor,2));drive(donor);assert.equal(donor.mCells[0].dccFavoriteProductId,'item-0');
assert.equal(donor.mCells[0].ext.Selected,true);assert.equal(donor.ApexGridStatus().phase,'done');
''')

    def test_native_selection_updates_between_atoms_invalidate_revision_and_rebind(self):
        self.case('''
for(const route of ['feed-update','selection-event']){
 const g=new NativeGrid(4,0);g.ApexGridBegin(request(g,2));
 for(let i=0;g.ApexGridStatus().phase!=='selection';i++){g.ApexGridStep(1,0);assert.ok(i<100);}
 const c=g.mCells[0],old=g.ApexGridStatus();
 if(route==='feed-update')g.mGridData.SetSelectionState(0,true);
 else{g.mGridData.selection.add(0);g.ApexGridNativeGuard('selection');}
 assert.ok(g.apexGridState.revision>old.revision);g.ApexGridStep(1,0);
 assert.equal(c.ext.Selected,false);assert.notEqual(g.apexGridState.ready[c],old.generation);
 drive(g);assert.equal(g.mCells[0].ext.Selected,true);assert.ok(g.ApexGridStatus().generation>old.generation);
}
''')

    def test_selection_timeline_reentry_cannot_publish_stale_or_resume_abandoned_work(self):
        self.case('''
for(const action of ['update','dispose','error-abandon','foreign-lease']){
 const g=new NativeGrid(4,0);g.mGridData.selection.add(0);g.ApexGridBegin(request(g,2));
 for(let i=0;g.ApexGridStatus().phase!=='selection';i++){g.ApexGridStep(1,0);assert.ok(i<100);}
 const c=g.mCells[0],oldGeneration=g.ApexGridStatus().generation;
 g.hooks.selection=()=>{delete g.hooks.selection;
  if(action==='update'){g.mGridData.items[0]=product('replacement');g.ApexGridNativeGuard('update',{currentTarget:g.mGridData});}
  else if(action==='foreign-lease'){g.ApexGridSuppressionChanged(true);g.mbSuppressUpdates=true;}
  else g.ApexGridCancel(action);
 };
 g.ApexGridStep(1,0);assert.notEqual(g.apexGridState.ready[c],oldGeneration);assert.equal(g.mGridView.visible,false);
 assert.equal(g.ApexGridNativeGuard('input',{currentTarget:c}),true);
 if(action==='update'){drive(g);assert.equal(g.mCells[0].item.id,'replacement');assert.equal(g.ApexGridStatus().phase,'done');}
 else if(action==='foreign-lease'){drive(g);assert.equal(g.mbSuppressUpdates,true);}
 else{const before=g.calls.length;assert.equal(g.ApexGridStatus().phase,'cancelled');g.ApexGridStep(64,0);assert.equal(g.calls.length,before);assert.equal(g.apexGridState.job.boundCell,null);}
 g.invariant();
}
''')

    def test_native_margin_order_preserves_zero_origin_total_pitch_and_stable_replans(self):
        self.case('''
for(const args of [[2],[2,3],[2,3,5],[2,3,5,7]]){
 const m=new Margin(...args);
 assert.equal(m.mTop,2);assert.equal(m.mBot,args.length>2?5:2);
 assert.equal(m.mRight,args.length>1?3:2);assert.equal(m.mLeft,args.length===4?7:(args.length>1?3:2));
 assert.equal(m.Horizontal,m.mLeft+m.mRight);assert.equal(m.Vertical,m.mTop+m.mBot);
}
const g=new NativeGrid(40,0);const extra={gapX:6,gapY:9,height:147*.35,viewHeight:100,marginX:0,marginY:0};
g.ApexGridBegin(request(g,4,extra));drive(g);
assert.equal(g.mCellMargin.mTop,0);assert.equal(g.mCellMargin.mLeft,0);assert.equal(g.mCellMargin.mRight,6);assert.equal(g.mCellMargin.mBot,9);
assert.equal(g.mCellMargin.Horizontal,6);assert.equal(g.mCellMargin.Vertical,9);
assert.equal(g.mCells[0].x,0);assert.equal(g.mCells[0].y,0);assert.equal(g.mCells[1].x,44);
assert.ok(Math.abs(g.mCells[4].y-(147*.35+9))<1e-10);
assert.ok(Math.abs(g.range-(10*(147*.35+9)-100))<1e-10);
const generation=g.ApexGridStatus().generation;const before=g.calls.length;
for(let i=0;i<30;i++){
 g.ApexGridBegin(request(g,4,Object.assign({},extra,{marginX:g.mCellMargin.mLeft,marginY:g.mCellMargin.mTop})));
 assert.equal(g.ApexGridStep(64,0).phase,'done');
}
assert.equal(g.ApexGridStatus().generation,generation);assert.equal(g.calls.length,before);assert.equal(g.mCells[0].x,0);
''')

    def test_confirmed_live_row_height_converges_across_geometry_only_replans(self):
        self.case('''
const g=new NativeGrid(436,0);for(const item of g.mGridData.items)item.aspect=103/147;
g.ApexGridBegin(request(g,12,{bootstrap:true}));for(let i=0;i<10&&!g.ApexGridStatus().measurement_ready;i++)g.ApexGridStep(64,getTimer()+1);
let row=147*.35,changes=0,done=0;
for(let frame=0;frame<600;frame++){
 g.ApexGridBegin(request(g,12,{bootstrap:false,height:row}));const status=g.ApexGridStep(64,getTimer()+1);if(status.phase==='done')done++;
 let next=status.natural_height*.35*status.natural_aspect;
 if(status.measured_scale===.35&&status.measured_height>0)next=status.measured_height;
 if(Math.abs(next-row)>1e-10)changes++;row=next;
}
assert.ok(done>400);assert.ok(changes<=2);assert.ok(g.ApexGridStatus().publishes>0);assert.ok(g.ApexGridStatus().generation<=3);
assert.ok(Math.abs(row-103*.35)<1e-10);assert.equal(g.mbSuppressUpdates,false);
const measured=g.ApexGridStatus().measured_height;g.ApexGridBegin(request(g,6,{height:row}));
assert.equal(g.ApexGridStatus().measured_height,measured);drive(g);assert.equal(g.ApexGridStatus().measured_height,measured);
''')

    def test_confirmed_row_metrics_invalidate_for_feed_class_scale_and_owner(self):
        self.case('''
const g=new NativeGrid(8,0);g.ApexGridBegin(request(g,4));drive(g);assert.ok(g.ApexGridStatus().measured_height>0);
g.ApexGridNativeGuard('update',{currentTarget:g.mGridData});assert.equal(g.ApexGridStatus().measured_height,0);drive(g);
g.ApexGridBegin(request(g,4,{scale:.5}));assert.equal(g.ApexGridStatus().measured_height,0);drive(g);assert.equal(g.ApexGridStatus().measured_scale,.5);
g.ApexGridNativeSetCellView(OtherCell,null,false);assert.equal(g.ApexGridStatus().measured_height,0);drive(g);
g.lease.active=false;g.lease={active:true,generation:2};g.ApexGridBegin(request(g,4));drive(g,12000,1);
if(g.ApexGridStatus().phase!=='done')drive(g);assert.ok(g.ApexGridStatus().measured_height>0);
g.lease.active=false;g.lease={active:true,generation:3};g.ApexGridBegin(request(g,4));
assert.equal(g.ApexGridStatus().measured_height,0);
''')

    def test_hidden_grid_can_arm_before_first_class_feed_and_requestdata_publication(self):
        self.case('''
const g=new NativeGrid(0,0);g.mGridData=null;g.mCellType=null;
g.ApexGridBegin(request(g,6));assert.equal(g.calls.length,0);
assert.equal(g.ApexGridNativeSetCellView(Cell,null,false),true);
g.mGridData=new SelectableArrayDataFeed(436);
assert.equal(g.ApexGridNativeGuard('position'),true);
g.ApexGridNativeGuard('add',{currentTarget:g.mGridData,mIndicesArray:g.mGridData.items.map((_,i)=>i)});
assert.equal(g.calls.filter(x=>x==='construct'||x==='draw').length,0);
g.lease.active=false;g.lease={active:true,generation:2};g.ApexGridBegin(request(g,6));drive(g);
if(g.ApexGridStatus().phase!=='done')drive(g);
assert.equal(g.ApexGridStatus().phase,'done');assert.equal(g.calls.filter(x=>x==='construct').length,g.mCells.length);
assert.equal(g.calls.filter(x=>x==='draw').length,g.mCells.length);
assert.equal(g.mCellType,Cell);assert.equal(g.mGridView.mouseChildren,true);
''')

    def test_live_donor_aspect_and_marker_survive_width_distortion_and_reflow(self):
        self.case('''
const g=new NativeGrid(4,0);for(const item of g.mGridData.items)item.aspect=103/147;
g.ApexGridBegin(request(g,2,{height:103*.35}));drive(g);
for(const c of g.mCells){assert.ok(Math.abs(c.scaleY/c.scaleX-103/147)<1e-10);assert.ok(Math.abs(c.getChildByName('apexCatalogCardScale').scaleY-103/147)<1e-10);c.scaleX*=2;}
g.ApexGridBegin(request(g,4,{height:103*.35}));drive(g);
for(const c of g.mCells)assert.ok(Math.abs(c.scaleY/c.scaleX-103/147)<1e-10);
assert.ok(Math.abs(g.ApexGridStatus().measured_height-103*.35)<1e-10);
''')

    def test_ready_input_performs_one_fresh_check_false_or_throw_blocks_and_cancels(self):
        self.case('''
for(const throwing of [false,true]){
 const g=new NativeGrid(4,0);const r=request(g,2);r.inputValidate=()=>{g.inputValidations++;if(throwing)throw Error('context unavailable');return false;};
 g.ApexGridBegin(r);drive(g);assert.equal(g.ApexGridNativeGuard('input',{currentTarget:g.mCells[0]}),true);
 assert.equal(g.inputValidations,1);assert.equal(g.lease.active,false);assert.equal(g.ApexGridStatus().cancelled,true);
}
''')

    def test_same_view_context_reuses_pool_but_view_replacement_retires_from_old_view(self):
        self.case('''
const g=new NativeGrid(8,0);g.ApexGridBegin(request(g,4));drive(g);let before=g.calls.filter(x=>x==='construct').length;
g.lease.active=false;g.lease={active:true,generation:2};g.ApexGridBegin(request(g,4));drive(g);if(g.ApexGridStatus().phase!=='done')drive(g);
assert.equal(g.calls.filter(x=>x==='construct').length,before);
const oldView=g.mGridView;g.mGridView=new DisplayObject();g.mGridView.owner=g;
g.lease.active=false;g.lease={active:true,generation:3};g.ApexGridBegin(request(g,4));drive(g);if(g.ApexGridStatus().phase!=='done')drive(g);
assert.equal(oldView.children.length,0);assert.ok(g.mCells.every(c=>c.parent===g.mGridView));assert.equal(g.mGridView.visible,true);
''')

    def test_bootstrap_uses_first_real_prewidth_cell_then_reuses_it_for_rendering(self):
        self.case('''
const g=new NativeGrid(8,0);g.mCellBounds=new Rectangle(0,0,10,0);g.ApexGridBegin(request(g,4,{bootstrap:true}));
let s;for(let i=0;i<10;i++){s=g.ApexGridStep(64,getTimer()+1);if(s.measurement_ready)break;}
assert.equal(s.phase,'measured');assert.equal(s.natural_width,107);assert.equal(s.natural_height,147);assert.equal(s.natural_aspect,1);
assert.equal(g.calls.filter(x=>x==='construct').length,1);assert.equal(g.calls.filter(x=>x==='attach').length,0);
g.ApexGridBegin(request(g,4,{bootstrap:false,width:107*.35}));drive(g);
assert.equal(g.calls.filter(x=>x==='construct').length,8);assert.equal(g.mCells.length,8);
for(const c of g.mCells)assert.ok(Math.abs(c.scaleY/c.scaleX-1)<1e-12);
''')

    def test_bootstrap_owner_readiness_and_safe_untouched_rollback(self):
        self.case('''
const g=new NativeGrid(8,0);g.lease.frame_validated=false;g.ApexGridBegin(request(g,4,{bootstrap:true}));
assert.equal(g.ApexGridStep(64,getTimer()+1).phase,'await-owner');assert.equal(g.calls.length,0);
assert.equal(g.ApexGridCancel('bootstrap-failed').phase,'unarmed');assert.equal(g.ApexGridNativeGuard('input',{}),false);
g.lease.frame_validated=true;g.ApexGridBegin(request(g,4,{bootstrap:true}));g.ApexGridStep(1,0);
assert.equal(g.ApexGridCancel('bootstrap-failed').phase,'rollback-refused');g.ApexGridCancel('dispose');assert.equal(g.mbSuppressUpdates,false);
const broken=new NativeGrid(4,0);assert.throws(()=>broken.ApexGridBegin(request(broken,2,{bootstrap:true,width:0})));
assert.equal(broken.ApexGridCancel('bootstrap-failed').phase,'unarmed');assert.equal(broken.ApexGridNativeGuard('position'),false);
const deferred=new NativeGrid(4,0);deferred.ApexGridBegin(request(deferred,2,{bootstrap:true}));
deferred.ApexGridNativeGuard('update',{currentTarget:deferred.mGridData});
assert.equal(deferred.ApexGridStatus().operations,0);assert.equal(deferred.ApexGridCancel('bootstrap-failed').reason,'native-events-deferred');
''')

    def test_needs_work_idle_fastpath_has_no_queries_objects_or_shape_access(self):
        self.case('''
const g=new NativeGrid(4,0);assert.equal(g.ApexGridNeedsWork(),false);g.ApexGridBegin(request(g,2));assert.equal(g.ApexGridNeedsWork(),true);drive(g);
const v=g.validations,input=g.inputValidations,calls=g.calls.length;
for(let i=0;i<1000;i++)assert.equal(g.ApexGridNeedsWork(),false);
assert.equal(g.validations,v);assert.equal(g.inputValidations,input);assert.equal(g.calls.length,calls);
g.ApexGridNativeGuard('position');assert.equal(g.ApexGridNeedsWork(),true);drive(g);
g.ApexGridNativeGuard('update',{currentTarget:g.mGridData});assert.equal(g.ApexGridNeedsWork(),true);
''')


@unittest.skipUnless(os.environ.get('APEX_PRIVATE_FFDEC_TESTS') == '1', 'Explicit private compiled-provider test opt-in')
class CompiledProviderTests(unittest.TestCase):
    def test_canonical_provider_serialization_and_unarmed_execution(self):
        data, proof = grid.adapt(ROOT / '.work/research/ClassLibraryGamedata.swf',
            (ROOT / '.work/v328-grid-perf-native/canonical-profile.swf').read_bytes(),
            None,
            ROOT / '.work/research/ffdec/ffdec-cli.exe', ROOT / '.work/v329-grid-transaction-compiled-test')
        self.assertEqual(grid.digest(data), proof['abc_sha256'])
        self.assertEqual(proof['guarded_native_bodies'], 18)
        self.assertTrue(proof['whole_abc_rollback_verified'])
        self.assertTrue(proof['unarmed_original_native_flow_verified'])
        self.assertFalse(proof['runtime_qualified'])
        self.check_chain(data, proof, '62ECC59A:00000000:12272E1AC0C1F8E2', 'canonical-profile.swf')

    def check_chain(self, data, proof, tgi, filename):
        import cas_ui_build
        baseline = (ROOT / '.work/v328-grid-perf-native' / filename).read_bytes()
        record = json.loads((ROOT / '.work/v328-grid-perf-profile-source-report.json').read_text())['providers'][tgi]
        base = dict(base_resource_sha256=proof['base_provider_sha256'], patched_resource_sha256=record['patched_resource_sha256'],
                    native_bytecode_contract=record['contract'])
        native_tag = next(t[3] for t in cas_ui_build.tags(cas_ui_build.unpack(baseline)[1]) if t[0] == 82)
        final = cas_ui_build.replace_payload(baseline, native_tag[:native_tag.index(b'\0', 4) + 1] + data)
        chained = grid.chain_adapter(base, proof, final)
        self.assertTrue(grid.verify_adapter(chained, final))
        work = Path(os.environ.get('APEX_GRID_TRANSACTION_FIXTURES', str(ROOT / '.work/v329-grid-transaction-final')))
        work.mkdir(exist_ok=True)
        name = 'canonical' if '12272' in tgi else 'donor'
        (work / (name + '.swf')).write_bytes(final)
        (work / (name + '.json')).write_text(json.dumps(chained, indent=2) + '\n')
        with self.assertRaises(ValueError):
            grid.verify_adapter(chained, baseline)

    def test_donor_provider_serialization_and_unarmed_execution(self):
        data, proof = grid.adapt(ROOT / '.work/research/maru-integrated/DynamicCASGridLibrary.swf',
            (ROOT / '.work/v328-grid-perf-native/donor-profile.swf').read_bytes(),
            None,
            ROOT / '.work/research/ffdec/ffdec-cli.exe', ROOT / '.work/v329-grid-transaction-donor-test')
        self.assertEqual(proof['guarded_native_bodies'], 18)
        self.assertEqual(proof['appended_methods'], 45)
        self.assertTrue(proof['protected_field_namespace_bindings_verified'])
        self.check_chain(data, proof, '62ECC59A:00000000:89D13757C58C2E05', 'donor-profile.swf')


if __name__ == '__main__':
    unittest.main()
