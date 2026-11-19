"""Marker-preserving opt-in publication attribution after Featured."""
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
import cas_grid_featured as previous
import cas_grid_pool as pool

GRID_REPLACED=('ApexTxnAdvance','ApexGridPresentationPublish')
GRID_ADDED=('ApexGridPublicationTrace',)
MAIN_REPLACED=('ApexCatalogGridRequest','ApexCatalogTraceStatus')
MAIN_ADDED=('ApexCatalogPublicationTraceStep',)


def block(name,body,indent='         '):
    return indent+'// APEX_PUBLICATION_TRACE_BEGIN '+name+'\n'+body+'\n'+indent+'// APEX_PUBLICATION_TRACE_END '+name+'\n'


def strip(source):
    pattern=r'(?m)^[ \t]*// APEX_PUBLICATION_TRACE_BEGIN ([^\n]+)\n(.*?)^[ \t]*// APEX_PUBLICATION_TRACE_END \1\n'
    return re.sub(pattern,'',source,flags=re.S)


def marker(event):
    return '         if(publicationTrace!=null)ApexGridPublicationTrace(publicationTrace,"'+event+'",publicationGeneration,j.target,publicationOldCount);'


def setup():
    return '''         var publicationTrace:Function=apexGridState.request!=null && apexGridState.request.publicationTraceStep is Function ? apexGridState.request.publicationTraceStep as Function : null;
         var publicationGeneration:int=publicationTrace==null ? 0 : int(apexGridState.request.publicationTraceGeneration);
         var publicationOldCount:int=publicationTrace==null || apexGridState.presentation==null ? 0 : int(apexGridState.presentation.committedCells.length);'''


def helpers():
    source=previous.helpers()
    a,b=pool.method_extent(source,'ApexTxnAdvance');body=source[a:b]
    before='''            j.publishing=true;
            j.lastOperation="publish";'''
    after=block('atom-open',setup()+'\n         var publicationCompleted:Boolean=false;\n'+marker('publication.enter')+'\n         try {')+before
    if body.count(before)!=1:raise ValueError('Exact admitted publication atom seam differs')
    body=body.replace(before,after)
    before='''            j.publishes++;'''
    if body.count(before)!=1:raise ValueError('Exact publication tail seam differs')
    body=body.replace(before,block('tail-enter',marker('tail.enter'))+before)
    before='''            a.ApexGridGate(j,false);j.phase="done";
            return true;'''
    after='''            a.ApexGridGate(j,false);j.phase="done";
'''+block('tail-complete',marker('tail.leave')+'\n         publicationCompleted=true;')+'''            return true;
'''+block('atom-finally','''         } finally {
'''+marker('PLACEHOLDER').replace('"PLACEHOLDER"','publicationCompleted ? "publication.leave" : "publication.interrupted"')+'''
         }''')
    if body.count(before)!=1:raise ValueError('Exact publication success/return seam differs')
    body=body.replace(before,after);source=source[:a]+body+source[b:]
    a,b=pool.method_extent(source,'ApexGridPresentationPublish');body=source[a:b]
    before='''         var s:Object=apexGridState;var presentation:Object=s.presentation;
'''
    if body.count(before)!=1:raise ValueError('Exact presentation entry seam differs')
    body=body.replace(before,before+block('presentation-locals',setup()))
    before='''            mGridView.dispatchEvent(new GridEvent(GridEvent.RESIZE,null,[]));return;'''
    if body.count(before)!=1:raise ValueError('Exact non-staged resize seam differs')
    body=body.replace(before,block('fallback-resize-enter',marker('resize.enter'))+'''            mGridView.dispatchEvent(new GridEvent(GridEvent.RESIZE,null,[]));
'''+block('fallback-resize-leave',marker('resize.leave'))+'''            return;''')
    before='''         // Complete before touching the committed mapping or presentation.
'''
    body=body.replace(before,block('pretexture-enter',marker('pretexture.enter'))+before)
    before='''         if(j.cancelled || j.dirty || j.revision!=s.revision || !ApexGridValid(j.identity))return;'''
    if body.count(before)!=1:raise ValueError('Exact fresh prepublication owner fence differs')
    body=body.replace(before,block('pretexture-leave',marker('pretexture.leave'))+before)
    before='''            mGridView.dispatchEvent(new GridEvent(GridEvent.RESIZE,null,[]));
            if(j.cancelled'''
    if body.count(before)!=1:raise ValueError('Exact staged native feedback seam differs')
    body=body.replace(before,block('resize-enter',marker('resize.enter'))+'''            mGridView.dispatchEvent(new GridEvent(GridEvent.RESIZE,null,[]));
'''+block('resize-leave',marker('resize.leave'))+'''            if(j.cancelled''')
    before='''            for(i=0;i<j.target;i++) {
               next=presentation.stageCells[i];'''
    if body.count(before)!=1:raise ValueError('Exact postcallback texture fence differs')
    body=body.replace(before,block('posttexture-enter',marker('posttexture.enter'))+before)
    before='''            // One synchronous publication; no yield/draw/load between these'''
    body=body.replace(before,block('posttexture-leave',marker('posttexture.leave'))+block('visibility-enter',marker('visibility.enter'))+before)
    before='''            presentation.spareCells=presentation.committedCells;'''
    body=body.replace(before,block('visibility-leave',marker('visibility.leave'))+block('diagnostics-enter',marker('diagnostics.enter'))+before)
    before='''         } catch(publicationError:*) {'''
    body=body.replace(before,block('diagnostics-leave',marker('diagnostics.leave'))+before)
    source=source[:a]+body+source[b:]
    source+='\n'+block('provider-emitter',(ROOT/'Source/CASUi/catalog_grid_publication_trace_emit.as').read_text(),indent='')
    if compact(strip(source))!=compact(previous.helpers()):raise ValueError('Marker-stripped provider differs from complete preceding helpers')
    return source


