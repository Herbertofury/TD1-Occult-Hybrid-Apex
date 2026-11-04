"""Execute the production pool AS helpers against the native grid fixture."""
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]
import cas_grid_pool as pool
import cas_grid_transaction as grid
from test_cas_grid_transaction import NATIVE_MOCK


def javascript():
    source = pool.transform_helpers(grid.ADAPTER_METHODS + '\n' + grid.CORE_METHODS)
    functions = []
    for m in re.finditer(r'(?:public|private) function (?:(get) )?(\w+)\(([^)]*)\)\s*:\s*[\w.<>]+\s*\{', source):
        end, depth = m.end(), 1
        while depth:
            depth += (source[end] == '{') - (source[end] == '}')
            end += 1
        body = source[m.end():end - 1]
        body = re.sub(r'\b(var\s+\w+)\s*:\s*[\w.*<>]+', r'\1', body)
        body = re.sub(r'catch\((\w+):(?:Error|\*)\)', r'catch(\1)', body)
        body = re.sub(r'\s+as\s+\w+', '', body)
        body = re.sub(r'\bis\b', 'instanceof', body)
        body = re.sub(r'new Vector\.<\w+>\(\)', '[]', body)
        body = re.sub(r'new Vector\.<\w+>\(([^)]*)\)', r'makeVector(\1)', body)
        params = re.sub(r':\s*[\w.<>]+', '', m.group(3))
        fn = 'function(' + params + '){with(this){' + body + '}}'
        if m.group(1):
            functions.append("Object.defineProperty(NativeGrid.prototype,'" + m.group(2) + "',{get:" + fn + '});')
        else:
            functions.append('NativeGrid.prototype.' + m.group(2) + '=' + fn + ';')
    if len(functions) != 55:
        raise AssertionError('Expected exact original45+pool10 actual AS methods: ' + str(len(functions)))
    return '\n'.join(functions)


