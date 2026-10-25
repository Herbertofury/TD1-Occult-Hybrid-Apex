"""Actual CAS prepare continuation. Native jobs receive copied bytes/primitives.

The authenticated loader supplies submit/poll callables once; this module never
loads a DLL, opens the bank, waits/joins, or runs game APIs on a worker thread.
"""
import copy
import json
import os
from pathlib import Path
import threading
import time

from .command_queue import OwnerContinuation
from . import cas_bank_transaction as bank, cas_commit_plan as primitive


def _wire(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                      separators=(',', ':')).encode('ascii')


class NativeBinding:
    """Frozen native byte ABI; root was authenticated by the existing loader."""
    def __init__(self, root, submit, poll):
        self.path = Path(os.path.abspath(str(root))) / 'form_bank.json'
        self.submit_call, self.poll_call = submit, poll
        self.owner = threading.current_thread().ident
        self.costs = dict(selected_decode_ms=0.0, selected_copy_encode_ms=0.0,
                          native_submit_ms=0.0, native_poll_ms=0.0)

    def _owner(self):
        if threading.current_thread().ident != self.owner:
            raise ValueError('Bank binding requires its canonical owner.')

    def submit(self, request, payload=b''):
        self._owner()
        header = _wire(request)
        if len(header) > 4096 or type(payload) is not bytes or len(payload) > primitive.MAX_DOCUMENT_BYTES:
            raise ValueError('Native bank header/payload exceeds its bound.')
        started = time.perf_counter()
        ticket = self.submit_call(header, payload)
        self.costs['native_submit_ms'] += (time.perf_counter() - started) * 1000.0
        if type(ticket) is not int or not 0 < ticket < 2**64:
            raise ValueError('Worker refused before admission; no fallback mutation submitted.')
        return ticket

    def poll(self, request, ticket):
        self._owner()
        started = time.perf_counter()
        raw = self.poll_call(_wire(request), ticket)
        self.costs['native_poll_ms'] += (time.perf_counter() - started) * 1000.0
        if type(raw) is not bytes or not 0 < len(raw) <= primitive.MAX_DOCUMENT_BYTES + 4096:
            raise ValueError('Native bank returned an invalid owned byte receipt.')
        started = time.perf_counter()
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=bank._pairs,
                           parse_float=bank._finite_float, parse_constant=bank._invalid_constant)
        self.costs['selected_decode_ms'] += (time.perf_counter() - started) * 1000.0
        if not isinstance(value, dict) or value.get('state') not in ('pending', 'ready', 'failed'):
            raise ValueError('Worker receipt is untyped.')
        return value


def _native_probe(backend):
    from . import native_cas_engine, cas_auto_settle
    scope = native_cas_engine._LAYOUT_SCOPE
    if scope is None:
        return None
    value = cas_auto_settle._native_status(backend)
    if value.get('ok') is not True or value.get('pid') != os.getpid() or value.get('scope_id') != scope.get('scope_id'):
        raise ValueError('Native CAS scope/generation fence is unavailable.')
    rows = value.get('members')
    if not isinstance(rows, list):
        raise ValueError('Native CAS roster fence is incomplete.')
    return (id(scope), value['scope_id'], tuple(sorted((row['sim_id'], row['graph_generation'],
        row['graph_selected_owner_id'], tuple(row['logical_owner_ids']), row['human_owner_id'],
        row['native_view_fault']) for row in rows)))


