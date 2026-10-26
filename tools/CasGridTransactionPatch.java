// Authenticated, post-profiler native incremental grid adapter.
// Default native paths stay original behind pure unarmed guards.
import java.io.*;
import java.nio.file.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;

public class CasGridTransactionPatch {
    static final String GRID="olympus.layout.GridLayout", REC="olympus.layout.RecyclingGridLayout", SEL="olympus.layout.SelectableRecyclingGridLayout";
    static void check(boolean b,String s){CasStructuralRolesPatch.check(b,s);}
    static String sha(byte[] b)throws Exception{return CasStructuralRolesPatch.sha(b);}
    static ABC load(String p)throws Exception{return CasStructuralRolesPatch.load(p);}
    static byte[] save(ABC a)throws Exception{return CasStructuralRolesPatch.save(a);}
    static ABC reparse(ABC a)throws Exception{return CasStructuralRolesPatch.reparse(a);}
    static String name(ABC a,int n){return CasStructuralRolesPatch.name(a,n);}
    static MethodBody body(ABC a,String c,String n){return n.equals("@SuppressUpdates") ? a.findBody(CasGridBytecodePatch.accessor(a,Trait.TRAIT_SETTER).method_info) : CasStructuralRolesPatch.body(a,c,n,false);}
    static int op(AVM2Instruction i){return CasStructuralRolesPatch.op(i);}
    static AVM2Instruction ins(int n,int... operands){return CasStructuralRolesPatch.ins(n,operands);}
    static boolean owned(String n){return !n.equals("ApexGridProviderIdentity") && (n.startsWith("ApexGrid") || n.startsWith("ApexTxn") || n.equals("apexGridState"));}
    static TraitMethodGetterSetter method(ABC a,String n){return CasStructuralRolesPatch.trait(a,REC,n,false);}
    record Target(String owner,String method,String kind,String helper,int args,String returns){}
    static final List<Target> TARGETS=List.of(
        new Target(GRID,"CreateCell","","ApexGridCaptureNewCell",3,"capture"),
        new Target(REC,"@SuppressUpdates","","ApexGridSuppressionChanged",1,"continue"),
        new Target(REC,"ResetAndPositionCells","reset","ApexGridNativeGuard",0,"void"),
        new Target(REC,"PositionCells","position","ApexGridNativeGuard",0,"void"),
        new Target(REC,"CycleCells","scroll","ApexGridNativeGuard",1,"false"),
        new Target(REC,"OnFeedUpdate","update","ApexGridNativeGuard",1,"void"),
        new Target(REC,"OnFeedAdd","add","ApexGridNativeGuard",1,"void"),
        new Target(REC,"OnFeedAddToFront","front","ApexGridNativeGuard",1,"void"),
        new Target(REC,"OnFeedRemove","remove","ApexGridNativeGuard",1,"void"),
        new Target(REC,"OnFeedRemoveAll","removeAll","ApexGridNativeGuard",1,"void"),
        new Target(REC,"OnFeedSortFilter","sort","ApexGridNativeGuard",1,"void"),
        new Target(REC,"SetCellView","","ApexGridNativeSetCellView",3,"void"),
        new Target(REC,"ApexProfileResetAndPositionCells","profile","ApexGridNativeGuard",0,"profile"),
        new Target(GRID,"SetCellBounds","bounds","ApexGridNativeGuard",1,"void"),
        new Target(GRID,"SetCellPadding","padding","ApexGridNativeGuard",1,"void"),
        new Target(GRID,"OnCellEventDispatched","input","ApexGridNativeGuard",1,"void"),
        new Target(GRID,"OnRedrawRequest","redraw","ApexGridNativeGuard",1,"void"),
        new Target(SEL,"UpdateSelectionInCells","selection","ApexGridNativeGuard",0,"void"));

