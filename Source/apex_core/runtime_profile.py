"""Opt-in, bounded game-thread menu profiling for the disposable CLI.

No profiler or Sim reads run during ordinary gameplay. The existing core
tick stops an explicitly requested sample automatically.
"""
import threading
import time

_ACTIVE = None
_LAST = None


def _finish(backend, clock):
    global _ACTIVE, _LAST
    item = _ACTIVE
    if item is None:
        return _LAST
    if threading.get_ident() != item['thread']:
        raise ValueError('Profiling must finish on its original game thread.')
    item['profiler'].disable()
    _ACTIVE = None
    backend._APEX_PROFILE_PULSE = None
    rows = []
    for stat in item['profiler'].getstats():
        code = stat.code
        rows.append(dict(name=code if isinstance(code, str) else code.co_name,
            file='' if isinstance(code, str) else code.co_filename,
            line=0 if isinstance(code, str) else code.co_firstlineno,
            calls=stat.callcount, recursive_calls=stat.reccallcount,
            self_ms=stat.inlinetime*1000, cumulative_ms=stat.totaltime*1000))
    _LAST = dict(ok=True, state='completed', label=item['label'],
        elapsed_seconds=max(0, clock()-item['started']),
        top_self=sorted(rows, key=lambda row: row['self_ms'], reverse=True)[:80],
        top_cumulative=sorted(rows, key=lambda row: row['cumulative_ms'], reverse=True)[:80],
        game_thread_only=True, appearance_written=False, save_submitted=False)
    return _LAST


def control(backend, argument, clock=time.monotonic, factory=None):
    global _ACTIVE
    if not isinstance(argument, dict) or argument.get('operation') not in ('start','status','stop'):
        raise ValueError('Use a typed profiling operation.')
    operation = argument['operation']
    if operation != 'start':
        if set(argument) != {'operation'}:
            raise ValueError('Unexpected profiling fields.')
        if operation == 'stop':
            return _finish(backend, clock) or dict(ok=True, state='idle')
        if _ACTIVE is not None:
            return dict(ok=True, state='running', label=_ACTIVE['label'],
                remaining_seconds=max(0, _ACTIVE['deadline']-clock()), profiling_overhead_present=True)
        return _LAST or dict(ok=True, state='idle')
    if (set(argument) != {'operation','seconds','label'} or
            type(argument['seconds']) is not int or not 1 <= argument['seconds'] <= 30 or
            not isinstance(argument['label'], str) or not 1 <= len(argument['label']) <= 80 or
            any(ord(c) < 32 for c in argument['label'])):
        raise ValueError('A sample needs 1–30 seconds and a bounded label.')
    if _ACTIVE is not None or getattr(backend, '_APEX_PROFILE_PULSE', None) is not None:
        raise ValueError('A profiling sample is already active; do not restart it.')
    if factory is None:
        import cProfile
        factory = cProfile.Profile
    profiler = factory()
    now = clock()
    item = dict(profiler=profiler, started=now, deadline=now+argument['seconds'],
        thread=threading.get_ident(), label=argument['label'])
    def pulse():
        global _ACTIVE, _LAST
        # A diagnostic must never raise into the game's ordinary core tick.
        # Only the original thread can disable its profiler; a foreign pulse
        # leaves it for the next owned tick rather than losing that authority.
        if (_ACTIVE is not item or threading.get_ident() != item['thread'] or
                clock() < item['deadline']):
            return
        try:
            _finish(backend, clock)
        except Exception as error:
            try:
                profiler.disable()
            except Exception:
                pass
            _ACTIVE = None
            backend._APEX_PROFILE_PULSE = None
            _LAST = dict(ok=False, state='failed', label=item['label'],
                error=str(error)[:500], game_thread_only=True,
                appearance_written=False, save_submitted=False)
    _ACTIVE = item
    backend._APEX_PROFILE_PULSE = pulse
    try:
        profiler.enable()
    except Exception:
        try:
            profiler.disable()
        except Exception:
            pass
        _ACTIVE = None
        backend._APEX_PROFILE_PULSE = None
        raise
    return dict(ok=True, state='running', label=item['label'], seconds=argument['seconds'],
        game_thread_only=True, profiling_overhead_present=True, appearance_written=False, save_submitted=False)
