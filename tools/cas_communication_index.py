"""Authenticated CAS-library listener membership acceleration.

Only Apex helper bodies live here. Private pinned native sources are compiled
locally; the postpass retains original dispatch, array order and removal bodies.
No service/timer/IO runs in the adapter. GetFunctions permanently disables the
index before exposing the original mutable array and WidgetFunction records.
"""
from pathlib import Path
import hashlib
import json
import os
import subprocess

ROOT=Path(__file__).resolve().parents[1]
TARGET='olympus.io.CommunicationObject'
PROVIDERS={
    '6ddb983fee2bd284a2b7efec155e1544bfe99d27f16d4d28097bada25e1864f0':'62ECC59A:00000000:89D13757C58C2E05',
    '5f475a80a4f9c77f9a0439e133221a31f766cb929318f74191b4b9bad98e8cae':'62ECC59A:00000000:12272E1AC0C1F8E2',
}
HELPERS=r'''
      private var apexCommIndex:Dictionary;
      private var apexCommAliased:Boolean;
      private static var apexCommBuilt:uint;
      private static var apexCommCalls:uint;
      private static var apexCommAlias:uint;
      private static var apexCommEligibility:uint;
      private static var apexCommErrors:uint;

      public static function ApexCommIndexStats() : Object
      {
         return {scope:"native-listener-membership-index",indexes_built:apexCommBuilt,indexed_calls:apexCommCalls,
            alias_fallbacks:apexCommAlias,eligibility_fallbacks:apexCommEligibility,error_fallbacks:apexCommErrors,
            appearance_written:false};
      }

      private function ApexCommCanIndex(fn:Function) : Boolean
      {
         return fn!=null && !apexCommAliased;
      }

      private function ApexCommDisable(reason:String) : void
      {
         if(!apexCommAliased) {
            if(reason=="alias" && apexCommAlias<0xffffffff)apexCommAlias++;
            else if(reason=="eligibility" && apexCommEligibility<0xffffffff)apexCommEligibility++;
            else if(reason=="error" && apexCommErrors<0xffffffff)apexCommErrors++;
         }
         apexCommAliased=true;apexCommIndex=null;
      }

      private function ApexCommIndexedHas(fn:Function) : Boolean
      {
         try {
            if(apexCommIndex==null) {
               var made:Dictionary=new Dictionary(true);
               // GFx method closures must agree with native == semantics.
               // Test once, without invoking the method or any listener.
               var first:Function=this.HasFunction;
               var second:Function=this.HasFunction;
               made[first]=true;
               if(!(first==second) || !(first===second) || made[second]!==true) {
                  ApexCommDisable("eligibility");return HasFunction(fn);
               }
               delete made[first];
               for each(var row:WidgetFunction in mFunctions)
                  if(row.mFunction!=null)made[row.mFunction]=true;
               apexCommIndex=made;
               if(apexCommBuilt<0xffffffff)apexCommBuilt++;
            }
            if(apexCommCalls<0xffffffff)apexCommCalls++;
            return apexCommIndex[fn]===true;
         } catch(error:*) {
            ApexCommDisable("error");
            // The native HasFunction prefix now takes its untouched original
            // path. Metadata allocation failure cannot change listener results.
            return HasFunction(fn);
         }
      }

      private function ApexCommAdded(fn:Function) : void
      {
         if(apexCommIndex==null || apexCommAliased || fn==null)return;
         try {apexCommIndex[fn]=true;}
         catch(error:*) {ApexCommDisable("error");}
      }

      private function ApexCommRemoved(fn:Function) : void
      {
         if(apexCommIndex==null || apexCommAliased)return;
         try {
            if(fn!=null)delete apexCommIndex[fn];
         } catch(error:*) {ApexCommDisable("error");}
      }

      private function ApexCommExpose() : void
      {
         // Public GetFunctions leaks the live Array and mutable row objects.
         // Never trust this index again after that irreversible alias escape.
         ApexCommDisable("alias");
      }
'''

HELPERS_SHA256="05d5e56c0c60d922dbba5ab192971f0d5088c9a50f357f21b5644047df35bb94"

def digest(data):return hashlib.sha256(data).hexdigest()

def inject(source):
    if digest(HELPERS.encode())!=HELPERS_SHA256:
        raise ValueError("Reviewed listener helper source changed without requalification.")
    if 'apexCommIndex' in source or source.count('public final class CommunicationObject')!=1:
        raise ValueError('Pinned final communication class boundary differs.')
    if 'import flash.utils.Dictionary;' not in source:
        source=source.replace('   public final class CommunicationObject','   import flash.utils.Dictionary;\n\n   public final class CommunicationObject',1)
    end=source.rfind('\n   }')
    if end<0:raise ValueError('Communication class closing boundary differs.')
    return source[:end]+'\n'+HELPERS+source[end:]

def run(args,log):
    result=subprocess.run([str(x) for x in args],cwd=ROOT,capture_output=True,text=True,
        encoding='utf-8',errors='replace',timeout=240)
    Path(log).write_bytes((result.stdout+result.stderr).encode('utf-8'))
    if result.returncode:raise ValueError('Communication index build failed: '+(result.stdout+result.stderr)[-2400:])

