"""Explicit bounded native image-boundary diagnostics after frozen V333.

No cache, fidelity, load order or native callback behavior is replaced. Runtime
state contains only integers, booleans and primitive metric arrays, never widgets.
"""
import hashlib
import json
import os
from pathlib import Path

import cas_communication_index as comm

ROOT=Path(__file__).resolve().parents[1]
RESOURCE='olympus.controls.ImageResource'
LOADER='olympus.resources.ImageLoader'
SOURCES=('tools/cas_image_boundary_profile.py','tools/CasImageBoundaryProfilePatch.java',
         'tools/CasStructuralRolesPatch.java','tools/CasCommunicationIndexPatch.java')
BASELINES={
    '4864a5942a9d77c0ecca0ee1682ca53cdd302751872b4173ad69d17b3ef022bc':('62ECC59A:00000000:12272E1AC0C1F8E2','59c8a4219fff053dfb581f03dd8e2647cc759dea2bdc2927f17b587fce66a380','8a50114b70de19772e82b07a84eccfdfef57c99544e26058be821b43616e6b60'),
    'b71a66ed5a0d867de864bba8c58d847b306ce685a6169429034850c955e5372f':('62ECC59A:00000000:89D13757C58C2E05','1432ec78709280243b750571e069d4b842a79727d23472a01c2fc23df3d0e397','f96cc61772cab844674134092aac1dc35af81a7bb0e6eb606526136451cd67c9'),
    '373db1aa7a273c8ca7b9124a027d420deddebdf1815f3ca3cb48c4390d66e859':('62ECC59A:00000000:3FFE72432A703655','364096fcf14dc9e906bedaf1d98406e65a3be641363ad76fa20e7920b32be89d','580340489c9fef6e32e98c7faf9b570e36d24efa1c2c5e9bd3ba2047f2aedd60'),
}
RAW_PROVIDERS={
    '62ECC59A:00000000:12272E1AC0C1F8E2':'5f475a80a4f9c77f9a0439e133221a31f766cb929318f74191b4b9bad98e8cae',
    '62ECC59A:00000000:89D13757C58C2E05':'6ddb983fee2bd284a2b7efec155e1544bfe99d27f16d4d28097bada25e1864f0',
    '62ECC59A:00000000:3FFE72432A703655':'e79b3b65c8b6234c54d4a76f4c7a671f46ece7ddb9f6940bc5db312850fdef91',
}
FINALS={
    '62ECC59A:00000000:12272E1AC0C1F8E2':('00aa765a0826342498a8ef176a77d98bcd83bbec7beb5281bf953128bf647dc1','f8b2a3128d9bef85dd8beddd40a38d60e5b6c1502d71fed40a32e90972f030dd'),
    '62ECC59A:00000000:89D13757C58C2E05':('18544a2c85e5291d0d5becd03e275119c90dd61dff0b84132297b8e8bde5d3b4','dcb80046ba0c93b821e57c785e418ecff36c4a886b5c5dc2c9684f3e9537cacc'),
    '62ECC59A:00000000:3FFE72432A703655':('3dfb9eefd6861aa2460b668cd0a8f5a13b1118f1e883c323749181462b545e49','0f639ae22236da819b387d4b1f0758d3182cc7aa26d89e3762a04f926c1a7531'),
}
LOADER_HELPERS=r'''
      private static var apexImageTraceState:Object;
      private static var apexImageTraceAccepting:Boolean;
      private static var apexImageTraceFault:Boolean;
      private static var apexImageTraceRequested:int;

      public final function get ApexImageTraceActive() : Boolean
      {
         return apexImageTraceAccepting;
      }

      public final function ApexImageTraceEnable(budget:int) : Object
      {
         if(budget<0 || budget>4096)
            return {available:false,reason:"budget-out-of-range",appearance_written:false};
         apexImageTraceRequested=budget;
         apexImageTraceAccepting=false;
         if(budget>0) {
            var previous:Object=apexImageTraceState;
            apexImageTraceState={budget:budget,generation:previous==null?1:int(previous.generation)+1,
               started:0,completed:0,depth:0,max_depth:0,phases:[],times:[],
               counts:[0,0,0,0,0],totals:[0,0,0,0,0],maxima:[0,0,0,0,0]};
            apexImageTraceFault=false;
            apexImageTraceAccepting=true;
         }
         return this.ApexImageTraceStats();
      }

      public final function ApexImageTraceStats() : Object
      {
         var s:Object=apexImageTraceState;
         var names:Array=["get_rect","initialize","readd_load","cancel_load","asset_load"];
         var rows:Array=[];
         for(var i:int=0;i<5;i++)
            rows.push({phase:names[i],count:s==null?0:int(s.counts[i]),total_ms:s==null?0:Number(s.totals[i]),max_ms:s==null?0:Number(s.maxima[i])});
         return {available:true,provider_resource_tgi:"__PROVIDER__",scope:"native-image-boundary-profile",
            enabled:apexImageTraceAccepting,requested_budget:apexImageTraceRequested,
            budget:s==null?0:int(s.budget),generation:s==null?0:int(s.generation),
            started:s==null?0:int(s.started),completed:s==null?0:int(s.completed),
            open_depth:s==null?0:int(s.depth),max_depth:s==null?0:int(s.max_depth),
            diagnostic_error:apexImageTraceFault,phases:rows,record_limit:0,
            clock_resolution_ms:1,appearance_written:false};
      }

      public final function ApexImageTraceStamp(phase:int, entering:Boolean) : void
      {
         var s:Object=apexImageTraceState;
         if(s==null || apexImageTraceFault || phase<0 || phase>=5)return;
         var depth:int=int(s.depth);
         if(entering) {
            if(depth>=32) {apexImageTraceAccepting=false;apexImageTraceFault=true;return;}
            s.phases[depth]=phase;
            if(apexImageTraceAccepting && int(s.started)<int(s.budget)) {
               s.times[depth]=Number(uint(getTimer()));
               s.started=int(s.started)+1;
               if(int(s.started)>=int(s.budget))apexImageTraceAccepting=false;
            } else s.times[depth]=-1;
            s.depth=depth+1;
            if(int(s.depth)>int(s.max_depth))s.max_depth=int(s.depth);
            return;
         }
         depth--;
         if(depth<0 || int(s.phases[depth])!=phase) {apexImageTraceAccepting=false;apexImageTraceFault=true;return;}
         s.depth=depth;
         var start:Number=Number(s.times[depth]);
         if(start<0)return;
         var elapsed:uint=uint(uint(getTimer())-uint(start));
         s.counts[phase]=int(s.counts[phase])+1;
         s.totals[phase]=Number(s.totals[phase])+elapsed;
         if(elapsed>Number(s.maxima[phase]))s.maxima[phase]=elapsed;
         s.completed=int(s.completed)+1;
      }
'''
RESOURCE_HELPERS=r'''
      public final function ApexImageTraceEnable(budget:int) : Object
      {
         if(this.mLoader==null || !("ApexImageTraceEnable" in this.mLoader))
            return {available:false,reason:"loader-probe-unavailable",appearance_written:false};
         return this.mLoader.ApexImageTraceEnable(budget);
      }

      public final function ApexImageTraceStats() : Object
      {
         if(this.mLoader==null || !("ApexImageTraceStats" in this.mLoader))
            return {available:false,reason:"loader-probe-unavailable",appearance_written:false};
         return this.mLoader.ApexImageTraceStats();
      }
'''


