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
        CasBytecodePatch.verifySocketLifetime(abc,instance);
        CasBytecodePatch.verifyFormSelection(abc,instance);
        CasBytecodePatch.verifyMemberSelection(abc,instance);
        CasBytecodePatch.verifyExactItemSelection(abc,instance);
        CasBytecodePatch.verifyTypedControls(abc,instance);
        CasBytecodePatch.verifyPhysiqueGesture(abc,instance);
    }
    public static void main(String[] args) throws Exception {
        String kind=args[0]; ABC abc=CasBytecodePatch.load(args[1]);
        var instance=abc.instance_info.get(abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain"));
        MethodBody execute=CasBytecodePatch.ownedBody(abc,instance,"ApexExecute");
        MethodBody helper=CasBytecodePatch.ownedBody(abc,instance,"ApexFormSelectionContext");
        MethodBody connect=CasBytecodePatch.ownedBody(abc,instance,"ApexSocketConnect");
        MethodBody tick=CasBytecodePatch.ownedBody(abc,instance,"ApexTick");
        MethodBody readback=CasBytecodePatch.ownedBody(abc,instance,"ApexReadback");
        MethodBody region=CasBytecodePatch.ownedBody(abc,instance,"ApexBodyTypes");
        MethodBody layers=CasBytecodePatch.ownedBody(abc,instance,"ApexNativeLayers");
        MethodBody memberHelper=CasBytecodePatch.ownedBody(abc,instance,"ApexMemberSelectionContext");
        MethodBody failure=CasBytecodePatch.ownedBody(abc,instance,"ApexSocketFailure");
        MethodBody send=CasBytecodePatch.ownedBody(abc,instance,"ApexSocketSend");
        MethodBody quote=CasBytecodePatch.ownedBody(abc,instance,"ApexQuote");
        MethodBody socketData=CasBytecodePatch.ownedBody(abc,instance,"ApexSocketData");
        checks(abc);
        switch(kind) {
            case "native-pipe-not-required": {
                var rows=CasBytecodePatch.ownedBody(abc,instance,"ApexInitialize").getCode().code;
                for(int i=1;i<rows.size();i++)if(CasBytecodePatch.property(abc,rows.get(i),0x61,"apexNativeTransportRequired")) {
                    rows.set(i-1,new AVM2Instruction(0,0x27,new int[0]));break;
                }
                break;
            }
            case "native-pipe-wrong-service":
                literal(abc,CasBytecodePatch.ownedBody(abc,instance,"ApexNativeExchange"),"GetSimOccult").operands[0]=abc.constants.getStringId("SetSimOccult",true);break;
            case "native-pipe-frame-parser-native-write": {
                var consume=CasBytecodePatch.ownedBody(abc,instance,"ApexConsumeFrame");
                for(var op:consume.getCode().code)if(CasBytecodePatch.property(abc,op,0x46,"split")) {
                    op.operands[0]=member(abc,"CallGameService");break;
                }
                break;
            }
            case "physique-readback-before-completion":
                literal(abc,readback,"GetSimOccult").operands[0]=abc.constants.getStringId("CASGetSimInfo",true);break;
            case "physique-timer-preview-guard-missing":
                property(abc,tick,"physique_commit_pending").operands[0]=member(abc,"apexFormsBootstrap");break;
            case "socket-failure-not-queued":
                for(var op:failure.getCode().code) if(CasBytecodePatch.property(abc,op,0x61,"apexSocketResetPending")) {
                    op.operands[0]=member(abc,"apexHelloPending");break;
                }
                break;
            case "socket-failure-native-close":
                int callbackReturn=failure.getCode().code.size()-1;
                if(!CasBytecodePatch.opcode(failure.getCode().code.get(callbackReturn),0x47))
                    throw new AssertionError("Missing callback return for native-close regression.");
                failure.insertAll(callbackReturn,List.of(new AVM2Instruction(0,0xd0,new int[0]),
                    new AVM2Instruction(0,0x4f,new int[]{member(abc,"ApexResetSocket"),0})));
                break;
            case "socket-data-stale-event": property(abc,socketData,"currentTarget").operands[0]=member(abc,"simId");break;
            case "socket-send-unretained-buffer":
                for(int i=1;i<send.getCode().code.size();i++) {
                    var rows=send.getCode().code;
                    if(CasBytecodePatch.property(abc,rows.get(i),0x4f,"writeUTFBytes") || CasBytecodePatch.property(abc,rows.get(i),0x46,"writeUTFBytes")) {
                        rows.get(i-1).operands[0]=member(abc,"apexWire");break;
                    }
                }
                break;
            case "socket-send-native-service":
                for(var op:send.getCode().code) if(CasBytecodePatch.property(abc,op,0x4f,"writeUTFBytes") || CasBytecodePatch.property(abc,op,0x46,"writeUTFBytes")) {
                    op.operands[0]=member(abc,"CallGameService");break;
                }
                break;
            case "socket-json-unescaped-unicode":
                for(var op:quote.getCode().code) if(CasBytecodePatch.opcode(op,0x24) && op.operands[0]==126) {op.operands[0]=127;break;}
                break;
            case "member-service-name":
                literal(abc,execute,"CASSelectSim").operands[0]=abc.constants.getStringId("CasRemoveSim",true);break;
            case "member-destination-index":
                property(abc,execute,"target_index").operands[0]=member(abc,"source_index");break;
            case "member-preflight-service":
                literal(abc,memberHelper,"ApexReadOwnerPairFeed").operands[0]=abc.constants.getStringId("CasRemoveSim",true);break;
            case "member-readback-missing":
                for(var instruction:readback.getCode().code) if(CasBytecodePatch.property(abc,instruction,0x46,"ApexMemberSelectionContext")) {
                    instruction.operands[0]=member(abc,"ApexOwnerSimRow");break;
                }
                break;
            case "actual-constructor-timer-path": break;
            case "native-snapshot-detached": break;
            case "body-region-native-write":
                for(var instruction:region.getCode().code) if(CasBytecodePatch.property(abc,instruction,0x46,"SetSelection")) {
                    instruction.operands[0]=member(abc,"CallGameService");break;
                }
                break;
            case "body-region-unbound-definition":
                for(var instruction:region.getCode().code) if(CasBytecodePatch.property(abc,instruction,0x60,"TattooBodyData")) {
                    instruction.operands[0]=member(abc,"MenuState");break;
                }
                break;
            case "layer-null-unsafe-service":
                literal(abc,layers,"CasHasPartOrTattooPaintLayer").operands[0]=abc.constants.getStringId("CasSetSwatchColorSelected",true);
                break;
            case "layer-helper-socket-phase":
                for(var instruction:connect.getCode().code) if(CasBytecodePatch.property(abc,instruction,0x46,"split")) {
                    instruction.operands[0]=member(abc,"ApexNativeLayers");break;
                }
                break;
            case "native-snapshot-borrowed": {
                var snapshot=CasBytecodePatch.ownedBody(abc,instance,"ApexSnapshot").getCode().code;
                boolean changed=false;
                for(var instruction:snapshot) if(CasBytecodePatch.property(abc,instruction,0x46,"ApexClone")) {
                    instruction.operands[0]=member(abc,"ApexEncode");changed=true;break;
                }
                if(!changed) throw new AssertionError("Missing detached native snapshot fixture.");
                break;
            }
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
            case "selection-native-handler": {
                  literal(abc,execute,"ApexNavigateOwnerLayer").operands[0]=abc.constants.getStringId("CasSelectOccultForm",true);break;
            }
            case "selection-layer-key": {
                  literal(abc,execute,"expected_layer").operands[0]=abc.constants.getStringId("hue_range_modifier",true);break;
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
        for(MethodBody body:List.of(execute,helper,connect,tick,readback,region,layers,memberHelper,failure,send,quote,socketData,
            CasBytecodePatch.ownedBody(abc,instance,"ApexInitialize"),
            CasBytecodePatch.ownedBody(abc,instance,"ApexNativeExchange"),
            CasBytecodePatch.ownedBody(abc,instance,"ApexConsumeFrame"),
            CasBytecodePatch.ownedBody(abc,instance,"ApexSnapshot"))) body.setModified();
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();abc.saveToStream(bytes);
        ABC saved=new ABC(new ABCInputStream(new MemoryInputStream(bytes.toByteArray())),abc.getSwf(),null);
        boolean positive=kind.equals("actual-constructor-timer-path") || kind.equals("native-snapshot-detached");
        try { checks(saved); if(!positive) throw new AssertionError("Unsafe serialized fixture was accepted: "+kind); }
        catch(IllegalArgumentException expected) { if(positive) throw expected; }
        System.out.println("PASS "+kind);
    }
}
