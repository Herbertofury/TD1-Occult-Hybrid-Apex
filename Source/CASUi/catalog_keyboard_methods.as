      private var apexKeyStage:flash.display.Stage;
      private var apexKeyIntent:int=0;
      private var apexKeyIndex:int=-1;
      private var apexKeyFeed:Object;
      private var apexKeyContext:String="";
      private var apexKeyFocus:flash.display.Sprite;
      private var apexKeyMessage:String="";
      private var apexKeyBounds:String="";
      private var apexKeyItem:Object;
      private var apexKeyQueue:Array;
      private var apexKeyReceipt:Object;
      private var apexKeyInjecting:Boolean=false;
      private var apexKeyReceived:int=0;
      private var apexKeyLastCode:int=0;
      private var apexKeyRejected:String="";

      private function ApexCatalogKeyboardInitialize() : void
      {
         if(stage==null || apexKeyStage===stage) return;
         ApexCatalogKeyboardDispose();apexKeyStage=stage;apexKeyQueue=[];
         apexKeyStage.addEventListener(flash.events.KeyboardEvent.KEY_DOWN,ApexCatalogKeyDown,true,20,true);
         apexKeyStage.addEventListener(flash.events.KeyboardEvent.KEY_DOWN,ApexCatalogKeyDown,false,20,true);
      }

      private function ApexCatalogKeyboardDispose() : void
      {
         if(apexKeyStage!=null) {apexKeyStage.removeEventListener(flash.events.KeyboardEvent.KEY_DOWN,ApexCatalogKeyDown,true);
            apexKeyStage.removeEventListener(flash.events.KeyboardEvent.KEY_DOWN,ApexCatalogKeyDown,false);}
         if(apexKeyFocus!=null && apexKeyFocus.parent!=null) apexKeyFocus.parent.removeChild(apexKeyFocus);
         apexKeyStage=null;apexKeyIntent=0;apexKeyIndex=-1;apexKeyFeed=null;apexKeyContext="";apexKeyFocus=null;apexKeyBounds="";apexKeyItem=null;apexKeyMessage="";apexKeyQueue=[];
      }

      private function ApexCatalogKeyDown(event:flash.events.KeyboardEvent) : void
      {
         apexKeyReceived=Math.min(2147483647,apexKeyReceived+1);apexKeyLastCode=int(event.keyCode);
         if(event.ctrlKey || event.altKey || event.shiftKey) {apexKeyRejected="modifier held";return;}
         if(stage==null || apexDisconnected) {apexKeyRejected="stage disconnected";return;}
         if(!apexKeyInjecting && (apexPendingFields!=null || apexReceiving)) {apexKeyRejected="command busy";return;}
         if(ApexCatalogKeyboardTyping()) {apexKeyRejected="text input owns focus";return;}
         if([13,33,34,35,36,37,38,39,40].indexOf(int(event.keyCode))<0) {apexKeyRejected="unsupported key code";return;}
         apexKeyRejected="";
         var panel:Object=mCurrentPanel;
         if(panel==null || !panel.visible || panel.mcTileList==null || !panel.mcTileList.visible) {apexKeyRejected="no visible catalog";return;}
         if(Boolean(CommunicationManager.CallUIService("IsUILoadingScreenVisible")) ||
            Boolean(CommunicationManager.CallUIService("IsModalVisible")) || Boolean(CommunicationManager.CallUIService("IsDialogModalVisible"))) {apexKeyQueue=[];apexKeyIntent=0;return;}
         // The key callback performs no catalog/native query, selection or
         // reflow. The owned idle phase below consumes one latest key intent.
         if(apexKeyQueue==null) apexKeyQueue=[];
         if(apexKeyQueue.length>=64) {apexKeyMessage="Keyboard input is busy; wait for the catalog.";event.preventDefault();event.stopImmediatePropagation();return;}
         apexKeyQueue.push({key:int(event.keyCode),sim:apexBoundSim,owner:apexFormsSelectedId,
            panel:panel,state:mCurrState,feed:panel.mcTileList.mGridLayout.GetDataFeed(),
            route:apexKeyInjecting ? "shared-keyboard-handler" : "stage-keyboard-event"});
         apexKeyIntent=int(apexKeyQueue[0].key);event.preventDefault();event.stopImmediatePropagation();
      }

      private function ApexCatalogKeyboardFrame(controlled:Boolean=false) : void
      {
         try {
         if(apexKeyStage==null) ApexCatalogKeyboardInitialize();
         if(apexKeyIntent==0 && apexKeyIndex<0) return;
         if(stage==null || (!controlled && (apexPendingFields!=null || apexReceiving)) || apexDisconnected) return;
         var panel:Object=mCurrentPanel;
         var list:Object=panel==null ? null : panel.mcTileList;
         var grid:Object=list==null ? null : list.mGridLayout;
         if(panel==null || !panel.visible || list==null || !list.visible || grid==null || mCurrSimInfo==null) {
            apexKeyIntent=0;apexKeyQueue=[];apexKeyIndex=-1;if(apexKeyFocus!=null) apexKeyFocus.visible=false;return;
         }
         var feed:Object=grid.GetDataFeed();
         var context:String=String(mCurrSimInfo.simId)+"|"+apexFormsSelectedId+"|"+mCurrState+"|"+apexEquippedActive;
         if(feed!==apexKeyFeed || context!=apexKeyContext || apexKeyIndex>=int(feed.length) || apexKeyIndex>=0 && feed.RequestItemAt(apexKeyIndex)!==apexKeyItem) {
            apexKeyFeed=feed;apexKeyContext=context;apexKeyIndex=-1;apexKeyItem=null;apexKeyBounds="";
            if(apexKeyFocus!=null) apexKeyFocus.visible=false;
         }
         if(apexKeyIntent!=0) {
            var intent:Object=apexKeyQueue==null || apexKeyQueue.length==0 ? null : apexKeyQueue.shift();
            apexKeyIntent=apexKeyQueue!=null && apexKeyQueue.length>0 ? int(apexKeyQueue[0].key) : 0;
            if(intent==null || intent.sim!=String(mCurrSimInfo.simId) || intent.owner!=apexFormsSelectedId ||
               intent.panel!==panel || int(intent.state)!=mCurrState || intent.feed!==feed) {
               apexKeyRejected="catalog context changed";apexKeyQueue=[];apexKeyIntent=0;return;
            }
            var key:int=int(intent.key);
            if((!controlled && ApexCatalogKeyboardTyping()) || Boolean(CommunicationManager.CallUIService("IsUILoadingScreenVisible")) ||
               Boolean(CommunicationManager.CallUIService("IsModalVisible")) || Boolean(CommunicationManager.CallUIService("IsDialogModalVisible"))) {apexKeyQueue=[];apexKeyIntent=0;return;}
            var count:int=int(feed.length);if(count<1) return;
            var columns:int=Math.max(1,int(grid.GetGridDimensions()[grid.Horizontal ? 0 : 1]));
            var before:int=apexKeyIndex;
            if(before<0) {
               var selected:Array=feed.GetSelectedIndices();
               before=selected!=null && selected.length>0 ? int(selected[0]) : 0;
            }
            var target:int=before;var page:int=0;
            if(key==37) target--;
            else if(key==39) target++;
            else if(key==38) target-=columns;
            else if(key==40) target+=columns;
            else if(key==36) target=0;
            else if(key==35) target=count-1;
            else if(key==33 || key==34) {
               var cells:Object=grid.GetVisibleCells(list.mScrollerView.GetScrollingRegion(),list.mScrollerView);
               page=columns*Math.max(1,int((cells==null ? columns : cells.length)/columns)-1);
               target+=(key==33 ? -page : page);
            }
            target=Math.max(0,Math.min(count-1,target));apexKeyIndex=target;apexKeyItem=feed.RequestItemAt(target);
            if(key==13) {
               // Reuse the exact native card click route, including its form,
               // swatch, eligibility, undo and equipped-view adapters.
               var item:Object=feed.RequestItemAt(target);
               if(item==null) return;
               var click:GridEvent=new GridEvent(
                  GridEvent.CELL_EVENT+PushButtonEvent.CLICK,null,null,item,false,target,target);
               list.GetGridView().dispatchEvent(click);
            } else {
               var targetCell:flash.display.DisplayObject=grid.GetViewAtIndex(target) as flash.display.DisplayObject;
               var outside:Boolean=targetCell==null;
               if(targetCell!=null) {
                  var cellBounds:flash.geom.Rectangle=targetCell.getBounds(list.mScrollerView);
                  var viewport:flash.geom.Rectangle=list.mScrollerView.GetScrollingRegion();
                  outside=cellBounds.top<viewport.top || cellBounds.bottom>viewport.bottom;
               }
               if(outside || key==33 || key==34) list.mSlider.SetCurrentValue(grid.GetPositionOfIndex(target)+list.ScrollerViewMargin.mTop,false);
            }
            apexKeyReceipt={key:key,sim_id:String(mCurrSimInfo.simId),owner_id:apexFormsSelectedId,
               menu_state:mCurrState,menu_state_before:int(intent.state),source_route:String(intent.route),
               index_before:before,index_after:target,count:count,columns:columns,
               page_step:page,click_dispatched:key==13};
         }
         if(apexKeyIndex<0) return;
         apexKeyMessage="Card "+(apexKeyIndex+1)+" of "+feed.length+" / arrows browse, Enter selects";
         var cell:flash.display.DisplayObject=grid.GetViewAtIndex(apexKeyIndex) as flash.display.DisplayObject;
         if(apexKeyFocus==null) {
            apexKeyFocus=new flash.display.Sprite();apexKeyFocus.mouseEnabled=false;apexKeyFocus.mouseChildren=false;
         }
         if(apexKeyFocus.parent!==list.GetGridView()) {
            list.GetGridView().addChild(apexKeyFocus);apexKeyBounds="";
         }
         apexKeyFocus.visible=cell!=null && cell.stage!=null;
         if(!apexKeyFocus.visible) return;
         var rect:flash.geom.Rectangle=cell.getBounds(apexKeyFocus.parent);
         var boundsKey:String=rect.x+":"+rect.y+":"+rect.width+":"+rect.height;
         if(boundsKey==apexKeyBounds) return;
         apexKeyBounds=boundsKey;
         apexKeyFocus.graphics.clear();apexKeyFocus.graphics.lineStyle(2,0xffffff,1);
         apexKeyFocus.graphics.drawRoundRect(rect.x+2,rect.y+2,Math.max(1,rect.width-4),Math.max(1,rect.height-4),8,8);
         apexKeyMessage="Card "+(apexKeyIndex+1)+" of "+feed.length+" / arrows browse, Enter selects";
         } catch(keyboardError:Error) {
            apexKeyQueue=[];apexKeyIntent=0;apexKeyIndex=-1;apexKeyReceipt=null;
            apexKeyMessage="Keyboard navigation paused: "+keyboardError.message;
            if(apexKeyFocus!=null) apexKeyFocus.visible=false;
         }
      }

      private function ApexCatalogKeyboardCommand(value:String) : void
      {
         var codes:Object={left:37,up:38,right:39,down:40,home:36,end:35,pageup:33,pagedown:34};
         if(!codes.hasOwnProperty(value)) throw new Error("Choose an explicit catalog navigation key");
         if(apexKeyQueue!=null && apexKeyQueue.length>0) throw new Error("Keyboard navigation is already pending");
         var panel:Object=mCurrentPanel;
         if(panel==null || !panel.visible || panel.mcTileList==null || panel.mcTileList.mGridLayout==null)
            throw new Error("No visible native card catalog");
         apexKeyReceipt=null;
         apexKeyQueue=[{key:int(codes[value]),sim:apexBoundSim,owner:apexFormsSelectedId,
            panel:panel,state:mCurrState,feed:panel.mcTileList.mGridLayout.GetDataFeed(),route:"semantic-navigation"}];
         apexKeyIntent=int(codes[value]);ApexCatalogKeyboardFrame(true);
         if(apexKeyReceipt==null || int(apexKeyReceipt.key)!=int(codes[value]))
            throw new Error(apexKeyMessage=="" ? "Native catalog navigation was not applied" : apexKeyMessage);
      }
      private function ApexCatalogKeyboardTyping() : Boolean
      {
         return stage!=null && stage.focus is flash.text.TextField && flash.text.TextField(stage.focus).type=="input";
      }

      private function ApexCatalogKeyboardInput(value:String) : void
      {
         var fields:Array=value.split(",");
         if(fields.length!=2 || (fields[1]!="0" && fields[1]!="1")) throw new Error("Explicit catalog focus choice required");
         value=String(fields[0]);
         if(Boolean(CommunicationManager.CallUIService("IsUILoadingScreenVisible")) ||
            Boolean(CommunicationManager.CallUIService("IsModalVisible")) || Boolean(CommunicationManager.CallUIService("IsDialogModalVisible")))
            throw new Error("A loading screen or modal owns keyboard input");
         if(fields[1]=="1") {
            var panel:Object=mCurrentPanel;
            if(stage==null || panel==null || !panel.visible || panel.mcTileList==null || !panel.mcTileList.visible)
               throw new Error("No visible catalog can receive keyboard focus");
            var focus:flash.display.InteractiveObject=panel.mcTileList.GetGridView() as flash.display.InteractiveObject;
            if(focus==null || focus.stage!==stage) throw new Error("The catalog focus target is detached");
            stage.focus=focus;
            if(stage.focus!==focus) throw new Error("The native catalog did not accept UI focus");
         }
         var codes:Object={left:37,up:38,right:39,down:40,home:36,end:35,pageup:33,pagedown:34,enter:13};
         if(!codes.hasOwnProperty(value) || stage==null) throw new Error("Choose an available catalog input key");
         if(apexKeyQueue!=null && apexKeyQueue.length>0) throw new Error("Earlier keyboard input is pending");
         ApexCatalogKeyboardInitialize();apexKeyReceipt=null;apexKeyInjecting=true;
         try {
            // Invoke the exact Stage listener with a typed keyboard event.
            // Scaleform does not reliably bubble synthetic events from its
            // movie root. Preserve the listener's text/modal/context checks.
            var event:flash.events.KeyboardEvent=new flash.events.KeyboardEvent(flash.events.KeyboardEvent.KEY_DOWN,true,true);
            event.keyCode=int(codes[value]);event.charCode=0;
            ApexCatalogKeyDown(event);
            ApexCatalogKeyboardFrame(true);
         } finally {apexKeyInjecting=false;}
         if(apexKeyReceipt==null || int(apexKeyReceipt.key)!=int(codes[value]) ||
            apexKeyReceipt.source_route!="shared-keyboard-handler")
            throw new Error("CAS key not consumed: "+apexKeyRejected+" / code "+apexKeyLastCode+" / "+apexKeyMessage);
      }
      private function ApexCatalogKeyboardVisibility() : Object
      {
         var panel:Object=mCurrentPanel;
         var list:Object=panel==null ? null : panel.mcTileList;
         var grid:Object=list==null ? null : list.mGridLayout;
         if(apexKeyIndex<0 || grid==null || list.mScrollerView==null) return {available:false};
         var cell:flash.display.DisplayObject=grid.GetViewAtIndex(apexKeyIndex) as flash.display.DisplayObject;
         if(cell==null || cell.stage==null) return {available:false};
         var rect:flash.geom.Rectangle=cell.getBounds(list.mScrollerView);rect.inflate(-2,-2);
         var viewport:flash.geom.Rectangle=list.mScrollerView.GetScrollingRegion().clone();viewport.inflate(0.5,0.5);
         return {available:true,fully_visible:viewport.containsRect(rect),focus_visible:apexKeyFocus!=null && apexKeyFocus.visible,
            cell:{x:rect.x,y:rect.y,width:rect.width,height:rect.height},
            viewport:{x:viewport.x,y:viewport.y,width:viewport.width,height:viewport.height}};
      }
