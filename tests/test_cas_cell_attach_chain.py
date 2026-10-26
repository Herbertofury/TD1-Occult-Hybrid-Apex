"""Frozen final Main admission and actual postpass seam; no compiler calls."""
import ast
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]
import cas_cell_attach as attach
import cas_draw_fast_path as draw
import cas_structural_roles as roles
import cas_communication_index as communication
import cas_ui_build as ui
import dbpf_build
import maru_companion
import cas_catalog_binding as binding
import cas_draw_phase as phase
import cas_swatch_geometry as swatch
import cas_preview_transition as preview
import cas_grid_scroll as scroll
import cas_grid_budget as budget
import cas_grid_featured as featured
from cas_main_chain_fixtures import current_main, rollback_terminal_main, TERMINAL_MAIN_MARKERS

WORK = ROOT / '.work/v335-cell-attach'
READY = all((WORK / name).is_file() for name in ('chained.json', 'baseline.swf', 'final.swf'))


def fixture():
    return json.loads((WORK / 'chained.json').read_text()), (WORK / 'final.swf').read_bytes()


def refresh_envelope(record):
    record['previous_chain_sha256'] = communication.contract_digest(record['previous_chain'])
    record['cell_attach_contract']['previous_chain_sha256'] = record['previous_chain_sha256']
    record['postproof_sha256'] = communication.contract_digest(record['cell_attach_contract'])


def main_fixture(info, resources, historical=False):
    # This explicit historical Main predates binding and granular diagnostics.
    # Replace their envelopes, unique tool pins and final bytes together.
    rollback_terminal_main(info,resources)
    info.pop('catalog_binding_native_bytecode_contract', None)
    info.pop('draw_phase_native_bytecode_contract', None)
    for name in phase.SOURCES[:2]:
        info['source_pins'].pop(name, None)
    for name in binding.SOURCES[:2]:
        info['source_pins'].pop(name, None)
    record, final = fixture()
    info.update(copy.deepcopy(record['previous_chain']))
    for value in record['previous_chain'].values():
        info['source_pins'].update(value.get('source_sha256', {}))
    if historical:
        info.pop('cell_attach_native_bytecode_contract', None)
        for name in attach.SOURCES[:2]:
            info['source_pins'].pop(name, None)
        resources[maru_companion.CUSTOMIZER] = (WORK / 'baseline.swf').read_bytes()
    else:
        info['cell_attach_native_bytecode_contract'] = record
        info['source_pins'].update(record['cell_attach_contract']['source_sha256'])
        resources[maru_companion.CUSTOMIZER] = final
    final_hash = dbpf_build.digest(resources[maru_companion.CUSTOMIZER])
    info['patched_resource_sha256'] = final_hash
    info['patched_resources'][dbpf_build.tgi(maru_companion.CUSTOMIZER)] = final_hash
    return info, resources


