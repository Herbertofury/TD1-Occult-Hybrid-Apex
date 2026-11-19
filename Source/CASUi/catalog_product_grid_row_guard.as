         if(item!=null && "rowValidate" in s.request && s.request.rowValidate!=null &&
            (!(s.request.rowValidate is Function) || s.request.rowValidate(item)!==true))
            throw new Error("Native catalogue row is not an admitted CASCatalogProduct");
