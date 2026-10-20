"""Narrow edits to the owner's pinned, privately decompiled CAS molecule.

No EA source is shipped. Build-time anchors fail when the installed UI changes.
The ABC adapter retains every native method outside this explicit inventory.
"""
import re

ICON_CLASS = 'widgets.TraitsMolecule.OccultSelectionButton'
MOLECULE_CLASS = 'widgets.CAS.Molecule.EquippedTraitsAsp'
PANEL_CLASS = 'widgets.TraitsMolecule.OccultSelectionPanel'
METHODS = {ICON_CLASS: ('UpdateIconDisplay',),
           MOLECULE_CLASS: ('SetSimInfo', 'OnOccultClick', 'OnOccultSelected'),
           PANEL_CLASS: ('OnItemClick',)}


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Installed CAS molecule anchor differs: '+old[:85])
    return source.replace(old, new, 1)


def inject(source, target):
    if 'ApexMolecule' in source:
        raise ValueError('CAS molecule source is already patched.')
    source = re.sub(r'\s*\[Embed\([^\n]*\)\]', '', source)
    full = 'Boolean(CommunicationManager.CallGameService("CasIsForcedFullEditingEnabled"))'
    if target == ICON_CLASS:
        # GetRealOccultType removes Human, but leaves a multi-occult mask.
        # GetOccultIcon expects ONE genus and otherwise hides the whole button.
        source = replace_once(source, 'int(OccultTypes.GetRealOccultType(param1.allOccultTypes))',
            '(int(CommunicationManager.CallGameService("GetSimOccult")) & ~OccultTypes.OCCULT_HUMAN)')
    elif target == PANEL_CLASS:
        source = replace_once(source, '   import gamedata.shared.OccultTypes;',
            '   import olympus.io.CommunicationManager;\n   import gamedata.shared.OccultTypes;')
        source = replace_once(source,
            'this.SelectionDataAsOccult.SelectOccult(_loc2_.occult_type.toString());',
            'var apexSelected:Object=CommunicationManager.CallUIService("ApexMoleculeReadSelection",null);\n'
            '         if(apexSelected && apexSelected.protocol===1)\n'
            '            this.SelectionDataAsOccult.SelectOccult(apexSelected.kind==1 ? null : String(apexSelected.kind));\n'
            '         else this.SelectionDataAsOccult.SelectOccult(_loc2_.occult_type.toString());')
    elif target == MOLECULE_CLASS:
        # HouseholdSimData is the molecule's presentation model. Later native
        # redraws reuse it after SetSimInfo returns, so fixing button.visible
        # once cannot prevent UpdateIconDisplay hiding a combined mask again.
        # Keep the complete membership on SimInfo; give only this icon/trait
        # molecule model the actual bound genus in full-edit mode.
        source = replace_once(source, '_loc2_.allOccultTypes = param1.allOccultTypes;',
            '_loc2_.allOccultTypes = '+full+' ? int(CommunicationManager.CallGameService("GetSimOccult")) : param1.allOccultTypes;')
        source = replace_once(source, 'ReadOnly = !param1.SimIsNew || Boolean(TutorialMode.IsFTUE());',
            'ReadOnly = !(param1.SimIsNew || '+full+') || Boolean(TutorialMode.IsFTUE());')
        source = replace_once(source, 'if(!this.mSimInfo.SimIsNew || this.mcTraitSelector.mcTraitsMolecule.WaitingForSimReveal)',
            'if((!this.mSimInfo.SimIsNew && !'+full+') || this.mcTraitSelector.mcTraitsMolecule.WaitingForSimReveal)')
        source = replace_once(source,
            'var _loc6_:Boolean = Boolean(this.mSimInfo.IsOccultAlternateForm()) || Boolean(this.mSimInfo.isRobot);',
            'var _loc6_:Boolean = (Boolean(this.mSimInfo.IsOccultAlternateForm()) || Boolean(this.mSimInfo.isRobot)) && !'+full+';')
        anchor = 'protected function OnOccultSelected(param1:TraitSelectorOccultEvent) : void\n      {'
        source = replace_once(source, anchor, anchor+'\n'
            '         if(Boolean(CommunicationManager.CallUIService("ApexMoleculeChooseOccult",\n'
            '            {sim_id:this.mSimInfo.simId,kind:int(param1.mOccultType)}))) return;')
        # Shared TraitsMolecule classes can already be linked from another UI
        # library. Restore this widget AFTER DrawSimMolecule's own visibility
        # calculation instead of relying on a duplicate shared icon class.
        anchor = 'this.mcTraitSelector.mcTraitsMolecule.btnPreferences.SetMaskVisibility(true);\n         }\n      }'
        source = replace_once(source, anchor,
            'this.mcTraitSelector.mcTraitsMolecule.btnPreferences.SetMaskVisibility(true);\n         }\n'
            '         var apexButton:Object=this.mcTraitSelector.mcTraitsMolecule.mcSpeciesDisplay;\n'
            '         var apexKind:int=int(CommunicationManager.CallGameService("GetSimOccult"));\n'
            '         this.mOccultSelectionData.SelectOccult(apexKind==1 ? null : String(apexKind));\n'
            '         if('+full+' && !TutorialMode.IsFTUE() && param1.speciesType==1 && this.mOccultSelectionData.length>0) {\n'
            '            apexButton.visible=!this.mcTraitSelector.mcTraitsMolecule.WaitingForSimReveal;\n'
            '            apexButton.enabled=true;apexButton.mCurrOccult=apexKind & ~OccultTypes.OCCULT_HUMAN;\n'
            '            var apexIcon:Object=CommunicationManager.CallGameService("GetOccultIcon",apexKind);\n'
            '            var apexImage:String=apexKind==1 ? "0x785ddfe321bcae11" :\n'
            '               (apexIcon && apexIcon.icon ? String(apexIcon.icon.instance) : "");\n'
            '            if(apexImage!="") apexButton.mcThumbnail.LoadImage(apexImage);\n'
            '            apexButton.TooltipExt.Text="Switch occult appearance. Other occult forms and their edits are retained.";\n'
            '         }\n'
            '         var apexBounds:Object=apexButton.getBounds(stage);\n'
            '         CommunicationManager.SendUIMessage("ApexMoleculeObserved",{sim_id:param1.simId,\n'
            '            kind:apexKind,visible:Boolean(apexButton.visible),enabled:Boolean(apexButton.enabled),\n'
            '            occult_count:int(this.mOccultSelectionData.length),x:Number(apexBounds.x),y:Number(apexBounds.y),\n'
            '            width:Number(apexBounds.width),height:Number(apexBounds.height)});\n'
            '      }')
    else:
        raise ValueError('Unsupported CAS molecule class.')
    return source
