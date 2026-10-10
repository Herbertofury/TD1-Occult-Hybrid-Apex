// Synthetic owned catalog annotations; no installed game assets or calls.
import java.io.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.helpers.MemoryInputStream;

public class CasCatalogMetadataTests {
    static AVM2Instruction op(int opcode,int... operands) { return CasAcceptLayerTests.op(opcode,operands); }
    static int member(ABC abc,String name) { return CasAcceptLayerTests.member(abc,name); }
    static ABC fixture(String variant) {
        ABC abc=new ABC((com.jpexs.decompiler.flash.tags.ABCContainerTag)null);
        InstanceInfo instance=new InstanceInfo(new com.jpexs.decompiler.flash.abc.types.traits.Traits());
        instance.interfaces=new int[0];abc.instance_info.add(instance);
        ClassInfo clazz=new ClassInfo(new com.jpexs.decompiler.flash.abc.types.traits.Traits());clazz.cinit_index=0;abc.class_info.add(clazz);
        Multiname loc=new Multiname();loc.kind=Multiname.QNAME;loc.name_index=abc.constants.getStringId("LocKey",true);
        loc.namespace_index=abc.constants.getNamespaceId(Namespace.KIND_PACKAGE,variant.equals("wrong-namespace")?"wrong.namespace":"olympus.localization",0,true);
        int key=abc.constants.getMultinameId(loc,true);
        List<AVM2Instruction> code=new ArrayList<>(List.of(
            op(0x2c,abc.constants.getStringId(variant.equals("wrong-getter")?"OtherGetter":"GetCatalogItem",true)),op(0x65,1),op(0x6c,11),
            op(0x46,member(abc,"CallGameService"),variant.equals("wrong-payload")?3:2),
            op(0x5d,variant.equals("runtime-package")?member(abc,"olympus"):key),op(0x65,1),op(0x6c,13),
            op(0x66,member(abc,variant.equals("wrong-title")?"data_id":"title")),op(0x4a,key,1),
            op(0x46,member(abc,variant.equals("missing-localization")?"OtherCall":"toString"),0),op(0x47)));
        CasAcceptLayerTests.body(abc,instance,"ApexSnapshot",code);
        return abc;
    }
    static void check(ABC abc,String variant) {
        boolean valid=variant.equals("valid");
        try {
            CasBytecodePatch.verifyCatalogMetadataLinkage(abc,abc.instance_info.get(0));
            if(!valid)throw new AssertionError("Invalid native catalog linkage accepted: "+variant);
        } catch(IllegalArgumentException error) {
            if(valid || !error.getMessage().startsWith("CAS catalog"))throw new AssertionError(error);
        }
    }
    public static void main(String[] args)throws Exception {
        for(String variant:List.of("valid","wrong-namespace","wrong-getter","wrong-payload","runtime-package","wrong-title","missing-localization")) {
            ABC abc=fixture(variant);check(abc,variant);
            ByteArrayOutputStream bytes=new ByteArrayOutputStream();abc.saveToStream(bytes);
            check(new ABC(new ABCInputStream(new MemoryInputStream(bytes.toByteArray())),null,null),variant);
        }
        System.out.println("{\"synthetic_fixtures\":7,\"serialized_rechecks\":7,\"all_passed\":true}");
    }
}
