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
            // APEX_TIMER_TRACE_BEGIN timer-status-empty-status
            timer_profile:ApexCatalogTimerStatus(),
            // APEX_TIMER_TRACE_END timer-status-empty-status
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
            // APEX_TIMER_TRACE_BEGIN timer-status-active-status
            timer_profile:ApexCatalogTimerStatus(),
            // APEX_TIMER_TRACE_END timer-status-active-status
            timing:"inclusive synchronous milliseconds; phase max is per completed draw",appearance_written:false};
      }

      // APEX_TIMER_TRACE_BEGIN helper-methods
      private function ApexCatalogTimerStep(event:String, generation:int=0) : int
      {
         var trace:Object=apexCatalogTrace;
         if(trace==null || (!trace.enabled && event!="tick.leave")) return 0;
         try {
            var profile:Object=trace.timer_profile;
            if(event=="tick.enter") {
               var begun:int=flash.utils.getTimer();
               if(Math.max(0,int(begun-int(trace.started_ms)))>=int(trace.duration_ms)) {
                  trace.expired=true;ApexCatalogTraceDispose();return 0;
               }
               if(profile==null) {
                  var aggregates:Object={};
                  for each(var phase:String in ["tick","receive","native-info","clone","execute","readback","snapshot","ack-encode","ack-send","forms"])
                     aggregates[phase]={started:0,completed:0,interrupted:0,total_ms:0,max_ms:0,incomplete_total_ms:0,incomplete_max_ms:0};
                  profile={aggregates:aggregates,stack:[],records:[],completed:0,errors:0,dropped:0,overflow:0,max_depth:0};
                  trace.timer_profile=profile;
               }
               if(profile.stack.length!=0) {profile.errors++;return 0;}
               profile.stack.push({name:"tick",started:begun,operation:"idle",phase:int(apexPendingPhase),times:{},interrupted:0});
               profile.aggregates.tick.started++;
               profile.max_depth=Math.max(profile.max_depth,1);
               return int(trace.generation);
            }
            if(profile==null || profile.stack.length==0) return 0;
            if(event=="tick.leave" && generation!=int(trace.generation)) return 0;
            var now:int=flash.utils.getTimer();
            var root:Object=profile.stack[0];
            var parts:Array=event.split(".");
            if(parts.length!=2 || profile.aggregates[parts[0]]==null) {profile.errors++;return 0;}
            var name:String=String(parts[0]);
            if(parts[1]=="enter") {
               if(name=="execute" || name=="readback" || name=="forms") {
                  var operation:String="";
                  if(apexPendingFields!=null && apexPendingFields.length>2) operation=String(apexPendingFields[2]);
                  else if(apexReceiving && apexWire!=null) {
                     var first:int=apexWire.indexOf("|");
                     var second:int=apexWire.indexOf("|",first+1);
                     var third:int=apexWire.indexOf("|",second+1);
                     if(first>=0 && second>first && third>second) operation=apexWire.substring(second+1,third);
                  }
                  if(operation!="") root.operation=operation.substr(0,64);
                  else if(name=="forms" && apexFormsIntent!=null) root.operation="ui-form";
               }
               if(profile.overflow>0 || profile.stack.length>=8) {profile.overflow++;profile.dropped++;return 0;}
               profile.stack.push({name:name,started:now});
               profile.aggregates[name].started++;
               profile.max_depth=Math.max(profile.max_depth,profile.stack.length);
               return int(trace.generation);
            }
            if(parts[1]!="leave") {profile.errors++;return 0;}
            if(name!="tick") {
               if(profile.overflow>0) {profile.overflow--;return 0;}
               var last:Object=profile.stack[profile.stack.length-1];
               if(last.name!=name) {profile.errors++;return 0;}
               profile.stack.pop();
               var elapsed:int=Math.max(0,int(now-int(last.started)));
               var counter:Object=profile.aggregates[name];
               counter.completed++;counter.total_ms+=elapsed;counter.max_ms=Math.max(counter.max_ms,elapsed);
               root.times[name]=int(root.times[name])+elapsed;
               return int(trace.generation);
            }
            // Only the existing ApexTick finally closes its enclosing span.
            // Missing inner leaves are interruptions, never forged completions.
            while(profile.stack.length>1) {
               last=profile.stack.pop();elapsed=Math.max(0,int(now-int(last.started)));
               counter=profile.aggregates[last.name];counter.interrupted++;
               counter.incomplete_total_ms+=elapsed;counter.incomplete_max_ms=Math.max(counter.incomplete_max_ms,elapsed);
               root.interrupted++;
            }
            profile.overflow=0;profile.stack.pop();
            elapsed=Math.max(0,int(now-int(root.started)));counter=profile.aggregates.tick;
            counter.completed++;counter.total_ms+=elapsed;counter.max_ms=Math.max(counter.max_ms,elapsed);
            profile.completed++;
            if(elapsed>=1) {
               var record:Object={operation:String(root.operation),phase:int(root.phase),total_ms:elapsed,phases:root.times,interrupted:int(root.interrupted)};
               if(profile.records.length<16) profile.records.push(record);
               else {
                  var smallest:int=0;
                  for(var i:int=1;i<16;i++) if(int(profile.records[i].total_ms)<int(profile.records[smallest].total_ms)) smallest=i;
                  if(elapsed>int(profile.records[smallest].total_ms)) profile.records[smallest]=record;
               }
            }
         } catch(profileError:*) {
            // Diagnostics never replace a native return, thrown value or ACK.
            try {if(trace.timer_profile!=null)trace.timer_profile.errors++;}catch(ignoredProfileError:*) { }
         }
         return 0;
      }

      private function ApexCatalogTimerStatus() : Object
      {
         var profile:Object=apexCatalogTrace==null ? null : apexCatalogTrace.timer_profile;
         if(profile==null)return {available:true,completed:0,errors:0,dropped:0,max_depth:0,record_limit:16,depth_limit:8,records:[],aggregates:{},incomplete:[],appearance_written:false};
         var incomplete:Array=[];
         for each(var row:Object in profile.stack) incomplete.push({phase:String(row.name)});
         return {available:true,completed:int(profile.completed),errors:int(profile.errors),dropped:int(profile.dropped),
            max_depth:int(profile.max_depth),record_limit:16,depth_limit:8,records:profile.records,aggregates:profile.aggregates,incomplete:incomplete,
            timing:"inclusive synchronous UI Timer milliseconds; interrupted phases are separate upper bounds; no CPU attribution",appearance_written:false};
      }
      // APEX_TIMER_TRACE_END helper-methods
