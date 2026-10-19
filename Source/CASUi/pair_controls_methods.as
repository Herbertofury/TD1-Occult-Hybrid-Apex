// Own controls at EA's portrait toolbar anchor. EA keeps its portraits/layout.
      private var apexPairRoot:flash.display.Sprite;
      private var apexPairContext:Object;
      private var apexPairIntent:Object;
      private var apexPairSignature:String="";
      private var apexPairTooltips:Array=[];
      private var apexPairMessage:String="";

      private function ApexPairDispose() : void
      {
         for each(var tooltip:TooltipObject in apexPairTooltips) tooltip.Shutdown();
         apexPairTooltips=[];
         if(apexPairRoot!=null) {
            apexPairRoot.removeEventListener(flash.events.MouseEvent.CLICK,ApexPairClick);
            if(apexPairRoot.parent!=null) apexPairRoot.parent.removeChild(apexPairRoot);
         }
         apexPairRoot=null;apexPairContext=null;apexPairIntent=null;apexPairSignature="";apexPairMessage="";
      }

      private function ApexPairRead() : Object
      {
         if(!apexFormsFastState || apexNativeChannel=="" || !apexNativeConnected) return null;
         var fields:Array=ApexNativeExchange("PAIR|"+apexNativeChannel).split("|");
         if(fields.length!=8 || fields[0]!="PAIR" || fields[1]!==apexBoundSim ||
            !/^[01]$/.test(fields[6]) || !/^[1-9][0-9]{0,19}$/.test(fields[7])) return null;
         for(var n:int=2;n<=5;++n)
            if(!/^[a-z0-9_][a-z0-9_-]{0,63}\/[a-z0-9_][a-z0-9_-]{0,63}$/.test(fields[n])) return null;
         if(fields[3]===fields[4] || fields[5]!==fields[3] && fields[5]!==fields[4] ||
            fields[2]!==fields[3] && fields[2]!==fields[4]) return null;
         var seen:int=0;
         for each(var owner:Object in apexFormsOwners) if(owner.id===fields[3] || owner.id===fields[4]) seen++;
         if(seen!=2) return null;
         return {sim_id:apexBoundSim,selected_owner_id:String(fields[2]),base_owner_id:String(fields[3]),
            alternate_owner_id:String(fields[4]),human_owner_id:String(fields[5]),linked:fields[6]=="1",generation:String(fields[7])};
      }

      private function ApexPairExecute(intent:Object) : Object
      {
         var pair:Object=ApexPairRead();
         if(pair==null || intent==null || intent.sim_id!==apexBoundSim ||
            !((intent.source_owner_id===pair.base_owner_id && intent.target_owner_id===pair.alternate_owner_id) ||
              (intent.source_owner_id===pair.alternate_owner_id && intent.target_owner_id===pair.base_owner_id)) ||
            ["copy","link"].indexOf(String(intent.operation))<0 || !(intent.enabled is Boolean) ||
            intent.operation=="copy" && intent.enabled!==false || apexNonce.length!=64 || apexFormsGestureSequence>=2147483647)
            throw new Error("Pair changed before the requested link/copy; no action submitted");
         apexFormsGestureSequence++;
         var nonce:String=apexNonce.substr(0,24)+("00000000"+apexFormsGestureSequence.toString(16)).substr(-8);
         var payload:String=nonce+"|"+apexBoundSim+"|"+pair.generation+"|"+intent.source_owner_id+"|"+intent.target_owner_id+"|"+intent.operation+"|"+(intent.enabled?"1":"0");
         var response:String=ApexNativeExchange("PAIRDO|"+apexNativeChannel+"|"+payload);
         if(response!=="PAIRDONE|"+nonce) throw new Error("Native pair action did not complete; do not replay it");
         ApexFormsReadNativeState();apexPairContext=ApexPairRead();
         if(apexPairContext==null || apexPairContext.sim_id!==pair.sim_id ||
            apexPairContext.base_owner_id!==pair.base_owner_id || apexPairContext.alternate_owner_id!==pair.alternate_owner_id ||
            intent.operation=="link" && apexPairContext.linked!==intent.enabled)
            throw new Error("Native pair postcondition unresolved; do not replay the action");
         return {operation:intent.operation,request_id:nonce,sim_id:pair.sim_id,source_owner_id:intent.source_owner_id,
            target_owner_id:intent.target_owner_id,enabled:intent.enabled,acknowledged:true,scope:"whole-appearance",
            pair:apexPairContext,appearance_persistence_verified:false};
      }

      private function ApexPairClick(event:flash.events.MouseEvent) : void
      {
         if(event==null || event.target==null || apexPairContext==null || apexPairIntent!=null ||
            apexFormsDesiredId!="" || apexFormsNativeIntent!=null || apexPendingFields!=null || apexReceiving) return;
         var name:String=String(event.target.name);var pair:Object=apexPairContext;
         if(["apexPair_link","apexPair_down","apexPair_up"].indexOf(name)<0) return;
         apexPairIntent={sim_id:apexBoundSim,operation:name=="apexPair_link"?"link":"copy",enabled:name=="apexPair_link"?!pair.linked:false,
            // EA draws alternate above base, including Alien's disguise pair.
            source_owner_id:name=="apexPair_down"?pair.alternate_owner_id:pair.base_owner_id,
            target_owner_id:name=="apexPair_down"?pair.base_owner_id:pair.alternate_owner_id};
         if(!apexFormsFrameQueued) {
            apexFormsFrameQueued=true;
            addEventListener(flash.events.Event.ENTER_FRAME,ApexFormsNextFrame,false,0,true);
         }
      }

      private function ApexPairLabel(id:String) : String
      {
         for each(var owner:Object in apexFormsOwners) if(owner.id===id) return String(owner.label);
         return id;
      }

      private function ApexPairButton(name:String,y:Number,tip:String,linked:Boolean=false) : void
      {
         var button:flash.display.Sprite=new flash.display.Sprite();button.name="apexPair_"+name;button.y=y;
         button.mouseChildren=false;button.buttonMode=true;
         button.graphics.lineStyle(1,linked?0x7cb737:0x93b5ce);button.graphics.beginFill(linked?0xe8f8c9:0xffffff,0.98);
         button.graphics.drawRoundRect(0,0,30,24,9,9);button.graphics.endFill();
         button.graphics.lineStyle(2,linked?0x568c18:0x387fba);
         if(name=="link") {
            button.graphics.drawRoundRect(6,7,12,7,5,5);button.graphics.drawRoundRect(13,11,12,7,5,5);
            if(!linked) {button.graphics.moveTo(8,19);button.graphics.lineTo(23,4);}
         } else {
            var from:Number=name=="down"?5:19;var to:Number=name=="down"?18:6;var edge:Number=name=="down"?13:11;
            button.graphics.moveTo(15,from);button.graphics.lineTo(15,to);
            button.graphics.moveTo(10,edge);button.graphics.lineTo(15,to);button.graphics.lineTo(20,edge);
         }
         apexPairRoot.addChild(button);
         var tooltip:TooltipObject=new TooltipObject(button);tooltip.Initialize({text:tip,maxwidth:300},250);apexPairTooltips.push(tooltip);
      }

      private function ApexPairTick() : void
      {
         if(apexPairIntent!=null && apexPendingFields==null && !apexReceiving && apexFormsDesiredId=="" && apexFormsNativeIntent==null) {
            var intent:Object=apexPairIntent;apexPairIntent=null;
            try {ApexPairExecute(intent);apexPairMessage="";} catch(error:Error) {apexPairMessage=error.message;}
         }
         var pair:Object=ApexPairRead();
         var feed:Object=CommunicationManager.CallUIService("ApexReadOwnerPairFeed",null);
         var anchor:Object=feed && feed.retained ? feed.retained.pair_controls_anchor : null;
         if(pair==null || anchor==null || !(anchor.x is Number) || !(anchor.y is Number) || !isFinite(anchor.x) || !isFinite(anchor.y)) {
            if(apexPairRoot!=null) apexPairRoot.visible=false;return;
         }
         apexPairContext=pair;
         var signature:String=apexBoundSim+"|"+pair.base_owner_id+"|"+pair.alternate_owner_id+"|"+pair.linked;
         if(signature!==apexPairSignature || apexPairRoot==null) {
            if(apexPairRoot==null) {
               apexPairRoot=new flash.display.Sprite();apexPairRoot.name="ApexPortraitPairControls";
               apexPairRoot.addEventListener(flash.events.MouseEvent.CLICK,ApexPairClick,false,0,true);addChild(apexPairRoot);
            }
            for each(var old:TooltipObject in apexPairTooltips) old.Shutdown();apexPairTooltips=[];
            while(apexPairRoot.numChildren>0) apexPairRoot.removeChildAt(0);
            ApexPairButton("link",0,(pair.linked?"Unlink":"Link")+" "+ApexPairLabel(pair.base_owner_id)+" and "+ApexPairLabel(pair.alternate_owner_id)+". Whole appearance; linking keeps both current looks and affects later edits only.",pair.linked);
            ApexPairButton("down",27,"Copy upper "+ApexPairLabel(pair.alternate_owner_id)+" to lower "+ApexPairLabel(pair.base_owner_id)+". Whole appearance; other forms remain separate.");
            ApexPairButton("up",54,"Copy lower "+ApexPairLabel(pair.base_owner_id)+" to upper "+ApexPairLabel(pair.alternate_owner_id)+". Whole appearance; other forms remain separate.");
            apexPairSignature=signature;
         }
         var point:flash.geom.Point=globalToLocal(new flash.geom.Point(anchor.x,anchor.y));
         apexPairRoot.x=point.x;apexPairRoot.y=point.y;apexPairRoot.visible=true;
         apexPairRoot.alpha=apexPendingFields!=null || apexFormsDesiredId!="" || apexPairIntent!=null ? 0.5:1;
      }

      private function ApexPairStatus() : Object
      {
         return {visible:apexPairRoot!=null && apexPairRoot.visible,pair:ApexClone(apexPairContext),
            pending:apexPairIntent!=null,message:apexPairMessage,scope:"whole-appearance",selective_copy_available:false};
      }
