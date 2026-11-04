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

private function ApexCatalogGridLeaseCurrent(lease:Object) : Boolean
      {
         var s:Object=apexCatalogGrid;
         if(s==null || !s.enabled || s.disposed || lease==null || lease!==s.lease || lease.active!==true ||
            int(lease.generation)!=int(s.generation) || lease.root!==this || lease.stage!==stage || stage==null)return false;
         // Reuse one synchronous native classifier result. Its pinned field
         // getters cannot invoke callbacks; all subsequent owner checks remain.
         var panelKind:String=ApexCatalogGridProductPanel(lease.panel);
         if(panelKind=="" || lease.panel_kind!==panelKind ||
            lease.panel.stage!==stage || lease.panel.mcTileList==null ||
            lease.grid!==lease.panel.mcTileList.mGridLayout || lease.grid!==s.grid ||
            lease.feed!==lease.grid.GetDataFeed() || lease.cell_type!==lease.grid.GetCellView)return false;
         if(lease.phase=="bootstrap")return true;
         var workVisible:Boolean=ApexCatalogPanelVisible(lease.panel);
         if(!workVisible && lease.phase=="bound" && lease.panel===mCurrentPanel && s.error=="" &&
            lease.view!=null && lease.panel.mcTileList.GetGridView()===lease.view && lease.view.visible===false &&
            lease.view.stage===stage && lease.panel.mcTileList.mScrollerView!=null &&
            lease.panel.mcTileList.mScrollerView.stage===stage && lease.grid.ApexGridNeedsWork()===true) {
            // Only the captured view's OWN visibility may be a pending-work
            // mask. All actual lifecycle ancestors must remain visible/current.
            // This grants construction work, never keyboard or card input.
            var ancestor:Object=lease.view.parent;var ownsPanel:Boolean=false;var ownsList:Boolean=false;var ownsScroller:Boolean=false;
            for(var depth:int=0;ancestor!=null && depth<64;depth++) {
               if(ancestor.visible!==true)break;
               if(ancestor===lease.panel)ownsPanel=true;
               if(ancestor===lease.panel.mcTileList)ownsList=true;
               if(ancestor===lease.panel.mcTileList.mScrollerView)ownsScroller=true;
               if(ancestor===this) {workVisible=ownsPanel && ownsList && ownsScroller;break;}
               ancestor=ancestor.parent;
            }
         }
         return lease.phase=="bound" && lease.panel===mCurrentPanel && workVisible && mCurrSimInfo!=null &&
            String(mCurrSimInfo.simId)===lease.sim_id && String(mCurrSimInfo.householdId)===lease.household_id &&
            int(mCurrSimInfo.occultLayer)==lease.layer && int(mCurrSimInfo.occultType)==lease.native_kind &&
            int(mCurrSimInfo.allOccultTypes)==lease.native_mask && apexBoundSim===lease.sim_id &&
            apexFormsSelectedId===lease.owner && apexOwnerSession==lease.session &&
            apexFormsNativeGeneration===lease.native_generation && apexFormsNativeState=="bound" &&
            apexFormsDesiredId=="" && apexFormsIntent==null && apexFormsNativeIntent==null &&
            apexMoleculeIntent==null && apexPairIntent==null && !apexFormsApplying && int(mCurrState)==lease.state;
      }

