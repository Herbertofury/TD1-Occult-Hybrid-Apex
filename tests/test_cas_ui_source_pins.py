import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import cas_ui_build


class SourcePinsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for index, name in enumerate(cas_ui_build.PINNED_SOURCES):
            raw = b'owned\r\nmethods' if index == 0 else b'owned\npatcher'
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)

    def test_exact_source_bytes_match_manifest_after_serialization(self):
        pins = cas_ui_build.source_pins(self.root)
        self.assertEqual(pins[cas_ui_build.PINNED_SOURCES[0]], hashlib.sha256(b'owned\r\nmethods').hexdigest())
        info = json.loads(json.dumps({'source_pins': pins}))
        self.assertTrue(cas_ui_build.verify_source_pins(info, self.root))

    def test_rebuilt_package_is_required_after_either_input_changes(self):
        for name in cas_ui_build.PINNED_SOURCES:
            info = {'source_pins': cas_ui_build.source_pins(self.root)}
            path = self.root / name
            path.write_bytes(path.read_bytes() + b'\nnew logic')
            with self.assertRaisesRegex(ValueError, 'source pins differ'):
                cas_ui_build.verify_source_pins(info, self.root)

    def test_no_missing_partial_or_foreign_source_contract(self):
        pins = cas_ui_build.source_pins(self.root)
        for info in ({}, {'source_pins': None}, {'source_pins': {}},
                     {'source_pins': {cas_ui_build.PINNED_SOURCES[0]: pins[cas_ui_build.PINNED_SOURCES[0]]}},
                     {'source_pins': dict(pins, other_file='a' * 64)}):
            with self.assertRaisesRegex(ValueError, 'source pins differ'):
                cas_ui_build.verify_source_pins(info, self.root)

    def test_exact_compiler_line_endings_do_not_share_a_pin(self):
        info = {'source_pins': cas_ui_build.source_pins(self.root)}
        (self.root / cas_ui_build.PINNED_SOURCES[0]).write_bytes(b'owned\nmethods')
        with self.assertRaisesRegex(ValueError, 'source pins differ'):
            cas_ui_build.verify_source_pins(info, self.root)

    def test_household_names_and_validation_cannot_be_skipped_or_follow_the_native_save(self):
        methods = (Path(__file__).resolve().parents[1] / 'Source/CASUi/semantic_methods.as').read_text(encoding='utf-8')
        self.assertTrue(cas_ui_build.verify_household_acceptance(methods))
        names = 'CallUIService("CasApplyNameFields",false)'
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            cas_ui_build.verify_household_acceptance(methods.replace(names, 'CallUIService("SkippedNames",false)'))
        save = 'CallGameService("SaveAndExitCAS",{bValidateExistingSimTraits:false})'
        swapped = methods.replace(names, '__SWAP__').replace(save, names).replace('__SWAP__', save)
        with self.assertRaisesRegex(ValueError, 'precede'):
            cas_ui_build.verify_household_acceptance(swapped)

    def test_household_native_class_is_imported_as_a_compiler_qname(self):
        native = '   import olympus.io.CommunicationManager;\n   class Fixture {\n      AddMessageListener("CASContextMenuSetMenuState",this.HandleContextMenuSetMenuState);\n   }'
        patched = cas_ui_build.inject(native, 'private function Owned() : void {}')
        self.assertIn('import gamedata.Exchange.ExchangeData;', patched)


if __name__ == '__main__':
    unittest.main()