class _Fence:
    def __init__(self, backend, sim, probe):
        self.backend, self.sim, self.probe = backend, sim, probe
        from . import cas_auto_settle
        self.live_household, self.live_roster = cas_auto_settle._live(backend)
        self.identity = bank._identity(backend, sim)
        if (str(self.live_household.id) != self.identity['household_id'] or
                self.live_roster.get(str(sim.id)) is not sim):
            raise ValueError('Prepare requires its exact current Live household member.')
        self.root = os.path.normcase(os.path.abspath(str(backend._data_directory())))
        self.tracker = sim.occult_tracker
        self.owners = primitive._forms(backend, sim, primitive._known(backend))
        self.roster = self._roster()
        self.native = probe(backend)
        self.before = primitive.read_owners(backend, sim, lambda: bank._identity(backend, sim))
        self.observed_return = None
        self.return_required = False
        self.epoch = None

    def bind_observed(self, captured, instance, argument):
        from . import native_cas_engine
        if not bank._same_json_receipt(self.before, instance.document.get('pre_write_owners')):
            raise ValueError('Complete physical owners changed after receiver observation.')
        self.epoch = argument.get('expected_pending_sha256')
        if not primitive._hash(self.epoch):
            raise ValueError('Prepare requires its exact observed transaction epoch.')
        self.return_required = captured.get('native_return_required', False)
        if type(self.return_required) is not bool:
            raise ValueError('Observed native return requirement is untyped.')
        if self.return_required:
            observed = captured.get('native_return')
            if (not isinstance(observed, dict) or observed.get('checkpoint_epoch') != self.epoch or
                    not isinstance(observed.get('identity'), dict) or
                    observed['identity'].get('pid') != self.identity['runtime_pid'] or
                    observed['identity'].get('sim_id') != self.identity['sim_id']):
                raise ValueError('Prepare has no complete receiver-held observed native return.')
            self.observed_return = copy.deepcopy(observed)
        self.check_native_return()

    def check_native_return(self):
        from . import native_cas_engine
        owned = native_cas_engine.owns_return(self.identity['sim_id'], self.epoch)
        if owned is not self.return_required:
            raise ValueError('Native return requirement changed after observation.')
        if self.return_required:
            fresh = native_cas_engine.returned_owners(self.backend, self.sim, self.epoch)
            if not bank._same_json_receipt(fresh, self.observed_return):
                raise ValueError('Complete native canonical/active/named owners changed after observation.')
        # The native export can cross several pages/calls. Bracket it with
        # the actual Live/no-editor predicate, rather than assuming a native
        # call cannot re-enter editor lifecycle code.
        self._assert_live()

    def _assert_live(self):
        from . import cas_auto_settle
        household, live_roster = cas_auto_settle._live(self.backend)
        if (household is not self.live_household or set(live_roster) != set(self.live_roster) or
                any(live_roster[sid] is not owner for sid, owner in self.live_roster.items())):
            raise ValueError('Prepare running Live household/roster changed while waiting.')

    def _roster(self):
        resolver = getattr(self.backend, '_household_sim_infos', None)
        if not callable(resolver):
            raise ValueError('Prepare requires the actual current household roster.')
        rows = tuple(resolver(self.sim))
        if (not rows or len(rows) > 4096 or len({str(row.id) for row in rows}) != len(rows) or
                any(self.backend._get_sim_info_by_id(row.id) is not row or
                    str(row.household_id) != self.identity['household_id'] for row in rows)):
            raise ValueError('Prepare household roster is missing or duplicated.')
        return {str(row.id): row for row in rows}

    def check(self):
        self._assert_live()
        if (bank._identity(self.backend, self.sim) != self.identity or self.sim.occult_tracker is not self.tracker or
                os.path.normcase(os.path.abspath(str(self.backend._data_directory()))) != self.root):
            raise ValueError('Prepare save/household/Sim/tracker fence changed.')
        roster = self._roster()
        current = primitive._forms(self.backend, self.sim, primitive._known(self.backend))
        if (set(roster) != set(self.roster) or any(roster[sid] is not owner for sid, owner in self.roster.items()) or
                set(current) != set(self.owners) or any(current[lane] is not owner for lane, owner in self.owners.items()) or
                self.probe(self.backend) != self.native):
            raise ValueError('Prepare household/native form generation or owner map changed.')
        raw = primitive.read_owners(self.backend, self.sim, lambda: bank._identity(self.backend, self.sim))
        if not bank._same_json_receipt(raw, self.before):
            raise ValueError('Complete native before-image changed while prepare was waiting.')
        self.check_native_return()


