"""Run the actual binding receipt AS against native-operation boundary mocks."""
import copy
import json
from pathlib import Path
import re
import shutil
import os
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import cas_catalog_binding as binding
import cas_communication_index as comm
from cas_main_chain_fixtures import READY, current_main


def javascript():
    source=binding.HELPERS+binding.OBSERVER;functions=[]
    for m in re.finditer(r'private function (\w+)\(([^)]*)\)\s*:\s*\w+\s*\{',source):
        end,depth=m.end(),1
        while depth:
            depth+=(source[end]=='{')-(source[end]=='}');end+=1
        body=source[m.end():end-1]
        body=re.sub(r'\b(var\s+\w+)\s*:\s*[\w.]+',r'\1',body)
        params=re.sub(r':\s*[\w.]+','',m.group(2))
        functions.append('Binding.prototype.'+m.group(1)+'=function('+params+'){with(this){'+body+'}};')
    if len(functions)!=3:raise AssertionError('Expected exact width, native wrapper and observer production AS')
    return '\n'.join(functions)


MOCK=r'''
const assert=require('node:assert/strict');const int=x=>Number(x)|0;
const CASCustomizerTunables={PANEL_SCREEN_OFFSET_X:15};
class Binding {
 constructor(){
  this.stage={};this.mLayerPanels={};this.mCurrSimInfo={simId:'arbitrary-member-001'};this.mCurrState=123;
  this.mcClothingPanel={visible:true,stage:this.stage,mcTileList:{mGridLayout:{}},mcPanelBackground:{width:706}};
  this.mCurrentPanel=this.mcClothingPanel;this.apexCatalogSignature='current-fit:12';
  this.apexCardGeometry={panel:this.mCurrentPanel,grid:this.mCurrentPanel.mcTileList.mGridLayout,applying:false};
  this.apexCatalogPrefs={columns:12};this.apexCardPrefs={scale:1,gap_x:4,gap_y:4};
  this.apexColumns={preferred_width:0};
  this.mcBodyModPanel=null;this.mcFaceModPanel=null;this.mcGenericCatalogPanel=null;
  this.mcFeaturedFaceLookPanel=null;this.mcSkinColorPanel=null;
  this.apexCardLayout={width:706,requested_columns:12,requested_scale:1,requested_gap_x:4,gap_y:4};
  this.apexCatalogBinding=null;this.apexCatalogBindingDirty=false;this.apexCatalogBoundWidth=-1;this.calls=[];this.hook=null;
 }
 BindDisplayObjectToSim(...args){this.calls.push(args);if(this.hook)this.hook();}
 apply(){let p=this.apexCatalogBinding;let width=this.mCurrentPanel===this.mcClothingPanel?this.apexCardLayout.width:262;
  if(p&&(this.apexCatalogBindingDirty||width!==this.apexCatalogBoundWidth)){
   this.BindDisplayObjectToSim(this.mLayerPanels,p.view,p.screen+15,Math.max(p.maximum,width+12));
   this.apexCatalogBoundWidth=width;this.apexCatalogBindingDirty=false;
  }
 }
}
function message(){return {view_x_offset:5,screen_x_offset:10,screen_x_max:262};}
function native(r,m,legend=0){r.ApexCatalogNativeBinding(r.mLayerPanels,m.view_x_offset,m.screen_x_offset+15,m.screen_x_max+legend,m);}
function dispatch(r,m,legend=0){native(r,m,legend);r.ApexCatalogObserveBinding(m);r.apply();}
'''


