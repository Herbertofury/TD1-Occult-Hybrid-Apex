// Private opt-in diagnostics only: original native bodies/traits remain exact.
import java.nio.file.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;

public class CasPublicationTracePatch {
 static final String GRID="olympus.layout.RecyclingGridLayout", MAIN="widgets.CAS.Customizer.CASCustomizerMain";
 static final Map<String,String> PINS=Map.ofEntries(
  Map.entry(GRID+"/ApexTxnAdvance","794570f04c32b919a8fc13f388a64333a8f982a0ac1b7cc18c71415701904c87"),
  Map.entry(GRID+"/ApexGridPresentationPublish","a40e163ae519463ddd827909c1c6ff1d1c299aad274b2d68677d33425bc416f6"),
  Map.entry(GRID+"/ApexGridPublicationTrace","82f338e8f4abadb5af7a68dc025baf2e7e54a7eb2540412f1a17adb75cac6ead"),
  Map.entry(MAIN+"/ApexCatalogGridRequest","f2bbf1a9bc36d2813cef51d31d1f1dc17ea24975309ba38694911eed0df49593"),
  Map.entry(MAIN+"/ApexCatalogTraceStatus","7b9f43ebfdd4e9b8a7ecf8a0cc5595afb7c8ac6a476a053599f5cb52a93c7c6f"),
  Map.entry(MAIN+"/ApexCatalogPublicationTraceStep","10054a10822fabb4aba0366fa5e4707a2b6514c7daf9ec627dc7a2b6ced5a32a")
 );
 static String owner(String mode){return mode.equals("grid")?GRID:MAIN;}
 static List<String> replaced(String mode){return mode.equals("grid")?List.of("ApexTxnAdvance","ApexGridPresentationPublish"):List.of("ApexCatalogGridRequest","ApexCatalogTraceStatus");}
 static String added(String mode){return mode.equals("grid")?"ApexGridPublicationTrace":"ApexCatalogPublicationTraceStep";}
 static List<String> owned(String mode){var n=new ArrayList<String>(replaced(mode));n.add(added(mode));return n;}
 static void check(boolean v,String s){CasStructuralRolesPatch.check(v,s);}
 static String sha(byte[] b)throws Exception{return CasStructuralRolesPatch.sha(b);}
 static TraitMethodGetterSetter trait(ABC a,String mode,String n){return CasStructuralRolesPatch.trait(a,owner(mode),n,false);}
 static MethodBody body(ABC a,String mode,String n){return a.findBody(trait(a,mode,n).method_info);}
 static String semantic(ABC a,MethodBody b)throws Exception {
  String text=CasCommunicationIndexPatch.semanticText(a,b);
  for(String name:List.of("RecyclingGridLayout","CASCustomizerMain"))text=text.replaceAll("(?<=5:)"+java.util.regex.Pattern.quote(name+".as$")+"[0-9]+",name+".as\\$SELF");
  int first=Integer.MAX_VALUE;
  for(var i:b.getCode().code)if(CasStructuralRolesPatch.op(i)==0xef&&i.operands.length==4&&i.operands[0]==1&&i.operands[3]>0)first=Math.min(first,i.operands[3]);
  if(first!=Integer.MAX_VALUE){final int start=first;text=java.util.regex.Pattern.compile("(?m)^(239:1:.*:[0-9]+):([1-9][0-9]*)$").matcher(text).replaceAll(m->m.group(1)+":owned-source+"+(Integer.parseInt(m.group(2))-start));}
  return sha(text.getBytes(java.nio.charset.StandardCharsets.UTF_8));
 }
 static void helpers(ABC a,String mode)throws Exception {
  for(String n:owned(mode)){
   var t=trait(a,mode,n);var b=body(a,mode,n);var q=a.constants.getMultiname(t.name_index);var ns=a.constants.getNamespace(q.namespace_index);
   check(semantic(a,b).equals(PINS.get(owner(mode)+"/"+n)),"Exact publication diagnostic semantic/CFG differs: "+n);
   check(t.kindType==Trait.TRAIT_METHOD&&t.kindFlags==0&&q.kind==Multiname.QNAME&&ns.kind==Namespace.KIND_PRIVATE&&a.constants.getString(ns.name_index).equals(mode.equals("grid")?"olympus.layout:RecyclingGridLayout":"widgets.CAS.Customizer:CASCustomizerMain"),"Exact private owned trait namespace differs: "+n);
   if(n.equals(added(mode))){
    var info=a.method_info.get(t.method_info);
    check(info.flags==2&&info.optional.length==0&&info.paramNames.length==info.param_types.length&&Arrays.stream(info.paramNames).allMatch(v->v==0),"Diagnostic helper activation/optional ABI differs");
    check(b.exceptions.length==(mode.equals("grid")?1:2)&&b.traits.traits.size()==(mode.equals("grid")?5:22),"Exact diagnostic activation/catch inventory differs");
   }
   int clocks=0;
   for(var i:b.getCode().code){int op=CasStructuralRolesPatch.op(i);
    check(!Set.of(0x40,0x43,0x44,0x67).contains(op),"Foreign nested/callmethod/outer dependency: "+n);
    if(Set.of(0x5d,0x60,0x66).contains(op)){String leaf=CasStructuralRolesPatch.name(a,i.operands[0]);check(leaf==null||!Set.of("flash","widgets","olympus","gamedata").contains(leaf),"Unresolved runtime package chain: "+n);}
    if(Set.of(0x5d,0x46,0x4f).contains(op)&&CasStructuralRolesPatch.name(a,i.operands[0]).equals("getTimer")){
     check(CasCommunicationIndexPatch.qname(a,i.operands[0]).equals("7:getTimer:22:flash.utils"),"Timer must be native flash.utils QName");
     if(op!=0x5d){check(i.operands[1]==0,"Native clock arguments differ");clocks++;}
    }
   }
   check(clocks==(mode.equals("main")&&!n.equals("ApexCatalogGridRequest")?1:0),"Default provider/request diagnostics introduced a clock: "+n);
  }
 }
 static void abi(ABC base,ABC compiled,String mode,String n){
  var a=trait(base,mode,n);var b=trait(compiled,mode,n);check(a.kindType==b.kindType&&a.kindFlags==b.kindFlags,"Owned trait kind differs");
  var x=base.method_info.get(a.method_info);var y=compiled.method_info.get(b.method_info);
  check(x.flags==y.flags&&x.param_types.length==y.param_types.length&&x.optional.length==y.optional.length&&CasCommunicationIndexPatch.qname(base,x.ret_type).equals(CasCommunicationIndexPatch.qname(compiled,y.ret_type)),"Owned callable ABI differs: "+n);
  for(int k=0;k<x.param_types.length;k++)check(CasCommunicationIndexPatch.qname(base,x.param_types[k]).equals(CasCommunicationIndexPatch.qname(compiled,y.param_types[k])),"Owned parameter type differs");
 }
 static void binding(ABC base,ABC a,String mode,Set<Integer> ids){
  if(mode.equals("grid")){CasGridPoolPatch.binding(a,ids);return;}
  var slots=new HashMap<String,Integer>();
  for(var t:base.instance_info.get(base.findClassByName(MAIN)).instance_traits.traits)if(t instanceof TraitSlotConst)slots.put(CasStructuralRolesPatch.name(base,t.name_index),t.name_index);
  for(int id:ids)for(var i:a.findBody(id).getCode().code)if(Set.of(0x5d,0x60,0x61,0x66,0x68).contains(CasStructuralRolesPatch.op(i))){
   String n=CasStructuralRolesPatch.name(a,i.operands[0]);
   if(slots.containsKey(n))check(CasCommunicationIndexPatch.qname(a,i.operands[0]).equals(CasCommunicationIndexPatch.qname(base,slots.get(n))),"Existing Main private/native slot binding differs: "+n);
   if("CASCustomizerMain".equals(n))check(CasCommunicationIndexPatch.qname(a,i.operands[0]).equals("7:CASCustomizerMain:22:widgets.CAS.Customizer"),"Actual Main class QName differs");
  }
 }
 static void verify(ABC base,ABC a,String mode,Map<Integer,String> hashes)throws Exception {
  CasStructuralRolesPatch.prefix(base,a);helpers(a,mode);binding(base,a,mode,hashes.keySet());
  check(a.method_info.size()==base.method_info.size()+1&&a.bodies.size()==base.bodies.size()+1,"Exactly one diagnostic method may be appended");
  for(var e:hashes.entrySet())check(sha(a.findBody(e.getKey()).getCodeBytes()).equals(e.getValue()),"Serialized diagnostic body differs");
  for(var b:base.bodies)if(!hashes.containsKey(b.method_info))check(Arrays.equals(b.getCodeBytes(),a.findBody(b.method_info).getCodeBytes()),"Unowned native/predecessor body differs");
  var rollback=CasStructuralRolesPatch.reparse(a);
  for(String n:replaced(mode))CasStructuralRolesPatch.replace(rollback,body(base,mode,n).clone());
  var traits=rollback.instance_info.get(rollback.findClassByName(owner(mode))).instance_traits.traits;
  check(traits.size()==base.instance_info.get(base.findClassByName(owner(mode))).instance_traits.traits.size()+1,"Added field/foreign trait refused");
  check(traits.get(traits.size()-1) instanceof TraitMethodGetterSetter&&CasStructuralRolesPatch.name(rollback,traits.get(traits.size()-1).name_index).equals(added(mode)),"New diagnostic is not final appended trait");traits.remove(traits.size()-1);
  rollback.method_info.remove(rollback.method_info.size()-1);rollback.bodies.remove(rollback.bodies.size()-1);rollback.constants=base.constants;rollback.resetMethodIndexing();
  check(Arrays.equals(CasStructuralRolesPatch.save(base),CasStructuralRolesPatch.save(rollback)),"Whole ABC rollback changed native initializers/fields/methods/signatures");
 }
 public static void main(String[] args)throws Exception {
  if(args.length==3&&args[0].equals("--semantic")){var a=CasStructuralRolesPatch.load(args[2]);for(String n:owned(args[1]))System.out.println(owner(args[1])+"/"+n+" "+semantic(a,body(a,args[1],n)));return;}
  check(args.length==5&&Set.of("grid","main").contains(args[0]),"Use grid/main, fully verified prior SWF, compiled SWF, output ABC, proof");
  String mode=args[0];var base=CasStructuralRolesPatch.load(args[1]);var compiled=CasStructuralRolesPatch.load(args[2]);CasStructuralRolesPatch.prefix(base,compiled);helpers(compiled,mode);
  var result=CasStructuralRolesPatch.reparse(base);result.constants=compiled.constants;var hashes=new HashMap<Integer,String>();
  String anchor=mode.equals("grid")?"ApexTxnBudgetStep":"ApexCatalogTraceStep";
  int delta=body(base,mode,anchor).init_scope_depth-body(compiled,mode,anchor).init_scope_depth;check(delta>=0&&delta<=16,"Exact diagnostic lexical scope delta differs");
  for(String n:replaced(mode)){
   abi(base,compiled,mode,n);var old=body(base,mode,n);var made=body(compiled,mode,n).clone();made.method_info=old.method_info;made.init_scope_depth+=delta;made.max_scope_depth+=delta;made.setCode(made.getCode());made.setModified();CasStructuralRolesPatch.replace(result,made);hashes.put(made.method_info,sha(made.getCodeBytes()));
  }
  String n=added(mode);var source=body(compiled,mode,n);int id=result.method_info.size();result.method_info.add(compiled.method_info.get(source.method_info));var made=source.clone();made.method_info=id;made.init_scope_depth+=delta;made.max_scope_depth+=delta;made.setCode(made.getCode());made.setModified();
  check(made.init_scope_depth==body(base,mode,anchor).init_scope_depth,"Appended catch helper scope does not match existing catch helper");result.bodies.add(made);
  var t=trait(compiled,mode,n).clone();t.method_info=id;t.disp_id=0;result.instance_info.get(result.findClassByName(owner(mode))).instance_traits.traits.add(t);hashes.put(id,sha(made.getCodeBytes()));
  result.resetMethodIndexing();verify(base,result,mode,hashes);result=CasStructuralRolesPatch.reparse(result);verify(base,result,mode,hashes);
  byte[] out=CasStructuralRolesPatch.save(result);Files.write(Path.of(args[3]),out);
  String report="{\"ok\":true,\"mode\":\""+mode+"\",\"replaced_owned_bodies\":2,\"appended_methods\":1,\"appended_fields\":0,\"changed_original_native_bodies\":0,\"whole_abc_rollback_verified\":true,\"serialized_owned_bodies_verified\":true,\"all_unowned_bodies_retained\":true,\"native_protected_bindings_verified\":true,\"native_clock_QName_verified\":true,\"runtime_qualified\":false,\"performance_gain_claimed\":false,\"baseline_swf_sha256\":\""+sha(Files.readAllBytes(Path.of(args[1])))+"\",\"baseline_abc_sha256\":\""+sha(CasStructuralRolesPatch.save(base))+"\",\"abc_sha256\":\""+sha(out)+"\"}";
  Files.writeString(Path.of(args[4]),report+"\n");System.out.println(report);
 }
}
