"""Actual retained providers: no proof flag can authorize different ABC bytes."""
from pathlib import Path
import copy,json,unittest,sys,os
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import cas_grid_presentation as v
from cas_ui_build import replace_payload
FIXTURE=os.environ.get('APEX_CAS_PRESENTATION_FIXTURE_DIR')

@unittest.skipUnless(FIXTURE,'Set APEX_CAS_PRESENTATION_FIXTURE_DIR for retained native provider proofs.')
class PresentationChainTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  home=Path(FIXTURE);cls.report=json.loads((home/'portable-build-proof.json').read_text());cls.fixtures=[]
  for tgi,row in cls.report['providers'].items():
   work=home/row['adapter'];adapter=json.loads(work.read_text());final=(home/row['path']).read_bytes()
   stages=[]
   while 'presentation_contract' in adapter:
    mode=adapter['presentation_contract']['mode'];stages.append((mode,final,adapter));adapter,final=v.previous(adapter,final)
   cls.fixtures.extend(reversed(stages))
  cls.mode,cls.final,cls.adapter=next(row for row in cls.fixtures if row[0]=='grid')
 def changed(self):return copy.deepcopy(self.adapter)
 def refused(self,adapter,final=None):
  with self.assertRaises((ValueError,KeyError,IndexError,UnicodeError)):v.verify_adapter(adapter,self.final if final is None else final)
 def refresh(self,adapter,final):
  proof=adapter['presentation_contract'];proof['final_swf_sha256']=v.sha(final);proof['abc_sha256']=v.sha(v.binding._abc_payload(final)[1]);adapter['postproof_sha256']=v.comm.contract_digest(proof);adapter['patched_resource_sha256']=v.sha(final)
 def mutate_code(self,final,owner,name):
  prefix,raw=v.binding._abc_payload(final);a=v.ABC(raw).parse();row=v.named(a,owner,name)[1];code=row['value']['code'];at=raw.find(code,row['start'],row['end'])
  self.assertGreaterEqual(at,0);self.assertEqual(raw[at],0xd0)
  raw=raw[:at]+b'\xd1'+raw[at+1:];return replace_payload(final,prefix+raw)
 def test_all_five_actual_compiled_provider_stages_verify_full_prior_chain(self):
  self.assertEqual(len(self.fixtures),5)
  for mode,final,adapter in self.fixtures:
   with self.subTest(mode=mode,hash=v.sha(final)):
    self.assertIs(v.verify_adapter(adapter,final),True)
    p=adapter['presentation_contract'];old=v.reconstruct(final,p)
    self.assertEqual(v.sha(old),p['baseline_swf_sha256'])
    self.assertEqual(v.sha(v.binding._abc_payload(old)[1]),p['baseline_abc_sha256'])
 def test_all_required_proof_flags_are_strict_true(self):
  for key in ('whole_abc_rollback_verified','serialized_owned_bodies_verified','all_unowned_bodies_retained','native_protected_bindings_verified'):
   for value in (None,False,1,'true'):
    with self.subTest(key=key,value=value):
     a=self.changed();a['presentation_contract'][key]=value;self.refused(a)
 def test_exact_integer_counts_reject_boolean_and_downgrade(self):
  for key in ('replaced_owned_bodies','appended_methods','appended_fields','changed_original_native_bodies'):
   a=self.changed();a['presentation_contract'][key]=True;self.refused(a)
  a=self.changed();a['presentation_contract']['mode']='image';self.refused(a)
 def test_source_pins_missing_partial_or_modified_refused(self):
  for value in (None,{},dict(list(v.pins().items())[1:])):
   a=self.changed();a['presentation_contract']['source_sha256']=value;self.refused(a)
  a=self.changed();a['presentation_contract']['source_sha256'][next(iter(v.pins()))]='0'*64;self.refused(a)
 def test_final_resource_and_final_abc_hashes_both_required(self):
  for key in ('final_swf_sha256','abc_sha256'):
   a=self.changed();a['presentation_contract'][key]='0'*64;self.refused(a)
  a=self.changed();a['patched_resource_sha256']='0'*64;self.refused(a)
 def test_resealed_owned_code_corruption_cannot_hide_behind_advertised_hash(self):
  final=self.mutate_code(self.final,v.GRID,'ApexGridPresentationStart');a=self.changed();self.refresh(a,final);self.refused(a,final)
 def test_resealed_original_native_body_corruption_fails_complete_rollback(self):
  prefix,raw=v.binding._abc_payload(self.final);a=v.ABC(raw).parse();native=None
  for i in a.instances:
   if a.qname(i['name'])!='7:RecyclingGridLayout:22:olympus.layout':continue
   for t in i['traits']['rows']:
    if t['value']['flags']&15 not in (1,2,3):continue
    n=a.string(a.pool(6,t['value']['name'])['name'])
    if not n.startswith('Apex'):
     rows=[r for r in a.bodies['rows'] if r['value']['method']==t['value']['method']]
     if rows and rows[0]['value']['code'].startswith(b'\xd0'):native=n;break
  self.assertIsNotNone(native);final=self.mutate_code(self.final,v.GRID,native);adapter=self.changed();self.refresh(adapter,final);self.refused(adapter,final)
 def test_missing_helper_name_cannot_pass_even_when_all_hashes_resealed(self):
  prefix,raw=v.binding._abc_payload(self.final);name=b'ApexGridPresentationTexture';self.assertGreaterEqual(raw.count(name),1)
  raw=raw.replace(name,b'ApexGridPresentationTexturX');final=replace_payload(self.final,prefix+raw);a=self.changed();self.refresh(a,final);self.refused(a,final)
 def test_rollback_inventory_mutation_and_cross_method_target_refused(self):
  for mutate in ('missing','extra','target','poolbool','huge','trailing'):
   a=self.changed();d=a['presentation_contract']['rollback'];keys=list(d['bodies'])
   if mutate=='missing':del d['bodies'][keys[0]]
   elif mutate=='extra':d['bodies']['unknown']='00'
   elif mutate=='target':d['bodies'][keys[0]]=d['bodies'][keys[1]]
   elif mutate=='poolbool':d['pool_counts'][0]=True
   elif mutate=='huge':d['bodies'][keys[0]]='00'*100001
   else:d['bodies'][keys[0]]+='00'
   with self.subTest(mutate=mutate):self.refused(a)
 def test_prior_complete_adapter_and_prior_resource_identity_are_mandatory(self):
  a=self.changed();a['previous_stage_adapter']['previous_stage_adapter']['grid_pool_contract']['whole_abc_rollback_verified']=False;self.refused(a)
  a=self.changed();a['previous_stage_adapter']['patched_resource_sha256']='0'*64;self.refused(a)
  a=self.changed();del a['previous_stage_adapter'];self.refused(a)
 def test_image_helpers_have_same_strict_ownership_guards(self):
  _,final,a=next(row for row in self.fixtures if row[0]=='image')
  final=self.mutate_code(final,v.LOADER,'ApexImageReadyFor');a=copy.deepcopy(a);self.refresh(a,final);self.refused(a,final)
 def test_no_extra_adapter_fields_or_partial_reconstruction_proof_accepted(self):
  a=self.changed();a['unknown']='pretend complete';self.refused(a)
  a=self.changed();a['presentation_contract']['rollback']={'pool_counts':[0]*7,'bodies':{}};self.refused(a)

if __name__=='__main__':unittest.main()
