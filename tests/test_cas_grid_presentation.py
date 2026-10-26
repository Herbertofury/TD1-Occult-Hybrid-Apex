"""Actual staged AS helpers; deterministic native/widget async fixture."""
from pathlib import Path
import importlib.util
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'tests')]
from test_cas_grid_transaction import NATIVE_MOCK
import cas_grid_presentation as stage


def javascript():
    source = stage.helpers()
    functions = []
    for m in re.finditer(r'(?:public|private) function (?:(get) )?(\w+)\(([^)]*)\)\s*:\s*[\w.<>]+\s*\{', source):
        end, depth = m.end(), 1
        while depth:
            depth += (source[end] == '{') - (source[end] == '}')
            end += 1
        body = source[m.end():end-1]
        body = re.sub(r'\b(var\s+\w+)\s*:\s*[\w.*<>]+', r'\1', body)
        body = re.sub(r'catch\((\w+):(?:Error|\*)\)', r'catch(\1)', body)
        body = re.sub(r'for each\(var (\w+) in ([^\n]+)\)', r'for(var \1 of \2)', body)
        body = re.sub(r'\s+as\s+\w+', '', body)
        body = body.replace('expected is String', 'typeof expected==="string"')
        body = re.sub(r'\bis\b', 'instanceof', body)
        body = re.sub(r'new Vector\.<\w+>\(\)', '[]', body)
        body = re.sub(r'new Vector\.<\w+>\(([^)]*)\)', r'makeVector(\1)', body)
        params = re.sub(r':\s*[\w.<>]+', '', m.group(3))
        fn = 'function(' + params + '){with(this){' + body + '}}'
        if m.group(1):
            functions.append("Object.defineProperty(NativeGrid.prototype,'" + m.group(2) + "',{get:" + fn + '});')
        else:
            functions.append('NativeGrid.prototype.' + m.group(2) + '=' + fn + ';')
    return '\n'.join(functions)


BOOT = '''
int.MAX_VALUE=2147483647;
const AssetLoaderEvent={FAIL:'assetLoadFail'},SharedIcons={ICON_WARNING:'0x2fbc69321e0759e7'};
class TextFormat{constructor(...args){}}
class TextField extends DisplayObject{constructor(){super();this.text='';}}
Object.defineProperty(Cell.prototype,'mcImage',{get(){
 if(!this._image){const cell=this;this.mcHitArea.width=107;this._image={resourceId:null,ready:false,listeners:[],toString(){return 'image:'+cell.id;},
  addEventListener(kind,fn){if(!this.listeners.includes(fn))this.listeners.push(fn);},
  LoadImage(resource){this.resourceId=resource;this.ready=!cell.owner.delayImages;
   if(cell.owner.failPrimary && resource!==SharedIcons.ICON_WARNING || cell.owner.failWarning && resource===SharedIcons.ICON_WARNING){
    this.ready=false;for(const fn of this.listeners)fn.call(cell.owner,{currentTarget:this});this.resourceId=null;
   }
  },ApexImageReadyFor(resource){return this.ready && this.resourceId===resource;}};
 }
 return this._image;
}});
const nativeDraw=Cell.prototype.Draw;
Cell.prototype.Draw=function(item){
 nativeDraw.call(this,item);
 this.mcImage.LoadImage('thumb:'+item.data_id);
};
const rendered=g=>g.mGridView.children.filter(c=>c.visible && c.item).map(c=>c.item.data_id);
function stagedReady(g){for(const c of g.apexGridState.presentation.stageCells)c.mcImage&&(c.mcImage.ready=true);}
function bounded(g,n=2000){for(let i=0;i<n && g.ApexGridStatus().phase!=='done';i++)g.ApexGridStep(64,0);return g.ApexGridStatus();}
'''


