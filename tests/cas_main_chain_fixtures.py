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
import cas_swatch_columns as skin
import cas_grid_row_delta as row_delta
import cas_grid_staging_attach as staging_attach
import cas_grid_publication as publication
import cas_catalog_unconsumed as unconsumed
import cas_grid_width as width
import cas_catalog_authority as authority
import cas_grid_eof as eof
import cas_grid_frame_status as frame_status
import cas_grid_logical_bank as logical_bank
import cas_grid_position as position
import cas_grid_spares as spares
import cas_list_insets as list_insets
import cas_catalog_workflow as workflow
import cas_catalog_schedule as schedule
import cas_grid_intrinsic as intrinsic
import cas_grid_physical as physical
import dbpf_build
import maru_companion

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'dist/candidate/ApexCASBridge.package'
READY = PACKAGE.is_file() and Path(str(PACKAGE) + '.manifest.json').is_file()


# Only markers unique to the removed terminal passes are stripped. Shared
# binding/attach/communication sources remain authoritative for earlier passes.
TERMINAL_MAIN_MARKERS={
    unconsumed.MANIFEST: unconsumed.SOURCES,
    width.MAIN_MANIFEST: width.SOURCES,
    authority.MANIFEST: authority.SOURCES,
    frame_status.MANIFEST: frame_status.SOURCES,
    list_insets.MANIFEST: list_insets.SOURCES,
    workflow.MANIFEST: workflow.SOURCES,
    schedule.MANIFEST: schedule.SOURCES,
    'intrinsic_geometry_main_native_bytecode_contract': intrinsic.SOURCES,
    'row_delta_main_native_bytecode_contract': row_delta.SOURCES,
    'swatch_columns_main_native_bytecode_contract': skin.SOURCES,
    'publication_trace_main_native_bytecode_contract': publication.SOURCES,
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


def unwrap_catalog_heads(info,resources,stop_before=None):
    """Authenticate and raw-roll back the complete latest provider/Main heads.

    Return new dictionaries on a real rollback, without changing the caller if
    any later proof fails. Only a successful full raw rollback can remove that
    stage's exact unique sources and envelope.
    """
    stages=(
            (unconsumed,unconsumed.SOURCES,(unconsumed.MANIFEST,)),
            (width,width.SOURCES,(width.MAIN_MANIFEST,)),
            (authority,authority.SOURCES,(authority.MANIFEST,)),
            (eof,eof.SOURCES,()),
            (frame_status,frame_status.SOURCES,(frame_status.MANIFEST,)),
            (logical_bank,logical_bank.SOURCES,()),
            (position,position.SOURCES,()),
            (spares,spares.SOURCES,()),
            (list_insets,list_insets.SOURCES,(list_insets.MANIFEST,)),
            (workflow,workflow.SOURCES,(workflow.MANIFEST,)),
            (schedule,schedule.SOURCES,(schedule.MANIFEST,)),
            (intrinsic,intrinsic.SOURCES,('intrinsic_geometry_main_native_bytecode_contract',)),
            (physical,physical.SOURCES,()),
            (row_delta,row_delta.SOURCES,('row_delta_main_native_bytecode_contract',)),
            (skin,skin.SOURCES,('swatch_columns_main_native_bytecode_contract',)),
            (staging_attach,staging_attach.SOURCES,()),
            (publication,publication.SOURCES,('publication_trace_main_native_bytecode_contract',)),
            (featured,featured.SOURCES,('featured_main_native_bytecode_contract',)),
            (budget,budget.SOURCES,('budget_main_native_bytecode_contract',)),
            (grid_slice,grid_slice.SOURCES,()),
            (scroll,scroll.SOURCES,('scroll_main_native_bytecode_contract',)),
            (swatch_provider,swatch_provider.SOURCES[:2],()))
    if stop_before is not None and stop_before not in {module.__name__ for module,_,_ in stages}:
        raise ValueError('Unknown exact historical terminal boundary')
    for module,unique,envelopes in stages:
        if module.__name__==stop_before:break
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
    # Authenticate the complete actual new Main before exposing a historical
    # test stage. Providers are irrelevant to this per-resource read, but their
    # complete heads are still rolled together by unwrap_catalog_heads above.
    for wanted,name,module,prior_name in (
        ('unconsumed',unconsumed.MANIFEST,unconsumed,width.MAIN_MANIFEST),
        ('width',width.MAIN_MANIFEST,width,authority.MANIFEST),
        ('authority',authority.MANIFEST,authority,frame_status.MANIFEST),
        ('frame',frame_status.MANIFEST,frame_status,list_insets.MANIFEST),
        ('list-insets',list_insets.MANIFEST,list_insets,workflow.MANIFEST),
        ('workflow',workflow.MANIFEST,workflow,schedule.MANIFEST),
        ('schedule',schedule.MANIFEST,schedule,'intrinsic_geometry_main_native_bytecode_contract'),
        ('intrinsic','intrinsic_geometry_main_native_bytecode_contract',intrinsic,'row_delta_main_native_bytecode_contract')):
        outer=info.get(name)
        if outer is None:
            if any(marker in info.get('source_pins',{})for marker in module.SOURCES):
                raise ValueError('Current Main terminal source has no exact envelope: '+name)
            if stage==wanted:raise ValueError('Current package has no requested Main stage: '+wanted)
            continue
        if module.verify_main(outer,final)is not True:raise AssertionError('Current Main '+wanted+' chain did not verify')
        if module in(frame_status,intrinsic,width):previous,prior=module.historical(outer,final,module.MAIN)
        else:previous,prior=module.historical(outer,final)
        if previous!=info.get(prior_name)or previous!=outer.get('previous_stage_contract'):
            raise AssertionError('Current Main '+wanted+' preceding complete history differs')
        if stage==wanted:return copy.deepcopy(outer),final,prior
        final=prior
    for wanted,name,module,proof_name,prior_name in (
        ('row-delta','row_delta_main_native_bytecode_contract',row_delta,'row_delta_contract',
         'swatch_columns_main_native_bytecode_contract'),
        ('skin','swatch_columns_main_native_bytecode_contract',skin,'swatch_columns_main_contract',
         'publication_trace_main_native_bytecode_contract'),
        ('publication','publication_trace_main_native_bytecode_contract',publication,'publication_trace_contract',
         'featured_main_native_bytecode_contract'),
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
        verify=module.verify_main if wanted in ('row-delta','skin','publication','featured') else module.verify_contract
        if verify(outer,final) is not True:
            raise AssertionError('Current Main '+wanted+' chain did not verify')
        if wanted=='row-delta':prior=row_delta.reconstruct(final,outer[proof_name]['rollback'],row_delta.MAIN)
        elif wanted=='skin':prior=skin.reconstruct(final,outer[proof_name])
        elif wanted=='publication':prior=publication.reconstruct(final,outer[proof_name]['rollback'],publication.MAIN)
        elif wanted=='featured':prior=featured.reconstruct(final,outer[proof_name]['rollback'],featured.MAIN)
        elif wanted=='budget':prior=budget.reconstruct(final,outer[proof_name]['rollback'],budget.MAIN,budget.MAIN_REPLACED,())
        elif wanted=='scroll':prior=scroll.reconstruct(final,outer[proof_name]['rollback'],scroll.MAIN,('ApexCatalogGridRequest',),())
        else:prior=module.reconstruct_previous(final,outer[proof_name])
        if outer['previous_stage_contract']!=info[prior_name]:
            raise AssertionError('Current Main '+wanted+' preceding history differs')
        if stage==wanted:return copy.deepcopy(outer),final,prior
        final=prior
    raise ValueError('Unknown Main fixture stage')
