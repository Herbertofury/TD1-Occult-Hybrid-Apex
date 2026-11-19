"""Private immutable complete serializer append; disk remains ordinary JSON.

The tuple's only payload is immutable canonical bytes and their exact hash.
There is no retained dict/list alias, including through base-class mutators.
Only the exact root journal field is spliced. No generic marker substitution.
"""
import copy
import hashlib
import json
import math

FIELD = 'native_serialized_append'
MAX_BYTES = 48 * 1024 * 1024
_ADMIT = object()


def _hash(value):
    return (type(value) is str and len(value) == 64 and
            all(c in '0123456789abcdef' for c in value))


def _dump(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                      separators=(',', ':')).encode('ascii')


def _exact(value, ancestors=None):
    kind = type(value)
    if kind in (dict, list):
        ancestors = set() if ancestors is None else ancestors
        if id(value) in ancestors:
            raise ValueError('Immutable append cannot contain cycles.')
        ancestors.add(id(value))
        try:
            if kind is dict:
                if any(type(key) is not str for key in value):
                    raise ValueError('Immutable append requires exact JSON string keys.')
                values = value.values()
            else:
                values = value
            for item in values:
                _exact(item, ancestors)
        finally:
            ancestors.remove(id(value))
    elif kind not in (str, int, bool, float, type(None)) or kind is float and not math.isfinite(value):
        raise ValueError('Immutable append requires exact finite JSON types.')


class FrozenAppend(tuple):
    __slots__ = ()

    def __new__(cls, raw, digest, admission=None):
        if admission is not _ADMIT or cls is not FrozenAppend:
            raise TypeError('Immutable append requires an exact validated admission.')
        if (type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES or
                not raw.startswith(b'{') or not raw.endswith(b'}') or not _hash(digest) or
                hashlib.sha256(raw).hexdigest() != digest):
            raise ValueError('Immutable append canonical bytes differ from their exact digest.')
        raw.decode('ascii')
        return tuple.__new__(cls, (raw, digest))

    @classmethod
    def from_value(cls, value, expected_sha256):
        if type(value) is not dict:
            raise ValueError('Complete serializer append must remain an exact JSON object.')
        _exact(value)
        return cls(_dump(value), expected_sha256, _ADMIT)

    @classmethod
    def _from_verified_native(cls, raw, expected_sha256):
        # This private seam accepts only bytes returned by the authenticated
        # worker's strict parser/canonicalizer. Full reconstructed journal SHA
        # is checked before receipt adoption. It is never a public JSON action.
        return cls(raw, expected_sha256, _ADMIT)

    @property
    def canonical(self):
        return tuple.__getitem__(self, 0)

    @property
    def sha256(self):
        return tuple.__getitem__(self, 1)

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        memo[id(self)] = self
        return self

    def plain(self):
        # Each explicit legacy writer gets a NEW independent mutable tree.
        return json.loads(self.canonical.decode('ascii'))


def chunks(value):
    """Return exact canonical chunks only for our one reviewed journal leaf."""
    if type(value) is FrozenAppend:
        return (value.canonical,)
    if type(value) is not dict or type(value.get(FIELD)) is not FrozenAppend:
        return None
    if any(type(key) is not str for key in value):
        raise ValueError('Immutable journal requires exact JSON string keys.')
    def parts():
        yield b'{'
        for index, key in enumerate(sorted(value)):
            if index:
                yield b','
            yield _dump(key)
            yield b':'
            yield value[key].canonical if key == FIELD else _dump(value[key])
        yield b'}'
    return parts()


def freeze_journal(document):
    """Own a plain journal once; retain no mutable append or external alias."""
    if FIELD not in document:
        return document
    value = document[FIELD]
    frozen = value if type(value) is FrozenAppend else FrozenAppend.from_value(value, document.get('native_serialized_sha256'))
    owned = copy.deepcopy({key: row for key, row in document.items() if key != FIELD})
    owned[FIELD] = frozen
    return owned


def thaw_journal(document):
    """Known-leaf boundary only; shared bank/history/seal retain plain JSON."""
    owned = copy.deepcopy(document)
    if type(owned.get(FIELD)) is FrozenAppend:
        owned[FIELD] = owned[FIELD].plain()
    return owned


def restore_native_receipt(value, request):
    """Replace exactly one proven null projection before owner adoption."""
    if type(value.get('immutable_append_protocol')) is not int or value['immutable_append_protocol'] != 1:
        raise ValueError('Worker does not supply the exact immutable append protocol.')
    capsule = value.get('immutable_journal_append')
    if capsule is None:
        record = value.get('record')
        transaction = record.get('cas_transaction') if type(record) is dict else None
        journal = transaction.get('journal') if type(transaction) is dict else None
        if type(journal) is dict and FIELD in journal:
            raise ValueError('Immutable append capsule is missing for its extracted leaf.')
        return value
    if (type(capsule) is not dict or set(capsule) !=
            {'schema', 'request_id', 'transaction_id', 'sequence', 'canonical_json', 'sha256'} or
            type(capsule['schema']) is not int or capsule['schema'] != 1 or
            type(capsule['sequence']) is not int or
            any(capsule[key] != request[key] for key in ('request_id', 'transaction_id', 'sequence')) or
            value.get('state') != 'ready' or value.get('ok') is not True or
            type(capsule['canonical_json']) is not str):
        raise ValueError('Immutable append capsule belongs to another exact receipt.')
    record = value.get('record')
    transaction = record.get('cas_transaction') if type(record) is dict else None
    journal = transaction.get('journal') if type(transaction) is dict else None
    if (type(journal) is not dict or FIELD not in journal or journal[FIELD] is not None or
            journal.get('native_serialized_sha256') != capsule['sha256']):
        raise ValueError('Immutable append requires its exact present-null journal projection.')
    frozen = FrozenAppend._from_verified_native(capsule['canonical_json'].encode('ascii'), capsule['sha256'])
    journal[FIELD] = frozen
    canonical = chunks(journal)
    actual = hashlib.sha256(b''.join(canonical)).hexdigest()
    if actual != value.get('journal_sha256'):
        raise ValueError('Immutable append changes the complete acknowledged journal hash.')
    return value
