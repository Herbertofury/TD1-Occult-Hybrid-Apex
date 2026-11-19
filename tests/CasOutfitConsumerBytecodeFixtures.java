import java.util.*;
public class CasOutfitConsumerBytecodeFixtures {
    public static void main(String[] args)throws Exception {
        var original=CasBytecodePatch.load(args[0]);var compiled=CasBytecodePatch.load(args[1]);String mode=args[2];
        if(mode.equals("shared-linkage")) {
            int shared=CasBytecodePatch.staticMethod(original,"dcc.history.HistoryHost","CurrentOutfitClick").method_info;
            var attach=CasBytecodePatch.staticMethod(original,"dcc.history.HistoryHost","Attach");int changed=0;
            for(var op:attach.getCode().code)if(CasBytecodePatch.opcode(op,0x40)&&op.operands[0]==shared) {op.operands[0]++;changed++;}
            CasBytecodePatch.require(changed==1,"Actual shared function linkage required.");attach.setModified();boolean refused=false;
            try {CasBytecodePatch.consumerAdapters(original,compiled);}catch(IllegalArgumentException expected){refused=true;}
            CasBytecodePatch.require(refused,"A detached anonymous save callback must not pass the shared-sink gate.");
            System.out.println("PASS "+mode);return;
        }
        var bodies=CasBytecodePatch.consumerAdapters(original,compiled);
        CasBytecodePatch.require(bodies.size()==3 && bodies.get(0).exceptions.length>0,"Actual native consumers, shared sink and catch/finally regions required.");
        compiled.instance_info=original.instance_info;compiled.class_info=original.class_info;
        compiled.method_info=original.method_info;compiled.script_info=original.script_info;
        compiled.metadata_info=original.metadata_info;compiled.bodies=new ArrayList<>(original.bodies);
        for(var body:bodies)for(int i=0;i<compiled.bodies.size();i++)if(compiled.bodies.get(i).method_info==body.method_info)compiled.bodies.set(i,body);
        var bytes=new java.io.ByteArrayOutputStream();compiled.saveToStream(bytes);
        compiled=new com.jpexs.decompiler.flash.abc.ABC(new com.jpexs.decompiler.flash.abc.ABCInputStream(
            new com.jpexs.helpers.MemoryInputStream(bytes.toByteArray())),compiled.getSwf(),null);
        var changed=compiled.findBody(bodies.get(0).method_info);
        if(mode.equals("callback"))changed.getCode().code.get(6).operands[0]=changed.getCode().code.get(5).operands[0];
        if(mode.equals("fallback"))changed.getCode().code.get(11).operands[0]=2;
        if(mode.equals("exception"))changed.exceptions[0].target++;
        if(mode.equals("retained"))changed.getCode().code.remove(changed.getCode().code.size()-1);
        if(mode.equals("sink-service"))compiled.findBody(bodies.get(2).method_info).getCode().code.get(1).operands[0]=compiled.constants.getStringId("ApexPanelConsumer",true);
        if(mode.equals("sink-fallback"))compiled.findBody(bodies.get(2).method_info).getCode().code.get(4).operands[0]=2;
        if(mode.startsWith("sink-"))compiled.findBody(bodies.get(2).method_info).setModified();
        changed.setModified();boolean refused=false;
        try {for(var body:bodies)CasBytecodePatch.verifyConsumerPrefix(compiled,compiled.findBody(body.method_info),original.findBody(body.method_info));}
        catch(IllegalArgumentException expected){refused=true;}
        CasBytecodePatch.require(refused!=mode.equals("valid"),"Consumer prefix misclassified "+mode);
        System.out.println("PASS "+mode);
    }
}
