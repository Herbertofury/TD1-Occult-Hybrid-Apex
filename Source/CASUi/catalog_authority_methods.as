      // Only private Main references and detached terminal receipts are kept.
      // The provider owns release, old cells and stolen/replaced widget state.
      private function ApexCatalogAuthorityScope(value:Object) : Object {
         if(value==null || !(value.sim_id is String) || !(value.household_id is String) ||
            !(value.owner is String) || value.owner=="" || !(value.session is int) || value.session<=0 ||
            !(value.layer is int) || !(value.native_kind is int) || !(value.shell_kind is int) ||
            !(value.native_mask is int) || !(value.native_generation is String) || value.native_generation=="" ||
            !(value.outfit_type is int) || value.outfit_type<0 || !(value.outfit_index is int) || value.outfit_index<0 ||
            !(value.state is int))return null;
         return {sim_id:value.sim_id,household_id:value.household_id,owner:value.owner,session:value.session,
            layer:value.layer,native_kind:value.native_kind,shell_kind:value.shell_kind,native_mask:value.native_mask,
            native_generation:value.native_generation,outfit_type:value.outfit_type,outfit_index:value.outfit_index,state:value.state};
      }

      private function ApexCatalogAuthorityEqual(a:Object,b:Object) : Boolean {
         return a!=null && b!=null && a.sim_id===b.sim_id && a.household_id===b.household_id &&
            a.owner===b.owner && a.session===b.session && a.layer===b.layer && a.native_kind===b.native_kind &&
            a.shell_kind===b.shell_kind && a.native_mask===b.native_mask && a.native_generation===b.native_generation &&
            a.outfit_type===b.outfit_type && a.outfit_index===b.outfit_index && a.state===b.state;
      }

      private function ApexCatalogAuthorityAvailable(grid:Object) : Boolean {
         if(grid==null)return false;
         if(!(grid is SelectableRecyclingGridLayout) || grid.constructor!==SelectableRecyclingGridLayout)return false;
         var name:String=flash.utils.getQualifiedClassName(grid);
         return name==="olympus.layout::SelectableRecyclingGridLayout" &&
            "ApexGridAuthorityStatus" in grid && grid.ApexGridAuthorityStatus is Function;
      }

      private function ApexCatalogAuthorityRemember(lease:Object) : void {
         var s:Object=apexCatalogGrid;
         if(s==null || lease==null || lease!==s.lease || lease.phase!=="bound" || lease.root!==this ||
            lease.grid!==s.grid || lease.panel==null || lease.panel.mcTileList==null || !ApexCatalogGridLeaseCurrent(lease))return;
         var list:Object=lease.panel.mcTileList;var view:Object=list.GetGridView();
         if(view==null || view.stage!==stage || lease!==s.lease || lease.panel.mcTileList!==list ||
            list.mGridLayout!==lease.grid || lease.grid.GetDataFeed()!==lease.feed || lease.grid.GetCellView!==lease.cell_type ||
            !ApexCatalogGridLeaseCurrent(lease))return;
         var key:String=ApexCatalogPanelKey(lease.panel);if(key==="")return;
         if(s.authority_owners==null)s.authority_owners={};
         var prior:Object=s.authority_owners[key];
         if(prior!=null && prior.blocked===true)return;
         if(prior!=null && prior.grid===lease.grid && prior.panel===lease.panel && prior.stage===lease.stage &&
            prior.view===view && prior.feed===lease.feed && prior.cell_type===lease.cell_type &&
            ApexCatalogAuthorityEqual(prior.scope,lease))return;
         s.authority_owners[key]={grid:lease.grid,panel:lease.panel,view:view,feed:lease.feed,
            cell_type:lease.cell_type,stage:lease.stage,scope:ApexCatalogAuthorityScope(lease),
            blocked:false,receipt:null,probe:false};
      }

      private function ApexCatalogAuthorityHeld(grid:Object) : Object {
         var s:Object=apexCatalogGrid;if(s==null || s.authority_owners==null || grid==null)return null;
         for each(var saved:Object in s.authority_owners) {
            if(saved.grid===grid && saved.blocked===true)return saved;
         }
         return null;
      }

      private function ApexCatalogAuthorityEffectHeld(row:Object) : Boolean {
         if(row==null)return false;
         if(row.authority_forget===true)return true;
         if(row.grid!=null)return ApexCatalogAuthorityHold(row.grid);
         var s:Object=apexCatalogGrid;var terminal:Boolean=false;
         if(s!=null && s.authority_owners!=null)for each(var held:Object in s.authority_owners) {
            if(held.blocked!==true)continue;
            terminal=true;
            if(row.cell!=null && held.view!=null && row.cell.parent===held.view)return true;
         }
         if(!terminal)return false;
         // A legacy record without a grid or matching original parent is not
         // permission to touch a possibly transferred cell. Retain the reason
         // on this Main-owned record and expose a bounded diagnostic count.
         row.authority_forget=true;row.authority_forget_reason="unattributed-effect-after-authority-loss";
         if(int(s.authority_unattributed_effects)<int.MAX_VALUE)s.authority_unattributed_effects=int(s.authority_unattributed_effects)+1;
         return true;
      }

      private function ApexCatalogAuthorityHold(grid:Object) : Boolean {
         var s:Object=apexCatalogGrid;if(s==null || grid==null)return false;
         var held:Object=ApexCatalogAuthorityHeld(grid);if(held!=null)return true;
         if(!ApexCatalogAuthorityAvailable(grid))return false;
         var terminal:Object=s.grid===grid && s.last!=null && s.last.authority_lost===true ? s.last : grid.ApexGridAuthorityStatus();
         if(terminal==null)return false;
         var panel:Object=s.grid===grid && s.lease!=null ? s.lease.panel : mCurrentPanel;
         var key:String=ApexCatalogPanelKey(panel);if(key==="")return true;
         if(s.authority_owners==null)s.authority_owners={};
         held=s.authority_owners[key];
         // A missing or foreign capture cannot authorize fallback or recovery.
         if(held==null || held.grid!==grid) {
            held={grid:grid,panel:panel,view:null,feed:null,cell_type:null,stage:null,scope:null,
               blocked:false,receipt:null,probe:false};s.authority_owners[key]=held;
         }
         var scope:Object=ApexCatalogAuthorityScope(terminal.scope);
         var valid:Boolean=terminal.protocol===1 && terminal.phase==="authority-lost" && terminal.authority_lost===true &&
            terminal.terminal_blocked===true && terminal.error===null && terminal.reason is String && terminal.reason.length<=160 &&
            terminal.generation is int && terminal.revision is int && terminal.lease_released is Boolean && terminal.input_released is Boolean &&
            terminal.release_refused is String && terminal.release_refused.length<=160 && terminal.lifecycle_changed is Boolean &&
            ApexCatalogAuthorityEqual(held.scope,scope);
         held.blocked=true;held.probe=false;
         held.receipt={protocol:1,phase:"authority-lost",authority_lost:true,terminal_blocked:true,error:null,
            reason:valid ? terminal.reason : "Unverified catalogue authority-loss receipt",generation:valid ? terminal.generation : 0,
            revision:valid ? terminal.revision : 0,lease_released:valid && terminal.lease_released===true,
            input_released:valid && terminal.input_released===true,release_refused:valid ? terminal.release_refused : "receipt-validation",
            lifecycle_changed:valid && terminal.lifecycle_changed===true,scope:ApexCatalogAuthorityScope(held.scope),verified:valid};
         s.waiting="authority-lost";
         return true;
      }

      private function ApexCatalogAuthorityRecover(panel:Object,grid:Object) : Boolean {
         var s:Object=apexCatalogGrid;var held:Object=ApexCatalogAuthorityHeld(grid);
         if(s==null || held==null || held.receipt==null || held.receipt.verified!==true || s.running!==true ||
            stage==null || panel!==mCurrentPanel || panel.stage!==stage || !ApexCatalogPanelVisible(panel) ||
            panel.mcTileList==null || panel.mcTileList.mGridLayout!==grid || ApexCatalogGridProductPanel(panel)==="")return false;
         var list:Object=panel.mcTileList;var scope:Object=held.scope;
         var identityChanged:Boolean=held.panel!==panel || held.stage!==stage || held.view!==list.GetGridView() ||
            held.feed!==grid.GetDataFeed() || held.cell_type!==grid.GetCellView;
         var cachedChanged:Boolean=mCurrSimInfo!=null && (String(mCurrSimInfo.simId)!==scope.sim_id ||
            String(mCurrSimInfo.householdId)!==scope.household_id || apexFormsSelectedId!==scope.owner ||
            apexOwnerSession!==scope.session || int(mCurrSimInfo.occultLayer)!==scope.layer ||
            int(mCurrSimInfo.occultType)!==scope.native_kind || int(mCurrSimInfo.allOccultTypes)!==scope.native_mask ||
            apexFormsNativeGeneration!==scope.native_generation || int(mCurrState)!==scope.state);
         if(!identityChanged && !cachedChanged && held.probe!==true)return false;
         var notified:Boolean=held.probe===true;
         held.probe=false;
         var cached:Object=mCurrSimInfo==null ? null : {sim_id:String(mCurrSimInfo.simId),household_id:String(mCurrSimInfo.householdId),
            owner:apexFormsSelectedId,session:apexOwnerSession,layer:int(mCurrSimInfo.occultLayer),native_kind:int(mCurrSimInfo.occultType),
            shell_kind:scope.shell_kind,native_mask:int(mCurrSimInfo.allOccultTypes),native_generation:apexFormsNativeGeneration,
            outfit_type:scope.outfit_type,outfit_index:scope.outfit_index,state:int(mCurrState)};
         if(!notified && held.observed!=null && ApexCatalogAuthorityEqual(held.observed.scope,cached) &&
            held.observed.panel===panel && held.observed.stage===stage && held.observed.view===list.GetGridView() &&
            held.observed.feed===grid.GetDataFeed() && held.observed.cell_type===grid.GetCellView)return false;
         held.observed={scope:cached,panel:panel,stage:stage,view:list.GetGridView(),feed:grid.GetDataFeed(),cell_type:grid.GetCellView};
         var context:Object=ApexCatalogGridObserve();
         identityChanged=held.panel!==panel || held.stage!==stage || held.view!==list.GetGridView() ||
            held.feed!==grid.GetDataFeed() || held.cell_type!==grid.GetCellView;
         if(apexCatalogGrid!==s || ApexCatalogAuthorityHeld(grid)!==held || context==null ||
            panel!==mCurrentPanel || panel.stage!==stage || list!==panel.mcTileList || list.mGridLayout!==grid ||
            (!identityChanged && ApexCatalogAuthorityEqual(scope,context)))return false;
         var feed:Object=grid.GetDataFeed();var view:Object=list.GetGridView();var cell:Class=grid.GetCellView as Class;
         if(feed==null || view==null || cell==null || s.generation>=int.MAX_VALUE)return false;
         if(held.attempted!=null && ApexCatalogAuthorityEqual(held.attempted.scope,context) &&
            held.attempted.panel===panel && held.attempted.stage===stage && held.attempted.view===view &&
            held.attempted.feed===feed && held.attempted.cell_type===cell)return false;
         held.attempted={scope:ApexCatalogAuthorityScope(context),panel:panel,stage:stage,view:view,feed:feed,cell_type:cell};
         var previousLease:Object=s.lease;var previousGrid:Object=s.grid;
         var lease:Object={active:true,generation:++s.generation,root:this,stage:stage,panel:panel,grid:grid,
            view:view,panel_kind:ApexCatalogGridProductPanel(panel),cell_type:cell,feed:feed,sim_id:context.sim_id,
            household_id:context.household_id,owner:context.owner,session:context.session,layer:context.layer,
            native_kind:context.native_kind,shell_kind:context.shell_kind,native_mask:context.native_mask,
            native_generation:context.native_generation,outfit_type:context.outfit_type,outfit_index:context.outfit_index,
            state:context.state,phase:"bound",frame_validated:true};
         s.lease=lease;s.grid=grid;
         var accepted:Boolean=false;
         try {
            var request:Object=ApexCatalogGridRequest(lease);if(request==null)return false;
            s.last=grid.ApexGridBegin(request);
            if(grid.ApexGridAuthorityStatus()!=null || s.last==null || s.last.authority_lost===true ||
               s.last.error!=null || apexCatalogGrid!==s || s.lease!==lease || !ApexCatalogGridLeaseCurrent(lease) ||
               !ApexCatalogGridMatches(lease,ApexCatalogGridObserve()))return false;
            accepted=true;held.blocked=false;held.recovered=true;s.waiting="";
            ApexCatalogAuthorityRemember(lease);
            return true;
         } finally {
            lease.frame_validated=false;
            if(!accepted && apexCatalogGrid===s && s.lease===lease) {s.lease=previousLease;s.grid=previousGrid;}
         }
      }
