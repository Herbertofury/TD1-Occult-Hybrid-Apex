"""Compile and retain a frame-budgeted native CAS grid adapter.

Private EA/donor sources are read at build time; only Apex helper code is stored
here. The paired Java pass authenticates provider bytes and all default native
paths, appends helpers and inserts guarded native prefixes only.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TARGET = 'olympus.layout.RecyclingGridLayout'
PROVIDERS = {
 '6ddb983fee2bd284a2b7efec155e1544bfe99d27f16d4d28097bada25e1864f0': '62ECC59A:00000000:89D13757C58C2E05',
 '5f475a80a4f9c77f9a0439e133221a31f766cb929318f74191b4b9bad98e8cae': '62ECC59A:00000000:12272E1AC0C1F8E2',
}

ADAPTER_METHODS = r'''
      private var apexGridState:Object;

      public function get ApexGridCells() : Object {return mCells;}
      public function get ApexGridCellsY() : Object {
         if(mCellsY==null)mCellsY=new Vector.<Number>(mCells.length);
         return mCellsY;
      }
      public function get ApexGridMap() : Object {
         if(mCellIndexToDataIndexMap==null)mCellIndexToDataIndexMap=new Vector.<int>(mCells.length);
         return mCellIndexToDataIndexMap;
      }

      public function ApexGridBegin(request:Object) : Object {
         if(!request || !request.panel || !request.owner || request.owner.active!==true ||
            !(request.validate is Function) || !(request.inputValidate is Function) || request.validate(request.owner)!==true ||
            !request.panel.mcTileList || request.panel.mcTileList.mGridLayout!==this ||
            !request.panel.stage || !isFinite(Number(request.scale)) || Number(request.scale)<=0)
            throw new Error("Grid transaction owner lease unavailable");
         if(apexGridState!=null && apexGridState.job!=null && apexGridState.job.phase!="cancelled") {
            if(apexGridState.owner===request.owner && apexGridState.ownerGeneration===int(request.owner.generation) &&
               apexGridState.feed===mGridData && apexGridState.view===mGridView) {
               var scaleChanged:Boolean=Number(apexGridState.request.scale)!=Number(request.scale);
               apexGridState.request=request;
               apexGridState.bootstrap=request.bootstrap===true;
               ApexTxnRequest(apexGridState.job,request);
               if(!apexGridState.bootstrap && apexGridState.job.phase=="measured") {
                  apexGridState.job.phase="acquire";apexGridState.job.dirty=true;
               }
               if(scaleChanged)ApexTxnNotify(apexGridState.job,"update");
               return ApexGridStatus();
            }
            apexGridState.nextRequest=request;
            ApexTxnCancel(apexGridState.job,"context");
            return ApexGridStatus();
         }
         var prior:Object=apexGridState;
         var visibleBefore:Boolean=prior!=null && prior.view===mGridView ? Boolean(prior.visibleBefore) : mGridView.visible;
         apexGridState={armed:true,job:null,request:request,panel:request.panel,owner:request.owner,
            ownerGeneration:int(request.owner.generation),validate:request.validate,inputValidate:request.inputValidate,feed:mGridData,view:mGridView,
            revision:0,deferredEvents:0,lease:null,externalSuppression:false,identity:{},visibleBefore:visibleBefore,retiringCell:null,
            mouseBefore:prior!=null && prior.view===mGridView ? prior.mouseBefore : mGridView.mouseEnabled,
            childrenBefore:prior!=null && prior.view===mGridView ? prior.childrenBefore : mGridView.mouseChildren,
            ready:new Dictionary(true),retireAll:prior!=null && (prior.retireAll || prior.view!==mGridView),
            retiringView:prior!=null && prior.view!==mGridView ? prior.view : null,
            measuredHeight:0,measuredAspect:0,measuredGeneration:0,measuredScale:0,measuredRevision:-1,measuredClass:null,
            bootstrap:request.bootstrap===true,measurementReady:false,naturalWidth:0,naturalHeight:0,naturalAspect:0,
            intrinsics:prior!=null && prior.view===mGridView ? prior.intrinsics : new Dictionary(true),
            pendingClass:prior==null?null:prior.pendingClass,pendingMargin:prior==null?null:prior.pendingMargin,
            pendingRedraw:prior==null?false:prior.pendingRedraw,nextRequest:null};
         if(mCellsY==null || mCellsY.length!=mCells.length)mCellsY=new Vector.<Number>(mCells.length);
         if(mCellIndexToDataIndexMap==null || mCellIndexToDataIndexMap.length!=mCells.length)
            mCellIndexToDataIndexMap=new Vector.<int>(mCells.length);
         apexGridState.job=ApexTxnBegin(this,request);
         return ApexGridStatus();
      }

      public function ApexGridStep(maxOps:int=1, deadline:int=0) : Object {
         if(apexGridState==null)return {phase:"unarmed",active:false};
         if(apexGridState.job==null)return ApexGridStatus();
         var s:Object=apexGridState;
         if(!ApexGridValid(s.identity))ApexTxnCancel(s.job,"context");
         if(s.bootstrap && !s.job.cancelled)return ApexGridBootstrapStep(maxOps,deadline);
         var result:Object=ApexTxnStep(s.job,maxOps,deadline);
         ApexGridMetrics(result);
         if(result.phase=="cancelled" && (result.reason=="dispose" || result.reason=="error-abandon"))s.request=null;
         if(result.phase=="cancelled" && s.nextRequest!=null) {
            var next:Object=s.nextRequest;s.nextRequest=null;
            return ApexGridBegin(next);
         }
         return result;
      }

      public function ApexGridStatus() : Object {
         if(apexGridState==null)return {phase:"unarmed",active:false};
         if(apexGridState.job==null)return {phase:apexGridState.armed ? "cancelled" : "unarmed",
            active:false,armed:apexGridState.armed,abandoned:apexGridState.terminalReason=="error-abandon",
            terminal_blocked:apexGridState.armed,reason:apexGridState.terminalReason,
            lease:false,pendingCell:false};
         var result:Object=ApexTxnStatus(apexGridState.job);
         ApexGridMetrics(result);
         return result;
      }
      public function ApexGridNeedsWork() : Boolean {
         var s:Object=apexGridState;
         if(s==null || !s.armed || s.job==null || s.job.phase=="cancelled")return false;
         var j:Object=s.job;
         return s.bootstrap || j.phase!="done" || j.dirty || j.revision!=s.revision ||
            s.owner==null || s.owner.active!==true || int(s.owner.generation)!=s.ownerGeneration;
      }
      private function ApexGridMetrics(result:Object) : void {
         var s:Object=apexGridState;
         // A confirmed live Draw metric survives a geometry-only replan.
         // New owner/feed state starts empty; class/revision/scale changes
         // invalidate before Main can consume an old category measurement.
         if(s.owner==null || s.owner.active!==true || int(s.owner.generation)!=s.ownerGeneration ||
            s.feed!==mGridData || s.view!==mGridView || s.measuredRevision!=s.revision ||
            s.measuredClass!==mCellType || s.request==null ||
            s.measuredScale!=Number(s.request.scale)) {
            s.measuredHeight=0;s.measuredAspect=0;s.measuredGeneration=0;s.measuredScale=0;
            s.measuredRevision=-1;s.measuredClass=null;
         }
         result.measured_height=s.measuredHeight;result.measured_aspect=s.measuredAspect;
         result.measured_generation=s.measuredGeneration;result.measured_scale=s.measuredScale;
         result.measurement_ready=s.measurementReady;result.natural_width=s.naturalWidth;
         result.natural_height=s.naturalHeight;result.natural_aspect=s.naturalAspect;result.bootstrap=s.bootstrap;
         result.deferred_events=s.deferredEvents;
      }
      public function ApexGridQueuedProfile() : Object {
         return {suppressed:true,before_count:mCells.length,after_count:mCells.length,
            setup_ms:0,position_ms:0,bind_ms:0,resize_ms:0,total_ms:0,transaction:ApexGridStatus()};
      }

      public function ApexGridCancel(reason:String) : Object {
         if(apexGridState==null)return {phase:"unarmed",active:false};
         if(apexGridState.job==null && reason=="error-abandon") {
            if(apexGridState.owner!=null)apexGridState.owner.active=false;
            apexGridState.nextRequest=null;apexGridState.validate=null;apexGridState.inputValidate=null;
            apexGridState.owner=null;apexGridState.panel=null;apexGridState.feed=null;apexGridState.request=null;
            apexGridState.terminalReason=reason;
            mGridView.visible=false;mGridView.mouseEnabled=false;mGridView.mouseChildren=false;
            return ApexGridStatus();
         }
         if(apexGridState.job==null) {
            if(reason=="bootstrap-failed" && apexGridState.deferredEvents>0)
               return {phase:"rollback-refused",reason:"native-events-deferred"};
            if(reason=="bootstrap-failed" || reason=="dispose")apexGridState=null;
            return {phase:"unarmed",active:false,reason:reason};
         }
         if(reason=="bootstrap-failed") {
            var untouched:Object=apexGridState.job;
            if(apexGridState.deferredEvents>0)return {phase:"rollback-refused",reason:"native-events-deferred"};
            if(untouched.operations!=0 || untouched.lease || untouched.pendingCell!=null || untouched.publishes!=0)
               return {phase:"rollback-refused",reason:"native-work-started"};
            apexGridState=null;return {phase:"unarmed",active:false,reason:reason};
         }
         if(reason=="dispose" || reason=="error-abandon") {
            var retired:Object=apexGridState.job;
            if(ApexGridOwns(retired))ApexGridRelease(retired);
            retired.lease=false;retired.cancelled=true;retired.reason=reason;retired.phase="cancelled";retired.abandoned=true;
            // Both terminal modes release references without replay/teardown.
            // A live failed view stays hidden; its widget retains its children.
            // Dispose separately means that widget is already retiring.
            if(apexGridState.owner!=null)apexGridState.owner.active=false;
            if(reason=="error-abandon") {
               mGridView.visible=false;mGridView.mouseEnabled=false;mGridView.mouseChildren=false;
            }
            retired.pendingCell=null;retired.pendingAttached=false;retired.boundCell=null;
            apexGridState.retiringCell=null;
            apexGridState.nextRequest=null;apexGridState.validate=null;apexGridState.inputValidate=null;apexGridState.owner=null;
            apexGridState.panel=null;apexGridState.feed=null;
            if(!retired.running)apexGridState.request=null;
            return ApexGridStatus();
         }
         ApexTxnCancel(apexGridState.job,reason);
         return ApexGridStatus();
      }

      public function ApexGridIdentity() : Object {return apexGridState.identity;}
      public function ApexGridValid(identity:Object) : Boolean {
         var s:Object=apexGridState;
         return s!=null && identity===s.identity && s.panel!=null && s.panel.stage!=null &&
            s.panel.mcTileList!=null && s.panel.mcTileList.mGridLayout===this && s.view===mGridView && s.feed===mGridData &&
            s.owner.active===true && int(s.owner.generation)==s.ownerGeneration && s.validate(s.owner)===true;
      }
      public function ApexGridCount() : int {return mGridData==null ? 0 : GetNumItems();}
      public function ApexGridRevision() : int {return apexGridState.revision;}
      public function ApexGridAcquire(j:Object) : Boolean {
         if(mbSuppressUpdates && apexGridState.lease!==j)return false;
         apexGridState.lease=j;mbSuppressUpdates=true;return true;
      }
      public function ApexGridOwns(j:Object) : Boolean {return apexGridState.lease===j && mbSuppressUpdates && !apexGridState.externalSuppression;}
      public function ApexGridSuppressionChanged(value:Boolean) : void {
         if(apexGridState!=null && apexGridState.armed && apexGridState.lease!=null) {
            apexGridState.externalSuppression=true;
            ApexTxnCancel(apexGridState.job,"lease");
         }
      }
      public function ApexGridRelease(j:Object) : void {
         if(apexGridState.lease!==j)return;
         mbSuppressUpdates=false;apexGridState.lease=null;
      }
      public function ApexGridGate(j:Object, blocked:Boolean) : void {
         if(blocked){mGridView.visible=false;mGridView.mouseEnabled=false;mGridView.mouseChildren=false;}
         else if(ApexGridValid(apexGridState.identity)) {
            mGridView.visible=apexGridState.visibleBefore;
            mGridView.mouseEnabled=apexGridState.mouseBefore;mGridView.mouseChildren=apexGridState.childrenBefore;
         }
      }
      public function ApexGridConfigure(p:Object,j:Object) : void {
         mNumLines=int(p.columns);
         mCellMargin=new Margin(0,p.gapX,p.gapY,0);
         mCellBounds=new Rectangle(0,0,p.width,0);
         mCellViewSizeFallback=new Point(p.width,p.height);
         mGridView.width=p.viewWidth;mGridView.height=p.viewHeight;
      }
      public function ApexGridCommitClass() : void {
         if(apexGridState.pendingClass!=null)mCellType=apexGridState.pendingClass as Class;
         mbUseRedrawListener=Boolean(apexGridState.pendingRedraw);
         apexGridState.pendingClass=null;apexGridState.retireAll=false;
         apexGridState.retiringView=null;
      }
      public function ApexGridCreate() : Object {
         var cell:Object=CreateCell();
         if(!(cell is DisplayObject) || !(cell is IView))throw new Error("Invalid native CAS cell class");
         return cell;
      }
      public function ApexGridAttach(cell:Object) : void {mGridView.addChild(cell as DisplayObject);}
      public function ApexGridDetach(cell:Object) : void {
         var child:DisplayObject=cell as DisplayObject;
         if(child!=null && (child.parent===mGridView || child.parent===apexGridState.retiringView))
            child.parent.removeChild(child);
         delete apexGridState.ready[cell];
      }
      public function ApexGridDiscard(cell:Object) : void {delete apexGridState.ready[cell];}
      public function ApexGridPosition(cell:Object,x:Number,y:Number,p:Object,j:Object) : void {
         var marker:Object=cell.getChildByName("apexCatalogCardScale");
         var intrinsic:Object=apexGridState.intrinsics[cell];
         var aspect:Number=marker==null ? (intrinsic==null ? Number(cell.scaleY)/Number(cell.scaleX) : Number(intrinsic.aspect)) : Number(marker.scaleY);
         if(!isFinite(aspect) || aspect<=0)throw new Error("Native card aspect unavailable");
         if(marker==null) {
            marker=new Sprite();marker.name="apexCatalogCardScale";marker.mouseEnabled=false;marker.mouseChildren=false;
            cell.addChild(marker);
         }
         marker.scaleY=aspect;
         cell.scaleX=Number(apexGridState.request.scale);cell.scaleY=Number(apexGridState.request.scale)*aspect;
         cell.x=x;cell.y=y;
      }
      public function ApexGridBind(cell:Object,sortedIndex:int,generation:int,j:Object) : void {
         var s:Object=apexGridState;j.boundCell=null;
         if(j.cancelled || j.dirty || generation!=j.generation || !ApexGridValid(j.identity) ||
            j.revision!=s.revision || j.index>=mCells.length || mCells[j.index]!==cell ||
            cell.parent!==mGridView || mCellIndexToDataIndexMap[j.index]!=sortedIndex) {j.dirty=true;return;}
         delete s.ready[cell];
         var started:Number=getTimer();var item:Object=GetDataAtIndex(sortedIndex);
         j.phaseCounts.data=int(j.phaseCounts.data)+1;
         j.phaseMax.data=Math.max(Number(j.phaseMax.data)||0,getTimer()-started);
         var dataIndex:int=item==null ? -1 : GetDataIndexOfSortedIndex(sortedIndex);
         var base:String=item==null ? null : String(item.data_id);
         var variation:String=item==null ? null : String(item.GetVariationOrBaseId());
         var body:int=item==null ? -1 : int(item.body_type);
         var menu:int=item==null ? -1 : int(item.menu_state);
         if(j.cancelled || j.dirty || !ApexGridValid(j.identity) || generation!=j.generation || j.revision!=s.revision ||
            mCells[j.index]!==cell || cell.parent!==mGridView || mCellIndexToDataIndexMap[j.index]!=sortedIndex ||
            item!=null && GetDataIndexOfSortedIndex(sortedIndex)!=dataIndex) {j.dirty=true;return;}
         if(item!=null) {
            started=getTimer();(cell as IView).Draw(item);
            j.phaseCounts.draw=int(j.phaseCounts.draw)+1;
            j.phaseMax.draw=Math.max(Number(j.phaseMax.draw)||0,getTimer()-started);
            if(j.cancelled || j.dirty || !ApexGridValid(j.identity) || generation!=j.generation || j.revision!=s.revision ||
               mCells[j.index]!==cell || cell.parent!==mGridView || mCellIndexToDataIndexMap[j.index]!=sortedIndex) {j.dirty=true;return;}
            var aspect:Number=Number(cell.scaleY)/Number(cell.scaleX);
            var marker:Object=cell.getChildByName("apexCatalogCardScale");
            if(!isFinite(aspect) || aspect<=0 || marker==null)throw new Error("Native bound card aspect unavailable");
            marker.scaleY=aspect;
            cell.scaleX=Number(s.request.scale);cell.scaleY=Number(s.request.scale)*aspect;
            if(j.index==0) {
               s.measuredAspect=aspect;
               s.measuredHeight=cell.mcHitArea==null ? 0 : Number(cell.mcHitArea.height)*Number(cell.scaleY);
               s.measuredGeneration=j.generation;s.measuredScale=Number(s.request.scale);
               s.measuredRevision=s.revision;s.measuredClass=mCellType;
            }
         }
         cell.visible=item!=null;
         // Keep only copied primitives and a widget handle across the yield.
         // The feed's borrowed product stays in this synchronous stack only.
         j.boundCell=cell;j.boundSlot=j.index;j.boundSorted=sortedIndex;j.boundData=dataIndex;
         j.boundGeneration=generation;j.boundRevision=s.revision;j.boundPresent=item!=null;
         j.boundBase=base;j.boundVariation=variation;j.boundBody=body;j.boundMenu=menu;
      }
      public function ApexGridReady(cell:Object,generation:int) : void {
         var s:Object=apexGridState;var j:Object=s.job;
         if(j.cancelled || j.dirty || !ApexGridValid(j.identity) || generation!=j.generation ||
            generation!=j.boundGeneration || j.revision!=s.revision || j.boundRevision!=s.revision ||
            j.boundCell!==cell || j.boundSlot!=j.index || j.index>=mCells.length || mCells[j.index]!==cell ||
            cell.parent!==mGridView || mCellIndexToDataIndexMap[j.index]!=j.boundSorted) {j.dirty=true;return;}
         var started:Number=getTimer();var item:Object=GetDataAtIndex(j.boundSorted);
         j.phaseCounts.data=int(j.phaseCounts.data)+1;
         j.phaseMax.data=Math.max(Number(j.phaseMax.data)||0,getTimer()-started);
         if((item!=null)!=j.boundPresent || item!=null &&
            (GetDataIndexOfSortedIndex(j.boundSorted)!=j.boundData || String(item.data_id)!==j.boundBase ||
             String(item.GetVariationOrBaseId())!==j.boundVariation || int(item.body_type)!=j.boundBody || int(item.menu_state)!=j.boundMenu ||
             "dccFavoriteProductId" in cell && cell.dccFavoriteProductId!==j.boundBase)) {j.dirty=true;return;}
         var selectable:SelectableArrayDataFeed=mGridData as SelectableArrayDataFeed;
         var selected:Boolean=item!=null && selectable!=null && selectable.GetSelectionState(j.boundData);
         var ext:Selectability=(cell as IExtendable).GetExtension(Selectability) as Selectability;
         if(j.cancelled || j.dirty || !ApexGridValid(j.identity) || generation!=j.generation || j.revision!=s.revision ||
            j.boundCell!==cell || j.boundSlot!=j.index || mCells[j.index]!==cell || cell.parent!==mGridView ||
            mCellIndexToDataIndexMap[j.index]!=j.boundSorted) {j.dirty=true;return;}
         started=getTimer();ext.Selected=selected;
         j.phaseCounts.selected_setter=int(j.phaseCounts.selected_setter)+1;
         j.phaseMax.selected_setter=Math.max(Number(j.phaseMax.selected_setter)||0,getTimer()-started);
         if(j.cancelled || j.dirty || !ApexGridValid(j.identity) || generation!=j.generation || j.revision!=s.revision ||
            j.boundCell!==cell || j.boundSlot!=j.index || mCells[j.index]!==cell ||
            cell.parent!==mGridView || mCellIndexToDataIndexMap[j.index]!=j.boundSorted) {j.dirty=true;return;}
         // The setter can run timeline/event callbacks. Re-read, never retain,
         // the native product before publishing this slot's ready generation.
         started=getTimer();item=GetDataAtIndex(j.boundSorted);
         j.phaseCounts.data=int(j.phaseCounts.data)+1;
         j.phaseMax.data=Math.max(Number(j.phaseMax.data)||0,getTimer()-started);
         if(j.cancelled || j.dirty || !ApexGridValid(j.identity) || generation!=j.generation || j.revision!=s.revision ||
            j.boundCell!==cell || j.boundSlot!=j.index || mCells[j.index]!==cell || cell.parent!==mGridView ||
            mCellIndexToDataIndexMap[j.index]!=j.boundSorted || (item!=null)!=j.boundPresent || item!=null &&
            (GetDataIndexOfSortedIndex(j.boundSorted)!=j.boundData || String(item.data_id)!==j.boundBase ||
             String(item.GetVariationOrBaseId())!==j.boundVariation || int(item.body_type)!=j.boundBody || int(item.menu_state)!=j.boundMenu ||
             "dccFavoriteProductId" in cell && cell.dccFavoriteProductId!==j.boundBase)) {j.dirty=true;return;}
         s.ready[cell]=item!=null ? generation : -1;j.boundCell=null;
      }
      public function ApexGridPublish(p:Object,j:Object) : void {
         mPrevRectangleUpdate.y=-Number(p.scrollY);
         mGridView.dispatchEvent(new GridEvent(GridEvent.RESIZE,null,[]));
      }
      public function ApexGridAbort(j:Object,reason:String) : void {
         if(reason=="dispose" || reason=="disarm")apexGridState.armed=false;
         // No bulk reset/recovery. Main must Begin with its fresh validated lease.
      }
      public function ApexGridNow() : Number {return getTimer();}

      public function ApexGridCaptureNewCell(cell:Object) : void {
         if(apexGridState==null || !apexGridState.armed)return;
         var sx:Number=Number(cell.scaleX);
         var marker:Object=cell.getChildByName("apexCatalogCardScale");
         var aspect:Number=marker==null ? Number(cell.scaleY)/sx : Number(marker.scaleY);
         var width:Number=Number(cell.width)/sx;
         var height:Number=cell.mcHitArea==null ? Number(cell.getBounds(cell).height) : Number(cell.mcHitArea.height);
         if(!isFinite(width) || width<=0 || !isFinite(height) || height<=0 || !isFinite(aspect) || aspect<=0)
            throw new Error("Native cell intrinsic metrics unavailable");
         apexGridState.intrinsics[cell]={width:width,height:height,aspect:aspect,type:mCellType};
         apexGridState.naturalWidth=width;apexGridState.naturalHeight=height;apexGridState.naturalAspect=aspect;
         apexGridState.measurementReady=true;
      }

      private function ApexGridBootstrapStep(maxOps:int,deadline:int) : Object {
         var s:Object=apexGridState;var j:Object=s.job;
         if(s.owner.frame_validated!==true) {
            var waiting:Object=ApexGridStatus();waiting.phase="await-owner";return waiting;
         }
         if(s.measurementReady){j.phase="measured";return ApexGridStatus();}
         if(maxOps<1 || maxOps>64)throw new Error("Invalid bootstrap budget");
         if(deadline>0 && getTimer()>=deadline)return ApexGridStatus();
         if(!j.lease) {
            if(!ApexGridAcquire(j))return ApexGridStatus();
            j.lease=true;ApexGridGate(j,true);j.operations++;
            if(maxOps==1 || deadline>0 && getTimer()>=deadline)return ApexGridStatus();
         }
         if(mCells.length>0 && !s.retireAll && s.intrinsics[mCells[0]]!=null) {
            var known:Object=s.intrinsics[mCells[0]];
            s.naturalWidth=known.width;s.naturalHeight=known.height;s.naturalAspect=known.aspect;s.measurementReady=true;
            j.operations++;j.phase="measured";return ApexGridStatus();
         }
         var type:Class=s.pendingClass==null ? mCellType : s.pendingClass as Class;
         if(type==null){var empty:Object=ApexGridStatus();empty.phase="await-class";return empty;}
         var before:Class=mCellType;var redrawBefore:Boolean=mbUseRedrawListener;var started:int=getTimer();
         j.running=true;
         try {
            mCellType=type;
            if(s.pendingClass!=null)mbUseRedrawListener=Boolean(s.pendingRedraw);
            var cell:Object=CreateCell();
            if(!j.abandoned){j.pendingCell=cell;j.pendingAttached=false;}
            if(!j.abandoned && !s.measurementReady)throw new Error("Native factory capture was not executed");
            j.operations++;j.lastPhase="bootstrap";j.lastOperation="construct";
            j.phaseCounts.construct=int(j.phaseCounts.construct)+1;
            j.phaseMax.construct=Math.max(Number(j.phaseMax.construct)||0,getTimer()-started);
            if(!j.cancelled && ApexGridValid(s.identity))j.phase="measured";
            else if(!j.cancelled)ApexTxnCancel(j,"context");
         } catch(error:*) {
            j.error=String(error);ApexTxnCancel(j,"error");
         } finally {mCellType=before;mbUseRedrawListener=redrawBefore;j.running=false;}
         if(j.abandoned){j.pendingCell=null;j.pendingAttached=false;j.phase="cancelled";s.request=null;}
         return ApexGridStatus();
      }

      public function ApexGridNativeSetCellView(type:Class,margin:Margin,redraw:Boolean) : Boolean {
         if(apexGridState==null || !apexGridState.armed)return false;
         // Initialization can fail before a job exists. The live failed view
         // remains terminal/input-blocked; consume events without native replay.
         if(apexGridState.job==null)return true;
         apexGridState.deferredEvents++;
         if(type!==mCellType) {
            apexGridState.pendingClass=type;apexGridState.pendingMargin=margin;apexGridState.pendingRedraw=redraw;
            apexGridState.retireAll=true;
            apexGridState.measurementReady=false;apexGridState.naturalWidth=0;apexGridState.naturalHeight=0;apexGridState.naturalAspect=0;
         } else mbUseRedrawListener=redraw;
         // Preserve the native logical setter immediately. Physical old-class
         // cells remain gated and are retired by bounded capacity steps.
         mCellType=type;mCellMargin=margin==null ? new Margin(0) : margin;mbUseRedrawListener=redraw;
         apexGridState.revision++;ApexTxnNotify(apexGridState.job,"update");return true;
      }

      private function ApexGridFreshInput(s:Object,j:Object) : Boolean {
         try {
            if(s.inputValidate(s.owner)===true)return false;
         } catch(inputError:*) {
         }
         s.owner.active=false;ApexTxnCancel(j,"context");return true;
      }

      public function ApexGridNativeGuard(kind:String,event:Object=null) : Boolean {
         if(apexGridState==null || !apexGridState.armed)return false;
         var s:Object=apexGridState;var j:Object=s.job;
         if(j==null)return true;
         if(kind!="input" && kind!="redraw")s.deferredEvents++;
         if(kind=="selection") {
            if(!j.running && !j.cancelled) {s.revision++;ApexTxnNotify(j,"selection");}
            return true;
         }
         if(kind=="input") {
            if(j==null || j.phase!="done" || j.dirty || j.revision!=s.revision || s.owner.active!==true ||
               int(s.owner.generation)!=s.ownerGeneration || s.feed!==mGridData || s.view!==mGridView ||
               s.panel==null || s.panel.stage==null || s.panel.mcTileList==null || s.panel.mcTileList.mGridLayout!==this ||
               event==null || event.currentTarget==null || s.ready[event.currentTarget]!==j.generation)return true;
            return ApexGridFreshInput(s,j);
         }
         if(kind=="redraw") {
            if(j.phase=="done" && !j.dirty && event!=null && s.ready[event.currentTarget]===j.generation)return false;
            ApexTxnNotify(j,"position");return true;
         }
         if(kind=="bounds") {if(event!=null)mCellBounds=event as Rectangle;ApexTxnNotify(j,"position");return true;}
         if(kind=="padding") {if(event!=null)mCellMargin=event as Margin;ApexTxnNotify(j,"position");return true;}
         if(kind=="position" || kind=="reset" || kind=="profile") {
            if(j.phase=="done")ApexTxnNotify(j,"update");else ApexTxnNotify(j,"position");
            return true;
         }
         if(kind=="scroll") {
            if(event!=null && event.mRect!=null && Number(event.mRect.y)!=-Number(j.plan==null?0:j.plan.scrollY)) {
               var desired:Object={columns:j.desired.columns,width:j.desired.width,height:j.desired.height,
                  gapX:j.desired.gapX,gapY:j.desired.gapY,viewHeight:j.desired.viewHeight,viewWidth:j.desired.viewWidth,
                  scrollY:-Number(event.mRect.y),marginX:j.desired.marginX,marginY:j.desired.marginY};
               ApexTxnRequest(j,desired);
            }
            return true;
         }
         if(event!=null && event.currentTarget!=null && event.currentTarget!==mGridData)return true;
         if(kind=="add")AddSortedData(event as DataFeedEvent);
         else if(kind=="front") {
            if(mNumLines>1)throw new Error("Cannot add multi-line recycling feed to front");
            AddSortedDataToFront(event as DataFeedEvent);
         }
         else if(kind=="remove") {
            if(GetSortedIndexOfDataIndex(event.mIndicesArray[0])!=-1)RemoveSortedData(event as DataFeedEvent);
         }
         else if(kind=="sort")mSortedIndexToDataIndex=event.mIndicesArray;
         else if(kind=="removeAll")mSortedIndexToDataIndex=null;
         else if(kind!="update")throw new Error("Unknown native grid guard");
         s.revision++;
         ApexTxnNotify(j,kind=="front"?"add":kind);
         return true;
      }
'''


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inject(source):
    if 'apexGridState' in source:
        raise ValueError('Native grid transaction already present.')
    imports = ('flash.display.Sprite', 'flash.utils.Dictionary', 'flash.utils.getTimer',
               'olympus.data.SelectableArrayDataFeed', 'olympus.extensions.Selectability',
               'olympus.interfaces.IExtendable')
    at = source.index('   public class RecyclingGridLayout')
    source = source[:at] + ''.join('   import ' + name + ';\n' for name in imports
                                 if 'import ' + name + ';' not in source) + source[at:]
    close = source.rfind('\n   }')
    if close < 0:
        raise ValueError('Native recycling class closing boundary differs.')
    return source[:close] + '\n' + ADAPTER_METHODS + '\n' + CORE_METHODS + source[close:]


def run(args, log):
    result = subprocess.run([str(x) for x in args], cwd=ROOT, capture_output=True,
                            text=True, encoding='utf-8', errors='replace', timeout=240)
    Path(log).write_text(result.stdout + result.stderr, encoding='utf-8')
    if result.returncode:
        raise ValueError('Native grid transaction compilation failed: ' + (result.stdout + result.stderr)[-2400:])


def adapt(original_swf, baseline_swf, source_path, ffdec, work):
    """Consume the retained getter/profiler baseline, return chained ABC/proof."""
    original_swf, ffdec, work = map(Path, (original_swf, ffdec, work))
    provider = PROVIDERS.get(digest(original_swf.read_bytes()))
    if provider is None:
        raise ValueError('Unsupported native grid provider.')
    work.mkdir(parents=True, exist_ok=True)
    baseline = work / 'baseline.swf';baseline.write_bytes(baseline_swf)
    if source_path is None:
        exported = work / 'private-source'
        run([ffdec, '-selectclass', TARGET, '-export', 'script', exported, baseline], work / 'export.log')
        source_path = exported / 'scripts/olympus/layout/RecyclingGridLayout.as'
    source_path = Path(source_path)
    owned = work / 'RecyclingGridLayout.as'
    owned.write_text(inject(source_path.read_text(encoding='utf-8')), encoding='utf-8')
    compiled = work / 'compiled.swf'
    run([ffdec, '-importAssets', 'yes,local', '-replace', baseline, compiled, TARGET, owned], work / 'ffdec.log')
    classes = work / 'classes';classes.mkdir(exist_ok=True)
    jar = ffdec.with_name('ffdec.jar')
    run(['javac', '-cp', jar, '-d', classes, ROOT / 'tools/CasStructuralRolesPatch.java',
         ROOT / 'tools/CasGridBytecodePatch.java', ROOT / 'tools/CasGridTransactionPatch.java'], work / 'javac.log')
    abc, proof = work / 'retained.abc', work / 'proof.json'
    run(['java', '-cp', str(jar) + os.pathsep + str(classes), 'CasGridTransactionPatch',
         original_swf, baseline, compiled, abc, proof], work / 'transplant.log')
    contract = json.loads(proof.read_text(encoding='utf-8'))
    data = abc.read_bytes()
    if contract.get('ok') is not True or contract.get('abc_sha256') != digest(data):
        raise ValueError('Native grid transaction bytecode proof differs.')
    contract['provider_resource_tgi'] = provider
    contract['source_sha256'] = {name: digest((ROOT / name).read_bytes()) for name in
        ('tools/CasGridTransactionPatch.java', 'tools/cas_grid_transaction.py', 'tools/CasStructuralRolesPatch.java', 'tools/CasGridBytecodePatch.java')}
    return data, contract


def chain_adapter(base_adapter, transaction, final_swf):
    """Retain the getter/profile proof as history; authenticate the final ABC."""
    from cas_ui_build import tags, unpack
    native = base_adapter.get('native_bytecode_contract', {})
    required = ('whole_abc_rollback_verified', 'serialized_projection_verified',
                'protected_field_namespace_bindings_verified', 'explicit_jump_switch_exception_fixtures',
                'unarmed_original_native_flow_verified')
    if (transaction.get('ok') is not True or any(transaction.get(k) is not True for k in required) or
            transaction.get('base_provider_sha256') != base_adapter.get('base_resource_sha256') or
            transaction.get('baseline_swf_sha256') != base_adapter.get('patched_resource_sha256') or
            transaction.get('provider_resource_tgi') != native.get('provider_resource_tgi') or
            transaction.get('original_method_info_count') != native.get('native_method_count') or
            transaction.get('guarded_native_bodies') != 18 or
            transaction.get('guarded_original_native_bodies') != 17 or
            transaction.get('guarded_existing_adapter_bodies') != 1 or
            transaction.get('appended_fields') != 1 or transaction.get('appended_methods') != 45 or
            transaction.get('unchanged_original_native_bodies') != transaction.get('original_method_body_count', 0) - 17 or
            transaction.get('unchanged_baseline_bodies') != transaction.get('baseline_method_body_count', 0) - 18):
        raise ValueError('Native transaction cannot chain to the retained provider proof.')
    abc = [t[3] for t in tags(unpack(final_swf)[1]) if t[0] == 82]
    if len(abc) != 1 or digest(abc[0][abc[0].index(b'\0', 4) + 1:]) != transaction.get('abc_sha256'):
        raise ValueError('Final provider does not contain the verified transaction ABC.')
    return dict(base_resource_sha256=base_adapter['base_resource_sha256'],
                patched_resource_sha256=digest(final_swf),
                retained_base_adapter=base_adapter,
                native_bytecode_contract=transaction)


def verify_adapter(adapter, final_swf):
    if not isinstance(adapter, dict) or not isinstance(adapter.get('retained_base_adapter'), dict):
        raise ValueError('Native transaction retained-provider proof is absent.')
    if chain_adapter(adapter['retained_base_adapter'], adapter.get('native_bytecode_contract', {}), final_swf) != adapter:
        raise ValueError('Final native provider proof differs.')
    return True

CORE_METHODS = r"""private function ApexTxnBegin(a:Object, request:Object) : Object
      {
         var j:Object={adapter:a,identity:a.ApexGridIdentity(),desired:null,plan:null,phase:"acquire",generation:0,
            revision:-1,dirty:true,running:false,publishing:false,cancelled:false,reason:"",lease:false,
            pendingCell:null,pendingAttached:false,index:0,target:0,operations:0,coalesced:0,reentrant:0,
            publishes:0,staleBinds:0,boundCell:null,boundSlot:-1,boundSorted:-1,boundData:-1,
            boundGeneration:0,boundRevision:-1,boundPresent:false,boundBase:null,boundVariation:null,boundBody:-1,boundMenu:-1,
            phaseCounts:{},phaseMax:{},lastPhase:"",lastOperation:"",error:null};
         ApexTxnInvariant(j);
         ApexTxnRequest(j,request);
         return j;
      }

