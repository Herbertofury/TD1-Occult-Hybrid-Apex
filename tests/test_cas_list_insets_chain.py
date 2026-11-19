"""Strict current-terminal, bytecode, native-field and recursive rollback gates."""
from pathlib import Path
import copy,hashlib,json,os,sys,unittest
H=Path(__file__).resolve().parents[1];R=next(p for p in(H,*H.parents)if(p/'tools/dbpf_build.py').is_file())
SOURCE=Path(os.environ.get('APEX_LIST_INSETS_SOURCE_ROOT',H if(H/'tools/cas_list_insets.py').is_file()else R))
F=Path(os.environ['APEX_LIST_INSETS_FIXTURE_DIR'])if os.environ.get('APEX_LIST_INSETS_FIXTURE_DIR')else H/'compiled'
sys.path[:0]=[str(SOURCE/'tools'),str(R/'tools')]
import cas_list_insets as m,cas_catalog_binding as binding,cas_ui_build as ui,cas_communication_index as comm

@unittest.skipUnless((F/'contract.json').is_file(),'Set APEX_LIST_INSETS_FIXTURE_DIR for exact compiled qualification')
class ListInsetChainTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.c=json.loads((F/'contract.json').read_text());cls.final=(F/'final.swf').read_bytes();cls.base=(F/'baseline.swf').read_bytes()
 def changed(self,edit):
  c=copy.deepcopy(self.c);prefix,raw=binding._abc_payload(self.final);a=m.ABC(raw).parse();at,old,new=edit(a,raw);assert raw[at:at+len(old)]==old
  raw=raw[:at]+new+raw[at+len(old):];final=ui.replace_payload(self.final,prefix+raw)
  p=c[m.CONTRACT];p['final_swf_sha256']=m.sha(final);p['abc_sha256']=m.sha(raw);c['final_swf_sha256']=m.sha(final);c['postproof_sha256']=comm.contract_digest(p)
  return c,final
 def test_exact_current_workflow_chain_and_all_raw_abc_bytes_restore(self):
  self.assertTrue(m.verify_main(self.c,self.final));prior,base=m.historical(self.c,self.final)
  self.assertEqual(base,self.base);self.assertTrue(m.previous.verify_main(prior,base));self.assertEqual(m.sha(base),'ab98d692e5261d2b86de077ccc22f4ccd2e0200fee07b59accbe37a6b178f213')
 def test_native_body_accounting_and_original_constructors_are_truthful(self):
  p=self.c[m.CONTRACT];self.assertEqual({n:p[n]for n in('changed_original_native_bodies','replaced_owned_bodies','appended_methods','appended_fields')},{'changed_original_native_bodies':4,'replaced_owned_bodies':5,'appended_methods':14,'appended_fields':3});self.assertTrue(p['constructors_retained'])
 def test_missing_proof_stale_current_sources_and_downgrade_reject(self):
  for key in('source_sha256','rollback','native_protected_bindings_verified','constructors_retained'):
   c=copy.deepcopy(self.c);del c[m.CONTRACT][key]
   with self.assertRaises(ValueError):m.verify_main(c,self.final)
  c=copy.deepcopy(self.c);c['previous_stage_contract']=c['previous_stage_contract']['previous_stage_contract']
  with self.assertRaises(ValueError):m.verify_main(c,self.final)
 def test_updated_outer_hash_does_not_accept_changed_geometry_guard_cfg(self):
  def edit(a,raw):
   t,row=m.named(a,m.MAIN,False,'ApexCatalogListApply');b=row['value'];code=a.instructions(b['code']);op=next(v for v in code if v[2]in(0x11,0x12));at=raw.index(b['code'],row['start'],row['end'])+op[0];return at,bytes([op[2]]),bytes([0x12 if op[2]==0x11 else 0x11])
  c,raw=self.changed(edit)
  with self.assertRaisesRegex(ValueError,'semantic/CFG'):m.verify_main(c,raw)
 def test_unchanged_constructor_corruption_fails_complete_predecessor(self):
  def edit(a,raw):
   ns,leaf=m.CATALOG.rsplit('.',1);ins=next(v for v in a.instances if a.qname(v['name'])=='7:'+leaf+':22:'+ns);row=next(v for v in a.bodies['rows']if v['value']['method']==ins['init']);b=row['value'];at=raw.index(b['code'],row['start'],row['end']);self.assertEqual(raw[at],0xd0);return at,b'\xd0',b'\xd1'
  c,raw=self.changed(edit)
  with self.assertRaisesRegex(ValueError,'original bytes'):m.verify_main(c,raw)
 def test_public_native_witness_cannot_lose_final_trait(self):
  def edit(a,raw):
   t,row=m.named(a,m.CATALOG,False,'ApexRawListGeneration');reader=m.ABC(raw[t['start']:t['end']]);reader.u30();at=t['start']+reader.at;return at,b'\x11',b'\x01'
  c,raw=self.changed(edit)
  with self.assertRaisesRegex(ValueError,'callable suffix/namespace'):m.verify_main(c,raw)
 def test_private_static_ui_slot_cannot_be_retyped_or_renumbered(self):
  def edit(a,raw):
   t=m.owner_rows(a,m.BODY,True)['rows'][-1];reader=m.ABC(raw[t['start']:t['end']]);reader.u30();reader.byte();at=t['start']+reader.at;self.assertEqual(raw[at],41);return at,b'\x29',b'\x28'
  c,raw=self.changed(edit)
  with self.assertRaisesRegex(ValueError,'metadata slot'):m.verify_main(c,raw)
 def test_original_native_body_inventory_cannot_omit_restore_or_refresh(self):
  for key in(m.CATALOG+'/RefreshLayout',m.BODY+'/RestoreList'):
   c=copy.deepcopy(self.c);del c[m.CONTRACT]['rollback']['bodies'][key]
   with self.assertRaisesRegex(ValueError,'rollback inventory'):m.verify_main(c,self.final)

if __name__=='__main__':unittest.main()
