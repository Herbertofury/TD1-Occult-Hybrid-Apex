import java.util.List;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;

public class CasCompanionBytecodeFixtures {
    static int member(com.jpexs.decompiler.flash.abc.ABC abc,String name) {
        for(int i=1;i<abc.constants.getMultinameCount();i++) {
            var q=abc.constants.getMultiname(i);
            if(q.name_index>0&&abc.constants.getString(q.name_index).equals(name))return i;
        }
        throw new IllegalArgumentException("Missing property "+name);
    }
    public static void main(String[] args)throws Exception {
        var abc=CasBytecodePatch.load(args[0]);String mode=args[1];
        var instance=abc.instance_info.get(abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain"));
        if(mode.endsWith("native-work")) {
            var body=CasBytecodePatch.ownedBody(abc,instance,mode.startsWith("badges")?"ApexCompanionBadges":"ApexCompanionCard");
            body.insertAll(2,List.of(new AVM2Instruction(0,0xd0,new int[0]),new AVM2Instruction(0,0x4f,new int[]{member(abc,"ApexNativeExchange"),0})));
            body.max_stack=Math.max(body.max_stack,1);body.setModified();
        }else if(!mode.equals("valid")) {
            String method,from;
            switch(mode){
                case "rightclick-propagates":method="ApexCompanionCard";from="stopImmediatePropagation";break;
                case "intent-no-context":method="ApexCompanionIntent";from="ApexSearchContext";break;
                case "dispose-no-tooltip-cleanup":method="ApexCompanionDispose";from="Shutdown";break;
                default:throw new IllegalArgumentException("Unknown case");
            }
            var body=CasBytecodePatch.ownedBody(abc,instance,method);boolean changed=false;
            for(var op:body.getCode().code)if(CasBytecodePatch.property(abc,op,0x46,from)||CasBytecodePatch.property(abc,op,0x4f,from)){op.operands[0]=member(abc,"ApexSearchStatus");changed=true;}
            CasBytecodePatch.require(changed,"Fixture did not mutate "+from);body.setModified();
        }
        var bytes=new java.io.ByteArrayOutputStream();abc.saveToStream(bytes);
        abc=new com.jpexs.decompiler.flash.abc.ABC(new com.jpexs.decompiler.flash.abc.ABCInputStream(new com.jpexs.helpers.MemoryInputStream(bytes.toByteArray())),abc.getSwf(),null);
        var checked=abc.instance_info.get(abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain"));boolean refused=false;
        try{CasBytecodePatch.verifyCatalogCompanion(abc,checked);}catch(IllegalArgumentException expected){refused=true;}
        CasBytecodePatch.require(refused!=mode.equals("valid"),"Companion mutation accepted or valid code refused");
        System.out.println("PASS "+mode);
    }
}
