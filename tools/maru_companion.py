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
GRID_LIBRARY = (0x62ECC59A, 0, 0x89D13757C58C2E05)
GRID_LIBRARY_SHA256 = '6ddb983fee2bd284a2b7efec155e1544bfe99d27f16d4d28097bada25e1864f0'
GRID_LIBRARY_PATCHED_SHA256 = 'd93ab23bae5cbbbbcaa223d4eaec25dd516ae3e87c9da26abe495d2dc0702a7a'
GRID_LIBRARY_CONTRACT = dict(ok=True, native_method_count=8479, unchanged_native_methods=8479,
    appended_native_getters=1, appended_provider_identity_methods=1, provider_identity_verified=True,
    appended_reset_profile_methods=1, reset_profile_native_flow_verified=True,
    reset_profile_scope_verified=True, reset_profile_report_verified=True,
    provider_resource_tgi='62ECC59A:00000000:89D13757C58C2E05',
    retained_native_abc_sha256='eb8615b7156e4434a15e207aee8cb629a2e47d1ef6e9490b2406777bdfd764f8',
    getter_field_namespace_verified=True, getter_scope_verified=True, getter_read_only_verified=True,
    native_abc_retention_verified=True)
CANONICAL_GRID_LIBRARY = (0x62ECC59A, 0, 0x12272E1AC0C1F8E2)
CANONICAL_GRID_LIBRARY_SHA256 = '5f475a80a4f9c77f9a0439e133221a31f766cb929318f74191b4b9bad98e8cae'
CANONICAL_GRID_LIBRARY_PATCHED_SHA256 = 'deb4f64ab6e1d6d5a752f2733cc4d73212a6380c82d73ccb82e4e7eece6a9116'
CANONICAL_GRID_LIBRARY_CONTRACT = dict(ok=True, native_method_count=9194, unchanged_native_methods=9194,
    appended_native_getters=1, appended_provider_identity_methods=1, provider_identity_verified=True,
    appended_reset_profile_methods=1, reset_profile_native_flow_verified=True,
    reset_profile_scope_verified=True, reset_profile_report_verified=True,
    provider_resource_tgi='62ECC59A:00000000:12272E1AC0C1F8E2',
    retained_native_abc_sha256='ae1435753ae49522947aa6fe364b83f3692163cff9fe2b9f1ab393c7e18bbc0f',
    getter_field_namespace_verified=True, getter_scope_verified=True, getter_read_only_verified=True,
    native_abc_retention_verified=True)
UNMODIFIED_OLYMPUS_LIBRARY = (0x62ECC59A, 0, 0x3FFE72432A703655)
# The earlier *_PATCHED_SHA256/CONTRACT values remain the historical
# getter/profile proof. Final transaction bytes have their own identities.
GRID_LIBRARY_TRANSACTION_SHA256 = 'f286299b7822fe857b13eaada6775de3e4c8ab536c741cd0582234d7fdd92792'
CANONICAL_GRID_LIBRARY_TRANSACTION_SHA256 = '525b5db224f243b4fc60fafe2dc9365409076a8c234358e62083ec922e33746f'
GRID_TRANSACTION_SOURCES = ('tools/CasGridTransactionPatch.java', 'tools/cas_grid_transaction.py')
GRID_TRANSACTION_PROOF_SOURCES = GRID_TRANSACTION_SOURCES + ('tools/CasStructuralRolesPatch.java',
                                                           'tools/CasGridBytecodePatch.java')
GRID_COMMUNICATION_SOURCES = ('tools/CasCommunicationIndexPatch.java', 'tools/cas_communication_index.py')
GRID_COMMUNICATION_DEPENDENCY_SOURCES = ('tools/CasCommunicationDependencyPatch.java', 'tools/cas_communication_dependency.py')
GRID_COMMUNICATION_DOMAIN_SOURCES = ('tools/CasCommunicationDomainProbePatch.java', 'tools/cas_communication_domain_probe.py')
GRID_COMMUNICATION_REMOVAL_SOURCES = ('tools/CasCommunicationRemovalMissPatch.java', 'tools/cas_communication_removal_miss.py')
GRID_IMAGE_PROFILE_SOURCES = ('tools/CasImageBoundaryProfilePatch.java', 'tools/cas_image_boundary_profile.py')
GRID_POOL_SOURCES = ('tools/CasGridPoolPatch.java', 'tools/cas_grid_pool.py')
GRID_COMMUNICATION_FINALS = {
    '62ECC59A:00000000:12272E1AC0C1F8E2': '2f74987d872080437fe9695a9f219e8a71c139f37c1f6c3c806f5888f98e8cf3',
    '62ECC59A:00000000:89D13757C58C2E05': 'b7ab103c2e1070ee474b88bd82c77279d176e4985d4f2caa7f27dab3ef85fe6f',
}
GRID_TRANSACTION_ABCS = {
    '62ECC59A:00000000:12272E1AC0C1F8E2': 'f2f6599a828a5b0630ee10dbffebc22af521756794d079cc58b58e5d34feca2a',
    '62ECC59A:00000000:89D13757C58C2E05': 'e67cb304ab5865b47125c84ecae737f4fd8892189401679b4566b53b67f06c08',
}


