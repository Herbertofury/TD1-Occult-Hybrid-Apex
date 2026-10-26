      // Widget-owned committed/staging presentation. No native product survives
      // a yield. Stage remains hidden until the real requested thumbnail loads.
      private function ApexGridPresentationStart(j:Object) : void {
         var s:Object=apexGridState;
         if(s.bootstrap)return;
         var p:Object=s.presentation;
         if(p==null) {
            p={working:false,committedCells:mCells,committedY:mCellsY,committedMap:mCellIndexToDataIndexMap,
               committedReady:s.ready,spareCells:new Vector.<IView>(),spareY:new Vector.<Number>(),spareMap:new Vector.<int>(),
               stageCells:null,stageY:null,stageMap:null,expected:new Dictionary(true),images:new Dictionary(true),
               committedVisible:new Dictionary(true),failures:[],published:false};
            s.presentation=p;
         }
         if(p.working)return;
         p.committedCells=mCells;p.committedY=mCellsY;p.committedMap=mCellIndexToDataIndexMap;
         p.committedVisible=new Dictionary(true);
         for each(var preceding:Object in mCells)p.committedVisible[preceding]=Boolean(preceding.visible);
         p.committedReady=s.ready;p.stageCells=p.spareCells;p.stageY=p.spareY;p.stageMap=p.spareMap;
         // A preceding committed bank can belong to the old native cell class.
         // Class changes must retire that hidden bank before it is reused.
         for each(var retained:Object in p.stageCells) {
            var intrinsic:Object=s.intrinsics[retained];
            if(intrinsic==null || intrinsic.type!==mCellType)s.retireAll=true;
         }
         p.spareCells=new Vector.<IView>();p.spareY=new Vector.<Number>();p.spareMap=new Vector.<int>();
         p.expected=new Dictionary(true);p.images=new Dictionary(true);p.published=false;p.working=true;
         s.ready=new Dictionary(true);
      }

      private function ApexGridPresentationWatch(cell:Object) : void {
         var s:Object=apexGridState;var p:Object=s.presentation;
         if(p==null || !p.working)return;
         if(!("mcImage" in cell) || cell.mcImage==null ||
            !("ApexImageReadyFor" in cell.mcImage) || !(cell.mcImage.ApexImageReadyFor is Function))
            throw new Error("Native card thumbnail readiness provider unavailable");
         p.images[cell.mcImage]={cell:cell,generation:s.job.generation,failed:false,failedResource:""};
         // Read the existing native URI before EA's ordinary FAIL handler
         // clears it. The original failure event/callback is never suppressed.
         cell.mcImage.addEventListener(AssetLoaderEvent.FAIL,ApexGridPresentationFailed,false,int.MAX_VALUE,true);
         var diagnostic:Object=cell.getChildByName("apexThumbnailFailure");
         if(diagnostic!=null)diagnostic.visible=false;
      }

      private function ApexGridPresentationFailed(event:Object) : void {
         var s:Object=apexGridState;if(s==null || s.presentation==null)return;
         var p:Object=s.presentation;if(!p.working || event==null)return;
         var row:Object=p.images[event.currentTarget];
         if(row==null || row.generation!=s.job.generation)return;
         row.failed=true;row.failedResource=event.currentTarget.resourceId==null ? "" : String(event.currentTarget.resourceId);
      }

      private function ApexGridPresentationBound(cell:Object) : void {
         var s:Object=apexGridState;var p:Object=s.presentation;
         if(p==null || !p.working)return;
         cell.visible=false;
         if(!("mcImage" in cell) || cell.mcImage==null ||
            !("ApexImageReadyFor" in cell.mcImage) || !(cell.mcImage.ApexImageReadyFor is Function))
            throw new Error("Native card thumbnail readiness provider unavailable");
         var watched:Object=p.images[cell.mcImage];
         var resource:String=cell.mcImage.resourceId;
         if((resource==null || resource.length==0) && watched!=null && watched.failed)resource=String(watched.failedResource);
         p.expected[cell]={requested:resource,display:resource,warning:false,diagnostic:false};
      }

      private function ApexGridPresentationTexture(cell:Object) : Boolean {
         var s:Object=apexGridState;var p:Object=s.presentation;
         if(p==null || !p.working)return true;
         var expected:Object=p.expected[cell];if(expected==null || cell.mcImage==null)return false;
         if(expected.diagnostic) {
            var label:Object=cell.getChildByName("apexThumbnailFailure");
            return label!=null && label.parent===cell && label.visible && String(label.text).length>0;
         }
         if(cell.mcImage.ApexImageReadyFor(expected.display)===true)return true;
         var watched:Object=p.images[cell.mcImage];
         var rejected:Boolean=expected.display==null || expected.display.length==0 || expected.display=="null" ||
            expected.display=="0" || expected.display.indexOf("[object Object]")>=0;
         if(!rejected && (watched==null || !watched.failed || watched.failedResource!==expected.display))return false;
         if(!expected.warning) {
            expected.warning=true;expected.display=SharedIcons.ICON_WARNING;
            watched.failed=false;watched.failedResource="";
            // Genuine EA failure art. The original item's identity, swatches,
            // selection and favorite/hide state remain the native Draw result.
            cell.mcImage.LoadImage(expected.display);return false;
         }
         // Even a broken/overridden EA warning texture cannot block all other
         // cards forever. This is a failure diagnostic, never loading filler.
         var text:TextField=cell.getChildByName("apexThumbnailFailure") as TextField;
         if(text==null) {text=new TextField();text.name="apexThumbnailFailure";text.mouseEnabled=false;cell.addChild(text);}
         text.defaultTextFormat=new TextFormat("_sans",12,0x215571);
         text.multiline=true;text.wordWrap=true;text.width=cell.mcHitArea==null ? 107 : Number(cell.mcHitArea.width);
         text.height=cell.mcHitArea==null ? 147 : Number(cell.mcHitArea.height);text.text="Thumbnail unavailable";text.visible=true;
         expected.diagnostic=true;return true;
      }

      private function ApexGridPresentationRollback() : void {
         var s:Object=apexGridState;if(s==null)return;var p:Object=s.presentation;
         if(p==null || !p.working)return;
         mCells=p.committedCells;mCellsY=p.committedY;mCellIndexToDataIndexMap=p.committedMap;
         s.ready=p.committedReady;
         for each(var cell:Object in p.stageCells)cell.visible=false;
         for each(var preceding:Object in p.committedCells)preceding.visible=Boolean(p.committedVisible[preceding]);
         p.spareCells=p.stageCells;p.spareY=p.stageY;p.spareMap=p.stageMap;
         p.stageCells=null;p.stageY=null;p.stageMap=null;p.expected=new Dictionary(true);p.images=new Dictionary(true);p.working=false;p.published=false;
      }

      private function ApexGridPresentationPublish(p:Object,j:Object) : void {
         var s:Object=apexGridState;var presentation:Object=s.presentation;
         if(presentation==null || !presentation.working) {
            mPrevRectangleUpdate.y=-Number(p.scrollY);
            mGridView.dispatchEvent(new GridEvent(GridEvent.RESIZE,null,[]));return;
         }
         // Complete before touching the committed mapping or presentation.
         for(var i:int=0;i<j.target;i++) {
            var next:Object=presentation.stageCells[i];
            if(presentation.stageMap[i]>=0 &&
               (s.ready[next]!==j.generation || !ApexGridPresentationTexture(next)))
               throw new Error("Replacement thumbnail/mapping is not ready for publication");
         }
         if(j.cancelled || j.dirty || j.revision!=s.revision || !ApexGridValid(j.identity))return;
         var oldScroll:Number=mPrevRectangleUpdate.y;
         mCells=presentation.stageCells;mCellsY=presentation.stageY;mCellIndexToDataIndexMap=presentation.stageMap;
         try {
            mPrevRectangleUpdate.y=-Number(p.scrollY);
            // Original native feedback runs with the complete NEW logical map,
            // while the preceding complete card presentation remains visible.
            mGridView.dispatchEvent(new GridEvent(GridEvent.RESIZE,null,[]));
            if(j.cancelled || j.dirty || j.revision!=s.revision || !ApexGridValid(j.identity)) {
               mPrevRectangleUpdate.y=oldScroll;ApexGridPresentationRollback();return;
            }
            for(i=0;i<j.target;i++) {
               next=presentation.stageCells[i];
               if(presentation.stageMap[i]>=0 && !ApexGridPresentationTexture(next)) {
                  j.dirty=true;mPrevRectangleUpdate.y=oldScroll;ApexGridPresentationRollback();return;
               }
            }
            // One synchronous publication; no yield/draw/load between these
            // visibility writes. Ready replacement first, preceding cards last.
            for(i=0;i<mCells.length;i++) {
               var displayed:Object=mCells[i];displayed.visible=i<j.target && mCellIndexToDataIndexMap[i]>=0;
            }
            for each(var old:Object in presentation.committedCells)old.visible=false;
            presentation.spareCells=presentation.committedCells;
            presentation.spareY=presentation.committedY;presentation.spareMap=presentation.committedMap;
            presentation.committedCells=mCells;presentation.committedY=mCellsY;presentation.committedMap=mCellIndexToDataIndexMap;
            presentation.failures=[];
            for(i=0;i<j.target;i++) {
               var failed:Object=presentation.expected[mCells[i]];
               if(failed!=null && failed.warning && presentation.failures.length<32)
                  presentation.failures.push({slot:i,requested_resource:failed.requested,ea_warning:true,text_diagnostic:Boolean(failed.diagnostic)});
            }
            presentation.committedReady=s.ready;presentation.stageCells=null;presentation.stageY=null;presentation.stageMap=null;
            presentation.expected=new Dictionary(true);presentation.images=new Dictionary(true);presentation.working=false;presentation.published=true;
         } catch(publicationError:*) {
            mPrevRectangleUpdate.y=oldScroll;ApexGridPresentationRollback();throw publicationError;
         }
      }
