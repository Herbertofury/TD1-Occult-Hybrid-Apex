import java.util.*;
import com.jpexs.decompiler.flash.abc.ABC;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;
public class CasNavigationTimerBytecodeFixtures {
    static void replace(AVM2Instruction op,int opcode){op.definition=new AVM2Instruction(0,opcode,new int[0]).definition;}
    static int firstCall(ABC abc,MethodBody body,String name){
        for(int n=0;n<body.getCode().code.size();n++)if(CasBytecodePatch.property(abc,body.getCode().code.get(n),0x4f,name)||
            CasBytecodePatch.property(abc,body.getCode().code.get(n),0x46,name))return n;
        throw new IllegalArgumentException("Fixture call missing: "+name);
    }
    public static void main(String[] args)throws Exception {
        java.util.logging.Logger.getLogger("com.jpexs").setLevel(java.util.logging.Level.OFF);
        var abc=CasBytecodePatch.load(args[0]);String mode=args[1];
        var owner=abc.instance_info.get(abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain"));
        var step=CasBytecodePatch.ownedBody(abc,owner,"ApexCatalogTimerStep");
        var nav=CasBytecodePatch.ownedBody(abc,owner,"ApexPanelNavigationSnapshot");
        var read=CasBytecodePatch.ownedBody(abc,owner,"ApexReadback");
        var complete=CasBytecodePatch.ownedBody(abc,owner,"ApexComplete");
        int service=CasBytecodePatch.communicationBinding(abc)[1];
        if(mode.equals("timer-service"))step.getCode().code.get(firstCall(abc,step,"push")).operands[0]=service;
        if(mode.equals("timer-scope"))step.init_scope_depth++;
        if(mode.equals("timer-disabled"))replace(complete.getCode().code.get(firstCall(abc,complete,"ApexCatalogTimerStep")-13),0x27);
        if(mode.equals("timer-branch"))complete.getCode().code.get(firstCall(abc,complete,"ApexCatalogTimerStep")-3).operands[0]++;
        if(mode.equals("timer-event"))complete.getCode().code.get(firstCall(abc,complete,"ApexCatalogTimerStep")-1).operands[0]=abc.constants.getStringId("foreign.enter",true);
        if(mode.equals("timer-status-service")){
            var status=CasBytecodePatch.ownedBody(abc,owner,"ApexCatalogTimerStatus");status.getCode().code.get(firstCall(abc,status,"push")).operands[0]=service;
        }
        if(mode.equals("timer-callback")){
            var callback=CasBytecodePatch.ownedBody(abc,owner,"ApexSocketConnect");
            callback.getCode().code.get(firstCall(abc,callback,"split")).operands[0]=
                complete.getCode().code.get(firstCall(abc,complete,"ApexCatalogTimerStep")).operands[0];
        }
        if(mode.equals("nav-scope"))nav.getCode().code.get(CasBytecodePatch.uniqueLiteral(abc,nav,"native-cas-navigation-client")).operands[0]=abc.constants.getStringId("native-cas-client",true);
        if(mode.equals("nav-service"))nav.getCode().code.get(firstCall(abc,nav,"isFinite")).operands[0]=service;
        if(mode.equals("nav-identity"))replace(nav.getCode().code.get(CasBytecodePatch.uniqueLiteral(abc,nav,"Panel navigation changed its bound native Sim/form/outfit context")-4),0xab);
        if(mode.equals("nav-fallback"))for(int n=0;n+2<read.getCode().code.size();n++)if(CasBytecodePatch.stringLiteral(abc,read.getCode().code.get(n),"panel-navigation") &&
            CasBytecodePatch.opcode(read.getCode().code.get(n+1),0xab) && CasBytecodePatch.opcode(read.getCode().code.get(n+2),0x96)) {
                read.getCode().code.get(n).operands[0]=abc.constants.getStringId("foreign-navigation",true);break;
            }
        if(mode.equals("accept-foreign-wire")){
            var accept=CasBytecodePatch.ownedBody(abc,owner,"ApexAccept");var code=accept.getCode().code;
            boolean changed=false;
            for(int n=1;n<code.size();n++)if(CasBytecodePatch.opcode(code.get(n),0x24) && code.get(n).operands[0]==6 &&
                CasBytecodePatch.property(abc,code.get(n-1),0x60,"apexPendingFields")){
                for(var op:nav.getCode().code)if(CasBytecodePatch.property(abc,op,0x60,"apexCardLayout")){code.get(n-1).operands[0]=op.operands[0];changed=true;break;}
                break;
            }
            CasBytecodePatch.require(changed,"Actual household wire receiver required for fixture.");
        }
        boolean refused=false;
        try{
            CasBytecodePatch.verifyTimerPipeline(abc,owner);
            CasBytecodePatch.verifyDrawTraceHelper(abc,owner);
            CasBytecodePatch.verifyTimerTraceHelper(abc,owner);
            CasBytecodePatch.verifyPanelNavigation(abc,owner);
            CasBytecodePatch.verifyAcceptHouseholdBinding(abc,owner);
        }catch(IllegalArgumentException expected){refused=true;}
        CasBytecodePatch.require(refused!=mode.equals("valid"),"Diagnostic/navigation gate misclassified "+mode);
        System.out.println("PASS "+mode);
    }
}
