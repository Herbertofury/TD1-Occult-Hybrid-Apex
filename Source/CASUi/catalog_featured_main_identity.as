      private function ApexCatalogGridFeaturedIdentity(item:Object) : Object {
         // Exact schema: the native feed's wrapper is not CASCatalogProduct.
         // Native Draw and OnCatalogClick continue receiving this original row.
         if(item==null || !("product" in item) || !(item.product is CASFeaturedLook) ||
            !("outfit" in item) || item.outfit==null || !("data_id" in item.outfit))return null;
         var look:CASFeaturedLook=item.product as CASFeaturedLook;
         if(typeof look.data_id!="string" || typeof item.outfit.data_id!="string")return null;
         return {schema:"featured-look-v1",look_id:look.data_id,outfit_id:String(item.outfit.data_id),pack_id:int(look.packId)};
      }
