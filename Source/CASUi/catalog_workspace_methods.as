      private var apexCatalogPrefs:Object;
      private var apexCatalogStore:Object;
      private var apexCatalogUi:flash.display.Sprite;
      private var apexCatalogRows:flash.display.Sprite;
      private var apexCatalogIntent:Object;
      private var apexCatalogSignature:String = "";
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
         apexCatalogTab="items";
         apexCatalogSelectionFrames=0;apexCatalogSelectionMaxMs=0;apexCatalogSelectionOverBudget=0;
         try {
            apexCatalogStore=flash.net.SharedObject.getLocal("TD1ApexCASCatalog");
            if(apexCatalogStore!=null && apexCatalogStore.data.version===1)
               { ApexCatalogValidate(apexCatalogStore.data.preferences);apexCatalogSaved=true; }
         } catch(storageError:Error) { apexCatalogStore=null; }
         if(!apexCatalogRegistered)
            apexCatalogRegistered=RegisterServiceHandler("ApexOpenEquippedCatalog",ApexCatalogOpen);
         addEventListener(flash.events.Event.ENTER_FRAME,ApexCatalogFrame,false,0,true);
      }

      private function ApexCatalogValidate(p:Object) : void
      {
         if(p==null || !isFinite(Number(p.columns)) || int(p.columns)!=Number(p.columns) || int(p.columns)<2 || int(p.columns)>12 ||
            !isFinite(Number(p.color)) || Number(p.color)!=uint(p.color) || uint(p.color)>0xffffff ||
            !isFinite(Number(p.glow)) || Number(p.glow)<0 || Number(p.glow)>12 ||
            !isFinite(Number(p.border)) || Number(p.border)<1 || Number(p.border)>8 ||
            !isFinite(Number(p.strength)) || Number(p.strength)<0.25 || Number(p.strength)>1 ||
            !isFinite(Number(p.period)) || Number(p.period)<0.8 || Number(p.period)>4 ||
            (p.animation!="none" && p.animation!="pulse" && p.animation!="flash"))
            throw new Error("Invalid bounded CAS catalog preferences");
         apexCatalogPrefs={columns:int(p.columns),color:uint(p.color),glow:Number(p.glow),animation:String(p.animation),
            strength:Number(p.strength),period:Number(p.period),border:Number(p.border)};
         apexCatalogSignature="";apexCatalogSaved=false;
      }

      private function ApexCatalogPersist() : void
      {
         if(apexCatalogStore==null) return;
         try {
            apexCatalogStore.data.version=1;apexCatalogStore.data.preferences=apexCatalogPrefs;
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

      private function ApexCatalogDispose() : void
      {
         removeEventListener(flash.events.Event.ENTER_FRAME,ApexCatalogFrame);
         if(stage!=null) {
            stage.removeEventListener(flash.events.MouseEvent.MOUSE_MOVE,ApexCatalogSlide);
            stage.removeEventListener(flash.events.MouseEvent.MOUSE_UP,ApexCatalogSlideEnd);
         }
         if(apexCatalogRegistered) UnregisterServiceHandler("ApexOpenEquippedCatalog",ApexCatalogOpen);
         apexCatalogRegistered=false;
         ApexCatalogClearEffects();
         if(apexCatalogUi!=null && apexCatalogUi.parent!=null) apexCatalogUi.parent.removeChild(apexCatalogUi);
         apexCatalogUi=null;apexCatalogRows=null;apexCatalogItems=[];apexCatalogIntent=null;apexCatalogStore=null;
         apexCatalogContext="";apexCatalogSignature="";apexCatalogDrag="";apexCatalogTab="items";
      }

      private function ApexCatalogOpen(value:Object=null) : Object
      {
         // The native radial button only queues. No game calls in its click.
         var started:int=flash.utils.getTimer();
         apexCatalogIntent={operation:"open"};ApexInputTiming(started);return {protocol:1,queued:true};
      }

      private function ApexCatalogFrame(event:flash.events.Event=null) : void
      {
         if(apexCatalogPrefs==null || stage==null || apexDisconnected) return;
         try {
         var panel:Object=this.mCurrentPanel;
         if(panel!=null && panel.visible && panel.mcTileList!=null && panel.mcTileList.mGridLayout!=null && panel is ClothingPanel) {
            var grid:Object=panel.mcTileList.mGridLayout;
            var maximum:int=Math.max(2,Math.min(12,int((stage.stageWidth*0.53-40)/111)));
            var columns:int=Math.min(int(apexCatalogPrefs.columns),maximum);
            var signature:String=String(mCurrState)+":"+columns+":"+stage.stageWidth+":"+apexCatalogPrefs.color+":"+
               apexCatalogPrefs.glow+":"+apexCatalogPrefs.border;
            if(signature!=apexCatalogSignature) {
               ApexCatalogClearEffects();apexCatalogSignature=signature;
               // The donor uses 262 + (columns - 2) * 111. Preserve EA cell
               // size, scrolling and lazy thumbnail loading; never scale tiles.
               grid.NumLines=columns;
               panel.width=262+(columns-2)*111;
               // EA owns the model-bound container's placement. Offsetting a
               // child here feeds back into native binding bounds and drifts.
               grid.PositionCells();
            }
            ApexCatalogSelection(grid);
         } else if(apexCatalogEffects!=null && apexCatalogEffects.length>0) ApexCatalogClearEffects();
         if(apexCatalogUi!=null && apexCatalogUi.visible) {
            if(apexCatalogContext!="" && mCurrSimInfo!=null &&
               apexCatalogContext!=String(mCurrSimInfo.simId)+"|"+apexFormsSelectedId) {
               apexCatalogItems=[];apexCatalogContext="";apexCatalogError="Sim or form changed. Refresh equipped items.";ApexCatalogDraw();
            }
            apexCatalogUi.x=Math.max(12,stage.stageWidth-apexCatalogUi.width-20);
            apexCatalogUi.y=75;
         }
         if(apexCatalogIntent!=null && apexPendingFields==null && !apexReceiving) {
            var intent:Object=apexCatalogIntent;apexCatalogIntent=null;
            try {
               if(intent.operation=="open") { ApexCatalogReadEquipped();ApexCatalogDraw(); }
               else if(intent.operation=="navigate") {
                  if(String(mCurrSimInfo.simId)!=intent.sim_id || apexFormsSelectedId!=intent.owner_id)
                     throw new Error("The Sim or form changed; refresh equipped items");
                  var target:int=int(intent.state);
                  if(apexCatalogUi!=null) apexCatalogUi.visible=false;
                  HandleContextMenuSetMenuState({menuState:target,skipAnim:true,setZoomState:true});
               }
            } catch(catalogError:Error) {apexCatalogError=catalogError.message;ApexCatalogDraw();}
         }
         } catch(frameError:Error) {
            apexCatalogError="Catalog display paused: "+frameError.message;
            removeEventListener(flash.events.Event.ENTER_FRAME,ApexCatalogFrame);
            ApexCatalogClearEffects();
         }
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
         var cells:Object=grid.GetAllDisplayObjectCells();var kept:Array=[];
         for each(var cell:Object in cells) {
            if(cell==null || !cell.visible || !cell.Selected) continue;
            var effect:flash.display.Sprite=cell.getChildByName("apexSelectedBorder") as flash.display.Sprite;
            var retained:Object=null;
            for each(var previous:Object in apexCatalogEffects) if(previous.cell===cell) {retained=previous;break;}
            if(effect==null) {
               effect=new flash.display.Sprite();effect.name="apexSelectedBorder";effect.mouseEnabled=false;effect.mouseChildren=false;
               var bounds:flash.geom.Rectangle=cell.getBounds(cell);
               effect.graphics.lineStyle(Number(apexCatalogPrefs.border),uint(apexCatalogPrefs.color),1,true);
               effect.graphics.drawRoundRect(bounds.x+2,bounds.y+2,Math.max(2,bounds.width-4),Math.max(2,bounds.height-4),9,9);
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
            effect.alpha=alpha;
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
         var slot:Object=CommunicationManager.CallGameService("CasGetCurrSimOutfitSlot");
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
         ApexFormsText(parent,label,15,y,200,11,0x275273);
         var track:flash.display.Sprite=new flash.display.Sprite();track.name="slider_"+name;track.y=y+20;track.x=15;
         track.graphics.beginFill(0xb8d7e8);track.graphics.drawRoundRect(0,-3,300,12,8,8);track.graphics.endFill();
         track.graphics.beginFill(uint(apexCatalogPrefs.color));track.graphics.drawCircle(300*(value-low)/(high-low),3,7);track.graphics.endFill();
         track.buttonMode=true;parent.addChild(track);
      }

      private function ApexCatalogDraw() : void
      {
         if(apexCatalogUi!=null && apexCatalogUi.parent!=null) apexCatalogUi.parent.removeChild(apexCatalogUi);
         apexCatalogUi=new flash.display.Sprite();apexCatalogUi.name="ApexEquippedCatalog";addChild(apexCatalogUi);
         apexCatalogUi.graphics.lineStyle(2,0xffffff);apexCatalogUi.graphics.beginFill(0xeef8ff,0.99);apexCatalogUi.graphics.drawRoundRect(0,0,350,620,16,16);apexCatalogUi.graphics.endFill();
         ApexFormsText(apexCatalogUi,"All equipped CAS items",15,12,280,17,0x235a80);
         ApexCatalogButton(apexCatalogUi,"close","Close",270,10,64);
         ApexCatalogButton(apexCatalogUi,"tab_items","Equipped items",15,46,155);
         ApexCatalogButton(apexCatalogUi,"tab_style","Catalog style",180,46,155);
         if(apexCatalogTab=="style") {
         ApexCatalogSlider(apexCatalogUi,"columns","Columns: "+apexCatalogPrefs.columns+" (fits your screen)",apexCatalogPrefs.columns,2,12,86);
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
         } else {
         ApexCatalogButton(apexCatalogUi,"refresh","Refresh items",15,86,128);
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
         else if(name=="tab_items" || name=="tab_style") {apexCatalogTab=name=="tab_items" ? "items" : "style";ApexCatalogDraw();}
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

      private function ApexCatalogSlide(event:flash.events.MouseEvent=null) : void
      {
         if(apexCatalogDrag=="" || apexCatalogUi==null) return;
         var ratio:Number=Math.max(0,Math.min(1,(apexCatalogUi.mouseX-15)/300));var c:uint=uint(apexCatalogPrefs.color);
         if(apexCatalogDrag=="columns") apexCatalogPrefs.columns=2+Math.round(ratio*10);
         else if(apexCatalogDrag=="glow") apexCatalogPrefs.glow=ratio*12;
         else if(apexCatalogDrag=="border") apexCatalogPrefs.border=1+ratio*7;
         else if(apexCatalogDrag=="period") apexCatalogPrefs.period=0.8+ratio*3.2;
         else if(apexCatalogDrag=="strength") apexCatalogPrefs.strength=0.25+ratio*0.75;
         else if(apexCatalogDrag=="red") apexCatalogPrefs.color=(c&0xffff)|(Math.round(ratio*255)<<16);
         else if(apexCatalogDrag=="green") apexCatalogPrefs.color=(c&0xff00ff)|(Math.round(ratio*255)<<8);
         else if(apexCatalogDrag=="blue") apexCatalogPrefs.color=(c&0xffff00)|Math.round(ratio*255);
         apexCatalogSignature="";apexCatalogSaved=false;
         // Coalesce pointer motion; redraw once when the drag ends.
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
         var layout:Object=null;
         if(stage!=null && mCurrentPanel!=null && mCurrentPanel.visible) {
            var bounds:flash.geom.Rectangle=mCurrentPanel.mcPanelBackground.getBounds(stage);
            layout={x:bounds.x,y:bounds.y,width:bounds.width,height:bounds.height,
               local_x:mCurrentPanel.x,stage_width:stage.stageWidth,stage_height:stage.stageHeight};
         }
         return {preferences:apexCatalogPrefs,visible:apexCatalogUi!=null && apexCatalogUi.visible,items:apexCatalogItems,
            catalog_bounds:layout,
            actual_columns:apexCatalogSignature=="" ? 0 : int(apexCatalogSignature.split(":")[1]),
            equipped_count:apexCatalogItems==null ? 0 : apexCatalogItems.length,context:apexCatalogContext,
            error:apexCatalogError,persisted:apexCatalogSaved,selection_effect_count:apexCatalogEffects==null ? 0 : apexCatalogEffects.length,
            selection_timing:{samples:apexCatalogSelectionFrames,max_ms:apexCatalogSelectionMaxMs,
               over_1ms:apexCatalogSelectionOverBudget,clock_resolution_ms:1}};
      }
