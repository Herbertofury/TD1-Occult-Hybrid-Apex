// Exact owned pre-queue witness continuation; no original/native callable edits.
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
            if(keyboardNavigation && keyboardPublication==null) {
               if(ApexCatalogUnconsumedReply(fields,context,reply)) {ApexComplete();return;}
               throw new Error("message" in reply ? String(reply.message) : "Navigation input lacks its retained consumed publication intent");
            }
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

private function ApexCatalogKeyDown(event:flash.events.KeyboardEvent) : void
      {
         apexKeyReceived=Math.min(2147483647,apexKeyReceived+1);apexKeyLastCode=int(event.keyCode);
         if(event.ctrlKey || event.altKey || event.shiftKey) {apexKeyRejected="modifier held";return;}
         if(stage==null || apexDisconnected) {apexKeyRejected="stage disconnected";return;}
         if(!apexKeyInjecting && (apexPendingFields!=null || apexReceiving)) {apexKeyRejected="command busy";return;}
         if(ApexCatalogKeyboardTyping()) {apexKeyRejected="text input owns focus";return;}
         if([13,33,34,35,36,37,38,39,40].indexOf(int(event.keyCode))<0) {apexKeyRejected="unsupported key code";return;}
         apexKeyRejected="";
         var panel:Object=mCurrentPanel;
         if(panel==null || !panel.visible || panel.mcTileList==null || !panel.mcTileList.visible) {apexKeyRejected="no visible catalog";return;}
         if(Boolean(CommunicationManager.CallUIService("IsUILoadingScreenVisible")) ||
            Boolean(CommunicationManager.CallUIService("IsModalVisible")) || Boolean(CommunicationManager.CallUIService("IsDialogModalVisible"))) {apexKeyQueue=[];apexKeyIntent=0;return;}
         var grid:Object=panel.mcTileList.mGridLayout;
         if(grid==null) {apexKeyRejected="no native catalog grid";return;}
         var owned:Boolean=ApexCatalogGridOwns(grid);
         var lease:Object=owned ? apexCatalogGrid.lease : null;
         var snapshot:Object=null;
         if(owned) {
            if(ApexCatalogGridPending(grid) || lease==null || lease.phase!="bound" || lease.active!==true ||
               panel.mcTileList.GetGridView().visible!==true) {
               apexKeyRejected="catalog is still loading";apexKeyMessage="Wait for the catalog before using a key.";
               apexKeyQueue=[];apexKeyIntent=0;
               ApexCatalogUnconsumedMark(int(event.keyCode),panel,grid,lease,"shared-keyboard-handler-before-queue");
               if(apexKeyFocus!=null)apexKeyFocus.visible=false;
               event.preventDefault();event.stopImmediatePropagation();return;
            }
            snapshot=grid.ApexGridStatus();
         }
         // Capture cheap native identity primitives only. Fresh engine reads,
         // selection and scrolling belong to the owned consuming phase.
         if(apexKeyQueue==null) apexKeyQueue=[];
         if(apexKeyQueue.length>=64) {apexKeyMessage="Keyboard input is busy; wait for the catalog.";event.preventDefault();event.stopImmediatePropagation();return;}
         apexKeyQueue.push({key:int(event.keyCode),sim:apexBoundSim,owner:apexFormsSelectedId,
            panel:panel,state:mCurrState,feed:grid.GetDataFeed(),grid:grid,lease:lease,
            lease_generation:owned ? int(lease.generation) : 0,native_generation:owned ? String(lease.native_generation) : "",
            grid_generation:owned ? int(snapshot.generation) : 0,grid_revision:owned ? int(snapshot.revision) : 0,
            focused_index:apexKeyIndex,focused_item:apexKeyItem,
            route:apexKeyInjecting ? "shared-keyboard-handler" : "stage-keyboard-event"});
         apexKeyIntent=int(apexKeyQueue[0].key);event.preventDefault();event.stopImmediatePropagation();
      }

