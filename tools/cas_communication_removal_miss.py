"""Reject only provably absent non-dispatching listener removals in O(1).

Positive, null, aliased, ineligible, unbuilt and uncertain cases execute the
retained original RemoveFunction instructions, including its deferred queue.
"""
import hashlib
import json
import os
from pathlib import Path

import cas_communication_index as comm

ROOT=Path(__file__).resolve().parents[1]
TARGET='olympus.io.CommunicationObject'
SOURCES=('tools/cas_communication_removal_miss.py','tools/CasCommunicationRemovalMissPatch.java',
         'tools/cas_communication_index.py','tools/CasCommunicationIndexPatch.java','tools/CasStructuralRolesPatch.java')
BASELINES={
    '74701ad23ea1eb9e97775a75d374ea72a1e3e1e9b40f7fdecd8e68f19b3139d3':('62ECC59A:00000000:12272E1AC0C1F8E2','e0a2e29a25f0272f95e53574b3652a69f46da5e758f04731d45d2fdfa181f3f4','954c5b699db6d4739f54136e7001341ef10fa67aae8adab935dcdad3f9a478ca'),
    '2501f2bc00caeb7d3b69b24e80ee81621c87110f569a442a5c090cce04246c79':('62ECC59A:00000000:89D13757C58C2E05','f977deacd36f4f66e5acaecabc74c6aa674e376031739b8dbd87537a2d1b3a62','2644756665b904b11e0bc0beddfc3f402507aeb3cfe3913905c1da6adb71e7be'),
    '5ff049dc49739a0672115f8dace4bd2f6b745ab37484cfd27970c6e27d87b41c':('62ECC59A:00000000:3FFE72432A703655','b9ac735f939f38348fe36827d10b400ac23cb57ee6405f5303b0c979c4d4595f','48e332e7fff272101d7039435d48a1f0035901f6f55f7074f0bd2bd7b15aaafd'),
}
RAW_PROVIDERS={
    '62ECC59A:00000000:12272E1AC0C1F8E2':'5f475a80a4f9c77f9a0439e133221a31f766cb929318f74191b4b9bad98e8cae',
    '62ECC59A:00000000:89D13757C58C2E05':'6ddb983fee2bd284a2b7efec155e1544bfe99d27f16d4d28097bada25e1864f0',
    '62ECC59A:00000000:3FFE72432A703655':'e79b3b65c8b6234c54d4a76f4c7a671f46ece7ddb9f6940bc5db312850fdef91',
}
FINALS={
    '62ECC59A:00000000:12272E1AC0C1F8E2':('4864a5942a9d77c0ecca0ee1682ca53cdd302751872b4173ad69d17b3ef022bc','59c8a4219fff053dfb581f03dd8e2647cc759dea2bdc2927f17b587fce66a380'),
    '62ECC59A:00000000:89D13757C58C2E05':('b71a66ed5a0d867de864bba8c58d847b306ce685a6169429034850c955e5372f','1432ec78709280243b750571e069d4b842a79727d23472a01c2fc23df3d0e397'),
    '62ECC59A:00000000:3FFE72432A703655':('373db1aa7a273c8ca7b9124a027d420deddebdf1815f3ca3cb48c4390d66e859','364096fcf14dc9e906bedaf1d98406e65a3be641363ad76fa20e7920b32be89d'),
}
HELPER=r'''
      private function ApexCommRemovalMissing(fn:Function) : Boolean
      {
         if(fn==null || mbDispatching || apexCommAliased || apexCommIndex==null)
            return false;
         return apexCommIndex[fn]!==true;
      }
'''


def digest(data):return hashlib.sha256(data).hexdigest()


def inject(source):
    if source.count('public final class CommunicationObject')!=1 or 'ApexCommRemovalMissing' in source:
        raise ValueError('Removal-miss private helper class boundary differs.')
    end=source.rfind('\n   }')
    if end<0:raise ValueError('Communication class closing boundary differs.')
    return source[:end]+'\n'+HELPER+source[end:]


