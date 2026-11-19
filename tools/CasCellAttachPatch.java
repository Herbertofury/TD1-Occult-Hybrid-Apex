// Delete only a dead donor half-scale write, retaining final authoritative X/Y.
import java.nio.file.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;

public class CasCellAttachPatch {
 static final String CELL="widgets.CAS.controls.CASClothingPanelCellViewMain",MAIN="widgets.CAS.Customizer.CASCustomizerMain";
 static final String DONOR="c97afa8f0362a0452b359074769b9c99174444dd211927d08972091db3391969";
 static void check(boolean b,String s){CasStructuralRolesPatch.check(b,s);}
 static MethodBody body(ABC a){return CasStructuralRolesPatch.body(a,CELL,"ConfigUI",false);}
 static int op(com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction i){return i.definition.instructionCode;}
 static boolean prop(ABC a,com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction i,int op,String n){return CasStructuralRolesPatch.prop(a,i,op,n);}
 static int deadWrite(ABC a)throws Exception {
  var b=body(a);check(b.exceptions.length==0,"Native ConfigUI exception boundary differs");var code=b.getCode().code;int found=-1;
  for(int j=0;j+12<code.size();j++)if(op(code.get(j))==0xd0&&op(code.get(j+1))==0x24&&code.get(j+1).operands[0]==1&&op(code.get(j+2))==0x24&&code.get(j+2).operands[0]==2&&op(code.get(j+3))==0xa3&&prop(a,code.get(j+4),0x61,"scaleX")){
   check(found<0,"Ambiguous donor half-scale write");
   check(op(code.get(j+5))==0xd0&&prop(a,code.get(j+6),0x60,"CASCustomizerMain")&&prop(a,code.get(j+7),0x66,"modded_thumbnail_scale")&&prop(a,code.get(j+8),0x61,"scaleX")&&
    op(code.get(j+9))==0xd0&&prop(a,code.get(j+10),0x60,"CASCustomizerMain")&&prop(a,code.get(j+11),0x66,"modded_thumbnail_scale")&&prop(a,code.get(j+12),0x61,"scaleY"),"Half-scale write is not immediately overwritten by exact native X/Y slot reads");
   var x=a.constants.getMultiname(code.get(j+4).operands[0]);check(code.get(j+4).operands[0]==code.get(j+8).operands[0]&&x.kind==Multiname.QNAME,"Dead write does not bind exact final native scaleX");
   int c=a.findClassByName(MAIN);boolean slot=false;for(var t:a.class_info.get(c).static_traits.traits)if(t.name_index==code.get(j+7).operands[0]){check(t instanceof com.jpexs.decompiler.flash.abc.types.traits.TraitSlotConst,"Final scale must be a static data slot, never a user getter");slot=true;}
   check(slot&&code.get(j+7).operands[0]==code.get(j+11).operands[0],"Final X/Y scaling does not use one authoritative static slot");found=j;
  }
  check(found>=2,"Pinned dead ConfigUI scale assignment absent");return found;
 }
 static CasStructuralRolesPatch.Rewrite rewrite(ABC a)throws Exception {
  var before=body(a);int at=deadWrite(a);var code=before.getCode().code;
  // Include one retained predecessor because the generic rewrite supports
  // nonempty replacement blocks. No branch may enter the removed side effect.
  var keep=CasStructuralRolesPatch.copy(code.get(at-1));var r=CasStructuralRolesPatch.rewrite(before,List.of(new CasStructuralRolesPatch.Block(at-1,at+5,List.of(keep))));
  r.origins.set(at-1,at-1);CasStructuralRolesPatch.verifyProjection(before,r,r.body);return r;
 }
 static void verify(ABC donor,ABC base,ABC candidate,CasStructuralRolesPatch.Rewrite change)throws Exception {
  CasStructuralRolesPatch.prefix(base,candidate);check(Arrays.equals(body(donor).getCodeBytes(),body(base).getCodeBytes()),"Incoming ConfigUI changed from the exact retained donor");
  check(candidate.method_info.size()==base.method_info.size()&&candidate.bodies.size()==base.bodies.size(),"Dead-write postpass must not append methods");
  check(candidate.constants.getMultinameCount()==base.constants.getMultinameCount()&&candidate.constants.getStringCount()==base.constants.getStringCount(),"Dead-write postpass must not append pool entries");
  CasStructuralRolesPatch.verifyProjection(body(base),change,body(candidate));check(Arrays.equals(body(candidate).getCodeBytes(),change.body.getCodeBytes()),"Dead-write projection differs from exact deletion");
  var rollback=CasStructuralRolesPatch.reparse(candidate);CasStructuralRolesPatch.replace(rollback,body(base).clone());
  check(Arrays.equals(CasStructuralRolesPatch.save(rollback),CasStructuralRolesPatch.save(base)),"Dead-write whole-ABC rollback changed final scaling/favorite/rightclick/native initialization");
  for(var b:base.bodies)if(b.method_info!=body(base).method_info)check(Arrays.equals(b.getCodeBytes(),candidate.findBody(b.method_info).getCodeBytes()),"Dead-write postpass changed another native/owned method");
 }
 public static void main(String[]args)throws Exception {
  if(args.length==2&&args[0].equals("--inspect")){var a=CasStructuralRolesPatch.load(args[1]);CasStructuralRolesPatch.dump(a,body(a),System.out);System.out.println("HEX "+java.util.HexFormat.of().formatHex(body(a).getCodeBytes()));return;}
  check(args.length==6,"Use original donor, exact final Main, baseline SWF SHA, baseline ABC SHA, output ABC, proof");
  check(CasStructuralRolesPatch.sha(Files.readAllBytes(Path.of(args[0]))).equals(DONOR),"Unpinned original CAS donor");check(CasStructuralRolesPatch.sha(Files.readAllBytes(Path.of(args[1]))).equals(args[2]),"Main differs from exact prior Draw stage");
  var donor=CasStructuralRolesPatch.load(args[0]);var base=CasStructuralRolesPatch.load(args[1]);check(CasStructuralRolesPatch.sha(CasStructuralRolesPatch.save(base)).equals(args[3]),"Main ABC differs from exact prior Draw proof");
  var candidate=CasStructuralRolesPatch.reparse(base);var change=rewrite(base);CasStructuralRolesPatch.replace(candidate,change.body);verify(donor,base,candidate,change);candidate=CasStructuralRolesPatch.reparse(candidate);verify(donor,base,candidate,change);
  byte[] data=CasStructuralRolesPatch.save(candidate);Files.write(Path.of(args[4]),data);
  String report="{\"ok\":true,\"phase\":\"dead-cell-attach-scale-write\",\"baseline_swf_sha256\":\""+args[2]+"\",\"baseline_abc_sha256\":\""+args[3]+"\",\"donor_swf_sha256\":\""+DONOR+"\",\"baseline_config_ui_sha256\":\""+CasStructuralRolesPatch.sha(body(base).getCodeBytes())+"\",\"config_ui_sha256\":\""+CasStructuralRolesPatch.sha(body(candidate).getCodeBytes())+"\",\"abc_sha256\":\""+CasStructuralRolesPatch.sha(data)+"\",\"edited_existing_methods\":1,\"removed_instructions\":5,\"appended_methods\":0,\"appended_traits\":0,\"appended_pool_entries\":0,\"dead_immediate_overwrite_verified\":true,\"authoritative_static_slot_verified\":true,\"final_xy_writes_retained\":true,\"rightclick_favorite_body_retained\":true,\"native_cfg_projection_verified\":true,\"whole_abc_rollback_verified\":true,\"all_other_methods_retained\":true,\"runtime_qualified\":false,\"performance_gain_claimed\":false}";
  Files.writeString(Path.of(args[5]),report+"\n");System.out.println(report);
 }
}
