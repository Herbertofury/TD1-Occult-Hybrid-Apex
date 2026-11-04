"""Repeatable real-game CLI tests with settled observations and durable evidence."""
import json
from pathlib import Path
import time
from source_manifest import write_json
import reusable_profile


class RuntimeTest:
    def __init__(self, state, sim_id, output, request, pause=time.sleep):
        self.state, self.sim_id, self.request, self.pause = state, sim_id, request, pause
        _, data, profile, original = reusable_profile.load(state)
        self.output = reusable_profile.writable(output)
        if any(self.output == root or root in self.output.parents for root in (profile, original)):
            raise ValueError('Runtime evidence must be outside both game profiles.')
        if self.output.exists():
            raise ValueError('Preserve previous proof; choose a new evidence filename.')
        self.token = data['token']
        self.evidence = {'schema': 1, 'ok': False, 'sim_id': sim_id, 'test_token': self.token,
            'installed_artifacts': data['artifacts'], 'steps': [], 'assertions': [],
            'scope': 'Actual game-thread CLI operations; no headless/CAS-render/full-parity claim.'}

    def record(self):
        write_json(self.output, self.evidence)

    def call(self, action, value=None, occult=None):
        if action.startswith('test_'):
            value = json.dumps({'test_token': self.token, 'value': value})
        result = self.request(self.state, action, self.sim_id, occult=occult, value=value)
        self.evidence['steps'].append({'action': action, 'occult': occult, 'result': result})
        self.record()
        if not result.get('ok') or result.get('outcome') == 'unresolved':
            raise ValueError('Runtime step failed or is unresolved: ' + action + '; inspect its recorded request ID before retrying.')
        return result

    def check(self, label, passed):
        self.evidence['assertions'].append({'assertion': label, 'passed': bool(passed)})
        self.record()
        if not passed:
            raise ValueError('Runtime assertion failed: ' + label)

    def settle(self, seconds):
        if not 1 <= seconds <= 10:
            raise ValueError('Settling interval must be 1–10 seconds.')
        self.call('test_play')
        try:
            self.pause(seconds)
            return self.call('test_snapshot')
        finally:
            self.call('test_pause')

    def color_cycle(self, target, settle_seconds):
        before = self.call('test_snapshot', 'outfits')
        status = self.call('studio_status')
        if status['pending_preview']:
            self.call('studio_recover')
            status = self.call('studio_status')
        initial = status['appearance_sha256']
        self.call('studio_checkpoint', 'CLI before reversible color test')
        inspected = self.call('studio_color_inspect', target)
        editor = inspected['color_editor']
        edited = None
        for name in ('hue', 'saturation', 'brightness', 'opacity'):
            channel = editor['channels'][name]
            if not channel['enabled']:
                continue
            step = max(channel.get('step', 0.05), 1.0 / 16384)
            value = channel['value'] + step
            if value > channel['max']:
                value = channel['value'] - step
            if channel['min'] <= value <= channel['max']:
                edited = {name: value}
                break
        if edited is None:
            raise ValueError('Selected CAS part has no editable color channel.')
        payload = {key: editor[key] for key in ('target', 'cas_part_id', 'color_hex', 'appearance_sha256', 'resource_sha256')}
        payload.update(lane=inspected['history_lane'], edits=edited)
        preview = self.call('studio_color_edit', json.dumps(payload))
        self.check('Preview leaves the actual Sim unchanged', self.call('studio_status')['appearance_sha256'] == initial)
        self.call('studio_cancel', preview['preview_id'])
        self.check('Cancel leaves the actual Sim unchanged', self.call('studio_status')['appearance_sha256'] == initial)
        preview = self.call('studio_color_edit', json.dumps(payload))
        self.call('studio_apply', preview['preview_id'])
        self.settle(settle_seconds)
        after = self.call('studio_status')
        applied = after['appearance_sha256']
        self.check('Applied color survives unpause/settle', applied != initial)
        linked_after = self.call('test_snapshot')['sim']['linked_forms']
        untouched_before = {row['flags']: row['outfit_sha256'] for row in before['sim']['linked_forms'] if row['flags'] != before['sim']['current_form']}
        untouched_after = {row['flags']: row['outfit_sha256'] for row in linked_after if row['flags'] != before['sim']['current_form']}
        self.check('Inactive occult forms retain their exact outfit bytes', untouched_before == untouched_after)
        undo = self.call('studio_undo')
        self.call('studio_apply', undo['preview_id'])
        self.settle(settle_seconds)
        self.check('Undo restores every normalized outfit byte after settling', self.call('studio_status')['appearance_sha256'] == initial)
        redo = self.call('studio_redo', after['history_cursor'])
        self.call('studio_apply', redo['preview_id'])
        self.settle(settle_seconds)
        self.check('Redo restores the exact accepted color state', self.call('studio_status')['appearance_sha256'] == applied)
        undo = self.call('studio_undo')
        self.call('studio_apply', undo['preview_id'])
        self.settle(settle_seconds)
        self.check('Final state restores the pre-test appearance', self.call('studio_status')['appearance_sha256'] == initial)

    def hybrid_cycle(self, occults, settle_seconds):
        initial = self.call('test_snapshot', 'outfits')
        present = {row['occult'] for row in initial['sim']['membership']}
        for kind in occults:
            if kind in present:
                continue
            self.call('add', occult=kind)
            added = self.settle(settle_seconds)
            present = {row['occult'] for row in added['sim']['membership']}
        expected = set(occults)
        for kind in tuple(occults) + ('HUMAN',):
            self.call('human' if kind == 'HUMAN' else 'switch', occult=None if kind == 'HUMAN' else kind)
            state = self.settle(settle_seconds)
            membership = {row['occult'] for row in state['sim']['membership']}
            self.check('Hybrid membership retained in ' + kind, expected <= membership)
            desired = 1 if kind == 'HUMAN' else next(row['flags'] for row in state['sim']['membership'] if row['occult'] == kind)
            self.check('Active form converged to ' + kind, state['sim']['current_form'] == desired)

    def run(self, suite, target='0:HAIR', occults=('VAMPIRE', 'WITCH'), settle_seconds=3):
        self.evidence['suite'] = suite
        self.record()
        try:
            self.call('test_pause')
            if suite == 'color-cycle':
                self.color_cycle(target, settle_seconds)
            elif suite == 'hybrid-cycle':
                self.hybrid_cycle(occults, settle_seconds)
            else:
                raise ValueError('Unknown real-game suite.')
            self.evidence['ok'] = True
        except Exception as error:
            self.evidence['error'] = str(error)
        finally:
            try:
                self.call('test_pause')
            except Exception as error:
                self.evidence['ok'] = False
                self.evidence['pause_error'] = str(error)
            self.record()
        return {'ok': self.evidence['ok'], 'suite': suite, 'steps': len(self.evidence['steps']),
                'assertions': self.evidence['assertions'], 'error': self.evidence.get('error'), 'evidence': str(self.output)}