class _View:
    def __init__(self, action, receipt):
        self.action = action
        self.advance(receipt)

    def advance(self, receipt):
        req = self.action.request
        if (receipt.get('ok') is not True or receipt.get('state') != 'ready' or
                receipt.get('request_id') != req['request_id'] or
                receipt.get('transaction_id') != req['transaction_id'] or
                receipt.get('sequence') != req['sequence'] or receipt.get('identity') != req['identity'] or
                receipt.get('native_call_authorized') is not False or
                type(receipt.get('durable')) is not bool or
                receipt['durable'] != (req['operation'] != 'read-selected') or
                not all(primitive._hash(receipt.get(name)) for name in
                    ('file_sha256', 'record_sha256', 'journal_sha256')) or not isinstance(receipt.get('record'), dict)):
            raise ValueError('Worker receipt lacks its exact immutable context/phase/readback.')
        self.receipt, self.record = receipt, receipt['record']

    def context(self, backend, sim, fresh):
        action = self.action
        bank._thread(backend)
        if backend is not action.backend or sim is not action.sim:
            raise ValueError('Selected-record view cannot inspect another Sim.')
        identity = bank._identity(backend, sim) if fresh else None
        if fresh and identity != action.fence.identity:
            raise ValueError('Selected-record view belongs to another native context.')
        return identity, action.binding.path, action.key, {'schema': 1, 'records': {action.key: self.record}}, self.receipt['file_sha256'], self.record


class _Wait:
    def __init__(self, request, ticket):
        self.request, self.ticket = request, ticket


