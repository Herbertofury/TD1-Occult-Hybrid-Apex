import copy
from pathlib import Path
import sys
import unittest
import contextlib
import json
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import cas_entry_observe
from cas_entry_observe import entry_identity,observed_member
import test_cas_entry_member as member_fixture


class AcceptedEntryObservationTests(unittest.TestCase):
    def setUp(self):
        self.identity = {'pid': 123, 'test_token': 'a' * 32, 'script_sha256': 'b' * 64}
        self.entry = {'operation': 'observe-native-cas-entry', 'entry_submitted': True,
                      'entry_accepted': True, 'requested_sim_id': '7', 'identity': self.identity,
                      'ok': False, 'error': 'observer timed out', 'crash': {'outcome': 'unchanged'}}

    def test_observer_timeout_does_not_require_replaying_accepted_entry(self):
        original = copy.deepcopy(self.entry)
        entry_identity(self.entry, self.identity, '7')
        self.assertEqual(self.entry, original)

    def test_rejected_or_unsubmitted_entry_is_not_promoted_by_followup(self):
        for key in ('entry_submitted', 'entry_accepted'):
            bad = copy.deepcopy(self.entry); bad[key] = False
            with self.subTest(key=key), self.assertRaises(ValueError): entry_identity(bad, self.identity, '7')

    def test_changed_runtime_identity_blocks_followup(self):
        for key, value in (('pid', 124), ('test_token', 'c' * 32), ('script_sha256', 'd' * 64)):
            changed = dict(self.identity, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError): entry_identity(self.entry, changed, '7')

    def test_changed_sim_crash_and_untyped_document_are_refused(self):
        with self.assertRaises(ValueError): entry_identity(self.entry, self.identity, '8')
        bad = copy.deepcopy(self.entry); bad['crash']['outcome'] = 'changed'
        with self.assertRaises(ValueError): entry_identity(bad, self.identity, '7')
        with self.assertRaises(ValueError): entry_identity([], self.identity, '7')

    def captured_entry(self):
        fixture=member_fixture.EntryMemberTests();fixture.setUp()
        ack=copy.deepcopy(fixture.entry)
        ack.update(ok=True,request_id='e'*32,request_state='completed')
        entry=dict(entry_request_id='e'*32,steps=[dict(action='test_cas_completion',result=ack)])
        return entry,fixture.diagnostic

    def test_initial_full_household_member_is_observed_without_selecting(self):
        entry,diagnostic=self.captured_entry();original=copy.deepcopy(entry)
        self.assertEqual(observed_member(entry,diagnostic,'13'),('12','20'))
        self.assertEqual(entry,original)

    def test_unrelated_stale_or_unacknowledged_member_cannot_qualify_entry(self):
        entry,diagnostic=self.captured_entry()
        for alter in ('other-request','single-editor','missing-checkpoint','stale-peer','duplicate-peer',
                      'untyped-steps','duplicate-ack'):
            bad=copy.deepcopy(entry);peer=copy.deepcopy(diagnostic);ack=bad['steps'][0]['result']
            if alter=='other-request':ack['request_id']='f'*32
            elif alter=='single-editor':ack['requested_editor']='native-full'
            elif alter=='missing-checkpoint':ack['household_form_checkpoints']['members'][0].pop('form_checkpoint')
            elif alter=='stale-peer':peer['native_peers'][0]['age_seconds']=4
            elif alter=='duplicate-peer':
                ack['household_form_checkpoints']['members'].append(copy.deepcopy(ack['household_form_checkpoints']['members'][0]))
            elif alter=='untyped-steps':bad['steps']=None
            elif alter=='duplicate-ack':bad['steps'].append(copy.deepcopy(bad['steps'][0]))
            with self.subTest(alter=alter),self.assertRaises(ValueError):observed_member(bad,peer,'13')

    def test_followup_reads_captured_initial_member_without_navigation_or_entry(self):
        from source_manifest import sha256
        for household in ('20','21'):
            entry,diagnostic=self.captured_entry()
            entry.update(copy.deepcopy(self.entry));entry['requested_sim_id']='13'
            actions=[];inventories=[]
            with self.subTest(household=household),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);path=root/'entry.json';path.write_text(json.dumps(entry),encoding='utf-8')
                def request(state,action,*args,**kwargs):
                    actions.append(action);self.assertEqual(action,'cas_ui_diagnostics')
                    kwargs['submission_observer'](action,'a'*32)
                    return dict(diagnostic,request_id='a'*32,request_state='completed')
                def inventory(args,recorded):
                    inventories.append(args.sim_id)
                    return dict(ok=True,ui_transition_verified=True,client=dict(sim=dict(simId='12',householdId=household)))
                with patch('reusable_profile.load',return_value=(None,None,root/'profile',root/'original')), \
                     patch('reusable_profile.writable',side_effect=lambda p:p), \
                     patch('cli_identity_cache.session',return_value=contextlib.nullcontext()), \
                     patch('cas_client.execute',side_effect=inventory):
                    result=cas_entry_observe.observe(root/'state.json',path,sha256(path),'13',root/'proof.json',request,lambda _:self.identity)
                self.assertEqual(result['ok'],household=='20')
                self.assertEqual(actions,['cas_ui_diagnostics']);self.assertEqual(inventories,['12'])
                proof=json.loads((root/'proof.json').read_text(encoding='utf-8'))
                self.assertFalse(proof['entry_submitted']);self.assertFalse(proof['input_submitted'])
                self.assertFalse(proof['member_selection_submitted'])
                self.assertEqual(proof['observed_sim_id'],'12')

    def test_stale_terminal_heartbeat_can_refresh_but_unresolved_read_cannot_replay(self):
        from source_manifest import sha256
        for initial_state in ('completed','pending'):
            entry,diagnostic=self.captured_entry();entry.update(copy.deepcopy(self.entry));entry['requested_sim_id']='13'
            requests=[];clock=[0]
            with self.subTest(initial_state=initial_state),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);path=root/'entry.json';path.write_text(json.dumps(entry),encoding='utf-8')
                def request(state,action,*args,**kwargs):
                    self.assertEqual(action,'cas_ui_diagnostics');rid=format(len(requests)+1,'032x');requests.append(rid)
                    kwargs['submission_observer'](action,rid)
                    value=copy.deepcopy(diagnostic)
                    if len(requests)==1:value['native_peers'][0]['age_seconds']=4
                    status=initial_state if len(requests)==1 else 'completed'
                    return dict(value,ok=status=='completed',request_id=rid,request_state=status)
                def pause(seconds):clock[0]+=seconds
                with patch('reusable_profile.load',return_value=(None,None,root/'profile',root/'original')), \
                     patch('reusable_profile.writable',side_effect=lambda p:p), \
                     patch('cli_identity_cache.session',return_value=contextlib.nullcontext()), \
                     patch('cas_client.execute',return_value=dict(ok=True,ui_transition_verified=True,
                         client=dict(sim=dict(simId='12',householdId='20')))) as inventory:
                    result=cas_entry_observe.observe(root/'state.json',path,sha256(path),'13',root/'proof.json',request,
                        lambda _:self.identity,monotonic=lambda:clock[0],pause=pause)
                self.assertEqual(result['ok'],initial_state=='completed')
                self.assertEqual(len(requests),2 if initial_state=='completed' else 1)
                self.assertEqual(len(set(requests)),len(requests))
                self.assertEqual(inventory.call_count,1 if initial_state=='completed' else 0)


if __name__ == '__main__': unittest.main()
