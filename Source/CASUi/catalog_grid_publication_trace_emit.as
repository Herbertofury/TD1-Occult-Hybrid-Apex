      private function ApexGridPublicationTrace(callback:Function,event:String,generation:int,target:int,oldCount:int) : void
      {
         if(callback==null)return;
         // Diagnostic callback failure cannot replace a native exception or
         // alter publication/rollback. Only scalar arguments cross the movie.
         try {callback(event,generation,target,oldCount);}catch(diagnosticError:*) { }
      }
