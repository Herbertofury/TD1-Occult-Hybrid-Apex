"""Real receiver/atomic-bank fixtures with a synthetic authenticated native return.

No game, profile, UI, DLL or actual save file is used. Native witness mocks are
not qualification of EA acceptance, Gallery/Tray export or import boundaries.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core import cas_auto_settle as auto,cas_bank_transaction as bank,cas_save_boundary as gate
from apex_core import form_bank,form_appearance as appearance,native_cas_engine,cas_ui
import test_cas_bank_transaction as fixture


class AutomaticAcceptedHouseholdTests(unittest.TestCase):
    def setUp(self):
        self.game=fixture.CasBankReceiverTests();self.game.setUp();self.addCleanup(self.game.doCleanups)
        self.backend=self.game.backend;self.sims={'10':self.game.sim};self.forms={'10':self.game.forms}
        self.backend.services.current_zone=lambda:Obj(is_zone_running=True,is_in_build_buy=False)
        self.household=Obj(id=20,sim_info_gen=lambda:list(self.sims.values()))
        self.backend.services.active_household=lambda:self.household
        self.backend._get_sim_info_by_id=lambda sid:self.sims.get(str(sid))
        self.backend._form_map=lambda tracker:next(self.forms[sid] for sid,sim in self.sims.items() if sim.occult_tracker is tracker)
        self.backend._ensure_human_form=lambda tracker:self.backend._form_map(tracker)[1]
        self.backend._ensure_form=lambda tracker,kind,generate_new=False:self.backend._form_map(tracker).get(kind)
        self.writes=[]
        def restore(owner,values):
            record=self.game.data()['records']['30:'+str(owner.id)]
            self.assertEqual(record['cas_transaction']['journal']['state'],'applying')
            self.writes.append((str(owner.id),owner.owner_lane))
            self.game._assign(owner,{name:appearance.encode(value) for name,value in values.items()})
        self.restore=restore;self.backend._restore_siminfo_payload=restore
        self.enterContext(patch.object(gate,'_READ_INDEX',None))
        self.enterContext(patch.object(cas_ui,'diagnostics',return_value={'native_peers':[]}))
        self.enterContext(patch.object(native_cas_engine,'complete_return',return_value={'enabled':True,'retired':False}))

    def begin(self,multiple=False,hair=False,cancel=False,witness=True):
        returned=self.game.named_native_return()
        if hair:self.game.enable_hair()
        if multiple:
            sim=copy.deepcopy(self.game.sim);sim.id=11;sim.occult_tracker=Obj()
            self.sims['11']=sim;self.forms['11']=copy.deepcopy(self.game.forms)
            for owner in self.forms['11'].values():owner.id=11
            data=self.game.data();data['records']['30:11']=copy.deepcopy(data['records']['30:10'])
            form_bank.save(self.game.path,data)
        self.epochs={};self.returned={}
        for sid,sim in self.sims.items():
            checkpoint=bank.begin(self.backend,sim);self.epochs[sid]=checkpoint['expected_pending_sha256']
            graph=copy.deepcopy(returned)
            graph['identity'].update(pid=os.getpid(),sim_id=sid,scope_id='s'*32,generation=7)
            graph['checkpoint_epoch']=self.epochs[sid]
            for row in graph['owners']:
                if row['owner_id']=='native/2':row['fields']['physique']=appearance.encode('accepted Alien '+sid)
                if row['owner_id']=='native/4':row['fields']['physique']=appearance.encode('accepted Vampire '+sid)
            self.returned[sid]=graph
        receipt=dict(schema=1,id='d'*32,stage='native-command-returned',sim_id='10',household_id='20',
            full_household=True,roster_sim_ids=list(self.sims),members=[{'sim_id':sid,'checkpoint':{'ok':True,
                'expected_pending_sha256':epoch}} for sid,epoch in self.epochs.items()])
        self.backend._APEX_CAS_FRONTDOOR_RECEIPT=receipt
        self.frontdoor=self.game.path.parent/('cas_frontdoor_'+receipt['id']+'.json')
        self.frontdoor.write_text(json.dumps(receipt))
        self.scope=dict(pid=os.getpid(),scope_id='s'*32,epochs=self.epochs,
            owners={(sid,row['owner_id']):{} for sid,g in self.returned.items() for row in g['owners']},
            load_identity={'household_id':'20','save_guid':'30'})
        self.proof=dict(verified=True,native_accepted=True,scope_id='s'*32,generations={sid:7 for sid in self.sims})
        if cancel:self.proof.update(verified=False,native_accepted=False,cancelled=True,cancel_started=True,
            cancel_completed=True,native_handled=True,runtime_pid=os.getpid(),session=0,cancel_serial=1,member_ids=list(self.sims))
        self.native=dict(ok=True,pid=os.getpid(),scope_id='s'*32,selection_enabled=True,sessions_retired=0,
            household_acceptance=self.proof,members=[dict(sim_id=sid,graph_generation=7,native_view_fault=False) for sid in self.sims])
        self.enterContext(patch.object(native_cas_engine,'_LAYOUT_SCOPE',self.scope))
        self.enterContext(patch.object(auto,'_native_status',side_effect=lambda _b:copy.deepcopy(self.native)))
        self.enterContext(patch.object(native_cas_engine,'returned_owners',side_effect=lambda _b,s,e:copy.deepcopy(self.returned[str(s.id)])))
        if witness:
            for sid,sim in self.sims.items():
                tracker=sim.occult_tracker;tracker.sim_info=sim
                tracker._apex_native_load_pending=True
                tracker._apex_native_load_appearance_retention={'verified':True}
                self.assertEqual(auto.note_native_ready(self.backend,tracker)['state'],'retained')
                tracker._apex_native_load_pending=False

    def test_all_members_all_forms_and_named_variants_complete_without_manual_review(self):
        self.begin(multiple=True)
        result=auto.settle(self.backend)
        self.assertTrue(result['ok'],result)
        self.assertEqual(result['members'],['10','11'])
        self.assertFalse(result['user_review_required'])
        self.assertFalse(gate.admission(self.backend)['locked'])
        for sid in self.sims:
            record=self.game.data()['records']['30:'+sid]
            self.assertIsNone(record['pending'])
            self.assertTrue(bank._completed(record['cas_transaction']))
            self.assertEqual(record['bank']['2']['physique']['value'],'accepted Alien '+sid)
            self.assertEqual(record['lifestate_forms']['forms']['ghost_ghost']['fields']['physique']['value'],'edited-ghost_ghost')
            self.assertEqual(record['native_cas_owner_archive'],self.returned[sid])
            self.assertEqual(appearance.packed(self.backend,self.forms[sid][2]),record['bank']['2'])
        before=len(self.writes);self.assertEqual(auto.settle(self.backend)['state'],'idle');self.assertEqual(len(self.writes),before)

    def test_native_acceptance_keeps_complete_added_hair_wardrobe(self):
        self.begin(hair=True)
        row=next(r for r in self.returned['10']['owners'] if r['owner_id']=='native/2')
        message=self.game.parse(appearance.decode(row['fields']['__outfits__'])[1])
        added=message.outfits.add();added.CopyFrom(message.outfits[0]);added.outfit_id=9999999
        row['fields']['__outfits__']=appearance.encode(('protobuf',message.SerializeToString()))
        result=auto.settle(self.backend);self.assertTrue(result['ok'],result)
        record=self.game.record()
        self.assertEqual(record['bank']['2'],row['fields'])
        self.assertTrue(any(r['outfit_id']=='9999999' for r in record['hair_policy']['forms']['2']))

    def test_completed_cancel_keeps_live_originals_and_never_accepts_cancelled_edits(self):
        self.begin(cancel=True)
        originals=copy.deepcopy(self.game.record()['pending']['original_owners']['stored'])
        result=auto.settle(self.backend);self.assertTrue(result['ok'],result)
        self.assertEqual(self.game.record()['bank'],originals)
        self.assertEqual(self.game.record()['lifestate_forms']['forms']['ghost_ghost']['fields'],originals['1'])
        self.assertEqual(self.game.record()['native_cas_owner_archive'],self.returned['10'])

    def test_uncertain_cancel_or_later_live_edits_never_authorize_automatic_rollback(self):
        for damage in ('incomplete','refused','pid','session','members','later-edit'):
            with self.subTest(damage=damage):
                self.setUp();self.begin(cancel=True)
                if damage=='incomplete':self.proof['cancel_completed']=False
                elif damage=='refused':self.proof['native_handled']=False
                elif damage=='pid':self.proof['runtime_pid']+=1
                elif damage=='session':self.proof['session']+=1
                elif damage=='members':self.proof['member_ids'].append('99')
                else:self.game.forms[2].physique='later user Live edit'
                before=self.game.path.read_bytes();result=auto.settle(self.backend)
                self.assertFalse(result['ok']);self.assertEqual(self.writes,[]);self.assertEqual(self.game.path.read_bytes(),before)

    def test_foreign_missing_or_uncertain_acceptance_has_no_native_writes(self):
        self.begin(multiple=True);before=self.game.path.read_bytes();self.native['household_acceptance']['generations'].pop('11')
        result=auto.settle(self.backend)
        self.assertFalse(result['ok']);self.assertEqual(self.writes,[]);self.assertEqual(self.game.path.read_bytes(),before)

    def test_later_member_collateral_damage_retains_group_and_blocks_actual_save(self):
        self.begin(multiple=True)
        def collateral(owner,values):
            self.restore(owner,values)
            if owner.id==11:self.game.forms[1].physique='later member damaged first Human'
        self.backend._restore_siminfo_payload=collateral
        result=auto.settle(self.backend)
        self.assertFalse(result['ok']);self.assertTrue(result['unresolved']);self.assertTrue(gate.admission(self.backend)['locked'])
        for sid in self.sims:self.assertIn('automatic_cas_preservation_failure',self.game.data()['records']['30:'+sid])
        before=len(self.writes);self.assertFalse(auto.settle(self.backend)['ok']);self.assertEqual(len(self.writes),before)

    def test_later_live_edits_cannot_be_overwritten_by_an_older_accepted_graph(self):
        self.begin();before=self.game.path.read_bytes()
        self.forms['10'][2].physique='newer intentional Live edit'
        result=auto.settle(self.backend)
        self.assertFalse(result['ok']);self.assertEqual(self.writes,[])
        self.assertEqual(self.forms['10'][2].physique,'newer intentional Live edit')
        self.assertEqual(self.game.path.read_bytes(),before)

    def test_repeated_ready_cannot_replace_first_physical_return_with_later_edits(self):
        self.begin();tracker=self.game.sim.occult_tracker
        self.forms['10'][2].physique='newer intentional Live edit'
        tracker._apex_native_load_pending=True
        self.assertEqual(auto.note_native_ready(self.backend,tracker)['state'],'already-retained')
        tracker._apex_native_load_pending=False
        self.assertFalse(auto.settle(self.backend)['ok']);self.assertEqual(self.writes,[])

    def test_missing_return_witness_requires_exact_physical_native_projection(self):
        self.begin(witness=False);before=self.game.path.read_bytes()
        result=auto.settle(self.backend);self.assertFalse(result['ok'])
        self.assertEqual(self.writes,[]);self.assertEqual(self.game.path.read_bytes(),before)
        for row in self.returned['10']['owners']:
            if row['owner_id'].startswith('native/'):
                lane=int(row['owner_id'].split('/')[1]);self.game._assign(self.forms['10'][lane],row['fields'])
                if lane==self.game.sim.current:self.game._assign(self.game.sim,row['fields'])
        self.assertTrue(auto.settle(self.backend)['ok'])

    def test_ordinary_ready_without_held_scope_never_reads_or_retains_appearance(self):
        with patch.object(native_cas_engine,'_LAYOUT_SCOPE',None), \
                patch.object(auto.primitive,'read_owners',side_effect=AssertionError('No normal-load scan')):
            self.assertEqual(auto.note_native_ready(self.backend,self.game.sim.occult_tracker)['state'],'not-applicable')
        self.assertFalse(hasattr(self.backend,'_APEX_CAS_NATIVE_READY_WITNESS'))

    def test_durable_frontdoor_roster_or_receiver_change_never_starts_writes(self):
        for damage in ('frontdoor-file','roster','epoch','held-receiver','native-peers'):
            with self.subTest(damage=damage):
                self.setUp();self.begin(multiple=True)
                if damage=='frontdoor-file':self.frontdoor.write_text('{}')
                elif damage=='roster':self.sims.pop('11')
                elif damage=='epoch':self.scope['epochs']=dict(self.epochs,**{'11':'f'*64})
                elif damage=='held-receiver':
                    path,key,record,tx=bank._selected(self.backend,self.sims['11'])
                    bank._CAPTURED[bank._cache_key(path,key,tx['transaction_id'])]['backend']=object()
                else:self.enterContext(patch.object(cas_ui,'diagnostics',return_value={'native_peers':[{}]}))
                before=self.game.path.read_bytes();result=auto.settle(self.backend)
                self.assertFalse(result['ok']);self.assertEqual(self.writes,[])
                self.assertEqual(self.game.path.read_bytes(),before)

    def test_every_graph_is_preflighted_before_first_observation_or_write(self):
        self.begin(multiple=True);before=self.game.path.read_bytes()
        self.returned['11']['identity']['generation']+=1
        result=auto.settle(self.backend)
        self.assertFalse(result['ok']);self.assertEqual(self.writes,[])
        self.assertEqual(self.game.path.read_bytes(),before)

    def test_real_save_wrapper_completes_all_members_before_serializer_and_only_saves_once(self):
        import test_cas_save_boundary as saving
        from apex_core import named_save_boundary
        self.begin(multiple=True);service=saving.native_service_type()()
        self.backend.services.get_persistence_service=lambda:service
        reason=object();original=service.__class__._save_game_gen
        service.__class__._save_game_gen=named_save_boundary.wrap(self.backend,original,reason)
        with patch.object(named_save_boundary,'prepare',side_effect=lambda *_a:self.assertFalse(gate.admission(self.backend)['locked'])):
            generator=service.save('Save');self.assertEqual(next(generator),'serialized')
            self.assertTrue(all(bank._completed(self.game.data()['records']['30:'+sid]['cas_transaction']) for sid in self.sims))
            with self.assertRaises(StopIteration) as done:next(generator)
        self.assertEqual(done.exception.value,('SUCCESS',None))
        self.assertEqual(service.serializer_calls,['Save']);self.assertEqual(service.save_file_creations,['Save'])

    def test_retirement_is_after_all_final_readbacks_and_never_replays_committed_owners(self):
        self.begin(multiple=True);retired=[]
        def retire(_b,sim,_tx):
            self.assertTrue(all(bank._completed(self.game.data()['records']['30:'+sid]['cas_transaction']) for sid in self.sims))
            self.assertFalse(gate.admission(self.backend)['locked']);retired.append(str(sim.id))
            raise RuntimeError('Retirement transport lost')
        with patch.object(native_cas_engine,'complete_return',side_effect=retire):result=auto.settle(self.backend)
        self.assertTrue(result['ok'],result);self.assertEqual(retired,['10','11'])
        before=len(self.writes);self.assertEqual(auto.settle(self.backend)['state'],'idle');self.assertEqual(len(self.writes),before)

    def test_unresolved_group_blocks_actual_save_even_if_failure_retention_file_write_failed(self):
        self.begin(multiple=True)
        def collateral(owner,values):
            self.restore(owner,values)
            if owner.id==11:self.game.forms[1].physique='late collateral'
        self.backend._restore_siminfo_payload=collateral
        with patch.object(auto,'_retain_failure',side_effect=OSError('disk refused retention marker')):
            result=auto.settle(self.backend)
        self.assertTrue(result['unresolved']);self.assertIn('retention_storage_error',result)
        self.assertTrue(gate.admission(self.backend)['locked'])
        self.game.path.unlink();self.assertTrue(gate.admission(self.backend)['locked'])
        before=len(self.writes);self.assertFalse(auto.settle(self.backend)['ok']);self.assertEqual(len(self.writes),before)

    def test_completed_receipt_checks_native_intent_even_after_plan_digest_is_recomputed(self):
        self.begin(cancel=True);self.assertTrue(auto.settle(self.backend)['ok'])
        original=self.game.record()['cas_transaction']
        for damage in ('members','generation','pid','intent','cancel-handled','cancel-session','cancel-serial'):
            with self.subTest(damage=damage):
                tx=copy.deepcopy(original);plan=tx['journal']['plan'];witness=plan['authenticated_native_intent']
                if damage=='members':witness['captured_sim_ids']=['99']
                elif damage=='generation':witness['generations']['10']+=1
                elif damage=='pid':witness['runtime_pid']+=1
                elif damage=='intent':witness['intent']='keep-looking-similar'
                elif damage=='cancel-handled':witness['native_handled']=False
                elif damage=='cancel-session':witness['session']=-1
                else:witness['cancel_serial']=0
                digest=auto.primitive.digest(plan)
                tx['journal']['plan_sha256']=digest;tx['metadata_commit']['plan_sha256']=digest
                self.assertEqual(auto.primitive.digest(plan),digest)
                self.assertFalse(bank._completed_uncached(tx))

    def test_forged_capability_and_json_route_cannot_prepare_native_intent(self):
        self.begin()
        with self.assertRaises(ValueError):bank.prepare_native_accepted(self.backend,self.game.sim,dict(self.proof))
        self.assertNotIn('cas_bank_prepare_native_accepted',bank.ACTION_NAMES)


if __name__=='__main__':unittest.main()