class PresentationTests(unittest.TestCase):
    def case(self, code):
        result = subprocess.run(['node', '-'], input=NATIVE_MOCK + '\n' + javascript() + BOOT + code,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_first_publish_and_scroll_keep_committed_cards_until_real_images_ready(self):
        self.case('''
const g=new NativeGrid(100,0);g.ApexGridBegin(request(g,6,{viewHeight:400}));
assert.equal(bounded(g).phase,'done');const old=g.mCells.slice(),ids=rendered(g);
assert.ok(ids.length>0);g.delayImages=true;
g.ApexGridBegin(request(g,6,{viewHeight:400,scrollY:400}));
for(let i=0;i<1000 && g.ApexGridStatus().phase!=='textures';i++)g.ApexGridStep(1,0);
assert.equal(g.ApexGridStatus().phase,'textures');assert.equal(g.mGridView.visible,true);
assert.deepEqual(g.mCells,old);assert.deepEqual(rendered(g),ids);
assert.equal(g.mGridView.mouseChildren,false);
for(const c of old)assert.equal(g.ApexGridNativeGuard('input',{currentTarget:c}),true);
assert.equal(g.apexGridState.presentation.stageCells.every(c=>!c.visible),true);
g.ApexGridStep(64,0);assert.deepEqual(rendered(g),ids);
stagedReady(g);assert.equal(bounded(g).phase,'done');
assert.notDeepEqual(g.mCells,old);assert.notDeepEqual(rendered(g),ids);
assert.equal(g.mGridView.mouseChildren,true);assert.equal(old.every(c=>!c.visible),true);
''')

    def test_texture_request_change_cannot_publish_stale_loaded_image(self):
        self.case('''
const g=new NativeGrid(100,0);g.ApexGridBegin(request(g,6,{viewHeight:400}));bounded(g);
const ids=rendered(g);g.delayImages=true;g.ApexGridBegin(request(g,6,{viewHeight:400,scrollY:400}));
for(let i=0;i<1000 && g.ApexGridStatus().phase!=='textures';i++)g.ApexGridStep(1,0);
stagedReady(g);const c=g.apexGridState.presentation.stageCells[0];c.mcImage.resourceId='foreign-new-request';
g.ApexGridStep(64,0);assert.notEqual(g.ApexGridStatus().phase,'done');assert.deepEqual(rendered(g),ids);
c.mcImage.resourceId=g.apexGridState.presentation.expected[c].display;assert.equal(bounded(g).phase,'done');
''')

    def test_cancel_releases_work_without_remapping_or_clearing_committed_cards(self):
        self.case('''
const g=new NativeGrid(100,0);g.ApexGridBegin(request(g,6,{viewHeight:400}));bounded(g);
const old=g.mCells.slice(),ids=rendered(g);g.delayImages=true;
g.ApexGridBegin(request(g,6,{viewHeight:400,scrollY:400}));
for(let i=0;i<1000 && g.ApexGridStatus().phase!=='textures';i++)g.ApexGridStep(1,0);
g.ApexGridCancel('context');for(let i=0;i<100 && g.ApexGridStatus().phase!=='cancelled';i++)g.ApexGridStep(64,0);
assert.equal(g.ApexGridStatus().phase,'cancelled');assert.deepEqual(g.mCells,old);assert.deepEqual(rendered(g),ids);
assert.equal(g.mGridView.visible,true);assert.equal(g.mGridView.mouseChildren,false);
''')

    def test_repeated_scroll_uses_two_bounded_initialized_banks(self):
        self.case('''
const g=new NativeGrid(100,0);g.ApexGridBegin(request(g,6,{viewHeight:400}));bounded(g);
g.ApexGridBegin(request(g,6,{viewHeight:400,scrollY:400}));bounded(g);
const allocated=g.calls.filter(c=>c==='construct'||c==='attach').length;
for(let i=0;i<8;i++){g.ApexGridBegin(request(g,6,{viewHeight:400,scrollY:i%2?400:0}));assert.equal(bounded(g).phase,'done');}
assert.equal(g.calls.filter(c=>c==='construct'||c==='attach').length,allocated);
assert.equal(g.calls.filter(c=>c==='detach').length,0);
assert.equal(g.mGridView.children.length,g.mCells.length*2);
''')

    def test_native_class_change_never_reuses_old_class_spare_bank(self):
        self.case('''
const g=new NativeGrid(100,0);g.ApexGridBegin(request(g,6,{viewHeight:400}));bounded(g);
g.ApexGridBegin(request(g,6,{viewHeight:400,scrollY:400}));bounded(g);
const old=g.mCells.slice(),ids=rendered(g);
g.ApexGridNativeSetCellView(OtherCell,new Margin(),true);
g.ApexGridStep(1,0);assert.deepEqual(rendered(g),ids);
assert.equal(bounded(g).phase,'done');assert.ok(g.mCells.every(c=>c instanceof OtherCell));
g.ApexGridBegin(request(g,6,{viewHeight:400,scrollY:0}));
assert.equal(bounded(g).phase,'done');assert.ok(g.mCells.every(c=>c instanceof OtherCell));
assert.equal(old.every(c=>c.parent===null),true);
''')

    def test_confirmed_bad_thumbnail_uses_ea_warning_without_blocking_every_card(self):
        self.case('''
const g=new NativeGrid(100,0);g.ApexGridBegin(request(g,6,{viewHeight:400}));bounded(g);
g.failPrimary=true;g.ApexGridBegin(request(g,6,{viewHeight:400,scrollY:400}));
assert.equal(bounded(g).phase,'done');assert.equal(g.mGridView.mouseChildren,true);
assert.ok(g.apexGridState.presentation.failures.length>0);
for(const c of g.ApexGridPoolViews())assert.equal(c.mcImage.resourceId,SharedIcons.ICON_WARNING);
for(const c of g.ApexGridPoolViews())assert.equal(g.ApexGridNativeGuard('input',{currentTarget:c}),false);
''')

    def test_broken_ea_warning_itself_yields_explicit_failure_text_not_infinite_block(self):
        self.case('''
const g=new NativeGrid(100,0);g.ApexGridBegin(request(g,6,{viewHeight:400}));bounded(g);
g.failPrimary=true;g.failWarning=true;g.ApexGridBegin(request(g,6,{viewHeight:400,scrollY:400}));
assert.equal(bounded(g).phase,'done');assert.equal(g.mGridView.mouseChildren,true);
assert.ok(g.apexGridState.presentation.failures.every(x=>x.text_diagnostic));
for(const c of g.ApexGridPoolViews())assert.equal(c.getChildByName('apexThumbnailFailure').text,'Thumbnail unavailable');
''')

    def test_sorted_selection_and_favorite_identity_publish_with_matching_texture(self):
        self.case('''
const g=new NativeGrid(100,0);g.ApexGridBegin(request(g,6,{viewHeight:400}));bounded(g);
g.mSortedIndexToDataIndex=Array.from({length:100},(_,i)=>99-i);g.mGridData.selection.add(99);
g.ApexGridNativeGuard('update',{currentTarget:g.mGridData});assert.equal(bounded(g).phase,'done');
for(let i=0;i<g.ApexGridStatus().target;i++){
 const c=g.mCells[i],sorted=g.mCellIndexToDataIndexMap[i];if(sorted<0)continue;
 const data=g.GetDataIndexOfSortedIndex(sorted);
 assert.equal(c.item.data_id,g.mGridData.items[data].data_id);
 assert.equal(c.dccFavoriteProductId,c.item.data_id);assert.equal(c.mcImage.resourceId,'thumb:'+c.item.data_id);
 assert.equal(c.ext.Selected,g.mGridData.selection.has(data));
}
''')

    def test_resize_feed_revision_reentry_rolls_back_then_rebuilds_without_blank(self):
        self.case('''
const g=new NativeGrid(100,0);g.ApexGridBegin(request(g,6,{viewHeight:400}));bounded(g);
const old=g.mCells.slice(),ids=rendered(g);let once=true;
g.hooks.resize=()=>{if(once){once=false;g.mGridData.items[0]=product('latest-after-resize');g.ApexGridNativeGuard('update',{currentTarget:g.mGridData});assert.deepEqual(rendered(g),ids);}};
g.ApexGridBegin(request(g,6,{viewHeight:400,scrollY:400}));
while(once)g.ApexGridStep(1,0);
assert.deepEqual(g.mCells,old);assert.deepEqual(rendered(g),ids);assert.equal(g.mGridView.mouseChildren,false);
assert.equal(bounded(g).phase,'done');assert.equal(g.mGridView.visible,true);assert.equal(g.mGridView.mouseChildren,true);
''')

    def test_selection_revision_during_image_wait_restarts_only_staging(self):
        self.case('''
const g=new NativeGrid(100,0);g.ApexGridBegin(request(g,6,{viewHeight:400}));bounded(g);
const old=g.mCells.slice(),ids=rendered(g);g.delayImages=true;
g.ApexGridBegin(request(g,6,{viewHeight:400,scrollY:400}));
for(let i=0;i<1000 && g.ApexGridStatus().phase!=='textures';i++)g.ApexGridStep(1,0);
g.mGridData.selection.add(50);g.ApexGridNativeGuard('selection');
g.ApexGridStep(64,0);assert.deepEqual(g.mCells,old);assert.deepEqual(rendered(g),ids);
g.delayImages=false;for(let i=0;i<1000 && g.ApexGridStatus().phase!=='done';i++){stagedReady(g);g.ApexGridStep(64,0);}
assert.equal(g.ApexGridStatus().phase,'done');
for(let i=0;i<g.ApexGridStatus().target;i++){const c=g.mCells[i],map=g.mCellIndexToDataIndexMap[i];if(map>=0)assert.equal(c.ext.Selected,map===50);}
''')


    def test_resize_throw_keeps_preceding_complete_cards_and_input_refused(self):
        self.case("""
const g=new NativeGrid(100,0);g.ApexGridBegin(request(g,6,{viewHeight:400}));bounded(g);
const old=g.mCells.slice(),ids=rendered(g);
g.hooks.resize=()=>{throw Error('native listener refused');};
g.ApexGridBegin(request(g,6,{viewHeight:400,scrollY:400}));
for(let i=0;i<2000 && g.ApexGridStatus().phase!=='cancelled';i++)g.ApexGridStep(64,0);
assert.equal(g.ApexGridStatus().phase,'cancelled');assert.deepEqual(g.mCells,old);assert.deepEqual(rendered(g),ids);
assert.equal(g.mGridView.visible,true);assert.equal(g.mGridView.mouseChildren,false);
""")

    def test_owner_generation_change_while_loading_never_publishes_stale_cards(self):
        self.case("""
const g=new NativeGrid(100,0);g.ApexGridBegin(request(g,6,{viewHeight:400}));bounded(g);
const old=g.mCells.slice(),ids=rendered(g);g.delayImages=true;
g.ApexGridBegin(request(g,6,{viewHeight:400,scrollY:400}));
for(let i=0;i<1000 && g.ApexGridStatus().phase!=='textures';i++)g.ApexGridStep(1,0);
g.lease.generation++;stagedReady(g);
for(let i=0;i<2000 && g.ApexGridStatus().phase!=='cancelled';i++)g.ApexGridStep(64,0);
assert.equal(g.ApexGridStatus().phase,'cancelled');assert.deepEqual(g.mCells,old);assert.deepEqual(rendered(g),ids);
assert.equal(g.mGridView.mouseChildren,false);
""")

    def test_legitimate_zero_results_publishes_empty_without_any_loading_placeholder(self):
        self.case("""
const g=new NativeGrid(100,0);g.ApexGridBegin(request(g,6,{viewHeight:400}));bounded(g);
g.mSortedIndexToDataIndex=[];g.ApexGridNativeGuard('update',{currentTarget:g.mGridData});
assert.equal(bounded(g).phase,'done');assert.deepEqual(rendered(g),[]);assert.equal(g.ApexGridPoolViews().length,0);
assert.equal(g.mGridView.visible,true);assert.equal(g.mGridView.mouseChildren,true);
""")


if __name__ == '__main__':
    unittest.main()
