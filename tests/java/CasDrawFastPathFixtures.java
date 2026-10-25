import java.nio.file.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;

/** Serialized adversaries and a deliberately limited Draw control-flow oracle.
 * Native instructions are opaque effects, not a replacement Flash VM.
 */
public class CasDrawFastPathFixtures {
    interface Throwing {void run()throws Exception;}
    interface Mutate {void run(ABC a)throws Exception;}
    static int checks=0;
    static void check(boolean b,String s){CasDrawFastPathPatch.check(b,s);}
    static void refuse(String name,Throwing test)throws Exception{
        boolean no=false;try{test.run();}catch(IllegalArgumentException expected){no=true;}
        check(no,"Accepted "+name);checks++;
    }
    static void changed(ABC base,CasDrawFastPathPatch.Envelope expected,String name,Mutate edit)throws Exception{
        var a=CasDrawFastPathPatch.reparse(base);CasDrawFastPathPatch.replace(a,expected.body().clone());edit.run(a);
        var parsed=CasDrawFastPathPatch.reparse(a);
        refuse(name,()->CasDrawFastPathPatch.verify(base,parsed,expected));
    }
    static void changeEdge(ABC a,int start,int end,int opcode,long destination){
        var b=CasDrawFastPathPatch.draw(a);var c=b.getCode().code;boolean found=false;
        for(int i=start;i<end;i++)if(CasDrawFastPathPatch.op(c.get(i))==opcode){CasDrawFastPathPatch.edge(c.get(i),destination);found=true;break;}
        check(found,"Fixture needs an actual edge");b.setModified();
    }
    record Run(List<Integer> nativeEffects,List<String> events,int callbackReads,int markerChecks){}
    static int enter(ABC a,MethodBody b,Object callback){
        var stack=new ArrayList<Object>();var c=b.getCode().code;Object main=new Object(),receiver=new Object();Object local=null;
        int at=0,reads=0,scope=0;
        while(at<7){var i=c.get(at);switch(CasDrawFastPathPatch.op(i)){
            case 0xd0:stack.add(receiver);break;
            case 0x30:check(stack.remove(stack.size()-1)==receiver,"Scope receiver");scope++;break;
            case 0x60:stack.add(main);break;
            case 0x66:check(stack.remove(stack.size()-1)==main,"Static callback receiver");reads++;stack.add(callback);break;
            case 0x2a:stack.add(stack.get(stack.size()-1));break;
            case 0x63:check(i.operands[0]==24,"Captured local");local=stack.remove(stack.size()-1);break;
            case 0x11:
                Object value=stack.remove(stack.size()-1);check(local==callback&&value==callback&&reads==1&&scope==1&&stack.isEmpty(),"Entry stack/scope or callback read count");
                return value==null?at+1:b.getCode().adr2pos(CasDrawFastPathPatch.target(i));
            default:throw new IllegalArgumentException("Unexpected envelope entry opcode");
        }at++;}throw new IllegalArgumentException("No entry decision");
    }
    static Map<Integer,Integer> nativeIndices(MethodBody baseline){
        var m=new HashMap<Integer,Integer>();var c=baseline.getCode().code;int n=0;
        for(int i=0;i<c.size();){if(i==2){i+=3;continue;}if(CasDrawFastPathPatch.op(c.get(i))==0x62&&c.get(i).operands[0]==24){i+=8;continue;}m.put(i++,n++);}return m;
    }
    static Run walk(ABC a,MethodBody b,int pc,boolean enabled,int seed,Map<Integer,Integer> indices,int throwAt,RuntimeException nativeError){
        var effects=new ArrayList<Integer>();var events=new ArrayList<String>();var code=b.getCode().code;int markers=0,steps=0;
        while(true){check(pc>=0&&pc<code.size()&&steps++<10000,"Invalid/unbounded fixture path");var i=code.get(pc);int op=CasDrawFastPathPatch.op(i);
            if(op==0x62&&i.operands[0]==24){
                check(CasDrawFastPathPatch.op(code.get(pc+1))==0x12,"Marker start");markers++;
                if(enabled)events.add(a.constants.getString(code.get(pc+4).operands[0]));
                pc+=8;continue;
            }
            Integer effect=indices.get(pc);check(effect!=null,"Entered removed code or opposite tail");
            if(effect==throwAt)throw nativeError;effects.add(effect);
            if(op==0x47)return new Run(effects,events,1,markers);
            if(CasDrawFastPathPatch.relative(i)){
                boolean branch=op==0x10||((Integer.rotateLeft(effect*0x9e3779b9,seed%31)^seed)&1)!=0;
                pc=branch?b.getCode().adr2pos(CasDrawFastPathPatch.target(i)):pc+1;
            }else pc++;
        }
    }
    static void oracle(ABC a,CasDrawFastPathPatch.Envelope e)throws Exception{
        var before=CasDrawFastPathPatch.draw(a);var made=e.body();var d=e.fast().body();var profileMap=nativeIndices(before);
        var fastMap=new HashMap<Integer,Integer>();for(int i=2;i<d.getCode().code.size();i++)fastMap.put(e.fastIndex()+i-2,i);
        var enabledMap=new HashMap<Integer,Integer>();for(var entry:profileMap.entrySet())if(entry.getKey()>=5)enabledMap.put(e.profileIndex()+entry.getKey()-5,entry.getValue());
        var plainMap=new HashMap<Integer,Integer>();for(int i=2;i<d.getCode().code.size();i++)plainMap.put(i,i);
        Object fn=new Object();int nullStart=enter(a,made,null),enabledStart=enter(a,made,fn);
        check(nullStart==e.fastIndex()&&enabledStart==e.profileIndex(),"Nullable callback chooses wrong tail");
        var nativeError=new RuntimeException("same native exception");int thrown=0;
        for(int seed=0;seed<512;seed++){
            var expected=walk(a,d,2,false,seed,plainMap,-1,nativeError);
            var fast=walk(a,made,nullStart,false,seed,fastMap,-1,nativeError);
            var profile=walk(a,before,5,true,seed,profileMap,-1,nativeError);
            var enabled=walk(a,made,enabledStart,true,seed,enabledMap,-1,nativeError);
            check(fast.nativeEffects.equals(expected.nativeEffects)&&fast.events.isEmpty()&&fast.markerChecks==0,"Disabled path does marker work or changes native flow");
            check(fast.nativeEffects.equals(profile.nativeEffects),"Removing markers changes original native branches/effect order");
            check(enabled.nativeEffects.equals(profile.nativeEffects)&&enabled.events.equals(profile.events)&&enabled.markerChecks==profile.markerChecks,"Enabled path changes native/diagnostic order");
            int throwAt=expected.nativeEffects.get(seed%expected.nativeEffects.size());
            for(boolean tracing:new boolean[]{false,true}){
                try{walk(a,made,tracing?enabledStart:nullStart,tracing,seed,tracing?enabledMap:fastMap,throwAt,nativeError);throw new AssertionError("Swallowed native throw");}
                catch(RuntimeException got){check(got==nativeError,"Native exception replaced");thrown++;}
            }
        }
        check(thrown==1024,"Native throw coverage");checks++;
    }
    public static void main(String[] args)throws Exception{
        var base=CasDrawFastPathPatch.read(Files.readAllBytes(Path.of(args[0])));var expected=CasDrawFastPathPatch.envelope(base,CasDrawFastPathPatch.draw(base));
        var good=CasDrawFastPathPatch.reparse(base);CasDrawFastPathPatch.replace(good,expected.body().clone());good=CasDrawFastPathPatch.reparse(good);
        CasDrawFastPathPatch.verify(base,good,expected);checks++;oracle(base,expected);
        changed(base,expected,"entry inverted",a->{var b=CasDrawFastPathPatch.draw(a);b.getCode().code.get(6).definition=CasDrawFastPathPatch.ins(0x12,0).definition;b.setModified();});
        changed(base,expected,"entry into marker interior",a->{var b=CasDrawFastPathPatch.draw(a);CasDrawFastPathPatch.edge(b.getCode().code.get(6),b.getCode().code.get(expected.profileIndex()+1).getAddress());b.setModified();});
        changed(base,expected,"entry falls into fast body",a->{var b=CasDrawFastPathPatch.draw(a);b.getCode().code.get(6).operands[0]=0;b.setModified();});
        changed(base,expected,"entry receiver",a->{var b=CasDrawFastPathPatch.draw(a);b.getCode().code.get(2).operands[0]=b.getCode().code.get(3).operands[0];b.setModified();});
        changed(base,expected,"entry local",a->{var b=CasDrawFastPathPatch.draw(a);b.getCode().code.get(5).operands[0]=23;b.setModified();});
        changed(base,expected,"fast unconditional jump into trace",a->changeEdge(a,expected.fastIndex(),expected.profileIndex(),0x10,CasDrawFastPathPatch.draw(a).getCode().code.get(expected.profileIndex()).getAddress()));
        changed(base,expected,"fast conditional into trace",a->changeEdge(a,expected.fastIndex(),expected.profileIndex(),0x12,CasDrawFastPathPatch.draw(a).getCode().code.get(expected.profileIndex()).getAddress()));
        changed(base,expected,"profile unconditional jump into fast",a->changeEdge(a,expected.profileIndex(),CasDrawFastPathPatch.draw(a).getCode().code.size(),0x10,CasDrawFastPathPatch.draw(a).getCode().code.get(expected.fastIndex()).getAddress()));
        changed(base,expected,"profile marker skip into fast",a->changeEdge(a,expected.profileIndex(),CasDrawFastPathPatch.draw(a).getCode().code.size(),0x12,CasDrawFastPathPatch.draw(a).getCode().code.get(expected.fastIndex()).getAddress()));
        changed(base,expected,"fast return fallthrough",a->{var b=CasDrawFastPathPatch.draw(a);b.getCode().code.get(expected.profileIndex()-1).definition=CasDrawFastPathPatch.ins(0x02).definition;b.setModified();});
        changed(base,expected,"profile receiver null",a->{var b=CasDrawFastPathPatch.draw(a);b.getCode().code.get(expected.profileIndex()+3).definition=CasDrawFastPathPatch.ins(0x20).definition;b.setModified();});
        changed(base,expected,"exception region across tails",a->{var b=CasDrawFastPathPatch.draw(a);var x=new ABCException();x.start=0;x.end=(int)b.getCode().code.get(expected.profileIndex()).getAddress();x.target=x.end;b.exceptions=new ABCException[]{x};});
        changed(base,expected,"max scope",a->CasDrawFastPathPatch.draw(a).max_scope_depth++);
        changed(base,expected,"max locals",a->CasDrawFastPathPatch.draw(a).max_regs++);
        changed(base,expected,"max stack",a->CasDrawFastPathPatch.draw(a).max_stack++);
        changed(base,expected,"foreign method metadata",a->{var d=CasDrawFastPathPatch.draw(a);for(var b:a.bodies)if(b.method_info!=d.method_info){b.max_stack++;break;}});
        changed(base,expected,"appended pool",a->a.constants.getStringId("unexpected fast path pool entry",true));
        changed(base,expected,"callback default",a->{int k=a.findClassByName(CasDrawFastPathPatch.MAIN);for(var t:a.class_info.get(k).static_traits.traits)if(CasDrawFastPathPatch.CALLBACK.equals(CasDrawFastPathPatch.name(a,t.name_index)))((com.jpexs.decompiler.flash.abc.types.traits.TraitSlotConst)t).value_index=1;});
        changed(base,expected,"callback type",a->{int k=a.findClassByName(CasDrawFastPathPatch.MAIN);for(var t:a.class_info.get(k).static_traits.traits)if(CasDrawFastPathPatch.CALLBACK.equals(CasDrawFastPathPatch.name(a,t.name_index)))((com.jpexs.decompiler.flash.abc.types.traits.TraitSlotConst)t).type_index=a.instance_info.get(k).name_index;});
        var switchInput=CasDrawFastPathPatch.reparse(base);var s=CasDrawFastPathPatch.draw(switchInput);var ops=new ArrayList<AVM2Instruction>();for(var i:s.getCode().code)ops.add(CasDrawFastPathPatch.copy(i));ops.add(CasDrawFastPathPatch.ins(0x1b,0,0,0));CasDrawFastPathPatch.set(s,ops);
        refuse("new input switch",()->CasDrawFastPathPatch.envelope(switchInput,s));
        var exceptionInput=CasDrawFastPathPatch.reparse(base);var x=CasDrawFastPathPatch.draw(exceptionInput);x.exceptions=new ABCException[]{new ABCException()};
        refuse("new input exception region",()->CasDrawFastPathPatch.envelope(exceptionInput,x));
        var interior=CasDrawFastPathPatch.reparse(base);var ib=CasDrawFastPathPatch.draw(interior);changeEdge(interior,5,ib.getCode().code.size(),0x10,ib.getCode().code.get(6).getAddress());
        refuse("input jump into marker interior",()->CasDrawFastPathPatch.envelope(interior,ib));
        System.out.println("PASS "+checks+" serialized cases;512 CFG paths each state;1024 identical native throws");
    }
}
