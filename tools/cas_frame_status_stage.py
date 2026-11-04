"""Private explicit frame APIs; existing public Begin/Status/Step are retained."""
from pathlib import Path
import cas_grid_logical_bank as previous,cas_grid_pool as pool
ROOT=Path(__file__).resolve().parents[1]
REPLACED=('ApexGridMetrics',)
ADDED=('ApexGridExpireMeasurement','ApexGridFrameStatusEffects','ApexGridBeginFrame','ApexGridPendingFrame','ApexGridGeometryFrame')
MAIN_REPLACED=('ApexCatalogGridFrame','ApexCatalogGridPending','ApexCardIncrementalApply')
MAIN_ADDED=('ApexCatalogFrameStatusAvailable',)

def helpers():
    source=previous.helpers();a,b=pool.method_extent(source,'ApexGridMetrics');metrics=source[a:b]
    start=metrics.index('         if(s.owner==null');end=metrics.index('         result.measured_height',start);expiry=metrics[start:end]
    metrics=metrics[:start]+'         ApexGridExpireMeasurement(s);\n'+metrics[end:]
    source=source[:a]+metrics+source[b:]
    expire='      private function ApexGridExpireMeasurement(s:Object) : void {\n'+expiry+'      }\n'
    a,b=pool.method_extent(source,'ApexGridBegin');begin=source[a:b]
    begin=begin.replace('public function ApexGridBegin(request:Object) : Object','public final function ApexGridBeginFrame(request:Object) : void',1)
    if begin.count('return ApexGridStatus();')!=3:raise ValueError('Exact Begin status-return inventory differs')
    begin=begin.replace('return ApexGridStatus();','ApexGridFrameStatusEffects();return;')
    return source+'\n'+expire+'\n'+begin+'\n'+(ROOT/'Source/CASUi/catalog_frame_status_methods.as').read_text()

def extend_main(source):
    source=pool.edit_method(source,'ApexCatalogGridFrame',[
       ('if(s.frame<int.MAX_VALUE)s.frame++;s.last=s.grid.ApexGridBegin(request);',
        'if(s.frame<int.MAX_VALUE)s.frame++;\n            if(ApexCatalogFrameStatusAvailable(s.grid))s.grid.ApexGridBeginFrame(request);\n            else s.last=s.grid.ApexGridBegin(request);')])
    a,b=pool.method_extent(source,'ApexCatalogGridPending');body=source[a:b]
    seam='         var status:Object=grid.ApexGridStatus();'
    if body.count(seam)!=1:raise ValueError('Exact scalar pending seam differs')
    body=body.replace(seam,'''         if(ApexCatalogFrameStatusAvailable(grid)) {
            var pending:Boolean=grid.ApexGridPendingFrame();
            return s.lease==null || s.lease.phase!="bound" || s.lease.active!==true || pending;
         }
'''+seam)
    source=source[:a]+body+source[b:]
    source=pool.edit_method(source,'ApexCardIncrementalApply',[
       ('var native:Object=grid.ApexGridStatus();',
        'var native:Object=ApexCatalogFrameStatusAvailable(grid) ? grid.ApexGridGeometryFrame() : grid.ApexGridStatus();')])
    return source+'''\n
      private function ApexCatalogFrameStatusAvailable(grid:Object) : Boolean {
         if(grid==null)return false;
         var name:String=flash.utils.getQualifiedClassName(grid);
         if(name!=="olympus.layout::RecyclingGridLayout" && name!=="olympus.layout::SelectableRecyclingGridLayout")return false;
         return "ApexGridBeginFrame" in grid && grid.ApexGridBeginFrame is Function &&
            "ApexGridPendingFrame" in grid && grid.ApexGridPendingFrame is Function &&
            "ApexGridGeometryFrame" in grid && grid.ApexGridGeometryFrame is Function;
      }
'''
