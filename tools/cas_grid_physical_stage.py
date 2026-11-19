"""Private exact logical/native physical position separation; no tolerances."""
from pathlib import Path
import sys
R=Path(__file__).resolve().parents[1]
import cas_grid_row_delta as previous
import cas_grid_pool as pool

REPLACED=('ApexGridDeltaCapture','ApexGridDeltaQueue','ApexGridDeltaBorrow','ApexGridDeltaPublish','ApexGridDeltaAdvance','ApexGridMetrics','ApexGridScrollOnlyApply')
ADDED=('ApexGridDeltaRefuse',)

def helpers():
    source=previous.helpers()
    source=pool.edit_method(source,'ApexGridDeltaCapture',[
      ('base:String(j.boundBase),variation:String(j.boundVariation),body:int(j.boundBody),menu:int(j.boundMenu),selected:selected};',
       'base:String(j.boundBase),variation:String(j.boundVariation),body:int(j.boundBody),menu:int(j.boundMenu),selected:selected,\n            logicalY:Number(ApexGridCellsY[j.index]),physicalY:Number(cell.y)};')])
    source=pool.edit_method(source,'ApexGridDeltaQueue',[
      ('oldVisible:new Dictionary(true),oldPositions:new Dictionary(true),bindings:new Dictionary(true),expected:new Dictionary(true),',
       'oldVisible:new Dictionary(true),oldPositions:new Dictionary(true),physicalY:new Dictionary(true),bindings:new Dictionary(true),expected:new Dictionary(true),')])
    source=pool.edit_method(source,'ApexGridDeltaBorrow',[
      ('Number(cell.y)!==Number(d.oldY[old]) || d.oldReady[cell]!==d.oldGeneration ||',
       'd.oldReady[cell]!==d.oldGeneration ||'),
      ('sorted!==int(d.first)+slot || !ApexGridDeltaTexture(cell,expected))return false;',
       '''sorted!==int(d.first)+slot || !ApexGridDeltaTexture(cell,expected))return false;
         var actualY:Number=Number(cell.y);
         if(!isFinite(Number(record.physicalY)) || record.logicalY!==Number(d.oldY[old]) || actualY!==record.physicalY)
            return ApexGridDeltaRefuse(d,"borrow-physical-y",Number(record.physicalY),actualY);'''),
      ('base:String(record.base),variation:String(record.variation),body:int(record.body),menu:int(record.menu),selected:Boolean(record.selected)};',
       'base:String(record.base),variation:String(record.variation),body:int(record.body),menu:int(record.menu),selected:Boolean(record.selected),\n            logicalY:Number(d.ys[slot]),physicalY:actualY};')])
    source=pool.edit_method(source,'ApexGridDeltaPublish',[
      ('for(i=0;i<j.target;i++) {cell=d.cells[i];if(d.entering[cell]!==true)cell.y=Number(d.ys[i]);}',
       '''for(i=0;i<j.target;i++) {
            cell=d.cells[i];if(d.entering[cell]!==true)cell.y=Number(d.ys[i]);
            d.physicalY[cell]=Number(cell.y);
            if(!isFinite(Number(d.physicalY[cell])))return ApexGridDeltaRefuse(d,"publish-native-y-nonfinite",Number(d.ys[i]),Number(d.physicalY[cell]));
         }'''),
      ('if(cell.parent!==d.view || cell.visible!==true || Number(cell.y)!==Number(d.ys[i]) || s.ready[cell]!==d.newGeneration ||',
       '''if(Number(cell.y)!==Number(d.physicalY[cell]))return ApexGridDeltaRefuse(d,"post-resize-physical-y",Number(d.physicalY[cell]),Number(cell.y));
            if(cell.parent!==d.view || cell.visible!==true || s.ready[cell]!==d.newGeneration ||'''),
      ('if(!ApexGridDeltaCurrent(d))return false;\n         var spare:Vector.<IView> =new Vector.<IView>();',
       '''if(!ApexGridDeltaCurrent(d))return false;
         for(i=0;i<j.target;i++) {cell=d.cells[i];d.bindings[cell].logicalY=Number(d.ys[i]);d.bindings[cell].physicalY=Number(d.physicalY[cell]);}
         var spare:Vector.<IView> =new Vector.<IView>();'''),
      ('if(d.latest!=null && !ApexGridDeltaQueue(j,d.latest))',
       'if(d.latest!=null && !ApexGridScrollOnlyQueue(j,d.latest) && !ApexGridDeltaQueue(j,d.latest))')])
    source=pool.edit_method(source,'ApexGridDeltaAdvance',[
      ('s.deltaLastRefusal="Borrowed row identity/resource/extension requires full native path";',
       'if(s.deltaRefusal==null || s.deltaRefusal.generation!==d.newGeneration)ApexGridDeltaRefuse(d,"borrow-identity-resource-extension",NaN,NaN);'),
      ('s.deltaLastRefusal="Delta feedback changed its complete ready owner/presentation";',
       'if(s.deltaRefusal==null || s.deltaRefusal.generation!==d.newGeneration)ApexGridDeltaRefuse(d,"publish-feedback-owner-presentation",NaN,NaN);')])
    source=pool.edit_method(source,'ApexGridMetrics',[
      ('result.row_delta_last_error=s.deltaLastError==null ? "" : String(s.deltaLastError);',
       '''result.row_delta_last_error=s.deltaLastError==null ? "" : String(s.deltaLastError);
         result.row_delta_last_refusal=s.deltaLastRefusal==null ? "" : String(s.deltaLastRefusal).substr(0,160);
         var refusal:Object=s.deltaRefusal;
         result.row_delta_refusal=refusal==null ? null : {reason:String(refusal.reason),phase:String(refusal.phase),
            index:int(refusal.index),generation:int(refusal.generation),expected:refusal.expected,actual:refusal.actual};''')])
    source=pool.edit_method(source,'ApexGridScrollOnlyApply',[
      ('var count:int=cells.length;',
       '''var count:int=cells.length;
         var physicalLedger:Boolean=ApexGridDeltaCapable();
         var ledger:Object=physicalLedger && s.presentation!=null ? s.presentation.committedBindings : null;'''),
      ('backup=s.scrollRollback;',
       '''backup=s.scrollRollback;
            if(physicalLedger && (backup.physicalYs==null || backup.physicalYs.length<count)) {
               backup.physicalYs=new Vector.<Number>(count);backup.nextPhysicalYs=new Vector.<Number>(count);backup.nextLogicalYs=new Vector.<Number>(count);
            }'''),
      ('var intrinsic:Object=s.intrinsics[cell];',
       '''var intrinsic:Object=s.intrinsics[cell];
               var physicalY:Number=physicalLedger && cell!=null ? Number(cell.y) : NaN;
               var record:Object=physicalLedger && ledger!=null ? ledger[cell] : null;
               if(physicalLedger) {
                  backup.physicalYs[i]=physicalY;
                  if(record==null || record.generation!==j.generation || record.revision!==s.revision || record.sorted!==int(map[i]) ||
                     record.logicalY!==Number(ys[i]) || !isFinite(Number(record.physicalY)) || record.physicalY!==physicalY) {
                     ApexGridDeltaRefuse({phase:"scroll-only",index:i,newGeneration:j.generation},"scroll-physical-y",record==null ? NaN : Number(record.physicalY),physicalY);
                     j.dirty=true;j.phase="acquire";return false;
                  }
               }'''),
      ('!isFinite(Number(cell.y)) || Number(cell.y)!==Number(ys[i]))',
       '(physicalLedger ? !isFinite(physicalY) : !isFinite(Number(cell.y)) || Number(cell.y)!==Number(ys[i])))'),
      ('cell.y=y;ys[i]=y;written++;',
       '''cell.y=y;ys[i]=y;written++;
               if(physicalLedger) {backup.nextPhysicalYs[i]=Number(cell.y);backup.nextLogicalYs[i]=y;}'''),
      ('completed=true;j.publishes++;j.phaseCounts.publish=int(j.phaseCounts.publish)+1;',
       '''if(physicalLedger) {
               for(i=0;i<count;i++)if(map[i]>=0) {
                  cell=cells[i];record=ledger==null ? null : ledger[cell];
                  if(s.presentation==null || s.presentation.committedBindings!==ledger || record==null ||
                     record.logicalY!==Number(backup.ys[i]) || record.physicalY!==Number(backup.physicalYs[i]) ||
                     Number(ys[i])!==Number(backup.nextLogicalYs[i]) || Number(cell.y)!==Number(backup.nextPhysicalYs[i])) {
                     ApexGridDeltaRefuse({phase:"scroll-only",index:i,newGeneration:j.generation},"scroll-post-resize-physical-y",Number(backup.nextPhysicalYs[i]),Number(cell.y));
                     j.dirty=true;j.phase="acquire";return false;
                  }
               }
               for(i=0;i<count;i++)if(map[i]>=0) {record=ledger[cells[i]];record.logicalY=Number(ys[i]);record.physicalY=Number(backup.nextPhysicalYs[i]);}
            }
            completed=true;j.publishes++;j.phaseCounts.publish=int(j.phaseCounts.publish)+1;'''),
      ('cell.y=Number(backup.ys[i]);ys[i]=Number(backup.ys[i]);',
       'cell.y=Number(physicalLedger ? backup.physicalYs[i] : backup.ys[i]);ys[i]=Number(backup.ys[i]);')])
    return source+'\n'+REFUSE

REFUSE='''      private function ApexGridDeltaRefuse(d:Object,reason:String,expected:Number,actual:Number) : Boolean {
         var s:Object=apexGridState;
         s.deltaLastRefusal=reason;
         s.deltaRefusal={reason:reason,phase:String(d.phase),index:int(d.index),generation:int(d.newGeneration),
            expected:isFinite(expected) ? expected : null,actual:isFinite(actual) ? actual : null};
         return false;
      }
'''
