"""Semantic CAS CLI with separate native acknowledgements and no pointer input."""
import copy
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from types import SimpleNamespace

from source_manifest import sha256, write_json


class IntentEvidence:
    """Retain exact owner UUIDs before dispatch, independently of the final ACK."""
    def __init__(self, args):
        import reusable_profile
        self.profile_module = reusable_profile
        journal, _data, test, original = reusable_profile.load(args.state)
        raw = Path(args.output).absolute()
        raw_intent = raw.with_suffix('.intent.json')
        if raw.is_symlink() or raw_intent.is_symlink():
            raise ValueError('CAS evidence paths must not be linked.')
        self.output = reusable_profile.writable(raw)
        self.intent = reusable_profile.writable(raw_intent)
        if (self.output.suffix.lower() != '.json' or not self.output.parent.is_dir() or
                self.output == self.intent or any(path.exists() or path == journal or
                any(path == root or root in path.parents for root in (test, original))
                for path in (self.output, self.intent))):
            raise ValueError('Use new external CAS output and intent JSON filenames outside both profiles and the journal.')
        arguments = {name: str(value) if isinstance(value, Path) else value
                     for name, value in vars(args).items()}
        self.proof = {'schema': 1, 'operation': 'semantic-cas-cli-intent',
            'requested_operation': args.operation, 'sim_id': getattr(args, 'sim_id', None),
            'intended_request': arguments, 'stage': 'intent-recorded', 'owner_requests': [],
            'no_request_replay': True, 'automatic_replay_allowed': False}
        self.hashes = {}
        # Exclusive creation reserves both names. No transport runs until both
        # records are flushed; subsequent intent updates use atomic replace.
        self._create(self.output, {'ok': False, 'outcome': 'intent-recorded', 'intent_file': str(self.intent)})
        self._create(self.intent, self.proof)

    @staticmethod
    def _encoded(value):
        raw = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
        if len(raw) > 48 * 1024 * 1024:
            raise ValueError('CAS retained intent exceeds its complete-evidence bound.')
        return raw

    def _create(self, path, value):
        raw = self._encoded(value)
        with path.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        self.hashes[path] = sha256(path)

    def _write(self, path, value):
        self._encoded(value)
        if (self.profile_module.writable(path) != path or not path.is_file() or
                sha256(path) != self.hashes[path]):
            raise ValueError('CAS retained evidence changed; no foreign file will be overwritten.')
        write_json(path, value)
        self.hashes[path] = sha256(path)

    def record(self):
        self._write(self.intent, self.proof)

    def wrap(self, request):
        def retained(state, action, *values, **options):
            observer = options.pop('submission_observer', None)
            row = {'action': action, 'request_id': None, 'stage': 'awaiting-owner-uuid',
                   'intended_request': {'positional': list(values),
                       **{key: options[key] for key in ('sim_id', 'occult', 'value', 'seconds') if key in options}}}
            self.proof['owner_requests'].append(row)
            self.proof['stage'] = 'owner-request-preflight'
            self.record()
            def submitting(observed_action, request_id):
                if (observed_action != action or not isinstance(request_id, str) or
                        re.fullmatch('[0-9a-f]{32}', request_id) is None or row['request_id'] is not None or
                        any(other is not row and other['request_id'] == request_id
                            for other in self.proof['owner_requests'])):
                    raise ValueError('Owner submission callback has a foreign, duplicate or invalid action/UUID; no dispatch authorized.')
                row.update(request_id=request_id, stage='owner-submission-intent')
                self.proof['stage'] = 'owner-submission-intent'
                self.record()
                if observer is not None:
                    observer(observed_action, request_id)
            try:
                result = request(state, action, *values, **options, submission_observer=submitting)
                if row['request_id'] is None:
                    raise ValueError('Owner transport omitted its pre-dispatch UUID callback; no replay is permitted.')
                row['result'] = result
                if not isinstance(result, dict):
                    raise ValueError('Owner transport returned an untyped result; retain the original UUID.')
                if 'ok' in result and type(result['ok']) is not bool:
                    raise ValueError('Owner acknowledgement has an untyped ok value; retain the original UUID without replay.')
                row['owner_ack_identity_verified'] = result.get('request_id') == row['request_id']
                if ((result.get('ok') is True and not row['owner_ack_identity_verified']) or
                        result.get('request_id') is not None and not row['owner_ack_identity_verified']):
                    raise ValueError('Owner acknowledgement has a missing or foreign UUID; retain the original UUID without replay.')
                if action == 'cas_ui_result':
                    row['cas_ack_identity_verified'] = result.get('cas_request_id') == options.get('value')
                    if ((result.get('ok') is True and not row['cas_ack_identity_verified']) or
                            result.get('cas_request_id') is not None and not row['cas_ack_identity_verified']):
                        raise ValueError('CAS result has a missing or foreign request UUID; retain the original request without replay.')
                row['stage'] = 'owner-response-retained'
                self.proof['stage'] = 'owner-response-retained'
                self.record()
                return result
            except BaseException as error:
                row.update(stage='owner-request-unresolved', error=str(error), error_type=type(error).__name__)
                self.proof['stage'] = 'owner-request-unresolved'
                try:
                    self.record()
                except Exception:
                    # The prior flushed UUID is already durable. Do not replay
                    # a request or overwrite a changed file to repair evidence.
                    pass
                raise
        return retained

    def finish(self, result):
        if not isinstance(result, dict):
            raise ValueError('CAS operation returned no typed retained result.')
        self.proof.update(stage='result-retained', result=result)
        self.record()
        final = dict(result, intent_file=str(self.intent), intent_sha256=self.hashes[self.intent])
        self._write(self.output, final)
        return dict(final, output=str(self.output), proof_sha256=self.hashes[self.output])

    def fail(self, error):
        self.proof.update(stage='execution-stopped', error=str(error), error_type=type(error).__name__)
        self.record()
        self._write(self.output, {'ok': False, 'outcome': 'unresolved', 'message': str(error),
            'intent_file': str(self.intent), 'intent_sha256': self.hashes[self.intent],
            'owner_requests': self.proof['owner_requests'], 'automatic_replay_allowed': False})