def adapt(original_swf,baseline_swf,source_path,ffdec,work):
    original_swf,ffdec,work=map(Path,(original_swf,ffdec,work))
    provider=PROVIDERS.get(digest(original_swf.read_bytes()))
    if provider is None:raise ValueError('Unsupported communication library provider.')
    pinned=('tools/cas_communication_index.py','tools/CasCommunicationIndexPatch.java','tools/CasStructuralRolesPatch.java')
    source_pins={n:digest((ROOT/n).read_bytes()) for n in pinned}
    work.mkdir(parents=True,exist_ok=True)
    baseline=work/'baseline.swf';baseline.write_bytes(baseline_swf)
    if source_path is None:
        private=work/'private-source'
        run([ffdec,'-selectclass',TARGET,'-export','script',private,baseline],work/'export.log')
        source_path=private/'scripts/olympus/io/CommunicationObject.as'
    source=Path(source_path).read_text(encoding='utf-8-sig')
    owned=work/'CommunicationObject.as';owned.write_bytes(inject(source).encode('utf-8'))
    compiled=work/'compiled.swf'
    run([ffdec,'-importAssets','yes,local','-replace',baseline,compiled,TARGET,owned],work/'ffdec.log')
    classes=work/'classes';classes.mkdir(exist_ok=True)
    jar=ffdec.with_name('ffdec.jar')
    run(['javac','-cp',jar,'-d',classes,ROOT/'tools/CasStructuralRolesPatch.java',
        ROOT/'tools/CasCommunicationIndexPatch.java'],work/'javac.log')
    abc,proof=work/'retained.abc',work/'proof.json'
    run(['java','-cp',str(jar)+os.pathsep+str(classes),'CasCommunicationIndexPatch',
        original_swf,baseline,compiled,abc,proof],work/'transplant.log')
    data=abc.read_bytes();report=json.loads(proof.read_text())
    if report.get('ok')is not True or report.get('abc_sha256')!=digest(data):
        raise ValueError('Communication index proof differs.')
    if source_pins!={n:digest((ROOT/n).read_bytes()) for n in pinned}:
        raise ValueError('Listener postpass source changed during compilation; discard output.')
    report['source_sha256']=source_pins
    return data,report


def contract_digest(value):return digest(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("utf-8"))


def chain_adapter(retained_transaction_adapter, postproof, final_swf):
    """Retain the earlier grid proof as history, authenticate the final ABC."""
    from cas_ui_build import tags, unpack
    required=('whole_abc_rollback_verified','reviewed_helper_semantic_pins_verified',
              'protected_field_namespace_verified','bound_closure_runtime_eligibility_probe',
              'explicit_primitive_diagnostics','native_array_dispatch_order_retained',
              'public_alias_falls_back_to_original','deferred_removal_semantics_retained')
    if (not isinstance(retained_transaction_adapter,dict) or not isinstance(postproof,dict) or
            postproof.get('ok') is not True or any(postproof.get(k) is not True for k in required) or
            postproof.get('base_provider_sha256')!=retained_transaction_adapter.get('base_resource_sha256') or
            postproof.get('baseline_swf_sha256')!=retained_transaction_adapter.get('patched_resource_sha256') or
            postproof.get('baseline_abc_sha256')!=retained_transaction_adapter.get('native_bytecode_contract',{}).get('abc_sha256') or
            postproof.get('provider_resource_tgi')!=retained_transaction_adapter.get('native_bytecode_contract',{}).get('provider_resource_tgi') or
            postproof.get('changed_native_bodies')!=5 or postproof.get('appended_methods')!=7 or
            postproof.get('appended_fields')!=2 or postproof.get('appended_static_fields')!=5 or
            postproof.get('runtime_qualified') is not False or postproof.get('hitch_free_claimed') is not False):
        raise ValueError('Listener index cannot chain to the retained transaction proof.')
    pins=postproof.get('source_sha256')
    expected={n:digest((ROOT/n).read_bytes()) for n in
        ('tools/cas_communication_index.py','tools/CasCommunicationIndexPatch.java','tools/CasStructuralRolesPatch.java')}
    if pins!=expected:raise ValueError('Listener postpass source pins differ.')
    abc=[t[3] for t in tags(unpack(final_swf)[1]) if t[0]==82]
    if len(abc)!=1 or digest(abc[0][abc[0].index(b'\0',4)+1:])!=postproof.get('abc_sha256'):
        raise ValueError('Final provider is not the authenticated listener-index ABC.')
    return dict(base_resource_sha256=retained_transaction_adapter['base_resource_sha256'],
        patched_resource_sha256=digest(final_swf),
        retained_transaction_sha256=contract_digest(retained_transaction_adapter),
        postproof_sha256=contract_digest(postproof),
        retained_transaction_adapter=json.loads(json.dumps(retained_transaction_adapter)),
        communication_index_contract=json.loads(json.dumps(postproof)))


def verify_adapter(adapter,final_swf):
    if not isinstance(adapter,dict) or not isinstance(adapter.get('retained_transaction_adapter'),dict):
        raise ValueError('Historical grid transaction proof is absent.')
    if chain_adapter(adapter['retained_transaction_adapter'],adapter.get('communication_index_contract',{}),final_swf)!=adapter:
        raise ValueError('Final communication provider proof differs.')
    return True
