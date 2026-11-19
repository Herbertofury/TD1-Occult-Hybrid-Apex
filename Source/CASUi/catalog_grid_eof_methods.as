      // Match the existing planner exactly. EOF slots are native overscan,
      // never fabricated products or permission to index an arbitrary row.
      private function ApexGridDeltaEofWindow(p:Object,first:int,target:int) : Boolean {
         if(p==null || typeof p.feedCount!="number" || typeof p.columns!="number" || typeof p.height!="number" || typeof p.gapY!="number" ||
            typeof p.pitchY!="number" || typeof p.viewHeight!="number" || typeof p.logicalRows!="number" || typeof p.rows!="number" ||
            typeof p.target!="number" || typeof p.range!="number" || typeof p.first!="number" ||
            !isFinite(Number(p.feedCount)) || Number(p.feedCount)!=int(p.feedCount) || int(p.feedCount)<=0 ||
            !isFinite(Number(p.columns)) || Number(p.columns)!=int(p.columns) || int(p.columns)<1 || int(p.columns)>32 ||
            !isFinite(Number(p.first)) || Number(p.first)!=int(p.first) ||
            !isFinite(Number(p.pitchY)) || Number(p.pitchY)<=0 || Number(p.pitchY)!==Number(p.height)+Number(p.gapY) ||
            !isFinite(Number(p.viewHeight)) || Number(p.viewHeight)<=0)return false;
         var columns:int=int(p.columns);var count:int=int(p.feedCount);var pitch:Number=Number(p.pitchY);
         var logical:int=Math.ceil(count/columns);var rows:int=Math.min(Math.ceil(Number(p.viewHeight)/pitch)+1,logical);
         var range:Number=Math.max(0,logical*pitch-Number(p.viewHeight));var last:int=int(Math.floor(range/pitch))*columns;
         return p.logicalRows==logical && p.rows==rows && p.target==rows*columns && target==p.target &&
            Number(p.range)===range && first>=0 && first<=last && first%columns==0 &&
            int(p.first)>=0 && int(p.first)<=last && int(p.first)%columns==0;
      }

      // Native Bind/Ready must have already parked this exact absent row.
      // This separate schema has no thumbnail or product identity to invent.
      private function ApexGridDeltaEofReady(cell:Object,slot:int,d:Object,old:Boolean) : Boolean {
         var s:Object=apexGridState;var j:Object=d==null ? null : d.job;var p:Object=s==null ? null : s.presentation;
         if(d==null || s!==d.state || j==null || s.job!==j || p==null || !p.working ||
            slot<0 || slot>=j.target || !ApexGridDeltaCurrent(d))return false;
         var currentReady:Object=s.ready;
         var sorted:int=int(d.first)+slot;var index:int=old ? sorted-int(d.oldPlan.first) : slot;
         var plan:Object=d.oldPlan;var count:int=int(plan.feedCount);var revision:int=d.revision;
         var cells:Object=old ? d.oldCells : d.cells;var ys:Object=old ? d.oldY : d.ys;var map:Object=old ? d.oldMap : d.map;
         var ready:Object=old ? d.oldReady : s.ready;var expected:Object=old ? d.oldExpected : d.expected;
         var bindings:Object=old ? d.oldBindings : d.bindings;var generation:int=old ? d.oldGeneration : d.newGeneration;
         var flags:Object=s.poolFlags==null || cell==null ? null : s.poolFlags[cell];
         var intrinsic:Object=s.intrinsics==null || cell==null ? null : s.intrinsics[cell];var type:Class=d.cellType as Class;
         var record:Object=cell==null || bindings==null ? null : bindings[cell];
         var physical:Number=cell==null ? NaN : Number(cell.y);var logical:Number=index<0 || ys==null ? NaN : Number(ys[index]);
         if(sorted<int(d.oldPlan.feedCount) || index<0 || index>=j.target || cells==null || ys==null || map==null || ready==null || expected==null ||
            cells[index]!==cell || map[index]!==-1 || ready[cell]!==-1 || expected[cell]!=null ||
            p.stageCells!==d.cells || p.stageY!==d.ys || p.stageMap!==d.map || p.expected!==d.expected || p.stageBindings!==d.bindings ||
            p.committedCells!==d.oldCells || p.committedY!==d.oldY || p.committedMap!==d.oldMap || p.committedReady!==d.oldReady ||
            p.committedBindings!==d.oldBindings || p.committedExpected!==d.oldExpected ||
            cell==null || cell.parent!==d.view || cell.visible!==false || cell.mouseEnabled!==false || cell.mouseChildren!==false ||
            type==null || !(cell is type) || cell.constructor!==type || getQualifiedClassName(cell)!==getQualifiedClassName(type) ||
            intrinsic==null || intrinsic.type!==type || flags==null ||
            (flags.mouse!==true && flags.mouse!==false) || (flags.children!==true && flags.children!==false) || !isFinite(physical) || !isFinite(logical) ||
            "dccFavoriteProductId" in cell && cell.dccFavoriteProductId!=null)return false;
         if(record!=null && (record.schema!=="empty-v1" || record.generation!==generation || record.revision!==d.revision ||
            record.sorted!==sorted || record.selected!==false || record.logicalY!==logical ||
            (!old && d.touched ? Number(d.physicalY[cell])!==physical : record.physicalY!==physical)))return false;
         if(!old && d.empty[cell]===true && record==null)return false;
         var mouse:Boolean=flags.mouse;var children:Boolean=flags.children;
         var ext:Selectability=(cell as IExtendable).GetExtension(Selectability) as Selectability;
         if(ext==null || ext.constructor!==Selectability || getQualifiedClassName(ext)!=="olympus.extensions::Selectability" || ext.Selected!==false)return false;
         // No additional out-of-range product lookup. The fresh authoritative
         // count, exact planner bounds and original Bind/Ready negative-map
         // completion jointly attest this absent row.
         if(!ApexGridDeltaCurrent(d))return false;
         // Every possibly reentrant read is finished. Recheck the exact copied
         // stock/negative-map/readiness custody before recording any new state.
         return apexGridState===s && s.job===j && s.presentation===p && s.ready===currentReady && d.oldPlan===plan && int(plan.feedCount)==count &&
            int(d.first)+slot==sorted && d.revision==revision && (old ? d.oldGeneration : d.newGeneration)===generation &&
            p.stageCells===d.cells && p.stageY===d.ys && p.stageMap===d.map && p.expected===d.expected && p.stageBindings===d.bindings &&
            p.committedCells===d.oldCells && p.committedY===d.oldY && p.committedMap===d.oldMap && p.committedReady===d.oldReady &&
            p.committedBindings===d.oldBindings && p.committedExpected===d.oldExpected &&
            (old ? d.oldCells===cells && d.oldY===ys && d.oldMap===map && d.oldReady===ready && d.oldExpected===expected && d.oldBindings===bindings :
             d.cells===cells && d.ys===ys && d.map===map && s.ready===ready && d.expected===expected && d.bindings===bindings) &&
            cells[index]===cell && Number(ys[index])===logical && map[index]===-1 && ready[cell]===-1 && expected[cell]==null && bindings[cell]===record &&
            cell.parent===d.view && cell.visible===false && cell.mouseEnabled===false && cell.mouseChildren===false && Number(cell.y)===physical &&
            s.poolFlags[cell]===flags && flags.mouse===mouse && flags.children===children &&
            s.intrinsics[cell]===intrinsic && intrinsic.type===type && mCellType===type &&
            ext.constructor===Selectability && ext.Selected===false &&
            (record==null || record.schema==="empty-v1" && record.generation===generation && record.revision===revision &&
             record.sorted===sorted && record.selected===false && record.logicalY===logical &&
             (!old && d.touched ? Number(d.physicalY[cell])===physical : record.physicalY===physical)) &&
            (!("dccFavoriteProductId" in cell) || cell.dccFavoriteProductId==null);
      }

      private function ApexGridDeltaBorrowEof(cell:Object,slot:int,d:Object) : Boolean {
         var old:int=int(d.first)+slot-int(d.oldPlan.first);
         if(d.members[cell]===true || !ApexGridDeltaEofReady(cell,slot,d,true))return false;
         var s:Object=apexGridState;var logical:Number=d.origin+Math.floor(slot/int(d.oldPlan.columns))*Number(d.oldPlan.pitchY);
         d.borrowed[cell]=old;d.members[cell]=true;d.empty[cell]=true;d.oldVisible[cell]=false;d.oldPositions[cell]=Number(cell.y);
         d.cells[slot]=cell;d.map[slot]=-1;d.ys[slot]=logical;
         d.bindings[cell]={schema:"empty-v1",generation:d.newGeneration,revision:d.revision,sorted:int(d.first)+slot,
            selected:false,logicalY:logical,physicalY:Number(cell.y)};
         s.ready[cell]=-1;d.borrowCount++;return true;
      }
