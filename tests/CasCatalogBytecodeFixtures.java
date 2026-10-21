// Mutate compiled owned methods only; no game, profile or artifact writes.
import java.util.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;

public class CasCatalogBytecodeFixtures {
    public static void main(String[] args)throws Exception {
        var abc=CasBytecodePatch.load(args[0]);
        var instance=abc.instance_info.get(abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain"));
        final String mode=args[1];
        if(mode.equals("extra-argument") || mode.equals("missing-outfit-prefix")) {
            var body=CasBytecodePatch.ownedBody(abc,instance,"ApexCatalogReadEquipped");
            boolean changed=false;
            for(var op:body.getCode().code) {
                if(mode.equals("extra-argument") && CasBytecodePatch.property(abc,op,0x46,"ApexNativeExchange")) {
                    op.operands[1]=2;changed=true;
                }
                if(mode.equals("missing-outfit-prefix") && op.definition.instructionCode==0x2c &&
                        abc.constants.getString(op.operands[0]).equals("EQUIPPED|")) {
                    op.operands[0]=0;changed=true;
                }
            }
            CasBytecodePatch.require(changed,"Fixture failed to mutate the inventory request.");
        } else if(mode.equals("transport-wait")) {
            int member=-1;
            for(var trait:instance.instance_traits.traits)
                if(CasBytecodePatch.name(abc,trait).equals("apexAwaiting"))member=trait.name_index;
            CasBytecodePatch.require(member>=0,"Missing native transport field.");
            var frame=CasBytecodePatch.ownedBody(abc,instance,"ApexCatalogFrame");
            frame.insertAll(2,List.of(new AVM2Instruction(0,0x60,new int[]{member}),new AVM2Instruction(0,0x29,new int[0])));
        } else if(mode.equals("style-regrids")) {
            int member=-1;
            for(var trait:instance.instance_traits.traits)
                if(CasBytecodePatch.name(abc,trait).equals("apexCatalogSignature"))member=trait.name_index;
            CasBytecodePatch.require(member>=0,"Missing native layout signature.");
            var slide=CasBytecodePatch.ownedBody(abc,instance,"ApexCatalogSlide");
            slide.insertAll(2,List.of(new AVM2Instruction(0,0xd0,new int[0]),new AVM2Instruction(0,0x2c,new int[]{0}),
                new AVM2Instruction(0,0x61,new int[]{member})));
        } else if(!mode.equals("valid"))throw new IllegalArgumentException("Unknown fixture.");
        boolean refused=false;
        try {CasBytecodePatch.verifyCatalogWorkspace(abc,instance);}
        catch(IllegalArgumentException expected){refused=true;}
        CasBytecodePatch.require(refused!=mode.equals("valid"),"Compiled catalog gate accepted a regression or rejected the valid build.");
        System.out.println("PASS "+mode);
    }
}