def adapt(original_swf,baseline_swf,ffdec,work):
    original_swf,baseline_swf,ffdec,work=map(Path,(original_swf,baseline_swf,ffdec,work))
    expected=BASELINES.get(digest(baseline_swf.read_bytes()))
    if expected is None or digest(original_swf.read_bytes())!=RAW_PROVIDERS[expected[0]]:raise ValueError('Unsupported original/frozen removal-miss provider pair.')
    pins={n:digest((ROOT/n).read_bytes())for n in SOURCES};work.mkdir(parents=True,exist_ok=True)
    private=work/'private-source'
    comm.run([ffdec,'-selectclass',TARGET,'-export','script',private,original_swf],work/'export.log')
    source=private/'scripts/olympus/io/CommunicationObject.as';owned=work/'CommunicationObject.as'
    owned.write_bytes(inject(comm.inject(source.read_text(encoding='utf-8-sig'))).encode())
    compiled=work/'compiled.swf';comm.run([ffdec,'-importAssets','yes,local','-replace',baseline_swf,compiled,TARGET,owned],work/'ffdec.log')
    classes=work/'classes';classes.mkdir(exist_ok=True);jar=ffdec.with_name('ffdec.jar')
    comm.run(['javac','-cp',jar,'-d',classes,ROOT/'tools/CasStructuralRolesPatch.java',ROOT/'tools/CasCommunicationIndexPatch.java',
        ROOT/'tools/CasCommunicationRemovalMissPatch.java'],work/'javac.log')
    abc,proof=work/'retained.abc',work/'proof.json'
    comm.run(['java','-cp',str(jar)+os.pathsep+str(classes),'CasCommunicationRemovalMissPatch',baseline_swf,compiled,abc,proof],work/'transplant.log')
    data=abc.read_bytes();report=json.loads(proof.read_text())
    if report.get('ok')is not True or report.get('abc_sha256')!=digest(data):raise ValueError('Removal-miss bytecode identity differs.')
    if pins!={n:digest((ROOT/n).read_bytes())for n in SOURCES}:raise ValueError('Removal-miss source changed during compilation; discard output.')
    report['source_sha256']=pins;report['helper_source_sha256']=digest(HELPER.encode())
    return data,report


def chain_adapter(previous_adapter,postproof,final_swf):
    from cas_ui_build import tags,unpack
    before=postproof.get('baseline_swf_sha256')if isinstance(postproof,dict)else None;expected=BASELINES.get(before)
    required=('whole_abc_rollback_verified','native_instruction_projection_verified','negative_only_predicate_verified','private_field_binding_verified',
        'manager_native_static_getter_oracle_verified','manager_native_dynamic_map_oracle_verified','diagnostic_reason_fields_verified',
        'deferred_removal_original_path_verified','native_positive_null_alias_unbuilt_paths_retained','no_lazy_index_build_or_allocation','all_other_bodies_retained')
    if (expected is None or postproof.get('ok')is not True or any(postproof.get(k)is not True for k in required) or
        postproof.get('provider_resource_tgi')!=expected[0] or postproof.get('baseline_abc_sha256')!=expected[1] or
        postproof.get('changed_existing_bodies')!=2 or postproof.get('changed_native_bodies')!=1 or postproof.get('replaced_owned_manager_bodies')!=1 or postproof.get('appended_methods')!=1 or postproof.get('appended_fields')!=0 or
        postproof.get('runtime_qualified')is not False or postproof.get('hitch_free_claimed')is not False):raise ValueError('Removal-miss contract differs.')
    if (not isinstance(previous_adapter,dict) or previous_adapter.get('patched_resource_sha256')!=before or
        comm.contract_digest(previous_adapter)!=expected[2]):raise ValueError('Removal-miss prior stage differs.')
    if postproof.get('source_sha256')!={n:digest((ROOT/n).read_bytes())for n in SOURCES} or postproof.get('helper_source_sha256')!=digest(HELPER.encode()):
        raise ValueError('Removal-miss source pins differ.')
    if FINALS[expected[0]]!=(digest(final_swf),postproof.get('abc_sha256')):raise ValueError('Removal-miss final bytes differ from the reviewed exact postpass.')
    abc=[x[3]for x in tags(unpack(final_swf)[1])if x[0]==82]
    if len(abc)!=1 or digest(abc[0][abc[0].index(b'\0',4)+1:])!=postproof.get('abc_sha256'):raise ValueError('Removal-miss final ABC differs.')
    return dict(base_resource_sha256=previous_adapter['base_resource_sha256'],patched_resource_sha256=digest(final_swf),
        previous_stage_sha256=comm.contract_digest(previous_adapter),postproof_sha256=comm.contract_digest(postproof),
        previous_stage_adapter=json.loads(json.dumps(previous_adapter)),communication_removal_miss_contract=json.loads(json.dumps(postproof)))


def verify_adapter(adapter,final_swf):
    if not isinstance(adapter,dict)or chain_adapter(adapter.get('previous_stage_adapter'),adapter.get('communication_removal_miss_contract'),final_swf)!=adapter:
        raise ValueError('Removal-miss final proof differs.')
    return True
