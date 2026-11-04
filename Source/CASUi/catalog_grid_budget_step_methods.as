public function ApexGridStep(maxOps:int=1, deadline:int=0) : Object {
         if(apexGridState==null)return {phase:"unarmed",active:false};
         if(apexGridState.job==null)return ApexGridStatus();
         var s:Object=apexGridState;
         if(!ApexGridValid(s.identity))ApexTxnCancel(s.job,"context");
         // This capability uses only a provider-local elapsed budget. The
         // independent Main clock is never compared with this movie's timer.
         var localBudget:Boolean=!s.job.cancelled && s.request!=null && s.request.stepBudgetClockContract===1;
         if(localBudget && s.request.stepBudgetMilliseconds!==1)throw new Error("Unsupported provider-local grid budget");
         if(s.bootstrap && !s.job.cancelled) {
            // One existing bootstrap atom preserves progress even at rollover.
            // Invalid caller budgets remain invalid, never sanitized to one.
            return ApexGridBootstrapStep(localBudget && maxOps>=1 && maxOps<=64 ? 1 : maxOps,localBudget ? 0 : deadline);
         }
         var result:Object=localBudget ? ApexTxnBudgetStep(s.job,maxOps,ApexGridNow()) : ApexTxnStep(s.job,maxOps,deadline);
         ApexGridMetrics(result);
         if(result.phase=="cancelled" && (result.reason=="dispose" || result.reason=="error-abandon"))s.request=null;
         if(result.phase=="cancelled" && s.nextRequest!=null) {
            var next:Object=s.nextRequest;s.nextRequest=null;
            return ApexGridBegin(next);
         }
         return result;
      }
