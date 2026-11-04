// Reviewed owned Main continuation; this is also the portable execution fixture.
private function ApexCatalogGridPrepare() : Boolean
      {
         var s:Object=apexCatalogGrid;
         if(s==null || !s.enabled || s.disposed || s.error!="" || stage==null)return false;
         if(s.retiring!=null)return false;
         var panel:Object=mCurrentPanel;
         if(panel==null || panel.visible!==true)panel=mcClothingPanel;
         var kind:String=ApexCatalogGridProductPanel(panel);
         if(kind=="")return false;
         var grid:Object=panel.mcTileList.mGridLayout;
         if(ApexCatalogAuthorityHold(grid))return ApexCatalogAuthorityRecover(panel,grid);
         if(s.grid!=null && s.grid!==grid && s.lease!=null && s.lease.phase=="bound") {
            // A new visible native panel does not authorize abandoning this
            // still-live widget's pending construction or suppression lease.
            ApexCatalogGridRetireInactive(s);return false;
         }
         if(!("ApexGridBegin" in grid) || !(grid.ApexGridBegin is Function) ||
            !(grid.ApexGridStep is Function) || !(grid.ApexGridCancel is Function) || !(grid.ApexGridStatus is Function) ||
            !(grid.ApexGridNeedsWork is Function))
            throw new Error("Native incremental catalogue adapter unavailable");
         if(s.grid===grid && s.lease!=null && s.lease.active===true && s.lease.root===this &&
            s.lease.stage===stage && s.lease.panel===panel && s.lease.feed===grid.GetDataFeed() &&
            s.lease.panel_kind===kind && s.lease.cell_type===grid.GetCellView)return true;
         if(s.grid===grid && s.lease!=null && (s.lease.stage!==stage || s.lease.panel!==panel))
            ApexCatalogGridInvalidate("display-context");
         if(s.grid===grid && s.lease!=null && s.lease.feed!==grid.GetDataFeed())ApexCatalogGridInvalidate("feed-replaced");
         if(s.grid===grid && s.lease!=null && (s.lease.panel_kind!==kind || s.lease.cell_type!==grid.GetCellView))
            ApexCatalogGridInvalidate("cell-schema");
         if(s.grid!=null && s.grid!==grid) {
            // A replacement widget owns its own display tree. Do not run the
            // retiring provider's original bulk Reset against that new tree.
            ApexCatalogGridInvalidate("grid-replaced");s.grid.ApexGridCancel("dispose");
         }
         if(s.generation>=int.MAX_VALUE)throw new Error("Catalogue lease generation exhausted");
         var lease:Object={active:true,generation:++s.generation,root:this,stage:stage,panel:panel,grid:grid,
            view:panel.mcTileList.GetGridView(),panel_kind:kind,cell_type:grid.GetCellView,feed:grid.GetDataFeed(),sim_id:"",household_id:"",owner:"",session:apexOwnerSession,
            layer:-1,outfit_type:-1,outfit_index:-1,state:int(mCurrState),native_generation:"",
            native_kind:0,native_mask:0,phase:"bootstrap",frame_validated:false};
         s.lease=lease;s.grid=grid;
         // Legal placeholder geometry arms native feed/input guards only.
         // This structural lease is NEVER stepped or published; measurement
         // requires the fresh bound-owner lease in Frame.
         s.last=grid.ApexGridBegin({columns:1,width:1,height:1,scale:1,gapX:0,gapY:0,
            viewWidth:1,viewHeight:1,scrollY:0,marginX:0,marginY:0,bootstrap:true,panel:panel,owner:lease,
            validate:ApexCatalogGridValidate,inputValidate:ApexCatalogGridInput,
            rowValidate:kind=="clothing" ? null : ApexCatalogGridProductRow});
         return true;
      }

private function ApexCatalogGridFrame(event:flash.events.Event=null) : void
      {
         var s:Object=apexCatalogGrid;
         if(s==null || !s.enabled || s.disposed || s.error!="" || s.running || stage==null)return;
         if(s.grid!=null && ApexCatalogAuthorityHold(s.grid)) {
            if(mCurrentPanel!=null && s.lease!=null && mCurrentPanel!==s.lease.panel && ApexCatalogGridProductPanel(mCurrentPanel)!="") {
               // Retire Main references only. The terminal provider owns release.
               s.lease=null;s.grid=null;s.retiring=null;
            } else {
               s.running=true;
               try {if(!ApexCatalogGridPrepare())return;}
               finally {s.running=false;}
            }
         }
         // Finish only owned cancellation atoms before considering a new
         // panel. No Sim query, Begin, Draw or old input can run in this lane.
         var workVisible:Boolean=ApexCatalogPanelVisible(mCurrentPanel);
         if(!workVisible && s.lease!=null && s.lease.phase=="bound" && s.lease.panel===mCurrentPanel && ApexCatalogGridLeaseCurrent(s.lease))workVisible=true;
         if(s.retiring!=null || !workVisible || ApexCatalogGridProductPanel(mCurrentPanel)=="") {
            // Initial hidden bootstrap must keep intercepting native setup.
            // It has never driven construction/publication and is not retired.
            if(s.retiring==null && (s.lease==null || s.lease.phase!="bound"))return;
            s.running=true;
            try {ApexCatalogGridRetireInactive(s);}
            catch(inactiveError:Error) {
               s.error="Inactive catalogue cleanup paused: "+inactiveError.message;
               ApexCatalogGridInvalidate("error-abandon");
            } finally {s.running=false;}
            return;
         }
         // A coherent idle grid needs no engine reads or status allocations.
         // Write input still validates the actual current owner and outfit.
         var retained:Object=ApexCardStateFor(s.grid);
         if(s.lease!=null && ApexCatalogGridLeaseCurrent(s.lease) && s.lease.phase=="bound" &&
            retained!=null && s.lease.geometry_signature===retained.signature && retained.geometry!=null &&
            retained.geometry.grid===s.grid && retained.geometry.panel===s.lease.panel && retained.layout!=null && s.grid.ApexGridNeedsWork()===false)return;
         var started:int=flash.utils.getTimer();
         var stepStarted:int=-1;
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
               lease={active:true,generation:++s.generation,root:this,stage:stage,panel:s.lease.panel,grid:s.grid,
                  view:s.lease.view,panel_kind:s.lease.panel_kind,cell_type:s.grid.GetCellView,feed:s.grid.GetDataFeed(),sim_id:context.sim_id,household_id:context.household_id,owner:context.owner,
                  session:context.session,layer:context.layer,native_kind:context.native_kind,shell_kind:context.shell_kind,native_mask:context.native_mask,
                  native_generation:context.native_generation,outfit_type:context.outfit_type,outfit_index:context.outfit_index,
                  state:context.state,phase:"bound",frame_validated:true};
               s.lease=lease;
            }
            lease.frame_validated=true;
            var request:Object=ApexCatalogGridRequest(lease);
            if(request==null) {s.waiting="panel-geometry";return;}
            ApexCatalogAuthorityRemember(lease);
            if(s.frame<int.MAX_VALUE)s.frame++;
            if(ApexCatalogFrameStatusAvailable(s.grid))s.grid.ApexGridBeginFrame(request);
            else s.last=s.grid.ApexGridBegin(request);
            retained=ApexCardStateFor(s.grid);
            lease.geometry_signature=retained==null ? "" : String(retained.signature);
            if(ApexCatalogAuthorityHold(s.grid))return;
            s.last=s.grid.ApexGridStep(64,(stepStarted=flash.utils.getTimer())+1);
            if(apexCatalogGrid!==s || s.disposed)return;
            if(ApexCatalogAuthorityHold(s.grid))return;
            if(s.last!=null && s.last.error!=null)throw new Error(String(s.last.error));
         } catch(error:Error) {
            s.error="Incremental catalogue paused: "+error.message;
            ApexCatalogGridInvalidate("error-abandon");
         } finally {
            if(s.lease!=null && !ApexCatalogAuthorityHold(s.grid))s.lease.frame_validated=false;
            s.running=false;
            var elapsed:int=Math.max(0,flash.utils.getTimer()-started);
            // Split the same three existing clocks without another native
            // query, timer sample or status allocation on working frames.
            var beforeStep:int=stepStarted<0 ? elapsed : Math.max(0,stepStarted-started);
            var inStep:int=stepStarted<0 ? 0 : Math.max(0,elapsed-beforeStep);
            s.frame_pre_step_max_ms=Math.max(int(s.frame_pre_step_max_ms),beforeStep);
            s.frame_step_max_ms=Math.max(int(s.frame_step_max_ms),inStep);
            if(elapsed>=int(s.frame_max_ms)) {
               s.frame_max_pre_step_ms=beforeStep;s.frame_max_step_ms=inStep;
            }
            s.frame_max_ms=Math.max(int(s.frame_max_ms),elapsed);
            if(elapsed>1 && int(s.over_1ms)<int.MAX_VALUE)s.over_1ms=int(s.over_1ms)+1;
         }
      }