def execute(args, request, monotonic=time.monotonic, pause=time.sleep):
    from cli_identity_cache import session
    with session(args.state):
        if getattr(args, 'output', None) is None:
            return _execute(args, request, monotonic, pause)
        evidence = IntentEvidence(args)
        internal = copy.copy(args)
        internal.output = None
        try:
            return evidence.finish(_execute(internal, evidence.wrap(request), monotonic, pause))
        except BaseException as error:
            try:
                evidence.fail(error)
            except Exception:
                pass  # Keep the last intact intent, including any submitted UUID.
            raise


def _execute(args, request, monotonic=time.monotonic, pause=time.sleep):
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
        if args.operation == 'select' and getattr(args, 'base_data_id', None) is not None:
            value['base_data_id'] = args.base_data_id
        if args.operation == 'accept': value['household_id'] = getattr(args, 'household_id', None)
        if args.operation == 'form-select':
            value.update(household_id=getattr(args, 'household_id', None),
                         expected_layer=getattr(args, 'expected_layer', None),
                         form_flags=getattr(args, 'form_flags', None),
                         native_session=getattr(args, 'native_session', None))
        if args.operation == 'member-select':
            value.update(household_id=getattr(args,'household_id',None),expected_layer=getattr(args,'expected_layer',None),
                native_session=getattr(args,'native_session',None),target_sim_id=getattr(args,'target_sim_id',None))
        if args.operation == 'layer-select':
            value.update(household_id=getattr(args, 'household_id', None),
                         expected_layer=getattr(args, 'expected_layer', None),
                         target_layer=getattr(args, 'target_layer', None),
                         native_session=getattr(args, 'native_session', None))
        # Validate before any transport, using the same production contract.
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
        from apex_core.cas_ui import envelope
        envelope(args.sim_id, value)
        if args.operation in ('form-select', 'layer-select', 'member-select'):
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
            observation = preflight['client'].get('owner_pair_observation')
            if (selected.get('householdId') != value['household_id'] or
                    type(selected.get('occultLayer')) is not int or
                    selected['occultLayer'] != value['expected_layer'] or
                    not isinstance(observation, dict) or
                    type(observation.get('session')) is not int or
                    observation['session'] != value['native_session']):
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
    if result.get('ok') is True and isinstance(result.get('member_selection'), dict):
        # The mutation ACK belongs to the old peer. The UI reconnects on its
        # next Timer tick; a fast following command otherwise finds neither
        # the destination socket nor an active gameplay distributor client.
        # Never repeat selection. Await the destination, then verify its fresh
        # status against this already completed native receipt.
        receipt = result['member_selection']
        target = receipt['target_sim_id']
        rebound = None
        while monotonic() < deadline:
            peers = request(args.state, 'cas_ui_diagnostics').get('native_peers', [])
            ready = any(isinstance(peer, dict) and peer.get('sim_id') == target and
                type(peer.get('age_seconds')) in (int, float) and math.isfinite(peer['age_seconds']) and
                0 <= peer['age_seconds'] <= 3 for peer in peers)
            if ready:
                remaining = deadline - monotonic()
                if remaining <= 0: break
                rebound = execute(SimpleNamespace(operation='status', state=args.state, sim_id=target,
                    seconds=min(60, remaining), output=None), request, monotonic=monotonic, pause=pause)
                break
            pause(.15)
        if rebound is not None and rebound.get('ok') is True:
            selected = rebound['client']['sim']
            observation = rebound['client'].get('owner_pair_observation', {})
            if (selected.get('simId') != target or selected.get('householdId') != receipt['household_id'] or
                    type(selected.get('occultLayer')) is not int or selected['occultLayer'] != 0 or
                    type(selected.get('occultType')) is not int or selected['occultType'] != receipt['target_form_flags'] or
                    observation.get('session') != receipt['native_session']):
                raise ValueError('CAS destination changed during peer handoff; selection must not be replayed.')
            result = dict(result, peer_rebound_verified=True, next_native_commands_ready=True,
                          destination_status=rebound)
        else:
            result = dict(result, ok=False, outcome='member-selected-peer-unresolved',
                peer_rebound_verified=False, next_native_commands_ready=False, destination_status=rebound,
                message='Member selection completed; destination peer is unresolved. Retain this UUID and do not repeat selection.')
    if preflight is not None:
        result = dict(result, form_selection_preflight=preflight,
                      form_selection_preflight_verified=True)
    if output is not None:
        write_json(output, result)
        return dict(result, output=str(output), proof_sha256=sha256(output))
    return result
