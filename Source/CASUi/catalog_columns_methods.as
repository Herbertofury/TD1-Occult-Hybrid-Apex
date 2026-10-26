      // A single geometry owner: preserve donor controls, queue their values,
      // and let Apex's recycled-cell layout apply one final change per frame.
      private var apexColumns:Object;

      private function ApexColumnsInitialize() : void
      {
         apexColumns={root:null,track:null,fallback_track:null,width_handle:null,preferred_width:0,width_anchor:NaN,width_panel:null,width_sim:"",bounds:null,anchor:null,resize:null,tooltips:[],track_tip:null,drag:false,scale_drag:false,scale_stage:null,stage:null,persist:false,due:0,signature:""};
         RegisterServiceHandler("ApexColumnsTakeover",ApexColumnsTakeover);
         RegisterServiceHandler("ApexColumnsSet",ApexColumnsSet);
         RegisterServiceHandler("ApexColumnsScale",ApexColumnsScale);
         RegisterServiceHandler("ApexColumnsScaleEnd",ApexColumnsScaleEnd);
         RegisterServiceHandler("ApexColumnsResize",ApexColumnsResize);
         RegisterServiceHandler("ApexColumnsResizeEnd",ApexColumnsResizeEnd);
      }

      private function ApexColumnsTakeover(value:Object=null) : Boolean
      {
         return apexColumns!=null && apexCatalogPrefs!=null && ApexCatalogPanelKind(mCurrentPanel)!="";
      }

      private function ApexColumnsSave() : void
      {
         apexColumns.persist=true;apexColumns.due=flash.utils.getTimer()+700;
      }

      private function ApexColumnsSet(value:Object=null) : Boolean
      {
         if(!ApexColumnsTakeover())return false;
         if(typeof value=="number" && isFinite(Number(value)) && int(value)==Number(value) && int(value)>=2 && int(value)<=32) {
            if(int(apexCatalogPrefs.columns)!=int(value)) {apexCatalogPrefs.columns=int(value);ApexColumnsSave();}
         }
         return true;
      }

      private function ApexColumnsScale(value:Object=null) : Boolean
      {
         if(!ApexColumnsTakeover())return false;
         var panel:Object=mCurrentPanel;
         var track:flash.display.DisplayObject=ApexColumnsTrack(panel);
         if(track!=null) {
            if(!apexColumns.scale_drag && stage!=null) {
               if(apexColumns.resize!=null)ApexColumnsResizeEnd(new flash.events.Event(flash.events.Event.DEACTIVATE));
               ApexColumnsUp();
               apexColumns.scale_drag=true;apexColumns.scale_stage=stage;
               if(apexColumns.anchor==null && apexColumns.root!=null && apexColumns.root.parent===panel)
                  apexColumns.anchor={panel:panel,columns:apexColumns.root.localToGlobal(new flash.geom.Point(0,0)),
                     thumbnail:track.localToGlobal(new flash.geom.Point(0,0)),half:Math.max(90,(panel.mcPanelBackground.width-30)*0.5),
                     stage:stage,width:stage.stageWidth,height:stage.stageHeight};
               stage.addEventListener(flash.events.Event.DEACTIVATE,ApexColumnsScaleEnd,false,30,true);
               stage.addEventListener(flash.events.Event.MOUSE_LEAVE,ApexColumnsScaleEnd,false,30,true);
            }
            var fraction:Number=Math.max(0,Math.min(1,(track.mouseX-20)/190));
            var size:Number=Math.round((0.2+fraction*1.4)*100)/100;
            if(apexCardPrefs.scale!=size) {apexCardPrefs.scale=size;ApexColumnsSave();}
         }
         return true;
      }

      private function ApexColumnsScaleEnd(value:Object=null) : Boolean
      {
         if(apexColumns==null)return false;
         if(ApexColumnsTakeover() && !(value is flash.events.Event && !(value is flash.events.MouseEvent)))ApexColumnsScale();
         var screen:Object=apexColumns.scale_stage==null ? stage : apexColumns.scale_stage;
         if(screen!=null) {
            screen.removeEventListener(flash.events.MouseEvent.MOUSE_MOVE,HandleThumbnailScaleMove);
            screen.removeEventListener(flash.events.MouseEvent.MOUSE_MOVE,ApexColumnsScaleMove);
            screen.removeEventListener(flash.events.MouseEvent.MOUSE_UP,ApexColumnsScaleUp);
            screen.removeEventListener(flash.events.MouseEvent.MOUSE_UP,HandleThumbnailScaleUp);
            screen.removeEventListener(flash.events.Event.ENTER_FRAME,HandleThumbnailScaleFrame);
            screen.removeEventListener(flash.events.Event.DEACTIVATE,ApexColumnsScaleEnd);
            screen.removeEventListener(flash.events.Event.MOUSE_LEAVE,ApexColumnsScaleEnd);
         }
         apexColumns.scale_drag=false;apexColumns.scale_stage=null;
         if(!apexColumns.drag)apexColumns.anchor=null;
         return true;
      }

      private function ApexColumnsResize(value:Object=null) : Boolean
      {
         // Retain the donor service name, but width and count now have separate
         // controls. A width drag never silently changes 2–32 or 20–160%.
         if(!ApexColumnsTakeover())return false;
         if(value is flash.events.MouseEvent) {
            if(apexColumns.resize==null)ApexColumnsWidthDown(value as flash.events.MouseEvent);
            else ApexColumnsWidthMove(value as flash.events.MouseEvent);
         }
         return true;
      }

      private function ApexColumnsResizeEnd(value:Object=null) : Boolean
      {
         if(apexColumns==null)return false;
         var owned:Boolean=ApexColumnsTakeover() || apexColumns.resize!=null;
         if(value is flash.events.MouseEvent)ApexColumnsWidthMove(value as flash.events.MouseEvent);
         var screen:Object=apexColumns.resize==null ? stage : apexColumns.resize.stage;
         if(screen!=null) {
            screen.removeEventListener(flash.events.MouseEvent.MOUSE_MOVE,HandleDynamicResizeMoveRight);
            screen.removeEventListener(flash.events.MouseEvent.MOUSE_UP,HandleDynamicResizeUpRight);
            screen.removeEventListener(flash.events.MouseEvent.MOUSE_MOVE,ApexColumnsWidthMove);
            screen.removeEventListener(flash.events.MouseEvent.MOUSE_UP,ApexColumnsWidthUp);
            screen.removeEventListener(flash.events.Event.DEACTIVATE,ApexColumnsWidthUp);
            screen.removeEventListener(flash.events.Event.MOUSE_LEAVE,ApexColumnsWidthUp);
         }
         apexColumns.resize=null;
         if(mDynamicResizeHandle!=null)mDynamicResizeHandle.alpha=0.78;
         if(apexColumns.width_handle!=null)apexColumns.width_handle.alpha=0.78;
         return owned;
      }

      private function ApexColumnsTrack(panel:Object) : flash.display.Sprite
      {
         if(panel==null)return null;
         var track:flash.display.Sprite=panel.getChildByName("dccThumbnailScaleTrack") as flash.display.Sprite;
         if(track!=null)return track;
         if(apexColumns.fallback_track==null) {
            // Same donor visual language and geometry, one retained control
            // reused by Body/Face/Generic instead of reparenting donor state.
            track=new flash.display.Sprite();track.name="apexSharedThumbnailScaleTrack";
            track.graphics.beginFill(0xffffff,0.01);track.graphics.drawRoundRect(0,0,230,28,1);track.graphics.endFill();
            track.graphics.beginFill(0xdcefea,0.92);track.graphics.drawRoundRect(20,12,190,4,4);track.graphics.endFill();
            var thumb:flash.display.Sprite=new flash.display.Sprite();thumb.name="dccThumbnailScaleThumb";
            thumb.graphics.beginFill(0x4f6a69,0.9);thumb.graphics.drawRoundRect(-10,4,20,20,20);thumb.graphics.endFill();
            thumb.graphics.beginFill(0xffffff,1);thumb.graphics.drawRoundRect(-8,6,16,16,16);thumb.graphics.endFill();track.addChild(thumb);
            track.mouseChildren=false;track.buttonMode=true;
            track.addEventListener(flash.events.MouseEvent.MOUSE_DOWN,ApexColumnsScaleDown,false,30,true);
            apexColumns.fallback_track=track;
         }
         track=apexColumns.fallback_track;
         if(track.parent!==panel)panel.addChild(track);
         return track;
      }

      private function ApexColumnsScaleDown(event:flash.events.MouseEvent) : void
      {
         if(!ApexColumnsTakeover() || event.currentTarget==null || event.currentTarget.parent!==mCurrentPanel)return;
         ApexColumnsScale(event);
         stage.addEventListener(flash.events.MouseEvent.MOUSE_MOVE,ApexColumnsScaleMove,false,30,true);
         stage.addEventListener(flash.events.MouseEvent.MOUSE_UP,ApexColumnsScaleUp,false,30,true);
         event.stopImmediatePropagation();event.preventDefault();
      }

      private function ApexColumnsScaleMove(event:flash.events.MouseEvent) : void
      {
         if(apexColumns==null || !apexColumns.scale_drag)return;
         if(apexColumns.anchor==null || apexColumns.anchor.panel!==mCurrentPanel || apexColumns.anchor.stage!==stage ||
            apexColumns.anchor.width!=stage.stageWidth || apexColumns.anchor.height!=stage.stageHeight) {
            ApexColumnsScaleEnd(new flash.events.Event(flash.events.Event.DEACTIVATE));return;
         }
         ApexColumnsScale(event);event.stopImmediatePropagation();event.preventDefault();
      }

      private function ApexColumnsScaleUp(event:flash.events.MouseEvent) : void
      {
         ApexColumnsScaleEnd(event);event.stopImmediatePropagation();event.preventDefault();
      }

      private function ApexColumnsWidthDown(event:flash.events.MouseEvent) : void
      {
         if(!ApexColumnsTakeover() || stage==null || apexCardLayout==null)return;
         var panel:Object=mCurrentPanel;var envelope:Object=ApexCatalogWidthEnvelope(panel);
         if(envelope==null || envelope.available<80)return;
         if(apexColumns.scale_drag)ApexColumnsScaleEnd(new flash.events.Event(flash.events.Event.DEACTIVATE));
         ApexColumnsUp();ApexColumnsResizeEnd(new flash.events.Event(flash.events.Event.DEACTIVATE));
         var width:Number=Number(panel.mcPanelBackground.width);
         if(!isFinite(width) || width<80)return;
         if(!ApexCatalogWidthMode()) {
            // Preserve the native clamp that is ALREADY displaying this left
            // edge. Future width changes consume space to its right only.
            apexColumns.width_anchor=apexCatalogBinding==null ? width+12 : Math.max(Number(apexCatalogBinding.maximum),width+12);
         }
         apexColumns.width_panel=panel;apexColumns.width_sim=mCurrSimInfo==null ? "" : String(mCurrSimInfo.simId);
         apexColumns.preferred_width=width;
         apexColumns.resize={stage:stage,panel:panel,grid:panel.mcTileList.mGridLayout,width:stage.stageWidth,height:stage.stageHeight,
            x:Number(event.stageX),start_width:width,scale:Number(envelope.scale)};
         stage.addEventListener(flash.events.MouseEvent.MOUSE_MOVE,ApexColumnsWidthMove,false,30,true);
         stage.addEventListener(flash.events.MouseEvent.MOUSE_UP,ApexColumnsWidthUp,false,30,true);
         stage.addEventListener(flash.events.Event.DEACTIVATE,ApexColumnsWidthUp,false,30,true);
         stage.addEventListener(flash.events.Event.MOUSE_LEAVE,ApexColumnsWidthUp,false,30,true);
         if(apexColumns.width_handle!=null)apexColumns.width_handle.alpha=1;
         event.stopImmediatePropagation();event.preventDefault();
      }

      private function ApexColumnsWidthMove(event:flash.events.MouseEvent) : void
      {
         if(apexColumns==null || apexColumns.resize==null)return;
         var drag:Object=apexColumns.resize;var panel:Object=mCurrentPanel;
         if(!ApexColumnsTakeover() || drag.panel!==panel || drag.grid!==panel.mcTileList.mGridLayout ||
            drag.stage!==stage || drag.width!=stage.stageWidth || drag.height!=stage.stageHeight) {
            ApexColumnsResizeEnd(new flash.events.Event(flash.events.Event.DEACTIVATE));return;
         }
         var envelope:Object=ApexCatalogWidthEnvelope(panel);
         if(envelope==null || envelope.scale!==drag.scale || envelope.available<80) {
            ApexColumnsResizeEnd(new flash.events.Event(flash.events.Event.DEACTIVATE));return;
         }
         var wanted:Number=Number(drag.start_width)+(Number(event.stageX)-Number(drag.x))/Number(drag.scale);
         if(!isFinite(wanted))return;
         wanted=Math.max(80,Math.min(16384,Number(envelope.available),wanted));
         if(wanted!==Number(apexColumns.preferred_width)) {apexColumns.preferred_width=wanted;ApexColumnsSave();}
         event.stopImmediatePropagation();event.preventDefault();
      }

      private function ApexColumnsWidthUp(event:flash.events.Event=null) : void
      {
         ApexColumnsResizeEnd(event);
         if(event!=null) {event.stopImmediatePropagation();event.preventDefault();}
      }

      private function ApexColumnsWidthHandle(panel:Object) : void
      {
         if(apexColumns.width_handle==null) {
            var handle:flash.display.Sprite=new flash.display.Sprite();handle.name="apexCatalogRightResize";
            handle.graphics.beginFill(0xffffff,0.01);handle.graphics.drawRect(0,0,12,72);handle.graphics.endFill();
            handle.graphics.beginFill(0xdcefea,0.92);handle.graphics.drawRoundRect(-3,8,6,56,6);handle.graphics.endFill();
            handle.graphics.lineStyle(1,0x4f6a69,0.78);handle.graphics.moveTo(-1,29);handle.graphics.lineTo(1,29);
            handle.graphics.moveTo(-1,35);handle.graphics.lineTo(1,35);handle.graphics.moveTo(-1,41);handle.graphics.lineTo(1,41);
            handle.buttonMode=true;handle.mouseChildren=false;handle.alpha=0.78;
            handle.addEventListener(flash.events.MouseEvent.MOUSE_DOWN,ApexColumnsWidthDown,false,30,true);
            apexColumns.width_handle=handle;
            var tip:TooltipObject=new TooltipObject(handle);
            tip.Initialize({text:"Drag the right edge to widen or shrink the catalog into free space. Column count and requested card size stay unchanged; your Sim and other controls stay clear.",maxwidth:310},250);
            apexColumns.tooltips.push(tip);
         }
         handle=apexColumns.width_handle;
         if(handle.parent!==panel)panel.addChild(handle);
         var bar:flash.geom.Rectangle=panel.mcTileList.mSlider.getBounds(panel);
         handle.visible=true;handle.x=Math.max(Number(panel.mcPanelBackground.width),bar.x+bar.width)+11;
         handle.y=panel.mcTileList.y+Math.max(0,(panel.mcTileList.height-72)*0.5);
         if(mDynamicResizeHandle!=null)mDynamicResizeHandle.visible=false;
      }

      private function ApexColumnsDown(event:flash.events.MouseEvent) : void
      {
         if(apexColumns==null || stage==null || !ApexColumnsTakeover())return;
         var panel:Object=mCurrentPanel;
         if(apexColumns.root==null || apexColumns.root.parent!==panel || event.currentTarget!==apexColumns.root)return;
         if(event.target.name=="apexColumnsLayout") {ApexCatalogView("layout");event.stopImmediatePropagation();return;}
         if(apexColumns.resize!=null)ApexColumnsResizeEnd(new flash.events.Event(flash.events.Event.DEACTIVATE));
         if(apexColumns.scale_drag)ApexColumnsScaleEnd(new flash.events.Event(flash.events.Event.DEACTIVATE));
         ApexColumnsUp();apexColumns.drag=true;apexColumns.stage=stage;
         if(apexColumns.anchor==null && apexColumns.root!=null && apexColumns.root.parent===panel) {
            var track:flash.display.DisplayObject=ApexColumnsTrack(panel);
            apexColumns.anchor={panel:panel,columns:apexColumns.root.localToGlobal(new flash.geom.Point(0,0)),
               thumbnail:track==null ? null : track.localToGlobal(new flash.geom.Point(0,0)),half:Math.max(90,(panel.mcPanelBackground.width-30)*0.5),
               stage:stage,width:stage.stageWidth,height:stage.stageHeight};
         }
         ApexColumnsMove(event);
         stage.addEventListener(flash.events.MouseEvent.MOUSE_MOVE,ApexColumnsMove,false,30,true);
         stage.addEventListener(flash.events.MouseEvent.MOUSE_UP,ApexColumnsUp,false,30,true);
         stage.addEventListener(flash.events.Event.DEACTIVATE,ApexColumnsUp,false,30,true);
         stage.addEventListener(flash.events.Event.MOUSE_LEAVE,ApexColumnsUp,false,30,true);
         event.stopImmediatePropagation();event.preventDefault();
      }

      private function ApexColumnsMove(event:flash.events.MouseEvent) : void
      {
         if(apexColumns==null || !apexColumns.drag || apexColumns.root==null)return;
         if(apexColumns.root.parent!==mCurrentPanel || apexColumns.anchor==null ||
            apexColumns.anchor.panel!==mCurrentPanel || apexColumns.anchor.stage!==stage ||
            apexColumns.anchor.width!=stage.stageWidth || apexColumns.anchor.height!=stage.stageHeight) {
            ApexColumnsUp();return;
         }
         var ratio:Number=Math.max(0,Math.min(1,(apexColumns.root.mouseX-12)/170));
         ApexColumnsSet(2+Math.round(30*ratio));
         var thumb:flash.display.DisplayObject=apexColumns.root.getChildByName("thumb");
         if(thumb!=null)thumb.x=12+170*(int(apexCatalogPrefs.columns)-2)/30;
         event.stopImmediatePropagation();event.preventDefault();
      }

      private function ApexColumnsUp(event:flash.events.Event=null) : void
      {
         if(apexColumns==null)return;
         if(apexColumns.stage!=null) {
            apexColumns.stage.removeEventListener(flash.events.MouseEvent.MOUSE_MOVE,ApexColumnsMove);
            apexColumns.stage.removeEventListener(flash.events.MouseEvent.MOUSE_UP,ApexColumnsUp);
            apexColumns.stage.removeEventListener(flash.events.Event.DEACTIVATE,ApexColumnsUp);
            apexColumns.stage.removeEventListener(flash.events.Event.MOUSE_LEAVE,ApexColumnsUp);
         }
         apexColumns.drag=false;
         if(!apexColumns.scale_drag)apexColumns.anchor=null;
      }

      private function ApexColumnsFrame() : void
      {
         if(apexColumns==null)return;
         var panel:Object=mCurrentPanel;
         if(apexColumns.resize!=null && (apexColumns.resize.panel!==panel || apexColumns.resize.stage!==stage ||
            apexColumns.resize.width!=stage.stageWidth || apexColumns.resize.height!=stage.stageHeight || panel==null || !panel.visible || ApexCatalogPanelKind(panel)==""))
            ApexColumnsResizeEnd(new flash.events.Event(flash.events.Event.DEACTIVATE));
         if(ApexCatalogPanelKind(panel)!="") {
            if(apexColumns.anchor!=null && (apexColumns.anchor.panel!==panel || apexColumns.anchor.stage!==stage ||
               apexColumns.anchor.width!=stage.stageWidth || apexColumns.anchor.height!=stage.stageHeight)) {
               ApexColumnsUp();ApexColumnsScaleEnd(new flash.events.Event(flash.events.Event.DEACTIVATE));
            }
            if(apexColumns.root==null) {
               var root:flash.display.Sprite=new flash.display.Sprite();root.name="ApexColumnsSlider";root.buttonMode=true;
               root.graphics.beginFill(0xffffff,0.01);root.graphics.drawRect(0,0,200,36);root.graphics.endFill();
               root.graphics.lineStyle(4,0xc7ecef);root.graphics.moveTo(12,26);root.graphics.lineTo(182,26);
               var thumb:flash.display.Sprite=new flash.display.Sprite();thumb.name="thumb";thumb.mouseEnabled=false;thumb.y=26;
               thumb.graphics.lineStyle(2,0x447c89);thumb.graphics.beginFill(0xffffff);thumb.graphics.drawCircle(0,0,8);thumb.graphics.endFill();root.addChild(thumb);
               var text:flash.text.TextField=ApexFormsText(root,"Columns",9,0,135,11,0x275273);text.name="caption";text.mouseEnabled=false;
               var button:flash.display.Sprite=new flash.display.Sprite();button.name="apexColumnsLayout";button.x=148;button.mouseChildren=false;
               ApexFormsText(button,"Layout",0,0,50,11,0x275273);button.graphics.beginFill(0xffffff,0.01);button.graphics.drawRect(0,0,50,17);button.graphics.endFill();root.addChild(button);
               root.addEventListener(flash.events.MouseEvent.MOUSE_DOWN,ApexColumnsDown,false,30,true);apexColumns.root=root;
               var tooltip:TooltipObject=new TooltipObject(root);
               tooltip.Initialize({text:"Choose 2–32 catalog columns. Cards fit the current panel width. Drag the separate right edge to widen or shrink it; column count and requested size stay independent.",maxwidth:310},250);apexColumns.tooltips.push(tooltip);
               tooltip=new TooltipObject(button);tooltip.Initialize({text:"Open card size, column and spacing settings.",maxwidth:280},250);apexColumns.tooltips.push(tooltip);
            }
            if(apexColumns.root.parent!==panel)panel.addChild(apexColumns.root);
            apexColumns.root.visible=true;ApexColumnsWidthHandle(panel);
            // A card reflow moves the right-anchored catalog itself. Hold only
            // this display band under the pointer until release, so neither
            // slider reads a moving track and feeds a second unwanted resize.
            var hold:Object=(apexColumns.drag || apexColumns.scale_drag) ? apexColumns.anchor : null;
            var half:Number=hold==null ? Math.max(90,(panel.mcPanelBackground.width-30)*0.5) : Number(hold.half);
            apexColumns.root.x=panel.mcTileList.x;apexColumns.root.y=panel.mcTileList.y+panel.mcTileList.height+3;
            if(hold!=null) {
               var columnOrigin:flash.geom.Point=panel.globalToLocal(hold.columns);
               apexColumns.root.x=columnOrigin.x;apexColumns.root.y=columnOrigin.y;
            }
            apexColumns.root.scaleX=Math.min(1,half/200);apexColumns.root.scaleY=1;
            var layout:flash.display.DisplayObject=apexColumns.root.getChildByName("apexColumnsLayout");
            layout.scaleX=1/apexColumns.root.scaleX;layout.x=(Math.min(200,half)-50)/apexColumns.root.scaleX;
            apexColumns.root.getChildByName("thumb").x=12+170*(int(apexCatalogPrefs.columns)-2)/30;
            var caption:String=(half<160 ? "Cols " : "Columns ")+apexCatalogPrefs.columns;
            if(apexCardLayout!=null && int(apexCardLayout.columns)!=int(apexCatalogPrefs.columns))caption=apexCatalogPrefs.columns+" → "+apexCardLayout.columns;
            var label:flash.text.TextField=apexColumns.root.getChildByName("caption") as flash.text.TextField;
            label.scaleX=1/apexColumns.root.scaleX;label.width=Math.max(40,Math.min(200,half)-62);
            if(label.text!=caption)label.text=caption;
            var track:flash.display.Sprite=ApexColumnsTrack(panel);
            if(track!=null) {
               track.visible=true;track.scaleX=Math.min(1,half/230);track.x=panel.mcTileList.x+half+7;track.y=apexColumns.root.y+12;
               if(hold!=null && hold.thumbnail!=null) {
                  var sizeOrigin:flash.geom.Point=panel.globalToLocal(hold.thumbnail);
                  track.x=sizeOrigin.x;track.y=sizeOrigin.y;
               }
               if(apexColumns.track!==track) {
                  if(apexColumns.track_tip!=null)apexColumns.track_tip.Shutdown();
                  apexColumns.track=track;apexColumns.track_tip=new TooltipObject(track);
                  apexColumns.track_tip.Initialize({text:"Thumbnail size: 20–160%. Cards fit your chosen columns; the caption reports any fitted size. Native hover tips and full-size swatch popups remain available; increase Size for detail.",maxwidth:310},250);
               }
               var sizeLabel:flash.text.TextField=track.getChildByName("apexThumbnailScaleCaption") as flash.text.TextField;
               if(sizeLabel==null) {sizeLabel=ApexFormsText(track,"",20,-12,190,11,0x275273);sizeLabel.name="apexThumbnailScaleCaption";sizeLabel.mouseEnabled=false;}
               sizeLabel.scaleX=1/track.scaleX;sizeLabel.width=Math.max(90,half-18);
               var sizeCaption:String="Size "+Math.round(Number(apexCardPrefs.scale)*100)+"%";
               if(apexCardLayout!=null && Number(apexCardLayout.scale)<Number(apexCardPrefs.scale)-0.005)
                  sizeCaption+=" / fit "+Math.round(Number(apexCardLayout.scale)*100)+"%";
               if(sizeLabel.text!=sizeCaption)sizeLabel.text=sizeCaption;
               var original:flash.display.DisplayObject=track.getChildByName("dccThumbnailScaleThumb");
               if(original!=null)original.x=20+190*(Number(apexCardPrefs.scale)-0.2)/1.4;
            }
            var columnFrom:flash.geom.Point=apexColumns.root.localToGlobal(new flash.geom.Point(0,0));
            var columnTo:flash.geom.Point=apexColumns.root.localToGlobal(new flash.geom.Point(200,36));
            var sizeFrom:flash.geom.Point=track==null ? null : track.localToGlobal(new flash.geom.Point(0,-12));
            var sizeTo:flash.geom.Point=track==null ? null : track.localToGlobal(new flash.geom.Point(230,28));
            var grip:flash.geom.Rectangle=apexColumns.width_handle.getBounds(stage);
            apexColumns.bounds={visible:true,width:{x:grip.x,y:grip.y,width:grip.width,height:grip.height,
               requested:isFinite(Number(apexColumns.preferred_width)) ? Number(apexColumns.preferred_width) : 0,
               fitted:Number(panel.mcPanelBackground.width),dragging:apexColumns.resize!=null,
               native_anchor_max:ApexCatalogWidthMode() ? Number(apexColumns.width_anchor) : null},
               columns:{x:columnFrom.x,y:columnFrom.y,width:columnTo.x-columnFrom.x,height:columnTo.y-columnFrom.y,
               requested:int(apexCatalogPrefs.columns),fitted:apexCardLayout==null ? 0 : int(apexCardLayout.columns)},
               thumbnail:sizeFrom==null ? null : {x:sizeFrom.x,y:sizeFrom.y,width:sizeTo.x-sizeFrom.x,height:sizeTo.y-sizeFrom.y,
                  requested_percent:Math.round(Number(apexCardPrefs.scale)*100),fitted_percent:apexCardLayout==null ? 0 : Math.round(Number(apexCardLayout.scale)*100)}};
         } else {
            if(apexColumns.bounds!=null)apexColumns.bounds.visible=false;
            if(apexColumns.root!=null)apexColumns.root.visible=false;
            if(apexColumns.width_handle!=null)apexColumns.width_handle.visible=false;
            if(apexColumns.track!=null)apexColumns.track.visible=false;
            if(apexColumns.drag)ApexColumnsUp();
            if(apexColumns.scale_drag)ApexColumnsScaleEnd(new flash.events.Event(flash.events.Event.DEACTIVATE));
         }
         if(apexColumns.persist && !apexColumns.drag && !apexColumns.scale_drag && apexColumns.resize==null && (apexPanels==null || apexPanels.drag==null) &&
            flash.utils.getTimer()>=int(apexColumns.due) && apexPendingFields==null && !apexReceiving) {
            apexColumns.persist=false;ApexCatalogPersist();
         }
      }

      private function ApexColumnsDispose() : void
      {
         if(apexColumns==null)return;
         ApexColumnsResizeEnd(new flash.events.Event(flash.events.Event.DEACTIVATE));
         ApexColumnsUp();
         ApexColumnsScaleEnd(new flash.events.Event(flash.events.Event.DEACTIVATE));
         for each(var tooltip:TooltipObject in apexColumns.tooltips)tooltip.Shutdown();
         if(apexColumns.track_tip!=null)apexColumns.track_tip.Shutdown();
         if(apexColumns.track!=null) {
            var label:flash.display.DisplayObject=apexColumns.track.getChildByName("apexThumbnailScaleCaption");
            if(label!=null)apexColumns.track.removeChild(label);
         }
         UnregisterServiceHandler("ApexColumnsTakeover",ApexColumnsTakeover);
         UnregisterServiceHandler("ApexColumnsSet",ApexColumnsSet);
         UnregisterServiceHandler("ApexColumnsScale",ApexColumnsScale);
         UnregisterServiceHandler("ApexColumnsScaleEnd",ApexColumnsScaleEnd);
         UnregisterServiceHandler("ApexColumnsResize",ApexColumnsResize);
         UnregisterServiceHandler("ApexColumnsResizeEnd",ApexColumnsResizeEnd);
         if(apexColumns.root!=null && apexColumns.root.parent!=null)apexColumns.root.parent.removeChild(apexColumns.root);
         if(apexColumns.fallback_track!=null && apexColumns.fallback_track.parent!=null)apexColumns.fallback_track.parent.removeChild(apexColumns.fallback_track);
         if(apexColumns.width_handle!=null && apexColumns.width_handle.parent!=null)apexColumns.width_handle.parent.removeChild(apexColumns.width_handle);
         apexColumns=null;
      }