private function ApexCatalogGridInvalidate(reason:String) : void
      {
         var s:Object=apexCatalogGrid;if(s==null || s.disposed)return;
         if(ApexCatalogAuthorityHold(s.grid))return;
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
         var s:Object=apexCatalogGrid;
         if(s!=null && s.authority_owners!=null)for each(var held:Object in s.authority_owners) {
            if(held.blocked===true)held.probe=true;
         }
         ApexCatalogGridInvalidate("notification");
      }

private function ApexCatalogGridInput(lease:Object) : Boolean
      {
         // Write-capable cell events receive a fresh bounded identity read.
         // A missed/delayed EA notification must never apply an old card to a
         // newly selected Sim, named form, category or outfit between frames.
         var s:Object=apexCatalogGrid;
         if(lease!=null && ApexCatalogAuthorityHold(lease.grid))return false;
         if(!ApexCatalogGridLeaseCurrent(lease) || lease.phase!="bound" || !ApexCatalogPanelVisible(lease.panel) || s.input_reading)return false;
         s.input_reading=true;
         try {
            if(ApexCatalogGridMatches(lease,ApexCatalogGridObserve()))return true;
            ApexCatalogGridInvalidate("input-context");return false;
         } catch(error:Error) {
            s.error="Catalogue input identity unavailable: "+error.message;
            ApexCatalogGridInvalidate("input-context");return false;
         } finally {s.input_reading=false;}
      }

private function ApexCatalogGridPending(grid:Object) : Boolean
      {
         if(ApexCatalogAuthorityHold(grid))return true;
         var s:Object=apexCatalogGrid;
         if(s==null || !s.enabled || s.disposed || grid!==s.grid)return false;
         if(ApexCatalogFrameStatusAvailable(grid)) {
            var pending:Boolean=grid.ApexGridPendingFrame();
            return s.lease==null || s.lease.phase!="bound" || s.lease.active!==true || pending;
         }
         var status:Object=grid.ApexGridStatus();
         return s.lease==null || s.lease.phase!="bound" || s.lease.active!==true ||
            status==null || status.phase!="done" || status.dirty===true || status.cancelled===true;
      }

