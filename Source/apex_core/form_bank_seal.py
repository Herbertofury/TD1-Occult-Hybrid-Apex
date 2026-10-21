"""Hash-bound household appearance sidecars for native saves and reloads.

An unsealed bank never authorizes a write. A seal binds the actual changed save
file, household banks, native Sim/household/GUID, token and exact script. Reload
reconciliation also requires an unchanged native load receipt, so subsequent
unsaved native edits cannot be replaced by an older sidecar.

One separate explicit disposable migration epoch binds the known A0 predecessor,
the audited target source/bytecode and immutable seal. It never grants automatic
product recovery or authorizes an unmarked profile.
"""
import hashlib
import copy
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
# Metadata-only compatibility: these reviewed builds captured complete schema-1
# named documents in household seals. V261's distinct five-member Alien/Vampire
# edits, all 40 native appearances and 155 named looks passed save/cold-load.
# Every admission still verifies its immutable seal, current file, exact owner
# coverage and native appearance/load observation. This never authorizes native
# restoration or changes the separate A0 recovery-source restrictions.
NAMED_METADATA_PREDECESSORS = ('40efecd91ebede4807a2fbc6c044de67628e3203a4cd4c2039d895fc0cd8363e',
                               'a534570689a04e48ea6d90cb26d9727cdaf369806ae950898ffacbf4fc0fa8d1',
                               'cfef084203d44910520917a2922a034bb6c996cb68bac436782460a94712b0cd',
                               'aa2b7e955890d44c6d0c66225777fa10cfeff68900c7650d860910e07d0a3770',
                               '30b38b03923e8d32cf191feec719f621a0e4b62bd1516209759ca007417995b4')
