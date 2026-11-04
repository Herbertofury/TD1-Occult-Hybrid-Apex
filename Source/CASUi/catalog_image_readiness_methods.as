      public final function ApexImageReadyFor(resource:String) : Boolean {
         // Native loader fields are authoritative. GetLoadedImage by itself can
         // still point to an older request or a loading indicator sibling.
         return resource!=null && resource.length>0 && this.mResourceId===resource &&
            this.mLoadUrl==null && !this.mbQueuedResourceLoad && this.mImageRegion!=null &&
            this.mContainer!=null && this.mContainer.stage!=null && this.GetLoadedImage()!=null;
      }
