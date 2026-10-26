"""Final Draw envelope after the authenticated structural-role pass.

This final pass does not compile ActionScript or change any object outside the
one Draw method.
The structural contract remains a historical input proof; this separate proof
binds its ABC to the final ABC instead of mislabelling the former as final.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ('tools/CasDrawFastPathPatch.java', 'tools/cas_draw_fast_path.py')
PROOFS = ('nullable_function_identity_verified', 'single_entry_branch_verified',
          'fast_tail_exact_verified', 'profiled_tail_exact_verified',
          'native_throw_propagation_preserved', 'serialized_whole_abc_rollback_projection')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def contract_digest(value):
    return digest(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())


def abc_payload(swf):
    from cas_ui_build import tags, unpack
    values = [t[3] for t in tags(unpack(swf)[1]) if t[0] == 82]
    if len(values) != 1:
        raise ValueError('Exactly one authenticated customizer ABC is required.')
    return values[0][values[0].index(b'\0', 4) + 1:]


def validate_contract(contract):
    if (contract.get('ok') is not True or any(contract.get(k) is not True for k in PROOFS) or
            any(type(contract.get(k)) is not type(v) or contract.get(k) != v for k, v in {
                'edited_existing_methods': 1, 'appended_methods': 0, 'appended_traits': 0,
                'appended_pool_entries': 0, 'disabled_added_instructions': 5,
                'disabled_callback_reads': 1, 'disabled_marker_checks': 0,
                'profiled_marker_count': 45, 'runtime_verified': False,
                'performance_gain_claimed': False}.items())):
        raise ValueError('Draw fast path contract differs.')


def adapt(base, structural, baseline_swf, ffdec_jar, work):
    """Return final ABC and proof; caller replaces only the existing ABC tag."""
    import cas_structural_roles as roles
    historical = roles.chain_contract(base, structural, baseline_swf)
    if ('base_contract_sha256' in structural and structural != historical or
            structural.get('source_sha256') != {
                name: digest((ROOT / name).read_bytes())
                for name in ('tools/CasStructuralRolesPatch.java', 'tools/cas_structural_roles.py')} or
            structural.get('private_source_sha256') != roles.PRIVATE_SOURCE_PINS or
            structural.get('donor_swf_sha256') != roles.DONOR_SHA256):
        raise ValueError('Draw requires the current authenticated structural-role input proof.')
    incoming = abc_payload(baseline_swf)
    work, jar = Path(work), Path(ffdec_jar)
    work.mkdir(parents=True, exist_ok=True)
    source, output, report = work / 'baseline.abc', work / 'retained.abc', work / 'contract.json'
    source.write_bytes(incoming)
    classes = work / 'classes'
    classes.mkdir(exist_ok=True)
    subprocess.run(['javac', '-cp', str(jar), '-d', str(classes), str(ROOT / SOURCES[0])],
                   check=True, capture_output=True, timeout=60)
    subprocess.run(['java', '-cp', str(jar) + os.pathsep + str(classes), 'CasDrawFastPathPatch',
                    str(source), structural['abc_sha256'], structural['draw_sha256'],
                    str(output), str(report)], check=True, capture_output=True, timeout=60)
    result, contract = output.read_bytes(), json.loads(report.read_text(encoding='utf-8'))
    validate_contract(contract)
    if (contract.get('baseline_abc_sha256') != digest(incoming) or
            contract.get('baseline_draw_sha256') != structural.get('draw_sha256') or
            contract.get('abc_sha256') != digest(result)):
        raise ValueError('Draw fast path bytes do not match the authenticated input/output proof.')
    contract['baseline_swf_sha256'] = digest(baseline_swf)
    contract['structural_contract_sha256'] = contract_digest(historical)
    contract['source_sha256'] = {name: digest((ROOT / name).read_bytes()) for name in SOURCES}
    return result, contract


def chain_contract(base, structural, fast, final_swf):
    """Verify final bytes while retaining the separate historical role proof."""
    validate_contract(fast)
    import cas_structural_roles as roles
    required = ('explicit_jump_switch_exception_fixtures', 'compiled_helper_control_flow_oracle',
                'compiled_cross_class_receiver_abi', 'serialized_whole_abc_rollback_projection',
                'main_and_height_preserved', 'unowned_corruption_rejected',
                'draw_replaces_existing_trace_adapter', 'base_contract_requires_post_adapter_chain')
    if (structural.get('ok') is not True or any(structural.get(key) is not True for key in required) or
            structural.get('base_donor_body_count') != base.get('native_method_count') or
            structural.get('edited_baseline_methods') != 2 or structural.get('appended_helpers') != 1 or
            structural.get('additional_native_changes_after_base') != ['dcc.history.CurrentOutfitUI.IsCurrent'] or
            structural.get('unchanged_baseline_bodies') != structural.get('baseline_body_count', 0) - 2 or
            structural.get('unchanged_original_native_bodies_after_chain') != base.get('unchanged_native_methods', 0) - 1 or
            structural.get('additional_changed_original_native_bodies') != 1 or
            structural.get('edited_existing_adapter_bodies') != 1 or
            structural.get('source_sha256') != {name: digest((ROOT / name).read_bytes()) for name in
                ('tools/CasStructuralRolesPatch.java', 'tools/cas_structural_roles.py')} or
            structural.get('private_source_sha256') != roles.PRIVATE_SOURCE_PINS or
            structural.get('donor_swf_sha256') != roles.DONOR_SHA256):
        raise ValueError('Historical structural-role/native proof differs.')
    if (structural.get('base_contract_sha256') != contract_digest(base) or
            fast.get('structural_contract_sha256') != contract_digest(structural) or
            fast.get('baseline_abc_sha256') != structural.get('abc_sha256') or
            fast.get('baseline_draw_sha256') != structural.get('draw_sha256') or
            fast.get('baseline_swf_sha256') != structural.get('final_swf_sha256') or
            fast.get('source_sha256') != {name: digest((ROOT / name).read_bytes()) for name in SOURCES} or
            digest(abc_payload(final_swf)) != fast.get('abc_sha256')):
        raise ValueError('Final Draw envelope does not chain to the structural-role/native proof.')
    result = dict(fast)
    result['base_contract_sha256'] = contract_digest(base)
    result['unchanged_original_native_bodies_after_chain'] = structural['unchanged_original_native_bodies_after_chain']
    result['additional_changed_original_native_bodies'] = 0
    result['edited_existing_adapter_bodies'] = 1
    result['final_swf_sha256'] = digest(final_swf)
    return result
