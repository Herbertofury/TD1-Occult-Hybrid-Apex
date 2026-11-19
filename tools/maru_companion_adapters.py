"""Compile five small identity adapters; retain the rest of the donor ABC.

These are compiler stubs only. Constructors, fields, static initializers and
every unselected donor method are restored from the pinned input by the ABC
retainer. No decompiled third-party source is checked into the repository.
"""
ROUTES = {
    'dcc.history.AgeFilter': ('Read', 'Current'),
    'dcc.history.SavedOutfitNames': ('EyeContext',),
    'dcc.history.SkinAdjust': ('ContextKey',),
    'dcc.history.OutfitPreview': ('Context',),
}

SOURCES = {
    'dcc.history.AgeFilter': '''
      private static var cachedSim:Object;
      private static var sampled:int;
      private static function ResetOwner():void {}
      public static function Group(sim:Object):int {return 0;}
      private static function Read():Object {
         ResetOwner();sampled=getTimer();cachedSim=null;
         var view:Object=CommunicationManager.CallUIService("ApexCatalogSearchSource",{operation:"appearance-context"});
         if(view!=null && view.info!=null && Group(view.info)) cachedSim=view.info;
         return cachedSim;
      }
      public static function Current():Object {return Read();}
''',
    'dcc.history.SavedOutfitNames': '''
      public static function EyeContext(sim:Object):String {
         var view:Object=CommunicationManager.CallUIService("ApexCatalogSearchSource",{operation:"appearance-context"});
         if(view==null || sim==null || String(sim.simId)!==view.sim ||
            (sim.apexAppearanceLease!==undefined && sim.apexAppearanceLease!==view.key)) return "";
         return view.key+":"+int(sim.gender)+":"+int(sim.age)+":"+int(sim.speciesType);
      }
''',
    'dcc.history.SkinAdjust': '''
      private static function ContextKey(refresh:Boolean=false):String {
         var view:Object=CommunicationManager.CallUIService("ApexCatalogSearchSource",{operation:"appearance-context"});
         return view==null ? "" : String(view.key);
      }
''',
    'dcc.history.OutfitPreview': '''
      public static function Context():Object {
         var view:Object=CommunicationManager.CallUIService("ApexCatalogSearchSource",{operation:"appearance-context"});
         if(view==null) return null;
         var slot:Object=CommunicationManager.CallGameService("CasGetCurrSimOutfitSlot",null,true);
         var after:Object=CommunicationManager.CallUIService("ApexCatalogSearchSource",{operation:"appearance-context"});
         if(after==null || view.key!==after.key || slot==null || slot.outfit_type===undefined ||
            slot.outfit_index===undefined || int(slot.outfit_type)<0 || int(slot.outfit_index)<0) return null;
         return {key:view.key+"/"+int(slot.outfit_type)+"/"+int(slot.outfit_index),sim:view.sim,
            type:int(slot.outfit_type),index:int(slot.outfit_index)};
      }
''',
}


def source(name):
    if name not in ROUTES:
        raise ValueError('Unreviewed Companion identity adapter')
    package, cls = name.rsplit('.', 1)
    return ('package ' + package + ' {\n'
            'import olympus.io.CommunicationManager;\nimport flash.utils.getTimer;\n'
            'public final class ' + cls + ' {\n' + SOURCES[name] + '\n}}\n')
