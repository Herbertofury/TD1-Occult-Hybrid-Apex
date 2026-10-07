"""Build concrete Apex development packages from pinned authorized baselines.

No deployment, game launch, profile mutation or runtime acceptance. Namespace
migration preserves IDs for existing save compatibility. Resource owners and
overlaps are explicit; current-build functional/parity tests belong to the owner.
"""
import argparse
import collections
import io
import json
import os
from pathlib import Path
import tempfile
from xml.etree import ElementTree
import zipfile
import dbpf_build as dbpf
from source_manifest import write_json

ROOT = Path(__file__).resolve().parents[1]


def atomic_bytes(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=str(path.parent), delete=False) as stream:
            temporary = stream.name
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, str(path))
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def migrate_xml(payload):
    if not payload.lstrip().startswith(b'<'):
        return payload
    if b'<!DOCTYPE' in payload.upper() or b'<!ENTITY' in payload.upper():
        raise ValueError('Unsupported baseline XML entities.')
    root = ElementTree.fromstring(payload)
    changed = False
    for node in root.iter():
        module = node.get('m')
        if module and (module == 'OccultHybrid' or module.startswith('OccultHybrid.')):
            node.set('m', 'apex_hybrid' + module[len('OccultHybrid'):])
            changed = True
    if root.get('m') == 'apex_hybrid.Modules.TD1_OccultHybrid_OccultPicker':
        for tests in root.findall("L[@n='test_globals']"):
            for test in list(tests):
                if test.get('t') == 'is_online':
                    tests.remove(test)
        for item in root.findall(".//L[@n='species']/E"):
            if not (item.text or '').strip():
                item.text = 'HUMAN'
        changed = True
    return ElementTree.tostring(root, encoding='utf-8', xml_declaration=True) if changed else payload


def build(baseline, output):
    baseline, output = Path(baseline).resolve(strict=True), Path(output).resolve()
    if baseline == output or baseline in output.parents or output.name.casefold() == 'mods':
        raise ValueError('Package output must be an external artifact folder.')
    if any(part.casefold().startswith('the sims 4') for part in output.parts):
        raise ValueError('Build outputs must be outside every Sims user profile.')
    inventory = json.loads((ROOT / 'manifests' / 'baseline-inventory.json').read_text(encoding='utf-8'))
    expected = {row['file']: row for row in inventory['archives'] + inventory['packages']}
    sources = {}
    for name, row in expected.items():
        path = baseline / name
        raw = path.read_bytes()
        if dbpf.digest(raw) != row['sha256']:
            raise ValueError('Baseline identity changed: ' + name)
        if name.endswith('.zip'):
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                for info in archive.infolist():
                    if info.file_size > dbpf.MAX_RESOURCE or '..' in Path(info.filename).parts:
                        raise ValueError('Unsafe baseline archive member.')
                    if info.filename.endswith('.package'):
                        sources[name + '/' + info.filename] = archive.read(info)
        else:
            sources[name] = raw
    hybrid_archive = next(name for name in expected if name.startswith('LordPercivalXII.'))
    hybrid_names = ['[TD1-IC] OccultHybrid.package', '[TwelfthDoctor1] OccultTurnActionsUnlocker.package',
                    '[TD1-IC] Hybrid - Plantsim Interactions.package', '[TD1-IC] Hybrid - Servo Interactions.package']
    groups = {
        'ApexOccultHybrid.package': [hybrid_archive + '/' + name for name in hybrid_names],
        'ApexCASUnlocks.package': sorted(name for name in sources if name.startswith('Crilender-v1.9h/')),
        'ApexColorStudio.package': sorted(name for name in sources if 'ColorSlidersUI' in name),
        'Optional/ApexPlantSimPermanent.package': [hybrid_archive + '/[TD1-IC] Hybrid - Plantsim Permanent.package'],
        'Optional/ApexPlantSimNoVampireThirst.package': [hybrid_archive + '/[TD1-IC] Hybrid - Plantsim No Vampire Thirst.package'],
        'Optional/ApexServoNoVampireThirst.package': [hybrid_archive + '/[TD1-IC] Hybrid - Servo No Vampire Thirst.package']}
    fairy = 'Crilender-v1.9h/Crilender_CASUnlocks_v1_9h_Addon_Fairy.package'
    overrides = {'545AC67A:005A8351:00000000000654BA': fairy, '545AC67A:005A8351:00000000000654BB': fairy}
    manifests = []
    for filename, names in groups.items():
        inputs = [(name, dbpf.read(sources[name])) for name in names]
        resources, owners, overlaps = dbpf.merge(inputs, overrides if filename == 'ApexCASUnlocks.package' else {})
        records, migrated = [], {}
        for key, payload in sorted(resources.items()):
            adapted = migrate_xml(payload) if filename == 'ApexOccultHybrid.package' else payload
            migrated[key] = adapted
            records.append({'tgi': dbpf.tgi(key), 'owner': owners[key], 'baseline_content_sha256': dbpf.digest(payload),
                            'content_sha256': dbpf.digest(adapted), 'namespace_adapted': payload != adapted,
                            'current_game_semantics_verified': False})
        raw = dbpf.build(migrated)
        target = output / filename
        atomic_bytes(target, raw)
        manifest = {'schema': 1, 'artifact': filename, 'status': 'authorized-baseline-development-candidate',
                    'target_game_version': '1.128.90.1030', 'runtime_verified': False,
                    'sha256': dbpf.digest(raw), 'bytes': len(raw), 'resources': records,
                    'resource_count': len(records), 'resource_types': dict(sorted(collections.Counter('{:08X}'.format(key[0]) for key in migrated).items())),
                    'resolved_overlaps': overlaps, 'required_baseline_files_at_runtime': [],
                    'input_packages': [{'file': name, 'sha256': dbpf.digest(sources[name])} for name in names],
                    'identity_policy': 'Existing tuning IDs preserved for compatibility; module ownership migrated into apex_hybrid.',
                    'limitations': ['Owner runtime/current-game parity validation pending.',
                                    'Color UI migration does not include the missing converted texture catalog.' if filename == 'ApexColorStudio.package' else 'Further policy/current-game generation and improvement remain tracked in the canonical master.']}
        write_json(target.with_name(target.name + '.manifest.json'), manifest)
        manifests.append(manifest)
    return manifests


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, default=ROOT / '.work' / 'baselines')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps([{'artifact': row['artifact'], 'sha256': row['sha256'], 'resources': row['resource_count']} for row in build(args.baseline, args.output)], indent=2))