# Prior v1 receipts remain immutable and cannot authorize this source epoch.
UPGRADE_EPOCH = '2026-10-21-saved-named-upgrade-v263'
UPGRADE_PREDECESSOR = 'a0dff198bd8bf778c440883baf58d83e695b0a26e3d2b7a491e315fcbabf34ce'
UPGRADE_SELF_BODY_SHA = '48564652cb4e032078c6ce936d4fc9e413262f275f2f325408f54fc5346ee60a'
UPGRADE_MODULE_PINS = {
    'apex_core/appearance_transfer.py': 'd6691fe789e8bb932843e23c171a05b2209c09fd4f2d521ae051970599aded63',
    'apex_core/bank_history.py': '3cca2e11f64f1f9bda0602984db0eda2f6b9d24abeb91b544c5353fc71034331',
    'apex_core/body_hair_initialization.py': 'b90fd14e840ae90de087b647519ef39208e3488dc72b5ab41d4389855f7b0592',
    'apex_core/bridge_startup.py': '0aa605cb1671a198571381ee51aa729082630faffbac657529a2ada385a9bee2',
    'apex_core/cas_bank_transaction.py': '0ad4ccd183084cf42fc938b6d213592e34e33a3f99ce949d603ec068acc7f083',
    'apex_core/cas_catalog.py': '72b6b949cbabdfc16d3f214b31edf2952e65edd2fe4c8b085a8c1bd0894c5e38',
    'apex_core/cas_commit_plan.py': '032ebc4a20e711db9ae359874b923c6cadd72eceec05277f85bfae3f935fe0c4',
    'apex_core/cas_controls.py': '8b71d58e752bdfd6bde1995f243c1d082d51604d55f4d508189d230fd795e029',
    'apex_core/cas_entry_context.py': '9474f7dbb6251318e908676ac7ba8b4479c99b9d2bead59ae706eb023726140b',
    'apex_core/cas_form_catalog.py': 'c7c7efc7925691ed2712d9ee0d1047c1368e3e68ddd49cc5fde84402076da32c',
    'apex_core/cas_frontdoor.py': 'cc749e4d5f4e3f05fcfe16b8c92a80296e84a4a9ebfb30b7e9cbaa6980e82f95',
    'apex_core/cas_named_return.py': '53888dcfb949e675820e86b946596e8aa8b6a1a3dcc0c5b4d48c49f66010d84d',
    'apex_core/cas_native_return.py': '3baf9162e487d9547703611a0725c5a497f1c342d6ebf72f3a70917cff9df8a0',
    'apex_core/cas_owner_decode.py': 'f371901c795ddd1fa6270d24b49db3ab0982f5084ce5edc3fb6d5f46fc2ca938',
    'apex_core/cas_owner_export_page.py': '46d190c9958cfa459a950687938e1bcbc8995840b9bcac323c27f6f42814c77e',
    'apex_core/cas_owner_payload.py': '47134e0e2ae6b222898677d7ed80a6e9cd20ddbc2be98a771af8d0167ca94b21',
    'apex_core/cas_panels.py': '3c87dea0c46651915b773d5ec8e9e33b96a58fa4c8b34ba49c2ae36e0eb99374',
    'apex_core/cas_room.py': '1d5ecb8c558f988674f4303ea7506e620a38d3d5b4392e6f7653aedd783d182f',
    'apex_core/cas_save_boundary.py': '57b393f876c3e9aaa1d483d80e5b1193618429947ba1543ec900ba0a6c253e79',
    'apex_core/cas_ui.py': '393d47a161deeb8aa3b5eee42163ed9a851ec4d9c78dc8a63e0993694c6df0fc',
    'apex_core/change_journal.py': '456c460c2154fdcd2dc40e8337debf10fcdb2a84e79253d31263933bdfba023e',
    'apex_core/foreign_current_trait.py': '69fe43862f36efd22dbf3adb992f520dc32c655de0383d94d985133a1a67003b',
    'apex_core/form_appearance.py': 'e5b8d7832ad09f3877123f701192b74e15f38a4599af7da3bd672b24b2d0ae5f',
    'apex_core/form_bank.py': '8f578c668e05b8370aad4137c982a9438f2ab13553270f8bb9aec28c2e3bffb4',
    'apex_core/gameplay_qol.py': 'f58a7fd7dff9b9c532bcf08dcb1e500f5559bf8905861fd93053933ac9d95cb7',
    'apex_core/genetics_snapshot.py': '25944c18d9b240e9c4b579efd4e762443916ada501d154d99d9fe8e0f651bf7a',
    'apex_core/growth_parts.py': 'efca6b2b2cacf2c18171e87779b95cd3be9766809068583fd1547b5f7bd32db2',
    'apex_core/household_io.py': '13e4b8e86ef6587d8e9319e48551637664813acda4c9bf34878d130ecc3df667',
    'apex_core/household_save_group.py': 'dcad435189961dc1a2375e35fc0a04e2e6304cf644a9b7d628a25e222f24e06d',
    'apex_core/human_werewolf.py': '9bafd4df1783f6a3c526242b9a40c42033e3dad4d2f8029e0046633b2f4a363e',
    'apex_core/hybrid_persistence.py': '7d80be549f58b3b2c4b936940130bad787429f0e898bf3dac50bfcdb402a42c7',
    'apex_core/installed_icon_resources.py': '9dc1e52a3e3ab5d064b729047f34e6c3a635a88780047db258fbb2eb72283cd4',
    'apex_core/legacy_phone_guard.py': '097e88240ed8828101de5389c8f966a76e2c393b821f0580808735b663b600cd',
    'apex_core/lifestate_forms.py': '3b7815856093c4fa7eb344d7a4141aa30bbf14a8baed70a4463a218a9f5b4af8',
    'apex_core/lifestates.py': 'c45a4c6f621b75c055e91f55fdb0b767ac15418cff649dcc90801e1bee355ac7',
    'apex_core/morph_controls.py': 'd144ebd7a8dcbff5695b1a2747f641b17017b60a6c39bd904e467602d4c7f876',
    'apex_core/named_save_boundary.py': 'e91cedc374353240e8a5abdde6ab6e99d2313de9158a3846b5a74e1f1fe0c8ca',
    'apex_core/native_cas_engine.py': '44755f3b8c5304e3e9b22a8a900fbab0d86d4a035ecb076a94cbae45fb32e9d3',
    'apex_core/native_controls.py': 'b9d63713fb02f73245ed6febbafd4b641e33b06120a7a5123977d670741fd80d',
    'apex_core/native_form_isolation.py': '8b543ee251da890e30df2f96a961d4d7d76519816376617330f5136de414bb33',
    'apex_core/native_form_select.py': '5c3c9b28d82df3e6515169f3bb653f94ed9c9505d7745673514d85ed79744c44',
    'apex_core/native_http.py': 'dfad235fba919f8aa3a1abfdcb6ba02eddae9f9181fbd1780d8f26bef515f046',
    'apex_core/native_occult_context.py': '4b1fb7278a8719ff58c5b2b1a97aaa89a9e5e953915a31ab212206a67928b186',
    'apex_core/native_pelt_copy.py': '4076c1193634c138e095e86f6c45c042dd6a6050e83c3236706bda54a1100191',
    'apex_core/occult_add_guard.py': '3e4630c36c705afdf9f5cbd3f256be85ec7efa0a3a8d94b8394474fb360c982c',
    'apex_core/occult_appearance_extension.py': '1d908a080f608960fdb9394d954552fb9e2af24a87b60e6f623f690bb8cdbe08',
    'apex_core/occult_icons.py': '8d2cf390a254bba09d98928da9863f3980782bc4429786c3b0f2781ae4e76589',
    'apex_core/outfit_hair.py': '127059656a2dd5ea10d8998c7a5c0f6b8e5353b8d166c4c25cb60dfea8666910',
    'apex_core/outfit_snapshot.py': '76d2feeb0104a8bba9dc341ba7276c1357475781d17b33749a81df5adb123a56',
    'apex_core/overlay_loader.py': '21ba456e3c6f26817ff224e40a26b099cca10f4baaba60ed0649c2d1f9ece1a1',
    'apex_core/phone_cas.py': 'dfa10301eaecde9d92282ebab19fceccfb2599be1e08cd9ebd8db6983a4138b6',
    'apex_core/phone_interactions.py': '05778ddb4e9e764ee4899cca39e5143bf3a4bd7d3bf61d4890c3e0466b72f025',
    'apex_core/profile_save_identity.py': '3dff19214d24119caa20bf3b0849e16e1c006a73a5a9e8f0c167ca5c0a080453',
    'apex_core/runtime_profile.py': '740f28d28c4493f88c61c77c81085e61a2b2c98097c1847dae066ea0c3e05072',
    'apex_core/saved_occult_extras.py': '6b7f0c8c4ea258823d680f35764155bd2de02551a1fc876424888108c814fb0a',
    'apex_core/sim_data.py': 'dfc26d8d9a016b24d69187233ab089058fe72ef82abbac60a2d09710fe0e7266',
    'apex_core/studio.py': '438ec3d9ff7b89607a6a8bfdd0e9136e39785da36e915a378d57ed6c0b759913',
    'apex_core/switch_trace.py': 'f6df67441d2024d41d2e7c47d5840332ce74abc3cb6836874c5a379c36fa0462',
    'apex_core/test_driver.py': 'b5d1b8d35bd136e3a7a7755385c12da383f71e8b63bc6fbc5d33deb23e75b494',
    'apex_core/werewolf_defaults.py': 'ec473439073c4eec1f347a493f0a319b349ce4578cf28dbff0f6bf65bd066443',
    'td1_occult_hybrid_apex.py': '8ad7deaa598e549ffa0d2ddd355b36a07bc14281d01ba61b5ae83fd24076e04c',
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


def _seal_owner_authority(identity, key, seal_path, row):
    old = row.get('identity')
    if (not isinstance(old, dict) or any(old.get(name) != identity.get(name) for name in ('profile', 'test_token')) or
            row.get('contract_sha256') != CONTRACT or any(name not in row for name in _SEAL_FIELDS) or
            _seal_digest(row) != row.get('seal_sha256')):
        raise ValueError('Seal native/profile/contract identity differs.')
    if 'save_group' in row:
        from . import household_save_group
        group = row['save_group']
        primary = group.get('primary_key') if isinstance(group, dict) else None
        ids = group.get('member_intents', {}) if isinstance(group, dict) else {}
        members = household_save_group.members(_store(seal_path)['records'], primary,
            ids.get(primary), ('sealed', 'reconciled'))
        if key not in members or members[key].get('seal_sha256') != row['seal_sha256']:
            raise ValueError('Seal belongs to another retained household group.')


def _source_authority(backend, identity, profile, bank_path, key, seal_path, row):
    _seal_owner_authority(identity, key, seal_path, row)
    old = row['identity']
    if old.get('script_sha256') == identity['script_sha256']:
        return None
    if old.get('script_sha256') != UPGRADE_PREDECESSOR:
        raise ValueError('Seal belongs to another source; only the audited A0 transition is supported.')
    return _upgrade_receipt(backend, identity, profile, bank_path, key, seal_path, row)


def _named_source_authority(backend, identity, profile, bank_path, key, seal_path, row):
    _seal_owner_authority(identity, key, seal_path, row)
    source = row['identity'].get('script_sha256')
    if source != identity['script_sha256'] and source in NAMED_METADATA_PREDECESSORS and 'named_forms' in row:
        from .lifestate_forms import document, KEY
        document({KEY: row['named_forms']})
        return 'named-metadata-only:' + source
    return _source_authority(backend, identity, profile, bank_path, key, seal_path, row)


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


def _seal_digest(row):
    names = _SEAL_FIELDS + tuple(name for name in ('save_group', 'named_forms') if name in row)
    return _hash({name: row[name] for name in names})


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
    player = not _uuid(identity.get('test_token'))
    if player:
        from .profile_save_identity import player as player_identity
        identity = player_identity(backend)
    if (type(identity.get('pid')) is not int or identity['pid'] != os.getpid() or not _uuid(identity.get('test_token')) or
            not _sha(identity.get('script_sha256')) or not isinstance(identity.get('profile'), str) or
            sim is None or not _save_id(str(sim.id)) or not _save_id(str(sim.household_id))):
        raise ValueError('No exact marked native sidecar identity.')
    profile = _unlinked(Path(identity['profile']))
    if not player:
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
            not isinstance(row.get('bank'), dict) or '1' not in row['bank'] or
            not set(row['bank']).issubset({str(flag) for flag in FORMS}) or
            not isinstance(row.get('history'), list) or
            (row['history'] and (not isinstance(row['history'][-1], dict) or row['history'][-1].get('state') != 'completed')) or
            (not row['history'] and 'lifestate_forms' not in row)):
        raise ValueError('No idle completed seven-lane or exact captured partial form bank; unsealed data cannot authorize restoration.')
    for fields in row['bank'].values():
        appearance.fingerprint(fields)
    return row


