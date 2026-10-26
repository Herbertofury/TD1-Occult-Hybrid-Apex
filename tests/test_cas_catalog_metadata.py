import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import cas_ui


def client():
    catalogs = [{'panel': name, 'menu_state': state, 'supported': True, 'items': [],
                 'preset': None, 'preset_query': 'returned-null'} for name, state in cas_ui.PANELS.items()]
    catalogs[0]['items'] = [{'dataID': '414264', 'future_modifier': {'retained': True}}]
    return {'scope': 'native-cas-client', 'sim': {'simId': '12'}, 'menu_state': catalogs[0]['menu_state'],
            'panel_visible': True, 'outfit': {'outfit_type': 0, 'outfit_index': 0}, 'catalogs': catalogs}


def annotation():
    return {'data_id': '414264', 'query': 'returned-value', 'source': 'native:GetCatalogItem',
            'name': 'Actual localized skin detail', 'name_query': 'localized-title', 'name_source': 'native:LocKey',
            'native_image_uri': 'thumbs/cas/c_414264_l_f', 'image_query': 'native-uri',
            'image_source': 'native:GetCatalogItem.image', 'raw_json': '{"title":{"hash":123},"future_field":true}',
            'error': '', 'name_error': ''}


def annotated():
    result = client()
    result.update(catalog_metadata=[annotation()], catalog_metadata_complete=True,
                  catalog_metadata_scope='native-catalog-identities-only')
    return result


class CatalogMetadataTests(unittest.TestCase):
    def check(self, data):
        cas_ui.validate_client(data, '12', {'operation': 'status'})

    def test_optional_metadata_preserves_raw_equipped_and_history(self):
        old, new = client(), annotated()
        self.check(old)
        self.check(new)
        self.assertEqual(old['catalogs'], new['catalogs'])
        self.assertEqual(cas_ui.history_state(old), cas_ui.history_state(new))
        self.assertEqual(json.loads(new['catalog_metadata'][0]['raw_json'])['future_field'], True)

    def test_missing_or_failed_name_remains_explicit(self):
        data = annotated()
        data['catalog_metadata'][0].update(name=None, name_query='empty-title', native_image_uri=None,
                                         image_query='not-returned')
        self.check(data)
        data['catalog_metadata'][0].update(query='failed', name_query='unavailable', raw_json=None,
                                         error='Catalog getter unavailable')
        self.check(data)

    def test_other_equipped_identity_and_duplicate_refused(self):
        data = annotated()
        data['catalog_metadata'][0]['data_id'] = '414266'
        with self.assertRaisesRegex(ValueError, 'exact equipped identity'): self.check(data)
        data = annotated(); data['catalog_metadata'].append(copy.deepcopy(data['catalog_metadata'][0]))
        with self.assertRaisesRegex(ValueError, 'exact equipped identity'): self.check(data)

    def test_name_query_and_virtual_uri_cannot_claim_pixels(self):
        for field, value in [('name_query', 'resource-id'), ('name_source', 'inferred-id'),
                             ('image_query', 'decoded-pixels'), ('image_source', 'guessed-file')]:
            data = annotated(); data['catalog_metadata'][0][field] = value
            with self.assertRaises(ValueError): self.check(data)

    def test_unresolved_names_cannot_contain_substitute_text(self):
        data = annotated(); data['catalog_metadata'][0]['name_query'] = 'unavailable'
        with self.assertRaisesRegex(ValueError, 'masquerade'): self.check(data)
        data = annotated(); data['catalog_metadata'][0]['query'] = 'failed'
        with self.assertRaisesRegex(ValueError, 'genuine'): self.check(data)

    def test_metadata_is_bounded_and_complete_json(self):
        for raw in ('{', '[]', '{"value":NaN}', 'x' * 65537):
            data = annotated(); data['catalog_metadata'][0]['raw_json'] = raw
            with self.assertRaises(ValueError): self.check(data)
        data = annotated(); data['catalog_metadata'][0]['name'] = 'x' * 2049
        with self.assertRaises(ValueError): self.check(data)
        data = annotated(); data['catalog_metadata_complete'] = 'true'
        with self.assertRaisesRegex(ValueError, 'coverage'): self.check(data)
        data = annotated(); data['catalog_metadata'] *= 129
        with self.assertRaisesRegex(ValueError, 'coverage'): self.check(data)

    def test_noncanonical_or_numeric_native_catalog_id_refused(self):
        for identity in (414264, '0414264', '18446744073709551616'):
            data = annotated(); data['catalog_metadata'][0]['data_id'] = identity
            with self.assertRaises(ValueError): self.check(data)


if __name__ == '__main__': unittest.main()
