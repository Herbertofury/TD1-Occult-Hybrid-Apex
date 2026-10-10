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
PINNED_SOURCES = ('Source/CASUi/semantic_methods.as', 'tools/CasBytecodePatch.java',
                  'Source/CASUi/selector_methods.as', 'tools/CasSelectorBytecodePatch.java',
                  'Source/apex_core/cas_panels.py', 'Source/apex_core/cas_controls.py')


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
    source = source.replace('   import ', '   import flash.utils.describeType;\n   import gamedata.CAS.shared.CASCatalogFilter;\n   import ', 1)
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


def build(input_swf, decompiled, ffdec, output, selector_swf=None, selector_decompiled=None, cleanup_library=None):
    expected_sources = source_pins()
    semantic = (ROOT / 'Source/CASUi/semantic_methods.as').read_text(encoding='utf-8')
    control_dispatch = verify_control_dispatch(semantic)
    detached_snapshot_getters = verify_snapshot_ownership(semantic)
    original = Path(input_swf).read_bytes()
    if hashlib.sha256(original).hexdigest() != PIN:
        raise ValueError("Installed CAS resource differs from the inspected 1.128.90 build.")
    work = ROOT / '.work' / 'research'
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
    # The general AS compiler changes native methods' lexical scope. It is
    # used only to obtain Apex methods; original game bytecode stays intact.
    retained = work / 'apex-cas-retained.abc'
    verification = run(['java', '-cp', Path(ffdec).parent / 'ffdec.jar', ROOT / 'tools/CasBytecodePatch.java', input_swf, compiled, retained])
    contract = json.loads(verification.stdout)
    native_tag = next(t[3] for t in tags(unpack(original)[1]) if t[0] == 82)
    boundary = native_tag.index(b'\0', 4) + 1
    payload = replace_payload(original, native_tag[:boundary] + retained.read_bytes())
    selector_source = work / 'ApexCASSelectorMain.as'
    selector_source.write_text(inject_selector(selector_decompiled.read_text(encoding='utf-8'),
        (ROOT / 'Source/CASUi/selector_methods.as').read_text(encoding='utf-8')), encoding='utf-8')
    selector_compiled = work / 'apex-cas-selector-compiled.swf'
    run([ffdec, '-importAssets', 'yes,local', '-replace', selector_swf, selector_compiled, SELECTOR_CLASS, selector_source])
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
    if source_pins() != expected_sources:
        raise ValueError('CAS bridge source changed during compilation; no package was written.')
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_bytes(dbpf_build.build({KEY: payload, SELECTOR_KEY: selector_payload}))
    info = {'schema': 1, 'artifact': Path(output).name, 'scope': 'native-CAS-semantic-bridge',
        'source_pins': expected_sources,
        'typed_control_dispatch_verified': control_dispatch,
        'detached_snapshot_getters': detached_snapshot_getters,
        'target_game': '1.128.90.1030', 'base_resource_sha256': hashlib.sha256(original).hexdigest(),
        'patched_resource_sha256': hashlib.sha256(payload).hexdigest(),
        'sha256': hashlib.sha256(Path(output).read_bytes()).hexdigest(),
        'runtime_verified': False, 'non_script_tags_preserved': True, 'native_bytecode_contract': contract,
        'selector_native_bytecode_contract': selector_contract,
        'base_resources': {dbpf_build.tgi(KEY): PIN, dbpf_build.tgi(SELECTOR_KEY): SELECTOR_PIN},
        'unmodified_dependency_resources': {dbpf_build.tgi(CLEANUP_KEY): CLEANUP_PIN},
        'patched_resources': {dbpf_build.tgi(KEY): hashlib.sha256(payload).hexdigest(),
                              dbpf_build.tgi(SELECTOR_KEY): hashlib.sha256(selector_payload).hexdigest()},
        'resources': [dbpf_build.tgi(KEY), dbpf_build.tgi(SELECTOR_KEY)], 'transport': 'fixed loopback CAS socket, native CAS acknowledgement',
        'socket_protocol': {'host': '127.0.0.1', 'port': 8021, 'length_digits': 8,
            'encoding': 'utf-8', 'maximum_frame_bytes': 131072, 'poll_interval_ms': 500}}
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
    a = p.parse_args()
    print(json.dumps(build(a.input_swf, a.decompiled, a.ffdec, a.output, a.selector_swf, a.selector_decompiled, a.cleanup_library), indent=2))
