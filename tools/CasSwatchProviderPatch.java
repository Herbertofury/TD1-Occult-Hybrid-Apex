// Append one reviewed geometry adapter to each exact native class provider.
// Original bytecode, callbacks, fields, feeds and initializers are never replaced.
import java.nio.file.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;

public class CasSwatchProviderPatch {
 static final String TYPE="widgets.CAS.controls.ColorSwatchPanel", METHOD="ApexSwatchGeometry";
 static final Set<String> ORIGINALS=Set.of("6ddb983fee2bd284a2b7efec155e1544bfe99d27f16d4d28097bada25e1864f0","5f475a80a4f9c77f9a0439e133221a31f766cb929318f74191b4b9bad98e8cae");
 static final String SEMANTIC="b7e342acf4dfb73f9512fa04b39938e3da60b9b4272d422f17cbff68e9309328";
 static void check(boolean b,String s){CasStructuralRolesPatch.check(b,s);}
 static String sha(byte[] b)throws Exception{return CasStructuralRolesPatch.sha(b);}
 static String name(ABC a,int n){return CasStructuralRolesPatch.name(a,n);}
 static TraitMethodGetterSetter method(ABC a){return CasStructuralRolesPatch.trait(a,TYPE,METHOD,false);}
 static MethodBody body(ABC a){return a.findBody(method(a).method_info);}
 static TraitSlotConst field(ABC a){TraitSlotConst found=null;for(var t:a.instance_info.get(a.findClassByName(TYPE)).instance_traits.traits)if(name(a,t.name_index).equals("apexSwatchGeometry")){check(found==null&&t instanceof TraitSlotConst,"Swatch provider state inventory differs");found=(TraitSlotConst)t;}check(found!=null,"Swatch provider state absent");return found;}
 static String semantic(ABC a,MethodBody b)throws Exception {
  String text=CasCommunicationIndexPatch.semanticText(a,b).replaceAll("(?<=5:)ColorSwatchPanel\\.as\\$[0-9]+","ColorSwatchPanel.as\\$SELF");
  int base=Integer.MAX_VALUE;for(var op:b.getCode().code)if(CasStructuralRolesPatch.op(op)==0xef&&op.operands.length==4&&op.operands[0]==1&&op.operands[3]>0)base=Math.min(base,op.operands[3]);
  if(base!=Integer.MAX_VALUE){final int start=base;text=java.util.regex.Pattern.compile("(?m)^(239:1:.*:[0-9]+):([1-9][0-9]*)$").matcher(text).replaceAll(m->m.group(1)+":owned-source+"+(Integer.parseInt(m.group(2))-start));}
  return sha(text.getBytes(java.nio.charset.StandardCharsets.UTF_8));
 }
 static void nativeClass(ABC original,ABC base)throws Exception {
  int id=original.findClassByName(TYPE);check(id>=0&&base.findClassByName(TYPE)==id,"Exact native swatch provider class moved");
  var a=original.instance_info.get(id);var b=base.instance_info.get(id);check(a.instance_traits.traits.size()==b.instance_traits.traits.size(),"Native swatch provider has unrelated traits");
  for(int n=0;n<a.instance_traits.traits.size();n++){var x=a.instance_traits.traits.get(n);var y=b.instance_traits.traits.get(n);check(x.getClass()==y.getClass()&&CasCommunicationIndexPatch.qname(original,x.name_index).equals(CasCommunicationIndexPatch.qname(base,y.name_index)),"Native swatch provider trait changed");if(x instanceof TraitMethodGetterSetter){var m=(TraitMethodGetterSetter)x;var k=(TraitMethodGetterSetter)y;check(m.method_info==k.method_info&&Arrays.equals(original.findBody(m.method_info).getCodeBytes(),base.findBody(k.method_info).getCodeBytes()),"Native swatch provider callback changed");}}
  for(int m:List.of(a.iinit_index,original.class_info.get(id).cinit_index))check(Arrays.equals(original.findBody(m).getCodeBytes(),base.findBody(m).getCodeBytes()),"Native swatch provider initializer changed");
  var p=CasStructuralRolesPatch.reparse(base);p.instance_info.set(id,a);p.class_info.set(id,original.class_info.get(id));check(Arrays.equals(CasStructuralRolesPatch.save(p),CasStructuralRolesPatch.save(base)),"Exact native swatch provider metadata differs");
 }
 static void helper(ABC a)throws Exception {
  var t=method(a);var b=body(a);var i=a.method_info.get(t.method_info);var q=a.constants.getMultiname(t.name_index);var ns=a.constants.getNamespace(q.namespace_index);
  check(q.kind==Multiname.QNAME&&ns.kind==Namespace.KIND_PACKAGE&&a.constants.getString(ns.name_index).isEmpty()&&t.kindType==Trait.TRAIT_METHOD&&t.kindFlags==0,"Swatch provider helper must be public");
  check(i.flags==0&&i.optional.length==0&&i.param_types.length==5&&name(a,i.ret_type).equals("Object")&&name(a,i.param_types[0]).equals("int"),"Swatch provider helper signature differs");for(int n=1;n<5;n++)check(name(a,i.param_types[n]).equals("Number"),"Swatch provider numeric signature differs");
  String actual=semantic(a,b);check(b.exceptions.length==0&&b.traits.traits.isEmpty()&&actual.equals(SEMANTIC),"Reviewed swatch provider helper semantics differ: "+actual);
  for(var op:b.getCode().code)check(!Set.of(0x40,0x43,0x44,0x67).contains(CasStructuralRolesPatch.op(op)),"Swatch provider helper has nested/outer linkage");
  var f=field(a);q=a.constants.getMultiname(f.name_index);ns=a.constants.getNamespace(q.namespace_index);check(f.kindType==Trait.TRAIT_SLOT&&f.kindFlags==0&&q.kind==Multiname.QNAME&&ns.kind==Namespace.KIND_PRIVATE&&a.constants.getString(ns.name_index).equals("widgets.CAS.controls:ColorSwatchPanel")&&name(a,f.type_index).equals("Object")&&f.value_index==0,"Swatch provider state must be exact default-null private Object");
 }
 static void bindings(ABC base,ABC a){var declared=new HashMap<String,Integer>();for(var t:base.instance_info.get(base.findClassByName(TYPE)).instance_traits.traits)declared.put(name(base,t.name_index),t.name_index);
  for(var op:body(a).getCode().code)if(Set.of(0x5d,0x60,0x61,0x66,0x68,0x46,0x4f).contains(CasStructuralRolesPatch.op(op))){String n=name(a,op.operands[0]);if(!declared.containsKey(n))continue;var expected=base.constants.getMultiname(declared.get(n));var actual=a.constants.getMultiname(op.operands[0]);boolean exact=actual.namespace_index==expected.namespace_index;if(actual.namespace_set_index>0)for(int ns:a.constants.getNamespaceSet(actual.namespace_set_index).namespaces)exact|=ns==expected.namespace_index;check(exact,"Swatch provider helper shadows native field: "+n);}}
 static void verify(ABC base,ABC a)throws Exception {
  CasStructuralRolesPatch.prefix(base,a);helper(a);bindings(base,a);int count=base.method_info.size();check(a.method_info.size()==count+1&&a.bodies.size()==base.bodies.size()+1,"Swatch provider may append one method only");
  var b=body(a);check(b.method_info==count&&b.init_scope_depth==CasStructuralRolesPatch.body(base,TYPE,"ResetLayout",false).init_scope_depth&&field(a).slot_id==0,"Swatch provider scope/order/default slot differs");
  for(var before:base.bodies){var after=a.findBody(before.method_info);check(after!=null&&Arrays.equals(before.getCodeBytes(),after.getCodeBytes())&&before.init_scope_depth==after.init_scope_depth&&before.max_scope_depth==after.max_scope_depth&&before.max_regs==after.max_regs&&before.max_stack==after.max_stack,"Unrelated provider body/lexical metadata changed");}
  var p=CasStructuralRolesPatch.reparse(a);var list=p.instance_info.get(p.findClassByName(TYPE)).instance_traits.traits;var t=list.remove(list.size()-1);check(t instanceof TraitMethodGetterSetter&&name(p,t.name_index).equals(METHOD)&&((TraitMethodGetterSetter)t).method_info==count,"Swatch provider appended method differs");check(list.remove(list.size()-1) instanceof TraitSlotConst,"Swatch provider appended field differs");p.bodies.remove(p.bodies.size()-1);p.method_info.remove(p.method_info.size()-1);p.constants=base.constants;p.resetMethodIndexing();check(Arrays.equals(CasStructuralRolesPatch.save(p),CasStructuralRolesPatch.save(base)),"Full swatch provider rollback differs");
 }
 public static void main(String[] args)throws Exception {
  check(args.length==5,"Use incoming provider, compiled helper, exact original, output ABC and proof");String originalSha=sha(Files.readAllBytes(Path.of(args[2])));check(ORIGINALS.contains(originalSha),"Unknown native swatch provider");var original=CasStructuralRolesPatch.load(args[2]);var base=CasStructuralRolesPatch.load(args[0]);var compiled=CasStructuralRolesPatch.load(args[1]);nativeClass(original,base);CasStructuralRolesPatch.prefix(base,compiled);helper(compiled);
  var a=CasStructuralRolesPatch.reparse(base);a.constants=compiled.constants;var f=field(compiled).clone();((TraitSlotConst)f).slot_id=0;a.instance_info.get(a.findClassByName(TYPE)).instance_traits.traits.add(f);int id=a.method_info.size();var m=method(compiled);a.method_info.add(compiled.method_info.get(m.method_info));a.bodies.add(CasStructuralRolesPatch.adapted(body(compiled),CasStructuralRolesPatch.body(base,TYPE,"ResetLayout",false),id));var t=m.clone();((TraitMethodGetterSetter)t).method_info=id;((TraitMethodGetterSetter)t).disp_id=0;a.instance_info.get(a.findClassByName(TYPE)).instance_traits.traits.add(t);a.resetMethodIndexing();verify(base,a);a=CasStructuralRolesPatch.reparse(a);verify(base,a);byte[] out=CasStructuralRolesPatch.save(a);Files.write(Path.of(args[3]),out);
  String proof="{\"ok\":true,\"phase\":\"native-swatch-provider\",\"baseline_swf_sha256\":\""+sha(Files.readAllBytes(Path.of(args[0])))+"\",\"baseline_abc_sha256\":\""+sha(CasStructuralRolesPatch.save(base))+"\",\"abc_sha256\":\""+sha(out)+"\",\"original_provider_sha256\":\""+originalSha+"\",\"appended_methods\":1,\"appended_fields\":1,\"changed_native_bodies\":0,\"same_native_class_scope\":true,\"same_native_field_bindings\":true,\"original_callbacks_feeds_initializers_retained\":true,\"all_unrelated_bodies_exact\":true,\"full_abc_rollback_exact\":true,\"runtime_qualified\":false,\"performance_gain_claimed\":false}";Files.writeString(Path.of(args[4]),proof+"\n");System.out.println(proof);
 }
}