def digest(data):return hashlib.sha256(data).hexdigest()


def inject(source,kind,tgi):
    target='class ImageLoader'if kind=='loader'else'class ImageResource'
    if source.count(target)!=1 or 'ApexImageTrace' in source:raise ValueError('Image helper class boundary differs.')
    if kind=='loader' and 'import flash.utils.getTimer;'not in source:
        source=source.replace('   public class ImageLoader','   import flash.utils.getTimer;\n\n   public class ImageLoader',1)
    at=source.rfind('\n   }')
    if at<0:raise ValueError('Image helper closing boundary differs.')
    return source[:at]+'\n'+(LOADER_HELPERS if kind=='loader'else RESOURCE_HELPERS).replace('__PROVIDER__',tgi)+source[at:]


def adapt(original_swf,baseline_swf,ffdec,work):
    original_swf,baseline_swf,ffdec,work=map(Path,(original_swf,baseline_swf,ffdec,work))
    expected=BASELINES.get(digest(baseline_swf.read_bytes()))
    if expected is None or digest(original_swf.read_bytes())!=RAW_PROVIDERS[expected[0]]:raise ValueError('Unsupported exact image profiler provider pair.')
    pins={n:digest((ROOT/n).read_bytes())for n in SOURCES};work.mkdir(parents=True,exist_ok=True);private=work/'private-source';incoming=baseline_swf
    for kind,target,relative in [('loader',LOADER,'olympus/resources/ImageLoader.as'),('resource',RESOURCE,'olympus/controls/ImageResource.as')]:
        comm.run([ffdec,'-selectclass',target,'-export','script',private,original_swf],work/(kind+'-export.log'))
        owned=work/('Apex-'+kind+'.as');owned.write_bytes(inject((private/'scripts'/relative).read_text(encoding='utf-8-sig'),kind,expected[0]).encode())
        compiled=work/('compiled-'+kind+'.swf');comm.run([ffdec,'-importAssets','yes,local','-replace',incoming,compiled,target,owned],work/(kind+'-compile.log'));incoming=compiled
    classes=work/'classes';classes.mkdir(exist_ok=True);jar=ffdec.with_name('ffdec.jar')
    comm.run(['javac','-cp',jar,'-d',classes,ROOT/'tools/CasStructuralRolesPatch.java',ROOT/'tools/CasCommunicationIndexPatch.java',ROOT/'tools/CasImageBoundaryProfilePatch.java'],work/'javac.log')
    abc,proof=work/'retained.abc',work/'proof.json'
    comm.run(['java','-cp',str(jar)+os.pathsep+str(classes),'CasImageBoundaryProfilePatch',baseline_swf,incoming,abc,proof],work/'transplant.log')
    data=abc.read_bytes();report=json.loads(proof.read_text())
    if report.get('ok')is not True or report.get('abc_sha256')!=digest(data):raise ValueError('Image profiler bytecode identity differs.')
    if pins!={n:digest((ROOT/n).read_bytes())for n in SOURCES}:raise ValueError('Image profiler source changed during compilation; discard output.')
    report['source_sha256']=pins;return data,report