@unittest.skipUnless(shutil.which('node'),'Node required for actual AS behavior fixture')
class BindingExecutionTests(unittest.TestCase):
    def run_case(self,source):
        r=subprocess.run(['node','-'],input=MOCK+'\n'+javascript()+'\n'+source,capture_output=True,text=True,timeout=20)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)

    def test_one_real_native_bind_for_each_coherent_message_and_no_receipt_survives_consumption(self):
        self.run_case('''
const r=new Binding();for(let i=0;i<100;i++){
 r.mCurrSimInfo.simId='arbitrary-member-'+i;dispatch(r,message());
 assert.equal(r.calls.length,i+1);assert.deepEqual(r.calls[i],[r.mLayerPanels,5,25,718]);
 assert.equal(r.apexCatalogBindingDirty,false);assert.equal(r.apexCatalogBoundWidth,706);
 assert.deepEqual(Object.keys(r.apexCatalogBinding).sort(),['maximum','native_binding_applied','native_binding_width','screen','view']);
 assert.equal(r.apexCatalogBinding.native_binding_applied,true);assert.equal(r.apexCardGeometry.binding_receipt,undefined);
}
''')

    def test_unmeasured_or_changed_preferences_retain_native_call_and_necessary_later_correction(self):
        self.run_case('''
for(const change of [r=>r.apexCardLayout=null,r=>r.apexCardGeometry=null,r=>r.apexCatalogSignature='',
 r=>r.apexCardGeometry.applying=true,r=>r.apexCatalogPrefs.columns=24,r=>r.apexCardPrefs.scale=.25,
 r=>r.apexCardPrefs.gap_x=8,r=>r.apexCardPrefs.gap_y=9,r=>r.mcClothingPanel.mcPanelBackground.width=300,
 r=>r.mcClothingPanel.mcPanelBackground.width=NaN,r=>r.mcClothingPanel.mcPanelBackground.width=Infinity,
 r=>r.apexCardGeometry.grid={},r=>r.mcClothingPanel.stage={}]){
 const r=new Binding();change(r);const m=message();native(r,m);assert.deepEqual(r.calls[0],[r.mLayerPanels,5,25,262]);
 r.ApexCatalogObserveBinding(m);assert.equal(r.apexCatalogBindingDirty,true);
}
const r=new Binding();r.apexCardGeometry=null;const m=message();native(r,m);r.ApexCatalogObserveBinding(m);
r.apexCardGeometry={panel:r.mCurrentPanel,grid:r.mCurrentPanel.mcTileList.mGridLayout};r.apply();
assert.equal(r.calls.length,2);assert.equal(r.calls[1][3],718);
''')

    def test_body_hidden_foreign_display_and_different_message_never_suppress_existing_correction(self):
        self.run_case('''
for(const change of [r=>r.mCurrentPanel={},r=>r.mcClothingPanel.visible=false]){
 const r=new Binding();change(r);const m=message();native(r,m);r.ApexCatalogObserveBinding(m);
 assert.equal(r.calls[0][3],262);assert.equal(r.apexCatalogBindingDirty,true);
}
const r=new Binding(),m=message();native(r,m);r.ApexCatalogObserveBinding({...m});assert.equal(r.apexCatalogBindingDirty,true);
r.apply();assert.equal(r.calls.length,2);
const q=new Binding();q.ApexCatalogNativeBinding({},5,25,262,message());assert.equal(q.calls[0][3],262);assert.equal(q.apexCatalogBinding,null);
''')

    def test_native_reentry_context_change_or_mutated_payload_does_not_publish_authority(self):
        self.run_case('''
for(const change of [r=>r.mCurrSimInfo.simId='other',r=>r.mCurrState=7,r=>r.apexCatalogSignature='changed',
 r=>r.mcClothingPanel.mcPanelBackground.width=705,r=>r.mCurrentPanel={},r=>r.apexCardGeometry.grid={}]){
 const r=new Binding(),m=message();r.hook=()=>change(r);native(r,m);r.hook=null;r.ApexCatalogObserveBinding(m);
 assert.equal(r.apexCatalogBindingDirty,true);
}
const r=new Binding(),m=message();native(r,m);m.view_x_offset=6;r.ApexCatalogObserveBinding(m);assert.equal(r.apexCatalogBindingDirty,true);
''')

    def test_console_lower_bound_is_preserved_and_each_future_dispatch_rebinds_even_same_object(self):
        self.run_case('''
const r=new Binding(),m=message();m.screen_x_max=1000;
for(let i=0;i<5;i++){dispatch(r,m,40);assert.equal(r.calls.length,i+1);assert.equal(r.calls[i][3],1040);assert.equal(r.apexCatalogBinding.maximum,1040);}
r.apexCardPrefs.scale=.2;r.apply();assert.equal(r.calls.length,5);
''')

    def test_native_throw_preserves_failure_and_revokes_older_exact_payload_receipt(self):
        self.run_case('''
const r=new Binding(),m=message();native(r,m);assert.equal(r.apexCardGeometry.binding_receipt.native_message,m);
assert.equal(r.apexCatalogBinding,null);
r.hook=()=>{throw new Error('native refusal');};assert.throws(()=>native(r,m),/native refusal/);
assert.equal(r.apexCardGeometry.binding_receipt,undefined);r.hook=null;r.ApexCatalogObserveBinding(m);
assert.equal(r.apexCatalogBindingDirty,true);
''')


