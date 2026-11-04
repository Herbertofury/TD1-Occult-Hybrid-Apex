import base64
import hashlib
from pathlib import Path
import struct
import sys
import unittest
import json
import tempfile
import zipfile
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import household_cli as cli
import tray_library
from live_color_probe import chunks


class HouseholdExportTests(unittest.TestCase):
    def setUp(self):
        self.original=b'\x09'+struct.pack('<Q',11)+cli.blob(501,b'old sim unknown')
        body=cli.integer(2,99)+cli.blob(3,b'old')+cli.blob(6,self.original)+cli.blob(502,b'future family')
        payload=cli.blob(1,body)+cli.integer(3,11)+cli.blob(503,b'future envelope')
        self.template=struct.pack('<IIII',2,len(payload)+17,0,len(payload))+payload+b'\x01\0\0\0\0'
        specific=cli.blob(2,cli.integer(1,1)+cli.blob(2,b'old sim metadata')+cli.blob(504,b'future household metadata'))
        meta=cli.integer(1,99)+cli.blob(3,b'remote gallery id')+cli.blob(4,b'old')+cli.blob(10,specific)+cli.integer(12,123)+cli.integer(20,1)+cli.blob(505,b'future metadata')
        self.metadata=struct.pack('<II',0,len(meta))+meta
        self.records=[]
        for i in (21,22,23):
            raw=b'\x09'+struct.pack('<Q',i)+cli.blob(501,b'complete sim unknown')
            self.records.append(dict(sim_id=str(i),native_sim=base64.b64encode(raw).decode(),native_sha256=hashlib.sha256(raw).hexdigest()))

    def test_three_complete_records_unknown_fields_and_new_identity_roundtrip(self):
        raw,meta=cli.build(self.template,self.metadata,self.records,123456,'Three hybrids')
        self.assertEqual(tray_library.sims(raw)['sims'],[r['native_sim'] for r in self.records])
        self.assertEqual(tray_library.sims(raw)['name'],'Three hybrids')
        self.assertEqual(raw[-5:],b'\x03\0\0\0\0')
        self.assertIn(b'future envelope',raw);self.assertIn(b'future family',raw)
        self.assertIn(b'future metadata',meta);self.assertIn(b'future household metadata',meta)
        fields=list(chunks(meta[8:]));self.assertEqual([v for n,k,v,w in fields if n==1],[123456])
        self.assertNotIn(3,[n for n,k,v,w in fields]);self.assertNotIn(20,[n for n,k,v,w in fields])
        self.assertIn(12,[n for n,k,v,w in fields])
        self.assertNotIn(b'old sim metadata',meta)
        self.assertEqual(struct.unpack_from('<II',meta),(0,len(meta)-8))

    def test_colliding_members_corrupt_bytes_and_wrong_record_identity_refused(self):
        for records in (self.records+[self.records[0]], [dict(self.records[0],native_sha256='0'*64)], [dict(self.records[0],sim_id='99')]):
            with self.assertRaises(ValueError):cli.build(self.template,self.metadata,records,123,'New')

    def test_unknown_footer_and_metadata_do_not_create_guessed_household(self):
        with self.assertRaises(ValueError):cli.build(self.template[:-1]+b'x',self.metadata,self.records,123,'New')
        with self.assertRaises(ValueError):cli.build(self.template,self.metadata[:-1],self.records,123,'New')

    def test_cli_requires_explicit_inventory_and_dispatches_typed_operation(self):
        import apex_cli
        args=apex_cli.parser().parse_args(['household','load-tray','--state','state.json','--sim-id','21','--values','members.json'])
        self.assertEqual(args.operation,'load-tray');self.assertEqual(args.values,Path('members.json'))

    def test_generated_record_export_never_writes_metadata_into_game_library(self):
        import apex_cli
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);active=root/'active';original=root/'original';tray=active/'Tray'
            tray.mkdir(parents=True);original.mkdir()
            template=tray/'0x00000001!0x0000000000000063.trayitem';template.write_bytes(self.metadata)
            binary=tray/'0x00000000!0x0000000000000063.householdbinary';binary.write_bytes(self.template)
            values=root/'values.json';values.write_text(json.dumps(dict(household_id='77',save_guid='88',sim_ids=['21','22','23'])))
            archive=root/'review.zip'
            args=apex_cli.parser().parse_args(['household','export-records','--state',str(root/'state.json'),'--sim-id','21',
                '--values',str(values),'--template',str(template),'--name','Three hybrids','--archive',str(archive)])
            before={p.name:p.read_bytes() for p in tray.iterdir()}
            with patch.object(apex_cli,'require_isolated'),patch.object(cli.reusable_profile,'load',return_value=(None,dict(token='f'*32),active,original)), \
                    patch.object(cli.reusable_profile,'writable',side_effect=lambda p:Path(p)), \
                    patch.object(apex_cli,'owned_request',return_value=dict(ok=True,sims=self.records)):
                result=cli.execute(args)
            self.assertFalse(result['game_library_files_written']);self.assertFalse(result['native_game_library_acceptance'])
            self.assertEqual({p.name:p.read_bytes() for p in tray.iterdir()},before)
            self.assertEqual(list(original.iterdir()),[])
            with zipfile.ZipFile(archive) as z:
                self.assertEqual(len(z.namelist()),2)
                self.assertFalse(any(n.endswith('.trayitem') for n in z.namelist()))
                candidate=json.loads(z.read('ApexHouseholdCandidate.json'))
                self.assertFalse(candidate['native_game_library_acceptance'])

    def test_unverified_gallery_export_is_refused_before_any_game_call(self):
        import apex_cli
        args=apex_cli.parser().parse_args(['household','export-tray','--state','state.json','--sim-id','21','--values','members.json'])
        with patch.object(apex_cli,'require_isolated'),patch.object(apex_cli,'owned_request') as request:
            with self.assertRaisesRegex(ValueError,'metadata/portrait generation remains unverified'):cli.execute(args)
            request.assert_not_called()

    def test_load_waits_for_queued_spawns_with_unpause_pause_and_readonly_finish(self):
        import apex_cli
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);active=root/'active';original=root/'original';active.mkdir();original.mkdir()
            values=root/'values.json';values.write_text(json.dumps(dict(household_id='77',save_guid='88')))
            output=root/'result.json'
            args=apex_cli.parser().parse_args(['household','load-tray','--state',str(root/'state.json'),'--sim-id','21',
                '--values',str(values),'--output',str(output),'--settle-seconds','0.1'])
            calls=[]
            def request(state,action,sim_id,value=None,submission_observer=None):
                calls.append(action)
                if submission_observer:submission_observer(action,'a'*32)
                if action=='test_household_import':return dict(ok=True,pending=True,created_sim_ids=['22','23'],journal_sha256='f'*64)
                if action=='test_household_finish_import':
                    self.assertEqual(json.loads(value)['value'],dict(household_id='77',save_guid='88',journal_sha256='f'*64))
                    return dict(ok=True,pending=False,created_sim_ids=['22','23'],native_instances_verified=True)
                return dict(ok=True)
            with patch.object(apex_cli,'require_isolated'),patch.object(cli.reusable_profile,'load',return_value=(None,dict(token='f'*32),active,original)),patch.object(apex_cli,'owned_request',side_effect=request),patch.object(cli.time,'sleep') as wait:
                result=cli.execute(args)
            self.assertEqual(calls,['test_household_import','test_play','test_pause','test_household_finish_import'])
            wait.assert_called_once_with(.1);self.assertFalse(result['pending'])
            self.assertEqual(len(result['creation_receipt']['lifecycle_requests']),3)
            self.assertTrue(json.loads(output.read_text())['native_instances_verified'])
            self.assertEqual(list(active.iterdir()),[]);self.assertEqual(list(original.iterdir()),[])