def _verify_transaction_history(evidence, expected, final_digest, body_count):
    """Validate the exact historical stage under a separately pinned final SWF.

    This is metadata validation, not a claim that the final communication ABC
    equals the earlier grid ABC. The caller authenticates both final bytes and
    the separate whole-ABC rollback/source proof linking those two stages.
    """
    def same(a, b):
        return json.dumps(a, sort_keys=True, separators=(',', ':')) == json.dumps(b, sort_keys=True, separators=(',', ':'))
    post = evidence.get('native_bytecode_contract', {}) if isinstance(evidence, dict) else {}
    counts = dict(original_method_info_count=expected['native_bytecode_contract']['native_method_count'],
        original_method_body_count=body_count, baseline_method_info_count=expected['native_bytecode_contract']['native_method_count'] + 3,
        baseline_method_body_count=body_count + 3, guarded_original_native_bodies=17,
        guarded_existing_adapter_bodies=1, guarded_native_bodies=18,
        unchanged_original_native_bodies=body_count - 17, unchanged_baseline_bodies=body_count - 15,
        appended_methods=45, appended_fields=1)
    required = ('whole_abc_rollback_verified', 'serialized_projection_verified',
                'protected_field_namespace_bindings_verified', 'explicit_jump_switch_exception_fixtures',
                'unarmed_original_native_flow_verified')
    if (not isinstance(evidence, dict) or not same(evidence.get('retained_base_adapter'), expected) or
            evidence.get('base_resource_sha256') != expected['base_resource_sha256'] or
            evidence.get('patched_resource_sha256') != final_digest or not isinstance(post, dict) or
            not same({name: post.get(name) for name in counts}, counts) or
            any(post.get(name) is not True for name in required) or post.get('ok') is not True or
            post.get('runtime_qualified') is not False or post.get('hitch_free_claimed') is not False or
            post.get('base_provider_sha256') != expected['base_resource_sha256'] or
            post.get('baseline_swf_sha256') != expected['patched_resource_sha256'] or
            post.get('provider_resource_tgi') != expected['native_bytecode_contract']['provider_resource_tgi'] or
            post.get('abc_sha256') != GRID_TRANSACTION_ABCS[expected['native_bytecode_contract']['provider_resource_tgi']] or
            post.get('source_sha256') != {name: dbpf_build.digest((Path(__file__).resolve().parents[1] / name).read_bytes())
                                        for name in GRID_TRANSACTION_PROOF_SOURCES}):
        raise ValueError('Historical grid transaction proof, source, identity or native counts differ.')
    return post


