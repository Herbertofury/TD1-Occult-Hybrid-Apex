import java.nio.file.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
public class CasGridStagingAttachPatch {
 static final String GRID="olympus.layout.RecyclingGridLayout",METHOD="ApexGridAttach";
 static final String PIN="cd4ed53c679fa7c314b08e29e4f6439ac64c40b2aac738093b4d12c9c080a312";
 static void check(boolean v,String m){CasStructuralRolesPatch.check(v,m);}
 static TraitMethodGetterSetter trait(ABC a){return CasStructuralRolesPatch.trait(a,GRID,METHOD,false);}
 static MethodBody body(ABC a){return a.findBody(trait(a).method_info);}
 static String sha(byte[] v)throws Exception{return CasStructuralRolesPatch.sha(v);}
 static String semantic(ABC a)throws Exception{
  var b=body(a);String text=CasCommunicationIndexPatch.semanticText(a,b).replaceAll("(?<=5:)RecyclingGridLayout\\.as\\$[0-9]+","RecyclingGridLayout.as\\$SELF");int first=Integer.MAX_VALUE;
  for(var i:b.getCode().code)if(CasStructuralRolesPatch.op(i)==0xef&&i.operands.length==4&&i.operands[0]==1&&i.operands[3]>0)first=Math.min(first,i.operands[3]);
  if(first!=Integer.MAX_VALUE){final int start=first;text=java.util.regex.Pattern.compile("(?m)^(239:1:.*:[0-9]+):([1-9][0-9]*)$").matcher(text).replaceAll(m->m.group(1)+":owned-source+"+(Integer.parseInt(m.group(2))-start));}
  return sha(text.getBytes(java.nio.charset.StandardCharsets.UTF_8));
 }
 static void reviewed(ABC a)throws Exception{
  var t=trait(a);var b=body(a);var q=a.constants.getMultiname(t.name_index);var ns=a.constants.getNamespace(q.namespace_index);var info=a.method_info.get(t.method_info);
  check(semantic(a).equals(PIN),"Reviewed staging attach semantic/CFG differs");
  check(t.kindType==Trait.TRAIT_METHOD&&t.kindFlags==0&&q.kind==Multiname.QNAME&&ns.kind==Namespace.KIND_PACKAGE&&a.constants.getString(ns.name_index).isEmpty(),"Existing public attach trait ABI differs");
  check(info.flags==0&&info.optional.length==0&&info.param_types.length==1&&b.exceptions.length==0&&b.traits.traits.isEmpty(),"Attach added activation/exception/default ABI");
  int calls=0;
  for(var i:b.getCode().code){int op=CasStructuralRolesPatch.op(i);
   check(!Set.of(0x40,0x41,0x42,0x43,0x44,0x55,0x56,0x57,0x67).contains(op),"Attach introduces allocation/function/outer dependency");
   if(Set.of(0x46,0x4f,0x45,0x4e).contains(op)){
    check(op==0x4f&&"addChild".equals(CasStructuralRolesPatch.name(a,i.operands[0]))&&i.operands[1]==1,"Attach may retain only its original single addChild callback");calls++;
   }
  }check(calls==1,"Original addChild call missing/repeated");
 }
 static void abi(ABC a,ABC c){
  var x=a.method_info.get(trait(a).method_info);var y=c.method_info.get(trait(c).method_info);
  check(x.flags==y.flags&&x.param_types.length==1&&y.param_types.length==1&&x.optional.length==0&&y.optional.length==0&&CasCommunicationIndexPatch.qname(a,x.param_types[0]).equals(CasCommunicationIndexPatch.qname(c,y.param_types[0]))&&CasCommunicationIndexPatch.qname(a,x.ret_type).equals(CasCommunicationIndexPatch.qname(c,y.ret_type)),"Original attach callable ABI differs");
 }
 static void bindings(ABC base,ABC a){
  String view=null,state=null;
  for(var i:body(base).getCode().code)if(Set.of(0x60,0x66).contains(CasStructuralRolesPatch.op(i))&&"mGridView".equals(CasStructuralRolesPatch.name(base,i.operands[0])))view=CasCommunicationIndexPatch.qname(base,i.operands[0]);
  for(var t:base.instance_info.get(base.findClassByName(GRID)).instance_traits.traits)if(t instanceof TraitSlotConst&&"apexGridState".equals(CasStructuralRolesPatch.name(base,t.name_index)))state=CasCommunicationIndexPatch.qname(base,t.name_index);
  check(view!=null&&state!=null,"Existing grid field declaration/binding missing");int views=0,states=0;
  for(var i:body(a).getCode().code)if(Set.of(0x5d,0x60,0x61,0x66,0x68).contains(CasStructuralRolesPatch.op(i))){String name=CasStructuralRolesPatch.name(a,i.operands[0]);
   if("mGridView".equals(name)){check(view.equals(CasCommunicationIndexPatch.qname(a,i.operands[0])),"Native inherited view protected binding differs");views++;}
   if("apexGridState".equals(name)){check(state.equals(CasCommunicationIndexPatch.qname(a,i.operands[0])),"Existing private state binding differs");states++;}
  }check(views>=3&&states==2,"Expected fixed view/state freshness reads differ");
 }
 static void retained(ABC base,ABC result,String expected)throws Exception{
  CasStructuralRolesPatch.prefix(base,result);reviewed(result);bindings(base,result);
  check(base.method_info.size()==result.method_info.size()&&base.bodies.size()==result.bodies.size(),"Attach added methods");
  check(sha(body(result).getCodeBytes()).equals(expected),"Serialized attach body differs");
  for(var b:base.bodies)if(b.method_info!=body(base).method_info)check(Arrays.equals(b.getCodeBytes(),result.findBody(b.method_info).getCodeBytes()),"Unowned/original body changed");
  var rollback=CasStructuralRolesPatch.reparse(result);CasStructuralRolesPatch.replace(rollback,body(base).clone());rollback.constants=base.constants;rollback.resetMethodIndexing();check(Arrays.equals(CasStructuralRolesPatch.save(base),CasStructuralRolesPatch.save(rollback)),"Complete attach ABC rollback changed native fields/traits/initializers/methods");
 }
 public static void main(String[] args)throws Exception{
  if(args.length==2&&args[0].equals("--semantic")){System.out.println(semantic(CasStructuralRolesPatch.load(args[1])));return;}
  check(args.length==4,"Use exact verified prior SWF, compiled one-body stub, retained ABC, proof");var base=CasStructuralRolesPatch.load(args[0]);var compiled=CasStructuralRolesPatch.load(args[1]);CasStructuralRolesPatch.prefix(base,compiled);reviewed(compiled);abi(base,compiled);
  var old=body(base);var made=body(compiled).clone();int delta=old.init_scope_depth-made.init_scope_depth;check(delta>=0&&delta<=16,"Attach lexical scope delta differs");made.method_info=old.method_info;made.init_scope_depth+=delta;made.max_scope_depth+=delta;made.setCode(made.getCode());made.setModified();
  var result=CasStructuralRolesPatch.reparse(base);result.constants=compiled.constants;CasStructuralRolesPatch.replace(result,made);result.resetMethodIndexing();String expected=sha(made.getCodeBytes());retained(base,result,expected);result=CasStructuralRolesPatch.reparse(result);retained(base,result,expected);byte[] out=CasStructuralRolesPatch.save(result);Files.write(Path.of(args[2]),out);
  String report="{\"ok\":true,\"owned_replacements\":1,\"new_methods\":0,\"new_traits\":0,\"new_fields\":0,\"changed_original_native_bodies\":0,\"whole_abc_rollback_verified\":true,\"all_unowned_bodies_retained\":true,\"serialized_owned_body_verified\":true,\"native_bindings_verified\":true,\"runtime_qualified\":false,\"performance_gain_claimed\":false,\"baseline_swf_sha256\":\""+sha(Files.readAllBytes(Path.of(args[0])))+"\",\"baseline_abc_sha256\":\""+sha(CasStructuralRolesPatch.save(base))+"\",\"abc_sha256\":\""+sha(out)+"\"}";Files.writeString(Path.of(args[3]),report+"\n");System.out.println(report);
 }
}
