"""Private exact native rail/search layout continuation; no production edits."""
from pathlib import Path
import cas_grid_pool as pool
ROOT=Path(__file__).resolve().parents[1]
MAIN_REPLACED=('ApexSearchInitialize','ApexSearchDispose','ApexSearchAttach','ApexSearchRestore','ApexSearchStatus')
BODY_REPLACED=('Layout','NativeLayout','RestoreList')
BODY_ADDED=('ApexListLayoutRecord','ApexNativeRailReceipt')
CATALOG_REPLACED=('RefreshLayout',)

def main(source):
 source=pool.edit_method(source,'ApexSearchInitialize',[
  ('apexSearch.registered=RegisterServiceHandler("ApexCatalogSearchSource",ApexSearchSource);',
   'apexSearch.registered=RegisterServiceHandler("ApexCatalogSearchSource",ApexSearchSource);\n         apexSearch.list_layouts=[null,null,null,null,null,null];\n         apexSearch.geometry_registered=RegisterServiceHandler("ApexCatalogListGeometry",ApexCatalogListGeometry);')])
 source=pool.edit_method(source,'ApexSearchDispose',[
  ('         ApexSearchRestore();apexSearch=null;',
   '''         ApexSearchRestore();
         if(apexSearch!=null && apexSearch.geometry_registered===true)
            UnregisterServiceHandler("ApexCatalogListGeometry",ApexCatalogListGeometry);
         if(apexSearch!=null && apexSearch.list_layouts!=null)
            for each(var record:Object in apexSearch.list_layouts)if(record!=null)record.active=false;
         apexSearch=null;''')])
 source=pool.edit_method(source,'ApexSearchRestore',[
  ('            if(g.no_results!=null && g.no_results.y==g.no_results_y+52)',
   '            if(g.list_layout==null && g.no_results!=null && g.no_results.y==g.no_results_y+52)'),
  ('            if(apexSearch.list!=null && apexSearch.list.y==g.list_y+52) {',
   '            if(g.list_layout!=null)ApexCatalogSearchListRestore(g);\n            else if(apexSearch.list!=null && apexSearch.list.y==g.list_y+52) {')])
 old='''         if(list.y!=g.list_y+52) {g.list_y=list.y;g.list_height=list.height;}
         if(bubble.y!=g.bubble_y+52) bubble.y=g.bubble_y+52;
         if(list.y!=g.list_y+52) list.y=g.list_y+52;
         var height:Number=Math.max(32,g.list_height-52);
         if(list.height!=height) list.height=height;'''
 new='''         if(bubble.y!=g.bubble_y+52) bubble.y=g.bubble_y+52;
         if(!ApexCatalogSearchListApply(panel,list,g)) {
            if(list.y!=g.list_y+52) {g.list_y=list.y;g.list_height=list.height;}
            if(list.y!=g.list_y+52) list.y=g.list_y+52;
            var height:Number=Math.max(32,g.list_height-52);
            if(list.height!=height) list.height=height;
         }'''
 source=pool.edit_method(source,'ApexSearchAttach',[(old,new),
  ('         if(g.no_results!=null) {\n            if(g.no_results.y!=g.no_results_y+52)',
   '''         if(g.no_results!=null && g.list_layout!=null && panel===mcClothingPanel) {
            g.no_results_y=Number(g.list_layout.raw_y)+Number(g.list_layout.rail);
            if(g.no_results.y!==g.list_layout.applied_y)g.no_results.y=g.list_layout.applied_y;
         } else if(g.no_results!=null) {
            if(g.no_results.y!=g.no_results_y+52)''')])
 source=pool.edit_method(source,'ApexSearchStatus',[
  ('         return {available:apexSearch.root!=null,text:apexSearch.text,',
   '         return {list_geometry:ApexCatalogListStatus(),available:apexSearch.root!=null,text:apexSearch.text,')])
 return source+'\n'+(ROOT/'Source/CASUi/catalog_list_inset_methods.as').read_text()

def catalog(source):
 source=source.replace('protected function RefreshLayout','public function RefreshLayout',1)
 source=pool.edit_method(source,'RefreshLayout',[
  ('         this.mcTileList.height = this.mcPanelBackground.height - this.mcTileList.y - this.GetTileListYBottomOffset();',
   '''         this.mcTileList.height = this.mcPanelBackground.height - this.mcTileList.y - this.GetTileListYBottomOffset();
         // The preceding exact EA assignments are the authoritative raw base.
         // The derived Clothing callback consumes this generation, never pixels.
         if(apexRawListGeneration<int.MAX_VALUE) {
            apexRawListGeneration++;
            apexRawListLayout={protocol:1,panel:this,list:this.mcTileList,stage:stage,generation:apexRawListGeneration,
               y:Number(this.mcTileList.y),height:Number(this.mcTileList.height)};
            CommunicationManager.CallUIService("ApexCatalogListGeometry",{operation:"native-base",panel:this,list:this.mcTileList,
               generation:apexRawListGeneration});
         }''')])
 helper='''
      private var apexRawListGeneration:int;
      private var apexRawListLayout:Object;
      public final function ApexRawListGeneration() : int {return apexRawListGeneration;}
      public final function ApexRawListBaseline() : Object {
         var r:Object=apexRawListLayout;
         if(r==null || r.panel!==this || r.list!==mcTileList || r.stage!==stage)return null;
         return {protocol:1,panel:this,list:r.list,stage:r.stage,generation:int(r.generation),y:Number(r.y),height:Number(r.height)};
      }
'''
 return source.replace('public function RefreshLayout','protected function RefreshLayout',1),helper

