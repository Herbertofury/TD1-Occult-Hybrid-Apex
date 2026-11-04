// Private exact owned-helper continuation. Native bodies remain byte-for-byte.
import java.nio.file.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;

public class CasGridPresentationPatch {
 static final String GRID="olympus.layout.RecyclingGridLayout",LOADER="olympus.resources.ImageLoader",IMAGE="olympus.controls.ImageResource";
 static final List<String> REPLACED=List.of("ApexGridCells","ApexGridCellsY","ApexGridMap","ApexGridBegin","ApexGridMetrics",
  "ApexGridGate","ApexGridPoolPark","ApexGridBind","ApexGridReady","ApexGridPublish","ApexGridAbort","ApexTxnPlan","ApexTxnAdvance");
 static final List<String> ADDED=List.of("ApexGridPresentationStart","ApexGridPresentationWatch","ApexGridPresentationFailed",
  "ApexGridPresentationBound","ApexGridPresentationTexture","ApexGridPresentationRollback","ApexGridPresentationPublish");
 static final Map<String,String> PINS=Map.ofEntries(
 Map.entry("olympus.controls.ImageResource/ApexImageReadyFor","d4b7516953e8b99f473955922f5f20091ece0152cb55bd3d39e64c07963c1098"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridAbort","7890e30370e22bffa62d9d0b795c336beb2c35a71c7b618bc2611cd08bb9a679"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridBegin","19e4d7563a667fbffe6cdea9a7a27fe384742781a1bd8a82bf64f9c5e4165bd9"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridBind","1b8fc616ce8d2610f9bd520091714c8a65ebd47c9bcb254d01fb381563da7562"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridCells","40084dceee1c0dc75bbb0ccfc6afcaf0e6ff5213d24081c9cc2a30a63629691b"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridCellsY","15240a7a1cf9558a56c9545c09c1f65b9aabcb7af64e25e9a2d3962f110f9910"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridGate","9d3d0ff6b33bffc85ee9b3a0db4ad014a4bf40a4dc0e00949f32703bf2ce1978"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridMap","f1df2ec97f9630dcc35004733590d56493c461311e2d90f2efa53f0a77534106"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridMetrics","7d96221603e76e101b2761c3ddee4baeef5f7a905ec578fd2319a35280892f48"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridPoolPark","d3fbb356fc2f667ed561f58adca7d352771639d45f49942388a462ed630090c0"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridPresentationBound","07854b1ef96eec9637adc62ef0d463e7d01373e6b45c15ecc04bc0480c72d916"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridPresentationFailed","81003060856b6417d0cb70eaf6262d5652f3ef12601cae88361e54a7810f935b"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridPresentationPublish","de85d1f0a7baf422fbba8fe08c6fafb639960167af2e26fae8d8309697cc9f4f"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridPresentationRollback","1fc369599ac529ea80a52e80c35e4c70af9b09213d8dec77dafb0f7a324af474"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridPresentationStart","6ffad3695b8c6b0e24a51bd5061cbf54e8bdda8da1a000d14896e00ad3adeb1e"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridPresentationTexture","4efbd10a8b805dae1e78ed37ec66ae169ee46b3dcdb0d47de4dc0e07135e1626"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridPresentationWatch","980621913f892224186dcc1d5eaa7baab603e057131d26f8549f70b982248f15"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridPublish","20cb0552c37723b9524e57c11990ccc05512886f31c30473ad880b4359a98e09"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridReady","a976abc89cc26b2567efd88965de31bec366b1dd30d228b0a3108dda7b8f5642"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexTxnAdvance","c492a6822fabbede205b4325ab3dad5fd96dec8124c924ad470681454a51f6dd"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexTxnPlan","6ab6256e0e4512691cadbc77a3641faf89d017f64f3656021c7add22e96482ed"),
 Map.entry("olympus.resources.ImageLoader/ApexImageReadyFor","f90cb087ee0ec8f9e4aacd1a009d3c5783f0603e0aa254793ee910aae7c00f86")
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
