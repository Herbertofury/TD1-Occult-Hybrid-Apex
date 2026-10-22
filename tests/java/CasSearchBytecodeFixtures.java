import java.util.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;
public class CasSearchBytecodeFixtures {
    static int member(com.jpexs.decompiler.flash.abc.ABC abc,String name) {
        for(int i=1;i<abc.constants.getMultinameCount();i++) {
            var q=abc.constants.getMultiname(i);
            if(q.name_index>0 && abc.constants.getString(q.name_index).equals(name))return i;
        }
        throw new IllegalArgumentException("Missing fixture property "+name);
    }
    public static void main(String[] args)throws Exception {
        var abc=CasBytecodePatch.load(args[0]);String mode=args[1];
        var instance=abc.instance_info.get(abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain"));
        if(mode.equals("input-native-work")) {
            var body=CasBytecodePatch.ownedBody(abc,instance,"ApexSearchChanged");
            body.insertAll(2,List.of(new AVM2Instruction(0,0xd0,new int[0]),
                new AVM2Instruction(0,0x4f,new int[]{member(abc,"ApexNativeExchange"),0})));
            body.max_stack=Math.max(body.max_stack,1);body.setModified();
        } else if(mode.equals("search-runtime-json")) {
            var body=CasBytecodePatch.ownedBody(abc,instance,"ApexSearchFrame");
            body.insertAll(2,List.of(new AVM2Instruction(0,0x60,new int[]{abc.constants.getMultinameId(
                com.jpexs.decompiler.flash.abc.types.Multiname.createQName(false,abc.constants.getStringId("JSON",true),
                abc.constants.getNamespaceId(0x16,"",0,true)),true)}),
                new AVM2Instruction(0,0x29,new int[0])));
            body.max_stack=Math.max(body.max_stack,1);body.setModified();
        } else if(mode.equals("search-sim-instead-of-channel")) {
            var body=CasBytecodePatch.ownedBody(abc,instance,"ApexSearchFrame");boolean changed=false;
            for(var op:body.getCode().code)if(CasBytecodePatch.property(abc,op,0x66,"apexNativeChannel") ||
                CasBytecodePatch.property(abc,op,0x60,"apexNativeChannel")) {
                op.operands[0]=member(abc,"apexBoundSim");changed=true;
            }
            CasBytecodePatch.require(changed,"Fixture did not replace the native channel");body.setModified();
        } else if(mode.equals("publish-rebuilds-unchanged")) {
            var body=CasBytecodePatch.ownedBody(abc,instance,"ApexSearchPublish");var rows=body.getCode().code;
            boolean compared=false,changed=false;
            for(int i=0;i<rows.size();i++) {
                var op=rows.get(i);
                if(CasBytecodePatch.property(abc,op,0x46,"RequestItemAt"))compared=true;
                if(compared && op.definition.instructionCode==0x47) {
                    rows.set(i,new AVM2Instruction(0,0x02,new int[0]));changed=true;break;
                }
            }
            CasBytecodePatch.require(changed,"Fixture did not remove the unchanged-results return");body.setModified();
        } else if(!mode.equals("valid")) {
            String old,replacement;int opcode;
            switch(mode) {
                case "publish-no-context":old="ApexSearchContext";replacement="ApexSearchStatus";opcode=0x46;break;
                case "publish-no-membership":old="matches";replacement="text";opcode=0x66;break;
                case "publish-stale-key":old="apexKeyIndex";replacement="apexKeyIntent";opcode=0x68;break;
                case "adopt-wrong-owner":old="owner";replacement="sim";opcode=0x66;break;
                default:throw new IllegalArgumentException("Unknown fixture");
            }
            var body=CasBytecodePatch.ownedBody(abc,instance,mode.startsWith("adopt-") ? "ApexSearchAdopt" : "ApexSearchPublish");boolean changed=false;
            for(var op:body.getCode().code)if(CasBytecodePatch.property(abc,op,opcode,old) ||
                opcode==0x68 && CasBytecodePatch.property(abc,op,0x61,old)) {
                op.operands[0]=member(abc,replacement);changed=true;
            }
            CasBytecodePatch.require(changed,"Fixture did not mutate "+old);body.setModified();
        }
        var saved=new java.io.ByteArrayOutputStream();abc.saveToStream(saved);
        abc=new com.jpexs.decompiler.flash.abc.ABC(new com.jpexs.decompiler.flash.abc.ABCInputStream(
            new com.jpexs.helpers.MemoryInputStream(saved.toByteArray())),abc.getSwf(),null);
        var checked=abc.instance_info.get(abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain"));
        boolean refused=false;
        try {CasBytecodePatch.verifyNativeCatalogSearch(abc,checked);}catch(IllegalArgumentException expected){refused=true;}
        CasBytecodePatch.require(refused!=mode.equals("valid"),"Search regression accepted, or valid build refused");
        System.out.println("PASS "+mode);
    }
}
