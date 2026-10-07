"""Authorized 1.13.7 persistence port with exception/unknown-data protection.

Retain the recognized-form load/save algorithm. Missing tuning never authorizes
deleting serialized forms. This helper registers no hooks on import.
"""


def _known_mask(tracker):
    mask = 1
    for kind in tracker.OCCULT_DATA:
        mask |= int(kind)
    return mask


def save_with_retention(original, tracker, occult_utils, *args, **kwargs):
    sim = tracker.sim_info
    membership, available = sim.occult_types, tracker._occult_form_available
    try:
        unknown = int(membership) & ~_known_mask(tracker)
        sim.occult_types = int(occult_utils.get_occult_types_for_save(tracker)) | unknown
        occult_utils.recalc_occult_form_availability(tracker, saving=True)
        data = original(tracker, *args, **kwargs)
        present = {int(item.occult_type) for item in data.occult_sim_infos}
        for item in getattr(tracker, '_apex_unresolved_occult_records', ()):
            if int(item.occult_type) not in present:
                data.occult_sim_infos.add().CopyFrom(item)
        data.occult_types = int(data.occult_types) | unknown
        return data
    finally:
        sim.occult_types = membership
        tracker._occult_form_available = available


def load_with_retention(original, tracker, data, occult_cache, occult_utils, occult_enum, base_wrapper):
    occult_cache.OccultDataCache.process_custom_occults()
    records, unresolved = {}, []
    known = {int(occult_enum.HUMAN)} | {int(kind) for kind in tracker.OCCULT_DATA}
    for item in data.occult_sim_infos:
        if int(item.occult_type) in records:
            raise ValueError('Duplicate saved occult identities; refusing ambiguous load.')
        records[int(item.occult_type)] = item
        if int(item.occult_type) not in known:
            clone = type(item)()
            clone.CopyFrom(item)
            unresolved.append(clone)
    tracker._apex_unresolved_occult_records = tuple(unresolved)
    tracker._sim_info.occult_types = data.occult_types or occult_enum.HUMAN
    tracker._sim_info.current_occult_types = data.current_occult_types or occult_enum.HUMAN
    tracker._pending_occult_type = data.pending_occult_type
    tracker._occult_form_available = data.occult_form_available
    for kind in occult_enum:
        if kind != occult_enum.HUMAN and kind not in tracker.OCCULT_DATA:
            continue
        item = records.get(int(kind))
        if item is not None:
            form = tracker._generate_sim_info(item.occult_type, generate_new=False)
            if kind == tracker._sim_info.current_occult_types:
                base_wrapper.copy_physical_attributes(item, tracker._sim_info._base)
            else:
                form.load_outfits(item.outfits)
                base_wrapper.copy_physical_attributes(form._base, item)
        if kind != occult_enum.HUMAN and tracker.has_occult_type(kind) and kind == tracker._sim_info.current_occult_types:
            tracker._generate_sim_info(kind, generate_new=False)
    result = original(tracker, data)
    tracker._sim_info.occult_types = int(tracker._sim_info.occult_types) | (int(data.occult_types) & ~_known_mask(tracker))
    return result