def _members(backend, sim, lanes=None):
    kinds = {int(kind): kind for kind in backend._all_occults()}
    required = set(FORMS[1:]) if lanes is None else {int(lane) for lane in lanes} - {1}
    if not required.issubset(kinds):
        raise ValueError('Native tuning for a captured occult is unavailable.')
    for flags in required:
        if sim.occult_tracker.has_occult_type(kinds[flags]) is not True:
            raise ValueError('Direct native membership for a captured occult is unavailable.')
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


def admit_saved_named(backend, sim):
    """Reopen certified saved variants with current native caches, no restore.

    The save seal owns the named document. A completed native load observation
    distinguishes load loss (which needs the existing repair path) from later
    Live edits. Unsaved sidecar looks are archived before selecting the saved
    document; no Sim, native appearance, membership or save file is written.
    """
    from . import lifestate_forms, lifestates
    diagnostics = getattr(backend, '_APEX_NAMED_LOAD_DIAGNOSTICS', None)
    if not isinstance(diagnostics, dict):
        diagnostics = {}; backend._APEX_NAMED_LOAD_DIAGNOSTICS = diagnostics
    def refuse(reason):
        diagnostics[str(sim.id)] = dict(state='retained', reason=reason, native_appearance_written=False)
        return False
    bank_path, key = form_bank.context(backend, sim)
    seal_path = _unlinked(bank_path.with_name('form_bank_seals.json'))
    if not bank_path.exists() or not seal_path.exists():
        return False
    from .cas_bank_transaction import _LOCK
    with _LOCK:
        bank_data = form_bank.load(bank_path)
        record = bank_data['records'].get(key)
        if not isinstance(record, dict) or lifestate_forms.KEY not in record:
            return False
        if record.get('runtime_pid') == os.getpid() and lifestate_forms._owns_runtime(record, sim):
            return True
        diagnostics[str(sim.id)] = dict(state='retained', reason='metadata-not-yet-admitted', native_appearance_written=False)
        try:
            lifestates.owner_thread(backend, sim)
            identity, profile, observed_bank, observed_key, path = _identity(backend, sim)
            if (observed_bank, observed_key, path) != (bank_path, key, seal_path):
                return refuse('native-profile-or-owner-context-changed')
            _idle()
            from .cas_bank_transaction import _blocked
            if _blocked(record, key):
                return refuse('retained-cas-review-incomplete')
            row = _store(path)['records'].get(key)
            if (not isinstance(row, dict) or row.get('sealed') is not True or
                    row.get('state') not in ('sealed', 'reconciled') or 'named_forms' not in row):
                return refuse('no-complete-saved-named-document')  # Legacy data never gains uncaptured names.
            authority = _named_source_authority(backend, identity, profile, bank_path, key, path, row)
            target = row['target']
            if target.get('sim_id') != str(sim.id) or target.get('household_id') != str(sim.household_id):
                return refuse('saved-sim-or-household-identity-changed')
            live = _live(backend, sim, target)
            from .test_driver import _save_file_evidence
            if (live.get('save_slot') != target['slot_id'] or
                    _save_file_evidence(profile, target['slot_id'])['sha256'] != row['file_sha256']):
                return refuse('native-slot-or-save-file-changed')
            saved = lifestate_forms.document({lifestate_forms.KEY: row['named_forms']})
            prior = lifestate_forms.document(record)
            for name in ('runtime_pid', 'lifestate_runtime_pid'):
                old = record.get(name)
                if type(old) is not int or old <= 0 or old != identity['pid'] and not form_bank._old_process_absent(old):
                    return refuse('prior-runtime-identity-is-invalid-or-still-alive')
            current = _native(backend, sim)
            if set(current['stored']) != set(row['appearances']) or str(current['active_form']) not in current['stored']:
                return refuse('native-saved-owner-coverage-changed')
            def matches_saved(native):
                return (set(native['stored']) == set(row['appearances']) and all(
                    appearance.fingerprint(native['stored'][lane]['fields'])['appearance_sha256'] ==
                    appearance.fingerprint(fields)['appearance_sha256'] for lane, fields in row['appearances'].items()))
            loaded = _LOADED.get(key)
            if not matches_saved(current):
                if not isinstance(loaded, dict) or loaded.get('pid') != identity['pid']:
                    return refuse('current-native-appearances-differ-without-a-load-observation')
                if (loaded.get('tracker') is not sim.occult_tracker or loaded.get('identity') != identity or
                        loaded.get('file_sha256') != row['file_sha256'] or
                        loaded.get('upgrade_receipt_sha256') != authority):
                    return refuse('load-observation-identity-changed')
                # Native loading can finish deferred appearance extensions after
                # the tracker load callback. Exact current saved appearances are
                # sufficient for metadata admission; an early incomplete sample
                # must not block that match. Later divergent Live edits require
                # a complete matching load sample and are never overwritten.
                if not matches_saved(loaded['native']):
                    return refuse('neither-loaded-nor-current-native-appearances-match-save')
            actual = {lane: owner['fields'] for lane, owner in current['stored'].items()}
            if (appearance.fingerprint(current['active'])['appearance_sha256'] !=
                    appearance.fingerprint(actual[str(current['active_form'])])['appearance_sha256']):
                return refuse('active-native-appearance-differs-from-stored-owner')
        except (ValueError, OSError, KeyError, TypeError) as error:
            return refuse(str(error)[:2048])
        archived = None
        if prior != saved or any(appearance.fingerprint(record['bank'][lane])['appearance_sha256'] !=
                appearance.fingerprint(fields)['appearance_sha256'] for lane, fields in actual.items()):
            preserved = dict(schema=1, owner_key=key, runtime_pid=record['runtime_pid'],
                lifestate_runtime_pid=record['lifestate_runtime_pid'], bank=record['bank'],
                named_forms=prior, active_lane=record.get('active_lane'),
                reason='prior-sidecar-looks-retained-before-certified-named-load')
            digest = _hash(preserved)
            folder = _unlinked(bank_path.parent / 'named_form_history'); folder.mkdir(exist_ok=True)
            archive = _unlinked(folder / (digest + '.json'))
            if archive.exists():
                if _hash(_read(archive)) != digest:
                    raise ValueError('Named appearance recovery archive changed; metadata not replaced.')
            else:
                _write(archive, preserved)
            archived = dict(path=str(archive), sha256=digest)
        # Native rendering lanes remain actual current data. A named variant is
        # never overwritten merely because it shares that lane's rendering kind.
        for lane, name in list(saved['active'].items()):
            if appearance.fingerprint(actual[lane])['appearance_sha256'] != saved['forms'][name]['appearance_sha256']:
                del saved['active'][lane]
        history = record.setdefault('named_load_history', [])
        if not isinstance(history, list):
            raise ValueError('Named load history is malformed; saved variants remain retained.')
        history.append(dict(runtime_pid=identity['pid'], prior_runtime_pid=record['runtime_pid'],
            seal_sha256=row['seal_sha256'], file_sha256=row['file_sha256'],
            saved_named_sha256=_hash(row['named_forms']), archived_unsaved=archived,
            native_appearance_written=False))
        record.update(runtime_pid=identity['pid'], lifestate_runtime_pid=identity['pid'],
            bank=copy.deepcopy(actual), active_lane=str(current['active_form']))
        record[lifestate_forms.KEY] = saved
        lifestate_forms._bind_runtime(record,sim)
        form_bank.save(bank_path, bank_data)
        diagnostics[str(sim.id)] = dict(state='saved-metadata-admitted', seal_sha256=row['seal_sha256'],
            metadata_source_authority=authority, native_appearance_written=False)
        return True


