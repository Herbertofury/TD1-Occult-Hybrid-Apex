"""Owned CAS catalog additions. Donor layout facts, no bundled donor bytecode.

The supplied six-column package uses 111px column increments over EA's 262px
two-column panel. Apex applies that width to the native recycled grid in place.
The radial addition uses the game's existing renderer, not an overlay button.
"""
import re
from pathlib import Path

CONTEXT_KEY = (0x62ECC59A, 0, 0xCAEE355CE0B704F7)
CONTEXT_CLASS = 'widgets.CAS.controls.CASContextMenu'
CONTEXT_METHODS = ('UpdateMenu', 'HandleItemSelection')
PLAN_KEY = (0x62ECC59A, 0, 0x3E752EBCB41E7298)
PLAN_CLASS = 'widgets.CAS.PlanOutfit.CASPlanOutfitMain'
PLAN_PIN = '060ced2b95e5cc25aaba4b30f0b850d2b0ce992139c68311dc4110f510200f35'
DONOR_SHA256 = '7df4290426fdfeca458b873c7c38626c124b5756314467cc87146d215944c79e'


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Installed CAS catalog anchor differs: ' + old[:90])
    return source.replace(old, new, 1)


def inject_context(source):
    if 'ApexOpenEquippedCatalog' in source:
        raise ValueError('CAS context menu is already adapted.')
    source = re.sub(r'\s*\[Embed\([^\n]*\)\]', '', source)
    source = replace_once(source, '   import flash.display.DisplayObjectContainer;',
        '   import olympus.localization.LocKey;\n   import flash.display.DisplayObjectContainer;')
    anchor = 'this.dataProvider = new DataProvider(_loc9_);\n               this.SetupArc(this.ARC_MAIN);'
    added = '''_loc9_=_loc9_.concat();
               var apexEquipped:CASContextMenuItem=new CASContextMenuItem();
               apexEquipped.title=LocKey.UntranslatedString("All equipped CAS items");
               apexEquipped.icon=CASIcons.SHOW_ALL_CONSOLE;
               apexEquipped.icon_selected=CASIcons.SHOW_ALL_SELECTED_CONSOLE;
               apexEquipped.icon_gold=CASIcons.SHOW_ALL_SELECTED_CONSOLE;
               apexEquipped.component_name="ApexEquippedCatalog";
               apexEquipped.action="ApexEquippedCatalog";
               apexEquipped.sub_items=[];apexEquipped.disallow_remove=true;
               _loc9_.push(apexEquipped);
               ''' + anchor
    source = replace_once(source, anchor, added)
    anchor = 'var _loc6_:CASContextMenuItem = _loc2_.data as CASContextMenuItem;'
    source = replace_once(source, anchor, anchor + '''
         if(_loc6_!=null && _loc6_.action=="ApexEquippedCatalog") {
            CommunicationManager.CallUIService("ApexOpenEquippedCatalog",null);
            return;
         }''')
    return source


def inject_plan(source):
    """Reserve the current width in EA's separate outfit-header attachment.

    The optional detached coordinates come from the existing native binding
    event. Ordinary EA visibility messages retain their original behavior.
    No new fields, game service, appearance setter or exported art is needed.
    """
    source = re.sub(r'\s*\[Embed\([^\n]*\)\]', '', source)
    source = replace_once(source, '"clampX":{"max":LayoutAPI.StageWidth - param4}',
        '"clampX":{"max":LayoutAPI.StageWidth - Math.max(param4,this.mWidth + 12)}')
    anchor = '         if(_loc2_ == this.mAnimExtension.IsVisible())'
    added = '''         if(_loc2_ && typeof param1.apex_view_x_offset=="number" &&
            typeof param1.apex_screen_x_offset=="number" && typeof param1.apex_screen_x_max=="number" &&
            isFinite(param1.apex_view_x_offset) && isFinite(param1.apex_screen_x_offset) &&
            isFinite(param1.apex_screen_x_max) && this.mWidth>=262 && this.mWidth<=1372)
         {
            this.BindPanelToSim(this.m3dBindLayer,Number(param1.apex_view_x_offset),
               Number(param1.apex_screen_x_offset)+CASPlanOutfitTunables.PANEL_SCREEN_OFFSET_X,
               Number(param1.apex_screen_x_max)+CASPlanOutfitTunables.PANEL_SCREEN_OFFSET_X*0.5);
         }
''' + anchor
    return replace_once(source, anchor, added)