private function ApexCatalogGridStatus() : Object
      {
         var s:Object=apexCatalogGrid;
         if(s==null)return {enabled:false,active:false,appearance_written:false};
         var blocked:Boolean=ApexCatalogAuthorityHold(s.grid);
         var held:Object=blocked ? ApexCatalogAuthorityHeld(s.grid) : null;
         if(held!=null)return {enabled:Boolean(s.enabled),active:false,generation:int(s.generation),
            frame:int(s.frame),running:Boolean(s.running),invalidations:int(s.invalidations),error:String(s.error),
            waiting_reason:"authority-lost",context:held.scope,authority:held.receipt,native:held.receipt,
            unattributed_effects:int(s.authority_unattributed_effects),appearance_written:false};
         var lease:Object=s.lease;
         var currentPanel:Object=mCurrentPanel;
         var currentList:Object=currentPanel==null || !("mcTileList" in currentPanel) ? null : currentPanel.mcTileList;
         var currentBackground:Object=currentPanel==null || !("mcPanelBackground" in currentPanel) ? null : currentPanel.mcPanelBackground;
         var currentGrid:Object=currentList==null ? null : currentList.mGridLayout;
         var currentView:Object=currentList==null ? null : currentList.GetGridView();
         var ancestry:Array=[];var ancestor:Object=currentView;var reachedRoot:Boolean=false;var containsPanel:Boolean=false;
         for(var ancestryDepth:int=0;ancestor!=null && ancestryDepth<64;ancestryDepth++) {
            ancestry.push({name:String(ancestor.name).substr(0,96),visible:ancestor.visible===true,stage_matches:ancestor.stage===stage,
               same_panel:ancestor===currentPanel,same_list:ancestor===currentList,
               same_scroller:currentList!=null && ancestor===currentList.mScrollerView,same_root:ancestor===this});
            if(ancestor===currentPanel)containsPanel=true;
            if(ancestor===this) {reachedRoot=true;break;}
            ancestor=ancestor.parent;
         }
         var geometry:Object=apexCardGeometry;var layout:Object=apexCardLayout;
         var currentGeometry:Boolean=currentGrid!=null && geometry!=null && geometry.grid===currentGrid && geometry.panel===currentPanel;
         var width:Number=currentGeometry && layout!=null ? Number(layout.width) : NaN;
         var applied:Object=currentGeometry ? geometry.controls_width_receipt : null;
         var margin:Object=currentList==null ? null : currentList.ScrollerViewMargin;
         var view:Object=currentList==null ? null : currentList.mScrollerView;
         var slider:Object=currentList==null ? null : currentList.mSlider;
         var receiptValid:Boolean=applied!=null && isFinite(width) && applied.request===width && applied.panel===currentPanel &&
            applied.list===currentList && applied.view===view && applied.gridView===currentView && applied.slider===slider &&
            applied.background===currentPanel.mcPanelBackground && applied.margin===margin &&
            applied.nativeWidth===Number(currentPanel.mcPanelBackground.width) && applied.nativeWidth===Number(currentList.width) &&
            applied.left===Number(margin.mLeft) && applied.right===Number(margin.mRight) && applied.horizontal===Number(margin.Horizontal) &&
            applied.viewX===Number(view.x) && applied.viewWidth===Number(view.width) &&
            applied.gridWidth===Number(currentView.width) && applied.sliderX===Number(slider.x) && applied.sliderWidth===Number(slider.width);
         // Deliberately omit opaque root/stage/panel/grid/feed/Function leases.
         return {enabled:Boolean(s.enabled),active:lease!=null && lease.active===true,generation:int(s.generation),
            frame:int(s.frame),running:Boolean(s.running),invalidations:int(s.invalidations),error:String(s.error),waiting_reason:s.waiting==null ? "" : String(s.waiting),
            scheduling:{current_grid_matches:currentGrid!=null && currentGrid===s.grid,current_grid_owned:currentGrid!=null && ApexCatalogGridOwns(currentGrid),
               current_panel_matches:lease!=null && lease.panel===currentPanel,lease_current:ApexCatalogGridLeaseCurrent(lease),
               current_panel_visible:ApexCatalogPanelVisible(currentPanel),panel_flag:currentPanel!=null && currentPanel.visible===true,
               list_flag:currentList!=null && currentList.visible===true,view_flag:currentView!=null && currentView.visible===true,
               list_stage_matches:currentList!=null && currentList.stage===stage,view_stage_matches:currentView!=null && currentView.stage===stage,
               reached_root:reachedRoot,contains_panel:containsPanel,ancestors:ancestry,
               card_geometry_incremental:currentGeometry && geometry.incremental===true,card_geometry_matches:currentGeometry,
               actual_repair_path:s.last_repair_grid===currentGrid && s.last_repair_panel===currentPanel ? String(s.last_repair_path) : "unobserved-current-grid",
               desired_width:isFinite(width) ? width : null,native_panel_width:currentBackground==null ? null : Number(currentBackground.width),
               native_list_width:currentList==null ? null : Number(currentList.width),native_scroller_width:view==null ? null : Number(view.width),
               native_grid_width:currentView==null ? null : Number(currentView.width),width_receipt_present:applied!=null,width_receipt_valid:receiptValid,
               retiring:s.retiring!=null},
            frame_timing:{max_ms:int(s.frame_max_ms),over_1ms:int(s.over_1ms),clock_resolution_ms:1,
               pre_step_max_ms:int(s.frame_pre_step_max_ms),step_max_ms:int(s.frame_step_max_ms),
               max_frame_parts:{pre_step_ms:int(s.frame_max_pre_step_ms),step_ms:int(s.frame_max_step_ms)}},
            context:held!=null ? held.scope : lease==null ? null : {panel_kind:lease.panel_kind,sim_id:lease.sim_id,household_id:lease.household_id,owner:lease.owner,
               session:lease.session,layer:lease.layer,outfit_type:lease.outfit_type,outfit_index:lease.outfit_index,
               state:lease.state,native_kind:lease.native_kind,shell_kind:lease.shell_kind,native_generation:lease.native_generation,phase:lease.phase},
            authority:held==null ? null : held.receipt,
            native:held!=null ? held.receipt : s.grid==null ? null : s.grid.ApexGridStatus(),appearance_written:false};
      }

private function ApexCatalogGridRetireInactive(s:Object) : void
      {
         if(apexCatalogGrid!==s || s.disposed)return;
         if(ApexCatalogAuthorityHold(s.grid)) {s.lease=null;s.grid=null;s.retiring=null;return;}
         var held:Object=s.retiring;
         if(held==null) {
            var lease:Object=s.lease;
            if(lease==null || lease.phase!="bound" || lease.root!==this || s.grid!==lease.grid)return;
            held={grid:s.grid,lease:lease,panel:lease.panel,list:lease.panel.mcTileList,
               view:lease.panel.mcTileList==null ? null : lease.panel.mcTileList.GetGridView(),stage:stage,cancelled:false};
            s.retiring=held;s.waiting="inactive-cancel";
         }
         if(s.grid!==held.grid || s.lease!==held.lease || held.lease.root!==this)
            throw new Error("Inactive catalogue ownership changed");
         if(!held.cancelled) {
            held.cancelled=true;ApexCatalogGridInvalidate("inactive");return;
         }
         // A replaced/removed widget owns its retiring display tree. Use the
         // existing terminal release path; never detach from its replacement.
         if(held.list==null || held.view==null || held.panel.stage!==held.stage || held.panel.mcTileList!==held.list ||
            held.list.mGridLayout!==held.grid || held.list.GetGridView()!==held.view) {
            s.last=held.grid.ApexGridCancel("dispose");
         } else {
            var observed:Object=held.grid.ApexGridStatus();
            if(observed==null || observed.cancelled!==true || (observed.phase!="cancel" && observed.phase!="cancelled"))
               throw new Error("Inactive catalogue did not retain its cancellation");
            if(observed.phase=="cancel") {
               s.waiting="inactive-cleanup";
               // One existing cancellation operation per frame. The provider
               // retains its native rollback/lease and pending-widget checks.
               s.last=held.grid.ApexGridStep(1,0);
            } else s.last=observed;
         }
         if(apexCatalogGrid!==s || s.disposed || s.retiring!==held || s.grid!==held.grid || s.lease!==held.lease)return;
         if(s.last!=null && s.last.error!=null)throw new Error(String(s.last.error));
         if(s.last!=null && s.last.phase=="cancelled") {
            s.lease=null;s.retiring=null;s.waiting="inactive";
         }
      }