    static CasStructuralRolesPatch.Rewrite guard(ABC abc,MethodBody before,Target target)throws Exception{
        var original=before.getCode().code;
        check(original.size()>2 && op(original.get(0))==0xd0 && op(original.get(1))==0x30,"Native scope prologue differs: "+target.method);
        check(before.exceptions.length==0,"Native guard target has unreviewed exception regions: "+target.method);
        int seam=2;
        if(target.returns.equals("capture")) {
            seam=-1;
            for(int n=2;n<original.size();n++)if(op(original.get(n))==0xd7 && op(original.get(n-1))==0x80 && name(abc,original.get(n-1).operands[0]).equals("IView")) {
                check(seam==-1,"Ambiguous native constructor IView store");seam=n+1;
            }
            check(seam>2,"Native factory constructor/pre-width boundary differs");
        }
        // No edge may enter the replaced boundary from within the native body.
        var nativeAddresses=CasStructuralRolesPatch.addresses(before);
        for(var i:original)for(int operand:CasStructuralRolesPatch.targetOperands(i))
            check(CasStructuralRolesPatch.index(nativeAddresses,CasStructuralRolesPatch.target(i,operand))>2 &&
                CasStructuralRolesPatch.index(nativeAddresses,CasStructuralRolesPatch.target(i,operand))!=seam,"Native edge enters guarded boundary");
        var code=new ArrayList<AVM2Instruction>();var jumps=new ArrayList<AVM2Instruction>();
        if(target.owner.equals(GRID)){
            code.add(ins(0xd0));code.add(ins(0xb2,abc.instance_info.get(abc.findClassByName(REC)).name_index));
            var no=ins(0x12,0);code.add(no);jumps.add(no);
        }
        code.add(ins(0xd0));
        if(target.returns.equals("capture")) {
            code.add(ins(0xd3));code.add(ins(0x4f,method(abc,target.helper).name_index,1));
        }else if(target.returns.equals("continue")) {
            code.add(ins(0xd1));code.add(ins(0x4f,method(abc,target.helper).name_index,1));
        }else if(target.helper.equals("ApexGridNativeSetCellView")){
            code.add(ins(0xd1));code.add(ins(0xd2));code.add(ins(0xd3));
            code.add(ins(0x46,method(abc,target.helper).name_index,3));
        }else{
            code.add(ins(0x2c,abc.constants.getStringId(target.kind,true)));
            code.add(target.args==0?ins(0x20):ins(0xd1));
            code.add(ins(0x46,method(abc,target.helper).name_index,2));
        }
        if(!target.returns.equals("continue") && !target.returns.equals("capture")) {var originalPath=ins(0x12,0);code.add(originalPath);jumps.add(originalPath);}
        if(target.returns.equals("continue") || target.returns.equals("capture")){}
        else if(target.returns.equals("false")){code.add(ins(0x27));code.add(ins(0x48));}
        else if(target.returns.equals("profile")){
            code.add(ins(0xd0));code.add(ins(0x46,method(abc,"ApexGridQueuedProfile").name_index,0));code.add(ins(0x48));
        }else code.add(ins(0x47));
        var first=CasStructuralRolesPatch.copy(original.get(seam));code.add(first);
        var block=new CasStructuralRolesPatch.Block(seam,seam+1,code);
        for(var branch:jumps)block.edge(branch,0,CasStructuralRolesPatch.local(first));
        var result=CasStructuralRolesPatch.rewrite(before,List.of(block));
        int copiedIndex=seam+code.size()-1;result.origins.set(copiedIndex,seam);result.boundaries.put(seam,copiedIndex);
        result.body.max_stack=Math.max(before.max_stack,4);result.body.setModified();
        CasStructuralRolesPatch.verifyProjection(before,result,result.body);
        return result;
    }
    static void verify(ABC baseline,ABC candidate,Map<Integer,CasStructuralRolesPatch.Rewrite> rewrites,
                       int addedMethods,int addedTraits,Map<Integer,String> hashes)throws Exception{
        CasStructuralRolesPatch.prefix(baseline,candidate);
        check(candidate.method_info.size()==baseline.method_info.size()+addedMethods && candidate.bodies.size()==baseline.bodies.size()+addedMethods,"Appended native method inventory differs");
        for(var entry:rewrites.entrySet())CasStructuralRolesPatch.verifyProjection(baseline.findBody(entry.getKey()),entry.getValue(),candidate.findBody(entry.getKey()));
        for(var entry:hashes.entrySet())check(sha(candidate.findBody(entry.getKey()).getCodeBytes()).equals(entry.getValue()),"Serialized helper/guard bytes differ");
        var rollback=reparse(candidate);
        for(int id:rewrites.keySet())CasStructuralRolesPatch.replace(rollback,baseline.findBody(id).clone());
        while(rollback.bodies.size()>baseline.bodies.size())rollback.bodies.remove(rollback.bodies.size()-1);
        while(rollback.method_info.size()>baseline.method_info.size())rollback.method_info.remove(rollback.method_info.size()-1);
        var traits=rollback.instance_info.get(rollback.findClassByName(REC)).instance_traits.traits;
        int oldTraits=baseline.instance_info.get(baseline.findClassByName(REC)).instance_traits.traits.size();
        check(traits.size()==oldTraits+addedTraits,"Appended trait inventory differs");
        while(traits.size()>oldTraits)traits.remove(traits.size()-1);
        rollback.constants=baseline.constants;rollback.resetMethodIndexing();
        check(Arrays.equals(save(rollback),save(baseline)),"Whole-ABC rollback changed an unowned native class/method/signature/initializer");
        for(var b:baseline.bodies)if(!rewrites.containsKey(b.method_info))
            check(Arrays.equals(b.getCodeBytes(),candidate.findBody(b.method_info).getCodeBytes()),"Unowned native body differs");
    }