def _prepare_save_member(backend, sim, argument, native_before, file_before, seals):
    """Prepare one verified member without a partial sidecar write."""
    identity, profile, bank_path, key, path = _identity(backend, sim)
    if not bank_path.exists():
        return {'state': 'not-applicable', 'reason': 'no-form-bank', 'sealed': False}
    bank = _read(bank_path)
    if key not in bank.get('records', {}):
        return {'state': 'not-applicable', 'reason': 'no-selected-form-bank', 'sealed': False}
    _idle()
    row = _record(bank_path, key)
    _members(backend, sim, row['bank'])
    previous = seals['records'].get(key)
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
    from . import lifestate_forms
    if lifestate_forms.KEY in row:
        if not lifestate_forms._owns_runtime(row,sim):
            raise ValueError('Prior named variants need certified load admission or explicit unsaved draft recovery before saving.')
        intent['named_forms'] = lifestate_forms.document(row)
    return intent


def _household(backend, sim):
    from .test_driver import _save_id
    household = backend.services.active_household()
    if household is None or str(household.id) != str(sim.household_id):
        raise ValueError('The native save household changed before sidecar preparation.')
    members = list(household.sim_info_gen())
    if (not 1 <= len(members) <= 8 or any(member is None or not _save_id(str(member.id)) or
            str(member.household_id) != str(household.id) for member in members) or
            len({str(member.id) for member in members}) != len(members) or
            not any(member is sim for member in members)):
        raise ValueError('The complete native save household roster is unavailable.')
    return {str(member.id): member for member in members}


