import java.util.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;
public class CasIdleMemberBytecodeFixtures {
    static void verify(com.jpexs.decompiler.flash.abc.ABC abc)throws Exception {
        var instance=abc.instance_info.get(abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain"));
        var helper=CasBytecodePatch.ownedBody(abc,instance,"ApexIdleMemberChanged");
        CasBytecodePatch.require(CasBytecodePatch.propertyCalls(abc,helper).equals(Set.of("test")),"Idle observation performed native work.");
        var tick=CasBytecodePatch.ownedBody(abc,instance,"ApexTick");int observed=-1,reset=-1;
        for(int i=0;i<tick.getCode().code.size();i++) {
            var op=tick.getCode().code.get(i);
            if(CasBytecodePatch.property(abc,op,0x46,"ApexIdleMemberChanged")) {
                CasBytecodePatch.require(observed<0 && op.operands[1]==1,"Idle observation has wrong invocation.");observed=i;
            }
            if(observed>=0 && i>observed && i<observed+7 &&
                (CasBytecodePatch.property(abc,op,0x4f,"ApexResetSocket") || CasBytecodePatch.property(abc,op,0x46,"ApexResetSocket")))reset=i;
        }
        CasBytecodePatch.require(observed>=0 && reset>observed && reset<CasBytecodePatch.uniqueLiteral(abc,tick,"CASGetSimInfo"),
            "Idle member changes must retire the old peer before native reconnect/readback.");
    }
    public static void main(String[] args)throws Exception {
        var abc=CasBytecodePatch.load(args[0]);var instance=abc.instance_info.get(abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain"));
        String mode=args[1];
        if(mode.equals("missing-idle-call")) {
            int replacement=-1;
            for(var trait:instance.instance_traits.traits)if(CasBytecodePatch.name(abc,trait).equals("ApexFormsObservedSim"))replacement=trait.name_index;
            CasBytecodePatch.require(replacement>0,"Native observation fixture missing.");boolean changed=false;
            var tick=CasBytecodePatch.ownedBody(abc,instance,"ApexTick");
            for(var op:tick.getCode().code)if(CasBytecodePatch.property(abc,op,0x46,"ApexIdleMemberChanged")){op.operands[0]=replacement;changed=true;}
            CasBytecodePatch.require(changed,"Fixture did not remove idle rebind.");tick.setModified();
        } else if(mode.equals("idle-native-query")) {
            int member=-1;
            for(int i=1;i<abc.constants.getMultinameCount();i++) {
                var q=abc.constants.getMultiname(i);
                if(q.name_index>0 && abc.constants.getString(q.name_index).equals("CallGameService")){member=i;break;}
            }
            CasBytecodePatch.require(member>0,"Game service fixture missing.");
            var body=CasBytecodePatch.ownedBody(abc,instance,"ApexIdleMemberChanged");
            body.insertAll(2,List.of(new AVM2Instruction(0,0xd0,new int[0]),new AVM2Instruction(0,0x2c,new int[]{0}),
                new AVM2Instruction(0,0x20,new int[0]),new AVM2Instruction(0,0x4f,new int[]{member,2})));
            body.max_stack=Math.max(body.max_stack,3);body.setModified();
        } else if(!mode.equals("valid"))throw new IllegalArgumentException("Unknown fixture.");
        var saved=new java.io.ByteArrayOutputStream();abc.saveToStream(saved);
        abc=new com.jpexs.decompiler.flash.abc.ABC(new com.jpexs.decompiler.flash.abc.ABCInputStream(
            new com.jpexs.helpers.MemoryInputStream(saved.toByteArray())),abc.getSwf(),null);
        boolean refused=false;try{verify(abc);}catch(IllegalArgumentException expected){refused=true;}
        CasBytecodePatch.require(refused!=mode.equals("valid"),"Idle member regression was not rejected or the valid build failed.");
        System.out.println("PASS "+mode);
    }
}
