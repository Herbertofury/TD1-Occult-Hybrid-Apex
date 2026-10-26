"""Exercise the pinned UI patch against the privately installed class sources."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import cas_molecule_patch as patch


class MoleculePatchTests(unittest.TestCase):
    def source(self, target):
        p=ROOT/'.work/research/cas-hair-casmolecule-current/scripts'/(target.replace('.', '/')+'.as')
        if not p.is_file(): self.skipTest('Requires the privately decompiled installed CAS molecule.')
        return p.read_text(encoding='utf-8')

    def test_icon_queries_the_selected_genus_instead_of_a_combined_membership_mask(self):
        s=patch.inject(self.source(patch.ICON_CLASS),patch.ICON_CLASS)
        self.assertIn('CallGameService("GetSimOccult")',s)
        self.assertNotIn('GetRealOccultType(param1.allOccultTypes)',s)
        self.assertIn('HUMAN_ICON',s)

    def test_click_highlight_follows_actual_native_form_instead_of_unacknowledged_choice(self):
        s=patch.inject(self.source(patch.PANEL_CLASS),patch.PANEL_CLASS)
        self.assertIn('import olympus.io.CommunicationManager;',s)
        self.assertIn('ApexMoleculeReadSelection',s)
        self.assertLess(s.index('dispatchEvent(_loc3_)'),s.index('ApexMoleculeReadSelection'))
        self.assertIn('apexSelected.kind==1 ? null : String(apexSelected.kind)',s)
        self.assertIn('else this.SelectionDataAsOccult.SelectOccult(_loc2_.occult_type.toString())',s)

    def test_existing_household_full_edit_restores_the_native_panel(self):
        s=patch.inject(self.source(patch.MOLECULE_CLASS),patch.MOLECULE_CLASS)
        self.assertEqual(s.count('CasIsForcedFullEditingEnabled'),5)
        self.assertIn('Boolean(TutorialMode.IsFTUE())',s)
        self.assertIn('WaitingForSimReveal',s)
        self.assertIn('this.mcTraitSelector.OccultPanelId',s)
        self.assertIn('apexButton.visible=!this.mcTraitSelector.mcTraitsMolecule.WaitingForSimReveal',s)
        self.assertIn('ApexMoleculeObserved',s)

    def test_later_redraws_use_the_bound_genus_without_rewriting_sim_membership(self):
        s=patch.inject(self.source(patch.MOLECULE_CLASS),patch.MOLECULE_CLASS)
        self.assertIn('_loc2_.allOccultTypes = Boolean(CommunicationManager.CallGameService("CasIsForcedFullEditingEnabled")) ? int(CommunicationManager.CallGameService("GetSimOccult")) : param1.allOccultTypes;',s)
        self.assertNotIn('param1.allOccultTypes =',s)
        self.assertIn('this.mSimInfo = param1;',s)
        self.assertIn('this.mOccultSelectionData.SetupDataFeed(param1);',s)

    def test_hybrid_routing_precedes_the_stock_conversion_and_ghost_warning(self):
        s=patch.inject(self.source(patch.MOLECULE_CLASS),patch.MOLECULE_CLASS)
        section=s.split('protected function OnOccultSelected(',1)[1]
        self.assertLess(section.index('ApexMoleculeChooseOccult'),section.index('CAS_GHOST_OCCULT_WARNING'))
        self.assertIn('sim_id:this.mSimInfo.simId,kind:int(param1.mOccultType)',section)
        self.assertIn('CallGameService("SetSimOccult",param1.occult)',section)

    def test_missing_or_duplicate_native_anchors_refuse_the_build(self):
        for old in ('', 'missing', 'twice twice'):
            with self.assertRaises(ValueError): patch.replace_once(old,'twice','changed')

    def test_second_application_and_unknown_class_refuse(self):
        for target in patch.METHODS:
            first=patch.inject(self.source(target),target)
            with self.assertRaises(ValueError):patch.inject(first,target)
        with self.assertRaises(ValueError):patch.inject('class Unknown {}','Unknown')

    def test_plain_tooltip_uses_the_native_object_property_not_the_lockey_method(self):
        api=ROOT/'.work/research/color-ui/library-scripts/scripts/olympus/extensions/TooltipExtension.as'
        if not api.is_file():self.skipTest('Requires the privately inspected native tooltip API.')
        contract=api.read_text(encoding='utf-8')
        self.assertIn('function set Text(param1:Object)',contract)
        self.assertIn('function SetText(param1:LocKey',contract)
        source=patch.inject(self.source(patch.MOLECULE_CLASS),patch.MOLECULE_CLASS)
        self.assertIn('apexButton.TooltipExt.Text=',source)
        self.assertNotIn('apexButton.TooltipExt.SetText(',source)


if __name__ == '__main__':unittest.main()
