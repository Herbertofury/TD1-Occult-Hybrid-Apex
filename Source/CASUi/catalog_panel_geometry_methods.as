      // PRIVATE V343 STAGE: shared native catalogue geometry only. The
      // incremental provider remains owned by its separate authenticated lease.
      private var apexPanelGeometry:Object;

      private function ApexCatalogPanelKey(panel:Object) : String
      {
         if(panel==null)return "";
         if(panel===mcClothingPanel)return "clothing";
         if(panel===mcBodyModPanel)return "body";
         if(panel===mcFaceModPanel)return "face";
         if(panel===mcGenericCatalogPanel)return "generic";
         if(panel===mcFeaturedFaceLookPanel)return "featured";
         if(panel===mcSkinColorPanel)return "skin";
         return "";
      }

      private function ApexCatalogPanelKind(panel:Object) : String
      {
         if(panel==null || panel!==mCurrentPanel || stage==null || panel.stage!==stage ||
            panel.visible!==true || panel.mcTileList==null || panel.mcPanelBackground==null ||
            panel.mcTileList.mGridLayout==null) return "";
         if(panel===mcClothingPanel || panel===mcBodyModPanel || panel===mcFaceModPanel ||
            panel===mcGenericCatalogPanel || panel===mcFeaturedFaceLookPanel) return "cards";
         // SkinTone's outer grid contains colour FAMILY rows. It must never
         // be given the card count. Its nested swatch adapter is separate.
         if(panel===mcSkinColorPanel) return "swatches";
         return "";
      }

      private function ApexCatalogOptional(owner:Object,name:String) : Object
      {
         return owner!=null && name in owner ? owner[name] : null;
      }

      private function ApexCardStateFor(grid:Object) : Object
      {
         if(apexPanelGeometry==null)apexPanelGeometry={};
         var saved:Object;
         if(apexCardGeometry!=null && apexCardGeometry.grid===grid) {
            var key:String=ApexCatalogPanelKey(apexCardGeometry.panel);
            if(key=="")return null;
            saved=apexPanelGeometry[key];
            if(saved==null || saved.geometry!==apexCardGeometry) {
               saved={geometry:apexCardGeometry,layout:null,signature:"",reflow:0};apexPanelGeometry[key]=saved;
            }
            saved.layout=apexCardLayout;saved.signature=apexCatalogSignature;saved.reflow=apexCardReflowAttempts;
            return saved;
         }
         // At most six native panels, independent of Sim count and category
         // visits. A replacement grid overwrites that panel's old entry.
         for each(saved in apexPanelGeometry) {
            if(saved.geometry!=null && saved.geometry.grid===grid)return saved;
         }
         return null;
      }

      private function ApexCardActivate(panel:Object,grid:Object) : Boolean
      {
         if(ApexCatalogPanelKind(panel)=="" || panel.mcTileList.mGridLayout!==grid)return false;
         if(apexPanelGeometry==null)apexPanelGeometry={};
         if(apexCardGeometry!=null && apexCardGeometry.grid===grid && apexCardGeometry.panel===panel)return true;
         if(apexCardGeometry!=null) {
            // Retain each native grid's own geometry instead of restoring a
            // hidden two-column pool on every Body / Tattoos round trip.
            if(apexCardGeometry.applying===true)return false;
            ApexCardStateFor(apexCardGeometry.grid);
         }
         var saved:Object=apexPanelGeometry[ApexCatalogPanelKey(panel)];
         if(saved!=null && saved.geometry.panel===panel && saved.geometry.grid===grid) {
            apexCardGeometry=saved.geometry;apexCardLayout=saved.layout;
            apexCatalogSignature=String(saved.signature);apexCardReflowAttempts=int(saved.reflow);
         } else {
            apexCardGeometry=null;apexCardLayout=null;apexCatalogSignature="";apexCardReflowAttempts=0;
         }
         apexCatalogFrameCells=null;
         return true;
      }

      private function ApexCatalogVisibleRect(display:Object) : Object
      {
         if(display==null || !(display is flash.display.DisplayObject) || display.stage!==stage)return null;
         var ancestor:Object=display;
         // A child of a hidden widget is not a physical obstacle. Bound the
         // ancestry walk, and fail conservatively for an unknown hierarchy.
         for(var depth:int=0;ancestor!=null && depth<64;depth++) {
            if(ancestor.visible!==true)return null;
            ancestor=ancestor.parent;
         }
         if(ancestor!=null)return null;
         // EA Button.GetBoundsOverride uses its configured hit area; ordinary
         // getBounds includes artwork/states and is NOT that native override.
         var hit:flash.display.Sprite=display is flash.display.Sprite ? flash.display.Sprite(display).hitArea : null;
         if(hit!=null && hit.stage!==stage)throw new Error("Visible native hit area is detached from its stage");
         var r:flash.geom.Rectangle=hit==null ? display.getBounds(stage) : hit.getBounds(stage);
         if(!isFinite(r.x) || !isFinite(r.y) || !isFinite(r.width) || !isFinite(r.height) || r.width<=0 || r.height<=0)return null;
         return {x:r.x,y:r.y,width:r.width,height:r.height,bounds_source:hit==null ? "conservative-artwork" : "native-sprite-hit-area"};
      }

      private function ApexCatalogSafeRight(left:Number,top:Number,bottom:Number,viewport:Number,minimum:Number,regions:Array) : Number
      {
         if(!isFinite(left) || !isFinite(top) || !isFinite(bottom) || !isFinite(viewport) ||
            !isFinite(minimum) || minimum<=0 || bottom<=top || left<0 || left>=viewport)return 0;
         var right:Number=viewport-12;
         for each(var region:Object in regions) {
            if(region==null)continue;
            if(!isFinite(Number(region.x)) || !isFinite(Number(region.y)) ||
               !isFinite(Number(region.width)) || !isFinite(Number(region.height)) || region.width<=0 || region.height<=0)return 0;
            if(Number(region.y)>=bottom || Number(region.y)+Number(region.height)<=top)continue;
            // The original EA attachment is a left boundary, not an avatar
            // silhouette estimate. Never expand to its left. Any other widget
            // intersecting the proposed rightward band stops expansion.
            if(Number(region.x)+Number(region.width)<=left)continue;
            right=Math.min(right,Math.max(left,Number(region.x)-8));
         }
         return Math.max(0,right-left);
      }

      private function ApexCatalogNavigationRects(probe:Object=null) : Array
      {
         // Existing native API: no new Navigation handler, game read, native
         // source replacement, or cross-widget retained object is required.
         if(probe!=null)probe.reason="layout-manager-unavailable";
         if(LayoutAPI.mLayoutMgr==null)return null;
         var navigation:Object=LayoutAPI.GetLoadedWidgetByName("CASNavigation");
         if(probe!=null) {
            probe.layout_manager_present=true;probe.navigation_found=navigation!=null;
            probe.navigation_same_stage=navigation!=null && navigation.stage===stage;
            probe.navigation_widget_name=navigation==null ? null : String(navigation.WidgetName);
            probe.reason="native-navigation-root-unverified";
         }
         if(navigation==null || navigation.stage!==stage || navigation.WidgetName!=="CASNavigation" ||
            !("btnPlay" in navigation) || !("btnCancel" in navigation))return null;
         var undo:Object=ApexCatalogOptional(ApexCatalogOptional(navigation,"mcCenterPanel"),"mcUndoRedoPanel");
         if(undo==null)undo=ApexCatalogOptional(navigation,"mcUndoRedoPanel");
         var model:Object=ApexCatalogOptional(navigation,"modelNavigatorClip");
         var random:Object=ApexCatalogOptional(navigation,"mcRandomizePanel");
         var gallery:Object=ApexCatalogOptional(navigation,"mcGalleryRandomizePanel");
         var buttons:Array=[navigation.btnPlay,navigation.btnCancel,ApexCatalogOptional(navigation,"btnSaveDemo"),
            ApexCatalogOptional(navigation,"btnReset"),ApexCatalogOptional(navigation,"btnRotateSimLeft"),
            ApexCatalogOptional(navigation,"btnRotateSimRight"),ApexCatalogOptional(undo,"btnUndo"),ApexCatalogOptional(undo,"btnRedo"),
            ApexCatalogOptional(model,"btnArrowLeft"),ApexCatalogOptional(model,"btnArrowRight"),
            ApexCatalogOptional(random,"btnRandomize"),ApexCatalogOptional(random,"btnListToggle"),
            ApexCatalogOptional(gallery,"btnRandomize"),ApexCatalogOptional(gallery,"btnInfo")];
         var regions:Array=[];
         if(probe!=null)probe.reason="navigation-hit-rectangles-read";
         for each(var button:Object in buttons) {
            var rect:Object=ApexCatalogVisibleRect(button);
            if(rect!=null) {rect.kind="native-navigation-button";regions.push(rect);}
         }
         return regions;
      }

      private function ApexCatalogWidthEnvelope(panel:Object,probe:Object=null) : Object
      {
         if(probe!=null) {probe.reason="unsupported-current-panel";probe.panel_kind=ApexCatalogPanelKind(panel);}
         if(ApexCatalogPanelKind(panel)=="")return null;
         var origin:flash.geom.Point=panel.localToGlobal(new flash.geom.Point(0,0));
         var unit:flash.geom.Point=panel.localToGlobal(new flash.geom.Point(1,0));
         var list:Object=panel.mcTileList;
         // Use EA's ACTUAL clipped content mask. Its scrolling list includes
         // margins; the separate slider band is not a foreign footer region.
         var view:Object=list.mScrollerView;
         if(probe!=null) {probe.reason="native-scroll-mask-unavailable";probe.mask_present=view!=null && view.mcMask!=null;
            probe.mask_same_stage=view!=null && view.mcMask!=null && view.mcMask.stage===stage;}
         if(view==null || view.mcMask==null || view.mcMask.stage!==stage)return null;
         var content:flash.geom.Rectangle=view.mcMask.getBounds(stage);
         var scale:Number=unit.x-origin.x;
         if(probe!=null) {probe.reason="native-content-transform-invalid";probe.origin={x:origin.x,y:origin.y};
            probe.unit={x:unit.x,y:unit.y};probe.content={x:content.x,y:content.y,width:content.width,height:content.height};}
         if(!isFinite(scale) || scale<=0 || Math.abs(unit.y-origin.y)>0.01 || !isFinite(origin.x) || origin.x<0 ||
            !isFinite(content.y) || !isFinite(content.height) || content.height<=0)return null;
         var from:Number=Number(content.y);var to:Number=Number(content.y)+Number(content.height);
         // Regions are physical stage coordinates. Avatar, traits and radial
         // are protected by EA's unchanged native left attachment. They are
         // not claimed to be a measured 3-D silhouette. No game call is made.
         var regions:Array=[{kind:"avatar-native-attachment",x:0,y:0,width:origin.x,height:stage.stageHeight},
            {kind:"traits-native-left",x:0,y:0,width:origin.x,height:stage.stageHeight},
            {kind:"radial-native-left",x:0,y:0,width:origin.x,height:stage.stageHeight}];
         var navigationProbe:Object=probe==null ? null : {};
         var navigation:Array=ApexCatalogNavigationRects(navigationProbe);
         if(probe!=null) {probe.navigation=navigationProbe;probe.reason="native-navigation-unavailable";}
         if(navigation==null)return null;
         for each(var button:Object in navigation) {regions.push(button);}
         var controls:Array=[mcGhostToggle,mcWingToggle,mcBodyModSliderPanel,mcDetailedEditModePanel,
            apexCatalogUi,apexCompanion==null ? null : apexCompanion.root];
         for each(var control:Object in controls) {
            if(control==null || control===panel || control===list)continue;
            var parent:Object=control;var own:Boolean=false;
            for(var depth:int=0;parent!=null && depth<64;depth++) {
               if(parent===panel) {own=true;break;}
               parent=parent.parent;
            }
            if(own)continue;
            var rect:Object=ApexCatalogVisibleRect(control);
            if(rect!=null) {rect.kind="other-visible-control";regions.push(rect);}
         }
         // The drawer already publishes bounded visible-panel geometry. Do
         // not getBounds() its container, which includes hidden card content.
         if(apexPanels!=null && apexPanels.root!=null && apexPanels.root.visible===true && apexPanels.bounds!=null)
            regions.push(apexPanels.bounds);
         var scrollbar:flash.geom.Rectangle=list.mSlider.getBounds(panel);
         if(probe!=null) {probe.reason="native-scrollbar-invalid";probe.scrollbar={x:scrollbar.x,y:scrollbar.y,width:scrollbar.width,height:scrollbar.height};}
         if(!isFinite(scrollbar.x) || !isFinite(scrollbar.width) || scrollbar.width<=0)return null;
         var gutter:Number=Math.max(0,scrollbar.x+scrollbar.width-Number(panel.mcPanelBackground.width))+32;
         var available:Number=ApexCatalogSafeRight(origin.x,from,to,stage.stageWidth-gutter*scale+12,80*scale,regions)/scale;
         var vertical:flash.geom.Point=panel.localToGlobal(new flash.geom.Point(0,1));
         var scaleY:Number=vertical.y-origin.y;
         if(probe!=null) {probe.reason="native-vertical-transform-invalid";probe.vertical={x:vertical.x,y:vertical.y};}
         if(!isFinite(scaleY) || scaleY<=0 || Math.abs(vertical.x-origin.x)>0.01)return null;
         // The catalogue's two retained control tracks are a separate band.
         // Protect real navigation buttons there without treating the whole
         // bottom strip (or our own controls) as an occupied card rectangle.
         var controlsOrigin:flash.geom.Point=panel.localToGlobal(new flash.geom.Point(list.x,list.y+list.height+3));
         // The native track starts at list.x, which may be left of the
         // panel origin. Preserve that EXISTING attachment for this band;
         // only the synthetic left boundaries follow it. Every real native
         // button, unknown visible control and drawer rectangle stays exact.
         var controlRegions:Array=[];
         for each(var bandRegion:Object in regions) {
            if(bandRegion.kind=="avatar-native-attachment" || bandRegion.kind=="traits-native-left" || bandRegion.kind=="radial-native-left") {
               var fixedLeft:Number=Math.min(Number(bandRegion.width),controlsOrigin.x);
               if(fixedLeft>0)controlRegions.push({kind:bandRegion.kind,x:0,y:0,width:fixedLeft,height:stage.stageHeight});
            } else controlRegions.push(bandRegion);
         }
         var controlRight:Number=ApexCatalogSafeRight(controlsOrigin.x,controlsOrigin.y,controlsOrigin.y+40*scaleY,
            stage.stageWidth,80*scale,controlRegions)/scale;
         // Native track placement: half=max(90,(width-30)/2), then a
         // seven-unit gap and min(230,half) wide thumbnail track.
         var controlsMaximum:Number=controlRight<187 ? 0 : (controlRight<467 ? controlRight+23 : 2*controlRight-444);
         var contentAvailable:Number=available;
         available=Math.min(available,controlsMaximum);
         if(probe!=null) {
            probe.reason=available>=80 ? "available" : "native-protected-region-blocks-width";
            probe.ok=available>=80;probe.available=available;probe.content_available=contentAvailable;
            probe.controls_available=controlRight;probe.controls_maximum=controlsMaximum;probe.gutter=gutter;
            probe.coordinate_scale=scale;probe.controls_origin={x:controlsOrigin.x,y:controlsOrigin.y};
            probe.controls_bottom=controlsOrigin.y+40*scaleY;probe.controls_left_boundary=controlsOrigin.x;probe.regions=[];
            for each(var region:Object in regions) {
               if(probe.regions.length>=64)throw new Error("Width diagnostic region bound exceeded");
               probe.regions.push({kind:region.kind==null ? "other-visible-control" : String(region.kind),
                  x:Number(region.x),y:Number(region.y),width:Number(region.width),height:Number(region.height),
                  bounds_source:region.bounds_source==null ? "published-conservative-bounds" : String(region.bounds_source)});
            }
         }
         return {panel:panel,grid:list.mGridLayout,stage:stage,width:stage.stageWidth,height:stage.stageHeight,
            left:origin.x,scale:scale,top:from,bottom:to,available:available,regions:regions};
      }

      private function ApexCatalogWidthRequest(panel:Object) : Number
      {
         if(apexColumns==null || typeof apexColumns.preferred_width!="number" ||
            !isFinite(apexColumns.preferred_width) || Number(apexColumns.preferred_width)<80)return NaN;
         var envelope:Object=ApexCatalogWidthEnvelope(panel);
         if(envelope==null || !isFinite(envelope.available) || envelope.available<80)return NaN;
         if(!ApexCatalogWidthMode()) {
            if(apexCatalogBinding==null || mCurrSimInfo==null || !isFinite(Number(apexCatalogBinding.maximum)))return NaN;
            var saved:Object=ApexCardStateFor(panel.mcTileList.mGridLayout);
            var nativeWidth:Number=saved!=null && saved.geometry!=null && saved.geometry.panel===panel ?
               Number(saved.geometry.width) : Number(panel.mcPanelBackground.width);
            if(!isFinite(nativeWidth) || nativeWidth<80)return NaN;
            apexColumns.width_anchor=Math.max(Number(apexCatalogBinding.maximum),nativeWidth+12);
            apexColumns.width_panel=panel;apexColumns.width_sim=String(mCurrSimInfo.simId);
         }
         return Math.min(Number(apexColumns.preferred_width),Number(envelope.available));
      }

      private function ApexCatalogWidthMode() : Boolean
      {
         return apexColumns!=null && typeof apexColumns.preferred_width=="number" &&
            isFinite(apexColumns.preferred_width) && apexColumns.preferred_width>=80 &&
            typeof apexColumns.width_anchor=="number" && isFinite(apexColumns.width_anchor) &&
            apexColumns.width_panel===mCurrentPanel && mCurrSimInfo!=null && apexColumns.width_sim===String(mCurrSimInfo.simId);
      }

      private function ApexSkinToneApply(panel:Object,grid:Object) : Number
      {
         if(ApexCatalogPanelKind(panel)!="swatches" || !ApexCardActivate(panel,grid))return Number(panel.mcPanelBackground.width);
         var groups:Object=grid.GetAllDisplayObjectCells();
         if(groups==null || groups.length==0)return Number(panel.mcPanelBackground.width);
         if(groups.length>4)throw new Error("Unexpected native skin-tone family inventory");
         var width:Number=NaN;var height:Number=NaN;
         // Validate the complete group inventory before changing any of it.
         // Never change the outer grid's NumLines or flatten its feed.
         for each(var group:Object in groups) {
            if(group==null || !("ApexSwatchGroupGeometry" in group) || group.mcColorSwatchPanel==null ||
               group.mcColorSwatchPanel.mcSelectionGrid==null)
               throw new Error("Exact native skin-tone adapters unavailable");
            var nested:Object=group.mcColorSwatchPanel.mcSelectionGrid.mGridLayout;
            if(nested==null)throw new Error("Native nested swatch grid unavailable");
            var first:Object=nested.FirstCell;
            if(first==null)continue;
            var w:Number=Number(first.width)/Number(first.scaleX);var h:Number=Number(first.height)/Number(first.scaleY);
            if(!isFinite(w) || w<=0 || !isFinite(h) || h<=0)throw new Error("Native swatch measurement unavailable");
            if(isNaN(width)) {width=w;height=h;}
            else if(Math.abs(width-w)>0.01 || Math.abs(height-h)>0.01)throw new Error("Native swatch family metrics disagree");
         }
         if(isNaN(width))return Number(panel.mcPanelBackground.width);
         if(apexCardGeometry==null)apexCardGeometry={grid:grid,panel:panel,specialized:true,width:panel.mcPanelBackground.width,
            title_x:panel.txtTitle==null ? null : panel.txtTitle.x,
            random_x:ApexCatalogOptional(panel,"btnRandomize")==null ? null : ApexCatalogOptional(panel,"btnRandomize").x};
         var origin:flash.geom.Point=panel.localToGlobal(new flash.geom.Point(0,0));
         var unit:flash.geom.Point=panel.localToGlobal(new flash.geom.Point(1,0));
         var scale:Number=unit.x-origin.x;
         if(!isFinite(scale) || scale<=0)throw new Error("Native swatch viewport unavailable");
         var viewport:Number=Math.min(Number(LayoutAPI.StageWidth),Number(stage.stageWidth)/scale);
         var fit:Object=ApexCardFit(int(apexCatalogPrefs.columns),viewport,Number(apexCardPrefs.scale),
            Number(apexCardPrefs.gap_x),Number(apexCardPrefs.gap_y),width,height,ApexCatalogWidthRequest(panel));
         var changed:Boolean=false;
         for each(group in groups) {
            var result:Object=group.ApexSwatchGroupGeometry(int(fit.columns),Number(fit.scale),Number(fit.gap_x),Number(fit.gap_y),Number(fit.width)-40);
            if(result!=null && result.changed===true)changed=true;
         }
         apexCardLayout=fit;
         if(ApexCardRepairControls(panel,Number(fit.width),false))changed=true;
         if(changed) {grid.PositionCells();panel.mcTileList.height=panel.mcTileList.height;}
         apexCatalogSignature="swatches:"+fit.columns+":"+fit.scale+":"+fit.gap_x+":"+fit.gap_y+":"+fit.width;
         return Number(fit.width);
      }