private function ApexCatalogGridOwns(grid:Object) : Boolean
      {
         var s:Object=apexCatalogGrid;
         return s!=null && s.enabled===true && !s.disposed && (grid===s.grid || ApexCatalogAuthorityHold(grid));
      }

private function ApexCatalogGridDispose() : void
      {
         var s:Object=apexCatalogGrid;if(s==null)return;
         if(apexCatalogEffects!=null)for each(var effectRecord:Object in apexCatalogEffects) {
            if(ApexCatalogAuthorityEffectHeld(effectRecord))effectRecord.authority_forget=true;
         }
         if(apexCardGeometry!=null && ApexCatalogAuthorityHold(apexCardGeometry.grid))ApexCardForget();
         if(apexPanelGeometry!=null)for(var key:String in apexPanelGeometry) {
            var saved:Object=apexPanelGeometry[key];
            if(saved!=null && saved.geometry!=null && ApexCatalogAuthorityHold(saved.geometry.grid))delete apexPanelGeometry[key];
         }
         s.disposed=true;s.enabled=false;
         if(s.lease!=null && !ApexCatalogAuthorityHold(s.grid)) {s.lease.active=false;s.lease.frame_validated=false;}
         removeEventListener(flash.events.Event.ENTER_FRAME,ApexCatalogGridFrame);
         RemoveMessageListener("CASSetSimInfo",ApexCatalogGridChanged);
         RemoveMessageListener("CASChangeMenuState",ApexCatalogGridChanged);
         RemoveMessageListener("CASPlannedOutfitTypeChanged",ApexCatalogGridChanged);
         RemoveMessageListener("CASClearSimsForReset",ApexCatalogGridChanged);
         try {if(s.grid!=null && !ApexCatalogAuthorityHold(s.grid))s.grid.ApexGridCancel("dispose");}
         finally {s.lease=null;s.grid=null;s.last=null;apexCatalogGrid=null;}
      }

