"""Read coherent Main fixtures from the current private compiled package.

Historical library tests may replace a provider, but must not combine that
provider with an obsolete Main diagnostic envelope. No hashes are rewritten:
each Main stage is recovered by the production bytecode rollback verifier.
"""
import copy
import json
from pathlib import Path

import cas_catalog_binding as binding
import cas_draw_phase as phase
import cas_swatch_geometry as swatch
import cas_preview_transition as preview
import cas_swatch_provider as swatch_provider
import cas_grid_scroll as scroll
import cas_grid_slice as grid_slice
import cas_grid_budget as budget
import cas_grid_featured as featured
import dbpf_build
import maru_companion

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'dist/candidate/ApexCASBridge.package'
READY = PACKAGE.is_file() and Path(str(PACKAGE) + '.manifest.json').is_file()


# Only markers unique to the removed terminal passes are stripped. Shared
# binding/attach/communication sources remain authoritative for earlier passes.
TERMINAL_MAIN_MARKERS={
    'featured_main_native_bytecode_contract': featured.SOURCES,
    'budget_main_native_bytecode_contract': budget.SOURCES,
    'scroll_main_native_bytecode_contract': scroll.SOURCES,
    'preview_transition_native_bytecode_contract': ('tools/cas_preview_transition.py',),
    'swatch_geometry_native_bytecode_contract': (
        'tools/cas_swatch_geometry.py','tools/CasSwatchGeometryPatch.java',
        'Source/CASUi/swatch_geometry_adapter_methods.as',
        'Source/CASUi/swatch_group_geometry_adapter_methods.as',
        'Source/CASUi/catalog_panel_geometry_methods.as'),
}


def unwrap_catalog_heads(info,resources):
    """Authenticate and raw-roll back the complete latest provider/Main heads.

    Return new dictionaries on a real rollback, without changing the caller if
    any later proof fails. Only a successful full raw rollback can remove that
    stage's exact unique sources and envelope.
    """
    for module,unique,envelopes in (
            (featured,featured.SOURCES,('featured_main_native_bytecode_contract',)),
            (budget,budget.SOURCES,('budget_main_native_bytecode_contract',)),
            (grid_slice,grid_slice.SOURCES,()),
            (scroll,scroll.SOURCES,('scroll_main_native_bytecode_contract',)),
            (swatch_provider,swatch_provider.SOURCES[:2],())):
        previous,rolled=module.unwrap_manifest(info,resources)
        if previous is info and rolled is resources:continue
        for marker in unique:previous['source_pins'].pop(marker,None)
        for name in envelopes:previous.pop(name)
        info,resources=previous,rolled
    return info,resources


def rollback_terminal_main(info,resources):
    """Authenticate actual terminal bytes before removing their unique markers.

    No replacement artifact, digest repinning or source-only downgrade is used.
    Missing/partial terminal envelopes fail before the caller's dictionaries are
    changed. Calling this again on an explicit earlier fixture is harmless.
    """
    original_info,original_resources=info,resources
    # Slice/scroll include shared Main+provider authority. Roll back the whole
    # exact terminal before removing any shared source evidence.
    info,resources=unwrap_catalog_heads(info,resources)
    key=maru_companion.CUSTOMIZER
    raw=resources[key]
    removed=[]
    stages=(('preview_transition_native_bytecode_contract',preview,'preview_transition_contract',
             'swatch_geometry_native_bytecode_contract'),
            ('swatch_geometry_native_bytecode_contract',swatch,'swatch_geometry_contract',
             'draw_phase_native_bytecode_contract'))
    for name,module,proof_name,prior_name in stages:
        record=info.get(name)
        markers=TERMINAL_MAIN_MARKERS[name]
        if record is None:
            if any(marker in info['source_pins'] for marker in markers):
                raise AssertionError('Terminal Main source markers have no authenticated envelope: '+name)
            continue
        proof=record.get(proof_name,{})
        if any(info['source_pins'].get(source)!=proof.get('source_sha256',{}).get(source)
               for source in module.SOURCES):
            raise AssertionError('Terminal Main manifest/proof source authority differs: '+name)
        if module.verify_contract(record,raw) is not True:
            raise AssertionError('Terminal Main contract failed: '+name)
        if record['previous_stage_contract']!=info.get(prior_name):
            raise AssertionError('Terminal Main previous complete contract differs: '+name)
        raw=module.reconstruct_previous(raw,proof)
        removed.append(name)
    for name in removed:
        info.pop(name)
        for marker in TERMINAL_MAIN_MARKERS[name]:
            info['source_pins'].pop(marker,None)
    resources[key]=raw
    info['patched_resource_sha256']=info['patched_resources'][dbpf_build.tgi(key)]=dbpf_build.digest(raw)
    if info is not original_info:
        original_info.clear();original_info.update(info)
        original_resources.clear();original_resources.update(resources)
    return original_info,original_resources


def current_main(stage):
    info=json.loads(Path(str(PACKAGE)+'.manifest.json').read_text(encoding='utf-8'))
    final=dbpf_build.read(PACKAGE.read_bytes())[maru_companion.CUSTOMIZER]
    for wanted,name,module,proof_name,prior_name in (
        ('featured','featured_main_native_bytecode_contract',featured,'featured_main_contract',
         'budget_main_native_bytecode_contract'),
        ('budget','budget_main_native_bytecode_contract',budget,'budget_main_contract',
         'scroll_main_native_bytecode_contract'),
        ('scroll','scroll_main_native_bytecode_contract',scroll,'scroll_main_contract',
         'preview_transition_native_bytecode_contract'),
        ('preview','preview_transition_native_bytecode_contract',preview,'preview_transition_contract',
         'swatch_geometry_native_bytecode_contract'),
        ('swatch','swatch_geometry_native_bytecode_contract',swatch,'swatch_geometry_contract',
         'draw_phase_native_bytecode_contract'),
        ('phase','draw_phase_native_bytecode_contract',phase,'draw_phase_contract',
         'catalog_binding_native_bytecode_contract'),
        ('binding','catalog_binding_native_bytecode_contract',binding,'catalog_binding_contract',
         'cell_attach_native_bytecode_contract')):
        outer=info.get(name)
        if outer is None:
            if stage==wanted:raise ValueError('Current package has no requested Main stage: '+wanted)
            continue
        verify=module.verify_main if wanted=='featured' else module.verify_contract
        if verify(outer,final) is not True:
            raise AssertionError('Current Main '+wanted+' chain did not verify')
        if wanted=='featured':prior=featured.reconstruct(final,outer[proof_name]['rollback'],featured.MAIN)
        elif wanted=='budget':prior=budget.reconstruct(final,outer[proof_name]['rollback'],budget.MAIN,budget.MAIN_REPLACED,())
        elif wanted=='scroll':prior=scroll.reconstruct(final,outer[proof_name]['rollback'],scroll.MAIN,('ApexCatalogGridRequest',),())
        else:prior=module.reconstruct_previous(final,outer[proof_name])
        if outer['previous_stage_contract']!=info[prior_name]:
            raise AssertionError('Current Main '+wanted+' preceding history differs')
        if stage==wanted:return copy.deepcopy(outer),final,prior
        final=prior
    raise ValueError('Unknown Main fixture stage')
