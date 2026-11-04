import java.util.*;
import com.jpexs.decompiler.flash.abc.ABC;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;

public class CasCompilerArgumentProvenanceFixtures {
 static void check(boolean value,String message){if(!value)throw new IllegalArgumentException(message);}
 static AVM2Instruction op(int code,int... args){return new AVM2Instruction(0,code,args);}
 static MethodBody copy(MethodBody original){var b=original.clone();var rows=new ArrayList<AVM2Instruction>();for(var i:original.getCode().code)rows.add(new AVM2Instruction(i.getAddress(),i.definition.instructionCode,i.operands==null?null:i.operands.clone()));set(b,rows);return b;}
 static void set(MethodBody b,List<AVM2Instruction> rows){long address=0;for(var i:rows){i.setAddress(address);address+=i.getBytesLength();}var c=b.getCode();c.code.clear();c.code.addAll(rows);b.setCode(c);b.setModified();}
 static int setter(ABC a,MethodBody b){for(int i=0;i<b.getCode().code.size();i++)if(CasBytecodePatch.stringLiteral(a,b.getCode().code.get(i),"SetSimOccult"))return i;throw new IllegalArgumentException("Setter fixture missing");}
 public static void main(String[] args)throws Exception {
  java.util.logging.Logger.getLogger("").setLevel(java.util.logging.Level.OFF);
  var a=CasBytecodePatch.load(args[0]);var inst=a.instance_info.get(a.findClassByName("widgets.CAS.Customizer.CASCustomizerMain"));
  var original=CasBytecodePatch.ownedBody(a,inst,"ApexControlExecute");
  CasBytecodePatch.verifyTypedControls(a,inst);System.out.println("PASS actual-typed-control-inventory");
  int start=setter(a,original)+1;check(CasBytecodePatch.typedIndexReadEnd(a,original,start)==start+2,"Actual formal activation read differs");System.out.println("PASS actual-formal-index-capture");
  int slot=CasBytecodePatch.gridBudgetSlot(a,original,"index","int");int store=-1;
  for(int i=0;i<original.getCode().code.size();i++)if(CasBytecodePatch.gridBudgetOp(original.getCode().code.get(i),0x6d,slot))store=i;
  check(store>=2&&!CasBytecodePatch.bootstrapReachable(original,start,store),"Actual captured formal did not dominate setter");
  for(String mode:List.of("wrong-read-scope","wrong-read-slot","wrong-formal-register","wrong-store-scope","missing-store","duplicate-store","bypass-capture")) {
   var b=copy(original);var rows=new ArrayList<>(b.getCode().code);int read=setter(a,b)+1;
   switch(mode){
    case "wrong-read-scope":rows.get(read).operands[0]=0;break;
    case "wrong-read-slot":rows.get(read+1).operands[0]=3;break;
    case "wrong-formal-register":rows.get(store-1).operands[0]=5;break;
    case "wrong-store-scope":rows.get(store-2).operands[0]=0;break;
    case "missing-store":rows.get(store).operands[0]=3;break;
    case "duplicate-store":rows.add(rows.size()-1,op(0x6d,slot));break;
    case "bypass-capture":{var target=rows.get(read);var jump=op(0x10,0);rows.set(0,jump);b.exceptions=new ABCException[0];set(b,rows);jump.operands[0]=(int)(target.getAddress()-jump.getAddress()-jump.getBytesLength());break;}
   }
   set(b,rows);boolean failed=false;try{CasBytecodePatch.typedIndexReadEnd(a,b,read);}catch(IllegalArgumentException expected){failed=true;}check(failed,"Invalid captured formal accepted: "+mode);System.out.println("PASS "+mode);
  }
  // Historical direct argument-four loading remains independently supported.
  var direct=copy(original);set(direct,new ArrayList<>(List.of(op(0x62,4),op(0x47))));direct.exceptions=new ABCException[0];check(CasBytecodePatch.typedIndexReadEnd(a,direct,0)==1,"Historical formal register refused");System.out.println("PASS historical-direct-formal");
  var nativeBody=CasBytecodePatch.ownedBody(a,inst,"ApexAcceptNative");CasBytecodePatch.verifyBoundedNativeRefusal(a,nativeBody);System.out.println("PASS actual-bounded-native-refusal");
  for(String mode:List.of("wrong-prefix","oversized-bound","wrong-substring","wrong-prefix-arity","wrong-substring-arity","inverted-bound","inverted-branch","wrong-jump","nonthrowing-refusal")) {
   var b=copy(nativeBody);var rows=new ArrayList<>(b.getCode().code);int p=CasBytecodePatch.uniqueLiteral(a,b,"REFUSED|");
   switch(mode){
    case "wrong-prefix":rows.get(p).operands[0]=a.constants.getStringId("APEXACCEPT1|",false);break;
    case "oversized-bound":rows.get(p+10).operands[0]=1025;break;
    case "wrong-substring":rows.get(p+17).operands[0]=7;break;
    case "wrong-prefix-arity":rows.get(p+1).operands[1]=0;break;
    case "wrong-substring-arity":rows.get(p+18).operands[1]=2;break;
    case "inverted-bound":rows.set(p+11,op(0xb0));break;
    case "inverted-branch":rows.set(p+12,op(0x11,rows.get(p+12).operands[0]));break;
    case "wrong-jump":rows.get(p+5).operands[0]++;break;
    case "nonthrowing-refusal":rows.set(p+21,op(0x29));break;
   }
   set(b,rows);boolean failed=false;try{CasBytecodePatch.verifyBoundedNativeRefusal(a,b);}catch(IllegalArgumentException expected){failed=true;}check(failed,"Invalid bounded refusal accepted: "+mode);System.out.println("PASS "+mode);
  }
 }
}