    static Object pop(List<Object> stack){check(!stack.isEmpty(),"Default-path VM stack underflow");return stack.remove(stack.size()-1);}
    static Object disabled(ABC a,MethodBody b,boolean recycling,long stop,Object[] arguments,int depth)throws Exception{return disabledAt(a,b,recycling,stop,arguments,depth,0);}
    static Object disabledAt(ABC a,MethodBody b,boolean recycling,long stop,Object[] arguments,int depth,int start)throws Exception{
        check(depth<4,"Default native guard unexpectedly recurses");Object self=new Object();Object[] locals=new Object[b.max_regs];locals[0]=self;
        for(int i=0;i<arguments.length && i+1<locals.length;i++)locals[i+1]=arguments[i];
        var stack=new ArrayList<Object>();var code=b.getCode().code;var addresses=CasStructuralRolesPatch.addresses(b);
        for(int pc=start,steps=0;steps<256;steps++){
            var i=code.get(pc);if(i.getAddress()==stop){check(stack.isEmpty(),"Disabled prefix changes original operand stack");return "original";}
            int next=pc+1;Object x,y;
            switch(op(i)){
                case 0xd0,0xd1,0xd2,0xd3 -> stack.add(locals[op(i)-0xd0]);
                case 0xd4,0xd5,0xd6,0xd7 -> locals[op(i)-0xd4]=pop(stack);
                case 0x62 -> stack.add(locals[i.operands[0]]);
                case 0x63 -> locals[i.operands[0]]=pop(stack);
                case 0x20 -> stack.add(null);
                case 0x26 -> stack.add(true);
                case 0x27 -> stack.add(false);
                case 0x2c -> stack.add(a.constants.getString(i.operands[0]));
                case 0x30,0x29 -> pop(stack);
                case 0x2a -> stack.add(stack.get(stack.size()-1));
                case 0x09,0xef,0xf0,0xf1,0x80,0x82 -> {}
                case 0x66 -> {check(name(a,i.operands[0]).equals("apexGridState") && pop(stack)==self,"Unarmed guard performs an unreviewed native read");stack.add(null);}
                case 0x60 -> {check(name(a,i.operands[0]).equals("apexGridState"),"Unarmed guard resolves a native/IO/global class");stack.add(null);}
                case 0xb2 -> {pop(stack);check(name(a,i.operands[0]).equals("RecyclingGridLayout"),"Unexpected class test");stack.add(recycling);}
                case 0xab,0xac -> {y=pop(stack);x=pop(stack);stack.add(x==y || x!=null&&x.equals(y));}
                case 0x96 -> stack.add(!CasStructuralRolesPatch.truth(pop(stack)));
                case 0x76 -> stack.add(CasStructuralRolesPatch.truth(pop(stack)));
                case 0x10 -> next=CasStructuralRolesPatch.index(addresses,CasStructuralRolesPatch.target(i,0));
                case 0x11,0x12 -> {boolean v=CasStructuralRolesPatch.truth(pop(stack));if(v==(op(i)==0x11))next=CasStructuralRolesPatch.index(addresses,CasStructuralRolesPatch.target(i,0));}
                case 0x13,0x14,0x19,0x1a -> {y=pop(stack);x=pop(stack);boolean equal=x==y||x!=null&&x.equals(y);if(equal==(op(i)==0x13||op(i)==0x19))next=CasStructuralRolesPatch.index(addresses,CasStructuralRolesPatch.target(i,0));}
                case 0x46,0x4f -> {
                    int argc=i.operands[1];Object[] args=new Object[argc];for(int n=argc-1;n>=0;n--)args[n]=pop(stack);check(pop(stack)==self,"Guard changed native receiver");
                    String member=name(a,i.operands[0]);check(member.equals("ApexGridNativeGuard")||member.equals("ApexGridNativeSetCellView")||member.equals("ApexGridSuppressionChanged")||member.equals("ApexGridCaptureNewCell"),"Unarmed guard calls native/IO/display work");
                    Object value=disabled(a,body(a,REC,member),recycling,-1,args,depth+1);if(op(i)==0x46)stack.add(value);
                }
                case 0x48 -> {Object value=pop(stack);check(stack.isEmpty(),"Default guard return stack differs");return value;}
                case 0x47 -> {check(stack.isEmpty(),"Default guard void stack differs");return null;}
                default -> throw new IllegalArgumentException("Unarmed guard uses unreviewed opcode "+op(i));
            }
            pc=next;
        }
        throw new IllegalArgumentException("Default native guard failed to terminate");
    }
    static void verifyDisabled(ABC candidate,Map<Integer,CasStructuralRolesPatch.Rewrite> rewrites)throws Exception{
        for(var target:TARGETS){var b=body(candidate,target.owner,target.method);var rewrite=rewrites.get(b.method_info);
            if(target.returns.equals("capture")) {
                int start=0;while(start<rewrite.origins.size() && rewrite.origins.get(start)>=0)start++;
                int end=start;while(end<rewrite.origins.size() && rewrite.origins.get(end)<0)end++;
                long stop=b.getCode().code.get(end).getAddress();
                check("original".equals(disabledAt(candidate,b,true,stop,new Object[]{null,null,new Object()},0,start)),"Unarmed factory capture changes native flow");
                check("original".equals(disabledAt(candidate,b,false,stop,new Object[]{null,null,new Object()},0,start)),"Ordinary grid factory capture changes native flow");
                continue;
            }
            long stop=b.getCode().code.get(rewrite.boundaries.get(2)).getAddress();Object[] args=new Object[]{null,null,false};
            check("original".equals(disabled(candidate,b,true,stop,args,0)),"Unarmed recycling grid changed default native control flow: "+target.method);
            if(target.owner.equals(GRID))check("original".equals(disabled(candidate,b,false,stop,args,0)),"Ordinary grid changed default native control flow");
        }
        check(Boolean.FALSE.equals(disabled(candidate,body(candidate,REC,"ApexGridNeedsWork"),true,-1,new Object[0],0)),"Unarmed NeedsWork performs native/shape work");
    }
    static void protectedBindings(ABC candidate,Set<Integer> helpers){
        var fields=new HashMap<String,Integer>();
        for(String type:List.of(GRID,REC))for(var t:candidate.instance_info.get(candidate.findClassByName(type)).instance_traits.traits)
            if(t instanceof TraitSlotConst && !name(candidate,t.name_index).equals("apexGridState"))fields.put(name(candidate,t.name_index),t.name_index);
        for(int id:helpers)for(var i:candidate.findBody(id).getCode().code)if(Set.of(0x5d,0x60,0x61,0x66,0x68).contains(op(i))){
            String member=name(candidate,i.operands[0]);if(!fields.containsKey(member))continue;
            var declared=candidate.constants.getMultiname(fields.get(member));var used=candidate.constants.getMultiname(i.operands[0]);
            boolean found=used.namespace_index==declared.namespace_index;
            if(used.namespace_set_index>0)for(int ns:candidate.constants.getNamespaceSet(used.namespace_set_index).namespaces)found|=ns==declared.namespace_index;
            check(found,"Appended helper does not bind exact retained field namespace: "+member);
        }
    }