def _verify_grid_adapter(evidence, data, expected, final_digest, body_count):
    """Authenticate history and final bytes without relabeling native counts."""
    def same(left, right):
        return json.dumps(left, sort_keys=True, separators=(',', ':')) == json.dumps(right, sort_keys=True, separators=(',', ':'))
    if isinstance(evidence, dict) and 'native_position_contract' in evidence:
        import cas_grid_position
        previous, original = cas_grid_position.historical(evidence, data)
        return _verify_grid_adapter(previous, original, expected, final_digest, body_count)
    if isinstance(evidence, dict) and 'spare_custody_contract' in evidence:
        import cas_grid_spares
        previous, original = cas_grid_spares.historical(evidence, data)
        return _verify_grid_adapter(previous, original, expected, final_digest, body_count)
    if isinstance(evidence, dict) and 'intrinsic_geometry_contract' in evidence:
        import cas_grid_intrinsic
        previous, original = cas_grid_intrinsic.historical(evidence, data)
        return _verify_grid_adapter(previous, original, expected, final_digest, body_count)
    if isinstance(evidence, dict) and 'physical_position_contract' in evidence:
        import cas_grid_physical
        previous, original = cas_grid_physical.historical(evidence, data)
        return _verify_grid_adapter(previous, original, expected, final_digest, body_count)
    if isinstance(evidence, dict) and 'row_delta_contract' in evidence:
        import cas_grid_row_delta
        previous, original = cas_grid_row_delta.historical(evidence, data)
        return _verify_grid_adapter(previous, original, expected, final_digest, body_count)
    if isinstance(evidence, dict) and 'swatch_columns_contract' in evidence:
        import cas_swatch_columns
        previous, original = cas_swatch_columns.historical(evidence, data)
        if evidence['swatch_columns_contract'].get('previous_stage_kind')!='staging-attach':
            raise ValueError('Historical Skin fixture is not a current provider capability.')
        return _verify_grid_adapter(previous, original, expected, final_digest, body_count)
    if isinstance(evidence, dict) and 'staging_attach_contract' in evidence:
        import cas_grid_staging_attach
        previous, original = cas_grid_staging_attach.historical(evidence, data)
        return _verify_grid_adapter(previous, original, expected, final_digest, body_count)
    if isinstance(evidence, dict) and 'publication_trace_contract' in evidence:
        import cas_grid_publication
        previous, original = cas_grid_publication.historical(evidence, data)
        return _verify_grid_adapter(previous, original, expected, final_digest, body_count)
    if isinstance(evidence, dict) and 'featured_contract' in evidence:
        import cas_grid_featured
        previous, original = cas_grid_featured.historical(evidence, data)
        return _verify_grid_adapter(previous, original, expected, final_digest, body_count)
    if isinstance(evidence, dict) and 'budget_contract' in evidence:
        import cas_grid_budget
        previous, original = cas_grid_budget.historical(evidence, data)
        return _verify_grid_adapter(previous, original, expected, final_digest, body_count)
    if isinstance(evidence, dict) and 'slice_contract' in evidence:
        import cas_grid_slice
        previous, original = cas_grid_slice.historical(evidence, data)
        return _verify_grid_adapter(previous, original, expected, final_digest, body_count)
    if isinstance(evidence, dict) and 'scroll_contract' in evidence:
        import cas_grid_scroll
        previous, original = cas_grid_scroll.historical(evidence, data)
        return _verify_grid_adapter(previous, original, expected, final_digest, body_count)
    if isinstance(evidence, dict) and 'swatch_provider_contract' in evidence:
        import cas_swatch_provider
        previous, original = cas_swatch_provider.historical(evidence, data)
        return _verify_grid_adapter(previous, original, expected, final_digest, body_count)
    if isinstance(evidence, dict) and 'progress_contract' in evidence:
        import cas_grid_progress
        previous, original = cas_grid_progress.historical(evidence, data)
        return _verify_grid_adapter(previous, original, expected, final_digest, body_count)
    if isinstance(evidence, dict) and 'product_rows_contract' in evidence:
        import cas_grid_product_rows
        previous, original = cas_grid_product_rows.historical(evidence, data)
        return _verify_grid_adapter(previous, original, expected, final_digest, body_count)
    if isinstance(evidence, dict) and 'presentation_contract' in evidence:
        import cas_grid_presentation
        previous, original = cas_grid_presentation.historical(evidence, data)
        return _verify_grid_adapter(previous, original, expected, final_digest, body_count)
    if isinstance(evidence, dict) and 'grid_pool_contract' in evidence:
        import cas_grid_pool
        cas_grid_pool.verify_adapter(evidence, data)
        previous = evidence['previous_stage_adapter']['previous_stage_adapter']['previous_stage_adapter']['previous_stage_adapter']
        _verify_transaction_history(previous['retained_transaction_adapter'], expected, final_digest, body_count)
        if previous['base_resource_sha256'] != expected['base_resource_sha256']:
            raise ValueError('Pool proof has the wrong native provider history.')
    elif isinstance(evidence, dict) and 'image_boundary_profile_contract' in evidence:
        import cas_image_boundary_profile
        cas_image_boundary_profile.verify_adapter(evidence, data)
        previous = evidence['previous_stage_adapter']['previous_stage_adapter']['previous_stage_adapter']
        _verify_transaction_history(previous['retained_transaction_adapter'], expected, final_digest, body_count)
        if previous['base_resource_sha256'] != expected['base_resource_sha256']:
            raise ValueError('Image-boundary proof has the wrong native provider history.')
    elif isinstance(evidence, dict) and 'communication_removal_miss_contract' in evidence:
        import cas_communication_removal_miss
        cas_communication_removal_miss.verify_adapter(evidence, data)
        previous = evidence['previous_stage_adapter']['previous_stage_adapter']
        _verify_transaction_history(previous['retained_transaction_adapter'], expected, final_digest, body_count)
        if previous['base_resource_sha256'] != expected['base_resource_sha256']:
            raise ValueError('Removal-miss proof has the wrong native provider history.')
    elif isinstance(evidence, dict) and 'communication_domain_probe_contract' in evidence:
        import cas_communication_domain_probe
        cas_communication_domain_probe.verify_adapter(evidence, data)
        previous = evidence['previous_stage_adapter']
        _verify_transaction_history(previous['retained_transaction_adapter'], expected, final_digest, body_count)
        if previous['base_resource_sha256'] != expected['base_resource_sha256']:
            raise ValueError('Listener domain proof has the wrong native provider history.')
    elif isinstance(evidence, dict) and 'retained_transaction_adapter' in evidence:
        import cas_communication_index
        history = _verify_transaction_history(evidence['retained_transaction_adapter'], expected, final_digest, body_count)
        post = evidence.get('communication_index_contract', {})
        if (dbpf_build.digest(data) != GRID_COMMUNICATION_FINALS[expected['native_bytecode_contract']['provider_resource_tgi']] or
                post.get('baseline_abc_sha256') != history.get('abc_sha256')):
            raise ValueError('Final communication provider is not the pinned continuation of its historical grid ABC.')
        cas_communication_index.verify_adapter(evidence, data)
    elif isinstance(evidence, dict) and 'retained_base_adapter' in evidence:
        import cas_grid_transaction
        post = evidence.get('native_bytecode_contract', {})
        counts = dict(original_method_info_count=expected['native_bytecode_contract']['native_method_count'],
            original_method_body_count=body_count, baseline_method_info_count=expected['native_bytecode_contract']['native_method_count'] + 3,
            baseline_method_body_count=body_count + 3, guarded_original_native_bodies=17,
            guarded_existing_adapter_bodies=1, guarded_native_bodies=18,
            unchanged_original_native_bodies=body_count - 17, unchanged_baseline_bodies=body_count - 15,
            appended_methods=45, appended_fields=1)
        if (not same(evidence['retained_base_adapter'], expected) or
                not isinstance(post, dict) or
                not same({name: post.get(name) for name in counts}, counts) or
                post.get('runtime_qualified') is not False or post.get('hitch_free_claimed') is not False or
                dbpf_build.digest(data) != final_digest):
            raise ValueError('Native grid transaction does not retain the exact provider history, counts or final bytes.')
        cas_grid_transaction.verify_adapter(evidence, data)
    elif not same(evidence, expected) or dbpf_build.digest(data) != expected['patched_resource_sha256']:
        raise ValueError('Grid provider is not the exact authenticated read-only getter/profile adaptation.')
    return True


def verify_grid_adapter(evidence, data):
    """Accept the historical donor or its exact chained transaction adapter."""
    expected = dict(base_resource_sha256=GRID_LIBRARY_SHA256,
                    patched_resource_sha256=GRID_LIBRARY_PATCHED_SHA256,
                    native_bytecode_contract=GRID_LIBRARY_CONTRACT)
    return _verify_grid_adapter(evidence, data, expected, GRID_LIBRARY_TRANSACTION_SHA256, 8224)


