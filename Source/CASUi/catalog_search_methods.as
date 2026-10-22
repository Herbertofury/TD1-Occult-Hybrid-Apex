      // The search field lives in the native filter pane. The worker returns
      // metadata only; the retained native eligible feed is the sole source of
      // result cards. No result can synthesize a product or equip a part.
      private var apexSearch:Object;

      private function ApexSearchInitialize() : void
      {
         apexSearch={text:"",context:"",ticket:"",due:0,poll:0,rows:null,feed:null,panel:null,
            matches:{},offset:0,total:0,resolved:0,shown:0,ready:false,pending:false,error:"",page:null,index:0,
            root:null,input:null,placeholder:null,count:null,clear:null,bubble:null,list:null,geometry:null,
            registered:false,revision:0,started:0,elapsed_ms:0,sources:[],query:null,native_response:"",publish_ms:0,rebuilds:0};
         apexSearch.registered=RegisterServiceHandler("ApexCatalogSearchSource",ApexSearchSource);
      }

      private function ApexSearchContext() : String
      {
         return mCurrSimInfo==null ? "" : String(mCurrSimInfo.simId)+"|"+apexFormsSelectedId+"|"+
            apexFormsNativeGeneration+"|"+mCurrState;
      }

      private function ApexSearchRestore() : void
      {
         if(apexSearch==null) return;
         var g:Object=apexSearch.geometry;
         if(g!=null) {
            if(apexSearch.bubble!=null && apexSearch.bubble.y==g.bubble_y+26) apexSearch.bubble.y=g.bubble_y;
            if(apexSearch.list!=null && apexSearch.list.y==g.list_y+26) {
               apexSearch.list.y=g.list_y;
               if(apexSearch.list.height==g.list_height-26) apexSearch.list.height=g.list_height;
            }
         }
         if(apexSearch.root!=null && apexSearch.root.parent!=null) apexSearch.root.parent.removeChild(apexSearch.root);
         apexSearch.root=null;apexSearch.input=null;apexSearch.geometry=null;apexSearch.bubble=null;apexSearch.list=null;apexSearch.width=-1;
      }

      private function ApexSearchDispose() : void
      {
         if(apexSearch!=null && apexSearch.registered===true)
            UnregisterServiceHandler("ApexCatalogSearchSource",ApexSearchSource);
         ApexSearchRestore();apexSearch=null;
      }

      private function ApexSearchReset(context:String) : void
      {
         apexSearch.context=context;apexSearch.ticket="";apexSearch.matches={};apexSearch.page=null;
         apexSearch.index=0;apexSearch.offset=0;apexSearch.total=0;apexSearch.resolved=0;apexSearch.shown=0;
         apexSearch.ready=false;apexSearch.pending=apexSearch.text!="";apexSearch.error="";
         apexSearch.query=null;apexSearch.native_response="";
         apexSearch.due=flash.utils.getTimer()+180;apexSearch.revision++;apexSearch.started=flash.utils.getTimer();
      }

      private function ApexSearchSource(value:Object) : Object
      {
         if(apexSearch==null || value==null || !(value.rows is Array) || value.feed==null || mCurrSimInfo==null)
            return null;
         // These are already constructed, UI-owned CASCatalogProducts from
         // the native category/age/species/filter query, never borrowed GFx data.
         // EA can request them before its new panel is visible/current. Queue
         // this exact feed and primitive identity; adopt only in the idle phase.
         var source:Object={rows:value.rows.concat(),feed:value.feed,state:int(value.state),selected:[],
            sim:String(mCurrSimInfo.simId),owner:apexFormsSelectedId,generation:apexFormsNativeGeneration};
         if(value.selected is Array) for each(var selectedIndex:int in value.selected) {
            var selectedProduct:Object=value.feed.RequestItemAt(selectedIndex);
            if(selectedProduct!=null) source.selected.push(String(selectedProduct.data_id));
         }
         for(var i:int=apexSearch.sources.length-1;i>=0;i--)
            if(apexSearch.sources[i].feed===value.feed) apexSearch.sources.splice(i,1);
         if(apexSearch.sources.length>=8) apexSearch.sources.shift();
         apexSearch.sources.push(source);return null;
      }

      private function ApexSearchAdopt(panel:Object) : void
      {
         var feed:Object=panel.mcTileList.mGridLayout.GetDataFeed();
         for(var i:int=apexSearch.sources.length-1;i>=0;i--) {
            var source:Object=apexSearch.sources[i];
            if(source.feed!==feed || int(source.state)!=mCurrState) continue;
            apexSearch.sources.splice(i,1);
            if(source.sim!=String(mCurrSimInfo.simId) || source.sim!=apexBoundSim || source.owner!=apexFormsSelectedId ||
               source.generation!=apexFormsNativeGeneration) continue;
            apexSearch.rows=source.rows;apexSearch.feed=feed;apexSearch.panel=panel;apexSearch.selected=source.selected;
            ApexSearchReset(ApexSearchContext());return;
         }
      }

      private function ApexSearchText(text:String) : void
      {
         if(text.length>160 || /[\x00-\x1f\x7f]/.test(text)) throw new Error("Search accepts up to 160 printable characters");
         if(apexSearch==null || apexSearch.input==null) throw new Error("Open a native item category with a filter bar first");
         apexSearch.text=text;apexSearch.input.text=text;
         ApexSearchReset(ApexSearchContext());
         if(text=="") {apexSearch.pending=true;apexSearch.due=0;}
         ApexSearchLabels();
      }

      private function ApexSearchChanged(event:flash.events.Event) : void
      {
         // Typing only records the latest intent; no worker/native/catalog call.
         ApexSearchText(String(apexSearch.input.text));
      }

      private function ApexSearchClear(event:flash.events.MouseEvent) : void
      {
         ApexSearchText("");if(stage!=null) stage.focus=apexSearch.input;
         event.stopImmediatePropagation();
      }

      private function ApexSearchKey(event:flash.events.KeyboardEvent) : void
      {
         // Stage catalog navigation already yields to INPUT fields. Keep
         // Enter/Escape local as well, without swallowing ordinary edit keys.
         if(event.keyCode==13) {apexSearch.due=0;event.preventDefault();event.stopImmediatePropagation();}
         else if(event.keyCode==27) {ApexSearchText("");event.preventDefault();event.stopImmediatePropagation();}
      }

      private function ApexSearchLabels() : void
      {
         if(apexSearch==null || apexSearch.root==null) return;
         apexSearch.placeholder.visible=apexSearch.text=="" && (stage==null || stage.focus!==apexSearch.input);
         apexSearch.clear.visible=apexSearch.text!="";
         var caption:String=apexSearch.error!="" ? "!" : apexSearch.pending ? "…" :
            apexSearch.text=="" ? "" : String(apexSearch.shown);
         if(apexSearch.count.text!=caption) apexSearch.count.text=caption;
      }

      private function ApexSearchFocus(event:flash.events.FocusEvent) : void {ApexSearchLabels();}

      private function ApexSearchAttach(panel:Object) : void
      {
         var bubble:Object=panel.mcFilterPane.mcFilterBubble;var list:Object=panel.mcTileList;
         if(apexSearch.root==null || apexSearch.bubble!==bubble || apexSearch.list!==list) {
            ApexSearchRestore();apexSearch.bubble=bubble;apexSearch.list=list;
            var root:flash.display.Sprite=new flash.display.Sprite();root.name="ApexNativeCatalogSearch";
            bubble.parent.addChild(root);apexSearch.root=root;
            var input:flash.text.TextField=new flash.text.TextField();input.name="ApexFilterItemsInput";
            input.type=flash.text.TextFieldType.INPUT;input.selectable=true;input.maxChars=160;
            input.defaultTextFormat=new flash.text.TextFormat("Arial",12,0x17527b);
            input.height=23;input.x=8;input.y=2;input.text=apexSearch.text;root.addChild(input);apexSearch.input=input;
            input.addEventListener(flash.events.Event.CHANGE,ApexSearchChanged,false,0,true);
            input.addEventListener(flash.events.KeyboardEvent.KEY_DOWN,ApexSearchKey,false,30,true);
            input.addEventListener(flash.events.FocusEvent.FOCUS_IN,ApexSearchFocus,false,0,true);
            input.addEventListener(flash.events.FocusEvent.FOCUS_OUT,ApexSearchFocus,false,0,true);
            apexSearch.placeholder=ApexFormsText(root,"Search items / packages…",8,4,180,12,0x376681);
            apexSearch.count=ApexFormsText(root,"",0,4,42,11,0x376681);
            var clear:flash.display.Sprite=new flash.display.Sprite();clear.name="ApexClearCatalogSearch";clear.buttonMode=true;
            clear.graphics.beginFill(0xffffff,0.01);clear.graphics.drawRect(0,0,23,24);clear.graphics.endFill();
            ApexFormsText(clear,"×",6,2,18,15,0x17527b);clear.mouseChildren=false;root.addChild(clear);apexSearch.clear=clear;
            clear.addEventListener(flash.events.MouseEvent.CLICK,ApexSearchClear,false,0,true);
         }
         var g:Object=apexSearch.geometry;
         // Native RefreshLayout may reset these coordinates. Never accumulate
         // another row on top of a previously applied offset.
         if(g==null) {g={bubble_y:bubble.y,list_y:list.y,list_height:list.height};apexSearch.geometry=g;}
         if(bubble.y!=g.bubble_y+26) g.bubble_y=bubble.y;
         if(list.y!=g.list_y+26) {g.list_y=list.y;g.list_height=list.height;}
         if(bubble.y!=g.bubble_y+26) bubble.y=g.bubble_y+26;
         if(list.y!=g.list_y+26) list.y=g.list_y+26;
         var height:Number=Math.max(32,g.list_height-26);
         if(list.height!=height) list.height=height;
         var width:Number=Math.max(180,Number(bubble.mcBackground.width));
         apexSearch.root.x=bubble.x;apexSearch.root.y=g.bubble_y;
         if(apexSearch.width!==width) {
            apexSearch.width=width;apexSearch.root.graphics.clear();apexSearch.root.graphics.lineStyle(1,0xc5e2e4,0.8);
            apexSearch.root.graphics.beginFill(0xe7f6f5,0.88);apexSearch.root.graphics.drawRoundRect(0,0,width,24,8,8);apexSearch.root.graphics.endFill();
            apexSearch.input.width=width-80;apexSearch.count.x=width-68;apexSearch.clear.x=width-25;
         }
         ApexSearchLabels();
      }

      private function ApexSearchQuery() : Object
      {
         var text:String=String(apexSearch.text);var author:String="";var origin:Object=null;var body:Object=null;
         var match:Array=/\bauthor:(?:"([^"]{1,80})"|([^\s]{1,80}))/i.exec(text);
         if(match!=null) {author=match[1]!=null ? match[1] : match[2];text=text.replace(match[0]," ");}
         match=/\btype:([0-9]{1,4})\b/i.exec(text);
         if(match!=null) {body=int(match[1]);text=text.replace(match[0]," ");}
         match=/\borigin:(cc|ea)\b/i.exec(text);
         if(match!=null) {origin=String(match[1]).toLowerCase()=="cc" ? "mod" : "ea";text=text.replace(match[0]," ");}
         return {text:text,author:author,sort:"name",body_type:body,origin:origin,name_mode:"preferred",
            offset:int(apexSearch.offset),limit:24,view:"all",grouped:false,fuzzy:true};
      }

      private function ApexSearchPublish() : void
      {
         var started:int=flash.utils.getTimer();
         if(apexSearch.context!=ApexSearchContext() || apexSearch.panel!==mCurrentPanel || apexSearch.rows==null ||
            mCurrentPanel==null || mCurrentPanel.mcTileList.mGridLayout.GetDataFeed()!==apexSearch.feed || apexEquippedActive) return;
         var products:Array=[];
         for each(var product:CASCatalogProduct in apexSearch.rows)
            if(apexSearch.text=="" || apexSearch.matches[String(product.body_type)+"|"+product.data_id]===true) products.push(product);
         apexKeyQueue=[];apexKeyIntent=0;apexKeyIndex=-1;apexKeyItem=null;apexKeyBounds="";
         // A failed query leaves native cards intact. Clearing it, or a warm
         // query with identical results, must not tear down/rebind every card.
         var unchanged:Boolean=int(apexSearch.feed.length)==products.length;
         if(unchanged) for(var position:int=0;position<products.length;position++)
            if(apexSearch.feed.RequestItemAt(position)!==products[position]) {unchanged=false;break;}
         if(unchanged) {
            apexSearch.shown=products.length;apexSearch.elapsed_ms=flash.utils.getTimer()-int(apexSearch.started);
            apexSearch.publish_ms=flash.utils.getTimer()-started;ApexSearchLabels();return;
         }
         var selected:Array=apexSearch.feed.GetSelectedIndices();var selectedIds:Array=[];
         for each(var index:int in selected) {var item:Object=apexSearch.feed.RequestItemAt(index);if(item!=null) selectedIds.push(String(item.data_id));}
         if(apexSearch.selected!=null) for each(var id:String in apexSearch.selected) if(selectedIds.indexOf(id)<0) selectedIds.push(id);
         // A queued Enter must not select a different item after the same feed
         // object publishes a new search result at that old numeric index.
         apexSearch.feed.RemoveAllItems();apexSearch.feed.AddItemsFromIterable(products);
         apexSearch.feed.UpdateSelections(selectedIds,true);apexSearch.shown=products.length;
         apexSearch.rebuilds++;apexSearch.publish_ms=flash.utils.getTimer()-started;
         apexSearch.elapsed_ms=flash.utils.getTimer()-int(apexSearch.started);ApexSearchLabels();
      }

      private function ApexSearchFrame() : void
      {
         if(apexSearch==null) return;
         var panel:Object=mCurrentPanel;
         if(panel==null || !panel.visible || panel.mcFilterPane==null || !panel.mcFilterPane.visible ||
            panel.mcTileList==null || !panel.mcTileList.visible || apexEquippedActive) {ApexSearchRestore();return;}
         ApexSearchAttach(panel);
         ApexSearchAdopt(panel);
         if(apexSearch.context!=ApexSearchContext() || apexSearch.panel!==panel ||
            panel.mcTileList.mGridLayout.GetDataFeed()!==apexSearch.feed) {
            // Wait for a fresh native feed for this exact appearance. Never
            // reuse a previous member's rows or asynchronous search results.
            apexSearch.ticket="";apexSearch.page=null;apexSearch.pending=false;apexSearch.ready=false;return;
         }
         if(!apexSearch.pending || apexPendingFields!=null || apexReceiving) return;
         if(apexSearch.text=="") {apexSearch.pending=false;apexSearch.ready=true;ApexSearchPublish();return;}
         if(Boolean(CommunicationManager.CallUIService("IsUILoadingScreenVisible")) ||
            Boolean(CommunicationManager.CallUIService("IsModalVisible")) || Boolean(CommunicationManager.CallUIService("IsDialogModalVisible"))) return;
         var now:int=flash.utils.getTimer();if(now<int(apexSearch.due)) return;
         try {
            if(apexSearch.page!=null) {
               var rows:Array=apexSearch.page.items;
               if(int(apexSearch.index)<rows.length) {
                  // One native metadata resolution per idle frame. Preserve all
                  // 64 instance bits and confirm the game's actual base identity.
                  var row:Object=rows[int(apexSearch.index)];apexSearch.index++;
                  var tgi:Array=String(row.resource_tgi).split(":");
                  if(tgi.length!=3 || String(tgi[0]).toUpperCase()!="034AEECB" || !/^[0-9a-f]{16}$/i.test(tgi[2])) throw new Error("Invalid indexed CAS resource key");
                  var exact:String=ApexEquippedDecimal("0x"+tgi[2]);
                  var raw:Object=CommunicationManager.CallGameService("GetCatalogItem",exact);
                  if(raw!=null && (String(raw.data_id)==exact || String(raw.variation_id)==exact) && int(raw.body_type)==int(row.body_type))
                     apexSearch.matches[String(raw.body_type)+"|"+String(raw.data_id)]=true;
                  apexSearch.resolved++;return;
               }
               var next:Object=apexSearch.page.next_offset;apexSearch.page=null;apexSearch.ticket="";
               if(next==null) {apexSearch.pending=false;apexSearch.ready=true;ApexSearchPublish();return;}
               apexSearch.offset=int(next);
            }
            if(apexSearch.ticket=="") {
               apexSearch.query=ApexSearchQuery();
               var submitted:String=ApexNativeExchange("SEARCH|"+apexNativeChannel+"|"+ApexEncode(apexSearch.query));
               apexSearch.native_response=submitted.substr(0,900);
               if(submitted.indexOf("SEARCHERROR|")==0) throw new Error("Search unavailable: "+submitted.substr(12));
               if(!/^SEARCH\|[1-9][0-9]*$/.test(submitted)) throw new Error("Search worker unavailable; native items unchanged");
               apexSearch.ticket=submitted.substr(7);apexSearch.poll=now+50;return;
            }
            if(now<int(apexSearch.poll)) return;apexSearch.poll=now+50;
            var wire:String=ApexNativeExchange("SEARCHREAD|"+apexNativeChannel+"|"+apexSearch.ticket);
            if(wire.indexOf("SEARCHRESULT|")!=0) throw new Error("Search context changed; native items unchanged");
            var reply:Object=JSON.parse(wire.substr(13));
            if(String(reply.ticket)!=apexSearch.ticket || reply.ok!==true) throw new Error("Search unavailable; native items unchanged");
            if(reply.state=="pending") return;
            if(!(reply.items is Array) || reply.items.length>24 || reply.query==null) throw new Error("Search reply does not match the current query");
            var query:Object=ApexSearchQuery();
            for(var key:String in query) if(!reply.query.hasOwnProperty(key) || reply.query[key]!==query[key])
               throw new Error("Search reply does not match the current query");
            apexSearch.page=reply;apexSearch.index=0;apexSearch.total=int(reply.total);
         } catch(error:Error) {apexSearch.pending=false;apexSearch.ready=false;apexSearch.error=error.message;ApexSearchLabels();}
      }

      private function ApexSearchStatus() : Object
      {
         if(apexSearch==null) return {available:false};
         return {available:apexSearch.root!=null,text:apexSearch.text,context:apexSearch.context,ticket:apexSearch.ticket,
            pending:apexSearch.pending,ready:apexSearch.ready,error:apexSearch.error,matched:apexSearch.shown,
            indexed_matches:apexSearch.total,resolved:apexSearch.resolved,elapsed_ms:apexSearch.elapsed_ms,
            source_count:apexSearch.rows==null ? 0 : apexSearch.rows.length,query:apexSearch.query,
            native_response:apexSearch.native_response,publish_ms:apexSearch.publish_ms,rebuilds:apexSearch.rebuilds,appearance_written:false};
      }
