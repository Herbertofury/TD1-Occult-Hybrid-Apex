// Prototype only: forward the first original layer-panel bind with live width.
// All remaining native bind calls and the native binding method remain exact.
import java.nio.file.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;

public class CasCatalogBindingPatch {
 static final String MAIN=CasStructuralRolesPatch.MAIN,ALIGN="HandleAlignToContextMenu",OBSERVE="ApexCatalogObserveBinding",WRAPPER="ApexCatalogNativeBinding",WIDTH="ApexCatalogBindingWidth";
 static final String ALIGN_PIN="f91d35898c71a91be92a16ff09f1b546555b06b7beba929c51f093b729d8da0e",BIND_PIN="86157039c4e2301508bb20948b7ce9322a1a949714060f41a9d3e15220792e38";
 static final List<String> ADDED=List.of(WIDTH,WRAPPER),OWNED=List.of(WIDTH,WRAPPER,OBSERVE);
 static final Map<String,String> SEMANTICS=Map.of(
  WIDTH,"0965b86c3177f8dd81afa0cacaf8b382445f902d4ae1f47765fb7eb6ba6b311d",
  WRAPPER,"a48fd5e6e7e8cf8a8b00fe77ac963f456f2cb6d7cc4a83b7b02f520e400c5554",
  OBSERVE,"43b54c1a09147780d2d03ad17949f95bbdbb0cc4a80b9c21255ea0014b5355f4");
 static final Map<String,String> PROVIDERS=Map.of("5f475a80a4f9c77f9a0439e133221a31f766cb929318f74191b4b9bad98e8cae","canonical","6ddb983fee2bd284a2b7efec155e1544bfe99d27f16d4d28097bada25e1864f0","donor");
 static void check(boolean b,String s){CasStructuralRolesPatch.check(b,s);}
 static String sha(byte[] b)throws Exception{return CasStructuralRolesPatch.sha(b);}
 static int op(AVM2Instruction i){return CasStructuralRolesPatch.op(i);}
 static boolean prop(ABC a,AVM2Instruction i,int o,String n){return CasStructuralRolesPatch.prop(a,i,o,n);}
 static MethodBody body(ABC a,String n){return CasStructuralRolesPatch.body(a,MAIN,n,false);}
 static TraitMethodGetterSetter trait(ABC a,String n){return CasStructuralRolesPatch.trait(a,MAIN,n,false);}
 static String semantic(ABC a,MethodBody b)throws Exception{return sha(CasCommunicationIndexPatch.semanticText(a,b).replaceAll("(?<=5:)CASCustomizerMain\\.as\\$[0-9]+","CASCustomizerMain.as\\$SELF").getBytes(java.nio.charset.StandardCharsets.UTF_8));}
 static void helperSemantics(ABC a)throws Exception {
  check(SEMANTICS.size()==OWNED.size(),"Binding helper semantic inventory is not frozen");
  for(String n:OWNED){check(semantic(a,body(a,n)).equals(SEMANTICS.get(n)),"Reviewed binding helper differs: "+n);var t=trait(a,n);var q=a.constants.getMultiname(t.name_index);var ns=a.constants.getNamespace(q.namespace_index);
   check(q.kind==Multiname.QNAME&&ns.kind==Namespace.KIND_PRIVATE&&a.constants.getString(ns.name_index).equals("widgets.CAS.Customizer:CASCustomizerMain"),"Binding helper is not the class-private method: "+n);
   check(t.kindType==Trait.TRAIT_METHOD&&t.kindFlags==0&&(!ADDED.contains(n)||t.disp_id==0),"Binding helper trait dispatch/kind differs: "+n);
   check(a.method_info.get(t.method_info).optional.length==0,"Binding helper must not add optional arguments");
   check(body(a,n).exceptions.length==0&&body(a,n).traits.traits.isEmpty(),"Binding helper has activation/exception dependencies");}
 }
 static void signature(ABC base,ABC compiled,String name)throws Exception {
  var a=base.method_info.get(trait(base,name).method_info);var b=compiled.method_info.get(trait(compiled,name).method_info);
  check(a.flags==b.flags&&a.param_types.length==b.param_types.length&&a.optional.length==b.optional.length,"Owned observer signature differs");
  check(CasCommunicationIndexPatch.qname(base,a.ret_type).equals(CasCommunicationIndexPatch.qname(compiled,b.ret_type)),"Owned observer return type differs");
  for(int i=0;i<a.param_types.length;i++)check(CasCommunicationIndexPatch.qname(base,a.param_types[i]).equals(CasCommunicationIndexPatch.qname(compiled,b.param_types[i])),"Owned observer argument type differs");
 }
 static void bindings(ABC base,ABC candidate,Set<Integer> methods)throws Exception {
  var nativeNames=new HashMap<String,String>();var instance=base.instance_info.get(base.findClassByName(MAIN));
  for(var t:instance.instance_traits.traits){String name=CasStructuralRolesPatch.name(base,t.name_index);if(t instanceof TraitSlotConst||name.equals("BindDisplayObjectToSim"))nativeNames.put(name,CasCommunicationIndexPatch.qname(base,t.name_index));}
  for(int method:methods)for(var i:candidate.findBody(method).getCode().code)if(Set.of(0x04,0x05,0x45,0x46,0x4e,0x4f,0x5d,0x5e,0x5f,0x60,0x61,0x66,0x68).contains(op(i))){String n=CasStructuralRolesPatch.name(candidate,i.operands[0]);if(nativeNames.containsKey(n))
   check(nativeNames.get(n).equals(CasCommunicationIndexPatch.qname(candidate,i.operands[0])),"Binding helper shadows native/private field: "+n);}
 }
 static void listenerOrder(ABC base)throws Exception {
  var init=body(base,"Initialize").getCode().code;int original=-1,apex=-1;
  for(int i=0;i<init.size();i++){
   if(prop(base,init.get(i),0x66,ALIGN)){check(original<0,"Ambiguous native binding listener");original=i;check(i>=2&&op(init.get(i-2))==0x2c&&base.constants.getString(init.get(i-2).operands[0]).equals("CASBindingSimContextMenu")&&prop(base,init.get(i+1),0x46,"AddMessageListener")&&init.get(i+1).operands[1]==2,"Native binding listener registration changed");}
   if(prop(base,init.get(i),0x4f,"ApexInitialize")){check(apex<0,"Ambiguous Apex initializer");apex=i;}
  }
  check(original>=0&&apex>original,"Apex binding observer does not follow native registration");
  int catalog=0;for(var i:body(base,"ApexInitialize").getCode().code)if(prop(base,i,0x4f,"ApexCatalogInitialize"))catalog++;
  check(catalog==1,"Apex initialize must register the catalogue once");var observer=body(base,"ApexCatalogInitialize").getCode().code;int registered=0;
  for(int i=0;i<observer.size();i++)if(prop(base,observer.get(i),0x60,OBSERVE)){check(i>=1&&op(observer.get(i-1))==0x2c&&base.constants.getString(observer.get(i-1).operands[0]).equals("CASBindingSimContextMenu")&&prop(base,observer.get(i+1),0x46,"AddMessageListener")&&observer.get(i+1).operands[1]==2,"Owned observer registration changed");registered++;}
  check(registered==1,"Owned binding observer must register exactly once");
 }
 static void dispatch(String path,String expected)throws Exception {
  String pin=sha(Files.readAllBytes(Path.of(path)));check(expected.equals(PROVIDERS.get(pin)),"Unpinned native communication provider");var a=CasStructuralRolesPatch.load(path);
  for(String n:List.of("Dispatch","DispatchToWidget")){var b=CasStructuralRolesPatch.body(a,"olympus.io.CommunicationObject",n,false);var code=b.getCode().code;int seen=0;
   for(int i=0;i<code.size();i++)if(prop(a,code.get(i),0x46,"mFunction")){check(i>0&&op(code.get(i-1))==(n.equals("Dispatch")?0xd1:0xd2)&&code.get(i).operands[1]==1,"Native dispatch clones/replaces callback argument");seen++;}
   check(seen==1,"Native dispatch callback count differs");}
  var add=CasStructuralRolesPatch.body(a,"olympus.io.CommunicationObject","AddFunction",false);int pushed=0;for(var i:add.getCode().code)if(prop(a,i,0x4f,"push")||prop(a,i,0x46,"push")){check(i.operands[1]==1,"Native listener append has a different ABI");pushed++;}
  check(pushed==1,"Native listener array no longer appends in insertion order");
 }
 static CasStructuralRolesPatch.Rewrite rewrite(ABC base,int wrapperQName)throws Exception {
  var before=body(base,ALIGN);var c=before.getCode().code;check(sha(before.getCodeBytes()).equals(ALIGN_PIN)&&before.exceptions.length==0&&before.traits.traits.isEmpty()&&c.size()==111,"Native align authority differs");
  check(op(c.get(35))==0xd0&&op(c.get(36))==0xd0&&prop(base,c.get(37),0x66,"mLayerPanels")&&op(c.get(38))==0xd2&&op(c.get(39))==0xd3&&op(c.get(40))==0x62&&c.get(40).operands[0]==4&&prop(base,c.get(41),0x4f,"BindDisplayObjectToSim")&&c.get(41).operands[1]==4,"First native layer binding boundary differs");
  var replacement=List.of(CasStructuralRolesPatch.ins(0xd1),CasStructuralRolesPatch.ins(0x4f,wrapperQName,5));
  var r=CasStructuralRolesPatch.rewrite(before,List.of(new CasStructuralRolesPatch.Block(41,42,replacement)));r.body.max_stack=before.max_stack+1;return r;
 }
 static void verify(ABC base,ABC candidate,CasStructuralRolesPatch.Rewrite change,Set<Integer> ids)throws Exception {
  CasStructuralRolesPatch.prefix(base,candidate);check(candidate.method_info.size()==base.method_info.size()+2&&candidate.bodies.size()==base.bodies.size()+2,"Binding may append only two helper methods");
  helperSemantics(candidate);bindings(base,candidate,ids);check(sha(body(candidate,"BindDisplayObjectToSim").getCodeBytes()).equals(BIND_PIN),"Native binding body changed");
  var aligned=body(candidate,ALIGN);var original=body(base,ALIGN);
  check(aligned.max_stack==original.max_stack+1&&aligned.max_regs==original.max_regs&&aligned.init_scope_depth==original.init_scope_depth&&aligned.max_scope_depth==original.max_scope_depth&&aligned.traits.traits.isEmpty(),"Native alignment frame metadata differs");
  for(String n:OWNED)check(body(candidate,n).init_scope_depth==body(base,OBSERVE).init_scope_depth,"Owned binding lexical scope differs: "+n);
  check(Arrays.equals(body(candidate,ALIGN).getCodeBytes(),change.body.getCodeBytes()),"Native first-bind call projection differs");CasStructuralRolesPatch.verifyProjection(body(base,ALIGN),change,body(candidate,ALIGN));
  int kept=0,wrapped=0;for(var i:body(candidate,ALIGN).getCode().code){if(prop(candidate,i,0x4f,"BindDisplayObjectToSim"))kept++;if(prop(candidate,i,0x4f,WRAPPER))wrapped++;}check(kept==4&&wrapped==1,"Other four native binds or first wrapper count changed");
  var projection=CasStructuralRolesPatch.reparse(candidate);CasStructuralRolesPatch.replace(projection,body(base,ALIGN).clone());CasStructuralRolesPatch.replace(projection,body(base,OBSERVE).clone());
  var traits=projection.instance_info.get(projection.findClassByName(MAIN)).instance_traits.traits;
  for(int n=ADDED.size()-1;n>=0;n--){int id=base.method_info.size()+n;check(projection.bodies.get(projection.bodies.size()-1).method_info==id,"Helper body must append");projection.bodies.remove(projection.bodies.size()-1);projection.method_info.remove(projection.method_info.size()-1);var t=traits.remove(traits.size()-1);check(t instanceof TraitMethodGetterSetter&&((TraitMethodGetterSetter)t).method_info==id&&CasStructuralRolesPatch.name(projection,t.name_index).equals(ADDED.get(n)),"Only reviewed private helper traits may append");}
  projection.constants=base.constants;projection.resetMethodIndexing();check(Arrays.equals(CasStructuralRolesPatch.save(projection),CasStructuralRolesPatch.save(base)),"Binding rollback changed unowned native data");
  for(var b:base.bodies)if(b.method_info!=body(base,ALIGN).method_info&&b.method_info!=body(base,OBSERVE).method_info)check(Arrays.equals(b.getCodeBytes(),candidate.findBody(b.method_info).getCodeBytes()),"Unowned native/owned method changed");
 }
 public static void main(String[] args)throws Exception {
  if(args.length==2&&args[0].equals("--semantic")){var a=CasStructuralRolesPatch.load(args[1]);for(String n:OWNED)System.out.println(n+" "+semantic(a,body(a,n)));return;}
  check(args.length==6,"Use prior Main, compiled helpers, output ABC, proof, original canonical and donor providers");
  var base=CasStructuralRolesPatch.load(args[0]);var compiled=CasStructuralRolesPatch.load(args[1]);CasStructuralRolesPatch.prefix(base,compiled);helperSemantics(compiled);signature(base,compiled,OBSERVE);listenerOrder(base);dispatch(args[4],"canonical");dispatch(args[5],"donor");
  check(base.instance_info.size()==compiled.instance_info.size()&&base.findClassByName(MAIN)==compiled.findClassByName(MAIN),"Compiler moved Main class layout");check(sha(body(base,"BindDisplayObjectToSim").getCodeBytes()).equals(BIND_PIN),"Original native binding method differs");
  var candidate=CasStructuralRolesPatch.reparse(base);candidate.constants=compiled.constants;var traits=candidate.instance_info.get(candidate.findClassByName(MAIN)).instance_traits.traits;var ids=new HashSet<Integer>();
  var observer=CasStructuralRolesPatch.adapted(body(compiled,OBSERVE),body(base,OBSERVE),body(base,OBSERVE).method_info);CasStructuralRolesPatch.replace(candidate,observer);ids.add(observer.method_info);
  for(String n:ADDED){for(var t:traits)check(!CasStructuralRolesPatch.name(candidate,t.name_index).equals(n),"Binding helper already exists");int id=candidate.method_info.size();candidate.method_info.add(compiled.method_info.get(trait(compiled,n).method_info));var b=CasStructuralRolesPatch.adapted(body(compiled,n),body(base,OBSERVE),id);candidate.bodies.add(b);var t=trait(compiled,n).clone();((TraitMethodGetterSetter)t).disp_id=0;((TraitMethodGetterSetter)t).method_info=id;traits.add(t);ids.add(id);}
  candidate.resetMethodIndexing();var change=rewrite(base,trait(candidate,WRAPPER).name_index);CasStructuralRolesPatch.replace(candidate,change.body);verify(base,candidate,change,ids);candidate=CasStructuralRolesPatch.reparse(candidate);verify(base,candidate,change,ids);
  var output=CasStructuralRolesPatch.save(candidate);Files.write(Path.of(args[2]),output);String report="{\"ok\":true,\"phase\":\"single-native-catalogue-bind\",\"baseline_swf_sha256\":\""+sha(Files.readAllBytes(Path.of(args[0])))+"\",\"baseline_abc_sha256\":\""+sha(CasStructuralRolesPatch.save(base))+"\",\"abc_sha256\":\""+sha(output)+"\",\"baseline_native_align_sha256\":\""+ALIGN_PIN+"\",\"native_bind_sha256\":\""+BIND_PIN+"\",\"changed_native_bodies\":1,\"replaced_owned_bodies\":1,\"appended_methods\":2,\"appended_fields\":0,\"native_first_bind_only_verified\":true,\"other_four_binds_retained\":true,\"native_binding_body_retained\":true,\"native_cfg_projection_verified\":true,\"listener_insertion_order_verified\":true,\"exact_dispatch_payload_verified\":true,\"protected_namespace_bindings_verified\":true,\"whole_abc_rollback_verified\":true,\"all_other_bodies_retained\":true,\"runtime_qualified\":false,\"performance_gain_claimed\":false}";Files.writeString(Path.of(args[3]),report+"\n");System.out.println(report);
 }
}
