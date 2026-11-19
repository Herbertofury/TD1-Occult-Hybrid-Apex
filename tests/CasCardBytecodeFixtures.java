// Actual compiler-output checks; no game/process/profile access.
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;

public class CasCardBytecodeFixtures {
    public static void main(String[] args)throws Exception {
        var original=CasBytecodePatch.load(args[0]);var compiled=CasBytecodePatch.load(args[1]);
        var body=CasBytecodePatch.classMethod(compiled,"widgets.CAS.controls.CASClothingPanelCellViewMain","height");
        String mode=args[2];boolean changed=false;
        for(var op:body.getCode().code) {
            if(mode.equals("missing-marker") && op.definition.instructionCode==0x2c &&
                    compiled.constants.getString(op.operands[0]).equals("apexCatalogCardScale")) {
                op.operands[0]=0;changed=true;
            }
            if(mode.equals("unscaled-height") && op.definition.instructionCode==0xa2) {
                op.definition= new AVM2Instruction(0,0xa0,new int[0]).definition;changed=true;
            }
        }
        if(!mode.equals("valid"))CasBytecodePatch.require(changed,"Card fixture did not mutate the compiled getter.");
        boolean refused=false;
        try {CasBytecodePatch.cardHeightAdapter(original,compiled);}
        catch(IllegalArgumentException expected){refused=true;}
        CasBytecodePatch.require(refused!=mode.equals("valid"),"Card adapter accepted regression or rejected valid compiler output.");
        System.out.println("PASS "+mode);
    }
}
