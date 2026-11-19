      // Lease complete feeds to the original synchronous save/remove handler.
      private function ApexPanelConsumer(value:Object) : Boolean
      {
         if(apexPanels==null)return false;
         try {
            if(value==null || ["save","remove"].indexOf(String(value.kind))<0 || !(value.callback is Function))
               throw new Error("Invalid outfit action");
            var drawer:Object=ApexPanelsDrawer();
            if(drawer==null || drawer[0]==null || drawer[0].stage!==stage || mCurrSimInfo==null)
               throw new Error("Outfit action no longer has its CAS view");
            var helpers:Object=apexPanels.helpers;
            if(helpers==null) {helpers={};apexPanels.helpers=helpers;}
            if(helpers.SavedOutfitNames==null)helpers.SavedOutfitNames=getDefinitionByName("dcc.history.SavedOutfitNames");
            if(helpers.SavedManage==null)helpers.SavedManage=getDefinitionByName("dcc.history.SavedManage");
            var dialog:Object=value.kind=="save" ? helpers.SavedOutfitNames.SavedManageDialogState() : null;
            if(value.kind=="save" && (helpers.SavedManage.IsRenaming() || dialog==null || dialog.dialog==null ||
               dialog.input==null || dialog.busy || String(dialog.input.text).replace(/^\s+|\s+$/g,"")==""))return false;
            var target:Object=value.event==null ? null : value.event.currentTarget;
            var running:Object=apexPanels.consumer_running;
            if(running!=null) {
               var valid:Boolean=running.kind===String(value.kind) && running.callback===value.callback &&
                  running.drawer===drawer && running.owner===apexPanels.owner && running.key===apexPanels.key;
               if(value.kind=="save")valid=valid && dialog.dialog===running.dialog && dialog.input===running.input &&
                  String(dialog.input.text)===running.name && String(dialog.sourceId)===running.source;
               else valid=valid && target===running.target;
               if(!valid) {running.refused=true;apexPanels.message="Outfit action changed before completion";}
               return !valid;
            }
            if(value.event!=null)value.event.stopImmediatePropagation();
            if(apexPanels.consumer!=null) {
               if(dialog!=null && dialog.error!=null)dialog.error.text="An outfit action is already updating. Please wait.";
               return true;
            }
            if(apexFormsDesiredId!="" || apexFormsApplying || apexFormsNativeState!="bound")
               throw new Error("Wait for the selected form to finish switching");
            if(dialog!=null && String(dialog.sourceId)!==String(mCurrSimInfo.simId))
               throw new Error("The save dialog belongs to a different Sim");
            var context:String=ApexPanelsContext(drawer);
            if(context=="" || apexPanels.owner=="")throw new Error("Outfit action lacks its exact owner");
            if(value.kind=="remove" && (target==null || target.stage!==stage || !target.visible || drawer[40]==null || !drawer[40].visible))
               throw new Error("Removal control is no longer available");
            var node:flash.display.DisplayObject=(value.kind=="save" ? dialog.dialog : target) as flash.display.DisplayObject;
            var owned:Boolean=false;
            while(node!=null && node!==stage) {
               if(node===drawer[0])owned=true;
               node=node.parent;
            }
            if(node!==stage || !owned)throw new Error("Outfit action belongs to a different CAS panel");
            apexPanels.consumer={kind:String(value.kind),callback:value.callback,drawer:drawer,owner:apexPanels.owner,
               context:context,target:target,dialog:dialog==null ? null : dialog.dialog,input:dialog==null ? null : dialog.input,
               name:dialog==null ? "" : String(dialog.input.text),source:dialog==null ? "" : String(dialog.sourceId),key:"",stamp:"",refused:false};
            // A consumer starts its own fresh capture, never a pre-click job.
            // The first resulting stamp is frozen; later edits cancel this
            // intent rather than silently saving/removing a different look.
            apexPanels.job=null;apexPanels.stamp_ticket="";apexPanels.stamp_retry=0;apexPanels.key="";
            if(dialog!=null && dialog.error!=null)dialog.error.text="Updating the current outfit…";
            ApexPanelRefreshGate();return true;
         } catch(error:Error) {
            apexPanels.message=error.message;
            if(dialog!=null && dialog.error!=null)dialog.error.text=error.message;
            return true;
         }
      }

      private function ApexPanelPersistGate(event:Object) : Boolean
      {
         if(apexPanels==null)return false;
         var drawer:Object=ApexPanelsDrawer();
         if(event==null || drawer==null || event.currentTarget!==drawer[108])return false;
         var running:Object=apexPanels.consumer_running;
         if(running!=null && running.kind=="save" && !running.refused && running.drawer===drawer &&
            running.owner===apexPanels.owner && running.key===apexPanels.key && apexPanels.job==null && !apexPanels.requested)return false;
         if("stopImmediatePropagation" in event)event.stopImmediatePropagation();
         apexPanels.message="Save requires a freshly completed outfit view";return true;
      }

      private function ApexPanelsConsumerCancel(request:Object,message:String) : void
      {
         if(apexPanels.consumer===request)apexPanels.consumer=null;
         apexPanels.message=message;
         try {
            if(request!=null && request.kind=="save" && apexPanels.helpers!=null && apexPanels.helpers.SavedOutfitNames!=null) {
               var dialog:Object=apexPanels.helpers.SavedOutfitNames.SavedManageDialogState();
               if(dialog!=null && dialog.dialog===request.dialog && dialog.error!=null)dialog.error.text=message;
            }
         } catch(noticeError:Error) { /* Cancellation must not depend on a surviving dialog. */ }
      }

      private function ApexPanelsConsume(drawer:Object,context:String,check_only:Boolean=false) : void
      {
         var request:Object=apexPanels.consumer;if(request==null)return;
         try {
         if(request.drawer!==drawer || request.owner!==apexPanels.owner || (!check_only && request.context!==context)) {
            ApexPanelsConsumerCancel(request,"Outfit action canceled because its Sim, form or outfit changed");return;
         }
         if(request.kind=="save") {
            var dialog:Object=apexPanels.helpers.SavedOutfitNames.SavedManageDialogState();
            if(dialog==null || dialog.dialog!==request.dialog || dialog.input!==request.input || dialog.busy ||
               dialog.input.stage!==stage || String(dialog.input.text)!==request.name || String(dialog.sourceId)!==request.source) {
               ApexPanelsConsumerCancel(request,"Saved-outfit action canceled because its dialog changed");return;
            }
         } else if(request.target==null || request.target.stage!==stage || !request.target.visible || drawer[40]==null || !drawer[40].visible) {
            ApexPanelsConsumerCancel(request,"Removal action canceled because its control changed");return;
         }
         var node:flash.display.DisplayObject=(request.kind=="save" ? request.dialog : request.target) as flash.display.DisplayObject;
         var owned:Boolean=false;
         while(node!=null && node!==stage) {
            if(!node.visible) {ApexPanelsConsumerCancel(request,"Outfit action canceled because its panel closed");return;}
            if(node===drawer[0])owned=true;
            node=node.parent;
         }
         if(node!==stage || !owned) {ApexPanelsConsumerCancel(request,"Outfit action canceled because its panel was removed");return;}
         if(check_only || apexPanels.job!=null || apexPanels.requested || apexPanels.stamp_ticket!="" || apexPanels.key=="")return;
         if(request.stamp=="" || apexPanels.key!==request.context+"|"+request.stamp) {
            ApexPanelsConsumerCancel(request,"Outfit action canceled because its appearance changed");return;
         }
         // Clear before invocation: exceptions and subsequent clicks cannot
         // replay this intent. Nested refresh reads this verified leased view.
         apexPanels.consumer=null;request.key=apexPanels.key;apexPanels.consumer_running=request;
         try {
            if(request.kind=="save") {
               if(dialog.error!=null)dialog.error.text="";
               request.callback(null);
            }
            else request.target.dispatchEvent(new flash.events.MouseEvent(flash.events.MouseEvent.CLICK));
         } catch(error:Error) {apexPanels.message=error.message;}
         finally {apexPanels.consumer_running=null;}
         } catch(validationError:Error) {ApexPanelsConsumerCancel(request,validationError.message);}
      }
