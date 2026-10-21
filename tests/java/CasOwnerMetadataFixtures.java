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
    }
    public static void main(String[] args) throws Exception {
        Logger.getLogger("com.jpexs.decompiler.flash.SWFInputStream").setLevel(Level.OFF);
        String key=args[0];var abc=CasBytecodePatch.load(args[1]);check(abc);
        var body=CasBytecodePatch.ownedBody(abc,abc.instance_info.get(
            abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain")),"ApexReadback");
        var rows=body.getCode().code;int p=CasBytecodePatch.uniqueLiteral(abc,body,"POLL|");
        switch(key) {
            case "exact":break;
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
