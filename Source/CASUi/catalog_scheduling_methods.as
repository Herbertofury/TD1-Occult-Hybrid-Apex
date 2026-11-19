// Main-only exact owned presentation admission and native control receipts.
private function ApexCardRepairControls(panel:Object,width:Number,reflow:Boolean) : Boolean
      {
         var list:Object=panel.mcTileList;if(list==null)return false;
         var geometryChanged:Boolean=false;
         var margin:Object=list.ScrollerViewMargin;var view:Object=list.mScrollerView;var slider:Object=list.mSlider;
         var nativeGridView:Object=list.GetGridView();var geometry:Object=apexCardGeometry;
         var applied:Object=geometry.controls_width_receipt;
         // A native Sprite background stores twip geometry while the requested
         // preference remains a full Number. Reuse only an exact acknowledged
         // readback for this same request and these same live native objects.
         // Any external movement, margin change or replacement breaks it.
         var widthSettled:Boolean=applied!=null && applied.request===width && applied.panel===panel &&
            applied.list===list && applied.view===view && applied.gridView===nativeGridView && applied.slider===slider &&
            applied.background===panel.mcPanelBackground && applied.margin===margin &&
            applied.nativeWidth===Number(panel.mcPanelBackground.width) && applied.nativeWidth===Number(list.width) &&
            applied.left===Number(margin.mLeft) && applied.right===Number(margin.mRight) && applied.horizontal===Number(margin.Horizontal) &&
            applied.viewX===Number(view.x) && applied.viewWidth===Number(view.width) &&
            applied.gridWidth===Number(nativeGridView.width) && applied.sliderX===Number(slider.x) && applied.sliderWidth===Number(slider.width);
         if(!widthSettled && panel.mcPanelBackground.width!=width) {panel.width=width;geometryChanged=true;}
         var expected:Number=width-Number(margin.mRight)*0.5-Number(slider.width)*0.5;
         // Use EA's setter: it updates the scrolling mask, view, grid and bar
         // together. Never move a detached scrollbar thumb over card content.
         if(!widthSettled && (list.width!=width || view.x!=margin.mLeft || view.width!=width-margin.Horizontal ||
            nativeGridView.width!=width-margin.Horizontal || !isFinite(Number(slider.x)) || Math.abs(slider.x-expected)>0.01)) {
            list.width=width;geometryChanged=true;
         }
         if(!widthSettled) {
            geometry.controls_width_receipt=null;
            var actualWidth:Number=Number(list.width);var actualViewWidth:Number=actualWidth-Number(margin.Horizontal);
            var actualSliderX:Number=actualWidth-Number(margin.mRight)*0.5-Number(slider.width)*0.5;
            // Conservatively acknowledge only the exact nearest-twip projection.
            // This is a bounded candidate representation, not a tolerance: another
            // native projection never gains a receipt and remains normal repair.
            if(apexCardGeometry===geometry && geometry.panel===panel && geometry.grid===list.mGridLayout &&
               panel.mcTileList===list && list.mScrollerView===view && list.mSlider===slider && list.GetGridView()===nativeGridView &&
               isFinite(actualWidth) && actualWidth===Math.round(width*20)/20 && Number(panel.mcPanelBackground.width)===actualWidth &&
               Number(view.x)===Number(margin.mLeft) && Number(view.width)===actualViewWidth && Number(nativeGridView.width)===actualViewWidth &&
               isFinite(Number(slider.x)) && Number(slider.x)===Math.round(actualSliderX*20)/20)
               geometry.controls_width_receipt={request:width,panel:panel,list:list,view:view,gridView:nativeGridView,slider:slider,
                  background:panel.mcPanelBackground,margin:margin,nativeWidth:actualWidth,left:Number(margin.mLeft),right:Number(margin.mRight),
                  horizontal:Number(margin.Horizontal),viewX:Number(view.x),viewWidth:Number(view.width),gridWidth:Number(nativeGridView.width),
                  sliderX:Number(slider.x),sliderWidth:Number(slider.width)};
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

private function ApexCardApply(panel:Object,grid:Object) : Number
      {
         if(!ApexCardActivate(panel,grid))return Number(panel.mcPanelBackground.width);
         var incrementalOwned:Boolean=ApexCatalogGridOwns(grid);
         if(apexCatalogGrid!=null) {
            apexCatalogGrid.last_repair_path=incrementalOwned ? "incremental" : "legacy";
            apexCatalogGrid.last_repair_grid=grid;apexCatalogGrid.last_repair_panel=panel;
         }
         if(incrementalOwned)return ApexCardIncrementalApply(panel,grid);
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

private function ApexCatalogPanelKind(panel:Object) : String
      {
         if(panel==null || panel!==mCurrentPanel || stage==null || panel.stage!==stage ||
            panel.visible!==true || panel.mcTileList==null || panel.mcPanelBackground==null ||
            panel.mcTileList.mGridLayout==null || !ApexCatalogPanelVisible(panel)) return "";
         if(panel===mcClothingPanel || panel===mcBodyModPanel || panel===mcFaceModPanel ||
            panel===mcGenericCatalogPanel || panel===mcFeaturedFaceLookPanel) return "cards";
         // SkinTone's outer grid contains colour FAMILY rows. It must never
         // be given the card count. Its nested swatch adapter is separate.
         if(panel===mcSkinColorPanel) return "swatches";
         return "";
      }

private function ApexCatalogGridInitialize(enabled:Boolean=false) : void
      {
         // A later ordinary initializer must not disarm the early bootstrap.
         // Explicit teardown/disable uses Dispose, never a default argument.
         if(apexCatalogGrid!=null && apexCatalogGrid.enabled===true && !apexCatalogGrid.disposed) {
            ApexCatalogGridPrepare();return;
         }
         if(apexCatalogGrid!=null)ApexCatalogGridDispose();
         apexCatalogGrid={enabled:enabled,disposed:false,running:false,input_reading:false,
            generation:0,frame:0,lease:null,grid:null,last:null,error:"",invalidations:0,retiring:null};
         if(!enabled)return;
         AddMessageListener("CASSetSimInfo",ApexCatalogGridChanged);
         AddMessageListener("CASChangeMenuState",ApexCatalogGridChanged);
         AddMessageListener("CASPlannedOutfitTypeChanged",ApexCatalogGridChanged);
         AddMessageListener("CASClearSimsForReset",ApexCatalogGridChanged);
         addEventListener(flash.events.Event.ENTER_FRAME,ApexCatalogGridFrame,false,20,true);
         // Integration must call this at a proven native Initialize seam
         // before HandleSetSimInfo/Show/Refresh. The existing ApexInitialize
         // return extension is too late to prove first-publication interception.
         ApexCatalogGridPrepare();
      }

private function ApexCatalogGridPrepare() : Boolean
      {
         var s:Object=apexCatalogGrid;
         if(s==null || !s.enabled || s.disposed || s.error!="" || stage==null)return false;
         if(s.retiring!=null)return false;
         var panel:Object=mCurrentPanel;
         if(panel==null || panel.visible!==true)panel=mcClothingPanel;
         var kind:String=ApexCatalogGridProductPanel(panel);
         if(kind=="")return false;
         var grid:Object=panel.mcTileList.mGridLayout;
         if(s.grid!=null && s.grid!==grid && s.lease!=null && s.lease.phase=="bound") {
            // A new visible native panel does not authorize abandoning this
            // still-live widget's pending construction or suppression lease.
            ApexCatalogGridRetireInactive(s);return false;
         }
         if(!("ApexGridBegin" in grid) || !(grid.ApexGridBegin is Function) ||
            !(grid.ApexGridStep is Function) || !(grid.ApexGridCancel is Function) || !(grid.ApexGridStatus is Function) ||
            !(grid.ApexGridNeedsWork is Function))
            throw new Error("Native incremental catalogue adapter unavailable");
         if(s.grid===grid && s.lease!=null && s.lease.active===true && s.lease.root===this &&
            s.lease.stage===stage && s.lease.panel===panel && s.lease.feed===grid.GetDataFeed() &&
            s.lease.panel_kind===kind && s.lease.cell_type===grid.GetCellView)return true;
         if(s.grid===grid && s.lease!=null && (s.lease.stage!==stage || s.lease.panel!==panel))
            ApexCatalogGridInvalidate("display-context");
         if(s.grid===grid && s.lease!=null && s.lease.feed!==grid.GetDataFeed())ApexCatalogGridInvalidate("feed-replaced");
         if(s.grid===grid && s.lease!=null && (s.lease.panel_kind!==kind || s.lease.cell_type!==grid.GetCellView))
            ApexCatalogGridInvalidate("cell-schema");
         if(s.grid!=null && s.grid!==grid) {
            // A replacement widget owns its own display tree. Do not run the
            // retiring provider's original bulk Reset against that new tree.
            ApexCatalogGridInvalidate("grid-replaced");s.grid.ApexGridCancel("dispose");
         }
         if(s.generation>=int.MAX_VALUE)throw new Error("Catalogue lease generation exhausted");
         var lease:Object={active:true,generation:++s.generation,root:this,stage:stage,panel:panel,grid:grid,
            panel_kind:kind,cell_type:grid.GetCellView,feed:grid.GetDataFeed(),sim_id:"",household_id:"",owner:"",session:apexOwnerSession,
            layer:-1,outfit_type:-1,outfit_index:-1,state:int(mCurrState),native_generation:"",
            native_kind:0,native_mask:0,phase:"bootstrap",frame_validated:false};
         s.lease=lease;s.grid=grid;
         // Legal placeholder geometry arms native feed/input guards only.
         // This structural lease is NEVER stepped or published; measurement
         // requires the fresh bound-owner lease in Frame.
         s.last=grid.ApexGridBegin({columns:1,width:1,height:1,scale:1,gapX:0,gapY:0,
            viewWidth:1,viewHeight:1,scrollY:0,marginX:0,marginY:0,bootstrap:true,panel:panel,owner:lease,
            validate:ApexCatalogGridValidate,inputValidate:ApexCatalogGridInput,
            rowValidate:kind=="clothing" ? null : ApexCatalogGridProductRow});
         return true;
      }

private function ApexCatalogGridLeaseCurrent(lease:Object) : Boolean
      {
         var s:Object=apexCatalogGrid;
         if(s==null || !s.enabled || s.disposed || lease==null || lease!==s.lease || lease.active!==true ||
            int(lease.generation)!=int(s.generation) || lease.root!==this || lease.stage!==stage || stage==null)return false;
         // Reuse one synchronous native classifier result. Its pinned field
         // getters cannot invoke callbacks; all subsequent owner checks remain.
         var panelKind:String=ApexCatalogGridProductPanel(lease.panel);
         if(panelKind=="" || lease.panel_kind!==panelKind ||
            lease.panel.stage!==stage || lease.panel.mcTileList==null ||
            lease.grid!==lease.panel.mcTileList.mGridLayout || lease.grid!==s.grid ||
            lease.feed!==lease.grid.GetDataFeed() || lease.cell_type!==lease.grid.GetCellView)return false;
         if(lease.phase=="bootstrap")return true;
         return lease.phase=="bound" && lease.panel===mCurrentPanel && ApexCatalogPanelVisible(lease.panel) && mCurrSimInfo!=null &&
            String(mCurrSimInfo.simId)===lease.sim_id && String(mCurrSimInfo.householdId)===lease.household_id &&
            int(mCurrSimInfo.occultLayer)==lease.layer && int(mCurrSimInfo.occultType)==lease.native_kind &&
            int(mCurrSimInfo.allOccultTypes)==lease.native_mask && apexBoundSim===lease.sim_id &&
            apexFormsSelectedId===lease.owner && apexOwnerSession==lease.session &&
            apexFormsNativeGeneration===lease.native_generation && apexFormsNativeState=="bound" &&
            apexFormsDesiredId=="" && apexFormsIntent==null && apexFormsNativeIntent==null &&
            apexMoleculeIntent==null && apexPairIntent==null && !apexFormsApplying && int(mCurrState)==lease.state;
      }

private function ApexCatalogGridFrame(event:flash.events.Event=null) : void
      {
         var s:Object=apexCatalogGrid;
         if(s==null || !s.enabled || s.disposed || s.error!="" || s.running || stage==null)return;
         // Finish only owned cancellation atoms before considering a new
         // panel. No Sim query, Begin, Draw or old input can run in this lane.
         if(s.retiring!=null || !ApexCatalogPanelVisible(mCurrentPanel) || ApexCatalogGridProductPanel(mCurrentPanel)=="") {
            // Initial hidden bootstrap must keep intercepting native setup.
            // It has never driven construction/publication and is not retired.
            if(s.retiring==null && (s.lease==null || s.lease.phase!="bound"))return;
            s.running=true;
            try {ApexCatalogGridRetireInactive(s);}
            catch(inactiveError:Error) {
               s.error="Inactive catalogue cleanup paused: "+inactiveError.message;
               ApexCatalogGridInvalidate("error-abandon");
            } finally {s.running=false;}
            return;
         }
         // A coherent idle grid needs no engine reads or status allocations.
         // Write input still validates the actual current owner and outfit.
         var retained:Object=ApexCardStateFor(s.grid);
         if(s.lease!=null && ApexCatalogGridLeaseCurrent(s.lease) && s.lease.phase=="bound" &&
            retained!=null && s.lease.geometry_signature===retained.signature && retained.geometry!=null &&
            retained.geometry.grid===s.grid && retained.geometry.panel===s.lease.panel && retained.layout!=null && s.grid.ApexGridNeedsWork()===false)return;
         var started:int=flash.utils.getTimer();
         var stepStarted:int=-1;
         s.running=true;
         try {
            if(!ApexCatalogGridPrepare())return;
            var lease:Object=s.lease;
            var context:Object=lease.phase=="bound" ? ApexCatalogGridFrameObserve() : ApexCatalogGridObserve();
            if(context==null) {if(lease.phase!="bootstrap")ApexCatalogGridInvalidate("context-unsettled");return;}
            if(!ApexCatalogGridMatches(lease,context)) {
               // A changed bound outfit/category is a rebind, not permission
               // to seed another lease from the visual-only observation.
               if(lease.phase=="bound") {ApexCatalogGridInvalidate("bound-context-change");return;}
               ApexCatalogGridInvalidate("owner");
               if(s.generation>=int.MAX_VALUE)throw new Error("Catalogue lease generation exhausted");
               lease={active:true,generation:++s.generation,root:this,stage:stage,panel:s.lease.panel,grid:s.grid,
                  panel_kind:s.lease.panel_kind,cell_type:s.grid.GetCellView,feed:s.grid.GetDataFeed(),sim_id:context.sim_id,household_id:context.household_id,owner:context.owner,
                  session:context.session,layer:context.layer,native_kind:context.native_kind,shell_kind:context.shell_kind,native_mask:context.native_mask,
                  native_generation:context.native_generation,outfit_type:context.outfit_type,outfit_index:context.outfit_index,
                  state:context.state,phase:"bound",frame_validated:true};
               s.lease=lease;
            }
            lease.frame_validated=true;
            var request:Object=ApexCatalogGridRequest(lease);
            if(request==null) {s.waiting="panel-geometry";return;}
            if(s.frame<int.MAX_VALUE)s.frame++;s.last=s.grid.ApexGridBegin(request);
            retained=ApexCardStateFor(s.grid);
            lease.geometry_signature=retained==null ? "" : String(retained.signature);
            s.last=s.grid.ApexGridStep(64,(stepStarted=flash.utils.getTimer())+1);
            if(apexCatalogGrid!==s || s.disposed)return;
            if(s.last!=null && s.last.error!=null)throw new Error(String(s.last.error));
         } catch(error:Error) {
            s.error="Incremental catalogue paused: "+error.message;
            ApexCatalogGridInvalidate("error-abandon");
         } finally {
            if(s.lease!=null)s.lease.frame_validated=false;
            s.running=false;
            var elapsed:int=Math.max(0,flash.utils.getTimer()-started);
            // Split the same three existing clocks without another native
            // query, timer sample or status allocation on working frames.
            var beforeStep:int=stepStarted<0 ? elapsed : Math.max(0,stepStarted-started);
            var inStep:int=stepStarted<0 ? 0 : Math.max(0,elapsed-beforeStep);
            s.frame_pre_step_max_ms=Math.max(int(s.frame_pre_step_max_ms),beforeStep);
            s.frame_step_max_ms=Math.max(int(s.frame_step_max_ms),inStep);
            if(elapsed>=int(s.frame_max_ms)) {
               s.frame_max_pre_step_ms=beforeStep;s.frame_max_step_ms=inStep;
            }
            s.frame_max_ms=Math.max(int(s.frame_max_ms),elapsed);
            if(elapsed>1 && int(s.over_1ms)<int.MAX_VALUE)s.over_1ms=int(s.over_1ms)+1;
         }
      }

private function ApexCatalogGridStatus() : Object
      {
         var s:Object=apexCatalogGrid;
         if(s==null)return {enabled:false,active:false,appearance_written:false};
         var lease:Object=s.lease;
         var currentPanel:Object=mCurrentPanel;
         var currentList:Object=currentPanel==null || !("mcTileList" in currentPanel) ? null : currentPanel.mcTileList;
         var currentBackground:Object=currentPanel==null || !("mcPanelBackground" in currentPanel) ? null : currentPanel.mcPanelBackground;
         var currentGrid:Object=currentList==null ? null : currentList.mGridLayout;
         var currentView:Object=currentList==null ? null : currentList.GetGridView();
         var ancestry:Array=[];var ancestor:Object=currentView;var reachedRoot:Boolean=false;var containsPanel:Boolean=false;
         for(var ancestryDepth:int=0;ancestor!=null && ancestryDepth<64;ancestryDepth++) {
            ancestry.push({name:String(ancestor.name).substr(0,96),visible:ancestor.visible===true,stage_matches:ancestor.stage===stage,
               same_panel:ancestor===currentPanel,same_list:ancestor===currentList,
               same_scroller:currentList!=null && ancestor===currentList.mScrollerView,same_root:ancestor===this});
            if(ancestor===currentPanel)containsPanel=true;
            if(ancestor===this) {reachedRoot=true;break;}
            ancestor=ancestor.parent;
         }
         var geometry:Object=apexCardGeometry;var layout:Object=apexCardLayout;
         var currentGeometry:Boolean=currentGrid!=null && geometry!=null && geometry.grid===currentGrid && geometry.panel===currentPanel;
         var width:Number=currentGeometry && layout!=null ? Number(layout.width) : NaN;
         var applied:Object=currentGeometry ? geometry.controls_width_receipt : null;
         var margin:Object=currentList==null ? null : currentList.ScrollerViewMargin;
         var view:Object=currentList==null ? null : currentList.mScrollerView;
         var slider:Object=currentList==null ? null : currentList.mSlider;
         var receiptValid:Boolean=applied!=null && isFinite(width) && applied.request===width && applied.panel===currentPanel &&
            applied.list===currentList && applied.view===view && applied.gridView===currentView && applied.slider===slider &&
            applied.background===currentPanel.mcPanelBackground && applied.margin===margin &&
            applied.nativeWidth===Number(currentPanel.mcPanelBackground.width) && applied.nativeWidth===Number(currentList.width) &&
            applied.left===Number(margin.mLeft) && applied.right===Number(margin.mRight) && applied.horizontal===Number(margin.Horizontal) &&
            applied.viewX===Number(view.x) && applied.viewWidth===Number(view.width) &&
            applied.gridWidth===Number(currentView.width) && applied.sliderX===Number(slider.x) && applied.sliderWidth===Number(slider.width);
         // Deliberately omit opaque root/stage/panel/grid/feed/Function leases.
         return {enabled:Boolean(s.enabled),active:lease!=null && lease.active===true,generation:int(s.generation),
            frame:int(s.frame),running:Boolean(s.running),invalidations:int(s.invalidations),error:String(s.error),waiting_reason:s.waiting==null ? "" : String(s.waiting),
            scheduling:{current_grid_matches:currentGrid!=null && currentGrid===s.grid,current_grid_owned:currentGrid!=null && ApexCatalogGridOwns(currentGrid),
               current_panel_matches:lease!=null && lease.panel===currentPanel,lease_current:ApexCatalogGridLeaseCurrent(lease),
               current_panel_visible:ApexCatalogPanelVisible(currentPanel),panel_flag:currentPanel!=null && currentPanel.visible===true,
               list_flag:currentList!=null && currentList.visible===true,view_flag:currentView!=null && currentView.visible===true,
               list_stage_matches:currentList!=null && currentList.stage===stage,view_stage_matches:currentView!=null && currentView.stage===stage,
               reached_root:reachedRoot,contains_panel:containsPanel,ancestors:ancestry,
               card_geometry_incremental:currentGeometry && geometry.incremental===true,card_geometry_matches:currentGeometry,
               actual_repair_path:s.last_repair_grid===currentGrid && s.last_repair_panel===currentPanel ? String(s.last_repair_path) : "unobserved-current-grid",
               desired_width:isFinite(width) ? width : null,native_panel_width:currentBackground==null ? null : Number(currentBackground.width),
               native_list_width:currentList==null ? null : Number(currentList.width),native_scroller_width:view==null ? null : Number(view.width),
               native_grid_width:currentView==null ? null : Number(currentView.width),width_receipt_present:applied!=null,width_receipt_valid:receiptValid,
               retiring:s.retiring!=null},
            frame_timing:{max_ms:int(s.frame_max_ms),over_1ms:int(s.over_1ms),clock_resolution_ms:1,
               pre_step_max_ms:int(s.frame_pre_step_max_ms),step_max_ms:int(s.frame_step_max_ms),
               max_frame_parts:{pre_step_ms:int(s.frame_max_pre_step_ms),step_ms:int(s.frame_max_step_ms)}},
            context:lease==null ? null : {panel_kind:lease.panel_kind,sim_id:lease.sim_id,household_id:lease.household_id,owner:lease.owner,
               session:lease.session,layer:lease.layer,outfit_type:lease.outfit_type,outfit_index:lease.outfit_index,
               state:lease.state,native_kind:lease.native_kind,shell_kind:lease.shell_kind,native_generation:lease.native_generation,phase:lease.phase},
            native:s.grid==null ? null : s.grid.ApexGridStatus(),appearance_written:false};
      }

private function ApexCatalogPanelVisible(panel:Object) : Boolean
      {
         // This is presentation admission only. Bootstrap's structural
         // interceptor deliberately does not call it before native Show.
         if(panel==null || panel!==mCurrentPanel || stage==null || panel.stage!==stage || panel.mcTileList==null)return false;
         var list:Object=panel.mcTileList;var view:Object=list.GetGridView();
         if(view==null || list.mScrollerView==null || list.mScrollerView.stage!==stage || view.stage!==stage)return false;
         var node:Object=view;var ownsPanel:Boolean=false;
         for(var depth:int=0;node!=null && depth<64;depth++) {
            if(node.visible!==true)return false;
            if(node===panel)ownsPanel=true;
            if(node===this)return ownsPanel && panel===mCurrentPanel && panel.mcTileList===list && list.GetGridView()===view;
            node=node.parent;
         }
         return false;
      }

private function ApexCatalogGridRetireInactive(s:Object) : void
      {
         if(apexCatalogGrid!==s || s.disposed)return;
         var held:Object=s.retiring;
         if(held==null) {
            var lease:Object=s.lease;
            if(lease==null || lease.phase!="bound" || lease.root!==this || s.grid!==lease.grid)return;
            held={grid:s.grid,lease:lease,panel:lease.panel,list:lease.panel.mcTileList,
               view:lease.panel.mcTileList==null ? null : lease.panel.mcTileList.GetGridView(),stage:stage,cancelled:false};
            s.retiring=held;s.waiting="inactive-cancel";
         }
         if(s.grid!==held.grid || s.lease!==held.lease || held.lease.root!==this)
            throw new Error("Inactive catalogue ownership changed");
         if(!held.cancelled) {
            held.cancelled=true;ApexCatalogGridInvalidate("inactive");return;
         }
         // A replaced/removed widget owns its retiring display tree. Use the
         // existing terminal release path; never detach from its replacement.
         if(held.list==null || held.view==null || held.panel.stage!==held.stage || held.panel.mcTileList!==held.list ||
            held.list.mGridLayout!==held.grid || held.list.GetGridView()!==held.view) {
            s.last=held.grid.ApexGridCancel("dispose");
         } else {
            var observed:Object=held.grid.ApexGridStatus();
            if(observed==null || observed.cancelled!==true || (observed.phase!="cancel" && observed.phase!="cancelled"))
               throw new Error("Inactive catalogue did not retain its cancellation");
            if(observed.phase=="cancel") {
               s.waiting="inactive-cleanup";
               // One existing cancellation operation per frame. The provider
               // retains its native rollback/lease and pending-widget checks.
               s.last=held.grid.ApexGridStep(1,0);
            } else s.last=observed;
         }
         if(apexCatalogGrid!==s || s.disposed || s.retiring!==held || s.grid!==held.grid || s.lease!==held.lease)return;
         if(s.last!=null && s.last.error!=null)throw new Error(String(s.last.error));
         if(s.last!=null && s.last.phase=="cancelled") {
            s.lease=null;s.retiring=null;s.waiting="inactive";
         }
      }
