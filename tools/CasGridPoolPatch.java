// Persistent staged native CAS widget capacity, after the exact V334 image pass.
// Native reads retain their complete unarmed flow behind narrow owned guards.
import java.nio.file.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;

public class CasGridPoolPatch {
    static final String GRID="olympus.layout.GridLayout", REC="olympus.layout.RecyclingGridLayout";
    static final Map<String,String> BASELINES=Map.of(
        "00aa765a0826342498a8ef176a77d98bcd83bbec7beb5281bf953128bf647dc1","62ECC59A:00000000:12272E1AC0C1F8E2",
        "18544a2c85e5291d0d5becd03e275119c90dd61dff0b84132297b8e8bde5d3b4","62ECC59A:00000000:89D13757C58C2E05");
    static final List<String> REPLACED=List.of("ApexGridBegin","ApexGridDetach","ApexGridDiscard","ApexGridPosition",
        "ApexGridBind","ApexGridNativeGuard","ApexTxnPlan","ApexTxnAdvance");
    static final List<String> ADDED=List.of("ApexGridPoolOwns","ApexGridPoolCoherent","ApexGridPoolSlot","ApexGridPoolViews","ApexGridPoolDisplays",
        "ApexGridPoolNeighbor","ApexGridPoolMap","ApexGridPoolDataIndex","ApexGridPoolPark","ApexGridPoolRestore");
    static final Map<String,String> PINS=Map.ofEntries(
        Map.entry("ApexGridBegin","2c5b07e89b66bd535432f8a7ddda4a928f5855d57e7a1a9ea33d7cb6c1127671"),
        Map.entry("ApexGridDetach","b9aba4da5cc48d0488812f1e1cdd00d8c9559d411489751cb0b2fc9e18eaa476"),
        Map.entry("ApexGridDiscard","d468862c0e8a91d954feee44ab2692d7650f4638ff6fb3df5aa587e3f973ff0d"),
        Map.entry("ApexGridPosition","0900b19597e56a7deacc82d44e60eaf88f7858b696756beca3e20ce7285450cb"),
        Map.entry("ApexGridBind","797522fd82963555d3fb7c2ad7e94072ed00fcc61136ecc8d2372f1f4b299fb7"),
        Map.entry("ApexGridNativeGuard","95aad5d651f6f156a64126da89625ec06357903641a6f04664409e4bbe3004ef"),
        Map.entry("ApexTxnPlan","5ce2ce1c9c7e106fc31ddbc745a958648cd47cb87757be5eb90fc9dbdec24426"),
        Map.entry("ApexTxnAdvance","46d8b10a6c4ec326af4652dc9e00f02d454b3953ae327e56a44cc8d7d403880a"),
        Map.entry("ApexGridPoolOwns","0e718e7927c4d23b053d79a7b0163d50a8f0d54a9956672b29815210c9dd666d"),
        Map.entry("ApexGridPoolCoherent","03c082164f572d2f878c6fdcc153689c23825371ad44d364c27d23af001c8a0c"),
        Map.entry("ApexGridPoolSlot","09a194ef5c647186e531bb099749868105eb7961ff6747f5ff18c2dd66c4af5f"),
        Map.entry("ApexGridPoolViews","664dfae1a0352da3101ef4ec01eb280c5bbbb5e25bb9ebfbb8154294d17c060a"),
        Map.entry("ApexGridPoolDisplays","3b6ffbd0b4c3a34e279d3a73ad19e449c0b8dc798328f742a70e5be75876008c"),
        Map.entry("ApexGridPoolNeighbor","d8d142d2d0a372229f786852785caeea6fa6b189e692ce2317ad2cc1cf703b49"),
        Map.entry("ApexGridPoolMap","a7983a53f59cace1d3eacb94b5e29e97ce4617725225277bf0cbfcc4f6398dcc"),
        Map.entry("ApexGridPoolDataIndex","057831b2dd2532271cef1d360ea89cbd92923840434fb80f41c8489132c84cd4"),
        Map.entry("ApexGridPoolPark","76b08b0d4dc6b1558c8d1b87ceeba06dce7b2368c01ca1c88709c580e0cff554"),
        Map.entry("ApexGridPoolRestore","439b79afaf9f541dc8c8c2c9351a159dd42b5801e28313a1da5522a7451a1e87"));
    record Read(String owner,String method,String helper,int mode){}
    static final List<Read> READS=List.of(
        new Read(GRID,"GetAllCells","ApexGridPoolViews",0),
        new Read(GRID,"GetAllDisplayObjectCells","ApexGridPoolDisplays",0),
        new Read(GRID,"FirstCell","ApexGridPoolNeighbor",1),
        new Read(GRID,"LastCell","ApexGridPoolNeighbor",-1),
        new Read(GRID,"GetNextCell","ApexGridPoolNeighbor",2),
        new Read(GRID,"GetPreviousCell","ApexGridPoolNeighbor",-2),
        new Read(GRID,"GetCellIndexToDataIndex","ApexGridPoolMap",3),
        new Read(REC,"GetDataIndexOfSortedIndex","ApexGridPoolDataIndex",3));
    static void check(boolean value,String message){CasStructuralRolesPatch.check(value,message);}
    static int op(AVM2Instruction i){return CasStructuralRolesPatch.op(i);}
    static AVM2Instruction ins(int code,int...args){return CasStructuralRolesPatch.ins(code,args);}
    static String name(ABC a,int q){return CasStructuralRolesPatch.name(a,q);}
    static TraitMethodGetterSetter method(ABC a,String type,String n){return CasStructuralRolesPatch.trait(a,type,n,false);}
    static MethodBody body(ABC a,String type,String n){return a.findBody(method(a,type,n).method_info);}
    static String hash(byte[] bytes)throws Exception{return CasStructuralRolesPatch.sha(bytes);}
    static List<String> owned(){var n=new ArrayList<>(REPLACED);n.addAll(ADDED);return n;}
    static String semantic(ABC a,MethodBody b)throws Exception{
        String text=CasCommunicationIndexPatch.semanticText(a,b);
        // FFDec's file-private namespace serial is provider dependent and is
        // not necessarily the class index. Normalize only this source file's
        // exact private label; native/private/protected field bindings stay
        // exact and are independently checked by binding().
        text=text.replaceAll("(?<=5:)RecyclingGridLayout\\.as\\$[0-9]+","RecyclingGridLayout.as\\$SELF");
        return hash(text.getBytes(java.nio.charset.StandardCharsets.UTF_8));
    }
    static void helpers(ABC a)throws Exception{
        check(PINS.size()==owned().size(),"Pool helper semantic inventory is not frozen");
        for(String n:owned())check(semantic(a,body(a,REC,n)).equals(PINS.get(n)),"Pool reviewed helper bytes/CFG differ: "+n);
        for(String n:ADDED){
            var trait=method(a,REC,n);var q=a.constants.getMultiname(trait.name_index);var ns=a.constants.getNamespace(q.namespace_index);
            boolean internal=Set.of("ApexGridPoolCoherent","ApexGridPoolSlot","ApexGridPoolPark","ApexGridPoolRestore").contains(n);
            check(trait.kindType==Trait.TRAIT_METHOD&&trait.kindFlags==0&&q.kind==Multiname.QNAME,"Pool helper trait ABI differs: "+n);
            check(internal ? ns.kind==Namespace.KIND_PRIVATE&&a.constants.getString(ns.name_index).equals("olympus.layout:RecyclingGridLayout") :
                ns.kind==Namespace.KIND_PACKAGE&&a.constants.getString(ns.name_index).isEmpty(),"Pool helper visibility differs: "+n);
        }
    }
    static CasStructuralRolesPatch.Rewrite prefix(ABC a,MethodBody before,Read read)throws Exception{
        var original=before.getCode().code;
        check(original.size()>2&&op(original.get(0))==0xd0&&op(original.get(1))==0x30,"Native read scope differs: "+read.method);
        check(before.exceptions.length==0,"Native read has an unreviewed exception region");
        var oldAddresses=CasStructuralRolesPatch.addresses(before);
        for(var i:original)for(int arg:CasStructuralRolesPatch.targetOperands(i))
            check(CasStructuralRolesPatch.index(oldAddresses,CasStructuralRolesPatch.target(i,arg))>2,"Native edge enters pool prefix seam");
        var code=new ArrayList<AVM2Instruction>();var jumps=new ArrayList<AVM2Instruction>();
        code.add(ins(0xd0));code.add(ins(0xb2,a.instance_info.get(a.findClassByName(REC)).name_index));
        var ordinary=ins(0x12,0);code.add(ordinary);jumps.add(ordinary);
        code.add(ins(0xd0));code.add(ins(0x46,method(a,REC,"ApexGridPoolOwns").name_index,0));
        var unarmed=ins(0x12,0);code.add(unarmed);jumps.add(unarmed);
        code.add(ins(0xd0));int argc=0;
        if(Math.abs(read.mode)==1){code.add(ins(0x20));code.add(ins(0x24,read.mode));argc=2;}
        else if(Math.abs(read.mode)==2){code.add(ins(0xd1));code.add(ins(0x24,read.mode>0?1:-1));argc=2;}
        else if(read.mode==3){code.add(ins(0xd1));argc=1;}
        code.add(ins(0x46,method(a,REC,read.helper).name_index,argc));
        code.add(ins(0x80,a.method_info.get(before.method_info).ret_type));code.add(ins(0x48));
        var first=CasStructuralRolesPatch.copy(original.get(2));code.add(first);
        var block=new CasStructuralRolesPatch.Block(2,3,code);
        for(var jump:jumps)block.edge(jump,0,CasStructuralRolesPatch.local(first));
        var result=CasStructuralRolesPatch.rewrite(before,List.of(block));
        int copied=2+code.size()-1;result.origins.set(copied,2);result.boundaries.put(2,copied);
        result.body.max_stack=Math.max(before.max_stack,3);result.body.setModified();
        CasStructuralRolesPatch.verifyProjection(before,result,result.body);return result;
    }
    static void binding(ABC a,Set<Integer> helperIds){
        var declared=new HashMap<String,Integer>();
        for(String type:List.of(GRID,REC))for(var t:a.instance_info.get(a.findClassByName(type)).instance_traits.traits)
            if(t instanceof TraitSlotConst)declared.put(name(a,t.name_index),t.name_index);
        for(int id:helperIds)for(var i:a.findBody(id).getCode().code)if(Set.of(0x5d,0x60,0x61,0x66,0x68).contains(op(i))){
            String n=name(a,i.operands[0]);if(!declared.containsKey(n))continue;
            var nativeName=a.constants.getMultiname(declared.get(n));var use=a.constants.getMultiname(i.operands[0]);
            boolean exact=use.namespace_index==nativeName.namespace_index;
            if(use.namespace_set_index>0)for(int ns:a.constants.getNamespaceSet(use.namespace_set_index).namespaces)exact|=ns==nativeName.namespace_index;
            check(exact,"Pool helper uses wrong native/private field namespace: "+n);
        }
    }
    static Object pop(List<Object> stack){check(!stack.isEmpty(),"Pool disabled VM stack underflow");return stack.remove(stack.size()-1);}
    static void disabled(ABC a,MethodBody b,long stop,boolean recycling)throws Exception{
        var stack=new ArrayList<Object>();Object self=new Object();var code=b.getCode().code;var addresses=CasStructuralRolesPatch.addresses(b);
        for(int pc=0,steps=0;steps<40;steps++){
            var i=code.get(pc);if(i.getAddress()==stop){check(stack.isEmpty(),"Pool prefix changed native entry stack");return;}
            int next=pc+1;
            switch(op(i)){
                case 0xd0 -> stack.add(self);
                case 0x30 -> check(pop(stack)==self,"Pool prefix scope differs");
                case 0xb2 -> {check(pop(stack)==self&&name(a,i.operands[0]).equals("RecyclingGridLayout"),"Pool class scope guard differs");stack.add(recycling);}
                case 0x12 -> {if(!CasStructuralRolesPatch.truth(pop(stack)))next=CasStructuralRolesPatch.index(addresses,CasStructuralRolesPatch.target(i,0));}
                case 0x46 -> {check(pop(stack)==self&&i.operands[1]==0&&name(a,i.operands[0]).equals("ApexGridPoolOwns"),"Disabled pool prefix performs display/read work");stack.add(false);}
                default -> throw new IllegalArgumentException("Disabled pool prefix unreviewed opcode "+op(i));
            }
            pc=next;
        }
        throw new IllegalArgumentException("Pool disabled prefix did not return to native entry");
    }
    static void verify(ABC base,ABC a,Map<Integer,CasStructuralRolesPatch.Rewrite> reads,Map<Integer,String> hashes)throws Exception{
        CasStructuralRolesPatch.prefix(base,a);
        check(a.method_info.size()==base.method_info.size()+ADDED.size()&&a.bodies.size()==base.bodies.size()+ADDED.size(),"Pool appended method inventory differs");
        helpers(a);binding(a,hashes.keySet());
        for(var e:hashes.entrySet())check(hash(a.findBody(e.getKey()).getCodeBytes()).equals(e.getValue()),"Serialized pool helper/native prefix differs");
        for(var e:reads.entrySet()){
            var b=a.findBody(e.getKey());CasStructuralRolesPatch.verifyProjection(base.findBody(e.getKey()),e.getValue(),b);
            long stop=b.getCode().code.get(e.getValue().boundaries.get(2)).getAddress();disabled(a,b,stop,false);disabled(a,b,stop,true);
        }
        var rollback=CasStructuralRolesPatch.reparse(a);
        for(String n:REPLACED)CasStructuralRolesPatch.replace(rollback,body(base,REC,n).clone());
        for(int id:reads.keySet())CasStructuralRolesPatch.replace(rollback,base.findBody(id).clone());
        while(rollback.method_info.size()>base.method_info.size())rollback.method_info.remove(rollback.method_info.size()-1);
        while(rollback.bodies.size()>base.bodies.size())rollback.bodies.remove(rollback.bodies.size()-1);
        var traits=rollback.instance_info.get(rollback.findClassByName(REC)).instance_traits.traits;
        int old=base.instance_info.get(base.findClassByName(REC)).instance_traits.traits.size();
        check(traits.size()==old+ADDED.size(),"Pool adds unknown traits");while(traits.size()>old)traits.remove(traits.size()-1);
        rollback.constants=base.constants;rollback.resetMethodIndexing();
        check(Arrays.equals(CasStructuralRolesPatch.save(rollback),CasStructuralRolesPatch.save(base)),"Pool rollback changed unowned native bodies/traits/signatures/initializers");
    }
    public static void main(String[]args)throws Exception{
        if(args.length==2&&args[0].equals("--semantic")){
            var a=CasStructuralRolesPatch.load(args[1]);for(String n:owned())System.out.println(n+" "+semantic(a,body(a,REC,n)));return;
        }
        check(args.length==4,"Use exact V334 provider, compiled pool helper provider, output ABC, proof");
        String pin=hash(Files.readAllBytes(Path.of(args[0]))),tgi=BASELINES.get(pin);check(tgi!=null,"Unpinned V334 pool baseline");
        var base=CasStructuralRolesPatch.load(args[0]);var compiled=CasStructuralRolesPatch.load(args[1]);helpers(compiled);CasStructuralRolesPatch.prefix(base,compiled);
        var a=CasStructuralRolesPatch.reparse(base);a.constants=compiled.constants;
        int rec=a.findClassByName(REC);check(rec==compiled.findClassByName(REC),"Compiler moved native recycling class");
        int delta=body(base,REC,REPLACED.get(0)).init_scope_depth-body(compiled,REC,REPLACED.get(0)).init_scope_depth;
        check(delta>=0&&delta<=16,"Pool helper scope delta differs");
        var hashes=new HashMap<Integer,String>();
        for(String n:REPLACED){
            var old=body(base,REC,n);var source=body(compiled,REC,n);var b=source.clone();
            check(CasCommunicationIndexPatch.qname(base,base.method_info.get(old.method_info).ret_type).equals(CasCommunicationIndexPatch.qname(compiled,compiled.method_info.get(source.method_info).ret_type)),"Pool method return ABI differs");
            check(base.method_info.get(old.method_info).param_types.length==compiled.method_info.get(source.method_info).param_types.length,"Pool method argument count differs");
            for(int p=0;p<base.method_info.get(old.method_info).param_types.length;p++)check(CasCommunicationIndexPatch.qname(base,base.method_info.get(old.method_info).param_types[p]).equals(CasCommunicationIndexPatch.qname(compiled,compiled.method_info.get(source.method_info).param_types[p])),"Pool argument ABI differs");
            b.method_info=old.method_info;b.init_scope_depth+=delta;b.max_scope_depth+=delta;b.setCode(b.getCode());b.setModified();CasStructuralRolesPatch.replace(a,b);hashes.put(b.method_info,hash(b.getCodeBytes()));
        }
        for(String n:ADDED){
            check(base.instance_info.get(rec).instance_traits.traits.stream().noneMatch(t->name(base,t.name_index).equals(n)),"Pool helper already exists");
            var source=body(compiled,REC,n);int id=a.method_info.size();a.method_info.add(compiled.method_info.get(source.method_info));
            var b=source.clone();b.method_info=id;b.init_scope_depth+=delta;b.max_scope_depth+=delta;b.setCode(b.getCode());b.setModified();a.bodies.add(b);
            var trait=method(compiled,REC,n).clone();trait.method_info=id;trait.disp_id=0;a.instance_info.get(rec).instance_traits.traits.add(trait);hashes.put(id,hash(b.getCodeBytes()));
        }
        a.resetMethodIndexing();var reads=new HashMap<Integer,CasStructuralRolesPatch.Rewrite>();
        for(var read:READS){var before=body(base,read.owner,read.method);var rewritten=prefix(a,before,read);reads.put(before.method_info,rewritten);CasStructuralRolesPatch.replace(a,rewritten.body);hashes.put(before.method_info,hash(rewritten.body.getCodeBytes()));}
        verify(base,a,reads,hashes);a=CasStructuralRolesPatch.reparse(a);verify(base,a,reads,hashes);
        byte[] bytes=CasStructuralRolesPatch.save(a);Files.write(Path.of(args[2]),bytes);
        String report="{\"ok\":true,\"provider_resource_tgi\":\""+tgi+"\",\"baseline_swf_sha256\":\""+pin+"\",\"baseline_abc_sha256\":\""+hash(CasStructuralRolesPatch.save(base))+"\",\"abc_sha256\":\""+hash(bytes)+"\",\"replaced_owned_bodies\":"+REPLACED.size()+",\"guarded_native_read_bodies\":"+READS.size()+",\"appended_methods\":"+ADDED.size()+",\"appended_fields\":0,\"baseline_method_info_count\":"+base.method_info.size()+",\"baseline_method_body_count\":"+base.bodies.size()+",\"unchanged_baseline_bodies\":"+(base.bodies.size()-REPLACED.size()-READS.size())+",\"whole_abc_rollback_verified\":true,\"native_read_projection_verified\":true,\"unarmed_original_native_flow_verified\":true,\"protected_namespace_bindings_verified\":true,\"serialized_owned_bodies_verified\":true,\"all_other_bodies_retained\":true,\"runtime_qualified\":false,\"hitch_free_claimed\":false}";
        Files.writeString(Path.of(args[3]),report+"\n");System.out.println(report);
    }
}
