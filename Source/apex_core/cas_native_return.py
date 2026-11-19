"""Project authenticated logical CAS owners onto their exact Live native lanes.

The native graph can retain edits while EA returns older wrappers to Live.
Read those wrappers separately for rollback/concurrency; appearance choices
come only from the captured native graph's explicit one-owner-per-lane binding.
Named special forms never supply a canonical lane just because genus matches.
"""
import copy
import hashlib
from . import form_appearance as appearance


def project(returned, raw, epoch):
    """Live receiver only: this process must own the raw native context."""
    from . import cas_commit_plan as primitive
    if not isinstance(raw,dict) or not isinstance(raw.get('stored'),dict):
        raise ValueError('Live native CAS choices require typed receiver-owned raw appearances.')
    primitive._validate_raw(raw, tuple(int(lane) for lane in raw.get('stored', {})))
    return project_archive(returned, raw, epoch)


def project_archive(returned, raw, epoch):
    """Pure historical consistency check; grants no receiver/write capability."""
    from . import cas_commit_plan as primitive
    if (not isinstance(returned, dict) or returned.get('ok') is not True or
            returned.get('source') != 'receiver-native-owner-return' or
            returned.get('appearance_written') is not False or returned.get('checkpoint_epoch') != epoch or
            not primitive._hash(epoch) or not isinstance(raw, dict)):
        raise ValueError('Native CAS choices require the exact receiver-owned return checkpoint.')
    def validate_raw(value):
        if (not isinstance(value,dict) or set(value)!={'identity','stored','active'} or
                not isinstance(value['identity'],dict) or set(value['identity'])!=primitive.IDENTITY_FIELDS or
                type(value['identity']['runtime_pid']) is not int or not 0<value['identity']['runtime_pid']<=0xffffffff or
                not all(primitive._id(value['identity'][name]) for name in ('sim_id','household_id','save_guid')) or
                not isinstance(value['stored'],dict) or not value['stored'] or
                not set(value['stored'])<={'1','2','4','8','16','32','64'} or
                not isinstance(value['active'],dict) or set(value['active'])!={'lane','fields'} or
                value['active']['lane'] not in value['stored']):
            raise ValueError('Archived native CAS choices lack exact raw appearance identities.')
        for fields in list(value['stored'].values())+[value['active']['fields']]:appearance.fingerprint(fields)
        primitive._json(value)
    validate_raw(raw)
    identity = returned.get('identity')
    if (not isinstance(identity, dict) or identity.get('pid') != raw['identity']['runtime_pid'] or
            identity.get('sim_id') != raw['identity']['sim_id']):
        raise ValueError('Native CAS choices belong to another runtime or Sim.')
    bindings = returned.get('logical_owner_ids')
    if (not isinstance(bindings, dict) or set(bindings) != set(raw['stored']) or
            bindings.get('1') != returned.get('human_owner_id') or
            not isinstance(returned.get('owners'), list) or not 1 <= len(returned['owners']) <= 2048):
        raise ValueError('Native CAS choices lack the complete shared-Human logical owner binding.')
    owners = {}
    for row in returned['owners']:
        if not isinstance(row, dict) or not isinstance(row.get('owner_id'), str) or row['owner_id'] in owners:
            raise ValueError('Native CAS return has a duplicate or invalid owner.')
        owners[row['owner_id']] = row
    chosen = {}
    for lane, oid in bindings.items():
        if oid not in ('native/' + lane, 'active/' + lane) or oid not in owners:
            raise ValueError('A canonical lane must use its captured logical owner, never a named-form substitute.')
        row = owners[oid]
        encoded = row.get('native_hex')
        if (type(row.get('native_kind')) is not int or row['native_kind'] != int(lane) or
                not isinstance(encoded, str) or not 0 < len(encoded) <= 1024 * 1024 or len(encoded) % 2):
            raise ValueError('Native CAS logical owner has invalid rendering identity or complete bytes.')
        decoded = bytes.fromhex(encoded)
        if decoded.hex() != encoded or hashlib.sha256(decoded).hexdigest() != row.get('sha256'):
            raise ValueError('Native CAS logical owner bytes differ from their retained digest.')
        fields = row.get('fields')
        if not isinstance(fields, dict) or set(fields) != set(raw['stored'][lane]):
            raise ValueError('Native CAS logical owner lacks the complete captured appearance field set.')
        appearance.fingerprint(fields)
        chosen[lane] = copy.deepcopy(fields)
    result = dict(identity=copy.deepcopy(raw['identity']), stored=chosen,
                  active=dict(lane=raw['active']['lane'], fields=copy.deepcopy(chosen[raw['active']['lane']])))
    validate_raw(result)
    primitive._consistent(result)
    return result
