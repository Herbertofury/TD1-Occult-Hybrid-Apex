"""Fixed game-owned native controls available before a household loads.

No Sim inspection, gameplay service calls, evaluation or foreign process input.
Request identities deduplicate commands after response loss.
"""
from collections import OrderedDict
import threading

ACTIONS = frozenset(('test_input', 'test_capture', 'test_studio_ui', 'overlay_start', 'overlay_status', 'overlay_show', 'overlay_hide'))
_LOCK = threading.RLock()
_RESULTS = OrderedDict()


def dispatch(backend, action, value, request_id):
    if action not in ACTIONS or not isinstance(request_id, str) or len(request_id) != 32 or any(c not in '0123456789abcdef' for c in request_id):
        raise ValueError('Unsupported native control or request identity.')
    from .test_driver import guard
    argument = guard(backend, value)
    signature = (action, value)
    with _LOCK:
        prior = _RESULTS.get(request_id)
        if prior is not None:
            if prior[0] != signature:
                raise ValueError('Native request identity was reused with a different command.')
            return dict(prior[1])
        from . import overlay_loader
        import paths
        if action == 'overlay_start':
            result = overlay_loader.start(backend.__file__, paths.DLL_PATH)
        elif action == 'overlay_status':
            result = overlay_loader.status()
        elif action in ('overlay_show', 'overlay_hide'):
            result = overlay_loader.show(action == 'overlay_show')
        elif action == 'test_capture':
            result = overlay_loader.capture(overlay=argument == 'overlay')
        elif action == 'test_studio_ui':
            result = overlay_loader.studio_ui(backend.__file__, paths.DLL_PATH, argument)
        else:
            result = overlay_loader.input_event(backend.__file__, paths.DLL_PATH, argument)
        result = dict(result, request_id=request_id, request_state='completed',
                      execution='fixed-native-control', sim_data_read=False)
        _RESULTS[request_id] = (signature, result)
        while len(_RESULTS) > 128:
            _RESULTS.popitem(last=False)
        return dict(result)
