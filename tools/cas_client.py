"""Semantic CAS CLI with separate native acknowledgements and no pointer input."""
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

from source_manifest import sha256, write_json


def execute(args, request, monotonic=time.monotonic, pause=time.sleep):
    preflight = None
    if args.operation == 'panels': return request(args.state, 'cas_ui_panels')
    if args.operation == 'diagnostics': return request(args.state, 'cas_ui_diagnostics')
    if not 0 < args.seconds <= 60: raise ValueError('CAS acknowledgement wait must be 0-60 seconds.')
    output = args.output
    if output is not None:
        import reusable_profile
        _, _, test, original = reusable_profile.load(args.state)
        output = reusable_profile.writable(output)
        if output.exists() or any(output == root or root in output.parents for root in (test, original)):
            raise ValueError('Use a new external CAS evidence filename outside both profiles.')
    if args.operation == 'result':
        if not args.request_id: raise ValueError('Supply the unresolved CAS request ID.')
        request_id = args.request_id
    else:
        if not args.sim_id: raise ValueError('An explicit native CAS Sim identity is required.')
        value = {'operation': args.operation}
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
        from apex_core import cas_controls
        if args.operation in cas_controls.OPERATIONS:
            value.update({name: getattr(args, name, None) for name in cas_controls.SCHEMAS[args.operation] - {'operation'}})
        if args.operation in ('panel', 'select'): value['panel'] = args.panel
        if args.operation == 'outfit': value.update(category=args.category, index=args.index)
        if args.operation == 'outfit-add': value['category'] = args.category
        if args.operation in ('select', 'hair-swatch'): value['data_id'] = args.data_id
        if args.operation == 'accept': value['household_id'] = getattr(args, 'household_id', None)
        if args.operation == 'form-select':
            value.update(household_id=getattr(args, 'household_id', None),
                         expected_layer=getattr(args, 'expected_layer', None),
                         form_flags=getattr(args, 'form_flags', None),
                         native_session=getattr(args, 'native_session', None))
        # Validate before any transport, using the same production contract.
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
        from apex_core.cas_ui import envelope
        envelope(args.sim_id, value)
        if args.operation == 'form-select':
            # Keep the caller's exact session/layer capability. Refresh only its
            # native observation, so operator/CLI latency cannot expire the
            # five-second Source acknowledgement before the navigation request.
            preflight = execute(SimpleNamespace(operation='status', state=args.state,
                sim_id=args.sim_id, seconds=args.seconds, output=None), request,
                monotonic=monotonic, pause=pause)
            if preflight.get('ok') is not True:
                return dict(preflight, form_selection_submitted=False,
                            form_selection_preflight_verified=False)
            from apex_core.cas_ui import validate_client
            validate_client(preflight.get('client'), args.sim_id, {'operation': 'status'})
            selected = preflight['client']['sim']
            room = preflight.get('cas_room')
            if (selected.get('householdId') != value['household_id'] or
                    type(selected.get('occultLayer')) is not int or
                    selected['occultLayer'] != value['expected_layer'] or
                    not isinstance(room, dict) or
                    type(room.get('native_session')) is not int or
                    room['native_session'] != value['native_session']):
                raise ValueError('Fresh native CAS context differs from the requested session/layer/household; no form selection sent.')
        submitted = request(args.state, 'cas_ui_request', args.sim_id, value=json.dumps(value))
        request_id = submitted.get('cas_request_id')
        if not request_id:
            return dict(submitted, form_selection_preflight=preflight) if preflight is not None else submitted
    if len(request_id) != 32 or any(c not in '0123456789abcdef' for c in request_id):
        raise ValueError('Use the returned CAS request identity.')
    deadline = monotonic() + args.seconds
    result = None
    while monotonic() < deadline:
        result = request(args.state, 'cas_ui_result', args.sim_id, value=request_id)
        if result.get('outcome') != 'pending-client': break
        pause(.15)
    if result is None or result.get('outcome') == 'pending-client':
        result = {'ok': False, 'outcome': 'unresolved', 'cas_request_id': request_id,
                  'ui_transition_verified': False, 'input_submitted': False,
                  'message': 'Native CAS acknowledgement was not observed; poll this ID rather than repeating.'}
    if preflight is not None:
        result = dict(result, form_selection_preflight=preflight,
                      form_selection_preflight_verified=True)
    if output is not None:
        write_json(output, result)
        return dict(result, output=str(output), proof_sha256=sha256(output))
    return result
