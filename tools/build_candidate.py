"""Build one reviewable Apex candidate bundle, never deploy or launch it."""
import argparse
import hashlib
import io
import json
from pathlib import Path
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

ROOT = Path(__file__).resolve().parents[1]


def build(output, foundry=None):
    output = Path(output).resolve()
    if ROOT not in output.parents or '.work' in output.parts or output.name != 'candidate':
        raise ValueError('Use the single checkout artifact directory dist/candidate.')
    baseline = ROOT / '.work' / 'baselines'
    packages = build_packages(baseline, output)
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
    filename = 'Apex_Development_Candidate_2026-10-07.zip'
    atomic_bytes(output / filename, bundle)
    receipt = {'artifact': filename, 'sha256': digest(bundle), 'bytes': len(bundle), 'members': len(payloads)}
    write_json(output / (filename + '.sha256.json'), receipt)
    write_json(ROOT / 'manifests' / 'candidate-build.json', {'schema': 1, 'bundle': receipt,
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
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.foundry), indent=2))
