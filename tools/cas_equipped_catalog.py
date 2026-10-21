"""Narrow adapters for native CAS tiles; private game exports stay untracked.

EA keeps its own tile renderer, swatch controller, removal and undo handlers.
The additional view supplies only currently equipped products, with a matching
native category and layer for each action. Normal categories keep their paths.
"""
import re
from cas_catalog_workspace import replace_once

CLOTHING_CLASS = 'widgets.CAS.Customizer.ClothingPanel'
CELL_CLASS = 'widgets.CAS.controls.CASClothingPanelCellViewMain'
FEED_CLASS = 'widgets.CAS.data.CatalogDataFeed'
NATIVE_METHODS = {
    CLOTHING_CLASS: ('Refresh','OnCatalogClick','OnToggleVariationGrid','RemoveSelectedItem','SelectCatalogProduct'),
    CELL_CLASS: ('height',),
    FEED_CLASS: ('RequestData',),
}


def prepend(source, signature, body):
    return replace_once(source, signature+'\n      {', signature+'\n      {\n'+body)


def prepare(product, action):
    return '''         var apex:Object=CommunicationManager.CallUIService("ApexEquippedPrepare",
            {panel:this,product:'''+product+''',action:"'''+action+'''"});
         if(apex!=null && apex.active===true) {
            if(apex.allowed!==true) return;
            mCurrState=int(apex.menu_state);
         }
'''


def inject_clothing(source):
    if 'ApexEquippedPrepare' in source:raise ValueError('Equipped adapter already present.')
    source=re.sub(r'\s*\[Embed\([^\n]*\)\]','',source)
    source=replace_once(source,'   import gamedata.CAS.CASAPI;',
        '   import flash.utils.getTimer;\n   import gamedata.CAS.CASAPI;')
    source=prepend(source,'      override public function Refresh(param1:int) : void',
        '''         var apexView:Object=CommunicationManager.CallUIService("ApexEquippedRefresh",{panel:this,state:param1,feed:mDataFeed});
         if(apexView!=null && apexView.active===true) {
            var apexStart:int=getTimer();
            if(apexView.reset===true) {
               super.Refresh(param1);
               this.mVariationGridController.RemoveVariationPopups();
               mDataFeed.RemoveAllItems();
            }
            this.btnRandomize.visible=false;this.mcHairGrowthPanel.visible=false;
            this.mcApplyToAllPanel.visible=false;this.mcBodyTypePanel.visible=false;
            this.SetLayerComponentVisibility(false);
            if(this.mcFilterPane!=null) this.mcFilterPane.visible=false;
            var apexCleared:int=getTimer();
            var apexFirst:int=mDataFeed.length;
            if(apexView.products.length>1) return;
            if(apexView.products.length>0) mDataFeed.AddItemsFromIterable(apexView.products);
            var apexBound:int=getTimer();
            if(apexView.products.length>0) mDataFeed.SetSelectionStateMultiple([apexFirst],true);
            var apexSelected:int=getTimer();
            this.txtNoResults.visible=apexView.complete===true && mDataFeed.length==0;
            txtTitle.text="All equipped CAS items"+(apexView.complete===true ? "" : " ("+mDataFeed.length+"/"+apexView.total+")");
            if(apexView.reset===true) this.RefreshLayout();
            if(this.mcFilterPane!=null) this.mcFilterPane.visible=false;
            apexView.commit.count=mDataFeed.length;apexView.commit.feed=mDataFeed;apexView.commit.reset=false;
            apexView.timing.clear_ms=apexCleared-apexStart;
            apexView.timing.bind_ms=apexBound-apexCleared;
            apexView.timing.selected_ms=apexSelected-apexBound;
            apexView.timing.layout_ms=getTimer()-apexSelected;
            if(apexView.products.length>0) {
               apexView.timing.chunks++;
               apexView.timing.bind_total_ms+=apexBound-apexCleared;
               apexView.timing.bind_max_ms=Math.max(apexView.timing.bind_max_ms,apexBound-apexCleared);
               apexView.timing.chunk_max_count=Math.max(apexView.timing.chunk_max_count,apexView.products.length);
            }
            apexView.timing.publish_max_ms=Math.max(apexView.timing.publish_max_ms,getTimer()-apexStart);
            return;
         }
''')
    source=prepend(source,'      protected function OnCatalogClick(param1:GridEvent) : void',
        '''         if(CommunicationManager.CallUIService("ApexEquippedClick",{panel:this,product:param1.mData})===true) {
            param1.preventDefault();return;
         }
''')
    source=prepend(source,'      protected function OnToggleVariationGrid(param1:GridEvent) : void',prepare('param1.mData','variants'))
    anchor='''            _loc6_ = CASAPI.GetCatalogItemSelectedWithModifiers(mCurrState,'''
    source=replace_once(source,anchor,'''            if(apex!=null && apex.active===true) _loc5_=apex.layer;
'''+anchor)
    anchor='         var _loc2_:Object = param1.product;'
    source=replace_once(source,anchor,anchor+'\n'+prepare('_loc2_','remove'))
    anchor='         CommunicationManager.AddMessageListener("CASItemCannotBeRemoved",this.ItemFailedToRemove,this);'
    source=replace_once(source,anchor,'''         if(apex!=null && apex.active===true && apex.layer!=null) _loc4_=int(apex.layer_index);
'''+anchor)
    source=prepend(source,'      protected function SelectCatalogProduct(param1:CASCatalogProduct, param2:ColorSwatchData = null) : void',prepare('param1','select'))
    anchor='         var _loc6_:Object = MenuState.GetBodyTypeFixedLayerIndexAndId(mCurrState,param1.body_type,_loc5_);'
    source=replace_once(source,anchor,'''         if(apex!=null && apex.active===true && apex.layer!=null) {
            _loc5_["layer_index"]=int(apex.layer.layer_index);
            _loc5_["layer_id"]=int(apex.layer.layer_id);
         }
'''+anchor)
    source=replace_once(source,'         mDataFeed.SelectIndex(mDataFeed.IndexOf(param1),mCurrState,param1.groupId);',
        '''         if(apex==null || apex.active!==true)
            mDataFeed.SelectIndex(mDataFeed.IndexOf(param1),mCurrState,param1.groupId);''')
    return source


