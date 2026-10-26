      // Private terminal schema continuation. Only copied primitives survive
      // a transaction yield. Default CASCatalogProduct requests stay separate.
      private function ApexGridFeaturedIdentity(item:Object) : Object {
         var s:Object=apexGridState;
         if(s==null || s.request==null || !("featuredRowIdentity" in s.request) || s.request.featuredRowIdentity==null)return null;
         if(!(s.request.featuredRowIdentity is Function))throw new Error("Featured row identity callback unavailable");
         if(item==null)return null;
         var source:Object=s.request.featuredRowIdentity(item);
         if(source==null || source.schema!=="featured-look-v1" ||
            typeof source.look_id!="string" || !/^[1-9][0-9]{0,19}$/.test(source.look_id) ||
            typeof source.outfit_id!="string" || !/^[1-9][0-9]{0,19}$/.test(source.outfit_id) ||
            typeof source.pack_id!="number" || !isFinite(source.pack_id) || source.pack_id<0 || int(source.pack_id)!==source.pack_id)
            throw new Error("Native Featured Look row schema differs");
         return {schema:"featured-look-v1",look_id:String(source.look_id),outfit_id:String(source.outfit_id),pack_id:int(source.pack_id)};
      }

      private function ApexGridFeaturedSame(actual:Object,expected:Object) : Boolean {
         return actual!=null && expected!=null && actual.schema==="featured-look-v1" && expected.schema==="featured-look-v1" &&
            actual.look_id===expected.look_id && actual.outfit_id===expected.outfit_id && actual.pack_id===expected.pack_id;
      }
