      // PRIVATE adapter grafted ONLY into ColorSwatchPanelCellView, which
      // owns native color-family title/background and its dynamic row height.
      public function ApexSwatchGroupGeometry(columns:int,scale:Number,gapX:Number,gapY:Number,width:Number) : Object
      {
         if(mcColorSwatchPanel==null || !("ApexSwatchGeometry" in mcColorSwatchPanel))
            throw new Error("Native nested swatch adapter unavailable");
         var result:Object=mcColorSwatchPanel.ApexSwatchGeometry(columns,scale,gapX,gapY,width);
         if(result!=null && result.changed===true) {
            txtTitle.width=width;txtTitle.x=mcColorSwatchPanel.mcSelectionGrid.x;
            RefreshLayout();
         }
         return result;
      }
