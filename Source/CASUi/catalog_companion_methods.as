      // Dynamic CAS Companion interaction patterns, integrated into Apex's
      // eligible native feed. Attribution: maru, CC BY 4.0 (see THIRD_PARTY).
      // Preferences contain catalogue keys only, never a Sim or appearance.
      private var apexCompanion:Object;

      private function ApexCompanionInitialize() : void
      {
         apexCompanion={favorites:{},hidden:{},recent:[],mode:"all",hide_mode:false,root:null,grid:null,
            panel:null,feed:null,context:"",intent:null,dirty:true,store:null,due:0,persist:false,
            message:"",paused:false,badges:new flash.utils.Dictionary(true),buttons:[],stage:null,
            toggles:0,revision:0,paint_ms:0,storage_error:"",drag:false,resize:null,receipt:null,favorite_count:0,hidden_count:0};
         try {
            apexCompanion.store=flash.net.SharedObject.getLocal("TD1ApexCASCompanion");
            var data:Object=apexCompanion.store.data;
            if(data.version===1) {
               if(!(data.favorites is Array) || !(data.hidden is Array) || !(data.recent is Array) ||
                  data.favorites.length>10000 || data.hidden.length>10000 || data.recent.length>200)
                  throw new Error("Invalid companion preference inventory");
               for each(var key:String in data.favorites) if(ApexCompanionValidKey(key) && apexCompanion.favorites[key]!==true) {apexCompanion.favorites[key]=true;apexCompanion.favorite_count++;}
               for each(key in data.hidden) if(ApexCompanionValidKey(key) && apexCompanion.hidden[key]!==true) {apexCompanion.hidden[key]=true;apexCompanion.hidden_count++;}
               for each(key in data.recent) if(ApexCompanionValidKey(key) && apexCompanion.recent.indexOf(key)<0) apexCompanion.recent.push(key);
            }
         } catch(error:Error) {apexCompanion.store=null;apexCompanion.storage_error=error.message;}
      }

      private function ApexCompanionValidKey(key:String) : Boolean
      {
         return /^(part|preset)\/-?[0-9]{1,10}\/[1-9][0-9]{0,19}$/.test(key);
      }

      private function ApexCompanionKey(product:Object) : String
      {
         if(product==null || !/^[1-9][0-9]{0,19}$/.test(String(product.data_id))) return "";
         return int(product.body_type)>0 ? "part/"+int(product.body_type)+"/"+product.data_id : "preset/"+mCurrState+"/"+product.data_id;
      }

      private function ApexCompanionAllows(product:Object) : Boolean
      {
         if(apexCompanion==null) return true;
         var key:String=ApexCompanionKey(product);var hidden:Boolean=apexCompanion.hidden[key]===true;
         if(apexCompanion.mode=="hidden") return hidden;
         if(hidden) return false;
         if(apexCompanion.mode=="favorites") return apexCompanion.favorites[key]===true;
         if(apexCompanion.mode=="recent") return apexCompanion.recent.indexOf(key)>=0;
         return true;
      }

      private function ApexCompanionRecentOrder(left:Object,right:Object) : Number
      {
         return apexCompanion.recent.indexOf(ApexCompanionKey(left))-apexCompanion.recent.indexOf(ApexCompanionKey(right));
      }

      private function ApexCompanionSave() : void
      {
         if(apexCompanion==null || !apexCompanion.persist || flash.utils.getTimer()<int(apexCompanion.due)) return;
         apexCompanion.persist=false;
         if(apexCompanion.store==null) return;
         try {
            var favorites:Array=[];var hidden:Array=[];
            for(var key:String in apexCompanion.favorites) if(apexCompanion.favorites[key]===true) favorites.push(key);
            for(key in apexCompanion.hidden) if(apexCompanion.hidden[key]===true) hidden.push(key);
            apexCompanion.store.data.version=1;apexCompanion.store.data.favorites=favorites;
            apexCompanion.store.data.hidden=hidden;apexCompanion.store.data.recent=apexCompanion.recent.concat();
            if(apexCompanion.store.flush()==flash.net.SharedObjectFlushStatus.PENDING)
               apexCompanion.storage_error="Preference storage permission pending";
         } catch(error:Error) {apexCompanion.storage_error=error.message;}
      }

      private function ApexCompanionChanged() : void
      {
         apexCompanion.revision++;apexCompanion.persist=true;apexCompanion.due=flash.utils.getTimer()+500;
         apexCompanion.dirty=true;
      }

      private function ApexCompanionIntent(action:String,product:Object=null) : void
      {
         if(apexCompanion==null || apexSearch==null || apexSearch.rows==null || mCurrSimInfo==null) return;
         // Single, exact intent; an earlier queued click is never overwritten.
         if(apexCompanion.intent!=null) {apexCompanion.message="Previous catalogue action is still pending";return;}
         apexCompanion.intent={action:action,product:product,context:ApexSearchContext(),panel:mCurrentPanel,feed:apexSearch.feed};
      }

      private function ApexCompanionCard(event:GridEvent) : void
      {
         if(apexCompanion==null || event.mData==null || apexCompanion.grid==null || event.currentTarget!==apexCompanion.grid) return;
         var click:PushButtonEvent=event.mCellEvent as PushButtonEvent;
         if(click!=null && click.buttonIdx==1) {
            // The same GFx right-button index used by the donor. Intercept
            // before EA's equip route; a favorite/hide action cannot equip.
            event.stopImmediatePropagation();
            ApexCompanionIntent(apexCompanion.hide_mode ? "toggle-hidden" : "toggle-favorite",event.mData);
         } else {
            var key:String=ApexCompanionKey(event.mData);
            if(key!="") {
               var old:int=apexCompanion.recent.indexOf(key);if(old>=0) apexCompanion.recent.splice(old,1);
               apexCompanion.recent.unshift(key);if(apexCompanion.recent.length>200) apexCompanion.recent.pop();
               ApexCompanionChanged();
            }
         }
      }

      private function ApexCompanionButton(event:flash.events.MouseEvent) : void
      {
         ApexCompanionIntent(String(event.currentTarget.name).substr(14));event.stopImmediatePropagation();
      }

      private function ApexCompanionKeyDown(event:flash.events.KeyboardEvent) : void
      {
         if(apexCompanion==null || apexCompanion.root==null || !apexCompanion.root.visible || ApexCatalogKeyboardTyping()) return;
         if(event.keyCode==32 && !event.ctrlKey && !event.altKey && !event.shiftKey) ApexCompanionIntent("pause");
         else if(event.keyCode==50 && event.ctrlKey && event.shiftKey && !event.altKey) ApexCompanionIntent("columns-reset");
         else return;
         event.preventDefault();event.stopImmediatePropagation();
      }

      private function ApexCompanionResizeStart(event:flash.events.MouseEvent) : void
      {
         if(apexCompanion==null || stage==null || apexCompanion.drag) return;
         var point:flash.geom.Point=mCurrentPanel.globalToLocal(new flash.geom.Point(stage.mouseX,stage.mouseY));
         apexCompanion.drag={panel:mCurrentPanel,context:ApexSearchContext(),start_x:point.x,columns:int(apexCatalogPrefs.columns)};
         event.stopImmediatePropagation();
      }

      private function ApexCompanionResizeEnd(event:flash.events.MouseEvent) : void
      {
         if(apexCompanion==null || !apexCompanion.drag) return;
         apexCompanion.drag=false;apexCompanion.persist_catalog=true;apexCompanion.catalog_due=flash.utils.getTimer()+500;
      }

      private function ApexCompanionGlyph(parent:flash.display.Sprite,kind:String,color:uint,fill:Boolean=false) : void
      {
         var g:flash.display.Graphics=parent.graphics;g.clear();g.lineStyle(1.6,color,1);
         if(kind=="favorites") {
            if(fill) g.beginFill(color,1);
            for(var i:int=0;i<10;i++) {var a:Number=-Math.PI/2+i*Math.PI/5;var r:Number=i%2==0 ? 8 : 3.6;
               var x:Number=12+Math.cos(a)*r;var y:Number=12+Math.sin(a)*r;if(i==0) g.moveTo(x,y);else g.lineTo(x,y);}
            g.lineTo(12,4);if(fill) g.endFill();
         } else if(kind=="recent") {g.drawCircle(12,12,8);g.moveTo(12,6);g.lineTo(12,12);g.lineTo(17,14);}
         else if(kind=="hidden" || kind=="hide-mode") {
            g.drawEllipse(3,6,18,12);g.drawCircle(12,12,3);
            if(kind=="hide-mode") {g.moveTo(3,3);g.lineTo(21,21);}
         } else if(kind=="random-favorite") {
            g.drawRoundRect(4,4,16,16,4,4);g.beginFill(color);g.drawCircle(8,8,1.3);g.drawCircle(16,16,1.3);g.drawCircle(12,12,1.3);g.endFill();
         } else if(kind=="pause") {g.moveTo(9,5);g.lineTo(9,19);g.moveTo(16,5);g.lineTo(16,19);}
         else if(kind=="play") {g.moveTo(8,4);g.lineTo(20,12);g.lineTo(8,20);g.lineTo(8,4);}
         else {for(i=0;i<4;i++) g.drawRect(5+(i%2)*9,5+int(i/2)*9,5,5);}
      }

      private function ApexCompanionAttach() : void
      {
         var panel:Object=mCurrentPanel;var grid:Object=panel.mcTileList.GetGridView();
         if(apexCompanion.grid!==grid) {
            if(apexCompanion.grid!=null) apexCompanion.grid.removeEventListener(GridEvent.CELL_EVENT+PushButtonEvent.CLICK,ApexCompanionCard);
            apexCompanion.grid=grid;
            grid.addEventListener(GridEvent.CELL_EVENT+PushButtonEvent.CLICK,ApexCompanionCard,false,100,true);
         }
         if(apexCompanion.root==null || apexCompanion.root.parent!==apexSearch.root.parent) {
            for each(var previous:Object in apexCompanion.buttons) previous.tooltip.Shutdown();
            if(apexCompanion.root!=null && apexCompanion.root.parent!=null) apexCompanion.root.parent.removeChild(apexCompanion.root);
            var root:flash.display.Sprite=new flash.display.Sprite();root.name="ApexCASCompanion";apexSearch.root.parent.addChild(root);
            apexCompanion.root=root;apexCompanion.buttons=[];
            var actions:Array=["all","favorites","recent","hidden","hide-mode","random-favorite","pause"];
            var tips:Array=["All eligible items","Favorites only · right-click a thumbnail to favorite/unfavorite",
               "Recently selected items","Hidden items only · right-click in Hide mode to restore",
               "Hide mode · right-click thumbnails to hide/unhide; no package is removed",
               "Choose and equip a random favorite from this eligible category","Pause/play CAS animations · Space when not typing"];
            for(var i:int=0;i<actions.length;i++) {
               var button:flash.display.Sprite=new flash.display.Sprite();button.name="apexCompanion_"+actions[i];button.x=i*29;button.buttonMode=true;button.mouseChildren=false;
               button.addEventListener(flash.events.MouseEvent.CLICK,ApexCompanionButton,false,0,true);
               var glyph:flash.display.Sprite=new flash.display.Sprite();glyph.name="glyph";button.addChild(glyph);
               // Keep tooltip ownership separate from the form strip, whose
               // redraw disposes its own registered tooltip collection.
               var tooltip:TooltipObject=new TooltipObject(button);tooltip.Initialize({text:tips[i],maxwidth:310},250);
               apexCompanion.buttons.push({button:button,glyph:glyph,tooltip:tooltip,signature:""});root.addChild(button);
            }
         }
         apexCompanion.root.x=apexSearch.root.x;apexCompanion.root.y=apexSearch.geometry.bubble_y;
         for each(var row:Object in apexCompanion.buttons) {
            var action:String=String(row.button.name).substr(14);var active:Boolean=apexCompanion.mode==action || action=="hide-mode" && apexCompanion.hide_mode;
            var signature:String=action+":"+active+":"+apexCompanion.paused;
            if(row.signature==signature) continue;row.signature=signature;
            row.button.graphics.clear();row.button.graphics.lineStyle(1,active ? 0x8fc53c : 0xa7ced4,0.9);
            row.button.graphics.beginFill(active ? 0xe2f6c8 : 0xe7f6f5,0.95);row.button.graphics.drawRoundRect(0,0,25,24,7,7);row.button.graphics.endFill();
            ApexCompanionGlyph(row.glyph,action=="pause" && apexCompanion.paused ? "play" : action,active ? 0x4b7e15 : 0x276584,active);
         }
      }

      private function ApexCompanionApply(action:String,product:Object=null) : void
      {
         if(["all","favorites","recent","hidden"].indexOf(action)>=0) {apexCompanion.mode=action;apexCompanion.dirty=true;return;}
         if(action=="hide-mode") {apexCompanion.hide_mode=!apexCompanion.hide_mode;return;}
         if(action=="refresh-search") {
            if(ApexNativeExchange("SEARCHRELOAD|"+apexNativeChannel)!="SEARCHRELOADED") throw new Error("The exact catalogue context could not reload");
            ApexSearchReset(ApexSearchContext());apexSearch.due=0;return;
         }
         if(action=="columns-reset") {apexCatalogPrefs.columns=2;apexCatalogSignature="";apexCompanion.persist_catalog=true;apexCompanion.catalog_due=flash.utils.getTimer()+500;return;}
         if(action=="pause" || action=="play") {
            if(!flash.external.ExternalInterface.available) throw new Error("Native CAS clock is unavailable");
            var pause:Boolean=action=="pause" ? !apexCompanion.paused : false;
            flash.external.ExternalInterface.call("PostCheatCommand",pause ? "casclockspeed 0" : "casclockspeed 1");
            apexCompanion.paused=pause;return;
         }
         if(action=="random-favorite") {
            if(apexSearch.pending) throw new Error("Wait for the current search before choosing a favorite");
            var candidates:Array=[];var feed:Object=apexSearch.feed;
            for(var at:int=0;at<int(feed.length);at++) {
               var item:Object=feed.RequestItemAt(at);if(apexCompanion.favorites[ApexCompanionKey(item)]===true) candidates.push(at);
            }
            if(candidates.length==0) throw new Error("No favorites in the current eligible results");
            at=int(candidates[int(Math.random()*candidates.length)]);
            apexCompanion.grid.dispatchEvent(new GridEvent(GridEvent.CELL_EVENT+PushButtonEvent.CLICK,null,null,feed.RequestItemAt(at),false,at,at));return;
         }
         if(action!="toggle-favorite" && action!="toggle-hidden") throw new Error("Unknown companion action");
         var key:String=ApexCompanionKey(product);
         if(key=="" || apexSearch.rows.indexOf(product)<0) throw new Error("The item is outside the exact native eligible source");
         var map:Object=action=="toggle-favorite" ? apexCompanion.favorites : apexCompanion.hidden;
         var counter:String=action=="toggle-favorite" ? "favorite_count" : "hidden_count";
         if(map[key]===true) {delete map[key];apexCompanion[counter]--;}else {
            if(int(apexCompanion[counter])>=10000) throw new Error("Catalogue preference inventory is full");map[key]=true;apexCompanion[counter]++;
         }
         apexCompanion.toggles++;ApexCompanionChanged();
      }

      private function ApexCompanionBadges() : void
      {
         var started:int=flash.utils.getTimer();var grid:Object=mCurrentPanel.mcTileList.mGridLayout;
         for each(var cell:Object in ApexCatalogCells(grid)) {
            if(cell==null || !cell.visible) continue;
            var index:int=grid.GetGridIndexOfCell(cell);
            if(index<0 || index>=int(apexSearch.feed.length)) continue;
            var product:Object=apexSearch.feed.RequestItemAt(index);
            var cached:Object=apexCompanion.badges[cell];
            if(cached!=null && cached.product===product && cached.revision==apexCompanion.revision) continue;
            apexCompanion.badges[cell]={product:product,revision:apexCompanion.revision};
            var key:String=ApexCompanionKey(product);var favorite:Boolean=apexCompanion.favorites[key]===true;var hidden:Boolean=apexCompanion.hidden[key]===true;
            var badge:flash.display.Sprite=cell.getChildByName("apexCompanionBadge") as flash.display.Sprite;
            if(!favorite && !hidden) {if(badge!=null) badge.visible=false;continue;}
            if(badge==null) {badge=new flash.display.Sprite();badge.name="apexCompanionBadge";badge.mouseEnabled=false;badge.mouseChildren=false;cell.addChild(badge);}
            badge.visible=true;badge.x=cell.mcHitArea==null ? 2 : cell.mcHitArea.width-25;badge.y=2;
            ApexCompanionGlyph(badge,hidden ? "hide-mode" : "favorites",hidden ? 0xb13c53 : 0xe8ab15,true);
         }
         apexCompanion.paint_ms=Math.max(apexCompanion.paint_ms,flash.utils.getTimer()-started);
      }

      private function ApexCompanionFrame() : void
      {
         if(apexCompanion==null) return;
         if(stage!=null && apexCompanion.stage!==stage) {
            if(apexCompanion.stage!=null) {
               apexCompanion.stage.removeEventListener(flash.events.KeyboardEvent.KEY_DOWN,ApexCompanionKeyDown,true);
               apexCompanion.stage.removeEventListener(flash.events.MouseEvent.MOUSE_UP,ApexCompanionResizeEnd);
            }
            apexCompanion.stage=stage;stage.addEventListener(flash.events.KeyboardEvent.KEY_DOWN,ApexCompanionKeyDown,true,19,true);
            stage.addEventListener(flash.events.MouseEvent.MOUSE_UP,ApexCompanionResizeEnd,false,0,true);
         }
         ApexCompanionSave();
         if(apexCompanion.persist_catalog===true && flash.utils.getTimer()>=int(apexCompanion.catalog_due)) {
            apexCompanion.persist_catalog=false;ApexCatalogPersist();
         }
         if(apexSearch==null || apexSearch.root==null || apexSearch.rows==null || apexSearch.panel!==mCurrentPanel ||
            apexSearch.context!=ApexSearchContext() || apexEquippedActive) {
            if(apexCompanion.resize!=null) apexCompanion.resize.visible=false;
            if(apexCompanion.root!=null) apexCompanion.root.visible=false;return;
         }
         ApexCompanionAttach();apexCompanion.root.visible=true;
         if("mcPanelBackground" in mCurrentPanel && mCurrentPanel.mcPanelBackground!=null) {
            if(apexCompanion.resize==null) {
               var resize:flash.display.Sprite=new flash.display.Sprite();resize.name="apexColumnResize";resize.buttonMode=true;
               resize.addEventListener(flash.events.MouseEvent.MOUSE_DOWN,ApexCompanionResizeStart,false,50,true);apexCompanion.resize=resize;
            }
            if(apexCompanion.resize.parent!==mCurrentPanel) mCurrentPanel.addChild(apexCompanion.resize);
            var handle:flash.display.Sprite=apexCompanion.resize;
            handle.visible=true;
            handle.x=mCurrentPanel.mcPanelBackground.width-7;handle.y=mCurrentPanel.mcTileList.y;
            var signature:String=handle.x+":"+handle.y+":"+mCurrentPanel.mcTileList.height;
            if(apexCompanion.resize_signature!==signature) {
               apexCompanion.resize_signature=signature;handle.graphics.clear();handle.graphics.beginFill(0x95cfd1,0.35);
               handle.graphics.drawRoundRect(-3,0,10,mCurrentPanel.mcTileList.height,5,5);handle.graphics.endFill();
            }
            if(apexCompanion.drag) {
               var drag:Object=apexCompanion.drag;
               if(drag.panel!==mCurrentPanel || drag.context!=ApexSearchContext()) apexCompanion.drag=false;
               else {
                  var point:flash.geom.Point=mCurrentPanel.globalToLocal(new flash.geom.Point(stage.mouseX,stage.mouseY));
                  var pitch:Number=mCurrentPanel.mcTileList.mGridLayout.GetCellBounds().width+mCurrentPanel.mcTileList.mGridLayout.GetCellPadding().Horizontal;
                  var columns:int=Math.max(2,Math.min(8,int(Math.round(int(drag.columns)+(point.x-Number(drag.start_x))/Math.max(1,pitch)))));
                  if(int(apexCatalogPrefs.columns)!=columns) {apexCatalogPrefs.columns=columns;apexCatalogSignature="";}
               }
            }
         }
         if(apexCompanion.context!=ApexSearchContext() || apexCompanion.feed!==apexSearch.feed) {
            apexCompanion.context=ApexSearchContext();apexCompanion.feed=apexSearch.feed;apexCompanion.dirty=true;
         }
         var intent:Object=apexCompanion.intent;apexCompanion.intent=null;
         if(intent!=null && intent.context==ApexSearchContext() && intent.panel===mCurrentPanel && intent.feed===apexSearch.feed) {
            try {
               if(Boolean(CommunicationManager.CallUIService("IsUILoadingScreenVisible")) || Boolean(CommunicationManager.CallUIService("IsModalVisible")) ||
                  Boolean(CommunicationManager.CallUIService("IsDialogModalVisible"))) throw new Error("A modal currently owns input");
               ApexCompanionApply(intent.action,intent.product);
               ApexCompanionReceipt(intent.action,intent.product);
            }catch(error:Error) {apexCompanion.message=error.message;}
         }
         if(apexCompanion.dirty && !apexSearch.pending && apexPendingFields==null && !apexReceiving) {
            apexCompanion.dirty=false;ApexSearchPublish();
         }
         ApexCompanionBadges();
      }

      private function ApexCompanionCommand(value:String) : void
      {
         if(apexCompanion==null || apexSearch==null || apexSearch.rows==null || apexSearch.panel!==mCurrentPanel ||
            apexSearch.context!=ApexSearchContext() || apexEquippedActive) throw new Error("Open an exact native catalogue first");
         if(apexCompanion.intent!=null) throw new Error("A previous companion gesture is pending");
         if(Boolean(CommunicationManager.CallUIService("IsUILoadingScreenVisible")) || Boolean(CommunicationManager.CallUIService("IsModalVisible")) ||
            Boolean(CommunicationManager.CallUIService("IsDialogModalVisible"))) throw new Error("A modal currently owns input");
         var fields:Array=value.split(",");if(fields.length!=2) throw new Error("Typed companion action and item are required");
         var product:Object=null;
         if(fields[1]!="") {
            for each(var row:Object in apexSearch.rows) if(String(row.data_id)==fields[1]) {product=row;break;}
            if(product==null) throw new Error("The item is not in this native category");
         }
         ApexCompanionApply(String(fields[0]),product);
         ApexCompanionReceipt(String(fields[0]),product);
         if(!apexSearch.pending) {apexCompanion.dirty=false;ApexSearchPublish();}
      }

      private function ApexCompanionStatus() : Object
      {
         if(apexCompanion==null) return {available:false};
         var favorites:Array=[];var hidden:Array=[];
         for(var key:String in apexCompanion.favorites) {favorites.push(key);if(favorites.length>=64) break;}
         for(key in apexCompanion.hidden) {hidden.push(key);if(hidden.length>=64) break;}
         var receiptKey:String=apexCompanion.receipt==null ? "" : String(apexCompanion.receipt.key);
         if(apexCompanion.favorites[receiptKey]===true && favorites.indexOf(receiptKey)<0) favorites.push(receiptKey);
         if(apexCompanion.hidden[receiptKey]===true && hidden.indexOf(receiptKey)<0) hidden.push(receiptKey);
         return {available:apexCompanion.root!=null,mode:apexCompanion.mode,hide_mode:apexCompanion.hide_mode,
            favorite_count:apexCompanion.favorite_count,hidden_count:apexCompanion.hidden_count,favorites:favorites,hidden:hidden,
            favorite_sample_complete:favorites.length==apexCompanion.favorite_count,hidden_sample_complete:hidden.length==apexCompanion.hidden_count,
            recent:apexCompanion.recent.concat(),pending:apexCompanion.intent!=null,save_pending:apexCompanion.persist,
            storage_error:apexCompanion.storage_error,message:apexCompanion.message,paused:apexCompanion.paused,
            toggles:apexCompanion.toggles,revision:apexCompanion.revision,visible_cells_max_ms:apexCompanion.paint_ms,
            source:"native eligible catalogue",appearance_written:false,receipt:apexCompanion.receipt};
      }

      private function ApexCompanionReceipt(action:String,product:Object) : void
      {
         var key:String=ApexCompanionKey(product);
         apexCompanion.receipt={action:action,data_id:product==null ? "" : String(product.data_id),key:key,
            enabled:action=="toggle-favorite" ? apexCompanion.favorites[key]===true : action=="toggle-hidden" ? apexCompanion.hidden[key]===true : null,
            sim_id:String(mCurrSimInfo.simId),owner_id:apexFormsSelectedId,context:ApexSearchContext()};
      }

      private function ApexCompanionDispose() : void
      {
         if(apexCompanion==null) return;
         apexCompanion.due=0;ApexCompanionSave();
         if(apexCompanion.persist_catalog===true) ApexCatalogPersist();
         if(apexCompanion.grid!=null) apexCompanion.grid.removeEventListener(GridEvent.CELL_EVENT+PushButtonEvent.CLICK,ApexCompanionCard);
         if(apexCompanion.stage!=null) {
            apexCompanion.stage.removeEventListener(flash.events.KeyboardEvent.KEY_DOWN,ApexCompanionKeyDown,true);
            apexCompanion.stage.removeEventListener(flash.events.MouseEvent.MOUSE_UP,ApexCompanionResizeEnd);
         }
         if(apexCompanion.resize!=null && apexCompanion.resize.parent!=null) apexCompanion.resize.parent.removeChild(apexCompanion.resize);
         if(apexCompanion.root!=null && apexCompanion.root.parent!=null) apexCompanion.root.parent.removeChild(apexCompanion.root);
         for each(var row:Object in apexCompanion.buttons) row.tooltip.Shutdown();
         apexCompanion=null;
      }
