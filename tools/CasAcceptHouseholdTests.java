// Synthetic structural fixtures only; no installed game assets are required.
// Every expected rejection is also checked after ABC serialization/reparsing.
import java.io.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.avm2.AVM2Code;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
import com.jpexs.decompiler.flash.tags.ABCContainerTag;
import com.jpexs.helpers.MemoryInputStream;

public class CasAcceptHouseholdTests {
    static AVM2Instruction op(int opcode, int... values) {
        return new AVM2Instruction(0,opcode,values);
    }
    static int member(ABC abc, String name) {
        Multiname value=new Multiname(); value.kind=Multiname.QNAME;
        value.name_index=abc.constants.getStringId(name,true);
        value.namespace_index=abc.constants.getNamespaceId(Namespace.KIND_PACKAGE,"",0,true);
        return abc.constants.getMultinameId(value,true);
    }
    static void body(ABC abc, InstanceInfo instance, String name, List<AVM2Instruction> code) {
        int index=abc.method_info.size();
        MethodBody body=new MethodBody(abc,new Traits(),new byte[0],new ABCException[0]);
        body.method_info=index; body.max_stack=4; body.max_regs=1;
        body.setCode(new AVM2Code(new ArrayList<>(code))); abc.bodies.add(body);
        abc.method_info.add(new MethodInfo(new int[0],0,0,0,new ValueKind[0],new int[0]));
        TraitMethodGetterSetter trait=new TraitMethodGetterSetter();
        trait.kindType=Trait.TRAIT_METHOD; trait.name_index=member(abc,name); trait.method_info=index;
        instance.instance_traits.traits.add(trait);
    }
    static ABC fixture(String variant) {
        ABC abc=new ABC((ABCContainerTag)null);
        InstanceInfo instance=new InstanceInfo(new Traits()); instance.interfaces=new int[0];
        abc.instance_info.add(instance);
        ClassInfo clazz=new ClassInfo(new Traits()); clazz.cinit_index=0; abc.class_info.add(clazz);
        Multiname late=new Multiname(); late.kind=Multiname.MULTINAMEL;
        int indexed=abc.constants.getMultinameId(late,true);
        int household=member(abc,variant.equals("wrong-observed-field")?"otherField":"householdId");
        List<AVM2Instruction> preflight=new ArrayList<>(List.of(
            op(0x24,variant.equals("preflight-index")?5:6),op(0x66,indexed),
            op(variant.equals("untyped-request")?0x73:0x85),op(0x6d,8),
            op(0x66,household),op(0x70),op(0x65,1),op(0x6c,variant.equals("preflight-slot")?9:8),
            op(variant.equals("preflight-branch")?0x12:0x13,0),op(0x47)));
        if(variant.equals("duplicate-index"))
            preflight.addAll(0,List.of(op(0x24,6),op(0x66,indexed),op(0x85),op(0x6d,9)));
        body(abc,instance,"ApexReadback",preflight);
        List<AVM2Instruction> commit=new ArrayList<>(List.of(
            op(0x24,variant.equals("commit-index")?5:6),op(0x66,indexed),op(0x70),op(0x85),op(0x6d,4),
            op(0x66,household),op(0x70),op(0x10,0),op(0x2c,abc.constants.getStringId("",true)),op(0x85),op(0x6d,10),
            op(0x65,1),op(0x6c,10),op(0x65,1),op(0x6c,variant.equals("commit-slot")?5:4),op(0xab),op(0x96),
            op(0x2c,abc.constants.getStringId("SaveAndExitCAS",true)),op(0x47)));
        if(variant.equals("late-comparison")) {
            var save=commit.remove(commit.size()-2); commit.add(0,save);
        }
        body(abc,instance,"ApexAccept",commit);
        return abc;
    }
    static void check(ABC abc, String variant, String expected) {
        try {
            CasBytecodePatch.verifyAcceptHouseholdBinding(abc,abc.instance_info.get(0));
            if(expected!=null) throw new AssertionError("Invalid household binding accepted: "+variant);
        } catch(IllegalArgumentException error) {
            if(expected==null||!error.getMessage().contains(expected))
                throw new AssertionError("Unexpected rejection: "+variant+": "+error.getMessage(),error);
        }
    }
    public static void main(String[] args)throws Exception {
        Map<String,String> cases=new LinkedHashMap<>();
        cases.put("valid",null);
        cases.put("preflight-index","wire field 6");
        cases.put("commit-index","wire field 6");
        cases.put("untyped-request","String slot");
        cases.put("preflight-slot","intent does not compare");
        cases.put("preflight-branch","intent does not compare");
        cases.put("commit-slot","native commit does not compare");
        cases.put("late-comparison","native commit does not compare");
        cases.put("wrong-observed-field","intent does not compare");
        cases.put("duplicate-index","read ambiguously");
        for(var test:cases.entrySet()) {
            ABC abc=fixture(test.getKey()); check(abc,test.getKey(),test.getValue());
            ByteArrayOutputStream output=new ByteArrayOutputStream(); abc.saveToStream(output);
            ABC parsed=new ABC(new ABCInputStream(new MemoryInputStream(output.toByteArray())),null,null);
            check(parsed,test.getKey(),test.getValue());
        }
        System.out.println("{\"synthetic_fixtures\":10,\"serialized_rechecks\":10,\"all_passed\":true}");
    }
}
