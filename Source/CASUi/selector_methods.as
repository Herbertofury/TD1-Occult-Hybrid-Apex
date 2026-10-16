// Apex-owned observer and checked navigation appended to the installed selector.
// CaptureFeed copies the raw delivery before the unchanged native handler.
// Navigation delegates to EA's complete SelectSimLayer lifecycle after checking
// the exact Sim, delivered pair, selected layer and one-shot request identity.
      private var apexSelectorFeed:Object;
      private var apexSelectorSequence:int = 0;
      private var apexSelectorRegistered:Boolean = false;
      private var apexSelectorResetRegistered:Boolean = false;
      private var apexSelectorNavigationRegistered:Boolean = false;
      private var apexSelectorLastNavigation:String = "";

      private function ApexSelectorInitialize() : void
      {
         // Initial CASReady delivery may already have been copied by the
         // native handler entry hook. Never discard it at this later hook.
         if(!apexSelectorRegistered)
            apexSelectorRegistered=RegisterServiceHandler("ApexReadOwnerPairFeed",ApexSelectorReadOwnerFeed);
         if(!apexSelectorResetRegistered)
            apexSelectorResetRegistered=AddMessageListener("CASClearSimsForReset",ApexSelectorClearFeed);
         if(!apexSelectorNavigationRegistered)
            apexSelectorNavigationRegistered=RegisterServiceHandler("ApexNavigateOwnerLayer",ApexSelectorNavigate);
      }

      private function ApexSelectorCopyRow(raw:Object) : Object
      {
         if(raw==null || !(raw.simId is String) || !/^(0|[1-9][0-9]{0,19})$/.test(raw.simId) ||
            !(raw.index is int) || !(raw.occultType is int) || !(raw.allOccultTypes is int) ||
            !(raw.occultLayer is int) || !(raw.selected is Boolean)) return null;
         return {sim_id:String(raw.simId),index:int(raw.index),occult_type:int(raw.occultType),
            all_occult_types:int(raw.allOccultTypes),occult_layer:int(raw.occultLayer),selected:Boolean(raw.selected)};
      }

      private function ApexSelectorCaptureFeed(message:Object) : void
      {
         var bases:Array=null; var alternates:Array=null; var raw:Object=null;
         var copied:Object={delivered:true,complete:false,sequence:apexSelectorSequence,
            source:"native-selector-raw-entry-observer",before_native_handler:true,
            selected_index:-1,selected_layer:-1,base_row_count:0,alternate_row_count:0,
            pairs:[],error:"Native selector raw feed is unavailable"};
         try {
            if(apexSelectorSequence>=2147483647) throw new Error("Selector feed sequence exhausted");
            copied.sequence=++apexSelectorSequence;
            if(message==null || !(message.sim_data is Array) || !(message.sim_occult_data is Array) ||
               !(message.selected_sim is int) || !(message.selected_layer is int))
               throw new Error("Native selector raw feed fields are untyped");
            bases=message.sim_data; alternates=message.sim_occult_data;
            copied.selected_index=int(message.selected_sim); copied.selected_layer=int(message.selected_layer);
            copied.base_row_count=bases.length; copied.alternate_row_count=alternates.length;
            if(bases.length==0 || bases.length>32 || alternates.length>32)
               throw new Error("Native selector raw feed exceeds or lacks bounded rows");
            copied.complete=bases.length==alternates.length; copied.error="";
            for(var i:int=0;i<bases.length;i++) {
               raw=bases[i]; var base:Object=ApexSelectorCopyRow(raw); raw=null;
               raw=i<alternates.length ? alternates[i] : null;
               var alternate:Object=ApexSelectorCopyRow(raw); raw=null;
               copied.pairs.push({index:i,base:base,alternate:alternate});
               if(base==null || alternate==null || base.sim_id=="0" || alternate.sim_id=="0") copied.complete=false;
            }
            if(copied.selected_index<0 || copied.selected_index>=bases.length ||
               (copied.selected_layer!=0 && copied.selected_layer!=1)) copied.complete=false;
            if(!copied.complete) copied.error="Raw pair, alternate placeholder or selection is incomplete";
         } catch(copyError:Error) {
            copied.complete=false; copied.error=copyError.message;
         } finally {
            raw=null; bases=null; alternates=null; message=null;
            apexSelectorFeed=copied;
         }
      }

      private function ApexSelectorClearFeed(message:Object=null) : void
      {
         if(apexSelectorSequence<2147483647) apexSelectorSequence++;
         apexSelectorFeed={delivered:false,complete:false,sequence:apexSelectorSequence,
            source:"native-selector-raw-entry-observer",before_native_handler:true,
            selected_index:-1,selected_layer:-1,base_row_count:0,alternate_row_count:0,
            pairs:[],error:"Native selector cleared its feed; awaiting actual delivery"};
         message=null;
      }

      private function ApexSelectorReadOwnerFeed(message:Object=null) : Object
      {
         var retained:Object={source:"native-selector-retained-filtered-feed",available:false,complete:false,
            selected_index:this.mSelectedSimIndex,selected_layer:this.mSelectedSimLayerIndex,
            selected_sim_id:this.mCurrSimId,pairs:[],error:"Retained selector feed unavailable"};
         var row:Object=null; var layers:Array=null; var raw:Object=null;
         try {
            if(this.mDataFeed==null || this.mDataFeed.length==0 || this.mDataFeed.length>32)
               throw new Error("Retained selector feed lacks bounded rows");
            retained.available=true; retained.complete=true; retained.error="";
            for(var i:int=0;i<this.mDataFeed.length;i++) {
               row=this.mDataFeed.RequestItemAt(i);
               layers=row!=null && row.sim_layers is Array ? row.sim_layers : null;
               if(layers==null || layers.length==0 || layers.length>2) {
                  retained.complete=false; retained.pairs.push({index:i,base:null,alternate:null});
               } else {
                  raw=layers[0]; var base:Object=ApexSelectorCopyRow(raw); raw=null;
                  raw=layers.length>1 ? layers[1] : null;
                  var alternate:Object=ApexSelectorCopyRow(raw); raw=null;
                  retained.pairs.push({index:i,base:base,alternate:alternate});
                  if(base==null || alternate==null || base.sim_id=="0" || alternate.sim_id=="0") retained.complete=false;
               }
               row=null; layers=null;
            }
            if(!retained.complete) retained.error="Native selector filters unavailable/unsupported alternates; no pair was invented";
         } catch(readError:Error) {
            retained.complete=false; retained.error=readError.message;
         } finally { row=null; layers=null; raw=null; message=null; }
         return {protocol:1,scope:"native-selector-owner-pair-view",service_registered:apexSelectorRegistered,
            navigation_service_registered:apexSelectorNavigationRegistered,
            reset_listener_registered:apexSelectorResetRegistered,raw_feed:apexSelectorFeed,retained:retained,
            mapping_verified:false,alternate_accept_authorized:false};
      }

      private function ApexSelectorNavigate(request:Object) : Object
      {
         if(request==null || !(request.request_id is String) || !/^[0-9a-f]{32}$/.test(request.request_id) ||
            request.request_id==apexSelectorLastNavigation || !(request.sim_id is String) ||
            !/^[1-9][0-9]{0,19}$/.test(request.sim_id) || !(request.index is int) ||
            !(request.expected_layer is int) || !(request.target_layer is int) || !(request.feed_sequence is int) ||
            !(request.target_kind is int) || request.index!=mSelectedSimIndex || request.sim_id!=mCurrSimId ||
            request.expected_layer!=mSelectedSimLayerIndex || request.expected_layer<0 || request.expected_layer>1 ||
            request.target_layer<0 || request.target_layer>1 || mDataFeed==null ||
            request.index<0 || request.index>=mDataFeed.length || apexSelectorFeed==null ||
            apexSelectorFeed.complete!==true || apexSelectorFeed.delivered!==true ||
            request.feed_sequence!=apexSelectorFeed.sequence || request.index>=apexSelectorFeed.pairs.length)
            throw new Error("Native selector navigation lost its exact Sim, pair, layer, sequence or one-shot identity");
         var item:Object=mDataFeed.RequestItemAt(int(request.index));
         var layers:Array=item!=null && item.sim_layers is Array ? item.sim_layers : null;
         var target:Object=layers!=null && layers.length==2 ? layers[int(request.target_layer)] : null;
         var copied:Object=ApexSelectorCopyRow(target);
         var raw:Object=apexSelectorFeed.pairs[int(request.index)];
         raw=raw==null ? null : request.target_layer==0 ? raw.base : raw.alternate;
         if(copied==null || raw==null || copied.sim_id!=request.sim_id || copied.index!=request.index ||
            copied.occult_layer!=request.target_layer || copied.occult_type!=request.target_kind ||
            target.enabled!==true || raw.sim_id!==copied.sim_id || raw.index!==copied.index ||
            raw.occult_layer!==copied.occult_layer || raw.occult_type!==copied.occult_type ||
            raw.all_occult_types!==copied.all_occult_types)
            throw new Error("Native selector target is unavailable or differs from its actual raw delivery");
         item=null; layers=null; target=null; raw=null; copied=null;
         var index:int=int(request.index); var layer:int=int(request.target_layer);
         var id:String=String(request.request_id); var simId:String=String(request.sim_id);
         apexSelectorLastNavigation=id; request=null;
         // The unchanged EA handler owns thumbnail cleanup, hiding equipped
         // traits, both native setters, retained selection/index, copy/link UI
         // and customizer lifecycle. Do not duplicate only its low-level calls.
         SelectSimLayer(index,layer);
         return {protocol:1,request_id:id,sim_id:simId,target_layer:layer,submitted:true,
            native_selector_handler:true,selection_verified:false};
      }
