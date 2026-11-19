"""Execute the periodic Live display path with forbidden audit/I/O sentinels."""
from enum import IntEnum
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace as Object
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Source'))
from apex_core import overlay_display_status as display
import td1_occult_hybrid_apex as backend


class Kind(IntEnum):
    HUMAN = 1
    ALIEN = 2
    VAMPIRE = 4
    MERMAID = 8
    WITCH = 16
    WEREWOLF = 32
    FAIRY = 64


class Owner:
    def __getattr__(self, name):
        raise AssertionError('Native appearance access is forbidden: ' + name)


def forbidden(*args, **kwargs):
    raise AssertionError('Periodic display must not perform a full scan, load or mutation')


class Manager:
    def __init__(self, sims):
        self.sims = {sim.id: sim for sim in sims}
        self.reads = []

    def get(self, sid):
        self.reads.append(sid)
        return self.sims.get(sid)

    get_all = forbidden


class Fixture:
    def __init__(self, count=5):
        self.members = []
        for index in range(count):
            sid = 2**64 - 1 - index
            forms = {kind: Owner() for kind in Kind}
            sim = Object(id=sid, sim_id=sid, household_id=77, full_name='Arbitrary member ' + str(index),
                         occult_types=127, current_occult_types=2 if index % 2 else 4,
                         occult_tracker=Object(_sim_info_map=forms, _occult_form_available=True,
                                               membership={kind for kind in Kind if kind is not Kind.HUMAN}))
            sim.occult_tracker.has_occult_type = lambda kind, tracker=sim.occult_tracker: kind in tracker.membership
            self.members.append(sim)
        self.household = Object(sim_info_gen=lambda: iter(self.members))
        for sim in self.members:
            sim.household = self.household
        self.manager = Manager(self.members)
        self.active = self.members[0]
        self.save_guid = 456
        self.persistence = Object(get_save_slot_proto_guid=lambda: self.save_guid)
        self.backend = Object(
            services=Object(sim_info_manager=lambda: self.manager,
                            get_persistence_service=lambda: self.persistence),
            _APEX_GAME_THREAD_IDENT=threading.current_thread().ident,
            _get_active_sim_info=lambda: self.active,
            _get_sim_info_by_id=forbidden, _get_occult_flags=lambda sim: sim.occult_types,
            _get_current_flags=lambda sim: sim.current_occult_types,
            _sim_label=lambda sim: sim.full_name + ' (' + str(sim.id) + ')',
            _form_map=lambda tracker: tracker._sim_info_map,
            # Actual OCCULT_DATA contains six non-Human enums even when the
            # helper is called with include_human=True. The native form map
            # independently contains its single shared Human appearance.
            _all_occults=lambda include_human=False: list(Kind)[1:],
            _has_occult=backend._has_occult,
            _safe_name=lambda kind: kind.name, _LOCK=threading.RLock(),
            _HISTORY=['line ' + str(n) for n in range(300)], _BUILD_VERSION='fixture-current',
            _ALARM_READY=True, _SERVER_RUNNING=True, _AUTO_REPAIR=False, _NATIVE_STATUS='available',
            _APEX7_WARNINGS={}, _status=forbidden, _health_report=forbidden,
            _list_saved_forms=forbidden, _load_saved_forms=forbidden, _load_wardrobes=forbidden,
            _overlay_capabilities=forbidden, _apex7_warning_rows=forbidden,
            _apex7_baseline_rows=forbidden, _apex7_scan_drift=forbidden,
            _v9_table_audit=forbidden, _data_directory=forbidden, _detect_mccc=forbidden,
            _detect_lot51_core=forbidden, _load_native=forbidden)


