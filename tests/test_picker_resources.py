from pathlib import Path
import sys
import unittest
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from build_packages import migrate_xml


class PickerResourceTests(unittest.TestCase):
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
