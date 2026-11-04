import java.nio.file.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;

// Exact reviewed multi-owner UI continuation. No original constructor copied.
public class CasListInsetsPatch {
 record Role(String owner,boolean statik,List<String> replaced,List<String> added,List<String> fields){}
 static final List<Role> ROLES=List.of(
  new Role("widgets.CAS.Customizer.CASCustomizerMain",false,List.of("ApexSearchInitialize","ApexSearchDispose","ApexSearchAttach","ApexSearchRestore","ApexSearchStatus"),List.of("ApexCatalogListSlot","ApexCatalogListCurrent","ApexCatalogListRecord","ApexCatalogListApply","ApexCatalogListRail","ApexCatalogListGeometry","ApexCatalogSearchListApply","ApexCatalogSearchListRestore","ApexCatalogListRect","ApexCatalogListStatus"),List.of()),
  new Role("widgets.CAS.Customizer.CatalogPanel",false,List.of("RefreshLayout"),List.of("ApexRawListGeneration","ApexRawListBaseline"),List.of("apexRawListGeneration","apexRawListLayout")),
  new Role("dcc.catalog.BodyTypeTabs",true,List.of("Layout","NativeLayout","RestoreList"),List.of("ApexListLayoutRecord","ApexNativeRailReceipt"),List.of("apexListLayout")));
 static final Map<String,String>PINS=Map.ofEntries(
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexSearchInitialize","1b0e3519956d2d2f3013e6f7f1c3d4988cc2eade82ee3574b9d7e1b748ed0e1c"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexSearchDispose","74ac97cc156c2f799036165898ca68691fca6efa1814fd57d84471de1f69535d"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexSearchAttach","8108a2cabbebe9a880d73256162b4344b221204999c3ef2790e577e2818652f0"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexSearchRestore","c3347421901cc7483d4827ecbad962620f3722c607267439cb9e7dadee146072"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexSearchStatus","83d2a50931c3a4f5c1db00135c649f3976b839673f84e9485c878b31caf9f833"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogListSlot","1c70fc8d1643b96aac1f184137757c582184e3949f7380b2f661a582ac10cc04"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogListCurrent","f1d41ae00baeba958565f1f800f55053b6ea626334d4122d57a5bd7c70cd3b14"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogListRecord","63f546138821e6908ad6256fb965355faa63966538b47444974c9161d0a72983"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogListApply","7d7e692615ebc8cc254507ba94b66415b217ea093b743500eb50ff0f05cc6555"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogListRail","3eb3172663aca5c653de6cf93d3f680335ffe6ca8333e698f31faa9d295d6da3"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogListGeometry","7632f7204fb3d3c2400520f1a9d08a6fe551c0a7edf508ea1d358174da960979"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogSearchListApply","60406881a0db14b1594f2b99d7c020aefc8f4b7798e8a2ea943da1e20ff6ab11"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogSearchListRestore","d7242c094b9033286a48199d7bd458661db449ee0138e16fcb055ab8f28da9b9"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogListRect","96b1b7831039cfdc44271b05bf3b5741f9b82fda9aa65b4fdab2e62fc93e53ae"),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogListStatus","05f6be8404236a0693181f33e39c4d4da3da8c361b874088f3eae38bafc87e8d"),
 Map.entry("widgets.CAS.Customizer.CatalogPanel/RefreshLayout","df2ef85d5259fdb93363c92593fbcc272175ea3dad95e5d71bd32c151c1dc3ad"),
 Map.entry("widgets.CAS.Customizer.CatalogPanel/ApexRawListGeneration","4c33865ad82bc0a58c5e6a0ddbb519e8110c0fe28494d26b0aaf9c20ba48d4b7"),
 Map.entry("widgets.CAS.Customizer.CatalogPanel/ApexRawListBaseline","f728be4d7365e2edc584dc35022a3819d63bda6573e019ba7de0babb2966e320"),
 Map.entry("dcc.catalog.BodyTypeTabs/Layout","5c748839a17ee3d117055a06ec35e09396d3af1dd51b62c1c65905b6ba236c37"),
 Map.entry("dcc.catalog.BodyTypeTabs/NativeLayout","696ff46dda9ea547b170570abdd4f1785eb1a261e758b4a55108d50f7da97f03"),
 Map.entry("dcc.catalog.BodyTypeTabs/RestoreList","eeea4cae27a685e59f2d631da13b345e581b26510a52ba86c60aba6047c51373"),
 Map.entry("dcc.catalog.BodyTypeTabs/ApexListLayoutRecord","da385261565e64245bdbd889d4d503fe4ee2d68fc0f330ab7de0a007db685df8"),
 Map.entry("dcc.catalog.BodyTypeTabs/ApexNativeRailReceipt","4a21105e2a9b0c77d0a083249f01f9c665de8a5e656543956eeab1f1dc96c5cd"));
 static final Map<String,Integer>FLAGS=Map.ofEntries(
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexSearchInitialize",0),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexSearchDispose",0),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexSearchAttach",0),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexSearchRestore",0),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexSearchStatus",0),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogListSlot",0),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogListCurrent",0),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogListRecord",2),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogListApply",2),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogListRail",8),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogListGeometry",0),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogSearchListApply",0),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogSearchListRestore",0),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogListRect",2),
 Map.entry("widgets.CAS.Customizer.CASCustomizerMain/ApexCatalogListStatus",0),
 Map.entry("widgets.CAS.Customizer.CatalogPanel/RefreshLayout",0),
 Map.entry("widgets.CAS.Customizer.CatalogPanel/ApexRawListGeneration",0),
 Map.entry("widgets.CAS.Customizer.CatalogPanel/ApexRawListBaseline",0),
 Map.entry("dcc.catalog.BodyTypeTabs/Layout",2),
 Map.entry("dcc.catalog.BodyTypeTabs/NativeLayout",2),
 Map.entry("dcc.catalog.BodyTypeTabs/RestoreList",2),
 Map.entry("dcc.catalog.BodyTypeTabs/ApexListLayoutRecord",0),
 Map.entry("dcc.catalog.BodyTypeTabs/ApexNativeRailReceipt",0));
 static void check(boolean v,String m){CasStructuralRolesPatch.check(v,m);}
 static String name(ABC a,int n){return CasStructuralRolesPatch.name(a,n);}
 static String q(ABC a,int n){return CasCommunicationIndexPatch.qname(a,n);}
 static String sha(byte[] b)throws Exception{return CasStructuralRolesPatch.sha(b);}
 static TraitMethodGetterSetter trait(ABC a,Role r,String n){return CasStructuralRolesPatch.trait(a,r.owner,n,r.statik);}
 static MethodBody body(ABC a,Role r,String n){return a.findBody(trait(a,r,n).method_info);}
 static Traits traits(ABC a,Role r){int c=a.findClassByName(r.owner);check(c>=0,"Missing exact owner");return r.statik?a.class_info.get(c).static_traits:a.instance_info.get(c).instance_traits;}
 static TraitSlotConst field(ABC a,Role r,String n){TraitSlotConst got=null;for(var t:traits(a,r).traits)if(t instanceof TraitSlotConst&&name(a,t.name_index).equals(n)){check(got==null,"Ambiguous new slot");got=(TraitSlotConst)t;}check(got!=null,"Missing new slot");return got;}
 static List<String>owned(Role r){var n=new ArrayList<>(r.replaced);n.addAll(r.added);return n;}
 static String semantic(ABC a,MethodBody b)throws Exception{
  String text=CasCommunicationIndexPatch.semanticText(a,b);
  for(String type:List.of("CASCustomizerMain","CatalogPanel","BodyTypeTabs"))text=text.replaceAll("(?<=5:)"+java.util.regex.Pattern.quote(type+".as$")+"[0-9]+",type+".as\\$SELF");
  int start=Integer.MAX_VALUE;for(var op:b.getCode().code)if(CasStructuralRolesPatch.op(op)==0xef&&op.operands.length==4&&op.operands[0]==1&&op.operands[3]>0)start=Math.min(start,op.operands[3]);
  if(start!=Integer.MAX_VALUE){final int origin=start;text=java.util.regex.Pattern.compile("(?m)^(239:1:.*:[0-9]+):([1-9][0-9]*)$").matcher(text).replaceAll(m->m.group(1)+":owned-source+"+(Integer.parseInt(m.group(2))-origin));}
  return sha(text.getBytes(java.nio.charset.StandardCharsets.UTF_8));
 }
 static void reviewed(ABC a,boolean retained)throws Exception{
  boolean actualQualified=false;
  for(var r:ROLES){
   for(String n:owned(r)){
    var t=trait(a,r,n);var b=body(a,r,n);var info=a.method_info.get(t.method_info);String key=r.owner+"/"+n;
    check(semantic(a,b).equals(PINS.get(key)),"Exact reviewed body/CFG differs: "+key);check(info.flags==FLAGS.get(key),"Method flags differ");
    for(var op:b.getCode().code){int code=CasStructuralRolesPatch.op(op);check(!Set.of(0x40,0x43,0x44,0x67).contains(code),"Foreign nested/outer/callmethod linkage");
     if(code==0x60&&name(a,op.operands[0]).equals("flash"))throw new IllegalArgumentException("Unbound flash lookup");
     if(Set.of(0x60,0x46,0x4f).contains(code)&&op.operands.length>0&&name(a,op.operands[0]).equals("getQualifiedClassName")){check(q(a,op.operands[0]).equals("7:getQualifiedClassName:22:flash.utils"),"Runtime QName differs");actualQualified=true;}
    }
    if(r.added.contains(n)){
     check(t.kindType==Trait.TRAIT_METHOD&&(!retained||t.disp_id==0),"Added callable trait shape differs: "+key);
     var mn=a.constants.getMultiname(t.name_index);var ns=a.constants.getNamespace(mn.namespace_index);
     if(r.owner.equals("widgets.CAS.Customizer.CatalogPanel"))check(ns.kind==Namespace.KIND_PACKAGE&&t.kindFlags==Trait.ATTR_Final,"Native witness getters must be final/public");
     else if(n.equals("ApexNativeRailReceipt"))check(ns.kind==Namespace.KIND_PACKAGE&&t.kindFlags==Trait.ATTR_Final,"Exact public static final witness required");
     else check(ns.kind==Namespace.KIND_PRIVATE&&t.kindFlags==(r.statik?Trait.ATTR_Final:0),"Exact private UI helper required: "+key);
     check(info.optional.length==(n.equals("ApexCatalogListRail")?1:0),"Added optional ABI differs");
    }
   }
   for(String n:r.fields){var f=field(a,r,n);var mn=a.constants.getMultiname(f.name_index);var ns=a.constants.getNamespace(mn.namespace_index);
    check(f.kindType==Trait.TRAIT_SLOT&&f.kindFlags==0&&ns.kind==Namespace.KIND_PRIVATE&&f.value_index==0,"Native UI metadata slot shape/default differs");
    check(q(a,f.type_index).equals(n.equals("apexRawListGeneration")?"7:int:22:":"7:Object:22:"),"Native UI metadata type differs");
   }
  }
  check(actualQualified,"Native exact runtime-class proof missing");
 }
 static void sameAbi(ABC a,ABC b,Role r,String n){var x=trait(a,r,n);var y=trait(b,r,n);var p=a.method_info.get(x.method_info);var z=b.method_info.get(y.method_info);
  check(x.kindType==y.kindType&&x.kindFlags==y.kindFlags&&q(a,x.name_index).equals(q(b,y.name_index))&&p.flags==z.flags&&q(a,p.ret_type).equals(q(b,z.ret_type))&&p.param_types.length==z.param_types.length&&p.optional.length==z.optional.length,"Original ABI differs: "+n);
  for(int i=0;i<p.param_types.length;i++)check(q(a,p.param_types[i]).equals(q(b,z.param_types[i])),"Original argument differs");
  for(int i=0;i<p.optional.length;i++)check(p.optional[i].value_kind==z.optional[i].value_kind&&p.optional[i].value_index==z.optional[i].value_index,"Original optional default differs");
 }
 static void bindings(ABC base,ABC a)throws Exception{
  for(var r:ROLES){var all=new HashMap<String,Integer>();for(var t:traits(base,r).traits)all.put(name(base,t.name_index),t.name_index);
   for(String n:owned(r))for(var op:body(a,r,n).getCode().code)if(Set.of(0x66,0x61,0x68,0x60).contains(CasStructuralRolesPatch.op(op))){String f=name(a,op.operands[0]);if(all.containsKey(f))check(q(base,all.get(f)).equals(q(a,op.operands[0])),"Original native/private binding differs: "+r.owner+"/"+n+"/"+f);}
  }
 }
 static void verify(ABC base,ABC a,Map<Integer,String>hashes)throws Exception{
  CasStructuralRolesPatch.prefix(base,a);reviewed(a,true);bindings(base,a);
  check(a.method_info.size()==base.method_info.size()+14&&a.bodies.size()==base.bodies.size()+14,"Exact appended callable inventory differs");
  for(var e:hashes.entrySet())check(sha(a.findBody(e.getKey()).getCodeBytes()).equals(e.getValue()),"Serialized selected body differs");
  for(var b:base.bodies)if(!hashes.containsKey(b.method_info))check(Arrays.equals(b.getCodeBytes(),a.findBody(b.method_info).getCodeBytes()),"Unselected native/constructor body differs");
  var rollback=CasStructuralRolesPatch.reparse(a);
  for(var r:ROLES){for(String n:r.replaced)CasStructuralRolesPatch.replace(rollback,body(base,r,n).clone());var list=traits(rollback,r).traits;int before=traits(base,r).traits.size();check(list.size()==before+r.added.size()+r.fields.size(),"Foreign trait appended");while(list.size()>before)list.remove(list.size()-1);}
  while(rollback.method_info.size()>base.method_info.size())rollback.method_info.remove(rollback.method_info.size()-1);
  while(rollback.bodies.size()>base.bodies.size())rollback.bodies.remove(rollback.bodies.size()-1);
  rollback.constants=base.constants;rollback.resetMethodIndexing();check(Arrays.equals(CasStructuralRolesPatch.save(base),CasStructuralRolesPatch.save(rollback)),"Complete raw ABC rollback differs");
 }
 public static void main(String[]args)throws Exception{
  if(args.length==2&&args[0].equals("--semantic")){var a=CasStructuralRolesPatch.load(args[1]);for(var r:ROLES)for(String n:owned(r)){var b=body(a,r,n);System.out.println(r.owner+"/"+n+" "+semantic(a,b)+" "+a.method_info.get(b.method_info).flags+" scope="+b.init_scope_depth);}return;}
  check(args.length==4,"Exact baseline, compiled, outputABC, proof required");var base=CasStructuralRolesPatch.load(args[0]);var compiled=CasStructuralRolesPatch.load(args[1]);CasStructuralRolesPatch.prefix(base,compiled);reviewed(compiled,false);
  var a=CasStructuralRolesPatch.reparse(base);a.constants=compiled.constants;var hashes=new HashMap<Integer,String>();
  for(var r:ROLES){check(base.findClassByName(r.owner)==compiled.findClassByName(r.owner),"Owner moved");String anchor=r.replaced.get(0);int delta=body(base,r,anchor).init_scope_depth-body(compiled,r,anchor).init_scope_depth;check(delta>=0&&delta<=16,"Scope delta differs");
   for(String n:r.replaced){sameAbi(base,compiled,r,n);var old=body(base,r,n);var made=body(compiled,r,n).clone();made.method_info=old.method_info;made.init_scope_depth+=delta;made.max_scope_depth+=delta;made.setCode(made.getCode());made.setModified();CasStructuralRolesPatch.replace(a,made);hashes.put(made.method_info,sha(made.getCodeBytes()));}
   for(String n:r.added){check(traits(base,r).traits.stream().noneMatch(t->name(base,t.name_index).equals(n)),"Helper already exists");int id=a.method_info.size();var from=body(compiled,r,n);a.method_info.add(compiled.method_info.get(from.method_info));var made=from.clone();made.method_info=id;made.init_scope_depth+=delta;made.max_scope_depth+=delta;made.setCode(made.getCode());made.setModified();a.bodies.add(made);var t=trait(compiled,r,n).clone();t.method_info=id;t.disp_id=0;traits(a,r).traits.add(t);hashes.put(id,sha(made.getCodeBytes()));}
   for(String n:r.fields){check(traits(base,r).traits.stream().noneMatch(t->name(base,t.name_index).equals(n)),"Slot already exists");traits(a,r).traits.add(field(compiled,r,n).clone());}
  }
  a.resetMethodIndexing();verify(base,a,hashes);a=CasStructuralRolesPatch.reparse(a);verify(base,a,hashes);byte[]raw=CasStructuralRolesPatch.save(a);Files.write(Path.of(args[2]),raw);
  String proof="{\"ok\":true,\"changed_original_native_bodies\":4,\"replaced_owned_bodies\":5,\"appended_methods\":14,\"appended_fields\":3,\"whole_abc_rollback_verified\":true,\"all_unowned_bodies_retained\":true,\"serialized_owned_bodies_verified\":true,\"native_protected_bindings_verified\":true,\"constructors_retained\":true,\"runtime_class_QName_verified\":true,\"baseline_swf_sha256\":\""+sha(Files.readAllBytes(Path.of(args[0])))+"\",\"baseline_abc_sha256\":\""+sha(CasStructuralRolesPatch.save(base))+"\",\"abc_sha256\":\""+sha(raw)+"\",\"runtime_qualified\":false,\"performance_gain_claimed\":false}";
  Files.writeString(Path.of(args[3]),proof+"\n");System.out.println(proof);
 }
}
