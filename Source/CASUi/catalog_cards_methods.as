      private var apexCardPrefs:Object;
      private var apexCardGeometry:Object;
      private var apexCardLayout:Object;
      private var apexCardReflowAttempts:int = 0;
      private function ApexCardRowsAligned(grid:Object,columns:int,pitch:Number) : Boolean
      {
         var cells:Object=grid.GetAllDisplayObjectCells();
         if(cells==null || cells.length==0) return true;
         var start:Number=Number(cells[0].y);
         for(var i:int=0;i<Math.min(cells.length,columns*2);i++)
            if(Math.abs(Number(cells[i].y)-start-Math.floor(i/columns)*pitch)>0.5) return false;
         return true;
      }

      private function ApexCardValidate(p:Object) : void
      {
         if(p==null || typeof p.scale!="number" || !isFinite(p.scale) || p.scale<0.65 || p.scale>1.6 ||
            typeof p.gap_x!="number" || !isFinite(p.gap_x) || p.gap_x<0 || p.gap_x>32 ||
            typeof p.gap_y!="number" || !isFinite(p.gap_y) || p.gap_y<0 || p.gap_y>32)
            throw new Error("Use card size 65-160% and independent gaps 0-32");
         apexCardPrefs={scale:Number(p.scale),gap_x:Number(p.gap_x),gap_y:Number(p.gap_y)};
         apexCatalogSaved=false;
      }

      private function ApexCardCommand(value:String) : void
      {
         var fields:Array=value.split(",");
         if(fields.length!=3) throw new Error("Complete card layout required");
         ApexCardValidate({scale:Number(fields[0]),gap_x:Number(fields[1]),gap_y:Number(fields[2])});
         ApexCatalogPersist();
         if(apexCatalogUi!=null && apexCatalogUi.visible) ApexCatalogDraw();
      }

      private function ApexCardReset() : void
      {
         // Reset the card layout, not the user's selection color or effects.
         var padding:Object=apexCardGeometry==null ? null : apexCardGeometry.padding;
         ApexCardValidate({scale:1,gap_x:padding==null ? 4 : padding.Horizontal,
            gap_y:padding==null ? 4 : padding.Vertical});
         ApexCatalogPersist();
         if(apexCatalogUi!=null && apexCatalogUi.visible) ApexCatalogDraw();
      }

      private function ApexCardRestore() : void
      {
         if(apexCardGeometry==null) return;
         var geometry:Object=apexCardGeometry;apexCardGeometry=null;apexCardLayout=null;apexCardReflowAttempts=0;
         var grid:Object=geometry.grid;
         // Stop applying our marker before restoring stock dimensions.
         for each(var cell:Object in grid.GetAllDisplayObjectCells()) {
            var marker:flash.display.DisplayObject=cell.getChildByName("apexCatalogCardScale");
            if(marker!=null) cell.removeChild(marker);
         }
         grid.CellViewSizeFallback=null;
         grid.NumLines=geometry.columns;
         // The inherited DisplayObject height setter conflicts with EA's
         // specialised getter. Uniform scale owns height; never write it.
         grid.SetCellBounds(new flash.geom.Rectangle(geometry.bounds.x,geometry.bounds.y,geometry.bounds.width,0));
         for each(cell in grid.GetAllDisplayObjectCells()) {cell.scaleX=1;cell.scaleY=1;}
         grid.SetCellPadding(geometry.padding);
         geometry.panel.width=geometry.width;
      }

      private function ApexCardScaleCells(grid:Object,scale:Number) : Boolean
      {
         var changed:Boolean=false;
         for each(var cell:Object in grid.GetAllDisplayObjectCells()) {
            if(cell.getChildByName("apexCatalogCardScale")==null) {
               var marker:flash.display.Sprite=new flash.display.Sprite();
               marker.name="apexCatalogCardScale";marker.mouseEnabled=false;marker.mouseChildren=false;
               cell.addChild(marker);changed=true;
            }
            if(Math.abs(cell.scaleX-scale)>0.000001 || Math.abs(cell.scaleY-scale)>0.000001) {
               cell.scaleX=scale;cell.scaleY=scale;changed=true;
            }
         }
         return changed;
      }

      private function ApexCardApply(panel:Object,grid:Object) : Number
      {
         if(apexCardGeometry==null || apexCardGeometry.grid!==grid) {
            ApexCardRestore();
            var bounds:flash.geom.Rectangle=grid.GetCellBounds();
            if(bounds==null || bounds.width<=0 || bounds.height<=0) throw new Error("Native card bounds unavailable");
            var nativePadding:Object=grid.GetCellPadding();
            var dimensions:Array=grid.GetGridDimensions();
            var nativeCell:Object=null;
            for each(var candidate:Object in grid.GetAllDisplayObjectCells()) {
               if(candidate!=null && candidate.scaleX>0 && candidate.width>0) {nativeCell=candidate;break;}
            }
            if(nativeCell==null) return 262;
            apexCardGeometry={grid:grid,panel:panel,bounds:bounds.clone(),padding:nativePadding,
               columns:int(dimensions[grid.Horizontal ? 0 : 1]),width:panel.mcPanelBackground.width,
               cell_width:Number(nativeCell.width)/Number(nativeCell.scaleX)};
            apexCatalogSignature="";
         }
         var base:flash.geom.Rectangle=apexCardGeometry.bounds;
         // EA measures horizontal pitch from the complete card (including its
         // frame), whereas getBounds() returns only the narrower input area.
         var naturalWidth:Number=Number(apexCardGeometry.cell_width);
         // Even two large cards must fit on a narrow supported viewport.
         var available:Number=stage.stageWidth*0.53;
         var scale:Number=Math.min(Number(apexCardPrefs.scale),
            (available-40-2*Number(apexCardPrefs.gap_x))/(2*naturalWidth));
         var pitch:Number=naturalWidth*scale+Number(apexCardPrefs.gap_x);
         var maximum:int=Math.max(2,Math.min(12,int((available-40)/pitch)));
         var columns:int=Math.min(int(apexCatalogPrefs.columns),maximum);
         var width:Number=Math.max(262,40+columns*pitch);
         var signature:String=String(mCurrState)+":"+columns+":"+stage.stageWidth+":"+scale+":"+
            apexCardPrefs.gap_x+":"+apexCardPrefs.gap_y;
         if(signature!=apexCatalogSignature) {
            ApexCatalogClearEffects();apexCatalogSignature=signature;
            apexCardReflowAttempts=0;
            grid.NumLines=columns;
            grid.CellViewSizeFallback=new flash.geom.Point(naturalWidth*scale,base.height*scale);
            ApexCardScaleCells(grid,scale);
            // Bounds also size subsequently recycled cells. Set final uniform
            // scale explicitly: native height has a specialised getter.
            grid.SetCellBounds(new flash.geom.Rectangle(base.x,base.y,naturalWidth*scale,0));
            ApexCardScaleCells(grid,scale);
            grid.SetCellPadding(new Margin(0,0,apexCardPrefs.gap_y,apexCardPrefs.gap_x));
            panel.width=width;
            ApexCardScaleCells(grid,scale);grid.ResetAndPositionCells();
            if(apexCatalogLayoutChanges<int.MAX_VALUE) apexCatalogLayoutChanges++;
            apexCardLayout={scale:scale,gap_x:Number(apexCardPrefs.gap_x),gap_y:Number(apexCardPrefs.gap_y),
               card_width:naturalWidth*scale,card_height:base.height*scale,hit_width:base.width*scale,pitch_x:pitch,
               pitch_y:base.height*scale+Number(apexCardPrefs.gap_y),columns:columns,width:width};
         } else if(ApexCardScaleCells(grid,scale)) grid.ResetAndPositionCells();
         // A native draw can publish its dimensions after the first layout.
         // Reset the stock row cache explicitly: PositionCells(false) preserves
         // an uninitialised NaN anchor after the recycling pool resizes.
         // Repair actual row coordinates, with a finite convergence bound;
         // never turn a failed resize into an endless idle layout loop.
         if(!ApexCardRowsAligned(grid,columns,base.height*scale+Number(apexCardPrefs.gap_y))) {
            if(++apexCardReflowAttempts>30) throw new Error("Native card rows did not converge to their measured height");
            grid.ResetAndPositionCells();
         } else apexCardReflowAttempts=0;
         return width;
      }

      private function ApexCardReadback() : Array
      {
         var rows:Array=[];
         if(apexCardGeometry==null) return rows;
         // Bounded diagnostic sampling on a requested readback, not each frame.
         for each(var cell:Object in apexCardGeometry.grid.GetAllDisplayObjectCells()) {
            if(!cell.visible) continue;
            var bounds:flash.geom.Rectangle=cell.mcHitArea.getBounds(cell.parent);
            rows.push({scale_x:cell.scaleX,scale_y:cell.scaleY,reported_height:cell.height,
               grid_height:apexCardGeometry.grid.CalculateCellViewHeight(cell as flash.display.DisplayObject),
               root_width:cell.width,root_x:cell.x,root_y:cell.y,
               local_width:cell.mcHitArea.width*cell.scaleX,local_height:cell.mcHitArea.height*cell.scaleY,
               x:bounds.x,y:bounds.y,width:bounds.width,height:bounds.height,
               marker:cell.getChildByName("apexCatalogCardScale")!=null,selected:cell.Selected});
            if(rows.length>=24) break;
         }
         return rows;
      }

      private function ApexCardGridReadback() : Object
      {
         if(apexCardGeometry==null) return null;
         var grid:Object=apexCardGeometry.grid;
         var padding:Object=grid.GetCellPadding();
         var bounds:flash.geom.Rectangle=grid.GetLayoutBounds();
         return {dimensions:grid.GetGridDimensions(),horizontal:grid.Horizontal,
            gap_x:padding.Horizontal,gap_y:padding.Vertical,layout_width:bounds.width,layout_height:bounds.height,
            row_reflow_attempts:apexCardReflowAttempts};
      }
