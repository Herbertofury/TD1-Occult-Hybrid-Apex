import enum
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core import phone_cas

class OutfitLabels(unittest.TestCase):
    def test_loaded_game_enum_supplies_names_without_importing_on_menu_path(self):
        class Category(enum.IntEnum):
            EVERYDAY=0
            HOT_WEATHER=7
        with patch.dict(sys.modules,{'sims.outfits.outfit_enums':SimpleNamespace(OutfitCategory=Category)}), \
                patch('builtins.__import__',side_effect=AssertionError('Menu labels must not import')):
            self.assertEqual(phone_cas._outfit_name(7),'Hot Weather')
            self.assertEqual(phone_cas._outfit_name(0),'Everyday')
            self.assertEqual(phone_cas._outfit_name(123),'Category 123')

    def test_unavailable_enum_keeps_category_identity_without_searching_disk(self):
        with patch.dict(sys.modules,{'sims.outfits.outfit_enums':None}), \
                patch('builtins.__import__',side_effect=AssertionError('Missing enum must not trigger imports')):
            self.assertEqual(phone_cas._outfit_name(71),'Category 71')

if __name__=='__main__':unittest.main()
