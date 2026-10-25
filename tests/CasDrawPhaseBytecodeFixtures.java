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
 public static void main(String[] args)throws Exception {
  var before=CasStructuralRolesPatch.load(args[0]);var after=CasStructuralRolesPatch.load(args[1]);verify(before,after);System.out.println("PASS serialized profile-only native CFG projection");
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
