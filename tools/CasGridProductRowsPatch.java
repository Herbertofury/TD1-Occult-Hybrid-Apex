// Private exact owned-helper continuation. Native bodies remain byte-for-byte.
import java.nio.file.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;

public class CasGridProductRowsPatch {
 static final String GRID="olympus.layout.RecyclingGridLayout",LOADER="olympus.resources.ImageLoader",IMAGE="olympus.controls.ImageResource";
 static final List<String> REPLACED=List.of("ApexGridBind","ApexGridReady");
 static final List<String> ADDED=List.of();
 static final Map<String,String> PINS=Map.ofEntries(
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridBind","7c09ed952c63af76fe80edd1cfa205f7ec45b4f06f7df90692f7125f40e48516"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridReady","9db97e67c8e8cd5ee9c1d65c0889d379f8cd232f69a50c3140107f037828d2b4")
 );
 static void check(boolean v,String message){CasStructuralRolesPatch.check(v,message);}
 static String name(ABC a,int n){return CasStructuralRolesPatch.name(a,n);}
 static TraitMethodGetterSetter trait(ABC a,String type,String method){return CasStructuralRolesPatch.trait(a,type,method,false);}
 static MethodBody body(ABC a,String type,String method){return a.findBody(trait(a,type,method).method_info);}
 static String sha(byte[] raw)throws Exception{return CasStructuralRolesPatch.sha(raw);}
 static List<String> types(String mode){return mode.equals("image")?List.of(LOADER,IMAGE):List.of(GRID);}
 static List<String> added(String mode,String type){return mode.equals("image")?List.of("ApexImageReadyFor"):ADDED;}
 static List<String> replaced(String mode){return mode.equals("image")?List.of():REPLACED;}
 static List<String> owned(String mode,String type){var names=new ArrayList<String>(replaced(mode));names.addAll(added(mode,type));return names;}
 static String semantic(ABC a,MethodBody b)throws Exception{
  String text=CasCommunicationIndexPatch.semanticText(a,b);
  for(String simple:List.of("RecyclingGridLayout","ImageLoader","ImageResource"))
   text=text.replaceAll("(?<=5:)"+java.util.regex.Pattern.quote(simple+".as$")+"[0-9]+",simple+".as\\$SELF");
  // Only owned debug-source absolute offsets are irrelevant; executable
  // operands, relative debug gaps, exception edges and native fields stay exact.
  int base=Integer.MAX_VALUE;
  for(var op:b.getCode().code)if(CasStructuralRolesPatch.op(op)==0xef&&op.operands.length==4&&op.operands[0]==1&&op.operands[3]>0)base=Math.min(base,op.operands[3]);
  if(base!=Integer.MAX_VALUE){final int start=base;text=java.util.regex.Pattern.compile("(?m)^(239:1:.*:[0-9]+):([1-9][0-9]*)$").matcher(text).replaceAll(m->m.group(1)+":owned-source+"+(Integer.parseInt(m.group(2))-start));}
  return sha(text.getBytes(java.nio.charset.StandardCharsets.UTF_8));
 }
 static void helpers(ABC a,String mode)throws Exception{
  for(String type:types(mode))for(String method:owned(mode,type)){
   var t=trait(a,type,method);var b=body(a,type,method);
   check(semantic(a,b).equals(PINS.get(type+"/"+method)),"Reviewed presentation helper semantic/CFG differs: "+type+"/"+method);
   // FFDec materializes Publish's reviewed catch scope as one local activation;
   // its ten slots and exact exception CFG are included in the semantic pin.
   // Existing replaced flags are separately required by sameAbi below.
   if(added(mode,type).contains(method)) {
    int expectedFlags=method.equals("ApexGridPresentationPublish")?2:0;
    check(a.method_info.get(t.method_info).flags==expectedFlags,"Presentation helper flags differ: "+method);
    check(b.traits.traits.size()==(expectedFlags==2?10:0)&&b.exceptions.length==(expectedFlags==2?1:0),"Presentation local activation/catch shape differs: "+method);
   }
   for(var op:b.getCode().code)check(!Set.of(0x40,0x43,0x44,0x67).contains(CasStructuralRolesPatch.op(op)),"Presentation helper has nested/outer/callmethod linkage: "+method);
   if(added(mode,type).contains(method)){
    var q=a.constants.getMultiname(t.name_index);var ns=a.constants.getNamespace(q.namespace_index);
    check(t.kindType==Trait.TRAIT_METHOD&&q.kind==Multiname.QNAME,"Presentation method trait kind differs");
    check(mode.equals("image") ? t.kindFlags==1&&ns.kind==Namespace.KIND_PACKAGE&&a.constants.getString(ns.name_index).isEmpty():
     t.kindFlags==0&&ns.kind==Namespace.KIND_PRIVATE&&a.constants.getString(ns.name_index).equals("olympus.layout:RecyclingGridLayout"),"Presentation helper visibility/final namespace differs: "+method);
   }
  }
 }
 static void sameAbi(ABC base,ABC compiled,String type,String n){
  var before=trait(base,type,n);var after=trait(compiled,type,n);
  check(before.kindType==after.kindType&&before.kindFlags==after.kindFlags,"Owned method/getter kind changed: "+n);
  var a=base.method_info.get(before.method_info);var b=compiled.method_info.get(after.method_info);
  check(a.flags==b.flags&&a.param_types.length==b.param_types.length&&CasCommunicationIndexPatch.qname(base,a.ret_type).equals(CasCommunicationIndexPatch.qname(compiled,b.ret_type)),"Owned method signature differs: "+n);
  for(int i=0;i<a.param_types.length;i++)check(CasCommunicationIndexPatch.qname(base,a.param_types[i]).equals(CasCommunicationIndexPatch.qname(compiled,b.param_types[i])),"Owned parameter type differs: "+n);
 }
 static void binding(ABC base,ABC a,Set<Integer> ids,String mode){
  if(mode.equals("grid")){CasGridPoolPatch.binding(a,ids);return;}
  for(String type:types(mode)){
   var declared=new HashMap<String,Integer>();
   for(var t:base.instance_info.get(base.findClassByName(type)).instance_traits.traits)if(t instanceof TraitSlotConst)declared.put(name(base,t.name_index),t.name_index);
   for(String n:added(mode,type))for(var op:body(a,type,n).getCode().code)if(Set.of(0x66,0x61,0x68).contains(CasStructuralRolesPatch.op(op))){
    String field=name(a,op.operands[0]);if(declared.containsKey(field))check(CasCommunicationIndexPatch.qname(a,op.operands[0]).equals(CasCommunicationIndexPatch.qname(base,declared.get(field))),"Image readiness protected field binding differs: "+field);
   }
  }
 }
 static void verify(ABC base,ABC a,String mode,Map<Integer,String> hashes)throws Exception{
  CasStructuralRolesPatch.prefix(base,a);int count=mode.equals("image")?2:ADDED.size();
  check(a.method_info.size()==base.method_info.size()+count&&a.bodies.size()==base.bodies.size()+count,"Presentation method count differs");
  helpers(a,mode);binding(base,a,hashes.keySet(),mode);
  for(var entry:hashes.entrySet())check(sha(a.findBody(entry.getKey()).getCodeBytes()).equals(entry.getValue()),"Serialized owned presentation body differs");
  for(var b:base.bodies)if(!hashes.containsKey(b.method_info))check(Arrays.equals(b.getCodeBytes(),a.findBody(b.method_info).getCodeBytes()),"Original native/unowned body changed");
  var rollback=CasStructuralRolesPatch.reparse(a);
  for(String type:types(mode)){
   for(String n:replaced(mode))CasStructuralRolesPatch.replace(rollback,body(base,type,n).clone());
   var traits=rollback.instance_info.get(rollback.findClassByName(type)).instance_traits.traits;
   int before=base.instance_info.get(base.findClassByName(type)).instance_traits.traits.size();
   check(traits.size()==before+added(mode,type).size(),"Presentation appended fields or foreign traits");
   while(traits.size()>before)traits.remove(traits.size()-1);
  }
  while(rollback.method_info.size()>base.method_info.size())rollback.method_info.remove(rollback.method_info.size()-1);
  while(rollback.bodies.size()>base.bodies.size())rollback.bodies.remove(rollback.bodies.size()-1);
  rollback.constants=base.constants;rollback.resetMethodIndexing();
  check(Arrays.equals(CasStructuralRolesPatch.save(base),CasStructuralRolesPatch.save(rollback)),"Whole ABC rollback changed native traits/signatures/initializers/bodies");
 }
 public static void main(String[] args)throws Exception{
  if(args.length==3&&args[0].equals("--semantic")){var a=CasStructuralRolesPatch.load(args[2]);for(String type:types(args[1]))for(String n:owned(args[1],type))System.out.println(type+"/"+n+" "+semantic(a,body(a,type,n)));return;}
  check(args.length==5&&Set.of("image","grid").contains(args[0]),"Use mode, dynamically verified previous SWF, compiled source SWF, output ABC, proof");
  String mode=args[0];var base=CasStructuralRolesPatch.load(args[1]);var compiled=CasStructuralRolesPatch.load(args[2]);
  CasStructuralRolesPatch.prefix(base,compiled);helpers(compiled,mode);var a=CasStructuralRolesPatch.reparse(base);a.constants=compiled.constants;
  var hashes=new HashMap<Integer,String>();
  for(String type:types(mode)){
   int index=a.findClassByName(type);check(index==compiled.findClassByName(type),"Compiler moved owner class");
   String anchor=mode.equals("grid")?"ApexGridBind":type.equals(LOADER)?"LoadImage":"OnAddedToStage";
   int delta=body(base,type,anchor).init_scope_depth-body(compiled,type,anchor).init_scope_depth;
   check(delta>=0&&delta<=16,"Presentation lexical scope delta differs");
   for(String n:replaced(mode)){
    sameAbi(base,compiled,type,n);var old=body(base,type,n);var made=body(compiled,type,n).clone();
    made.method_info=old.method_info;made.init_scope_depth+=delta;made.max_scope_depth+=delta;made.setCode(made.getCode());made.setModified();
    CasStructuralRolesPatch.replace(a,made);hashes.put(made.method_info,sha(made.getCodeBytes()));
   }
   for(String n:added(mode,type)){
    check(base.instance_info.get(index).instance_traits.traits.stream().noneMatch(t->name(base,t.name_index).equals(n)),"Readiness/presentation helper already present");
    var source=body(compiled,type,n);int id=a.method_info.size();a.method_info.add(compiled.method_info.get(source.method_info));
    var made=source.clone();made.method_info=id;made.init_scope_depth+=delta;made.max_scope_depth+=delta;made.setCode(made.getCode());made.setModified();a.bodies.add(made);
    var t=trait(compiled,type,n).clone();t.method_info=id;t.disp_id=0;a.instance_info.get(index).instance_traits.traits.add(t);hashes.put(id,sha(made.getCodeBytes()));
   }
  }
  a.resetMethodIndexing();verify(base,a,mode,hashes);a=CasStructuralRolesPatch.reparse(a);verify(base,a,mode,hashes);
  byte[] output=CasStructuralRolesPatch.save(a);Files.write(Path.of(args[3]),output);
  String proof="{\"ok\":true,\"mode\":\""+mode+"\",\"baseline_swf_sha256\":\""+sha(Files.readAllBytes(Path.of(args[1])))+"\",\"baseline_abc_sha256\":\""+sha(CasStructuralRolesPatch.save(base))+"\",\"abc_sha256\":\""+sha(output)+"\",\"replaced_owned_bodies\":"+replaced(mode).size()+",\"appended_methods\":"+(mode.equals("image")?2:ADDED.size())+",\"appended_fields\":0,\"changed_original_native_bodies\":0,\"whole_abc_rollback_verified\":true,\"serialized_owned_bodies_verified\":true,\"all_unowned_bodies_retained\":true,\"native_protected_bindings_verified\":true,\"runtime_qualified\":false,\"hitch_free_claimed\":false}";
  Files.writeString(Path.of(args[4]),proof+"\n");System.out.println(proof);
 }
}
