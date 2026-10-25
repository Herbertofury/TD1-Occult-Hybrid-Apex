      // Null is the entire disabled Draw fast path. This typed static trait is
      // appended without replacing Main's native class initializer.
      public static var apexCatalogDrawTraceStep:Function;
      private var apexCatalogTrace:Object;

      private function ApexCatalogTraceConfigure(milliseconds:int) : Object
      {
         if(milliseconds<0 || milliseconds>30000)throw new Error("Draw diagnostics need 0 to 30000 milliseconds");
         var generation:int=apexCatalogTrace==null ? 1 : int(apexCatalogTrace.generation)+1;
         ApexCatalogTraceDispose();
         if(milliseconds==0) {if(apexCatalogTrace!=null)apexCatalogTrace.requested_ms=0;return ApexCatalogTraceStatus();}
         ApexLayoutTraceDispose();
         var phases:Object={};
         for each(var phase:String in ["draw","favorite","super","thumbnail","decoration","swatches","icons","other"])
            phases[phase]={calls:0,total_ms:0,max_ms:0};
         apexCatalogTrace={enabled:true,requested_ms:milliseconds,duration_ms:milliseconds,generation:generation,started_ms:flash.utils.getTimer(),elapsed_ms:0,
            expired:false,completed:0,errors:0,dropped:0,overflow:0,max_depth:0,stack:[],phases:phases,slow:[],callback:ApexCatalogTraceStep};
         CASCustomizerMain.apexCatalogDrawTraceStep=apexCatalogTrace.callback;
         return ApexCatalogTraceStatus();
      }

      private function ApexCatalogTraceDispose() : void
      {
         if(apexCatalogTrace!=null) {
            if(CASCustomizerMain.apexCatalogDrawTraceStep===apexCatalogTrace.callback)
               CASCustomizerMain.apexCatalogDrawTraceStep=null;
            apexCatalogTrace.enabled=false;
         }
      }

      private function ApexCatalogTraceStep(event:String,product:Object=null) : void
      {
         // Diagnostic failures must never replace a native Draw return/throw.
         // No product, cell, renderer or native pointer is stored in this state.
         var trace:Object=apexCatalogTrace;
         if(trace==null || !trace.enabled)return;
         try {
            var now:int=flash.utils.getTimer();
            trace.elapsed_ms=Math.max(0,int(now-int(trace.started_ms)));
            if(trace.elapsed_ms>=int(trace.duration_ms)) {
               trace.expired=true;ApexCatalogTraceDispose();return;
            }
            var stack:Array=trace.stack;
            if(event=="draw.enter") {
               if(trace.overflow>0 || stack.length>=8) {trace.overflow++;trace.dropped++;return;}
               var id:String="";var body:int=-1;
               if(product!=null) {id=String(product.data_id).substr(0,64);body=int(product.body_type);}
               stack.push({id:id,body_type:body,start:now,last:now,phase:"other",
                  times:{favorite:0,"super":0,thumbnail:0,decoration:0,swatches:0,icons:0,other:0},
                  counts:{favorite:0,"super":0,thumbnail:0,decoration:0,swatches:0,icons:0,other:1}});
               trace.max_depth=Math.max(trace.max_depth,stack.length);return;
            }
            if(trace.overflow>0) {if(event=="draw.leave")trace.overflow--;return;}
            if(stack.length==0) {trace.errors++;return;}
            var row:Object=stack[stack.length-1];
            var elapsed:int=Math.max(0,int(now-int(row.last)));
            if(event=="draw.leave") {
               row.times[String(row.phase)]+=elapsed;stack.pop();
               var total:int=Math.max(0,int(now-int(row.start)));trace.completed++;
               var counter:Object=trace.phases.draw;counter.calls++;counter.total_ms+=total;counter.max_ms=Math.max(counter.max_ms,total);
               for each(var name:String in ["favorite","super","thumbnail","decoration","swatches","icons","other"]) {
                  counter=trace.phases[name];counter.calls+=int(row.counts[name]);counter.total_ms+=int(row.times[name]);
                  counter.max_ms=Math.max(counter.max_ms,int(row.times[name]));
               }
               if(total>=1) {
                  var record:Object={id:String(row.id),body_type:int(row.body_type),total_ms:total,phases:row.times};
                  if(trace.slow.length<32)trace.slow.push(record);
                  else {
                     var smallest:int=0;
                     for(var i:int=1;i<32;i++)if(int(trace.slow[i].total_ms)<int(trace.slow[smallest].total_ms))smallest=i;
                     if(total>int(trace.slow[smallest].total_ms))trace.slow[smallest]=record;
                  }
               }
               return;
            }
            var parts:Array=event.split(".");
            if(parts.length!=2 || trace.phases[parts[0]]==null || parts[0]=="draw") {trace.errors++;return;}
            if(parts[1]=="enter") {
               row.times[String(row.phase)]+=elapsed;row.last=now;row.phase=String(parts[0]);row.counts[parts[0]]++;
            } else if(parts[1]=="leave" && row.phase==parts[0]) {
               row.times[String(row.phase)]+=elapsed;row.last=now;row.phase="other";
            }
         } catch(diagnosticError:*) {
            trace.errors++;ApexCatalogTraceDispose();
         }
      }

      private function ApexCatalogTraceStatus() : Object
      {
         var trace:Object=apexCatalogTrace;
         if(trace==null)return {enabled:false,available:true,requested_ms:0,generation:0,records:[],aggregates:{},
            callback_active:false,callback_present:CASCustomizerMain.apexCatalogDrawTraceStep!=null,
            record_limit:32,depth_limit:8,appearance_written:false};
         if(trace.enabled) {
            trace.elapsed_ms=Math.max(0,int(flash.utils.getTimer()-int(trace.started_ms)));
            if(trace.elapsed_ms>=int(trace.duration_ms)) {trace.expired=true;ApexCatalogTraceDispose();}
         }
         // Open records are explicit. A native exception propagates unchanged;
         // no catch/finally wrapper fabricates a completed duration for it.
         var incomplete:Array=[];
         for each(var row:Object in trace.stack)
            incomplete.push({id:String(row.id),body_type:int(row.body_type),phase:String(row.phase)});
         return {enabled:Boolean(trace.enabled),available:true,expired:Boolean(trace.expired),duration_ms:int(trace.duration_ms),
            requested_ms:int(trace.requested_ms),generation:int(trace.generation),
            callback_active:CASCustomizerMain.apexCatalogDrawTraceStep!=null && CASCustomizerMain.apexCatalogDrawTraceStep===trace.callback,
            callback_present:CASCustomizerMain.apexCatalogDrawTraceStep!=null,
            elapsed_ms:int(trace.elapsed_ms),completed:int(trace.completed),errors:int(trace.errors),dropped:int(trace.dropped),
            max_depth:int(trace.max_depth),incomplete:incomplete,overflow_depth:int(trace.overflow),
            aggregates:trace.phases,records:trace.slow,record_limit:32,depth_limit:8,
            timing:"inclusive synchronous milliseconds; phase max is per completed draw",appearance_written:false};
      }
