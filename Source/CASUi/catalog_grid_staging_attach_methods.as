      public function ApexGridAttach(cell:Object) : void {
         var s:Object=apexGridState;var p:Object=s==null ? null : s.presentation;
         var j:Object=s==null ? null : s.job;var view:Object=mGridView;
         // A fresh factory-owned staging widget must not cover the retained
         // ready bank between attachment and its later budgeted Draw atom.
         var staged:Boolean=s!=null && s.armed===true && p!=null && p.working===true && j!=null &&
            s.view===view && s.lease===j && j.lease===true && j.pendingAttached===true &&
            j.pendingCell===cell && cell!=null && cell.parent==null;
         if(staged)cell.visible=false;
         mGridView.addChild(cell as DisplayObject);
         // Native ADDED_TO_STAGE/ConfigUI still runs exactly once. A callback
         // may have replaced/adopted the context; never hide that new owner.
         if(staged && apexGridState===s && s.presentation===p && s.job===j && s.view===view &&
            mGridView===view && p.working===true && s.lease===j && j.pendingCell===cell && cell.parent===view)
            cell.visible=false;
      }
