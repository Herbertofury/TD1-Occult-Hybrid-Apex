// Private narrow postpass: add geometry entry points without replacing any
// native method, initializer, callback, feed, selection or color operation.
import java.nio.file.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;

public class CasSwatchGeometryPatch {
 static final String DONOR="c97afa8f0362a0452b359074769b9c99174444dd211927d08972091db3391969";
 static final String PANEL="widgets.CAS.controls.ColorSwatchPanel",GROUP="widgets.CAS.controls.ColorSwatchPanelCellView";
 static final List<String> TYPES=List.of(PANEL,GROUP),METHODS=List.of("ApexSwatchGeometry","ApexSwatchGroupGeometry");
 static final Map<String,String> SEMANTICS=Map.of("ApexSwatchGeometry","afe0a1083e9edab5870a3e3766a50b63a94fc2823304ce9d8c109b96091f5ca3","ApexSwatchGroupGeometry","128049fdc011312b5d98e1803cc11e5013c18ea1252544e8376d0d27e96695c8");
 static void check(boolean b,String s){CasStructuralRolesPatch.check(b,s);}
 static String sha(byte[] b)throws Exception{return CasStructuralRolesPatch.sha(b);}
 static String name(ABC a,int q){return CasStructuralRolesPatch.name(a,q);}
 static TraitMethodGetterSetter method(ABC a,String type,String n){return CasStructuralRolesPatch.trait(a,type,n,false);}
 static MethodBody body(ABC a,String type,String n){return CasStructuralRolesPatch.body(a,type,n,false);}
 static String semantic(ABC a,MethodBody b)throws Exception{return sha(CasCommunicationIndexPatch.semanticText(a,b).getBytes(java.nio.charset.StandardCharsets.UTF_8));}
 static TraitSlotConst field(ABC a){TraitSlotConst found=null;for(var t:a.instance_info.get(a.findClassByName(PANEL)).instance_traits.traits)if(name(a,t.name_index).equals("apexSwatchGeometry")){check(found==null&&t instanceof TraitSlotConst,"Swatch private field inventory differs");found=(TraitSlotConst)t;}check(found!=null,"Swatch private field missing");return found;}
 static String signature(ABC a,int id){var i=a.method_info.get(id);var out=new StringBuilder(i.flags+":"+CasCommunicationIndexPatch.qname(a,i.ret_type));for(int p:i.param_types)out.append(':').append(CasCommunicationIndexPatch.qname(a,p));check(i.optional.length==0,"Native swatch reference method acquired optional arguments");return out.toString();}
 static void nativeClasses(ABC donor,ABC base)throws Exception {
  var metadata=CasStructuralRolesPatch.reparse(base);
  for(String type:TYPES){int n=donor.findClassByName(type);check(n>=0&&base.findClassByName(type)==n,"Native swatch class moved");var a=donor.instance_info.get(n);var b=base.instance_info.get(n);
   check(a.instance_traits.traits.size()==b.instance_traits.traits.size(),"Incoming swatch class has unrelated new traits");
   for(int j=0;j<a.instance_traits.traits.size();j++){var x=a.instance_traits.traits.get(j);var y=b.instance_traits.traits.get(j);check(x.getClass()==y.getClass()&&CasCommunicationIndexPatch.qname(donor,x.name_index).equals(CasCommunicationIndexPatch.qname(base,y.name_index)),"Incoming native swatch trait changed");if(x instanceof TraitMethodGetterSetter){var m=(TraitMethodGetterSetter)x;var k=(TraitMethodGetterSetter)y;check(m.method_info==k.method_info&&Arrays.equals(donor.findBody(m.method_info).getCodeBytes(),base.findBody(k.method_info).getCodeBytes()),"Native swatch handler changed before geometry graft");}}
   for(int id:List.of(a.iinit_index,donor.class_info.get(n).cinit_index))check(Arrays.equals(donor.findBody(id).getCodeBytes(),base.findBody(id).getCodeBytes()),"Native swatch initializer changed before geometry graft");
   metadata.instance_info.set(n,a);metadata.class_info.set(n,donor.class_info.get(n));
  }
  check(Arrays.equals(CasStructuralRolesPatch.save(metadata),CasStructuralRolesPatch.save(base)),"Native swatch class/static trait/default metadata differs from exact donor");
 }
 static void helpers(ABC a)throws Exception {
  for(int j=0;j<TYPES.size();j++){String type=TYPES.get(j),n=METHODS.get(j);var t=method(a,type,n);var b=body(a,type,n);var i=a.method_info.get(t.method_info);var q=a.constants.getMultiname(t.name_index);var ns=a.constants.getNamespace(q.namespace_index);
   check(q.kind==Multiname.QNAME&&ns.kind==Namespace.KIND_PACKAGE&&a.constants.getString(ns.name_index).isEmpty()&&t.kindType==Trait.TRAIT_METHOD&&t.kindFlags==0,"Swatch helper must be an exact public method");
   check(i.param_types.length==5&&i.optional.length==0&&name(a,i.ret_type).equals("Object")&&name(a,i.param_types[0]).equals("int"),"Swatch geometry argument/return ABI differs");for(int k=1;k<5;k++)check(name(a,i.param_types[k]).equals("Number"),"Swatch geometry requires numeric parameters");
   check(b.exceptions.length==0&&b.traits.traits.isEmpty()&&semantic(a,b).equals(SEMANTICS.get(n)),"Reviewed swatch helper semantics/scope differ: "+n);
   for(var op:b.getCode().code)check(!Set.of(0x40,0x44,0x67).contains(CasStructuralRolesPatch.op(op)),"Swatch helper has a nested/outer dependency");
  }
  var t=field(a);var q=a.constants.getMultiname(t.name_index);var ns=a.constants.getNamespace(q.namespace_index);
  check(t.kindType==Trait.TRAIT_SLOT&&t.kindFlags==0&&q.kind==Multiname.QNAME&&ns.kind==Namespace.KIND_PRIVATE&&a.constants.getString(ns.name_index).equals("widgets.CAS.controls:ColorSwatchPanel")&&name(a,t.type_index).equals("Object")&&t.value_index==0,"Swatch geometry field must be exact private default-null Object");
 }
 static void bindings(ABC base,ABC candidate)throws Exception {
  for(int j=0;j<TYPES.size();j++){String type=TYPES.get(j);var declared=new HashMap<String,Integer>();for(var t:base.instance_info.get(base.findClassByName(type)).instance_traits.traits)declared.put(name(base,t.name_index),t.name_index);
   for(var op:body(candidate,type,METHODS.get(j)).getCode().code)if(Set.of(0x5d,0x60,0x61,0x66,0x68,0x46,0x4f).contains(CasStructuralRolesPatch.op(op))){String n=name(candidate,op.operands[0]);if(!declared.containsKey(n))continue;var expected=base.constants.getMultiname(declared.get(n));var actual=candidate.constants.getMultiname(op.operands[0]);boolean exact=actual.namespace_index==expected.namespace_index;if(actual.namespace_set_index>0)for(int ns:candidate.constants.getNamespaceSet(actual.namespace_set_index).namespaces)exact|=ns==expected.namespace_index;check(exact,"Swatch helper shadows native private/protected field/method: "+n);}
  }
 }
 static void verify(ABC base,ABC candidate)throws Exception {
  CasStructuralRolesPatch.prefix(base,candidate);helpers(candidate);bindings(base,candidate);
  check(candidate.method_info.size()==base.method_info.size()+2&&candidate.bodies.size()==base.bodies.size()+2,"Swatch may append only two methods");
  for(int j=0;j<2;j++){var b=body(candidate,TYPES.get(j),METHODS.get(j));check(b.method_info==base.method_info.size()+j&&b.init_scope_depth==body(base,TYPES.get(j),j==0 ? "ResetLayout" : "Draw").init_scope_depth,"Swatch helper lexical root or append order differs");}
  check(field(candidate).slot_id==0,"Swatch helper field must use append-only automatic slot assignment");
  for(var b:base.bodies){var made=candidate.findBody(b.method_info);check(made!=null&&Arrays.equals(b.getCodeBytes(),made.getCodeBytes())&&b.init_scope_depth==made.init_scope_depth&&b.max_scope_depth==made.max_scope_depth&&b.max_regs==made.max_regs&&b.max_stack==made.max_stack,"Unowned native/owned body or lexical metadata changed");}
  var projected=CasStructuralRolesPatch.reparse(candidate);
  for(int j=1;j>=0;j--){var list=projected.instance_info.get(projected.findClassByName(TYPES.get(j))).instance_traits.traits;var t=list.remove(list.size()-1);check(t instanceof TraitMethodGetterSetter&&name(projected,t.name_index).equals(METHODS.get(j))&&((TraitMethodGetterSetter)t).method_info==base.method_info.size()+j,"Only appended public geometry traits may roll back");projected.bodies.remove(projected.bodies.size()-1);projected.method_info.remove(projected.method_info.size()-1);}
  var list=projected.instance_info.get(projected.findClassByName(PANEL)).instance_traits.traits;check(list.remove(list.size()-1) instanceof TraitSlotConst,"Only appended private swatch state may roll back");
  projected.constants=base.constants;projected.resetMethodIndexing();check(Arrays.equals(CasStructuralRolesPatch.save(projected),CasStructuralRolesPatch.save(base)),"Full swatch rollback changed any unrelated native/owned ABC bytes");
 }
 public static void main(String[] args)throws Exception {
  check(args.length==5,"Use exact incoming Main, compiled swatch helpers, original donor, output ABC and proof");
  check(sha(Files.readAllBytes(Path.of(args[2]))).equals(DONOR),"Original donor authority differs");var donor=CasStructuralRolesPatch.load(args[2]);var base=CasStructuralRolesPatch.load(args[0]);var compiled=CasStructuralRolesPatch.load(args[1]);
  nativeClasses(donor,base);CasStructuralRolesPatch.prefix(base,compiled);helpers(compiled);
  var candidate=CasStructuralRolesPatch.reparse(base);candidate.constants=compiled.constants;
  var f=field(compiled).clone();((TraitSlotConst)f).slot_id=0;candidate.instance_info.get(candidate.findClassByName(PANEL)).instance_traits.traits.add(f);
  for(int j=0;j<2;j++){String type=TYPES.get(j),n=METHODS.get(j);int id=candidate.method_info.size();var t=method(compiled,type,n);candidate.method_info.add(compiled.method_info.get(t.method_info));candidate.bodies.add(CasStructuralRolesPatch.adapted(body(compiled,type,n),body(base,type,j==0 ? "ResetLayout" : "Draw"),id));var copy=t.clone();((TraitMethodGetterSetter)copy).method_info=id;((TraitMethodGetterSetter)copy).disp_id=0;candidate.instance_info.get(candidate.findClassByName(type)).instance_traits.traits.add(copy);}
  candidate.resetMethodIndexing();verify(base,candidate);candidate=CasStructuralRolesPatch.reparse(candidate);verify(base,candidate);
  byte[] out=CasStructuralRolesPatch.save(candidate);Files.write(Path.of(args[3]),out);
  String proof="{\"ok\":true,\"phase\":\"native-swatch-geometry\",\"baseline_swf_sha256\":\""+sha(Files.readAllBytes(Path.of(args[0])))+"\",\"baseline_abc_sha256\":\""+sha(CasStructuralRolesPatch.save(base))+"\",\"abc_sha256\":\""+sha(out)+"\",\"original_donor_sha256\":\""+DONOR+"\",\"appended_methods\":2,\"appended_fields\":1,\"changed_native_bodies\":0,\"same_native_class_scopes\":true,\"same_native_field_bindings\":true,\"original_callbacks_feeds_initializers_retained\":true,\"all_unrelated_bodies_exact\":true,\"full_abc_rollback_exact\":true,\"runtime_qualified\":false,\"performance_gain_claimed\":false}";Files.writeString(Path.of(args[4]),proof+"\n");System.out.println(proof);
 }
}