class PrepareAction(OwnerContinuation):
    def __init__(self, backend, sim, argument, binding, request_id, native_probe=_native_probe):
        bank._thread(backend)
        if not bank._token(request_id) or bank._BANK_ASYNC_VIEW is not None:
            raise ValueError('Prepare needs one fresh owner-bound transport UUID.')
        self.backend, self.sim, self.binding = backend, sim, binding
        self.costs = dict(owner_capture_ms=0.0, owner_fence_ms=0.0, owner_planner_ms=0.0)
        started = time.perf_counter()
        self.fence = _Fence(backend, sim, native_probe)
        self.costs['owner_capture_ms'] += (time.perf_counter() - started) * 1000.0
        self.key = self.fence.identity['save_guid'] + ':' + self.fence.identity['sim_id']
        if os.path.normcase(str(binding.path.parent)) != self.fence.root:
            raise ValueError('Authenticated bank worker belongs to another active profile root.')
        # The held receiver is mandatory. JSON cannot reconstruct it or make a
        # previous-runtime journal into authority over a current native Sim.
        held = [(key, value) for key, value in bank._CAPTURED.items()
                if key[:2] == (str(binding.path), self.key) and value.get('backend') is backend and
                value.get('sim') is sim and value.get('identity') == self.fence.identity]
        if len(held) != 1 or held[0][0] not in bank._ACTIVE:
            raise ValueError('Prepare has no exact live observed receiver capability.')
        cache_key, captured = held[0]
        self.instance = bank._ACTIVE[cache_key]
        if self.instance.state != 'observed' or captured.get('prepare_async_request') is not None:
            raise ValueError('Prepare was already issued or receiver is not observed; no replay.')
        self.argument = copy.deepcopy(argument)  # typed small intent only
        self.fence.bind_observed(captured, self.instance, self.argument)
        self.request = dict(request_id=request_id, transaction_id=cache_key[2], identity=self.fence.identity,
            operation='read-selected', sequence=0, expected_file_sha256=None, expected_record_sha256=None,
            expected_journal_sha256=None, document_sha256=None)
        ticket = binding.submit(self.request)
        captured['prepare_async_request'] = request_id
        self.waiting = _Wait(self.request, ticket)
        self.view, self.generator, self.terminal = None, None, None

    def _journal(self, document, previous):
        path, key, record, transaction = bank._selected(self.backend, self.sim, self.request['transaction_id'])
        current = transaction.get('journal')
        if (primitive.digest(current) != previous or document.get('identity') != self.fence.identity or
                document.get('pending_sha256') != transaction['checkpoint_sha256']):
            raise ValueError('Exact journal predecessor/checkpoint changed before async storage.')
        old_plan = current.get('plan', {})
        plan = document.get('plan', {})
        operation = ('plan-base' if current.get('state') == 'observed' else
                     'plan-named' if 'native_owner_return_sha256' in plan and
                        plan.get('native_owner_return_sha256') != old_plan.get('native_owner_return_sha256') else
                     'plan-hair' if 'hair_policy_contract' in plan and 'hair_policy_contract' not in old_plan else None)
        if operation is None:
            raise ValueError('Unreviewed PreparePlan journal transition.')
        started = time.perf_counter()
        payload = primitive._json(document)  # selected journal only, never whole bank
        self.binding.costs['selected_copy_encode_ms'] += (time.perf_counter() - started) * 1000.0
        self.request = dict(self.request, operation=operation, sequence=self.request['sequence'] + 1,
            expected_file_sha256=self.view.receipt['file_sha256'],
            expected_record_sha256=self.view.receipt['record_sha256'],
            expected_journal_sha256=previous, document_sha256=primitive.digest(document))
        ticket = self.binding.submit(self.request, payload)
        received = yield _Wait(self.request, ticket)
        self.view.advance(received)
        if self.view.receipt['journal_sha256'] != self.request['document_sha256']:
            raise ValueError('Complete journal receipt differs from submitted plan.')
        return dict(durable=True, sha256=self.view.receipt['journal_sha256'])

    def resume(self):
        bank._thread(self.backend)
        if self.terminal is not None:
            return self.terminal
        try:
            receipt = self.binding.poll(self.waiting.request, self.waiting.ticket)
            if receipt.get('state') == 'pending':
                return self
            if receipt.get('ok') is not True:
                raise ValueError(receipt.get('message', 'Worker outcome retained as uncertain.'))
            started = time.perf_counter()
            self.fence.check()
            self.costs['owner_fence_ms'] += (time.perf_counter() - started) * 1000.0
            if self.view is None:
                self.view = _View(self, receipt)
                self.instance.journal_writer_steps = self._journal
                self.generator = bank.prepare_steps(self.backend, self.sim, self.argument)
            prior = bank._BANK_ASYNC_VIEW
            if prior is not None:
                raise ValueError('A different selected-record owner scope is active.')
            started = time.perf_counter()
            bank._BANK_ASYNC_VIEW = self.view
            try:
                with bank._LOCK:
                    self.waiting = (next(self.generator) if self.request['operation'] == 'read-selected' else
                                    self.generator.send(receipt))
            except StopIteration as done:
                self.terminal = done.value
                if not isinstance(self.terminal, dict) or self.terminal.get('ok') is not True:
                    raise ValueError('Prepare continuation returned no explicit verified result.')
                self.terminal['async_prepare'] = True
            finally:
                bank._BANK_ASYNC_VIEW = None
                self.costs['owner_planner_ms'] += (time.perf_counter() - started) * 1000.0
            if self.terminal is not None:
                self.terminal['owner_phase_costs'] = dict(self.costs, **self.binding.costs)
                return self.terminal
            if not isinstance(self.waiting, _Wait):
                raise ValueError('Prepare yielded no typed immutable worker ticket.')
            return self
        except Exception as error:
            self.instance.state = 'recovery-required'
            self.instance.prepare_error = str(error)
            self.terminal = dict(ok=False, message=str(error), originals_and_returned_edits_retained=True,
                automatic_replay_allowed=False, save_reload_verified=False, native_write_attempted=False,
                async_prepare=True, owner_phase_costs=dict(self.costs, **self.binding.costs))
            return self.terminal
