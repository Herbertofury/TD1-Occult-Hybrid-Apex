private function ApexCatalogGridStatus() : Object
      {
         var s:Object=apexCatalogGrid;
         if(s==null)return {enabled:false,active:false,appearance_written:false};
         var lease:Object=s.lease;
         var clockProbe:Object=null;
         // Only the explicitly claimed one-off catalogue-state read samples
         // clocks. No Frame/default status call invokes a provider clock here.
         if(apexPendingFields!=null && String(apexPendingFields[2])=="catalog-state" &&
            apexClaimNonce===apexNonce && !apexDisconnected && apexSocketActive) {
            var requestId:String=String(apexPendingFields[0]);
            if(s.clockProbeRequest!==requestId) {
               if(lease==null || lease.phase!="bound" || !ApexCatalogGridLeaseCurrent(lease))
                  clockProbe={available:false,reason:"no-current-owned-native-grid",request_id:requestId};
               else {
                  var mainBefore:int=flash.utils.getTimer();
                  var providerNow:Number=Number(s.grid.ApexGridNow());
                  var mainAfter:int=flash.utils.getTimer();
                  if(!isFinite(providerNow) || providerNow!=int(providerNow))throw new Error("Provider bracket clock is not a finite native integer");
                  if(apexCatalogGrid!==s || s.lease!==lease || !ApexCatalogGridLeaseCurrent(lease) ||
                     apexPendingFields==null || String(apexPendingFields[0])!==requestId || String(apexPendingFields[2])!=="catalog-state" ||
                     apexClaimNonce!==apexNonce || apexDisconnected || !apexSocketActive)
                     throw new Error("Clock bracket changed its exact native owner lease");
                  clockProbe={available:true,request_id:requestId,lease_generation:int(lease.generation),main_before_ms:mainBefore,provider_ms:providerNow,
                     main_after_ms:mainAfter,main_wrap:mainAfter<mainBefore,
                     provider_inside_main_bracket:mainAfter>=mainBefore && isFinite(providerNow) && providerNow>=mainBefore && providerNow<=mainAfter,
                     provider_offset_min_ms:providerNow-mainAfter,provider_offset_max_ms:providerNow-mainBefore,
                     appearance_written:false};
               }
               s.clockProbeRequest=requestId;s.clockProbe=clockProbe;
            } else {
               clockProbe=s.clockProbe;
               if(clockProbe!=null && clockProbe.available===true && (lease==null ||
                  int(clockProbe.lease_generation)!=int(lease.generation) || !ApexCatalogGridLeaseCurrent(lease)))
                  throw new Error("Cached clock bracket no longer has its sampled owner lease");
            }
         }
         // Deliberately omit opaque root/stage/panel/grid/feed/Function leases.
         var result:Object={enabled:Boolean(s.enabled),active:lease!=null && lease.active===true,generation:int(s.generation),
            frame:int(s.frame),running:Boolean(s.running),invalidations:int(s.invalidations),error:String(s.error),waiting_reason:s.waiting==null ? "" : String(s.waiting),
            frame_timing:{max_ms:int(s.frame_max_ms),over_1ms:int(s.over_1ms),clock_resolution_ms:1,
               pre_step_max_ms:int(s.frame_pre_step_max_ms),step_max_ms:int(s.frame_step_max_ms),
               max_frame_parts:{pre_step_ms:int(s.frame_max_pre_step_ms),step_ms:int(s.frame_max_step_ms)}},
            context:lease==null ? null : {panel_kind:lease.panel_kind,sim_id:lease.sim_id,household_id:lease.household_id,owner:lease.owner,
               session:lease.session,layer:lease.layer,outfit_type:lease.outfit_type,outfit_index:lease.outfit_index,
               state:lease.state,native_kind:lease.native_kind,shell_kind:lease.shell_kind,native_generation:lease.native_generation,phase:lease.phase},
            native:s.grid==null ? null : s.grid.ApexGridStatus(),appearance_written:false};
         if(clockProbe!=null)result.clock_probe=ApexClone(clockProbe);
         return result;
      }
