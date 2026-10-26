"""Explicit native EOF slots for the exact FrameStatus row-delta provider."""
from pathlib import Path
import re
import cas_grid_frame_status as previous,cas_grid_pool as pool
ROOT=Path(__file__).resolve().parents[1]
REPLACED=('ApexGridDeltaQueue','ApexGridDeltaBorrow','ApexGridDeltaAdvance','ApexGridDeltaPublish',
 'ApexGridDeltaCurrent','ApexGridDeltaRestore','ApexGridDeltaRetarget','ApexGridDeltaStep','ApexGridStatus','ApexGridBegin','ApexGridBeginFrame',
 'ApexGridStep','ApexGridNeedsWork','ApexGridCancel','ApexGridFrameStatusEffects','ApexGridPendingFrame','ApexGridGeometryFrame',
 'ApexGridNativeGuard','ApexGridNativeSetCellView','ApexGridPoolOwns','ApexGridPoolCoherent','ApexGridPoolSlot',
 'ApexGridPoolDataIndex','ApexGridCells','ApexGridCellsY','ApexGridMap')
ADDED=('ApexGridDeltaEofWindow','ApexGridDeltaEofReady','ApexGridDeltaBorrowEof','ApexGridAuthorityScope',
 'ApexGridAuthorityCapture','ApexGridAuthorityProbe','ApexGridAuthorityCurrent','ApexGridAuthorityOldCell','ApexGridAuthorityBank','ApexGridAuthorityReleaseCurrent',
 'ApexGridAuthorityLose','ApexGridAuthorityStatus','ApexGridAuthorityDispose','ApexGridAuthorityRecover')
FIELDS=('apexGridAuthority',)
def prepend(source,name,guard):
 pattern=r'\b(?:public|private)\s+(?:final\s+)?function\s+(?:get\s+)?'+re.escape(name)+r'\([^)]*\)\s*:\s*[\w.<>]+\s*\{'
 matches=list(re.finditer(pattern,source))
 if len(matches)!=1:raise ValueError('Exact authority method boundary differs: '+name)
 m=matches[0];a=m.start();b=m.end();depth=1
 while depth:depth+=(source[b]=='{')-(source[b]=='}');b+=1
 body=source[a:b];at=body.index('{')+1
 return source[:a]+body[:at]+'\n         '+guard+'\n'+body[at:]+source[b:]
