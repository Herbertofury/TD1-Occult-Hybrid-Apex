      // Shared layout metadata belongs to one of the six exact UI controls.
      // It contains UI references and primitive geometry, never Sim/model rows.
      private function ApexCatalogListSlot(panel:Object) : int {
         if(panel===mcClothingPanel)return 0;
         if(panel===mcBodyModPanel)return 1;
         if(panel===mcFaceModPanel)return 2;
         if(panel===mcGenericCatalogPanel)return 3;
         if(panel===mcFeaturedFaceLookPanel)return 4;
         if(panel===mcSkinColorPanel)return 5;
         return -1;
      }

      private function ApexCatalogListCurrent(r:Object) : Boolean {
         if(apexSearch==null || apexSearch.list_layouts==null || r==null || r.protocol!==1 || r.active!==true || stage==null ||
            r.stage!==stage || r.panel==null || r.list==null || r.panel.stage!==stage || r.list.stage!==stage ||
            r.panel.mcTileList!==r.list || r.list.mcBackground!==r.background ||
            r.list.mScrollerView!==r.view || r.list.mSlider!==r.slider || r.list.GetGridView()!==r.grid_view ||
            !(r.type is Class) || !(r.list is r.type))return false;
         var slot:int=ApexCatalogListSlot(r.panel);
         return slot>=0 && apexSearch.list_layouts[slot]===r;
      }

      private function ApexCatalogListRecord(panel:Object,list:Object) : Object {
         var slot:int=ApexCatalogListSlot(panel);
         if(slot<0 || apexSearch==null || stage==null || panel.stage!==stage || list==null ||
            panel.mcTileList!==list || list.stage!==stage || list.mcBackground==null ||
            list.mScrollerView==null || list.mSlider==null || !(list.GetGridView is Function))return null;
         if(apexSearch.list_layouts==null)apexSearch.list_layouts=[null,null,null,null,null,null];
         var old:Object=apexSearch.list_layouts[slot];
         if(ApexCatalogListCurrent(old))return old;
         if(old!=null)old.active=false;
         // Exact exported native factories, including the game's symbol class.
         // A replacement/custom subclass keeps the original uncomposed route.
         var type:Class=null;var name:String=flash.utils.getQualifiedClassName(list);
         if(name=="olympus.controls::ScrollList")type=getDefinitionByName("olympus.controls.ScrollList") as Class;
         else if(name=="olympus.gui.lists::ScrollList")type=getDefinitionByName("olympus.gui.lists.ScrollList") as Class;
         if(type==null || !(list is type) || flash.utils.getQualifiedClassName(type)!==name)return null;
         if(!("ApexRawListBaseline" in panel) || !(panel.ApexRawListBaseline is Function))return null;
         var raw:Object=panel.ApexRawListBaseline();
         if(raw==null || raw.protocol!==1 || raw.panel!==panel || raw.list!==list || raw.stage!==stage ||
            !(raw.generation is int) || int(raw.generation)<1 || !isFinite(Number(raw.y)) ||
            !isFinite(Number(raw.height)) || Number(raw.height)<=0)return null;
         var y:Number=Number(raw.y);var h:Number=Number(raw.height);
         var r:Object={protocol:1,active:true,panel:panel,list:list,stage:stage,type:type,
            background:list.mcBackground,view:list.mScrollerView,slider:list.mSlider,grid_view:list.GetGridView(),
            raw_y:y,raw_height:h,native_generation:int(raw.generation),search:0,rail:0,rail_view:null,receipt:null,applying:false,blocked:false,pending_native:null,
            apply:ApexCatalogListApply,set_rail:ApexCatalogListRail,current:ApexCatalogListCurrent,
            applied_y:y,applied_height:h,rail_y:y,last_error:""};
         apexSearch.list_layouts[slot]=r;
         // Native setup can create the real rail before Main registers its UI
         // service. Adopt only a private native-state receipt bound to the SAME
         // raw witness; never subtract guessed offsets from current pixels.
         var donor:Class=null;
         try {donor=getDefinitionByName("dcc.catalog.BodyTypeTabs") as Class;}
         catch(missing:Error) {donor=null;}
         if(donor!=null && "ApexNativeRailReceipt" in donor && donor.ApexNativeRailReceipt is Function) {
            var preceding:Object=donor.ApexNativeRailReceipt(panel,list);
            if(preceding!=null && preceding.protocol===1 && preceding.panel===panel && preceding.list===list && preceding.stage===stage &&
               preceding.generation===r.native_generation && preceding.raw_y===r.raw_y && preceding.raw_height===r.raw_height &&
               (preceding.rail===68 || preceding.rail===128) && preceding.rail_view!=null &&
               preceding.rail_view.parent===panel && preceding.rail_view.stage===stage &&
               Number(list.y)===preceding.native_y && Number(list.height)===preceding.native_height) {
               r.rail=Number(preceding.rail);r.rail_view=preceding.rail_view;r.receipt={generation:r.native_generation,y:r.raw_y+r.rail,height:r.raw_height-r.rail,
                  native_y:Number(preceding.native_y),native_height:Number(preceding.native_height)};
               r.applied_y=Number(preceding.native_y);r.applied_height=Number(preceding.native_height);
            }
         }
         return r;
      }

      private function ApexCatalogListApply(r:Object) : Boolean {
         if(!ApexCatalogListCurrent(r) || r.applying || r.blocked===true || !isFinite(Number(r.raw_y)) ||
            !isFinite(Number(r.raw_height)) || Number(r.raw_height)<=0 ||
            (r.search!==0 && r.search!==52) || !isFinite(Number(r.rail)) || Number(r.rail)<0)return false;
         var nativeRail:Object=r.rail_view;
         if(Number(r.rail)>0 && (nativeRail==null || nativeRail.parent!==r.panel || nativeRail.stage!==stage ||
            flash.utils.getQualifiedClassName(nativeRail)!=="flash.display::Sprite"))return false;
         var witness:int=int(r.panel.ApexRawListGeneration());
         if(witness!==int(r.native_generation))return false;
         var y:Number=Number(r.raw_y)+Number(r.rail)+Number(r.search);
         var h:Number=Math.max(32,Number(r.raw_height)-Number(r.rail)-Number(r.search));
         var projectedY:Number=Math.round(y*20)/20;var projectedH:Number=Math.round(h*20)/20;
         var railY:Number=Math.round((Number(r.raw_y)+Number(r.search))*20)/20;
         var receipt:Object=r.receipt;var list:Object=r.list;
         if(receipt!=null && receipt.generation===r.native_generation && receipt.y===y && receipt.height===h &&
            receipt.native_y===Number(list.y) && receipt.native_height===Number(list.height) &&
            (Number(r.rail)===0 || Number(nativeRail.y)===railY))return true;
         var generation:int=int(r.native_generation);var rail:Number=Number(r.rail);var search:int=int(r.search);
         var rawY:Number=Number(r.raw_y);var rawH:Number=Number(r.raw_height);
         var oldY:Number=Number(list.y);var oldH:Number=Number(list.height);var done:Boolean=false;
         var text:Object=r.panel===mcClothingPanel ? r.panel.txtNoResults : null;
         var oldTextY:Number=text==null ? 0 : Number(text.y);
         var ownText:Boolean=text!=null && (oldTextY===oldY || (receipt!=null && oldTextY===Number(receipt.native_y)));
         // The only allowed preimage is the last complete acknowledged result
         // or the authoritative raw native refresh. Never adopt an arbitrary
         // external position as an already-uninset baseline.
         var raw:Boolean=Number(list.y)===Number(r.raw_y) && Number(list.height)===Number(r.raw_height);
         var owned:Boolean=receipt!=null && Number(list.y)===receipt.native_y && Number(list.height)===receipt.native_height;
         if(!raw && !owned) {r.last_error="External native list geometry requires a fresh native baseline";r.blocked=true;return false;}
         r.applying=true;
         try {
            if(Number(list.y)!==projectedY)list.y=y;
            if(!ApexCatalogListCurrent(r) || r.native_generation!==generation || r.raw_y!==rawY || r.raw_height!==rawH || r.rail!==rail || r.search!==search ||
               r.rail_view!==nativeRail || int(r.panel.ApexRawListGeneration())!==witness || Number(list.y)!==projectedY)return false;
            if(Number(list.height)!==projectedH)list.height=h;
            if(!ApexCatalogListCurrent(r) || r.native_generation!==generation || r.raw_y!==rawY || r.raw_height!==rawH || r.rail!==rail || r.search!==search ||
               r.rail_view!==nativeRail || int(r.panel.ApexRawListGeneration())!==witness || Number(list.y)!==projectedY || Number(list.height)!==projectedH)return false;
            if(rail>0) {
               if(nativeRail.parent!==r.panel || nativeRail.stage!==stage)return false;
               if(Number(nativeRail.y)!==railY)nativeRail.y=railY;
            }
            r.receipt={generation:generation,y:y,height:h,native_y:Number(list.y),native_height:Number(list.height)};
            r.applied_y=Number(list.y);r.applied_height=Number(list.height);r.rail_y=railY;r.last_error="";
            if(ownText && r.panel.txtNoResults===text && Number(text.y)===oldTextY)text.y=r.applied_y;
            done=true;return true;
         } finally {
            r.applying=false;
            if(!done) {
               r.last_error="Native list composition was interrupted; awaiting a fresh native baseline";
               // Only undo our own y write when the complete preimage/epoch is
               // still current and the second dimension was never changed.
               // A reentrant new owner/baseline or arbitrary foreign edit wins.
               if(ApexCatalogListCurrent(r) && r.native_generation===generation && r.raw_y===rawY && r.raw_height===rawH &&
                  r.rail===rail && r.search===search && int(r.panel.ApexRawListGeneration())===witness &&
                  Number(list.y)===projectedY && Number(list.height)===oldH && oldY!==projectedY)
                  list.y=oldY;
               if(r.native_generation===generation)r.blocked=true;
            }
            // A genuine native refresh can reenter either dimension setter.
            // Retain its authoritative witness, then resume on the next normal
            // Layout/Search call; never recursively apply or overwrite it here.
            var pending:Object=r.pending_native;r.pending_native=null;
            if(pending!=null && ApexCatalogListCurrent(r) && pending.generation>int(r.native_generation) &&
               int(r.panel.ApexRawListGeneration())===int(pending.generation)) {
               r.raw_y=Number(pending.y);r.raw_height=Number(pending.height);r.native_generation=int(pending.generation);
               r.receipt=null;r.blocked=false;
            }
         }
      }

      private function ApexCatalogListRail(r:Object,height:Number,rail:Object=null) : Boolean {
         if(!ApexCatalogListCurrent(r) || r.applying || !isFinite(height) || height<0 ||
            (height!==0 && height!==68 && height!==128))return false;
         if(height>0 && (rail==null || rail.parent!==r.panel || rail.stage!==stage ||
            flash.utils.getQualifiedClassName(rail)!=="flash.display::Sprite"))return false;
         r.rail=height;if(height>0)r.rail_view=rail;
         var applied:Boolean=ApexCatalogListApply(r);
         if(applied && height===0)r.rail_view=null;
         return applied;
      }

      private function ApexCatalogListGeometry(value:Object) : Object {
         if(value==null || (value.operation!=="lookup" && value.operation!=="native-base"))return null;
         var r:Object=ApexCatalogListRecord(value.panel,value.list);
         if(r==null)return null;
         if(value.operation=="native-base") {
            // A private native witness is written only by the exact original
            // raw assignment boundary. Repeated bridge calls cannot relabel
            // already-composed pixels as an authoritative baseline.
            var raw:Object=r.panel.ApexRawListBaseline();
            if(raw==null || raw.protocol!==1 || raw.panel!==r.panel || raw.list!==r.list || raw.stage!==stage ||
               !(raw.generation is int) || int(raw.generation)<int(r.native_generation) || raw.generation!==value.generation ||
               !isFinite(Number(raw.y)) || !isFinite(Number(raw.height)) || Number(raw.height)<=0)return null;
            if(r.applying) {
               if(int(raw.generation)>int(r.native_generation))r.pending_native={generation:int(raw.generation),y:Number(raw.y),height:Number(raw.height)};
               return r;
            }
            if(int(raw.generation)>int(r.native_generation) || (r.receipt==null && r.blocked!==true)) {
               r.raw_y=Number(raw.y);r.raw_height=Number(raw.height);r.native_generation=int(raw.generation);
               r.receipt=null;r.blocked=false;ApexCatalogListApply(r);
            }
         }
         return ApexCatalogListCurrent(r) ? r : null;
      }

      private function ApexCatalogSearchListApply(panel:Object,list:Object,g:Object) : Boolean {
         var r:Object=ApexCatalogListRecord(panel,list);
         if(r==null)return false;
         g.list_layout=r;
         r.search=52;
         if(!ApexCatalogListApply(r))return true;
         g.list_y=Number(r.raw_y)+Number(r.rail);g.list_height=Number(r.raw_height)-Number(r.rail);
         return true;
      }

      private function ApexCatalogSearchListRestore(g:Object) : Boolean {
         var r:Object=g==null ? null : g.list_layout;
         if(!ApexCatalogListCurrent(r))return false;
         r.search=0;
         return ApexCatalogListApply(r);
      }

      // Explicit status only. Never called from a frame/layout/input handler.
      private function ApexCatalogListRect(display:Object,target:Object,space:String) : Object {
         if(display==null || target==null || stage==null || display.stage!==stage || !(display.getBounds is Function))
            return {available:false,space:space};
         try {
            var bounds:Object=display.getBounds(target);
            if(bounds==null || !isFinite(Number(bounds.x)) || !isFinite(Number(bounds.y)) ||
               !isFinite(Number(bounds.width)) || !isFinite(Number(bounds.height)))return {available:false,space:space};
            return {available:true,space:space,source:"native-getBounds",x:Number(bounds.x),y:Number(bounds.y),
               width:Number(bounds.width),height:Number(bounds.height),visible:display.visible===true,
               mouse_enabled:display.mouseEnabled===true,mouse_children:display.mouseChildren===true};
         } catch(error:Error) {return {available:false,space:space,error:String(error.message).substr(0,160)};}
      }

      private function ApexCatalogListStatus() : Object {
         var panel:Object=mCurrentPanel;var slot:int=ApexCatalogListSlot(panel);
         var r:Object=apexSearch==null || apexSearch.list_layouts==null || slot<0 ? null : apexSearch.list_layouts[slot];
         var list:Object=panel==null || !("mcTileList" in panel) ? null : panel.mcTileList;
         var out:Object={protocol:1,diagnostic_only:true,appearance_written:false,
            admitted:ApexCatalogListCurrent(r),record_present:r!=null,local_space:"panel-local",stage_space:"stage"};
         if(r!=null) {
            out.active=r.active===true;out.blocked=r.blocked===true;out.applying=r.applying===true;
            out.raw={y:Number(r.raw_y),height:Number(r.raw_height),native_generation:int(r.native_generation)};
            out.insets={search:Number(r.search),rail:Number(r.rail),rail_y:Number(r.rail_y)};
            out.applied={y:Number(r.applied_y),height:Number(r.applied_height)};
            out.refusal=r.last_error==null ? "" : String(r.last_error).substr(0,160);
            var receipt:Object=r.receipt;
            out.receipt=receipt==null ? null : {native_generation:int(receipt.generation),requested_y:Number(receipt.y),
               requested_height:Number(receipt.height),native_y:Number(receipt.native_y),native_height:Number(receipt.native_height)};
            var pending:Object=r.pending_native;
            out.pending=pending==null ? null : {native_generation:int(pending.generation),y:Number(pending.y),height:Number(pending.height)};
         }
         if(list!=null) {
            out.list_class=flash.utils.getQualifiedClassName(list);
            out.current={y:Number(list.y),height:Number(list.height),width:Number(list.width),visible:list.visible===true,
               stage_matches:list.stage===stage,record_matches:r!=null && r.list===list};
            if(panel.ApexRawListGeneration is Function)out.native_witness_generation=int(panel.ApexRawListGeneration());
         }
         var search:Object=apexSearch==null || apexSearch.list!==list ? null : apexSearch.root;
         var bubble:Object=panel==null || !("mcFilterPane" in panel) || panel.mcFilterPane==null ? null : panel.mcFilterPane.mcFilterBubble;
         var rail:Object=r==null ? null : r.rail_view;
         var mask:Object=list==null || list.mScrollerView==null ? null : list.mScrollerView.mcMask;
         out.search={local:ApexCatalogListRect(search,panel,"panel-local"),stage:ApexCatalogListRect(search,stage,"stage")};
         out.filter={local:ApexCatalogListRect(bubble,panel,"panel-local"),stage:ApexCatalogListRect(bubble,stage,"stage")};
         out.rail={local:ApexCatalogListRect(rail,panel,"panel-local"),stage:ApexCatalogListRect(rail,stage,"stage")};
         out.mask={local:ApexCatalogListRect(mask,panel,"panel-local"),stage:ApexCatalogListRect(mask,stage,"stage")};
         return out;
      }
