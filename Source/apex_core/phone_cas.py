"""Game-thread phone review of the durable all-owner CAS receiver.

Phone choices contain only an opaque review nonce, exact form and decision.
The receiver owns raw appearances, journals, hashes and native restoration.
Uncertain submissions are never automatically repeated, including observation.
"""
import json
import math
import threading
import time
import uuid

_SESSIONS = {}
_MAX_SESSIONS = 128
_FORMS = {'1': 'Human', '2': 'Alien', '4': 'Vampire', '8': 'Mermaid',
          '16': 'Spellcaster', '32': 'Werewolf', '64': 'Fairy'}
_DECISIONS = {'accept-returned': 'Keep returned edit', 'restore-original': 'Restore retained original'}


def _lane(value):
    return (isinstance(value, str) and value.isascii() and value.isdecimal() and
            str(int(value)) == value and 0 < int(value) < 1 << 32 and not int(value) & (int(value) - 1))


def _name(lane):
    return _FORMS.get(lane, 'Native form ' + lane)


def _hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _thread(backend):
    if (type(getattr(backend, '_APEX_GAME_THREAD_IDENT', None)) is not int or
            backend._APEX_GAME_THREAD_IDENT != threading.current_thread().ident):
        raise ValueError('Phone CAS controls require the canonical game thread.')


def _id(value):
    if not isinstance(value, int) or isinstance(value, bool) or not 0 < value < 1 << 64:
        raise ValueError('Native Live identity is unavailable or not an exact integer.')
    return str(value)


def _call(backend, sim_id, action, value=None):
    _thread(backend)
    result = backend.run_action(action, sim_id=sim_id, value=None if value is None else json.dumps(value))
    if not isinstance(result, dict) or result.get('ok') is not True:
        raise ValueError(result.get('message', 'Phone CAS result was not acknowledged.') if isinstance(result, dict)
                         else 'Phone CAS result was not a typed acknowledgement.')
    return result


def _live(backend, sim_id):
    """Read Live authority without serializing a Sim or touching appearances."""
    _thread(backend)
    sim = backend._get_sim_info_by_id(sim_id)
    services = backend.services
    zone, household = services.current_zone(), services.active_household()
    client = services.client_manager().get_first_client()
    if (sim is None or str(sim.id) != sim_id or sim.get_sim_instance() is None or
            zone is None or zone.is_zone_running is not True or zone.is_in_build_buy is not False or
            household is None or client is None or sim.household_id != household.id):
        raise ValueError('Return to the selected Sim’s running Live household before reviewing CAS.')
    diagnostic = _call(backend, sim_id, 'cas_ui_diagnostics')
    peers, requests = diagnostic.get('native_peers'), diagnostic.get('requests')
    if not isinstance(peers, list) or not isinstance(requests, list) or len(requests) > 512:
        raise ValueError('Native CAS ownership is unavailable; no observation submitted.')
    for peer in peers:
        age = peer.get('age_seconds') if isinstance(peer, dict) else None
        if type(age) not in (int, float) or not math.isfinite(age) or age < 0 or age <= 3:
            raise ValueError('Native CAS is active or its peer age is unknown; return to Live first.')
    for row in requests:
        expired = isinstance(row, dict) and row.get('state') == 'superseded-read' and row.get('operation') == 'status'
        if (not isinstance(row, dict) or row.get('state') not in ('completed', 'failed') and not expired or
                row.get('lifecycle_stage') in ('accept-intent', 'accept-unresolved') or
                row.get('outcome') in ('unresolved', 'accept-intent', 'accept-unresolved') or
                row.get('commit_outcome') == 'unresolved'):
            raise ValueError('A native CAS request is unresolved; retain it without repeating observation.')
    clock = services.game_clock_service()
    if clock is None or not callable(getattr(clock, 'now', None)):
        raise ValueError('Live clock authority is unavailable; CAS observation remains blocked.')
    timeline = services.time_service()
    if timeline is None or timeline.sim_timeline is None:
        raise ValueError('Live simulation timeline authority is unavailable; CAS observation remains blocked.')
    ticks, speed = timeline.sim_now.absolute_ticks(), clock.clock_speed
    if (type(ticks) is not int or not 0 <= ticks < 1 << 64 or
            not isinstance(speed, int) or isinstance(speed, bool) or not 0 <= int(speed) <= 3):
        raise ValueError('Live simulation tick/clock speed readback is unavailable.')
    return {'sim': sim, 'client': client, 'clock': clock, 'ticks': ticks, 'speed': int(speed),
        'identity': {'sim_id': _id(sim.id), 'household_id': _id(household.id),
                     'save_guid': _id(services.get_persistence_service().get_save_slot_proto_guid()),
                     'zone_id': _id(zone.id), 'client_id': _id(client.id)}}