private function ApexCardApply(panel:Object,grid:Object) : Number
      {
         if(ApexCatalogAuthorityHold(grid))return Number(panel.mcPanelBackground.width);
         if(!ApexCardActivate(panel,grid))return Number(panel.mcPanelBackground.width);
         var incrementalOwned:Boolean=ApexCatalogGridOwns(grid);
         if(apexCatalogGrid!=null) {
            apexCatalogGrid.last_repair_path=incrementalOwned ? "incremental" : "legacy";
            apexCatalogGrid.last_repair_grid=grid;apexCatalogGrid.last_repair_panel=panel;
         }
         if(incrementalOwned)return ApexCardIncrementalApply(panel,grid);
         if(grid.SuppressUpdates===true || apexCardGeometry!=null && apexCardGeometry.applying===true)
            return Number(panel.mcPanelBackground.width);
         var donor:Object=apexCompanion==null ? null : apexCompanion.layout_owner;
         // Donor controls now queue values through named UI services. Never
         // read its transient reset-to-zero or fitted values back as user
         // preferences; that feedback caused competing layouts on navigation.
         if(apexCardGeometry==null || apexCardGeometry.grid!==grid) {
            if(apexCardGeometry!=null)return Number(panel.mcPanelBackground.width);
            var bounds:flash.geom.Rectangle=grid.GetCellBounds();
            if(bounds==null || bounds.width<=0 || bounds.height<=0) throw new Error("Native card bounds unavailable");
            var nativePadding:Object=grid.GetCellPadding();
            var dimensions:Array=grid.GetGridDimensions();
            var nativeCell:Object=null;
            for each(var candidate:Object in ApexCatalogCells(grid)) {
               if(candidate!=null && candidate.scaleX>0 && candidate.width>0) {nativeCell=candidate;break;}
            }
            if(nativeCell==null) return 262;
            apexCardGeometry={grid:grid,panel:panel,bounds:bounds.clone(),padding:nativePadding,
               columns:int(dimensions[grid.Horizontal ? 0 : 1]),width:panel.mcPanelBackground.width,
               title_x:panel.txtTitle==null ? null : panel.txtTitle.x,random_x:ApexCatalogOptional(panel,"btnRandomize")==null ? null : ApexCatalogOptional(panel,"btnRandomize").x,
               filter_width:panel.mcFilterPane==null ? null : panel.mcFilterPane.mcFilterBubble.mcBackground.width,
               cell_width:Number(nativeCell.width)/Number(nativeCell.scaleX)};
            apexCatalogSignature="";
         }
         var geometry:Object=apexCardGeometry;geometry.applying=true;
         try {
         var base:flash.geom.Rectangle=geometry.bounds;
         // EA measures horizontal pitch from the complete card (including its
         // frame), whereas getBounds() returns only the narrower input area.
         var naturalWidth:Number=Number(apexCardGeometry.cell_width);
         // Native UI size and physical stage pixels can differ with UI scale.
         // Bound the region in this panel's actual local units, while retaining
         // EA's logical safe-area width for its native attachment/clamp.
         var origin:flash.geom.Point=panel.localToGlobal(new flash.geom.Point(0,0));
         var unit:flash.geom.Point=panel.localToGlobal(new flash.geom.Point(1,0));
         var unitWidth:Number=Math.abs(unit.x-origin.x);
         var viewportWidth:Number=Math.min(Number(LayoutAPI.StageWidth),Number(stage.stageWidth)/unitWidth);
         if(!isFinite(unitWidth) || unitWidth<=0 || !isFinite(viewportWidth) || viewportWidth<=0)
            throw new Error("Native catalogue viewport unavailable");
         var fitted:Object=ApexCardFit(int(apexCatalogPrefs.columns),viewportWidth,Number(apexCardPrefs.scale),
            Number(apexCardPrefs.gap_x),Number(apexCardPrefs.gap_y),naturalWidth,base.height,ApexCatalogWidthRequest(panel));
         var scale:Number=Number(fitted.scale);
         var pitch:Number=naturalWidth*scale+Number(fitted.gap_x);
         var columns:int=int(fitted.columns);var width:Number=Number(fitted.width);
         var currentCells:Object=ApexCatalogCells(grid);
         var rowHeight:Number=base.height*scale;
         if(currentCells!=null && currentCells.length>0) {
            var first:Object=currentCells[0];
            var hit:Object=ApexCatalogOptional(first,"mcHitArea");
            var localHeight:Number=hit==null ? base.height : Number(hit.height);
            var aspect:Number=Number(first.scaleY)/Number(first.scaleX);
            if(!isFinite(localHeight) || localHeight<=0 || !isFinite(aspect) || aspect<=0)
               throw new Error("Native card row height unavailable");
            rowHeight=localHeight*scale*aspect;
         }
         if(!isFinite(rowHeight) || rowHeight<=0) throw new Error("Native card row height unavailable");
         // GFx rounds native coordinates to twips. Do not turn sub-twip
         // transform noise into a repeated geometry transaction.
         if(geometry.row_height!=null && Math.abs(rowHeight-Number(geometry.row_height))<=0.05+0.000001)
            rowHeight=Number(geometry.row_height);
         fitted.card_height=rowHeight;fitted.pitch_y=rowHeight+Number(apexCardPrefs.gap_y);
         if(donor!=null && apexCompanion.donor!=null) {
            donor.modded_numcolumns=columns;donor.modded_thumbnail_scale=scale;donor.modded_catalog_width=width;
            apexCompanion.layout_seen=true;apexCompanion.layout_columns=columns;apexCompanion.layout_scale=scale;
         }
         // Category identity is not geometry. Retain the fitted pool across
         // category changes; newly recycled cells are still scaled below.
         var signature:String="cards:"+columns+":"+viewportWidth+":"+scale+":"+
            apexCardPrefs.gap_x+":"+apexCardPrefs.gap_y+":"+width;
         var actualDimensions:Array=grid.GetGridDimensions();
         var reflow:Boolean=signature!=apexCatalogSignature || int(actualDimensions[grid.Horizontal ? 0 : 1])!=columns ||
            geometry.row_height==null || Math.abs(rowHeight-Number(geometry.row_height))>0.05+0.000001;
         var redraw:Boolean=reflow;
         // Native dimension setters synchronously PositionCells/Draw. Commit
         // the complete geometry under EA's own suppression flag, then bind
         // the final visible pool once. No item/Sim appearance is cached.
         grid.SuppressUpdates=true;
         try {
          if(reflow) {
            ApexCatalogClearEffects();
            apexCardReflowAttempts=0;
            grid.NumLines=columns;
            grid.CellViewSizeFallback=new flash.geom.Point(naturalWidth*scale,rowHeight);
            ApexCardScaleCells(grid,scale);
            // Bounds size new recycled cells. Keep the live donor aspect
            // while repairing the width setter's temporary X-only scaling.
            grid.SetCellBounds(new flash.geom.Rectangle(base.x,base.y,naturalWidth*scale,0));
            ApexCardScaleCells(grid,scale,false);
            grid.SetCellPadding(new Margin(0,0,apexCardPrefs.gap_y,fitted.gap_x));
            panel.width=width;
          } else ApexCardScaleCells(grid,scale);
         apexCardLayout=fitted;apexCardLayout.hit_width=base.width*scale;
         if(ApexCardRepairControls(panel,width,reflow))redraw=true;
         } finally {grid.SuppressUpdates=false;}
         if(redraw) {
            // SetupCells can grow or shrink the pool. Retire the frame-local
            // enumeration before and after binding to include its new cells.
            apexCatalogFrameCells=null;ApexLayoutReset(grid);apexCatalogFrameCells=null;
            ApexCardScaleCells(grid,scale);
            apexCatalogSignature=signature;geometry.row_height=rowHeight;
            if(reflow && apexCatalogLayoutChanges<int.MAX_VALUE)apexCatalogLayoutChanges++;
         }
         // A native draw can publish its dimensions after the first layout.
         // Reset the stock row cache explicitly: PositionCells(false) preserves
         // an uninitialised NaN anchor after the recycling pool resizes.
         // Repair actual row coordinates, with a finite convergence bound;
         // never turn a failed resize into an endless idle layout loop.
         if(!ApexCardRowsAligned(grid,columns,Number(fitted.pitch_y),Number(fitted.pitch_x))) {
            if(++apexCardReflowAttempts>30) throw new Error("Native card rows did not converge to their measured height");
            ApexLayoutReset(grid);
         } else apexCardReflowAttempts=0;
         return width;
         } finally {geometry.applying=false;}
      }

