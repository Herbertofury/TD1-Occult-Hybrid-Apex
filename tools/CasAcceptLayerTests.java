// Synthetic owned guard fragments; no installed game assets or native calls.
// Each fixture is checked both before and after ABC serialization/reparsing.
import java.io.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.avm2.AVM2Code;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
import com.jpexs.decompiler.flash.tags.ABCContainerTag;
import com.jpexs.helpers.MemoryInputStream;

public class CasAcceptLayerTests {
    static AVM2Instruction op(int opcode, int... values) { return new AVM2Instruction(0,opcode,values); }
    static int member(ABC abc, String name) {
        Multiname value=new Multiname(); value.kind=Multiname.QNAME;
        value.name_index=abc.constants.getStringId(name,true);
        value.namespace_index=abc.constants.getNamespaceId(Namespace.KIND_PACKAGE,"",0,true);
        return abc.constants.getMultinameId(value,true);
    }
    static void jumps(List<AVM2Instruction> code, int[][] targets) {
        long[] addresses=new long[code.size()]; long address=0;
        for(int i=0;i<code.size();i++) { addresses[i]=address; address+=code.get(i).getBytesLength(); }
        for(int[] target:targets)
            code.get(target[0]).operands[0]=(int)(addresses[target[1]]-addresses[target[0]]-code.get(target[0]).getBytesLength());
    }
    static void body(ABC abc, InstanceInfo instance, String name, List<AVM2Instruction> code) {
        int index=abc.method_info.size();
        MethodBody body=new MethodBody(abc,new Traits(),new byte[0],new ABCException[0]);
        body.method_info=index; body.max_stack=8; body.max_regs=1; body.max_scope_depth=2;
        body.setCode(new AVM2Code(new ArrayList<>(code))); abc.bodies.add(body);
        abc.method_info.add(new MethodInfo(new int[0],0,0,0,new ValueKind[0],new int[0]));
        TraitMethodGetterSetter trait=new TraitMethodGetterSetter();
        trait.kindType=Trait.TRAIT_METHOD; trait.name_index=member(abc,name); trait.method_info=index;
        instance.instance_traits.traits.add(trait);
    }
    static ABC fixture(String variant) {
        ABC abc=new ABC((ABCContainerTag)null);
        InstanceInfo instance=new InstanceInfo(new Traits()); instance.interfaces=new int[0]; abc.instance_info.add(instance);
        ClassInfo clazz=new ClassInfo(new Traits()); clazz.cinit_index=0; abc.class_info.add(clazz);
        int layer=member(abc,"occultLayer"), client=member(abc,"client"), sim=member(abc,"sim"), error=member(abc,"Error");
        int integer=member(abc,"int"), booleanType=member(abc,"Boolean"), other=member(abc,"otherLayer");
        List<AVM2Instruction> preflight=new ArrayList<>(List.of(
            op(0x65,1),op(0x6c,2),op(0x66,client),op(0x66,sim),op(0x66,variant.equals("preflight-field")?other:layer),
            op(0x60,variant.equals("preflight-type")?booleanType:integer),op(0xb3),op(0x96),op(0x2a),op(0x11,0),op(0x29),
            op(0x65,1),op(0x6c,2),op(0x66,client),op(0x66,sim),op(0x66,layer),op(0x73),
            op(0x24,variant.equals("preflight-zero")?1:0),op(0xab),op(0x96),op(variant.equals("preflight-inverted")?0x11:0x12,0),
            op(0x5d,error),op(0x2c,abc.constants.getStringId("Unverified layer",true)),op(0x4a,error,1),op(0x03),op(0x47)));
        jumps(preflight,new int[][]{{9,variant.equals("preflight-bypass")?25:20},{20,25}});
        body(abc,instance,"ApexReadback",preflight);
        List<AVM2Instruction> commit=new ArrayList<>(List.of(
            op(0x60,member(abc,"CommunicationManager")),
            op(0x2c,abc.constants.getStringId(variant.equals("commit-getter")?"OtherGetter":"CASGetSimInfo",true)),
            op(0x20),op(0x26),op(0x46,member(abc,"CallGameService"),3),op(0x80,member(abc,"Object")),op(0x6d,8),
            op(0x65,1),op(0x6c,8),op(0x66,variant.equals("commit-field")?other:layer),op(0x10,0),op(0x20),
            op(variant.equals("commit-coerced")?0x73:0x82),op(0x6d,11),
            op(0x65,1),op(0x6c,variant.equals("commit-slot")?12:11),
            op(0x60,variant.equals("commit-type")?booleanType:integer),op(0xb3),op(0x96),op(0x2a),op(0x11,0),op(0x29),
            op(0x65,1),op(0x6c,11),op(0x73),op(0x24,variant.equals("commit-zero")?1:0),op(0xab),op(0x96),op(0x2a),op(0x11,0)));
        int joining=commit.size();
        if(variant.equals("valid-chain")) commit.addAll(List.of(op(0x2a),op(0x11,0)));
        int refusal=commit.size(); commit.addAll(List.of(op(0x12,0),op(0x5d,error),
            op(0x2c,abc.constants.getStringId("Native preconditions changed",true)),op(0x4a,error,1),op(0x03)));
        int saving=commit.size();
        commit.addAll(List.of(op(0x2c,abc.constants.getStringId("SaveAndExitCAS",true)),op(0x47)));
        List<int[]> targets=new ArrayList<>(List.of(new int[]{10,12},new int[]{20,joining},new int[]{29,joining},new int[]{refusal,saving}));
        if(variant.equals("valid-chain")) targets.add(new int[]{joining+1,refusal});
        if(variant.equals("commit-bypass-type")) targets.get(1)[1]=saving;
        if(variant.equals("commit-bypass-zero")) targets.get(2)[1]=saving;
        if(variant.equals("commit-refusal-does-not-throw")) commit.set(refusal+4,op(0x02));
        jumps(commit,targets.toArray(new int[0][]));
        if(variant.equals("commit-late-refusal")) {
            commit.add(0,op(0x2c,abc.constants.getStringId("SaveAndExitCAS",true)));
            // The production gate records the last service reference; remove
            // the later name rather than introducing an unrelated duplicate.
            commit.set(saving+1,op(0x2c,abc.constants.getStringId("OtherService",true)));
        }
        body(abc,instance,"ApexAccept",commit);
        return abc;
    }
    static void check(ABC abc, String variant, String expected) {
        try {
            CasBytecodePatch.verifyAcceptPrimaryLayerOnly(abc,abc.instance_info.get(0));
            if(expected!=null) throw new AssertionError("Invalid layer gate accepted: "+variant);
        } catch(IllegalArgumentException error) {
            if(expected==null || !error.getMessage().contains(expected))
                throw new AssertionError("Unexpected rejection: "+variant+": "+error.getMessage(),error);
        }
    }
    public static void main(String[] args)throws Exception {
        Map<String,String> cases=new LinkedHashMap<>();
        cases.put("valid",null); cases.put("valid-chain",null);
        for(String variant:List.of("preflight-field","preflight-type","preflight-zero","preflight-bypass","preflight-inverted"))
            cases.put(variant,"intent lacks an exact typed primary-layer");
        for(String variant:List.of("commit-getter","commit-field","commit-coerced","commit-slot","commit-type", "commit-zero",
                "commit-bypass-type","commit-bypass-zero","commit-refusal-does-not-throw","commit-late-refusal"))
            cases.put(variant,"native commit lacks a fresh raw typed primary-layer");
        for(var test:cases.entrySet()) {
            ABC abc=fixture(test.getKey()); check(abc,test.getKey(),test.getValue());
            ByteArrayOutputStream output=new ByteArrayOutputStream(); abc.saveToStream(output);
            ABC parsed=new ABC(new ABCInputStream(new MemoryInputStream(output.toByteArray())),null,null);
            check(parsed,test.getKey(),test.getValue());
        }
        System.out.println("{\"synthetic_fixtures\":17,\"serialized_rechecks\":17,\"all_passed\":true}");
    }
}
