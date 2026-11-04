"""Append explicit actual-listener diagnostics after frozen library stages.

Original communication index/dependency tools stay source-frozen. This separate
postproof distinguishes retained stages from final bytes and never claims a
runtime result from offline bytecode validation.
"""
import hashlib
import json
import os
from pathlib import Path

import cas_communication_index as comm

ROOT=Path(__file__).resolve().parents[1]
SOURCES=('tools/cas_communication_domain_probe.py','tools/CasCommunicationDomainProbePatch.java','tools/CasStructuralRolesPatch.java')
BASELINES={
    '2f74987d872080437fe9695a9f219e8a71c139f37c1f6c3c806f5888f98e8cf3':(
        '62ECC59A:00000000:12272E1AC0C1F8E2','12b3333527aaa68d44350256ca480a1830c0cb0c13f05a19dc3ced790dc9d08d','df57fc89e1d4a84c783833653309bebc8fe61d74e21e8f8481baa733dbe1a580'),
    'b7ab103c2e1070ee474b88bd82c77279d176e4985d4f2caa7f27dab3ef85fe6f':(
        '62ECC59A:00000000:89D13757C58C2E05','3eb0fd1f63b9a77d3196898ee094a20ec3d448df1ad51d5d287255763dd549f7','f849cfb2e1c1f41b4f3cbef8296f5692e407be1b75d7d739b4ff26ab66f2037b'),
    '4625eee68d2ffcffce8ece197741e321f840bca44f83843d306d0206e6cece11':(
        '62ECC59A:00000000:3FFE72432A703655','98733178ec63096d60ee4fa2bb64b1adc5260f32e5a7db46bfee81e84f627dca','b656e68ec9d5cbb371418c77dafba0db341ac886624f512463616035a21b344c'),
}
FINALS={
    '62ECC59A:00000000:12272E1AC0C1F8E2':('74701ad23ea1eb9e97775a75d374ea72a1e3e1e9b40f7fdecd8e68f19b3139d3','e0a2e29a25f0272f95e53574b3652a69f46da5e758f04731d45d2fdfa181f3f4'),
    '62ECC59A:00000000:89D13757C58C2E05':('2501f2bc00caeb7d3b69b24e80ee81621c87110f569a442a5c090cce04246c79','f977deacd36f4f66e5acaecabc74c6aa674e376031739b8dbd87537a2d1b3a62'),
    '62ECC59A:00000000:3FFE72432A703655':('5ff049dc49739a0672115f8dace4bd2f6b745ab37484cfd27970c6e27d87b41c','b9ac735f939f38348fe36827d10b400ac23cb57ee6405f5303b0c979c4d4595f'),
}


def digest(data):return hashlib.sha256(data).hexdigest()


def adapt(baseline_swf,ffdec,work):
    baseline_swf,ffdec,work=map(Path,(baseline_swf,ffdec,work))
    if digest(baseline_swf.read_bytes())not in BASELINES:raise ValueError('Unsupported frozen domain-probe baseline.')
    pins={name:digest((ROOT/name).read_bytes()) for name in SOURCES}
    work.mkdir(parents=True,exist_ok=True);classes=work/'classes';classes.mkdir(exist_ok=True)
    jar=ffdec.with_name('ffdec.jar')
    comm.run(['javac','-cp',jar,'-d',classes,ROOT/'tools/CasStructuralRolesPatch.java',ROOT/'tools/CasCommunicationDomainProbePatch.java'],work/'javac.log')
    abc,proof=work/'retained.abc',work/'proof.json'
    comm.run(['java','-cp',str(jar)+os.pathsep+str(classes),'CasCommunicationDomainProbePatch',baseline_swf,abc,proof],work/'transplant.log')
    data=abc.read_bytes();report=json.loads(proof.read_text())
    if report.get('ok')is not True or report.get('abc_sha256')!=digest(data):raise ValueError('Domain-probe bytecode identity differs.')
    if pins!={name:digest((ROOT/name).read_bytes()) for name in SOURCES}:raise ValueError('Domain-probe source changed during compilation; discard output.')
    report['source_sha256']=pins
    return data,report


def chain_adapter(previous_adapter,postproof,final_swf):
    from cas_ui_build import tags,unpack
    before=postproof.get('baseline_swf_sha256')if isinstance(postproof,dict)else None
    expected=BASELINES.get(before)
    required=('whole_abc_rollback_verified','original_index_bodies_retained','actual_listener_instance_read_verified',
              'protected_singleton_binding_verified','public_native_array_not_exposed','no_dispatch_write_or_services')
    if (expected is None or postproof.get('ok')is not True or postproof.get('phase')!='native-listener-domain-probe' or
        any(postproof.get(key)is not True for key in required) or postproof.get('provider_resource_tgi')!=expected[0] or
        postproof.get('baseline_abc_sha256')!=expected[1] or postproof.get('changed_native_bodies')!=0 or
        postproof.get('runtime_qualified')is not False or postproof.get('hitch_free_claimed')is not False):
        raise ValueError('Domain-probe retained-stage contract differs.')
    dependency=expected[0].endswith(':3FFE72432A703655')
    if postproof.get('replaced_owned_button_bodies')!=int(dependency) or postproof.get('appended_methods')!=(2 if dependency else 3):
        raise ValueError('Domain-probe owned method inventory differs.')
    if (not isinstance(previous_adapter,dict) or previous_adapter.get('patched_resource_sha256')!=before or
        comm.contract_digest(previous_adapter)!=expected[2]):raise ValueError('Domain-probe historical adapter differs from the frozen exact stage.')
    if postproof.get('source_sha256')!={name:digest((ROOT/name).read_bytes()) for name in SOURCES}:raise ValueError('Domain-probe source pins differ.')
    if FINALS[expected[0]]!=(digest(final_swf),postproof.get('abc_sha256')):raise ValueError('Domain-probe final bytes differ from the reviewed exact postpass.')
    abc=[x[3] for x in tags(unpack(final_swf)[1]) if x[0]==82]
    if len(abc)!=1 or digest(abc[0][abc[0].index(b'\0',4)+1:])!=postproof.get('abc_sha256'):raise ValueError('Final library is not the authenticated domain probe.')
    return dict(base_resource_sha256=previous_adapter['base_resource_sha256'],patched_resource_sha256=digest(final_swf),
        previous_stage_sha256=comm.contract_digest(previous_adapter),postproof_sha256=comm.contract_digest(postproof),
        previous_stage_adapter=json.loads(json.dumps(previous_adapter)),communication_domain_probe_contract=json.loads(json.dumps(postproof)))


def verify_adapter(adapter,final_swf):
    if not isinstance(adapter,dict) or chain_adapter(adapter.get('previous_stage_adapter'),adapter.get('communication_domain_probe_contract'),final_swf)!=adapter:
        raise ValueError('Domain-probe final adapter differs.')
    return True