def begin_save(backend, sim, argument, native_before, file_before):
    """Prepare every household bank before the one native save request."""
    from . import household_save_group
    identity, profile, bank_path, selected_key, path = _identity(backend, sim)
    if not bank_path.exists():
        return {'state': 'not-applicable', 'reason': 'no-form-bank', 'sealed': False}
    roster = _household(backend, sim)
    data = _store(path); prepared = {}
    for sid, member in roster.items():
        admit_saved_named(backend, member)
        target = dict(argument, sim_id=sid)
        before = native_before if member is sim else _live(backend, member, target)
        row = _prepare_save_member(backend, member, target, before, file_before, data)
        if row.get('state') == 'not-applicable':
            continue
        key = argument['save_guid'] + ':' + sid
        if row.get('identity') != identity:
            raise ValueError('A prepared household member belongs to another runtime or source.')
        prepared[key] = row
    if set(_household(backend, sim)) != set(roster):
        raise ValueError('Native household changed during preparation; no save intent written.')
    if not prepared:
        return {'state': 'not-applicable', 'reason': 'no-household-form-bank', 'sealed': False}
    primary = selected_key if selected_key in prepared else sorted(prepared)[0]
    prepared = household_save_group.prepare(primary, list(roster), prepared)
    data['records'].update(prepared)
    _write(path, data)
    return {'state': 'save-intent', 'intent_id': prepared[primary]['intent_id'], 'sealed': False,
            'contract_sha256': CONTRACT, 'primary_key': primary,
            'household_member_count': len(roster), 'appearance_bank_count': len(prepared)}


