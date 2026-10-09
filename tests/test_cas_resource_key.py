"""Native resource-key identity is obtained, never reconstructed from a part ID."""
from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import cas_catalog
from casp_fixture import casp
import test_studio


class ResourceKeyTests(unittest.TestCase):
    def resources(self, native_key):
        resources = Obj(Types=Obj(CASPART=0x034AEECB),
                        get_resource_key=Mock(return_value=native_key),
                        ResourceLoader=Mock(return_value=Obj(load_raw=Mock(return_value=casp(body=7)))))
        return resources, patch.dict(sys.modules, {'sims4': Obj(resources=resources)})

    def test_actual_nonzero_native_group_and_instance_are_preserved(self):
        instance = 0xABCD123456789012
        native_key = Obj(type=0x034AEECB, group=0xFEDCBA98, instance=instance)
        resources, modules = self.resources(native_key)
        with modules:
            metadata = cas_catalog.effective_metadata(Obj(), instance)
        self.assertEqual(metadata['resource_tgi'], '034AEECB:FEDCBA98:ABCD123456789012')
        self.assertEqual(metadata['resource_key_query'], 'native-key')
        resources.get_resource_key.assert_called_once_with(instance, resources.Types.CASPART)
        resources.ResourceLoader.assert_called_once_with(native_key)
        self.assertEqual(metadata['resource_sha256'], cas_catalog.slider_metadata(casp(body=7))['resource_sha256'])

    def test_fixture_bytes_have_no_invented_native_group(self):
        metadata = cas_catalog.effective_metadata(Obj(_studio_casp_bytes=lambda _: casp()), 999)
        self.assertIsNone(metadata['resource_tgi'])
        self.assertEqual(metadata['resource_key_query'], 'unavailable')

    def test_untyped_missing_or_mismatched_native_identity_refuses_before_loading(self):
        baseline = {'type': 0x034AEECB, 'group': 0, 'instance': 999}
        mutations = [('type', True), ('group', False), ('instance', True),
                     ('type', '034AEECB'), ('group', '0'), ('instance', '999'),
                     ('group', None), ('group', -1), ('group', 2**32),
                     ('type', 1), ('instance', 998), ('instance', 2**64)]
        for field, value in mutations:
            with self.subTest(field=field, value=value):
                attributes = dict(baseline, **{field: value})
                resources, modules = self.resources(Obj(**attributes))
                with modules, self.assertRaisesRegex(ValueError, 'native CASP resource key'):
                    cas_catalog.effective_metadata(Obj(), 999)
                resources.ResourceLoader.assert_not_called()
        resources, modules = self.resources(Obj(type=0x034AEECB, instance=999))
        with modules, self.assertRaises(ValueError):
            cas_catalog.effective_metadata(Obj(), 999)
        resources.ResourceLoader.assert_not_called()

    def test_part_instance_has_precise_unsigned_integer_type(self):
        provider = Mock(return_value=casp())
        for value in (True, False, 0, -1, 2**64, '999', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                cas_catalog.effective_metadata(Obj(_studio_casp_bytes=provider), value)
        provider.assert_not_called()

    def test_part_and_color_editors_expose_actual_native_key_with_same_effective_hash(self):
        fixture = test_studio.StudioTests('runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        resources, modules = self.resources(Obj(type=0x034AEECB, group=0x123, instance=999))
        with modules:
            part = fixture.request('studio_part_inspect', '0:7:0')['part_editor']
            color = fixture.request('studio_color_inspect', '0:7:0')['color_editor']
        for editor in (part, color):
            self.assertEqual(editor['resource_tgi'], '034AEECB:00000123:00000000000003E7')
            self.assertEqual(editor['resource_key_query'], 'native-key')
        self.assertEqual(part['resource_sha256'], color['resource_sha256'])


if __name__ == '__main__':
    unittest.main()
