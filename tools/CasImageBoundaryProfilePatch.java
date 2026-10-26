// Explicit diagnostics: duplicate retained native flow; default remains original.
import java.nio.file.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;

public class CasImageBoundaryProfilePatch {
 static final String RESOURCE="olympus.controls.ImageResource",LOADER="olympus.resources.ImageLoader",BUTTON="olympus.gui.buttons.Button";
 static final String ACTIVE="ApexImageTraceActive",STAMP="ApexImageTraceStamp";
 static final Set<String> LOADER_METHODS=Set.of(ACTIVE,"ApexImageTraceEnable","ApexImageTraceStats",STAMP);
 static final Set<String> RESOURCE_METHODS=Set.of("ApexImageTraceEnable","ApexImageTraceStats");
 static final Set<String> FIELDS=Set.of("apexImageTraceState","apexImageTraceAccepting","apexImageTraceFault","apexImageTraceRequested");
 static final Map<String,String> BASELINES=Map.of(
  "4864a5942a9d77c0ecca0ee1682ca53cdd302751872b4173ad69d17b3ef022bc","62ECC59A:00000000:12272E1AC0C1F8E2",
  "b71a66ed5a0d867de864bba8c58d847b306ce685a6169429034850c955e5372f","62ECC59A:00000000:89D13757C58C2E05",
  "373db1aa7a273c8ca7b9124a027d420deddebdf1815f3ca3cb48c4390d66e859","62ECC59A:00000000:3FFE72432A703655");
 static final Map<String,String> PINS=Map.of(
  LOADER+"/ApexImageTraceStats","3590013fd1c75c41b27729d83664bd832d3ba9c6e7d46332dc5e192f378ee68b",
  LOADER+"/ApexImageTraceActive","94ac05c8bb889ca4cd06e1780ae86f111bc69b0bfffcfb9c2216977f1844bad2",
  LOADER+"/ApexImageTraceStamp","2e726ba9c5509b63994598d8fdf575cfed50112ec89ef4f136f30cf92457b7fd",
  LOADER+"/ApexImageTraceEnable","a026bcf7c7e039c9e2ab684be26ab2295f2d80ea910c38ebbdee2230938697f8",
  RESOURCE+"/ApexImageTraceEnable","09ed82d8a875a3e541abe89df51e05b34cd769fb9ff86908a3dd52f6b9c390ae",
  RESOURCE+"/ApexImageTraceStats","f0eb8ed2c3b5c99acc533e63712257a7609dff90b95e05225476f3d909cc7a86");
 static void check(boolean v,String s){CasStructuralRolesPatch.check(v,s);}
 static int op(AVM2Instruction i){return i.definition.instructionCode;}
 static AVM2Instruction ins(int code,int...args){return CasStructuralRolesPatch.ins(code,args);}
 static String name(ABC a,int q){return CasStructuralRolesPatch.name(a,q);}
 static TraitMethodGetterSetter method(ABC a,String type,String n){return CasStructuralRolesPatch.trait(a,type,n,false);}
 static MethodBody body(ABC a,String type,String n){return a.findBody(method(a,type,n).method_info);}
 static int field(ABC a,String type,String n,boolean statik){int c=a.findClassByName(type);int found=-1;for(var t:(statik?a.class_info.get(c).static_traits:a.instance_info.get(c).instance_traits).traits)if(n.equals(name(a,t.name_index))){check(found<0&&t instanceof TraitSlotConst,"Ambiguous image field");found=t.name_index;}check(found>0,"Image authority field absent: "+n);return found;}
 static String semantic(ABC a,MethodBody b)throws Exception {
  String text=CasCommunicationIndexPatch.semanticText(a,b);
  // FFDec's file-private namespace serial need not equal the class index.
  // Normalize only this exact source file's private label; protected/private
  // class field namespaces and every foreign binding remain exact.
  for(String type:new String[]{LOADER,RESOURCE}){String simple=type.substring(type.lastIndexOf('.')+1);text=text.replaceAll("(?<=5:)"+java.util.regex.Pattern.quote(simple+".as$")+"[0-9]+",simple+".as\\$SELF");}
  for(String tgi:BASELINES.values())text=text.replace(tgi,"$PROVIDER");
  return CasStructuralRolesPatch.sha(text.getBytes(java.nio.charset.StandardCharsets.UTF_8));
 }
 static void helpers(ABC a,boolean guarded)throws Exception {
  for(String type:new String[]{LOADER,RESOURCE})for(String n:type.equals(LOADER)?LOADER_METHODS:RESOURCE_METHODS){
   var t=method(a,type,n);var b=body(a,type,n);var normal=n.equals(STAMP)&&guarded?normalStamp(b):b;
   check(t.kindFlags==1&&t.kindType==(n.equals(ACTIVE)?Trait.TRAIT_GETTER:Trait.TRAIT_METHOD),"Image helper public/final kind differs: "+n);
   var declared=a.constants.getMultiname(t.name_index);var space=a.constants.getNamespace(declared.namespace_index);check(declared.kind==Multiname.QNAME&&space.kind==Namespace.KIND_PACKAGE&&"".equals(a.constants.getString(space.name_index)),"Image helper public namespace differs: "+n);
   check(a.method_info.get(t.method_info).flags==0,"Image helper must not allocate activation: "+n);
   check(semantic(a,normal).equals(PINS.get(type+"/"+n)),"Image helper reviewed semantic bytes differ: "+type+"/"+n);
  }
  int count=0;for(var t:a.class_info.get(a.findClassByName(LOADER)).static_traits.traits)if(FIELDS.contains(name(a,t.name_index))){check(t instanceof TraitSlotConst&&((TraitSlotConst)t).value_index==0,"Image fields must preserve native default initializer");String n=name(a,t.name_index),expected=n.equals("apexImageTraceState")?"Object":n.equals("apexImageTraceRequested")?"int":"Boolean";var q=a.constants.getMultiname(t.name_index);check(name(a,((TraitSlotConst)t).type_index).equals(expected)&&a.constants.getNamespace(q.namespace_index).kind==Namespace.KIND_PRIVATE,"Image diagnostic field type/privacy differs");count++;}check(count==4,"Image static field inventory differs");
  var active=body(a,LOADER,ACTIVE);var meaningful=new ArrayList<AVM2Instruction>();for(var i:active.getCode().code)if(!Set.of(0xef,0xf0,0xf1).contains(op(i)))meaningful.add(i);
  check(meaningful.size()==4&&op(meaningful.get(0))==0xd0&&op(meaningful.get(1))==0x30&&op(meaningful.get(2))==0x60&&meaningful.get(2).operands[0]==field(a,LOADER,"apexImageTraceAccepting",true)&&op(meaningful.get(3))==0x48&&active.exceptions.length==0,"Disabled active getter must be one exact lexical Boolean read");
  if(guarded){var code=body(a,LOADER,STAMP).getCode().code;int n=code.size()-10;check(code.get(n+3).operands[0]==field(a,LOADER,"apexImageTraceAccepting",true)&&code.get(n+5).operands[0]==field(a,LOADER,"apexImageTraceAccepting",true)&&code.get(n+6).operands[0]==field(a,LOADER,"apexImageTraceFault",true)&&code.get(n+8).operands[0]==field(a,LOADER,"apexImageTraceFault",true),"Trace fault handler must write only its private diagnostic flags");}
 }
 static MethodBody guardStamp(ABC a,MethodBody source)throws Exception {
  var b=source.clone();check(b.exceptions.length==0,"Compiled trace stamp exceptions differ");var code=b.getCode().code;long start=code.get(2).getAddress(),end=b.getCode().getEndOffset();
  for(var i:List.of(ins(0x29),ins(0xd0),ins(0x30),ins(0x5d,field(a,LOADER,"apexImageTraceAccepting",true)),ins(0x27),ins(0x61,field(a,LOADER,"apexImageTraceAccepting",true)),ins(0x5d,field(a,LOADER,"apexImageTraceFault",true)),ins(0x26),ins(0x61,field(a,LOADER,"apexImageTraceFault",true)),ins(0x47)))code.add(i);
  CasStructuralRolesPatch.set(b,new ArrayList<>(code));var e=new ABCException();e.start=(int)start;e.end=(int)end;e.target=(int)end;e.type_index=0;e.name_index=0;b.exceptions=new ABCException[]{e};return b;
 }
 static MethodBody normalStamp(MethodBody b)throws Exception {
  var n=b.clone();var code=n.getCode().code;check(code.size()>12&&b.exceptions.length==1,"Trace stamp fault handler absent");int at=code.size()-10;var e=b.exceptions[0];check(e.start==code.get(2).getAddress()&&e.end==code.get(at).getAddress()&&e.target==e.end&&e.type_index==0&&e.name_index==0,"Trace stamp fault range differs");
  int[] ops={0x29,0xd0,0x30,0x5d,0x27,0x61,0x5d,0x26,0x61,0x47};for(int i=0;i<10;i++)check(op(code.get(at+i))==ops[i],"Trace stamp fault-only disable instructions differ");
  while(code.size()>at)code.remove(code.size()-1);n.exceptions=new ABCException[0];n.setCode(n.getCode());n.setModified();return n;
 }
 static List<AVM2Instruction> loaderTarget(ABC a,boolean resource){return resource?List.of(ins(0xd0),ins(0x66,field(a,RESOURCE,"mLoader",false))):List.of(ins(0xd0));}
 static List<AVM2Instruction> stamp(ABC a,boolean resource,int phase,boolean enter){var out=new ArrayList<>(loaderTarget(a,resource));out.add(ins(0x24,phase));out.add(ins(enter?0x26:0x27));out.add(ins(0x4f,method(a,LOADER,STAMP).name_index,2));return out;}
 static Map<Integer,Integer> spans(ABC a,MethodBody before,String type,String n){
  var out=new TreeMap<Integer,Integer>();var code=before.getCode().code;int rect=0,init=0,readd=0,cancel=0,load=0;
  for(int j=2;j<code.size();j++){var i=code.get(j);if(op(i)!=0x46&&op(i)!=0x4f)continue;String call=name(a,i.operands[0]);
   if(type.equals(RESOURCE)&&n.equals("OnAddedToStage")){if(call.equals("getRect")){check(i.operands[1]==1,"Native getRect ABI differs");out.put(j,0);rect++;}if(call.equals("Initialize")){check(i.operands[1]==1,"Native image Initialize ABI differs");out.put(j,1);init++;}}
   else if(n.equals("OnContainerAddedToStage")&&call.equals("LoadImage")){check(i.operands[1]==2,"Native reattach LoadImage defaults differ");out.put(j,2);readd++;}
   else if(n.equals("LoadImage")){if(call.equals("CancelLoad")){check(i.operands[1]==0,"Native cancel ABI differs");out.put(j,3);cancel++;}if(call.equals("Load")){check(i.operands[1]==2,"Native AssetLoader.Load defaults differ");out.put(j,4);load++;}}
  }
  check(type.equals(RESOURCE)?rect==1&&init==1:n.equals("OnContainerAddedToStage")?readd==1:cancel==1&&load==1,"Image native span inventory differs");return out;
 }
 record Wrapped(MethodBody body,CasStructuralRolesPatch.Rewrite disabled,CasStructuralRolesPatch.Rewrite enabled){}
 static Wrapped wrap(ABC a,MethodBody before,String type,String n)throws Exception {
  var old=before.getCode().code;check(old.size()>2&&op(old.get(0))==0xd0&&op(old.get(1))==0x30&&before.exceptions.length==0&&Set.of(0x47,0x48,0x03).contains(op(old.get(old.size()-1))),"Unsupported native image prologue/exception/return");
  boolean resource=type.equals(RESOURCE);var markers=spans(a,before,type,n);var out=new ArrayList<AVM2Instruction>();out.add(CasStructuralRolesPatch.copy(old.get(0)));out.add(CasStructuralRolesPatch.copy(old.get(1)));
  var gates=new IdentityHashMap<AVM2Instruction,AVM2Instruction>();var nativeEdges=new IdentityHashMap<AVM2Instruction,Integer>();var nativeKinds=new IdentityHashMap<AVM2Instruction,Boolean>();var disabledMap=new HashMap<Integer,Integer>();var enabledMap=new HashMap<Integer,Integer>();disabledMap.put(0,0);disabledMap.put(1,1);enabledMap.put(0,0);enabledMap.put(1,1);
  var branchProfile=ins(0x11,0);var branchNative=new ArrayList<AVM2Instruction>();var loaderPop=ins(0x29);
  if(resource){out.addAll(loaderTarget(a,true));out.add(ins(0x2a));var nullLoader=ins(0x12,0);out.add(nullLoader);gates.put(nullLoader,loaderPop);
   out.add(ins(0x2a));out.add(ins(0x2c,a.constants.getStringId(ACTIVE,true)));out.add(ins(0x2b));out.add(ins(0xb4));var absentActive=ins(0x12,0);out.add(absentActive);gates.put(absentActive,loaderPop);
   out.add(ins(0x2a));out.add(ins(0x66,method(a,LOADER,ACTIVE).name_index));var notActive=ins(0x12,0);out.add(notActive);gates.put(notActive,loaderPop);
   out.add(ins(0x2a));out.add(ins(0x2c,a.constants.getStringId(STAMP,true)));out.add(ins(0x2b));out.add(ins(0xb4));var absentStamp=ins(0x12,0);out.add(absentStamp);gates.put(absentStamp,loaderPop);out.add(ins(0x29));out.add(ins(0x26));out.add(branchProfile);out.add(loaderPop);
  }else{out.add(ins(0xd0));out.add(ins(0x66,method(a,LOADER,ACTIVE).name_index));out.add(branchProfile);}
  var disabledOrigins=new ArrayList<Integer>();var enabledOrigins=new ArrayList<Integer>();for(int j=0;j<out.size();j++){disabledOrigins.add(j<2?j:-1);enabledOrigins.add(j<2?j:-1);}
  for(int j=2;j<old.size();j++){disabledMap.put(j,out.size());var i=CasStructuralRolesPatch.copy(old.get(j));nativeEdges.put(i,j);nativeKinds.put(i,false);out.add(i);disabledOrigins.add(j);enabledOrigins.add(-1);}disabledMap.put(old.size(),out.size());
  int profileStart=out.size();
  for(int j=2;j<old.size();j++){enabledMap.put(j,out.size());if(markers.containsKey(j))for(var i:stamp(a,resource,markers.get(j),true)){out.add(i);disabledOrigins.add(-1);enabledOrigins.add(-1);}
   var i=CasStructuralRolesPatch.copy(old.get(j));nativeEdges.put(i,j);nativeKinds.put(i,true);out.add(i);disabledOrigins.add(-1);enabledOrigins.add(j);
   if(markers.containsKey(j))for(var after:stamp(a,resource,markers.get(j),false)){out.add(after);disabledOrigins.add(-1);enabledOrigins.add(-1);}}
  enabledMap.put(old.size(),out.size());long address=0;for(var i:out){i.setAddress(address);address+=i.getBytesLength();}
  gates.put(branchProfile,out.get(profileStart));for(var e:gates.entrySet())e.getKey().operands[0]=(int)(e.getValue().getAddress()-e.getKey().getAddress()-e.getKey().getBytesLength());
  var originalAddresses=CasStructuralRolesPatch.addresses(before);
  for(var e:nativeEdges.entrySet())for(int operand:CasStructuralRolesPatch.targetOperands(e.getKey())){var map=nativeKinds.get(e.getKey())?enabledMap:disabledMap;int target=CasStructuralRolesPatch.index(originalAddresses,CasStructuralRolesPatch.target(old.get(e.getValue()),operand));int at=map.get(target);long dest=at==out.size()?address:out.get(at).getAddress();e.getKey().operands[operand]=(int)(dest-e.getKey().getAddress()-(op(e.getKey())==0x1b?0:e.getKey().getBytesLength()));}
  var b=before.clone();CasStructuralRolesPatch.set(b,out);b.max_stack=before.max_stack+4;
  var d=new CasStructuralRolesPatch.Rewrite(b,disabledMap,disabledOrigins);var p=new CasStructuralRolesPatch.Rewrite(b,enabledMap,enabledOrigins);CasStructuralRolesPatch.verifyProjection(before,d,b);CasStructuralRolesPatch.verifyProjection(before,p,b);return new Wrapped(b,d,p);
 }
 static byte[] buttonCode(ABC base,ABC a)throws Exception {
  var nativeButton=body(base,BUTTON,"OnAddedToStage").getCode().code;AVM2Instruction sys=null,mode=null;
  for(int i=0;i+1<nativeButton.size();i++)if(op(nativeButton.get(i))==0x60&&"SystemUtils".equals(name(base,nativeButton.get(i).operands[0]))&&op(nativeButton.get(i+1))==0x66&&"UsingMouseKeyboard".equals(name(base,nativeButton.get(i+1).operands[0]))){check(sys==null,"Native Button input-mode oracle ambiguous");sys=nativeButton.get(i);mode=nativeButton.get(i+1);}
  check(sys!=null,"Native Button input-mode oracle absent");var old=body(base,BUTTON,"ApexCommButtonIndexStats").getCode().code;check(old.size()==9&&op(old.get(7))==0x55&&old.get(7).operands[0]==2,"Owned Button diagnostic differs");
  var out=new java.io.ByteArrayOutputStream();for(int i=0;i<7;i++)out.write(old.get(i).getBytes());for(var i:List.of(ins(0x2c,a.constants.getStringId("using_mouse_keyboard",true)),CasStructuralRolesPatch.copy(sys),CasStructuralRolesPatch.copy(mode),ins(0x55,3),ins(0x48)))out.write(i.getBytes());return out.toByteArray();
 }
 static void verify(ABC base,ABC a,Map<Integer,Wrapped> wraps)throws Exception {
  CasStructuralRolesPatch.prefix(base,a);check(a.method_info.size()==base.method_info.size()+6&&a.bodies.size()==base.bodies.size()+6,"Image helper method inventory differs");helpers(a,true);
  for(var e:wraps.entrySet()){var b=a.findBody(e.getKey());CasStructuralRolesPatch.verifyProjection(base.findBody(e.getKey()),e.getValue().disabled,b);CasStructuralRolesPatch.verifyProjection(base.findBody(e.getKey()),e.getValue().enabled,b);check(Arrays.equals(b.getCodeBytes(),e.getValue().body.getCodeBytes()),"Image gate/marker bytes differ");}
  check(Arrays.equals(body(a,BUTTON,"ApexCommButtonIndexStats").getCodeBytes(),buttonCode(base,a)),"Owned Button input-mode oracle differs");
  var rollback=CasStructuralRolesPatch.reparse(a);for(int id:wraps.keySet())CasStructuralRolesPatch.replace(rollback,base.findBody(id).clone());CasStructuralRolesPatch.replace(rollback,body(base,BUTTON,"ApexCommButtonIndexStats").clone());
  while(rollback.method_info.size()>base.method_info.size())rollback.method_info.remove(rollback.method_info.size()-1);while(rollback.bodies.size()>base.bodies.size())rollback.bodies.remove(rollback.bodies.size()-1);
  for(String type:new String[]{LOADER,RESOURCE}){int c=rollback.findClassByName(type);var traits=rollback.instance_info.get(c).instance_traits.traits;int count=base.instance_info.get(c).instance_traits.traits.size();check(traits.size()==count+(type.equals(LOADER)?4:2),"Image helper trait inventory differs");while(traits.size()>count)traits.remove(traits.size()-1);}
  var statics=rollback.class_info.get(rollback.findClassByName(LOADER)).static_traits.traits;int count=base.class_info.get(base.findClassByName(LOADER)).static_traits.traits.size();check(statics.size()==count+4,"Image static trait inventory differs");while(statics.size()>count)statics.remove(statics.size()-1);
  rollback.constants=base.constants;rollback.resetMethodIndexing();check(Arrays.equals(CasStructuralRolesPatch.save(rollback),CasStructuralRolesPatch.save(base)),"Image profiler whole-ABC rollback changed other methods/initializers");
 }
 public static void main(String[]args)throws Exception {
  if(args.length==2&&args[0].equals("--semantic")){var a=CasStructuralRolesPatch.load(args[1]);for(String type:new String[]{LOADER,RESOURCE})for(String n:type.equals(LOADER)?LOADER_METHODS:RESOURCE_METHODS)System.out.println(type+"/"+n+" "+semantic(a,body(a,type,n)));return;}
  check(args.length==4,"Use V333 baseline, compiled image helpers, output ABC, proof");String pin=CasStructuralRolesPatch.sha(Files.readAllBytes(Path.of(args[0]))),tgi=BASELINES.get(pin);check(tgi!=null,"Unpinned image profiler baseline");
  var base=CasStructuralRolesPatch.load(args[0]);var compiled=CasStructuralRolesPatch.load(args[1]);CasStructuralRolesPatch.prefix(base,compiled);helpers(compiled,false);var a=CasStructuralRolesPatch.reparse(base);a.constants=compiled.constants;
  var ids=new TreeSet<Integer>();var appended=new HashMap<String,List<Trait>>();
  for(String type:new String[]{LOADER,RESOURCE}){int c=compiled.findClassByName(type);check(c==base.findClassByName(type),"Compiler moved image class");var list=new ArrayList<Trait>();for(var t:compiled.instance_info.get(c).instance_traits.traits)if((type.equals(LOADER)?LOADER_METHODS:RESOURCE_METHODS).contains(name(compiled,t.name_index))){var made=((TraitMethodGetterSetter)t).clone();made.disp_id=0;ids.add(made.method_info);list.add(made);}appended.put(type,list);}
  var remap=new HashMap<Integer,Integer>();for(int id:ids){String type=appended.get(LOADER).stream().anyMatch(t->((TraitMethodGetterSetter)t).method_info==id)?LOADER:RESOURCE;String nativeName=type.equals(LOADER)?"LoadImage":"OnAddedToStage";var source=compiled.findBody(id);var b=id==method(compiled,LOADER,STAMP).method_info?guardStamp(compiled,source):source.clone();int delta=body(base,type,nativeName).init_scope_depth-body(compiled,type,nativeName).init_scope_depth;check(delta>=0&&delta<=16,"Image helper compilation scope differs");int made=a.method_info.size();remap.put(id,made);a.method_info.add(compiled.method_info.get(id));b.method_info=made;b.init_scope_depth+=delta;b.max_scope_depth+=delta;b.setCode(b.getCode());b.setModified();a.bodies.add(b);}
  for(String type:new String[]{LOADER,RESOURCE})for(var t:appended.get(type)){var m=(TraitMethodGetterSetter)t;m.method_info=remap.get(m.method_info);a.instance_info.get(a.findClassByName(type)).instance_traits.traits.add(t);}
  for(var t:compiled.class_info.get(compiled.findClassByName(LOADER)).static_traits.traits)if(FIELDS.contains(name(compiled,t.name_index))){var made=((TraitSlotConst)t).clone();made.slot_id=0;a.class_info.get(a.findClassByName(LOADER)).static_traits.traits.add(made);}a.resetMethodIndexing();
  var wraps=new HashMap<Integer,Wrapped>();for(String[] target:new String[][]{{RESOURCE,"OnAddedToStage"},{LOADER,"OnContainerAddedToStage"},{LOADER,"LoadImage"}}){var old=body(base,target[0],target[1]);var w=wrap(a,old,target[0],target[1]);wraps.put(old.method_info,w);CasStructuralRolesPatch.replace(a,w.body);}
  var button=body(a,BUTTON,"ApexCommButtonIndexStats");button.setCodeBytes(buttonCode(base,a));button.setCode(button.getCode());button.max_stack=6;button.setModified();verify(base,a,wraps);a=CasStructuralRolesPatch.reparse(a);verify(base,a,wraps);
  byte[] data=CasStructuralRolesPatch.save(a);Files.write(Path.of(args[2]),data);String report="{\"ok\":true,\"provider_resource_tgi\":\""+tgi+"\",\"baseline_swf_sha256\":\""+pin+"\",\"baseline_abc_sha256\":\""+CasStructuralRolesPatch.sha(CasStructuralRolesPatch.save(base))+"\",\"abc_sha256\":\""+CasStructuralRolesPatch.sha(data)+"\",\"changed_native_bodies\":3,\"replaced_owned_button_bodies\":1,\"appended_methods\":6,\"appended_static_fields\":4,\"budget_limit\":4096,\"depth_limit\":32,\"record_limit\":0,\"whole_abc_rollback_verified\":true,\"native_disabled_projection_verified\":true,\"native_enabled_projection_verified\":true,\"native_exceptions_not_intercepted\":true,\"actual_loader_instance_route_verified\":true,\"disabled_no_allocation_clock_counter\":true,\"bounded_primitive_state_verified\":true,\"native_input_mode_oracle_verified\":true,\"runtime_qualified\":false,\"optimization_claimed\":false}";Files.writeString(Path.of(args[3]),report+"\n");System.out.println(report);
 }
}
