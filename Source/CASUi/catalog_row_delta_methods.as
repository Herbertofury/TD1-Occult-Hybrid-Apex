      // Private compiled continuation with an exact Main producer. Unknown
      // native classes, extensions or data schemas keep the complete Draw path.
      private function ApexGridDeltaCapable() : Boolean {
         var s:Object=apexGridState;var r:Object=s==null ? null : s.request;
         return r!=null && r.rowDeltaReuseContract===1 &&
            r.rowDeltaFeedbackContract==="ea-complete-ready-before-resize-v1" &&
            r.rowDeltaRowValidate is Function && !("featuredRowIdentity" in r && r.featuredRowIdentity!=null) &&
            s.owner!=null && s.owner.cell_type===mCellType &&
            (s.owner.panel_kind=="clothing" || s.owner.panel_kind=="body" || s.owner.panel_kind=="face" || s.owner.panel_kind=="generic");
      }

      private function ApexGridDeltaCapture(cell:Object,generation:int,selected:Boolean) : void {
         if(!ApexGridDeltaCapable())return;
         var s:Object=apexGridState;var j:Object=s.job;var p:Object=s.presentation;
         if(p==null || !p.working || j.boundFeatured!=null)return;
         if(p.stageBindings==null || p.stageBindingGeneration!==generation) {p.stageBindings=new Dictionary(true);p.stageBindingGeneration=generation;}
         if(!j.boundPresent) {delete p.stageBindings[cell];return;}
         // The original Ready function has just revalidated the borrowed row
         // after selection callbacks. Store only its existing copied scalars.
         p.stageBindings[cell]={schema:"product-v1",generation:generation,revision:int(s.revision),sorted:int(j.boundSorted),data:int(j.boundData),
            base:String(j.boundBase),variation:String(j.boundVariation),body:int(j.boundBody),menu:int(j.boundMenu),selected:selected};
      }

      private function ApexGridDeltaCurrent(d:Object) : Boolean {
         var s:Object=apexGridState;var j:Object=d==null ? null : d.job;
         return d!=null && s===d.state && s.delta===d && s.job===j && !j.cancelled && !j.dirty &&
            j.revision==d.revision && s.revision==d.revision && s.owner===d.owner &&
            s.owner.active===true && int(s.owner.generation)==d.ownerGeneration &&
            s.feed===d.feed && mGridData===d.feed && s.view===d.view && mGridView===d.view &&
            mCellType===d.cellType && ApexGridDeltaCapable() && s.request.rowDeltaRowValidate===d.rowValidate &&
            ApexGridValid(j.identity) && ApexGridOwns(j);
      }

      private function ApexGridDeltaQueue(j:Object,r:Object) : Boolean {
         if(!ApexGridDeltaCapable())return false;
         var s:Object=apexGridState;var p:Object=j.plan;var presentation:Object=s.presentation;
         if(s.delta!=null)return ApexGridDeltaLatest(j,r);
         // Native wheel/SCROLL arrives between Main frames. Queue no display
         // mutation here; the next Step requires the fresh complete frame lease.
         if(!s.armed || s.job!==j || s.owner.active!==true || int(s.owner.generation)!=s.ownerGeneration ||
            s.feed!==mGridData || s.view!==mGridView || s.bootstrap || j.phase!="done" || j.cancelled || j.dirty || j.revision!=s.revision ||
            p==null || presentation==null || presentation.working || presentation.committedCells!==mCells ||
            presentation.committedBindings==null || presentation.committedExpected==null ||
            mCells.length!=j.target || mCells.length!=mCellsY.length || mCells.length!=mCellIndexToDataIndexMap.length ||
            j.target<=0 || Math.max(Number(j.generation),Number(s.deltaEpoch)||0)>=int.MAX_VALUE ||
            r.columns!=p.columns || r.width!==p.width || r.height!==p.height ||
            r.gapX!==p.gapX || r.gapY!==p.gapY || r.viewWidth!==p.viewWidth || r.viewHeight!==p.viewHeight ||
            r.marginX!==p.marginX || r.marginY!==p.marginY)return false;
         var raw:Number=Math.max(0,Math.min(Number(p.range),Number(r.scrollY)));
         var first:int=int(Math.floor(raw/Number(p.pitchY)))*int(p.columns);
         if(Math.abs(first-int(p.first))>=j.target || first<0 || first+j.target>p.feedCount ||
            p.first<0 || int(p.first)+j.target>p.feedCount)return false;
         var d:Object={state:s,job:j,owner:s.owner,ownerGeneration:int(s.owner.generation),feed:mGridData,view:mGridView,cellType:mCellType,
            rowValidate:s.request.rowDeltaRowValidate,
            revision:int(s.revision),oldPlan:p,desired:r,latest:null,cleaning:false,oldGeneration:int(j.generation),newGeneration:int(Math.max(Number(j.generation),Number(s.deltaEpoch)||0))+1,
            oldIndex:int(j.index),oldCells:mCells,oldY:mCellsY,oldMap:mCellIndexToDataIndexMap,oldReady:s.ready,
            oldExpected:presentation.committedExpected,oldBindings:presentation.committedBindings,oldSpare:presentation.spareCells,
            oldSpareY:presentation.spareY,oldSpareMap:presentation.spareMap,oldScroll:mPrevRectangleUpdate.y,
            oldHeight:s.measuredHeight,oldAspect:s.measuredAspect,oldMeasuredGeneration:s.measuredGeneration,
            oldMeasuredScale:s.measuredScale,oldMeasuredRevision:s.measuredRevision,oldMeasuredClass:s.measuredClass,
            first:first,raw:raw,origin:Number(p.marginY)-(raw-Math.floor(raw/Number(p.pitchY))*Number(p.pitchY)),
            index:0,phase:"acquire",stockUsed:0,created:new Vector.<IView>(),
            cells:new Vector.<IView>(j.target),ys:new Vector.<Number>(j.target),map:new Vector.<int>(j.target),
            borrowed:new Dictionary(true),entering:new Dictionary(true),members:new Dictionary(true),
            oldVisible:new Dictionary(true),oldPositions:new Dictionary(true),bindings:new Dictionary(true),expected:new Dictionary(true),
            touched:false,borrowCount:0,enterCount:0,feedback:0};
         s.deltaEpoch=d.newGeneration;s.delta=d;j.desired=r;j.phase="row-delta";
         return true;
      }

      private function ApexGridDeltaLatest(j:Object,r:Object) : Boolean {
         // Only primitive request bookkeeping in native wheel/SCROLL callbacks.
         // No native getter, display write, lease validation or rollback here.
         var s:Object=apexGridState;var d:Object=s==null ? null : s.delta;
         var p:Object=d==null ? null : d.oldPlan;
         if(d==null || s.job!==j || d.job!==j || d.state!==s || j.cancelled || j.dirty ||
            s.revision!=d.revision || j.revision!=d.revision || s.owner!==d.owner || s.owner.active!==true ||
            int(s.owner.generation)!=d.ownerGeneration || s.feed!==d.feed || mGridData!==d.feed ||
            s.view!==d.view || mGridView!==d.view || mCellType!==d.cellType ||
            r.columns!=p.columns || r.width!==p.width || r.height!==p.height ||
            r.gapX!==p.gapX || r.gapY!==p.gapY || r.viewWidth!==p.viewWidth || r.viewHeight!==p.viewHeight ||
            r.marginX!==p.marginX || r.marginY!==p.marginY)return false;
         d.latest=!d.cleaning && r.signature===d.desired.signature ? null : r;
         j.desired=r;return true;
      }

      private function ApexGridDeltaRetarget(d:Object) : Boolean {
         var s:Object=apexGridState;var j:Object=d.job;var p:Object=s.presentation;var cell:Object=null;
         if(d.phase=="retarget-spares") {
            if(d.cleanIndex<d.stockUsed) {
               cell=d.oldSpare[d.cleanIndex++];
               if(cell==null || cell.parent!==d.view || s.intrinsics[cell]==null || s.intrinsics[cell].type!==d.cellType)
                  throw new Error("Retarget spare custody changed");
               if(cell.visible!==false)cell.visible=false;
               return true;
            }
            d.cleanIndex=0;d.phase="retarget-created";return true;
         }
         if(d.phase=="retarget-created") {
            if(d.cleanIndex<d.created.length) {
               cell=d.created[d.cleanIndex++];
               if(cell===j.pendingCell && !j.pendingAttached && cell.parent==null) {
                  // Original discard only removes our ready/pool/intrinsic keys.
                  ApexGridDiscard(cell);j.pendingCell=null;j.pendingAttached=false;d.cleanedCreated[cell]=true;return true;
               }
               if(cell==null || cell.parent!==d.view || s.intrinsics[cell]==null || s.intrinsics[cell].type!==d.cellType)
                  throw new Error("Retarget constructed widget custody changed");
               if(cell.visible!==false)cell.visible=false;
               if(!ApexGridDeltaCurrent(d))return true;
               d.oldSpare.push(cell as IView);d.cleanedCreated[cell]=true;
               if(cell===j.pendingCell){j.pendingCell=null;j.pendingAttached=false;}
               return true;
            }
            d.phase="retarget-finish";return true;
         }
         if(d.phase!="retarget-finish")throw new Error("Unknown retarget phase");
         if(!ApexGridDeltaCurrent(d))return false;
         var latest:Object=d.latest==null ? d.restart : d.latest;
         // Borrowed committed widgets have never been mutated. Restore only
         // metadata, not their native display properties, and keep input gated.
         mCells=d.oldCells;mCellsY=d.oldY;mCellIndexToDataIndexMap=d.oldMap;s.ready=d.oldReady;
         s.measuredHeight=d.oldHeight;s.measuredAspect=d.oldAspect;s.measuredGeneration=d.oldMeasuredGeneration;
         s.measuredScale=d.oldMeasuredScale;s.measuredRevision=d.oldMeasuredRevision;s.measuredClass=d.oldMeasuredClass;
         p.spareCells=d.oldSpare;p.spareY=new Vector.<Number>(d.oldSpare.length);p.spareMap=new Vector.<int>(d.oldSpare.length);
         p.stageCells=null;p.stageY=null;p.stageMap=null;p.stageBindings=null;p.expected=new Dictionary(true);p.images=new Dictionary(true);p.working=false;
         p.committedExpected=d.oldExpected;p.committedBindings=d.oldBindings;p.committedCells=d.oldCells;p.committedY=d.oldY;p.committedMap=d.oldMap;p.committedReady=d.oldReady;
         j.plan=d.oldPlan;j.generation=d.oldGeneration;j.index=d.oldIndex;j.boundCell=null;j.desired=latest;j.phase="done";
         s.delta=null;j.deltaRetargets=int(j.deltaRetargets)+1;
         if(!ApexGridDeltaQueue(j,latest)) {j.generation=int(Math.max(Number(j.generation),Number(s.deltaEpoch)||0));j.dirty=true;j.phase="acquire";}
         return true;
      }

      private function ApexGridDeltaTexture(cell:Object,expected:Object) : Boolean {
         if(expected==null || cell==null || cell.mcImage==null)return false;
         if(expected.diagnostic) {
            var label:Object=cell.getChildByName("apexThumbnailFailure");
            return label!=null && label.parent===cell && label.visible && String(label.text).length>0;
         }
         // Read-only for visible borrowed art. Never LoadImage/fallback on it.
         return cell.mcImage.ApexImageReadyFor(expected.display)===true;
      }

      private function ApexGridDeltaBorrow(cell:Object,slot:int,d:Object) : Boolean {
         var s:Object=apexGridState;var j:Object=d.job;var old:int=int(d.first)+slot-int(d.oldPlan.first);
         var record:Object=d.oldBindings[cell];var expected:Object=d.oldExpected[cell];
         if(old<0 || old>=j.target || d.oldCells[old]!==cell || d.oldMap[old]!=int(d.first)+slot ||
            cell==null || cell.parent!==d.view || cell.visible!==true ||
            Number(cell.y)!==Number(d.oldY[old]) || d.oldReady[cell]!==d.oldGeneration ||
            record==null || record.schema!=="product-v1" || record.generation!==d.oldGeneration || record.revision!==d.revision ||
            record.sorted!==int(d.first)+slot || !ApexGridDeltaTexture(cell,expected))return false;
         var item:Object=GetDataAtIndex(int(d.first)+slot);
         if(item==null || apexGridState.request.rowDeltaRowValidate(item)!==true ||
            GetDataIndexOfSortedIndex(int(d.first)+slot)!==record.data || String(item.data_id)!==record.base ||
            String(item.GetVariationOrBaseId())!==record.variation || int(item.body_type)!==record.body || int(item.menu_state)!==record.menu ||
            "dccFavoriteProductId" in cell && cell.dccFavoriteProductId!==record.base)return false;
         var selectable:SelectableArrayDataFeed=mGridData as SelectableArrayDataFeed;
         var ext:Selectability=(cell as IExtendable).GetExtension(Selectability) as Selectability;
         if(selectable==null || ext==null || getQualifiedClassName(ext)!=="olympus.extensions::Selectability" ||
            ext.Selected!==record.selected || selectable.GetSelectionState(record.data)!==record.selected ||
            !ApexGridDeltaCurrent(d))return false;
         d.borrowed[cell]=old;d.members[cell]=true;d.oldVisible[cell]=Boolean(cell.visible);d.oldPositions[cell]=Number(cell.y);
         d.cells[slot]=cell;d.map[slot]=int(d.first)+slot;d.ys[slot]=d.origin+Math.floor(slot/int(d.oldPlan.columns))*Number(d.oldPlan.pitchY);
         d.bindings[cell]={schema:"product-v1",generation:d.newGeneration,revision:d.revision,sorted:int(d.first)+slot,data:int(record.data),
            base:String(record.base),variation:String(record.variation),body:int(record.body),menu:int(record.menu),selected:Boolean(record.selected)};
         d.expected[cell]={requested:String(expected.requested),display:String(expected.display),warning:Boolean(expected.warning),diagnostic:Boolean(expected.diagnostic)};
         s.ready[cell]=d.newGeneration;d.borrowCount++;return true;
      }

      private function ApexGridDeltaRestore(d:Object) : void {
         // Never overwrite a replacement authoritative state installed by a
         // reentrant callback. That state's guards own subsequent recovery.
         var s:Object=apexGridState;if(s!==d.state || s.delta!==d || s.job!==d.job)return;
         d.physicalReady=false;
         var j:Object=d.job;var p:Object=s.presentation;
         for each(var borrowed:Object in d.oldCells) {
            if(d.oldPositions[borrowed]!=null && borrowed.parent===d.view) {
               borrowed.y=Number(d.oldPositions[borrowed]);borrowed.visible=Boolean(d.oldVisible[borrowed]);
            }
         }
         for each(var incoming:Object in d.cells)if(incoming!=null && d.entering[incoming]===true && incoming.parent===d.view)incoming.visible=false;
         mCells=d.oldCells;mCellsY=d.oldY;mCellIndexToDataIndexMap=d.oldMap;mPrevRectangleUpdate.y=d.oldScroll;s.ready=d.oldReady;
         s.measuredHeight=d.oldHeight;s.measuredAspect=d.oldAspect;s.measuredGeneration=d.oldMeasuredGeneration;
         s.measuredScale=d.oldMeasuredScale;s.measuredRevision=d.oldMeasuredRevision;s.measuredClass=d.oldMeasuredClass;
         var spare:Vector.<IView> =new Vector.<IView>();
         for each(var oldSpare:Object in d.oldSpare)spare.push(oldSpare as IView);
         for each(var created:Object in d.created)if(created!==j.pendingCell && created.parent===d.view &&
            (d.cleanedCreated==null || d.cleanedCreated[created]!==true))spare.push(created as IView);
         p.spareCells=spare;p.spareY=new Vector.<Number>(spare.length);p.spareMap=new Vector.<int>(spare.length);
         p.stageCells=null;p.stageY=null;p.stageMap=null;p.stageBindings=null;p.expected=new Dictionary(true);p.images=new Dictionary(true);p.working=false;
         p.committedExpected=d.oldExpected;p.committedBindings=d.oldBindings;p.committedCells=d.oldCells;p.committedY=d.oldY;p.committedMap=d.oldMap;
         j.plan=d.oldPlan;j.generation=int(Math.max(Number(d.oldGeneration),Number(s.deltaEpoch)||0));j.index=d.oldIndex;j.boundCell=null;
         if(ApexGridOwns(j))ApexGridRelease(j);j.lease=false;s.delta=null;
         if(!j.cancelled) {j.dirty=true;j.phase="acquire";}
         if(ApexGridValid(j.identity))ApexGridGate(j,false);
      }

      private function ApexGridDeltaPublish(d:Object) : Boolean {
         var s:Object=apexGridState;var j:Object=d.job;var p:Object=s.presentation;
         for(var i:int=0;i<j.target;i++) {
            var cell:Object=d.cells[i];
            if(cell==null || s.ready[cell]!==d.newGeneration ||
               (d.entering[cell]===true ? !ApexGridPresentationTexture(cell) : !ApexGridDeltaTexture(cell,d.expected[cell])))return false;
         }
         if(!ApexGridDeltaCurrent(d))return false;
         mCells=d.cells;mCellsY=d.ys;mCellIndexToDataIndexMap=d.map;mPrevRectangleUpdate.y=-d.raw;
         // EA's completed scroll/PositionCells reference exposes a complete
         // ready logical/physical state before feedback. Native properties of
         // these exact classes have no scripted setters; no Draw/load/yield.
         for(i=0;i<j.target;i++) {cell=d.cells[i];if(d.entering[cell]!==true)cell.y=Number(d.ys[i]);}
         d.touched=true;
         for(i=0;i<j.target;i++) {cell=d.cells[i];if(d.entering[cell]===true)cell.visible=true;}
         for each(var leaving:Object in d.oldCells)if(d.members[leaving]!==true)leaving.visible=false;
         if(!ApexGridDeltaCurrent(d))return false;
         d.physicalReady=true;
         j.publishing=true;
         try {d.view.dispatchEvent(new GridEvent(GridEvent.RESIZE,null,[]));d.feedback++;}
         finally {j.publishing=false;d.physicalReady=false;}
         if(!ApexGridDeltaCurrent(d) || mCells!==d.cells || mCellsY!==d.ys || mCellIndexToDataIndexMap!==d.map)return false;
         for each(var preceding:Object in d.oldCells)if(d.members[preceding]!==true &&
            (preceding.parent!==d.view || preceding.visible!==false || Number(preceding.y)!==Number(d.oldPositions[preceding])))return false;
         for(i=0;i<j.target;i++) {
            cell=d.cells[i];
            if(cell.parent!==d.view || cell.visible!==true || Number(cell.y)!==Number(d.ys[i]) || s.ready[cell]!==d.newGeneration ||
               (d.entering[cell]===true ? !ApexGridPresentationTexture(cell) :
                !ApexGridDeltaTexture(cell,d.expected[cell])))return false;
         }
         if(!ApexGridDeltaCurrent(d))return false;
         var spare:Vector.<IView> =new Vector.<IView>();
         for each(var retired:Object in d.oldCells)if(d.members[retired]!==true)spare.push(retired as IView);
         for(i=d.stockUsed;i<d.oldSpare.length;i++)spare.push(d.oldSpare[i] as IView);
         p.spareCells=spare;p.spareY=new Vector.<Number>(spare.length);p.spareMap=new Vector.<int>(spare.length);
         p.committedCells=mCells;p.committedY=mCellsY;p.committedMap=mCellIndexToDataIndexMap;p.committedReady=s.ready;
         p.committedExpected=d.expected;p.committedBindings=d.bindings;p.stageCells=null;p.stageY=null;p.stageMap=null;p.stageBindings=null;
         p.failures=[];
         for(i=0;i<j.target;i++) {
            var failed:Object=d.expected[d.cells[i]];
            if(failed!=null && failed.warning && p.failures.length<32)
               p.failures.push({slot:i,requested_resource:String(failed.requested),ea_warning:true,text_diagnostic:Boolean(failed.diagnostic)});
         }
         p.expected=new Dictionary(true);p.images=new Dictionary(true);p.working=false;p.published=true;
         var old:Object=d.oldPlan;
         j.plan={columns:old.columns,width:old.width,height:old.height,gapX:old.gapX,gapY:old.gapY,viewWidth:old.viewWidth,viewHeight:old.viewHeight,
            marginX:old.marginX,marginY:old.marginY,pitchX:old.pitchX,pitchY:old.pitchY,feedCount:old.feedCount,logicalRows:old.logicalRows,
            rows:old.rows,target:old.target,range:old.range,scrollY:d.raw,first:d.first,originY:d.origin,signature:d.desired.signature};
         j.index=j.target;j.publishes++;j.deltaPublishes=int(j.deltaPublishes)+1;j.phase="done";j.desired=d.desired;
         if(ApexGridOwns(j))ApexGridRelease(j);j.lease=false;s.delta=null;
         if(d.latest!=null && !ApexGridDeltaQueue(j,d.latest)) {j.desired=d.latest;j.dirty=true;j.phase="acquire";}
         if(j.phase=="done")ApexGridGate(j,false);return true;
      }

      private function ApexGridDeltaAdvance(d:Object) : Boolean {
         var s:Object=apexGridState;var j:Object=d.job;var p:Object=s.presentation;var cell:Object=null;
         if(d.latest!=null && !d.cleaning && d.phase!="acquire" && !d.touched) {
            d.restart=d.latest;d.latest=null;d.cleaning=true;d.cleanIndex=0;d.cleanedCreated=new Dictionary(true);d.phase="retarget-spares";
         }
         if(d.cleaning)return ApexGridDeltaRetarget(d);
         if(d.phase=="acquire") {
            if(GetNumItems()!=d.oldPlan.feedCount || !ApexGridValid(j.identity) || s!==apexGridState || s.job!==j) {
               ApexGridDeltaRestore(d);return false;
            }
            if(!ApexGridAcquire(j))return false;j.lease=true;
            mGridView.mouseEnabled=false;mGridView.mouseChildren=false;
            p.committedReady=s.ready;p.committedVisible=new Dictionary(true);
            for each(var old:Object in d.oldCells) {
               p.committedVisible[old]=Boolean(old.visible);d.oldVisible[old]=Boolean(old.visible);d.oldPositions[old]=Number(old.y);
            }
            p.stageCells=d.cells;p.stageY=d.ys;p.stageMap=d.map;p.stageBindings=d.bindings;p.stageBindingGeneration=d.newGeneration;
            p.expected=d.expected;p.images=new Dictionary(true);p.working=true;
            s.ready=new Dictionary(true);j.generation=d.newGeneration;d.phase="plan";return true;
         }
         if(d.phase=="plan") {
            if(d.index>=j.target) {d.index=0;d.phase="textures";return true;}
            var slot:int=d.index;var sorted:int=int(d.first)+slot;var oldSlot:int=sorted-int(d.oldPlan.first);
            if(oldSlot>=0 && oldSlot<j.target) {
               if(!ApexGridDeltaBorrow(d.oldCells[oldSlot],slot,d)) {
                  s.deltaLastRefusal="Borrowed row identity/resource/extension requires full native path";
                  ApexGridDeltaRestore(d);return false;
               }
               d.index++;return true;
            }
            if(d.stockUsed<d.oldSpare.length) {
               cell=d.oldSpare[d.stockUsed++];
               var intrinsic:Object=s.intrinsics[cell];
               if(cell==null || cell.parent!==d.view || cell.visible || intrinsic==null || intrinsic.type!==mCellType)throw new Error("Delta spare ownership/class changed");
               d.cells[slot]=cell;d.phase="position";return true;
            }
            if(j.pendingCell==null) {
               cell=ApexGridCreate();j.pendingCell=cell;j.pendingAttached=false;d.created.push(cell as IView);
               if(cell.parent!=null)throw new Error("Constructed delta widget already has a foreign parent");
               cell.visible=false;d.phase="attach";return true;
            }
            throw new Error("Unowned delta construction pending");
         }
         if(d.phase=="attach") {
            cell=j.pendingCell;j.pendingAttached=true;ApexGridAttach(cell);
            if(!ApexGridDeltaCurrent(d))return true;
            d.cells[d.index]=cell;j.pendingCell=null;j.pendingAttached=false;d.phase="position";return true;
         }
         if(d.phase=="position") {
            cell=d.cells[d.index];d.entering[cell]=true;d.members[cell]=true;d.enterCount++;
            d.map[d.index]=int(d.first)+d.index;d.ys[d.index]=d.origin+Math.floor(d.index/int(d.oldPlan.columns))*Number(d.oldPlan.pitchY);
            j.index=d.index;ApexGridPosition(cell,Number(d.oldPlan.marginX)+(d.index%int(d.oldPlan.columns))*Number(d.oldPlan.pitchX),Number(d.ys[d.index]),d.oldPlan,j);
            d.phase="bind";return true;
         }
         if(d.phase=="bind") {
            cell=d.cells[d.index];j.index=d.index;ApexGridBind(cell,int(d.map[d.index]),d.newGeneration,j);
            j.phaseCounts.bind=int(j.phaseCounts.bind)+1;d.phase="selection";return true;
         }
         if(d.phase=="selection") {
            cell=d.cells[d.index];j.index=d.index;ApexGridReady(cell,d.newGeneration);j.phaseCounts.selection=int(j.phaseCounts.selection)+1;
            if(j.boundCell!=null || s.ready[cell]!==d.newGeneration)throw new Error("Entering row Ready fence refused");
            d.index++;d.phase="plan";return true;
         }
         if(d.phase=="textures") {
            if(d.index>=j.target) {d.phase="publish";return true;}
            cell=d.cells[d.index];
            if(d.entering[cell]===true) {if(!ApexGridPresentationTexture(cell))return false;}
            else if(!ApexGridDeltaTexture(cell,d.expected[cell])) {
               s.deltaLastRefusal="Committed texture changed while preparing delta";ApexGridDeltaRestore(d);return false;
            }
            d.index++;return true;
         }
         if(d.phase=="publish") {
            if(!ApexGridDeltaPublish(d)) {
               s.deltaLastRefusal="Delta feedback changed its complete ready owner/presentation";ApexGridDeltaRestore(d);return false;
            }
            return true;
         }
         throw new Error("Unknown delta phase");
      }

      private function ApexGridDeltaStep(maxOps:int) : Object {
         if(maxOps<1 || maxOps>64)throw new Error("Invalid delta operation budget");
         var s:Object=apexGridState;var d:Object=s.delta;var j:Object=d.job;
         if(j.running)return ApexGridStatus();
         var start:Number=ApexGridNow();var used:int=0;j.running=true;
         try {
            while(used<maxOps && s.delta===d) {
               if(j.cancelled || j.dirty || s.revision!=d.revision || s!==apexGridState ||
                  (d.phase!="acquire" && !ApexGridDeltaCurrent(d)) || !ApexGridValid(j.identity)) {
                  ApexGridDeltaRestore(d);break;
               }
               if(used>0 && uint(ApexGridNow()-start)>=1)break;
               if(!ApexGridDeltaAdvance(d))break;
               used++;j.operations++;
            }
         } catch(deltaError:*) {
            try {d.failure=String(deltaError);s.deltaLastError=d.failure;}catch(diagnosticError:*) { }
            try {ApexGridDeltaRestore(d);}catch(restoreError:*) { }
            // Match the original core Error boundary; arbitrary native thrown
            // values propagate unchanged after best-effort held-state cleanup.
            if(!(deltaError is Error))throw deltaError;
            j.error=String(deltaError);ApexTxnCancel(j,"error");
         } finally {j.running=false;}
         return ApexGridStatus();
      }
