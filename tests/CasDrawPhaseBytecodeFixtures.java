import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
public class CasDrawPhaseBytecodeFixtures {
 interface Mutation {void run(ABC a)throws Exception;}
 static void verify(ABC before,ABC after)throws Exception {
  var plan=CasDrawPhasePatch.rewrite(after,CasDrawPhasePatch.body(before,CasDrawPhasePatch.CELL,"Draw"));CasDrawPhasePatch.verify(before,after,plan);
 }
 static void reject(ABC before,ABC after,String name,Mutation change)throws Exception {
  var a=CasStructuralRolesPatch.reparse(after);change.run(a);a=CasStructuralRolesPatch.reparse(a);boolean failed=false;
  try{verify(before,a);}catch(IllegalArgumentException expected){failed=true;}
  CasDrawPhasePatch.check(failed,"Unreviewed granular change accepted: "+name);System.out.println("PASS "+name);
 }
 // Execute the actual AVM2 timer call operands against a PackageNamespace-only
 // scope. There intentionally is no global object named "flash". A flat JS
 // facade with flash.utils.getTimer would incorrectly allow the broken stub.
 static void exerciseNativeTimerBinding(ABC a,String method)throws Exception {
  var b=CasDrawPhasePatch.body(a,CasDrawPhasePatch.MAIN,method);CasDrawPhasePatch.timerBinding(a,b);
  Map<String,java.util.function.IntSupplier> packageScope=Map.of("7:getTimer:22:flash.utils",()->731);
  String receiver=null;int calls=0,result=-1;
  for(var i:b.getCode().code){if(i.operands==null||i.operands.length==0||!Set.of(0x5d,0x46).contains(CasDrawPhasePatch.op(i))||!"getTimer".equals(CasDrawPhasePatch.name(a,i.operands[0])))continue;
   String q=CasCommunicationIndexPatch.qname(a,i.operands[0]);
   if(CasDrawPhasePatch.op(i)==0x5d){CasDrawPhasePatch.check(packageScope.containsKey(q),"Native findpropstrict cannot resolve timer package");receiver=q;}
   else {CasDrawPhasePatch.check(q.equals(receiver)&&i.operands[1]==0,"Native callproperty timer receiver differs");result=packageScope.get(q).getAsInt();calls++;}}
  CasDrawPhasePatch.check(calls==1&&result==731,"Native PackageNamespace timer did not execute exactly once");
 }
 public static void main(String[] args)throws Exception {
  var before=CasStructuralRolesPatch.load(args[0]);var after=CasStructuralRolesPatch.load(args[1]);verify(before,after);System.out.println("PASS serialized profile-only native CFG projection");
  for(String n:CasDrawPhasePatch.OWNED)exerciseNativeTimerBinding(after,n);System.out.println("PASS native PackageNamespace timer operands execute without global flash object");
  var wrongNamespace=CasStructuralRolesPatch.reparse(after);
  var timer=CasDrawPhasePatch.body(wrongNamespace,CasDrawPhasePatch.MAIN,"ApexCatalogTraceConfigure").getCode().code.stream().filter(i->CasDrawPhasePatch.op(i)==0x5d&&"getTimer".equals(CasDrawPhasePatch.name(wrongNamespace,i.operands[0]))).findFirst().orElseThrow();
  var q=wrongNamespace.constants.getMultiname(timer.operands[0]);int empty=0;for(int n=1;n<wrongNamespace.constants.getNamespaceCount();n++){var ns=wrongNamespace.constants.getNamespace(n);if(ns.kind==22&&wrongNamespace.constants.getString(ns.name_index).equals("")){empty=n;break;}}
  CasDrawPhasePatch.check(empty>0,"Default PackageNamespace fixture absent");q.namespace_index=empty;boolean namespaceRejected=false;try{CasDrawPhasePatch.timerBinding(wrongNamespace,CasDrawPhasePatch.body(wrongNamespace,CasDrawPhasePatch.MAIN,"ApexCatalogTraceConfigure"));}catch(IllegalArgumentException expected){namespaceRejected=true;}
  CasDrawPhasePatch.check(namespaceRejected,"Wrong timer namespace accepted without relying on semantic hash");System.out.println("PASS timer namespace corruption independently rejected");
  var offset=CasStructuralRolesPatch.reparse(after);var shifted=CasDrawPhasePatch.body(offset,CasDrawPhasePatch.MAIN,"ApexCatalogTraceConfigure").clone();for(var i:shifted.getCode().code)if(CasDrawPhasePatch.op(i)==0xef&&i.operands[0]==1&&i.operands[3]>0)i.operands[3]+=37;shifted.setCode(shifted.getCode());shifted.setModified();CasStructuralRolesPatch.replace(offset,shifted);verify(before,CasStructuralRolesPatch.reparse(offset));System.out.println("PASS common owned debug source offset preserves semantics and native rollback");
  reject(before,after,"relative owned debug line gap",a->{var b=CasDrawPhasePatch.body(a,CasDrawPhasePatch.MAIN,"ApexCatalogTraceConfigure").clone();for(var i:b.getCode().code)if(CasDrawPhasePatch.op(i)==0xef&&i.operands[0]==1&&"phases".equals(a.constants.getString(i.operands[1]))){i.operands[3]++;break;}b.setCode(b.getCode());b.setModified();CasStructuralRolesPatch.replace(a,b);});
  reject(before,after,"owned debug register identity",a->{var b=CasDrawPhasePatch.body(a,CasDrawPhasePatch.MAIN,"ApexCatalogTraceConfigure").clone();for(var i:b.getCode().code)if(CasDrawPhasePatch.op(i)==0xef&&i.operands[3]>0){i.operands[2]++;break;}b.setCode(b.getCode());b.setModified();CasStructuralRolesPatch.replace(a,b);});
  reject(before,after,"zero owned debug extra remains exact",a->{var b=CasDrawPhasePatch.body(a,CasDrawPhasePatch.MAIN,"ApexCatalogTraceConfigure").clone();for(var i:b.getCode().code)if(CasDrawPhasePatch.op(i)==0xef&&i.operands[3]==0){i.operands[3]=1;break;}b.setCode(b.getCode());b.setModified();CasStructuralRolesPatch.replace(a,b);});
  reject(before,after,"native fast tail operand",a->{var b=CasDrawPhasePatch.body(a,CasDrawPhasePatch.CELL,"Draw").clone();b.getCode().code.get(7).definition=b.getCode().code.get(0).definition;b.setCode(b.getCode());b.setModified();CasStructuralRolesPatch.replace(a,b);});
  reject(before,after,"native Draw extra local",a->{var b=CasDrawPhasePatch.body(a,CasDrawPhasePatch.CELL,"Draw").clone();b.max_regs++;CasStructuralRolesPatch.replace(a,b);});
  reject(before,after,"native Draw stack metadata",a->{var b=CasDrawPhasePatch.body(a,CasDrawPhasePatch.CELL,"Draw").clone();b.max_stack++;CasStructuralRolesPatch.replace(a,b);});
  reject(before,after,"native Draw scope metadata",a->{var b=CasDrawPhasePatch.body(a,CasDrawPhasePatch.CELL,"Draw").clone();b.init_scope_depth++;b.max_scope_depth++;CasStructuralRolesPatch.replace(a,b);});
  reject(before,after,"profiled gotoAndStop target ABI",a->{var b=CasDrawPhasePatch.body(a,CasDrawPhasePatch.CELL,"Draw").clone();var c=b.getCode().code;long profile=CasDrawPhasePatch.target(c.get(6));for(var i:c)if(i.getAddress()>=profile&&CasStructuralRolesPatch.prop(a,i,0x4f,"gotoAndStop")){i.operands[1]=2;break;}b.setCode(b.getCode());b.setModified();CasStructuralRolesPatch.replace(a,b);});
  reject(before,after,"marker branch enters native operation incorrectly",a->{var b=CasDrawPhasePatch.body(a,CasDrawPhasePatch.CELL,"Draw").clone();var c=b.getCode().code;long profile=CasDrawPhasePatch.target(c.get(6));for(int j=0;j+3<c.size();j++)if(c.get(j).getAddress()>=profile&&CasDrawPhasePatch.op(c.get(j))==0x62&&CasDrawPhasePatch.op(c.get(j+1))==0x12){c.get(j+1).operands[0]++;break;}b.setCode(b.getCode());b.setModified();CasStructuralRolesPatch.replace(a,b);});
  reject(before,after,"diagnostic exception handler removed",a->{var b=CasDrawPhasePatch.body(a,CasDrawPhasePatch.MAIN,"ApexCatalogTraceStep").clone();b.exceptions=new com.jpexs.decompiler.flash.abc.types.ABCException[0];CasStructuralRolesPatch.replace(a,b);});
  reject(before,after,"diagnostic lexical scope",a->{var b=CasDrawPhasePatch.body(a,CasDrawPhasePatch.MAIN,"ApexCatalogTraceStep").clone();b.init_scope_depth++;b.max_scope_depth++;CasStructuralRolesPatch.replace(a,b);});
  reject(before,after,"unowned native Initialize metadata",a->{var b=CasDrawPhasePatch.body(a,CasDrawPhasePatch.MAIN,"Initialize").clone();b.max_regs++;CasStructuralRolesPatch.replace(a,b);});
  reject(before,after,"native constant prefix",a->{a.constants.setString(1,a.constants.getString(1)+"changed");});
 }
}
