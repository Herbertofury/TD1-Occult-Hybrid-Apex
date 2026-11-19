"""Read only labels/roster for compact catalogue references, never Sim assets.

CAS can suspend the zone/game-clock services. Persistence remains available;
do not route this read through a Live-only snapshot or instantiate SimInfo.
"""
import json
import os
import threading


def roster(backend, value):
    if threading.current_thread().ident != backend._APEX_GAME_THREAD_IDENT:
        raise ValueError('Read catalogue labels on the canonical game thread.')
    request = json.loads(value) if isinstance(value, str) else value
    if not isinstance(request, dict) or set(request) != {'save_guid', 'household_id'}:
        raise ValueError('An exact save GUID and household ID are required.')
    for name in ('save_guid', 'household_id'):
        item = request[name]
        if (not isinstance(item, str) or not item.isascii() or not item.isdecimal() or
                str(int(item)) != item or not 0 < int(item) < 2**64):
            raise ValueError('Use positive decimal save and household identities.')
    persistence = backend.services.get_persistence_service()
    if str(persistence.get_save_slot_proto_guid()) != request['save_guid']:
        raise ValueError('The loaded save changed; no catalogue roster captured.')
    household = persistence.get_household_proto_buff(int(request['household_id']))
    if household is None or str(household.household_id) != request['household_id']:
        raise ValueError('The exact persisted household is unavailable.')
    ids = [int(sid) for sid in household.sims.ids]
    if not 1 <= len(ids) <= 32 or len(set(ids)) != len(ids):
        raise ValueError('The complete household roster exceeds its bound or has duplicates.')
    def label(text):
        if not isinstance(text, str) or not 1 <= len(text) <= 128 or any(ord(c) < 32 for c in text):
            raise ValueError('A household/Sim label is unavailable or unbounded.')
        return text
    rows = []
    for sid in ids:
        sim = persistence.get_sim_proto_buff(sid)
        if sim is None or sim.sim_id != sid or str(sim.household_id) != request['household_id']:
            raise ValueError('Persisted Sim/household identity differs; no partial roster returned.')
        rows.append({'sim_id': str(sid), 'name': label((sim.first_name + ' ' + sim.last_name).strip())})
    # Re-read exact metadata identities; no appearance getter, constructor or
    # save operation is called, including for household members never selected.
    if (str(persistence.get_save_slot_proto_guid()) != request['save_guid'] or
            list(household.sims.ids) != ids):
        raise ValueError('The household changed while reading its names.')
    return dict(ok=True, schema=1, pid=os.getpid(), save_guid=request['save_guid'],
                household_id=request['household_id'], name=label(household.name),
                members=rows, names_source='persisted-household-metadata',
                appearance_written=False, save_submitted=False)
