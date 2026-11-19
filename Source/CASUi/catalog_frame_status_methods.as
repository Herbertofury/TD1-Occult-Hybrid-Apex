      // Reproduce the invariant/expiry effects of a status query without
      // constructing its detached counters, failure arrays or diagnostic maps.
      private function ApexGridFrameStatusEffects() : void {
         if(apexGridState==null || apexGridState.job==null)return;
         ApexTxnInvariant(apexGridState.job);
         ApexGridExpireMeasurement(apexGridState);
      }

      public final function ApexGridPendingFrame() : Boolean {
         ApexGridFrameStatusEffects();
         var s:Object=apexGridState;var j:Object=s==null ? null : s.job;
         return j==null || j.phase!="done" || j.dirty===true || j.cancelled===true;
      }

      public final function ApexGridGeometryFrame() : Object {
         ApexGridFrameStatusEffects();
         var s:Object=apexGridState;
         if(s==null || s.job==null)return null;
         // Only the exact six scalars consumed by IncrementalApply. The old
         // status did not define columns; its absent value remains absent.
         return {measurement_ready:s.measurementReady,natural_width:s.naturalWidth,natural_height:s.naturalHeight,
            natural_aspect:s.naturalAspect,measured_scale:s.measuredScale,measured_height:s.measuredHeight};
      }
