"""Build the CAS semantic bridge from a user's exact installed UI resource.

Only the compiled DoABC tag is substituted. Every other original tag, including
Scaleform extensions FFDec cannot decode, remains byte-for-byte unchanged.
Game files are read only; proprietary source exports stay in ignored work.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import zlib

import dbpf_build
from source_manifest import write_json

ROOT = Path(__file__).resolve().parents[1]
KEY = (0x62ECC59A, 0, 0xDF09D526F4C77B95)
CLASS = 'widgets.CAS.Customizer.CASCustomizerMain'
PIN = '8fe6d87964b8d2e1ad919972d8bb2168c4c176b9aab7300b2a838e638f87aad6'
SELECTOR_KEY = (0x62ECC59A, 0, 0x26DF5B0A7B97963E)
SELECTOR_CLASS = 'widgets.CAS.SimSelector.CASSimSelectorMain'
SELECTOR_PIN = '420eb0f8417bfc6935ffb4126086f19b72f2cae98a853d34abf6d59a94d454f1'
CLEANUP_KEY = (0x62ECC59A, 0, 0x3FFE72432A703655)
CLEANUP_PIN = 'e79b3b65c8b6234c54d4a76f4c7a671f46ece7ddb9f6940bc5db312850fdef91'
VOICE_KEY = (0x62ECC59A, 0, 0xE36BA403351FFE60)
VOICE_PIN = 'd0f81a01e1ef4039dc8fb4b5d39dac680ea45e512a8102e243e59a99d3362764'
MOLECULE_KEY = (0x62ECC59A, 0, 9034126160331862072)
MOLECULE_PIN = '3124ed12ea50140da6f072d16ab0703e6154e448974edb1c3f6f7d05f7c24524'
PINNED_SOURCES = ('Source/CASUi/semantic_methods.as', 'tools/CasBytecodePatch.java',
                  'NativeOverlay/Source/ApexCasAcceptReadiness.h',
                  'NativeOverlay/Source/ApexNativeCasEngineWin.h',
                  'NativeOverlay/Source/ApexNativeServiceProfilerWin.h',
                  'tools/CasStructuralRolesPatch.java', 'tools/cas_structural_roles.py',
                  'tools/CasGridTransactionPatch.java', 'tools/cas_grid_transaction.py',
                  'tools/CasDrawFastPathPatch.java', 'tools/cas_draw_fast_path.py',
                  'tools/CasCommunicationIndexPatch.java', 'tools/cas_communication_index.py',
                  'tools/CasCommunicationDependencyPatch.java', 'tools/cas_communication_dependency.py',
                  'tools/CasCommunicationDomainProbePatch.java', 'tools/cas_communication_domain_probe.py',
                  'tools/CasCommunicationRemovalMissPatch.java', 'tools/cas_communication_removal_miss.py',
                  'tools/CasImageBoundaryProfilePatch.java', 'tools/cas_image_boundary_profile.py',
                  'tools/CasCellAttachPatch.java', 'tools/cas_cell_attach.py',
                  'tools/CasGridPoolPatch.java', 'tools/cas_grid_pool.py',
                  'tools/CasGridPresentationPatch.java', 'tools/cas_grid_presentation.py',
                  'tools/CasGridProductRowsPatch.java', 'tools/cas_grid_product_rows.py',
                  'tools/CasGridProgressPatch.java', 'tools/cas_grid_progress.py',
                  'tools/CasSwatchProviderPatch.java', 'tools/cas_swatch_provider.py',
                  'tools/cas_grid_scroll.py','tools/CasGridScrollPatch.java','tools/CasGridScrollMainPatch.java',
                  'Source/CASUi/catalog_grid_scroll_methods.as','Source/CASUi/catalog_grid_scroll_main_methods.as',
                  'tools/cas_grid_slice.py','tools/CasGridSlicePatch.java','Source/CASUi/catalog_grid_slice_methods.as',
                  'tools/cas_grid_row_delta.py','tools/cas_row_delta_stage.py','tools/CasGridRowDeltaPatch.java',
                  'tools/cas_grid_physical.py','tools/cas_grid_physical_stage.py','tools/CasGridPhysicalPatch.java',
                  'tools/cas_grid_intrinsic.py','tools/cas_grid_intrinsic_stage.py','tools/CasGridIntrinsicPatch.java',
                  'Source/CASUi/catalog_grid_intrinsic_methods.as',
                  'tools/cas_grid_spares.py','tools/cas_grid_spares_stage.py','tools/CasGridSparesPatch.java',
                  'Source/CASUi/catalog_spare_custody_methods.as',
                  'tools/cas_grid_position.py','tools/cas_grid_position_stage.py','tools/CasGridPositionPatch.java',
                  'Source/CASUi/catalog_native_position_gate.as',
                  'tools/cas_catalog_schedule.py','tools/cas_catalog_schedule_stage.py','tools/CasCatalogSchedulePatch.java',
                  'Source/CASUi/catalog_scheduling_methods.as',
                  'tools/cas_catalog_workflow.py','tools/cas_catalog_workflow_stage.py','tools/CasCatalogWorkflowPatch.java',
                  'Source/CASUi/catalog_workflow_methods.as',
                  'tools/cas_list_insets.py','tools/cas_list_insets_stage.py','tools/CasListInsetsPatch.java',
                  'Source/CASUi/catalog_list_inset_methods.as',
                  'tools/cas_grid_logical_bank.py','tools/cas_grid_logical_bank_stage.py','tools/CasGridLogicalBankPatch.java',
                  'Source/CASUi/catalog_logical_bank_methods.as',
                  'tools/cas_grid_frame_status.py','tools/cas_frame_status_stage.py','tools/CasGridFrameStatusPatch.java',
                  'Source/CASUi/catalog_frame_status_methods.as',
                  'tools/cas_grid_eof.py',
                  'tools/cas_grid_eof_stage.py',
                  'tools/CasGridEofPatch.java',
                  'Source/CASUi/catalog_grid_eof_methods.as',
                  'Source/CASUi/catalog_grid_authority_methods.as',
                  'tools/cas_catalog_authority.py',
                  'tools/cas_catalog_authority_stage.py',
                  'tools/CasCatalogAuthorityPatch.java',
                  'Source/CASUi/catalog_authority_methods.as',
                  'Source/CASUi/catalog_authority_consumer_methods.as',
                  'tools/cas_grid_width.py',
                  'tools/cas_grid_width_stage.py',
                  'tools/CasGridWidthPatch.java',
                  'Source/CASUi/catalog_grid_width_methods.as',
                  'Source/CASUi/catalog_grid_width_main_request.as',
                  'tools/cas_catalog_unconsumed.py',
                  'tools/cas_unconsumed_stage.py',
                  'tools/CasCatalogUnconsumedPatch.java',
                  'Source/CASUi/catalog_unconsumed_methods.as',
                  'Source/CASUi/catalog_unconsumed_consumer_methods.as',
                  'Source/CASUi/catalog_row_delta_methods.as',
                  'tools/cas_swatch_columns.py','tools/CasSwatchColumnsPatch.java','Source/CASUi/swatch_columns_methods.as',
                  'tools/cas_grid_staging_attach.py','tools/CasGridStagingAttachPatch.java','Source/CASUi/catalog_grid_staging_attach_methods.as',
                  'tools/cas_grid_publication.py','tools/cas_publication_stage.py','tools/CasPublicationTracePatch.java',
                  'Source/CASUi/catalog_publication_trace_methods.as','Source/CASUi/catalog_grid_publication_trace_emit.as',
                  'tools/cas_grid_featured.py','tools/CasGridFeaturedPatch.java','tools/CasGridFeaturedMainPatch.java',
                  'Source/CASUi/catalog_featured_identity_methods.as','Source/CASUi/catalog_featured_main_identity.as',
                  'tools/cas_grid_budget.py','tools/CasGridBudgetPatch.java','tools/CasGridBudgetMainPatch.java',
                  'Source/CASUi/catalog_grid_budget_step_methods.as','Source/CASUi/catalog_grid_budget_loop_methods.as',
                  'Source/CASUi/catalog_grid_budget_main_request.as','Source/CASUi/catalog_grid_budget_main_status.as',
                  'Source/CASUi/catalog_grid_progress_methods.as',
                  'Source/CASUi/catalog_product_grid_row_guard.as',
                  'Source/CASUi/catalog_grid_presentation_methods.as',
                  'Source/CASUi/catalog_image_readiness_methods.as',
                  'Source/CASUi/catalog_image_resource_readiness_methods.as',
                  'tools/CasCatalogBindingPatch.java', 'tools/cas_catalog_binding.py',
                  'tools/CasDrawPhasePatch.java', 'tools/cas_draw_phase.py',
                  'Source/CASUi/form_strip_methods.as',
                  'Source/CASUi/pair_controls_methods.as',
                  'Source/CASUi/catalog_workspace_methods.as',
                  'Source/CASUi/catalog_cards_methods.as','Source/CASUi/catalog_panel_geometry_methods.as',
                  'Source/CASUi/swatch_geometry_adapter_methods.as','Source/CASUi/swatch_group_geometry_adapter_methods.as',
                  'tools/cas_swatch_geometry.py','tools/CasSwatchGeometryPatch.java',
                  'tools/cas_preview_transition.py', 'tools/cas_equipped_catalog.py',
                  'Source/CASUi/catalog_grid_transaction_methods.as',
                  'Source/CASUi/catalog_grid_geometry_methods.as',
                  'Source/CASUi/equipped_category_methods.as', 'Source/CASUi/catalog_keyboard_methods.as',
                  'Source/CASUi/catalog_search_methods.as',
                  'Source/CASUi/catalog_companion_methods.as',
                  'Source/CASUi/panel_layout_methods.as',
                  'Source/CASUi/panel_input_methods.as',
                  'Source/CASUi/panel_consumer_methods.as',
                  'Source/CASUi/catalog_columns_methods.as',
                  'Source/CASUi/catalog_trace_methods.as',
                  'Source/CASUi/catalog_layout_trace_methods.as',
                  'tools/cas_catalog_workspace.py', 'tools/CasCatalogBytecodePatch.java',
                  'Source/CASUi/selector_methods.as', 'tools/CasSelectorBytecodePatch.java',
                  'tools/cas_pair_panel_patch.py',
                  'tools/cas_pelt_patch.py',
                  'tools/maru_companion.py',
                  'tools/maru_companion_adapters.py',
                  'tools/maru_companion_performance.py',
                  'tools/maru_companion_resources.json',
                  'Source/apex_core/cas_panels.py', 'Source/apex_core/cas_controls.py',
                  'tools/CasVoiceBytecodePatch.java', 'tools/CasGridBytecodePatch.java', 'tools/cas_molecule_patch.py',
                  'tools/CasMoleculeBytecodePatch.java')


def source_pins(root=ROOT):
    """Exact input bytes used by the AS compiler and retained-bytecode patcher.

    These checkout SHA-256 values intentionally differ from Git's canonical
    line-ending inventory when the bytes supplied to the compiler differ.
    """
    return {name: hashlib.sha256((Path(root) / name).read_bytes()).hexdigest()
            for name in PINNED_SOURCES}


def verify_source_pins(info, root=ROOT):
    """Reject a stale, missing or partial source contract without building.

    The bundle builder calls this before consuming the already-built package.
    Package bytes/gates must also be checked independently by that caller.
    """
    if (not isinstance(info, dict) or not isinstance(info.get('source_pins'), dict) or
            set(info['source_pins']) != set(PINNED_SOURCES) or
            info['source_pins'] != source_pins(root)):
        raise ValueError('CAS bridge source pins differ from the current semantic methods or bytecode patcher.')
    return True


def verified_library_cache(output, originals):
    """Admit only three complete, current native-library continuations.

    Main/Selector/other UI resources are never returned. Any stale, partial or
    invalid evidence discards the entire optional cache; the compiler remains
    the normal path and the final merged-package gates are unchanged.
    """
    import maru_companion
    keys = {maru_companion.CANONICAL_GRID_LIBRARY, maru_companion.GRID_LIBRARY, CLEANUP_KEY}
    try:
        if not isinstance(originals, dict) or set(originals) != keys:
            return None
        output = Path(output)
        raw = output.read_bytes()
        info = json.loads(Path(str(output) + '.manifest.json').read_text(encoding='utf-8'))
        if not isinstance(info, dict) or info.get('sha256') != dbpf_build.digest(raw):
            return None
        resources = dbpf_build.read(raw)
        selected = {key: resources[key] for key in keys}
        inputs = {key: dbpf_build.digest(Path(originals[key]).read_bytes()) for key in keys}
        providers = info.get('grid_provider_adapters')
        dependencies = info.get('communication_dependency_adapters')
        if (not isinstance(providers, dict) or not isinstance(dependencies, dict) or
                not isinstance(info.get('base_resources'), dict) or
                not isinstance(info.get('patched_resources'), dict)):
            return None
        def current_grid_stages(adapter):
            # Historical chains remain valid recovery evidence, but may not
            # bypass newly required builder stages through this early return.
            # Admit an exact current final OR the authenticated immediately
            # preceding V345 prefix; adapt_grid_provider must continue it.
            if isinstance(adapter,dict) and isinstance(adapter.get('view_width_transfer_contract'),dict):
                adapter=adapter.get('previous_stage_adapter')
                if not isinstance(adapter,dict) or not isinstance(adapter.get('eof_delta_contract'),dict):return False
            if isinstance(adapter,dict) and isinstance(adapter.get('eof_delta_contract'),dict):
                adapter=adapter.get('previous_stage_adapter')
                if not isinstance(adapter,dict) or not isinstance(adapter.get('frame_status_contract'),dict):return False
            if isinstance(adapter,dict) and isinstance(adapter.get('frame_status_contract'),dict):
                adapter=adapter.get('previous_stage_adapter')
                if not isinstance(adapter,dict) or not isinstance(adapter.get('logical_bank_contract'),dict):return False
            if isinstance(adapter,dict) and isinstance(adapter.get('logical_bank_contract'),dict):
                adapter=adapter.get('previous_stage_adapter')
                if not isinstance(adapter,dict) or not isinstance(adapter.get('native_position_contract'),dict):return False
            if isinstance(adapter,dict) and isinstance(adapter.get('native_position_contract'),dict):
                adapter=adapter.get('previous_stage_adapter')
                if not isinstance(adapter,dict) or not isinstance(adapter.get('spare_custody_contract'),dict):return False
            if isinstance(adapter,dict) and isinstance(adapter.get('spare_custody_contract'),dict):
                adapter=adapter.get('previous_stage_adapter')
                if not isinstance(adapter,dict) or not isinstance(adapter.get('intrinsic_geometry_contract'),dict):return False
            if isinstance(adapter,dict) and isinstance(adapter.get('intrinsic_geometry_contract'),dict):
                adapter=adapter.get('previous_stage_adapter')
                if not isinstance(adapter,dict) or not isinstance(adapter.get('physical_position_contract'),dict):return False
            if isinstance(adapter,dict) and isinstance(adapter.get('physical_position_contract'),dict):
                adapter=adapter.get('previous_stage_adapter')
                if not isinstance(adapter,dict) or not isinstance(adapter.get('row_delta_contract'),dict):return False
            if isinstance(adapter,dict) and isinstance(adapter.get('row_delta_contract'),dict):
                adapter=adapter.get('previous_stage_adapter')
                if not isinstance(adapter,dict) or not isinstance(adapter.get('swatch_columns_contract'),dict):return False
            if isinstance(adapter,dict) and isinstance(adapter.get('swatch_columns_contract'),dict):
                adapter=adapter.get('previous_stage_adapter')
                if not isinstance(adapter,dict) or not isinstance(adapter.get('staging_attach_contract'),dict):return False
            if isinstance(adapter,dict) and isinstance(adapter.get('staging_attach_contract'),dict):
                if adapter.get('previous_stage_kind')!='publication':return False
                adapter=adapter.get('previous_stage_adapter')
                if not isinstance(adapter,dict) or not isinstance(adapter.get('publication_trace_contract'),dict):return False
            if isinstance(adapter,dict) and isinstance(adapter.get('publication_trace_contract'),dict):
                adapter=adapter.get('previous_stage_adapter')
                if not isinstance(adapter,dict) or not isinstance(adapter.get('featured_contract'),dict):return False
            if isinstance(adapter,dict) and isinstance(adapter.get('featured_contract'),dict):
                adapter=adapter.get('previous_stage_adapter')
                if not isinstance(adapter,dict) or not isinstance(adapter.get('budget_contract'),dict):return False
            if isinstance(adapter,dict) and isinstance(adapter.get('budget_contract'),dict):
                adapter=adapter.get('previous_stage_adapter')
            for contract in ('slice_contract','scroll_contract','swatch_provider_contract','progress_contract','product_rows_contract'):
                if not isinstance(adapter,dict) or not isinstance(adapter.get(contract),dict):
                    return False
                adapter=adapter.get('previous_stage_adapter')
            return True
        if (any(not current_grid_stages(providers.get(dbpf_build.tgi(key)))
                for key in (maru_companion.CANONICAL_GRID_LIBRARY, maru_companion.GRID_LIBRARY)) or
                not isinstance(dependencies.get(dbpf_build.tgi(CLEANUP_KEY)), dict) or
                dependencies[dbpf_build.tgi(CLEANUP_KEY)].get('presentation_contract', {}).get('mode') != 'image'):
            return None
        for key in keys:
            text = dbpf_build.tgi(key)
            proof = (dependencies if key == CLEANUP_KEY else providers).get(text, {})
            if (not isinstance(proof, dict) or
                    info.get('base_resources', {}).get(text) != inputs[key] or
                    proof.get('base_resource_sha256') != inputs[key] or
                    info.get('patched_resources', {}).get(text) != dbpf_build.digest(selected[key])):
                return None
        if maru_companion.verify_grid_providers(providers, selected, dependencies) is not True:
            return None
        # Complete provider verification authenticates every nested proof. Its
        # declared build pins must also name the exact current owned sources;
        # unrelated Main source changes deliberately do not invalidate a library.
        declared = info.get('source_pins', {})
        if not isinstance(declared, dict):
            return None
        def pins_match(value):
            if isinstance(value, dict):
                pins = value.get('source_sha256')
                if pins is not None:
                    if not isinstance(pins, dict):
                        return False
                    for name, digest in pins.items():
                        if (name not in PINNED_SOURCES or declared.get(name) != digest or
                                dbpf_build.digest((ROOT / name).read_bytes()) != digest):
                            return False
                return all(pins_match(child) for child in value.values())
            return not isinstance(value, list) or all(pins_match(child) for child in value)
        if not pins_match(providers) or not pins_match(dependencies):
            return None
        return {'resources': selected, 'original_sha256': inputs,
                'providers': json.loads(json.dumps(providers)),
                'dependencies': json.loads(json.dumps(dependencies)), 'used': set()}
    except (OSError, ValueError, KeyError, TypeError, RecursionError, UnicodeError, zlib.error):
        return None


def finish_grid_provider(prior, retained, original, ffdec, work):
    """Apply only the exact ready-bank width continuation after EOF authority."""
    import cas_grid_width
    if isinstance(prior,dict) and 'view_width_transfer_contract' in prior:
        cas_grid_width.verify_adapter(prior,retained)
        return retained,prior
    retained,prior=_finish_grid_provider_eof(prior,retained,original,ffdec,work)
    return cas_grid_width.adapt(prior,retained,original,ffdec,Path(work)/'view-width-transfer')


def _finish_grid_provider_eof(prior, retained, original, ffdec, work):
    """Keep native EOF slots and typed authority fences after complete frame APIs."""
    import cas_grid_eof
    if isinstance(prior,dict) and 'eof_delta_contract' in prior:
        cas_grid_eof.verify_adapter(prior,retained)
        return retained,prior
    retained,prior=_finish_grid_provider_frame_status(prior,retained,original,ffdec,work)
    return cas_grid_eof.adapt(prior,retained,original,ffdec,Path(work)/'eof-delta')


def _finish_grid_provider_frame_status(prior, retained, original, ffdec, work):
    """Continue exact authenticated providers through the complete frame API."""
    import cas_grid_frame_status
    if isinstance(prior,dict) and 'frame_status_contract' in prior:
        cas_grid_frame_status.verify_adapter(prior,retained)
        return retained,prior
    retained,prior=_finish_grid_provider_logical_bank(prior,retained,original,ffdec,work)
    return cas_grid_frame_status.adapt(prior,retained,original,ffdec,Path(work)/'frame-status')


def _finish_grid_provider_logical_bank(prior, retained, original, ffdec, work):
    """Keep the complete ready logical window before adding frame APIs."""
    import cas_grid_logical_bank
    if isinstance(prior,dict) and 'logical_bank_contract' in prior:
        cas_grid_logical_bank.verify_adapter(prior,retained)
        return retained,prior
    retained,prior=_finish_grid_provider_position(prior,retained,original,ffdec,work)
    return cas_grid_logical_bank.adapt(prior,retained,original,ffdec,Path(work)/'logical-bank')


def _finish_grid_provider_position(prior, retained, original, ffdec, work):
    """Continue through the native subclass position-tail repair."""
    import cas_grid_position
    if isinstance(prior,dict) and 'native_position_contract' in prior:
        cas_grid_position.verify_adapter(prior,retained)
        return retained,prior
    retained,prior=_finish_grid_provider_spares(prior,retained,original,ffdec,work)
    return cas_grid_position.adapt(prior,retained,original,ffdec,Path(work)/'native-position')


def _finish_grid_provider_spares(prior, retained, original, ffdec, work):
    """Continue authenticated prefixes through the complete spare-custody terminal."""
    import cas_grid_spares
    if isinstance(prior,dict) and 'spare_custody_contract' in prior:
        cas_grid_spares.verify_adapter(prior,retained)
        return retained,prior
    retained,prior=_finish_grid_provider_intrinsic(prior,retained,original,ffdec,work)
    return cas_grid_spares.adapt(prior,retained,original,ffdec,Path(work)/'spare-custody')


def _finish_grid_provider_intrinsic(prior, retained, original, ffdec, work):
    """Continue only authenticated prefixes through the complete intrinsic terminal."""
    import cas_grid_intrinsic
    if isinstance(prior,dict) and 'intrinsic_geometry_contract' in prior:
        cas_grid_intrinsic.verify_adapter(prior,retained)
        return retained,prior
    retained,prior=_finish_grid_provider_physical(prior,retained,original,ffdec,work)
    return cas_grid_intrinsic.adapt(prior,retained,original,ffdec,Path(work)/'intrinsic-geometry')


def _finish_grid_provider_physical(prior, retained, original, ffdec, work):
    """Continue every missing authenticated terminal stage; no prefix early return."""
    import cas_grid_physical
    import cas_grid_row_delta
    import cas_swatch_columns
    import cas_grid_staging_attach
    import cas_grid_publication
    import cas_grid_featured
    import cas_grid_budget
    import cas_grid_slice
    work=Path(work)
    if isinstance(prior,dict) and 'physical_position_contract' in prior:
        cas_grid_physical.verify_adapter(prior,retained)
        return retained,prior
    if isinstance(prior,dict) and 'row_delta_contract' in prior:
        cas_grid_row_delta.verify_adapter(prior,retained)
        return cas_grid_physical.adapt(prior,retained,original,ffdec,work/'physical-position')
    if isinstance(prior,dict) and 'swatch_columns_contract' in prior:
        cas_swatch_columns.verify_adapter(prior,retained)
        if prior['swatch_columns_contract'].get('previous_stage_kind')!='staging-attach':
            raise ValueError('Historical Skin fixture is not a current build capability.')
        retained,prior=cas_grid_row_delta.adapt(prior,retained,original,ffdec,work/'row-delta')
        return cas_grid_physical.adapt(prior,retained,original,ffdec,work/'physical-position')
    if isinstance(prior,dict) and 'staging_attach_contract' in prior:
        if prior.get('previous_stage_kind')!='publication':raise ValueError('Production Attach requires Publication predecessor')
        cas_grid_staging_attach.verify_adapter(prior,retained)
    else:
        if isinstance(prior,dict) and 'publication_trace_contract' in prior:
            cas_grid_publication.verify_adapter(prior,retained)
        else:
            if isinstance(prior,dict) and 'featured_contract' in prior:
                cas_grid_featured.verify_adapter(prior,retained)
            else:
                if isinstance(prior,dict) and 'budget_contract' in prior:
                    cas_grid_budget.verify_adapter(prior,retained)
                else:
                    cas_grid_slice.verify_adapter(prior,retained)
                    retained,prior=cas_grid_budget.adapt(prior,retained,original,ffdec,work/'budget')
                retained,prior=cas_grid_featured.adapt(prior,retained,original,ffdec,work/'featured')
            retained,prior=cas_grid_publication.adapt(prior,retained,original,ffdec,work/'publication')
        retained,prior=cas_grid_staging_attach.adapt(prior,retained,original,ffdec,work/'staging-attach')
    retained,prior=cas_swatch_columns.adapt(prior,retained,original,ffdec,work/'swatch-columns')
    retained,prior=cas_grid_row_delta.adapt(prior,retained,original,ffdec,work/'row-delta')
    return cas_grid_physical.adapt(prior,retained,original,ffdec,work/'physical-position')


def adapt_dependency_provider(cleanup_library, ffdec, work, cache=None):
    """Reuse a verified communication dependency or run its complete compiler."""
    if cache is not None:
        actual = dbpf_build.digest(Path(cleanup_library).read_bytes())
        if actual != CLEANUP_PIN or actual != cache['original_sha256'][CLEANUP_KEY]:
            raise ValueError('Cleanup library differs from its authenticated native resource.')
        cache['used'].add(dbpf_build.tgi(CLEANUP_KEY))
        return cache['resources'][CLEANUP_KEY], cache['dependencies'][dbpf_build.tgi(CLEANUP_KEY)]
    import cas_communication_dependency
    dependency_abc, dependency_contract = cas_communication_dependency.adapt(cleanup_library, ffdec,
        work / 'native-communication-dependency')
    dependency_original = Path(cleanup_library).read_bytes()
    dependency_tag = next(t[3] for t in tags(unpack(dependency_original)[1]) if t[0] == 82)
    dependency_boundary = dependency_tag.index(b'\0', 4) + 1
    dependency_payload = replace_payload(dependency_original, dependency_tag[:dependency_boundary] + dependency_abc)
    dependency_adapter = cas_communication_dependency.chain_adapter(dependency_contract, dependency_payload)
    import cas_communication_domain_probe
    dependency_baseline = work / 'dependency-domain-baseline.swf'
    dependency_baseline.write_bytes(dependency_payload)
    domain_abc, domain_contract = cas_communication_domain_probe.adapt(dependency_baseline,
        ffdec, work / 'dependency-domain')
    dependency_payload = replace_payload(dependency_payload, dependency_tag[:dependency_boundary] + domain_abc)
    dependency_adapter = cas_communication_domain_probe.chain_adapter(dependency_adapter, domain_contract, dependency_payload)
    import cas_communication_removal_miss
    dependency_removal_baseline = work / 'dependency-removal-baseline.swf'
    dependency_removal_baseline.write_bytes(dependency_payload)
    removal_abc, removal_contract = cas_communication_removal_miss.adapt(cleanup_library, dependency_removal_baseline,
        ffdec, work / 'dependency-removal')
    dependency_payload = replace_payload(dependency_payload, dependency_tag[:dependency_boundary] + removal_abc)
    dependency_adapter = cas_communication_removal_miss.chain_adapter(dependency_adapter, removal_contract, dependency_payload)
    import cas_image_boundary_profile
    dependency_image_baseline = work / 'dependency-image-baseline.swf'
    dependency_image_baseline.write_bytes(dependency_payload)
    image_abc, image_contract = cas_image_boundary_profile.adapt(cleanup_library, dependency_image_baseline,
        ffdec, work / 'dependency-image')
    dependency_payload = replace_payload(dependency_payload, dependency_tag[:dependency_boundary] + image_abc)
    dependency_adapter = cas_image_boundary_profile.chain_adapter(dependency_adapter, image_contract, dependency_payload)
    import cas_grid_presentation
    return cas_grid_presentation.adapt(dependency_adapter, dependency_payload, cleanup_library,
        ffdec, work / 'dependency-presentation')


def verify_control_dispatch(methods):
    """Every advertised typed control must reach its next-tick readback.

    Missing result dispatch was observed in v21: native success was rejected
    by Python and left the query pending. Check the complete public registry,
    rather than a smaller hand-maintained list of the controls being tested.
    """
    sys.path.insert(0, str(ROOT / 'Source'))
    from apex_core import cas_controls
    readback = methods.split('private function ApexReadback()', 1)[1].split('private function ApexComplete()', 1)[0]
    dispatch = readback.split('reply.client=ApexSnapshot();', 1)[1].split('reply.client.control=ApexControlResult', 1)[0]
    routed = set(re.findall(r'operation=="([a-z-]+)"', dispatch))
    if routed != set(cas_controls.OPERATIONS):
        raise ValueError('Native typed CAS result dispatch differs from the complete public control registry: ' +
                         ', '.join(sorted(routed ^ set(cas_controls.OPERATIONS))))
    execution = methods.split('private function ApexControlExecute(', 1)[1].split('private function ApexControlResult(', 1)[0]
    implemented = set(re.findall(r'operation(?:==|!=)"([a-z-]+)"', execution))
    if implemented != set(cas_controls.OPERATIONS):
        raise ValueError('Native typed CAS execution differs from the complete public control registry.')
    return sorted(routed)


def verify_snapshot_ownership(methods):
    """Do not retain borrowed native getter records across snapshot calls."""
    snapshot = methods.split('private function ApexSnapshot(', 1)[1].split('private function ApexClone(', 1)[0]
    calls = list(re.finditer(r'CommunicationManager\.CallGameService\(', snapshot))
    if not calls or any(not snapshot[:call.start()].endswith('ApexClone(') for call in calls):
        raise ValueError('Native CAS inventory retains a getter result without immediate detachment.')
    return len(calls)


def verify_household_acceptance(methods):
    body=methods.split('private function ApexAccept()',1)[1]
    steps=('apexPendingFields=null; apexPendingReply=null; apexPendingContext=null;',
      'if(int(editMode)==0)', 'CallUIService("IsWidgetVisible","CASGeneticsPane")',
      'CallUIService("CasApplyNameFields",false)',
      'CallGameService("CasGetHouseholdExchangeData",{bValidateExistingSimTraits:false})',
      'validatedHousehold.HouseholdContainsAdults()',
      'CallGameService("CASCheckProfanityOnSimNames",null)',
      'reply.household_finalization_verified=true;',
      'apexAcceptWait={id:id,simId:simId,owner:owner,household:expectedHousehold',
      'apexPendingPhase=9;ApexAcceptListen(true);',
      'ApexAcceptNative(apexAcceptWait,"PREPARE")',
      'if(!ApexAcceptReady(apexAcceptWait)) return;',
      'ApexAcceptListen(false);apexAcceptWait=null;apexAcceptInput=false;',
      'apexPendingPhase=7;', 'reply.readiness_verified=true;', 'reply.commit_attempted=true;',
      'CallGameService("SaveAndExitCAS",{bValidateExistingSimTraits:false,apex_accept_id:id,apex_accept_nonce:owner})')
    try:positions=[body.index(s,0 if s!='apexPendingPhase=7;' else body.index('if(!ApexAcceptReady(apexAcceptWait)) return;')) for s in steps]
    except ValueError as error:raise ValueError('Native acceptance finalization/readiness contract is incomplete.') from error
    if positions!=sorted(positions) or body.count('CallGameService("SaveAndExitCAS",')!=1 or body.count('ApexAcceptNative(apexAcceptWait,"PREPARE")')!=1:
        raise ValueError('Native acceptance must retain one prepare and at most one original typed commit.')
    ready=methods.split('private function ApexAcceptReady(',1)[1].split('private function ApexAccept()',1)[0]
    native=methods.split('private function ApexAcceptNative(',1)[1].split('private function ApexAcceptReady(',1)[0]
    for required in ('elapsed<0 || elapsed>10000','if(apexAcceptInput)','apexNonce!==held.owner','this.stage!==apexAcceptStage',
       'fresh.occultLayer===0','currentMode!==held.mode','currentNewFamily!==false','!currentFromLive',
       'CASStateData.TattooMode!==false','currentOwner!==expectedOwner','ApexAcceptNative(held,"READY")'):
        if required not in ready:raise ValueError('Acceptance ready fence missing: '+required)
    for required in ('fields.length!=18','fields[2]!==held.simId','fields[3]!==held.household','fields[17]!=="1"',
       'stamp!==held.stamp','fields[15]===ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â©ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â°ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬"0"'.replace('ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â©ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â°ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬',''),'fields[16]===ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â©ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â°ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬"0"'.replace('ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â©ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â°ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬','')):
        if required not in native:raise ValueError('Acceptance native receipt guard missing: '+required)
    if re.search(r'CASStateData\.TattooMode\s*=(?!=)',body):raise ValueError('Acceptance cannot force a preview flag.')
    if 'if(apexPendingPhase==9) { ApexAccept();return; }' not in methods:
        raise ValueError('Owned Timer must service an outstanding readiness continuation.')
    if 'APEXACCEPT1|CANCEL|' not in methods or 'ApexAcceptReadyFrame' not in methods:
        raise ValueError('Readiness must detach/cancel its exact original continuation.')
    return True

def unpack(raw):
    if raw[:3] not in (b'FWS', b'CWS', b'GFX', b'CFX') or len(raw) < 12:
        raise ValueError('Unsupported SWF header.')
    body = raw[8:] if raw[:3] in (b'FWS', b'GFX') else zlib.decompress(raw[8:])
    if len(body) + 8 != struct.unpack_from('<I', raw, 4)[0]:
        raise ValueError('SWF size mismatch.')
    return raw[3], body


def tags(body):
    bits = body[0] >> 3
    pos = (5 + bits * 4 + 7) // 8 + 4
    while pos < len(body):
        start = pos
        code = struct.unpack_from('<H', body, pos)[0]; pos += 2
        kind, size = code >> 6, code & 63
        if size == 63:
            size = struct.unpack_from('<I', body, pos)[0]; pos += 4
        end = pos + size
        if end > len(body): raise ValueError('Truncated SWF tag.')
        yield kind, start, end, body[pos:end]
        pos = end
        if kind == 0:
            if pos != len(body): raise ValueError('Trailing SWF data.')
            break


def replace_abc(original, compiled):
    version, source = unpack(original)
    _, result = unpack(compiled)
    old = [t for t in tags(source) if t[0] == 82]
    new = [t for t in tags(result) if t[0] == 82]
    if len(old) != 1 or len(new) != 1:
        raise ValueError('Exactly one original and compiled DoABC tag is required.')
    return replace_payload(original, new[0][3])


def replace_payload(original, payload):
    version, source = unpack(original)
    old = [t for t in tags(source) if t[0] == 82]
    if len(old) != 1: raise ValueError('Exactly one native DoABC tag is required.')
    replacement = struct.pack('<HI', (82 << 6) | 63, len(payload)) + payload
    body = source[:old[0][1]] + replacement + source[old[0][2]:]
    # Verify everything outside that tag independently before writing.
    prior = [t[3] for t in tags(source) if t[0] != 82]
    after = [t[3] for t in tags(body) if t[0] != 82]
    if prior != after: raise ValueError('Non-script SWF content changed.')
    return (b'GFX' if original[:3] in (b'GFX', b'CFX') else b'FWS') + bytes([version]) + struct.pack('<I', len(body) + 8) + body


def inject(source, methods):
    sys.path.insert(0, str(ROOT / 'Source'))
    from apex_core.cas_panels import PANELS
    methods = methods.replace('__APEX_PANEL_STATES__', json.dumps(PANELS, sort_keys=True, separators=(',', ':')))
    anchor = 'AddMessageListener("CASContextMenuSetMenuState",this.HandleContextMenuSetMenuState);'
    if source.count(anchor) != 1 or 'ApexInitialize' in source:
        raise ValueError('Installed CAS initializer does not match the inspected contract.')
    source = source.replace(anchor, anchor + '\n         ApexInitialize();')
    # Resolve external QNames at compilation, avoiding dotted runtime lookups.
    source = source.replace('   import gamedata.CAS.CASAPI;',
        '   import olympus.events.GridEvent;\n   import olympus.events.DataFeedEvent;\n   import olympus.events.ScrollerEvent;\n   import olympus.events.PushButtonEvent;\n   import gamedata.shared.SimGenderTypes;\n   import gamedata.CAS.shared.CASCatalogProduct;\n   import olympus.layout.SelectableRecyclingGridLayout;\n   import widgets.CAS.controls.CASBodyPanelCellView;\n   import widgets.CAS.controls.CASFacePanelCellView;\n   import widgets.CAS.controls.CASGenericCatalogVariantCellView;\n   import widgets.CAS.controls.CASBreedCatalogCellView;\n   import gamedata.CAS.CASAPI;')
    source = source.replace('   import ', '   import CasCustomizer.IconComponentResource;\n   import olympus.core.widget.Margin;\n   import olympus.core.tooltip.TooltipObject;\n   import flash.utils.describeType;\n   import flash.utils.getTimer;\n   import flash.utils.getDefinitionByName;\n   import gamedata.shared.TattooBodyData;\n   import gamedata.CAS.shared.CASCatalogFilter;\n   import gamedata.Exchange.ExchangeData;\n   import ', 1)
    source = re.sub(r'\s*\[Embed\([^\n]*\)\]', '', source)
    end = source.rfind('   }')
    if end < 0: raise ValueError('CAS class end is missing.')
    return source[:end] + methods + '\n' + source[end:]


def inject_selector(source, methods):
    if (source.count('override public function Initialize() : void') != 1 or
            source.count('protected function HandleRefreshSimIcons(param1:SkewerData) : void') != 1 or
            'ApexSelectorInitialize' in source):
        raise ValueError('Installed selector class does not match the inspected contract.')
    source = re.sub(r'\s*\[Embed\([^\n]*\)\]', '', source)
    end = source.rfind('   }')
    if end < 0:
        raise ValueError('Selector class end is missing.')
    # Compiler output supplies only owned methods. The bytecode adapter alone
    # inserts the initializer and raw-handler hooks into native bytecode.
    return source[:end] + methods + '\n' + source[end:]


def run(args):
    proc = subprocess.run([str(x) for x in args], text=True, encoding='utf-8',
                          errors='replace', capture_output=True, timeout=120)
    if proc.returncode: raise ValueError(proc.stdout[-1500:] + proc.stderr[-1500:])
    return proc


def build(input_swf, decompiled, ffdec, output, selector_swf=None, selector_decompiled=None, cleanup_library=None, voice_swf=None,
          companion_package=None):
    expected_sources = source_pins()
    semantic = (ROOT / 'Source/CASUi/semantic_methods.as').read_text(encoding='utf-8')
    semantic += '\n' + (ROOT / 'Source/CASUi/form_strip_methods.as').read_text(encoding='utf-8')
    semantic += '\n' + (ROOT / 'Source/CASUi/pair_controls_methods.as').read_text(encoding='utf-8')
    import cas_catalog_workspace
    semantic += '\n' + (ROOT / 'Source/CASUi/catalog_workspace_methods.as').read_text(encoding='utf-8').replace(
        '__APEX_EQUIPPED_MENUS__',json.dumps(cas_catalog_workspace.equipped_menus(),sort_keys=True,separators=(',', ':')))
    semantic += '\n' + (ROOT / 'Source/CASUi/catalog_cards_methods.as').read_text(encoding='utf-8')
    semantic += '\n' + (ROOT / 'Source/CASUi/catalog_panel_geometry_methods.as').read_text(encoding='utf-8')
    semantic += '\n' + (ROOT / 'Source/CASUi/catalog_grid_transaction_methods.as').read_text(encoding='utf-8')
    semantic += '\n' + (ROOT / 'Source/CASUi/catalog_grid_geometry_methods.as').read_text(encoding='utf-8')
    semantic += '\n' + (ROOT / 'Source/CASUi/equipped_category_methods.as').read_text(encoding='utf-8')
    semantic += '\n' + (ROOT / 'Source/CASUi/catalog_keyboard_methods.as').read_text(encoding='utf-8')
    semantic += '\n' + (ROOT / 'Source/CASUi/catalog_search_methods.as').read_text(encoding='utf-8')
    semantic += '\n' + (ROOT / 'Source/CASUi/catalog_companion_methods.as').read_text(encoding='utf-8')
    semantic += '\n' + (ROOT / 'Source/CASUi/panel_layout_methods.as').read_text(encoding='utf-8')
    semantic += '\n' + (ROOT / 'Source/CASUi/panel_input_methods.as').read_text(encoding='utf-8')
    semantic += '\n' + (ROOT / 'Source/CASUi/panel_consumer_methods.as').read_text(encoding='utf-8')
    semantic += '\n' + (ROOT / 'Source/CASUi/catalog_columns_methods.as').read_text(encoding='utf-8')
    semantic += '\n' + (ROOT / 'Source/CASUi/catalog_trace_methods.as').read_text(encoding='utf-8')
    semantic += '\n' + (ROOT / 'Source/CASUi/catalog_layout_trace_methods.as').read_text(encoding='utf-8')
    control_dispatch = verify_control_dispatch(semantic)
    detached_snapshot_getters = verify_snapshot_ownership(semantic)
    household_acceptance = verify_household_acceptance(semantic)
    original = Path(input_swf).read_bytes()
    if hashlib.sha256(original).hexdigest() != PIN:
        raise ValueError("Installed CAS resource differs from the inspected 1.128.90 build.")
    work = ROOT / '.work' / 'research'
    companion = None
    customizer_sources = work / 'current-cas/scripts/scripts'
    if companion_package is not None:
        # Compile against the actual donor ABC, including its helper classes,
        # closures, account preferences and drawer assets. The retained-bytecode
        # pass below still preserves every method outside the reviewed adapters.
        import maru_companion
        companion = maru_companion.prepare(companion_package, ffdec, work / 'maru-integrated')
        input_swf = Path(companion['customizer'])
        # The compiler supplies Apex methods only. Retain the donor's main
        # methods verbatim in the ABC pass; do not recompile its source-only
        # protected-access shortcuts (which FFDec correctly rejects).
        customizer_sources = Path(companion['scripts'])
        original = input_swf.read_bytes()
    selector_swf = Path(selector_swf or work / 'cas-hair-cassimselector-current.swf')
    selector_decompiled = Path(selector_decompiled or work / 'cas-hair-cassimselector-current/scripts/widgets/CAS/SimSelector/CASSimSelectorMain.as')
    original_selector = selector_swf.read_bytes()
    if hashlib.sha256(original_selector).hexdigest() != SELECTOR_PIN:
        raise ValueError('Installed selector resource differs from the inspected 1.128.90 build.')
    cleanup_library = Path(cleanup_library or work / 'OlympusLibrary.swf')
    if hashlib.sha256(cleanup_library.read_bytes()).hexdigest() != CLEANUP_PIN:
        raise ValueError('Installed cleanup library differs from the inspected native widget contract.')
    library_cache = verified_library_cache(output, {
        maru_companion.CANONICAL_GRID_LIBRARY: work / 'ClassLibraryGamedata.swf',
        maru_companion.GRID_LIBRARY: companion['grid_library'], CLEANUP_KEY: cleanup_library}) if companion is not None else None
    patched = work / 'ApexCASCustomizerMain.as'
    patched.write_text(inject(Path(decompiled).read_text(encoding='utf-8'),
        semantic), encoding='utf-8')
    compiled = work / 'apex-cas-compiled.swf'
    run([ffdec, '-importAssets', 'yes,local', '-replace', input_swf, compiled, CLASS, patched])
    import cas_equipped_catalog
    cell_source = work / 'current-cas/scripts/scripts/widgets/CAS/controls/CASClothingPanelCellViewMain.as'
    cell_owned = work / 'ApexCASClothingPanelCellViewMain.as'
    cell_owned.write_text(cas_equipped_catalog.inject_cell(cell_source.read_text(encoding='utf-8')),encoding='utf-8')
    cards_compiled = work / 'apex-cas-cards-compiled.swf'
    run([ffdec,'-importAssets','yes,local','-replace',compiled,cards_compiled,cas_equipped_catalog.CELL_CLASS,cell_owned])
    compiled = cards_compiled
    for kind, relative, inject_method in (
        ('clothing','Customizer/ClothingPanel.as',cas_equipped_catalog.inject_clothing),
        ('feed','data/CatalogDataFeed.as',cas_equipped_catalog.inject_feed)):
        native_source=customizer_sources / ('widgets/CAS/'+relative)
        owned_source=work / ('ApexCAS-'+kind+'.as')
        owned_source.write_text(inject_method(native_source.read_text(encoding='utf-8')),encoding='utf-8')
        next_compiled=work / ('apex-cas-'+kind+'-compiled.swf')
        class_name=cas_equipped_catalog.CLOTHING_CLASS if kind=='clothing' else cas_equipped_catalog.FEED_CLASS
        run([ffdec,'-importAssets','yes,local','-replace',compiled,next_compiled,class_name,owned_source])
        compiled=next_compiled
    import cas_pelt_patch
    for kind, type_name, button in (('pane', cas_pelt_patch.PANE, False), ('button', cas_pelt_patch.BUTTON, True)):
        native_source=customizer_sources / (type_name.replace('.', '/')+'.as')
        owned_source=work / ('ApexCAS-pelt-'+kind+'.as')
        owned_source.write_text(cas_pelt_patch.inject(native_source.read_text(encoding='utf-8'), button),encoding='utf-8')
        next_compiled=work / ('apex-cas-pelt-'+kind+'-compiled.swf')
        run([ffdec,'-importAssets','yes,local','-replace',compiled,next_compiled,type_name,owned_source])
        compiled=next_compiled
    if companion is not None:
        import maru_companion_adapters
        import maru_companion_performance
        for sequence, name in enumerate(maru_companion_adapters.ROUTES):
            stub = work / ('apex-companion-context-' + str(sequence) + '.as')
            stub.write_text(maru_companion_adapters.source(name), encoding='utf-8')
            destination = work / ('apex-companion-context-' + str(sequence) + '.swf')
            run([ffdec, '-importAssets', 'yes,local', '-replace', compiled, destination, name, stub])
            compiled = destination
        name = maru_companion_performance.PREFERENCES
        donor_source = customizer_sources / (name.replace('.', '/') + '.as')
        stub = work / 'apex-companion-favorite-lookup.as'
        stub.write_text(maru_companion_performance.preferences(donor_source.read_text(encoding='utf-8')), encoding='utf-8')
        destination = work / 'apex-companion-favorite-lookup.swf'
        run([ffdec, '-importAssets', 'yes,local', '-replace', compiled, destination, name, stub])
        compiled = destination
        for sequence, name in enumerate(maru_companion_performance.ROUTES):
            donor_source = customizer_sources / (name.replace('.', '/') + '.as')
            stub = work / ('apex-companion-lazy-swatches-' + str(sequence) + '.as')
            stub.write_text(maru_companion_performance.inject(name, donor_source.read_text(encoding='utf-8')), encoding='utf-8')
            destination = work / ('apex-companion-lazy-swatches-' + str(sequence) + '.swf')
            run([ffdec, '-importAssets', 'yes,local', '-replace', compiled, destination, name, stub])
            compiled = destination
    # The general AS compiler changes native methods' lexical scope. It is
    # used only to obtain Apex methods; original game bytecode stays intact.
    retained = work / 'apex-cas-retained.abc'
    verification = run(['java', '-cp', Path(ffdec).parent / 'ffdec.jar', ROOT / 'tools/CasBytecodePatch.java', input_swf, compiled, retained])
    contract = json.loads(verification.stdout)
    native_tag = next(t[3] for t in tags(unpack(original)[1]) if t[0] == 82)
    boundary = native_tag.index(b'\0', 4) + 1
    payload = replace_payload(original, native_tag[:boundary] + retained.read_bytes())
    structural_roles_contract = None
    draw_fast_path_contract = None
    cell_attach_contract = None
    catalog_binding_contract = None
    draw_phase_contract = None
    swatch_geometry_contract = None
    preview_transition_contract = None
    scroll_main_contract = None
    budget_main_contract = None
    featured_main_contract = None
    publication_main_contract = None
    swatch_columns_main_contract = None
    row_delta_main_contract = None
    intrinsic_geometry_main_contract = None
    catalog_schedule_main_contract = None
    catalog_workflow_main_contract = None
    catalog_list_insets_main_contract = None
    frame_status_main_contract = None
    catalog_authority_main_contract = None
    view_width_transfer_main_contract = None
    catalog_unconsumed_main_contract = None
    if companion is not None:
        import cas_structural_roles
        role_abc, role_proof = cas_structural_roles.adapt(input_swf, payload,
            customizer_sources, ffdec, work / 'structural-roles')
        payload = replace_payload(payload, native_tag[:boundary] + role_abc)
        structural_roles_contract = cas_structural_roles.chain_contract(contract, role_proof, payload)
        import cas_draw_fast_path
        draw_abc, draw_proof = cas_draw_fast_path.adapt(contract, structural_roles_contract,
            payload, Path(ffdec).with_name('ffdec.jar'), work / 'draw-fast-path')
        payload = replace_payload(payload, native_tag[:boundary] + draw_abc)
        draw_fast_path_contract = cas_draw_fast_path.chain_contract(contract, structural_roles_contract,
            draw_proof, payload)
        import cas_cell_attach
        attach_abc, attach_proof = cas_cell_attach.adapt(input_swf, contract, structural_roles_contract,
            draw_fast_path_contract, payload, Path(ffdec).with_name('ffdec.jar'), work / 'cell-attach')
        payload = replace_payload(payload, native_tag[:boundary] + attach_abc)
        cell_attach_contract = cas_cell_attach.chain_contract(contract, structural_roles_contract,
            draw_fast_path_contract, attach_proof, payload)
        import cas_catalog_binding
        payload, binding_proof = cas_catalog_binding.adapt(cell_attach_contract, payload,
            decompiled, ffdec, work / 'catalog-binding')
        catalog_binding_contract = cas_catalog_binding.chain_contract(cell_attach_contract,
            binding_proof, payload)
        import cas_draw_phase
        payload, phase_proof = cas_draw_phase.adapt(catalog_binding_contract, payload,
            decompiled, ffdec, work / 'draw-phases')
        draw_phase_contract = cas_draw_phase.chain_contract(catalog_binding_contract,
            phase_proof, payload)
        import cas_swatch_geometry
        payload, swatch_proof = cas_swatch_geometry.adapt(draw_phase_contract, payload,
            input_swf, customizer_sources, ffdec, work / 'swatch-geometry')
        swatch_geometry_contract = cas_swatch_geometry.chain_contract(draw_phase_contract,
            swatch_proof, payload)
        import cas_preview_transition
        payload, preview_proof = cas_preview_transition.adapt(swatch_geometry_contract, payload)
        preview_transition_contract = cas_preview_transition.chain_contract(swatch_geometry_contract,
            preview_proof, payload)
        import cas_grid_scroll
        payload, scroll_main_contract = cas_grid_scroll.adapt_main(preview_transition_contract, payload,
            patched, ffdec, work / 'grid-scroll-main')
        import cas_grid_budget
        payload, budget_main_contract = cas_grid_budget.adapt_main(scroll_main_contract, payload,
            patched, ffdec, work / 'grid-budget-main')
        import cas_grid_featured
        payload, featured_main_contract = cas_grid_featured.adapt_main(budget_main_contract, payload,
            patched, ffdec, work / 'grid-featured-main')
        import cas_grid_publication
        payload, publication_main_contract = cas_grid_publication.adapt_main(featured_main_contract, payload,
            patched, ffdec, work / 'grid-publication-main')
        import cas_swatch_columns
        payload, swatch_columns_main_contract = cas_swatch_columns.adapt_main(publication_main_contract, payload,
            input_swf, ffdec, work / 'swatch-columns-main')
        import cas_grid_row_delta
        payload, row_delta_main_contract = cas_grid_row_delta.adapt_main(swatch_columns_main_contract, payload,
            patched, ffdec, work / 'grid-row-delta-main')
        import cas_grid_intrinsic
        payload, intrinsic_geometry_main_contract = cas_grid_intrinsic.adapt_main(row_delta_main_contract, payload,
            patched, ffdec, work / 'grid-intrinsic-main')
        import cas_catalog_schedule
        payload, catalog_schedule_main_contract = cas_catalog_schedule.adapt_main(intrinsic_geometry_main_contract, payload,
            patched, ffdec, work / 'catalog-schedule-main')
        import cas_catalog_workflow
        payload, catalog_workflow_main_contract = cas_catalog_workflow.adapt_main(catalog_schedule_main_contract, payload,
            patched, ffdec, work / 'catalog-workflow-main')
        import cas_list_insets
        payload, catalog_list_insets_main_contract = cas_list_insets.adapt_main(catalog_workflow_main_contract, payload,
            patched, ffdec, work / 'catalog-list-insets-main')
        import cas_grid_frame_status
        payload, frame_status_main_contract = cas_grid_frame_status.adapt_main(catalog_list_insets_main_contract, payload,
            patched, ffdec, work / 'grid-frame-status-main')
        import cas_catalog_authority
        payload, catalog_authority_main_contract = cas_catalog_authority.adapt_main(frame_status_main_contract, payload,
            patched, ffdec, work / 'catalog-authority-main')
        import cas_grid_width
        payload, view_width_transfer_main_contract = cas_grid_width.adapt_main(catalog_authority_main_contract, payload,
            patched, ffdec, work / 'view-width-transfer-main')
        import cas_catalog_unconsumed
        payload, catalog_unconsumed_main_contract = cas_catalog_unconsumed.adapt_main(view_width_transfer_main_contract, payload,
            patched, ffdec, work / 'catalog-unconsumed-main')
    selector_source = work / 'ApexCASSelectorMain.as'
    selector_source.write_text(inject_selector(selector_decompiled.read_text(encoding='utf-8'),
        (ROOT / 'Source/CASUi/selector_methods.as').read_text(encoding='utf-8')), encoding='utf-8')
    selector_compiled = work / 'apex-cas-selector-compiled.swf'
    run([ffdec, '-importAssets', 'yes,local', '-replace', selector_swf, selector_compiled, SELECTOR_CLASS, selector_source])
    import cas_pair_panel_patch
    pair_source = work / 'ApexCASPairPanel.as'
    pair_native = selector_decompiled.parent / 'CASSimSelectorCopyOptionPanel.as'
    pair_source.write_text(cas_pair_panel_patch.inject(pair_native.read_text(encoding='utf-8')), encoding='utf-8')
    pair_compiled = work / 'apex-cas-pair-panel-compiled.swf'
    run([ffdec, '-importAssets', 'yes,local', '-replace', selector_compiled, pair_compiled,
         cas_pair_panel_patch.CLASS, pair_source])
    selector_compiled = pair_compiled
    cell_native = selector_decompiled.parent.parent / 'controls/CASSimSelectorCellView.as'
    cell_source = work / 'ApexCASSimSelectorCellView.as'
    cell_text = re.sub(r'\s*\[Embed\([^\n]*\)\]', '', cell_native.read_text(encoding='utf-8'))
    cell_anchor = '         var _loc9_:String = "";'
    if cell_text.count(cell_anchor) != 1:
        raise ValueError('Native portrait tooltip anchor differs from inspected build.')
    cell_text = cell_text.replace(cell_anchor, '''         // A restored hybrid pair has independently named portraits. Preserve
         // EA's disabled/affordability tooltip and relationship content.
         if(_loc2_.enabled && _loc3_ && _loc3_.alternativeTooltipText)
            _loc5_ = _loc3_.alternativeTooltipText;
''' + cell_anchor)
    cell_source.write_text(cell_text, encoding='utf-8')
    cell_compiled = work / 'apex-cas-selector-cell-compiled.swf'
    run([ffdec, '-importAssets', 'yes,local', '-replace', selector_compiled, cell_compiled,
         'widgets.CAS.controls.CASSimSelectorCellView', cell_source])
    selector_compiled = cell_compiled
    java_classes = work / 'cas-build-java'
    java_classes.mkdir(parents=True, exist_ok=True)
    run(['javac', '-cp', Path(ffdec).parent / 'ffdec.jar', '-d', java_classes,
         ROOT / 'tools/CasBytecodePatch.java', ROOT / 'tools/CasSelectorBytecodePatch.java'])
    selector_retained = work / 'apex-cas-selector-retained.abc'
    selector_verification = run(['java', '-cp', str(Path(ffdec).parent / 'ffdec.jar') + os.pathsep + str(java_classes),
        'CasSelectorBytecodePatch', selector_swf, selector_compiled, selector_retained, cleanup_library])
    selector_contract = json.loads(selector_verification.stdout)
    selector_tag = next(t[3] for t in tags(unpack(original_selector)[1]) if t[0] == 82)
    selector_boundary = selector_tag.index(b'\0', 4) + 1
    selector_payload = replace_payload(original_selector, selector_tag[:selector_boundary] + selector_retained.read_bytes())
    voice_swf = Path(voice_swf or work / 'cas-hair-casagegenderpane-current.swf')
    original_voice = voice_swf.read_bytes()
    if hashlib.sha256(original_voice).hexdigest() != VOICE_PIN:
        raise ValueError('Voice widget differs from the inspected 1.128.90 build.')
    run(['javac', '-cp', Path(ffdec).parent / 'ffdec.jar', '-d', java_classes,
         ROOT / 'tools/CasBytecodePatch.java', ROOT / 'tools/CasVoiceBytecodePatch.java'])
    voice_retained = work / 'apex-cas-voice-retained.abc'
    voice_verification = run(['java', '-cp', str(Path(ffdec).parent / 'ffdec.jar') + os.pathsep + str(java_classes),
        'CasVoiceBytecodePatch', voice_swf, cleanup_library, voice_retained])
    voice_contract = json.loads(voice_verification.stdout)
    voice_tag = next(t[3] for t in tags(unpack(original_voice)[1]) if t[0] == 82)
    voice_boundary = voice_tag.index(b'\0', 4) + 1
    voice_payload = replace_payload(original_voice, voice_tag[:voice_boundary] + voice_retained.read_bytes())
    import cas_molecule_patch
    molecule_swf = work / 'cas-hair-casmolecule-current.swf'
    original_molecule = molecule_swf.read_bytes()
    if hashlib.sha256(original_molecule).hexdigest() != MOLECULE_PIN:
        raise ValueError('CAS molecule differs from the inspected 1.128.90 build.')
    molecule_compiled = molecule_swf
    for sequence, target in enumerate(cas_molecule_patch.METHODS):
        source = work / 'cas-hair-casmolecule-current/scripts' / (target.replace('.', '/') + '.as')
        owned_source = work / ('apex-molecule-' + str(sequence) + '.as')
        owned_source.write_text(cas_molecule_patch.inject(source.read_text(encoding='utf-8'), target), encoding='utf-8')
        destination = work / ('apex-molecule-compiled-' + str(sequence) + '.swf')
        run([ffdec, '-importAssets', 'yes,local', '-replace', molecule_compiled, destination, target, owned_source])
        molecule_compiled = destination
    run(['javac', '-cp', Path(ffdec).parent / 'ffdec.jar', '-d', java_classes,
         ROOT / 'tools/CasBytecodePatch.java', ROOT / 'tools/CasMoleculeBytecodePatch.java'])
    molecule_retained = work / 'apex-molecule-retained.abc'
    molecule_verification = run(['java', '-cp', str(Path(ffdec).parent / 'ffdec.jar') + os.pathsep + str(java_classes),
        'CasMoleculeBytecodePatch', molecule_swf, molecule_compiled, molecule_retained])
    molecule_contract = json.loads(molecule_verification.stdout)
    molecule_tag = next(t[3] for t in tags(unpack(original_molecule)[1]) if t[0] == 82)
    molecule_boundary = molecule_tag.index(b'\0', 4) + 1
    molecule_payload = replace_payload(original_molecule, molecule_tag[:molecule_boundary] + molecule_retained.read_bytes())
    context_swf = work / 'more-cas-columns-donor/context-candidate-CAEE355CE0B704F7.swf'
    original_context = context_swf.read_bytes()
    context_pin = '2f09c674e42b87a09d21a7ef76c194967520c9ab93174d460df9f0c7b57ca52c'
    if hashlib.sha256(original_context).hexdigest()!=context_pin:
        raise ValueError('CAS radial menu differs from the inspected 1.128.90 build.')
    context_source = work / 'more-cas-columns-donor/context-menu/scripts/widgets/CAS/controls/CASContextMenu.as'
    context_owned = work / 'ApexCASContextMenu.as'
    context_owned.write_text(cas_catalog_workspace.inject_context(context_source.read_text(encoding='utf-8')),encoding='utf-8')
    context_compiled = work / 'apex-cas-context-compiled.swf'
    run([ffdec, '-importAssets','yes,local','-replace',context_swf,context_compiled,
         cas_catalog_workspace.CONTEXT_CLASS,context_owned])
    run(['javac','-cp',Path(ffdec).parent / 'ffdec.jar','-d',java_classes,
         ROOT / 'tools/CasBytecodePatch.java',ROOT / 'tools/CasCatalogBytecodePatch.java'])
    context_retained = work / 'apex-cas-context-retained.abc'
    context_contract = json.loads(run(['java','-cp',str(Path(ffdec).parent / 'ffdec.jar')+os.pathsep+str(java_classes),
        'CasCatalogBytecodePatch',context_swf,context_compiled,context_retained]).stdout)
    context_tag = next(t[3] for t in tags(unpack(original_context)[1]) if t[0]==82)
    context_boundary = context_tag.index(b'\0',4)+1
    context_payload = replace_payload(original_context,context_tag[:context_boundary]+context_retained.read_bytes())
    plan_swf = work / 'current-cas-plan.swf'
    original_plan = plan_swf.read_bytes()
    if hashlib.sha256(original_plan).hexdigest()!=cas_catalog_workspace.PLAN_PIN:
        raise ValueError('CAS outfit header differs from the inspected 1.128.90 build.')
    plan_source = work / 'current-cas-plan/scripts/widgets/CAS/PlanOutfit/CASPlanOutfitMain.as'
    plan_owned = work / 'ApexCASPlanOutfitMain.as'
    plan_owned.write_text(cas_catalog_workspace.inject_plan(plan_source.read_text(encoding='utf-8')),encoding='utf-8')
    plan_compiled = work / 'apex-cas-plan-compiled.swf'
    run([ffdec, '-importAssets','yes,local','-replace',plan_swf,plan_compiled,
         cas_catalog_workspace.PLAN_CLASS,plan_owned])
    plan_retained = work / 'apex-cas-plan-retained.abc'
    plan_contract = json.loads(run(['java','-cp',str(Path(ffdec).parent / 'ffdec.jar')+os.pathsep+str(java_classes),
        'CasCatalogBytecodePatch',plan_swf,plan_compiled,plan_retained,'plan']).stdout)
    plan_tag = next(t[3] for t in tags(unpack(original_plan)[1]) if t[0]==82)
    plan_boundary = plan_tag.index(b'\0',4)+1
    plan_payload = replace_payload(original_plan,plan_tag[:plan_boundary]+plan_retained.read_bytes())
    # Import-free ClassLibraryGamedata can supply the grid before the donor's
    # duplicate classes. Adapt each authenticated provider independently;
    # keep cleanup_library itself original for the selector/voice verifiers.
    import maru_companion
    if library_cache is None:
        run(['javac', '-cp', Path(ffdec).parent / 'ffdec.jar', '-d', java_classes,
             ROOT / 'tools/CasGridBytecodePatch.java'])
    def adapt_grid_provider(grid_swf, base_digest, output_name, cache=None):
        original_grid = Path(grid_swf).read_bytes()
        if hashlib.sha256(original_grid).hexdigest() != base_digest:
            raise ValueError('Grid class provider differs from its authenticated native resource.')
        if cache is not None:
            for key in (maru_companion.CANONICAL_GRID_LIBRARY, maru_companion.GRID_LIBRARY):
                if cache['original_sha256'][key] == base_digest:
                    cache['used'].add(dbpf_build.tgi(key))
                    prior=cache['providers'][dbpf_build.tgi(key)];retained=cache['resources'][key]
                    if 'view_width_transfer_contract' not in prior:cache.setdefault('continued',set()).add(dbpf_build.tgi(key))
                    return finish_grid_provider(prior,retained,grid_swf,
                        ffdec,work/(Path(output_name).stem+'-from-prefix'))
            raise ValueError('Cached native library has no matching original provider identity.')
        grid_retained = work / output_name
        grid_contract = json.loads(run(['java', '-cp', str(Path(ffdec).parent / 'ffdec.jar') + os.pathsep + str(java_classes),
            'CasGridBytecodePatch', grid_swf, grid_retained]).stdout)
        grid_tag = next(t[3] for t in tags(unpack(original_grid)[1]) if t[0] == 82)
        grid_boundary = grid_tag.index(b'\0', 4) + 1
        grid_payload = replace_payload(original_grid, grid_tag[:grid_boundary] + grid_retained.read_bytes())
        adapter = dict(base_resource_sha256=base_digest,
            patched_resource_sha256=hashlib.sha256(grid_payload).hexdigest(), native_bytecode_contract=grid_contract)
        # Keep the exact getter/profile proof historical; the transaction pass
        # proves rollback to that ABC and authenticates its own final output.
        import cas_grid_transaction
        transaction_abc, transaction_contract = cas_grid_transaction.adapt(grid_swf, grid_payload, None,
            ffdec, work / (Path(output_name).stem + '-transaction'))
        grid_payload = replace_payload(grid_payload, grid_tag[:grid_boundary] + transaction_abc)
        adapter = cas_grid_transaction.chain_adapter(adapter, transaction_contract, grid_payload)
        import cas_communication_index
        communication_abc, communication_contract = cas_communication_index.adapt(grid_swf, grid_payload, None,
            ffdec, work / (Path(output_name).stem + '-communication'))
        grid_payload = replace_payload(grid_payload, grid_tag[:grid_boundary] + communication_abc)
        adapter = cas_communication_index.chain_adapter(adapter, communication_contract, grid_payload)
        import cas_communication_domain_probe
        domain_baseline = work / (Path(output_name).stem + '-domain-baseline.swf')
        domain_baseline.write_bytes(grid_payload)
        domain_abc, domain_contract = cas_communication_domain_probe.adapt(domain_baseline,
            ffdec, work / (Path(output_name).stem + '-domain'))
        grid_payload = replace_payload(grid_payload, grid_tag[:grid_boundary] + domain_abc)
        adapter = cas_communication_domain_probe.chain_adapter(adapter, domain_contract, grid_payload)
        import cas_communication_removal_miss
        removal_baseline = work / (Path(output_name).stem + '-removal-baseline.swf')
        removal_baseline.write_bytes(grid_payload)
        removal_abc, removal_contract = cas_communication_removal_miss.adapt(grid_swf, removal_baseline,
            ffdec, work / (Path(output_name).stem + '-removal'))
        grid_payload = replace_payload(grid_payload, grid_tag[:grid_boundary] + removal_abc)
        adapter = cas_communication_removal_miss.chain_adapter(adapter, removal_contract, grid_payload)
        import cas_image_boundary_profile
        image_baseline = work / (Path(output_name).stem + '-image-baseline.swf')
        image_baseline.write_bytes(grid_payload)
        image_abc, image_contract = cas_image_boundary_profile.adapt(grid_swf, image_baseline,
            ffdec, work / (Path(output_name).stem + '-image'))
        grid_payload = replace_payload(grid_payload, grid_tag[:grid_boundary] + image_abc)
        adapter = cas_image_boundary_profile.chain_adapter(adapter, image_contract, grid_payload)
        import cas_grid_pool
        pool_baseline = work / (Path(output_name).stem + '-pool-baseline.swf')
        pool_baseline.write_bytes(grid_payload)
        pool_abc, pool_contract = cas_grid_pool.adapt(grid_swf, pool_baseline,
            ffdec, work / (Path(output_name).stem + '-pool'))
        grid_payload = replace_payload(grid_payload, grid_tag[:grid_boundary] + pool_abc)
        adapter = cas_grid_pool.chain_adapter(adapter, pool_contract, grid_payload)
        import cas_grid_presentation
        grid_payload, adapter = cas_grid_presentation.adapt(adapter, grid_payload, grid_swf,
            ffdec, work / (Path(output_name).stem + '-presentation'))
        import cas_grid_product_rows
        grid_payload, adapter = cas_grid_product_rows.adapt(adapter, grid_payload, grid_swf,
            ffdec, work / (Path(output_name).stem + '-product-rows'))
        import cas_grid_progress
        grid_payload, adapter = cas_grid_progress.adapt(adapter, grid_payload, grid_swf,
            ffdec, work / (Path(output_name).stem + '-progress'))
        import cas_swatch_provider
        grid_payload, adapter = cas_swatch_provider.adapt(adapter, grid_payload, grid_swf,
            ffdec, work / (Path(output_name).stem + '-swatch-provider'))
        import cas_grid_scroll
        grid_payload, adapter = cas_grid_scroll.adapt(adapter, grid_payload, grid_swf,
            ffdec, work / (Path(output_name).stem + '-scroll-only'))
        import cas_grid_slice
        grid_payload, adapter = cas_grid_slice.adapt(adapter, grid_payload, grid_swf,
            ffdec, work / (Path(output_name).stem + '-logical-slice'))
        import cas_grid_budget
        grid_payload, adapter = cas_grid_budget.adapt(adapter, grid_payload, grid_swf,
            ffdec, work / (Path(output_name).stem + '-budget'))
        return finish_grid_provider(adapter, grid_payload, grid_swf,
            ffdec, work / (Path(output_name).stem + '-featured'))
    canonical_grid_payload, canonical_grid_adapter = adapt_grid_provider(work / 'ClassLibraryGamedata.swf',
        maru_companion.CANONICAL_GRID_LIBRARY_SHA256, 'apex-cas-canonical-grid-getter-retained.abc', library_cache)
    maru_companion.verify_canonical_grid_adapter(canonical_grid_adapter, canonical_grid_payload)
    grid_providers = {dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY): canonical_grid_adapter}
    grid_payload = None
    if companion is not None:
        grid_payload, companion['grid_library_adapter'] = adapt_grid_provider(companion['grid_library'],
            maru_companion.GRID_LIBRARY_SHA256, 'apex-cas-grid-getter-retained.abc', library_cache)
        maru_companion.verify_grid_adapter(companion['grid_library_adapter'], grid_payload)
        grid_providers[dbpf_build.tgi(maru_companion.GRID_LIBRARY)] = companion['grid_library_adapter']
        maru_companion.verify_grid_providers(grid_providers,
            {maru_companion.CANONICAL_GRID_LIBRARY: canonical_grid_payload, maru_companion.GRID_LIBRARY: grid_payload})
    # The earlier Olympus domain owns real Button/controller listeners too.
    # Authenticate its original cleanup code separately from this pure
    # communication override; it has no fictional grid transaction history.
    dependency_payload, dependency_adapter = adapt_dependency_provider(cleanup_library, ffdec, work, library_cache)
    dependencies = {dbpf_build.tgi(CLEANUP_KEY): dependency_adapter}
    if source_pins() != expected_sources:
        raise ValueError('CAS bridge source changed during compilation; no package was written.')
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    resources = {KEY: payload, SELECTOR_KEY: selector_payload, VOICE_KEY: voice_payload,
                                              MOLECULE_KEY: molecule_payload,cas_catalog_workspace.CONTEXT_KEY:context_payload,
                                              cas_catalog_workspace.PLAN_KEY:plan_payload,maru_companion.CANONICAL_GRID_LIBRARY:canonical_grid_payload,
                                              CLEANUP_KEY:dependency_payload}
    if companion is not None:
        import maru_companion
        resources[maru_companion.GRID_LIBRARY] = grid_payload
        resources = maru_companion.combine(companion_package, resources, companion, grid_providers, dependencies)
    Path(output).write_bytes(dbpf_build.build(resources))
    info = {'schema': 1, 'artifact': Path(output).name, 'scope': 'native-CAS-semantic-bridge',
        'companion_code_merge': companion,
        'grid_provider_adapters': grid_providers,
        'communication_dependency_adapters': dependencies,
        'cached_library_resources': sorted(library_cache['used']) if library_cache is not None else [],
        'continued_library_resources': sorted(library_cache.get('continued',set())) if library_cache is not None else [],
        'source_pins': expected_sources,
        'typed_control_dispatch_verified': control_dispatch,
        'detached_snapshot_getters': detached_snapshot_getters,
        'household_acceptance_contract_verified': household_acceptance,
        'target_game': '1.128.90.1030', 'base_resource_sha256': hashlib.sha256(original).hexdigest(),
        'patched_resource_sha256': hashlib.sha256(payload).hexdigest(),
        'sha256': hashlib.sha256(Path(output).read_bytes()).hexdigest(),
        'runtime_verified': False, 'non_script_tags_preserved': True, 'native_bytecode_contract': contract,
        'structural_roles_native_bytecode_contract': structural_roles_contract,
        'draw_fast_path_native_bytecode_contract': draw_fast_path_contract,
        'cell_attach_native_bytecode_contract': cell_attach_contract,
        'catalog_binding_native_bytecode_contract': catalog_binding_contract,
        'draw_phase_native_bytecode_contract': draw_phase_contract,
        'swatch_geometry_native_bytecode_contract': swatch_geometry_contract,
        'preview_transition_native_bytecode_contract': preview_transition_contract,
        'scroll_main_native_bytecode_contract': scroll_main_contract,
        'budget_main_native_bytecode_contract': budget_main_contract,
        'featured_main_native_bytecode_contract': featured_main_contract,
        'publication_trace_main_native_bytecode_contract': publication_main_contract,
        'swatch_columns_main_native_bytecode_contract': swatch_columns_main_contract,
        'row_delta_main_native_bytecode_contract': row_delta_main_contract,
        'intrinsic_geometry_main_native_bytecode_contract': intrinsic_geometry_main_contract,
        'catalog_schedule_main_native_bytecode_contract': catalog_schedule_main_contract,
        'catalog_workflow_main_native_bytecode_contract': catalog_workflow_main_contract,
        'catalog_list_insets_main_native_bytecode_contract': catalog_list_insets_main_contract,
        'frame_status_main_native_bytecode_contract': frame_status_main_contract,
        'catalog_authority_main_native_bytecode_contract': catalog_authority_main_contract,
        'view_width_transfer_main_native_bytecode_contract': view_width_transfer_main_contract,
        'catalog_unconsumed_main_native_bytecode_contract': catalog_unconsumed_main_contract,
        'selector_native_bytecode_contract': selector_contract,
        'voice_native_bytecode_contract': voice_contract,
        'molecule_native_bytecode_contract': molecule_contract,
        'catalog_native_bytecode_contract': context_contract,
        'catalog_header_native_bytecode_contract': plan_contract,
        'base_resources': {dbpf_build.tgi(KEY): PIN, dbpf_build.tgi(SELECTOR_KEY): SELECTOR_PIN, dbpf_build.tgi(VOICE_KEY): VOICE_PIN,
                           dbpf_build.tgi(MOLECULE_KEY): MOLECULE_PIN,dbpf_build.tgi(cas_catalog_workspace.CONTEXT_KEY):context_pin,
                           dbpf_build.tgi(cas_catalog_workspace.PLAN_KEY):cas_catalog_workspace.PLAN_PIN,
                           dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY):maru_companion.CANONICAL_GRID_LIBRARY_SHA256,
                           dbpf_build.tgi(CLEANUP_KEY):CLEANUP_PIN},
        'unmodified_dependency_resources': {},
        'patched_resources': {dbpf_build.tgi(KEY): hashlib.sha256(payload).hexdigest(),
                              dbpf_build.tgi(SELECTOR_KEY): hashlib.sha256(selector_payload).hexdigest(),
                              dbpf_build.tgi(VOICE_KEY): hashlib.sha256(voice_payload).hexdigest(),
                              dbpf_build.tgi(MOLECULE_KEY): hashlib.sha256(molecule_payload).hexdigest(),
                              dbpf_build.tgi(cas_catalog_workspace.CONTEXT_KEY):hashlib.sha256(context_payload).hexdigest(),
                              dbpf_build.tgi(cas_catalog_workspace.PLAN_KEY):hashlib.sha256(plan_payload).hexdigest(),
                              dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY):hashlib.sha256(canonical_grid_payload).hexdigest(),
                              dbpf_build.tgi(CLEANUP_KEY):hashlib.sha256(dependency_payload).hexdigest()},
        'resources': [dbpf_build.tgi(KEY), dbpf_build.tgi(SELECTOR_KEY), dbpf_build.tgi(VOICE_KEY), dbpf_build.tgi(MOLECULE_KEY),
                      dbpf_build.tgi(cas_catalog_workspace.CONTEXT_KEY),dbpf_build.tgi(cas_catalog_workspace.PLAN_KEY),
                      dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY),dbpf_build.tgi(CLEANUP_KEY)], 'transport': 'fixed loopback CAS socket, native CAS acknowledgement',
        'socket_protocol': {'host': '127.0.0.1', 'port': 8021, 'length_digits': 8,
            'encoding': 'utf-8', 'maximum_frame_bytes': 131072, 'poll_interval_ms': 500}}
    if companion is not None:
        info['base_resources'][dbpf_build.tgi(maru_companion.GRID_LIBRARY)] = maru_companion.GRID_LIBRARY_SHA256
        info['resources'] = [dbpf_build.tgi(k) for k in sorted(resources)]
        info['patched_resources'] = {dbpf_build.tgi(k): dbpf_build.digest(v) for k, v in resources.items()}
        maru_companion.verify_merged(info, resources)
    write_json(Path(str(output) + '.manifest.json'), info)
    return info


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-swf', type=Path, required=True)
    p.add_argument('--decompiled', type=Path, required=True)
    p.add_argument('--ffdec', type=Path, required=True)
    p.add_argument('--output', type=Path, default=ROOT / 'dist/candidate/ApexCASBridge.package')
    p.add_argument('--selector-swf', type=Path)
    p.add_argument('--selector-decompiled', type=Path)
    p.add_argument('--cleanup-library', type=Path)
    p.add_argument('--voice-swf', type=Path)
    p.add_argument('--companion-package', type=Path)
    a = p.parse_args()
    print(json.dumps(build(a.input_swf, a.decompiled, a.ffdec, a.output, a.selector_swf, a.selector_decompiled, a.cleanup_library, a.voice_swf, a.companion_package), indent=2))
