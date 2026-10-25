      // Explicit short-lived layout diagnostics. Ordinary layout retains one
      // native Reset call and performs no clocks, callbacks or cell reads here.
      private var apexLayoutTrace:Object;

      private function ApexLayoutTraceConfigure(milliseconds:int) : Object
      {
         if(milliseconds<0 || milliseconds>30000)throw new Error("Layout diagnostics need 0 to 30000 milliseconds");
         var generation:int=apexLayoutTrace==null ? 1 : int(apexLayoutTrace.generation)+1;
         ApexLayoutTraceDispose();
         if(milliseconds==0) {if(apexLayoutTrace!=null)apexLayoutTrace.requested_ms=0;return ApexLayoutTraceStatus();}
         ApexCatalogTraceDispose();
         var phases:Object={};
         for each(var phase:String in ["setup_ms","position_ms","bind_ms","resize_ms","total_ms"])
            phases[phase]={calls:0,total_ms:0,max_ms:0};
         apexLayoutTrace={enabled:true,requested_ms:milliseconds,generation:generation,started_ms:flash.utils.getTimer(),
            elapsed_ms:0,expired:false,completed:0,suppressed:0,errors:0,phases:phases,records:[]};
         return ApexLayoutTraceStatus();
      }

      private function ApexLayoutTraceDispose() : void
      {
         if(apexLayoutTrace!=null)apexLayoutTrace.enabled=false;
      }

      private function ApexLayoutTraceStatus() : Object
      {
         var trace:Object=apexLayoutTrace;
         if(trace==null)return {enabled:false,available:true,requested_ms:0,generation:0,record_limit:16,
            records:[],aggregates:{},completed:0,suppressed:0,errors:0,appearance_written:false};
         if(trace.enabled) {
            trace.elapsed_ms=Math.max(0,int(flash.utils.getTimer()-int(trace.started_ms)));
            if(trace.elapsed_ms>=int(trace.requested_ms)) {trace.expired=true;ApexLayoutTraceDispose();}
         }
         return {enabled:Boolean(trace.enabled),available:true,requested_ms:int(trace.requested_ms),generation:int(trace.generation),
            elapsed_ms:int(trace.elapsed_ms),expired:Boolean(trace.expired),completed:int(trace.completed),suppressed:int(trace.suppressed),
            errors:int(trace.errors),record_limit:16,records:trace.records,aggregates:trace.phases,
            timing:"inclusive native reset phases in synchronous milliseconds; setup includes stage callbacks; bind includes Draw",appearance_written:false};
      }

      private function ApexLayoutReset(grid:Object) : void
      {
         var trace:Object=apexLayoutTrace;
         if(trace==null || !trace.enabled) {grid.ResetAndPositionCells();return;}
         trace.elapsed_ms=Math.max(0,int(flash.utils.getTimer()-int(trace.started_ms)));
         if(trace.elapsed_ms>=int(trace.requested_ms)) {
            trace.expired=true;ApexLayoutTraceDispose();grid.ResetAndPositionCells();return;
         }
         // No catch-and-retry: a native exception must not repeat construction,
         // binding or resize. Diagnostics retain no grid, feed or cell objects.
         var result:Object;
         try {result=grid.ApexProfileResetAndPositionCells();}
         catch(nativeError:*) {trace.errors++;ApexLayoutTraceDispose();throw nativeError;}
         if(result.suppressed) {trace.suppressed++;return;}
         trace.completed++;
         for each(var phase:String in ["setup_ms","position_ms","bind_ms","resize_ms","total_ms"]) {
            var count:Object=trace.phases[phase];
            count.calls++;count.total_ms+=int(result[phase]);count.max_ms=Math.max(count.max_ms,int(result[phase]));
         }
         var record:Object={provider:String(grid.ApexGridProviderIdentity()),before_count:int(result.before_count),after_count:int(result.after_count),
            setup_ms:int(result.setup_ms),position_ms:int(result.position_ms),bind_ms:int(result.bind_ms),resize_ms:int(result.resize_ms),total_ms:int(result.total_ms)};
         if(trace.records.length<16)trace.records.push(record);
         else {
            var smallest:int=0;
            for(var i:int=1;i<16;i++)if(int(trace.records[i].total_ms)<int(trace.records[smallest].total_ms))smallest=i;
            if(int(record.total_ms)>int(trace.records[smallest].total_ms))trace.records[smallest]=record;
         }
      }
