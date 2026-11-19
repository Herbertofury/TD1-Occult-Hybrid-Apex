"""Retain initialized native CAS widgets across changes in visible capacity.

This postpass follows the exact V334 image adapter. It changes only reviewed
owned grid helpers and armed-only native read prefixes. It retains one native
widget class in its existing stage container, never appearance/product data.
"""
from pathlib import Path
import hashlib
import json
import os
import re

import cas_grid_transaction as grid
import cas_communication_index as comm
import cas_image_boundary_profile as image

ROOT = Path(__file__).resolve().parents[1]
TARGET = grid.TARGET
SOURCES = ('tools/cas_grid_pool.py', 'tools/CasGridPoolPatch.java',
           'tools/cas_grid_transaction.py', 'tools/CasStructuralRolesPatch.java',
           'tools/CasCommunicationIndexPatch.java')
BASELINES = {
    '00aa765a0826342498a8ef176a77d98bcd83bbec7beb5281bf953128bf647dc1':
        ('62ECC59A:00000000:12272E1AC0C1F8E2', 'f8b2a3128d9bef85dd8beddd40a38d60e5b6c1502d71fed40a32e90972f030dd',
         'de75ffcf01465cd770e48bceba0ea403ec1e91162bcae08608a75361f5452318'),
    '18544a2c85e5291d0d5becd03e275119c90dd61dff0b84132297b8e8bde5d3b4':
        ('62ECC59A:00000000:89D13757C58C2E05', 'dcb80046ba0c93b821e57c785e418ecff36c4a886b5c5dc2c9684f3e9537cacc',
         '5ed658cd9bba6b6b9cfb3d482e1ec7761f5e033e538c2a97123b2bf8e48119c6'),
}
# Both outputs pass full native ABC rollback, serialized helper/CFG checks,
# native-read argument execution and production-AS active/parked-cell fixtures.
FINALS = {
    '62ECC59A:00000000:12272E1AC0C1F8E2':
        ('0adb6e002e9ddc72db5cfbdddc8ee74e3d6053bffa63fac1575b0f2b41162199',
         '4bac87f78376d58d9c91b92cd60580d48894673fc287bc2f4f79aaf58820b4c5'),
    '62ECC59A:00000000:89D13757C58C2E05':
        ('a0f3387e15eb7380975d614f0784feed2bc64024a878697631f2795bacea371e',
         'dc053de9eb26ab5b9076213cbf5e4c20b13835f3b4fabc00533f9b1614eee056'),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def method_extent(source, name):
    hits = list(re.finditer(r'\b(?:public|private) function (?:get )?' + re.escape(name)
                           + r'\([^)]*\)\s*:\s*[\w.<>]+\s*\{', source))
    if len(hits) != 1:
        raise ValueError('Pool helper source boundary differs: ' + name)
    m = hits[0]
    end, depth = m.end(), 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return m.start(), end


def edit_method(source, name, changes):
    start, end = method_extent(source, name)
    body = source[start:end]
    for before, after in changes:
        if body.count(before) != 1:
            raise ValueError('Pool source seam differs: ' + name + ': ' + before[:70])
        body = body.replace(before, after, 1)
    return source[:start] + body + source[end:]


REPLACED_METHODS = ('ApexGridBegin', 'ApexGridDetach', 'ApexGridDiscard',
                    'ApexGridPosition', 'ApexGridBind', 'ApexGridNativeGuard',
                    'ApexTxnPlan', 'ApexTxnAdvance')

POOL_METHODS = r'''
      public function ApexGridPoolOwns() : Boolean {
         var s:Object=apexGridState;
         return s!=null && s.armed && !(s.job!=null && s.job.cancelled &&
            (s.job.reason=="dispose" || s.job.reason=="disarm"));
      }
      private function ApexGridPoolCoherent() : Boolean {
         var s:Object=apexGridState;
         return ApexGridPoolOwns() && s.job!=null && s.job.phase=="done" &&
            !s.job.dirty && !s.job.cancelled && s.job.revision==s.revision &&
            s.owner!=null && s.owner.active===true && int(s.owner.generation)==s.ownerGeneration &&
            s.feed===mGridData && s.view===mGridView && s.panel!=null && s.panel.stage!=null &&
            s.panel.mcTileList!=null && s.panel.mcTileList.mGridLayout===this;
      }
      private function ApexGridPoolSlot(index:int) : Boolean {
         var s:Object=apexGridState;
         if(s==null || s.job==null || index<0 || index>=s.job.target || index>=mCells.length)return false;
         var cell:Object=mCells[index];
         return s.ready[cell]===s.job.generation && mCellIndexToDataIndexMap[index]>=0 &&
            cell.parent===mGridView && cell.visible;
      }
      public function ApexGridPoolViews() : Vector.<IView> {
         var result:Vector.<IView> = new Vector.<IView>();
         if(!ApexGridPoolCoherent())return result;
         var s:Object=apexGridState;var j:Object=s.job;
         for(var i:int=0;i<j.target && i<mCells.length;i++) {
            var cell:Object=mCells[i];
            if(ApexGridPoolSlot(i))result.push(cell as IView);
         }
         return result;
      }
      public function ApexGridPoolDisplays() : Vector.<DisplayObject> {
         var result:Vector.<DisplayObject> = new Vector.<DisplayObject>();
         if(!ApexGridPoolCoherent())return result;
         var s:Object=apexGridState;var j:Object=s.job;
         for(var i:int=0;i<j.target && i<mCells.length;i++) {
            var cell:Object=mCells[i];
            if(ApexGridPoolSlot(i))result.push(cell as DisplayObject);
         }
         return result;
      }
      public function ApexGridPoolNeighbor(cell:IView,direction:int) : IView {
         if(!ApexGridPoolCoherent())return null;
         var s:Object=apexGridState;var j:Object=s.job;
         var limit:int=Math.min(j.target,mCells.length);
         var at:int=cell==null ? (direction>0 ? -1 : limit) : mCells.indexOf(cell);
         if(cell!=null && (at<0 || at>=limit || s.ready[cell]!==j.generation))return null;
         for(var i:int=at+direction;i>=0 && i<limit;i+=direction) {
            var candidate:Object=mCells[i];
            if(ApexGridPoolSlot(i))return candidate as IView;
         }
         return null;
      }
      public function ApexGridPoolMap(index:int) : int {
         if(!ApexGridPoolCoherent() || index<0 || index>=apexGridState.job.target || index>=mCells.length)
            return -1;
         return ApexGridPoolSlot(index) ? mCellIndexToDataIndexMap[index] : -1;
      }
      public function ApexGridPoolDataIndex(index:int) : int {
         if(index<0 || index>=GetNumItems())return -1;
         return mSortedIndexToDataIndex ? int(mSortedIndexToDataIndex[index]) : index;
      }
      private function ApexGridPoolPark(cell:Object,slot:int) : void {
         var s:Object=apexGridState;
         if(s.poolFlags[cell]==null)
            s.poolFlags[cell]={mouse:cell.mouseEnabled,children:cell.mouseChildren};
         cell.visible=false;cell.mouseEnabled=false;cell.mouseChildren=false;
         delete s.ready[cell];mCellIndexToDataIndexMap[slot]=-1;
         if("dccFavoriteProductId" in cell)cell.dccFavoriteProductId=null;
      }
      private function ApexGridPoolRestore(cell:Object) : void {
         var flags:Object=apexGridState.poolFlags[cell];
         if(flags!=null) {
            cell.mouseEnabled=Boolean(flags.mouse);cell.mouseChildren=Boolean(flags.children);
            delete apexGridState.poolFlags[cell];
         }
      }
'''


def transform_helpers(source):
    source = edit_method(source, 'ApexGridBegin', [
        ('ready:new Dictionary(true),retireAll:',
         'ready:new Dictionary(true),poolFlags:prior!=null && prior.view===mGridView ? prior.poolFlags : new Dictionary(true),retireAll:')])
    source = edit_method(source, 'ApexGridDetach', [
        ('delete apexGridState.ready[cell];',
         'delete apexGridState.ready[cell];delete apexGridState.poolFlags[cell];delete apexGridState.intrinsics[cell];')])
    source = edit_method(source, 'ApexGridDiscard', [
        ('delete apexGridState.ready[cell];',
         'delete apexGridState.ready[cell];delete apexGridState.poolFlags[cell];delete apexGridState.intrinsics[cell];')])
    source = edit_method(source, 'ApexGridPosition', [
        ('var marker:Object=',
         'if(j.index>=j.target) {ApexGridPoolPark(cell,j.index);return;}\n         var marker:Object=')])
    source = edit_method(source, 'ApexGridBind', [
        ('if(item!=null) {\n            started=getTimer();',
         'if(item!=null) {\n            ApexGridPoolRestore(cell);\n            started=getTimer();'),
        ('cell.visible=item!=null;',
         'if(item==null) {ApexGridPoolPark(cell,j.index);sortedIndex=-1;}\n         else cell.visible=true;')])
    source = edit_method(source, 'ApexGridNativeGuard', [
        ('if(kind=="redraw") {',
         'if(kind=="redraw") {\n            if(event!=null && event.currentTarget!=null && s.poolFlags[event.currentTarget]!=null)return true;')])
    source = edit_method(source, 'ApexTxnPlan', [
        ('j.target=j.plan.target;',
         'if(!isFinite(j.plan.target) || j.plan.target<0 || j.plan.target>int.MAX_VALUE)throw new Error("Native grid index range exceeded");\n         j.target=j.plan.target;')])
    source = edit_method(source, 'ApexTxnAdvance', [
        ('if(apexGridState.retireAll || a.ApexGridCells.length>j.target ||\n               j.target>0 && j.pendingCell!=null && a.ApexGridCells.length>=j.target) {',
         'if(apexGridState.retireAll) {'),
        ('if(j.target==0){j.index=0;j.phase="position";return false;}',
         'if(a.ApexGridCells.length>=j.target) {\n                  j.lastOperation="discardConstruct";a.ApexGridDiscard(j.pendingCell);j.pendingCell=null;j.pendingAttached=false;return true;\n               }'),
        ('if(a.ApexGridCells.length>j.target || apexGridState.retireAll && a.ApexGridCells.length>0) {',
         'if(apexGridState.retireAll && a.ApexGridCells.length>0) {'),
        ('a.ApexGridCellsY[slot]=y;', 'a.ApexGridCellsY[slot]=slot<j.target ? y : 0;'),
        ('a.ApexGridMap[slot]=j.plan.first+slot;',
         'a.ApexGridMap[slot]=slot<j.target ? j.plan.first+slot : -1;'),
        ('if(j.index>=a.ApexGridCells.length){j.phase="publish";return false;}',
         'if(j.index>=j.target){j.phase="publish";return false;}')])
    return source + '\n' + POOL_METHODS


def inject(source):
    helpers = transform_helpers(grid.ADAPTER_METHODS + '\n' + grid.CORE_METHODS)
    original = grid.inject(source)
    return original.replace(grid.ADAPTER_METHODS + '\n' + grid.CORE_METHODS, helpers, 1)


def adapt(original_swf, final_v334_swf, ffdec, work):
    original_swf, final_v334_swf, ffdec, work = map(Path, (original_swf, final_v334_swf, ffdec, work))
    expected = BASELINES.get(digest(final_v334_swf.read_bytes()))
    if expected is None or digest(original_swf.read_bytes()) != image.RAW_PROVIDERS[expected[0]]:
        raise ValueError('Unsupported original/exact V334 pool provider pair.')
    pins = {n: digest((ROOT / n).read_bytes()) for n in SOURCES}
    work.mkdir(parents=True, exist_ok=True)
    private = work / 'private-source'
    comm.run([ffdec, '-selectclass', TARGET, '-export', 'script', private, original_swf], work / 'export.log')
    source = private / 'scripts/olympus/layout/RecyclingGridLayout.as'
    owned = work / 'RecyclingGridLayout.as'
    owned.write_text(inject(source.read_text(encoding='utf-8-sig')), encoding='utf-8')
    compiled = work / 'compiled.swf'
    comm.run([ffdec, '-importAssets', 'yes,local', '-replace', final_v334_swf, compiled,
              TARGET, owned], work / 'ffdec.log')
    classes = work / 'classes'; classes.mkdir(exist_ok=True)
    jar = ffdec.with_name('ffdec.jar')
    comm.run(['javac', '-cp', jar, '-d', classes, ROOT / 'tools/CasStructuralRolesPatch.java',
              ROOT / 'tools/CasCommunicationIndexPatch.java', ROOT / 'tools/CasGridPoolPatch.java'], work / 'javac.log')
    abc, proof = work / 'retained.abc', work / 'proof.json'
    comm.run(['java', '-cp', str(jar) + os.pathsep + str(classes), 'CasGridPoolPatch',
              final_v334_swf, compiled, abc, proof], work / 'transplant.log')
    data = abc.read_bytes(); report = json.loads(proof.read_text())
    if report.get('ok') is not True or report.get('abc_sha256') != digest(data):
        raise ValueError('Pool retained ABC proof differs.')
    if pins != {n: digest((ROOT / n).read_bytes()) for n in SOURCES}:
        raise ValueError('Pool sources changed during compilation; discard output.')
    report['source_sha256'] = pins
    report['helper_source_sha256'] = digest(transform_helpers(grid.ADAPTER_METHODS + '\n' + grid.CORE_METHODS).encode())
    return data, report


def chain_adapter(previous_adapter, proof, final_swf):
    from cas_ui_build import tags, unpack
    expected = BASELINES.get(proof.get('baseline_swf_sha256')) if isinstance(proof, dict) else None
    required = ('whole_abc_rollback_verified', 'native_read_projection_verified',
                'unarmed_original_native_flow_verified', 'protected_namespace_bindings_verified',
                'serialized_owned_bodies_verified', 'all_other_bodies_retained')
    counts = {'replaced_owned_bodies':len(REPLACED_METHODS),
              'guarded_native_read_bodies':8,'appended_methods':10,'appended_fields':0}
    if expected is not None:
        counts.update(dict(zip(('baseline_method_info_count','baseline_method_body_count','unchanged_baseline_bodies'),
            (9259,8993,8977) if expected[0].endswith('12272E1AC0C1F8E2') else (8544,8289,8273))))
    if (expected is None or proof.get('ok') is not True or
            any(proof.get(k) is not True for k in required) or
            proof.get('provider_resource_tgi') != expected[0] or
            proof.get('baseline_abc_sha256') != expected[1] or
            any(type(proof.get(k)) is not int or proof[k]!=v for k,v in counts.items()) or
            proof.get('runtime_qualified') is not False or
            proof.get('hitch_free_claimed') is not False):
        raise ValueError('Pool contract differs.')
    if (not isinstance(previous_adapter, dict) or previous_adapter.get('patched_resource_sha256') != proof['baseline_swf_sha256']):
        raise ValueError('Pool prior image stage differs.')
    if comm.contract_digest(previous_adapter) != expected[2]:
        raise ValueError('Pool exact historical image contract differs.')
    if (proof.get('source_sha256') != {n: digest((ROOT / n).read_bytes()) for n in SOURCES} or
            proof.get('helper_source_sha256') != digest(transform_helpers(grid.ADAPTER_METHODS + '\n' + grid.CORE_METHODS).encode())):
        raise ValueError('Pool source pins differ.')
    if FINALS.get(expected[0]) != (digest(final_swf), proof.get('abc_sha256')):
        raise ValueError('Pool final bytes differ from reviewed output.')
    abc = [t[3] for t in tags(unpack(final_swf)[1]) if t[0] == 82]
    if len(abc) != 1 or digest(abc[0][abc[0].index(b'\0', 4) + 1:]) != proof.get('abc_sha256'):
        raise ValueError('Pool final ABC differs.')
    return dict(base_resource_sha256=previous_adapter['base_resource_sha256'],
                patched_resource_sha256=digest(final_swf),
                previous_stage_sha256=comm.contract_digest(previous_adapter),
                postproof_sha256=comm.contract_digest(proof),
                previous_stage_adapter=json.loads(json.dumps(previous_adapter)),
                grid_pool_contract=json.loads(json.dumps(proof)))


def verify_adapter(adapter, final_swf):
    if not isinstance(adapter, dict) or chain_adapter(adapter.get('previous_stage_adapter'),
            adapter.get('grid_pool_contract'), final_swf) != adapter:
        raise ValueError('Pool final proof differs.')
    return True
