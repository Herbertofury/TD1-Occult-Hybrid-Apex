public class CasCompanionGridFixtures {
    public static void main(String[] args)throws Exception {
        var abc=CasBytecodePatch.load(args[0]);String mode=args[1];
        int index=abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain");
        var instance=abc.instance_info.get(index);
        if(!mode.equals("valid")) {
            var body=CasBytecodePatch.ownedBody(abc,instance,mode.equals("status")?"ApexCompanionStatus":"ApexCompanionCommand");
            var code=body.getCode().code;boolean changed=false;
            if(mode.equals("self-busy"))for(var op:code)if(CasBytecodePatch.property(abc,op,0x66,"apexEquippedActive") || CasBytecodePatch.property(abc,op,0x60,"apexEquippedActive")) {
                var q=abc.constants.getMultiname(op.operands[0]);q.name_index=abc.constants.getStringId("apexReceiving",true);changed=true;break;
            }
            if(!mode.equals("self-busy"))for(int i=1;i<code.size();++i)if(CasBytecodePatch.property(abc,code.get(i),0x46,"ApexCatalogCells")) {
                var q=abc.constants.getMultiname(code.get(i-1).operands[0]);
                q.name_index=abc.constants.getStringId("mcTileList",true);changed=true;break;
            }
            CasBytecodePatch.require(changed,"Fixture did not substitute its wrong container");body.setModified();
        }
        boolean refused=false;
        try{CasBytecodePatch.verifyCatalogCompanion(abc,instance);}catch(IllegalArgumentException expected){refused=true;}
        CasBytecodePatch.require(refused!=mode.equals("valid"),"Companion grid gate misclassified "+mode);
        System.out.println("PASS "+mode);
    }
}
