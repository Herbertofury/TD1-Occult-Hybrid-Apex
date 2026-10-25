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
                  'tools/CasCatalogBindingPatch.java', 'tools/cas_catalog_binding.py',
                  'tools/CasDrawPhasePatch.java', 'tools/cas_draw_phase.py',
                  'Source/CASUi/form_strip_methods.as',
                  'Source/CASUi/pair_controls_methods.as',
                  'Source/CASUi/catalog_workspace_methods.as',
                  'Source/CASUi/catalog_cards_methods.as', 'tools/cas_equipped_catalog.py',
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
    """Keep the inspected household validation ahead of its single native save.

    A single-Sim shortcut returned false in actual household CAS. The native
    name application can have side effects, so the intent is consumed first.
    """
    body = methods.split('private function ApexAccept()', 1)[1]
    steps = ('apexPendingFields=null; apexPendingReply=null; apexPendingContext=null;',
             'if(int(editMode)==0)',
             'CallUIService("IsWidgetVisible","CASGeneticsPane")',
             'CallUIService("CasApplyNameFields",false)',
             'CallGameService("CasGetHouseholdExchangeData",{bValidateExistingSimTraits:false})',
             'validatedHousehold.HouseholdContainsAdults()',
             'CallGameService("CASCheckProfanityOnSimNames",null)',
             'reply.household_finalization_verified=true;',
             'reply.commit_attempted=true;',
             'CallGameService("SaveAndExitCAS",{bValidateExistingSimTraits:false})')
    try:
        positions = [body.index(step) for step in steps]
    except ValueError as error:
        raise ValueError('Native household CAS finalization contract is incomplete.') from error
    if positions != sorted(positions) or body.count('CallGameService("SaveAndExitCAS",') != 1:
        raise ValueError('Native household CAS finalization must precede one consumed commit.')
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
        '   import olympus.events.GridEvent;\n   import olympus.events.DataFeedEvent;\n   import olympus.events.ScrollerEvent;\n   import olympus.events.PushButtonEvent;\n   import gamedata.shared.SimGenderTypes;\n   import gamedata.CAS.shared.CASCatalogProduct;\n   import gamedata.CAS.CASAPI;')
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
    run(['javac', '-cp', Path(ffdec).parent / 'ffdec.jar', '-d', java_classes,
         ROOT / 'tools/CasGridBytecodePatch.java'])
    def adapt_grid_provider(grid_swf, base_digest, output_name):
        original_grid = Path(grid_swf).read_bytes()
        if hashlib.sha256(original_grid).hexdigest() != base_digest:
            raise ValueError('Grid class provider differs from its authenticated native resource.')
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
        return grid_payload, adapter
    canonical_grid_payload, canonical_grid_adapter = adapt_grid_provider(work / 'ClassLibraryGamedata.swf',
        maru_companion.CANONICAL_GRID_LIBRARY_SHA256, 'apex-cas-canonical-grid-getter-retained.abc')
    maru_companion.verify_canonical_grid_adapter(canonical_grid_adapter, canonical_grid_payload)
    grid_providers = {dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY): canonical_grid_adapter}
    grid_payload = None
    if companion is not None:
        grid_payload, companion['grid_library_adapter'] = adapt_grid_provider(companion['grid_library'],
            maru_companion.GRID_LIBRARY_SHA256, 'apex-cas-grid-getter-retained.abc')
        maru_companion.verify_grid_adapter(companion['grid_library_adapter'], grid_payload)
        grid_providers[dbpf_build.tgi(maru_companion.GRID_LIBRARY)] = companion['grid_library_adapter']
        maru_companion.verify_grid_providers(grid_providers,
            {maru_companion.CANONICAL_GRID_LIBRARY: canonical_grid_payload, maru_companion.GRID_LIBRARY: grid_payload})
    # The earlier Olympus domain owns real Button/controller listeners too.
    # Authenticate its original cleanup code separately from this pure
    # communication override; it has no fictional grid transaction history.
    import cas_communication_dependency
    dependency_abc, dependency_contract = cas_communication_dependency.adapt(cleanup_library, ffdec,
        work / 'native-communication-dependency')
    dependency_original = cleanup_library.read_bytes()
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
    dependencies = {dbpf_build.tgi(CLEANUP_KEY): cas_image_boundary_profile.chain_adapter(
        dependency_adapter, image_contract, dependency_payload)}
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
