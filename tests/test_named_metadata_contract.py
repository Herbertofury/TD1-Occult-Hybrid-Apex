"""Cross-build metadata compatibility with real household seal validation."""
import copy,json,threading,unittest
from unittest.mock import patch
import test_household_bank_seal as fixture
from apex_core import form_bank_seal as seal,form_appearance as appearance,lifestate_forms as forms


class NamedMetadataHouseholdContractTests(unittest.TestCase):
    def setUp(self):
        self.game=fixture.HouseholdBankSealTests();self.game.setUp();self.addCleanup(self.game.doCleanups)
        self.backend=self.game.backend;self.backend._APEX_GAME_THREAD_IDENT=threading.current_thread().ident
        self.backend._get_sim_info_by_id=lambda sid:next((sim for sim in self.game.sims if str(sim.id)==str(sid)),None)
        self.enterContext(patch('apex_core.form_bank._old_process_absent',return_value=True))
        self.saved={}
        for sim in self.game.sims:
            key=fixture.GUID+':'+str(sim.id);record=self.game.bank['records'][key]
            fields=copy.deepcopy(record['bank']['1']);fields['physique']=appearance.encode('saved independent Ghost '+str(sim.id))
            record[forms.KEY]=dict(schema=1,forms={'ghost_ghost':dict(id='ghost_ghost',lifestate='GHOST',label='Ghost',base_form=1,
                fields=fields,appearance_sha256=appearance.fingerprint(fields)['appearance_sha256'])},active={})
            forms._bind_runtime(record,sim);self.saved[key]=copy.deepcopy(record[forms.KEY])
        self.game.bank_path.write_text(json.dumps(self.game.bank))
        self.game.finish(self.game.begin());self.certificates=seal._store(self.game.path)
        self.game.identity['script_sha256']='e'*64;self.game.identity['pid']+=1

    def test_one_saved_household_keeps_all_named_documents_after_unlisted_code_update(self):
        before_seals=self.game.path.read_bytes();before_save=self.game.slot.read_bytes()
        for sim in self.game.sims:seal.note_loaded(sim.occult_tracker)
        for sim in self.game.sims:
            self.assertTrue(seal.admit_saved_named(self.backend,sim))
            data=json.loads(self.game.bank_path.read_text());key=fixture.GUID+':'+str(sim.id)
            self.assertEqual(data['records'][key][forms.KEY],self.saved[key])
            self.assertTrue(forms._owns_runtime(data['records'][key],sim))
            self.assertFalse(seal.current_runtime_bank_verified(self.backend,sim,data['records'][key]))
        self.assertEqual(self.game.writes,[]);self.assertEqual(self.game.path.read_bytes(),before_seals)
        self.assertEqual(self.game.slot.read_bytes(),before_save)

    def test_changed_household_group_never_partially_admits_the_selected_member(self):
        primary=self.game.key;peer=next(key for key in self.certificates['records'] if key!=primary)
        for damage in ('missing-peer','duplicate-intent','roster','source','contract','file'):
            with self.subTest(damage=damage):
                value=copy.deepcopy(self.certificates);row=value['records'][primary]
                if damage=='missing-peer':value['records'].pop(peer)
                elif damage=='duplicate-intent':
                    value['records'][peer]['intent_id']=row['intent_id']
                    for item in value['records'].values():item['save_group']['member_intents'][peer]=row['intent_id']
                elif damage=='roster':
                    for item in value['records'].values():item['save_group']['roster_sim_ids'].append(str(self.game.sim.id))
                elif damage=='source':value['records'][peer]['identity']['script_sha256']='d'*64
                elif damage=='contract':value['records'][peer]['contract_sha256']='f'*64
                else:value['records'][peer]['target']['slot_id']+=1
                for item in value['records'].values():item['seal_sha256']=seal._seal_digest(item)
                seal._write(self.game.path,value);seal._LOADED.clear()
                before=self.game.bank_path.read_bytes()
                self.assertFalse(seal.admit_saved_named(self.backend,self.game.sim))
                self.assertEqual(self.game.bank_path.read_bytes(),before);self.assertEqual(self.game.writes,[])


if __name__=='__main__':unittest.main()
