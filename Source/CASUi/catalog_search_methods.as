      // The search field lives in the native filter pane. The worker returns
      // metadata only; the retained native eligible feed is the sole source of
      // result cards. No result can synthesize a product or equip a part.
      private var apexSearch:Object;

      private function ApexSearchInitialize() : void
      {
         apexSearch={text:"",context:"",ticket:"",due:0,poll:0,rows:null,feed:null,panel:null,
            matches:{},offset:0,total:0,resolved:0,shown:0,ready:false,pending:false,error:"",page:null,index:0,
            root:null,input:null,placeholder:null,count:null,clear:null,bubble:null,list:null,geometry:null,
            registered:false,revision:0,started:0,elapsed_ms:0,sources:[],query:null,native_response:"",publish_ms:0,rebuilds:0,index_sha256:"",
            folder_matches:[],folder_corrected:false,suggestions:null,suggestion_signature:"",order:{},rank:0,
            eligible:{},families:{},unresolved_resources:[]};
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
            if(apexSearch.bubble!=null && apexSearch.bubble.y==g.bubble_y+52) apexSearch.bubble.y=g.bubble_y;
            if(apexSearch.list!=null && apexSearch.list.y==g.list_y+52) {
               apexSearch.list.y=g.list_y;
               if(apexSearch.list.height==g.list_height-52) apexSearch.list.height=g.list_height;
            }
         }
         if(apexSearch.root!=null && apexSearch.root.parent!=null) apexSearch.root.parent.removeChild(apexSearch.root);
         apexSearch.root=null;apexSearch.input=null;apexSearch.geometry=null;apexSearch.bubble=null;apexSearch.list=null;apexSearch.width=-1;
         apexSearch.suggestions=null;apexSearch.suggestion_signature="";
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
         apexSearch.order={};apexSearch.rank=0;
         apexSearch.unresolved_resources=[];
         apexSearch.index=0;apexSearch.offset=0;apexSearch.total=0;apexSearch.resolved=0;apexSearch.shown=0;
         apexSearch.ready=false;apexSearch.pending=apexSearch.text!="";apexSearch.error="";
         apexSearch.query=null;apexSearch.native_response="";apexSearch.index_sha256="";
         apexSearch.folder_matches=[];apexSearch.folder_corrected=false;
         apexSearch.due=flash.utils.getTimer()+180;apexSearch.revision++;apexSearch.started=flash.utils.getTimer();
      }

      private function ApexSearchSource(value:Object) : Object
      {
         if(value!=null && value.operation=="appearance-context") {
            // A UI-only identity lease for imported Companion tools. Never
            // let their timers mistake two named forms sharing an EA layer.
            if(mCurrSimInfo==null || String(mCurrSimInfo.simId)!==apexBoundSim ||
               apexFormsSelectedId=="" || apexFormsNativeGeneration=="" ||
               apexFormsNativeState!="bound" || apexFormsDesiredId!="" ||
               apexFormsNativeIntent!=null || apexMoleculeIntent!=null) return null;
            var lease:String=apexBoundSim+"|"+apexFormsSelectedId+"|"+apexFormsNativeGeneration;
            return {key:lease,sim:apexBoundSim,owner:apexFormsSelectedId,info:{
               simId:apexBoundSim,age:int(mCurrSimInfo.age),gender:int(mCurrSimInfo.gender),
               speciesType:int(mCurrSimInfo.speciesType),occultType:int(mCurrSimInfo.occultType),
               occultLayer:int(mCurrSimInfo.occultLayer),apexAppearanceLease:lease}};
         }
         if(value!=null && value.operation=="canine-context") {
            // A catalogue query only: preserve the actual Human geometry and
            // exact named owner. The game still filters age, sex and CC tags.
            var canineStates:Array=[MenuState.PROFILE_HEAD_WHOLE_HEADS,MenuState.PROFILE_HEAD_EARS,
               MenuState.PROFILE_HEAD_EYES,MenuState.PROFILE_HEAD_NOSE,MenuState.PROFILE_HEAD_MOUTH,
               MenuState.PROFILE_HEAD_CHEEK,MenuState.PROFILE_HEAD_CHIN,MenuState.PROFILE_HEAD_JAW,
               MenuState.PROFILE_HEAD_FOREHEAD,MenuState.PROFILE_BODY_FUR,MenuState.PROFILE_GENERIC_PELT];
            return {enabled:mCurrSimInfo!=null && String(mCurrSimInfo.simId)===apexBoundSim &&
               apexFormsSelectedId==="werewolf/werewolf_human_cc" &&
               apexFormsNativeState=="bound" && apexFormsDesiredId=="" && apexFormsNativeIntent==null &&
               canineStates.indexOf(int(value.state))>=0};
         }
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
            apexSearch.eligible={};apexSearch.families={};
            for each(var product:CASCatalogProduct in source.rows)
               apexSearch.eligible[String(product.body_type)+"|"+String(product.data_id)]=true;
            ApexSearchReset(ApexSearchContext());return;
         }
      }

      private function ApexSearchText(text:String) : void
      {
         if(text.length>160 || /[\x00-\x1f\x7f]/.test(text)) throw new Error("Search accepts up to 160 printable characters");
         if(apexSearch==null || apexSearch.input==null) throw new Error("Open a native item category with a filter bar first");
         apexSearch.text=text;
         // Assigning text again during CHANGE resets the caret/selection. Let
         // native typing keep its edit position; only CLI/clear replaces it.
         if(apexSearch.input.text!=text) apexSearch.input.text=text;
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
         ApexSearchSuggestions();
      }

      private function ApexSearchChooseFolder(event:flash.events.MouseEvent) : void
      {
         var at:int=int(String(event.currentTarget.name).substr(16));
         if(at<0 || at>=apexSearch.folder_matches.length) return;
         var folder:String=String(apexSearch.folder_matches[at]);
         if(folder.indexOf('"')>=0) return;
         var text:String=String(apexSearch.text);var match:Array=/\bfolder:(?:"[^"]*"|[^\s]+)/i.exec(text);
         if(match==null) return;
         var position:int=int(match.index);
         var next:String=text.substr(0,position)+'folder:"'+folder+'"'+text.substr(position+String(match[0]).length);
         if(next.length>160) {
            apexSearch.error="Use a shorter folder qualifier with this query";ApexSearchLabels();
            event.preventDefault();event.stopImmediatePropagation();return;
         }
         ApexSearchText(next);
         if(stage!=null) {stage.focus=apexSearch.input;apexSearch.input.setSelection(apexSearch.input.length,apexSearch.input.length);}
         event.preventDefault();event.stopImmediatePropagation();
      }

      private function ApexSearchSuggestions() : void
      {
         if(apexSearch.root==null) return;
         var show:Boolean=stage!=null && stage.focus===apexSearch.input && /\bfolder:/i.test(String(apexSearch.text)) && apexSearch.folder_matches.length>0;
         if(apexSearch.suggestions!=null) apexSearch.suggestions.visible=show;
         if(!show) return;
         var signature:String=apexSearch.folder_matches.join("\n")+"|"+apexSearch.width;
         if(signature==apexSearch.suggestion_signature) return;
         apexSearch.suggestion_signature=signature;
         if(apexSearch.suggestions!=null && apexSearch.suggestions.parent!=null) apexSearch.suggestions.parent.removeChild(apexSearch.suggestions);
         var root:flash.display.Sprite=new flash.display.Sprite();root.name="ApexFolderSuggestions";root.y=25;
         root.graphics.lineStyle(1,0x9dc6da);root.graphics.beginFill(0xf4fbff,0.99);
         root.graphics.drawRoundRect(0,0,Number(apexSearch.width),apexSearch.folder_matches.length*25+5,8,8);root.graphics.endFill();
         apexSearch.root.addChild(root);apexSearch.suggestions=root;
         for(var i:int=0;i<apexSearch.folder_matches.length;i++) {
            var row:flash.display.Sprite=new flash.display.Sprite();row.name="ApexFolderChoice"+i;row.y=3+i*25;row.buttonMode=true;row.mouseChildren=false;
            row.graphics.beginFill(0xffffff,0.01);row.graphics.drawRect(0,0,Number(apexSearch.width),25);row.graphics.endFill();
            ApexFormsText(row,String(apexSearch.folder_matches[i]),8,3,Number(apexSearch.width)-16,11,0x17527b);
            row.addEventListener(flash.events.MouseEvent.MOUSE_DOWN,ApexSearchChooseFolder,false,30,true);root.addChild(row);
         }
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
            // Use the same embedded game font as the other readable Apex CAS
            // labels. GFx cannot render system Arial in this game process.
            input.embedFonts=true;input.displayAsPassword=false;
            input.defaultTextFormat=new flash.text.TextFormat("$TextFont",12,0x17527b);
            input.height=23;input.x=8;input.y=2;input.text=apexSearch.text;root.addChild(input);apexSearch.input=input;
            input.addEventListener(flash.events.Event.CHANGE,ApexSearchChanged,false,0,true);
            input.addEventListener(flash.events.KeyboardEvent.KEY_DOWN,ApexSearchKey,false,30,true);
            input.addEventListener(flash.events.FocusEvent.FOCUS_IN,ApexSearchFocus,false,0,true);
            input.addEventListener(flash.events.FocusEvent.FOCUS_OUT,ApexSearchFocus,false,0,true);
            apexSearch.placeholder=ApexFormsText(root,"Search / folder: / author: / added:7d",8,4,180,11,0x376681);
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
         if(bubble.y!=g.bubble_y+52) g.bubble_y=bubble.y;
         if(list.y!=g.list_y+52) {g.list_y=list.y;g.list_height=list.height;}
         if(bubble.y!=g.bubble_y+52) bubble.y=g.bubble_y+52;
         if(list.y!=g.list_y+52) list.y=g.list_y+52;
         var height:Number=Math.max(32,g.list_height-52);
         if(list.height!=height) list.height=height;
         var width:Number=Math.max(180,Number(bubble.mcBackground.width));
         apexSearch.root.x=bubble.x;apexSearch.root.y=g.bubble_y+26;
         if(apexSearch.width!==width) {
            apexSearch.width=width;apexSearch.root.graphics.clear();apexSearch.root.graphics.lineStyle(1,0xc5e2e4,0.8);
            apexSearch.root.graphics.beginFill(0xe7f6f5,0.88);apexSearch.root.graphics.drawRoundRect(0,0,width,24,8,8);apexSearch.root.graphics.endFill();
            apexSearch.input.width=width-80;apexSearch.count.x=width-68;apexSearch.clear.x=width-25;
         }
         ApexSearchLabels();
      }

      private function ApexSearchQuery() : Object
      {
         // One parser in the offline worker handles quoted filters, exclusions,
         // wildcard filenames and dates. Typing never parses/scans packages.
         return {text:String(apexSearch.text),author:"",sort:"name",body_type:null,origin:null,name_mode:"preferred",
            offset:int(apexSearch.offset),limit:24,view:"all",grouped:false,fuzzy:true};
      }

      private function ApexSearchOrder(left:Object,right:Object) : Number
      {
         return Number(apexSearch.order[String(left.body_type)+"|"+String(left.data_id)])-Number(apexSearch.order[String(right.body_type)+"|"+String(right.data_id)]);
      }

      private function ApexSearchPublish() : void
      {
         var started:int=flash.utils.getTimer();
         if(apexSearch.context!=ApexSearchContext() || apexSearch.panel!==mCurrentPanel || apexSearch.rows==null ||
            mCurrentPanel==null || mCurrentPanel.mcTileList.mGridLayout.GetDataFeed()!==apexSearch.feed || apexEquippedActive) return;
         var products:Array=[];
         for each(var product:CASCatalogProduct in apexSearch.rows)
            if((apexSearch.text=="" || apexSearch.matches[String(product.body_type)+"|"+product.data_id]===true) && ApexCompanionAllows(product)) products.push(product);
         if(apexCompanion!=null && apexCompanion.mode=="recent") products.sort(ApexCompanionRecentOrder);
         else if(apexSearch.text!="") products.sort(ApexSearchOrder);
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
         if(panel==null || !panel.visible || !("mcFilterPane" in panel) || panel.mcFilterPane==null || !panel.mcFilterPane.visible ||
            !("mcTileList" in panel) || panel.mcTileList==null || !panel.mcTileList.visible || apexEquippedActive) {ApexSearchRestore();return;}
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
               var sliceStart:int=flash.utils.getTimer();var sliceCount:int=0;
               while(int(apexSearch.index)<rows.length && sliceCount<8 && flash.utils.getTimer()-sliceStart<2) {
                  // Bounded idle slices avoid a frame of latency per swatch.
                  // Preserve all 64 bits and confirm the actual native base.
                  var row:Object=rows[int(apexSearch.index)];apexSearch.index++;
                  var tgi:Array=String(row.resource_tgi).split(":");
                  if(tgi.length!=3 || String(tgi[0]).toUpperCase()!="034AEECB" || !/^[0-9a-f]{16}$/i.test(tgi[2])) throw new Error("Invalid indexed CAS resource key");
                  var exact:String=ApexEquippedDecimal("0x"+tgi[2]);
                  var raw:Object=CommunicationManager.CallGameService("GetCatalogItem",exact);
                  var resolvedKey:String=ApexSearchNativeKey(raw,exact,row.body_type);
                  if(resolvedKey!="") {
                     if(apexSearch.matches[resolvedKey]!==true) apexSearch.order[resolvedKey]=apexSearch.rank++;
                     apexSearch.matches[resolvedKey]=true;
                  } else if(apexSearch.unresolved_resources.length<8) {
                     apexSearch.unresolved_resources.push({resource:exact,body_type:row.body_type,
                        native_base:raw==null ? "" : String(raw.data_id),native_variant:raw==null ? "" : String(raw.variation_id)});
                  }
                  apexSearch.resolved++;sliceCount++;
               }
               if(int(apexSearch.index)<rows.length) return;
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
            var wire:String=ApexNativeExchange("SEARCHPAGE|"+apexNativeChannel+"|"+apexSearch.ticket);
            if(wire=="SEARCHWAIT|"+apexSearch.ticket) return;
            if(wire.indexOf("SEARCHERROR|")==0) throw new Error("Search unavailable: "+wire.substr(12));
            if(wire.length>4096) throw new Error("Search reply exceeds its bound");
            var fields:Array=wire.split("|");
            if((fields.length!=7 && fields.length!=9) || fields[0]!="SEARCHPAGE" || fields[1]!=apexSearch.ticket ||
               !/^[0-9a-f]{64}$/i.test(fields[2]) || !/^[0-9]{1,7}$/.test(fields[3]) ||
               !/^[0-9]{1,7}$/.test(fields[4]) || int(fields[4])!=int(apexSearch.offset) ||
               int(fields[3])>2000000 || int(fields[4])>int(fields[3]))
               throw new Error("Search reply does not match the current query");
            if(fields.length==9) {
               if(fields[8]!="0" && fields[8]!="1") throw new Error("Invalid folder suggestion flag");
               var folders:Array=fields[7]=="" ? [] : String(fields[7]).split(";");
               if(folders.length>5) throw new Error("Too many folder suggestions");
               for(var folderAt:int=0;folderAt<folders.length;folderAt++) {
                  folders[folderAt]=decodeURIComponent(String(folders[folderAt]));
                  if(String(folders[folderAt]).length>512 || /[\x00-\x1f\x7f]/.test(String(folders[folderAt]))) throw new Error("Invalid indexed folder name");
               }
               apexSearch.folder_matches=folders;apexSearch.folder_corrected=fields[8]=="1";ApexSearchLabels();
            }
            if(apexSearch.index_sha256!="" && apexSearch.index_sha256!=fields[2])
               throw new Error("Search index changed; clear or repeat the query");
            var items:Array=[];var encoded:Array=fields[6]=="" ? [] : String(fields[6]).split(";");
            if(encoded.length>24) throw new Error("Search reply has too many items");
            for each(var resource:String in encoded) {
               var parts:Array=resource.split(",");
               if(parts.length!=2 || !/^034AEECB:[0-9a-f]{8}:[0-9a-f]{16}$/i.test(parts[0]) ||
                  !(parts[1]=="-" || /^[0-9]{1,10}$/.test(parts[1]) && Number(parts[1])<=2147483647))
                  throw new Error("Search reply contains an invalid resource");
               items.push({resource_tgi:parts[0],body_type:parts[1]=="-" ? null : int(parts[1])});
            }
            var nextOffset:int=int(fields[4])+items.length;
            if(nextOffset>int(fields[3]) || (nextOffset==int(fields[3]) ? fields[5]!="-" :
               items.length==0 || String(nextOffset)!=fields[5])) throw new Error("Search reply pagination differs");
            apexSearch.index_sha256=fields[2];apexSearch.index=0;apexSearch.total=int(fields[3]);
            apexSearch.page={items:items,next_offset:fields[5]=="-" ? null : nextOffset};
         } catch(error:Error) {apexSearch.pending=false;apexSearch.ready=false;apexSearch.error=error.message;ApexSearchLabels();}
      }

      private function ApexSearchNativeKey(raw:Object,exact:String,bodyType:Object) : String
      {
         if(raw==null || bodyType==null || int(raw.body_type)!=int(bodyType)) return "";
         var key:String=String(raw.body_type)+"|"+String(raw.data_id);
         if(apexSearch.eligible[key]===true && (String(raw.data_id)==exact || String(raw.variation_id)==exact)) return key;
         // The native getter can return the worn swatch itself. Its color
         // family contains the separate base used by the visible native feed.
         // Intersect that exact family with eligible cards; an ambiguous or
         // absent parent cannot synthesize a card. Cache detached IDs only.
         if(apexSearch.families[key]==null) {
            var family:Object=CommunicationManager.CallGameService("GetCatalogColorFamilies",
               {base:String(raw.data_id),simId:"0",targetSimId:"0"});
            var ids:Object={};var parent:String="";var count:int=0;
            if(family!=null && family.mItems is Array && family.mItems.length<=8192)
               for each(var variant:Object in family.mItems) if(variant!=null) {
                  var id:String=String(variant.dataID);var candidate:String=String(raw.body_type)+"|"+id;
                  if(ids[id]!==true && apexSearch.eligible[candidate]===true) {parent=candidate;count++;}
                  ids[id]=true;
               }
            var resolved:Object={ids:ids,parent:count==1 ? parent : ""};
            apexSearch.families[key]=resolved;
            for(var alias:String in ids) apexSearch.families[String(raw.body_type)+"|"+alias]=resolved;
         }
         var cached:Object=apexSearch.families[key];
         return cached.ids[exact]===true ? String(cached.parent) : "";
      }

      private function ApexSearchStatus() : Object
      {
         if(apexSearch==null) return {available:false};
         return {available:apexSearch.root!=null,text:apexSearch.text,context:apexSearch.context,ticket:apexSearch.ticket,
            pending:apexSearch.pending,ready:apexSearch.ready,error:apexSearch.error,matched:apexSearch.shown,
            indexed_matches:apexSearch.total,resolved:apexSearch.resolved,elapsed_ms:apexSearch.elapsed_ms,
            folder_matches:apexSearch.folder_matches,folder_corrected:apexSearch.folder_corrected,
            source_count:apexSearch.rows==null ? 0 : apexSearch.rows.length,query:apexSearch.query,
            unresolved_resources:apexSearch.unresolved_resources,
            native_response:apexSearch.native_response,publish_ms:apexSearch.publish_ms,rebuilds:apexSearch.rebuilds,
            index_sha256:apexSearch.index_sha256,input_font:apexSearch.input==null ? "" : apexSearch.input.defaultTextFormat.font,
            input_embedded:apexSearch.input!=null && apexSearch.input.embedFonts,
            input_password:apexSearch.input!=null && apexSearch.input.displayAsPassword,
            input_text:apexSearch.input==null ? "" : apexSearch.input.text,
            input_text_width:apexSearch.input==null ? 0 : apexSearch.input.textWidth,appearance_written:false};
      }
