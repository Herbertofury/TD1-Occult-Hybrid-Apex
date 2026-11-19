// EA owns the real portrait panel, buttons and category list. This adapter
// only binds its explicit actions to an independent Sim/form pair.
      private var apexPairRoot:flash.display.Sprite;
      private var apexPairContext:Object;
      private var apexPairIntent:Object;
      private var apexPairSignature:String="";
      private var apexPairTooltips:Array=[];
      private var apexPairMessage:String="";
      private var apexPairRegistered:Boolean=false;

      private function ApexPairDispose() : void
      {
         apexPairRoot=null;apexPairContext=null;apexPairIntent=null;
         apexPairSignature="";apexPairMessage="";
      }

      private function ApexPairRead() : Object
      {
         if(!apexFormsFastState || apexNativeChannel=="" || !(apexNativeConnected || apexFormsLocalCatalog)) return null;
         var fields:Array=ApexNativeExchange("PAIR|"+apexNativeChannel).split("|");
         if(fields.length!=9 || fields[0]!="PAIR" || fields[1]!==apexBoundSim ||
            !/^[01]$/.test(fields[6]) || !/^[1-9][0-9]{0,19}$/.test(fields[7]) ||
            !/^(0|[1-9][0-9]{0,9})$/.test(fields[8]) || Number(fields[8])>4294967295) return null;
         for(var n:int=2;n<=5;++n)
            if(!/^[a-z0-9_][a-z0-9_-]{0,63}\/[a-z0-9_][a-z0-9_-]{0,63}$/.test(fields[n])) return null;
         if(fields[3]===fields[4] || fields[5]!==fields[3] && fields[5]!==fields[4] ||
            fields[2]!==fields[3] && fields[2]!==fields[4]) return null;
         var seen:int=0;
         for each(var owner:Object in apexFormsOwners) if(owner.id===fields[3] || owner.id===fields[4]) seen++;
         if(seen!=2) return null;
         return {sim_id:apexBoundSim,selected_owner_id:String(fields[2]),base_owner_id:String(fields[3]),
            alternate_owner_id:String(fields[4]),human_owner_id:String(fields[5]),linked:fields[6]=="1",
            generation:String(fields[7]),category_flags:Number(fields[8])};
      }

      private function ApexPairExecute(intent:Object) : Object
      {
         var pair:Object=ApexPairRead();
         var furRestore:Boolean=intent!=null && intent.operation=="copy" &&
            Number(intent.category_flags)==16777232 && apexFormsSelectedId==="werewolf/werewolf_human_cc" &&
            intent.target_owner_id===apexFormsSelectedId && intent.source_owner_id==="native/32";
         if(pair==null || intent==null || intent.sim_id!==apexBoundSim ||
            intent.hasOwnProperty("session") && intent.session!==apexOwnerSession ||
            intent.hasOwnProperty("generation") && intent.generation!==pair.generation ||
            !((intent.source_owner_id===pair.base_owner_id && intent.target_owner_id===pair.alternate_owner_id) ||
              (intent.source_owner_id===pair.alternate_owner_id && intent.target_owner_id===pair.base_owner_id) || furRestore) ||
            ["copy","link"].indexOf(String(intent.operation))<0 || !(intent.enabled is Boolean) ||
            intent.operation=="copy" && intent.enabled!==false ||
            apexNonce.length!=64 && !apexFormsLocalCatalog || apexFormsGestureSequence>=2147483647)
            throw new Error("Pair changed before the requested link/copy; no action submitted");
         var flags:Number=intent.hasOwnProperty("category_flags")?Number(intent.category_flags):4294967295;
         if(!isFinite(flags) || flags<0 || flags>4294967295 || flags!=Math.floor(flags) ||
            flags==0 && (intent.operation=="copy" || intent.enabled)) throw new Error("Select the details to copy or link");
         apexFormsGestureSequence++;
         var nonce:String="";
         if(apexNonce.length==64) nonce=apexNonce.substr(0,24)+("00000000"+apexFormsGestureSequence.toString(16)).substr(-8);
         else {
            // Player link/copy uses the same exact native pair while Source's
            // independent CLI handshake finishes. The ID is replay protection,
            // not permission: native channel/Sim/owner/generation checks stay.
            var localRequest:Array=ApexNativeExchange("UIREQUEST|"+apexNativeChannel).split("|");
            if(localRequest.length!=5 || localRequest[0]!=="UIREQUEST" || localRequest[1]!==apexBoundSim ||
               localRequest[2]!==apexFormsSelectedId || localRequest[3]!==pair.generation ||
               !/^[0-9a-f]{32}$/.test(localRequest[4])) throw new Error("Local pair request changed context; no action submitted");
            nonce=String(localRequest[4]);
         }
         var payload:String=nonce+"|"+apexBoundSim+"|"+pair.generation+"|"+intent.source_owner_id+"|"+intent.target_owner_id+"|"+intent.operation+"|"+(intent.enabled?"1":"0")+"|"+String(flags);
         var response:String=ApexNativeExchange("PAIRDO|"+apexNativeChannel+"|"+payload);
         if(response!=="PAIRDONE|"+nonce) throw new Error("Native pair action did not complete; do not replay it");
         ApexFormsReadNativeState();apexPairContext=ApexPairRead();
         if(apexPairContext==null || apexPairContext.sim_id!==pair.sim_id ||
            apexPairContext.base_owner_id!==pair.base_owner_id || apexPairContext.alternate_owner_id!==pair.alternate_owner_id ||
            intent.operation=="link" && (apexPairContext.linked!==intent.enabled || apexPairContext.category_flags!==flags))
            throw new Error("Native pair postcondition unresolved; do not replay the action");
         return {operation:intent.operation,request_id:nonce,sim_id:pair.sim_id,source_owner_id:intent.source_owner_id,
            target_owner_id:intent.target_owner_id,enabled:intent.enabled,acknowledged:true,
            scope:flags==4294967295?"whole-appearance":"selected-categories",category_flags:flags,
            pair:apexPairContext,appearance_persistence_verified:false};
      }

      private function ApexPairPanel(request:Object) : Object
      {
         var inputStarted:int=getTimer();
         if(request==null || request.sim_id!==apexBoundSim || apexFormsOwners.length==0) return null;
         if(apexFormsDesiredId!="" || apexFormsNativeIntent!=null)
            return {blocked:true,enabled:false};
         ApexFormsReadNativeState();var pair:Object=ApexPairRead();
         if(pair==null) return {blocked:true,enabled:false};
         if(request.operation=="status") {
            pair.enabled=true;pair.source_label=ApexPairLabel(pair.selected_owner_id);
            for each(var owner:Object in apexFormsOwners) if(owner.id===pair.selected_owner_id)
               pair.native_kind=int(owner.kind);
            pair.target_label=ApexPairLabel(pair.selected_owner_id===pair.base_owner_id?pair.alternate_owner_id:pair.base_owner_id);
            return pair;
         }
         if(ApexFormsCommandBlocksInput()) return {blocked:true,enabled:false};
         if(["copy","link"].indexOf(String(request.operation))<0 ||
            request.generation!==pair.generation || request.base_owner_id!==pair.base_owner_id ||
            request.alternate_owner_id!==pair.alternate_owner_id || !(request.enabled is Boolean) ||
            !(request.category_flags is Number) || request.category_flags<0 || request.category_flags>4294967295 ||
            request.category_flags!=Math.floor(request.category_flags))
            return {blocked:true,enabled:false,message:"The selected pair changed or an action is pending"};
         // Consecutive checkbox/link changes on this exact pair keep the last
         // requested state. A Copy remains a distinct one-shot operation.
         if(apexPairIntent!=null && (request.operation!="link" || apexPairIntent.operation!="link" ||
            apexPairIntent.sim_id!==apexBoundSim || apexPairIntent.session!==apexOwnerSession ||
            apexPairIntent.generation!==pair.generation))
            return {blocked:true,enabled:false,message:"A separate pair action is pending"};
         apexPairIntent={sim_id:pair.sim_id,session:apexOwnerSession,generation:pair.generation,
            operation:request.operation,enabled:request.enabled,category_flags:request.category_flags,
            source_owner_id:pair.selected_owner_id,
            target_owner_id:pair.selected_owner_id===pair.base_owner_id?pair.alternate_owner_id:pair.base_owner_id};
         ApexFormsScheduleFrame();ApexInputTiming(inputStarted);return {queued:true,enabled:true};
      }

      // No replacement floating buttons. Keep these retired entry points for
      // the semantic bridge's explicit method inventory and old diagnostics.
      private function ApexPairClick(event:flash.events.MouseEvent) : void { }
      private function ApexPairButton(name:String,y:Number,tip:String,linked:Boolean=false) : void { }
      private function ApexPairLabel(id:String) : String
      {
         for each(var owner:Object in apexFormsOwners) if(owner.id===id) return String(owner.label);
         return id;
      }
      private function ApexPairTick() : void
      {
         if(apexPairIntent==null || ApexFormsCommandBlocksInput() || apexFormsDesiredId!="" || apexFormsNativeIntent!=null) return;
         var intent:Object=apexPairIntent;apexPairIntent=null;
         try {ApexPairExecute(intent);apexPairMessage="";} catch(error:Error) {apexPairMessage=error.message;}
         CommunicationManager.CallUIService("ApexConfigureFormPortraits",{sim_id:apexBoundSim,refresh_pair:true});
      }
      private function ApexPairStatus() : Object
      {
         var observed:Object=CommunicationManager.CallUIService("ApexReadOwnerPairFeed",null);
         observed=observed!=null && observed.retained!=null?observed.retained.native_pair_panel:null;
         return {visible:observed!=null && observed.visible===true,native_panel:true,panel:ApexClone(observed),pair:ApexClone(apexPairContext),pending:apexPairIntent!=null,
            message:apexPairMessage,scope:"selected-categories",selective_copy_available:true};
      }