private function ApexCardIncrementalApply(panel:Object,grid:Object) : Number
      {
         if(ApexCatalogAuthorityHold(grid))return Number(panel.mcPanelBackground.width);
         var native:Object=ApexCatalogFrameStatusAvailable(grid) ? grid.ApexGridGeometryFrame() : grid.ApexGridStatus();
         if(native==null || native.measurement_ready!==true) {
            apexCardLayout=null;
            return Number(panel.mcPanelBackground.width);
         }
         var naturalWidth:Number=Number(native.natural_width);
         var naturalHeight:Number=Number(native.natural_height);
         var aspect:Number=Number(native.natural_aspect);
         if(!isFinite(naturalWidth) || naturalWidth<=0 || !isFinite(naturalHeight) || naturalHeight<=0 ||
            !isFinite(aspect) || aspect<=0)throw new Error("Native card measurement unavailable");
         if(apexCardGeometry!=null && apexCardGeometry.grid!==grid) {
            if(apexCardGeometry.incremental!==true)throw new Error("Cannot replace a live legacy geometry transaction");
            ApexCardForget();
            if(apexCardGeometry!=null)return Number(panel.mcPanelBackground.width);
         }
         if(apexCardGeometry==null) {
            // GetCellBounds may construct a second probe when the native
            // height is zero. Use the retained real cell's intrinsic metrics.
            apexCardGeometry={grid:grid,panel:panel,incremental:true,
               bounds:new flash.geom.Rectangle(0,0,naturalWidth,naturalHeight),padding:grid.GetCellPadding(),
               width:panel.mcPanelBackground.width,columns:int(native.columns),cell_width:naturalWidth,
               title_x:panel.txtTitle==null ? null : panel.txtTitle.x,random_x:ApexCatalogOptional(panel,"btnRandomize")==null ? null : ApexCatalogOptional(panel,"btnRandomize").x,
               filter_width:panel.mcFilterPane==null ? null : panel.mcFilterPane.mcFilterBubble.mcBackground.width};
            apexCatalogSignature="";
         }
         var geometry:Object=apexCardGeometry;
         if(geometry.applying===true)return Number(panel.mcPanelBackground.width);
         geometry.applying=true;
         try {
            var origin:flash.geom.Point=panel.localToGlobal(new flash.geom.Point(0,0));
            var unit:flash.geom.Point=panel.localToGlobal(new flash.geom.Point(1,0));
            var unitWidth:Number=Math.abs(unit.x-origin.x);
            var viewportWidth:Number=Math.min(Number(LayoutAPI.StageWidth),Number(stage.stageWidth)/unitWidth);
            if(!isFinite(unitWidth) || unitWidth<=0 || !isFinite(viewportWidth) || viewportWidth<=0)
               throw new Error("Native catalogue viewport unavailable");
            var fitted:Object=ApexCardFit(int(apexCatalogPrefs.columns),viewportWidth,Number(apexCardPrefs.scale),
               Number(apexCardPrefs.gap_x),Number(apexCardPrefs.gap_y),naturalWidth,naturalHeight,ApexCatalogWidthRequest(panel));
            var rowHeight:Number=naturalHeight*Number(fitted.scale)*aspect;
            if(isFinite(Number(native.measured_scale)) && Number(native.measured_scale)==Number(fitted.scale) &&
               isFinite(Number(native.measured_height)) && Number(native.measured_height)>0)
               rowHeight=Number(native.measured_height);
            if(!isFinite(rowHeight) || rowHeight<=0)throw new Error("Native card row height unavailable");
            fitted.card_height=rowHeight;fitted.pitch_y=rowHeight+Number(fitted.gap_y);
            // Full-card metrics do not attest the separate native input mask.
            // Requested readbacks inspect that mask on the real bound cells.
            fitted.hit_width=null;
            var signature:String="cards:"+fitted.columns+":"+viewportWidth+":"+fitted.scale+":"+
               fitted.gap_x+":"+fitted.gap_y+":"+naturalWidth+":"+naturalHeight+":"+rowHeight+":"+fitted.width;
            var changed:Boolean=signature!=apexCatalogSignature;
            if(changed)ApexCatalogClearEffects();
            apexCardLayout=fitted;geometry.cell_width=naturalWidth;geometry.row_height=rowHeight;
            // These native control setters can emit layout/resize events. The
            // authenticated grid adapter coalesces them under its own lease;
            // Main never acquires/releases the provider's suppression flag.
            ApexCardRepairControls(panel,Number(fitted.width),changed);
            var donor:Object=apexCompanion==null ? null : apexCompanion.layout_owner;
            if(donor!=null && apexCompanion.donor!=null) {
               donor.modded_numcolumns=int(fitted.columns);donor.modded_thumbnail_scale=Number(fitted.scale);
               donor.modded_catalog_width=Number(fitted.width);apexCompanion.layout_seen=true;
               apexCompanion.layout_columns=int(fitted.columns);apexCompanion.layout_scale=Number(fitted.scale);
            }
            if(changed && apexCatalogLayoutChanges<int.MAX_VALUE)apexCatalogLayoutChanges++;
            apexCatalogSignature=signature;apexCardReflowAttempts=0;
            return Number(fitted.width);
         } finally {geometry.applying=false;}
      }

