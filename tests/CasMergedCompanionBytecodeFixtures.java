// Check the serialized identity adapters rather than matching source strings.
public class CasMergedCompanionBytecodeFixtures {
    public static void main(String[] args)throws Exception {
        var original=CasBytecodePatch.load(args[0]);var compiled=CasBytecodePatch.load(args[1]);String mode=args[2];
        if(!mode.equals("valid")) {
            String type=mode.equals("eye-lease")?"SavedOutfitNames":mode.equals("preview-recheck")?"OutfitPreview":"AgeFilter";
            String method=mode.equals("eye-lease")?"EyeContext":mode.equals("preview-recheck")?"Context":mode.equals("cached-member")?"Current":"Read";
            var body=CasBytecodePatch.staticMethod(compiled,"dcc.history."+type,method);boolean changed=false;int seen=0;
            for(var op:body.getCode().code) {
                if(mode.equals("service") && CasBytecodePatch.stringLiteral(compiled,op,"appearance-context")) {op.operands[0]=0;changed=true;}
                if(mode.equals("preview-recheck") && CasBytecodePatch.stringLiteral(compiled,op,"appearance-context") && ++seen==2) {op.operands[0]=0;changed=true;}
                if(mode.equals("eye-lease") && CasBytecodePatch.property(compiled,op,0x66,"apexAppearanceLease")) {
                    var q=compiled.constants.getMultiname(op.operands[0]);q.name_index=compiled.constants.getStringId("missingLease",true);changed=true;
                }
                if(mode.equals("cached-member") && (CasBytecodePatch.property(compiled,op,0x46,"Read")||CasBytecodePatch.property(compiled,op,0x4f,"Read"))) {
                    var q=compiled.constants.getMultiname(op.operands[0]);q.name_index=compiled.constants.getStringId("Group",true);changed=true;
                }
            }
            CasBytecodePatch.require(changed,"Fixture failed to introduce its regression: "+mode);body.setModified();
        }
        var bytes=new java.io.ByteArrayOutputStream();compiled.saveToStream(bytes);
        compiled=new com.jpexs.decompiler.flash.abc.ABC(new com.jpexs.decompiler.flash.abc.ABCInputStream(
            new com.jpexs.helpers.MemoryInputStream(bytes.toByteArray())),compiled.getSwf(),null);
        boolean refused=false;
        try {CasBytecodePatch.companionAdapters(original,compiled);}catch(IllegalArgumentException expected){refused=true;}
        CasBytecodePatch.require(refused!=mode.equals("valid"),"Companion identity gate misclassified "+mode);
        System.out.println("PASS "+mode);
    }
}
