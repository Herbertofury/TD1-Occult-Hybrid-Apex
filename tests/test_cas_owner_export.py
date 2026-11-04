from contextlib import nullcontext
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import apex_cli
import cas_client
import cli_identity_cache
import cas_owner_export as client
from test_native_cas_probe_cli import Evidence


class OwnerExportCliTests(unittest.TestCase):
    def run_export(self,damage=None,sim_id=None):
        kinds={'123':{'alien/real':2,'human/base':1,'ghost/manifested':1},
               '456':{'servo/robot':1,'servo/human_cc':1}}
        native=dict(ok=True,pid=555,scope_id='a'*32,selection_enabled=True,
            selected_native=dict(available=True,sim_id='123'),members=[])
        for sid,owners in kinds.items():
            mask=3 if sid=='123' else 1
            native['members'].append(dict(sim_id=sid,owned_mask=mask,imported_mask=mask,
                graph_generation=17,graph_selected_owner_id=sorted(owners)[0],
                separate_owners=[dict(owner_id=owner,native_kind=kind) for owner,kind in owners.items()]))
        calls=[];statuses=0
        def execute(args):
            nonlocal statuses
            value=json.loads(args.value);calls.append(value)
            if value['operation']=='status':
                statuses+=1;result=copy.deepcopy(native)
                if statuses>1 and damage=='stale':result['members'][1]['graph_generation']=18
            else:
                sid=value['sim_id'];member=next(row for row in native['members'] if row['sim_id']==sid)
                rows=[]
                for owner,kind in sorted(kinds[sid].items()):
                    raw=(sid+owner).encode('ascii')
                    rows.append(dict(owner_id=owner,native_kind=kind,revision=2,linked_targets=[],
                        bytes=len(raw),native_hex=raw.hex(),sha256=hashlib.sha256(raw).hexdigest()))
                result=dict(ok=True,schema=1,pid=555,scope='native-owner-export-page',scope_id='a'*32,
                    sim_id=sid,generation=17,owned_mask=member['owned_mask'],selected_owner_id=member['graph_selected_owner_id'],
                    after_owner_id='',start_index=0,total_owners=len(rows),owners=rows,complete=True,next_owner_id=None,
                    appearance_written=False,model_harvested=False,game_files_written=False,
                    native_patch_qualified=False,production_ready=False,source='committed-native-appearance')
                if damage=='missing':result['owners']=result['owners'][:-1]
            args.output.write_text(json.dumps(result),encoding='utf-8')
            return result
        with tempfile.TemporaryDirectory(prefix='apex-owner-export-unit-') as directory, \
                patch.object(apex_cli,'execute',side_effect=execute), \
                patch.object(cas_client,'IntentEvidence',return_value=Evidence()), \
                patch.object(cli_identity_cache,'session',return_value=nullcontext()):
            result=client.run(Path('state'),Path(directory)/'new.json',sim_id)
        return result,calls

    def test_default_exports_all_members_and_keeps_same_kind_variants_separate(self):
        result,calls=self.run_export()
        self.assertTrue(result['ok']);self.assertEqual(len(result['members']),2)
        self.assertEqual([len(member['owners']) for member in result['members']],[3,2])
        self.assertEqual([c['sim_id'] for c in calls if c['operation']=='export-owner-page'],['123','456'])
        self.assertFalse(result['appearance_written']);self.assertFalse(result['cas_accept_submitted'])
        self.assertFalse(result['save_submitted']);self.assertFalse(result['production_ready'])
        parsed=apex_cli.parser().parse_args(['cas-owner-export','--state','state','--output','new.json'])
        self.assertIsNone(parsed.sim_id)

    def test_unrelated_member_generation_change_prevents_complete_household_claim(self):
        result,calls=self.run_export('stale')
        self.assertFalse(result['ok']);self.assertIn('changed during export',result['error'])
        self.assertEqual(sum(c['operation']=='status' for c in calls),2)

    def test_partial_page_stops_without_replay_or_exporting_the_next_member(self):
        result,calls=self.run_export('missing')
        self.assertFalse(result['ok']);self.assertIn('continuation',result['error'])
        self.assertEqual(sum(c['operation']=='export-owner-page' for c in calls),1)


if __name__=='__main__':unittest.main()