def equipped_menus():
    """Known installed body-type routes; unknown future types remain visible."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
    from apex_core.cas_panels import PANELS
    routes = {1:'clothing_accessories_hats',2:'clothing_hair',3:'profile_head_whole_heads',
        4:'profile_head_whole_heads',5:'clothing_fullbody',6:'clothing_tops',7:'clothing_bottoms',
        8:'clothing_shoes',9:'clothing_accessories_body',10:'clothing_accessories_earrings',
        11:'clothing_accessories_glasses',12:'clothing_accessories_necklaces',13:'clothing_accessories_gloves',
        14:'clothing_accessories_bracelets',15:'clothing_accessories_bracelets',28:'clothing_face_facial_hair',
        29:'clothing_face_makeup_lips',30:'clothing_face_makeup_eyes',31:'clothing_face_makeup_eyeliner',
        32:'clothing_face_makeup_cheeks',33:'clothing_face_makeup_paint',34:'profile_hair_eyebrows',
        35:'profile_head_eyes',36:'clothing_accessories_socks',37:'clothing_face_makeup_eyelashes'}
    for body in range(16,22): routes[body]='clothing_accessories_piercings'
    for body in range(22,28): routes[body]='clothing_accessories_rings'
    for body in (*range(38,42),43,44,*range(55,59)): routes[body]='clothing_head_skin_details'
    for body in range(45,55): routes[body]='clothing_body_tattoos'
    routes.update({42:'clothing_accessories_tights',59:'profile_body_fur',60:'profile_head_ears',
        61:'clothing_pet_tail',62:'clothing_head_skin_details',63:'profile_head_eyes',
        64:'vampire_brows',65:'vampire_eyesockets',66:'vampire_eyebags',67:'vampire_mouth',
        68:'vampire_cheeks',69:'vampire_cheeks',70:'clothing_head_skin_details',71:'clothing_bodyscar',
        72:'clothing_head_skin_details',73:'clothing_accessories_fingernail',74:'clothing_accessories_toenail',
        75:'clothing_hair',76:'clothing_head_skin_details',77:'clothing_body_skin_details',
        78:'clothing_body_bodyhair_arm',79:'clothing_body_bodyhair_leg',80:'clothing_body_bodyhair_torsofront',
        81:'clothing_body_bodyhair_torsoback',88:'clothing_accessories_body',89:'clothing_head_skin_details',
        90:'clothing_bodyscar',91:'clothing_head_skin_details',95:'clothing_head_skin_details',
        101:'clothing_saddle',102:'clothing_bridle',103:'clothing_bridle',104:'clothing_blanket',105:'clothing_body_hoofcolor',
        106:'clothing_hair_mane',107:'clothing_hair_horse_tail',108:'clothing_hair_forelock',109:'clothing_hair_horse_feather',
        110:'clothing_accessories_horn',111:'clothing_pet_tail',112:'clothing_body_skin_details',113:'clothing_head_tattoos',
        114:'clothing_body_wings',115:'clothing_accessories_headdeco',116:'clothing_body_skinspecularity',117:'clothing_accessories_base_layer'})
    for body in range(82,88):routes[body]='clothing_bodyscar'
    for body in (92,93,94,96,97,98,99,100):routes[body]='clothing_body_skin_details'
    return {str(body):PANELS[panel] for body,panel in routes.items()}


def viewport_layout(columns, stage_width):
    """Reference for the owned AS viewport rule, in logical stage units."""
    import math
    if type(columns) is not int or not 2 <= columns <= 12 or not math.isfinite(stage_width) or stage_width < 640:
        raise ValueError('Use bounded columns and a supported viewport.')
    actual=min(columns,max(2,min(12,int((stage_width*.53-40)/111))))
    return {'requested':columns,'columns':actual,'width':262+(actual-2)*111}


def native_catalog_clamp(columns,stage_width,original_maximum):
    """Preserve EA's attachment; reserve enough width at its native max clamp."""
    import math
    if not math.isfinite(original_maximum) or not 0<=original_maximum<=stage_width:
        raise ValueError('Native context-menu clamp is unavailable.')
    layout=viewport_layout(columns,stage_width)
    return stage_width-max(original_maximum,layout['width']+12)
