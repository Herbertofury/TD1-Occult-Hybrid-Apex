import java.nio.file.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
public class CasGridBudgetMainPatch {
 static final String MAIN="widgets.CAS.Customizer.CASCustomizerMain";
 static final List<String> METHODS=List.of("ApexCatalogGridRequest","ApexCatalogGridStatus");
 static final Map<String,String> PINS=Map.ofEntries(Map.entry("ApexCatalogGridRequest","e2139e162faa9e271c6274774159cc46b11c57dcbb015c4928475e0be6aa974c"),
 Map.entry("ApexCatalogGridStatus","b3a3c0a2f4a08707179a38b9d3c9e2fa7f91fb5e22d58c9e3bf9caa403950f74")
 );
 static void check(boolean v,String m){CasStructuralRolesPatch.check(v,m);}
 static TraitMethodGetterSetter trait(ABC a,String n){return CasStructuralRolesPatch.trait(a,MAIN,n,false);}
 static MethodBody body(ABC a,String n){return a.findBody(trait(a,n).method_info);}
 static String sha(byte[] b)throws Exception{return CasStructuralRolesPatch.sha(b);}
 static String semantic(ABC a,MethodBody b)throws Exception {
  String text=CasCommunicationIndexPatch.semanticText(a,b).replaceAll("(?<=5:)CASCustomizerMain\\.as\\$[0-9]+","CASCustomizerMain.as\\$SELF");int first=Integer.MAX_VALUE;
  for(var i:b.getCode().code)if(CasStructuralRolesPatch.op(i)==0xef&&i.operands.length==4&&i.operands[0]==1&&i.operands[3]>0)first=Math.min(first,i.operands[3]);
  if(first!=Integer.MAX_VALUE){final int start=first;text=java.util.regex.Pattern.compile("(?m)^(239:1:.*:[0-9]+):([1-9][0-9]*)$").matcher(text).replaceAll(m->m.group(1)+":owned-source+"+(Integer.parseInt(m.group(2))-start));}
  return sha(text.getBytes(java.nio.charset.StandardCharsets.UTF_8));
 }
 static void reviewed(ABC a)throws Exception {
  for(String n:METHODS){var t=trait(a,n);var b=body(a,n);var ns=a.constants.getNamespace(a.constants.getMultiname(t.name_index).namespace_index);
   check(semantic(a,b).equals(PINS.get(n)),"Budget Main exact semantic/CFG differs: "+n);check(t.kindType==1&&t.kindFlags==0&&ns.kind==5&&a.constants.getString(ns.name_index).equals("widgets.CAS.Customizer:CASCustomizerMain"),"Main private method namespace differs");
   check(a.method_info.get(t.method_info).flags==0&&b.traits.traits.isEmpty()&&b.exceptions.length==0,"Main unexpected activation/closure/catch");int clocks=0;
   for(var i:b.getCode().code){int op=CasStructuralRolesPatch.op(i);check(!Set.of(0x40,0x43,0x44,0x67).contains(op),"Main new nested/outer dependency");
    if(op==0x60){String leaf=CasStructuralRolesPatch.name(a,i.operands[0]);check(!Set.of("flash","widgets","olympus","gamedata").contains(leaf),"Unresolved runtime package chain");}
    if(Set.of(0x5d,0x46).contains(op)&&CasStructuralRolesPatch.name(a,i.operands[0]).equals("getTimer")){check(CasCommunicationIndexPatch.qname(a,i.operands[0]).equals("7:getTimer:22:flash.utils"),"Timer QName is not native flash.utils");if(op==0x46){check(i.operands[1]==0,"Native timer argument count differs");clocks++;}}
   }check(clocks==(n.equals("ApexCatalogGridStatus")?2:0),"Only one-off status bracket may have exactly two native Main clocks");
  }
 }
 static void abi(ABC a,ABC c,String n){var x=a.method_info.get(trait(a,n).method_info);var y=c.method_info.get(trait(c,n).method_info);check(x.flags==y.flags&&x.optional.length==0&&y.optional.length==0&&x.param_types.length==y.param_types.length&&CasCommunicationIndexPatch.qname(a,x.ret_type).equals(CasCommunicationIndexPatch.qname(c,y.ret_type)),"Main method ABI differs");for(int i=0;i<x.param_types.length;i++)check(CasCommunicationIndexPatch.qname(a,x.param_types[i]).equals(CasCommunicationIndexPatch.qname(c,y.param_types[i])),"Main parameter type differs");}
 static void retained(ABC base,ABC result)throws Exception {
  CasStructuralRolesPatch.prefix(base,result);reviewed(result);check(base.method_info.size()==result.method_info.size()&&base.bodies.size()==result.bodies.size(),"Main added methods");var ids=new HashSet<Integer>();for(String n:METHODS)ids.add(body(base,n).method_info);
  for(var b:base.bodies)if(!ids.contains(b.method_info))check(Arrays.equals(b.getCodeBytes(),result.findBody(b.method_info).getCodeBytes()),"Unowned/native Main body changed");
  var rollback=CasStructuralRolesPatch.reparse(result);for(String n:METHODS)CasStructuralRolesPatch.replace(rollback,body(base,n).clone());rollback.constants=base.constants;rollback.resetMethodIndexing();check(Arrays.equals(CasStructuralRolesPatch.save(base),CasStructuralRolesPatch.save(rollback)),"Whole Main ABC rollback differs");
 }
 public static void main(String[] args)throws Exception {
  if(args.length==2&&args[0].equals("--semantic")){var a=CasStructuralRolesPatch.load(args[1]);for(String n:METHODS)System.out.println(n+" "+semantic(a,body(a,n)));return;}
  check(args.length==4,"Use previous Main, compiled Main, output ABC, proof");var base=CasStructuralRolesPatch.load(args[0]);var compiled=CasStructuralRolesPatch.load(args[1]);CasStructuralRolesPatch.prefix(base,compiled);reviewed(compiled);var result=CasStructuralRolesPatch.reparse(base);result.constants=compiled.constants;
  for(String n:METHODS){abi(base,compiled,n);var old=body(base,n);var made=body(compiled,n).clone();int delta=old.init_scope_depth-made.init_scope_depth;check(delta>=0&&delta<=16,"Owned method lexical scope delta differs");made.method_info=old.method_info;made.init_scope_depth+=delta;made.max_scope_depth+=delta;made.setCode(made.getCode());made.setModified();CasStructuralRolesPatch.replace(result,made);}
  result.resetMethodIndexing();retained(base,result);result=CasStructuralRolesPatch.reparse(result);retained(base,result);byte[] out=CasStructuralRolesPatch.save(result);Files.write(Path.of(args[2]),out);String proof="{\"ok\":true,\"owned_main_replacements\":2,\"new_traits\":0,\"new_fields\":0,\"native_original_changes\":0,\"whole_abc_rollback_verified\":true,\"all_other_bodies_retained\":true,\"native_timer_QNames_verified\":true,\"runtime_qualified\":false,\"baseline_swf_sha256\":\""+sha(Files.readAllBytes(Path.of(args[0])))+"\",\"abc_sha256\":\""+sha(out)+"\"}";Files.writeString(Path.of(args[3]),proof+"\n");System.out.println(proof);
 }
}
