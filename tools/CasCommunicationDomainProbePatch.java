// Explicit diagnostics only: actual Button -> bound Manager -> actual listener.
// No native initialization, dispatch, registration or index body is rewritten.
import java.nio.file.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;

public class CasCommunicationDomainProbePatch {
    static final String COMM="olympus.io.CommunicationObject",MANAGER="olympus.io.CommunicationManager",BUTTON="olympus.gui.buttons.Button";
    static final String OBJECT_PROBE="ApexCommObjectIndexStats",MANAGER_PROBE="ApexCommTargetIndexStats",BUTTON_PROBE="ApexCommButtonIndexStats";
    static final String DEPENDENCY="62ECC59A:00000000:3FFE72432A703655";
    static final Map<String,String> BASELINES=Map.of(
        "2f74987d872080437fe9695a9f219e8a71c139f37c1f6c3c806f5888f98e8cf3","62ECC59A:00000000:12272E1AC0C1F8E2",
        "b7ab103c2e1070ee474b88bd82c77279d176e4985d4f2caa7f27dab3ef85fe6f","62ECC59A:00000000:89D13757C58C2E05",
        "4625eee68d2ffcffce8ece197741e321f840bca44f83843d306d0206e6cece11",DEPENDENCY);
    static void check(boolean b,String s){CasStructuralRolesPatch.check(b,s);}
    static int op(AVM2Instruction i){return i.definition.instructionCode;}
    static String name(ABC a,int q){return CasStructuralRolesPatch.name(a,q);}
    static Trait find(ABC a,String type,String n,boolean statik){
        int c=a.findClassByName(type);check(c>=0,"Probe class absent: "+type);Trait found=null;
        for(var t:(statik?a.class_info.get(c).static_traits:a.instance_info.get(c).instance_traits).traits)
            if(n.equals(name(a,t.name_index))){check(found==null,"Ambiguous probe member: "+type+"."+n);found=t;}
        return found;
    }
    static int field(ABC a,String type,String n,boolean statik){var t=find(a,type,n,statik);check(t instanceof TraitSlotConst,"Probe field absent: "+type+"."+n);return t.name_index;}
    static TraitMethodGetterSetter method(ABC a,String type,String n,boolean statik){var t=find(a,type,n,statik);check(t instanceof TraitMethodGetterSetter,"Probe method absent: "+type+"."+n);return (TraitMethodGetterSetter)t;}
    static AVM2Instruction ins(int op,int... args){return CasStructuralRolesPatch.ins(op,args);}
    static int string(ABC a,String s){return a.constants.getStringId(s,true);}
    static int pub(ABC a,String s){return a.constants.getPublicQnameId(s,true);}
    static void text(ABC a,List<AVM2Instruction> out,String s){out.add(ins(0x2c,string(a,s)));}
    static void own(ABC a,List<AVM2Instruction> out,String key,String member,boolean statik){
        text(a,out,key);out.add(statik?ins(0x60,a.instance_info.get(a.findClassByName(COMM)).name_index):ins(0xd0));out.add(ins(0x66,field(a,COMM,member,statik)));
    }
    static byte[] bytes(List<AVM2Instruction> out)throws Exception{var b=new java.io.ByteArrayOutputStream();for(var i:out)b.write(i.getBytes());return b.toByteArray();}
    static byte[] objectCode(ABC a,String tgi)throws Exception {
        var out=new ArrayList<AVM2Instruction>();out.add(ins(0xd0));out.add(ins(0x30));
        text(a,out,"provider_resource_tgi");text(a,out,tgi);
        own(a,out,"index_active","apexCommIndex",false);out.add(ins(0x20));out.add(ins(0xac));out.add(ins(0x96));
        own(a,out,"alias_escaped","apexCommAliased",false);
        own(a,out,"listener_count","mFunctions",false);out.add(ins(0x66,pub(a,"length")));
        own(a,out,"indexes_built","apexCommBuilt",true);own(a,out,"indexed_calls","apexCommCalls",true);
        own(a,out,"alias_fallbacks","apexCommAlias",true);own(a,out,"eligibility_fallbacks","apexCommEligibility",true);own(a,out,"error_fallbacks","apexCommErrors",true);
        text(a,out,"appearance_written");out.add(ins(0x27));out.add(ins(0x55,10));out.add(ins(0x48));return bytes(out);
    }
    static byte[] managerCode(ABC a)throws Exception {
        var out=new ArrayList<AVM2Instruction>();out.add(ins(0xd0));out.add(ins(0x30));
        // Static local0 is the exact Manager class called by Button. Do not
        // perform a second global class lookup before reading its singleton.
        out.add(ins(0xd0));out.add(ins(0x66,field(a,MANAGER,"instance",true)));out.add(ins(0xd5));
        out.add(ins(0xd1));var haveManager=ins(0x11,0);out.add(haveManager);out.add(ins(0x20));out.add(ins(0x48));
        var lookup=ins(0xd1);out.add(lookup);out.add(ins(0x66,field(a,MANAGER,"mMessageListeners",false)));out.add(ins(0x66,pub(a,"UsingControllerToggled")));out.add(ins(0xd6));
        out.add(ins(0xd2));var haveListener=ins(0x11,0);out.add(haveListener);out.add(ins(0x20));out.add(ins(0x48));
        var call=ins(0xd2);out.add(call);out.add(ins(0x46,method(a,COMM,OBJECT_PROBE,false).name_index,0));out.add(ins(0x48));
        long address=0;for(var i:out){i.setAddress(address);address+=i.getBytesLength();}
        haveManager.operands[0]=(int)(lookup.getAddress()-haveManager.getAddress()-haveManager.getBytesLength());haveListener.operands[0]=(int)(call.getAddress()-haveListener.getAddress()-haveListener.getBytesLength());return bytes(out);
    }
    static byte[] buttonCode(ABC a,String tgi,boolean legacy)throws Exception {
        var out=new ArrayList<AVM2Instruction>();out.add(ins(0xd0));out.add(ins(0x30));text(a,out,"button_provider");text(a,out,tgi);text(a,out,"listener_membership");
        String type=legacy?COMM:MANAGER;out.add(ins(0x60,a.instance_info.get(a.findClassByName(type)).name_index));
        out.add(ins(0x46,method(a,type,legacy?"ApexCommIndexStats":MANAGER_PROBE,true).name_index,0));out.add(ins(0x55,2));out.add(ins(0x48));return bytes(out);
    }
    static void append(ABC a,String type,String n,boolean statik,String prototype,int stack,int regs,byte[] code)throws Exception {
        check(find(a,type,n,statik)==null,"Domain probe already present: "+n);var nativeMethod=method(a,type,prototype,statik);var q=new Multiname();q.kind=Multiname.QNAME;
        q.namespace_index=a.constants.getMultiname(nativeMethod.name_index).namespace_index;q.name_index=string(a,n);
        var t=new TraitMethodGetterSetter();t.kindType=Trait.TRAIT_METHOD;t.name_index=a.constants.getMultinameId(q,true);t.method_info=a.method_info.size();
        int object=a.constants.getPublicQnameId("Object",false);check(object>0,"Native Object return type absent");
        a.method_info.add(new MethodInfo(new int[0],object,q.name_index,0,new ValueKind[0],new int[0]));
        var b=new MethodBody(a,new Traits(),code,new ABCException[0]);b.method_info=t.method_info;b.max_stack=stack;b.max_regs=regs;b.init_scope_depth=a.findBody(nativeMethod.method_info).init_scope_depth;b.max_scope_depth=b.init_scope_depth+1;
        b.setCode(b.getCode());b.setModified();a.bodies.add(b);int c=a.findClassByName(type);(statik?a.class_info.get(c).static_traits:a.instance_info.get(c).instance_traits).traits.add(t);a.resetMethodIndexing();
    }
    static ABC apply(ABC base,String tgi)throws Exception {
        var a=CasStructuralRolesPatch.reparse(base);boolean prior=DEPENDENCY.equals(tgi);
        if(prior){var t=method(a,BUTTON,BUTTON_PROBE,false);check(Arrays.equals(a.findBody(t.method_info).getCodeBytes(),buttonCode(a,tgi,true)),"Previous owned Button diagnostic differs");}
        else check(find(a,BUTTON,BUTTON_PROBE,false)==null,"Unreviewed existing Button probe");
        append(a,COMM,OBJECT_PROBE,false,"HasFunction",20,1,objectCode(a,tgi));
        append(a,MANAGER,MANAGER_PROBE,true,"TraceAutomation",1,3,managerCode(a));
        if(prior){var t=method(a,BUTTON,BUTTON_PROBE,false);var b=a.findBody(t.method_info);b.setCodeBytes(buttonCode(a,tgi,false));b.setCode(b.getCode());b.setModified();}
        else append(a,BUTTON,BUTTON_PROBE,false,"Draw",4,1,buttonCode(a,tgi,false));
        return a;
    }
    static void verifyMethod(ABC a,String type,String n,boolean statik,String prototype,int stack,int regs,byte[] code){
        var t=method(a,type,n,statik);var p=method(a,type,prototype,statik);var info=a.method_info.get(t.method_info);var b=a.findBody(t.method_info);var q=a.constants.getMultiname(t.name_index);
        check(t.kindType==Trait.TRAIT_METHOD&&t.kindFlags==0&&t.disp_id==0&&q.kind==Multiname.QNAME&&q.namespace_index==a.constants.getMultiname(p.name_index).namespace_index,"Domain probe public trait differs: "+n);
        check(info.flags==0&&info.param_types.length==0&&"Object".equals(name(a,info.ret_type))&&info.optional.length==0&&info.paramNames.length==0,"Domain probe signature differs: "+n);
        check(b.max_stack==stack&&b.max_regs==regs&&b.init_scope_depth==a.findBody(p.method_info).init_scope_depth&&b.max_scope_depth==b.init_scope_depth+1&&b.exceptions.length==0&&b.traits.traits.isEmpty(),"Domain probe scope/frame differs: "+n);
        check(Arrays.equals(b.getCodeBytes(),code),"Domain probe route/field/branch/instruction differs: "+n);
    }
    static void removeTrait(ABC a,ABC base,String type,boolean statik,int added){
        int c=a.findClassByName(type);var t=(statik?a.class_info.get(c).static_traits:a.instance_info.get(c).instance_traits).traits;
        var old=(statik?base.class_info.get(c).static_traits:base.instance_info.get(c).instance_traits).traits;
        check(t.size()==old.size()+added,"Domain probe trait inventory differs: "+type);while(t.size()>old.size())t.remove(t.size()-1);
    }
    static void verify(ABC base,ABC candidate,String tgi)throws Exception {
        CasStructuralRolesPatch.prefix(base,candidate);boolean prior=DEPENDENCY.equals(tgi);int added=prior?2:3;
        check(candidate.method_info.size()==base.method_info.size()+added&&candidate.bodies.size()==base.bodies.size()+added,"Domain probe appended-method inventory differs");
        verifyMethod(candidate,COMM,OBJECT_PROBE,false,"HasFunction",20,1,objectCode(candidate,tgi));
        verifyMethod(candidate,MANAGER,MANAGER_PROBE,true,"TraceAutomation",1,3,managerCode(candidate));
        verifyMethod(candidate,BUTTON,BUTTON_PROBE,false,"Draw",4,1,buttonCode(candidate,tgi,false));
        var rollback=CasStructuralRolesPatch.reparse(candidate);
        while(rollback.method_info.size()>base.method_info.size())rollback.method_info.remove(rollback.method_info.size()-1);
        while(rollback.bodies.size()>base.bodies.size())rollback.bodies.remove(rollback.bodies.size()-1);
        removeTrait(rollback,base,COMM,false,1);removeTrait(rollback,base,MANAGER,true,1);removeTrait(rollback,base,BUTTON,false,prior?0:1);
        if(prior)CasStructuralRolesPatch.replace(rollback,base.findBody(method(base,BUTTON,BUTTON_PROBE,false).method_info).clone());
        rollback.constants=base.constants;rollback.resetMethodIndexing();
        check(Arrays.equals(CasStructuralRolesPatch.save(rollback),CasStructuralRolesPatch.save(base)),"Domain probe whole-ABC rollback changed original traits/methods/initializers");
        int owned=prior?method(base,BUTTON,BUTTON_PROBE,false).method_info:-1;
        for(var b:base.bodies)if(b.method_info!=owned)check(Arrays.equals(b.getCodeBytes(),candidate.findBody(b.method_info).getCodeBytes()),"Domain probe changed an existing native/index body");
    }
    public static void main(String[] args)throws Exception {
        check(args.length==3,"Use frozen final baseline, output ABC, proof");String pin=CasStructuralRolesPatch.sha(Files.readAllBytes(Path.of(args[0]))),tgi=BASELINES.get(pin);check(tgi!=null,"Unpinned domain-probe baseline");
        var base=CasStructuralRolesPatch.load(args[0]);var candidate=apply(base,tgi);verify(base,candidate,tgi);candidate=CasStructuralRolesPatch.reparse(candidate);verify(base,candidate,tgi);
        byte[] data=CasStructuralRolesPatch.save(candidate);Files.write(Path.of(args[1]),data);boolean prior=DEPENDENCY.equals(tgi);
        String report="{\"ok\":true,\"phase\":\"native-listener-domain-probe\",\"provider_resource_tgi\":\""+tgi+"\",\"baseline_swf_sha256\":\""+pin+"\",\"baseline_abc_sha256\":\""+CasStructuralRolesPatch.sha(CasStructuralRolesPatch.save(base))+"\",\"abc_sha256\":\""+CasStructuralRolesPatch.sha(data)+"\",\"changed_native_bodies\":0,\"replaced_owned_button_bodies\":"+(prior?1:0)+",\"appended_methods\":"+(prior?2:3)+",\"whole_abc_rollback_verified\":true,\"original_index_bodies_retained\":true,\"actual_listener_instance_read_verified\":true,\"protected_singleton_binding_verified\":true,\"public_native_array_not_exposed\":true,\"no_dispatch_write_or_services\":true,\"runtime_qualified\":false,\"hitch_free_claimed\":false}";
        Files.writeString(Path.of(args[2]),report+"\n");System.out.println(report);
    }
}
