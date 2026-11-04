      // A native width setter changes only its proxy/mask before emitting the
      // intercepted PositionCells/SCROLL pair. Keep that geometry wake pending
      // until Main supplies a fresh complete owner-bound request. No card,
      // input, image, feed, sorted map or appearance is changed in this callback.
      private function ApexGridWidthWake(j:Object) : Boolean {
         var s:Object=apexGridState;var p:Object=j==null ? null : j.plan;
         if(s==null || s.job!==j || !s.armed || s.bootstrap || s.request==null || s.request.viewWidthTransferContract!==1 ||
            !ApexGridDeltaCapable() || s.lease!=null || mbSuppressUpdates || s.externalSuppression || j.cancelled || j.dirty || j.phase!="done" || j.revision!=s.revision ||
            p==null || s.owner==null || !s.owner.active || int(s.owner.generation)!=s.ownerGeneration ||
            s.owner.cell_type!==mCellType || s.feed!==mGridData || s.view!==mGridView ||
            s.pendingClass!=null || s.pendingMargin!=null || s.pendingRedraw===true ||
            s.delta!=null && s.delta.widthTransfer!==true || s.presentation==null || s.presentation.working ||
            s.presentation.committedCells!==mCells || s.presentation.committedReady!==s.ready ||
            Number(mGridView.height)!==Number(p.viewHeight))return false;
         var width:Number=Number(mGridView.width);
         if(!isFinite(width) || width<=0 || width===Number(p.viewWidth))return false;
         var counters:Object=ApexGridWidthCounters();if(counters==null || apexGridState!==s || s.job!==j || j.plan!==p || s.view!==mGridView || s.feed!==mGridData || s.owner==null || s.owner.cell_type!==mCellType)return false;
         s.widthWake={job:j,plan:p,generation:int(j.generation),revision:int(s.revision),width:width,height:Number(p.viewHeight),counters:counters};
         return true;
      }

      private function ApexGridWidthCounters() : Object {
         var s:Object=apexGridState;if(s==null)return null;var values:Object={};
         for each(var key:String in ["reset","profile","bounds","padding","redraw","selection","update","add","front","remove","removeAll","sort","unknown"]) {
            var n:int=int(s["nativeEvent_"+key]);if(n<0 || n>=int.MAX_VALUE)return null;values[key]=n;
         }
         return values;
      }

      private function ApexGridWidthCurrent(d:Object) : Boolean {
         if(!ApexGridAuthorityCurrent(d))return false;
         var s:Object=apexGridState;var j:Object=d.job;var p:Object=d.oldPlan;var r:Object=d.desired;
         if(s.lease!=null || mbSuppressUpdates || s.externalSuppression || j.cancelled || j.dirty || j.phase!="done" || j.plan!==p || j.generation!==d.oldGeneration || j.revision!=d.revision ||
            s.revision!=d.revision || s.request==null || s.request.viewWidthTransferContract!==1 ||
            s.owner.active!==true || int(s.owner.generation)!=d.ownerGeneration || !ApexGridDeltaCapable() ||
            s.pendingClass!=null || s.pendingMargin!=null || s.pendingRedraw===true ||
            s.widthWake!==d.wake || Number(mGridView.width)!==Number(r.viewWidth) || Number(mGridView.height)!==Number(r.viewHeight))return false;
         for each(var key:String in ["reset","profile","bounds","padding","redraw","selection","update","add","front","remove","removeAll","sort","unknown"])
            if(int(s["nativeEvent_"+key])!==int(d.wake.counters[key]))return false;
         var scope:Object=d.eofScope;var owner:Object=d.owner;
         for each(var scopeKey:String in ["sim_id","household_id","owner","session","layer","native_kind","shell_kind","native_mask","native_generation","outfit_type","outfit_index","state"])
            if(owner[scopeKey]!==scope[scopeKey])return false;
         return ApexGridAuthorityCurrent(d);
      }

      private function ApexGridWidthTry(j:Object,r:Object) : Boolean {
         var s:Object=apexGridState;if(s==null || s.job!==j)return false;
         if(s.delta!=null && s.delta.widthTransfer===true) {s.delta.latest=r;return true;}
         var wake:Object=s.widthWake;var p:Object=j.plan;var presentation:Object=s.presentation;
         if(wake==null)return false;
         // Unknown/stale geometry stays on the complete original path. A wake
         // never licenses a changed row, layout, scale, class, owner or feed.
         if(s.request==null || s.request.viewWidthTransferContract!==1 || !ApexGridDeltaCapable() || s.bootstrap ||
            wake.job!==j || wake.plan!==p || wake.generation!==j.generation || wake.revision!==s.revision ||
            s.lease!=null || mbSuppressUpdates || s.externalSuppression || j.running || j.cancelled || j.dirty || j.phase!="done" || p==null || j.revision!=s.revision ||
            j.index!=j.target || j.boundCell!=null || j.pendingCell!=null || s.delta!=null ||
            presentation==null || presentation.working || presentation.committedCells!==mCells ||
            presentation.committedY!==mCellsY || presentation.committedMap!==mCellIndexToDataIndexMap ||
            presentation.committedReady!==s.ready || presentation.committedBindings==null || presentation.committedExpected==null ||
            mCells.length!=j.target || mCellsY.length!=j.target || mCellIndexToDataIndexMap.length!=j.target ||
            r.columns!=p.columns || r.width!==p.width || r.height!==p.height || r.gapX!==p.gapX || r.gapY!==p.gapY ||
            r.viewHeight!==p.viewHeight || r.marginX!==p.marginX || r.marginY!==p.marginY || r.scrollY!==p.scrollY ||
            Number(s.request.scale)!==Number(s.measuredScale) || s.measuredClass!==mCellType || s.measuredRevision!=s.revision ||
            r.viewWidth!==wake.width || Number(mGridView.width)!==r.viewWidth || Number(mGridView.height)!==r.viewHeight) {
            if(s.widthWake===wake)s.widthWake=null;s.widthOnlyRefusal="width-only-layout-or-owner-preflight";return false;
         }
         var scope:Object=ApexGridAuthorityScope(s.owner);if(scope==null)return false;
         var d:Object={widthTransfer:true,wake:wake,state:s,job:j,owner:s.owner,ownerGeneration:s.ownerGeneration,feed:mGridData,view:mGridView,cellType:mCellType,
            eofScope:scope,eofPanel:s.panel,eofStage:s.panel.stage,authorityOwned:true,authority:null,
            rowValidate:s.request.rowDeltaRowValidate,revision:int(s.revision),oldPlan:p,desired:r,latest:null,
            oldGeneration:int(j.generation),newGeneration:int(j.generation),oldCells:mCells,oldY:mCellsY,oldMap:mCellIndexToDataIndexMap,oldReady:s.ready,
            oldExpected:presentation.committedExpected,oldBindings:presentation.committedBindings,oldPool:s.poolFlags,oldIntrinsics:s.intrinsics,oldPresentation:presentation,
            cells:mCells,ys:mCellsY,map:mCellIndexToDataIndexMap,borrowed:new Dictionary(true),members:new Dictionary(true),
            oldPositions:new Dictionary(true),oldVisible:new Dictionary(true),touched:false,first:int(p.first),
            snapshots:new Vector.<Object>(j.target),phase:"width-only-preflight"};
         var accepted:Boolean=false;var oldRunning:Boolean=j.running;s.delta=d;j.running=true;
         try {
            if(!ApexGridAuthorityCapture(d) || !ApexGridWidthCurrent(d) || GetNumItems()!=p.feedCount || !ApexGridValid(j.identity))return false;
            // Capture every physical before-image before ANY row/extension
            // callback. A callback on row0 cannot become row1's new baseline.
            var type:Class=mCellType as Class;
            for(var i:int=0;i<j.target;i++) {
               var cell:Object=mCells[i];
               if(type==null || cell==null || !(cell is type) || cell.constructor!==type || cell.parent!==d.view)return false;
               d.snapshots[i]={cell:cell,binding:d.oldBindings[cell],expected:d.oldExpected[cell],extension:null,selected:false,
                  x:Number(cell.x),y:Number(cell.y),sx:Number(cell.scaleX),sy:Number(cell.scaleY),rotation:Number(cell.rotation),alpha:Number(cell.alpha),
                  visible:Boolean(cell.visible),mouse:Boolean(cell.mouseEnabled),children:Boolean(cell.mouseChildren)};
               var v:Object=d.snapshots[i];
               if(!isFinite(v.x)||!isFinite(v.y)||!isFinite(v.sx)||!isFinite(v.sy)||v.sx<=0||v.sy<=0||!isFinite(v.rotation)||!isFinite(v.alpha))return false;
            }
            if(!ApexGridWidthCurrent(d))return false;
            var selectable:SelectableArrayDataFeed=mGridData as SelectableArrayDataFeed;if(selectable==null)return false;
            for(i=0;i<j.target;i++) {
               cell=mCells[i];var sorted:int=int(p.first)+i;v=d.snapshots[i];
               if(cell!==v.cell || d.oldBindings[cell]!==v.binding || d.oldExpected[cell]!==v.expected) {ApexGridAuthorityLose(d,"width-row-record-adopted");return true;}
               if(!ApexGridAuthorityOldCell(cell,i,d)) {ApexGridAuthorityLose(d,"width-old-bank-custody-changed");return true;}
               var ext:Selectability=(cell as IExtendable).GetExtension(Selectability) as Selectability;
               if(ext==null || ext.constructor!==Selectability)return false;
               var record:Object=d.oldBindings[cell];var expected:Object=d.oldExpected[cell];
               if(sorted>=int(p.feedCount)) {
                  if(mCellIndexToDataIndexMap[i]!==-1 || s.ready[cell]!==-1 || cell.visible!==false || ext.Selected!==false || expected!=null)return false;
               } else {
                  if(record==null || mCellIndexToDataIndexMap[i]!==sorted || s.ready[cell]!==j.generation ||
                     record.sorted!==sorted || record.selected!==ext.Selected || !ApexGridDeltaTexture(cell,expected))return false;
                  var item:Object=GetDataAtIndex(sorted);
                  if(item==null || d.rowValidate(item)!==true || GetDataIndexOfSortedIndex(sorted)!==record.data ||
                     String(item.data_id)!==record.base || String(item.GetVariationOrBaseId())!==record.variation ||
                     int(item.body_type)!==record.body || int(item.menu_state)!==record.menu ||
                     selectable.GetSelectionState(record.data)!==record.selected ||
                     ("dccFavoriteProductId" in cell && cell.dccFavoriteProductId!==record.base))return false;
               }
               v.extension=ext;v.selected=record==null ? false : Boolean(record.selected);
               if(!ApexGridWidthCurrent(d))return false;
            }
            if(GetNumItems()!=p.feedCount || !ApexGridValid(j.identity) || !ApexGridWidthCurrent(d) || !ApexGridAuthorityBank(d))return false;
            for(i=0;i<j.target;i++) {
               v=d.snapshots[i];cell=v.cell;
               if(mCells[i]!==cell || d.oldBindings[cell]!==v.binding || d.oldExpected[cell]!==v.expected ||
                  Number(cell.x)!==v.x || Number(cell.y)!==v.y || Number(cell.scaleX)!==v.sx || Number(cell.scaleY)!==v.sy ||
                  Number(cell.rotation)!==v.rotation || Number(cell.alpha)!==v.alpha || cell.visible!==v.visible ||
                  cell.mouseEnabled!==v.mouse || cell.mouseChildren!==v.children ||
                  (cell as IExtendable).GetExtension(Selectability)!==v.extension || v.extension.Selected!==v.selected) {
                  ApexGridAuthorityLose(d,"width-card-presentation-adopted");return true;
               }
            }
            if(!ApexGridWidthCurrent(d) || !ApexGridAuthorityBank(d))return false;
            if(d.latest!=null)return true;
            // Native width/mask/scrollbar controls are ALREADY applied by their
            // original setter route. Only copied plan/request scalars change.
            // No cell, selection, texture, input, map, lease or event is written.
            p.viewWidth=r.viewWidth;p.signature=r.signature;j.desired=r;
            s.widthWake=null;s.widthOnlyRefusal="";
            if(int(s.widthOnlyCommits)<int.MAX_VALUE)s.widthOnlyCommits=int(s.widthOnlyCommits)+1;
            accepted=true;return true;
         } finally {
            j.running=oldRunning;
            if(d.authority!=null && apexGridAuthority===d.authority && !d.authority.lost) {
               if(!ApexGridAuthorityCurrent(d) || !ApexGridAuthorityBank(d))ApexGridAuthorityLose(d,"width-cleanup-custody-changed");
               else {if(s.delta===d)s.delta=null;apexGridAuthority=null;}
            }
            if(!accepted && apexGridAuthority==null && apexGridState===s && s.job===j) {
               if(s.widthWake===wake)s.widthWake=null;
               s.widthOnlyRefusal="width-only-fresh-row-or-reentry-refused";
               if(d.latest!=null && !j.cancelled) {j.desired=d.latest;j.dirty=true;if(j.phase=="done")j.phase="acquire";}
            }
         }
      }
