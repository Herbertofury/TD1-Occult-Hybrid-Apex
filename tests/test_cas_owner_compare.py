import copy
import unittest
from cas_owner_compare import compare
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


if __name__=='__main__':unittest.main()
