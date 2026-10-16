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

      private function ApexFormsDispose() : void
      {
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
         var label:flash.text.TextField=ApexFormsText(button,title,1,39,70,11,selected ? 0x256207 : 0x315778);
         var format:flash.text.TextFormat=label.defaultTextFormat; format.align="center"; label.setTextFormat(format);
      }

      private function ApexFormsTick(sim:Object) : void
      {
         if(stage==null || sim==null || String(sim.simId)!=apexBoundSim || apexFormsOwnedMask==0 || apexFormsDragging) return;
         if(!isFinite(apexFormsScale) || apexFormsScale<0.7 || apexFormsScale>1.5) apexFormsScale=1;
         // Live entry is needed for a captured original. Other editors retain
         // their ordinary EA interface until a complete owner is available.
         var busy:Boolean=apexPendingFields!=null || apexReceiving || apexPendingPhase>=5;
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
         var selector:Object=CommunicationManager.CallUIService("ApexReadOwnerPairFeed",null);
         if(selector==null || selector.protocol!==1 || selector.scope!="native-selector-owner-pair-view" ||
            selector.service_registered!==true || selector.retained==null) return null;
         var feed:Object=selector.retained;
         if(feed.available!==true || !(feed.pairs is Array) || !(feed.selected_index is int) ||
            feed.selected_index<0 || feed.selected_index>=feed.pairs.length ||
            !(feed.selected_layer is int) || (feed.selected_layer!=0 && feed.selected_layer!=1)) return null;
         var pair:Object=feed.pairs[int(feed.selected_index)];
         var row:Object=pair==null ? null : feed.selected_layer==0 ? pair.base : pair.alternate;
         if(row==null || !(row.sim_id is String) || !/^[1-9][0-9]{0,19}$/.test(row.sim_id) ||
            row.sim_id!=feed.selected_sim_id || !(row.occult_type is int) || !(row.occult_layer is int) ||
            !(row.all_occult_types is int) || row.occult_layer!=feed.selected_layer) return null;
         return {simId:String(row.sim_id),householdId:apexFormsHousehold,occultType:int(row.occult_type),
            occultLayer:int(row.occult_layer),allOccultTypes:int(row.all_occult_types)};
      }

      private function ApexFormsClick(event:flash.events.MouseEvent) : void
      {
         if(event!=null && event.target!=null && String(event.target.name).indexOf("apexTool_")==0) {
            ApexFormsToolbarClick(String(event.target.name).substr(9)); return;
         }
         if(event==null || event.target==null || apexFormsIntent!=null || apexPendingFields!=null || apexReceiving ||
            apexFormsResult!=null && apexFormsResult.verified!==true) return;
         var name:String=String(event.target.name);
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
            cross_kind_navigation:false,form_conversion_called:false,gesture_pending:apexFormsIntent!=null,
            selection_result:ApexClone(apexFormsResult),message:apexFormsMessage,
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
         if(action=="smaller") apexFormsScale=Math.max(0.7,Math.round((apexFormsScale-0.1)*10)/10);
         else if(action=="larger") apexFormsScale=Math.min(1.5,Math.round((apexFormsScale+0.1)*10)/10);
         else if(action=="lock") apexFormsLocked=!apexFormsLocked;
         else if(action=="collapse") apexFormsCollapsed=!apexFormsCollapsed;
         else if(action=="reset") { apexFormsPosition=null; apexFormsScale=1; apexFormsCollapsed=false; apexFormsLocked=false; }
         else return;
         apexFormsSignature="";
      }

      private function ApexFormsPlace() : void
      {
         if(apexFormsRoot==null || stage==null) return;
         apexFormsRoot.scaleX=apexFormsRoot.scaleY=apexFormsScale;
         var spanX:Number=Math.max(0,stage.stageWidth-apexFormsPanelWidth*apexFormsScale-28);
         var spanY:Number=Math.max(0,stage.stageHeight-(apexFormsCollapsed ? 34 : 146)*apexFormsScale-28);
         var x:Number=apexFormsPosition==null ? 18 : 14+apexFormsPosition.x*spanX;
         var y:Number=apexFormsPosition==null ? stage.stageHeight-326 : 14+apexFormsPosition.y*spanY;
         x=Math.max(14,Math.min(x,stage.stageWidth-apexFormsPanelWidth*apexFormsScale-14));
         y=Math.max(14,Math.min(y,stage.stageHeight-(apexFormsCollapsed ? 34 : 146)*apexFormsScale-14));
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
         var spanY:Number=Math.max(1,stage.stageHeight-(apexFormsCollapsed ? 34 : 146)*apexFormsScale-28);
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
