// Private exact owned continuation. No native/constructor/click body enters it.
import java.nio.file.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;

public class CasGridWidthPatch {
 static final String GRID="olympus.layout.RecyclingGridLayout",MAIN="widgets.CAS.Customizer.CASCustomizerMain";
 static final List<String> GRID_REPLACED=List.of("ApexTxnRequest","ApexGridNativeGuard","ApexGridNeedsWork","ApexGridMetrics","ApexGridBegin","ApexGridBeginFrame","ApexGridDeltaRestore");
 static final List<String> GRID_ADDED=List.of("ApexGridWidthWake","ApexGridWidthCounters","ApexGridWidthCurrent","ApexGridWidthTry");
 static final Map<String,String> PINS=Map.ofEntries(
 Map.entry("olympus.layout.RecyclingGridLayout/ApexTxnRequest","584182a2652b79c664ce468ddbc96125ea51e614ff6ca573e71fd0e998806ce0"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridNativeGuard","5ae50eadb1751a4ccbe5dc9b3b0ebbecf76e3add6a7a3eb3e894388af202b88d"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridNeedsWork","6fe262f78569cd75968d8c3b584fa996a92daad422485b0b6b7ff24ad82ad00c"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridMetrics","f9ee6c1ce565bdd496e7c8cd1e6f6d5f9f0b55c1d980ddea7339cde5d1b07873"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridBegin","4745a446ea1ea625801eeea5b25b7ed4b34baa2ca8ed1173a501293dc4b10882"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridBeginFrame","90c6fa3c39912ccb136dd877f07086935bfa9357576b9fc6666944164fab4b5d"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaRestore","02cd8a9a1bcb8eda5eec85e511bc9afc3bb0419451fa6737c76016752225e1ce"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridWidthWake","10c770e6bd2d4bcc9bb9dadb2ffec56e7f1ebffab8d548f358b79d76dfe5aff3"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridWidthCounters","dc527504271c1992e8f1afbbd64495942358228680b619caa61954d5c4881aab"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridWidthCurrent","6eece3941170e4277982ea10065aa69ae829128e7a37a5f1d0d55cbfdfcd2e5e"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridWidthTry","fe752a49fcf310b887292045bcab08787cc9fe885bbfe245c7016281a0a62b65"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridRequest","3d1975102d0b9e784546cf9a32fed2bd9e6cdafacb5dad34016fa647e96d0a4f")
 );
 static final Map<String,Integer> FLAGS=Map.ofEntries(
 Map.entry("olympus.layout.RecyclingGridLayout/ApexTxnRequest",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridNativeGuard",8),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridNeedsWork",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridMetrics",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridBegin",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridBeginFrame",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaRestore",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridWidthWake",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridWidthCounters",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridWidthCurrent",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridWidthTry",2),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridRequest",0)
 );
 static void check(boolean v,String message){CasStructuralRolesPatch.check(v,message);}
 static String name(ABC a,int n){return CasStructuralRolesPatch.name(a,n);}
 static TraitMethodGetterSetter trait(ABC a,String type,String method){return CasStructuralRolesPatch.trait(a,type,method,false);}
 static MethodBody body(ABC a,String type,String method){return a.findBody(trait(a,type,method).method_info);}
 static String sha(byte[] raw)throws Exception{return CasStructuralRolesPatch.sha(raw);}
 static String owner(String mode){check(Set.of("grid","main").contains(mode),"Exact width-transfer mode required");return mode.equals("grid")?GRID:MAIN;}
 static List<String> replaced(String mode){return mode.equals("grid")?GRID_REPLACED:List.of("ApexCatalogGridRequest");}
 static List<String> added(String mode){return mode.equals("grid")?GRID_ADDED:List.of();}
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
   check(semantic(a,b).equals(PINS.get(type+"/"+n)),"Reviewed width-transfer semantic/CFG differs: "+n);
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
  check(!qname,"Width-only helpers must not introduce runtime class reflection");
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
  String proof="{\"ok\":true,\"mode\":\""+mode+"\",\"replaced_owned_bodies\":"+replaced(mode).size()+",\"appended_methods\":"+added(mode).size()+",\"appended_fields\":0,\"changed_original_native_bodies\":0,\"whole_abc_rollback_verified\":true,\"all_unowned_bodies_retained\":true,\"serialized_owned_bodies_verified\":true,\"native_protected_bindings_verified\":true,\"runtime_class_QName_verified\":"+false+",\"baseline_swf_sha256\":\""+sha(Files.readAllBytes(Path.of(args[1])))+"\",\"baseline_abc_sha256\":\""+sha(CasStructuralRolesPatch.save(base))+"\",\"abc_sha256\":\""+sha(out)+"\",\"runtime_qualified\":false,\"performance_gain_claimed\":false}";
  Files.writeString(Path.of(args[4]),proof+"\n");System.out.println(proof);
 }
}