class PhoneCasSession:
    def __init__(self, backend, sim_id):
        self.backend, self.sim_id = backend, sim_id
        self.nonce = uuid.uuid4().hex
        self.epoch = self.raw_hash = self.plan_hash = None
        self.phase = 'idle'
        self.evidence, self.decisions, self.receipts = [], {}, []
        self.observe_attempted = self.prepare_attempted = self.commit_attempted = False
        self.alarm = self.callback = None
        self.probe = None
        self.error = None
        self.ticking = False

    def _status(self):
        return _call(self.backend, self.sim_id, 'cas_bank_status')

    def _bind(self, status):
        epoch = status.get('expected_pending_sha256')
        if not _hash(epoch) or status.get('current_runtime') is not True:
            raise ValueError('No current-runtime retained CAS originals are available. Retain originals before CAS.')
        if self.epoch is not None and epoch != self.epoch:
            raise ValueError('Phone review belongs to an older CAS transaction; reopen the review.')
        self.epoch = epoch

    def _reopen(self, status):
        """Explicit review may adopt another frontend's fresh retained epoch."""
        epoch = status.get('expected_pending_sha256')
        if not _hash(epoch) or status.get('current_runtime') is not True:
            raise ValueError('No current-runtime retained CAS originals are available. Retain originals before CAS.')
        if self.epoch is not None and epoch != self.epoch:
            if self.alarm is not None or self.ticking:
                raise ValueError('An owned Live probe is still running; no new review adopted.')
            self.receipts.append({'operation': 'review-superseded', 'nonce': self.nonce,
                'epoch': self.epoch, 'phase': self.phase, 'new_epoch': epoch})
            self.nonce = uuid.uuid4().hex
            self.epoch = self.raw_hash = self.plan_hash = None
            self.phase, self.evidence, self.decisions = 'idle', [], {}
            self.observe_attempted = self.prepare_attempted = self.commit_attempted = False
            self.probe = self.error = None
        self._bind(status)

    def _clock_guard(self, status):
        if (self.alarm is not None or self.phase not in ('observed', 'planned', 'completed') or
                not self.probe or self.probe['positive_normal_ticks_verified'] is not True or
                self.probe['paused_verified'] is not True or self.probe.get('nonce') != self.nonce or
                self.probe.get('epoch') != self.epoch or self.probe.get('raw_hash') != self.raw_hash or
                self.probe.get('plan_hash') != self.plan_hash or status.get('current_runtime') is not True or
                status.get('expected_pending_sha256') != self.epoch or
                status.get('raw_return_sha256') != self.raw_hash or status.get('plan_sha256') != self.plan_hash):
            raise ValueError('Choose After CAS to verify normal Live ticks and Pause for this exact retained return.')
        live = _live(self.backend, self.sim_id)
        if (live['identity'] != self.probe['identity'] or live['sim'] is not self.probe['sim'] or live['speed'] != 0):
            raise ValueError('Exact verified Live Sim/client/zone and Pause must remain unchanged before applying the reviewed plan.')
        return live

    def begin(self):
        if self.alarm is not None:
            raise ValueError('Live review is still running; its owned probe must finish before another capture.')
        _live(self.backend, self.sim_id)
        status = self._status()
        if status.get('blocked') is True:
            self._bind(status)
            return {'ok': False, 'message': 'Existing CAS originals are retained. Review or resolve that transaction before another capture.'}
        # An explicit new capture may follow a receiver-completed transaction
        # from another frontend. Preserve receipts while invalidating old tags.
        self.nonce = uuid.uuid4().hex
        self.epoch = self.raw_hash = self.plan_hash = None
        self.evidence, self.decisions = [], {}
        self.observe_attempted = self.prepare_attempted = self.commit_attempted = False
        self.probe = self.error = None
        result = _call(self.backend, self.sim_id, 'cas_bank_begin')
        self._bind(dict(result, current_runtime=True))
        self.phase = 'captured'
        self.receipts.append({'operation': 'begin', 'nonce': self.nonce, 'receipt': result})
        return {'ok': True, 'message': 'All native form originals are retained. Enter CAS or MCCC CAS, then return to Live and choose “After CAS: run, pause and review”. Automatic MCCC entry capture is not installed.'}

    def _adopt_observation(self, status):
        self._bind(status)
        if (status.get('lane_change_evidence_available') is not True or
                not isinstance(status.get('changed_lanes'), list) or not isinstance(status.get('lane_change_evidence'), list) or
                not _hash(status.get('raw_return_sha256'))):
            raise ValueError('Complete returned-owner evidence is unavailable; no form decision may be guessed.')
        changed = status['changed_lanes']
        rows, seen = [], set()
        for row in status['lane_change_evidence']:
            if (not isinstance(row, dict) or not _lane(row.get('lane')) or row['lane'] in seen or
                    type(row.get('changed')) is not bool or not isinstance(row.get('changed_fields'), list) or
                    any(not isinstance(field, str) for field in row['changed_fields'])):
                raise ValueError('Returned form/field evidence is incomplete or ambiguous.')
            seen.add(row['lane'])
            if row['changed']:
                rows.append({'lane': row['lane'], 'fields': list(row['changed_fields'])})
        if (len(changed) != len(set(changed)) or set(changed) != {row['lane'] for row in rows} or
                status.get('evidence_establishes_edit_intent') is not False):
            raise ValueError('Every changed owner must have exact evidence; differences do not establish intent.')
        raw_hash = status['raw_return_sha256']
        if self.raw_hash is not None and self.raw_hash != raw_hash:
            raise ValueError('Returned-owner evidence changed after phone review; earlier choices are stale.')
        self.raw_hash, self.evidence = raw_hash, rows
        return status

    def refresh(self, reopen=False):
        status = self._status()
        self._reopen(status) if reopen else self._bind(status)
        if status.get('phase') == 'observed':
            self._adopt_observation(status)
            if self.phase not in ('blocked', 'observing', 'preparing', 'committing'):
                self.phase = 'observed'
        if status.get('completed_receipt') is True:
            self.phase = 'completed'
        return status

    def start_observe(self, callback=None):
        before = _live(self.backend, self.sim_id)
        status = self._status()
        self._bind(status)
        reopening = status.get('phase') == 'observed'
        if reopening:
            self._adopt_observation(status)
            try:
                self._clock_guard(status)
            except ValueError:
                pass
            else:
                self.phase = 'observed'
                return {'ok': True, 'page': 'cas_review', 'message': 'Retained return reopened; native observation was not repeated.'}
        if self.alarm is not None or not reopening and (self.observe_attempted or status.get('phase') != 'captured'):
            raise ValueError('Observation is already attempted or unavailable. Retained originals/results were not replayed.')
        alarms, clock_module = getattr(self.backend, 'alarms', None), getattr(self.backend, 'clock', None)
        if (alarms is None or not callable(getattr(alarms, 'add_alarm_real_time', None)) or
                not callable(getattr(alarms, 'cancel_alarm', None)) or clock_module is None or
                not callable(getattr(clock_module, 'interval_in_real_seconds', None))):
            raise ValueError('Game-thread clock scheduling is unavailable; no observation submitted.')
        self.phase, self.callback = 'settling-live', callback
        self.probe = {'identity': before['identity'], 'sim': before['sim'], 'initial_ticks': before['ticks'],
            'baseline_ticks': None, 'observe_required': not reopening,
            'started': time.monotonic(), 'normal_attempted': False, 'pause_attempted': False,
            'positive_normal_ticks_verified': False, 'paused_verified': False, 'nonce': self.nonce}
        self.probe.update(epoch=self.epoch, raw_hash=None, plan_hash=None)
        self.alarm = alarms.add_alarm_real_time(self, clock_module.interval_in_real_seconds(.25), self._tick, repeating=True)
        if self.alarm is None:
            self.phase = 'blocked'
            raise ValueError('The game did not acknowledge the Live observation alarm; no observation submitted.')
        return {'ok': True, 'pending': True, 'message': 'The game will run briefly at normal speed, pause, then open every changed form for review.'}

    def _speed(self, live, name):
        from server_commands.clock_commands import set_speed
        flag = 'normal_attempted' if name == 'one' else 'pause_attempted'
        if self.probe[flag]:
            raise ValueError('Clock control already attempted; it must not be replayed.')
        self.probe[flag] = True
        set_speed(name, 'apex.phone.cas-review', _connection=live['client'].id)

    def _finish_alarm(self, result):
        alarm, callback = self.alarm, self.callback
        self.alarm = self.callback = None
        if alarm is not None:
            self.backend.alarms.cancel_alarm(alarm)
        if callback is not None:
            callback(result)

    def _tick(self, _handle=None):
        if self.alarm is None or self.ticking:
            return
        self.ticking = True
        try:
            self._tick_once()
        finally:
            self.ticking = False

    def _tick_once(self):
        try:
            _thread(self.backend)
            live = _live(self.backend, self.sim_id)
            if live['identity'] != self.probe['identity'] or live['sim'] is not self.probe['sim']:
                raise ValueError('Live Sim/household/save/client/zone changed while settling; no CAS observation submitted.')
            self._bind(self._status())
            if time.monotonic() - self.probe['started'] > 10:
                raise ValueError('Normal Live ticks were not verified within ten seconds; observation remains retained.')
            if not self.probe['normal_attempted']:
                self.probe['baseline_ticks'] = live['ticks']
                self._speed(live, 'one')
                return
            if live['speed'] != 1:
                raise ValueError('Normal Live clock speed did not read back; no observation submitted.')
            if live['ticks'] - self.probe['baseline_ticks'] < 30:
                return
            self.probe['positive_normal_ticks_verified'] = True
            self._speed(live, 'paused')
            paused = _live(self.backend, self.sim_id)
            if (paused['identity'] != self.probe['identity'] or paused['sim'] is not self.probe['sim'] or
                    paused['speed'] != 0):
                raise ValueError('Paused Live authority was not verified; no observation submitted.')
            self.probe['paused_verified'] = True
            if self.probe['observe_required']:
                self.observe_attempted, self.phase = True, 'observing'
                argument = {'expected_pending_sha256': self.epoch}
                self.receipts.append({'operation': 'observe', 'nonce': self.nonce, 'argument': argument, 'state': 'attempted'})
                result = _call(self.backend, self.sim_id, 'cas_bank_observe', argument)
                self.receipts[-1].update(state='acknowledged', receipt=result)
                self._adopt_observation(dict(result, raw_return_sha256=result.get('raw_return_sha256'), current_runtime=True))
            else:
                self._adopt_observation(self._status())  # Existing raw WAL is read, never observed again.
            final_live = _live(self.backend, self.sim_id)
            if (final_live['identity'] != self.probe['identity'] or final_live['sim'] is not self.probe['sim'] or
                    final_live['speed'] != 0):
                raise ValueError('Live identity or Pause changed during returned-owner observation; review remains retained.')
            self.probe.update(raw_hash=self.raw_hash, plan_hash=self.plan_hash)
            self.phase = 'observed'
            self._finish_alarm({'ok': True, 'page': 'cas_review'})
        except Exception as error:
            self.phase, self.error = 'blocked', str(error)
            # A different context never receives cleanup commands. A single
            # explicit pause is allowed only for our unchanged running context.
            try:
                if self.probe and self.probe['normal_attempted'] and not self.probe['pause_attempted']:
                    live = _live(self.backend, self.sim_id)
                    if live['identity'] == self.probe['identity'] and live['sim'] is self.probe['sim']:
                        self._speed(live, 'paused')
            except Exception as pause_error:
                self.error += ' Pause remains unverified: ' + str(pause_error)
            self._finish_alarm({'ok': False, 'message': self.error + ' Originals and returned journals remain retained; no submission was replayed.'})

    def choose(self, nonce, lane, decision):
        if nonce != self.nonce or not isinstance(decision, str) or decision not in _DECISIONS or self.phase != 'observed':
            raise ValueError('Phone decision is stale or the return is unresolved; reopen review.')
        status = self.refresh()
        if status.get('phase') != 'observed' or lane not in {row['lane'] for row in self.evidence}:
            raise ValueError('Only an exact changed form in this observed return can receive a decision.')
        self.decisions[lane] = decision
        return {'ok': True, 'page': 'cas_review'}

    def prepare(self, nonce):
        if nonce != self.nonce or self.phase != 'observed' or self.prepare_attempted:
            raise ValueError('Plan is stale, already attempted or unresolved; it was not replayed.')
        self._adopt_observation(self.refresh())
        changed = {row['lane'] for row in self.evidence}
        if set(self.decisions) != changed:
            raise ValueError('Choose Keep returned edit or Restore original separately for EVERY changed form.')
        self._clock_guard(self._status())
        argument = {'expected_pending_sha256': self.epoch, 'expected_raw_return_sha256': self.raw_hash,
            'dispositions': [{'lane': lane, 'action': self.decisions[lane]} for lane in sorted(changed, key=int)]}
        self.prepare_attempted, self.phase = True, 'preparing'
        self.receipts.append({'operation': 'prepare', 'nonce': self.nonce, 'argument': argument, 'state': 'attempted'})
        try:
            result = _call(self.backend, self.sim_id, 'cas_bank_prepare', argument)
            if not _hash(result.get('plan_sha256')):
                raise ValueError('Receiver plan hash was not acknowledged.')
            self.receipts[-1].update(state='acknowledged', receipt=result)
            self.plan_hash, self.phase = result['plan_sha256'], 'planned'
            self.probe['plan_hash'] = self.plan_hash
            return {'ok': True, 'page': 'cas_review'}
        except Exception as error:
            self.phase, self.error = 'blocked', str(error)
            raise

    def commit(self, nonce):
        if nonce != self.nonce or self.phase != 'planned' or self.commit_attempted or not _hash(self.plan_hash):
            raise ValueError('Apply is stale, already attempted or unresolved; native writes were not replayed.')
        status = self.refresh()
        if status.get('phase') != 'planned' or status.get('plan_sha256') != self.plan_hash:
            raise ValueError('Receiver plan changed after phone review; no native write submitted.')
        self._clock_guard(status)
        argument = {'expected_pending_sha256': self.epoch, 'expected_plan_sha256': self.plan_hash}
        self.commit_attempted, self.phase = True, 'committing'
        self.receipts.append({'operation': 'commit', 'nonce': self.nonce, 'argument': argument, 'state': 'attempted'})
        try:
            result = _call(self.backend, self.sim_id, 'cas_bank_commit', argument)
            if (result.get('bank_committed') is not True or result.get('plan_sha256') != self.plan_hash or
                    result.get('all_native_owners_verified') is not True or result.get('save_reload_verified') is not False):
                raise ValueError('Exact native form-bank completion was not acknowledged.')
            self.receipts[-1].update(state='acknowledged', receipt=result)
            self.phase = 'completed'
            return {'ok': True, 'message': 'Reviewed form decisions were applied and verified by the receiver. Disk save and reload verification remain separate.'}
        except Exception as error:
            self.phase, self.error = 'blocked', str(error)
            raise


