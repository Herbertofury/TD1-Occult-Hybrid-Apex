      override public function PositionCells() : void
      {
         // The armed adapter owns geometry AND its selection phase. Guard the
         // override before its unconditional selection tail, not just super.
         // Direct feed/selection refresh routes remain their original bodies.
         if(ApexGridNativeGuard("position",null))return;
         super.PositionCells();
         this.UpdateSelectionInCells();
      }
