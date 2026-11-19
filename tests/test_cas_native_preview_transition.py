"""Optional current-package proof of the exact native preview guard.

Read-only: no compiler, process handle, game/profile action or package writer.
The unpatched predecessor comes from the production contract's full rollback.
"""
from pathlib import Path
import json,os,sys,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import cas_preview_transition as p
import cas_catalog_binding as b
import cas_cell_attach as attach
import cas_ui_build as ui
import dbpf_build,maru_companion
EXPLICIT=os.environ.get('APEX_CAS_PREVIEW_PACKAGE')
PACKAGE=Path(EXPLICIT) if EXPLICIT else ROOT/'dist/candidate/ApexCASBridge.package'
MANIFEST=Path(str(PACKAGE)+'.manifest.json')

@unittest.skipUnless(PACKAGE.is_file() and MANIFEST.is_file(),'Current CAS package and its manifest required')
class NativePreviewTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  info=json.loads(MANIFEST.read_text(encoding='utf-8'));contract=info.get('preview_transition_native_bytecode_contract')
  if contract is None:
   if EXPLICIT:raise AssertionError('Explicit current package lacks the native preview contract')
   raise unittest.SkipTest('Current package predates the native preview stage')
  cls.final=dbpf_build.read(PACKAGE.read_bytes())[maru_companion.CUSTOMIZER]
  if p.verify_contract(contract,cls.final) is not True:raise AssertionError('Current native preview continuation failed')
  cls.proof=contract['preview_transition_contract']
  cls.original=p.reconstruct_previous(cls.final,cls.proof)
  prefix,raw=b._abc_payload(cls.original);cls.a=b._ABC(raw).parse()
  row=cls.a.named('OnLeaveState')[2];body=row['value'];cls.expected=p.expected_code(cls.a,body)
  code=p.instructions(body['code'])
  setters=[i for i,(_,_,op,args) in enumerate(code) if op==0x61 and cls.a.string(cls.a.pool(6,args[0])['name'])=='TattooMode']
  if len(setters)!=1:raise AssertionError('Exact native false-setter boundary differs')
  setter=setters[0];cls.guard_start=code[setter-2][0];cls.setter_bytes=code[setter][1]-cls.guard_start
  cls.guard=cls.expected[cls.guard_start:cls.guard_start+len(cls.expected)-len(body['code'])]
  cls.previous_code=body['code'];cls.raw=b._abc_payload(cls.final)[1]
 def run_guard(self,next_name,ui_flag,native_flag):
  code=p.instructions(self.guard);addresses={r[0]:n for n,r in enumerate(code)}
  addresses[len(self.guard)]=len(code);stack=[];pc=0;calls=0
  for _ in range(120):
   if pc>=len(code):return False,calls
   start,end,op,args=code[pc];pc+=1
   if op==0x60:stack.append(('class',self.a.string(self.a.pool(6,args[0])['name'])))
   elif op==0xd0:stack.append(('this',None))
   elif op==0x2c:stack.append(self.a.string(args[0]))
   elif op==0x26:stack.append(True)
   elif op==0x66:
    owner=stack.pop();name=self.a.string(self.a.pool(6,args[0])['name'])
    if name=='TattooMode':self.assertEqual(owner[1],'CASStateData');stack.append(ui_flag)
    elif name=='mNextState':self.assertEqual(owner[0],'this');stack.append(next_name)
    else:self.assertEqual(owner[1],'MenuState');stack.append(name)
   elif op==0x46:
    self.assertEqual(self.a.string(self.a.pool(6,args[0])['name']),'CallGameService');self.assertEqual(args[1],1)
    self.assertEqual(stack.pop(),'GetIsTattooModeEnabled');self.assertEqual(stack.pop(),('class','CommunicationManager'))
    calls+=1;stack.append(native_flag)
   elif op==0x12:
    if not stack.pop():pc=addresses[end+args[0]]
   elif op in (0x13,0x1a):
    right=stack.pop();left=stack.pop();equal=(type(left)is type(right) and left==right)
    branch=equal if op==0x13 else not equal
    if branch:
     target=end+args[0]
     if target==len(self.guard)+self.setter_bytes:
      self.assertEqual(stack,[]);return True,calls
     pc=addresses[target]
   else:self.fail('Unreviewed guard instruction '+hex(op))
  self.fail('Native preview guard did not terminate')
 def test_all_eight_directed_transitions_require_both_actual_preview_flags(self):
  for current in p.CATEGORIES:
   for target in p.CATEGORIES:
    for ui_flag,native_flag in ((True,True),(True,False),(False,True),(False,False)):
     with self.subTest(current=current,target=target,ui=ui_flag,native=native_flag):
      skip,calls=self.run_guard(target,ui_flag,native_flag)
      self.assertEqual(skip,ui_flag and native_flag);self.assertEqual(calls,int(ui_flag))
 def test_unknown_or_non_boolean_native_query_falls_back_to_original_setter(self):
  for native in (None,0,1,'true',[],{}):
   with self.subTest(native=native):self.assertEqual(self.run_guard(p.CATEGORIES[0],True,native),(False,1))
 def test_real_exits_and_nonpreview_categories_keep_original_setter(self):
  for target in ('NONE','PROFILE_BODY','CLOTHING_HAIR','CLOTHING_LOOKS','PROFILE_HEAD_EYES','unknown',None):
   for native in (True,False):
    with self.subTest(target=target,native=native):self.assertEqual(self.run_guard(target,True,native),(False,1))
 def test_full_raw_rollback_and_all_native_branch_edges_remain_exact(self):
  self.assertEqual(p.reconstruct_previous(self.final,self.proof),self.original)
  self.assertGreater(len(self.guard),0)
  self.assertEqual(len(self.expected)-len(self.previous_code),len(self.guard))
 def test_mutated_query_guard_and_unowned_native_context_are_refused(self):
  a=b._ABC(self.raw).parse();row=a.named('OnLeaveState')[2]
  at=self.raw.index(self.expected,row['start'],row['end'])
  prefix=b._abc_payload(self.final)[0]
  for offset in (0,self.guard_start,self.guard_start+1,self.guard_start+len(self.guard)//2,self.guard_start+len(self.guard)-1,len(self.expected)-1):
   bad=bytearray(self.raw);bad[at+offset]^=1
   with self.subTest(offset=offset),self.assertRaises(ValueError):p.reconstruct_previous(ui.replace_payload(self.final,prefix+bytes(bad)),self.proof)
  context=a.named('OnEnterState')[2];code=context['value']['code'];position=self.raw.index(code,context['start'],context['end'])
  bad=bytearray(self.raw);bad[position]^=1
  with self.assertRaises(ValueError):p.reconstruct_previous(ui.replace_payload(self.final,prefix+bytes(bad)),self.proof)
if __name__=='__main__':unittest.main()
