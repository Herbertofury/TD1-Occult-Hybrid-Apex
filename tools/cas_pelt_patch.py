"""Bind EA's wing/pelt header to the displayed owner, not its backing slot."""
import re

PANE = 'widgets.CAS.Customizer.Panes.PeltMarkings.PeltMarkingsPane'
BUTTON = 'widgets.CAS.Customizer.Panes.PeltMarkings.PeltPaintLayerButton'
CONTEXT = '''var apexInfo:Object=CASStateData.GetCurrentSimInfo(true);
         var apexPair:Object=CommunicationManager.CallUIService("ApexFormPairPanel",{operation:"status",sim_id:String(apexInfo.simId)});
         if(apexPair!=null && apexPair.enabled===true && apexPair.native_kind is int &&
            [1,2,4,8,16,32,64].indexOf(int(apexPair.native_kind))>=0) {
            // CASStateData is the UI cache; membership and appearance data
            // stay intact. Its PetPaintMode setter must recognize Fairy.
            apexInfo.occultType=int(apexPair.native_kind);
            apexInfo.occultLayer=apexPair.selected_owner_id===apexPair.base_owner_id?0:1;
         }
         '''


def replace(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Installed wing/pelt header anchor differs: '+old[:80])
    return source.replace(old, new, 1)


def inject(source, button=False):
    source = re.sub(r'\s*\[Embed\([^\n]*\)\]', '', source)
    if button:
        return replace(source,
            'if(CASStateData.GetCurrentSimInfo(true).occultType == OccultTypes.OCCULT_FAIRY)',
            CONTEXT+'if(apexInfo.occultType == OccultTypes.OCCULT_FAIRY)')
    source = replace(source, 'CASStateData.PetPaintMode = param1;', CONTEXT+'CASStateData.PetPaintMode = param1;')
    # An empty imported palette disables the five native layer controls. EA's
    # later valid-color path updates their colors but never enables them again.
    # Recover only a layer whose exact selected color resolved in EA's palette.
    source = replace(source, '                  this.mLayerComponents[_loc3_].color = _loc6_["color"];',
        '                  this.mLayerComponents[_loc3_].enabled = true;\n'
        '                  this.mLayerComponents[_loc3_].color = _loc6_["color"];')
    return replace(source,
        'var _loc2_:Boolean = CASStateData.GetCurrentSimInfo(true).occultType == OccultTypes.OCCULT_FAIRY;',
        CONTEXT+'var _loc2_:Boolean = apexInfo.occultType == OccultTypes.OCCULT_FAIRY;')
