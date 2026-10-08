from pathlib import Path
import sys
import unittest
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from build_packages import migrate_xml


class PickerResourceTests(unittest.TestCase):
    def test_phone_root_keeps_original_continuations_and_uses_first_party_extension(self):
        raw = b'<I n="TD1:interactionPicker_OccultHybrid_Panel_Main" m="OccultHybrid.CoreLib.TD1_OccultHybrid_MenuUI" c="TD1OccultHybridMenuUIPicker"><L n="possible_actions"><T>16827766500387554810</T></L></I>'
        root = ElementTree.fromstring(migrate_xml(raw))
        self.assertEqual(root.get('m'), 'apex_core.phone_interactions')
        self.assertEqual(root.get('c'), 'ApexPhoneMenu')
        self.assertEqual(root.find('./L/T').text, '16827766500387554810')
    def test_module_dialog_and_icon_tuning_bind_to_the_ported_owner(self):
        raw = b'<M n="OccultHybrid.CoreLib.TD1_OccultHybrid_MenuUI"><C n="MenuUIBaseIcons"><V n="UI_ICON_PLACEHOLDER"/></C></M>'
        root = ElementTree.fromstring(migrate_xml(raw))
        self.assertEqual(root.get('n'), 'apex_hybrid.CoreLib.TD1_OccultHybrid_MenuUI')
        self.assertEqual(root.find('./C/V').get('n'), 'UI_ICON_MENU_PLACEHOLDER')

    def test_phone_picker_repairs_invalid_localization_and_species_without_losing_icons(self):
        raw = b'<I m="OccultHybrid.CoreLib.TD1_OccultHybrid_MenuUI"><L n="species"><E/></L><T n="enabled">0x0x9DAC5C26</T><T n="key">2f7d0004:00000000:AF1747D4DBBCC870</T></I>'
        root = ElementTree.fromstring(migrate_xml(raw))
        self.assertEqual(root.find('./L/E').text, 'HUMAN')
        self.assertEqual(root.find("./T[@n='enabled']").text, '0x9DAC5C26')
        self.assertEqual(root.find("./T[@n='key']").text, '2f7d0004:00000000:AF1747D4DBBCC870')
    def test_orphan_picker_repairs_impossible_tests_without_removing_age_restrictions(self):
        raw = b'''<I m="OccultHybrid.Modules.TD1_OccultHybrid_OccultPicker" c="TD1HybridOccultPickerSuperInteraction">
        <L n="test_globals"><V t="is_online"><U><T n="negate">False</T></U></V>
        <V t="sim_info"><U><L n="specified"><E>TEEN</E></L><L n="species"><E/></L></U></V>
        <V t="is_online"><U><T n="negate">True</T></U></V></L></I>'''
        result = ElementTree.fromstring(migrate_xml(raw))
        self.assertEqual(result.get('m'), 'apex_hybrid.Modules.TD1_OccultHybrid_OccultPicker')
        self.assertEqual(len(result.findall(".//V[@t='is_online']")), 0)
        self.assertEqual(result.find(".//L[@n='specified']/E").text, 'TEEN')
        self.assertEqual(result.find(".//L[@n='species']/E").text, 'HUMAN')

    def test_game_owned_tuning_without_a_custom_namespace_stays_byte_exact(self):
        raw = b'<I m="sims.occult.occult_interactions" c="OriginalGameClass" s="123"><T n="x">5</T></I>'
        self.assertEqual(migrate_xml(raw), raw)
