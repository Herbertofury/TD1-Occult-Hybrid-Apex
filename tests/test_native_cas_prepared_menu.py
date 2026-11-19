import copy
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core import native_cas_engine as engine


def status():
    return dict(ok=True,scope_id='a'*32,selection_enabled=True,members=[dict(sim_id='123',graph_generation=7,
        human_owner_id='native/1',logical_owner_ids={'1':'native/1','2':'active/2'},graph_selected_owner_id='active/2',
        separate_owners=[dict(owner_id=oid,native_kind=kind,ui_token=0x20000000+i) for i,(oid,kind) in enumerate(
            [('native/1',1),('native/2',2),('active/2',2),('ghost/manifested',1)])])])


class PreparedMenus(unittest.TestCase):
    def test_exact_read_only_projection_keeps_one_human_and_omits_backup_alias(self):
        before=status();original=copy.deepcopy(before);calls=[]
        def call(request):
            engine.argument(request);calls.append(request)
            out=copy.deepcopy(before);out['members'][0]['prepared_menu_owner_count']=3;return out
        result=engine._stage_member_menus(call,before,'a'*32)
        self.assertEqual(before,original);self.assertFalse(result['appearance_written']);self.assertEqual(len(calls),1)
        rows=calls[0]['pages'][0].split('|')[3].split(';')
        self.assertEqual({row.split(',')[0] for row in rows},{'native/1','active/2','ghost/manifested'})
        self.assertEqual(result['members'],[dict(sim_id='123',owners=3,pages=1)])

    def test_changed_scope_graph_token_roster_and_incomplete_native_menu_fail(self):
        for change in ('scope','generation','token','roster','count','inactive'):
            with self.subTest(change=change):
                before=status()
                def call(request):
                    out=copy.deepcopy(before);out['members'][0]['prepared_menu_owner_count']=3
                    if change=='scope':out['scope_id']='b'*32
                    elif change=='generation':out['members'][0]['graph_generation']+=1
                    elif change=='token':out['members'][0]['separate_owners'][0]['ui_token']+=1
                    elif change=='roster':out['members']=[]
                    elif change=='count':out['members'][0]['prepared_menu_owner_count']=2
                    elif change=='inactive':out['selection_enabled']=False
                    return out
                with self.assertRaises(ValueError):engine._stage_member_menus(call,before,'a'*32)

    def test_untyped_or_unbounded_staging_is_rejected_before_native_call(self):
        base=dict(operation='menu-stage',scope_id='a'*32,sim_id='123',pages=['OWNERS|0|1|bounded'])
        engine.argument(base)
        for patch in (dict(sim_id=True),dict(pages=[]),dict(pages=[True]),dict(pages=['x\n']),dict(pages=['x'*131073]),dict(pages=['x']*65),dict(extra=True)):
            with self.subTest(patch=patch),self.assertRaises(ValueError):engine.argument(dict(base,**patch))


if __name__=='__main__':unittest.main()
