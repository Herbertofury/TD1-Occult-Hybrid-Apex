      // Main issues this capability only for authenticated exact native classes.
      // No new data map or native product is admitted by a pixel-only scroll.
      private function ApexGridScrollOnlyEligible(j:Object,r:Object) : Boolean {
         var s:Object=apexGridState;var p:Object=j==null ? null : j.plan;
         if(s==null || !s.armed || s.job!==j || s.request==null ||
            s.request.scrollOnlyPositionContract!==1 || s.bootstrap || j.cancelled || j.dirty ||
            p==null || (j.phase!="done" && j.phase!="scroll-only") || j.revision!=s.revision ||
            s.owner==null || s.owner.active!==true || int(s.owner.generation)!=s.ownerGeneration ||
            s.owner.cell_type!==mCellType ||
            (s.owner.panel_kind!="clothing" && s.owner.panel_kind!="body" && s.owner.panel_kind!="face" && s.owner.panel_kind!="generic") ||
            s.feed!==mGridData || s.view!==mGridView || s.presentation==null || s.presentation.working ||
            s.presentation.committedCells!==mCells || mCells.length!=mCellsY.length || mCells.length!=mCellIndexToDataIndexMap.length ||
            r==null || r.columns!=p.columns || r.width!==p.width || r.height!==p.height ||
            r.gapX!==p.gapX || r.gapY!==p.gapY || r.viewWidth!==p.viewWidth || r.viewHeight!==p.viewHeight ||
            r.marginX!==p.marginX || r.marginY!==p.marginY || GetNumItems()!=p.feedCount)return false;
         var raw:Number=Math.max(0,Math.min(Number(p.range),Number(r.scrollY)));
         return isFinite(raw) && int(Math.floor(raw/Number(p.pitchY)))*int(p.columns)==int(p.first);
      }

      private function ApexGridScrollOnlyQueue(j:Object,r:Object) : Boolean {
         if(!ApexGridScrollOnlyEligible(j,r))return false;
         j.desired=r;
         // A native RESIZE echo can coalesce a newer raw target while the
         // current atomic publication runs. Never replay or quantize it.
         if(!j.publishing) {
            var raw:Number=Math.max(0,Math.min(Number(j.plan.range),Number(r.scrollY)));
            j.phase=raw===Number(j.plan.scrollY) ? "done" : "scroll-only";
         }
         return true;
      }

      private function ApexGridScrollOnlyApply(j:Object) : Boolean {
         var s:Object=apexGridState;var p:Object=j.plan;var desired:Object=j.desired;
         if(!ApexGridScrollOnlyEligible(j,desired) || !ApexGridValid(j.identity)) {
            j.dirty=true;j.phase="acquire";return false;
         }
         if(!ApexGridAcquire(j))return false;
         j.lease=true;
         var cells:Object=mCells;var ys:Object=mCellsY;var map:Object=mCellIndexToDataIndexMap;var view:Object=mGridView;
         var count:int=cells.length;
         // Reusable rollback storage contains UI widgets and copied numbers,
         // never a product/model row. No display mutation occurs in preflight.
         var backup:Object=null;var saved:int=0;var written:int=0;var completed:Boolean=false;
         var oldRaw:Number=Number(p.scrollY);var oldOrigin:Number=Number(p.originY);var oldPrev:Number=mPrevRectangleUpdate.y;
         var raw:Number=Math.max(0,Math.min(Number(p.range),Number(desired.scrollY)));
         var origin:Number=Number(p.marginY)-(raw-Math.floor(raw/Number(p.pitchY))*Number(p.pitchY));
         try {
            if(s.scrollRollback==null || int(s.scrollRollback.capacity)<count)
               s.scrollRollback={capacity:count,cells:new Vector.<IView>(count),ys:new Vector.<Number>(count),map:new Vector.<int>(count)};
            backup=s.scrollRollback;
            for(var i:int=0;i<count;i++) {
               var cell:Object=cells[i];backup.cells[i]=cell;backup.ys[i]=Number(ys[i]);backup.map[i]=int(map[i]);saved++;
               if(map[i]<0)continue;
               var intrinsic:Object=s.intrinsics[cell];
               if(cell==null || cell.parent!==view || intrinsic==null || intrinsic.type!==mCellType ||
                  map[i]!=int(p.first)+i || s.ready[cell]!==j.generation ||
                  !isFinite(Number(cell.y)) || Number(cell.y)!==Number(ys[i])) {
                  j.dirty=true;j.phase="acquire";return false;
               }
            }
            if(j.cancelled || j.dirty || j.revision!=s.revision || !ApexGridValid(j.identity) ||
               !ApexGridOwns(j) || cells!==mCells || ys!==mCellsY || map!==mCellIndexToDataIndexMap || view!==mGridView) {
               if(!j.cancelled) {j.dirty=true;j.phase="acquire";}return false;
            }
            // Exact known native card classes have callback-free y setters.
            // Unknown/default requests never opt in. No yield occurs here.
            for(i=0;i<count;i++) {
               if(map[i]<0)continue;
               cell=cells[i];var y:Number=origin+Math.floor(i/int(p.columns))*Number(p.pitchY);
               cell.y=y;ys[i]=y;written++;
               j.phaseCounts.position=int(j.phaseCounts.position)+1;
            }
            p.scrollY=raw;p.originY=origin;mPrevRectangleUpdate.y=-raw;
            j.publishing=true;
            try {view.dispatchEvent(new GridEvent(GridEvent.RESIZE,null,[]));}
            finally {j.publishing=false;}
            if(j.cancelled || j.dirty || j.revision!=s.revision || !ApexGridValid(j.identity) ||
               !ApexGridOwns(j) || cells!==mCells || ys!==mCellsY || map!==mCellIndexToDataIndexMap || view!==mGridView) {
               if(!j.cancelled) {j.dirty=true;j.phase="acquire";}return false;
            }
            completed=true;j.publishes++;j.phaseCounts.publish=int(j.phaseCounts.publish)+1;
            j.scrollCommits=int(j.scrollCommits)+1;
            var latest:Number=Math.max(0,Math.min(Number(p.range),Number(j.desired.scrollY)));
            j.phase=latest===raw ? "done" : "scroll-only";
            return true;
         } finally {
            if(!completed && written>0) {
               for(i=0;i<saved;i++) {
                  cell=backup.cells[i];
                  if(cell!=null && backup.map[i]>=0 && cell.parent===view) {cell.y=Number(backup.ys[i]);ys[i]=Number(backup.ys[i]);}
               }
               p.scrollY=oldRaw;p.originY=oldOrigin;mPrevRectangleUpdate.y=oldPrev;
            }
            for(i=0;i<saved;i++)backup.cells[i]=null;
            if(ApexGridOwns(j))ApexGridRelease(j);
            j.lease=false;
         }
      }
