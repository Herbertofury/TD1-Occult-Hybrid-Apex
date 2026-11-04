import java.util.*;
import java.util.function.*;
import com.jpexs.decompiler.flash.abc.ABC;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;
public class AcceptReadinessBytecodeTests {
 static String source;static int passed=0;
 static int literal(ABC abc,String text){for(int i=1;i<abc.constants.getStringCount();i++)if(text.equals(abc.constants.getString(i)))return i;throw new AssertionError(text);}
 static int member(ABC abc,String text){for(int i=1;i<abc.constants.getMultinameCount();i++)if(text.equals(abc.constants.getString(abc.constants.getMultiname(i).name_index)))return i;throw new AssertionError(text);}
 static void bad(String label,String method,Consumer<List<AVM2Instruction>> change)throws Exception {
  var abc=CasBytecodePatch.load(source);var instance=abc.instance_info.get(abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain"));
  current=abc;var body=CasBytecodePatch.ownedBody(abc,instance,method);change.accept(body.getCode().code);
  boolean refused=false;try{CasBytecodePatch.verifyAcceptReadiness(abc,instance);}catch(IllegalArgumentException expected){refused=true;}
  if(!refused)throw new AssertionError("Accepted corrupt compiled boundary: "+label);++passed;
 }
 static ABC current;
 static int call(List<AVM2Instruction> c,String name){for(int i=0;i<c.size();i++)if(CasBytecodePatch.acceptCall(current,c.get(i),name))return i;throw new AssertionError(name);}
 static int lit(List<AVM2Instruction> c,String name){for(int i=0;i<c.size();i++)if(CasBytecodePatch.stringLiteral(current,c.get(i),name))return i;throw new AssertionError(name);}
 static void opcode(List<AVM2Instruction> c,int at,int code){var prior=c.get(at);c.set(at,new AVM2Instruction(prior.getAddress(),code,prior.operands==null?null:prior.operands.clone()));}
 public static void main(String[] args)throws Exception {
  source=args[0];var abc=CasBytecodePatch.load(source);var instance=abc.instance_info.get(abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain"));CasBytecodePatch.verifyAcceptReadiness(abc,instance);
  bad("not-ready branch inversion","ApexAccept",c->opcode(c,call(c,"ApexAcceptReady")+2,0x11));
  bad("not-ready return removal","ApexAccept",c->opcode(c,call(c,"ApexAcceptReady")+3,0x02));
  bad("PREPARE replaced with READY","ApexAccept",c->c.get(call(c,"ApexAcceptNative")-1).operands[0]=literal(current,"READY"));
  bad("UUID replaced with nonce slot","ApexAccept",c->c.get(lit(c,"apex_accept_id")+2).operands[0]=c.get(lit(c,"apex_accept_nonce")+2).operands[0]);
  bad("nonce replaced with UUID slot","ApexAccept",c->c.get(lit(c,"apex_accept_nonce")+2).operands[0]=c.get(lit(c,"apex_accept_id")+2).operands[0]);
  bad("retained owner replaced","ApexAccept",c->{for(int i=0;i+1<c.size();i++)if(CasBytecodePatch.property(current,c.get(i),0x60,"apexAcceptWait")&&CasBytecodePatch.property(current,c.get(i+1),0x66,"owner")){c.get(i+1).operands[0]=member(current,"id");return;}throw new AssertionError();});
  bad("phase9 replaced with phase7","ApexAccept",c->{for(int i=1;i<c.size();i++)if(CasBytecodePatch.property(current,c.get(i),0x61,"apexPendingPhase")&&c.get(i-1).definition.instructionCode==0x24&&c.get(i-1).operands[0]==9){c.get(i-1).operands[0]=7;return;}throw new AssertionError();});
  bad("consume replaced with Boolean","ApexAccept",c->{int from=call(c,"ApexAcceptReady"),to=lit(c,"SaveAndExitCAS");for(int i=from;i<to;i++)if(CasBytecodePatch.property(current,c.get(i),0x61,"apexAcceptWait")){opcode(c,i-1,0x27);return;}throw new AssertionError();});
  bad("receipt arity18 replaced17","ApexAcceptNative",c->{for(int i=1;i<c.size();i++)if(CasBytecodePatch.property(current,c.get(i-1),0x66,"length")&&c.get(i).definition.instructionCode==0x24){c.get(i).operands[0]=17;return;}throw new AssertionError();});
  bad("receipt stamp inversion","ApexAcceptNative",c->{for(int i=0;i+1<c.size();i++)if(CasBytecodePatch.property(current,c.get(i),0x66,"stamp")){opcode(c,i+1,0x1a);return;}throw new AssertionError();});
  for(int index:new int[]{15,16})bad("genuine phase/model predicate changed "+index,"ApexAcceptNative",c->{for(int i=0;i+3<c.size();i++)if(c.get(i).definition.instructionCode==0x24&&c.get(i).operands[0]==index&&c.get(i+1).definition.instructionCode==0x66&&CasBytecodePatch.stringLiteral(current,c.get(i+2),"0")&&c.get(i+3).definition.instructionCode==0xac){c.get(i+2).operands[0]=literal(current,"1");return;}throw new AssertionError();});
  bad("READY Boolean equivalence inverted","ApexAcceptNative",c->{for(int i=0;i+3<c.size();i++)if(CasBytecodePatch.stringLiteral(current,c.get(i),"READY")&&c.get(i+1).definition.instructionCode==0xac&&c.get(i+3).definition.instructionCode==0x19){opcode(c,i+3,0x1a);return;}throw new AssertionError();});
  bad("timeout bound changed","ApexAcceptReady",c->{for(var o:c)if(o.definition.instructionCode==0x25&&o.operands[0]==10000){o.operands[0]=10001;return;}throw new AssertionError();});
  bad("input cancellation removed","ApexAcceptReady",c->{for(var o:c)if(CasBytecodePatch.property(current,o,0x60,"apexAcceptInput")){o.operands[0]=member(current,"apexDisconnected");return;}throw new AssertionError();});
  bad("nonce strict comparison weakened","ApexAcceptReady",c->{for(int i=0;i+3<c.size();i++)if(CasBytecodePatch.property(current,c.get(i),0x60,"apexNonce")){opcode(c,i+3,0xab);return;}throw new AssertionError();});
  bad("stage identity removed","ApexAcceptReady",c->{for(var o:c)if(CasBytecodePatch.property(current,o,0x66,"stage")){o.operands[0]=member(current,"id");return;}throw new AssertionError();});
  bad("fresh editor mode read removed","ApexAcceptReady",c->c.get(lit(c,"CasGetCASEditMode")).operands[0]=literal(current,"GetSimOccult"));
  bad("input callback native call added","ApexAcceptUserInput",c->c.add(1,new AVM2Instruction(0,0x4f,new int[]{member(current,"CallGameService"),0})));
  bad("frame dispatches another operation","ApexAcceptReadyFrame",c->c.get(call(c,"ApexAccept")).operands[0]=member(current,"ApexReadback"));
  bad("abort loses listener removal","ApexAcceptAbort",c->c.get(call(c,"ApexAcceptListen")).operands[0]=member(current,"ApexAcceptUserInput"));
  bad("room retirement loses cancellation","ApexResetSocket",c->c.get(call(c,"ApexAcceptAbort")).operands[0]=member(current,"ApexDisconnect"));
  System.out.println("{\"compiled_boundary_mutations_refused\":"+passed+",\"valid_compiled_accepted\":true}");
 }
}
