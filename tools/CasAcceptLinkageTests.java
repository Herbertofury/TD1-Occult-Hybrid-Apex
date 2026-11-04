// Synthetic, redistributable ABC linkage fixtures. No EA assets or game access.
// Compile with CasBytecodePatch.java and the public FFDec jar, then run this
// class. Every fixture is checked again after ABC serialization and reparsing.
import java.io.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.avm2.AVM2Code;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
import com.jpexs.decompiler.flash.tags.ABCContainerTag;
import com.jpexs.helpers.MemoryInputStream;

public class CasAcceptLinkageTests {
    static int qname(ABC abc, String namespace, String name) {
        Multiname member = new Multiname();
        member.kind = Multiname.QNAME;
        member.name_index = abc.constants.getStringId(name, true);
        member.namespace_index = abc.constants.getNamespaceId(Namespace.KIND_PACKAGE, namespace, 0, true);
        return abc.constants.getMultinameId(member, true);
    }
    static ABC fixture(String variant) {
        ABC abc = new ABC((ABCContainerTag)null);
        int traitName = qname(abc, "owned.fixture", "ApexAccept");
        int receiver = qname(abc, variant.equals("namespace") ? "wrong.namespace" : "olympus.extensions",
            variant.equals("runtime-package") ? "olympus" : variant.equals("missing-load") ? "OtherClass" : "CASTelemetryExtension");
        int method = qname(abc, "", variant.equals("missing-call") ? "OtherMethod" : "ReportHouseholdSimIDs");
        ArrayList<AVM2Instruction> instructions = new ArrayList<>();
        instructions.add(new AVM2Instruction(0, variant.equals("non-qname-load") ? 0x66 : 0x60, new int[]{receiver}));
        if (variant.equals("receiver-gap")) instructions.add(new AVM2Instruction(0, 0x02, new int[0]));
        instructions.add(new AVM2Instruction(0, 0x4f, new int[]{method, variant.equals("arguments") ? 1 : 0}));
        if (variant.equals("duplicate")) {
            instructions.add(new AVM2Instruction(0, 0x60, new int[]{receiver}));
            instructions.add(new AVM2Instruction(0, 0x4f, new int[]{method, 0}));
        }
        instructions.add(new AVM2Instruction(0, 0x47, new int[0]));
        MethodBody body = new MethodBody(abc, new Traits(), new byte[0], new ABCException[0]);
        body.method_info = 0;
        body.max_stack = 1;
        body.max_regs = 1;
        body.setCode(new AVM2Code(instructions));
        abc.bodies.add(body);
        abc.method_info.add(new MethodInfo(new int[0], 0, 0, 0, new ValueKind[0], new int[0]));
        // The instance is independent of the fixture's class inventory; its
        // sole trait indexes the synthetic method and survives constant IDs.
        InstanceInfo instance = new InstanceInfo(new Traits());
        instance.interfaces = new int[0];
        TraitMethodGetterSetter trait = new TraitMethodGetterSetter();
        trait.kindType = Trait.TRAIT_METHOD;
        trait.name_index = traitName;
        trait.method_info = 0;
        instance.instance_traits.traits.add(trait);
        abc.instance_info.add(instance);
        ClassInfo clazz = new ClassInfo(new Traits());
        clazz.cinit_index = 0;
        abc.class_info.add(clazz);
        return abc;
    }
    static void check(ABC abc, String variant, String expected) {
        try {
            CasBytecodePatch.verifyAcceptLinkage(abc, abc.instance_info.get(0));
            if (expected != null) throw new AssertionError("Invalid linkage accepted: " + variant);
        } catch (IllegalArgumentException error) {
            if (expected == null || !error.getMessage().contains(expected))
                throw new AssertionError("Unexpected rejection for " + variant + ": " + error.getMessage(), error);
        }
    }
    public static void main(String[] args) throws Exception {
        Map<String,String> cases = new LinkedHashMap<>();
        cases.put("valid", null);
        cases.put("runtime-package", "unresolved runtime package lookup");
        cases.put("namespace", "incorrect package namespace");
        cases.put("non-qname-load", "not loaded through its native QName");
        cases.put("receiver-gap", "not bound to its native class receiver");
        cases.put("arguments", "not bound to its native class receiver");
        cases.put("duplicate", "linkage inventory differs");
        cases.put("missing-call", "not bound to its native class receiver");
        cases.put("missing-load", "linkage inventory differs");
        for (var test : cases.entrySet()) {
            ABC abc = fixture(test.getKey());
            check(abc, test.getKey(), test.getValue());
            ByteArrayOutputStream output = new ByteArrayOutputStream();
            abc.saveToStream(output);
            ABC serialized = new ABC(new ABCInputStream(new MemoryInputStream(output.toByteArray())), null, null);
            check(serialized, test.getKey(), test.getValue());
        }
        System.out.println("{\"synthetic_fixtures\":9,\"serialized_rechecks\":9,\"all_passed\":true}");
    }
}
