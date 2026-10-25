import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;

public class CasCommunicationDependencyBytecodeFixtures {
    interface Change {void apply(ABC a)throws Exception;}
    static void expect(ABC index,ABC valid,String name,Change change)throws Exception {
        var bad=CasStructuralRolesPatch.reparse(valid);change.apply(bad);boolean rejected=false;
        try{CasCommunicationDependencyPatch.verifyButton(index,CasStructuralRolesPatch.reparse(bad));}catch(IllegalArgumentException error){rejected=true;}
        if(!rejected)throw new IllegalArgumentException("Corruption accepted: "+name);System.out.println("PASS "+name);
    }
    static com.jpexs.decompiler.flash.abc.types.MethodBody diagnostic(ABC a){return a.findBody(CasCommunicationDependencyPatch.buttonMethod(a,CasCommunicationDependencyPatch.DIAGNOSTIC).method_info);}
    public static void main(String[] args)throws Exception {
        var raw=CasStructuralRolesPatch.load(args[0]);var compiled=CasStructuralRolesPatch.load(args[1]);
        var index=CasCommunicationDependencyPatch.communication(raw,raw,compiled);var valid=CasStructuralRolesPatch.load(args[2]);
        CasCommunicationDependencyPatch.verifyButton(index,valid);System.out.println("PASS valid");
        expect(index,valid,"wrong-lexical-class",a->{for(var i:diagnostic(a).getCode().code)if(i.definition.instructionCode==0x60)i.operands[0]=a.instance_info.get(a.findClassByName(CasCommunicationDependencyPatch.BUTTON)).name_index;diagnostic(a).setCode(diagnostic(a).getCode());});
        expect(index,valid,"wrong-stats-call",a->{for(var i:diagnostic(a).getCode().code)if(i.definition.instructionCode==0x46)i.operands[0]=CasCommunicationDependencyPatch.buttonMethod(a,"Draw").name_index;diagnostic(a).setCode(diagnostic(a).getCode());});
        expect(index,valid,"wrong-provider",a->{var b=diagnostic(a);b.getCode().code.get(3).operands[0]=a.constants.getStringId("wrong-provider",true);b.setCode(b.getCode());});
        expect(index,valid,"wrong-argument-count",a->{var b=diagnostic(a);b.getCode().code.get(6).operands[1]=1;b.setCode(b.getCode());});
        expect(index,valid,"wrong-return",a->{var b=diagnostic(a);b.getCode().code.set(8,CasStructuralRolesPatch.ins(0x47));b.setCode(b.getCode());});
        expect(index,valid,"wrong-frame",a->{diagnostic(a).max_regs=2;});
        expect(index,valid,"wrong-scope",a->{diagnostic(a).init_scope_depth++;});
        expect(index,valid,"wrong-signature",a->{a.method_info.get(diagnostic(a).method_info).ret_type=a.constants.getPublicQnameId("String",false);});
        expect(index,valid,"button-draw-changed",a->{var b=a.findBody(CasCommunicationDependencyPatch.buttonMethod(a,"Draw").method_info);b.getCode().code.add(0,CasStructuralRolesPatch.ins(0x02));b.setCode(b.getCode());});
        expect(index,valid,"native-constructor-changed",a->{var b=a.findBody(a.instance_info.get(a.findClassByName(CasCommunicationDependencyPatch.BUTTON)).iinit_index);b.getCode().code.add(0,CasStructuralRolesPatch.ins(0x02));b.setCode(b.getCode());});
        expect(index,valid,"communication-dispatch-changed",a->{var b=CasCommunicationIndexPatch.body(a,"Dispatch");b.getCode().code.add(0,CasStructuralRolesPatch.ins(0x02));b.setCode(b.getCode());});
    }
}
