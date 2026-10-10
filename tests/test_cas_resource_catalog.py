"""Synthetic package/image fixtures; tests never launch Studio or touch a game."""
import http.client
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import cas_resource_catalog as catalog
import dbpf_build
from casp_fixture import casp


PART = (catalog.CASP, 0xABCDEF01, 0x123456789ABCDEFF)
THUMB = (catalog.CAS_THUMB, 2, PART[2])


def part(body=35, title=0):
    data = bytearray(casp(body=body))
    # Synthetic fixture has two six-byte tags; title follows price.
    marker = struct.pack('<IIIIBIIII', 0, 0, 0, 0, 0, body, 0, 0, 1)
    offset = data.index(marker)
    struct.pack_into('<I', data, offset + 4, title)
    return bytes(data)


def strings(values):
    payload = bytearray()
    for ident, value in values.items():
        encoded = value.encode('utf-8')
        payload += struct.pack('<IBH', ident, 0, len(encoded)) + encoded
    return b'STBL' + struct.pack('<HBQHI', 5, 0, len(values), 0, len(payload)) + payload


def picture(kind='PNG', size=(4, 3), color=(20, 30, 40, 255)):
    from PIL import Image
    stream = io.BytesIO()
    image = Image.new('RGBA', size, color)
    if kind == 'JPEG':
        image = image.convert('RGB')
    image.save(stream, format=kind)
    return stream.getvalue()


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.cache = self.root / 'cache'
        self.sources = []

    def package(self, name, resources, origin='mod'):
        path = self.root / name
        path.write_bytes(dbpf_build.build(resources))
        self.sources.append({'path': str(path), 'origin': origin})
        return path

    def prepare(self, data, **fields):
        request = {'resource_tgi': catalog.tgi(PART),
                   'effective_resource_sha256': catalog.digest(data), **fields}
        with patch.object(catalog, 'studio_executable', return_value=catalog.STUDIO):
            return catalog.prepare(self.sources, [request], self.cache)

    def broker(self, result):
        return catalog.Broker(result['manifest'], result['manifest_sha256'])

    def test_exact_hash_bound_skin_detail_name_image_and_independent_open_copy(self):
        raw = part(body=35, title=0x99)
        original = self.package('skin.package', {
            PART: raw, THUMB: picture(), (catalog.STBL, 0, 1): strings({0x99: 'Freckles – exact title'})})
        before = original.read_bytes()
        result = self.prepare(raw, body_type=35, gender='female')
        row = result['catalog']['items'][0]
        self.assertEqual((row['status'], row['body_type']), ('resolved', 35))
        self.assertEqual(row['display_name'], 'Freckles – exact title')
        self.assertEqual(row['name_status'], 'localized-title')
        self.assertEqual(row['resource_tgi'], catalog.tgi(PART))
        self.assertEqual(row['thumbnail']['resource_tgi'], catalog.tgi(THUMB))
        self.assertEqual((row['thumbnail']['width'], row['thumbnail']['height']), (4, 3))
        broker = self.broker(result)
        image = broker.thumbnail(row['resource_id'])
        self.assertTrue(image.startswith(b'\x89PNG'))
        launch = Mock()
        with patch.object(catalog, 'studio_executable', return_value=catalog.STUDIO):
            response = broker.open(row['resource_id'], row['cache_proof'], launcher=launch)
        argv = launch.call_args.args[0]
        opened = Path(argv[1])
        self.assertEqual(argv[0], str(catalog.STUDIO))
        self.assertNotEqual(opened, original)
        self.assertIn(self.cache, opened.parents)
        self.assertEqual(opened.read_bytes(), before)
        self.assertEqual(launch.call_args.kwargs['shell'], False)
        self.assertFalse(response['resource_selection_supported'])
        opened.write_bytes(b'edited user copy')
        self.assertEqual(original.read_bytes(), before)
        self.assertEqual(catalog.file_hash(broker.cache / broker.records[row['resource_id']]['package_file']),
                         row['provenance']['package_sha256'])

    def test_effective_resource_hash_selects_real_override_without_filename_guess(self):
        effective = part(body=73)
        self.package('z-last.package', {PART: part(body=35)})
        self.package('a-first.package', {PART: effective})
        row = self.prepare(effective)['catalog']['items'][0]
        self.assertEqual(row['status'], 'resolved')
        self.assertEqual(row['body_type'], 73)
        self.assertEqual(row['display_name'], 'a-first.package')
        self.assertEqual(row['name_status'], 'cc-package-filename')
        self.assertEqual(row['code_name'], 'Apex test part')
        self.assertEqual(row['package_name'], 'a-first.package')

    def test_cc_filename_and_genuine_code_remain_independent_with_exact_unicode(self):
        raw = part()
        filename = '[Creator] Moon — freckles v2.PACKAGE'
        self.package(filename, {PART: raw})
        row = self.prepare(raw)['catalog']['items'][0]
        self.assertEqual(row['preferred_name'], filename)
        self.assertEqual(row['package_name'], filename)
        self.assertEqual(row['code_name'], 'Apex test part')
        self.assertEqual(row['preferred_name_status'], 'cc-package-filename')
        self.assertEqual(row['display_name'], row['preferred_name'])
        self.assertEqual(row['name_status'], row['preferred_name_status'])
        self.assertEqual(row['provenance']['package_filename'], filename)
        self.assertEqual(row['metadata']['internal_name'], row['code_name'])

    def test_validated_localized_title_precedes_cc_filename_and_retains_both_names(self):
        raw = part(title=99)
        self.package('[Creator] Original.package', {
            PART: raw, (catalog.STBL, 0, 1): strings({99: 'Exact native title'})})
        row = self.prepare(raw)['catalog']['items'][0]
        self.assertEqual(row['preferred_name'], 'Exact native title')
        self.assertEqual(row['preferred_name_status'], 'localized-title')
        self.assertEqual(row['package_name'], '[Creator] Original.package')
        self.assertEqual(row['code_name'], 'Apex test part')
        self.assertEqual(row['name_evidence'][0]['string_table_tgi'], catalog.tgi((catalog.STBL, 0, 1)))

    def test_ea_without_title_keeps_genuine_code_as_preferred(self):
        raw = part()
        self.package('ClientFullBuild0.package', {PART: raw}, origin='ea')
        row = self.prepare(raw)['catalog']['items'][0]
        self.assertEqual(row['preferred_name'], 'Apex test part')
        self.assertEqual(row['preferred_name_status'], 'casp-internal-name')
        self.assertEqual(row['package_name'], 'ClientFullBuild0.package')
        self.assertEqual(row['code_name'], 'Apex test part')

    def test_blank_localized_title_does_not_hide_cc_package_name(self):
        raw = part(title=99)
        self.package('Creator Exact.package', {
            PART: raw, (catalog.STBL, 0, 1): strings({99: '  \t'})})
        row = self.prepare(raw)['catalog']['items'][0]
        self.assertEqual(row['preferred_name'], 'Creator Exact.package')
        self.assertEqual(row['preferred_name_status'], 'cc-package-filename')

    def test_absent_casp_code_stays_null_without_inventing_ea_item_name(self):
        raw = bytearray(part())
        size = raw[12]
        del raw[13:13 + size]
        raw[12] = 0
        struct.pack_into('<I', raw, 4, struct.unpack_from('<I', raw, 4)[0] - size)
        raw = bytes(raw)
        self.package('ClientFullBuild0.package', {PART: raw}, origin='ea')
        row = self.prepare(raw)['catalog']['items'][0]
        self.assertEqual(row['status'], 'resolved')
        self.assertIsNone(row['code_name'])
        self.assertIsNone(row['preferred_name'])
        self.assertEqual(row['preferred_name_status'], 'unresolved')
        self.assertEqual(row['package_name'], 'ClientFullBuild0.package')

    def test_failed_resolution_clears_previously_candidate_name_fields(self):
        raw = part(title=99)
        self.package('Original.package', {
            PART: raw, (catalog.STBL, 0, 1): strings({99: 'Real title'})})
        row = self.prepare(raw, gender='unverified')['catalog']['items'][0]
        self.assertEqual(row['status'], 'unresolved')
        for field in ['preferred_name', 'package_name', 'code_name', 'display_name']:
            self.assertIsNone(row[field])
        self.assertEqual(row['preferred_name_status'], 'unresolved')
        self.assertEqual(row['name_status'], 'unresolved')

    def test_unresolved_and_ambiguous_names_never_gain_filename_guess(self):
        raw = part()
        self.package('First.package', {PART: raw})
        self.package('Second.package', {PART: raw})
        ambiguous = self.prepare(raw)['catalog']['items'][0]
        unresolved = self.prepare(part(body=999))['catalog']['items'][0]
        for row in [ambiguous, unresolved]:
            for field in ['preferred_name', 'package_name', 'code_name', 'display_name']:
                self.assertIsNone(row[field])
            self.assertEqual(row['preferred_name_status'], 'unresolved')

    def test_identical_effective_bytes_in_two_packages_do_not_prove_owner(self):
        raw = part()
        self.package('a.package', {PART: raw})
        self.package('b.package', {PART: raw})
        row = self.prepare(raw)['catalog']['items'][0]
        self.assertEqual(row['status'], 'ambiguous')
        self.assertIsNone(row['provenance'])
        self.assertEqual(row['studio_open']['status'], 'unavailable')

    def test_unknown_effective_hash_or_unmapped_catalog_id_never_resolves(self):
        self.package('a.package', {PART: part()})
        row = self.prepare(part(body=999))['catalog']['items'][0]
        self.assertEqual(row['status'], 'unresolved')
        with self.assertRaises(ValueError):
            catalog.prepare(self.sources, [{'resource_tgi': '414264',
                                            'effective_resource_sha256': 'a' * 64}], self.cache)
        with self.assertRaises(ValueError):
            catalog.prepare(self.sources, [{'resource_tgi': catalog.tgi(PART)}], self.cache)

    def test_title_conflict_and_thumbnail_conflict_fail_closed(self):
        raw = part(title=99)
        self.package('part.package', {PART: raw, THUMB: picture(),
                                      (catalog.STBL, 0, 1): strings({99: 'One'})})
        self.package('other.package', {THUMB: picture(color=(90, 100, 120, 255)),
                                       (catalog.STBL, 0, 2): strings({99: 'Two'})})
        row = self.prepare(raw, gender='female')['catalog']['items'][0]
        self.assertEqual(row['name_status'], 'cc-package-filename')
        self.assertEqual(row['thumbnail']['status'], 'unresolved')
        self.assertIn('Conflicting', row['thumbnail']['reason'])

    def test_locale_and_male_thumbnail_are_explicit(self):
        raw = part(title=99)
        male = (catalog.CAS_THUMB, 0x102, PART[2])
        self.package('part.package', {PART: raw, male: picture(),
            (catalog.STBL, 0, 1 << 56): strings({99: 'Another language'})})
        row = self.prepare(raw, gender='male')['catalog']['items'][0]
        self.assertEqual(row['name_status'], 'cc-package-filename')
        self.assertEqual(row['thumbnail']['resource_tgi'], catalog.tgi(male))

    def test_changed_source_index_and_changed_sealed_cache_refuse_reads_and_open(self):
        raw = part()
        original = self.package('part.package', {PART: raw})
        package = catalog.Package(original, 'mod')
        original.write_bytes(dbpf_build.build({PART: part(body=18)}))
        with self.assertRaisesRegex(ValueError, 'changed'):
            package.read(PART)
        original.write_bytes(dbpf_build.build({PART: raw}))
        result = self.prepare(raw)
        broker = self.broker(result)
        row = result['catalog']['items'][0]
        sealed = self.cache / broker.records[row['resource_id']]['package_file']
        sealed.write_bytes(b'changed')
        launch = Mock()
        with patch.object(catalog, 'studio_executable', return_value=catalog.STUDIO):
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                broker.open(row['resource_id'], row['cache_proof'], launch)
        launch.assert_not_called()
        self.assertEqual(original.read_bytes(), dbpf_build.build({PART: raw}))

    def rewrite_with_original_times(self, path, changed):
        before = path.stat()
        self.assertEqual(len(changed), before.st_size)
        path.write_bytes(changed)
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertEqual(path.stat().st_size, before.st_size)
        self.assertEqual(path.stat().st_mtime_ns, before.st_mtime_ns)

    def test_same_size_source_resource_rewrite_with_unchanged_signature_refuses(self):
        raw = part(body=35)
        original = self.package('part.package', {PART: raw})
        package = catalog.Package(original, 'mod')
        changed = dbpf_build.build({PART: part(body=18)})
        self.rewrite_with_original_times(original, changed)
        self.assertNotEqual(catalog.file_hash(original), package.source_sha256)
        # NTFS creation/mtime granularity can leave every signature component
        # unchanged. Model that observation while retaining the real rewrite.
        with patch.object(catalog, 'signature', return_value=package.before):
            with self.assertRaisesRegex(ValueError, 'changed'):
                package.read(PART)

    def test_streamed_extent_crosses_chunk_boundary_and_binds_unrequested_bytes(self):
        # Independent uncompressed wire fixture places CASP across the 1 MiB
        # stream boundary, rather than relying on the compressed build helper.
        padding, raw = b'p' * (1024 * 1024 - 100), part()
        unrelated = (1, 0, 1)
        index = struct.pack('<I', 0)
        for item, start, payload in ((unrelated, 96, padding),
                                     (PART, 96 + len(padding), raw)):
            index += struct.pack('<7I', item[0], item[1], item[2] >> 32,
                                 item[2] & 0xffffffff, start, len(payload), len(payload))
        header = bytearray(96)
        header[:4] = b'DBPF'
        struct.pack_into('<II', header, 4, 2, 1)
        struct.pack_into('<I', header, 36, 2)
        struct.pack_into('<I', header, 44, len(index))
        struct.pack_into('<I', header, 64, 96 + len(padding) + len(raw))
        path = self.root / 'stream.package'
        original = bytes(header) + padding + raw + index
        path.write_bytes(original)
        package = catalog.Package(path, 'ea')
        self.assertEqual(package.source_sha256, catalog.digest(original))
        self.assertEqual(package.read(PART), raw)
        self.assertEqual(package.read(unrelated), padding)
        changed = bytearray(original)
        changed[96] ^= 1  # The requested CASP and every index byte stay exact.
        self.rewrite_with_original_times(path, bytes(changed))
        with patch.object(catalog, 'signature', return_value=package.before):
            with self.assertRaisesRegex(ValueError, 'changed'):
                package.read(PART)

    def test_same_size_source_index_rewrite_refuses_unchanged_resource_and_copy(self):
        raw = part()
        original = self.package('part.package', {PART: raw})
        package = catalog.Package(original, 'mod')
        replacement = (PART[0], PART[1], PART[2] + 1)
        self.rewrite_with_original_times(original, dbpf_build.build({replacement: raw}))
        self.assertEqual(catalog.Package(original, 'mod').read(replacement), raw)
        with patch.object(catalog, 'signature', return_value=package.before):
            with self.assertRaisesRegex(ValueError, 'changed'):
                package.read(PART)
            with self.assertRaisesRegex(ValueError, 'changed'):
                catalog.copy_package(package, self.cache)
        self.assertFalse(any((self.cache / 'packages').iterdir()))

    def test_same_size_unrequested_source_change_blocks_copy_of_old_provenance(self):
        unrelated = (0x12345678, 0, 42)
        original = self.package('part.package', {PART: part(), unrelated: b'first'})
        package = catalog.Package(original, 'mod')
        self.rewrite_with_original_times(original,
            dbpf_build.build({PART: part(), unrelated: b'other'}))
        with patch.object(catalog, 'signature', return_value=package.before):
            with self.assertRaisesRegex(ValueError, 'changed'):
                catalog.copy_package(package, self.cache)
        self.assertFalse(any((self.cache / 'packages').iterdir()))

    def test_same_size_sealed_cache_rewrite_refuses_before_copy_or_studio_launch(self):
        raw = part(body=35)
        original = self.package('part.package', {PART: raw})
        before = original.read_bytes()
        result = self.prepare(raw)
        row, broker = result['catalog']['items'][0], self.broker(result)
        sealed = self.cache / broker.records[row['resource_id']]['package_file']
        self.rewrite_with_original_times(sealed, dbpf_build.build({PART: part(body=18)}))
        launch = Mock()
        with patch.object(catalog, 'studio_executable', return_value=catalog.STUDIO), \
                patch.object(catalog.shutil, 'copyfile') as copy:
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                broker.open(row['resource_id'], row['cache_proof'], launch)
        copy.assert_not_called()
        launch.assert_not_called()
        self.assertFalse((self.cache / 'open').exists())
        self.assertEqual(original.read_bytes(), before)

    def test_same_size_thumbnail_rewrite_with_original_times_refuses_delivery(self):
        raw = part()
        self.package('part.package', {PART: raw, THUMB: picture()})
        result = self.prepare(raw)
        row, broker = result['catalog']['items'][0], self.broker(result)
        image = self.cache / broker.records[row['resource_id']]['thumbnail_file']
        changed = bytearray(image.read_bytes())
        changed[-1] ^= 1
        self.rewrite_with_original_times(image, bytes(changed))
        with self.assertRaisesRegex(ValueError, 'hash differs'):
            broker.thumbnail(row['resource_id'])
        launch = Mock()
        with self.assertRaisesRegex(ValueError, 'hash differs'):
            broker.open(row['resource_id'], row['cache_proof'], launch)
        launch.assert_not_called()

    def test_manifest_or_request_proof_changes_refuse_open(self):
        raw = part()
        self.package('part.package', {PART: raw})
        result = self.prepare(raw)
        broker = self.broker(result)
        row = result['catalog']['items'][0]
        with self.assertRaises(ValueError):
            broker.open(row['resource_id'], '0' * 64, Mock())
        Path(result['manifest']).write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError, 'manifest hash'):
            self.broker(result)
        launch = Mock()
        with self.assertRaisesRegex(ValueError, 'manifest changed'):
            broker.open(row['resource_id'], row['cache_proof'], launch)
        launch.assert_not_called()

    def test_changed_thumbnail_cache_blocks_image_and_open_without_launch(self):
        raw = part()
        self.package('part.package', {PART: raw, THUMB: picture()})
        result = self.prepare(raw)
        row, broker = result['catalog']['items'][0], self.broker(result)
        path = self.cache / broker.records[row['resource_id']]['thumbnail_file']
        path.write_bytes(picture(color=(1, 2, 3, 255)))
        with self.assertRaisesRegex(ValueError, 'hash differs'):
            broker.thumbnail(row['resource_id'])
        launch = Mock()
        with self.assertRaisesRegex(ValueError, 'hash differs'):
            broker.open(row['resource_id'], row['cache_proof'], launch)
        launch.assert_not_called()

    def test_changed_studio_build_never_launches(self):
        raw = part()
        self.package('part.package', {PART: raw})
        result = self.prepare(raw)
        row = result['catalog']['items'][0]
        launch = Mock()
        with patch.object(catalog, 'studio_executable', side_effect=ValueError('Build changed')):
            with self.assertRaisesRegex(ValueError, 'Build changed'):
                self.broker(result).open(row['resource_id'], row['cache_proof'], launch)
        launch.assert_not_called()

    def test_ea_index_before_resource_bodies_is_supported_and_overlap_rejected(self):
        raw = dbpf_build.build({PART: part(), THUMB: picture()})
        header = bytearray(raw[:96])
        index_offset = struct.unpack_from('<I', header, 64)[0]
        index = bytearray(raw[index_offset:])
        count = struct.unpack_from('<I', header, 36)[0]
        for i in range(count):
            at = 4 + i * 32 + 16
            old = struct.unpack_from('<I', index, at)[0]
            struct.pack_into('<I', index, at, old + len(index))
        struct.pack_into('<I', header, 64, 96)
        path = self.root / 'ea-layout.package'
        path.write_bytes(header + index + raw[96:index_offset])
        package = catalog.Package(path, 'ea')
        self.assertEqual(package.read(PART), part())
        struct.pack_into('<I', index, 4 + 16, 97)
        path.write_bytes(header + index + raw[96:index_offset])
        with self.assertRaisesRegex(ValueError, 'extent'):
            catalog.Package(path, 'ea')

    def test_ea_zero_extent_empty_resources_do_not_block_unrelated_casp(self):
        payload = part()
        index = struct.pack('<I', 0)
        index += struct.pack('<7I', 0x01661233, 0, 0, 9, 0, 0, 0)
        index += struct.pack('<7I', PART[0], PART[1], PART[2] >> 32, PART[2] & 0xffffffff,
                             96 + 60, len(payload), len(payload))
        header = bytearray(96)
        header[:4] = b'DBPF'
        struct.pack_into('<II', header, 4, 2, 1)
        struct.pack_into('<I', header, 36, 2)
        struct.pack_into('<I', header, 44, len(index))
        struct.pack_into('<I', header, 64, 96)
        path = self.root / 'ea-empty.package'
        path.write_bytes(header + index + payload)
        package = catalog.Package(path, 'ea')
        self.assertEqual(package.read((0x01661233, 0, 9)), b'')
        self.assertEqual(package.read(PART), payload)

    def test_refpack_bounded_commands_and_real_ea_string_table_layout(self):
        payload = strings({99: 'Exact localized title'})
        packed = bytearray(b'\x50\xfb' + len(payload).to_bytes(3, 'big'))
        position = 0
        while len(payload) - position >= 4:
            count = min((len(payload) - position) // 4, 28)
            packed.append(0xe0 + count - 1)
            packed.extend(payload[position:position + count * 4])
            position += count * 4
        packed.append(0xfc + len(payload) - position)
        packed.extend(payload[position:])
        self.assertEqual(catalog.stbl_strings(catalog.refpack(bytes(packed), len(payload)))[99],
                         'Exact localized title')
        overlap = b'\x50\xfb\x00\x00\x09\xe0abcd\x08\x03\xfc'
        self.assertEqual(catalog.refpack(overlap, 9), b'abcdabcda')
        for invalid, bound in ((overlap, 8), (overlap[:-1], 9),
                               (b'\x50\xfb\x00\x00\x03\x00\x01\xfc', 3),
                               (overlap + b'x', 9)):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                catalog.refpack(invalid, bound)

    def test_variant_thumbnail_is_retained_as_swatch_link_not_catalog_image(self):
        data = bytearray(part())
        table = struct.unpack_from('<I', data, 4)[0] + 8
        data[table] = 1
        data += struct.pack('<QII', 0x77, 0, 0x00B2D882)
        raw = bytes(data)
        self.package('variant.package', {PART: raw, THUMB: picture(),
                                         (0x00B2D882, 0, 0x77): picture(color=(100, 90, 50, 255))})
        row = self.prepare(raw, gender='female')['catalog']['items'][0]
        self.assertEqual(row['metadata']['variant_thumbnail_tgi'], '00B2D882:00000000:0000000000000077')
        self.assertEqual(row['thumbnail']['resource_tgi'], catalog.tgi(THUMB))
        self.assertEqual(row['thumbnail']['association'], 'installed-studio-casp-key')

    def test_casp_versions_and_all_body_types_preserve_metadata(self):
        for version in range(44, 53):
            for body in (0, 7, 35, 73, 255):
                with self.subTest(version=version, body=body):
                    meta = catalog.casp_metadata(casp(version=version, body=body))
                    self.assertEqual(meta['body_type'], body)
                    self.assertEqual(meta['internal_name'], 'Apex test part')
        with self.assertRaises(ValueError):
            catalog.casp_metadata(casp(version=53))

    def test_ts4_jpeg_embedded_alpha_decodes_actual_pixels_without_placeholder(self):
        from PIL import Image
        jpeg, alpha = picture('JPEG'), picture(color=(83, 83, 83, 255))
        # Installed Studio's TS4 thumbnail format: 12 original JPEG bytes,
        # APP0 segment header, ALFA + big-endian PNG length, remaining JPEG.
        segment_size = len(alpha) + 10
        frame = (jpeg[:12] + struct.pack('<II', 16777217, 256) + b'\xff\xe0' +
                 struct.pack('>H', segment_size) + b'ALFA' + struct.pack('>I', len(alpha)) + alpha + jpeg[12:])
        output, width, height = catalog.thumbnail_png(frame)
        self.assertEqual((width, height), (4, 3))
        with Image.open(io.BytesIO(output)) as image:
            self.assertEqual(image.getpixel((0, 0))[3], 83)
        for invalid in (b'encrypted thumbnail', picture(size=(513, 1)), frame[:30]):
            with self.assertRaises((ValueError, OSError)):
                catalog.thumbnail_png(invalid)

    def test_http_typed_loopback_routes_reject_arbitrary_paths_origin_and_commands(self):
        raw = part()
        self.package('part.package', {PART: raw, THUMB: picture()})
        result = self.prepare(raw)
        broker = self.broker(result)
        row = result['catalog']['items'][0]
        server = ThreadingHTTPServer(('127.0.0.1', 0), catalog.handler(broker))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        def request(method, path, value=None, **headers):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
            body = json.dumps(value).encode() if value is not None else None
            connection.request(method, path, body, {'Host': '127.0.0.1:8022',
                               'Content-Type': 'application/json', **headers})
            response = connection.getresponse()
            status, data = response.status, response.read()
            connection.close()
            return status, data
        self.assertEqual(request('GET', '/v1/resources')[0], 200)
        self.assertEqual(request('GET', row['thumbnail']['url'])[0], 200)
        self.assertEqual(request('GET', '/v1/resources', Origin='https://untrusted.example')[0], 403)
        self.assertEqual(request('GET', '/../../part.package')[0], 404)
        with patch.object(broker, 'open', return_value={'ok': True}) as open_mock:
            self.assertEqual(request('POST', '/v1/open', {'resource_id': row['resource_id'],
                                                        'cache_proof': row['cache_proof']})[0], 200)
            open_mock.assert_called_once_with(row['resource_id'], row['cache_proof'])
            self.assertEqual(request('POST', '/v1/open', {'path': str(self.root), 'command': 'any'})[0], 409)
            self.assertEqual(open_mock.call_count, 1)

    def test_cli_never_writes_a_profile_or_serves_an_unpinned_path(self):
        with self.assertRaisesRegex(ValueError, 'fixed external'):
            catalog.main(['prepare', '--input', 'unused.json', '--cache', str(self.root)])
        with self.assertRaisesRegex(ValueError, 'fixed external'):
            catalog.main(['serve', '--manifest', str(self.root / 'any.json'),
                          '--expected-manifest-sha256', 'a' * 64])

    def test_parent_traversal_and_redirected_ancestors_refuse_before_cache_write(self):
        outside = self.root / 'outside'
        traversal = str(catalog.CACHE_ROOT / '..' / '..' / 'outside')
        with self.assertRaisesRegex(ValueError, 'traversal'):
            catalog.main(['prepare', '--input', 'unused.json', '--cache', traversal])
        with self.assertRaisesRegex(ValueError, 'traversal'):
            catalog.ensure_directory(self.cache / '..' / 'outside', '')
        self.assertFalse(outside.exists())
        actual, link = self.root / 'actual', self.root / 'link'
        actual.mkdir()
        try:
            link.symlink_to(actual, target_is_directory=True)
        except OSError as error:
            self.skipTest('Directory symlinks unavailable: ' + str(error))
        with self.assertRaisesRegex(ValueError, 'redirected'):
            catalog.prepare([], [], link / 'nested' / 'cache')
        self.assertFalse((actual / 'nested').exists())


if __name__ == '__main__':
    unittest.main()