def helpers():
 s=previous.helpers()
 s=pool.edit_method(s,'ApexGridDeltaQueue',[
  ('if(Math.abs(first-int(p.first))>=j.target || first<0 || first+j.target>p.feedCount ||\n            p.first<0 || int(p.first)+j.target>p.feedCount)return false;',
   '''if(Math.abs(first-int(p.first))>=j.target || !ApexGridDeltaEofWindow(p,first,j.target))return false;
         var eofWindow:Boolean=first+j.target>p.feedCount || int(p.first)+j.target>p.feedCount;
         var eofScope:Object=ApexGridAuthorityScope(s.owner);
         if(eofScope==null)return false;'''),
  ('rowValidate:s.request.rowDeltaRowValidate,',
   'rowValidate:s.request.rowDeltaRowValidate,eofWindow:eofWindow,authorityOwned:true,eofScope:eofScope,eofPanel:s.panel,eofStage:s.panel.stage,\n            oldPool:s.poolFlags,oldIntrinsics:s.intrinsics,oldPresentation:s.presentation,authority:null,'),
  ('borrowed:new Dictionary(true),entering:new Dictionary(true),members:new Dictionary(true),',
   'borrowed:new Dictionary(true),entering:new Dictionary(true),empty:new Dictionary(true),members:new Dictionary(true),')])
 s=pool.edit_method(s,'ApexGridDeltaBorrow',[
  ('var record:Object=d.oldBindings[cell];var expected:Object=d.oldExpected[cell];',
   'if(int(d.first)+slot>=int(d.oldPlan.feedCount))return ApexGridDeltaBorrowEof(cell,slot,d);\n         var record:Object=d.oldBindings[cell];var expected:Object=d.oldExpected[cell];'),
  ('ext.Selected!==record.selected || selectable.GetSelectionState(record.data)!==record.selected ||\n            !ApexGridDeltaCurrent(d))return false;',
   'ext.Selected!==record.selected || selectable.GetSelectionState(record.data)!==record.selected ||\n            !ApexGridDeltaCurrent(d) || !ApexGridAuthorityOldCell(cell,old,d))return false;')])
 s=pool.edit_method(s,'ApexGridDeltaAdvance',[
  ('if(!ApexGridAcquire(j))return false;j.lease=true;\n            mGridView.mouseEnabled=false;mGridView.mouseChildren=false;',
   '''if(!ApexGridAcquire(j))return false;j.lease=true;
            if(d.authorityOwned) {
               var held:Object=d.authority;held.acquired=true;
               if(!ApexGridAuthorityCurrent(d)) {ApexGridAuthorityLose(d,"acquire-authority-changed");return false;}
               held.mouse=Boolean(mGridView.mouseEnabled);held.children=Boolean(mGridView.mouseChildren);
               mGridView.mouseEnabled=false;
               if(!ApexGridAuthorityCurrent(d)) {ApexGridAuthorityLose(d,"mouse-gate-reentry");return false;}
               mGridView.mouseChildren=false;
               if(!ApexGridAuthorityCurrent(d) || mGridView.mouseEnabled!==false || mGridView.mouseChildren!==false) {ApexGridAuthorityLose(d,"input-gate-reentry");return false;}
               held.gate=true;
            } else {mGridView.mouseEnabled=false;mGridView.mouseChildren=false;}'''),
  ('for each(var old:Object in d.oldCells) {\n               d.originalMembers[old]=true;',
   '''for(var oldIndex:int=0;oldIndex<d.oldCells.length;oldIndex++) {
               var old:Object=d.oldCells[oldIndex];
               if(d.authorityOwned && (d.originalMembers[old]===true || !ApexGridAuthorityOldCell(old,oldIndex,d))) {
                  ApexGridAuthorityLose(d,"old-bank-custody-changed");return false;
               }
               d.originalMembers[old]=true;'''),
  ('s.ready=new Dictionary(true);j.generation=d.newGeneration;d.phase="plan";return true;',
   'if(d.authorityOwned && !ApexGridAuthorityCurrent(d)) {ApexGridAuthorityLose(d,"before-ready-registry-change");return false;}\n            s.ready=new Dictionary(true);if(d.authorityOwned) {d.authority.ready=s.ready;d.authority.working=true;}j.generation=d.newGeneration;d.phase="plan";return true;'),
  ('if(j.boundCell!=null || s.ready[cell]!==d.newGeneration)throw new Error("Entering row Ready fence refused");',
   '''if(int(d.first)+d.index>=int(d.oldPlan.feedCount)) {
               if(j.boundCell!=null || !ApexGridDeltaEofReady(cell,d.index,d,false))throw new Error("Entering EOF Ready fence refused");
               d.empty[cell]=true;
               d.bindings[cell]={schema:"empty-v1",generation:d.newGeneration,revision:d.revision,sorted:int(d.first)+d.index,
                  selected:false,logicalY:Number(d.ys[d.index]),physicalY:Number(cell.y)};
            } else if(j.boundCell!=null || s.ready[cell]!==d.newGeneration)throw new Error("Entering row Ready fence refused");'''),
  ('if(d.entering[cell]===true) {if(!ApexGridPresentationTexture(cell))return false;}',
   'if(d.empty[cell]===true) {if(!ApexGridDeltaEofReady(cell,d.index,d,false)) {ApexGridDeltaRestore(d);return false;}}\n            else if(d.entering[cell]===true) {if(!ApexGridPresentationTexture(cell))return false;}')])
 s=pool.edit_method(s,'ApexGridDeltaPublish',[
  ('mCells=d.cells;mCellsY=d.ys;mCellIndexToDataIndexMap=d.map;mPrevRectangleUpdate.y=-d.raw;',
   'if(d.authorityOwned)d.authority.mapping=true;\n         mCells=d.cells;mCellsY=d.ys;mCellIndexToDataIndexMap=d.map;mPrevRectangleUpdate.y=-d.raw;'),
  ('if(cell==null || s.ready[cell]!==d.newGeneration ||\n               (d.entering[cell]===true ? !ApexGridPresentationTexture(cell) : !ApexGridDeltaTexture(cell,d.expected[cell])))return false;',
   'if(d.empty[cell]===true) {if(!ApexGridDeltaEofReady(cell,i,d,false))return false;}\n            else if(cell==null || s.ready[cell]!==d.newGeneration ||\n               (d.entering[cell]===true ? !ApexGridPresentationTexture(cell) : !ApexGridDeltaTexture(cell,d.expected[cell])))return false;'),
  ('for(i=0;i<j.target;i++) {cell=d.cells[i];if(d.entering[cell]===true)cell.visible=true;}',
   'for(i=0;i<j.target;i++) {cell=d.cells[i];if(d.entering[cell]===true)cell.visible=d.empty[cell]!==true;}'),
  ('if(cell.parent!==d.view || cell.visible!==true || s.ready[cell]!==d.newGeneration ||\n               (d.entering[cell]===true ? !ApexGridPresentationTexture(cell) :\n                !ApexGridDeltaTexture(cell,d.expected[cell])))return false;',
   'if(d.empty[cell]===true) {if(!ApexGridDeltaEofReady(cell,i,d,false))return false;}\n            else if(cell.parent!==d.view || cell.visible!==true || s.ready[cell]!==d.newGeneration ||\n               (d.entering[cell]===true ? !ApexGridPresentationTexture(cell) :\n                !ApexGridDeltaTexture(cell,d.expected[cell])))return false;')])
 s=prepend(s,'ApexGridDeltaPublish','if(GetNumItems()!=d.oldPlan.feedCount || !ApexGridDeltaCurrent(d))return false;')
 s=prepend(s,'ApexGridDeltaPublish','if(!ApexGridAuthorityBank(d)) {ApexGridAuthorityLose(d,"publication-custody-changed");return false;}')
 s=pool.edit_method(s,'ApexGridDeltaPublish',[
  ('if(!ApexGridDeltaCurrent(d) || mCells!==d.cells || mCellsY!==d.ys || mCellIndexToDataIndexMap!==d.map)return false;',
   'if(GetNumItems()!=d.oldPlan.feedCount || !ApexGridDeltaCurrent(d) || mCells!==d.cells || mCellsY!==d.ys || mCellIndexToDataIndexMap!==d.map)return false;\n         if(!ApexGridAuthorityBank(d)) {ApexGridAuthorityLose(d,"feedback-custody-changed");return false;}')])
 s=pool.edit_method(s,'ApexGridDeltaRetarget',[
  ('if(d.phase!="retarget-finish")throw new Error("Unknown retarget phase");',
   'if(d.phase!="retarget-finish")throw new Error("Unknown retarget phase");\n         if(!ApexGridAuthorityBank(d)) {ApexGridAuthorityLose(d,"retarget-custody-changed");return false;}')])
 s=prepend(s,'ApexGridDeltaCurrent','if(d!=null && d.authorityOwned && d.authority!=null && !ApexGridAuthorityCurrent(d))return false;')
 s=prepend(s,'ApexGridDeltaRestore', '''if(d!=null && d.authorityOwned && d.authority!=null) {
            if(apexGridAuthority!=null && apexGridAuthority.lost===true)return;
            if(!ApexGridAuthorityCurrent(d)) {ApexGridAuthorityLose(d,"rollback-authority-changed");return;}
            if(!ApexGridAuthorityBank(d)) {ApexGridAuthorityLose(d,"rollback-custody-changed");return;}
         }''')
 s=pool.edit_method(s,'ApexGridDeltaStep',[
  ('var s:Object=apexGridState;var d:Object=s.delta;var j:Object=d.job;',
   '''var s:Object=apexGridState;var d:Object=s.delta;var j:Object=d.job;
         if(d.authorityOwned) {
            if(d.authority==null)ApexGridAuthorityCapture(d);
            if(!ApexGridAuthorityCurrent(d)) {ApexGridAuthorityLose(d,"step-authority-changed");return ApexGridAuthorityStatus();}
         }''')])
 guards={
  'ApexGridStatus':'if(apexGridAuthority!=null)return ApexGridAuthorityStatus();',
  'ApexGridStep':'if(apexGridAuthority!=null)return ApexGridAuthorityStatus();',
  'ApexGridDeltaStep':'if(apexGridAuthority!=null)return ApexGridAuthorityStatus();',
  'ApexGridBegin':'if(apexGridAuthority!=null && !ApexGridAuthorityRecover(request))return ApexGridAuthorityStatus();',
  'ApexGridBeginFrame':'if(apexGridAuthority!=null && !ApexGridAuthorityRecover(request))return;',
  'ApexGridNeedsWork':'if(apexGridAuthority!=null)return false;',
  'ApexGridCancel':'if(apexGridAuthority!=null) {if(reason=="dispose")ApexGridAuthorityDispose();return ApexGridAuthorityStatus();}',
  'ApexGridFrameStatusEffects':'if(apexGridAuthority!=null)return;',
  'ApexGridPendingFrame':'if(apexGridAuthority!=null)return true;',
  'ApexGridGeometryFrame':'if(apexGridAuthority!=null)return null;',
  'ApexGridNativeGuard':'if(apexGridAuthority!=null)return kind=="input";',
  'ApexGridNativeSetCellView':'if(apexGridAuthority!=null)return false;',
  'ApexGridPoolOwns':'if(apexGridAuthority!=null)return true;',
  'ApexGridPoolCoherent':'if(apexGridAuthority!=null)return false;',
  'ApexGridPoolSlot':'if(apexGridAuthority!=null)return false;',
  'ApexGridPoolDataIndex':'if(apexGridAuthority!=null)return -1;',
  'ApexGridCells':'if(apexGridAuthority!=null)return new Vector.<IView>();',
  'ApexGridCellsY':'if(apexGridAuthority!=null)return new Vector.<Number>();',
  'ApexGridMap':'if(apexGridAuthority!=null)return new Vector.<int>();'}
 for name,guard in guards.items():s=prepend(s,name,guard.replace('apexGridAuthority!=null','ApexGridAuthorityProbe()'))
 for name in ('ApexGridDeltaRestore','ApexGridDeltaPublish','ApexGridDeltaRetarget'):
  s=pool.edit_method(s,name,[('s.delta=null;', 's.delta=null;if(apexGridAuthority===d.authority && !d.authority.lost)apexGridAuthority=null;')])
 return s+'\n'+(ROOT/'Source/CASUi/catalog_grid_eof_methods.as').read_text(encoding='utf-8')+'\n'+(ROOT/'Source/CASUi/catalog_grid_authority_methods.as').read_text(encoding='utf-8')
