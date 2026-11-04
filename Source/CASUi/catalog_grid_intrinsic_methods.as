      // Native constructor geometry belongs to an authenticated class/asset
      // lifetime. The donor's fitted root scale is layout policy, not geometry.
      private function ApexGridIntrinsicContext(g:Object,s:Object,type:Class) : Boolean {
         var o:Object=s==null ? null : s.owner;
         return g!=null && o!=null && g.state===s && g.owner===o && g.ownerGeneration===s.ownerGeneration &&
            g.feed===mGridData && g.view===mGridView && g.panel===s.panel && g.type===type &&
            g.epoch===int(s.intrinsicGeometryEpoch) && g.session===o.session && g.sim===o.sim_id &&
            g.household===o.household_id && g.form===o.owner && g.layer===o.layer && g.kind===o.native_kind &&
            g.shell===o.shell_kind && g.mask===o.native_mask && g.generation===o.native_generation &&
            g.outfitType===o.outfit_type && g.outfitIndex===o.outfit_index && g.menu===o.state;
      }

      private function ApexGridIntrinsicCapture(cell:Object) : Boolean {
         var s:Object=apexGridState;
         if(s==null || !s.armed || s.request==null || s.request.intrinsicGeometryContract!==1 ||
            s.request.intrinsicGeometrySource!=="exact-native-constructor-v1" || s.intrinsicGeometryForeign===true)return false;
         var type:Class=s.request.intrinsicGeometryClass as Class;var o:Object=s.owner;
         if(type==null || type!==mCellType || o==null || o.active!==true || o.cell_type!==type ||
            int(o.generation)!=s.ownerGeneration || s.request.owner!==o || s.feed!==mGridData || s.view!==mGridView ||
            s.panel!==s.request.panel || !(cell is type) || getQualifiedClassName(cell)!==getQualifiedClassName(type) ||
            getQualifiedClassName(this)!=="olympus.layout::SelectableRecyclingGridLayout")return false;
         var g:Object=s.intrinsicGeometry;
         if(!ApexGridIntrinsicContext(g,s,type)) {s.intrinsicGeometry=null;g=null;}
         var sx:Number=Number(cell.scaleX);var marker:Object=cell.getChildByName("apexCatalogCardScale");
         var aspect:Number=marker==null ? Number(cell.scaleY)/sx : Number(marker.scaleY);
         var height:Number=cell.mcHitArea==null ? Number(cell.getBounds(cell).height) : Number(cell.mcHitArea.height);
         if(!isFinite(sx) || sx<=0 || !isFinite(height) || height<=0 || !isFinite(aspect) || aspect<=0)return false;
         if(g!=null && (g.height!==height || g.aspect!==aspect)) {
            s.intrinsicGeometryForeign=true;s.intrinsicGeometry=null;return false;
         }
         var width:Number;
         if(g==null) {
            width=Number(cell.width)/sx;
            if(!isFinite(width) || width<=0)return false;
            g={state:s,owner:o,ownerGeneration:s.ownerGeneration,feed:mGridData,view:mGridView,panel:s.panel,type:type,
               epoch:int(s.intrinsicGeometryEpoch),session:o.session,sim:o.sim_id,household:o.household_id,form:o.owner,
               layer:o.layer,kind:o.native_kind,shell:o.shell_kind,mask:o.native_mask,generation:o.native_generation,
               outfitType:o.outfit_type,outfitIndex:o.outfit_index,menu:o.state,width:width,height:height,aspect:aspect};
            s.intrinsicGeometry=g;s.intrinsicGeometryCaptures=int(s.intrinsicGeometryCaptures)+1;
         } else {width=Number(g.width);s.intrinsicGeometryReuses=int(s.intrinsicGeometryReuses)+1;}
         s.intrinsics[cell]={width:width,height:height,aspect:aspect,type:type};
         s.naturalWidth=width;s.naturalHeight=height;s.naturalAspect=aspect;s.measurementReady=true;return true;
      }

      private function ApexGridIntrinsicReset(foreign:Boolean) : void {
         var s:Object=apexGridState;if(s==null)return;
         if(int(s.intrinsicGeometryEpoch)>=int.MAX_VALUE)throw new Error("Native intrinsic geometry epoch exhausted");
         s.intrinsicGeometryEpoch=int(s.intrinsicGeometryEpoch)+1;
         s.intrinsicGeometry=null;s.intrinsicGeometryForeign=foreign;
         s.intrinsicGeometryResets=int(s.intrinsicGeometryResets)+1;
      }
