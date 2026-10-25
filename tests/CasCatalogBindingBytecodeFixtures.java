import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;

public class CasCatalogBindingBytecodeFixtures {
 interface Mutation {void run(ABC a)throws Exception;}
 static void check(boolean b,String n){CasCatalogBindingPatch.check(b,n);}
 static void verify(ABC base,ABC candidate)throws Exception {
  var r=CasCatalogBindingPatch.rewrite(base,CasCatalogBindingPatch.trait(candidate,CasCatalogBindingPatch.WRAPPER).name_index);
  var ids=Set.of(CasCatalogBindingPatch.body(base,CasCatalogBindingPatch.OBSERVE).method_info,base.method_info.size(),base.method_info.size()+1);
  CasCatalogBindingPatch.verify(base,candidate,r,ids);
 }
 static void rejected(ABC base,ABC finalAbc,String n,Mutation mutation)throws Exception {
  var a=CasStructuralRolesPatch.reparse(finalAbc);mutation.run(a);a=CasStructuralRolesPatch.reparse(a);boolean refused=false;
  try{verify(base,a);}catch(IllegalArgumentException expected){refused=true;}
  check(refused,"Unreviewed mutation accepted: "+n);System.out.println("PASS "+n);
 }
 public static void main(String[] args)throws Exception {
  check(args.length==2,"Use exact baseline and final Main fixture");var base=CasStructuralRolesPatch.load(args[0]);var result=CasStructuralRolesPatch.load(args[1]);verify(base,result);System.out.println("PASS compiled native projection and whole-ABC rollback");
  rejected(base,result,"unowned initializer metadata",a->{var b=CasCatalogBindingPatch.body(a,"Initialize").clone();b.max_stack++;CasStructuralRolesPatch.replace(a,b);});
  rejected(base,result,"unowned native binding metadata",a->{var b=CasCatalogBindingPatch.body(a,"BindDisplayObjectToSim").clone();b.max_stack++;CasStructuralRolesPatch.replace(a,b);});
  rejected(base,result,"first native alignment extra locals",a->{var b=CasCatalogBindingPatch.body(a,CasCatalogBindingPatch.ALIGN).clone();b.max_regs++;CasStructuralRolesPatch.replace(a,b);});
  rejected(base,result,"first native alignment stack",a->{var b=CasCatalogBindingPatch.body(a,CasCatalogBindingPatch.ALIGN).clone();b.max_stack++;CasStructuralRolesPatch.replace(a,b);});
  rejected(base,result,"first native alignment lexical scope",a->{var b=CasCatalogBindingPatch.body(a,CasCatalogBindingPatch.ALIGN).clone();b.init_scope_depth++;b.max_scope_depth++;CasStructuralRolesPatch.replace(a,b);});
  rejected(base,result,"other native bind ABI",a->{var b=CasCatalogBindingPatch.body(a,CasCatalogBindingPatch.ALIGN).clone();for(var i:b.getCode().code)if(CasCatalogBindingPatch.prop(a,i,0x4f,"BindDisplayObjectToSim")){i.operands[1]++;break;}b.setCode(b.getCode());b.setModified();CasStructuralRolesPatch.replace(a,b);});
  rejected(base,result,"owned observer semantic mutation",a->{var b=CasCatalogBindingPatch.body(a,CasCatalogBindingPatch.OBSERVE).clone();b.max_stack++;CasStructuralRolesPatch.replace(a,b);});
  rejected(base,result,"width helper lexical scope",a->{var b=CasCatalogBindingPatch.body(a,CasCatalogBindingPatch.WIDTH).clone();b.init_scope_depth++;b.max_scope_depth++;CasStructuralRolesPatch.replace(a,b);});
  rejected(base,result,"wrapper helper dispatch ID",a->{CasCatalogBindingPatch.trait(a,CasCatalogBindingPatch.WRAPPER).disp_id=7;});
  rejected(base,result,"wrapper helper getter kind",a->{CasCatalogBindingPatch.trait(a,CasCatalogBindingPatch.WRAPPER).kindType=Trait.TRAIT_GETTER;});
  rejected(base,result,"wrapper helper final flag",a->{CasCatalogBindingPatch.trait(a,CasCatalogBindingPatch.WRAPPER).kindFlags=1;});
  rejected(base,result,"native constant pool prefix",a->{a.constants.setString(1,a.constants.getString(1)+"changed");});
 }
}
