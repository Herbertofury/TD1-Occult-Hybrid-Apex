"""Semantic CAS CLI with separate native acknowledgements and no pointer input."""
import json
from pathlib import Path
import sys
import time

from source_manifest import sha256, write_json


def execute(args, request, monotonic=time.monotonic, pause=time.sleep):
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
        submitted = request(args.state, 'cas_ui_request', args.sim_id, value=json.dumps(value))
        request_id = submitted.get('cas_request_id')
        if not request_id: return submitted
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
    if output is not None:
        write_json(output, result)
        return dict(result, output=str(output), proof_sha256=sha256(output))
    return result
