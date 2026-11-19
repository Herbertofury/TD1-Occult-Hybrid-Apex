// Exact native override + three owned diagnostic bodies; no new fields/traits.
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
public class CasGridPositionPatch {
 static final String REC="olympus.layout.RecyclingGridLayout",SEL="olympus.layout.SelectableRecyclingGridLayout";
 record Target(String owner,String name) {String key(){return owner+"/"+name;}}
 static final List<Target> TARGETS=List.of(new Target(SEL,"PositionCells"),new Target(REC,"ApexGridBegin"),new Target(REC,"ApexGridNativeGuard"),new Target(REC,"ApexGridMetrics"));
 static final Map<String,String> PINS=Map.ofEntries(
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridBegin","a94384b65066837044924f1c2b5151b1c47a1c2b8bb9dd879dfac3f503a0b7be"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridMetrics","ea340ca71e1dff5baf80bc0b84bbd062181bee6407e08ffbd75c89b569c971b1"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridNativeGuard","6de9affa556de4f53f9e380b35d4f8135b33d988b4444ed046c34adb587aca43"),
 Map.entry("olympus.layout.SelectableRecyclingGridLayout/PositionCells","378ae65da25b654d55e945e971db60e65474064a29ec70cbcffad46a88e4b099")
 );
 static final Map<String,Integer> FLAGS=Map.ofEntries(
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridBegin",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridMetrics",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridNativeGuard",8),
 Map.entry("olympus.layout.SelectableRecyclingGridLayout/PositionCells",0)
 );
 static void check(boolean b,String s){CasStructuralRolesPatch.check(b,s);}
 static String sha(byte[] b)throws Exception{return CasStructuralRolesPatch.sha(b);}
 static TraitMethodGetterSetter trait(ABC a,Target t){return CasStructuralRolesPatch.trait(a,t.owner,t.name,false);}
 static MethodBody body(ABC a,Target t){return a.findBody(trait(a,t).method_info);}
 static String semantic(ABC a,MethodBody b)throws Exception{
  String text=CasCommunicationIndexPatch.semanticText(a,b);
  for(String simple:List.of("RecyclingGridLayout","SelectableRecyclingGridLayout"))text=text.replaceAll("(?<=5:)"+java.util.regex.Pattern.quote(simple+".as$")+"[0-9]+",simple+".as\\$SELF");
  int start=Integer.MAX_VALUE;for(var op:b.getCode().code)if(CasStructuralRolesPatch.op(op)==0xef&&op.operands.length==4&&op.operands[0]==1&&op.operands[3]>0)start=Math.min(start,op.operands[3]);
  if(start!=Integer.MAX_VALUE){final int origin=start;text=java.util.regex.Pattern.compile("(?m)^(239:1:.*:[0-9]+):([1-9][0-9]*)$").matcher(text).replaceAll(m->m.group(1)+":owned-source+"+(Integer.parseInt(m.group(2))-origin));}
  return sha(text.getBytes(StandardCharsets.UTF_8));
 }
 static void helpers(ABC a)throws Exception{
  for(Target t:TARGETS){var b=body(a,t);var info=a.method_info.get(trait(a,t).method_info);
   check(semantic(a,b).equals(PINS.get(t.key())),"Reviewed native-position/event semantic differs: "+t.key());check(info.flags==FLAGS.get(t.key()),"Callable flags differ");
   for(var op:b.getCode().code)check(!Set.of(0x40,0x43,0x44,0x67).contains(CasStructuralRolesPatch.op(op)),"Foreign nested/outer linkage");
  }
 }
 static void abi(ABC base,ABC made,Target t){
  var x=trait(base,t);var y=trait(made,t);var a=base.method_info.get(x.method_info);var b=made.method_info.get(y.method_info);
  check(x.kindType==y.kindType&&x.kindFlags==y.kindFlags&&a.flags==b.flags&&a.param_types.length==b.param_types.length&&a.optional.length==b.optional.length&&CasCommunicationIndexPatch.qname(base,a.ret_type).equals(CasCommunicationIndexPatch.qname(made,b.ret_type)),"Original native/owned callable ABI differs");
  for(int i=0;i<a.param_types.length;i++)check(CasCommunicationIndexPatch.qname(base,a.param_types[i]).equals(CasCommunicationIndexPatch.qname(made,b.param_types[i])),"Parameter ABI differs");
  for(int i=0;i<a.optional.length;i++)check(a.optional[i].value_kind==b.optional[i].value_kind&&a.optional[i].value_index==b.optional[i].value_index,"Original optional default differs");
 }
 static void verify(ABC base,ABC a,Map<Integer,String> hashes)throws Exception{
  CasStructuralRolesPatch.prefix(base,a);helpers(a);CasGridPoolPatch.binding(a,hashes.keySet());
  check(a.method_info.size()==base.method_info.size()&&a.bodies.size()==base.bodies.size(),"No new callable/body permitted");
  for(var e:hashes.entrySet())check(sha(a.findBody(e.getKey()).getCodeBytes()).equals(e.getValue()),"Serialized replacement differs");
  for(var b:base.bodies)if(!hashes.containsKey(b.method_info))check(Arrays.equals(b.getCodeBytes(),a.findBody(b.method_info).getCodeBytes()),"Unmodified native/owned body differs");
  var rollback=CasStructuralRolesPatch.reparse(a);for(Target t:TARGETS)CasStructuralRolesPatch.replace(rollback,body(base,t).clone());
  rollback.constants=base.constants;rollback.resetMethodIndexing();check(Arrays.equals(CasStructuralRolesPatch.save(base),CasStructuralRolesPatch.save(rollback)),"Complete raw ABC rollback differs");
 }
 public static void main(String[] args)throws Exception{
  if(args.length==3&&args[0].equals("--semantic")){check(args[1].equals("grid"),"Grid mode required");var a=CasStructuralRolesPatch.load(args[2]);for(Target t:TARGETS){var b=body(a,t);System.out.println(t.key()+" "+semantic(a,b)+" "+a.method_info.get(trait(a,t).method_info).flags+" scope="+b.init_scope_depth+" exceptions="+b.exceptions.length);}return;}
  check(args.length==5&&args[0].equals("grid"),"Grid mode, exact previous, compiled, ABC, proof required");var base=CasStructuralRolesPatch.load(args[1]);var compiled=CasStructuralRolesPatch.load(args[2]);
  check(semantic(base,body(base,TARGETS.get(0))).equals("e583a9e109d5f239ef2bf1e9cb8e0b9c171cd91f9d4cc1e18f667410866e5fe3"),"Exact native override predecessor differs");
  CasStructuralRolesPatch.prefix(base,compiled);helpers(compiled);var a=CasStructuralRolesPatch.reparse(base);a.constants=compiled.constants;var hashes=new HashMap<Integer,String>();
  for(Target t:TARGETS){abi(base,compiled,t);var old=body(base,t);var source=body(compiled,t);var anchor=new Target(t.owner,t.owner.equals(SEL)?"PositionCells":"ApexTxnStep");int delta=body(base,anchor).init_scope_depth-body(compiled,anchor).init_scope_depth;
   check(delta>=0&&delta<=16,"Exact class lexical scope adjustment differs");var made=source.clone();made.method_info=old.method_info;made.init_scope_depth+=delta;made.max_scope_depth+=delta;made.setCode(made.getCode());made.setModified();CasStructuralRolesPatch.replace(a,made);hashes.put(made.method_info,sha(made.getCodeBytes()));
  }
  a.resetMethodIndexing();verify(base,a,hashes);a=CasStructuralRolesPatch.reparse(a);verify(base,a,hashes);byte[] raw=CasStructuralRolesPatch.save(a);Files.write(Path.of(args[3]),raw);
  String proof="{\"ok\":true,\"mode\":\"grid\",\"replaced_owned_bodies\":3,\"replaced_native_bodies\":1,\"appended_methods\":0,\"appended_fields\":0,\"changed_original_native_bodies\":1,\"whole_abc_rollback_verified\":true,\"all_unowned_bodies_retained\":true,\"serialized_owned_bodies_verified\":true,\"native_protected_bindings_verified\":true,\"runtime_class_QName_verified\":false,\"baseline_swf_sha256\":\""+sha(Files.readAllBytes(Path.of(args[1])))+"\",\"baseline_abc_sha256\":\""+sha(CasStructuralRolesPatch.save(base))+"\",\"abc_sha256\":\""+sha(raw)+"\",\"runtime_qualified\":false,\"performance_gain_claimed\":false}";
  Files.writeString(Path.of(args[4]),proof+"\n");System.out.println(proof);
 }
}
