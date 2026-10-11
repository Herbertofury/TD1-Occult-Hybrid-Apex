"""Build the separately licensed SimRipper-based, no-window preview worker.

The complete pinned upstream archive and these transformations are the worker's
corresponding source. No game process, profile or installed tool is modified.
"""
import argparse
import hashlib
import re
from pathlib import Path
import shutil
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
COMMIT = '862a32949e5156b371e2d2f83de4e37e0bb1afcc'
SOURCES = ('https://codeload.github.com/CmarNYC-Tools/TS4SimRipper/zip/' + COMMIT,
           '64944a9e004a427de20505aac305d3516a1f9e94648337cf07e86f8dff139366')
DEPENDENCIES = ('https://github.com/CmarNYC-Tools/TS4SimRipper/releases/download/3.14.2.11/CmarNYC_TS4SimRipper_3_14_2_11.zip',
                '182b4cfa22b3a01eb20c192cdd24b43a61687d3d6ae32d529cb2b87ed5d17bb4')


def fetch(url, expected, path):
    if not path.exists():
        raw = urllib.request.urlopen(url, timeout=90).read(32 * 1024 * 1024 + 1)
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('Preview build dependency hash differs.')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream: stream.write(raw)
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError('Cached preview dependency differs.')
    return path


def main():
    cache = ROOT / '.work' / 'preview-worker'
    cache.mkdir(parents=True, exist_ok=True)
    source_zip = fetch(*SOURCES, cache / 'source.zip')
    dependencies_zip = fetch(*DEPENDENCIES, cache / 'dependencies.zip')
    source, deps = cache / 'source', cache / 'dependencies'
    for archive, destination in ((source_zip, source), (dependencies_zip, deps)):
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                path = destination / info.filename
                if path.resolve() != destination.resolve() and destination.resolve() not in path.resolve().parents:
                    raise ValueError('Build archive path leaves the worker cache.')
            z.extractall(destination)
    upstream = source / ('TS4SimRipper-' + COMMIT)
    src = upstream / 'src'
    # Refuse dialogs, window activation and persistent settings. The upstream
    # UI controls remain hidden input holders for its existing assembly code.
    for path in src.rglob('*.cs'):
        text = path.read_text(encoding='utf-8-sig')
        text = text.replace('MessageBox.Show(', 'ApexDialog.Fail(')
        text = text.replace('Properties.Settings.Default.Save();', '/* Process-local worker settings. */')
        text = text.replace('FileStream log', 'Stream log')
        if path.name == 'DMAP.cs':
            assert text.count('public class DMap') == 1
            text = text.replace('public class DMap','public partial class DMap')
            needle = 'this.version = br.ReadUInt32();'
            assert text.count(needle) == 1
            text = text.replace(needle,needle+'\n            if(this.version==9){ApexReadModern(br);return;}\n            if(this.version>7)throw new InvalidDataException("Unsupported deformer version.");')
            needle = 'public MorphMap ToMorphMap()\n        {'
            assert text.count(needle) == 1
            text = text.replace(needle,needle+'\n            if(this.version==9)return ApexModernMorph();')
        if path.name == 'Form1.cs':
            needle='morphs.face_modifiers != null ? morphs.face_modifiers : new List<EA.Sims4.Persistence.BlobSimFacialCustomizationData.Modifier>()'
            assert text.count(needle)==2
            text=text.replace(needle,'ApexEffectiveFaceModifiers(morphs)')
            needle='morphs.body_modifiers != null ? morphs.body_modifiers : new List<EA.Sims4.Persistence.BlobSimFacialCustomizationData.Modifier>()'
            assert text.count(needle)==2
            text=text.replace(needle,'ApexEffectiveBodyModifiers(morphs)')
            assert 'starter.Show();' in text and 'starter.Close();' in text
            text = text.replace('starter.Show();', '/* Never show a worker window. */')
            text = text.replace('starter.Close();', 'starter.Dispose();')
            # WPF's scene is not needed: the native F11 renderer receives the
            # exact assembled meshes/textures and its own independent rig.
            text = re.sub(r'morphPreview1\.Start_Mesh\([^;]+;', '/* Native preview owns rendering. */', text)
            text = text.replace('log = File.Open(logPath, FileMode.Create, FileAccess.Write);', 'log = Stream.Null;')
            text = text.replace('FileStream log', 'Stream log')
            # Don't accumulate copies of every CC resource in the upstream
            # troubleshooting packages when thousands of Sims are inspected.
        text = re.sub(r'if \(notBaseGame\[i\]\) SaveStream\([^;]+;', '/* In-place resource reads only. */', text)
        if path.name == 'GameFileHandler.cs':
            # These methods exist solely to collect troubleshooting copies.
            # Leaving any call active would accumulate every selected Sim's
            # custom resources even though no package is exported.
            text = re.sub(r'pack\.AddResource\([^;]+;', '/* No troubleshooting resource copies. */', text)
        if path.name == 'GameFileHandler.cs':
            needle = 'new Predicate<IResourceIndexEntry>(r => r.ResourceType == (uint)ResourceTypes.Sculpt),'
            assert needle in text
            text = text.replace(needle, 'new Predicate<IResourceIndexEntry>(r => r.ResourceType == 0x6B20C4F3),\n                ' + needle)
        path.write_text(text, encoding='utf-8')
    for path in (ROOT / 'PreviewWorker').glob('*.cs'):
        shutil.copy2(path, src / path.name)
    project = src / 'TS4SimRipper.NET.csproj'
    xml = project.read_text(encoding='utf-8-sig')
    xml = xml.replace('<OutputType>WinExe</OutputType>', '<OutputType>Exe</OutputType>')
    xml = xml.replace('<TargetFrameworks>net6.0-windows;net8.0-windows</TargetFrameworks>',
                      '<TargetFramework>net8.0-windows</TargetFramework><StartupObject>TS4SimRipper.ApexWorker</StartupObject>')
    xml = xml.replace('<AssemblyName>TS4SimRipper</AssemblyName>', '<AssemblyName>ApexPreviewWorker</AssemblyName>')
    project.write_text(xml, encoding='utf-8')
    output = cache / 'bin'
    subprocess.run(['dotnet', 'build', str(project), '-c', 'Release', '-o', str(output),
                    '-p:S4PI_LIB=' + str(deps), '--nologo'], cwd=ROOT, check=True)
    for path in deps.iterdir():
        if path.suffix in ('.dll', '.package', '.grannyrig') and path.name != 'TS4SimRipper.dll':
            shutil.copy2(path, output / path.name)
    shutil.copy2(upstream / 'LICENSE', output / 'SimRipper-LICENSE.txt')
    provenance = {'upstream': 'https://github.com/CmarNYC-Tools/TS4SimRipper', 'commit': COMMIT,
                  'source_url': SOURCES[0], 'source_sha256': SOURCES[1],
                  'dependency_url': DEPENDENCIES[0], 'dependency_sha256': DEPENDENCIES[1],
                  'adapters': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / 'PreviewWorker').glob('*.cs')},
                  'recipe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    import json
    (output / 'provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
    # Distribute the complete corresponding source beside the helper. This
    # includes the pinned upstream sources, adapters and build recipe.
    with zipfile.ZipFile(output / 'corresponding-source.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        with zipfile.ZipFile(source_zip) as original:
            for info in original.infolist():
                if not info.is_dir(): archive.writestr(info, original.read(info))
        for p in (ROOT / 'PreviewWorker').glob('*.cs'): archive.write(p, 'PreviewWorker/' + p.name)
        archive.write(Path(__file__), 'tools/build_preview_worker.py')
    print(output / 'ApexPreviewWorker.exe')


if __name__ == '__main__': main()
