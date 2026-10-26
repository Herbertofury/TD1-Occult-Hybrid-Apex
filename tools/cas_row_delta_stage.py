"""Exact owned product-row reuse and newest-only native scroll scheduling."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
import cas_grid_featured as previous
import cas_grid_pool as pool

REPLACED=('ApexTxnRequest','ApexGridStep','ApexGridReady','ApexGridPresentationPublish','ApexGridPresentationRollback','ApexGridCancel','ApexGridMetrics','ApexGridPoolCoherent','ApexGridNativeGuard')
ADDED=('ApexGridDeltaCapable','ApexGridDeltaCapture','ApexGridDeltaCurrent','ApexGridDeltaQueue','ApexGridDeltaLatest','ApexGridDeltaRetarget','ApexGridDeltaTexture','ApexGridDeltaBorrow','ApexGridDeltaRestore','ApexGridDeltaPublish','ApexGridDeltaAdvance','ApexGridDeltaStep')


def helpers(base=None):
    source=previous.helpers()if base is None else base
    source=pool.edit_method(source,'ApexTxnRequest',[
        ('if(ApexGridScrollOnlyQueue(j,r)) {j.coalesced++;return;}',
         'if(ApexGridScrollOnlyQueue(j,r)) {j.coalesced++;return;}\n         if(ApexGridDeltaQueue(j,r)) {j.coalesced++;return;}')])
    source=pool.edit_method(source,'ApexGridStep',[
        ('// This capability uses only a provider-local elapsed budget.',
         'if(s.delta!=null)return ApexGridDeltaStep(maxOps);\n         // This capability uses only a provider-local elapsed budget.')])
    source=pool.edit_method(source,'ApexGridReady',[
        ('s.ready[cell]=item!=null ? generation : -1;j.boundCell=null;',
         'ApexGridDeltaCapture(cell,generation,selected);\n         s.ready[cell]=item!=null ? generation : -1;j.boundCell=null;')])
    source=pool.edit_method(source,'ApexGridPresentationPublish',[
        ('presentation.expected=new Dictionary(true);presentation.images=new Dictionary(true);presentation.working=false;presentation.published=true;',
         '''if(ApexGridDeltaCapable() && presentation.stageBindingGeneration===j.generation) {
               presentation.committedBindings=presentation.stageBindings;presentation.committedExpected=presentation.expected;
            } else {presentation.committedBindings=null;presentation.committedExpected=null;}
            presentation.stageBindings=null;
            presentation.expected=new Dictionary(true);presentation.images=new Dictionary(true);presentation.working=false;presentation.published=true;''')])
    source=pool.edit_method(source,'ApexGridPresentationRollback',[
        ('var s:Object=apexGridState;if(s==null)return;var p:Object=s.presentation;',
         'var s:Object=apexGridState;if(s==null)return;if(s.delta!=null){ApexGridDeltaRestore(s.delta);return;}var p:Object=s.presentation;')])
    source=pool.edit_method(source,'ApexGridCancel',[
        ('if(apexGridState==null)return {phase:"unarmed",active:false};',
         'if(apexGridState==null)return {phase:"unarmed",active:false};\n         if(apexGridState.delta!=null)ApexGridDeltaRestore(apexGridState.delta);')])
    source=pool.edit_method(source,'ApexGridMetrics',[
        ('var s:Object=apexGridState;',
         '''var s:Object=apexGridState;
         result.row_delta_active=s.delta!=null;
         result.row_delta_phase=s.delta==null ? "" : String(s.delta.phase);
         result.row_delta_last_error=s.deltaLastError==null ? "" : String(s.deltaLastError);''')])
    source=pool.edit_method(source,'ApexGridPoolCoherent',[
        ('s.job!=null && s.job.phase=="done" &&',
         's.job!=null && (s.job.phase=="done" || s.job.phase=="row-delta" && s.job.publishing && s.delta!=null && s.delta.physicalReady===true) &&')])
    source=pool.edit_method(source,'ApexGridNativeGuard',[
        ('if(s.request!=null && s.request.scrollOnlyPositionContract===1 && j.phase=="scroll-only"',
         '''if(j.phase=="row-delta" && s.delta!=null && event!=null && s.delta.oldReady[event.currentTarget]===s.delta.oldGeneration) {
               s.revision++;ApexTxnNotify(j,"update");return true;
            }
            if(s.request!=null && s.request.scrollOnlyPositionContract===1 && j.phase=="scroll-only"'''),
        ('Number(event.mRect.y)!=-Number(j.plan==null?0:j.plan.scrollY)',
         'Number(event.mRect.y)!=-Number(s.delta!=null ? j.desired.scrollY : (j.plan==null?0:j.plan.scrollY))')])
    return source+'\n'+(ROOT/'Source/CASUi/catalog_row_delta_methods.as').read_text()


def extend_main(source):
    a,b=pool.method_extent(source,'ApexCatalogGridRequest');body=source[a:b]
    before='         if(view==null || list.mSlider==null'
    if body.count(before)!=1:raise ValueError('Exact current Main geometry admission seam differs')
    body=body.replace(before,'''         var rowDeltaContract:int=nativeCardContract==1 &&
            (lease.panel_kind=="clothing" || lease.panel_kind=="body" || lease.panel_kind=="face" || lease.panel_kind=="generic") ? 1 : 0;
'''+before)
    before='stepBudgetMilliseconds:1'
    if body.count(before)!=2:raise ValueError('Exact current Main two request producers differ')
    body=body.replace(before,'''stepBudgetMilliseconds:1,rowDeltaReuseContract:rowDeltaContract,
               rowDeltaFeedbackContract:"ea-complete-ready-before-resize-v1",rowDeltaRowValidate:rowDeltaContract==1 ? ApexCatalogGridProductRow : null''')
    return source[:a]+body+source[b:]



