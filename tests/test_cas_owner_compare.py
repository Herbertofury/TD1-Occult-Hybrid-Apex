import copy
import unittest
from cas_owner_compare import compare,original_outfit_records
from apex_core import form_appearance as appearance


class OwnerAppearanceComparisonTests(unittest.TestCase):
    def fixture(self):
        fields=dict(physique=appearance.encode('original'),genetic_data=appearance.encode(b'\xa0\x06\x01'),
                    pelt_layers=appearance.encode(b'\xa0\x06\x01'),__outfits__=appearance.encode(('protobuf',b'\xa0\x06\x01')))
        reference=dict(ok=True,native_scope_id='a'*32,members={'123':{'ghost/living':dict(native_kind=1,fields=fields)}})
        page=dict(ok=True,scope='native-owner-export-page',scope_id='a'*32,sim_id='123',
            owner_appearance_query='returned-value',appearance_written=False,model_harvested=False,
            owners=[dict(owner_id='ghost/living',sha256='b'*64)],owner_appearances=[dict(owner_id='ghost/living',native_kind=1,
                fields=copy.deepcopy(fields),native_sha256='b'*64)])
        return reference,page

    def test_intended_physique_does_not_hide_unintended_pelt_or_genetic_changes(self):
        reference,page=self.fixture();row=page['owner_appearances'][0];row['fields']['physique']=appearance.encode('edited')
        self.assertTrue(compare(reference,[page],['physique'])['ok'])
        for field in ('pelt_layers','genetic_data','__outfits__'):
            changed=copy.deepcopy(page);changed['owner_appearances'][0]['fields'][field]=appearance.encode(
                ('protobuf',b'\xa0\x06\x02') if field=='__outfits__' else b'\xa0\x06\x02')
            result=compare(reference,[changed],['physique'])
            self.assertFalse(result['ok']);self.assertEqual(result['differences'][0]['fields'],[field])

    def test_missing_duplicate_changed_scope_or_raw_binding_refuse(self):
        reference,page=self.fixture()
        for change in ('missing','duplicate','scope','sha','decode'):
            changed=copy.deepcopy(page)
            if change=='missing':pages=[]
            elif change=='duplicate':pages=[changed,changed]
            else:
                pages=[changed]
                if change=='scope':changed['scope_id']='c'*32
                elif change=='sha':changed['owner_appearances'][0]['native_sha256']='c'*64
                else:changed['owner_appearance_query']='unavailable'
            with self.subTest(change=change),self.assertRaises(ValueError):compare(reference,pages,['physique'])

    def test_added_outfits_are_reported_without_passing_the_strict_comparison(self):
        reference,page=self.fixture()
        original=appearance.encode(('protobuf',b'\x0a\x07\x08\x01\x10\x00\xa0\x06\x01\xa0\x06\x01'))
        added=appearance.encode(('protobuf',b'\x0a\x07\x08\x01\x10\x00\xa0\x06\x01\x0a\x04\x08\x02\x10\x01\xa0\x06\x01'))
        reference['members']['123']['ghost/living']['fields']['__outfits__']=original
        page['owner_appearances'][0]['fields']['__outfits__']=added
        result=compare(reference,[page],['physique'])
        self.assertFalse(result['ok']);self.assertTrue(result['original_fields_and_outfit_records_retained'])
        self.assertEqual(result['added_outfits'][0]['records'],[dict(category=1,ordinal=0)])
        self.assertFalse(result['added_outfits_user_authorized'])
        raw=bytearray(appearance.decode(added)[1]);raw[8]=2
        changed=appearance.encode(('protobuf',bytes(raw)))
        self.assertFalse(original_outfit_records(original,changed)['original_records_retained'])


if __name__=='__main__':unittest.main()
