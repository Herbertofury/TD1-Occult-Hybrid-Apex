"""Recorded controls for the disposable native CAS engine qualification."""
import json
from pathlib import Path
from types import SimpleNamespace
from cas_client import IntentEvidence
from cli_identity_cache import session
import reusable_profile


def run(state, output, request, argument):
    if output is None:
        raise ValueError('Use a new external --output JSON for native form patch evidence.')
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
    from apex_core.native_cas_engine import argument as validate
    validate(argument)
    state = Path(state)
    with session(state):
        _, journal, _, _ = reusable_profile.load(state)
        evidence = IntentEvidence(SimpleNamespace(operation='native-cas-engine', state=state, output=Path(output), sim_id=None))
        evidence.proof['native_engine_request'] = argument
        evidence.record()
        call = evidence.wrap(request)
        try:
            # A committed-owner export requires an already armed graph in the
            # exact running DLL. Starting the renderer again cannot create that
            # graph. Dispatch this read directly; the game still verifies the
            # loaded DLL, scope, owner and generation, and fails if absent.
            startup = (None if argument['operation'] in ('export-owner','export-owner-page') else
                call(state, 'overlay_start', value=json.dumps({'test_token': journal['token'], 'value': None})))
            if startup is not None and startup.get('ok') is not True:
                result = dict(ok=False, message='Matching native sidecar did not start.', startup=startup)
            else:
                result = call(state, 'test_native_cas_engine', value=json.dumps({'test_token': journal['token'], 'value': argument}))
            final = evidence.finish(result)
        except BaseException as error:
            evidence.fail(error)
            raise
    return {key: final.get(key) for key in ('ok', 'message', 'scope_id', 'armed', 'selection_enabled',
            'members', 'existing_owner_selections', 'proof_sha256', 'production_ready')}
