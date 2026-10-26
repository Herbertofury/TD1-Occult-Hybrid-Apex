import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;

public class CasCommunicationRemovalMissBytecodeFixtures {
    static MethodBody body(ABC a,String n){return CasCommunicationRemovalMissPatch.body(a,n);}
    static String q(String s){return s==null?"null":"\""+s.replace("\\","\\\\").replace("\"","\\\"")+"\"";}
    static String dump(ABC a)throws Exception {
        var b=body(a,CasCommunicationRemovalMissPatch.HELPER);var addresses=CasStructuralRolesPatch.addresses(b);var out=new StringBuilder("{\"code\":[");boolean comma=false;
        for(var i:b.getCode().code){if(comma)out.append(',');comma=true;int op=i.definition.instructionCode;out.append("{\"op\":").append(op);
            if(op==0x60||op==0x66)out.append(",\"name\":").append(q(CasStructuralRolesPatch.name(a,i.operands[0])));
            if(op==0x11||op==0x12)out.append(",\"target\":").append(CasStructuralRolesPatch.index(addresses,CasStructuralRolesPatch.target(i,0)));out.append('}');
        }
        var e=b.exceptions[0];return out.append("],\"catch\":{\"from\":").append(CasStructuralRolesPatch.index(addresses,e.start)).append(",\"to\":").append(CasStructuralRolesPatch.index(addresses,e.end)).append(",\"target\":").append(CasStructuralRolesPatch.index(addresses,e.target)).append("},\"max_stack\":").append(b.max_stack).append(",\"max_scope\":").append(b.max_scope_depth-b.init_scope_depth).append(",\"flags\":").append(a.method_info.get(b.method_info).flags).append('}').toString();
    }
    static String dumpManager(ABC a)throws Exception {
        var b=CasCommunicationRemovalMissPatch.managerBody(a,CasCommunicationRemovalMissPatch.MANAGER_PROBE,true);var addresses=CasStructuralRolesPatch.addresses(b);var out=new StringBuilder("{\"native_singleton_qname\":").append(CasCommunicationRemovalMissPatch.originalSingleton(a)).append(",\"native_map_qname\":").append(CasCommunicationRemovalMissPatch.originalMap(a)[1]).append(",\"code\":[");boolean comma=false;
        for(var i:b.getCode().code){if(comma)out.append(',');comma=true;int op=i.definition.instructionCode;out.append("{\"op\":").append(op);
            if(Set.of(0x60,0x66,0x61,0x46,0xb2).contains(op))out.append(",\"name\":").append(q(CasStructuralRolesPatch.name(a,i.operands[0]))).append(",\"qname\":").append(i.operands[0]);
            if(op==0x2c)out.append(",\"value\":").append(q(a.constants.getString(i.operands[0])));
            if(op==0x11)out.append(",\"target\":").append(CasStructuralRolesPatch.index(addresses,CasStructuralRolesPatch.target(i,0)));
            if(op==0x55)out.append(",\"count\":").append(i.operands[0]);out.append('}');
        }return out.append("]}").toString();
    }
    public static void main(String[]args)throws Exception {
        var base=CasStructuralRolesPatch.load(args[0]);var valid=CasStructuralRolesPatch.load(args[1]);var change=CasCommunicationRemovalMissPatch.rewrite(valid,body(base,"RemoveFunction"));
        CasCommunicationRemovalMissPatch.verify(base,valid,change);
        if(args.length==3&&args[2].equals("--dump")){System.out.println(dump(valid));return;}
        if(args.length==3&&args[2].equals("--manager")){System.out.println(dumpManager(valid));return;}
        System.out.println("PASS serialized-valid");
        for(String mode:List.of("dispatch-guard","alias-guard","index-namespace","dictionary-strict","predicate-allocation","error-range","error-return","error-scope","prefix-argument","prefix-condition","prefix-fallback","prefix-callback","deferred-native-push","positive-native-hook","other-native-dispatch","native-constructor","owned-manager-static-getter","owned-manager-dynamic-map","owned-manager-missing-probe","owned-manager-reason","owned-manager-scope")){
            var a=CasStructuralRolesPatch.reparse(valid);MethodBody b=null;
            if(mode.equals("dispatch-guard")||mode.equals("alias-guard")||mode.equals("index-namespace")){
                b=body(a,CasCommunicationRemovalMissPatch.HELPER);String want=mode.equals("dispatch-guard")?"mbDispatching":mode.equals("alias-guard")?"apexCommAliased":"apexCommIndex";
                for(var i:b.getCode().code)if(i.definition.instructionCode==0x60&&want.equals(CasStructuralRolesPatch.name(a,i.operands[0]))){i.operands[0]=a.constants.getPublicQnameId(want,true);break;}
            }
            if(mode.equals("dictionary-strict")){b=body(a,CasCommunicationRemovalMissPatch.HELPER);for(var i:b.getCode().code)if(i.definition.instructionCode==0xac){i.definition=CasStructuralRolesPatch.ins(0xab).definition;break;}}
            if(mode.equals("predicate-allocation")){b=body(a,CasCommunicationRemovalMissPatch.HELPER);b.getCode().code.add(2,CasStructuralRolesPatch.ins(0x57));}
            if(mode.equals("error-range")){b=body(a,CasCommunicationRemovalMissPatch.HELPER);b.exceptions[0].start++;}
            if(mode.equals("error-return")){b=body(a,CasCommunicationRemovalMissPatch.HELPER);b.getCode().code.set(b.getCode().code.size()-2,CasStructuralRolesPatch.ins(0x26));}
            if(mode.equals("error-scope")){b=body(a,CasCommunicationRemovalMissPatch.HELPER);b.getCode().code.set(b.getCode().code.size()-3,CasStructuralRolesPatch.ins(0x29));}
            if(mode.equals("prefix-argument")){b=body(a,"RemoveFunction");b.getCode().code.set(3,CasStructuralRolesPatch.ins(0xd1));}
            if(mode.equals("prefix-condition")){b=body(a,"RemoveFunction");b.getCode().code.get(5).definition=CasStructuralRolesPatch.ins(0x11,0).definition;}
            if(mode.equals("prefix-fallback")){b=body(a,"RemoveFunction");b.getCode().code.get(5).operands[0]++;}
            if(mode.equals("prefix-callback")){b=body(a,"RemoveFunction");b.getCode().code.get(4).operands[0]=CasCommunicationRemovalMissPatch.method(a,"ApexCommCanIndex").name_index;}
            if(mode.equals("deferred-native-push")){b=body(a,"RemoveFunction");for(var i:b.getCode().code)if(i.definition.instructionCode==0x4f&&"push".equals(CasStructuralRolesPatch.name(a,i.operands[0]))){i.operands[0]=a.constants.getPublicQnameId("splice",true);break;}}
            if(mode.equals("positive-native-hook")){b=body(a,"RemoveFunction");for(var i:b.getCode().code)if(i.definition.instructionCode==0x4f&&"ApexCommRemoved".equals(CasStructuralRolesPatch.name(a,i.operands[0]))){i.operands[0]=CasCommunicationRemovalMissPatch.method(a,"ApexCommAdded").name_index;break;}}
            if(mode.equals("other-native-dispatch")){b=body(a,"Dispatch");b.getCode().code.add(0,CasStructuralRolesPatch.ins(0x02));}
            if(mode.equals("native-constructor")){b=a.findBody(a.instance_info.get(a.findClassByName(CasCommunicationRemovalMissPatch.TYPE)).iinit_index);b.getCode().code.add(0,CasStructuralRolesPatch.ins(0x02));}
            if(mode.equals("owned-manager-static-getter")){b=CasCommunicationRemovalMissPatch.managerBody(a,CasCommunicationRemovalMissPatch.MANAGER_PROBE,true);b.getCode().code.set(2,CasStructuralRolesPatch.ins(0xd0));}
            if(mode.equals("owned-manager-dynamic-map")){b=CasCommunicationRemovalMissPatch.managerBody(a,CasCommunicationRemovalMissPatch.MANAGER_PROBE,true);for(var i:b.getCode().code)if(i.definition.instructionCode==0x66&&CasStructuralRolesPatch.name(a,i.operands[0])==null){i.operands[0]=a.constants.getPublicQnameId("UsingControllerToggled",true);break;}}
            if(mode.equals("owned-manager-missing-probe")){b=CasCommunicationRemovalMissPatch.managerBody(a,CasCommunicationRemovalMissPatch.MANAGER_PROBE,true);for(var i:b.getCode().code)if(i.definition.instructionCode==0xb4){i.definition=CasStructuralRolesPatch.ins(0x29).definition;break;}}
            if(mode.equals("owned-manager-reason")){b=CasCommunicationRemovalMissPatch.managerBody(a,CasCommunicationRemovalMissPatch.MANAGER_PROBE,true);for(var i:b.getCode().code)if(i.definition.instructionCode==0x2c&&"ready".equals(a.constants.getString(i.operands[0]))){i.operands[0]=a.constants.getStringId("wrong-reason",true);break;}}
            if(mode.equals("owned-manager-scope")){b=CasCommunicationRemovalMissPatch.managerBody(a,CasCommunicationRemovalMissPatch.MANAGER_PROBE,true);b.init_scope_depth++;}
            if(b!=null){b.setCode(b.getCode());b.setModified();}boolean refused=false;
            try{CasCommunicationRemovalMissPatch.verify(base,a,change);}catch(Exception expected){refused=true;}
            if(!refused)throw new IllegalArgumentException("Accepted "+mode);System.out.println("PASS "+mode);
        }
    }
}
