      // Bounded diagnostics only. Inputs and retained records are copied
      // primitives; no card, product, image, feed or renderer is retained.
      private function ApexCatalogPublicationTraceStep(event:String,generation:int,target:int,oldCount:int) : void
      {
         var trace:Object=apexCatalogTrace;
         if(trace==null || generation!=int(trace.generation))return;
         try {
            var profile:Object=trace.publication_profile;
            if(!trace.enabled && ((event!="publication.leave" && event!="publication.interrupted") ||
               profile==null || profile.stack.length==0 && profile.overflow==0))return;
            var now:int=flash.utils.getTimer();
            if(event=="publication.enter") {
               if(CASCustomizerMain.apexCatalogDrawTraceStep!==trace.callback ||
                  uint(now-int(trace.started_ms))>=uint(trace.duration_ms)) {
                  trace.expired=true;ApexCatalogTraceDispose();return;
               }
               if(profile==null) {
                  var aggregates:Object={};
                  for each(var name:String in ["publication","pretexture","resize","posttexture","visibility","diagnostics","tail","other"])
                     aggregates[name]={started:0,completed:0,interrupted:0,total_ms:0,max_ms:0,incomplete_total_ms:0,incomplete_max_ms:0};
                  profile={available:true,generation:generation,stack:[],aggregates:aggregates,records:[],errors:0,dropped:0,overflow:0,max_depth:0,
                     record_limit:16,depth_limit:8,timing:"inclusive synchronous publication wall milliseconds; no CPU or GC attribution",appearance_written:false};
                  trace.publication_profile=profile;
               }
               if(profile.overflow>0 || profile.stack.length>=8) {profile.overflow++;profile.dropped++;return;}
               profile.stack.push({started:now,last:now,phase:"other",phase_started:now,target:target,old_count:oldCount,
                  times:{pretexture:0,resize:0,posttexture:0,visibility:0,diagnostics:0,tail:0,other:0},incomplete:false});
               profile.aggregates.publication.started++;profile.max_depth=Math.max(profile.max_depth,profile.stack.length);return;
            }
            if(profile==null)return;
            var rootEvent:Boolean=event=="publication.leave" || event=="publication.interrupted";
            if(profile.overflow>0) {if(rootEvent)profile.overflow--;return;}
            if(profile.stack.length==0) {profile.errors++;return;}
            var row:Object=profile.stack[profile.stack.length-1];
            var elapsed:Number=uint(now-int(row.last));
            if(rootEvent) {
               row.times[String(row.phase)]+=elapsed;profile.stack.pop();
               var total:Number=uint(now-int(row.started));
               var counter:Object=profile.aggregates.publication;
               var interrupted:Boolean=event=="publication.interrupted" || !trace.enabled || row.phase!="other" || row.incomplete;
               if(interrupted) {
                  counter.interrupted++;counter.incomplete_total_ms+=total;counter.incomplete_max_ms=Math.max(counter.incomplete_max_ms,total);
                  if(row.phase!="other") {
                     var inner:Object=profile.aggregates[String(row.phase)];var partial:Number=uint(now-int(row.phase_started));
                     inner.interrupted++;inner.incomplete_total_ms+=partial;inner.incomplete_max_ms=Math.max(inner.incomplete_max_ms,partial);
                  }
               } else {counter.completed++;counter.total_ms+=total;counter.max_ms=Math.max(counter.max_ms,total);}
               counter=profile.aggregates.other;counter.started++;
               if(interrupted) {counter.interrupted++;counter.incomplete_total_ms+=Number(row.times.other);counter.incomplete_max_ms=Math.max(counter.incomplete_max_ms,Number(row.times.other));}
               else {counter.completed++;counter.total_ms+=Number(row.times.other);counter.max_ms=Math.max(counter.max_ms,Number(row.times.other));}
               var record:Object={total_ms:total,target:int(row.target),old_count:int(row.old_count),interrupted:interrupted,phases:row.times};
               if(profile.records.length<16)profile.records.push(record);
               else {
                  var smallest:int=0;
                  for(var i:int=1;i<16;i++)if(Number(profile.records[i].total_ms)<Number(profile.records[smallest].total_ms))smallest=i;
                  if(total>Number(profile.records[smallest].total_ms))profile.records[smallest]=record;
               }
               return;
            }
            if(!trace.enabled || uint(now-int(trace.started_ms))>=uint(trace.duration_ms)) {
               trace.expired=true;ApexCatalogTraceDispose();return;
            }
            var parts:Array=event.split(".");
            if(parts.length!=2 || profile.aggregates[parts[0]]==null || parts[0]=="publication" || parts[0]=="other") {profile.errors++;return;}
            if(parts[1]=="enter") {
               if(row.phase!="other") {
                  // A legitimate early return from the presentation helper can
                  // enter tail checks without completing its inner fence.
                  row.times[String(row.phase)]+=elapsed;row.incomplete=true;
                  counter=profile.aggregates[String(row.phase)];duration=uint(now-int(row.phase_started));
                  counter.interrupted++;counter.incomplete_total_ms+=duration;counter.incomplete_max_ms=Math.max(counter.incomplete_max_ms,duration);
               } else row.times.other+=elapsed;
               row.last=now;row.phase=String(parts[0]);row.phase_started=now;
               profile.aggregates[parts[0]].started++;return;
            }
            if(parts[1]!="leave" || row.phase!==parts[0]) {profile.errors++;return;}
            row.times[String(row.phase)]+=elapsed;
            counter=profile.aggregates[String(row.phase)];var duration:Number=uint(now-int(row.phase_started));
            counter.completed++;counter.total_ms+=duration;counter.max_ms=Math.max(counter.max_ms,duration);
            row.last=now;row.phase="other";
         } catch(diagnosticError:*) {
            // Preserve every native return/throw, including arbitrary values.
            try {if(trace.publication_profile!=null)trace.publication_profile.errors++;}catch(ignoredDiagnosticError:*) { }
         }
      }
