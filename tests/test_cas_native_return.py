import copy
import hashlib
import os
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import cas_native_return as native, form_appearance as appearance


class NativeReturnTests(unittest.TestCase):
    def fixture(self):
        def fields(label):
            return {name: appearance.encode(value) for name,value in dict(
                physique=label,genetic_data=b'unknown\x00\xff',facial_attributes=b'face',
                parts_custom_tattoos={7:9001},__outfits__=('protobuf',b'\xa0\x06\x01')).items()}
        raw=dict(identity=dict(runtime_pid=os.getpid(),sim_id='10',household_id='20',save_guid='30'),
                 stored={str(lane):fields('Live-'+str(lane)) for lane in (1,2,4)},
                 active=dict(lane='2',fields=fields('Live-2')))
        owners=[]
        for oid,kind in [('native/1',1),('native/2',2),('active/2',2),('native/4',4),('ghost/ghost_ghost',1)]:
            data=(oid+'-complete-native').encode()
            owners.append(dict(owner_id=oid,native_kind=kind,native_hex=data.hex(),
                sha256=hashlib.sha256(data).hexdigest(),fields=fields('CAS-'+oid)))
        returned=dict(ok=True,source='receiver-native-owner-return',appearance_written=False,checkpoint_epoch='a'*64,
            identity=dict(pid=os.getpid(),sim_id='10'),owners=owners,
            logical_owner_ids={'1':'native/1','2':'active/2','4':'native/4'},human_owner_id='native/1')
        return raw,returned

    def test_logical_active_alien_and_shared_human_win_over_hidden_stale_aliases_without_merging(self):
        raw,returned=self.fixture();before=copy.deepcopy((raw,returned))
        result=native.project(returned,raw,'a'*64)
        self.assertEqual(result['stored']['1']['physique']['value'],'CAS-native/1')
        self.assertEqual(result['stored']['2']['physique']['value'],'CAS-active/2')
        self.assertEqual(result['stored']['4']['physique']['value'],'CAS-native/4')
        self.assertEqual(result['active']['fields'],result['stored']['2'])
        self.assertEqual((raw,returned),before)
        result['stored']['2']['genetic_data']['value']='mutated'
        self.assertEqual((raw,returned),before)

    def test_foreign_missing_same_genus_substitute_or_malformed_return_never_projects_partial_data(self):
        for damage in ('pid','sim','epoch','binding','human','missing','duplicate','genus','bytes','digest','field'):
            with self.subTest(damage=damage):
                raw,returned=self.fixture()
                if damage=='pid':returned['identity']['pid']+=1
                elif damage=='sim':returned['identity']['sim_id']='11'
                elif damage=='epoch':returned['checkpoint_epoch']='b'*64
                elif damage=='binding':returned['logical_owner_ids']['2']='native/4'
                elif damage=='human':returned['logical_owner_ids']['1']='ghost/ghost_ghost'
                elif damage=='missing':del returned['logical_owner_ids']['4']
                elif damage=='duplicate':returned['owners'].append(copy.deepcopy(returned['owners'][0]))
                elif damage=='genus':returned['owners'][2]['native_kind']=4
                elif damage=='bytes':returned['owners'][2]['native_hex']='00'
                elif damage=='digest':returned['owners'][2]['sha256']='0'*64
                else:del returned['owners'][2]['fields']['genetic_data']
                before=copy.deepcopy(raw)
                with self.assertRaises(ValueError):native.project(returned,raw,'a'*64)
                self.assertEqual(raw,before)

    def test_historical_projection_can_verify_old_receipt_but_cannot_supply_a_live_receiver(self):
        raw,returned=self.fixture()
        old_pid=0xfffffffe
        raw['identity']['runtime_pid']=old_pid;returned['identity']['pid']=old_pid
        archived=native.project_archive(returned,raw,'a'*64)
        self.assertEqual(archived['stored']['2']['physique']['value'],'CAS-active/2')
        with self.assertRaisesRegex(ValueError,'this runtime'):
            native.project(returned,raw,'a'*64)


if __name__=='__main__':unittest.main()
