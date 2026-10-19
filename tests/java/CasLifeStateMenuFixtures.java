import java.io.*;
import java.util.logging.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.Namespace;
import com.jpexs.helpers.MemoryInputStream;

public class CasLifeStateMenuFixtures {
    static int member(ABC abc,String name) {
        for(int i=1;i<abc.constants.getMultinameCount();i++)
            if(name.equals(abc.constants.getString(abc.constants.getMultiname(i).name_index))) return i;
        throw new AssertionError("Missing fixture member: "+name);
    }
    static void check(ABC abc) {
        CasBytecodePatch.verifyFormStrip(abc,abc.instance_info.get(
            abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain")));
    }
    public static void main(String[] args) throws Exception {
        Logger.getLogger("com.jpexs.decompiler.flash.SWFInputStream").setLevel(Level.OFF);
        String key=args[0];var abc=CasBytecodePatch.load(args[1]);check(abc);
        String method=null,from=null,to="ApexClone";int opcode=0x4f;
        switch(key) {
            case "exact":break;
            case "grouping":method="ApexFormsOwnedTick";from="ApexFormsGroupCatalog";break;
            case "rendering-kind":method="ApexFormsGroupCatalog";from="family";to="kind";opcode=0x66;break;
            case "tooltip-create":method="ApexFormsTooltip";from="Initialize";break;
            case "tooltip-rebuild":method="ApexFormsOwnedTick";from="ApexFormsClearTooltips";break;
            case "tooltip-unload":method="ApexFormsDispose";from="ApexFormsClearTooltips";break;
            case "tooltip-shutdown":method="ApexFormsClearTooltips";from="Shutdown";break;
            case "fast-queue-not-deferred":method="ApexFormsQueueOwner";from="addEventListener";break;
            case "fast-frame-network-poll":method="ApexFormsNextFrame";from="ApexFormsOwnedTick";to="ApexTick";break;
            case "fast-frame-missing-lease":method="ApexFormsNextFrame";from="apexPendingFields";to="apexFormsDesiredId";opcode=0x60;break;
            case "fast-clock-namespace":
                abc.constants.getMultiname(member(abc,"getTimer")).namespace_index=
                    abc.constants.getNamespaceId(Namespace.KIND_PACKAGE,"wrong.package",0,true);break;
            case "fast-state-not-native":method="ApexFormsReadNativeState";from="ApexNativeExchange";opcode=0x46;break;
            case "pair-click-not-deferred":method="ApexPairClick";from="addEventListener";break;
            case "pair-read-mutates":method="ApexPairRead";from="ApexNativeExchange";to="ApexPairExecute";opcode=0x46;break;
            case "pair-native-action-missing":method="ApexPairExecute";from="ApexNativeExchange";opcode=0x46;break;
            case "pair-cli-action-missing":method="ApexControlExecute";from="ApexPairExecute";to="ApexPairRead";opcode=0x46;break;
            default:throw new AssertionError("Unknown case");
        }
        if(method!=null) {
            var body=CasBytecodePatch.ownedBody(abc,abc.instance_info.get(
                abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain")),method);
            boolean changed=false;
            for(var op:body.getCode().code) if(CasBytecodePatch.property(abc,op,opcode,from)) {
                op.operands[0]=member(abc,to);changed=true;
            }
            if(!changed) throw new AssertionError("No matching fixture instruction: "+key);
            body.setModified();
        }
        var bytes=new ByteArrayOutputStream();abc.saveToStream(bytes);
        var serialized=new ABC(new ABCInputStream(new MemoryInputStream(bytes.toByteArray())),abc.getSwf(),null);
        boolean accepted=true;try {check(serialized);}catch(IllegalArgumentException|IllegalStateException error){accepted=false;}
        if(accepted!=key.equals("exact")) throw new AssertionError("Unexpected validation: "+key);
        System.out.println("PASS "+key);
    }
}
