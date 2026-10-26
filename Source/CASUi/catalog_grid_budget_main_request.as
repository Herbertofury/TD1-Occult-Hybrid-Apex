private function ApexCatalogGridRequest(lease:Object) : Object
      {
         if(!ApexCatalogGridLeaseCurrent(lease) || lease.phase!="bound")return null;
         var list:Object=lease.panel.mcTileList;var view:Object=list.mScrollerView;
         var nativeCardContract:int=(lease.cell_type===CASClothingPanelCellViewMain ||
            lease.cell_type===CASClothingPanelCellViewCommon || lease.cell_type===CASClothingPanelCellViewSkinSpecularity ||
            lease.cell_type===CASBodyPanelCellView ||
            lease.cell_type===CASFacePanelCellView || lease.cell_type===CASGenericCatalogVariantCellView ||
            lease.cell_type===CASBreedCatalogCellView) ? 1 : 0;
         if(view==null || list.mSlider==null || !isFinite(Number(view.width)) || Number(view.width)<=0 ||
            !isFinite(Number(view.height)) || Number(view.height)<=0 || !isFinite(Number(list.mSlider.Value)))return null;
         // Measure the first REAL native cell and retain it for the fitted pool.
         // Only the freshly observed bound owner may step this measurement.
         var retained:Object=ApexCardStateFor(lease.grid);
         if(retained==null || retained.geometry==null || retained.geometry.grid!==lease.grid || retained.geometry.panel!==lease.panel || retained.layout==null)
            return {columns:1,width:1,height:1,scale:1,gapX:0,gapY:0,viewWidth:Number(view.width),viewHeight:Number(view.height),
               scrollY:0,marginX:0,marginY:0,bootstrap:true,panel:lease.panel,owner:lease,
               validate:ApexCatalogGridValidate,inputValidate:ApexCatalogGridInput,
               rowValidate:lease.panel_kind=="clothing" ? null : ApexCatalogGridProductRow,scrollOnlyPositionContract:nativeCardContract,stepBudgetClockContract:nativeCardContract,stepBudgetMilliseconds:1};
         var p:Object=retained.layout;var margin:Object=lease.grid.GetCellPadding();
         if(margin==null || !isFinite(Number(p.scale)) || Number(p.scale)<=0 ||
            !isFinite(Number(p.card_width)) || Number(p.card_width)<=0 || !isFinite(Number(p.card_height)) || Number(p.card_height)<=0 ||
            int(p.columns)<2)return null;
         return {columns:int(p.columns),width:Number(p.card_width),height:Number(p.card_height),scale:Number(p.scale),
            gapX:Number(p.gap_x),gapY:Number(p.gap_y),viewWidth:Number(view.width),viewHeight:Number(view.height),
            scrollY:Number(list.mSlider.Value),marginX:Number(margin.mLeft),marginY:Number(margin.mTop),bootstrap:false,
            panel:lease.panel,owner:lease,validate:ApexCatalogGridValidate,inputValidate:ApexCatalogGridInput,
               rowValidate:lease.panel_kind=="clothing" ? null : ApexCatalogGridProductRow,scrollOnlyPositionContract:nativeCardContract,stepBudgetClockContract:nativeCardContract,stepBudgetMilliseconds:1};
      }
