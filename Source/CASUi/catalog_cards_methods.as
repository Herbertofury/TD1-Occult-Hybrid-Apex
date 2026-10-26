      private var apexCardPrefs:Object;
      private var apexCardGeometry:Object;
      private var apexCardLayout:Object;
      private var apexCardReflowAttempts:int = 0;
      private var apexCatalogFrameCells:Object;
      private function ApexCatalogCells(grid:Object) : Object
      {
         if(apexCatalogFrameCells==null || apexCatalogFrameCells.grid!==grid)
            apexCatalogFrameCells={grid:grid,cells:grid.GetAllDisplayObjectCells()};
         return apexCatalogFrameCells.cells;
      }
      private function ApexCardRowsAligned(grid:Object,columns:int,pitch:Number,pitchX:Number=0) : Boolean
      {
         var cells:Object=ApexCatalogCells(grid);
         if(cells==null || cells.length==0) return true;
         var start:Number=Number(cells[0].y);var left:Number=Number(cells[0].x);
         if(!isFinite(start) || !isFinite(left) || !isFinite(pitch) || pitch<=0 ||
            !isFinite(pitchX) || pitchX<0) return false;
         for(var i:int=0;i<Math.min(cells.length,columns*2);i++) {
            var x:Number=Number(cells[i].x);var y:Number=Number(cells[i].y);
            if(!isFinite(x) || !isFinite(y) || Math.abs(y-start-Math.floor(i/columns)*pitch)>0.5 ||
               pitchX>0 && Math.abs(x-left-(i%columns)*pitchX)>0.5) return false;
         }
         return true;
      }

      private function ApexCardValidate(p:Object) : void
      {
         if(p==null || typeof p.scale!="number" || !isFinite(p.scale) || p.scale<0.2 || p.scale>1.6 ||
            typeof p.gap_x!="number" || !isFinite(p.gap_x) || p.gap_x<0 || p.gap_x>32 ||
            typeof p.gap_y!="number" || !isFinite(p.gap_y) || p.gap_y<0 || p.gap_y>32)
            throw new Error("Use card size 20-160% and independent gaps 0-32");
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

      private function ApexCardForget() : void
      {
         // EA has already retired catalogue tuning during widget unload.
         // The retiring widget owns these cells; do not reflow or redraw them.
         apexCardGeometry=null;apexCardLayout=null;apexCardReflowAttempts=0;
      }

      private function ApexCardRestore() : void
      {
         if(apexCardGeometry==null) return;
         var geometry:Object=apexCardGeometry;
         var grid:Object=geometry.grid;
         if(geometry.incremental===true || geometry.specialized===true) {
            // The controller owns retirement/rebinding. Never bulk-reset an
            // active or retired incremental pool from the legacy restore path.
            ApexCardForget();return;
         }
         // Respect an EA/other-mod layout transaction. Never release a lease
         // we did not acquire or leave a half-restored recycling pool.
         if(grid.SuppressUpdates===true || geometry.applying===true)return;
         geometry.applying=true;
         try {
         grid.SuppressUpdates=true;
         try {
         // Keep the empty marker's donor aspect across the native width
         // setter, which changes X alone. Suppression prevents intermediate
         // positioning; remove our marker before the final native redraw.
         grid.CellViewSizeFallback=null;
         grid.NumLines=geometry.columns;
         // The inherited DisplayObject height setter conflicts with EA's
         // specialised getter. The donor aspect owns height; never write it.
         grid.SetCellBounds(new flash.geom.Rectangle(geometry.bounds.x,geometry.bounds.y,geometry.bounds.width,0));
         for each(var cell:Object in ApexCatalogCells(grid)) {
            var marker:flash.display.DisplayObject=cell.getChildByName("apexCatalogCardScale");
            var aspect:Number=marker==null ? Number(cell.scaleY)/Number(cell.scaleX) : marker.scaleY;
            if(!isFinite(aspect) || aspect<=0) throw new Error("Native card aspect unavailable");
            cell.scaleX=1;cell.scaleY=aspect;
            if(marker!=null) cell.removeChild(marker);
         }
         grid.SetCellPadding(geometry.padding);
         var lastWidth:Number=Number(geometry.controls_width);
         if(geometry.panel.txtTitle!=null && geometry.title_x!=null &&
            geometry.panel.txtTitle.x==Number(geometry.title_x)+(lastWidth-Number(geometry.width))*0.5)
            geometry.panel.txtTitle.x=Number(geometry.title_x);
         if(ApexCatalogOptional(geometry.panel,"btnRandomize")!=null && geometry.random_x!=null &&
            ApexCatalogOptional(geometry.panel,"btnRandomize").x==Number(geometry.random_x)+lastWidth-Number(geometry.width))
            ApexCatalogOptional(geometry.panel,"btnRandomize").x=Number(geometry.random_x);
         var filter:Object=geometry.panel.mcFilterPane;
         if(filter!=null && filter.mcFilterBubble!=null && geometry.filter_width!=null && filter.mcFilterBubble.mcBackground.width==lastWidth-30)
            filter.mcFilterBubble.mcBackground.width=Number(geometry.filter_width);
         geometry.panel.width=geometry.width;
         geometry.panel.mcTileList.ScrollerAmount=Math.max(10,geometry.bounds.height*0.75);
         if(apexCompanion!=null && apexCompanion.donor!=null)apexCompanion.donor.PositionButton(geometry.panel);
         } finally {grid.SuppressUpdates=false;}
         apexCatalogFrameCells=null;
         ApexLayoutReset(grid);
         apexCardGeometry=null;apexCardLayout=null;apexCardReflowAttempts=0;apexCatalogSignature="";
         } finally {geometry.applying=false;}
      }

      private function ApexCardFit(columns:int,stageWidth:Number,scale:Number,gapX:Number,gapY:Number,naturalWidth:Number,naturalHeight:Number,availableOverride:Number=-1) : Object
      {
         // The native attachment remains authoritative. Reserve the left
         // 60% of the actual viewport for the Sim and its controls; extra
         // columns shrink within the catalogue instead of covering the Sim.
         // Its default maximum is the compact six-card footprint, independent
         // of the chosen count, requested size or requested spacing.
         var nominal:Number=40+6*(naturalWidth+4);
         var available:Number=Math.max(80,Math.min(nominal,stageWidth*0.40-12));
         var explicitWidth:Boolean=isFinite(availableOverride) && availableOverride>=80;
         if(explicitWidth)available=Math.max(80,Math.min(availableOverride,stageWidth-24));
         var content:Number=available-40;
         // Keep the requested count even at 12+ columns. An automatic fit may
         // go below the user's size-slider minimum. If gaps alone would fill
         // the region, reserve at least half of every pitch for the card.
         var fittedGap:Number=Math.min(gapX,content/(columns*2));
         var size:Number=Math.min(scale,(content-columns*fittedGap)/(columns*naturalWidth));
         var pitch:Number=naturalWidth*size+fittedGap;
         return {scale:size,gap_x:fittedGap,gap_y:gapY,card_width:naturalWidth*size,card_height:naturalHeight*size,
            pitch_x:pitch,pitch_y:naturalHeight*size+gapY,columns:columns,width:explicitWidth ? available : Math.max(Math.min(262,available),40+columns*pitch),
            right_growth:explicitWidth,
            requested_columns:columns,requested_scale:scale,requested_gap_x:gapX,available_width:available,
            columns_fit:true,size_fitted:size<scale-0.000001,gap_x_fitted:fittedGap<gapX-0.000001};
      }

      private function ApexCardRepairControls(panel:Object,width:Number,reflow:Boolean) : Boolean
      {
         var list:Object=panel.mcTileList;if(list==null)return false;
         var geometryChanged:Boolean=false;
         var margin:Object=list.ScrollerViewMargin;var view:Object=list.mScrollerView;var slider:Object=list.mSlider;
         if(panel.mcPanelBackground.width!=width) {panel.width=width;geometryChanged=true;}
         var expected:Number=width-Number(margin.mRight)*0.5-Number(slider.width)*0.5;
         // Use EA's setter: it updates the scrolling mask, view, grid and bar
         // together. Never move a detached scrollbar thumb over card content.
         if(list.width!=width || view.x!=margin.mLeft || view.width!=width-margin.Horizontal ||
            list.GetGridView().width!=width-margin.Horizontal || !isFinite(Number(slider.x)) || Math.abs(slider.x-expected)>0.01) {
            list.width=width;geometryChanged=true;
         }
         if(reflow) {
            // Recompute range at the retained scroll value through EA's own
            // lifecycle. Its scroll event also dismisses obsolete swatch-popup
            // anchors; newly opened native swatch/detail popups stay full size.
            list.height=list.height;
         }
         if(apexCardLayout!=null)list.ScrollerAmount=Math.max(16,Number(apexCardLayout.pitch_y)*0.75);
         var filter:Object=panel.mcFilterPane;
         if(filter!=null && filter.mcFilterBubble!=null && filter.mcFilterBubble.mcBackground.width!=width-30)
            filter.mcFilterBubble.mcBackground.width=width-30;
         var moved:Boolean=false;
         if(panel.txtTitle!=null && apexCardGeometry.title_x!=null) {
            var titleX:Number=Number(apexCardGeometry.title_x)+(width-Number(apexCardGeometry.width))*0.5;
            if(panel.txtTitle.x!=titleX) {panel.txtTitle.x=titleX;moved=true;}
         }
         if(ApexCatalogOptional(panel,"btnRandomize")!=null && apexCardGeometry.random_x!=null) {
            var randomX:Number=Number(apexCardGeometry.random_x)+width-Number(apexCardGeometry.width);
            if(ApexCatalogOptional(panel,"btnRandomize").x!=randomX) {ApexCatalogOptional(panel,"btnRandomize").x=randomX;moved=true;}
         }
         if((reflow || moved) && apexCompanion!=null && apexCompanion.donor!=null)apexCompanion.donor.PositionButton(panel);
         apexCardGeometry.controls_width=width;
         return geometryChanged;
      }

      private function ApexCardScaleCells(grid:Object,scale:Number,preserveAspect:Boolean=true) : Boolean
      {
         var changed:Boolean=false;
         for each(var cell:Object in ApexCatalogCells(grid)) {
            var marker:flash.display.DisplayObject=cell.getChildByName("apexCatalogCardScale");
            var aspect:Number=Number(cell.scaleY)/Number(cell.scaleX);
            if(!preserveAspect && marker!=null) aspect=marker.scaleY;
            if(!isFinite(aspect) || aspect<=0) throw new Error("Native card aspect unavailable");
            if(marker==null) {
               var added:flash.display.Sprite=new flash.display.Sprite();
               added.name="apexCatalogCardScale";added.mouseEnabled=false;added.mouseChildren=false;
               cell.addChild(added);marker=added;changed=true;
            }
            // Empty marker transforms are geometry metadata only. Retain the
            // donor's live aspect (for example eyebrow cards), including when
            // SetCellBounds temporarily changes only the X transform.
            if(marker.scaleY!=aspect)marker.scaleY=aspect;
            var heightScale:Number=scale*aspect;
            if(Math.abs(cell.scaleX-scale)>0.000001 || Math.abs(cell.scaleY-heightScale)>0.000001) {
               cell.scaleX=scale;cell.scaleY=heightScale;changed=true;
            }
         }
         return changed;
      }

      private function ApexCardApply(panel:Object,grid:Object) : Number
      {
         if(!ApexCardActivate(panel,grid))return Number(panel.mcPanelBackground.width);
         if(ApexCatalogGridOwns(grid))return ApexCardIncrementalApply(panel,grid);
         if(grid.SuppressUpdates===true || apexCardGeometry!=null && apexCardGeometry.applying===true)
            return Number(panel.mcPanelBackground.width);
         var donor:Object=apexCompanion==null ? null : apexCompanion.layout_owner;
         // Donor controls now queue values through named UI services. Never
         // read its transient reset-to-zero or fitted values back as user
         // preferences; that feedback caused competing layouts on navigation.
         if(apexCardGeometry==null || apexCardGeometry.grid!==grid) {
            if(apexCardGeometry!=null)return Number(panel.mcPanelBackground.width);
            var bounds:flash.geom.Rectangle=grid.GetCellBounds();
            if(bounds==null || bounds.width<=0 || bounds.height<=0) throw new Error("Native card bounds unavailable");
            var nativePadding:Object=grid.GetCellPadding();
            var dimensions:Array=grid.GetGridDimensions();
            var nativeCell:Object=null;
            for each(var candidate:Object in ApexCatalogCells(grid)) {
               if(candidate!=null && candidate.scaleX>0 && candidate.width>0) {nativeCell=candidate;break;}
            }
            if(nativeCell==null) return 262;
            apexCardGeometry={grid:grid,panel:panel,bounds:bounds.clone(),padding:nativePadding,
               columns:int(dimensions[grid.Horizontal ? 0 : 1]),width:panel.mcPanelBackground.width,
               title_x:panel.txtTitle==null ? null : panel.txtTitle.x,random_x:ApexCatalogOptional(panel,"btnRandomize")==null ? null : ApexCatalogOptional(panel,"btnRandomize").x,
               filter_width:panel.mcFilterPane==null ? null : panel.mcFilterPane.mcFilterBubble.mcBackground.width,
               cell_width:Number(nativeCell.width)/Number(nativeCell.scaleX)};
            apexCatalogSignature="";
         }
         var geometry:Object=apexCardGeometry;geometry.applying=true;
         try {
         var base:flash.geom.Rectangle=geometry.bounds;
         // EA measures horizontal pitch from the complete card (including its
         // frame), whereas getBounds() returns only the narrower input area.
         var naturalWidth:Number=Number(apexCardGeometry.cell_width);
         // Native UI size and physical stage pixels can differ with UI scale.
         // Bound the region in this panel's actual local units, while retaining
         // EA's logical safe-area width for its native attachment/clamp.
         var origin:flash.geom.Point=panel.localToGlobal(new flash.geom.Point(0,0));
         var unit:flash.geom.Point=panel.localToGlobal(new flash.geom.Point(1,0));
         var unitWidth:Number=Math.abs(unit.x-origin.x);
         var viewportWidth:Number=Math.min(Number(LayoutAPI.StageWidth),Number(stage.stageWidth)/unitWidth);
         if(!isFinite(unitWidth) || unitWidth<=0 || !isFinite(viewportWidth) || viewportWidth<=0)
            throw new Error("Native catalogue viewport unavailable");
         var fitted:Object=ApexCardFit(int(apexCatalogPrefs.columns),viewportWidth,Number(apexCardPrefs.scale),
            Number(apexCardPrefs.gap_x),Number(apexCardPrefs.gap_y),naturalWidth,base.height,ApexCatalogWidthRequest(panel));
         var scale:Number=Number(fitted.scale);
         var pitch:Number=naturalWidth*scale+Number(fitted.gap_x);
         var columns:int=int(fitted.columns);var width:Number=Number(fitted.width);
         var currentCells:Object=ApexCatalogCells(grid);
         var rowHeight:Number=base.height*scale;
         if(currentCells!=null && currentCells.length>0) {
            var first:Object=currentCells[0];
            var hit:Object=ApexCatalogOptional(first,"mcHitArea");
            var localHeight:Number=hit==null ? base.height : Number(hit.height);
            var aspect:Number=Number(first.scaleY)/Number(first.scaleX);
            if(!isFinite(localHeight) || localHeight<=0 || !isFinite(aspect) || aspect<=0)
               throw new Error("Native card row height unavailable");
            rowHeight=localHeight*scale*aspect;
         }
         if(!isFinite(rowHeight) || rowHeight<=0) throw new Error("Native card row height unavailable");
         // GFx rounds native coordinates to twips. Do not turn sub-twip
         // transform noise into a repeated geometry transaction.
         if(geometry.row_height!=null && Math.abs(rowHeight-Number(geometry.row_height))<=0.05+0.000001)
            rowHeight=Number(geometry.row_height);
         fitted.card_height=rowHeight;fitted.pitch_y=rowHeight+Number(apexCardPrefs.gap_y);
         if(donor!=null && apexCompanion.donor!=null) {
            donor.modded_numcolumns=columns;donor.modded_thumbnail_scale=scale;donor.modded_catalog_width=width;
            apexCompanion.layout_seen=true;apexCompanion.layout_columns=columns;apexCompanion.layout_scale=scale;
         }
         // Category identity is not geometry. Retain the fitted pool across
         // category changes; newly recycled cells are still scaled below.
         var signature:String="cards:"+columns+":"+viewportWidth+":"+scale+":"+
            apexCardPrefs.gap_x+":"+apexCardPrefs.gap_y+":"+width;
         var actualDimensions:Array=grid.GetGridDimensions();
         var reflow:Boolean=signature!=apexCatalogSignature || int(actualDimensions[grid.Horizontal ? 0 : 1])!=columns ||
            geometry.row_height==null || Math.abs(rowHeight-Number(geometry.row_height))>0.05+0.000001;
         var redraw:Boolean=reflow;
         // Native dimension setters synchronously PositionCells/Draw. Commit
         // the complete geometry under EA's own suppression flag, then bind
         // the final visible pool once. No item/Sim appearance is cached.
         grid.SuppressUpdates=true;
         try {
          if(reflow) {
            ApexCatalogClearEffects();
            apexCardReflowAttempts=0;
            grid.NumLines=columns;
            grid.CellViewSizeFallback=new flash.geom.Point(naturalWidth*scale,rowHeight);
            ApexCardScaleCells(grid,scale);
            // Bounds size new recycled cells. Keep the live donor aspect
            // while repairing the width setter's temporary X-only scaling.
            grid.SetCellBounds(new flash.geom.Rectangle(base.x,base.y,naturalWidth*scale,0));
            ApexCardScaleCells(grid,scale,false);
            grid.SetCellPadding(new Margin(0,0,apexCardPrefs.gap_y,fitted.gap_x));
            panel.width=width;
          } else ApexCardScaleCells(grid,scale);
         apexCardLayout=fitted;apexCardLayout.hit_width=base.width*scale;
         if(ApexCardRepairControls(panel,width,reflow))redraw=true;
         } finally {grid.SuppressUpdates=false;}
         if(redraw) {
            // SetupCells can grow or shrink the pool. Retire the frame-local
            // enumeration before and after binding to include its new cells.
            apexCatalogFrameCells=null;ApexLayoutReset(grid);apexCatalogFrameCells=null;
            ApexCardScaleCells(grid,scale);
            apexCatalogSignature=signature;geometry.row_height=rowHeight;
            if(reflow && apexCatalogLayoutChanges<int.MAX_VALUE)apexCatalogLayoutChanges++;
         }
         // A native draw can publish its dimensions after the first layout.
         // Reset the stock row cache explicitly: PositionCells(false) preserves
         // an uninitialised NaN anchor after the recycling pool resizes.
         // Repair actual row coordinates, with a finite convergence bound;
         // never turn a failed resize into an endless idle layout loop.
         if(!ApexCardRowsAligned(grid,columns,Number(fitted.pitch_y),Number(fitted.pitch_x))) {
            if(++apexCardReflowAttempts>30) throw new Error("Native card rows did not converge to their measured height");
            ApexLayoutReset(grid);
         } else apexCardReflowAttempts=0;
         return width;
         } finally {geometry.applying=false;}
      }

      private function ApexCardReadback() : Array
      {
         var rows:Array=[];
         if(apexCardGeometry==null || apexCardGeometry.panel!==mCurrentPanel) return rows;
         // Bounded diagnostic sampling on a requested readback, not each frame.
         if(apexCardGeometry.specialized===true) {
            var groups:Object=apexCardGeometry.grid.GetAllDisplayObjectCells();var family:int=0;
            for each(var group:Object in groups) {
               if(family>=4)break;
               var nested:Object=group.mcColorSwatchPanel.mcSelectionGrid.mGridLayout;
               var nativeBounds:flash.geom.Rectangle=nested.GetCellBounds();
               for each(var swatch:Object in nested.GetAllDisplayObjectCells()) {
                  if(!swatch.visible)continue;
                  var swatchBounds:flash.geom.Rectangle=swatch.getBounds(swatch.parent);
                  rows.push({family_group:family,scale_x:swatch.scaleX,scale_y:swatch.scaleY,reported_height:swatch.height,
                     grid_height:nativeBounds.height,root_width:swatch.width,root_x:swatch.x,root_y:swatch.y,
                     local_width:swatchBounds.width,local_height:swatchBounds.height,x:swatchBounds.x,y:swatchBounds.y,
                     width:swatchBounds.width,height:swatchBounds.height,marker:false,selected:ApexCatalogOptional(swatch,"Selected")});
                  if(rows.length>=24)return rows;
               }
               family++;
            }
            return rows;
         }
         for each(var cell:Object in apexCardGeometry.grid.GetAllDisplayObjectCells()) {
            if(!cell.visible) continue;
            var hit:Object=ApexCatalogOptional(cell,"mcHitArea");
            if(hit==null)hit=cell;
            var bounds:flash.geom.Rectangle=hit.getBounds(cell.parent);
            rows.push({scale_x:cell.scaleX,scale_y:cell.scaleY,reported_height:cell.height,
               grid_height:apexCardGeometry.grid.CalculateCellViewHeight(cell as flash.display.DisplayObject),
               root_width:cell.width,root_x:cell.x,root_y:cell.y,
               local_width:bounds.width,local_height:bounds.height,
               x:bounds.x,y:bounds.y,width:bounds.width,height:bounds.height,
               marker:cell.getChildByName("apexCatalogCardScale")!=null,selected:cell.Selected});
            if(rows.length>=24) break;
         }
         return rows;
      }

      private function ApexCardGridReadback() : Object
      {
         if(apexCardGeometry==null) return null;
         if(apexCardGeometry.panel!==mCurrentPanel)return null;
         var grid:Object=apexCardGeometry.grid;var families:Array=null;var outer:Array=null;var cellCount:int=0;
         if(apexCardGeometry.specialized===true) {
            outer=grid.GetGridDimensions();families=[];
            for each(var group:Object in grid.GetAllDisplayObjectCells()) {
               if(families.length>=4)break;
               var nested:Object=group.mcColorSwatchPanel.mcSelectionGrid.mGridLayout;
               var nativeBounds:flash.geom.Rectangle=nested.GetLayoutBounds();var nativePadding:Object=nested.GetCellPadding();
               var count:int=int(nested.GetAllDisplayObjectCells().length);cellCount+=count;
               families.push({dimensions:nested.GetGridDimensions(),physical_cell_count:count,gap_x:nativePadding.Horizontal,
                  gap_y:nativePadding.Vertical,layout_width:nativeBounds.width,layout_height:nativeBounds.height});
               if(families.length==1)grid=nested;
            }
            if(families.length==0)return null;
         } else cellCount=int(grid.GetAllDisplayObjectCells().length);
         var padding:Object=grid.GetCellPadding();
         var bounds:flash.geom.Rectangle=grid.GetLayoutBounds();
         var list:Object=apexCardGeometry.panel.mcTileList;var slider:Object=list.mSlider;var view:Object=list.mScrollerView;
         var bar:flash.geom.Rectangle=slider.getBounds(stage);var mask:flash.geom.Rectangle=view.mcMask.getBounds(stage);
         return {dimensions:grid.GetGridDimensions(),dimension_scope:families==null ? "current-native-card-grid" : "first-nested-skin-family",
            outer_family_dimensions:outer,swatch_families:families,physical_cell_count:cellCount,horizontal:grid.Horizontal,
            native_grid_provider:("ApexGridProviderIdentity" in grid) ? grid.ApexGridProviderIdentity() : "unidentified",
            gap_x:padding.Horizontal,gap_y:padding.Vertical,layout_width:bounds.width,layout_height:bounds.height,
            scroll_list_width:list.width,scroll_list_height:list.height,scroll_view_width:view.width,scroll_view_height:view.height,grid_view_width:list.GetGridView().width,
            scrollbar:{x:bar.x,y:bar.y,width:bar.width,height:bar.height,local_x:slider.x,visible:slider.visible,mouse_enabled:slider.mouseEnabled,
               value:slider.Value,min:slider.MinValue,max:slider.MaxValue},
            scroll_mask:{x:mask.x,y:mask.y,width:mask.width,height:mask.height},
            row_reflow_attempts:apexCardReflowAttempts};
      }
