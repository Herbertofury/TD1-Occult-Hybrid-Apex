      // Complete publication may reuse a larger initialized physical stock.
      // Keep only the exact ready logical window in EA's committed arrays;
      // hidden parked surplus remains attached, unchanged, in owned spare stock.
      private function ApexGridCommitLogicalBank(j:Object) : Boolean {
         var s:Object=apexGridState;var p:Object=s==null ? null : s.presentation;
         var cells:Object=mCells;var ys:Object=mCellsY;var map:Object=mCellIndexToDataIndexMap;
         var view:Object=mGridView;var type:Class=mCellType as Class;
         if(s==null || s.job!==j || !s.armed || s.bootstrap || j==null || j.phase!="publish" || j.cancelled || j.dirty ||
            j.revision!=s.revision || !ApexGridDeltaCapable() || p==null || p.working || !p.published ||
            p.committedCells!==cells || p.committedY!==ys || p.committedMap!==map || p.committedReady!==s.ready ||
            p.committedBindings==null || p.committedExpected==null || j.plan==null || j.target<=0 ||
            cells.length<=j.target || cells.length!=ys.length || cells.length!=map.length || type==null ||
            s.feed!==mGridData || s.view!==view || s.owner==null || s.owner.active!==true ||
            int(s.owner.generation)!=s.ownerGeneration || s.owner.cell_type!==type)return false;
         var count:int=cells.length;var target:int=j.target;var generation:int=j.generation;var revision:int=s.revision;
         var owner:Object=s.owner;var ownerGeneration:int=s.ownerGeneration;var request:Object=s.request;var feed:Object=s.feed;
         var ready:Object=s.ready;var intrinsics:Object=s.intrinsics;var poolFlags:Object=s.poolFlags;
         var bindings:Object=p.committedBindings;var expectedRows:Object=p.committedExpected;
         var stock:Object=p.spareCells;var stockY:Object=p.spareY;var stockMap:Object=p.spareMap;
         if(stock==null || stockY==null || stockMap==null || stock.length!=stockY.length || stock.length!=stockMap.length ||
            !ApexGridValid(j.identity) || !ApexGridOwns(j))return false;
         var nativeName:String=getQualifiedClassName(type);var seen:Object=new Dictionary(true);
         var next:Vector.<IView> =new Vector.<IView>(target);var nextY:Vector.<Number> =new Vector.<Number>(target);var nextMap:Vector.<int> =new Vector.<int>(target);
         var spare:Vector.<IView> =new Vector.<IView>();var spareY:Vector.<Number> =new Vector.<Number>();var spareMap:Vector.<int> =new Vector.<int>();
         for(var i:int=0;i<count;i++) {
            var cell:Object=cells[i];var intrinsic:Object=cell==null ? null : intrinsics[cell];
            if(cell==null || seen[cell]===true || cell.parent!==view || intrinsic==null || intrinsic.type!==type ||
               !(cell is type) || cell.constructor!==type || getQualifiedClassName(cell)!==nativeName)return false;
            seen[cell]=true;
            if(i<target) {
               var binding:Object=bindings[cell];var expected:Object=expectedRows[cell];
               if(map[i]!=int(j.plan.first)+i || cell.visible!==true || ready[cell]!==generation ||
                  binding==null || binding.schema!=="product-v1" || binding.generation!==generation || binding.revision!==revision ||
                  binding.sorted!==int(map[i]) || binding.logicalY!==Number(ys[i]) || binding.physicalY!==Number(cell.y) ||
                  !ApexGridDeltaTexture(cell,expected))return false;
               next[i]=cell as IView;nextY[i]=Number(ys[i]);nextMap[i]=int(map[i]);
            } else {
               // An inactive slot must have passed the existing PoolPark path.
               // Unknown/visible/foreign/aliased or still-ready objects refuse
               // normalization without modifying that object or the live bank.
               if(map[i]!=-1 || cell.visible!==false || ready[cell]!=null || poolFlags[cell]==null)return false;
               spare.push(cell as IView);spareY.push(Number(ys[i]));spareMap.push(int(map[i]));
            }
         }
         // Existing stock remains unadmitted metadata here. The unchanged
         // immediately following SpareAfterPublish performs its full custody,
         // alias, class and foreign-widget filtering exactly once.
         for(i=0;i<stock.length;i++) {
            spare.push(stock[i] as IView);spareY.push(Number(stockY[i]));spareMap.push(int(stockMap[i]));
         }
         // All native/service reads are complete. A callback-installed owner,
         // feed, request, ready bank or array always keeps its own authority.
         if(apexGridState!==s || s.job!==j || s.presentation!==p || s.owner!==owner || s.request!==request ||
            s.feed!==feed || mGridData!==feed || s.view!==view || mGridView!==view || mCellType!==type ||
            owner.active!==true || s.ownerGeneration!=ownerGeneration || int(owner.generation)!=ownerGeneration || owner.cell_type!==type || j.cancelled || j.dirty ||
            j.revision!=revision || s.revision!=revision || j.generation!=generation || j.target!=target ||
            p.working || !p.published || s.ready!==ready || p.committedReady!==ready || s.intrinsics!==intrinsics || s.poolFlags!==poolFlags ||
            p.committedBindings!==bindings || p.committedExpected!==expectedRows || s.lease!==j || !mbSuppressUpdates || s.externalSuppression ||
            mCells!==cells || mCellsY!==ys || mCellIndexToDataIndexMap!==map || cells.length!=count || ys.length!=count || map.length!=count ||
            p.committedCells!==cells || p.committedY!==ys || p.committedMap!==map || p.spareCells!==stock || p.spareY!==stockY || p.spareMap!==stockMap)return false;
         // Only private UI array references change. No setter, Draw, selection,
         // image load, event, detach, input, lease release or native call follows.
         mCells=next;mCellsY=nextY;mCellIndexToDataIndexMap=nextMap;
         p.committedCells=next;p.committedY=nextY;p.committedMap=nextMap;
         p.spareCells=spare;p.spareY=spareY;p.spareMap=spareMap;
         return true;
      }