def session(backend, sim_id):
    _thread(backend)
    key = (id(backend), sim_id)
    current = _SESSIONS.get(key)
    if current is None:
        if len(_SESSIONS) >= _MAX_SESSIONS:
            raise ValueError('Phone review capacity reached; retained sessions were not discarded.')
        current = _SESSIONS[key] = PhoneCasSession(backend, sim_id)
    return current


def _ui_argument(argument, required, optional=()):
    if (not isinstance(argument, dict) or not set(argument).issubset(set(required) | set(optional)) or
            not set(required).issubset(argument)):
        raise ValueError('CAS review accepts only its exact typed intent fields.')
    return argument


def _ui_receipt(current, operation):
    last = current.receipts[-1] if current.receipts else {}
    if (last.get('operation') != operation or last.get('nonce') != current.nonce or
            last.get('state') != 'acknowledged' or not isinstance(last.get('receipt'), dict)):
        raise ValueError('Exact receiver acknowledgement is unavailable; no submission was replayed.')
    current._clock_guard(current._status())
    result = dict(last['receipt'])
    result.update(clock_proof_validated=True, review_nonce=current.nonce, review_state=current.phase)
    return result


def ui_dispatch(backend, sim_id, action, argument=None):
    """Canonical F11 adapters share the phone-owned clock proof, never raw bytes."""
    _thread(backend)
    sim = backend._get_sim_info_by_id(sim_id) if isinstance(sim_id, str) else None
    if sim is None or _id(sim.id) != sim_id:
        raise ValueError('CAS review requires the exact manager-owned Sim identity.')
    current = session(backend, sim_id)
    if action == 'cas_bank_ui_status':
        if argument is not None:
            raise ValueError('CAS review status accepts no argument.')
        status = current._status()  # Raw receiver status; never recursive UI dispatch.
        result = dict(status, clock_proof_validated=False, review_nonce=current.nonce, review_state=current.phase)
        try:
            current._clock_guard(status)
        except (ValueError, TypeError, AttributeError) as error:
            result['clock_proof_error'] = str(error)
        else:
            result['clock_proof_validated'] = True
        if current.error:
            result['review_error'] = current.error
        return result
    if action == 'cas_bank_ui_review':
        _ui_argument(argument, {'expected_pending_sha256'})
        status = current._status()
        if (not _hash(argument['expected_pending_sha256']) or
                status.get('expected_pending_sha256') != argument['expected_pending_sha256']):
            raise ValueError('CAS review must name the exact current retained transaction.')
        current._reopen(status)
        if current.alarm is not None:
            return {'ok': True, 'pending': True, 'expected_pending_sha256': current.epoch,
                'review_nonce': current.nonce, 'review_state': current.phase, 'clock_proof_validated': False}
        outcome = current.start_observe()
        pending = outcome.get('pending') is True
        return dict(outcome, pending=pending, expected_pending_sha256=current.epoch,
            review_nonce=current.nonce, review_state=current.phase, clock_proof_validated=not pending)
    if action == 'cas_bank_ui_prepare':
        _ui_argument(argument, {'expected_pending_sha256', 'expected_raw_return_sha256', 'dispositions',
                                'review_nonce'}, {'hair_targets'})
        if 'hair_targets' in argument:
            raise ValueError('Explicit per-outfit hair targets are not supported by the phone/F11 review adapter yet.')
        status = current.refresh()
        if (argument['review_nonce'] != current.nonce or argument['expected_pending_sha256'] != current.epoch or
                argument['expected_raw_return_sha256'] != current.raw_hash or current.phase != 'observed'):
            raise ValueError('CAS choices belong to a stale review nonce or returned-owner hash.')
        current._clock_guard(status)
        dispositions = argument['dispositions']
        if not isinstance(dispositions, list) or len(dispositions) > 64:
            raise ValueError('Every changed form needs one explicit bounded decision.')
        choices = {}
        for row in dispositions:
            if (not isinstance(row, dict) or set(row) != {'lane', 'action'} or not _lane(row.get('lane')) or
                    row['lane'] in choices or not isinstance(row.get('action'), str) or row['action'] not in _DECISIONS):
                raise ValueError('CAS choices must name each changed native form exactly once.')
            choices[row['lane']] = row['action']
        if set(choices) != {row['lane'] for row in current.evidence}:
            raise ValueError('Choose Keep returned edit or Restore original separately for EVERY changed form.')
        current.decisions = choices
        current.prepare(current.nonce)
        return _ui_receipt(current, 'prepare')
    if action == 'cas_bank_ui_commit':
        _ui_argument(argument, {'expected_pending_sha256', 'expected_plan_sha256', 'review_nonce'})
        if (argument['review_nonce'] != current.nonce or argument['expected_pending_sha256'] != current.epoch or
                argument['expected_plan_sha256'] != current.plan_hash):
            raise ValueError('CAS Apply belongs to a stale review nonce or exact plan hash.')
        current.commit(current.nonce)
        return _ui_receipt(current, 'commit')
    raise ValueError('Unknown typed CAS review adapter.')


