import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.lang.reflect.*;
import java.security.MessageDigest;
import com.jpexs.decompiler.flash.SWF;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;
import com.jpexs.helpers.MemoryInputStream;

// Post-retainer structural-role adapter. Reads compiled UI only; no game/process access.
// Every unselected method/trait and the incoming Main/height are retained exactly.
public class CasStructuralRolesPatch {
    static final String CELL="widgets.CAS.controls.CASClothingPanelCellViewMain";
    static final String CURRENT="dcc.history.CurrentOutfitUI";
    static final String PROBE="dcc.history.OutfitCategory";
    static final String MAIN="widgets.CAS.Customizer.CASCustomizerMain";
    static final String DONOR_PIN="c97afa8f0362a0452b359074769b9c99174444dd211927d08972091db3391969";
    static final String DRAW_PIN="1f289754f5a45f86a44986a4e61840ab4a647e83a1a8c5d8afc82f1322e359f8";
    static void check(boolean b,String message){if(!b)throw new IllegalArgumentException(message);}
    static String sha(byte[] b)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(b));}
    static ABC load(String path)throws Exception{
        var swf=new SWF(new FileInputStream(path),false);
        check(swf.getAbcList().size()==1,"Expected one exact ABC");return swf.getAbcList().get(0).getABC();
    }
    static byte[] save(ABC a)throws Exception{var out=new ByteArrayOutputStream();a.saveToStream(out);return out.toByteArray();}
    static ABC reparse(ABC a)throws Exception{return new ABC(new ABCInputStream(new MemoryInputStream(save(a))),a.parentTag==null?null:a.getSwf(),null);}
    static String name(ABC a,int multiname){return a.constants.getString(a.constants.getMultiname(multiname).name_index);}
    static TraitMethodGetterSetter trait(ABC a,String type,String method,boolean statik){
        int c=a.findClassByName(type);check(c>=0,"Missing class "+type);TraitMethodGetterSetter found=null;
        for(var t:(statik?a.class_info.get(c).static_traits:a.instance_info.get(c).instance_traits).traits)
            if(t instanceof TraitMethodGetterSetter && name(a,t.name_index).equals(method)){
                check(found==null,"Ambiguous method "+method);found=(TraitMethodGetterSetter)t;}
        check(found!=null,"Missing method "+type+"."+method);return found;
    }
    static MethodBody body(ABC a,String type,String method,boolean statik){return a.findBody(trait(a,type,method,statik).method_info);}
    static int op(AVM2Instruction i){return i.definition.instructionCode;}
    static boolean prop(ABC a,AVM2Instruction i,int opcode,String member){return op(i)==opcode && name(a,i.operands[0]).equals(member);}
    static void dump(ABC a,MethodBody b,PrintStream out)throws Exception{
        out.println("method="+b.method_info+" regs="+b.max_regs+" scope="+b.init_scope_depth+"/"+b.max_scope_depth+" sha="+sha(b.getCodeBytes()));
        var code=b.getCode().code;
        for(int n=0;n<code.size();n++){
            var i=code.get(n);String member="";
            if(Set.of(0x60,0x5d,0x66,0x61,0x46,0x4f,0x45,0x4e,0x80,0x68).contains(op(i)))member=name(a,i.operands[0]);
            out.println(n+" @"+i.getAddress()+" "+i.definition.instructionName+" "+Arrays.toString(i.operands)+" "+member);
        }
    }
    static void prefix(ABC a,ABC c)throws Exception{
        for(String kind:List.of("String","Int","UInt","Double","Namespace","NamespaceSet","Multiname")){
            var type=a.constants.getClass();var count=type.getMethod("get"+kind+"Count");var get=type.getMethod("get"+kind,int.class);
            int n=(Integer)count.invoke(a.constants);check((Integer)count.invoke(c.constants)>=n,"Pool shrank: "+kind);
            for(int i=1;i<n;i++){
                Object x=get.invoke(a.constants,i),y=get.invoke(c.constants,i);
                check(kind.equals("NamespaceSet")?Arrays.equals(((NamespaceSet)x).namespaces,((NamespaceSet)y).namespaces):
                    String.valueOf(x).equals(String.valueOf(y)),"Native constant changed: "+kind+" "+i);
            }
        }
    }
    static AVM2Instruction ins(int opcode,int... operands){return new AVM2Instruction(0,opcode,operands);}
    static AVM2Instruction copy(AVM2Instruction op){var c=op.clone();c.operands=op.operands==null?null:op.operands.clone();return c;}
    static boolean relative(int opcode){return opcode>=0x0c && opcode<=0x1a;} // Includes unconditional jump 0x10.
    static List<Integer> targetOperands(AVM2Instruction i){
        if(relative(op(i)))return List.of(0);
        if(op(i)==0x1b){
            check(i.operands!=null && i.operands.length>=3 && i.operands[1]>=0 && i.operands.length==i.operands[1]+3,"Malformed lookupswitch");
            var result=new ArrayList<Integer>();result.add(0);for(int j=2;j<i.operands.length;j++)result.add(j);return result;
        }
        return List.of();
    }
    static long target(AVM2Instruction i,int operand){return i.getAddress()+(op(i)==0x1b?0:i.getBytesLength())+i.operands[operand];}
    static Map<Long,Integer> addresses(MethodBody b){
        var map=new HashMap<Long,Integer>();var code=b.getCode().code;
        for(int i=0;i<code.size();i++)check(map.put(code.get(i).getAddress(),i)==null,"Duplicate instruction address");
        map.put(b.getCode().getEndOffset(),code.size());return map;
    }
    record Destination(Integer oldIndex,AVM2Instruction instruction){}
    static Destination old(int index){return new Destination(index,null);}
    static Destination local(AVM2Instruction instruction){return new Destination(null,instruction);}
    static class Block {
        final int start,end;final List<AVM2Instruction> code;
        final Map<AVM2Instruction,Map<Integer,Destination>> edges=new IdentityHashMap<>();
        Block(int start,int end,List<AVM2Instruction> code){this.start=start;this.end=end;this.code=code;}
        void edge(AVM2Instruction instruction,int operand,Destination target){edges.computeIfAbsent(instruction,k->new HashMap<>()).put(operand,target);}
    }
    static class Rewrite {
        final MethodBody body;final Map<Integer,Integer> boundaries;final List<Integer> origins;
        Rewrite(MethodBody body,Map<Integer,Integer> boundaries,List<Integer> origins){this.body=body;this.boundaries=boundaries;this.origins=origins;}
    }
    static long boundary(Rewrite rewrite,int oldIndex){
        Integer index=rewrite.boundaries.get(oldIndex);check(index!=null,"Edge/exception enters removed interior: "+oldIndex);
        return index==rewrite.body.getCode().code.size()?rewrite.body.getCode().getEndOffset():rewrite.body.getCode().code.get(index).getAddress();
    }
    static int index(Map<Long,Integer> map,long address){Integer result=map.get(address);check(result!=null,"Edge targets non-instruction "+address);return result;}
    static Rewrite rewrite(MethodBody before,List<Block> blocks)throws Exception{
        var original=before.getCode().code;var edits=new TreeMap<Integer,Block>();int previous=0;
        for(var block:blocks){check(block.start>=previous && block.end>block.start && block.end<=original.size() && !block.code.isEmpty(),"Invalid/overlapping edit");
            check(edits.put(block.start,block)==null,"Duplicate edit start");previous=block.end;}
        var result=before.clone();var code=result.getCode();var made=new ArrayList<AVM2Instruction>();
        var boundaries=new HashMap<Integer,Integer>();var origins=new ArrayList<Integer>();var newEdges=new IdentityHashMap<AVM2Instruction,Map<Integer,Destination>>();
        for(int i=0;i<original.size();){
            boundaries.put(i,made.size());var block=edits.get(i);
            if(block!=null){for(var instruction:block.code){made.add(instruction);origins.add(-1);}newEdges.putAll(block.edges);i=block.end;}
            else{made.add(copy(original.get(i)));origins.add(i);i++;}
        }
        boundaries.put(original.size(),made.size());long address=0;
        for(var instruction:made){instruction.setAddress(address);address+=instruction.getBytesLength();}
        code.code.clear();code.code.addAll(made);result.setCode(code);result.setModified();
        var answer=new Rewrite(result,boundaries,origins);var oldAddresses=addresses(before);
        for(int n=0;n<made.size();n++){
            var instruction=made.get(n);int origin=origins.get(n);
            for(int operand:targetOperands(instruction)){
                long destination;
                if(origin>=0){destination=boundary(answer,index(oldAddresses,target(original.get(origin),operand)));}
                else{
                    var edges=newEdges.get(instruction);check(edges!=null && edges.containsKey(operand),"New branch lacks reviewed edge");
                    var ref=edges.get(operand);destination=ref.oldIndex()!=null?boundary(answer,ref.oldIndex()):ref.instruction().getAddress();
                    if(ref.instruction()!=null)check(made.contains(ref.instruction()),"New branch leaves generated block");
                }
                instruction.operands[operand]=Math.toIntExact(destination-instruction.getAddress()-(op(instruction)==0x1b?0:instruction.getBytesLength()));
                check(instruction.operands[operand]>=-8388608 && instruction.operands[operand]<=8388607,"S24 edge overflow");
            }
        }
        result.exceptions=new ABCException[before.exceptions.length];
        for(int i=0;i<before.exceptions.length;i++){
            var e=before.exceptions[i].clone();e.start=(int)boundary(answer,index(oldAddresses,e.start));
            e.end=(int)boundary(answer,index(oldAddresses,e.end));e.target=(int)boundary(answer,index(oldAddresses,e.target));result.exceptions[i]=e;
        }
        result.setCode(code);result.setModified();verifyProjection(before,answer,result);return answer;
    }
    static void verifyProjection(MethodBody before,Rewrite rewrite,MethodBody candidate)throws Exception{
        var nativeCode=before.getCode().code;var code=candidate.getCode().code;var nativeAddresses=addresses(before);
        check(code.size()==rewrite.origins.size(),"Serialized rewrite instruction inventory differs");
        for(int i=0;i<code.size();i++){
            int origin=rewrite.origins.get(i);if(origin<0)continue;
            var a=nativeCode.get(origin);var b=code.get(i);check(op(a)==op(b),"Unowned opcode changed");
            check((a.operands==null)==(b.operands==null),"Unowned operand shape differs");
            if(a.operands!=null){check(a.operands.length==b.operands.length,"Unowned operand count differs");
                var targets=targetOperands(a);for(int j=0;j<a.operands.length;j++){
                    if(targets.contains(j))check(target(b,j)==boundary(rewrite,index(nativeAddresses,target(a,j))),"Unowned branch/jump/switch edge changed");
                    else check(a.operands[j]==b.operands[j],"Unowned operand changed");
                }}
        }
        check(candidate.exceptions.length==before.exceptions.length,"Exception inventory changed");
        for(int i=0;i<before.exceptions.length;i++){
            var a=before.exceptions[i];var b=candidate.exceptions[i];
            check(b.start==boundary(rewrite,index(nativeAddresses,a.start)) && b.end==boundary(rewrite,index(nativeAddresses,a.end)) &&
                b.target==boundary(rewrite,index(nativeAddresses,a.target)) && b.type_index==a.type_index && b.name_index==a.name_index,"Exception remap differs");
        }
        candidate.getCode().checkValidOffsets(candidate);
    }
    static void set(MethodBody body,List<AVM2Instruction> instructions){
        var code=body.getCode();code.code.clear();long address=0;for(var i:instructions){i.setAddress(address);address+=i.getBytesLength();code.code.add(i);}
        body.setCode(code);body.setModified();
    }
    static void fixtures(ABC context)throws Exception{
        var f=new MethodBody(context,new Traits(),new byte[]{0x47},new ABCException[0]);
        var code=new ArrayList<>(List.of(ins(0xd0),ins(0x30),ins(0x26),ins(0x12,0),ins(0x24,0),ins(0x1b,0,2,0,0,0),
            ins(0x02),ins(0x10,0),ins(0x02),ins(0x47),ins(0x29),ins(0x47)));
        set(f,code);
        for(int i:List.of(3,7))code.get(i).operands[0]=(int)(code.get(9).getAddress()-code.get(i).getAddress()-code.get(i).getBytesLength());
        code.get(5).operands[0]=(int)(code.get(9).getAddress()-code.get(5).getAddress());
        code.get(5).operands[2]=(int)(code.get(6).getAddress()-code.get(5).getAddress());
        code.get(5).operands[3]=(int)(code.get(8).getAddress()-code.get(5).getAddress());
        code.get(5).operands[4]=(int)(code.get(2).getAddress()-code.get(5).getAddress());
        set(f,code);var e=new ABCException();e.start=(int)code.get(2).getAddress();e.end=(int)code.get(9).getAddress();e.target=(int)code.get(10).getAddress();
        f.exceptions=new ABCException[]{e};f.max_stack=2;f.max_regs=1;f.init_scope_depth=0;f.max_scope_depth=1;
        var edit=new Block(6,7,new ArrayList<>(List.of(ins(0x02),ins(0x02),ins(0x02))));var r=rewrite(f,List.of(edit));
        var reparsed=new MethodBody(context,new Traits(),r.body.getCodeBytes(),r.body.exceptions);verifyProjection(f,r,reparsed);
        check(target(reparsed.getCode().code.get(r.boundaries.get(7)),0)==boundary(r,9),"Explicit 0x10 jump was not relocated");
        boolean rejected=false;try{rewrite(f,List.of(new Block(6,9,new ArrayList<>(List.of(ins(0x02))))));}catch(IllegalArgumentException expected){rejected=true;}
        check(rejected,"Branch to removed interior was accepted");
        var tampered=new MethodBody(context,new Traits(),r.body.getCodeBytes(),r.body.exceptions);
        var jump=tampered.getCode().code.get(r.boundaries.get(7));jump.operands[0]=0;tampered.setModified();
        rejected=false;try{verifyProjection(f,r,tampered);}catch(IllegalArgumentException expected){rejected=true;}
        check(rejected,"Changed explicit jump edge escaped projection");
        var exceptionOnly=f.clone();exceptionOnly.exceptions=new ABCException[]{e.clone()};exceptionOnly.exceptions[0].start=(int)code.get(7).getAddress();
        rejected=false;try{rewrite(exceptionOnly,List.of(new Block(6,8,new ArrayList<>(List.of(ins(0x02))))));}catch(IllegalArgumentException expected){rejected=true;}
        check(rejected,"Exception boundary inside removed span accepted");
    }
    static List<Integer> traceProjection(ABC donor,MethodBody nativeDraw,ABC baseline,MethodBody traced)throws Exception{
        check(sha(nativeDraw.getCodeBytes()).equals(DRAW_PIN),"Pinned original Draw differs");
        check(nativeDraw.exceptions.length==0 && traced.exceptions.length==0 && nativeDraw.max_regs==24 && traced.max_regs==25,"Draw metadata differs");
        var original=nativeDraw.getCode().code;var code=traced.getCode().code;var origins=new ArrayList<Integer>();
        var baseAddressToOriginal=new HashMap<Long,Integer>();var retained=new ArrayList<AVM2Instruction>();int markers=0,prefixes=0;
        for(int i=0;i<code.size();){
            var a=code.get(i);baseAddressToOriginal.put(a.getAddress(),retained.size());
            if(i==2){
                check(prop(baseline,a,0x60,"CASCustomizerMain") && prop(baseline,code.get(i+1),0x66,"apexCatalogDrawTraceStep") &&
                    op(code.get(i+2))==0x63 && code.get(i+2).operands[0]==24,"Baseline trace callback prefix differs");prefixes++;i+=3;continue;
            }
            if(op(a)==0x62 && a.operands[0]==24){
                check(i+8<=code.size(),"Short trace marker");
                check(op(code.get(i+1))==0x12 && op(code.get(i+2))==0x62 && code.get(i+2).operands[0]==24 &&
                    op(code.get(i+3))==0x64 && op(code.get(i+4))==0x2c &&
                    (op(code.get(i+5))==0x20 || op(code.get(i+5))==0xd1) && op(code.get(i+6))==0x41 &&
                    code.get(i+6).operands[0]==2 && op(code.get(i+7))==0x29,"Trace marker receiver/arguments differ");
                long end=i+8==code.size()?traced.getCode().getEndOffset():code.get(i+8).getAddress();
                check(target(code.get(i+1),0)==end,"Trace disabled branch does not skip exactly its own marker");
                String event=baseline.constants.getString(code.get(i+4).operands[0]);
                check(event.matches("(draw|favorite|super|thumbnail|decoration|swatches|icons)\\.(enter|leave)"),"Unknown trace marker");
                check((event.equals("draw.enter"))==(op(code.get(i+5))==0xd1),"Trace product argument differs");markers++;i+=8;continue;
            }
            origins.add(i);retained.add(a);i++;
        }
        baseAddressToOriginal.put(traced.getCode().getEndOffset(),retained.size());
        check(prefixes==1 && markers==45 && retained.size()==original.size(),"Baseline trace projection inventory differs");
        var originalAddresses=addresses(nativeDraw);
        for(int i=0;i<original.size();i++){
            var a=original.get(i);var b=retained.get(i);check(op(a)==op(b),"Baseline native opcode differs");
            check((a.operands==null)==(b.operands==null),"Baseline native operand shape differs");
            if(a.operands!=null){check(a.operands.length==b.operands.length,"Baseline native operand count differs");
                for(int j=0;j<a.operands.length;j++){
                    if(targetOperands(a).contains(j))check(index(originalAddresses,target(a,j))==index(baseAddressToOriginal,target(b,j)),"Baseline native branch/jump/switch edge differs");
                    else check(a.operands[j]==b.operands[j],"Baseline native operand differs");
                }}
        }
        return origins;
    }
    static List<AVM2Instruction> compiledCall(ABC compiled)throws Exception{
        var probe=body(compiled,PROBE,"ApexRoleCallProbe",true);var filtered=new ArrayList<AVM2Instruction>();
        check(probe.exceptions.length==0 && probe.traits.traits.isEmpty(),"ABI probe has activation/exception dependencies");
        for(var i:probe.getCode().code)if(op(i)!=0xef && op(i)!=0xf0 && op(i)!=0xf1)filtered.add(i);
        check(filtered.size()==6 && op(filtered.get(0))==0xd0 && op(filtered.get(1))==0x30 &&
            prop(compiled,filtered.get(2),0x60,"CurrentOutfitUI") && op(filtered.get(3))==0xd1 &&
            prop(compiled,filtered.get(4),0x46,"ApexCellRole") && filtered.get(4).operands[1]==1 && op(filtered.get(5))==0x48,
            "Cross-class compiler probe does not prove exact static receiver/callproperty ABI");
        check(filtered.get(4).operands[0]==trait(compiled,CURRENT,"ApexCellRole",true).name_index,"ABI call uses a different helper namespace");
        return List.of(copy(filtered.get(2)),ins(0xd0),copy(filtered.get(4)));
    }
    static void publicQName(ABC a,int name){
        var q=a.constants.getMultiname(name);check(q.kind==Multiname.QNAME && q.namespace_index>0,"Helper requires QName");
        var ns=a.constants.getNamespace(q.namespace_index);check(ns.kind==Namespace.KIND_PACKAGE && a.constants.getString(ns.name_index).isEmpty(),"Helper must use exact public namespace");
    }
    static void helperContract(ABC c)throws Exception{
        var t=trait(c,CURRENT,"ApexCellRole",true);var h=c.findBody(t.method_info);var info=c.method_info.get(t.method_info);
        publicQName(c,t.name_index);check(info.param_types.length==1 && name(c,info.param_types[0]).equals("Object") && name(c,info.ret_type).equals("int") &&
            info.optional.length==0 && h.exceptions.length==0 && h.traits.traits.isEmpty(),"Helper signature/activation differs");
        int limit=0;boolean parent=false,live=false;
        for(var i:h.getCode().code){
            check(!Set.of(0x04,0x05,0x40,0x41,0x42,0x43,0x44,0x45,0x46,0x49,0x4a,0x4c,0x4e,0x4f,0x55,0x56,0x58,0x61,0x68,0x6d,0x6f,0x67).contains(op(i)),"Helper contains a call/write/allocation/outer dependency");
            if(op(i)==0x60)check(name(c,i.operands[0]).equals("HistoryHost"),"Helper resolves an unknown class");
            if(op(i)==0x66){String member=name(c,i.operands[0]);check(member==null || member.equals("parent") || member.equals("dccHistoryRuntimeDrawer"),"Helper reads an unknown property");parent|="parent".equals(member);live|="dccHistoryRuntimeDrawer".equals(member);}
            if(op(i)==0x25 && i.operands[0]==256)limit++;
        }
        check(limit==1 && parent && live,"Helper lost bound/live structural ownership reads");
    }
    // Deliberately limited interpreter for this verified pure helper's serialized
    // AVM2 only. It is an executable control-flow oracle, not a Flash VM claim.
    static class GraphNode {Object parent;Runnable onParent;GraphNode(Object parent){this.parent=parent;}}
    static Object vmRuntime;static final Object HISTORY_CLASS=new Object(),CURRENT_CLASS=new Object();
    static boolean truth(Object v){return v!=null && (!(v instanceof Boolean)||((Boolean)v)) && (!(v instanceof Number)||((Number)v).doubleValue()!=0);}
    static boolean equal(Object a,Object b){return a==b || a instanceof Number && b instanceof Number && ((Number)a).doubleValue()==((Number)b).doubleValue();}
    static Object pop(List<Object> s){check(!s.isEmpty(),"VM stack underflow");return s.remove(s.size()-1);}
    static int vm(ABC a,MethodBody b,Object argument)throws Exception{
        Object[] locals=new Object[b.max_regs];locals[0]=CURRENT_CLASS;locals[1]=argument;var stack=new ArrayList<Object>();var code=b.getCode().code;var map=addresses(b);
        for(int pc=0,steps=0;steps<50000;steps++){
            var i=code.get(pc);int next=pc+1;Object x,y;
            switch(op(i)){
                case 0xd0,0xd1,0xd2,0xd3 -> stack.add(locals[op(i)-0xd0]);
                case 0xd4,0xd5,0xd6,0xd7 -> locals[op(i)-0xd4]=pop(stack);
                case 0x62 -> stack.add(locals[i.operands[0]]);
                case 0x63 -> locals[i.operands[0]]=pop(stack);
                case 0x30,0x29 -> pop(stack);
                case 0x2a -> stack.add(stack.get(stack.size()-1));
                case 0x24,0x25 -> stack.add(i.operands[0]);
                case 0x20 -> stack.add(null);
                case 0x60 -> {String n=name(a,i.operands[0]);check(n.equals("HistoryHost")||n.equals("CurrentOutfitUI"),"Unreviewed VM lex");stack.add(n.equals("HistoryHost")?HISTORY_CLASS:CURRENT_CLASS);}
                case 0x5d -> {check(name(a,i.operands[0]).equals("ApexCellRole"),"Unreviewed VM property resolver");stack.add(CURRENT_CLASS);}
                case 0x66 -> {
                    String n=name(a,i.operands[0]);Integer key=n==null?((Number)pop(stack)).intValue():null;x=pop(stack);
                    if(n==null){check(x instanceof Object[],"VM indexed read is not runtime record");var values=(Object[])x;stack.add(key<values.length?values[key]:null);}
                    else if(n.equals("dccHistoryRuntimeDrawer")){check(x==HISTORY_CLASS,"VM wrong HistoryHost receiver");stack.add(vmRuntime);}
                    else{check(n.equals("parent")&&x instanceof GraphNode,"VM unreviewed property read");var node=(GraphNode)x;if(node.onParent!=null)node.onParent.run();stack.add(node.parent);}
                }
                case 0x73 -> stack.add(((Number)pop(stack)).intValue());
                case 0x76 -> stack.add(truth(pop(stack)));
                case 0x80,0x82,0x09,0xef,0xf0,0xf1 -> {}
                case 0x96 -> stack.add(!truth(pop(stack)));
                case 0xc2 -> locals[i.operands[0]]=((Number)locals[i.operands[0]]).intValue()+1;
                case 0xab -> {y=pop(stack);x=pop(stack);stack.add(equal(x,y));}
                case 0xad -> {y=pop(stack);x=pop(stack);stack.add(((Number)x).doubleValue()<((Number)y).doubleValue());}
                case 0x10 -> next=index(map,target(i,0));
                case 0x11,0x12 -> {boolean yes=truth(pop(stack));if(yes==(op(i)==0x11))next=index(map,target(i,0));}
                case 0x13,0x14,0x19,0x1a -> {y=pop(stack);x=pop(stack);boolean same=equal(x,y);if(same==(op(i)==0x13||op(i)==0x19))next=index(map,target(i,0));}
                case 0x46 -> {check(prop(a,i,0x46,"ApexCellRole")&&i.operands[1]==1,"VM unreviewed call");x=pop(stack);check(pop(stack)==CURRENT_CLASS,"VM static helper receiver differs");stack.add(vm(a,body(a,CURRENT,"ApexCellRole",true),x));}
                case 0x48 -> {Object result=pop(stack);check(stack.isEmpty(),"VM return left values on stack");return result instanceof Boolean?((Boolean)result?1:0):((Number)result).intValue();}
                default -> throw new IllegalArgumentException("VM unsupported opcode "+op(i));
            }
            pc=next;
        }
        throw new IllegalArgumentException("VM helper did not terminate within structural bound");
    }
    static void compiledRoleFixtures(ABC a)throws Exception{
        var h=body(a,CURRENT,"ApexCellRole",true);var currentPredicate=body(a,CURRENT,"IsCurrent",true);
        var stage=new GraphNode(null);var host=new GraphNode(stage);var root=new GraphNode(host);
        var history=new GraphNode(root);var preview=new GraphNode(root);var current=new GraphNode(root);var grid=new GraphNode(history);var cell=new GraphNode(grid);
        Object[] r=new Object[41];r[0]=root;r[2]=history;r[25]=preview;r[40]=current;vmRuntime=r;
        check(vm(a,h,cell)==1,"Compiled helper missed first-paint history role");grid.parent=preview;check(vm(a,h,cell)==2,"Compiled helper cached direct parent role");
        grid.parent=current;check(vm(a,h,cell)==3 && vm(a,currentPredicate,cell)==1,"Compiled Current Outfit receiver/role differs");
        grid.parent=host;check(vm(a,h,cell)==0 && vm(a,currentPredicate,cell)==0,"Compiled helper retained recycled role");
        check(vm(a,h,new GraphNode(null))==0 && vm(a,h,null)==0,"Compiled unattached measurement is owned");
        grid.parent=current;Object[] replacement=new Object[41];replacement[0]=new GraphNode(host);replacement[40]=new GraphNode(replacement[0]);vmRuntime=replacement;
        check(vm(a,h,cell)==0,"Compiled helper retained replaced drawer role");vmRuntime=r;
        grid.onParent=()->vmRuntime=replacement;check(vm(a,h,cell)==0,"Compiled helper published replaced runtime capture");grid.onParent=null;vmRuntime=r;
        root.parent=null;check(vm(a,h,cell)==0,"Compiled detached drawer is owned");root.parent=host;
        var cycle=new GraphNode(null);cycle.parent=cycle;check(vm(a,h,cycle)==0,"Compiled helper did not terminate corrupt cycle");
    }
    static Block initialBlock(ABC original,MethodBody draw,List<Integer> projected,ABC compiled)throws Exception{
        // These indices are authenticated by DRAW_PIN and traceProjection, not text matching.
        var source=draw.getCode().code;check(source.size()==759,"Pinned original Draw instruction inventory differs");
        int start=projected.get(9),end=projected.get(58);check(end-start==49,"Trace marker entered initial owned span");
        var code=new ArrayList<AVM2Instruction>();for(int i=9;i<12;i++)code.add(copy(source.get(i)));
        code.addAll(compiledCall(compiled));code.add(ins(0x63,22));
        code.add(ins(0x62,22));code.add(ins(0x24,1));var yes=ins(0x13,0);code.add(yes);
        code.add(ins(0x62,22));code.add(ins(0x24,2));var no=ins(0x14,0);code.add(no);
        var assign=copy(source.get(31));code.add(assign);for(int i=32;i<35;i++)code.add(copy(source.get(i)));
        check(op(source.get(31))==0x62 && source.get(31).operands[0]==21 && op(source.get(34))==0x63 && source.get(34).operands[0]==20,"Scale assignment ABI differs");
        var block=new Block(start,end,code);block.edge(yes,0,local(assign));block.edge(no,0,old(end));return block;
    }
    static Block previewBlock(MethodBody draw,List<Integer> projected,ABC compiled)throws Exception{
        var source=draw.getCode().code;int start=projected.get(724),end=projected.get(750);check(end-start==26,"Trace marker entered preview owned span");
        var code=new ArrayList<AVM2Instruction>(compiledCall(compiled));code.add(ins(0x24,2));var no=ins(0x14,0);code.add(no);
        for(int i=746;i<750;i++)code.add(copy(source.get(i)));
        var block=new Block(start,end,code);block.edge(no,0,old(end));return block;
    }
    static MethodBody adapted(MethodBody made,MethodBody before,int index){
        check(made.exceptions.length==0 && made.traits.traits.isEmpty(),"New body has unreviewed activation/exception state");
        int delta=before.init_scope_depth-made.init_scope_depth;check(delta>=0 && delta<=16,"Lexical scope differs");
        var result=made.clone();result.method_info=index;result.init_scope_depth+=delta;result.max_scope_depth+=delta;
        for(var i:result.getCode().code)check(op(i)!=0x40 && op(i)!=0x44 && op(i)!=0x67,"New body has nested/outer dependency");
        result.setCode(result.getCode());result.setModified();return result;
    }
    static void replace(ABC a,MethodBody body){
        int found=-1;for(int i=0;i<a.bodies.size();i++)if(a.bodies.get(i).method_info==body.method_info){check(found<0,"Duplicate body");found=i;}
        check(found>=0,"Missing body to replace");a.bodies.set(found,body);a.resetMethodIndexing();
    }
    static List<String> calls(ABC a,MethodBody body,Set<String> ignored){
        var result=new ArrayList<String>();for(var i:body.getCode().code)if(Set.of(0x41,0x43,0x44,0x45,0x46,0x4c,0x4e,0x4f).contains(op(i))){
            String member=op(i)==0x41?"<function>":name(a,i.operands[0]);if(!ignored.contains(member))result.add(op(i)+":"+member+":"+Arrays.toString(i.operands));}
        return result;
    }
    static void verifyAll(ABC baseline,ABC candidate,Rewrite drawRewrite,int helperId,String expectedDraw,String expectedCurrent,String expectedHelper)throws Exception{
        prefix(baseline,candidate);check(candidate.method_info.size()==baseline.method_info.size()+1 && candidate.bodies.size()==baseline.bodies.size()+1,"Only one method/body may be appended");
        var d=body(candidate,CELL,"Draw",false);var c=body(candidate,CURRENT,"IsCurrent",true);var h=body(candidate,CURRENT,"ApexCellRole",true);
        check(h.method_info==helperId && helperId==baseline.method_info.size(),"Helper must append exact method index");
        check(sha(d.getCodeBytes()).equals(expectedDraw) && sha(c.getCodeBytes()).equals(expectedCurrent) && sha(h.getCodeBytes()).equals(expectedHelper),"Serialized owned body differs");
        verifyProjection(body(baseline,CELL,"Draw",false),drawRewrite,d);
        helperContract(candidate);compiledRoleFixtures(candidate);publicQName(candidate,trait(candidate,CURRENT,"ApexCellRole",true).name_index);
        check(calls(baseline,body(baseline,CELL,"Draw",false),Set.of("GetAllCells","indexOf")).equals(
            calls(candidate,d,Set.of("ApexCellRole"))),"Calls outside reviewed structural spans changed order/ABI");
        int roleCalls=0;for(var i:d.getCode().code)if(prop(candidate,i,0x46,"ApexCellRole"))roleCalls++;
        check(roleCalls==2,"Draw must query live role exactly at the two selected boundaries");
        // Roll back ONLY the permitted changes, then compare serialized entire ABC.
        // This covers every native trait, method signature/body metadata, initializer,
        // Main method, height getter, script, namespace, exception and class ordering.
        var projection=reparse(candidate);replace(projection,body(baseline,CELL,"Draw",false).clone());replace(projection,body(baseline,CURRENT,"IsCurrent",true).clone());
        check(projection.bodies.get(projection.bodies.size()-1).method_info==helperId,"Helper body is not appended");projection.bodies.remove(projection.bodies.size()-1);
        projection.method_info.remove(projection.method_info.size()-1);var traits=projection.class_info.get(projection.findClassByName(CURRENT)).static_traits.traits;
        var appended=traits.get(traits.size()-1);check(appended instanceof TraitMethodGetterSetter && ((TraitMethodGetterSetter)appended).method_info==helperId && name(projection,appended.name_index).equals("ApexCellRole"),"Only reviewed static helper trait may append");
        traits.remove(traits.size()-1);projection.constants=baseline.constants;projection.resetMethodIndexing();
        check(Arrays.equals(save(projection),save(baseline)),"Whole-ABC rollback projection changed unowned native data");
        for(var b:baseline.bodies)if(b.method_info!=d.method_info && b.method_info!=c.method_info)
            check(Arrays.equals(b.getCodeBytes(),candidate.findBody(b.method_info).getCodeBytes()),"Unowned native body hash differs");
        check(Arrays.equals(body(baseline,CELL,"height",false).getCodeBytes(),body(candidate,CELL,"height",false).getCodeBytes()),"Existing height authority changed");
    }
    static void patch(String donorPath,String baselinePath,String compiledPath,String outputPath,String reportPath)throws Exception{
        check(sha(Files.readAllBytes(Path.of(donorPath))).equals(DONOR_PIN),"Donor SWF pin differs");
        String baselineSha=sha(Files.readAllBytes(Path.of(baselinePath)));
        ABC donor=load(donorPath),baseline=load(baselinePath),compiled=load(compiledPath);prefix(donor,baseline);prefix(baseline,compiled);
        var donorDraw=body(donor,CELL,"Draw",false);var baselineDraw=body(baseline,CELL,"Draw",false);
        var projection=traceProjection(donor,donorDraw,baseline,baselineDraw);helperContract(compiled);compiledCall(compiled);fixtures(baseline);
        check(Arrays.equals(body(donor,CURRENT,"IsCurrent",true).getCodeBytes(),body(baseline,CURRENT,"IsCurrent",true).getCodeBytes()),"Baseline IsCurrent no longer equals reviewed donor");
        var initial=initialBlock(donor,donorDraw,projection,compiled);var preview=previewBlock(donorDraw,projection,compiled);
        var rewritten=rewrite(baselineDraw,List.of(initial,preview));var candidate=reparse(baseline);candidate.constants=compiled.constants;
        replace(candidate,rewritten.body);var oldCurrent=body(baseline,CURRENT,"IsCurrent",true);
        var newCurrent=adapted(body(compiled,CURRENT,"IsCurrent",true),oldCurrent,oldCurrent.method_info);replace(candidate,newCurrent);
        int helperId=candidate.method_info.size();var helperTrait=trait(compiled,CURRENT,"ApexCellRole",true).clone();
        for(var t:candidate.class_info.get(candidate.findClassByName(CURRENT)).static_traits.traits)check(!name(candidate,t.name_index).equals("ApexCellRole"),"Helper already exists");
        int maxDispatch=0;for(var t:candidate.class_info.get(candidate.findClassByName(CURRENT)).static_traits.traits)
            if(t instanceof TraitMethodGetterSetter)maxDispatch=Math.max(maxDispatch,((TraitMethodGetterSetter)t).disp_id);
        check(helperTrait.kindType==Trait.TRAIT_METHOD && helperTrait.kindFlags==trait(baseline,CURRENT,"IsCurrent",true).kindFlags &&
            helperTrait.disp_id==maxDispatch+1,"Helper must match retained static-final flags and append the next free dispatch id: flags="+helperTrait.kindFlags+" disp="+helperTrait.disp_id+" max="+maxDispatch);
        var madeHelper=body(compiled,CURRENT,"ApexCellRole",true);var helper=adapted(madeHelper,oldCurrent,helperId);
        // Same class, same compilation scope depth proven by the IsCurrent pair.
        int scopeDelta=oldCurrent.init_scope_depth-body(compiled,CURRENT,"IsCurrent",true).init_scope_depth;
        helper.init_scope_depth=madeHelper.init_scope_depth+scopeDelta;helper.max_scope_depth=madeHelper.max_scope_depth+scopeDelta;
        candidate.method_info.add(compiled.method_info.get(helperTrait.method_info));helperTrait.method_info=helperId;
        candidate.bodies.add(helper);candidate.class_info.get(candidate.findClassByName(CURRENT)).static_traits.traits.add(helperTrait);candidate.resetMethodIndexing();
        String drawHash=sha(rewritten.body.getCodeBytes()),currentHash=sha(newCurrent.getCodeBytes()),helperHash=sha(helper.getCodeBytes());
        verifyAll(baseline,candidate,rewritten,helperId,drawHash,currentHash,helperHash);var saved=reparse(candidate);verifyAll(baseline,saved,rewritten,helperId,drawHash,currentHash,helperHash);
        // Adversarial gate: mutate an unowned Main body; whole-ABC projection must reject.
        var adversary=reparse(saved);var main=adversary.instance_info.get(adversary.findClassByName(MAIN));
        var mainBody=adversary.findBody(main.iinit_index);var tampered=mainBody.clone();tampered.max_stack++;replace(adversary,tampered);
        boolean rejected=false;try{verifyAll(baseline,adversary,rewritten,helperId,drawHash,currentHash,helperHash);}catch(IllegalArgumentException expected){rejected=true;}
        check(rejected,"Unowned Main metadata corruption escaped projection");
        byte[] bytes=save(saved);Files.write(Path.of(outputPath),bytes);
        String json="{\"ok\":true,\"prototype_only\":false,\"baseline_swf_sha256\":\""+baselineSha+"\",\"donor_swf_sha256\":\""+DONOR_PIN+"\",\"base_donor_method_info_count\":"+donor.method_info.size()+",\"base_donor_body_count\":"+donor.bodies.size()+",\"baseline_method_info_count\":"+baseline.method_info.size()+",\"baseline_body_count\":"+baseline.bodies.size()+
            ",\"unchanged_baseline_bodies\":"+(baseline.bodies.size()-2)+",\"edited_baseline_methods\":2,\"draw_replaces_existing_trace_adapter\":true,\"additional_native_changes_after_base\":[\"dcc.history.CurrentOutfitUI.IsCurrent\"],\"base_contract_requires_post_adapter_chain\":true,\"appended_helpers\":1,\"helper_name\":\""+CURRENT+".ApexCellRole\",\"removed_draw_vector_scan_sites\":3,\"draw_original_instruction_spans\":[[9,58],[724,750]],\"explicit_jump_switch_exception_fixtures\":true,\"compiled_helper_control_flow_oracle\":true,\"compiled_cross_class_receiver_abi\":true,\"serialized_whole_abc_rollback_projection\":true,\"main_and_height_preserved\":true,\"unowned_corruption_rejected\":true,\"draw_sha256\":\""+drawHash+"\",\"is_current_sha256\":\""+currentHash+"\",\"helper_sha256\":\""+helperHash+"\",\"abc_sha256\":\""+sha(bytes)+"\",\"runtime_verified\":false,\"performance_gain_claimed\":false}";
        Files.writeString(Path.of(reportPath),json+"\n");System.out.println(json);
    }
    public static void main(String[] args)throws Exception{
        check(args.length==5,"Use pinned donor SWF, retained baseline SWF, helper compiler SWF, output ABC and report JSON");
        patch(args[0],args[1],args[2],args[3],args[4]);
    }
}