private function ApexCatalogFrame(event:flash.events.Event=null) : void
      {
         if(apexCatalogPrefs==null || stage==null || apexDisconnected) return;
         var frameStarted:int=flash.utils.getTimer();
         apexCatalogFrameCells=null;
         try {
         ApexPanelsFrame();
         var panel:Object=this.mCurrentPanel;
         if(ApexCatalogPanelKind(panel)!="") {
            var grid:Object=panel.mcTileList.mGridLayout;
            if(!ApexCatalogAuthorityHold(grid) && (apexCatalogDisplayFaults==null || !ApexCatalogDisplayFaulted(panel,grid))) {
            try {
            var layoutStarted:int=flash.utils.getTimer();
            var width:Number=ApexCatalogPanelKind(panel)=="swatches" ? ApexSkinToneApply(panel,grid) : ApexCardApply(panel,grid);
            apexCatalogFrameTiming.layout_max_ms=Math.max(apexCatalogFrameTiming.layout_max_ms,flash.utils.getTimer()-layoutStarted);
            var bindingStarted:int=flash.utils.getTimer();
            ApexCatalogApplyBinding(width);
            apexCatalogFrameTiming.binding_max_ms=Math.max(apexCatalogFrameTiming.binding_max_ms,flash.utils.getTimer()-bindingStarted);
            var styleSignature:String=apexCatalogPrefs.color+":"+apexCatalogPrefs.glow+":"+apexCatalogPrefs.border;
            if(styleSignature!=apexCatalogStyleSignature) {
               ApexCatalogClearEffects();apexCatalogStyleSignature=styleSignature;
            }
            if(panel===mcClothingPanel && !ApexCatalogGridPending(grid))ApexCatalogSelection(grid);
            // Clear only this feature's displayed fault summary after another
            // healthy panel actually completes its apply. Private evidence stays.
            if(apexCatalogDisplayFaults!=null && apexCatalogError!="") {
               for each(var precedingFault:Object in apexCatalogDisplayFaults) {
                  if(apexCatalogError===precedingFault.display_message) {apexCatalogError="";break;}
               }
            }
            } catch(displayError:Error) {ApexCatalogDisplayFault(panel,grid,displayError);}
            }
         } else {
            if(apexCatalogEffects!=null && apexCatalogEffects.length>0) ApexCatalogClearEffects();
            // The hidden clothing panel retains its fitted recycled pool.
            // Restoring it to two columns here rebuilt every card when the
            // player returned from Body to Tattoos, then fitted it again.
            // Restore only on disposal, replacement grid, or a display fault.
            ApexCatalogApplyBinding(262);apexCatalogHeaderSignature="";
         }
         ApexColumnsFrame();
         if(apexCatalogUi!=null && apexCatalogUi.visible) {
            var visibleContext:String=mCurrSimInfo==null || apexFormsSelectedId=="" ? "" : String(mCurrSimInfo.simId)+"|"+apexFormsSelectedId;
            var visibleOwner:String=visibleContext=="" ? "" : visibleContext+"|"+apexNativeChannel+"|"+apexOwnerSession;
            if(visibleOwner!==apexCatalogObservedOwner || (apexCatalogContext!="" && apexCatalogContext!==visibleContext)) {
               apexCatalogObservedOwner=visibleOwner;
               // Retire the old owner's actionable rows immediately. Queue one
               // inventory read after the new native owner has actually bound.
               apexCatalogItems=[];apexCatalogSlot=null;apexCatalogPage=0;apexCatalogContext="";
               apexCatalogDirty=true;apexCatalogError="Updating equipped items for the selected Sim and form.";ApexCatalogDraw();
            }
            if(apexCatalogDirty && apexPendingFields==null && !apexReceiving && apexPendingPhase==0 &&
               mCurrSimInfo!=null && String(mCurrSimInfo.simId)===apexBoundSim && apexNativeChannel!="" &&
               (apexNativeConnected || apexFormsLocalCatalog) && apexFormsNativeState=="bound" &&
               apexFormsSelectedId!="" && apexFormsNativeGeneration!="" && apexOwnerSession>0 &&
               !apexFormsApplying && apexFormsDesiredId=="" && apexFormsNativeIntent==null && apexFormsIntent==null &&
               apexMoleculeIntent==null && apexPairIntent==null) {
               apexCatalogDirty=false;
               try {ApexCatalogReadEquipped();ApexCatalogDraw();}
               catch(refreshError:Error) {apexCatalogDirty=false;apexCatalogError=refreshError.message;}
            }
            // Keep layout controls away from the native thumbnail catalog so
            // size/spacing changes can be previewed while dragging a slider.
            var catalogX:Number=apexCatalogTab=="items" ? Math.max(12,stage.stageWidth-apexCatalogUi.width-20) : 12;
            if(apexCatalogUi.x!=catalogX)apexCatalogUi.x=catalogX;
            if(apexCatalogUi.y!=75)apexCatalogUi.y=75;
         }
         if(apexCatalogIntent!=null && apexPendingFields==null && !apexReceiving) {
            var intent:Object=apexCatalogIntent;apexCatalogIntent=null;
            try {
               if(intent.operation=="open") ApexEquippedOpen();
               else if(intent.operation=="navigate") {
                  if(String(mCurrSimInfo.simId)!=intent.sim_id || apexFormsSelectedId!=intent.owner_id)
                     throw new Error("The Sim or form changed; refresh equipped items");
                  var target:int=int(intent.state);
                  apexEquippedActive=false;apexEquippedInteraction=null;
                  apexEquippedRetirePending=true;
                  if(apexCatalogUi!=null) apexCatalogUi.visible=false;
                  HandleContextMenuSetMenuState({menuState:target,skipAnim:true,setZoomState:true});
                  CommunicationManager.SendUIMessage("CASChangeMenuState",target);
               }
            } catch(catalogError:Error) {apexCatalogError=catalogError.message;ApexCatalogDraw();}
         }
         if(apexPendingFields==null && !apexReceiving) {ApexEquippedFrame();ApexSearchFrame();ApexCompanionFrame();ApexCatalogKeyboardFrame();}
         } catch(frameError:Error) {
            apexCatalogError="Catalog display paused: "+frameError.message;
            if(apexCatalogGrid!=null) {
               apexCatalogGrid.error=apexCatalogError;ApexCatalogGridInvalidate("error-abandon");
            }
            removeEventListener(flash.events.Event.ENTER_FRAME,ApexCatalogFrame);
            ApexCatalogClearEffects();ApexCardRestore();
         }
         var frameElapsed:int=flash.utils.getTimer()-frameStarted;
         if(apexCatalogFrameTiming.samples<int.MAX_VALUE) apexCatalogFrameTiming.samples++;
         apexCatalogFrameTiming.total_ms+=frameElapsed;
         apexCatalogFrameTiming.max_ms=Math.max(apexCatalogFrameTiming.max_ms,frameElapsed);
         if(frameElapsed>1 && apexCatalogFrameTiming.over_1ms<int.MAX_VALUE) apexCatalogFrameTiming.over_1ms++;
         apexCatalogFrameCells=null;
      }

private function ApexCardRestore() : void
      {
         if(apexCardGeometry==null) return;
         var geometry:Object=apexCardGeometry;
         var grid:Object=geometry.grid;
         if(ApexCatalogAuthorityHold(grid)) {ApexCardForget();return;}
         if(geometry.incremental===true || geometry.specialized===true) {
            // The controller owns retirement/rebinding. Never bulk-reset an
            // active or retired incremental pool from the legacy restore path.
            ApexCardForget();return;
         }
         // Respect an EA/other-mod layout transaction. Never release a lease
         // we did not acquire or leave a half-restored recycling pool.
         if(grid.SuppressUpdates===true || geometry.applying===true)return;
         geometry.applying=true;
         try {
         grid.SuppressUpdates=true;
         try {
         // Keep the empty marker's donor aspect across the native width
         // setter, which changes X alone. Suppression prevents intermediate
         // positioning; remove our marker before the final native redraw.
         grid.CellViewSizeFallback=null;
         grid.NumLines=geometry.columns;
         // The inherited DisplayObject height setter conflicts with EA's
         // specialised getter. The donor aspect owns height; never write it.
         grid.SetCellBounds(new flash.geom.Rectangle(geometry.bounds.x,geometry.bounds.y,geometry.bounds.width,0));
         for each(var cell:Object in ApexCatalogCells(grid)) {
            var marker:flash.display.DisplayObject=cell.getChildByName("apexCatalogCardScale");
            var aspect:Number=marker==null ? Number(cell.scaleY)/Number(cell.scaleX) : marker.scaleY;
            if(!isFinite(aspect) || aspect<=0) throw new Error("Native card aspect unavailable");
            cell.scaleX=1;cell.scaleY=aspect;
            if(marker!=null) cell.removeChild(marker);
         }
         grid.SetCellPadding(geometry.padding);
         var lastWidth:Number=Number(geometry.controls_width);
         if(geometry.panel.txtTitle!=null && geometry.title_x!=null &&
            geometry.panel.txtTitle.x==Number(geometry.title_x)+(lastWidth-Number(geometry.width))*0.5)
            geometry.panel.txtTitle.x=Number(geometry.title_x);
         if(ApexCatalogOptional(geometry.panel,"btnRandomize")!=null && geometry.random_x!=null &&
            ApexCatalogOptional(geometry.panel,"btnRandomize").x==Number(geometry.random_x)+lastWidth-Number(geometry.width))
            ApexCatalogOptional(geometry.panel,"btnRandomize").x=Number(geometry.random_x);
         var filter:Object=geometry.panel.mcFilterPane;
         if(filter!=null && filter.mcFilterBubble!=null && geometry.filter_width!=null && filter.mcFilterBubble.mcBackground.width==lastWidth-30)
            filter.mcFilterBubble.mcBackground.width=Number(geometry.filter_width);
         geometry.panel.width=geometry.width;
         geometry.panel.mcTileList.ScrollerAmount=Math.max(10,geometry.bounds.height*0.75);
         if(apexCompanion!=null && apexCompanion.donor!=null)apexCompanion.donor.PositionButton(geometry.panel);
         } finally {grid.SuppressUpdates=false;}
         apexCatalogFrameCells=null;
         ApexLayoutReset(grid);
         apexCardGeometry=null;apexCardLayout=null;apexCardReflowAttempts=0;apexCatalogSignature="";
         } finally {geometry.applying=false;}
      }

