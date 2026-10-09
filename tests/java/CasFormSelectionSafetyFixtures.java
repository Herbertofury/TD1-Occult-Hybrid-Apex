// Validate actual compiled native constructor/listener/Timer and selector paths.
import java.io.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.ABC;
import com.jpexs.decompiler.flash.abc.ABCInputStream;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;
import com.jpexs.helpers.MemoryInputStream;

public class CasFormSelectionSafetyFixtures {
    static int member(ABC abc,String name) {
        for(int i=1;i<abc.constants.getMultinameCount();i++) {
            var item=abc.constants.getMultiname(i);
            if(name.equals(abc.constants.getString(item.name_index))) return i;
        }
        throw new AssertionError("Missing fixture member "+name);
    }
    static AVM2Instruction literal(ABC abc,MethodBody body,String value) {
        for(var instruction:body.getCode().code) if(CasBytecodePatch.opcode(instruction,0x2c) &&
                value.equals(abc.constants.getString(instruction.operands[0]))) return instruction;
        throw new AssertionError("Missing fixture literal "+value);
    }
    static AVM2Instruction property(ABC abc,MethodBody body,String value) {
        for(var instruction:body.getCode().code) if(CasBytecodePatch.property(abc,instruction,0x66,value)) return instruction;
        throw new AssertionError("Missing fixture property "+value);
    }
    static void checks(ABC abc) {
        var instance=abc.instance_info.get(abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain"));
        CasBytecodePatch.verifyTimerPipeline(abc,instance);
        CasBytecodePatch.verifyQueuedHandshake(abc,instance);
        CasBytecodePatch.verifyFormSelection(abc,instance);
        CasBytecodePatch.verifyExactItemSelection(abc,instance);
    }
    public static void main(String[] args) throws Exception {
        String kind=args[0]; ABC abc=CasBytecodePatch.load(args[1]);
        var instance=abc.instance_info.get(abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain"));
        MethodBody execute=CasBytecodePatch.ownedBody(abc,instance,"ApexExecute");
        MethodBody helper=CasBytecodePatch.ownedBody(abc,instance,"ApexFormSelectionContext");
        MethodBody connect=CasBytecodePatch.ownedBody(abc,instance,"ApexSocketConnect");
        MethodBody tick=CasBytecodePatch.ownedBody(abc,instance,"ApexTick");
        MethodBody readback=CasBytecodePatch.ownedBody(abc,instance,"ApexReadback");
        checks(abc);
        switch(kind) {
            case "actual-constructor-timer-path": break;
            case "connect-native-getter":
                for(var instruction:connect.getCode().code) if(CasBytecodePatch.property(abc,instruction,0x46,"split")) {
                    instruction.operands[0]=member(abc,"CallGameService"); break;
                }
                break;
            case "connect-native-helper":
                for(var instruction:connect.getCode().code) if(CasBytecodePatch.property(abc,instruction,0x46,"split")) {
                    instruction.operands[0]=member(abc,"ApexFormSelectionContext"); break;
                }
                break;
            case "connect-transport-send":
                for(var instruction:connect.getCode().code) if(CasBytecodePatch.property(abc,instruction,0x46,"split")) {
                    instruction.operands[0]=member(abc,"ApexSocketSend"); break;
                }
                break;
            case "connect-event-owner": property(abc,connect,"currentTarget").operands[0]=member(abc,"simId"); break;
            case "constructor-connect-event": property(abc,tick,"CONNECT").operands[0]=member(abc,"CLOSE"); break;
            case "constructor-connect-callback":
                for(var instruction:tick.getCode().code) if(CasBytecodePatch.property(abc,instruction,0x60,"ApexSocketConnect")) {
                    instruction.operands[0]=member(abc,"ApexSocketData"); break;
                }
                break;
            case "handshake-native-getter": literal(abc,tick,"CASGetSimInfo").operands[0]=abc.constants.getStringId("CasIsNewFamily",true); break;
            case "handshake-consume-once": {
                var code=tick.getCode().code;
                int at=code.indexOf(literal(abc,tick,"HELLO|"));
                for(int i=at-1;i>=Math.max(1,at-16);i--) if(CasBytecodePatch.property(abc,code.get(i),0x61,"apexHelloPending")) {
                    code.set(i-1,new AVM2Instruction(0,0x26,new int[0])); break;
                }
                break;
            }
            case "handshake-exact-sim-payload": {
                var code=tick.getCode().code; int at=code.indexOf(literal(abc,tick,"HELLO|"));
                code.get(at+2).operands[0]=1; break;
            }
            case "selector-service-contract": literal(abc,helper,"ApexReadOwnerPairFeed").operands[0]=abc.constants.getStringId("CasSelectSim",true); break;
            case "selector-helper-native-write": literal(abc,helper,"CASGetSimInfo").operands[0]=abc.constants.getStringId("CasSelectSim",true); break;
            case "selection-current-index": property(abc,execute,"selected_index").operands[0]=member(abc,"target_layer"); break;
            case "selection-write-order": {
                var first=literal(abc,execute,"CasSelectSim");var second=literal(abc,execute,"CasSelectOccultForm");
                int value=first.operands[0];first.operands[0]=second.operands[0];second.operands[0]=value;break;
            }
            case "selection-typed-boolean": {
                var code=execute.getCode().code;int at=code.indexOf(literal(abc,execute,"CasSelectOccultForm"));
                code.get(at+1).operands[0]=abc.constants.getStringId("hue_range_modifier",true);break;
            }
            case "selection-next-tick-readback":
                for(var instruction:readback.getCode().code) if(CasBytecodePatch.property(abc,instruction,0x46,"ApexFormSelectionContext")) {
                    instruction.operands[0]=member(abc,"ApexOwnerSimRow");break;
                }
                break;
            case "earrings-wrong-bodytype": property(abc,execute,"EARRINGS").operands[0]=member(abc,"SHOES");break;
            case "ambiguous-swatch-count": {
                var code=execute.getCode().code;int at=code.indexOf(literal(abc,execute,
                    "Choose one exact returned catalog swatch dataID; base/ambiguous variant requests are not changed"));
                code.get(at-3).operands[0]=0;break;
            }
            default:throw new AssertionError("Unknown fixture "+kind);
        }
        for(MethodBody body:List.of(execute,helper,connect,tick,readback)) body.setModified();
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();abc.saveToStream(bytes);
        ABC saved=new ABC(new ABCInputStream(new MemoryInputStream(bytes.toByteArray())),abc.getSwf(),null);
        boolean positive=kind.equals("actual-constructor-timer-path");
        try { checks(saved); if(!positive) throw new AssertionError("Unsafe serialized fixture was accepted: "+kind); }
        catch(IllegalArgumentException expected) { if(positive) throw expected; }
        System.out.println("PASS "+kind);
    }
}