private function ApexCatalogKeyboardFrame(controlled:Boolean=false) : void
      {
         try {
         if(apexKeyStage==null) ApexCatalogKeyboardInitialize();
         if(apexKeyIntent==0 && apexKeyIndex<0) return;
         if(stage==null || (!controlled && (apexPendingFields!=null || apexReceiving)) || apexDisconnected) return;
         var panel:Object=mCurrentPanel;
         var list:Object=panel==null ? null : panel.mcTileList;
         var grid:Object=list==null ? null : list.mGridLayout;
         if(panel==null || !panel.visible || list==null || !list.visible || grid==null || mCurrSimInfo==null) {
            apexKeyIntent=0;apexKeyQueue=[];apexKeyIndex=-1;if(apexKeyFocus!=null) apexKeyFocus.visible=false;return;
         }
         var feed:Object=grid.GetDataFeed();
         var owned:Boolean=ApexCatalogGridOwns(grid);
         var lease:Object=owned ? apexCatalogGrid.lease : null;
         var context:String=String(mCurrSimInfo.simId)+"|"+apexFormsSelectedId+"|"+mCurrState+"|"+apexEquippedActive;
         if(owned && lease!=null)context+="|"+lease.native_generation+"|"+lease.generation;
         if(feed!==apexKeyFeed || context!=apexKeyContext) {
            apexKeyFeed=feed;apexKeyContext=context;apexKeyIndex=-1;apexKeyItem=null;apexKeyBounds="";
            if(apexKeyFocus!=null) apexKeyFocus.visible=false;
         }
         if(owned && (ApexCatalogGridPending(grid) || list.GetGridView().visible!==true)) {
            // Retain a logical target while its ordinary scroll job binds.
            // Queued actions are never replayed after that job or a rebind.
            apexKeyQueue=[];apexKeyIntent=0;apexKeyRejected="catalog is still loading";
            apexKeyMessage="Wait for the catalog before using a key.";
            if(apexKeyFocus!=null)apexKeyFocus.visible=false;return;
         }
         var count:int=owned ? int(grid.GetNumItems()) : int(feed.length);
         if(apexKeyIndex>=count || apexKeyIndex>=0 &&
            (owned ? grid.GetDataAtIndex(apexKeyIndex) : feed.RequestItemAt(apexKeyIndex))!==apexKeyItem) {
            apexKeyIndex=-1;apexKeyItem=null;apexKeyBounds="";
            if(apexKeyFocus!=null)apexKeyFocus.visible=false;
         }
         if(apexKeyIntent!=0) {
            if(apexPendingContext!=null)apexPendingContext.keyboard_unconsumed=null;
            var intent:Object=apexKeyQueue==null || apexKeyQueue.length==0 ? null : apexKeyQueue.shift();
            apexKeyIntent=apexKeyQueue!=null && apexKeyQueue.length>0 ? int(apexKeyQueue[0].key) : 0;
            if(intent==null || intent.sim!=String(mCurrSimInfo.simId) || intent.owner!=apexFormsSelectedId ||
               intent.panel!==panel || int(intent.state)!=mCurrState || intent.feed!==feed) {
               apexKeyRejected="catalog context changed";apexKeyQueue=[];apexKeyIntent=0;return;
            }
            var snapshot:Object=null;
            if(owned) {
               snapshot=grid.ApexGridStatus();
               if(intent.grid!==grid || intent.lease!==lease || lease==null ||
                  int(intent.lease_generation)!=int(lease.generation) || intent.native_generation!==lease.native_generation ||
                  int(intent.grid_generation)!=int(snapshot.generation) || int(intent.grid_revision)!=int(snapshot.revision) ||
                  !ApexCatalogGridInput(lease)) {
                  apexKeyRejected="catalog lease changed";apexKeyMessage="The catalog changed; press the key again.";
                  apexKeyQueue=[];apexKeyIntent=0;return;
               }
               var current:Object=grid.ApexGridStatus();
               if(ApexCatalogGridPending(grid) || grid.GetDataFeed()!==feed ||
                  apexCatalogGrid.lease!==lease || int(current.generation)!=int(snapshot.generation) ||
                  int(current.revision)!=int(snapshot.revision)) {
                  apexKeyRejected="catalog changed during input";apexKeyQueue=[];apexKeyIntent=0;return;
               }
            }
            var key:int=int(intent.key);
            if((!controlled && ApexCatalogKeyboardTyping()) || Boolean(CommunicationManager.CallUIService("IsUILoadingScreenVisible")) ||
               Boolean(CommunicationManager.CallUIService("IsModalVisible")) || Boolean(CommunicationManager.CallUIService("IsDialogModalVisible"))) {apexKeyQueue=[];apexKeyIntent=0;return;}
            if(count<1) return;
            var columns:int=Math.max(1,int(grid.GetGridDimensions()[grid.Horizontal ? 0 : 1]));
            var before:int=apexKeyIndex;
            if(before<0) {
               var selected:Array=feed.GetSelectedIndices();
               before=selected!=null && selected.length>0 ? int(selected[0]) : 0;
               if(owned && selected!=null && selected.length>0) {
                  var mapping:Object=grid.GetFilteredDataIndices();
                  if(mapping!=null)before=Math.max(0,int(mapping.indexOf(before)));
               }
            }
            var target:int=before;var page:int=0;
            if(key==37) target--;
            else if(key==39) target++;
            else if(key==38) target-=columns;
            else if(key==40) target+=columns;
            else if(key==36) target=0;
            else if(key==35) target=count-1;
            else if(key==33 || key==34) {
               var cells:Object=grid.GetVisibleCells(list.mScrollerView.GetScrollingRegion(),list.mScrollerView);
               page=columns*Math.max(1,int((cells==null ? columns : cells.length)/columns)-1);
               target+=(key==33 ? -page : page);
            }
            target=Math.max(0,Math.min(count-1,target));apexKeyIndex=target;
            apexKeyItem=owned ? grid.GetDataAtIndex(target) : feed.RequestItemAt(target);
            if(key==13) {
               // Reuse the exact native card click route, including its form,
               // swatch, eligibility, undo and equipped-view adapters.
               var item:Object=apexKeyItem;
               if(item==null) return;
               var cellIndex:int=target;
               if(owned) {
                  if(int(intent.focused_index)>=0 && (target!=int(intent.focused_index) || item!==intent.focused_item)) {
                     apexKeyRejected="focused card changed";apexKeyQueue=[];apexKeyIntent=0;return;
                  }
                  var ready:flash.display.DisplayObject=grid.GetViewAtIndex(target) as flash.display.DisplayObject;
                  current=grid.ApexGridStatus();
                  if(ApexCatalogGridPending(grid) || apexCatalogGrid.lease!==lease || grid.GetDataFeed()!==feed ||
                     int(current.generation)!=int(snapshot.generation) || int(current.revision)!=int(snapshot.revision) ||
                     grid.GetDataAtIndex(target)!==item || ready==null || !ready.visible || ready.stage!==stage ||
                     ready.parent!==list.GetGridView() || int(grid.GetGridIndexOfCell(ready))!=target) {
                     apexKeyRejected="focused card is not ready";apexKeyMessage="Wait for the focused card to appear.";
                     apexKeyQueue=[];apexKeyIntent=0;return;
                  }
                  cellIndex=int(grid.ApexGridCells.indexOf(ready));
                  if(cellIndex<0)return;
               }
               var click:GridEvent=new GridEvent(
                  GridEvent.CELL_EVENT+PushButtonEvent.CLICK,null,null,item,false,target,cellIndex);
               list.GetGridView().dispatchEvent(click);
            } else {
               var targetCell:flash.display.DisplayObject=grid.GetViewAtIndex(target) as flash.display.DisplayObject;
               var outside:Boolean=targetCell==null;
               if(targetCell!=null) {
                  var cellBounds:flash.geom.Rectangle=targetCell.getBounds(list.mScrollerView);
                  var viewport:flash.geom.Rectangle=list.mScrollerView.GetScrollingRegion();
                  outside=cellBounds.top<viewport.top || cellBounds.bottom>viewport.bottom;
               }
               if(outside || key==33 || key==34) {
                  var position:Number;
                  if(owned) {
                     if(apexCardLayout==null || !isFinite(Number(apexCardLayout.pitch_y)) || Number(apexCardLayout.pitch_y)<=0 ||
                        int(apexCardLayout.columns)!=columns)throw new Error("Confirmed catalog geometry unavailable");
                     position=Math.floor(target/columns)*Number(apexCardLayout.pitch_y);
                  } else position=grid.GetPositionOfIndex(target);
                  list.mSlider.SetCurrentValue(position+list.ScrollerViewMargin.mTop,false);
               }
            }
            apexKeyReceipt={key:key,sim_id:String(mCurrSimInfo.simId),owner_id:apexFormsSelectedId,
               menu_state:mCurrState,menu_state_before:int(intent.state),source_route:String(intent.route),
               index_before:before,index_after:target,count:count,columns:columns,
               page_step:page,click_dispatched:key==13};
         }
         if(apexKeyIndex<0) return;
         apexKeyMessage="Card "+(apexKeyIndex+1)+" of "+count+" / arrows browse, Enter selects";
         var cell:flash.display.DisplayObject=grid.GetViewAtIndex(apexKeyIndex) as flash.display.DisplayObject;
         if(apexKeyFocus==null) {
            apexKeyFocus=new flash.display.Sprite();apexKeyFocus.mouseEnabled=false;apexKeyFocus.mouseChildren=false;
         }
         if(apexKeyFocus.parent!==list.GetGridView()) {
            list.GetGridView().addChild(apexKeyFocus);apexKeyBounds="";
         }
         apexKeyFocus.visible=cell!=null && cell.stage!=null;
         if(!apexKeyFocus.visible) return;
         var rect:flash.geom.Rectangle=cell.getBounds(apexKeyFocus.parent);
         var boundsKey:String=rect.x+":"+rect.y+":"+rect.width+":"+rect.height;
         if(boundsKey==apexKeyBounds) return;
         apexKeyBounds=boundsKey;
         apexKeyFocus.graphics.clear();apexKeyFocus.graphics.lineStyle(2,0xffffff,1);
         apexKeyFocus.graphics.drawRoundRect(rect.x+2,rect.y+2,Math.max(1,rect.width-4),Math.max(1,rect.height-4),8,8);
         apexKeyMessage="Card "+(apexKeyIndex+1)+" of "+count+" / arrows browse, Enter selects";
         } catch(keyboardError:Error) {
            apexKeyQueue=[];apexKeyIntent=0;apexKeyIndex=-1;apexKeyReceipt=null;
            apexKeyMessage="Keyboard navigation paused: "+keyboardError.message;
            if(apexKeyFocus!=null) apexKeyFocus.visible=false;
         }
      }

