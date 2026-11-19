// Separate communication-only postpass for the pinned native Olympus dependency.
// Does not change its Grid, Button dispatch, initialization or listener semantics.
import java.nio.file.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;

public class CasCommunicationDependencyPatch {
    static final String PIN="e79b3b65c8b6234c54d4a76f4c7a671f46ece7ddb9f6940bc5db312850fdef91";
    static final String TGI="62ECC59A:00000000:3FFE72432A703655";
    static final String BUTTON="olympus.gui.buttons.Button", DIAGNOSTIC="ApexCommButtonIndexStats";
    static void check(boolean b,String s){CasStructuralRolesPatch.check(b,s);}
    static String sha(byte[] b)throws Exception{return CasStructuralRolesPatch.sha(b);}
    static ABC communication(ABC original,ABC baseline,ABC compiled)throws Exception {
        CasCommunicationIndexPatch.sourceAuthority(original,baseline);CasStructuralRolesPatch.prefix(baseline,compiled);
        check(baseline.instance_info.size()==compiled.instance_info.size()&&baseline.findClassByName(CasCommunicationIndexPatch.TYPE)==compiled.findClassByName(CasCommunicationIndexPatch.TYPE),"Compiler moved communication class layout");
        CasCommunicationIndexPatch.helpers(compiled);var candidate=CasStructuralRolesPatch.reparse(baseline);candidate.constants=compiled.constants;
        int c=candidate.findClassByName(CasCommunicationIndexPatch.TYPE);
        var traits=candidate.instance_info.get(c).instance_traits.traits;var statics=candidate.class_info.get(c).static_traits.traits;
        var appended=new ArrayList<Trait>();var staticAdded=new ArrayList<Trait>();var ids=new TreeSet<Integer>();
        for(boolean statik:new boolean[]{false,true})for(var t:(statik?compiled.class_info.get(c).static_traits:compiled.instance_info.get(c).instance_traits).traits){
            String n=CasCommunicationIndexPatch.name(compiled,t.name_index);
            if(statik?!CasCommunicationIndexPatch.STATIC_METHODS.contains(n)&&!CasCommunicationIndexPatch.STATIC_FIELDS.contains(n):!CasCommunicationIndexPatch.METHODS.contains(n)&&!CasCommunicationIndexPatch.FIELDS.contains(n))continue;
            var made=t.clone();if(made instanceof TraitSlotConst)((TraitSlotConst)made).slot_id=0;else{var m=(TraitMethodGetterSetter)made;m.disp_id=0;ids.add(m.method_info);}
            (statik?staticAdded:appended).add(made);
        }
        check(appended.size()==8&&staticAdded.size()==6&&ids.size()==7,"Index trait inventory differs");
        int delta=CasCommunicationIndexPatch.body(baseline,"HasFunction").init_scope_depth-CasCommunicationIndexPatch.body(compiled,"HasFunction").init_scope_depth;
        check(delta>=0&&delta<=16,"Index helper scope differs");var remap=new HashMap<Integer,Integer>();
        for(int id:ids){int made=candidate.method_info.size();remap.put(id,made);candidate.method_info.add(compiled.method_info.get(id));var bb=compiled.findBody(id).clone();
            bb.method_info=made;bb.init_scope_depth+=delta;bb.max_scope_depth+=delta;
            for(var i:bb.getCode().code)if(CasCommunicationIndexPatch.op(i)==0x65)check(i.operands[0]>=0&&i.operands[0]<bb.max_scope_depth-bb.init_scope_depth,"Helper local activation scope index differs");
            bb.setCode(bb.getCode());bb.setModified();candidate.bodies.add(bb);
        }
        var allAdded=new ArrayList<Trait>(appended);allAdded.addAll(staticAdded);
        for(var t:allAdded)if(t instanceof TraitMethodGetterSetter)((TraitMethodGetterSetter)t).method_info=remap.get(((TraitMethodGetterSetter)t).method_info);
        traits.addAll(appended);statics.addAll(staticAdded);candidate.resetMethodIndexing();CasCommunicationIndexPatch.protectedBindings(candidate,new HashSet<>(remap.values()));
        var rewrites=new HashMap<Integer,CasStructuralRolesPatch.Rewrite>();
        for(String n:CasCommunicationIndexPatch.CHANGED){var before=CasCommunicationIndexPatch.body(baseline,n);var change=CasCommunicationIndexPatch.rewrite(candidate,before,n);rewrites.put(before.method_info,change);CasStructuralRolesPatch.replace(candidate,change.body);}
        var hashes=new HashMap<Integer,String>();for(var bb:candidate.bodies)if(bb.method_info>=baseline.method_info.size()||rewrites.containsKey(bb.method_info))hashes.put(bb.method_info,sha(bb.getCodeBytes()));
        CasCommunicationIndexPatch.verify(baseline,candidate,rewrites,hashes);candidate=CasStructuralRolesPatch.reparse(candidate);CasCommunicationIndexPatch.verify(baseline,candidate,rewrites,hashes);
        return candidate;
    }
    static TraitMethodGetterSetter buttonMethod(ABC a,String name){
        int c=a.findClassByName(BUTTON);if(c<0)return null;
        for(var t:a.instance_info.get(c).instance_traits.traits)
            if(t instanceof TraitMethodGetterSetter&&name.equals(CasCommunicationIndexPatch.name(a,t.name_index)))return (TraitMethodGetterSetter)t;
        return null;
    }
    static byte[] diagnosticCode(ABC a)throws Exception {
        int comm=a.instance_info.get(a.findClassByName(CasCommunicationIndexPatch.TYPE)).name_index;
        int stats=CasStructuralRolesPatch.trait(a,CasCommunicationIndexPatch.TYPE,"ApexCommIndexStats",true).name_index;
        var out=new java.io.ByteArrayOutputStream();
        for(var i:List.of(CasStructuralRolesPatch.ins(0xd0),CasStructuralRolesPatch.ins(0x30),
            CasStructuralRolesPatch.ins(0x2c,a.constants.getStringId("button_provider",true)),CasStructuralRolesPatch.ins(0x2c,a.constants.getStringId(TGI,true)),
            CasStructuralRolesPatch.ins(0x2c,a.constants.getStringId("listener_membership",true)),CasStructuralRolesPatch.ins(0x60,comm),
            CasStructuralRolesPatch.ins(0x46,stats,0),CasStructuralRolesPatch.ins(0x55,2),CasStructuralRolesPatch.ins(0x48)))out.write(i.getBytes());
        return out.toByteArray();
    }
    static void appendButton(ABC a)throws Exception {
        check(a.findClassByName(BUTTON)>=0&&buttonMethod(a,DIAGNOSTIC)==null,"Button diagnostic class boundary differs");
        var nativeMethod=buttonMethod(a,"Draw");check(nativeMethod!=null,"Native Button.Draw absent");
        var nativeBody=a.findBody(nativeMethod.method_info);var q=new Multiname();q.kind=Multiname.QNAME;
        q.namespace_index=a.constants.getMultiname(nativeMethod.name_index).namespace_index;q.name_index=a.constants.getStringId(DIAGNOSTIC,true);
        var trait=new TraitMethodGetterSetter();trait.kindType=Trait.TRAIT_METHOD;trait.name_index=a.constants.getMultinameId(q,true);trait.method_info=a.method_info.size();
        int object=a.constants.getPublicQnameId("Object",false);check(object>0,"Native Object type absent");
        var bytes=diagnosticCode(a);a.method_info.add(new MethodInfo(new int[0],object,q.name_index,0,new ValueKind[0],new int[0]));
        var body=new MethodBody(a,new Traits(),bytes,new ABCException[0]);body.method_info=trait.method_info;body.max_stack=4;body.max_regs=1;
        body.init_scope_depth=nativeBody.init_scope_depth;body.max_scope_depth=body.init_scope_depth+1;
        a.bodies.add(body);a.instance_info.get(a.findClassByName(BUTTON)).instance_traits.traits.add(trait);a.resetMethodIndexing();
    }
    static void verifyButton(ABC communication,ABC candidate)throws Exception {
        CasStructuralRolesPatch.prefix(communication,candidate);
        check(candidate.method_info.size()==communication.method_info.size()+1&&candidate.bodies.size()==communication.bodies.size()+1,"Button diagnostic method inventory differs");
        var t=buttonMethod(candidate,DIAGNOSTIC);check(t!=null&&t.method_info==communication.method_info.size()&&t.kindType==Trait.TRAIT_METHOD&&t.kindFlags==0&&t.disp_id==0,"Button diagnostic trait ABI differs");
        var nativeMethod=buttonMethod(candidate,"Draw");var q=candidate.constants.getMultiname(t.name_index);
        check(q.kind==Multiname.QNAME&&q.namespace_index==candidate.constants.getMultiname(nativeMethod.name_index).namespace_index,"Button diagnostic public namespace differs");
        var info=candidate.method_info.get(t.method_info);var b=candidate.findBody(t.method_info);
        check(info.flags==0&&info.param_types.length==0&&"Object".equals(CasCommunicationIndexPatch.name(candidate,info.ret_type))&&info.optional.length==0&&info.paramNames.length==0,"Button diagnostic signature differs");
        check(b.max_stack==4&&b.max_regs==1&&b.init_scope_depth==candidate.findBody(nativeMethod.method_info).init_scope_depth&&b.max_scope_depth==b.init_scope_depth+1&&b.exceptions.length==0&&b.traits.traits.isEmpty(),"Button diagnostic frame/scope differs");
        check(Arrays.equals(b.getCodeBytes(),diagnosticCode(candidate)),"Button diagnostic must read only its exact lexical communication class");
        var rollback=CasStructuralRolesPatch.reparse(candidate);rollback.method_info.remove(rollback.method_info.size()-1);rollback.bodies.remove(rollback.bodies.size()-1);
        var traits=rollback.instance_info.get(rollback.findClassByName(BUTTON)).instance_traits.traits;var old=communication.instance_info.get(communication.findClassByName(BUTTON)).instance_traits.traits;
        check(traits.size()==old.size()+1&&traits.get(traits.size()-1).name_index==t.name_index,"Button diagnostic trait placement differs");traits.remove(traits.size()-1);
        rollback.constants=communication.constants;rollback.resetMethodIndexing();
        check(Arrays.equals(CasStructuralRolesPatch.save(rollback),CasStructuralRolesPatch.save(communication)),"Button whole-ABC rollback changed native methods/dispatch/initializers");
    }
    public static void main(String[] args)throws Exception {
        check(args.length==5,"Use original dependency, retained baseline, compiled helpers, output ABC, proof");
        byte[] raw=Files.readAllBytes(Path.of(args[0])),base=Files.readAllBytes(Path.of(args[1]));
        check(sha(raw).equals(PIN)&&Arrays.equals(raw,base),"Dependency input must be exact native e79b library without a Grid stage");
        var baseline=CasStructuralRolesPatch.load(args[1]);var index=communication(CasStructuralRolesPatch.load(args[0]),baseline,CasStructuralRolesPatch.load(args[2]));
        Files.write(Path.of(args[3]).resolveSibling("communication.abc"),CasStructuralRolesPatch.save(index));
        var candidate=CasStructuralRolesPatch.reparse(index);appendButton(candidate);verifyButton(index,candidate);candidate=CasStructuralRolesPatch.reparse(candidate);verifyButton(index,candidate);
        byte[] data=CasStructuralRolesPatch.save(candidate);Files.write(Path.of(args[3]),data);
        String report="{\"ok\":true,\"provider_resource_tgi\":\""+TGI+"\",\"base_provider_sha256\":\""+PIN+"\",\"baseline_swf_sha256\":\""+sha(base)+"\",\"baseline_abc_sha256\":\""+sha(CasStructuralRolesPatch.save(baseline))+"\",\"communication_abc_sha256\":\""+sha(CasStructuralRolesPatch.save(index))+"\",\"abc_sha256\":\""+sha(data)+"\",\"changed_native_bodies\":5,\"appended_methods\":8,\"appended_communication_methods\":7,\"appended_button_diagnostic_methods\":1,\"appended_fields\":2,\"appended_static_fields\":5,\"whole_abc_rollback_verified\":true,\"button_whole_abc_rollback_verified\":true,\"button_lexical_domain_read_verified\":true,\"reviewed_helper_semantic_pins_verified\":true,\"protected_field_namespace_verified\":true,\"bound_closure_runtime_eligibility_probe\":true,\"explicit_primitive_diagnostics\":true,\"native_array_dispatch_order_retained\":true,\"public_alias_falls_back_to_original\":true,\"deferred_removal_semantics_retained\":true,\"grid_stage_present\":false,\"runtime_qualified\":false,\"hitch_free_claimed\":false}";
        Files.writeString(Path.of(args[4]),report+"\n");System.out.println(report);
    }
}
