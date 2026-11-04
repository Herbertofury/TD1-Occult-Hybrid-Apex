      // Renderer widgets only: no borrowed catalog row or game appearance.
      private function ApexGridSpareCustody(cell:Object) : Boolean {
         var s:Object=apexGridState;var record:Object=s==null || s.spareCustody==null ? null : s.spareCustody[cell];
         if(record==null)return true; // Existing fresh-factory/default path.
         var p:Object=s.presentation;
         var heldType:Class=record.intrinsic==null ? null : record.intrinsic.type as Class;
         return record.abandoned!==true && cell!=null && record.view===mGridView && s.view===mGridView && cell.parent===mGridView && cell.visible===false &&
            (s.ready[cell]==null || s.ready[cell]===record.readyValue) && s.intrinsics[cell]===record.intrinsic && heldType!=null && cell is heldType &&
            getQualifiedClassName(cell)===getQualifiedClassName(heldType) &&
            (p==null || p.committedCells==null || p.committedCells.indexOf(cell)<0);
      }

      private function ApexGridSpareDescribe(cell:Object,exclude:Object,used:Object) : Object {
         var s:Object=apexGridState;var intrinsic:Object=cell==null ? null : s.intrinsics[cell];
         var member:Boolean=cell!=null && exclude!=null && exclude[cell]===true;
         var taken:Boolean=cell!=null && used!=null && used[cell]===true;
         var parent:Boolean=cell!=null && cell.parent===mGridView;
         var hidden:Boolean=cell!=null && cell.visible===false;
         var custody:Object=cell==null || s.spareCustody==null ? null : s.spareCustody[cell];
         var heldType:Class=intrinsic==null ? null : intrinsic.type as Class;
         var registered:Boolean=(custody==null || custody.abandoned!==true && (s.ready[cell]==null || s.ready[cell]===custody.readyValue)) && heldType!=null && cell is heldType &&
            getQualifiedClassName(cell)===getQualifiedClassName(heldType);
         var current:Boolean=registered && intrinsic.type===mCellType;
         var reason:String=cell==null ? "null" : member ? "committed-alias" : taken ? "used-duplicate" :
            !parent ? "foreign-parent" : !hidden ? "visible" : !registered ? "unregistered" : !current ? "old-class" : "eligible";
         return {reason:reason,parent:parent,hidden:hidden,registered:registered,current:current,
            member:member,used:taken,intrinsic:intrinsic,
            eligible:parent && hidden && registered && current && !member && !taken,
            retire:parent && hidden && registered && !current && !member && !taken};
      }

      private function ApexGridSpareReport(reason:String,index:int,flags:Object) : void {
         var s:Object=apexGridState;
         if(int(s.spareRejected)<int.MAX_VALUE)s.spareRejected=int(s.spareRejected)+1;
         s.spareLast={reason:reason.substr(0,64),index:index,parent:flags.parent===true,hidden:flags.hidden===true,
            registered:flags.registered===true,current:flags.current===true,member:flags.member===true,used:flags.used===true};
         s.deltaLastRefusal=("spare-skip:"+reason+" slot="+index+" parent="+int(flags.parent)+" hidden="+int(flags.hidden)+
            " registered="+int(flags.registered)+" current="+int(flags.current)+" member="+int(flags.member)+" used="+int(flags.used)).substr(0,160);
      }

      private function ApexGridSpareDefer(cell:Object,intrinsic:Object) : void {
         var s:Object=apexGridState;
         if(cell==null || intrinsic==null)return;
         if(s.deferredSpare==null)s.deferredSpare=[];
         if(s.deferredSpareFlags==null)s.deferredSpareFlags=new Dictionary(true);
         if(s.deferredSpareFlags[cell]===true)return;
         s.deferredSpare.push({cell:cell,intrinsic:intrinsic,view:mGridView});s.deferredSpareFlags[cell]=true;
      }

      private function ApexGridSpareFilter(cells:Object,ys:Object,map:Object,exclude:Object,retire:Boolean,mergeDeferred:Boolean) : Object {
         var s:Object=apexGridState;var stock:Array=[];var cell:Object;var at:int;
         for(at=0;at<cells.length;at++)stock.push({cell:cells[at],y:ys!=null && at<ys.length ? Number(ys[at]) : 0,
            data:map!=null && at<map.length ? int(map[at]) : -1,record:null});
         if(mergeDeferred && s.deferredSpare!=null) {
            for each(var deferred:Object in s.deferredSpare)stock.push({cell:deferred.cell,y:0,data:-1,record:deferred});
            s.deferredSpare=[];s.deferredSpareFlags=new Dictionary(true);
         }
         var kept:Vector.<IView> =new Vector.<IView>();var keptY:Vector.<Number> =new Vector.<Number>();var keptMap:Vector.<int> =new Vector.<int>();
         var seen:Object=new Dictionary(true);
         for(at=0;at<stock.length;at++) {
            var entry:Object=stock[at];cell=entry.cell;
            var flags:Object=ApexGridSpareDescribe(cell,exclude,seen);
            if(entry.record!=null && (entry.record.view!==mGridView || flags.intrinsic!==entry.record.intrinsic)) {
               ApexGridSpareReport("retire-record-changed",at,flags);continue;
            }
            if(flags.eligible || retire && flags.retire) {
               seen[cell]=true;kept.push(cell as IView);keptY.push(Number(entry.y));keptMap.push(int(entry.data));
               s.spareCustody[cell]={view:mGridView,intrinsic:flags.intrinsic,readyValue:s.ready[cell]};
            } else {
               ApexGridSpareReport(String(flags.reason),at,flags);
               if(flags.retire)ApexGridSpareDefer(cell,flags.intrinsic);
            }
         }
         return {cells:kept,ys:keptY,map:keptMap};
      }

      private function ApexGridDeltaTakeSpare(cell:Object,d:Object,index:int) : Boolean {
         var s:Object=apexGridState;var flags:Object=ApexGridSpareDescribe(cell,d.originalMembers,d.stockTaken);
         if(int(s.spareScanned)<int.MAX_VALUE)s.spareScanned=int(s.spareScanned)+1;
         if(!flags.eligible) {
            ApexGridSpareReport(String(flags.reason),index,flags);
            return false;
         }
         d.stockTaken[cell]=true;d.usedSpare.push(cell as IView);
         s.spareCustody[cell]={view:d.view,intrinsic:flags.intrinsic,readyValue:s.ready[cell]};
         if(int(s.spareAccepted)<int.MAX_VALUE)s.spareAccepted=int(s.spareAccepted)+1;
         return true;
      }

      private function ApexGridSpareAfterPublish() : void {
         var s:Object=apexGridState;var p:Object=s.presentation;var current:Object=new Dictionary(true);
         for each(var cell:Object in p.committedCells) {current[cell]=true;if(s.spareCustody!=null)delete s.spareCustody[cell];}
         var filtered:Object=ApexGridSpareFilter(p.spareCells,p.spareY,p.spareMap,current,false,false);
         p.spareCells=filtered.cells;p.spareY=filtered.ys;p.spareMap=filtered.map;
      }
