"""Owned CAS catalog additions. Donor layout facts, no bundled donor bytecode.

The supplied six-column package uses 111px column increments over EA's 262px
two-column panel. Apex applies that width to the native recycled grid in place.
The radial addition uses the game's existing renderer, not an overlay button.
"""
import re
from pathlib import Path

CONTEXT_KEY = (0x62ECC59A, 0, 0xCAEE355CE0B704F7)
CONTEXT_CLASS = 'widgets.CAS.controls.CASContextMenu'
CONTEXT_METHODS = ('UpdateMenu', 'HandleItemSelection', 'Refresh')
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
        '   import flash.utils.describeType;\n   import olympus.localization.LocKey;\n   import flash.display.DisplayObjectContainer;')
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
    # The physical alternate may be a Vampire backing slot. The radial menu
    # already holds the exact selected owner's display kind; asking for fresh
    # SimInfo here selects pelt painting for Fairy wings.
    source = replace_once(source,
        '_loc9_ = CASStateData.GetCurrentSimInfo(true).occultType == OccultTypes.OCCULT_FAIRY;',
        '''var apexPaintOwner:Object=CommunicationManager.CallUIService("ApexFormPairPanel",{operation:"status",sim_id:this.mCurrSimId});
               _loc9_ = apexPaintOwner!=null && apexPaintOwner.enabled===true && apexPaintOwner.native_kind is int ?
                  int(apexPaintOwner.native_kind)==OccultTypes.OCCULT_FAIRY : this.mCurrOccultType==OccultTypes.OCCULT_FAIRY;''')
    source = replace_once(source, 'public function Refresh(param1:SimInfo) : void\n      {',
        '''public function Refresh(param1:SimInfo) : void
      {
         // A display-only copy follows the actual bound owner even when EA
         // refreshes this radial from the physical alternate backing slot.
         var apexOwner:Object=CommunicationManager.CallUIService("ApexFormPairPanel",{operation:"status",sim_id:String(param1.simId)});
         if(apexOwner!=null && apexOwner.enabled===true && apexOwner.native_kind is int &&
            [1,2,4,8,16,32,64].indexOf(int(apexOwner.native_kind))>=0) {
            // SimInfo's public slots are sealed, not for-in enumerable.
            // OlympusObject.ParseObject expects an ordinary detached object.
            var apexInfo:Object={};var apexDefinition:XML=describeType(param1);
            for each(var apexSlot:XML in apexDefinition.variable) {
               var apexName:String=String(apexSlot.@name);apexInfo[apexName]=param1[apexName];
            }
            param1=new SimInfo(apexInfo);param1.occultType=int(apexOwner.native_kind);
            // Menu capabilities only. The Human/CC owner still binds Human
            // geometry; canine presets and fur are additional catalogue items.
            if(apexOwner.selected_owner_id==="werewolf/werewolf_human_cc") param1.occultType=32;
            param1.occultLayer=apexOwner.selected_owner_id===apexOwner.base_owner_id?0:1;
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
            isFinite(param1.apex_screen_x_max) && this.mWidth>=262 && this.mWidth<=LayoutAPI.StageWidth-12)
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
    """Default compact card fit, preserving the chosen count by scaling tiles."""
    layout=card_layout(columns,stage_width,1,4,4,base_width=107)
    return {'requested':columns,'columns':layout['columns'],'width':layout['width']}


def native_catalog_clamp(columns,stage_width,original_maximum):
    """Preserve EA's attachment; reserve enough width at its native max clamp."""
    import math
    if not math.isfinite(original_maximum) or not 0<=original_maximum<=stage_width:
        raise ValueError('Native context-menu clamp is unavailable.')
    layout=viewport_layout(columns,stage_width)
    return stage_width-max(original_maximum,layout['width']+12)


def card_layout(columns,stage_width,scale,gap_x,gap_y,base_width=107,base_height=148,*,ui_scale=1,native_stage_width=None):
    """Independent geometry oracle for fitted, proportional native tiles."""
    import math
    if (type(columns) is not int or not 2<=columns<=32 or
            any(type(v) not in (int,float) or not math.isfinite(v) for v in
                (stage_width,scale,gap_x,gap_y,base_width,base_height)) or
            stage_width<640 or not .2<=scale<=1.6 or not 0<=gap_x<=32 or not 0<=gap_y<=32 or
            base_width<=0 or base_height<=0):
        raise ValueError('Use bounded cards and the actual native tile dimensions.')
    # Match the native attachment's reserved catalogue region. More columns
    # fit smaller cards here; they must never grow left across the Sim.
    if (type(ui_scale) not in (int,float) or not math.isfinite(ui_scale) or ui_scale<=0 or
            native_stage_width is not None and (type(native_stage_width) not in (int,float) or
                not math.isfinite(native_stage_width) or native_stage_width<=0)):
        raise ValueError('Native catalogue viewport unavailable.')
    logical_width=min(stage_width if native_stage_width is None else native_stage_width,stage_width/ui_scale)
    available=max(80,min(40+6*(base_width+4),logical_width*.40-12))
    content=available-40
    actual_gap_x=min(gap_x,content/(columns*2))
    actual_scale=min(scale,(content-columns*actual_gap_x)/(columns*base_width))
    pitch=base_width*actual_scale+actual_gap_x
    return dict(scale=actual_scale,gap_x=actual_gap_x,gap_y=gap_y,card_width=base_width*actual_scale,
        card_height=base_height*actual_scale,pitch_x=pitch,pitch_y=base_height*actual_scale+gap_y,
        columns=columns,width=max(min(262,available),40+columns*pitch),requested_columns=columns,requested_scale=scale,requested_gap_x=gap_x,
        available_width=available,columns_fit=True,size_fitted=actual_scale<scale-1e-6,gap_x_fitted=actual_gap_x<gap_x-1e-6)