def rows(backend, sim_id, page):
    current = session(backend, sim_id)
    try:
        status = current.refresh(reopen=True)
    except Exception as error:
        return [('cas:info', 'Review unavailable: ' + str(error), 'MENU_UNKNOWN')]
    if page.startswith('cas_form:'):
        lane = page.split(':', 1)[1]
        record = next((row for row in current.evidence if row['lane'] == lane), None)
        if record is None:
            return [('page:cas_review', 'Return to current form review', 'MENU_BACK')]
        choices = [('cas:info', _name(lane) + ': every changed field is listed below', 'MENU_UNKNOWN')]
        choices += [('cas:info', field.strip('_').replace('_', ' ') + ' [' + field + ']', 'MENU_UNKNOWN') for field in record['fields']]
        if current.phase == 'observed':
            choices += [('cas:decision:{}:{}:{}'.format(current.nonce, lane, decision), label, 'MENU_PLACEHOLDER')
                        for decision, label in _DECISIONS.items()]
        choices.append(('page:cas_review', 'Back to every changed form', 'MENU_BACK'))
        return choices
    choices = [('cas:info', 'Return state: ' + str(status.get('phase', 'unknown')), 'MENU_UNKNOWN')]
    if current.phase == 'observed':
        if status.get('hair_policy_enabled') is True:
            choices.append(('cas:info', 'Separate hair is enabled. Keeping hair edits needs explicit outfit targets; the phone target picker is unfinished.', 'MENU_UNKNOWN'))
        for row in current.evidence:
            decision = _DECISIONS.get(current.decisions.get(row['lane']), 'REQUIRED: choose separately')
            choices.append(('page:cas_form:' + row['lane'], '{}: {} ({} changed fields)'.format(
                _name(row['lane']), decision, len(row['fields'])), 'MENU_PLACEHOLDER'))
        if not current.evidence:
            choices.append(('cas:info', 'No changed native forms were observed; no edits were inferred.', 'MENU_UNKNOWN'))
        choices.append(('cas:prepare:' + current.nonce, 'Prepare reviewed decisions; no appearance write yet', 'MENU_PLACEHOLDER'))
    elif current.phase == 'planned':
        for row in current.evidence:
            choices.append(('page:cas_form:' + row['lane'], _name(row['lane']) + ': ' + _DECISIONS[current.decisions[row['lane']]], 'MENU_UNKNOWN'))
        choices.append(('cas:commit:' + current.nonce, 'Apply this exact reviewed plan once', 'SETTINGS_ENABLED'))
    elif current.phase == 'completed':
        choices.append(('cas:info', 'Receiver completed; disk save/reload remains separate.', 'MENU_UNKNOWN'))
    else:
        choices.append(('cas:info', current.error or 'Return to Live and choose After CAS. Retained or unresolved work is never replayed.', 'MENU_UNKNOWN'))
    return choices


def select(backend, sim_id, tag, callback=None):
    current = session(backend, sim_id)
    if tag == 'cas:begin':
        return current.begin()
    if tag == 'cas:observe':
        current._reopen(current._status())
        return current.start_observe(callback)
    if tag == 'cas:info':
        return {'ok': True, 'page': 'cas_review'}
    parts = tag.split(':')
    if len(parts) == 5 and parts[:2] == ['cas', 'decision']:
        return current.choose(parts[2], parts[3], parts[4])
    if len(parts) == 3 and parts[:2] == ['cas', 'prepare']:
        return current.prepare(parts[2])
    if len(parts) == 3 and parts[:2] == ['cas', 'commit']:
        return current.commit(parts[2])
    raise ValueError('Unknown or stale typed phone CAS choice.')
