// Postpass for exactly pinned native listener arrays. No game/process access.
// Original dispatch/order/removal instructions remain authoritative.
import java.io.*;
import java.nio.file.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;

public class CasCommunicationIndexPatch {
    static final String TYPE="olympus.io.CommunicationObject",ROW="olympus.io.WidgetFunction";
    static final Map<String,String> PROVIDERS=Map.of(
        "6ddb983fee2bd284a2b7efec155e1544bfe99d27f16d4d28097bada25e1864f0","62ECC59A:00000000:89D13757C58C2E05",
        "5f475a80a4f9c77f9a0439e133221a31f766cb929318f74191b4b9bad98e8cae","62ECC59A:00000000:12272E1AC0C1F8E2");
    static final Set<String> METHODS=Set.of("ApexCommCanIndex","ApexCommDisable","ApexCommIndexedHas","ApexCommAdded","ApexCommRemoved","ApexCommExpose");
    static final Set<String> FIELDS=Set.of("apexCommIndex","apexCommAliased");
    static final Set<String> STATIC_FIELDS=Set.of("apexCommBuilt","apexCommCalls","apexCommAlias","apexCommEligibility","apexCommErrors");
    static final Set<String> STATIC_METHODS=Set.of("ApexCommIndexStats");
    static Set<String> allMethods(){var names=new TreeSet<>(METHODS);names.addAll(STATIC_METHODS);return names;}
    static final Map<String,String> SEMANTIC_PINS=Map.of(
        "ApexCommAdded","917d08a3bfe7620ec81f0998ce882b2deddfe42a9761ba2d309a065459a3505f",
        "ApexCommCanIndex","9a231142fb2d41da1e7c8f3bfad3a795629aa8b55583f630a9b9275b719d5a26",
        "ApexCommDisable","f3fd903b8359db8d91318686e85ba7e61305daa1f7fa60c8563f103890d8c77b",
        "ApexCommExpose","10174a6eaa76db57f33e7b5cdd9801741c6ccf9eeb1eb28b48894c553155e615",
        "ApexCommIndexStats","803cff6f331ed000bd3d940a7239758943ac6067ea216bb0ad1c70d0a768bc01",
        "ApexCommIndexedHas","aa8c174b255997c2da5f1c3223bb04524466cc5b81f03cf7c497bf03dd612046",
        "ApexCommRemoved","de3428401100f1074dc38db5233ab1323bef12d9458da5fde7656e579e6da9b0");
    static final List<String> CHANGED=List.of("HasFunction","GetFunctions","AddFunction","RemoveFunction","RemoveWidgetsFunctions");
    static void check(boolean b,String s){CasStructuralRolesPatch.check(b,s);}
    static String name(ABC a,int q){return CasStructuralRolesPatch.name(a,q);}
    static int op(AVM2Instruction i){return i.definition.instructionCode;}
    static AVM2Instruction ins(int n,int... a){return CasStructuralRolesPatch.ins(n,a);}
    static MethodBody body(ABC a,String n){return CasStructuralRolesPatch.body(a,TYPE,n,STATIC_METHODS.contains(n));}
    static TraitMethodGetterSetter method(ABC a,String n){return CasStructuralRolesPatch.trait(a,TYPE,n,false);}
    static boolean prop(ABC a,AVM2Instruction i,int opcode,String n){return op(i)==opcode&&n.equals(name(a,i.operands[0]));}
    static void sourceAuthority(ABC original,ABC baseline)throws Exception{
        int c=original.findClassByName(TYPE),b=baseline.findClassByName(TYPE);
        check(c>=0&&b==c&&(original.instance_info.get(c).flags&2)!=0,"Native communication class must remain final at the pinned index");
        var nativeClass=original.instance_info.get(c);var retained=baseline.instance_info.get(b);
        check(nativeClass.instance_traits.traits.size()==retained.instance_traits.traits.size(),"Communication class was changed before index postpass");
        var permitted=new HashSet<Integer>();permitted.add(nativeClass.iinit_index);
        for(var t:nativeClass.instance_traits.traits)if(t instanceof TraitMethodGetterSetter){
            var m=(TraitMethodGetterSetter)t;permitted.add(m.method_info);
            check(Arrays.equals(original.findBody(m.method_info).getCodeBytes(),baseline.findBody(m.method_info).getCodeBytes()),"Pinned communication method changed before adapter");
        }
        check(Arrays.equals(original.findBody(nativeClass.iinit_index).getCodeBytes(),baseline.findBody(retained.iinit_index).getCodeBytes()),"Original communication constructor changed");
        int assignments=0,aliasReturns=0;
        for(var bb:baseline.bodies)for(var i:bb.getCode().code)if(i.operands!=null&&i.operands.length>0&&Set.of(0x5d,0x60,0x61,0x66,0x68).contains(op(i))){
            String member=name(baseline,i.operands[0]);
            if("mFunctions".equals(member)){
                check(permitted.contains(bb.method_info),"Native listener array has an unaudited external access");
                if(op(i)==0x61||op(i)==0x68){check(bb.method_info==nativeClass.iinit_index,"Listener array reassigned outside constructor");assignments++;}
            }
            if("GetFunctions".equals(member))aliasReturns++;
        }
        check(assignments==1 && aliasReturns==0,"Native array writer/alias inventory differs");
        // GetFunctions is the sole API returning the live array. Its prefix
        // marks aliasing before original bytes expose mutable WidgetFunctions.
        var getter=body(baseline,"GetFunctions").getCode().code;
        check(getter.size()==5&&op(getter.get(2))==0xd0&&prop(baseline,getter.get(3),0x66,"mFunctions")&&op(getter.get(4))==0x48,
            "Native mutable-array escape differs");
    }
    static String ns(ABC a,int index){if(index==0)return "*";var n=a.constants.getNamespace(index);String text=a.constants.getString(n.name_index);
        // FFDec names the imported class's file-private namespace with its
        // unchanged provider-specific class index. Normalize only that exact
        // self namespace; all foreign/private/protected bindings stay exact.
        if(n.kind==Namespace.KIND_PRIVATE&&text.equals("CommunicationObject.as$"+a.findClassByName(TYPE)))text="CommunicationObject.as$SELF";
        return n.kind+":"+text;}
    static String qname(ABC a,int index){
        if(index==0)return "*";var q=a.constants.getMultiname(index);var out=new StringBuilder();
        out.append(q.kind).append(':').append(a.constants.getString(q.name_index)).append(':').append(ns(a,q.namespace_index));
        if(q.namespace_set_index>0){out.append('[');for(int n:a.constants.getNamespaceSet(q.namespace_set_index).namespaces)out.append(ns(a,n)).append(';');out.append(']');}
        if(q.qname_index>0)out.append('<').append(qname(a,q.qname_index)).append('>');
        if(q.params!=null)for(int p:q.params)out.append('<').append(qname(a,p)).append('>');return out.toString();
    }
    static String semanticText(ABC a,MethodBody b)throws Exception{
        var text=new StringBuilder();var info=a.method_info.get(b.method_info);
        text.append(info.flags).append('|').append(qname(a,info.ret_type));for(int p:info.param_types)text.append('|').append(qname(a,p));
        text.append('|').append(b.max_regs).append('|').append(b.max_stack).append('|').append(b.max_scope_depth-b.init_scope_depth);
        for(var t:b.traits.traits){check(t instanceof TraitSlotConst,"Indexed helper activation has a non-slot trait");var slot=(TraitSlotConst)t;
            text.append("|local:").append(qname(a,t.name_index)).append(':').append(qname(a,slot.type_index)).append(':').append(slot.slot_id).append(':').append(slot.value_index).append(':').append(slot.value_kind);}

        var addresses=CasStructuralRolesPatch.addresses(b);
        var multinames=Set.of(0x04,0x05,0x45,0x46,0x4a,0x4c,0x4e,0x4f,0x59,0x5b,0x5c,0x5d,0x5e,0x5f,0x60,0x61,0x66,0x68,0x6a,0x80,0x86,0xb2);
        for(var i:b.getCode().code){text.append('\n').append(op(i));if(i.operands==null)continue;
            for(int n=0;n<i.operands.length;n++){
                text.append(':');if(CasStructuralRolesPatch.targetOperands(i).contains(n))text.append('@').append(CasStructuralRolesPatch.index(addresses,CasStructuralRolesPatch.target(i,n)));
                else if(n==0&&multinames.contains(op(i)))text.append(qname(a,i.operands[n]));
                else if(n==1&&op(i)==0xef)text.append(a.constants.getString(i.operands[n]));
                else if(n==0&&op(i)==0xf1)text.append("owned-helper-source");
                else if(n==0&&op(i)==0x2c)text.append(a.constants.getString(i.operands[n]));
                else if(n==0&&op(i)==0x2d)text.append(a.constants.getInt(i.operands[n]));
                else if(n==0&&op(i)==0x2e)text.append(a.constants.getUInt(i.operands[n]));
                else if(n==0&&op(i)==0x2f)text.append(a.constants.getDouble(i.operands[n]));
                else text.append(i.operands[n]);
            }
        }
        for(var e:b.exceptions)text.append("\ncatch:").append(CasStructuralRolesPatch.index(addresses,e.start)).append(':')
            .append(CasStructuralRolesPatch.index(addresses,e.end)).append(':').append(CasStructuralRolesPatch.index(addresses,e.target))
            .append(':').append(qname(a,e.type_index)).append(':').append(qname(a,e.name_index));
        return text.toString();
    }
    static String semantic(ABC a,MethodBody b)throws Exception{return CasStructuralRolesPatch.sha(semanticText(a,b).getBytes(java.nio.charset.StandardCharsets.UTF_8));}
    static void helpers(ABC a)throws Exception{
        var c=a.instance_info.get(a.findClassByName(TYPE));int fields=0,methods=0;
        for(var t:c.instance_traits.traits){String n=name(a,t.name_index);
            if(FIELDS.contains(n)){check(t instanceof TraitSlotConst,"Indexed field kind differs");var s=(TraitSlotConst)t;
                check(s.value_index==0,"Index fields must use native null/false defaults without constructor changes");
                check(name(a,s.type_index).equals(n.equals("apexCommIndex")?"Dictionary":"Boolean"),"Index field type differs");fields++;}
            if(METHODS.contains(n)){methods++;var bb=a.findBody(((TraitMethodGetterSetter)t).method_info);
                for(var i:bb.getCode().code){check(!Set.of(0x40,0x43,0x44,0x67).contains(op(i)),"Index helper has nested/outer/callmethod linkage");
                    if(op(i)==0x46||op(i)==0x4f){String call=name(a,i.operands[0]);check(call.equals("ApexCommDisable")||call.equals("HasFunction"),"Index helper calls native/IO/dispatch work: "+call);}
                    if(op(i)==0x61||op(i)==0x68){String member=name(a,i.operands[0]);check(member==null||FIELDS.contains(member)||STATIC_FIELDS.contains(member),"Index helper writes original listener metadata");}
                }
            }
        }
        check(fields==2&&methods==6,"Index helper inventory differs");
        int statFields=0,statMethods=0;
        for(var t:a.class_info.get(a.findClassByName(TYPE)).static_traits.traits){String n=name(a,t.name_index);
            if(STATIC_FIELDS.contains(n)){check(t instanceof TraitSlotConst,"Index diagnostic field kind differs");var slot=(TraitSlotConst)t;
                check(slot.value_index==0&&"uint".equals(name(a,slot.type_index)),"Index counters must use native zero defaults");statFields++;}
            if(STATIC_METHODS.contains(n)){check(t instanceof TraitMethodGetterSetter,"Index diagnostic method kind differs");statMethods++;
                var b=a.findBody(((TraitMethodGetterSetter)t).method_info);check(b.exceptions.length==0,"Index statistics must be a pure explicit read");
                for(var i:b.getCode().code)check(!Set.of(0x40,0x41,0x42,0x43,0x44,0x45,0x46,0x49,0x4a,0x4c,0x4e,0x4f,0x61,0x68).contains(op(i)),"Index statistics performs an invocation/write");
            }
        }
        check(statFields==5&&statMethods==1,"Index diagnostics inventory differs");
        var has=body(a,"ApexCommIndexedHas");int dictionaries=0;
        for(var i:has.getCode().code)if((op(i)==0x5d||op(i)==0x60)&&"Dictionary".equals(name(a,i.operands[0]))){
            var q=a.constants.getMultiname(i.operands[0]);var ns=a.constants.getNamespace(q.namespace_index);
            check(q.kind==Multiname.QNAME&&ns.kind==Namespace.KIND_PACKAGE&&"flash.utils".equals(a.constants.getString(ns.name_index)),"Index Dictionary binding differs");dictionaries++;}
        check(dictionaries==1 && has.exceptions.length>0,"Index must use native Dictionary and retain allocation-failure fallback");
        for(String n:List.of("ApexCommAdded","ApexCommRemoved"))check(body(a,n).exceptions.length>0,"Index mutation must degrade to original scan on failure");
        for(String n:List.of("ApexCommCanIndex","ApexCommDisable","ApexCommExpose"))check(body(a,n).exceptions.length==0,"Pure index predicate/alias operation acquired an exception dependency");
        for(String n:allMethods())check(semantic(a,body(a,n)).equals(SEMANTIC_PINS.get(n)),"Reviewed index helper semantic bytes differ: "+n);
    }
    static CasStructuralRolesPatch.Rewrite rewrite(ABC a,MethodBody before,String target)throws Exception{
        var old=before.getCode().code;check(old.size()>2&&op(old.get(0))==0xd0&&op(old.get(1))==0x30&&before.exceptions.length==0,"Native communication scope/exception contract differs");
        if(target.equals("HasFunction")||target.equals("GetFunctions")){
            var nativeFirst=CasStructuralRolesPatch.copy(old.get(2));var added=new ArrayList<AVM2Instruction>();AVM2Instruction fallback=null;
            added.add(ins(0xd0));
            if(target.equals("HasFunction")){
                added.add(ins(0xd1));added.add(ins(0x46,method(a,"ApexCommCanIndex").name_index,1));fallback=ins(0x12,0);added.add(fallback);
                added.add(ins(0xd0));added.add(ins(0xd1));added.add(ins(0x46,method(a,"ApexCommIndexedHas").name_index,1));added.add(ins(0x48));
            }else added.add(ins(0x4f,method(a,"ApexCommExpose").name_index,0));
            added.add(nativeFirst);var block=new CasStructuralRolesPatch.Block(2,3,added);
            if(fallback!=null)block.edge(fallback,0,CasStructuralRolesPatch.local(nativeFirst));
            var result=CasStructuralRolesPatch.rewrite(before,List.of(block));int actual=2+added.size()-1;
            result.origins.set(actual,2);result.boundaries.put(2,actual);result.body.max_stack=before.max_stack+2;result.body.setModified();
            CasStructuralRolesPatch.verifyProjection(before,result,result.body);return result;
        }
        String mutation=target.equals("AddFunction")?"push":"splice";int at=-1;
        for(int i=0;i<old.size();i++)if(prop(a,old.get(i),0x4f,mutation)||prop(a,old.get(i),0x46,mutation)){
            // RemoveFunction also pushes deferred removals. Only its actual
            // splice is a committed mutation of mFunctions.
            check(at<0,"Ambiguous native committed listener mutation");at=i;}
        check(at>=0&&op(old.get(at))==0x4f&&old.get(at).operands[1]==(target.equals("AddFunction")?1:2),"Native mutation call ABI differs");
        var added=new ArrayList<AVM2Instruction>();added.add(CasStructuralRolesPatch.copy(old.get(at)));added.add(ins(0xd0));
        if(target.equals("RemoveWidgetsFunctions")){
            int field=-1;for(var t:a.instance_info.get(a.findClassByName(ROW)).instance_traits.traits)if("mFunction".equals(name(a,t.name_index)))field=t.name_index;
            check(field>=0,"Native WidgetFunction function slot absent");int read=-1;
            for(int i=0;i<at;i++)if(prop(a,old.get(i),0x66,"mWidgetName")){check(read<0,"Ambiguous native widget-row read");read=i;}
            check(read>=1&&(op(old.get(read-1))==0xd3||op(old.get(read-1))==0x62),"Native widget-row local differs");
            added.add(CasStructuralRolesPatch.copy(old.get(read-1)));added.add(ins(0x66,field));
        }else added.add(ins(0xd2));
        added.add(ins(0x4f,method(a,target.equals("AddFunction")?"ApexCommAdded":"ApexCommRemoved").name_index,1));
        var result=CasStructuralRolesPatch.rewrite(before,List.of(new CasStructuralRolesPatch.Block(at,at+1,added)));
        result.origins.set(at,at);result.body.max_stack=before.max_stack+2;result.body.setModified();
        CasStructuralRolesPatch.verifyProjection(before,result,result.body);return result;
    }
    static void verify(ABC baseline,ABC candidate,Map<Integer,CasStructuralRolesPatch.Rewrite> rewrites,Map<Integer,String> hashes)throws Exception{
        CasStructuralRolesPatch.prefix(baseline,candidate);
        check(candidate.method_info.size()==baseline.method_info.size()+7&&candidate.bodies.size()==baseline.bodies.size()+7,"Index appended-method inventory differs");
        for(var e:rewrites.entrySet())CasStructuralRolesPatch.verifyProjection(baseline.findBody(e.getKey()),e.getValue(),candidate.findBody(e.getKey()));
        for(var e:hashes.entrySet())check(CasStructuralRolesPatch.sha(candidate.findBody(e.getKey()).getCodeBytes()).equals(e.getValue()),"Serialized index helper/dispatcher bytes changed");
        helpers(candidate);
        var rollback=CasStructuralRolesPatch.reparse(candidate);
        for(int id:rewrites.keySet())CasStructuralRolesPatch.replace(rollback,baseline.findBody(id).clone());
        while(rollback.method_info.size()>baseline.method_info.size())rollback.method_info.remove(rollback.method_info.size()-1);
        while(rollback.bodies.size()>baseline.bodies.size())rollback.bodies.remove(rollback.bodies.size()-1);
        var traits=rollback.instance_info.get(rollback.findClassByName(TYPE)).instance_traits.traits;
        int old=baseline.instance_info.get(baseline.findClassByName(TYPE)).instance_traits.traits.size();check(traits.size()==old+8,"Index appended-trait inventory differs");
        while(traits.size()>old)traits.remove(traits.size()-1);
        var statics=rollback.class_info.get(rollback.findClassByName(TYPE)).static_traits.traits;
        int oldStatic=baseline.class_info.get(baseline.findClassByName(TYPE)).static_traits.traits.size();check(statics.size()==oldStatic+6,"Index diagnostic trait inventory differs");
        while(statics.size()>oldStatic)statics.remove(statics.size()-1);
        rollback.constants=baseline.constants;rollback.resetMethodIndexing();
        check(Arrays.equals(CasStructuralRolesPatch.save(rollback),CasStructuralRolesPatch.save(baseline)),"Index whole-ABC rollback changed unrelated native code/traits/initializers");
        for(var b:baseline.bodies)if(!rewrites.containsKey(b.method_info))check(Arrays.equals(b.getCodeBytes(),candidate.findBody(b.method_info).getCodeBytes()),"Unowned native body changed");
    }
    static void protectedBindings(ABC a,Set<Integer> methods){
        int field=-1;for(var t:a.instance_info.get(a.findClassByName(TYPE)).instance_traits.traits)if("mFunctions".equals(name(a,t.name_index)))field=t.name_index;
        check(field>=0,"Native listener field absent");var declared=a.constants.getMultiname(field);
        for(int id:methods)for(var i:a.findBody(id).getCode().code)if((op(i)==0x66||op(i)==0x5d||op(i)==0x60)&&"mFunctions".equals(name(a,i.operands[0]))){
            var q=a.constants.getMultiname(i.operands[0]);boolean same=q.namespace_index==declared.namespace_index;
            if(q.namespace_set_index>0)for(int ns:a.constants.getNamespaceSet(q.namespace_set_index).namespaces)same|=ns==declared.namespace_index;
            check(same,"Index helper does not bind exact native protected listener array");}
    }
    public static void main(String[] args)throws Exception{
        if(args.length==2&&args[0].equals("--semantic")){var a=CasStructuralRolesPatch.load(args[1]);helpers(a);for(String n:allMethods())System.out.println(n+" "+semantic(a,body(a,n)));return;}
        check(args.length==5,"Use original provider, retained baseline, compiled helpers, output ABC, proof");
        String pin=CasStructuralRolesPatch.sha(Files.readAllBytes(Path.of(args[0]))),tgi=PROVIDERS.get(pin);check(tgi!=null,"Unpinned communication provider");
        var original=CasStructuralRolesPatch.load(args[0]);var baseline=CasStructuralRolesPatch.load(args[1]);var compiled=CasStructuralRolesPatch.load(args[2]);
        sourceAuthority(original,baseline);CasStructuralRolesPatch.prefix(baseline,compiled);
        check(baseline.instance_info.size()==compiled.instance_info.size()&&baseline.findClassByName(TYPE)==compiled.findClassByName(TYPE),"Compiler moved communication class layout");
        helpers(compiled);var candidate=CasStructuralRolesPatch.reparse(baseline);candidate.constants=compiled.constants;
        var traits=candidate.instance_info.get(candidate.findClassByName(TYPE)).instance_traits.traits;
        var statics=candidate.class_info.get(candidate.findClassByName(TYPE)).static_traits.traits;
        var appended=new ArrayList<Trait>();var staticAdded=new ArrayList<Trait>();var ids=new TreeSet<Integer>();
        for(boolean statik:new boolean[]{false,true})for(var t:(statik?compiled.class_info.get(compiled.findClassByName(TYPE)).static_traits:
            compiled.instance_info.get(compiled.findClassByName(TYPE)).instance_traits).traits){String n=name(compiled,t.name_index);
            if(statik?!STATIC_METHODS.contains(n)&&!STATIC_FIELDS.contains(n):!METHODS.contains(n)&&!FIELDS.contains(n))continue;
            var made=t.clone();if(made instanceof TraitSlotConst){((TraitSlotConst)made).slot_id=0;}else{var m=(TraitMethodGetterSetter)made;m.disp_id=0;ids.add(m.method_info);}
            (statik?staticAdded:appended).add(made);}
        check(appended.size()==8&&staticAdded.size()==6&&ids.size()==7,"Index trait inventory differs");
        int delta=body(baseline,"HasFunction").init_scope_depth-body(compiled,"HasFunction").init_scope_depth;check(delta>=0&&delta<=16,"Index helper scope differs");var remap=new HashMap<Integer,Integer>();
        for(int id:ids){int made=candidate.method_info.size();remap.put(id,made);candidate.method_info.add(compiled.method_info.get(id));var bb=compiled.findBody(id).clone();
            bb.method_info=made;bb.init_scope_depth+=delta;bb.max_scope_depth+=delta;
            for(var instruction:bb.getCode().code)if(op(instruction)==0x65)check(instruction.operands[0]>=0&&instruction.operands[0]<bb.max_scope_depth-bb.init_scope_depth,"Helper local activation scope index differs");
            bb.setCode(bb.getCode());bb.setModified();candidate.bodies.add(bb);}
        var allAdded=new ArrayList<Trait>(appended);allAdded.addAll(staticAdded);
        for(var t:allAdded)if(t instanceof TraitMethodGetterSetter)((TraitMethodGetterSetter)t).method_info=remap.get(((TraitMethodGetterSetter)t).method_info);
        traits.addAll(appended);statics.addAll(staticAdded);candidate.resetMethodIndexing();protectedBindings(candidate,new HashSet<>(remap.values()));
        var rewrites=new HashMap<Integer,CasStructuralRolesPatch.Rewrite>();
        for(String n:CHANGED){var before=body(baseline,n);var change=rewrite(candidate,before,n);rewrites.put(before.method_info,change);CasStructuralRolesPatch.replace(candidate,change.body);}
        var hashes=new HashMap<Integer,String>();for(var bb:candidate.bodies)if(bb.method_info>=baseline.method_info.size()||rewrites.containsKey(bb.method_info))hashes.put(bb.method_info,CasStructuralRolesPatch.sha(bb.getCodeBytes()));
        verify(baseline,candidate,rewrites,hashes);candidate=CasStructuralRolesPatch.reparse(candidate);verify(baseline,candidate,rewrites,hashes);
        byte[] data=CasStructuralRolesPatch.save(candidate);Files.write(Path.of(args[3]),data);
        String report="{\"ok\":true,\"provider_resource_tgi\":\""+tgi+"\",\"base_provider_sha256\":\""+pin+"\",\"baseline_swf_sha256\":\""+CasStructuralRolesPatch.sha(Files.readAllBytes(Path.of(args[1])))+"\",\"baseline_abc_sha256\":\""+CasStructuralRolesPatch.sha(CasStructuralRolesPatch.save(baseline))+"\",\"abc_sha256\":\""+CasStructuralRolesPatch.sha(data)+"\",\"changed_native_bodies\":5,\"appended_methods\":7,\"appended_fields\":2,\"appended_static_fields\":5,\"whole_abc_rollback_verified\":true,\"reviewed_helper_semantic_pins_verified\":true,\"protected_field_namespace_verified\":true,\"bound_closure_runtime_eligibility_probe\":true,\"explicit_primitive_diagnostics\":true,\"native_array_dispatch_order_retained\":true,\"public_alias_falls_back_to_original\":true,\"deferred_removal_semantics_retained\":true,\"runtime_qualified\":false,\"hitch_free_claimed\":false}";
        Files.writeString(Path.of(args[4]),report+"\n");System.out.println(report);
    }
}