private function ApexTxnRequest(j:Object, request:Object) : void
      {
         if(j.cancelled)return;
         var r:Object={columns:int(request.columns),width:Number(request.width),height:Number(request.height),
            gapX:Number(request.gapX),gapY:Number(request.gapY),viewHeight:Number(request.viewHeight),
            viewWidth:Number(request.viewWidth),scrollY:Number(request.scrollY),
            marginX:Number(request.marginX),marginY:Number(request.marginY)};
         if(r.columns<1 || r.columns>256 || !isFinite(r.width) || r.width<=0 || !isFinite(r.height) || r.height<=0 ||
            !isFinite(r.gapX) || r.gapX<0 || !isFinite(r.gapY) || r.gapY<0 ||
            !isFinite(r.viewWidth) || r.viewWidth<=0 || !isFinite(r.viewHeight) || r.viewHeight<=0 ||
            !isFinite(r.scrollY) || !isFinite(r.marginX) || !isFinite(r.marginY))throw new Error("Invalid grid geometry");
         var signature:String=[r.columns,r.width,r.height,r.gapX,r.gapY,r.viewHeight,r.viewWidth,r.scrollY,r.marginX,r.marginY].join(":");
         if(j.desired!=null && j.desired.signature==signature){j.coalesced++;return;}
         r.signature=signature;j.desired=r;j.dirty=true;
         if(j.phase=="done")j.phase="acquire";
      }

