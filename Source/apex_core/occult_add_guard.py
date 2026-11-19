"""Keep every existing appearance owner through native add/loot callbacks.

Pack initialization may switch the active form and replace older map entries.
Preserve the exact preimages before calling it; new occult defaults stay native.
"""
import json
import os
from pathlib import Path
from . import form_appearance as appearance
from .overlay_loader import _unlinked


def fields(backend, owner):
    raw = backend._snapshot_siminfo_payload(owner)
    return {name: appearance.encode(value) for name, value in raw.items()
            if name in appearance.FIELDS + ('__outfits__',)}


def publish(path, proof):
    payload = json.dumps(proof, sort_keys=True, ensure_ascii=True, allow_nan=False).encode('utf-8')
    if len(payload) > 32 * 1024 * 1024:
        raise ValueError('Occult add preimages exceed their recovery bound.')
    temporary = _unlinked(path.with_suffix('.pending'))
    with temporary.open('wb') as stream:
        stream.write(payload); stream.flush(); os.fsync(stream.fileno())
    os.replace(str(temporary), str(path))


class Preservation:
    def __init__(self, backend, sim, kind):
        self.backend, self.sim, self.tracker = backend, sim, sim.occult_tracker
        self.mapping = backend._form_map(self.tracker)
        if not isinstance(self.mapping, dict):
            raise ValueError('Exact native appearance-owner map required before adding an occult.')
        self.original_map = dict(self.mapping)
        self.owners = []
        self.owner_flags = []
        for owner in list(self.original_map.values()) + [sim]:
            if not any(owner is old for old, _ in self.owners):
                packed = fields(backend, owner)
                if '__outfits__' not in packed:
                    raise ValueError('No readable appearance preimage; no occult add submitted.')
                self.owners.append((owner, packed))
                self.owner_flags.append((owner, getattr(owner,'flags',None)))
        self.flags = (backend._get_occult_flags(sim), backend._get_current_flags(sim))
        self.previous_members=[int(k) for k in backend._all_occults() if backend._has_occult(self.tracker,k)]
        self.kind=int(kind)
        guid = str(backend.services.get_persistence_service().get_save_slot_proto_guid())
        folder = _unlinked(Path(backend._data_directory()) / 'OccultAdd')
        folder.mkdir(exist_ok=True)
        self.path = _unlinked(folder / (guid + '-' + str(sim.id) + '-' + str(int(kind)) + '.json'))
        if self.path.exists():
            if self.path.stat().st_size > 32 * 1024 * 1024:
                raise ValueError('Occult add recovery exceeds its bound.')
            previous = json.loads(self.path.read_text(encoding='utf-8'))
            if previous.get('stage') != 'restored':
                raise ValueError('Interrupted occult add retained; recover its preimages before retrying.')
        self.proof = dict(schema=1, stage='adding', sim_id=str(sim.id), save_guid=guid,
            requested_form=int(kind), flags=list(self.flags), native_members=self.previous_members, owners=[
                dict(form=next((int(k) for k,v in self.original_map.items() if v is owner), None),
                     active=owner is sim, fields=packed, appearance_flags=next(v for o,v in self.owner_flags if o is owner))
                     for owner,packed in self.owners])
        publish(self.path, self.proof)

    def restore(self, membership, accepted):
        backend = self.backend
        def mask_matches():
            observed=backend._get_occult_flags(self.sim)
            if observed==membership:return True
            # The installed Spellcaster setter removes the default Human bit
            # while preserving its stored appearance and active Human kind.
            # Admit only that exact native normalization, with all actual
            # previous/requested occult queries true. No other bit loss passes.
            wanted=set(self.previous_members)
            if accepted and self.kind in (2,4,8,16,32,64):wanted.add(self.kind)
            return (membership&16 and membership&1 and observed==(membership&~1) and
                any(int(k)==1 for k in self.mapping) and
                all(backend._has_occult(self.tracker,backend._coerce_flags(k)) for k in wanted))
        if backend._form_map(self.tracker) is not self.mapping:
            self.tracker._sim_info_map = self.mapping
        # Retain newly generated owners but put every original slot back on
        # its original wrapper. Never infer an old look from the active form.
        self.mapping.update(self.original_map)
        if backend._get_current_flags(self.sim) != self.flags[1]:
            backend._set_flags(self.sim, 'current_occult_types', self.flags[1])
        if backend._get_occult_flags(self.sim) != membership:
            backend._set_flags(self.sim, 'occult_types', membership)
        # Resending/loading the active owner can affect a stored wrapper.
        # Restore it first, then all stored owners; check the entire set.
        ordered = sorted(self.owners, key=lambda pair: pair[0] is not self.sim)
        for _ in range(2):
            for owner, original in ordered:
                native_flags=next(v for o,v in self.owner_flags if o is owner)
                if native_flags is not None and getattr(owner,'flags',None)!=native_flags:
                    backend._restore_siminfo_payload(owner,{'flags':native_flags})
                current = fields(backend, owner)
                differences = {name: value for name,value in original.items() if current.get(name) != value}
                if differences: backend._restore_siminfo_payload(owner, appearance.payload(differences))
            # Native physical-flag/genetics setters can recalculate the occult
            # mask (notably when adding Witch). Publish the intended membership
            # only after every physical owner has been restored.
            if backend._get_current_flags(self.sim)!=self.flags[1]:
                backend._set_flags(self.sim,'current_occult_types',self.flags[1])
            if backend._get_occult_flags(self.sim)!=membership:
                backend._set_flags(self.sim,'occult_types',membership)
            if all(appearance.fingerprint(fields(backend, owner)) == appearance.fingerprint(original)
                   and getattr(owner,'flags',None)==next(v for o,v in self.owner_flags if o is owner)
                   for owner,original in self.owners) and mask_matches() and backend._get_current_flags(self.sim)==self.flags[1]: break
        changed = [dict(form=next((int(k) for k,v in self.original_map.items() if v is owner),None),
                        active=owner is self.sim, expected=original, observed=fields(backend,owner),
                        expected_appearance_flags=next(v for o,v in self.owner_flags if o is owner),
                        observed_appearance_flags=getattr(owner,'flags',None))
                   for owner,original in self.owners
                   if appearance.fingerprint(fields(backend,owner)) != appearance.fingerprint(original)
                   or getattr(owner,'flags',None)!=next(v for o,v in self.owner_flags if o is owner)]
        if (changed or any(self.mapping.get(k) is not v for k,v in self.original_map.items()) or
                not mask_matches() or backend._get_current_flags(self.sim)!=self.flags[1]):
            self.proof.update(stage='recovery-required', differences=changed,
                expected_tracker_flags=[membership,self.flags[1]],
                observed_tracker_flags=[backend._get_occult_flags(self.sim),backend._get_current_flags(self.sim)])
            publish(self.path,self.proof)
            raise ValueError('Occult add changed an existing appearance or membership; exact preimages retained for recovery.')
        self.proof.update(stage='restored',accepted=accepted,membership=backend._get_occult_flags(self.sim),
            intended_membership=membership,native_human_default_normalization=backend._get_occult_flags(self.sim)!=membership,
            representation_changes=[dict(form=next((int(k) for k,v in self.original_map.items() if v is owner),None),
                active=owner is self.sim,fields=[n for n,v in original.items() if fields(backend,owner).get(n)!=v],
                appearance=appearance.fingerprint(fields(backend,owner)))
                for owner,original in self.owners if fields(backend,owner)!=original])
        publish(self.path,self.proof)
