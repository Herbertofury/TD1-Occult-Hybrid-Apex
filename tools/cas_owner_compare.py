"""Compare complete receiver-decoded owner pages with fresh pre-entry fields.

Read-only evidence. An explicit intended-field set excludes only those actual
edits from comparison; the remaining fields must still match every owner.
This does not authorize a bank write, CAS acceptance, or gameplay restoration.
"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core import form_appearance
from source_manifest import sha256,write_json


def compare(reference,pages,intended=()):
    if (not isinstance(reference,dict) or reference.get('ok') is not True or
            not isinstance(reference.get('members'),dict) or
            not set(intended)<set(form_appearance.FIELDS+('__outfits__',))):
        raise ValueError('Use a complete original reference and an explicit partial intended-field set.')
    expected={(sid,oid):row for sid,owners in reference['members'].items() for oid,row in owners.items()}
    seen=set();differences=[]
    for page in pages:
        if (page.get('ok') is not True or page.get('scope')!='native-owner-export-page' or
                page.get('scope_id')!=reference['native_scope_id'] or
                page.get('owner_appearance_query')!='returned-value' or
                page.get('appearance_written') is not False or page.get('model_harvested') is not False):
            raise ValueError('A page lacks complete receiver-decoded read-only appearance evidence.')
        raw={row['owner_id']:row for row in page['owners']}
        decoded=page.get('owner_appearances')
        if not isinstance(decoded,list) or {row['owner_id'] for row in decoded}!=set(raw):
            raise ValueError('Decoded appearances omit a complete raw owner.')
        for row in decoded:
            key=(page['sim_id'],row['owner_id'])
            if (key not in expected or key in seen or row['native_kind']!=expected[key]['native_kind'] or
                    row['native_sha256']!=raw[row['owner_id']]['sha256']):
                raise ValueError('Decoded appearance has another Sim, form, kind or complete-byte digest.')
            seen.add(key);before=form_appearance.fingerprint(expected[key]['fields'])
            after=form_appearance.fingerprint(row['fields'])
            changed=sorted(name for name in set(before['field_sha256'])|set(after['field_sha256'])
                if name not in intended and before['field_sha256'].get(name)!=after['field_sha256'].get(name))
            if changed:differences.append(dict(sim_id=key[0],owner_id=key[1],fields=changed))
    if seen!=set(expected):raise ValueError('Complete comparison omitted household owners.')
    return dict(ok=not differences,owners_compared=len(seen),intended_fields=sorted(set(intended)),
        differences=differences,appearance_written=False,cas_accept_submitted=False,save_submitted=False,
        production_ready=False)


def run(state,reference,export,output,intended=()):
    import reusable_profile
    journal,_data,profile,original_profile=reusable_profile.load(state)
    reference,export,output=map(Path,(reference,export,output))
    reference,export,output=(reusable_profile.writable(p) for p in (reference,export,output))
    if (output.exists() or output.suffix!='.json' or not output.parent.is_dir() or
            any(path==journal or path==root or root in path.parents for path in (reference,export,output)
                for root in (profile,original_profile))):
        raise ValueError('Use new external comparison evidence outside both profiles and the journal.')
    original=json.loads(reference.read_text(encoding='utf-8'))
    manifest=json.loads(export.read_text(encoding='utf-8'))
    if manifest.get('ok') is not True:raise ValueError('A partial export cannot qualify all owners.')
    pages=[]
    for receipt in manifest['receipts']:
        path=Path(receipt['path'])
        if sha256(path)!=receipt['sha256']:raise ValueError('A native export receipt changed.')
        page=json.loads(path.read_text(encoding='utf-8'))
        if page.get('scope')=='native-owner-export-page':pages.append(page)
    result=compare(original,pages,intended)
    result.update(reference_sha256=sha256(reference),export_sha256=sha256(export))
    write_json(output,result);return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('state','reference','export','output'):parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--intended-field',action='append',default=[])
    args=parser.parse_args();result=run(args.state,args.reference,args.export,args.output,args.intended_field)
    print(json.dumps(result));raise SystemExit(0 if result['ok'] else 1)