private function ApexTxnNotify(j:Object, kind:String, request:Object=null) : void
      {
         if(j.cancelled)return;
         if(kind=="owner" || kind=="dispose"){ApexTxnCancel(j,kind);return;}
         if(kind=="resize" || kind=="position" || kind=="scroll") {
            j.coalesced++;
            if(request!=null)ApexTxnRequest(j,request);
            return;
         }
         if(kind!="add" && kind!="update" && kind!="remove" && kind!="removeAll" && kind!="sort" && kind!="selection")
            throw new Error("Unknown grid notification");
         // Native adapter must perform sorted/feed bookkeeping BEFORE notifying.
         j.dirty=true;
         if(j.phase=="done")j.phase="acquire";
      }

private function ApexTxnCancel(j:Object, reason:String) : void
      {
         if(j.cancelled)return;
         j.cancelled=true;j.reason=reason;j.phase="cancel";j.boundCell=null;
      }

private function ApexTxnInvariant(j:Object) : void
      {
         var a:Object=j.adapter;
         if(a.ApexGridCells.length!=a.ApexGridCellsY.length || a.ApexGridCells.length!=a.ApexGridMap.length)throw new Error("Native grid arrays diverged");
      }

private function ApexTxnPlan(j:Object) : void
      {
         var a:Object=j.adapter;
         var r:Object=j.desired;
         var n:int=int(a.ApexGridCount());
         if(n<0)throw new Error("Invalid native feed length");
         var px:Number=r.width+r.gapX;
         var py:Number=r.height+r.gapY;
         var logicalRows:int=Math.ceil(n/r.columns);
         var visibleRows:int=Math.ceil(r.viewHeight/py);
         var rows:int=n==0 ? 0 : Math.min(visibleRows+1,logicalRows);
         var range:Number=Math.max(0,logicalRows*py-r.viewHeight);
         var scroll:Number=Math.max(0,Math.min(range,r.scrollY));
         var firstRow:int=Math.floor(scroll/py);
         j.plan={columns:r.columns,width:r.width,height:r.height,gapX:r.gapX,gapY:r.gapY,
            viewWidth:r.viewWidth,viewHeight:r.viewHeight,marginX:r.marginX,marginY:r.marginY,
            pitchX:px,pitchY:py,feedCount:n,logicalRows:logicalRows,rows:rows,
            target:rows*r.columns,range:range,scrollY:scroll,first:firstRow*r.columns,
            originY:r.marginY-(scroll-firstRow*py),signature:r.signature};
         // Confirmed metrics are keyed to native state/class/revision/scale,
         // not this transient geometry generation (see ApexGridMetrics).
         j.boundCell=null;
         j.target=j.plan.target;j.revision=a.ApexGridRevision();j.generation++;j.index=0;j.dirty=false;j.phase="configure";
      }

