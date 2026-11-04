// Private exact owned continuation. No native/constructor/click body enters it.
import java.nio.file.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.*;

public class CasGridEofPatch {
 static final String GRID="olympus.layout.RecyclingGridLayout",MAIN="widgets.CAS.Customizer.CASCustomizerMain";
 static final List<String> GRID_REPLACED=List.of("ApexGridDeltaQueue","ApexGridDeltaBorrow","ApexGridDeltaAdvance","ApexGridDeltaPublish","ApexGridDeltaCurrent","ApexGridDeltaRestore","ApexGridDeltaRetarget","ApexGridDeltaStep","ApexGridStatus","ApexGridBegin","ApexGridBeginFrame","ApexGridStep","ApexGridNeedsWork","ApexGridCancel","ApexGridFrameStatusEffects","ApexGridPendingFrame","ApexGridGeometryFrame","ApexGridNativeGuard","ApexGridNativeSetCellView","ApexGridPoolOwns","ApexGridPoolCoherent","ApexGridPoolSlot","ApexGridPoolDataIndex","ApexGridCells","ApexGridCellsY","ApexGridMap");
 static final List<String> GRID_ADDED=List.of("ApexGridDeltaEofWindow","ApexGridDeltaEofReady","ApexGridDeltaBorrowEof","ApexGridAuthorityScope","ApexGridAuthorityCapture","ApexGridAuthorityProbe","ApexGridAuthorityCurrent","ApexGridAuthorityOldCell","ApexGridAuthorityBank","ApexGridAuthorityReleaseCurrent","ApexGridAuthorityLose","ApexGridAuthorityStatus","ApexGridAuthorityDispose","ApexGridAuthorityRecover");
 static final Map<String,String> PINS=Map.ofEntries(
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaQueue","70e341803f9aa2c499d75de0123158a1c8fe6073f3e7a42fbdfabdc188a8e9d7"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaBorrow","84d9eb5b41794730afed1c804e202c36e2901d1cc9f10bfa3e09c68d0351b35a"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaAdvance","086b04c71f53a1cfe4c2b565f9cac0932c75e4db2f858a0501df675dacfde258"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaPublish","88001328b6309a68e96ac782713f9c40c7735ebe271ad395875846b8ec9c9b2c"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaCurrent","008ce3b0485ddfa4cf62166655bd5f63c2ec5fec62b93bf6ea7cf5c912e48161"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaRestore","fcd540d280594be2d85d1a1a50b50232d19929fb7baf33cf20bbb26437a2749e"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaRetarget","0759ba95d2d9b62c035d68d9a258b19c43aa7225b4eb437d6d9188e8b2120427"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaStep","0e00b523a459f3f99bc76e74540ecd902aa36e6cf0050df6614c309354c70e42"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridStatus","4d7438451077d24635f4f817563d0d13315278490feec2285e2a9e21d2a4bc97"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridBegin","ae829450eb8ad02424421dc98c21855b37216585c33e77f4eed0450095b01f3d"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridBeginFrame","d87ab8007a1a7c26668c26484ae057478dfd03892e1c3304943ac2072268807a"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridStep","4843b7c8b400ba6c23725d5da0627bd13d605e34340e111108a12096eb877c2e"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridNeedsWork","a27ab067f8e0fefb0aa3309caccf60f68ffbf7e8536ddd73d6b7e1d1bf82722c"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridCancel","ae62762bc8f7db774a58f421e384ae7c15753421a4d9ff351cd5d7a15c8d1029"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridFrameStatusEffects","18b6bee2ab00cfefa2b4c8962afaf93aff101a5186a1c37898c7737802cfffd0"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridPendingFrame","fb6910599f4c9753e0b537ad1b6fd522ad02545a314a944543fdced1bed3170a"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridGeometryFrame","195974d67d5b74e713142ffc2c1fd9676ce316bb421921e1385e2ba5dea62d34"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridNativeGuard","c1dff6374ec1cb5564dccae45e4707e9977f71f7d738509521c0ca12f076381f"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridNativeSetCellView","1efe02a2a2c3db2e91d2f99ec18691e564258c3e6fc277c9d1406e9649f255a3"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridPoolOwns","0cf411199fe19d6210643a75a863971d48f228ba5becedbcf5a1d7db6427a75b"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridPoolCoherent","0813322de5e770cf51894b54247e1345e1177ee429b0df1d078dde38d50e53f7"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridPoolSlot","d200db63b1c36878a981ef5e09dbee954042d5a62e0d6f6c1ac8365fd49f022d"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridPoolDataIndex","24a63f4b1f9c25c01fc1ea6a1df0a8ad805a44efc2dd74c2af20349b26cb16c3"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridCells","f65a28fac64f50d1b8fb180fe0871f479b464f2f5d40e2d20cd5ad98ed52ba82"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridCellsY","44e8c33c2d491ee1577af85e94fb9c48456532fb760e09ca06d8f06d9b238a58"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridMap","abbd56544f58fc8208970d0d8fcf6d23904e490041b47f40f2ae09117f4b3f33"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaEofWindow","b7764f755dfad06b19a1e413f46212677ca3f90b063bbac3dcb56183afe03068"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaEofReady","6f614ef769c72c0b6c4f9641af05cc18154b90668482c9aa92635ac575cbf26a"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaBorrowEof","90a0bab426102ab0925b3550e1463b76f31b792b4c09f52f4318e1d387a05e01"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridAuthorityScope","cad476e04d70d177415cbf94c7d4a679abbcce01dc676cad049ae31a7e3bd4cb"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridAuthorityCapture","33b067fd9240d385168f629c35f7357599a62a3cd52c3e267b703e1e84754cdc"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridAuthorityProbe","9331ea6fbd80435a7a464b886890c51d9e481165594f957d8e32e3bf84a46ffa"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridAuthorityCurrent","0de9d50c8cd83a2cc0a549963f1932654483d03cd4e84e11e0a8e68dd2f8e913"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridAuthorityOldCell","45e02297bf67d8ad18fff285028e923e414430cbd2612efc482e44649228890d"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridAuthorityBank","eeeda0561b490ac5e601c91479050b10e7ff9bfd4c34421a7202a33671df7e3d"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridAuthorityReleaseCurrent","d3703a18052d2c020e48125ad8453ccf5ee782c7113ebd66da6bae274d4beb1f"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridAuthorityLose","fde006f86ca91e2ade203d2643eff6e5e7d6f5697f569ec3a10632d991819de1"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridAuthorityStatus","d9ffefaa44f21d5f73332f7b0fc45f07a191f7db710b42b1ce192e9bfbe1d12c"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridAuthorityDispose","758dd5d0ff1bdcabc15ff908523ad24c22acba115742708aa7e6b45fbdc54253"),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridAuthorityRecover","65e2465ba357758ffaa7a1857e1ddcb1b1706401f54651ba1cf48cc68bc91292")
 );
 static final Map<String,Integer> FLAGS=Map.ofEntries(
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaQueue",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaBorrow",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaAdvance",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaPublish",2),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaCurrent",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaRestore",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaRetarget",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaStep",2),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridStatus",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridBegin",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridBeginFrame",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridStep",8),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridNeedsWork",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridCancel",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridFrameStatusEffects",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridPendingFrame",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridGeometryFrame",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridNativeGuard",8),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridNativeSetCellView",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridPoolOwns",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridPoolCoherent",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridPoolSlot",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridPoolDataIndex",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridCells",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridCellsY",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridMap",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaEofWindow",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaEofReady",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridDeltaBorrowEof",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridAuthorityScope",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridAuthorityCapture",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridAuthorityProbe",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridAuthorityCurrent",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridAuthorityOldCell",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridAuthorityBank",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridAuthorityReleaseCurrent",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridAuthorityLose",2),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridAuthorityStatus",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridAuthorityDispose",0),
 Map.entry("olympus.layout.RecyclingGridLayout/ApexGridAuthorityRecover",0)
 );
 static void check(boolean v,String message){CasStructuralRolesPatch.check(v,message);}
 static String name(ABC a,int n){return CasStructuralRolesPatch.name(a,n);}
 static TraitMethodGetterSetter trait(ABC a,String type,String method){return CasStructuralRolesPatch.trait(a,type,method,false);}
 static MethodBody body(ABC a,String type,String method){return a.findBody(trait(a,type,method).method_info);}
 static String sha(byte[] raw)throws Exception{return CasStructuralRolesPatch.sha(raw);}
 static String owner(String mode){check(mode.equals("grid"),"Exact EOF provider mode required");return mode.equals("grid")?GRID:MAIN;}
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
   check(semantic(a,b).equals(PINS.get(type+"/"+n)),"Reviewed EOF schema semantic/CFG differs: "+n);
   check(info.flags==FLAGS.get(type+"/"+n),"Reviewed method flags differ: "+n);
   for(var op:b.getCode().code){int code=CasStructuralRolesPatch.op(op);check(!Set.of(0x40,0x43,0x44,0x67).contains(code),"Nested/outer/callmethod linkage: "+n);
    if(Set.of(0x60,0x46,0x4f).contains(code)&&op.operands.length>0&&name(a,op.operands[0]).equals("getQualifiedClassName")){
     check(CasCommunicationIndexPatch.qname(a,op.operands[0]).equals("7:getQualifiedClassName:22:flash.utils"),"Real exact runtime class getter QName required");qname=true;
    }
    if(code==0x60&&name(a,op.operands[0]).equals("flash"))throw new IllegalStateException("Unbound flash package lookup");
   }
   if(added(mode).contains(n)){
    var q=a.constants.getMultiname(t.name_index);var ns=a.constants.getNamespace(q.namespace_index);
    boolean exposed=n.equals("ApexGridAuthorityStatus");
    check(t.kindType==Trait.TRAIT_METHOD&&t.kindFlags==(exposed?1:0)&&q.kind==Multiname.QNAME&& (exposed?ns.kind==Namespace.KIND_PACKAGE&&a.constants.getString(ns.name_index).isEmpty():ns.kind==Namespace.KIND_PRIVATE&&a.constants.getString(ns.name_index).equals("olympus.layout:RecyclingGridLayout")),"Appended helper namespace/kind differs");
    check(info.optional.length==0,"No new optional callable defaults");
   }
  }
  check(!mode.equals("grid")||qname,"Native runtime class proof getter absent");
 }
 static TraitSlotConst authorityField(ABC a){
  TraitSlotConst found=null;for(var t:a.instance_info.get(a.findClassByName(GRID)).instance_traits.traits)if(name(a,t.name_index).equals("apexGridAuthority")){check(found==null&&t instanceof TraitSlotConst,"Authority field absent/ambiguous");found=(TraitSlotConst)t;}
  check(found!=null,"Authority field missing");var q=a.constants.getMultiname(found.name_index);var ns=a.constants.getNamespace(q.namespace_index);
  check(found.kindType==Trait.TRAIT_SLOT&&found.kindFlags==0&&found.slot_id==0&&found.value_index==0&&name(a,found.type_index).equals("Object")&&q.kind==Multiname.QNAME&&ns.kind==Namespace.KIND_PRIVATE&&a.constants.getString(ns.name_index).equals("olympus.layout:RecyclingGridLayout"),"Authority must be exact auto private default-null Object");return found;
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
  String type=owner(mode);int count=added(mode).size();CasStructuralRolesPatch.prefix(base,a);authorityField(a);helpers(a,mode);binding(base,a,mode,hashes.keySet());
  check(a.method_info.size()==base.method_info.size()+count&&a.bodies.size()==base.bodies.size()+count,"Only exact appended method/body count permitted");
  for(var e:hashes.entrySet())check(sha(a.findBody(e.getKey()).getCodeBytes()).equals(e.getValue()),"Serialized owned body differs");
  for(var b:base.bodies)if(!hashes.containsKey(b.method_info))check(Arrays.equals(b.getCodeBytes(),a.findBody(b.method_info).getCodeBytes()),"Original native/unowned body differs");
  var rollback=CasStructuralRolesPatch.reparse(a);for(String n:replaced(mode))CasStructuralRolesPatch.replace(rollback,body(base,type,n).clone());
  var traits=rollback.instance_info.get(rollback.findClassByName(type)).instance_traits.traits;int old=base.instance_info.get(base.findClassByName(type)).instance_traits.traits.size();
  check(traits.size()==old+count+1&&traits.get(old) instanceof TraitSlotConst&&name(rollback,traits.get(old).name_index).equals("apexGridAuthority"),"Only exact appended authority field and helper traits permitted");while(traits.size()>old)traits.remove(traits.size()-1);
  while(rollback.method_info.size()>base.method_info.size())rollback.method_info.remove(rollback.method_info.size()-1);
  while(rollback.bodies.size()>base.bodies.size())rollback.bodies.remove(rollback.bodies.size()-1);
  rollback.constants=base.constants;rollback.resetMethodIndexing();check(Arrays.equals(CasStructuralRolesPatch.save(base),CasStructuralRolesPatch.save(rollback)),"Complete raw ABC rollback differs");
 }
 public static void main(String[] args)throws Exception{
  if(args.length==3&&args[0].equals("--semantic")){String mode=args[1],type=owner(mode);var a=CasStructuralRolesPatch.load(args[2]);for(String n:owned(mode)){var b=body(a,type,n);System.out.println(type+"/"+n+" "+semantic(a,b)+" "+a.method_info.get(b.method_info).flags+" scope="+b.init_scope_depth+" exceptions="+b.exceptions.length+" activation="+b.traits.traits.size());}return;}
  check(args.length==5,"Mode, exact previous SWF, compiled SWF, output ABC, proof required");String mode=args[0],type=owner(mode);var base=CasStructuralRolesPatch.load(args[1]);var compiled=CasStructuralRolesPatch.load(args[2]);
  CasStructuralRolesPatch.prefix(base,compiled);helpers(compiled,mode);var a=CasStructuralRolesPatch.reparse(base);a.constants=compiled.constants;var hashes=new HashMap<Integer,String>();int index=a.findClassByName(type);check(index==compiled.findClassByName(type),"Compiler moved owner class");
  String slotProof=CasGridSlotAudit.audit(args[1]);
  check(base.instance_info.get(index).instance_traits.traits.stream().noneMatch(t->name(base,t.name_index).equals("apexGridAuthority")),"Authority slot already exists");
  var field=authorityField(compiled).clone();field.slot_id=0;a.instance_info.get(index).instance_traits.traits.add(field);
  String anchor=mode.equals("grid")?"ApexTxnStep":"ApexCatalogGridRequest";int delta=body(base,type,anchor).init_scope_depth-body(compiled,type,anchor).init_scope_depth;check(delta>=0&&delta<=16,"Lexical scope adjustment differs");
  for(String n:replaced(mode)){sameAbi(base,compiled,type,n);var old=body(base,type,n);var made=body(compiled,type,n).clone();made.method_info=old.method_info;made.init_scope_depth+=delta;made.max_scope_depth+=delta;made.setCode(made.getCode());made.setModified();CasStructuralRolesPatch.replace(a,made);hashes.put(made.method_info,sha(made.getCodeBytes()));}
  for(String n:added(mode)){check(base.instance_info.get(index).instance_traits.traits.stream().noneMatch(t->name(base,t.name_index).equals(n)),"Added method already present");var source=body(compiled,type,n);int id=a.method_info.size();a.method_info.add(compiled.method_info.get(source.method_info));var made=source.clone();made.method_info=id;made.init_scope_depth+=delta;made.max_scope_depth+=delta;made.setCode(made.getCode());made.setModified();a.bodies.add(made);var t=trait(compiled,type,n).clone();t.method_info=id;t.disp_id=0;a.instance_info.get(index).instance_traits.traits.add(t);hashes.put(id,sha(made.getCodeBytes()));}
  a.resetMethodIndexing();verify(base,a,mode,hashes);a=CasStructuralRolesPatch.reparse(a);verify(base,a,mode,hashes);byte[] out=CasStructuralRolesPatch.save(a);Files.write(Path.of(args[3]),out);
  String proof="{\"ok\":true,\"mode\":\""+mode+"\",\"replaced_owned_bodies\":"+replaced(mode).size()+",\"appended_methods\":"+added(mode).size()+",\"appended_fields\":1,\"activation_slot_receivers_verified\":true,\"changed_original_native_bodies\":0,\"whole_abc_rollback_verified\":true,\"all_unowned_bodies_retained\":true,\"serialized_owned_bodies_verified\":true,\"native_protected_bindings_verified\":true,\"runtime_class_QName_verified\":"+mode.equals("grid")+",\"baseline_swf_sha256\":\""+sha(Files.readAllBytes(Path.of(args[1])))+"\",\"baseline_abc_sha256\":\""+sha(CasStructuralRolesPatch.save(base))+"\",\"abc_sha256\":\""+sha(out)+"\",\"runtime_qualified\":false,\"performance_gain_claimed\":false}";
  proof=proof.substring(0,proof.length()-1)+",\"slot_abi_audit\":"+slotProof+"}";
  Files.writeString(Path.of(args[4]),proof+"\n");System.out.println(proof);
 }
}

