import java.io.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;
import com.jpexs.helpers.MemoryInputStream;

/** Final, opt-in build adapter: one nullable callback test before either Draw tail.
 * The authenticated input is the output of the structural-role retention pass.
 * No source compilation, added method/trait/pool entry, or game access is used.
 */
public class CasDrawFastPathPatch {
    static final String CELL="widgets.CAS.controls.CASClothingPanelCellViewMain";
    static final String MAIN="widgets.CAS.Customizer.CASCustomizerMain";
    static final String CALLBACK="apexCatalogDrawTraceStep";
    static final int CALLBACK_LOCAL=24;
    static void check(boolean b,String s){if(!b)throw new IllegalArgumentException(s);}
    static String sha(byte[] b)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(b));}
    static byte[] save(ABC a)throws Exception{var out=new ByteArrayOutputStream();a.saveToStream(out);return out.toByteArray();}
    static ABC read(byte[] bytes)throws Exception{return new ABC(new ABCInputStream(new MemoryInputStream(bytes)),null,null);}
    static ABC reparse(ABC a)throws Exception{return read(save(a));}
    static int op(AVM2Instruction i){return i.definition.instructionCode;}
    static AVM2Instruction ins(int n,int... args){return new AVM2Instruction(0,n,args);}
    static AVM2Instruction copy(AVM2Instruction i){var c=i.clone();c.operands=i.operands==null?null:i.operands.clone();return c;}
    static String name(ABC a,int q){return a.constants.getString(a.constants.getMultiname(q).name_index);}
    static boolean qname(ABC a,int index,String space,String leaf){
        if(index<=0)return false;var q=a.constants.getMultiname(index);
        if(q.kind!=Multiname.QNAME||q.namespace_index<=0||!leaf.equals(a.constants.getString(q.name_index)))return false;
        var ns=a.constants.getNamespace(q.namespace_index);
        return ns.kind==Namespace.KIND_PACKAGE&&space.equals(a.constants.getString(ns.name_index));
    }
    static MethodBody draw(ABC a){
        int c=a.findClassByName(CELL);check(c>=0,"Missing Draw owner");MethodBody result=null;
        for(var t:a.instance_info.get(c).instance_traits.traits)if(t instanceof TraitMethodGetterSetter&&"Draw".equals(name(a,t.name_index))){
            check(result==null,"Ambiguous Draw");result=a.findBody(((TraitMethodGetterSetter)t).method_info);}
        check(result!=null,"Missing Draw");return result;
    }
    static int callback(ABC a){
        int main=a.findClassByName(MAIN);check(main>=0,"Missing Main");TraitSlotConst found=null;
        for(var t:a.class_info.get(main).static_traits.traits)if(CALLBACK.equals(name(a,t.name_index))){
            check(found==null&&t instanceof TraitSlotConst,"Ambiguous callback trait");found=(TraitSlotConst)t;}
        check(found!=null&&found.kindType==Trait.TRAIT_SLOT&&found.value_index==0&&
            qname(a,found.name_index,"",CALLBACK)&&qname(a,found.type_index,"","Function"),
            "Callback must be the original public uninitialized nullable Function slot");
        return found.name_index;
    }
    static void set(MethodBody b,List<AVM2Instruction> code){
        var made=b.getCode();made.code.clear();long at=0;for(var i:code){i.setAddress(at);at+=i.getBytesLength();made.code.add(i);}
        b.setCode(made);b.setModified();
    }
    static Map<Long,Integer> addresses(MethodBody b){
        var m=new HashMap<Long,Integer>();var c=b.getCode().code;
        for(int i=0;i<c.size();i++)check(m.put(c.get(i).getAddress(),i)==null,"Duplicate address");
        m.put(b.getCode().getEndOffset(),c.size());return m;
    }
    static boolean relative(AVM2Instruction i){return op(i)>=0x0c&&op(i)<=0x1a;}
    static long target(AVM2Instruction i){check(relative(i),"Not an S24 branch");return i.getAddress()+i.getBytesLength()+i.operands[0];}
    static void edge(AVM2Instruction i,long destination){
        long offset=destination-i.getAddress()-i.getBytesLength();check(offset>=-8388608&&offset<=8388607,"Branch overflow");i.operands[0]=(int)offset;
    }
    record Projection(MethodBody body,int markers){}
    static Projection strip(ABC a,MethodBody before){
        var c=before.getCode().code;
        check(c.size()>13&&op(c.get(0))==0xd0&&op(c.get(1))==0x30,"Native scope prologue differs");
        check(before.exceptions.length==0&&before.traits.traits.isEmpty()&&before.max_regs==25&&before.max_stack==28&&
            before.init_scope_depth==13&&before.max_scope_depth==14,"Authenticated Draw metadata differs");
        int main=a.findClassByName(MAIN),cb=callback(a);
        check(op(c.get(2))==0x60&&c.get(2).operands[0]==a.instance_info.get(main).name_index&&
            op(c.get(3))==0x66&&c.get(3).operands[0]==cb&&op(c.get(4))==0x63&&c.get(4).operands[0]==CALLBACK_LOCAL,
            "Trace callback capture differs");
        var kept=new ArrayList<AVM2Instruction>();var from=new ArrayList<Integer>();var boundary=new HashMap<Long,Integer>();
        int markers=0,returns=0;var events=new HashMap<String,Integer>();
        for(int i=0;i<c.size();){
            boundary.put(c.get(i).getAddress(),kept.size());
            if(i==2){i+=3;continue;}
            var first=c.get(i);
            check(op(first)!=0x1b,"Pinned Draw has no lookupswitch; new switch requires separate review");
            if(op(first)==0x62&&first.operands[0]==CALLBACK_LOCAL){
                check(i+8<=c.size()&&op(c.get(i+1))==0x12&&op(c.get(i+2))==0x62&&c.get(i+2).operands[0]==CALLBACK_LOCAL&&
                    op(c.get(i+3))==0x64&&op(c.get(i+4))==0x2c&&op(c.get(i+6))==0x41&&c.get(i+6).operands[0]==2&&op(c.get(i+7))==0x29,
                    "Unreviewed marker receiver, stack or callback local");
                long end=i+8==c.size()?before.getCode().getEndOffset():c.get(i+8).getAddress();
                check(target(c.get(i+1))==end,"Nullable marker branch differs");
                String event=a.constants.getString(c.get(i+4).operands[0]);
                check(event!=null&&event.matches("(draw|favorite|super|thumbnail|decoration|swatches|icons)\\.(enter|leave)")&&
                    op(c.get(i+5))==(event.equals("draw.enter")?0xd1:0x20),"Marker event/product differs");
                events.merge(event,1,Integer::sum);markers++;i+=8;continue;
            }
            check(!(op(first)==0x63&&first.operands[0]==CALLBACK_LOCAL),"Native tail writes callback local");
            if(op(first)==0x47)returns++;
            from.add(i);kept.add(copy(first));i++;
        }
        boundary.put(before.getCode().getEndOffset(),kept.size());
        check(markers==45&&returns==4&&events.equals(Map.ofEntries(Map.entry("draw.enter",1),Map.entry("draw.leave",4),
            Map.entry("favorite.enter",1),Map.entry("favorite.leave",1),Map.entry("super.enter",1),Map.entry("super.leave",1),
            Map.entry("thumbnail.enter",5),Map.entry("thumbnail.leave",5),Map.entry("decoration.enter",4),Map.entry("decoration.leave",4),
            Map.entry("swatches.enter",7),Map.entry("swatches.leave",7),Map.entry("icons.enter",2),Map.entry("icons.leave",2))),"Trace inventory differs");
        var result=before.clone();set(result,kept);
        for(int i=0;i<kept.size();i++)if(relative(kept.get(i))){
            var old=c.get(from.get(i));Integer destination=boundary.get(target(old));
            check(destination!=null&&destination>=2&&destination<kept.size(),"Native branch enters a removed marker/prologue or leaves Draw");
            edge(kept.get(i),kept.get(destination).getAddress());
        }
        check(op(kept.get(kept.size()-1))==0x47,"Fast tail must terminate without falling into profiled tail");
        set(result,kept);result.getCode().checkValidOffsets(result);return new Projection(result,markers);
    }
    record Envelope(MethodBody body,Projection fast,int fastIndex,int profileIndex){}
    static Envelope envelope(ABC a,MethodBody before){
        var projection=strip(a,before);var fast=projection.body.getCode().code;var traced=before.getCode().code;
        var made=new ArrayList<AVM2Instruction>();made.add(copy(traced.get(0)));made.add(copy(traced.get(1)));
        made.add(copy(traced.get(2)));made.add(copy(traced.get(3)));made.add(ins(0x2a));made.add(copy(traced.get(4)));
        var choose=ins(0x11,0);made.add(choose);int fastStart=made.size();
        for(int i=2;i<fast.size();i++)made.add(copy(fast.get(i)));int profileStart=made.size();
        for(int i=5;i<traced.size();i++)made.add(copy(traced.get(i)));
        var result=before.clone();set(result,made);edge(choose,made.get(profileStart).getAddress());
        // Both tails are copied contiguously. Their relative edge operands must
        // remain byte-identical; explicit destinations additionally forbid a
        // jump into the common prologue, opposite tail, or marker interior.
        validateTail(projection.body,result,2,fastStart,profileStart);
        validateTail(before,result,5,profileStart,made.size());
        set(result,made);result.getCode().checkValidOffsets(result);return new Envelope(result,projection,fastStart,profileStart);
    }
    static void validateTail(MethodBody source,MethodBody result,int first,int start,int end){
        var a=source.getCode().code;var b=result.getCode().code;var map=addresses(source);
        check(end-start==a.size()-first,"Tail instruction inventory differs");
        for(int i=first;i<a.size();i++){
            var old=a.get(i);var now=b.get(start+i-first);
            check(op(old)==op(now)&&Arrays.equals(old.operands,now.operands),"Tail bytes changed");
            if(relative(old)){
                Integer oldIndex=map.get(target(old));check(oldIndex!=null&&oldIndex>=first&&oldIndex<a.size(),"Tail edge leaves its source tail");
                check(target(now)==b.get(start+oldIndex-first).getAddress(),"Tail jump/conditional crosses diagnostic boundary");
            }
        }
    }
    static void replace(ABC a,MethodBody b){
        for(int i=0;i<a.bodies.size();i++)if(a.bodies.get(i).method_info==b.method_info){a.bodies.set(i,b);a.resetMethodIndexing();return;}
        throw new IllegalArgumentException("Draw method index disappeared");
    }
    static void verify(ABC baseline,ABC candidate,Envelope expected)throws Exception{
        var before=draw(baseline);var after=draw(candidate);
        check(Arrays.equals(after.getCodeBytes(),expected.body.getCodeBytes()),"Serialized Draw envelope/CFG differs");
        check(after.max_regs==before.max_regs&&after.max_stack==before.max_stack&&after.init_scope_depth==before.init_scope_depth&&
            after.max_scope_depth==before.max_scope_depth&&after.exceptions.length==0&&after.traits.traits.isEmpty(),"Draw scope/locals/exceptions/traits differ");
        check(callback(candidate)==callback(baseline),"Nullable callback identity differs");
        var c=after.getCode().code;
        check(op(c.get(6))==0x11&&target(c.get(6))==c.get(expected.profileIndex).getAddress(),"Entry must select profiled tail only for non-null callback");
        validateTail(expected.fast.body,after,2,expected.fastIndex,expected.profileIndex);
        validateTail(before,after,5,expected.profileIndex,c.size());
        var restored=reparse(candidate);replace(restored,before.clone());
        check(Arrays.equals(save(restored),save(baseline)),"Whole-ABC rollback changed data outside Draw");
        after.getCode().checkValidOffsets(after);
    }
    static String patch(String input,String expectedAbc,String expectedDraw,String output,String report)throws Exception{
        byte[] bytes=Files.readAllBytes(Path.of(input));check(expectedAbc.matches("[0-9a-f]{64}")&&sha(bytes).equals(expectedAbc),"Authenticated input ABC hash differs");
        var baseline=read(bytes);check(Arrays.equals(bytes,save(baseline)),"Input ABC has unretained serialized data");
        var before=draw(baseline);check(expectedDraw.matches("[0-9a-f]{64}")&&sha(before.getCodeBytes()).equals(expectedDraw),"Authenticated input Draw hash differs");
        var made=envelope(baseline,before);var candidate=reparse(baseline);replace(candidate,made.body);candidate=reparse(candidate);verify(baseline,candidate,made);
        byte[] result=save(candidate);Files.write(Path.of(output),result);
        String json="{\"ok\":true,\"baseline_abc_sha256\":\""+expectedAbc+"\",\"baseline_draw_sha256\":\""+expectedDraw+"\",\"abc_sha256\":\""+sha(result)+
            "\",\"draw_sha256\":\""+sha(draw(candidate).getCodeBytes())+"\",\"input_draw_instructions\":"+before.getCode().code.size()+",\"input_draw_bytes\":"+before.getCodeBytes().length+
            ",\"fast_draw_instructions\":"+made.fast.body.getCode().code.size()+",\"fast_draw_bytes\":"+made.fast.body.getCodeBytes().length+",\"output_draw_instructions\":"+made.body.getCode().code.size()+",\"output_draw_bytes\":"+made.body.getCodeBytes().length+
            ",\"disabled_added_instructions\":5,\"disabled_callback_reads\":1,\"disabled_marker_checks\":0,\"profiled_marker_count\":45,\"edited_existing_methods\":1,\"appended_methods\":0,\"appended_traits\":0,\"appended_pool_entries\":0,"+
            "\"nullable_function_identity_verified\":true,\"single_entry_branch_verified\":true,\"fast_tail_exact_verified\":true,\"profiled_tail_exact_verified\":true,\"native_throw_propagation_preserved\":true,\"serialized_whole_abc_rollback_projection\":true,\"runtime_verified\":false,\"performance_gain_claimed\":false}";
        Files.writeString(Path.of(report),json+"\n");return json;
    }
    public static void main(String[] args)throws Exception{
        check(args.length==5,"Use input ABC, authenticated ABC SHA, authenticated Draw SHA, output ABC, report JSON");
        System.out.println(patch(args[0],args[1],args[2],args[3],args[4]));
    }
}