def verify_grid_providers(evidence, resources, dependencies=None):
    """Require both exact class providers; duplicate native classes can bind first."""
    donor_key, canonical_key = dbpf_build.tgi(GRID_LIBRARY), dbpf_build.tgi(CANONICAL_GRID_LIBRARY)
    if isinstance(evidence, dict) and any(isinstance(value, dict) and 'native_position_contract' in value for value in evidence.values()):
        import cas_grid_position
        previous, original, prior_dependencies = cas_grid_position.unwrap_providers(evidence, resources, dependencies)
        return verify_grid_providers(previous, original, prior_dependencies)
    if isinstance(evidence, dict) and any(isinstance(value, dict) and 'spare_custody_contract' in value for value in evidence.values()):
        import cas_grid_spares
        previous, original, prior_dependencies = cas_grid_spares.unwrap_providers(evidence, resources, dependencies)
        return verify_grid_providers(previous, original, prior_dependencies)
    if isinstance(evidence, dict) and any(isinstance(value, dict) and 'intrinsic_geometry_contract' in value for value in evidence.values()):
        import cas_grid_intrinsic
        previous, original, prior_dependencies = cas_grid_intrinsic.unwrap_providers(evidence, resources, dependencies)
        return verify_grid_providers(previous, original, prior_dependencies)
    if isinstance(evidence, dict) and any(isinstance(value, dict) and 'physical_position_contract' in value for value in evidence.values()):
        import cas_grid_physical
        previous, original, prior_dependencies = cas_grid_physical.unwrap_providers(evidence, resources, dependencies)
        return verify_grid_providers(previous, original, prior_dependencies)
    if isinstance(evidence, dict) and any(isinstance(value, dict) and 'row_delta_contract' in value for value in evidence.values()):
        import cas_grid_row_delta
        previous, original, prior_dependencies = cas_grid_row_delta.unwrap_providers(evidence, resources, dependencies)
        return verify_grid_providers(previous, original, prior_dependencies)
    if isinstance(evidence, dict) and any(isinstance(value, dict) and 'swatch_columns_contract' in value for value in evidence.values()):
        import cas_swatch_columns
        previous, original, prior_dependencies = cas_swatch_columns.unwrap_providers(evidence, resources, dependencies)
        return verify_grid_providers(previous, original, prior_dependencies)
    if isinstance(evidence, dict) and any(isinstance(value, dict) and 'staging_attach_contract' in value for value in evidence.values()):
        import cas_grid_staging_attach
        previous, original, prior_dependencies = cas_grid_staging_attach.unwrap_providers(evidence, resources, dependencies)
        return verify_grid_providers(previous, original, prior_dependencies)
    if isinstance(evidence, dict) and any(isinstance(value, dict) and 'publication_trace_contract' in value for value in evidence.values()):
        import cas_grid_publication
        previous, original, prior_dependencies = cas_grid_publication.unwrap_providers(evidence, resources, dependencies)
        return verify_grid_providers(previous, original, prior_dependencies)
    if isinstance(evidence, dict) and any(isinstance(value, dict) and 'featured_contract' in value for value in evidence.values()):
        import cas_grid_featured
        previous, original, prior_dependencies = cas_grid_featured.unwrap_providers(evidence, resources, dependencies)
        return verify_grid_providers(previous, original, prior_dependencies)
    if isinstance(evidence, dict) and any(isinstance(value, dict) and 'budget_contract' in value for value in evidence.values()):
        import cas_grid_budget
        previous, original, prior_dependencies = cas_grid_budget.unwrap_providers(evidence, resources, dependencies)
        return verify_grid_providers(previous, original, prior_dependencies)
    if isinstance(evidence, dict) and any(isinstance(value, dict) and 'slice_contract' in value for value in evidence.values()):
        import cas_grid_slice
        previous, original, prior_dependencies = cas_grid_slice.unwrap_providers(evidence, resources, dependencies)
        return verify_grid_providers(previous, original, prior_dependencies)
    if isinstance(evidence, dict) and any(isinstance(value, dict) and 'scroll_contract' in value for value in evidence.values()):
        import cas_grid_scroll
        previous, original, prior_dependencies = cas_grid_scroll.unwrap_providers(evidence, resources, dependencies)
        return verify_grid_providers(previous, original, prior_dependencies)
    if isinstance(evidence, dict) and any(isinstance(value, dict) and 'swatch_provider_contract' in value for value in evidence.values()):
        import cas_swatch_provider
        previous, original, prior_dependencies = cas_swatch_provider.unwrap_providers(evidence, resources, dependencies)
        return verify_grid_providers(previous, original, prior_dependencies)
    if isinstance(evidence, dict) and any(isinstance(value, dict) and 'progress_contract' in value for value in evidence.values()):
        import cas_grid_progress
        previous, original, prior_dependencies = cas_grid_progress.unwrap_providers(evidence, resources, dependencies)
        return verify_grid_providers(previous, original, prior_dependencies)
    if isinstance(evidence, dict) and any(isinstance(value, dict) and 'product_rows_contract' in value for value in evidence.values()):
        import cas_grid_product_rows
        previous, original, prior_dependencies = cas_grid_product_rows.unwrap_providers(evidence, resources, dependencies)
        return verify_grid_providers(previous, original, prior_dependencies)
    if isinstance(evidence, dict) and any(isinstance(value, dict) and 'presentation_contract' in value for value in evidence.values()):
        import cas_grid_presentation
        previous, original, prior_dependencies = cas_grid_presentation.unwrap_providers(evidence, resources, dependencies)
        return verify_grid_providers(previous, original, prior_dependencies)
    if not isinstance(evidence, dict) or set(evidence) != {donor_key, canonical_key}:
        raise ValueError('Both authenticated grid class providers are required.')
    if UNMODIFIED_OLYMPUS_LIBRARY in resources:
        import cas_communication_dependency
        key = dbpf_build.tgi(UNMODIFIED_OLYMPUS_LIBRARY)
        if not isinstance(dependencies, dict) or set(dependencies) != {key}:
            raise ValueError('The Olympus dependency override requires its separate exact communication proof.')
        if 'image_boundary_profile_contract' in dependencies[key]:
            import cas_image_boundary_profile
            cas_image_boundary_profile.verify_adapter(dependencies[key], resources[UNMODIFIED_OLYMPUS_LIBRARY])
        elif 'communication_removal_miss_contract' in dependencies[key]:
            import cas_communication_removal_miss
            cas_communication_removal_miss.verify_adapter(dependencies[key], resources[UNMODIFIED_OLYMPUS_LIBRARY])
        elif 'communication_domain_probe_contract' in dependencies[key]:
            import cas_communication_domain_probe
            cas_communication_domain_probe.verify_adapter(dependencies[key], resources[UNMODIFIED_OLYMPUS_LIBRARY])
        else:
            cas_communication_dependency.verify_adapter(dependencies[key], resources[UNMODIFIED_OLYMPUS_LIBRARY])
    elif dependencies:
        raise ValueError('A communication dependency proof has no matching final resource.')
    verify_grid_adapter(evidence[donor_key], resources.get(GRID_LIBRARY, b''))
    verify_canonical_grid_adapter(evidence[canonical_key], resources.get(CANONICAL_GRID_LIBRARY, b''))
    def stage(value):
        return (6 if 'grid_pool_contract' in value else
                5 if 'image_boundary_profile_contract' in value else
                4 if 'communication_removal_miss_contract' in value else
                3 if 'communication_domain_probe_contract' in value else
                2 if 'retained_transaction_adapter' in value else 1 if 'retained_base_adapter' in value else 0)
    if stage(evidence[donor_key]) != stage(evidence[canonical_key]):
        raise ValueError('Both native class providers must use the same reviewed adapter stage.')
    return True


