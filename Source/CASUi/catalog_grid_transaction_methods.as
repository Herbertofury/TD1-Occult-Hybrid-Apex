      // Frame-owned orchestration for the explicitly armed native grid adapter.
      // This fragment is inert until its initializer is wired with enabled=true.
      private var apexCatalogGrid:Object;

      private function ApexCatalogGridPermit() : Boolean
      {
         // A synchronous read of the installed native capture scope. No pipe
         // is opened and no appearance, input or catalog operation is submitted.
         var response:String;
         try {response=ApexNativeExchange("GRIDPERMIT|1");}
         catch(unavailable:Error) {return false;}
         return /^GRIDPERMIT\|[0-9a-f]{32}\|[1-9][0-9]{0,19}\|[1-9][0-9]{0,19}$/.test(response);
      }

      private function ApexCatalogGridBootstrap() : void
      {
         // Dedicated no-argument native Initialize seam. The original first
         // AddMessageListener has established the communication object, and
         // ConfigUI has already constructed the hidden panel/list/grid.
         if(!ApexCatalogGridPermit())return;
         try {ApexCatalogGridInitialize(true);}
         catch(error:Error) {
            // A missing future adapter must not escape into EA Initialize.
            // Before any Step, the native rollback unarms without touching
            // cells or claiming that an uncertain Draw was cancelled safely.
            var s:Object=apexCatalogGrid;
            if(s!=null) {
               s.enabled=false;s.error="Catalogue acceleration unavailable: "+error.message;
               apexCatalogError=s.error;
               if(s.lease!=null) {s.lease.active=false;s.lease.frame_validated=false;}
               removeEventListener(flash.events.Event.ENTER_FRAME,ApexCatalogGridFrame);
               RemoveMessageListener("CASSetSimInfo",ApexCatalogGridChanged);
               RemoveMessageListener("CASChangeMenuState",ApexCatalogGridChanged);
               RemoveMessageListener("CASPlannedOutfitTypeChanged",ApexCatalogGridChanged);
               RemoveMessageListener("CASClearSimsForReset",ApexCatalogGridChanged);
               try {
                  if(s.grid!=null && "ApexGridCancel" in s.grid && s.grid.ApexGridCancel is Function)
                     s.last=s.grid.ApexGridCancel("bootstrap-failed");
               } catch(cleanupError:Error) {s.error+="; adapter rollback unavailable: "+cleanupError.message;}
               s.grid=null;s.lease=null;
            }
         }
      }

      private function ApexCatalogGridInitialize(enabled:Boolean=false) : void
      {
         // A later ordinary initializer must not disarm the early bootstrap.
         // Explicit teardown/disable uses Dispose, never a default argument.
         if(apexCatalogGrid!=null && apexCatalogGrid.enabled===true && !apexCatalogGrid.disposed) {
            ApexCatalogGridPrepare();return;
         }
         if(apexCatalogGrid!=null)ApexCatalogGridDispose();
         apexCatalogGrid={enabled:enabled,disposed:false,running:false,input_reading:false,
            generation:0,frame:0,lease:null,grid:null,last:null,error:"",invalidations:0};
         if(!enabled)return;
         AddMessageListener("CASSetSimInfo",ApexCatalogGridChanged);
         AddMessageListener("CASChangeMenuState",ApexCatalogGridChanged);
         AddMessageListener("CASPlannedOutfitTypeChanged",ApexCatalogGridChanged);
         AddMessageListener("CASClearSimsForReset",ApexCatalogGridChanged);
         addEventListener(flash.events.Event.ENTER_FRAME,ApexCatalogGridFrame,false,20,true);
         // Integration must call this at a proven native Initialize seam
         // before HandleSetSimInfo/Show/Refresh. The existing ApexInitialize
         // return extension is too late to prove first-publication interception.
         ApexCatalogGridPrepare();
      }

      private function ApexCatalogGridPrepare() : Boolean
      {
         var s:Object=apexCatalogGrid;
         if(s==null || !s.enabled || s.disposed || s.error!="" || stage==null)return false;
         var panel:Object=mcClothingPanel;
         if(panel==null || panel.stage!==stage || panel.mcTileList==null || panel.mcTileList.mGridLayout==null)return false;
         var grid:Object=panel.mcTileList.mGridLayout;
         if(!("ApexGridBegin" in grid) || !(grid.ApexGridBegin is Function) ||
            !(grid.ApexGridStep is Function) || !(grid.ApexGridCancel is Function) || !(grid.ApexGridStatus is Function) ||
            !(grid.ApexGridNeedsWork is Function))
            throw new Error("Native incremental catalogue adapter unavailable");
         if(s.grid===grid && s.lease!=null && s.lease.active===true && s.lease.root===this &&
            s.lease.stage===stage && s.lease.panel===panel && s.lease.feed===grid.GetDataFeed())return true;
         if(s.grid===grid && s.lease!=null && (s.lease.stage!==stage || s.lease.panel!==panel))
            ApexCatalogGridInvalidate("display-context");
         if(s.grid===grid && s.lease!=null && s.lease.feed!==grid.GetDataFeed())ApexCatalogGridInvalidate("feed-replaced");
         if(s.grid!=null && s.grid!==grid) {
            // A replacement widget owns its own display tree. Do not run the
            // retiring provider's original bulk Reset against that new tree.
            ApexCatalogGridInvalidate("grid-replaced");s.grid.ApexGridCancel("dispose");
         }
         if(s.generation>=int.MAX_VALUE)throw new Error("Catalogue lease generation exhausted");
         var lease:Object={active:true,generation:++s.generation,root:this,stage:stage,panel:panel,grid:grid,
            feed:grid.GetDataFeed(),sim_id:"",household_id:"",owner:"",session:apexOwnerSession,
            layer:-1,outfit_type:-1,outfit_index:-1,state:int(mCurrState),native_generation:"",
            native_kind:0,native_mask:0,phase:"bootstrap",frame_validated:false};
         s.lease=lease;s.grid=grid;
         // Legal placeholder geometry arms native feed/input guards only.
         // This structural lease is NEVER stepped or published; measurement
         // requires the fresh bound-owner lease in Frame.
         s.last=grid.ApexGridBegin({columns:1,width:1,height:1,scale:1,gapX:0,gapY:0,
            viewWidth:1,viewHeight:1,scrollY:0,marginX:0,marginY:0,bootstrap:true,panel:panel,owner:lease,
            validate:ApexCatalogGridValidate,inputValidate:ApexCatalogGridInput});
         return true;
      }

      private function ApexCatalogGridLeaseCurrent(lease:Object) : Boolean
      {
         var s:Object=apexCatalogGrid;
         if(s==null || !s.enabled || s.disposed || lease==null || lease!==s.lease || lease.active!==true ||
            int(lease.generation)!=int(s.generation) || lease.root!==this || lease.stage!==stage || stage==null ||
            lease.panel!==mcClothingPanel || lease.panel.stage!==stage || lease.panel.mcTileList==null ||
            lease.grid!==lease.panel.mcTileList.mGridLayout || lease.grid!==s.grid ||
            lease.feed!==lease.grid.GetDataFeed())return false;
         if(lease.phase=="bootstrap")return true;
         return lease.phase=="bound" && mCurrSimInfo!=null &&
            String(mCurrSimInfo.simId)===lease.sim_id && String(mCurrSimInfo.householdId)===lease.household_id &&
            int(mCurrSimInfo.occultLayer)==lease.layer && int(mCurrSimInfo.occultType)==lease.native_kind &&
            int(mCurrSimInfo.allOccultTypes)==lease.native_mask && apexBoundSim===lease.sim_id &&
            apexFormsSelectedId===lease.owner && apexOwnerSession==lease.session &&
            apexFormsNativeGeneration===lease.native_generation && apexFormsNativeState=="bound" &&
            apexFormsDesiredId=="" && apexFormsIntent==null && apexFormsNativeIntent==null &&
            apexMoleculeIntent==null && apexPairIntent==null && !apexFormsApplying && int(mCurrState)==lease.state;
      }

      private function ApexCatalogGridValidate(lease:Object) : Boolean
      {
         // Native layout validation is pure, including constructor/resize
         // reentry. Engine reads occur once in Main's owned frame below.
         return ApexCatalogGridLeaseCurrent(lease) &&
            (lease.phase=="bootstrap" || apexCatalogGrid.running===true && lease.frame_validated===true);
      }

      private function ApexCatalogGridObserve() : Object
      {
         var s:Object=apexCatalogGrid;
         if(s!=null)s.waiting="form-handshake";
         if(s==null || !s.enabled || s.disposed || !(s.running || s.input_reading) || apexDisconnected ||
            stage==null || mCurrSimInfo==null || apexFormsNativeState!="bound" || apexFormsSelectedId=="" ||
            apexFormsNativeGeneration=="" || apexFormsDesiredId!="" || apexOwnerSession<=0 ||
            apexFormsIntent!=null || apexFormsNativeIntent!=null || apexMoleculeIntent!=null ||
            apexPairIntent!=null || apexFormsApplying)return null;
         var raw:Object=null;var selected:Object=null;var slot:Object=null;var current:Array=null;
         try {
            raw=CommunicationManager.CallGameService("CASGetSimInfo",null,true);
            selected=ApexOwnerSimRow(raw);raw=null;
            slot=CommunicationManager.CallGameService("CasGetCurrSimOutfitSlot",null,true);
            s.waiting="selected-sim-outfit";
            if(selected==null || slot==null || !(slot.outfit_type is int) || !(slot.outfit_index is int) ||
               slot.outfit_type<0 || slot.outfit_index<0 || selected.sim_id!==apexBoundSim ||
               selected.sim_id!==String(mCurrSimInfo.simId) || selected.household_id!==String(mCurrSimInfo.householdId) ||
               selected.occult_layer!=int(mCurrSimInfo.occultLayer) ||
               selected.all_occult_types!=int(mCurrSimInfo.allOccultTypes))return null;
            // Physical kind/layer alone cannot distinguish two independent
            // named owners using the same renderer. Read the actual cursor.
            current=ApexNativeExchange("GRIDSTATE|"+apexNativeChannel).split("|");
            s.waiting="rendered-owner-cursor";
            if(current.length!=9 || current[0]!="GRIDSTATE" || current[1]!==selected.sim_id ||
               current[2]!==selected.household_id || current[3]!==apexFormsSelectedId ||
               !/^(1|2|4|8|16|32|64)$/.test(current[4]) || current[4]!==String(int(mCurrSimInfo.occultType)) ||
               current[5]!==String(selected.occult_layer) ||
               current[6]!==String(selected.all_occult_types) || current[7]!==String(selected.all_occult_types) ||
               current[8]!==apexFormsNativeGeneration || !/^[1-9][0-9]{0,19}$/.test(current[8]))return null;
            s.waiting="";
            return {sim_id:selected.sim_id,household_id:selected.household_id,owner:String(current[3]),
               // EA's shell may stay Vampire while our independently bound
               // Alien (or another owner) renders. The authenticated cursor
               // attests the actual model; retain shell identity separately.
               session:apexOwnerSession,layer:int(selected.occult_layer),native_kind:int(current[4]),shell_kind:int(selected.occult_type),
               native_mask:int(selected.all_occult_types),native_generation:String(current[8]),
               outfit_type:int(slot.outfit_type),outfit_index:int(slot.outfit_index),state:int(mCurrState)};
         } finally {raw=null;selected=null;slot=null;current=null;}
      }

      private function ApexCatalogGridMatches(lease:Object,context:Object) : Boolean
      {
         return lease!=null && context!=null && lease.phase=="bound" && lease.sim_id===context.sim_id &&
            lease.household_id===context.household_id && lease.owner===context.owner && lease.session===context.session &&
            lease.layer===context.layer && lease.native_kind===context.native_kind && lease.shell_kind===context.shell_kind && lease.native_mask===context.native_mask &&
            lease.native_generation===context.native_generation && lease.outfit_type===context.outfit_type &&
            lease.outfit_index===context.outfit_index && lease.state===context.state;
      }

      private function ApexCatalogGridFrameObserve() : Object
      {
         var s:Object=apexCatalogGrid;var lease:Object=s==null ? null : s.lease;
         if(!ApexCatalogGridLeaseCurrent(lease) || lease.phase!="bound" || !s.running)return null;
         var slot:Object=null;var current:Array=null;
         try {
            // Bootstrap/rebind and EVERY write-capable input use the complete
            // observation above. A visual frame reads the actual outfit and
            // native controller/household/model/cursor. This avoids requesting
            // a complete Sim-info object for each visual work frame.
            slot=CommunicationManager.CallGameService("CasGetCurrSimOutfitSlot",null,true);
            current=ApexNativeExchange("GRIDSTATE|"+apexNativeChannel).split("|");
            s.waiting="fresh-native-grid";
            if(slot==null || !(slot.outfit_type is int) || !(slot.outfit_index is int) ||
               slot.outfit_type<0 || slot.outfit_index<0 || current.length!=9 || current[0]!="GRIDSTATE" ||
               current[1]!==lease.sim_id || current[2]!==lease.household_id || current[3]!==lease.owner ||
               current[4]!==String(lease.native_kind) || current[5]!==String(lease.layer) ||
               current[6]!==String(lease.native_mask) || current[7]!==String(lease.native_mask) ||
               current[8]!==lease.native_generation)return null;
            s.waiting="";
            return {sim_id:String(current[1]),household_id:String(current[2]),owner:String(current[3]),
               session:lease.session,layer:int(current[5]),native_kind:int(current[4]),shell_kind:lease.shell_kind,
               native_mask:int(current[6]),native_generation:String(current[8]),
               outfit_type:int(slot.outfit_type),outfit_index:int(slot.outfit_index),state:int(mCurrState)};
         } finally {slot=null;current=null;}
      }

      private function ApexCatalogGridInput(lease:Object) : Boolean
      {
         // Write-capable cell events receive a fresh bounded identity read.
         // A missed/delayed EA notification must never apply an old card to a
         // newly selected Sim, named form, category or outfit between frames.
         var s:Object=apexCatalogGrid;
         if(!ApexCatalogGridLeaseCurrent(lease) || lease.phase!="bound" || s.input_reading)return false;
         s.input_reading=true;
         try {
            if(ApexCatalogGridMatches(lease,ApexCatalogGridObserve()))return true;
            ApexCatalogGridInvalidate("input-context");return false;
         } catch(error:Error) {
            s.error="Catalogue input identity unavailable: "+error.message;
            ApexCatalogGridInvalidate("input-context");return false;
         } finally {s.input_reading=false;}
      }

      private function ApexCatalogGridRequest(lease:Object) : Object
      {
         if(!ApexCatalogGridLeaseCurrent(lease) || lease.phase!="bound")return null;
         var list:Object=lease.panel.mcTileList;var view:Object=list.mScrollerView;
         if(view==null || list.mSlider==null || !isFinite(Number(view.width)) || Number(view.width)<=0 ||
            !isFinite(Number(view.height)) || Number(view.height)<=0 || !isFinite(Number(list.mSlider.Value)))return null;
         // Measure the first REAL native cell and retain it for the fitted pool.
         // Only the freshly observed bound owner may step this measurement.
         if(apexCardGeometry==null || apexCardGeometry.grid!==lease.grid || apexCardLayout==null)
            return {columns:1,width:1,height:1,scale:1,gapX:0,gapY:0,viewWidth:Number(view.width),viewHeight:Number(view.height),
               scrollY:0,marginX:0,marginY:0,bootstrap:true,panel:lease.panel,owner:lease,
               validate:ApexCatalogGridValidate,inputValidate:ApexCatalogGridInput};
         var p:Object=apexCardLayout;var margin:Object=lease.grid.GetCellPadding();
         if(margin==null || !isFinite(Number(p.scale)) || Number(p.scale)<=0 ||
            !isFinite(Number(p.card_width)) || Number(p.card_width)<=0 || !isFinite(Number(p.card_height)) || Number(p.card_height)<=0 ||
            int(p.columns)<2)return null;
         return {columns:int(p.columns),width:Number(p.card_width),height:Number(p.card_height),scale:Number(p.scale),
            gapX:Number(p.gap_x),gapY:Number(p.gap_y),viewWidth:Number(view.width),viewHeight:Number(view.height),
            scrollY:Number(list.mSlider.Value),marginX:Number(margin.mLeft),marginY:Number(margin.mTop),bootstrap:false,
            panel:lease.panel,owner:lease,validate:ApexCatalogGridValidate,inputValidate:ApexCatalogGridInput};
      }

      private function ApexCatalogGridFrame(event:flash.events.Event=null) : void
      {
         var s:Object=apexCatalogGrid;
         if(s==null || !s.enabled || s.disposed || s.error!="" || s.running || stage==null)return;
         // A hidden clothing grid has no visible work. Keep its native guards
         // armed, but do not poll the engine or construct/bind an offscreen pool.
         // Explicit disposal/error cleanup releases its lease synchronously.
         if(mcClothingPanel==null || mCurrentPanel!==mcClothingPanel || mcClothingPanel.visible!==true)return;
         // A coherent idle grid needs no engine reads or status allocations.
         // Write input still validates the actual current owner and outfit.
         if(s.lease!=null && ApexCatalogGridLeaseCurrent(s.lease) && s.lease.phase=="bound" &&
            s.lease.geometry_signature===apexCatalogSignature && apexCardGeometry!=null &&
            apexCardGeometry.grid===s.grid && apexCardLayout!=null && s.grid.ApexGridNeedsWork()===false)return;
         var started:int=flash.utils.getTimer();
         s.running=true;
         try {
            if(!ApexCatalogGridPrepare())return;
            var lease:Object=s.lease;
            var context:Object=lease.phase=="bound" ? ApexCatalogGridFrameObserve() : ApexCatalogGridObserve();
            if(context==null) {if(lease.phase!="bootstrap")ApexCatalogGridInvalidate("context-unsettled");return;}
            if(!ApexCatalogGridMatches(lease,context)) {
               // A changed bound outfit/category is a rebind, not permission
               // to seed another lease from the visual-only observation.
               if(lease.phase=="bound") {ApexCatalogGridInvalidate("bound-context-change");return;}
               ApexCatalogGridInvalidate("owner");
               if(s.generation>=int.MAX_VALUE)throw new Error("Catalogue lease generation exhausted");
               lease={active:true,generation:++s.generation,root:this,stage:stage,panel:mcClothingPanel,grid:s.grid,
                  feed:s.grid.GetDataFeed(),sim_id:context.sim_id,household_id:context.household_id,owner:context.owner,
                  session:context.session,layer:context.layer,native_kind:context.native_kind,shell_kind:context.shell_kind,native_mask:context.native_mask,
                  native_generation:context.native_generation,outfit_type:context.outfit_type,outfit_index:context.outfit_index,
                  state:context.state,phase:"bound",frame_validated:true};
               s.lease=lease;
            }
            lease.frame_validated=true;
            var request:Object=ApexCatalogGridRequest(lease);
            if(request==null) {s.waiting="panel-geometry";return;}
            if(s.frame<int.MAX_VALUE)s.frame++;s.last=s.grid.ApexGridBegin(request);
            lease.geometry_signature=apexCatalogSignature;
            s.last=s.grid.ApexGridStep(64,flash.utils.getTimer()+1);
            if(apexCatalogGrid!==s || s.disposed)return;
            if(s.last!=null && s.last.error!=null)throw new Error(String(s.last.error));
         } catch(error:Error) {
            s.error="Incremental catalogue paused: "+error.message;
            ApexCatalogGridInvalidate("error-abandon");
         } finally {
            if(s.lease!=null)s.lease.frame_validated=false;
            s.running=false;
            var elapsed:int=Math.max(0,flash.utils.getTimer()-started);
            s.frame_max_ms=Math.max(int(s.frame_max_ms),elapsed);
            if(elapsed>1 && int(s.over_1ms)<int.MAX_VALUE)s.over_1ms=int(s.over_1ms)+1;
         }
      }

      private function ApexCatalogGridInvalidate(reason:String) : void
      {
         var s:Object=apexCatalogGrid;if(s==null || s.disposed)return;
         if(s.lease!=null) {
            s.lease.active=false;s.lease.frame_validated=false;
            if(s.generation<int.MAX_VALUE)s.lease.generation=++s.generation;
         }
         if(s.invalidations<int.MAX_VALUE)s.invalidations++;
         if(s.grid!=null)s.last=s.grid.ApexGridCancel(reason);
      }

      private function ApexCatalogGridChanged(message:Object=null) : void
      {
         // Synchronous notifications and explicit owner/member intent hooks
         // only invalidate cheap primitives; no engine query or list rebuild.
         ApexCatalogGridInvalidate("notification");
      }

      private function ApexCatalogGridOwns(grid:Object) : Boolean
      {
         var s:Object=apexCatalogGrid;
         return s!=null && s.enabled===true && !s.disposed && grid===s.grid;
      }

      private function ApexCatalogGridPending(grid:Object) : Boolean
      {
         var s:Object=apexCatalogGrid;
         if(s==null || !s.enabled || s.disposed || grid!==s.grid)return false;
         var status:Object=grid.ApexGridStatus();
         return s.lease==null || s.lease.phase!="bound" || s.lease.active!==true ||
            status==null || status.phase!="done" || status.dirty===true || status.cancelled===true;
      }

      private function ApexCatalogGridStatus() : Object
      {
         var s:Object=apexCatalogGrid;
         if(s==null)return {enabled:false,active:false,appearance_written:false};
         var lease:Object=s.lease;
         // Deliberately omit opaque root/stage/panel/grid/feed/Function leases.
         return {enabled:Boolean(s.enabled),active:lease!=null && lease.active===true,generation:int(s.generation),
            frame:int(s.frame),running:Boolean(s.running),invalidations:int(s.invalidations),error:String(s.error),waiting_reason:s.waiting==null ? "" : String(s.waiting),
            frame_timing:{max_ms:int(s.frame_max_ms),over_1ms:int(s.over_1ms),clock_resolution_ms:1},
            context:lease==null ? null : {sim_id:lease.sim_id,household_id:lease.household_id,owner:lease.owner,
               session:lease.session,layer:lease.layer,outfit_type:lease.outfit_type,outfit_index:lease.outfit_index,
               state:lease.state,native_kind:lease.native_kind,shell_kind:lease.shell_kind,native_generation:lease.native_generation,phase:lease.phase},
            native:s.grid==null ? null : s.grid.ApexGridStatus(),appearance_written:false};
      }

      private function ApexCatalogGridDispose() : void
      {
         var s:Object=apexCatalogGrid;if(s==null)return;
         s.disposed=true;s.enabled=false;
         if(s.lease!=null) {s.lease.active=false;s.lease.frame_validated=false;}
         removeEventListener(flash.events.Event.ENTER_FRAME,ApexCatalogGridFrame);
         RemoveMessageListener("CASSetSimInfo",ApexCatalogGridChanged);
         RemoveMessageListener("CASChangeMenuState",ApexCatalogGridChanged);
         RemoveMessageListener("CASPlannedOutfitTypeChanged",ApexCatalogGridChanged);
         RemoveMessageListener("CASClearSimsForReset",ApexCatalogGridChanged);
         try {if(s.grid!=null)s.grid.ApexGridCancel("dispose");}
         finally {s.lease=null;s.grid=null;s.last=null;apexCatalogGrid=null;}
      }