def _save_group(data, selected_key, intent_id, states):
    from . import household_save_group
    matches = [(key, row) for key, row in data['records'].items()
               if isinstance(row, dict) and row.get('intent_id') == intent_id]
    if len(matches) != 1:
        raise ValueError('Save intent has no unique retained primary.')
    key, row = matches[0]
    if row.get('save_group') is None and key != selected_key:
        raise ValueError('A legacy intent belongs to another selected Sim.')
    if row.get('state') not in states:
        if 'save-submitted' in states:
            raise ValueError('No submitted native save intent for this completion.')
        raise ValueError('Native save intent changed before submission.')
    return key, household_save_group.members(data['records'], key, intent_id, (row['state'],))


def submitted(backend, sim, receipt, accepted):
    if receipt.get('state') == 'not-applicable':
        return
    _identity_row, _profile, _bank, key, path = _identity(backend, sim)
    data = _store(path)
    primary, rows = _save_group(data, key, receipt.get('intent_id'), ('save-intent',))
    for row in rows.values():
        if row.get('identity') != _identity_row:
            raise ValueError('A household save intent belongs to another runtime/source.')
    for row in rows.values():
        row['state'] = 'save-submitted' if accepted is True else 'save-rejected' if accepted is False else 'save-unresolved'
    _write(path, data)


