import java.io.*;
import java.util.logging.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;
import com.jpexs.helpers.MemoryInputStream;

public class CasOwnerMetadataFixtures {
    static int member(ABC abc,String name) {
        for(int i=1;i<abc.constants.getMultinameCount();i++) {
            var m=abc.constants.getMultiname(i);
            if(name.equals(abc.constants.getString(m.name_index)))return i;
        }
        throw new AssertionError("Missing fixture member: "+name);
    }
    static void check(ABC abc) {
        var instance=abc.instance_info.get(abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain"));
        CasBytecodePatch.verifyOwnerMetadataReadback(abc,instance);
        CasBytecodePatch.verifyCatalogVariantReadback(abc,instance);
        CasBytecodePatch.verifySettledOwnerBootstrap(abc,instance);
        CasBytecodePatch.verifyImmediatePairAcknowledgement(abc,instance);
        CasBytecodePatch.verifyPresentationBootstrap(abc,instance);
        CasBytecodePatch.verifyOwnerObservation(abc,instance);
    }
    public static void main(String[] args) throws Exception {
        Logger.getLogger("com.jpexs.decompiler.flash.SWFInputStream").setLevel(Level.OFF);
        String key=args[0];var abc=CasBytecodePatch.load(args[1]);check(abc);
        var body=CasBytecodePatch.ownedBody(abc,abc.instance_info.get(
            abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain")),"ApexReadback");
        var rows=body.getCode().code;int p=CasBytecodePatch.uniqueLiteral(abc,body,"POLL|");
        switch(key) {
            case "exact":break;
            case "prime-claim":case "prime-household":case "prime-native-read": {
                var instance=abc.instance_info.get(abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain"));
                var target=CasBytecodePatch.ownedBody(abc,instance,"ApexPresentationPrime");int changes=0;
                for(var row:target.getCode().code) {
                    String field=key.equals("prime-claim")?"apexPendingFields":"householdId";
                    if(!key.equals("prime-native-read")&&(CasBytecodePatch.property(abc,row,0x60,field)||CasBytecodePatch.property(abc,row,0x66,field))) {
                        row.operands[0]=member(abc,key.equals("prime-claim")?"apexFormsPage":"simId");changes++;
                    }
                    if(key.equals("prime-native-read")&&(CasBytecodePatch.property(abc,row,0x46,"ApexFormsObservedSim")||CasBytecodePatch.property(abc,row,0x4f,"ApexFormsObservedSim"))) {
                        row.operands[0]=member(abc,"CallGameService");changes++;
                    }
                }
                if(changes<1)throw new AssertionError("Missing exact local prime mutation");target.setModified();break;
            }
            case "local-menu-operation":case "local-menu-duplicate":case "local-menu-count": {
                var instance=abc.instance_info.get(abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain"));
                var target=CasBytecodePatch.ownedBody(abc,instance,key.equals("local-menu-duplicate")?"ApexFormsConsumeCatalog":"ApexFormsTryLocalCatalog");
                int changes=0;
                for(var op:target.getCode().code) {
                    if(key.equals("local-menu-operation")&&CasBytecodePatch.stringLiteral(abc,op,"LOCALOWNERS|")) {op.operands[0]=abc.constants.getStringId("WRITE|",true);changes++;}
                    if(key.equals("local-menu-duplicate")&&CasBytecodePatch.stringLiteral(abc,op,"Late peer form catalogue differs from the prepared native page")) {op.operands[0]=abc.constants.getStringId("Unchecked duplicate catalogue",true);changes++;}
                    if(key.equals("local-menu-count")&&(CasBytecodePatch.property(abc,op,0x60,"apexFormsOwnerTotal")||CasBytecodePatch.property(abc,op,0x66,"apexFormsOwnerTotal"))) {op.operands[0]=member(abc,"apexFormsPage");changes++;}
                }
                if(changes<1)throw new AssertionError("Missing exact prepared menu mutation");target.setModified();break;
            }
            case "frame-ack-drain":case "frame-open-busy": {
                var instance=abc.instance_info.get(abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain"));
                var target=CasBytecodePatch.ownedBody(abc,instance,key.equals("frame-ack-drain")?"ApexTick":"ApexNativeOpen");
                int changes=0;
                for(var row:target.getCode().code) {
                    if(key.equals("frame-ack-drain")&&CasBytecodePatch.property(abc,row,0x4f,"ApexNativeReceive")) {row.operands[0]=member(abc,"ApexClone");changes++;}
                    if(key.equals("frame-open-busy")&&CasBytecodePatch.stringLiteral(abc,row,"BUSY")) {row.operands[0]=abc.constants.getStringId("STALE",true);changes++;}
                }
                if(changes!=1)throw new AssertionError("Missing exact transport bootstrap mutation");target.setModified();break;
            }
            case "pair-strip-call":case "pair-typed-call":case "pair-typed-ready":case "pair-native-rebind": {
                var instance=abc.instance_info.get(abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain"));
                String method=key.equals("pair-strip-call")?"ApexFormsOwnedTick":
                    key.equals("pair-native-rebind")?"ApexFormsRefreshBoundPair":"ApexReadback";
                String call=key.equals("pair-typed-ready")?"ApexPresentationReady":
                    key.equals("pair-native-rebind")?"ApexFormsBindUiKind":"ApexFormsRefreshBoundPair";
                var target=CasBytecodePatch.ownedBody(abc,instance,method);int changes=0;
                for(var row:target.getCode().code)
                    if(CasBytecodePatch.property(abc,row,0x46,call)||CasBytecodePatch.property(abc,row,0x4f,call)) {
                        row.operands[0]=member(abc,key.equals("pair-native-rebind")?"ApexFormsOwnedTick":"ApexFormsObservedSim");changes++;
                    }
                if(changes<1)throw new AssertionError("No shared pair mutation: "+key);
                target.setModified();break;
            }
            case "pair-refresh-read":case "pair-refresh-generation":case "pair-refresh-identity":
            case "pair-refresh-protocol":case "pair-refresh-enabled":case "pair-refresh-signature": {
                var instance=abc.instance_info.get(abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain"));
                var target=CasBytecodePatch.ownedBody(abc,instance,"ApexFormsRefreshBoundPair");
                boolean afterRefresh=false;int changes=0;
                String replaced=key.equals("pair-refresh-generation")?"apexFormsNativeGeneration":
                    key.equals("pair-refresh-identity")?"sim_id":key.equals("pair-refresh-protocol")?"protocol":"enabled";
                for(var row:target.getCode().code) {
                    if(CasBytecodePatch.property(abc,row,0x46,"CallUIService")||CasBytecodePatch.property(abc,row,0x4f,"CallUIService"))afterRefresh=true;
                    if(!afterRefresh)continue;
                    boolean read=key.equals("pair-refresh-read")&&(CasBytecodePatch.property(abc,row,0x46,"ApexFormsReadNativeState")||CasBytecodePatch.property(abc,row,0x4f,"ApexFormsReadNativeState"));
                    boolean signature=key.equals("pair-refresh-signature")&&CasBytecodePatch.property(abc,row,0x61,"apexPairSignature");
                    boolean guard=!key.equals("pair-refresh-read")&&!key.equals("pair-refresh-signature")&&
                        (CasBytecodePatch.property(abc,row,0x60,replaced)||CasBytecodePatch.property(abc,row,0x66,replaced));
                    if(read||signature||guard) {row.operands[0]=member(abc,read?"ApexFormsObservedSim":signature?"apexFormsSignature":"apexLastId");changes++;}
                }
                if(changes<1)throw new AssertionError("No immediate pair acknowledgement mutation: "+key);
                target.setModified();break;
            }
            case "frame-call":case "frame-gate":case "frame-write":case "frame-ready":case "frame-cleanup":case "frame-deadline":case "frame-cli-event":case "frame-cli-yield":
            case "frame-native-ready":case "frame-target-ready":case "notify-call":case "notify-lifetime":case "notify-write":case "notify-listener":case "notify-restart":case "notify-bound-return": {
                var instance=abc.instance_info.get(abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain"));
                String method=key.startsWith("notify-")?(key.equals("notify-listener")?"ApexInitialize":"ApexPresentationNotify"):
                    (key.equals("frame-ready")||key.equals("frame-native-ready")||key.equals("frame-target-ready"))?"ApexPresentationReady":key.equals("frame-cleanup")?"ApexPresentationStop":
                    key.equals("frame-deadline")?"ApexPresentationSchedule":key.startsWith("frame-cli-")?"ApexTick":"ApexPresentationFrame";
                var target=CasBytecodePatch.ownedBody(abc,instance,method);int changes=0;boolean inGuard=false,firstNotifyReturn=false;
                for(var row:target.getCode().code) {
                    if(CasBytecodePatch.property(abc,row,0x66,"ENTER_FRAME"))inGuard=true;
                    if(key.equals("frame-native-ready")&&(CasBytecodePatch.property(abc,row,0x60,"mCurrSimInfo")||CasBytecodePatch.property(abc,row,0x66,"mCurrSimInfo"))) {row.operands[0]=member(abc,"apexLastId");changes++;}
                    if(key.equals("frame-target-ready")&&(CasBytecodePatch.property(abc,row,0x60,"apexPresentationSim")||CasBytecodePatch.property(abc,row,0x66,"apexPresentationSim"))) {row.operands[0]=member(abc,"apexLastId");changes++;}
                    if(CasBytecodePatch.opcode(row,0x47))firstNotifyReturn=true;
                    if(key.equals("notify-bound-return")&&!firstNotifyReturn&&(CasBytecodePatch.property(abc,row,0x60,"apexPresentationSim")||CasBytecodePatch.property(abc,row,0x66,"apexPresentationSim"))) {row.operands[0]=member(abc,"apexLastId");changes++;}
                    if(key.equals("notify-restart")&&(CasBytecodePatch.property(abc,row,0x60,"apexPresentationStarted")||CasBytecodePatch.property(abc,row,0x66,"apexPresentationStarted"))) {row.operands[0]=member(abc,"apexLastId");changes++;}
                    if(key.equals("notify-call")&&(CasBytecodePatch.property(abc,row,0x4f,"ApexPresentationSchedule")||CasBytecodePatch.property(abc,row,0x46,"ApexPresentationSchedule"))) {row.operands[0]=member(abc,"ApexExecute");changes++;}
                    if(key.equals("notify-lifetime")&&(CasBytecodePatch.property(abc,row,0x60,"apexPresentationListener")||CasBytecodePatch.property(abc,row,0x66,"apexPresentationListener"))) {row.operands[0]=member(abc,"apexLastId");changes++;}
                    if(key.equals("notify-write")&&CasBytecodePatch.property(abc,row,0x61,"apexPresentationSim")) {row.operands[0]=member(abc,"apexBoundSim");changes++;}
                    if(key.equals("notify-listener")&&CasBytecodePatch.stringLiteral(abc,row,"CASSetSimInfo")) {row.operands[0]=abc.constants.getStringId("CASUnexpectedMember",true);changes++;}
                    if(key.equals("frame-call")&&(CasBytecodePatch.property(abc,row,0x4f,"ApexTick")||CasBytecodePatch.property(abc,row,0x46,"ApexTick"))) {row.operands[0]=member(abc,"ApexExecute");changes++;}
                    if(key.equals("frame-gate")&&(CasBytecodePatch.property(abc,row,0x60,"apexTicking")||CasBytecodePatch.property(abc,row,0x66,"apexTicking"))) {row.operands[0]=member(abc,"apexPendingFields");changes++;}
                    if(key.equals("frame-write")&&CasBytecodePatch.property(abc,row,0x61,"apexPresentationMilliseconds")) {row.operands[0]=member(abc,"apexClaimNonce");changes++;}
                    if(key.equals("frame-ready")&&(CasBytecodePatch.property(abc,row,0x60,"apexFormsSelectedId")||CasBytecodePatch.property(abc,row,0x66,"apexFormsSelectedId"))) {row.operands[0]=member(abc,"apexLastId");changes++;}
                    if(key.equals("frame-cleanup")&&(CasBytecodePatch.property(abc,row,0x4f,"removeEventListener")||CasBytecodePatch.property(abc,row,0x46,"removeEventListener"))) {row.operands[0]=member(abc,"addEventListener");changes++;}
                    if(key.equals("frame-deadline")&&CasBytecodePatch.opcode(row,0x25)&&row.operands[0]==2000) {row.operands[0]=20000;changes++;}
                    if(key.equals("frame-cli-event")&&CasBytecodePatch.property(abc,row,0x66,"ENTER_FRAME")) {row.operands[0]=member(abc,"CONNECT");changes++;}
                    if(key.equals("frame-cli-yield")&&inGuard&&(CasBytecodePatch.property(abc,row,0x60,"apexReceiving")||CasBytecodePatch.property(abc,row,0x66,"apexReceiving"))) {row.operands[0]=member(abc,"apexLastId");changes++;}
                }
                if(changes<1)throw new AssertionError("No bootstrap fixture mutation: "+key);
                target.setModified();break;
            }
            case "frame-lease":rows.get(p-10).operands[0]=member(abc,"apexFormsBootstrap");break;
            case "lease-branch":rows.set(p-8,new AVM2Instruction(0,0x11,rows.get(p-8).operands.clone()));break;
            case "nonce":rows.get(p+1).operands[0]=member(abc,"apexBoundSim");break;
            case "send":rows.get(p+3).operands[0]=member(abc,"ApexExecute");break;
            case "stage":rows.get(p-6).operands[0]=abc.constants.getStringId("readback|",true);break;
            case "wire":rows.get(p).operands[0]=abc.constants.getStringId("ACK|",true);break;
            case "deadline":rows.get(p-13).operands[0]=member(abc,"owner_id");break;
            case "bound-owner-refresh": {
                int changes=0;
                for(var row:rows) if(CasBytecodePatch.property(abc,row,0x4f,"ApexFormsReadNativeState") ||
                    CasBytecodePatch.property(abc,row,0x46,"ApexFormsReadNativeState")) {
                    row.operands[0]=member(abc,"ApexFormsObservedSim");changes++;
                }
                if(changes!=1)throw new AssertionError("Expected one direct bound-owner readback");
                break;
            }
            case "palette-source": case "palette-slot": {
                int palette=CasBytecodePatch.uniqueLiteral(abc,body,"CasGetSwatchColorList"),at=-1;
                for(int i=0;i+3<palette;i++) if(CasBytecodePatch.property(abc,rows.get(i),0x66,"selection_variant_id") &&
                    CasBytecodePatch.opcode(rows.get(i+3),0x6d)) {at=i;break;}
                if(at<0)throw new AssertionError("No early palette assignment");
                if(key.equals("palette-source"))rows.get(at).operands[0]=member(abc,"selection_base_id");
                else rows.get(at+3).operands[0]++;
                break;
            }
            case "bootstrap-state":case "bootstrap-guard": {
                var instance=abc.instance_info.get(abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain"));
                int at=CasBytecodePatch.settledBootstrapAssignment(abc,instance);
                var bootstrap=CasBytecodePatch.ownedBody(abc,instance,"ApexFormsOwnedTick");var b=bootstrap.getCode().code;
                if(key.equals("bootstrap-state"))b.get(at-2).operands[0]=abc.constants.getStringId("unbound",true);
                else b.set(at+3,new AVM2Instruction(0,0x11,b.get(at+3).operands.clone()));
                bootstrap.setModified();break;
            }
            default:throw new AssertionError("Unknown case");
        }
        body.setModified();var bytes=new ByteArrayOutputStream();abc.saveToStream(bytes);
        var serialized=new ABC(new ABCInputStream(new MemoryInputStream(bytes.toByteArray())),abc.getSwf(),null);
        boolean accepted=true;try {check(serialized);}catch(IllegalArgumentException|IllegalStateException error){accepted=false;}
        if(accepted!=key.equals("exact"))throw new AssertionError("Unexpected validation: "+key);
        System.out.println("PASS "+key);
    }
}