def verify_canonical_grid_adapter(evidence, data):
    """Accept only the authenticated canonical history or its transaction chain."""
    expected = dict(base_resource_sha256=CANONICAL_GRID_LIBRARY_SHA256,
                    patched_resource_sha256=CANONICAL_GRID_LIBRARY_PATCHED_SHA256,
                    native_bytecode_contract=CANONICAL_GRID_LIBRARY_CONTRACT)
    return _verify_grid_adapter(evidence, data, expected, CANONICAL_GRID_LIBRARY_TRANSACTION_SHA256, 8928)


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
    grid_library = work / 'DynamicCASGridLibrary.swf'
    grid_library.write_bytes(resources[GRID_LIBRARY])
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
                customizer=str(customizer), grid_library=str(grid_library), decompiled=str(source), scripts=str(scripts),
                method='donor-ABC-with-retained-Apex-adapters', runtime_verified=False)


def combine(path, apex, evidence, grid_providers=None, dependencies=None):
    resources = read_package(path)
    if evidence.get('resource_sha256') != {dbpf_build.tgi(k): dbpf_build.digest(v) for k, v in resources.items()}:
        raise ValueError('Dynamic CAS donor changed after compilation.')
    # The original customizer and this one authenticated getter adaptation are
    # the complete overlap allowance. Every other dependency remains exact.
    overlaps = set(resources) & set(apex)
    grid_adapter = evidence.get('grid_library_adapter')
    expected_overlap = {CUSTOMIZER}
    if grid_adapter is not None:
        verify_grid_adapter(grid_adapter, apex.get(GRID_LIBRARY, b''))
        expected_overlap.add(GRID_LIBRARY)
    if overlaps != expected_overlap:
        raise ValueError('Unreviewed Dynamic CAS/Apex resource overlap.')
    if CANONICAL_GRID_LIBRARY in apex or grid_providers is not None or UNMODIFIED_OLYMPUS_LIBRARY in apex:
        verify_grid_providers(grid_providers, apex, dependencies)
        if grid_providers[dbpf_build.tgi(GRID_LIBRARY)] != grid_adapter:
            raise ValueError('Grid provider and donor retention evidence differ.')
    resources.update(apex)
    return resources