class DisplayMetadataTests(unittest.TestCase):
    def test_five_arbitrary_hybrids_return_complete_current_metadata_without_appearance_or_audit_work(self):
        fixture = Fixture()
        with patch('builtins.open', side_effect=forbidden), patch.object(Path, 'read_bytes', forbidden), \
                patch.object(Path, 'read_text', forbidden):
            result = display.dispatch(fixture.backend)
        self.assertTrue(result['ok'])
        self.assertEqual(result['status']['sim_id'], str(2**64 - 1))
        self.assertEqual(result['status']['save_guid'], '456')
        self.assertEqual(result['status']['household_id'], '77')
        self.assertEqual(len(result['household']['members']), 5)
        self.assertTrue(result['household']['complete'])
        self.assertEqual(len(result['status']['form_membership']), 6)
        self.assertEqual(len(result['status']['form_map_keys']), 7)
        self.assertTrue(result['status']['human_form_data_present'])
        self.assertEqual(result['status']['logical_occult_membership_mask'], 126)
        self.assertEqual(len(result['status']['occults']), 6)
        self.assertTrue(all(row['has_occult'] and row['has_form_data'] for row in result['status']['occults']))
        self.assertIsNone(result['status']['health'])
        self.assertFalse(result['status']['drift_scan_performed'])
        self.assertFalse(result['mutation_authority'])
        self.assertFalse(result['appearance_read'])
        self.assertFalse(result['appearance_written'])
        self.assertFalse(result['library_scan_performed'])
        self.assertEqual(len(result['logs']), 220)
        # Only copied JSON values cross to the native/HTTP worker, never owners.
        self.assertEqual(json.loads(json.dumps(result)), result)

    def test_new_selection_save_and_form_metadata_are_fresh_without_cached_sim_looks(self):
        f = Fixture()
        first = display.dispatch(f.backend)
        f.active = f.members[1]
        f.save_guid = 789
        f.active.current_occult_types = 64
        f.active.occult_types = 65
        f.active.occult_tracker.membership = {Kind.FAIRY}
        second = display.dispatch(f.backend)
        self.assertNotEqual(first['status']['sim_id'], second['status']['sim_id'])
        self.assertEqual(second['status']['save_guid'], '789')
        self.assertEqual(second['status']['current_occult_types_value'], 64)
        vampire = next(row for row in second['status']['occults'] if row['name'] == 'VAMPIRE')
        self.assertFalse(vampire['has_occult'])
        self.assertEqual(first['status']['current_occult_types_value'], 4)

    def test_tracker_hybrid_membership_is_independent_of_raw_render_channel_flags(self):
        f = Fixture()
        f.active.occult_types = 65
        f.active.current_occult_types = 2
        result = display.dispatch(f.backend)
        status = result['status']
        self.assertEqual(status['occult_types_value'], 65)
        self.assertEqual(status['current_occult_types_value'], 2)
        self.assertEqual(status['logical_occult_membership_mask'], 126)
        self.assertEqual(status['membership_observation'], 'native-occult-tracker-query')
        self.assertTrue(all(row['has_occult'] for row in status['occults']))
        self.assertEqual({row['name'] for row in status['occults']},
                         {'ALIEN', 'VAMPIRE', 'MERMAID', 'WITCH', 'WEREWOLF', 'FAIRY'})
        self.assertEqual(len(status['form_map_keys']), 7)
        self.assertTrue(status['human_form_data_present'])
        self.assertFalse(status['mutation_authority'])
        # Conversely, raw bits never claim a tracker membership which was
        # actually removed; existing form-data presence is a separate fact.
        f.active.occult_types = 127
        f.active.occult_tracker.membership.remove(Kind.VAMPIRE)
        next_status = display.dispatch(f.backend)['status']
        vampire = next(row for row in next_status['occults'] if row['name'] == 'VAMPIRE')
        self.assertFalse(vampire['has_occult'])
        self.assertTrue(vampire['has_form_data'])
        self.assertEqual(next_status['occult_types_value'], 127)
        self.assertEqual(next_status['logical_occult_membership_mask'], 122)

    def test_explicit_missing_selection_never_substitutes_active_sim_or_scans_world(self):
        f = Fixture()
        for selected in ('123', '0', '-1', str(2**64), 'abc', ' 123', True, '1' * 1000, '\u0661\u0662\u0663'):
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                display.dispatch(f.backend, selected)
        result = display.dispatch(f.backend, hex(f.members[2].id))
        self.assertEqual(result['status']['sim_id'], str(f.members[2].id))

    def test_worker_thread_rejected_before_any_game_or_profile_access(self):
        f = Fixture()
        errors = []
        def run():
            try:
                display.dispatch(f.backend)
            except Exception as error:
                errors.append(error)
        worker = threading.Thread(target=run)
        worker.start()
        worker.join()
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], ValueError)
        self.assertEqual(f.manager.reads, [])

    def test_foreign_duplicate_incomplete_or_replaced_household_members_are_not_partially_published(self):
        for change in ('foreign', 'duplicate', 'unavailable', 'replaced'):
            f = Fixture()
            if change == 'foreign':
                f.members[1].household_id = 999
            elif change == 'duplicate':
                f.members.append(f.members[0])
            elif change == 'unavailable':
                f.members.append(None)
            else:
                original = f.backend._sim_label
                def replacement(sim):
                    value = original(sim)
                    f.manager.sims[f.active.id] = Object(id=f.active.id)
                    return value
                f.backend._sim_label = replacement
            with self.subTest(change=change), self.assertRaises(ValueError):
                display.dispatch(f.backend)

    def test_unavailable_household_does_not_report_one_member_as_complete(self):
        f = Fixture()
        f.active.household = None
        with self.assertRaises(ValueError):
            display.dispatch(f.backend)
        f.active.household_id = 0
        result = display.dispatch(f.backend)
        self.assertEqual(result['status']['household_id'], '0')
        self.assertTrue(result['household']['complete'])
        self.assertEqual(result['sims'], [])

    def test_in_memory_warnings_are_named_as_old_notifications_not_a_clean_drift_scan(self):
        f = Fixture()
        selected = str(f.active.id)
        f.backend._APEX7_WARNINGS = {selected + ':ALIEN:appearance_drift': {'payload': Owner()},
                                    selected + ':FAIRY:missing_form': {'payload': Owner()},
                                    'other:VAMPIRE:appearance_drift': {'payload': Owner()}}
        result = display.dispatch(f.backend)
        self.assertEqual(result['status']['drift_warning_count'], 2)
        self.assertEqual(result['status']['drift_observation'], 'cached-notifications-only')
        self.assertFalse(result['status']['drift_scan_performed'])
        self.assertNotIn('payload', json.dumps(result))

    def test_payload_bounds_zero_logs_and_no_active_sim(self):
        f = Fixture()
        for value in ({'count': True}, {'count': -1}, {'count': 261}, {'count': 1.5}, {'count': 2, 'appearance': {}}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                display.dispatch(f.backend, value=value)
        for value in ('{"count":0,"count":1}', '{"count":"' + 'x' * 1024 + '"}'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                display.dispatch(f.backend, value=value)
        f.active = None
        result = display.dispatch(f.backend, value='{"count":0}')
        self.assertTrue(result['ok'])
        self.assertIsNone(result['status']['sim_id'])
        self.assertEqual(result['logs'], [])


class ActualBackendRouteTests(unittest.TestCase):
    def test_http_display_queues_only_dedicated_action_and_legacy_state_path_remains(self):
        f = Fixture()
        with patch.object(backend, '_submit_action', return_value={'ok': True, 'display_metadata_only': True}) as submit, \
                patch.object(backend, '_logs_payload', side_effect=forbidden), \
                patch.object(backend, '_overlay_capabilities', side_effect=forbidden), \
                patch.object(backend, '_status', side_effect=forbidden):
            result = backend._overlay_display_payload({'sim_id': str(f.active.id), 'count': '180'})
        self.assertTrue(result['ok'])
        submit.assert_called_once_with('overlay_display_status', sim_id=str(f.active.id), value='{"count": 180}', wait_seconds=2.5)
        for count in (True, -1, 261, 1.5, 'invalid'):
            with patch.object(backend, '_submit_action', side_effect=forbidden):
                self.assertFalse(backend._overlay_display_payload({'count': count})['ok'])
        text = (ROOT / 'NativeOverlay/Source/TD1ApexD3D11Proxy.cpp').read_text(encoding='utf-8')
        self.assertIn('std::string path = "/api/overlay/display?count=220";', text)
        self.assertNotIn('std::string path = "/api/overlay/state?count=220";', text)
        self.assertIn('g_visible.load() && !g_nativeCasPaneVisible.load()', text)
        self.assertIn('Drift is not scanned by periodic refresh.', text)

    def test_real_owner_dispatch_avoids_layered_status_and_mutation_dispatch_stays_original(self):
        f = Fixture()
        names = ('services', '_APEX_GAME_THREAD_IDENT', '_get_active_sim_info', '_get_occult_flags', '_get_current_flags',
                 '_sim_label', '_form_map', '_all_occults', '_has_occult', '_safe_name', '_LOCK', '_HISTORY', '_BUILD_VERSION',
                 '_ALARM_READY', '_SERVER_RUNNING', '_AUTO_REPAIR', '_NATIVE_STATUS', '_APEX7_WARNINGS')
        with patch.multiple(backend, **{name: getattr(f.backend, name) for name in names}), \
                patch.object(backend, '_APEX_PRE_OWNER_RUN_ACTION', side_effect=forbidden), \
                patch.object(backend, '_status', side_effect=forbidden), \
                patch.object(backend, '_list_saved_forms', side_effect=forbidden), \
                patch.object(backend, '_load_wardrobes', side_effect=forbidden), \
                patch.object(backend, '_overlay_capabilities', side_effect=forbidden), \
                patch.object(backend, '_health_report', side_effect=forbidden):
            result = backend.run_action('overlay_display_status', sim_id=str(f.active.id), value='{"count":0}')
            self.assertTrue(result['ok'])
            self.assertFalse(backend.run_action('overlay_display_status', occult='ALIEN')['ok'])
        with patch.object(backend, 'services', object()), \
                patch.object(backend, '_APEX_GAME_THREAD_IDENT', threading.current_thread().ident), \
                patch.object(backend, '_APEX_PRE_OWNER_RUN_ACTION', return_value={'ok': True, 'message': 'explicit-full-status'}) as original:
            self.assertEqual(backend.run_action('status')['message'], 'explicit-full-status')
            original.assert_called_once_with('status', sim_id=None, occult=None, value=None)


if __name__ == '__main__':
    unittest.main()