    public static void main(String[] args)throws Exception{
        check(args.length==5,"Use original provider, retained provider, compiler provider, output ABC, report");
        String originalHash=sha(Files.readAllBytes(Path.of(args[0])));
        var provider=CasGridBytecodePatch.PINS.get(originalHash);check(provider!=null,"Unauthenticated grid provider");
        ABC original=load(args[0]),baseline=load(args[1]),compiled=load(args[2]);
        CasGridBytecodePatch.verify(original,baseline,provider.tgi());
        CasStructuralRolesPatch.prefix(baseline,compiled);
        check(baseline.instance_info.size()==compiled.instance_info.size() && baseline.findClassByName(REC)==compiled.findClassByName(REC),"Compiler class layout moved");
        ABC candidate=reparse(baseline);candidate.constants=compiled.constants;
        var originalTraits=baseline.instance_info.get(baseline.findClassByName(REC)).instance_traits.traits;
        var appended=new ArrayList<Trait>();var ids=new TreeSet<Integer>();
        for(var trait:compiled.instance_info.get(compiled.findClassByName(REC)).instance_traits.traits)if(owned(name(compiled,trait.name_index))){
            for(var old:originalTraits)check(!name(baseline,old.name_index).equals(name(compiled,trait.name_index)),"Owned name already exists");
            check(trait instanceof TraitSlotConst || trait instanceof TraitMethodGetterSetter,"Unexpected owned trait kind");
            var made=trait.clone();
            if(made instanceof TraitSlotConst){var slot=(TraitSlotConst)made;check(name(compiled,slot.type_index).equals("Object") && slot.value_index==0,"State field must default null without initializer");slot.slot_id=0;}
            else{var method=(TraitMethodGetterSetter)made;ids.add(method.method_info);method.disp_id=0;}
            appended.add(made);
        }
        check(appended.size()>25 && ids.size()==appended.size()-1,"Expected one state field plus native transaction helpers");
        var remap=new HashMap<Integer,Integer>();int scopeDelta=body(baseline,REC,"PositionCells").init_scope_depth-body(compiled,REC,"PositionCells").init_scope_depth;
        check(scopeDelta>=0 && scopeDelta<=16,"Native helper lexical scope differs");
        for(int oldId:ids){
            int id=candidate.method_info.size();remap.put(oldId,id);candidate.method_info.add(compiled.method_info.get(oldId));
            var b=compiled.findBody(oldId).clone();b.method_info=id;b.init_scope_depth+=scopeDelta;b.max_scope_depth+=scopeDelta;
            for(var i:b.getCode().code)check(op(i)!=0x40 && op(i)!=0x43 && op(i)!=0x44 && op(i)!=0x67,"Helper contains unreviewed nested/outer/callmethod linkage");
            b.setCode(b.getCode());b.setModified();candidate.bodies.add(b);
        }
        for(var trait:appended)if(trait instanceof TraitMethodGetterSetter){var t=(TraitMethodGetterSetter)trait;t.method_info=remap.get(t.method_info);}
        candidate.instance_info.get(candidate.findClassByName(REC)).instance_traits.traits.addAll(appended);candidate.resetMethodIndexing();
        protectedBindings(candidate,new HashSet<>(remap.values()));
        var rewrites=new HashMap<Integer,CasStructuralRolesPatch.Rewrite>();
        for(var target:TARGETS){
            var before=body(baseline,target.owner,target.method);var result=guard(candidate,before,target);
            check(rewrites.put(before.method_info,result)==null,"Duplicate native guard target");CasStructuralRolesPatch.replace(candidate,result.body);
        }
        CasStructuralRolesPatch.fixtures(candidate);
        var hashes=new HashMap<Integer,String>();for(var b:candidate.bodies)if(b.method_info>=baseline.method_info.size() || rewrites.containsKey(b.method_info))hashes.put(b.method_info,sha(b.getCodeBytes()));
        verify(baseline,candidate,rewrites,ids.size(),appended.size(),hashes);var saved=reparse(candidate);verify(baseline,saved,rewrites,ids.size(),appended.size(),hashes);verifyDisabled(saved,rewrites);
        byte[] bytes=save(saved);Files.write(Path.of(args[3]),bytes);
        String report="{\"ok\":true,\"provider_resource_tgi\":\""+provider.tgi()+"\",\"base_provider_sha256\":\""+originalHash+"\",\"baseline_swf_sha256\":\""+sha(Files.readAllBytes(Path.of(args[1])))+"\",\"abc_sha256\":\""+sha(bytes)+"\",\"original_method_info_count\":"+original.method_info.size()+",\"original_method_body_count\":"+original.bodies.size()+",\"baseline_method_info_count\":"+baseline.method_info.size()+",\"baseline_method_body_count\":"+baseline.bodies.size()+",\"guarded_original_native_bodies\":"+(rewrites.size()-1)+",\"guarded_existing_adapter_bodies\":1,\"unchanged_original_native_bodies\":"+(original.bodies.size()-rewrites.size()+1)+",\"guarded_native_bodies\":"+rewrites.size()+",\"unchanged_baseline_bodies\":"+(baseline.bodies.size()-rewrites.size())+",\"appended_methods\":"+ids.size()+",\"appended_fields\":1,\"whole_abc_rollback_verified\":true,\"serialized_projection_verified\":true,\"protected_field_namespace_bindings_verified\":true,\"explicit_jump_switch_exception_fixtures\":true,\"unarmed_original_native_flow_verified\":true,\"runtime_qualified\":false,\"hitch_free_claimed\":false}";
        Files.writeString(Path.of(args[4]),report+"\n");System.out.println(report);
    }
}
