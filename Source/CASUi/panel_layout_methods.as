      // Display-only placement preferences. Dragging/scaling never queries CAS,
      // rebuilds item feeds, writes a Sim or flushes storage on mouse movement.
      private var apexPanels:Object;

      private function ApexPanelsInitialize() : void
      {
         apexPanels={root:null,grip:null,stage:null,store:null,bounds:null,opened:false,x:-1,y:-1,scale:1,locked:false,tooltips:[],preview:null,owner:"",
            host:null,helpers:null,drag:null,save:false,due:0,key:"",skipped:0,refreshes:0,consumer:null,consumer_running:null,
            refresh_max_ms:0,stamp_max_ms:0,stamp_ticket:"",stamp_context:"",stamp_wait:false,stamp_retry:0,requested:false,revision:0,job:null,
            slices:0,slice_max_ms:0,over_1ms:0,stale:0,cards_added:0,cards_reused:0,cards_removed:0,viewport:"",message:"",metrics:{},job_metrics:null,last_job_metrics:null,
            phase:"",phase_state:-1,phase_id:"",phase_group:-1};
         for each(var phase:String in ["context","selected_ids","product","category_part","eye_color","feed_publish","position_cells","current_layout"])
            apexPanels.metrics[phase]={calls:0,total_ms:0,max_ms:0,last_ms:0};
         try {
            apexPanels.store=flash.net.SharedObject.getLocal("TD1ApexCASPanels");
            var p:Object=apexPanels.store.data;
            if(p.version===1 && typeof p.scale=="number" && isFinite(p.scale) && p.scale>=0.35 && p.scale<=1.5 &&
               typeof p.x=="number" && typeof p.y=="number" && isFinite(p.x) && isFinite(p.y) &&
               (p.x==-1 || p.x>=0 && p.x<=1) && (p.y==-1 || p.y>=0 && p.y<=1) && p.locked is Boolean) {
               apexPanels.x=p.x;apexPanels.y=p.y;apexPanels.scale=p.scale;apexPanels.locked=p.locked;
            }
         } catch(error:Error) {apexPanels.store=null;}
         RegisterServiceHandler("ApexPanelRefreshGate",ApexPanelRefreshGate);
         RegisterServiceHandler("ApexPanelConsumer",ApexPanelConsumer);
         RegisterServiceHandler("ApexPanelPersistGate",ApexPanelPersistGate);
      }

      private function ApexPanelsDrawer() : Object
      {
         try {
            if(apexPanels.host==null)apexPanels.host=getDefinitionByName("dcc.history.HistoryHost");
            return apexPanels.host.dccHistoryRuntimeDrawer;
         }
         catch(missing:Error) {return null;}
      }

      private function ApexPanelsChanged() : void
      {
         apexPanels.save=true;apexPanels.due=flash.utils.getTimer()+700;
      }

      private function ApexPanelsButton(parent:flash.display.Sprite,name:String,label:String,x:Number,width:Number) : void
      {
         var button:flash.display.Sprite=new flash.display.Sprite();button.name="apexPanel_"+name;button.x=x;button.y=3;
         button.graphics.beginFill(0xffffff,0.98);button.graphics.lineStyle(1,0xb4cee1);
         button.graphics.drawRoundRect(0,0,width,24,8,8);button.graphics.endFill();button.buttonMode=true;button.mouseChildren=false;
         var caption:flash.text.TextField=ApexFormsText(button,label,6,3,width-8,11,0x275273);caption.name="caption";parent.addChild(button);
         ApexPanelsTooltip(button,name=="smaller" ? "Make the History and Current Outfit panels smaller (Ctrl + mouse wheel also works)." :
            name=="larger" ? "Make the History and Current Outfit panels larger, within the available screen." :
            name=="lock" ? "Lock or unlock panel dragging. Size controls remain available." : "Reset panel position, size and movement lock.");
         button.addEventListener(flash.events.MouseEvent.CLICK,ApexPanelsClick,false,20,true);
      }

      private function ApexPanelsTooltip(button:flash.display.Sprite,text:String) : void
      {
         var tooltip:TooltipObject=new TooltipObject(button);tooltip.Initialize({text:text,maxwidth:310},250);
         apexPanels.tooltips.push(tooltip);
      }

      private function ApexPanelsAdopt(root:flash.display.Sprite) : void
      {
         if(apexPanels.root===root) return;
         ApexPanelsDragEnd();
         for each(var tooltip:TooltipObject in apexPanels.tooltips)tooltip.Shutdown();apexPanels.tooltips=[];
         if(apexPanels.grip!=null && apexPanels.grip.parent!=null) apexPanels.grip.parent.removeChild(apexPanels.grip);
         if(apexPanels.preview!=null && apexPanels.preview.parent!=null)apexPanels.preview.parent.removeChild(apexPanels.preview);
         apexPanels.root=root;apexPanels.viewport="";apexPanels.key="";apexPanels.owner="";apexPanels.preview=null;
         apexPanels.job=null;apexPanels.stamp_ticket="";apexPanels.stamp_retry=0;apexPanels.requested=true;
         var grip:flash.display.Sprite=new flash.display.Sprite();grip.name="ApexPanelMoveAndScale";grip.y=-30;grip.visible=false;
         grip.graphics.beginFill(0xeaf5ff,0.98);grip.graphics.lineStyle(1,0xb4cee1);
         grip.graphics.drawRoundRect(0,0,358,30,10,10);grip.graphics.endFill();
         var handle:flash.display.Sprite=new flash.display.Sprite();handle.name="apexPanel_move";
         handle.graphics.beginFill(0xffffff,0.01);handle.graphics.drawRect(0,0,158,30);handle.graphics.endFill();
         handle.buttonMode=true;handle.mouseChildren=false;grip.addChild(handle);
         var label:flash.text.TextField=ApexFormsText(handle,"Move · 100%",9,6,148,11,0x275273);label.name="caption";
         ApexPanelsTooltip(handle,"Drag to move the History and Current Outfit panels. Ctrl + mouse wheel changes their size. Position and size are saved after you finish.");
         handle.addEventListener(flash.events.MouseEvent.MOUSE_DOWN,ApexPanelsDragStart,false,30,true);
         ApexPanelsButton(grip,"smaller","-",162,28);ApexPanelsButton(grip,"larger","+",194,28);
         ApexPanelsButton(grip,"lock","Lock",226,50);ApexPanelsButton(grip,"reset","Reset",280,70);
         root.addChild(grip);apexPanels.grip=grip;
      }

      private function ApexPanelsApply(target:flash.geom.Point=null) : void
      {
         var root:flash.display.Sprite=apexPanels.root as flash.display.Sprite;
         if(root==null || root.parent==null || stage==null) return;
         // HistoryDrawer.SetOpen owns this public visibility and its tab
         // arrangement. Its private anchors belong to SetLayout; closing alone
         // resets x but leaves our expanded y/scale behind. Give the retained
         // native layout authority back once per collapsed viewport.
         var body:flash.display.DisplayObject=root.getChildByName("body");
         apexPanels.opened=body!=null && body.visible;
         if(!apexPanels.opened) {
            apexPanels.grip.visible=false;apexPanels.bounds=null;
            if(apexPanels.drag!=null)ApexPanelsDragEnd();
            var collapsed:String="closed:"+stage.stageWidth+":"+stage.stageHeight;
            if(apexPanels.viewport!==collapsed && apexPanels.host!=null) {
               apexPanels.host.Layout(root.parent);apexPanels.viewport=collapsed;
            }
            return;
         }
         apexPanels.viewport="open";
         var origin:flash.geom.Point=root.parent.globalToLocal(new flash.geom.Point(0,0));
         var lower:flash.geom.Point=root.parent.globalToLocal(new flash.geom.Point(stage.stageWidth,stage.stageHeight-112));
         var top:flash.geom.Point=root.parent.globalToLocal(new flash.geom.Point(0,Math.max(340,stage.stageHeight*0.4)));
         var fit:Number=Math.max(0.2,Math.min(1,(lower.y-top.y)/656,(lower.x-origin.x)/790));
         var inset:flash.geom.Point=root.parent.globalToLocal(new flash.geom.Point(16,8));
         var size:Number=Math.min(fit*Number(apexPanels.scale),(lower.y-inset.y)/686,(lower.x-inset.x)/790);
         if(!isFinite(size) || size<=0)return;
         var bottom:flash.geom.Point=root.parent.localToGlobal(new flash.geom.Point(origin.x,lower.y-656*size));
         var unit:flash.geom.Point=root.parent.localToGlobal(new flash.geom.Point(origin.x+size,origin.y+size));
         var sx:Number=Math.abs(unit.x);var sy:Number=Math.abs(unit.y);
         var screen:flash.geom.Point=target==null ? new flash.geom.Point(apexPanels.x<0 ? 12 : Number(apexPanels.x)*stage.stageWidth,
            apexPanels.y<0 ? bottom.y : Number(apexPanels.y)*stage.stageHeight)
            : target;
         screen.x=Math.max(8,Math.min(Math.max(8,stage.stageWidth-8-790*sx),screen.x));
         screen.y=Math.max(8+30*sy,Math.min(Math.max(8+30*sy,stage.stageHeight-112-656*sy),screen.y));
         var local:flash.geom.Point=root.parent.globalToLocal(screen);
         if(root.x!=local.x) root.x=local.x;if(root.y!=local.y) root.y=local.y;
         if(root.scaleX!=size) root.scaleX=size;if(root.scaleY!=size) root.scaleY=size;
         if(target!=null) {apexPanels.x=screen.x/stage.stageWidth;apexPanels.y=screen.y/stage.stageHeight;}
         apexPanels.bounds={x:screen.x,y:screen.y,width:790*sx,height:656*sy,toolbar_top:screen.y-30*sy,
            viewport_width:stage.stageWidth,viewport_height:stage.stageHeight,actual_scale:size,conservative_envelope:true};
         apexPanels.grip.visible=root.visible;
         var handle:flash.display.Sprite=apexPanels.grip.getChildByName("apexPanel_move") as flash.display.Sprite;
         var caption:flash.text.TextField=handle==null ? null : handle.getChildByName("caption") as flash.text.TextField;
         var text:String=(apexPanels.locked ? "Locked" : "Move")+" · "+Math.round(Number(apexPanels.scale)*100)+"%";
         if(caption!=null && caption.text!=text)caption.text=text;
         if(handle!=null)handle.buttonMode=!apexPanels.locked;
         var lock:flash.display.DisplayObjectContainer=apexPanels.grip.getChildByName("apexPanel_lock") as flash.display.DisplayObjectContainer;
         var lockCaption:flash.text.TextField=lock==null ? null : lock.getChildByName("caption") as flash.text.TextField;
         var lockText:String=apexPanels.locked ? "Unlock" : "Lock";
         if(lockCaption!=null && lockCaption.text!=lockText)lockCaption.text=lockText;
      }

      private function ApexPanelsDragStart(event:flash.events.MouseEvent) : void
      {
         if(apexPanels==null || apexPanels.locked || apexPanels.root==null || apexPanels.root.parent==null || stage==null) return;
         ApexPanelsDragEnd();apexPanels.stage=stage;
         var point:flash.geom.Point=apexPanels.root.localToGlobal(new flash.geom.Point(0,0));
         apexPanels.drag={x:stage.mouseX-point.x,y:stage.mouseY-point.y};
         stage.addEventListener(flash.events.MouseEvent.MOUSE_MOVE,ApexPanelsDragMove,false,30,true);
         stage.addEventListener(flash.events.MouseEvent.MOUSE_UP,ApexPanelsDragEnd,false,30,true);
         stage.addEventListener(flash.events.Event.DEACTIVATE,ApexPanelsDragEnd,false,30,true);
         stage.addEventListener(flash.events.Event.MOUSE_LEAVE,ApexPanelsDragEnd,false,30,true);
         event.stopImmediatePropagation();event.preventDefault();
      }

      private function ApexPanelsDragMove(event:flash.events.MouseEvent) : void
      {
         if(apexPanels==null || apexPanels.drag==null || stage==null || apexPanels.root==null || apexPanels.root.parent==null) return;
         // The same display-only geometry authority clamps dragging, resizing
         // and restored preferences, so releasing the mouse cannot jump.
         ApexPanelsApply(new flash.geom.Point(stage.mouseX-Number(apexPanels.drag.x),stage.mouseY-Number(apexPanels.drag.y)));
         event.stopImmediatePropagation();event.preventDefault();
      }

      private function ApexPanelsDragEnd(event:flash.events.Event=null) : void
      {
         if(apexPanels==null) return;
         var screen:Object=apexPanels.stage;
         if(screen!=null) {
            screen.removeEventListener(flash.events.MouseEvent.MOUSE_MOVE,ApexPanelsDragMove);
            screen.removeEventListener(flash.events.MouseEvent.MOUSE_UP,ApexPanelsDragEnd);
            screen.removeEventListener(flash.events.Event.DEACTIVATE,ApexPanelsDragEnd);
            screen.removeEventListener(flash.events.Event.MOUSE_LEAVE,ApexPanelsDragEnd);
         }
         if(apexPanels.drag!=null) {apexPanels.drag=null;ApexPanelsChanged();}
      }

      private function ApexPanelsScale(value:Number) : void
      {
         var size:Number=Math.max(0.35,Math.min(1.5,Math.round(value*100)/100));
         if(apexPanels.scale==size)return;
         apexPanels.scale=size;ApexPanelsApply();ApexPanelsChanged();
      }

      private function ApexPanelsWheel(event:flash.events.MouseEvent) : void
      {
         if(apexPanels==null || !event.ctrlKey || event.delta==0 || apexPanels.root==null || !apexPanels.root.visible) return;
         var body:flash.display.DisplayObject=apexPanels.root.getChildByName("body");
         if(body==null || !body.visible)return;
         var node:flash.display.DisplayObject=event.target as flash.display.DisplayObject;
         while(node!=null && node!==apexPanels.root) node=node.parent;
         if(node==null)return;
         ApexPanelsScale(Number(apexPanels.scale)+(event.delta>0 ? 0.05 : -0.05));
         event.stopImmediatePropagation();event.preventDefault();
      }

      private function ApexPanelsClick(event:flash.events.MouseEvent) : void
      {
         ApexPanelsAction(String(event.currentTarget.name));
         event.stopImmediatePropagation();
      }

      private function ApexPanelsFrame() : void
      {
         if(apexPanels==null || stage==null)return;
         if(apexPanels.stage!==stage) {
            ApexPanelsDragEnd();
            if(apexPanels.stage!=null) {
               apexPanels.stage.removeEventListener(flash.events.MouseEvent.MOUSE_WHEEL,ApexPanelsWheel,true);
               apexPanels.stage.removeEventListener(flash.events.MouseEvent.MOUSE_DOWN,ApexPanelsCapture,true);
               apexPanels.stage.removeEventListener(flash.events.MouseEvent.CLICK,ApexPanelsCapture,true);
            }
            apexPanels.stage=stage;stage.addEventListener(flash.events.MouseEvent.MOUSE_WHEEL,ApexPanelsWheel,true,50,true);
            stage.addEventListener(flash.events.MouseEvent.MOUSE_DOWN,ApexPanelsCapture,true,10000,true);
            stage.addEventListener(flash.events.MouseEvent.CLICK,ApexPanelsCapture,true,10000,true);
         }
         var drawer:Object=ApexPanelsDrawer();
         if(drawer!=null && drawer[0] is flash.display.Sprite) {ApexPanelsAdopt(drawer[0]);ApexPanelsApply();}
         var body:flash.display.DisplayObject=drawer==null || drawer[0]==null ? null : drawer[0].getChildByName("body");
         // Observe only retained display identity while idle. Native outfit
         // queries remain inside requested work; form/member transitions hide
         // the previous owner's actionable cards before a new job can publish.
         // Columns and thumbnail scale are display geometry. Native handlers
         // already reflow them; they must not invalidate appearance products.
         var owner:String=drawer==null || mCurrSimInfo==null || apexNativeChannel=="" || apexFormsSelectedId=="" ||
            apexFormsDesiredId!="" || apexFormsApplying ? "" : apexNativeChannel+"|"+mCurrSimInfo.simId+"|"+apexFormsSelectedId+
            "|"+mCurrSimInfo.gender+"|"+mCurrSimInfo.age+"|"+mCurrSimInfo.speciesType;
         if(owner!==apexPanels.owner) {
            if(apexPanels.job!=null)apexPanels.stale++;
            apexPanels.owner=owner;apexPanels.key="";apexPanels.job=null;apexPanels.stamp_ticket="";
            apexPanels.stamp_retry=0;apexPanels.requested=true;
         }
         if(apexPanels.consumer!=null && (apexPanels.consumer.drawer!==drawer || apexPanels.consumer.owner!==owner)) {
            ApexPanelsConsumerCancel(apexPanels.consumer,"Outfit action canceled because its owner changed");
         }
         // Lifecycle checks cannot depend on an open Current Outfit tab: the
         // user may close the save dialog or collapse the drawer while queued.
         if(apexPanels.consumer!=null)ApexPanelsConsume(drawer,"",true);
         if(drawer!=null && body!=null && body.visible && drawer[40]!=null && (drawer[40].visible || apexPanels.consumer!=null) && (apexPanels.requested || apexPanels.job!=null || apexPanels.consumer!=null) && apexPendingFields==null && !apexReceiving &&
            apexFormsDesiredId=="" && !apexFormsApplying && apexPanels.drag==null &&
            (apexColumns==null || !apexColumns.drag && !apexColumns.scale_drag) && flash.utils.getTimer()>=int(apexPanels.stamp_retry)) {
            var started:int=flash.utils.getTimer();
            var measured:Object=apexPanels.job==null ? null : apexPanels.job_metrics;
            apexPanels.stamp_wait=false;
            try {
               var context:String=drawer==null ? "" : ApexPanelsContext(drawer);
               for(var step:int=0;step<8;step++) {
                  var publish:Boolean=apexPanels.job!=null && apexPanels.job.phase=="publish";
                  ApexPanelsWork(drawer,context);
                  if(publish || apexPanels.stamp_wait || flash.utils.getTimer()-started>=1 || (!apexPanels.requested && apexPanels.job==null))break;
               }
               if(apexPanels.consumer!=null)ApexPanelsConsume(drawer,context);
            }
            catch(error:Error) {apexPanels.message=error.message;apexPanels.key="";apexPanels.job=null;apexPanels.stamp_ticket="";apexPanels.requested=false;
               if(apexPanels.consumer!=null)ApexPanelsConsumerCancel(apexPanels.consumer,error.message);
               if(measured!=null)measured.failure=error.message;}
            var elapsed:int=flash.utils.getTimer()-started;
            apexPanels.slices++;apexPanels.slice_max_ms=Math.max(apexPanels.slice_max_ms,elapsed);
            if(elapsed>1)apexPanels.over_1ms++;
            if(apexPanels.job_metrics!=null && (measured!=null || apexPanels.job!=null)) {
               var timing:Object=apexPanels.job_metrics;timing.slices++;timing.slice_max_ms=Math.max(timing.slice_max_ms,elapsed);
               timing.elapsed_ms=flash.utils.getTimer()-int(timing.started_ms);timing.last_phase=apexPanels.phase;
               timing.last_state=apexPanels.phase_state;timing.last_id=apexPanels.phase_id;timing.last_group=apexPanels.phase_group;
               if(apexPanels.job==null)apexPanels.last_job_metrics=timing;
            }
         }
         ApexPanelsPreview(drawer);
         if(apexPanels.save && flash.utils.getTimer()>=int(apexPanels.due) && apexPanels.drag==null &&
            (apexColumns==null || !apexColumns.drag && !apexColumns.scale_drag) && apexPendingFields==null && !apexReceiving) {
            apexPanels.save=false;
            try {if(apexPanels.store!=null) {var p:Object=apexPanels.store.data;
               p.version=1;p.x=apexPanels.x;p.y=apexPanels.y;p.scale=apexPanels.scale;p.locked=apexPanels.locked;apexPanels.store.flush();}}
            catch(saveError:Error) {apexPanels.message=saveError.message;}
         }
      }

      private function ApexPanelsPreview(drawer:Object) : void
      {
         if(drawer==null || !(drawer[40] is flash.display.Sprite))return;
         var pending:Boolean=apexPanels.key=="" || apexPanels.requested || apexPanels.job!=null;
         var content:flash.display.Sprite=drawer[80] as flash.display.Sprite;
         if(content!=null) {content.visible=!pending;content.mouseEnabled=!pending;}
         // Mask only Current Outfit's content. History, saved outfits, tabs,
         // favorites, hide controls and all original donor handlers stay intact.
         if(apexPanels.preview==null || apexPanels.preview.parent!==drawer[40]) {
            if(apexPanels.preview!=null && apexPanels.preview.parent!=null)apexPanels.preview.parent.removeChild(apexPanels.preview);
            apexPanels.preview=ApexFormsText(drawer[40],"Updating outfit…",12,67,300,12,0x47708b);
            apexPanels.preview.name="ApexCurrentOutfitRefresh";apexPanels.preview.mouseEnabled=false;
            apexPanels.preview.wordWrap=true;apexPanels.preview.height=44;
         }
         var text:String=apexPanels.message=="" ? "Updating outfit…" : "Preview unavailable. Reopen this tab to retry.";
         if(apexPanels.preview.text!=text)apexPanels.preview.text=text;
         apexPanels.preview.visible=pending;
      }

      private function ApexPanelRefreshGate(value:Object=null) : Boolean
      {
         if(apexPanels==null)return false;
         if(apexPanels.consumer_running!=null)return true;
         // Input callback: coalesce intent only. No engine, catalogue, file,
         // product resolution or list rebuilding runs in this call stack.
         apexPanels.requested=true;apexPanels.revision++;return true;
      }

      private function ApexPanelsContext(drawer:Object) : String
      {
         if(mCurrSimInfo==null || apexNativeChannel=="" || apexFormsSelectedId=="")return "";
         apexPanels.phase="context";apexPanels.phase_state=-1;apexPanels.phase_id="";apexPanels.phase_group=-1;
         var started:int=flash.utils.getTimer();var slot:Object;
         try {slot=CommunicationManager.CallGameService("CasGetCurrSimOutfitSlot",null,true);}
         finally {
            var elapsed:int=flash.utils.getTimer()-started;var counter:Object=apexPanels.metrics.context;
            counter.calls++;counter.total_ms+=elapsed;counter.max_ms=Math.max(counter.max_ms,elapsed);counter.last_ms=elapsed;
            if(apexPanels.job!=null && apexPanels.job_metrics!=null) {counter=apexPanels.job_metrics.phases.context;
               counter.calls++;counter.total_ms+=elapsed;counter.max_ms=Math.max(counter.max_ms,elapsed);counter.last_ms=elapsed;}
         }
         if(slot==null || !(slot.outfit_type is int) || !(slot.outfit_index is int))return "";
         return String(mCurrSimInfo.simId)+"|"+apexFormsSelectedId+"|"+slot.outfit_type+"|"+slot.outfit_index+
            "|"+mCurrSimInfo.gender+"|"+mCurrSimInfo.age+"|"+mCurrSimInfo.speciesType;
      }

      private function ApexPanelsStamp(context:String) : String
      {
         var start:int=flash.utils.getTimer();
         apexPanels.stamp_wait=true;
         var ticket:String=String(apexPanels.stamp_ticket);
         var stamp:Array=ApexNativeExchange(ticket=="" ? "EQUIPPEDSTAMPSTART|"+apexNativeChannel :
            "EQUIPPEDSTAMPREAD|"+apexNativeChannel+"|"+ticket).split("|");
         apexPanels.stamp_max_ms=Math.max(apexPanels.stamp_max_ms,flash.utils.getTimer()-start);
         if(ticket=="") {
            if(stamp.length==1 && stamp[0]=="STAMPBUSY") {apexPanels.stamp_retry=start+100;return "";}
            if(stamp.length!=4 || stamp[0]!="STAMPJOB" || stamp[1]!==String(mCurrSimInfo.simId) ||
               stamp[2]!==apexFormsSelectedId || !/^[1-9][0-9]{0,19}$/.test(stamp[3]))throw new Error("Outfit preview stamp request refused");
            apexPanels.stamp_ticket=String(stamp[3]);apexPanels.stamp_context=context;return "";
         }
         if(stamp.length==2 && stamp[1]===ticket) {
            if(stamp[0]=="STAMPPENDING")return "";
            if(stamp[0]=="STAMPSTALE") {
               if(apexPanels.consumer!=null)
                  ApexPanelsConsumerCancel(apexPanels.consumer,"Outfit action canceled because its captured appearance became stale");
               apexPanels.stamp_ticket="";apexPanels.key="";apexPanels.job=null;apexPanels.requested=true;
               apexPanels.stamp_retry=start+100;apexPanels.stale++;return "";
            }
         }
         if(stamp.length!=4 || stamp[0]!="EQUIPPEDSTAMP" || stamp[1]!==String(mCurrSimInfo.simId) ||
            stamp[2]!==apexFormsSelectedId || !/^[0-9a-f]{64}$/.test(stamp[3]))throw new Error("Outfit preview identity changed");
         apexPanels.stamp_ticket="";apexPanels.stamp_retry=0;
         return String(stamp[3]);
      }

      private function ApexPanelsWork(drawer:Object,context:String) : void
      {
         if(drawer==null || drawer[40]==null || (!drawer[40].visible && apexPanels.consumer==null) || drawer[0]==null || drawer[0].parent==null) {
            apexPanels.job=null;return;
         }
         var body:Object=drawer[0].getChildByName("body");
         if(body==null || !body.visible)return;
         if(context=="")return;
         if(apexPanels.stamp_ticket!="" && apexPanels.stamp_context!==context) {
            apexPanels.stamp_ticket="";apexPanels.key="";apexPanels.job=null;apexPanels.requested=true;apexPanels.stale++;
         }
         var job:Object=apexPanels.job;
         if(job!=null && (job.drawer!==drawer || job.context!==context)) {
            apexPanels.job=null;apexPanels.key="";apexPanels.stamp_ticket="";apexPanels.requested=true;apexPanels.stale++;job=null;
         }
         if(job==null) {
            if(!apexPanels.requested)return;
            var stamp:String=ApexPanelsStamp(context);if(stamp=="")return;
            apexPanels.requested=false;
            if(apexPanels.consumer!=null) {
               if(apexPanels.consumer.context!==context || (apexPanels.consumer.stamp!="" && apexPanels.consumer.stamp!==stamp)) {
                  ApexPanelsConsumerCancel(apexPanels.consumer,"Outfit action canceled because its appearance changed");
                  apexPanels.requested=true;return;
               }
               apexPanels.consumer.stamp=stamp;
            }
            var key:String=context+"|"+stamp;
            if(key===apexPanels.key) {apexPanels.skipped++;return;}
            if(apexPanels.helpers==null) {
               apexPanels.helpers={};
            }
            for each(var name:String in ["SavedOutfitNames","OutfitSwatchRoute","HairSwatches","OutfitRemoval","OutfitCategory","CurrentRemove"])
               if(apexPanels.helpers[name]==null)apexPanels.helpers[name]=getDefinitionByName("dcc.history."+name);
            if(apexPanels.job_metrics!=null)apexPanels.last_job_metrics=apexPanels.job_metrics;
            apexPanels.job_metrics={started_ms:flash.utils.getTimer(),elapsed_ms:0,slices:0,slice_max_ms:0,completed:false,
               last_phase:"",last_state:-1,last_id:"",last_group:-1,phases:{}};
            for each(var phase:String in ["context","selected_ids","product","category_part","eye_color","feed_publish","position_cells","current_layout"])
               apexPanels.job_metrics.phases[phase]={calls:0,total_ms:0,max_ms:0,last_ms:0};
            apexPanels.job={drawer:drawer,context:context,stamp:stamp,key:key,group:0,category:0,ids:null,item:0,
               products:[[],[],[],[]],seen:[{},{},{},{}],phase:"resolve",publish:0,publish_item:0,revision:apexPanels.revision,started:flash.utils.getTimer()};
            return;
         }
         var helpers:Object=apexPanels.helpers;
         var started:int;var elapsed:int;var counter:Object;
         if(job.phase=="resolve") {
            if(job.group>=4) {job.phase="verify";return;}
            var states:Array=drawer[70+int(job.group)];
            if(states==null || int(job.category)>=states.length) {
               apexPanels.phase="eye_color";apexPanels.phase_state=-1;apexPanels.phase_id="";apexPanels.phase_group=int(job.group);
               started=flash.utils.getTimer();
               try {helpers.SavedOutfitNames.AddEyeColor(job.products[int(job.group)],int(job.group));}
               finally {elapsed=flash.utils.getTimer()-started;counter=apexPanels.metrics.eye_color;
                  counter.calls++;counter.total_ms+=elapsed;counter.max_ms=Math.max(counter.max_ms,elapsed);counter.last_ms=elapsed;
                  counter=apexPanels.job_metrics.phases.eye_color;
                  counter.calls++;counter.total_ms+=elapsed;counter.max_ms=Math.max(counter.max_ms,elapsed);counter.last_ms=elapsed;}
               job.group++;job.category=0;job.ids=null;return;
            }
            var state:int=int(states[int(job.category)]);
            if(job.ids==null) {
               // One engine category query per frame. Never a full category
               // sweep or a product-resolution loop on the input stack.
               apexPanels.phase="selected_ids";apexPanels.phase_state=state;apexPanels.phase_id="";apexPanels.phase_group=int(job.group);
               started=flash.utils.getTimer();
               try {job.ids=CASAPI.GetCatalogItemsSelected(state);}
               finally {elapsed=flash.utils.getTimer()-started;counter=apexPanels.metrics.selected_ids;
                  counter.calls++;counter.total_ms+=elapsed;counter.max_ms=Math.max(counter.max_ms,elapsed);counter.last_ms=elapsed;
                  counter=apexPanels.job_metrics.phases.selected_ids;
                  counter.calls++;counter.total_ms+=elapsed;counter.max_ms=Math.max(counter.max_ms,elapsed);counter.last_ms=elapsed;}
               if(job.ids==null)job.ids=[];job.item=0;return;
            }
            if(int(job.item)>=job.ids.length) {job.ids=null;job.category++;return;}
            var id:String=String(job.ids[int(job.item++)]);
            if(id=="" || id=="0" || job.seen[int(job.group)][id]===true)return;
            apexPanels.phase="product";apexPanels.phase_state=state;apexPanels.phase_id=id;apexPanels.phase_group=int(job.group);
            started=flash.utils.getTimer();var raw:Object;
            try {raw=drawer[0].parent.mcClothingPanel.GetCatalogProduct(id);}
            finally {elapsed=flash.utils.getTimer()-started;counter=apexPanels.metrics.product;
               counter.calls++;counter.total_ms+=elapsed;counter.max_ms=Math.max(counter.max_ms,elapsed);counter.last_ms=elapsed;
               counter=apexPanels.job_metrics.phases.product;
               counter.calls++;counter.total_ms+=elapsed;counter.max_ms=Math.max(counter.max_ms,elapsed);counter.last_ms=elapsed;}
            apexPanels.phase="category_part";started=flash.utils.getTimer();var eligible:Boolean;
            try {eligible=helpers.SavedOutfitNames.CurrentCategoryPart(raw,state,id);}
            finally {elapsed=flash.utils.getTimer()-started;counter=apexPanels.metrics.category_part;
               counter.calls++;counter.total_ms+=elapsed;counter.max_ms=Math.max(counter.max_ms,elapsed);counter.last_ms=elapsed;
               counter=apexPanels.job_metrics.phases.category_part;
               counter.calls++;counter.total_ms+=elapsed;counter.max_ms=Math.max(counter.max_ms,elapsed);counter.last_ms=elapsed;}
            if(!eligible)return;
            var product:CASCatalogProduct=new CASCatalogProduct(raw);
            helpers.OutfitSwatchRoute.Register(product,state,id);helpers.HairSwatches.Register(product,state);
            helpers.OutfitRemoval.Register(product,state);helpers.OutfitCategory.Register(product,state);
            job.seen[int(job.group)][id]=true;job.products[int(job.group)].push(product);return;
         }
         if(job.phase=="verify") {
            var verified:String=ApexPanelsStamp(context);if(verified=="")return;
            if(verified!==job.stamp) {
               if(apexPanels.consumer!=null)ApexPanelsConsumerCancel(apexPanels.consumer,"Outfit action canceled because its appearance changed");
               apexPanels.job=null;apexPanels.key="";apexPanels.requested=true;apexPanels.stale++;return;
            }
            job.revision=apexPanels.revision;job.phase="publish";return;
         }
         if(job.revision!==apexPanels.revision) {apexPanels.job=null;apexPanels.requested=true;apexPanels.stale++;return;}
         var group:int=int(job.publish);var products:Array=job.products[group];
         // Keep the donor's original card instances. A full clear/add destroys
         // every timeline, image and control tree even when only one slot has
         // changed. Rebind one complete product per frame; never reuse another
         // owner's product or skip the exact freshness check above.
         apexPanels.phase="feed_publish";apexPanels.phase_state=-1;apexPanels.phase_id="";apexPanels.phase_group=group;
         var complete:Boolean=false;var index:int=int(job.publish_item);
         started=flash.utils.getTimer();
         try {
            var feed:Object=drawer[47+group*3];if(feed==null)throw new Error("Current Outfit feed is unavailable");
            if(index<products.length) {
               apexPanels.phase_id=String(products[index].data_id);
               if(index<int(feed.length)) {feed.ReplaceItemAt(index,products[index]);apexPanels.cards_reused++;}
               else {feed.AddItem(products[index]);apexPanels.cards_added++;}
               job.publish_item=index+1;
            } else if(int(feed.length)>products.length) {
               feed.RemoveItemAt(int(feed.length)-1);apexPanels.cards_removed++;
            } else {
               helpers.CurrentRemove.Record(group,products);drawer[64+group]=products.length;complete=true;
            }
         }
         finally {elapsed=flash.utils.getTimer()-started;counter=apexPanels.metrics.feed_publish;
            counter.calls++;counter.total_ms+=elapsed;counter.max_ms=Math.max(counter.max_ms,elapsed);counter.last_ms=elapsed;
            counter=apexPanels.job_metrics.phases.feed_publish;
            counter.calls++;counter.total_ms+=elapsed;counter.max_ms=Math.max(counter.max_ms,elapsed);counter.last_ms=elapsed;}
         if(!complete)return;
         var layout:Object=drawer[49+group*3];
         if(layout!=null) {
            apexPanels.phase="position_cells";started=flash.utils.getTimer();
            try {layout.PositionCells();}
            finally {elapsed=flash.utils.getTimer()-started;counter=apexPanels.metrics.position_cells;
               counter.calls++;counter.total_ms+=elapsed;counter.max_ms=Math.max(counter.max_ms,elapsed);counter.last_ms=elapsed;
               counter=apexPanels.job_metrics.phases.position_cells;
               counter.calls++;counter.total_ms+=elapsed;counter.max_ms=Math.max(counter.max_ms,elapsed);counter.last_ms=elapsed;}
         }
         job.publish_item=0;
         if(++job.publish==4) {
            apexPanels.phase="current_layout";started=flash.utils.getTimer();
            try {apexPanels.host.LayoutCurrentOutfit();}
            finally {elapsed=flash.utils.getTimer()-started;counter=apexPanels.metrics.current_layout;
               counter.calls++;counter.total_ms+=elapsed;counter.max_ms=Math.max(counter.max_ms,elapsed);counter.last_ms=elapsed;
               counter=apexPanels.job_metrics.phases.current_layout;
               counter.calls++;counter.total_ms+=elapsed;counter.max_ms=Math.max(counter.max_ms,elapsed);counter.last_ms=elapsed;}
            apexPanels.job_metrics.completed=true;
            apexPanels.key=job.key;apexPanels.refreshes++;
            apexPanels.refresh_max_ms=Math.max(apexPanels.refresh_max_ms,flash.utils.getTimer()-int(job.started));
            apexPanels.job=null;apexPanels.message="";
         }
      }

      private function ApexPanelsCommand(value:String) : void
      {
         var fields:Array=value.split(",");
         if(apexPanels==null || fields.length!=4)throw new Error("Panel layout needs x, y, scale and lock");
         var x:Number=Number(fields[0]);var y:Number=Number(fields[1]);var size:Number=Number(fields[2]);
         if(!isFinite(x) || !isFinite(y) || !isFinite(size) || x< -1 || x>1 || y< -1 || y>1 ||
            (x<0 && x!= -1) || (y<0 && y!= -1) || size<0.35 || size>1.5 || ["0","1"].indexOf(fields[3])<0)
            throw new Error("Invalid bounded panel layout");
         ApexPanelsDragEnd();apexPanels.x=x;apexPanels.y=y;apexPanels.scale=size;apexPanels.locked=fields[3]=="1";
         ApexPanelsApply();ApexPanelsChanged();
      }

      private function ApexPanelsStatus() : Object
      {
         if(apexPanels==null)return null;
         return {available:apexPanels.root!=null,expanded:apexPanels.opened,scale:apexPanels.scale,x:apexPanels.x,y:apexPanels.y,
            locked:apexPanels.locked,dragging:apexPanels.drag!=null,save_pending:apexPanels.save,
            refreshes:apexPanels.refreshes,skipped_unchanged:apexPanels.skipped,refresh_max_ms:apexPanels.refresh_max_ms,
            pending:apexPanels.requested || apexPanels.job!=null,slices:apexPanels.slices,slice_max_ms:apexPanels.slice_max_ms,
            over_1ms:apexPanels.over_1ms,stale_discarded:apexPanels.stale,
            cards_added:apexPanels.cards_added,cards_reused:apexPanels.cards_reused,cards_removed:apexPanels.cards_removed,
            consumer_pending:apexPanels.consumer==null ? "" : String(apexPanels.consumer.kind),
            stamp_max_ms:apexPanels.stamp_max_ms,stamp_pending:apexPanels.stamp_ticket!="",bounds:apexPanels.bounds,
            last_phase:apexPanels.phase,last_state:apexPanels.phase_state,last_id:apexPanels.phase_id,last_group:apexPanels.phase_group,
            phase_timing_ms:apexPanels.metrics,active_job_timing:apexPanels.job==null ? null : apexPanels.job_metrics,
            last_job_timing:apexPanels.last_job_metrics,last_job_max_ms:apexPanels.last_job_metrics==null ? 0 : apexPanels.last_job_metrics.slice_max_ms,
            catalog_controls:apexColumns==null ? null : apexColumns.bounds,message:apexPanels.message,appearance_written:false};
      }

      private function ApexPanelsDispose() : void
      {
         if(apexPanels==null)return;
         ApexPanelsDragEnd();
         UnregisterServiceHandler("ApexPanelRefreshGate",ApexPanelRefreshGate);
         UnregisterServiceHandler("ApexPanelConsumer",ApexPanelConsumer);
         UnregisterServiceHandler("ApexPanelPersistGate",ApexPanelPersistGate);
         if(apexPanels.stage!=null) {
            apexPanels.stage.removeEventListener(flash.events.MouseEvent.MOUSE_WHEEL,ApexPanelsWheel,true);
            apexPanels.stage.removeEventListener(flash.events.MouseEvent.MOUSE_DOWN,ApexPanelsCapture,true);
            apexPanels.stage.removeEventListener(flash.events.MouseEvent.CLICK,ApexPanelsCapture,true);
         }
         for each(var tooltip:TooltipObject in apexPanels.tooltips)tooltip.Shutdown();
         if(apexPanels.preview!=null && apexPanels.preview.parent!=null)apexPanels.preview.parent.removeChild(apexPanels.preview);
         if(apexPanels.grip!=null && apexPanels.grip.parent!=null)apexPanels.grip.parent.removeChild(apexPanels.grip);
         apexPanels=null;
      }
