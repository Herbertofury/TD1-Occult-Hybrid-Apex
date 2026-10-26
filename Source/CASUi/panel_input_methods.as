      // Own toolbar input before HistoryHost's retained drawer capture hooks.
      // Body, tab, card and other native controls keep their original routing.
      private function ApexPanelsCapture(event:flash.events.MouseEvent) : void
      {
         if(apexPanels==null || stage==null || event==null || event.currentTarget!==stage || apexPanels.stage!==stage ||
            (event.type!=flash.events.MouseEvent.MOUSE_DOWN && event.type!=flash.events.MouseEvent.CLICK))return;
         var root:flash.display.Sprite=apexPanels.root as flash.display.Sprite;
         var grip:flash.display.Sprite=apexPanels.grip as flash.display.Sprite;
         if(root==null || grip==null || root.parent!==this || grip.parent!==root || root.stage!==stage || grip.stage!==stage ||
            !root.visible || !grip.visible)return;
         var drawer:Object=apexPanels.host==null ? null : apexPanels.host.dccHistoryRuntimeDrawer;
         if(drawer==null || drawer[0]!==root)return;
         var body:flash.display.DisplayObject=root.getChildByName("body");
         if(body==null || !body.visible)return;
         var node:flash.display.DisplayObject=root;
         while(node!=null && node!==stage) {
            if(!node.visible)return;
            node=node.parent;
         }
         if(node!==stage)return;
         var control:flash.display.DisplayObject=null;
         node=event.target as flash.display.DisplayObject;
         while(node!=null && node!==grip) {
            if(node.parent===grip && ["apexPanel_move","apexPanel_smaller","apexPanel_larger","apexPanel_lock","apexPanel_reset"].indexOf(node.name)>=0)
               control=node;
            node=node.parent;
         }
         if(node!==grip || control==null)return;
         // Consume before executing: a locked move or an action failure must
         // never fall through to popup teardown or a second target listener.
         event.stopImmediatePropagation();event.preventDefault();
         var name:String=String(control.name);
         if(event.type==flash.events.MouseEvent.MOUSE_DOWN) {
            if(name=="apexPanel_move")ApexPanelsDragStart(event);
            return;
         }
         ApexPanelsAction(name);
      }

      private function ApexPanelsAction(name:String) : void
      {
         if(apexPanels==null)return;
         if(name=="apexPanel_smaller")ApexPanelsScale(Number(apexPanels.scale)-0.05);
         else if(name=="apexPanel_larger")ApexPanelsScale(Number(apexPanels.scale)+0.05);
         else if(name=="apexPanel_lock") {ApexPanelsDragEnd();apexPanels.locked=!apexPanels.locked;ApexPanelsApply();ApexPanelsChanged();}
         else if(name=="apexPanel_reset") {apexPanels.x=-1;apexPanels.y=-1;apexPanels.scale=1;apexPanels.locked=false;ApexPanelsApply();ApexPanelsChanged();}
      }
