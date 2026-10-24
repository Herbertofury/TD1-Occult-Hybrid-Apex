// First-party native CAS display and same-pair navigation. This never calls
// SetSimOccult: converting kinds is quarantined independently of this widget.
      private var apexFormsRoot:flash.display.Sprite;
      private var apexFormsSignature:String = "";
      private var apexFormsOwnedMask:int = 0;
      private var apexFormsCatalog:Object;
      private var apexFormsIntent:Object;
      private var apexFormsResult:Object;
      private var apexFormsMessage:String = "";
      private var apexFormsApplying:Boolean = false;
      private var apexFormsPosition:flash.geom.Point;
      private var apexFormsScale:Number = 1;
      private var apexFormsLocked:Boolean = false;
      private var apexFormsCollapsed:Boolean = false;
      private var apexFormsDragging:Boolean = false;
      private var apexFormsPanelWidth:Number = 554;
      private var apexFormsHousehold:String = "";
      private var apexFormsLayerButtons:Array;
      private var apexFormsGestureSequence:int = 0;
      private var apexFormsOwners:Array=[];
      private var apexFormsCatalogPages:Object={};
      private var apexFormsLocalCatalog:Boolean=false;
      private var apexFormsLocalOffset:int=0;
      private var apexFormsOwnerTotal:int=-1;
      private var apexFormsSelectedId:String="";
      private var apexFormsNativeState:String="";
      private var apexFormsDesiredId:String="";
      private var apexFormsNativeIntent:Object;
      private var apexFormsBootstrap:Boolean=false;
      private var apexFormsPage:int=0;
      private var apexFormsPanelHeight:Number=146;
      private var apexFormsGroups:Array=[];
      private var apexFormsVariantFamily:String="";
      private var apexFormsTooltips:Array=[];
      private var apexFormsGroupKey:String="";
      private var apexFormsFrameQueued:Boolean=false;
      private var apexFormsFastState:Boolean=false;
      private var apexFormsNativeGeneration:String="";
      private var apexFormsGestureStarted:int=-1;
      private var apexFormsSwitchMilliseconds:int=-1;
      private var apexMoleculeIntent:Object;
      private var apexInputSamples:int=0;
      private var apexInputOverBudget:int=0;
      private var apexInputMaxMs:int=0;
      private var apexInputTotalMs:Number=0;


      private function ApexFormsDispose() : void
      {
         ApexPairDispose();
         removeEventListener(flash.events.Event.ENTER_FRAME,ApexFormsNextFrame);
         apexFormsFrameQueued=false;apexFormsFastState=false;apexFormsNativeGeneration="";
         apexFormsGestureStarted=-1;apexFormsSwitchMilliseconds=-1;
         apexMoleculeIntent=null;
         ApexFormsClearTooltips();
         if(apexFormsRoot!=null) {
            apexFormsRoot.stopDrag();
            apexFormsRoot.removeEventListener(flash.events.MouseEvent.CLICK,ApexFormsClick);
            apexFormsRoot.removeEventListener(flash.events.MouseEvent.MOUSE_DOWN,ApexFormsDragStart);
            apexFormsRoot.removeEventListener(flash.events.MouseEvent.DOUBLE_CLICK,ApexFormsResetPosition);
            if(apexFormsRoot.parent!=null) apexFormsRoot.parent.removeChild(apexFormsRoot);
         }
         if(stage!=null) stage.removeEventListener(flash.events.MouseEvent.MOUSE_UP,ApexFormsDragEnd);
         if(stage!=null) stage.removeEventListener(flash.events.Event.DEACTIVATE,ApexFormsDragCancel);
         if(stage!=null) stage.removeEventListener(flash.events.Event.MOUSE_LEAVE,ApexFormsDragCancel);
         apexFormsRoot=null; apexFormsSignature=""; apexFormsCatalog=null;
         apexFormsOwnedMask=0; apexFormsIntent=null; apexFormsResult=null; apexFormsMessage=""; apexFormsApplying=false;
         apexFormsDragging=false;
         apexFormsHousehold="";
         apexFormsLayerButtons=null;
         apexFormsOwners=[];apexFormsOwnerTotal=-1;apexFormsSelectedId="";apexFormsNativeState="";
         apexFormsCatalogPages={};apexFormsLocalCatalog=false;apexFormsLocalOffset=0;
         apexFormsDesiredId="";apexFormsNativeIntent=null;apexFormsBootstrap=false;apexFormsPage=0;apexFormsPanelHeight=146;
         apexFormsGroups=[];apexFormsVariantFamily="";apexFormsGroupKey="";
      }

      private function ApexFormsText(parent:flash.display.Sprite,text:String,x:Number,y:Number,width:Number,size:int,color:uint) : flash.text.TextField
      {
         var label:flash.text.TextField=new flash.text.TextField();
         // These aliases are taken from the installed CAS DefineEditText
         // font classes. System Arial is not available in the game renderer.
         label.embedFonts=true;
         label.defaultTextFormat=new flash.text.TextFormat("$TextFont",size,color);
         label.text=text; label.x=x; label.y=y; label.width=width; label.height=size+9;
         label.selectable=false; label.mouseEnabled=false;
         parent.addChild(label); return label;
      }

      private function ApexFormsButton(kind:int,layer:int,title:String,icon:String,selected:Boolean,enabled:Boolean,x:Number,y:Number) : void
      {
         var button:flash.display.Sprite=new flash.display.Sprite();
         button.name="apexForm_"+kind+"_"+layer; button.x=x; button.y=y;
         button.graphics.beginFill(selected ? 0xe8f8c9 : 0xffffff,0.98);
         button.graphics.lineStyle(selected ? 2 : 1,selected ? 0x7cb737 : 0xb4cee1,1);
         button.graphics.drawRoundRect(0,0,72,60,12,12); button.graphics.endFill();
         button.buttonMode=enabled; button.mouseChildren=false; button.mouseEnabled=enabled;
         button.alpha=1;
         apexFormsRoot.addChild(button);
         if(icon!="") {
            // Use the existing exported native symbol: the embedded class
            // carries the image component's real Scaleform asset definition.
            var image:Object=new IconComponentResource();
            image.x=21; image.y=5; image.mouseEnabled=false;
            // Add to the live display list BEFORE loading. The native image
            // component initializes its stage/load listeners at this point.
            button.addChild(image); image.ResetImageSize(30,30); image.LoadImage(icon);
         } else if(kind==1) {
            button.graphics.beginFill(0x85d849,1);
            button.graphics.moveTo(36,5); button.graphics.lineTo(46,20); button.graphics.lineTo(36,36);
            button.graphics.lineTo(26,20); button.graphics.lineTo(36,5); button.graphics.endFill();
            button.graphics.beginFill(0xbdf686,1);
            button.graphics.moveTo(36,5); button.graphics.lineTo(36,36); button.graphics.lineTo(26,20);
            button.graphics.lineTo(36,5); button.graphics.endFill();
         }
         var label:flash.text.TextField=ApexFormsText(button,title,1,37,70,10,selected ? 0x256207 : 0x315778);
         label.multiline=true;label.wordWrap=true;label.height=25;
         var format:flash.text.TextFormat=label.defaultTextFormat; format.align="center"; label.setTextFormat(format);
      }

      private function ApexFormsTick(sim:Object) : void
      {
         if(stage==null || sim==null || String(sim.simId)!=apexBoundSim || apexFormsOwnedMask==0 || apexFormsDragging) return;
         if(apexFormsOwners.length>0 && apexFormsOwners.length==apexFormsOwnerTotal) { ApexFormsOwnedTick(sim);return; }
         if(!isFinite(apexFormsScale) || apexFormsScale<0.7 || apexFormsScale>1.5) apexFormsScale=1;
         // Live entry is needed for a captured original. Other editors retain
         // their ordinary EA interface until a complete owner is available.
         var busy:Boolean=ApexFormsCommandBlocksInput();
         if(apexFormsLayerButtons!=null) for each(var layerControl:Object in apexFormsLayerButtons) {
            layerControl.button.mouseEnabled=!busy && int(layerControl.layer)!=int(sim.occultLayer);
            layerControl.button.buttonMode=layerControl.button.mouseEnabled;
         }
         if(apexFormsResult!=null && apexFormsResult.pending===true) {
            if(String(sim.simId)!=apexFormsResult.sim_id || int(sim.occultLayer)!=apexFormsResult.layer ||
               int(sim.occultType)!=apexFormsResult.kind || int(sim.allOccultTypes)!=apexFormsResult.mask)
               apexFormsMessage="Form change did not match its native readback. Further strip input is blocked.";
            else apexFormsMessage="Each retained form keeps its own edits. Review changes when returning to Live.";
            apexFormsResult.verified=apexFormsMessage.indexOf("did not match")<0;
            apexFormsResult.pending=false;
         }
         if(apexFormsIntent!=null && !busy && apexAwaiting=="") {
            var intent:Object=apexFormsIntent; apexFormsIntent=null;
            try {
               if(apexFormsResult!=null && apexFormsResult.verified!==true)
                  throw new Error("Previous form selection is unresolved");
               if(String(sim.simId)!=intent.sim_id || int(sim.occultLayer)!=intent.source_layer ||
                  int(sim.allOccultTypes)!=intent.mask || intent.session!=apexOwnerSession)
                  throw new Error("Selection changed before this form button was applied");
               apexFormsApplying=true;
               var context:Object;
               try {
                  context=ApexFormSelectionContext(intent.sim_id,String(sim.householdId),intent.source_layer,
                     intent.kind,apexOwnerSession,intent.layer,true);
               } finally { apexFormsApplying=false; }
               if(context.selected_layer!=context.target_layer) {
                  // Consume the user gesture before the first native call.
                  apexFormsResult={sim_id:intent.sim_id,layer:int(context.target_layer),kind:int(context.form_flags),
                     mask:int(sim.allOccultTypes),verified:false,pending:true};
                  var navigation:Object=CommunicationManager.CallUIService("ApexNavigateOwnerLayer",{
                     request_id:String(intent.request_id),sim_id:String(intent.sim_id),index:int(context.selected_index),
                     expected_layer:int(context.selected_layer),target_layer:int(context.target_layer),
                     target_kind:int(context.form_flags),feed_sequence:int(context.feed_sequence)});
                  if(navigation==null || navigation.protocol!==1 || navigation.request_id!==String(intent.request_id) ||
                     navigation.sim_id!==String(intent.sim_id) || navigation.submitted!==true || navigation.native_selector_handler!==true)
                     throw new Error("Native selector did not acknowledge this exact form-button intent");
                  apexFormsSignature=""; return;
               }
            } catch(selectionError:Error) { apexFormsMessage=selectionError.message; }
         }
         var signature:String=apexBoundSim+":"+sim.occultType+":"+sim.occultLayer+":"+sim.allOccultTypes+":"+
            apexFormsOwnedMask+":"+stage.stageWidth+":"+stage.stageHeight+":"+apexFormsMessage+":"+
            apexFormsScale+":"+apexFormsLocked+":"+apexFormsCollapsed;
         if(signature==apexFormsSignature) return;
         apexFormsSignature=signature;
         if(apexFormsRoot==null) {
            apexFormsRoot=new flash.display.Sprite(); apexFormsRoot.name="ApexHybridForms";
            apexFormsRoot.addEventListener(flash.events.MouseEvent.CLICK,ApexFormsClick,false,0,true);
            apexFormsRoot.addEventListener(flash.events.MouseEvent.MOUSE_DOWN,ApexFormsDragStart,false,0,true);
            apexFormsRoot.addEventListener(flash.events.MouseEvent.DOUBLE_CLICK,ApexFormsResetPosition,false,0,true);
            addChild(apexFormsRoot);
         }
         while(apexFormsRoot.numChildren>0) apexFormsRoot.removeChildAt(0);
         apexFormsLayerButtons=[];
         var kinds:Array=[1,2,4,8,16,32,64];
         var names:Array=["Human","Alien","Vampire","Mermaid","Spellcaster","Werewolf","Fairy"];
         if(apexFormsCatalog==null || apexFormsCatalog.sim_id!=apexBoundSim) {
            var catalog:Object=ApexClone(CommunicationManager.CallGameService("CasGetAvailableOccults",{simId:apexBoundSim}));
            apexFormsCatalog={sim_id:apexBoundSim,icons:{}};
            if(catalog!=null && catalog.avail_occult is Array) for each(var item:Object in catalog.avail_occult)
               if(item!=null && item.occult_type is int && item.icon is String) {
                  var iconData:Object=ApexClone(CommunicationManager.CallGameService("GetOccultIcon",int(item.occult_type)));
                  apexFormsCatalog.icons[String(item.occult_type)]=iconData!=null && iconData.icon!=null &&
                     iconData.icon.instance is String ? String(iconData.icon.instance) : String(item.icon);
                  iconData=null;
               }
            catalog=null;
         }
         var count:int=0;
         for each(var k:int in kinds) if((apexFormsOwnedMask & k)!=0) count++;
         apexFormsPanelWidth=Math.max(350,count*78+8);
         var panelHeight:Number=apexFormsCollapsed ? 34 : 146;
         apexFormsRoot.graphics.clear(); apexFormsRoot.graphics.beginFill(0x214c71,0.16);
         apexFormsRoot.graphics.drawRoundRect(-6,-3,apexFormsPanelWidth+4,panelHeight+4,18,18); apexFormsRoot.graphics.endFill();
         apexFormsRoot.graphics.beginFill(0xf4fbff,0.97); apexFormsRoot.graphics.lineStyle(2,0xffffff,0.95);
         apexFormsRoot.graphics.drawRoundRect(-8,-6,apexFormsPanelWidth+4,panelHeight,16,16); apexFormsRoot.graphics.endFill();
         var handle:flash.display.Sprite=new flash.display.Sprite(); handle.name="apexDragHandle";
         handle.graphics.beginFill(0xdceefa,1); handle.graphics.drawRoundRect(-7,-5,apexFormsPanelWidth+2,32,14,14); handle.graphics.endFill();
         handle.mouseChildren=false; handle.buttonMode=!apexFormsLocked; handle.doubleClickEnabled=true;
         apexFormsRoot.addChild(handle);
         for(var dot:int=0;dot<6;dot++) {
            handle.graphics.beginFill(0x81a9c6,0.9); handle.graphics.drawCircle(4+(dot%2)*5,5+int(dot/2)*5,1.3); handle.graphics.endFill();
         }
         ApexFormsText(handle,"HYBRID FORMS",18,0,170,14,0x2765a2);
         ApexFormsToolbar("smaller","-",apexFormsPanelWidth-190);
         ApexFormsToolbar("larger","+",apexFormsPanelWidth-163);
         ApexFormsToolbar("lock",apexFormsLocked ? "Unlock" : "Lock",apexFormsPanelWidth-134,49);
         ApexFormsToolbar("reset","Reset",apexFormsPanelWidth-82,47);
         ApexFormsToolbar("collapse",apexFormsCollapsed ? "+" : "-",apexFormsPanelWidth-32);
         ApexFormsPlace();
         if(apexFormsCollapsed) return;
         var observation:Object=ApexOwnerObservation();
         var layers:Array=ApexFormsLayers(observation);
         var column:int=0;
         for(var i:int=0;i<kinds.length;i++) {
            k=int(kinds[i]); if((apexFormsOwnedMask & k)==0) continue;
            var selected:Boolean=int(sim.occultType)==k;
            var icon:String=apexFormsCatalog.icons.hasOwnProperty(String(k)) ? String(apexFormsCatalog.icons[String(k)]) : "";
            // Kind conversion remains blocked. A locked card is still shown
            // so native CAS filtering cannot conceal an owned occult.
            var cardLayer:int=-1; var matches:int=0;
            for each(var nativeLayer:Object in layers) if(int(nativeLayer.form_flags)==k) {
               cardLayer=int(nativeLayer.layer); matches++;
            }
            if(matches!=1) cardLayer=-1;
            ApexFormsButton(k,cardLayer,String(names[i]),icon,selected,!busy && cardLayer>=0 && !selected,column++*78,33);
         }
         // The native pair owns the primary/alternate distinction, including
         // Alien's actual layer zero and Vampire's two type-four layers.
         var layerX:int=0;
         for each(var row:Object in layers) {
            var text:String=String(row.label);
            var layerButton:flash.display.Sprite=new flash.display.Sprite();
            layerButton.name="apexLayer_"+int(row.layer); layerButton.x=layerX; layerButton.y=99;
            layerButton.graphics.beginFill(row.selected===true ? 0xe1f3bd : 0xffffff,1);
            layerButton.graphics.lineStyle(1,row.selected===true ? 0x7cb737 : 0x9dbfd9,1);
            layerButton.graphics.drawRoundRect(0,0,147,25,16,16); layerButton.graphics.endFill();
            layerButton.mouseChildren=false; layerButton.buttonMode=!busy && row.selected!==true;
            layerButton.mouseEnabled=layerButton.buttonMode;
            apexFormsLayerButtons.push({button:layerButton,layer:int(row.layer)});
            ApexFormsText(layerButton,text,7,3,136,12,row.selected===true ? 0x306609 : 0x2765a2); apexFormsRoot.addChild(layerButton); layerX+=153;
         }
         ApexFormsText(apexFormsRoot,apexFormsMessage!="" ? apexFormsMessage : "Other forms are retained. Cross-occult switching is unavailable in this build.",
            2,125,apexFormsPanelWidth-8,11,0x55778f);
         observation=null; layers=null;
      }

      private function ApexFormsLayers(observation:Object) : Array
      {
         var result:Array=[];
         if(observation==null || observation.stable!==true || observation.selected==null ||
            observation.selector_feed==null || observation.selector_feed.retained==null) return result;
         var feed:Object=observation.selector_feed.retained;
         var raw:Object=observation.selector_feed.raw_feed;
         if(feed.available!==true || feed.complete!==true || !(feed.pairs is Array) ||
            raw==null || raw.complete!==true || raw.delivered!==true || !(raw.pairs is Array) ||
            raw.pairs.length!=feed.pairs.length ||
            !(feed.selected_index is int) || feed.selected_index<0 || feed.selected_index>=feed.pairs.length ||
            feed.selected_sim_id!=apexBoundSim) return result;
         var pair:Object=feed.pairs[int(feed.selected_index)];
         if(pair==null || pair.base==null || pair.alternate==null ||
            pair.base.sim_id!=apexBoundSim || pair.alternate.sim_id!=apexBoundSim) return result;
         var selected:Object=int(feed.selected_layer)==0 ? pair.base : pair.alternate;
         if(selected.occult_layer!==observation.selected.occult_layer || selected.occult_type!==observation.selected.occult_type ||
            selected.all_occult_types!==observation.selected.all_occult_types) return result;
         for(var layer:int=0;layer<2;layer++) {
            var row:Object=layer==0 ? pair.base : pair.alternate;
            if(!(row.occult_type is int) || !(row.occult_layer is int) || row.occult_layer!=layer) return [];
            var kind:int=int(row.occult_type);
            var label:String=layer==0 ? "Primary form" : "Alternate form";
            if(kind==1) label="Human";
            else if(kind==2) label="Alien";
            else if(kind==4) label=layer==0 ? "Vampire" : "Vampire dark form";
            else if(kind==8) label="Mermaid";
            else if(kind==16) label="Spellcaster";
            else if(kind==32) label="Werewolf";
            else if(kind==64) label=layer==0 ? "Fairy" : "Fairy alternate";
            result.push({layer:layer,label:label,form_flags:kind,selected:int(feed.selected_layer)==layer});
         }
         return result;
      }

      private function ApexFormsObservedSim() : Object
      {
         // Identity only. Do not serialize all household pairs and the category
         // panel every rendered frame. Native state revalidates before writes.
         var row:Object=this.mCurrSimInfo;
         if(row==null || !(row.simId is String) || row.simId!==apexBoundSim ||
            !/^[1-9][0-9]{0,19}$/.test(row.simId) || !(row.occultType is int) ||
            !(row.occultLayer is int) || (row.occultLayer!=0 && row.occultLayer!=1) ||
            !(row.allOccultTypes is int)) return null;
         return {simId:String(row.simId),householdId:apexFormsHousehold,occultType:int(row.occultType),
            occultLayer:int(row.occultLayer),allOccultTypes:int(row.allOccultTypes)};
      }

      private function ApexMoleculeChooseOccult(request:Object) : Boolean
      {
         var inputStarted:int=getTimer();
         // The EA molecule's choice is an appearance selection for a retained
         // hybrid, never a destructive native genus conversion. Only enqueue;
         // the existing UI timer revalidates and consumes the exact owner token.
         // Input callbacks use the UI's retained Sim record. CASGetSimInfo
         // synchronizes/serializes the native model and belongs off this path.
         var sim:Object=this.mCurrSimInfo;
         if(sim==null) return true;
         var mask:int=int(sim.allOccultTypes)&~1;
         if(apexFormsOwners.length==0 && (mask==0 || (mask&(mask-1))==0)) return false;
         if(apexDisconnected || request==null || !(request.sim_id is String) ||
            request.sim_id!==apexBoundSim || String(sim.simId)!==apexBoundSim ||
            !(request.kind is int) || [1,2,4,8,16,32,64].indexOf(int(request.kind))<0) return true;
         var forms:Object={1:"human/shared",2:"alien/alien",4:"vampire/dark",8:"mermaid/mermaid",
            16:"witch/primary",32:"werewolf/beast",64:"fairy/primary"};
         for each(var owner:Object in apexFormsOwners) if(owner.form_id===forms[String(request.kind)]) {
            // Keep the latest explicit choice until the current command has
            // completed. A status/readback lease must not silently eat a click.
            // Bind it to this exact Sim/session, never carry it to a new editor.
            apexMoleculeIntent={sim_id:apexBoundSim,session:apexOwnerSession,
               owner_id:String(owner.id),token:int(owner.token),queued_at:getTimer()};
            apexFormsMessage="Switching to "+String(owner.label)+"...";
            apexFormsSignature="";ApexFormsScheduleFrame();ApexInputTiming(inputStarted);return true;
         }
         apexFormsMessage="This occult has no captured independent appearance yet.";
         apexFormsSignature="";return true;
      }

      private function ApexMoleculeReadSelection(request:Object=null) : Object
      {
         if(apexDisconnected || apexFormsOwners.length==0 || apexBoundSim=="") return null;
         var kind:* = CommunicationManager.CallGameService("GetSimOccult");
         if(!(kind is int) || [1,2,4,8,16,32,64].indexOf(int(kind))<0) return null;
         return {protocol:1,sim_id:apexBoundSim,kind:int(kind)};
      }

      private function ApexMoleculeDrain() : void
      {
         if(apexMoleculeIntent==null) return;
         if(apexMoleculeIntent.sim_id!==apexBoundSim || apexMoleculeIntent.session!==apexOwnerSession) {
            apexMoleculeIntent=null;return;
         }
         if(ApexFormsCommandBlocksInput() ||
            apexFormsDesiredId!="" || apexFormsNativeIntent!=null || apexFormsNativeState!="bound") return;
         var intent:Object=apexMoleculeIntent;apexMoleculeIntent=null;
         if(!Boolean(CommunicationManager.CallGameService("CasIsForcedFullEditingEnabled"))) {
            apexFormsMessage="Open full CAS to change the selected occult appearance.";apexFormsSignature="";return;
         }
         for each(var owner:Object in apexFormsOwners) if(owner.id===intent.owner_id && int(owner.token)==int(intent.token)) {
            if(owner.id!==apexFormsSelectedId) {
               apexFormsGestureStarted=int(intent.queued_at);apexFormsNativeIntent=ApexClone(owner);
            } else apexFormsMessage="";
            apexFormsSignature="";return;
         }
         apexFormsMessage="The selected form changed before this choice could be applied.";
         apexFormsSignature="";
      }

      private function ApexObserveMolecule(message:Object) : void
      {
         // Data-only event: no native reads/writes or UI transitions here.
         if(message==null || !(message.sim_id is String) ||
            !/^[1-9][0-9]{0,19}$/.test(message.sim_id) || !(message.kind is int) ||
            !(message.visible is Boolean) || !(message.enabled is Boolean) ||
            !(message.occult_count is int) || message.occult_count<0 || message.occult_count>32) return;
         for each(var key:String in ["x","y","width","height"])
            if(!(message[key] is Number) || !isFinite(Number(message[key])) || Math.abs(Number(message[key]))>16384) return;
         apexMoleculeView=ApexClone(message);
      }

      private function ApexMoleculeListen(enable:Boolean) : void
      {
         if(enable) apexMoleculeListener=AddMessageListener("ApexMoleculeObserved",ApexObserveMolecule);
         else {
            if(apexMoleculeListener) RemoveMessageListener("ApexMoleculeObserved",ApexObserveMolecule);
            apexMoleculeListener=false;apexMoleculeView=null;
         }
      }

      private function ApexFormsClick(event:flash.events.MouseEvent) : void
      {
         if(event!=null && event.target!=null && String(event.target.name).indexOf("apexTool_")==0) {
            ApexFormsToolbarClick(String(event.target.name).substr(9)); return;
         }
         if(event==null || event.target==null || apexFormsIntent!=null ||
            apexFormsResult!=null && apexFormsResult.verified!==true) return;
         var name:String=String(event.target.name);
         if(name.indexOf("apexGroup_")==0) {
            var groupIndex:int=int(name.substr(10));
            if(groupIndex<0 || groupIndex>=apexFormsGroups.length) return;
            var group:Object=apexFormsGroups[groupIndex];
            if(group.indices.length>1 || group.family=="imaginary_friend") {
               apexFormsVariantFamily=String(group.family);apexFormsPage=0;apexFormsSignature="";
               ApexFormsScheduleFrame();
            } else if(apexFormsOwners[int(group.indices[0])].id!=apexFormsSelectedId || apexMoleculeIntent!=null || apexFormsNativeIntent!=null || apexFormsDesiredId!="")
               ApexFormsQueueOwner(apexFormsOwners[int(group.indices[0])]);
            return;
         }
         if(name.indexOf("apexOwned_")==0) {
            var ownerIndex:int=int(name.substr(10));
            if(ownerIndex<0 || ownerIndex>=apexFormsOwners.length) return;
            if(apexFormsOwners[ownerIndex].id!=apexFormsSelectedId || apexMoleculeIntent!=null || apexFormsNativeIntent!=null || apexFormsDesiredId!="") ApexFormsQueueOwner(apexFormsOwners[ownerIndex]);
            apexFormsVariantFamily="";apexFormsPage=0;apexFormsSignature="";ApexFormsScheduleFrame();return;
         }

         var target:String="";
         if(name.indexOf("apexLayer_")==0) target=name.substr(10);
         else if(name.indexOf("apexForm_")==0) {
            var card:Array=name.split("_"); if(card.length!=3) return; target=String(card[2]);
         } else return;
         if(target!="0" && target!="1") return;
         // Only queue this gesture. Native work belongs to the next UI tick,
         // after revalidating Sim, layer, household, pair and CAS session.
         var sim:Object=ApexClone(CommunicationManager.CallGameService("CASGetSimInfo",null,true));
         if(sim==null || String(sim.simId)!=apexBoundSim) return;
         if(apexFormsGestureSequence>=2147483647 || apexNonce.length!=64) return;
         apexFormsGestureSequence++;
         apexFormsIntent={sim_id:apexBoundSim,source_layer:int(sim.occultLayer),mask:int(sim.allOccultTypes),
            kind:int(sim.occultType),layer:int(target),session:apexOwnerSession,
            request_id:apexNonce.substr(0,24)+("00000000"+apexFormsGestureSequence.toString(16)).substr(-8)};
         sim=null;
      }

      private function ApexFormsStatus() : Object
      {
         return {protocol:1,scope:"native-cas-hybrid-form-strip",visible:apexFormsRoot!=null,
            sim_id:apexBoundSim,owned_mask:apexFormsOwnedMask,session:apexOwnerSession,
            cross_kind_navigation:apexFormsNativeState=="bound",selected_owner_id:apexFormsSelectedId,owner_count:apexFormsOwners.length,
            native_owner_state:apexFormsNativeState,desired_owner_id:apexFormsDesiredId,form_conversion_called:false,gesture_pending:apexFormsIntent!=null,
            native_fast_state:apexFormsFastState,native_generation:apexFormsNativeGeneration,switch_milliseconds:apexFormsSwitchMilliseconds,
            pair_controls:ApexPairStatus(), member_ui_ready:ApexPresentationReady(),member_ui_milliseconds:apexPresentationMilliseconds,member_ui_frames:apexPresentationFrames,member_ui_timing:{first_frame_delay_ms:apexPresentationFirstFrameDelay,prime_ms:apexPresentationPrimeMs,catalog_ms:apexPresentationCatalogMs,menu_ms:apexPresentationMenuMs,state_ms:apexPresentationStateMs,pair_ms:apexPresentationPairMs,icons_ms:apexPresentationIconsMs,graphics_ms:apexPresentationGraphicsMs},local_catalog:apexFormsLocalCatalog,local_catalog_offset:apexFormsLocalOffset,
            selection_result:ApexClone(apexFormsResult),message:apexFormsMessage,
            molecule_pending:ApexClone(apexMoleculeIntent),command_pending:apexPendingFields!=null,
            command_phase:apexPendingPhase,receiving:apexReceiving,
            input_timing:{scope:"accepted-CAS-input-queue-handler",clock_resolution_ms:1,target_ms:1,
               samples:apexInputSamples,over_budget:apexInputOverBudget,max_ms:apexInputMaxMs,total_ms:apexInputTotalMs},
            transport:{error:apexSocketError,reset_pending:apexSocketResetPending,
               stage:apexAwaiting.split("|")[0],native_connected:apexNativeConnected,
               catalog_expected:apexFormsOwnerTotal,catalog_received:apexFormsOwners.length},
            life_states:ApexClone(apexFormsGroups),variant_family:apexFormsVariantFamily,
            layout:{scale:apexFormsScale,locked:apexFormsLocked,collapsed:apexFormsCollapsed,dragging:apexFormsDragging,
               x:apexFormsPosition==null ? null : apexFormsPosition.x,y:apexFormsPosition==null ? null : apexFormsPosition.y}};
      }

      private function ApexFormsToolbar(action:String,text:String,x:Number,width:Number=24) : void
      {
         var button:flash.display.Sprite=new flash.display.Sprite(); button.name="apexTool_"+action;
         button.x=x; button.y=-1; button.mouseChildren=false; button.buttonMode=true;
         button.graphics.beginFill(0xffffff,0.95); button.graphics.lineStyle(1,0xb1cee3,1);
         button.graphics.drawRoundRect(0,0,width,24,12,12); button.graphics.endFill();
         var label:flash.text.TextField=ApexFormsText(button,text,2,3,width-4,11,0x2765a2);
         var format:flash.text.TextFormat=label.defaultTextFormat; format.align="center"; label.setTextFormat(format);
         apexFormsRoot.addChild(button);
      }

      private function ApexFormsToolbarClick(action:String) : void
      {
         if(action=="humanfur" || action=="wolffur") {
            if(apexFormsSelectedId!=="werewolf/werewolf_human_cc" || apexPendingFields!=null || apexReceiving ||
               apexFormsDesiredId!="" || apexFormsNativeIntent!=null || apexPairIntent!=null) return;
            var furPair:Object=ApexPairRead();
            if(furPair==null || furPair.selected_owner_id!==apexFormsSelectedId ||
               furPair.human_owner_id===apexFormsSelectedId) return;
            apexPairIntent={sim_id:apexBoundSim,session:apexOwnerSession,generation:furPair.generation,
               operation:"copy",enabled:false,category_flags:action=="humanfur"?268435472:16777232,
               source_owner_id:action=="humanfur"?furPair.human_owner_id:"native/32",target_owner_id:apexFormsSelectedId};
            ApexFormsScheduleFrame();return;
         }
         if(action=="humanbase") {
            if(apexFormsSelectedId!=="werewolf/werewolf_human_cc" || apexPendingFields!=null || apexReceiving ||
               apexFormsDesiredId!="" || apexFormsNativeIntent!=null || apexPairIntent!=null) return;
            var pair:Object=ApexPairRead();
            if(pair==null || pair.selected_owner_id!==apexFormsSelectedId ||
               pair.human_owner_id===apexFormsSelectedId) return;
            apexPairIntent={sim_id:apexBoundSim,session:apexOwnerSession,generation:pair.generation,
               operation:"copy",enabled:false,category_flags:4294967295,
               source_owner_id:pair.human_owner_id,target_owner_id:apexFormsSelectedId};
            ApexFormsScheduleFrame();return;
         }
         if(action=="smaller") apexFormsScale=Math.max(0.7,Math.round((apexFormsScale-0.1)*10)/10);
         else if(action=="larger") apexFormsScale=Math.min(1.5,Math.round((apexFormsScale+0.1)*10)/10);
         else if(action=="previous") apexFormsPage=Math.max(0,apexFormsPage-1);
         else if(action=="next") apexFormsPage=Math.min(Math.ceil(apexFormsOwners.length/21)-1,apexFormsPage+1);
         else if(action=="lock") apexFormsLocked=!apexFormsLocked;
         else if(action=="collapse") apexFormsCollapsed=!apexFormsCollapsed;
         else if(action=="forms") { apexFormsVariantFamily="";apexFormsPage=0; }
         else if(action=="reset") { apexFormsPosition=null; apexFormsScale=1; apexFormsCollapsed=false; apexFormsLocked=false; }
         else return;
         apexFormsSignature="";
         ApexFormsScheduleFrame();
      }

      private function ApexFormsPlace() : void
      {
         if(apexFormsRoot==null || stage==null) return;
         apexFormsRoot.scaleX=apexFormsRoot.scaleY=apexFormsScale;
         var spanX:Number=Math.max(0,stage.stageWidth-apexFormsPanelWidth*apexFormsScale-28);
         var spanY:Number=Math.max(0,stage.stageHeight-(apexFormsCollapsed ? 34 : apexFormsPanelHeight)*apexFormsScale-28);
         var x:Number=apexFormsPosition==null ? 18 : 14+apexFormsPosition.x*spanX;
         var y:Number=apexFormsPosition==null ? stage.stageHeight-326 : 14+apexFormsPosition.y*spanY;
         // Default placement clears the actual portrait toolbar, including
         // EA's animation/scale. Explicit player placement remains movable.
         if(apexFormsPosition==null && apexPairRoot!=null && apexPairRoot.visible) {
            var pairPoint:flash.geom.Point=localToGlobal(new flash.geom.Point(apexPairRoot.x,apexPairRoot.y));
            y=Math.min(y,pairPoint.y-(apexFormsCollapsed?34:apexFormsPanelHeight)*apexFormsScale-14);
         }
         x=Math.max(14,Math.min(x,stage.stageWidth-apexFormsPanelWidth*apexFormsScale-14));
         y=Math.max(14,Math.min(y,stage.stageHeight-(apexFormsCollapsed ? 34 : apexFormsPanelHeight)*apexFormsScale-14));
         var point:flash.geom.Point=globalToLocal(new flash.geom.Point(x,y));
         apexFormsRoot.x=point.x; apexFormsRoot.y=point.y;
      }

      private function ApexFormsDragStart(event:flash.events.MouseEvent) : void
      {
         if(apexFormsLocked || apexFormsRoot==null || event==null || event.target==null ||
            String(event.target.name)!="apexDragHandle") return;
         apexFormsDragging=true; apexFormsRoot.startDrag(false);
         stage.addEventListener(flash.events.MouseEvent.MOUSE_UP,ApexFormsDragEnd,false,0,true);
         stage.addEventListener(flash.events.Event.DEACTIVATE,ApexFormsDragCancel,false,0,true);
         stage.addEventListener(flash.events.Event.MOUSE_LEAVE,ApexFormsDragCancel,false,0,true);
         event.stopPropagation();
      }

      private function ApexFormsDragEnd(event:flash.events.MouseEvent) : void
      {
         if(stage!=null) stage.removeEventListener(flash.events.MouseEvent.MOUSE_UP,ApexFormsDragEnd);
         if(stage!=null) stage.removeEventListener(flash.events.Event.DEACTIVATE,ApexFormsDragCancel);
         if(stage!=null) stage.removeEventListener(flash.events.Event.MOUSE_LEAVE,ApexFormsDragCancel);
         if(apexFormsRoot==null || stage==null) { apexFormsDragging=false; return; }
         apexFormsRoot.stopDrag();
         var point:flash.geom.Point=localToGlobal(new flash.geom.Point(apexFormsRoot.x,apexFormsRoot.y));
         var spanX:Number=Math.max(1,stage.stageWidth-apexFormsPanelWidth*apexFormsScale-28);
         var spanY:Number=Math.max(1,stage.stageHeight-(apexFormsCollapsed ? 34 : apexFormsPanelHeight)*apexFormsScale-28);
         apexFormsPosition=new flash.geom.Point(Math.max(0,Math.min(1,(point.x-14)/spanX)),Math.max(0,Math.min(1,(point.y-14)/spanY)));
         apexFormsDragging=false; apexFormsSignature=""; ApexFormsPlace();
      }

      private function ApexFormsResetPosition(event:flash.events.MouseEvent) : void
      {
         if(event!=null && event.target!=null && String(event.target.name)=="apexDragHandle" && !apexFormsLocked) {
            apexFormsPosition=null; apexFormsSignature=""; ApexFormsPlace();
         }
      }

      private function ApexFormsDragCancel(event:flash.events.Event) : void
      {
         if(apexFormsDragging) ApexFormsDragEnd(null);
      }

      private function ApexFormsApply(x:Number,y:Number,scale:Number,locked:Boolean,collapsed:Boolean) : void
      {
         apexFormsPosition=new flash.geom.Point(x,y); apexFormsScale=scale;
         apexFormsLocked=locked; apexFormsCollapsed=collapsed; apexFormsSignature="";
         ApexFormsTick(ApexFormsObservedSim());
      }

      private function ApexFormsOwnedTick(sim:Object) : void
      {
         // Time only bounded incoming-member publication. An idle or already
         // ready CAS frame performs no extra clock calls or profiling work.
         var measuring:Boolean=apexPresentationStarted>=0 && apexPresentationMilliseconds<0;
         var phaseStarted:int=measuring?getTimer():0;
         if(apexNativeChannel!="" && (apexNativeConnected || apexFormsLocalCatalog)) ApexFormsReadNativeState();
         ApexPairTick();
         ApexFormsBindUiKind();
         ApexMoleculeDrain();
         if(measuring) {apexPresentationStateMs+=getTimer()-phaseStarted;phaseStarted=getTimer();}
         var busy:Boolean=ApexFormsCommandBlocksInput() || apexFormsDragging || apexFormsDesiredId!="";
         var pairSignature:String=apexBoundSim+"|"+apexFormsSelectedId+"|"+apexFormsNativeGeneration;
         var refreshPair:Boolean=apexFormsNativeState=="bound" && apexFormsDesiredId=="" && pairSignature!==apexPairSignature;
         var pairLabels:Object=ApexPairRead();
         var portraits:Object=CommunicationManager.CallUIService("ApexConfigureFormPortraits",{sim_id:apexBoundSim,refresh_pair:refreshPair,
            base_label:pairLabels==null?"":ApexPairLabel(pairLabels.base_owner_id),
            alternate_label:pairLabels==null?"":ApexPairLabel(pairLabels.alternate_owner_id)});
         if(measuring) {apexPresentationPairMs+=getTimer()-phaseStarted;phaseStarted=getTimer();}
         if(portraits==null || portraits.protocol!==1 || portraits.enabled!==true || portraits.sim_id!==apexBoundSim)
            return;
         if(refreshPair) apexPairSignature=pairSignature;
         if(!apexFormsBootstrap && !busy) {
            // Member navigation may already have bound the exact native owner.
            // Rebinding it again can strand an identical-state UI lease and
            // needlessly rebuild the model/undo context.
            apexFormsBootstrap=apexFormsNativeState=="bound";
            if(!apexFormsBootstrap) for each(var original:Object in apexFormsOwners) if(original.id==apexFormsSelectedId) {
               apexFormsNativeIntent=ApexClone(original);apexFormsNativeIntent.bootstrap=true;
               apexFormsBootstrap=true;break;
            }
         }
         if(apexFormsNativeIntent!=null && !busy && String(sim.simId)==apexBoundSim) {
            var intent:Object=apexFormsNativeIntent;apexFormsNativeIntent=null;
            var nativeToken:int=int(intent.token);
            if(nativeToken<0x20000000 || nativeToken>0x2fffffff) throw new Error("Native form button lost its exact token");
            apexFormsDesiredId=String(intent.id);
            CommunicationManager.CallGameService("SetSimOccult",nativeToken);
            ApexFormsReadNativeState();
            ApexFormsBindUiKind();
            busy=apexFormsDesiredId!="";
            if(!busy) {
               ApexFormsRefreshBoundPair();
            }
         }
         if(apexFormsCatalog==null || apexFormsCatalog.sim_id!=apexBoundSim) {
            apexFormsCatalog={sim_id:apexBoundSim,icons:{}};
            // Prepared descriptors already contain exact game asset IDs. Only
            // ask EA for an icon when an actually displayed family lacks one.
            var preparedIconKinds:Object={human:1,alien:2,vampire:4,mermaid:8,witch:16,werewolf:32,fairy:64};
            var neededIcons:Object={};
            for each(var iconOwner:Object in apexFormsOwners) if(preparedIconKinds.hasOwnProperty(String(iconOwner.family))) {
               var iconKind:String=String(preparedIconKinds[String(iconOwner.family)]);neededIcons[iconKind]=true;
               var preparedIcon:String=String(iconOwner.family_icon);
               if(preparedIcon=="") preparedIcon=String(iconOwner.icon);
               if(preparedIcon!="" && !apexFormsCatalog.icons.hasOwnProperty(iconKind)) apexFormsCatalog.icons[iconKind]=preparedIcon;
            }
            for each(var kind:int in [1,2,4,8,16,32,64]) if(neededIcons.hasOwnProperty(String(kind)) && !apexFormsCatalog.icons.hasOwnProperty(String(kind))) {
               var iconData:Object=ApexClone(CommunicationManager.CallGameService("GetOccultIcon",kind));
               if(iconData && iconData.icon && iconData.icon.instance is String) apexFormsCatalog.icons[String(kind)]=String(iconData.icon.instance);
            }
         }
         if(measuring) {apexPresentationIconsMs+=getTimer()-phaseStarted;phaseStarted=getTimer();}
         ApexFormsGroupCatalog();
         var entries:Array=[];
         if(apexFormsVariantFamily!="") {
            for each(var variantGroup:Object in apexFormsGroups) if(variantGroup.family==apexFormsVariantFamily)
               entries=variantGroup.indices.concat();
            // Real is the existing shared Human, never another IF Human owner.
            if(apexFormsVariantFamily=="imaginary_friend") for(var h:int=0;h<apexFormsOwners.length;++h)
               if(apexFormsOwners[h].form_id=="human/shared") entries.push(h);
            if(entries.length==0) apexFormsVariantFamily="";
         }
         var count:int=apexFormsVariantFamily==""?apexFormsGroups.length:entries.length;
         var columns:int=Math.min(8,count);
         apexFormsPage=Math.max(0,Math.min(apexFormsPage,Math.ceil(count/21)-1));
         var start:int=apexFormsPage*21;var end:int=Math.min(count,start+21);
         var rows:int=Math.ceil((end-start)/columns);
         var cellWidth:int=apexFormsVariantFamily==""?44:82;
         var cellHeight:int=apexFormsVariantFamily==""?44:70;
         apexFormsPanelWidth=Math.max(350,columns*cellWidth+8);apexFormsPanelHeight=rows*cellHeight+62;
         var humanBase:Boolean=apexFormsSelectedId==="werewolf/werewolf_human_cc" && apexFormsNativeState=="bound";
         if(humanBase) apexFormsPanelHeight+=30;
         var signature:String=apexBoundSim+":"+apexFormsSelectedId+":"+apexFormsNativeState+":"+apexFormsDesiredId+":"+
            count+":"+apexFormsPage+":"+busy+":"+apexFormsScale+":"+apexFormsLocked+":"+apexFormsCollapsed+":"+apexFormsVariantFamily+":"+apexPairMessage;
         if(signature==apexFormsSignature) {if(measuring) apexPresentationGraphicsMs+=getTimer()-phaseStarted;return;}apexFormsSignature=signature;
         if(apexFormsRoot==null) {
            apexFormsRoot=new flash.display.Sprite();apexFormsRoot.name="ApexHybridForms";
            apexFormsRoot.addEventListener(flash.events.MouseEvent.CLICK,ApexFormsClick,false,0,true);
            apexFormsRoot.addEventListener(flash.events.MouseEvent.MOUSE_DOWN,ApexFormsDragStart,false,0,true);
            apexFormsRoot.addEventListener(flash.events.MouseEvent.DOUBLE_CLICK,ApexFormsResetPosition,false,0,true);addChild(apexFormsRoot);
         }
         ApexFormsClearTooltips();
         while(apexFormsRoot.numChildren>0) apexFormsRoot.removeChildAt(0);
         apexFormsRoot.graphics.clear();apexFormsRoot.graphics.beginFill(0xf4fbff,0.97);
         apexFormsRoot.graphics.lineStyle(2,0xffffff,0.95);
         apexFormsRoot.graphics.drawRoundRect(-8,-6,apexFormsPanelWidth+4,apexFormsCollapsed?34:apexFormsPanelHeight,16,16);apexFormsRoot.graphics.endFill();
         var handle:flash.display.Sprite=new flash.display.Sprite();handle.name="apexDragHandle";
         handle.graphics.beginFill(0xdceefa,1);handle.graphics.drawRoundRect(-7,-5,apexFormsPanelWidth+2,30,14,14);handle.graphics.endFill();apexFormsRoot.addChild(handle);
         var selectedLabel:String="Forms";
         for each(var selectedOwner:Object in apexFormsOwners) if(selectedOwner.id==apexFormsSelectedId) selectedLabel=String(selectedOwner.label);
         if(apexFormsVariantFamily!="") for each(var titleGroup:Object in apexFormsGroups)
            if(titleGroup.family==apexFormsVariantFamily) selectedLabel=String(titleGroup.label);
         ApexFormsText(handle,selectedLabel,apexFormsVariantFamily!=""?76:12,2,
            apexFormsPanelWidth-(apexFormsVariantFamily!=""?274:210),12,0x2765a2);
         if(apexFormsVariantFamily!="") ApexFormsToolbar("forms","< Forms",2,66);
         if(count>21) { ApexFormsToolbar("previous","<",172);ApexFormsToolbar("next",">",199); }
         ApexFormsToolbar("smaller","-",apexFormsPanelWidth-190);ApexFormsToolbar("larger","+",apexFormsPanelWidth-163);
         ApexFormsToolbar("lock",apexFormsLocked?"Unlock":"Lock",apexFormsPanelWidth-134,49);
         ApexFormsToolbar("reset","Reset",apexFormsPanelWidth-82,47);ApexFormsToolbar("collapse",apexFormsCollapsed?"+":"-",apexFormsPanelWidth-32);
         ApexFormsPlace();if(apexFormsCollapsed) {if(measuring) apexPresentationGraphicsMs+=getTimer()-phaseStarted;return;}
         var nativeNames:Object={"1":"Human","2":"Alien","4":"Vampire","8":"Mermaid","16":"Spellcaster","32":"Werewolf","64":"Fairy"};
         for(var i:int=start;i<end;++i) {
            var owner:Object;
            var button:flash.display.Sprite;
            if(apexFormsVariantFamily=="") {
               var familyGroup:Object=apexFormsGroups[i];
               owner=ApexClone(apexFormsOwners[int(familyGroup.indices[0])]);
               owner.id=familyGroup.selected?apexFormsSelectedId:"";
               owner.icon=familyGroup.icon;owner.label=familyGroup.label;owner.description=familyGroup.description;
               button=ApexFormsCompactButton(owner,i,((i-start)%columns)*44,32+Math.floor((i-start)/columns)*44,!busy);
               button.name="apexGroup_"+i;
               if(familyGroup.indices.length>1 || familyGroup.family=="imaginary_friend")
                  ApexFormsText(button,"\u25be",28,24,10,9,0x2765a2);
            } else {
               var exactIndex:int=int(entries[i]);owner=ApexClone(apexFormsOwners[exactIndex]);
               owner.label=owner.form_id=="human/shared"?"Human / Real":owner.variant_label;
               owner.description=owner.label+". "+owner.description;
               button=ApexFormsCompactButton(owner,exactIndex,((i-start)%columns)*cellWidth,32+Math.floor((i-start)/columns)*cellHeight,!busy,true);
            }
         }
         if(humanBase) {
            ApexFormsToolbar("humanfur","Human skin / no fur",4,168);
            ApexFormsToolbar("wolffur","Use Werewolf fur",178,168);
            var humanFur:flash.display.Sprite=apexFormsRoot.getChildByName("apexTool_humanfur") as flash.display.Sprite;
            var wolfFur:flash.display.Sprite=apexFormsRoot.getChildByName("apexTool_wolffur") as flash.display.Sprite;
            humanFur.y=wolfFur.y=apexFormsPanelHeight-53;
            ApexFormsTooltip(humanFur,"Remove body fur and fur paint from this Human/CC look and use the shared Human skin tone. Keep canine head, ears, shape, clothes, tattoos and other forms.");
            ApexFormsTooltip(wolfFur,"Copy skin tone, fur and fur paint from this Sim's EA Werewolf form into only this Human/CC look. Keep its head, ears, shape, clothes and tattoos. This uses the Werewolf form's current fur colours.");
         }
         var footer:String=apexFormsNativeState=="unresolved" ? "Form view unresolved; further switching is blocked." : apexFormsDesiredId!="" ? "Opening "+apexFormsDesiredId : apexFormsNativeState=="bound" ? "Each form keeps its own edits. Copy or link only when you choose." :
            apexFormsNativeState=="unresolved" ? "Form view unresolved; further switching is blocked." : "Initializing independent form owners...";
         if(apexFormsNativeState=="bound" && apexFormsDesiredId=="") footer="Each form keeps its own appearance";
         if(apexPairMessage!="") footer=apexPairMessage;
         ApexFormsText(apexFormsRoot,footer,2,apexFormsPanelHeight-23,apexFormsPanelWidth-8,10,0x55778f);
         if(measuring) apexPresentationGraphicsMs+=getTimer()-phaseStarted;
      }

      private function ApexFormsCompactButton(owner:Object,index:int,x:Number,y:Number,enabled:Boolean,wide:Boolean=false) : flash.display.Sprite
      {
         var selected:Boolean=owner.id==apexFormsSelectedId && apexFormsNativeState=="bound";
         var button:flash.display.Sprite=new flash.display.Sprite();
         button.name="apexOwned_"+index;button.x=x;button.y=y;
         button.graphics.beginFill(selected?0xe8f8c9:0xffffff,1);
         button.graphics.lineStyle(selected?2:1,selected?0x7cb737:0xb4cee1,1);
         button.graphics.drawRoundRect(0,0,wide?76:40,wide?64:38,10,10);button.graphics.endFill();
         // Selected and temporarily busy controls still explain themselves on hover.
         button.mouseChildren=false;button.mouseEnabled=true;button.buttonMode=enabled;
         apexFormsRoot.addChild(button);
         var icon:String=owner.icon is String?String(owner.icon):"";
         var nativeFamilies:Object={human:1,alien:2,vampire:4,mermaid:8,witch:16,werewolf:32,fairy:64};
         if(icon=="" && nativeFamilies.hasOwnProperty(String(owner.family)) &&
            apexFormsCatalog.icons.hasOwnProperty(String(nativeFamilies[String(owner.family)])))
            icon=String(apexFormsCatalog.icons[String(nativeFamilies[String(owner.family)])]);
         if(icon!="") {
            var image:Object=new IconComponentResource();image.x=wide?24:6;image.y=5;image.mouseEnabled=false;
            button.addChild(image);image.ResetImageSize(28,28);image.LoadImage(icon);
         } else {
            // Unknown/mod-added identities retain their name, never borrowed art.
            var initials:String=String(owner.label).substr(0,3).toUpperCase();
            if(String(owner.form_id).indexOf("imaginary_friend/")==0) initials="IF";
            ApexFormsText(button,initials,3,11,37,11,0x2765a2);
         }
         if(wide) {
            var caption:flash.text.TextField=ApexFormsText(button,String(owner.label),3,36,70,10,0x2765a2);
            caption.wordWrap=true;caption.height=27;
            var captionFormat:flash.text.TextFormat=caption.defaultTextFormat;captionFormat.align="center";caption.setTextFormat(captionFormat);
         }
         ApexFormsTooltip(button,String(owner.description));
         return button;
      }

      private function ApexFormsGroupCatalog() : void
      {
         var key:String=apexBoundSim+":"+apexFormsOwners.length+":"+apexFormsSelectedId;
         if(key==apexFormsGroupKey && apexFormsGroups.length>0) return;
         apexFormsGroups=[];var byFamily:Object={};
         var nativeFamilies:Object={human:1,alien:2,vampire:4,mermaid:8,witch:16,werewolf:32,fairy:64};
         var labels:Object={human:"Human",alien:"Alien",vampire:"Vampire",mermaid:"Mermaid",witch:"Spellcaster",
            werewolf:"Werewolf",fairy:"Fairy",ghost:"Ghost",plantsim:"PlantSim",servo:"Servo / Robot",reaper:"Grim Reaper",
            skeleton:"Skeleton / Bonehilda",scarecrow:"Scarecrow / Patchy",imaginary_friend:"Imaginary Friend"};
         for(var i:int=0;i<apexFormsOwners.length;++i) {
            var owner:Object=apexFormsOwners[i];var family:String=String(owner.family);
            if(!byFamily.hasOwnProperty(family)) {
               var icon:String=String(owner.family_icon);
               if(icon=="" && nativeFamilies.hasOwnProperty(family) && apexFormsCatalog.icons.hasOwnProperty(String(nativeFamilies[family])))
                  icon=String(apexFormsCatalog.icons[String(nativeFamilies[family])]);
               var group:Object={family:family,label:labels.hasOwnProperty(family)?labels[family]:owner.label,
                  description:owner.description,icon:icon,indices:[],variants:[],selected:false};
               byFamily[family]=group;apexFormsGroups.push(group);
            }
            group=byFamily[family];group.indices.push(i);group.selected=group.selected || owner.id==apexFormsSelectedId;
            group.variants.push({owner_id:owner.id,label:owner.variant_label,icon:owner.icon,description:owner.description});
         }
         apexFormsGroupKey=key;
      }

      private function ApexFormsTooltip(button:flash.display.Sprite,text:String) : void
      {
         var tooltip:TooltipObject=new TooltipObject(button);
         tooltip.Initialize({text:text,maxwidth:300},250);
         apexFormsTooltips.push(tooltip);
      }

      private function ApexFormsBindUiKind() : void
      {
         // EA's UI SimInfo can still describe the physical Vampire backing
         // slot after the native model binds an independent Fairy/Mermaid.
         // Correct this AS display record from the exact bound owner. Do not
         // change memberships, native CasData, traits or either appearance.
         if(apexFormsNativeState!="bound" || apexFormsDesiredId!="" || this.mCurrSimInfo==null ||
            String(this.mCurrSimInfo.simId)!==apexBoundSim) return;
         for each(var owner:Object in apexFormsOwners) if(owner.id===apexFormsSelectedId) {
            var kind:int=int(owner.kind);
            if([1,2,4,8,16,32,64].indexOf(kind)<0 ||
               (int(this.mCurrSimInfo.allOccultTypes)&kind)==0 || int(this.mCurrSimInfo.occultType)==kind) return;
            this.mCurrSimInfo.occultType=kind;
            CommunicationManager.SendUIMessage("CASContextMenuSetSimInfo",this.mCurrSimInfo);
            HandleContextMenuUpdate(this.mContextMenuState);
            return;
         }
      }

      private function ApexFormsRefreshBoundPair() : Boolean
      {
         // Both actual strip clicks and typed CLI selection finish the same
         // EA portrait/category panel before acknowledging presentation.
         // No second model bind, polling delay or appearance copy is needed.
         if(apexFormsNativeState!=="bound" || apexFormsDesiredId!="") return false;
         var signature:String=apexBoundSim+"|"+apexFormsSelectedId+"|"+apexFormsNativeGeneration;
         var pair:Object=ApexPairRead();
         if(pair==null) return false;
         var portraits:Object=CommunicationManager.CallUIService("ApexConfigureFormPortraits",{
            sim_id:apexBoundSim,refresh_pair:true,
            base_label:ApexPairLabel(pair.base_owner_id),alternate_label:ApexPairLabel(pair.alternate_owner_id)});
         if(portraits==null || portraits.protocol!==1 || portraits.enabled!==true ||
            portraits.sim_id!==apexBoundSim || !ApexFormsReadNativeState() ||
            apexFormsNativeState!=="bound" || apexFormsDesiredId!="" ||
            signature!==apexBoundSim+"|"+apexFormsSelectedId+"|"+apexFormsNativeGeneration) return false;
         apexPairContext=pair;apexPairSignature=signature;
         ApexFormsBindUiKind();return true;
      }

      private function ApexFormsClearTooltips() : void
      {
         for each(var tooltip:TooltipObject in apexFormsTooltips) tooltip.Shutdown();
         apexFormsTooltips=[];
      }

      private function ApexFormsQueueOwner(owner:Object) : void
      {
         // Consume once on the next rendered UI frame, outside the click
         // callback. The 500ms network poll is not a form-navigation scheduler.
         if(owner==null) return;
         // One bounded latest-choice slot, tied to the exact Sim and editor.
         // Never discard a click simply because the previous frame is busy.
         apexFormsGestureStarted=getTimer();
         apexMoleculeIntent={sim_id:apexBoundSim,session:apexOwnerSession,
            owner_id:String(owner.id),token:int(owner.token),queued_at:apexFormsGestureStarted};
         ApexFormsScheduleFrame();
         ApexInputTiming(apexFormsGestureStarted);
      }

      private function ApexInputTiming(started:int) : void
      {
         var elapsed:int=getTimer()-started;
         if(elapsed<0 || apexInputSamples>=2147483647) return;
         apexInputSamples++;apexInputTotalMs+=elapsed;
         if(elapsed>apexInputMaxMs) apexInputMaxMs=elapsed;
         if(elapsed>1) apexInputOverBudget++;
      }

      private function ApexFormsScheduleFrame() : void
      {
         if(!apexFormsFrameQueued) {
            apexFormsFrameQueued=true;
            addEventListener(flash.events.Event.ENTER_FRAME,ApexFormsNextFrame,false,0,true);
         }
      }

      private function ApexFormsCommandBlocksInput() : Boolean
      {
         // Native input and the CLI run on separate UI events, never together
         // inside a native call. A status-only claim may observe the user's
         // newer selection on its readback; it owns no appearance write.
         // Unknown/received commands and every mutation retain the full gate.
         if(apexReceiving || this.mCurrSimInfo==null || this.mCurrSimInfo.simId!==apexBoundSim) return true;
         if(apexPendingFields==null) return apexPendingPhase!=0;
         return !(apexPendingPhase==1 && apexPendingFields.length==7 &&
            apexPendingFields[1]===apexBoundSim && apexPendingFields[2]==="status" &&
            apexClaimNonce===apexNonce && apexPendingReply!=null &&
            apexPendingReply.mutation_started!==true);
      }

      private function ApexFormsNextFrame(event:flash.events.Event) : void
      {
         removeEventListener(flash.events.Event.ENTER_FRAME,ApexFormsNextFrame);
         apexFormsFrameQueued=false;
         if(apexDisconnected || !(apexNativeConnected || apexFormsLocalCatalog) || apexBoundSim=="" || apexPendingPhase>=7) return;
         if(apexTicking || ApexFormsCommandBlocksInput()) {
            if(apexMoleculeIntent!=null || apexFormsNativeIntent!=null || apexFormsDesiredId!="" || apexPairIntent!=null) ApexFormsScheduleFrame();
            return;
         }
         // An outstanding network POLL must not postpone a local form click.
         // Both operations below use only this UI thread's exact bound model.
         apexTicking=true;
         try {ApexFormsOwnedTick(ApexFormsObservedSim());}
         catch(error:Error) {apexFormsMessage=error.message;apexFormsSignature="";}
         finally {
            apexTicking=false;
            // Continue an outstanding transition on UI frames, not the
            // unrelated 500 ms network polling timer. Idle UI does no work.
            if(apexMoleculeIntent!=null || apexFormsNativeIntent!=null || apexFormsDesiredId!="" || apexPairIntent!=null)
               ApexFormsScheduleFrame();
         }
      }

      private function ApexFormsReadNativeState() : Boolean
      {
         if(apexNativeChannel=="" || !(apexNativeConnected || apexFormsLocalCatalog)) return false;
         var message:String=ApexNativeExchange("STATE|"+apexNativeChannel);
         if(message=="WAIT") return false;
         var fields:Array=message.split("|");
         if(fields.length!=7 || fields[0]!="VIEWSTATE" || fields[1]!==apexBoundSim ||
            !/^[a-z0-9_][a-z0-9_-]{0,63}\/[a-z0-9_][a-z0-9_-]{0,63}$/.test(fields[2]) ||
            ["1","2","4","8","16","32","64"].indexOf(String(fields[3]))<0 ||
            !/^[01]$/.test(fields[4]) || fields[5]!="bound" || !/^[1-9][0-9]{0,19}$/.test(fields[6])) return false;
         var known:Boolean=false;
         for each(var owner:Object in apexFormsOwners) if(owner.id===fields[2] && int(owner.kind)==int(fields[3])) known=true;
         if(!known) return false;
         apexFormsFastState=true;apexFormsNativeGeneration=String(fields[6]);
         apexFormsSelectedId=String(fields[2]);apexFormsNativeState="bound";
         if(apexFormsDesiredId===apexFormsSelectedId) {
            apexFormsDesiredId="";
            apexFormsMessage="";
            if(apexFormsGestureStarted>=0) apexFormsSwitchMilliseconds=getTimer()-apexFormsGestureStarted;
            apexFormsGestureStarted=-1;
         }
         return true;
      }
