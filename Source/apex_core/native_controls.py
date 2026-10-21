"""Fixed game-owned native controls available before a household loads.

No gameplay service calls, evaluation or foreign process input. The fixed
native CAS reader explicitly reports whether cache-key metadata was inspected.
Request identities deduplicate commands after response loss.
"""
from collections import OrderedDict
import threading

ACTIONS = frozenset(('test_input', 'test_capture', 'test_studio_ui', 'test_preview', 'test_native_cas_probe', 'test_native_cas_code_window', 'test_native_cas_engine', 'overlay_start', 'overlay_status', 'overlay_show', 'overlay_hide'))
_LOCK = threading.RLock()
_RESULTS = OrderedDict()


def dispatch(backend, action, value, request_id):
    if action not in ACTIONS or not isinstance(request_id, str) or len(request_id) != 32 or any(c not in '0123456789abcdef' for c in request_id):
        raise ValueError('Unsupported native control or request identity.')
    from .test_driver import guard
    argument = guard(backend, value, limit=4 * 1024 * 1024) if action in ('test_preview','test_native_cas_engine') else guard(backend, value)
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
        elif action == 'test_preview':
            result = overlay_loader.sim_preview(backend.__file__, paths.DLL_PATH, argument)
        elif action == 'test_native_cas_probe':
            if argument is not None:
                raise ValueError('Native CAS inspection accepts no addresses or operations.')
            result = overlay_loader.native_cas_probe(backend.__file__, paths.DLL_PATH)
        elif action == 'test_native_cas_code_window':
            result = overlay_loader.native_cas_code_window(backend.__file__, paths.DLL_PATH, argument)
        elif action == 'test_native_cas_engine':
            result = overlay_loader.native_cas_engine_control(backend.__file__, paths.DLL_PATH, argument)
        else:
            result = overlay_loader.input_event(backend.__file__, paths.DLL_PATH, argument)
        sim_data_read = action == 'test_native_cas_engine' or (result.get('sim_data_read', False) if action in ('test_native_cas_probe', 'test_native_cas_code_window') else False)
        if type(sim_data_read) is not bool:
            raise ValueError('Native CAS metadata-read declaration is untyped.')
        result = dict(result, request_id=request_id, request_state='completed',
                      execution='fixed-native-control', sim_data_read=sim_data_read)
        _RESULTS[request_id] = (signature, result)
        while len(_RESULTS) > 128:
            _RESULTS.popitem(last=False)
        return dict(result)
