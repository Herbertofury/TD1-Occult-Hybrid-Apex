"""Build the CAS semantic bridge from a user's exact installed UI resource.

Only the compiled DoABC tag is substituted. Every other original tag, including
Scaleform extensions FFDec cannot decode, remains byte-for-byte unchanged.
Game files are read only; proprietary source exports stay in ignored work.
"""
import argparse
import hashlib
import json
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
    source = re.sub(r'\s*\[Embed\([^\n]*\)\]', '', source)
    end = source.rfind('   }')
    if end < 0: raise ValueError('CAS class end is missing.')
    return source[:end] + methods + '\n' + source[end:]


def run(args):
    proc = subprocess.run([str(x) for x in args], text=True, encoding='utf-8',
                          errors='replace', capture_output=True, timeout=120)
    if proc.returncode: raise ValueError(proc.stdout[-1500:] + proc.stderr[-1500:])
    return proc


def build(input_swf, decompiled, ffdec, output):
    original = Path(input_swf).read_bytes()
    if hashlib.sha256(original).hexdigest() != PIN:
        raise ValueError("Installed CAS resource differs from the inspected 1.128.90 build.")
    work = ROOT / '.work' / 'research'
    patched = work / 'ApexCASCustomizerMain.as'
    patched.write_text(inject(Path(decompiled).read_text(encoding='utf-8'),
        (ROOT / 'Source/CASUi/semantic_methods.as').read_text(encoding='utf-8')), encoding='utf-8')
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
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_bytes(dbpf_build.build({KEY: payload}))
    info = {'schema': 1, 'artifact': Path(output).name, 'scope': 'native-CAS-semantic-bridge',
        'target_game': '1.128.90.1030', 'base_resource_sha256': hashlib.sha256(original).hexdigest(),
        'patched_resource_sha256': hashlib.sha256(payload).hexdigest(),
        'sha256': hashlib.sha256(Path(output).read_bytes()).hexdigest(),
        'runtime_verified': False, 'non_script_tags_preserved': True, 'native_bytecode_contract': contract,
        'resources': [dbpf_build.tgi(KEY)], 'transport': 'fixed loopback CAS socket, native CAS acknowledgement',
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
    a = p.parse_args()
    print(json.dumps(build(a.input_swf, a.decompiled, a.ffdec, a.output), indent=2))
