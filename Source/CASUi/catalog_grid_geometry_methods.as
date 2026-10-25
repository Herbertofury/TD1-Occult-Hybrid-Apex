      // Geometry only for a grid owned by the explicit incremental lease.
      // Native construction/attachment/sizing/Draw remains in its bounded job.
      private function ApexCardIncrementalApply(panel:Object,grid:Object) : Number
      {
         var native:Object=grid.ApexGridStatus();
         if(native==null || native.measurement_ready!==true) {
            apexCardLayout=null;
            return Number(panel.mcPanelBackground.width);
         }
         var naturalWidth:Number=Number(native.natural_width);
         var naturalHeight:Number=Number(native.natural_height);
         var aspect:Number=Number(native.natural_aspect);
         if(!isFinite(naturalWidth) || naturalWidth<=0 || !isFinite(naturalHeight) || naturalHeight<=0 ||
            !isFinite(aspect) || aspect<=0)throw new Error("Native card measurement unavailable");
         if(apexCardGeometry!=null && apexCardGeometry.grid!==grid) {
            if(apexCardGeometry.incremental!==true)throw new Error("Cannot replace a live legacy geometry transaction");
            ApexCardForget();
            if(apexCardGeometry!=null)return Number(panel.mcPanelBackground.width);
         }
         if(apexCardGeometry==null) {
            // GetCellBounds may construct a second probe when the native
            // height is zero. Use the retained real cell's intrinsic metrics.
            apexCardGeometry={grid:grid,panel:panel,incremental:true,
               bounds:new flash.geom.Rectangle(0,0,naturalWidth,naturalHeight),padding:grid.GetCellPadding(),
               width:panel.mcPanelBackground.width,columns:int(native.columns),cell_width:naturalWidth,
               title_x:panel.txtTitle==null ? null : panel.txtTitle.x,random_x:panel.btnRandomize==null ? null : panel.btnRandomize.x,
               filter_width:panel.mcFilterPane==null ? null : panel.mcFilterPane.mcFilterBubble.mcBackground.width};
            apexCatalogSignature="";
         }
         var geometry:Object=apexCardGeometry;
         if(geometry.applying===true)return Number(panel.mcPanelBackground.width);
         geometry.applying=true;
         try {
            var origin:flash.geom.Point=panel.localToGlobal(new flash.geom.Point(0,0));
            var unit:flash.geom.Point=panel.localToGlobal(new flash.geom.Point(1,0));
            var unitWidth:Number=Math.abs(unit.x-origin.x);
            var viewportWidth:Number=Math.min(Number(LayoutAPI.StageWidth),Number(stage.stageWidth)/unitWidth);
            if(!isFinite(unitWidth) || unitWidth<=0 || !isFinite(viewportWidth) || viewportWidth<=0)
               throw new Error("Native catalogue viewport unavailable");
            var fitted:Object=ApexCardFit(int(apexCatalogPrefs.columns),viewportWidth,Number(apexCardPrefs.scale),
               Number(apexCardPrefs.gap_x),Number(apexCardPrefs.gap_y),naturalWidth,naturalHeight);
            var rowHeight:Number=naturalHeight*Number(fitted.scale)*aspect;
            if(isFinite(Number(native.measured_scale)) && Number(native.measured_scale)==Number(fitted.scale) &&
               isFinite(Number(native.measured_height)) && Number(native.measured_height)>0)
               rowHeight=Number(native.measured_height);
            if(!isFinite(rowHeight) || rowHeight<=0)throw new Error("Native card row height unavailable");
            fitted.card_height=rowHeight;fitted.pitch_y=rowHeight+Number(fitted.gap_y);
            // Full-card metrics do not attest the separate native input mask.
            // Requested readbacks inspect that mask on the real bound cells.
            fitted.hit_width=null;
            var signature:String="cards:"+fitted.columns+":"+viewportWidth+":"+fitted.scale+":"+
               fitted.gap_x+":"+fitted.gap_y+":"+naturalWidth+":"+naturalHeight+":"+rowHeight;
            var changed:Boolean=signature!=apexCatalogSignature;
            if(changed)ApexCatalogClearEffects();
            apexCardLayout=fitted;geometry.cell_width=naturalWidth;geometry.row_height=rowHeight;
            // These native control setters can emit layout/resize events. The
            // authenticated grid adapter coalesces them under its own lease;
            // Main never acquires/releases the provider's suppression flag.
            ApexCardRepairControls(panel,Number(fitted.width),changed);
            var donor:Object=apexCompanion==null ? null : apexCompanion.layout_owner;
            if(donor!=null && apexCompanion.donor!=null) {
               donor.modded_numcolumns=int(fitted.columns);donor.modded_thumbnail_scale=Number(fitted.scale);
               donor.modded_catalog_width=Number(fitted.width);apexCompanion.layout_seen=true;
               apexCompanion.layout_columns=int(fitted.columns);apexCompanion.layout_scale=Number(fitted.scale);
            }
            if(changed && apexCatalogLayoutChanges<int.MAX_VALUE)apexCatalogLayoutChanges++;
            apexCatalogSignature=signature;apexCardReflowAttempts=0;
            return Number(fitted.width);
         } finally {geometry.applying=false;}
      }
