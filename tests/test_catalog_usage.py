"""Equipped metadata reads must work with CAS's suspended Live services."""
import copy
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace as NS
import unittest

sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'Source')]
from apex_core import catalog_usage


class CatalogUsageRosterTests(unittest.TestCase):
    def setUp(self):
        self.household = NS(household_id=10,name='Goth Family',sims=NS(ids=[100,101]))
        self.sims = {100:NS(sim_id=100,household_id=10,first_name='Bella',last_name='Goth'),
                     101:NS(sim_id=101,household_id=10,first_name='Mortimer',last_name='Goth')}
        self.calls=[]
        def sim(sid):
            self.calls.append(sid)
            return self.sims.get(sid)
        self.persistence = NS(get_save_slot_proto_guid=lambda:987,
            get_household_proto_buff=lambda sid:self.household if sid==10 else None,
            get_sim_proto_buff=sim)
        # Deliberately no zone, clock, active Sim, outfit getter or SimInfo
        # constructor is exposed. Reading names must not touch any of them.
        self.backend = NS(_APEX_GAME_THREAD_IDENT=threading.current_thread().ident,
                          services=NS(get_persistence_service=lambda:self.persistence))
        self.request = dict(save_guid='987',household_id='10')

    def test_complete_exact_roster_without_live_services_or_appearance_getters(self):
        before=copy.deepcopy(self.sims)
        r=catalog_usage.roster(self.backend,json.dumps(self.request))
        self.assertTrue(r['ok']);self.assertEqual([100,101],self.calls)
        self.assertEqual('Goth Family',r['name']);self.assertEqual('Bella Goth',r['members'][0]['name'])
        self.assertEqual('persisted-household-metadata',r['names_source'])
        self.assertFalse(r['appearance_written']);self.assertFalse(r['save_submitted'])
        self.assertEqual(before,self.sims)

    def test_wrong_save_foreign_member_missing_sim_or_duplicate_roster_reject(self):
        for change in ('save','household','foreign','missing','duplicate','empty','bad-name'):
            self.setUp()
            request=dict(self.request)
            if change=='save':request['save_guid']='988'
            elif change=='household':request['household_id']='11'
            elif change=='foreign':self.sims[101].household_id=20
            elif change=='missing':self.sims.pop(101)
            elif change=='duplicate':self.household.sims.ids=[100,100]
            elif change=='empty':self.household.sims.ids=[]
            else:self.household.name='x'*129
            with self.subTest(change=change),self.assertRaises(ValueError):
                catalog_usage.roster(self.backend,request)

    def test_names_cannot_supply_restore_payloads_or_noncanonical_identities(self):
        for extra in ({'appearance':{}},{'sim_id':'100'},{'native_hex':'00'}):
            with self.assertRaises(ValueError):catalog_usage.roster(self.backend,dict(self.request,**extra))
        for value in (10,'010','-1','0','18446744073709551616',True):
            with self.subTest(value=value),self.assertRaises(ValueError):
                catalog_usage.roster(self.backend,dict(self.request,household_id=value))

    def test_owner_thread_required_and_mid_read_roster_change_rejects(self):
        self.backend._APEX_GAME_THREAD_IDENT=-1
        with self.assertRaises(ValueError):catalog_usage.roster(self.backend,self.request)
        self.setUp()
        def sim(sid):
            if sid==101:self.household.sims.ids=[100]
            return self.sims[sid]
        self.persistence.get_sim_proto_buff=sim
        with self.assertRaises(ValueError):catalog_usage.roster(self.backend,self.request)


if __name__=='__main__':unittest.main()