def verify_merged(info, resources):
    """Bundle gate independent of the owner's donor path and compiler scratch."""
    import cas_grid_position
    info, resources = cas_grid_position.unwrap_manifest(info, resources)
    import cas_grid_spares
    info, resources = cas_grid_spares.unwrap_manifest(info, resources)
    import cas_list_insets
    info, resources = cas_list_insets.unwrap_manifest(info, resources)
    import cas_catalog_workflow
    info, resources = cas_catalog_workflow.unwrap_manifest(info, resources)
    import cas_catalog_schedule
    info, resources = cas_catalog_schedule.unwrap_manifest(info, resources)
    import cas_grid_intrinsic
    info, resources = cas_grid_intrinsic.unwrap_manifest(info, resources)
    import cas_grid_physical
    info, resources = cas_grid_physical.unwrap_manifest(info, resources)
    import cas_grid_row_delta
    info, resources = cas_grid_row_delta.unwrap_manifest(info, resources)
    import cas_swatch_columns
    info, resources = cas_swatch_columns.unwrap_manifest(info, resources)
    import cas_grid_staging_attach
    info, resources = cas_grid_staging_attach.unwrap_manifest(info, resources)
    import cas_grid_publication
    info, resources = cas_grid_publication.unwrap_manifest(info, resources)
    import cas_grid_featured
    info, resources = cas_grid_featured.unwrap_manifest(info, resources)
    import cas_grid_budget
    info, resources = cas_grid_budget.unwrap_manifest(info, resources)
    import cas_grid_slice
    info, resources = cas_grid_slice.unwrap_manifest(info, resources)
    import cas_grid_scroll
    info, resources = cas_grid_scroll.unwrap_manifest(info, resources)
    import cas_swatch_provider
    info, resources = cas_swatch_provider.unwrap_manifest(info, resources)
    import cas_grid_progress
    info, resources = cas_grid_progress.unwrap_manifest(info, resources)
    import cas_grid_product_rows
    info, resources = cas_grid_product_rows.unwrap_manifest(info, resources)
    import cas_grid_presentation
    info, resources = cas_grid_presentation.unwrap_manifest(info, resources)
    evidence = info.get('companion_code_merge')
    if not isinstance(evidence, dict) or evidence.get('package_sha256') != PACKAGE_SHA256:
        raise ValueError('Missing exact Dynamic CAS merge identity.')
    expected = expected_resources()
    actual = {dbpf_build.tgi(k): dbpf_build.digest(v) for k, v in resources.items()}
    main_hash = actual.get(dbpf_build.tgi(CUSTOMIZER))
    if (main_hash is None or info.get('patched_resource_sha256') != main_hash or
            info.get('patched_resources', {}).get(dbpf_build.tgi(CUSTOMIZER)) != main_hash):
        raise ValueError('Advertised final Main identities differ from the actual merged bytes.')
    if (evidence.get('resource_sha256') != expected or evidence.get('resource_count') != RESOURCE_COUNT or
            evidence.get('customizer_sha256') != CUSTOMIZER_SHA256 or
            evidence.get('method') != 'donor-ABC-with-retained-Apex-adapters'):
        raise ValueError('Dynamic CAS input provenance differs from the reviewed donor.')
    pins = info.get('source_pins', {})
    transaction_required = any(name in pins for name in GRID_TRANSACTION_SOURCES)
    communication_required = any(name in pins for name in GRID_COMMUNICATION_SOURCES)
    dependency_required = (any(name in pins for name in GRID_COMMUNICATION_DEPENDENCY_SOURCES) or
                           UNMODIFIED_OLYMPUS_LIBRARY in resources or
                           info.get('communication_dependency_adapters') is not None)
    pool_required = (any(name in pins for name in GRID_POOL_SOURCES) or
                     any(isinstance(value, dict) and 'grid_pool_contract' in value
                         for value in (info.get('grid_provider_adapters') or {}).values()))
    if pool_required and any(name not in pins for name in GRID_POOL_SOURCES + GRID_IMAGE_PROFILE_SOURCES):
        raise ValueError('Current initialized-grid pool source pins are incomplete.')
    image_required = (pool_required or any(name in pins for name in GRID_IMAGE_PROFILE_SOURCES) or
                     any(isinstance(value, dict) and 'image_boundary_profile_contract' in value
                         for group in ('grid_provider_adapters', 'communication_dependency_adapters')
                         for value in (info.get(group) or {}).values()))
    if image_required and any(name not in pins for name in GRID_IMAGE_PROFILE_SOURCES):
        raise ValueError('Current image-boundary profiling source pins are incomplete.')
    removal_required = (image_required or any(name in pins for name in GRID_COMMUNICATION_REMOVAL_SOURCES) or
                       any(isinstance(value, dict) and 'communication_removal_miss_contract' in value
                           for group in ('grid_provider_adapters', 'communication_dependency_adapters')
                           for value in (info.get(group) or {}).values()))
    if removal_required and any(name not in pins for name in
            GRID_COMMUNICATION_REMOVAL_SOURCES + GRID_COMMUNICATION_DOMAIN_SOURCES +
            GRID_COMMUNICATION_SOURCES + GRID_TRANSACTION_PROOF_SOURCES):
        raise ValueError('Current removal-miss continuation source pins are incomplete.')
    domain_required = (removal_required or any(name in pins for name in GRID_COMMUNICATION_DOMAIN_SOURCES) or
                       any(isinstance(value, dict) and 'communication_domain_probe_contract' in value
                           for group in ('grid_provider_adapters', 'communication_dependency_adapters')
                           for value in (info.get(group) or {}).values()))
    if domain_required and any(name not in pins for name in GRID_COMMUNICATION_DOMAIN_SOURCES):
        raise ValueError('Current listener domain diagnostic pins are incomplete.')
    if dependency_required and any(name not in pins for name in GRID_COMMUNICATION_DEPENDENCY_SOURCES):
        raise ValueError('Current Olympus communication dependency pins are incomplete.')
    if communication_required and any(name not in pins for name in GRID_COMMUNICATION_SOURCES):
        raise ValueError('Current listener index source pins are incomplete.')
    if transaction_required and any(name not in pins for name in GRID_TRANSACTION_PROOF_SOURCES):
        raise ValueError('Current grid transaction source pins are incomplete.')
    if ('tools/CasGridBytecodePatch.java' in pins and
            evidence.get('grid_library_adapter') is None):
        raise ValueError('The current CAS sources require the authenticated grid suppression getter.')
    if ('tools/CasGridBytecodePatch.java' in info.get('source_pins', {}) or
            info.get('grid_provider_adapters') is not None or CANONICAL_GRID_LIBRARY in resources):
        providers = info.get('grid_provider_adapters')
        dependencies = info.get('communication_dependency_adapters')
        if pool_required:
            import cas_grid_pool
            if not isinstance(providers, dict) or set(providers) != {
                    dbpf_build.tgi(CANONICAL_GRID_LIBRARY), dbpf_build.tgi(GRID_LIBRARY)}:
                raise ValueError('Current CAS sources require both exact initialized-grid pool continuations.')
            for key, adapter in providers.items():
                if (not isinstance(adapter, dict) or adapter.get('grid_pool_contract', {}).get('source_sha256') !=
                        {name: pins.get(name) for name in cas_grid_pool.SOURCES}):
                    raise ValueError('Current CAS sources require the exact initialized-grid pool and source proof.')
            if isinstance(dependencies, dict) and any(isinstance(adapter, dict) and 'grid_pool_contract' in adapter for adapter in dependencies.values()):
                raise ValueError('The communication-only dependency has no grid pool adaptation.')
        def before_pool(adapter):
            if not isinstance(adapter, dict):
                raise ValueError('CAS provider continuation is not an object.')
            return adapter.get('previous_stage_adapter', {}) if 'grid_pool_contract' in adapter else adapter
        if image_required:
            import cas_image_boundary_profile
            for group in (providers, dependencies):
                if not isinstance(group, dict) or not group:
                    raise ValueError('Current CAS sources require all three image-boundary continuations.')
                for key, adapter in group.items():
                    image_adapter = before_pool(adapter)
                    if (not isinstance(adapter, dict) or image_adapter.get('image_boundary_profile_contract', {}).get('source_sha256') !=
                            {name: pins.get(name) for name in cas_image_boundary_profile.SOURCES}):
                        raise ValueError('Current CAS sources require the exact image-boundary continuation and source proof.')
        if removal_required:
            import cas_communication_removal_miss
            for group in (providers, dependencies):
                if not isinstance(group, dict) or not group:
                    raise ValueError('Current CAS sources require all three removal-miss continuations.')
                for key, adapter in group.items():
                    image_adapter = before_pool(adapter)
                    removal_adapter = image_adapter.get('previous_stage_adapter', {}) if image_required else image_adapter
                    if (not isinstance(adapter, dict) or not isinstance(removal_adapter, dict) or
                            removal_adapter.get('communication_removal_miss_contract', {}).get('source_sha256') !=
                                {name: pins.get(name) for name in cas_communication_removal_miss.SOURCES}):
                        raise ValueError('Current CAS sources require the exact removal-miss continuation and source proof.')
        if domain_required:
            import cas_communication_domain_probe
            for group in (providers, dependencies):
                if not isinstance(group, dict) or not group:
                    raise ValueError('Current CAS sources require all three listener domain continuations.')
                for key, adapter in group.items():
                    image_adapter = before_pool(adapter)
                    removal_adapter = image_adapter.get('previous_stage_adapter', {}) if image_required else image_adapter
                    domain_adapter = removal_adapter.get('previous_stage_adapter', {}) if removal_required else removal_adapter
                    if (not isinstance(adapter, dict) or not isinstance(domain_adapter, dict) or
                            domain_adapter.get('communication_domain_probe_contract', {}).get('source_sha256') !=
                                {name: pins.get(name) for name in cas_communication_domain_probe.SOURCES}):
                        raise ValueError('Current CAS sources require the exact listener domain diagnostic and source proof.')
        if dependency_required:
            import cas_communication_dependency
            key = dbpf_build.tgi(UNMODIFIED_OLYMPUS_LIBRARY)
            dependency_adapter = dependencies.get(key, {}) if isinstance(dependencies, dict) else {}
            if image_required:
                dependency_adapter = dependency_adapter.get('previous_stage_adapter', {})
            if removal_required:
                dependency_adapter = dependency_adapter.get('previous_stage_adapter', {})
            historical_dependency = dependency_adapter.get('previous_stage_adapter', dependency_adapter)
            dependency_final = (cas_image_boundary_profile.FINALS[key][0] if image_required else
                                cas_communication_removal_miss.FINALS[key][0] if removal_required else
                                cas_communication_domain_probe.FINALS[key][0] if domain_required else
                                cas_communication_dependency.FINAL_SWF_SHA256)
            if (not isinstance(dependencies, dict) or set(dependencies) != {key} or
                    historical_dependency.get('communication_dependency_contract', {}).get('source_sha256') !=
                        {name: pins.get(name) for name in cas_communication_dependency.SOURCES} or
                    key in info.get('unmodified_dependency_resources', {}) or
                    info.get('base_resources', {}).get(key) != cas_communication_dependency.PIN or
                    info.get('patched_resources', {}).get(key) != dependency_final):
                raise ValueError('Current CAS sources require the exact earlier Olympus communication override.')
        verify_grid_providers(providers, resources, dependencies)
        if providers[dbpf_build.tgi(GRID_LIBRARY)] != evidence.get('grid_library_adapter'):
            raise ValueError('Grid provider and donor retention evidence differ.')
        if dbpf_build.tgi(CANONICAL_GRID_LIBRARY) in info.get('unmodified_dependency_resources', {}):
            raise ValueError('The adapted canonical provider cannot be declared unmodified.')
        for key, adapter in providers.items():
            image_adapter = before_pool(adapter)
            removal_adapter = image_adapter.get('previous_stage_adapter', image_adapter) if image_required else image_adapter
            domain_adapter = removal_adapter.get('previous_stage_adapter', removal_adapter) if removal_required else removal_adapter
            historical_adapter = domain_adapter.get('previous_stage_adapter', domain_adapter)
            if communication_required:
                proof = historical_adapter.get('communication_index_contract', {})
                communication_sources = GRID_COMMUNICATION_SOURCES + ('tools/CasStructuralRolesPatch.java',)
                if (not isinstance(historical_adapter.get('retained_transaction_adapter'), dict) or
                        proof.get('source_sha256') != {name: pins.get(name) for name in communication_sources}):
                    raise ValueError('Current CAS sources require the exact listener index continuation and source proof.')
            if transaction_required:
                transaction = historical_adapter.get('retained_transaction_adapter', historical_adapter)
                post = transaction.get('native_bytecode_contract', {})
                if (not isinstance(transaction.get('retained_base_adapter'), dict) or
                        post.get('source_sha256') != {name: pins[name] for name in GRID_TRANSACTION_PROOF_SOURCES}):
                    raise ValueError('Current CAS sources require the exact chained grid transaction and source proof.')
            if (info.get('base_resources', {}).get(key) != adapter['base_resource_sha256'] or
                    info.get('patched_resources', {}).get(key) != adapter['patched_resource_sha256']):
                raise ValueError('Grid provider hashes are absent or inconsistent in the resource manifest.')
    for key, digest in expected.items():
        if key == dbpf_build.tgi(GRID_LIBRARY) and evidence.get('grid_library_adapter') is not None:
            verify_grid_adapter(evidence['grid_library_adapter'], resources.get(GRID_LIBRARY, b''))
        elif key != dbpf_build.tgi(CUSTOMIZER) and actual.get(key) != digest:
            raise ValueError('A retained Dynamic CAS dependency changed or is absent: ' + key)
    contract = info.get('native_bytecode_contract', {})
    if (contract.get('native_method_count') != 2650 or contract.get('unchanged_native_methods') != 2616 or
            contract.get('companion_named_form_adapters') != 5 or
            contract.get('native_column_scheduler_adapters') != 8 or
            contract.get('native_lazy_swatch_adapters') != 2 or
            contract.get('native_outfit_consumers') != 3 or
            contract.get('native_draw_trace_adapters') != 1 or
            contract.get('native_draw_trace_guard_verified') is not True or
            contract.get('native_draw_trace_cfg_verified') is not True or
            contract.get('native_draw_trace_call_abi_verified') is not True or
            contract.get('native_favorite_lookup_map_verified') is not True or
            contract.get('native_current_outfit_refresh_queue_verified') is not True or
            contract.get('native_pelt_palette_reenable_verified') is not True):
        raise ValueError('The complete donor ABC did not pass retained-method verification.')
    historical_main = resources[CUSTOMIZER]
    preview_required = ('tools/cas_preview_transition.py' in pins or
                        info.get('preview_transition_native_bytecode_contract') is not None)
    if preview_required:
        import cas_preview_transition
        preview = info.get('preview_transition_native_bytecode_contract')
        if (any(name not in pins for name in cas_preview_transition.SOURCES) or not isinstance(preview,dict) or
                preview.get('preview_transition_contract',{}).get('source_sha256') !=
                    {name:pins[name] for name in cas_preview_transition.SOURCES} or
                preview.get('previous_stage_contract') != info.get('swatch_geometry_native_bytecode_contract') or
                cas_preview_transition.verify_contract(preview,historical_main) is not True):
            raise ValueError('Native preview transition lacks its exact complete preceding geometry/Main proof.')
        historical_main = cas_preview_transition.reconstruct_previous(historical_main,preview['preview_transition_contract'])
    swatch_required = (any(name in pins for name in ('tools/cas_swatch_geometry.py','tools/CasSwatchGeometryPatch.java',
        'Source/CASUi/swatch_geometry_adapter_methods.as','Source/CASUi/swatch_group_geometry_adapter_methods.as','Source/CASUi/catalog_panel_geometry_methods.as')) or
                       info.get('swatch_geometry_native_bytecode_contract') is not None)
    if swatch_required:
        import cas_swatch_geometry
        swatch = info.get('swatch_geometry_native_bytecode_contract')
        if (any(name not in pins for name in cas_swatch_geometry.SOURCES) or not isinstance(swatch,dict) or
                swatch.get('swatch_geometry_contract',{}).get('source_sha256') !=
                    {name:pins[name] for name in cas_swatch_geometry.SOURCES} or
                swatch.get('previous_stage_contract') != info.get('draw_phase_native_bytecode_contract') or
                cas_swatch_geometry.verify_contract(swatch,historical_main) is not True):
            raise ValueError('Final native swatch geometry does not retain its exact complete Draw/Main history.')
        historical_main = cas_swatch_geometry.reconstruct_previous(historical_main,swatch['swatch_geometry_contract'])
    if 'tools/CasStructuralRolesPatch.java' in info.get('source_pins', {}):
        import cas_structural_roles
        post = info.get('structural_roles_native_bytecode_contract')
        if 'tools/CasDrawFastPathPatch.java' in info.get('source_pins', {}):
            import cas_draw_fast_path
            fast = info.get('draw_fast_path_native_bytecode_contract')
            binding_required = (any(name in pins for name in ('tools/CasCatalogBindingPatch.java', 'tools/cas_catalog_binding.py')) or
                                info.get('catalog_binding_native_bytecode_contract') is not None)
            attach_required = (any(name in pins for name in ('tools/CasCellAttachPatch.java', 'tools/cas_cell_attach.py')) or
                               info.get('cell_attach_native_bytecode_contract') is not None)
            if attach_required:
                import cas_cell_attach
                attach = info.get('cell_attach_native_bytecode_contract')
                attach_bytes = historical_main
                phase_required = (any(name in pins for name in ('tools/CasDrawPhasePatch.java', 'tools/cas_draw_phase.py')) or
                                  info.get('draw_phase_native_bytecode_contract') is not None)
                if phase_required:
                    import cas_draw_phase
                    phase = info.get('draw_phase_native_bytecode_contract')
                    if (any(name not in pins for name in cas_draw_phase.SOURCES) or
                            not isinstance(phase, dict) or
                            phase.get('draw_phase_contract', {}).get('source_sha256') !=
                                {name: pins[name] for name in cas_draw_phase.SOURCES} or
                            phase.get('previous_stage_contract') != info.get('catalog_binding_native_bytecode_contract') or
                            cas_draw_phase.verify_contract(phase, attach_bytes) is not True):
                        raise ValueError('Granular Draw pass does not retain the exact historical Main/binding proofs.')
                    attach_bytes = cas_draw_phase.reconstruct_previous(attach_bytes, phase['draw_phase_contract'])
                if binding_required:
                    import cas_catalog_binding
                    binding = info.get('catalog_binding_native_bytecode_contract')
                    if (any(name not in pins for name in cas_catalog_binding.SOURCES) or
                            not isinstance(binding, dict) or
                            binding.get('catalog_binding_contract', {}).get('source_sha256') !=
                                {name: pins[name] for name in cas_catalog_binding.SOURCES} or
                            binding.get('previous_stage_contract') != attach or
                            cas_catalog_binding.verify_contract(binding, attach_bytes) is not True):
                        raise ValueError('Final catalogue binding pass does not retain the exact historical Main/cell proofs.')
                    attach_bytes = cas_catalog_binding.reconstruct_previous(attach_bytes, binding['catalog_binding_contract'])
                if (any(name not in pins for name in cas_cell_attach.SOURCES) or
                        not isinstance(attach, dict) or
                        attach.get('cell_attach_contract', {}).get('source_sha256') !=
                            {name: pins[name] for name in cas_cell_attach.SOURCES} or
                        attach.get('previous_chain') != cas_cell_attach.previous(contract, post, fast) or
                        cas_cell_attach.verify_contract(attach, attach_bytes) is not True):
                    raise ValueError('Final cell attach pass does not retain the exact historical Main/Draw proofs.')
            elif binding_required:
                raise ValueError('Catalogue binding pass requires the complete historical Main/cell chain.')
            elif (not isinstance(post, dict) or not isinstance(fast, dict) or
                    cas_draw_fast_path.chain_contract(contract, post, fast, historical_main) != fast):
                raise ValueError('Final Draw fast path does not chain to the historical structural/native proof.')
        elif not isinstance(post, dict) or cas_structural_roles.chain_contract(contract, post, historical_main) != post:
            raise ValueError('Final structural-role ABC does not chain to the base native proof.')
    return True
