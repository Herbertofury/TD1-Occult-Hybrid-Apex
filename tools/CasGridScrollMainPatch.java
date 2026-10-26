import java.nio.file.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;

/** Private single owned-method continuation; no native original replacement. */
public class CasGridScrollMainPatch {
 static final String MAIN="widgets.CAS.Customizer.CASCustomizerMain",METHOD="ApexCatalogGridRequest";
 static final Set<String> CELLS=Set.of("CASClothingPanelCellViewMain","CASClothingPanelCellViewCommon","CASClothingPanelCellViewSkinSpecularity","CASBodyPanelCellView","CASFacePanelCellView","CASGenericCatalogVariantCellView","CASBreedCatalogCellView");
 static final String PIN="d2b580a29b66032215564b9d251fe18695a3859452417bd3090a2be242a6d0ee";
 static void check(boolean v,String m){CasStructuralRolesPatch.check(v,m);}
 static TraitMethodGetterSetter trait(ABC a){return CasStructuralRolesPatch.trait(a,MAIN,METHOD,false);}
 static MethodBody body(ABC a){return a.findBody(trait(a).method_info);}
 static String sha(byte[] b)throws Exception{return CasStructuralRolesPatch.sha(b);}
 static String semantic(ABC a,MethodBody b)throws Exception {
  String text=CasCommunicationIndexPatch.semanticText(a,b).replaceAll("(?<=5:)CASCustomizerMain\\.as\\$[0-9]+","CASCustomizerMain.as\\$SELF");
  int base=Integer.MAX_VALUE;
  for(var op:b.getCode().code)if(CasStructuralRolesPatch.op(op)==0xef&&op.operands.length==4&&op.operands[0]==1&&op.operands[3]>0)base=Math.min(base,op.operands[3]);
  if(base!=Integer.MAX_VALUE){final int start=base;text=java.util.regex.Pattern.compile("(?m)^(239:1:.*:[0-9]+):([1-9][0-9]*)$").matcher(text).replaceAll(m->m.group(1)+":owned-source+"+(Integer.parseInt(m.group(2))-start));}
  return sha(text.getBytes(java.nio.charset.StandardCharsets.UTF_8));
 }
 static void reviewed(ABC a)throws Exception {
  var b=body(a);var t=trait(a);var ns=a.constants.getNamespace(a.constants.getMultiname(t.name_index).namespace_index);
  check(semantic(a,b).equals(PIN),"Reviewed Main request semantic/CFG differs");
  check(t.kindType==Trait.TRAIT_METHOD&&t.kindFlags==0&&ns.kind==Namespace.KIND_PRIVATE&&a.constants.getString(ns.name_index).equals("widgets.CAS.Customizer:CASCustomizerMain"),"Main request namespace/trait differs");
  check(a.method_info.get(t.method_info).flags==0&&b.traits.traits.isEmpty()&&b.exceptions.length==0,"Main request has unexpected closure/exception state");
  var found=new HashSet<String>();
  for(var op:b.getCode().code) {
   int kind=CasStructuralRolesPatch.op(op);
   check(!Set.of(0x40,0x43,0x44,0x67).contains(kind),"Main request has new function/outer/callmethod dependency");
   if(kind==0x60) {
    String name=CasStructuralRolesPatch.name(a,op.operands[0]);
    check(!Set.of("flash","widgets","olympus","gamedata").contains(name),"Main request unresolved runtime package chain");
    if(CELLS.contains(name)) {check(CasCommunicationIndexPatch.qname(a,op.operands[0]).equals("7:"+name+":22:widgets.CAS.controls"),"Known card class QName differs");found.add(name);}
   }
  }
  check(found.equals(CELLS),"Main known-class opt-in inventory differs");
 }
 static void abi(ABC a,ABC c) {
  var x=a.method_info.get(trait(a).method_info);var y=c.method_info.get(trait(c).method_info);
  check(x.flags==y.flags&&x.param_types.length==1&&y.param_types.length==1&&x.optional.length==0&&y.optional.length==0&&CasCommunicationIndexPatch.qname(a,x.param_types[0]).equals(CasCommunicationIndexPatch.qname(c,y.param_types[0]))&&CasCommunicationIndexPatch.qname(a,x.ret_type).equals(CasCommunicationIndexPatch.qname(c,y.ret_type)),"Main request callable ABI differs");
 }
 static void retained(ABC base,ABC result,String expected)throws Exception {
  CasStructuralRolesPatch.prefix(base,result);reviewed(result);
  check(base.method_info.size()==result.method_info.size()&&base.bodies.size()==result.bodies.size(),"Main request added methods");
  check(sha(body(result).getCodeBytes()).equals(expected),"Serialized request instructions differ");
  for(var b:base.bodies)if(b.method_info!=body(base).method_info)check(Arrays.equals(b.getCodeBytes(),result.findBody(b.method_info).getCodeBytes()),"Unowned/native Main body changed");
  var rollback=CasStructuralRolesPatch.reparse(result);CasStructuralRolesPatch.replace(rollback,body(base).clone());rollback.constants=base.constants;rollback.resetMethodIndexing();
  check(Arrays.equals(CasStructuralRolesPatch.save(base),CasStructuralRolesPatch.save(rollback)),"Whole Main ABC rollback differs");
 }
 public static void main(String[] args)throws Exception {
  if(args.length==2&&args[0].equals("--semantic")){var a=CasStructuralRolesPatch.load(args[1]);System.out.println(semantic(a,body(a)));return;}
  check(args.length==4,"Use reviewed prior Main, compiled request, output ABC, proof");
  var base=CasStructuralRolesPatch.load(args[0]);var compiled=CasStructuralRolesPatch.load(args[1]);CasStructuralRolesPatch.prefix(base,compiled);reviewed(compiled);abi(base,compiled);
  var made=body(compiled).clone();var old=body(base);int delta=old.init_scope_depth-made.init_scope_depth;check(delta>=0&&delta<=16,"Main request scope delta differs");
  made.method_info=old.method_info;made.init_scope_depth+=delta;made.max_scope_depth+=delta;made.setCode(made.getCode());made.setModified();
  var result=CasStructuralRolesPatch.reparse(base);result.constants=compiled.constants;CasStructuralRolesPatch.replace(result,made);result.resetMethodIndexing();String expected=sha(made.getCodeBytes());retained(base,result,expected);result=CasStructuralRolesPatch.reparse(result);retained(base,result,expected);
  byte[] out=CasStructuralRolesPatch.save(result);Files.write(Path.of(args[2]),out);
  String report="{\"ok\":true,\"new_traits\":0,\"new_fields\":0,\"native_original_changes\":0,\"owned_request_replacements\":1,\"whole_abc_rollback_verified\":true,\"all_other_bodies_retained\":true,\"known_native_class_QNames_verified\":true,\"runtime_qualified\":false,\"baseline_sha256\":\""+sha(Files.readAllBytes(Path.of(args[0])))+"\",\"abc_sha256\":\""+sha(out)+"\",\"semantic\":\""+PIN+"\"}";
  Files.writeString(Path.of(args[3]),report+"\n");System.out.println(report);
 }
}
