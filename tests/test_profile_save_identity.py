import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as Obj
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import profile_save_identity


class PlayerSaveIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.profile = Path(self.temp.name) / 'The Sims 4'
        self.archive = self.profile / 'Mods/Apex/ApexOccultHybrid.ts4script'
        self.archive.parent.mkdir(parents=True); self.archive.write_bytes(b'fixture installed script')
        self.data = self.profile / 'TD1_OccultHybridApexData'
        self.backend = Obj(__file__=str(self.archive / 'td1_occult_hybrid_apex.py'), _data_directory=lambda: str(self.data))

    def test_unmarked_player_profile_has_stable_local_identity_without_enabling_test_controls(self):
        first = profile_save_identity.player(self.backend)
        second = profile_save_identity.player(self.backend)
        self.assertEqual(first, second); self.assertEqual(first['identity_kind'], 'player-appearance-save')
        self.assertFalse((self.profile / '.apex-disposable-profile.json').exists())
        self.assertEqual(len(first['test_token']), 32)

    def test_existing_malformed_identity_is_retained_and_refused(self):
        self.data.mkdir(); path = self.data / 'profile_save_identity.json'
        for value in ('[]', '{', '{"schema":1,"token":"bad"}'):
            path.write_text(value)
            with self.assertRaises((ValueError, TypeError)): profile_save_identity.player(self.backend)
            self.assertEqual(path.read_text(), value)

    def test_marked_profile_cannot_fall_back_to_player_identity(self):
        (self.profile / '.apex-disposable-profile.json').write_text('{"disposable":false}')
        with self.assertRaisesRegex(ValueError, 'exact disposable'): profile_save_identity.player(self.backend)
        self.assertFalse(self.data.exists())

    def test_mismatched_data_folder_or_protected_profile_never_receives_a_write(self):
        self.backend._data_directory = lambda: str(self.profile / 'foreign-data')
        with self.assertRaisesRegex(ValueError, 'actual installed profile'): profile_save_identity.player(self.backend)
        self.assertFalse(self.data.exists())
        self.backend.__file__ = str(self.profile.with_name('The Sims 4 DO NOT TOUCH') / 'Mods/Apex/ApexOccultHybrid.ts4script/td1_occult_hybrid_apex.py')
        with self.assertRaises(ValueError): profile_save_identity.player(self.backend)
        self.assertFalse(self.profile.with_name('The Sims 4 DO NOT TOUCH').exists())
