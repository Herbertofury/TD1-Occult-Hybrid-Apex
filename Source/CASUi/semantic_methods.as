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
      private var apexHelloPending:Boolean = false;
      private var apexSocketError:String = "";
      private var apexPendingFields:Array;
      private var apexPendingReply:Object;
      private var apexPendingContext:Object;
      private var apexReadbackTick:int = -1;
      private var apexPendingPhase:int = 0;
      private var apexClaimNonce:String = "";
      private var apexTicking:Boolean = false;
      private var apexOwnerFeed:Object;
      private var apexOwnerFeedSequence:int = 0;
      private var apexOwnerSession:int = 0;
      private var apexOwnerFeedListener:Boolean = false;
      private var apexOwnerResetListener:Boolean = false;

      private function ApexInitialize() : void
      {
         // A missing/unsupported intrinsic must not escape the game's native
         // initializer. CAS disconnects its Python Distributor client, so this
         // transport is driven exclusively by native UI events and its timer.
         try {
            ApexDisconnect();
            apexWire=""; apexReceiving=false; apexLastId=""; apexLastReply="";
            apexPendingFields=null; apexPendingReply=null; apexPendingContext=null;
            apexReadbackTick=-1; apexPendingPhase=0; apexClaimNonce="";
            apexTicking=false;
            apexDisconnected=false; apexSocketError="";
            if(apexOwnerSession>=2147483647) throw new Error("CAS owner observation session exhausted");
            apexOwnerSession++;
            apexOwnerFeed={delivered:false,complete:false,sequence:apexOwnerFeedSequence,
               selected_index:-1,selected_layer:-1,pairs:[],error:"No paired feed delivered after listener registration"};
            // The installed selector owns the SkewerData class mapping. Do not
            // replace that mapping or manufacture a native refresh/delivery.
            apexOwnerFeedListener=AddMessageListener("CASRefreshSimIcons",ApexObserveOwnerFeed);
            apexOwnerResetListener=AddMessageListener("CASClearSimsForReset",ApexInvalidateOwnerFeed);
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
         // Losing the owner after intent must never arm/replay a CAS commit
         // under a replacement nonce. Retain the issued identity as unresolved.
         if(apexPendingPhase==5 || apexPendingPhase==6) {
            apexPendingPhase=8; apexReadbackTick=-1;
         }
         if(apexSocket) {
            apexSocket.removeEventListener(flash.events.Event.CONNECT,ApexSocketConnect);
            apexSocket.removeEventListener(flash.events.Event.CLOSE,ApexSocketFailure);
            apexSocket.removeEventListener(flash.events.IOErrorEvent.IO_ERROR,ApexSocketFailure);
            apexSocket.removeEventListener(flash.events.ProgressEvent.SOCKET_DATA,ApexSocketData);
            try { apexSocket.close(); } catch(closeError:Error) { }
         }
         apexSocket=null; apexSocketActive=false; apexHelloPending=false; apexNonce=""; apexBoundSim="";
         apexAwaiting=""; apexAckId=""; apexFrame=""; apexExpected=-1;
         apexReceiving=false; apexWire="";
         // Keep the last UUID/reply across connection failures. A lost ACK
         // never makes a delivered mutation eligible for blind execution again.
      }

      private function ApexDisconnect() : void
      {
         apexDisconnected=true;
         if(apexOwnerFeedListener) {
            RemoveMessageListener("CASRefreshSimIcons",ApexObserveOwnerFeed);
            apexOwnerFeedListener=false;
         }
         if(apexOwnerResetListener) {
            RemoveMessageListener("CASClearSimsForReset",ApexInvalidateOwnerFeed);
            apexOwnerResetListener=false;
         }
         apexOwnerFeed=null;
         if(apexTimer) {
            apexTimer.stop();
            apexTimer.removeEventListener(flash.events.TimerEvent.TIMER,ApexTick);
            apexTimer=null;
         }
         ApexResetSocket();
         apexPendingFields=null; apexPendingReply=null; apexPendingContext=null;
         apexReadbackTick=-1; apexPendingPhase=0; apexClaimNonce="";
      }

      private function ApexTick(message:Object=null) : void
      {
         if(apexDisconnected || apexTicking || apexPendingPhase==7 || apexPendingPhase==8) return;
         apexTicking=true;
         try {
            // GFx implements Timer.currentCount, but explicitly does not support
            // Socket.securityError. Bound every outstanding stage using the
            // existing state string: stage|timer-count. Never register an
            // unsupported native event or await its callback indefinitely.
            if(apexAwaiting!="") {
               var waiting:Array=apexAwaiting.split("|");
               if(waiting.length!=2 || !/^[0-9]+$/.test(String(waiting[1])))
                  throw new Error("Invalid CAS transport wait state");
               var waitLimit:int=waiting[0]=="connect" ? 6 : 40;
               if(int(apexTimer.currentCount)-int(waiting[1])>=waitLimit) {
                  ApexSocketFailure("CAS socket "+waiting[0]+" timed out"); return;
               }
            }
            var native:Object=CommunicationManager.CallGameService("CASGetSimInfo",null,true);
            var simId:String=native ? String(native.simId) : "";
            native=null;
            if(!/^[1-9][0-9]{0,19}$/.test(simId)) return;
            if(apexSocket==null) {
               apexSocket=new flash.net.Socket();
               apexSocket.addEventListener(flash.events.Event.CONNECT,ApexSocketConnect);
               apexSocket.addEventListener(flash.events.Event.CLOSE,ApexSocketFailure);
               apexSocket.addEventListener(flash.events.IOErrorEvent.IO_ERROR,ApexSocketFailure);
               apexSocket.addEventListener(flash.events.ProgressEvent.SOCKET_DATA,ApexSocketData);
               apexSocket.timeout=1500;
               apexBoundSim=simId; apexHelloPending=false;
               apexAwaiting="connect|"+apexTimer.currentCount;
               apexSocket.connect("127.0.0.1",8021);
               return;
            }
            if(apexBoundSim!="" && apexBoundSim!=simId) {
               ApexResetSocket(); return;
            }
            if(apexHelloPending) {
               // The real CONNECT callback queues only. This Timer's fresh
               // exact-Sim read owns handshake production and consumes once.
               if(apexAwaiting.split("|")[0]!="connect" || apexBoundSim!=simId || !apexSocket.connected)
                  throw new Error("Queued CAS handshake lost its exact socket/Sim ownership");
               apexHelloPending=false; apexSocketActive=true;
               apexAwaiting="hello|"+apexTimer.currentCount;
               ApexSocketSend("HELLO|"+simId);
               return;
            }
            // Socket callbacks only queue. All native writes and their later
            // readback run from this supported UI Timer, never reentrantly
            // inside SocketData. Claim/result survive a transport reset.
            if(apexPendingPhase==6 && apexPendingFields!=null && int(apexTimer.currentCount)>=apexReadbackTick) {
               ApexAccept(); return;
            }
            if(apexPendingPhase>=1 && apexPendingPhase<=4 && apexPendingFields!=null && int(apexTimer.currentCount)>=apexReadbackTick) {
               ApexReadback(); return;
            }
            if(apexReceiving && apexSocketActive && apexNonce.length==64) {
               ApexExecute(); return;
            }
            if(apexSocketActive && apexNonce.length==64 && apexAwaiting=="") {
               apexAwaiting="poll|"+apexTimer.currentCount;
               ApexSocketSend("POLL|"+apexNonce);
            }
         } catch(tickError:Error) { ApexSocketFailure(tickError); }
         finally { apexTicking=false; }
      }

      private function ApexSocketConnect(message:Object=null) : void
      {
         // The listener belongs to the exact Socket constructed by ApexTick.
         // No native getter or transport send may run in this event callback.
         if(apexDisconnected || apexSocket==null || message==null || message.currentTarget!==apexSocket ||
            apexAwaiting.split("|")[0]!="connect" || apexHelloPending) return;
         apexHelloPending=true;
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
               var stage:String=apexAwaiting.split("|")[0];
               if(stage=="hello") {
                  if(!/^HELLO\|[0-9a-f]{64}$/.test(payload)) throw new Error("Invalid CAS session nonce");
                  apexNonce=payload.substr(6); apexAwaiting="";
               } else if(stage=="poll") {
                  if(payload=="WAIT") { apexAwaiting=""; }
                  else {
                     if(payload.length>512 || payload.split("|").length!=7)
                        throw new Error("Invalid semantic CAS command frame");
                     for(var c:int=0;c<payload.length;++c)
                        if(payload.charCodeAt(c)<32 || payload.charCodeAt(c)>126)
                           throw new Error("CAS command must contain printable ASCII");
                     if(apexReceiving || apexPendingFields!=null)
                        throw new Error("CAS command arrived while a claim is outstanding");
                     apexWire=payload; apexReceiving=true;
                     // Keep the poll lease occupied until the native result's
                     // ACK has itself been acknowledged by the owning server.
                     apexAwaiting="execute|"+apexTimer.currentCount;
                  }
               } else if(stage=="ack") {
                  if(payload!="ACK|"+apexAckId) throw new Error("CAS result acknowledgement differs");
                  if(apexPendingPhase==5 && apexPendingFields!=null &&
                     String(apexPendingFields[0])==apexAckId && apexClaimNonce==apexNonce) {
                     // Only the owning server's durable intent ACK arms a
                     // commit. SocketData performs no native work itself.
                     apexPendingPhase=6; apexReadbackTick=int(apexTimer.currentCount)+1;
                     apexAwaiting="commit|"+apexTimer.currentCount;
                  } else apexAwaiting="";
                  apexAckId="";
               } else throw new Error("Unsolicited CAS transport frame");
            }
         } catch(frameError:Error) { ApexSocketFailure(frameError); }
      }

      private function ApexSocketReply(id:String, reply:String) : void
      {
         apexAckId=id; apexAwaiting="ack|"+apexTimer.currentCount;
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

      private function ApexOwnerFeedRow(raw:Object) : Object
      {
         // Only primitives from the inspected SimLayerSkewerData schema.
         // This helper and its callback never call a native service.
         if(raw==null || !(raw.simId is String) ||
            !/^(0|[1-9][0-9]{0,19})$/.test(raw.simId) ||
            !(raw.index is int) || !(raw.occultType is int) ||
            !(raw.allOccultTypes is int) || !(raw.occultLayer is int) ||
            !(raw.selected is Boolean)) return null;
         return {sim_id:String(raw.simId),index:int(raw.index),occult_type:int(raw.occultType),
            all_occult_types:int(raw.allOccultTypes),occult_layer:int(raw.occultLayer),
            selected:Boolean(raw.selected)};
      }

      private function ApexObserveOwnerFeed(message:Object) : void
      {
         if(apexDisconnected || !apexOwnerFeedListener) return;
         var baseData:Array=null; var alternateData:Array=null; var raw:Object=null;
         var copied:Object={delivered:true,complete:false,sequence:apexOwnerFeedSequence,
            selected_index:-1,selected_layer:-1,pairs:[],error:"Invalid native paired feed"};
         try {
            if(apexOwnerFeedSequence>=2147483647) throw new Error("CAS owner feed sequence exhausted");
            copied.sequence=++apexOwnerFeedSequence;
            if(message==null || !(message.sim_data is Array) || !(message.sim_occult_data is Array) ||
               !(message.selected_sim is int) || !(message.selected_layer is int))
               throw new Error("Native paired feed fields are unavailable");
            baseData=message.sim_data; alternateData=message.sim_occult_data;
            copied.selected_index=int(message.selected_sim); copied.selected_layer=int(message.selected_layer);
            if(baseData.length==0 || baseData.length>32 || alternateData.length>32 ||
               baseData.length!=alternateData.length) throw new Error("Native paired feed exceeds or lacks bounded parallel rows");
            copied.complete=true; copied.error="";
            for(var i:int=0;i<baseData.length;i++) {
               raw=baseData[i]; var base:Object=ApexOwnerFeedRow(raw); raw=null;
               raw=alternateData[i]; var alternate:Object=ApexOwnerFeedRow(raw); raw=null;
               copied.pairs.push({index:i,base:base,alternate:alternate});
               if(base==null || alternate==null || base.sim_id=="0" || alternate.sim_id=="0") {
                  copied.complete=false; copied.error="A paired identity is missing or a native zero placeholder";
               }
            }
            if(copied.selected_index<0 || copied.selected_index>=baseData.length ||
               (copied.selected_layer!=0 && copied.selected_layer!=1)) {
               copied.complete=false; copied.error="Native paired feed selection is unavailable";
            }
         } catch(feedError:Error) {
            copied.complete=false; copied.error=feedError.message;
         } finally {
            // Never retain the globally dispatched Olympus/native payload.
            raw=null; baseData=null; alternateData=null; message=null;
            apexOwnerFeed=copied;
         }
      }

      private function ApexInvalidateOwnerFeed(message:Object=null) : void
      {
         if(apexDisconnected || !apexOwnerResetListener) return;
         if(apexOwnerFeedSequence<2147483647) apexOwnerFeedSequence++;
         apexOwnerFeed={delivered:false,complete:false,sequence:apexOwnerFeedSequence,
            selected_index:-1,selected_layer:-1,pairs:[],error:"Native paired feed was cleared for reset; awaiting actual delivery"};
         message=null;
      }

      private function ApexOwnerSimRow(raw:Object) : Object
      {
         if(raw==null || !(raw.simId is String) || !(raw.householdId is String) ||
            !/^[1-9][0-9]{0,19}$/.test(raw.simId) || !/^[1-9][0-9]{0,19}$/.test(raw.householdId) ||
            !(raw.occultType is int) || !(raw.allOccultTypes is int) || !(raw.occultLayer is int)) return null;
         return {sim_id:String(raw.simId),household_id:String(raw.householdId),occult_type:int(raw.occultType),
            all_occult_types:int(raw.allOccultTypes),occult_layer:int(raw.occultLayer)};
      }


      private function ApexFormSelectionContext(simId:String, householdId:String, expectedLayer:int,
         formFlags:int, nativeSession:int) : Object
      {
         // A same-ID paired feed permits navigation only. It never proves the
         // native wrapper relationship and cannot authorize alternate acceptance.
         if(!apexTicking || apexDisconnected || !apexSocketActive || apexClaimNonce!=apexNonce ||
            nativeSession!=apexOwnerSession || nativeSession<=0 || (expectedLayer!=0 && expectedLayer!=1))
            throw new Error("CAS form selection lacks its exact Timer/session/peer ownership");
         var native:Object=null; var selector:Object=null; var fresh:Object=null;
         try {
            native=CommunicationManager.CallGameService("CASGetSimInfo",null,true);
            var selected:Object=ApexOwnerSimRow(native); native=null;
            if(selected==null || selected.sim_id!=simId || selected.household_id!=householdId ||
               selected.occult_layer!=expectedLayer)
               throw new Error("CAS form selection selected Sim/household/current layer differs");
            var mode:* = CommunicationManager.CallGameService("CasGetCASEditMode");
            var family:* = CommunicationManager.CallGameService("CasIsNewFamily");
            var area:Object=CommunicationManager.CallGameService("CasIsEnteredFromPlayArea");
            if(!(mode is int) || int(mode)!=7 || family!==false || area==null || area.result!==true)
               throw new Error("CAS form selection requires mode7, existing family and explicit Live entry");
            area=null;
            selector=CommunicationManager.CallUIService("ApexReadOwnerPairFeed",null);
            if(selector==null || !(selector.protocol is int) || int(selector.protocol)!=1 ||
               selector.scope!="native-selector-owner-pair-view" || selector.service_registered!==true ||
               selector.reset_listener_registered!==true || selector.mapping_verified!==false ||
               selector.alternate_accept_authorized!==false)
               throw new Error("CAS form selection read-only selector service is unavailable");
            var raw:Object=selector.raw_feed; var retained:Object=selector.retained;
            if(raw==null || raw.source!="native-selector-raw-entry-observer" || raw.before_native_handler!==true ||
               raw.delivered!==true || raw.complete!==true || !(raw.sequence is int) || int(raw.sequence)<=0 ||
               retained==null || retained.source!="native-selector-retained-filtered-feed" ||
               retained.available!==true || retained.complete!==true || !(raw.pairs is Array) || !(retained.pairs is Array) ||
               raw.pairs.length==0 || raw.pairs.length>32 || raw.pairs.length!=retained.pairs.length ||
               !(raw.base_row_count is int) || raw.base_row_count!=raw.pairs.length ||
               !(raw.alternate_row_count is int) || raw.alternate_row_count!=raw.pairs.length)
               throw new Error("CAS form selection requires a complete bounded raw/retained pair");
            var selectedIndex:int=int(retained.selected_index);
            if(!(retained.selected_index is int) || selectedIndex<0 || selectedIndex>=retained.pairs.length ||
               !(raw.selected_index is int) || raw.selected_index!=selectedIndex ||
               !(raw.selected_layer is int) || (raw.selected_layer!=0 && raw.selected_layer!=1) ||
               !(retained.selected_layer is int) || retained.selected_layer!=expectedLayer || retained.selected_sim_id!=simId)
               throw new Error("CAS form selection cannot choose another native Sim/index");
            var projection:Object=null; var matches:int=0;
            for(var i:int=0;i<retained.pairs.length;i++) {
               var rawPair:Object=raw.pairs[i]; var pair:Object=retained.pairs[i];
               if(rawPair==null || pair==null || !(rawPair.index is int) || rawPair.index!=i ||
                  !(pair.index is int) || pair.index!=i) throw new Error("CAS paired row position differs");
               var copied:Object={index:i};
               for each(var side:String in ["base","alternate"]) {
                  var row:Object=pair[side]; var rawRow:Object=rawPair[side];
                  var layer:int=side=="base" ? 0 : 1;
                  if(row==null || rawRow==null || !(row.sim_id is String) ||
                     !/^[1-9][0-9]{0,19}$/.test(row.sim_id) || !(row.index is int) || row.index!=i ||
                     !(row.occult_type is int) || !(row.all_occult_types is int) || !(row.occult_layer is int) ||
                     row.occult_layer!=layer || !(row.selected is Boolean) || !(rawRow.selected is Boolean) ||
                     !(rawRow.index is int) || !(rawRow.occult_type is int) || !(rawRow.all_occult_types is int) ||
                     !(rawRow.occult_layer is int) || rawRow.sim_id!==row.sim_id || rawRow.index!==row.index ||
                     rawRow.occult_type!==row.occult_type || rawRow.all_occult_types!==row.all_occult_types ||
                     rawRow.occult_layer!==row.occult_layer) throw new Error("CAS raw/retained pair identity/context differs");
                  copied[side]={sim_id:String(row.sim_id),index:int(row.index),occult_type:int(row.occult_type),
                     all_occult_types:int(row.all_occult_types),occult_layer:int(row.occult_layer)};
               }
               if(pair.base.sim_id==simId || pair.alternate.sim_id==simId) {
                  matches++;
                  if(i!=selectedIndex || pair.base.sim_id!=simId || pair.alternate.sim_id!=simId)
                     throw new Error("CAS form selection requires one same-original-ID pair, not a wrapper guess");
               }
               if(i==selectedIndex) projection=copied;
            }
            pair=retained.pairs[selectedIndex];
            if(matches!=1 || pair.base.occult_type!=1 ||
               (pair.alternate.occult_type!=2 && pair.alternate.occult_type!=4 && pair.alternate.occult_type!=8 &&
                pair.alternate.occult_type!=16 && pair.alternate.occult_type!=32 && pair.alternate.occult_type!=64) ||
               pair.base.all_occult_types!=pair.alternate.all_occult_types || pair.base.all_occult_types<0 ||
               (pair.base.all_occult_types & 1)==0 || (pair.base.all_occult_types & pair.alternate.occult_type)==0)
               throw new Error("CAS form selection lacks the observed Human/alternate form context");
            var current:Object=expectedLayer==0 ? pair.base : pair.alternate;
            var other:Object=expectedLayer==0 ? pair.alternate : pair.base;
            if(current.selected!==true || other.selected!==false || current.occult_type!=selected.occult_type ||
               current.all_occult_types!=selected.all_occult_types || current.occult_layer!=selected.occult_layer)
               throw new Error("CAS form selection fresh selected context differs from retained selection");
            var targetLayer:int=formFlags==1 ? 0 : 1;
            var target:Object=targetLayer==0 ? pair.base : pair.alternate;
            if(target.occult_type!=formFlags) throw new Error("Requested form is absent from the actual base/alternate pair");
            native=CommunicationManager.CallGameService("CASGetSimInfo",null,true);
            fresh=ApexOwnerSimRow(native); native=null;
            if(fresh==null || ApexEncode(fresh)!=ApexEncode(selected))
               throw new Error("CAS form selection selected context changed during preflight");
            return {native_session:nativeSession,sim_id:simId,household_id:householdId,selected_index:selectedIndex,
               selected_layer:expectedLayer,target_layer:targetLayer,form_flags:formFlags,feed_sequence:int(raw.sequence),
               pair_json:ApexEncode(projection)};
         } finally { native=null; selector=null; fresh=null; }
      }

      private function ApexOwnerHouseholdProbe(raw:Object) : Object
      {
         // The household getter's raw rows are not proven to carry the full
         // selected-Sim schema. Preserve absence and primitive types exactly.
         var result:Object={fields:{},field_names:[],field_names_truncated:false};
         var names:Array=["simId","householdId","occultType","allOccultTypes","occultLayer",
            "speciesType","age","isNew","sim_id","household_id"];
         var value:* = null;
         try {
            for each(var name:String in names) {
               value=raw!=null ? raw[name] : undefined;
               var primitive:Boolean=value==null || value is String || value is Boolean || value is Number;
               var bounded:Boolean=!(value is String && String(value).length>128) &&
                  !(value is Number && !isFinite(Number(value)));
               result.fields[name]={present:value!==undefined,type:typeof value,primitive:primitive,bounded:bounded,
                  value:primitive && bounded && value!==undefined ? value : null};
               value=null;
            }
            if(raw!=null) for(var field:String in raw) {
               if(result.field_names.length>=32 || field.length>64) { result.field_names_truncated=true; break; }
               result.field_names.push(field);
            }
         } finally { raw=null; value=null; }
         return result;
      }

      private function ApexOwnerObservation() : Object
      {
         var feed:Object=apexOwnerFeed;
         var result:Object={protocol:1,scope:"native-cas-paired-feed-read-only",session:apexOwnerSession,
            listener_registered:apexOwnerFeedListener && apexOwnerResetListener,feed:feed,selected_query:"not-queried",
            household_query:"not-queried",selected:null,household:[],stable:false,complete:false,
            household_primitives:[],selector_query:"not-queried",selector_feed:null,
            error:"Owner observation requires the native Timer readback"};
         if(!apexTicking || apexDisconnected) return result;
         var nativeSelected:Object=null; var nativeHousehold:Array=null; var nativeRow:Object=null;
         var fresh:Object=null;
         try {
            nativeSelected=CommunicationManager.CallGameService("CASGetSimInfo",null,true);
            result.selected=ApexOwnerSimRow(nativeSelected); nativeSelected=null;
            result.selected_query=result.selected!=null ? "returned-value" : "returned-null-or-invalid";
            nativeHousehold=CommunicationManager.CallGameService("CasGetHouseholdSims") as Array;
            if(nativeHousehold==null) result.household_query="returned-null";
            else if(nativeHousehold.length==0 || nativeHousehold.length>32) result.household_query="invalid-bound";
            else {
               result.household_query="returned-value";
               for(var i:int=0;i<nativeHousehold.length;i++) {
                  nativeRow=nativeHousehold[i]; result.household_primitives.push(ApexOwnerHouseholdProbe(nativeRow));
                  var row:Object=ApexOwnerSimRow(nativeRow); nativeRow=null;
                  if(row==null) result.household_query="invalid-record";
                  else result.household.push(row);
               }
            }
            nativeHousehold=null;
            try {
               result.selector_feed=CommunicationManager.CallUIService("ApexReadOwnerPairFeed",null);
               result.selector_query=result.selector_feed!=null ? "returned-value" : "returned-null";
            } catch(selectorError:Error) { result.selector_query="failed"; }
            nativeSelected=CommunicationManager.CallGameService("CASGetSimInfo",null,true);
            fresh=ApexOwnerSimRow(nativeSelected); nativeSelected=null;
            result.stable=feed===apexOwnerFeed && fresh!=null && result.selected!=null &&
               ApexEncode(fresh)==ApexEncode(result.selected);
            result.error="Paired feed delivery or fresh selected/household records are incomplete";
            if(result.stable && apexOwnerFeedListener && apexOwnerResetListener && feed!=null && feed.delivered && feed.complete &&
               result.household_query=="returned-value") {
               var pair:Object=feed.pairs[feed.selected_index];
               var selectedFeed:Object=feed.selected_layer==0 ? pair.base : pair.alternate;
               result.complete=selectedFeed!=null && selectedFeed.sim_id==fresh.sim_id &&
                  feed.selected_layer==fresh.occult_layer && selectedFeed.occult_type==fresh.occult_type &&
                  selectedFeed.all_occult_types==fresh.all_occult_types;
               if(result.complete) result.error="";
               else result.error="Fresh selected Sim does not match the native paired selection";
            }
         } catch(observeError:Error) {
            result.complete=false; result.stable=false; result.error=observeError.message;
         } finally {
            nativeSelected=null; nativeHousehold=null; nativeRow=null; fresh=null;
         }
         return result;
      }

      private function ApexSnapshot(includeCatalogMetadata:Boolean=false) : Object
      {
         var catalogs:Array=[];
         var catalogMetadata:Array=[]; var catalogMetadataSeen:Object={};
         var catalogMetadataComplete:Boolean=includeCatalogMetadata;
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
            // Selected dataID is a native catalog identity, not a CASP TGI.
            // Keep these optional annotations separate from exact equipped
            // records/history. No panel selection or native mutation occurs.
            // Native inventory must not perform an unverified bulk product
            // lookup. The current native engine has crashed during this
            // optional path. Equipped records and history remain independent.
            // Only a separately verified explicit lookup may opt into it.
            if(includeCatalogMetadata && items is Array) for each(var selectedItem:Object in items) {
               if(!selectedItem || !(selectedItem.dataID is String) ||
                  !new RegExp("^[1-9][0-9]{0,19}$").test(selectedItem.dataID)) {
                  catalogMetadataComplete=false; continue;
               }
               var catalogId:String=String(selectedItem.dataID);
               if(catalogMetadataSeen[catalogId]) continue;
               if(catalogMetadata.length>=128) { catalogMetadataComplete=false; continue; }
               catalogMetadataSeen[catalogId]=true;
               var annotation:Object={data_id:catalogId,query:"returned-null",source:"native:GetCatalogItem",
                  name:null,name_query:"unavailable",name_source:"native:LocKey",
                  native_image_uri:null,image_query:"not-returned",image_source:"native:GetCatalogItem.image",
                  raw_json:null,error:"",name_error:""};
               var product:Object=null; var productTitle:LocKey=null;
               try {
                  product=CommunicationManager.CallGameService("GetCatalogItem",catalogId) as Object;
                  if(product!=null) {
                     annotation.query="returned-value";
                     // Serialize before localization and release all returned
                     // native objects before the next getter/native phase.
                     annotation.raw_json=ApexEncode(product);
                     if(String(annotation.raw_json).length>65536) throw new Error("Native catalog product exceeds the annotation bound");
                     if(product.image is String && String(product.image).length>0 && String(product.image).length<=512) {
                        annotation.native_image_uri=String(product.image); annotation.image_query="native-uri";
                     }
                     if(product.title!=null) try {
                        productTitle=new LocKey(product.title);
                        var localizedName:String=productTitle.toString();
                        if(localizedName!=null && localizedName.length>0 && localizedName.length<=2048) {
                           annotation.name=localizedName; annotation.name_query="localized-title";
                        } else annotation.name_query="empty-title";
                     } catch(titleFailure:Error) {
                        annotation.name_query="failed"; annotation.name_error=titleFailure.message;
                     }
                  }
               } catch(metadataFailure:Error) {
                  annotation.query="failed"; annotation.error=metadataFailure.message;
                  annotation.raw_json=null; annotation.name=null; annotation.name_query="unavailable";
                  annotation.native_image_uri=null; annotation.image_query="not-returned";
               }
               productTitle=null; product=null; selectedItem=null;
               catalogMetadata.push(annotation);
            }
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
         // These are the inspected native navigation/configuration getters.
         // Preserve raw return types and distinguish unavailable from false/0.
         // Context is evidence only; it does not authorize a CAS exit/commit.
         var nativeContext:Object={};
         var contextGetters:Object={edit_mode:"CasGetCASEditMode",new_family:"CasIsNewFamily",
            entered_from_play_area:"CasIsEnteredFromPlayArea",forced_full_edit:"CasIsForcedFullEditingEnabled"};
         for(var contextName:String in contextGetters) {
            var contextValue:* = null; var contextQuery:String="returned-null"; var contextError:String="";
            try {
               if(contextName=="forced_full_edit")
                  contextValue=CommunicationManager.CallGameService("CasIsForcedFullEditingEnabled",null,true);
               else contextValue=CommunicationManager.CallGameService(contextGetters[contextName]);
               if(contextValue!=null) contextQuery="returned-value";
            } catch(contextFailure:Error) { contextQuery="failed"; contextError=contextFailure.message; }
            nativeContext[contextName]={value:contextValue,query:contextQuery,error:contextError};
         }
         return {protocol:1,scope:"native-cas-client",sim:CommunicationManager.CallGameService("CASGetSimInfo",null,true),
            menu_state:this.mCurrState,panel_visible:this.mCurrentPanel!=null && this.mCurrentPanel.visible,
            outfit:CommunicationManager.CallGameService("CasGetCurrSimOutfitSlot"),
            selected:CommunicationManager.CallGameService("GetCatalogItemsSelectedWithModifiers",{state:this.mCurrState}),
            hair_color:hairSelected,hair_selected_swatch_id:hairSelected,hair_swatches:hairSwatches,
            hair_swatch_query:hairQuery,planned_outfits:plannedOutfits,planned_outfits_scope:"slot-metadata-only",
            native_context:nativeContext,catalogs:catalogs,catalog_metadata:catalogMetadata,
            owner_pair_observation:ApexOwnerObservation(),
            catalog_metadata_complete:catalogMetadataComplete,catalog_metadata_scope:"native-catalog-identities-only",
            catalog_metadata_query:includeCatalogMetadata ? "explicit-lookup" : "disabled-pending-native-contract-proof"};
      }

      private function ApexExecute(message:Object=null) : void
      {
         if(!apexReceiving) return;
         apexReceiving=false;
         var fields:Array=apexWire.split("|");
         if(fields.length!=7 || String(fields[0]).length!=32) return;
         var id:String=fields[0];
         if(id==apexLastId) {
            if(apexLastReply!="") ApexSocketReply(id,apexLastReply);
            else apexSocketError="Duplicate CAS claim is still unresolved";
            return;
         }
         // Claim before the first native call. A socket reset must never turn
         // an executed mutation into a fresh request eligible for replay.
         apexLastId=id; apexLastReply=""; apexClaimNonce=apexNonce;
         var reply:Object={ok:false,protocol:1,scope:"native-cas-client",cas_request_id:id};
         var operation:String=fields[2]; reply.operation=operation;
         if(operation=="accept") {
            // Even a first-getter/preflight failure must be a typed terminal
            // refusal rather than an unacknowledgeable generic error receipt.
            reply.lifecycle_stage="accept-result"; reply.commit_attempted=false;
            reply.commit_submitted=false; reply.ui_transition_verified=false;
         }
         apexPendingFields=fields; apexPendingReply=reply; apexPendingContext={};
         apexPendingPhase=1; apexReadbackTick=int(apexTimer.currentCount)+1;
         apexAwaiting="readback|"+apexTimer.currentCount;
         try {
            var native:Object=CommunicationManager.CallGameService("CASGetSimInfo",null,true);
            if(!native || String(native.simId)!=String(fields[1])) throw new Error("CAS selected Sim differs from request");
            native=null;
            var state:int=int(fields[3]);
            var category:int=int(fields[4]); var index:int=int(fields[5]); var value:String=fields[6];
            if(operation=="form-select") {
               if(!/^(1|2|4|8|16|32|64)$/.test(String(fields[3])) ||
                  !/^[01]$/.test(String(fields[4])) || !/^[1-9][0-9]{0,9}$/.test(String(fields[5])) ||
                  String(index)!=String(fields[5]) || !/^[1-9][0-9]{0,19}$/.test(value))
                  throw new Error("CAS form selection requires exact form/current-layer/session/household fields");
               var selectionBefore:Object=ApexFormSelectionContext(String(fields[1]),value,category,state,index);
               apexPendingContext.selection_before=selectionBefore;
               if(selectionBefore.selected_layer!=selectionBefore.target_layer) {
                  // Claim/phase are consumed before either native write. The
                  // index is the already selected same-original-ID pair only.
                  var selectionIndex:int=int(selectionBefore.selected_index);
                  var selectAlternate:Boolean=int(selectionBefore.target_layer)>0;
                  reply.mutation_started=true;
                  var nativeSelection:* = CommunicationManager.CallGameService("CasSelectSim",selectionIndex);
                  if(!(nativeSelection is Boolean) || nativeSelection!==true)
                     throw new Error("Native CasSelectSim refused or returned an untyped result; no second write");
                  CommunicationManager.CallGameService("CasSelectOccultForm",{select:selectAlternate});
               }
            } else if(operation=="panel") {
               reply.mutation_started=true;
               HandleContextMenuSetMenuState({menuState:state,skipAnim:true,setZoomState:true});
            } else if(operation=="outfit" || operation=="outfit-add") {
               var planned:Object=CommunicationManager.CallGameService("CasGetPlannedOutfits",category);
               if(category<0 || category>13 || !planned || !(planned.outfit_list is Array))
                  throw new Error("Native CAS outfit metadata is unavailable; no outfit generated");
               var previousCount:int=planned.outfit_list.length;
               if(operation=="outfit-add") {
                  if(!(planned.max_outfits is int) || previousCount>=int(planned.max_outfits) || previousCount<0 || previousCount>=5)
                     throw new Error("CAS outfit creation requires an available append slot; no outfit generated");
                  // The typed outfit-add wire has no caller index. Its zero
                  // placeholder must never be confused with the append slot.
                  index=previousCount;
                  apexPendingContext.before_count=previousCount;
                  apexPendingContext.index=index;
                  apexPendingPhase=3;
                  planned=null;
                  reply.mutation_started=true;
                  CommunicationManager.CallGameService("CasAddPlannedOutfit",{outfit_type:category,outfit_index:index});
               } else {
                  if(index<0 || index>=previousCount)
                     throw new Error("CAS outfit does not exist; no outfit generated");
                  planned=null;
                  reply.mutation_started=true;
                  CommunicationManager.CallGameService("CasSelectPlannedOutfit",{outfit_type:category,outfit_index:index});
                  CommunicationManager.SendUIMessage("CASRefreshActiveCatalog");
               }
            } else if(operation=="select") {
               // Presets, skin tones, featured looks and layered products have
               // different native contracts. Do not guess their write payload.
               if(state!=MenuState.CLOTHING_HAIR && state!=MenuState.CLOTHING_TOPS && state!=MenuState.CLOTHING_BOTTOMS &&
                  state!=MenuState.CLOTHING_FULLBODY && state!=MenuState.CLOTHING_SHOES && state!=MenuState.CLOTHING_ACCESSORIES_EARRINGS)
                  throw new Error("Native selection for this panel requires its typed preset/layer contract; no item changed");
               if(MenuState.SupportsLayerList(state)) throw new Error("Layered selection requires an explicit layer; no item changed");
               HandleContextMenuSetMenuState({menuState:state,skipAnim:true,setZoomState:true});
               var product:Object=CommunicationManager.CallGameService("GetCatalogItem",value);
               if(!product) {
                  var products:Array=CommunicationManager.CallGameService("GetCatalogVariantItems",value) as Array;
                  if(products) for each(var variantProduct:Object in products)
                     if(variantProduct && String(variantProduct.data_id)==value) product=variantProduct;
               }
               reply.requested_product_json=ApexEncode(product);
               if(!product) throw new Error("Native CAS catalog item is unavailable");
               var expectedBodyType:int=state==MenuState.CLOTHING_HAIR ? CASBodyType.HAIR :
                  (state==MenuState.CLOTHING_TOPS ? CASBodyType.UPPERBODY :
                  (state==MenuState.CLOTHING_BOTTOMS ? CASBodyType.LOWERBODY :
                  (state==MenuState.CLOTHING_FULLBODY ? CASBodyType.FULLBODY :
                   (state==MenuState.CLOTHING_ACCESSORIES_EARRINGS ? CASBodyType.EARRINGS : CASBodyType.SHOES))));
               if(!("body_type" in product) || int(product.body_type)!=expectedBodyType)
                  throw new Error("Native catalog item's body type differs from the requested panel; no item changed");
               var family:Object=CommunicationManager.CallGameService("GetCatalogColorFamilies",
                  {base:String(product.data_id),simId:"0",targetSimId:"0"});
               reply.color_family_json=ApexEncode(family);
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
               // Native getter records are not retained across an editor write.
               // Evidence is detached as JSON text; the write payload is owned.
               product=null; products=null; variantProduct=null;
               family=null; exactVariant=null; variant=null;
               reply.mutation_started=true;
               CommunicationManager.CallGameService("SetCatalogSlotSelected",exactModifiers);
               // Defer fresh swatch discovery until the next native UI tick.
               // Native product/color callers do not send a global catalog
               // refresh; duplicating that event can reenter native UI updates.
               if(state==MenuState.CLOTHING_HAIR) apexPendingPhase=2;
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
               var swatchPayload:Object={dataId:String(chosenSwatch.dataID),swatchType:2,
                  colorId:chosenSwatch.color,furColors:null,value_range_modifier:swatchValue};
               chosenSwatch=null; swatches=null; swatch=null;
               reply.mutation_started=true;
               CommunicationManager.CallGameService("CasSetSwatchColorSelected",swatchPayload);

            } else if(operation=="accept") {
               if(state!=0 || category!=0 || index!=0)
                  throw new Error("CAS accept has no caller-supplied mode/transition parameters");
               if(!/^[1-9][0-9]{0,19}$/.test(value))
                  throw new Error("CAS accept requires its bound original household identity; no intent prepared");
               // Read-only preflight/intent is completed on a later tick.
               // SaveAndExitCAS is exclusively the ACK-armed Timer phase.
               apexPendingPhase=4;
               reply.lifecycle_stage="accept-intent"; reply.commit_attempted=false;
               reply.commit_submitted=false; reply.ui_transition_verified=false;
            } else if(operation=="undo" || operation=="redo") {
               apexPendingContext.history_before=ApexEncode(ApexSnapshot());
               // Mirror the inspected native caller. PC uses only the toggle
               // reset message; controller paths have their own pre/post events.
               if(SystemUtils.UsingController)
                  CommunicationManager.SendUIMessage(operation=="undo" ? "CASPrePerformUndo" : "CASPerformRedo");
               else CommunicationManager.SendUIMessage("CASPreventToggleReset");
               reply.mutation_started=true;
               CommunicationManager.CallGameService(operation=="undo" ? "CasNavigationUndo" : "CasNavigationRedo",null,true);
               if(SystemUtils.UsingController)
                  CommunicationManager.SendUIMessage(operation=="undo" ? "CASPostPerformUndo" : "CASPostPerformRedo");
            } else if(operation!="status") throw new Error("Unsupported semantic CAS operation");
         } catch(error:Error) {
            reply.ok=false; reply.message=error.message;
            if(String(fields[2])=="accept") {
               reply.operation="accept"; reply.lifecycle_stage="accept-result";
               reply.commit_attempted=false; reply.commit_submitted=false; reply.ui_transition_verified=false;
            }
         }
         // Every postcondition, including failed writes, is read on a later
         // Timer tick. No bulk snapshot/readback immediately follows a mutation.
      }

      private function ApexReadback() : void
      {
         if(apexPendingFields==null || int(apexTimer.currentCount)<apexReadbackTick) return;
         var fields:Array=apexPendingFields;
         var reply:Object=apexPendingReply;
         var context:Object=apexPendingContext;
         var operation:String=fields[2]; var state:int=int(fields[3]);
         var category:int=int(fields[4]); var index:int=int(fields[5]); var value:String=fields[6];
         if((operation=="undo" || operation=="redo") && context.history_before is String)
            reply.history_before_json=String(context.history_before);
         var selectedSimMatches:Boolean=false; var writeStarted:Boolean=false;
         try {
            var native:Object=CommunicationManager.CallGameService("CASGetSimInfo",null,true);
            selectedSimMatches=native && String(native.simId)==String(fields[1]);
            native=null;
            if(!selectedSimMatches) throw new Error("CAS selected Sim changed before native readback");
            if(!("message" in reply) && apexPendingPhase==2) {
               // Item selection settles before querying that hairstyle's swatches.
               var freshHairSwatches:Array=CommunicationManager.CallGameService("CasGetSwatchColorList",2) as Array;
               if(!freshHairSwatches) throw new Error("Native hair swatches are unavailable after item selection");
               var exactHairSwatch:Object=null; var hairMatches:int=0;
               for each(var hairSwatch:Object in freshHairSwatches)
                  if(hairSwatch && String(hairSwatch.dataID)==value) { exactHairSwatch=hairSwatch; hairMatches++; }
               if(hairMatches!=1 || !("color" in exactHairSwatch))
                  throw new Error("Requested hair swatch is unavailable/ambiguous after native item selection");
               var hairValue:Number=("value_range_modifier" in exactHairSwatch ? Number(exactHairSwatch.value_range_modifier) : 0);
               if(!isFinite(hairValue)) throw new Error("Native hair swatch modifier is not finite");
               var hairPayload:Object={dataId:String(exactHairSwatch.dataID),swatchType:2,
                  colorId:exactHairSwatch.color,furColors:null,value_range_modifier:hairValue};
               exactHairSwatch=null; freshHairSwatches=null; hairSwatch=null;
               // Advance before calling native code: even a nested callback
               // cannot see this sub-mutation as eligible to execute again.
               apexPendingPhase=1; apexReadbackTick=int(apexTimer.currentCount)+1;
               apexAwaiting="readback|"+apexTimer.currentCount;
               writeStarted=true;
               CommunicationManager.CallGameService("CasSetSwatchColorSelected",hairPayload);
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
            reply.client=ApexSnapshot();
            if(!("message" in reply)) {
               if(operation=="accept") {
                  if(!(reply.client.sim.occultLayer is int) || int(reply.client.sim.occultLayer)!=0)
                     throw new Error("Alternate or untyped CAS layers lack a verified original owner mapping; no intent prepared");
                  var casContext:Object=reply.client.native_context;
                  if(!casContext || !casContext.edit_mode || casContext.edit_mode.query!="returned-value" ||
                     !(casContext.edit_mode.value is int) || int(casContext.edit_mode.value)!=7 ||
                     !casContext.new_family || casContext.new_family.query!="returned-value" || casContext.new_family.value!==false ||
                     !casContext.entered_from_play_area || casContext.entered_from_play_area.query!="returned-value" ||
                     !casContext.entered_from_play_area.value || casContext.entered_from_play_area.value.result!==true)
                     throw new Error("CAS accept requires exact single-Sim mode7, an existing family and entry from Live mode");
                  if(!(reply.client.sim.householdId is String) || !/^[1-9][0-9]{0,19}$/.test(reply.client.sim.householdId))
                     throw new Error("Native CAS accept lacks an exact household identity; no intent prepared");
                  if(String(reply.client.sim.householdId)!=value)
                     throw new Error("Native CAS accept household differs from its bound original request; no intent prepared");
                  context.household_id=value;
               }
               if(operation=="form-select") {
                  var beforeSelection:Object=context.selection_before;
                  if(beforeSelection==null) throw new Error("CAS form selection has no retained original intent");
                  var afterSelection:Object=ApexFormSelectionContext(String(fields[1]),value,
                     int(beforeSelection.target_layer),state,index);
                  if(afterSelection.native_session!=beforeSelection.native_session || afterSelection.sim_id!=beforeSelection.sim_id ||
                     afterSelection.household_id!=beforeSelection.household_id || afterSelection.selected_index!=beforeSelection.selected_index ||
                     afterSelection.form_flags!=beforeSelection.form_flags || afterSelection.target_layer!=beforeSelection.target_layer ||
                     afterSelection.pair_json!=beforeSelection.pair_json || afterSelection.feed_sequence<beforeSelection.feed_sequence)
                     throw new Error("CAS form selection pair/session changed before next-tick readback");
                  reply.form_selection={native_session:int(afterSelection.native_session),sim_id:String(afterSelection.sim_id),
                     household_id:String(afterSelection.household_id),selected_index:int(afterSelection.selected_index),
                     expected_layer:category,target_layer:int(afterSelection.target_layer),form_flags:state,
                     selection_changed:category!=int(afterSelection.target_layer),selection_verified:true,
                     mapping_verified:false,alternate_accept_authorized:false};
               }
               if(operation=="panel" || operation=="select") {
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
                  var selected:Array=reply.client.selected as Array;
                  var matched:Boolean=false;
                  if(selected) for each(var selectedItem:Object in selected)
                     if(String(selectedItem.dataID)==value) matched=true;
                  if(!matched) throw new Error("Native CAS did not read back the requested catalog item");
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
            if(operation=="accept") {
               reply.lifecycle_stage="accept-result"; reply.commit_attempted=false;
               reply.commit_submitted=false; reply.ui_transition_verified=false;
            }
            if(writeStarted) {
               apexPendingPhase=1; apexReadbackTick=int(apexTimer.currentCount)+1;
               apexAwaiting="readback|"+apexTimer.currentCount;
               return;
            }
            if(reply.mutation_started && selectedSimMatches && reply.client==null) {
               try { reply.client=ApexSnapshot(); }
               catch(snapshotError:Error) { reply.client_snapshot_error=snapshotError.message; }
            }
         }
         ApexComplete();
      }

      private function ApexComplete() : void
      {
         var reply:Object=apexPendingReply; var id:String=String(apexPendingFields[0]);
         try {
            apexLastReply=ApexEncode(reply);
            var encoded:flash.utils.ByteArray=new flash.utils.ByteArray();
            encoded.writeUTFBytes("ACK|"+apexClaimNonce+"|"+id+"|"+apexLastReply);
            if(encoded.length>131072) throw new Error("CAS response exceeds limit; no partial inventory returned");
         } catch(encodeError:Error) {
            // A bounded failure ACK must never arm an accept intent whose
            // successful snapshot could not be encoded/delivered completely.
            reply.ok=false;
            var boundedFailure:Object={ok:false,protocol:1,scope:"native-cas-client",cas_request_id:id,
               mutation_started:reply.mutation_started===true,message:String(encodeError)};
            if(reply.operation=="accept") {
               boundedFailure.operation="accept"; boundedFailure.lifecycle_stage="accept-result";
               boundedFailure.commit_attempted=false; boundedFailure.commit_submitted=false;
               boundedFailure.ui_transition_verified=false;
            }
            apexLastReply=ApexEncode(boundedFailure);
         }
         // Release only after the complete result is cached. A replacement peer
         // cannot acknowledge or re-execute another peer's claimed mutation.
         var owner:String=apexClaimNonce;
         if(reply.operation=="accept" && reply.ok===true && reply.lifecycle_stage=="accept-intent") {
            // The cached intent is plain UTF-8 text. Drop the raw client/reply
            // before any later native commit; preserve only identity/owner.
            apexPendingReply=null;
            apexPendingContext={household_id:String(apexPendingContext.household_id)};
            apexReadbackTick=-1; apexPendingPhase=5;
            if(apexSocketActive && apexNonce==owner) ApexSocketReply(id,apexLastReply);
            else apexPendingPhase=8;
            return;
         }
         apexPendingFields=null; apexPendingReply=null; apexPendingContext=null;
         apexReadbackTick=-1; apexPendingPhase=0; apexClaimNonce="";
         if(apexSocketActive && apexNonce==owner) ApexSocketReply(id,apexLastReply);
      }

      private function ApexAccept() : void
      {
         if(apexPendingPhase!=6 || apexPendingFields==null || apexClaimNonce!=apexNonce ||
            !apexSocketActive || int(apexTimer.currentCount)<apexReadbackTick) return;
         // Cache only owned identity/primitive values before native code can
         // synchronously unload this widget and clear its Timer/Socket fields.
         var id:String=String(apexPendingFields[0]); var simId:String=String(apexPendingFields[1]);
         var owner:String=apexClaimNonce;
         var expectedHousehold:String=String(apexPendingFields[6]);
         var preparedHousehold:String=apexPendingContext ? String(apexPendingContext.household_id) : "";
         var reply:Object={ok:false,protocol:1,scope:"native-cas-client",cas_request_id:id,operation:"accept",
            lifecycle_stage:"accept-result",commit_attempted:false,commit_submitted:false,ui_transition_verified:false};
         var commitAccepted:Boolean=false;
         try {
            var sim:Object=CommunicationManager.CallGameService("CASGetSimInfo",null,true);
            var observedId:String=sim ? String(sim.simId) : "";
            var observedHousehold:String=sim && sim.householdId is String ? String(sim.householdId) : "";
            var observedLayer:* = sim ? sim.occultLayer : null;
            sim=null;
            var editMode:* = CommunicationManager.CallGameService("CasGetCASEditMode");
            var newFamily:* = CommunicationManager.CallGameService("CasIsNewFamily");
            var playArea:Object=CommunicationManager.CallGameService("CasIsEnteredFromPlayArea");
            var fromLive:Boolean=playArea!=null && playArea.result===true; playArea=null;
            if(observedId!=simId || expectedHousehold=="" || preparedHousehold!=expectedHousehold || observedHousehold!=expectedHousehold ||
               !(observedLayer is int) || int(observedLayer)!=0 ||
               !(editMode is int) || int(editMode)!=7 || newFamily!==false || !fromLive)
               throw new Error("Native CAS accept preconditions changed after intent acknowledgement; no commit submitted");
            // The native class already imports this external class. Use its
            // imported QName; FFDec treats a fully qualified dotted expression
            // here as a runtime lookup for an object named "olympus".
            CASTelemetryExtension.ReportHouseholdSimIDs();
            if(apexPendingPhase!=6 || apexClaimNonce!=owner || apexNonce!=owner || !apexSocketActive) {
               apexPendingPhase=8; apexReadbackTick=-1;
               return;
            }
            // Consume BEFORE the native call. A thrown exception, unload or
            // disconnect cannot turn this accepted intent into another commit.
            apexPendingFields=null; apexPendingReply=null; apexPendingContext=null;
            apexPendingPhase=7; apexReadbackTick=-1; apexClaimNonce="";
            reply.commit_attempted=true;
            var accepted:* = CommunicationManager.CallGameService("SaveAndExitCAS",{bValidateExistingSimTraits:false});
            if(accepted===true) {
               commitAccepted=true;
               // CAS_TO_LIVE=32 is pinned in TransitionScreenMode. Do not read
               // this widget's state or attempt a client snapshot after success.
               CommunicationManager.SendUIMessage("ShowTransitionScreen",{mode:32});
               return;
            }
            if(accepted===false) {
               reply.commit_accepted=false;
               reply.message="Native SaveAndExitCAS did not accept the prepared existing-Sim commit";
            } else {
               reply.commit_accepted=null; reply.commit_outcome="unresolved";
               reply.message="Native SaveAndExitCAS returned an unverified non-Boolean outcome; commit is not repeated";
            }
         } catch(acceptError:Error) {
            // Once native save accepted, a transition delivery error is an
            // unresolved lifecycle outcome, never a false "not committed" ACK.
            if(commitAccepted) return;
            reply.message=acceptError.message;
            if(reply.commit_attempted===true) {
               reply.commit_accepted=null; reply.commit_outcome="unresolved";
            }
         }
         // Failed native/preflight paths retain the original UUID and nonce.
         // Successful completion is established by the host's Live observer.
         apexPendingFields=null; apexPendingReply=null; apexPendingContext=null;
         apexPendingPhase=reply.commit_outcome=="unresolved" ? 7 : 0;
         apexReadbackTick=-1; apexClaimNonce="";
         apexLastReply=ApexEncode(reply);
         if(apexSocketActive && apexNonce==owner) ApexSocketReply(id,apexLastReply);
      }
