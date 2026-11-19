import base64
import copy
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import tray_library as tray
import tray_cli
import apex_cli
import reusable_profile


def varint(value):
    out=bytearray()
    while value>127:out.append((value&127)|128);value>>=7
    out.append(value);return bytes(out)


def wire(number,value,kind=2):
    return varint(number*8+kind)+(varint(len(value))+value if kind==2 else varint(value))


class TrayLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.folder=self.root/'Tray';self.folder.mkdir()
        self.item='0x00000001!0x00f51748712e0032.trayitem'
        self.native=b'original native Sim including unknown fields'
        payload=wire(1,wire(3,b'Household')+wire(6,self.native)+wire(200,b'future household field'))
        self.raw=struct.pack('<IIII',2,len(payload)+17,0,len(payload))+payload+b'\x01\0\0\0\0'
        self.file=self.folder/'0x00000000!0x00f51748712e0032.householdbinary';self.file.write_bytes(self.raw)
        (self.folder/self.item).write_bytes(b'original metadata')
        (self.folder/'0x00000013!0x03f51748712e0033.sgi').write_bytes(b'original thumbnail')

    def test_v2_household_retains_exact_sim_unknown_fields_and_native_footer(self):
        decoded=tray.sims(self.raw)
        self.assertEqual(decoded['name'],'Household');self.assertEqual(decoded['version'],2)
        self.assertEqual(base64.b64decode(decoded['sims'][0]),self.native)
        def worker(request):
            self.assertEqual(request['sims'],decoded['sims'])
            return dict(ok=True,game_contacted=False,disk_assets_written=False,sims=[])
        before=self.file.read_bytes()
        self.assertTrue(tray.inspect(self.file,hashlib.sha256(before).hexdigest(),worker)['ok'])
        self.assertEqual(self.file.read_bytes(),before)
        with self.assertRaises(ValueError):tray.inspect(self.file,'a'*64,worker)

    def test_unknown_truncated_duplicate_and_wrong_wire_households_refused(self):
        for raw in (b'',self.raw[:-1],struct.pack('<II',3,4),self.raw[:8]+struct.pack('<II',1,10)+self.raw[16:]):
            with self.subTest(raw=raw[:16]),self.assertRaises(ValueError):tray.sims(raw)
        for payload in (wire(1,b'')+wire(1,b''),wire(1,wire(6,1,0))):
            raw=struct.pack('<II',1,len(payload)+4)+payload
            with self.assertRaises(ValueError):tray.sims(raw)

    def test_whole_group_exchange_retains_images_footer_and_metadata_without_overwrites(self):
        before={p.name:p.read_bytes() for p in self.folder.iterdir()}
        bundle=self.root/'sim.zip';result=tray.export(self.folder,self.item,bundle)
        self.assertEqual(result['files'],3)
        with zipfile.ZipFile(bundle) as z:
            self.assertEqual({n:z.read(n) for n in before},before)
        active=self.root/'The Sims 4';active.mkdir();dest=active/'Tray';dest.mkdir()
        with patch.object(apex_cli,'require_isolated'),patch.object(reusable_profile,'load',return_value=(None,None,active,self.root/'original')):
            imported=tray.import_bundle(bundle,self.root/'state.json');self.assertEqual(imported['created'],3)
            self.assertEqual(tray.import_bundle(bundle,self.root/'state.json')['already_identical'],3)
            (dest/self.item).write_bytes(b'concurrent user edit')
            with self.assertRaisesRegex(ValueError,'no file was overwritten'):tray.import_bundle(bundle,self.root/'state.json')
        self.assertEqual({p.name:p.read_bytes() for p in self.folder.iterdir()},before)
        self.assertEqual((dest/self.item).read_bytes(),b'concurrent user edit')

    def test_protected_original_can_only_be_read_not_destination(self):
        original=self.root/reusable_profile.PROTECTED_NAME;original.mkdir()
        with self.assertRaises(ValueError):tray.export(self.folder,self.item,original/'export.zip')
        self.assertEqual(list(original.iterdir()),[])

    def test_archive_traversal_and_mixed_item_groups_refused_before_writes(self):
        active=self.root/'The Sims 4';active.mkdir()
        for label,files in [('escape',{'../oops':b'x'}),('mixed',{self.item:b'item','0x00000001!0x00f51748712e0034.trayitem':b'other'})]:
            archive=self.root/(label+'.zip')
            with zipfile.ZipFile(archive,'w') as z:
                for n,raw in files.items():z.writestr(n,raw)
                z.writestr('ApexTrayManifest.json',json.dumps(dict(schema=1,item=self.item,files={n:hashlib.sha256(v).hexdigest() for n,v in files.items()})))
            with patch.object(apex_cli,'require_isolated'),patch.object(reusable_profile,'load',return_value=(None,None,active,self.root/'original')),self.assertRaises(ValueError):
                tray.import_bundle(archive,self.root/'state.json')
            self.assertFalse((active/'Tray').exists())

    def test_missing_zero_outfit_identity_and_duplicate_wire_are_handled_exactly(self):
        outfit=wire(2,0,0)+wire(5,b'parts')
        sim=dict(sim_id='42',name='Source',native_sim='AQ==',native_sha256='a'*64,forms=[dict(form=2,fields={'__outfits__':dict(kind='protobuf',value=base64.b64encode(wire(1,outfit)).decode())})])
        result=tray.preview_forms(sim,'b'*64,dict(pid=77),dict(history_lane='123:2:999:8:runtime-77'))
        self.assertEqual(result[0]['outfits'][0]['outfit_id'],'0')
        self.assertIn(':42:2:',result[0]['request']['lane']);self.assertNotIn(':999:',result[0]['request']['lane'])
        broken=copy.deepcopy(sim);broken['forms'][0]['fields']['__outfits__']['value']=base64.b64encode(wire(1,outfit+wire(1,b'wrong type'))).decode()
        with self.assertRaises(ValueError):tray.preview_forms(broken,'b'*64,dict(pid=77),dict(history_lane='123:2:999:8:runtime-77'))

    def test_paste_requires_explicit_destination_selection_before_game_submission(self):
        inspection=self.root/'inspection.json';inspection.write_text(json.dumps(dict(ok=True,game_contacted=False,sims=[dict(sim_id='42',forms=[dict(form=2,fields={})])])),encoding='utf-8')
        args=apex_cli.parser().parse_args(['tray','paste','--inspection',str(inspection),'--expected-sha256',hashlib.sha256(inspection.read_bytes()).hexdigest(),
            '--state',str(self.root/'state.json'),'--source-sim-id','42','--form','2','--target-sim-id','99'])
        with patch.object(apex_cli,'owned_request',side_effect=AssertionError('game contacted')) as submit,self.assertRaisesRegex(ValueError,'destination form'):
            tray_cli.execute(args)
        submit.assert_not_called()


if __name__=='__main__':unittest.main()
