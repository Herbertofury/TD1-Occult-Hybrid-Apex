"""Keep returned native CAS appearances under their exact named identities.

The caller supplies receiver-owned, complete native graph readback. Rendering
genus is checked, never used to group/copy variants. This pure metadata step
does not load a DTO as a Sim, grant a life state, or certify save/Tray reload.
"""
import copy
import hashlib
from . import form_appearance as appearance, lifestate_forms
from .cas_owner_payload import owner_id
from .cas_owner_export_page import OWNER, SHA


def _validated(record,returned):
    document=lifestate_forms.document(record)
    if (not isinstance(returned,dict) or returned.get('ok') is not True or
            returned.get('source')!='receiver-native-owner-return' or
            returned.get('appearance_written') is not False or
            not isinstance(returned.get('owners'),list) or not 1<=len(returned['owners'])<=2048):
        raise ValueError('Named CAS completion requires complete receiver-owned native appearances.')
    rows={};total=0
    for row in returned['owners']:
        oid=row.get('owner_id');encoded=row.get('native_hex');sha=row.get('sha256')
        if (not isinstance(oid,str) or OWNER.fullmatch(oid) is None or oid in rows or
                type(row.get('native_kind')) is not int or row['native_kind'] not in (1,2,4,8,16,32,64) or
                not isinstance(encoded,str) or not 0<len(encoded)<=1024*1024 or len(encoded)%2 or
                not isinstance(sha,str) or SHA.fullmatch(sha) is None):
            raise ValueError('Returned native owner identity or complete bytes are invalid.')
        raw=bytes.fromhex(encoded)
        total+=len(raw)
        if total>48*1024*1024:raise ValueError('Returned native appearance archive exceeds its complete bound.')
        if raw.hex()!=encoded or hashlib.sha256(raw).hexdigest()!=sha:
            raise ValueError('Returned native appearance bytes differ from their digest.')
        appearance.fingerprint(row['fields']);rows[oid]=row
    expected={owner_id(row['lifestate'],row['id']):row for row in document['forms'].values()}
    named={oid for oid in rows if not oid.startswith(('native/','active/'))}
    if named!=set(expected):
        raise ValueError('Returned named forms differ from the complete captured document.')
    changed=set()
    for oid,original in expected.items():
        row=rows[oid]
        if row['native_kind']!=lifestate_forms.visual_form(original) or set(row['fields'])!=set(original['fields']):
            raise ValueError('A named form changed its rendering owner or captured field set.')
        if appearance.fingerprint(row['fields'])['appearance_sha256']!=original['appearance_sha256']:changed.add(oid)
    return document,rows,expected,changed


def changes(record,returned):
    _document,rows,expected,changed=_validated(record,returned)
    result=[]
    for oid in sorted(changed):
        before=appearance.fingerprint(expected[oid]['fields']);after=appearance.fingerprint(rows[oid]['fields'])
        result.append(dict(owner_id=oid,label=expected[oid]['label'],lifestate=expected[oid]['lifestate'],
            native_kind=lifestate_forms.visual_form(expected[oid]),gameplay_form=expected[oid]['base_form'],
            before_sha256=before['appearance_sha256'],
            after_sha256=after['appearance_sha256'],fields=sorted(name for name in before['field_sha256']
                if before['field_sha256'][name]!=after['field_sha256'].get(name))))
    return result


def prepare(record, returned, native_bank,dispositions):
    document,rows,expected,changed=_validated(record,returned)
    if not isinstance(dispositions,list) or len(dispositions)!=len(changed):
        raise ValueError('Every changed named form requires its own explicit disposition; CAS cancellation is not acceptance.')
    decisions={}
    for decision in dispositions:
        if (not isinstance(decision,dict) or set(decision)!={'owner_id','action'} or
                decision.get('owner_id') not in changed or decision['owner_id'] in decisions or
                decision.get('action') not in ('accept-returned','restore-original')):
            raise ValueError('Named CAS decisions require exact changed owner identities and explicit actions.')
        decisions[decision['owner_id']]=decision['action']
    for oid,original in expected.items():
        if decisions.get(oid)=='accept-returned':
            original['fields']=copy.deepcopy(rows[oid]['fields'])
            original['appearance_sha256']=appearance.fingerprint(original['fields'])['appearance_sha256']
    # A native lane may now show a canonical owner or another named variant.
    # Retain a named binding only when its exact returned fields still match;
    # never overwrite that named form from the lane to make it match.
    for lane,identity in list(document['active'].items()):
        fields=native_bank.get(lane)
        if fields is None or appearance.fingerprint(fields)['appearance_sha256']!=document['forms'][identity]['appearance_sha256']:
            del document['active'][lane]
    lifestate_forms.validate(document)
    return document,copy.deepcopy(returned)
