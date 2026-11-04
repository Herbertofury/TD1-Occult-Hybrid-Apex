import java.io.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;
import com.jpexs.helpers.MemoryInputStream;

public class CasGridBootstrapBytecodeFixtures {
    static void check(boolean b,String s){if(!b)throw new IllegalArgumentException(s);}
    static int op(AVM2Instruction i){return i.definition.instructionCode;}
    static AVM2Instruction ins(int n,int...a){return new AVM2Instruction(0,n,a);}
    static byte[] save(ABC a)throws Exception{var out=new ByteArrayOutputStream();a.saveToStream(out);return out.toByteArray();}
    static ABC parse(ABC a,byte[] b)throws Exception{return new ABC(new ABCInputStream(new MemoryInputStream(b)),a.getSwf(),null);}
    static void set(MethodBody b,List<AVM2Instruction> ops){long address=0;for(var i:ops){i.setAddress(address);address+=i.getBytesLength();}var c=b.getCode();c.code.clear();c.code.addAll(ops);b.setCode(c);b.setModified();}
    static void replace(ABC a,MethodBody b){for(int i=0;i<a.bodies.size();i++)if(a.bodies.get(i).method_info==b.method_info){a.bodies.set(i,b);return;}throw new IllegalArgumentException("Missing fixture body");}
    static long destination(AVM2Instruction i,int at){return i.getAddress()+(op(i)==27?0:i.getBytesLength())+i.operands[at];}
    static List<Integer> operands(AVM2Instruction i){
        var answer=new ArrayList<Integer>();int n=op(i);
        if(n>=12&&n<=26)answer.add(0);
        if(n==27){answer.add(0);for(int k=2;k<i.operands.length;k++)answer.add(k);}return answer;
    }
    // Independent fixture oracle: strip only exact receiver/call pairs, then
    // rebuild native relative offsets and compare complete recovered bytes.
    static void oracle(MethodBody original,MethodBody candidate,int boot,int late)throws Exception{
        var nativeOps=original.getCode().code;var kept=new ArrayList<AVM2Instruction>();var map=new HashMap<Long,Integer>();
        var code=candidate.getCode().code;int calls=0;
        for(int i=0;i<code.size();){var a=code.get(i);
            if(i+1<code.size()&&op(a)==208&&op(code.get(i+1))==79&&(code.get(i+1).operands[0]==boot||code.get(i+1).operands[0]==late)){
                check(code.get(i+1).operands[1]==0,"Hook argument corruption");map.put(a.getAddress(),kept.size());calls++;i+=2;
            }else{map.put(a.getAddress(),kept.size());kept.add(a);i++;}}
        map.put(candidate.getCode().getEndOffset(),kept.size());check(calls==2&&kept.size()==nativeOps.size(),"Oracle native/hook count differs");
        var recovered=new ArrayList<AVM2Instruction>();
        for(int i=0;i<kept.size();i++){var a=kept.get(i);var n=nativeOps.get(i);check(op(a)==op(n),"Oracle opcode differs");
            int[] args=a.operands==null?null:a.operands.clone();
            for(int k:operands(a)){Integer target=map.get(destination(a,k));check(target!=null,"Oracle invalid target");
                long targetAddress=target==nativeOps.size()?original.getCode().getEndOffset():nativeOps.get(target).getAddress();
                args[k]=Math.toIntExact(targetAddress-n.getAddress()-(op(a)==27?0:n.getBytesLength()));}
            recovered.add(new AVM2Instruction(n.getAddress(),op(a),args));}
        var rollback=original.clone();set(rollback,recovered);check(Arrays.equals(rollback.getCodeBytes(),original.getCodeBytes()),"Oracle native bytes not exactly recovered");
        check(original.exceptions.length==candidate.exceptions.length,"Oracle exception count differs");
        var nativeMap=new HashMap<Long,Integer>();for(int i=0;i<nativeOps.size();i++)nativeMap.put(nativeOps.get(i).getAddress(),i);nativeMap.put(original.getCode().getEndOffset(),nativeOps.size());
        for(int i=0;i<original.exceptions.length;i++){var a=original.exceptions[i];var b=candidate.exceptions[i];
            check(Objects.equals(nativeMap.get((long)a.start),map.get((long)b.start))&&Objects.equals(nativeMap.get((long)a.end),map.get((long)b.end))&&
                Objects.equals(nativeMap.get((long)a.target),map.get((long)b.target))&&a.type_index==b.type_index&&a.name_index==b.name_index,"Oracle original exception differs");}
        // Both inserted hooks preserve arbitrary live value-stack entries and
        // original locals, and call exactly the original this with no args.
        for(int i=0;i+1<code.size();i++)if(op(code.get(i))==208&&op(code.get(i+1))==79&&(code.get(i+1).operands[0]==boot||code.get(i+1).operands[0]==late))
            for(int depth=0;depth<=32;depth++){Object self=new Object();var stack=new ArrayList<Object>();for(int j=0;j<depth;j++)stack.add(new Object());var initial=new ArrayList<>(stack);
                stack.add(self);Object receiver=stack.remove(stack.size()-1);check(receiver==self&&code.get(i+1).operands[1]==0&&stack.equals(initial),"Hook this/value stack ABI differs");}
    }
    static MethodBody synthetic(ABC a,MethodBody nativeBody)throws Exception{
        var base=nativeBody.getCode().code;int literal=-1,handler=-1,history=-1;
        for(int i=0;i<base.size();i++){
            if(CasBytecodePatch.stringLiteral(a,base.get(i),"CASContextMenuSetMenuState"))literal=i;
            if(CasBytecodePatch.property(a,base.get(i),0x46,"HandleSetSimInfo"))handler=i;
            if(CasBytecodePatch.property(a,base.get(i),0x60,"HistoryHost"))history=i;}
        check(literal>0&&handler>0&&history>0,"Actual initializer anchors required");
        var code=new ArrayList<AVM2Instruction>();code.add(ins(208));code.add(ins(48));
        for(int i=literal-1;i<=literal+4;i++){var p=base.get(i);code.add(new AVM2Instruction(0,op(p),p.operands==null?null:p.operands.clone()));}
        // Reachable normal execution skips the backward explicit jump, while
        // the retained conditional/jump/switch edges exercise relocation.
        code.add(ins(38));code.add(ins(18,0));code.add(ins(38));code.add(ins(17,0));code.add(ins(16,0));
        code.add(ins(36,1));code.add(ins(27,0,1,0,0));
        code.add(ins(208));code.add(ins(32));code.add(ins(79,base.get(handler).operands[0],1));
        code.add(ins(16,0));code.add(ins(41));code.add(ins(16,0));code.add(ins(2));
        code.add(ins(96,base.get(history).operands[0]));code.add(ins(208));code.add(ins(79,base.get(history+2).operands[0],1));code.add(ins(71));
        var b=nativeBody.clone();b.exceptions=new ABCException[0];set(b,code);
        int[][] edges={{9,8},{11,13},{12,8},{18,22},{20,22}};
        for(int[] edge:edges)code.get(edge[0]).operands[0]=(int)(code.get(edge[1]).getAddress()-code.get(edge[0]).getAddress()-code.get(edge[0]).getBytesLength());
        code.get(14).operands[0]=(int)(code.get(15).getAddress()-code.get(14).getAddress());
        code.get(14).operands[2]=(int)(code.get(8).getAddress()-code.get(14).getAddress());
        code.get(14).operands[3]=(int)(code.get(15).getAddress()-code.get(14).getAddress());set(b,code);
        var e=new ABCException();e.start=(int)code.get(8).getAddress();e.end=(int)code.get(18).getAddress();e.target=(int)code.get(19).getAddress();
        b.exceptions=new ABCException[]{e};b.max_stack=nativeBody.max_stack;return b;
    }

