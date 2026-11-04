"""Identify exact donor versions and report collisions; never build or merge.

The current merge gate in maru_companion is deliberately unchanged. In
particular, recognizing a donor here does not authorize the old bytecode
retention proof for a different version or select a collision winner.
"""
import argparse
import hashlib
import json
from pathlib import Path

import dbpf_build
import maru_companion

SUPPLIED_SHA='66ab31072bfe3d7e9fe4b9954d3e7bb7c5409ece01190db8c82349a1bc7acda5'
SUPPLIED_COUNT=88
INVENTORY=Path(__file__).with_name('maru_companion_supplied_inventory.json')
WORK=Path(__file__).resolve().parents[1]/'.work'
ROLES={
    '62ECC59A:00000000:DF09D526F4C77B95': 'customizer-main',
    '62ECC59A:00000000:89D13757C58C2E05': 'donor-grid-provider',
    '62ECC59A:00000000:3E752EBCB41E7298': 'plan-outfit-header',
    '62ECC59A:00000000:DBEC8F675D3E53B2': 'styled-looks',
}


def _load(path):
    path=Path(path)
    if not path.is_file() or path.stat().st_size>dbpf_build.MAX_PACKAGE:
        raise ValueError('Exact bounded package file required.')
    raw=path.read_bytes()
    return raw,hashlib.sha256(raw).hexdigest()


def _unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate donor inventory key: '+key)
        result[key]=value
    return result


def inspect_donor(path):
    raw,package_sha=_load(path)
    if package_sha==maru_companion.PACKAGE_SHA256:
        resources=maru_companion.read_package(path)
        version='historical-reviewed'
    elif package_sha==SUPPLIED_SHA:
        with INVENTORY.open('r',encoding='utf-8') as stream:
            expected=json.load(stream,object_pairs_hook=_unique)
        if (not isinstance(expected,dict) or set(expected)!={'package_sha256','resource_count','resource_sha256'} or
                expected['package_sha256']!=SUPPLIED_SHA or expected['resource_count']!=SUPPLIED_COUNT or
                not isinstance(expected['resource_sha256'],dict)):
            raise ValueError('Supplied donor inventory identity differs.')
        resources=dbpf_build.read(raw)
        actual={dbpf_build.tgi(k):dbpf_build.digest(v) for k,v in resources.items()}
        if len(resources)!=SUPPLIED_COUNT or actual!=expected['resource_sha256']:
            raise ValueError('Supplied donor resource inventory differs.')
        version='owner-supplied-66ab3107'
    else:
        raise ValueError('Unknown donor package; existing version gates remain unchanged.')
    hashes={dbpf_build.tgi(k):dbpf_build.digest(v) for k,v in resources.items()}
    return dict(version=version,package_sha256=package_sha,resource_count=len(hashes),resource_sha256=hashes,
                donor_version_string='unestablished' if version!='historical-reviewed' else 'historical',
                merge_authorized=False,actual_game_verified=False)


def collision_report(donor_path,apex_path,apex_sha256):
    donor=inspect_donor(donor_path)
    if (not isinstance(apex_sha256,str) or len(apex_sha256)!=64 or
            any(c not in '0123456789abcdef' for c in apex_sha256)):
        raise ValueError('An exact lowercase SHA-256 for the compared Apex artifact is required.')
    apex_raw,actual_sha=_load(apex_path)
    if actual_sha!=apex_sha256:raise ValueError('Apex artifact differs from the reviewed hash.')
    apex={dbpf_build.tgi(k):dbpf_build.digest(v) for k,v in dbpf_build.read(apex_raw).items()}
    incoming=donor['resource_sha256'];collisions=[]
    for key in sorted(set(incoming)&set(apex)):
        equal=incoming[key]==apex[key]
        collisions.append(dict(tgi=key,role=ROLES.get(key,'other-resource'),
            incoming_sha256=incoming[key],apex_sha256=apex[key],same_bytes=equal,
            disposition='identical-bytes' if equal else 'unresolved-proof-required'))
    role_status=[]
    for key,role in sorted(ROLES.items()):
        if key not in incoming:continue
        state='absent-in-apex' if key not in apex else 'identical-bytes' if apex[key]==incoming[key] else 'unresolved-proof-required'
        role_status.append(dict(tgi=key,role=role,status=state))
    return dict(donor_version=donor['version'],donor_sha256=donor['package_sha256'],
        apex_sha256=actual_sha,collisions=collisions,role_status=role_status,precedence_selected=False,
        merge_authorized=False,feature_parity_verified=False,game_verified=False,
        note='Hash identity and collision reports do not verify bytecode semantics or runtime behavior.')


def write_report(path,report):
    path=Path(path).resolve();work=WORK.resolve()
    if work not in path.parents or not path.parent.is_dir():
        raise ValueError('Write a new audit only inside this checkout private .work.')
    with path.open('x',encoding='utf-8') as stream:
        json.dump(report,stream,indent=2,sort_keys=True,allow_nan=False);stream.write('\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--donor',type=Path,required=True)
    parser.add_argument('--apex',type=Path,required=True)
    parser.add_argument('--apex-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=collision_report(args.donor,args.apex,args.apex_sha256)
    write_report(args.output,report)
    print(json.dumps(dict(collisions=len(report['collisions']),merge_authorized=False,
                          feature_parity_verified=False,game_verified=False)))


if __name__=='__main__':main()
