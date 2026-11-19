"""Provider-only successor to exact Intrinsic; default/native route retained."""
from pathlib import Path
import cas_grid_intrinsic as previous,cas_grid_pool as pool
ROOT=Path(__file__).resolve().parents[1]
REPLACED=('ApexGridBegin','ApexGridDeltaQueue','ApexGridDeltaAdvance','ApexGridDeltaRetarget','ApexGridDeltaRestore','ApexGridDeltaPublish',
 'ApexGridPresentationStart','ApexGridPresentationPublish','ApexGridPresentationRollback','ApexGridDetach','ApexGridPosition','ApexGridBind','ApexGridReady','ApexGridMetrics')
ADDED=('ApexGridSpareCustody','ApexGridSpareDescribe','ApexGridSpareReport','ApexGridSpareDefer','ApexGridSpareFilter','ApexGridDeltaTakeSpare','ApexGridSpareAfterPublish')
def helpers():
 s=previous.helpers()
 s=pool.edit_method(s,'ApexGridBegin',[
  ('ready:new Dictionary(true),poolFlags:',
   'spareCustody:prior!=null && prior.view===mGridView && prior.spareCustody!=null ? prior.spareCustody : new Dictionary(true),spareDetached:prior!=null && prior.view===mGridView && prior.spareDetached!=null ? prior.spareDetached : new Dictionary(true),deferredSpare:prior!=null && prior.view===mGridView ? prior.deferredSpare : [],deferredSpareFlags:prior!=null && prior.view===mGridView ? prior.deferredSpareFlags : new Dictionary(true),\n            ready:new Dictionary(true),poolFlags:')])
 s=pool.edit_method(s,'ApexGridDeltaQueue',[
  ('index:0,phase:"acquire",stockUsed:0,created:new Vector.<IView>(),',
   'index:0,phase:"acquire",stockUsed:0,usedSpare:new Vector.<IView>(),stockTaken:new Dictionary(true),originalMembers:new Dictionary(true),created:new Vector.<IView>(),')])
 s=pool.edit_method(s,'ApexGridDeltaAdvance',[
  ('p.committedVisible[old]=Boolean(old.visible);d.oldVisible[old]=Boolean(old.visible);d.oldPositions[old]=Number(old.y);',
   'd.originalMembers[old]=true;p.committedVisible[old]=Boolean(old.visible);d.oldVisible[old]=Boolean(old.visible);d.oldPositions[old]=Number(old.y);'),
  ('''               var intrinsic:Object=s.intrinsics[cell];
               if(cell==null || cell.parent!==d.view || cell.visible || intrinsic==null || intrinsic.type!==mCellType)throw new Error("Delta spare ownership/class changed");
               d.cells[slot]=cell;d.phase="position";return true;''',
   '''               // A cursor is not a proof that the preceding bank is reusable.
               // Reject one candidate per atom, without touching that widget.
               if(!ApexGridDeltaTakeSpare(cell,d,d.stockUsed-1))return true;
               d.cells[slot]=cell;d.phase="position";return true;'''),
  ('cell=d.cells[d.index];d.entering[cell]=true;',
   'cell=d.cells[d.index];if(!ApexGridSpareCustody(cell)) {ApexGridDeltaRestore(d);return true;}d.entering[cell]=true;')])
 s=pool.edit_method(s,'ApexGridDeltaRetarget',[
  ('if(d.cleanIndex<d.stockUsed) {\n               cell=d.oldSpare[d.cleanIndex++];',
   'if(d.cleanIndex<d.usedSpare.length) {\n               cell=d.usedSpare[d.cleanIndex++];'),
  ('''               if(cell==null || cell.parent!==d.view || s.intrinsics[cell]==null || s.intrinsics[cell].type!==d.cellType)
                  throw new Error("Retarget spare custody changed");
               if(cell.visible!==false)cell.visible=false;''',
   '''               if(!ApexGridSpareCustody(cell)) {ApexGridDeltaRestore(d);return true;}
               if(cell.visible!==false)cell.visible=false;''')])
 s=pool.edit_method(s,'ApexGridDeltaRestore',[
  ('if(incoming!=null && d.entering[incoming]===true && incoming.parent===d.view)incoming.visible=false;',
   'if(incoming!=null && d.entering[incoming]===true && incoming.parent===d.view && (s.ready[incoming]==null || s.ready[incoming]===j.generation) && ApexGridSpareCustody(incoming))incoming.visible=false;')])
 s=pool.edit_method(s,'ApexGridDeltaPublish',[
  ('for(i=d.stockUsed;i<d.oldSpare.length;i++)spare.push(d.oldSpare[i] as IView);',
   'for(i=0;i<d.oldSpare.length;i++)if(d.stockTaken[d.oldSpare[i]]!==true)spare.push(d.oldSpare[i] as IView);'),
  ('p.expected=new Dictionary(true);p.images=new Dictionary(true);p.working=false;p.published=true;',
   'p.expected=new Dictionary(true);p.images=new Dictionary(true);p.working=false;p.published=true;\n         ApexGridSpareAfterPublish();')])
 s=pool.edit_method(s,'ApexGridPresentationStart',[
  ('// A preceding committed bank can belong to the old native cell class.',
   '''var exclude:Object=new Dictionary(true);
         for each(var committed:Object in mCells)exclude[committed]=true;
         var filtered:Object=ApexGridSpareFilter(p.stageCells,p.stageY,p.stageMap,exclude,true,true);
         p.stageCells=filtered.cells;p.stageY=filtered.ys;p.stageMap=filtered.map;
         // A preceding committed bank can belong to the old native cell class.''')])
 s=pool.edit_method(s,'ApexGridPresentationPublish',[
  ('presentation.expected=new Dictionary(true);presentation.images=new Dictionary(true);presentation.working=false;presentation.published=true;',
   'presentation.expected=new Dictionary(true);presentation.images=new Dictionary(true);presentation.working=false;presentation.published=true;\n            ApexGridSpareAfterPublish();')])
 s=pool.edit_method(s,'ApexGridPresentationRollback',[
  ('for each(var cell:Object in p.stageCells)cell.visible=false;',
   'for each(var cell:Object in p.stageCells)if(cell!=null && cell.parent===mGridView && p.committedCells.indexOf(cell)<0 && (s.ready[cell]==null || s.ready[cell]===s.job.generation) && ApexGridSpareCustody(cell))cell.visible=false;')])
 a,b=pool.method_extent(s,'ApexGridDetach');body=s[a:b]
 needle='         var child:DisplayObject=cell as DisplayObject;'
 body=body.replace(needle,'''         var held:Object=apexGridState;var record:Object=held.spareCustody==null ? null : held.spareCustody[cell];
         if(held.spareDetached!=null && held.spareDetached[cell]===true)return;
         if(held.presentation!=null && held.presentation.committedCells!=null && held.presentation.committedCells.indexOf(cell)>=0)return;
         if(record!=null) {
            if(!ApexGridSpareCustody(cell))return;
            var ready:Object=held.ready;var readyValue:* =ready[cell];var flags:Object=held.poolFlags;var flagValue:* =flags[cell];
            var spare:DisplayObject=cell as DisplayObject;spare.parent.removeChild(spare);
            // Removal callbacks may adopt a cell or install a new state. Do not
            // erase that owner's ready/pool/intrinsic bookkeeping afterward.
            if(apexGridState!==held || cell.parent!=null || held.intrinsics[cell]!==record.intrinsic || held.ready!==ready || ready[cell]!==readyValue ||
               held.poolFlags!==flags || flags[cell]!==flagValue || held.presentation!=null && held.presentation.committedCells.indexOf(cell)>=0) {record.abandoned=true;return;}
            delete ready[cell];delete flags[cell];delete held.intrinsics[cell];delete held.spareCustody[cell];held.spareDetached[cell]=true;return;
         }
'''+needle,1)
 s=s[:a]+body+s[b:]
 for name,needle,j in(
  ('ApexGridPosition','         if(j.index>=j.target) {ApexGridPoolPark(cell,j.index);return;}','j'),
  ('ApexGridBind','         var s:Object=apexGridState;j.boundCell=null;','j'),
  ('ApexGridReady','         var s:Object=apexGridState;var j:Object=s.job;','j')):
  guard='         if(!ApexGridSpareCustody(cell)) {ApexTxnCancel('+j+',"spare-custody");return;}'
  s=pool.edit_method(s,name,[(needle,(guard+'\n'+needle)if name=='ApexGridPosition'else(needle+'\n'+guard))])
 s=pool.edit_method(s,'ApexGridReady',[
  ('s.ready[cell]=item!=null ? generation : -1;j.boundCell=null;',
   's.ready[cell]=item!=null ? generation : -1;\n         if(s.spareCustody[cell]!=null)s.spareCustody[cell].readyValue=s.ready[cell];j.boundCell=null;')])
 s=pool.edit_method(s,'ApexGridMetrics',[
  ('var s:Object=apexGridState;',
   '''var s:Object=apexGridState;
         result.spare_diagnostic={scanned:int(s.spareScanned),accepted:int(s.spareAccepted),rejected:int(s.spareRejected),
            deferred:s.deferredSpare==null ? 0 : int(s.deferredSpare.length),last:s.spareLast==null ? null :
            {reason:String(s.spareLast.reason),index:int(s.spareLast.index),parent:s.spareLast.parent===true,hidden:s.spareLast.hidden===true,
             registered:s.spareLast.registered===true,current:s.spareLast.current===true,member:s.spareLast.member===true,used:s.spareLast.used===true}};''')])
 return s+'\n'+(ROOT/'Source/CASUi/catalog_spare_custody_methods.as').read_text()
