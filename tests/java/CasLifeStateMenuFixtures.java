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
            case "fast-queue-not-deferred":method="ApexFormsScheduleFrame";from="addEventListener";break;
            case "fast-frame-network-poll":method="ApexFormsNextFrame";from="ApexFormsOwnedTick";to="ApexTick";break;
            case "fast-frame-missing-lease":method="ApexFormsNextFrame";from="apexPendingFields";to="apexFormsDesiredId";opcode=0x60;break;
            case "fast-clock-namespace":
                abc.constants.getMultiname(member(abc,"getTimer")).namespace_index=
                    abc.constants.getNamespaceId(Namespace.KIND_PACKAGE,"wrong.package",0,true);break;
            case "fast-state-not-native":method="ApexFormsReadNativeState";from="ApexNativeExchange";opcode=0x46;break;
            case "pair-click-not-deferred": {
                // The floating callback is retired. Prove that adding any
                // inline pair action is rejected rather than looking for a
                // listener which correctly no longer exists.
                var retired=CasBytecodePatch.ownedBody(abc,abc.instance_info.get(
                    abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain")),"ApexPairClick");
                if(!CasBytecodePatch.propertyCalls(abc,retired).isEmpty())
                    throw new AssertionError("Retired pair callback is not empty.");
                var code=retired.getCode().code;int at=-1;
                for(int i=0;i<code.size();i++)if(code.get(i).definition.instructionCode==0x47)at=i;
                if(at<0)throw new AssertionError("Retired callback return missing.");
                retired.insertAll(at,java.util.List.of(
                    new com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction(0,0xd0,new int[0]),
                    new com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction(0,0x20,new int[0]),
                    new com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction(0,0x4f,new int[]{member(abc,"ApexPairExecute"),1})));
                retired.max_stack=Math.max(retired.max_stack,2);retired.setModified();break;
            }
            case "pair-panel-not-deferred":method="ApexPairPanel";from="ApexFormsScheduleFrame";to="ApexPairExecute";break;
            case "pair-read-mutates":method="ApexPairRead";from="ApexNativeExchange";to="ApexPairExecute";opcode=0x46;break;
            case "pair-native-action-missing":method="ApexPairExecute";from="ApexNativeExchange";opcode=0x46;break;
            case "pair-cli-action-missing":method="ApexControlExecute";from="ApexPairExecute";to="ApexPairRead";opcode=0x46;break;
            case "molecule-click-drops-intent":method="ApexMoleculeChooseOccult";from="apexMoleculeIntent";to="apexFormsIntent";opcode=0x61;break;
            case "molecule-click-inline":method="ApexMoleculeChooseOccult";from="ApexFormsScheduleFrame";to="ApexFormsOwnedTick";break;
            case "molecule-drain-other-session":method="ApexMoleculeDrain";from="apexOwnerSession";to="apexFormsGestureSequence";opcode=0x60;break;
            case "molecule-drain-active-command":method="ApexMoleculeDrain";from="apexPendingFields";to="apexFormsResult";opcode=0x60;break;
            case "molecule-drain-inline":method="ApexMoleculeDrain";from="ApexClone";to="ApexFormsOwnedTick";opcode=0x46;break;
            case "molecule-not-consumed":method="ApexFormsOwnedTick";from="ApexMoleculeDrain";to="ApexFormsReadNativeState";break;
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