private function ApexTxnAdvance(j:Object) : Boolean
      {
         var a:Object=j.adapter;
         var c:Object=null;
         var slot:int=0;
         if(j.phase=="cancel") {
            if(apexGridState.retiringCell!=null) {
               j.lastOperation="cleanupRetire";a.ApexGridDetach(apexGridState.retiringCell);
               apexGridState.retiringCell=null;return true;
            }
            if(j.pendingCell!=null) {
               c=j.pendingCell;
               j.lastOperation=j.pendingAttached ? "cleanupAttach" : "cleanupConstruct";
               // One cleanup atom, including any native removed-stage callbacks.
               if(j.pendingAttached)a.ApexGridDetach(c);else a.ApexGridDiscard(c);
               j.pendingCell=null;j.pendingAttached=false;
               return true;
            }
            if(j.lease) {
               if(a.ApexGridOwns(j))a.ApexGridRelease(j);
               j.lease=false;
            }
            // Adapter queues bounded recovery for a still-live owner, or retires
            // a disposed owner. It must NEVER call native bulk Reset here.
            j.lastOperation="abort";a.ApexGridAbort(j,j.reason);j.phase="cancelled";return true;
         }
         if(j.phase=="acquire") {
            j.lastOperation="acquire";
            if(!a.ApexGridAcquire(j))return false;
            j.lease=true;
            a.ApexGridGate(j,true);
            ApexTxnPlan(j);
            return true;
         }
         if(j.phase=="configure") {
            j.lastOperation="configure";
            a.ApexGridConfigure(j.plan,j);
            j.phase="capacity";
            return true;
         }
         if(j.phase=="capacity") {
            if(apexGridState.retireAll || a.ApexGridCells.length>j.target ||
               j.target>0 && j.pendingCell!=null && a.ApexGridCells.length>=j.target) {
               if(a.ApexGridCells.length>0) {
                  j.lastOperation="retire";c=a.ApexGridCells[a.ApexGridCells.length-1];
                  a.ApexGridCells.pop();a.ApexGridCellsY.pop();a.ApexGridMap.pop();
                  // A measured pending cell is retained while old cells retire.
                  apexGridState.retiringCell=c;a.ApexGridDetach(c);apexGridState.retiringCell=null;return true;
               }
               if(apexGridState.retireAll){j.lastOperation="cellClass";ApexGridCommitClass();return true;}
            }
            if(j.pendingCell!=null) {
               if(j.target==0){j.index=0;j.phase="position";return false;}
               j.lastOperation="attach";
               c=j.pendingCell;j.pendingAttached=true;a.ApexGridAttach(c);
               if(j.cancelled || !a.ApexGridValid(j.identity)){ApexTxnCancel(j,"context");return true;}
               // No callback or yield between these three mutations.
               var length:int=a.ApexGridCells.length;
               try {a.ApexGridCells.push(c);a.ApexGridCellsY.push(0);a.ApexGridMap.push(-1);}
               catch(error:Error) {
                  a.ApexGridCells.length=length;a.ApexGridCellsY.length=length;a.ApexGridMap.length=length;
                  throw error;
               }
               j.pendingCell=null;j.pendingAttached=false;
               return true;
            }
            if(a.ApexGridCells.length>j.target || apexGridState.retireAll && a.ApexGridCells.length>0) {
               j.lastOperation="retire";
               c=a.ApexGridCells[a.ApexGridCells.length-1];
               a.ApexGridCells.pop();a.ApexGridCellsY.pop();a.ApexGridMap.pop();
               j.pendingCell=c;j.pendingAttached=true;
               a.ApexGridDetach(c);j.pendingCell=null;j.pendingAttached=false;
               return true;
            }
            if(apexGridState.retireAll && a.ApexGridCells.length==0){j.lastOperation="cellClass";ApexGridCommitClass();return true;}
            if(a.ApexGridCells.length<j.target) {
               j.lastOperation="construct";
               c=a.ApexGridCreate();
               if(c==null)throw new Error("Native cell factory returned null");
               j.pendingCell=c;j.pendingAttached=false;
               return true;
            }
            j.index=0;j.phase="position";return false;
         }
         if(j.phase=="position") {
            if(j.index>=a.ApexGridCells.length){j.index=0;j.phase="bind";return false;}
            slot=j.index;c=a.ApexGridCells[slot];
            j.lastOperation="position";
            var y:Number=j.plan.originY+Math.floor(slot/j.plan.columns)*j.plan.pitchY;
            var x:Number=j.plan.marginX+(slot%j.plan.columns)*j.plan.pitchX;
            a.ApexGridPosition(c,x,y,j.plan,j);
            a.ApexGridCellsY[slot]=y;
            // Map values are SORTED indices, matching the native recycling map.
            a.ApexGridMap[slot]=j.plan.first+slot;
            j.index++;
            return true;
         }
         if(j.phase=="bind") {
            if(j.index>=a.ApexGridCells.length){j.phase="publish";return false;}
            slot=j.index;c=a.ApexGridCells[slot];
            j.lastOperation="bind";
            // Draw and Selectability run in different budgeted atoms.
            a.ApexGridBind(c,a.ApexGridMap[slot],j.generation,j);
            if(j.cancelled || !a.ApexGridValid(j.identity)){ApexTxnCancel(j,"context");return true;}
            if(j.dirty || a.ApexGridRevision()!=j.revision || j.boundCell!==c){j.staleBinds++;j.dirty=true;return true;}
            j.phase="selection";return true;
         }
         if(j.phase=="selection") {
            slot=j.index;c=a.ApexGridCells[slot];j.lastOperation="selection";
            a.ApexGridReady(c,j.generation);
            if(j.cancelled || !a.ApexGridValid(j.identity)){ApexTxnCancel(j,"context");return true;}
            if(j.dirty || a.ApexGridRevision()!=j.revision || j.boundCell!=null){j.staleBinds++;j.dirty=true;return true;}
            j.index++;j.phase="bind";return true;
         }
         if(j.phase=="publish") {
            if(j.dirty || a.ApexGridRevision()!=j.revision){j.dirty=true;return false;}
            j.publishing=true;
            j.lastOperation="publish";
            try {a.ApexGridPublish(j.plan,j);} finally {j.publishing=false;}
            j.publishes++;
            if(j.cancelled || !a.ApexGridValid(j.identity)){ApexTxnCancel(j,"context");return true;}
            if(j.dirty || a.ApexGridRevision()!=j.revision){j.dirty=true;return true;}
            // Native RESIZE feedback occurs under the lease. No full reset or
            // selection pass is allowed to escape from that feedback.
            if(!a.ApexGridOwns(j))throw new Error("Grid suppression ownership was lost");
            a.ApexGridRelease(j);j.lease=false;
            a.ApexGridGate(j,false);j.phase="done";
            return true;
         }
         return false;
      }

