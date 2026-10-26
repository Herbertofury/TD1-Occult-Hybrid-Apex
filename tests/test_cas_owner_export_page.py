import copy
import hashlib
import unittest
from apex_core.cas_owner_export_page import Collector,validate
from apex_core import native_cas_engine as engine


class OwnerExportPageTests(unittest.TestCase):
    def setUp(self):
        self.identity=dict(pid=555,scope_id='a'*32,sim_id='123',generation=17,
                           owned_mask=3,selected_owner_id='alien/alternate')
        self.kinds={'alien/alternate':2,'ghost/manifested':1,'ghost/living':1}

    def page(self,start=0,count=2):
        ids=sorted(self.kinds);selected=ids[start:start+count];rows=[]
        for n,owner in enumerate(selected):
            raw=b'\x08\x7b\xf8\xff\x01'+bytes([start+n+11])
            rows.append(dict(owner_id=owner,native_kind=self.kinds[owner],native_hex=raw.hex(),
                             bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),revision=3,
                             linked_targets=['ghost/living'] if owner=='ghost/manifested' else []))
        end=start+len(rows)
        return dict(self.identity,ok=True,schema=1,scope='native-owner-export-page',
            after_owner_id=ids[start-1] if start else '',start_index=start,total_owners=len(ids),
            owners=rows,complete=end==len(ids),next_owner_id=None if end==len(ids) else selected[-1],
            appearance_written=False,model_harvested=False,game_files_written=False,
            native_patch_qualified=False,production_ready=False,source='committed-native-appearance')

    def test_complete_collection_preserves_same_kind_owners_and_unknown_bytes(self):
        collector=Collector(self.identity,self.kinds)
        first=self.page();second=self.page(2,1)
        self.assertFalse(collector.append(first)['complete'])
        with self.assertRaises(ValueError):collector.document()
        self.assertTrue(collector.append(second)['complete'])
        document=collector.document()
        self.assertEqual([row['owner_id'] for row in document['owners']],sorted(self.kinds))
        self.assertEqual(document['owners'][1]['native_hex'],'087bf8ff010c')
        self.assertEqual(document['owners'][2]['linked_targets'],['ghost/living'])
        document['owners'][1]['native_hex']='00'
        self.assertNotEqual(document,collector.document())
        with self.assertRaises(ValueError):collector.append(second)

    def test_stale_runtime_generation_scope_cursor_and_partial_page_refuse_atomically(self):
        collector=Collector(self.identity,self.kinds);collector.append(self.page())
        before=copy.deepcopy(collector.__dict__)
        for key,value in [('pid',556),('sim_id','456'),('scope_id','b'*32),('generation',18),
                          ('after_owner_id','alien/alternate'),('start_index',0),('total_owners',4),
                          ('complete',False),('next_owner_id','ghost/living'),('appearance_written',True),
                          ('owned_mask',7),('selected_owner_id','ghost/living')]:
            with self.subTest(key=key):
                page=self.page(2,1);page[key]=value
                with self.assertRaises(ValueError):collector.append(page)
                self.assertEqual(collector.__dict__,before)

    def test_corruption_duplicate_and_relabelled_owner_refuse(self):
        for damage in ('digest','truncate','uppercase','duplicate','kind','unknown'):
            with self.subTest(damage=damage):
                page=self.page();row=page['owners'][-1]
                if damage=='digest':row['sha256']='0'*64
                elif damage=='truncate':row['native_hex']=row['native_hex'][:-2]
                elif damage=='uppercase':row['native_hex']=row['native_hex'].upper()
                elif damage=='duplicate':row['owner_id']=page['owners'][0]['owner_id']
                elif damage=='kind':row['native_kind']=4
                else:row['owner_id']='future/other';page['next_owner_id']=row['owner_id']
                collector=Collector(self.identity,self.kinds)
                with self.assertRaises(ValueError):collector.append(page)
                self.assertEqual(collector.rows,[])

    def test_reply_and_request_remain_read_only_and_bounded(self):
        page=self.page()
        self.assertEqual(engine.reply(copy.deepcopy(page),555),dict(page,owner_appearance_query='unavailable',bank_commit_authorized=False))
        request=dict(operation='export-owner-page',scope_id='a'*32,sim_id='123',
                     expected_generation=17,after_owner_id='')
        engine.argument(request)
        for key,value in [('expected_generation',True),('sim_id','0123'),('after_owner_id','bad'),('scope_id','z'*32)]:
            with self.subTest(key=key):
                damaged=dict(request);damaged[key]=value
                with self.assertRaises(ValueError):engine.argument(damaged)
        for key,value in [('schema',True),('pid',True),('generation',True),('total_owners',2049),('model_harvested',True)]:
            with self.subTest(key=key):
                damaged=copy.deepcopy(page);damaged[key]=value
                with self.assertRaises(ValueError):validate(damaged,555)

    def test_links_and_revisions_cannot_be_lost_or_redirected(self):
        for key,value in [('linked_targets',['ghost/living']*2),('linked_targets',['ghost/manifested']),
                          ('linked_targets',['other/missing']),('revision',True),('revision',-1)]:
            with self.subTest(key=key,value=value):
                collector=Collector(self.identity,self.kinds);collector.append(self.page())
                page=self.page(2,1);page['owners'][0][key]=value
                with self.assertRaises(ValueError):collector.append(page)
                self.assertEqual(len(collector.rows),2)

    def test_large_payload_cannot_exceed_page_budget_even_with_valid_digests(self):
        page=self.page()
        raw=b'x'*(300*1024)
        for row in page['owners']:
            row.update(bytes=len(raw),native_hex=raw.hex(),sha256=hashlib.sha256(raw).hexdigest())
        with self.assertRaises(ValueError):validate(page,555)


if __name__=='__main__':unittest.main()
