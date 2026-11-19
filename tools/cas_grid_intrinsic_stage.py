'''Private exact-class constructor intrinsic latch; no production edits.'''
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
import cas_grid_physical as baseline
import cas_grid_pool as pool
REPLACED=('ApexGridCaptureNewCell','ApexGridNativeSetCellView','ApexGridNativeGuard','ApexGridMetrics')
ADDED=('ApexGridIntrinsicContext','ApexGridIntrinsicCapture','ApexGridIntrinsicReset')

def helpers(base=None):
    source=baseline.helpers()if base is None else base
    source=pool.edit_method(source,'ApexGridCaptureNewCell',[
        ('if(apexGridState==null || !apexGridState.armed)return;',
         'if(apexGridState==null || !apexGridState.armed)return;\n         if(ApexGridIntrinsicCapture(cell))return;')])
    source=pool.edit_method(source,'ApexGridNativeSetCellView',[
        ('apexGridState.deferredEvents++;',
         'apexGridState.deferredEvents++;\n         ApexGridIntrinsicReset(false);')])
    source=pool.edit_method(source,'ApexGridNativeGuard',[
        ('if(kind=="bounds") {if(event!=null)mCellBounds=event as Rectangle;',
         'if(kind=="bounds") {ApexGridIntrinsicReset(true);if(event!=null)mCellBounds=event as Rectangle;')])
    source=pool.edit_method(source,'ApexGridMetrics',[
        ('var s:Object=apexGridState;',
         '''var s:Object=apexGridState;
         result.intrinsic_geometry_captures=int(s.intrinsicGeometryCaptures);
         result.intrinsic_geometry_reuses=int(s.intrinsicGeometryReuses);
         result.intrinsic_geometry_resets=int(s.intrinsicGeometryResets);
         result.intrinsic_geometry_foreign=s.intrinsicGeometryForeign===true;''')])
    return source+'\n'+(ROOT/'Source/CASUi/catalog_grid_intrinsic_methods.as').read_text()

def extend_main(source):
    a,b=pool.method_extent(source,'ApexCatalogGridRequest');body=source[a:b]
    needle='stepBudgetMilliseconds:1'
    if body.count(needle)!=2 or 'var nativeCardContract:int='not in body:raise ValueError('Exact independent native Class issuer missing')
    body=body.replace(needle,needle+''',intrinsicGeometryContract:nativeCardContract,
               intrinsicGeometryClass:nativeCardContract==1 ? lease.cell_type : null,
               intrinsicGeometrySource:"exact-native-constructor-v1"''')
    return source[:a]+body+source[b:]
