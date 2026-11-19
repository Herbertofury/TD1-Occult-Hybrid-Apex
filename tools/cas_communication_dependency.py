"""Pure listener-index override of the exact native Olympus dependency.

This has no Grid transaction stage. Selector/voice cleanup checks continue to
authenticate the original library separately; every unrelated native body and
trait is retained by the communication and Button whole-ABC rollback proofs.
"""
from pathlib import Path
import hashlib
import json
import os

import cas_communication_index as comm

ROOT=Path(__file__).resolve().parents[1]
PIN='e79b3b65c8b6234c54d4a76f4c7a671f46ece7ddb9f6940bc5db312850fdef91'
TGI='62ECC59A:00000000:3FFE72432A703655'
BASELINE_ABC_SHA256='80d72696fddfc82b81e9db231ed235a45acb7cad2df22632d7cab056247bfd21'
COMMUNICATION_ABC_SHA256='163b99cd94a2f2ace72921414daefcb949513a863c55f4e23281f011e06c800d'
FINAL_ABC_SHA256='98733178ec63096d60ee4fa2bb64b1adc5260f32e5a7db46bfee81e84f627dca'
FINAL_SWF_SHA256='4625eee68d2ffcffce8ece197741e321f840bca44f83843d306d0206e6cece11'
SOURCES=('tools/cas_communication_dependency.py','tools/CasCommunicationDependencyPatch.java',
         'tools/cas_communication_index.py','tools/CasCommunicationIndexPatch.java','tools/CasStructuralRolesPatch.java')


def digest(data):return hashlib.sha256(data).hexdigest()


def adapt(original_swf,ffdec,work):
    original_swf,ffdec,work=map(Path,(original_swf,ffdec,work))
    if digest(original_swf.read_bytes())!=PIN:raise ValueError('Unsupported native communication dependency.')
    pins={name:digest((ROOT/name).read_bytes()) for name in SOURCES}
    work.mkdir(parents=True,exist_ok=True)
    baseline=work/'baseline.swf';baseline.write_bytes(original_swf.read_bytes())
    private=work/'private-source'
    comm.run([ffdec,'-selectclass',comm.TARGET,'-export','script',private,baseline],work/'export.log')
    source=private/'scripts/olympus/io/CommunicationObject.as'
    owned=work/'CommunicationObject.as';owned.write_bytes(comm.inject(source.read_text(encoding='utf-8-sig')).encode())
    compiled=work/'compiled.swf'
    comm.run([ffdec,'-importAssets','yes,local','-replace',baseline,compiled,comm.TARGET,owned],work/'ffdec.log')
    classes=work/'classes';classes.mkdir(exist_ok=True);jar=ffdec.with_name('ffdec.jar')
    comm.run(['javac','-cp',jar,'-d',classes,ROOT/'tools/CasStructuralRolesPatch.java',
        ROOT/'tools/CasCommunicationIndexPatch.java',ROOT/'tools/CasCommunicationDependencyPatch.java'],work/'javac.log')
    abc,proof=work/'retained.abc',work/'proof.json'
    comm.run(['java','-cp',str(jar)+os.pathsep+str(classes),'CasCommunicationDependencyPatch',
        original_swf,baseline,compiled,abc,proof],work/'transplant.log')
    data=abc.read_bytes();report=json.loads(proof.read_text())
    if report.get('ok')is not True or report.get('abc_sha256')!=digest(data):raise ValueError('Communication dependency proof differs.')
    if pins!={name:digest((ROOT/name).read_bytes()) for name in SOURCES}:raise ValueError('Dependency source changed during compilation; discard output.')
    report['source_sha256']=pins
    return data,report


def chain_adapter(postproof,final_swf):
    from cas_ui_build import tags,unpack
    required=('whole_abc_rollback_verified','button_whole_abc_rollback_verified','button_lexical_domain_read_verified',
        'reviewed_helper_semantic_pins_verified','protected_field_namespace_verified','bound_closure_runtime_eligibility_probe',
        'explicit_primitive_diagnostics','native_array_dispatch_order_retained','public_alias_falls_back_to_original','deferred_removal_semantics_retained')
    if (not isinstance(postproof,dict) or postproof.get('ok')is not True or any(postproof.get(k)is not True for k in required) or
        postproof.get('provider_resource_tgi')!=TGI or postproof.get('base_provider_sha256')!=PIN or postproof.get('baseline_swf_sha256')!=PIN or
        postproof.get('changed_native_bodies')!=5 or postproof.get('appended_methods')!=8 or postproof.get('appended_communication_methods')!=7 or
        postproof.get('appended_button_diagnostic_methods')!=1 or postproof.get('appended_fields')!=2 or postproof.get('appended_static_fields')!=5 or
        postproof.get('grid_stage_present')is not False or postproof.get('runtime_qualified')is not False or postproof.get('hitch_free_claimed')is not False):
        raise ValueError('Native communication dependency contract differs.')
    for key in ('baseline_abc_sha256','communication_abc_sha256','abc_sha256'):
        value=postproof.get(key)
        if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):raise ValueError('Dependency ABC identity differs.')
    if (postproof['baseline_abc_sha256']!=BASELINE_ABC_SHA256 or postproof['communication_abc_sha256']!=COMMUNICATION_ABC_SHA256 or
        postproof['abc_sha256']!=FINAL_ABC_SHA256 or digest(final_swf)!=FINAL_SWF_SHA256):raise ValueError('Dependency bytes differ from the reviewed exact native postpass.')
    if postproof.get('source_sha256')!={name:digest((ROOT/name).read_bytes()) for name in SOURCES}:raise ValueError('Dependency source pins differ.')
    abc=[t[3] for t in tags(unpack(final_swf)[1]) if t[0]==82]
    if len(abc)!=1 or digest(abc[0][abc[0].index(b'\0',4)+1:])!=postproof['abc_sha256']:raise ValueError('Final dependency does not contain the authenticated listener index.')
    return dict(base_resource_sha256=PIN,patched_resource_sha256=digest(final_swf),
        postproof_sha256=comm.contract_digest(postproof),communication_dependency_contract=json.loads(json.dumps(postproof)))


def verify_adapter(adapter,final_swf):
    if not isinstance(adapter,dict) or chain_adapter(adapter.get('communication_dependency_contract'),final_swf)!=adapter:
        raise ValueError('Native communication dependency proof differs.')
    return True
