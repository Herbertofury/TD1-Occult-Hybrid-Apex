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
         // A literal Dynamic CAS build owns its native favorites/history UI.
         // Do not install a second right-click listener, clock shortcut or
         // competing preference store over those actual donor handlers.
         try {
            apexCompanion.donor=getDefinitionByName("widgets.CAS.dcc.DCCFavorites");
            apexCompanion.layout_owner=getDefinitionByName("widgets.CAS.Customizer.CASCustomizerMain");
         } catch(donorMissing:Error) {apexCompanion.donor=null;}
         if(apexCompanion.donor!=null) return;
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
         var grid:Object=mCurrentPanel==null || mCurrentPanel.mcTileList==null ? null : mCurrentPanel.mcTileList.mGridLayout;
         var owned:Boolean=action=="random-favorite" && grid!=null && ApexCatalogGridOwns(grid);
         var lease:Object=owned ? apexCatalogGrid.lease : null;
         if(owned && (ApexCatalogGridPending(grid) || lease==null || lease.phase!="bound" || lease.active!==true ||
            mCurrentPanel.mcTileList.GetGridView().visible!==true)) {
            apexCompanion.message="Wait for the catalog before choosing a favorite";return;
         }
         var snapshot:Object=owned ? grid.ApexGridStatus() : null;
         apexCompanion.intent={action:action,product:product,context:ApexSearchContext(),panel:mCurrentPanel,feed:apexSearch.feed,
            grid:grid,lease:lease,lease_generation:owned ? int(lease.generation) : 0,
            native_generation:owned ? String(lease.native_generation) : "",
            grid_generation:owned ? int(snapshot.generation) : 0,grid_revision:owned ? int(snapshot.revision) : 0};
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
            var panel:Object=mCurrentPanel;
            var grid:Object=panel==null || panel.mcTileList==null ? null : panel.mcTileList.mGridLayout;
            var owned:Boolean=grid!=null && ApexCatalogGridOwns(grid);
            var lease:Object=owned ? apexCatalogGrid.lease : null;
            if(owned && (ApexCatalogGridPending(grid) || lease==null || panel.visible!==true ||
               panel.mcTileList.visible!==true || panel.mcTileList.GetGridView()!==apexCompanion.grid ||
               apexCompanion.grid.visible!==true || grid.GetDataFeed()!==feed))
               throw new Error("Wait for the current catalog before choosing a favorite");
            var snapshot:Object=owned ? grid.ApexGridStatus() : null;
            var count:int=owned ? int(grid.GetNumItems()) : int(feed.length);
            for(var at:int=0;at<count;at++) {
               var item:Object=owned ? grid.GetDataAtIndex(at) : feed.RequestItemAt(at);
               if(apexCompanion.favorites[ApexCompanionKey(item)]===true) candidates.push(at);
            }
            if(candidates.length==0) throw new Error("No favorites in the current eligible results");
            at=int(candidates[int(Math.random()*candidates.length)]);
            item=owned ? grid.GetDataAtIndex(at) : feed.RequestItemAt(at);
            if(owned) {
               if(!ApexCatalogGridInput(lease))throw new Error("The catalog owner changed; choose a favorite again");
               var current:Object=grid.ApexGridStatus();
               if(ApexCatalogGridPending(grid) || apexCatalogGrid.lease!==lease || mCurrentPanel!==panel ||
                  panel.mcTileList.mGridLayout!==grid || grid.GetDataFeed()!==feed ||
                  panel.mcTileList.GetGridView()!==apexCompanion.grid || apexCompanion.grid.visible!==true ||
                  int(current.generation)!=int(snapshot.generation) || int(current.revision)!=int(snapshot.revision) ||
                  grid.GetDataAtIndex(at)!==item)
                  throw new Error("The catalog results changed; choose a favorite again");
            }
            if(item==null)throw new Error("The favorite is no longer in the current results");
            apexCompanion.grid.dispatchEvent(new GridEvent(GridEvent.CELL_EVENT+PushButtonEvent.CLICK,null,null,item,false,at,at));return;
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
         if(apexCompanion.donor!=null) {
            var donorPanel:Object=mCurrentPanel;
            if(donorPanel==null || !donorPanel.visible || !("dccFavoriteButton" in donorPanel) || apexEquippedActive) return;
            // The donor hides its real buttons when EA has no title. Apex's
            // search can occupy that layout, so anchor the SAME buttons above
            // the search bar rather than installing duplicate controls.
            if(donorPanel.dccFavoriteButton==null) apexCompanion.donor.EnsureButton(donorPanel);
            if(apexSearch!=null && apexSearch.panel===donorPanel && apexSearch.root!=null &&
               (donorPanel.txtTitle==null || !donorPanel.txtTitle.visible || donorPanel.txtTitle.text.length==0)) {
               var bounds:flash.geom.Rectangle=apexSearch.root.getBounds(donorPanel);
               donorPanel.dccFavoriteButton.visible=true;
               donorPanel.dccFavoriteButton.x=bounds.right-76;donorPanel.dccFavoriteButton.y=bounds.top-35;
               if(donorPanel.dccHiddenButton!=null) {
                  donorPanel.dccHiddenButton.visible=true;
                  donorPanel.dccHiddenButton.x=bounds.right-38;donorPanel.dccHiddenButton.y=bounds.top-35;
               }
            }
            return;
         }
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
               if(intent.action=="random-favorite") {
                  var intentGrid:Object=mCurrentPanel.mcTileList.mGridLayout;
                  if(ApexCatalogGridOwns(intentGrid)) {
                     var intentLease:Object=apexCatalogGrid.lease;
                     var intentStatus:Object=intentGrid.ApexGridStatus();
                     if(ApexCatalogGridPending(intentGrid) || intent.grid!==intentGrid || intent.lease!==intentLease || intentLease==null ||
                        int(intent.lease_generation)!=int(intentLease.generation) || intent.native_generation!==intentLease.native_generation ||
                        int(intent.grid_generation)!=int(intentStatus.generation) || int(intent.grid_revision)!=int(intentStatus.revision))
                        throw new Error("The catalog changed; choose a favorite again");
                  }
               }
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
         if(apexCompanion!=null && apexCompanion.donor!=null) {
            // Exercise the retained donor's real handlers and preference store.
            // Never maintain a parallel Apex favorites list in this build.
            if(mCurrentPanel==null || !mCurrentPanel.visible || apexEquippedActive ||
               apexFormsDesiredId!="" ||
               apexMoleculeIntent!=null || apexFormsNativeIntent!=null)
               throw new Error("Open a settled native catalogue before changing favorites");
            // The checked semantic dispatcher already owns this command's
            // pending/receiving lease; those flags cannot reject their owner.
            var donor:Object=apexCompanion.donor;
            var donorPanel:Object=mCurrentPanel;
            if(!("dccFavoriteButton" in donorPanel) || !("mcTileList" in donorPanel))
               throw new Error("Open a native clothing catalogue with favorites controls");
            var donorFields:Array=value.split(",");
            if(donorFields.length!=2) throw new Error("Typed companion action and item are required");
            var donorType:int=int(donor.CurrentType());
            if(donorType<0 || donor.refreshPending===true)
               throw new Error("The native catalogue is still refreshing");
            if(donorFields[0]=="toggle-favorite") {
               if(!/^[1-9][0-9]{0,19}$/.test(String(donorFields[1]))) throw new Error("Choose a visible catalogue item");
               var donorCell:Object=null;
               for each(var candidate:Object in ApexCatalogCells(donorPanel.mcTileList.mGridLayout))
                  if(candidate!=null && String(candidate.dccFavoriteProductId)===String(donorFields[1])) {donorCell=candidate;break;}
               if(donorCell==null) throw new Error("The item is no longer a visible native card");
               var previousFavorite:Boolean=Boolean(donor.Has(donorType,String(donorFields[1])));
               donor.Click(donorCell);
               if(Boolean(donor.Has(donorType,String(donorFields[1])))===previousFavorite)
                  throw new Error("The donor favorite preference did not change");
               apexCompanion.receipt={action:"toggle-favorite",key:String(donor.Key(donorType,String(donorFields[1]))),
                  data_id:String(donorFields[1]),enabled:!previousFavorite,sim_id:String(mCurrSimInfo.simId),
                  owner_id:apexFormsSelectedId,source:"Dynamic CAS Companion actual code",appearance_written:false};
            } else if(donorFields[0]=="favorites" || donorFields[0]=="all") {
               if(donorFields[1]!=="" || donorPanel.dccFavoriteButton==null)
                  throw new Error("Use the native favorites button on an open catalogue");
               var wantFavorites:Boolean=donorFields[0]=="favorites";
               if(Boolean(donor.QueryMode(donorType))!==wantFavorites)
                  donorPanel.dccFavoriteButton.dispatchEvent(new flash.events.MouseEvent(flash.events.MouseEvent.CLICK));
               if(Boolean(donor.QueryMode(donorType))!==wantFavorites)
                  throw new Error("The donor favorites view did not change");
               apexCompanion.receipt={action:String(donorFields[0]),data_id:"",sim_id:String(mCurrSimInfo.simId),
                  owner_id:apexFormsSelectedId,source:"Dynamic CAS Companion actual code",appearance_written:false};
            } else throw new Error("Use the retained Dynamic CAS controls for this action");
            return;
         }
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
         if(apexCompanion.donor!=null) {
            var donor:Object=apexCompanion.donor;
            var donorPanel:Object=mCurrentPanel;
            var type:int=int(donor.CurrentType());
            var button:Object=donorPanel==null || !("dccFavoriteButton" in donorPanel)?null:donorPanel.dccFavoriteButton;
            var visibleFavorites:Array=[];
            if(donorPanel!=null && donorPanel.visible && "mcTileList" in donorPanel && donorPanel.mcTileList!=null && donorPanel.mcTileList.mGridLayout!=null)
               for each(var cell:Object in ApexCatalogCells(donorPanel.mcTileList.mGridLayout))
                  if(cell!=null && cell.dccFavoriteProductId!=null && donor.Has(type,String(cell.dccFavoriteProductId)))
                     visibleFavorites.push(String(donor.Key(type,String(cell.dccFavoriteProductId))));
            var last:Object=apexCompanion.receipt;
            if(last!=null && last.action=="toggle-favorite" && donor.Has(type,String(last.data_id)) &&
               visibleFavorites.indexOf(String(last.key))<0) visibleFavorites.push(String(last.key));
            return {available:true,source:"Dynamic CAS Companion actual code",native_controls:true,
               pending:donor.refreshPending===true,appearance_written:false,duplicate_handlers_installed:false,
               favorite_button_present:button!=null,favorite_button_visible:button!=null && button.visible===true,
               mode:donor.QueryMode(type)?"favorites":"all",favorites:visibleFavorites,receipt:ApexClone(apexCompanion.receipt)};
         }
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
