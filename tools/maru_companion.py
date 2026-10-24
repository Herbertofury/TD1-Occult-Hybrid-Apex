"""Import the owner's exact Dynamic CAS Companion code and dependent resources.

The donor is a build input, never an additional competing installed override.
EA-derived decompiled sources remain private. The compiled donor ABC is the
retention baseline; Apex's existing bytecode adapter preserves all unselected
methods, including donor helpers and their nested functions.
"""
import hashlib
import json
from pathlib import Path
import subprocess

import dbpf_build

PACKAGE_SHA256 = '054ca6a189a587063290df004a42072c5381e59404d33e58ddb737ab821cf9c3'
CUSTOMIZER = (0x62ECC59A, 0, 0xDF09D526F4C77B95)
CUSTOMIZER_SHA256 = 'c97afa8f0362a0452b359074769b9c99174444dd211927d08972091db3391969'
RESOURCE_COUNT = 66


def expected_resources():
    return json.loads(Path(__file__).with_name('maru_companion_resources.json').read_text(encoding='utf-8'))


def read_package(path):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PACKAGE_SHA256:
        raise ValueError('Dynamic CAS donor differs from the reviewed owner-supplied package.')
    resources = dbpf_build.read(raw)
    if (len(resources) != RESOURCE_COUNT or
            {dbpf_build.tgi(k): dbpf_build.digest(v) for k, v in resources.items()} != expected_resources()):
        raise ValueError('Dynamic CAS donor resource inventory differs.')
    return resources


def prepare(path, ffdec, work):
    resources = read_package(path)
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    customizer = work / 'DynamicCASCustomizer.swf'
    customizer.write_bytes(resources[CUSTOMIZER])
    # Preserve the exact donor imports and definitions, rather than recompiling
    # its classes from text or relying on another mod to provide them at runtime.
    exported = work / 'customizer'
    result = subprocess.run([str(ffdec), '-export', 'script', str(exported), str(customizer)],
                            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
    if result.returncode:
        raise ValueError('Dynamic CAS source inspection failed: ' + result.stderr[-1200:])
    scripts = exported / 'scripts'
    source = scripts / 'widgets/CAS/Customizer/CASCustomizerMain.as'
    if not source.is_file() or 'HistoryHost.Attach(this)' not in source.read_text(encoding='utf-8'):
        raise ValueError('Dynamic CAS compiled history coordinator is absent.')
    rows = {dbpf_build.tgi(key): dbpf_build.digest(data) for key, data in resources.items()}
    return dict(package_sha256=PACKAGE_SHA256, customizer_sha256=CUSTOMIZER_SHA256,
                resource_count=RESOURCE_COUNT, resource_sha256=rows,
                customizer=str(customizer), decompiled=str(source), scripts=str(scripts),
                method='donor-ABC-with-retained-Apex-adapters', runtime_verified=False)


def combine(path, apex, evidence):
    resources = read_package(path)
    if evidence.get('resource_sha256') != {dbpf_build.tgi(k): dbpf_build.digest(v) for k, v in resources.items()}:
        raise ValueError('Dynamic CAS donor changed after compilation.')
    # An overlap must be the reviewed customizer. Other Apex native UI resources
    # cannot be silently replaced by a donor, even if a later version adds them.
    if set(resources) & set(apex) != {CUSTOMIZER}:
        raise ValueError('Unreviewed Dynamic CAS/Apex resource overlap.')
    resources.update(apex)
    return resources


def verify_merged(info, resources):
    """Bundle gate independent of the owner's donor path and compiler scratch."""
    evidence = info.get('companion_code_merge')
    if not isinstance(evidence, dict) or evidence.get('package_sha256') != PACKAGE_SHA256:
        raise ValueError('Missing exact Dynamic CAS merge identity.')
    expected = expected_resources()
    actual = {dbpf_build.tgi(k): dbpf_build.digest(v) for k, v in resources.items()}
    if (evidence.get('resource_sha256') != expected or evidence.get('resource_count') != RESOURCE_COUNT or
            evidence.get('customizer_sha256') != CUSTOMIZER_SHA256 or
            evidence.get('method') != 'donor-ABC-with-retained-Apex-adapters'):
        raise ValueError('Dynamic CAS input provenance differs from the reviewed donor.')
    for key, digest in expected.items():
        if key != dbpf_build.tgi(CUSTOMIZER) and actual.get(key) != digest:
            raise ValueError('A retained Dynamic CAS dependency changed or is absent: ' + key)
    contract = info.get('native_bytecode_contract', {})
    if (contract.get('native_method_count') != 2650 or contract.get('unchanged_native_methods') != 2632 or
            contract.get('companion_named_form_adapters') != 5 or
            contract.get('native_pelt_palette_reenable_verified') is not True):
        raise ValueError('The complete donor ABC did not pass retained-method verification.')
    return True
