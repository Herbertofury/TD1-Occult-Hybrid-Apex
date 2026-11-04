"""Exact legacy mutation boundaries must honor the canonical durable CAS gate.

This module registers nothing. The authorized namespace port inserts these
checks before verified old command/callback bodies; raw appearances are never
read or submitted by the guard.
"""
import threading


def _backend():
    import td1_occult_hybrid_apex as backend
    if (type(getattr(backend, '_APEX_GAME_THREAD_IDENT', None)) is not int or
            backend._APEX_GAME_THREAD_IDENT != threading.current_thread().ident):
        raise ValueError('Legacy occult changes require the canonical Apex game thread.')
    return backend


def _idle_info(backend, sim):
    identity = getattr(sim, 'id', None)
    if (sim is None or type(identity) is not int or not 0 < identity < 1 << 64 or
            backend._get_sim_info_by_id(str(identity)) is not sim):
        raise ValueError('Legacy occult changes require the exact manager-owned native Sim.')
    from .form_bank import assert_idle
    assert_idle(backend, sim)
    return sim


def _idle(backend, target):
    return _idle_info(backend, getattr(target, 'sim_info', None))


def sim_info_idle(sim):
    _idle_info(_backend(), sim)


def command_idle(opt_sim, connection):
    backend = _backend()
    from server_commands.argument_helpers import get_optional_target
    _idle(backend, get_optional_target(opt_sim, connection))


def interaction_idle(interaction):
    backend = _backend()
    _idle(backend, interaction.get_participant(interaction.picker_target))


def settings_idle():
    backend = _backend()
    client = backend.services.client_manager().get_first_client()
    sim = _idle(backend, getattr(client, 'active_sim', None))
    from . import form_bank
    from .cas_bank_transaction import _blocked, _lease_path
    path, _key = form_bank.context(backend, sim)
    if (_lease_path(path).exists() or
            any(_blocked(record, key) for key, record in form_bank.load(path)['records'].items())):
        raise ValueError('Legacy global settings are blocked while any retained CAS transaction remains unresolved.')


def retired(connection):
    """Known unsafe whole-household CAS/cache restoration has no legacy fallback."""
    from sims4.commands import CheatOutput
    CheatOutput(connection)('Legacy CAS edit/restore is disabled. Use Apex CAS History: retain every form original before CAS, then run/pause and review every changed form. No legacy traits or cached form maps were changed.')
    return False
