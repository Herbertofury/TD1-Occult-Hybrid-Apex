"""Optional authenticated compiled EOF/authority provider gates; no Game calls.

APEX_CAS_GRID_EOF_FIXTURE_DIR selects fixtures, never supplies authority. Every
resource is still reconstructed through the full production predecessor chain.
"""
from pathlib import Path
import copy,json,os,sys,unittest
REPO=next(p for p in Path(__file__).resolve().parents if(p/'tools/dbpf_build.py').is_file())
ROOT=Path(os.environ.get('APEX_GRID_EOF_SOURCE_ROOT',Path(__file__).resolve().parents[1])).resolve()
FRAME=Path(os.environ.get('APEX_FRAME_STATUS_SOURCE_ROOT',REPO)).resolve()
LOGICAL=Path(os.environ.get('APEX_LOGICAL_BANK_SOURCE_ROOT',REPO)).resolve()
sys.path[:0]=[str(ROOT/'tools'),str(FRAME/'tools'),str(LOGICAL/'tools'),str(REPO/'tools')]
import cas_grid_eof as stage,cas_catalog_binding as binding,cas_grid_presentation as presentation,cas_communication_index as comm
from cas_ui_build import replace_payload
FIXTURE=os.environ.get('APEX_CAS_GRID_EOF_FIXTURE_DIR')

