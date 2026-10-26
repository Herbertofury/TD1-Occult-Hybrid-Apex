"""Explicit historical library stages for tests derived from a newer package."""
import json
from pathlib import Path

import dbpf_build
import maru_companion
import cas_communication_dependency
import cas_communication_removal_miss
import cas_image_boundary_profile
import cas_grid_pool
import cas_catalog_binding
import cas_draw_phase
from cas_main_chain_fixtures import rollback_terminal_main, unwrap_catalog_heads
import cas_grid_progress
import cas_grid_product_rows
import cas_grid_presentation
import cas_swatch_provider

ROOT = Path(__file__).resolve().parents[1]


def historical_library_terminals(info,resources):
    """Remove swatch/progress/row/presentation after their exact raw rollback.

    Existing image/pool/domain tests deliberately substitute older providers.
    They must not retain source markers for the newer two-/three-domain stages.
    Shared transaction/pool/communication source authority remains untouched.
    """
    current,current_resources=unwrap_catalog_heads(info,resources)
    changed=current is not info or current_resources is not resources
    for module,unique in ((cas_grid_progress,cas_grid_progress.SOURCES),
                          (cas_grid_product_rows,cas_grid_product_rows.SOURCES),
                          (cas_grid_presentation,cas_grid_presentation.PRESENTATION_SOURCES)):
        previous,rolled=module.unwrap_manifest(current,current_resources)
        if previous is current and rolled is current_resources:continue
        for source in unique:previous['source_pins'].pop(source,None)
        current,current_resources=previous,rolled
        changed=True
    if changed:
        info.clear();info.update(current)
        resources.clear();resources.update(current_resources)
    return info,resources


def historical_image_fixture(info, resources):
    """V334 image packages predate the two-provider retained widget pool."""
    historical_library_terminals(info,resources)
    for source in cas_grid_pool.SOURCES[:2]:
        info['source_pins'].pop(source, None)
    for name, key in [('canonical', maru_companion.CANONICAL_GRID_LIBRARY),
                      ('donor', maru_companion.GRID_LIBRARY)]:
        text = dbpf_build.tgi(key)
        record = info['grid_provider_adapters'][text]
        if isinstance(record, dict) and 'grid_pool_contract' in record:
            previous = record['previous_stage_adapter']
            path = ROOT / ('.work/v334-image-profile-' + name)
            assert previous == json.loads((path / 'chained.json').read_text())
            info['grid_provider_adapters'][text] = previous
            resources[key] = (path / 'final.swf').read_bytes()
            info['patched_resources'][text] = previous['patched_resource_sha256']
            if name == 'donor':
                info['companion_code_merge']['grid_library_adapter'] = previous
    return info, resources


def historical_removal_fixture(info, resources):
    """V333 removal packages predate the image-boundary diagnostics pass."""
    historical_image_fixture(info, resources)
    for source in cas_image_boundary_profile.SOURCES[:2]:
        info['source_pins'].pop(source, None)
    for name, key in [('canonical', maru_companion.CANONICAL_GRID_LIBRARY),
                      ('donor', maru_companion.GRID_LIBRARY),
                      ('dependency', maru_companion.UNMODIFIED_OLYMPUS_LIBRARY)]:
        text = dbpf_build.tgi(key)
        group = info.get('communication_dependency_adapters', {}) if name == 'dependency' else info['grid_provider_adapters']
        record = group.get(text)
        if isinstance(record, dict) and 'image_boundary_profile_contract' in record:
            previous = record['previous_stage_adapter']
            path = ROOT / ('.work/v333-removal-miss-' + name)
            assert previous == json.loads((path / 'chained.json').read_text())
            group[text] = previous
            resources[key] = (path / 'final.swf').read_bytes()
            info['patched_resources'][text] = previous['patched_resource_sha256']
            if name == 'donor':
                info['companion_code_merge']['grid_library_adapter'] = previous
    return info, resources


