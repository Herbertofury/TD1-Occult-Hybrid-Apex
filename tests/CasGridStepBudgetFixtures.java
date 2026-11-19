import java.util.*;
import com.jpexs.decompiler.flash.abc.ABC;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;

public class CasGridStepBudgetFixtures {
 static void check(boolean value,String message){if(!value)throw new IllegalArgumentException(message);}
 static AVM2Instruction op(int code,int... args){return new AVM2Instruction(0,code,args);}
 static MethodBody copy(MethodBody original){var b=original.clone();var code=b.getCode();var rows=new ArrayList<AVM2Instruction>();for(var i:original.getCode().code)rows.add(new AVM2Instruction(i.getAddress(),i.definition.instructionCode,i.operands==null?null:i.operands.clone()));code.code.clear();code.code.addAll(rows);b.setCode(code);return b;}
 static void set(MethodBody b,List<AVM2Instruction> rows){long address=0;for(var i:rows){i.setAddress(address);address+=i.getBytesLength();}var code=b.getCode();code.code.clear();code.code.addAll(rows);b.setCode(code);b.setModified();}
 static int step(ABC a,MethodBody b){for(int i=0;i<b.getCode().code.size();i++)if(CasBytecodePatch.property(a,b.getCode().code.get(i),0x46,"ApexGridStep"))return i;throw new IllegalArgumentException("Fixture Step absent");}
 static MethodBody suffix(ABC a,MethodBody original,boolean plain){
  int i=step(a,original);var old=original.getCode().code;var rows=new ArrayList<AVM2Instruction>();
  for(int n=i-15;n<i-12;n++)rows.add(new AVM2Instruction(0,old.get(n).definition.instructionCode,old.get(n).operands.clone()));
  if(plain){for(int n:new int[]{i-12,i-10,i-9,i-2,i-1,i})rows.add(new AVM2Instruction(0,old.get(n).definition.instructionCode,old.get(n).operands==null?null:old.get(n).operands.clone()));}
  else for(int n=i-12;n<=i;n++)rows.add(new AVM2Instruction(0,old.get(n).definition.instructionCode,old.get(n).operands==null?null:old.get(n).operands.clone()));
  rows.add(op(0x29));rows.add(op(0x47));var made=original.clone();made.exceptions=new ABCException[0];set(made,rows);return made;
 }
 static void refused(ABC a,MethodBody body,String name){boolean failed=false;try{CasBytecodePatch.verifyGridStepBudget(a,body);}catch(IllegalArgumentException expected){failed=true;}check(failed,"Invalid budget accepted: "+name);System.out.println("PASS "+name);}
 public static void main(String[] args)throws Exception {
  java.util.logging.Logger.getLogger("").setLevel(java.util.logging.Level.OFF);
  var a=CasBytecodePatch.load(args[0]);var instance=a.instance_info.get(a.findClassByName("widgets.CAS.Customizer.CASCustomizerMain"));var original=CasBytecodePatch.ownedBody(a,instance,"ApexCatalogGridFrame");
  CasBytecodePatch.verifyGridStepBudget(a,original);System.out.println("PASS actual-compiled-timed");
  CasBytecodePatch.verifyGridController(a,instance);System.out.println("PASS actual-full-controller");
  var timed=suffix(a,original,false);var plain=suffix(a,original,true);
  CasBytecodePatch.verifyGridStepBudget(a,timed);System.out.println("PASS timed-suffix");
  CasBytecodePatch.verifyGridStepBudget(a,plain);System.out.println("PASS historical-plain-suffix");
  for(String mode:List.of("operations63","clock-arity","wrong-clock-target","wrong-clock-lookup","wrong-store","wrong-scope","wrong-local","wrong-load","wrong-kill","deadline2","subtract","step3","void-step","wrong-step-target","wrong-grid","decoy64","duplicate-step","branch-into-deadline")) {
   var b=copy(timed);var rows=new ArrayList<>(b.getCode().code);int i=step(a,b);
   switch(mode){
    case "operations63":rows.get(i-12).operands[0]=63;break;
    case "clock-arity":rows.get(i-9).operands[1]=1;break;
    case "wrong-clock-target":rows.get(i-9).operands[0]=rows.get(i).operands[0];break;
    case "wrong-clock-lookup":rows.get(i-10).operands[0]=rows.get(i).operands[0];break;
    case "wrong-store":rows.get(i-5).operands[0]=CasBytecodePatch.gridBudgetSlot(a,b,"started","int");break;
    case "wrong-scope":rows.get(i-11).operands[0]=0;break;
    case "wrong-local":rows.set(i-6,op(0xd6));break;
    case "wrong-load":rows.set(i-4,op(0xd2));break;
    case "wrong-kill":rows.get(i-3).operands[0]=2;break;
    case "deadline2":rows.get(i-2).operands[0]=2;break;
    case "subtract":rows.set(i-1,op(0xa1));break;
    case "step3":rows.get(i).operands[1]=3;break;
    case "void-step":rows.set(i,op(0x4f,rows.get(i).operands[0],2));break;
    case "wrong-step-target":rows.get(i).operands[0]=rows.get(i-9).operands[0];break;
    case "wrong-grid":rows.get(i-14).operands[0]=CasBytecodePatch.gridBudgetSlot(a,b,"retained","Object");break;
    case "decoy64":rows.get(i-12).operands[0]=63;rows.add(0,op(0x24,64));rows.add(1,op(0x29));break;
    case "duplicate-step":rows.add(rows.size()-1,op(0x46,rows.get(i).operands[0],2));break;
    case "branch-into-deadline":{var target=rows.get(i-2);var jump=op(0x10,0);rows.add(0,jump);set(b,rows);jump.operands[0]=(int)(target.getAddress()-jump.getAddress()-jump.getBytesLength());break;}
   }
   set(b,rows);refused(a,b,mode);
  }
  for(String mode:List.of("plain63","plain-clock-arity","plain2","plain-subtract")) {
   var b=copy(plain);var rows=new ArrayList<>(b.getCode().code);int i=step(a,b);
   if(mode.equals("plain63"))rows.get(i-5).operands[0]=63;
   else if(mode.equals("plain-clock-arity"))rows.get(i-3).operands[1]=1;
   else if(mode.equals("plain2"))rows.get(i-2).operands[0]=2;
   else rows.set(i-1,op(0xa1));set(b,rows);refused(a,b,mode);
  }
 }
}