def body(source):
 source=source.replace('public static function','public function').replace('private static function','private function')
 source=pool.edit_method(source,'Layout',[
  ('            list = panel.mcTileList;','            list = panel.mcTileList;\n            var shared:Object=ApexListLayoutRecord(panel,list);'),
  ('            frame = panel.mcPanelBackground.getBounds(panel);',
   '''            if(shared!=null) {baseY=Number(shared.raw_y);baseHeight=Number(shared.raw_height);}
            frame = panel.mcPanelBackground.getBounds(panel);'''),
  ('            if(baseHeight < 208)','            if(baseHeight-(shared==null ? 0 : Number(shared.search)) < 208)'),
  ('            if(baseHeight < space + 80)','            if(baseHeight-(shared==null ? 0 : Number(shared.search)) < space + 80)'),
  ('            appliedY = baseY + space;',
   '''            appliedY = baseY + space;'''),
  ('            hasLayout = true;\n            if(Number(list.y) != appliedY)',
   '''            hasLayout = true;
            var composed:Boolean=shared!=null;
            if(composed) {
               if(shared.set_rail(shared,space,rail)!==true)return;
               appliedY=Number(shared.applied_y);appliedHeight=Number(shared.applied_height);
            }
            if(!composed && Number(list.y) != appliedY)'''),
  ('            if(Number(list.height) != appliedHeight)','            if(!composed && Number(list.height) != appliedHeight)'),
  ('            rail.y = baseY;','            rail.y = composed ? Number(shared.rail_y) : baseY;')])
 source=pool.edit_method(source,'NativeLayout',[
  ('            baseY = Number(layoutList.y);\n            baseHeight = Number(layoutList.height);',
   '''            var shared:Object=ApexListLayoutRecord(panel,layoutList);
            baseY = shared==null ? Number(layoutList.y) : Number(shared.raw_y);
            baseHeight = shared==null ? Number(layoutList.height) : Number(shared.raw_height);''')])
 source=pool.edit_method(source,'RestoreList',[
  ('            if(layoutList && hasLayout)',
   '''            var shared:Object=apexListLayout;apexListLayout=null;
            if(shared!=null) {
               if(shared.current(shared)===true && shared.set_rail(shared,0)===true &&
                  host && host.txtNoResults && Number(host.txtNoResults.y)===appliedY)
                  host.txtNoResults.y=Number(shared.applied_y);
            }
            else if(layoutList && hasLayout)''')])
 # Keep every other original static body and trait unchanged in the retainer;
 # this source-only marker is replaced with one private static slot at graft.
 helper='''
      private static var apexListLayout:Object;

      private static function ApexListLayoutRecord(panel:Object,list:Object) : Object {
         var r:Object=apexListLayout;
         if(r!=null && r.protocol===1 && r.panel===panel && r.list===list && r.stage===panel.stage &&
            r.current is Function && r.set_rail is Function && r.current(r)===true)return r;
         apexListLayout=null;
         r=CommunicationManager.CallUIService("ApexCatalogListGeometry",{operation:"lookup",panel:panel,list:list});
         if(r==null || r.protocol!==1 || r.panel!==panel || r.list!==list || r.stage!==panel.stage ||
            !(r.current is Function) || !(r.set_rail is Function) || r.current(r)!==true)return null;
         apexListLayout=r;return r;
      }

      public static function ApexNativeRailReceipt(panel:Object,list:Object) : Object {
         if(host!==panel || layoutList!==list || !hasLayout || panel.stage==null ||
            !(panel.ApexRawListBaseline is Function))return null;
         var raw:Object=panel.ApexRawListBaseline();
         if(raw==null || raw.protocol!==1 || raw.panel!==panel || raw.list!==list || raw.stage!==panel.stage ||
            Number(raw.y)!==baseY || Number(raw.height)!==baseHeight)return null;
         var space:Number=appliedY===baseY+68 && appliedHeight===baseHeight-68 ? 68 :
            (appliedY===baseY+128 && appliedHeight===baseHeight-128 ? 128 : 0);
         if(space===0)return null;
         var y:Number=Math.round(appliedY*20)/20;var h:Number=Math.round(appliedHeight*20)/20;
         if(appliedHeight!==baseHeight-space || Number(list.y)!==y || Number(list.height)!==h)return null;
         return {protocol:1,panel:panel,list:list,stage:panel.stage,generation:int(raw.generation),raw_y:baseY,raw_height:baseHeight,
            rail:space,rail_view:rail,native_y:y,native_height:h};
      }

'''
 # Static declarations are restored exactly for compilation of the original
 # class. A private helper uses an unambiguous distinct marker below.
 for name in BODY_REPLACED:
  a,b=pool.method_extent(source,name);part=source[a:b]
  source=source[:a]+part.replace('function '+name,'static function '+name,1)+source[b:]
 # All other original source static keywords were normalized only to locate
 # exact bodies; restore them from the original source by owned spans.
 # The caller uses this function's returned owned methods, not a full compile.
 return source,helper
