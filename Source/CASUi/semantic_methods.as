// Apex-owned methods inserted into the installed build's CASCustomizerMain.
// Typed data only over a fixed loopback socket. No code fetch/evaluation,
// arbitrary URLs, mouse input, or executable offsets.
      private var apexWire:String = "";
      private var apexReceiving:Boolean = false;
      private var apexLastId:String = "";
      private var apexLastReply:String = "";
      private var apexSocket:flash.net.Socket;
      // Retain the old path for build-time comparison; matching candidates
      // require the native pipe and never instantiate a GFx Socket.
      private var apexNativeTransportRequired:Boolean = true;
      private var apexNativeChannel:String = "";
      private var apexNativeConnected:Boolean = false;
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
      private var apexSocketResetPending:Boolean = false;
      private var apexOutboundFrame:String = "";
      private var apexOutboundPending:Boolean = false;
      private var apexPendingFields:Array;
      private var apexPendingReply:Object;
      private var apexPendingContext:Object;
      private var apexReadbackTick:int = -1;
      private var apexPendingPhase:int = 0;
      private var apexClaimNonce:String = "";
      private var apexTicking:Boolean = false;
      // Only the original accepted intent owns this short readiness continuation.
      // No idle poller, replay UUID, arbitrary delay or input suppression.
      private var apexAcceptWait:Object=null;
      private var apexAcceptInput:Boolean=false;
      private var apexAcceptStage:flash.display.Stage=null;
      private var apexPresentationQueued:Boolean=false;
      private var apexPresentationStarted:int=-1;
      private var apexPresentationMilliseconds:int=-1;
      private var apexPresentationFrames:int=0;
      private var apexPresentationListener:Boolean=false;
      private var apexPresentationSim:String="";
      private var apexPresentationFirstFrameDelay:int=-1;
      private var apexPresentationPrimeMs:int=0;
      private var apexPresentationCatalogMs:int=0;
      private var apexPresentationMenuMs:int=0;
      private var apexPresentationStateMs:int=0;
      private var apexPresentationPairMs:int=0;
      private var apexPresentationIconsMs:int=0;
      private var apexPresentationGraphicsMs:int=0;

      private function ApexPresentationReady() : Boolean
      {
         return apexNativeChannel!="" && (apexNativeConnected && apexNonce.length==64 || apexFormsLocalCatalog) && apexBoundSim!="" &&
            this.mCurrSimInfo!=null && this.mCurrSimInfo.simId===apexBoundSim &&
            (apexPresentationSim=="" || apexPresentationSim===apexBoundSim) &&
            apexFormsRoot!=null && apexFormsSelectedId!="" && apexFormsNativeState=="bound" &&
            apexFormsDesiredId=="" && apexFormsOwnerTotal>=0 &&
            apexFormsOwners.length==apexFormsOwnerTotal &&
            apexPairSignature==apexBoundSim+"|"+apexFormsSelectedId+"|"+apexFormsNativeGeneration;
      }

      private function ApexPresentationNotify(message:Object) : void
      {
         // EA's own typed delivery remains authoritative. This observer only
         // queues a later frame; no native calls or mutation in the callback.
         if(apexDisconnected || !apexPresentationListener || message==null ||
            !(message.simId is String) || !/^[1-9][0-9]{0,19}$/.test(message.simId) ||
            message.simId===apexBoundSim && (apexPresentationSim=="" || apexPresentationSim===apexBoundSim)) return;
         // Repeated deliveries of the same incoming member retain the first
         // timestamp, including time spent waiting for an existing CLI claim.
         if(apexPresentationSim!==message.simId || apexPresentationStarted<0 || apexPresentationMilliseconds>=0) {
            apexPresentationStarted=getTimer();apexPresentationMilliseconds=-1;apexPresentationFrames=0;
            apexPresentationFirstFrameDelay=-1;apexPresentationPrimeMs=0;apexPresentationCatalogMs=0;apexPresentationMenuMs=0;
            apexPresentationStateMs=0;apexPresentationPairMs=0;apexPresentationIconsMs=0;apexPresentationGraphicsMs=0;
         }
         apexPresentationSim=String(message.simId);
         // Returning to the still-bound member cancels the older pending
         // target; its existing controls need no rebuild or delayed handshake.
         if(ApexPresentationReady()) {
            apexPresentationMilliseconds=0;ApexPresentationStop();return;
         }
         ApexPresentationSchedule();
      }

      private function ApexPresentationStop() : void
      {
         removeEventListener(flash.events.Event.ENTER_FRAME,ApexPresentationFrame);
         apexPresentationQueued=false;
      }

      private function ApexPresentationSchedule() : void
      {
         if(apexDisconnected || apexPresentationQueued || ApexPresentationReady()) return;
         if(apexPresentationStarted<0) {
            apexPresentationStarted=getTimer();apexPresentationMilliseconds=-1;apexPresentationFrames=0;
         }
         // The ordinary timer remains the fallback for slow/loading peers.
         // Never turn a hidden/idle CAS movie into an unbounded frame poller.
         var elapsed:int=getTimer()-apexPresentationStarted;
         if(elapsed<0 || elapsed>2000) return;
         apexPresentationQueued=true;
         addEventListener(flash.events.Event.ENTER_FRAME,ApexPresentationFrame,false,0,true);
      }

      private function ApexPresentationPrime() : Boolean
      {
         // The delivered selector supplies identity only. OPEN and LOCALOWNERS
         // revalidate the exact native group, member, scope and bound model.
         // No CLI claim or pending player action may be advanced here.
         if(apexDisconnected || apexTicking || apexPendingFields!=null || apexReceiving || apexPendingPhase!=0 ||
            apexMoleculeIntent!=null || apexFormsNativeIntent!=null || apexFormsDesiredId!="" || apexPairIntent!=null ||
            this.mCurrSimInfo==null || !(this.mCurrSimInfo.simId is String) ||
            !/^[1-9][0-9]{0,19}$/.test(this.mCurrSimInfo.simId) ||
            !(this.mCurrSimInfo.householdId is String) || !/^[1-9][0-9]{0,19}$/.test(this.mCurrSimInfo.householdId)) return false;
         if(apexBoundSim!="" && apexBoundSim!==this.mCurrSimInfo.simId) {ApexResetSocket();return false;}
         if(apexNativeChannel=="") ApexNativeOpen(String(this.mCurrSimInfo.simId));
         if(apexNativeChannel=="") return false;
         var catalogStarted:int=getTimer();var catalogReady:Boolean=ApexFormsTryLocalCatalog();
         apexPresentationCatalogMs+=getTimer()-catalogStarted;
         if(!catalogReady) return false;
         apexFormsHousehold=String(this.mCurrSimInfo.householdId);
         var delivered:Object=ApexFormsObservedSim();if(delivered==null) return false;
         var menuStarted:int=getTimer();ApexFormsOwnedTick(delivered);
         apexPresentationMenuMs+=getTimer()-menuStarted;return ApexPresentationReady();
      }

      private function ApexPresentationFrame(event:flash.events.Event) : void
      {
         ApexPresentationStop();
         if(apexDisconnected) return;
         if(apexPresentationFirstFrameDelay<0 && apexPresentationStarted>=0) apexPresentationFirstFrameDelay=getTimer()-apexPresentationStarted;
         if(ApexPresentationReady()) { apexPresentationMilliseconds=getTimer()-apexPresentationStarted;return; }
         try {
            var primeStarted:int=getTimer();var primed:Boolean=ApexPresentationPrime();apexPresentationPrimeMs+=getTimer()-primeStarted;
            if(primed) {apexPresentationFrames++;apexPresentationMilliseconds=getTimer()-apexPresentationStarted;return;}
         } catch(primeFailure:Error) {ApexSocketFailure(primeFailure);return;}
         if(!apexTicking &&
            this.mCurrSimInfo!=null && this.mCurrSimInfo.simId is String &&
            /^[1-9][0-9]{0,19}$/.test(this.mCurrSimInfo.simId)) {
            // Drain an already-owned transport ACK before the next 500ms tick.
            // ApexTick's ENTER_FRAME guard still yields all command execution
            // and readback to the Timer. A completed claim must not starve the
            // incoming member's bounded, read-only bootstrap.
            apexPresentationFrames++;ApexTick(event);
            // The complete menu was staged before CAS from these exact native
            // owner graphs. Render it locally while the independent CLI nonce
            // handshake completes. A claimed command still owns its Timer.
            try {
               if(!apexDisconnected && apexPendingFields==null && !apexReceiving && apexPendingPhase==0 &&
                  ApexFormsTryLocalCatalog()) ApexFormsOwnedTick(ApexFormsObservedSim());
            } catch(localMenuFailure:Error) {ApexSocketFailure(localMenuFailure);}
         }
         if(ApexPresentationReady()) apexPresentationMilliseconds=getTimer()-apexPresentationStarted;
         else ApexPresentationSchedule();
      }

      private var apexOwnerFeed:Object;
      private var apexOwnerFeedSequence:int = 0;
      private var apexOwnerSession:int = 0;
      private var apexOwnerFeedListener:Boolean = false;
      private var apexOwnerResetListener:Boolean = false;
      private var apexMoleculeRegistered:Boolean = false;
      private var apexMoleculeReadRegistered:Boolean = false;
      private var apexMoleculeListener:Boolean = false;
      private var apexMoleculeView:Object;

      private function ApexInitialize() : void
      {
         // A missing/unsupported intrinsic must not escape the game's native
         // initializer. CAS disconnects its Python Distributor client, so this
         // transport is driven exclusively by native UI events and its timer.
         try {
            // Native Initialize arms the hidden grid before initial Sim/data
            // delivery. Preserve only that unstepped bootstrap while resetting
            // transport; ordinary disconnect/unload always disposes the grid.
            var preserveBootstrap:Boolean=apexCatalogGrid!=null && apexCatalogGrid.enabled===true &&
               !apexCatalogGrid.disposed && !apexCatalogGrid.running && apexCatalogGrid.frame===0 &&
               apexCatalogGrid.lease!=null && apexCatalogGrid.lease.root===this &&
               apexCatalogGrid.lease.phase=="bootstrap";
            ApexDisconnect(preserveBootstrap);
            apexNativeTransportRequired=true;apexNativeChannel="";apexNativeConnected=false;
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
            apexPresentationListener=AddMessageListener("CASSetSimInfo",ApexPresentationNotify);
            if(!apexMoleculeRegistered)
               apexMoleculeRegistered=RegisterServiceHandler("ApexMoleculeChooseOccult",ApexMoleculeChooseOccult);
            if(!apexMoleculeReadRegistered)
               apexMoleculeReadRegistered=RegisterServiceHandler("ApexMoleculeReadSelection",ApexMoleculeReadSelection);
            if(!apexPairRegistered)
               apexPairRegistered=RegisterServiceHandler("ApexFormPairPanel",ApexPairPanel);
            ApexMoleculeListen(true);
            ApexCatalogInitialize();
            apexTimer=new flash.utils.Timer(500);
            apexTimer.addEventListener(flash.events.TimerEvent.TIMER,ApexTick);
            apexTimer.start();
            ApexTick();
            ApexPresentationSchedule();
         } catch(startError:Error) {
            apexSocketError=String(startError);
            ApexDisconnect();
         }
      }

      private function ApexResetSocket() : void
      {
         if(apexAcceptWait!=null) ApexAcceptAbort("CAS room transport retired before native acceptance");
         apexSocketResetPending=false;
         if(apexNativeChannel!="") {
            try { ApexNativeExchange("CLOSE|"+apexNativeChannel); } catch(pipeCloseError:Error) { }
            apexNativeChannel="";apexNativeConnected=false;
         }
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
         apexOutboundPending=false;apexOutboundFrame="";
         ApexFormsDispose();
         apexAwaiting=""; apexAckId=""; apexFrame=""; apexExpected=-1;
         apexReceiving=false; apexWire="";
         ApexPresentationStop();
         // Keep the notification timestamp through the new member handshake.
         if(apexPresentationMilliseconds>=0) apexPresentationStarted=-1;
         ApexPresentationSchedule();
         // Keep the last UUID/reply across connection failures. A lost ACK
         // never makes a delivered mutation eligible for blind execution again.
      }

      private function ApexDisconnect(preserveGridBootstrap:Boolean=false) : void
      {
         apexDisconnected=true;
         if(apexPresentationListener) {
            RemoveMessageListener("CASSetSimInfo",ApexPresentationNotify);
            apexPresentationListener=false;
         }
         apexPresentationSim="";apexPresentationStarted=-1;apexPresentationMilliseconds=-1;
         ApexCatalogDispose(preserveGridBootstrap);
         ApexMoleculeListen(false);
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

      private function ApexIdleMemberChanged(nativeNeeded:Boolean) : Boolean
      {
         // A strict bound-form observer rejects a different Sim. Detect that
         // change separately, without hiding it behind the old bound identity.
         // Reconnection still requires a fresh native identity; never select.
         if(nativeNeeded || apexBoundSim=="" || this.mCurrSimInfo==null ||
            !(this.mCurrSimInfo.simId is String) || !/^[1-9][0-9]{0,19}$/.test(this.mCurrSimInfo.simId)) return false;
         return this.mCurrSimInfo.simId!==apexBoundSim;
      }

      private function ApexTick(message:Object=null) : void
      {
         if(apexDisconnected || apexTicking) return;
         apexTicking=true;
         // APEX_TIMER_TRACE_BEGIN tick-begin
         var apexTimerTraceGeneration:int=0;
         if(apexCatalogTrace!=null && apexCatalogTrace.enabled===true) apexTimerTraceGeneration=ApexCatalogTimerStep("tick.enter");
         // APEX_TIMER_TRACE_END tick-begin
         try {
            // Never tear down GFx's native Socket from its own event callback.
            // A failure records intent only; this later Timer owns closure.
            if(apexSocketResetPending) { ApexResetSocket();return; }
            if(apexPendingPhase==9) { ApexAccept();return; }
            // APEX_TIMER_TRACE_BEGIN receive-begin
            if(apexCatalogTrace!=null && apexCatalogTrace.enabled===true && apexCatalogTrace.timer_profile!=null) ApexCatalogTimerStep("receive.enter");
            // APEX_TIMER_TRACE_END receive-begin
            if(apexNativeChannel!="") ApexNativeReceive();
            // APEX_TIMER_TRACE_BEGIN receive-end
            if(apexCatalogTrace!=null && apexCatalogTrace.enabled===true && apexCatalogTrace.timer_profile!=null) ApexCatalogTimerStep("receive.leave");
            // APEX_TIMER_TRACE_END receive-end
            // A bootstrap frame may receive an existing CLI claim, but only
            // the ordinary owned Timer executes that claim and its readback.
            if(message is flash.events.Event && message.type==flash.events.Event.ENTER_FRAME &&
               (apexPendingFields!=null || apexReceiving)) return;
            if(apexPendingPhase==7 || apexPendingPhase==8) return;
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
            // Polling an idle socket needs no native Sim-info allocation.
            // Use the selector's already delivered AS data for idle binding;
            // commands, gestures and their readbacks still get a fresh native
            // identity before they can do any work.
            var physiqueOpen:Boolean=apexPendingFields!=null && String(apexPendingFields[2])=="physique" &&
               apexPendingContext!=null && apexPendingContext.physique_commit_pending===true;
            // CASGetSimInfo can synchronize/replace appearance cache records.
            // An open native slider gesture still owns its preview/undo data.
            // Use the delivered selector identity until its completion returns.
            var nativeNeeded:Boolean=!physiqueOpen && (apexSocket==null && apexNativeChannel=="" || apexHelloPending || apexReceiving ||
               apexPendingFields!=null || apexFormsIntent!=null ||
               apexFormsResult!=null && apexFormsResult.pending===true);
            if(ApexIdleMemberChanged(nativeNeeded)) {ApexResetSocket();return;}
            // APEX_TIMER_TRACE_BEGIN tick-native-begin
            if(nativeNeeded && apexCatalogTrace!=null && apexCatalogTrace.enabled===true && apexCatalogTrace.timer_profile!=null) ApexCatalogTimerStep("native-info.enter");
            // APEX_TIMER_TRACE_END tick-native-begin
            var native:Object=nativeNeeded ? CommunicationManager.CallGameService("CASGetSimInfo",null,true) : null;
            // APEX_TIMER_TRACE_BEGIN tick-native-end
            if(nativeNeeded && apexCatalogTrace!=null && apexCatalogTrace.enabled===true && apexCatalogTrace.timer_profile!=null) ApexCatalogTimerStep("native-info.leave");
            if(apexCatalogTrace!=null && apexCatalogTrace.enabled===true && apexCatalogTrace.timer_profile!=null) ApexCatalogTimerStep("clone.enter");
            // APEX_TIMER_TRACE_END tick-native-end
            var formsSim:Object=nativeNeeded ? ApexClone(native) : ApexFormsObservedSim();
            // APEX_TIMER_TRACE_BEGIN tick-clone-end
            if(apexCatalogTrace!=null && apexCatalogTrace.enabled===true && apexCatalogTrace.timer_profile!=null) ApexCatalogTimerStep("clone.leave");
            // APEX_TIMER_TRACE_END tick-clone-end
            var simId:String=formsSim ? String(formsSim.simId) : apexBoundSim;
            if(nativeNeeded && formsSim!=null) apexFormsHousehold=String(formsSim.householdId);
            native=null;
            if(!/^[1-9][0-9]{0,19}$/.test(simId)) return;
            if(apexSocket==null && apexNativeChannel=="") {
               if(apexNativeTransportRequired) {
                  ApexNativeOpen(simId);return;
               }
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
            if(apexBoundSim!="" && apexBoundSim!=simId && !(apexPendingFields!=null &&
               String(apexPendingFields[2])=="member-select" && apexPendingPhase==1 &&
               apexPendingContext.target_sim_id==simId && apexClaimNonce==apexNonce)) {
               ApexResetSocket(); return;
            }
            if(apexHelloPending) {
               // The real CONNECT callback queues only. This Timer's fresh
               // exact-Sim read owns handshake production and consumes once.
               if(apexAwaiting.split("|")[0]!="connect" || apexBoundSim!=simId ||
                  !(apexNativeChannel!="" ? apexNativeConnected : apexSocket.connected))
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
               // APEX_TIMER_TRACE_BEGIN readback-begin
               if(apexCatalogTrace!=null && apexCatalogTrace.enabled===true && apexCatalogTrace.timer_profile!=null) ApexCatalogTimerStep("readback.enter");
               // APEX_TIMER_TRACE_END readback-begin
               ApexReadback();
               // APEX_TIMER_TRACE_BEGIN readback-end
               if(apexCatalogTrace!=null && apexCatalogTrace.enabled===true && apexCatalogTrace.timer_profile!=null) ApexCatalogTimerStep("readback.leave");
               // APEX_TIMER_TRACE_END readback-end
               return;
            }
            if(apexReceiving && apexSocketActive && apexNonce.length==64) {
               // APEX_TIMER_TRACE_BEGIN execute-begin
               if(apexCatalogTrace!=null && apexCatalogTrace.enabled===true && apexCatalogTrace.timer_profile!=null) ApexCatalogTimerStep("execute.enter");
               // APEX_TIMER_TRACE_END execute-begin
               ApexExecute();
               // APEX_TIMER_TRACE_BEGIN execute-end
               if(apexCatalogTrace!=null && apexCatalogTrace.enabled===true && apexCatalogTrace.timer_profile!=null) ApexCatalogTimerStep("execute.leave");
               // APEX_TIMER_TRACE_END execute-end
               return;
            }
            if(apexSocketActive && apexNonce.length==64 && apexAwaiting=="") {
               // APEX_TIMER_TRACE_BEGIN forms-begin
               if(apexCatalogTrace!=null && apexCatalogTrace.enabled===true && apexCatalogTrace.timer_profile!=null) ApexCatalogTimerStep("forms.enter");
               // APEX_TIMER_TRACE_END forms-begin
               ApexFormsTick(formsSim); formsSim=null;
               // APEX_TIMER_TRACE_BEGIN forms-end
               if(apexCatalogTrace!=null && apexCatalogTrace.enabled===true && apexCatalogTrace.timer_profile!=null) ApexCatalogTimerStep("forms.leave");
               // APEX_TIMER_TRACE_END forms-end
               apexAwaiting="poll|"+apexTimer.currentCount;
               ApexSocketSend("POLL|"+apexNonce);
            }
         } catch(tickError:Error) { ApexSocketFailure(tickError); }
         finally {
            if(apexPresentationStarted>=0 && apexPresentationMilliseconds<0 && ApexPresentationReady())
               apexPresentationMilliseconds=getTimer()-apexPresentationStarted;
            // APEX_TIMER_TRACE_BEGIN tick-end
            if(apexTimerTraceGeneration!=0) ApexCatalogTimerStep("tick.leave",apexTimerTraceGeneration);
            // APEX_TIMER_TRACE_END tick-end
            apexTicking=false;
         }
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
         if(message is flash.events.Event && (apexSocket==null || message.currentTarget!==apexSocket)) return;
         apexSocketError=message==null ? "CAS socket disconnected" : String(message);
         apexSocketResetPending=true;
      }

      private function ApexSocketSend(payload:String) : void
      {
         if(apexOutboundPending) throw new Error("CAS socket still owns its previous unacknowledged frame");
         if(payload.length<1 || payload.length>131072) throw new Error("CAS socket frame exceeds limit");
         for(var i:int=0;i<payload.length;++i)
            if(payload.charCodeAt(i)>127) throw new Error("CAS socket frame must be ASCII encoded");
         // JSON escapes preserve every Unicode value while making byte length
         // equal to String.length. Submit header+body in one native write and
         // retain the complete buffer through the peer's matching response.
         apexOutboundFrame=("00000000"+payload.length).substr(-8)+payload;
         apexOutboundPending=true;
         if(apexNativeChannel!="") {
            if(ApexNativeExchange("WRITE|"+apexNativeChannel+"|"+apexOutboundFrame)!="QUEUED")
               throw new Error("Native CAS frame ownership refused; no replay");
            return;
         }
         apexSocket.writeUTFBytes(apexOutboundFrame);
         apexSocket.flush();
      }

      private function ApexSocketData(message:Object=null) : void
      {
         if(apexSocket==null || message==null || message.currentTarget!==apexSocket) return;
         try {
            var available:uint=apexSocket.bytesAvailable;
            if(available>131080 || apexFrame.length+available>131080)
               throw new Error("CAS socket receive buffer exceeds limit");
            var chunk:String=apexSocket.readUTFBytes(available);
            ApexConsumeFrame(chunk);
         } catch(frameError:Error) { ApexSocketFailure(frameError); }
      }

      private function ApexNativeExchange(command:String) : String
      {
         var response:* = CommunicationManager.CallGameService("GetSimOccult","APEXUI1|"+command,true);
         if(!(response is String)) throw new Error("Matching native CAS pipe is unavailable; no GFx Socket fallback");
         return String(response);
      }

      private function ApexFormsConsumeCatalog(payload:String) : void
      {
         var catalogFields:Array=payload.split("|");
         if(catalogFields.length!=4 || !/^[0-9]+$/.test(catalogFields[1]) || !/^[0-9]+$/.test(catalogFields[2]))
            throw new Error("Invalid native owner catalog page");
         var catalogOffset:int=int(catalogFields[1]);var catalogTotal:int=int(catalogFields[2]);
         if(catalogTotal<1 || catalogTotal>2048 || catalogOffset>apexFormsOwners.length ||
            apexFormsOwnerTotal>=0 && apexFormsOwnerTotal!=catalogTotal) throw new Error("Native owner catalog sequence changed");
         if(catalogOffset<apexFormsOwners.length) {
            if(apexFormsCatalogPages[String(catalogOffset)]!==payload) throw new Error("Late peer form catalogue differs from the prepared native page");
            return;
         }
         apexFormsCatalogPages[String(catalogOffset)]=payload;
         apexFormsOwnerTotal=catalogTotal;
         var catalogRows:Array=String(catalogFields[3]).split(";");
         if(catalogRows.length<1 || catalogRows.length>32 || catalogOffset+catalogRows.length>catalogTotal)
            throw new Error("Invalid native owner catalog page size");
         for each(var catalogRow:String in catalogRows) {
            var ownerFields:Array=catalogRow.split(",");
            if(ownerFields.length!=10 || !/^[a-z0-9_][a-z0-9_-]{0,63}\/[a-z0-9_][a-z0-9_-]{0,63}$/.test(ownerFields[0]) ||
               !/^[a-z0-9_][a-z0-9_-]{0,63}\/[a-z0-9_][a-z0-9_-]{0,63}$/.test(ownerFields[3]) ||
               String(ownerFields[4]).length>1024 ||
               !/^[a-z0-9_][a-z0-9_-]{0,63}$/.test(ownerFields[5]) ||
               !/^(|[1-9][0-9]{0,19})$/.test(ownerFields[6]) || !/^(|[1-9][0-9]{0,19})$/.test(ownerFields[7]) ||
               String(ownerFields[8]).length>4096 || String(ownerFields[9]).length>1024 ||
               !/^[0-9]+$/.test(ownerFields[1]) || !/^[0-9]+$/.test(ownerFields[2])) throw new Error("Invalid native owner button");
            var ownerKind:int=int(ownerFields[1]);var ownerToken:uint=uint(ownerFields[2]);
            if(ownerKind<1 || ownerKind>64 || (ownerKind & (ownerKind-1))!=0 || ownerToken<0x20000000 || ownerToken>0x2fffffff)
               throw new Error("Invalid native owner button rendering kind/token");
            for each(var oldOwner:Object in apexFormsOwners) if(oldOwner.id==ownerFields[0]) throw new Error("Duplicate native owner identity");
            var ownerLabel:String=decodeURIComponent(String(ownerFields[4]));
            if(ownerLabel.length<1 || ownerLabel.length>192) throw new Error("Invalid form display name");
            var ownerDescription:String=decodeURIComponent(String(ownerFields[8]));
            var variantLabel:String=decodeURIComponent(String(ownerFields[9]));
            if(ownerDescription.length<1 || ownerDescription.length>768 || variantLabel.length<1 || variantLabel.length>192)
               throw new Error("Invalid form description or variant name");
            apexFormsOwners.push({id:String(ownerFields[0]),kind:ownerKind,token:ownerToken,
               form_id:String(ownerFields[3]),label:ownerLabel,family:String(ownerFields[5]),
               icon:String(ownerFields[6]),family_icon:String(ownerFields[7]),description:ownerDescription,variant_label:variantLabel});
         }
         apexFormsSignature="";
      }

      private function ApexFormsTryLocalCatalog() : Boolean
      {
         if(apexFormsLocalCatalog) return true;
         if(apexDisconnected || apexNativeChannel=="" ||
            this.mCurrSimInfo==null || this.mCurrSimInfo.simId!==apexBoundSim) return false;
         var payload:String=ApexNativeExchange("LOCALOWNERS|"+apexNativeChannel+"|"+apexBoundSim+"|"+apexFormsLocalOffset);
         if(payload=="WAIT" || payload=="UNAVAILABLE") return false;
         if(payload.indexOf("OWNERS|")!=0) throw new Error("Prepared native form catalogue refused");
         var fields:Array=payload.split("|");
         if(fields.length!=4 || String(apexFormsLocalOffset)!==String(fields[1])) throw new Error("Prepared native form page lost its exact continuation");
         ApexFormsConsumeCatalog(payload);
         apexFormsLocalOffset+=String(fields[3]).split(";").length;
         if(apexFormsOwnerTotal>=0 && apexFormsLocalOffset===apexFormsOwnerTotal && apexFormsOwners.length===apexFormsOwnerTotal) {
            var localMask:int=0;
            for each(var localOwner:Object in apexFormsOwners) localMask|=int(localOwner.kind);
            if(localMask<1 || localMask>127 || (localMask & 1)==0) throw new Error("Prepared native menu membership descriptor differs");
            apexFormsOwnedMask=localMask;
            apexFormsLocalCatalog=true;
         }
         return apexFormsLocalCatalog;
      }

      private function ApexNativeOpen(simId:String) : void
      {
         var opened:String=ApexNativeExchange("OPEN|"+simId);
         // The previous member's worker closes asynchronously. BUSY is a
         // bounded retry on the next bootstrap frame, not a failed connection
         // which needs another reset and ordinary Timer interval.
         if(opened=="BUSY") return;
         if(!/^OPEN\|[1-9][0-9]{0,19}$/.test(opened)) throw new Error("Native CAS pipe opening refused");
         apexNativeChannel=opened.substr(5);apexNativeConnected=false;
         apexBoundSim=simId;apexHelloPending=false;
         apexAwaiting="connect|"+apexTimer.currentCount;
      }

      private function ApexNativeReceive() : void
      {
         var received:String=ApexNativeExchange("READ|"+apexNativeChannel);
         if(received=="WAIT") return;
         if(received=="CONNECTED") {
            if(apexNativeConnected || apexAwaiting.split("|")[0]!="connect")
               throw new Error("Native CAS pipe repeated its connection event");
            apexNativeConnected=true;apexSocketActive=true;apexHelloPending=true;return;
         }
         if(!apexNativeConnected || received.indexOf("DATA|")!=0)
            throw new Error("Native CAS pipe closed or lost its scope; no replay");
         ApexConsumeFrame(received.substr(5));
      }

      private function ApexConsumeFrame(chunk:String) : void
      {
         try {
            if(chunk.length>131080 || apexFrame.length+chunk.length>131080)
               throw new Error("CAS transport receive buffer exceeds limit");
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
                  if(!/^HELLO\|[0-9a-f]{64}\|(0|[1-9][0-9]{0,2})$/.test(payload)) throw new Error("Invalid CAS session nonce or membership descriptor");
                  var hello:Array=payload.split("|");
                  apexFormsOwnedMask=int(hello[2]);
                  if(apexFormsOwnedMask>127 || apexFormsOwnedMask!=0 && (apexFormsOwnedMask & 1)==0)
                     throw new Error("Invalid captured membership display descriptor");
                  apexNonce=String(hello[1]); apexAwaiting="";
               } else if(stage=="poll") {
                  if(payload=="WAIT") { apexAwaiting=""; }
                  else if(payload.indexOf("OWNERS|")==0) {
                     ApexFormsConsumeCatalog(payload);apexAwaiting="";
                  } else if(payload.indexOf("OWNERSTATE|")==0) {
                     var ownerState:Array=payload.split("|");
                     if(ownerState.length!=5 || !/^[a-z0-9_][a-z0-9_-]{0,63}\/[a-z0-9_][a-z0-9_-]{0,63}$/.test(ownerState[1]) ||
                        !/^[0-9]+$/.test(ownerState[2]) || !/^[01]$/.test(ownerState[3]) ||
                        ["bound","unbound","unresolved"].indexOf(ownerState[4])<0) throw new Error("Invalid native owner selection metadata");
                     // A delayed Python heartbeat must not overwrite the UI
                     // thread's newer bound owner or keep a finished switch busy.
                     if(!ApexFormsReadNativeState() && !apexFormsFastState) {
                        apexFormsSelectedId=String(ownerState[1]);apexFormsNativeState=String(ownerState[4]);
                        if(apexFormsDesiredId!="" && apexFormsDesiredId==apexFormsSelectedId && apexFormsNativeState=="bound") apexFormsDesiredId="";
                     }
                     // The renderer's signature already includes selection,
                     // native state and desired owner. An identical heartbeat
                     // must not tear down and reload every native image.
                     apexAwaiting="";
                  } else {
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
               // Keep the buffer itself until the next send. The matched peer
               // response releases only the one outstanding-frame lease.
               apexOutboundPending=false;
            }
         } catch(frameError:Error) { ApexSocketFailure(frameError); }
      }

      private function ApexSocketReply(id:String, reply:String) : void
      {
         apexAckId=id; apexAwaiting="ack|"+apexTimer.currentCount;
         // APEX_TIMER_TRACE_BEGIN ack-send-begin
         if(apexCatalogTrace!=null && apexCatalogTrace.enabled===true && apexCatalogTrace.timer_profile!=null) ApexCatalogTimerStep("ack-send.enter");
         // APEX_TIMER_TRACE_END ack-send-begin
         ApexSocketSend("ACK|"+apexNonce+"|"+id+"|"+reply);
         // APEX_TIMER_TRACE_BEGIN ack-send-end
         if(apexCatalogTrace!=null && apexCatalogTrace.enabled===true && apexCatalogTrace.timer_profile!=null) ApexCatalogTimerStep("ack-send.leave");
         // APEX_TIMER_TRACE_END ack-send-end
      }

      private function ApexQuote(value:String) : String
      {
         var result:String = '"';
         for(var i:int=0; i<value.length; ++i) {
            var c:int=value.charCodeAt(i);
            if(c==34 || c==92) result += "\\" + value.charAt(i);
            else if(c<32 || c>126) result += "\\u" + ("0000" + c.toString(16)).substr(-4);
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
         formFlags:int, nativeSession:int, requestedLayer:int=-1, userGesture:Boolean=false) : Object
      {
         // A same-ID paired feed permits navigation only. It never proves the
         // native wrapper relationship and cannot authorize alternate acceptance.
         if(!apexTicking || apexDisconnected || !apexSocketActive ||
            (!userGesture && apexClaimNonce!=apexNonce) ||
            (userGesture && (!apexFormsApplying || apexFormsOwnedMask==0 || apexPendingFields!=null)) ||
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
            if(!(mode is int) || (int(mode)!=0 && int(mode)!=7) || family!==false || area==null || area.result!==true)
               throw new Error("CAS form selection requires mode0 or mode7, existing family and explicit Live entry");
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
               !(raw.selected_index is int) || raw.selected_index<0 || raw.selected_index>=raw.pairs.length ||
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
            var nonhumanKind:int=pair.base.occult_type==1 ? int(pair.alternate.occult_type) : int(pair.base.occult_type);
            var explicitLayer:Boolean=requestedLayer==0 || requestedLayer==1;
            var baseKind:int=int(pair.base.occult_type); var alternateKind:int=int(pair.alternate.occult_type);
            var baseKnown:Boolean=baseKind==1 || baseKind==2 || baseKind==4 || baseKind==8 || baseKind==16 || baseKind==32 || baseKind==64;
            var alternateKnown:Boolean=alternateKind==1 || alternateKind==2 || alternateKind==4 || alternateKind==8 || alternateKind==16 || alternateKind==32 || alternateKind==64;
            var supportedPair:Boolean=explicitLayer ? baseKnown && alternateKnown :
               (pair.base.occult_type==1 || pair.alternate.occult_type==1) &&
               pair.base.occult_type!=pair.alternate.occult_type && baseKnown && alternateKnown;
            if(matches!=1 || !supportedPair ||
               pair.base.all_occult_types!=pair.alternate.all_occult_types || pair.base.all_occult_types<0 ||
               (pair.base.all_occult_types & pair.base.occult_type)==0 ||
               (pair.base.all_occult_types & pair.alternate.occult_type)==0)
               throw new Error("CAS form selection lacks the exact observed native layer context");
            var current:Object=expectedLayer==0 ? pair.base : pair.alternate;
            var other:Object=expectedLayer==0 ? pair.alternate : pair.base;
            if(current.selected!==true || other.selected!==false || current.occult_type!=selected.occult_type ||
               current.all_occult_types!=selected.all_occult_types || current.occult_layer!=selected.occult_layer)
               throw new Error("CAS form selection fresh selected context differs from retained selection");
            var targetLayer:int=explicitLayer ? requestedLayer :
               pair.base.occult_type==formFlags ? 0 : pair.alternate.occult_type==formFlags ? 1 : -1;
            if(targetLayer<0) throw new Error("Requested form is absent from the actual base/alternate pair");
            var target:Object=targetLayer==0 ? pair.base : pair.alternate;
            if(!explicitLayer && target.occult_type!=formFlags) throw new Error("Requested form is absent from the actual base/alternate pair");
            native=CommunicationManager.CallGameService("CASGetSimInfo",null,true);
            fresh=ApexOwnerSimRow(native); native=null;
            if(fresh==null || ApexEncode(fresh)!=ApexEncode(selected))
               throw new Error("CAS form selection selected context changed during preflight");
            return {native_session:nativeSession,sim_id:simId,household_id:householdId,selected_index:selectedIndex,
               selected_layer:expectedLayer,target_layer:targetLayer,form_flags:int(target.occult_type),feed_sequence:int(raw.sequence),
               pair_json:ApexEncode(projection)};
         } finally { native=null; selector=null; fresh=null; }
      }

      private function ApexMemberSelectionContext(currentId:String, targetId:String, householdId:String,
         expectedLayer:int, nativeSession:int) : Object
      {
         // Member navigation uses actual retained base rows. EA filters
         // alternate thumbnails for composite masks; never invent them.
         if(!apexTicking || apexDisconnected || !apexSocketActive || apexClaimNonce!=apexNonce ||
            nativeSession!=apexOwnerSession || nativeSession<=0 || (expectedLayer!=0 && expectedLayer!=1))
            throw new Error("Member selection lacks its owned Timer/session/peer");
         var selected:Object=ApexOwnerSimRow(CommunicationManager.CallGameService("CASGetSimInfo",null,true));
         if(selected==null || selected.sim_id!=currentId || selected.household_id!=householdId ||
            selected.occult_layer!=expectedLayer) throw new Error("Member selection selected identity differs");
         var mode:* = CommunicationManager.CallGameService("CasGetCASEditMode");
         var family:* = CommunicationManager.CallGameService("CasIsNewFamily");
         var area:Object=CommunicationManager.CallGameService("CasIsEnteredFromPlayArea");
         if(!(mode is int) || int(mode)!=0 || family!==false || area==null || area.result!==true)
            throw new Error("Member selection requires the full existing-household editor from Live");
         var selector:Object=CommunicationManager.CallUIService("ApexReadOwnerPairFeed",null);
         if(selector==null || selector.protocol!==1 || selector.scope!="native-selector-owner-pair-view" ||
            selector.service_registered!==true || selector.reset_listener_registered!==true ||
            selector.mapping_verified!==false || selector.alternate_accept_authorized!==false)
            throw new Error("Member selection roster service is unavailable");
         var raw:Object=selector.raw_feed; var retained:Object=selector.retained;
         if(raw==null || retained==null || raw.source!="native-selector-raw-entry-observer" ||
            raw.before_native_handler!==true || raw.delivered!==true || raw.complete!==true ||
            !(raw.sequence is int) || raw.sequence<=0 || retained.source!="native-selector-retained-filtered-feed" ||
            retained.available!==true || !(raw.pairs is Array) || !(retained.pairs is Array) ||
            raw.pairs.length==0 || raw.pairs.length>32 || raw.pairs.length!=retained.pairs.length ||
            raw.base_row_count!==raw.pairs.length || raw.alternate_row_count!==raw.pairs.length ||
            !(retained.selected_index is int) || retained.selected_index<0 || retained.selected_index>=raw.pairs.length ||
            retained.selected_sim_id!==currentId || retained.selected_layer!==expectedLayer)
            throw new Error("Member selection lacks its complete delivered/retained member roster");
         var pairs:Array=raw.pairs as Array;
         var roster:Array=[]; var targetIndex:int=-1; var targetKind:int=-1;
         var identities:Object={}; var currentIndex:int=int(retained.selected_index);
         for(var i:int=0;i<pairs.length;i++) {
            var pair:Object=pairs[i]; var kept:Object=retained.pairs[i];
            if(pair==null || pair.index!==i || kept==null || kept.index!==i || pair.base==null || pair.alternate==null || kept.base==null)
               throw new Error("Member selection lacks exact roster positions");
            var base:Object=pair.base; var alt:Object=pair.alternate;
            if(!(base.sim_id is String) || !/^[1-9][0-9]{0,19}$/.test(base.sim_id) ||
               base.sim_id!==alt.sim_id || identities[base.sim_id]===true || base.index!==i || alt.index!==i ||
               base.occult_layer!==0 || alt.occult_layer!==1 || base.all_occult_types!==alt.all_occult_types)
               throw new Error("Member selection identities are invalid or duplicated");
            identities[base.sim_id]=true;
            var copied:Object={index:i};
            for each(var side:String in ["base","alternate"]) {
               var row:Object=pair[side];
               var keptRow:Object=kept[side];
               if(!(row.occult_type is int) || !/^(1|2|4|8|16|32|64)$/.test(String(row.occult_type)) ||
                  !(row.all_occult_types is int) || (row.all_occult_types & row.occult_type)==0 ||
                  (keptRow!=null && (keptRow.sim_id!==row.sim_id || keptRow.index!==row.index ||
                   keptRow.occult_type!==row.occult_type || keptRow.all_occult_types!==row.all_occult_types ||
                   keptRow.occult_layer!==row.occult_layer)))
                  throw new Error("Member selection raw and retained identities differ");
               copied[side]={sim_id:String(row.sim_id),index:int(row.index),occult_type:int(row.occult_type),
                  all_occult_types:int(row.all_occult_types),occult_layer:int(row.occult_layer)};
            }
            roster.push(copied);
            if(pair.base.sim_id==targetId) {
               if(targetIndex!=-1) throw new Error("Member selection target is ambiguous");
               targetIndex=i; targetKind=int(pair.base.occult_type);
            }
         }
         var chosen:Object=expectedLayer==0 ? pairs[currentIndex].base : pairs[currentIndex].alternate;
         if(chosen.sim_id!==currentId || chosen.occult_type!==selected.occult_type ||
            chosen.all_occult_types!==selected.all_occult_types)
            throw new Error("Member selection fresh metadata differs from delivery");
         selector=null; pairs=null;
         if(targetIndex<0) throw new Error("Member selection target is absent from the observed household");
         return {native_session:nativeSession,household_id:householdId,source_sim_id:currentId,target_sim_id:targetId,
            source_index:currentIndex,target_index:targetIndex,target_form_flags:targetKind,
            roster_json:ApexEncode(roster)};
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

      private function ApexCatalogReadbackOnly(operation:String) : Boolean
      {
         // Opening/browsing can intentionally navigate to another native menu;
         // those commands retain full readback rather than relax this identity.
         return operation=="catalog-state" || operation=="catalog-style" ||
            operation=="catalog-cards" || operation=="catalog-card-reset" ||
            operation=="catalog-search" || operation=="catalog-width-drag" || operation=="panel-layout" || operation=="catalog-trace" || operation=="catalog-layout-trace";
      }

      private function ApexCatalogReadbackContext(selected:Object) : Object
      {
         // selected is already a detached primitive row. Never retain a native
         // Sim/outfit object while the authenticated owner cursor is queried.
         if(!apexTicking || apexDisconnected || !apexSocketActive || apexNativeChannel=="" ||
            apexClaimNonce!==apexNonce || !/^[0-9a-f]{64}$/.test(apexNonce) || selected==null ||
            selected.sim_id!==apexBoundSim || mCurrSimInfo==null || selected.sim_id!==mCurrSimInfo.simId ||
            selected.household_id!==mCurrSimInfo.householdId || selected.occult_layer!=int(mCurrSimInfo.occultLayer) ||
            selected.all_occult_types!=int(mCurrSimInfo.allOccultTypes) || apexOwnerSession<=0 ||
            apexFormsNativeState!="bound" || apexFormsSelectedId=="" || apexFormsDesiredId!="" ||
            apexFormsIntent!=null || apexFormsNativeIntent!=null || apexMoleculeIntent!=null || apexPairIntent!=null || apexFormsApplying)
            throw new Error("Catalogue readback lacks its fresh bound Sim/owner context");
         var raw:Object=CommunicationManager.CallGameService("CasGetCurrSimOutfitSlot",null,true);
         if(raw==null || !(raw.outfit_type is int) || raw.outfit_type<0 || raw.outfit_type>255 ||
            !(raw.outfit_index is int) || raw.outfit_index<0 || raw.outfit_index>=5)
            throw new Error("Catalogue readback lacks its exact outfit identity");
         var outfitType:int=int(raw.outfit_type);var outfitIndex:int=int(raw.outfit_index);raw=null;
         var cursor:Array=ApexNativeExchange("STATE|"+apexNativeChannel).split("|");
         if(cursor.length!=7 || cursor[0]!="VIEWSTATE" || cursor[1]!==selected.sim_id ||
            cursor[2]!==apexFormsSelectedId || !/^[a-z0-9_][a-z0-9_-]{0,63}\/[a-z0-9_][a-z0-9_-]{0,63}$/.test(cursor[2]) ||
            !/^(1|2|4|8|16|32|64)$/.test(cursor[3]) || cursor[3]!==String(int(mCurrSimInfo.occultType)) ||
            cursor[4]!==String(selected.occult_layer) || cursor[5]!="bound" ||
            cursor[6]!==apexFormsNativeGeneration || !/^[1-9][0-9]{0,19}$/.test(cursor[6]))
            throw new Error("Catalogue readback owner/generation changed");
         return {sim_id:selected.sim_id,household_id:selected.household_id,owner_id:String(cursor[2]),
            native_kind:int(cursor[3]),shell_kind:int(selected.occult_type),native_mask:int(selected.all_occult_types),
            native_generation:String(cursor[6]),session:apexOwnerSession,layer:int(selected.occult_layer),
            outfit_type:outfitType,outfit_index:outfitIndex,menu_state:int(mCurrState)};
      }

      private function ApexCatalogSnapshot(before:Object,after:Object) : Object
      {
         if(before==null || after==null || ApexEncode(before)!==ApexEncode(after))
            throw new Error("Catalogue metadata changed Sim/owner/generation before readback");
         return {protocol:1,scope:"native-cas-catalog-client",appearance_written:false,
            sim:{simId:after.sim_id,householdId:after.household_id,occultType:after.shell_kind,
               allOccultTypes:after.native_mask,occultLayer:after.layer},
            menu_state:after.menu_state,panel_visible:mCurrentPanel!=null && mCurrentPanel.visible,
            outfit:{outfit_type:after.outfit_type,outfit_index:after.outfit_index},
            form_strip:{sim_id:after.sim_id,selected_owner_id:after.owner_id,native_owner_state:"bound",desired_owner_id:"",
               gesture_pending:false,native_generation:after.native_generation,session:after.session},
            catalog_identity:{request_id:String(apexPendingFields[0]),peer_nonce:apexClaimNonce,before:before,after:after},
            catalog_workspace:ApexCatalogStatus()};
      }

      private function ApexPanelNavigationSnapshot(before:Object,after:Object,requested:int) : Object
      {
         // This distinct scope proves navigation only, never a full inventory,
         // form write, save capability or an appearance-preservation result.
         if(before==null || after==null || after.menu_state!==requested ||
            mCurrentPanel==null || mCurrentPanel.visible!==true)
            throw new Error("Requested native CAS panel did not become visible");
         for(var field:String in before)
            if(field!="menu_state" && before[field]!==after[field])
               throw new Error("Panel navigation changed its bound native Sim/form/outfit context");
         var layout:Object={query:"not-available-current-panel",available:false};
         // Only copy cached numeric tuning for the current physical panel.
         // Never enumerate cells, call getBounds, inspect a feed or force layout.
         if(apexCardGeometry!=null && apexCardGeometry.panel===mCurrentPanel && apexCardLayout!=null) {
            var columns:* = apexCardLayout.columns;
            if(!(columns is int) || columns<2 || columns>32)
               throw new Error("Current panel cached columns are invalid");
            layout={query:"cached-current-panel-only",available:true,columns:int(columns)};
            for each(var metric:String in ["scale","width","card_width","card_height","gap_x","gap_y"]){
               var number:* = apexCardLayout[metric];
               if(typeof number!="number" || !isFinite(number) || number<0 || number>8192 ||
                  (metric=="scale" && (number<=0 || number>1.6)))
                  throw new Error("Current panel cached layout metric is invalid");
               layout[metric]=Number(number);
            }
         }
         return {protocol:1,scope:"native-cas-navigation-client",appearance_written:false,
            sim:{simId:after.sim_id,householdId:after.household_id,occultType:after.shell_kind,
               allOccultTypes:after.native_mask,occultLayer:after.layer},
            menu_state:after.menu_state,panel_visible:true,requested_menu_state:requested,
            outfit:{outfit_type:after.outfit_type,outfit_index:after.outfit_index},
            form_strip:{sim_id:after.sim_id,selected_owner_id:after.owner_id,native_owner_state:"bound",desired_owner_id:"",
               gesture_pending:false,native_generation:after.native_generation,session:after.session},
            navigation_identity:{request_id:String(apexPendingFields[0]),peer_nonce:apexClaimNonce,before:before,after:after},
            card_layout:layout};
      }

      private function ApexSnapshot(includeCatalogMetadata:Boolean=false) : Object
      {
         var catalogs:Array=[];
         var catalogMetadata:Array=[]; var catalogMetadataSeen:Object={};
         var catalogMetadataComplete:Boolean=includeCatalogMetadata;
         // A native getter is not guaranteed to support an inactive panel.
         // Keep every panel's identity, but query only the actual current one.
         // Complete appearance DTOs retain the other fields independently.
         var panels:Object=__APEX_PANEL_STATES__;
         for(var name:String in panels) {
            // Detach each returned record before another native getter. No
            // borrowed GFx catalog/preset objects survive subsequent calls.
            var panelCurrent:Boolean=int(panels[name])==this.mCurrState;
            var items:* = panelCurrent ? ApexClone(CommunicationManager.CallGameService("GetCatalogItemsSelectedWithModifiers",{state:panels[name]})) : null;
            var preset:* = null; var presetQuery:String=panelCurrent ? "returned-null" : "not-queried-inactive-panel";
            try {
               if(!panelCurrent) {
                  // Visiting another panel is an explicit navigation action.
               } else if(int(panels[name])==MenuState.PROFILE_HAIR_EYEBROWS || int(panels[name])==MenuState.PROFILE_PET_WHISKERS) {
                  // The native FaceModPanel explicitly uses equipped-part
                  // selection for these states, never a preset index.
                  presetQuery="not-applicable";
               } else {
               preset=ApexClone(CommunicationManager.CallGameService("GetSelectedPresetFromMenuState",panels[name],true));
               if(preset!=null) presetQuery="returned-value";
               }
            } catch(presetError:Error) { presetQuery="failed"; }
            catalogs.push({panel:name,menu_state:panels[name],supported:items is Array,items:items is Array ? items : null,
               query:panelCurrent ? "queried-current-panel" : "not-queried-inactive-panel",
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
                  product=ApexClone(CommunicationManager.CallGameService("GetCatalogItem",catalogId)) as Object;
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
         // Do not inventory hidden categories by invoking their game getter.
         // A getter can lazily create missing outfit records. Complete native
         // DTO exports retain the full wardrobe without visiting each category.
         // Read only the currently selected category; explicit outfit controls
         // own requests to create/select another category or slot.
         var observedSlot:Object=ApexClone(CommunicationManager.CallGameService("CasGetCurrSimOutfitSlot"));
         var plannedOutfits:Array=[];
         for(var outfitCategory:int=0;outfitCategory<=13;outfitCategory++) {
            var plannedData:* = null; var plannedQuery:String="not-queried-no-edit-intent"; var plannedError:String="";
            if(observedSlot!=null && observedSlot.outfit_type is int && outfitCategory==int(observedSlot.outfit_type)) try {
               plannedQuery="returned-null";
               plannedData=ApexClone(CommunicationManager.CallGameService("CasGetPlannedOutfits",outfitCategory));
               if(plannedData!=null) plannedQuery="returned-value";
            } catch(outfitError:Error) { plannedQuery="failed"; plannedError=outfitError.message; }
            plannedOutfits.push({category:outfitCategory,supported:plannedData!=null,data:plannedData,
               query:plannedQuery,error:plannedError});
         }
         var hairSwatches:* = null; var hairSelected:* = null; var hairQuery:String="returned-null";
         try {
            hairSwatches=ApexClone(CommunicationManager.CallGameService("CasGetSwatchColorList",2));
            hairSelected=ApexClone(CommunicationManager.CallGameService("CasGetSwatchColorSelected",2));
            if(hairSwatches is Array) hairQuery="returned-value";
         } catch(swatchError:Error) { hairQuery="failed"; }
         // These are the inspected native navigation/configuration getters.
         // Preserve raw return types and distinguish unavailable from false/0.
         // Context is evidence only; it does not authorize a CAS exit/commit.
         var nativeContext:Object={};
         var contextGetters:Object={edit_mode:"CasGetCASEditMode",new_family:"CasIsNewFamily",rendered_form:"GetSimOccult",
            entered_from_play_area:"CasIsEnteredFromPlayArea",forced_full_edit:"CasIsForcedFullEditingEnabled"};
         for(var contextName:String in contextGetters) {
            var contextValue:* = null; var contextQuery:String="returned-null"; var contextError:String="";
            try {
               if(contextName=="forced_full_edit")
                  contextValue=ApexClone(CommunicationManager.CallGameService("CasIsForcedFullEditingEnabled",null,true));
               else contextValue=ApexClone(CommunicationManager.CallGameService(contextGetters[contextName]));
               if(contextValue!=null) contextQuery="returned-value";
            } catch(contextFailure:Error) { contextQuery="failed"; contextError=contextFailure.message; }
            nativeContext[contextName]={value:contextValue,query:contextQuery,error:contextError};
         }
         var historyPalette:Object={protocol:1,query:"not-queried-outside-bound-pelt-owner",swatch_type:6,
            sim_id:apexBoundSim,owner_id:apexFormsSelectedId,native_kind:null,selected:null};
         if(apexFormsNativeState=="bound" && apexFormsDesiredId=="" &&
            nativeContext.rendered_form.query=="returned-value" &&
            (nativeContext.rendered_form.value===32 || nativeContext.rendered_form.value===64)) {
            historyPalette.native_kind=int(nativeContext.rendered_form.value);
            try {
               var peltSelected:* = ApexClone(CommunicationManager.CallGameService("CasGetSwatchColorSelected",6));
               if(!(peltSelected is Array) || peltSelected.length>5) throw new Error("Incomplete native pelt palette");
               var peltColors:Array=[];
               if(peltSelected.length>0) {
                  // EA returns selected dataID strings, not ARGB values. Mirror
                  // PeltMarkingsPane.GetPeltColors: resolve each exact ID in the
                  // native FURTONE palette, retaining only its uint32 color.
                  // Detach the palette before subsequent native service calls.
                  var peltAvailable:* = ApexClone(CommunicationManager.CallGameService("CasGetSwatchColorList",6));
                  if(!(peltAvailable is Array) || peltAvailable.length>16384) throw new Error("Incomplete native pelt color list");
                  for each(var peltId:* in peltSelected) {
                     if(!(peltId is String) || peltId.length<1 || peltId.length>128) throw new Error("Untyped native pelt swatch ID");
                     var peltMatches:int=0;var peltColor:* = null;
                     for each(var peltRow:* in peltAvailable)
                        if(peltRow!=null && peltRow.dataID===peltId) {peltMatches++;peltColor=peltRow.color;}
                     if(peltMatches!=1 || !(peltColor is Number) || !isFinite(Number(peltColor)) || peltColor<0 ||
                        peltColor>4294967295 || peltColor!=Math.floor(peltColor)) throw new Error("Unresolved native pelt swatch color");
                     peltColors.push(Number(peltColor));
                  }
               }
               historyPalette.selected=peltColors;historyPalette.query="returned-value";
            } catch(peltReadFailure:Error) {historyPalette.query="unavailable";}
         }
         return {protocol:1,scope:"native-cas-client",sim:ApexClone(CommunicationManager.CallGameService("CASGetSimInfo",null,true)),
            menu_state:this.mCurrState,panel_visible:this.mCurrentPanel!=null && this.mCurrentPanel.visible,
            ui_occult_type:this.mCurrSimInfo==null ? null : int(this.mCurrSimInfo.occultType),
            molecule:ApexClone(apexMoleculeView),
            outfit:observedSlot,
            selected:ApexClone(CommunicationManager.CallGameService("GetCatalogItemsSelectedWithModifiers",{state:this.mCurrState})),
            hair_color:hairSelected,hair_selected_swatch_id:hairSelected,hair_swatches:hairSwatches,
            hair_swatch_query:hairQuery,planned_outfits:plannedOutfits,planned_outfits_scope:"selected-category-only",
            native_context:nativeContext,history_palette:historyPalette,catalogs:catalogs,catalog_metadata:catalogMetadata,
            owner_pair_observation:ApexOwnerObservation(),form_strip:ApexFormsStatus(),catalog_workspace:ApexCatalogStatus(),
            catalog_metadata_complete:catalogMetadataComplete,catalog_metadata_scope:"native-catalog-identities-only",
            catalog_metadata_query:includeCatalogMetadata ? "explicit-lookup" : "disabled-pending-native-contract-proof"};
      }

      private function ApexClone(value:*,depth:int=0) : *
      {
         if(depth>12) throw new Error("CAS clone nesting exceeds limit");
         if(value==null || value is String || value is Number || value is Boolean) return value;
         if(value is Array) {
            var result:Array=[];
            if(value.length>1024) throw new Error("CAS clone list exceeds limit");
            for each(var item:* in value) result.push(ApexClone(item,depth+1));
            return result;
         }
         var object:Object={};
         var fieldCount:int=0;
         for(var name:String in value) {
            if(++fieldCount>1024) throw new Error("CAS clone object exceeds limit");
            object[name]=ApexClone(value[name],depth+1);
         }
         // Sealed native filter records have non-enumerable public slots.
         // Reflect this data class only; never walk arbitrary widget getters.
         // Include public instance fields added by later patches.
         if(value is CASCatalogFilter) {
            var definition:XML=describeType(value);
            for each(var slot:XML in definition.variable) {
               if(++fieldCount>1024) throw new Error("CAS clone slots exceed limit");
               name=String(slot.@name); object[name]=ApexClone(value[name],depth+1);
            }
            for each(var accessor:XML in definition.accessor) {
               if(String(accessor.@access)!="writeonly") {
                  if(++fieldCount>1024) throw new Error("CAS clone accessors exceed limit");
                  name=String(accessor.@name); object[name]=ApexClone(value[name],depth+1);
               }
            }
         }
         return object;
      }

      private function ApexCatalog(state:int) : Array
      {
         if(this.mCurrState!=state || this.mCurrentPanel==null || !this.mCurrentPanel.visible)
            throw new Error("Native catalog requires the exact visible requested panel");
         var filter:Object=this.mCurrentPanel.mcFilterPane!=null ? this.mCurrentPanel.mcFilterPane.GetCatalogFilter() :
            {tags:[],excludeTags:[],filterByGameplayUnlocks:false,filterLocked:false,
             filterPurchasedProducts:false,filterModdedContent:false,packIds:[],body_type:0};
         if(this.mCurrentPanel is FaceModPanel)
            filter={tags:[],excludeTags:[],filterByGameplayUnlocks:false,filterLocked:false,
               filterPurchasedProducts:false,filterModdedContent:false,packIds:[],body_type:0};
         if(this.mCurrentPanel is BodyModPanel) filter.tags=[];
         var bodyType:int=0;
         if(MenuState.SupportsBodyTypeFilter(state) && this.mCurrentPanel is ClothingPanel)
            bodyType=ClothingPanel(this.mCurrentPanel).mcBodyTypePanel.GetSelected();
         if(MenuState.SupportsLayerList(state)) {
            if(!(this.mCurrentPanel is ClothingPanel)) throw new Error("Native layered catalog panel is unavailable");
            // Native base discovery has a body-type filter; selected-layer
            // filtering belongs to the separate selected-item getter.
         }
         var rows:Array=CommunicationManager.CallGameService("GetCatalogBaseItems",{state:state,
            tags:ApexClone(filter.tags),excludeTags:ApexClone(filter.excludeTags),
            unlocks:Boolean(filter.filterByGameplayUnlocks),locked:Boolean(filter.filterLocked),
            mtx:Boolean(filter.filterPurchasedProducts),mods:Boolean(filter.filterModdedContent),
            packIds:ApexClone(filter.packIds),genusOverride:null,bodyType:bodyType}) as Array;
         if(rows==null) throw new Error("Native catalog returned null; unsupported cannot count as empty");
         var canine:Object=ApexSearchSource({operation:"canine-context",state:state});
         if(canine!=null && canine.enabled===true) {
            rows=ApexClone(rows) as Array;
            var wolf:Array=ApexClone(CommunicationManager.CallGameService("GetCatalogBaseItems",{state:state,
               tags:ApexClone(filter.tags),excludeTags:ApexClone(filter.excludeTags),
               unlocks:Boolean(filter.filterByGameplayUnlocks),locked:Boolean(filter.filterLocked),
               mtx:Boolean(filter.filterPurchasedProducts),mods:Boolean(filter.filterModdedContent),
               packIds:ApexClone(filter.packIds),genusOverride:{occult:32},bodyType:bodyType})) as Array;
            var ids:Object={};var product:Object;
            for each(product in rows) if(product!=null) ids["$"+String(product.data_id)]=true;
            if(wolf!=null) for each(product in wolf) if(product!=null && ids["$"+String(product.data_id)]!==true) {
               ids["$"+String(product.data_id)]=true;rows.push(product);
            }
         }
         filter=null;return rows;
      }

      private function ApexWingObservation() : Object
      {
         // Evidence only. Keep the raw native return types even when a strict
         // compound selection will refuse them. Never infer a color from its
         // base or turn a diagnostic getter into a successful edit receipt.
         var result:Object={protocol:1,scope:"native-wing-selection-read-only",qualified_success:false,
            panel_state:this.mCurrState,body_type:CASBodyType.WINGS,base_native_flag:true,
            base_arguments:null,color_argument:CASBodyType.WINGS,base_query:"not-queried",color_query:"not-queried",
            selected_base_ids:null,selected_base_types:[],base_return_type:"undefined",base_is_array:false,
            selected_color_id:null,selected_color_type:"undefined",base_error:"",color_error:""};
         if(this.mCurrState!=MenuState.CLOTHING_BODY_WINGS || this.mCurrentPanel==null || !this.mCurrentPanel.visible) {
            result.base_query="refused"; result.color_query="refused";
            result.base_error="Exact visible native wing panel required";
            result.color_error=result.base_error; return result;
         }
         var filter:Object=null; var baseArgs:Object=null; var baseRaw:* = null; var colorRaw:* = null;
         try {
            filter=this.mCurrentPanel.mcFilterPane!=null ? this.mCurrentPanel.mcFilterPane.GetCatalogFilter() :
               {tags:[],excludeTags:[]};
            baseArgs={state:this.mCurrState,tags:ApexClone(filter.tags),excludeTags:ApexClone(filter.excludeTags),bodyType:0,layer:-1};
            filter=null; result.base_arguments=ApexClone(baseArgs);
            baseRaw=ApexClone(CommunicationManager.CallGameService("GetCatalogBaseItemSelected",baseArgs,true));
            result.base_return_type=typeof baseRaw; result.base_is_array=baseRaw is Array;
            result.base_query=baseRaw===null ? "returned-null" : (typeof baseRaw=="undefined" ? "returned-undefined" : "returned-value");
            if(baseRaw is Array && baseRaw.length>32) {
               result.base_query="refused-bound"; result.base_error="Native wing base observation exceeds its bound";
            } else {
               result.selected_base_ids=baseRaw;
               if(baseRaw is Array) for(var i:int=0;i<baseRaw.length;i++) result.selected_base_types.push(typeof baseRaw[i]);
            }
         } catch(baseError:Error) { result.base_query="failed"; result.base_error=baseError.message; }
         finally { filter=null; baseArgs=null; baseRaw=null; }
         try {
            colorRaw=ApexClone(CommunicationManager.CallGameService("GetCatalogVariantItemSelected",CASBodyType.WINGS));
            result.selected_color_id=colorRaw; result.selected_color_type=typeof colorRaw;
            result.color_query=colorRaw===null ? "returned-null" : (typeof colorRaw=="undefined" ? "returned-undefined" : "returned-value");
         } catch(colorError:Error) { result.color_query="failed"; result.color_error=colorError.message; }
         finally { colorRaw=null; }
         return result;
      }

      private function ApexSelectEyebrowSwatch(value:String,rows:Array) : Object
      {
         // Mirror FaceModPanel/ColorSwatchPanel's actual palette selection.
         // Its grid callback also maintains the native Match Hair checkbox
         // and flags. A bare color service call omits that widget lifecycle.
         if(this.mCurrState!=MenuState.PROFILE_HAIR_EYEBROWS || !(this.mCurrentPanel is FaceModPanel) ||
            rows==null || rows.length==0 || rows.length>512)
            throw new Error("Exact native eyebrow palette is unavailable");
         var widget:Object=FaceModPanel(this.mCurrentPanel).mcColorSwatchPanel;
         if(widget==null || widget.mcSelectionGrid==null || !widget.IsEnabled())
            throw new Error("Native eyebrow color widget is unavailable");
         widget.SetType(3);
         // SetType already refreshes. Resolve against the widget's actual
         // current feed, whose order can differ from the earlier native array.
         var layout:Object=widget.mcSelectionGrid.mGridLayout;
         var feed:Object=layout!=null ? layout.GetDataFeed() : null;
         if(feed==null || int(feed.length)<1 || int(feed.length)>512)
            throw new Error("Native eyebrow widget has no complete bounded swatch feed");
         var items:Array=ApexClone(feed.RequestItemsAt(0,int(feed.length))) as Array;
         var at:int=-1; var count:int=0;
         if(items==null || items.length!=int(feed.length))
            throw new Error("Native eyebrow widget feed is incomplete");
         for(var i:int=0;i<items.length;i++)
            if(items[i] && items[i].dataID is String && String(items[i].dataID)==value) { at=i; count++; }
         if(count!=1) throw new Error("Native eyebrow widget requires one exact returned swatch");
         var selectedItem:String=ApexEncode(items[at]);var itemCount:int=items.length;
         items=null;feed=null;layout=null;
         var before:Array=ApexClone(widget.GetSelectedIndices()) as Array;
         widget.mcSelectionGrid.SetSelection(at,true,true);
         return {requested_data_id:value,target_index:at,palette_count:itemCount,native_palette_count:rows.length,
            selected_palette_item_json:selectedItem,
            selected_indices_before:before,selected_indices_after:ApexClone(widget.GetSelectedIndices())};
      }

      private function ApexControlExecute(operation:String,state:int,category:int,index:int,value:String,reply:Object,context:Object) : void
      {
         if(operation=="catalog-state") {
            if(state!=0 || category!=0 || index!=0 || value!="") throw new Error("Catalogue state has no mutation parameters");
            return;
         }
         if(operation=="catalog-width-drag") {
            // UI-only input on the CURRENT physical handle. Coordinates are
            // measured here under the same owner lease, never supplied as an
            // arbitrary pointer target or used to write preferences directly.
            if(state!=0 || category!=0 || index!=0 || !/^-?(0|[1-9][0-9]*)(\.[0-9]{1,6})?$/.test(value) ||
               !isFinite(Number(value)) || Math.abs(Number(value))<0.05 || Math.abs(Number(value))>2048 ||
               context.catalog_before==null || apexColumns==null || apexColumns.resize!=null || apexColumns.drag || apexColumns.scale_drag ||
               stage==null || !ApexColumnsTakeover())throw new Error("Width drag requires its exact idle native catalog handle and bounded delta");
            var wdPanel:Object=mCurrentPanel;
            var wdGrid:Object=wdPanel.mcTileList==null ? null : wdPanel.mcTileList.mGridLayout;
            var wdHandle:flash.display.Sprite=apexColumns.width_handle as flash.display.Sprite;
            if(wdGrid==null || apexCardGeometry==null || apexCardGeometry.panel!==wdPanel || apexCardGeometry.grid!==wdGrid ||
               apexCardLayout==null || wdHandle==null || wdHandle.parent!==wdPanel || !wdPanel.visible || !wdHandle.visible ||
               wdPanel.stage!==stage || wdHandle.stage!==stage || !wdHandle.mouseEnabled)
               throw new Error("Width drag handle is stale, detached or unavailable");
            var wdVisible:Object=wdHandle;
            while(wdVisible!=null && wdVisible!==stage) {if(!wdVisible.visible)throw new Error("Width drag handle is hidden");wdVisible=wdVisible.parent;}
            if(wdVisible!==stage)throw new Error("Width drag handle left its observed stage");
            var wdBounds:flash.geom.Rectangle=wdHandle.getBounds(stage);
            var wdProbe:Object={protocol:1,scope:"native-catalog-width-bounds",ok:false,reason:"not-attempted",appearance_written:false};
            var wdEnvelope:Object=ApexCatalogWidthEnvelope(wdPanel,wdProbe);
            var wdBefore:Number=Number(wdPanel.mcPanelBackground.width);
            if(wdEnvelope==null || !isFinite(wdEnvelope.scale) || wdEnvelope.scale<=0 ||
               !isFinite(wdEnvelope.available) || wdEnvelope.available<80)
               throw new Error("Width envelope unavailable: "+String(wdProbe.reason)+
                  (wdProbe.navigation==null ? "" : " / "+String(wdProbe.navigation.reason)));
            if(wdBounds==null || !isFinite(wdBefore) || wdBefore<80 ||
               !isFinite(wdBounds.x) || !isFinite(wdBounds.y) || !isFinite(wdBounds.width) || !isFinite(wdBounds.height) ||
               wdBounds.width<=0 || wdBounds.width>128 || wdBounds.height<=0 || wdBounds.height>256)
               throw new Error("Width drag handle has no finite current hit bounds");
            var wdX:Number=wdBounds.x+wdBounds.width*0.5;var wdY:Number=wdBounds.y+wdBounds.height*0.5;
            var wdTarget:Number=wdX+Number(value);
            if(wdBounds.x<0 || wdBounds.y<0 || wdBounds.right>stage.stageWidth || wdBounds.bottom>stage.stageHeight ||
               wdTarget<0 || wdTarget>stage.stageWidth)throw new Error("Width drag exceeds the actual viewport");
            var wdLocal:flash.geom.Point=wdHandle.globalToLocal(stage.localToGlobal(new flash.geom.Point(wdX,wdY)));
            if(!isFinite(wdLocal.x) || !isFinite(wdLocal.y) || wdLocal.x<0 || wdLocal.x>12 || wdLocal.y<0 || wdLocal.y>72)
               throw new Error("Width drag center is outside the actual handle hit area");
            context.width_drag={handler_invoked:false,appearance_written:false,delta_x:Number(value),
               menu_state:int(mCurrState),stage_width:stage.stageWidth,stage_height:stage.stageHeight,
               handle:{x:wdBounds.x,y:wdBounds.y,width:wdBounds.width,height:wdBounds.height},
               down:{x:wdX,y:wdY},move:{x:wdTarget,y:wdY},up:{x:wdTarget,y:wdY},
               before_width:wdBefore,maximum_width:Number(wdEnvelope.available),coordinate_scale:Number(wdEnvelope.scale),
               columns:int(apexCatalogPrefs.columns),card_scale:Number(apexCardPrefs.scale),
               gap_x:Number(apexCardPrefs.gap_x),gap_y:Number(apexCardPrefs.gap_y)};
            context.width_drag_panel=wdPanel;context.width_drag_grid=wdGrid;context.width_drag_handle=wdHandle;
            try {
               wdHandle.dispatchEvent(new flash.events.MouseEvent(flash.events.MouseEvent.MOUSE_DOWN,true,true,wdLocal.x,wdLocal.y,null,false,false,false,true));
               if(apexColumns.resize==null || apexColumns.resize.panel!==wdPanel || apexColumns.resize.grid!==wdGrid ||
                  apexColumns.resize.stage!==stage || apexColumns.resize.width!=stage.stageWidth || apexColumns.resize.height!=stage.stageHeight)
                  throw new Error("Actual width down handler did not acquire its exact native handle");
               stage.dispatchEvent(new flash.events.MouseEvent(flash.events.MouseEvent.MOUSE_MOVE,false,true,wdTarget,wdY,null,false,false,false,true));
               stage.dispatchEvent(new flash.events.MouseEvent(flash.events.MouseEvent.MOUSE_UP,false,true,wdTarget,wdY));
               if(apexColumns.resize!=null)throw new Error("Actual width up handler did not release its drag");
               context.width_drag.handler_invoked=true;context.width_drag.width_bounds=wdProbe;
               context.width_drag.requested_width=Number(apexColumns.preferred_width);
            } finally {if(apexColumns.resize!=null)ApexColumnsResizeEnd(new flash.events.Event(flash.events.Event.DEACTIVATE));}
            wdVisible=null;wdHandle=null;wdGrid=null;wdPanel=null;return;
         }
         if(operation=="catalog-layout-trace") {
            if(state!=0 || category!=0 || index!=0 || !/^(0|[1-9][0-9]{0,4})$/.test(value) || Number(value)>30000)
               throw new Error("Layout diagnostics require a bounded explicit duration");
            ApexLayoutTraceConfigure(int(value));return;
         }
         if(operation=="catalog-trace") {
            if(state!=0 || category!=0 || index!=0 || !/^(0|[1-9][0-9]{0,4})$/.test(value) || Number(value)>30000)
               throw new Error("Draw diagnostics require a bounded explicit duration");
            ApexCatalogTraceConfigure(int(value));return;
         }
         if(operation=="catalog-search") { ApexSearchText(decodeURIComponent(value));return; }
         if(operation=="catalog-companion") {reply.mutation_started=String(value.split(",")[0])=="random-favorite";ApexCompanionCommand(value);return;}
         if(operation=="catalog-input") {
            reply.mutation_started=String(value.split(",")[0])=="enter";ApexCatalogKeyboardInput(value);
            if(!reply.mutation_started)context.keyboard_publication=ApexCatalogKeyboardPublication(context.keyboard_before);
            return;
         }
         if(operation=="catalog-key") {
            ApexCatalogKeyboardCommand(value);context.keyboard_publication=ApexCatalogKeyboardPublication(context.keyboard_before);return;
         }
         if(operation=="catalog-cards") { ApexCardCommand(value);return; }
         if(operation=="catalog-card-reset") { ApexCardReset();return; }
         if(operation=="catalog-style") { ApexCatalogStyle(value);return; }
         if(operation=="panel-layout") { ApexPanelsCommand(value);return; }
         if(operation=="catalog-view") { ApexCatalogView(value);return; }
         if(operation=="catalog-slider") { ApexCatalogSliderCommand(value);return; }
         if(operation=="catalog-open") {
            ApexCatalogReadEquipped();
            CommunicationManager.SendMessage("CASContextMenuUpdate",CASContextMenuState.BODY);
            ApexCatalogDraw();return;
         }
         var data:Object=null; var rows:Array=null; var row:Object=null; var n:int=0;
         var parts:Array=value.split(","); var layerId:int=0; var target:int=0;
         if(operation=="form-owner-select") {
            if(!/^[a-z0-9_][a-z0-9_-]{0,63}\/[a-z0-9_][a-z0-9_-]{0,63}$/.test(value) ||
               index<0x10000000 || index>0x1fffffff)
               throw new Error("Independent form view requires its exact staged one-shot token");
            if(apexFormsDesiredId!="" || apexFormsNativeIntent!=null && apexFormsNativeIntent.bootstrap!==true)
               throw new Error("Wait for the current form-button selection to settle; no independent view submitted");
            // An explicit selection supersedes only the unsubmitted automatic
            // bootstrap. Never leave that old default queued behind this view,
            // and never discard a player's pending portrait gesture.
            apexFormsNativeIntent=null;apexFormsBootstrap=true;apexFormsDesiredId=value;
            context.owner_id=value;context.owner_deadline_tick=int(apexTimer.currentCount)+20;
            reply.mutation_started=true;
            // The pinned native hook recognizes this reserved token and binds
            // the staged existing owner. It never calls the kind converter.
            CommunicationManager.CallGameService("SetSimOccult",index); return;
         }
         if(operation=="pair-link" || operation=="pair-copy") {
            var pair:Object=ApexPairRead();
            if((parts.length!=2 && parts.length!=3) || pair==null) throw new Error("Exact native portrait pair required");
            var pairIntent:Object={sim_id:apexBoundSim,operation:operation=="pair-copy"?"copy":"link",enabled:false};
            if(parts.length==3) {
               if(!/^(0|[1-9][0-9]{0,9})$/.test(parts[2]) || Number(parts[2])>4294967295)
                  throw new Error("Exact typed pair category flags required");
               pairIntent.category_flags=Number(parts[2]);
            }
            if(operation=="pair-link") {
               var other:String=pair.base_owner_id==pair.human_owner_id?pair.alternate_owner_id:pair.base_owner_id;
               if(parts[0]!==other || !/^[01]$/.test(parts[1])) throw new Error("Link request targets another form");
               pairIntent.source_owner_id=pair.base_owner_id;pairIntent.target_owner_id=pair.alternate_owner_id;pairIntent.enabled=parts[1]=="1";
            } else {pairIntent.source_owner_id=String(parts[0]);pairIntent.target_owner_id=String(parts[1]);}
            reply.mutation_started=true;context.control=ApexPairExecute(pairIntent);context.control.operation=operation;
            CommunicationManager.CallUIService("ApexConfigureFormPortraits",{sim_id:apexBoundSim,refresh_pair:true});return;
         }
         if(operation=="form-menu") {
            if(!/^[a-z0-9_][a-z0-9_-]{0,63}$/.test(value) || apexFormsRoot==null || apexFormsDragging ||
               apexFormsDesiredId!="" || apexFormsNativeIntent!=null || apexFormsNativeState!="bound")
               throw new Error("Life-state menu is not ready for browsing");
            ApexFormsGroupCatalog();var foundFamily:Boolean=value=="all";
            for each(var menuGroup:Object in apexFormsGroups) if(menuGroup.family==value) foundFamily=true;
            if(!foundFamily) throw new Error("Life-state family is absent from this Sim's captured forms");
            context.control={operation:operation};reply.mutation_started=true;
            apexFormsVariantFamily=value=="all"?"":value;apexFormsPage=0;apexFormsCollapsed=false;apexFormsSignature="";
            return;
         }
         if(operation=="workspace") {
            if(parts.length!=5 || !/^(0|1)(\.[0-9]+)?$/.test(String(parts[0])) ||
               !/^(0|1)(\.[0-9]+)?$/.test(String(parts[1])) ||
               !/^[01](\.[0-9]+)?$/.test(String(parts[2])) ||
               !/^[01]$/.test(String(parts[3])) || !/^[01]$/.test(String(parts[4])))
               throw new Error("CAS workspace requires typed position, scale and explicit toggles");
            var workspaceX:Number=Number(parts[0]); var workspaceY:Number=Number(parts[1]); var workspaceScale:Number=Number(parts[2]);
            if(!isFinite(workspaceX) || !isFinite(workspaceY) || !isFinite(workspaceScale) ||
               workspaceX<0 || workspaceX>1 || workspaceY<0 || workspaceY>1 || workspaceScale<0.7 || workspaceScale>1.5 ||
               apexFormsRoot==null || apexFormsDragging)
               throw new Error("CAS workspace must be visible, in bounds and not being dragged");
            context.control={operation:operation,before:ApexFormsStatus()}; reply.mutation_started=true;
            ApexFormsApply(workspaceX,workspaceY,workspaceScale,String(parts[3])=="1",String(parts[4])=="1"); return;
         }
         if(operation=="occults" || operation=="occult-view" || operation=="occult-cache-view" || operation=="occult-owner-view") {
            data=ApexClone(CommunicationManager.CallGameService("CASGetSimInfo",null,true));
            if(!data || !(data.allOccultTypes is int) || !(data.occultType is int) || !(data.occultLayer is int))
               throw new Error("Native occult view identity is unavailable");
            var occultCatalog:Object=ApexClone(CommunicationManager.CallGameService("CasGetAvailableOccults",{simId:String(data.simId)}));
            if(!occultCatalog || !(occultCatalog.avail_occult is Array))
               throw new Error("Native occult catalog is unavailable");
            context.control={operation:operation,occults:occultCatalog.avail_occult};
            if(operation=="occults") { data=null;occultCatalog=null;return; }
            var ownerProbe:Boolean=operation=="occult-owner-view";
            var cacheProbe:Boolean=operation=="occult-cache-view" || ownerProbe;
            if(state!=apexOwnerSession || parts.length!=(cacheProbe?3:2) || String(data.householdId)!=parts[0] ||
               int(data.occultLayer)!=int(parts[1]) || int(data.allOccultTypes)!=category ||
               index<(ownerProbe?1:2) || (index & (index-1))!=0 || (!cacheProbe && (category & index)!=index) ||
               CommunicationManager.CallGameService("CasIsForcedFullEditingEnabled",null,true)!==true)
               throw new Error("Occult view requires the exact existing membership, session, household and full CAS editor");
            if(cacheProbe && (int(parts[2])<1 || int(parts[2])>127 || index>64 ||
               (int(parts[2]) & index)!=index || (category & ~int(parts[2]))!=0))
               throw new Error("Experimental cache view lacks captured existing ownership");
            var editMode:* = ApexClone(CommunicationManager.CallGameService("CasGetCASEditMode"));
            if(!(editMode is int) || (int(editMode)!=0 && int(editMode)!=7))
               throw new Error("Occult view requires an existing household CAS visit");
            context.occultBefore={all_occult_types:int(data.allOccultTypes),occult_type:int(data.occultType),layer:int(data.occultLayer)};
            if(int(data.occultType)==index) { data=null;occultCatalog=null;return; }
            data=null;occultCatalog=null;reply.mutation_started=true;
            // Normal navigation retains its strict full-mask contract. The
            // separate disposable-only qualification tests the native cache;
            // pair projection is not evidence of persistent membership loss.
            CommunicationManager.CallGameService("SetSimOccult",index);return;
         }
         if(operation=="voices" || operation=="voice-actor" || operation=="voice-pitch") {
            data=ApexClone(CommunicationManager.CallGameService("CASGetSimInfo",null,true));
            if(!data || !(data.voiceActor is uint) || !(data.voicePitch is Number))
               throw new Error("Native current voice is unavailable");
            rows=ApexClone(CommunicationManager.CallGameService("GetVoicesDataForAgeSpecies",
               {species:data.speciesType,age:data.age},true)) as Array;
            if(rows==null || rows.length==0 || int(data.voiceActor)<1 || int(data.voiceActor)>rows.length)
               throw new Error("Eligible native voice inventory is unavailable");
            context.control={operation:operation,voices:rows};
            if(operation=="voices") { data=null; rows=null; return; }
            if(data.occultLayer!==0 || CommunicationManager.CallGameService("CasIsForcedFullEditingEnabled",null,true)!==true)
               throw new Error("Voice edits require the primary original Sim in full edit mode");
            if(operation=="voice-actor") {
               if(index<0 || index>=rows.length) throw new Error("Voice index is outside the eligible native inventory");
               data=null; rows=null; reply.mutation_started=true;
               CommunicationManager.CallGameService("SetSimVoiceActor",index); return;
            }
            var pitch:Number=Number(value); row=rows[int(data.voiceActor)-1];
            if(!row || !isFinite(pitch) || !("minPitch" in row) || !("maxPitch" in row) ||
               !isFinite(Number(row.minPitch)) || !isFinite(Number(row.maxPitch)) ||
               pitch<Number(row.minPitch) || pitch>Number(row.maxPitch))
               throw new Error("Voice pitch is outside the exact selected voice's native bounds");
            data=null; rows=null; row=null; reply.mutation_started=true;
            CommunicationManager.CallGameService("SetSimVoicePitch",{value:pitch,slider_mouse_up:true}); return;
         }
         if(operation=="walkstyles" || operation=="walkstyle") {
            data=ApexClone(CommunicationManager.CallGameService("CASGetSimInfo",null,true));
            if(!data) throw new Error("Native walkstyle Sim context is unavailable");
            rows=ApexClone(CommunicationManager.CallGameService("CasGetWalkCycleTraits",{simId:String(data.simId)},true)) as Array;
            if(rows==null) throw new Error("Native walkstyle inventory is unavailable");
            context.control={operation:operation,walkstyles:rows};
            if(operation=="walkstyles") { data=null; rows=null; return; }
            if(data.occultLayer!==0 || data.speciesType!=1 || data.isGhost===true || data.isRobot===true ||
               CommunicationManager.CallGameService("CasIsForcedFullEditingEnabled",null,true)!==true)
               throw new Error("Walkstyle edits require an eligible primary human Sim in full edit mode");
            var walkMatches:int=0;
            for each(row in rows) if(row && String(row.id)==value) walkMatches++;
            if(walkMatches!=1) throw new Error("Requested walkstyle lacks one exact eligible native trait");
            context.walkstyleBefore=ApexClone(rows); data=null; rows=null; row=null; reply.mutation_started=true;
            CommunicationManager.CallGameService("CasSetWalkCycleTrait",{traitID:value}); return;
         }
         if(operation=="detail-status" || operation=="detail-mode") {
            if(!this.mcDetailedEditModePanel) throw new Error("Native detailed edit control is unavailable");
            context.control={operation:operation,active:this.mcDetailedEditModePanel.IsActive()};
            if(operation=="detail-status") return;
            if(value!="0" && value!="1") throw new Error("Detailed edit mode requires an explicit desired state");
            if(Boolean(context.control.active)!=(value=="1")) {
               reply.mutation_started=true; this.mcDetailedEditModePanel.ToggleAdvancedMode();
            }
            return;
         }
         if(operation=="filters" || operation=="filter-clear") {
            HandleContextMenuSetMenuState({menuState:state,skipAnim:true,setZoomState:true});
            if(!this.mCurrentPanel || !this.mCurrentPanel.mcFilterPane)
               throw new Error("Requested native panel has no catalog filter control");
            if(operation=="filter-clear") this.mCurrentPanel.mcFilterPane.ClearSelections();
            return;
         }
         if(operation=="hair-matching" || operation=="hair-match") {
            var flags:* = CommunicationManager.CallGameService("CasGetHairMatchingFlags",null,true);
            if(!(flags is int) || int(flags)<0 || int(flags)>63) throw new Error("Native hair matching flags are unavailable");
            context.control={operation:operation,flags:int(flags)}; flags=null;
            if(operation=="hair-matching") return;
            if(!/^[0-9]+$/.test(value) || int(value)<0 || int(value)>63) throw new Error("Invalid native hair matching mask");
            data=CommunicationManager.CallGameService("CASGetSimInfo",null,true);
            if(!data || data.speciesType!=1) throw new Error("Human hair matching flags require the human species context");
            data=null; reply.mutation_started=true;
            CommunicationManager.CallGameService("CasSetHairMatchingFlags",int(value),true); return;
         }
         if(operation=="modifiers" || operation=="color-sliders") {
            HandleContextMenuSetMenuState({menuState:state,skipAnim:true,setZoomState:true});
            if(index<-1 || category<0 || category>=127 || (index==-1)!=(category==0)) throw new Error("Invalid exact modifier layer");
            if(MenuState.SupportsLayerList(state)!=(index>=0)) throw new Error("Layered modifiers require an explicit native layer");
            rows=CommunicationManager.CallGameService("GetCatalogItemsSelectedWithModifiers",{state:state}) as Array;
            matches=0;
            if(rows) for each(row in rows) if(row && String(row.dataID)==String(parts[0])) { data=ApexClone(row); matches++; }
            rows=null; row=null;
            if(matches!=1) throw new Error("Native modifiers lack one exact equipped identity");
            if(index>=0) {
               var modifierProduct:Object=CommunicationManager.CallGameService("GetCatalogItem",String(parts[0]));
               if(!modifierProduct || !("body_type" in modifierProduct)) throw new Error("Layered modifier body type is unavailable");
               var modifierBody:int=int(modifierProduct.body_type); modifierProduct=null;
               var modifierLayers:Array=CASAPI.GetBodyTypeLayers(modifierBody);
               if(modifierLayers==null || index>=modifierLayers.length || modifierLayers[index].layerId!=category ||
                  String(modifierLayers[index].partKey)!=String(parts[0])) throw new Error("Equipped modifier layer identity differs");
               modifierLayers=null;
            }
            context.control={operation:operation,selected:ApexClone(data)};
            if(operation=="modifiers") { data=null; return; }
            if(parts.length!=5) throw new Error("Color sliders require all four values");
            var names:Array=["hue","opacity","saturation","value"];
            var colorPayload:Object={data_id:String(parts[0]),slider_mouse_up:true,layer_index:index,layer_id:category,menu_state:state};
            for(n=0;n<names.length;n++) {
               var field:String=String(names[n]); var number:Number=Number(parts[n+1]);
               if(!isFinite(number) || !(field+"_range_min" in data) || !(field+"_range_max" in data) ||
                  !isFinite(Number(data[field+"_range_min"])) || !isFinite(Number(data[field+"_range_max"])) ||
                  number<Number(data[field+"_range_min"]) || number>Number(data[field+"_range_max"]))
                  throw new Error("Color slider is outside the exact native part's returned range");
               colorPayload[field+"_range_modifier"]=number;
            }
            context.beforeModifiers=ApexClone(data); data=null; reply.mutation_started=true;
            CommunicationManager.CallGameService("SetCatalogSlotSelected",colorPayload); return;
         }
         if(operation=="swatches" || operation=="swatch") {
            if(state<0 || state>16 || state==5) throw new Error("Native palette requires its supported typed color context");
            if(operation=="swatch" && state==3)
               HandleContextMenuSetMenuState({menuState:MenuState.PROFILE_HAIR_EYEBROWS,skipAnim:true,setZoomState:true});
            rows=ApexClone(CommunicationManager.CallGameService("CasGetSwatchColorList",state)) as Array;
            if(rows==null) throw new Error("Native palette is unavailable");
            if(operation=="swatches") {
               if(category<0 || index<1 || index>32) throw new Error("Invalid native palette page");
               context.control={operation:operation,offset:category,limit:index,total:rows.length,
                  items:ApexClone(rows.slice(category,category+index)),
                  selected:ApexClone(CommunicationManager.CallGameService("CasGetSwatchColorSelected",state))};
               rows=null; return;
            }
            var matches:int=0;
            for each(row in rows) if(row && String(row.dataID)==value) { data=row; matches++; }
            if(matches!=1 || !("color" in data)) throw new Error("Native palette lacks one exact requested swatch");
            var modifier:Number=("value_range_modifier" in data ? Number(data.value_range_modifier) : 0);
            if(!isFinite(modifier)) throw new Error("Native palette modifier is not finite");
            var fur:Array=null;
            if(state==6) {
               fur=ApexClone(CommunicationManager.CallGameService("CasGetSwatchColorSelected",state)) as Array;
               if(fur==null || index<0 || index>=fur.length) throw new Error("Native fur palette slot does not exist");
               fur[index]=value;
            } else if(index!=0) throw new Error("Only fur palettes have indexed colors");
            var swatchPayload:Object={dataId:value,swatchType:state,colorId:ApexClone(data.color),
               furColors:fur,value_range_modifier:modifier};
            if(state==3) {
               data=null; row=null; reply.mutation_started=true;
               reply.eyebrow_widget=ApexSelectEyebrowSwatch(value,rows); rows=null; return;
            }
            data=null; rows=null; row=null;
            reply.mutation_started=true;
            CommunicationManager.CallGameService("CasSetSwatchColorSelected",swatchPayload);
            return;
         }
         if(operation=="physique") {
            if(state!=0 && state!=1) throw new Error("Unknown native physique slider");
            var newValue:Number=Number(value);
            data=CommunicationManager.CallGameService("CASGetSimInfo",null,true);
            if(!data || !(data.physiqueValues is Array) || data.physiqueValues.length<=state ||
               !isFinite(newValue) || newValue<0 || newValue>1 || !isFinite(Number(data.physiqueValues[state])))
               throw new Error("Native physique values are unavailable or outside the slider range");
            context.physique_start_value=Number(data.physiqueValues[state]);
            context.physique_layer=int(data.occultLayer);context.physique_owner_id=apexFormsSelectedId;
            var physiquePayload:Object={type:state,value:newValue,slider_mouse_up:false,slider_start_value:context.physique_start_value};
            data=null;
            var physiqueKind:* = CommunicationManager.CallGameService("GetSimOccult");
            if(!(physiqueKind is int)) throw new Error("Native physique form identity is unavailable");
            context.physique_kind=int(physiqueKind);context.physique_commit_pending=true;
            // Match the stock SmoothSlider SNAP -> DRAG_END lifecycle. A fresh
            // form's first edit must initialize its preview/undo gesture before
            // the mouse-up commit; a completion-only call skips that contract.
            data=null; reply.mutation_started=true;
            CommunicationManager.CallGameService("SetSimPhysiqueValue",physiquePayload);
            return;
         }
         if(operation=="body-types" || operation=="body-type") {
            HandleContextMenuSetMenuState({menuState:state,skipAnim:true,setZoomState:true});
            context.control={operation:operation,body_types:ApexBodyTypes(operation=="body-type" ? category : 0),
               body_type:ClothingPanel(this.mCurrentPanel).mcBodyTypePanel.GetSelected()};
            return;
         }
         if(operation!="catalog" && operation!="variants" && operation!="preset" && operation!="select-layer" &&
            operation!="remove" && operation!="layers" && operation!="layer-add" && operation!="layer-remove" && operation!="layer-move")
            throw new Error("Unsupported typed native CAS control");
         HandleContextMenuSetMenuState({menuState:state,skipAnim:true,setZoomState:true});
         rows=ApexCatalog(state);
         if(operation=="catalog") {
            if(category<0 || index<1 || index>32) throw new Error("Invalid native catalog page");
            context.control={operation:operation,offset:category,limit:index,total:rows.length,
               items:ApexClone(rows.slice(category,category+index))};
            rows=null; return;
         }
         if(operation=="preset") {
            if(state==MenuState.PROFILE_HAIR_EYEBROWS || state==MenuState.PROFILE_PET_WHISKERS)
               throw new Error("This native face panel uses equipped parts; use exact part selection");
            if(!(this.mCurrentPanel is FaceModPanel) && !(this.mCurrentPanel is BodyModPanel) && !(this.mCurrentPanel is GenericCatalogPanel))
               throw new Error("Requested panel does not use the native preset contract");
            matches=0;
            for(n=0;n<rows.length;n++) if(rows[n] && String(rows[n].data_id)==value) { matches++; context.preset_index=n; }
            if(matches!=1) throw new Error("Native filtered preset catalog lacks one exact requested item");
            context.preset_id=value; rows=null;
            reply.mutation_started=true;
            CommunicationManager.CallGameService("SetCatalogSlotSelected",value);
            return;
         }
         if(operation=="layers" || operation=="layer-add" || operation=="layer-remove" || operation=="layer-move" || operation=="select-layer") {
            if(!(this.mCurrentPanel is ClothingPanel) || !MenuState.SupportsLayerList(state))
               throw new Error("Requested panel has no native tattoo layer list");
            var bodyPresent:Boolean=false;
            for each(row in rows) if(row && int(row.body_type)==category) bodyPresent=true;
            if(!bodyPresent) throw new Error("Requested body type is absent from the native tattoo catalog");
            rows=null; row=null;
            var nativeLayers:Array=ApexNativeLayers(category);
            context.before=ApexClone(nativeLayers); nativeLayers=null;
            if(operation=="layers") return;
            if(operation=="layer-add") {
               if(context.before.length==0)
                  throw new Error("First-tattoo insertion is unavailable after failed native runtime validation; no layer added");
               var used:Object={}; var ordinaryCount:int=0;
               for each(row in context.before) {
                  used[String(row.layerId)]=true;
                  if(int(row.layerId)!=127) ordinaryCount++;
               }
               // Five is the installed native layer component's capacity.
               if(ordinaryCount>=5) throw new Error("Native tattoo layer capacity is reached");
               layerId=1;
               while(used[String(layerId)] && layerId<127) layerId++;
               if(layerId>=127) throw new Error("No native tattoo layer identity is available");
               row=null; reply.mutation_started=true;
               CASAPI.AddEmptyLayer(category,context.before.length,layerId);
               return;
            }
            layerId=int(operation=="select-layer" ? parts[1] : parts[0]);
            if(operation=="select-layer" && context.before.length==0)
               throw new Error("First-tattoo insertion is unavailable after failed native runtime validation; no part changed");
            if(index<0 || index>=context.before.length || int(context.before[index].layerId)!=layerId || layerId==127)
               throw new Error("Native tattoo layer identity changed or names the protected medical layer");
            if(operation=="layer-remove") {
               reply.mutation_started=true; CASAPI.RemoveBodyTypeLayer(category,index); return;
            }
            if(operation=="layer-move") {
               target=int(parts[1]);
               if(target<0 || target>=context.before.length || int(context.before[target].layerId)==127)
                  throw new Error("Native tattoo target layer does not exist or is medical");
               reply.mutation_started=true; CASAPI.MoveBodyTypeLayers(category,index,target); return;
            }
            value=String(parts[0]);
         }
         data=CommunicationManager.CallGameService("GetCatalogItem",value);
         if(data==null || !("body_type" in data) || int(data.body_type)<=0)
            throw new Error("Native product has no exact body identity");
         if(operation=="variants") {
            context.control={operation:operation,data_id:value,
               family:ApexClone(CommunicationManager.CallGameService("GetCatalogColorFamilies",{base:String(data.data_id),simId:"0",targetSimId:"0"}))};
            data=null; return;
         }
         if(operation=="remove") {
            if(MenuState.SupportsLayerList(state)) throw new Error("Use the typed layer removal contract for tattoos");
            rows=CommunicationManager.CallGameService("GetCatalogItemsSelectedWithModifiers",{state:state}) as Array;
            matches=0;
            for each(row in rows) if(row && String(row.dataID)==value) matches++;
            if(matches!=1) throw new Error("Only one exact currently equipped item may be removed");
            var removePayload:Object={body_type:int(data.body_type),layer_index:MenuState.GetRemoveBodyTypeFixedLayerIndex(state,int(data.body_type))};
            context.removed_data_id=value;
            data=null; rows=null; row=null; reply.mutation_started=true;
            CommunicationManager.CallGameService("ClearSelectedBodyType",removePayload); return;
         }
         if(operation!="select-layer" || int(data.body_type)!=category) throw new Error("Native tattoo item belongs to a different body type");
         rows=ApexCatalog(state); bodyPresent=false;
         for each(row in rows) if(row && String(row.data_id)==String(data.data_id) && int(row.body_type)==category) bodyPresent=true;
         if(!bodyPresent) throw new Error("Native tattoo product is absent from the requested filtered catalog");
         var colors:Object=CommunicationManager.CallGameService("GetCatalogColorFamilies",{base:String(data.data_id),simId:"0",targetSimId:"0"});
         var color:Object=null; matches=0;
         if(colors && colors.mItems is Array) for each(row in colors.mItems)
            if(row && String(row.dataID)==value) { color=row; matches++; }
         if(matches!=1) throw new Error("Native tattoo selection requires one exact returned variant");
         var payload:Object={data_id:value,layer_index:index,layer_id:layerId,slider_mouse_up:true,
            hue_range_modifier:("hue_range_modifier" in color ? Number(color.hue_range_modifier) : 0),
            opacity_range_modifier:("opacity_range_modifier" in color ? Number(color.opacity_range_modifier) : 1),
            saturation_range_modifier:("saturation_range_modifier" in color ? Number(color.saturation_range_modifier) : 0),
            value_range_modifier:("value_range_modifier" in color ? Number(color.value_range_modifier) : 0)};
         if(!isFinite(payload.hue_range_modifier) || !isFinite(payload.opacity_range_modifier) ||
            !isFinite(payload.saturation_range_modifier) || !isFinite(payload.value_range_modifier))
            throw new Error("Native tattoo color modifier is not finite");
         data=null; rows=null; row=null; colors=null; color=null; reply.mutation_started=true;
         CommunicationManager.CallGameService("SetCatalogSlotSelected",payload);
      }

      private function ApexControlResult(operation:String,state:int,category:int,index:int,value:String,context:Object,client:Object) : Object
      {
         if(operation=="catalog-width-drag") {
            if(apexColumns==null || stage==null || context.width_drag==null || context.width_drag.handler_invoked!==true ||
               context.width_drag_panel!==mCurrentPanel || mCurrentPanel==null || !mCurrentPanel.visible ||
               mCurrentPanel.mcTileList.mGridLayout!==context.width_drag_grid ||
               context.width_drag_handle!==apexColumns.width_handle || context.width_drag_handle.parent!==mCurrentPanel ||
               context.width_drag_handle.stage!==stage || !context.width_drag_handle.visible || apexColumns.resize!=null ||
               int(mCurrState)!==context.width_drag.menu_state || stage.stageWidth!==context.width_drag.stage_width ||
               stage.stageHeight!==context.width_drag.stage_height)
               throw new Error("Width drag lost its physical handle before readback");
            return {operation:operation,workspace:client.catalog_workspace,drag:context.width_drag,appearance_written:false};
         }
         if(operation=="catalog-layout-trace") return {operation:operation,trace:client.catalog_workspace.layout_trace,appearance_written:false};
         if(operation=="catalog-trace") return {operation:operation,trace:client.catalog_workspace.draw_trace,appearance_written:false};
         // The same Timer readback already captured this workspace. Repeating
         // display-bound diagnostics here traverses the physical cards twice.
         if(operation=="catalog-input") return {operation:operation,workspace:client.catalog_workspace,handler_invoked:true,focus_requested:String(value.split(",")[1])=="1",appearance_write_possible:String(value.split(",")[0])=="enter"};
         if(operation=="catalog-companion") return {operation:operation,workspace:client.catalog_workspace,appearance_write_possible:String(value.split(",")[0])=="random-favorite"};
         if(operation=="catalog-state" || operation=="panel-layout" || operation=="catalog-style" || operation=="catalog-open" || operation=="catalog-view" || operation=="catalog-slider" || operation=="catalog-cards" || operation=="catalog-card-reset" || operation=="catalog-key" || operation=="catalog-search")
            return {operation:operation,workspace:client.catalog_workspace,appearance_written:false};
         if(operation=="form-owner-select") return {operation:operation,owner_id:String(context.owner_id)};
         if(operation=="pair-link" || operation=="pair-copy") {
            var currentPair:Object=ApexPairRead();
            if(currentPair==null) throw new Error("Pair disappeared before the next-frame acknowledgement");
            context.control.pair=currentPair;return context.control;
         }
         if(operation=="form-menu") {
            var menu:Object=ApexFormsStatus();
            return {operation:operation,life_states:menu.life_states,variant_family:menu.variant_family,appearance_written:false};
         }
         if(operation=="workspace") {
            var workspace:Object=ApexFormsStatus();
            return {operation:operation,layout:workspace.layout,visible:workspace.visible,appearance_written:false,before:context.control.before};
         }
         if(operation=="occults" || operation=="occult-view" || operation=="occult-cache-view" || operation=="occult-owner-view") {
            var occultCatalog:Object=ApexClone(CommunicationManager.CallGameService("CasGetAvailableOccults",{simId:String(client.sim.simId)}));
            if(!occultCatalog || !(occultCatalog.avail_occult is Array))throw new Error("Native occult catalog readback is unavailable");
            return {operation:operation,occults:occultCatalog.avail_occult,before:context.occultBefore};
         }
         if(operation=="voices" || operation=="voice-actor" || operation=="voice-pitch") return context.control;
         if(operation=="walkstyles") return context.control;
         if(operation=="walkstyle") {
            var walkstyles:Array=ApexClone(CommunicationManager.CallGameService("CasGetWalkCycleTraits",{simId:String(client.sim.simId)},true)) as Array;
            if(walkstyles==null) throw new Error("Native walkstyle readback is unavailable");
            return {operation:operation,walkstyles:walkstyles,before:context.walkstyleBefore};
         }
         if(operation=="detail-status" || operation=="detail-mode")
            return {operation:operation,active:this.mcDetailedEditModePanel.IsActive()};
         if(operation=="filters" || operation=="filter-clear") {
            if(!this.mCurrentPanel || !this.mCurrentPanel.mcFilterPane)
               throw new Error("Native catalog filter pane disappeared before readback");
            return {operation:operation,filters:ApexClone(this.mCurrentPanel.mcFilterPane.GetCatalogFilter()),
               selected_bubble_empty:Boolean(this.mCurrentPanel.mcFilterPane.mcFilterBubble.txtTitle.visible)};
         }
         if(operation=="catalog" || operation=="variants" || operation=="swatches") return context.control;
         if(operation=="body-types" || operation=="body-type") {
            if(!(this.mCurrentPanel is ClothingPanel) ||
               ClothingPanel(this.mCurrentPanel).mcBodyTypePanel.GetSelected()!=context.control.body_type)
               throw new Error("Native body region changed before next-tick readback");
            return context.control;
         }
         var result:Object={operation:operation};
         if(operation=="hair-matching") return context.control;
         if(operation=="hair-match") {
            var flags:* = CommunicationManager.CallGameService("CasGetHairMatchingFlags",null,true);
            if(!(flags is int) || int(flags)!=int(value)) throw new Error("Native hair matching flags did not retain the requested mask");
            result.flags=int(flags); flags=null; return result;
         }
         if(operation=="modifiers") return context.control;
         if(operation=="color-sliders") {
            var parts:Array=value.split(","); var count:int=0; var selected:Object=null;
            if(client.selected is Array) for each(var modified:Object in client.selected)
               if(modified && String(modified.dataID)==String(parts[0])) { selected=ApexClone(modified); count++; }
            modified=null;
            if(count!=1) throw new Error("Native color slider equipped identity did not read back");
            result.selected=selected; result.before=context.beforeModifiers; return result;
         }
         if(operation=="preset") {
            var preset:Object=CommunicationManager.CallGameService("GetSelectedPresetFromMenuState",state,true);
            if(preset==null || !(preset.index is int) || int(preset.index)!=int(context.preset_index))
               throw new Error("Native preset did not read back the exact requested catalog index");
            var presetIndex:int=int(preset.index);
            result.selected_data_id=value; result.preset=ApexClone(preset); result.preset_query="returned-value";
            preset=null;
            var current:Array=ApexCatalog(state);
            if(presetIndex<0 || presetIndex>=current.length || String(current[presetIndex].data_id)!=value)
               throw new Error("Native preset catalog changed before selection readback");
            current=null; preset=null;
         } else if(operation=="swatch") {
            result.selected=ApexClone(CommunicationManager.CallGameService(state==0 ? "CasGetSwatchColorSelectedWithModifier" : "CasGetSwatchColorSelected",state));
         } else if(operation=="physique") {
            if(!(client.sim.physiqueValues is Array) || client.sim.physiqueValues.length<=state ||
               Math.abs(Number(client.sim.physiqueValues[state])-Number(value))>0.000001)
               throw new Error("Native physique slider did not read back the requested value");
            this.mcBodyModSliderPanel.HandleCASPhysiqueValues(client.sim.physiqueValues);
         } else if(operation=="remove") result.removed_data_id=context.removed_data_id;
         else {
            result.body_type=category; result.before=context.before;
            result.layers=ApexClone(ApexNativeLayers(category));
            ClothingPanel(this.mCurrentPanel).mcLayerComponent.Refresh(category);
         }
         return result;
      }

      private function ApexNativeLayers(bodyType:int) : Array
      {
         var layers:Array=CASAPI.GetBodyTypeLayers(bodyType);
         if(layers!=null) return layers;
         // The installed CASLayerComponent displays its fake empty layer for
         // null native storage. Require both exact native empty predicates
         // before exposing an empty list; painted/unknown storage stays blocked.
         var occupied:* = CommunicationManager.CallGameService("CasHasPartOrTattooPaintLayer",bodyType);
         var painted:* = CommunicationManager.CallGameService("CasGetPartTattooPaintLayerPresent",bodyType);
         if(!(occupied is Boolean) || occupied!==false || !(painted is Boolean) || painted!==false)
            throw new Error("Native body-type layers are unavailable or contain unrepresented paint");
         return [];
      }

      private function ApexBodyTypes(target:int) : Array
      {
         if(!(this.mCurrentPanel is ClothingPanel) || !MenuState.SupportsBodyTypeFilter(this.mCurrState))
            throw new Error("Native panel has no body-region selector");
         var panel:CASBodyTypePanel=ClothingPanel(this.mCurrentPanel).mcBodyTypePanel;
         if(panel==null || panel.mcSelectionGrid==null) throw new Error("Native body-region grid is unavailable");
         var sim:Object=ApexClone(CommunicationManager.CallGameService("CASGetSimInfo",null,true));
         if(sim==null || !(sim.occultType is int)) throw new Error("Native body-region occult context is unavailable");
         var rows:Array=TattooBodyData.DATA as Array;
         if(rows==null || rows.length==0 || rows.length>128) throw new Error("Native body-region definitions are unavailable");
         var types:Array=[]; var seen:Object={};
         for each(var row:Object in rows) {
            if(row==null || !(row.type is int) || int(row.type)<=0 || seen[String(row.type)])
               throw new Error("Native body-region definition is ambiguous");
            seen[String(row.type)]=true;
            if("occults_blacklist" in row) {
               if(!(row.occults_blacklist is Array)) throw new Error("Native body-region occult filter is unavailable");
               if(row.occults_blacklist.indexOf(sim.occultType)!=-1) continue;
            }
            types.push(int(row.type));
         }
         var selected:Array=panel.mcSelectionGrid.GetSelectedIndices();
         if(selected==null || selected.length!=1 || int(selected[0])<0 || int(selected[0])>=types.length ||
            panel.GetSelected()!=int(types[int(selected[0])]))
            throw new Error("Native body-region grid differs from its exact filtered definitions");
         if(target!=0) {
            var index:int=types.indexOf(target);
            if(index<0) throw new Error("Requested body region is unavailable for this native occult");
            // PC has no mGridInputAdapter. Its public selection grid emits the
            // same typed selection event used by mouse selection, followed by
            // the native region-change event, without controller navigation.
            if(panel.GetSelected()!=target) {
               if(!panel.mcSelectionGrid.SetSelection(index,true,true) || panel.GetSelected()!=target)
                  throw new Error("Native body-region selection did not retain the exact requested type");
               panel.dispatchEvent(new GenericEvent(GenericEvent.CHANGE));
            }
         }
         return types;
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
         var reply:Object={ok:false,protocol:1,scope:"native-cas-client",cas_request_id:id,mutation_started:false};
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
            // APEX_TIMER_TRACE_BEGIN execute-native-begin
            if(apexCatalogTrace!=null && apexCatalogTrace.enabled===true && apexCatalogTrace.timer_profile!=null) ApexCatalogTimerStep("native-info.enter");
            // APEX_TIMER_TRACE_END execute-native-begin
            var native:Object=CommunicationManager.CallGameService("CASGetSimInfo",null,true);
            // APEX_TIMER_TRACE_BEGIN execute-native-end
            if(apexCatalogTrace!=null && apexCatalogTrace.enabled===true && apexCatalogTrace.timer_profile!=null) ApexCatalogTimerStep("native-info.leave");
            // APEX_TIMER_TRACE_END execute-native-end
            if(!native || String(native.simId)!=String(fields[1])) throw new Error("CAS selected Sim differs from request");
            var keyboardNavigation:Boolean=operation=="catalog-key" || operation=="catalog-input" && String(fields[6].split(",")[0])!="enter";
            var catalogSelected:Object=(ApexCatalogReadbackOnly(operation) || operation=="panel-navigation" || keyboardNavigation) ? ApexOwnerSimRow(native) : null;
            native=null;
            if(ApexCatalogReadbackOnly(operation)) apexPendingContext.catalog_before=ApexCatalogReadbackContext(catalogSelected);
            if(operation=="panel-navigation") apexPendingContext.navigation_before=ApexCatalogReadbackContext(catalogSelected);
            if(keyboardNavigation)apexPendingContext.keyboard_before=ApexCatalogReadbackContext(catalogSelected);
            catalogSelected=null;
            if(operation=="occult-owner-view")
               throw new Error("Cross-occult conversion is disabled; independent owner binding is required");
            var state:int=int(fields[3]);
            var category:int=int(fields[4]); var index:int=int(fields[5]); var value:String=fields[6];
            if(operation=="member-select") {
               var memberParts:Array=value.split(":");
               if(state!=0 || !/^[01]$/.test(String(fields[4])) || index<=0 || String(index)!=String(fields[5]) ||
                  memberParts.length!=2 || !/^[1-9][0-9]{0,19}$/.test(String(memberParts[0])) ||
                  !/^[1-9][0-9]{0,19}$/.test(String(memberParts[1])))
                  throw new Error("Member selection requires exact source layer/session/household/target");
               var memberBefore:Object=ApexMemberSelectionContext(String(fields[1]),String(memberParts[1]),String(memberParts[0]),category,index);
               apexPendingContext.member_before=memberBefore;
               apexPendingContext.target_sim_id=String(memberBefore.target_sim_id);
               if(String(fields[1])!=String(memberBefore.target_sim_id)) {
                  var memberIndex:int=int(memberBefore.target_index);
                  ApexCatalogGridInvalidate("member-intent");
                  reply.mutation_started=true;
                  // The installed selector's ordinary SelectSim handler keeps
                  // its native selected index/layer and displayed UI in sync.
                  CommunicationManager.SendMessage("CASSelectSim",memberIndex);
               } else if(category!=0) throw new Error("Same-member navigation cannot silently reset an alternate layer");
            } else if(operation=="form-select" || operation=="layer-select") {
               if(!(operation=="layer-select" ? /^[01]$/.test(String(fields[3])) : /^(1|2|4|8|16|32|64)$/.test(String(fields[3]))) ||
                  !/^[01]$/.test(String(fields[4])) || !/^[1-9][0-9]{0,9}$/.test(String(fields[5])) ||
                  String(index)!=String(fields[5]) || !/^[1-9][0-9]{0,19}$/.test(value))
                  throw new Error("CAS form selection requires exact form/current-layer/session/household fields");
               var selectionBefore:Object=ApexFormSelectionContext(String(fields[1]),value,category,state,index,
                  operation=="layer-select" ? state : -1);
               apexPendingContext.selection_before=selectionBefore;
               if(selectionBefore.selected_layer!=selectionBefore.target_layer) {
                  ApexCatalogGridInvalidate("layer-intent");
                  // Claim/phase are consumed before either native write. The
                  // index is the already selected same-original-ID pair only.
                  reply.mutation_started=true;
                  var navigation:Object=CommunicationManager.CallUIService("ApexNavigateOwnerLayer",{
                     request_id:String(fields[0]),sim_id:String(fields[1]),index:int(selectionBefore.selected_index),
                     expected_layer:int(selectionBefore.selected_layer),target_layer:int(selectionBefore.target_layer),
                     target_kind:int(selectionBefore.form_flags),feed_sequence:int(selectionBefore.feed_sequence)});
                  if(navigation==null || navigation.protocol!==1 || navigation.request_id!==String(fields[0]) ||
                     navigation.sim_id!==String(fields[1]) || navigation.submitted!==true || navigation.native_selector_handler!==true)
                     throw new Error("Native selector handler did not acknowledge this exact navigation intent");
               }
            } else if(operation=="panel" || operation=="panel-navigation") {
               reply.mutation_started=true;
               HandleContextMenuSetMenuState({menuState:state,skipAnim:true,setZoomState:true});
               // Notify the native radial widget too. A direct Customizer call
               // alone can leave its model attachment unset on fresh CAS entry.
               CommunicationManager.SendUIMessage("CASChangeMenuState",state);
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
               if(MenuState.SupportsLayerList(state)) throw new Error("Layered selection requires an explicit layer; no item changed");
               HandleContextMenuSetMenuState({menuState:state,skipAnim:true,setZoomState:true});
               if(!(this.mCurrentPanel is ClothingPanel) && !((this.mCurrentPanel is FaceModPanel) &&
                  (state==MenuState.PROFILE_HAIR_EYEBROWS || state==MenuState.PROFILE_PET_WHISKERS)) || state==MenuState.CLOTHING_LOOKS)
                  throw new Error("Use the native preset, swatch or featured-look contract for this panel");
               var selectionBase:String="";
               if(value.indexOf(",")>=0) {
                  if(!new RegExp("^[1-9][0-9]{0,19},[1-9][0-9]{0,19}$").test(value))
                     throw new Error("Explicit base/color selection requires one exact native catalog pair");
                  var selectionIds:Array=value.split(",");
                  selectionBase=String(selectionIds[0]); value=String(selectionIds[1]);
                  apexPendingContext.selection_variant_id=value;
                  if(state==MenuState.CLOTHING_BODY_WINGS) apexPendingContext.selection_base_id=selectionBase;
               }
               var product:Object=null;
               var available:Array=null;
               if(selectionBase!="") {
                  // A swatch need not be a card in the filtered base catalog
                  // and may omit body_type. Never guess its parent: the caller
                  // supplies the exact visible base and its returned variant.
                  available=ApexCatalog(state);
                  var baseMatches:int=0;
                  for each(var baseProduct:Object in available)
                     if(baseProduct && String(baseProduct.data_id)==selectionBase &&
                        ("body_type" in baseProduct) && int(baseProduct.body_type)>0 &&
                        (state!=MenuState.CLOTHING_BODY_WINGS || int(baseProduct.body_type)==CASBodyType.WINGS)) {
                        product=ApexClone(baseProduct); baseMatches++;
                     }
                  if(baseMatches!=1) throw new Error("Native catalog base is absent or ambiguous; no item changed");
               } else product=CommunicationManager.CallGameService("GetCatalogItem",value);
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
                   (state==MenuState.CLOTHING_ACCESSORIES_EARRINGS ? CASBodyType.EARRINGS :
                    (state==MenuState.CLOTHING_SHOES ? CASBodyType.SHOES : int(product.body_type))))));
               if(!("body_type" in product) || int(product.body_type)!=expectedBodyType)
                  throw new Error("Native catalog item's body type differs from the requested panel; no item changed");
               if(expectedBodyType<=0) throw new Error("Native catalog item has no typed body identity");
               if(available==null) available=ApexCatalog(state);
               var belongs:Boolean=false;
               for each(var availableProduct:Object in available)
                  if(availableProduct && String(availableProduct.data_id)==String(product.data_id) &&
                     int(availableProduct.body_type)==int(product.body_type)) belongs=true;
               if(!belongs) throw new Error("Exact native product is absent from the requested filtered panel; no item changed");
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
               if(selectionBase!="" && state!=MenuState.CLOTHING_BODY_WINGS)
                  apexPendingContext.catalog_selection={base_data_id:selectionBase,data_id:value,
                     body_type:int(product.body_type),filtered_base_matches:baseMatches,family_variant_matches:variantMatches};
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
               var secondMedical:Object=MenuState.GetBodyTypeFixedLayerIndexAndId(state,int(product.body_type),exactModifiers);
               if(state==MenuState.CLOTHING_BODY_WINGS)
                  exactModifiers={data_id:String(product.data_id),color_data_id:value};
               // FaceModPanel's native catalog click passes a STRING, unlike
               // ClothingPanel's modifier object. Its color is a separate
               // palette operation after the selected part has settled.
               var facePart:Boolean=state==MenuState.PROFILE_HAIR_EYEBROWS || state==MenuState.PROFILE_PET_WHISKERS;
               var faceBase:String=String(product.data_id);
               product=null; products=null; variantProduct=null; available=null; availableProduct=null; baseProduct=null;
               family=null; exactVariant=null; variant=null;
               reply.mutation_started=true;
               CommunicationManager.CallGameService("SetCatalogSlotSelected",facePart ? faceBase : exactModifiers);
               if(secondMedical!=null) CommunicationManager.CallGameService("SetCatalogSlotSelected",secondMedical);
               // Defer fresh swatch discovery until the next native UI tick.
               // Native product/color callers do not send a global catalog
               // refresh; duplicating that event can reenter native UI updates.
               if(state==MenuState.CLOTHING_HAIR || state==MenuState.PROFILE_HAIR_EYEBROWS) {
                  apexPendingContext.palette_type=state==MenuState.CLOTHING_HAIR ? 2 : 3;
                  apexPendingPhase=2;
               }
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
            } else if(operation!="status") ApexControlExecute(operation,state,category,index,value,reply,apexPendingContext);
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

      private function ApexComplete() : void
      {
         var reply:Object=apexPendingReply; var id:String=String(apexPendingFields[0]);
         // APEX_TIMER_TRACE_BEGIN ack-encode-begin
         if(apexCatalogTrace!=null && apexCatalogTrace.enabled===true && apexCatalogTrace.timer_profile!=null) ApexCatalogTimerStep("ack-encode.enter");
         // APEX_TIMER_TRACE_END ack-encode-begin
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
         // APEX_TIMER_TRACE_BEGIN ack-encode-end
         if(apexCatalogTrace!=null && apexCatalogTrace.enabled===true && apexCatalogTrace.timer_profile!=null) ApexCatalogTimerStep("ack-encode.leave");
         // APEX_TIMER_TRACE_END ack-encode-end
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

      private function ApexAcceptListen(enabled:Boolean) : void
      {
         removeEventListener(flash.events.Event.ENTER_FRAME,ApexAcceptReadyFrame);
         if(apexAcceptStage!=null) {
            apexAcceptStage.removeEventListener(flash.events.MouseEvent.MOUSE_DOWN,ApexAcceptUserInput,true);
            apexAcceptStage.removeEventListener(flash.events.KeyboardEvent.KEY_DOWN,ApexAcceptUserInput,true);
         }
         apexAcceptStage=null;
         if(!enabled) return;
         if(this.stage==null) throw new Error("Acceptance readiness lacks its original stage");
         apexAcceptStage=this.stage;
         apexAcceptStage.addEventListener(flash.events.MouseEvent.MOUSE_DOWN,ApexAcceptUserInput,true,1000,true);
         apexAcceptStage.addEventListener(flash.events.KeyboardEvent.KEY_DOWN,ApexAcceptUserInput,true,1000,true);
         addEventListener(flash.events.Event.ENTER_FRAME,ApexAcceptReadyFrame,false,-100,true);
      }

      private function ApexAcceptUserInput(event:flash.events.Event) : void
      {
         // Merely cancel our pending automation. EA receives the input normally.
         if(apexAcceptWait!=null && apexPendingPhase==9) apexAcceptInput=true;
      }

      private function ApexAcceptReadyFrame(event:flash.events.Event) : void
      {
         if(apexAcceptWait==null || apexPendingPhase!=9 || apexTicking) return;
         apexTicking=true;
         try { ApexAccept(); } finally { apexTicking=false; }
      }

      private function ApexAcceptAbort(message:String) : void
      {
         var held:Object=apexAcceptWait;
         ApexAcceptListen(false);apexAcceptWait=null;apexAcceptInput=false;
         if(held==null) return;
         try { CommunicationManager.CallGameService("GetSimOccult","APEXACCEPT1|CANCEL|"+held.request); } catch(cancelWaitError:Error) { }
         var cancelled:Object=held.reply;
         cancelled.message=message;cancelled.commit_attempted=false;cancelled.commit_submitted=false;
         cancelled.readiness_cancelled=true;
         apexPendingFields=null;apexPendingReply=null;apexPendingContext=null;
         apexPendingPhase=8;apexReadbackTick=-1;apexClaimNonce="";
         apexLastReply=ApexEncode(cancelled);
         if(apexSocketActive && apexNonce===held.owner) ApexSocketReply(held.id,apexLastReply);
      }

      private function ApexAcceptNative(held:Object,operation:String) : Array
      {
         var raw:* = CommunicationManager.CallGameService("GetSimOccult","APEXACCEPT1|"+operation+"|"+held.request);
         if(!(raw is String)) throw new Error("Native acceptance readiness is not a typed receipt");
         // Preserve a bounded native refusal. A generic shape error hides
         // which exact editor/owner check prevented the one save attempt.
         if(String(raw).indexOf("REFUSED|")===0 && String(raw).length<=1024)
            throw new Error("Native acceptance readiness refused: "+String(raw).substr(8));
         var fields:Array=String(raw).split("|");
         if(fields.length!=18 || fields[0]!="ACCEPTSTATE" || (fields[1]!="READY" && fields[1]!="WAIT") ||
            fields[2]!==held.simId || fields[3]!==held.household || fields[4]!=="0" ||
            held.mode===0 && ((fields[5]!==String(held.shell) &&
               !(operation==="PREPARE" && held.channel!="" && fields[5]===String(held.rendered))) ||
               fields[6]!==String(held.rendered) || fields[7]!==String(held.mask)) ||
            !/^(1|2|4|8|16|32|64)$/.test(fields[5]) || !/^(1|2|4|8|16|32|64)$/.test(fields[6]) ||
            !/^[0-9]{1,3}$/.test(fields[7]) || !/^[0-9]{1,3}$/.test(fields[8]) ||
            !/^[0-9a-f]{64}$/.test(fields[12]) || !/^[0-9]{1,20}$/.test(fields[13]) || !/^[0-9]{1,20}$/.test(fields[14]) ||
            !/^[0-9]{1,10}$/.test(fields[15]) || (fields[16]!="0" && fields[16]!="1") || fields[17]!=="1")
            throw new Error("Native acceptance readiness lost its exact editor/form identity");
         if(held.channel!="") {
            if(!/^[0-9a-f]{32}$/.test(fields[9]) || fields[10]!==held.formOwner || !/^[1-9][0-9]{0,19}$/.test(fields[11]))
               throw new Error("Native acceptance readiness lost its exact bound owner");
         } else if(fields[9]!=="-" || fields[10]!=="-" || fields[11]!=="0")
            throw new Error("Unbound acceptance readiness invented an owner");
         var ready:Boolean=fields[15]==="0" && fields[16]==="0";
         if((fields[1]==="READY")!==ready) throw new Error("Native acceptance ready flag differs from its genuine phase/model predicates");
         var stamp:String=fields.slice(2,15).join("|");
         if(operation==="PREPARE") {
            // The native once-only harvest can replace EA's layout shell with
            // this exact selected owner's rendered kind. The original request
            // stays immutable; all subsequent probes use the attested shell.
            if(held.mode===0) {held.shell=int(fields[5]);held.mask=int(fields[7]);}
            held.stamp=stamp;held.preparedGeneration=String(fields[11]);
         } else if(stamp!==held.stamp) throw new Error("Prepared native editor/household changed during readiness wait");
         return fields;
      }

      private function ApexAcceptReady(held:Object) : Boolean
      {
         var elapsed:int=getTimer()-int(held.started);
         if(elapsed<0 || elapsed>10000) throw new Error("Native editor readiness timed out before any save attempt");
         if(apexAcceptInput) throw new Error("User input cancelled pending acceptance; EA input was not blocked");
         if(apexDisconnected || !apexSocketActive || apexNonce!==held.owner || this.stage!==apexAcceptStage ||
            held.channel!="" && apexNativeChannel!==held.channel || apexFormsDesiredId!="" || apexFormsIntent!=null ||
            apexFormsNativeIntent!=null || apexMoleculeIntent!=null || apexPairIntent!=null || apexFormsApplying)
            throw new Error("Acceptance readiness lost its original room/nonce or has a pending edit");
         var fresh:Object=CommunicationManager.CallGameService("CASGetSimInfo",null,true);
         var freshMatches:Boolean=fresh!=null && String(fresh.simId)===held.simId && String(fresh.householdId)===held.household &&
            fresh.occultLayer is int && fresh.occultLayer===0 &&
            (held.mode===7 || fresh.occultType===held.shell && fresh.allOccultTypes===held.mask);
         fresh=null;
         var currentMode:* = CommunicationManager.CallGameService("CasGetCASEditMode");
         var currentNewFamily:* = CommunicationManager.CallGameService("CasIsNewFamily");
         var currentArea:Object=CommunicationManager.CallGameService("CasIsEnteredFromPlayArea");
         var currentFromLive:Boolean=currentArea!=null && currentArea.result===true;currentArea=null;
         if(!freshMatches || currentMode!==held.mode || currentNewFamily!==false || !currentFromLive)
            throw new Error("Acceptance readiness changed Sim/household/layer/editor mode");
         if(held.mode===0 && (CommunicationManager.CallGameService("GetSimOccult")!==held.rendered ||
            this.mCurrState!==MenuState.NONE || CASStateData.TattooMode!==false))
            throw new Error("Acceptance readiness reopened or changed the original preview/form");
         if(held.channel!="") {
            var currentOwner:String=ApexNativeExchange("STATE|"+held.channel);
            var expectedOwner:String="VIEWSTATE|"+held.simId+"|"+held.formOwner+"|"+held.rendered+"|0|bound|"+held.preparedGeneration;
            if(apexFormsNativeState!=="bound" || apexFormsSelectedId!==held.formOwner || currentOwner!==expectedOwner ||
               apexFormsNativeGeneration!==held.preparedGeneration)
               throw new Error("Acceptance readiness changed its original bound owner/generation");
         }
         var nativeReady:Array=ApexAcceptNative(held,"READY");
         held.reply.readiness_observations=int(held.reply.readiness_observations)+1;
         return nativeReady[1]==="READY";
      }

      private function ApexAccept() : void
      {
         var resuming:Boolean=apexPendingPhase==9 && apexAcceptWait!=null;
         if(!resuming && (apexPendingPhase!=6 || apexPendingFields==null || apexClaimNonce!=apexNonce ||
            !apexSocketActive || int(apexTimer.currentCount)<apexReadbackTick)) return;
         // Cache only owned identity/primitive values before native code can
         // synchronously unload this widget and clear its Timer/Socket fields.
         var id:String=resuming ? String(apexAcceptWait.id) : String(apexPendingFields[0]);
         var simId:String=resuming ? String(apexAcceptWait.simId) : String(apexPendingFields[1]);
         var owner:String=resuming ? String(apexAcceptWait.owner) : apexClaimNonce;
         var expectedHousehold:String=resuming ? String(apexAcceptWait.household) : String(apexPendingFields[6]);
         var preparedHousehold:String=apexPendingContext ? String(apexPendingContext.household_id) : "";
         var reply:Object={ok:false,protocol:1,scope:"native-cas-client",cas_request_id:id,operation:"accept",
            lifecycle_stage:"accept-result",commit_attempted:false,commit_submitted:false,ui_transition_verified:false};
         var commitAccepted:Boolean=false;
         try {
            if(resuming) reply=apexAcceptWait.reply;
            else {
            var sim:Object=CommunicationManager.CallGameService("CASGetSimInfo",null,true);
            var observedId:String=sim ? String(sim.simId) : "";
            var observedHousehold:String=sim && sim.householdId is String ? String(sim.householdId) : "";
            var observedLayer:* = sim ? sim.occultLayer : null;
            var observedShell:* = sim ? sim.occultType : null;
            var observedMask:* = sim ? sim.allOccultTypes : null;
            sim=null;
            var editMode:* = CommunicationManager.CallGameService("CasGetCASEditMode");
            var newFamily:* = CommunicationManager.CallGameService("CasIsNewFamily");
            var playArea:Object=CommunicationManager.CallGameService("CasIsEnteredFromPlayArea");
            var fromLive:Boolean=playArea!=null && playArea.result===true; playArea=null;
            if(observedId!=simId || expectedHousehold=="" || preparedHousehold!=expectedHousehold || observedHousehold!=expectedHousehold ||
               !(observedLayer is int) || int(observedLayer)!=0 ||
               !(editMode is int) || (int(editMode)!=0 && int(editMode)!=7) || newFamily!==false || !fromLive)
               throw new Error("Native CAS accept preconditions changed after intent acknowledgement; no commit submitted");
            // Capture only immutable identity before cleanup can synchronously
            // hide panels. Never carry borrowed Sim/native objects across it.
            var observedRendered:* = null;
            var acceptanceChannel:String="";
            var observedOwnerState:String="";
            if(editMode===0) {
               observedRendered=CommunicationManager.CallGameService("GetSimOccult");
               if(!(observedShell is int) || !(observedMask is int) || !(observedRendered is int))
                  throw new Error("Native household cleanup lacks its typed original form identity");
               // An already bound independent owner must remain the same exact
               // native cursor. Plain/native CAS without that binding keeps
               // its existing fresh Sim/editor guards; no owner is invented.
               if(apexFormsNativeState=="bound" || apexFormsSelectedId!="") {
                  acceptanceChannel=apexNativeChannel;
                  if(acceptanceChannel=="" || apexFormsNativeState!="bound" || apexFormsDesiredId!="" ||
                     apexFormsIntent!=null || apexFormsNativeIntent!=null || apexMoleculeIntent!=null || apexPairIntent!=null || apexFormsApplying)
                     throw new Error("Native household cleanup has an unresolved original form owner");
                  observedOwnerState=ApexNativeExchange("STATE|"+acceptanceChannel);
                  var ownerBefore:Array=observedOwnerState.split("|");
                  if(ownerBefore.length!=7 || ownerBefore[0]!="VIEWSTATE" || ownerBefore[1]!==simId ||
                     ownerBefore[2]!==apexFormsSelectedId ||
                     !/^[a-z0-9_][a-z0-9_-]{0,63}\/[a-z0-9_][a-z0-9_-]{0,63}$/.test(ownerBefore[2]) ||
                     ownerBefore[3]!==String(observedRendered) || ownerBefore[4]!==String(observedLayer) || ownerBefore[5]!="bound" ||
                     ownerBefore[6]!==apexFormsNativeGeneration || !/^[1-9][0-9]{0,19}$/.test(ownerBefore[6]))
                     throw new Error("Native household cleanup original owner/cursor differs");
                  ownerBefore=null;
               }
            }
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
            // Existing-household CAS follows Navigation.OnPlayButtonClicked,
            // not the single-Sim shortcut. Apply its pending name fields and
            // validate the family before SaveAndExitCAS. Consume the intent
            // first: an uncertain finalization must never be replayed.
            if(int(editMode)==0) {
               reply.household_finalization_attempted=true;
               var geneticsVisible:* = CommunicationManager.CallUIService("IsWidgetVisible","CASGeneticsPane");
               if(geneticsVisible!==false)
                  throw new Error("Native genetics panel is active or unverified; household commit not submitted");
               var namesApplied:* = CommunicationManager.CallUIService("CasApplyNameFields",false);
               if(namesApplied!==true)
                  throw new Error("Native household name finalization refused or is unverified; commit not submitted");
               // Match EA Navigation.EnterGame after FinalizeSimFamily's
               // genetics/name checks. Hiding the native Customizer leaves the
               // active category (including Medical/TattooMode) through its
               // original handler; no arbitrary panel/part is selected here.
               // The original intent was consumed above. Cache id/owner locally
               // and refuse if cleanup unexpectedly retires this CAS room.
               reply.household_cleanup_attempted=true;
               CommunicationManager.SendUIMessage("CASHidePersonalityAndGeneticsPanels",null);
               CommunicationManager.SendUIMessage("CASHideCustomizer",null);
               CommunicationManager.SendUIMessage("CASResetGhostToggle",null);
               CommunicationManager.SendUIMessage("CASResetWingToggle",null);
               if(apexDisconnected || !apexSocketActive || apexNonce!==owner || this.mCurrState!==MenuState.NONE ||
                  CASStateData.TattooMode!==false || acceptanceChannel!="" && apexNativeChannel!==acceptanceChannel)
                  throw new Error("Native household cleanup retired its room or did not leave the active panel; commit not submitted");
               var householdData:Object=CommunicationManager.CallGameService("CasGetHouseholdExchangeData",{bValidateExistingSimTraits:false});
               if(householdData==null)
                  throw new Error("Native household validation refused; commit not submitted");
               var validatedHousehold:ExchangeData=new ExchangeData(householdData);
               householdData=null;
               var hasAdult:Boolean=validatedHousehold.HouseholdContainsAdults();
               validatedHousehold=null;
               if(!hasAdult)
                  throw new Error("Native household has no teen or adult; commit not submitted");
               var profanity:Object=CommunicationManager.CallGameService("CASCheckProfanityOnSimNames",null);
               if(profanity!=null && profanity.simId && String(profanity.simId)!="0")
                  throw new Error("Native name warning requires an explicit user decision; commit not submitted");
               profanity=null;
               // Finalization may refresh the selection; preserve the exact
               // original Sim and creature layer before the one native save.
               var finalizedSim:Object=CommunicationManager.CallGameService("CASGetSimInfo",null,true);
               var finalizedLayer:* = finalizedSim ? finalizedSim.occultLayer : null;
               var finalizedShell:* = finalizedSim ? finalizedSim.occultType : null;
               var finalizedMask:* = finalizedSim ? finalizedSim.allOccultTypes : null;
               var finalizedMatches:Boolean=finalizedSim!=null && String(finalizedSim.simId)==simId &&
                  String(finalizedSim.householdId)==expectedHousehold;
               finalizedSim=null;
               var finalizedRendered:* = CommunicationManager.CallGameService("GetSimOccult");
               var finalizedMode:* = CommunicationManager.CallGameService("CasGetCASEditMode");
               var finalizedNewFamily:* = CommunicationManager.CallGameService("CasIsNewFamily");
               var finalizedPlayArea:Object=CommunicationManager.CallGameService("CasIsEnteredFromPlayArea");
               var finalizedFromLive:Boolean=finalizedPlayArea!=null && finalizedPlayArea.result===true;finalizedPlayArea=null;
               if(!(finalizedLayer is int) || int(finalizedLayer)!=0 || !finalizedMatches ||
                  finalizedShell!==observedShell || finalizedMask!==observedMask || finalizedRendered!==observedRendered ||
                  finalizedMode!==editMode || finalizedNewFamily!==false || !finalizedFromLive ||
                  apexDisconnected || !apexSocketActive || apexNonce!==owner ||
                  acceptanceChannel!="" && (apexNativeChannel!==acceptanceChannel || ApexNativeExchange("STATE|"+acceptanceChannel)!==observedOwnerState))
                  throw new Error("Native household cleanup/finalization changed the bound Sim/form/editor; commit not submitted");
               reply.household_cleanup_verified=true;
               reply.household_finalization_verified=true;
            }
            var formOwner:String=acceptanceChannel!="" ? String(observedOwnerState.split("|")[2]) : "-";
            var originalGeneration:String=acceptanceChannel!="" ? String(observedOwnerState.split("|")[6]) : "0";
            apexAcceptWait={id:id,simId:simId,owner:owner,household:expectedHousehold,mode:int(editMode),
               shell:observedShell,mask:observedMask,rendered:observedRendered,channel:acceptanceChannel,formOwner:formOwner,
               started:getTimer(),reply:reply,request:id+"|"+owner+"|"+simId+"|"+expectedHousehold+"|"+
                  (acceptanceChannel!="" ? acceptanceChannel : "0")+"|0|"+
                  (editMode===0 ? String(acceptanceChannel!="" ? observedRendered : observedShell)+"|"+String(observedRendered)+"|"+String(observedMask) : "-|-|-")+"|"+formOwner+"|"+originalGeneration};
            reply.readiness_observations=0;apexAcceptInput=false;
            apexPendingPhase=9;ApexAcceptListen(true);
            ApexAcceptNative(apexAcceptWait,"PREPARE"); // Exactly one authoritative harvest, before waiting.
            if(acceptanceChannel!="") apexFormsNativeGeneration=apexAcceptWait.preparedGeneration;
            }
            if(!ApexAcceptReady(apexAcceptWait)) return;
            ApexAcceptListen(false);apexAcceptWait=null;apexAcceptInput=false;
            apexPendingPhase=7;
            reply.readiness_verified=true;
            reply.commit_attempted=true;
            var accepted:* = CommunicationManager.CallGameService("SaveAndExitCAS",{bValidateExistingSimTraits:false,apex_accept_id:id,apex_accept_nonce:owner});
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
         if(apexAcceptWait!=null) {
            try { CommunicationManager.CallGameService("GetSimOccult","APEXACCEPT1|CANCEL|"+apexAcceptWait.request); } catch(acceptCancelError:Error) { }
         }
         ApexAcceptListen(false);apexAcceptWait=null;apexAcceptInput=false;
         apexPendingFields=null; apexPendingReply=null; apexPendingContext=null;
         apexPendingPhase=reply.commit_outcome=="unresolved" ? 7 : 0;
         apexReadbackTick=-1; apexClaimNonce="";
         apexLastReply=ApexEncode(reply);
         if(apexSocketActive && apexNonce==owner) ApexSocketReply(id,apexLastReply);
      }
