"""Hash-bound appearance sidecars for controlled disposable saves and reloads.

An unsealed bank never authorizes a write. A seal binds the actual changed save
file, selected bank, native Sim/household/GUID, token and exact script. Reload
reconciliation also requires an unchanged native load receipt, so subsequent
unsaved native edits cannot be replaced by an older sidecar.

One separate explicit disposable migration epoch binds the known A0 predecessor,
the audited target source/bytecode and immutable seal. It never grants automatic
product recovery or authorizes an unmarked profile.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import types
import uuid
import zipfile
from . import form_appearance as appearance, form_bank
from .overlay_loader import _unlinked

FORMS = (1, 2, 4, 8, 16, 32, 64)
MAX_BYTES = 48 * 1024 * 1024
CONTRACT = hashlib.sha256(json.dumps({'version': 2, 'fields': appearance.FIELDS,
    'genetics': 'complete-wire-native-exact-growth-dedup',
    'outfits': 'complete-category-normalized-protobuf', 'ownership': 'stored-and-active-separate'},
    sort_keys=True).encode('ascii')).hexdigest()
_LOADED = {}
# Prior v1 receipts remain immutable and cannot authorize this source epoch.
UPGRADE_EPOCH = '2026-10-10-native-existing-kind-appearance-context-v33'
UPGRADE_PREDECESSOR = 'a0dff198bd8bf778c440883baf58d83e695b0a26e3d2b7a491e315fcbabf34ce'
UPGRADE_SELF_BODY_SHA = '6e6e756269e0bb4ec3a5de4ac18278637d4d1104441eddc01af59eaa45c0b15a'
UPGRADE_MODULE_PINS = {
    'apex_core/bank_history.py': '3cca2e11f64f1f9bda0602984db0eda2f6b9d24abeb91b544c5353fc71034331',
    'apex_core/cas_bank_transaction.py': 'c280b7de5ebef550cb71588d2394cb5ede3a559a73895071c352655726f8f8ed',
    'apex_core/cas_commit_plan.py': '77a5eda1eb8f1b2706f7e76cfbd27a95597d4676e8a9833c4721d6737c08e00d',
    'apex_core/cas_controls.py': '090e8c7fe0c879899bd34e7363b79d68ba2159e3524b8b00cf5016c1e81fbfb9',
    'apex_core/cas_panels.py': '3c87dea0c46651915b773d5ec8e9e33b96a58fa4c8b34ba49c2ae36e0eb99374',
    'apex_core/cas_room.py': '1d5ecb8c558f988674f4303ea7506e620a38d3d5b4392e6f7653aedd783d182f',
    'apex_core/cas_ui.py': 'd4d9d3c9786d14257884edcda95e04c979e609065945db5dbe7a79574f776c73',
    'apex_core/change_journal.py': 'b8442037e86dc04334a375daf86471992dffa617bc7d36ea5c84a6c4563c0d2e',
    'apex_core/form_appearance.py': 'e5b8d7832ad09f3877123f701192b74e15f38a4599af7da3bd672b24b2d0ae5f',
    'apex_core/form_bank.py': '9f5ca22186122ab6982c88ed0252a3b2048757cf1cc411555a639ef5d71d4434',
    'apex_core/genetics_snapshot.py': '8fefbe2898884cfbc8aab7675d3ff169f376848175d9f0ee7277e2d75bc73640',
    'apex_core/hybrid_persistence.py': 'd63b42795401435cb37ec37f8de9f898a664b203797ed63b6df9d0c186a20379',
    'apex_core/legacy_phone_guard.py': '097e88240ed8828101de5389c8f966a76e2c393b821f0580808735b663b600cd',
    'apex_core/native_form_select.py': '5c3c9b28d82df3e6515169f3bb653f94ed9c9505d7745673514d85ed79744c44',
    'apex_core/native_occult_context.py': '4b1fb7278a8719ff58c5b2b1a97aaa89a9e5e953915a31ab212206a67928b186',
    'apex_core/outfit_hair.py': '530fb5e8f5e80137b3607e55a796a6423648f0ff25b6780f3430b8361d2f61d8',
    'apex_core/outfit_snapshot.py': '76d2feeb0104a8bba9dc341ba7276c1357475781d17b33749a81df5adb123a56',
    'apex_core/overlay_loader.py': 'ab45896f36af7ce23290fbd3a1e43819f020b61988d791876742dbb417742263',
    'apex_core/phone_cas.py': 'd36633ac04f225e57e060239b5bd27d358707b876ee10bcef734f1e928bca3c6',
    'apex_core/phone_interactions.py': '033c9b9f788adb075f7519ec8ff90994d22fbeb0861aa22eba216cefec0aae0d',
    'apex_core/sim_data.py': 'e82260f1aef92190a070cea76dbd63c3cfef33689f40297b83c03290eb19794e',
    'apex_core/studio.py': '36446997face1dc68281cd6c1b6ba8220263250f1d1c5a0f4878a16cb252b0be',
    'apex_core/test_driver.py': '6a1f1674e26087705cb87f90b37cb1da2de97beba7ec0b85dbdfff03410f03b2',
    'td1_occult_hybrid_apex.py': '2c194763e74aa761b1bea2832da87b2fdcbb08eabc2fa328c0d27a6232aed363',
}
_SEAL_FIELDS = ('intent_id', 'identity', 'contract_sha256', 'target',
                'bank_record_sha256', 'appearances', 'file_sha256')


def upgrade_source_hash(name, raw):
    if name == 'apex_core/form_bank_seal.py':
        lines = raw.splitlines(keepends=True)
        selected = [index for index, line in enumerate(lines) if line.startswith(b'UPGRADE_SELF_BODY_SHA = ')]
        if len(selected) != 1:
            raise ValueError('Upgrade receiver self-pin declaration differs.')
        line = lines[selected[0]]
        end = b'\r\n' if line.endswith(b'\r\n') else b'\n' if line.endswith(b'\n') else b''
        content = line[:-len(end)] if end else line
        prefix = b"UPGRADE_SELF_BODY_SHA = '"
        if (len(content) != len(prefix) + 65 or not content.startswith(prefix) or not content.endswith(b"'") or
                any(value not in b'0123456789abcdef' for value in content[len(prefix):-1])):
            raise ValueError('Upgrade receiver self-pin must be one literal hash, with no appended code.')
        lines[selected[0]] = b"UPGRADE_SELF_BODY_SHA = '<pinned>'" + end
        raw = b''.join(lines)
    return hashlib.sha256(raw).hexdigest()


def upgrade_archive(raw, manifest):
    """Validate bounded build evidence and exact audited recovery source pins.

    Returns plain member bytes for host compilation or loaded-code comparison;
    never imports/executes archive code and accepts no filesystem paths.
    """
    if (not isinstance(raw, bytes) or not 0 < len(raw) <= 16 * 1024 * 1024 or
            not isinstance(manifest, dict) or type(manifest.get('schema')) is not int or manifest['schema'] != 1 or
            manifest.get('artifact') != 'ApexOccultHybrid.ts4script' or manifest.get('sha256') != hashlib.sha256(raw).hexdigest()):
        raise ValueError('Upgrade target archive/build identity differs.')
    compiler = manifest.get('compiler', {})
    if (not isinstance(compiler, dict) or compiler.get('magic') != '420d0d0a' or compiler.get('invalidation') != 'PEP 552 checked source hash' or
            type(compiler.get('hash_seed')) is not int or compiler['hash_seed'] != 0):
        raise ValueError('Upgrade target compiler contract differs.')
    source_rows, compiled_rows = manifest.get('modules'), manifest.get('compiled_modules')
    if not isinstance(source_rows, list) or not isinstance(compiled_rows, list):
        raise ValueError('Upgrade target module inventory is unavailable.')
    rows = source_rows + compiled_rows
    if not 0 < len(rows) <= 256 or any(not isinstance(row, dict) for row in rows):
        raise ValueError('Upgrade target module inventory exceeds its bound.')
    names = [row.get('module') for row in rows]
    if any(not isinstance(name, str) for name in names) or len(set(name.casefold() for name in names)) != len(names):
        raise ValueError('Upgrade target module inventory is ambiguous.')
    if (any(not row['module'].endswith('.py') for row in source_rows) or
            any(not row['module'].endswith('.pyc') for row in compiled_rows)):
        raise ValueError('Upgrade source/compiled module inventories differ.')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        if (len(infos) != len(rows) or sum(row.file_size for row in infos) > 32 * 1024 * 1024 or
                set(row.filename for row in infos) != set(names) or len({row.filename.casefold() for row in infos}) != len(infos)):
            raise ValueError('Upgrade target ZIP inventory differs.')
        for row in infos:
            if (row.is_dir() or row.file_size > 4 * 1024 * 1024 or '\\' in row.filename or ':' in row.filename or
                    row.filename.startswith('/') or '..' in row.filename.split('/') or (row.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError('Upgrade target ZIP member is unsafe.')
        members = {}
        for row in rows:
            value = archive.read(row['module'])
            if type(row.get('bytes')) is not int or row['bytes'] != len(value) or not _sha(row.get('sha256')) or hashlib.sha256(value).hexdigest() != row['sha256']:
                raise ValueError('Upgrade target member differs from its build manifest.')
            members[row['module']] = value
    pins = dict(UPGRADE_MODULE_PINS, **{'apex_core/form_bank_seal.py': UPGRADE_SELF_BODY_SHA})
    for name, expected in pins.items():
        if name not in members or upgrade_source_hash(name, members[name]) != expected:
            raise ValueError('Upgrade target recovery source is not this audited epoch: ' + name)
        if name == 'apex_core/form_bank_seal.py' and ("UPGRADE_SELF_BODY_SHA = '" + expected + "'").encode('ascii') not in members[name].splitlines():
            raise ValueError('Upgrade target receiver pin literal differs.')
        compiled = members.get(name[:-3] + '.pyc', b'')
        if len(compiled) <= 16 or compiled[:8] != b'\x42\x0d\x0d\x0a\x03\x00\x00\x00':
            raise ValueError('Upgrade target recovery bytecode header differs.')
    return members


def _code_identity(code):
    def constant(value):
        if isinstance(value, types.CodeType):
            return ['code', _code_identity(value)]
        if isinstance(value, bytes):
            return ['bytes', value.hex()]
        if isinstance(value, (tuple, frozenset)):
            values = [constant(item) for item in value]
            return [type(value).__name__, sorted(values, key=_bytes) if isinstance(value, frozenset) else values]
        if value is None or isinstance(value, (str, int, float, bool)):
            return [type(value).__name__, value]
        if value is Ellipsis:
            return ['ellipsis']
        raise ValueError('Upgrade compiled constant has an unsupported type.')
    return _hash({'args': code.co_argcount, 'kwonly': code.co_kwonlyargcount,
        'flags': code.co_flags, 'code': code.co_code.hex(), 'names': code.co_names,
        'vars': code.co_varnames, 'free': code.co_freevars, 'cells': code.co_cellvars,
        'file': code.co_filename, 'name': code.co_name, 'line': code.co_firstlineno,
        'constants': [constant(value) for value in code.co_consts]})


def _verify_loaded_upgrade(members, archive):
    import ast
    import importlib
    import importlib.util
    import marshal
    if sys.version_info[:2] != (3, 7):
        raise ValueError('Upgrade receiver requires the running Sims Python 3.7.')
    for name in list(UPGRADE_MODULE_PINS) + ['apex_core/form_bank_seal.py']:
        expected = compile(members[name], name, 'exec', dont_inherit=True, optimize=0)
        if members[name[:-3] + '.pyc'][8:16] != importlib.util.source_hash(members[name]):
            raise ValueError('Upgrade bytecode checked-source hash differs.')
        stream = io.BytesIO(members[name[:-3] + '.pyc'][16:])
        try:
            compiled = marshal.load(stream)
        except (ValueError, EOFError, TypeError):
            raise ValueError('Upgrade bytecode cannot be read as bounded Python 3.7 code.')
        if stream.read(1):
            raise ValueError('Upgrade bytecode has trailing data outside its compiled code.')
        if not isinstance(compiled, types.CodeType) or _code_identity(compiled) != _code_identity(expected):
            raise ValueError('Upgrade bytecode does not compile from the audited source.')
        allowed = set()
        def visit(code):
            allowed.add(_code_identity(code))
            for value in code.co_consts:
                if isinstance(value, types.CodeType): visit(value)
        visit(expected)
        module = importlib.import_module(name[:-3].replace('/', '.'))
        module_file = str(getattr(module, '__file__', '')).replace('\\', '/')
        root = str(archive).replace('\\', '/') + '/'
        if module_file.casefold() not in {(root + name).casefold(), (root + name[:-3] + '.pyc').casefold()}:
            raise ValueError('Upgrade receiver module came from another archive: ' + name)
        for node in ast.parse(members[name], filename=name).body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                value = vars(module).get(node.name)
                expected_type = types.FunctionType if isinstance(node, ast.FunctionDef) else type
                if not isinstance(value, expected_type) or value.__module__ != module.__name__:
                    raise ValueError('Upgrade receiver lacks an audited loaded declaration: ' + name)
        found = 0
        values = list(vars(module).values())
        for value in list(values):
            if isinstance(value, type) and value.__module__ == module.__name__:
                for member in vars(value).values():
                    if isinstance(member, (staticmethod, classmethod)): values.append(member.__func__)
                    elif isinstance(member, property): values.extend(fn for fn in (member.fget, member.fset, member.fdel) if fn is not None)
                    else: values.append(member)
        for value in values:
            if isinstance(value, types.FunctionType) and value.__module__ == module.__name__:
                found += 1
                if value.__globals__ is not vars(module) or _code_identity(value.__code__) not in allowed:
                    raise ValueError('Upgrade receiver loaded code differs: ' + name)
        if found == 0:
            raise ValueError('Upgrade receiver loaded functions are unavailable: ' + name)


def upgrade_artifacts(rows):
    if not isinstance(rows, list) or len(rows) != 14:
        raise ValueError('This migration requires the complete fourteen-artifact inventory.')
    result = {}
    apex = {'Apex/' + name for name in ('ApexOccultHybrid.package', 'ApexOccultHybrid.ts4script',
        'ApexCASUnlocks.package', 'ApexCASBridge.package', 'ApexPlantSimPermanent.package',
        'ApexPlantSimNoVampireThirst.package', 'ApexServoNoVampireThirst.package')}
    apex.update('Apex/Native/' + name for name in ('ApexOverlay.dll', 'ApexOverlay.ini', 'overlay-manifest.json'))
    mccc = {'MCCC/' + name for name in ('mc_cmd_center.package', 'mc_cmd_center.ts4script', 'mc_cas.ts4script', 'mc_dresser.ts4script')}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'relative', 'sha256', 'bytes'}:
            raise ValueError('Upgrade artifact identity is incomplete.')
        name = row['relative']
        cc = (isinstance(name, str) and name.startswith('ApexTest/') and len(name.split('/')) == 2 and
              name.endswith('.package') and '\\' not in name and ':' not in name and '..' not in name.split('/'))
        if (not isinstance(name, str) or name not in apex | mccc and not cc or name.casefold() in result or
                not _sha(row['sha256']) or type(row['bytes']) is not int or not 0 < row['bytes'] <= 64 * 1024 * 1024):
            raise ValueError('Upgrade artifact path/hash/size is unsupported or ambiguous.')
        result[name.casefold()] = row
    return result


def _upgrade_inventory(profile, receipt):
    before, after = upgrade_artifacts(receipt['artifacts_before']), upgrade_artifacts(receipt['artifacts_after'])
    script, native = 'apex/apexocculthybrid.ts4script', 'apex/native/overlay-manifest.json'
    if (set(before) != set(after) or script not in after or native not in after or
            before[script]['sha256'] != UPGRADE_PREDECESSOR or after[script]['sha256'] != receipt['target_sha256'] or
            any(before[name] != after[name] for name in before if name not in (script, native)) or
            type(receipt['generation_before']) is not int or receipt['generation_before'] < 0):
        raise ValueError('Upgrade changed an artifact outside its two exact owned targets.')
    expected = set(after)
    allowed_data = {'resource.cfg', 'apex/td1_occulthybrid_settings.json'}
    allowed_data.update('mccc/' + name for name in ('mc_settings.cfg', 'mc_cas.cfg', 'mc_dresser.cfg', 'mc_cmd_center.log', 'mc_lastexception.html'))
    mods = _unlinked(profile / 'Mods')
    for directory, subdirs, files in os.walk(str(mods), followlinks=False):
        for name in subdirs + files: _unlinked(Path(directory) / name)
        for name in files:
            path = Path(directory) / name
            relative = path.relative_to(mods).as_posix().casefold()
            if relative in allowed_data: continue
            if relative not in expected:
                raise ValueError('Upgrade profile has an unknown or duplicate mod.')
            row = after[relative]
            stat_before = path.stat()
            if stat_before.st_size != row['bytes']:
                raise ValueError('Upgrade retained artifact size changed.')
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                while True:
                    raw = stream.read(1024 * 1024)
                    if not raw: break
                    digest.update(raw)
            stat_after = path.stat()
            if ((stat_before.st_size, stat_before.st_mtime_ns) != (stat_after.st_size, stat_after.st_mtime_ns) or
                    digest.hexdigest() != row['sha256']):
                raise ValueError('Upgrade retained artifact hash changed.')
            expected.remove(relative)
    if expected:
        raise ValueError('Upgrade retained artifact is missing.')


def upgrade_bank_authority(bank, row, receipt, bank_path=None):
    """Exact appearances plus an explicitly certified metadata-only archive.

    Ordinary seals still bind their full original record. This extra case is
    available only within the explicit pinned script migration receipt, and
    retains every current history/metadata field without rewriting the bank.
    """
    if (_hash(bank) != receipt['current_bank_record_sha256'] or bank.get('bank') != row['appearances'] or
            receipt['bank_record_sha256'] != row['bank_record_sha256']):
        raise ValueError('Upgrade bank changed; newer appearances or metadata were preserved.')
    if receipt['current_bank_record_sha256'] == row['bank_record_sha256']:
        if receipt['failed_history_leaf_sha256'] is not None or receipt['metadata_archive_proof'] is not None:
            raise ValueError('Unchanged upgrade bank cannot borrow unrelated archive evidence.')
        return
    evidence = receipt['metadata_archive_proof']
    history = bank.get('failed_history')
    if isinstance(history, list) and history:
        from .bank_history import reference, resolve
        if reference(history[-1]):
            if bank_path is None:
                raise ValueError('Archived upgrade evidence requires its exact bank path.')
            history = list(history)
            history[-1] = resolve(bank_path, history[-1])
    if (not isinstance(evidence, dict) or set(evidence) != {'sha256', 'raw'} or not _sha(evidence['sha256']) or
            not isinstance(evidence['raw'], str) or not 0 < len(evidence['raw'].encode('utf-8')) <= 12 * 1024 * 1024 or
            hashlib.sha256(evidence['raw'].encode('utf-8')).hexdigest() != evidence['sha256'] or
            not _sha(receipt['failed_history_leaf_sha256']) or not isinstance(history, list) or not history or
            not isinstance(history[-1], dict) or _hash(history[-1]) != receipt['failed_history_leaf_sha256']):
        raise ValueError('A changed bank requires the exact retained metadata-archive proof and failed-history leaf.')
    proof = json.loads(evidence['raw'], parse_constant=lambda _value: (_ for _ in ()).throw(ValueError('Nonfinite archive proof.')))
    if not isinstance(proof, dict):
        raise ValueError('Metadata-archive proof must be a typed object.')
    leaf, target = history[-1], row['target']
    prior, identity, pending = proof.get('prior_identity'), proof.get('identity'), leaf.get('pending')
    if (not isinstance(proof, dict) or type(proof.get('schema')) is not int or proof['schema'] != 1 or
            proof.get('operation') != 'archive-unsaved-failed-cas-metadata' or
            proof.get('outcome') != 'failed-transaction-archived-without-appearance-writes' or
            any(proof.get(name) is not True for name in ('ok', 'finalized', 'archive_submitted',
                'failed_history_retained_verified', 'save_file_unchanged_verified', 'other_records_unchanged_verified', 'native_live_identity_verified')) or
            any(proof.get(name) is not False for name in ('appearance_mutated', 'bank_lanes_changed', 'save_submitted')) or
            not isinstance(prior, dict) or not isinstance(identity, dict) or not isinstance(pending, dict) or
            any(value.get('script_sha256') != UPGRADE_PREDECESSOR or
                value.get('profile') != row['identity']['profile'] or value.get('test_token') != row['identity']['test_token']
                for value in (prior, identity)) or
            any(type(value.get('pid')) is not int or not 0 < value['pid'] <= 0xffffffff for value in (prior, identity)) or
            prior['pid'] == identity['pid'] or leaf.get('prior_pid') != prior['pid'] or leaf.get('new_pid') != identity['pid'] or
            leaf.get('state') != 'abandoned-unsaved-exit' or leaf.get('metadata_archive_only') is not True or
            leaf.get('appearance_restored') is not False or leaf.get('seal_created') is not False or
            not isinstance(leaf.get('reloaded_file'), dict) or leaf['reloaded_file'].get('sha256') != row['file_sha256'] or
            proof.get('expected_save_sha256') != row['file_sha256'] or proof.get('slot_id') != target['slot_id'] or
            any(proof.get(name) != target[name] or leaf.get(name) != target[name] for name in ('save_guid', 'sim_id', 'household_id')) or
            proof.get('pending_sha256') != leaf.get('pending_sha256') or
            proof.get('failed_return_proof_sha256') != leaf.get('failed_return_proof_sha256') or
            not _sha(proof.get('failed_return_proof_sha256')) or
            proof.get('native_save_slot') != leaf.get('actual_native_slot_id') or
            type(proof.get('native_save_slot')) is not int or proof['native_save_slot'] not in (target['slot_id'], 0xffffffff) or
            type(proof.get('disk_slot_verified')) is not bool or
            proof.get('disk_slot_verified') is not leaf.get('disk_slot_verified') or
            proof['disk_slot_verified'] != (proof['native_save_slot'] == target['slot_id']) or
            proof['native_save_slot'] == 0xffffffff and proof.get('allow_auto_save_slot_metadata_only') is not True):
        raise ValueError('Metadata-archive proof does not bind the original A0 native owners/save/failed session.')
    utf8_hash = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        allow_nan=False, separators=(',', ':')).encode('utf-8')).hexdigest()
    native = pending.get('native_original')
    native_fields = native.get('data', {}).get('fields', []) if isinstance(native, dict) else []
    household = [value for value in native_fields if isinstance(value, dict) and value.get('name') == 'household_id']
    if (pending.get('state') not in ('captured', 'returned', 'reconciling', 'recovery-required') or
            pending.get('runtime_pid') is not None and (type(pending['runtime_pid']) is not int or pending['runtime_pid'] != prior['pid']) or
            utf8_hash(pending) != leaf.get('pending_sha256') or
            not isinstance(native, dict) or native.get('sim_id') != target['sim_id'] or native.get('save_guid') != target['save_guid'] or
            len(household) != 1 or household[0].get('present') is not True or household[0].get('value') != target['household_id'] or
            proof.get('bank_lanes_sha256') != utf8_hash(bank['bank'])):
        raise ValueError('Retained failed-session originals or current bank appearance equality differ.')


def _upgrade_receipt(backend, identity, profile, bank_path, key, seal_path, row):
    path = _unlinked(bank_path.with_name('form_bank_script_upgrade.json'))
    if not path.is_file():
        raise ValueError('No explicit closed-profile script upgrade receipt.')
    value = _read(path)
    if not isinstance(value, dict) or set(value) != {'schema', 'receipt', 'receipt_sha256'} or type(value['schema']) is not int or value['schema'] != 1:
        raise ValueError('No explicit closed-profile script upgrade receipt.')
    receipt = value['receipt']
    fields = {'epoch', 'predecessor_sha256', 'target_sha256', 'profile', 'test_token', 'key', 'old_seal_sha256',
              'old_seal_file_sha256', 'bank_record_sha256', 'file_sha256', 'target', 'build_manifest',
              'build_manifest_sha256', 'artifacts_before', 'artifacts_after', 'generation_before',
              'current_bank_record_sha256', 'failed_history_leaf_sha256', 'metadata_archive_proof'}
    if (not isinstance(receipt, dict) or set(receipt) != fields or _hash(receipt) != value['receipt_sha256'] or
            not all(_sha(receipt.get(name)) for name in ('predecessor_sha256', 'target_sha256', 'old_seal_sha256',
                'old_seal_file_sha256', 'bank_record_sha256', 'current_bank_record_sha256', 'file_sha256', 'build_manifest_sha256')) or
            receipt['epoch'] != UPGRADE_EPOCH or receipt['predecessor_sha256'] != UPGRADE_PREDECESSOR or
            receipt['target_sha256'] == UPGRADE_PREDECESSOR or receipt['target_sha256'] != identity['script_sha256'] or
            receipt['profile'] != str(profile) or receipt['test_token'] != identity['test_token'] or receipt['key'] != key or
            row['identity']['script_sha256'] != UPGRADE_PREDECESSOR or receipt['old_seal_sha256'] != row['seal_sha256'] or
            receipt['target'] != row['target'] or receipt['file_sha256'] != row['file_sha256'] or
            receipt['bank_record_sha256'] != row['bank_record_sha256'] or
            _hash(receipt['build_manifest']) != receipt['build_manifest_sha256']):
        raise ValueError('Explicit script upgrade receipt is altered or mismatched.')
    seal_file = _unlinked(seal_path)
    before = seal_file.stat()
    with seal_file.open('rb') as stream: raw_seal = stream.read()
    after = seal_file.stat()
    if (len(raw_seal) != after.st_size or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or
            hashlib.sha256(raw_seal).hexdigest() != receipt['old_seal_file_sha256']):
        raise ValueError('Original upgrade seal file changed.')
    upgrade_bank_authority(_record(bank_path, key), row, receipt, bank_path)
    from .test_driver import _save_file_evidence
    if _save_file_evidence(profile, row['target']['slot_id'])['sha256'] != receipt['file_sha256']:
        raise ValueError('Upgrade save file changed; newer saves were preserved.')
    archive = _unlinked(profile / 'Mods' / 'Apex' / 'ApexOccultHybrid.ts4script')
    before = archive.stat()
    with archive.open('rb') as stream: raw = stream.read(16 * 1024 * 1024 + 1)
    after = archive.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or hashlib.sha256(raw).hexdigest() != identity['script_sha256']:
        raise ValueError('Upgrade loaded/disk archive identity changed.')
    _upgrade_inventory(profile, receipt)
    members = upgrade_archive(raw, receipt['build_manifest'])
    _verify_loaded_upgrade(members, archive)
    return value['receipt_sha256']


def _source_authority(backend, identity, profile, bank_path, key, seal_path, row):
    old = row.get('identity')
    if (not isinstance(old, dict) or any(old.get(name) != identity.get(name) for name in ('profile', 'test_token')) or
            row.get('contract_sha256') != CONTRACT or any(name not in row for name in _SEAL_FIELDS) or
            _hash({name: row[name] for name in _SEAL_FIELDS}) != row.get('seal_sha256')):
        raise ValueError('Seal native/profile/contract identity differs.')
    if old.get('script_sha256') == identity['script_sha256']:
        return None
    if old.get('script_sha256') != UPGRADE_PREDECESSOR:
        raise ValueError('Seal belongs to another source; only the audited A0 transition is supported.')
    return _upgrade_receipt(backend, identity, profile, bank_path, key, seal_path, row)


def _upgrade_runtime(bank_path, key, row, receipt_hash):
    path = _unlinked(bank_path.with_name('form_bank_upgrade_runtime.json'))
    data = _store(path)
    current = data['records'].get(key)
    if current is None:
        current = json.loads(_bytes(row).decode('ascii'))
        current['upgrade_receipt_sha256'] = receipt_hash
        data['records'][key] = current
    if (not isinstance(current, dict) or current.get('upgrade_receipt_sha256') != receipt_hash or
            any(current.get(name) != row.get(name) for name in _SEAL_FIELDS) or current.get('seal_sha256') != row.get('seal_sha256')):
        raise ValueError('Upgrade runtime recovery record changed.')
    return path, data, current


def _expected_bank_hash(bank_path, row, authority):
    if authority is None:
        return row['bank_record_sha256']
    value = _read(bank_path.with_name('form_bank_script_upgrade.json'))
    if value.get('receipt_sha256') != authority or _hash(value.get('receipt')) != authority:
        raise ValueError('Upgrade authority changed during native recovery.')
    return value['receipt']['current_bank_record_sha256']


def _sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _uuid(value):
    return isinstance(value, str) and len(value) == 32 and all(c in '0123456789abcdef' for c in value)


def _bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(',', ':')).encode('ascii')


def _hash(value):
    return hashlib.sha256(_bytes(value)).hexdigest()


def _read(path):
    path = _unlinked(path)
    before = path.stat()
    with path.open('rb') as stream:
        raw = stream.read()
    after = path.stat()
    if not raw or len(raw) != after.st_size or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Complete sidecar changed during reading.')
    return json.loads(raw.decode('utf-8'), parse_constant=lambda _value: (_ for _ in ()).throw(ValueError('Nonfinite sidecar.')))


def _write(path, value):
    raw = _bytes(value)
    temporary = _unlinked(path.with_suffix('.pending'))
    with temporary.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    os.replace(str(temporary), str(path))


def _store(path):
    value = _read(path) if path.exists() else {'schema': 1, 'records': {}}
    if not isinstance(value, dict) or type(value.get('schema')) is not int or value['schema'] != 1 or not isinstance(value.get('records'), dict):
        raise ValueError('Invalid sealed appearance store.')
    return value


def _identity(backend, sim):
    from .test_driver import runtime_identity, _save_id
    identity = runtime_identity(backend.__file__)
    if (type(identity.get('pid')) is not int or identity['pid'] != os.getpid() or not _uuid(identity.get('test_token')) or
            not _sha(identity.get('script_sha256')) or not isinstance(identity.get('profile'), str) or
            sim is None or not _save_id(str(sim.id)) or not _save_id(str(sim.household_id))):
        raise ValueError('No exact marked native sidecar identity.')
    profile = _unlinked(Path(identity['profile']))
    marker = _unlinked(profile / '.apex-disposable-profile.json')
    if marker.stat().st_size > 4096:
        raise ValueError('Disposable marker exceeds its bound.')
    marked = json.loads(marker.read_text(encoding='utf-8'))
    if not isinstance(marked, dict) or marked.get('disposable') is not True or marked.get('token') != identity['test_token']:
        raise ValueError('Disposable marker changed; no sidecar operation authorized.')
    bank_path, key = form_bank.context(backend, sim)
    if profile.name != 'The Sims 4' or bank_path.parent != profile / 'TD1_OccultHybridApexData':
        raise ValueError('Appearance sidecar escaped the marked disposable layout.')
    return identity, profile, bank_path, key, _unlinked(bank_path.with_name('form_bank_seals.json'))


def _idle():
    from . import cas_ui
    if cas_ui._PEERS or any(not isinstance(row, dict) or
            row.get('state') not in ('completed', 'failed', 'superseded-read') or
            row.get('state') == 'superseded-read' and row.get('operation') != 'status'
            for row in cas_ui._RECORDS.values()):
        raise ValueError('CAS or unresolved native ownership blocks sidecar writes.')


def _live(backend, sim, argument, paused=False):
    from .test_driver import snapshot, _save_live_context
    value = _save_live_context(snapshot(backend, sim), argument)
    if paused and (type(value.get('clock_speed')) is not int or value['clock_speed'] != 0):
        raise ValueError('Reload reconciliation requires the native Live session paused.')
    return value


def _record(bank_path, key):
    bank = _read(bank_path)
    row = bank.get('records', {}).get(key) if isinstance(bank, dict) else None
    from .cas_bank_transaction import _blocked, _lease_path
    if _blocked(row, key) or _lease_path(bank_path).exists():
        raise ValueError('Incomplete CAS journal or writer lease blocks certification and reload restoration.')
    if (not isinstance(bank, dict) or type(bank.get('schema')) is not int or bank['schema'] != 1 or not isinstance(row, dict) or
            row.get('pending') is not None or row.get('switch_pending') is not None or
            (row.get('native_rebase_requires_cas_completion') is not None and row.get('native_rebase_requires_cas_completion') is not False) or
            not isinstance(row.get('bank'), dict) or set(row['bank']) != {str(flag) for flag in FORMS} or
            not isinstance(row.get('history'), list) or not row['history'] or not isinstance(row['history'][-1], dict) or
            row['history'][-1].get('state') != 'completed'):
        raise ValueError('No idle completed seven-lane form bank; unsealed data cannot authorize restoration.')
    for fields in row['bank'].values():
        appearance.fingerprint(fields)
    return row


def _members(backend, sim):
    kinds = {int(kind): kind for kind in backend._all_occults()}
    if not set(FORMS[1:]).issubset(kinds):
        raise ValueError('Native six-occult tuning is unavailable.')
    for flags in FORMS[1:]:
        if sim.occult_tracker.has_occult_type(kinds[flags]) is not True:
            raise ValueError('Direct native six-occult membership is unavailable.')
    return kinds


def _native(backend, sim):
    forms = backend._form_map(sim.occult_tracker)
    if not isinstance(forms, dict):
        raise ValueError('Native stored appearance owners are unavailable.')
    return {'stored': {str(int(kind)): {'id': str(owner.id), 'fields': appearance.packed(backend, owner)} for kind, owner in forms.items()},
            'active_form': backend._get_current_flags(sim), 'active': appearance.packed(backend, sim)}


def current_runtime_bank_verified(backend, sim, bank_record):
    """An exact consumed reload receipt can authorize the same sealed bank.

    This never updates the bank PID or restores a lane. Unknown, unsealed or
    changed receipts cannot turn a prior-runtime appearance into current data.
    """
    identity, profile, bank_path, key, path = _identity(backend, sim)
    if not path.exists():
        return False
    row = _store(path)['records'].get(key)
    if not isinstance(row, dict):
        return False
    try:
        authority = _source_authority(backend, identity, profile, bank_path, key, path, row)
        if authority is not None:
            _runtime_path, _runtime_data, row = _upgrade_runtime(bank_path, key, row, authority)
        expected_bank_hash = _expected_bank_hash(bank_path, row, authority)
    except Exception:
        return False
    if row.get('state') != 'reconciled':
        return False
    recovery = row.get('reconciliation')
    return (row.get('sealed') is True and row.get('contract_sha256') == CONTRACT and
        expected_bank_hash == _hash(bank_record) and isinstance(recovery, dict) and
        recovery.get('ok') is True and type(recovery.get('pid')) is int and recovery['pid'] == identity['pid'] and
        _sha(row.get('seal_sha256')))


def begin_save(backend, sim, argument, native_before, file_before):
    """Called before scheduling a controlled native save, never afterward."""
    identity, profile, bank_path, key, path = _identity(backend, sim)
    if not bank_path.exists():
        return {'state': 'not-applicable', 'reason': 'no-form-bank', 'sealed': False}
    bank = _read(bank_path)
    if key not in bank.get('records', {}):
        return {'state': 'not-applicable', 'reason': 'no-selected-form-bank', 'sealed': False}
    _idle(); _members(backend, sim)
    row = _record(bank_path, key)
    data = _store(path)
    previous = data['records'].get(key)
    prior_reconciled = current_runtime_bank_verified(backend, sim, row)
    if (type(row.get('runtime_pid')) is not int or row['runtime_pid'] != identity['pid']) and not prior_reconciled:
        raise ValueError('Bank is not from this runtime; reconcile its prior certified reload first.')
    native = _native(backend, sim)
    if set(native['stored']) != set(row['bank']) or type(native['active_form']) is not int or str(native['active_form']) not in row['bank']:
        raise ValueError('Required native form owner is absent; no save seal was created.')
    for lane, fields in row['bank'].items():
        if appearance.fingerprint(native['stored'][lane]['fields'])['appearance_sha256'] != appearance.fingerprint(fields)['appearance_sha256']:
            raise ValueError('Native form differs from bank before save; no stale appearance sealed.')
    if appearance.fingerprint(native['active'])['appearance_sha256'] != appearance.fingerprint(row['bank'][str(native['active_form'])])['appearance_sha256']:
        raise ValueError('Active native appearance differs before save; no stale appearance sealed.')
    if previous is not None and (not isinstance(previous, dict) or previous.get('state') not in ('sealed', 'reconciled', 'save-rejected')):
        raise ValueError('Previous sidecar operation is unresolved; no new save intent.')
    intent = {'state': 'save-intent', 'intent_id': uuid.uuid4().hex, 'identity': identity, 'contract_sha256': CONTRACT,
        'target': dict(argument), 'bank_record_sha256': _hash(row), 'appearances': row['bank'],
        'before_file': file_before, 'before_context': native_before, 'native_before': native,
        'seal_sha256': None, 'file_sha256': None, 'sealed': False}
    data['records'][key] = intent; _write(path, data)
    return {'state': intent['state'], 'intent_id': intent['intent_id'], 'sealed': False, 'contract_sha256': CONTRACT}


def submitted(backend, sim, receipt, accepted):
    if receipt.get('state') == 'not-applicable':
        return
    _identity_row, _profile, _bank, key, path = _identity(backend, sim)
    data = _store(path); row = data['records'].get(key)
    if not isinstance(row, dict) or row.get('intent_id') != receipt.get('intent_id') or row.get('state') != 'save-intent':
        raise ValueError('Native save intent identity changed.')
    row['state'] = 'save-submitted' if accepted is True else 'save-rejected' if accepted is False else 'save-unresolved'
    _write(path, data)


def complete_save(backend, sim, argument):
    if not isinstance(argument, dict) or set(argument) != {'intent_id', 'expected_save_sha256'} or not _uuid(argument['intent_id']) or not _sha(argument['expected_save_sha256']):
        raise ValueError('Use the original save intent and exact stable changed file hash.')
    identity, profile, bank_path, key, path = _identity(backend, sim)
    _idle(); data = _store(path); row = data['records'].get(key)
    if (not isinstance(row, dict) or row.get('intent_id') != argument['intent_id'] or row.get('identity') != identity or
            row.get('contract_sha256') != CONTRACT or row.get('state') not in ('save-submitted', 'sealed')):
        raise ValueError('No submitted native save intent for this exact runtime/source.')
    target = row['target']; live = _live(backend, sim, target)
    if live.get('save_slot') != target['slot_id'] or _hash(_record(bank_path, key)) != row['bank_record_sha256']:
        raise ValueError('Native saved target or desired bank changed; no seal created.')
    from .test_driver import _save_file_evidence
    observed = _save_file_evidence(profile, target['slot_id'])
    if observed['sha256'] != argument['expected_save_sha256'] or observed['sha256'] == row['before_file']['sha256']:
        raise ValueError('Actual save file does not match the changed completion hash.')
    if row['state'] == 'sealed':
        if row['file_sha256'] != observed['sha256']:
            raise ValueError('Existing seal differs; no completion replay.')
    else:
        row.update(state='sealed', sealed=True, file_sha256=observed['sha256'], after_file=observed)
        row['seal_sha256'] = _hash({name: row[name] for name in ('intent_id', 'identity', 'contract_sha256',
            'target', 'bank_record_sha256', 'appearances', 'file_sha256')})
        _write(path, data)
    return {'ok': True, 'state': 'sealed', 'intent_id': row['intent_id'], 'seal_sha256': row['seal_sha256'],
            'file_sha256': row['file_sha256'], 'bank_record_sha256': row['bank_record_sha256'], 'save_reload_verified': False}


def note_loaded(tracker):
    """Memory-only receipt at the native load boundary; never restore here."""
    from .hybrid_persistence import _appearance_backend
    backend = _appearance_backend()
    if backend is None:
        return
    sim = tracker.sim_info
    try:
        identity, profile, bank_path, key, path = _identity(backend, sim)
        if not path.exists():
            return
        row = _store(path)['records'].get(key)
        if not isinstance(row, dict):
            return
        authority = _source_authority(backend, identity, profile, bank_path, key, path, row)
        if authority is not None:
            _runtime_path, _runtime_data, row = _upgrade_runtime(bank_path, key, row, authority)
        if isinstance(row, dict) and row.get('state') == 'recovery-required':
            tracker._apex_seal_recovery_required = True
            return
        if not isinstance(row, dict) or row.get('sealed') is not True or row.get('state') not in ('sealed', 'reconciled'):
            return
        recovery = row.get('reconciliation')
        if (row['state'] == 'reconciled' and isinstance(recovery, dict) and
                type(recovery.get('pid')) is int and recovery['pid'] == identity['pid']):
            return  # Durable same-runtime consumption survives repeated load hooks.
        first = _LOADED.get(key)
        if isinstance(first, dict) and first.get('pid') == identity['pid']:
            return  # Zone loads cannot replace the original load-boundary baseline.
        from .test_driver import _save_file_evidence
        file_row = _save_file_evidence(profile, row['target']['slot_id'])
        if file_row['sha256'] != row['file_sha256']:
            return
        _LOADED[key] = {'pid': identity['pid'], 'tracker': tracker, 'native': _native(backend, sim),
                        'file_sha256': file_row['sha256'], 'identity': identity, 'upgrade_receipt_sha256': authority}
    except Exception as error:
        tracker._apex_sealed_load_observation_error = str(error)[:2048]


def reconcile(backend, sim, argument):
    if not isinstance(argument, dict) or set(argument) != {'seal_sha256'} or not _sha(argument['seal_sha256']):
        raise ValueError('Use one exact certified save seal; no caller appearance payload accepted.')
    identity, profile, bank_path, key, path = _identity(backend, sim)
    _idle(); _members(backend, sim)
    data = _store(path); row = data['records'].get(key)
    if (not isinstance(row, dict) or row.get('state') not in ('sealed', 'reconciled') or row.get('sealed') is not True or
            row.get('seal_sha256') != argument['seal_sha256'] or row.get('contract_sha256') != CONTRACT or
            not isinstance(row.get('identity'), dict) or row['identity'].get('pid') == identity['pid']):
        raise ValueError('Seal is absent, altered, unresolved or from another source/runtime identity.')
    authority = _source_authority(backend, identity, profile, bank_path, key, path, row)
    if authority is not None:
        path, data, row = _upgrade_runtime(bank_path, key, row, authority)
        if row.get('state') not in ('sealed', 'reconciled'):
            raise ValueError('Upgrade recovery is unresolved; prior originals were retained.')
    recovery = row.get('reconciliation')
    if (row['state'] == 'reconciled' and isinstance(recovery, dict) and
            type(recovery.get('pid')) is int and recovery['pid'] == identity['pid']):
        raise ValueError('Certified reload was already reconciled in this runtime; newer unsaved edits were preserved.')
    target = row['target']; live = _live(backend, sim, target, paused=True)
    from .test_driver import _save_file_evidence
    if live.get('save_slot') != target['slot_id'] or _save_file_evidence(profile, target['slot_id'])['sha256'] != row['file_sha256']:
        raise ValueError('Reloaded native save target differs from the certified file.')
    if _hash(_record(bank_path, key)) != _expected_bank_hash(bank_path, row, authority):
        raise ValueError('Form bank changed after certification; newer edits were preserved.')
    loaded = _LOADED.get(key)
    if (not isinstance(loaded, dict) or loaded.get('pid') != identity['pid'] or loaded.get('tracker') is not sim.occult_tracker or
            loaded.get('identity') != identity or loaded.get('file_sha256') != row['file_sha256'] or
            loaded.get('upgrade_receipt_sha256') != authority):
        raise ValueError('No exact native load-boundary receipt; restoration not authorized.')
    before = _native(backend, sim)
    if _hash(before) != _hash(loaded['native']):
        raise ValueError('Native owners changed after load; newer unsaved edits were preserved.')
    forms = backend._form_map(sim.occult_tracker)
    if {str(int(kind)) for kind in forms} - set(row['appearances']):
        raise ValueError('Unknown native owners were preserved; restoration not authorized.')
    missing = set(row['appearances']) - {str(int(kind)) for kind in forms}
    if missing - {'16'} or '16' in missing and backend._coerce_flags(16) not in sim.occult_tracker.OCCULT_DATA:
        raise ValueError('Required owner reconstruction is unsupported by native tuning.')
    row.update(state='reconciling', reconciliation={'pid': identity['pid'], 'native_before': before,
        'writes_attempted': False, 'created_forms': [], 'ok': False})
    _write(path, data)  # Recovery originals precede all native writes.
    try:
        row['reconciliation']['writes_attempted'] = True; _write(path, data)
        if '16' in missing:
            # Inspected native save deliberately excludes Witch; native load
            # supports its tuned wrapper without new random appearance.
            owner = sim.occult_tracker._generate_sim_info(backend._coerce_flags(16), generate_new=False)
            if owner is None or forms.get(backend._coerce_flags(16)) is not owner:
                raise ValueError('Native Witch wrapper creation was not verified.')
            row['reconciliation']['created_forms'].append({'flags': 16, 'id': str(owner.id)})
            _write(path, data)
        for lane, fields in row['appearances'].items():
            form_bank.restore(backend, sim, lane, fields)
        after = _native(backend, sim)
        if set(after['stored']) != set(row['appearances']):
            raise ValueError('Reconciled stored native owner coverage differs.')
        for lane, fields in row['appearances'].items():
            if appearance.fingerprint(after['stored'][lane]['fields'])['appearance_sha256'] != appearance.fingerprint(fields)['appearance_sha256']:
                raise ValueError('Reconciled native stored appearance differs.')
        active = str(after['active_form'])
        if appearance.fingerprint(after['active'])['appearance_sha256'] != appearance.fingerprint(row['appearances'][active])['appearance_sha256']:
            raise ValueError('Reconciled active Live appearance differs.')
        _live(backend, sim, target, paused=True)
        row['reconciliation'].update(ok=True, native_after=after)
        row['state'] = 'reconciled'; _write(path, data)
        # This prevents a second reset in the same loaded session.
        _LOADED.pop(key, None)
        return {'ok': True, 'state': 'reconciled', 'seal_sha256': row['seal_sha256'],
                'stored_forms_verified': sorted(map(int, after['stored'])), 'active_form': after['active_form'],
                'created_forms': row['reconciliation']['created_forms'], 'save_file_written': False,
                'bank_written': False, 'save_reload_verified': False, 'upgrade_receipt_sha256': authority}
    except Exception as error:
        sim.occult_tracker._apex_seal_recovery_required = True
        failures = []
        try:
            _live(backend, sim, target, paused=True)
            current_forms = backend._form_map(sim.occult_tracker)
            for lane, original in before['stored'].items():
                owner = current_forms.get(backend._coerce_flags(int(lane)))
                if owner is None or str(owner.id) != original['id']:
                    raise ValueError('Original appearance owner identity changed during rollback.')
                backend._restore_siminfo_payload(owner, appearance.payload(original['fields']))
                if appearance.evidence(backend, owner)['appearance_sha256'] != appearance.fingerprint(original['fields'])['appearance_sha256']:
                    raise ValueError('Original stored appearance rollback did not read back.')
            backend._restore_siminfo_payload(sim, appearance.payload(before['active']))
            if appearance.evidence(backend, sim)['appearance_sha256'] != appearance.fingerprint(before['active'])['appearance_sha256']:
                raise ValueError('Original active appearance rollback did not read back.')
        except Exception as rollback_error:
            failures.append(str(rollback_error)[:2048])
        row['state'] = 'recovery-required'; row['reconciliation']['error'] = str(error)[:2048]
        row['reconciliation']['rollback_errors'] = failures
        row['reconciliation']['original_payloads_restored_verified'] = not failures
        row['reconciliation']['rollback_verified'] = False
        try:
            restored = _native(backend, sim)
            row['reconciliation']['rollback_native_after'] = restored
            row['reconciliation']['rollback_verified'] = not failures and _hash(restored) == _hash(before)
            if not row['reconciliation']['rollback_verified'] and not failures:
                row['reconciliation']['rollback_scope_difference'] = 'Original payloads restored; native owner map or active appearance differs from the complete pre-write receipt.'
        except Exception as observation_error:
            row['reconciliation']['rollback_observation_error'] = str(observation_error)[:2048]
        # Disk recovery failure cannot replace the original native error. The
        # tracker also retains this exact failed receipt for owner diagnostics.
        sim.occult_tracker._apex_seal_reconciliation_failure = dict(row['reconciliation'])
        try:
            _write(path, data)
        except Exception as evidence_error:
            sim.occult_tracker._apex_seal_reconciliation_failure['evidence_write_error'] = str(evidence_error)[:2048]
        raise