def chain_adapter(previous_adapter,postproof,final_swf):
    from cas_ui_build import tags,unpack
    before=postproof.get('baseline_swf_sha256')if isinstance(postproof,dict)else None;expected=BASELINES.get(before)
    required=('whole_abc_rollback_verified','native_disabled_projection_verified','native_enabled_projection_verified','native_exceptions_not_intercepted',
              'actual_loader_instance_route_verified','disabled_no_allocation_clock_counter','bounded_primitive_state_verified','native_input_mode_oracle_verified')
    if (expected is None or postproof.get('ok')is not True or any(postproof.get(k)is not True for k in required) or
        postproof.get('provider_resource_tgi')!=expected[0] or postproof.get('baseline_abc_sha256')!=expected[1] or
        postproof.get('changed_native_bodies')!=3 or postproof.get('replaced_owned_button_bodies')!=1 or
        postproof.get('appended_methods')!=6 or postproof.get('appended_static_fields')!=4 or
        postproof.get('budget_limit')!=4096 or postproof.get('depth_limit')!=32 or postproof.get('record_limit')!=0 or
        postproof.get('runtime_qualified')is not False or postproof.get('optimization_claimed')is not False):raise ValueError('Image profiler contract differs.')
    if(not isinstance(previous_adapter,dict)or previous_adapter.get('patched_resource_sha256')!=before or comm.contract_digest(previous_adapter)!=expected[2]):raise ValueError('Image profiler prior stage differs.')
    if postproof.get('source_sha256')!={n:digest((ROOT/n).read_bytes())for n in SOURCES}:raise ValueError('Image profiler source pins differ.')
    if FINALS[expected[0]]!=(digest(final_swf),postproof.get('abc_sha256')):raise ValueError('Image profiler final bytes differ from the reviewed exact postpass.')
    abc=[x[3]for x in tags(unpack(final_swf)[1])if x[0]==82]
    if len(abc)!=1 or digest(abc[0][abc[0].index(b'\0',4)+1:])!=postproof.get('abc_sha256'):raise ValueError('Image profiler final ABC differs.')
    return dict(base_resource_sha256=previous_adapter['base_resource_sha256'],patched_resource_sha256=digest(final_swf),
        previous_stage_sha256=comm.contract_digest(previous_adapter),postproof_sha256=comm.contract_digest(postproof),
        previous_stage_adapter=json.loads(json.dumps(previous_adapter)),image_boundary_profile_contract=json.loads(json.dumps(postproof)))


def verify_adapter(adapter,final_swf):
    if not isinstance(adapter,dict)or chain_adapter(adapter.get('previous_stage_adapter'),adapter.get('image_boundary_profile_contract'),final_swf)!=adapter:
        raise ValueError('Image profiler final proof differs.')
    return True
