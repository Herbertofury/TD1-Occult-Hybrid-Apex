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

    def test_owner_can_remain_unchanged_while_assembly_runs(self):
        verify_selection(self.selection, copy.deepcopy(self.selection), self.snapshot)

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