private function ApexCatalogSelection(grid:Object) : void
      {
         if(ApexCatalogAuthorityHold(grid))return;
         var started:int=flash.utils.getTimer();
         // Only EA's recycled visible cells are inspected. No catalog scan,
         // game query, thumbnail export or per-Sim appearance copy is needed.
         var cells:Object=ApexCatalogCells(grid);var kept:Array=[];
         for each(var cell:Object in cells) {
            if(cell==null || !cell.visible || !cell.Selected) continue;
            var effect:flash.display.Sprite=cell.getChildByName("apexSelectedBorder") as flash.display.Sprite;
            var retained:Object=null;
            for each(var previous:Object in apexCatalogEffects) if(previous.cell===cell) {retained=previous;break;}
            if(effect==null) {
               effect=new flash.display.Sprite();effect.name="apexSelectedBorder";effect.mouseEnabled=false;effect.mouseChildren=false;
               // Native getBounds() is the input hit area, including spacing
               // outside the thumbnail. Keep every stroke inside its mask.
               var visual:flash.display.DisplayObject=cell.mcIconAndMask!=null ? cell.mcIconAndMask : cell.mcImage;
               var bounds:flash.geom.Rectangle=visual!=null ? visual.getBounds(cell) : cell.getBounds(cell);
               var stroke:Number=Number(apexCatalogPrefs.border);
               var inset:Number=stroke*0.5+1;
               effect.graphics.lineStyle(stroke,uint(apexCatalogPrefs.color),1,true);
               // GFx's stroked drawRoundRect loses the right edge here.
               // Emit every edge and rounded corner, including path closure.
               var left:Number=bounds.x+inset;var top:Number=bounds.y+inset;
               var right:Number=left+Math.max(2,bounds.width-inset*2);
               var bottom:Number=top+Math.max(2,bounds.height-inset*2);
               var radius:Number=Math.min(4.5,(right-left)*0.5,(bottom-top)*0.5);
               effect.graphics.moveTo(left+radius,top);
               effect.graphics.lineTo(right-radius,top);
               effect.graphics.curveTo(right,top,right,top+radius);
               effect.graphics.lineTo(right,bottom-radius);
               effect.graphics.curveTo(right,bottom,right-radius,bottom);
               effect.graphics.lineTo(left+radius,bottom);
               effect.graphics.curveTo(left,bottom,left,bottom-radius);
               effect.graphics.lineTo(left,top+radius);
               effect.graphics.curveTo(left,top,left+radius,top);
               if(Number(apexCatalogPrefs.glow)>0) effect.filters=[new flash.filters.GlowFilter(uint(apexCatalogPrefs.color),0.9,
                  Number(apexCatalogPrefs.glow),Number(apexCatalogPrefs.glow),1.5,1)];
               cell.addChild(effect);
               if(retained==null) retained={cell:cell,effect:effect,frame:cell.mcBottomFrame,transform:null};
               else retained.effect=effect;
               if(retained.frame!=null && retained.transform==null) {
                  retained.transform=retained.frame.transform.colorTransform;
                  var rgb:uint=uint(apexCatalogPrefs.color);
                  retained.frame.transform.colorTransform=new flash.geom.ColorTransform(0,0,0,1,(rgb>>16)&255,(rgb>>8)&255,rgb&255,0);
               }
            }
            var phase:Number=(flash.utils.getTimer()%(Number(apexCatalogPrefs.period)*1000))/(Number(apexCatalogPrefs.period)*1000);
            var alpha:Number=Number(apexCatalogPrefs.strength);
            if(apexCatalogPrefs.animation=="pulse") alpha*=0.4+0.6*(0.5-0.5*Math.cos(phase*Math.PI*2));
            else if(apexCatalogPrefs.animation=="flash") alpha*=phase<0.5 ? 1 : 0.25;
            if(effect.alpha!=alpha)effect.alpha=alpha;
            if(retained==null) retained={cell:cell,effect:effect,frame:null,transform:null};
            retained.grid=grid;
            kept.push(retained);
         }
         for each(var old:Object in apexCatalogEffects) {
            var retain:Boolean=false;
            for each(var current:Object in kept) if(current.effect===old.effect) {retain=true;break;}
            if(!retain && !ApexCatalogAuthorityEffectHeld(old)) {if(old.effect.parent!=null) old.effect.parent.removeChild(old.effect);
               if(old.frame!=null) old.frame.transform.colorTransform=old.transform;}
         }
         apexCatalogEffects=kept;
         var elapsed:int=flash.utils.getTimer()-started;
         if(apexCatalogSelectionFrames<int.MAX_VALUE) apexCatalogSelectionFrames++;
         apexCatalogSelectionMaxMs=Math.max(apexCatalogSelectionMaxMs,elapsed);
         if(elapsed>1 && apexCatalogSelectionOverBudget<int.MAX_VALUE) apexCatalogSelectionOverBudget++;
      }

private function ApexCatalogClearEffects() : void
      {
         if(apexCatalogEffects==null) return;
         for each(var row:Object in apexCatalogEffects)
            { if(ApexCatalogAuthorityEffectHeld(row))continue;
              if(row.effect.parent!=null) row.effect.parent.removeChild(row.effect);
              if(row.frame!=null) row.frame.transform.colorTransform=row.transform; }
         apexCatalogEffects=[];
      }
