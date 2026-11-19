// O(1) proven-negative removal only; retain every original positive/deferred op.
import java.nio.file.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;

public class CasCommunicationRemovalMissPatch {
    static final String TYPE="olympus.io.CommunicationObject",HELPER="ApexCommRemovalMissing";
    static final String MANAGER="olympus.io.CommunicationManager",MANAGER_PROBE="ApexCommTargetIndexStats";
    static final String SEMANTIC="0c30fd54477fa9dedc9c3f9edbc4662596768e95c1255fe55e1498c08bbd10a5";
    static final Map<String,String> BASELINES=Map.of(
        "74701ad23ea1eb9e97775a75d374ea72a1e3e1e9b40f7fdecd8e68f19b3139d3","62ECC59A:00000000:12272E1AC0C1F8E2",
        "2501f2bc00caeb7d3b69b24e80ee81621c87110f569a442a5c090cce04246c79","62ECC59A:00000000:89D13757C58C2E05",
        "5ff049dc49739a0672115f8dace4bd2f6b745ab37484cfd27970c6e27d87b41c","62ECC59A:00000000:3FFE72432A703655");
    static void check(boolean b,String s){CasStructuralRolesPatch.check(b,s);}
    static int op(AVM2Instruction i){return i.definition.instructionCode;}
    static TraitMethodGetterSetter method(ABC a,String n){return CasStructuralRolesPatch.trait(a,TYPE,n,false);}
    static MethodBody body(ABC a,String n){return a.findBody(method(a,n).method_info);}
    static MethodBody managerBody(ABC a,String n,boolean statik){return CasStructuralRolesPatch.body(a,MANAGER,n,statik);}
    static int originalSingleton(ABC a){
        var b=managerBody(a,"AddMessageListenerByName",true);var code=b.getCode().code;
        check(code.size()==9&&op(code.get(0))==0xd0&&op(code.get(1))==0x30&&op(code.get(2))==0x60&&"instance".equals(CasStructuralRolesPatch.name(a,code.get(2).operands[0]))&&b.exceptions.length==0,"Original static singleton getter oracle differs");
        var q=a.constants.getMultiname(code.get(2).operands[0]);var ns=a.constants.getNamespace(q.namespace_index);
        check(q.kind==Multiname.QNAME&&ns.kind==26&&"olympus.io:CommunicationManager".equals(a.constants.getString(ns.name_index)),"Original static singleton protected namespace differs");return code.get(2).operands[0];
    }
    static int[] originalMap(ABC a){
        var code=managerBody(a,"AddMessageListener",false).getCode().code;int field=-1,dynamic=-1,count=0;
        for(int i=0;i+2<code.size();i++)if(op(code.get(i))==0x66&&"mMessageListeners".equals(CasStructuralRolesPatch.name(a,code.get(i).operands[0]))&&op(code.get(i+1))==0xd1&&op(code.get(i+2))==0x66){
            field=code.get(i).operands[0];dynamic=code.get(i+2).operands[0];count++;
        }
        check(count==1&&a.constants.getMultiname(dynamic).kind==Multiname.MULTINAMEL,"Original dynamic message-map getter oracle differs");return new int[]{field,dynamic};
    }
    static void text(ABC a,List<AVM2Instruction> out,String value){out.add(CasStructuralRolesPatch.ins(0x2c,a.constants.getStringId(value,true)));}
    static void missing(ABC a,List<AVM2Instruction> out,boolean singleton,boolean listener,String reason){
        text(a,out,"singleton_present");out.add(CasStructuralRolesPatch.ins(singleton?0x26:0x27));text(a,out,"listener_present");out.add(CasStructuralRolesPatch.ins(listener?0x26:0x27));text(a,out,"reason");text(a,out,reason);text(a,out,"appearance_written");out.add(CasStructuralRolesPatch.ins(0x27));out.add(CasStructuralRolesPatch.ins(0x55,4));out.add(CasStructuralRolesPatch.ins(0x48));
    }
    static byte[] correctedManagerCode(ABC a)throws Exception {
        int singleton=originalSingleton(a);var map=originalMap(a);var out=new ArrayList<AVM2Instruction>();
        out.add(CasStructuralRolesPatch.ins(0xd0));out.add(CasStructuralRolesPatch.ins(0x30));out.add(CasStructuralRolesPatch.ins(0x60,singleton));out.add(CasStructuralRolesPatch.ins(0xd5));
        out.add(CasStructuralRolesPatch.ins(0xd1));var haveSingleton=CasStructuralRolesPatch.ins(0x11,0);out.add(haveSingleton);missing(a,out,false,false,"singleton-missing");
        var readMap=CasStructuralRolesPatch.ins(0xd1);out.add(readMap);out.add(CasStructuralRolesPatch.ins(0x66,map[0]));out.add(CasStructuralRolesPatch.ins(0xd6));out.add(CasStructuralRolesPatch.ins(0xd2));var haveMap=CasStructuralRolesPatch.ins(0x11,0);out.add(haveMap);missing(a,out,true,false,"listener-map-missing");
        var lookup=CasStructuralRolesPatch.ins(0xd2);out.add(lookup);text(a,out,"UsingControllerToggled");out.add(CasStructuralRolesPatch.ins(0x66,map[1]));out.add(CasStructuralRolesPatch.ins(0xd6));out.add(CasStructuralRolesPatch.ins(0xd2));var haveListener=CasStructuralRolesPatch.ins(0x11,0);out.add(haveListener);missing(a,out,true,false,"listener-missing");
        var checkProbe=CasStructuralRolesPatch.ins(0x2c,a.constants.getStringId("ApexCommObjectIndexStats",true));out.add(checkProbe);out.add(CasStructuralRolesPatch.ins(0xd2));out.add(CasStructuralRolesPatch.ins(0xb4));var probeExists=CasStructuralRolesPatch.ins(0x11,0);out.add(probeExists);missing(a,out,true,true,"listener-probe-unavailable");
        var readProbe=CasStructuralRolesPatch.ins(0xd2);out.add(readProbe);out.add(CasStructuralRolesPatch.ins(0x66,method(a,"ApexCommObjectIndexStats").name_index));out.add(CasStructuralRolesPatch.ins(0xb2,a.method_info.get(method(a,"HasFunction").method_info).param_types[0]));var probeCallable=CasStructuralRolesPatch.ins(0x11,0);out.add(probeCallable);missing(a,out,true,true,"listener-probe-unavailable");
        var call=CasStructuralRolesPatch.ins(0xd2);out.add(call);out.add(CasStructuralRolesPatch.ins(0x46,method(a,"ApexCommObjectIndexStats").name_index,0));out.add(CasStructuralRolesPatch.ins(0xd7));
        for(String key:new String[]{"singleton_present","listener_present","reason"}){out.add(CasStructuralRolesPatch.ins(0xd3));if(key.equals("reason"))text(a,out,"ready");else out.add(CasStructuralRolesPatch.ins(0x26));out.add(CasStructuralRolesPatch.ins(0x61,a.constants.getPublicQnameId(key,true)));}
        out.add(CasStructuralRolesPatch.ins(0xd3));out.add(CasStructuralRolesPatch.ins(0x48));long address=0;for(var i:out){i.setAddress(address);address+=i.getBytesLength();}
        for(var pair:List.of(new AVM2Instruction[]{haveSingleton,readMap},new AVM2Instruction[]{haveMap,lookup},new AVM2Instruction[]{haveListener,checkProbe},new AVM2Instruction[]{probeExists,readProbe},new AVM2Instruction[]{probeCallable,call}))pair[0].operands[0]=(int)(pair[1].getAddress()-pair[0].getAddress()-pair[0].getBytesLength());
        var bytes=new java.io.ByteArrayOutputStream();for(var i:out)bytes.write(i.getBytes());return bytes.toByteArray();
    }
    static void correctManager(ABC a)throws Exception {
        var b=managerBody(a,MANAGER_PROBE,true);b.setCodeBytes(correctedManagerCode(a));b.setCode(b.getCode());b.max_stack=8;b.max_regs=4;
        b.init_scope_depth=managerBody(a,"AddMessageListenerByName",true).init_scope_depth;b.max_scope_depth=b.init_scope_depth+1;b.setModified();
    }
    static void verifyManager(ABC a)throws Exception {
        var t=CasStructuralRolesPatch.trait(a,MANAGER,MANAGER_PROBE,true);var info=a.method_info.get(t.method_info);var b=a.findBody(t.method_info);
        check(t.kindType==Trait.TRAIT_METHOD&&t.kindFlags==0&&t.disp_id==0&&info.flags==0&&info.param_types.length==0&&"Object".equals(CasStructuralRolesPatch.name(a,info.ret_type)),"Owned Manager probe signature differs");
        check(b.max_stack==8&&b.max_regs==4&&b.exceptions.length==0&&b.traits.traits.isEmpty()&&b.init_scope_depth==managerBody(a,"AddMessageListenerByName",true).init_scope_depth&&b.max_scope_depth==b.init_scope_depth+1,"Owned Manager probe scope/frame differs");
        check(Arrays.equals(b.getCodeBytes(),correctedManagerCode(a)),"Manager probe must mirror original static/dynamic getters and exact reason paths");
    }
    static MethodBody normalHelper(MethodBody b,boolean guarded)throws Exception {
        var normal=b.clone();if(!guarded){check(b.exceptions.length==0,"Compiled normal predicate acquired an exception dependency");return normal;}
        var code=normal.getCode().code;check(code.size()>7&&b.exceptions.length==1,"Removal predicate catch inventory differs");int n=code.size()-5;
        for(int j=0;j<5;j++)check(op(code.get(n+j))==new int[]{0x29,0xd0,0x30,0x27,0x48}[j],"Removal predicate allocation-free fallback handler differs");
        var e=b.exceptions[0];check(e.start==code.get(2).getAddress()&&e.end==code.get(n).getAddress()&&e.target==e.end&&e.type_index==0&&e.name_index==0,"Removal predicate error fallback range differs");
        while(code.size()>n)code.remove(code.size()-1);normal.exceptions=new ABCException[0];normal.setCode(normal.getCode());normal.setModified();return normal;
    }
    static MethodBody guardedHelper(MethodBody source)throws Exception {
        var b=source.clone();var code=b.getCode().code;long start=code.get(2).getAddress(),end=b.getCode().getEndOffset();
        for(int opcode:new int[]{0x29,0xd0,0x30,0x27,0x48})code.add(CasStructuralRolesPatch.ins(opcode));
        long address=0;for(var i:code){i.setAddress(address);address+=i.getBytesLength();}b.setCode(b.getCode());
        var e=new ABCException();e.start=(int)start;e.end=(int)end;e.target=(int)end;e.type_index=0;e.name_index=0;b.exceptions=new ABCException[]{e};b.setModified();return b;
    }
    static void helper(ABC a,boolean guarded)throws Exception {
        var t=method(a,HELPER);var b=normalHelper(a.findBody(t.method_info),guarded);var info=a.method_info.get(t.method_info);var q=a.constants.getMultiname(t.name_index);var ns=a.constants.getNamespace(q.namespace_index);
        check(t.kindType==Trait.TRAIT_METHOD&&t.kindFlags==0&&t.disp_id==0&&q.kind==Multiname.QNAME&&ns.kind==Namespace.KIND_PRIVATE,"Removal predicate must be private");
        check(info.flags==0&&info.param_types.length==1&&"Function".equals(CasStructuralRolesPatch.name(a,info.param_types[0]))&&"Boolean".equals(CasStructuralRolesPatch.name(a,info.ret_type))&&info.optional.length==0,"Removal predicate signature differs flags="+info.flags);
        for(var i:b.getCode().code)check(!Set.of(0x40,0x41,0x42,0x43,0x44,0x45,0x46,0x49,0x4a,0x4c,0x4e,0x4f,0x55,0x56,0x57,0x61,0x68).contains(op(i)),"Removal predicate must not invoke/allocate/write native state");
        var allowed=Set.of("mbDispatching","apexCommAliased","apexCommIndex");var declarations=new HashMap<String,Integer>();
        for(var field:a.instance_info.get(a.findClassByName(TYPE)).instance_traits.traits)if(allowed.contains(CasStructuralRolesPatch.name(a,field.name_index)))declarations.put(CasStructuralRolesPatch.name(a,field.name_index),field.name_index);
        check(declarations.size()==3,"Removal predicate authority fields absent");
        for(var i:b.getCode().code)if((op(i)==0x66||op(i)==0x5d||op(i)==0x60)&&CasStructuralRolesPatch.name(a,i.operands[0])!=null&&allowed.contains(CasStructuralRolesPatch.name(a,i.operands[0]))){
            String name=CasStructuralRolesPatch.name(a,i.operands[0]);var declared=a.constants.getMultiname(declarations.get(name));var used=a.constants.getMultiname(i.operands[0]);boolean same=used.namespace_index==declared.namespace_index;
            if(used.namespace_set_index>0)for(int n:a.constants.getNamespaceSet(used.namespace_set_index).namespaces)same|=n==declared.namespace_index;
            check(same,"Removal predicate private field binding differs: "+name);
        }
        check(CasCommunicationIndexPatch.semantic(a,b).equals(SEMANTIC),"Removal predicate source-authenticated semantic bytes differ");
    }
    static CasStructuralRolesPatch.Rewrite rewrite(ABC a,MethodBody before)throws Exception {
        var old=before.getCode().code;check(old.size()>2&&op(old.get(0))==0xd0&&op(old.get(1))==0x30&&before.exceptions.length==0,"Native RemoveFunction scope/exception boundary differs");
        var fallback=CasStructuralRolesPatch.copy(old.get(2));var branch=CasStructuralRolesPatch.ins(0x12,0);
        var added=new ArrayList<AVM2Instruction>(List.of(CasStructuralRolesPatch.ins(0xd0),CasStructuralRolesPatch.ins(0xd2),CasStructuralRolesPatch.ins(0x46,method(a,HELPER).name_index,1),branch,CasStructuralRolesPatch.ins(0x27),CasStructuralRolesPatch.ins(0x48),fallback));
        var block=new CasStructuralRolesPatch.Block(2,3,added);block.edge(branch,0,CasStructuralRolesPatch.local(fallback));
        var r=CasStructuralRolesPatch.rewrite(before,List.of(block));r.origins.set(8,2);r.boundaries.put(2,8);r.body.max_stack=before.max_stack+2;r.body.setModified();
        CasStructuralRolesPatch.verifyProjection(before,r,r.body);return r;
    }
    static void verify(ABC base,ABC candidate,CasStructuralRolesPatch.Rewrite change)throws Exception {
        CasStructuralRolesPatch.prefix(base,candidate);check(candidate.method_info.size()==base.method_info.size()+1&&candidate.bodies.size()==base.bodies.size()+1,"Removal-miss helper inventory differs");
        helper(candidate,true);verifyManager(candidate);CasStructuralRolesPatch.verifyProjection(body(base,"RemoveFunction"),change,body(candidate,"RemoveFunction"));
        check(Arrays.equals(body(candidate,"RemoveFunction").getCodeBytes(),change.body.getCodeBytes()),"Removal-miss branch/native bytes differ");
        var rollback=CasStructuralRolesPatch.reparse(candidate);CasStructuralRolesPatch.replace(rollback,body(base,"RemoveFunction").clone());CasStructuralRolesPatch.replace(rollback,managerBody(base,MANAGER_PROBE,true).clone());
        rollback.method_info.remove(rollback.method_info.size()-1);rollback.bodies.remove(rollback.bodies.size()-1);
        var t=rollback.instance_info.get(rollback.findClassByName(TYPE)).instance_traits.traits;var old=base.instance_info.get(base.findClassByName(TYPE)).instance_traits.traits;
        check(t.size()==old.size()+1&&HELPER.equals(CasStructuralRolesPatch.name(rollback,t.get(t.size()-1).name_index)),"Removal predicate trait placement differs");t.remove(t.size()-1);
        rollback.constants=base.constants;rollback.resetMethodIndexing();check(Arrays.equals(CasStructuralRolesPatch.save(rollback),CasStructuralRolesPatch.save(base)),"Removal-miss whole-ABC rollback changed native/owned bodies or initializers");
        for(var b:base.bodies)if(b.method_info!=body(base,"RemoveFunction").method_info&&b.method_info!=managerBody(base,MANAGER_PROBE,true).method_info)check(Arrays.equals(b.getCodeBytes(),candidate.findBody(b.method_info).getCodeBytes()),"Removal-miss changed another existing body");
    }
    public static void main(String[] args)throws Exception {
        if(args.length==2&&args[0].equals("--semantic")){var a=CasStructuralRolesPatch.load(args[1]);System.out.println(CasCommunicationIndexPatch.semantic(a,body(a,HELPER)));CasStructuralRolesPatch.dump(a,body(a,HELPER),System.out);return;}
        check(args.length==4,"Use frozen baseline, compiled predicate, output ABC, proof");String pin=CasStructuralRolesPatch.sha(Files.readAllBytes(Path.of(args[0]))),tgi=BASELINES.get(pin);check(tgi!=null,"Unpinned removal-miss baseline");
        var base=CasStructuralRolesPatch.load(args[0]);var compiled=CasStructuralRolesPatch.load(args[1]);CasStructuralRolesPatch.prefix(base,compiled);helper(compiled,false);
        check(base.findClassByName(TYPE)==compiled.findClassByName(TYPE)&&base.instance_info.size()==compiled.instance_info.size(),"Compiler moved removal helper class");
        var a=CasStructuralRolesPatch.reparse(base);a.constants=compiled.constants;var trait=method(compiled,HELPER).clone();var source=body(compiled,HELPER);var b=guardedHelper(source);
        int delta=body(base,"RemoveFunction").init_scope_depth-body(compiled,"RemoveFunction").init_scope_depth;check(delta>=0&&delta<=16,"Removal helper outer scope differs");
        trait.method_info=a.method_info.size();trait.disp_id=0;a.method_info.add(compiled.method_info.get(source.method_info));b.method_info=trait.method_info;b.init_scope_depth+=delta;b.max_scope_depth+=delta;
        for(var i:b.getCode().code)if(op(i)==0x65)check(i.operands[0]>=0&&i.operands[0]<b.max_scope_depth-b.init_scope_depth,"Removal helper outer activation capture differs");
        b.setCode(b.getCode());b.setModified();a.bodies.add(b);a.instance_info.get(a.findClassByName(TYPE)).instance_traits.traits.add(trait);a.resetMethodIndexing();
        var change=rewrite(a,body(base,"RemoveFunction"));CasStructuralRolesPatch.replace(a,change.body);correctManager(a);verify(base,a,change);a=CasStructuralRolesPatch.reparse(a);verify(base,a,change);
        byte[] data=CasStructuralRolesPatch.save(a);Files.write(Path.of(args[2]),data);
        String report="{\"ok\":true,\"provider_resource_tgi\":\""+tgi+"\",\"baseline_swf_sha256\":\""+pin+"\",\"baseline_abc_sha256\":\""+CasStructuralRolesPatch.sha(CasStructuralRolesPatch.save(base))+"\",\"abc_sha256\":\""+CasStructuralRolesPatch.sha(data)+"\",\"changed_existing_bodies\":2,\"changed_native_bodies\":1,\"replaced_owned_manager_bodies\":1,\"manager_native_static_getter_oracle_verified\":true,\"manager_native_dynamic_map_oracle_verified\":true,\"diagnostic_reason_fields_verified\":true,\"appended_methods\":1,\"appended_fields\":0,\"whole_abc_rollback_verified\":true,\"native_instruction_projection_verified\":true,\"negative_only_predicate_verified\":true,\"private_field_binding_verified\":true,\"deferred_removal_original_path_verified\":true,\"native_positive_null_alias_unbuilt_paths_retained\":true,\"no_lazy_index_build_or_allocation\":true,\"all_other_bodies_retained\":true,\"runtime_qualified\":false,\"hitch_free_claimed\":false}";
        Files.writeString(Path.of(args[3]),report+"\n");System.out.println(report);
    }
}