@unittest.skipUnless(FIXTURE,'Set APEX_CAS_GRID_EOF_FIXTURE_DIR for authenticated compiled fixtures')
class EofAuthorityChainTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rows={}
  for suffix in('12272E1AC0C1F8E2','89D13757C58C2E05'):
   p=Path(FIXTURE)/suffix;cls.rows[suffix]=(json.loads((p/'contract.json').read_text()),(p/'final.swf').read_bytes(),(p/'baseline.swf').read_bytes())
 def rehash(self,c,raw):
  c=copy.deepcopy(c);p=c['eof_delta_contract'];p['abc_sha256']=stage.sha(binding._abc_payload(raw)[1]);p['final_swf_sha256']=stage.sha(raw);c['patched_resource_sha256']=stage.sha(raw);c['postproof_sha256']=comm.contract_digest(p);return c
 def test_two_complete_frame_predecessors_reconstruct_exactly(self):
  for name,(c,raw,base)in self.rows.items():
   with self.subTest(name=name):
    self.assertTrue(stage.verify_adapter(c,raw));prior,restored=stage.historical(c,raw);self.assertEqual(restored,base);self.assertEqual(prior,c['previous_stage_adapter'])
 def test_every_owned_and_native_unowned_body_rejects_rehashed_tampering(self):
  for resource,(c,final,_)in self.rows.items():
   prefix,raw=binding._abc_payload(final);a=stage.mechanics.ABC(raw).parse()
   for method in(*stage.stage.REPLACED,*stage.stage.ADDED,'ApexGridReady'):
    _,b=presentation.named(a,stage.GRID,method);at=raw.find(b['value']['code'],b['start'],b['end']);self.assertGreaterEqual(at,0)
    data=bytearray(raw);data[at]=0xd1 if data[at]==0xd0 else 0x27;changed=replace_payload(final,prefix+bytes(data))
    with self.subTest(resource=resource,method=method),self.assertRaises(ValueError):stage.verify_adapter(self.rehash(c,changed),changed)
 def test_counts_effect_claims_five_source_pins_and_slot_proof_are_mandatory(self):
  facts=[('source_sha256',{}),('rollback',{}),('appended_fields',0),('appended_methods',0),('replaced_owned_bodies',0),('changed_original_native_bodies',1),('whole_abc_rollback_verified',False),('activation_slot_receivers_verified',False),('slot_abi_audit',{}),('runtime_qualified',True),('performance_gain_claimed',True)]
  for name,(c,raw,_)in self.rows.items():
   for key,value in facts:
    bad=copy.deepcopy(c);bad['eof_delta_contract'][key]=value;bad['postproof_sha256']=comm.contract_digest(bad['eof_delta_contract'])
    with self.subTest(resource=name,key=key),self.assertRaises(ValueError):stage.verify_adapter(bad,raw)
   for missing in stage.SOURCES:
    bad=copy.deepcopy(c);del bad['eof_delta_contract']['source_sha256'][missing];bad['postproof_sha256']=comm.contract_digest(bad['eof_delta_contract'])
    with self.subTest(resource=name,missing=missing),self.assertRaises(ValueError):stage.verify_adapter(bad,raw)
 def test_exact_public_final_status_and_private_default_null_instance_slot(self):
  for name,(c,final,_)in self.rows.items():
   a=stage.mechanics.ABC(binding._abc_payload(final)[1]).parse();owner=next(i for i in a.instances if a.qname(i['name'])=='7:RecyclingGridLayout:22:olympus.layout')
   f=owner['traits']['rows'][-len(stage.stage.ADDED)-1]['value']
   self.assertEqual(f['flags'],0);self.assertEqual(f['slot'],0);self.assertEqual(f['value'],0)
   self.assertEqual(a.qname(f['type']),'7:Object:22:');self.assertEqual(a.qname(f['name']),'7:apexGridAuthority:5:olympus.layout:RecyclingGridLayout')
   t,_=presentation.named(a,stage.GRID,'ApexGridAuthorityStatus');self.assertEqual(t['value']['flags'],17);self.assertEqual(a.qname(t['value']['name']),'7:ApexGridAuthorityStatus:22:')
   # Rehashing cannot legitimize a different field type.
   prefix,raw=binding._abc_payload(final);row=owner['traits']['rows'][-len(stage.stage.ADDED)-1]
   old=raw[row['start']:row['end']];changed=stage.attach._u30(f['name'])+bytes([f['flags']])+stage.attach._u30(f['slot'])+stage.attach._u30(0)+stage.attach._u30(0)
   modified=replace_payload(final,prefix+raw[:row['start']]+changed+raw[row['end']:])
   with self.subTest(name=name),self.assertRaises(ValueError):stage.verify_adapter(self.rehash(c,modified),modified)
 def test_downgraded_predecessor_cross_provider_and_missing_pair_refuse(self):
  for name,(c,raw,_)in self.rows.items():
   bad=copy.deepcopy(c);bad['previous_stage_adapter']=bad['previous_stage_adapter']['previous_stage_adapter'];bad['previous_stage_sha256']=comm.contract_digest(bad['previous_stage_adapter'])
   with self.subTest(resource=name),self.assertRaises(ValueError):stage.verify_adapter(bad,raw)
  a,b=self.rows.values()
  with self.assertRaises(ValueError):stage.verify_adapter(a[0],b[1])
  with self.assertRaises(ValueError):stage.unwrap_providers({'62ECC59A:00000000:12272E1AC0C1F8E2':a[0]}, {})
 def info(self):
  import dbpf_build
  providers={'62ECC59A:00000000:'+n:r[0]for n,r in self.rows.items()};resources={(0x62ECC59A,0,int(n,16)):r[1]for n,r in self.rows.items()};resources[(1,0,99)]=b'unrelated exact bytes'
  return {'source_pins':stage.pins(),'grid_provider_adapters':providers,'companion_code_merge':{'grid_library_adapter':providers['62ECC59A:00000000:89D13757C58C2E05']},'patched_resources':{dbpf_build.tgi(k):stage.sha(v)for k,v in resources.items()}},resources
 def test_manifest_pair_unwrap_and_every_missing_pin_refusal(self):
  info,resources=self.info();changed,out=stage.unwrap_manifest(info,resources);self.assertEqual(out[(1,0,99)],resources[(1,0,99)])
  for name,(_,_,base)in self.rows.items():self.assertEqual(out[(0x62ECC59A,0,int(name,16))],base)
  for key in stage.SOURCES:
   bad=copy.deepcopy(info);del bad['source_pins'][key]
   with self.subTest(key=key),self.assertRaises(ValueError):stage.unwrap_manifest(bad,resources)

if __name__=='__main__':unittest.main()
