// Verify the actual serialized native-method transplant, including refusal.
import java.util.*;
public class CasEquippedBytecodeFixtures {
    public static void main(String[] args)throws Exception {
        var original=CasBytecodePatch.load(args[0]);var compiled=CasBytecodePatch.load(args[1]);
        String mode=args[2];
        if(mode.equals("selection-batch")) {
            var body=CasBytecodePatch.classMethod(compiled,"widgets.CAS.Customizer.ClothingPanel","Refresh");int member=-1;
            for(int i=1;i<compiled.constants.getMultinameCount();i++) {
                var q=compiled.constants.getMultiname(i);
                if(q.name_index>0 && compiled.constants.getString(q.name_index).equals("SetSelectionState")) {member=i;break;}
            }
            CasBytecodePatch.require(member>0,"Native per-item selection method absent.");boolean changed=false;
            for(var op:body.getCode().code)if(CasBytecodePatch.property(compiled,op,0x4f,"SelectAll") ||
                CasBytecodePatch.property(compiled,op,0x46,"SelectAll")) {op.operands[0]=member;changed=true;}
            CasBytecodePatch.require(changed,"Fixture did not regress the native batch.");body.setModified();
        } else if(mode.equals("clock-package")) {
            var body=CasBytecodePatch.classMethod(compiled,"widgets.CAS.data.CatalogDataFeed","RequestData");boolean changed=false;
            for(var op:body.getCode().code)if(op.definition.instructionCode==0x5d || op.definition.instructionCode==0x60) {
                var q=compiled.constants.getMultiname(op.operands[0]);
                if(compiled.constants.getString(q.name_index).equals("getTimer")) {
                    q.name_index=compiled.constants.getStringId("flash",true);changed=true;
                }
            }
            CasBytecodePatch.require(changed,"Fixture did not regress the Flash binding.");body.setModified();
        } else if(!mode.equals("valid")) {
            String type=mode.equals("RequestData")?"widgets.CAS.data.CatalogDataFeed":"widgets.CAS.Customizer.ClothingPanel";
            var body=CasBytecodePatch.classMethod(compiled,type,mode);boolean changed=false;
            for(var op:body.getCode().code)if(op.definition.instructionCode==0x2c) {
                String value=compiled.constants.getString(op.operands[0]);
                if(value.startsWith("ApexEquipped") || value.equals("ApexCatalogPerformance")) {op.operands[0]=0;changed=true;}
            }
            CasBytecodePatch.require(changed,"Fixture did not remove the adapter service.");body.setModified();
        }
        // Round-trip before checking: stale MethodBody byte caches must not hide
        // either an injected regression or the intended native adapter.
        var bytes=new java.io.ByteArrayOutputStream();compiled.saveToStream(bytes);
        compiled=new com.jpexs.decompiler.flash.abc.ABC(new com.jpexs.decompiler.flash.abc.ABCInputStream(
            new com.jpexs.helpers.MemoryInputStream(bytes.toByteArray())),compiled.getSwf(),null);
        boolean refused=false;
        try {CasBytecodePatch.equippedAdapters(original,compiled);}catch(IllegalArgumentException expected){refused=true;}
        CasBytecodePatch.require(refused!=mode.equals("valid"),"Equipped native gate accepted a regression or rejected the valid build.");
        System.out.println("PASS "+mode);
    }
}
