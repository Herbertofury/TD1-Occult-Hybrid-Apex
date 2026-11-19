import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import tempfile
import json
from argparse import Namespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from preview_cli import verify_selection
import preview_cli
import apex_cli


class PreviewSelectionTests(unittest.TestCase):
    def test_workspace_cli_delivers_typed_layout_query_without_camera_or_render_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            values = dict(layout='catalog',columns=6,tab='library',sidebar=False,
                          query=dict(text='lipstick',body_type=29,origin='mod',name_mode='package',offset=0,limit=60,view='all',author='',sort='name'))
            path = Path(temporary) / 'workspace.json'; path.write_text(json.dumps(values), encoding='utf-8')
            args = apex_cli.parser().parse_args(['preview','workspace','--state','profile.json','--values',str(path)])
            with patch.object(preview_cli,'native',return_value={'ok': True}) as submit, \
                 patch.object(preview_cli,'render',side_effect=AssertionError('render command submitted')):
                self.assertTrue(preview_cli.execute(args)['ok'])
            submit.assert_called_once_with(Path('profile.json'),dict(operation='workspace',values=values))

    def setUp(self):
        self.selection = dict(ok=True, runtime_pid=1234, history_lane='save:sim:form',
            appearance_sha256='a'*64, inspected_form_flags=2, pending_preview=None,
            outfit_inventory=[dict(outfit_id='789')])
        self.snapshot = dict(outfit_index=0, outfit_id='789')

    def test_library_selection_never_submits_an_apply_or_render_and_rejects_operation_override(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'selection.json'; values=dict(part_id='a'*64,index_sha256='b'*64,swatch_offset=120)
            path.write_text(json.dumps(values),encoding='utf-8')
            args=apex_cli.parser().parse_args(['preview','library-select','--state','profile.json','--values',str(path)])
            with patch.object(preview_cli,'native',return_value={'ok':True}) as submit, patch.object(preview_cli,'render',side_effect=AssertionError('render submitted')):
                self.assertTrue(preview_cli.execute(args)['ok'])
                submit.assert_called_once_with(Path('profile.json'),dict(values,operation='library-select'))
                path.write_text(json.dumps(dict(values,operation='load')),encoding='utf-8')
                with self.assertRaisesRegex(ValueError,'typed operation'):preview_cli.execute(args)
                self.assertEqual(submit.call_count,1)

    def test_owner_can_remain_unchanged_while_assembly_runs(self):
        verify_selection(self.selection, copy.deepcopy(self.selection), self.snapshot)

    def test_completed_render_rearms_a_cancelled_read_only_page_with_its_exact_filters(self):
        selection=dict(self.selection,outfit_inventory=[dict(outfit_id='789')])
        identity=dict(pid=1234,test_token='token',script_sha256='a'*64)
        selection['inspected_form_flags']=2
        snapshot=dict(ok=True,sim_id='42',form=2,fields={},native_sim='AQ==',native_sha256='b'*64,
            lane=selection['history_lane'],appearance_sha256=selection['appearance_sha256'],outfit_index=0,outfit_id='789',
            appearance_source='native',save_guid='123',runtime_pid=1234,save_file_written=False,history_written=False,
            render_sha256='c'*64,preview_id=None)
        job=dict(snapshot,request_id='d'*64,scene_id='e'*64,state='ready')
        query=dict(text='lipstick',body_type=29,origin='mod',name_mode='preferred',offset=120,limit=60,view='favorites',author='Author',sort='name',grouped=True)
        args=Namespace(state=Path('profile.json'),game_root=Path('game'),sim_id='42',form=2,outfit_index=0,preview_id=None)
        for ready in (False,True):
            reply=dict(ok=True,ready=True,busy=False,scene_id=job['scene_id'],sim_id='42',form=2,outfit_id='789',outfit_index=0,
                workspace=dict(query=query,catalog_ready=ready))
            with self.subTest(catalog_ready=ready), patch.object(preview_cli,'start'), \
                 patch.object(apex_cli,'verified_identity',return_value=identity), \
                 patch.object(apex_cli,'owned_request',side_effect=[selection,snapshot,selection]) as owner, \
                 patch.object(preview_cli,'http',side_effect=[dict(active=False),job]), \
                 patch.object(preview_cli,'native',side_effect=[reply,dict(ok=True)]) as submit:
                result=preview_cli.render(args)
                self.assertTrue(result['ok']);self.assertFalse(result['game_appearance_written'])
                self.assertEqual([c.args[1] for c in owner.call_args_list],['studio_status','studio_preview_snapshot','studio_status'])
                self.assertEqual(submit.call_count,1 if ready else 2)
                if not ready:submit.assert_called_with(args.state,dict(operation='workspace',values=dict(query=query)))

    def test_concurrent_edits_restarts_or_new_try_on_cannot_display_stale_scene(self):
        for key, value in [('runtime_pid',1235), ('history_lane','another'),
                           ('appearance_sha256','b'*64), ('inspected_form_flags',4),
                           ('pending_preview','c'*32), ('ok',False)]:
            current = copy.deepcopy(self.selection); current[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError,'no stale scene'):
                verify_selection(self.selection,current,self.snapshot)

    def test_removed_or_reordered_outfit_cannot_display_stale_scene(self):
        for outfits in ([],[dict(outfit_id='790')]):
            current = dict(self.selection,outfit_inventory=outfits)
            with self.subTest(outfits=outfits), self.assertRaisesRegex(ValueError,'outfit changed'):
                verify_selection(self.selection,current,self.snapshot)

    def test_prepared_wardrobe_uses_its_own_outfit_identity_without_changing_accepted_inventory(self):
        selection=dict(self.selection,pending_preview='c'*32,preview_outfit_inventory=[dict(outfit_id='990')])
        snapshot=dict(self.snapshot,outfit_id='990',preview_id='c'*32)
        verify_selection(selection,copy.deepcopy(selection),snapshot)
        self.assertEqual(selection['outfit_inventory'][0]['outfit_id'],'789')
        with self.assertRaisesRegex(ValueError,'identity changed'):
            verify_selection(selection,selection,dict(snapshot,preview_id='d'*32))