def compact(source):
    # Preserve quoted literals before discarding comment/space trivia. The
    # independent Acorn test also compares every recovered method's real AST.
    tokens=r'(?P<string>"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')|(?P<comment>//[^\n]*|/\*.*?\*/)|(?P<space>\s+)|(?P<code>.)'
    return tuple(m.group() for m in re.finditer(tokens,source,re.S) if m.lastgroup in ('string','code'))


def main(source):
    baseline=source
    a,b=pool.method_extent(source,'ApexCatalogGridRequest');body=source[a:b]
    anchor='''         var list:Object=lease.panel.mcTileList;'''
    if body.count(anchor)!=1:raise ValueError('Exact current-owned Main request seam differs')
    locals='''         var publicationTrace:Function=null;var publicationGeneration:int=0;
         if(apexCatalogTrace!=null && apexCatalogTrace.enabled===true &&
            CASCustomizerMain.apexCatalogDrawTraceStep===apexCatalogTrace.callback) {
            publicationTrace=ApexCatalogPublicationTraceStep;publicationGeneration=int(apexCatalogTrace.generation);
         }'''
    body=body.replace(anchor,block('main-request-locals',locals)+anchor)
    before='stepBudgetMilliseconds:1};'
    if body.count(before)!=2:raise ValueError('Exact current two Main request budget fields differ')
    body=body.replace(before,'stepBudgetMilliseconds:1\n'+block('main-request-fields',',publicationTraceStep:publicationTrace,publicationTraceGeneration:publicationGeneration',indent='')+'};')
    source=source[:a]+body+source[b:]
    a,b=pool.method_extent(source,'ApexCatalogTraceStatus');body=source[a:b]
    before='''            // APEX_TIMER_TRACE_BEGIN timer-status-empty-status'''
    if body.count(before)!=1:raise ValueError('Exact disabled trace status seam differs')
    body=body.replace(before,block('trace-status-empty','            publication_profile:null,')+before)
    before='''            // APEX_TIMER_TRACE_BEGIN timer-status-active-status'''
    if body.count(before)!=1:raise ValueError('Exact active trace status seam differs')
    body=body.replace(before,block('trace-status-active','            publication_profile:trace.publication_profile==null ? null : trace.publication_profile,')+before)
    source=source[:a]+body+source[b:]
    at=source.rfind('\n   }')
    if at<0:raise ValueError('Exact Main class close unavailable')
    source=source[:at]+'\n'+block('main-callback',(ROOT/'Source/CASUi/catalog_publication_trace_methods.as').read_text(),indent='')+source[at:]
    if compact(strip(source))!=compact(baseline):raise ValueError('Marker-stripped Main differs from complete original')
    return source


if __name__=='__main__':
    (ROOT/'helpers.as').write_text(helpers(),encoding='utf-8')
