// Check the serialized dispatcher and retained donor body, including corruption.
public class CasOutfitSchedulingBytecodeFixtures {
    public static void main(String[] args)throws Exception {
        var original=CasBytecodePatch.load(args[0]);var compiled=CasBytecodePatch.load(args[1]);String mode=args[2];
        var body=CasBytecodePatch.currentOutfitAdapter(original,compiled);
        CasBytecodePatch.require(body!=null,"Actual donor refresh method is required.");
        int changed=0;
        for(var op:body.getCode().code) {
            if(mode.equals("service") && CasBytecodePatch.stringLiteral(compiled,op,"ApexPanelRefreshGate")) {op.operands[0]=0;changed++;}
            if(mode.equals("fallback") && CasBytecodePatch.opcode(op,0x12) && changed==0) {op.operands[0]=2;changed++;}
        }
        if(mode.equals("retained-body")) {body.getCode().code.remove(body.getCode().code.size()-1);changed++;}
        if(!mode.equals("valid"))CasBytecodePatch.require(changed>0,"Regression was not introduced.");
        body.setModified();
        for(int i=0;i<compiled.bodies.size();i++)if(compiled.bodies.get(i).method_info==body.method_info)compiled.bodies.set(i,body);
        var bytes=new java.io.ByteArrayOutputStream();compiled.saveToStream(bytes);
        compiled=new com.jpexs.decompiler.flash.abc.ABC(new com.jpexs.decompiler.flash.abc.ABCInputStream(
            new com.jpexs.helpers.MemoryInputStream(bytes.toByteArray())),compiled.getSwf(),null);
        boolean refused=false;
        try {CasBytecodePatch.verifyCurrentOutfitAdapter(compiled,compiled.findBody(body.method_info),
            CasBytecodePatch.staticMethod(original,"dcc.history.HistoryHost","RefreshCurrentOutfit").getCodeBytes());}
        catch(IllegalArgumentException expected){refused=true;}
        CasBytecodePatch.require(refused!=mode.equals("valid"),"Outfit dispatcher misclassified "+mode);
        System.out.println("PASS "+mode);
    }
}
