// Private exact owned continuation. No native/constructor/click body enters it.
import java.nio.file.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;

public class CasGridSparesPatch {
 static final String GRID="olympus.layout.RecyclingGridLayout",MAIN="widgets.CAS.Customizer.CASCustomizerMain";
 static final List<String> GRID_REPLACED=List.of("ApexGridBegin","ApexGridDeltaQueue","ApexGridDeltaAdvance","ApexGridDeltaRetarget","ApexGridDeltaRestore","ApexGridDeltaPublish","ApexGridPresentationStart","ApexGridPresentationPublish","ApexGridPresentationRollback","ApexGridDetach","ApexGridPosition","ApexGridBind","ApexGridReady","ApexGridMetrics");
 static final List<String> GRID_ADDED=List.of("ApexGridSpareCustody","ApexGridSpareDescribe","ApexGridSpareReport","ApexGridSpareDefer","ApexGridSpareFilter","ApexGridDeltaTakeSpare","ApexGridSpareAfterPublish");
 static final Map<String,String> PINS=Map.ofEntries(
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridBegin","604054606d791174266a401df455cba4198a663237595d2b42d26af042b331b5"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridBind","1c63de90916066d9835cb6ab8650b5543cfd61a4c15225860e711b1b87a5baeb"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaAdvance","934ffa47bc48d54d840473b14a1e5dc133bcf60a8829519048c78da1d203b058"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaPublish","11f0273508a3b3c38ee5134d065745e9fc741c28b64b9489e13a6b5f06c8613c"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaQueue","17fa07c31da5703e88b63a2678f0eed64b76d72abba9b37f3ee204e49a7b333b"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaRestore","83731890ae8cb405406e258b32fcdf345774734e622a961002b25ec96a6a74a9"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaRetarget","21a7b07e9e9a8f3abc8a7d023aee3d89f09f226af7363992fdd5fbe19a7dcf4f"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaTakeSpare","0546bf72f4769514a4a5b07ac8b66a30cb409c5376cc68d975f26bdb8da918f1"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDetach","2a219f9761fc750b9fc61777cc902e71d126f245b0434b6a1fa60e82d8e6c812"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridMetrics","01b4d94f2f54987d260a02178928769dac8809dc66178ede7053332a2a497d61"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridPosition","f2ba082667b790aea1c0567d715fc5f41b4d40a55bcc91e1d2731968dbe4bbfe"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridPresentationPublish","414200828b71fd611aaae3d449c939f93ca7a2e696b8a586aad4961f20bd5e4e"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridPresentationRollback","999c92c3e625610f4c0c62cb2dfd541a9273aec44fe95384615f03a3b78b6e66"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridPresentationStart","a27811893ddd9017ff1632f72345a2dd5136a766e04d077c8df8723e69b2e4a6"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridReady","e36cf1d58bcbb012223d20d790cf77f72e8716b94e8cf8696fc090b2f49d5eb8"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridSpareAfterPublish","508a20e98b8fa61b475bb7270c6d10d607652eaa9f5e64ad418c795c148df32f"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridSpareCustody","08cb7c8d77ad9642213c065a9949adb6c43e96a07b3d754989ebdf2e50ee0505"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridSpareDefer","65094b725a684d2ee101cd0a3136669137df90ce01681cf1876f106db057fc73"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridSpareDescribe","2dfb4cb2c2a0995970099c0190b63c898f4a02f2b543885ccd03403d6d09fecb"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridSpareFilter","1964f78db4809b124529f01fb96170850a13419a20cf794039ffa87aa4b1f6d8"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridSpareReport","d3057d23e9c54de9673c839ed2e1e2277288401f325db77ccc27a2ad7690b2ec")
 );
 static final Map<String,Integer> FLAGS=Map.ofEntries(
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridBegin",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridBind",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaAdvance",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaPublish",2),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaQueue",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaRestore",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaRetarget",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaTakeSpare",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDetach",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridMetrics",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridPosition",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridPresentationPublish",2),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridPresentationRollback",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridPresentationStart",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridReady",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridSpareAfterPublish",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridSpareCustody",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridSpareDefer",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridSpareDescribe",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridSpareFilter",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridSpareReport",0)
 );
 static void check(boolean v,String message){CasStructuralRolesPatch.check(v,message);}
 static String name(ABC a,int n){return CasStructuralRolesPatch.name(a,n);}
 static TraitMethodGetterSetter trait(ABC a,String type,String method){return CasStructuralRolesPatch.trait(a,type,method,false);}
 static MethodBody body(ABC a,String type,String method){return a.findBody(trait(a,type,method).method_info);}
 static String sha(byte[] raw)throws Exception{return CasStructuralRolesPatch.sha(raw);}
 static String owner(String mode){check(mode.equals("grid"),"Exact row-delta mode required");return mode.equals("grid")?GRID:MAIN;}
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
   check(semantic(a,b).equals(PINS.get(type+"/"+n)),"Reviewed row-delta semantic/CFG differs: "+n);
   check(info.flags==FLAGS.get(type+"/"+n),"Reviewed method flags differ: "+n);
   for(var op:b.getCode().code){int code=CasStructuralRolesPatch.op(op);check(!Set.of(0x40,0x43,0x44,0x67).contains(code),"Nested/outer/callmethod linkage: "+n);
    if(Set.of(0x60,0x46,0x4f).contains(code)&&op.operands.length>0&&name(a,op.operands[0]).equals("getQualifiedClassName")){
     check(CasCommunicationIndexPatch.qname(a,op.operands[0]).equals("7:getQualifiedClassName:22:flash.utils"),"Real exact runtime class getter QName required");qname=true;
    }
    if(code==0x60&&name(a,op.operands[0]).equals("flash"))throw new IllegalStateException("Unbound flash package lookup");
   }
   if(added(mode).contains(n)){
    var q=a.constants.getMultiname(t.name_index);var ns=a.constants.getNamespace(q.namespace_index);
    check(t.kindType==Trait.TRAIT_METHOD&&t.kindFlags==0&&q.kind==Multiname.QNAME&&ns.kind==Namespace.KIND_PRIVATE&&a.constants.getString(ns.name_index).equals("olympus.layout:RecyclingGridLayout"),"Appended private method namespace/kind differs");
    check(info.optional.length==0,"No new optional callable defaults");
   }
  }
  check(!mode.equals("grid")||qname,"Native runtime class proof getter absent");
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
  String proof="{\"ok\":true,\"mode\":\""+mode+"\",\"replaced_owned_bodies\":"+replaced(mode).size()+",\"appended_methods\":"+added(mode).size()+",\"appended_fields\":0,\"changed_original_native_bodies\":0,\"whole_abc_rollback_verified\":true,\"all_unowned_bodies_retained\":true,\"serialized_owned_bodies_verified\":true,\"native_protected_bindings_verified\":true,\"runtime_class_QName_verified\":"+mode.equals("grid")+",\"baseline_swf_sha256\":\""+sha(Files.readAllBytes(Path.of(args[1])))+"\",\"baseline_abc_sha256\":\""+sha(CasStructuralRolesPatch.save(base))+"\",\"abc_sha256\":\""+sha(out)+"\",\"runtime_qualified\":false,\"performance_gain_claimed\":false}";
  Files.writeString(Path.of(args[4]),proof+"\n");System.out.println(proof);
 }
}
