// Private exact owned continuation. No native/constructor/click body enters it.
import java.nio.file.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;

public class CasCatalogWorkflowPatch {
 static final String GRID="olympus.layout.RecyclingGridLayout",MAIN="widgets.CAS.Customizer.CASCustomizerMain";
 static final List<String> GRID_REPLACED=List.of();
 static final List<String> GRID_ADDED=List.of();
 static final Map<String,String> PINS=Map.ofEntries(
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridFrame","4c61fb7d9bd40ec08eebf05385d43166984558574272240c4172a176b7ad7640"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridInput","2c9806c23db579fdc40d8b79274d1a01f8be7ef71ec04c33f5abe2cc585b4a33"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridLeaseCurrent","f758da586467955cd98610f76789e292ddf100d9212e91ee7911dea4e6333861"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridPrepare","82ab77ccaa31fea25d685941e328eab44281373ee7d63a9147dabdae7cff5b70"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogKeyboardFailureDiagnostic","1a54d6dde8b5fd18a761084c0d52e8d98f681b532a59c7d82fd8d25cfb94dba9"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogKeyboardPublicationReady","b45614fec42ba413ba99158737777149a49cc8a59f3b91e800a0b549dfcf9a35"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexReadback","1e49b45962c520e7c9374b9da00ea4c7873585dcb9d514485f42433022b39008")
 );
 static final Map<String,Integer> FLAGS=Map.ofEntries(
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridFrame",10),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridInput",2),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridLeaseCurrent",0),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogGridPrepare",0),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogKeyboardFailureDiagnostic",2),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogKeyboardPublicationReady",0),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexReadback",2)
 );
 static void check(boolean v,String message){CasStructuralRolesPatch.check(v,message);}
 static String name(ABC a,int n){return CasStructuralRolesPatch.name(a,n);}
 static TraitMethodGetterSetter trait(ABC a,String type,String method){return CasStructuralRolesPatch.trait(a,type,method,false);}
 static MethodBody body(ABC a,String type,String method){return a.findBody(trait(a,type,method).method_info);}
 static String sha(byte[] raw)throws Exception{return CasStructuralRolesPatch.sha(raw);}
 static String owner(String mode){check(mode.equals("main"),"Exact Main scheduling mode required");return MAIN;}
 static List<String> replaced(String mode){return List.of("ApexCatalogGridPrepare","ApexCatalogGridLeaseCurrent","ApexCatalogGridFrame","ApexCatalogGridInput","ApexCatalogKeyboardPublicationReady","ApexReadback");}
 static List<String> added(String mode){return List.of("ApexCatalogKeyboardFailureDiagnostic");}
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
    check(t.kindType==Trait.TRAIT_METHOD&&t.kindFlags==0&&q.kind==Multiname.QNAME&&ns.kind==Namespace.KIND_PRIVATE&&a.constants.getString(ns.name_index).equals(mode.equals("grid")?"olympus.layout:RecyclingGridLayout":"widgets.CAS.Customizer:CASCustomizerMain"),"Appended private method namespace/kind differs");
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
