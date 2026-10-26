      // A one-request witness from the exact rejection before queue insertion.
      // No witness is created for ordinary player events or an executed key.
      private function ApexCatalogUnconsumedMark(code:int,panel:Object,grid:Object,lease:Object,route:String) : void {
         if(apexPendingFields==null || apexPendingContext==null || apexPendingReply==null ||
            apexPendingReply.mutation_started!==false || apexClaimNonce!==apexNonce || stage==null || apexDisconnected ||
            !apexSocketActive || panel!==mCurrentPanel || panel==null || panel.mcTileList==null ||
            grid==null || panel.mcTileList.mGridLayout!==grid || lease==null || apexCatalogGrid==null ||
            apexCatalogGrid.grid!==grid || apexCatalogGrid.lease!==lease || apexKeyIntent!=0 ||
            apexKeyQueue!=null && apexKeyQueue.length!=0 || apexKeyReceipt!=null || code==13)return;
         var fields:Array=apexPendingFields;var context:Object=apexPendingContext;var reply:Object=apexPendingReply;
         var peer:String=apexClaimNonce;var originalStage:Object=stage;var channel:String=apexNativeChannel;
         var operation:String=String(fields[2]);var value:Array=String(fields[6]).split(",");
         var codes:Object={left:37,up:38,right:39,down:40,home:36,end:35,pageup:33,pagedown:34};
         if(!codes.hasOwnProperty(value[0]) || int(codes[value[0]])!=code || apexPendingContext.keyboard_before==null)return;
         if(operation=="catalog-input") {
            if(!apexKeyInjecting || route!="shared-keyboard-handler-before-queue" || value.length!=2 ||
               value[1]!="0" && value[1]!="1")return;
         } else if(operation!="catalog-key" || route!="semantic-navigation-before-queue" || value.length!=1)return;
         var held:Object={request_id:String(fields[0]),peer_nonce:peer,
            before:ApexClone(context.keyboard_before),stage:originalStage,channel:channel,
            panel:panel,list:panel.mcTileList,view:panel.mcTileList.GetGridView(),grid:grid,feed:grid.GetDataFeed(),
            lease:lease,lease_generation:int(lease.generation),native_generation:String(lease.native_generation),
            received:apexKeyReceived,last_code:apexKeyLastCode,code:code,key:String(value[0]),route:route,
            focus_requested:operation=="catalog-input" && value[1]=="1"};
         // Getter reentry may replace the active request. Only the original
         // Main-owned context may receive or retire this one witness.
         if(apexPendingFields!==fields || apexPendingContext!==context || apexPendingReply!==reply)return;
         context.keyboard_unconsumed=held;
         if(!ApexCatalogUnconsumedBound(held,fields,context,reply) && context.keyboard_unconsumed===held)
            context.keyboard_unconsumed=null;
      }

      private function ApexCatalogUnconsumedBound(held:Object,fields:Array,context:Object,reply:Object) : Boolean {
         if(held==null || apexPendingFields!==fields || apexPendingContext!==context || apexPendingReply!==reply ||
            context.keyboard_unconsumed!==held || context.keyboard_publication!=null || reply.mutation_started!==false ||
            String(fields[0])!==held.request_id || apexClaimNonce!==held.peer_nonce || apexNonce!==held.peer_nonce ||
            apexDisconnected || !apexSocketActive || apexNativeChannel!==held.channel || stage!==held.stage || stage==null ||
            apexKeyIntent!=0 || apexKeyQueue!=null && apexKeyQueue.length!=0 || apexKeyReceipt!=null ||
            apexKeyReceived!=held.received || apexKeyLastCode!=held.last_code || mCurrSimInfo==null ||
            mCurrentPanel!==held.panel || String(mCurrSimInfo.simId)!==held.before.sim_id ||
            String(mCurrSimInfo.householdId)!==held.before.household_id || int(mCurrSimInfo.occultLayer)!=int(held.before.layer) ||
            int(mCurrSimInfo.occultType)!=int(held.before.native_kind) || int(mCurrSimInfo.allOccultTypes)!=int(held.before.native_mask) ||
            apexBoundSim!==held.before.sim_id || apexFormsSelectedId!==held.before.owner_id || apexOwnerSession!=int(held.before.session) ||
            apexFormsNativeGeneration!==held.before.native_generation || int(mCurrState)!=int(held.before.menu_state) ||
            apexFormsNativeState!=="bound" || apexFormsDesiredId!=="" || apexFormsIntent!=null || apexFormsNativeIntent!=null ||
            apexMoleculeIntent!=null || apexPairIntent!=null || apexFormsApplying ||
            apexCatalogGrid==null || apexCatalogGrid.grid!==held.grid || apexCatalogGrid.lease!==held.lease ||
            int(held.lease.generation)!=int(held.lease_generation) || String(held.lease.native_generation)!==held.native_generation ||
            !ApexCatalogKeyboardScopeEqual(context.keyboard_before,held.before))return false;
         var operation:String=String(fields[2]);var value:Array=String(fields[6]).split(",");
         if(operation=="catalog-input")return held.route==="shared-keyboard-handler-before-queue" && value.length==2 &&
            String(value[0])===held.key && (value[1]==="0" || value[1]==="1") &&
            held.focus_requested===(value[1]==="1") && apexKeyRejected==="catalog is still loading" &&
            apexKeyMessage==="Wait for the catalog before using a key.";
         return operation=="catalog-key" && held.route==="semantic-navigation-before-queue" && value.length==1 &&
            String(value[0])===held.key && held.focus_requested===false;
      }

      private function ApexCatalogUnconsumedCurrent(held:Object,fields:Array,context:Object,reply:Object) : Boolean {
         if(apexKeyInjecting || !ApexCatalogUnconsumedBound(held,fields,context,reply))return false;
         return held.panel.stage===stage && held.panel.mcTileList===held.list && held.list.mGridLayout===held.grid &&
            held.list.GetGridView()===held.view && held.grid.GetDataFeed()===held.feed &&
            held.panel.stage===stage && held.panel.mcTileList===held.list && held.list.mGridLayout===held.grid &&
            ApexCatalogUnconsumedBound(held,fields,context,reply);
      }

      private function ApexCatalogUnconsumedReply(fields:Array,context:Object,reply:Object) : Boolean {
         var held:Object=context.keyboard_unconsumed;
         if(!ApexCatalogUnconsumedCurrent(held,fields,context,reply))return false;
         var raw:Object=CommunicationManager.CallGameService("CASGetSimInfo",null,true);
         var selected:Object=ApexOwnerSimRow(raw);raw=null;
         var after:Object=ApexCatalogReadbackContext(selected);selected=null;
         if(!ApexCatalogUnconsumedCurrent(held,fields,context,reply) ||
            !ApexCatalogKeyboardScopeEqual(held.before,after))return false;
         reply.ok=false;reply.message="CAS catalog navigation rejected before consumption: catalog is still loading";
         reply.navigation_unconsumed={protocol:1,emitter:"apex-keyboard-loading-before-queue-v1",
            request_id:held.request_id,peer_nonce:held.peer_nonce,before:ApexClone(held.before),after:after,
            requested_key:held.key,key_code:int(held.code),source_route:held.route,rejection:"catalog-loading-before-consumption",
            key_listener_invoked:String(fields[2])==="catalog-input",navigation_dispatched:false,appearance_written:false,
            intent:0,queued:0,receipt_present:false,focus_requested:Boolean(held.focus_requested)};
         return true;
      }
