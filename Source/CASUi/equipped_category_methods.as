      // A view of the CURRENT native outfit, not another appearance or catalog.
      private var apexEquippedActive:Boolean=false;
      private var apexEquippedOpening:Boolean=false;
      private var apexEquippedProducts:Array;
      private var apexEquippedBindings:Array;
      private var apexEquippedIndex:int=0;
      private var apexEquippedRefreshPending:Boolean=false;
      private var apexEquippedDirty:Boolean=false;
      private var apexEquippedInteraction:Object;
      private var apexEquippedServices:Boolean=false;
      private var apexEquippedUnresolved:Array;
      private var apexCatalogPerformance:Array;
      private var apexCatalogFrameTiming:Object;
      private var apexEquippedTiming:Object;
      private var apexEquippedRetirePending:Boolean=false;
      private var apexEquippedPublication:Object;

      private function ApexEquippedInitialize() : void
      {
         apexEquippedProducts=[];apexEquippedBindings=[];apexEquippedUnresolved=[];
         apexCatalogPerformance=[];apexCatalogFrameTiming={samples:0,total_ms:0,max_ms:0,over_1ms:0,layout_max_ms:0,binding_max_ms:0};
         if(apexEquippedServices) return;
         RegisterServiceHandler("ApexEquippedRefresh",ApexEquippedRefresh);
         RegisterServiceHandler("ApexEquippedPrepare",ApexEquippedPrepare);
         RegisterServiceHandler("ApexEquippedClick",ApexEquippedClick);
         RegisterServiceHandler("ApexCatalogPerformance",ApexCatalogPerformance);
         AddMessageListener("CASContextMenuSetMenuState",ApexEquippedNavigation);
         AddMessageListener("CASChangeMenuState",ApexEquippedNavigation);
         apexEquippedServices=true;
      }

      private function ApexEquippedDispose() : void
      {
         if(apexEquippedServices) {
            UnregisterServiceHandler("ApexEquippedRefresh",ApexEquippedRefresh);
            UnregisterServiceHandler("ApexEquippedPrepare",ApexEquippedPrepare);
            UnregisterServiceHandler("ApexEquippedClick",ApexEquippedClick);
            UnregisterServiceHandler("ApexCatalogPerformance",ApexCatalogPerformance);
            RemoveMessageListener("CASContextMenuSetMenuState",ApexEquippedNavigation);
            RemoveMessageListener("CASChangeMenuState",ApexEquippedNavigation);
         }
         apexEquippedServices=false;apexEquippedActive=false;apexEquippedInteraction=null;
         apexEquippedProducts=[];apexEquippedBindings=[];apexEquippedUnresolved=[];
      }

      private function ApexEquippedNavigation(value:Object=null) : void
      {
         // Native user navigation retires this view. No catalog fetch on clicks.
         if(!apexEquippedOpening && apexEquippedActive) {
            apexEquippedActive=false;apexEquippedInteraction=null;apexEquippedRetirePending=true;
         }
      }

      private function ApexCatalogPerformance(value:Object=null) : Object
      {
         if(value==null) return null;
         var sample:Object={};
         for each(var key:String in ["state","count","clear_ms","native_ms","construct_ms","bind_ms","selected_ms"])
            if(typeof value[key]!="number" || !isFinite(value[key])) return null;
            else sample[key]=Number(value[key]);
         apexCatalogPerformance.push(sample);
         if(apexCatalogPerformance.length>32) apexCatalogPerformance.shift();
         return null;
      }

      private function ApexEquippedRefresh(value:Object) : Object
      {
         if(value==null || value.panel!==mcClothingPanel) return null;
         if(!apexEquippedActive) {apexEquippedRetirePending=false;return null;}
         // EA invokes Refresh while entering the next state, before its menu
         // listener returns. Never intercept an unrelated native category.
         if(int(mNextState)!=MenuState.CLOTHING_SHOES) {
            apexEquippedActive=false;apexEquippedInteraction=null;apexEquippedRetirePending=false;
            return null;
         }
         if(mCurrSimInfo==null || apexCatalogContext!=String(mCurrSimInfo.simId)+"|"+apexFormsSelectedId) {
            apexEquippedActive=false;apexEquippedInteraction=null;apexEquippedRetirePending=true;
            return {active:true,products:[],reset:true,complete:true,timing:apexEquippedTiming,commit:{}};
         }
         // Publish at most ONE native card per frame. The native ADD event
         // draws thumbnails synchronously; one bulk event stalled the UI.
         // Only the adapter commits after the native feed and layout succeed.
         var reset:Boolean=apexEquippedPublication.reset===true ||
            apexEquippedPublication.feed!==value.feed || int(value.feed.length)!=int(apexEquippedPublication.count);
         var start:int=reset ? 0 : int(apexEquippedPublication.count);
         var end:int=Math.min(start+1,apexEquippedProducts.length);
         return {active:true,products:apexEquippedProducts.slice(start,end),reset:reset,
            complete:apexEquippedIndex>=apexCatalogItems.length && end>=apexEquippedProducts.length,
            total:apexCatalogItems.length,timing:apexEquippedTiming,commit:apexEquippedPublication};
      }

      private function ApexEquippedOpen() : void
      {
         var started:int=flash.utils.getTimer();
         ApexCatalogReadEquipped();
         apexEquippedTiming={read_ms:flash.utils.getTimer()-started,resolve_max_ms:0,clear_ms:0,bind_ms:0,selected_ms:0,layout_ms:0,
            chunks:0,bind_total_ms:0,bind_max_ms:0,publish_max_ms:0,chunk_max_count:0};
         apexEquippedPublication={reset:true,count:0,feed:null};
         apexEquippedProducts=[];apexEquippedBindings=[];apexEquippedUnresolved=[];
         apexEquippedIndex=0;apexEquippedInteraction=null;apexEquippedActive=true;apexEquippedDirty=false;apexEquippedRetirePending=false;
         if(apexCatalogUi!=null) apexCatalogUi.visible=false;
         apexEquippedOpening=true;
         try {
            HandleContextMenuSetMenuState({menuState:MenuState.CLOTHING_SHOES,skipAnim:true,setZoomState:false});
            CommunicationManager.SendUIMessage("CASChangeMenuState",MenuState.CLOTHING_SHOES);
            mcClothingPanel.Refresh(MenuState.CLOTHING_SHOES);
         } finally {apexEquippedOpening=false;}
         apexEquippedRefreshPending=true;
      }

      private function ApexEquippedFrame() : void
      {
         if(apexEquippedRetirePending) {
            apexEquippedRetirePending=false;
            if(mCurrentPanel===mcClothingPanel && mCurrState==MenuState.CLOTHING_SHOES) {
               RefreshFilterPane(mcClothingPanel,mCurrState,true);
               mcClothingPanel.Refresh(mCurrState);
            }
         }
         if(!apexEquippedActive) return;
         if(mCurrSimInfo==null || apexCatalogContext!=String(mCurrSimInfo.simId)+"|"+apexFormsSelectedId ||
            mCurrentPanel!==mcClothingPanel || mCurrState!=MenuState.CLOTHING_SHOES) {
            apexEquippedActive=false;apexEquippedInteraction=null;apexEquippedRetirePending=true;return;
         }
         if(apexEquippedDirty) {
            ApexCatalogReadEquipped();apexEquippedProducts=[];apexEquippedBindings=[];
            apexEquippedUnresolved=[];apexEquippedIndex=0;apexEquippedRefreshPending=true;apexEquippedDirty=false;
            apexEquippedPublication={reset:true,count:0,feed:null};apexEquippedInteraction=null;
         }
         // Resolve one EQUIPPED slot per idle frame, never scan the installed CC
         // library or construct thousands of products on the radial click.
         if(apexEquippedIndex<apexCatalogItems.length) {
            var row:Object=apexCatalogItems[apexEquippedIndex++];
            var resolveStarted:int=flash.utils.getTimer();
            try {ApexEquippedResolve(row);} catch(error:Error) {
               apexEquippedUnresolved.push({part_key:row.part_key,body_type:row.body_type,reason:error.message});
            }
            apexEquippedTiming.resolve_max_ms=Math.max(apexEquippedTiming.resolve_max_ms,flash.utils.getTimer()-resolveStarted);
            apexEquippedRefreshPending=true;
         }
         if(apexEquippedRefreshPending) {
            mcClothingPanel.Refresh(MenuState.CLOTHING_SHOES);
            apexEquippedRefreshPending=apexEquippedIndex<apexCatalogItems.length ||
               apexEquippedPublication.reset===true || int(apexEquippedPublication.count)<apexEquippedProducts.length;
         }
      }

      private function ApexEquippedResolve(row:Object) : void
      {
         if(int(row.menu_state)==0) throw new Error("No native category route; retained in the text list");
         var layer:Object=null;var index:int=-1;
         if(MenuState.SupportsLayerList(int(row.menu_state))) {
            var layers:Array=CASAPI.GetBodyTypeLayers(int(row.body_type));
            if(layers==null || layers.length>32) throw new Error("Native equipped layers unavailable");
            for(var i:int=0;i<layers.length;i++)
               if(ApexEquippedKey(String(layers[i].partKey))==ApexEquippedKey(String(row.part_key))) {
                  if(layer!=null) throw new Error("Ambiguous duplicate layered part");
                  index=i;layer={layer_index:i,layer_id:int(layers[i].layerId)};
               }
            if(layer==null || int(layer.layer_id)!=int(row.layer)) throw new Error("Equipped layer identity differs");
         }
         var ids:Array=CASAPI.GetCatalogBaseItemSelected(int(row.menu_state),[],[],int(row.body_type),index);
         row.selected_catalog_ids=ids;
         var selected:Array=[];
         if(ids!=null) for each(var id:Object in ids) if(String(id)!="0") selected.push(String(id));
         // The native selected getter includes empty slots and hides default
         // nail parts. Query the exact equipped instance without any active
         // catalog filters; verify the native product/variation identity.
         var exact:String=ApexEquippedDecimal(String(row.part_key));
         var raw:Object=CommunicationManager.CallGameService("GetCatalogItem",exact);
         var identity:Boolean=raw!=null && (String(raw.data_id)==exact || String(raw.variation_id)==exact);
         row.default_part=selected.length==0;
         if(!identity && selected.length==1) raw=CommunicationManager.CallGameService("GetCatalogItem",String(selected[0]));
         else if(!identity) raw=null;
         row.catalog_body_type=raw==null ? -1 : int(raw.body_type);
         if(raw==null || int(raw.body_type)!=int(row.body_type)) throw new Error("Native catalog product body type differs");
         var product:CASCatalogProduct=new CASCatalogProduct(raw);
         var thumbnail:CASCatalogProduct=product.GetVariation();
         // Reuse the installed FacePanel renderer's whole-head thumbnail route.
         if(thumbnail.image==null && product.menu_state==MenuState.PROFILE_HEAD_WHOLE_HEADS)
            thumbnail.image="thumbs/cas/h_"+thumbnail.data_id+"_l_"+(SimGenderTypes.IsFemale(thumbnail.gender) ? "f" : "m");
         apexEquippedProducts.push(product);
         apexEquippedBindings.push({product:product,row:row,layer:layer,layer_index:index,read_only:row.default_part});
      }

      private function ApexEquippedDecimal(value:String) : String
      {
         var hex:String=ApexEquippedKey(value);var decimal:String="0";
         for(var i:int=0;i<hex.length;i++) {
            var carry:int="0123456789abcdef".indexOf(hex.charAt(i));var result:String="";
            for(var j:int=decimal.length-1;j>=0;j--) {
               var number:int=int(decimal.charAt(j))*16+carry;
               result=String(number%10)+result;carry=int(number/10);
            }
            while(carry>0) {result=String(carry%10)+result;carry=int(carry/10);}
            decimal=result;
         }
         return decimal;
      }

      private function ApexEquippedKey(value:String) : String
      {
         // Preserve all 64 bits. Catalog IDs and CASP instance keys are distinct.
         if(/^0x[0-9a-f]+$/i.test(value)) return value.toLowerCase().replace(/^0x0*/,"");
         if(!/^[0-9]{1,20}$/.test(value)) throw new Error("Invalid native part key");
         var result:String="";
         while(value!="0" && value!="") {
            var quotient:String="";var carry:int=0;
            for(var i:int=0;i<value.length;i++) {
               var digit:int=carry*10+int(value.charAt(i));
               if(quotient!="" || int(digit/16)>0) quotient+=String(int(digit/16));
               carry=digit%16;
            }
            result="0123456789abcdef".charAt(carry)+result;value=quotient;
         }
         return result;
      }

      private function ApexEquippedPrepare(value:Object) : Object
      {
         if(!apexEquippedActive) {
            // A departing category may still have recycled owned products for
            // one frame. They must never fall through to EA's generic setters.
            if(value!=null) for each(var retired:Object in apexEquippedBindings)
               if(retired.product===value.product) return {active:true,allowed:false};
            return null;
         }
         var slot:Object=CommunicationManager.CallGameService("CasGetCurrSimOutfitSlot");
         if(slot==null || apexCatalogSlot==null || int(slot.outfit_type)!=int(apexCatalogSlot.category) ||
            int(slot.outfit_index)!=int(apexCatalogSlot.index)) return {active:true,allowed:false};
         var binding:Object=null;
         if(value!=null && value.panel===mcClothingPanel && mCurrSimInfo!=null &&
            apexCatalogContext==String(mCurrSimInfo.simId)+"|"+apexFormsSelectedId && !apexCatalogDirty && !apexEquippedDirty) {
            for each(var candidate:Object in apexEquippedBindings)
               if(candidate.product===value.product) {binding=candidate;break;}
         }
         // A swatch callback carries a variation rather than the base product.
         // Only the currently opened, exact native product may supply it.
         if(binding==null && value!=null && value.panel===mcClothingPanel && !apexCatalogDirty && !apexEquippedDirty &&
            mCurrSimInfo!=null && apexCatalogContext==String(mCurrSimInfo.simId)+"|"+apexFormsSelectedId &&
            value.action=="select" && apexEquippedInteraction!=null &&
            value.product!=null && int(value.product.body_type)==int(apexEquippedInteraction.row.body_type)) {
            var swatches:Object=apexEquippedInteraction.product.GetColorSwatchArray();
            if(swatches!=null) for each(var swatch:Object in swatches.mItems)
               if(String(swatch.dataID)==String(value.product.data_id)) {binding=apexEquippedInteraction;break;}
         }
         if(binding==null || binding.read_only===true || [3,4].indexOf(int(binding.row.body_type))>=0) return {active:true,allowed:false};
         if(value.action=="variants") apexEquippedInteraction=binding;
         return {active:true,allowed:true,menu_state:int(binding.row.menu_state),layer:binding.layer,layer_index:binding.layer_index};
      }

      private function ApexEquippedClick(value:Object) : Object
      {
         if(!apexEquippedActive) return false;
         if(value!=null && value.panel===mcClothingPanel) for each(var binding:Object in apexEquippedBindings)
            if(binding.product===value.product) {
               apexCatalogIntent={operation:"navigate",sim_id:String(mCurrSimInfo.simId),owner_id:apexFormsSelectedId,state:int(binding.row.menu_state)};
               break;
            }
         return true;
      }
