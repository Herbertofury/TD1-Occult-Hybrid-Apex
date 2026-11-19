// Adversarial execution of the actual serialized postpass proof. No game input.
import java.nio.file.*;import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;
import com.jpexs.helpers.MemoryInputStream;
public class CasCommunicationIndexBytecodeFixtures {
 static void check(boolean b,String s){CasCommunicationIndexPatch.check(b,s);}
 static int op(AVM2Instruction i){return i.definition.instructionCode;}
 static ABC parse(ABC base,byte[] bytes)throws Exception{return new ABC(new ABCInputStream(new MemoryInputStream(bytes)),base.getSwf(),null);}
 static void fail(Runnable task,String why){boolean refused=false;try{task.run();}catch(Exception expected){refused=true;}check(refused,"Accepted "+why);}
 public static void main(String[]args)throws Exception{
  var original=CasStructuralRolesPatch.load(args[0]);var base=CasStructuralRolesPatch.load(args[1]);var compiler=CasStructuralRolesPatch.load(args[2]);
  byte[] bytes=Files.readAllBytes(Path.of(args[3]));var good=parse(base,bytes);
  CasCommunicationIndexPatch.sourceAuthority(original,base);CasCommunicationIndexPatch.helpers(compiler);CasCommunicationIndexPatch.helpers(good);
  var rewrites=new HashMap<Integer,CasStructuralRolesPatch.Rewrite>();
  for(String n:CasCommunicationIndexPatch.CHANGED){var b=CasCommunicationIndexPatch.body(base,n);rewrites.put(b.method_info,CasCommunicationIndexPatch.rewrite(good,b,n));}
  var hashes=new HashMap<Integer,String>();for(var b:good.bodies)if(b.method_info>=base.method_info.size()||rewrites.containsKey(b.method_info))hashes.put(b.method_info,CasStructuralRolesPatch.sha(b.getCodeBytes()));
  CasCommunicationIndexPatch.verify(base,good,rewrites,hashes);System.out.println("PASS serialized-valid");
  for(String mode:List.of("probe-equality","dictionary-weak","alias-reason","counter-body","fallback-call","scope-local","original-dispatch","original-constructor","missing-alias-prefix","mutation-hook","fallback-edge","foreign-field")){
   var a=parse(base,bytes);MethodBody changed=null;
   if(mode.equals("probe-equality")){changed=CasCommunicationIndexPatch.body(a,"ApexCommIndexedHas");boolean found=false;
    for(var i:changed.getCode().code)if(op(i)==0xac){i.definition=new AVM2Instruction(0,0xab,new int[0]).definition;found=true;break;}check(found,"Strict equality probe required");}
   if(mode.equals("dictionary-weak")){changed=CasCommunicationIndexPatch.body(a,"ApexCommIndexedHas");boolean found=false;var code=changed.getCode().code;
    for(int k=0;k+1<code.size();k++)if(op(code.get(k))==0x26&&op(code.get(k+1))==0x4a){code.get(k).definition=new AVM2Instruction(0,0x27,new int[0]).definition;found=true;break;}check(found,"Actual Dictionary constructor required");}
   if(mode.equals("alias-reason")){changed=CasCommunicationIndexPatch.body(a,"ApexCommExpose");boolean found=false;
    for(var i:changed.getCode().code)if(op(i)==0x2c){i.operands[0]=a.constants.getStringId("error",true);found=true;break;}check(found,"Alias fallback reason required");}
   if(mode.equals("counter-body")){changed=CasCommunicationIndexPatch.body(a,"ApexCommIndexStats");changed.getCode().code.get(2).definition=new AVM2Instruction(0,0x20,new int[0]).definition;}
   if(mode.equals("fallback-call")){changed=CasCommunicationIndexPatch.body(a,"ApexCommIndexedHas");boolean found=false;
    for(var i:changed.getCode().code)if(CasCommunicationIndexPatch.prop(a,i,0x46,"HasFunction")){i.operands[0]=CasCommunicationIndexPatch.method(a,"ApexCommCanIndex").name_index;found=true;break;}check(found,"Native fallback required");}
   if(mode.equals("scope-local")){changed=CasCommunicationIndexPatch.body(a,"ApexCommIndexedHas");boolean found=false;
    for(var i:changed.getCode().code)if(op(i)==0x65){i.operands[0]++;found=true;break;}check(found,"Actual activation scope required");}
   if(mode.equals("original-dispatch")){changed=CasCommunicationIndexPatch.body(a,"Dispatch");changed.getCode().code.get(2).definition=new AVM2Instruction(0,0x26,new int[0]).definition;}
   if(mode.equals("original-constructor")){changed=a.findBody(a.instance_info.get(a.findClassByName(CasCommunicationIndexPatch.TYPE)).iinit_index);changed.getCode().code.get(2).definition=new AVM2Instruction(0,0x26,new int[0]).definition;}
   if(mode.equals("missing-alias-prefix")){changed=CasCommunicationIndexPatch.body(a,"GetFunctions");changed.getCode().code.get(3).operands[0]=CasCommunicationIndexPatch.method(a,"ApexCommDisable").name_index;}
   if(mode.equals("mutation-hook")){changed=CasCommunicationIndexPatch.body(a,"AddFunction");boolean found=false;
    for(var i:changed.getCode().code)if(CasCommunicationIndexPatch.prop(a,i,0x4f,"ApexCommAdded")){i.operands[0]=CasCommunicationIndexPatch.method(a,"ApexCommRemoved").name_index;found=true;break;}check(found,"Committed native push hook required");}
   if(mode.equals("fallback-edge")){changed=CasCommunicationIndexPatch.body(a,"HasFunction");boolean found=false;
    for(var i:changed.getCode().code)if(op(i)==0x12){i.operands[0]++;found=true;break;}check(found,"Native fallback edge required");}
   if(mode.equals("foreign-field")){changed=CasCommunicationIndexPatch.body(a,"ApexCommIndexedHas");boolean found=false;
    for(var i:changed.getCode().code)if(CasCommunicationIndexPatch.prop(a,i,0x60,"apexCommIndex")){i.operands[0]=a.constants.getPublicQnameId("apexCommIndex",true);found=true;break;}check(found,"Private index binding required");}
   check(changed!=null,"Fixture did not modify a real body");changed.setModified();boolean refused=false;
   try{CasCommunicationIndexPatch.verify(base,a,rewrites,hashes);}catch(Exception expected){refused=true;}
   check(refused,"Serialized verifier accepted "+mode);System.out.println("PASS "+mode);
  }
  // Before the producer computes hashes, a changed compiled helper must still
  // fail the independently pinned semantic/helper source authority gate.
  var damaged=CasStructuralRolesPatch.reparse(compiler);var h=CasCommunicationIndexPatch.body(damaged,"ApexCommCanIndex");h.getCode().code.get(3).definition=new AVM2Instruction(0,0x20,new int[0]).definition;h.setModified();
  boolean refused=false;try{CasCommunicationIndexPatch.helpers(damaged);}catch(Exception expected){refused=true;}check(refused,"Changed compiler helper escaped semantic pins");System.out.println("PASS compiler-semantic-pin");
 }
}