WORK=ROOT/'.work/v336-catalog-binding'
@unittest.skipUnless(READY,'Current authenticated binding continuation required')
class BindingContinuationTests(unittest.TestCase):
    def fixture(self):return current_main('binding')[:2]

    def refresh(self,r):
        r['previous_stage_sha256']=comm.contract_digest(r['previous_stage_contract'])
        r['catalog_binding_contract']['previous_stage_sha256']=r['previous_stage_sha256']
        r['postproof_sha256']=comm.contract_digest(r['catalog_binding_contract'])

    def test_exact_final_bytes_and_prior_full_history_are_retained(self):
        r,b=self.fixture();self.assertTrue(binding.verify_contract(r,b));self.assertIs(r['catalog_binding_contract']['runtime_qualified'],False)
        self.assertEqual(binding.reconstruct_previous(b,r['catalog_binding_contract']),current_main('binding')[2])

    def test_current_history_is_dynamic_but_obsolete_source_evidence_cannot_be_adopted(self):
        r,b,prior=current_main('binding')
        self.assertTrue(binding.verify_contract(r,b))
        self.assertEqual(binding.reconstruct_previous(b,r['catalog_binding_contract']),prior)
        self.assertTrue(binding.attach.verify_contract(r['previous_stage_contract'],prior))
        # A different proof source cannot be promoted by rewriting its outer
        # digest. Old fixture paths/final hashes are not an admission allowlist.
        stale=copy.deepcopy(r)
        stale['catalog_binding_contract']['source_sha256']['tools/cas_catalog_binding.py']='0'*64
        self.refresh(stale)
        with self.assertRaises(ValueError):binding.verify_contract(stale,b)

    @unittest.skipUnless(shutil.which('javac'),'JDK required for compiled corruption fixture')
    def test_serialized_bytecode_projection_and_metadata_corruptions(self):
        with tempfile.TemporaryDirectory(prefix='apex-native-binding-') as work:
            record,final,prior=current_main('binding')
            before_path=Path(work)/'previous.swf';final_path=Path(work)/'final.swf'
            before_path.write_bytes(prior);final_path.write_bytes(final)
            jar=ROOT/'.work/research/ffdec/ffdec.jar'
            r=subprocess.run(['javac','-cp',str(jar),'-d',work,str(ROOT/'tools/CasStructuralRolesPatch.java'),
                str(ROOT/'tools/CasCommunicationIndexPatch.java'),str(ROOT/'tools/CasCatalogBindingPatch.java'),
                str(ROOT/'tests/CasCatalogBindingBytecodeFixtures.java')],capture_output=True,text=True,timeout=45)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            r=subprocess.run(['java','-cp',str(jar)+os.pathsep+work,'CasCatalogBindingBytecodeFixtures',
                str(before_path),str(final_path)],capture_output=True,text=True,timeout=45)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr[-2000:]);self.assertEqual(r.stdout.count('PASS '),13)

    def test_forged_counts_booleans_sources_baseline_history_and_runtime_claims_are_refused(self):
        original,b=self.fixture()
        changes=[('ok',1),('changed_native_bodies',True),('replaced_owned_bodies',2),('appended_methods',1),('appended_fields',False),
          ('native_first_bind_only_verified',False),('other_four_binds_retained',False),('whole_abc_rollback_verified',False),
          ('runtime_qualified',True),('performance_gain_claimed',True),('baseline_native_align_sha256','0'*64),('abc_sha256','0'*64)]
        for field,value in changes:
            r=copy.deepcopy(original);r['catalog_binding_contract'][field]=value;self.refresh(r)
            with self.subTest(field=field),self.assertRaises(ValueError):binding.verify_contract(r,b)
        r=copy.deepcopy(original);r['previous_stage_contract']['previous_chain']['native_bytecode_contract']['ok']=False;self.refresh(r)
        with self.assertRaises(ValueError):binding.verify_contract(r,b)
        for source in binding.SOURCES:
            r=copy.deepcopy(original);r['catalog_binding_contract']['source_sha256'][source]='0'*64;self.refresh(r)
            with self.subTest(source=source),self.assertRaises(ValueError):binding.verify_contract(r,b)
        with self.assertRaises(ValueError):binding.verify_contract(original,b[:-1]+bytes([b[-1]^1]))

    def test_rehashed_final_native_owned_and_unowned_corruption_is_refused_without_a_final_allowlist(self):
        import cas_ui_build as ui
        original,b=self.fixture();prefix,abc=binding._abc_payload(b);a=binding._ABC(abc).parse()
        for name in ('HandleAlignToContextMenu','ApexCatalogNativeBinding','Initialize'):
            row=a.named(name)[2];reader=binding.attach._ABCReader(abc);reader.at=row['start'];reader.u30()
            for _ in range(4):reader.u30()
            reader.u30();code_at=reader.at;changed=bytearray(abc)
            if name=='HandleAlignToContextMenu':changed[code_at+77]=0xd2
            elif name=='ApexCatalogNativeBinding':
                candidate=next(x for x in a.instructions(row['value']['code']) if x[2]==0x24 and x[3]==[12]);changed[code_at+candidate[0]+1]=13
            else:changed[code_at]=0xd1
            damaged=ui.replace_payload(b,prefix+changed);r=copy.deepcopy(original)
            r['catalog_binding_contract']['abc_sha256']=binding.digest(changed);r['final_swf_sha256']=binding.digest(damaged);self.refresh(r)
            with self.subTest(method=name),self.assertRaises(ValueError):binding.verify_contract(r,damaged)
        for value in (True,-1,2**30):
            r=copy.deepcopy(original);r['catalog_binding_contract']['rollback']['pool_counts'][0]=value;self.refresh(r)
            with self.subTest(pool_count=value),self.assertRaises(ValueError):binding.verify_contract(r,b)
        with self.assertRaises(ValueError):binding._ABC(abc[:-1]).parse()
        with self.assertRaises(ValueError):binding._ABC(abc+b'\0').parse()


if __name__=='__main__':unittest.main()