    public static void main(String[] args)throws Exception{
        var abc=CasBytecodePatch.load(args[0]);String mode=args[1];
        var nativeBody=CasBytecodePatch.classMethod(abc,"widgets.CAS.Customizer.CASCustomizerMain","Initialize");
        int boot=abc.constants.getPublicQnameId("ApexCatalogGridBootstrap",true),late=abc.constants.getPublicQnameId("ApexInitialize",true);
        boolean synth=mode.startsWith("synthetic-")||mode.equals("bypass")||mode.equals("wrong-order");var before=synth?synthetic(abc,nativeBody):nativeBody.clone();
        if(mode.equals("missing")||mode.equals("duplicate")||mode.equals("receiver")){
            var ops=new ArrayList<>(before.getCode().code);int literal=-1;for(int i=0;i<ops.size();i++)if(CasBytecodePatch.stringLiteral(abc,ops.get(i),"CASContextMenuSetMenuState"))literal=i;
            if(mode.equals("missing"))ops.get(literal).operands[0]=abc.constants.getStringId("WrongListener",true);
            if(mode.equals("receiver"))ops.set(literal+1,ins(32));
            if(mode.equals("duplicate")){ops.add(ops.size()-1,ins(44,ops.get(literal).operands[0]));ops.add(ops.size()-1,ins(41));}set(before,ops);
            boolean refused=false;try{CasBytecodePatch.gridBootstrapAdapter(abc,before,boot,late);}catch(IllegalArgumentException expected){refused=true;}
            check(refused,"Invalid seam accepted: "+mode);System.out.println("PASS "+mode);return;
        }
        if(mode.equals("wrong-order")) {
            var ops=before.getCode().code;var first=new ArrayList<>(ops.subList(15,18));var second=new ArrayList<>(ops.subList(22,25));
            for(int i=0;i<3;i++){ops.set(15+i,second.get(i));ops.set(22+i,first.get(i));}set(before,new ArrayList<>(ops));
            boolean refused=false;try{CasBytecodePatch.gridBootstrapAdapter(abc,before,boot,late);}catch(IllegalArgumentException expected){refused=true;}
            check(refused,"Wrong native mutation/History ordering accepted");System.out.println("PASS "+mode);return;
        }
        if(mode.equals("bypass")){
            var ops=before.getCode().code;ops.get(0).definition=ins(16,0).definition;ops.get(0).operands=new int[]{0};set(before,new ArrayList<>(ops));
            before.getCode().code.get(0).operands[0]=(int)(before.getCode().code.get(15).getAddress()-before.getCode().code.get(0).getBytesLength());before.setModified();
            boolean refused=false;try{CasBytecodePatch.gridBootstrapAdapter(abc,before,boot,late);}catch(IllegalArgumentException expected){refused=true;}
            check(refused,"Bootstrap-bypassing control flow accepted");System.out.println("PASS "+mode);return;
        }
        replace(abc,before);byte[] baseline=save(abc);
        var adapted=CasBytecodePatch.gridBootstrapAdapter(abc,before,boot,late);replace(abc,adapted);var serialized=parse(abc,save(abc));
        var actual=serialized.findBody(before.method_info);
        if(mode.endsWith("stale-jump")||mode.endsWith("stale-switch")||mode.endsWith("stale-if")){
            int wanted=mode.endsWith("stale-jump")?16:mode.endsWith("stale-switch")?27:18;boolean changed=false;
            for(var op:actual.getCode().code)if(op(op)==wanted)for(var old:before.getCode().code)if(op(old)==wanted){
                for(int k:operands(op))if(op.operands[k]!=old.operands[k]){op.operands[k]=old.operands[k];changed=true;break;}if(changed)break;}
            check(changed,"Fixture must corrupt an actually relocated edge");actual.setModified();
        }
        if(mode.equals("synthetic-exception"))actual.exceptions[0].end++;
        if(mode.equals("wrong-this"))for(int i=0;i+1<actual.getCode().code.size();i++)if(op(actual.getCode().code.get(i+1))==79&&actual.getCode().code.get(i+1).operands[0]==boot){actual.getCode().code.set(i,ins(32));break;}
        if(mode.equals("wrong-args"))for(var op:actual.getCode().code)if(op(op)==79&&op.operands[0]==boot){op.operands[1]=1;break;}
        if(mode.equals("retained"))actual.getCode().code.get(2).definition=ins(2).definition;
        if(mode.equals("locals"))actual.max_regs++;
        actual.setModified();boolean refused=false;
        try{CasBytecodePatch.verifyGridBootstrapProjection(serialized,before,actual,boot,late);}catch(IllegalArgumentException expected){refused=true;}
        boolean valid=mode.equals("valid")||mode.equals("synthetic-valid");check(refused!=valid,"Projection misclassified "+mode);
        if(valid){oracle(before,actual,boot,late);replace(serialized,before.clone());check(Arrays.equals(baseline,save(serialized)),"Whole ABC rollback differs outside initializer hooks");}
        System.out.println("PASS "+mode);
    }
}