def complete_save(backend, sim, argument):
    if not isinstance(argument, dict) or set(argument) != {'intent_id', 'expected_save_sha256'} or not _uuid(argument['intent_id']) or not _sha(argument['expected_save_sha256']):
        raise ValueError('Use the original save intent and exact stable changed file hash.')
    identity, profile, bank_path, key, path = _identity(backend, sim)
    _idle(); data = _store(path)
    primary, rows = _save_group(data, key, argument['intent_id'], ('save-submitted', 'sealed'))
    row = rows[primary]; target = row['target']
    roster = _household(backend, sim) if row.get('save_group') is not None else {str(sim.id): sim}
    if row.get('save_group') is not None and set(roster) != set(row['save_group']['roster_sim_ids']):
        raise ValueError('Native household changed after submission; no group sealed.')
    for owner_key, member_row in rows.items():
        sid = member_row['target']['sim_id']; member = roster.get(sid)
        if (member is None or member_row.get('identity') != identity or member_row.get('contract_sha256') != CONTRACT):
            raise ValueError('A saved member has another runtime, source or identity.')
        live = _live(backend, member, member_row['target'])
        if (live.get('save_slot') != target['slot_id'] or
                _hash(_record(bank_path, owner_key)) != member_row['bank_record_sha256']):
            raise ValueError('A saved member or desired bank changed; no group sealed.')
    from .test_driver import _save_file_evidence
    observed = _save_file_evidence(profile, target['slot_id'])
    if observed['sha256'] != argument['expected_save_sha256'] or observed['sha256'] == row['before_file']['sha256']:
        raise ValueError('Actual save file does not match the changed completion hash.')
    for member_row in rows.values():
        if member_row['state'] == 'sealed' and member_row['file_sha256'] != observed['sha256']:
            raise ValueError('An existing household seal differs; no completion replay.')
    if row['state'] != 'sealed':
        for member_row in rows.values():
            member_row.update(state='sealed', sealed=True, file_sha256=observed['sha256'], after_file=observed)
            member_row['seal_sha256'] = _seal_digest(member_row)
        _write(path, data)
    return {'ok': True, 'state': 'sealed', 'intent_id': row['intent_id'], 'seal_sha256': row['seal_sha256'],
            'file_sha256': row['file_sha256'], 'bank_record_sha256': row['bank_record_sha256'], 'save_reload_verified': False,
            'household_seals': {owner_key: member['seal_sha256'] for owner_key, member in rows.items()}}


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
        authority = _named_source_authority(backend, identity, profile, bank_path, key, path, row)
        if authority is not None and not authority.startswith('named-metadata-only:'):
            _runtime_path, _runtime_data, row = _upgrade_runtime(bank_path, key, row, authority)
        if isinstance(row, dict) and row.get('state') == 'recovery-required':
            tracker._apex_seal_recovery_required = True
            return
        if not isinstance(row, dict) or row.get('sealed') is not True or row.get('state') not in ('sealed', 'reconciled'):
            return
        recovery = row.get('reconciliation')
        if (row['state'] == 'reconciled' and isinstance(recovery, dict) and
                type(recovery.get('pid')) is int and recovery['pid'] == identity['pid']):
            from . import lifestate_forms
            bank_record=_record(bank_path,key)
            if lifestate_forms.KEY not in bank_record or lifestate_forms._owns_runtime(bank_record,sim):
                return  # Same tracker/zone reload cannot replay a saved look.
        first = _LOADED.get(key)
        if isinstance(first, dict) and first.get('pid') == identity['pid'] and first.get('tracker') is tracker:
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
    _idle()
    data = _store(path); row = data['records'].get(key)
    if (not isinstance(row, dict) or row.get('state') not in ('sealed', 'reconciled') or row.get('sealed') is not True or
            row.get('seal_sha256') != argument['seal_sha256'] or row.get('contract_sha256') != CONTRACT or
            not isinstance(row.get('identity'), dict) or row['identity'].get('pid') == identity['pid']):
        raise ValueError('Seal is absent, altered, unresolved or from another source/runtime identity.')
    _members(backend, sim, row['appearances'])
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
