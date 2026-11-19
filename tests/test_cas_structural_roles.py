"""Execute production AS role bodies; optional private FFDec round-trip gate."""
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import cas_structural_roles as roles


def javascript(source, name):
    body = source.split('{', 1)[1].rsplit('}', 1)[0]
    body = re.sub(r'\b(var\s+\w+)\s*:\s*[\w.*]+', r'\1', body)
    return 'function ' + name + '(cell){' + body + '}\n'


@unittest.skipUnless(shutil.which('node'), 'Node required for actual AS body fixtures')
class StructuralRoleTests(unittest.TestCase):
    def case(self, source):
        harness = '''
const assert=require('node:assert/strict');let reads=0;
class Node {constructor(parent=null){this._parent=parent;this.hook=null;this.name='same';this.visible=true;}
 get parent(){reads++;if(this.hook)this.hook();return this._parent;}}
const stage=new Node(),host=new Node(stage),root=new Node(host),history=new Node(root),preview=new Node(root),current=new Node(root);
let r=[];r[0]=root;r[2]=history;r[25]=preview;r[40]=current;r[4]=r[26]={GetAllCells(){throw Error('vector scan forbidden');}};
const HistoryHost={dccHistoryRuntimeDrawer:r};
''' + javascript(roles.HELPER_METHOD, 'ApexCellRole') + javascript(roles.IS_CURRENT_METHOD, 'IsCurrent')
        result = subprocess.run(['node', '-e', harness + source], capture_output=True,
                                text=True, encoding='utf-8', timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_first_paint_and_all_roles_do_not_depend_on_vector_membership(self):
        self.case('''
for(const [owner,want] of [[history,1],[preview,2],[current,3],[host,0]]){
 const c=new Node(new Node(owner));assert.equal(ApexCellRole(c),want);assert.equal(IsCurrent(c),want===3);
}
assert.equal(ApexCellRole(new Node(new Node(root))),0);assert.equal(ApexCellRole(null),0);
''')

    def test_recycled_roles_and_reparented_ancestor_are_live_without_cache(self):
        self.case('''
const grid=new Node(history),cell=new Node(grid);assert.equal(ApexCellRole(cell),1);
for(const [owner,want] of [[preview,2],[current,3],[host,0],[history,1]]){
 grid._parent=owner;assert.equal(cell.parent,grid);assert.equal(ApexCellRole(cell),want);
}
root.visible=history.visible=false;assert.equal(ApexCellRole(cell),1);
''')

    def test_replaced_drawer_and_mid_walk_runtime_replacement_fail_closed(self):
        self.case('''
const grid=new Node(current),cell=new Node(grid),replacement=[];replacement[0]=new Node(host);replacement[40]=new Node(replacement[0]);
HistoryHost.dccHistoryRuntimeDrawer=replacement;assert.equal(ApexCellRole(cell),0);
HistoryHost.dccHistoryRuntimeDrawer=r;grid.hook=()=>HistoryHost.dccHistoryRuntimeDrawer=replacement;
assert.equal(ApexCellRole(cell),0);
''')

    def test_unattached_measurement_detached_owner_and_corrupt_chain_are_bounded(self):
        self.case('''
assert.equal(ApexCellRole(new Node()),0);const cell=new Node(current);root._parent=null;assert.equal(ApexCellRole(cell),0);
root._parent=host;const detached=new Node();current._parent=detached;assert.equal(ApexCellRole(cell),0);
const cycle=new Node();cycle._parent=cycle;reads=0;assert.equal(ApexCellRole(cycle),0);assert.ok(reads<=257);
''')


class SourceBoundaryTests(unittest.TestCase):
    def test_only_selected_predicate_and_one_helper_are_injected(self):
        source='''package dcc.history
{
   public final class CurrentOutfitUI
   {
      public static function IsCurrent(cell:Object) : Boolean
      {
         return false;
      }
      public static function Scale(cell:Object, fallback:Number) : Number
      {
         return fallback;
      }
      public static function Decorate(cell:Object, product:Object) : void
      {
         KeepEyeRestoreAndNativeCalls(cell,product);
      }
   }
}
'''
        result = roles.inject_current(source)
        start, end = roles.method_extent(source, '      public static function IsCurrent(')
        self.assertEqual(result.replace(roles.HELPER_METHOD, '').replace(roles.IS_CURRENT_METHOD, '<selected>'),
                         (source[:start] + '<selected>' + source[end:]).replace('\n   }', '\n\n   }', 1))
        self.assertEqual(result.count('function ApexCellRole('), 1)
        self.assertIn('KeepEyeRestoreAndNativeCalls(cell,product);', result)
        with self.assertRaises(ValueError):
            roles.inject_current(result)


@unittest.skipUnless(os.environ.get('APEX_PRIVATE_FFDEC_TESTS') == '1', 'Explicit private FFDec test opt-in')
class PrivateBytecodeTests(unittest.TestCase):
    def test_actual_transplant_and_serialized_adversarial_gates(self):
        donor = ROOT / '.work/research/maru-integrated/DynamicCASCustomizer.swf'
        baseline = ROOT / '.work/v326-structural-roles-baseline.swf'
        data, contract = roles.adapt(donor, baseline.read_bytes(),
            ROOT / '.work/research/maru-integrated/customizer/scripts',
            ROOT / '.work/research/ffdec/ffdec-cli.exe',
            ROOT / '.work/v326-structural-roles-production-test')
        self.assertEqual(roles.digest(data), contract['abc_sha256'])
        self.assertEqual(contract['unchanged_baseline_bodies'], contract['baseline_body_count'] - 2)
        self.assertTrue(contract['compiled_helper_control_flow_oracle'])
        self.assertTrue(contract['explicit_jump_switch_exception_fixtures'])
        self.assertTrue(contract['serialized_whole_abc_rollback_projection'])
        self.assertTrue(contract['unowned_corruption_rejected'])
        self.assertFalse(contract['runtime_verified'])
        import json
        import cas_ui_build
        info = json.loads((ROOT / 'dist/candidate/ApexCASBridge.package.manifest.json').read_text())
        self.assertEqual(info['patched_resource_sha256'], roles.digest(baseline.read_bytes()))
        native_tag = next(t[3] for t in cas_ui_build.tags(cas_ui_build.unpack(baseline.read_bytes())[1]) if t[0] == 82)
        final = cas_ui_build.replace_payload(baseline.read_bytes(), native_tag[:native_tag.index(b'\0', 4) + 1] + data)
        chained = roles.chain_contract(info['native_bytecode_contract'], contract, final)
        self.assertEqual(chained['unchanged_original_native_bodies_after_chain'], 2615)
        self.assertEqual(chained['base_donor_body_count'], 2650)
        self.assertEqual(roles.chain_contract(info['native_bytecode_contract'], chained, final), chained)
        with self.assertRaises(ValueError):
            roles.chain_contract(info['native_bytecode_contract'], contract, baseline.read_bytes())


if __name__ == '__main__':
    unittest.main()
