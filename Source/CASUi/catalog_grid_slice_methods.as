private function ApexTxnStep(j:Object, maxOperations:int=1, deadline:Number=0) : Object
      {
         if(j.running){j.reentrant++;return ApexTxnStatus(j);}
         if(j.phase=="done" && !j.dirty && j.adapter.ApexGridRevision()==j.revision)return ApexTxnStatus(j);
         if(j.phase=="done"){j.dirty=true;j.phase="acquire";}
         if(j.phase=="cancelled")return ApexTxnStatus(j);
         if(maxOperations<1 || maxOperations>64)throw new Error("Invalid transaction operation budget");
         j.running=true;
         try {
            var a:Object=j.adapter;
            var used:int=0;
            var transitions:int=0;
            while(used<maxOperations && transitions++<128) {
               ApexTxnInvariant(j);
               if(j.phase=="cancelled" || (j.phase=="done" && !j.dirty))break;
               if(!j.cancelled && !a.ApexGridValid(j.identity))ApexTxnCancel(j,"context");
               if(!j.cancelled && j.lease && !a.ApexGridOwns(j))ApexTxnCancel(j,"lease");
               // An admitted frame must make one bounded logical step of progress. Pure
               // owner checks may consume the soft slice before the first step.
               // Every original invariant/identity/lease and reentry check stays.
               if(transitions>1 && deadline>0 && a.ApexGridNow()>=deadline)break;
               if(!j.cancelled && j.phase!="acquire" && (j.dirty || a.ApexGridRevision()!=j.revision)) {
                  if(!j.lease){j.phase="acquire";}else ApexTxnPlan(j);
               }
               var before:String=j.phase;
               var started:Number=a.ApexGridNow();
               var performed:Boolean=ApexTxnAdvance(j);
               if(j.abandoned){j.pendingCell=null;j.pendingAttached=false;j.phase="cancelled";}
               ApexTxnInvariant(j);
               if(performed) {
                  used++;j.operations++;j.lastPhase=before;
                  j.phaseCounts[j.lastOperation]=int(j.phaseCounts[j.lastOperation])+1;
                  j.phaseMax[j.lastOperation]=Math.max(Number(j.phaseMax[j.lastOperation])||0,a.ApexGridNow()-started);
               } else if(j.phase==before)break;
            }
         } catch(error:Error) {
            j.error=String(error);ApexTxnCancel(j,"error");
            ApexTxnInvariant(j);
         } finally {j.running=false;}
         return ApexTxnStatus(j);
      }
