"""One recorded cold-menu code inspection; no Sim or gameplay operations."""
import json
from pathlib import Path
from types import SimpleNamespace
from cas_client import IntentEvidence
from cli_identity_cache import session
import reusable_profile


def run(state, output, request):
    if output is None:
        raise ValueError('Use a new external --output JSON for native code inspection.')
    state=Path(state)
    with session(state):
        _,journal,_,_=reusable_profile.load(state)
        evidence=IntentEvidence(SimpleNamespace(operation='native-cas-probe',state=state,output=Path(output),sim_id=None))
        evidence.proof['operation']='read-only-native-cas-code-probe-intent';evidence.record()
        call=evidence.wrap(request)
        envelope=json.dumps({'test_token':journal['token'],'value':None})
        try:
            # The existing loader is idempotent for the exact already-loaded
            # DLL; it rejects replacement/mismatched lifetimes instead of reloading.
            startup=call(state,'overlay_start',value=envelope)
            if startup.get('ok') is not True:
                result=dict(ok=False,message='Native sidecar initialization was not acknowledged.',
                    startup=startup,probe_submitted=False,native_patch_qualified=False)
            else:
                result=call(state,'test_native_cas_probe',value=envelope)
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
        code_snapshot_bytes=final.get('code_snapshot_bytes',0),native_patch_qualified=False)
