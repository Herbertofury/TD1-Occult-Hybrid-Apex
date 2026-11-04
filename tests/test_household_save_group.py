import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import household_save_group as group


class HouseholdSaveGroupTests(unittest.TestCase):
    def setUp(self):
        self.roster = ['11', '12', '13']
        self.rows = {('20:' + sid): dict(state='save-intent', sealed=False,
            intent_id=format(index + 1, '032x'), identity=dict(pid=10, script_sha256='a'*64),
            contract_sha256='b'*64, before_file=dict(sha256='c'*64),
            target=dict(sim_id=sid, household_id='30', save_guid='20', slot_id=2,
                        slot_name='Existing save', expected_save_sha256='c'*64))
            for index, sid in enumerate(self.roster)}

    def test_one_save_binds_all_three_members_without_altering_the_native_preparations(self):
        original = copy.deepcopy(self.rows)
        prepared = group.prepare('20:12', self.roster, self.rows)
        self.assertEqual(self.rows, original)
        self.assertEqual(set(prepared), set(self.rows))
        for row in prepared.values():
            self.assertEqual(row['save_group']['primary_key'], '20:12')
            self.assertEqual(row['save_group']['roster_sim_ids'], self.roster)
            self.assertEqual(set(row['save_group']['member_intents']), set(self.rows))
        self.assertEqual(group.members(prepared,'20:12',self.rows['20:12']['intent_id'],('save-intent',)),prepared)

    def test_members_without_sidecars_still_belong_to_the_complete_roster(self):
        del self.rows['20:13']
        prepared = group.prepare('20:12',self.roster,self.rows)
        self.assertEqual(len(prepared),2)
        self.assertEqual(prepared['20:12']['save_group']['roster_sim_ids'],self.roster)

    def test_foreign_target_or_incomplete_member_never_changes_any_preparation(self):
        for damage in ('pid','file','slot','household','save','intent','state','roster','duplicate-roster'):
            rows=copy.deepcopy(self.rows);roster=list(self.roster);row=rows['20:13']
            if damage=='pid':row['identity']['pid']=11
            elif damage=='file':row['before_file']['sha256']='d'*64
            elif damage=='slot':row['target']['slot_id']=3
            elif damage=='household':row['target']['household_id']='31'
            elif damage=='save':row['target']['save_guid']='21'
            elif damage=='intent':row['intent_id']=rows['20:11']['intent_id']
            elif damage=='state':row['state']='save-unresolved'
            elif damage=='roster':roster.remove('13')
            else:roster.append('11')
            original=copy.deepcopy(rows)
            with self.subTest(damage=damage),self.assertRaises(ValueError):group.prepare('20:12',roster,rows)
            self.assertEqual(rows,original)

    def test_result_validation_refuses_missing_changed_or_partially_completed_group(self):
        prepared=group.prepare('20:12',self.roster,self.rows)
        for damage in ('missing','intent','group','partial-state','target','extra-roster'):
            rows=copy.deepcopy(prepared)
            if damage=='missing':del rows['20:13']
            elif damage=='intent':rows['20:13']['intent_id']='d'*32
            elif damage=='group':rows['20:13']['save_group']['primary_key']='20:11'
            elif damage=='partial-state':rows['20:13']['state']='save-submitted'
            elif damage=='target':rows['20:13']['target']['slot_name']='Another slot'
            else:rows['20:12']['save_group']['roster_sim_ids'].append('14')
            original=copy.deepcopy(rows)
            with self.subTest(damage=damage),self.assertRaises(ValueError):
                group.members(rows,'20:12',self.rows['20:12']['intent_id'],('save-intent',))
            self.assertEqual(rows,original)

    def test_legacy_single_member_receipt_does_not_gain_household_authority(self):
        receipt=copy.deepcopy(self.rows['20:12'])
        self.assertEqual(group.members({'20:12':receipt},'20:12',receipt['intent_id'],('save-intent',)),{'20:12':receipt})
        self.assertNotIn('save_group',receipt)


if __name__=='__main__':unittest.main()
