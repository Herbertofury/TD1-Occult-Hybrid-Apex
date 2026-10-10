"""Build one reviewable Apex candidate bundle, never deploy or launch it."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import uuid
from xml.etree import ElementTree
import zipfile
from build_packages import build as build_packages, atomic_bytes
from build_script import build as build_script
from dbpf_build import digest, read, tgi
from source_manifest import write_json
from verify_mccc_port import verify as verify_mccc
from verify_overlay_sidecar import verify as verify_overlay
from cas_ui_build import verify_source_pins

ROOT = Path(__file__).resolve().parents[1]


def candidate_filename(epoch):
    epoch = '2026-10-07' if epoch is None else epoch
    if not isinstance(epoch, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{7,79}', epoch):
        raise ValueError('Use a bounded explicit build epoch containing lowercase letters, numbers and hyphens.')
    return 'Apex_Development_Candidate_' + epoch + '.zip'


def build(output, foundry=None, cas_ui_package=None, epoch=None):
    output = Path(output).resolve()
    if ROOT not in output.parents or '.work' in output.parts or output.name != 'candidate':
        raise ValueError('Use the single checkout artifact directory dist/candidate.')
    filename = candidate_filename(epoch)
    if (output / filename).exists() or (output / (filename + '.sha256.json')).exists():
        raise ValueError('This candidate epoch already exists; retain its immutable artifacts and use a new explicit --epoch.')
    baseline = ROOT / '.work' / 'baselines'
    packages = build_packages(baseline, output)
    if cas_ui_package is not None:
        ui_path = Path(cas_ui_package).resolve(strict=True)
        if ui_path != output / 'ApexCASBridge.package':
            raise ValueError('Use the single built candidate CAS bridge package.')
        ui_info = json.loads(Path(str(ui_path) + '.manifest.json').read_text(encoding='utf-8'))
        verify_source_pins(ui_info)
        contract = ui_info.get('native_bytecode_contract', {})
        selector_contract = ui_info.get('selector_native_bytecode_contract', {})
        required_selector_contract = (
            'native_class_script_traits_preserved', 'native_initialize_tail_hook_verified',
            'native_refresh_entry_hook_verified', 'native_bodies_after_hook_stripping_exact',
            'callback_raw_copy_only_verified', 'service_retained_view_read_only_verified',
            'exact_widget_registration_linkage_verified', 'initialize_preserves_captured_feed_verified',
            'selector_has_no_unload_override', 'inherited_cleanup_bytecode_verified',
            'independent_occult_sync_default_verified',
        )
        required_contract = (
            'native_lexical_scope_preserved', 'owned_local_scope_indexes_verified',
            'native_unload_bytecode_extended', 'native_unload_cleanup_precedes_teardown',
            'serialized_lifecycle_hooks_verified', 'socket_callbacks_data_only_verified',
            'timer_command_phases_verified', 'accept_commit_timer_owned_verified',
            'accept_native_class_linkage_verified',
            'accept_expected_household_bound_verified',
            'accept_primary_layer_only_verified', 'catalog_metadata_localization_linkage_verified',
            'owner_pair_listener_cleanup_verified', 'owner_pair_callback_data_only_verified',
            'owner_pair_timer_read_only_verified',
            'socket_connect_queue_only_verified',
            'socket_handshake_exact_constructor_timer_verified',
            'form_select_timer_owned_verified', 'form_select_exact_same_original_pair_verified',
            'form_select_native_argument_order_verified', 'form_select_next_tick_readback_verified',
            'earrings_exact_bodytype_and_swatch_guard_verified',
        )
        if (ui_info.get('target_game') != '1.128.90.1030' or
                ui_info.get('sha256') != digest(ui_path.read_bytes()) or
                ui_info.get('non_script_tags_preserved') is not True or
                contract.get('unchanged_native_methods') != 1785 or
                selector_contract.get('native_method_count') != 462 or
                selector_contract.get('unchanged_native_methods') != 459 or
                any(selector_contract.get(flag) is not True for flag in required_selector_contract) or
                any(contract.get(flag) is not True for flag in required_contract)):
            raise ValueError('CAS bridge package does not match its build evidence.')
        if set(tgi(key) for key in read(ui_path.read_bytes())) != {
                '62ECC59A:00000000:DF09D526F4C77B95',
                '62ECC59A:00000000:26DF5B0A7B97963E'}:
            raise ValueError('CAS bridge must contain exactly the two verified native UI resources.')
        packages.append(ui_info)
    script = build_script(ROOT / 'Source', output / 'ApexOccultHybrid.ts4script',
        hybrid_baseline=baseline / 'LordPercivalXII.Occult.Hybrid.Unlocker.Stabilizer.Version.1.13.7.zip')
    mccc = verify_mccc()
    payloads = {}
    evidence = []
    script_bytes = (output / script['artifact']).read_bytes()
    with zipfile.ZipFile(io.BytesIO(script_bytes)) as archive:
        script_members = set(archive.namelist())
        if archive.testzip() is not None:
            raise ValueError('Script CRC failure.')
    for package in packages:
        path = output / package['artifact']
        raw = path.read_bytes()
        resources = read(raw)
        references = set()
        for resource in resources.values():
            if resource.lstrip().startswith(b'<'):
                for node in ElementTree.fromstring(resource).iter():
                    module = node.get('m', '')
                    if module.startswith(('apex_hybrid.', 'apex_core.')):
                        member = module.replace('.', '/') + '.pyc'
                        if member not in script_members:
                            raise ValueError('Package has an orphaned script reference: ' + module)
                        references.add(module)
        row = {'artifact': package['artifact'], 'resources': len(resources),
               'namespace_modules_resolved': sorted(references), 'independent_rust_verified': False}
        if foundry:
            result = subprocess.run([str(foundry), 'validate', str(path)], text=True, capture_output=True, timeout=30)
            if result.returncode or json.loads(result.stdout).get('resources') != len(resources):
                raise ValueError('Independent Rust index validation failed: ' + path.name)
            # Hash every resource extracted by the independent Rust implementation.
            # One ephemeral file at a time, strictly inside private checkout work.
            verified = 0
            work = ROOT / '.work'
            work.mkdir(exist_ok=True)
            for key, expected in sorted(resources.items()):
                extracted = work / ('dbpf-verify-' + uuid.uuid4().hex + '.bin')
                if extracted.exists() or extracted.resolve().parent != work.resolve():
                    raise ValueError('Resource verification path collision.')
                try:
                    result = subprocess.run([str(foundry), 'extract', str(path), '--key', tgi(key), '--output', str(extracted)],
                        text=True, capture_output=True, timeout=30)
                    if result.returncode or not extracted.is_file() or digest(extracted.read_bytes()) != digest(expected):
                        raise ValueError('Independent resource contents differ: ' + tgi(key))
                    verified += 1
                finally:
                    if extracted.is_file() and extracted.resolve().parent == work.resolve():
                        extracted.unlink()
            row.update({'independent_rust_verified': True, 'independent_resource_hashes_verified': verified})
        evidence.append(row)
        name = package['artifact']
        destination = name if name.startswith('Optional/') else (
            'ExperimentalUI/' + name if name == 'ApexColorStudio.package' else 'Mods/Apex/' + name)
        payloads[destination] = raw
        payloads['Manifests/' + name + '.manifest.json'] = path.with_name(path.name + '.manifest.json').read_bytes()
    payloads['Mods/Apex/' + script['artifact']] = script_bytes
    payloads['Manifests/' + script['artifact'] + '.manifest.json'] = (output / (script['artifact'] + '.manifest.json')).read_bytes()
    native = ROOT / 'NativeOverlay' / 'build' / 'Release' / 'ApexOverlay.dll'
    native_bytes = native.read_bytes()
    if native_bytes[:2] != b'MZ':
        raise ValueError('Build the actual native overlay before bundling it.')
    native_info = verify_overlay(native, script=output / script['artifact'])
    write_json(output / 'overlay-manifest.json', native_info)
    write_json(ROOT / 'manifests' / 'native-sidecar.json', native_info)
    payloads['Mods/Apex/Native/ApexOverlay.dll'] = native_bytes
    payloads['Mods/Apex/Native/ApexOverlay.ini'] = (ROOT / 'NativeOverlay' / 'ApexOverlay.ini').read_bytes()
    payloads['Mods/Apex/Native/overlay-manifest.json'] = (output / 'overlay-manifest.json').read_bytes()
    payloads['README.md'] = (ROOT / 'docs' / 'CANDIDATE_INSTALL_AND_TEST.md').read_bytes()
    payloads['THIRD_PARTY_NOTICES.md'] = (ROOT / 'THIRD_PARTY_NOTICES.md').read_bytes()
    payloads['Licenses/ImGui-LICENSE.txt'] = (ROOT / 'NativeOverlay' / 'third_party' / 'imgui' / 'LICENSE.txt').read_bytes()
    payloads['Licenses/nlohmann-json-LICENSE.MIT'] = (ROOT / 'NativeOverlay' / 'third_party' / 'nlohmann' / 'LICENSE.MIT').read_bytes()
    payloads['Licenses/MinHook-LICENSE.txt'] = (ROOT / 'NativeOverlay' / 'third_party' / 'minhook' / 'LICENSE.txt').read_bytes()
    for name in ('baseline-inventory.json', 'mccc-dresser-port.json', 'cas-color-format.json'):
        payloads['Manifests/' + name] = (ROOT / 'manifests' / name).read_bytes()
    manifest = {'schema': 1, 'status': 'owner-test-development-candidate', 'target_game': '1.128.90.1030',
        'build_epoch': epoch or '2026-10-07',
        'runtime_verified': False, 'f11_game_loader_verified': False, 'deployed': False,
        'native_load_model': 'mod-folder-sidecar-via-game-_ctypes', 'native_protocol': 1,
        'package_verification': evidence, 'compiled_script_modules': len(script['compiled_modules']),
        'mccc_pure_helpers': len(mccc['functions']), 'mccc_matching_cases': mccc['matching_cases'],
        'files': [{'file': name, 'bytes': len(raw), 'sha256': digest(raw)} for name, raw in sorted(payloads.items())]}
    write_json(output / 'candidate-manifest.json', manifest)
    payloads['Manifests/candidate-manifest.json'] = (output / 'candidate-manifest.json').read_bytes()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(payloads.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system, info.external_attr, info.compress_type = 3, 0o100644 << 16, zipfile.ZIP_DEFLATED
            archive.writestr(info, raw, compresslevel=9)
    bundle = stream.getvalue()
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != set(payloads):
            raise ValueError('Candidate bundle inventory/CRC mismatch.')
        for name, raw in payloads.items():
            if archive.read(name) != raw:
                raise ValueError('Candidate bundle content mismatch: ' + name)
    atomic_bytes(output / filename, bundle)
    receipt = {'artifact': filename, 'sha256': digest(bundle), 'bytes': len(bundle), 'members': len(payloads)}
    write_json(output / (filename + '.sha256.json'), receipt)
    write_json(ROOT / 'manifests' / 'candidate-build.json', {'schema': 1, 'bundle': receipt,
        'build_epoch': epoch or '2026-10-07',
        'runtime_verified': False, 'f11_game_loader_verified': False, 'deployed': False,
        'package_verification': evidence, 'compiled_script_modules': len(script['compiled_modules']),
        'files': manifest['files']})
    return dict(receipt, compiled_modules=len(script['compiled_modules']),
                packages=len(packages), resource_count=sum(row['resources'] for row in evidence),
                independent_rust_verified=bool(foundry))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist' / 'candidate')
    parser.add_argument('--foundry', type=Path)
    parser.add_argument('--cas-ui-package', type=Path)
    parser.add_argument('--epoch', help='New immutable candidate identifier; required when the prior epoch exists')
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.foundry, args.cas_ui_package, args.epoch), indent=2))