private function ApexTxnStep(j:Object, maxOperations:int=1, deadline:Number=0) : Object
      {
         if(j.running){j.reentrant++;return ApexTxnStatus(j);}
         if(j.phase=="done" && !j.dirty && j.adapter.ApexGridRevision()==j.revision)return ApexTxnStatus(j);
         if(j.phase=="done"){j.dirty=true;j.phase="acquire";}
         if(j.phase=="cancelled")return ApexTxnStatus(j);
         if(maxOperations<1 || maxOperations>64)throw new Error("Invalid transaction operation budget");
         j.running=true;
         try {
            var a:Object=j.adapter;
            var used:int=0;
            var transitions:int=0;
            while(used<maxOperations && transitions++<128) {
               ApexTxnInvariant(j);
               if(j.phase=="cancelled" || (j.phase=="done" && !j.dirty))break;
               if(!j.cancelled && !a.ApexGridValid(j.identity))ApexTxnCancel(j,"context");
               if(!j.cancelled && j.lease && !a.ApexGridOwns(j))ApexTxnCancel(j,"lease");
               if(deadline>0 && a.ApexGridNow()>=deadline)break;
               if(!j.cancelled && j.phase!="acquire" && (j.dirty || a.ApexGridRevision()!=j.revision)) {
                  if(!j.lease){j.phase="acquire";}else ApexTxnPlan(j);
               }
               var before:String=j.phase;
               var started:Number=a.ApexGridNow();
               var performed:Boolean=ApexTxnAdvance(j);
               if(j.abandoned){j.pendingCell=null;j.pendingAttached=false;j.phase="cancelled";}
               ApexTxnInvariant(j);
               if(performed) {
                  used++;j.operations++;j.lastPhase=before;
                  j.phaseCounts[j.lastOperation]=int(j.phaseCounts[j.lastOperation])+1;
                  j.phaseMax[j.lastOperation]=Math.max(Number(j.phaseMax[j.lastOperation])||0,a.ApexGridNow()-started);
               } else if(j.phase==before)break;
            }
         } catch(error:Error) {
            j.error=String(error);ApexTxnCancel(j,"error");
            ApexTxnInvariant(j);
         } finally {j.running=false;}
         return ApexTxnStatus(j);
      }

