      // Per-instance UI-only terminal. It must survive replacement of the
      // transaction's dynamic state without modifying that foreign object.
      private var apexGridAuthority:Object;

      private function ApexGridAuthorityScope(owner:Object) : Object {
         if(owner==null || owner.phase!=="bound")return null;
         for each(var key:String in ["sim_id","household_id","owner","native_generation"])
            if(typeof owner[key]!="string" || String(owner[key]).length==0 || String(owner[key]).length>160)return null;
         for each(var scalarKey:String in ["session","layer","native_kind","shell_kind","native_mask","outfit_type","outfit_index","state"])
            if(typeof owner[scalarKey]!="number" || !isFinite(Number(owner[scalarKey])) || Number(owner[scalarKey])!=int(owner[scalarKey]))return null;
         return {sim_id:String(owner.sim_id),household_id:String(owner.household_id),owner:String(owner.owner),session:int(owner.session),
            layer:int(owner.layer),native_kind:int(owner.native_kind),shell_kind:int(owner.shell_kind),native_mask:int(owner.native_mask),
            native_generation:String(owner.native_generation),outfit_type:int(owner.outfit_type),outfit_index:int(owner.outfit_index),state:int(owner.state)};
      }

      private function ApexGridAuthorityCapture(d:Object) : Boolean {
         var s:Object=d==null ? null : d.state;
         if(d==null || s==null || d.job==null || d.eofScope==null)return false;
         d.authority={state:s,job:d.job,delta:d,owner:d.owner,ownerGeneration:d.ownerGeneration,
            panel:d.eofPanel,view:d.view,feed:d.feed,type:d.cellType,stage:d.eofStage,scope:d.eofScope,
            ready:d.oldReady,pool:d.oldPool,intrinsics:d.oldIntrinsics,presentation:d.oldPresentation,
            oldIntrinsicValues:new Vector.<Object>(d.oldCells.length),oldPoolValues:new Vector.<Object>(d.oldCells.length),oldCaptured:new Vector.<Boolean>(d.oldCells.length),
            acquired:false,working:false,mapping:false,gate:false,mouse:false,children:false,
            generation:int(d.newGeneration),revision:int(d.revision),lost:false,disposed:false,reason:"",
            lease_released:false,input_released:false,release_refused:"not-acquired"};
         apexGridAuthority=d.authority;return true;
      }

      private function ApexGridAuthorityProbe() : Boolean {
         var h:Object=apexGridAuthority;
         if(h!=null && !h.lost && (apexGridState!==h.state || apexGridState.job!==h.job))
            ApexGridAuthorityLose(h.delta,"entry-state-or-job-replaced");
         return apexGridAuthority!=null && apexGridAuthority.lost===true;
      }

      private function ApexGridAuthorityCurrent(d:Object) : Boolean {
         var h:Object=d==null ? null : d.authority;var s:Object=apexGridState;
         if(h==null || h.lost || (apexGridAuthority!=null && apexGridAuthority!==h) || s!==h.state || s.job!==h.job || s.delta!==d || d!==h.delta ||
            s.owner!==h.owner || s.ownerGeneration!=h.ownerGeneration || s.panel!==h.panel ||
            s.view!==h.view || mGridView!==h.view || s.feed!==h.feed || mGridData!==h.feed || mCellType!==h.type ||
            s.ready!==h.ready || s.poolFlags!==h.pool || s.intrinsics!==h.intrinsics || s.presentation!==h.presentation ||
            (h.acquired && (s.lease!==h.job || !mbSuppressUpdates || s.externalSuppression)) ||
            (h.gate && (h.view.mouseEnabled!==false || h.view.mouseChildren!==false)))return false;
         var p:Object=h.presentation;
         if(p==null || p.committedCells!==d.oldCells || p.committedY!==d.oldY || p.committedMap!==d.oldMap ||
            p.committedReady!==d.oldReady || p.committedBindings!==d.oldBindings || p.committedExpected!==d.oldExpected)return false;
         if(h.working && (p.stageCells!==d.cells || p.stageY!==d.ys || p.stageMap!==d.map ||
            p.expected!==d.expected || p.stageBindings!==d.bindings))return false;
         return h.mapping ? mCells===d.cells && mCellsY===d.ys && mCellIndexToDataIndexMap===d.map :
            mCells===d.oldCells && mCellsY===d.oldY && mCellIndexToDataIndexMap===d.oldMap;
      }

      private function ApexGridAuthorityOldCell(cell:Object,index:int,d:Object) : Boolean {
         var h:Object=d.authority;var s:Object=apexGridState;var type:Class=d.cellType as Class;
         if(!ApexGridAuthorityCurrent(d) || cell==null || type==null || !(cell is type) || cell.constructor!==type || cell.parent!==d.view ||
            s.intrinsics[cell]==null || s.intrinsics[cell].type!==type)return false;
         var intrinsic:Object=s.intrinsics[cell];var flags:Object=s.poolFlags[cell];
         var actualY:Number=Number(cell.y);var actualVisible:Boolean=Boolean(cell.visible);
         var oldPresent:Boolean=d.oldMap[index]>=0;var expectedOld:int=oldPresent ? d.oldGeneration : -1;
         var borrowed:Boolean=d.borrowed[cell]!=null;
         var expectedCurrent:int=oldPresent ? d.newGeneration : -1;
         if(!isFinite(actualY) || d.oldReady[cell]!==expectedOld ||
            (h.working && (borrowed ? s.ready[cell]!==expectedCurrent : s.ready[cell]!=null)))return false;
         if(h.oldCaptured[index]===true) {
            if(h.oldIntrinsicValues[index]!==intrinsic || h.oldPoolValues[index]!==flags)return false;
         } else {
            // Initial acquisition only records already authenticated custody.
            // A later check never adopts a changed entry as a new baseline.
            if(h.working || d.touched)return false;
         }
         var expectedY:Number=d.oldPositions[cell]==null ? actualY : Number(d.oldPositions[cell]);
         var expectedVisible:Boolean=d.oldVisible[cell]==null ? oldPresent : Boolean(d.oldVisible[cell]);
         if(d.touched) {
            if(d.members[cell]===true) {expectedY=Number(d.physicalY[cell]);expectedVisible=oldPresent;}
            else expectedVisible=false;
         }
         if(actualY!==expectedY || actualVisible!==expectedVisible)return false;
         if(oldPresent) {
            var binding:Object=d.oldBindings[cell];
            if(binding==null || binding.schema!=="product-v1" || binding.generation!==d.oldGeneration || binding.revision!==d.revision ||
               binding.sorted!==int(d.oldMap[index]) || binding.logicalY!==Number(d.oldY[index]) ||
               (d.oldPositions[cell]==null && binding.physicalY!==actualY))return false;
            if(!ApexGridAuthorityCurrent(d) || d.oldReady[cell]!==expectedOld ||
               (h.working && (borrowed ? s.ready[cell]!==expectedCurrent : s.ready[cell]!=null)))return false;
            if(h.oldCaptured[index]!==true) {
               h.oldIntrinsicValues[index]=intrinsic;h.oldPoolValues[index]=flags;h.oldCaptured[index]=true;
            }
            return true;
         }
         if(d.oldMap[index]!==-1 || d.oldReady[cell]!==-1 || cell.visible!==false || cell.mouseEnabled!==false || cell.mouseChildren!==false ||
            flags==null || (s.ready[cell]!=null && s.ready[cell]!==-1) ||
            ("dccFavoriteProductId" in cell && cell.dccFavoriteProductId!=null))return false;
         var ext:Selectability=(cell as IExtendable).GetExtension(Selectability) as Selectability;
         var valid:Boolean=ext!=null && ext.constructor===Selectability && ext.Selected===false &&
            getQualifiedClassName(ext)==="olympus.extensions::Selectability" && ApexGridAuthorityCurrent(d) &&
            s.poolFlags[cell]===flags && s.intrinsics[cell]===intrinsic && intrinsic.type===type &&
            cell.parent===d.view && cell.visible===false && cell.mouseEnabled===false && cell.mouseChildren===false &&
            d.oldMap[index]===-1 && d.oldReady[cell]===-1 && (s.ready[cell]==null || s.ready[cell]===-1);
         if(valid && h.oldCaptured[index]!==true) {
            h.oldIntrinsicValues[index]=intrinsic;h.oldPoolValues[index]=flags;h.oldCaptured[index]=true;
         }
         return valid;
      }

      private function ApexGridAuthorityBank(d:Object) : Boolean {
         if(!ApexGridAuthorityCurrent(d))return false;
         for(var index:int=0;index<d.oldCells.length;index++)
            if(!ApexGridAuthorityOldCell(d.oldCells[index],index,d))return false;
         return ApexGridAuthorityCurrent(d);
      }

      private function ApexGridAuthorityReleaseCurrent(h:Object,ready:Object,pool:Object,mouse:Boolean,children:Boolean) : Boolean {
         if(h==null || apexGridAuthority!==h || apexGridState!==h.state)return false;
         var s:Object=h.state;var j:Object=h.job;var view:Object=h.view;
         // Finish all potentially reentrant property/method reads first.
         var actualMouse:Boolean=view.mouseEnabled;var actualChildren:Boolean=view.mouseChildren;
         var actualGeneration:int=int(h.owner.generation);var owns:Boolean=ApexGridOwns(j);
         // The remaining fields are our captured plain UI records/native
         // storage. A getter cannot replace authority then return a stale true.
         return actualMouse===mouse && actualChildren===children && actualGeneration==h.ownerGeneration && owns &&
            apexGridAuthority===h && apexGridState===s && s===h.state && s.job===j && s.owner===h.owner && s.ownerGeneration==h.ownerGeneration &&
            s.panel===h.panel && s.view===view && mGridView===view &&
            s.feed===h.feed && mGridData===h.feed && mCellType===h.type && s.ready===ready && s.poolFlags===pool &&
            s.lease===j && mbSuppressUpdates && !s.externalSuppression && h.acquired && h.gate;
      }

      private function ApexGridAuthorityLose(d:Object,reason:String) : void {
         var h:Object=d==null ? null : d.authority;if(h==null)return;
         if(h.lost || (apexGridAuthority!=null && apexGridAuthority!==h))return;
         h.lost=true;h.reason=String(reason).substr(0,160);apexGridAuthority=h;
         var s:Object=apexGridState;var j:Object=h.job;
         // Only our original transaction bookkeeping is retired. A complete
         // replacement state is never written, traversed, or rolled backward.
         if(s===h.state && s.job===j && s.delta===d) {
            s.delta=null;j.cancelled=true;j.reason="authority-lost";j.phase="authority-lost";j.error=null;
         }
         if(!h.acquired || !h.gate) {h.release_refused="gate-not-owned";return;}
         var ready:Object=s==null ? null : s.ready;var pool:Object=s==null ? null : s.poolFlags;
         try {
            if(!ApexGridAuthorityReleaseCurrent(h,ready,pool,false,false)) {h.release_refused="lease-view-or-gate-changed";return;}
            h.view.mouseEnabled=Boolean(h.mouse);
            if(!ApexGridAuthorityReleaseCurrent(h,ready,pool,Boolean(h.mouse),false)) {h.release_refused="mouse-release-reentry";return;}
            h.view.mouseChildren=Boolean(h.children);
            if(!ApexGridAuthorityReleaseCurrent(h,ready,pool,Boolean(h.mouse),Boolean(h.children))) {h.release_refused="children-release-reentry";return;}
            h.input_released=true;
            ApexGridRelease(j);
            if(apexGridAuthority===h && apexGridState===s && s.job===j && s.lease==null && !mbSuppressUpdates &&
               mGridView===h.view && s.ready===ready && s.poolFlags===pool) {
               j.lease=false;h.lease_released=true;h.release_refused="";
            } else h.release_refused="suppression-release-reentry";
         } catch(releaseError:*) {h.release_refused="owned-release-threw";}
      }

      public final function ApexGridAuthorityStatus() : Object {
         if(!ApexGridAuthorityProbe())return null;
         var h:Object=apexGridAuthority;var c:Object=h.scope;
         return {protocol:1,phase:"authority-lost",authority_lost:true,terminal_blocked:true,error:null,cancelled:true,
            reason:String(h.reason),generation:int(h.generation),revision:int(h.revision),
            lease_released:h.lease_released===true,input_released:h.input_released===true,release_refused:String(h.release_refused),
            lifecycle_changed:h.disposed===true || mGridView!==h.view || mGridData!==h.feed || mCellType!==h.type || h.panel.stage!==h.stage,
            scope:{sim_id:String(c.sim_id),household_id:String(c.household_id),owner:String(c.owner),session:int(c.session),layer:int(c.layer),
               native_kind:int(c.native_kind),shell_kind:int(c.shell_kind),native_mask:int(c.native_mask),native_generation:String(c.native_generation),
               outfit_type:int(c.outfit_type),outfit_index:int(c.outfit_index),state:int(c.state)}};
      }

      private function ApexGridAuthorityDispose() : void {
         var h:Object=apexGridAuthority;if(h==null || h.disposed)return;
         if(h.panel.stage!=null && mGridView===h.view && mGridData===h.feed && mCellType===h.type)return;
         // Actual native retirement releases retained UI handles. A bounded
         // primitive tombstone still prevents unchanged-context replay.
         apexGridAuthority={disposed:true,lost:true,scope:h.scope,reason:String(h.reason),generation:int(h.generation),revision:int(h.revision),
            lease_released:h.lease_released===true,input_released:h.input_released===true,release_refused:String(h.release_refused)};
         if(apexGridState===h.state)apexGridState=null;
      }

      private function ApexGridAuthorityRecover(request:Object) : Boolean {
         var h:Object=apexGridAuthority;if(h==null)return true;
         if(request==null || request.owner==null || !(request.validate is Function) || request.owner.phase!=="bound")return false;
         var state:Object=apexGridState;
         if(mbSuppressUpdates || state!=null && (state.lease!=null || state.externalSuppression===true))return false;
         var owner:Object=request.owner;var scope:Object=ApexGridAuthorityScope(owner);if(scope==null)return false;
         var old:Object=h.scope;var changed:Boolean=false;
         for each(var key:String in ["sim_id","household_id","owner","session","layer","native_kind","shell_kind","native_mask","native_generation","outfit_type","outfit_index","state"])if(scope[key]!==old[key])changed=true;
         var lifecycle:Boolean=h.disposed===true || mGridView!==h.view || mGridData!==h.feed || mCellType!==h.type || h.panel.stage!==h.stage;
         if(!changed && !lifecycle)return false;
         var view:Object=mGridView;var feed:Object=mGridData;var type:Class=mCellType as Class;
         if(request.validate(owner)!==true || apexGridAuthority!==h || apexGridState!==state || mGridView!==view || mGridData!==feed || mCellType!==type ||
            mbSuppressUpdates || state!=null && (state.lease!=null || state.externalSuppression===true) ||
            request.owner!==owner || owner.phase!=="bound" || owner.active!==true || owner.view!==view || owner.feed!==feed || owner.cell_type!==type ||
            request.panel==null || request.panel!==owner.panel || request.panel.stage==null || request.panel.mcTileList==null ||
            request.panel.mcTileList.mGridLayout!==this)return false;
         var after:Object=ApexGridAuthorityScope(owner);if(after==null)return false;
         for each(var afterKey:String in ["sim_id","household_id","owner","session","layer","native_kind","shell_kind","native_mask","native_generation","outfit_type","outfit_index","state"])if(after[afterKey]!==scope[afterKey])return false;
         if(apexGridAuthority!==h || apexGridState!==state || mGridView!==view || mGridData!==feed || mCellType!==type ||
            mbSuppressUpdates || state!=null && (state.lease!=null || state.externalSuppression===true))return false;
         // Fresh binding starts from the current native widget. Do not run
         // the old presentation rollback or restore any foreign registries.
         apexGridAuthority=null;apexGridState=null;return true;
      }