private function ApexCatalogKeyboardCommand(value:String) : void
      {
         var codes:Object={left:37,up:38,right:39,down:40,home:36,end:35,pageup:33,pagedown:34};
         if(!codes.hasOwnProperty(value)) throw new Error("Choose an explicit catalog navigation key");
         if(apexKeyQueue!=null && apexKeyQueue.length>0) throw new Error("Keyboard navigation is already pending");
         var panel:Object=mCurrentPanel;
         if(panel==null || !panel.visible || panel.mcTileList==null || panel.mcTileList.mGridLayout==null)
            throw new Error("No visible native card catalog");
         var grid:Object=panel.mcTileList.mGridLayout;
         var owned:Boolean=ApexCatalogGridOwns(grid);
         var lease:Object=owned ? apexCatalogGrid.lease : null;
         if(owned && (ApexCatalogGridPending(grid) || lease==null || lease.phase!="bound" || lease.active!==true))
            {ApexCatalogUnconsumedMark(int(codes[value]),panel,grid,lease,"semantic-navigation-before-queue");
             throw new Error("Wait for the catalog before using a key");}
         var snapshot:Object=owned ? grid.ApexGridStatus() : null;
         apexKeyReceipt=null;
         apexKeyQueue=[{key:int(codes[value]),sim:apexBoundSim,owner:apexFormsSelectedId,
            panel:panel,state:mCurrState,feed:grid.GetDataFeed(),grid:grid,lease:lease,
            lease_generation:owned ? int(lease.generation) : 0,native_generation:owned ? String(lease.native_generation) : "",
            grid_generation:owned ? int(snapshot.generation) : 0,grid_revision:owned ? int(snapshot.revision) : 0,
            focused_index:apexKeyIndex,focused_item:apexKeyItem,route:"semantic-navigation"}];
         apexKeyIntent=int(codes[value]);ApexCatalogKeyboardFrame(true);
         if(apexKeyReceipt==null || int(apexKeyReceipt.key)!=int(codes[value]))
            throw new Error(apexKeyMessage=="" ? "Native catalog navigation was not applied" : apexKeyMessage);
      }