def historical_domain_fixture(info, resources):
    """V332 domain packages predate the later removal/Manager correction."""
    historical_removal_fixture(info, resources)
    for source in cas_communication_removal_miss.SOURCES[:2]:
        info['source_pins'].pop(source, None)
    for name, key in [('canonical', maru_companion.CANONICAL_GRID_LIBRARY),
                      ('donor', maru_companion.GRID_LIBRARY),
                      ('dependency', maru_companion.UNMODIFIED_OLYMPUS_LIBRARY)]:
        text = dbpf_build.tgi(key)
        group = info.get('communication_dependency_adapters', {}) if name == 'dependency' else info['grid_provider_adapters']
        record = group.get(text)
        if isinstance(record, dict) and 'communication_removal_miss_contract' in record:
            previous = record['previous_stage_adapter']
            path = ROOT / ('.work/v332-domain-probe-' + name)
            assert previous == json.loads((path / 'chained.json').read_text())
            group[text] = previous
            resources[key] = (path / 'final.swf').read_bytes()
            info['patched_resources'][text] = previous['patched_resource_sha256']
            if name == 'donor':
                info['companion_code_merge']['grid_library_adapter'] = previous
    return info, resources


def historical_provider_fixture(info, resources, keep_dependency=False):
    """Remove later source requirements together with their actual envelopes."""
    # Binding/phase use the communication verifier as a compiler dependency.
    # A pre-communication library manifest cannot keep that Main authority
    # while deleting its shared source marker. Recover the exact earlier Main
    # bytes and envelopes; never relabel the later bytecode as historical.
    rollback_terminal_main(info,resources)
    key = maru_companion.CUSTOMIZER
    outer = info.pop('draw_phase_native_bytecode_contract', None)
    if outer is not None:
        assert cas_draw_phase.verify_contract(outer, resources[key])
        assert outer['previous_stage_contract'] == info['catalog_binding_native_bytecode_contract']
        resources[key] = cas_draw_phase.reconstruct_previous(resources[key], outer['draw_phase_contract'])
    for source in cas_draw_phase.SOURCES[:2]:
        info['source_pins'].pop(source, None)
    outer = info.pop('catalog_binding_native_bytecode_contract', None)
    if outer is not None:
        assert cas_catalog_binding.verify_contract(outer, resources[key])
        assert outer['previous_stage_contract'] == info['cell_attach_native_bytecode_contract']
        resources[key] = cas_catalog_binding.reconstruct_previous(resources[key], outer['catalog_binding_contract'])
    for source in cas_catalog_binding.SOURCES[:2]:
        info['source_pins'].pop(source, None)
    text = dbpf_build.tgi(key)
    info['patched_resource_sha256'] = info['patched_resources'][text] = dbpf_build.digest(resources[key])
    historical_domain_fixture(info, resources)
    for source in maru_companion.GRID_COMMUNICATION_DOMAIN_SOURCES:
        info['source_pins'].pop(source, None)
    for name, key in [('canonical', maru_companion.CANONICAL_GRID_LIBRARY), ('donor', maru_companion.GRID_LIBRARY)]:
        text = dbpf_build.tgi(key)
        record = info['grid_provider_adapters'][text]
        if 'previous_stage_adapter' in record:
            previous = record['previous_stage_adapter']
            path = ROOT / ('.work/v331-comm-index-stage-' + name)
            assert previous == json.loads((path / 'chained.json').read_text())
            info['grid_provider_adapters'][text] = previous
            resources[key] = (path / 'final.swf').read_bytes()
            info['patched_resources'][text] = previous['patched_resource_sha256']
            if name == 'donor':
                info['companion_code_merge']['grid_library_adapter'] = previous
    key = maru_companion.UNMODIFIED_OLYMPUS_LIBRARY
    text = dbpf_build.tgi(key)
    if keep_dependency:
        evidence = info.get('communication_dependency_adapters', {})
        record = evidence.get(text)
        if isinstance(record, dict) and 'previous_stage_adapter' in record:
            previous = record['previous_stage_adapter']
            path = ROOT / '.work/v332-communication-dependency'
            assert previous == json.loads((path / 'chained.json').read_text())
            evidence[text] = previous
            resources[key] = (path / 'final.swf').read_bytes()
            info['patched_resources'][text] = previous['patched_resource_sha256']
    else:
        for source in maru_companion.GRID_COMMUNICATION_DEPENDENCY_SOURCES:
            info['source_pins'].pop(source, None)
        resources.pop(key, None)
        info.pop('communication_dependency_adapters', None)
        info.get('base_resources', {}).pop(text, None)
        info.get('patched_resources', {}).pop(text, None)
        if isinstance(info.get('resources'), list):
            info['resources'] = [value for value in info['resources'] if value != text]
        info.setdefault('unmodified_dependency_resources', {})[text] = cas_communication_dependency.PIN
    return info, resources
