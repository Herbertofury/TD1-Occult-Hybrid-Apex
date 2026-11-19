// Private exact owned continuation. No native/constructor/click body enters it.
import java.nio.file.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;

public class CasCatalogAuthorityPatch {
 static final String GRID="olympus.layout.RecyclingGridLayout",MAIN="widgets.CAS.Customizer.CASCustomizerMain";
 static final List<String> GRID_REPLACED=List.of("ApexGridMetrics");
 static final List<String> GRID_ADDED=List.of("ApexGridExpireMeasurement","ApexGridFrameStatusEffects","ApexGridBeginFrame","ApexGridPendingFrame","ApexGridGeometryFrame");
 static final Map<String,String> PINS=Map.ofEntries(
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridPrepare","dca3d1dd0a32a91834179067158e4838069fd233f39dee7fe2b3c31857b991dc"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridFrame","3a9e5b9122a0b9ac8b9e4073a4e00f4bca5178857e0d78e8c72a485f67400bab"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridInvalidate","f3000172dbbb038380ca505762c23ceb13ad8cfbbed4d4e0a1c489e8a52a62d4"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridChanged","9c88997c2d1ec9f9adcb0fb00590307ac92626df36738613f5b61053c0a0fe5f"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridInput","91c237c015e8e7698c352d3f4bde2a54e08bf0a2896c59d3cd5af0b6888d4df4"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridPending","f261fc1e41126264b37ea2f7dd7d25ef0d87a901dc3e4fe5e55406a80cde210b"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridStatus","3a76b89fcbb8d2ba6ea1a1960c2477c01b9a643ee59a18e9bd457cb77ed90d1b"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridRetireInactive","af126c7e56d39ee7f920217998052ed02438fcb1d8023b88585024b19e1a9976"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridOwns","4f5f473a2d22ab4192722875baf04aebd1cc014049c9a9db5a9a8f996ac89150"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridDispose","ee57790b33f9e9221d9ed73eb2f6c09c6cc2533c12420e653861b2b3900818b0"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCardApply","17a52e09a379333df01adacf0f36e13ec775e8ef8b5a93f0ff79d642b83bed01"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCardIncrementalApply","6e8e9c257d5a11930a87b1f73be24ff06cc4eef09bd916e62bdeab5753150e88"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogFrame","5aa73c1d4a22d9e61a9d0881a0e486d1ee8cf635fdb872238cb5d183e7773e61"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCardRestore","aef9906aa69bae8c78fd3baa60a7c0f03696c6f3024c84901f62db51df47f424"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogSelection","c85a4223f386f49c7507dcbd5516647c2d9e12d8e32d3d024cf1bc5bb8078974"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogClearEffects","5f4d81d8f80ed12063d4d1a6022a43922b74ddfb0a1ae2bc98826dc008dd0c63"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogAuthorityScope","1e4c637fabd7fced84ecfd5e3ed3d0b34d6ef3e8134fb9113d53ee7f0bbf67fd"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogAuthorityEqual","b749a431eb17ff84ffb59a78c1cb560d2907fc0c9ad185eef48631f380b3b0f9"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogAuthorityAvailable","64cdc8d44823d8ed7bb64c91970fef8f25fd827eb90ec9efae6c4f85a89100df"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogAuthorityRemember","b2577dc48ec993d8b6c037169d3636b39a3cc8805f4ce2da043eb7c2f106937c"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogAuthorityHeld","5dbfff1f323437bb2887a25cc97325dcda73d9d2be075aca2fde82f65203f9f0"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogAuthorityEffectHeld","7a4c19703462153fb248594c3b3443096c528a3d49c2870ee3d50afcb0f00b2f"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogAuthorityHold","ff3d6c185c7debc9f733f69c4aab543805b16c451b1c93b046dd86db99e474ca"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogAuthorityRecover","ff3863d3b104291e1009a897d8d8236af9e369bada8b77734f23de7be5e10799")
 );
 static final Map<String,Integer> FLAGS=Map.ofEntries(
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridPrepare",0),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridFrame",10),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridInvalidate",0),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridChanged",8),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridInput",2),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridPending",0),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridStatus",0),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridRetireInactive",0),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridOwns",0),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridDispose",2),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCardApply",2),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCardIncrementalApply",2),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogFrame",10),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCardRestore",2),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogSelection",0),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogClearEffects",0),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogAuthorityScope",0),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogAuthorityEqual",0),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogAuthorityAvailable",0),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogAuthorityRemember",0),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogAuthorityHeld",0),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogAuthorityEffectHeld",0),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogAuthorityHold",0),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogAuthorityRecover",2)
 );
 static void check(boolean v,String message){CasStructuralRolesPatch.check(v,message);}
 static String name(ABC a,int n){return CasStructuralRolesPatch.name(a,n);}
 static TraitMethodGetterSetter trait(ABC a,String type,String method){return CasStructuralRolesPatch.trait(a,type,method,false);}
 static MethodBody body(ABC a,String type,String method){return a.findBody(trait(a,type,method).method_info);}
 static String sha(byte[] raw)throws Exception{return CasStructuralRolesPatch.sha(raw);}
 static String owner(String mode){check(mode.equals("main"),"Exact Main authority consumer mode required");return MAIN;}
 static List<String> replaced(String mode){return List.of("ApexCatalogGridPrepare","ApexCatalogGridFrame","ApexCatalogGridInvalidate","ApexCatalogGridChanged","ApexCatalogGridInput","ApexCatalogGridPending","ApexCatalogGridStatus","ApexCatalogGridRetireInactive","ApexCatalogGridOwns","ApexCatalogGridDispose","ApexCardApply","ApexCardIncrementalApply","ApexCatalogFrame","ApexCardRestore","ApexCatalogSelection","ApexCatalogClearEffects");}
 static List<String> added(String mode){return List.of("ApexCatalogAuthorityScope","ApexCatalogAuthorityEqual","ApexCatalogAuthorityAvailable","ApexCatalogAuthorityRemember","ApexCatalogAuthorityHeld","ApexCatalogAuthorityEffectHeld","ApexCatalogAuthorityHold","ApexCatalogAuthorityRecover");}
 static List<String> owned(String mode){var names=new ArrayList<String>(replaced(mode));names.addAll(added(mode));return names;}
 static String semantic(ABC a,MethodBody b)throws Exception{
  String text=CasCommunicationIndexPatch.semanticText(a,b);
  for(String simple:List.of("RecyclingGridLayout","CASCustomizerMain"))text=text.replaceAll("(?<=5:)"+java.util.regex.Pattern.quote(simple+".as$")+"[0-9]+",simple+".as\\$SELF");
  int start=Integer.MAX_VALUE;
  for(var op:b.getCode().code)if(CasStructuralRolesPatch.op(op)==0xef&&op.operands.length==4&&op.operands[0]==1&&op.operands[3]>0)start=Math.min(start,op.operands[3]);
  if(start!=Integer.MAX_VALUE){final int origin=start;text=java.util.regex.Pattern.compile("(?m)^(239:1:.*:[0-9]+):([1-9][0-9]*)$").matcher(text).replaceAll(m->m.group(1)+":owned-source+"+(Integer.parseInt(m.group(2))-origin));}
  return sha(text.getBytes(java.nio.charset.StandardCharsets.UTF_8));
 }
 static void helpers(ABC a,String mode)throws Exception{
  String type=owner(mode);boolean qname=false;
  for(String n:owned(mode)){
   var t=trait(a,type,n);var b=body(a,type,n);var info=a.method_info.get(t.method_info);
   check(semantic(a,b).equals(PINS.get(type+"/"+n)),"Reviewed authority consumer semantic/CFG differs: "+n);
   check(info.flags==FLAGS.get(type+"/"+n),"Reviewed method flags differ: "+n);
   for(var op:b.getCode().code){int code=CasStructuralRolesPatch.op(op);check(!Set.of(0x40,0x43,0x44,0x67).contains(code),"Nested/outer/callmethod linkage: "+n);
    if(Set.of(0x60,0x46,0x4f).contains(code)&&op.operands.length>0&&name(a,op.operands[0]).equals("getQualifiedClassName")){
     check(CasCommunicationIndexPatch.qname(a,op.operands[0]).equals("7:getQualifiedClassName:22:flash.utils"),"Real exact runtime class getter QName required");qname=true;
    }
    if(code==0x60&&name(a,op.operands[0]).equals("flash"))throw new IllegalStateException("Unbound flash package lookup");
   }
   if(added(mode).contains(n)){
    var q=a.constants.getMultiname(t.name_index);var ns=a.constants.getNamespace(q.namespace_index);
    check(t.kindType==Trait.TRAIT_METHOD&&t.kindFlags==(mode.equals("grid")&&Set.of("ApexGridBeginFrame","ApexGridPendingFrame","ApexGridGeometryFrame").contains(n)?Trait.ATTR_Final:0)&&q.kind==Multiname.QNAME&&ns.kind==(mode.equals("grid")&&Set.of("ApexGridBeginFrame","ApexGridPendingFrame","ApexGridGeometryFrame").contains(n)?Namespace.KIND_PACKAGE:Namespace.KIND_PRIVATE)&&a.constants.getString(ns.name_index).equals(mode.equals("grid")&&Set.of("ApexGridBeginFrame","ApexGridPendingFrame","ApexGridGeometryFrame").contains(n)?"":mode.equals("grid")?"olympus.layout:RecyclingGridLayout":"widgets.CAS.Customizer:CASCustomizerMain"),"Appended private method namespace/kind differs");
    check(info.optional.length==0,"No new optional callable defaults");
   }
  }
  check(!mode.equals("main")||qname,"Native runtime class proof getter absent");
 }
 static void sameAbi(ABC base,ABC compiled,String type,String n){
  var before=trait(base,type,n);var after=trait(compiled,type,n);var a=base.method_info.get(before.method_info);var b=compiled.method_info.get(after.method_info);
  check(before.kindType==after.kindType&&before.kindFlags==after.kindFlags&&a.flags==b.flags&&a.param_types.length==b.param_types.length&&a.optional.length==b.optional.length&&CasCommunicationIndexPatch.qname(base,a.ret_type).equals(CasCommunicationIndexPatch.qname(compiled,b.ret_type)),"Existing callable ABI differs: "+n);
  for(int i=0;i<a.param_types.length;i++)check(CasCommunicationIndexPatch.qname(base,a.param_types[i]).equals(CasCommunicationIndexPatch.qname(compiled,b.param_types[i])),"Existing parameter differs: "+n);
  for(int i=0;i<a.optional.length;i++)check(a.optional[i].value_kind==b.optional[i].value_kind&&a.optional[i].value_index==b.optional[i].value_index,"Existing optional default differs: "+n);
 }
 static void binding(ABC base,ABC a,String mode,Set<Integer> ids){
  if(mode.equals("grid")){CasGridPoolPatch.binding(a,ids);return;}
  var fields=new HashMap<String,Integer>();for(var t:base.instance_info.get(base.findClassByName(MAIN)).instance_traits.traits)if(t instanceof TraitSlotConst)fields.put(name(base,t.name_index),t.name_index);
  for(String n:owned(mode))for(var op:body(a,MAIN,n).getCode().code)if(Set.of(0x66,0x61,0x68).contains(CasStructuralRolesPatch.op(op))){String f=name(a,op.operands[0]);if(fields.containsKey(f))check(CasCommunicationIndexPatch.qname(a,op.operands[0]).equals(CasCommunicationIndexPatch.qname(base,fields.get(f))),"Main field binding differs: "+f);}
 }
 static void verify(ABC base,ABC a,String mode,Map<Integer,String> hashes)throws Exception{
  String type=owner(mode);int count=added(mode).size();CasStructuralRolesPatch.prefix(base,a);helpers(a,mode);binding(base,a,mode,hashes.keySet());
  check(a.method_info.size()==base.method_info.size()+count&&a.bodies.size()==base.bodies.size()+count,"Only exact appended method/body count permitted");
  for(var e:hashes.entrySet())check(sha(a.findBody(e.getKey()).getCodeBytes()).equals(e.getValue()),"Serialized owned body differs");
  for(var b:base.bodies)if(!hashes.containsKey(b.method_info))check(Arrays.equals(b.getCodeBytes(),a.findBody(b.method_info).getCodeBytes()),"Original native/unowned body differs");
  var rollback=CasStructuralRolesPatch.reparse(a);for(String n:replaced(mode))CasStructuralRolesPatch.replace(rollback,body(base,type,n).clone());
  var traits=rollback.instance_info.get(rollback.findClassByName(type)).instance_traits.traits;int old=base.instance_info.get(base.findClassByName(type)).instance_traits.traits.size();
  check(traits.size()==old+count,"No new field or foreign trait permitted");while(traits.size()>old)traits.remove(traits.size()-1);
  while(rollback.method_info.size()>base.method_info.size())rollback.method_info.remove(rollback.method_info.size()-1);
  while(rollback.bodies.size()>base.bodies.size())rollback.bodies.remove(rollback.bodies.size()-1);
  rollback.constants=base.constants;rollback.resetMethodIndexing();check(Arrays.equals(CasStructuralRolesPatch.save(base),CasStructuralRolesPatch.save(rollback)),"Complete raw ABC rollback differs");
 }
 public static void main(String[] args)throws Exception{
  if(args.length==3&&args[0].equals("--semantic")){String mode=args[1],type=owner(mode);var a=CasStructuralRolesPatch.load(args[2]);for(String n:owned(mode)){var b=body(a,type,n);System.out.println(type+"/"+n+" "+semantic(a,b)+" "+a.method_info.get(b.method_info).flags+" scope="+b.init_scope_depth+" exceptions="+b.exceptions.length+" activation="+b.traits.traits.size());}return;}
  check(args.length==5,"Mode, exact previous SWF, compiled SWF, output ABC, proof required");String mode=args[0],type=owner(mode);var base=CasStructuralRolesPatch.load(args[1]);var compiled=CasStructuralRolesPatch.load(args[2]);
  CasStructuralRolesPatch.prefix(base,compiled);helpers(compiled,mode);var a=CasStructuralRolesPatch.reparse(base);a.constants=compiled.constants;var hashes=new HashMap<Integer,String>();int index=a.findClassByName(type);check(index==compiled.findClassByName(type),"Compiler moved owner class");
  String anchor=mode.equals("grid")?"ApexTxnStep":"ApexCatalogGridRequest";int delta=body(base,type,anchor).init_scope_depth-body(compiled,type,anchor).init_scope_depth;check(delta>=0&&delta<=16,"Lexical scope adjustment differs");
  for(String n:replaced(mode)){sameAbi(base,compiled,type,n);var old=body(base,type,n);var made=body(compiled,type,n).clone();made.method_info=old.method_info;made.init_scope_depth+=delta;made.max_scope_depth+=delta;made.setCode(made.getCode());made.setModified();CasStructuralRolesPatch.replace(a,made);hashes.put(made.method_info,sha(made.getCodeBytes()));}
  for(String n:added(mode)){check(base.instance_info.get(index).instance_traits.traits.stream().noneMatch(t->name(base,t.name_index).equals(n)),"Added method already present");var source=body(compiled,type,n);int id=a.method_info.size();a.method_info.add(compiled.method_info.get(source.method_info));var made=source.clone();made.method_info=id;made.init_scope_depth+=delta;made.max_scope_depth+=delta;made.setCode(made.getCode());made.setModified();a.bodies.add(made);var t=trait(compiled,type,n).clone();t.method_info=id;t.disp_id=0;a.instance_info.get(index).instance_traits.traits.add(t);hashes.put(id,sha(made.getCodeBytes()));}
  a.resetMethodIndexing();verify(base,a,mode,hashes);a=CasStructuralRolesPatch.reparse(a);verify(base,a,mode,hashes);byte[] out=CasStructuralRolesPatch.save(a);Files.write(Path.of(args[3]),out);
  String proof="{\"ok\":true,\"mode\":\""+mode+"\",\"replaced_owned_bodies\":"+replaced(mode).size()+",\"appended_methods\":"+added(mode).size()+",\"appended_fields\":0,\"changed_original_native_bodies\":0,\"whole_abc_rollback_verified\":true,\"all_unowned_bodies_retained\":true,\"serialized_owned_bodies_verified\":true,\"native_protected_bindings_verified\":true,\"runtime_class_QName_verified\":"+mode.equals("main")+",\"baseline_swf_sha256\":\""+sha(Files.readAllBytes(Path.of(args[1])))+"\",\"baseline_abc_sha256\":\""+sha(CasStructuralRolesPatch.save(base))+"\",\"abc_sha256\":\""+sha(out)+"\",\"runtime_qualified\":false,\"performance_gain_claimed\":false}";
  Files.writeString(Path.of(args[4]),proof+"\n");System.out.println(proof);
 }
}