@unittest.skipUnless(READY, 'Frozen private Main attach fixture required')
class CellAttachContinuationTests(unittest.TestCase):
    def test_final_main_reconstructs_exact_historical_fast_stage_and_keeps_counts_historical(self):
        record, final = fixture()
        previous = record['previous_chain']
        baseline = (WORK / 'baseline.swf').read_bytes()
        self.assertTrue(attach.verify_contract(record, final))
        self.assertEqual(attach.reconstruct_previous(final), baseline)
        self.assertEqual(draw.chain_contract(previous['native_bytecode_contract'],
            previous['structural_roles_native_bytecode_contract'],
            previous['draw_fast_path_native_bytecode_contract'], baseline),
            previous['draw_fast_path_native_bytecode_contract'])
        self.assertNotEqual(dbpf_build.digest(final), previous['draw_fast_path_native_bytecode_contract']['final_swf_sha256'])
        self.assertNotEqual(dbpf_build.digest(draw.abc_payload(final)), previous['draw_fast_path_native_bytecode_contract']['abc_sha256'])
        self.assertEqual(previous['native_bytecode_contract']['unchanged_native_methods'], 2616)
        self.assertEqual(previous['structural_roles_native_bytecode_contract']['unchanged_original_native_bodies_after_chain'], 2615)
        post = record['cell_attach_contract']
        self.assertEqual((post['edited_existing_methods'], post['removed_instructions'],
                          post['appended_methods'], post['appended_traits'], post['appended_pool_entries']), (1, 5, 0, 0, 0))
        self.assertIs(post['runtime_qualified'], False)
        self.assertIs(post['performance_gain_claimed'], False)

    def test_rehashed_proof_counts_predicates_source_and_historical_corruption_are_refused(self):
        record, final = fixture()
        changes = [('ok', 1), ('removed_instructions', 3), ('edited_existing_methods', 0),
                   ('appended_methods', 1), ('appended_traits', 1), ('appended_pool_entries', 1),
                   ('edited_existing_methods', True), ('appended_methods', False),
                   ('appended_traits', False), ('appended_pool_entries', False),
                   ('donor_swf_sha256', '0' * 64), ('baseline_swf_sha256', '0' * 64),
                   ('baseline_abc_sha256', '0' * 64), ('abc_sha256', '0' * 64),
                   ('baseline_config_ui_sha256', '0' * 64), ('config_ui_sha256', '0' * 64),
                   ('dead_immediate_overwrite_verified', False), ('authoritative_static_slot_verified', False),
                   ('final_xy_writes_retained', False), ('rightclick_favorite_body_retained', False),
                   ('native_cfg_projection_verified', 1), ('whole_abc_rollback_verified', False),
                   ('all_other_methods_retained', False), ('runtime_qualified', True), ('performance_gain_claimed', True)]
        for field, value in changes:
            changed = copy.deepcopy(record)
            changed['cell_attach_contract'][field] = value
            refresh_envelope(changed)
            with self.subTest(field=field), self.assertRaises(ValueError):
                attach.verify_contract(changed, final)
        for source in attach.SOURCES:
            changed = copy.deepcopy(record)
            changed['cell_attach_contract']['source_sha256'][source] = '0' * 64
            refresh_envelope(changed)
            with self.subTest(source=source), self.assertRaises(ValueError):
                attach.verify_contract(changed, final)
        for stage, field in [('native_bytecode_contract', 'native_method_count'),
                             ('structural_roles_native_bytecode_contract', 'main_and_height_preserved'),
                             ('draw_fast_path_native_bytecode_contract', 'disabled_callback_reads')]:
            changed = copy.deepcopy(record)
            changed['previous_chain'][stage][field] = 0
            refresh_envelope(changed)
            with self.subTest(stage=stage), self.assertRaises(ValueError):
                attach.verify_contract(changed, final)

    def test_unowned_native_body_corruption_with_all_outer_hashes_recomputed_is_refused(self):
        record, final = fixture()
        payload = next(tag[3] for tag in ui.tags(ui.unpack(final)[1]) if tag[0] == 82)
        boundary = payload.index(b'\0', 4) + 1
        abc = payload[boundary:]
        row = next(row for row in attach._ABCReader(abc).code_vectors()
                   if row['method'] < 2650 and len(row['code']) > 8 and row['code'][0] == 0xd0
                   and attach.digest(row['code']) != attach.EDITED_CONFIG_UI_SHA256)
        changed_abc = bytearray(abc)
        changed_abc[row['code_at']] = 0xd1  # Same-sized valid getlocal opcode in an unrelated native body.
        changed_bytes = ui.replace_payload(final, payload[:boundary] + changed_abc)
        forged = copy.deepcopy(record)
        forged['cell_attach_contract']['abc_sha256'] = attach.digest(changed_abc)
        forged['final_swf_sha256'] = attach.digest(changed_bytes)
        refresh_envelope(forged)
        with self.assertRaisesRegex(ValueError, 'reconstruct'):
            attach.verify_contract(forged, changed_bytes)

    def test_actual_main_builder_runs_all_ten_postpasses_on_current_bytes(self):
        # This seam consumes mutable current compiler cache entries. Authenticate
        # those entries against the CURRENT package chain rather than mixing
        # them with the immutable V334 Main used by the historical tests above.
        package = ROOT / 'dist/candidate/ApexCASBridge.package'
        info = json.loads(Path(str(package) + '.manifest.json').read_text())
        outer,bound_final,final=current_main('binding')
        record = info['cell_attach_native_bytecode_contract']
        self.assertTrue(attach.verify_contract(record, final))
        prior = record['previous_chain']
        for stage, proof in prior.items():
            self.assertEqual(proof, info[stage])
        baseline = attach.reconstruct_previous(final)
        native = ROOT / '.work/research/structural-roles/retained-baseline.swf'
        role_abc = (ROOT / '.work/research/structural-roles/retained.abc').read_bytes()
        self.assertEqual(draw.digest(native.read_bytes()), prior['structural_roles_native_bytecode_contract']['baseline_swf_sha256'])
        self.assertEqual(draw.digest(role_abc), prior['structural_roles_native_bytecode_contract']['abc_sha256'])
        outer, bound_final, _ = current_main('binding')
        self.assertTrue(binding.verify_contract(outer, bound_final))
        self.assertEqual(outer['previous_stage_contract'], record)
        self.assertEqual(binding.reconstruct_previous(bound_final, outer['catalog_binding_contract']), final)
        phase_outer, phase_final, _ = current_main('phase')
        self.assertTrue(phase.verify_contract(phase_outer, phase_final))
        self.assertEqual(phase_outer['previous_stage_contract'], outer)
        self.assertEqual(phase.reconstruct_previous(phase_final, phase_outer['draw_phase_contract']), bound_final)
        swatch_outer,swatch_final,swatch_prior=current_main('swatch')
        self.assertTrue(swatch.verify_contract(swatch_outer,swatch_final))
        self.assertEqual(swatch_outer['previous_stage_contract'],phase_outer)
        self.assertEqual(swatch_prior,phase_final)
        preview_outer,preview_final,preview_prior=current_main('preview')
        self.assertTrue(preview.verify_contract(preview_outer,preview_final))
        self.assertEqual(preview_outer['previous_stage_contract'],swatch_outer)
        self.assertEqual(preview_prior,swatch_final)
        scroll_outer,scroll_final,scroll_prior=current_main('scroll')
        self.assertTrue(scroll.verify_contract(scroll_outer,scroll_final))
        self.assertEqual(scroll_outer['previous_stage_contract'],preview_outer)
        self.assertEqual(scroll_prior,preview_final)
        budget_outer,budget_final,budget_prior=current_main('budget')
        self.assertTrue(budget.verify_contract(budget_outer,budget_final))
        self.assertEqual(budget_outer['previous_stage_contract'],scroll_outer)
        self.assertEqual(budget_prior,scroll_final)
        featured_outer,featured_final,featured_prior=current_main('featured')
        self.assertTrue(featured.verify_main(featured_outer,featured_final))
        self.assertEqual(featured_outer['previous_stage_contract'],budget_outer)
        self.assertEqual(featured_prior,budget_final)
        tree = ast.parse(Path(ui.__file__).read_text())
        build = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'build')
        block = next(node for node in build.body if isinstance(node, ast.If) and
                     any(isinstance(child, ast.Import) and any(alias.name == 'cas_structural_roles' for alias in child.names)
                         for child in node.body))
        native_tag = next(tag[3] for tag in ui.tags(ui.unpack(native.read_bytes())[1]) if tag[0] == 82)
        order = []
        def adapt_roles(*args):
            order.append('structural')
            self.assertEqual(args[1], native.read_bytes())
            return role_abc, prior['structural_roles_native_bytecode_contract']
        def adapt_draw(*args):
            order.append('draw')
            self.assertEqual(draw.digest(args[2]), prior['structural_roles_native_bytecode_contract']['final_swf_sha256'])
            return draw.abc_payload(baseline), prior['draw_fast_path_native_bytecode_contract']
        def adapt_attach(*args):
            order.append('attach')
            self.assertEqual(attach.digest(Path(args[0]).read_bytes()), attach.DONOR)
            self.assertEqual(args[4], baseline)
            self.assertEqual(args[1:4], tuple(prior[name] for name in
                ('native_bytecode_contract', 'structural_roles_native_bytecode_contract', 'draw_fast_path_native_bytecode_contract')))
            return draw.abc_payload(final), record['cell_attach_contract']
        def adapt_binding(*args):
            order.append('binding')
            self.assertEqual(args[0], record)
            self.assertEqual(args[1], final)
            self.assertEqual(args[2], ROOT / '.work/research/current-cas/scripts/scripts/widgets/CAS/Customizer/CASCustomizerMain.as')
            return bound_final, outer['catalog_binding_contract']
        def adapt_phase(*args):
            order.append('phase')
            self.assertEqual(args[0], outer)
            self.assertEqual(args[1], bound_final)
            self.assertEqual(args[2], ROOT / '.work/research/current-cas/scripts/scripts/widgets/CAS/Customizer/CASCustomizerMain.as')
            return phase_final, phase_outer['draw_phase_contract']
        def adapt_swatch(*args):
            order.append('swatch')
            self.assertEqual(args[0],phase_outer)
            self.assertEqual(args[1],phase_final)
            self.assertEqual(args[2],ROOT / '.work/research/maru-integrated/DynamicCASCustomizer.swf')
            self.assertEqual(args[3],ROOT / '.work/research/maru-integrated/customizer/scripts')
            return swatch_final,swatch_outer['swatch_geometry_contract']
        def adapt_preview(*args):
            order.append('preview')
            self.assertEqual(args,(swatch_outer,swatch_final))
            return preview_final,preview_outer['preview_transition_contract']
        def adapt_scroll(*args):
            order.append('scroll')
            self.assertEqual(args[0],preview_outer)
            self.assertEqual(args[1],preview_final)
            self.assertEqual(Path(args[2]).name,'CASCustomizerMain.as')
            return scroll_final,scroll_outer
        def adapt_budget(*args):
            order.append('budget')
            self.assertEqual(args[0],scroll_outer);self.assertEqual(args[1],scroll_final)
            self.assertEqual(args[2],namespace['patched'])
            return budget_final,budget_outer
        def adapt_featured(*args):
            order.append('featured')
            self.assertEqual(args[0],budget_outer);self.assertEqual(args[1],budget_final)
            self.assertEqual(args[2],namespace['patched'])
            return featured_final,featured_outer
        with tempfile.TemporaryDirectory() as directory:
            namespace = vars(ui).copy()
            namespace.update(companion={},input_swf=ROOT / '.work/research/maru-integrated/DynamicCASCustomizer.swf',
                payload=native.read_bytes(),contract=prior['native_bytecode_contract'],
                structural_roles_contract=None,draw_fast_path_contract=None,cell_attach_contract=None,
                catalog_binding_contract=None,draw_phase_contract=None,
                swatch_geometry_contract=None,preview_transition_contract=None,scroll_main_contract=None,
                budget_main_contract=None,featured_main_contract=None,
                patched=Path(directory)/'CASCustomizerMain.as',
                customizer_sources=ROOT / '.work/research/maru-integrated/customizer/scripts',
                decompiled=ROOT / '.work/research/current-cas/scripts/scripts/widgets/CAS/Customizer/CASCustomizerMain.as',
                ffdec=ROOT / '.work/research/ffdec/ffdec-cli.exe',work=Path(directory),
                native_tag=native_tag,boundary=native_tag.index(b'\0', 4) + 1)
            with patch.object(roles, 'adapt', side_effect=adapt_roles), patch.object(draw, 'adapt', side_effect=adapt_draw), \
                 patch.object(attach, 'adapt', side_effect=adapt_attach), patch.object(binding, 'adapt', side_effect=adapt_binding), \
                 patch.object(phase, 'adapt', side_effect=adapt_phase), patch.object(swatch, 'adapt', side_effect=adapt_swatch), \
                 patch.object(preview, 'adapt', side_effect=adapt_preview), \
                 patch.object(scroll, 'adapt_main', side_effect=adapt_scroll), \
                 patch.object(budget, 'adapt_main', side_effect=adapt_budget), \
                 patch.object(featured, 'adapt_main', side_effect=adapt_featured):
                exec(compile(ast.Module(body=[block], type_ignores=[]), '<actual-main-postpass-seam>', 'exec'), namespace)
            self.assertEqual(order, ['structural', 'draw', 'attach', 'binding', 'phase', 'swatch', 'preview', 'scroll', 'budget', 'featured'])
            self.assertEqual(namespace['payload'], featured_final)
            self.assertEqual(namespace['cell_attach_contract'], record)
            self.assertEqual(namespace['catalog_binding_contract'], outer)
            self.assertEqual(namespace['draw_phase_contract'], phase_outer)
            self.assertEqual(namespace['swatch_geometry_contract'],swatch_outer)
            self.assertEqual(namespace['preview_transition_contract'],preview_outer)
            self.assertEqual(namespace['scroll_main_contract'],scroll_outer)
            self.assertEqual(namespace['budget_main_contract'],budget_outer)
            self.assertEqual(namespace['featured_main_contract'],featured_outer)


