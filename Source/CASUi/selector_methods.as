// Apex-owned read-only observer appended to the exact installed selector.
// The retained-bytecode adapter calls CaptureFeed before the native handler.
// No native getter, refresh, selection or mutation is issued by these methods.
      private var apexSelectorFeed:Object;
      private var apexSelectorSequence:int = 0;
      private var apexSelectorRegistered:Boolean = false;
      private var apexSelectorResetRegistered:Boolean = false;

      private function ApexSelectorInitialize() : void
      {
         // Initial CASReady delivery may already have been copied by the
         // native handler entry hook. Never discard it at this later hook.
         if(!apexSelectorRegistered)
            apexSelectorRegistered=RegisterServiceHandler("ApexReadOwnerPairFeed",ApexSelectorReadOwnerFeed);
         if(!apexSelectorResetRegistered)
            apexSelectorResetRegistered=AddMessageListener("CASClearSimsForReset",ApexSelectorClearFeed);
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
            reset_listener_registered:apexSelectorResetRegistered,raw_feed:apexSelectorFeed,retained:retained,
            mapping_verified:false,alternate_accept_authorized:false};
      }