private function ApexCatalogGridFrame(event:flash.events.Event=null) : void
      {
         var s:Object=apexCatalogGrid;
         if(s==null || !s.enabled || s.disposed || s.error!="" || s.running || stage==null)return;
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
            if(s.frame<int.MAX_VALUE)s.frame++;s.last=s.grid.ApexGridBegin(request);
            retained=ApexCardStateFor(s.grid);
            lease.geometry_signature=retained==null ? "" : String(retained.signature);
            s.last=s.grid.ApexGridStep(64,(stepStarted=flash.utils.getTimer())+1);
            if(apexCatalogGrid!==s || s.disposed)return;
            if(s.last!=null && s.last.error!=null)throw new Error(String(s.last.error));
         } catch(error:Error) {
            s.error="Incremental catalogue paused: "+error.message;
            ApexCatalogGridInvalidate("error-abandon");
         } finally {
            if(s.lease!=null)s.lease.frame_validated=false;
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

private function ApexCatalogGridInput(lease:Object) : Boolean
      {
         // Write-capable cell events receive a fresh bounded identity read.
         // A missed/delayed EA notification must never apply an old card to a
         // newly selected Sim, named form, category or outfit between frames.
         var s:Object=apexCatalogGrid;
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

private function ApexCatalogKeyboardPublicationReady(held:Object) : Boolean
      {
         // Preserve the exact original predicate/callback order. Labels are
         // error evidence only; no extra native/status getter or relaxed guard.
         if(held==null || apexPendingFields==null || String(apexPendingFields[0])!==held.request_id ||
            apexClaimNonce!==held.peer_nonce || apexNonce!==held.peer_nonce || apexDisconnected || !apexSocketActive ||
            stage!==held.stage || apexNativeChannel!==held.channel || mCurrSimInfo==null)
            throw new Error("Navigation publication changed its original request, target or catalog [guard=transport]");
         if(String(mCurrSimInfo.simId)!==held.before.sim_id || String(mCurrSimInfo.householdId)!==held.before.household_id ||
            apexBoundSim!==held.before.sim_id || apexFormsSelectedId!==held.before.owner_id ||
            apexFormsNativeGeneration!==held.before.native_generation || apexOwnerSession!=int(held.before.session) ||
            int(mCurrState)!=int(held.before.menu_state) || int(mCurrSimInfo.occultLayer)!=int(held.before.layer))
            throw new Error("Navigation publication changed its original request, target or catalog [guard=owner]");
         if(int(mCurrSimInfo.occultType)!=int(held.before.native_kind) || int(mCurrSimInfo.allOccultTypes)!=int(held.before.native_mask))
            throw new Error("Navigation publication changed its original request, target or catalog [guard=cached-renderer]");
         if(apexFormsNativeState!=="bound" || apexFormsDesiredId!="" || apexFormsIntent!=null ||
            apexFormsNativeIntent!=null || apexMoleculeIntent!=null || apexPairIntent!=null || apexFormsApplying)
            throw new Error("Navigation publication changed its original request, target or catalog [guard=form-intent]");
         if(mCurrentPanel!==held.panel || held.panel.stage!==stage || held.panel.visible!==true ||
            held.panel.mcTileList!==held.list || held.list.mGridLayout!==held.grid || held.grid.GetDataFeed()!==held.feed)
            throw new Error("Navigation publication changed its original request, target or catalog [guard=display-feed]");
         if(apexKeyReceipt!==held.receipt || ApexEncode(apexKeyReceipt)!==held.receipt_json)
            throw new Error("Navigation publication changed its original request, target or catalog [guard=receipt]");
         if(apexKeyIndex!=int(held.target) || apexKeyItem!==held.item)
            throw new Error("Navigation publication changed its original request, target or catalog [guard=logical-target]");
         if(apexKeyIntent!=0 || apexKeyQueue!=null && apexKeyQueue.length!=0 || ApexCatalogGridOwns(held.grid)!==held.owned)
            throw new Error("Navigation publication changed its original request, target or catalog [guard=input-ownership]");
         var grid:Object=held.grid;var list:Object=held.list;
         if(held.owned) {
            if(apexCatalogGrid.lease!==held.lease || !ApexCatalogGridLeaseCurrent(held.lease) ||
               int(held.lease.generation)!=int(held.lease_generation) ||
               int(grid.ApexGridStatus().revision)!=int(held.revision))
               throw new Error("Navigation publication changed its original native lease or feed revision");
            // A scroll may advance native JOB generation; it must finish its
            // own double-buffer publication before its mapping can be used.
            if(ApexCatalogGridPending(grid))return false;
         }
         if(list.visible!==true || list.GetGridView().visible!==true)return false;
         if((held.owned ? grid.GetDataAtIndex(int(held.target)) : held.feed.RequestItemAt(int(held.target)))!==held.item)
            throw new Error("Navigation publication replaced its original target item");
         var cell:flash.display.DisplayObject=grid.GetViewAtIndex(int(held.target)) as flash.display.DisplayObject;
         if(cell==null || cell.stage!==stage || cell.visible!==true || cell.parent!==list.GetGridView() ||
            int(grid.GetGridIndexOfCell(cell))!=int(held.target) || apexKeyFocus==null ||
            apexKeyFocus.parent!==list.GetGridView() || apexKeyFocus.stage!==stage || apexKeyFocus.visible!==true)return false;
         var visibility:Object=ApexCatalogKeyboardVisibility();
         return visibility.available===true && visibility.fully_visible===true && visibility.focus_visible===true &&
            grid.GetDataFeed()===held.feed &&
            (held.owned ? grid.GetDataAtIndex(int(held.target)) : held.feed.RequestItemAt(int(held.target)))===held.item &&
            (!held.owned || apexCatalogGrid.lease===held.lease && ApexCatalogGridLeaseCurrent(held.lease) &&
             int(grid.ApexGridStatus().revision)==int(held.revision) && !ApexCatalogGridPending(grid));
      }

private function ApexReadback() : void
      {
         if(apexPendingFields==null || int(apexTimer.currentCount)<apexReadbackTick) return;
         var fields:Array=apexPendingFields;
         var reply:Object=apexPendingReply;
         var context:Object=apexPendingContext;
         var operation:String=fields[2]; var state:int=int(fields[3]);
         var category:int=int(fields[4]); var index:int=int(fields[5]); var value:String=fields[6];
         // Palette completion needs the child ID too, before its next-tick
         // lookup. The original wire retains the parent/child pair unchanged.
         if(operation=="select" && context.selection_variant_id is String) value=String(context.selection_variant_id);
         if((operation=="undo" || operation=="redo") && context.history_before is String)
            reply.history_before_json=String(context.history_before);
         var selectedSimMatches:Boolean=false; var writeStarted:Boolean=false;
         var keyboardNavigation:Boolean=operation=="catalog-key" || operation=="catalog-input" && String(value.split(",")[0])!="enter";
         var keyboardPublication:Object=keyboardNavigation ? context.keyboard_publication : null;
         var keyboardObserved:Object=null;
         try {
            if(keyboardNavigation && keyboardPublication==null)
               throw new Error("message" in reply ? String(reply.message) : "Navigation input lacks its retained consumed publication intent");
            if(operation=="physique" && context.physique_commit_pending===true) {
               if("message" in reply) throw new Error("Native physique preview is unresolved; no completion replay");
               var physiqueRead:Object=ApexFormsObservedSim();
               selectedSimMatches=physiqueRead && String(physiqueRead.simId)==String(fields[1]);
               var physiqueCurrentKind:* = CommunicationManager.CallGameService("GetSimOccult");
               if(!selectedSimMatches || int(physiqueRead.occultLayer)!=int(context.physique_layer) ||
                  !(physiqueCurrentKind is int) || int(physiqueCurrentKind)!=int(context.physique_kind) ||
                  String(context.physique_owner_id)!="" && apexFormsSelectedId!=String(context.physique_owner_id))
                  throw new Error("Native physique preview changed owner; no completion replay");
               physiqueRead=null;
               var physiqueCommit:Object={type:state,value:Number(value),slider_mouse_up:true,
                  slider_start_value:Number(context.physique_start_value)};
               // Complete the gesture before any full native snapshot/cache
               // synchronization. Verify its actual value on the next tick.
               reply.physique_preview_readback="deferred-until-native-completion";
               context.physique_commit_pending=false;apexPendingPhase=1;
               apexReadbackTick=int(apexTimer.currentCount)+1;apexAwaiting="readback|"+apexTimer.currentCount;
               writeStarted=true;
               CommunicationManager.CallGameService("SetSimPhysiqueValue",physiqueCommit);
               return;
            }
            // APEX_TIMER_TRACE_BEGIN readback-native-begin
            if(apexCatalogTrace!=null && apexCatalogTrace.enabled===true && apexCatalogTrace.timer_profile!=null) ApexCatalogTimerStep("native-info.enter");
            // APEX_TIMER_TRACE_END readback-native-begin
            var native:Object=CommunicationManager.CallGameService("CASGetSimInfo",null,true);
            // APEX_TIMER_TRACE_BEGIN readback-native-end
            if(apexCatalogTrace!=null && apexCatalogTrace.enabled===true && apexCatalogTrace.timer_profile!=null) ApexCatalogTimerStep("native-info.leave");
            // APEX_TIMER_TRACE_END readback-native-end
            selectedSimMatches=native && String(native.simId)==(operation=="member-select" ? String(context.target_sim_id) : String(fields[1]));
            // CASGetSimInfo reports the Sim's family metadata. GetSimOccult
            // reads the current native model's genus, including its alt view.
            var renderedKind:* = operation=="form-owner-select" ? CommunicationManager.CallGameService("GetSimOccult") : null;
            // A same-owner native bind need not send a changed-owner heartbeat.
            // Reconcile our pending desired ID from the current bound native
            // model on this readback; do not await an unrelated socket poll.
            if(operation=="form-owner-select" && ApexFormsReadNativeState() &&
               apexFormsSelectedId===String(context.owner_id) && apexFormsDesiredId=="") {
               ApexFormsBindUiKind();ApexFormsRefreshBoundPair();
            }
            if(selectedSimMatches && operation=="form-owner-select" && !("message" in reply) &&
                (!(renderedKind is int) || int(renderedKind)!=state || (int(native.allOccultTypes) | 1)!=category ||
                 apexFormsSelectedId!=String(context.owner_id) || apexFormsNativeState!="bound" || apexFormsDesiredId!="" ||
                 !ApexPresentationReady())) {
               if(int(apexTimer.currentCount)<int(context.owner_deadline_tick)) {
                  // The normal idle poll is suspended while a command owns
                  // its readback. Poll only metadata here: Source's outstanding
                  // request excludes another command until this one is ACKed.
                  // Keep the same nonce/claim and the one-frame transport lease.
                  if(!apexOutboundPending) {
                     apexAwaiting="poll|"+apexTimer.currentCount;
                     ApexSocketSend("POLL|"+apexNonce);
                  }
                  apexReadbackTick=int(apexTimer.currentCount)+1;return;
               }
               throw new Error("Native independent form view did not settle before its bounded readback deadline");
            }
            var catalogAfter:Object=(ApexCatalogReadbackOnly(operation) || operation=="panel-navigation" || keyboardPublication!=null) ? ApexOwnerSimRow(native) : null;
            native=null;
            if(!selectedSimMatches) throw new Error("CAS selected Sim changed before native readback");
            if(keyboardPublication!=null && !("message" in reply)) {
               keyboardObserved=ApexCatalogReadbackContext(catalogAfter);
               if(!ApexCatalogKeyboardScopeEqual(keyboardPublication.before,keyboardObserved))
                  throw new Error("Navigation publication changed its original native Sim/form/outfit scope");
            }
            if(!("message" in reply) && apexPendingPhase==2) {
               // Item selection settles before querying that hairstyle's swatches.
               var freshHairSwatches:Array=ApexClone(CommunicationManager.CallGameService("CasGetSwatchColorList",int(context.palette_type))) as Array;
               if(!freshHairSwatches) throw new Error("Native hair swatches are unavailable after item selection");
               var exactHairSwatch:Object=null; var hairMatches:int=0;
               for each(var hairSwatch:Object in freshHairSwatches)
                  if(hairSwatch && String(hairSwatch.dataID)==value) { exactHairSwatch=hairSwatch; hairMatches++; }
               if(hairMatches!=1 || !("color" in exactHairSwatch))
                  throw new Error("Requested hair swatch is unavailable/ambiguous after native item selection");
               var hairValue:Number=("value_range_modifier" in exactHairSwatch ? Number(exactHairSwatch.value_range_modifier) : 0);
               if(!isFinite(hairValue)) throw new Error("Native hair swatch modifier is not finite");
               var hairPayload:Object={dataId:String(exactHairSwatch.dataID),swatchType:int(context.palette_type),
                  colorId:exactHairSwatch.color,furColors:null,value_range_modifier:hairValue};
               exactHairSwatch=null; hairSwatch=null;
               // Advance before calling native code: even a nested callback
               // cannot see this sub-mutation as eligible to execute again.
               apexPendingPhase=1; apexReadbackTick=int(apexTimer.currentCount)+1;
               apexAwaiting="readback|"+apexTimer.currentCount;
               writeStarted=true;
               if(int(context.palette_type)==3) reply.eyebrow_widget=ApexSelectEyebrowSwatch(value,freshHairSwatches);
               else CommunicationManager.CallGameService("CasSetSwatchColorSelected",hairPayload);
               freshHairSwatches=null;
               return;
            }
            if(!("message" in reply) && apexPendingPhase==3) {
               var added:Object=CommunicationManager.CallGameService("CasGetPlannedOutfits",category);
               if(!added || !(added.outfit_list is Array) || added.outfit_list.length!=int(context.before_count)+1)
                  throw new Error("Native CAS did not read back exactly one appended outfit");
               context.after_count=added.outfit_list.length;
               added=null;
               apexPendingPhase=1; apexReadbackTick=int(apexTimer.currentCount)+1;
               apexAwaiting="readback|"+apexTimer.currentCount;
               writeStarted=true;
               CommunicationManager.CallGameService("CasSelectPlannedOutfit",{outfit_type:category,outfit_index:int(context.index)});
               CommunicationManager.SendUIMessage("CASRefreshActiveCatalog");
               return;
            }
            var eyebrowProbe:Boolean=(operation=="select" && state==MenuState.PROFILE_HAIR_EYEBROWS) || (operation=="swatch" && state==3);
            if(eyebrowProbe)
               reply.eyebrow_palette_before_snapshot=ApexClone(CommunicationManager.CallGameService("CasGetSwatchColorSelected",3));
            if(keyboardPublication!=null && (apexKeyIntent!=0 || apexKeyQueue!=null && apexKeyQueue.length!=0))
               throw new Error("Navigation publication received another keyboard intent before readback");
            if(operation=="catalog-key" || operation=="catalog-input") ApexCatalogKeyboardFrame(true);
            if(keyboardPublication!=null && !("message" in reply) && !ApexCatalogKeyboardPublicationReady(keyboardPublication)) {
               var keyboardElapsed:int=flash.utils.getTimer()-int(keyboardPublication.started);
               if(keyboardElapsed<0)throw new Error("Navigation publication clock changed");
               if(keyboardElapsed<10000) {
                  // Yield to the existing native scroll/publication job. The
                  // key and slider gesture have ALREADY been consumed once.
                  apexReadbackTick=int(apexTimer.currentCount)+1;return;
               }
            }
            // APEX_TIMER_TRACE_BEGIN snapshot-begin
            if(apexCatalogTrace!=null && apexCatalogTrace.enabled===true && apexCatalogTrace.timer_profile!=null) ApexCatalogTimerStep("snapshot.enter");
            // APEX_TIMER_TRACE_END snapshot-begin
            if(operation=="panel-navigation") reply.client=ApexPanelNavigationSnapshot(context.navigation_before,ApexCatalogReadbackContext(catalogAfter),state);
            else if(ApexCatalogReadbackOnly(operation)) reply.client=ApexCatalogSnapshot(context.catalog_before,ApexCatalogReadbackContext(catalogAfter));
            else {
               reply.client=ApexSnapshot();
               if(this.mCurrState==MenuState.CLOTHING_BODY_WINGS)
                  reply.client.wing_observation=ApexWingObservation();
            }
            // APEX_TIMER_TRACE_BEGIN snapshot-end
            if(apexCatalogTrace!=null && apexCatalogTrace.enabled===true && apexCatalogTrace.timer_profile!=null) ApexCatalogTimerStep("snapshot.leave");
            // APEX_TIMER_TRACE_END snapshot-end
            catalogAfter=null;
            if(eyebrowProbe)
               reply.eyebrow_palette_after_snapshot=ApexClone(CommunicationManager.CallGameService("CasGetSwatchColorSelected",3));
            if(!("message" in reply)) {
               if(operation=="catalog" || operation=="variants" || operation=="preset" || operation=="select-layer" ||
                  operation=="remove" || operation=="layers" || operation=="layer-add" || operation=="layer-remove" ||
                  operation=="layer-move" || operation=="swatches" || operation=="swatch" || operation=="physique" ||
                  operation=="body-types" || operation=="body-type" || operation=="modifiers" ||
                  operation=="color-sliders" || operation=="hair-matching" || operation=="hair-match" || operation=="workspace" || operation=="form-menu" || operation=="pair-link" || operation=="pair-copy" || operation=="catalog-state" || operation=="catalog-style" || operation=="catalog-open" || operation=="catalog-view" || operation=="catalog-slider" || operation=="catalog-width-drag" || operation=="catalog-cards" || operation=="catalog-card-reset" || operation=="catalog-key" || operation=="catalog-input" || operation=="catalog-search" || operation=="catalog-companion" || operation=="panel-layout" || operation=="catalog-trace" || operation=="catalog-layout-trace" ||
                  operation=="voices" || operation=="voice-actor" || operation=="voice-pitch" ||
                  operation=="walkstyles" || operation=="walkstyle" || operation=="occults" || operation=="occult-view" || operation=="occult-cache-view" || operation=="occult-owner-view" || operation=="form-owner-select" || operation=="detail-status" ||
                  operation=="detail-mode" || operation=="filters" || operation=="filter-clear")
                  reply.client.control=ApexControlResult(operation,state,category,index,value,context,reply.client);
               if(keyboardPublication!=null) {
                  var keyboardReady:Boolean=ApexCatalogKeyboardPublicationReady(keyboardPublication);
                  var keyboardAfter:Object=ApexCatalogReadbackContext(ApexOwnerSimRow(reply.client.sim));
                  keyboardObserved=keyboardAfter;
                  if(!ApexCatalogKeyboardScopeEqual(keyboardPublication.before,keyboardAfter))
                     throw new Error("Navigation publication changed scope during its complete snapshot");
                  if(!keyboardReady) {
                     keyboardElapsed=flash.utils.getTimer()-int(keyboardPublication.started);
                     if(keyboardElapsed<0)throw new Error("Navigation publication clock changed");
                     if(keyboardElapsed<10000) {
                        reply.client=null;apexReadbackTick=int(apexTimer.currentCount)+1;return;
                     }
                     reply.navigation_publication={protocol:1,request_id:String(fields[0]),peer_nonce:apexClaimNonce,
                        before:ApexClone(keyboardPublication.before),after:keyboardAfter,key:int(keyboardPublication.receipt.key),
                        target_index:int(keyboardPublication.target),elapsed_ms:keyboardElapsed,published:false,appearance_written:false};
                     throw new Error("Native catalog navigation did not publish its focused card before the bounded deadline");
                  }
               }
               if(operation=="accept") {
                  if(!(reply.client.sim.occultLayer is int) || int(reply.client.sim.occultLayer)!=0)
                     throw new Error("Alternate or untyped CAS layers lack a verified original owner mapping; no intent prepared");
                  var casContext:Object=reply.client.native_context;
                  if(!casContext || !casContext.edit_mode || casContext.edit_mode.query!="returned-value" ||
                     !(casContext.edit_mode.value is int) || (int(casContext.edit_mode.value)!=0 && int(casContext.edit_mode.value)!=7) ||
                     !casContext.new_family || casContext.new_family.query!="returned-value" || casContext.new_family.value!==false ||
                     !casContext.entered_from_play_area || casContext.entered_from_play_area.query!="returned-value" ||
                     !casContext.entered_from_play_area.value || casContext.entered_from_play_area.value.result!==true)
                     throw new Error("CAS accept requires existing-household mode0 or single-Sim mode7, an existing family and entry from Live mode");
                  if(!(reply.client.sim.householdId is String) || !/^[1-9][0-9]{0,19}$/.test(reply.client.sim.householdId))
                     throw new Error("Native CAS accept lacks an exact household identity; no intent prepared");
                  if(String(reply.client.sim.householdId)!=value)
                     throw new Error("Native CAS accept household differs from its bound original request; no intent prepared");
                  context.household_id=value;
               }
               if(operation=="member-select") {
                  var memberOriginal:Object=context.member_before;
                  var memberAfter:Object=ApexMemberSelectionContext(String(context.target_sim_id),String(context.target_sim_id),
                     String(memberOriginal.household_id),int(reply.client.sim.occultLayer),index);
                  if(memberAfter.native_session!=memberOriginal.native_session || memberAfter.household_id!=memberOriginal.household_id ||
                     memberAfter.target_index!=memberOriginal.target_index || memberAfter.target_form_flags!=memberOriginal.target_form_flags ||
                     memberAfter.roster_json!=memberOriginal.roster_json || String(reply.client.sim.simId)!=String(context.target_sim_id))
                     throw new Error("Member selection changed household identity, roster or destination form");
                  reply.member_selection={native_session:index,household_id:String(memberAfter.household_id),
                     source_sim_id:String(fields[1]),target_sim_id:String(memberAfter.target_sim_id),
                     source_index:int(memberOriginal.source_index),target_index:int(memberAfter.target_index),
                     target_form_flags:int(memberAfter.target_form_flags),selection_verified:true,
                     appearance_persistence_verified:false};
               }
               if(operation=="form-select" || operation=="layer-select") {
                  var beforeSelection:Object=context.selection_before;
                  if(beforeSelection==null) throw new Error("CAS form selection has no retained original intent");
                  var afterSelection:Object=ApexFormSelectionContext(String(fields[1]),value,
                     int(beforeSelection.target_layer),state,index,operation=="layer-select" ? state : -1);
                  if(afterSelection.native_session!=beforeSelection.native_session || afterSelection.sim_id!=beforeSelection.sim_id ||
                     afterSelection.household_id!=beforeSelection.household_id || afterSelection.selected_index!=beforeSelection.selected_index ||
                     afterSelection.form_flags!=beforeSelection.form_flags || afterSelection.target_layer!=beforeSelection.target_layer ||
                     afterSelection.pair_json!=beforeSelection.pair_json || afterSelection.feed_sequence<beforeSelection.feed_sequence)
                     throw new Error("CAS form selection pair/session changed before next-tick readback");
                  reply.form_selection={native_session:int(afterSelection.native_session),sim_id:String(afterSelection.sim_id),
                     household_id:String(afterSelection.household_id),selected_index:int(afterSelection.selected_index),
                     expected_layer:category,target_layer:int(afterSelection.target_layer),form_flags:int(afterSelection.form_flags),
                     selection_changed:category!=int(afterSelection.target_layer),selection_verified:true,
                     mapping_verified:false,alternate_accept_authorized:false};
               }
               if(operation=="panel" || operation=="panel-navigation" || operation=="select") {
                  if(reply.client.menu_state!=state || reply.client.panel_visible!==true)
                     throw new Error("Native CAS panel did not become visible");
               }
               if(operation=="outfit" || operation=="outfit-add") {
                  var expectedIndex:int=operation=="outfit-add" ? int(context.index) : index;
                  var slot:Object=reply.client.outfit;
                  if(!slot || int(slot.outfit_type)!=category || int(slot.outfit_index)!=expectedIndex)
                     throw new Error("Native CAS outfit selection did not match");
                  if(operation=="outfit-add") reply.client.outfit_created={before_count:int(context.before_count),after_count:int(context.after_count)};
               }
               if(operation=="select") {
                  if(context.selection_variant_id is String) value=String(context.selection_variant_id);
                  if(context.selection_base_id is String) {
                     if(state!=MenuState.CLOTHING_BODY_WINGS)
                        throw new Error("Compound wing readback requires the exact wing panel");
                     // Native CatalogDataFeed reads selected BASES separately
                     // from its color variation. Do not compare a base to a
                     // requested color or infer one from the other.
                     var wingObserved:Object=reply.client.wing_observation;
                     var wingBases:Array=wingObserved!=null ? wingObserved.selected_base_ids as Array : null;
                     var wingColor:* = wingObserved!=null ? wingObserved.selected_color_id : null;
                     if(wingBases==null || wingBases.length!=1 || !(wingBases[0] is String) ||
                        String(wingBases[0])!=String(context.selection_base_id) || !(wingColor is String) || wingColor!==value)
                        throw new Error("Native wing base and color did not both read back exactly");
                     reply.client.wing_selection={base_query:"returned-value",color_query:"returned-value",
                        selected_base_ids:wingBases,selected_color_id:wingColor,body_type:CASBodyType.WINGS};
                     wingBases=null; wingColor=null;
                  } else {
                     var selected:Array=reply.client.selected as Array;
                     var matched:Boolean=false;
                     if(selected) for each(var selectedItem:Object in selected)
                        if(String(selectedItem.dataID)==value) matched=true;
                     if(!matched) throw new Error("Native CAS did not read back the requested catalog item");
                     if(context.catalog_selection!=null)
                        reply.client.catalog_selection=ApexClone(context.catalog_selection);
                  }
               }
               if(operation=="hair-swatch" || (operation=="select" && state==MenuState.CLOTHING_HAIR))
                  if(String(reply.client.hair_selected_swatch_id)!=value)
                     throw new Error("Native CAS did not read back the exact requested hair swatch");
               if(operation=="undo" || operation=="redo")
                  if(context.history_before==ApexEncode(reply.client))
                     throw new Error("Native history operation produced no observable client change");
               reply.ok=true;
            }
         } catch(error:Error) {
            reply.ok=false; reply.message=error.message;
            if(keyboardNavigation && !("navigation_publication" in reply))
               reply.navigation_publication={protocol:1,request_id:String(fields[0]),peer_nonce:apexClaimNonce,
                  before:context.keyboard_before!=null ? ApexClone(context.keyboard_before) : null,
                  after:keyboardObserved!=null ? ApexClone(keyboardObserved) : null,
                  key:keyboardPublication!=null ? int(keyboardPublication.receipt.key) : -1,
                  target_index:keyboardPublication!=null ? int(keyboardPublication.target) : -1,
                  elapsed_ms:keyboardPublication!=null ? flash.utils.getTimer()-int(keyboardPublication.started) : 0,
                  published:false,appearance_written:false};
            if(keyboardNavigation && reply.mutation_started!==true &&
               (reply.client==null || String(error.message)!="Native catalog navigation did not publish its focused card before the bounded deadline")) {
               reply.message=String(reply.message).substr(0,512);
               try {reply.navigation_diagnostic=ApexCatalogKeyboardFailureDiagnostic(error,keyboardPublication);}
               catch(diagnosticError:Error) {reply.navigation_diagnostic={protocol:1,diagnostic_only:true,error:String(diagnosticError.message).substr(0,512)};}
            }
            if(operation=="accept") {
               reply.lifecycle_stage="accept-result"; reply.commit_attempted=false;
               reply.commit_submitted=false; reply.ui_transition_verified=false;
            }
            if(writeStarted) {
               apexPendingPhase=1; apexReadbackTick=int(apexTimer.currentCount)+1;
               apexAwaiting="readback|"+apexTimer.currentCount;
               return;
            }
            if(operation!="panel-navigation" && reply.mutation_started && selectedSimMatches && reply.client==null &&
               !(operation=="physique" && context.physique_commit_pending===true)) {
               // APEX_TIMER_TRACE_BEGIN fallback-snapshot-begin
               if(apexCatalogTrace!=null && apexCatalogTrace.enabled===true && apexCatalogTrace.timer_profile!=null) ApexCatalogTimerStep("snapshot.enter");
               // APEX_TIMER_TRACE_END fallback-snapshot-begin
               try { reply.client=ApexSnapshot(); }
               catch(snapshotError:Error) { reply.client_snapshot_error=snapshotError.message; }
               // APEX_TIMER_TRACE_BEGIN fallback-snapshot-end
               if(apexCatalogTrace!=null && apexCatalogTrace.enabled===true && apexCatalogTrace.timer_profile!=null) ApexCatalogTimerStep("snapshot.leave");
               // APEX_TIMER_TRACE_END fallback-snapshot-end
            }
         }
         var unresolvedPhysique:Boolean=operation=="physique" && context.physique_commit_pending===true;
         ApexComplete();
         if(unresolvedPhysique) apexPendingPhase=8; // No later getter or mutation after a partial gesture.
      }

private function ApexCatalogKeyboardFailureDiagnostic(error:Error,held:Object) : Object
      {
         // Diagnostic only: emitted once inside the original FAILED non-Enter
         // ACK. Never authority to finish/replay it or admit another command.
         var s:Object=apexCatalogGrid;
         var out:Object={protocol:1,diagnostic_only:true,appearance_written:false,
            error:{message:String(error.message).substr(0,512),id:int(error.errorID),stack:null},
            keyboard:{message:String(apexKeyMessage).substr(0,512),rejected:String(apexKeyRejected).substr(0,256),
               index:int(apexKeyIndex),intent:int(apexKeyIntent),queued:apexKeyQueue==null ? 0 : int(apexKeyQueue.length),
               receipt:null,target:held==null ? -1 : int(held.target),receipt_same:held!=null && apexKeyReceipt===held.receipt,
               item_same:held!=null && apexKeyItem===held.item},
            main:{error:s==null ? "" : String(s.error).substr(0,512),waiting:s==null ? "" : String(s.waiting).substr(0,256),
               running:s!=null && s.running===true,retiring:s!=null && s.retiring!=null,
               generation:s==null ? 0 : int(s.generation),lease_generation:s==null || s.lease==null ? 0 : int(s.lease.generation),
               lease_active:s!=null && s.lease!=null && s.lease.active===true,
               held_lease_same:held!=null && s!=null && s.lease===held.lease,
               cached_kind:mCurrSimInfo==null ? -1 : int(mCurrSimInfo.occultType),
               held_native_kind:held==null ? -1 : int(held.before.native_kind),
               held_shell_kind:held==null ? -1 : int(held.before.shell_kind),
               current_panel_same:held!=null && mCurrentPanel===held.panel,
               current_grid_same:held!=null && s!=null && s.grid===held.grid,
               panel_visible:mCurrentPanel!=null && mCurrentPanel.visible===true,
               list_visible:held!=null && held.list!=null && held.list.visible===true,
               view_visible:s!=null && s.lease!=null && s.lease.view!=null ? s.lease.view.visible===true : null},
            grid:null,status_error:""};
         try {out.error.stack=error.getStackTrace();if(out.error.stack!=null)out.error.stack=String(out.error.stack).substr(0,2048);}
         catch(stackError:Error) {out.error.stack=null;}
         try {
            var receipt:Object=apexKeyReceipt;
            if(receipt!=null)out.keyboard.receipt={key:int(receipt.key),sim_id:String(receipt.sim_id).substr(0,32),
               owner_id:String(receipt.owner_id).substr(0,128),menu_state:int(receipt.menu_state),menu_state_before:int(receipt.menu_state_before),
               source_route:String(receipt.source_route).substr(0,64),index_before:int(receipt.index_before),index_after:int(receipt.index_after),
               count:int(receipt.count),columns:int(receipt.columns),page_step:int(receipt.page_step),click_dispatched:receipt.click_dispatched===true};
            receipt=null;
         }
         catch(receiptError:Error) {out.keyboard.receipt=null;}
         try {
            // Read the authenticated owned primitive status once, then copy a
            // FIXED schema. Never encode its URI lists, opaque objects or rows.
            var native:Object=s==null || s.grid==null ? null : s.grid.ApexGridStatus();
            if(native!=null) {
               out.grid={error:typeof native.error=="string" ? String(native.error).substr(0,512) : "",
                  reason:typeof native.reason=="string" ? String(native.reason).substr(0,512) : "",
                  phase:typeof native.phase=="string" ? String(native.phase).substr(0,64) : "",
                  row_delta_last_refusal:typeof native.row_delta_last_refusal=="string" ? String(native.row_delta_last_refusal).substr(0,512) : "",
                  row_delta_last_error:typeof native.row_delta_last_error=="string" ? String(native.row_delta_last_error).substr(0,512) : "",
                  row_delta_phase:typeof native.row_delta_phase=="string" ? String(native.row_delta_phase).substr(0,64) : "",
                  row_delta_refusal:null,
                  counts:{},maxMS:{}};
               var names:Array=["generation","revision","publishes","operations","index","target","cells","dirty","cancelled","lease",
                  "row_delta_active","natural_width","natural_height","measured_height","measured_scale","measured_aspect",
                  "intrinsic_geometry_captures","intrinsic_geometry_reuses","intrinsic_geometry_resets","intrinsic_geometry_foreign"];
               var name:String;var scalar:*;
               for each(name in names) {
                  scalar=native[name];out.grid[name]=typeof scalar=="number" && isFinite(Number(scalar)) ? Number(scalar) :
                     (scalar is Boolean ? Boolean(scalar) : null);
               }
               names=["construct","attach","retire","position","bind","selection","data","draw","selected_setter","publish"];
               for each(name in names) {
                  scalar=native.counts==null ? null : native.counts[name];
                  out.grid.counts[name]=typeof scalar=="number" && isFinite(Number(scalar)) ? Number(scalar) : null;
                  scalar=native.maxMS==null ? null : native.maxMS[name];
                  out.grid.maxMS[name]=typeof scalar=="number" && isFinite(Number(scalar)) ? Number(scalar) : null;
               }
               var refusal:Object=native.row_delta_refusal;
               if(refusal!=null)out.grid.row_delta_refusal={reason:typeof refusal.reason=="string" ? String(refusal.reason).substr(0,512) : "",
                  phase:typeof refusal.phase=="string" ? String(refusal.phase).substr(0,64) : "",index:int(refusal.index),generation:int(refusal.generation),
                  expected:typeof refusal.expected=="number" && isFinite(Number(refusal.expected)) ? Number(refusal.expected) : null,
                  actual:typeof refusal.actual=="number" && isFinite(Number(refusal.actual)) ? Number(refusal.actual) : null};
               refusal=null;
            }
            native=null;
         } catch(statusError:Error) {out.grid=null;out.status_error=String(statusError.message).substr(0,512);}
         return out;
      }