@unittest.skipUnless(READY and (ROOT / 'dist/candidate/ApexCASBridge.package').is_file(), 'Private package Main fixture required')
class CellAttachManifestTests(unittest.TestCase):
    def setUp(self):
        package = ROOT / 'dist/candidate/ApexCASBridge.package'
        self.info = json.loads(Path(str(package) + '.manifest.json').read_text())
        self.resources = dbpf_build.read(package.read_bytes())
        main_fixture(self.info, self.resources)

    def test_current_main_manifest_requires_attach_source_pair_and_final_proof(self):
        self.assertTrue(maru_companion.verify_merged(self.info, self.resources))
        for name in attach.SOURCES[:2]:
            self.assertIn(name, ui.source_pins())
        for group in (attach.SOURCES[:1], attach.SOURCES[1:2], attach.SOURCES[:2]):
            changed = copy.deepcopy(self.info)
            for name in group:
                changed['source_pins'].pop(name, None)
            with self.subTest(missing=group), self.assertRaises(ValueError):
                maru_companion.verify_merged(changed, self.resources)
        changed = copy.deepcopy(self.info)
        del changed['cell_attach_native_bytecode_contract']
        with self.assertRaises(ValueError):
            maru_companion.verify_merged(changed, self.resources)

    def test_current_source_downgrade_and_relabelled_historical_fast_final_are_refused(self):
        changed, resources = copy.deepcopy(self.info), dict(self.resources)
        main_fixture(changed, resources, historical=True)
        changed['source_pins'].update(self.info['cell_attach_native_bytecode_contract']['cell_attach_contract']['source_sha256'])
        with self.assertRaises(ValueError):
            maru_companion.verify_merged(changed, resources)
        changed = copy.deepcopy(self.info)
        changed.pop('cell_attach_native_bytecode_contract')
        for name in attach.SOURCES[:2]:
            changed['source_pins'].pop(name, None)
        with self.assertRaises(ValueError):
            maru_companion.verify_merged(changed, self.resources)

    def test_explicit_historical_main_fast_stage_stays_valid(self):
        main_fixture(self.info, self.resources, historical=True)
        self.assertTrue(maru_companion.verify_merged(self.info, self.resources))
        self.assertNotIn('cell_attach_native_bytecode_contract', self.info)
        self.assertEqual(self.info['draw_fast_path_native_bytecode_contract']['final_swf_sha256'],
                         dbpf_build.digest(self.resources[maru_companion.CUSTOMIZER]))


if __name__ == '__main__':
    unittest.main()
