      // PRIVATE adapter grafted ONLY into native ColorSwatchPanel. It retains
      // the existing feed, selection callback, popup, add/delete and color
      // controls. The native outer SkinTone grid keeps one color-family row.
      private var apexSwatchGeometry:Object;

      public function ApexSwatchGeometry(columns:int,scale:Number,gapX:Number,gapY:Number,width:Number) : Object
      {
         if(columns<2 || columns>32 || !isFinite(scale) || scale<=0 || scale>1.6 ||
            !isFinite(gapX) || gapX<0 || gapX>32 || !isFinite(gapY) || gapY<0 || gapY>32 ||
            !isFinite(width) || width<=0 || mGrid==null || mcSelectionGrid==null || mcSelectionGrid.mGridLayout!==mGrid)
            throw new Error("Exact native swatch geometry required");
         if(apexSwatchGeometry==null || apexSwatchGeometry.grid!==mGrid)
            apexSwatchGeometry={grid:mGrid,width:NaN,height:NaN,signature:"",columns:columns,policy:1};
         var g:Object=apexSwatchGeometry;g.columns=columns;g.policy=1;
         var first:Object=mGrid.FirstCell;
         if(first==null) {
            var emptyDimensions:Array=mGrid.GetGridDimensions();
            var emptyChanged:Boolean=mMaxCols!==columns || int(emptyDimensions[mGrid.Horizontal ? 0 : 1])!==columns;
            if(emptyChanged) {mMaxCols=columns;mGrid.NumLines=columns;}
            return {ready:false,changed:emptyChanged,columns:columns,width:width};
         }
         if(!isFinite(g.width) || g.width<=0 || !isFinite(g.height) || g.height<=0) {
            if(!isFinite(first.scaleX) || first.scaleX<=0 || !isFinite(first.scaleY) || first.scaleY<=0)
               throw new Error("Native swatch intrinsic metrics unavailable");
            g.width=Number(first.width)/Number(first.scaleX);g.height=Number(first.height)/Number(first.scaleY);
         }
         if(!isFinite(g.width) || g.width<=0 || !isFinite(g.height) || g.height<=0)
            throw new Error("Native swatch intrinsic metrics unavailable");
         var signature:String=columns+":"+scale+":"+gapX+":"+gapY+":"+width;
         var dimensions:Array=mGrid.GetGridDimensions();var padding:Object=mGrid.GetCellPadding();
         var bounds:flash.geom.Rectangle=mGrid.GetCellBounds();
         var changed:Boolean=g.signature!==signature || mMaxCols!==columns ||
            int(dimensions[mGrid.Horizontal ? 0 : 1])!==columns || bounds==null ||
            Math.abs(bounds.width-Number(g.width)*scale)>0.01 || Math.abs(bounds.height-Number(g.height)*scale)>0.01 ||
            padding==null || padding.Horizontal!==gapX || padding.Vertical!==gapY;
         if(changed) {
            // Base GridLayout has no suppression lease. These are its public
            // geometry setters, with no feed replacement or cell reconstruction.
            // Native display-only cost must be measured before promotion.
            mMaxCols=columns;mGrid.NumLines=columns;
            mGrid.SetCellPadding(new olympus.core.widget.Margin(0,0,gapY,gapX));
            mGrid.SetCellBounds(new flash.geom.Rectangle(0,0,Number(g.width)*scale,Number(g.height)*scale));
            mCenterX=width*0.5;
            if(mbPreserveBackgroundWidth)mcSelectionGridBackground.width=Math.max(1,width);
            ResetLayout();g.signature=signature;
         }
         return {ready:true,changed:changed,columns:columns,scale:scale,natural_width:g.width,natural_height:g.height,
            card_width:Number(g.width)*scale,card_height:Number(g.height)*scale,width:width,signature:signature};
      }

      // The donor's existing width reflow calls this only after calculating its
      // legacy column value. It retains the exact native width/scroll algorithm.
      private function ApexSwatchColumns(legacy:int) : int
      {
         var g:Object=apexSwatchGeometry;
         if(mSwatchType==CASSwatchType.SKINTONE && g!=null && g.policy===1 && g.grid===mGrid &&
            typeof g.columns=="number" && isFinite(g.columns) && g.columns>=2 && g.columns<=32 && int(g.columns)===g.columns)
            return int(g.columns);
         return legacy;
      }