/** Fail-closed dataflow proof for appending one auto-numbered UI instance slot.
 * Direct getslot/setslot receivers in all affected descendants must be local
 * activation/catch objects, never the native instance or an unknown value.
 */
final class CasGridSlotAudit {
 static final int OTHER=0,THIS=1,ACTIVATION=2,CATCH=3;
 static void check(boolean b,String m){if(!b)throw new IllegalStateException(m);}
 static final class State {
  final ArrayList<Integer> stack=new ArrayList<>(),scope=new ArrayList<>(); final int[] local;
  State(int n){local=new int[n];local[0]=THIS;}
  State(State s){local=s.local.clone();stack.addAll(s.stack);scope.addAll(s.scope);}
  int pop(){check(!stack.isEmpty(),"Stack underflow");return stack.remove(stack.size()-1);}
  boolean merge(State from){
   check(stack.size()==from.stack.size()&&scope.size()==from.scope.size(),"CFG stack/scope mismatch");boolean changed=false;
   for(int i=0;i<local.length;i++)if(local[i]!=from.local[i]&&local[i]!=OTHER){local[i]=OTHER;changed=true;}
   for(int i=0;i<stack.size();i++)if(!stack.get(i).equals(from.stack.get(i))&&stack.get(i)!=OTHER){stack.set(i,OTHER);changed=true;}
   for(int i=0;i<scope.size();i++)if(!scope.get(i).equals(from.scope.get(i))&&scope.get(i)!=OTHER){scope.set(i,OTHER);changed=true;}
   return changed;
  }
 }
 static int count(ABC a,MethodBody body){
  var ops=body.getCode().code;var byAddress=new HashMap<Long,Integer>();for(int i=0;i<ops.size();i++)byAddress.put(ops.get(i).getAddress(),i);
  var states=new HashMap<Integer,State>();var queue=new ArrayDeque<Integer>();states.put(0,new State(body.max_regs));queue.add(0);var receivers=new HashMap<Integer,Integer>();
  int rounds=0;while(!queue.isEmpty()){
   check(++rounds<1000000,"Dataflow failed to converge");int index=queue.remove();State before=states.get(index),s=new State(before);AVM2Instruction op=ops.get(index);int code=op.definition.instructionCode;
   if(code==0x6c||code==0x6d){int at=s.stack.size()-(code==0x6c?1:2);check(at>=0,"Missing direct-slot receiver");int value=s.stack.get(at);check(value==ACTIVATION||value==CATCH,"Direct-slot receiver is native/unknown at method "+body.method_info+" byte "+op.getAddress());receivers.put(index,value);}
   if(code==0x2a){int value=s.pop();s.stack.add(value);s.stack.add(value);}
   else if(code==0x2b){int b=s.pop(),v=s.pop();s.stack.add(b);s.stack.add(v);}
   else if(code==0x30||code==0x1c)s.scope.add(s.pop());
   else if(code==0x1d){check(!s.scope.isEmpty(),"Scope underflow");s.scope.remove(s.scope.size()-1);}
   else if(code==0x65){int n=op.operands[0];check(n>=0&&n<s.scope.size(),"Unhandled captured scope receiver");s.stack.add(s.scope.get(n));}
   else if(code==0x62||code>=0xd0&&code<=0xd3)s.stack.add(s.local[code==0x62?op.operands[0]:code-0xd0]);
   else if(code==0x63||code>=0xd4&&code<=0xd7)s.local[code==0x63?op.operands[0]:code-0xd4]=s.pop();
   else if(code==0x08)s.local[op.operands[0]]=OTHER;
   else if(code==0x57)s.stack.add(ACTIVATION);
   else if(code==0x5a)s.stack.add(CATCH);
   else {int pop=op.definition.getStackPopCount(op,a),push=op.definition.getStackPushCount(op,a);check(pop>=0&&push>=0,"Unknown stack transfer");for(int i=0;i<pop;i++)s.pop();for(int i=0;i<push;i++)s.stack.add(OTHER);}
   ArrayList<Integer> next=new ArrayList<>();
   if(code==0x1b){for(long target:op.getOffsets()){Integer n=byAddress.get(target);check(n!=null,"Switch target missing");next.add(n);}}
   else if(code>=0x0c&&code<=0x1a){Integer n=byAddress.get(op.getTargetAddress());check(n!=null,"Branch target missing");next.add(n);if(code!=0x10&&index+1<ops.size())next.add(index+1);}
   else if(!op.definition.isExitInstruction()&&index+1<ops.size())next.add(index+1);
   for(int n:next)enqueue(states,queue,n,s);
   if(op.definition.canThrow)for(var e:body.exceptions)if(op.getAddress()>=e.start&&op.getAddress()<e.end){Integer n=byAddress.get((long)e.target);check(n!=null,"Handler target missing");State handler=new State(before);handler.stack.clear();handler.stack.add(OTHER);handler.scope.clear();enqueue(states,queue,n,handler);}
  }
  int literal=0;for(int i=0;i<ops.size();i++)if(ops.get(i).definition.instructionCode==0x6c||ops.get(i).definition.instructionCode==0x6d){literal++;check(receivers.containsKey(i),"Unreachable direct-slot op not proven");}
  return literal;
 }
 static void enqueue(Map<Integer,State> states,Deque<Integer> queue,int n,State s){State prior=states.get(n);if(prior==null){states.put(n,new State(s));queue.add(n);}else if(prior.merge(s))queue.add(n);}
 static String audit(String path)throws Exception{
  ABC a=CasStructuralRolesPatch.load(path);String grid="olympus.layout.RecyclingGridLayout";int owner=a.findClassByName(grid);check(owner>=0,"Owner absent");Set<Integer> affected=new HashSet<>();affected.add(owner);boolean more=true;
  while(more){more=false;for(int i=0;i<a.instance_info.size();i++)if(!affected.contains(i))for(int p:new HashSet<>(affected))if(CasCommunicationIndexPatch.qname(a,a.instance_info.get(i).super_index).equals(CasCommunicationIndexPatch.qname(a,a.instance_info.get(p).name_index))){affected.add(i);more=true;break;}}
  Set<Integer> methods=new TreeSet<>();int slots=0;for(int i:affected){var ci=a.instance_info.get(i);methods.add(ci.iinit_index);methods.add(a.class_info.get(i).cinit_index);for(var t:ci.instance_traits.traits){if(t instanceof TraitSlotConst slot){check(slot.slot_id==0,"Explicit instance slot conflicts with append");slots++;}if(t instanceof TraitMethodGetterSetter method)methods.add(method.method_info);}}
  int direct=0,withSlots=0;for(int method:methods){MethodBody b=a.findBody(method);check(b!=null,"Affected body absent");boolean uses=b.getCode().code.stream().anyMatch(x->x.definition.instructionCode==0x6c||x.definition.instructionCode==0x6d);if(uses){check((a.method_info.get(method).flags&2)!=0,"Direct slot outside activation method");int n=count(a,b);direct+=n;withSlots++;}}
  return "{\"ok\":true,\"source_swf_sha256\":\""+CasStructuralRolesPatch.sha(Files.readAllBytes(Path.of(path)))+"\",\"affected_classes\":"+affected.size()+",\"auto_instance_slots\":"+slots+",\"affected_methods\":"+methods.size()+",\"activation_methods_with_slots\":"+withSlots+",\"proven_activation_or_catch_slot_receivers\":"+direct+",\"unhandled_receivers\":0}";
 }
 public static void main(String[] args)throws Exception {check(args.length==1,"One authenticated provider SWF required");System.out.println(audit(args[0]));}
}
