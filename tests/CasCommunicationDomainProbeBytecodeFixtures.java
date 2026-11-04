import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;

public class CasCommunicationDomainProbeBytecodeFixtures {
    static MethodBody body(ABC a,String type,String n,boolean statik){return a.findBody(CasCommunicationDomainProbePatch.method(a,type,n,statik).method_info);}
    static MethodBody object(ABC a){return body(a,CasCommunicationDomainProbePatch.COMM,CasCommunicationDomainProbePatch.OBJECT_PROBE,false);}
    static MethodBody manager(ABC a){return body(a,CasCommunicationDomainProbePatch.MANAGER,CasCommunicationDomainProbePatch.MANAGER_PROBE,true);}
    static MethodBody button(ABC a){return body(a,CasCommunicationDomainProbePatch.BUTTON,CasCommunicationDomainProbePatch.BUTTON_PROBE,false);}
    static void prop(ABC a,MethodBody b,int opcode,String from,int to){for(var i:b.getCode().code)if(i.definition.instructionCode==opcode&&from.equals(CasStructuralRolesPatch.name(a,i.operands[0]))){i.operands[0]=to;b.setCode(b.getCode());return;}throw new IllegalArgumentException("Fixture missed "+from);}
    static String quote(String s){return "\""+s.replace("\\","\\\\").replace("\"","\\\"")+"\"";}
    static String dump(ABC a,MethodBody b)throws Exception {
        var out=new StringBuilder("[");var addresses=CasStructuralRolesPatch.addresses(b);boolean comma=false;
        for(var i:b.getCode().code){if(comma)out.append(',');comma=true;int op=i.definition.instructionCode;out.append("{\"op\":").append(op);
            if(op==0x2c)out.append(",\"value\":").append(quote(a.constants.getString(i.operands[0])));
            else if(Set.of(0x60,0x66,0x46).contains(op))out.append(",\"value\":").append(quote(CasStructuralRolesPatch.name(a,i.operands[0])));
            if(op==0x11)out.append(",\"target\":").append(CasStructuralRolesPatch.index(addresses,CasStructuralRolesPatch.target(i,0)));
            if(op==0x55)out.append(",\"count\":").append(i.operands[0]);
            if(op==0x46)out.append(",\"argc\":").append(i.operands[1]);out.append('}');
        }return out.append(']').toString();
    }
    public static void main(String[] args)throws Exception {
        var base=CasStructuralRolesPatch.load(args[0]);var candidate=CasStructuralRolesPatch.load(args[1]);String tgi=CasCommunicationDomainProbePatch.BASELINES.get(CasStructuralRolesPatch.sha(java.nio.file.Files.readAllBytes(java.nio.file.Path.of(args[0]))));
        CasCommunicationDomainProbePatch.verify(base,candidate,tgi);
        if(args.length==3&&args[2].equals("--dump")){System.out.println("{\"object\":"+dump(candidate,object(candidate))+",\"manager\":"+dump(candidate,manager(candidate))+",\"button\":"+dump(candidate,button(candidate))+"}");return;}
        System.out.println("PASS serialized-valid");
        for(String mode:List.of("object-index-field","object-array-escape","object-provider","manager-static-receiver","manager-singleton-binding","manager-listener-key","manager-actual-object-call","manager-null-branch","manager-call-arguments","button-manager-binding","button-manager-call","probe-scope","probe-frame","probe-exceptions","native-constructor","native-index-helper","native-dispatch")){
            var a=CasStructuralRolesPatch.reparse(candidate);MethodBody changed=null;
            if(mode.equals("object-index-field"))prop(a,object(a),0x66,"apexCommIndex",CasCommunicationDomainProbePatch.field(a,CasCommunicationDomainProbePatch.COMM,"mFunctions",false));
            if(mode.equals("object-array-escape")){changed=object(a);for(var i:changed.getCode().code)if(i.definition.instructionCode==0x66&&"length".equals(CasStructuralRolesPatch.name(a,i.operands[0]))){i.definition=CasStructuralRolesPatch.ins(0x02).definition;i.operands=new int[0];break;}}
            if(mode.equals("object-provider")){changed=object(a);changed.getCode().code.get(3).operands[0]=a.constants.getStringId("foreign-provider",true);}
            if(mode.equals("manager-static-receiver")){changed=manager(a);changed.getCode().code.set(2,CasStructuralRolesPatch.ins(0x60,a.instance_info.get(a.findClassByName(CasCommunicationDomainProbePatch.COMM)).name_index));}
            if(mode.equals("manager-singleton-binding"))prop(a,manager(a),0x66,"instance",a.constants.getPublicQnameId("instance",true));
            if(mode.equals("manager-listener-key"))prop(a,manager(a),0x66,"UsingControllerToggled",a.constants.getPublicQnameId("OtherMessage",true));
            if(mode.equals("manager-actual-object-call"))prop(a,manager(a),0x46,CasCommunicationDomainProbePatch.OBJECT_PROBE,CasCommunicationDomainProbePatch.method(a,CasCommunicationDomainProbePatch.COMM,"ApexCommIndexStats",true).name_index);
            if(mode.equals("manager-null-branch")){changed=manager(a);for(var i:changed.getCode().code)if(i.definition.instructionCode==0x11){i.operands[0]++;break;}}
            if(mode.equals("manager-call-arguments")){changed=manager(a);for(var i:changed.getCode().code)if(i.definition.instructionCode==0x46)i.operands[1]=1;}
            if(mode.equals("button-manager-binding")){changed=button(a);for(var i:changed.getCode().code)if(i.definition.instructionCode==0x60)i.operands[0]=a.instance_info.get(a.findClassByName(CasCommunicationDomainProbePatch.COMM)).name_index;}
            if(mode.equals("button-manager-call"))prop(a,button(a),0x46,CasCommunicationDomainProbePatch.MANAGER_PROBE,CasCommunicationDomainProbePatch.method(a,CasCommunicationDomainProbePatch.COMM,"ApexCommIndexStats",true).name_index);
            if(mode.equals("probe-scope"))manager(a).max_scope_depth++;
            if(mode.equals("probe-frame"))object(a).max_regs++;
            if(mode.equals("probe-exceptions"))button(a).exceptions=new ABCException[]{new ABCException()};
            if(mode.equals("native-constructor")){changed=a.findBody(a.instance_info.get(a.findClassByName(CasCommunicationDomainProbePatch.BUTTON)).iinit_index);changed.getCode().code.add(0,CasStructuralRolesPatch.ins(0x02));}
            if(mode.equals("native-index-helper")){changed=body(a,CasCommunicationDomainProbePatch.COMM,"ApexCommIndexedHas",false);changed.getCode().code.add(0,CasStructuralRolesPatch.ins(0x02));}
            if(mode.equals("native-dispatch")){changed=body(a,CasCommunicationDomainProbePatch.COMM,"Dispatch",false);changed.getCode().code.add(0,CasStructuralRolesPatch.ins(0x02));}
            if(changed!=null){changed.setCode(changed.getCode());changed.setModified();}
            boolean refused=false;try{CasCommunicationDomainProbePatch.verify(base,a,tgi);}catch(Exception expected){refused=true;}
            if(!refused)throw new IllegalArgumentException("Corruption accepted: "+mode);System.out.println("PASS "+mode);
        }
    }
}
