"""Normal player CAS entry arms itself, without research CLI authority."""
import copy
from enum import IntFlag
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace as Obj
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import native_cas_engine as engine, cas_bank_transaction, overlay_loader, sim_data


class ReachedAppearanceImport(Exception):
    pass


class EntryScopeTests(unittest.TestCase):
    def setUp(self):
        class Kind(IntFlag):
            HUMAN = 1
            ALIEN = 2
            VAMPIRE = 4
        self.sims = [Obj(id=22, household_id=99, mask=7, current=2),
                     Obj(id=11, household_id=99, mask=7, current=4)]
        for sim in self.sims:
            sim.occult_tracker = Obj(forms={kind: Obj() for kind in Kind})
        self.household = Obj(id=99, sim_info_gen=lambda: iter(self.sims))
        self.backend = Obj(__file__='matching-installed-script',
            _form_map=lambda tracker: tracker.forms,
            _get_occult_flags=lambda sim: sim.mask, _get_current_flags=lambda sim: sim.current,
            services=Obj(active_household=lambda: self.household,
                get_persistence_service=lambda: Obj(get_save_slot_proto_guid=lambda: 77)))
        self.checkpoints = patch.object(cas_bank_transaction, 'status',
            side_effect=lambda backend, sim: dict(phase='captured', expected_pending_sha256=str(sim.id % 10)*64))
        self.checkpoints.start(); self.addCleanup(self.checkpoints.stop)
        self.layout = patch.object(engine, '_LAYOUT_SCOPE', None)
        self.layout.start(); self.addCleanup(self.layout.stop)
        self.fresh = dict(ok=True, armed=False, selection_enabled=False, scope_retired=False, entry_scope_protocol=1,
                          scope_id='', members=[])
        self.rows = [dict(sim_id='11', owned_mask=7), dict(sim_id='22', owned_mask=7)]

    def acknowledge(self, request):
        engine.argument(request)
        return dict(ok=True, armed=True, selection_enabled=False, scope_retired=False, entry_scope_protocol=1,
            scope_id=request['scope_id'], members=[dict(row, imported_mask=0) for row in request['members']])

    def test_unarmed_normal_entry_creates_exact_scope_and_current_checkpoints(self):
        call = Mock(side_effect=self.acknowledge)
        result, checkpoints = engine._entry_scope(self.backend, call, self.fresh, self.household)
        request = call.call_args.args[0]
        self.assertEqual(request['operation'], 'arm')
        self.assertEqual(request['members'], self.rows)
        self.assertEqual(len(request['scope_id']), 32)
        self.assertEqual(result['scope_id'], request['scope_id'])
        self.assertEqual(checkpoints, {'11': '1'*64, '22': '2'*64})
        call.assert_called_once()

    def test_all_checkpoints_precede_arm_and_no_test_token_is_used(self):
        def arm(request):
            self.assertEqual(cas_bank_transaction.status.call_count, 2)
            self.assertEqual(set(request), {'operation', 'scope_id', 'members'})
            return self.acknowledge(request)
        engine._entry_scope(self.backend, arm, self.fresh, self.household)

    def test_any_missing_checkpoint_or_stale_membership_refuses_before_arm(self):
        call = Mock()
        for change in ('checkpoint', 'membership', 'owner', 'current', 'duplicate'):
            with self.subTest(change=change):
                sims = copy.deepcopy(self.sims)
                household = Obj(id=99, sim_info_gen=lambda: iter(sims))
                if change == 'checkpoint':
                    failure = patch.object(cas_bank_transaction, 'status', side_effect=lambda backend, sim:
                        dict(phase='captured' if sim.id == 22 else 'observed', expected_pending_sha256='a'*64))
                else:
                    failure = patch.object(cas_bank_transaction, 'status', return_value=dict(phase='captured', expected_pending_sha256='a'*64))
                if change == 'membership': sims[-1].mask = 3
                if change == 'owner': del sims[-1].occult_tracker.forms[1]
                if change == 'current': sims[-1].current = 32
                if change == 'duplicate': sims[-1].id = sims[0].id
                with failure, self.assertRaises(ValueError):
                    engine._entry_scope(self.backend, call, self.fresh, household)
        call.assert_not_called()

    def test_existing_exact_empty_development_scope_is_reused_without_rearming(self):
        request = dict(operation='arm', scope_id='a'*32, members=self.rows)
        status = self.acknowledge(request); call = Mock()
        result, _ = engine._entry_scope(self.backend, call, status, self.household)
        self.assertEqual(result, status); call.assert_not_called()

    def test_active_partial_or_foreign_scope_cannot_be_replaced(self):
        status = self.acknowledge(dict(operation='arm', scope_id='a'*32, members=self.rows))
        for mutate in (lambda s: s.update(selection_enabled=True),
                       lambda s: s['members'][0].update(imported_mask=7),
                       lambda s: s['members'].pop(),
                       lambda s: s['members'][0].update(sim_id='33'),
                       lambda s: s.update(scope_retired=1)):
            changed = copy.deepcopy(status); mutate(changed); call = Mock()
            with self.assertRaises(ValueError): engine._entry_scope(self.backend, call, changed, self.household)
            call.assert_not_called()

    def test_retired_previous_household_receives_a_new_identity(self):
        old = self.acknowledge(dict(operation='arm', scope_id='a'*32,
                                    members=[dict(sim_id='999', owned_mask=5)]))
        old['scope_retired'] = True; call = Mock(side_effect=self.acknowledge)
        result, _ = engine._entry_scope(self.backend, call, old, self.household)
        self.assertNotEqual(result['scope_id'], old['scope_id'])
        self.assertEqual(call.call_args.args[0]['members'], self.rows)

    def test_arm_failure_or_wrong_acknowledgement_is_not_replayed(self):
        for change in (dict(ok=False), dict(scope_id='b'*32), dict(selection_enabled=True), dict(scope_retired=True)):
            call = Mock(side_effect=lambda request: dict(self.acknowledge(request), **change))
            with self.subTest(change=change), self.assertRaises(ValueError):
                engine._entry_scope(self.backend, call, self.fresh, self.household)
            call.assert_called_once()

    def test_older_native_build_refuses_before_arm(self):
        for value in (None, True, 0, 2, '1'):
            call = Mock(); old = dict(self.fresh, entry_scope_protocol=value)
            with self.subTest(protocol=value), self.assertRaises(ValueError):
                engine._entry_scope(self.backend, call, old, self.household)
            call.assert_not_called()

    def test_normal_seed_path_starts_installed_sidecar_and_arms_before_import(self):
        operations = []
        def start(module, dll):
            self.assertEqual((module, dll), ('matching-installed-script', 'fixture-dll'))
            overlay_loader._CALLS = {'loaded': True}
            return dict(ok=True)
        def native(module, dll, request):
            operations.append(request['operation'])
            return self.fresh if request['operation'] == 'status' else self.acknowledge(request)
        with patch.object(overlay_loader, '_CALLS', None), \
                patch.object(overlay_loader, 'auto_start_enabled', return_value=True), \
                patch.object(overlay_loader, 'start', side_effect=start) as startup, \
                patch.object(overlay_loader, 'native_cas_engine_control', side_effect=native), \
                patch.dict(sys.modules, {'paths': Obj(DLL_PATH='fixture-dll')}), \
                patch.object(sim_data, 'snapshot', side_effect=ReachedAppearanceImport), \
                patch('apex_core.form_appearance.packed', return_value={
                    'skin_tone': dict(kind='value', value=1),
                    '__outfits__': dict(kind='protobuf', value='oAYB')}):
            with self.assertRaises(ReachedAppearanceImport): engine.seed_members(self.backend)
        startup.assert_called_once()
        self.assertEqual(operations, ['status', 'arm'])

    def test_explicit_autostart_preference_and_script_only_installation_are_respected(self):
        with patch.object(overlay_loader, '_CALLS', None), \
                patch.object(overlay_loader, 'start') as startup, \
                patch.object(sim_data, 'snapshot') as snapshot:
            for behavior in (False, FileNotFoundError('No optional sidecar')):
                with patch.object(overlay_loader, 'auto_start_enabled',
                    **({'side_effect': behavior} if isinstance(behavior, Exception) else {'return_value': behavior})):
                    self.assertEqual(engine.seed_members(self.backend), {'enabled': False})
            startup.assert_not_called(); snapshot.assert_not_called()

    def test_real_script_only_layout_preserves_optional_native_behavior(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / 'Mods' / 'Apex' / 'ApexOccultHybrid.ts4script'
            archive.parent.mkdir(parents=True); archive.write_bytes(b'fixture archive')
            backend = Obj(__file__=str(archive)+'/td1_occult_hybrid_apex.pyc')
            with patch.object(overlay_loader, '_CALLS', None), patch.object(overlay_loader, 'start') as start:
                self.assertEqual(engine.seed_members(backend), {'enabled': False})
                start.assert_not_called()
            # A partial/corrupt native installation is not silently disabled.
            (archive.parent/'Native').mkdir()
            (archive.parent/'Native'/'ApexOverlay.dll').write_bytes(b'MZ'+b'x'*4096)
            with patch.object(overlay_loader, '_CALLS', None), self.assertRaises(ValueError):
                engine.seed_members(backend)


if __name__ == '__main__':
    unittest.main()
