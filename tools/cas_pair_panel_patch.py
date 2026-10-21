"""Adapt the installed EA portrait panel; no EA source is distributed.

Only hybrid branches change. The embedded native artwork, layout, checkbox
widget, copy/link buttons, localization and ordinary-Sim behavior are retained.
"""
import re

CLASS = 'widgets.CAS.SimSelector.CASSimSelectorCopyOptionPanel'
METHODS = ('UpdateSimInfo', 'SetOccultData', 'GetSelectedBitValues', 'OnCopy',
           'SendLinkUpdate', 'OnRandomizeBitChanged', 'UpdateCopyFiltersAndRandomizationFlags')
SUPPORTED = 2|4|8|16|32|64|128|256|1024|4096|16384|32768|65536|131072|262144|524288|1048576|2097152|4194304|8388608|134217728


def prepend(source, method, owned):
    pattern = r'(function\s+'+re.escape(method)+r'\([^\n]*\)\s*:\s*\w+\s*\{)'
    source, count = re.subn(pattern, lambda m: m[1]+'\n'+owned, source)
    if count != 1:
        raise ValueError('EA pair-panel method signature differs: '+method)
    return source


def inject(source):
    if 'ApexFormPairPanel' in source:
        raise ValueError('EA pair panel is already adapted.')
    source = re.sub(r'\s*\[Embed\([^\n]*\)\]', '', source)
    source = prepend(source, 'UpdateSimInfo', '''
         var apexSim:String=String(param1.sim_layers[OccultTypes.OCCULT_FORM_BASE].simId);
         var apexPair:Object=CommunicationManager.CallUIService("ApexFormPairPanel",{operation:"status",sim_id:apexSim});
         if(apexPair!=null && apexPair.enabled===true) {
            this.mCopyModeData["apexPair"]=apexPair;
            this.mCurrentBaseSimId=apexSim+"|"+apexPair.base_owner_id+"|"+apexPair.alternate_owner_id;
            this.UpdateCopyFiltersAndRandomizationFlags();
            var apexFlags:uint=apexPair.category_flags==4294967295?this.mAllBitFlags:uint(apexPair.category_flags);
            for(var apexBit:int=0;apexBit<31;++apexBit)
               mSelectedRandomizeFlags[1<<apexBit]=(apexFlags&(1<<apexBit))!=0;
            for each(var apexItem:MenuItem in this.mCopyFilters)
               mSelectedRandomizeFlags[apexItem.data.flags]=(apexFlags&uint(apexItem.data.flags))==uint(apexItem.data.flags);
            this.ApplyFilter(this.mCopyFilters,true,true);
            this.SetRandomizationFlagsToFeed();this.RefreshBackground();
            this.SetCopyMode(!Boolean(apexPair.linked));
            this.btnCopy.TooltipExt.SetText("Copy "+apexPair.source_label+" to "+apexPair.target_label+". Only checked details are copied; other forms and Sims stay separate.");
            this.btnLink.TooltipExt.SetText("Link or unlink "+apexPair.source_label+" and "+apexPair.target_label+". Only checked details follow later edits. Linking keeps both current appearances.");
            this.visible=true;return;
         }
         delete this.mCopyModeData["apexPair"];
         var apexMask:int=int(param1.sim_layers[0].allOccultTypes)&~1;
         if(apexPair!=null && apexPair.blocked===true || (apexMask&(apexMask-1))!=0) {
            this.visible=false;return;
         }
''')
    source = prepend(source, 'SetOccultData', '''
         // Native labels and directional tooltips are supplied from the exact
         // selected pair, never GetRealOccultType's hybrid priority choice.
         if(this.mCopyModeData["apexPair"]!=null) return;
''')
    source = prepend(source, 'GetSelectedBitValues', '''
         // Do not inherit Vampire's implicit Face -> Skin Details expansion.
         if(this.mCopyModeData["apexPair"]!=null) return super.GetSelectedBitValues();
''')
    source = prepend(source, 'OnCopy', '''
         var apexPair:Object=this.mCopyModeData["apexPair"];
         if(apexPair!=null) {
            CommunicationManager.CallUIService("ApexFormPairPanel",{operation:"copy",sim_id:apexPair.sim_id,
               base_owner_id:apexPair.base_owner_id,alternate_owner_id:apexPair.alternate_owner_id,
               generation:apexPair.generation,enabled:false,category_flags:Number(this.GetSelectedBitValues())});
            return;
         }
''')
    source = prepend(source, 'SendLinkUpdate', '''
         var apexPair:Object=this.mCopyModeData["apexPair"];
         if(apexPair!=null) {
            var apexFlags:Number=Number(this.GetSelectedBitValues());
            var apexStored:Number=apexPair.category_flags==4294967295?Number(this.mAllBitFlags):Number(apexPair.category_flags);
            if(apexPair.linked!==this.btnLink.Selected || apexFlags!==apexStored)
               CommunicationManager.CallUIService("ApexFormPairPanel",{operation:"link",sim_id:apexPair.sim_id,
                  base_owner_id:apexPair.base_owner_id,alternate_owner_id:apexPair.alternate_owner_id,
                  generation:apexPair.generation,enabled:Boolean(this.btnLink.Selected),category_flags:apexFlags});
            return;
         }
''')
    source = prepend(source, 'OnRandomizeBitChanged', '''
         if(this.mCopyModeData["apexPair"]!=null) {
            var apexChanged:Boolean=super.OnRandomizeBitChanged(param1);
            this.SendLinkUpdate();return apexChanged;
         }
''')
    # Extend the existing EA list rather than replacing its visual component.
    anchor = 'mAllBitFlags = _loc1_.allFlags;'
    if source.count(anchor) != 1:
        raise ValueError('EA copy-filter assignment differs.')
    source = source.replace(anchor, anchor+'''
         if(this.mCopyModeData["apexPair"]!=null) {
            var apexSupported:uint=__SUPPORTED__;
            var apexFilters:Array=[];var apexCovered:uint=0;var apexAll:MenuItem=null;
            for each(var apexItem:MenuItem in this.mCopyFilters) {
               var apexFlag:uint=uint(apexItem.data.flags);
               if(apexFlag==_loc1_.allFlags) {apexAll=apexItem;continue;}
               apexFlag&=apexSupported;
               if(apexFlag==0 || (apexCovered&apexFlag)==apexFlag) continue;
               apexItem.data.flags=apexFlag;apexItem.data.required_flags=0;
               apexCovered|=apexFlag;apexFilters.push(apexItem);
            }
            var apexExtra:Array=[{name:"Body shape",flags:6},{name:"Face and presets",flags:8},
               {name:"Skin tone",flags:16},{name:"Hair",flags:32},{name:"Facial hair",flags:64},
               {name:"Voice",flags:128},{name:"Outfits",flags:256},{name:"Tattoos",flags:1024},
               {name:"Skin details and scars",flags:4096},{name:"Accessories and jewelry",flags:16384},
               {name:"Makeup and eyelashes",flags:524288},{name:"Eyes and eyebrows",flags:4194304},
               {name:"Body hair",flags:8388608},{name:"Wings",flags:134217728}];
            for each(var apexChoice:Object in apexExtra) if((apexCovered&uint(apexChoice.flags))!=uint(apexChoice.flags)) {
               var apexFilter:CASRandomizeFilter=new CASRandomizeFilter({flags:uint(apexChoice.flags),required_flags:0});
               apexFilters.push(new MenuItem(String(apexChoice.name),apexFilter));apexCovered|=uint(apexChoice.flags);
            }
            this.mAllBitFlags=apexCovered;
            if(apexAll==null) apexAll=new MenuItem("All details",new CASRandomizeFilter({flags:apexCovered,required_flags:0}));
            apexAll.data.flags=apexCovered;apexAll.data.required_flags=0;apexFilters.unshift(apexAll);mItemAllIndex=0;
            this.mCopyFilters=apexFilters;mDataFeed.RemoveAllItems();mDataFeed.AddItemsFromIterable(apexFilters);
         }
'''.replace('__SUPPORTED__', str(SUPPORTED)))
    return source
