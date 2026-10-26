// Granular markers exist only in the explicitly profiled Draw tail.
// The null-callback branch and every original native instruction stay exact.
import java.nio.file.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;

public class CasDrawPhasePatch {
 static final String MAIN=CasStructuralRolesPatch.MAIN,CELL=CasStructuralRolesPatch.CELL;
 static final List<String> OWNED=List.of("ApexCatalogTraceConfigure","ApexCatalogTraceStep");
 static final Map<String,Integer> COUNTS=Map.of("overlay",3,"geometry",9,"state",15,"context",11,"tooltip",9);
 static final Map<String,String> SEMANTICS=Map.of("ApexCatalogTraceConfigure","f4cc380bea6e4ea55385cc22b9133deb9750307d70abf119da7b9664561148b2",
  "ApexCatalogTraceStep","59ba48e2346931068847a55b9be674a08521fe015601d28d63f99a5c06d7d6d1");
 static void check(boolean b,String s){CasStructuralRolesPatch.check(b,s);}
 static int op(AVM2Instruction i){return CasStructuralRolesPatch.op(i);}
 static String name(ABC a,int q){return CasStructuralRolesPatch.name(a,q);}
 static MethodBody body(ABC a,String type,String method){return CasStructuralRolesPatch.body(a,type,method,false);}
 static String sha(byte[] b)throws Exception{return CasStructuralRolesPatch.sha(b);}
 static String semantic(ABC a,MethodBody b)throws Exception{
  String text=CasCommunicationIndexPatch.semanticText(a,b).replaceAll("(?<=5:)CASCustomizerMain\\.as\\$[0-9]+","CASCustomizerMain.as\\$SELF");
  // Only the common absolute source offset in owned debug(0xEF) records is
  // irrelevant. Preserve their type/name/register/zero extras/relative gaps;
  // do not normalize an executable operand or any unowned native method.
  int base=Integer.MAX_VALUE;for(var i:b.getCode().code)if(op(i)==0xef&&i.operands.length==4&&i.operands[0]==1&&i.operands[3]>0)base=Math.min(base,i.operands[3]);
  if(base!=Integer.MAX_VALUE){final int offset=base;text=java.util.regex.Pattern.compile("(?m)^(239:1:.*:[0-9]+):([1-9][0-9]*)$").matcher(text).replaceAll(m->m.group(1)+":owned-source+"+(Integer.parseInt(m.group(2))-offset));}
  return sha(text.getBytes(java.nio.charset.StandardCharsets.UTF_8));
 }
 static void timerBinding(ABC a,MethodBody b){
  var bindings=new ArrayList<Integer>();
  for(var i:b.getCode().code){if(!Set.of(0x5d,0x60,0x66,0x46,0x4f).contains(op(i))||i.operands==null||i.operands.length==0)continue;
   String n=name(a,i.operands[0]);if(n==null)continue;check(!Set.of("flash","utils").contains(n),"Granular timer uses an unresolved runtime flash object");
   if(n.equals("getTimer")){check(CasCommunicationIndexPatch.qname(a,i.operands[0]).equals("7:getTimer:22:flash.utils")&&Set.of(0x5d,0x46).contains(op(i))&&(op(i)!=0x46||i.operands[1]==0),"Granular timer must resolve native flash.utils PackageNamespace function");bindings.add(op(i));}}
  check(bindings.equals(List.of(0x5d,0x46)),"Granular diagnostic timer binding inventory differs");
 }
 static void helpers(ABC a)throws Exception {
  check(SEMANTICS.size()==2,"Granular Draw helper semantic inventory is not frozen");
  for(String n:OWNED){var b=body(a,MAIN,n);timerBinding(a,b);check(semantic(a,b).equals(SEMANTICS.get(n)),"Granular Draw helper differs: "+n);}
 }
 static String phase(ABC a,AVM2Instruction i){
  if(!Set.of(0x46,0x4f,0x61,0x68).contains(op(i)))return null;String n=name(a,i.operands[0]);
  if(Set.of(0x46,0x4f).contains(op(i))&&n.equals("gotoAndStop"))return "overlay";
  if(Set.of(0x61,0x68).contains(op(i))&&Set.of("enabled","Selected","visible").contains(n))return "state";
  if(op(i)==0x61&&Set.of("scaleX","scaleY","x","y","alpha").contains(n))return "geometry";
  if(Set.of(0x46,0x4f).contains(op(i))&&Set.of("CallUIService","GetVariation","IsMTX","IsUnviewed","IsLocked","GetCASBrandedProduct","GetPackIcon").contains(n))return "context";
  if(Set.of(0x61,0x46,0x4f).contains(op(i))&&Set.of("Text","Data","HorizontalAlignment","VerticalAlignment","SetText").contains(n))return "tooltip";
  return null;
 }
 static List<AVM2Instruction> stamp(ABC a,String event){
  int literal=a.constants.getStringId(event,false);check(literal>0,"Exact granular marker literal absent: "+event);
  var rest=List.of(CasStructuralRolesPatch.ins(0x62,24),CasStructuralRolesPatch.ins(0x64),CasStructuralRolesPatch.ins(0x2c,literal),CasStructuralRolesPatch.ins(0x20),CasStructuralRolesPatch.ins(0x41,2),CasStructuralRolesPatch.ins(0x29));
  int length=0;for(var i:rest)length+=i.getBytesLength();var out=new ArrayList<AVM2Instruction>();out.add(CasStructuralRolesPatch.ins(0x62,24));out.add(CasStructuralRolesPatch.ins(0x12,length));out.addAll(rest);return out;
 }
 static long target(AVM2Instruction i){check(op(i)>=0x0c&&op(i)<=0x1a,"Expected relative branch");return i.getAddress()+i.getBytesLength()+i.operands[0];}
 static CasStructuralRolesPatch.Rewrite rewrite(ABC a,MethodBody before)throws Exception {
  var old=before.getCode().code;check(old.size()==1783&&before.max_regs==25&&before.exceptions.length==0&&before.traits.traits.isEmpty(),"Exact two-tail Draw inventory differs");
  check(op(old.get(0))==0xd0&&op(old.get(1))==0x30&&CasStructuralRolesPatch.prop(a,old.get(2),0x60,"CASCustomizerMain")&&CasStructuralRolesPatch.prop(a,old.get(3),0x66,"apexCatalogDrawTraceStep")&&op(old.get(4))==0x2a&&op(old.get(5))==0x63&&old.get(5).operands[0]==24&&op(old.get(6))==0x11,"Exact nullable callback Draw envelope differs");
  long profile=target(old.get(6));check(CasStructuralRolesPatch.addresses(before).containsKey(profile),"Draw profile boundary is not an instruction");
  var blocks=new ArrayList<CasStructuralRolesPatch.Block>();var counts=new TreeMap<String,Integer>();
  for(int i=0;i<old.size();i++){if(old.get(i).getAddress()<profile)continue;String n=phase(a,old.get(i));if(n==null)continue;
   var enter=stamp(a,n+".enter");var leave=stamp(a,n+".leave");var original=CasStructuralRolesPatch.copy(old.get(i));
   var code=new ArrayList<AVM2Instruction>(enter);code.add(original);code.addAll(leave);var block=new CasStructuralRolesPatch.Block(i,i+1,code);
   block.edge(enter.get(1),0,CasStructuralRolesPatch.local(original));block.edge(leave.get(1),0,CasStructuralRolesPatch.old(i+1));blocks.add(block);counts.merge(n,1,Integer::sum);}
  check(counts.equals(COUNTS)&&blocks.size()==47,"Exact granular Draw site inventory differs: "+counts);
  var result=CasStructuralRolesPatch.rewrite(before,blocks);for(var block:blocks){int at=result.boundaries.get(block.start);result.origins.set(at+8,block.start);}
  result.body.max_stack=before.max_stack+5;CasStructuralRolesPatch.verifyProjection(before,result,result.body);return result;
 }
 static void verify(ABC base,ABC candidate,CasStructuralRolesPatch.Rewrite plan)throws Exception {
  CasStructuralRolesPatch.prefix(base,candidate);check(candidate.method_info.size()==base.method_info.size()&&candidate.bodies.size()==base.bodies.size(),"Granular profiling must append no methods");helpers(candidate);
  var before=body(base,CELL,"Draw");var after=body(candidate,CELL,"Draw");check(Arrays.equals(after.getCodeBytes(),plan.body.getCodeBytes()),"Granular Draw marker/CFG projection differs");CasStructuralRolesPatch.verifyProjection(before,plan,after);
  check(after.max_stack==before.max_stack+5&&after.max_regs==before.max_regs&&after.init_scope_depth==before.init_scope_depth&&after.max_scope_depth==before.max_scope_depth&&after.traits.traits.isEmpty(),"Granular Draw frame metadata differs");
  int boundary=(int)target(before.getCode().code.get(6));check(Arrays.equals(Arrays.copyOf(before.getCodeBytes(),boundary),Arrays.copyOf(after.getCodeBytes(),boundary)),"Disabled fast path has additional instructions or changed bytes");
  var rollback=CasStructuralRolesPatch.reparse(candidate);CasStructuralRolesPatch.replace(rollback,before.clone());
  for(String n:OWNED){var b=body(candidate,MAIN,n);check(b.init_scope_depth==body(base,MAIN,n).init_scope_depth,"Diagnostic lexical scope changed");CasStructuralRolesPatch.replace(rollback,body(base,MAIN,n).clone());}
  rollback.constants=base.constants;rollback.resetMethodIndexing();check(Arrays.equals(CasStructuralRolesPatch.save(rollback),CasStructuralRolesPatch.save(base)),"Granular profiling changed unowned native data");
  var owned=new HashSet<Integer>();owned.add(before.method_info);for(String n:OWNED)owned.add(body(base,MAIN,n).method_info);
  for(var b:base.bodies)if(!owned.contains(b.method_info))check(Arrays.equals(b.getCodeBytes(),candidate.findBody(b.method_info).getCodeBytes()),"Granular profiling changed another body");
 }
 public static void main(String[] args)throws Exception {
  if(args.length==2&&args[0].equals("--semantic")){var a=CasStructuralRolesPatch.load(args[1]);for(String n:OWNED)System.out.println(n+" "+semantic(a,body(a,MAIN,n)));return;}
  check(args.length==4,"Use previous Main, compiled diagnostic helpers, output ABC and proof");var base=CasStructuralRolesPatch.load(args[0]);var compiled=CasStructuralRolesPatch.load(args[1]);CasStructuralRolesPatch.prefix(base,compiled);helpers(compiled);
  var candidate=CasStructuralRolesPatch.reparse(base);candidate.constants=compiled.constants;
  for(String n:OWNED){var old=body(base,MAIN,n);var source=body(compiled,MAIN,n);var made=source.clone();int delta=old.init_scope_depth-source.init_scope_depth;
   check(delta>=0&&delta<=16,"Granular diagnostic scope delta differs");for(var i:source.getCode().code)check(!Set.of(0x40,0x44,0x67).contains(op(i)),"Granular diagnostic has nested/outer dependencies");
   made.method_info=old.method_info;made.init_scope_depth+=delta;made.max_scope_depth+=delta;made.setCode(made.getCode());made.setModified();CasStructuralRolesPatch.replace(candidate,made);}
  var plan=rewrite(candidate,body(base,CELL,"Draw"));CasStructuralRolesPatch.replace(candidate,plan.body);verify(base,candidate,plan);candidate=CasStructuralRolesPatch.reparse(candidate);verify(base,candidate,plan);
  var result=CasStructuralRolesPatch.save(candidate);Files.write(Path.of(args[2]),result);
  String report="{\"ok\":true,\"phase\":\"opt-in-granular-draw-profile\",\"baseline_swf_sha256\":\""+sha(Files.readAllBytes(Path.of(args[0])))+"\",\"baseline_abc_sha256\":\""+sha(CasStructuralRolesPatch.save(base))+"\",\"abc_sha256\":\""+sha(result)+"\",\"changed_draw_bodies\":1,\"replaced_owned_bodies\":2,\"appended_methods\":0,\"appended_fields\":0,\"disabled_added_instructions\":0,\"granular_sites\":47,\"phase_sites\":{\"overlay\":3,\"geometry\":9,\"state\":15,\"context\":11,\"tooltip\":9},\"disabled_fast_tail_exact\":true,\"existing_profile_markers_retained\":true,\"native_cfg_projection_verified\":true,\"native_throw_propagation_retained\":true,\"whole_abc_rollback_verified\":true,\"all_other_bodies_retained\":true,\"no_borrowed_handles_retained\":true,\"native_timer_namespace_verified\":true,\"runtime_qualified\":false,\"performance_gain_claimed\":false}";Files.writeString(Path.of(args[3]),report+"\n");System.out.println(report);
 }
}
