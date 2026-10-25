      private var apexCatalogPrefs:Object;
      private var apexCatalogStore:Object;
      private var apexCatalogUi:flash.display.Sprite;
      private var apexCatalogRows:flash.display.Sprite;
      private var apexCatalogIntent:Object;
      private var apexCatalogSignature:String = "";
      private var apexCatalogStyleSignature:String = "";
      private var apexCatalogLayoutChanges:int = 0;
      private var apexCatalogRefreshRegistered:Boolean = false;
      private var apexCatalogDirty:Boolean = false;
      private var apexCatalogSlot:Object;
      private var apexCatalogBinding:Object;
      private var apexCatalogBindingRegistered:Boolean = false;
      private var apexCatalogBindingDirty:Boolean = false;
      private var apexCatalogBoundWidth:Number = -1;
      private var apexCatalogHeaderSignature:String = "";
      private var apexCatalogEffects:Array;
      private var apexCatalogPage:int = 0;
      private var apexCatalogItems:Array;
      private var apexCatalogContext:String = "";
      private var apexCatalogError:String = "";
      private var apexCatalogRegistered:Boolean = false;
      private var apexCatalogDrag:String = "";
      private var apexCatalogSaved:Boolean = false;
      private var apexCatalogTab:String = "items";
      private var apexCatalogSelectionFrames:int = 0;
      private var apexCatalogSelectionMaxMs:int = 0;
      private var apexCatalogSelectionOverBudget:int = 0;

      private function ApexCatalogInitialize() : void
      {
         apexCatalogPrefs={columns:6,color:0x00c9eb,glow:0,animation:"none",strength:1,period:1.4,border:3};
         apexCatalogEffects=[];apexCatalogItems=[];
         apexCardPrefs={scale:1,gap_x:4,gap_y:4};apexCardGeometry=null;apexCardLayout=null;
         apexCatalogSaved=false;apexCatalogLayoutChanges=0;apexCatalogStyleSignature="";
         apexCatalogDirty=false;apexCatalogSlot=null;
         apexCatalogBinding=null;apexCatalogBindingDirty=false;apexCatalogBoundWidth=-1;apexCatalogHeaderSignature="";
         apexCatalogTab="items";
         apexCatalogSelectionFrames=0;apexCatalogSelectionMaxMs=0;apexCatalogSelectionOverBudget=0;
         ApexEquippedInitialize();
         ApexCatalogKeyboardInitialize();
         ApexSearchInitialize();
         ApexCompanionInitialize();
         ApexPanelsInitialize();
         ApexColumnsInitialize();
         try {
            apexCatalogStore=flash.net.SharedObject.getLocal("TD1ApexCASCatalog");
            if(apexCatalogStore!=null && (apexCatalogStore.data.version===1 || apexCatalogStore.data.version===2))
               { ApexCatalogValidate(apexCatalogStore.data.preferences);
                 if(apexCatalogStore.data.version===2) ApexCardValidate(apexCatalogStore.data.cards);apexCatalogSaved=true; }
         } catch(storageError:Error) { apexCatalogStore=null; }
         if(!apexCatalogRegistered)
            apexCatalogRegistered=RegisterServiceHandler("ApexOpenEquippedCatalog",ApexCatalogOpen);
         if(!apexCatalogRefreshRegistered)
            apexCatalogRefreshRegistered=AddMessageListener("CASRefreshActiveCatalog",ApexCatalogInvalidate);
         // CommunicationObject keeps multiple functions per widget/event.
         // Retain EA's original alignment callback and observe its primitives.
         if(!apexCatalogBindingRegistered)
            apexCatalogBindingRegistered=AddMessageListener("CASBindingSimContextMenu",ApexCatalogObserveBinding);
         addEventListener(flash.events.Event.ENTER_FRAME,ApexCatalogFrame,false,0,true);
      }

      private function ApexCatalogValidate(p:Object) : void
      {
         if(p==null || !isFinite(Number(p.columns)) || int(p.columns)!=Number(p.columns) || int(p.columns)<2 || int(p.columns)>32 ||
            !isFinite(Number(p.color)) || Number(p.color)!=uint(p.color) || uint(p.color)>0xffffff ||
            !isFinite(Number(p.glow)) || Number(p.glow)<0 || Number(p.glow)>12 ||
            !isFinite(Number(p.border)) || Number(p.border)<1 || Number(p.border)>8 ||
            !isFinite(Number(p.strength)) || Number(p.strength)<0.25 || Number(p.strength)>1 ||
            !isFinite(Number(p.period)) || Number(p.period)<0.8 || Number(p.period)>4 ||
            (p.animation!="none" && p.animation!="pulse" && p.animation!="flash"))
            throw new Error("Invalid bounded CAS catalog preferences");
         apexCatalogPrefs={columns:int(p.columns),color:uint(p.color),glow:Number(p.glow),animation:String(p.animation),
            strength:Number(p.strength),period:Number(p.period),border:Number(p.border)};
         apexCatalogSaved=false;
      }

      private function ApexCatalogPersist() : void
      {
         if(apexCatalogStore==null) return;
         try {
            apexCatalogStore.data.version=2;apexCatalogStore.data.preferences=apexCatalogPrefs;
            apexCatalogStore.data.cards=apexCardPrefs;
            apexCatalogSaved=String(apexCatalogStore.flush())=="flushed";
         } catch(storageError:Error) { apexCatalogSaved=false; }
      }

      private function ApexCatalogStyle(value:String) : void
      {
         var p:Array=value.split(",");
         if(p.length!=7) throw new Error("Complete typed CAS catalog preferences required");
         ApexCatalogValidate({columns:Number(p[0]),color:Number(p[1]),glow:Number(p[2]),strength:Number(p[3]),
            period:Number(p[4]),border:Number(p[5]),animation:String(p[6])});
         ApexCatalogPersist();
         if(apexCatalogUi!=null && apexCatalogUi.visible) ApexCatalogDraw();
      }

      private function ApexCatalogView(view:String) : void
      {
         if(view=="category") {ApexEquippedOpen();return;}
         if(view!="items" && view!="style" && view!="layout" && view!="closed") throw new Error("Invalid catalog tab");
         if(view=="closed") {if(apexCatalogUi!=null) apexCatalogUi.visible=false;return;}
         if(apexCatalogUi==null || apexCatalogContext=="" || mCurrSimInfo==null ||
            apexCatalogContext!=String(mCurrSimInfo.simId)+"|"+apexFormsSelectedId) ApexCatalogReadEquipped();
         apexCatalogTab=view;ApexCatalogDraw();
      }

      private function ApexCatalogSliderCommand(value:String) : void
      {
         var parts:Array=value.split(",");
         if(parts.length!=2 || ["columns","red","green","blue","glow","border","period","strength","card_scale","gap_x","gap_y"].indexOf(parts[0])<0 ||
            !isFinite(Number(parts[1])) || Number(parts[1])<0 || Number(parts[1])>1 || apexCatalogDrag!="")
            throw new Error("Use an exact idle catalog slider and bounded fraction");
         ApexCatalogView(["card_scale","gap_x","gap_y"].indexOf(parts[0])>=0 ? "layout" : "style");apexCatalogDrag=String(parts[0]);
         try {ApexCatalogSlide(null,Number(parts[1]));} finally {apexCatalogDrag="";}
         ApexCatalogPersist();ApexCatalogDraw();
      }

      private function ApexCatalogDispose(preserveGridBootstrap:Boolean=false) : void
      {
         ApexCatalogTraceDispose();ApexLayoutTraceDispose();
         if(!preserveGridBootstrap)ApexCatalogGridDispose();
         ApexPanelsDispose();
         ApexColumnsDispose();
         ApexEquippedDispose();
         ApexCatalogKeyboardDispose();
         ApexCompanionDispose();
         ApexSearchDispose();
         removeEventListener(flash.events.Event.ENTER_FRAME,ApexCatalogFrame);
         if(stage!=null) {
            stage.removeEventListener(flash.events.MouseEvent.MOUSE_MOVE,ApexCatalogSlide);
            stage.removeEventListener(flash.events.MouseEvent.MOUSE_UP,ApexCatalogSlideEnd);
         }
         if(apexCatalogRegistered) UnregisterServiceHandler("ApexOpenEquippedCatalog",ApexCatalogOpen);
         if(apexCatalogRefreshRegistered) RemoveMessageListener("CASRefreshActiveCatalog",ApexCatalogInvalidate);
         if(apexCatalogBindingRegistered) RemoveMessageListener("CASBindingSimContextMenu",ApexCatalogObserveBinding);
         apexCatalogRegistered=false;
         apexCatalogBindingRegistered=false;apexCatalogBinding=null;apexCatalogBoundWidth=-1;apexCatalogHeaderSignature="";
         apexCatalogRefreshRegistered=false;apexCatalogDirty=false;apexCatalogSlot=null;
         ApexCatalogClearEffects();ApexCardForget();
         if(apexCatalogUi!=null && apexCatalogUi.parent!=null) apexCatalogUi.parent.removeChild(apexCatalogUi);
         apexCatalogUi=null;apexCatalogRows=null;apexCatalogItems=[];apexCatalogIntent=null;apexCatalogStore=null;
         apexCatalogContext="";apexCatalogSignature="";apexCatalogStyleSignature="";apexCatalogDrag="";apexCatalogTab="items";
      }

      private function ApexCatalogOpen(value:Object=null) : Object
      {
         // The native radial button only queues. No game calls in its click.
         var started:int=flash.utils.getTimer();
         apexCatalogIntent={operation:"open"};ApexInputTiming(started);return {protocol:1,queued:true};
      }

      private function ApexCatalogInvalidate(value:Object=null) : void
      {
         // Outfit/part changes only mark the list dirty; read it on a later
         // idle frame if visible, with no background scan when it is closed.
         apexCatalogDirty=true;
         apexEquippedDirty=true;
      }

      private function ApexCatalogObserveBinding(value:Object) : void
      {
         if(value==null || typeof value.view_x_offset!="number" || typeof value.screen_x_offset!="number" ||
            typeof value.screen_x_max!="number" || !isFinite(value.view_x_offset) ||
            !isFinite(value.screen_x_offset) || !isFinite(value.screen_x_max)) return;
         apexCatalogBinding={view:Number(value.view_x_offset),screen:Number(value.screen_x_offset),maximum:Number(value.screen_x_max)};
         apexCatalogBindingDirty=true;
      }

      private function ApexCatalogApplyBinding(width:Number) : void
      {
         if(apexCatalogBinding==null || stage==null) return;
         if(apexCatalogBindingDirty || width!=apexCatalogBoundWidth) {
            // Correct the native container's right-edge clamp, not a child's
            // x coordinate. EA's view/screen attachment and min clamp survive.
            BindDisplayObjectToSim(this.mLayerPanels,apexCatalogBinding.view,
               apexCatalogBinding.screen+CASCustomizerTunables.PANEL_SCREEN_OFFSET_X,
               Math.max(apexCatalogBinding.maximum,width+12));
            apexCatalogBoundWidth=width;apexCatalogBindingDirty=false;
         }
         var header:String=String(mCurrState)+":"+width;
         if(mCurrentPanel is ClothingPanel && mCurrentPanel.visible &&
            !CASConfiguration.IsFashionMode && MenuState.SupportsPlanOutfit(mCurrState) && header!=apexCatalogHeaderSignature) {
            apexCatalogHeaderSignature=header;
            CommunicationManager.SendUIMessage("CASSetPlanOutfitVisible",{visible:true,width:width,skipAnim:true,
               apex_view_x_offset:apexCatalogBinding.view,apex_screen_x_offset:apexCatalogBinding.screen,
               apex_screen_x_max:apexCatalogBinding.maximum});
         }
      }

      private function ApexCatalogFrame(event:flash.events.Event=null) : void
      {
         if(apexCatalogPrefs==null || stage==null || apexDisconnected) return;
         var frameStarted:int=flash.utils.getTimer();
         apexCatalogFrameCells=null;
         try {
         ApexPanelsFrame();
         var panel:Object=this.mCurrentPanel;
         if(panel!=null && panel.visible && panel.mcTileList!=null && panel.mcTileList.mGridLayout!=null && panel is ClothingPanel) {
            var grid:Object=panel.mcTileList.mGridLayout;
            var layoutStarted:int=flash.utils.getTimer();
            var width:Number=ApexCardApply(panel,grid);
            apexCatalogFrameTiming.layout_max_ms=Math.max(apexCatalogFrameTiming.layout_max_ms,flash.utils.getTimer()-layoutStarted);
            var bindingStarted:int=flash.utils.getTimer();
            ApexCatalogApplyBinding(width);
            apexCatalogFrameTiming.binding_max_ms=Math.max(apexCatalogFrameTiming.binding_max_ms,flash.utils.getTimer()-bindingStarted);
            var styleSignature:String=apexCatalogPrefs.color+":"+apexCatalogPrefs.glow+":"+apexCatalogPrefs.border;
            if(styleSignature!=apexCatalogStyleSignature) {
               ApexCatalogClearEffects();apexCatalogStyleSignature=styleSignature;
            }
            if(!ApexCatalogGridPending(grid))ApexCatalogSelection(grid);
         } else {
            if(apexCatalogEffects!=null && apexCatalogEffects.length>0) ApexCatalogClearEffects();
            // The hidden clothing panel retains its fitted recycled pool.
            // Restoring it to two columns here rebuilt every card when the
            // player returned from Body to Tattoos, then fitted it again.
            // Restore only on disposal, replacement grid, or a display fault.
            ApexCatalogApplyBinding(262);apexCatalogHeaderSignature="";
         }
         ApexColumnsFrame();
         if(apexCatalogUi!=null && apexCatalogUi.visible) {
            if(apexCatalogContext!="" && mCurrSimInfo!=null &&
               apexCatalogContext!=String(mCurrSimInfo.simId)+"|"+apexFormsSelectedId) {
               apexCatalogItems=[];apexCatalogContext="";apexCatalogError="Sim or form changed. Refresh equipped items.";ApexCatalogDraw();
            }
            if(apexCatalogDirty && apexPendingFields==null && !apexReceiving) {
               apexCatalogDirty=false;
               try {ApexCatalogReadEquipped();ApexCatalogDraw();}
               catch(refreshError:Error) {apexCatalogError=refreshError.message;}
            }
            // Keep layout controls away from the native thumbnail catalog so
            // size/spacing changes can be previewed while dragging a slider.
            var catalogX:Number=apexCatalogTab=="items" ? Math.max(12,stage.stageWidth-apexCatalogUi.width-20) : 12;
            if(apexCatalogUi.x!=catalogX)apexCatalogUi.x=catalogX;
            if(apexCatalogUi.y!=75)apexCatalogUi.y=75;
         }
         if(apexCatalogIntent!=null && apexPendingFields==null && !apexReceiving) {
            var intent:Object=apexCatalogIntent;apexCatalogIntent=null;
            try {
               if(intent.operation=="open") ApexEquippedOpen();
               else if(intent.operation=="navigate") {
                  if(String(mCurrSimInfo.simId)!=intent.sim_id || apexFormsSelectedId!=intent.owner_id)
                     throw new Error("The Sim or form changed; refresh equipped items");
                  var target:int=int(intent.state);
                  apexEquippedActive=false;apexEquippedInteraction=null;
                  apexEquippedRetirePending=true;
                  if(apexCatalogUi!=null) apexCatalogUi.visible=false;
                  HandleContextMenuSetMenuState({menuState:target,skipAnim:true,setZoomState:true});
                  CommunicationManager.SendUIMessage("CASChangeMenuState",target);
               }
            } catch(catalogError:Error) {apexCatalogError=catalogError.message;ApexCatalogDraw();}
         }
         if(apexPendingFields==null && !apexReceiving) {ApexEquippedFrame();ApexSearchFrame();ApexCompanionFrame();ApexCatalogKeyboardFrame();}
         } catch(frameError:Error) {
            apexCatalogError="Catalog display paused: "+frameError.message;
            if(apexCatalogGrid!=null) {
               apexCatalogGrid.error=apexCatalogError;ApexCatalogGridInvalidate("error-abandon");
            }
            removeEventListener(flash.events.Event.ENTER_FRAME,ApexCatalogFrame);
            ApexCatalogClearEffects();ApexCardRestore();
         }
         var frameElapsed:int=flash.utils.getTimer()-frameStarted;
         if(apexCatalogFrameTiming.samples<int.MAX_VALUE) apexCatalogFrameTiming.samples++;
         apexCatalogFrameTiming.total_ms+=frameElapsed;
         apexCatalogFrameTiming.max_ms=Math.max(apexCatalogFrameTiming.max_ms,frameElapsed);
         if(frameElapsed>1 && apexCatalogFrameTiming.over_1ms<int.MAX_VALUE) apexCatalogFrameTiming.over_1ms++;
         apexCatalogFrameCells=null;
      }

      private function ApexCatalogClearEffects() : void
      {
         if(apexCatalogEffects==null) return;
         for each(var row:Object in apexCatalogEffects)
            { if(row.effect.parent!=null) row.effect.parent.removeChild(row.effect);
              if(row.frame!=null) row.frame.transform.colorTransform=row.transform; }
         apexCatalogEffects=[];
      }

      private function ApexCatalogSelection(grid:Object) : void
      {
         var started:int=flash.utils.getTimer();
         // Only EA's recycled visible cells are inspected. No catalog scan,
         // game query, thumbnail export or per-Sim appearance copy is needed.
         var cells:Object=ApexCatalogCells(grid);var kept:Array=[];
         for each(var cell:Object in cells) {
            if(cell==null || !cell.visible || !cell.Selected) continue;
            var effect:flash.display.Sprite=cell.getChildByName("apexSelectedBorder") as flash.display.Sprite;
            var retained:Object=null;
            for each(var previous:Object in apexCatalogEffects) if(previous.cell===cell) {retained=previous;break;}
            if(effect==null) {
               effect=new flash.display.Sprite();effect.name="apexSelectedBorder";effect.mouseEnabled=false;effect.mouseChildren=false;
               // Native getBounds() is the input hit area, including spacing
               // outside the thumbnail. Keep every stroke inside its mask.
               var visual:flash.display.DisplayObject=cell.mcIconAndMask!=null ? cell.mcIconAndMask : cell.mcImage;
               var bounds:flash.geom.Rectangle=visual!=null ? visual.getBounds(cell) : cell.getBounds(cell);
               var stroke:Number=Number(apexCatalogPrefs.border);
               var inset:Number=stroke*0.5+1;
               effect.graphics.lineStyle(stroke,uint(apexCatalogPrefs.color),1,true);
               // GFx's stroked drawRoundRect loses the right edge here.
               // Emit every edge and rounded corner, including path closure.
               var left:Number=bounds.x+inset;var top:Number=bounds.y+inset;
               var right:Number=left+Math.max(2,bounds.width-inset*2);
               var bottom:Number=top+Math.max(2,bounds.height-inset*2);
               var radius:Number=Math.min(4.5,(right-left)*0.5,(bottom-top)*0.5);
               effect.graphics.moveTo(left+radius,top);
               effect.graphics.lineTo(right-radius,top);
               effect.graphics.curveTo(right,top,right,top+radius);
               effect.graphics.lineTo(right,bottom-radius);
               effect.graphics.curveTo(right,bottom,right-radius,bottom);
               effect.graphics.lineTo(left+radius,bottom);
               effect.graphics.curveTo(left,bottom,left,bottom-radius);
               effect.graphics.lineTo(left,top+radius);
               effect.graphics.curveTo(left,top,left+radius,top);
               if(Number(apexCatalogPrefs.glow)>0) effect.filters=[new flash.filters.GlowFilter(uint(apexCatalogPrefs.color),0.9,
                  Number(apexCatalogPrefs.glow),Number(apexCatalogPrefs.glow),1.5,1)];
               cell.addChild(effect);
               if(retained==null) retained={cell:cell,effect:effect,frame:cell.mcBottomFrame,transform:null};
               else retained.effect=effect;
               if(retained.frame!=null && retained.transform==null) {
                  retained.transform=retained.frame.transform.colorTransform;
                  var rgb:uint=uint(apexCatalogPrefs.color);
                  retained.frame.transform.colorTransform=new flash.geom.ColorTransform(0,0,0,1,(rgb>>16)&255,(rgb>>8)&255,rgb&255,0);
               }
            }
            var phase:Number=(flash.utils.getTimer()%(Number(apexCatalogPrefs.period)*1000))/(Number(apexCatalogPrefs.period)*1000);
            var alpha:Number=Number(apexCatalogPrefs.strength);
            if(apexCatalogPrefs.animation=="pulse") alpha*=0.4+0.6*(0.5-0.5*Math.cos(phase*Math.PI*2));
            else if(apexCatalogPrefs.animation=="flash") alpha*=phase<0.5 ? 1 : 0.25;
            if(effect.alpha!=alpha)effect.alpha=alpha;
            if(retained==null) retained={cell:cell,effect:effect,frame:null,transform:null};
            kept.push(retained);
         }
         for each(var old:Object in apexCatalogEffects) {
            var retain:Boolean=false;
            for each(var current:Object in kept) if(current.effect===old.effect) {retain=true;break;}
            if(!retain) {if(old.effect.parent!=null) old.effect.parent.removeChild(old.effect);
               if(old.frame!=null) old.frame.transform.colorTransform=old.transform;}
         }
         apexCatalogEffects=kept;
         var elapsed:int=flash.utils.getTimer()-started;
         if(apexCatalogSelectionFrames<int.MAX_VALUE) apexCatalogSelectionFrames++;
         apexCatalogSelectionMaxMs=Math.max(apexCatalogSelectionMaxMs,elapsed);
         if(elapsed>1 && apexCatalogSelectionOverBudget<int.MAX_VALUE) apexCatalogSelectionOverBudget++;
      }

      private function ApexCatalogReadEquipped() : void
      {
         if(mCurrSimInfo==null || apexNativeChannel=="" || apexFormsSelectedId=="") throw new Error("No exact active CAS form");
         var slot:Object=ApexClone(CommunicationManager.CallGameService("CasGetCurrSimOutfitSlot"));
         if(slot==null || !(slot.outfit_type is int) || !(slot.outfit_index is int)) throw new Error("Current outfit is unavailable");
         var response:String=ApexNativeExchange("EQUIPPED|"+apexNativeChannel+"|"+slot.outfit_type+"|"+slot.outfit_index);
         var lines:Array=response.split("\n");var header:Array=String(lines.shift()).split("|");
         if(header.length!=6 || header[0]!="EQUIPPED" || header[1]!=String(mCurrSimInfo.simId) || header[2]!=apexFormsSelectedId ||
            int(header[3])!=slot.outfit_type || int(header[4])!=slot.outfit_index || lines.length>256)
            throw new Error("Equipped items do not belong to this exact Sim, form and outfit");
         var names:Object={};var definition:XML=flash.utils.describeType(CASBodyType);
         for each(var constant:XML in definition.constant) names[int(CASBodyType[String(constant.@name)])]=String(constant.@name).replace(/_/g," ");
         var rows:Array=[];
         for each(var line:String in lines) {
            var fields:Array=line.split("|");
            if(fields.length!=4 || !/^0x[0-9a-f]{16}$/.test(fields[0]) || !/^[0-9]+$/.test(fields[1]))
               throw new Error("Invalid equipped item identity");
            var body:int=int(fields[1]);var state:int=ApexCatalogMenu(body);
            rows.push({part_key:fields[0],body_type:body,color:fields[2],layer:fields[3],
               label:(names[body] || "Body type "+body)+(int(fields[3])>0 ? " / layer "+fields[3] : ""),menu_state:state});
         }
         apexCatalogItems=rows;apexCatalogPage=0;apexCatalogError="";
         apexCatalogSlot={category:int(slot.outfit_type),index:int(slot.outfit_index)};apexCatalogDirty=false;
         apexCatalogContext=String(mCurrSimInfo.simId)+"|"+apexFormsSelectedId;
      }

      private function ApexCatalogMenu(body:int) : int
      {
         var menus:Object=__APEX_EQUIPPED_MENUS__;
         return menus.hasOwnProperty(String(body)) ? int(menus[String(body)]) : 0;
      }

      private function ApexCatalogButton(parent:flash.display.Sprite,name:String,text:String,x:Number,y:Number,width:Number=92) : void
      {
         var button:flash.display.Sprite=new flash.display.Sprite();button.name=name;button.x=x;button.y=y;
         button.graphics.lineStyle(1,0xadcfe5);button.graphics.beginFill(0xffffff);button.graphics.drawRoundRect(0,0,width,27,8,8);button.graphics.endFill();
         button.buttonMode=true;button.mouseChildren=false;parent.addChild(button);
         ApexFormsText(button,text,7,4,width-10,11,0x275273);
      }

      private function ApexCatalogSlider(parent:flash.display.Sprite,name:String,label:String,value:Number,low:Number,high:Number,y:Number) : void
      {
         var caption:flash.text.TextField=ApexFormsText(parent,label,15,y,300,11,0x275273);caption.name="label_"+name;
         var track:flash.display.Sprite=new flash.display.Sprite();track.name="slider_"+name;track.y=y+20;track.x=15;
         track.graphics.beginFill(0xb8d7e8);track.graphics.drawRoundRect(0,-3,300,12,8,8);track.graphics.endFill();
         var thumb:flash.display.Sprite=new flash.display.Sprite();thumb.name="thumb";thumb.x=300*(value-low)/(high-low);thumb.y=3;
         thumb.mouseEnabled=false;thumb.graphics.beginFill(uint(apexCatalogPrefs.color));thumb.graphics.drawCircle(0,0,7);thumb.graphics.endFill();track.addChild(thumb);
         track.buttonMode=true;parent.addChild(track);
      }

      private function ApexCatalogDraw() : void
      {
         if(apexCatalogUi!=null && apexCatalogUi.parent!=null) apexCatalogUi.parent.removeChild(apexCatalogUi);
         apexCatalogUi=new flash.display.Sprite();apexCatalogUi.name="ApexEquippedCatalog";addChild(apexCatalogUi);
         apexCatalogUi.graphics.lineStyle(2,0xffffff);apexCatalogUi.graphics.beginFill(0xeef8ff,0.99);apexCatalogUi.graphics.drawRoundRect(0,0,350,620,16,16);apexCatalogUi.graphics.endFill();
         ApexFormsText(apexCatalogUi,"All equipped CAS items",15,12,280,17,0x235a80);
         ApexCatalogButton(apexCatalogUi,"close","Close",270,10,64);
         ApexCatalogButton(apexCatalogUi,"tab_items","Text list",15,46,100);
         ApexCatalogButton(apexCatalogUi,"tab_layout","Card layout",125,46,100);
         ApexCatalogButton(apexCatalogUi,"tab_style","Selection",235,46,100);
         if(apexCatalogTab=="style") {
         ApexCatalogSlider(apexCatalogUi,"columns","Columns: "+apexCatalogPrefs.columns+" (cards fit this count)",apexCatalogPrefs.columns,2,32,86);
         var c:uint=uint(apexCatalogPrefs.color);
         ApexCatalogSlider(apexCatalogUi,"red","Selection red: "+((c>>16)&255),(c>>16)&255,0,255,133);
         ApexCatalogSlider(apexCatalogUi,"green","Selection green: "+((c>>8)&255),(c>>8)&255,0,255,177);
         ApexCatalogSlider(apexCatalogUi,"blue","Selection blue: "+(c&255),c&255,0,255,221);
         ApexCatalogSlider(apexCatalogUi,"glow","Glow: "+Number(apexCatalogPrefs.glow).toFixed(1),apexCatalogPrefs.glow,0,12,265);
         ApexCatalogSlider(apexCatalogUi,"border","Border: "+Number(apexCatalogPrefs.border).toFixed(1),apexCatalogPrefs.border,1,8,309);
         ApexCatalogButton(apexCatalogUi,"none","Static",15,355);
         ApexCatalogButton(apexCatalogUi,"pulse","Pulse",120,355);
         ApexCatalogButton(apexCatalogUi,"flash","Flash",225,355);
         ApexCatalogSlider(apexCatalogUi,"period","Animation period: "+Number(apexCatalogPrefs.period).toFixed(1)+" seconds",apexCatalogPrefs.period,0.8,4,401);
         ApexCatalogSlider(apexCatalogUi,"strength","Border opacity: "+Number(apexCatalogPrefs.strength).toFixed(2),apexCatalogPrefs.strength,0.25,1,448);
         ApexFormsText(apexCatalogUi,"Effect: "+apexCatalogPrefs.animation+" / "+(apexCatalogSaved ? "Saved" : "Session settings"),15,501,320,11,0x47708b);
         } else if(apexCatalogTab=="layout") {
         ApexCatalogSlider(apexCatalogUi,"columns","Columns: "+apexCatalogPrefs.columns+" (cards fit this count)",apexCatalogPrefs.columns,2,32,86);
         ApexCatalogSlider(apexCatalogUi,"card_scale","Card size: "+Math.round(apexCardPrefs.scale*100)+"%",apexCardPrefs.scale,0.2,1.6,145);
         ApexCatalogSlider(apexCatalogUi,"gap_x","Horizontal spacing: "+Number(apexCardPrefs.gap_x).toFixed(1),apexCardPrefs.gap_x,0,32,204);
         ApexCatalogSlider(apexCatalogUi,"gap_y","Vertical spacing: "+Number(apexCardPrefs.gap_y).toFixed(1),apexCardPrefs.gap_y,0,32,263);
         ApexCatalogButton(apexCatalogUi,"reset_cards","Reset EA card size / spacing",15,329,320);
         var cardHelp:flash.text.TextField=ApexFormsText(apexCatalogUi,"20-160% cards / 2-32 columns. Cards fit the chosen count. Swatches open at full size.",15,380,320,11,0x47708b);
         cardHelp.wordWrap=true;cardHelp.height=64;
         } else {
         ApexCatalogButton(apexCatalogUi,"category","Thumbnails",15,86,110);
         ApexCatalogButton(apexCatalogUi,"refresh","Refresh",130,86,95);
         ApexCatalogButton(apexCatalogUi,"previous","<",235,86,43);ApexCatalogButton(apexCatalogUi,"next",">",290,86,43);
         var start:int=apexCatalogPage*12;var finish:int=Math.min(start+12,apexCatalogItems.length);
         for(var i:int=start;i<finish;i++) {
            var row:Object=apexCatalogItems[i];
            ApexCatalogButton(apexCatalogUi,"item_"+i,String(row.label)+"  /  "+String(row.part_key),15,126+(i-start)*36,320);
         }
         }
         ApexFormsText(apexCatalogUi,apexCatalogError!="" ? apexCatalogError : apexCatalogItems.length+" equipped parts / click a row to edit its category",15,586,320,11,apexCatalogError!="" ? 0xa62b2b : 0x47708b);
         apexCatalogUi.addEventListener(flash.events.MouseEvent.CLICK,ApexCatalogClick,false,0,true);
         apexCatalogUi.addEventListener(flash.events.MouseEvent.MOUSE_DOWN,ApexCatalogSlideStart,false,0,true);
      }

      private function ApexCatalogClick(event:flash.events.MouseEvent) : void
      {
         var name:String=event.target.name;
         if(name=="close") apexCatalogUi.visible=false;
         else if(name=="category") apexCatalogIntent={operation:"open"};
         else if(name=="tab_items" || name=="tab_style" || name=="tab_layout") {apexCatalogTab=name.substr(4);ApexCatalogDraw();}
         else if(name=="reset_cards") ApexCardReset();
         else if(name=="refresh") apexCatalogIntent={operation:"open"};
         else if(name=="previous" || name=="next") {
            apexCatalogPage=Math.max(0,Math.min(Math.max(0,int((apexCatalogItems.length-1)/12)),apexCatalogPage+(name=="next" ? 1 : -1)));ApexCatalogDraw();
         } else if(name=="none" || name=="pulse" || name=="flash") {
            apexCatalogPrefs.animation=name;ApexCatalogPersist();ApexCatalogDraw();
         } else if(name.indexOf("item_")==0) {
            var row:Object=apexCatalogItems[int(name.substr(5))];var parts:Array=apexCatalogContext.split("|");
            if(row!=null && int(row.menu_state)!=0) apexCatalogIntent={operation:"navigate",sim_id:parts[0],owner_id:parts[1],state:row.menu_state};
         }
         event.stopPropagation();
      }

      private function ApexCatalogSlideStart(event:flash.events.MouseEvent) : void
      {
         var name:String=event.target.name;
         if(name.indexOf("slider_")!=0 || stage==null) return;
         apexCatalogDrag=name.substr(7);ApexCatalogSlide();
         stage.addEventListener(flash.events.MouseEvent.MOUSE_MOVE,ApexCatalogSlide,false,0,true);
         stage.addEventListener(flash.events.MouseEvent.MOUSE_UP,ApexCatalogSlideEnd,false,0,true);
         event.stopPropagation();
      }

      private function ApexCatalogSlide(event:flash.events.MouseEvent=null,fraction:Number=-1) : void
      {
         if(apexCatalogDrag=="" || apexCatalogUi==null) return;
         var started:int=flash.utils.getTimer();
         var ratio:Number=fraction<0 ? Math.max(0,Math.min(1,(apexCatalogUi.mouseX-15)/300)) : fraction;var c:uint=uint(apexCatalogPrefs.color);
         if(apexCatalogDrag=="columns") apexCatalogPrefs.columns=2+Math.round(ratio*30);
         else if(apexCatalogDrag=="card_scale") apexCardPrefs.scale=0.2+ratio*1.4;
         else if(apexCatalogDrag=="gap_x" || apexCatalogDrag=="gap_y") apexCardPrefs[apexCatalogDrag]=ratio*32;
         else if(apexCatalogDrag=="glow") apexCatalogPrefs.glow=ratio*12;
         else if(apexCatalogDrag=="border") apexCatalogPrefs.border=1+ratio*7;
         else if(apexCatalogDrag=="period") apexCatalogPrefs.period=0.8+ratio*3.2;
         else if(apexCatalogDrag=="strength") apexCatalogPrefs.strength=0.25+ratio*0.75;
         else if(apexCatalogDrag=="red") apexCatalogPrefs.color=(c&0xffff)|(Math.round(ratio*255)<<16);
         else if(apexCatalogDrag=="green") apexCatalogPrefs.color=(c&0xff00ff)|(Math.round(ratio*255)<<8);
         else if(apexCatalogDrag=="blue") apexCatalogPrefs.color=(c&0xffff00)|Math.round(ratio*255);
         apexCatalogSaved=false;
         var track:flash.display.Sprite=apexCatalogUi.getChildByName("slider_"+apexCatalogDrag) as flash.display.Sprite;
         if(track!=null) {
            var thumb:flash.display.DisplayObject=track.getChildByName("thumb");
            if(thumb!=null) thumb.x=300*ratio;
         }
         var caption:flash.text.TextField=apexCatalogUi.getChildByName("label_"+apexCatalogDrag) as flash.text.TextField;
         if(caption!=null) {
            c=uint(apexCatalogPrefs.color);
            if(apexCatalogDrag=="columns") caption.text="Columns: "+apexCatalogPrefs.columns+" (cards fit this count)";
            else if(apexCatalogDrag=="card_scale") caption.text="Card size: "+Math.round(apexCardPrefs.scale*100)+"%";
            else if(apexCatalogDrag=="gap_x") caption.text="Horizontal spacing: "+Number(apexCardPrefs.gap_x).toFixed(1);
            else if(apexCatalogDrag=="gap_y") caption.text="Vertical spacing: "+Number(apexCardPrefs.gap_y).toFixed(1);
            else if(apexCatalogDrag=="red") caption.text="Selection red: "+((c>>16)&255);
            else if(apexCatalogDrag=="green") caption.text="Selection green: "+((c>>8)&255);
            else if(apexCatalogDrag=="blue") caption.text="Selection blue: "+(c&255);
            else if(apexCatalogDrag=="glow") caption.text="Glow: "+Number(apexCatalogPrefs.glow).toFixed(1);
            else if(apexCatalogDrag=="border") caption.text="Border: "+Number(apexCatalogPrefs.border).toFixed(1);
            else if(apexCatalogDrag=="period") caption.text="Animation period: "+Number(apexCatalogPrefs.period).toFixed(1)+" seconds";
            else if(apexCatalogDrag=="strength") caption.text="Border opacity: "+Number(apexCatalogPrefs.strength).toFixed(2);
         }
         ApexInputTiming(started);
      }

      private function ApexCatalogSlideEnd(event:flash.events.MouseEvent=null) : void
      {
         if(stage!=null) {
            stage.removeEventListener(flash.events.MouseEvent.MOUSE_MOVE,ApexCatalogSlide);
            stage.removeEventListener(flash.events.MouseEvent.MOUSE_UP,ApexCatalogSlideEnd);
         }
         apexCatalogDrag="";ApexCatalogPersist();ApexCatalogDraw();
      }

      private function ApexCatalogStatus() : Object
      {
         // Explicit diagnostics only. Older/unmodified providers remain valid;
         // no function, widget or communication object leaves this readback.
         var communicationIndex:Object={available:false,appearance_written:false};
         try {
            var communicationClass:Class=flash.utils.getDefinitionByName("olympus.io.CommunicationObject") as Class;
            if(communicationClass!=null && "ApexCommIndexStats" in communicationClass &&
               communicationClass["ApexCommIndexStats"] is Function) {
               communicationIndex=communicationClass["ApexCommIndexStats"]();
               communicationIndex.available=true;
            }
         } catch(unavailableIndex:Error) { }
         var buttonCommunicationIndex:Object={available:false,appearance_written:false};
         try {
            if(mcClothingPanel!=null && mcClothingPanel.mcTileList!=null &&
               mcClothingPanel.mcTileList.mGridLayout!=null) {
               var diagnosticCells:Object=mcClothingPanel.mcTileList.mGridLayout.GetAllDisplayObjectCells();
               for(var diagnosticIndex:int=0;diagnosticIndex<Math.min(8,diagnosticCells.length);diagnosticIndex++) {
                  var diagnosticCell:Object=diagnosticCells[diagnosticIndex];
                  if(diagnosticCell!=null && "ApexCommButtonIndexStats" in diagnosticCell &&
                     diagnosticCell["ApexCommButtonIndexStats"] is Function) {
                     var localCommunication:Object=diagnosticCell["ApexCommButtonIndexStats"]();
                     buttonCommunicationIndex={available:true,button_provider:localCommunication.button_provider,
                        listener_membership:localCommunication.listener_membership,
                        using_mouse_keyboard:(localCommunication.using_mouse_keyboard is Boolean) ? Boolean(localCommunication.using_mouse_keyboard) : null,
                        appearance_written:false};
                     break;
                  }
               }
               diagnosticCell=null;diagnosticCells=null;
            }
         } catch(unavailableButtonIndex:Error) { }
         var layout:Object=null;
         var thumbs:Object={};
         if(apexCatalogUi!=null && (apexCatalogTab=="style" || apexCatalogTab=="layout"))
            for each(var control:String in ["columns","red","green","blue","glow","border","period","strength","card_scale","gap_x","gap_y"]) {
               var track:flash.display.DisplayObjectContainer=apexCatalogUi.getChildByName("slider_"+control) as flash.display.DisplayObjectContainer;
               if(track!=null && track.getChildByName("thumb")!=null) thumbs[control]=track.getChildByName("thumb").x/300;
            }
         if(stage!=null && mCurrentPanel!=null && mCurrentPanel.visible) {
            var bounds:flash.geom.Rectangle=mCurrentPanel.mcPanelBackground.getBounds(stage);
            layout={x:bounds.x,y:bounds.y,width:bounds.width,height:bounds.height,
               local_x:mCurrentPanel.x,stage_width:stage.stageWidth,stage_height:stage.stageHeight};
         }
         return {preferences:apexCatalogPrefs,card_preferences:apexCardPrefs,card_layout:apexCardLayout,card_cells:ApexCardReadback(),grid_metrics:ApexCardGridReadback(),visible:apexCatalogUi!=null && apexCatalogUi.visible,view:apexCatalogTab,items:apexCatalogItems,
            catalog_bounds:layout,binding_observation:apexCatalogBinding,outfit:apexCatalogSlot,inventory_dirty:apexCatalogDirty,
            actual_columns:apexCatalogSignature=="" ? 0 : int(apexCatalogSignature.split(":")[1]),
            layout_changes:apexCatalogLayoutChanges,
            slider_thumbs:thumbs,
            equipped_count:apexCatalogItems==null ? 0 : apexCatalogItems.length,context:apexCatalogContext,
            clothing_grid_item_count:apexCardGeometry==null ? 0 : apexCardGeometry.grid.GetDataFeed().length,
            error:apexCatalogError,persisted:apexCatalogSaved,selection_effect_count:apexCatalogEffects==null ? 0 : apexCatalogEffects.length,
            selection_timing:{samples:apexCatalogSelectionFrames,max_ms:apexCatalogSelectionMaxMs,
               over_1ms:apexCatalogSelectionOverBudget,clock_resolution_ms:1},
            equipped_category:{active:apexEquippedActive,resolved:apexEquippedProducts==null ? 0 : apexEquippedProducts.length,
               published:apexEquippedPublication==null ? 0 : int(apexEquippedPublication.count),
               pending:apexEquippedActive && apexEquippedRefreshPending,unresolved:apexEquippedUnresolved,timing:apexEquippedTiming},
            keyboard:{received:apexKeyReceived,last_code:apexKeyLastCode,rejected:apexKeyRejected,visibility:ApexCatalogKeyboardVisibility(),typing:ApexCatalogKeyboardTyping(),focused_name:stage==null || stage.focus==null ? "" : String(stage.focus.name),index:apexKeyIndex,context:apexKeyContext,pending:apexKeyIntent,queued:apexKeyQueue==null ? 0 : apexKeyQueue.length,receipt:ApexClone(apexKeyReceipt),message:apexKeyMessage},
            search:ApexSearchStatus(),companion:ApexCompanionStatus(),panels:ApexPanelsStatus(),native_catalog_timing:apexCatalogPerformance,owned_frame_timing:apexCatalogFrameTiming,draw_trace:ApexCatalogTraceStatus(),layout_trace:ApexLayoutTraceStatus(),incremental_grid:ApexCatalogGridStatus(),listener_membership:communicationIndex,button_listener_membership:buttonCommunicationIndex};
      }