@unittest.skipUnless(shutil.which('node'), 'Node required for actual production AS fixture')
class NativePoolExecutionTests(unittest.TestCase):
    def case(self, code):
        result = subprocess.run(['node', '-'], input=NATIVE_MOCK + '\nint.MAX_VALUE=2147483647;\n' + javascript() + code,
                                capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_shrink_regrow_reuses_initialized_staged_controls_without_attach_or_construct(self):
        self.case('''
const g=new NativeGrid(436,0);g.ApexGridBegin(request(g,12,{viewHeight:400}));drive(g);
assert.equal(g.mCells.length,108);const controls=g.mCells.slice();const initial=g.calls.length;
g.ApexGridBegin(request(g,6,{viewHeight:400}));drive(g);
assert.equal(g.ApexGridStatus().target,54);assert.equal(g.mCells.length,108);
assert.equal(g.ApexGridPoolViews().length,54);assert.equal(g.ApexGridPoolDisplays().length,54);
for(let i=54;i<108;i++) {const c=g.mCells[i];assert.equal(c.parent,g.mGridView);assert.equal(c.visible,false);assert.equal(c.mouseEnabled,false);assert.equal(c.mouseChildren,false);assert.equal(g.mCellIndexToDataIndexMap[i],-1);assert.equal(g.ApexGridPoolMap(i),-1);assert.equal(g.ApexGridNativeGuard('input',{currentTarget:c}),true);}
g.ApexGridBegin(request(g,12,{viewHeight:400}));drive(g);
assert.deepEqual(g.mCells,controls);assert.equal(g.ApexGridPoolViews().length,108);
assert.equal(g.calls.slice(initial).filter(x=>['construct','attach','detach'].includes(x)).length,0);
for(const c of controls){assert.equal(c.visible,true);assert.equal(c.mouseEnabled,true);assert.equal(c.mouseChildren,true);}
''')

    def test_initial_growth_attaches_each_new_control_once_then_reuses_high_water(self):
        self.case('''
const g=new NativeGrid(436,0);g.ApexGridBegin(request(g,6,{viewHeight:400}));drive(g);
assert.equal(g.mCells.length,54);g.ApexGridBegin(request(g,12,{viewHeight:400}));drive(g);
assert.equal(g.mCells.length,108);assert.equal(g.calls.filter(x=>x==='attach').length,108);
assert.equal(g.calls.filter(x=>x==='construct').length,108);assert.equal(g.calls.filter(x=>x==='detach').length,0);
const n=g.calls.length;g.ApexGridBegin(request(g,6,{viewHeight:400}));drive(g);g.ApexGridBegin(request(g,12,{viewHeight:400}));drive(g);
assert.equal(g.calls.slice(n).filter(x=>x==='attach'||x==='construct'||x==='detach').length,0);
''')

    def test_published_native_reads_work_outside_frame_only_validation_and_never_authorize_a_write(self):
        self.case('''
const g=new NativeGrid(100,0);let inFrame=true;
g.ApexGridBegin(request(g,6,{viewHeight:400,validate:owner=>{g.validations++;return inFrame&&owner===g.lease&&owner.active===true;}}));drive(g);
inFrame=false;g.lease.frame_validated=false;let validations=g.validations;
assert.equal(g.ApexGridValid(g.apexGridState.identity),false);validations=g.validations;
assert.equal(g.ApexGridPoolViews().length,54);assert.equal(g.ApexGridPoolDisplays().length,54);
assert.equal(g.ApexGridPoolNeighbor(null,1),g.mCells[0]);assert.equal(g.ApexGridPoolNeighbor(null,-1),g.mCells[53]);assert.equal(g.ApexGridPoolMap(53),53);
assert.equal(g.validations,validations);assert.equal(g.inputValidations,0);
assert.equal(g.ApexGridNativeGuard('input',{currentTarget:g.mCells[0]}),false);assert.equal(g.inputValidations,1);
g.apexGridState.inputValidate=()=>{g.inputValidations++;return false;};
assert.equal(g.ApexGridNativeGuard('input',{currentTarget:g.mCells[0]}),true);assert.equal(g.inputValidations,2);assert.equal(g.lease.active,false);
assert.deepEqual(g.ApexGridPoolViews(),[]);assert.equal(g.ApexGridPoolMap(0),-1);assert.equal(g.ApexGridPoolNeighbor(null,1),null);
''')

    def test_readonly_structural_retirement_blocks_stale_owner_generation_feed_view_and_panel(self):
        self.case('''
const g=new NativeGrid(100,0);g.ApexGridBegin(request(g,6,{viewHeight:400}));drive(g);
function blocked(){assert.deepEqual(g.ApexGridPoolViews(),[]);assert.deepEqual(g.ApexGridPoolDisplays(),[]);assert.equal(g.ApexGridPoolMap(0),-1);assert.equal(g.ApexGridPoolNeighbor(null,1),null);}
const old=g.lease.generation;g.lease.generation++;blocked();g.lease.generation=old;
const feed=g.mGridData;g.mGridData=new SelectableArrayDataFeed(100);blocked();g.mGridData=feed;
const view=g.mGridView;g.mGridView=new DisplayObject();blocked();g.mGridView=view;
const stage=g.panel.stage;g.panel.stage=null;blocked();g.panel.stage=stage;
g.panel.mcTileList.mGridLayout={};blocked();g.panel.mcTileList.mGridLayout=g;
assert.equal(g.ApexGridPoolViews().length,54);assert.equal(g.inputValidations,0);
''')

    def test_no_match_keeps_pool_hidden_unmapped_and_clear_freshly_rebinds(self):
        self.case('''
const g=new NativeGrid(40,0);g.ApexGridBegin(request(g,6,{viewHeight:400}));drive(g);
const cells=g.mCells.slice();const n=g.calls.length;g.mSortedIndexToDataIndex=[];g.ApexGridNativeGuard('sort',{currentTarget:g.mGridData,mIndicesArray:[]});drive(g);
assert.equal(g.ApexGridStatus().target,0);assert.equal(g.ApexGridPoolViews().length,0);assert.equal(g.mCells.length,42);
assert.equal(g.ApexGridPoolNeighbor(null,1),null);assert.equal(g.ApexGridPoolNeighbor(null,-1),null);
for(const c of cells){assert.equal(c.visible,false);assert.equal(c.mouseEnabled,false);assert.equal(c.mouseChildren,false);}
assert.ok(g.mCellIndexToDataIndexMap.every(i=>i===-1));
g.mSortedIndexToDataIndex=null;g.ApexGridNativeGuard('sort',{currentTarget:g.mGridData,mIndicesArray:null});drive(g);
assert.deepEqual(g.mCells,cells);assert.equal(g.ApexGridPoolViews().length,40);
assert.equal(g.calls.slice(n).filter(x=>x==='construct'||x==='attach'||x==='detach').length,0);
assert.equal(g.ApexGridPoolDataIndex(-1),-1);assert.equal(g.ApexGridPoolDataIndex(40),-1);
''')

    def test_partial_job_exposes_no_cells_and_parked_redraw_stays_idle(self):
        self.case('''
const g=new NativeGrid(100,0);g.ApexGridBegin(request(g,12,{viewHeight:400}));
while(g.ApexGridStatus().phase!=='done'){g.ApexGridStep(1,0);if(g.ApexGridStatus().phase!=='done'){assert.deepEqual(g.ApexGridPoolViews(),[]);assert.deepEqual(g.ApexGridPoolDisplays(),[]);assert.equal(g.ApexGridPoolNeighbor(null,1),null);assert.equal(g.ApexGridPoolMap(0),-1);}}
g.ApexGridBegin(request(g,6,{viewHeight:400}));drive(g);const parked=g.mCells[80];const n=g.calls.length;
for(let i=0;i<10;i++) {assert.equal(g.ApexGridNativeGuard('redraw',{currentTarget:parked}),true);assert.equal(g.ApexGridNeedsWork(),false);}
assert.equal(g.calls.length,n);assert.equal(g.ApexGridPoolNeighbor(g.mCells[53],1),null);assert.equal(g.ApexGridPoolNeighbor(parked,-1),null);
assert.equal(g.ApexGridPoolNeighbor(null,-1),g.mCells[53]);assert.equal(g.ApexGridPoolNeighbor(g.mCells[1],-1),g.mCells[0]);
''')

    def test_mouse_flags_restore_actual_values_and_selected_sorted_identity_survives(self):
        self.case('''
const g=new NativeGrid(100,0);g.ApexGridBegin(request(g,12,{viewHeight:400}));drive(g);
const c=g.mCells[80];c.mouseEnabled=false;c.mouseChildren=true;
g.ApexGridBegin(request(g,6,{viewHeight:400}));drive(g);
g.mSortedIndexToDataIndex=Array.from({length:100},(_,i)=>99-i);g.mGridData.selection.add(19);
g.ApexGridNativeGuard('sort',{currentTarget:g.mGridData,mIndicesArray:g.mSortedIndexToDataIndex});
g.ApexGridBegin(request(g,12,{viewHeight:400}));drive(g);
assert.equal(g.mCells[80],c);assert.equal(c.item.data_id,'item-19');assert.equal(c.ext.Selected,true);
assert.equal(c.mouseEnabled,false);assert.equal(c.mouseChildren,true);assert.equal(g.ApexGridPoolDataIndex(80),19);
assert.equal(g.ApexGridNativeGuard('input',{currentTarget:c}),false);assert.equal(g.inputValidations,1);
''')

    def test_new_owner_feed_outfit_uses_fresh_lease_and_every_active_slot_rebinds(self):
        self.case('''
const g=new NativeGrid(80,0);g.ApexGridBegin(request(g,12,{viewHeight:400}));drive(g);const cells=g.mCells.slice();const n=g.calls.length;
g.lease.active=false;g.mGridData=new SelectableArrayDataFeed(80);g.mGridData.owner=g;g.mGridData.items=g.mGridData.items.map((p,i)=>product('other-member-'+i));
g.lease={active:true,generation:2,frame_validated:true};g.ApexGridBegin(request(g,12,{viewHeight:400}));drive(g);if(g.ApexGridStatus().phase!=='done')drive(g);
assert.equal(g.ApexGridStatus().phase,'done');assert.deepEqual(g.mCells,cells);
for(const c of g.ApexGridPoolViews())assert.ok(c.item.data_id.startsWith('other-member-'));
assert.equal(g.calls.slice(n).filter(x=>x==='draw').length,80);assert.equal(g.calls.slice(n).filter(x=>x==='attach'||x==='construct'||x==='detach').length,0);
assert.equal(g.ApexGridNativeGuard('input',{currentTarget:g.mCells[79]}),false);
''')

    def test_class_replacement_retires_all_old_controls_and_view_replacement_retires_old_stage(self):
        self.case('''
for(const replaceView of [false,true]) {
 const g=new NativeGrid(40,0);g.ApexGridBegin(request(g,6,{viewHeight:400}));drive(g);const old=g.mCells.slice();
 if(replaceView){g.lease.active=false;g.lease={active:true,generation:2,frame_validated:true};g.mGridView=new DisplayObject();g.mGridView.owner=g;g.ApexGridBegin(request(g,6,{viewHeight:400}));drive(g);if(g.ApexGridStatus().phase!=='done')drive(g);}
 else {g.ApexGridNativeSetCellView(OtherCell,new Margin(),true);drive(g);}
 assert.equal(g.ApexGridStatus().phase,'done');assert.ok(old.every(c=>c.parent===null));assert.ok(g.mCells.every(c=>!old.includes(c)));
 if(!replaceView)assert.ok(g.mCells.every(c=>c instanceof OtherCell));g.invariant();
}
''')

    def test_terminal_failure_revokes_entire_pool_without_replay_or_teardown_callbacks(self):
        self.case('''
for(const reason of ['error-abandon','dispose']) {
 const g=new NativeGrid(100,0);g.ApexGridBegin(request(g,12,{viewHeight:400}));drive(g);g.ApexGridBegin(request(g,6,{viewHeight:400}));g.ApexGridStep(1,0);
 const n=g.calls.length;g.ApexGridCancel(reason);assert.equal(g.calls.length,n);assert.equal(g.ApexGridNeedsWork(),false);
 assert.equal(g.ApexGridNativeGuard('input',{currentTarget:g.mCells[0]}),true);assert.equal(g.mbSuppressUpdates,false);
 if(reason==='error-abandon'){assert.deepEqual(g.ApexGridPoolViews(),[]);assert.equal(g.ApexGridPoolOwns(),true);}
 else assert.equal(g.ApexGridPoolOwns(),false);
 for(let i=0;i<4;i++)g.ApexGridStep(64,0);assert.equal(g.calls.length,n);g.invariant();
}
''')

    def test_cancelled_constructor_attach_and_draw_keep_vector_shape_and_no_partial_publication(self):
        self.case('''
for(const phase of ['construct','attach','draw']) {
 const g=new NativeGrid(80,0);g.ApexGridBegin(request(g,6,{viewHeight:400}));let hit=false;
 g.hooks[phase]=()=>{if(!hit){hit=true;g.lease.active=false;g.ApexGridCancel('error-abandon');}};
 for(let i=0;!hit;i++){g.ApexGridStep(1,0);assert.ok(i<1000);}
 assert.equal(g.ApexGridStatus().cancelled,true);assert.equal(g.mGridView.visible,false);assert.deepEqual(g.ApexGridPoolViews(),[]);g.invariant();
}
''')


class PoolSourceBoundaryTests(unittest.TestCase):
    def test_source_transform_requires_exact_native_adapter_seams(self):
        source = grid.ADAPTER_METHODS + '\n' + grid.CORE_METHODS
        self.assertIn('ApexGridPoolPark', pool.transform_helpers(source))
        with self.assertRaisesRegex(ValueError, 'source seam differs'):
            pool.transform_helpers(source.replace('a.ApexGridMap[slot]=j.plan.first+slot;', 'changed();'))

    def test_only_two_authenticated_original_and_image_provider_pairs_are_allowed(self):
        self.assertEqual(len(pool.BASELINES), 2)
        self.assertTrue(all('3FFE' not in row[0] for row in pool.BASELINES.values()))
        self.assertEqual(len(pool.REPLACED_METHODS), 8)


@unittest.skipUnless(shutil.which('javac') and all((ROOT / ('.work/v335-grid-pool-'+name+'/final.swf')).is_file()
    for name in ('canonical','donor')), 'Private final providers and JDK required')
class PoolSerializedNativeReadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='apex-grid-pool-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.jar=ROOT / '.work/research/ffdec/ffdec.jar'
        result=subprocess.run(['javac','-cp',str(cls.jar),'-d',cls.temp.name,
            str(ROOT/'tools/CasStructuralRolesPatch.java'), str(ROOT/'tools/CasCommunicationIndexPatch.java'),
            str(ROOT/'tools/CasGridPoolPatch.java'),str(ROOT/'tests/CasGridPoolBytecodeFixtures.java')],
            capture_output=True,text=True,timeout=60)
        if result.returncode:raise AssertionError(result.stdout+result.stderr)

    def test_both_serialized_providers_execute_native_read_arguments_and_refuse_corruption(self):
        for name in ('canonical','donor'):
            with self.subTest(provider=name):
                result=subprocess.run(['java','-cp',str(self.jar)+os.pathsep+self.temp.name,
                    'CasGridPoolBytecodeFixtures',str(ROOT/('.work/v334-image-profile-'+name+'/final.swf')),
                    str(ROOT/('.work/v335-grid-pool-'+name+'/final.swf'))],
                    capture_output=True,text=True,timeout=90)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr[-4000:])
                self.assertEqual(result.stdout.count('PASS '),26)


if __name__ == '__main__':
    unittest.main()
