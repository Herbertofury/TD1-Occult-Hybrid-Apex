// Apex-owned methods inserted into the installed build's CASCustomizerMain.
// No mouse input, arbitrary evaluation, network access, or executable offsets.
      private var apexWire:String = "";
      private var apexReceiving:Boolean = false;
      private var apexLastId:String = "";
      private var apexLastReply:String = "";

      private function ApexInitialize() : void
      {
         apexWire=""; apexReceiving=false; apexLastId=""; apexLastReply="";
         AddMessageListener("ApexCAS.Begin",ApexBegin);
         AddMessageListener("ApexCAS.End",ApexExecute);
         for(var code:int = 32; code <= 126; ++code)
            AddMessageListener("ApexCAS.Char." + code,ApexCharacter(code));
         CommunicationManager.PostServerCommand("apex.cas.ready",1);
      }

      private function ApexBegin(message:Object=null) : void { apexWire = ""; apexReceiving = true; }
      private function ApexCharacter(code:int) : Function
      {
         return function(message:Object=null):void {
            if(apexReceiving && apexWire.length < 512) apexWire += String.fromCharCode(code);
            else apexReceiving = false;
         };
      }

      private function ApexQuote(value:String) : String
      {
         var result:String = '"';
         for(var i:int=0; i<value.length; ++i) {
            var c:int=value.charCodeAt(i);
            if(c==34 || c==92) result += "\\" + value.charAt(i);
            else if(c<32) result += "\\u" + ("0000" + c.toString(16)).substr(-4);
            else result += value.charAt(i);
         }
         return result + '"';
      }

      private function ApexEncode(value:*, depth:int=0) : String
      {
         if(depth>12) throw new Error("CAS result nesting exceeds limit");
         if(value==null) return "null";
         if(value is String) return ApexQuote(value);
         if(value is Boolean) return value ? "true" : "false";
         if(value is Number) return isFinite(value) ? String(value) : "null";
         var parts:Array=[];
         if(value is Array) {
            if(value.length>1024) throw new Error("CAS result list exceeds limit");
            for each(var item:* in value) parts.push(ApexEncode(item,depth+1));
            return "[" + parts.join(",") + "]";
         }
         for(var key:String in value) {
            if(parts.length>=1024) throw new Error("CAS result object exceeds limit");
            parts.push(ApexQuote(key) + ":" + ApexEncode(value[key],depth+1));
         }
         return "{" + parts.join(",") + "}";
      }

      private function ApexSnapshot() : Object
      {
         var catalogs:Array=[];
         // Read every mapped native panel without changing the selected panel.
         // Null remains unsupported/unknown; it must never masquerade as empty.
         var panels:Object=__APEX_PANEL_STATES__;
         for(var name:String in panels) {
            var items:* = CommunicationManager.CallGameService("GetCatalogItemsSelectedWithModifiers",{state:panels[name]});
            var preset:* = null; var presetQuery:String="returned-null";
            try {
               preset=CommunicationManager.CallGameService("GetSelectedPresetFromMenuState",panels[name],true);
               if(preset!=null) presetQuery="returned-value";
            } catch(presetError:Error) { presetQuery="failed"; }
            catalogs.push({panel:name,menu_state:panels[name],supported:items is Array,items:items is Array ? items : null,
               preset:preset,preset_query:presetQuery});
         }
         return {protocol:1,scope:"native-cas-client",sim:CommunicationManager.CallGameService("CASGetSimInfo",null,true),
            menu_state:this.mCurrState,panel_visible:this.mCurrentPanel!=null && this.mCurrentPanel.visible,
            outfit:CommunicationManager.CallGameService("CasGetCurrSimOutfitSlot"),
            selected:CommunicationManager.CallGameService("GetCatalogItemsSelectedWithModifiers",{state:this.mCurrState}),
            hair_color:CommunicationManager.CallGameService("CasGetSwatchColorSelected",2),catalogs:catalogs};
      }

      private function ApexExecute(message:Object=null) : void
      {
         if(!apexReceiving) return;
         apexReceiving=false;
         var fields:Array=apexWire.split("|");
         if(fields.length!=7 || String(fields[0]).length!=32) return;
         var id:String=fields[0];
         if(id==apexLastId) {
            CommunicationManager.PostServerCommand("apex.cas.reply",id,apexLastReply); return;
         }
         var reply:Object={ok:false,protocol:1,scope:"native-cas-client",cas_request_id:id};
         try {
            var native:Object=CommunicationManager.CallGameService("CASGetSimInfo",null,true);
            if(!native || String(native.simId)!=String(fields[1])) throw new Error("CAS selected Sim differs from request");
            var operation:String=fields[2]; var state:int=int(fields[3]);
            reply.operation=operation;
            var category:int=int(fields[4]); var index:int=int(fields[5]); var value:String=fields[6];
            if(operation=="panel") {
               HandleContextMenuSetMenuState({menuState:state,skipAnim:true,setZoomState:true});
               if(this.mCurrState!=state || !this.mCurrentPanel || !this.mCurrentPanel.visible)
                  throw new Error("Native CAS panel did not become visible");
            } else if(operation=="outfit") {
               var planned:Object=CommunicationManager.CallGameService("CasGetPlannedOutfits",category);
               if(!planned || !planned.outfit_list || index<0 || index>=planned.outfit_list.length)
                  throw new Error("CAS outfit does not exist; no outfit generated");
               CommunicationManager.CallGameService("CasSelectPlannedOutfit",{outfit_type:category,outfit_index:index});
               CommunicationManager.SendUIMessage("CASRefreshActiveCatalog");
               var slot:Object=CommunicationManager.CallGameService("CasGetCurrSimOutfitSlot");
               if(!slot || int(slot.outfit_type)!=category || int(slot.outfit_index)!=index)
                  throw new Error("Native CAS outfit selection did not match");
            } else if(operation=="select") {
               // Presets, skin tones, featured looks and layered products have
               // different native contracts. Do not guess their write payload.
               if(state!=MenuState.CLOTHING_HAIR && state!=MenuState.CLOTHING_TOPS && state!=MenuState.CLOTHING_BOTTOMS &&
                  state!=MenuState.CLOTHING_FULLBODY && state!=MenuState.CLOTHING_SHOES)
                  throw new Error("Native selection for this panel requires its typed preset/layer contract; no item changed");
               if(MenuState.SupportsLayerList(state)) throw new Error("Layered selection requires an explicit layer; no item changed");
               HandleContextMenuSetMenuState({menuState:state,skipAnim:true,setZoomState:true});
               var product:Object=CommunicationManager.CallGameService("GetCatalogItem",value);
               if(!product) throw new Error("Native CAS catalog item is unavailable");
               CommunicationManager.CallGameService("SetCatalogSlotSelected",{data_id:value});
               CommunicationManager.SendUIMessage("CASRefreshActiveCatalog");
               var selected:Array=CommunicationManager.CallGameService("GetCatalogItemsSelectedWithModifiers",{state:state}) as Array;
               var matched:Boolean=false;
               for each(var selectedItem:Object in selected)
                  if(String(selectedItem.dataID)==value) matched=true;
               if(!matched) throw new Error("Native CAS did not read back the requested catalog item");
            } else if(operation=="undo" || operation=="redo") {
               var before:Object=ApexSnapshot();
               CommunicationManager.CallGameService(operation=="undo" ? "CasUndo" : "CasRedo");
               CommunicationManager.SendUIMessage("CASRefreshActiveCatalog");
               if(ApexEncode(before)==ApexEncode(ApexSnapshot()))
                  throw new Error("Native history operation produced no observable client change");
            } else if(operation!="status") throw new Error("Unsupported semantic CAS operation");
            reply.ok=true; reply.client=ApexSnapshot();
         } catch(error:Error) { reply.message=error.message; }
         apexLastId=id; apexLastReply=ApexEncode(reply);
         if(apexLastReply.length>32768) apexLastReply=ApexEncode({ok:false,protocol:1,scope:"native-cas-client",cas_request_id:id,message:"CAS response exceeds limit; no partial inventory returned"});
         CommunicationManager.PostServerCommand("apex.cas.reply",id,apexLastReply);
      }
