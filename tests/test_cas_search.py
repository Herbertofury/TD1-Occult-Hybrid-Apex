"""Player searches are read-only, typo tolerant and isolated by all filters."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from cas_search import Vocabulary, one_typo, aliases
import test_live_cas_catalog as fixtures
import cas_resource_catalog as resources
import live_cas_catalog as catalog
from casp_fixture import casp


class TypoPlannerTests(unittest.TestCase):
    def test_typical_filename_typos_and_unicode(self):
        words = Vocabulary(['eyebrows', 'necklace', 'élégance', 'creator', 'short', 'shirt'])
        for typed, actual in [('eyeborws', 'eyebrows'), ('neckace', 'necklace'),
                              ('necklce', 'necklace'), ('neclace', 'necklace'),
                              ('xreator', 'creator'), ('élégacne', 'élégance')]:
            self.assertTrue(any(actual.startswith(value) for value in words.alternatives(typed)),typed)
        self.assertEqual(words.alternatives('neck'), [])
        self.assertFalse(one_typo('shirt', 'shorts'))
        self.assertFalse(one_typo('aaa', 'bbb'))
        self.assertEqual(words.plan('ＥＹＥＢＯＲＷＳ')[1][0]['suggestions'], ['eyebrows'])
        self.assertIn('eyebrow', words.alternatives('eyeborw'))

    def test_fts_operators_remain_terms_and_plan_cache_is_bounded(self):
        words = Vocabulary(['eyebrows', 'necklace'])
        expression, _ = words.plan('"eyeborws" OR necklace*')
        self.assertEqual(expression, '("eyeborws"* OR "eyebrows"*) AND ("or"*) AND ("necklace"*)')
        for number in range(300):
            words.plan('query' + str(number))
        self.assertEqual(len(words.plans), 256)

    def test_camel_case_names_keep_source_spelling_and_get_searchable_words(self):
        self.assertEqual(aliases('yfHair_SDXLightBrown'), 'brown hair light sdx yf')


class SearchIntegrationTests(unittest.TestCase):
    setUp = fixtures.LiveCatalogTests.setUp
    package = fixtures.LiveCatalogTests.package
    build = fixtures.LiveCatalogTests.build

    def test_internal_name_words_are_searchable_without_package_name_matches(self):
        self.package('Completely unrelated.package', {(resources.CASP, 8, 91): casp(body=34, name='yuMakeupEyebrows_SDXLightBrown')})
        built = self.build(); index = catalog.PinnedIndex(self.index, built['index_sha256'])
        self.addCleanup(index.close)
        exact = index.query(text='eyebrows light', fuzzy=True)
        self.assertEqual((exact['total'], exact['search_mode']), (1, 'prefix'))
        self.assertEqual(exact['items'][0]['code_name'], 'yuMakeupEyebrows_SDXLightBrown')
        typo = index.query(text='eyeborws light', fuzzy=True)
        self.assertEqual((typo['total'], typo['search_mode']), (1, 'fuzzy'))
    def test_fuzzy_author_type_and_cached_pages_remain_exact(self):
        self.package('[Alice] Eyebrows.package', {(resources.CASP, 8, 91): casp(body=34)})
        self.package('[Bob] Eyebrows.package', {(resources.CASP, 8, 92): casp(body=34)})
        self.package('[Alice] Necklace.package', {(resources.CASP, 8, 93): casp(body=18)})
        built = self.build(); index = catalog.PinnedIndex(self.index, built['index_sha256'])
        self.addCleanup(index.close)
        query = dict(text='eyeborws', author='Alice', body_type=34, fuzzy=True, grouped=True)
        # The pinned lease already verified the index. No package scan, hash,
        # JSON source parsing or game contact is allowed during a query.
        with patch.object(catalog, 'file_hash', side_effect=AssertionError('query full-file hash')) if catalog.os.name == 'nt' else patch.object(catalog, 'Package', side_effect=AssertionError('query package scan')):
            page = index.query(**query)
            self.assertEqual((page['total'], page['search_mode'], page['cache_hit']), (1, 'fuzzy', False))
            self.assertEqual(page['items'][0]['creator_hint'], 'Alice')
            self.assertFalse(page['items'][0]['creator_verified'])
            self.assertFalse(page['items'][0]['equip_verified'])
            original = page['items'][0]['package_path']; page['items'][0].pop('package_path')
            cached = index.query(**query)
            self.assertTrue(cached['cache_hit'])
            self.assertEqual(cached['items'][0]['package_path'], original)
            self.assertEqual(index.query(**dict(query, author='Bob'))['items'][0]['creator_hint'], 'Bob')
            self.assertEqual(index.query(**dict(query, body_type=18))['total'], 0)
            self.assertEqual(index.query(**dict(query, fuzzy=False))['total'], 0)
            self.assertEqual(index.query(**dict(query, part_ids=[]))['total'], 0)
        with self.assertRaises(ValueError):
            index.query(fuzzy='yes')


if __name__ == '__main__':
    unittest.main()