def inject_cell(source):
    """Native height is unscaled; opt in only cells carrying our empty marker."""
    if 'apexCatalogCardScale' in source:raise ValueError('Card-height adapter already present.')
    return replace_once(source,'         return mcHitArea.height;',
        '''         return mcHitArea.height*(getChildByName("apexCatalogCardScale")!=null ? scaleY : 1);''')


def inject_feed(source):
    """Measure real native lookup/construction/selection separately, off clicks.

    No result cache or eligibility assumption. Every original game query and
    product construction is retained while identifying the expensive boundary.
    """
    if 'ApexCatalogPerformance' in source:raise ValueError('Catalog profiler already present.')
    source=replace_once(source,'   import gamedata.CAS.CASAPI;',
        '   import flash.utils.getTimer;\n   import gamedata.CAS.CASAPI;')
    source=prepend(source,'      public function RequestData(param1:CASCatalogFilter, param2:Boolean = true, param3:Object = null) : void',
        '         var apexStarted:int=flash.utils.getTimer();\n')
    anchor='         var _loc4_:Array = CASAPI.GetCatalogBaseItemsUsingFilter(param1,param3);'
    source=replace_once(source,anchor,'         var apexFetchStarted:int=flash.utils.getTimer();\n'+anchor)
    source=replace_once(source,'         OlympusObject.ConstructArrayInPlace(_loc4_,CASCatalogProduct);',
        '         var apexNative:int=flash.utils.getTimer();\n         OlympusObject.ConstructArrayInPlace(_loc4_,CASCatalogProduct);\n         var apexConstructed:int=flash.utils.getTimer();')
    source=replace_once(source,'         AddItemsFromIterable(_loc4_);',
        '         AddItemsFromIterable(_loc4_);\n         var apexBound:int=flash.utils.getTimer();')
    anchor='''            this.RequestSelectedItem(param1);
         }
      }'''
    source=replace_once(source,anchor,'''            this.RequestSelectedItem(param1);
         }
         CommunicationManager.CallUIService("ApexCatalogPerformance",{state:param1.menuState,count:_loc4_.length,
            clear_ms:apexFetchStarted-apexStarted,native_ms:apexNative-apexFetchStarted,
            construct_ms:apexConstructed-apexNative,bind_ms:apexBound-apexConstructed,
            selected_ms:flash.utils.getTimer()-apexBound});
      }''')
    return source.replace('flash.utils.getTimer()','getTimer()')
