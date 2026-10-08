// Apex-owned methods inserted into the installed build's CASCustomizerMain.
// Typed data only over a fixed loopback socket. No code fetch/evaluation,
// arbitrary URLs, mouse input, or executable offsets.
      private var apexWire:String = "";
      private var apexReceiving:Boolean = false;
      private var apexLastId:String = "";
      private var apexLastReply:String = "";
      private var apexSocket:flash.net.Socket;
      private var apexTimer:flash.utils.Timer;
      private var apexFrame:String = "";
      private var apexExpected:int = -1;
      private var apexNonce:String = "";
      private var apexBoundSim:String = "";
      private var apexAwaiting:String = "";
      private var apexAckId:String = "";
      private var apexDisconnected:Boolean = true;
      private var apexSocketActive:Boolean = false;
      private var apexSocketError:String = "";

      private function ApexInitialize() : void
      {
         // A missing/unsupported intrinsic must not escape the game's native
         // initializer. CAS disconnects its Python Distributor client, so this
         // transport is driven exclusively by native UI events and its timer.
         try {
            ApexDisconnect();
            apexWire=""; apexReceiving=false; apexLastId=""; apexLastReply="";
            apexDisconnected=false; apexSocketError="";
            apexTimer=new flash.utils.Timer(500);
            apexTimer.addEventListener(flash.events.TimerEvent.TIMER,ApexTick);
            apexTimer.start();
            ApexTick();
         } catch(startError:Error) {
            apexSocketError=String(startError);
            ApexDisconnect();
         }
      }

      private function ApexResetSocket() : void
      {
         if(apexSocket) {
            apexSocket.removeEventListener(flash.events.Event.CONNECT,ApexSocketConnect);
            apexSocket.removeEventListener(flash.events.Event.CLOSE,ApexSocketFailure);
            apexSocket.removeEventListener(flash.events.IOErrorEvent.IO_ERROR,ApexSocketFailure);
            apexSocket.removeEventListener("securityError",ApexSocketFailure);
            apexSocket.removeEventListener(flash.events.ProgressEvent.SOCKET_DATA,ApexSocketData);
            try { apexSocket.close(); } catch(closeError:Error) { }
         }
         apexSocket=null; apexSocketActive=false; apexNonce=""; apexBoundSim="";
         apexAwaiting=""; apexAckId=""; apexFrame=""; apexExpected=-1;
         apexReceiving=false; apexWire="";
         // Keep the last UUID/reply across connection failures. A lost ACK
         // never makes a delivered mutation eligible for blind execution again.
      }

      private function ApexDisconnect() : void
      {
         apexDisconnected=true;
         if(apexTimer) {
            apexTimer.stop();
            apexTimer.removeEventListener(flash.events.TimerEvent.TIMER,ApexTick);
            apexTimer=null;
         }
         ApexResetSocket();
      }

      private function ApexTick(message:Object=null) : void
      {
         if(apexDisconnected) return;
         try {
            var native:Object=CommunicationManager.CallGameService("CASGetSimInfo",null,true);
            var simId:String=native ? String(native.simId) : "";
            if(!/^[1-9][0-9]{0,19}$/.test(simId)) return;
            if(apexSocket==null) {
               apexSocket=new flash.net.Socket();
               apexSocket.addEventListener(flash.events.Event.CONNECT,ApexSocketConnect);
               apexSocket.addEventListener(flash.events.Event.CLOSE,ApexSocketFailure);
               apexSocket.addEventListener(flash.events.IOErrorEvent.IO_ERROR,ApexSocketFailure);
               // GFx may expose a SecurityErrorEvent class stub; using its
               // event-name string avoids resolving that unsupported class.
               apexSocket.addEventListener("securityError",ApexSocketFailure);
               apexSocket.addEventListener(flash.events.ProgressEvent.SOCKET_DATA,ApexSocketData);
               apexSocket.timeout=1500;
               apexAwaiting="connect";
               apexSocket.connect("127.0.0.1",8021);
               return;
            }
            if(apexBoundSim!="" && apexBoundSim!=simId) {
               ApexResetSocket(); return;
            }
            if(apexSocketActive && apexNonce.length==64 && apexAwaiting=="") {
               apexAwaiting="poll";
               ApexSocketSend("POLL|"+apexNonce);
            }
         } catch(tickError:Error) { ApexSocketFailure(tickError); }
      }

      private function ApexSocketConnect(message:Object=null) : void
      {
         try {
            var native:Object=CommunicationManager.CallGameService("CASGetSimInfo",null,true);
            var simId:String=native ? String(native.simId) : "";
            if(!/^[1-9][0-9]{0,19}$/.test(simId)) throw new Error("Native CAS has no selected Sim");
            apexSocketActive=true; apexBoundSim=simId; apexAwaiting="hello";
            ApexSocketSend("HELLO|"+simId);
         } catch(connectError:Error) { ApexSocketFailure(connectError); }
      }

      private function ApexSocketFailure(message:Object=null) : void
      {
         apexSocketError=message==null ? "CAS socket disconnected" : String(message);
         ApexResetSocket();
      }

      private function ApexSocketSend(payload:String) : void
      {
         var bytes:flash.utils.ByteArray=new flash.utils.ByteArray();
         bytes.writeUTFBytes(payload);
         if(bytes.length<1 || bytes.length>131072) throw new Error("CAS socket frame exceeds limit");
         apexSocket.writeUTFBytes(("00000000"+bytes.length).substr(-8));
         apexSocket.writeBytes(bytes,0,bytes.length);
         apexSocket.flush();
      }

      private function ApexSocketData(message:Object=null) : void
      {
         try {
            var available:uint=apexSocket.bytesAvailable;
            if(available>131080 || apexFrame.length+available>131080)
               throw new Error("CAS socket receive buffer exceeds limit");
            var chunk:String=apexSocket.readUTFBytes(available);
            for(var p:int=0;p<chunk.length;++p)
               if(chunk.charCodeAt(p)>127) throw new Error("CAS command frame must contain ASCII only");
            apexFrame+=chunk;
            while(true) {
               if(apexExpected<0) {
                  if(apexFrame.length<8) return;
                  var header:String=apexFrame.substr(0,8);
                  if(!/^[0-9]{8}$/.test(header)) throw new Error("Invalid CAS frame length");
                  apexExpected=int(header);
                  if(apexExpected<1 || apexExpected>131072) throw new Error("CAS frame length exceeds limit");
                  apexFrame=apexFrame.substr(8);
               }
               if(apexFrame.length<apexExpected) return;
               var payload:String=apexFrame.substr(0,apexExpected);
               apexFrame=apexFrame.substr(apexExpected); apexExpected=-1;
               if(apexAwaiting=="hello") {
                  if(!/^HELLO\|[0-9a-f]{64}$/.test(payload)) throw new Error("Invalid CAS session nonce");
                  apexNonce=payload.substr(6); apexAwaiting="";
               } else if(apexAwaiting=="poll") {
                  if(payload=="WAIT") { apexAwaiting=""; }
                  else {
                     if(payload.length>512 || payload.split("|").length!=7)
                        throw new Error("Invalid semantic CAS command frame");
                     for(var c:int=0;c<payload.length;++c)
                        if(payload.charCodeAt(c)<32 || payload.charCodeAt(c)>126)
                           throw new Error("CAS command must contain printable ASCII");
                     apexWire=payload; apexReceiving=true;
                     // Keep the poll lease occupied until the native result's
                     // ACK has itself been acknowledged by the owning server.
                     ApexExecute();
                  }
               } else if(apexAwaiting=="ack") {
                  if(payload!="ACK|"+apexAckId) throw new Error("CAS result acknowledgement differs");
                  apexAckId=""; apexAwaiting="";
               } else throw new Error("Unsolicited CAS transport frame");
            }
         } catch(frameError:Error) { ApexSocketFailure(frameError); }
      }

      private function ApexSocketReply(id:String, reply:String) : void
      {
         apexAckId=id; apexAwaiting="ack";
         ApexSocketSend("ACK|"+apexNonce+"|"+id+"|"+reply);
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
         // Native OutfitType defines 0..13. Normal swim/hot/cold categories
         // are 9/10/11, not 5/6/7. This getter accepts a category and does not
         // select it; preserve all raw slot metadata, including future fields.
         var plannedOutfits:Array=[];
         for(var outfitCategory:int=0;outfitCategory<=13;outfitCategory++) {
            var plannedData:* = null; var plannedQuery:String="returned-null"; var plannedError:String="";
            try {
               plannedData=CommunicationManager.CallGameService("CasGetPlannedOutfits",outfitCategory);
               if(plannedData!=null) plannedQuery="returned-value";
            } catch(outfitError:Error) { plannedQuery="failed"; plannedError=outfitError.message; }
            plannedOutfits.push({category:outfitCategory,supported:plannedData!=null,data:plannedData,
               query:plannedQuery,error:plannedError});
         }
         var hairSwatches:* = null; var hairSelected:* = null; var hairQuery:String="returned-null";
         try {
            hairSwatches=CommunicationManager.CallGameService("CasGetSwatchColorList",2);
            hairSelected=CommunicationManager.CallGameService("CasGetSwatchColorSelected",2);
            if(hairSwatches is Array) hairQuery="returned-value";
         } catch(swatchError:Error) { hairQuery="failed"; }
         return {protocol:1,scope:"native-cas-client",sim:CommunicationManager.CallGameService("CASGetSimInfo",null,true),
            menu_state:this.mCurrState,panel_visible:this.mCurrentPanel!=null && this.mCurrentPanel.visible,
            outfit:CommunicationManager.CallGameService("CasGetCurrSimOutfitSlot"),
            selected:CommunicationManager.CallGameService("GetCatalogItemsSelectedWithModifiers",{state:this.mCurrState}),
            hair_color:hairSelected,hair_selected_swatch_id:hairSelected,hair_swatches:hairSwatches,
            hair_swatch_query:hairQuery,planned_outfits:plannedOutfits,planned_outfits_scope:"slot-metadata-only",catalogs:catalogs};
      }

      private function ApexExecute(message:Object=null) : void
      {
         if(!apexReceiving) return;
         apexReceiving=false;
         var fields:Array=apexWire.split("|");
         if(fields.length!=7 || String(fields[0]).length!=32) return;
         var id:String=fields[0];
         if(id==apexLastId) {
            ApexSocketReply(id,apexLastReply); return;
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
            } else if(operation=="outfit" || operation=="outfit-add") {
               var planned:Object=CommunicationManager.CallGameService("CasGetPlannedOutfits",category);
               if(category<0 || category>13 || !planned || !(planned.outfit_list is Array))
                  throw new Error("Native CAS outfit metadata is unavailable; no outfit generated");
               var previousCount:int=planned.outfit_list.length;
               if(operation=="outfit-add") {
                  if(index!=previousCount || !(planned.max_outfits is int) || previousCount>=int(planned.max_outfits))
                     throw new Error("CAS outfit creation requires the next available append slot; no outfit generated");
                  reply.mutation_started=true;
                  CommunicationManager.CallGameService("CasAddPlannedOutfit",{outfit_type:category,outfit_index:index});
                  var added:Object=CommunicationManager.CallGameService("CasGetPlannedOutfits",category);
                  if(!added || !(added.outfit_list is Array) || added.outfit_list.length!=previousCount+1)
                     throw new Error("Native CAS did not read back exactly one appended outfit");
               } else if(index<0 || index>=previousCount) {
                  throw new Error("CAS outfit does not exist; no outfit generated");
               }
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
               if(!product) {
                  var products:Array=CommunicationManager.CallGameService("GetCatalogVariantItems",value) as Array;
                  if(products) for each(var variantProduct:Object in products)
                     if(variantProduct && String(variantProduct.data_id)==value) product=variantProduct;
               }
               reply.requested_product=product;
               if(!product) throw new Error("Native CAS catalog item is unavailable");
               var expectedBodyType:int=state==MenuState.CLOTHING_HAIR ? CASBodyType.HAIR :
                  (state==MenuState.CLOTHING_TOPS ? CASBodyType.UPPERBODY :
                  (state==MenuState.CLOTHING_BOTTOMS ? CASBodyType.LOWERBODY :
                  (state==MenuState.CLOTHING_FULLBODY ? CASBodyType.FULLBODY : CASBodyType.SHOES)));
               if(!("body_type" in product) || int(product.body_type)!=expectedBodyType)
                  throw new Error("Native catalog item's body type differs from the requested panel; no item changed");
               var family:Object=CommunicationManager.CallGameService("GetCatalogColorFamilies",
                  {base:String(product.data_id),simId:"0",targetSimId:"0"});
               reply.color_family=family;
               var exactVariant:Object=null; var variantMatches:int=0;
               if(family && family.mItems is Array) {
                  for each(var variant:Object in family.mItems)
                     if(variant && String(variant.dataID)==value) { exactVariant=variant; variantMatches++; }
               }
               if(variantMatches!=1)
                  throw new Error("Choose one exact returned catalog swatch dataID; base/ambiguous variant requests are not changed");
               var exactModifiers:Object={
                  data_id:value,slider_mouse_up:true,
                  hue_range_modifier:("hue_range_modifier" in exactVariant ? Number(exactVariant.hue_range_modifier) : 0),
                  opacity_range_modifier:("opacity_range_modifier" in exactVariant ? Number(exactVariant.opacity_range_modifier) : 1),
                  saturation_range_modifier:("saturation_range_modifier" in exactVariant ? Number(exactVariant.saturation_range_modifier) : 0),
                  value_range_modifier:("value_range_modifier" in exactVariant ? Number(exactVariant.value_range_modifier) : 0)};
               if(!isFinite(exactModifiers.hue_range_modifier) || !isFinite(exactModifiers.opacity_range_modifier) ||
                  !isFinite(exactModifiers.saturation_range_modifier) || !isFinite(exactModifiers.value_range_modifier))
                  throw new Error("Native catalog modifiers are not finite; no item changed");
               reply.mutation_started=true;
               CommunicationManager.CallGameService("SetCatalogSlotSelected",exactModifiers);
               // Hair selection may preserve the previous head color by choosing
               // another CASP variation. Explicitly apply the requested variant's
               // freshly returned swatch rather than accepting that substitution.
               if(state==MenuState.CLOTHING_HAIR) {
                  var freshHairSwatches:Array=CommunicationManager.CallGameService("CasGetSwatchColorList",2) as Array;
                  if(!freshHairSwatches) throw new Error("Native hair swatches are unavailable after item selection");
                  var exactHairSwatch:Object=null; var hairMatches:int=0;
                  for each(var hairSwatch:Object in freshHairSwatches)
                     if(hairSwatch && String(hairSwatch.dataID)==value) { exactHairSwatch=hairSwatch; hairMatches++; }
                  if(hairMatches!=1 || !("color" in exactHairSwatch))
                     throw new Error("Requested hair swatch is unavailable/ambiguous after native item selection");
                  CommunicationManager.CallGameService("CasSetSwatchColorSelected",{
                     dataId:exactHairSwatch.dataID,swatchType:2,colorId:exactHairSwatch.color,furColors:null,
                     value_range_modifier:("value_range_modifier" in exactHairSwatch ? exactHairSwatch.value_range_modifier : 0)});
                  if(String(CommunicationManager.CallGameService("CasGetSwatchColorSelected",2))!=value)
                     throw new Error("Native CAS did not read back the exact requested hair swatch");
               }
               CommunicationManager.SendUIMessage("CASRefreshActiveCatalog");
               var selected:Array=CommunicationManager.CallGameService("GetCatalogItemsSelectedWithModifiers",{state:state}) as Array;
               var matched:Boolean=false;
               for each(var selectedItem:Object in selected)
                  if(String(selectedItem.dataID)==value) matched=true;
               if(!matched) throw new Error("Native CAS did not read back the requested catalog item");
            } else if(operation=="hair-swatch") {
               var swatches:Array=CommunicationManager.CallGameService("CasGetSwatchColorList",2) as Array;
               if(!swatches) throw new Error("Native hair swatches are unavailable; no color changed");
               var chosenSwatch:Object=null; var swatchMatches:int=0;
               for each(var swatch:Object in swatches)
                  if(swatch && String(swatch.dataID)==value) { chosenSwatch=swatch; swatchMatches++; }
               if(swatchMatches!=1 || !("color" in chosenSwatch))
                  throw new Error("Choose one exact returned hair swatch dataID; no color changed");
               var swatchValue:Number=("value_range_modifier" in chosenSwatch ? Number(chosenSwatch.value_range_modifier) : 0);
               if(!isFinite(swatchValue)) throw new Error("Native hair swatch modifier is not finite; no color changed");
               reply.mutation_started=true;
               CommunicationManager.CallGameService("CasSetSwatchColorSelected",{
                  dataId:chosenSwatch.dataID,swatchType:2,colorId:chosenSwatch.color,furColors:null,value_range_modifier:swatchValue});
               CommunicationManager.SendUIMessage("CASRefreshActiveCatalog");
               if(String(CommunicationManager.CallGameService("CasGetSwatchColorSelected",2))!=value)
                  throw new Error("Native CAS did not read back the exact requested hair swatch");
            } else if(operation=="undo" || operation=="redo") {
               var before:Object=ApexSnapshot();
               CommunicationManager.SendUIMessage("CASPreventToggleReset");
               reply.mutation_started=true;
               CommunicationManager.CallGameService(operation=="undo" ? "CasNavigationUndo" : "CasNavigationRedo",null,true);
               CommunicationManager.SendUIMessage("CASRefreshActiveCatalog");
               if(ApexEncode(before)==ApexEncode(ApexSnapshot()))
                  throw new Error("Native history operation produced no observable client change");
            } else if(operation!="status") throw new Error("Unsupported semantic CAS operation");
            reply.client=ApexSnapshot();
            if(operation=="outfit-add") reply.client.outfit_created={before_count:previousCount,after_count:added.outfit_list.length};
            reply.ok=true;
         } catch(error:Error) {
            reply.ok=false;
            reply.message=error.message;
            if(reply.mutation_started) {
               try { reply.client=ApexSnapshot(); }
               catch(snapshotError:Error) { reply.client_snapshot_error=snapshotError.message; }
            }
         }
         apexLastId=id;
         try {
            apexLastReply=ApexEncode(reply);
            var encoded:flash.utils.ByteArray=new flash.utils.ByteArray();
            encoded.writeUTFBytes("ACK|"+apexNonce+"|"+id+"|"+apexLastReply);
            if(encoded.length>131072) throw new Error("CAS response exceeds limit; no partial inventory returned");
         } catch(encodeError:Error) {
            apexLastReply=ApexEncode({ok:false,protocol:1,scope:"native-cas-client",cas_request_id:id,
               mutation_started:reply.mutation_started===true,message:String(encodeError)});
         }
         ApexSocketReply(id,apexLastReply);
      }