private function ApexTxnStatus(j:Object) : Object
      {
         ApexTxnInvariant(j);
         return {phase:j.phase,generation:j.generation,revision:j.revision,target:j.target,
            cells:j.adapter.ApexGridCells.length,cellsY:j.adapter.ApexGridCellsY.length,map:j.adapter.ApexGridMap.length,
            index:j.index,pendingCell:j.pendingCell!=null,dirty:j.dirty,lease:j.lease,
            operations:j.operations,publishes:j.publishes,coalesced:j.coalesced,
            reentrant:j.reentrant,staleBinds:j.staleBinds,lastPhase:j.lastPhase,
            lastOperation:j.lastOperation,
            counts:{construct:int(j.phaseCounts.construct),attach:int(j.phaseCounts.attach),retire:int(j.phaseCounts.retire),
               position:int(j.phaseCounts.position),bind:int(j.phaseCounts.bind),selection:int(j.phaseCounts.selection),
               data:int(j.phaseCounts.data),draw:int(j.phaseCounts.draw),selected_setter:int(j.phaseCounts.selected_setter),
               publish:int(j.phaseCounts.publish)},
            maxMS:{construct:Number(j.phaseMax.construct)||0,attach:Number(j.phaseMax.attach)||0,retire:Number(j.phaseMax.retire)||0,
               position:Number(j.phaseMax.position)||0,bind:Number(j.phaseMax.bind)||0,selection:Number(j.phaseMax.selection)||0,
               data:Number(j.phaseMax.data)||0,draw:Number(j.phaseMax.draw)||0,selected_setter:Number(j.phaseMax.selected_setter)||0,
               publish:Number(j.phaseMax.publish)||0},
            error:j.error,cancelled:j.cancelled,reason:j.reason};
      }
"""
