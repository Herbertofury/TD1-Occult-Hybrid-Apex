"""One recorded cold-menu code inspection; no Sim or gameplay operations."""
import json
from pathlib import Path
from types import SimpleNamespace
from cas_client import IntentEvidence
from cli_identity_cache import session
import reusable_profile


def run(state, output, request, code_window=None):
    if output is None:
        raise ValueError('Use a new external --output JSON for native code inspection.')
    if code_window is not None:
        if (not isinstance(code_window, dict) or set(code_window) != {'rva', 'bytes'} or
                type(code_window['rva']) is not int or not 0 <= code_window['rva'] <= 0xffffffff or
                type(code_window['bytes']) is not int or not 1 <= code_window['bytes'] <= 8192):
            raise ValueError('Use an exact code RVA and 1..8192 bytes.')
    state=Path(state)
    with session(state):
        _,journal,_,_=reusable_profile.load(state)
        operation='native-cas-probe' if code_window is None else 'native-cas-code-window'
        evidence=IntentEvidence(SimpleNamespace(operation=operation,state=state,output=Path(output),sim_id=None))
        evidence.proof['operation']=('read-only-native-cas-code-probe-intent' if code_window is None
                                     else 'read-only-native-cas-code-window-intent')
        if code_window is not None:evidence.proof['requested_code_window']=dict(code_window)
        evidence.record()
        call=evidence.wrap(request)
        envelope=json.dumps({'test_token':journal['token'],'value':None})
        try:
            # A code window requires the already loaded exact native DLL.
            # Read it directly; starting the renderer adds no read authority
            # and can stall an unrelated CAS session.
            startup=None if code_window is not None else call(state,'overlay_start',value=envelope)
            if startup is not None and startup.get('ok') is not True:
                result=dict(ok=False,message='Native sidecar initialization was not acknowledged.',
                    startup=startup,probe_submitted=False,native_patch_qualified=False)
            else:
                action='test_native_cas_probe' if code_window is None else 'test_native_cas_code_window'
                result=call(state,action,value=json.dumps({'test_token':journal['token'],'value':code_window}))
                if (result.get('read_only') is not True or result.get('game_memory_written') is not False or
                        result.get('game_files_written') is not False or result.get('native_patch_qualified') is not False):
                    raise ValueError('Native code inspection lacks its no-write contract.')
                result=dict(result,startup=startup,probe_submitted=True)
            final=evidence.finish(result)
        except BaseException as error:
            try: evidence.fail(error)
            except Exception: pass  # Retain the last flushed UUID even if final publication fails.
            raise
    references=sum(len(target.get('references',[])) for service in final.get('services',[])
                   for target in service.get('targets',[]))
    return dict(ok=final.get('ok') is True,output=str(output),proof_sha256=final['proof_sha256'],
        message=final.get('message'),reference_count=references,
        function_snapshots=len(final.get('function_snapshots',[])),
        controller_available=final.get('controller',{}).get('available',False),
        controller_methods=final.get('controller',{}).get('methods',[]),
        code_snapshot_bytes=final.get('code_snapshot_bytes',0),code_rva=final.get('code_rva'),
        captured_bytes=final.get('captured_bytes'),code_sha256=final.get('code_sha256'),native_patch_qualified=False)
