"""Capture household appearance metadata around one inspected native save.

Runs only at EA's existing game-thread generator boundary. No timer, input,
second native save, appearance restoration or native exception suppression.
"""
import copy
from pathlib import Path
import threading
from . import form_bank_seal as seal
from .overlay_loader import _unlinked


def prepare(backend, service, save_data):
    bank_path = _unlinked(Path(backend._data_directory()) / 'form_bank.json')
    slot = getattr(save_data, 'slot_id', None)
    if type(slot) is int and slot == 0:
        return None  # EA's internal travel/CAS scratch serialization stays native.
    if not bank_path.exists():
        return None
    guid = str(service.get_save_slot_proto_guid())
    records = seal._read(bank_path).get('records', {})
    if not any(isinstance(key, str) and key.startswith(guid + ':') for key in records):
        return None
    if threading.current_thread().ident != backend._APEX_GAME_THREAD_IDENT:
        raise ValueError('Appearance save capture requires the canonical game thread.')
    sim = backend._get_active_sim_info()
    identity, profile, _, selected_key, path = seal._identity(backend, sim)
    if type(slot) is not int or not 0 < slot < 0xffffffff:
        raise ValueError('The native save has no exact supported slot identity.')
    name = getattr(save_data, 'slot_name', None)
    if not isinstance(name, str) or not 0 < len(name.strip()) <= 128:
        raise ValueError('The native save has no bounded slot name.')
    target_file = _unlinked(profile / 'saves' / ('Slot_{:08x}.save'.format(slot)))
    from .test_driver import _save_file_evidence
    before = _save_file_evidence(profile, slot) if target_file.exists() else dict(
        path=str(target_file), exists=False, bytes=0, sha256=None)
    target = dict(slot_id=slot, slot_name=name, save_guid=guid, household_id=str(sim.household_id),
        sim_id=str(sim.id), expected_save_sha256=before['sha256'] or '0' * 64)
    # A CLI save already prepared its group before scheduling this same native
    # generator. Reuse that exact intent instead of submitting or capturing twice.
    held = seal._store(path)
    candidates = [(key, row) for key, row in held['records'].items() if isinstance(row, dict) and
        row.get('state') in ('save-intent', 'save-submitted') and
        row.get('save_group', {}).get('primary_key') == key and
        str(sim.id) in row['save_group'].get('roster_sim_ids', []) and
        row.get('identity') == identity and isinstance(row.get('target'), dict) and
        dict(row['target'], sim_id=str(sim.id)) == target]
    if len(candidates) > 1:
        raise ValueError('Multiple native appearance save intents are unresolved.')
    if candidates:
        primary, row = candidates[0]
        seal._save_group(held, selected_key, row['intent_id'], (row['state'],))
        receipt = dict(state=row['state'], intent_id=row['intent_id'], primary_key=primary)
    else:
        receipt = seal.begin_save(backend, sim, target, seal._live(backend, sim, target), before)
    if receipt.get('state') == 'not-applicable':
        return None
    if receipt['state'] == 'save-intent':
        seal.submitted(backend, sim, receipt, True)
    return dict(sim=sim, profile=profile, target=target, receipt=copy.deepcopy(receipt))


def finish(backend, context, succeeded):
    if context is None:
        return None
    sim, receipt = context['sim'], context['receipt']
    if not succeeded:
        # The original native generator returned a definite failure. Retain the
        # captured looks, but permit a later genuinely new native save request.
        identity, _, _, key, path = seal._identity(backend, sim)
        data = seal._store(path)
        _, rows = seal._save_group(data, key, receipt['intent_id'], ('save-submitted',))
        if any(row['identity'] != identity for row in rows.values()):
            raise ValueError('Failed native save changed appearance ownership.')
        for row in rows.values():
            row.update(state='save-rejected', native_save_failed=True)
        seal._write(path, data)
        return dict(state='save-rejected', native_save_succeeded=False)
    from .test_driver import _save_file_evidence
    file_row = _save_file_evidence(context['profile'], context['target']['slot_id'])
    return seal.complete_save(backend, sim, dict(intent_id=receipt['intent_id'],
        expected_save_sha256=file_row['sha256']))


def wrap(backend, original, reason):
    def _save_game_gen(self, timeline, save_game_data, check_cooldown=True):
        context = None
        applies = self is backend.services.get_persistence_service()
        if applies and not self.is_save_locked() and self.get_save_lock_tooltip() is None:
            # Slot0 is EA's internal CAS/travel scratch path. The guarded CAS
            # engine owns that serialization; it is not an actual file save.
            slot=getattr(save_game_data,'slot_id',None)
            if not (type(slot) is int and slot==0):
                from . import cas_save_boundary,cas_auto_settle
                if cas_save_boundary.admission(backend)['locked']:
                    cas_auto_settle.settle(backend)
                if cas_save_boundary.admission(backend)['locked']:
                    return (original.__globals__['SaveGameResult'].FAILED_SAVE_LOCKED,reason)
            try:
                context = prepare(backend, self, save_game_data)
            except Exception as error:
                backend._APEX_NAMED_SAVE_BOUNDARY = dict(state='capture-refused', error=str(error)[:2048],
                    native_save_submitted=False, appearance_written=False)
                return (original.__globals__['SaveGameResult'].FAILED_SAVE_LOCKED, reason)
        # Preserve all native yields, returns and exceptions. In particular a
        # cancellation or exception never turns an unknown save into a rejection.
        returned = yield from original(self, timeline, save_game_data, check_cooldown=check_cooldown)
        if applies and context is not None:
            try:
                success = returned[0] == original.__globals__['SaveGameResult'].SUCCESS
                backend._APEX_NAMED_SAVE_BOUNDARY = finish(backend, context, success)
            except Exception as error:
                # The file may already be saved. Do not claim native failure or
                # replay its save; retain the complete pending group for review.
                backend._APEX_NAMED_SAVE_BOUNDARY = dict(state='completion-unresolved',
                    intent_id=context['receipt']['intent_id'], error=str(error)[:2048],
                    native_save_replay_allowed=False, appearance_written=False)
        return returned
    _save_game_gen._apex_cas_save_boundary = backend
    _save_game_gen._apex_original = original
    _save_game_gen._apex_preservation_reason = reason
    return _save_game_gen
